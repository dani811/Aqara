"""Aqara U200 BLE authentication — cloud KDF client.

The Aqara U200 authentication uses a CLOUD-SIDE KDF, not a device-side one.
The lock and the Aqara cloud exchange ephemeral EC keys (SECP256R1); the
cloud computes ECDH + KDF server-side and returns the derived session
material (sessionKey, nonce, verifyData) to the app.

KDF flow (from Frida instrumentation of com.lumiunited.aqarahome.play v6905):
  1. App  → Cloud  POST /dev/bluetooth/login/assure/publickey
                   body: {"deviceId": "<did>"}
                   ← {"cloudPublicKey": "<65-byte hex uncompressed SECP256R1>",
                       "extraId": "lumi.<mac>", "mac": "<mac>"}
  2. App  → Lock   BLE write (char ff07): send cloudPublicKey in 5a-framed
                   fragments (65 bytes, 20-byte BLE packets).
  3. Lock → App    BLE notify (char ff08): lock's ephemeral pubkey in
                   da-framed fragments (65 bytes, uncompressed SECP256R1).
  4. App  → Cloud  POST /dev/bluetooth/login/assure/verify
                   body: {"deviceId": "<did>", "devicePublicKey": "<65-byte hex>"}
                   ← {"sessionKey": "<32 hex chars>",
                       "nonce":       "<26 hex chars>",
                       "verifyData":  "<16 hex chars>",
                       "mac":         "<16 hex chars>"}
  5. App  → Lock   BLE: verifyData proves the session to the lock.
  6. Lock → App    BLE: ack; subsequent data encrypted with AES-CCM
                   (sessionKey / nonce).

Session material shape (values are placeholders — real captures never ship):
    cloudPublicKey  = 04<...>            (65 bytes, uncompressed SECP256R1)
    lockPublicKey   = 04<...>            (65 bytes)
    sessionKey      = <...>              (16 bytes)
    nonce           = <...>              (13 bytes, fixed per session)
    verifyData      = <...>              (8 bytes)
    LTMK            = <...>              (32 bytes, server-side secret)
    Device DID      = matt.<...>
    Lock MAC        = <AA:BB:CC:DD:EE:FF>

Standard HKDF-SHA256 helpers are also exposed for local experimentation
(offline analysis of captured session data).

NOTE: this module is purely observational.  It never writes to the lock.
"""

from __future__ import annotations

import base64
import contextlib
import gzip
import hashlib
import hmac
import json
import os
import secrets
import ssl
import sys
import time
import uuid
from collections.abc import Callable, Mapping
from typing import Any, cast
from urllib import error as urlerror
from urllib import request as urlrequest

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding as _pad
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.serialization import load_der_public_key

# A cloud request signer: (relative path, plaintext body) -> signed HTTP headers.
Signer = Callable[[str | None, str], Mapping[str, str]]

# ---------------------------------------------------------------------------
# HKDF-SHA256 primitives
# ---------------------------------------------------------------------------


def hkdf_extract(salt: bytes, ikm: bytes) -> bytes:
    """HKDF-Extract using SHA-256."""

    if not salt:
        salt = b"\x00" * hashlib.sha256().digest_size
    return hmac.new(salt, ikm, hashlib.sha256).digest()


def hkdf_expand(prk: bytes, info: bytes, length: int) -> bytes:
    """HKDF-Expand using SHA-256."""

    if length <= 0:
        raise ValueError("length must be positive")
    digest_size = hashlib.sha256().digest_size
    if length > 255 * digest_size:
        raise ValueError("length too large for HKDF-SHA256")

    okm = bytearray()
    previous_block = b""
    counter = 1
    while len(okm) < length:
        previous_block = hmac.new(
            prk,
            previous_block + info + bytes((counter,)),
            hashlib.sha256,
        ).digest()
        okm.extend(previous_block)
        counter += 1
    return bytes(okm[:length])


def hkdf_sha256(
    ikm: bytes,
    salt: bytes = b"",
    info: bytes = b"",
    length: int = 32,
) -> bytes:
    """Convenience wrapper around HKDF-Extract and HKDF-Expand."""

    prk = hkdf_extract(salt, ikm)
    return hkdf_expand(prk, info, length)


# ---------------------------------------------------------------------------
# Aqara cloud KDF API client
# ---------------------------------------------------------------------------

