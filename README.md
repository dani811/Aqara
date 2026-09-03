# Aqara BLE

Autonomous control of Aqara Bluetooth Low Energy locks from Python — no app, no
phone — reconstructed by reverse-engineering the official application's observed
behaviour. The **U200** is the fully solved reference device.

## Goals

- Document the Aqara BLE + cloud protocol precisely enough to reproduce it.
- Provide a cross-platform Python library that exposes the lock's full operation
  surface.
- Enable a native Home Assistant integration (the primary target).
- Make porting to other Aqara-family devices a methodical, repeatable process.

## Quick start

Two ways in — a terminal command and an importable API. **Integrations couple to
the API**; the CLI is just a thin adapter over that same API.

### Terminal — the `aqara` command

```bash
pip install -e .            # puts `aqara` on your PATH
aqara login                 # account login only (no radio)
aqara scan  --transport bleak
aqara lock  --transport bumble --port serial:/dev/cu.usbmodemNNNN,115200
aqara unlock ; aqara operate keepalive
```

Credentials come from `--account/--password` or the environment/`.env`
(`AQARA_ACCOUNT`, `AQARA_PASSWORD`, `AQARA_APPID`, `AQARA_APPKEY`,
`AQARA_CLIENT_ID`, `AQARA_PHONE_ID`, `AQARA_DEVICE_ID`).

### Library — the coupling surface for integrations

```python
from aqara_ble import BleakTransport, CloudAuthManager, U200Client

auth = CloudAuthManager(
    account=..., password=..., appid=..., appkey=..., client_id=..., phone_id=...
)
async with await U200Client.connect(
    auth=auth, transport=BleakTransport(), device_id="lumi1.xxxx"
) as lock:
    await lock.lock()
```

The facade logs in (and re-authenticates on token expiry), scans and identifies
the lock by what it advertises, connects, discovers services and runs the
authenticated operation. Swap `BleakTransport()` for
`BumbleTransport("serial:/dev/…")` to drive an ESP32‑S3 controller
([firmware](tools/esp32s3_hci_usb/README.md)). Shell equivalent:
`python examples/lock_cli.py --transport bleak lock`.

## Start here

- **[docs/](docs/README.md)** — the documentation entry point (understand · port ·
  diagnose).
- **[docs/devices/u200/validation.md](docs/devices/u200/validation.md)** — run it
  against a real U200 (facade, transports, troubleshooting).
- **[docs/architecture.md](docs/architecture.md)** — how it works end to end and
  the transversal-vs-device Layer Map.
- **[docs/porting-guide.md](docs/porting-guide.md)** — the numbered process to
  bring a new device online, with the CRC and login obstacles solved up front.
- **[CONTRIBUTING.md](CONTRIBUTING.md)** — Spec-Driven Development workflow and the
  secret-hygiene rules.

## Secrets — non-negotiable

No real secret, capture, or app source ever enters this repository. Credentials
and device identifiers live only in a local, git-ignored `.env` (see
[`.env.example`](.env.example)); raw captures live under a git-ignored `captures/`
tree. See Constitution Principle I in
[`.specify/memory/constitution.md`](.specify/memory/constitution.md).

## License

Copyright (c) 2026 dani811.

This project is **free and open source** under the
[GNU Affero General Public License v3.0 (AGPL-3.0-only)](LICENSE). In plain terms:

- ✅ **You may** use it (including for home automation — e.g. a
  [Home Assistant](https://www.home-assistant.io/) custom integration), study it,
  run it, share it and modify it, free of charge.
- 🔁 **Copyleft — the catch that protects the work:** if you distribute it or
  offer it to others over a network (as a service), you **must** release your
  full source under this same AGPL license and **keep the author's copyright and
  attribution**. Nobody can take this code, close it up, and sell it as a
  proprietary product.
- 📛 **Attribution is mandatory:** the copyright notice and per-file license
  headers must stay intact in any copy or derivative.

**Home Assistant:** the AGPL is compatible with a Home Assistant **custom
integration** (installed by the user, e.g. via HACS) for personal/home use. Note
that Home Assistant *Core* only accepts permissively licensed
(Apache-2.0-compatible) dependencies, so an official-core integration would
require different terms.

**Relicensing:** dani811 is the sole copyright holder and may release future
versions of this project under different terms (for example, a permissive
Apache-2.0 license) at any time. The full legal text is in [LICENSE](LICENSE);
this summary is for convenience and does not replace it.
