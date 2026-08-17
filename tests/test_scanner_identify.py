"""Scan identification & selection (feature 015, US2).

Pure logic, no radio: `identify_candidate` classifies simulated advertisements
and `select_preferred` applies the picking rules (name/service beat a bare
manufacturer id; ties without a MAC are refused; MAC filters exclusively).
"""

from __future__ import annotations

import asyncio

import pytest

from aqara_u200_ble import (
    AQARA_COMPANY_ID,
    AmbiguousDeviceError,
    NoDeviceFoundError,
    ScanCandidate,
    identify_candidate,
    scan,
    select_preferred,
)
from aqara_u200_ble.session import AUTH_SERVICE_UUID, CONTROL_SERVICE_UUID

MAC_LOCK = "CA:FE:00:00:00:01"
MAC_OTHER = "CA:FE:00:00:00:02"


def adv(address: str, name: str | None = None, services=(), manufacturer=None, rssi=-60, mac=None):
    return identify_candidate(
        address=address,
        name=name,
        rssi=rssi,
        service_uuids=tuple(services),
        manufacturer_data=manufacturer or {},
        mac=mac,
    )


# ── identify_candidate ──────────────────────────────────────────────────────


def test_name_only_is_preferred_with_score_4() -> None:
    c = adv(MAC_LOCK, name="DoorLocker")
    assert c is not None and c.reasons == {"name"} and c.score == 4 and c.is_preferred


def test_manufacturer_only_is_not_preferred() -> None:
    c = adv(MAC_OTHER, name="vuart:ktunnel", manufacturer={AQARA_COMPANY_ID: b"\x01"})
    assert c is not None and c.reasons == {"manufacturer"} and c.score == 1
    assert not c.is_preferred


def test_service_16bit_and_128bit_are_recognised() -> None:
    short = adv(MAC_LOCK, services=("fcb9",))
    full = adv(MAC_LOCK, services=(CONTROL_SERVICE_UUID.upper(),))
    assert short is not None and "service" in short.reasons
    assert full is not None and "service" in full.reasons and full.score == 2


def test_foreign_device_is_ignored() -> None:
    assert adv("11:22:33:44:55:66", name="Printer", services=("180f",)) is None


def test_mac_filter_excludes_others_and_adds_reason() -> None:
    assert adv(MAC_OTHER, name="DoorLocker", mac=MAC_LOCK) is None
    c = adv(MAC_LOCK, name="DoorLocker", mac="ca-fe-00-00-00-01")
    assert c is not None and c.reasons == {"name", "mac"} and c.score == 12


def test_all_reasons_stack() -> None:
    c = adv(
        MAC_LOCK,
        name="DoorLocker",
        services=(AUTH_SERVICE_UUID,),
        manufacturer={AQARA_COMPANY_ID: b""},
        mac=MAC_LOCK,
    )
    assert c is not None and c.score == 15


def test_raw_is_excluded_from_repr_and_eq() -> None:
    a = ScanCandidate(address=MAC_LOCK, name="DoorLocker", rssi=-50, raw=object())
    b = ScanCandidate(address=MAC_LOCK, name="DoorLocker", rssi=-50, raw=None)
    assert a == b and "raw" not in repr(a)


# ── select_preferred ────────────────────────────────────────────────────────


def test_prefers_name_over_manufacturer_only() -> None:
    lock = adv(MAC_LOCK, name="DoorLocker", rssi=-80)
    other = adv(MAC_OTHER, manufacturer={AQARA_COMPANY_ID: b""}, rssi=-40)
    assert select_preferred([other, lock]) is lock


def test_manufacturer_only_pool_refuses_to_pick() -> None:
    other = adv(MAC_OTHER, manufacturer={AQARA_COMPANY_ID: b""})
    with pytest.raises(NoDeviceFoundError) as info:
        select_preferred([other])
    assert info.value.phase.value == "scan" and info.value.seen == [other]


def test_empty_pool_mentions_keypad() -> None:
    with pytest.raises(NoDeviceFoundError, match="teclado"):
        select_preferred([])


def test_tie_without_mac_is_ambiguous() -> None:
    a = adv(MAC_LOCK, name="DoorLocker", rssi=-50)
    b = adv(MAC_OTHER, name="DoorLocker", rssi=-50)
    with pytest.raises(AmbiguousDeviceError) as info:
        select_preferred([a, b])
    assert {c.address for c in info.value.candidates} == {MAC_LOCK, MAC_OTHER}


def test_tie_broken_by_mac() -> None:
    a = adv(MAC_LOCK, name="DoorLocker")
    b = adv(MAC_OTHER, name="DoorLocker")
    assert select_preferred([a, b], mac=MAC_OTHER) is b


def test_mac_not_seen_raises() -> None:
    a = adv(MAC_LOCK, name="DoorLocker")
    with pytest.raises(NoDeviceFoundError, match="MAC"):
        select_preferred([a], mac=MAC_OTHER)


# ── scan() delegates and sorts ──────────────────────────────────────────────


class _FakeTransport:
    name = "fake"

    def __init__(self, result):
        self.result = result
        self.calls = []

    async def scan(self, timeout, *, mac=None):
        self.calls.append((timeout, mac))
        return list(self.result)

    async def connect(self, target, *, timeout):  # pragma: no cover
        raise NotImplementedError

    async def disconnect(self):  # pragma: no cover
        pass


def test_scan_sorts_best_first_and_passes_args() -> None:
    weak = adv(MAC_LOCK, name="DoorLocker", rssi=-90)
    strong = adv(MAC_OTHER, name="DoorLocker", services=("fcb9",), rssi=-40)
    t = _FakeTransport([weak, strong])
    out = asyncio.run(scan(t, timeout=3.0, mac=None))
    assert out == [strong, weak] and t.calls == [(3.0, None)]
