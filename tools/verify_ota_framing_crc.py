#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# SPDX-FileCopyrightText: 2026 dani811 <https://github.com/dani811/Aqara>
#
# This file is part of Aqara BLE, licensed under the GNU Affero General Public
# License v3.0 (AGPL-3.0-only). You may use, study, share and modify it; any
# distributed or network-served derivative must stay licensed under the AGPL
# and keep this notice. See the LICENSE file for the full terms.

"""Verified OTA language-transfer framing for the U200 (offline, 2026-09-02).

The ff91 YMODEM data stream (each ATT write = 0x11 + payload, concatenated and
0x11-stripped) is, per 1024-byte block of the language `.bin`:

    [02 <seq> <0xff-seq>]  ||  block[1024]  ||  CRC16-XMODEM(block) big-endian

  * seq = 01, 02, 03, ...   (marker byte = 0xff - seq)
  * block = blob[1024*n : 1024*(n+1)]   (last block per file is short)
  * trailing 2-byte field = CRC-16/XMODEM (poly 0x1021, init 0x0000,
    refin/refout=false, xorout=0), big-endian.  <-- this is the framing CRC.

Note the OTHER CRC in this protocol: the encrypted short-pack's
`getMijiaCrc16String` is CRC-16/MODBUS (poly 0x8005, init 0xFFFF, reflected) over
`mainCmd||subCmd||data`. Different CRC — don't conflate. See
docs/devices/u200/ota-0x90-investigation.md.

Verified 11/11 blocks against captures/ota/btsnoop_end.log +
captures/U200_FR_audio_burn.bin (blk1 field b605 == XMODEM == the live "b6 05").

Usage:
    python3 tools/verify_ota_framing_crc.py                 # verify the capture
    python3 tools/verify_ota_framing_crc.py <snoop> <bin>
"""
from __future__ import annotations

import sys

DEFAULT_SNOOP = "captures/ota/btsnoop_end.log"
DEFAULT_BIN = "captures/U200_FR_audio_burn.bin"
BLOCK = 1024


def crc16_xmodem(data: bytes) -> int:
    """Framing per-block CRC (poly 0x1021, init 0x0000, no reflection)."""
    crc = 0x0000
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if (crc & 0x8000) else (crc << 1) & 0xFFFF
    return crc


def crc16_modbus(data: bytes) -> int:
    """Short-pack CRC (getMijiaCrc16String): poly 0x8005, init 0xFFFF, reflected."""
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if (crc & 1) else crc >> 1
    return crc


def frame_block(seq: int, block: bytes) -> bytes:
    """Build one framed data segment (WITHOUT the leading 0x11 ff91 write prefix).

    seq is 1-based. Caller prepends 0x11 per ATT write and fragments to MTU.
    """
    marker = bytes([0x02, seq & 0xFF, (0xFF - seq) & 0xFF])
    return marker + block + crc16_xmodem(block).to_bytes(2, "big")


def build_stream(blob: bytes) -> bytes:
    """Segment a language .bin into the full framed ff91 data stream."""
    out = bytearray()
    seq = 1
    for off in range(0, len(blob), BLOCK):
        out += frame_block(seq, blob[off:off + BLOCK])
        seq += 1
    return bytes(out)


def _verify(snoop: str, binp: str) -> int:
    sys.path.insert(0, "tools")
    from decode_ota_framing import att_writes  # noqa: PLC0415

    blob = open(binp, "rb").read()
    frames = list(att_writes(snoop))
    start = next(i for i, (_n, v) in enumerate(frames)
                 if v[:1] == b"\x11" and b".bin\x00" in v) + 1
    stream = bytearray()
    for i in range(start, len(frames)):
        _n, v = frames[i]
        if v and v[0] == 0x11:
            stream += v[1:]
        else:
            break

    ok = 0
    pos = 0
    blob_off = 0
    seq = 1
    while pos + 3 <= len(stream):
        hdr = bytes([0x02, seq & 0xFF, (0xFF - seq) & 0xFF])
        if stream[pos:pos + 3] != hdr:
            break
        pos += 3
        nxt = bytes([0x02, (seq + 1) & 0xFF, (0xFF - (seq + 1)) & 0xFF])
        npos = stream.find(nxt, pos)
        end = npos if npos != -1 else len(stream)
        payload = bytes(stream[pos:end - 2])
        field = int.from_bytes(stream[end - 2:end], "big")
        good = (blob[blob_off:blob_off + len(payload)] == payload
                and crc16_xmodem(payload) == field)
        ok += good
        if not good and seq <= 3:
            print(f"blk{seq}: MISMATCH field={field:#06x} calc={crc16_xmodem(payload):#06x}")
        blob_off += len(payload)
        pos = end
        seq += 1
    print(f"framing verified: {ok} blocks OK, covered {blob_off} bytes "
          f"({100*blob_off/len(blob):.1f}% of the {len(blob)}-byte bundle in this capture window)")
    # spot-check the reusable builder reproduces the capture's first blocks
    rebuilt = build_stream(blob)[:len(stream)]
    print(f"build_stream() reproduces captured stream prefix: {rebuilt == bytes(stream[:len(rebuilt)])}")
    return 0 if ok else 1


if __name__ == "__main__":
    snoop = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SNOOP
    binp = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_BIN
    raise SystemExit(_verify(snoop, binp))
