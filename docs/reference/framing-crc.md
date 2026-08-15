# Frame checksum — CRC-16/ARC

**Layer:** transversal

> The single field that gated the whole project. Get it wrong and the lock
> answers every authentication attempt with an empty ACK. Get it right and the
> handshake opens.

## What it is

The authentication frame header carries a 2-byte field (bytes 7–8) that looks
random because it changes every session. It is **not** a token or a nonce — it is
the **CRC-16/ARC of the frame body**, stored little-endian.

Because each session exchanges a fresh ephemeral public key, the checksum over
that key changes too, which is exactly why it was long mistaken for a random
"app token".

## The algorithm

CRC-16/ARC (a.k.a. CRC-16/IBM): polynomial `0x8005`, reflected form `0xA001`,
init `0x0000`, input and output reflected, no final XOR.

```text
crc = 0
for b in body:
    crc = (crc >> 8) ^ CRC16_ARC_TABLE[(crc ^ b) & 0xFF]
    crc &= 0xFFFF
header[7:9] = crc.to_bytes(2, "little")   # little-endian
```

Any standard CRC-16/ARC table works; a table-driven and a bitwise implementation
produce identical results. Compute it over the **body only** (the bytes after the
18-byte header), then place the two bytes little-endian into the header.

## How to verify you got it right

1. **Offline against a capture.** Recompute the field over the captured body and
   compare to the captured header bytes. On the reference device it matched
   **130/133** real headers; the three misses are fragment-reassembly artifacts,
   not algorithm errors (see [`../evidence/`](../evidence/README.md)).
2. **Live.** Write the `0610` frame with the correct field. A wrong value returns
   an empty ACK (`status 01`); the correct value makes the lock reply with a
   frame carrying its own public key. That flip from empty-ACK to real-key is the
   unambiguous success signal.

## Do not confuse it with the bulk CRC

This CRC-16/ARC (reflected, little-endian, over the public key) protects the
**authentication header**. The **control/bulk channel** uses a *different*
checksum — **CRC-HQX** (CRC-16/XMODEM, big-endian); see
[control-channel.md](control-channel.md). Keeping the two variants distinct
avoids a whole class of dead ends.

## Porting note

The algorithm and its placement are device-agnostic across the Aqara family — the
same header shape and the same CRC variant are expected to apply. What a new
device may change is the surrounding header/opcode values, not the checksum math.
Validate against a fresh capture of the new device before assuming.
