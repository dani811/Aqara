#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# SPDX-FileCopyrightText: 2026 dani811 <https://github.com/dani811/Aqara>
#
# This file is part of Aqara BLE, licensed under the GNU Affero General Public
# License v3.0 (AGPL-3.0-only). You may use, study, share and modify it; any
# distributed or network-served derivative must stay licensed under the AGPL
# and keep this notice. See the LICENSE file for the full terms.

"""Decode the U200 language-OTA per-chunk framing by aligning a captured
transfer against the known bundle bytes.

We confirmed the BLE transfer streams the voice `.bin` verbatim after an init
frame, each chunk wrapped as `11 <header...> <payload = slice of .bin>`. This
tool recovers the exact header layout: for each 0x11 chunk (in order) it finds
the header length H that makes `chunk[H:]` equal the next contiguous slice of
the `.bin`, then prints the header bytes vs. the running bundle offset so the
seq/marker formula can be read off.

    python3 tools/decode_ota_framing.py <btsnoop.log> <bundle.bin>
"""
from __future__ import annotations

import struct
import sys


def att_writes(path: str, target: int = 0x3C):
    """Yield (pkt_index, value_bytes) for every ATT WriteCmd/Req on `target`."""
    with open(path, "rb") as f:
        data = f.read()
    assert data[:8] == b"btsnoop\x00", "not a btsnoop file"
    off = 16
    n = 0
    while off + 24 <= len(data):
        _ol, incl, _fl, _dr, _ts = struct.unpack(">IIIIq", data[off:off + 24])
        off += 24
        pkt = data[off:off + incl]
        off += incl
        n += 1
        if not pkt or pkt[0] != 0x02:
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
        if cid != 0x0004:
            continue
        att = l2cap[4:4 + l2_len]
        if len(att) < 3 or att[0] not in (0x52, 0x12):
            continue
        if struct.unpack("<H", att[1:3])[0] != target:
            continue
        yield n, att[3:]


def main(snoop: str, binp: str) -> int:
    with open(binp, "rb") as fh:
        blob = fh.read()
    print(f"bundle: {binp}  {len(blob)} bytes")

    frames = list(att_writes(snoop))
    print(f"captured {len(frames)} ATT writes on 0x3c\n")

    # Find the init frame: 11 0100 ff <ascii filename> 00 <ascii size>
    start_idx = None
    for i, (_n, v) in enumerate(frames):
        if v[:1] == b"\x11" and b".bin\x00" in v:
            print(f"init frame @capture#{i}: {v[:4].hex()} | {v[4:].split(b'/'+b'/')[0][:40]!r}")
            start_idx = i + 1
            break
    if start_idx is None:
        print("!! init frame not found in this capture (buffer rotated past it)")
        return 1

    offset = 0
    decoded = 0
    header_shapes = {}
    rows = []
    for i in range(start_idx, len(frames)):
        _n, v = frames[i]
        if not v or v[0] != 0x11:
            rows.append((i, "non-0x11", v[:6].hex(), None, None))
            continue
        # Find header length H s.t. v[H:] == blob[offset: offset+len(v)-H]
        matchedH = None
        for H in range(2, 8):
            pl = v[H:]
            if pl and blob[offset:offset + len(pl)] == pl:
                matchedH = H
                break
        if matchedH is None:
            # maybe a gap (missed packets) — try to relocate by searching
            found = -1
            for H in range(2, 8):
                pl = v[H:]
                if len(pl) >= 16:
                    p = blob.find(pl)
                    if p != -1:
                        found, matchedH = p, H
                        break
            if matchedH is None:
                rows.append((i, "NO-MATCH", v[:8].hex(), None, len(v)))
                break
            offset = found
        header = v[:matchedH]
        pl = v[matchedH:]
        rows.append((i, "chunk", header.hex(), offset, len(pl)))
        header_shapes[matchedH] = header_shapes.get(matchedH, 0) + 1
        offset += len(pl)
        decoded += 1

    print(f"decoded {decoded} chunks; header-length histogram: {header_shapes}\n")
    print("idx   kind      header(hex)     bin_offset   payload_len")
    for (i, kind, hdr, ofs, pl) in rows[:40]:
        print(f"{i:<5} {kind:<9} {hdr:<15} {ofs!s:<12} {pl}")
    print("...")
    print("last rows:")
    for (i, kind, hdr, ofs, pl) in rows[-8:]:
        print(f"{i:<5} {kind:<9} {hdr:<15} {ofs!s:<12} {pl}")
    print(f"\nbundle covered: {offset} / {len(blob)} bytes ({100*offset/len(blob):.1f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1], sys.argv[2]))
