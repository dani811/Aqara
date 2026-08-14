"""High-level lock operations captured from real U200 sessions.

The operations in this module are plaintext command payloads observed in
runtime traces before the app encryption layer.

**Provenance of the actuation commands (feature 009, 2026-08-14).** UNLOCK and
LOCK are the *exact* plaintexts the official app hands to `AqEdUtils.encryptAESCCM`
when you press Open / Close, captured live with a Frida gadget and then replayed
successfully from our own autonomous session (the lock opened, reply `74007706`).
They start with `0x74` (`BLE_OPEN_LOCK`); the 2nd byte is the direction
(`01` = open, `00` = close). The old `1f031f` / `200320` values shipped earlier
were **never** the real actuators — the lock is silent to them — and are kept
below only as clearly-marked legacy, not used by any alias.

**Replay caveat.** These are captured payloads, replayed verbatim. We re-encrypt
them with our *own* fresh session key/nonce (so the AES-CCM is genuinely ours),
but we do not yet synthesise them: the 3rd byte looks like a per-command counter
(`01` seen on open, `02` on the next close) and the last two bytes are a trailer
(`b917` / `3a12`) whose algorithm is unresolved — no standard CRC-16 reproduces
both pairs. One command per fresh session works (the counter appears to reset per
session); multiple commands in one session, or a lock with strict cross-session
replay protection, would need the counter+trailer reversed. See
specs/009-lock-open-spike.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class LockOperation(str, Enum):
    """Observed operation payloads (plaintext, before AES-CCM session encryption).

    Actuation commands confirmed live (feature 009): captured from the app's
    `encryptAESCCM` input on a real button press and replayed to open the lock
    from our own session.
      - UNLOCK (open)  -> 74010100b917  (opcode 0x74, dir 0x01)
      - LOCK  (close)  -> 740002003a12  (opcode 0x74, dir 0x00)
    KEEPALIVE and STATE_SNAPSHOT were recovered from decrypted control traces.
    All are sent encrypted: control_write = write_prefix + AESCCM(sessionKey,nonce).
    """

    # Keepalive / status poll frame. The counter rotates; 2f012f is one sample.
    KEEPALIVE = "2f012f"
    # OPEN the lock — real captured command (BLE_OPEN_LOCK, dir 0x01). Replay.
    UNLOCK = "74010100b917"
    # CLOSE the lock — real captured command (BLE_OPEN_LOCK, dir 0x00). Replay.
    LOCK = "740002003a12"
    # Extended state payload observed around control-page interactions.
    STATE_SNAPSHOT = "334e74746a201c00003049"
    # LEGACY, NON-FUNCTIONAL: shipped as LOCK/UNLOCK before feature 009 but the
    # lock is silent to them — they are NOT the real actuators. Kept for
    # provenance only; no alias maps here.
    LEGACY_UNVERIFIED_1F031F = "1f031f"
    LEGACY_UNVERIFIED_200320 = "200320"


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
        "close": LockOperation.LOCK,
        "unlock": LockOperation.UNLOCK,
        "desbloquear": LockOperation.UNLOCK,
        "abrir": LockOperation.UNLOCK,
        "open": LockOperation.UNLOCK,
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
    # Every control frame in a real capture is written to ff61 with prefix 0x01
    # (short frames) — including the actuation commands (their ff61 write was
    # `01` + ciphertext). Legacy values are not dispatched.
    prefix_by_operation = {
        LockOperation.KEEPALIVE: 0x01,
        LockOperation.LOCK: 0x01,
        LockOperation.UNLOCK: 0x01,
        LockOperation.STATE_SNAPSHOT: 0x01,
    }
    try:
        prefix = prefix_by_operation[normalized]
    except KeyError as exc:
        raise ValueError(
            f"{normalized.name} is legacy/non-functional and is not dispatched; "
            f"use UNLOCK/LOCK (the real captured commands)."
        ) from exc
    return LockOperationWrite(
        operation=normalized,
        payload=bytes.fromhex(normalized.value),
        write_prefix=prefix,
    )


def send_lock_operation(
    transport: SessionOperationTransport,
    operation: LockOperation | str,
) -> LockOperationWrite:
    write = build_lock_operation_write(operation)
    transport.send_plaintext_operation(write.payload)
    return write
