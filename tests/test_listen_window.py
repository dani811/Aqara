"""Post-command listen window forwards spontaneous frames (feature 023)."""

from __future__ import annotations

import asyncio
from typing import Any

from aqara_u200_ble import session
from test_session_flow import (  # noqa: F401 - fixtures
    FakeLockClient,
    LockScript,
    _fake_cloud,
    _no_real_sleeping,
)


def _run(client: FakeLockClient, listen_after: float, on_report: Any) -> Any:
    return asyncio.run(
        session.run_authenticated_lock_operation(
            client=client,
            device_id="listen",
            auth_headers=None,
            region="EU",
            base_url=None,
            operation="keepalive",
            notify_timeout=0.5,
            signer=None,
            listen_after=listen_after,
            on_report=on_report,
        )
    )


def test_report_channel_frames_are_forwarded(_fake_cloud: list[str]) -> None:
    script = LockScript(extra_reports=(("ff64", b"\xaa\xbb"), ("ff92", b"\x01\x02\x03")))
    client = FakeLockClient(script)
    seen: list[tuple[str, str]] = []
    _run(client, listen_after=0.05, on_report=lambda ch, d: seen.append((ch, d.hex())))
    assert ("ff64", "aabb") in seen
    assert ("ff92", "010203") in seen


def test_listen_after_zero_forwards_nothing(_fake_cloud: list[str]) -> None:
    # Default behaviour: no listen window, nothing forwarded even if pushed.
    script = LockScript(extra_reports=(("ff64", b"\xaa\xbb"),))
    client = FakeLockClient(script)
    seen: list[Any] = []
    _run(client, listen_after=0.0, on_report=lambda ch, d: seen.append((ch, d)))
    assert seen == []


def test_no_on_report_is_safe(_fake_cloud: list[str]) -> None:
    # listen_after set but no callback: must not raise, just skip forwarding.
    client = FakeLockClient(LockScript(extra_reports=(("ff64", b"\xaa"),)))
    _material, _write, response = _run(client, listen_after=0.02, on_report=None)
    assert response is not None
