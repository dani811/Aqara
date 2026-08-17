# Architecture

How autonomous control of an Aqara lock works, end to end, using the U200 as the
worked reference. The lock is a **BLE + Thread** device with **no Wi-Fi**; the
official app reaches it only over BLE and relays the cloud. This project replaces
the app on that BLE path.

## The pipeline

```text
        ┌─────────────┐   HTTPS      ┌──────────────┐
        │  Your code  │─────────────▶│  Aqara cloud │   (login, KDF material)
        └─────────────┘              └──────────────┘
               │ BLE (GATT)                  ▲
               ▼                             │ /verify
        ┌─────────────┐                      │
        │   The lock  │◀─────────────────────┘
        └─────────────┘
```

Seven phases run in order. Phases 1–2 and 5 are HTTPS to the cloud; 3–4 and 6–7
are BLE to the lock.

| # | Phase | Where | Reference |
| --- | --- | --- | --- |
| 1 | Account login | cloud | [cloud-login](reference/cloud-login.md) |
| 2 | `cloudPublicKey` (ephemeral EC) | cloud | [cloud-login](reference/cloud-login.md) |
| 3 | Connect + GATT preamble (MTU, CCCD…) | BLE | [ble-transport](reference/ble-transport.md) |
| 4 | **`0610` — send pubkey, get lock pubkey** | BLE | [auth-handshake](reference/auth-handshake.md) |
| 5 | `verify` → `sessionKey` | cloud | [cloud-login](reference/cloud-login.md) |
| 6 | `0710` — proof | BLE | [auth-handshake](reference/auth-handshake.md) |
| 7 | AES-CCM control channel | BLE | [control-channel](reference/control-channel.md) |

Phase 4 is the one that gates everything: the header carries a
[CRC-16/ARC of the public key](reference/framing-crc.md), and until that field is
correct the lock returns only an empty ACK.

## The official app as reference implementation

There is no vendor spec. The source of truth is the observed behaviour of the
official app talking to a real lock: its cloud calls, its BLE frames, and its own
frame-construction logic. The protocol documented here is what reproduces that
behaviour byte-for-byte; anything not yet reproduced byte-exact is marked
`unverified`.

## Trust model

- **No BLE bonding / SMP.** The link is unencrypted at the link layer; all
  security is at the application layer (the EC exchange + AES-CCM).
- **The cloud cannot reach the lock directly** (no Aqara hub in a
  Home-Assistant/Thread setup). The central is the only bridge, so authorization
  must live entirely in the BLE exchange — which is exactly why the `0610` CRC
  matters.
- **`sessionKey` is cloud-derived** from `verifyData` plus the lock's ephemeral
  public key; it is not reusable across sessions.

## Layer Map — transversal vs device-specific

The heart of this documentation: what is **reusable across the Aqara family**
versus what is **specific to one device**. Porting = reuse the transversal layer
unchanged, replace the device-specific layer.

### Transversal (reusable) → [`reference/`](reference/README.md)

| Element | Home |
| --- | --- |
| Frame checksum CRC-16/ARC (header field = CRC of body) | [reference/framing-crc.md](reference/framing-crc.md) |
| Cloud login (RSA over MD5(password) hex + AES-128-GCM) | [reference/cloud-login.md](reference/cloud-login.md) |
| Request signing `compute_sign` (MD5 over ordered fields) | [reference/cloud-login.md](reference/cloud-login.md) |
| KDF (`/publickey`, `/verify`) → session material | [reference/cloud-login.md](reference/cloud-login.md) |
| GATT role model (auth / control / OTA / bulk) | [reference/ble-transport.md](reference/ble-transport.md) |
| Fragmentation (18-byte, direction-tagged, sequenced) + timing | [reference/ble-transport.md](reference/ble-transport.md) |
| Handshake `0610`/`0710` + header layout | [reference/auth-handshake.md](reference/auth-handshake.md) |
| Control channel AES-CCM (tag=4, aad=∅) | [reference/control-channel.md](reference/control-channel.md) |
| Bulk integrity CRC-HQX (CRC-16/XMODEM) | [reference/control-channel.md](reference/control-channel.md) |
| Trust model (no SMP; app-layer security) | this document |

### Device-specific → [`devices/<device>/`](devices/u200/README.md)

| Element | Home (U200) |
| --- | --- |
| Service/characteristic UUIDs | [devices/u200/gatt-map.md](devices/u200/gatt-map.md) |
| Concrete ATT handles | [devices/u200/gatt-map.md](devices/u200/gatt-map.md) |
| Operation/opcode catalog (8 families) | [devices/u200/operations.md](devices/u200/operations.md) |
| Operate-frame trailer bases (additive) | [devices/u200/operations.md](devices/u200/operations.md) |
| Region/endpoint (EU confirmed) | [devices/u200/README.md](devices/u200/README.md) |

> **Grey zone.** Whether the opcode catalog is shared across the family is not yet
> proven; it is documented as device-specific by default. Promoting it to
> transversal is a decision for a future multi-device effort.

## Home Assistant

Home Assistant is the intended primary integration. That sets the bar for the
library: it must expose the lock's **full** operation surface, not just open/close,
so an integration can map every capability. The integration itself is out of scope
for this documentation.

## Package layout

```text
aqara_u200_ble/
├── client.py         # U200Client — the facade: login → scan → connect → operate
├── transport.py      # Transport contract, ScanCandidate, BleakTransport, BumbleTransport
├── scanner.py        # scan() + identify/select a U200 by name/services/manufacturer
├── errors.py         # FlowPhase, U200ClientError, NoDeviceFoundError, AmbiguousDeviceError
├── auth.py           # CloudAuthManager: account login + token refresh (code 108)
├── kdf.py            # cloud login, request signing, KDF endpoints, HKDF
├── session.py        # auth handshake (0610/0710), CRC, AES-CCM control codec
├── lock_ops.py       # lock / unlock / keepalive payloads
├── operations_catalog.py  # the U200 operation surface
├── protocol.py       # ATT + control-request primitives
├── gatt.py           # GattClient protocol the transports must satisfy
├── volume.py         # voice-volume helper
├── bumble_transport.py  # BumbleGattAdapter (Peer -> GattClient, low-level primitives)
└── py.typed
```
