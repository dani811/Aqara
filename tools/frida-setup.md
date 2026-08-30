# Frida capture toolchain — pinned & reproducible

The capture hooks (`tools/capture_*.js`, run via `tools/run_hook.py`) attach to the
**Aqara Home app repackaged with a frida-gadget**. This file pins the toolchain so
it does not silently break as the project ages.

## The invariant (the thing that broke)

> **The host `frida-tools` version MUST EQUAL the `frida-gadget` version baked into
> the repackaged APK.**

Frida changed its wire protocol between **16.x and 17.x**. An unpinned host (e.g. a
plain `pipx install frida-tools`, which always pulls the latest) drifts to 17.x while
the repacked app still carries a 16.x gadget. The symptom is **not** an obvious
version error — it is:

```
Failed to spawn: connection closed          # via `frida … Gadget`
TransportError: connection closed           # via the Python API
Failed to enumerate processes: connection closed   # via frida-ps
```

The handshake dies before frida can even report the gadget's version. Do **not**
mistake this for the known transient "connection closed on the *first* attach, retry
once" quirk — that one clears on a second attempt; a version mismatch never does.

## Pinned version

This repo pins the whole chain to **frida 16.7.19** (see `requirements-frida.txt`) —
confirmed working end-to-end (2026-08-27 in specs/037-cloud-session-mitm/spec.md,
re-confirmed live 2026-08-28). A 17.17.0 pin was tried first and never got a gadget
to actually connect; don't re-attempt it without re-verifying, this doc previously
claimed 17.17.0 worked and that was wrong.

### Host
```bash
pip install -r tools/requirements-frida.txt   # pins core `frida` to 16.7.19
# if frida-tools (the CLI) was installed via pipx separately, its own venv needs
# the same core package downgraded too — pipx does not pick up requirements.txt:
pipx runpip frida-tools install --force-reinstall "frida==16.7.19"
frida --version   # -> 16.7.19 (this reports the core `frida` version, not the
                  #  frida-tools package's own — much lower — version number)
```

### Gadget (in the repacked app)
Objection's `patchapk` downloads the gadget itself — `objection patchapk -s <apk>
-a arm64 -V 16.7.19 -t com.secneo.apkwrapper.AW` (target class: SecNeo's own loader,
since `apktool`/objection can't patch the real launch activity — its dex is
encrypted). It has a **packaging bug**: it drops the `.so` at `lib/arm64/` instead of
`lib/arm64-v8a/` — fix by moving it inside the built APK, then re-`zipalign` +
re-`apksigner sign` (objection's own keystore + password are in
`objection/utils/patchers/android.py::sign_apk` — `objection.jks` / alias
`objection` / pass `basil-joule-bug`). The **native lib split** (`split_config.
arm64_v8a.apk`) must be re-signed with the **same** key (`zipalign` + `apksigner
sign`, no content change needed) so `adb install-multiple base.apk split.apk`
accepts both as one signed set. `aapt`/`aapt2`/`zipalign`/`apksigner` ship under
`~/Library/Android/sdk/build-tools/<ver>/` if no standalone install exists.

> If you ever prefer to pin to a different version, that is fine — the only rule is
> **host == gadget**. Bump both here and in `requirements-frida.txt` together, and
> actually verify `check_gadget.py` connects before trusting the new pin.

## Verify before capturing

```bash
python tools/check_gadget.py    # prints "CONNECTED — gadget compatible" or the mismatch
```
`check_gadget.py` connects to `127.0.0.1:27042` and confirms host↔gadget compatibility.

## Capture procedure

```bash
# 1. phone connected + authorised (adb devices shows it)
adb forward tcp:27042 tcp:27042

# 2. COLD-START the app so the gadget's `on_load: wait` blocks and listens on 27042.
#    (A warm relaunch may skip the wait — force-stop first.)
adb shell am force-stop com.lumiunited.aqarahome.play
adb shell monkey -p com.lumiunited.aqarahome.play -c android.intent.category.LAUNCHER 1
#    wait until 27042 is listening on the phone:
adb shell "cat /proc/net/tcp /proc/net/tcp6" | grep -i 69A2   # 69A2 = 27042

# 3. attach a hook (unblocks the app; it resumes and its HTTP/BLE is logged):
python3 tools/run_hook.py tools/capture_all_http.js > /tmp/allhttp.log 2>&1 &
#    (if the FIRST attach says "connection closed" and check_gadget says versions
#     match, that's the transient quirk — force-stop, cold-start, attach again.)

# 4. drive the app; then grep the log.
```

## Notes
- The Aqara app is **SecNeo-hardened** (`libDexHelper*.so`, `libdatajar.so`): it will
  not run under a plain `frida-server`/emulator — hence the gadget-repack on a real
  device.
- The gadget listens on **27042** only while the repacked app is running, and only
  blocks on **cold start** (`on_load: wait`).
- `run_hook.py` attaches with `frida -H 127.0.0.1:27042 Gadget -l <script>`.
- **Use `capture_ssl_native.js`, not a Java/okhttp hook.** SecNeo's *runtime*
  anti-Frida makes any hook that touches the ART/Java bridge (e.g. an
  `RealInterceptorChain.proceed` hook) crash within minutes (SecNeo suspends-all →
  gadget SIGSEGVs, `_performPendingVmOpsWhenReady`). A **native**
  `Interceptor.attach` on BoringSSL's `SSL_read`/`SSL_write` (across every loaded
  module, plus a `dlopen` watcher for libraries that load lazily after attach) never
  touches ART and is stable. It dumps plaintext bodies pre-encryption/post-decryption
  — no proxy, no CA install, no network-security-config needed.
- **Kill the hook before doing UI navigation.** A hook that `console.log`s every
  `SSL_read`/`SSL_write` synchronously over the PTY can stall the app's main thread
  badly enough that `uiautomator`/taps stop registering (looks like a frozen app, not
  a crash). Attach it only right before the action you need to capture, detach right
  after.
