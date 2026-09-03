# U200 language-OTA `0x90` token — living investigation log

## ✅ RESOLVED (2026-09-02) — the `0x90` is standard AES-CCM under the session key+nonce; NO secret `expandedIv`

Proven by a live Frida hook on **BouncyCastle `CCMBlockCipher`** (reached via
`NativeModules.LHRNEncryption`, methods obfuscated to `a()`/`c()`/… — resolved by
parameter types) during a real voice-pack download on the gadget app:

- Every CCM op in the whole session — control-channel keepalives AND the OTA
  control messages — used **one** `AEADParameters`: **key
  `ffd5e302ca27faba3fe1d2007e706765`** (16 B), **nonce
  `78503198e7bae54bd4cefbad8b`** (13 B), **associatedText = null**, macSize 32
  bits (**4-byte tag**). No second nonce, no `expandedIv` field ever appeared.
- **Byte-exact offline reproduction** with Python `AESCCM(key, tag_length=4)
  .encrypt(nonce, pt, b"")`: `2f012f`→`7b1db83eb71599` ✅, `{"ID":255}` plaintext
  `047b224944223a3235357d00`→`5067b566cfeeb8be3fe54954…` ✅, and it **decrypts**
  the lock's own frames (`\x10{"ID":0,"xfer_statu":"success","progress":100}`).
- So the JS `encryptAESCCM(sessionKey, expandedIv, nonce, …)` collapses: the
  BouncyCastle nonce IS the session nonce; `expandedIv` is not an extra secret.
  This is the **same AES-CCM our `control_codec.py` already runs** (key=cloud
  sessionKey, tag 4, empty AAD) — so the OTA is computable from the session
  material `aqara_ble/kdf.py` already derives. **No Frida/root at runtime.**
- The OTA control protocol is JSON short-packs over this CCM: app→lock
  `{"ID":255}` (start) then chunk IDs; lock→app `{"statu":0,"ID":…}` and
  `{"ID":0,"xfer_statu":"success","progress":100}`. Bulk `.bin` blocks stream as
  **plaintext** ff91 `0x11` frames (framing = CRC-16/XMODEM, §7, already solved).

**⇒ Autonomous language OTA is now unblocked end-to-end.** Remaining work is pure
plumbing in `aqara_ble` (no more RE): drive the JSON OTA command sequence +
plaintext block framing inside the existing authenticated session, encrypting
control frames with the session key+nonce via `control_codec`.

Proven primitives are landed in **`aqara_ble/ota_language.py`** (+
`tests/test_ota_language.py`, 9 tests incl. the REAL captured CCM vectors below):
`ota_encrypt`/`ota_decrypt` (thin `control_codec` wrappers — the OTA crypto),
`crc16_xmodem` (framing) + `crc16_mijia` (short-pack, CRC-16/MODBUS),
`frame_data_block`/`iter_data_frames` (the `[02 seq (ff-seq)] block XMODEM`
segmenter).

**The full OTA command protocol — CAPTURED end-to-end (2026-09-02, a live
Français download hooked from the start, decrypted via the session key+nonce):**

```
APP→LOCK  {"ID":255}
LOCK→APP  {"statu":0,"ID":255}
APP→LOCK  {"MCU_role":"receiver","file_info":{"name":"U200_FR_audio_burn.bin","size":1664596,"crc32":"14711156"}}
LOCK→APP  {"statu":0,"ID":1}
          … bulk .bin blocks stream as plaintext ff91 0x11 frames, XMODEM-framed …
LOCK→APP  {"ID":0,"xfer_statu":"success","progress":100}
APP→LOCK  {"ID":255}
LOCK→APP  {"statu":0,"ID":255}
```

**LIVE library push — LANDMARK result (2026-09-02).** `tools/push_language_ota.py`
built the whole ES transfer from `U200_ES_audio_burn.bin` (CDN) and drove it via
`U200Client.push_voice_pack_ota` over the ESP32-S3 — NO captured frames, NO Frida.
The lock **fully engaged for the first time ever** (every prior replay got 0 acks):
authenticated, then `{"ID":255}` → `{"statu":0,"ID":255}`, manifest →
**`{"statu":0,"ID":1}`** (lock parsed+accepted our ES name/size/crc32), then a raw
`1106`, then `{"xfer_statu":"abort"}` at **~11.3 s** (early — the streamer kept
blasting all 8400 frames to a lock that had already aborted; only 4 ff92 acks vs
the app's 1637). **Diagnosis: the data phase is ID-driven FLOW CONTROL** (the
lock's `{"statu":0,"ID":1}` is a request for block 1; the app's ~1637 acks are
per-block requests). Our driver blasted instead of waiting per-block → abort.
**Iteration (2026-09-02, same session) — down to a pacing stall at ~block 200.**
Two bugs fixed after correlating the app's post-manifest ff91 writes with its
ff92 acks:
1. **Missing init frame** — before any block the app sends
   `0x11 01 00 ff || <128B: filename NUL decimal-size space, zero-padded> ||
   CRC16-XMODEM` (marker `01 00 ff` = init block, seq 0). Verified byte-exact vs
   the FR capture (`…9071`). `build_ota_init_frame` + `build_ota_data_plan` now
   emit it; without it the lock aborts right after the manifest.
2. **Per-block chunking** — each 1024-B block's XMODEM segment is chunked into
   0x11 writes independently (a write never spans two blocks): 5 writes/block
   (4x244 + short tail). `iter_ota_data_writes` now matches the capture's first 7
   writes byte-for-byte.
