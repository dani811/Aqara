#!/usr/bin/env python3
"""Attach a Frida script to the running Aqara gadget via the Python API and
stay resident.

This replaces the ad-hoc `python3 -c "import frida..."` one-liners and the
`run_hook.py` PTY wrapper (which hung repeatedly). The Python API is faster,
non-interactive, and easy to bound with a timeout.

Prereqs: repacked (gadget) app cold-started + `adb forward tcp:27042 tcp:27042`.
(A cold-started gadget app blocks on its splash until a script attaches — this
tool unblocks it as a side effect.)

Usage:
    python3 tools/frida_attach.py tools/capture_all_native.js            # stay until Ctrl-C
    python3 tools/frida_attach.py tools/capture_all_native.js --seconds 120

`send()` payloads from the script print to stdout, prefixed `MSG:`.
The FIRST attach after a cold start sometimes returns "connection closed" — the
tool retries a few times automatically before giving up.
"""
from __future__ import annotations

import argparse
import sys
import time

try:
    import frida
except ImportError:
    sys.exit("frida not installed: pip install 'frida==17.2.12' (match the gadget)")

HOST = "127.0.0.1:27042"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("script", help="path to the .js Frida script to load")
    ap.add_argument("--host", default=HOST)
    ap.add_argument("--seconds", type=float, default=0, help="0 = stay until Ctrl-C")
    ap.add_argument("--retries", type=int, default=5)
    args = ap.parse_args()

    src = open(args.script, encoding="utf-8").read()

    dev = frida.get_device_manager().add_remote_device(args.host)
    session = None
    for attempt in range(1, args.retries + 1):
        try:
            session = dev.attach("Gadget")
            break
        except frida.TransportError as exc:
            print(f"[attach {attempt}/{args.retries}] {exc}; retrying...", file=sys.stderr)
            time.sleep(2)
    if session is None:
        return "could not attach after retries (gadget cold-started? port forwarded?)"

    script = session.create_script(src)
    script.on("message", lambda m, d: print("MSG:", m.get("payload", m), flush=True))
    script.load()
    print(f"ATTACHED {args.script}", flush=True)

    try:
        if args.seconds > 0:
            time.sleep(args.seconds)
        else:
            while True:
                time.sleep(3600)
    except KeyboardInterrupt:
        print("\ndetaching", flush=True)
    finally:
        try:
            session.detach()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
