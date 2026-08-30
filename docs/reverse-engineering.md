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
  lists every model→plugin-URL mapping needs one Frida session (native file read, see
  §3g); after that, **any model's real plugin source is one `curl` + decompile away,
  no device needed.** See [reference/rn-device-plugins.md](reference/rn-device-plugins.md)
  for the full catalog and the U200's own entry.
- HTTP stack: okhttp3 + retrofit2 + Cronet, HTTP/2. Cloud request headers ride HPACK —
  decode offline with `scratchpad/sslfull.js` (native SSL full-hex dump) +
  `scratchpad/decode_h2.py` (fixes SSL* pointer reuse + double-hooked SSL_write).

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

## 4. Key findings index (see memory + operations.md for detail)

- **No cloud "privilege tier"** — all settings read over BLE from our own session; the
  earlier gap was two client bugs (reply correlation + ff61 write-prefix). The MITM
  proved the `/verify` cloud grant is byte-identical to the app's.
- **Read/write opcodes** (byte-confirmed): voice volume read `0xc3` / write `02 04 <lvl>`
  (Alto=01/Medio=02/Bajo=03); alarm volume read `0x84` / write `83 02 <val> 07`
  (Silencio=00/Normal=0x10); turn-assist read `0xe9` / write `e8 <0/1>`; door type
  `0xe0` (EU/UK/US = 01/02/03). Alert volume lives in the `0x1a` lock-setting blob
  byte 4 (1=Alto…4=Silencio).
- **Offline password ("Contraseña sin conexión")** = a TOTP-like hourly code
  `truncate6(Hash(private_key_seed, hour_period))` (Aqara patent US11120656B2). The
  per-lock seed is factory-set, stored in lock + cloud, and handed to the app on
  binding. To implement: obtain the seed (app internal data / a cloud endpoint) and pin
  the exact hash+truncation (RN plugin). "Contraseña programada" is instead a BLE
  temp-password command — capturable with the write-opcode loop (3d).
- **User / credential management** (add/del user, fingerprint, NFC) is deferred pending
  a strategy decision — not yet reverse-engineered.
