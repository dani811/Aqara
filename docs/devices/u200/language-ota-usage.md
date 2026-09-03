# U200 language OTA — usage, config & the keypad question (consolidated)

**Status: SOLVED (2026-09-03).** `aqara_ble` changes the lock's spoken language
end-to-end **from scratch, no phone app, no Frida** — it downloads the voice pack
from the CDN, authenticates, and drives the full Xiaomi-mible OTA (JSON handshake
+ `VOICE_OTA_INFO_SET` + XMODEM data stream) inside one authenticated session. A
full ~2 MB ES pack streamed 1984/1984 blocks, 0 NAKs, and the lock returned
`{"ID":0,"xfer_statu":"success","progress":100}`.

RE detail lives in [ota-0x90-investigation.md](ota-0x90-investigation.md); the
mechanism in [language-ota.md](language-ota.md). This file is the practical
"how to call it, what to configure, what it changes, and the keypad situation".

---

## 1. The example call — this is the valuable bit

### Python API (high level)

```python
from aqara_ble.client import U200Client
from aqara_ble.auth import CloudAuthManager
from aqara_ble.esphome_transport import EsphomeProxyTransport  # or Bleak/Bumble

blob = open("captures/U200_ES_audio_burn.bin", "rb").read()   # from the CDN

async with await U200Client.connect(
        auth=CloudAuthManager(...),                # cloud creds (see §2)
        transport=EsphomeProxyTransport(host, noise_psk=psk),
        device_id=AQARA_DEVICE_ID, mac=AQARA_LOCK_MAC, region="EU") as lock:
    result = await lock.push_voice_pack_ota(
        blob, "U200_ES_audio_burn.bin",            # CDN filename matters (lang code)
        progress=lambda done, total, acks: print(f"{done}/{total} acks={acks}"),
    )
    print(result.completed, result.final_status)   # True, {"xfer_statu":"success","progress":100}
```

`push_voice_pack_ota(blob, filename, *, arm=True, data_delay=0.006, window=3,
resume_from=0, skip_manifest=False, manifest_wait_s=90.0,
post_manifest_settle_s=4.0, keepalive_every_s=8.0, precomputed_cloud_pubkey=None,
progress=None) -> VoicePackResult`. Result fields: `completed: bool`,
`final_status: dict|None`, `frames_sent`, `duration_s`, `acks`, `stalled_at`.

### CLI tool

```bash
# offline sanity (no radio): show the control-frame shapes it will send
python3 tools/push_language_ota.py --bin captures/U200_ES_audio_burn.bin --dry-run

# live push over the ESPHome proxy (the transport that completes reliably)
python3 tools/push_language_ota.py --bin captures/U200_ES_audio_burn.bin --transport esphome
```

Get any language's `.bin` from the CDN with no auth (see
[../../reference/aqara-cdn-and-models.md](../../reference/aqara-cdn-and-models.md)):
`voice/list?did=<did>` → per-language `url + fileName` (e.g.
`U200_FR_audio_burn.bin`, `U200_ES_audio_burn.bin`).

## 2. Configuration (`.env`)

Cloud auth (all required): `AQARA_ACCOUNT`, `AQARA_PASSWORD`, `AQARA_APPID`,
`AQARA_APPKEY`, `AQARA_CLIENT_ID`, `AQARA_PHONE_ID`, `AQARA_DEVICE_ID`,
`AQARA_REGION` (EU). Optional cached: `AQARA_TOKEN`, `AQARA_USER_ID`.

Device / transport: `AQARA_LOCK_MAC`. Then ONE transport:
- **ESPHome proxy (recommended — the one that completes):**
  `AQARA_ESPHOME_HOST` + `AQARA_ESPHOME_NOISE_PSK`. Uses the proxy's own ACL
  flow control → clean data AND stable link.
- **ESP32-S3 / bumble:** `AQARA_ESP32_PORT` (`serial:/dev/cu.usbmodemNNNN,115200`)
  — stable link but corrupts a fraction of WRITE_WITHOUT_RESPONSE packets under
  load (transport bug, not protocol).