# Known region → base URL mapping
# Captured from Frida OkHttp hook (auth4.log, 2026-08-06):
#   rpc-ger.aqara.com → European/German server (area=EU)
# Full URL format: {base_url}/{path}
# Captured example: https://rpc-ger.aqara.com/app/v1.0/lumi/dev/bluetooth/login/assure/publickey
REGION_BASE_URLS: dict[str, str] = {
    "EU": "https://rpc-ger.aqara.com/app/v1.0/lumi",  # confirmed from auth4.log
    "US": "https://rpc-us.aqara.com/app/v1.0/lumi",  # inferred pattern
    "CN": "https://rpc.aqara.com/app/v1.0/lumi",  # inferred pattern
    "KR": "https://rpc-kr.aqara.com/app/v1.0/lumi",  # inferred pattern
    "RU": "https://rpc-ru.aqara.com/app/v1.0/lumi",  # inferred pattern
}

# API paths (relative; append to base URL)
_PATH_PUBLICKEY = "/dev/bluetooth/login/assure/publickey"
_PATH_VERIFY = "/dev/bluetooth/login/assure/verify"
_REQUIRED_AUTH_HEADERS = (
    "Lang",
    "Cuty",
    "App-Version",
    "Phone-Model",
    "Sys-Type",
    "Sys-Version",
    "PhoneId",
    "Area",
    "Appid",
    "Appkey",
    "ClientId",
    "UserId",
    "Token",
)


# ---------------------------------------------------------------------------
# Sign nativo reimplementado (autonomo, sin app/movil)
# ---------------------------------------------------------------------------
#
# Reverseado de com.lumi.external.http...DefaultInterceptorStrategy.assemblyHeaderSign
# + captura del input EXACTO al MD5 dentro de LumiDevSDK.getSignHead (Rust nativo,
# liblumidevsdk.so) via hook acotado de memcpy.  Validado contra la salida
# controlada del propio getSignHead y contra 3 firmas reales capturadas.
#
#   Nonce = MD5(Requestid).UPPERCASE
#   Sign  = MD5("Appid={appid}&Nonce={nonce}&Time={time}&Token={token}&{body}&{appkey}")
#
# OJO: body y appkey van SIN clave (solo "&valor"); nonce va en MAYUSCULAS.


def compute_nonce(request_id: str) -> str:
    """Nonce = MD5(Requestid) en mayusculas (como MD5Utils.getMD5 de la app)."""
    return hashlib.md5(request_id.encode("utf-8")).hexdigest().upper()


def compute_sign(
    *,
    appid: str,
    nonce: str,
    time: str,
    token: str,
    body: str,
    appkey: str,
) -> str:
    """Reimplementacion de LumiDevSDK.getSignHead (Rust nativo) en Python puro.

    `nonce` debe ser el valor del header Nonce (= MD5(Requestid).upper()).
    `body` es el cuerpo en CLARO (JSON compacto). Ojo: incluso cuando la
    peticion viaja cifrada (x-aes128gcm), el Sign se calcula sobre el PLAINTEXT.
    Cuando no hay token (p.ej. login), el campo `Token=` se OMITE por completo
    (verificado contra una firma real de login).
    """
    if token:
        pre = f"Appid={appid}&Nonce={nonce}&Time={time}&Token={token}&{body}&{appkey}"
    else:
        pre = f"Appid={appid}&Nonce={nonce}&Time={time}&{body}&{appkey}"
    return hashlib.md5(pre.encode("utf-8")).hexdigest()


