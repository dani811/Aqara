# U200 language OTA — the WORKING recipe (byte-level, reproducible)

**Layer:** device-specific (U200). **Status: ✅ WORKS end-to-end** — `run_voice_pack_ota`
took the full ES pack to `{"ID":0,"xfer_statu":"success","progress":100}` live over an
ESPHome proxy (1984/1984 blocks, 0 NAKs). This is the concrete, squeeze-tested procedure —
not prose. For the *why* / dead-ends, see [ota-0x90-investigation.md](ota-0x90-investigation.md).

---

## 1. The exact command that worked

```bash
# .env must define: AQARA_ACCOUNT, AQARA_PASSWORD (or AQARA_TOKEN), AQARA_REGION=EU,
#   AQARA_DEVICE_ID, AQARA_LOCK_MAC=CA:46:83:E1:13:0E,
#   AQARA_ESPHOME_HOST=192.168.68.234, AQARA_ESPHOME_NOISE_PSK=<proxy noise psk>
.venv/bin/python tools/push_language_ota.py \
  --bin captures/U200_ES_audio_burn.bin \
  --transport esphome --host 192.168.68.234 \
  --delay 0.033 --window 1 --attempts 1 --timeout 90
```

Runs ~10 min (1984 blocks at ~16 frame/s). Ends with:
`[result] 🎯 OTA SUCCESS: {'ID': 0, 'xfer_statu': 'success', 'progress': 100}`.

**Fingerbot (`switch.pulsador`, presence gate — see §6):** press once so the proxy sees the
advert and connects; press again ~11 s later for the manifest handshake. That's it — a
**single** manifest-phase press carries the whole transfer (presence is NOT periodic).

**Effective params passed to `push_voice_pack_ota`** (from `tools/push_language_ota.py`):
`data_delay=0.033, window=1, manifest_wait_s=120.0, post_manifest_settle_s=0.0,
keepalive_every_s=2.0, precomputed_cloud_pubkey=<pre-fetched>`. Cloud pubkey is fetched
BEFORE any BLE (`cloud_get_public_key`) so on-lock auth is instant after connect.

---

## 2. Transport that makes it survive (ESPHome proxy)

`aqara_ble/esphome_transport.py` — drives bleak-esphome's `ESPHomeClient` over the proxy.
Three settings are load-bearing for a ~2 MB WRITE_WITHOUT_RESPONSE stream:

| Setting | Value | Why |
|---|---|---|
| Connection interval | **7.5–15 ms** (`min_interval=12, max_interval=12`) | The ESP32 gattc TX queue drains ~1 WoR write per interval. At the idle 45 ms interval it backs up and silently drops a fragment ~80 writes in → block-CRC NAK → abort. The app runs the data phase at exactly these fast intervals. |
| Scanning | **PASSIVE** during the transfer (restored to ACTIVE on disconnect) | ACTIVE scan requests time-share the single radio and corrupt blocks mid-stream. |
| Supervision timeout | `timeout=500` (5 s) | A brief radio hiccup mustn't drop the link. |

`bluetooth_device_set_connection_params` is called with `mac_to_int(mac)` (a NameError there
used to silently no-op the whole thing). ff91 is **WRITE_WITHOUT_RESPONSE only** — write-with-
response is rejected (`Write not permitted`), so pacing is the only WoR flow control available.

---

## 3. The full on-wire sequence (in order, byte-level — ES example)

All control frames are AES-CCM (tag_length=4, empty AAD) under the cloud-derived session
key+nonce. The `0x90` OTA frames go to **ff91**; short control to **ff61**; data to **ff91**;
the lock acks on **ff92**.

| # | Frame (plaintext / structure) | Channel | Lock reply (ff92/ff62) |
|---|---|---|---|
| 1 | `0x90 ‖ CCM(04 {"ID":255} 00)` — **start** | ff91 | `{"statu":0,"ID":255}` |
| 2 | `0x90 ‖ CCM(03 {"MCU_role":"receiver","file_info":{"name":"U200_ES_audio_burn.bin","size":2031272,"crc32":"4a6f76a8"}} 00)` — **manifest** | ff91 | `{"statu":0,"ID":1}` (needs the keypad touch) |
| 3 | **`3f a5 ff` ‖ CCM(`01 21 <md5-hex:32> 00 02 09 45 73 70 61 c3 b1 6f 6c 00`)** — **VOICE_OTA_INFO_SET** ⚠ | **ff61** | `a6…` (accepted; NOT a `statu:0xFFFFFFFF` reject) |
| 4 | init/file-info: `11 01 00 ff` ‖ `<name 0x00 decimal-size 0x20 padded to 128>` ‖ CRC16 (134 B) | ff91 | `1106` |
| 5 | **1984 data blocks**, each `11` ‖ `[02 seq (0xff-seq)]` ‖ `block[1024]` ‖ CRC16-XMODEM, sliced into ≤243 B `0x11`-prefixed writes (4×244 B + 1×58 B) | ff91 | one **`1106`** per block |
| 6 | `11 04` — **end-of-data marker** (2 B) | ff91 | `1106` |
| 7 | `11 01 00 ff` ‖ `<128 × 0x00>` ‖ CRC16 — **zero activation frame** (134 B), **×2** | ff91 | `1106` |
| 8 | `0x90 ‖ CCM(04 {"ID":255} 00)` — **commit** (identical to the start frame), **×2** | ff91 | `{"statu":0,"ID":255}` |
| — | **the lock validates the whole image and pushes** | ff92 | **`{"ID":0,"xfer_statu":"success","progress":100}`** |

