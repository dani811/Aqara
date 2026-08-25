"""The read-opcode registry must never expose a mutating/actuating command."""

from __future__ import annotations

from aqara_ble.operations_catalog import system_read_opcodes


def test_registry_is_non_empty_and_lowercase() -> None:
    reads = system_read_opcodes()
    assert len(reads) > 20
    assert all(name == name.lower() for name in reads)
    assert all(0 <= op <= 0xFF for op in reads.values())


def test_no_mutating_opcode_leaks_in() -> None:
    reads = system_read_opcodes()
    # None of these actuators/mutators may be reachable through the read map.
    for banned in ("set_", "del_", "add_", "modify_", "un_lock", "open_lock",
                   "report", "config_", "enable", "apdu", "ota"):
        assert not any(banned in name for name in reads), banned
    # The confirmed actuator opcodes are absent by value, too.
    assert 0x74 not in reads.values()  # BLE_OPEN_LOCK
    assert 0x18 not in reads.values()  # UN_LOCK


def test_known_reads_are_present() -> None:
    reads = system_read_opcodes()
    assert reads.get("lock_status") == 0x07
    assert reads.get("get_battery_info") == 0xDE
    assert reads.get("get_lock_volume") == 0xC3
