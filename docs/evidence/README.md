# Evidence

Reverse engineering only counts when it is proven. This is the index of what backs
each protocol claim. **The raw captures themselves are never committed** — they
embed keys, addresses, and personal data. They live locally under a git-ignored
`captures/` tree; here we record *what* was observed and *how* it was verified,
sanitized.

## Claims

| Claim | Kind of evidence | How verified |
| --- | --- | --- |
| `0610` header field is `CRC-16/ARC(body)` | HCI trace of app sessions | recomputed CRC matches 130/133 real headers; byte-exact vs the app frame |
| The wall falls with the correct CRC | live probe run | lock returned a real public-key frame (status 00) instead of the empty ACK |
| Control channel is AES-CCM (tag=4, aad=∅) | control-frame captures | ~20 frames decrypt with a valid tag, zero failures |
| `Sign` = MD5 over ordered fields | HTTP captures | our `compute_sign` reproduces the app's header |
| Login RSA input is `MD5(password)` hex | app crypto hook | the RSA input for a test password was its lowercase-hex MD5 |
| App sends `cloudPublicKey` verbatim in `0610` | HCI + HTTP correlation | reassembled body == `/publickey` response, byte for byte |
| Operation opcodes | app command enum | enums extracted; builders read for structure |
| No BLE bonding/encryption | HCI trace | zero SMP / encryption-change events across all sessions |
| No cloud→lock path | topology | no hub present; lock reachable only via the central's BLE |

## Reproducing evidence

Capturing HCI/BLE requires instrumentation and hardware you own. Store any capture
under `captures/` (git-ignored) and cite it here by date and what it shows — never
by committing the file.

## Why sanitized

Every trace of a real session contains the lock's address, the ephemeral keys, the
session key, and account identifiers. The findings are public; the captures are
not (Constitution Principles I & IV).
