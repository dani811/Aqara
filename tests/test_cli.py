"""Packaged `aqara` CLI is a thin adapter over the public API (feature 017).

No radio, no network: the transport, scan and client are faked. These tests prove
the CLI only parses/dispatches/prints, that importing the library stays pure
(no cli, no argparse, no env read), and the exit-code contract.
"""

from __future__ import annotations

import subprocess
import sys
from typing import Any

import pytest


def test_import_library_is_pure() -> None:
    # Run in a fresh interpreter so nothing this test session already imported
    # pollutes the check: importing the package must not pull the CLI or argparse.
    code = (
        "import sys, aqara_u200_ble; "
        "assert 'aqara_u200_ble.cli' not in sys.modules, 'cli imported'; "
        "assert 'argparse' not in sys.modules, 'argparse imported'"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


def test_cli_module_has_no_protocol_logic() -> None:
    # The adapter must not import protocol/session/crypto modules directly.
    import aqara_u200_ble.cli as cli

    src = __import__("inspect").getsource(cli)
    for banned in ("import struct", "AES", "crc16", "_post_json", "session.run_authenticated"):
        assert banned not in src, f"CLI leaked protocol logic: {banned}"


class _FakeClient:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.candidate = None

    async def __aenter__(self) -> _FakeClient:
        return self

    async def __aexit__(self, *a: Any) -> None:
        self.calls.append("close")

    async def lock(self) -> str:
        self.calls.append("lock")
        return "740077"

    async def unlock(self) -> str:
        self.calls.append("unlock")
        return "74007706"

    async def operate(self, op: str) -> Any:
        self.calls.append(f"operate:{op}")
        from aqara_u200_ble.lock_ops import LockOperation, build_lock_operation_write

        class R:
            response_hex = "2f00"
            operation = LockOperation.KEEPALIVE
            write = build_lock_operation_write("keepalive")

        return R()


@pytest.fixture
def patched(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    import aqara_u200_ble.cli as cli

    state: dict[str, Any] = {"client": _FakeClient(), "connect_kwargs": None, "scanned": False}

    async def fake_connect(**kwargs: Any) -> _FakeClient:
        state["connect_kwargs"] = kwargs
        return state["client"]

    async def fake_scan(transport: Any, timeout: float, mac: str | None = None) -> list[Any]:
        state["scanned"] = True
        return []

    class FakeTransport:
        name = "fake"

        async def disconnect(self) -> None:
            state["client"].calls.append("transport.disconnect")

    monkeypatch.setattr(cli.U200Client, "connect", staticmethod(fake_connect))
    monkeypatch.setattr(cli, "scan", fake_scan)
    monkeypatch.setattr(cli, "_make_transport", lambda args: FakeTransport())
    monkeypatch.setattr(cli, "_auth_from", lambda args: object())
    monkeypatch.setattr(cli, "_device_id", lambda: "dev-cli")
    monkeypatch.setattr(cli, "_load_dotenv", lambda: None)
    return state


def test_lock_dispatches_to_client(patched: dict[str, Any]) -> None:
    from aqara_u200_ble.cli import main

    assert main(["lock"]) == 0
    assert "lock" in patched["client"].calls


def test_unlock_dispatches(patched: dict[str, Any]) -> None:
    from aqara_u200_ble.cli import main

    assert main(["unlock"]) == 0
    assert "unlock" in patched["client"].calls


def test_operate_passes_operation(patched: dict[str, Any]) -> None:
    from aqara_u200_ble.cli import main

    assert main(["operate", "keepalive"]) == 0
    assert "operate:keepalive" in patched["client"].calls


def test_scan_returns_not_found_exit_when_empty(patched: dict[str, Any]) -> None:
    from aqara_u200_ble.cli import main

    assert main(["scan"]) == 2  # EXIT_NOT_FOUND
    assert patched["scanned"]


def test_missing_credentials_is_config_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    import aqara_u200_ble.cli as cli

    monkeypatch.setattr(cli, "_load_dotenv", lambda: None)
    monkeypatch.delenv("AQARA_ACCOUNT", raising=False)
    monkeypatch.delenv("AQARA_APPID", raising=False)
    # No patch of _auth_from: exercise the real config check.
    assert cli.main(["--transport", "bleak", "lock"]) == 4  # EXIT_CONFIG


def test_client_error_maps_to_phase_exit(
    patched: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    import aqara_u200_ble.cli as cli
    from aqara_u200_ble import FlowPhase, U200ClientError

    async def boom(**kwargs: Any) -> Any:
        raise U200ClientError(FlowPhase.CONNECT, "no radio")

    monkeypatch.setattr(cli.U200Client, "connect", staticmethod(boom))
    assert cli.main(["lock"]) == 1  # EXIT_ERROR


def test_no_secrets_printed(patched: dict[str, Any], capsys: pytest.CaptureFixture[str]) -> None:
    from aqara_u200_ble.cli import main

    main(["--password", "sup3r-secret", "--account", "a@b.c", "lock"])
    out = capsys.readouterr().out
    assert "sup3r-secret" not in out
