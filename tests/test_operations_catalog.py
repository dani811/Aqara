# SPDX-License-Identifier: AGPL-3.0-only
# SPDX-FileCopyrightText: 2026 dani811 <https://github.com/dani811/Aqara>
#
# This file is part of Aqara BLE, licensed under the GNU Affero General Public
# License v3.0 (AGPL-3.0-only). You may use, study, share and modify it; any
# distributed or network-served derivative must stay licensed under the AGPL
# and keep this notice. See the LICENSE file for the full terms.

"""Tests for the operation & settings catalog and the generic builder (feature 010).

Pure logic: opcodes and frame structure, no BLE and no network (Principle V).
The catalog reproduces the app's decompiled command enum with an honest
confirmed/catalogued status; only the feature-009 commands are confirmed.
"""

from __future__ import annotations

import pytest

from aqara_ble import (
    OPERATIONS_CATALOG,
    CommandFamily,
    OperationStatus,
    build_control_frame,
    build_operate_frame,
    find_operation,
    operations_in_family,
)

ALL_FAMILIES = [
    CommandFamily.SYSTEM,
    CommandFamily.USER,
    CommandFamily.LOG,
    CommandFamily.ALARM,
    CommandFamily.DEVICELOG,
    CommandFamily.XXQ,
    CommandFamily.SYSTEM_EXT,
    CommandFamily.LONG,
]


def test_all_eight_families_present_and_non_empty() -> None:
    for family in ALL_FAMILIES:
        ops = operations_in_family(family.main_cmd)
        assert ops, f"family {family.name} has no operations"


def test_family_reply_byte_is_main_or_0x80() -> None:
    assert CommandFamily.SYSTEM.reply == 0x81
    assert CommandFamily.USER.reply == 0x82
    assert CommandFamily.LONG.reply == 0xBF


def test_confirmed_set_is_exactly_open_close_keepalive_and_2026_08_28_sweep() -> None:
    confirmed = {
        (e.family.main_cmd, e.sub_cmd)
        for e in OPERATIONS_CATALOG
        if e.status is OperationStatus.CONFIRMED
    }
    # Open and close share sub 0x74; keepalive is 0x2f. 0xAF/0xD5 were added by
    # the 2026-08-28 settings sweep (see build_set_verify_fail_time /
    # build_set_auto_lockup_delay_time); 0x03 (LANGUAGE) and 0xC4
    # (SET_AUXILIARY_LOCKING) by the 2026-08-29 sweep. All under SYSTEM.
    assert confirmed == {
        (0x01, 0x74),
        (0x01, 0x2F),
        (0x01, 0x02),
        (0x01, 0x18),
        (0x01, 0x83),
        (0x01, 0xAF),
        (0x01, 0xD5),
        (0x01, 0x03),
        (0x01, 0xC4),
    }


def test_confirmed_entries_carry_a_frame_catalogued_do_not() -> None:
    for e in OPERATIONS_CATALOG:
        if e.status is OperationStatus.CONFIRMED:
            assert e.confirmed_frame is not None
        else:
            assert e.confirmed_frame is None


def test_find_operation_hits_and_misses() -> None:
    open_op = find_operation(0x01, 0x74)
    assert open_op is not None and open_op.name == "BLE_OPEN_LOCK"
    assert open_op.status is OperationStatus.CONFIRMED
    volume = find_operation(0x01, 0x02)
    assert volume is not None and volume.name == "VOLUME"
    assert volume.status is OperationStatus.CONFIRMED
    still_catalogued = find_operation(0x01, 0x04)
    assert still_catalogued is not None and still_catalogued.name == "DOUBLE_VERIFY"
    assert still_catalogued.status is OperationStatus.CATALOGUED
    # Unknown pair returns None, never raises.
    assert find_operation(0x01, 0x99) is None


def test_open_close_operate_frames_are_confirmed_via_build_operate_frame() -> None:
    assert build_operate_frame(open=True, seq=1).hex() == "74010100b917"
    assert build_operate_frame(open=False, seq=1).hex() == "740001003912"


def test_generic_builder_matches_the_confirmed_subcmd_shape() -> None:
    # The confirmed frames start with the sub-command byte (no mainCmd on the
    # wire). Keepalive 2f012f == sub 0x2f + data 012f.
    assert build_control_frame(0x2F, bytes.fromhex("012f")).hex() == "2f012f"
    assert build_control_frame(0xE5).hex() == "e5"  # empty-data status get


def test_generic_builder_rejects_out_of_range_sub() -> None:
    with pytest.raises(ValueError):
        build_control_frame(0x100)


def test_catalog_covers_the_operate_and_keepalive_names() -> None:
    names = {e.name for e in OPERATIONS_CATALOG}
    assert {"BLE_OPEN_LOCK", "HEART_PCK", "GET_DOOR_LOCK_STATUS", "VOLUME"} <= names
