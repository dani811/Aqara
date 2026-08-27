# U200 settings read protocol (2026-08-26, updated 2026-08-27)

How the lock's configuration settings are read over the control channel, why some
answer freely while others are privilege-gated, and where that privilege lives.
Reconstructed by decrypting the official Aqara app's own BLE session (see "How this
was obtained"). The privileged tier is unsolved (granted cloud-side) — see
investigation `specs/036-privilege-elevation` and the MITM follow-up
`specs/037-cloud-session-mitm`.

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

These return **nothing** to our sessions — they are **privilege-gated**: volume
`0xc3` & `0x02`, language `0x68`, alarm volume `0x84`, finger count `0x20`, `0x1f`,
voice OTA `0xa6`, lock-setting `0x1a`, **and the access-log sync `0x13` itself**.
The official app reads them all; our authenticated sessions (same account) do not.

### Where the privilege comes from — cloud-side (investigation 036)

The app is privileged **from its first post-auth command** (clean capture: auth
done 11:19:50.97, first gated `0x13` answered 11:19:51.826 — ~0.5 s later). And
**every BLE-observable is identical** between the app and our library: the auth
message format (`00 ft 10 01 00 <len_le> crc16(body) …`), the 8-byte verifyData,
and the cloud calls (our library reimplements them). The phone even connects with a
**rotating RPA** over an **unbonded** link, so the lock cannot gate on central
identity either. Conclusion: **the privileged tier is granted CLOUD-SIDE at session
mint time and is invisible on the BLE link** — the Aqara cloud hands the official
app privilege-bearing session material (or accepts a role/scope/app-signature field
in its mint request) that our reimplemented `kdf` request does not obtain. Likely
only the SecNeo-signed official app is granted it. Confirming/bypassing this needs
an HTTPS MITM of the app's cloud session-grant — tracked in
`specs/037-cloud-session-mitm`.

**UPDATE 2026-08-27 (MITM breakthrough — body ruled out):** a Frida-16 **native**
`SSL_read`/`SSL_write` hook (stable under SecNeo, unlike Java hooks) captured the
app's `/dev/bluetooth/login/assure/verify` in clear. The **request body is
byte-identical** to our `kdf.cloud_verify` (`{deviceId, devicePublicKey}`) and the
**`deviceId` matches our `.env`** (`matt.73cb…`, a Matter id); the response
structure matches too. So the privilege is **not in the `/verify` body or
deviceId** — it can only be in the HPACK-compressed **HTTP request headers** (Token
scope / `Sign` / `Appid`) which the native hook can't read, or bound to the
SecNeo-signed app. See spec 037's 2026-08-27 breakthrough log.

**Hypotheses tested and REFUTED** (do not re-try — evidence in spec 036 / memory
`app-reads-settings-bulk-blob`): keypad-per-read; keypad held during read; set-time
`0x33` then read; "log-sync `0x13` completes → elevates" (circular — `0x13` is
itself gated); session age / settling delay; response latency / queueing (30 s
listen, 0 frames); persistent session alone; BLE bonding/encryption (app's ATT is
in the clear); BLE central address (rotating RPA + unbonded).

### Reading them, if a privileged session is ever obtained

Use a **persistent session** (one auth, many frames) — `U200Client.read_burst()` /
`run_authenticated_lock_operation(follow_up_ops=…)`. A multi-frame burst needs the
stabilized BLE link (2026-08-27 fix in `transport.py`: `supervision_timeout`
5 s→20 s, connection interval 30–60 ms) — before it, the ESP32 link dropped
mid-burst within ~10–16 s; after it, a held session survives 27 s+.

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
