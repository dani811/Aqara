"""High-level U200 client — the facade of the library (feature 015).

Composes the pieces that already exist into one flow, without touching the
protocol layer:

    login (CloudAuthManager, feature 014, incl. auto re-auth on code 108)
      → scan & identify (transport.scan → ScanCandidate, see scanner.py)
      → connect + GATT discovery (Transport.connect → GattClient)
      → operation (session.run_authenticated_lock_operation)

Usage::

    auth = CloudAuthManager(account=..., password=..., appid=..., appkey=...,
                            client_id=..., phone_id=..., region="EU")
    async with await U200Client.connect(auth=auth, transport=BleakTransport(),
                                        device_id="lumi1.xxxx") as lock:
        await lock.lock()

Every phase is bounded by a timeout and failures carry the phase they happened
in (`U200ClientError.phase`). No secret (password, token, session key) is ever
logged or shown in `repr`.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .auth import CloudAuthManager
from .errors import AmbiguousDeviceError, FlowPhase, NoDeviceFoundError, U200ClientError
from .gatt import GattClient
from .kdf import REGION_BASE_URLS, CloudServiceError, cloud_get_public_key
from .lock_ops import (
    LockOperation,
    LockOperationWrite,
    build_control_query_write,
    build_read_query_write,
    normalize_lock_operation,
)
from .lock_state import (
    SOURCE_BATTERY,
    SOURCE_KEEPALIVE,
    SOURCE_OPERATION,
    SOURCE_QUERY,
    LockEvent,
    LockSettings,
    LockState,
    decode_alarm_volume,
    decode_alert_volume,
    decode_assist_turn,
    decode_battery_info,
    decode_door_type,
    decode_event,
    decode_language,
    decode_lock_state,
    decode_lock_status,
    decode_lock_volume,
    decode_pull_spring,
    decode_state_report,
)
from .ota import VoicePackResult, run_voice_pack_ota
from .scanner import scan, select_preferred
from .session import (
    OperationInProgressError,
    PostAuthContext,
    SessionMaterial,
    run_authenticated_lock_operation,
)
from .transport import (
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_SCAN_TIMEOUT,
    DISCONNECT_TIMEOUT,
    ScanCandidate,
    Transport,
)


@dataclass(frozen=True)
class OperationResult:
    """What one operation produced (returned by `U200Client.operate`)."""

    operation: LockOperation
    response_hex: str | None
    write: LockOperationWrite
    session: SessionMaterial
    #: Real bolt position observed on the ff62 report channel during a
    #: post-command listen window (True locked / False unlocked / None not seen).
    observed_locked: bool | None = None

    @property
    def state(self) -> LockState:
        """The lock's response to this operation, as a `LockState`."""

        raw = bytes.fromhex(self.response_hex) if self.response_hex else None
        return decode_lock_state(raw, source=SOURCE_OPERATION)


