# Feature Specification: Cloud session-grant MITM (privilege capture)

**Feature Branch**: `feat/037-cloud-session-mitm`

**Created**: 2026-08-27

**Status**: ✅ RESOLVED 2026-08-27 — the MITM proved (HPACK-decoded `/verify`) that
the cloud session-grant is **identical** app-vs-library (same body, deviceId,
headers, and JWT scope `tokenSource:UC/loginSource:USER_NEW`). There was **no cloud
privilege**: the gated-read failure was two client bugs in `aqara_ble` (reply
correlation + ff61 write-prefix), now fixed — all settings read over BLE from our
own session, live 6/6 (commit `8b24731`). See `settings-protocol.md` and spec 036.

**Original status**: Planned (blocked-hard research; open only when ready to invest)

**Input**: Capture the official Aqara app's HTTPS traffic to the Aqara cloud during
a lock session, and diff the session-grant (`get_public_key` + `verify`) request +
response against our `aqara_ble.kdf`, to find why the cloud mints a **privileged**
session for the app but not for our library (see `specs/036-privilege-elevation`).

## Background (why this phase exists)

Spec 036 proved the U200's sensitive-settings tier (volume/language/finger/log/…)
is granted **cloud-side at session mint time** and is invisible on the BLE link:
the app is privileged from its first post-auth command, and every BLE-observable
(auth format, 8-byte verifyData, RPA address, unbonded link) is identical to ours.
So the only place the privilege can differ is the **cloud HTTP session-grant**. Our
`kdf` reimplementation authenticates fine (free reads work) but evidently obtains
non-privileged session material.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Intercept the app↔Aqara-cloud HTTPS for one full lock session (login,
  `get_public_key`, `verify`/session-material). A phone-level MITM proxy
  (mitmproxy/Charles) with a trusted CA.
- **FR-002**: Defeat/áwork around the app's certificate pinning. The app is
  **SecNeo-hardened** (libDexHelper) so standard user-CA trust likely fails; options
  (in rising effort): system-CA on a rooted/emulated device (blocked — no root),
  `mitmproxy` + Android network-security-config on a debuggable rebuild (blocked —
  SecNeo), Frida SSL-unpinning (blocked — SecNeo anti-Frida), or a hardware/network
  MITM with a pinning-bypass. This is the crux risk and may prove infeasible.
- **FR-003**: Diff the captured requests + responses field-by-field against what
  `aqara_ble/kdf.py` sends/receives (headers, body params, signed fields, and any
  role/scope/device-capability field in the response).
- **FR-004**: If a privilege-bearing field is found, replicate it in `kdf` and
  verify a gated read (volume `0xc3`) returns a real value from our session.
- **FR-005**: No lock actuation (`0x74`) at any point; capture is passive.

## Attempt log — 2026-08-27 (walls confirmed empirically)

First MITM attempt with mitmproxy 12.2.0 (own device/account):

- **Regular HTTP proxy (WiFi `http_proxy` = Mac:8080):** works for cooperating
  apps — the phone's browser/Google/Spotify all appeared in the proxy log (with
  TLS failures until a CA was trusted). But the **Aqara app made ZERO connections
  through it** — it **ignores the system HTTP proxy** (hardened-app behaviour;
  Context7 confirms this is the known case that needs WireGuard/transparent/local
  modes).
- **User-CA install:** Android 14 refuses CA install via file intent ("install CA
  in Settings"); installed via Settings → Encryption & credentials as a **user CA**.
  Modern/hardened apps distrust user CAs, so this alone would not decrypt the app.
- **WireGuard mode** (`mitmdump --mode wireguard`, tun0 up on the phone): routing
  came up but traffic failed end-to-end ("error de red" on the phone, empty proxy
  log — a mitmproxy-WG DNS/forwarding issue that needs more setup), and the
  user-CA/pinning wall still sits behind it.

**Conclusion:** standard MITM of this SecNeo app **without root** hits compounding
walls (proxy bypass → WireGuard plumbing → user-CA distrust → likely pinning). This
confirms the crux risk. To proceed would need root (system-CA + iptables transparent
redirect) or app instrumentation (Frida SSL-unpin) — both blocked (unrooted phone +
SecNeo). Cleanup after the attempt: revert phone `http_proxy`, re-enable mobile
data, remove the installed mitmproxy user CA, delete the WireGuard tunnel.

## Attempt log — 2026-08-27 (Frida gadget-repack — got IN, /verify blocked by runtime)

After the MITM walls, pivoted to Frida via **gadget-repack on the real phone**
(no root). This got MUCH further than expected:

- `objection patchapk` couldn't patch the launchable `SplashActivity` (SecNeo
  encrypts the real dex) → injected into SecNeo's own loader class
  **`com.secneo.apkwrapper.AW`** instead (`--target-class`). apktool decodes the
  SecNeo stub fine.
- Resigned base + arm64 split with the same key (objection.jks); fixed a packaging
  bug (objection put the gadget in `lib/arm64/` but Android needs `lib/arm64-v8a/`).
