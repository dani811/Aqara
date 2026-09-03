# U200 — Language voice-pack OTA (consolidated investigation)

**Layer:** device-specific (U200). **Status (2026-09-03): ✅ SOLVED — the library
completes the OTA to 100% from scratch, no app.** `run_voice_pack_ota` streamed the
full ~2 MB ES pack over the ESPHome proxy (1984/1984 blocks, 0 NAKs) and the lock
returned `{"ID":0,"xfer_statu":"success","progress":100}` — Spanish applied. The
`0x90` token was never session-bound (it's computed under our own session key); the
two real blockers, both found by decoding the app's OWN captures, were:

1. **The VOICE_OTA_INFO_SET command + its framing.** After the manifest the app
   writes to **ff61** a frame `3f a5 ff || CCM(01 21 <md5(bin) hex-ascii:32> 00 02
   <len(lang)+1> <lang-utf8> 00)` — a **3-byte cleartext header `3f a5 ff`** (0xa5 =
   SET opcode) before the CCM payload, NOT our usual single `0x01` control prefix.
   Without it the lock capped the transfer at exactly **16 blocks** (it read the
   `0x01`-prefixed frame as a version GET). This is the file MD5 (as an ASCII hex
   string) + the language display name.
2. **Last-block padding.** The lock validates the whole received image against the
   declared MD5/CRC and reports `abort` (not `success`) on mismatch. The final
   partial block must be **padded up to 1024 bytes with `0x1a`** before its CRC16
   (verified byte-exact vs the app, CRC `2df0`). A short final block passes its own
   per-block CRC (0x1106-acked) but fails the image check.

**→ Concrete, byte-level, reproducible procedure: [language-ota-recipe.md](language-ota-recipe.md)**
(the exact command, the full on-wire frame sequence with ES values, the ff92 codes, the
transport tuning, the keypad recipe, and a symptom→fix table). Full blow-by-blow of how it
was cracked: [ota-0x90-investigation.md](ota-0x90-investigation.md) (2026-09-03 SOLVED). Goal
met: switch the lock's spoken-prompt language autonomously from `aqara_ble` — the user's
"réplica exacta de la app" ask.

## 1. Where the voice pack comes from (SOLVED — cloud + public CDN)

No per-language BLE snoop is needed. The cloud endpoint
`GET /app/dev/voice/list?did=<did>` (signed, phone-free) returns all languages
with a public CDN URL + md5. Full anatomy, the 6-language catalog, and the whole
72-plugin/158-model device catalog: **[../../reference/aqara-cdn-and-models.md](../../reference/aqara-cdn-and-models.md)**.
We hold the Français pack verbatim (`captures/U200_FR_audio_burn.bin`, md5 OK).

## 2. The BLE transfer anatomy (DECODED)

Captured end-to-end via btsnoop on the clean Play-Store app
(`captures/ota/btsnoop_end.log`) — a full Français download that ran to 100%.

- **Channel:** AUX service `ff90`, characteristic **`ff91`** (value handle
  `0x003c`), WRITE_WITHOUT_RESPONSE (ATT opcode 0x52). Plaintext — NOT AES-CCM.
  The lock **block-acks on `ff92`** (value handle `0x003e`, NOTIFY).
- **8138 frames**, in order: opening `0x90` token (17 B) + a second `0x90`
  (110 B) → init frame (`11 0100ff <filename> 00 <decimal size>`) → the `.bin`
  streamed verbatim, wrapped per ~1024-B block with a `02 <seq> <0xff-seq>`
  marker + an undecoded 2-byte field → activation tail (`11 ff…`→`11 00…`→
  `11 1a…`×2→`11 04`→two zeroed 134-B frames) → closing `0x90` token (17 B),
  **identical to the opening one**: `900d55d9bea3755376155b749ca0066d93`.
- The whole transfer runs **inside a fully authenticated aqara session** (see §3);
  it is NOT a standalone plaintext blast.

Tools: `tools/decode_ota_framing.py` (framing), `tools/replay_ota.py`
(extract + replay, see §5).

## 3. Channel map — COMPLETE, verified live (no missing channel)

Authoritative live discovery (`tools/dump_gatt.py`, 2026-09-02) matches
[gatt-map.md](gatt-map.md). Every write and notification in the real transfer,
counted from the capture, lands on a channel the library already knows and uses:

| Direction | Channel | Handle | Count in transfer | Library uses it? |
| --- | --- | --- | --- | --- |
| write | FF07 auth | 0x0020 | 28 | yes (auth) |
| notify | FF08 auth | 0x0022 | 24 | yes (subscribed) |
| write | FF61 control | 0x0031 | 328 | yes (control) |
| notify | FF62 control | 0x0033 | 519 | yes (subscribed) |
| notify | FF64 report | 0x0038 | 0 | yes (subscribed) |
| **write** | **FF91 OTA** | **0x003c** | **8138** | yes (stream) |
| **notify** | **FF92 OTA acks** | **0x003e** | **1637** | yes (subscribed) |

The app subscribes (CCCD 0100) to exactly FF08/FF62/FF64/FF92 — identical to the
library's `PRE_AUTH_NOTIFY_ORDER`. The OTA acks arrive **only on FF92**, which we
monitor. Unused services (FF70: FF71/FF72; FF80: FF81/FF82; FF63) get **zero**
writes/notifications during the OTA — correctly ignored. **There is no unknown
channel and no mis-mapped characteristic.**

## 4. The control channel is decodable (keystream reuse)

The AES-CCM control channel (FF61/FF62) uses a **static per-connection nonce**,
so its CTR keystream is identical for every frame in a connection. Anchor on the
most-common opcode = `HEART_PCK` (0x2f) → `ks0`, then
`opcode = ciphertext_byte0 XOR ks0`; recover more keystream bytes from the
keepalive's known plaintext `2f012f`. This decodes the whole channel without the
session key. (Method proven in the `tools/replay_ota.py` analysis; per-connection
segmentation via the 4× CCCD-write cluster.)

### The pre-OTA control handshake (decrypted from the successful capture)

Right before the ff91 stream, the app issues these control reads
(`<op> <family> <op>` shape) — NOT a metadata SET:

| Δt vs stream | plaintext | opcode |
| --- | --- | --- |
| −7304 ms | `1a 01 1a` | SYNC_OTA_URL |
| −7284 ms | `68 01 68` | READ_LOCK_LANGUAGE |
| −7259 ms | `a6 03 a6` | VOICE_OTA_INFO_GET (family 0x03) |

(`VOICE_OTA_INFO_SET` 0xa5 and `WIRELESS_OTA_STATUS` 0x5b appear only in much
earlier connections, never before this transfer.) These are built as
`aqara_ble.ota.ARMING_READS` and issued before the stream.

## 5. Live attempts and results

Reusable infra built this session (all additive, 97 tests green, uncommitted on
`docs/042-…`):
- `session.py`: optional `post_auth` hook + `PostAuthContext`
  (`write_aux`/`send_keepalive`/`send_control`/`read_control`).
- `aqara_ble/ota.py`: `stream_language_ota()` (+ `ARMING_READS`), `OtaResult`.
- `client.py`: `U200Client.push_language_ota(frames, arm=…)`.
- `tools/replay_ota.py`: authenticated stream by default; `--bare`, `--no-arm`.

| # | Setup | Result |
| --- | --- | --- |
| 1–3 | Bare ff91 blast, no auth | ff92 silent; no change |
| 4 | Full authenticated session (auth+CCCD+control keepalives) + ff91 stream | ff92 silent; no change |
| 5 | Authenticated + the §4 control arming reads | **Lock REPLIED to all 3 reads** (SYNC_OTA_URL → `1a000001010a010102000002001c77`, READ_LOCK_LANGUAGE → `680002010000106c`, VOICE_OTA_INFO_GET → `a6000005de`) — yet **ff92 still 0 acks, no change** |

## 6. Verdict — the `0x90` commit token is session-bound

We reproduced **every** layer the app does — auth, CCCD on all four notify
channels, control keepalives, and the exact pre-OTA control handshake with valid
lock responses — and the lock still refuses to engage the ff91 stream (zero ff92
acks). The **only** element not reproduced is the **value** of the 17-byte `0x90`
token, replayed verbatim from a different app-process capture.

Known `0x90` properties (from prior sessions): per-app-process (identical across
transfers in one process, changes after a force-stop), opening == closing within
a transfer. Conclusion: it is **validated live / bound to the session or app
process**; a stale captured value is rejected and the lock silently discards the
stream. This matches the pre-registered "reject at 0x90 → session-bound" outcome.

## 7. What's needed next — a native hook on `0x90`

The only remaining path to autonomous language OTA is to learn **how the app
mints `0x90`**, then compute it ourselves inside the authenticated session that
already works. Concretely:

- **Native Frida hook** (SecNeo-safe; Java hooks are dead but native hooks work —
  see [capture-infrastructure](../../../tools/) / `tools/frida_attach.py` +
  `capture_all_native.js`) on the native function that produces the 17-byte
  `90 0d …` write to `ff91` at transfer start.
- Goal: identify the token's source — derived from the ECDH `sessionKey`/`nonce`/
  `verifyData` (then we can compute it), or fetched from a cloud call (then we
  add that call), or an internal counter.
- Capture ≥2 `(session material, 0x90)` pairs to confirm the derivation.

Once `0x90` is understood, `push_language_ota()` gains a token-builder and the
whole flow works — and, since the sibling Matter locks (U300/U500/U600/U200 Lite)
share the `aqara.matter` plugin, it should generalize across the line.

## Loose ends (device state)

Lock left on **Español** (unchanged by any attempt). HA `aqara_u200` integration
**disabled** to free the BLE slot — **re-enable it** when done.
