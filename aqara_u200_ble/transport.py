"""BLE transports for the U200 client facade (feature 015).

A *transport* is the radio the facade drives: it knows how to **scan** for
advertisements, **connect** to a peripheral (including GATT service and
characteristic discovery) and **disconnect**. It hands back a `GattClient`
(see `gatt.py`) that `session.run_authenticated_lock_operation` consumes, so
the protocol layer is identical whichever radio is used.

Two implementations ship with the package, each importing its optional
dependency lazily so the package itself stays dependency-free:

- `BleakTransport` — the host's native Bluetooth stack (macOS / Linux / Windows)
  through `bleak` (extra: `aqara-u200-ble[ble]`).
- `BumbleTransport` — an external HCI controller (e.g. an ESP32-S3 running
  `tools/esp32s3_hci_usb`) through `bumble` (extra: `aqara-u200-ble[bumble]`).

Scan results are `ScanCandidate`s: what was seen on the air plus *why* it looks
like a U200 (`reasons`), so a consumer can identify the lock without knowing its
MAC and never connects blindly to a device that merely shares the manufacturer
id (a real false positive observed on 2026-08-17).
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from .gatt import GattClient
from .session import AUTH_SERVICE_UUID, AUX_SERVICE_UUID, CONTROL_SERVICE_UUID

# ── identification constants ─────────────────────────────────────────────────

#: Local name the U200 advertises.
EXPECTED_NAME = "DoorLocker"
#: Bluetooth SIG company identifier Aqara/Lumi puts in the manufacturer data.
AQARA_COMPANY_ID = 0x0B27
#: Services the U200 exposes (auth fcb9, control ff60, auxiliary ff90). Used both
#: to identify a candidate from its advertisement and to restrict discovery on
#: stacks (CoreBluetooth) that refuse to enumerate descriptors of foreign services.
U200_SERVICE_UUIDS: tuple[str, ...] = (
    AUTH_SERVICE_UUID,
    CONTROL_SERVICE_UUID,
    AUX_SERVICE_UUID,
)
#: 16-bit short forms of the same services, for advertisements that carry them short.
U200_SERVICE_UUID16: tuple[str, ...] = tuple(u[4:8] for u in U200_SERVICE_UUIDS)

#: Scores that make up `ScanCandidate.score` (higher = more certainly the lock).
SCORE_BY_REASON: Mapping[str, int] = {"mac": 8, "name": 4, "service": 2, "manufacturer": 1}

#: Timeouts shared by the transports (seconds).
DEFAULT_SCAN_TIMEOUT = 30.0
DEFAULT_CONNECT_TIMEOUT = 20.0
DEFAULT_DISCOVERY_TIMEOUT = 15.0
DISCONNECT_TIMEOUT = 5.0


def normalize_mac(value: str) -> str:
    """Uppercase, colon-separated MAC (accepts `aa-bb-…`, `aabbcc…`, `AA:BB:…`)."""

    hexdigits = "".join(ch for ch in value if ch.isalnum()).upper()
    if len(hexdigits) == 12 and all(c in "0123456789ABCDEF" for c in hexdigits):
        return ":".join(hexdigits[i : i + 2] for i in range(0, 12, 2))
    return value.upper()


def _normalize_uuid(uuid: str) -> str:
    return str(uuid).lower().replace("0x", "")


def _is_u200_service(uuid: str) -> bool:
    """Match a normalized UUID (16-bit short or 128-bit) against the U200 services."""

    if uuid in U200_SERVICE_UUIDS or uuid in U200_SERVICE_UUID16:
        return True
    return len(uuid) == 36 and uuid[4:8] in U200_SERVICE_UUID16


@dataclass(frozen=True, order=False)
class ScanCandidate:
    """A device seen on the air that may be the U200 (see data-model.md)."""

    address: str
    name: str | None
    rssi: int | None
    service_uuids: tuple[str, ...] = ()
    manufacturer_data: Mapping[int, bytes] = field(default_factory=dict)
    reasons: frozenset[str] = frozenset()
    score: int = 0
    #: Stack-specific handle (e.g. bleak's BLEDevice) used to reconnect. Not
    #: part of equality/repr — it may carry platform objects.
    raw: Any = field(default=None, repr=False, compare=False)

    @property
    def is_preferred(self) -> bool:
        """True when identified by something stronger than the manufacturer id."""

        return bool(self.reasons & {"mac", "name", "service"})

    def sort_key(self) -> tuple[int, int]:
        return (self.score, self.rssi if self.rssi is not None else -999)


def identify_candidate(
    *,
    address: str,
    name: str | None,
    rssi: int | None,
    service_uuids: tuple[str, ...] | list[str] = (),
    manufacturer_data: Mapping[int, bytes] | None = None,
    mac: str | None = None,
    raw: Any = None,
) -> ScanCandidate | None:
    """Classify one advertisement. Returns None when nothing points to a U200.

    Reasons: ``mac`` (address equals the requested MAC), ``name`` (local name is
    `DoorLocker`), ``service`` (advertises any U200 service, 16- or 128-bit),
    ``manufacturer`` (carries Aqara's company id). When ``mac`` is given and the
    address does not match, the device is filtered out regardless of the rest.
    """

    manufacturer_data = dict(manufacturer_data or {})
    normalized_services = tuple(_normalize_uuid(u) for u in service_uuids)
    reasons: set[str] = set()

    if mac is not None:
        if normalize_mac(address) != normalize_mac(mac):
            return None
        reasons.add("mac")
    if name == EXPECTED_NAME:
        reasons.add("name")
    if any(_is_u200_service(uuid) for uuid in normalized_services):
        reasons.add("service")
    if AQARA_COMPANY_ID in manufacturer_data:
        reasons.add("manufacturer")
    if not reasons:
        return None
    return ScanCandidate(
        address=address,
        name=name,
        rssi=rssi,
        service_uuids=normalized_services,
        manufacturer_data=manufacturer_data,
        reasons=frozenset(reasons),
        score=sum(SCORE_BY_REASON[r] for r in reasons),
        raw=raw,
    )


#: After the first *preferred* candidate is seen, keep listening this long so a
#: stronger advertisement (name, MAC) can still be collected, then stop early
#: instead of burning the whole scan timeout. Verified 2026-08-17: the U200 often
#: shows services before its name, and a full 30 s wait made connect() take ~30 s.
SCAN_SETTLE_SECONDS = 2.0


def _early_stop(candidate: ScanCandidate, mac: str | None, done: asyncio.Event) -> None:
    """Stop the scan once we clearly have the lock (MAC match or a preferred hit)."""

    if mac is not None or candidate.is_preferred:
        loop = asyncio.get_running_loop()
        loop.call_later(SCAN_SETTLE_SECONDS if mac is None else 0.0, done.set)


# ── the transport contract ───────────────────────────────────────────────────


@runtime_checkable
class Transport(Protocol):
    """What the facade needs from a radio: scan, connect (+discover), disconnect."""

    name: str

    async def scan(self, timeout: float, *, mac: str | None = None) -> list[ScanCandidate]: ...

    async def connect(self, target: ScanCandidate | str, *, timeout: float) -> GattClient: ...

    async def disconnect(self) -> None: ...


def _missing_extra(module: str, extra: str) -> ImportError:
    return ImportError(
        f"Falta la dependencia opcional '{module}'. Instala el extra: "
        f"pip install 'aqara-u200-ble[{extra}]'"
    )


# ── native stack via bleak ───────────────────────────────────────────────────


class BleakTransport:
    """Native Bluetooth through `bleak`.

    Discovery is restricted to the U200 services (`U200_SERVICE_UUIDS`): verified
    on macOS 2026-08-17 that a plain `BleakClient(dev)` fails in `_get_services`
    with `CBErrorDomain Code=8 "The specified UUID is not allowed for this
    operation"` while enumerating descriptors of a foreign characteristic, and
    that passing `services=[…]` connects and reaches the CCCD/cloud phases.

    On CoreBluetooth `address` is a system UUID, not the MAC: `connect()` with a
    bare MAC string therefore scans first, filtering by that MAC (harmless on
    Linux, where the address *is* the MAC and the filter matches directly).
    """

    name = "bleak"

    def __init__(self, *, services: tuple[str, ...] = U200_SERVICE_UUIDS) -> None:
        try:
            import bleak  # noqa: PLC0415
        except ImportError as exc:  # pragma: no cover - exercised via monkeypatched sys.modules
            raise _missing_extra("bleak", "ble") from exc
        self._bleak = bleak
        self._services = services
        self._client: Any = None

    async def scan(self, timeout: float, *, mac: str | None = None) -> list[ScanCandidate]:
        found: dict[str, ScanCandidate] = {}
        done = asyncio.Event()

        def detection(device: Any, adv: Any) -> None:
            candidate = identify_candidate(
                address=device.address,
                name=adv.local_name,
                rssi=adv.rssi,
                service_uuids=tuple(adv.service_uuids or ()),
                manufacturer_data=adv.manufacturer_data,
                mac=mac,
                raw=device,
            )
            if candidate is None:
                return
            found[device.address] = candidate
            _early_stop(candidate, mac, done)

        scanner = self._bleak.BleakScanner(detection_callback=detection)
        async with scanner:
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(done.wait(), timeout=timeout)
        return sorted(found.values(), key=ScanCandidate.sort_key, reverse=True)

    async def connect(self, target: ScanCandidate | str, *, timeout: float) -> GattClient:
        if isinstance(target, ScanCandidate) and target.raw is not None:
            device: Any = target.raw
        elif isinstance(target, ScanCandidate):
            device = target.address
        else:
            candidates = await self.scan(timeout, mac=target)
            if not candidates:
                raise LookupError(
                    f"no se encontró ningún dispositivo con MAC {normalize_mac(target)}"
                )
            device = candidates[0].raw or candidates[0].address
        client = self._bleak.BleakClient(device, timeout=timeout, services=list(self._services))
        await client.connect()
        self._client = client
        return client

    async def disconnect(self) -> None:
        client, self._client = self._client, None
        if client is None:
            return
        with contextlib.suppress(Exception):
            await asyncio.wait_for(client.disconnect(), timeout=DISCONNECT_TIMEOUT)


# ── external HCI controller via bumble ───────────────────────────────────────


class BumbleTransport:
    """External HCI controller (ESP32-S3 + `tools/esp32s3_hci_usb`) via `bumble`.

    `port` is a bumble transport spec, e.g. ``serial:/dev/cu.usbmodemNNNN,115200``.
    Connection parameters mirror the real phone (interval 45 ms, latency 0,
    supervision 5000 ms — verified against a live Android HCI capture). The U200
    does **not** support bonding: sending any SMP request makes it drop the link
    (observed live 2026-08-11), so this transport never calls ``pair()``.
    """

    name = "bumble"

    def __init__(
        self,
        port: str,
        *,
        local_address: str = "F0:F1:F2:F3:F4:F5",
        discovery_timeout: float = DEFAULT_DISCOVERY_TIMEOUT,
    ) -> None:
        try:
            import bumble.device  # noqa: PLC0415
            import bumble.hci  # noqa: PLC0415
            import bumble.transport  # noqa: PLC0415
        except ImportError as exc:  # pragma: no cover - exercised via monkeypatched sys.modules
            raise _missing_extra("bumble", "bumble") from exc
        self._bumble_device = bumble.device
        self._bumble_hci = bumble.hci
        self._bumble_transport = bumble.transport
        self.port = port
        self.local_address = local_address
        self.discovery_timeout = discovery_timeout
        self._transport: Any = None
        self._device: Any = None
        self._connection: Any = None

    async def _ensure_device(self) -> Any:
        if self._device is not None:
            return self._device
        self._transport = await self._bumble_transport.open_transport(self.port)
        source, sink = self._transport.source, self._transport.sink
        device = self._bumble_device.Device.with_hci(
            "aqara-u200-ble",
            self.local_address,  # type: ignore[arg-type]  # str is accepted at runtime
            source,
            sink,
        )
        await device.power_on()
        self._device = device
        return device

    async def scan(self, timeout: float, *, mac: str | None = None) -> list[ScanCandidate]:
        device = await self._ensure_device()
        found: dict[str, ScanCandidate] = {}
        done = asyncio.Event()

        def on_advertisement(adv: Any) -> None:
            address = str(adv.address).split("/")[0]
            data = adv.data
            name = None
            services: list[str] = []
            manufacturer: dict[int, bytes] = {}
            try:
                from bumble.core import AdvertisingData  # noqa: PLC0415

                name = data.get(AdvertisingData.COMPLETE_LOCAL_NAME) or data.get(
                    AdvertisingData.SHORTENED_LOCAL_NAME
                )
                for key in (
                    AdvertisingData.COMPLETE_LIST_OF_16_BIT_SERVICE_CLASS_UUIDS,
                    AdvertisingData.INCOMPLETE_LIST_OF_16_BIT_SERVICE_CLASS_UUIDS,
                    AdvertisingData.COMPLETE_LIST_OF_128_BIT_SERVICE_CLASS_UUIDS,
                    AdvertisingData.INCOMPLETE_LIST_OF_128_BIT_SERVICE_CLASS_UUIDS,
                ):
                    services.extend(str(u) for u in (data.get(key) or []))
                md = data.get(AdvertisingData.MANUFACTURER_SPECIFIC_DATA)
                if md:
                    company, payload = md
                    manufacturer[int(company)] = bytes(payload)
            except Exception:  # pragma: no cover - defensive against bumble API drift
                pass
            candidate = identify_candidate(
                address=address,
                name=name,
                rssi=getattr(adv, "rssi", None),
                service_uuids=tuple(services),
                manufacturer_data=manufacturer,
                mac=mac,
            )
            if candidate is None:
                return
            found[address] = candidate
            _early_stop(candidate, mac, done)

        device.on("advertisement", on_advertisement)
        await device.start_scanning()
        try:
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(done.wait(), timeout=timeout)
        finally:
            with contextlib.suppress(Exception):
                await asyncio.wait_for(device.stop_scanning(), timeout=DISCONNECT_TIMEOUT)
            device.remove_listener("advertisement", on_advertisement)
        return sorted(found.values(), key=ScanCandidate.sort_key, reverse=True)

    async def connect(self, target: ScanCandidate | str, *, timeout: float) -> GattClient:
        from .bumble_transport import BumbleGattAdapter  # noqa: PLC0415

        device = await self._ensure_device()
        mac = target.address if isinstance(target, ScanCandidate) else target
        prefs = self._bumble_device.ConnectionParametersPreferences(
            connection_interval_min=45.0,
            connection_interval_max=45.0,
            max_latency=0,
            supervision_timeout=5000,
        )
        connection = await asyncio.wait_for(
            device.connect(
                normalize_mac(mac),
                connection_parameters_preferences={self._bumble_hci.Phy.LE_1M: prefs},
            ),
            timeout=timeout,
        )
        self._connection = connection
        # No pairing/bonding on purpose (see class docstring): straight to discovery.
        peer = self._bumble_device.Peer(connection)
        await asyncio.wait_for(peer.discover_services(), timeout=self.discovery_timeout)
        for service in peer.services:
            await asyncio.wait_for(
                peer.discover_characteristics(service=service), timeout=self.discovery_timeout
            )
        return BumbleGattAdapter(peer)

    async def disconnect(self) -> None:
        connection, self._connection = self._connection, None
        if connection is not None:
            with contextlib.suppress(Exception):
                await asyncio.wait_for(connection.disconnect(), timeout=DISCONNECT_TIMEOUT)
        device, self._device = self._device, None
        if device is not None:
            with contextlib.suppress(Exception):
                await asyncio.wait_for(device.power_off(), timeout=DISCONNECT_TIMEOUT)
        transport, self._transport = self._transport, None
        if transport is not None:
            with contextlib.suppress(Exception):
                await asyncio.wait_for(transport.close(), timeout=DISCONNECT_TIMEOUT)


__all__ = [
    "AQARA_COMPANY_ID",
    "DEFAULT_CONNECT_TIMEOUT",
    "DEFAULT_DISCOVERY_TIMEOUT",
    "DEFAULT_SCAN_TIMEOUT",
    "EXPECTED_NAME",
    "SCORE_BY_REASON",
    "U200_SERVICE_UUIDS",
    "BleakTransport",
    "BumbleTransport",
    "ScanCandidate",
    "Transport",
    "identify_candidate",
    "normalize_mac",
]
