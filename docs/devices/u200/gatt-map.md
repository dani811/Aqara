# U200 — GATT map

**Layer:** device-specific (U200)

The concrete services, characteristics, and ATT handles that fill the
device-agnostic [channel roles](../../reference/ble-transport.md) for the U200.
These are the values to rediscover for any other device.

## Services & characteristics (used by the protocol)

| Service | Characteristic | Role |
| --- | --- | --- |
| `fcb9` (16-bit SIG) | `ff07` (write) / `ff08` (notify) | Auth channel (`0610`/`0710`) |
| `ff60` (vendor base) | `ff61` (write) / `ff62` (notify) | Control channel (AES-CCM commands) |
| `ff60` (vendor base) | `ff63` (write) / `ff64` (notify) | OTA / secondary report channel |
| `ff90` (vendor base) | `ff91` (write) / `ff92` (notify) | YMODEM bulk transfer / aux report |

Vendor base = `0000XXXX-2333-5b1e-9d7c-c687fd2f04f2`. Only `fcb9` uses the
Bluetooth SIG base; the advertisement carries them all as 16-bit shorts.

## Full attribute table (complete service discovery, 2026-08-19)

Enumerated live against the reference U200 (macOS CoreBluetooth + ESP32-S3/bumble
for the OS-hidden services, own lock, firmware as shipped). Every service the lock exposes, in handle order —
including the ones the protocol does not use:

| Handles | Service | Characteristic (decl / value) | Props | Descriptors | Notes |
| --- | --- | --- | --- | --- | --- |
| `0x0001`–`0x0008` | `1801` Generic Attribute | `2a05` Service Changed `0x0002`/`0x0003` | indicate | CCCD `0x0004` | Hidden by CoreBluetooth; read via ESP32-S3/bumble |
| | | `2b2a` Database Hash `0x0005`/`0x0006` | read | — | `c1e296c4089af00548a300f1177fedea` (firmware-specific; changes if the GATT table changes) |
| | | `2b29` Client Supported Features `0x0007`/`0x0008` | read, write | — | `00` |
| `0x0009`–`0x000d` | `1800` Generic Access | `2a00` Device Name `0x000a`/`0x000b` | read, write | — | `"Empty Example"` (SiLabs SDK default — the advertised name `DoorLocker` is not the GAP name) |
| | | `2a01` Appearance `0x000c`/`0x000d` | read | — | `0000` |
| `0x000e`–`0x0014` | `180a` Device Information | `2a29` Manufacturer `0x000f`/`0x0010` | read | — | `"Silicon Labs"` |
| | | `2a24` Model Number `0x0011`/`0x0012` | read | — | `"Blue Gecko"` (SoC default, useless for model id) |
| | | `2a23` System ID `0x0013`/`0x0014` | read | — | `000102030405` (SoC default) |
| `0x0015`–`0x001d` | **`fff6` Matter BTP (commissioning)** | `18ee2ef5-263d-4559-959f-4f9c429f9d11` C1 `0x0016`/`0x0017` | read, write | — | Matter BLE Transport C1 (central → device); reads `00` via bumble |
| | | `18ee2ef5-…-9d12` C2 `0x0018`/`0x0019` | read, write, write-no-rsp, indicate | CCCD `0x001a` | Matter BTP C2 (device → central) |
| | | `64630238-8772-45f2-b87d-748a83218f04` C3 `0x001b`/`0x001c` | read, write, write-no-rsp, indicate | CCCD `0x001d` | Matter "additional data" |
| `0x001e`–`0x0023` | `fcb9` Auth | `ff07` `0x001f`/`0x0020` | write-no-rsp | — | auth write |
| | | `ff08` `0x0021`/`0x0022` | notify | CCCD `0x0023` | auth notify |
| `0x0024`–`0x0028` | `ff70` (vendor) **unknown** | `ff71` `0x0025`/`0x0026` | write-no-rsp | — | Not used by the app flow we reproduce; no notify side |
| | | `ff72` `0x0027`/`0x0028` | write-no-rsp | — | idem |
| `0x0029`–`0x002e` | `ff80` (vendor) **unknown** | `ff81` `0x002a`/`0x002b` | write-no-rsp | — | Not used by the app flow we reproduce |
| | | `ff82` `0x002c`/`0x002d` | notify | CCCD `0x002e` | Never subscribed by us — candidate for a state/event channel |
| `0x002f`–`0x0039` | `ff60` Control | `ff61` `0x0030`/`0x0031` | write-no-rsp | — | control write |
| | | `ff62` `0x0032`/`0x0033` | notify | CCCD `0x0034` | control notify |
| | | `ff63` `0x0035`/`0x0036` | write-no-rsp | — | OTA write |
| | | `ff64` `0x0037`/`0x0038` | notify | CCCD `0x0039` | control notify 2 (report; ff64) |
| `0x003a`–`0x003f` | `ff90` Aux / bulk | `ff91` `0x003b`/`0x003c` | write-no-rsp | — | bulk write |
| | | `ff92` `0x003d`/`0x003e` | notify | CCCD `0x003f` | bulk/aux notify (ff92) |