def make_local_signer(
    *,
    appid: str,
    appkey: str,
    token: str,
    user_id: str,
    client_id: str,
    phone_id: str,
    area: str = "EU",
    lang: str = "es",
    country: str = "ES",
    app_version: str = "6.3.7",
    phone_model: str = "motorola edge 50 fusion##Mobile",
    sys_type: str = "1",
    sys_version: str = "16",
) -> Signer:
    """Devuelve un `signer(path_rel, body_str) -> headers` 100% local (sin movil).

    Compatible con el parametro `signer` de cloud_get_public_key / cloud_verify /
    get_session_material / run_authenticated_lock_operation.  Genera Requestid,
    Time y Nonce frescos y calcula el Sign con compute_sign().
    """

    def signer(path_rel: str | None, body_str: str) -> dict[str, str]:
        request_id = str(uuid.uuid4())
        nonce = compute_nonce(request_id)
        time_ms = str(int(time.time() * 1000))
        sign = compute_sign(
            appid=appid,
            nonce=nonce,
            time=time_ms,
            token=token,
            body=body_str,
            appkey=appkey,
        )
        # Cabeceras enviadas: como las reales, con Sign en lugar de Appkey.
        headers = {
            "Lang": lang,
            "Cuty": country,
            "App-Version": app_version,
            "Phone-Model": phone_model,
            "Sys-Type": sys_type,
            "Sys-Version": sys_version,
            "PhoneId": phone_id,
            "Area": area,
            "Appid": appid,
            "ClientId": client_id,
            "Time": time_ms,
            "Nonce": nonce,
            "Sign": sign,
        }
        if token:
            # Peticion autenticada: incluir identidad.
            headers["Token"] = token
            headers["UserId"] = user_id
            headers["Requestid"] = request_id
        # Sin token (login): la app NO envia Token/UserId/Requestid; el Nonce
        # ya codifica el Requestid y el Sign se calculo sin el campo Token.
        return headers

    return signer


# Clave publica RSA-1024 del login (encryptType:2). Se usa para cifrar la
# contrasena en POST /user/guard-code/login.
#
# RESUELTA 2026-08-12: extraida en runtime (NO estatica) via hook Frida sobre
# javax.crypto.Cipher.doFinal([B]) filtrando por output.length==128 (RSA-1024)
# + reflexion sobre el campo `spi` -> OpenSSLKey -> NativeCrypto.get_RSA_public_params
# (tools/capture_rsaspi2.js). Clave anterior (extraida estaticamente del dex /
# libdatajar.so) daba code=500 "Service impl error" -> NO era la del login.
# Esta SI es correcta: verificado end-to-end contra el servidor real con una
# contrasena deliberadamente falsa -> code=810 "Password incorrect" (el server
# descifro bien y comparo, solo fallo por la contrasena, como se esperaba) en
# vez del 500 de antes. Login 100% autonomo ya no depende de reenviar un
# ciphertext capturado.
_LOGIN_RSA_PUBKEY_DER_B64 = (
    "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCG46slB57013JJs4Vvj5cVyMpR9b+B2F+YJU6"
    "qhBEYbiEmIdWpFPpOuBikDs2FcPS19MiWq1IrmxJtkICGurqImRUt4lP688IWlEmqHfSxSRf2+a"
    "H0cH8VWZ2OaZn5DWSIHIPBF2kxM71q8stmoYiV0oZsrZzBHsMuBwA4LQdxBwIDAQAB"
)

_PATH_LOGIN = "/user/guard-code/login"


def encrypt_login_password(password: str) -> str:
    """Cifra la contrasena con la RSA-1024 del login (PKCS#1 v1.5) -> base64."""
    pub = load_der_public_key(base64.b64decode(_LOGIN_RSA_PUBKEY_DER_B64))
    if not isinstance(pub, rsa.RSAPublicKey):  # pragma: no cover - key is RSA-1024
        raise TypeError("login public key is not RSA")
    ct = pub.encrypt(password.encode("utf-8"), _pad.PKCS1v15())
    return base64.b64encode(ct).decode("ascii")


# --- Content-Encoding: x-aes128gcm (esquema custom estilo RFC 8188) ----------
# El body del login (y la respuesta) van cifrados con AES-128-GCM.  Reversado por
# captura nativa (LumiDevSDK.aesEncryptedContent) + verificado con 2 muestras:
#   key   = appkey[:16]                          (AES-128, los 16 primeros bytes)
#   salt  = 16 bytes aleatorios
#   nonce = HKDF-SHA256(salt=salt, IKM=appkey, info=b"")[:12]
#   ct||tag = AES-128-GCM(key, nonce, plaintext)
#   wire  = base64(salt + 0x00) "-" base64(ct) "-" base64(tag)
# El server responde con el mismo formato (su propio salt) -> se descifra igual.


def _aes128gcm_nonce(salt: bytes, appkey: str) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=12, salt=salt, info=b"").derive(
        appkey.encode("ascii")
    )


