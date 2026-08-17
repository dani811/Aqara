# U200 — end-to-end validation

**Layer:** device-specific (U200)

Drive a real Aqara U200 from Python with no app and no phone. Use this to confirm,
on the reference device, that the whole pipeline works after any change.

> You need your **own** account credentials and your **own** lock. Every sensitive
> value comes from your environment — nothing is committed (Constitution
> Principle I). Copy `.env.example` to `.env` and fill it in
> (see the [porting guide](../../porting-guide.md), steps 0–1).

## 1. Prerequisites

- Python 3.10+ and the package installed: `pip install -e '.[ble]'` (native BLE)
  or `pip install -e '.[bumble]'` (external HCI controller, e.g. an ESP32-S3
  running [`tools/esp32s3_hci_usb`](../../../tools/esp32s3_hci_usb/README.md)).
- A `.env` with your account (`AQARA_ACCOUNT`/`AQARA_PASSWORD`), app identifiers
  and device id. No token to capture: the library logs in by itself.

## 2. The recommended way: the facade (three lines)

Everything below — login, token refresh, scan & identification, connection,
service discovery, the authenticated session — is one call chain:

```python
import asyncio, os
from aqara_u200_ble import BleakTransport, BumbleTransport, CloudAuthManager, U200Client

auth = CloudAuthManager(
    account=os.environ["AQARA_ACCOUNT"],
    password=os.environ["AQARA_PASSWORD"],
    appid=os.environ["AQARA_APPID"],
    appkey=os.environ["AQARA_APPKEY"],
    client_id=os.environ["AQARA_CLIENT_ID"],
    phone_id=os.environ["AQARA_PHONE_ID"],
    region=os.environ.get("AQARA_REGION", "EU"),
)
transport = BleakTransport()  # host Bluetooth …
# transport = BumbleTransport(os.environ["AQARA_ESP32_PORT"])   # … or ESP32-S3 controller


async def main():
    async with await U200Client.connect(
        auth=auth,
        transport=transport,
        device_id=os.environ["AQARA_DEVICE_ID"],
        # mac=os.environ.get("AQARA_LOCK_MAC"),  # optional; otherwise identified by advertisement
    ) as lock:
        print(await lock.operate("keepalive"))  # full handshake, bolt does not move
        print(await lock.lock())  # -> the lock's response (hex) or None


asyncio.run(main())
```

Or from the shell with the packaged command: `aqara scan | lock | unlock`
(`aqara --help`). The CLI is a thin adapter over this same API.

**Scan & identification.** `scan(transport)` returns `ScanCandidate`s with the
*reasons* they look like a U200 (`name` = `DoorLocker`, `service` = fcb9/ff60/ff90
advertised, `manufacturer` = 0x0B27, `mac` = the one you asked for). A device
that only shares the manufacturer id is never chosen automatically (a real false
positive was seen); pass `mac=` to disambiguate. The U200 only advertises after
its **keypad is physically activated**.

**Transports.** `BleakTransport` restricts discovery to the U200 services (needed
on macOS/CoreBluetooth) and omits the low-level primitives; `BumbleTransport`
connects with the phone's connection parameters, never pairs (the U200 drops the
link on any SMP request), and exposes Read-By-Type / MTU / connection update.
Errors carry the phase (`U200ClientError.phase`: login, scan, connect, discover,
operation).

## 3. Lower level: bring your own connected client

If you already hold a connected GATT client (Home Assistant's, or a Bumble
`Peer` wrapped in `BumbleGattAdapter`), wrap it: `U200Client.from_gatt(auth=…,
gatt_client=…, device_id=…)`, or call the flow directly:

```python
from aqara_u200_ble import run_authenticated_lock_operation

material, write, response = await run_authenticated_lock_operation(
    client=gatt_client,
    device_id=...,
    auth_headers=None,
    region="EU",
    base_url=None,
    operation="keepalive",
    auth=auth,
)
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

## 4. Troubleshooting

- **Empty response / no key from the lock**: almost always a dropped fragment or a
  wrong CRC field. The library spaces fragment writes (~40 ms); confirm your
  transport does not coalesce writes. See [diagnostics](../../diagnostics.md).
- **A GATT request hangs**: bound every low-level request with its own timeout; a
  mid-request disconnect must not hang forever.
- **Missing optional dependency `bleak`/`bumble`**: the transport tells you the extra
  to install (`.[ble]` or `.[bumble]`).
- **`NoDeviceFoundError` / `AmbiguousDeviceError`**: touch the keypad; if several
  locks answer, pass `mac=`.
- **Disconnect during discovery right after a previous run**: the U200 rejects an
  immediate reconnect; wait ~5 s.
