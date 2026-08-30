# Aqara U200

**Layer:** device-specific (U200)

The reference device — the lock this project has fully solved. Everything here is
specific to the U200; the reusable mechanisms it builds on live in
[`../../reference/`](../../reference/README.md).

## Fact sheet

| Property | Value |
| --- | --- |
| Connectivity | BLE + Thread, **no Wi-Fi** |
| Region confirmed | EU (`status: confirmed`); other regions `unverified` |
| BLE security | No SMP bonding; security at the application layer |
| Advertising | Only after the keypad is physically activated |
| Confirmed operations | `UNLOCK`, `LOCK`, `KEEPALIVE` (2 opcodes verified live) |

## Documents

| Document | Covers |
| --- | --- |
| [gatt-map.md](gatt-map.md) | Concrete service/characteristic UUIDs and ATT handles. |
| [operations.md](operations.md) | The full opcode catalog (214 ops, 8 families) with status. |
| [settings-protocol.md](settings-protocol.md) | The read frame shape (`<opcode> <kind> <body>`) and ff61 write-prefix rules. |
| [u200-app-opcode-table.md](u200-app-opcode-table.md) | The SYSTEM-family opcode table mined straight from the app's decompiled source, cross-checked against `operations.md`. |
| [validation.md](validation.md) | End-to-end run to confirm the whole pipeline works. |

## Using it as a porting template

A new Aqara device reuses [`../../reference/`](../../reference/README.md) unchanged
and replaces this folder: a new `gatt-map.md` (rediscovered UUIDs/handles) and a
new `operations.md` (its own catalog). Follow the
[porting guide](../../porting-guide.md).