def aes128gcm_encrypt_body(plaintext: bytes, appkey: str) -> str:
    """Cifra un cuerpo -> blob `b64(salt+00)-b64(ct)-b64(tag)` (x-aes128gcm)."""
    ak = appkey.encode("ascii")
    salt = secrets.token_bytes(16)
    nonce = _aes128gcm_nonce(salt, appkey)
    ct_tag = AESGCM(ak[:16]).encrypt(nonce, plaintext, None)
    ct, tag = ct_tag[:-16], ct_tag[-16:]
    return "-".join(
        (
            base64.b64encode(salt + b"\x00").decode("ascii"),
            base64.b64encode(ct).decode("ascii"),
            base64.b64encode(tag).decode("ascii"),
        )
    )


def aes128gcm_decrypt_body(blob: str, appkey: str) -> bytes:
    """Descifra un blob x-aes128gcm -> bytes en claro."""
    ak = appkey.encode("ascii")
    parts = blob.strip().split("-")
    if len(parts) != 3:
        raise ValueError(f"blob x-aes128gcm invalido ({len(parts)} partes)")
    salt = base64.b64decode(parts[0])[:16]
    ct = base64.b64decode(parts[1])
    tag = base64.b64decode(parts[2])
    nonce = _aes128gcm_nonce(salt, appkey)
    return AESGCM(ak[:16]).decrypt(nonce, ct + tag, None)


def login(
    account: str,
    password: str,
    *,
    appid: str,
    appkey: str,
    client_id: str,
    phone_id: str,
    district: str = "ES",
    region: str = "EU",
    area: str = "EU",
    guard_code: str = "",
    sign_token: str = "",
    user_id: str = "",
) -> dict[str, Any]:
    """Login: credenciales -> token (JWT).

    POST /user/guard-code/login. El body lleva DOBLE cifrado:
      1. `password` = RSA-1024 PKCS#1 v1.5 base64 (encryptType:2).
      2. El body JSON entero -> AES-128-GCM (Content-Encoding: x-aes128gcm),
         con clave = appkey[:16] y nonce = HKDF(salt, appkey).
    IMPORTANTE: la peticion se FIRMA con un token valido existente (`sign_token`)
    sobre el BLOB cifrado; el servidor rechaza la firma con token vacio.  Es
    decir, se re-loguea con un token bootstrap (~10 dias) para obtener uno fresco.
    Devuelve el dict `result` (incluye el nuevo token) + clave 'token'.
    """
    body = {
        "account": account,
        "district": district,
        "encryptType": 2,
        "guardCode": guard_code,
        "password": encrypt_login_password(password),
    }
    base = REGION_BASE_URLS.get(region, REGION_BASE_URLS["EU"])
    signer = make_local_signer(
        appid=appid,
        appkey=appkey,
        token=sign_token,
        user_id=user_id,
        client_id=client_id,
        phone_id=phone_id,
        area=area,
    )
    data = _post_json(
        base + _PATH_LOGIN,
        body,
        None,
        signer=signer,
        path_rel=_PATH_LOGIN,
        encrypt_appkey=appkey,
    )
    result = _unwrap_aqara_result(data, endpoint=_PATH_LOGIN)
    token = None
    if isinstance(result, dict):
        token = result.get("token") or result.get("accessToken") or result.get("loginToken")
    result = dict(result) if isinstance(result, dict) else {"raw": result}
    result["token"] = token
    return result


def build_cloud_auth_headers(
    *,
    lang: str,
    country: str,
    app_version: str,
    phone_model: str,
    time: str,
    sys_type: str,
    sys_version: str,
    nonce: str,
    phone_id: str,
    area: str,
    appid: str,
    appkey: str,
    client_id: str,
    user_id: str,
    token: str,
    request_id: str | None = None,
    sign: str | None = None,
) -> dict[str, str]:
    """Build the exact HTTP auth headers observed in the real Aqara app.

    The log shows the header name `Cuty` (not `Country`), so the builder keeps
    the observed casing to match the captured requests.
    """

    headers = {
        "Lang": lang,
        "Cuty": country,
        "App-Version": app_version,
        "Phone-Model": phone_model,
        "Time": time,
        "Sys-Type": sys_type,
        "Sys-Version": sys_version,
        "Nonce": nonce,
        "PhoneId": phone_id,
        "Area": area,
        "Appid": appid,
        "Appkey": appkey,
        "ClientId": client_id,
        "UserId": user_id,
        "Token": token,
    }
    if request_id:
        headers["Requestid"] = request_id
    if sign:
        headers["Sign"] = sign
    return headers


