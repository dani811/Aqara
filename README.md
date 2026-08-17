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

```python
from aqara_u200_ble import BleakTransport, CloudAuthManager, U200Client

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

See [LICENSE](LICENSE).
