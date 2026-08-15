# Diagnostics — unblocking a port

A compact method for the failures you are most likely to hit. Match the symptom,
work the hypotheses in order, rule each out with the stated test.

## Symptom → hypothesis → test

### The lock returns an empty ACK (`status 01`) to the `0610` write

The classic wall. In likelihood order:

| Hypothesis | Test to rule it out |
| --- | --- |
| Wrong header CRC (bytes 7–8) | Recompute [CRC-16/ARC](reference/framing-crc.md) over the body; compare to a captured frame. Wrong CRC is by far the most common cause. |
| A fragment was dropped/coalesced | Confirm the transport spaces writes (~40 ms) and does not merge them; a truncated key looks identical to a bad CRC. |
| Truncated / wrong-size public key | Check the body length field and the reassembled key size against a capture. |
| Notifications not enabled in time | Ensure CCCD is set before the write, in the captured order. |

### A GATT request hangs forever

| Hypothesis | Test |
| --- | --- |
| No per-request timeout | Bound every low-level request; a mid-request disconnect must not hang. |
| Native stack lacks a needed primitive | The pre-auth needs Read-By-Type / MTU / data-length / connection-update; if the native stack does not expose them, use an external HCI controller. |

### Cloud login rejects valid credentials

| Hypothesis | Test |
| --- | --- |
| RSA over raw password instead of `MD5(password)` hex | See [cloud-login](reference/cloud-login.md); the RSA input must be the 32-char lowercase-hex MD5. |
| Stale token | Tokens rotate on re-login elsewhere; mint a fresh one (login is unauthenticated). |
| TLS certificate error | Usually a broken local CA store, not interception; fix the trust store. |

### Nothing appears on a passive scan

| Hypothesis | Test |
| --- | --- |
| Device not advertising | The U200 advertises only after its keypad is activated; trigger the device, then scan again. |

## Heuristics that generalize

- **"Random" is a hypothesis, not a fact.** A field that changes every session may
  be a checksum, nonce, or MAC. Prove what it is before dismissing it — the CRC
  gate hid here for a long time behind the label "random token".
- **Byte-diffs lie if you pre-filter.** Calling a field "noise" removes it from
  every "identical" comparison you run afterwards.
- **A working oracle can mislead.** If a component recomputes a field over whatever
  you give it, swapping your value in will "work" and mask the real gate.
- **Read the builder, not just the bytes.** The definitive answer to how a frame is
  constructed is in the construction logic, not only in the wire capture.
- **Isolate the variable.** When "the app works and mine doesn't", reproduce with
  the smallest possible central (own radio, minimal stack) to separate app logic
  from radio behaviour.