# Headers that describe THIS Python request's transport and must never be
# replayed from a captured header block: they belong to the original okhttp
# connection (stale Content-Length, gzip negotiation, keep-alive, its Host).
# Leaking them makes the outgoing request self-inconsistent (e.g. a stale
# Content-Length truncates the body, or Accept-Encoding: gzip yields a gzipped
# response that json.loads cannot read).
_TRANSPORT_HEADERS = frozenset(
    h.lower()
    for h in (
        "Content-Length",
        "Host",
        "Connection",
        "Accept-Encoding",
        "Content-Encoding",
        "Transfer-Encoding",
        "User-Agent",
    )
)

# Transport security (feature 006). Cloud calls carry the material that opens a
# physical door, so certificates are verified by default. The opt-out exists for
# machines whose CA store is unusable (a fresh macOS Python install); it is an
# environment switch, never a parameter, so no call site can hard-code it.
_INSECURE_TLS_ENV = "U200_INSECURE_TLS"
# Fail-safe parsing: only these disable verification. A typo keeps it enabled.
_TRUTHY_ENV_VALUES = frozenset({"1", "true", "yes", "on"})


def _tls_context() -> ssl.SSLContext:
    """Build the TLS context for a cloud request.

    Verifies the certificate chain against the platform trust store and checks
    the hostname. Setting ``U200_INSECURE_TLS`` to ``1``/``true``/``yes``/``on``
    disables both and prints a warning — it removes protection against
    machine-in-the-middle interception and must never be used on an untrusted
    network.
    """

    context = ssl.create_default_context()
    if os.environ.get(_INSECURE_TLS_ENV, "").strip().lower() in _TRUTHY_ENV_VALUES:
        print(
            f"[U200] WARNING: TLS certificate verification is DISABLED "
            f"({_INSECURE_TLS_ENV}); this connection is not protected against "
            f"interception.",
            file=sys.stderr,
        )
        # Order matters: CPython rejects CERT_NONE while check_hostname is on.
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    return context


def _post_json(
    url: str,
    payload: Mapping[str, Any],
    auth_headers: Mapping[str, str] | None = None,
    timeout: float = 10,
    signer: Signer | None = None,
    path_rel: str | None = None,
    encrypt_appkey: str | None = None,
) -> dict[str, Any]:
    # Serialize compactly (no spaces) so the body matches the exact bytes the
    # Aqara app signs/sends; okhttp+gson emit `{"deviceId":"..."}` with no space.
    body_str = json.dumps(payload, separators=(",", ":"))
    # El Sign SIEMPRE se calcula sobre el PLAINTEXT (body_str), aunque el cuerpo
    # viaje cifrado. Con cifrado x-aes128gcm se envia el BLOB pero se firma el claro.
    if encrypt_appkey is not None:
        data = aes128gcm_encrypt_body(body_str.encode("utf-8"), encrypt_appkey).encode("utf-8")
    else:
        data = body_str.encode("utf-8")
    if signer is not None:
        # El firmante devuelve cabeceras YA firmadas sobre el cuerpo en claro. El
        # Sign NO cubre la URL (solo cabeceras+body en claro).
        prepared = dict(signer(path_rel, body_str))
    else:
        if auth_headers is None:
            raise RuntimeError("_post_json necesita auth_headers o signer")
        prepared = prepare_runtime_cloud_auth_headers(auth_headers)
    request_headers = {
        key: value for key, value in prepared.items() if key.lower() not in _TRANSPORT_HEADERS
    }
    request_headers.setdefault("Accept", "application/json")
    request_headers.setdefault("Content-Type", "application/json; charset=utf-8")
    if encrypt_appkey is not None:
        # Cuerpo cifrado: negociamos el mismo codec para peticion y respuesta.
        request_headers["Content-Encoding"] = "x-aes128gcm"
        request_headers["Accept-Encoding"] = "x-aes128gcm"
    else:
        # Ask for an unencoded body so response.read() is plain UTF-8 JSON; we
        # still gunzip defensively below in case the server ignores this.
        request_headers["Accept-Encoding"] = "identity"
    request = urlrequest.Request(url, data=data, headers=request_headers, method="POST")
    try:
        ssl_context = _tls_context()
        with urlrequest.urlopen(request, timeout=timeout, context=ssl_context) as response:
            raw = response.read()
            enc = response.headers.get("Content-Encoding", "").lower()
            if enc == "gzip":
                raw = gzip.decompress(raw)
                body = raw.decode("utf-8")
            elif enc == "x-aes128gcm" and encrypt_appkey is not None:
                body = aes128gcm_decrypt_body(raw.decode("ascii"), encrypt_appkey).decode("utf-8")
            else:
                body = raw.decode("utf-8")
    except urlerror.HTTPError as exc:
        raw = exc.read()
        enc = exc.headers.get("Content-Encoding", "").lower()
        if enc == "gzip":
            with contextlib.suppress(OSError):
                raw = gzip.decompress(raw)
            body = raw.decode("utf-8", "replace")
        elif enc == "x-aes128gcm" and encrypt_appkey is not None:
            try:
                body = aes128gcm_decrypt_body(raw.decode("ascii"), encrypt_appkey).decode("utf-8")
            except Exception:
                body = raw.decode("utf-8", "replace")
        else:
            body = raw.decode("utf-8", "replace")
        raise RuntimeError(f"{url} returned HTTP {exc.code}: {body[:200]}") from exc
    except urlerror.URLError as exc:
        # urlopen wraps a certificate failure in URLError.reason. Say what failed
        # and what the deliberate override is, instead of a bare ssl traceback.
        if isinstance(exc.reason, ssl.SSLCertVerificationError):
            raise RuntimeError(
                f"TLS certificate verification failed for {url}: {exc.reason}. "
                f"Either this machine's trust store is misconfigured or the "
                f"connection is being intercepted. If you accept the risk, set "
                f"{_INSECURE_TLS_ENV}=1 to skip verification."
            ) from exc
        raise RuntimeError(f"failed to contact {url}: {exc.reason}") from exc
    except TimeoutError as exc:
        raise RuntimeError(f"timeout contacting {url}") from exc

    try:
        result = json.loads(body)
        if os.environ.get("U200_DEBUG"):
            print(f"[U200] {url} -> {result}", file=sys.stderr)
        return cast("dict[str, Any]", result)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{url} returned invalid JSON: {body[:200]}") from exc


