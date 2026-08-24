"""Lock state snapshot decoded from the control-channel response (feature 019).

`run_authenticated_lock_operation` already returns the **decrypted** control
response. This module turns that response into a typed `LockState`. It is
deliberately **honest**: `raw_hex` is always exposed, and a decoded field is set
**only** when captured evidence supports it — otherwise it stays `None`. We never
invent a lock state.

Confirmed real samples (2026-08-17, this project's own lock, own account):

    keepalive `2f012f`  ->  response `2f00 2c06`
    unlock    (open)    ->  response `7400 7706`

Working hypothesis (NOT yet confirmed — needs labelled captures in known physical
states): the response echoes the sub-command byte (`0x2f` keepalive, `0x74`
operate) followed by a direction/status byte and a 2-byte tail. The direction
byte of the operate response looked like `0x00` after an unlock — plausibly the
resulting bolt position — but a single sample is not proof. `decode_lock_state`
therefore leaves `locked`/`battery_percent` as `None` until a sample set pins
them down (see docs/devices/u200/validation.md capture procedure).
"""

from __future__ import annotations

from dataclasses import dataclass

#: Where a LockState came from.
SOURCE_KEEPALIVE = "keepalive"
SOURCE_OPERATION = "operation"
SOURCE_QUERY = "query"
SOURCE_EVENT = "event"  # reserved for spontaneous reports (needs a persistent session)


@dataclass(frozen=True)
class LockState:
    """A point-in-time view of the lock, decoded from a control response.

    ``raw_hex`` is the decrypted response bytes (or ``None`` if the lock did not
    answer). Decoded fields are ``None`` unless confirmed by evidence — a
    consumer must treat ``None`` as "unknown", never as a default state.
    """

    raw_hex: str | None
    source: str
    responded: bool
    locked: bool | None = None
    battery_percent: int | None = None

    @property
    def sub_command(self) -> int | None:
        """The echoed sub-command byte of the response, if any (e.g. 0x2f/0x74)."""

        if not self.raw_hex or len(self.raw_hex) < 2:
            return None
        return int(self.raw_hex[:2], 16)


def decode_lock_state(raw: bytes | None, source: str) -> LockState:
    """Build a `LockState` from a decrypted control response.

    Only evidence-backed fields are populated; everything unconfirmed stays
    ``None``. Never raises on unexpected bytes and never invents a state.
    """

    if not raw:
        return LockState(raw_hex=None, source=source, responded=False)
    # Present the raw bytes; decoded fields remain None until confirmed by a
    # labelled capture set (see module docstring / validation.md).
    return LockState(raw_hex=raw.hex(), source=source, responded=True)


__all__ = [
    "SOURCE_EVENT",
    "SOURCE_KEEPALIVE",
    "SOURCE_OPERATION",
    "SOURCE_QUERY",
    "LockState",
    "decode_lock_state",
]