- **Mac native (bleak):** clean data (with the `_await_wor_ready` CoreBluetooth
  flow-control fix) but the macOS link can drop mid-transfer.

`SSL_CERT_FILE` may be needed for the cloud TLS on some setups.

## 3. ⭐ The keypad question ("sin el teclado vale millones")

**The keypad gate applies ONCE, only to authorise the OTA start — NOT during the
stream.** A single presence event carries the whole ~10-minute transfer to 100 %;
presence does NOT need refreshing per block. (The old "keypad every ~15 s or it
aborts" was a MISDIAGNOSIS — the real cause of the early abort was the missing
`VOICE_OTA_INFO_SET` command; fixed.)

**And that one press is already remote — no human at the door.** The "keypad
touch" is delivered by a **Tuya Zigbee fingerbot** (`switch.pulsador`, driven via
Home Assistant) physically mounted on the keypad. So the flow is already fully
remote/autonomous: HA fires the fingerbot once → the lock wakes/advertises and
authorises the OTA → the library streams the rest with no further presence.

**What "without the keypad" would mean, precisely, and where it stands:** the
wake authorises BLE + advertises the lock; it is a lock-side security/battery
design. We have NOT found a way to make the U200 connectable/authorise an OTA
with zero presence event — so today the minimum is that ONE remote fingerbot
press. Eliminating even that is an open research question (the lock requires
presence to authorise BLE ops). Functionally, though, the "worth millions"
scenario — change the lock's language remotely with nobody touching it — **works
now** via the fingerbot + library. Caveats for a hands-off run: fingerbot
presence is flaky (Zigbee LQI ~51, connect 7–20 s), so the tool re-sends the
start+manifest for up to `manifest_wait_s` to land on whatever moment the
presence pulse arrives.

## 4. Settings / state we changed on the lock (to restore)

- **Spoken language:** left on **Français** (a FR OTA completed on the gadget;
  an ES from-scratch push also ran). Restore to **Español** when done — a
  from-scratch ES push via §1, or the app quick-pick.
- **Test values set live while building HA entities (not restored):**
  `select.alert_volume` = medium, `select.alarm_volume` = normal,
  `number.alert_delay` = 10 s. Reset to your preferred values if they matter.
- **HA `aqara_u200` integration:** disabled (to free the single BLE slot). Re-enable it.
- **Phone:** was left on the **gadget-repacked** app (logged in). Reinstall the
  Play-Store build if you want the clean app back.
- **Fingerbot:** `number.pulsador_upper` = 0 (so it actually reaches the keypad).

## 5. What changed in the code (the mechanism, in one place)

- The OTA crypto = **standard AES-CCM under the cloud session key+nonce** (proven
  by a BouncyCastle `CCMBlockCipher` hook — one AEADParameters for the whole
  session, 4-byte tag, empty AAD; Python `AESCCM(key, tag_length=4)` reproduces it
  byte-exact). No secret `expandedIv`; same CCM `control_codec.py` already runs.
- Protocol = JSON short-packs over that CCM on ff61/ff62, plus **plaintext** bulk
  `.bin` blocks on ff91 (`0x11` frames), XMODEM-framed (`02 seq (ff-seq)` marker
  + CRC-16/XMODEM), last block **padded to 1024 B with `0x1a`** before CRC.
- The two final unlocks: (1) `VOICE_OTA_INFO_SET` must be written to ff61 with a
  3-byte cleartext header **`3f a5 ff`** before the CCM payload (not our normal
  `0x01` prefix) — else the lock caps at 16 blocks; (2) the `0x1a` last-block
  padding — else the lock validates the image and returns `abort` at 100 %.
- Code: `aqara_ble/ota.py` (`run_voice_pack_ota`, ack-driven flow control +
  retransmit-on-`1115`), `aqara_ble/ota_language.py` (frame/crc/crypto builders),
  `aqara_ble/client.py::push_voice_pack_ota`, `tools/push_language_ota.py`. Tests:
  `tests/test_ota_language.py` (incl. the real captured CCM vectors).
