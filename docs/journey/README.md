# The journey — how the U200 was cracked

A reverse-engineering case study, told honestly: the wins, the months-long
dead end, and the one-field breakthrough. Written so the _process_ is reusable,
not just the result. This is the "built with AI" part of the project — the
reasoning was developed in an AI pair-RE loop.

## Act I — The easy half

The cloud side fell quickly. Login crypto (RSA + AES-128-GCM), the request
signing (`getSignHead` → `compute_sign`), and the KDF endpoints
(`/publickey`, `/verify`) were all reimplemented in pure Python. We could get a
fresh `cloudPublicKey` autonomously, no app.
→ [spec 001](../../specs/001-cloud-kdf-login/spec.md)

## Act II — The wall

Then: silence. Writing the `0610` public-key frame from any non-app central —
ESP32+Bumble, macOS/bleak, even a bespoke native Android app on the same
phone — got an **empty ACK** (`status 01`, no pubkey). The official app, on the
same phone, same radio, succeeded every time.

We ruled out, each with direct evidence:

| Hypothesis | Verdict |
| --- | --- |
| Message format / bytes | ❌ byte-identical to the app |
| MTU, PHY, connection params | ❌ replicated; still failed |
| The account / registration | ❌ two devices, unregistered, worked with the app |
| BLE bonding / encryption | ❌ zero SMP, zero encryption on the wire |
| The APK signature | ❌ a debug-resigned app worked fine |
| Cloud pre-authorising the lock | ❌ no Aqara hub — no path to the lock |
| The radio / chip | ❌ our native app used the phone's own radio |

We even proved that swapping our key into the running app **worked** — so the
key content was fine. And a full HCI byte-diff said the app's connection and
ours were _identical_. A genuine paradox.

## Act III — "It's not the radio"

The paradox only resolves if something we called "identical" wasn't. The one
field we had dismissed: a 2-byte value in the `0610` header, documented as a
**random `app_token`** and filled with `os.urandom(2)`.

Reading the app's own frame builder (`getAiotLongPackageList`,
`CrcUtils.ts::getCrc16String`) revealed it was never random — it was the
**CRC-16 of the public key**. It only looked random because every handshake
carries a fresh key, hence a fresh checksum. The lock validates it; ours was
garbage, so `status 01`.

We reproduced the CRC (CRC-16/ARC, table lifted from the bundle) — it matched
**130/133** real headers and was byte-exact against the app. With the fix, our
own native central wrote the `0610` and the lock returned
`da00000610ffff4100…` — **its real public key**.

Six months. One checksum.
→ [spec 004](../../specs/004-ble-auth-handshake/spec.md) ·
[the write-up](../protocol/auth-handshake.md#the-crc-wall)

## Act IV — The whole app

With the control channel open, the app's entire command surface became
reachable. The opcode map — users, credentials, auto-lock, alarms, volume,
Matter — was extracted from `BleCommandConstant.ts`.
→ [operations](../protocol/operations.md) ·
[spec 003](../../specs/003-lock-operations/spec.md)

## Lessons

1. **"Random" is a hypothesis, not a fact.** A field that varies every session
   might be a checksum, a nonce, or a MAC. Prove it before dismissing it.
2. **Byte-diffs lie if you pre-filter.** Calling a field "noise" hid it from
   every "identical HCI" comparison we ran.
3. **A working oracle can mislead.** The key-swap succeeded because the app
   re-computes the checksum over whatever it sends — masking the real gate.
4. **Read the builder, not just the bytes.** The answer was in the app's own
   frame-construction code all along.