- **Result: the patched app RAN — SecNeo's load-time detection did NOT block it.**
  `Frida: Listening on 127.0.0.1 TCP port 27042`, `frida-ps -U` shows `Aqara Home /
  Gadget`. The app uses **okhttp3 + retrofit2** (+ Cronet), un-obfuscated.
- **Captured the app's login + config HTTP in PLAINTEXT** (`/user/guard-code/login`,
  `/app/config/*`, etc.) via an okhttp `RealInterceptorChain.proceed` hook — the
  method works.
- **BUT** SecNeo's RUNTIME anti-Frida makes Java hooking unstable: the process
  crashes deep inside `libfrida-gadget.so` (280+ frame recursion / SIGSEGV) after a
  few minutes, and re-attaches then hit `access violation at
  _performPendingVmOpsWhenReady` (java.js) — SecNeo protects ART. We got ONE good
  window (login), but could not hold a stable window long enough to also trigger the
  BLE lock connection that fires `/publickey`+`/verify` — the exact call needed.

**Conclusion:** gadget-repack defeats SecNeo's *load-time* checks and proves the
HTTP-hook approach, but SecNeo's *runtime* anti-Frida (ART protection → gadget
crashes) prevents reliably capturing the `/verify` session-grant. To finish would
need Frida anti-anti-debug (hook SecNeo's detection/ptrace/timer routines to
stabilise the gadget) or a native-layer hook that avoids the Java bridge — a
further deep effort. The privileged-read tier stays app-only for now.

## Attempt log — 2026-08-27 (BREAKTHROUGH — native SSL hook captured `/verify` in clear)

Downgraded the gadget to **Frida 16.7.19** (user: "frida 16 secneo funcionaba")
and, because SecNeo's runtime ART protection crashes any **Java** hook (SuspendAll
conflict), pivoted to a **native** hook: `Interceptor.attach` on `SSL_read`/
`SSL_write` (BoringSSL) across all loaded modules (`scratchpad/sslhook.js`). This is
**stable** — no crash — because it never touches the Java bridge. It dumps the
plaintext TLS buffers, i.e. the HTTP **bodies** (HTTP/2 DATA frames are not
compressed).

**Captured the app's `/dev/bluetooth/login/assure/verify` exchange in clear:**

- **REQUEST body (SSL_write):**
  `{"deviceId":"matt.73cb7865154223b90e81d000","devicePublicKey":"045f8401…e565"}`
- **RESPONSE body (SSL_read):**
  `{"sessionKey":"9adb2050f051c638e72536dcc93bec4d","verifyData":"24984d904e2c3b34",`
  `"nonce":"d1cf53369e454d917e9ae77cfe","mac":"54ef44100124dcda","code":0}`
  (a second capture gave the same `mac`, fresh sessionKey/nonce/verifyData.)

**Decisive diff result:** the `/verify` **request body is byte-identical** to what
`aqara_ble/kdf.py` (`cloud_verify`) sends — same two fields `{deviceId,
devicePublicKey}` — and the **`deviceId` is identical** to our `.env`
`AQARA_DEVICE_ID` (`matt.73cb7865154223b90e81d000`, a Matter-prefixed id). So the
privilege is **NOT in the `/verify` request body nor the deviceId**. The response
structure is also identical to ours (sessionKey/verifyData/nonce/mac/code).

**What is left, and the residual wall:** the only place the grant can still differ
is the **HTTP request headers** (Token scope, `Sign` preimage, `Appid`/`ClientId`)
— and those ride in **HPACK-compressed HTTP/2 HEADERS frames** (Huffman literals),
which the native SSL_read/SSL_write hook cannot read as plaintext. Reading them
needs an **okhttp `Interceptor`/`Request` (Java) hook** — the exact hook SecNeo's
runtime anti-Frida crashes (proven twice: `_performPendingVmOpsWhenReady` access
violation, SuspendAll SIGSEGV). We DID once read okhttp request headers in a single
brief Java window (the login capture), but cannot hold a window long enough to also
fire `/verify`.

**Status of the line:** narrowed to header-or-app-binding but **not closed**. The
body/deviceId are ruled out. To finish would need either (a) a SecNeo
anti-anti-Frida shim to stabilise a Java okhttp hook, or (b) an HPACK decoder over
the captured SSL_write buffer to reconstruct the request headers offline — both
non-trivial. Our library already sends a full owner-authenticated header set
(`Lang…Appid/Appkey/ClientId/UserId/Token/Sign`, recovered from the app; login +
free reads succeed), so if a privilege header exists it is a subtle scope/signature
difference, not a missing credential.

**Cleanup owed (security hygiene, pending):** uninstall the Frida-patched APK and
reinstall the user's original Aqara app (`scratchpad/apk/base.apk` +
`split_config.arm64_v8a.apk`); remove the mitmproxy user-CA; delete the WireGuard
tunnel.

## Attempt log — 2026-08-27 (FULL HEADERS decoded — cloud request is IDENTICAL)

Pushed past the "bodies-only" wall (user: "no seas complaciente, investiga a fondo").
The request **headers** ride in HPACK-compressed HTTP/2 HEADERS frames, unreadable by
a plaintext SSL dump — but recoverable **offline** without any Java hook:

