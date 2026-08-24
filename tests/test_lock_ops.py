"""Pure-logic unit tests for lock operations (features 003 + 009).

Payloads are protocol opcodes recovered from decrypted captures (not secrets).
Dispatch is exercised through an in-memory fake transport — no BLE, no network.

The UNLOCK/LOCK payloads are the real captured actuation commands (feature 009):
`74010100b917` opened the physical lock from our own session, `740002003a12`
closes it. Both start with `0x74` (BLE_OPEN_LOCK); byte 1 is the direction.
"""

from __future__ import annotations

import pytest

from aqara_ble import (
    LockOperation,
    build_lock_operation_write,
    normalize_lock_operation,
    send_lock_operation,
)
from aqara_ble.lock_ops import build_operate_frame


class FakeTransport:
    """Captures the plaintext operation bytes handed to a session transport."""

    def __init__(self) -> None:
        self.sent: list[bytes] = []

    def send_plaintext_operation(self, payload: bytes) -> None:
        self.sent.append(payload)


def test_build_unlock_payload_and_prefix() -> None:
    write = build_lock_operation_write("unlock")
    assert write.operation is LockOperation.UNLOCK
    # Real captured open command: 0x74 = BLE_OPEN_LOCK, byte 1 = 0x01 (open).
    assert write.payload == bytes.fromhex("74010100b917")
    assert write.hex_payload == "74010100b917"
    assert write.write_prefix == 0x01


def test_unlock_and_lock_share_opcode_but_differ_in_direction() -> None:
    unlock = build_lock_operation_write("unlock")
    lock = build_lock_operation_write("lock")
    # Same 0x74 operate opcode; byte 1 is the direction (01 open / 00 close).
    assert unlock.payload[0] == 0x74 and lock.payload[0] == 0x74
    assert unlock.payload[1] == 0x01 and lock.payload[1] == 0x00
    assert lock.payload == bytes.fromhex("740001003912")
    assert lock.payload != unlock.payload


# Nine live-captured (dir, seq, frame) samples; the builder must reproduce them.
_OPERATE_SAMPLES = [
    (True, 1, "74010100b917"),
    (True, 2, "74010200ba17"),
    (True, 4, "74010400bc17"),
    (True, 6, "74010600be17"),
    (True, 7, "74010700bf17"),
    (False, 1, "740001003912"),
    (False, 2, "740002003a12"),
    (False, 3, "740003003b12"),
    (False, 5, "740005003d12"),
]


@pytest.mark.parametrize(("is_open", "seq", "frame"), _OPERATE_SAMPLES)
def test_build_operate_frame_reproduces_captures(is_open: bool, seq: int, frame: str) -> None:
    # The trailer is additive (base_dir + seq), not a CRC — pinned against real
    # captures so a regression to a wrong trailer is caught.
    assert build_operate_frame(open=is_open, seq=seq).hex() == frame


def test_build_operate_frame_defaults_to_seq_1_and_matches_enum() -> None:
    assert build_operate_frame(open=True).hex() == LockOperation.UNLOCK.value
    assert build_operate_frame(open=False).hex() == LockOperation.LOCK.value


def test_build_operate_frame_rejects_out_of_range_seq() -> None:
    with pytest.raises(ValueError):
        build_operate_frame(open=True, seq=0x10000)


def test_keepalive_uses_prefix_01() -> None:
    write = build_lock_operation_write("keepalive")
    assert write.operation is LockOperation.KEEPALIVE
    assert write.write_prefix == 0x01


@pytest.mark.parametrize("intent", ["unlock", "Desbloquear", "ABRIR", "open"])
def test_alias_and_case_insensitive(intent: str) -> None:
    assert normalize_lock_operation(intent) is LockOperation.UNLOCK


def test_legacy_values_are_not_dispatchable() -> None:
    # The old 1f031f/200320 were never the real actuators; they must not be
    # buildable into a write (no alias maps to them, and dispatch rejects them).
    with pytest.raises(ValueError):
        build_lock_operation_write(LockOperation.LEGACY_UNVERIFIED_1F031F)


def test_unknown_intent_raises() -> None:
    with pytest.raises(ValueError):
        normalize_lock_operation("teleport")


def test_send_dispatches_exact_payload() -> None:
    transport = FakeTransport()
    write = send_lock_operation(transport, "unlock")
    assert transport.sent == [bytes.fromhex("74010100b917")]
    assert write.operation is LockOperation.UNLOCK
