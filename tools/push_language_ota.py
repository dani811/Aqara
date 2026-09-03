#!/usr/bin/env python3
"""Push a language voice-pack OTA to the U200 FROM SCRATCH with aqara_ble.

Builds the full transfer (JSON handshake + manifest + XMODEM data stream) from a
CDN ``.bin`` and drives it inside an authenticated session — no captured frames,
no Frida. This is the culmination of the language-OTA reverse engineering
(mechanism = standard AES-CCM under the session key+nonce; see
docs/devices/u200/ota-0x90-investigation.md "RESOLVED").

Usage (needs .env sourced: AQARA_* + AQARA_ESP32_PORT + AQARA_LOCK_MAC):
    python3 tools/push_language_ota.py --bin captures/U200_ES_audio_burn.bin --dry-run
    python3 tools/push_language_ota.py --bin captures/U200_ES_audio_burn.bin        # live push
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples"))


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from aqara_ble.ota_language import (
    build_ota_control_frame,
    build_ota_manifest_json,
    iter_ota_data_writes,
)


def _dry_run(blob: bytes, name: str) -> int:
    # A dummy session key+nonce just to show the control-frame shapes offline.
    k = "00" * 16
    n = "00" * 13
    start = build_ota_control_frame(k, n, 0x04, b'{"ID":255}')
    manifest_json = build_ota_manifest_json(name, blob)
    manifest = build_ota_control_frame(k, n, 0x03, manifest_json)
    writes = list(iter_ota_data_writes(blob, name))
    print(f"[dry-run] {name}  size={len(blob)}")
    print(f"[dry-run] manifest JSON: {manifest_json.decode()}")
    print(f"[dry-run] start frame   : {start.hex()}  ({len(start)}B, prefix 0x90)")
    print(f"[dry-run] manifest frame: {len(manifest)}B (prefix 0x90)")
    print(f"[dry-run] data writes   : {len(writes)}  (each 0x11 + <=243B)")
    print(f"[dry-run] first data    : {writes[0][:8].hex()}…  last {writes[-1][-6:].hex()}")
    print("[dry-run] OK — nothing sent. Drop --dry-run for the live push.")
    return 0


async def _live(blob: bytes, name: str, args: argparse.Namespace) -> int:
    from auth_from_env import auth_from_env

    from aqara_ble.client import U200Client

    mac = args.mac or os.environ.get("AQARA_LOCK_MAC")
    device_id = os.environ.get("AQARA_DEVICE_ID")
    if not device_id:
        print("[config] need AQARA_DEVICE_ID", file=sys.stderr)
        return 2

    if args.transport == "bleak":
        from aqara_ble.transport import BleakTransport
        transport = BleakTransport()
        where = "Mac native BLE (bleak/CoreBluetooth)"
        # macOS/CoreBluetooth hides MACs — identify the lock by name/advert instead.
        mac = None
    elif args.transport == "esphome":
        from aqara_ble.esphome_transport import EsphomeProxyTransport
        host = args.host or os.environ.get("AQARA_ESPHOME_HOST")
        psk = os.environ.get("AQARA_ESPHOME_NOISE_PSK")
        if not host:
            print("[config] --transport esphome needs --host or AQARA_ESPHOME_HOST", file=sys.stderr)
            return 2
        transport = EsphomeProxyTransport(host, noise_psk=psk)
        where = f"ESPHome proxy {host}"
        if not mac:
            print("[config] --transport esphome needs AQARA_LOCK_MAC", file=sys.stderr)
            return 2
    else:
        from aqara_ble.transport import BumbleTransport
        port = args.port or os.environ.get("AQARA_ESP32_PORT")
        if not port:
            print("[config] --transport bumble needs --port or AQARA_ESP32_PORT", file=sys.stderr)
            return 2
        transport = BumbleTransport(port)
        where = port

    auth = auth_from_env()
    region = os.environ.get("AQARA_REGION", "EU")

    # PRE-LOAD THE CLOUD like the app does: fetch the ephemeral cloud pubkey BEFORE
    # any BLE, so the on-lock auth completes instantly after connect — while the
    # keypad-touch presence is still active. Doing it inline (between connect and the
    # auth write) burns the presence window and the lock NAKs the OTA mid-stream.
    from aqara_ble.kdf import REGION_BASE_URLS, cloud_get_public_key  # noqa: PLC0415

    _t = time.monotonic()
    _signer = await asyncio.to_thread(auth.build_signer)  # warm the login token
    precloud_pubkey = await asyncio.to_thread(
        cloud_get_public_key, device_id, None, REGION_BASE_URLS.get(region, REGION_BASE_URLS["EU"]),
        _signer,
    )
    print(f"[precloud] cloud pubkey fetched in {time.monotonic() - _t:.1f}s (BLE auth will be instant)")

    started = time.monotonic()
    print(f"[push] {name} ({len(blob)}B) → authenticated OTA over {where}")

    def progress(sent: int, total: int, acks: int) -> None:
        rate = sent / max(0.001, time.monotonic() - started)
        print(f"  [{sent}/{total}] {rate:.0f} f/s  ff92 acks: {acks}")

    try:
        async with await U200Client.connect(
            auth=auth, transport=transport, device_id=device_id, mac=mac,
            region=region, scan_timeout=args.timeout,
        ) as lock:
            print(f"[connect] connected in {time.monotonic() - started:.1f}s")
            result = await lock.push_voice_pack_ota(
                blob, name, arm=not args.no_arm, data_delay=args.delay,
                window=args.window, resume_from=args.start_block,
                manifest_wait_s=120.0, post_manifest_settle_s=0.0, keepalive_every_s=2.0,
                precomputed_cloud_pubkey=precloud_pubkey, progress=progress,
            )
            print(f"\n[write] {result.frames_sent} data frames in {result.duration_s:.1f}s")
            print(f"[result] ff92 acks: {len(result.acks)}  completed={result.completed}")
            print(f"[result] stalled_at block: {getattr(result, 'stalled_at', None)}")
            # Diagnostic: distribution of the plaintext 2-byte ff92 status codes
            # (0x11xx) and the full arrival timeline, to see the real per-block ack.
            from collections import Counter  # noqa: PLC0415
            codes = Counter(
                obj[:2].hex() if isinstance(obj, (bytes, bytearray)) else "json"
                for _t, obj in result.acks
            )
            print(f"[result] ff92 code histogram: {dict(codes)}")
            print("[result] ff92 timeline:")
            for t, obj in result.acks:
                print(f"    @{t:6.2f}s  {obj if isinstance(obj, dict) else obj.hex()}")
            ok = bool(result.completed) and (
                isinstance(result.final_status, dict)
                and result.final_status.get("xfer_statu") == "success"
            )
            if ok:
                print(f"[result] 🎯 OTA SUCCESS: {result.final_status} — language applied.")
            else:
                print(f"[result] not done ({result.final_status}); will retry if attempts remain.")
            return 0 if ok else 1
    except Exception as exc:
        print(f"[attempt] failed: {type(exc).__name__}: {exc}")
        return 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin", required=True, help="path to the CDN .bin voice pack")
    ap.add_argument("--transport", choices=("bleak", "bumble", "esphome"), default="bleak", help="bleak = Mac native BLE (default), bumble = ESP32-S3")
    ap.add_argument("--name", help="on-wire filename (default: the .bin basename)")
    ap.add_argument("--dry-run", action="store_true", help="build frames offline, send nothing")
    ap.add_argument("--port", help="ESP32-S3 HCI (overrides AQARA_ESP32_PORT)")
    ap.add_argument("--host", help="ESPHome proxy host/IP (overrides AQARA_ESPHOME_HOST)")
    ap.add_argument("--mac", help="lock MAC (overrides AQARA_LOCK_MAC)")
    ap.add_argument("--delay", type=float, default=0.006, help="per-data-frame delay (s)")
    ap.add_argument("--timeout", type=float, default=30.0, help="scan timeout (s)")
    ap.add_argument("--no-arm", action="store_true", help="skip the pre-stream arming reads")
    ap.add_argument("--window", type=int, default=3, help="max blocks ahead of the lock acks")
    ap.add_argument("--attempts", type=int, default=6, help="auto-retry this many times until success")
    ap.add_argument("--start-block", type=int, default=0, help="resume test: start streaming at block N")
    ap.add_argument("--reset-bt", action="store_true",
                    help="reset the Mac Bluetooth (blueutil) between attempts")
    args = ap.parse_args()

    blob = Path(args.bin).read_bytes()
    name = args.name or Path(args.bin).name
    if args.dry_run:
        return _dry_run(blob, name)

    import subprocess  # noqa: PLC0415

    for attempt in range(1, args.attempts + 1):
        print(f"\n========== attempt {attempt}/{args.attempts} ==========")
        rc = asyncio.run(_live(blob, name, args))
        if rc == 0:
            print(f"[done] completed on attempt {attempt}.")
            return 0
        if attempt < args.attempts:
            if args.reset_bt and args.transport == "bleak":
                with contextlib.suppress(Exception):
                    subprocess.run(["blueutil", "-p", "0"], timeout=10, check=False)
                    time.sleep(4)
                    subprocess.run(["blueutil", "-p", "1"], timeout=10, check=False)
                    print("[retry] Mac BT reset; waiting for the lock to release…")
            time.sleep(12)  # let the lock drop the stale connection
    print("[done] exhausted attempts without a success frame.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
