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

**Command builder (trailer cracked, feature 009).** The frame is
``74 <dir> <seq:2 LE> <trailer:2 LE>`` where ``dir`` is ``01`` open / ``00``
close, ``seq`` is a 2-byte little-endian sequence, and the trailer is
**additive, not a CRC**: ``trailer = base_dir + seq`` (``base_open = 0x17b8``,
``base_close = 0x1238``). Cracked from nine live captures across a run of
presses — the trailer increments by exactly 1 with the sequence, which rules out
a CRC. ``build_operate_frame`` synthesises any command; ``UNLOCK`` / ``LOCK`` are
the ``seq=1`` case. The bases were derived from one device and could be
device-specific (unconfirmed on a second lock).
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
    # OPEN the lock — build_operate_frame(open=True, seq=1). Confirmed live.
    UNLOCK = "74010100b917"
    # CLOSE the lock — build_operate_frame(open=False, seq=1).
    LOCK = "740001003912"
    # Extended state payload observed around control-page interactions.
    STATE_SNAPSHOT = "334e74746a201c00003049"
    # LEGACY, NON-FUNCTIONAL: shipped as LOCK/UNLOCK before feature 009 but the
    # lock is silent to them — they are NOT the real actuators. Kept for
    # provenance only; no alias maps here.
    LEGACY_UNVERIFIED_1F031F = "1f031f"
    LEGACY_UNVERIFIED_200320 = "200320"


# Operate-command builder (feature 009). frame = 74 <dir> <seq:2 LE> <trailer:2 LE>
# with trailer = base_dir + seq (additive, not a CRC). Bases derived from live
# captures on one device; may be device-specific.
_OPERATE_OPCODE = 0x74
_OPERATE_BASE = {True: 0x17B8, False: 0x1238}  # open / close


def build_operate_frame(*, open: bool, seq: int = 1) -> bytes:
    """Synthesise the plaintext for an open/close command with any sequence.

    ``open=True`` opens the bolt, ``open=False`` closes it. ``seq`` is the 2-byte
    little-endian sequence number (the lock does not validate it across sessions,
    so ``seq=1`` per fresh session is fine). The trailer is ``base_dir + seq``.
    """
    if not 0 <= seq <= 0xFFFF:
        raise ValueError("seq must fit in 2 bytes (0..65535)")
    direction = 0x01 if open else 0x00
    trailer = (_OPERATE_BASE[open] + seq) & 0xFFFF
    return (
        bytes([_OPERATE_OPCODE, direction])
        + seq.to_bytes(2, "little")
        + trailer.to_bytes(2, "little")
    )


def build_control_frame(sub_cmd: int, data: bytes = b"") -> bytes:
    """Build a generic control-frame plaintext: ``sub_cmd`` byte followed by data.

    The two commands confirmed on the real lock (operate ``0x74`` and keepalive
    ``0x2f``) both start with their **sub-command byte** — there is **no mainCmd
    byte on the wire**; the command family (SYSTEM/USER/…) in
    ``operations_catalog`` is an app-side grouping, not a wire prefix. This helper
    emits that confirmed shape.

    The exact ``data`` for non-confirmed commands is **unverified** (only ``0x74``
    and ``0x2f`` were captured). For the confirmed operate command use
    ``build_operate_frame`` — it has the additive-trailer structure that this
    generic ``sub_cmd + data`` form does not model.
    """
    if not 0 <= sub_cmd <= 0xFF:
        raise ValueError("sub_cmd must be a single byte (0..255)")
    return bytes([sub_cmd]) + data


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
    #: Either a catalogued `LockOperation` or a probe label like "query:0x07"
    #: (feature 021) for a generic control frame that has no enum member.
    operation: LockOperation | str
    payload: bytes
    write_prefix: int

    @property
    def hex_payload(self) -> str:
        return self.payload.hex()


def build_control_query_write(sub_cmd: int, data: bytes = b"") -> LockOperationWrite:
    """Build a generic **read-only-intended** control query write (feature 021).

    Wraps ``build_control_frame(sub_cmd, data)`` with the captured control write
    prefix (0x01). Use it to probe catalogued status opcodes (e.g. ``0x07``
    ``LOCK_STATUS``, ``0xE5`` ``GET_DOOR_LOCK_STATUS``) whose response might carry
    the bolt position — the keepalive/operate/state_snapshot ACKs do not. The
    exact payload of these opcodes is **unconfirmed**; the honest first probe
    sends only the opcode byte. The caller is responsible for sending only
    read-only opcodes — this helper does not enforce that (the CLI does).
    """

    return LockOperationWrite(
        operation=f"query:0x{sub_cmd:02x}",
        payload=build_control_frame(sub_cmd, data),
        write_prefix=0x01,
    )


class SessionOperationTransport(Protocol):
    def send_plaintext_operation(self, payload: bytes) -> None:
        """Send plaintext operation bytes through an authenticated session."""


def build_lock_operation_write(
    operation: LockOperation | str | LockOperationWrite,
) -> LockOperationWrite:
    # Passthrough (feature 021): a pre-built write (e.g. a status-query probe from
    # build_control_query_write) is sent as-is, so the session's actuator path is
    # unchanged and can carry generic control frames too.
    if isinstance(operation, LockOperationWrite):
        return operation
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
