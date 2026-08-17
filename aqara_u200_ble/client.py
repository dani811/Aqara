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
from dataclasses import dataclass
from typing import Any

from .auth import CloudAuthManager
from .errors import AmbiguousDeviceError, FlowPhase, NoDeviceFoundError, U200ClientError
from .gatt import GattClient
from .kdf import CloudServiceError
from .lock_ops import LockOperation, LockOperationWrite, normalize_lock_operation
from .lock_state import SOURCE_KEEPALIVE, SOURCE_OPERATION, LockState, decode_lock_state
from .scanner import scan, select_preferred
from .session import (
    OperationInProgressError,
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

    async def operate(self, operation: LockOperation | str) -> OperationResult:
        """Run any catalogued `LockOperation` (by member, name or hex value)."""

        if not self.connected or self._gatt is None:
            raise U200ClientError(
                FlowPhase.OPERATION, "el cliente está cerrado/desconectado; vuelve a conectar"
            )
        op = normalize_lock_operation(operation)
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
            )
        except (OperationInProgressError, CloudServiceError, U200ClientError):
            raise
        except Exception as exc:
            raise U200ClientError(FlowPhase.OPERATION, f"{op.name}: {exc}") from exc
        return OperationResult(operation=op, response_hex=response, write=write, session=material)

    async def lock(self) -> str | None:
        return (await self.operate(LockOperation.LOCK)).response_hex

    async def unlock(self) -> str | None:
        return (await self.operate(LockOperation.UNLOCK)).response_hex

    async def status(self) -> LockState:
        """Read the lock state without actuating, via the confirmed keepalive poll.

        Sends only the read-only KEEPALIVE command (never an unconfirmed status
        opcode) and returns a `LockState` wrapping the decrypted response. Decoded
        fields stay ``None`` until confirmed by evidence — see `lock_state`.
        """

        result = await self.operate(LockOperation.KEEPALIVE)
        raw = bytes.fromhex(result.response_hex) if result.response_hex else None
        return decode_lock_state(raw, source=SOURCE_KEEPALIVE)

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
