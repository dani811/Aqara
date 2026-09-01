# frida-17.2.12 — CONFIRMED: survives, use this for Java-level work

**2026-09-01 result: `Java.perform()` survives.** Built fresh against a
pristine Play Store pull (6.3.9/6966 — the previously-patched 16.7.19 APK
was NOT reused as a base; repacking an already-repacked APK duplicates the
gadget .so and is its own hazard, unrelated to this test — see the
git history of this file if that ever needs re-explaining). Installed via
`adb install-multiple` (base + `split_config.arm64_v8a`, both re-signed
with objection's debug key). Host pinned to matching 17.2.12
(`pip install "frida==17.2.12"` + the pipx `frida-tools` reinstall from
`../../frida-setup.md`).

Test script (`frida-java-bridge` via npm + `frida-compile`, since Frida 17
unbundled the Java runtime bridge — a bare `Java.perform` in a raw
Python-attached script throws `ReferenceError: 'Java' is not defined`
without this):

```js
import Java from 'frida-java-bridge';
Java.perform(() => {
  send('[test] Java.perform succeeded, ART bridge attached');
  const ActivityThread = Java.use('android.app.ActivityThread');
  send('[test] Java.use(android.app.ActivityThread) succeeded too');
});
setInterval(() => send('[heartbeat]'), 5000);
```

Result: both `send()` calls fired, then **29 heartbeats over 150s with no
crash, no detach, the app UI stayed fully responsive** (screenshotted
mid-test — normal login screen, not frozen). Compare to the standing
16.7.19 finding: "SecNeo suspends-all → gadget SIGSEGVs" within minutes of
any ART/JNI-touching hook.

**Practical fallout for the whole project**: the offline-password
Kotlin-level investigation (flagged "untried, crash risk" for months) and
the OTA-activation-value question ([[clean-session-start-here]]) are both
unblocked — hook `handleSetLanguageByChannel`/`mapLanguageValueToChannel`
(and, for the older investigation, `PeriodPasswordViewModel`/
`CreatePeriodPasswordEntity`) directly now, no need for the native-Hermes
workaround this README originally proposed as a fallback.

**Open decision, not made yet**: should 17.2.12 become the new pinned
"daily driver" in `tools/requirements-frida.txt`, replacing 16.7.19
project-wide? Arguments for: strictly more capable (native hooks that
worked on 16.7.19 have no reason to stop working on 17.2.12; Java hooks
now also work). Arguments for caution: only smoke-tested with a trivial
hook so far, not with the heavier native SSL/BLE capture scripts this
project actually depends on day to day — verify those still work on
17.2.12 before fully retiring 16.7.19, don't assume from one passing test.

---

## Original hypothesis (superseded by the result above, kept for provenance)

## Hypothesis

`docs/devices/u200/operations.md`/`full-feature-roadmap.md` record, more
than once, that any Frida hook touching the ART/Java bridge on this
SecNeo-hardened app crashes within minutes (SecNeo detects the tampering
and suspends-all). Every attempt so far was on **16.7.19**, pinned back in
2026-08-27 for an *unrelated* reason (a 16↔17 wire-protocol break that made
17.17.0 fail to even connect the gadget — see `../README.md`'s status
table). **No attempt has ever combined a matched, modern 17.x host+gadget
pair with a Java-level hook against this app.**

Frida's own release notes single out 17.2.12 for fixing exactly the class
of bug most likely to matter here:

> "Frida's Android support has been improved by updating `frida-java-bridge`
> in `system-server`. This update fixes incorrect ART class spec offset
> detection, preventing crashes that occurred when `libart.so` was updated
> independently of the SDK version. The fix now relies on runtime detection
> via known classes for greater reliability."

This is **not confirmed to fix the SecNeo crash** — that crash is
attributed to SecNeo's own *deliberate* anti-tampering (an active defense),
not to Frida guessing wrong ART offsets (a passive compatibility bug). The
two are different failure classes, and this fix addresses the second one.
Treat this as a real, evidence-backed hypothesis worth ~30 minutes of live
testing, not a confirmed solution — see the conversation that produced this
note for the full reasoning trail if it's ever unclear why 17.2.12
specifically (not 17.7.1, not latest) was picked first.

## Build & test plan

```bash
# 1. Build (host stays on 16.7.19 for everything else until this is confirmed):
tools/repack_apk.sh 17.2.12

# 2. Install on the phone (this REPLACES whatever repacked build is currently
#    installed — same package name, so a plain reinstall is fine, no uninstall
#    needed unless signing keys ever differ, which they won't here since the
#    script always uses objection's own fixed debug key):
adb install -r tools/repacked-apks/frida-17.2.12/aqara-repacked.apk

# 3. Temporarily point the HOST at 17.2.12 too (don't forget to revert this
#    after the test if it fails — see step 6):
pip install "frida==17.2.12" "frida-tools"
pipx runpip frida-tools install --force-reinstall "frida==17.2.12"
frida --version   # must print 17.2.12

# 4. Cold-start + verify the gadget connects at all (this alone answers half
#    the open question — 17.17.0 never got this far):
adb forward tcp:27042 tcp:27042
adb shell am force-stop com.lumiunited.aqarahome.play
adb shell monkey -p com.lumiunited.aqarahome.play -c android.intent.category.LAUNCHER 1
python3 tools/check_gadget.py   # expect "CONNECTED — gadget compatible with host 17.2.12"

# 5. THE actual test — a trivial Java.perform no-op, nothing more, watch for
#    a crash within the next few minutes of normal app use (not just at
#    attach time — the recorded crash pattern was "crashes within minutes",
#    i.e. it can look fine for the first several seconds):
python3 -c "
import frida, time
dev = frida.get_device_manager().add_remote_device('127.0.0.1:27042')
session = dev.attach('Gadget')
script = session.create_script('''
Java.perform(function () {
    console.log('[test] Java.perform succeeded, ART bridge attached');
});
''')
script.load()
time.sleep(120)  # stay attached, use the app normally during this window
session.detach()
print('survived 120s with a live Java.perform hook')
"

# 6. Whatever the result, record it in ../README.md's status table AND revert
#    the host pin back to 16.7.19 before doing anything else with the app
#    (tools/requirements-frida.txt is the source of truth for the "daily
#    driver" version — don't leave the host drifted to 17.2.12 for routine
#    work, only for this test):
pip install -r tools/requirements-frida.txt
pipx runpip frida-tools install --force-reinstall "frida==16.7.19"
```

## If it survives

Hook `handleSetLanguageByChannel`/`mapLanguageValueToChannel` (real
function names already located in the decompiled Hermes bundle — see
`docs/reference/rn-device-plugins.md`) to capture what actually produces
the OTA "activate" frame's 17-byte value, instead of inferring it from
timing correlation (see `docs/devices/u200/operations.md`'s 2026-09-01
entry). This would also reopen the offline-password Kotlin-level
investigation flagged as "untried, crash risk" in `full-feature-roadmap.md`.

## If it crashes the same way

That's a real, useful negative result too — it means the crash is
SecNeo's own detection, not an ART-compatibility bug, and no Frida version
bump will fix it. The next thing worth trying is hooking **`libhermes.so`'s
own native exports directly** (`Interceptor.attach` on Hermes's C++ call
surface, e.g. around `HermesRuntime::evaluateJavaScript` or the bytecode
interpreter's function-call dispatch) — this never touches the ART/JNI
bridge at all (same reason the native SSL hook in `capture_ssl_native.js`
is stable while Java hooks aren't), so it should sidestep SecNeo's
ART-specific detection entirely. Untried this session; the exact Hermes
symbol names to target need probing with `Process.getModuleByName
('libhermes.so').enumerateExports()` first.
