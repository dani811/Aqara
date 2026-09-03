#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# SPDX-FileCopyrightText: 2026 dani811 <https://github.com/dani811/Aqara>
#
# This file is part of Aqara BLE, licensed under the GNU Affero General Public
# License v3.0 (AGPL-3.0-only). You may use, study, share and modify it; any
# distributed or network-served derivative must stay licensed under the AGPL
# and keep this notice. See the LICENSE file for the full terms.

"""Smoke-test an external HCI controller with Bumble: HCI Reset + Read Local Version.

Usage: python tools/hci_smoke.py serial:/dev/cu.usbmodemNNNN,115200
(defaults to $AQARA_ESP32_PORT). Prints the controller's version block; no
secrets involved. See tools/esp32s3_hci_usb/README.md.
"""

from __future__ import annotations

import asyncio
import os
import sys


async def main(port: str) -> int:
    from bumble.host import Host  # noqa: PLC0415
    from bumble.transport import open_transport  # noqa: PLC0415

    async with await open_transport(port) as (source, sink):
        host = Host(source, sink)
        await asyncio.wait_for(host.reset(), timeout=10)
        print(f"controller on {port} answered HCI Reset")
        print("local version:", host.local_version)
    return 0


if __name__ == "__main__":
    spec = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("AQARA_ESP32_PORT")
    if not spec:
        raise SystemExit(
            "usage: hci_smoke.py serial:/dev/cu.usbmodemNNNN,115200 (or set AQARA_ESP32_PORT)"
        )
    raise SystemExit(asyncio.run(main(spec)))
