# Repacked Aqara APKs, one folder per Frida gadget version

Every past session repacked the app ad hoc, tested it, and threw the APK
away — so each new session started from zero and had to rediscover the same
findings ("17.17.0 doesn't even connect") from a one-line mention buried in
a doc, if it survived at all. This directory is the fix: **build once per
version, keep the binary locally (git-ignored — see below), record the
result here, and never repeat a build whose outcome is already known.**

Build a version with:

```bash
tools/repack_apk.sh <frida-version>          # e.g. tools/repack_apk.sh 17.2.12
```

It reads `original/aqara-official.apk` (pull it once from the phone — see
that folder) and writes `frida-<version>/aqara-repacked.apk` +
`BUILD_INFO.txt`. Install any built version with
`adb install -r tools/repacked-apks/frida-<version>/aqara-repacked.apk` —
switching which one is "live" on the phone is just re-running that install
command, no rebuild needed as long as the folder already exists.

**The APK/keystore binaries themselves are git-ignored** (see repo
`.gitignore`) — multi-hundred-MB binary artifacts don't belong in git. What
*is* committed and consolidated is this table and each version's notes, so
the knowledge survives even when the binary doesn't.

## Status per version

| Version | Host+gadget connect? | Java/ART hook survives? | Notes |
| --- | --- | --- | --- |
| `16.7.19` | ✅ yes | ❌ crashes (SecNeo suspends-all within minutes) | Was the daily driver through 2026-09-01. Confirmed working end-to-end 2026-08-27/28. Superseded for Java-hook work by 17.2.12 below — kept here as the known-safe fallback for native-only capture work. |
| `17.17.0` | ❌ **no — gadget never connects** ("connection closed" before Frida can even report gadget version) | untested (never got that far) | Tried first, historically, before the project settled on 16.7.19. **Don't re-attempt without a real reason** — this is a recorded negative result, not a guess. If retried anyway, use this script so the attempt and its outcome get logged here instead of lost again. |
| `17.2.12` | ✅ **yes** | ✅ **CONFIRMED SURVIVES — 2026-09-01 live test** | `Java.perform()` + `Java.use('android.app.ActivityThread')` + a 5s heartbeat ran 150s straight, zero crash, on a fresh repack of the pristine Play Store APK (6.3.9/6966). **This overturns the standing "any ART/JNI hook crashes SecNeo" finding — that was only ever true on 16.7.19.** See `frida-17.2.12/README.md` for the exact repro and the real next step (hooking the OTA-activation code path instead of a no-op). |

## `original/`

Holds the pristine, un-repacked official APK — pull it fresh whenever you
suspect Aqara pushed an app update (a repack against a stale original can
behave differently from what's actually installed):

```bash
adb shell pm path com.lumiunited.aqarahome.play
adb pull <base.apk path from above> tools/repacked-apks/original/aqara-official.apk
```

## Why this doesn't defeat the whole point of reverse-engineering carefully

Keeping several repacked builds around is fine precisely because repacking
is **non-destructive to the real investigation** — it only touches a copy
of the APK on the phone's filesystem, never the lock, never the account.
Swapping which repacked build is installed is safe to do as often as
useful; it's live BLE/keypad-gate actions on the physical lock that need
the care documented elsewhere ([[clean-session-start-here]]).
