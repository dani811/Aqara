# SPDX-License-Identifier: AGPL-3.0-only
# SPDX-FileCopyrightText: 2026 dani811 <https://github.com/dani811/Aqara>
#
# This file is part of Aqara BLE, licensed under the GNU Affero General Public
# License v3.0 (AGPL-3.0-only). You may use, study, share and modify it; any
# distributed or network-served derivative must stay licensed under the AGPL
# and keep this notice. See the LICENSE file for the full terms.

"""LockState decode is honest: raw always, confirmed-only fields (feature 019)."""

from __future__ import annotations

from aqara_ble import LockState, decode_lock_state
from aqara_ble.lock_state import (
    SOURCE_KEEPALIVE,
    SOURCE_OPERATION,
    decode_alarm_volume,
    decode_alert_volume,
    decode_assist_turn,
    decode_battery_info,
    decode_door_type,
    decode_event,
    decode_language,
    decode_lock_status,
    decode_lock_volume,
    decode_pull_spring,
)

# Real samples captured 2026-08-17.
KEEPALIVE_RESP = bytes.fromhex("2f002c06")
UNLOCK_RESP = bytes.fromhex("74007706")
# GET_BATTERY_INFO (0xde) reply captured live 2026-08-25 (feature 030): 48%.
BATTERY_RESP = bytes.fromhex("de0007000101300000c70a")


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


def test_decode_battery_info_from_confirmed_frame() -> None:
    # de 00 07 00 01 01 <pct=0x30> 00 00 <crc16> -> 48%
    assert decode_battery_info(BATTERY_RESP) == 48


def test_decode_lock_status_from_confirmed_frames() -> None:
    # Correlated live with ff62 (2026-08-25): bit 0x02 of byte 2 = unlocked.
    assert decode_lock_status(bytes.fromhex("07000400000000000095a5")) is True  # locked
    assert decode_lock_status(bytes.fromhex("0700060000000000001556")) is False  # unlocked
    assert decode_lock_status(bytes.fromhex("07000b000000000000970d")) is False  # unlocked (0x0b)


def test_decode_lock_status_rejects_non_status() -> None:
    assert decode_lock_status(None) is None
    assert decode_lock_status(bytes.fromhex("de0007000101300000c70a")) is None  # battery, not 0x07
    assert decode_lock_status(bytes.fromhex("0700")) is None  # too short


def test_decode_feature_settings_from_app_correlated_frames() -> None:
    # Correlated live with the phone app (2026-08-25).
    assert decode_door_type(bytes.fromhex("e0000101")) == "eu"
    assert decode_door_type(bytes.fromhex("e0000201")) == "uk"
    assert decode_door_type(bytes.fromhex("e0000901")) == "type-9"  # unknown → labelled
    assert decode_assist_turn(bytes.fromhex("e90000847f")) is False
    assert decode_assist_turn(bytes.fromhex("e90001847f")) is True
    assert decode_pull_spring(bytes.fromhex("e400010200")) == (True, 2)
    assert decode_pull_spring(bytes.fromhex("e400000000")) == (False, 0)


def test_decode_feature_settings_reject_wrong_opcode() -> None:
    assert decode_door_type(bytes.fromhex("de0007000101300000c70a")) is None
    assert decode_assist_turn(None) is None
    assert decode_pull_spring(bytes.fromhex("e400")) is None  # too short


def test_decode_event_from_captured_ff62_stream() -> None:
    # Captured live 2026-08-26 holding the connection while operating the lock.
    unlock = decode_event(bytes.fromhex("dd010be58e6a927f"))
    assert unlock.kind == "unlocked" and unlock.locked is False
    assert unlock.timestamp == 0x6A8EE50B

    lock = decode_event(bytes.fromhex("1dff0900dec0cae58e6ab9cd"))
    assert lock.kind == "locked" and lock.locked is True and lock.source == "manual"

    other = decode_event(bytes.fromhex("1d2002000180f3e28e6a3c01"))
    assert other.kind == "locked" and other.source == "source-0x20"

    batt = decode_event(bytes.fromhex("de070001012f0000d65f"))
    assert batt.kind == "battery" and batt.battery_percent == 47

    status = decode_event(bytes.fromhex("1506cae58e6ab43d"))
    assert status.kind == "status"

    assert decode_event(None) is None
    assert decode_event(b"\x00") is None


def test_decode_battery_info_rejects_non_battery_and_out_of_range() -> None:
    assert decode_battery_info(None) is None
    assert decode_battery_info(bytes.fromhex("2f002c06")) is None  # keepalive, not 0xde
    assert decode_battery_info(bytes.fromhex("de00")) is None  # too short
    # 0xde reply shape but percentage byte > 100 is rejected (not invented).
    assert decode_battery_info(bytes.fromhex("de00070001016500000000")) is None


# ── configuration settings reads (real samples captured live 2026-08-27) ─────
# Alert volume lives in the 0x1a lock-setting blob (byte 4); pinned by
# change-and-reread on the real lock: Alto=01, Bajo=03, Silencio=04 → Medio=02.
ALERT_ALTO = bytes.fromhex("1a000001010a010102000002001c77")
ALERT_BAJO = bytes.fromhex("1a000001030a010102000002009e54")
ALERT_SILENCIO = bytes.fromhex("1a000001040a010102000002001927")
VOLUME_RESP = bytes.fromhex("c300020482")  # system volume (0xc3)
LANGUAGE_ES = bytes.fromhex("680002010000106c")  # Español (0x68)
ALARM_RESP = bytes.fromhex("84000200101e")  # alarm volume (0x84)


def test_decode_alert_volume_from_confirmed_frames() -> None:
    assert decode_alert_volume(ALERT_ALTO) == "high"
    assert decode_alert_volume(ALERT_BAJO) == "low"
    assert decode_alert_volume(ALERT_SILENCIO) == "silent"
    # Medio (0x02) inferred between Alto/Bajo.
    assert decode_alert_volume(bytes.fromhex("1a000001020a01010200000200aaaa")) == "medium"


def test_decode_alert_volume_unknown_and_bad_replies() -> None:
    assert decode_alert_volume(bytes.fromhex("1a000001070a01010200000200aaaa")) == "level-7"
    assert decode_alert_volume(None) is None
    assert decode_alert_volume(bytes.fromhex("c300020482")) is None  # wrong opcode
    assert decode_alert_volume(bytes.fromhex("1a0000")) is None  # too short


def test_decode_lock_volume_and_language_and_alarm() -> None:
    assert decode_lock_volume(VOLUME_RESP) == 0x02
    assert decode_lock_volume(None) is None
    assert decode_lock_volume(bytes.fromhex("680002010000106c")) is None  # wrong opcode
    assert decode_language(LANGUAGE_ES) == "es"
    assert decode_language(bytes.fromhex("680002050000abcd")) == "lang-5"  # unknown index (byte 3)
    assert decode_language(None) is None
    assert decode_alarm_volume(ALARM_RESP) == "0200"  # value bytes minus opcode/status/crc
    assert decode_alarm_volume(None) is None