- New native hook `scratchpad/sslfull.js` dumps the **full hex** of every
  `SSL_write`/`SSL_read`, tagged by the `SSL*` pointer (connection id).
- Offline decoder `scratchpad/decode_h2.py` reassembles each connection's byte
  stream and HPACK-decodes the HEADERS frames (`hpack` 4.2.0).
- **Two bugs found and fixed to get a clean decode:** (1) BoringSSL **reuses the
  same `SSL*` address** for sequential connections → split each pointer stream on
  the HTTP/2 client preface (`PRI * HTTP/2.0…`), one HPACK table per segment;
  (2) `SSL_write` is exported by **two modules** so every write is logged **twice**
  → dedup consecutive-identical payloads (else every frame doubles and HPACK
  desyncs). After both fixes the `/verify` request decodes perfectly.

**Captured `/verify` request headers (`POST …/assure/verify`, `:authority
rpc-ger.aqara.com`):** `lang=es, cuty=ES, app-version=6.3.9, phone-model=…,
time, sys-type=1, sys-version=16, nonce, phoneid, area=EU, appid, clientid,
userid, token(JWT), sign, content-type, content-length`.

**Field-by-field diff vs our `.env` / `kdf` — the cloud request is FUNCTIONALLY
IDENTICAL:**

| header | app (captured) | our library |
| --- | --- | --- |
| `appid` | `444c476ef7135e53330f46e7` | **identical** |
| `userid` | `318a69ea3099258.1530073141342154752` | **identical** |
| `phoneid` | `ZAAwu2m8aezvtqXLSdEqBGr4QA0v2sa7m197POp4x9g` | **identical** |
| `account` (in JWT) | `jusdadodaniel@gmail.com` | **identical** |
| `area` | `EU` | identical |
| `appid`/body/`deviceId` | (see body log above) | identical |
| **`clientid`** | `AFCMfMFEfh72SRG4Zfayx13vIV:APA91b…` | **differs** — but it is an **FCM push-registration token**, not a privilege field |

The app JWT claims: `{sub, appId, iss:rpc-ger, tokenSource:"UC", account, exp,
loginSource:"USER_NEW"}`.

**CONCLUSION — this REFUTES the "privilege lives in the cloud `/verify` request"
hypothesis (036 lead 2 / 037 premise).** Every meaningful field — body, deviceId,
appid, userid, phoneid, account, area, sign structure — is identical between the
app and our library; the only difference is the FCM push token (`clientid`), which
does not gate a BLE read. So the Aqara cloud mints the app's session material from
a request we already reproduce byte-for-byte. The gated-read difference is therefore
**NOT** granted by a distinguishing field in the session-mint request.

**Remaining live variables (ranked):**
1. **JWT scope.** The app's token is `tokenSource:UC / loginSource:USER_NEW`. Our
   library logs in via `/user/guard-code/login`; its token's `tokenSource`/
   `loginSource`/scope is **unverified** (needs an account login to decode — the
   password is not in `.env`). If our token carries a narrower scope, the *lock*
   (not the request) could still be handed non-privileged material. CHEAP to check:
   decode our `CloudAuthManager.get_token()` JWT and compare the two claim sets.
2. **Timing / wake-window artifact.** Because the cloud grant is now proven
   identical, the earlier "gated reads return silence" (036) may be a
   session-timing miss (the gated ops answer only within the lock's wake window;
   `read_burst` must run within ~40 s of a wake on the stabilized link), not a true
   privilege wall. A single correctly-timed persistent-session read of the exact
   app frames (`c3 04 43 01` volume, `68 01 68` language) would settle it — and may
   simply succeed.

The gated-read frames AND their values are already known from the app's decrypted
BLE session (`c3 00 02 04` volume, `68 00 02 01 00 00` language, `20 00 00…`
finger=0, `84 00 02 00 10` alarm) — so even the values are captured.

## Success Criteria

- **SC-001**: Either the cloud field/step that grants privilege is identified and
  replicated (a gated read succeeds from our library), OR it is proven that the
  grant is bound to a secret only the SecNeo-signed app holds (documented, closes
  the line honestly).

## Out of Scope / risks

- Rooting the phone or repacking the SecNeo APK (both ruled out in 036).
- If pinning cannot be bypassed without app instrumentation, this phase is a dead
  end and the gated tier stays app-only — accept and document.

## Assumptions

- The free-tier BLE functionality (event feed, lock/unlock, non-gated reads) is
  already shipped and unaffected; this phase only concerns the sensitive settings.

---

## Related future goal (not this spec): replicate device pairing/union

The user wants, as a future objective, to **replicate the device pairing/union flow**
(adding a U200 to the account from scratch — the provisioning handshake, not just
operating an already-bound lock). That is a separate large feature (its own spec
when tackled); the cloud MITM tooling built here (HTTPS capture of the app's cloud
calls) would directly serve it, since pairing is cloud-heavy. Tracked as a note so
it is not lost.
