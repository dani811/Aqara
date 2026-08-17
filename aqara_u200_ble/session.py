"""Authenticated BLE session helpers for Aqara U200."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar

from .auth import CloudAuthManager
from .gatt import GattClient
from .kdf import (
    REGION_BASE_URLS,
    CloudServiceError,
    cloud_get_public_key,
    get_session_material,
)
from .lock_ops import LockOperation, LockOperationWrite, build_lock_operation_write

logger = logging.getLogger(__name__)

_T = TypeVar("_T")


class OperationInProgressError(RuntimeError):
    """Raised when run_authenticated_lock_operation() is called during another operation."""

    pass


def _debug_report(channel: str, data: bytes) -> None:
    """Log a frame from a report channel (ff64/ff92) under U200_DEBUG (feature 022).

    These channels carry the lock's REPORT_* pushes (status/events). The auth flow
    subscribes to them but historically discarded their payloads; logging them here
    is how we discover whether the lock reports state/position spontaneously.
    """

    if os.environ.get("U200_DEBUG"):
        print(f"[BLE] report {channel}: {data.hex()}", file=sys.stderr)


async def _run_cloud_phase(phase: str, fn: Callable[..., _T], /, **kwargs: Any) -> _T:
    """Run a blocking cloud call in a worker thread with whitelisted DEBUG logging.

    Only non-sensitive telemetry is logged (Feature 012 FR-008): the operation
    phase, its duration, the worker thread id, the outcome, and — on failure —
    the *type* of the exception. URLs, headers, request/response bodies, device
    ids, auth/session/crypto material and raw exception messages are never
    logged.
    """

    logger.debug("cloud phase %s: started", phase)
    started = time.perf_counter()
    # Capture the worker thread id from INSIDE the worker execution context: after
    # the await we are back on the event-loop thread, so reading get_ident() there
    # would report the loop, not the worker (issue #3). Only this non-sensitive
    # integer crosses back for telemetry.
    worker_ident: dict[str, int] = {}

    def _traced(**call_kwargs: Any) -> _T:
        worker_ident["id"] = threading.get_ident()
        return fn(**call_kwargs)

    try:
        result = await asyncio.to_thread(_traced, **kwargs)
    except BaseException as exc:  # log the type only, then re-raise unchanged
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.debug(
            "cloud phase %s: failed after %.0f ms (%s)",
            phase,
            elapsed_ms,
            type(exc).__name__,
        )
        raise
    elapsed_ms = (time.perf_counter() - started) * 1000
    logger.debug(
        "cloud phase %s: completed in %.0f ms (worker thread %d)",
        phase,
        elapsed_ms,
        worker_ident.get("id", -1),
    )
    return result


AUTH_SERVICE_UUID = "0000fcb9-0000-1000-8000-00805f9b34fb"
AUTH_WRITE_UUID = "0000ff07-0000-1000-8000-00805f9b34fb"
AUTH_NOTIFY_UUID = "0000ff08-0000-1000-8000-00805f9b34fb"
CONTROL_SERVICE_UUID = "0000ff60-2333-5b1e-9d7c-c687fd2f04f2"
CONTROL_WRITE_UUID = "0000ff61-2333-5b1e-9d7c-c687fd2f04f2"
CONTROL_NOTIFY_UUID = "0000ff62-2333-5b1e-9d7c-c687fd2f04f2"
# Notificaciones secundarias (svc ff60): la app las habilita antes del auth.
CONTROL_NOTIFY2_UUID = "0000ff64-2333-5b1e-9d7c-c687fd2f04f2"
AUX_SERVICE_UUID = "0000ff90-2333-5b1e-9d7c-c687fd2f04f2"
AUX_NOTIFY_UUID = "0000ff92-2333-5b1e-9d7c-c687fd2f04f2"

# Preámbulo GATT estándar de Bluetooth 5.1+ ("Robust Caching", Vol 3 Part G):
# Read By Type de Appearance (0x2A01) y Database Hash (0x2B2A). Confirmado
# por captura HCI real (2026-08-11) que la app/Android SIEMPRE hace estas dos
# lecturas justo tras el MTU exchange y ANTES de escribir la clave pública
# (0610). Es lo que durante meses se documentó como "lectura del handle
# 0x0006" sin saber qué era: no es un secreto de Aqara, es que el handle 0x0006
# resulta ser donde vive el Database Hash EN ESTA CERRADURA (el handle en sí
# no es estable; se resuelve por UUID, no a pelo). bleak no expone esta
# primitiva (Read By Type genérico); Bumble sí, vía
# Client.read_characteristics_by_uuid. Adaptadores que no la soporten
# simplemente se saltan este paso (best-effort, ver
# run_authenticated_lock_operation).
GATT_CACHING_PREAMBLE_UUID16 = (0x2A01, 0x2B2A)  # Appearance, Database Hash

# HIPOTESIS PROBADA Y DESCARTADA (2026-08-12b): el preambulo de arriba solo
# REPLICA LA LECTURA de Database Hash, pero nunca escribia `Client Supported
# Features` (0x2B29) -- la otra mitad del mecanismo de "Robust Caching"
# (Bluetooth Core Vol 3 Part G Sec 2.5.2; ver tambien la doc de Silicon Labs
# -el MISMO fabricante del SoC EFR32MG24 de la cerradura- en
# docs.silabs.com/bluetooth/.../gatt-caching). Una fuente AOSP real (commit de
# packages/modules/Bluetooth) confirma que Android "reads Server Supported
# Features and writes Client supported features after discovery" de forma
# AUTOMATICA a nivel de plataforma, fuera del control de cualquier app.
# Encajaba con todos los hechos observados (Android real funciona, macOS/
# bleak y ESP32/Bumble fallan igual) sin requerir secreto de vinculacion.
# PROBADO EN VIVO contra la cerradura real: la escritura se confirma (sin
# error, característica localizada y escrita), pero el ACK vacío PERSISTE
# idéntico (`000610ffff0000...`, body_len=0). DESCARTADO como causa única del
# muro. Se deja implementado (best-effort, no hace daño y es spec-compliant)
# por si combinado con otra pieza aporta algo, pero no es la solucion. Ver
# docs/ble-control-handoff.md §11.7 para el detalle completo y los siguientes
# candidatos.
CLIENT_SUPPORTED_FEATURES_UUID16 = 0x2B29
CLIENT_SUPPORTED_FEATURES_ROBUST_CACHING_BIT = 0x01

# LE Data Length Change visto en el HCI snoop real justo tras el MTU exchange
# (subevent 0x07), ANTES del preambulo GATT caching. Valores exactos del lado
# del telefono en esa sesion: max_tx_octets=27/max_tx_time=328,
# max_rx_octets=251/max_rx_time=2120 (asimetrico: tx queda en el valor
# default sin extender, rx si se extiende). Se pide el valor RX (extendido)
# como tx_octets/tx_time propios al llamar set_data_length, que es lo mas
# parecido a "pedir la extension" desde el lado central. Sin confirmar aun
# si esto es necesario o si el propio controlador ya lo hace solo. Ver
# docs/ble-control-handoff.md §8.
DATA_LENGTH_TX_OCTETS = 251
DATA_LENGTH_TX_TIME = 2120

# LE Connection Update visto en el HCI snoop real justo despues del preambulo
# GATT y ANTES de las CCCD: intervalo 36->12 (unidades de 1.25ms = 45ms->15ms),
# latencia 0, supervision_timeout 400 (unidades de 10ms = 4000ms). Ver
# docs/ble-control-handoff.md §6.6 (sospechoso siguiente, sin confirmar aun
# si esto es necesario para que la cerradura responda con su pubkey real).
POST_AUTH_CONNECTION_INTERVAL_MS = 15.0
POST_AUTH_CONNECTION_LATENCY = 0
POST_AUTH_SUPERVISION_TIMEOUT_MS = 4000.0

# Orden EXACTO en el que la app habilita CCCD antes de mandar la clave pública
# (confirmado por captura real, ver docs/protocolo.md "Secuencia completa de
# conexión").
PRE_AUTH_NOTIFY_ORDER = (
    CONTROL_NOTIFY_UUID,  # ff62
    CONTROL_NOTIFY2_UUID,  # ff64
    AUX_NOTIFY_UUID,  # ff92
    AUTH_NOTIFY_UUID,  # ff08
)


@dataclass(frozen=True)
class SessionMaterial:
    session_key_hex: str
    nonce_hex: str
    verify_data_hex: str
    lock_public_key_hex: str


@dataclass(frozen=True)
class AuthMessage:
    frame_type: int
    app_token: int
    lock_token: int
    body: bytes


# Per-device concurrency tracking: one flag per device_id to prevent concurrent
# run_authenticated_lock_operation() calls on the same lock.
# Feature 012: Cloud I/O Async-Safe (fail-fast concurrency control)
_device_operation_in_progress: dict[str, bool] = {}


# Tabla CRC-16/ARC (poly 0x8005 reflejado = 0xA001, init 0x0000) — extraída
# LITERAL del módulo Hermes `CrcUtils.ts` de la app (getCrc16String usa esta
# tabla exacta con el bucle reflejado `crc = (crc>>8) ^ tabla[(crc^b)&0xff]`).
# 2026-08-15: ESTE es el muro. El campo de 2 bytes del header del 0610/0710
# NO era un "app_token aleatorio" (asunción errónea de todo el proyecto) —
# es el CRC-16 de `body`, en little-endian. Verificado 130/133 contra el
# btsnoop real (los 3 fallos son artefactos de reensamblado de fragmentos).
# Mandarlo aleatorio hacía que el lock respondiera SIEMPRE status 01 (ACK
# vacío sin pubkey). Ver docs/ble-control-handoff.md §11.58.
# Frozen protocol data (Constitution Article V): kept in its captured
# 16-per-row shape so it stays diffable against the app's table. One value
# per line would be 256 lines of noise that hides any future tampering.
# fmt: off
_CRC16_TABLE = (
    0, 49345, 49537, 320, 49921, 960, 640, 49729, 50689, 1728, 1920, 51009,
    1280, 50625, 50305, 1088, 52225, 3264, 3456, 52545, 3840, 53185, 52865,
    3648, 2560, 51905, 52097, 2880, 51457, 2496, 2176, 51265, 55297, 6336,
    6528, 55617, 6912, 56257, 55937, 6720, 7680, 57025, 57217, 8000, 56577,
    7616, 7296, 56385, 5120, 54465, 54657, 5440, 55041, 6080, 5760, 54849,
    53761, 4800, 4992, 54081, 4352, 53697, 53377, 4160, 61441, 12480, 12672,
    61761, 13056, 62401, 62081, 12864, 13824, 63169, 63361, 14144, 62721,
    13760, 13440, 62529, 15360, 64705, 64897, 15680, 65281, 16320, 16000,
    65089, 64001, 15040, 15232, 64321, 14592, 63937, 63617, 14400, 10240,
    59585, 59777, 10560, 60161, 11200, 10880, 59969, 60929, 11968, 12160,
    61249, 11520, 60865, 60545, 11328, 58369, 9408, 9600, 58689, 9984, 59329,
    59009, 9792, 8704, 58049, 58241, 9024, 57601, 8640, 8320, 57409, 40961,
    24768, 24960, 41281, 25344, 41921, 41601, 25152, 26112, 42689, 42881,
    26432, 42241, 26048, 25728, 42049, 27648, 44225, 44417, 27968, 44801,
    28608, 28288, 44609, 43521, 27328, 27520, 43841, 26880, 43457, 43137,
    26688, 30720, 47297, 47489, 31040, 47873, 31680, 31360, 47681, 48641,
    32448, 32640, 48961, 32000, 48577, 48257, 31808, 46081, 29888, 30080,
    46401, 30464, 47041, 46721, 30272, 29184, 45761, 45953, 29504, 45313,
    29120, 28800, 45121, 20480, 37057, 37249, 20800, 37633, 21440, 21120,
    37441, 38401, 22208, 22400, 38721, 21760, 38337, 38017, 21568, 39937,
    23744, 23936, 40257, 24320, 40897, 40577, 24128, 23040, 39617, 39809,
    23360, 39169, 22976, 22656, 38977, 34817, 18624, 18816, 35137, 19200,
    35777, 35457, 19008, 19968, 36545, 36737, 20288, 36097, 19904, 19584,
    35905, 17408, 33985, 34177, 17728, 34561, 18368, 18048, 34369, 33281,
    17088, 17280, 33601, 16640, 33217, 32897, 16448,
)
# fmt: on


def crc16_aqara(data: bytes) -> int:
    """CRC-16 exacto de la app (getCrc16String de CrcUtils.ts). Devuelve el
    valor entero; en la trama va en little-endian."""
    crc = 0
    for b in data:
        crc = (crc >> 8) ^ _CRC16_TABLE[(crc ^ b) & 0xFF]
        crc &= 0xFFFF
    return crc


def build_auth_message(
    frame_type: int,
    *,
    body: bytes,
    app_token: int | None = None,  # IGNORADO: se conserva por compatibilidad.
    lock_token: int = 0,
) -> bytes:
    if frame_type not in (0x06, 0x07):
        raise ValueError(f"frame_type no soportado: {frame_type:#x}")
    header = bytearray(18)
    header[0] = 0x00
    header[1] = frame_type
    header[2] = 0x10
    header[3] = 0x01
    header[4] = 0x00
    header[5:7] = len(body).to_bytes(2, "little")
    # header[7:9] = CRC-16 del body (NO un token aleatorio). Ver _CRC16_TABLE.
    header[7:9] = crc16_aqara(body).to_bytes(2, "little")
    header[9:11] = lock_token.to_bytes(2, "little")
    return bytes(header) + body


def fragment_auth_message(payload: bytes, direction: int = 0x5A) -> list[bytes]:
    if direction not in (0x5A, 0xDA):
        raise ValueError(f"dirección de fragmento no soportada: {direction:#x}")
    chunks = [payload[i : i + 18] for i in range(0, len(payload), 18)] or [b""]
    fragments: list[bytes] = []
    for index, chunk in enumerate(chunks):
        seq = 0xFF if index == len(chunks) - 1 else index
        fragments.append(bytes((direction, seq)) + chunk)
    return fragments


def assemble_auth_fragments(fragments: list[bytes], expected_direction: int) -> bytes:
    if not fragments:
        raise ValueError("no hay fragmentos para ensamblar")
    payload_parts: list[bytes] = []
    for index, fragment in enumerate(fragments):
        if len(fragment) < 2:
            raise ValueError("fragmento de auth demasiado corto")
        direction = fragment[0]
        seq = fragment[1]
        if direction != expected_direction:
            raise ValueError(
                f"dirección inesperada en auth: {direction:#x} != {expected_direction:#x}"
            )
        if index < len(fragments) - 1 and seq != index:
            raise ValueError(f"secuencia auth inesperada: {seq:#x} != {index:#x}")
        payload_parts.append(fragment[2:])
    return b"".join(payload_parts)


def parse_auth_message(message: bytes) -> AuthMessage:
    if len(message) < 18:
        raise ValueError("mensaje auth incompleto")
    frame_type = message[1]
    body_length = int.from_bytes(message[5:7], "little")
    app_token = int.from_bytes(message[7:9], "little")
    lock_token = int.from_bytes(message[9:11], "little")
    body = message[18 : 18 + body_length]
    if len(body) != body_length:
        raise ValueError("longitud de body auth no coincide")
    return AuthMessage(
        frame_type=frame_type,
        app_token=app_token,
        lock_token=lock_token,
        body=body,
    )


def encrypt_control_payload(
    session_key_hex: str,
    nonce_hex: str,
    *,
    plaintext: bytes,
) -> bytes:
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESCCM  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "Falta la dependencia opcional 'cryptography' para cifrado AES-CCM."
        ) from exc
    aes = AESCCM(bytes.fromhex(session_key_hex), tag_length=4)
    return aes.encrypt(bytes.fromhex(nonce_hex), plaintext, b"")


def decrypt_control_payload(
    session_key_hex: str,
    nonce_hex: str,
    *,
    ciphertext: bytes,
) -> bytes:
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESCCM  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "Falta la dependencia opcional 'cryptography' para descifrado AES-CCM."
        ) from exc
    aes = AESCCM(bytes.fromhex(session_key_hex), tag_length=4)
    return aes.decrypt(bytes.fromhex(nonce_hex), ciphertext, b"")


async def run_authenticated_lock_operation(
    *,
    client: GattClient,
    device_id: str,
    auth_headers: dict[str, str] | None,
    region: str,
    base_url: str | None,
    operation: LockOperation | str | LockOperationWrite,
    notify_timeout: float = 8.0,
    signer: Any = None,
    auth: CloudAuthManager | None = None,
) -> tuple[SessionMaterial, LockOperationWrite, str | None]:
    """
    Authenticate with the lock, send a command, and receive the response.

    Credential mechanisms (provide at most one; passing **both is an error**):

    - ``auth``: a :class:`CloudAuthManager` (built by the consumer from its own
      secure credential storage). The flow logs in on demand, keeps the token in
      memory, and — if a cloud call fails with ``code 108`` (token expired) **before
      the actuator command is sent** — re-authenticates and re-runs the whole
      operation once (Feature 014). A ``code 810`` (bad credentials) or any error
      after actuation is never retried.
    - ``signer``: a pre-built static signer (legacy path, no auto-refresh). If
      neither is given, the legacy behaviour is preserved (the ``None`` signer is
      passed through, as before Feature 014).

    The token and credentials are never persisted or logged.
    """
    if signer is not None and auth is not None:
        raise ValueError(
            "run_authenticated_lock_operation accepts `signer` (static token) or "
            "`auth` (CloudAuthManager for auto-login), not both."
        )

    if auth is not None:
        active_signer: Any = await _run_cloud_phase("login", auth.build_signer)
    else:
        active_signer = signer

    max_reauth = 1 if auth is not None else 0
    for attempt in range(max_reauth + 1):
        actuation_state: dict[str, bool] = {"done": False}
        try:
            return await _run_authenticated_lock_operation_once(
                client=client,
                device_id=device_id,
                auth_headers=auth_headers,
                region=region,
                base_url=base_url,
                operation=operation,
                notify_timeout=notify_timeout,
                signer=active_signer,
                actuation_state=actuation_state,
            )
        except CloudServiceError as exc:
            can_retry = (
                auth is not None
                and exc.is_code(108)
                and not actuation_state["done"]
                and attempt < max_reauth
            )
            if not can_retry:
                raise
            assert auth is not None  # narrowed by can_retry
            active_signer = await _run_cloud_phase(
                "login_refresh", auth.build_signer, force_refresh=True
            )

    raise RuntimeError("run_authenticated_lock_operation: retry loop exhausted")


async def _run_authenticated_lock_operation_once(
    *,
    client: GattClient,
    device_id: str,
    auth_headers: dict[str, str] | None,
    region: str,
    base_url: str | None,
    operation: LockOperation | str | LockOperationWrite,
    notify_timeout: float = 8.0,
    signer: Any = None,
    actuation_state: dict[str, bool],
) -> tuple[SessionMaterial, LockOperationWrite, str | None]:
    """
    Single attempt of the authenticated lock operation (see the public wrapper
    ``run_authenticated_lock_operation``). ``actuation_state["done"]`` is set to
    True immediately before the control (actuator) write so the wrapper can avoid
    retrying after the lock may have moved.

    Authenticate with lock, send command, and receive response (async-safe).

    Cloud I/O (key derivation, session material) executes in worker threads
    via asyncio.to_thread(), keeping the event loop responsive. BLE operations
    remain on the caller's event loop.

    Args:
        client: BLE GATT client for read/write operations
        device_id: Lock device identifier for cloud KDF and concurrency tracking
        auth_headers: Optional HTTP headers for cloud requests
        region: Cloud region (e.g., "EU", "CN")
        base_url: Optional custom cloud endpoint
        operation: Lock operation (e.g., "unlock", "lock")
        notify_timeout: Seconds to wait for control response (default 8.0)
        signer: Optional cloud request signer (e.g., RSA key for Akamai)

    Returns:
        tuple of:
            - SessionMaterial: Session keys, nonce, verify data, lock public key
            - LockOperationWrite: Operation details and encrypted payload
            - str | None: Decrypted control response hex, or None if timeout

    Raises:
        OperationInProgressError: Another operation is in progress on this device
        RuntimeError: Cloud call failure, BLE protocol violation, or crypto error
        asyncio.TimeoutError: BLE notification timeout

    Feature 012: Cloud I/O Async-Safe
        - Per-device concurrency control (fail-fast, non-blocking)
        - Cloud calls execute in worker threads (never block event loop)
        - Exceptions propagate unwrapped (original type preserved)
        - No credentials/keys logged (FR-008 compliance)
    """
    # Feature 012: Per-device concurrency control (T005+T006)
    # Fail-fast check: if operation already in progress for this device, reject immediately
    if _device_operation_in_progress.get(device_id, False):
        raise OperationInProgressError(
            f"Another lock operation is in progress for device {device_id}"
        )

    # Mark operation as in progress
    _device_operation_in_progress[device_id] = True

    try:
        auth_queue: asyncio.Queue[bytes] = asyncio.Queue()
        control_queue: asyncio.Queue[bytes] = asyncio.Queue()

        def on_auth_fragment(_: object, data: bytearray) -> None:
            auth_queue.put_nowait(bytes(data))

        def on_control_fragment(_: object, data: bytearray) -> None:
            control_queue.put_nowait(bytes(data))

        async def write_auth_message(message_payload: bytes) -> None:
            # ff07 es write-SIN-respuesta (write-with-response da "Not Permitted").
            # Sin pausa, CoreBluetooth pierde fragmentos y el lock recibe la clave
            # incompleta -> responde body vacio. La pausa asegura la entrega ordenada.
            for fragment in fragment_auth_message(message_payload, direction=0x5A):
                await client.write_gatt_char(AUTH_WRITE_UUID, fragment, response=False)
                await asyncio.sleep(0.04)

        async def read_full_auth_message() -> bytes:
            fragments: list[bytes] = []
            while True:
                fragment = await asyncio.wait_for(auth_queue.get(), timeout=notify_timeout)
                if not fragment:
                    continue
                fragments.append(fragment)
                if fragment[1] == 0xFF:
                    return assemble_auth_fragments(fragments, expected_direction=0xDA)

        def on_report_notify(channel: str) -> Callable[[object, bytearray], None]:
            # ff64/ff92 carry the lock's REPORT_* pushes. We enable them because the
            # app does (PRE_AUTH_NOTIFY_ORDER); previously their payloads were
            # discarded. Capture them under U200_DEBUG to learn if the lock reports
            # state/position spontaneously (feature 022).
            def handler(_: object, data: bytearray) -> None:
                _debug_report(channel, bytes(data))

            return handler

        callback_by_notify_uuid = {
            CONTROL_NOTIFY_UUID: on_control_fragment,
            CONTROL_NOTIFY2_UUID: on_report_notify("ff64"),
            AUX_NOTIFY_UUID: on_report_notify("ff92"),
            AUTH_NOTIFY_UUID: on_auth_fragment,
        }

        async def enable_cccd_in_app_order() -> None:
            """Habilita CCCD en el orden EXACTO capturado de la app: ff62, ff64,
            ff92, ff08 (ver PRE_AUTH_NOTIFY_ORDER). Tolera fallos por-característica
            (algunos transportes ya tienen el CCCD activo o no exponen esa char)."""
            for uuid in PRE_AUTH_NOTIFY_ORDER:
                try:
                    if os.environ.get("U200_DEBUG"):
                        print(f"[BLE] enabling CCCD for {uuid[-4:]}", file=sys.stderr)
                    await client.start_notify(uuid, callback_by_notify_uuid[uuid])
                    await asyncio.sleep(0.02)
                except Exception as exc:
                    if os.environ.get("U200_DEBUG"):
                        print(f"[BLE] CCCD enable failed for {uuid[-4:]}: {exc}", file=sys.stderr)

        async def request_remote_le_features() -> None:
            """HCI LE Read Remote Features -- ver
            bumble_transport.py::get_remote_le_features para la evidencia
            (btsnoop real, 2026-08-13). Best-effort; bleak no lo expone."""
            get_features = getattr(client, "get_remote_le_features", None)
            if get_features is None:
                if os.environ.get("U200_DEBUG"):
                    print("[BLE] adaptador sin get_remote_le_features; se omite", file=sys.stderr)
                return
            try:
                features = await get_features()
                if os.environ.get("U200_DEBUG"):
                    print(f"[BLE] LE Read Remote Features -> 0x{features:016x}", file=sys.stderr)
            except Exception as exc:
                if os.environ.get("U200_DEBUG"):
                    print(f"[BLE] LE Read Remote Features fallo: {exc}", file=sys.stderr)

        async def request_att_mtu() -> None:
            """ATT Exchange MTU Request -- PRIMER paso real tras conectar, ANTES
            de todo lo demas (ver docs/ble-control-handoff.md §3 paso 2). Es la
            UNICA pieza de la secuencia pre-auth que este proyecto nunca habia
            reproducido con exito (un intento anterior colgo Bumble y se
            abandono sin reintentar, ver §6.3 y bumble_transport.py::request_mtu).
            Best-effort con timeout corto propio; bleak no expone esto (el SO
            decide) asi que se salta sin romper nada en ese adaptador."""
            request_mtu = getattr(client, "request_mtu", None)
            if request_mtu is None:
                if os.environ.get("U200_DEBUG"):
                    print("[BLE] adaptador sin request_mtu; se omite", file=sys.stderr)
                return
            try:
                negotiated = await request_mtu(247)
                if os.environ.get("U200_DEBUG"):
                    print(f"[BLE] ATT MTU negociado: {negotiated}", file=sys.stderr)
            except Exception as exc:
                if os.environ.get("U200_DEBUG"):
                    print(f"[BLE] ATT MTU exchange fallo: {exc}", file=sys.stderr)

        async def request_data_length_extension() -> None:
            """Replica el LE Data Length Change real, visto justo tras el MTU
            exchange y ANTES del preambulo GATT caching (ver
            DATA_LENGTH_TX_OCTETS/_TIME). Best-effort: bleak no expone esto (lo
            decide el SO); solo adaptadores de bajo nivel como Bumble pueden
            pedirlo explicitamente."""
            set_data_length = getattr(client, "set_data_length", None)
            if set_data_length is None:
                if os.environ.get("U200_DEBUG"):
                    print(
                        "[BLE] adaptador sin set_data_length; se omite",
                        file=sys.stderr,
                    )
                return
            try:
                await set_data_length(tx_octets=DATA_LENGTH_TX_OCTETS, tx_time=DATA_LENGTH_TX_TIME)
                if os.environ.get("U200_DEBUG"):
                    print(
                        f"[BLE] data length extension solicitada: "
                        f"tx_octets={DATA_LENGTH_TX_OCTETS} tx_time={DATA_LENGTH_TX_TIME}",
                        file=sys.stderr,
                    )
            except Exception as exc:
                if os.environ.get("U200_DEBUG"):
                    print(f"[BLE] data length extension fallo: {exc}", file=sys.stderr)

        async def run_gatt_caching_preamble() -> None:
            """Read By Type de Appearance (0x2A01) y Database Hash (0x2B2A),
            exactamente como hace Android antes de escribir la pubkey (ver
            GATT_CACHING_PREAMBLE_UUID16). Best-effort: el adaptador bleak
            estandar no expone read_by_type, asi que se salta sin romper nada."""
            read_by_type = getattr(client, "read_by_type", None)
            if read_by_type is None:
                if os.environ.get("U200_DEBUG"):
                    print(
                        "[BLE] adaptador sin read_by_type; se omite el preambulo "
                        "de GATT caching (0x2A01/0x2B2A)",
                        file=sys.stderr,
                    )
                return
            for uuid16 in GATT_CACHING_PREAMBLE_UUID16:
                try:
                    values = await read_by_type(uuid16)
                    if os.environ.get("U200_DEBUG"):
                        hexvals = [bytes(v).hex() for v in values]
                        print(f"[BLE] Read By Type 0x{uuid16:04x} -> {hexvals}", file=sys.stderr)
                except Exception as exc:
                    if os.environ.get("U200_DEBUG"):
                        print(f"[BLE] Read By Type 0x{uuid16:04x} fallo: {exc}", file=sys.stderr)

        async def write_client_supported_features() -> None:
            """Escribe el bit Robust Caching en Client Supported Features (0x2B29)
            -- ver CLIENT_SUPPORTED_FEATURES_UUID16 arriba para la hipotesis y las
            fuentes. Best-effort: solo adaptadores de bajo nivel (Bumble) exponen
            write_by_type; bleak/CoreBluetooth no lo necesitan porque el propio
            SO ya lo hace por su cuenta."""
            write_by_type = getattr(client, "write_by_type", None)
            if write_by_type is None:
                if os.environ.get("U200_DEBUG"):
                    print(
                        "[BLE] adaptador sin write_by_type; se omite Client "
                        "Supported Features (0x2B29)",
                        file=sys.stderr,
                    )
                return
            try:
                await write_by_type(
                    CLIENT_SUPPORTED_FEATURES_UUID16,
                    bytes((CLIENT_SUPPORTED_FEATURES_ROBUST_CACHING_BIT,)),
                )
                if os.environ.get("U200_DEBUG"):
                    print(
                        "[BLE] Client Supported Features (0x2B29) <- Robust Caching bit escrito",
                        file=sys.stderr,
                    )
            except Exception as exc:
                if os.environ.get("U200_DEBUG"):
                    msg = f"[BLE] Client Supported Features write failed: {exc}"
                    print(msg, file=sys.stderr)

        async def request_connection_update() -> None:
            """Replica el LE Connection Update real (45ms->15ms) visto justo tras
            el preambulo GATT y antes de las CCCD. Best-effort: bleak no expone
            esto (el SO decide los parametros de conexion); solo Bumble/adaptadores
            de bajo nivel pueden pedirlo explicitamente."""
            update = getattr(client, "update_connection_parameters", None)
            if update is None:
                if os.environ.get("U200_DEBUG"):
                    print(
                        "[BLE] adaptador sin update_connection_parameters; se omite",
                        file=sys.stderr,
                    )
                return
            try:
                await update(
                    interval_ms=POST_AUTH_CONNECTION_INTERVAL_MS,
                    latency=POST_AUTH_CONNECTION_LATENCY,
                    supervision_timeout_ms=POST_AUTH_SUPERVISION_TIMEOUT_MS,
                )
                if os.environ.get("U200_DEBUG"):
                    print(
                        f"[BLE] connection update solicitado: "
                        f"interval={POST_AUTH_CONNECTION_INTERVAL_MS}ms",
                        file=sys.stderr,
                    )
            except Exception as exc:
                if os.environ.get("U200_DEBUG"):
                    print(f"[BLE] connection update fallo: {exc}", file=sys.stderr)

        await request_remote_le_features()
        await request_att_mtu()
        # request_data_length_extension() -- RETIRADO de la secuencia activa
        # 2026-08-13: verificado contra el btsnoop de hoy (frame 161047, evento
        # LE Data Length Change) que el HOST del movil NUNCA manda el comando
        # HCI "LE Set Data Length" para la conexion con la cerradura (se
        # comprobaron las 5 apariciones de ese comando en todo el archivo -- las
        # 5 son para OTROS connection_handle, ninguna para el de la cerradura).
        # La extension de longitud (27/251) ocurre sola, a nivel de controlador
        # (iniciada por el propio periferico), sin intervencion del host. Es
        # otra operacion "de mas" que hariamos nosotros y el movil real no hace
        # -- igual que Client Supported Features (§11.7). Se deja la funcion
        # definida por si hace falta en un adaptador que SI la necesite.
        await run_gatt_caching_preamble()
        # write_client_supported_features() -- RETIRADO de la secuencia activa
        # 2026-08-13: un btsnoop fresco (bugreport de hoy) confirma que Android
        # NO escribe 0x2B29 contra esta cerradura en absoluto -- 4 Write Request
        # totales en toda la fase pre-auth, los 4 son CCCD (0x0034/0x0039/0x003f/
        # 0x0023), ninguno a Client Supported Features. La funcion se deja
        # definida (ver docs/ble-control-handoff.md §11.7/§11.12) por si hace
        # falta reactivarla, pero mandarla es una operacion EXTRA que el flujo
        # real no hace -- se quita para que la secuencia sea un espejo exacto.
        await request_connection_update()
        await enable_cccd_in_app_order()
        try:
            resolved_base_url = base_url or REGION_BASE_URLS.get(region, REGION_BASE_URLS["EU"])
            cloud_public_key_hex = await _run_cloud_phase(
                "cloud_get_public_key",
                cloud_get_public_key,
                device_id=device_id,
                auth_headers=auth_headers,
                base_url=resolved_base_url,
                signer=signer,
            )
            app_token_key = int.from_bytes(os.urandom(2), "little")
            await write_auth_message(
                build_auth_message(
                    0x06,
                    body=bytes.fromhex(cloud_public_key_hex),
                    app_token=app_token_key,
                )
            )

            # La cerradura responde primero con un ACK 0x06 sin cuerpo y DESPUES envia
            # su clave publica efimera (65 bytes) en otro frame 0x06. Leemos hasta
            # obtener un 0x06 con cuerpo (la clave), tolerando ACKs vacios.
            if os.environ.get("U200_DEBUG"):
                print(f"[BLE] cloudPubKey={cloud_public_key_hex}", file=sys.stderr)
            lock_key_message = None
            for _ in range(6):
                lock_key_raw = await read_full_auth_message()
                msg = parse_auth_message(lock_key_raw)
                if os.environ.get("U200_DEBUG"):
                    print(
                        f"[BLE] frame type={msg.frame_type:#x} body_len={len(msg.body)} "
                        f"raw={lock_key_raw.hex()}",
                        file=sys.stderr,
                    )
                if msg.frame_type == 0x06 and len(msg.body) >= 33:
                    lock_key_message = msg
                    break
            if lock_key_message is None:
                raise RuntimeError(
                    "no se recibio la clave publica del lock (solo ACKs vacios); "
                    "reintenta con la cerradura despierta."
                )

            session = await _run_cloud_phase(
                "get_session_material",
                get_session_material,
                device_id=device_id,
                device_public_key_hex=lock_key_message.body.hex(),
                auth_headers=auth_headers,
                region=region,
                base_url=resolved_base_url,
                signer=signer,
            )

            app_token_verify = int.from_bytes(os.urandom(2), "little")
            await write_auth_message(
                build_auth_message(
                    0x07,
                    body=bytes.fromhex(session["verifyData"]),
                    app_token=app_token_verify,
                )
            )
            auth_ack_raw = await read_full_auth_message()
            auth_ack = parse_auth_message(auth_ack_raw)
            if auth_ack.frame_type != 0x07:
                raise RuntimeError(f"se esperaba ACK auth 0x07 y llegó {auth_ack.frame_type:#x}")

            write = build_lock_operation_write(operation)
            encrypted_payload = encrypt_control_payload(
                session["sessionKey"],
                session["nonce"],
                plaintext=write.payload,
            )
            control_write = bytes((write.write_prefix,)) + encrypted_payload
            # Point of no return: from here the lock may actuate, so the wrapper
            # must NOT retry/reauth even on a late token error (FR-016).
            actuation_state["done"] = True
            await client.write_gatt_char(CONTROL_WRITE_UUID, control_write, response=False)

            decrypted_response_hex: str | None = None
            try:
                control_frame = await asyncio.wait_for(control_queue.get(), timeout=notify_timeout)
            except TimeoutError:
                control_frame = b""
            if control_frame:
                if len(control_frame) < 2:
                    raise RuntimeError("respuesta de control cifrada demasiado corta")
                decrypted_response_hex = decrypt_control_payload(
                    session["sessionKey"],
                    session["nonce"],
                    ciphertext=control_frame[1:],
                ).hex()

            material = SessionMaterial(
                session_key_hex=session["sessionKey"],
                nonce_hex=session["nonce"],
                verify_data_hex=session["verifyData"],
                lock_public_key_hex=lock_key_message.body.hex(),
            )
            return material, write, decrypted_response_hex
        finally:
            for uuid in PRE_AUTH_NOTIFY_ORDER:
                with contextlib.suppress(Exception):
                    await client.stop_notify(uuid)
    finally:
        # Feature 012: Release concurrency control flag
        _device_operation_in_progress[device_id] = False
