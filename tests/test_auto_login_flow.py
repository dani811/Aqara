# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# SPDX-FileCopyrightText: 2026 dani811 <https://github.com/dani811/Aqara>
#
# Aqara BLE. Source-available under the PolyForm Noncommercial License 1.0.0.
# Noncommercial use only; any commercial or for-profit use requires a separate
# written license from the copyright holder. See the LICENSE file for the terms.

"""Tests for the autonomous login flow (feature 014).

Verifies that the operation flow can authenticate from injected credentials
(a CloudAuthManager), refresh the token on a 108 and re-run the whole operation
once, fail cleanly on 810 without looping, keep the legacy signer path working,
never retry after actuation, run login off the event loop, and never log secrets.
All cloud/BLE I/O is simulated — no network, no radio.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from pathlib import Path
from typing import Any

import pytest

from aqara_ble import CloudAuthManager, CloudServiceError, session
from aqara_ble import auth as auth_module
from aqara_ble.kdf import _unwrap_aqara_result
from test_session_flow import FakeLockClient, LockScript

FAKE_PUBKEY_HEX = (bytes([0x04]) + bytes(range(65, 129))).hex()
FAKE_SESSION = {
    "sessionKey": "000102030405060708090a0b0c0d0e0f",
    "nonce": "0102030405060708090a0b0c0d",
    "verifyData": "aabbccddeeff00112233445566778899",
}
FAKE_TOKEN = "faketoken.header.payload"
FAKE_PASSWORD = "sup3r-s3cr3t-pw"


def _make_auth(login_calls: list[str]) -> CloudAuthManager:
    return CloudAuthManager(
        account="user@example.invalid",
        password=FAKE_PASSWORD,
        appid="appid",
        appkey="appkey",
        client_id="cid",
        phone_id="pid",
        region="EU",
    )


def _patch_working_cloud(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(session, "cloud_get_public_key", lambda **k: FAKE_PUBKEY_HEX)
    monkeypatch.setattr(session, "get_session_material", lambda **k: dict(FAKE_SESSION))


def _patch_login(monkeypatch: pytest.MonkeyPatch, calls: list[str]) -> None:
    def fake_login(account: str, password: str, **kwargs: Any) -> dict[str, str]:
        calls.append("login")
        return {"token": FAKE_TOKEN, "userId": "u1"}

    monkeypatch.setattr(auth_module, "login", fake_login)


# ── T003: typed service error ───────────────────────────────────────────────


class TestCloudServiceError:
    def test_raises_typed_error_with_code(self) -> None:
        for code in (108, "108", 810):
            with pytest.raises(CloudServiceError) as ei:
                _unwrap_aqara_result({"code": code, "message": "x"}, endpoint="/e")
            assert ei.value.is_code(int(code)) if str(code).isdigit() else True
        # subclass of RuntimeError (backward compatible)
        try:
            _unwrap_aqara_result({"code": 108}, endpoint="/e")
        except RuntimeError as exc:
            assert isinstance(exc, CloudServiceError)

    def test_zero_code_is_not_an_error(self) -> None:
        assert _unwrap_aqara_result({"code": 0, "result": {"ok": 1}}, endpoint="/e") == {"ok": 1}


# ── US1: operate from credentials only ──────────────────────────────────────


class TestOperateFromCredentials:
    def test_only_auth_logs_in_and_completes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[str] = []
        _patch_working_cloud(monkeypatch)
        _patch_login(monkeypatch, calls)
        auth = _make_auth(calls)
        client = FakeLockClient(LockScript())

        material, _write, _ = asyncio.run(
            session.run_authenticated_lock_operation(
                client=client,
                device_id="d",
                auth_headers=None,
                region="EU",
                base_url=None,
                operation="unlock",
                notify_timeout=0.5,
                auth=auth,
            )
        )
        assert material.session_key_hex == FAKE_SESSION["sessionKey"]
        assert len(client.control_writes) == 1
        assert calls == ["login"]  # logged in once, no token was provided

    def test_cached_token_reused_across_operations(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[str] = []
        _patch_working_cloud(monkeypatch)
        _patch_login(monkeypatch, calls)
        auth = _make_auth(calls)

        for _ in range(2):
            asyncio.run(
                session.run_authenticated_lock_operation(
                    client=FakeLockClient(LockScript()),
                    device_id="d",
                    auth_headers=None,
                    region="EU",
                    base_url=None,
                    operation="keepalive",
                    notify_timeout=0.5,
                    auth=auth,
                )
            )
        assert calls == ["login"]  # second operation reused the cached token

    def test_both_auth_and_signer_is_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[str] = []
        auth = _make_auth(calls)
        with pytest.raises(ValueError):
            asyncio.run(
                session.run_authenticated_lock_operation(
                    client=FakeLockClient(LockScript()),
                    device_id="d",
                    auth_headers=None,
                    region="EU",
                    base_url=None,
                    operation="unlock",
                    signer=object(),
                    auth=auth,
                )
            )
        assert calls == []  # failed before any login / I/O

    def test_explicit_signer_path_still_works(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # SC-005 / FR-010: the legacy signer path completes with no auth.
        _patch_working_cloud(monkeypatch)
        material, _write, _ = asyncio.run(
            session.run_authenticated_lock_operation(
                client=FakeLockClient(LockScript()),
                device_id="d",
                auth_headers=None,
                region="EU",
                base_url=None,
                operation="unlock",
                notify_timeout=0.5,
                signer=lambda path, body: {"X": "1"},
            )
        )
        assert material.session_key_hex == FAKE_SESSION["sessionKey"]


# ── US2: transparent refresh on 108 ─────────────────────────────────────────


class TestRefreshOn108:
    def test_108_then_success_reauths_and_reruns_once(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[str] = []
        _patch_login(monkeypatch, calls)
        monkeypatch.setattr(session, "cloud_get_public_key", lambda **k: FAKE_PUBKEY_HEX)

        state = {"n": 0}

        def flaky_session(**k: Any) -> dict[str, str]:
            state["n"] += 1
            if state["n"] == 1:
                raise CloudServiceError(code=108, message="Token has expired", endpoint="/verify")
            return dict(FAKE_SESSION)

        monkeypatch.setattr(session, "get_session_material", flaky_session)
        auth = _make_auth(calls)
        client = FakeLockClient(LockScript())

        material, _, _ = asyncio.run(
            session.run_authenticated_lock_operation(
                client=client,
                device_id="d",
                auth_headers=None,
                region="EU",
                base_url=None,
                operation="unlock",
                notify_timeout=0.5,
                auth=auth,
            )
        )
        assert material.session_key_hex == FAKE_SESSION["sessionKey"]
        assert calls == ["login", "login"]  # initial + one refresh
        assert len(client.control_writes) == 1  # actuated exactly once

    def test_reauth_then_still_failing_gives_up_no_loop(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[str] = []
        _patch_login(monkeypatch, calls)
        monkeypatch.setattr(session, "cloud_get_public_key", lambda **k: FAKE_PUBKEY_HEX)

        def always_108(**k: Any) -> dict[str, str]:
            raise CloudServiceError(code=108, message="Token has expired", endpoint="/verify")

        monkeypatch.setattr(session, "get_session_material", always_108)
        auth = _make_auth(calls)

        with pytest.raises(CloudServiceError) as ei:
            asyncio.run(
                session.run_authenticated_lock_operation(
                    client=FakeLockClient(LockScript()),
                    device_id="d",
                    auth_headers=None,
                    region="EU",
                    base_url=None,
                    operation="unlock",
                    notify_timeout=0.5,
                    auth=auth,
                )
            )
        assert ei.value.is_code(108)
        assert calls == ["login", "login"]  # exactly one refresh, then give up (no loop)

    def test_108_after_actuation_is_not_retried(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # SC-008 idempotency: a 108 raised AFTER the control write must not retry.
        calls: list[str] = []
        _patch_login(monkeypatch, calls)
        _patch_working_cloud(monkeypatch)

        def boom_after_write(*a: Any, **k: Any) -> bytes:
            raise CloudServiceError(code=108, message="late", endpoint="/post")

        monkeypatch.setattr(session, "decrypt_control_payload", boom_after_write)
        auth = _make_auth(calls)
        client = FakeLockClient(LockScript())

        with pytest.raises(CloudServiceError):
            asyncio.run(
                session.run_authenticated_lock_operation(
                    client=client,
                    device_id="d",
                    auth_headers=None,
                    region="EU",
                    base_url=None,
                    operation="unlock",
                    notify_timeout=0.5,
                    auth=auth,
                )
            )
        assert len(client.control_writes) == 1  # no double actuation
        assert calls == ["login"]  # no refresh after actuation

    def test_login_runs_off_the_event_loop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # FR-011: login (network I/O) executes in a worker thread, not the loop.
        _patch_working_cloud(monkeypatch)
        main_thread = threading.get_ident()
        seen: dict[str, int] = {}

        def fake_login(account: str, password: str, **kwargs: Any) -> dict[str, str]:
            seen["thread"] = threading.get_ident()
            return {"token": FAKE_TOKEN, "userId": "u1"}

        monkeypatch.setattr(auth_module, "login", fake_login)
        auth = _make_auth([])
        asyncio.run(
            session.run_authenticated_lock_operation(
                client=FakeLockClient(LockScript()),
                device_id="d",
                auth_headers=None,
                region="EU",
                base_url=None,
                operation="keepalive",
                notify_timeout=0.5,
                auth=auth,
            )
        )
        assert seen["thread"] != main_thread


# ── US3: 810 fails clearly, no loop ─────────────────────────────────────────


class TestBadCredentials810:
    def test_810_fails_without_login_retry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[str] = []

        def login_810(account: str, password: str, **kwargs: Any) -> dict[str, str]:
            calls.append("login")
            raise CloudServiceError(code=810, message="Password incorrect", endpoint="/login")

        monkeypatch.setattr(auth_module, "login", login_810)
        _patch_working_cloud(monkeypatch)
        auth = _make_auth(calls)

        with pytest.raises(RuntimeError) as ei:
            asyncio.run(
                session.run_authenticated_lock_operation(
                    client=FakeLockClient(LockScript()),
                    device_id="d",
                    auth_headers=None,
                    region="EU",
                    base_url=None,
                    operation="unlock",
                    notify_timeout=0.5,
                    auth=auth,
                )
            )
        assert "810" in str(ei.value)
        assert calls == ["login"]  # attempted once, not retried
        assert not ei.value.is_code(810) if isinstance(ei.value, CloudServiceError) else True


# ── US4: no secrets in logs; package purity ─────────────────────────────────


class TestNoSecretsInLogs:
    def _assert_clean(self, text: str) -> None:
        for secret in (
            FAKE_TOKEN,
            FAKE_PASSWORD,
            FAKE_SESSION["sessionKey"],
            FAKE_SESSION["nonce"],
            FAKE_SESSION["verifyData"],
            "user@example.invalid",
        ):
            assert secret not in text, f"secret leaked to logs: {secret!r}"

    def test_no_secrets_on_success(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.DEBUG)
        _patch_working_cloud(monkeypatch)
        _patch_login(monkeypatch, [])
        auth = _make_auth([])
        asyncio.run(
            session.run_authenticated_lock_operation(
                client=FakeLockClient(LockScript()),
                device_id="d",
                auth_headers=None,
                region="EU",
                base_url=None,
                operation="unlock",
                notify_timeout=0.5,
                auth=auth,
            )
        )
        self._assert_clean(caplog.text)

    def test_no_secrets_on_810_failure(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.DEBUG)

        def login_810(account: str, password: str, **kwargs: Any) -> dict[str, str]:
            raise CloudServiceError(code=810, message="Password incorrect", endpoint="/login")

        monkeypatch.setattr(auth_module, "login", login_810)
        _patch_working_cloud(monkeypatch)
        auth = _make_auth([])
        with pytest.raises(RuntimeError):
            asyncio.run(
                session.run_authenticated_lock_operation(
                    client=FakeLockClient(LockScript()),
                    device_id="d",
                    auth_headers=None,
                    region="EU",
                    base_url=None,
                    operation="unlock",
                    notify_timeout=0.5,
                    auth=auth,
                )
            )
        self._assert_clean(caplog.text)


class TestPackagePurity:
    def test_package_has_no_utilities_or_interactivity(self) -> None:
        # The importable library must not load credentials, prompt, or read the
        # environment. `cli.py` is the ONE sanctioned adapter (feature 017): it
        # may have a `__main__` entry point, but must still never prompt — and it
        # is NOT imported by the package __init__ (see test_import_library_is_pure
        # in test_cli.py), so `import aqara_ble` stays pure.
        pkg = Path(session.__file__).parent
        offenders: list[str] = []
        for py in pkg.glob("*.py"):
            src = py.read_text(encoding="utf-8")
            patterns = ["getpass", "input(", "def from_env"]
            if py.name != "cli.py":
                patterns.append('if __name__ == "__main__"')
            for pattern in patterns:
                if pattern in src:
                    offenders.append(f"{py.name}: {pattern}")
        assert offenders == [], f"non-library code in package: {offenders}"
