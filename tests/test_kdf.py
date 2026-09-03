# SPDX-License-Identifier: AGPL-3.0-only
# SPDX-FileCopyrightText: 2026 dani811 <https://github.com/dani811/Aqara>
#
# This file is part of Aqara BLE, licensed under the GNU Affero General Public
# License v3.0 (AGPL-3.0-only). You may use, study, share and modify it; any
# distributed or network-served derivative must stay licensed under the AGPL
# and keep this notice. See the LICENSE file for the full terms.

"""Pure-logic unit tests for the cloud KDF client (feature 001).

These tests pin the *observable behaviour* of the reverse-engineered crypto so
any accidental drift is caught (Constitution Principle II). They never touch the
network (Principle V) and contain no real secrets (Principle I) — every value
here is a throwaway fixture.
"""

from __future__ import annotations

import base64
import hashlib
import ssl
from typing import Any
from urllib import error as urlerror

import pytest
from cryptography.hazmat.primitives.asymmetric import padding as _pad
from cryptography.hazmat.primitives.asymmetric import rsa as _rsa
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from aqara_ble import (
    aes128gcm_decrypt_body,
    aes128gcm_encrypt_body,
    cloud_crypto,
    compute_nonce,
    compute_sign,
    encrypt_login_password,
    hkdf_sha256,
    kdf,
)

# The TLS opt-out flag under test (feature 006). Kept as a literal here so the
# test pins the documented name, not whatever the module happens to call it.
INSECURE_TLS_ENV = "U200_INSECURE_TLS"

# A throwaway 32-char appkey-shaped fixture. NOT a real key.
FAKE_APPKEY = "0123456789abcdef0123456789abcdef"


def test_compute_nonce_is_uppercase_md5_of_request_id() -> None:
    request_id = "b1d2c3-req-0001"
    expected = hashlib.md5(request_id.encode("utf-8")).hexdigest().upper()
    assert compute_nonce(request_id) == expected
    # Uppercase invariant: no lowercase hex digits leak through.
    assert compute_nonce(request_id) == compute_nonce(request_id).upper()


def test_compute_sign_matches_documented_formula_with_token() -> None:
    # Sign = MD5("Appid=..&Nonce=..&Time=..&Token=..&{body}&{appkey}")
    appid, nonce, time_, token, body = (
        "app-id",
        "ABCDEF0123456789",
        "1700000000000",
        "tok-123",
        '{"deviceId":"dev-1"}',
    )
    preimage = f"Appid={appid}&Nonce={nonce}&Time={time_}&Token={token}&{body}&{FAKE_APPKEY}"
    expected = hashlib.md5(preimage.encode("utf-8")).hexdigest()
    got = compute_sign(
        appid=appid, nonce=nonce, time=time_, token=token, body=body, appkey=FAKE_APPKEY
    )
    assert got == expected


def test_compute_sign_omits_token_field_when_empty() -> None:
    # On login there is no token: the whole `Token=` segment is dropped.
    appid, nonce, time_, body = ("app-id", "ABCDEF0123456789", "1700000000000", "{}")
    preimage_no_token = f"Appid={appid}&Nonce={nonce}&Time={time_}&{body}&{FAKE_APPKEY}"
    expected = hashlib.md5(preimage_no_token.encode("utf-8")).hexdigest()
    got = compute_sign(
        appid=appid, nonce=nonce, time=time_, token="", body=body, appkey=FAKE_APPKEY
    )
    assert got == expected
    # And it must differ from the token-present variant.
    with_token = compute_sign(
        appid=appid, nonce=nonce, time=time_, token="x", body=body, appkey=FAKE_APPKEY
    )
    assert got != with_token


