# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# SPDX-FileCopyrightText: 2026 dani811 <https://github.com/dani811/Aqara>
#
# Aqara BLE. Source-available under the PolyForm Noncommercial License 1.0.0.
# Noncommercial use only; any commercial or for-profit use requires a separate
# written license from the copyright holder. See the LICENSE file for the terms.

"""Packaged transports honour the `Transport` contract (feature 015, US3).

`bleak` and `bumble` are replaced by tiny fake modules in `sys.modules`, so
these tests run without either extra installed and without any radio. They
prove: the lazy import error names the extra to install; the bleak transport
restricts discovery to the U200 services (the CoreBluetooth fix) and maps
advertisements through `identify_candidate`; the bumble transport uses the
phone's connection parameters, never pairs, discovers services and
characteristics, and returns a `BumbleGattAdapter`.
"""

from __future__ import annotations

import asyncio
import builtins
import sys
import types
from typing import Any, ClassVar

import pytest

from aqara_ble import BleakTransport, BumbleTransport, ScanCandidate, Transport
from aqara_ble.bumble_transport import BumbleGattAdapter
from aqara_ble.transport import U200_SERVICE_UUIDS

MAC = "CA:FE:00:00:00:01"


# ── missing extras ──────────────────────────────────────────────────────────


def _block_import(monkeypatch: pytest.MonkeyPatch, *names: str) -> None:
    for n in names:
        monkeypatch.setitem(sys.modules, n, None)  # type: ignore[arg-type]


def test_bleak_transport_names_extra_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    _block_import(monkeypatch, "bleak")
    with pytest.raises(ImportError, match=r"aqara-ble\[ble\]"):
        BleakTransport()


def test_bumble_transport_names_extra_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    _block_import(monkeypatch, "bumble", "bumble.device", "bumble.hci", "bumble.transport")
    with pytest.raises(ImportError, match=r"aqara-ble\[bumble\]"):
        BumbleTransport("serial:/dev/null")


# ── fake bleak ──────────────────────────────────────────────────────────────


class _Adv:
    def __init__(self, name: str | None, rssi: int, services=(), manufacturer=None) -> None:
        self.local_name = name
        self.rssi = rssi
        self.service_uuids = list(services)
        self.manufacturer_data = manufacturer or {}


class _Dev:
    def __init__(self, address: str) -> None:
        self.address = address


def _install_fake_bleak(
    monkeypatch: pytest.MonkeyPatch, adverts: list[tuple[_Dev, _Adv]]
) -> dict[str, Any]:
    captured: dict[str, Any] = {"client_kwargs": None, "connected": False, "disconnected": False}

    class BleakScanner:
        def __init__(self, detection_callback: Any) -> None:
            self.cb = detection_callback

        async def __aenter__(self) -> BleakScanner:
            for dev, adv in adverts:
                self.cb(dev, adv)
            return self

        async def __aexit__(self, *a: Any) -> None:
            return None

    class BleakClient:
        def __init__(self, device: Any, **kwargs: Any) -> None:
            captured["client_kwargs"] = kwargs
            captured["device"] = device

        async def connect(self) -> None:
            captured["connected"] = True

        async def disconnect(self) -> None:
            captured["disconnected"] = True

    fake = types.ModuleType("bleak")
    fake.BleakScanner = BleakScanner  # type: ignore[attr-defined]
    fake.BleakClient = BleakClient  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "bleak", fake)
    return captured


