#!/usr/bin/env python3
"""Replay a captured U200 language-OTA transfer verbatim onto the lock.

Background (see docs/devices/u200/operations.md + memory clean-session-start-here):
the language voice-pack is pushed to the lock over a PLAINTEXT GATT channel — the
AUX service ff90, characteristic ff91 (ATT value handle 0x003c),
WRITE_WITHOUT_RESPONSE (ATT opcode 0x52, fire-and-forget). A full Français
transfer was captured end-to-end via btsnoop on the clean Play-Store app
(``captures/ota/btsnoop_end.log``): 8138 writes = an opening ``0x90`` per-process
token, the init frame, the manifest-driven ``.bin`` chunks, the activation tail,
and a closing ``0x90`` token identical to the opening one.

Because the whole transfer is captured byte-for-byte, replaying it needs NO
framing decode and NO from-scratch builder: we extract every ff91 write in order
and push it back to ff91 over bumble. This is the decisive test:

  * Lock accepts (language flips)  → the ``0x90`` token is opaque/replayable,
    the OTA channel needs neither Frida nor root. Path to a real
    ``OtaLanguageTransfer`` is open.
  * Lock rejects at ``0x90``       → the token is session-bound (validated live),
    and a from-scratch builder needs a native hook to mint a fresh one.

The tool has two independent stages so the risky part is opt-in:

    # 1. Offline: parse the capture, print stats, cache the frames. No radio.
    python3 tools/replay_ota.py --extract-only

    # 2. Live: connect over the ESP32-S3, negotiate MTU 247, stream to ff91.
    python3 tools/replay_ota.py            # needs .env (AQARA_ESP32_PORT, MAC…)
    python3 tools/replay_ota.py --dry-run  # connect + MTU, but write nothing

Observable-change tip: the lock is currently on Français, so a Français replay
would be a no-op to the ear. First switch it to Español (app quick-pick or the
HA ``select.language`` entity), THEN run this — you should hear it flip back.

Safety: this performs a REAL firmware voice-pack write. It only ever writes to
ff91 (never the control/auth channels) and only the exact bytes from the capture.
Nothing here actuates the bolt.
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import os
import struct
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

DEFAULT_CAPTURE = _ROOT / "captures" / "ota" / "btsnoop_end.log"
OTA_HANDLE = 0x3C  # ff91 value handle
EXPECTED_FRAMES = 8138
MTU_TARGET = 247  # 244-byte value + 3-byte ATT header


def _load_dotenv() -> None:
    """Populate os.environ from .env without shell interpretation (values may
    hold ``&``/``!``). Existing environment always wins."""
    path = _ROOT / ".env"
    if not path.is_file():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.split(" #", 1)[0].strip())


def extract_ota_writes(path: Path, target: int = OTA_HANDLE) -> list[bytes]:
    """Return, in capture order, the value bytes of every ATT Write Command /
    Write Request on ``target`` in a btsnoop file. Direction is not filtered by
    the parser, but on this handle only the phone ever writes, so every hit is an
    outgoing app→lock frame."""
    data = path.read_bytes()
    if data[:8] != b"btsnoop\x00":
        raise ValueError(f"{path} is not a btsnoop file")
    off = 16  # 8 magic + 4 version + 4 datalink
    frames: list[bytes] = []
    while off + 24 <= len(data):
        _orig, incl, _flags, _drops, _ts = struct.unpack(">IIIIq", data[off:off + 24])
        off += 24
        pkt = data[off:off + incl]
        off += incl
        if not pkt or pkt[0] != 0x02:  # HCI ACL data only
            continue
        body = pkt[1:]
        if len(body) < 4:
            continue
        acl_len = struct.unpack("<H", body[2:4])[0]
        l2cap = body[4:4 + acl_len]
        if len(l2cap) < 4:
            continue
        l2_len = struct.unpack("<H", l2cap[0:2])[0]
        cid = struct.unpack("<H", l2cap[2:4])[0]
        if cid != 0x0004:  # ATT
            continue
        att = l2cap[4:4 + l2_len]
        if len(att) < 3 or att[0] not in (0x52, 0x12):  # WriteCmd / WriteReq
            continue
        if struct.unpack("<H", att[1:3])[0] != target:
            continue
        frames.append(bytes(att[3:]))
    return frames


def summarize(frames: list[bytes]) -> None:
    from collections import Counter

    lens = Counter(len(f) for f in frames)
    prefixes = Counter(f[0] for f in frames if f)
    print(f"frames on 0x{OTA_HANDLE:02x}: {len(frames)}")
    print(f"  value lengths (top): {lens.most_common(5)}")
    print(f"  max value length:    {max(len(f) for f in frames)}")
    print(f"  first-byte prefixes: {{{', '.join(f'0x{k:02x}:{v}' for k, v in prefixes.most_common())}}}")
    n90 = [i for i, f in enumerate(frames) if f and f[0] == 0x90]
    print(f"  0x90 token frames at indices: {n90}")
    if n90:
        print(f"    opening 0x90: {frames[n90[0]].hex()}")
        print(f"    closing 0x90: {frames[n90[-1]].hex()}")
        print(f"    opening == closing: {frames[n90[0]] == frames[n90[-1]]}")
    init = next((f for f in frames if f[:1] == b"\x11" and b".bin\x00" in f), None)
    if init is not None:
        name = init[3:].split(b"\x00", 1)[0]
        print(f"  init frame: {name.decode('latin1')!r}  (len {len(init)})")


def _auth_from_env() -> Any:
    """Build a CloudAuthManager from the environment (same vars as the `aqara` CLI)."""
    from aqara_ble.auth import CloudAuthManager

    need = ["AQARA_ACCOUNT", "AQARA_PASSWORD", "AQARA_APPID", "AQARA_APPKEY",
            "AQARA_CLIENT_ID", "AQARA_PHONE_ID"]
    missing = [n for n in need if not os.environ.get(n)]
    if missing:
        raise RuntimeError("missing credentials in env: " + ", ".join(missing))
    return CloudAuthManager(
        account=os.environ["AQARA_ACCOUNT"],
        password=os.environ["AQARA_PASSWORD"],
        appid=os.environ["AQARA_APPID"],
        appkey=os.environ["AQARA_APPKEY"],
        client_id=os.environ["AQARA_CLIENT_ID"],
        phone_id=os.environ["AQARA_PHONE_ID"],
        region=os.environ.get("AQARA_REGION", "EU"),
    )


async def _run_authenticated(frames: list[bytes], args: argparse.Namespace) -> int:
    """The real path: authenticate a full aqara session (auth + CCCD on ff92 +
    live control channel), then stream the OTA frames to ff91 while draining ff92
    acks. This is what the wire evidence showed the app actually does."""
    from aqara_ble.client import U200Client
    from aqara_ble.transport import BumbleTransport

    port = args.port or os.environ.get("AQARA_ESP32_PORT")
    mac = args.mac or os.environ.get("AQARA_LOCK_MAC")
    device_id = os.environ.get("AQARA_DEVICE_ID")
    if not port or not mac or not device_id:
        print("[config] need AQARA_ESP32_PORT, AQARA_LOCK_MAC, AQARA_DEVICE_ID (or --port/--mac)",
              file=sys.stderr)
        return 2
    try:
        auth = _auth_from_env()
    except RuntimeError as exc:
        print(f"[config] {exc}", file=sys.stderr)
        return 2

    transport = BumbleTransport(port)
    started = time.monotonic()
    print(f"[auth-ota] full authenticated session → stream {len(frames)} frames to ff91")
    print("[flow] login → scan/connect → discover → AUTH → CCCD(ff92) → stream ff91 (ff92 acks)")

    def progress(sent: int, total: int, acks: int) -> None:
        rate = sent / max(0.001, time.monotonic() - started)
        print(f"  [{sent}/{total}] {rate:.0f} f/s  (ff92 acks so far: {acks})")

    try:
        async with await U200Client.connect(
            auth=auth,
            transport=transport,
            device_id=device_id,
            mac=mac,
            region=os.environ.get("AQARA_REGION", "EU"),
            scan_timeout=args.timeout,
        ) as lock:
            print(f"[connect] connected in {time.monotonic() - started:.1f}s")
            if args.dry_run:
                print("[dry-run] authenticated connect OK; NOT streaming. (Full auth "
                      "handshake runs at stream time, not connect time.) Done.")
                return 0
            result = await lock.push_language_ota(
                frames,
                delay=args.delay,
                handshake_pause_s=args.handshake_pause,
                trailing_listen_s=args.listen_ms / 1000.0,
                arm=not args.no_arm,
                progress=progress,
            )
            print("\n[arming] pre-stream OTA control reads (lock replies):")
            for name, reply in result.arming_replies:
                print(f"    {name:<20} → {reply.hex() if reply else '(no reply)'}")
            print(f"[write] DONE: {result.frames_sent} frames in {result.duration_s:.1f}s")
            print(f"[result] ff92 acks captured: {len(result.acks)}  lock_engaged={result.lock_engaged}")
            for t, idx, payload in result.acks[:40]:
                print(f"    @{t:6.2f}s  after frame#{idx}  {payload.hex()}")
            if len(result.acks) > 40:
                print(f"    … and {len(result.acks) - 40} more")
            if result.lock_engaged:
                print("[result] 🎯 the lock ACK'd on ff92 → it engaged in the OTA transfer. "
                      "Compare ack count/shape against the capture's 1637; check if the "
                      "language actually switched.")
            else:
                print("[result] ff92 SILENT even authenticated → the lock did not engage. "
                      "Points at the 0x90 commit token being session-bound (rejected).")
            return 0
    except Exception as exc:  # noqa: BLE001
        print(f"[error] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        with contextlib.suppress(Exception):
            await transport.disconnect()


async def _run_live(frames: list[bytes], args: argparse.Namespace) -> int:
    from aqara_ble.transport import BumbleTransport, normalize_mac
    from aqara_ble.gatt_uuids import AUX_WRITE_UUID, AUX_NOTIFY_UUID

    port = args.port or os.environ.get("AQARA_ESP32_PORT")
    if not port:
        print("[config] need --port or AQARA_ESP32_PORT (ESP32-S3 HCI)", file=sys.stderr)
        return 2
    mac = args.mac or os.environ.get("AQARA_LOCK_MAC")
    if not mac:
        print("[config] need --mac or AQARA_LOCK_MAC", file=sys.stderr)
        return 2

    max_len = max(len(f) for f in frames)
    print(f"[plan] {len(frames)} frames, max value {max_len}B → MTU {MTU_TARGET} required")
    transport = BumbleTransport(port)
    started = time.monotonic()
    try:
        print(f"[connect] {mac} via {transport.name} ({port})")
        gatt = await asyncio.wait_for(transport.connect(normalize_mac(mac), timeout=20.0), timeout=25.0)
        print(f"[connect] linked + discovered in {time.monotonic() - started:.1f}s")

        # MTU: the authenticated flow normally negotiates this; here we do it
        # ourselves so 244-byte values are not fragmented.
        request_mtu = getattr(gatt, "request_mtu", None)
        if request_mtu is not None:
            try:
                negotiated = await request_mtu(MTU_TARGET)
                print(f"[mtu] negotiated {negotiated}")
                if negotiated < max_len + 3:
                    print(
                        f"[mtu] WARNING negotiated {negotiated} < {max_len + 3}; "
                        "244-byte writes may be rejected/fragmented"
                    )
            except Exception as exc:  # noqa: BLE001 - report, keep going
                print(f"[mtu] request failed ({exc}); proceeding at default MTU")
        else:
            print("[mtu] adapter has no request_mtu; proceeding at default MTU")

        # Best-effort faster connection interval for throughput (OTA path has no
        # firmware timeout, so this is purely to shorten the ~8k-frame stream).
        upd = getattr(gatt, "update_connection_parameters", None)
        if upd is not None and not args.no_speedup:
            try:
                await upd(interval_ms=15.0, latency=0, supervision_timeout_ms=6000.0)
                print("[conn] requested 15ms interval")
            except Exception as exc:  # noqa: BLE001
                print(f"[conn] interval update skipped ({exc})")

        # Listen on ff92 (AUX notify, handle 0x003e) for anything the lock
        # sends back during/after the transfer: a NAK, a progress/ack, or the
        # 0x90 commit reply. A blind fire-and-forget replay would miss all of
        # this; capturing it distinguishes "0x90 token rejected" from "the
        # lock expected a bidirectional handshake we skipped".
        state = {"idx": -1}
        notifs: list[tuple[float, int, bytes]] = []
        tsub = time.monotonic()

        def on_ff92(_sender: Any, data: bytearray) -> None:
            notifs.append((time.monotonic() - tsub, state["idx"], bytes(data)))
            print(f"  [ff92 @{time.monotonic() - tsub:6.2f}s after frame#{state['idx']}] "
                  f"{bytes(data).hex()}")

        try:
            await gatt.start_notify(AUX_NOTIFY_UUID, on_ff92)
            print(f"[notify] subscribed to ff92 ({AUX_NOTIFY_UUID})")
        except Exception as exc:  # noqa: BLE001
            print(f"[notify] could NOT subscribe to ff92 ({exc}); replay continues blind")

        if args.dry_run:
            print("[dry-run] connection + MTU + ff92 subscription ready; NOT writing. "
                  "Waiting 3s for any spontaneous ff92 traffic…")
            await asyncio.sleep(3.0)
            print(f"[dry-run] ff92 notifications while idle: {len(notifs)}")
            return 0

        print(f"[write] streaming {len(frames)} frames to ff91 "
              f"({AUX_WRITE_UUID}) as WRITE_WITHOUT_RESPONSE, delay={args.delay*1000:.0f}ms")
        t0 = time.monotonic()
        sent = 0
        for i, value in enumerate(frames):
            state["idx"] = i
            await gatt.write_gatt_char(AUX_WRITE_UUID, value, response=False)
            sent += 1
            # After the opening 0x90 handshake (frames 0-1) give the lock a beat
            # to answer on ff92 before the bulk stream races past it.
            if i == 1:
                await asyncio.sleep(args.handshake_pause)
            if args.delay > 0:
                await asyncio.sleep(args.delay)
            if (i + 1) % 500 == 0 or (i + 1) == len(frames):
                rate = (i + 1) / (time.monotonic() - t0)
                print(f"  [{i + 1}/{len(frames)}] {rate:.0f} frames/s  (ff92 so far: {len(notifs)})")
        dt = time.monotonic() - t0
        print(f"[write] DONE: {sent} frames in {dt:.1f}s ({sent/dt:.0f} frames/s)")

        # Collect trailing ff92 traffic after the activation tail.
        print(f"[notify] waiting {args.listen_ms}ms for trailing ff92 traffic…")
        await asyncio.sleep(args.listen_ms / 1000.0)

        print(f"\n[result] ff92 notifications captured: {len(notifs)}")
        if notifs:
            for t, idx, payload in notifs:
                print(f"    @{t:6.2f}s  after frame#{idx}  {payload.hex()}")
            print("[result] the lock DID talk back on ff92 → not a silent reject; "
                  "decode these to see if it's a NAK, an ack, or a commit reply.")
        else:
            print("[result] ff92 stayed SILENT the whole transfer → the lock never "
                  "acknowledged anything. Consistent with the 0x90 commit token being "
                  "rejected outright (session-bound), or the AUX notify not being the "
                  "reply channel. Either way, no bidirectional progress happened.")
        with contextlib.suppress(Exception):
            await gatt.stop_notify(AUX_NOTIFY_UUID)
        return 0
    except Exception as exc:  # noqa: BLE001 - top-level report
        print(f"[error] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        with contextlib.suppress(Exception):
            await asyncio.wait_for(transport.disconnect(), timeout=5.0)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--capture", type=Path, default=DEFAULT_CAPTURE,
                   help=f"btsnoop file to replay (default: {DEFAULT_CAPTURE.relative_to(_ROOT)})")
    p.add_argument("--extract-only", action="store_true",
                   help="parse + summarize the capture, cache frames, no radio")
    p.add_argument("--dry-run", action="store_true",
                   help="connect + negotiate MTU but write nothing")
    p.add_argument("--mac", help="lock MAC (default: AQARA_LOCK_MAC)")
    p.add_argument("--port", help="ESP32-S3 HCI port (default: AQARA_ESP32_PORT)")
    p.add_argument("--delay", type=float, default=0.006,
                   help="seconds between frames (default 0.006; 0 = as fast as bumble allows)")
    p.add_argument("--no-speedup", action="store_true",
                   help="do not request a faster connection interval")
    p.add_argument("--handshake-pause", type=float, default=1.5,
                   help="seconds to wait after the opening 0x90 handshake (frames 0-1) "
                        "for a ff92 reply before the bulk stream (default 1.5)")
    p.add_argument("--listen-ms", type=int, default=5000,
                   help="ms to keep listening on ff92 after the last frame (default 5000)")
    p.add_argument("--timeout", type=float, default=25.0,
                   help="scan/connect timeout seconds (default 25)")
    p.add_argument("--bare", action="store_true",
                   help="OLD path: blast ff91 with NO auth (proven insufficient — kept for comparison)")
    p.add_argument("--no-arm", action="store_true",
                   help="skip the pre-stream OTA arming reads (SYNC_OTA_URL/VOICE_OTA_INFO_GET)")
    p.add_argument("--cache", type=Path, default=None,
                   help="also write extracted frames to this file (length-prefixed)")
    args = p.parse_args(argv)

    _load_dotenv()

    if not args.capture.is_file():
        print(f"[error] capture not found: {args.capture}", file=sys.stderr)
        return 2
    frames = extract_ota_writes(args.capture)
    summarize(frames)
    if len(frames) != EXPECTED_FRAMES:
        print(f"[warn] expected {EXPECTED_FRAMES} frames, got {len(frames)} "
              "(capture may differ from the reference Français transfer)")

    if args.cache is not None:
        with args.cache.open("wb") as fh:
            for f in frames:
                fh.write(struct.pack("<H", len(f)))
                fh.write(f)
        print(f"[cache] wrote {len(frames)} frames → {args.cache}")

    if args.extract_only:
        return 0

    if args.bare:
        return asyncio.run(_run_live(frames, args))
    return asyncio.run(_run_authenticated(frames, args))


if __name__ == "__main__":
    raise SystemExit(main())
