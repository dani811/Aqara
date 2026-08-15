# BLE transport — GATT model & fragmentation

**Layer:** transversal

> The device-agnostic shape of the Bluetooth link: which GATT roles exist, how
> frames are fragmented across a characteristic, and the timing discipline that
> keeps the lock from seeing a truncated frame.

## GATT role model

The lock exposes four logical channels, each a write/notify characteristic pair:

| Role | Direction pair | Carries |
| --- | --- | --- |
| **Auth** | write / notify | the `0610`/`0710` handshake |
| **Control** | write / notify | AES-CCM-protected commands |
| **OTA** | write / notify | firmware update |
| **Bulk** | write / notify | large transfers (YMODEM-style) |

The *roles* are device-agnostic; the concrete UUIDs and ATT handles that fill
them are device-specific — see the device's `gatt-map.md` (for the reference lock,
[`../devices/u200/gatt-map.md`](../devices/u200/gatt-map.md)).

Higher layers reference channels symbolically (AUTH_WRITE/NOTIFY,
CONTROL_WRITE/NOTIFY, BULK_WRITE/NOTIFY) so the concrete handles live in one
device-specific place.

## Connection preamble

Before the handshake, the central completes the usual GATT preamble: connect,
negotiate MTU, and enable notifications (CCCD) on the channels it will read. Some
low-level primitives the lock's pre-authentication path needs (Read-By-Type, MTU
and data-length negotiation, connection-parameter update) are not exposed by every
native BLE stack; an external HCI controller may be required to drive them.

## Fragmentation (auth channel)

Handshake frames cross the characteristic in **18-byte, direction-tagged,
sequenced** fragments:

- Each fragment is `<direction> <seq> <≤18 body bytes>`.
- `direction` = `0x5A` outbound (central → lock), `0xDA` inbound (lock → central).
- `seq` counts `0, 1, 2, …`; the **last** fragment is tagged `0xFF`.
- Reassembly must reject an unexpected direction or an out-of-order sequence;
  fragmenting and reassembling are exact inverses.

### Timing discipline

Space the outbound fragment writes (~40 ms apart) so the controller does not
coalesce or drop them. A dropped fragment makes the lock see a truncated public
key and reply with an empty ACK — indistinguishable at first glance from a wrong
[CRC](framing-crc.md), and a common re-run of "the wall". If a custom transport
coalesces writes, this failure reappears.

## Porting note

The channel roles, the fragmentation scheme, and the timing discipline are
expected to be common across the Aqara family. The concrete UUIDs/handles are the
device-specific piece to rediscover per device (step 2 of the
[porting guide](../porting-guide.md)).
