"""Read-only status-query probe (feature 021).

The keepalive/operate/state_snapshot ACKs are static (verified live), so this
adds a generic control-query path to probe catalogued status opcodes. Proves the
query bytes, the write passthrough, and — the fidelity guard — that the actuator
path is byte-identical.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from aqara_ble import (
    build_control_query_write,
    session,
)
from aqara_ble.lock_ops import build_control_frame, build_lock_operation_write
from test_session_flow import (  # noqa: F401 - imported for fixtures
    FakeLockClient,
    LockScript,
    _fake_cloud,
    _no_real_sleeping,
)

pytestmark = pytest.mark.usefixtures("_no_real_sleeping")


def test_query_write_is_opcode_with_prefix() -> None:
    w = build_control_query_write(0x07)
    assert w.payload == b"\x07" and w.write_prefix == 0x01
    assert w.operation == "query:0x07"
    assert build_control_query_write(0xE5, b"\x01").payload == build_control_frame(0xE5, b"\x01")


def test_build_lock_operation_write_passes_through_a_prebuilt_write() -> None:
    w = build_control_query_write(0xE5)
    assert build_lock_operation_write(w) is w  # passthrough, not rebuilt


def test_actuator_bytes_unchanged_by_this_feature(_fake_cloud: list[str]) -> None:
    # LOCK still produces exactly its captured frame — no regression.
    w = build_lock_operation_write("lock")
    assert w.payload == bytes.fromhex("740001003912") and w.write_prefix == 0x01
    u = build_lock_operation_write("unlock")
    assert u.payload == bytes.fromhex("74010100b917")


def _run_query(client: FakeLockClient, sub_cmd: int) -> Any:
    write = build_control_query_write(sub_cmd)
    return asyncio.run(
        session.run_authenticated_lock_operation(
            client=client,
            device_id="q",
            auth_headers=None,
            region="EU",
            base_url=None,
            operation=write,
            notify_timeout=0.5,
            signer=None,
        )
    )


def test_query_sends_the_opcode_frame_and_returns_response(_fake_cloud: list[str]) -> None:
    client = FakeLockClient(LockScript())
    _material, write, response = _run_query(client, 0x07)
    # The plaintext that was encrypted and written is the query frame.
    assert write.payload == b"\x07"
    assert client.control_writes, "a control frame was written"
    assert response is not None  # the fake answered
