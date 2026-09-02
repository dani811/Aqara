"""Language voice-pack OTA streaming over the AUX channel (ff91/ff92).

Wire evidence (2026-09-02, `captures/ota/btsnoop_end.log`, both directions)
established the real mechanism:

- The transfer is NOT a standalone plaintext blast. It runs INSIDE a fully
  authenticated aqara session (ECDH done, CCCD enabled on ff62/ff64/ff92/ff08,
  control channel kept alive). A bare unauthenticated ff91 write is ignored.
- The phone streams the voice `.bin` (wrapped with per-block markers + an
  activation tail + two `0x90` commit frames) to ff91 as WRITE_WITHOUT_RESPONSE.
- The lock **block-acks on ff92** — ~1637 notifications for a full transfer —
  i.e. it is flow-controlled, not fire-and-forget.
- The control channel must keep receiving keepalives or the lock goes quiet
  ~30 s in.

This module drives that stream given a :class:`~aqara_ble.session.PostAuthContext`
(handed in after auth by ``run_authenticated_lock_operation(post_auth=…)``). It
is deliberately a thin, observable driver: it streams the captured/con­structed
frames, interleaves control keepalives, and surfaces every ff92 ack so a caller
can see whether the lock engaged (and, crucially, whether the `0x90` commit was
accepted or rejected).
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from .session import PostAuthContext


# The pre-stream OTA "arming" reads the app issues on the control channel right
# before it starts pushing ff91, recovered by decrypting the capture's control
# channel (keystream reuse; 2026-09-02). Plaintext is the `<op> <family> <op>`
# read shape. The hypothesis under test: issuing these transitions the lock's OTA
# state machine into "ready to receive", without which it ignores the ff91 stream.
ARMING_READS: tuple[tuple[str, bytes], ...] = (
    ("SYNC_OTA_URL", bytes([0x1A, 0x01, 0x1A])),
    ("READ_LOCK_LANGUAGE", bytes([0x68, 0x01, 0x68])),
    ("VOICE_OTA_INFO_GET", bytes([0xA6, 0x03, 0xA6])),
)


@dataclass
class OtaResult:
    """What happened during a language-OTA stream attempt."""

    frames_sent: int
    duration_s: float
    #: Every ff92 payload the lock pushed, in arrival order, with the seconds
    #: since stream start and the index of the last ff91 frame written before it.
    acks: list[tuple[float, int, bytes]] = field(default_factory=list)
    #: (name, response_plaintext_or_None) for each pre-stream arming read.
    arming_replies: list[tuple[str, bytes | None]] = field(default_factory=list)

    @property
    def lock_engaged(self) -> bool:
        """True if the lock ack'd anything on ff92 — i.e. it accepted us into an
        OTA transfer at all (as opposed to silently ignoring the whole stream)."""
        return bool(self.acks)


async def stream_language_ota(
    ctx: PostAuthContext,
    frames: list[bytes],
    *,
    delay: float = 0.006,
    keepalive_every_s: float = 8.0,
    handshake_pause_s: float = 1.5,
    trailing_listen_s: float = 5.0,
    arm: bool = True,
    progress: object | None = None,
) -> OtaResult:
    """Stream ``frames`` (verbatim ff91 writes, in order) inside the authenticated
    session in ``ctx``, draining ff92 acks and keeping the control channel alive.

    ``arm`` (default True): first issue the pre-stream OTA control reads
    (:data:`ARMING_READS`) the app sends before it streams, to transition the
    lock into its OTA-ready state. Set False to skip them (A/B comparison).

    ``progress`` — optional callable ``(sent, total, acks)`` invoked periodically.

    Returns an :class:`OtaResult`; ``result.lock_engaged`` is the headline signal.
    """
    acks: list[tuple[float, int, bytes]] = []
    arming_replies: list[tuple[str, bytes | None]] = []
    state = {"idx": -1}
    t0 = time.monotonic()

    if arm:
        for name, plaintext in ARMING_READS:
            await ctx.send_control(plaintext)
            reply = await ctx.read_control(timeout=3.0)
            arming_replies.append((name, reply))

    async def drain_acks() -> None:
        """Continuously move ff92 reports out of the session queue into ``acks``.
        ff64 also lands here; we keep only ff92 (the OTA ack channel)."""
        while True:
            channel, data = await ctx.aux_reports.get()
            if channel == "ff92":
                acks.append((time.monotonic() - t0, state["idx"], bytes(data)))

    drainer = asyncio.ensure_future(drain_acks())
    keepalive_task_next = time.monotonic() + keepalive_every_s
    try:
        total = len(frames)
        for i, value in enumerate(frames):
            state["idx"] = i
            await ctx.write_aux(value)
            # After the opening 0x90 handshake (frames 0-1) give the lock a beat
            # to accept/answer on ff92 before the bulk stream races past it.
            if i == 1 and handshake_pause_s > 0:
                await asyncio.sleep(handshake_pause_s)
            if delay > 0:
                await asyncio.sleep(delay)
            # Interleave the control keepalive so the session survives the stream.
            now = time.monotonic()
            if now >= keepalive_task_next:
                await ctx.send_keepalive()
                keepalive_task_next = now + keepalive_every_s
            if progress is not None and ((i + 1) % 500 == 0 or (i + 1) == total):
                progress(i + 1, total, len(acks))  # type: ignore[operator]

        # Let trailing acks / the commit reply arrive.
        end = time.monotonic() + trailing_listen_s
        while time.monotonic() < end:
            await ctx.send_keepalive()
            await asyncio.sleep(min(1.0, keepalive_every_s))
    finally:
        drainer.cancel()

    return OtaResult(
        frames_sent=len(frames),
        duration_s=time.monotonic() - t0,
        acks=acks,
        arming_replies=arming_replies,
    )
