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

Copyright (c) 2026 dani811. **All rights reserved except as granted below.**

This project is **source-available, not open source**. It is licensed under the
[PolyForm Noncommercial License 1.0.0](LICENSE):

- ✅ **Permitted, free of charge:** personal use, study, research, experiment,
  testing, hobby and amateur projects, and use by charitable, educational,
  public-research, public-safety/health, environmental and government
  organizations — any genuinely **noncommercial** purpose.
- ⛔ **Not permitted without a separate written license:** any **commercial or
  for-profit** use, including selling, sublicensing, offering it as a paid or
  ad-supported product or service, or using it to build or run a commercial
  product. Reusing this work without permission to profit from it is a licensing
  violation.

You must keep the copyright notice and the `Required Notice:` line from
[LICENSE](LICENSE) with any copy or derivative you distribute.

**Want to use this commercially?** Commercial licenses are available — open an
issue or contact the author via [the repository](https://github.com/dani811/Aqara)
to arrange terms. The full legal text is in [LICENSE](LICENSE); this summary is
for convenience and does not replace it.