Plus **ack-driven flow control** in `run_voice_pack_ota` (send init, wait its
ack, then keep ≤`window` blocks ahead of the ff92 acks). Live result jumped from
**4 acks → 201 acks**: the lock now flow-control-acks every block and accepted
~200 blocks of our from-scratch ES pack, then **stalled at ~block 200**
(`[1001/9919] ff92 acks: 201`, no progress for 100 s). So the whole protocol is
right; the remaining issue is transfer robustness past ~10 % — likely pacing
(too fast for the lock's flash write past a buffer), a keepalive-cadence detail,
or ESP32-link backpressure. **Next: tune pacing (try `window=1` strict + slower
`data_delay`, keepalive more often) and/or check for write backpressure on the
bumble transport.** Crypto, manifest, init, framing, auth, per-block flow control
all proven. Lock left on Français (ES not applied — partial OTA doesn't commit).

**Deeper (2026-09-02, from the saved captures + `window=1` live runs) — the block
is DETERMINISTIC and the lock emits a NAK code `1115`.** Verified from
`btsnoop_end.log`: a healthy transfer's ff92 acks are ONLY `1106` (x1629, one per
block), `1143` (x3, start/end), and the `0x90` control acks — **`1115` never
appears**. Our seq wrap is byte-identical to the app (block#256 `02 00 ff`, …,
checked vs the capture). With `window=1` the ES push fails at **block 262 every
time** (delay 10 ms → the lock sends `xfer_statu:abort`; delay 25 ms → it goes
silent) and the last ff92 acks before it are a burst of **`1115`** — so the lock
is NAK'ing block ~262 as bad and, getting no correct resend, aborts. Two open
explanations: (a) the ESP32-S3 HCI controller deterministically corrupts a
WRITE_WITHOUT_RESPONSE around that offset (a buffer boundary), or (b) `1115` is a
YMODEM-style NAK the app answers by RE-SENDING the block — which the app's
captures never show because the app never hits a bad block. **Next: (1) implement
retransmit-on-`1115` in `run_voice_pack_ota` (on a `1115` ff92 ack, resend the
last block group), and/or (2) rule out the ESP32 by pushing over a different
transport / checking bumble's ACL completed-packets flow control.** All of crypto,
manifest, init, framing, auth, and 1:1 block flow control (up to ~260 blocks) are
proven; the single blocker is surviving the `1115` at block 262.

**RESOLVED the `1115` — it IS a YMODEM-style NAK; retransmit-on-NAK works and
takes the transfer to ~95% (2026-09-02).** `run_voice_pack_ota` now retransmits a
block when the lock returns `0x1115` on ff92 (`max_resends`, default 30). Live
result jumped from a hard stop at block 262 to **2299 ff92 acks (~all ~1983
blocks, +~315 resends)** — the transfer flows the whole way. BUT it does not
reliably COMPLETE: it is **non-deterministic** — one run reached 2299 acks near
the end, another `xfer_statu:abort`ed at 526 acks. Root cause is now clearly the
**ESP32-S3 HCI transport**: it corrupts a large fraction (~16 %) of the
`WRITE_WITHOUT_RESPONSE` ff91 packets under sustained load; the lock NAKs each bad
block with `1115`, retransmit recovers most, but too many corruptions on one
block (or a corrupted control frame) eventually makes the lock abort. ff91 is
WRITE_WITHOUT_RESPONSE-only (no with-response fallback). **The OTA protocol +
implementation are complete and correct; the remaining blocker is transport
reliability, not the OTA logic.** To finish: run over a reliable BLE path (the
phone's native stack never corrupts; a better ESP32 firmware / HCI flow-control
fix; or a different adapter), or add end-to-end resend of any block the lock
never positively acks. Lock still on Français (ES never committed — partial/
aborted OTA does not apply).

**ESP32 hard-reset tried (2026-09-02) — confirms the transport is the wall.** A
clean DTR/RTS hard-reset of the ESP32-S3 before the push made the FIRST ~1550
blocks transfer nearly 1:1 with almost no `1115` NAKs (vs corruption from block
~262 on a degraded adapter) — so the corruption is accumulated-load/state
degradation, and a fresh adapter helps. But past ~1550 blocks it returns hard: the
run streamed **27256 data frames** (2.75x the 9919 needed — i.e. ~17k retransmits)
over 406 s and still ended in `xfer_statu:abort`. So resetting delays but does not
cure it; the ESP32-S3 cannot sustain a full ~2 MB WRITE_WITHOUT_RESPONSE transfer.
**Firm verdict: use a reliable BLE transport (the phone's native stack, a better
HCI adapter, or resetting/cooling between shorter chunked pushes).**

**Mac native BLE tried (2026-09-02) — cleaner DATA, but unstable CONNECTION.**
Added `--transport bleak` to `tools/push_language_ota.py` (CoreBluetooth hides
MACs, so it identifies the lock by name/advert, not `AQARA_LOCK_MAC`). Results
vs the ESP32: **corruption dropped from ~16 % to ~2 %** (27 NAKs over ~1160
blocks) and one run reached **~1160 blocks (59 %) — the furthest yet**. BUT the
Mac's CoreBluetooth link is unstable for this workload: connects are slow/variable
(7–25 s) and the connection **drops mid-transfer** (`Service Discovery has not
been performed yet` = the peripheral disconnected), even with a lock battery-pull
first. ~~Presence rule: keypad touch every ~15 s or it NAKs and aborts~~
**[CORRECTED 2026-09-03 — this was a MISDIAGNOSIS.** The ~40 s / ~16-block "NAK
then abort" was NOT keypad-presence expiry; it was the missing VOICE_OTA_INFO_SET
command (see the SOLVED section). With that command sent, a **single** keypad
touch (for the manifest handshake) carries the whole ~10-minute transfer to 100 %
— presence does NOT need refreshing during the stream. The keypad gate applies
once, to authorise the OTA start, not periodically.]** Net: ESP32 =
stable link / corrupt data; Mac = clean data / unstable link — neither host
transport completes. **The app succeeds because the phone's own BLE stack is both
stable and clean.** Options to finish: an Android/phone-hosted push, a better HCI
dongle, or chunked pushes with reconnect+resume (needs an OTA "resume from block
N" — untested; the app always sends from block 1). Protocol + library are done;
this is purely transport. Reached 59 % from-scratch over Mac BLE.

**ROOT CAUSE of the Mac corruption FOUND + FIXED (2026-09-02, via research —
bleak discussion #1589, Apple CoreBluetooth docs).** macOS/CoreBluetooth
**silently DROPS** write-without-response packets sent faster than the controller
can take them, and **bleak does not gate on the readiness signal** (its
`peripheralIsReadyToSendWriteWithoutResponse` delegate is never called in
practice). Blasting the OTA in a tight loop is exactly what corrupts blocks (the
lock NAKs `1115`) and makes macOS drop the link. Fix landed in
`session.py::_await_wor_ready`: before every ff91 write we poll
`client._backend._peripheral.canSendWriteWithoutResponse()` (verified this
attribute path + method exist on the installed bleak/pyobjc) and wait until ready;
no-op on bumble/BlueZ/WinRT (they do their own ACL flow control). **Effect,
live-confirmed: corruption on Mac went from ~2–16 % to runs of 0 NAKs — one
streamed ~980 blocks with ZERO NAKs.** Two more robustness fixes in
`ota.py::run_voice_pack_ota`: (a) **re-send the start+manifest every
`manifest_resend_s` for up to `manifest_wait_s`** so a single keypad presence
pulse anywhere in the window lands an acked manifest (the presence window is too
short to hand-time against the variable connect); (b) a **`post_manifest_settle_s`
pause** after the manifest ack so the keypad event that woke the lock doesn't NAK
the first blocks. All three are the correct, research-backed fixes and the tests
stay green (41 in the OTA/session/API suites).

**Remaining (2026-09-02, end of a ~30-attempt session): environmental
degradation, not code.** After that many connect/OTA cycles BOTH the lock's OTA
state and the macOS CoreBluetooth stack gum up — connects go slow/variable
(6–25 s) and drop, and outcomes turn erratic (clean 980-block run early → quick
aborts later) even right after a lock battery-pull + Mac-BT toggle. The flow-
control fix is correct; a genuinely fresh environment (fresh lock, fresh Mac BT,
few attempts) is what's needed to run the ~90 s transfer to 100 %. `blueutil` is
NOT installed, so the Mac BT can't be reset from code — `brew install blueutil`
would let a future session reset it between attempts and make this reliable.

Each JSON line is an AES-CCM short-pack (session key+nonce, tag 4, empty AAD).
`file_info` is fully computable from any CDN `.bin`: `size` = byte length
(verified 1664596), **`crc32` = the standard zlib CRC32 as a HEX string**
(`"14711156"` == `hex(zlib.crc32(bin))` == 0x14711156 == 342954326, verified).
Preceded by the auth/ECDH handshake (the large `..8U.. B…jnH…_` frames) + the
canonical 12-frame control keepalive burst + the arming reads (`SYNC_OTA_URL`
1a, `READ_LANGUAGE` 68, `VOICE_OTA_INFO_GET` a6). **Nothing about the OTA is
unknown any more** — orchestration in `ota.py` is now a pure implement.

Tools: `tools/probe_ccm_init.js` (the CCM hook, kept for re-verification),
`tools/verify_ota_framing_crc.py` (framing). Everything below is the historical
investigation that led here.

Captured CCM vectors (session key `ffd5e302ca27faba3fe1d2007e706765`, nonce
`78503198e7bae54bd4cefbad8b`, tag 4, empty AAD): enc `2f012f`→`7b1db83eb71599`;
enc `047b224944223a3235357d00` (`\x04{"ID":255}\x00`) →
`5067b566cfeeb8be3fe5495451a3eb35`; dec
`4467b566…7426fcb1e70` → `\x10{"ID":0,"xfer_statu":"success","progress":100}\x00…`.

---

**Purpose:** a systematic, incrementally-updated record of the ONE unsolved
blocker for autonomous language OTA — the 17-byte `0x90` commit token written to
ff91. Append here every attempt, result, and ruled-out path so no session
restarts blind. Companion to [language-ota.md](language-ota.md) (the settled
findings); this file is the open front.

Update rule: add a dated bullet under the relevant section for every new datum.
Never delete a ruled-out entry — that's how we avoid re-treading.

---

## 1. The goal / the one unknown

Everything about the language OTA is reproduced EXCEPT the value of the `0x90`
token. We can: fetch any language `.bin` (cloud+CDN), authenticate, subscribe
all channels, run the pre-OTA control handshake (lock replies), and stream ff91.
The lock still won't engage unless the `0x90` is right. So: **how is the 17-byte
`90 0d …` value produced, and can we compute it?**

## 2. Hard facts about `0x90`

- Written to **ff91** (AUX OTA channel, value handle 0x003c), WRITE_WITHOUT_RESPONSE.
- Appears **twice per transfer**, identical value: once opening (frame 0), once
  closing (after the activation tail). A second opening frame is `90 0a …` (110 B).
- Captured value (2026-09-02 Français transfer): `90 0d 55d9bea3755376155b749ca0066d93`
  (17 bytes = `90` prefix + `0d` len(13?) + 15-byte payload).
- **Per-app-process**: identical across transfers within one app process;
  changes after a force-stop/relaunch; stable across BLE reconnects within a
  process (see history in [operations.md] + [[clean-session-start-here]]).
- All OTHER ff91 frames use prefix `0x11`; only these use `0x90`.

## 3. Channel map (SETTLED — not the blocker)

Authoritative live `dump_gatt.py` == [gatt-map.md](gatt-map.md). During a real
transfer every write/notif is on a library-known channel; OTA acks come only on
ff92 (0x003e), 1637 of them. No unknown/mis-mapped channel. Full audit in
[language-ota.md](language-ota.md) §3.

## 4. Approaches TRIED and RULED OUT

- **Verbatim replay of captured `0x90`, unauthenticated** (2026-09-02, ×3):
  ff92 silent, no engage. Ruled out "standalone plaintext blast".
- **Verbatim replay inside a full authenticated session** (auth+CCCD+control
  keepalives) (2026-09-02): ff92 still silent. Ruled out "just needed a valid
  session".
- **+ the exact pre-OTA control arming reads** (SYNC_OTA_URL 0x1a, READ_LOCK_
  LANGUAGE 0x68, VOICE_OTA_INFO_GET 0xa6 family 0x03 — decoded from the capture's
  control channel via keystream reuse): **lock REPLIED to all three** yet ff92
  still silent. So auth+control+handshake are byte-correct; the `0x90` value is
  the gate. → session-bound.
- **Native Frida hook on `liblumidevsdk.so` crypto exports** (2026-09-02):
  hooked 9 crypto-ish functions (aes/encrypt/sign/getEncrypted…), scanned their
  args/returns for a 17-byte `0x90` buffer. A FULL successful Français transfer
  ran (download reached 100% on the gadget build) and the hook caught **ZERO**.
  → the `0x90` is NOT built in the liblumidevsdk native crypto functions.
- **Module enumeration during the transfer** (2026-09-02): 404 modules, **no
  native BLE lib** (no react-native-ble, no gatt lib), and **`libaqara_ed.so`
  never loaded** (the "loads on BLE connect" hint from native-libs.md did NOT
  hold this run). → the ff91 write is driven by the **Android Java framework**
  (BluetoothGatt), and the `0x90` bytes are assembled in **Java or Hermes JS**,
  not in a hookable `.so` export. This is why native-export hooking found nothing.

## 5. Current leading hypotheses (open)

1. **`0x90` built in the RN plugin's Hermes JS** (VoiceOtaPage / BleCommander /
   the OTA writer). If so, it's readable in the DECOMPILED bundle — no live hook
   needed. ⇐ **being checked now** (§7). Note: rn-device-plugins.md:77-82 said
   the *quick-pick language byte* (0x03 scheme) is built in a native module, NOT
   the JS — but that is a DIFFERENT value from the OTA `0x90`; don't conflate.
2. **`0x90` built in Java** (app dex, SecNeo-protected). Would need a passive
   Java approach (Java.perform/Java.use survive SecNeo; active `.implementation`
   crashes — native-libs.md golden rule) or the dex.
3. **`0x90` = f(session material)** — derived from the ECDH sessionKey/nonce/
   verifyData the lock also holds, hence per-process and lock-verifiable. If the
   JS/Java shows the inputs, we compute it in aqara_ble's authenticated session.

## 6. Tooling / assets in hand

- `tools/replay_ota.py` — authenticated OTA stream (post_auth hook) + control
  arming + ff92 listener. Reusable once `0x90` is known.
- `aqara_ble/ota.py`, `session.py::PostAuthContext`, `client.push_language_ota`.
- `tools/probe_ota_0x90.js` — native hook (wrong target, kept for reference).
- Native libs pulled: `scratchpad/native/liblumidevsdk.so`, `libaqara_ed.so`.
- **U200 RN plugin (v3.0.5)**: `scratchpad/native/u200-plugin/` — downloaded
  from CDN `.../rn/eddb8f69feea48368f8827bac13a37f9.zip`; Hermes bundle
  `aqara.matter.4447_10242.main.bundle` being decompiled to `decompiled.js`.
- Keystream-decode method for the control channel (static per-connection nonce,
  anchor on HEART_PCK 0x2f) — see language-ota.md §4.

## 7. Decompiled-JS review — BREAKTHROUGH (2026-09-02)

Decompiled the U200 plugin v3.0.5 Hermes bundle (`hbc-decompiler`, 818k lines,
`scratchpad/native/u200-plugin/.../decompiled.js`). This **reframes the whole
problem**: the `0x90` is NOT an opaque native token needing a live Frida hook —
the OTA has its own **AES-CCM crypto layer keyed by the session material we
already derive**, and it's all in this JS. No native hook needed.

**Findings (with line numbers in `decompiled.js`):**

- The OTA channel is literally named **YMODEM** in `BleUUID.ts` (line 94951):
  `SERVICE_YMODEM=ff90`, `WRITE_UUID_YMODEM=ff91`, `NOTIFY_UUID_YMODEM=ff92`.
  Confirms the "YMODEM bulk transfer" label in gatt-map.md.
- The transfer driver is **`LockOTADataTransformer` / `LockOtaDataManager` /
  `YModemManager`** (region ~319900–322000, saved as `ymodem_region.js`).
  Methods: `getShortPackString`, `getLongPackString`, `getSendCmdByResHead`,
  `generateFragment`, `sendShortPack`/`sendLongPack`, `handleResponse`, `mainCmd`.
- **The control packets are AES-CCM ENCRYPTED** (this is the key). Both encode
  and decode call `AHEncryptUtil.encryptAESCCM(sessionKey, expandedIv, nonce,
  data, …)` / `decryptAESCCM(sessionKey, expandedIv, nonce, …)` (ymodem_region
  ~line 900–920 decode, ~1075–1085 encode), and append `getMijiaCrc16String`
  (Mijia/Xiaomi CRC16) as the trailer.
- The crypto keys are a **3-value session bundle `{sessionKey, nonce,
  expandedIv}`**, set via **`initSessionKey(sessionKey, nonce, expandedIv)`** /
  `initOtaSessionKey` (line ~106191) and fed into the OTA manager
  (`setSessionKey`/`setNonce`/`setExpandedIv`, lines 240634/240658/240682).
  **We already derive `sessionKey` and `nonce`** in `aqara_ble/kdf.py`; the ONLY
  new input is **`expandedIv`** (kdf.py does not produce it yet).

**⇒ The `0x90` (and every OTA control frame) = `0x90` prefix + AES-CCM(sessionKey,
expandedIv, nonce, <plaintext>) + Mijia-CRC16.** It is computable, not
session-bound-unknowable. A captured value fails on replay simply because it's
ciphertext under a DIFFERENT session's key — exactly consistent with all our
replay failures. Compute it fresh under our own authenticated session and it
will validate.

### Concrete remaining unknowns (all reversible from THIS JS — no device needed)

1. **`expandedIv` derivation** — where `initSessionKey`'s 3rd arg is computed
   from the ECDH session (callers at lines 105314, 245619, 245759). This is the
   one input `kdf.py` lacks. Likely a KDF/expansion of the sessionKey or nonce.
2. **The `0x90` short-package plaintext** — what `getShortPackString` /
   `getSendCmdByResHead` feeds to `encryptAESCCM` for `mainCmd=0x90` (the
   open/commit command). Read the short-pack builder in `ymodem_region.js`.
3. **`AHEncryptUtil.encryptAESCCM` exact shape** (def ~line 239036) — is
   `expandedIv` the CCM nonce/counter block, and how does it differ from the
   control channel's plain `AESCCM(key).encrypt(nonce, pt)` in
   `aqara_ble/control_codec.py`?
4. **`getMijiaCrc16String`** — ✅ IDENTIFIED (2026-09-02): the `Crc16` class
   (@111238) uses constant `32773` = **0x8005** and init `65535` = **0xFFFF**,
   i.e. **CRC-16/MODBUS** (poly 0x8005, init 0xFFFF, refin/refout=true,
   xorout=0). This is the SHORT-PACK CRC (over `mainCmd||subCmd||data`), a
   SEPARATE CRC from the framing field below. Do not conflate the two.

   **✅ FRAMING 2-byte field — CRACKED & VERIFIED (2026-09-02, offline).** It is
   **NOT** MODBUS — it is **CRC-16/XMODEM** (poly 0x1021, init 0x0000,
   refin/refout=false, xorout=0), big-endian. Verified against
   `captures/ota/btsnoop_end.log` + `U200_FR_audio_burn.bin`: the ff91 data
   stream (0x11-payloads concatenated) is exactly, per block:
   ```
   [02 <seq> <0xff-seq>]  ||  [1024 bytes of the .bin]  ||  CRC16-XMODEM(1024B) big-endian
   ```
   seq = 01,02,03… (marker byte = 0xff-seq; the marker repeats every 256 blocks
   as seq is one byte). Checked **1625/1625 blocks, 100% of the bundle**: block
   bytes equal `blob[1024*n : 1024*(n+1)]` and the trailing 2 bytes equal
   XMODEM(block) exactly (blk1 field `b605` == XMODEM == the "b6 05" seen live;
   blk2 `3b4d`, blk3 `b902`, … all match). Last block is short.
   Reusable verifier + CRC fns + block framer saved to
   `tools/verify_ota_framing_crc.py` (`crc16_xmodem`, `crc16_modbus`,
   `frame_block`, `build_stream`). (A naive `build_stream` over pure 1024B
   slices does not yet byte-match the capture's tail — seq wraparound past 255
   and a ~695-byte trailer beyond the raw .bin remain to pin for a
   from-scratch builder; the per-block CRC law itself is fully confirmed.)
   → **the from-scratch framing is now fully solved**: an `OtaLanguageTransfer`
   can segment ANY language `.bin` (from `cdn.aqara.com`) into these framed
   0x11 chunks with correct markers+CRC — no captured bundle needed. (Repro:
   `scratchpad/test_crc2.py` this session.) The only remaining from-scratch
   blocker is the encrypted control layer's `0x90` (expandedIv), not framing.

Once 1–4 are read off the JS: implement `encryptAESCCM` + Mijia-CRC16 in
`aqara_ble`, build the `0x90` + short-packs from our session material, and
`push_language_ota` completes autonomously — no Frida, no root, generalizing to
the sibling Matter locks.

### BIG lead — it's the Xiaomi MIoT/Mijia BLE protocol (2026-09-02)

The builders are named **`getMiotShortPackString`** (MIoT = Xiaomi IoT), the CRC
is **`getMijiaCrc16String`**, and AES is **CryptoJS** (pure JS — which is why the
native `.so` hook caught nothing: the crypto runs in Hermes, not a hookable
lib). So the U200's BLE control + OTA is Aqara's build of the **Xiaomi "mible"
secure BLE stack**, which is **publicly documented / has open-source
implementations**. Reverse the remaining crypto (expandedIv, the exact CCM
construction) against those public specs instead of grinding Hermes bytecode.

**Short-pack structure — CRACKED (from `getMiotShortPackString` @108508):**
```
shortPack = mainCmd  ||  AES-CCM( sessionKey, expandedIv, nonce,
                                  plaintext = subCmd || data || CRC16(mainCmd||subCmd||data) )
```
`mainCmd` is prepended IN CLEARTEXT — which is exactly why the `0x90` byte is
visible at the front of the token while the rest is ciphertext. The 5th arg to
encryptAESCCM (`mainCmd||subCmd||data`) is likely the CCM AAD. This confirms the
whole replay-failure story: the encrypted tail is AES-CCM under THIS session's
key, so any captured value is invalid under a fresh session.

**Command enums (Constants module @66281):**
- `SendMainCmd` (app→lock, control channel ff61): SYSTEM=`01`, USER=`02`,
  LOG=`03`, ALARM=`04`, DEVICELOG=`05`, XXQ=`06`, LONG=`3f`, SYSTEM_EXT=`07`.
- `ReplyMainCmd` (lock→app): SYSTEM=`81`, USER=`82`, LOG=`83`, ALARM=`84`,
  LONG=`bf`. (So the control-channel keystream-decode from language-ota.md §4
  matches: those were SendMainCmd sub-commands.)
- **`0x90`/`0x91`/`0x11` are NOT in SendMainCmd** — they are the **YMODEM
  channel's own** command bytes (ff91), a separate command set from the control
  channel. `0x11` = data chunk, `0x90`/`0x91` = the short/long OTA control packs.
  TODO: find the YMODEM command constants + the `0x90` open command's
  subCmd/data (in `ymodem_region.js`, `sendShortPack`/`sendLongPack`, ~line 1085
  uses 145=0x91).

### Deeper trace (2026-09-02 continuation) — where each piece lives

- **Key plumbing (confirmed):** `AiotLockConnector.getInstance().getEncryptKey()`
  returns `{sessionKey, nonce, expandedIv}` (def @238517 getEncryptKey / @238547
  setEncryptKey — pure store/return). `initOTAManagerData` (@326855) pulls it and
  calls `LockOTADataTransformer.setEncryptData(key)`. `BleCommanderClass`
  (@106138) holds `initSessionKey(sessionKey, nonce, expandedIv)` /
  `initOtaSessionKey` (@106191). So all three travel together as one bundle.
- **`expandedIv` is derived CLIENT-SIDE** — the cloud `verify` response gives
  only `{sessionKey, nonce, verifyData, mac}` (kdf.py doc), so `expandedIv` is
  computed locally in `AiotLockConnector` right after the session-verify step.
  NOT yet pinpointed: the exact formula (register-renamed Hermes bytecode is
  opaque to read). Next-session leads: (a) disassemble to `.hasm` (hbc-decompiler
  pseudo-JS hides the math; the raw HASM shows the ops) and read the
  AiotLockConnector verify-success handler where sessionKey/nonce land; OR
  (b) **live-hook the NATIVE AES primitive** that `AHEncryptUtil.encryptAESCCM`
  ultimately calls (react-native-quick-crypto / a native AES in the app) and read
  its (key, iv, nonce) args directly — this is the correctly-targeted native hook
  (the earlier one guessed liblumidevsdk crypto and missed; target the AES the JS
  actually calls). Check the dlopen/module list for a quick-crypto / openssl-ish
  lib during a transfer.
- **Response decode shape (from `handleResponse` @107353):** strips the first 6
  chars of the hex response, then `decryptAESCCM(sessionKey, expandedIv, nonce,
  body)`; frame markers `'fe'`/`'00'`/`'01'` gate is-end; CRC mismatch raises
  `ERROR_CRC_INCORRECT` (so Mijia-CRC16 is validated both ways). The `getShortPack
  String`/`getLongPackString` builders (ymodem_region.js) are the send side —
  read them for the `0x90` mainCmd plaintext (item 2).
- **Regeneration (no device):** plugin is public — re-download
  `cdn.aqara.com/cdn/appadmin/mainland/rn/eddb8f69feea48368f8827bac13a37f9.zip`
  (bundleId aqara.matter.4447_10242, v3.0.5), `hbc-decompiler <bundle> out.js`.
  For the math, prefer a HASM disassembly of the same bundle.

## 9. Offline JS/HASM review — CORRECTION: the crypto is NATIVE, not CryptoJS (2026-09-02, later)

Followed §7's plan (camino 1: pure offline, no device — decompiled.js + the
`.bundle`). Result: **the short-pack is fully decoded, but the two remaining
unknowns (`expandedIv` + the exact CCM construction) are NOT in the JS — they
live in a native RN module. §7's "AES is CryptoJS, no native hook needed" claim
is WRONG and is corrected here.**

**Decoded fully from JS (reimplementable):**
- **Short-pack builder** `getMiotShortPackString(cmdObj, sessionKey, expandedIv,
  nonce)` (JS body @242855–242905, confirmed byte-by-byte):
  ```
  crc       = getMijiaCrc16String(mainCmd || subCmd || data)   # CRC over mainCmd||subCmd||data
  plaintext = subCmd || data || crc                            # NOTE: mainCmd is NOT in the plaintext
  ct        = encryptAESCCM(sessionKey, expandedIv, nonce, plaintext, aad = mainCmd||subCmd||data)
  shortPack = mainCmd || ct                                    # mainCmd stays CLEARTEXT at the front
  ```
  So AAD = `mainCmd||subCmd||data`, plaintext = `subCmd||data||CRC16`. This is
  exactly why `0x90` shows in the clear and the rest is ciphertext.
- **CRC** = `getMijiaCrc16String` has a real JS body (@111216 / @242390) — CRC-16/
  MODBUS (poly 0x8005, init 0xFFFF). Reimplementable.
- **Key bundle** `{sessionKey, nonce, expandedIv}` is shuttled via
  `getEncryptKey`/`setEncryptKey`/`initSessionKey` (all pure store/copy getters).

**The wall (native, NOT crackable offline from the JS):**
- **`encryptAESCCM` / `decryptAESCCM` have NO JS body anywhere in the 818k-line
  decompile** (grep for `Original name: encryptAESCCM` → 0 hits; only
  `getMijiaCrc16String` and `getMiotShortPackString` have JS bodies). They are
  **native methods of `NativeModules.LHRNEncryption`** — `EncryptionModule.ts`
  literally resolves as `EncryptionModule.default = react-native.NativeModules.
  LHRNEncryption` (decompiled.js line 109955). `AHEncryptUtil` is that native
  module. So the exact CCM construction (how `expandedIv` and `nonce` combine
  into the CCM nonce/counter, tag length, AAD wiring) is in a `.so`/JNI, not JS.
  → **This is the REAL reason the earlier `liblumidevsdk.so` hook caught nothing:
  not "because CryptoJS", but because it hooked the WRONG native lib. The right
  target is named: `LHRNEncryption`.**
- **`expandedIv` is NEVER computed in the visible JS** — searched every
  assignment; all are getter/setter copies. And critically (kdf.py): the **cloud
  `verify` returns only `{sessionKey, nonce, verifyData}` — NOT `expandedIv`**.
  The JS login/verify path stores only sessionKey+nonce onto the connector
  (decompiled.js 245120-245125); it never sets `expandedIv` from any response.
  So `expandedIv` is minted **client-side in the native `LHRNEncryption` module**
  from the session material — invisible to both the cloud replay and the JS.

**The pivotal unanswered question (decides whether OFFLINE is even possible):**
is `expandedIv = f(sessionKey, nonce)` — both of which WE already derive from the
cloud (kdf.py) — or `f(hidden ECDH shared secret / verifyData)` which the cloud
never hands us? The JS can't answer it (derivation is native). Also note our
working control channel (`control_codec.py`) uses `AESCCM(sessionKey, tag=4).
encrypt(nonce, pt, aad=b"")` with the cloud `nonce` as the CCM nonce and EMPTY
AAD; the OTA CCM differs by (a) the extra `expandedIv` arg and (b) a non-empty
AAD — so it is NOT the same call as the control channel.

**⇒ Sharpest next step (one cheap native hook, correctly targeted this time):**
run our OWN authenticated session (replay_ota.py already derives a fresh
sessionKey+nonce live) and native-hook **`LHRNEncryption.encryptAESCCM`** (its
`.so` export / JNI method — SecNeo-safe native hook, gadget build) to capture the
`expandedIv` argument it passes ALONGSIDE our known sessionKey+nonce, for one
transfer. Then:
- if `expandedIv` is reproducible from (sessionKey, nonce) → reverse that small
  function, implement CCM+CRC in aqara_ble, go fully offline/autonomous forever;
- if it depends on hidden ECDH material → autonomous offline OTA is impossible;
  the hook (or a session-material leak) is required each run.
**The `.so` is IDENTIFIED: `libdatajar.so` — and it's Java, not C (2026-09-02).**
Swept every `lib/arm64-v8a/*.so` in `split_config.arm64_v8a.apk` for the strings
`encryptAESCCM`/`decryptAESCCM`/`LHRNEncryption` — the ONLY hit is
**`libdatajar.so`** (152 MB). It is the **SecNeo-packed Java/DEX blob** (an ELF
whose cleartext string pool holds Java class descriptors), containing:
- `encryptAESCCM`, `decryptAESCCM`, `getExpandedIv`, `setExpandedIv`,
  **`getAESCCMSecretKey`** (Java getters/setters + the crypto entrypoints);
- **`Lorg/bouncycastle/crypto/modes/CCMBlockCipher;`** — the AES-CCM is **stock
  BouncyCastle Java**, i.e. a 100%-standard AES-CCM (reimplementable in Python
  with `cryptography`'s `AESCCM` in a few lines — no custom nonce folding to
  reverse, only the parameter wiring);
- app classes `com/lumi/arn/pkgs/ahdoorlock/*` (the lock RN package, obfuscated
  a–r) and `com/lumi/blelibrary/ble/*`.

⇒ **So `LHRNEncryption.encryptAESCCM` is a Java method over BouncyCastle, NOT a
native C export.** A native-`.so`-export Frida hook cannot catch it (it runs as
DEX bytecode on ART). `getExpandedIv`'s derivation logic is in the packed DEX
bytecode (not the cleartext string pool), so still not readable statically here.

**Refined hook target — cleanest path, sidesteps SecNeo:** passively hook
**`org.bouncycastle.crypto.modes.CCMBlockCipher.init(boolean, CipherParameters)`**.
It is a LIBRARY class, not app code — SecNeo watches app classes, so a passive
Java hook here should not crash (unlike the app-class Java hooks that did). Its
`init` receives the `AEADParameters` = (key, macSize, nonce, associatedText) for
EVERY CCM op incl. the `0x90` short-pack. One captured transfer reveals the real
key/nonce/aad aligned with OUR derivable sessionKey+nonce → settles the pivotal
question (expandedIv = f(sessionKey,nonce) vs f(hidden ECDH)) AND yields the exact
`0x90` plaintext. Secondary (more specific but app-class = SecNeo risk, reads
only): hook `getExpandedIv`/`getAESCCMSecretKey`/`encryptAESCCM` on the
`ahdoorlock` class. `tools/probe_ota_0x90.js` should be replaced with this
CCMBlockCipher.init passive-read hook (it currently targets liblumidevsdk native
exports — wrong layer entirely).

## 8. Environment notes (so a session doesn't rediscover)

- Phone: gadget-repacked app (`com.lumiunited.aqarahome.play`) installed 2026-09-02,
  logged in. NOT debuggable (`run-as` fails) and NOT rooted. Gadget listens on
  27042; `adb forward tcp:27042 tcp:27042` + `tools/frida_attach.py`.
- Native hooks are SecNeo-safe; active Java overrides crash (native-libs.md).
- The app's download **% is NOT visible to uiautomator** (Hermes UI) — use
  `adb shell screencap` to read progress, not `uiautomator dump`.
- Lock currently on **Français** (OTA succeeded on the gadget 2026-09-02);
  restore to Español later. HA `aqara_u200` integration disabled (slot free).

## BREAKTHROUGH 2026-09-02 (late) — the "stuck manifest" was the FINGERBOT, not the lock

Two user instincts cracked it. (1) The keypad "has more weight than we thought":
the presence pulse is a **Tuya Zigbee fingerbot** (`switch.pulsador`, z2m) in
**click** mode. While debugging I toggled its mode and its **`upper` (rest)
position drifted 0 → 30**, shortening the click stroke so it **stopped pressing
the keypad** → no presence → the OTA manifest silently stopped ack'ing. This was
misdiagnosed as a "gummed lock OTA state." **Fix: `number.pulsador_upper` = 0**
(full 85→0 stroke). Keep it at 0. (2) "Is something connected?": verified the HA
`aqara_u200` integration is disabled and the ESP32 holds no stale BLE — nothing
was hogging the slot.

**With the fingerbot fixed + the CoreBluetooth flow-control fix, a live Mac-BLE
run streamed CLEAN to 1016 / ~1984 blocks (51%), 0 NAKs** — then hit the macOS
CoreBluetooth **connection drop at ~54 s** ("Service Discovery has not been
performed yet"). So the stack now works end-to-end; the ONLY remaining wall is
that ~54 s / ~1000-block macOS link drop (well-known Sequoia BLE bug), which is
under the ~108 s a full window=1 transfer needs.

**Two paths to 100% (both real, code side done):**
1. **Beat the drop**: finish < 54 s. window=1 is clean but ~24 blk/s; window=3 is
   faster but the tap-bleed corrupts it. Needs clean-fast pacing (or a resume).
2. **Resume-from-block-N** across reconnects (auto-retry wrapper is built:
   `--attempts N --reset-bt`) — UNTESTED whether the lock resumes vs restarts;
   test by tapping for attempt 2's manifest and watching its start block.
3. **ESPHome bluetooth_proxy** (most robust): NimBLE firmware handles the link +
   flow-control, sidestepping both the macOS drop and the fingerbot-timing race.

Fingerbot presence is also flaky (Zigbee LQI ~51, connect time varies 7–20 s), so
the manifest tap timing is a race; a proxy or an in-tool HA-driven keypad removes
it. `tools/push_language_ota.py` now has `--attempts`/`--reset-bt` and blueutil is
installed so the Mac BT can be reset between attempts from code.

## 2026-09-03 — the 16-block wall is REAL, transport-independent, and the "1016/2299 blocks" were a MISCOUNT

Hard, evidence-based findings this session (correcting earlier ones):

- **`1106` is the ONLY real per-block ack** (confirmed vs `btsnoop_start_50pct.log`:
  709 × `1106` for 708 blocks). **`1143` is the lock's RESPONSE to our `2f012f`
  keepalive** (they arrive at exactly the keepalive cadence, ~every 2 s), NOT a
  "start/end marker". `1115` is the NAK. So the older "reached ~1016 / 2299 acks"
  numbers were **counting `1143` keepalive-responses and `1115` NAKs as block acks**
  — the real `1106` count never exceeded ~16. The 51%/95% claims were artifacts.
- **The wall is exactly 16 `1106` blocks, deterministic, and TRANSPORT-INDEPENDENT.**
  Reproduced identically on the ESPHome proxy AND Mac CoreBluetooth (bleak):
  `{'1106': 16, '1115': 7, '1143': 7, '1118': 2}`, `stalled_at 17`, on every run,
  fast or slow (delay 0.02–0.15). On the Mac the 16 blocks ack in ~1.7 s (10 blk/s),
  so it is NOT pacing, presence, keepalive, or link corruption — it is a lock-side
  cap of 16 blocks. Block 16 (gi=16, seq 17) is **byte-identical to the app's**
  (verified against the capture) yet the lock NAKs it 7× → aborts.
- **Fixed a real bug**: the per-block ack gate was RELATIVE ("did blockack rise since
  I started this block") which, with ack pipelining, wrongly declared a block unacked
  and resent it forever (stuck ~block 16 with 0 NAKs). Now ABSOLUTE:
  `state["blockack"] >= base_ack + gi + 1`. After the fix the lock genuinely NAKs
  block 16 (real `1115`), exposing the true wall.

**ROOT-CAUSE HYPOTHESIS (strong): a missing setup command.** In the app's data-phase
start the ONLY thing we do not replicate is a **54-byte ff61 write** right after the
`0x90` manifest ack and before the file-info frame:
`3fa5ff08 0fc9918561087c455a3aa466c85b161843178de77867941f8a68cc19a867fbfcecc4243767c1b4ba760a9d1053132d72d5f7`.
`0xa5` = **VOICE_OTA_INFO_SET** (operations.md). Almost certainly it declares the
transfer (size / block count / window) so the lock buffers the whole stream; without
it the lock defaults to a 16-block window and NAKs the 17th. It is CCM-encrypted; the
Frida session keys on file are from a different session (InvalidTag), so it cannot be
decrypted offline.

**NEXT (the actual unblock):** capture the plaintext of the VOICE_OTA_INFO_SET (0xa5)
command with the Java Frida hook on `AqEdUtils.encryptAESCCM` (`tools/dump_ccm_java`)
during a real app language-OTA — the hook sees the plaintext BEFORE encryption. Then
send that command (encrypted under our session key) after the manifest, before the
data stream, in `run_voice_pack_ota`. Everything else (crypto, auth, manifest, init,
per-block framing, absolute-gated stop-and-wait + retransmit, keepalive) is in place
and verified; the 16→full unlock is this one command.

## 2026-09-03 (cont.) — DECODED the missing OTA "info" command; 16-wall still unsolved

Via the user's "review the logs" instinct, decoded the one command the app sends at
OTA start that our library never did, from the app's OWN successful FR transfer
(`scratchpad/ccm_fr.log`, `[CCM] doFinal in=/out=`):

    plaintext:  01 21 <md5(bin) as 32-char hex ASCII> 00 02 <len(lang)+1> <lang-utf8> 00
    FR example: 0121 "2fb6a8e43870816c3e5c3319afd903fd" 00 020a "Français" 00

**MD5(FR bin) == the captured token, byte-exact** — so it's the file MD5 (hex string)
+ the language display name, as a 2-field TLV. Computable for any pack. Added to
`run_voice_pack_ota` (helper `_lang_from_filename`, param `language_name`).

Sent it two ways: (a) as a 0x90 OTA frame subcmd 0x01 → the lock read it as a version
QUERY and replied `{"statu":4294967295,"version":1}` (0xFFFFFFFF = reject); (b) via the
control channel ff61 (`send_control`) → no reject, and **the 0x1115 NAK at block 16
DISAPPEARED** (histogram `1106:16, 1143:N, 0 NAKs`). So the command IS meaningful and
goes on ff61. BUT the transfer STILL caps at exactly 16 `1106` blocks then goes quiet
→ abort. Note the app's ff61 wire frame for it was 54 B (≈ a 3-byte long-pack header +
51 B CCM), whereas `send_control` uses a 1-byte prefix — so our framing may be subtly
off, but even so the 16-wall persists.

**The 16-block cap is ROCK SOLID and is OURS, not the lock's:** identical 16 across the
ESPHome proxy AND Mac CoreBluetooth, across strict stop-and-wait AND windowed
continuous streaming, with/without keepalive, with/without the info command. Yet the
**app got past it on this same lock THIS session** (its Spanish OTA reached 5% ≈ 99
blocks before a Frida-gadget crash blanked the screen). And the app sends NO per-16
command (only 271 total control ops in the whole 1626-block FR OTA; keepalive ~every 65
blocks). Our blocks 0..16 are byte-identical to the app's. So the difference that lets
the app stream past 16 is still unidentified — it is NOT the data framing, NOT a
per-block command, NOT transport, NOT stop-and-wait vs continuous.

**Frida hook status:** rewrote `tools/dump_ccm_java.js` to be persistent + re-scan
(`setInterval(()=>Java.perform(scan),2500)`) so one attach catches crypto classes that
only load in the lock session. It ATTACHES and unblanks the splash, but the periodic
`Java.perform` throws `access violation @0x0` in frida-java-bridge (JVMTI on this
gadget) — so the re-scan needs a different mechanism (e.g. hook a classloader / retry
enumerate on the JVM thread) before it can capture a fresh OTA. The existing
`ccm_fr.log` (older capture) had the info command; a NEW capture of the app streaming
PAST block 16 is the way to find the remaining difference.

## 2026-09-03 — ✅✅✅ SOLVED — the library completes the OTA to 100% from scratch

`{'ID': 0, 'xfer_statu': 'success', 'progress': 100}` — "language applied". The whole
2 MB ES voice pack streamed by `run_voice_pack_ota` over the ESPHome proxy, 1984/1984
blocks, 0 NAKs, and the lock reported **success** (Spanish applied). No phone app.

Two final fixes cracked it (both found by reviewing the existing logs — the user's call):

1. **The 16-block wall = a missing VOICE_OTA_INFO_SET, and its FRAMING.** The command
   (decoded from `ccm_fr.log`: plaintext `01 21 <md5(bin) hex-ascii:32> 00 02 <len(lang)+1>
   <lang-utf8> 00`) must go on ff61 with a **3-byte cleartext header `3f a5 ff`** (0xa5 =
   the SET opcode) before the CCM payload — NOT our normal 1-byte `01` control prefix.
   With the `01` prefix the lock read it as a version GET (replied 0xa6…/statu 0xFFFFFFFF)
   and kept a default 16-block window. With `3f a5 ff || CCM(payload)` the lock SETs the
   transfer and accepts the whole stream. (Sent via a direct `client.write_gatt_char`
   to CONTROL_WRITE_UUID in `run_voice_pack_ota`.)

2. **The final `abort`-at-100% = last-block padding.** The lock validates the whole
   received image against the declared MD5/CRC and reports `abort` (not `success`) on a
   mismatch. The app **pads the final partial block up to 1024 bytes with `0x1a`** before
   CRC16 (verified: our padded FR last block == the app's, CRC `2df0` byte-exact). A short
   final block passes its own per-block CRC (0x1106-acked) but fails the image check.
   Fixed in `iter_data_frames` (pad `<block_size` blocks with 0x1a).

Plus the end-of-transfer/activation tail (`0x1104` marker → zero-filled `110100ff` frame
×2 → `0x90` subcmd-04 commit ×2) added to `run_voice_pack_ota`. Correcting earlier notes:
`1106`=per-block ack, `1143`=our keepalive's response; the old "1016/2299-block" numbers
were miscounts — before today the library never got past ~16 real blocks.