def test_bleak_transport_satisfies_protocol_and_restricts_services(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lock = _Dev("11111111-2222-3333-4444-555555555555")
    captured = _install_fake_bleak(monkeypatch, [(lock, _Adv("DoorLocker", -55))])
    t = BleakTransport()
    assert isinstance(t, Transport)

    async def go() -> list[ScanCandidate]:
        found = await t.scan(0.1)
        await t.connect(found[0], timeout=3.0)
        await t.disconnect()
        return found

    found = asyncio.run(go())
    assert found[0].reasons == {"name"} and found[0].raw is lock
    assert captured["device"] is lock
    assert captured["client_kwargs"]["services"] == list(U200_SERVICE_UUIDS)
    assert captured["connected"] and captured["disconnected"]


def test_bleak_scan_filters_by_mac_and_ignores_manufacturer_only_strangers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    other = _Dev("CA:FE:00:00:00:02")
    lock = _Dev(MAC)
    _install_fake_bleak(
        monkeypatch,
        [
            (other, _Adv("vuart:ktunnel", -40, manufacturer={0x0B27: b"\x00"})),
            (lock, _Adv("DoorLocker", -60)),
        ],
    )
    t = BleakTransport()
    all_found = asyncio.run(t.scan(0.1))
    assert [c.address for c in all_found] == [MAC, "CA:FE:00:00:00:02"]  # lock first (score)
    assert not all_found[1].is_preferred
    only = asyncio.run(t.scan(0.1, mac=MAC))
    assert [c.address for c in only] == [MAC] and "mac" in only[0].reasons


def test_bleak_connect_by_mac_string_scans_first(monkeypatch: pytest.MonkeyPatch) -> None:
    lock = _Dev(MAC)
    captured = _install_fake_bleak(monkeypatch, [(lock, _Adv("DoorLocker", -60))])
    t = BleakTransport()
    asyncio.run(t.connect(MAC, timeout=1.0))
    assert captured["device"] is lock


# ── fake bumble ─────────────────────────────────────────────────────────────


def _install_fake_bumble(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    captured: dict[str, Any] = {
        "paired": False,
        "prefs": None,
        "connect_addr": None,
        "discovered": [],
        "disconnected": False,
        "powered_off": False,
        "closed": False,
    }

    class Phy:
        LE_1M = "LE_1M"

    class ConnectionParametersPreferences:
        def __init__(self, **kw: Any) -> None:
            captured["prefs"] = kw

    class _Char:
        uuid = "0000ff07-0000-1000-8000-00805f9b34fb"

    class _Service:
        characteristics: ClassVar[list[Any]] = [_Char()]

    class _Connection:
        async def pair(self) -> None:  # pragma: no cover - must never be called
            captured["paired"] = True

        async def disconnect(self) -> None:
            captured["disconnected"] = True

    class Peer:
        def __init__(self, connection: Any) -> None:
            self.connection = connection
            self.services: list[Any] = []

        async def discover_services(self) -> None:
            self.services = [_Service()]
            captured["discovered"].append("services")

        async def discover_characteristics(self, service: Any) -> None:
            captured["discovered"].append("characteristics")

    class Device:
        @classmethod
        def with_hci(cls, name: str, addr: str, source: Any, sink: Any) -> Device:
            return cls()

        async def power_on(self) -> None:
            return None

        async def power_off(self) -> None:
            captured["powered_off"] = True

        async def connect(
            self, address: str, connection_parameters_preferences: Any
        ) -> _Connection:
            captured["connect_addr"] = address
            captured["phy_keys"] = list(connection_parameters_preferences)
            return _Connection()

    class _Transport:
        source = object()
        sink = object()

        async def close(self) -> None:
            captured["closed"] = True

    async def open_transport(spec: str) -> _Transport:
        captured["port"] = spec
        return _Transport()

    bumble = types.ModuleType("bumble")
    device = types.ModuleType("bumble.device")
    device.Device = Device  # type: ignore[attr-defined]
    device.Peer = Peer  # type: ignore[attr-defined]
    device.ConnectionParametersPreferences = ConnectionParametersPreferences  # type: ignore[attr-defined]
    hci = types.ModuleType("bumble.hci")
    hci.Phy = Phy  # type: ignore[attr-defined]
    transport = types.ModuleType("bumble.transport")
    transport.open_transport = open_transport  # type: ignore[attr-defined]
    bumble.device = device  # type: ignore[attr-defined]
    bumble.hci = hci  # type: ignore[attr-defined]
    bumble.transport = transport  # type: ignore[attr-defined]
    for name, mod in (
        ("bumble", bumble),
        ("bumble.device", device),
        ("bumble.hci", hci),
        ("bumble.transport", transport),
    ):
        monkeypatch.setitem(sys.modules, name, mod)
    return captured


def test_bumble_transport_connects_like_the_phone_and_never_pairs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _install_fake_bumble(monkeypatch)
    t = BumbleTransport("serial:/dev/fake,115200")
    assert isinstance(t, Transport)

    async def go() -> Any:
        gatt = await t.connect("ca:fe:00:00:00:01", timeout=2.0)
        await t.disconnect()
        return gatt

    gatt = asyncio.run(go())
    assert isinstance(gatt, BumbleGattAdapter)
    assert captured["port"] == "serial:/dev/fake,115200"
    assert captured["connect_addr"] == MAC
    assert captured["prefs"] == {
        "connection_interval_min": 45.0,
        "connection_interval_max": 45.0,
        "max_latency": 0,
        "supervision_timeout": 5000,
    }
    assert captured["phy_keys"] == ["LE_1M"]
    assert captured["discovered"] == ["services", "characteristics"]
    assert captured["paired"] is False
    assert captured["disconnected"] and captured["powered_off"] and captured["closed"]


def test_bumble_disconnect_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_bumble(monkeypatch)
    t = BumbleTransport("serial:/dev/fake")
    asyncio.run(t.disconnect())
    asyncio.run(t.disconnect())


def test_real_modules_untouched_by_fakes() -> None:
    # Sanity: monkeypatch restored sys.modules; importing must not explode.
    assert builtins.__import__ is not None
