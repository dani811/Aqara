# Phase 0 Research / Spike Findings: Lock open command

**Verdict: ACHIEVED — the lock was opened autonomously (2026-08-14).** The
offline path was a NO-GO (findings 1–3 below), so we instrumented the app with a
Frida gadget, captured the real open command, and replayed it from our own
session — the physical lock opened. See Finding 4 (Resolution).

## What the spike set out to answer

Whether the 4-byte control-command "trailer" (`d5fddfe4`, …) could be
reconstructed so the open (`01 74`) and status (`01 e5`) commands become
buildable on the already-working session.

## Finding 1 — the "4-byte trailer" is the AES-CCM tag, not a CRC (SOLVED)

The control channel is AES-CCM with `tag_length=4` (`operaciones-u200.md:11`,
`ble-control-handoff.md:142`; the original decrypted ~20 real frames cleanly,
`§190`). The volume frame `01d3 02d13e15 d5fddfe4` is 10 bytes = 6 ciphertext +
**4-byte tag** (`d5fddfe4`). Our [`encrypt_control_payload`](../../aqara_ble/session.py)
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

## Finding 4 — Resolution: captured the real command and opened the lock

The offline NO-GO was overturned by going through the app:

1. **Instrumented the app.** The stock Play build has no gadget and the device is
   unrooted, but a Frida-gadget repack of `base.apk` + split (built earlier,
   `on_load: wait`, signed with a debug key) was reinstalled. The app freezes on
   launch until Frida attaches on `127.0.0.1:27042`.
2. **Captured the real command.** Hooking `AqEdUtils.encryptAESCCM`, one press of
   Open in the app produced the exact plaintext handed to AES-CCM:
   - **OPEN  = `74010100b917`** (`0x74` = BLE_OPEN_LOCK, byte 1 `01` = open)
   - **CLOSE = `740002003a12`** (byte 1 `00` = close)
   The `1f031f` / `200320` values the repo shipped as LOCK/UNLOCK are **not** the
   actuators — the lock is silent to them.
3. **Verified the crypto is ours.** `AESCCM(key, tag_length=4).encrypt(nonce,
   74010100b917, b"")` reproduces the app's `ff61` ciphertext byte-for-byte, so
   our `encrypt_control_payload` needs no change — only the right plaintext.
4. **Opened it autonomously.** From our own ESP32 session (owner account), we
   re-encrypted `74010100b917` with our fresh session key/nonce (prefix `0x01`)
   and wrote it to `ff61`. The lock replied `74007706` (the first actuation ack we
   ever received) and **the physical bolt opened**. Two prerequisites mattered:
   the app must not hold the single BLE connection, and actuation needs the
   owner's session (the test account handshakes but does not actuate).

### Robustness and the trailer — both resolved (2026-08-14)

**Robustness.** CLOSE (`740002003a12`, seq `02`) then OPEN (`74010100b917`,
seq `01`) in two *separate* fresh sessions both actuated the bolt and both
replied `74007706` — seq went `02` then `01` across sessions and both were
accepted. The lock does **not** validate the sequence across sessions.

**Trailer cracked (Finding 5).** A run of ~8 app presses (open/close alternating;
"retract bolt" turned out to be just another open) captured nine
`(direction, seq, frame)` samples. The frame is:

```text
74 <dir:1> <seq:2 LE> <trailer:2 LE>     dir = 01 open / 00 close
trailer = base_dir + seq                 base_open = 0x17b8, base_close = 0x1238
```

The trailer increments by exactly 1 with the sequence (`b917, ba17, bc17, …`),
which rules out a CRC — it is **additive**. `build_operate_frame(open, seq)`
reproduces all nine captures and synthesises any command, so this is a real
builder, not replay. The bases were derived from one device and may be
device-specific (unconfirmed on a second lock). Sequence choice is free because
the lock ignores it across sessions, so `seq=1` per fresh session is fine.

## Safety

The read-only probes earlier sent only getters. The actuation in Finding 4 was
explicitly authorised by the owner, who was present and watching; the bolt was
opened on purpose as the spike's goal.
