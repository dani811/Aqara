#!/usr/bin/env python3
"""Minimal btsnoop parser: dump ATT writes/notifications for one handle.

Built for the 2026-08-31 OTA voice-pack capture (handle 60, 0x003c) but
generic — pass any ATT handle. Parses the raw btsnoop file straight from
`adb bugreport`'s `FS/data/misc/bluetooth/logs/btsnoop_hci.log`, no root
needed. Complements `scratchpad/app_keystream.py` (which decrypts the
AES-CCM control channel on ff61/ff62): this one is for handles that are
NOT encrypted with the session cipher, like the OTA transfer channel,
where the ATT payload is directly meaningful.

Usage:
    python3 tools/parse_att_handle.py btsnoop_hci.log [handle_hex]

`handle_hex` defaults to 0x3c (the OTA voice-pack handle). Pass e.g. `3d`
to inspect a different one.
"""
import struct
import sys


def printable(b: bytes) -> str:
    return "".join(chr(c) if 32 <= c < 127 else "." for c in b)


def main(path: str, target_handle: int) -> None:
    with open(path, "rb") as f:
        data = f.read()
    assert data[:8] == b"btsnoop\x00", "not a btsnoop file"
    off = 16  # file header: 8 magic + 4 version + 4 datalink
    n = 0
    hits = 0
    while off < len(data):
        if off + 24 > len(data):
            break
        _orig_len, incl_len, _flags, _drops, ts = struct.unpack(">IIIIq", data[off : off + 24])
        off += 24
        pkt = data[off : off + incl_len]
        off += incl_len
        n += 1
        if not pkt or pkt[0] != 0x02:  # ACL data only
            continue
        body = pkt[1:]
        if len(body) < 4:
            continue
        acl_len = struct.unpack("<H", body[2:4])[0]
        l2cap = body[4 : 4 + acl_len]
        if len(l2cap) < 4:
            continue
        l2_len = struct.unpack("<H", l2cap[0:2])[0]
        cid = struct.unpack("<H", l2cap[2:4])[0]
        if cid != 0x0004:  # ATT
            continue
        att = l2cap[4 : 4 + l2_len]
        if len(att) < 3:
            continue
        opcode = att[0]
        # Write Command = 0x52, Write Request = 0x12, Handle Value Notification = 0x1b
        if opcode not in (0x52, 0x12, 0x1b):
            continue
        att_handle = struct.unpack("<H", att[1:3])[0]
        if att_handle != target_handle:
            continue
        value = att[3:]
        hits += 1
        op_name = {0x52: "WriteCmd", 0x12: "WriteReq", 0x1b: "Notify"}[opcode]
        print(f"[{n}] ts={ts} {op_name} handle=0x{att_handle:04x} len={len(value)}")
        print("  hex:", value[:32].hex(), "..." if len(value) > 32 else "")
        print("  txt:", printable(value[:80]))
    print(f"total packets={n}, handle-0x{target_handle:04x} ATT writes/notifies={hits}", file=sys.stderr)


if __name__ == "__main__":
    handle = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0x3C
    main(sys.argv[1], handle)
