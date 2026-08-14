# Tutorial — End-to-end autonomous unlock

Drive a real Aqara U200 from Python, with no app and no phone. This ties together
all five features: cloud key (001), control framing (002), operations (003), the
BLE handshake (004), and this transport/discovery layer (005).

> You need your **own** account credentials and your **own** lock. Every sensitive
> value comes from your environment — nothing is committed (Constitution
> Principle I). Copy `.env.example` to `.env` and fill it in.

## 1. Prerequisites

- Python 3.11+ and the package installed: `pip install -e '.[ble]'` (native BLE)
  or `pip install -e '.[bumble]'` (external controller, e.g. ESP32-S3 over HCI).
- A `.env` with your captured account token and device identifiers (see
  `docs/tutorials/` capture guides and `.env.example`).

## 2. Discover the lock (optional)

```python
import asyncio
from aqara_u200_ble import scan

asyncio.run(scan(seconds=8))
```

The scan is **passive** — it never writes to any device. If nothing appears, the
observed U200 only advertises after its **keypad is physically activated**; touch
the keypad and scan again.

## 3. Choose a transport

- **Native (bleak)**: pass a connected `BleakClient` straight to the flow.
- **External controller (Bumble)**: wrap a connected Bumble `Peer` in
  `BumbleGattAdapter`, which supplies the low-level GATT primitives (Read-By-Type,
  MTU, data-length, connection update) the lock's pre-auth needs and that native
  stacks do not expose.

```python
from aqara_u200_ble import BumbleGattAdapter
transport = BumbleGattAdapter(peer)   # peer: a connected bumble Peer
```

## 4. Run the end-to-end unlock

```python
import os, asyncio
from aqara_u200_ble import run_authenticated_lock_operation, make_local_signer

signer = make_local_signer(
    appid=os.environ["AQARA_APPID"],
    appkey=os.environ["AQARA_APPKEY"],
    token=os.environ["AQARA_TOKEN"],
    user_id=os.environ["AQARA_USER_ID"],
    client_id=os.environ["AQARA_CLIENT_ID"],
    phone_id=os.environ["AQARA_PHONE_ID"],
)

async def main():
    material, write, response = await run_authenticated_lock_operation(
        bleak_client=transport,               # native client or BumbleGattAdapter
        device_id=os.environ["AQARA_DEVICE_ID"],
        auth_headers=None,
        region=os.environ.get("AQARA_REGION", "EU"),
        base_url=None,
        operation="unlock",                   # or "lock", "keepalive"
        signer=signer,
    )
    print("session:", material.lock_public_key_hex[:16], "…")
    print("dispatched:", write.operation, write.hex_payload)

asyncio.run(main())
```

What happens under the hood:

1. The cloud issues an ephemeral public key (feature 001).
2. The handshake writes it with the **correct CRC-16** header field and the lock
   returns its own public key — the wall-break (feature 004).
3. The cloud verifies and returns the session material (feature 001).
4. The operation payload (feature 003) is wrapped in AES-CCM (feature 004) and
   written on the control channel (feature 002).

## 5. Troubleshooting

- **Lock returns an empty response / never sends its key**: almost always a
  fragment was dropped or the CRC field was wrong. The library spaces fragment
  writes (~40 ms) to avoid drops; confirm your transport does not coalesce writes.
- **A GATT request hangs**: every low-level request is bounded by its own timeout;
  if you wrote a custom transport, keep that discipline — a mid-request disconnect
  must not hang forever.
- **`SystemExit: Falta la dependencia opcional 'bleak'`**: install the matching
  extra (`.[ble]` or `.[bumble]`).
