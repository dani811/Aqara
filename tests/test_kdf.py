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

from aqara_u200_ble import (
    aes128gcm_decrypt_body,
    aes128gcm_encrypt_body,
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
