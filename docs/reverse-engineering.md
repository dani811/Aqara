# U200 reverse-engineering & debugging methodology

How this project reverse-engineers the Aqara U200 lock, what the moving parts are,
and the exact toolchain to reproduce reads, writes (control), and new-feature RE. Kept
here so a clean session can pick up without re-discovering any of it.

> Everything below is protocol/opcode knowledge on the maintainer's own lock and
> account. No secrets (session keys, tokens, passwords) are committed.

## 1. The two shipped packages (and their versions)

| Package | What | Where | Current |
| --- | --- | --- | --- |
| **`aqara-ble`** | Python BLE library (the protocol: cloud KDF auth, AES-CCM control channel, reads, actuation). `import aqara_ble` | **PyPI** | **1.8.0** |
| **`haos_aqara`** | Home Assistant custom integration (`aqara_u200`). Wraps `aqara-ble`. | GitHub / HACS custom repo | **0.12.0** |

**Version coupling:** the integration's `manifest.json` pins the library exactly —
`"requirements": ["aqara-ble==1.8.0"]`. Bump both together: publish the library first,
then bump the manifest pin + the integration `version`. HA installs the pinned library
on setup; if the pin is unsatisfiable the integration fails to load.

### Release / publish flow (how a version actually ships)

- **Branching:** work on `feat/NNN-*` / `docs/NNN-*` off `develop`; PR → `develop`;
  `main` and the tags are fast-forwarded from `develop` (main was stale — resynced
  2026-08-27; it is NOT the working branch). Tags `vX.Y.Z` carry the releases.
- **aqara-ble → PyPI:** creating a **GitHub Release** `vX.Y.Z` triggers
  `.github/workflows/publish.yml` (`on: release`), which builds and publishes via
  **PyPI Trusted Publishing (OIDC, `environment: pypi`)** — no token in the repo.
  So: merge to develop → `gh release create vX.Y.Z --target develop` → CI publishes.
  Verify with `curl -s https://pypi.org/pypi/aqara-ble/json` (CDN can lag a minute).
- **haos_aqara → HACS:** it's a **custom-repo** HACS integration; a GitHub Release
  `vX.Y.Z` is what HACS installs. `manifest.json` `version` must match. Its CI is
  `tests.yml` + `validate.yml` (HACS/hassfest validation), no PyPI step.
- **Tests:** the repo's pytest suite runs under a broken `pytest-asyncio` pin — run it
  with `-W "ignore::pytest.PytestRemovedIn9Warning"` to get green (the sync decoder
  tests pass; the async fixtures otherwise error at collection). The HA integration
  tests run against `pytest-homeassistant-custom-component`.

## 2. The official Aqara app (RE target)

- Package `com.lumiunited.aqarahome.play`, app-version **6.3.9** (EU cloud
  `rpc-ger.aqara.com`). **SecNeo-hardened** (libDexHelper encrypts the dex) — static
  dex analysis is blocked; the app crashes on emulators; Frida **Java** hooks crash
  SecNeo's ART protection (Frida **native** hooks are stable).
- **React Native** device plugins: the lock UI is an RN plugin. The shared SDK bundle
  `assets/lumi/reactnative/prefab/bundle/base-android-2.0.1.zip → android_base/base.bundle`
  is **Hermes bytecode v96** — disassemble with **`hbc-decompiler`** (pip-installed in
  this repo's `.venv`; `hbctool`'s `disasm` does NOT support v96, but `hbctool disasm`
  isn't needed — `hbc-decompiler` alone produces working, if verbosely register-named,
  JS). It carries i18n labels + the feature catalogue but **not** the device
  opcode↔byte enums — those live in the per-model plugin, **downloaded from a public
  CDN** (`cdn.aqara.com`, no auth) and cached on the phone. Getting the manifest that
  lists every model→plugin-URL mapping needs one Frida session (native file read); after
  that, **any model's real plugin source is one `curl` + decompile away, no device
  needed.** See [reference/rn-device-plugins.md](reference/rn-device-plugins.md) for the
  full catalog and the U200's own entry.
- HTTP stack: okhttp3 + retrofit2 + Cronet, HTTP/2. Cloud request headers ride HPACK —
  decode offline with `tools/sslfull.js` (native SSL full-hex dump, tagged by `SSL*`
  pointer + direction) + `tools/decode_h2.py` (HTTP/2 frame parser + HPACK decoder; fixes
  the two known BoringSSL/Frida quirks — `SSL*` pointer reuse across sequential
  connections, split on the client preface; and the double-hooked `SSL_write`, dedup
  consecutive-identical entries).

## 3. Debugging toolchain

