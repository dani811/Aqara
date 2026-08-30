# Reference — the transversal layer

**Layer:** transversal

The device-agnostic protocol shared across the Aqara family. Everything here is
expected to be reusable as-is when porting to another device; what changes per
device lives under [`../devices/`](../devices/).

| Document | Covers |
| --- | --- |
| [framing-crc.md](framing-crc.md) | The CRC-16/ARC header field — **the gate that blocked the project**. |
| [cloud-login.md](cloud-login.md) | Cloud endpoints, request signing, login crypto, and the KDF that yields session material. |
| [ble-transport.md](ble-transport.md) | GATT role model, connection preamble, and frame fragmentation/timing. |
| [auth-handshake.md](auth-handshake.md) | The `0610`/`0710` exchange and the header layout. |
| [control-channel.md](control-channel.md) | AES-CCM encryption, the control-frame shape, and the bulk CRC-HQX. |
| [rn-device-plugins.md](rn-device-plugins.md) | How to pull any Aqara device's real React Native plugin source from a public CDN — reusable for porting to a new device. |

Every claim links to sanitized proof in [`../evidence/`](../evidence/README.md)
or is tagged `unverified`.