def test_hkdf_sha256_rfc5869_test_case_1() -> None:
    # RFC 5869, Appendix A.1
    ikm = bytes.fromhex("0b" * 22)
    salt = bytes.fromhex("000102030405060708090a0b0c")
    info = bytes.fromhex("f0f1f2f3f4f5f6f7f8f9")
    expected_okm = bytes.fromhex(
        "3cb25f25faacd57a90434f64d0362f2a2d2d0a90cf1a5a4c5db02d56ecc4c5bf34007208d5b887185865"
    )
    assert hkdf_sha256(ikm, salt=salt, info=info, length=42) == expected_okm


def test_aes128gcm_body_roundtrip() -> None:
    plaintext = b'{"account":"user","password":"redacted"}'
    blob = aes128gcm_encrypt_body(plaintext, FAKE_APPKEY)
    # Wire shape: three base64 segments joined by '-'.
    assert blob.count("-") == 2
    assert aes128gcm_decrypt_body(blob, FAKE_APPKEY) == plaintext


def test_aes128gcm_decrypt_rejects_malformed_blob() -> None:
    with pytest.raises(ValueError):
        aes128gcm_decrypt_body("only-two", FAKE_APPKEY)


def test_encrypt_login_password_has_rsa1024_shape() -> None:
    # RSA-1024 PKCS#1 v1.5 ciphertext is exactly 128 bytes, base64-encoded.
    out = encrypt_login_password("hunter2")
    raw = base64.b64decode(out)
    assert len(raw) == 128
    # Non-deterministic padding: two encryptions differ.
    assert encrypt_login_password("hunter2") != out


def test_encrypt_login_password_rsa_plaintext_is_md5_hex_lowercase() -> None:
    # The RSA plaintext is MD5(password) in lowercase hex (32 ASCII chars), NOT
    # the raw password — the shape confirmed by the app capture (see
    # docs/protocol/cloud-api.md). A raw-password regression here brings back the
    # permanent code=810. Uses a throwaway, non-credential password so no real
    # secret enters the repo (Constitution Principle I).
    #
    # We cannot decrypt (no private key), so we prove the transform by decrypting
    # our own ciphertext with a throwaway RSA key that mirrors the login shape.
    throwaway_password = "not-a-real-password-000"
    key = _rsa.generate_private_key(public_exponent=65537, key_size=1024)
    der = key.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
    monkey_b64 = base64.b64encode(der).decode("ascii")

    saved = cloud_crypto._LOGIN_RSA_PUBKEY_DER_B64
    try:
        cloud_crypto._LOGIN_RSA_PUBKEY_DER_B64 = monkey_b64
        blob = cloud_crypto.encrypt_login_password(throwaway_password)
    finally:
        cloud_crypto._LOGIN_RSA_PUBKEY_DER_B64 = saved

    plaintext = key.decrypt(base64.b64decode(blob), _pad.PKCS1v15())
    expected = hashlib.md5(throwaway_password.encode("utf-8")).hexdigest()
    # The plaintext is the 32-char lowercase-hex MD5, not the raw password bytes.
    assert plaintext == expected.encode("ascii")
    assert len(plaintext) == 32
    assert plaintext != throwaway_password.encode("utf-8")


# ---------------------------------------------------------------------------
# Service-level error codes (feature 001, FR-008)
#
# The cloud answers HTTP 200 with a non-zero `code` for auth, signature, and
# ownership failures. Those must reach the caller distinguishably from a
# transport failure — otherwise "expired token" looks like "network down".
# ---------------------------------------------------------------------------


def test_service_error_code_is_surfaced_with_its_details() -> None:
    payload = {
        "code": 108,
        "message": "token expired",
        "msgDetails": "re-login required",
        "result": None,
    }
    with pytest.raises(RuntimeError) as excinfo:
        kdf._unwrap_aqara_result(payload, endpoint="/dev/bluetooth/login/assure/verify")

    message = str(excinfo.value)
    assert "108" in message
    assert "token expired" in message
    assert "/dev/bluetooth/login/assure/verify" in message
    # Distinguishable from the transport-failure wording (FR-008).
    assert "failed to contact" not in message


