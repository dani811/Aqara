# Native libraries of the Aqara app — hooking reference

Grounded map of the app's loaded `.so` files and what each is good for, so a
future session doesn't re-enumerate from scratch. Confirmed live 2026-09-02
(Frida 17.2.12, `Process.enumerateModules()` + `enumerateExports()` on the
running `com.lumiunited.aqarahome.play` gadget build).

**Golden rule (see [[frida-repack-strategy]] memory):** native
`Interceptor.attach` on a `.so` export never touches the ART/Java bridge and is
**safe under SecNeo**. Passive `Java.perform`/`Java.use` also survive. What
crashes SecNeo is an **active Java method override** (`.implementation =`) —
avoid those. So everything below is hooked natively, at the `.so` boundary,
never via a Java method override.

## The libraries that matter

| `.so` | Size | Role | Hook for |
| --- | --- | --- | --- |
| `libssl.so` | 610 KB | OkHttp/conscrypt TLS | `SSL_read`/`SSL_write` (exported) → HTTPS plaintext. **This is the stack all our target API traffic uses.** |
| `libjavacrypto.so` | 274 KB | conscrypt JNI TLS | also exports `SSL_read`/`SSL_write` — same buffers, double-logged; `decode_h2.py` dedups. |
| `libcrypto_httpengine.so` | 893 KB | **Cronet (Chromium net) TLS — a SECOND stack** | **NOT hookable by symbol** — stripped, exports/symbols have no `SSL_read`/`SSL_write` (confirmed 2026-09-02). Carries CDN/webview/analytics, NOT our OkHttp API calls. Only revisit (offset/pattern hook) if a needed request is ever missing from the OkHttp capture. |
| `liblumidevsdk.so` | 1.59 MB | **the app's crypto/sign core** | see its export table below — `getSignHead` (the cloud Sign!), `aes*`/`get*cryptedData` (cloud + BLE payload crypto). |
| `libcrypto.so` (×2) | 1.5–1.8 MB | BoringSSL primitives | HMAC/`EVP_Digest*` fallback for any crypto not in lumidevsdk. |
| `libhermes.so` / `libjsi.so` / `libreactnative.so` / `libhermestooling.so` | — | React Native / Hermes runtime | RN bundle runs here. `libhermes.so` is a **stripped release build** — no `evaluateJavaScript`/interpreter-dispatch export, so live RN-bytecode hooking is NOT viable. Use the decompiled bundle + `rn_bundle_config.json` instead. |
| `libDexHelper.so` (1.2 MB) / `libdexjni.so` (10.9 MB) / `libdexfile.so` | — | SecNeo/DexHelper protection | the thing that crashes on active Java hooks. Not a hook target; the reason for the native-only rule. |
| `libaqara_ed.so` | — | app-private "encrypt/decrypt" | **not loaded** during cloud/offline-password use. Watch `modules.log`'s dlopen trace — if it loads when BLE connects, it's a BLE-crypto lib worth enumerating. |

## `liblumidevsdk.so` exports (12, confirmed 2026-09-02)

```
Java_com_lumi_lumidevsdk_LumiDevSDK_getSignHead      # THE cloud Sign (JNI)
Java_com_lumi_lumidevsdk_LumiDevSDK_aesEncryptedContent   # AES encrypt (JNI)
Java_com_lumi_lumidevsdk_LumiDevSDK_aesDecryptedContent   # AES decrypt (JNI)
Java_com_lumi_lumidevsdk_LumiDevSDK_getEncryptedInfo
Java_com_lumi_lumidevsdk_LumiDevSDK_getDecryptedInfo
Java_com_lumi_lumidevsdk_LumiDevSDK_getCert
Java_com_lumi_lumidevsdk_LumiDevSDK_getVersion
Java_com_lumi_lumidevsdk_LumiDevSDK_getTimeZone
aesEncryptedContent      # bare C internals (raw char*,len — easier to read
aesDecryptedContent      #   than the JNI wrappers, which need JNIEnv calls)
getEncryptedData
getDecryptedData
```

- `getSignHead` is the native impl already reverse-engineered into
  `aqara_ble.cloud_crypto.compute_sign` (MD5 of the documented preimage).
  Hooking it live captures the app's REAL Sign inputs — the direct attack on
  the `code=106 "Invalid sign"` mystery (track B, see
  [[cloud-signing-broken-2026-09-01]]).
- The bare `getEncryptedData`/`getDecryptedData`/`aes*Content` (no `Java_`
  prefix) are the internal C functions the JNI wrappers call. Prefer hooking
  these for payload crypto — they take plain C pointers, not `jbyteArray`s.
  **Their exact C signatures (arg count/types) are not yet known** — reverse
  them from live calls before reading buffers (getSignHead fires on every
  cloud request; aes fires on BLE). This is C-stage-2 of the capture infra,
  deliberately not built blind.

## Capture infrastructure (track C)

- **C-stage-1 (built):** `tools/capture_all_native.js` — native SSL across all
  SSL-exporting modules → `https.log`, plus a `dlopen` trace → `modules.log`.
  Attach with `tools/frida_attach.py`; decode `https.log` with
  `tools/decode_h2.py`. Per-category files land in the app's
  `files/cap/` dir on-device; pull to the git-ignored local `captures/` tree.
- **C-stage-2 (pending, built when B/BLE run):** add `liblumidevsdk.so`
  crypto/sign hooks once their signatures are reversed from live calls.
- **BLE** is a separate pipeline: `adb bugreport` → `btsnoop_hci.log` →
  `tools/parse_att_handle.py` + the per-connection AES-CCM keystream decode
  (see `docs/devices/u200/operations.md`). But the plaintext BLE frames AND the
  session key may also be catchable natively via `liblumidevsdk.so`'s `aes*`
  functions (C-stage-2) — untested, but the promising path toward a fully
  offline/local BLE (no cloud KDF).

## Focused SSL variants (already in `tools/`)

- `sslfull_frida17.js` — full-hex SSL dump, all modules (what C-stage-1's HTTPS
  part is based on). Heavy: stalls TLS-heavy screens (the WebView **login**
  screen especially) — see the freeze note in `tools/frida-setup.md`.
- `sslfilter_frida17.js` — same but only dumps buffers matching a path filter
  (few writes → won't stall the login). Note: filtering breaks HPACK dynamic-
  table decode (it's stateful across the whole connection), so use the full
  variant when you need decoded request **headers**, the filtered one when you
  only need to confirm a body/path or to avoid a stall.
