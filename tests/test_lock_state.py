"""LockState decode is honest: raw always, confirmed-only fields (feature 019)."""

from __future__ import annotations

from aqara_ble import LockState, decode_lock_state
from aqara_ble.lock_state import SOURCE_KEEPALIVE, SOURCE_OPERATION

# Real samples captured 2026-08-17.
KEEPALIVE_RESP = bytes.fromhex("2f002c06")
UNLOCK_RESP = bytes.fromhex("74007706")


def test_raw_is_preserved_and_flagged_responded() -> None:
    st = decode_lock_state(KEEPALIVE_RESP, SOURCE_KEEPALIVE)
    assert st.raw_hex == "2f002c06" and st.responded is True
    assert st.source == "keepalive" and st.sub_command == 0x2F


def test_unconfirmed_fields_stay_none() -> None:
    # We must never invent a state: locked/battery unknown until evidence.
    st = decode_lock_state(UNLOCK_RESP, SOURCE_OPERATION)
    assert st.locked is None and st.battery_percent is None
    assert st.raw_hex == "74007706" and st.sub_command == 0x74


def test_no_response_is_not_a_state() -> None:
    st = decode_lock_state(None, SOURCE_KEEPALIVE)
    assert st.responded is False and st.raw_hex is None
    assert st.locked is None and st.sub_command is None


def test_garbage_bytes_do_not_raise() -> None:
    st = decode_lock_state(b"\x00", SOURCE_KEEPALIVE)
    assert st.raw_hex == "00" and st.responded is True and st.locked is None


def test_lockstate_is_frozen_and_exported() -> None:
    st = LockState(raw_hex="2f00", source="keepalive", responded=True)
    assert st.sub_command == 0x2F