def _unwrap_aqara_result(payload: dict[str, Any], *, endpoint: str) -> dict[str, Any]:
    if "code" in payload and payload.get("code") not in (0, "0", None):
        raise RuntimeError(
            f"{endpoint} rejected by Aqara cloud: "
            f"code={payload.get('code')} message={payload.get('message')} "
            f"details={payload.get('msgDetails')}"
        )
    result = payload.get("result")
    if isinstance(result, dict):
        return result
    return payload


def prepare_runtime_cloud_auth_headers(auth_headers: Mapping[str, str]) -> dict[str, str]:
    prepared = dict(auth_headers)
    has_sign = bool(prepared.get("Sign", "").strip())
    required_headers = tuple(
        key for key in _REQUIRED_AUTH_HEADERS if not (has_sign and key == "Appkey")
    )
    missing = [key for key in required_headers if not prepared.get(key)]
    if missing:
        raise RuntimeError(
            "Faltan cabeceras de auth obligatorias para Aqara cloud: " + ", ".join(missing)
        )
    placeholder_keys = []
    for key in ("Token", "Authorization", "Appid", "Appkey", "ClientId", "UserId"):
        if key not in prepared:
            continue
        if prepared.get(key, "").strip() in {"", "******", "REPLACE_ME", "<token>"}:
            placeholder_keys.append(key)
    if placeholder_keys:
        raise RuntimeError(
            "Cabeceras con valores de marcador detectadas. "
            f"Actualiza estos campos con valores reales capturados: {', '.join(placeholder_keys)}"
        )

    if has_sign:
        # Si llega una firma capturada, hay que mantener el mismo Time/Nonce/Requestid
        # para no invalidarla.
        for key in ("Time", "Nonce"):
            if not prepared.get(key):
                raise RuntimeError(
                    f"El header firmado incluye Sign pero falta {key}; no se puede reutilizar."
                )
    else:
        # Sin firma, renovamos campos volátiles para flujos donde el backend no la exige.
        prepared["Time"] = str(int(time.time() * 1000))
        prepared["Nonce"] = secrets.token_hex(16).upper()
        prepared["Requestid"] = str(uuid.uuid4())
    return prepared


