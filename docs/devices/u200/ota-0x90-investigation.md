# U200 language-OTA `0x90` token — living investigation log

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
   xorout=0). Consistent with the framing note in language-ota.md that the
   per-1024-B "2-byte field" was NOT CRC16-ARC (poly 0x8005 but init 0x0000) —
   the difference is exactly the init value. **TODO: verify** by computing
   CRC-16/MODBUS over a 1024-B block of `captures/U200_FR_audio_burn.bin` and
   matching the capture's 2-byte field; if it matches, both the OTA-frame CRC AND
   the framing 2-byte field are solved in one shot. (A first NAIVE check —
   concat all 0x11 chunks stripped of their prefix, find `02 01 fe`, CRC the
   preceding bytes — was inconclusive; that reconstruction is wrong because the
   markers stay interleaved in the stream and the OTA-frame CRC is over the
   ENCRYPTED short-pack, not the raw block. Redo with a proper framing parser
   that separates block payload from markers/CRC, per decode_ota_framing.py.)

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

## 8. Environment notes (so a session doesn't rediscover)

- Phone: gadget-repacked app (`com.lumiunited.aqarahome.play`) installed 2026-09-02,
  logged in. NOT debuggable (`run-as` fails) and NOT rooted. Gadget listens on
  27042; `adb forward tcp:27042 tcp:27042` + `tools/frida_attach.py`.
- Native hooks are SecNeo-safe; active Java overrides crash (native-libs.md).
- The app's download **% is NOT visible to uiautomator** (Hermes UI) — use
  `adb shell screencap` to read progress, not `uiautomator dump`.
- Lock currently on **Français** (OTA succeeded on the gadget 2026-09-02);
  restore to Español later. HA `aqara_u200` integration disabled (slot free).
