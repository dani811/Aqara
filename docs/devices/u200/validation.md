# U200 — end-to-end validation

**Layer:** device-specific (U200)

Drive a real Aqara U200 from Python with no app and no phone. Use this to confirm,
on the reference device, that the whole pipeline works after any change.

> You need your **own** account credentials and your **own** lock. Every sensitive
> value comes from your environment — nothing is committed (Constitution
> Principle I). Copy `.env.example` to `.env` and fill it in
> (see the [porting guide](../../porting-guide.md), steps 0–1).

## 1. Prerequisites

- Python 3.11+ and the package installed: `pip install -e '.[ble]'` (native BLE)
  or `pip install -e '.[bumble]'` (external HCI controller, e.g. ESP32-S3).
- A `.env` with your captured account token and device identifiers.

## 2. Discover the lock (optional)

```python
import asyncio
from aqara_u200_ble import scan

asyncio.run(scan(seconds=8))
```

The scan is **passive** — it never writes to any device. The U200 only advertises
after its **keypad is physically activated**; touch the keypad and scan again if
nothing appears.

## 3. Choose a transport

- **Native (bleak)**: pass a connected client straight to the flow.
- **External controller (Bumble)**: wrap a connected Bumble `Peer` in
  `BumbleGattAdapter`, which exposes the low-level GATT primitives (Read-By-Type,
  MTU, data-length, connection update) the pre-authentication needs and that
  native stacks may not.

```python
from aqara_u200_ble import BumbleGattAdapter
transport = BumbleGattAdapter(peer)  # peer: a connected bumble Peer
```

## 4. Run it

The recommended path is autonomous login: give the library a `CloudAuthManager`
built from your credentials and it logs in on demand, keeps the token in memory,
and refreshes it if it expires — no manual token to capture or paste.

```python
import os, asyncio
from aqara_u200_ble import run_authenticated_lock_operation, CloudAuthManager

# In production the consumer (e.g. Home Assistant) injects these from its own
# secure storage. For a local run, load them from the environment:
auth = CloudAuthManager(
    account=os.environ["AQARA_ACCOUNT"],
    password=os.environ["AQARA_PASSWORD"],
    appid=os.environ["AQARA_APPID"],
    appkey=os.environ["AQARA_APPKEY"],
    client_id=os.environ["AQARA_CLIENT_ID"],
    phone_id=os.environ["AQARA_PHONE_ID"],
    region=os.environ.get("AQARA_REGION", "EU"),
)

async def main():
    material, write, response = await run_authenticated_lock_operation(
        client=transport,                 # native client or BumbleGattAdapter
        device_id=os.environ["AQARA_DEVICE_ID"],
        auth_headers=None,
        region=os.environ.get("AQARA_REGION", "EU"),
        base_url=None,
        operation="keepalive",            # start here; then "unlock" / "lock"
        auth=auth,                        # autonomous login + token refresh
    )
    print("session:", material.lock_public_key_hex[:16], "…")
    print("dispatched:", write.operation, write.hex_payload)

asyncio.run(main())
```

> Legacy: instead of `auth=`, you can pass a pre-built `signer=` bound to a static
> `AQARA_TOKEN` (via `make_local_signer`). That path has no auto-refresh — when the
> token expires the operation fails instead of renewing it.

Start with `operation="keepalive"`: it runs the full handshake **without** moving
the bolt, so you confirm the [CRC gate](../../reference/framing-crc.md) is passed
(the lock returns its public key) before ever actuating.

### What happens under the hood

1. The cloud issues an ephemeral public key.
2. The handshake writes it with the correct CRC-16 header field; the lock returns
   its own key — the wall-break.
3. The cloud `verify` returns the session material.
4. The operation payload is wrapped in AES-CCM and written on the control channel.

## 5. Troubleshooting

- **Empty response / no key from the lock**: almost always a dropped fragment or a
  wrong CRC field. The library spaces fragment writes (~40 ms); confirm your
  transport does not coalesce writes. See [diagnostics](../../diagnostics.md).
- **A GATT request hangs**: bound every low-level request with its own timeout; a
  mid-request disconnect must not hang forever.
- **Missing optional dependency `bleak`/`bumble`**: install the matching extra
  (`.[ble]` or `.[bumble]`).
