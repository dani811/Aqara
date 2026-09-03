# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# SPDX-FileCopyrightText: 2026 dani811 <https://github.com/dani811/Aqara>
#
# Aqara BLE. Source-available under the PolyForm Noncommercial License 1.0.0.
# Noncommercial use only; any commercial or for-profit use requires a separate
# written license from the copyright holder. See the LICENSE file for the terms.

"""U200Client facade flow (feature 015, US1).

Drives `U200Client` against a fake transport that hands back the scripted
`FakeLockClient` from `test_session_flow.py`, with the cloud calls and the
account login patched. No radio, no network.

What this proves: the phase order (login → scan → connect → operation), that
successive operations reuse the connection, the phase-labelled errors, the safe
`repr`, the context-manager cleanup, and — the fidelity guard — that the bytes
written through the facade are identical to those written by calling
`run_authenticated_lock_operation` directly.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from aqara_ble import (
    CloudAuthManager,
    FlowPhase,
    NoDeviceFoundError,
    OperationInProgressError,
    OperationResult,
    ScanCandidate,
    U200Client,
    U200ClientError,
    session,
)
from aqara_ble import auth as auth_module
from test_auto_login_flow import (
    FAKE_PASSWORD,
    FAKE_TOKEN,
    _make_auth,
    _patch_login,
    _patch_working_cloud,
)
from test_session_flow import (  # noqa: F401 - fixture import
    FAKE_SESSION_KEY_HEX,
    FakeLockClient,
    LockScript,
    _no_real_sleeping,
)

pytestmark = pytest.mark.usefixtures("_no_real_sleeping")

LOCK = ScanCandidate(
    address="CA:FE:00:00:00:01", name="DoorLocker", rssi=-50, reasons=frozenset({"name"}), score=4
)


class FakeTransport:
    """Records the order of transport calls and returns a scripted lock."""

    name = "fake"

    def __init__(
        self,
        candidates: list[ScanCandidate] | None = None,
        gatt: FakeLockClient | None = None,
        fail_connect: Exception | None = None,
    ) -> None:
        self.candidates = [LOCK] if candidates is None else candidates
        self.gatt = gatt or FakeLockClient(LockScript(optional_capabilities="present"))
        self.fail_connect = fail_connect
        self.calls: list[str] = []
        self.targets: list[Any] = []

    async def scan(self, timeout: float, *, mac: str | None = None) -> list[ScanCandidate]:
        self.calls.append("scan")
        return list(self.candidates)

    async def connect(self, target: Any, *, timeout: float) -> Any:
        self.calls.append("connect")
        self.targets.append(target)
        if self.fail_connect is not None:
            raise self.fail_connect
        return self.gatt

    async def disconnect(self) -> None:
        self.calls.append("disconnect")


@pytest.fixture
def cloud(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []
    _patch_login(monkeypatch, calls)
    _patch_working_cloud(monkeypatch)
    return calls


def _auth() -> CloudAuthManager:
    return _make_auth([])


async def _connect(transport: FakeTransport, **kw: Any) -> U200Client:
    return await U200Client.connect(auth=_auth(), transport=transport, device_id="dev-facade", **kw)


# ── flow ────────────────────────────────────────────────────────────────────


def test_connect_then_lock_runs_phases_in_order(cloud: list[str]) -> None:
    t = FakeTransport()

    async def go() -> str | None:
        client = await _connect(t)
        assert client.connected and client.candidate == LOCK
        return await client.lock()

    response = asyncio.run(go())
    assert cloud == ["login"]  # login happened first, once
    assert t.calls == ["scan", "connect"]  # then scan → connect
    assert t.gatt.control_writes, "the operation wrote to the control characteristic"
    assert response == t.gatt.script.control_response.hex()  # type: ignore[union-attr]


def test_successive_operations_reuse_connection(cloud: list[str]) -> None:
    t = FakeTransport()

    async def go() -> None:
        client = await _connect(t)
        await client.unlock()
        await client.lock()
        assert len(t.gatt.control_writes) == 2

    asyncio.run(go())
    assert t.calls == ["scan", "connect"] and cloud == ["login"]


def test_operate_by_name_returns_result(cloud: list[str]) -> None:
    t = FakeTransport()

    async def go() -> OperationResult:
        client = await _connect(t)
        return await client.operate("keepalive")

    result = asyncio.run(go())
    assert result.operation.name == "KEEPALIVE"
    assert result.session.session_key_hex == FAKE_SESSION_KEY_HEX


def test_mac_given_skips_scan(cloud: list[str]) -> None:
    t = FakeTransport()
    client = asyncio.run(_connect(t, mac="CA:FE:00:00:00:01"))
    assert t.calls == ["connect"] and t.targets == ["CA:FE:00:00:00:01"]
    assert client.candidate is None


def test_no_candidates_raises_scan_error(cloud: list[str]) -> None:
    t = FakeTransport(candidates=[])
    with pytest.raises(NoDeviceFoundError) as info:
        asyncio.run(_connect(t))
    assert info.value.phase is FlowPhase.SCAN and t.calls == ["scan"]


def test_connect_failure_is_labelled_and_transport_released(cloud: list[str]) -> None:
    boom = TimeoutError("radio said no")
    t = FakeTransport(fail_connect=boom)
    with pytest.raises(U200ClientError) as info:
        asyncio.run(_connect(t))
    assert info.value.phase is FlowPhase.CONNECT and info.value.__cause__ is boom
    assert t.calls == ["scan", "connect", "disconnect"]


def test_bad_login_fails_before_radio(monkeypatch: pytest.MonkeyPatch) -> None:
    def login_fails(*a: Any, **k: Any) -> dict[str, str]:
        raise RuntimeError("no network")

    monkeypatch.setattr(auth_module, "login", login_fails)
    t = FakeTransport()
    with pytest.raises(U200ClientError) as info:
        asyncio.run(_connect(t))
    assert info.value.phase is FlowPhase.LOGIN and t.calls == []


def test_operate_after_close_is_an_error(cloud: list[str]) -> None:
    t = FakeTransport()

    async def go() -> None:
        client = await _connect(t)
        await client.close()
        assert not client.connected
        with pytest.raises(U200ClientError) as info:
            await client.lock()
        assert info.value.phase is FlowPhase.OPERATION

    asyncio.run(go())
    assert t.calls == ["scan", "connect", "disconnect"]


def test_async_with_closes_transport(cloud: list[str]) -> None:
    t = FakeTransport()

    async def go() -> None:
        async with await _connect(t) as client:
            await client.lock()

    asyncio.run(go())
    assert t.calls[-1] == "disconnect"


def test_concurrent_operation_is_rejected(cloud: list[str]) -> None:
    t = FakeTransport()

    async def go() -> None:
        client = await _connect(t)
        # Simulate an operation in flight for this device id.
        session._device_operation_in_progress[client.device_id] = True
        try:
            with pytest.raises(OperationInProgressError):
                await client.lock()
        finally:
            session._device_operation_in_progress.pop(client.device_id, None)

    asyncio.run(go())


def test_repr_has_no_secrets(cloud: list[str]) -> None:
    t = FakeTransport()
    client = asyncio.run(_connect(t))
    text = repr(client)
    assert "dev-facade" in text and "fake" in text
    for secret in (FAKE_PASSWORD, FAKE_TOKEN, FAKE_SESSION_KEY_HEX):
        assert secret not in text


def test_from_gatt_wraps_existing_client(cloud: list[str]) -> None:
    gatt = FakeLockClient()
    client = U200Client.from_gatt(auth=_auth(), gatt_client=gatt, device_id="dev-facade")
    assert client.connected and "external" in repr(client)
    asyncio.run(client.lock())
    assert len(gatt.control_writes) == 1
    asyncio.run(client.close())  # no transport → nothing to release, no error


# ── fidelity guard: same bytes as the direct call ───────────────────────────


def test_facade_writes_same_bytes_as_direct_session_call(
    monkeypatch: pytest.MonkeyPatch, cloud: list[str]
) -> None:
    # Make the random app_token deterministic so both runs build identical frames.
    monkeypatch.setattr(session.os, "urandom", lambda n: b"\x11" * n)

    direct = FakeLockClient(LockScript(optional_capabilities="present"))
    asyncio.run(
        session.run_authenticated_lock_operation(
            client=direct,
            device_id="dev-direct",
            auth_headers=None,
            region="EU",
            base_url=None,
            operation="lock",
            notify_timeout=0.5,
            auth=_auth(),
        )
    )

    via = FakeLockClient(LockScript(optional_capabilities="present"))
    t = FakeTransport(gatt=via)
    asyncio.run(_run_lock(t))

    assert via.written_frames == direct.written_frames
    assert via.control_writes == direct.control_writes
    assert via.events == direct.events


async def _run_lock(t: FakeTransport) -> None:
    client = await _connect(t)
    await client.lock()
