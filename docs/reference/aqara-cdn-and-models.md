# Aqara CDN, model catalog & voice-pack mechanism

Consolidated 2026-09-02. How Aqara's app resolves per-device assets (RN plugins
and voice packs) from public CDN URLs, plus the full model catalog. This is the
generic, device-independent knowledge — the U200 lock is just one row.

## 1. Voice-pack CDN URL anatomy

A language voice pack lives at a fully public, no-auth CDN URL. Example (U200
Français):

```
https://cdn.aqara.com/cdn/opencloud-product/mainland/product-voice/prd/aqara.matter.4447_10242/20240611190727/U200_FR_audio_burn.bin
```

| Segment | Value (example) | Meaning |
|---------|-----------------|---------|
| host | `cdn.aqara.com` | Public CDN, no auth (plain GET returns 200) |
| `/cdn/opencloud-product` | fixed | Open-cloud product-assets bucket |
| `mainland` | region | China-mainland storage bucket (NOT your account region — the asset lives centrally) |
| `product-voice` | fixed | Asset category: voice packs |
| `prd` | env | production (vs dev/staging) |
| `aqara.matter.4447_10242` | **model ID** | The device model (see catalog §3). `4447` = product line, `10242` = the U200 |
| `20240611190727` | **build timestamp** `YYYYMMDDHHMMSS` | The real "version" of the pack. A `version` bump in `voice/list` changes ONLY this segment |
| `U200_FR_audio_burn.bin` | **fileName** | `U200`=model prefix, `FR`=ISO language, `audio_burn`=audio image to flash |

**What varies vs what's constant** (for one device): only the **timestamp**
segment and the **ISO language** in the fileName change between languages/
versions. Everything else (`aqara.matter.4447_10242`, `product-voice/prd`,
`U200_<ISO>_audio_burn.bin`) is constant for the U200.

**Key limitation**: the timestamp is unique per file and NOT guessable. GET is
public, but you must already know the exact timestamp. A HEAD or a GET with the
wrong timestamp 404s (verified: `U200_ES` with FR's timestamp → 404; each with
its own timestamp → 200).

## 2. The `voice/list` cloud endpoint (source of the timestamps)

The timestamps come from a signed cloud call (no phone needed — pure cloud,
same `make_local_signer`/`compute_sign` scheme as everything else):

```
GET /app/dev/voice/list?did=<did>     → code=0, 12 rows
GET /app/dev/voice/list               → code=106 (parameterless)
GET /app/dev/voice/list?did=<did>&model=  → code=106 (model= form rejected)
```

Only the bare `did=` form works, and `did` must be a device you own. Each row:
`{ lang, langName, version, url, fileInfo }` where `fileInfo` is a JSON *string*
of `[{fileName, md5}]`. The full asset URL = `url + "/" + fileName`.

Tool: `tools/probe_voice_list.py`. Live sanitized dump:
`captures/voice_list.1.sanitized.json`.

### U200 language catalog (model `aqara.matter.4447_10242`, latest version each)

| lang | langName | fileName | latest md5 |
|------|----------|----------|------------|
| 1 | 中文 (CN) | `U200_CN_audio_burn.bin` | `bdd2a140256727cfc0d491ea238ff33d` (v4) |
| 10 | Русский (RU) | `U200_RU_audio_burn.bin` | `6ba36de1f261d7e215d299326e5211c4` (v2) |
| 12 | Español (ES) | `U200_ES_audio_burn.bin` | `4220816493dad2993f04a598465f008d` (v2) |
| 13 | Français (FR) | `U200_FR_audio_burn.bin` | `2fb6a8e43870816c3e5c3319afd903fd` (v1) |
| 17 | Polski (PL) | `U200_PL_audio_burn.bin` | `e696d086198251731bbb90e977f3cb98` (v4) |
| 2 | 中文 (old variant) | `U200_CN_audio_burn.bin` | `05e97a585e196458b3d147e409b8ffa6` (v2) |

FR = 1.66 MB, ES = 2.03 MB. We hold `captures/U200_FR_audio_burn.bin` (md5
verified). **No per-language BLE snoop needed — the catalog + CDN give every
language's exact bytes.** (Pushing them to the lock is a separate problem: the
OTA BLE framing / `0x90` token — see the U200 operations doc.)

## 3. The full model catalog (72 plugin bundles, 158 model IDs)

Source: `docs/reference/rn_bundle_config.json` (app-private, plain JSON, 72
device plugins). Cleaned into `docs/reference/aqara-model-catalog.json`
(`bundleId, label, models[], pluginVersion, pluginUrl, pluginType`).

**Every one of the 72 bundles carries a public CDN `.zip` plugin URL** — e.g.
`https://cdn.aqara.com/cdn/appadmin/mainland/rn/<hash>.zip`. So the RN plugin
for ANY listed device is directly downloadable right now, no auth. (This is the
analog of the voice-pack CDN, for plugin code instead of audio.)

### Matter lock family (`aqara.matter.4447_*`) — all share one plugin family

| model ID | Device |
|----------|--------|
| `4447_10241` | U300 (DA3) |
| `4447_10242` | **U200 (DA2)** ← ours |
| `4447_10245` | J200 DA2JP (set) |
| `4447_10247` | U200 Lite (DA2L) |
| `4447_10253` | J200 DA2 JP (single host) |
| `4447_10254/10255/10256` | U500 (DO4) |
| `4447_10314` | U600 (DA6UK) |
| `4447_16386` | Voice Companion H1 (语音伴侣) |

Because the sibling locks (U300/U500/U600/U200 Lite/J200) use the same
`aqara.matter` plugin, they very likely share the U200's OTA framing + `0x90`
mechanism — so cracking the U200 replay should generalize across the line.

### Other families present (count of model IDs)

`matter`:53, `models`:22 (lumi.models.*), `switch`:21, `lock`:12 (older
lumi/aqara locks: S100, D200i, N200, U100, A100, D100A, U50, N100, DZ1…),
`gateway`:9, `light`:7, `plug`:7, `airrtc`:6 (thermostats), `curtain`:6,
`sensor_occupy`:3, `group`:3, `sensor_gas`:2, plus single entries for
`motion`, `vibration`, `sensor_ht`, `sensor_smoke`, `airer`, `remote`,
`fitting`, `sensor_occupy`. Full detail in `aqara-model-catalog.json`.

## 4. What is / isn't pullable from the CDN

- ✅ **Model catalog** (all 158 IDs + labels): held.
- ✅ **RN plugin `.zip` for any of the 72 bundles**: public CDN URL in the
  catalog, downloadable now.
- ✅ **A voice `.bin` for a device you OWN**: `voice/list?did=<yourDid>` → URL.
- ❌ **A voice `.bin` for a device you DON'T own** (e.g. another lock model):
  needs that model's per-file timestamp, which only comes from *its* `voice/list`
  (needs a `did` of that device). Blind CDN timestamp enumeration is not viable.
