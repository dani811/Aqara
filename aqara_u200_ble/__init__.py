"""Autonomous BLE control for the Aqara U200 smart lock.

Pure-Python reimplementation of the cloud KDF, the BLE authentication
handshake (frames ``0610``/``0710``) and the AES-CCM control channel. See
``docs/`` for the reverse-engineered protocol.

This package is assembled incrementally, one Spec Kit feature at a time. The
current build exposes **feature 001 — cloud login & key derivation** and
**feature 002 — control channel framing**; later features (003 operations,
004 BLE auth handshake, 005 end-to-end) extend the public surface below.
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
from .lock_ops import (
    LockOperation,
    LockOperationWrite,
    build_lock_operation_write,
    normalize_lock_operation,
    send_lock_operation,
)
from .protocol import (
    ATT_CONTROL_NOTIFY,
    ATT_CONTROL_WRITE,
    AUTH_NOTIFY,
    AUTH_WRITE,
    BULK_NOTIFY,
    BULK_WRITE,
    CONTROL_NOTIFY,
    CONTROL_WRITE,
    ATTPacket,
    ControlRequest,
    control_command_name,
    parse_control_request,
    valid_crc,
)
from .volume import (
    VoiceVolumePreset,
    VoiceVolumeWrite,
    build_voice_volume_write,
    normalize_voice_volume_preset,
    set_voice_volume,
    write_voice_volume,
)

try:
    __version__ = version("aqara-u200-ble")
except PackageNotFoundError:  # pragma: no cover - running from a source checkout
    __version__ = "0.0.0+unknown"

__all__ = [
    "ATT_CONTROL_NOTIFY",
    "ATT_CONTROL_WRITE",
    "AUTH_NOTIFY",
    "AUTH_WRITE",
    "BULK_NOTIFY",
    "BULK_WRITE",
    "CONTROL_NOTIFY",
    "CONTROL_WRITE",
    "ATTPacket",
    "ControlRequest",
    "LockOperation",
    "LockOperationWrite",
    "VoiceVolumePreset",
    "VoiceVolumeWrite",
    "__version__",
    "aes128gcm_decrypt_body",
    "aes128gcm_encrypt_body",
    "build_cloud_auth_headers",
    "build_lock_operation_write",
    "build_voice_volume_write",
    "cloud_get_public_key",
    "cloud_verify",
    "compute_nonce",
    "compute_sign",
    "control_command_name",
    "encrypt_login_password",
    "get_session_material",
    "hkdf_expand",
    "hkdf_extract",
    "hkdf_sha256",
    "login",
    "make_local_signer",
    "normalize_lock_operation",
    "normalize_voice_volume_preset",
    "parse_control_request",
    "prepare_runtime_cloud_auth_headers",
    "send_lock_operation",
    "set_voice_volume",
    "valid_crc",
    "write_voice_volume",
]
