"""Autonomous BLE control for the Aqara U200 smart lock.

Pure-Python reimplementation of the cloud KDF, the BLE authentication
handshake (frames ``0610``/``0710``) and the AES-CCM control channel. See
``docs/`` for the reverse-engineered protocol.

This package is assembled incrementally, one Spec Kit feature at a time. The
current build exposes **feature 001 — cloud login & key derivation**; later
features (002 BLE handshake, 003 control channel, 004 operations, 005
end-to-end) extend the public surface below.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from .kdf import (
    aes128gcm_decrypt_body,
    aes128gcm_encrypt_body,
    build_cloud_auth_headers,
    cloud_get_public_key,
    cloud_verify,
    compute_nonce,
    compute_sign,
    encrypt_login_password,
    get_session_material,
    hkdf_expand,
    hkdf_extract,
    hkdf_sha256,
    login,
    make_local_signer,
    prepare_runtime_cloud_auth_headers,
)

try:
    __version__ = version("aqara-u200-ble")
except PackageNotFoundError:  # pragma: no cover - running from a source checkout
    __version__ = "0.0.0+unknown"

__all__ = [
    "__version__",
    # feature 001 — cloud login & key derivation
    "aes128gcm_decrypt_body",
    "aes128gcm_encrypt_body",
    "build_cloud_auth_headers",
    "cloud_get_public_key",
    "cloud_verify",
    "compute_nonce",
    "compute_sign",
    "encrypt_login_password",
    "get_session_material",
    "hkdf_expand",
    "hkdf_extract",
    "hkdf_sha256",
    "login",
    "make_local_signer",
    "prepare_runtime_cloud_auth_headers",
]
