# Protocol reference

The reverse-engineered wire protocol of the Aqara U200, over BLE and the Aqara
cloud. Every claim here is backed by a real capture cited from
[`../evidence/`](../evidence/README.md).

| Document | Covers |
| --- | --- |
| [auth-handshake.md](auth-handshake.md) | The `0610`/`0710` auth frames, fragmentation, and **the CRC-16 that was the wall**. |
| [control-channel.md](control-channel.md) | The AES-CCM control channel on `ff61`/`ff62`. |
| [cloud-api.md](cloud-api.md) | Cloud endpoints, request signing, login crypto. |
| [operations.md](operations.md) | The complete command map: every operation the app exposes. |

## Conventions

- Hex is lower-case, byte-wise. Multi-byte integers are **little-endian**
  unless stated.
- "App" = the official Aqara Home app (the reference implementation).
- Frame fields are shown as `name(width)`; widths are in bytes.