@pytest.mark.parametrize("code", [0, "0", None])
def test_success_codes_unwrap_the_result(code: object) -> None:
    payload = {"code": code, "result": {"sessionKey": "fake"}}
    assert kdf._unwrap_aqara_result(payload, endpoint="/x") == {"sessionKey": "fake"}


def test_payload_without_result_is_returned_whole() -> None:
    # Some endpoints answer flat, with no `result` envelope.
    payload = {"code": 0, "macAddress": "fake", "ltmk": "fake"}
    assert kdf._unwrap_aqara_result(payload, endpoint="/x") == payload


def test_missing_code_field_is_not_an_error() -> None:
    # Absence of `code` means the endpoint does not use the envelope at all.
    payload = {"result": {"cloudPublicKey": "fake"}}
    assert kdf._unwrap_aqara_result(payload, endpoint="/x") == {"cloudPublicKey": "fake"}


# ---------------------------------------------------------------------------
# TLS policy for cloud requests (feature 006)
#
# These assert the *policy*, never a connection: no socket is opened anywhere
# below (Principle V). The material these requests carry opens a physical door,
# so the default must verify the server's identity.
# ---------------------------------------------------------------------------


def _fake_signer(path_rel: str | None, body: str) -> dict[str, str]:
    """Stand-in for the runtime signer: returns already-signed fake headers."""

    return {"Appid": "fake-appid", "Sign": "fake-sign", "Time": "0"}


def test_tls_context_verifies_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(INSECURE_TLS_ENV, raising=False)
    context = kdf._tls_context()
    assert context.check_hostname is True
    assert context.verify_mode is ssl.CERT_REQUIRED


