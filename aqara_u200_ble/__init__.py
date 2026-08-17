"""Autonomous BLE control for the Aqara U200 smart lock.

Pure-Python reimplementation of the cloud KDF, the BLE authentication
handshake (frames ``0610``/``0710``) and the AES-CCM control channel. See
``docs/`` for the reverse-engineered protocol.

This package is assembled incrementally, one Spec Kit feature at a time. The
recommended entry point is the **feature 015 facade**: ``U200Client`` +
a ``Transport`` (``BleakTransport`` for the host radio, ``BumbleTransport`` for
an external ESP32-S3 HCI controller) + ``CloudAuthManager`` (account login with
automatic token refresh). The lower-level pieces (KDF, framing, session flow,
operations catalogue) remain public for advanced consumers.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from .auth import CloudAuthManager
from .bumble_transport import BumbleGattAdapter
from .client import OperationResult, U200Client
from .errors import AmbiguousDeviceError, FlowPhase, NoDeviceFoundError, U200ClientError
from .gatt import GattClient
from .kdf import (
    CloudServiceError,
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
    build_control_frame,
    build_control_query_write,
    build_lock_operation_write,
    build_operate_frame,
    normalize_lock_operation,
    send_lock_operation,
)
from .lock_state import LockState, decode_lock_state
from .models import MODEL_BY_PRODUCT_ID, decode_manufacturer_payload
from .operations_catalog import (
    OPERATIONS_CATALOG,
    CommandFamily,
    OperationEntry,
    OperationStatus,
    find_operation,
    operations_in_family,
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
from .scanner import identify_candidate, scan, select_preferred
from .session import (
    AUTH_NOTIFY_UUID,
    AUTH_SERVICE_UUID,
    AUTH_WRITE_UUID,
    AUX_NOTIFY_UUID,
    AUX_SERVICE_UUID,
    CONTROL_NOTIFY2_UUID,
    CONTROL_NOTIFY_UUID,
    CONTROL_SERVICE_UUID,
    CONTROL_WRITE_UUID,
    GATT_CACHING_PREAMBLE_UUID16,
    PRE_AUTH_NOTIFY_ORDER,
    OperationInProgressError,
    SessionMaterial,
    assemble_auth_fragments,
    build_auth_message,
    crc16_aqara,
    decrypt_control_payload,
    encrypt_control_payload,
    fragment_auth_message,
    parse_auth_message,
    run_authenticated_lock_operation,
)
from .transport import (
    AQARA_COMPANY_ID,
    EXPECTED_NAME,
    U200_SERVICE_UUIDS,
    BleakTransport,
    BumbleTransport,
    ScanCandidate,
    Transport,
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
    "AQARA_COMPANY_ID",
    "ATT_CONTROL_NOTIFY",
    "ATT_CONTROL_WRITE",
    "AUTH_NOTIFY",
    "AUTH_NOTIFY_UUID",
    "AUTH_SERVICE_UUID",
    "AUTH_WRITE",
    "AUTH_WRITE_UUID",
    "AUX_NOTIFY_UUID",
    "AUX_SERVICE_UUID",
    "BULK_NOTIFY",
    "BULK_WRITE",
    "CONTROL_NOTIFY",
    "CONTROL_NOTIFY2_UUID",
    "CONTROL_NOTIFY_UUID",
    "CONTROL_SERVICE_UUID",
    "CONTROL_WRITE",
    "CONTROL_WRITE_UUID",
    "EXPECTED_NAME",
    "GATT_CACHING_PREAMBLE_UUID16",
    "MODEL_BY_PRODUCT_ID",
    "OPERATIONS_CATALOG",
    "PRE_AUTH_NOTIFY_ORDER",
    "U200_SERVICE_UUIDS",
    "ATTPacket",
    "AmbiguousDeviceError",
    "BleakTransport",
    "BumbleGattAdapter",
    "BumbleTransport",
    "CloudAuthManager",
    "CloudServiceError",
    "CommandFamily",
    "ControlRequest",
    "FlowPhase",
    "GattClient",
    "LockOperation",
    "LockOperationWrite",
    "LockState",
    "NoDeviceFoundError",
    "OperationEntry",
    "OperationInProgressError",
    "OperationResult",
    "OperationStatus",
    "ScanCandidate",
    "SessionMaterial",
    "Transport",
    "U200Client",
    "U200ClientError",
    "VoiceVolumePreset",
    "VoiceVolumeWrite",
    "__version__",
    "aes128gcm_decrypt_body",
    "aes128gcm_encrypt_body",
    "assemble_auth_fragments",
    "build_auth_message",
    "build_cloud_auth_headers",
    "build_control_frame",
    "build_control_query_write",
    "build_lock_operation_write",
    "build_operate_frame",
    "build_voice_volume_write",
    "cloud_get_public_key",
    "cloud_verify",
    "compute_nonce",
    "compute_sign",
    "control_command_name",
    "crc16_aqara",
    "decode_lock_state",
    "decode_manufacturer_payload",
    "decrypt_control_payload",
    "encrypt_control_payload",
    "encrypt_login_password",
    "find_operation",
    "fragment_auth_message",
    "get_session_material",
    "hkdf_expand",
    "hkdf_extract",
    "hkdf_sha256",
    "identify_candidate",
    "login",
    "make_local_signer",
    "normalize_lock_operation",
    "normalize_voice_volume_preset",
    "operations_in_family",
    "parse_auth_message",
    "parse_control_request",
    "prepare_runtime_cloud_auth_headers",
    "run_authenticated_lock_operation",
    "scan",
    "select_preferred",
    "send_lock_operation",
    "set_voice_volume",
    "valid_crc",
    "write_voice_volume",
]
