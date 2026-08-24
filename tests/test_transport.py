"""Pure-logic unit tests for discovery + transport (feature 005).

The Bumble adapter's characteristic lookup is exercised against an in-memory fake
peer — no bumble, no BLE, no hardware. The live scan and end-to-end unlock need a
real controller and are validated live, not here (Principle V).
"""

from __future__ import annotations

import pytest

from aqara_ble import BumbleGattAdapter
from aqara_ble.scanner import AQARA_COMPANY_ID, EXPECTED_NAME


class FakeChar:
    def __init__(self, uuid: str) -> None:
        self.uuid = uuid


class FakeService:
    def __init__(self, characteristics: list[FakeChar]) -> None:
        self.characteristics = characteristics


class FakePeer:
    """Minimal stand-in for a bumble Peer: just exposes discovered services."""

    def __init__(self, services: list[FakeService]) -> None:
        self.services = services


def _peer_with(*uuids: str) -> FakePeer:
    return FakePeer([FakeService([FakeChar(u) for u in uuids])])


def test_find_by_short_uuid_resolves_auth_char() -> None:
    peer = _peer_with("0000ff07-0000-1000-8000-00805f9b34fb")
    adapter = BumbleGattAdapter(peer)
    ch = adapter._find("0000ff07-0000-1000-8000-00805f9b34fb")
    assert ch.uuid == "0000ff07-0000-1000-8000-00805f9b34fb"


def test_find_missing_characteristic_raises() -> None:
    peer = _peer_with("0000ff07-0000-1000-8000-00805f9b34fb")
    adapter = BumbleGattAdapter(peer)
    with pytest.raises(KeyError):
        adapter._find("0000ff61-2333-5b1e-9d7c-c687fd2f04f2")


def test_find_by_uuid16_resolves_standard_char() -> None:
    peer = _peer_with("2b29")
    adapter = BumbleGattAdapter(peer)
    ch = adapter._find_by_uuid16(0x2B29)
    assert ch.uuid == "2b29"


def test_find_by_uuid16_missing_raises() -> None:
    peer = _peer_with("2a01")
    adapter = BumbleGattAdapter(peer)
    with pytest.raises(KeyError):
        adapter._find_by_uuid16(0x2B29)


def test_scanner_constants() -> None:
    assert AQARA_COMPANY_ID == 0x0B27
    assert EXPECTED_NAME == "DoorLocker"