def test_tls_context_emits_no_warning_by_default(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(INSECURE_TLS_ENV, raising=False)
    kdf._tls_context()
    assert capsys.readouterr().err == ""


def test_tls_context_opt_out_disables_verification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(INSECURE_TLS_ENV, "1")
    context = kdf._tls_context()
    assert context.check_hostname is False
    assert context.verify_mode is ssl.CERT_NONE


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "  yes  ", "on", "On"])
def test_tls_context_opt_out_accepts_documented_values(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv(INSECURE_TLS_ENV, value)
    assert kdf._tls_context().verify_mode is ssl.CERT_NONE


@pytest.mark.parametrize("value", ["", "0", "false", "no", "off", "maybe", "  "])
def test_tls_context_falsey_values_stay_secure(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    # Fail-safe parsing: anything not explicitly affirmative — including a typo —
    # keeps verification on. The inverse would turn a slip into a silent hole.
    monkeypatch.setenv(INSECURE_TLS_ENV, value)
    context = kdf._tls_context()
    assert context.check_hostname is True
    assert context.verify_mode is ssl.CERT_REQUIRED


def test_tls_context_opt_out_warns(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv(INSECURE_TLS_ENV, "1")
    kdf._tls_context()
    err = capsys.readouterr().err
    assert INSECURE_TLS_ENV in err
    assert "verification" in err.lower()


def test_certificate_failure_message_names_the_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # urlopen surfaces a certificate failure as URLError(reason=SSLCertVerificationError).
    # The user must learn what failed and what their deliberate override is.
    def _raise_cert_error(*args: Any, **kwargs: Any) -> None:
        raise urlerror.URLError(
            ssl.SSLCertVerificationError("certificate verify failed: self-signed")
        )

    monkeypatch.delenv(INSECURE_TLS_ENV, raising=False)
    monkeypatch.setattr(kdf.urlrequest, "urlopen", _raise_cert_error)

    with pytest.raises(RuntimeError) as excinfo:
        kdf._post_json(
            "https://example.invalid/dev/bluetooth/login/assure/verify",
            {"deviceId": "fake"},
            signer=_fake_signer,
        )

    message = str(excinfo.value)
    assert "example.invalid" in message
    assert "certificate" in message.lower()
    assert INSECURE_TLS_ENV in message


def test_non_certificate_url_errors_are_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A plain connection failure must keep its original wording: the new advice
    # only applies to verification failures.
    def _raise_url_error(*args: Any, **kwargs: Any) -> None:
        raise urlerror.URLError("Connection refused")

    monkeypatch.setattr(kdf.urlrequest, "urlopen", _raise_url_error)

    with pytest.raises(RuntimeError) as excinfo:
        kdf._post_json(
            "https://example.invalid/dev/bluetooth/login/assure/verify",
            {"deviceId": "fake"},
            signer=_fake_signer,
        )

    message = str(excinfo.value)
    assert "failed to contact" in message
    assert INSECURE_TLS_ENV not in message


# ---------------------------------------------------------------------------
# Account login (feature 001, User Story 2)
#
# STATUS — READ BEFORE TRUSTING THIS PATH: the request built below has never
# produced a token. Against the real EU server it answers `code=810,
# "Error de contraseña o cuenta no registrada"` for every input tried,
# including credentials the official app accepts. A deliberately nonexistent
# account returns that *same* 810, so the code discriminates nothing and the
# old "810 instead of 500 proves the envelope is correct" reasoning does not
# hold. Acceptance Scenario 1 of the spec (correct credentials -> usable
# token) is UNPROVEN.
#
# These tests therefore pin what the client SENDS — they cannot pin what the
# server accepts. Their job is to make any fix to the request shape visible.
# ---------------------------------------------------------------------------

LOGIN_KWARGS = {
    "appid": "fake-appid",
    "appkey": FAKE_APPKEY,
    "client_id": "fake-client",
    "phone_id": "fake-phone",
}


def _capture_login(
    monkeypatch: pytest.MonkeyPatch, response: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Replace the transport and record exactly what login() would have sent."""

    seen: dict[str, Any] = {}

    def _fake_post(
        url: str,
        payload: Any,
        auth_headers: Any = None,
        timeout: float = 10,
        signer: Any = None,
        path_rel: str | None = None,
        encrypt_appkey: str | None = None,
    ) -> dict[str, Any]:
        seen["url"] = url
        seen["body"] = payload
        seen["encrypt_appkey"] = encrypt_appkey
        # The signer is what decides whether this is an authenticated request.
        seen["headers"] = signer(path_rel, "{}") if signer is not None else {}
        return response if response is not None else {"code": 0, "result": {"token": "a.b.c"}}

    monkeypatch.setattr(kdf, "_post_json", _fake_post)
    return seen


def test_login_posts_the_documented_body(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _capture_login(monkeypatch)
    kdf.login("user@example.invalid", "hunter2", **LOGIN_KWARGS)

    body = seen["body"]
    assert body["account"] == "user@example.invalid"
    assert body["encryptType"] == 2
    assert body["guardCode"] == ""
    # The password never travels in clear: it is RSA-1024 ciphertext, and the
    # plaintext must not appear anywhere in the body.
    assert len(base64.b64decode(body["password"])) == 128
    assert "hunter2" not in str(body)


def test_login_targets_the_region_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _capture_login(monkeypatch)
    kdf.login("u", "p", region="EU", **LOGIN_KWARGS)
    assert seen["url"] == kdf.REGION_BASE_URLS["EU"] + "/user/guard-code/login"


def test_login_body_travels_encrypted(monkeypatch: pytest.MonkeyPatch) -> None:
    # Content-Encoding: x-aes128gcm — the appkey must reach the transport.
    seen = _capture_login(monkeypatch)
    kdf.login("u", "p", **LOGIN_KWARGS)
    assert seen["encrypt_appkey"] == FAKE_APPKEY


def test_login_is_unauthenticated_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    # No previous token needed: no session headers, and compute_sign drops the
    # whole `Token=` field (pinned by test_compute_sign_omits_token_field_when_empty).
    seen = _capture_login(monkeypatch)
    kdf.login("u", "p", **LOGIN_KWARGS)

    headers = seen["headers"]
    assert "Token" not in headers
    assert "UserId" not in headers
    assert "Requestid" not in headers
    assert headers["Sign"]


def test_login_signs_with_a_stored_token_when_asked(monkeypatch: pytest.MonkeyPatch) -> None:
    # The --sign-with-stored fallback: identity headers come back.
    seen = _capture_login(monkeypatch)
    kdf.login("u", "p", sign_token="tok-123", user_id="uid-9", **LOGIN_KWARGS)

    headers = seen["headers"]
    assert headers["Token"] == "tok-123"
    assert headers["UserId"] == "uid-9"
    assert headers["Requestid"]


def test_login_returns_the_token_from_the_result(monkeypatch: pytest.MonkeyPatch) -> None:
    _capture_login(monkeypatch, {"code": 0, "result": {"token": "a.b.c", "userId": "uid-9"}})
    result = kdf.login("u", "p", **LOGIN_KWARGS)
    assert result["token"] == "a.b.c"
    # The rest of the result survives: the caller may need userId (the tools
    # read AQARA_USER_ID separately, which is only safe while it never changes).
    assert result["userId"] == "uid-9"


def test_login_surfaces_the_810_rejection(monkeypatch: pytest.MonkeyPatch) -> None:
    # The observed real-server answer. Note the cloud's own wording covers TWO
    # causes — wrong password OR unregistered account — so callers must not
    # report it as "wrong password" alone.
    _capture_login(
        monkeypatch,
        {
            "code": 810,
            "message": "Error de contraseña o cuenta no registrada.",
            "msgDetails": "Password incorrect",
        },
    )
    with pytest.raises(RuntimeError) as excinfo:
        kdf.login("u", "p", **LOGIN_KWARGS)

    message = str(excinfo.value)
    assert "810" in message
    assert "/user/guard-code/login" in message


# ---------------------------------------------------------------------------
# Offline password ("Contraseña sin conexión") — feature 038
#
# Response fixtures below are the REAL JSON captured live 2026-08-30 (see
# docs/devices/u200/operations.md, "2026-08-30 (resolved)"), reproduced here
# as-is so a regression in parsing this exact shape is caught.
# ---------------------------------------------------------------------------

OFFLINE_PASSWORD_RESPONSE: dict[str, Any] = {
    "result": {"passwd": ["651399", "637408"]},
    "code": 0,
    "requestId": "6e162a10df7e455c8a09f95e42326000.65.17881247433120661",
    "message": "Success",
    "msgDetails": "Success",
}

OFFLINE_PASSWORD_LOG_RESPONSE: dict[str, Any] = {
    "result": [
        {
            "createTime": "1788123833807",
            "startTime": "1788123600000",
            "endTime": "1788124200000",
            "did": "matt.73cb7865154223b90e81d000",
        }
    ],
    "code": 0,
    "requestId": "6e162a10df7e455c8a09f95e42326000.68.17881247317827579",
    "message": "Success",
    "msgDetails": "Success",
}


def _capture_request_json(
    monkeypatch: pytest.MonkeyPatch, response: dict[str, Any]
) -> dict[str, Any]:
    """Replace kdf._request_json and record exactly what was asked of it."""

    seen: dict[str, Any] = {}

    def _fake_request(
        method: str,
        url: str,
        payload: Any,
        auth_headers: Any = None,
        timeout: float = 10,
        signer: Any = None,
        path_rel: str | None = None,
        encrypt_appkey: str | None = None,
    ) -> dict[str, Any]:
        seen["method"] = method
        seen["url"] = url
        seen["payload"] = payload
        return response

    monkeypatch.setattr(kdf, "_request_json", _fake_request)
    return seen


def test_fetch_offline_passwords_parses_the_real_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _capture_request_json(monkeypatch, OFFLINE_PASSWORD_RESPONSE)
    batch = kdf.fetch_offline_passwords("matt.fake", None, "https://example.test")
    assert batch.codes == ("651399", "637408")


def test_fetch_offline_passwords_calls_the_get_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _capture_request_json(monkeypatch, OFFLINE_PASSWORD_RESPONSE)
    kdf.fetch_offline_passwords("matt.fake", None, "https://example.test")
    assert seen["method"] == "GET"
    assert seen["url"] == "https://example.test" + kdf._PATH_OFFLINE_PASSWORD


def test_fetch_offline_passwords_sends_did_as_a_json_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Confirmed live 2026-08-31 (native SSL hook, fresh capture): the real
    app's GET request to this endpoint carries a JSON body ``{"did": "..."}``
    — not a bodyless GET as originally assumed, and not a header/query param
    either. Captured the exact SSL_write immediately preceding a real
    passwd response on the maintainer's own account/device.
    """
    seen = _capture_request_json(monkeypatch, OFFLINE_PASSWORD_RESPONSE)
    kdf.fetch_offline_passwords("matt.fake", None, "https://example.test")
    assert seen["payload"] == {"did": "matt.fake"}


def test_fetch_offline_passwords_window_is_a_10_minute_grid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _capture_request_json(monkeypatch, OFFLINE_PASSWORD_RESPONSE)
    # 2026-08-30 23:19:03.474 local, mid-window — same instant as one of the
    # real samples that produced OFFLINE_PASSWORD_RESPONSE.
    fixed_now_ms = 1788124743474
    batch = kdf.fetch_offline_passwords(
        "matt.fake", None, "https://example.test", _now_ms=lambda: fixed_now_ms
    )
    assert batch.window_start_ms % 600_000 == 0
    assert batch.window_end_ms - batch.window_start_ms == 600_000
    assert batch.window_start_ms == 1788124200000  # confirmed real startTime
    assert batch.window_end_ms == 1788124800000  # confirmed real endTime


def test_fetch_offline_passwords_empty_list_is_not_an_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _capture_request_json(monkeypatch, {**OFFLINE_PASSWORD_RESPONSE, "result": {"passwd": []}})
    batch = kdf.fetch_offline_passwords("matt.fake", None, "https://example.test")
    assert batch.codes == ()


def test_fetch_offline_passwords_propagates_cloud_service_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _capture_request_json(
        monkeypatch, {"code": 108, "message": "token expired", "msgDetails": None}
    )
    with pytest.raises(kdf.CloudServiceError) as excinfo:
        kdf.fetch_offline_passwords("matt.fake", None, "https://example.test")
    assert excinfo.value.is_code(108)


def test_fetch_offline_password_log_parses_the_real_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _capture_request_json(monkeypatch, OFFLINE_PASSWORD_LOG_RESPONSE)
    entries = kdf.fetch_offline_password_log(
        "matt.73cb7865154223b90e81d000", 1788123600000, 1788124200000, None, "https://example.test"
    )
    assert len(entries) == 1
    entry = entries[0]
    assert entry.create_time_ms == 1788123833807
    assert entry.start_time_ms == 1788123600000
    assert entry.end_time_ms == 1788124200000
    assert entry.device_id == "matt.73cb7865154223b90e81d000"


def test_fetch_offline_password_log_builds_the_query_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _capture_request_json(monkeypatch, OFFLINE_PASSWORD_LOG_RESPONSE)
    kdf.fetch_offline_password_log("matt.abc", 111, 222, None, "https://example.test")
    assert seen["method"] == "GET"
    assert seen["url"].startswith("https://example.test" + kdf._PATH_OFFLINE_PASSWORD_LOG + "?")
    assert "did=matt.abc" in seen["url"]
    assert "startTime=111" in seen["url"]
    assert "endTime=222" in seen["url"]


def test_fetch_offline_password_log_drops_incomplete_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = {
        "result": [
            {"createTime": "1", "startTime": "2", "endTime": "3", "did": "matt.a"},
            {"createTime": "1", "startTime": "2"},  # missing endTime/did
        ],
        "code": 0,
    }
    _capture_request_json(monkeypatch, response)
    entries = kdf.fetch_offline_password_log("matt.a", 1, 2, None, "https://example.test")
    assert len(entries) == 1
    assert entries[0].device_id == "matt.a"
