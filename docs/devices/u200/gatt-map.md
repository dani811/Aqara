# U200 — GATT map

**Layer:** device-specific (U200)

The concrete services, characteristics, and ATT handles that fill the
device-agnostic [channel roles](../../reference/ble-transport.md) for the U200.
These are the values to rediscover for any other device.

## Services & characteristics

| Service | Characteristic | Role |
| --- | --- | --- |
| `fcb9` | `ff07` (write) / `ff08` (notify) | Auth channel (`0610`/`0710`) |
| `ff60` | `ff61` (write) / `ff62` (notify) | Control channel (AES-CCM commands) |
| `ff60` | `ff63` / `ff64` | OTA |
| `ff60` | `ff91` / `ff92` | YMODEM bulk transfer |

## ATT handles

Higher layers reference these symbolically so the concrete handles live in one
place:

| Constant | Handle | Role |
|----------|--------|------|
| `AUTH_WRITE` | `0x0020` | Auth — central → lock |
| `AUTH_NOTIFY` | `0x0022` | Auth — lock → central |
| `CONTROL_WRITE` | `0x0031` | Control — central → lock |
| `CONTROL_NOTIFY` | `0x0033` | Control — lock → central |
| `BULK_WRITE` | `0x003C` | Bulk — central → lock |
| `BULK_NOTIFY` | `0x003E` | Bulk — lock → central |

## Discovery notes

- `status: confirmed` against real captures of the reference device.
- The U200 was observed to **advertise only after its keypad is physically
  activated**; a passive scan finds nothing until then. This behaviour may differ
  on other devices.
- Handles are stable for this firmware family but should be re-read (service
  discovery) rather than hard-assumed on a new device or firmware.
