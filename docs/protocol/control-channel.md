# Control channel — wire framing

> Reverse-engineered from BLE captures. Examples are short, sanitized framing
> fragments; they carry no account or session secrets (Constitution Principles I & IV).

The control channel carries every lock command (open, keepalive, volume, user
management). This document covers only the **framing** of a control request — the
byte shape that wraps a command. The AES-CCM encryption that protects these frames
and the session that derives its keys are documented with the BLE auth handshake
(feature 004).

## ATT handles

Higher layers reference the well-known ATT handles symbolically:

| Constant | Handle | Role |
|----------|--------|------|
| `AUTH_WRITE` | `0x0020` | Auth handshake — central → lock |
| `AUTH_NOTIFY` | `0x0022` | Auth handshake — lock → central |
| `CONTROL_WRITE` | `0x0031` | Control — central → lock |
| `CONTROL_NOTIFY` | `0x0033` | Control — lock → central |
| `BULK_WRITE` | `0x003C` | Bulk transfer — central → lock |
| `BULK_NOTIFY` | `0x003E` | Bulk transfer — lock → central |

`ATT_CONTROL_WRITE` / `ATT_CONTROL_NOTIFY` are aliases of the control handles.

## Control request frame

A decrypted control request has four parts:

```text
┌──────┬─────────┬───────────────┬───────────┐
│ kind │ command │     body      │  trailer  │
│  1B  │   1B    │   variable    │    4B     │
└──────┴─────────┴───────────────┴───────────┘
```

- **kind** — `0x01` or `0x03`. Any other leading byte is not a control request
  this layer handles.
- **command** — the operation selector (see the command map below).
- **body** — command-specific payload (may be empty).
- **trailer** — a 4-byte integrity/sequence tail.

A frame must be at least **7 bytes** (1 + 1 + ≥1 + 4). Parsing is the exact inverse
of serialization: `parse(frame).as_bytes() == frame`.

### Worked examples

| Frame (hex) | kind | command | body | trailer | meaning |
|-------------|------|---------|------|---------|---------|
| `01 d3 02d13e15 d5fddfe4` | `0x01` | `0xD3` | `02d13e15` | `d5fddfe4` | voice-volume-alert |
| `01 fe 01fc 158b3609` | `0x01` | `0xFE` | `01fc` | `158b3609` | session-keepalive |

## Command map

Known command bytes are given human-readable names; unknown bytes fall back to a
stable `command-0xNN` label so analysis never breaks on an unseen command.

| Command | Name |
|---------|------|
| `0xD3` | `voice-volume-alert` |
| `0xFE` | `session-keepalive` |

The map grows as more commands are catalogued (feature 003, operations).

## Bulk integrity — CRC-HQX

Bulk-transfer blocks carry a trailing 16-bit checksum validated with **CRC-HQX**
(CRC-16/XMODEM), big-endian:

```text
valid_crc(block) == ( crc_hqx(block[:-2], 0) == int.from_bytes(block[-2:], "big") )
```

> ⚠️ This is **not** the same CRC as the auth handshake. The handshake header uses
> **CRC-16/ARC** (reflected, little-endian) over the exchanged public key
> (feature 004). Keep the two variants distinct.
