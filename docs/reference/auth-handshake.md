# Authentication handshake — `0610` / `0710`

**Layer:** transversal

> Every session must pass this handshake before any command works. The example
> body is an ephemeral EC **public** key (public by definition); no session key,
> nonce, or token appears here (Constitution Principles I & IV).

## The exchange

1. **`0610` (KEY_EXCHANGE)** — the central writes the cloud's ephemeral public
   key. The lock replies with a frame carrying **its own** public key.
2. **`0710` (AUTH_PROOF)** — the central writes the verify proof derived from the
   cloud `verify` step. The lock accepts, and the control channel is now usable.

Between the two, the cloud `verify` call turns the lock's returned key into the
session material (see [cloud-login.md](cloud-login.md)).

## Header layout (18 bytes) + body

```text
00 <ftype> 10 01 00 | len(2 LE) | CRC16(body)(2 LE) | lock_token(2 LE) | 00×7 | body
   ftype = 0x06 (public-key exchange) or 0x07 (verify proof)
```

| Bytes | Field | Value |
|-------|-------|-------|
| 0 | fixed | `0x00` |
| 1 | frame type | `0x06` / `0x07` |
| 2–4 | fixed | `10 01 00` |
| 5–6 | body length | little-endian |
| 7–8 | **CRC-16/ARC of body** | little-endian — see [framing-crc.md](framing-crc.md) |
| 9–10 | lock token | little-endian |
| 11–17 | padding | `00 × 7` |
| 18… | body | e.g. a 65-byte uncompressed SECP256R1 public key |

Building and parsing are exact inverses over (frame type, lock token, body). The
frame is fragmented onto the wire per [ble-transport.md](ble-transport.md).

## The gate: bytes 7–8

The single reason a byte-perfect frame still fails is a wrong value in bytes 7–8.
That field is the [CRC-16/ARC of the body](framing-crc.md), not a random token.
With the correct CRC the lock returns its public key; with a wrong one it returns
an empty ACK (`status 01`). Read the [framing-crc.md](framing-crc.md) solution
**before** attempting the handshake.

## The choreography

Drive it in the captured order: enable notifications, write `0610`, tolerate the
lock's empty ACKs until its real key arrives, run the cloud `verify`, write
`0710`, then use the control channel and clean up the subscriptions. This sequence
is verifiable without a radio against a scripted stand-in lock; what stays
hardware-only is whether a *real* lock accepts it — timing, radio, and firmware.

## Porting note

The two-frame exchange, the header layout, and the CRC gate are device-agnostic.
The `lock_token` handling and the exact key sizes should be reconfirmed against a
fresh capture of the new device, but the mechanism is expected to carry over.