### 3a. Direct BLE from the library (ESP32 transport)
`aqara-ble` talks BLE via **bleak** (host adapter) or **bumble over an ESP32-S3 HCI
bridge** (`tools/esp32s3_hci_usb`, port e.g. `serial:/dev/cu.usbmodem14301,115200`).
The stabilized link (transport.py: `supervision_timeout` 20 s, interval 30–60 ms) is
required for multi-frame bursts. `U200Client.read_burst([...])` reads many frames in
one authenticated session; frames may carry a `"PP:frame"` write-prefix (`01` default,
`03` for finger `0x20` / log `0x13` / `0x1f` / voice-OTA `0xa6`). Replies are
correlated **by opcode** (spontaneous ff62 events are skipped).

### 3b. Driving the app over USB adb (autonomous UI + capture)
- **USB DATA cable** required — a charge-only cable shows nothing in
  `system_profiler SPUSBDataType` and `adb devices` stays empty. Approve the
  "USB debugging" prompt on the phone. `adb shell svc power stayon usb` stops it
  sleeping; if it locks, `adb shell input keyevent 224` + a swipe unlocks (no PIN case).
- **Read the screen:** `adb shell uiautomator dump /sdcard/ui.xml` + pull it; the app's
  native AND RN screens expose `text=`/`content-desc=`/`bounds=` nodes. Compute a node's
  centre from `bounds` and `adb shell input tap X Y`. (RN toggles often expose no
  `checkable` — find the small clickable at the row's right edge.)
- **Launch:** `adb shell monkey -p com.lumiunited.aqarahome.play -c android.intent.category.LAUNCHER 1`.
  Login needs the account password — the human types it; Claude must not.

### 3c. Decrypting the app's BLE session (btsnoop + keystream reuse)
The control channel is **AES-CCM (tag 4, empty AAD) with a STATIC nonce per session**,
so the CTR keystream is reused across every frame → a known-plaintext recovery reads
the whole session without the key:
1. Enable HCI snoop: `adb shell settings get global bluetooth_hci_log` should be `1`
   (Developer options → "Enable Bluetooth HCI snoop log", FULL).
2. `adb bugreport report.zip` (no root; slow, run backgrounded) →
   `unzip -j report.zip FS/data/misc/bluetooth/logs/btsnoop_hci.log`.
3. `python3 scratchpad/app_keystream.py btsnoop_hci.log` — derives the keystream from
   the most-repeated frame (keepalive `2f012f`/`2f002c06`), extends it with a known
   firmware reply, XOR-decrypts all TX/RX frames, prints `pt[:12]` per frame.

### 3d. The write-opcode RE loop (how SET/control opcodes are found)
Reproducible for any setting: **open the setting in the app → change its value → the
app writes the SET frame on ff61 → `adb bugreport` → decode (3c) → read off the opcode
and value bytes.** Confirmed byte-for-byte against the read value each time. This yields
BOTH the enum byte-mapping and the write frame, so the library can **control**, not just
read. Confirmed writes are catalogued in
[devices/u200/operations.md](devices/u200/operations.md).

### 3e. The keypad gate (important)
Several settings screens ("Sonido de voz" = volume/language, auto-lock, night-latch,
etc.) are gated: opening them pops **"Please activate the keypad first — press any
keypad key"**. It does not clear itself — you close it, physically press a keypad key,
then re-enter, and the entry must happen inside the lock's short post-touch presence
window. Because that window is short and every gated sub-action re-checks it, RE of
these settings needs the keypad pressed **repeatedly / continuously** through the
navigation. Automating that physical press (so a machine can drive it unattended) is
left to the reader's ingenuity — a small physical button-pusher aimed at the keypad is
one obvious option. The lock's **capacitive** keypad expects a finger-like (conductive)
touch, and the presser must actually depress/contact a key, not merely nudge the body.

### 3f. Home Assistant as a live probe
With the HA connector, the integration's "Refresh over Bluetooth" button drives a real
BLE read (state→battery→door→assist→pull→config). BLE coverage needs a **Bluetooth
proxy in range** of the lock (ESPHome BT proxy or the host adapter); the U200 only
advertises briefly after a keypad touch, so `binary_sensor..._conectividad` flips on
only when a scanner hears that advertisement. Note: the app and HA compete for the
lock's **single BLE slot** — disable the `aqara_u200` integration while driving the app,
re-enable it after.

### 3g. The device-binding capture (multi-front, one-shot — prepared 2026-08-31)

**Why**: every write/read opcode captured so far assumes the lock is **already
bound** to the account. The one flow never captured is **binding a brand-new
lock** — and it's the one plausible moment a per-lock secret could reach the
phone at all, if (as competitor locks confirm — see below) the offline-password
seed is synced cloud→lock once, at pairing, via the phone as a BLE relay, the
same pattern already reverse-engineered for the ECDH pubkey exchange in
`kdf.py`. Two competitor lock ecosystems confirm this exact pattern in their
own words: igloohome's algoPIN ("connects to the cloud to sync access
credentials... once stored locally, the device operates completely offline")
and Tuya BLE locks (a factory-assigned per-lock "auth key" stored on Tuya's
cloud, released to the app once during setup). This is the strongest, most
concrete remaining lead for the offline-password blocker — attack the
**lock↔cloud** relationship at the one moment it's observable (via the phone),
not the app↔cloud one already solved.

**This is a one-shot, disruptive capture** (un-bind + re-bind the maintainer's
real lock) — do not attempt without the maintainer present and an explicit
go-ahead for that specific step. Everything else below (tooling setup,
verification) can be prepared/tested beforehand without touching the real
binding.

#### Before touching the real lock: verify tooling health

Ordinary use this session already proved the repacked app fully functional
(login persists, screens navigate, cloud+BLE-adjacent calls all work) — but
`screencap`/`screenrecord` went briefly black once after a cold relaunch. Before
the real attempt:
1. `adb devices` shows the phone; `adb forward tcp:27042 tcp:27042`;
   `python3 tools/check_gadget.py` reports `CONNECTED`.
2. Cold-relaunch the app once (`am force-stop` + `monkey -c LAUNCHER`), then
   confirm `adb shell screencap -p` returns a **real, non-black** PNG before
   relying on it for timing correlation. If it's black again, don't burn time
   debugging it — fall back to `uiautomator dump` text/bounds only for that
   session (still enough to know which screen is showing).
3. Confirm HCI snoop is still ON: `adb shell settings get global
   bluetooth_hci_log` → `1`. It has silently reset to OFF before (Bluetooth
   toggle, phone restart) — re-enable via Developer Options → "Enable
   Bluetooth HCI snoop log" → FULL if not.

#### Plan A vs. Plan B (decide BEFORE un-binding)

**Plan A (default): use the current Frida-gadget-repacked app.** All of
today's captures (btsnoop + `tools/sslfull.js`) worked cleanly on it. Risk:
a device-**binding** flow specifically might call an integrity/attestation
check (e.g. Play Integrity) that a resigned, non-Play-Store APK fails — normal
navigation wouldn't trigger this, binding new hardware plausibly would, as an
anti-fraud measure. There's no way to know without trying.

**Plan B (fallback, only if Plan A's binding step visibly fails/errors):**
reinstall the **official, unmodified** APK for this one action.
`docs/reference/rn-device-plugins.md`/`tools/frida-setup.md` have the repack
procedure to reverse if needed; keep the repacked APKs so re-patching later is
fast. Under the official app: **no live Frida HTTPS decode** for this specific
attempt (the earlier mitmproxy/WireGuard MITM approach in
`specs/037-cloud-session-mitm` hit unresolved network-security-config/pinning
issues — it is NOT a reliable fallback for HTTPS). BLE-side (btsnoop) still
works fully regardless of which APK is installed — it's a phone-OS-level
capture, not app-instrumented. So Plan B means: full BLE capture, no HTTPS
capture, for that one attempt. If Plan A works, this whole paragraph is moot.

#### The fronts to run simultaneously (start ALL of these before un-binding)

1. **BLE — HCI snoop (continuous, whole session)**: already running as long as
   the setting is ON (step 3 above); nothing to "start", just don't forget to
   pull it via `adb bugreport` **immediately after** binding completes (a
   bugreport is a point-in-time snapshot of the rolling log, not a live tail —
   the sooner it's pulled after the event, the less other traffic has pushed
   the interesting frames out of the rolling buffer).
2. **HTTPS — `tools/sslfull.js` (Plan A only)**: attach **once**, before
   starting the un-bind/re-bind sequence, and leave it running for the
   **entire** flow (do not detach/reattach mid-flow — repeated attach/detach
   cycles are what's suspected of destabilizing SecNeo's protection). Use a
   long duration (the binding wizard likely takes minutes, not the ~60-90s
   windows used earlier today) — either raise `frida_read.py`'s
   `done_event.wait(timeout=...)` well past the expected flow length, or run
   the script with no timeout and manually stop it once binding visibly
   completes.
3. **Native module-load recon**: extend `tools/sslfull.js`'s existing
   `dlopen`/`android_dlopen_ext` hook (already there for re-scanning SSL
   exports) to also `send()` the name of any **newly loaded module** during
   the window — if binding pulls in a native lib not seen during normal
   operation (a secure-element/crypto helper, say), this is the cheapest way
   to notice it happened at all.
4. **adb logcat (continuous, whole session)**:
   `adb logcat -v threadtime > logcat_binding.txt &` started before un-binding,
   stopped after. Cheap, easy to grep afterward for `BluetoothGatt`/`aqara`/
   `lumi`-tagged lines — the Android Bluetooth stack's own logs sometimes name
   characteristic UUIDs/handles even when the app's own logging is stripped.
5. **UI timeline**: a screenshot (or `uiautomator dump` if `screencap` is
   unhealthy) **before every tap**, plus a `python3 -c "import time;
   print(int(time.time()*1000))"` timestamp immediately before/after each tap
   — keep this as a plain running log (`tap N at <ms>: <what it was>`). This
   is the cheapest, most reliable cross-reference and doesn't depend on any
   tool staying healthy.
6. **GATT table baseline diff**: before un-binding, use the library's own
   `aqara_ble` scanner/GATT client (or a generic BLE tool) to dump the lock's
   full service/characteristic list once, for comparison against whatever the
   binding wizard discovers/uses — flag anything not already in
   [devices/u200/gatt-map.md](devices/u200/gatt-map.md).

#### What to look for once everything's decoded (the actual hunt)

Cross-reference all fronts by timestamp into one timeline, then look
specifically for:
- Any **HTTP path not already documented** in `aqara_ble/kdf.py`'s `_PATH_*`
  constants (a `bind`/`create`/`provision`/`register`-shaped endpoint is the
  obvious candidate name, but don't assume — read what's actually there).
- Any **BLE characteristic write/notify** beyond the known auth channel
  (ff07/ff08, the ECDH pubkey exchange) and control channel (ff61/ff62) —
  especially one that carries a payload **larger** than a normal control frame
  (a key/seed blob would not fit in the usual few bytes).
- Any write that happens **right after** the BLE session/auth handshake
  completes but **before** normal control-channel traffic starts — that's the
  natural place to push something the lock needs to store permanently.
- Any HTTPS response body containing a field shaped like key material
  (unusually long hex/base64 string) that isn't `cloudPublicKey`/`sessionKey`/
  `nonce`/`verifyData`/`mac` (all already known and accounted for).

If none of the above turns up anything: that's a real, valuable negative
result too (same as the earlier native-crypto-hook negatives) — it would mean
either the seed is pre-provisioned at manufacture time with **zero** wire
transfer ever (harder — points to hardware-level RE as the only remaining
path), or it's smuggled inside a field already assumed "just session
material" that needs a second, closer look rather than a new one.

**Write up whatever happens** (positive or negative) in
[devices/u200/operations.md](devices/u200/operations.md)'s offline-password
section and [[full-feature-roadmap]] memory, same as every other capture this
project has done — a clean negative here is progress, not a wasted attempt.

**Then, separately**: once the binding wire protocol is decoded (regardless of
whether it settles the offline-password seed question), it's a real gap in
`aqara_ble` worth closing on its own — today the library has **no code path
at all** for adding a brand-new lock to an account, only for driving one
already bound. That's new protocol territory, not yet specified, so it goes
through the normal `/speckit-specify` → `plan` → `tasks` → `implement` flow
(Constitution III) **after** this capture, not before — there's nothing to
spec accurately until the wire shape is known.

## 4. Key findings index (see memory + operations.md for detail)

- **No cloud "privilege tier"** — all settings read over BLE from our own session; the
  earlier gap was two client bugs (reply correlation + ff61 write-prefix). The MITM
  proved the `/verify` cloud grant is byte-identical to the app's.
- **Read/write opcodes** (byte-confirmed): voice volume read `0xc3` / write `02 04 <lvl>`
  (Alto=01/Medio=02/Bajo=03); alarm volume read `0x84` / write `83 02 <val> 07`
  (Silencio=00/Normal=0x10); turn-assist read `0xe9` / write `e8 <0/1>`; door type
  `0xe0` (EU/UK/US = 01/02/03). Alert volume lives in the `0x1a` lock-setting blob
  byte 4 (1=Alto…4=Silencio).
- **Offline password ("Contraseña sin conexión")** — the 6-digit codes are
  **cloud-generated**, not computed locally by the app (confirmed live
  2026-08-30: the cloud's response contained the exact codes the app
  displayed). Implemented as `aqara_ble.fetch_offline_passwords()`/
  `fetch_offline_password_log()` (`GET /dev/bluetooth/lock/passwd` — no BLE
  needed at all). What's still open: whether the **lock itself** independently
  validates a keypad-typed code using its own locally-held copy of a per-lock
  seed (it must, per the patent US11120656B2's design, since the lock has no
  WAN) — see §3g for the prepared capture plan targeting the one moment that
  seed could reach the phone (device binding). "Contraseña programada" is a
  distinct, separate feature — a BLE temp-password command, capturable with
  the write-opcode loop (3d).
- **User / credential management** (add/del user, fingerprint, NFC) is deferred pending
  a strategy decision — not yet reverse-engineered.