class U200Client:
    """A connected U200. Build it with `connect()` (full flow) or `from_gatt()`."""

    def __init__(
        self,
        *,
        auth: CloudAuthManager,
        transport: Transport | None,
        gatt_client: GattClient,
        device_id: str,
        region: str = "EU",
        base_url: str | None = None,
        notify_timeout: float = 10.0,
        candidate: ScanCandidate | None = None,
    ) -> None:
        self.auth = auth
        self.transport = transport
        self.device_id = device_id
        self.region = region
        self.base_url = base_url
        self.notify_timeout = notify_timeout
        self.candidate = candidate
        self._gatt: GattClient | None = gatt_client
        self._closed = False

    # ── construction ────────────────────────────────────────────────────────

    @classmethod
    async def connect(
        cls,
        *,
        auth: CloudAuthManager,
        transport: Transport,
        device_id: str,
        mac: str | None = None,
        region: str = "EU",
        base_url: str | None = None,
        scan_timeout: float = DEFAULT_SCAN_TIMEOUT,
        connect_timeout: float = DEFAULT_CONNECT_TIMEOUT,
        notify_timeout: float = 10.0,
        login_first: bool = True,
    ) -> U200Client:
        """Run login → scan/identify → connect/discover and return a ready client.

        ``mac`` given → the transport connects straight to that address (a
        transport that cannot connect by address, e.g. CoreBluetooth, scans
        internally filtering by it). Without ``mac`` the transport scans and
        `select_preferred` picks the lock by name/services; a device that only
        shares the manufacturer id is never chosen automatically.

        ``login_first`` validates the credentials up front (fase LOGIN) so a bad
        password fails before touching the radio; the operation flow re-uses the
        cached token and refreshes it on code 108 by itself.
        """

        if login_first:
            try:
                await asyncio.to_thread(auth.build_signer)
            except CloudServiceError:
                raise
            except Exception as exc:
                raise U200ClientError(FlowPhase.LOGIN, str(exc)) from exc

        candidate: ScanCandidate | None = None
        target: ScanCandidate | str
        if mac is not None:
            target = mac
        else:
            try:
                candidates = await scan(transport, timeout=scan_timeout)
            except U200ClientError:
                raise
            except Exception as exc:
                raise U200ClientError(FlowPhase.SCAN, str(exc)) from exc
            candidate = select_preferred(candidates)
            target = candidate

        try:
            gatt = await asyncio.wait_for(
                transport.connect(target, timeout=connect_timeout),
                timeout=connect_timeout + 1.0,
            )
        except Exception as exc:
            with contextlib.suppress(Exception):
                await asyncio.wait_for(transport.disconnect(), timeout=DISCONNECT_TIMEOUT)
            raise U200ClientError(
                FlowPhase.CONNECT, f"no se pudo conectar/descubrir ({transport.name}): {exc}"
            ) from exc

        return cls(
            auth=auth,
            transport=transport,
            gatt_client=gatt,
            device_id=device_id,
            region=region,
            base_url=base_url,
            notify_timeout=notify_timeout,
            candidate=candidate,
        )

    @classmethod
    def from_gatt(
        cls,
        *,
        auth: CloudAuthManager,
        gatt_client: GattClient,
        device_id: str,
        region: str = "EU",
        base_url: str | None = None,
        notify_timeout: float = 10.0,
    ) -> U200Client:
        """Wrap an already-connected GATT client (tests, Home Assistant, …)."""

        return cls(
            auth=auth,
            transport=None,
            gatt_client=gatt_client,
            device_id=device_id,
            region=region,
            base_url=base_url,
            notify_timeout=notify_timeout,
        )

    # ── operations ──────────────────────────────────────────────────────────

    @property
    def connected(self) -> bool:
        return self._gatt is not None and not self._closed

    async def operate(
        self, operation: LockOperation | str, *, listen_after: float = 0.0
    ) -> OperationResult:
        """Run any catalogued `LockOperation` (by member, name or hex value).

        With ``listen_after > 0`` the session stays open that many seconds after
        the command and reads the lock's real bolt position from the ff62 report
        channel — ``OperationResult.observed_locked`` carries it (True/False, or
        None if nothing was pushed in the window).
        """

        if not self.connected or self._gatt is None:
            raise U200ClientError(
                FlowPhase.OPERATION, "el cliente está cerrado/desconectado; vuelve a conectar"
            )
        op = normalize_lock_operation(operation)
        observed: list[bool] = []

        def on_report(channel: str, data: bytes) -> None:
            if channel == "ff62":
                position = decode_state_report(data)
                if position is not None:
                    observed.append(position)

        try:
            material, write, response = await run_authenticated_lock_operation(
                client=self._gatt,
                device_id=self.device_id,
                auth_headers=None,
                region=self.region,
                base_url=self.base_url,
                operation=op,
                notify_timeout=self.notify_timeout,
                auth=self.auth,
                listen_after=listen_after,
                on_report=on_report if listen_after > 0 else None,
            )
        except (OperationInProgressError, CloudServiceError, U200ClientError):
            raise
        except Exception as exc:
            raise U200ClientError(FlowPhase.OPERATION, f"{op.name}: {exc}") from exc
        return OperationResult(
            operation=op,
            response_hex=response,
            write=write,
            session=material,
            observed_locked=observed[-1] if observed else None,
        )

    async def push_voice_pack_ota(
        self,
        blob: bytes,
        filename: str,
        *,
        arm: bool = True,
        data_delay: float = 0.006,
        window: int = 3,
        resume_from: int = 0,
        skip_manifest: bool = False,
        manifest_wait_s: float = 90.0,
        post_manifest_settle_s: float = 4.0,
        keepalive_every_s: float = 8.0,
        precomputed_cloud_pubkey: str | None = None,
        language_name: str | None = None,
        progress: Any = None,
    ) -> VoicePackResult:
        """Push a language voice-pack OTA FROM SCRATCH (not a replay) inside an
        authenticated session — builds the JSON handshake + manifest + XMODEM
        data stream from ``blob`` and drives :func:`run_voice_pack_ota`.
        ``filename`` is the CDN name (e.g. ``U200_ES_audio_burn.bin``)."""

        if not self.connected or self._gatt is None:
            raise U200ClientError(
                FlowPhase.OPERATION, "el cliente está cerrado/desconectado; vuelve a conectar"
            )

        result_box: list[VoicePackResult] = []

        async def _hook(ctx: PostAuthContext) -> None:
            result_box.append(
                await run_voice_pack_ota(
                    ctx, blob, filename, arm=arm, data_delay=data_delay, window=window,
                    resume_from=resume_from, skip_manifest=skip_manifest,
                    manifest_wait_s=manifest_wait_s, keepalive_every_s=keepalive_every_s,
                    post_manifest_settle_s=post_manifest_settle_s,
                    language_name=language_name, progress=progress
                )
            )

        try:
            await run_authenticated_lock_operation(
                client=self._gatt,
                device_id=self.device_id,
                auth_headers=None,
                region=self.region,
                base_url=self.base_url,
                operation=LockOperation.KEEPALIVE,  # placeholder; never sent (post_auth)
                notify_timeout=self.notify_timeout,
                auth=self.auth,
                post_auth=_hook,
                precomputed_cloud_pubkey=precomputed_cloud_pubkey,
            )
        except (OperationInProgressError, CloudServiceError, U200ClientError):
            raise
        except Exception as exc:
            raise U200ClientError(FlowPhase.OPERATION, f"voice-pack-ota: {exc}") from exc
        if not result_box:
            raise U200ClientError(FlowPhase.OPERATION, "voice-pack-ota: el hook no produjo resultado")
        return result_box[0]

    async def change_language(
        self, language: str, *, verify_md5: bool = True, **ota_kwargs: Any
    ) -> VoicePackResult:
        """Switch the lock's spoken-prompt language end-to-end, phone-free: look the
        pack up in the cloud voice list, download it from the CDN, then stream it to
        the lock with :meth:`push_voice_pack_ota`.

        ``language`` accepts the cloud code ("13"), the display name ("Español"), or
        the file-name code ("ES") — see :func:`aqara_ble.voice_ota.select_voice_pack`.
        Extra keyword args pass straight through to ``push_voice_pack_ota`` (e.g.
        ``data_delay``, ``window``, ``manifest_wait_s``).

        **Keypad presence is required and is the CALLER's job — not the library's.**
        A language change is a settings-class op: the lock only ACKs the manifest
        while a keypad key was pressed within its short presence window. The library
        does not (and cannot) press the keypad — pressing it is an external, physical
        act specific to the deployment (e.g. a fingerbot on the keypad, driven by Home
        Assistant). This call just holds the manifest handshake open for
        ``manifest_wait_s`` (default 90 s), re-sending it, so a single press landed
        anywhere in that window authorises the whole ~10-minute transfer. Arrange that
        press to happen after this coroutine starts and within ``manifest_wait_s``.
        """
        from .voice_ota import (  # noqa: PLC0415 - cloud/HTTP, only needed here
            cloud_get_voice_list,
            download_voice_pack,
            select_voice_pack,
        )

        signer = await asyncio.to_thread(self.auth.build_signer)
        base_url = self.base_url or REGION_BASE_URLS.get(self.region, REGION_BASE_URLS["EU"])
        rows = await asyncio.to_thread(cloud_get_voice_list, self.device_id, base_url, signer)
        pack = select_voice_pack(rows, language)
        blob = await asyncio.to_thread(download_voice_pack, pack, verify=verify_md5)
        # Pre-fetch the ephemeral cloud pubkey so the on-lock auth is instant once
        # connected — the manifest's keypad-presence window is short.
        pubkey = ota_kwargs.pop("precomputed_cloud_pubkey", None)
        if pubkey is None:
            pubkey = await asyncio.to_thread(
                cloud_get_public_key, self.device_id, None, base_url, signer
            )
        return await self.push_voice_pack_ota(
            blob, pack.file_name, language_name=pack.name or None,
            precomputed_cloud_pubkey=pubkey, **ota_kwargs
        )

    async def lock(self, *, listen_after: float = 0.0) -> str | None:
        return (await self.operate(LockOperation.LOCK, listen_after=listen_after)).response_hex

    async def unlock(self, *, listen_after: float = 0.0) -> str | None:
        return (await self.operate(LockOperation.UNLOCK, listen_after=listen_after)).response_hex

    async def status(self) -> LockState:
        """Read the lock state without actuating, via the confirmed keepalive poll.

        Sends only the read-only KEEPALIVE command (never an unconfirmed status
        opcode) and returns a `LockState` wrapping the decrypted response. Decoded
        fields stay ``None`` until confirmed by evidence — see `lock_state`.
        """

        result = await self.operate(LockOperation.KEEPALIVE)
        raw = bytes.fromhex(result.response_hex) if result.response_hex else None
        return decode_lock_state(raw, source=SOURCE_KEEPALIVE)

    async def listen(
        self,
        seconds: float = 15.0,
        *,
        on_state: Callable[[bool], None] | None = None,
        on_event: Callable[[LockEvent], None] | None = None,
        low_power: bool = False,
    ) -> list[tuple[str, str]]:
        """Keep the session open after a keepalive and collect spontaneous frames.

        Returns ``(channel, hex)`` for every extra frame the lock pushes within the
        window — control ff62 (decrypted), report ff64/ff92 (raw). Non-actuating
        (uses the keepalive poll).

        ``on_state`` fires **in real time** with the decoded bolt position each
        time the lock pushes an ff62 position report (0x1d/0xdd) — this is how a
        consumer keeps a persistent, real-time state session. ``low_power``
        requests a slow connection interval + slave latency, but **only transports
        that expose ``update_connection_parameters`` honour it** (the Bumble /
        ESP32-S3 central). Plain ``bleak`` — both CoreBluetooth and BlueZ — does
        not expose that call, so on a Home Assistant host the OS/controller (or a
        Bluetooth proxy) decides the interval; the request is a no-op there.
        """

        if not self.connected or self._gatt is None:
            raise U200ClientError(FlowPhase.OPERATION, "el cliente está cerrado; vuelve a conectar")
        reports: list[tuple[str, str]] = []

        def collect(channel: str, data: bytes) -> None:
            reports.append((channel, data.hex()))
            if channel != "ff62":
                return
            if on_state is not None:
                position = decode_state_report(data)
                if position is not None:
                    on_state(position)
            if on_event is not None:
                event = decode_event(data)
                if event is not None:
                    on_event(event)

        try:
            await run_authenticated_lock_operation(
                client=self._gatt,
                device_id=self.device_id,
                auth_headers=None,
                region=self.region,
                base_url=self.base_url,
                operation=LockOperation.KEEPALIVE,
                notify_timeout=self.notify_timeout,
                auth=self.auth,
                listen_after=seconds,
                on_report=collect,
                low_power_connection=low_power,
            )
        except (OperationInProgressError, CloudServiceError, U200ClientError):
            raise
        except Exception as exc:
            raise U200ClientError(FlowPhase.OPERATION, f"listen: {exc}") from exc
        return reports

    async def query(self, sub_cmd: int, data: bytes = b"") -> LockState:
        """Send a generic control opcode and return its decrypted response as state.

        Intended for probing **read-only** status opcodes (e.g. 0x07 LOCK_STATUS,
        0xE5 GET_DOOR_LOCK_STATUS) whose response may carry the bolt position,
        unlike the static keepalive/operate ACKs. The caller is responsible for
        sending only read-only opcodes (the CLI restricts this to a whitelist).
        """

        if not self.connected or self._gatt is None:
            raise U200ClientError(FlowPhase.OPERATION, "el cliente está cerrado; vuelve a conectar")
        write = build_control_query_write(sub_cmd, data)
        try:
            _material, _write, response = await run_authenticated_lock_operation(
                client=self._gatt,
                device_id=self.device_id,
                auth_headers=None,
                region=self.region,
                base_url=self.base_url,
                operation=write,
                notify_timeout=self.notify_timeout,
                auth=self.auth,
            )
        except (OperationInProgressError, CloudServiceError, U200ClientError):
            raise
        except Exception as exc:
            raise U200ClientError(FlowPhase.OPERATION, f"query 0x{sub_cmd:02x}: {exc}") from exc
        raw = bytes.fromhex(response) if response else None
        return decode_lock_state(raw, source=SOURCE_QUERY)

    async def battery(self) -> LockState:
        """Read the lock's battery over BLE (GET_BATTERY_INFO, 0xde).

        Sends the well-formed read frame `de 00 <trailer>` (see
        :func:`build_read_query_write`) and returns a :class:`LockState` whose
        ``battery_percent`` is decoded from the reply. Confirmed live: the lock
        answers `de0007000101300000c70a` → 48% (feature 030). Returns
        ``responded=False`` if the lock does not answer.
        """

        if not self.connected or self._gatt is None:
            raise U200ClientError(FlowPhase.OPERATION, "el cliente está cerrado; vuelve a conectar")
        write = build_read_query_write(0xDE)
        try:
            _material, _write, response = await run_authenticated_lock_operation(
                client=self._gatt,
                device_id=self.device_id,
                auth_headers=None,
                region=self.region,
                base_url=self.base_url,
                operation=write,
                notify_timeout=self.notify_timeout,
                auth=self.auth,
            )
        except (OperationInProgressError, CloudServiceError, U200ClientError):
            raise
        except Exception as exc:
            raise U200ClientError(FlowPhase.OPERATION, f"battery read: {exc}") from exc
        raw = bytes.fromhex(response) if response else None
        return LockState(
            raw_hex=raw.hex() if raw else None,
            source=SOURCE_BATTERY,
            responded=raw is not None,
            battery_percent=decode_battery_info(raw),
        )

    async def read_lock_status(self) -> LockState:
        """Read the real bolt position on demand over BLE (LOCK_STATUS, 0x07).

        Sends the well-formed read frame `07 00 <trailer>` and returns a
        :class:`LockState` whose ``locked`` is decoded from bit 0x02 of the status
        byte (confirmed live, correlated with ff62). Unlike :meth:`status`
        (keepalive, static), this reports the actual bolt position without waiting
        for a spontaneous ff62 report. Returns ``responded=False`` if unanswered.
        """

        if not self.connected or self._gatt is None:
            raise U200ClientError(FlowPhase.OPERATION, "el cliente está cerrado; vuelve a conectar")
        write = build_read_query_write(0x07)
        try:
            _material, _write, response = await run_authenticated_lock_operation(
                client=self._gatt,
                device_id=self.device_id,
                auth_headers=None,
                region=self.region,
                base_url=self.base_url,
                operation=write,
                notify_timeout=self.notify_timeout,
                auth=self.auth,
            )
        except (OperationInProgressError, CloudServiceError, U200ClientError):
            raise
        except Exception as exc:
            raise U200ClientError(FlowPhase.OPERATION, f"lock-status read: {exc}") from exc
        raw = bytes.fromhex(response) if response else None
        return LockState(
            raw_hex=raw.hex() if raw else None,
            source=SOURCE_QUERY,
            responded=raw is not None,
            locked=decode_lock_status(raw),
        )

    async def read(self, opcode: int) -> LockState:
        """Read any SYSTEM read opcode over BLE and return the decrypted response.

        Sends the well-formed read frame `<opcode> 00 <trailer>` and returns a
        :class:`LockState` with the raw hex; ``locked`` and ``battery_percent`` are
        filled in when ``opcode`` is LOCK_STATUS (0x07) / GET_BATTERY_INFO (0xde).
        Intended for **read-only** opcodes — see
        :func:`aqara_ble.operations_catalog.system_read_opcodes`; the caller is
        responsible for not passing a mutating opcode.
        """

        if not self.connected or self._gatt is None:
            raise U200ClientError(FlowPhase.OPERATION, "el cliente está cerrado; vuelve a conectar")
        write = build_read_query_write(opcode)
        try:
            _material, _write, response = await run_authenticated_lock_operation(
                client=self._gatt,
                device_id=self.device_id,
                auth_headers=None,
                region=self.region,
                base_url=self.base_url,
                operation=write,
                notify_timeout=self.notify_timeout,
                auth=self.auth,
            )
        except (OperationInProgressError, CloudServiceError, U200ClientError):
            raise
        except Exception as exc:
            raise U200ClientError(FlowPhase.OPERATION, f"read 0x{opcode:02x}: {exc}") from exc
        raw = bytes.fromhex(response) if response else None
        return LockState(
            raw_hex=raw.hex() if raw else None,
            source=SOURCE_QUERY,
            responded=raw is not None,
            locked=decode_lock_status(raw),
            battery_percent=decode_battery_info(raw),
        )

    async def _read_raw(self, opcode: int) -> bytes | None:
        st = await self.read(opcode)
        return bytes.fromhex(st.raw_hex) if st.raw_hex else None

    async def read_burst(self, frames_hex: list[str]) -> list[tuple[str, str | None]]:
        """Read many control frames in ONE authenticated session (persistent).

        Each item in ``frames_hex`` is a raw plaintext control frame in hex — the
        bytes fed to AES-CCM (e.g. ``"c3044301"`` = volume, opcode 0xc3 / kind 0x04).
        An item may carry an explicit **write-prefix** as ``"PP:frame"`` (hex),
        e.g. ``"03:200320"`` for finger count — the ff61 write byte differs per op
        family: volume/language/alarm/lock-setting use ``01`` (the default), while
        finger `0x20`, log-sync `0x13`, `0x1f` and voice-OTA `0xa6` use ``03`` (from
        the app's decrypted session). Authenticates once and sends them all on the
        same session, mirroring the official app. Returns ``(spec, response_hex_or_
        None)`` for each, in order. Run within ~40 s of a wake.
        """
        if not self.connected or self._gatt is None:
            raise U200ClientError(FlowPhase.OPERATION, "el cliente está cerrado; vuelve a conectar")
        if not frames_hex:
            return []
        from .lock_ops import LockOperationWrite  # noqa: PLC0415

        def _mk(spec: str) -> LockOperationWrite:
            prefix = 0x01
            fh = spec
            if ":" in spec:
                pfx, fh = spec.split(":", 1)
                prefix = int(pfx, 16)
            return LockOperationWrite(
                operation=f"burst:{spec}", payload=bytes.fromhex(fh), write_prefix=prefix
            )

        # Route EVERY read through the follow-up path, which correlates each reply
        # to its request by opcode and discards spontaneous state events (0x1d/
        # 0xdd/0x15) that share the notify channel. A harmless keepalive is the
        # primary op (its reply is not opcode-checked, so it must not be a real
        # read — otherwise a stray event could steal it).
        primary = _mk("2f012f")  # keepalive, never actuation
        follow_ups = [_mk(fh) for fh in frames_hex]
        follow_out: list[tuple[object, str | None]] = []
        try:
            await run_authenticated_lock_operation(
                client=self._gatt,
                device_id=self.device_id,
                auth_headers=None,
                region=self.region,
                base_url=self.base_url,
                operation=primary,
                notify_timeout=self.notify_timeout,
                auth=self.auth,
                follow_up_ops=follow_ups,
                follow_up_out=follow_out,
            )
        except (OperationInProgressError, CloudServiceError, U200ClientError):
            raise
        except Exception as exc:
            raise U200ClientError(FlowPhase.OPERATION, f"read_burst: {exc}") from exc
        out: list[tuple[str, str | None]] = []
        for fh, (_op, resp) in zip(frames_hex, follow_out, strict=False):
            out.append((fh, resp))
        return out

    async def read_settings(self) -> LockSettings:
        """Read the configuration settings over BLE in ONE persistent session.

        Reads volume (0xc3), language (0x68), alarm volume (0x84) and the
        lock-setting blob (0x1a — carries the alert volume) in a single
        opcode-correlated burst, mirroring the official app. Returns a
        :class:`LockSettings`; a field is ``None`` if that opcode did not answer.
        Requires a live connection (wake the lock's radio to connect; no per-read
        keypad touch is needed once connected).
        """
        frames = ["c3044301", "680168", "84020407", "1a011a"]
        results = dict(await self.read_burst(frames))

        def _raw(frame: str) -> bytes | None:
            resp = results.get(frame)
            return bytes.fromhex(resp) if resp else None

        return LockSettings(
            alert_volume=decode_alert_volume(_raw("1a011a")),
            system_volume=decode_lock_volume(_raw("c3044301")),
            language=decode_language(_raw("680168")),
            alarm_volume=decode_alarm_volume(_raw("84020407")),
            raw={f: results.get(f) for f in frames},
        )

    async def read_door_type(self) -> str | None:
        """Read the configured door-lock type over BLE ('eu'/'uk'/'us'; 0xe0)."""
        return decode_door_type(await self._read_raw(0xE0))

    async def read_assist_turn(self) -> bool | None:
        """Read whether turn-assist is enabled over BLE (0xe9)."""
        return decode_assist_turn(await self._read_raw(0xE9))

    async def read_pull_spring(self) -> tuple[bool, int] | None:
        """Read the pull-spring setting over BLE → (enabled, retraction_seconds) (0xe4)."""
        return decode_pull_spring(await self._read_raw(0xE4))

    # ── lifecycle ───────────────────────────────────────────────────────────

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._gatt = None
        if self.transport is not None:
            with contextlib.suppress(Exception):
                await asyncio.wait_for(self.transport.disconnect(), timeout=DISCONNECT_TIMEOUT)

    async def __aenter__(self) -> U200Client:
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.close()

    def __repr__(self) -> str:
        transport = self.transport.name if self.transport is not None else "external"
        return (
            f"U200Client(device_id={self.device_id!r}, transport={transport!r}, "
            f"connected={self.connected})"
        )


__all__ = [
    "AmbiguousDeviceError",
    "FlowPhase",
    "NoDeviceFoundError",
    "OperationResult",
    "U200Client",
    "U200ClientError",
]
