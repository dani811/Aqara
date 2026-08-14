"""High-level lock operations captured from real U200 sessions.

The operations in this module are plaintext command payloads observed in
runtime traces before the app encryption layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class LockOperation(str, Enum):
    """Observed operation payloads (plaintext, before AES-CCM session encryption).

    Confirmados descifrando el canal de control (ff61) con la sessionKey real y
    correlacionando por orden temporal con las pulsaciones de la app:
      - BLOQUEAR  -> 1f031f  (opcode 0x03; primera pulsacion capturada)
      - DESBLOQUEAR -> 200320 (opcode 0x03; segunda pulsacion capturada)
      - keepalive -> {ctr}01{ctr} con contador rotante (opcode 0x01)
    El byte central es el opcode; los 13.../33... son tramas de estado, no comandos.
    Todas se envian cifradas: control_write = write_prefix + AESCCM(sessionKey,nonce).
    """

    # Keepalive / status poll frame (opcode 0x01). El contador rota; 2f012f es una muestra.
    KEEPALIVE = "2f012f"
    # BLOQUEAR: comando de cierre confirmado (opcode 0x03).
    LOCK = "1f031f"
    # DESBLOQUEAR: comando de apertura confirmado (opcode 0x03).
    UNLOCK = "200320"
    # Alias historico: 1f031f resulto ser BLOQUEAR (no unlock).
    UNLOCK_CANDIDATE = "1f031f"
    # Extended state payload observed around control-page interactions.
    STATE_SNAPSHOT = "334e74746a201c00003049"


def normalize_lock_operation(value: LockOperation | str) -> LockOperation:
    if isinstance(value, LockOperation):
        return value

    normalized = value.strip().lower().replace("_", "-")
    aliases = {
        "keepalive": LockOperation.KEEPALIVE,
        "keep-alive": LockOperation.KEEPALIVE,
        "heartbeat": LockOperation.KEEPALIVE,
        "lock": LockOperation.LOCK,
        "bloquear": LockOperation.LOCK,
        "cerrar": LockOperation.LOCK,
        "unlock": LockOperation.UNLOCK,
        "desbloquear": LockOperation.UNLOCK,
        "abrir": LockOperation.UNLOCK,
        "unlock-candidate": LockOperation.UNLOCK_CANDIDATE,
        "snapshot": LockOperation.STATE_SNAPSHOT,
        "state-snapshot": LockOperation.STATE_SNAPSHOT,
        "estado": LockOperation.STATE_SNAPSHOT,
    }
    try:
        return aliases[normalized]
    except KeyError as exc:
        raise ValueError(f"operación no soportada: {value}") from exc


@dataclass(frozen=True)
class LockOperationWrite:
    operation: LockOperation
    payload: bytes
    write_prefix: int

    @property
    def hex_payload(self) -> str:
        return self.payload.hex()


class SessionOperationTransport(Protocol):
    def send_plaintext_operation(self, payload: bytes) -> None:
        """Send plaintext operation bytes through an authenticated session."""


def build_lock_operation_write(operation: LockOperation | str) -> LockOperationWrite:
    normalized = normalize_lock_operation(operation)
    prefix_by_operation = {
        LockOperation.KEEPALIVE: 0x01,
        LockOperation.LOCK: 0x03,
        LockOperation.UNLOCK: 0x03,
        LockOperation.STATE_SNAPSHOT: 0x01,
    }
    return LockOperationWrite(
        operation=normalized,
        payload=bytes.fromhex(normalized.value),
        write_prefix=prefix_by_operation[normalized],
    )


def send_lock_operation(
    transport: SessionOperationTransport,
    operation: LockOperation | str,
) -> LockOperationWrite:
    write = build_lock_operation_write(operation)
    transport.send_plaintext_operation(write.payload)
    return write
