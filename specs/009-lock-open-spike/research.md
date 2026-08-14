# Phase 0 Research / Spike Findings: Lock open command

**Verdict: NO-GO for the pure-offline autonomous path.** The AES-CCM layer is
already solved; the missing piece is the inner control-command **pack** (MiOT
short-pack + Mijia CRC), which is not available offline and must be captured from
an instrumented app or a rooted device.

## What the spike set out to answer

Whether the 4-byte control-command "trailer" (`d5fddfe4`, …) could be
reconstructed so the open (`01 74`) and status (`01 e5`) commands become
buildable on the already-working session.

## Finding 1 — the "4-byte trailer" is the AES-CCM tag, not a CRC (SOLVED)

The control channel is AES-CCM with `tag_length=4` (`operaciones-u200.md:11`,
`ble-control-handoff.md:142`; the original decrypted ~20 real frames cleanly,
`§190`). The volume frame `01d3 02d13e15 d5fddfe4` is 10 bytes = 6 ciphertext +
**4-byte tag** (`d5fddfe4`). Our [`encrypt_control_payload`](../../aqara_u200_ble/session.py)
already produces exactly this tag. So the premise "reverse an unknown CRC
trailer" was wrong — there is nothing to reverse for the tag. The repo's
`volume.py` frames are captured **encrypted replay blobs**, and
`control-channel.md` mislabels an encrypted frame as a "decrypted request".

## Finding 2 — bare `mainCmd+subCmd` is silently dropped; the pack is required (BLOCKER)

The authoritative table says the plaintext is `mainCmd + subCmd + data` **"con
CRC Mijia (`getMijiaCrc16String`) según el pack"**, built by
`getMiotShortPackString`. Live probing (test-account session, real lock via
ESP32) shows the pack is **not optional**:

| Plaintext sent (read-only) | Prefix | Lock reply |
|---|---|---|
| `01e5` (GET_DOOR_LOCK_STATUS) | 0x03 | none |
| `01e5` | 0x01 | none |
| `01e500` | 0x03 | none |
| `0107` (LOCK_STATUS) | 0x03 | none |
| `0107` | 0x01 | none |
| — keepalive `2f012f` (baseline) | 0x01 | **`2f002c06`** ✅ |

An all-notify capture (drain every `ff62` notify for 8 s after the write)
returned **zero frames** — not even a heartbeat — for `01e5`. The lock answers
the keepalive but is completely silent to a bare `mainCmd+subCmd`. Conclusion:
the frame is malformed without the MiOT pack + Mijia CRC.

*(Caveat: a reply could in theory arrive on `ff64`/CONTROL_NOTIFY2, which our
listener currently ignores. Total silence on `ff62` plus the bundle's own "con
CRC Mijia" note makes "dropped" the strongly-supported reading, but a future
probe should also listen on `ff64` to fully close it.)*

## Finding 3 — the pack algorithm is not available offline (why it's a NO-GO)

- **Not in the APK.** `base.bundle` (Hermes v96, 22 MB) contains **zero** lock
  strings (`netAccess`, `bleOpenLock`, `crc16`, `ff61` … all 0). The only
  zip-asset is widget resources. The lock module (`lumi.lock.netAccess`) is an
  **OTA-downloaded ARN module**, cached in the app's private data.
- **Device-private.** `/data/.../files/lumi/reactnative` is `Permission denied`
  without root (`relevo-investigacion.md`); `run-as` is unavailable for this
  signed build.
- **Never saved.** The original decompiled it in-memory via Frida and recorded
  only the *names* (`getMijiaCrc16String`, `getMiotShortPackString`) plus the
  auth-handshake CRC (`crc16_aqara`, already in our repo). The control-command
  pack was never fully reversed or persisted.

## Go/No-Go and fallback (FR-006)

**NO-GO** for building the open command purely offline. The AES-CCM tag is done;
the missing MiOT pack + Mijia CRC can only be obtained by:

- **(A) Instrument the app** — Frida gadget on a repackaged build, hook
  `getMiotShortPackString`/`getMijiaCrc16String` (or the `encryptAESCCM`
  plaintext input of one real command). Gives the exact pack bytes + CRC to
  reproduce. Blocked today: the installed app is stock (no gadget) and the
  device is unrooted.
- **(B) Root the device** — pull the cached `lumi.lock.netAccess` bundle and
  disassemble it (Hermes v96).

Either unblocks a definitive reimplementation, validated by reproducing a
captured command frame, after which `01 74` (open) and `01 e5` (status) build on
the session that already works. Recommended: (A) with the repackaged/gadget app
from the original RE setup.

## Safety

No actuation command (`0x74`) was ever constructed; every live frame sent was a
read-only getter. The bolt was not moved (SC-004 upheld).
