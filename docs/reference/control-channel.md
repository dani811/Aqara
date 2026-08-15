# Control channel — encryption & framing

**Layer:** transversal

> The channel that carries every command once the handshake succeeds. Examples are
> short, sanitized framing fragments carrying no account or session secrets
> (Constitution Principles I & IV).

## Encryption — AES-CCM

Once the session material exists, control payloads are protected with **AES-CCM**:
the session key, a 13-byte nonce, a **4-byte** tag, and **empty AAD**.

```text
ciphertext = AES-CCM(session_key, nonce, plaintext)     # len == len(plaintext) + 4
plaintext  = AES-CCM-decrypt(session_key, nonce, ciphertext)
```

Encryption and decryption are inverses. The key and nonce come from the cloud
exchange and the handshake ([cloud-login.md](cloud-login.md),
[auth-handshake.md](auth-handshake.md)); they are never committed. The write on
the wire is `write_prefix + ciphertext`, where `write_prefix` is a small opcode
byte (`0x01` for the confirmed operations).

## Decrypted control frame

A decrypted control request has four parts:

```text
┌──────┬─────────┬───────────────┬───────────┐
│ kind │ command │     body      │  trailer  │
│  1B  │   1B    │   variable    │    4B     │
└──────┴─────────┴───────────────┴───────────┘
```

- **kind** — `0x01` or `0x03`. Any other leading byte is not a control request
  this layer handles.
- **command** — the operation selector (the catalog is device-specific).
- **body** — command-specific payload (may be empty).
- **trailer** — a 4-byte integrity/sequence tail.

A frame is at least **7 bytes** (1 + 1 + ≥1 + 4). Parsing is the exact inverse of
serialization.

## Bulk integrity — CRC-HQX

Bulk-transfer blocks carry a trailing 16-bit checksum validated with **CRC-HQX**
(CRC-16/XMODEM), **big-endian**:

```text
valid(block) == ( crc_hqx(block[:-2]) == int.from_bytes(block[-2:], "big") )
```

> ⚠️ This is **not** the handshake CRC. The handshake header uses **CRC-16/ARC**
> (reflected, little-endian) — see [framing-crc.md](framing-crc.md). Two channels,
> two different CRC variants; keep them distinct.

## Porting note

The AES-CCM parameters (tag length, empty AAD), the four-part frame shape, and the
bulk CRC-HQX are expected to be common across the Aqara family. The set of
**commands** carried in the `command` byte — and their bodies — is device-specific
(see the device's `operations.md`).
