#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# SPDX-FileCopyrightText: 2026 dani811 <https://github.com/dani811/Aqara>
#
# This file is part of Aqara BLE, licensed under the GNU Affero General Public
# License v3.0 (AGPL-3.0-only). You may use, study, share and modify it; any
# distributed or network-served derivative must stay licensed under the AGPL
# and keep this notice. See the LICENSE file for the full terms.

"""Language OTA over the ESPHome proxy, resuming across mid-stream link drops.

The proxy<->lock BLE link drops at a variable point (22 s .. ~50 %). Rather than
restart, this keeps the habluetooth manager / APIClient / scanner alive and, on
each drop, reconnects the BLE and RESUMES the transfer from the last acked block
(``skip_manifest=True`` so the lock's receiver is not reset). If the lock keeps
its OTA state across the reconnect, the transfer completes in chunks.
"""
from __future__ import annotations

import asyncio
import contextlib
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
    def _discover_service_info(self, service_info) -> None:  # noqa: ANN001
        return None


async def main() -> int:
    host = os.environ.get("AQARA_ESPHOME_HOST", "192.168.68.234")
    psk = os.environ["AQARA_ESPHOME_NOISE_PSK"]
    mac = os.environ["AQARA_LOCK_MAC"]
    total_blocks = 1984  # 2031272 B / 1024

    mgr = _Manager()
    await mgr.async_setup()
    habluetooth.set_manager(mgr)
    cli = APIClient(host, 6053, "", noise_psk=psk)
    await cli.connect(login=True)
    di = await cli.device_info()
    print(f"[proxy] {di.name} exclusive", flush=True)
    data = connect_scanner(cli, di, available=True)
    data.scanner.async_setup()
    unregister = mgr.async_register_scanner(data.scanner, connection_slots=3)

    from auth_from_env import auth_from_env

    from aqara_ble.client import U200Client

    auth = auth_from_env()
    blob = Path("captures/U200_ES_audio_burn.bin").read_bytes()

    resume_block = 0
    try:
        for chunk in range(12):
            print(f"\n===== chunk {chunk} resume_from={resume_block} =====", flush=True)
            device = None
            for _ in range(70):
                device = mgr.async_ble_device_from_address(mac, connectable=True)
                if device is not None:
                    break
                await asyncio.sleep(1)
            if device is None:
                print("[wait] lock not advertising (press keypad)", file=sys.stderr, flush=True)
                continue
            client = HaBleakClientWrapper(device)
            try:
                await client.connect()
            except Exception as exc:  # noqa: BLE001
                print(f"[connect] failed: {exc}", flush=True)
                continue
            print(f"[ble] connected mtu={client.mtu_size}", flush=True)

            best = {"blocks": resume_block}

            def _progress(sent: int, t: int, acks: int) -> None:
                # good block-acks ~= blocks confirmed this session start + acks
                blk = resume_block + acks
                best["blocks"] = max(best["blocks"], blk)
                print(f"  [{sent}/{t}] acks={acks} ~block={blk}", flush=True)

            class _Pre:
                name = "esphome-bleak"

                async def scan(self, *a, **k):  # noqa: ANN002, ANN003
                    return []

                async def connect(self, target, *, timeout):  # noqa: ANN001
                    return client

                async def disconnect(self) -> None:
                    with contextlib.suppress(Exception):
                        await client.disconnect()

            try:
                async with await U200Client.connect(
                    auth=auth, transport=_Pre(), device_id=os.environ["AQARA_DEVICE_ID"],
                    mac=mac, region=os.environ.get("AQARA_REGION", "EU"), scan_timeout=30,
                ) as lock:
                    r = await lock.push_voice_pack_ota(
                        blob, "U200_ES_audio_burn.bin", arm=(chunk == 0),
                        data_delay=0.006, resume_from=resume_block,
                        skip_manifest=(chunk > 0), manifest_wait_s=120.0,
                        post_manifest_settle_s=12.0, progress=_progress,
                    )
                    good = sum(1 for _, a in r.acks if a == b"\x11\x06")
                    reached = resume_block + good
                    print(f"[chunk {chunk}] status={r.final_status} good_acks={good} reached~{reached}", flush=True)
                    if isinstance(r.final_status, dict) and r.final_status.get("xfer_statu") == "success":
                        print("🎯🎯🎯 OTA SUCCESS — language applied", flush=True)
                        return 0
                    if reached <= resume_block + 2:
                        print("[resume] no forward progress → lock reset its OTA state on reconnect; resume not supported", flush=True)
                        # keep trying from 0 only on chunk 0 semantics
                        if chunk > 0:
                            return 1
                    resume_block = max(resume_block, reached, best["blocks"])
            except Exception:  # noqa: BLE001
                print("--- chunk error ---", flush=True)
                traceback.print_exc()
            finally:
                with contextlib.suppress(Exception):
                    await client.disconnect()
            await asyncio.sleep(4)
        print(f"[done] exhausted chunks, reached ~{resume_block}/{total_blocks}", flush=True)
        return 1
    finally:
        unregister()
        with contextlib.suppress(Exception):
            await cli.disconnect()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