### ⚠ The two things that are easy to get wrong

- **Frame 3 (the info command).** Its **plaintext** is `01 21 <md5(bin) as 32-char lowercase
  hex ASCII> 00 02 <len(lang)+1> <lang-utf8> 00` (= the file MD5 + the language display name,
  as a 2-field TLV). It must be written to **ff61** as **`3f a5 ff` ‖ CCM(plaintext)** — a
  3-byte cleartext header where **`a5` = the VOICE_OTA_INFO_SET opcode** — NOT our normal
  single `0x01` control prefix, and NOT a `0x90` OTA frame. With the wrong framing the lock
  reads it as a version GET and **caps the transfer at exactly 16 blocks**. In code:
  `client.write_gatt_char(CONTROL_WRITE_UUID, b"\x3f\xa5\xff" + encrypt_control_payload(...))`.
- **Frame 5, the LAST block.** The final partial block MUST be **padded up to a full 1024 B
  with `0x1a`** before its CRC16. The lock validates the whole received image against the
  declared MD5/CRC; a short last block passes its own per-block CRC (gets a `1106`) but fails
  the image check → **`abort` at progress 100**, not `success`. `iter_data_frames` pads.

### ES concrete values (from `captures/U200_ES_audio_burn.bin`)

```
size            2031272
manifest crc32  4a6f76a8              (zlib.crc32, lowercase hex, no 0x)
info md5        4220816493dad2993f04a598465f008d
language        "Español"            (utf-8: 45 73 70 61 c3 b1 6f 6c, 8 bytes)
info plaintext  0121 3432323038313634393364616432393933663034613539383436356630303864 00 02 09 45737061c3b16f6c 00   (46 B)
block 0         11 02 01 fe 4c0000004a00000001…              (0x11 prefix, marker 02 seq=01 ~seq=fe)
last block tail …1a1a1a1a1a1a 6989     (0x1a padding + CRC16 6989)
1984 data blocks total
```

---

## 4. Reading the ff92 replies (don't miscount!)

| Code (2-byte plaintext on ff92) | Meaning |
|---|---|
| `1106` | **per-block ACK** — one per accepted block (1984 of them for ES). The ONLY thing to count as progress. |
| `1143` | the lock's reply to OUR `2f012f` keepalive — **NOT** a block ack, NOT a marker. Arrives at the keepalive cadence. |
| `1115` | NAK (bad block). Healthy transfer = **zero**. |
| `90xx` / JSON | `0x90` control acks (start/manifest/commit) and the final `{"…xfer_statu":…}`. |

Gating is **absolute**: block `gi` is confirmed when the running `1106` count reaches
`base_ack + gi + 1` (a relative "did the count rise since I sent this block" test breaks under
ack pipelining and resends a block forever — that was a real bug). The old "reached
1016/2299 blocks" numbers were miscounts that counted `1143`/`1115` as block acks.

---

## 5. Auth / session (prerequisite, already solved elsewhere)

The transfer runs INSIDE a fully authenticated aqara session: ECDH over ff07/ff08, session
key+nonce derived with the cloud public key (`cloud_get_public_key`, phone-free, pre-fetched),
CCCDs enabled on ff62/ff64/ff92/ff08. See `aqara_ble/session.py::run_authenticated_lock_operation`
and [../../reference/](../../reference/). The `0x90` token is computed under our OWN session
key — it was never session-bound to the app.

---

## 6. The keypad presence gate (what still needs a physical touch)

- Advertising, connection, and actuation (`LOCK`/`UNLOCK`/status) need **NO** keypad.
- The **manifest handshake** (a settings-class op) needs the lock to be "present" = a keypad
  touch within ~15 s. Drive `switch.pulsador` (Zigbee fingerbot, `number.pulsador_upper=0` for
  full stroke — it does register on the capacitive keypad). **One** press for the manifest
  carries the whole ~10-min transfer; presence is NOT refreshed during the stream.
- The touch emits **nothing on BLE** (ff82/ff62/ff64/ff92 all silent when pressed) — it flips
  an internal lock flag, so it can't be injected over BLE. The fingerbot IS the replication.

---

## 7. Failure → fix quick table

| Symptom | Cause | Fix |
|---|---|---|
| Manifest never acks (`ID:1` never comes) | no keypad presence | press `switch.pulsador` during `manifest_wait_s` |
| Streams then aborts at **exactly ~16 blocks** | info command missing / wrong framing | send frame 3 as `3f a5 ff ‖ CCM(...)` on ff61 |
| All 1984 blocks ack but `abort` at progress 100 | last block not padded | pad final block to 1024 with `0x1a` (frame 5) |
| NAK storm ~80 writes in, any transport | WoR overrun | fast 15 ms interval + PASSIVE scan (§2) |
| Stuck resending one block, no NAK | relative ack gating + pipelining | absolute gating `blockack ≥ base+gi+1` |
| `Write not permitted` on ff91 | tried write-with-response | ff91 is WoR-only; pace instead |
