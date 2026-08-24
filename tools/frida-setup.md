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

This repo pins the whole chain to **frida 17.17.0** (see `requirements-frida.txt`).
Both sides must be 17.17.0:

### Host
```bash
pipx install --force "frida-tools==17.17.0"   # or: pip install -r tools/requirements-frida.txt
frida --version   # -> 17.17.0
```

### Gadget (in the repacked app)
The repack embeds a frida-gadget `.so`. It must be the **17.17.0** build:
`frida-gadget-17.17.0-android-arm64.so` from
<https://github.com/frida/frida/releases/tag/17.17.0>.

Re-repack once to move the gadget from 16.x → 17.17.0 (drop-in `.so` swap; keep the
same config, `on_load: wait`, re-sign, reinstall). The existing repack process is
unchanged — only the gadget `.so` version changes.

> If you ever prefer to pin to a different version, that is fine — the only rule is
> **host == gadget**. Bump both here and in `requirements-frida.txt` together.

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
