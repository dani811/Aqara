#!/usr/bin/env python3
"""Dump any Aqara-family device's full GATT database (services + chars + handles).

This is the tool for **Step 2 of the porting guide** ("Identify the GATT map"):
point it at a new device and it enumerates every service, characteristic, value
handle, properties and descriptor over a real BLE link — the raw material for
that device's ``docs/devices/<device>/gatt-map.md``.

Read-only: it only does service discovery, never authenticates and never writes.

Transport:
- ``--transport bumble --port serial:/dev/cu.usbmodemNNNN,115200`` (ESP32-S3 HCI)
  — required on macOS to see the Matter ``fff6`` service, which CoreBluetooth hides.
- ``--transport bleak`` — native OS adapter (Linux/BlueZ sees everything; macOS
  CoreBluetooth aborts a full connect on the Matter service, so bumble is safer).

Target:
- ``--mac AA:BB:..`` or the ``AQARA_LOCK_MAC`` env var. Omit to connect to the
  first Aqara candidate the scan identifies (handy on a brand-new device whose
  MAC you don't know yet).

Examples:
    # U200 over the ESP32-S3, mac + port from .env:
    .venv/bin/python tools/dump_gatt.py --transport bumble

    # A new device, native adapter, identify by advert:
    .venv/bin/python tools/dump_gatt.py --transport bleak

    # Flag a specific value handle (e.g. the U200's OTA channel at 0x3c):
    .venv/bin/python tools/dump_gatt.py --transport bumble --flag-handle 0x3c
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))


def _load_dotenv() -> None:
    """Populate os.environ from .env without shell interpretation (values may
    hold ``&``/``!`` that break ``. ./.env`` under zsh). Existing env wins."""
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


def _hx(v: object) -> str:
    try:
        return f"0x{int(v):04x} ({int(v)})"
    except (TypeError, ValueError):
        return str(v)


def _make_transport(args: argparse.Namespace):
    from aqara_ble.transport import BleakTransport, BumbleTransport  # noqa: PLC0415

    if args.transport == "bleak":
        return BleakTransport()
    port = args.port or os.environ.get("AQARA_ESP32_PORT")
    if not port:
        raise SystemExit("[config] --transport bumble needs --port or AQARA_ESP32_PORT")
    return BumbleTransport(port)


async def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--transport", choices=("bleak", "bumble"), default="bumble")
    ap.add_argument("--port", help="bumble transport spec, e.g. serial:/dev/cu.usbmodemNNNN,115200")
    ap.add_argument("--mac", help="target MAC (overrides AQARA_LOCK_MAC); omit to identify by advert")
    ap.add_argument("--timeout", type=float, default=20.0, help="scan timeout seconds (default 20)")
    ap.add_argument(
        "--flag-handle",
        action="append",
        default=[],
        help="value handle to highlight, e.g. 0x3c (repeatable). Purely cosmetic.",
    )
    args = ap.parse_args()

    _load_dotenv()

    flagged = set()
    for h in args.flag_handle:
        try:
            flagged.add(int(h, 0))
        except ValueError:
            print(f"[warn] ignoring un-parseable --flag-handle {h!r}")

    mac = args.mac or os.environ.get("AQARA_LOCK_MAC") or None
    transport = _make_transport(args)
    try:
        print(f"[scan] {transport.name}, {args.timeout:g}s"
              + (f", mac={mac}" if mac else ", identify by advert")
              + " (touch the keypad / fire the fingerbot so it advertises)")
        candidates = await transport.scan(args.timeout, mac=mac)
        if not candidates:
            print("[scan] no Aqara device found — wake it and retry")
            return 1
        target = candidates[0]
        print(f"[scan] {target.address}  name={target.name!r}  model={target.model}  rssi={target.rssi}")
        print("[connect] connecting + discovering …")
        client = await asyncio.wait_for(transport.connect(target, timeout=40.0), timeout=45.0)

        # Both adapters expose the discovered DB, but shape differs:
        #  - BumbleGattAdapter has `.peer.services` (bumble CharacteristicProxy: .handle, .properties)
        #  - BleakClient has `.services` (BleakGATTService/Characteristic: .handle, .properties)
        peer = getattr(client, "peer", None)
        services = list(peer.services) if peer is not None else list(client.services)

        print("\n=== GATT DATABASE ===")
        hits = []
        for svc in services:
            s_start = getattr(svc, "handle", "?")
            s_end = getattr(svc, "end_group_handle", getattr(svc, "end_handle", "?"))
            print(f"\nSERVICE {svc.uuid}  handles {_hx(s_start)}..{_hx(s_end)}")
            for ch in svc.characteristics:
                v_handle = getattr(ch, "handle", None)
                props = getattr(ch, "properties", "")
                star = "  <<<" if _to_int(v_handle) in flagged else ""
                print(f"  CHAR {ch.uuid}  value_handle={_hx(v_handle)}  props={props}{star}")
                if _to_int(v_handle) in flagged:
                    hits.append((_to_int(v_handle), str(ch.uuid), str(props), str(svc.uuid)))
                for desc in getattr(ch, "descriptors", []) or []:
                    print(f"      DESC {desc.uuid}  handle={_hx(getattr(desc, 'handle', '?'))}")

        if flagged:
            print("\n=== flagged handles ===")
            if hits:
                for h, uuid, props, svc in sorted(hits):
                    print(f"  handle {_hx(h)}  uuid={uuid}  props={props}  service={svc}")
            else:
                print("  (none of the requested handles were present — handles are "
                      "not stable across firmware; match by service/props instead)")

        print("\n[next] write this into docs/devices/<device>/gatt-map.md and map each "
              "characteristic to its channel role (see porting-guide.md Step 2).")
    finally:
        await transport.disconnect()
    return 0


def _to_int(v: object) -> int | None:
    try:
        return int(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
