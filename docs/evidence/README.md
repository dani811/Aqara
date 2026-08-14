# Evidence

Reverse engineering only counts when it's proven. This is the index of what
backs each protocol claim. **The raw captures themselves are never committed**
— they embed keys, MACs and personal data. They live locally under a
git-ignored `captures/` tree; here we record _what_ was observed and _how_ it
was verified, sanitised.

## Format

Each claim links to the capture kind and the verification method:

| Claim | Kind of evidence | How verified |
| --- | --- | --- |
| `0610` header field is `CRC-16(body)` | HCI btsnoop of app sessions | `crc16_aqara` matches 130/133 real headers; byte-exact vs app frame |
| The wall falls with the correct CRC | live android-probe run | lock returned `da00000610ffff4100…` (real pubkey, status 00) |
| Control channel is AES-CCM(tag=4, aad=∅) | control-frame captures | ~20 frames decrypt with valid tag, zero failures |
| `Sign` = MD5 over ordered fields | HTTP captures | our `compute_sign` reproduces the app's header |
| App sends `cloudPublicKey` verbatim in `0610` | HCI + HTTP correlation | reassembled body == `/publickey` response, byte for byte |
| Operation opcodes | app bundle (`BleCommandConstant.ts`) | enums extracted verbatim; builders read for structure |
| No BLE bonding/encryption | HCI btsnoop | zero SMP / Encryption-Change events across all sessions |
| No cloud→lock path | topology | no Aqara hub; lock reachable only via the phone's BLE |

## Reproducing evidence

Capturing HCI/BLE requires the instrumentation in
[`../../tools/`](../../tools/README.md) and hardware you own. Store any capture
under `captures/` (git-ignored) and cite it here by date + what it shows — never
by committing the file.

## Why sanitised

Every btsnoop of a real session contains the lock's MAC, the ephemeral keys,
the session key and account identifiers. The findings are public; the captures
are not.
