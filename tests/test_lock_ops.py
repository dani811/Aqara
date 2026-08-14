"""Pure-logic unit tests for lock operations (feature 003).

Payloads are protocol opcodes recovered from decrypted captures (not secrets).
Dispatch is exercised through an in-memory fake transport — no BLE, no network.
"""

from __future__ import annotations

import pytest

from aqara_u200_ble import (
    LockOperation,
    build_lock_operation_write,
    normalize_lock_operation,
    send_lock_operation,
)


class FakeTransport:
    """Captures the plaintext operation bytes handed to a session transport."""

    def __init__(self) -> None:
        self.sent: list[bytes] = []

    def send_plaintext_operation(self, payload: bytes) -> None:
        self.sent.append(payload)


def test_build_unlock_payload_and_prefix() -> None:
    write = build_lock_operation_write("unlock")
    assert write.operation is LockOperation.UNLOCK
    assert write.payload == bytes.fromhex("200320")
    assert write.hex_payload == "200320"
    assert write.write_prefix == 0x03


def test_lock_is_distinct_from_unlock() -> None:
    lock = build_lock_operation_write("lock")
    unlock = build_lock_operation_write("unlock")
    assert lock.payload == bytes.fromhex("1f031f")
    assert lock.payload != unlock.payload


def test_keepalive_uses_prefix_01() -> None:
    write = build_lock_operation_write("keepalive")
    assert write.operation is LockOperation.KEEPALIVE
    assert write.write_prefix == 0x01


@pytest.mark.parametrize("intent", ["unlock", "Desbloquear", "ABRIR", "unlock"])
def test_alias_and_case_insensitive(intent: str) -> None:
    assert normalize_lock_operation(intent) is LockOperation.UNLOCK


def test_unknown_intent_raises() -> None:
    with pytest.raises(ValueError):
        normalize_lock_operation("teleport")


def test_send_dispatches_exact_payload() -> None:
    transport = FakeTransport()
    write = send_lock_operation(transport, "unlock")
    assert transport.sent == [bytes.fromhex("200320")]
    assert write.operation is LockOperation.UNLOCK
