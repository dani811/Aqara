#!/usr/bin/env python3
"""Full language OTA over an ESPHome bluetooth_proxy using bleak-esphome's OWN
client stack (the reference implementation every HA proxy-BLE integration uses).

Instead of the hand-rolled EsphomeProxyGattClient (which mishandles the v3
REMOTE_CACHING CCCD write and reconnects), this bootstraps a habluetooth manager,
wires bleak-esphome's scanner to the proxy, gets a real ``BLEDevice`` for the lock,
and connects a real ``BleakClient`` (ESPHomeClient backend). That client is fed to
the existing aqara_ble session — the same bleak path that already works on macOS.
"""
from __future__ import annotations

import asyncio
import os
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples"))


def _le(p: Path) -> None:
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_le(Path(__file__).resolve().parents[1] / ".env")

import habluetooth
from aioesphomeapi import APIClient
from bleak_esphome import connect_scanner
from habluetooth import BluetoothManager, HaBleakClientWrapper


class _Manager(BluetoothManager):
    """Minimal standalone habluetooth manager (HA provides its own subclass)."""

    def _discover_service_info(self, service_info) -> None:  # noqa: ANN001
        return None


async def _press_fingerbot() -> None:
    """Best-effort keypad wake via the HA fingerbot (optional)."""
    # Driven externally in this session; nothing to do here.
    return None


async def main() -> int:
    host = os.environ.get("AQARA_ESPHOME_HOST", "192.168.68.234")
    psk = os.environ["AQARA_ESPHOME_NOISE_PSK"]
    mac = os.environ["AQARA_LOCK_MAC"]

    mgr = _Manager()
    await mgr.async_setup()
    habluetooth.set_manager(mgr)
    print("[boot] habluetooth manager up", flush=True)

    cli = APIClient(host, 6053, "", noise_psk=psk)
    await cli.connect(login=True)
    di = await cli.device_info()
    print(f"[proxy] {di.name} bt_flags={di.bluetooth_proxy_feature_flags}", flush=True)

    data = connect_scanner(cli, di, available=True)
    data.scanner.async_setup()
    unregister = mgr.async_register_scanner(data.scanner, connection_slots=3)
    # bluetooth_device was created available=True by connect_scanner, so the
    # can_connect gate is already open.
    print("[scanner] registered; waiting for the lock advertisement", flush=True)

    # Wait for the lock's BLEDevice to appear (press the fingerbot now).
    device = None
    for _ in range(80):
        device = mgr.async_ble_device_from_address(mac, connectable=True)
        if device is not None:
            break
        await asyncio.sleep(1)
    if device is None:
        print("[scanner] lock never advertised (press the keypad)", file=sys.stderr)
        return 2
    print(f"[scanner] got BLEDevice {device.address} rssi={getattr(device,'rssi',None)}", flush=True)

    # HaBleakClientWrapper routes to the ESPHomeClient backend (via the device's
    # connector) instead of the host CoreBluetooth stack.
    client = HaBleakClientWrapper(device)
    await client.connect()
    print(f"[ble] connected via ESPHome proxy backend, mtu={client.mtu_size}", flush=True)

    # Hand the connected BleakClient to the aqara_ble session via a pass-through
    # transport, then run the language OTA.
    from auth_from_env import auth_from_env

    from aqara_ble.client import U200Client

    class _PreConnected:
        name = "esphome-bleak"

        async def scan(self, *a, **k):  # noqa: ANN002, ANN003
            return []

        async def connect(self, target, *, timeout):  # noqa: ANN001
            return client

        async def disconnect(self) -> None:
            import contextlib

            with contextlib.suppress(Exception):
                await client.disconnect()

    auth = auth_from_env()
    pack = os.environ.get("AQARA_OTA_PACK", "U200_ES_audio_burn.bin")
    blob = Path(f"captures/{pack}").read_bytes()
    try:
        async with await U200Client.connect(
            auth=auth, transport=_PreConnected(), device_id=os.environ["AQARA_DEVICE_ID"],
            mac=mac, region=os.environ.get("AQARA_REGION", "EU"), scan_timeout=30,
        ) as lock:
            print("[session] authenticated; starting voice pack OTA", flush=True)
            r = await lock.push_voice_pack_ota(
                blob, pack, arm=True, data_delay=0.03,
                manifest_wait_s=120.0, post_manifest_settle_s=12.0,
                progress=lambda s, t, a: print(f"  [{s}/{t}] acks={a}", flush=True),
            )
            ok = isinstance(r.final_status, dict) and r.final_status.get("xfer_statu") == "success"
            print(f"[result] completed={r.completed} status={r.final_status} "
                  f"frames={r.frames_sent} acks={len(r.acks)} stalled_at={r.stalled_at}", flush=True)
            print(f"[result] last acks: {[a for _, a in r.acks[-12:]]}", flush=True)
            return 0 if ok else 1
    except Exception:
        print("=== TRACEBACK ===", flush=True)
        traceback.print_exc()
        return 1
    finally:
        unregister()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
