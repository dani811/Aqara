#!/usr/bin/env python3
"""Change the U200's spoken language over BLE, from scratch — the reproducible
example.

No phone app, no Frida: authenticates with the cloud, then drives the full
Xiaomi-mible voice-pack OTA (JSON handshake + VOICE_OTA_INFO_SET + XMODEM data
stream) inside one authenticated session. See
docs/devices/u200/language-ota-usage.md.

Run it every time like:

    # .env must have the AQARA_* creds + AQARA_LOCK_MAC + a transport (below)
    python3 examples/change_language.py captures/U200_ES_audio_burn.bin
    python3 examples/change_language.py captures/U200_ES_audio_burn.bin --transport bumble

Transport (pick via --transport / env):
  esphome (default, most reliable): AQARA_ESPHOME_HOST + AQARA_ESPHOME_NOISE_PSK
  bumble (ESP32-S3):                AQARA_ESP32_PORT=serial:/dev/cu.usbmodemNNNN,115200
  bleak  (Mac native BLE)

Get any language's `.bin` (public CDN, no auth) via the voice/list flow in
docs/reference/aqara-cdn-and-models.md — filenames are U200_<ISO>_audio_burn.bin
(FR, ES, CN, RU, PL). The filename you pass is what the lock keys the language on.

Presence note: the lock must be awake/advertising to connect. Today that is one
keypad presence (delivered remotely by the `switch.pulsador` fingerbot via Home
Assistant) — it authorises the OTA start only, NOT each block. Fire the fingerbot
just before running this; the tool re-sends the manifest for up to 120 s to catch
the presence window.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

# repo root + examples on the path so this runs from anywhere
_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "examples"))

from auth_from_env import auth_from_env  # noqa: E402
from aqara_ble.client import U200Client  # noqa: E402


def _load_dotenv() -> None:
    path = _ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _build_transport(kind: str):
    if kind == "bleak":
        from aqara_ble.transport import BleakTransport
        return BleakTransport()
    if kind == "bumble":
        from aqara_ble.transport import BumbleTransport
        port = os.environ["AQARA_ESP32_PORT"]
        return BumbleTransport(port)
    from aqara_ble.esphome_transport import EsphomeProxyTransport
    return EsphomeProxyTransport(
        os.environ["AQARA_ESPHOME_HOST"], noise_psk=os.environ["AQARA_ESPHOME_NOISE_PSK"]
    )


async def change_language(bin_path: Path, transport_kind: str) -> bool:
    blob = bin_path.read_bytes()
    filename = bin_path.name  # e.g. U200_ES_audio_burn.bin — the lock keys on this
    lock = await U200Client.connect(
        auth=auth_from_env(),
        transport=_build_transport(transport_kind),
        device_id=os.environ["AQARA_DEVICE_ID"],
        mac=os.environ["AQARA_LOCK_MAC"],
        region=os.environ.get("AQARA_REGION", "EU"),
    )
    async with lock:
        print(f"[connected] pushing {filename} ({len(blob)} bytes)")
        result = await lock.push_voice_pack_ota(
            blob,
            filename,
            manifest_wait_s=120.0,        # re-send manifest to catch the presence window
            post_manifest_settle_s=0.0,
            keepalive_every_s=2.0,
            progress=lambda sent, total, acks: print(f"  {sent}/{total}  acks={acks}", end="\r"),
        )
    ok = bool(result.completed) and (result.final_status or {}).get("xfer_statu") == "success"
    print(f"\n[result] completed={result.completed} status={result.final_status}")
    if ok:
        print("🎯 language applied.")
    return ok


def main() -> int:
    _load_dotenv()
    ap = argparse.ArgumentParser(description="Change the U200 language over BLE (from scratch).")
    ap.add_argument("bin", type=Path, help="voice pack .bin (e.g. captures/U200_ES_audio_burn.bin)")
    ap.add_argument("--transport", choices=("esphome", "bumble", "bleak"), default="esphome")
    args = ap.parse_args()
    if not args.bin.is_file():
        print(f"no such file: {args.bin}", file=sys.stderr)
        return 2
    return 0 if asyncio.run(change_language(args.bin, args.transport)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
