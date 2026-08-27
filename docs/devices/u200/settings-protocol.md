# U200 settings read protocol (2026-08-26)

How the lock's configuration settings are read over the control channel, and why
some answer freely while others are gated. Reconstructed by decrypting the official
Aqara app's own BLE session (see "How this was obtained").

## Control frame shape for a read

A read is a short control frame sent on **ff61** as `0x01 || AES-CCM(plaintext)`
(the `0x01` write-prefix is on the wire, outside the cipher). The **plaintext** is:

```
<opcode:1> <kind:1> <body...>            # e.g. keepalive = 2f 01 2f
```

- **opcode** — the setting (e.g. `0xde` battery, `0xc3` lock volume, `0x68` language).
- **kind** — the command **family**, and it MATTERS: `0x01` SYSTEM, `0x02`, `0x03`,
  `0x04`. Sending an opcode with the wrong kind gets no answer. Examples confirmed
  from the app: door type `e0 01 e0` (kind 01), volume `02 02 …` / `c3 04 43 01`
  (kinds 02/04), alarm volume `84 02 04 07` (kind 02), finger count `20 03 20`.
- The lock replies on **ff62** (`0x81 || AES-CCM(response)`); response plaintext is
  `<opcode> 00 <value…> <crc16>`.

The generic `build_read_query_write` (opcode + `00` + 4-byte trailer, kind absent)
works for the kind-01 status/info opcodes but NOT for the family-02/03/04 settings —
those need the real `<opcode> <kind> <body>` frame.

## Two tiers: free reads vs elevation-gated reads

Against this lock (fw 3.0.0_0085), one authenticated session reads these **freely**
(answer in ~300 ms, no extra state): keepalive `0x2f`, MTU `0x4d`, firmware `0x0d`,
lock status `0x07`, battery `0xde`, tongue `0x08`, door type `0xe0`, pull spring
`0xe4`, work mode `0xee`, advanced `0xd8`, limits `0xe2`, verify-fail `0x94`, alarm
enable `0xcb`, timezone `0x33`.

These return **nothing** cold — they are **session-elevation gated**: volume `0xc3`
& `0x02`, language `0x68`, alarm volume `0x84`, finger count `0x20`, `0x1f`, voice
OTA `0xa6`, lock-setting `0x1a`. The official app reads them fine **after** its
connect-time setup burst (set-time `0x33` + access-log sync `0x13`); the exact
elevation trigger within that burst is not yet pinned (leading candidate: the
`0x33` set-time; alternative: completing the `0x13` log sync). Once elevated, the
gated reads answer as fast as the free ones. See the memory
`app-reads-settings-bulk-blob` for the open A/B test (set-time → read volume).

Reading the settings therefore needs a **persistent session** (one auth, many
frames) after elevation — implemented as `U200Client.read_burst()` /
`run_authenticated_lock_operation(follow_up_ops=…)`.

## How this was obtained (own device, own account)

The app's control channel is AES-CCM (tag 4, empty AAD) with a **static nonce per
session** (see `control-channel.md`). A static nonce means the CTR keystream is
reused across every frame, so a **known-plaintext / keystream-reuse** recovery reads
the whole session without the key: the keepalive (`2f012f` req / `2f002c06` resp) is
the most-repeated frame → gives the keystream; extend it with a known response
(firmware `0d0003000000000055003b44`, 12 B) → XOR-decrypt all frames. This decoded
the app's captured btsnoop (`adb bugreport`, no root/Frida) and revealed the frame
format and the two-tier behaviour above. Cross-checked against known values
(door type = eu, pull spring = 01 02 00, MTU = 247).
