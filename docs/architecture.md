# Architecture

How autonomous control of the Aqara U200 works, end to end. The lock is a
BLE + Thread device with **no Wi‑Fi**; the official app reaches it only over
BLE and relays the cloud. This project replaces the app on that BLE path.

## The reconnection pipeline

```text
        ┌─────────────┐   HTTPS      ┌──────────────┐
        │  Your code  │─────────────▶│  Aqara cloud │   (login, KDF material)
        └─────────────┘              └──────────────┘
               │ BLE (GATT)                  ▲
               ▼                             │ /verify
        ┌─────────────┐                      │
        │  U200 lock  │◀─────────────────────┘
        └─────────────┘
```

Seven phases run in order. Phases 1–2 and 5 are HTTPS to the Aqara cloud;
3–4, 6–7 are BLE to the lock.

| # | Phase | Where | Module |
| --- | --- | --- | --- |
| 1 | Account login | cloud | `kdf.login` |
| 2 | `cloudPublicKey` (ephemeral EC) | cloud | `kdf.cloud_get_public_key` |
| 3 | Connect + GATT preamble (MTU, CCCD…) | BLE | `session` |
| 4 | **`0610` — send pubkey, get lock pubkey** | BLE | `session.build_auth_message` |
| 5 | `verify` → `sessionKey` | cloud | `kdf.get_session_material` |
| 6 | `0710` — proof | BLE | `session` |
| 7 | AES‑CCM control channel | BLE | `session.encrypt_control_payload` |

Phase 4 is where the project was blocked for months — see
[the CRC wall](protocol/auth-handshake.md#the-crc-wall).

## GATT map

| Service | Characteristic | Role |
| --- | --- | --- |
| `fcb9` | `ff07` (write) / `ff08` (notify) | Auth channel (`0610`/`0710`) |
| `ff60` | `ff61` (write) / `ff62` (notify) | Control channel (AES‑CCM commands) |
| `ff60` | `ff63`/`ff64` | OTA |
| `ff60` | `ff91`/`ff92` | YMODEM bulk transfer |

Full frame formats: [protocol reference](protocol/README.md).

## Trust model

- **No BLE bonding / SMP.** The link is unencrypted at the LL layer; all
  security is at the application layer (the EC exchange + AES‑CCM).
- **The cloud is not reachable by the lock directly** (no Aqara hub in a
  Home‑Assistant/Thread setup). The phone/central is the only bridge, so the
  authorization must live entirely in the BLE exchange — which is exactly why
  the `0610` CRC mattered.
- **`sessionKey`** is derived cloud‑side from `verifyData` + the lock's
  ephemeral pubkey; it is not reusable across sessions.

## Package layout

```text
aqara_u200_ble/
├── kdf.py            # cloud login, request signing, KDF endpoints, HKDF
├── session.py       # auth handshake (0610/0710), CRC, AES-CCM control codec
├── lock_ops.py      # lock / unlock / keepalive payloads
├── protocol.py      # ATT + control-request primitives
├── scanner.py       # passive BLE discovery
├── volume.py        # voice-volume helper
├── bumble_transport.py  # ESP32-S3 HCI (Bumble) GATT adapter
└── py.typed
```