Negotiated MTU on macOS: 247.

### Findings worth acting on

- **The U200 is a Matter device over BLE (`fff6`)** — the standard Matter BTP
  commissioning service with C1/C2/C3. macOS/iOS refuse any access to it
  (`CBErrorDomain Code=8 "The specified UUID is not allowed"` on descriptor
  discovery and reads): the OS reserves Matter for itself. This is why a plain
  `BleakClient(dev)` fails in `_get_services` on macOS and the transport passes
  `services=[…]`. It is also the `GET_MATTER_*` family in the operation catalog.
  A Matter-over-Thread path into Home Assistant may exist independently of this
  library; out of scope here.
- **Two vendor services nobody touches: `ff70` (2 write chars) and `ff80`
  (write + notify)**. The app flow we reproduce never subscribes `ff82`. Given
  that ff62/ff64/ff92 stay silent about lock position, `ff82` is the next
  candidate to subscribe during an `aqara listen` window (its payload is
  unknown — maybe the same encrypted framing, maybe a different sub-protocol).
- Earlier docs listed `ff91`/`ff92` under `ff60`; they belong to `ff90`
  (corrected above; handles were already right).

### Reproducing the dump on macOS

CoreBluetooth refuses descriptor discovery on the Matter characteristics, so a
full `BleakClient(dev)` connect aborts. Discover per service list instead:
`BleakClient(dev, services=["180a","fcb9","0000ff60-2333-…","0000ff70-2333-…",
"0000ff80-2333-…","0000ff90-2333-…"])`, and for `fff6` monkeypatch
`PeripheralDelegate.discover_descriptors` to swallow the error. Short 16-bit
forms only resolve SIG-base UUIDs; the vendor services need the full 128-bit
string. On Linux/BlueZ or the ESP32-S3 HCI transport a plain discovery works.

## ATT handles (informational)

These are the concrete handle values observed on the reference firmware. The code
does **not** reference handles directly — every characteristic is resolved by UUID
(see `aqara_u200_ble/gatt_uuids.py`), so handles are not stable across firmware and
are listed here only for orientation when reading a capture.

| Role | Handle |
|------|--------|
| Auth write (central → lock) | `0x0020` |
| Auth notify (lock → central) | `0x0022` |
| Control write (central → lock) | `0x0031` |
| Control notify (lock → central) | `0x0033` |
| Bulk write (central → lock) | `0x003C` |
| Bulk notify (lock → central) | `0x003E` |

## Discovery notes

- `status: confirmed` against real captures of the reference device.
- The U200 was observed to **advertise only after its keypad is physically
  activated**; a passive scan finds nothing until then. This behaviour may differ
  on other devices.
- Handles are stable for this firmware family but should be re-read (service
  discovery) rather than hard-assumed on a new device or firmware.
