# BLE authentication handshake — `0610` / `0710`

> Reverse-engineered from BLE captures and confirmed against a real lock. The
> example body below is an ephemeral EC **public** key (public by definition);
> no session key, nonce, or token is committed (Constitution Principles I & IV).

Every session must pass this handshake before any command works. The central
writes the cloud's ephemeral public key (`0610`), the lock replies with its own
public key, and the central sends the verify proof (`0710`).

## The CRC wall

For a long time the central sent a **random** value in header bytes 7–8 (assumed
to be an "app token"). The lock answered every time with `status 01` and an empty
body — no public key, no session. That was the wall.

The field is **not** a token. It is the **CRC-16/ARC of the body**, little-endian:

```text
crc = 0
for b in body:
    crc = (crc >> 8) ^ CRC16_TABLE[(crc ^ b) & 0xFF]
    crc &= 0xFFFF
# header[7:9] = crc.to_bytes(2, "little")
```

- Variant: **CRC-16/ARC** — poly `0x8005` (reflected `0xA001`), init `0x0000`,
  reflected in/out. The table is lifted verbatim from the app's `CrcUtils.ts`.
- Verified **130/133** against the real btsnoop (the 3 misses are fragment
  reassembly artifacts), and confirmed **live**: with the correct CRC the lock
  returns `da…0610…` carrying its 65-byte public key instead of the empty ACK.

> ⚠️ This is **not** the control channel's CRC. The control/bulk channel uses
> **CRC-HQX** (feature 002). Keep the two variants distinct.

A backward-compatible `app_token` argument remains on the builder but is ignored —
the CRC alone governs the wire.

## Header layout (18 bytes) + body

```text
00 <ftype> 10 01 00 | len(2 LE) | CRC16(body)(2 LE) | lock_token(2 LE) | 00×7 | body
   ftype = 0x06 (publickey exchange) or 0x07 (verify proof)
```

| Bytes | Field | Value |
|-------|-------|-------|
| 0 | fixed | `0x00` |
| 1 | frame type | `0x06` / `0x07` |
| 2–4 | fixed | `10 01 00` |
| 5–6 | body length | little-endian |
| 7–8 | **CRC-16/ARC of body** | little-endian |
| 9–10 | lock token | little-endian |
| 11–17 | padding | `00 × 7` |
| 18… | body | e.g. 65-byte uncompressed SECP256R1 key |

`build_auth_message` / `parse_auth_message` are exact inverses over
(frame type, lock token, body).

## Fragmentation

Frames cross the BLE characteristic in 18-byte, direction-tagged, sequenced
fragments:

- Each fragment is `<direction> <seq> <≤18 body bytes>`.
- `direction` is `0x5A` outbound (central → lock) and `0xDA` inbound.
- `seq` counts `0, 1, 2, …`; the **last** fragment is tagged `0xFF`.
- `fragment_auth_message` and `assemble_auth_fragments` are exact inverses;
  reassembly rejects an unexpected direction or an out-of-order sequence.

On the wire the outbound writes are deliberately spaced (~40 ms) so the controller
does not drop fragments — a dropped fragment makes the lock see a truncated key and
reply empty (a re-run of the wall).

## Control payload crypto

Once session material exists, control payloads are protected with **AES-CCM**
(session key + 13-byte nonce, **4-byte** tag, empty AAD):

```text
ciphertext = AES-CCM(session_key, nonce, plaintext)   # len == len(plaintext) + 4
plaintext  = AES-CCM-decrypt(session_key, nonce, ciphertext)
```

`encrypt_control_payload` / `decrypt_control_payload` are inverses. The session key
and nonce come from the cloud exchange (feature 001) and the handshake; they are
never committed.
