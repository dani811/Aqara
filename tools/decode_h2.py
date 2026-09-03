#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# SPDX-FileCopyrightText: 2026 dani811 <https://github.com/dani811/Aqara>
#
# This file is part of Aqara BLE, licensed under the GNU Affero General Public
# License v3.0 (AGPL-3.0-only). You may use, study, share and modify it; any
# distributed or network-served derivative must stay licensed under the AGPL
# and keep this notice. See the LICENSE file for the full terms.

"""Reassemble HTTP/2 + HPACK from an sslfull.js log.

Fixes two known BoringSSL/Frida quirks (per specs/037-cloud-session-mitm):
1. SSL* pointers get reused across sequential connections -> split each
   pointer's WRITE stream on the client preface, bucket both directions by
   time into per-connection "segments".
2. SSL_write is exported by two modules -> every logical write is logged
   twice with identical bytes; dedup consecutive identical entries.
"""
from __future__ import annotations

import re
import sys
import gzip
from collections import defaultdict

try:
    from hpack import Decoder as HpackDecoder
except ImportError:
    print("pip install hpack", file=sys.stderr)
    raise

PREFACE = bytes.fromhex("505249202a20485454502f322e300d0a0d0a534d0d0a0d0a")

ENTRY_RE = re.compile(
    r"==== (\d+) SSL_(read|write) \[([^\]]+)\] ssl=(0x[0-9a-f]+) len=(\d+) ====\n([0-9a-f]*)"
)


def parse_entries(path):
    text = open(path, encoding="utf-8", errors="replace").read()
    entries = []
    for m in ENTRY_RE.finditer(text):
        ts, direction, module, ssl, length, hexdata = m.groups()
        entries.append({
            "ts": int(ts), "dir": direction, "module": module,
            "ssl": ssl, "len": int(length), "hex": hexdata,
        })
    entries.sort(key=lambda e: e["ts"])
    return entries


def dedup(entries):
    out = []
    prev = None
    for e in entries:
        if prev and prev["dir"] == e["dir"] and prev["ssl"] == e["ssl"] and prev["hex"] == e["hex"]:
            continue
        out.append(e)
        prev = e
    return out


def segment(entries):
    """Assign each entry to (ssl, segment_index) using preface positions on writes."""
    preface_ts = defaultdict(list)
    for e in entries:
        if e["dir"] == "write" and bytes.fromhex(e["hex"]).startswith(PREFACE):
            preface_ts[e["ssl"]].append(e["ts"])
    for ts_list in preface_ts.values():
        ts_list.sort()

    buckets = defaultdict(list)  # (ssl, seg_idx) -> [entries] preserving order
    for e in entries:
        ts_list = preface_ts.get(e["ssl"], [])
        seg_idx = sum(1 for t in ts_list if t <= e["ts"]) - 1
        if seg_idx < 0:
            seg_idx = 0  # entries before any known preface: lump into segment 0
        buckets[(e["ssl"], seg_idx)].append(e)
    return buckets


def parse_h2_frames(data: bytes):
    frames = []
    i = 0
    while i + 9 <= len(data):
        length = int.from_bytes(data[i:i + 3], "big")
        ftype = data[i + 3]
        flags = data[i + 4]
        stream_id = int.from_bytes(data[i + 5:i + 9], "big") & 0x7FFFFFFF
        payload = data[i + 9:i + 9 + length]
        if len(payload) < length:
            break  # truncated
        frames.append((ftype, flags, stream_id, payload))
        i += 9 + length
    return frames


FRAME_NAMES = {0: "DATA", 1: "HEADERS", 2: "PRIORITY", 3: "RST_STREAM",
               4: "SETTINGS", 5: "PUSH_PROMISE", 6: "PING", 7: "GOAWAY",
               8: "WINDOW_UPDATE", 9: "CONTINUATION"}


def strip_headers_padding_priority(payload, flags):
    pad_len = 0
    off = 0
    if flags & 0x08:  # PADDED
        pad_len = payload[0]
        off = 1
    if flags & 0x20:  # PRIORITY
        off += 5
    end = len(payload) - pad_len
    return payload[off:end]


def reconstruct(entries_for_conn, label):
    by_stream_headers = defaultdict(list)  # stream_id -> list of header-block fragments
    by_stream_headers_done = {}
    by_stream_data = defaultdict(bytearray)
    decoder = HpackDecoder()
    raw = b"".join(bytes.fromhex(e["hex"]) for e in entries_for_conn)
    if raw.startswith(PREFACE):
        raw = raw[len(PREFACE):]
    frames = parse_h2_frames(raw)
    results = []
    for ftype, flags, stream_id, payload in frames:
        name = FRAME_NAMES.get(ftype, hex(ftype))
        if ftype == 1:  # HEADERS
            block = strip_headers_padding_priority(payload, flags)
            by_stream_headers[stream_id].append(block)
            if flags & 0x04:  # END_HEADERS
                full = b"".join(by_stream_headers[stream_id])
                try:
                    headers = decoder.decode(full)
                except Exception as exc:
                    headers = [("<hpack error>", str(exc))]
                by_stream_headers_done[stream_id] = headers
                results.append((label, stream_id, "HEADERS", headers))
        elif ftype == 9:  # CONTINUATION
            by_stream_headers[stream_id].append(payload)
            if flags & 0x04:
                full = b"".join(by_stream_headers[stream_id])
                try:
                    headers = decoder.decode(full)
                except Exception as exc:
                    headers = [("<hpack error>", str(exc))]
                by_stream_headers_done[stream_id] = headers
                results.append((label, stream_id, "HEADERS", headers))
        elif ftype == 0:  # DATA
            by_stream_data[stream_id] += payload
            if flags & 0x01:  # END_STREAM
                body = bytes(by_stream_data[stream_id])
                results.append((label, stream_id, "DATA", body))
        else:
            pass  # SETTINGS/WINDOW_UPDATE/PING/etc — not interesting here
    return results


def main():
    path = sys.argv[1]
    grep_filter = sys.argv[2] if len(sys.argv) > 2 else None
    entries = dedup(parse_entries(path))
    print(f"parsed {len(entries)} deduped entries", file=sys.stderr)
    buckets = segment(entries)
    print(f"{len(buckets)} connection segments", file=sys.stderr)
    for (ssl, seg_idx), conn_entries in sorted(buckets.items(), key=lambda kv: kv[1][0]["ts"]):
        writes = [e for e in conn_entries if e["dir"] == "write"]
        reads = [e for e in conn_entries if e["dir"] == "read"]
        label_w = f"{ssl}#{seg_idx} C->S"
        label_r = f"{ssl}#{seg_idx} S->C"
        for label, ents in ((label_w, writes), (label_r, reads)):
            try:
                results = reconstruct(ents, label)
            except Exception as exc:
                print(f"[{label}] reconstruct failed: {exc}", file=sys.stderr)
                continue
            for lbl, stream_id, kind, val in results:
                if kind == "HEADERS":
                    text = " | ".join(f"{k}={v}" for k, v in val)
                else:
                    body = val
                    try:
                        if body[:2] == b"\x1f\x8b":
                            body = gzip.decompress(body)
                        text = body.decode("utf-8", errors="replace")
                    except Exception:
                        text = body.hex()
                if grep_filter and grep_filter.lower() not in text.lower():
                    continue
                print(f"[{lbl} stream={stream_id} {kind}] {text[:2000]}")


if __name__ == "__main__":
    main()
