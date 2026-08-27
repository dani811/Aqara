# U200 settings read protocol (2026-08-26, updated 2026-08-27)

How the lock's configuration settings are read over the control channel.
Reconstructed by decrypting the official Aqara app's own BLE session (see "How this
was obtained"). **All settings read over BLE from our own session** — there is no
privilege tier; the earlier "cloud-gated" theory (specs 036/037) was two client
bugs, now fixed (see "There is NO privilege tier" below).

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

## There is NO privilege tier — every setting reads over BLE (RESOLVED 2026-08-27)

Earlier notes here (and specs 036/037) claimed a "privileged/cloud-gated tier"
that answered the official app but stayed silent to our library: volume `0xc3`,
language `0x68`, alarm volume `0x84`, finger count `0x20`, `0x1f`, voice-OTA
`0xa6`, lock-setting `0x1a`, access-log sync `0x13`. **That tier does not exist.**
On our own authenticated ESP32 session (same account, fw 3.0.0_0085) all of them
read fine and return **byte-identical values** to the app — confirmed live **6/6**:

| setting | frame (plaintext) | response | value |
| --- | --- | --- | --- |
| battery `0xde` | `de 01 de` (pfx 01) | `de 00 07 00 01 01 64 00 00` | 100 % |
| lock-setting `0x1a` | `1a 01 1a` (pfx 01) | `1a 00 00 01 01 0a 01 01 02 00 00 02` | bulk blob |
| volume `0xc3` | `c3 04 43 01` (pfx 01) | `c3 00 02 04` | `02 04` |
| language `0x68` | `68 01 68` (pfx 01) | `68 00 02 01 00 00` | `02 01 00 00` |
| alarm-vol `0x84` | `84 02 04 07` (pfx 01) | `84 00 02 00 10` | `02 00 10` |
| finger `0x20` | `20 03 20` (**pfx 03**) | `20 00 00 00 00 00` | 0 fingers |

### The real cause: two client bugs (both fixed)

The MITM investigation (037) proved the cloud session-grant is **identical**
between the app and our library — same `/verify` body, `deviceId`, and every header
(`appid`/`userid`/`phoneid`/`account`/`sign`), and the **same JWT scope**
(`tokenSource:UC`, `loginSource:USER_NEW`). So the difference was never cloud-side.
It was two bugs in `aqara_ble`:

1. **Response correlation by arrival order.** The persistent-session follow-up loop
   in `session.py` paired each reply to its request by the order frames arrived on
   `ff62`. But that notify channel also carries **spontaneous state events**
   (`0x1d`/`0xdd`/`0x15`); a stray event stole a read's slot and desynced the whole
   burst, so later reads (e.g. volume) got no matching frame → looked "gated".
   **Fix:** correlate each reply to its request by **opcode** (the reply is
   `<op> 00 …`), draining/forwarding non-matching event frames.
2. **Fixed ff61 write-prefix.** `read_burst` forced write-prefix `0x01` for every
   frame. The app uses **`0x03`** for finger `0x20`, log-sync `0x13`, `0x1f` and
   voice-OTA `0xa6` (proven from the decrypted app session). With `0x01` those stay
   silent; with `0x03` they answer. **Fix:** `read_burst` accepts a `"PP:frame"`
   spec to set the per-frame prefix (default `01`).

### Reading them from the library

Use a **persistent session** (one auth, many frames): `U200Client.read_burst([…])`.
Pass raw plaintext frames; add a `"03:"` prefix for the pfx-03 family, e.g.
`read_burst(["c3044301", "680168", "03:200320"])`. Each reply is opcode-correlated
and spontaneous events are skipped. A multi-frame burst needs the stabilized BLE
link (2026-08-27 fix in `transport.py`: `supervision_timeout` 5 s→20 s, connection
interval 30–60 ms). The lock only needs a keypad touch to **wake its radio for a
new connection**; once connected, reads work with no further touches (the app never
touches the keypad — it holds a persistent link).

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
