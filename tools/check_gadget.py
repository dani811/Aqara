#!/usr/bin/env python3
"""Report the frida-gadget version reachable at 127.0.0.1:27042 (via adb forward).

Frida requires the host `frida-tools` version to MATCH the frida-gadget baked into
the repackaged app. A mismatch shows up as "connection closed" / "Failed to spawn".
This connects with the Python API and prints the gadget's parameters, or the
version-mismatch error (which names the required version). Use it to pin
`frida-tools` to the gadget's version — see tools/frida-setup.md.

Prereqs: app cold-started (gadget listening, on_load:wait) + `adb forward tcp:27042 tcp:27042`.
"""
from __future__ import annotations

import sys

try:
    import frida
except ImportError:
    print("frida not installed: pip install frida-tools==<pinned>  (see tools/frida-setup.md)")
    sys.exit(2)

print(f"host frida python: {frida.__version__}")
try:
    dm = frida.get_device_manager()
    dev = dm.add_remote_device("127.0.0.1:27042")
    params = dev.query_system_parameters()
    print("CONNECTED — gadget compatible with host", frida.__version__)
    print("system parameters:", {k: params.get(k) for k in ("os", "platform", "arch", "name") if k in params})
    procs = dev.enumerate_processes()
    print("processes:", [(p.pid, p.name) for p in procs][:5])
except Exception as exc:  # noqa: BLE001
    msg = str(exc)
    print("NOT COMPATIBLE / not reachable:")
    print(" ", type(exc).__name__, "-", msg)
    # frida names the required version on a hard mismatch; surface it plainly.
    import re
    m = re.findall(r"\d+\.\d+\.\d+", msg)
    if m:
        print("  version(s) mentioned:", m)