def cloud_get_public_key(
    device_id: str,
    auth_headers: Mapping[str, str] | None,
    base_url: str,
    signer: Signer | None = None,
) -> str:
    """Step 1 of BLE auth: ask the cloud for an ephemeral EC public key.

    Args:
        device_id:    Lock DID, e.g. "matt.<...>".
        auth_headers: HTTP headers that authenticate the request to Aqara
                      cloud.  Build them from a real capture with
                      build_cloud_auth_headers().
        base_url:     Region base URL, e.g. REGION_BASE_URLS["EU"].

    Returns:
        cloudPublicKey as a hex string (130 hex chars, uncompressed SECP256R1,
        starting with "04").

    Raises:
        RuntimeError: if the cloud returns a non-200 status or missing key.
    """
    data = _post_json(
        f"{base_url}{_PATH_PUBLICKEY}",
        {"deviceId": device_id},
        auth_headers,
        signer=signer,
        path_rel=_PATH_PUBLICKEY,
    )

    unwrapped = _unwrap_aqara_result(data, endpoint=_PATH_PUBLICKEY)
    cloud_pub = unwrapped.get("cloudPublicKey") if isinstance(unwrapped, dict) else None
    if not cloud_pub:
        raise RuntimeError(f"No cloudPublicKey in response: {data}")
    return cast("str", cloud_pub)


def cloud_verify(
    device_id: str,
    device_public_key_hex: str,
    auth_headers: Mapping[str, str] | None,
    base_url: str,
    signer: Signer | None = None,
) -> dict[str, str]:
    """Step 4 of BLE auth: send the lock's pubkey; receive session material.

    Args:
        device_id:             Lock DID.
        device_public_key_hex: Lock's ephemeral EC public key (130 hex chars,
                               uncompressed SECP256R1, starting with "04").
                               Captured from BLE da-framed notify packets.
        auth_headers:          Same auth headers as cloud_get_public_key.
        base_url:              Region base URL.

    Returns:
        Dict with keys:
          "sessionKey"  — 16-byte hex string (AES-128 key for AES-CCM)
          "nonce"       — 13-byte hex string (AES-CCM nonce)
          "verifyData"  — 8-byte hex string (sent to lock to prove session)
          "mac"         — 8-byte hex string (lock MAC bytes, little-endian)

    Raises:
        RuntimeError: on HTTP error or missing fields.
    """
    data = _post_json(
        f"{base_url}{_PATH_VERIFY}",
        {
            "deviceId": device_id,
            "devicePublicKey": device_public_key_hex,
        },
        auth_headers,
        signer=signer,
        path_rel=_PATH_VERIFY,
    )
    result: dict[str, Any] = _unwrap_aqara_result(data, endpoint=_PATH_VERIFY)
    for field in ("sessionKey", "nonce", "verifyData"):
        if field not in result:
            raise RuntimeError(f"Missing '{field}' in verify response: {data}")
    return {
        "sessionKey": result["sessionKey"],
        "nonce": result["nonce"],
        "verifyData": result["verifyData"],
        "mac": result.get("mac", ""),
    }


def get_session_material(
    device_id: str,
    device_public_key_hex: str,
    auth_headers: Mapping[str, str] | None = None,
    *,
    region: str = "EU",
    base_url: str | None = None,
    signer: Signer | None = None,
) -> dict[str, str]:
    """Convenience wrapper for step 4 only (caller already has cloudPublicKey).

    This is the typical call after BLE key exchange is complete:
      - cloud gave you cloudPublicKey (step 1)
      - you sent it to the lock (step 2)
      - the lock responded with its pubkey (step 3)
      - call this function with the lock's pubkey → get session material

    Args:
        device_id:             Lock DID.
        device_public_key_hex: Lock's ephemeral EC public key from BLE.
        auth_headers:          Aqara cloud auth headers built from a captured
                               runtime request.
        region:                Region code ("EU", "US", "CN", …).
        base_url:              Override base URL; inferred from region if None.

    Returns:
        Dict with sessionKey, nonce, verifyData, mac (all hex strings).
    """
    url = base_url or REGION_BASE_URLS.get(region, REGION_BASE_URLS["EU"])
    return cloud_verify(device_id, device_public_key_hex, auth_headers, url, signer=signer)


# The auth header map is intentionally caller-provided.  Use
# build_cloud_auth_headers() to materialize the exact key casing from a capture
# and keep user-specific values (token, sign, request id) out of source.
