# Examples

Runnable, **dev-only** helpers. They are **not** part of the `aqara_ble`
API — the library never reads the environment, prompts, or persists secrets. In
production (e.g. Home Assistant) the consumer injects credentials from its own
secure storage and constructs a `CloudAuthManager` directly.

| File | What it does |
| --- | --- |
| [`auth_from_env.py`](auth_from_env.py) | Build a `CloudAuthManager` from environment variables (a `.env` convenience). |
| [`lock_cli.py`](lock_cli.py) | Compat shim → the packaged **`aqara`** command (`aqara_ble.cli:main`). Prefer `aqara …`. `scan` / `lock` / `unlock` / `operate <name>` through the library facade (`U200Client`), with `--transport bleak` (host Bluetooth) or `--transport bumble` (ESP32‑S3 controller, see [`../tools/esp32s3_hci_usb`](../tools/esp32s3_hci_usb/README.md)). |

```bash
.venv/bin/python examples/lock_cli.py --transport bleak scan
.venv/bin/python examples/lock_cli.py --transport bleak lock
.venv/bin/python examples/lock_cli.py --transport bumble lock      # port from AQARA_ESP32_PORT
```

The same thing from Python is three lines:

```python
auth = CloudAuthManager(
    account=..., password=..., appid=..., appkey=..., client_id=..., phone_id=...
)
async with await U200Client.connect(
    auth=auth, transport=BleakTransport(), device_id="lumi1.xxxx"
) as lock:
    await lock.lock()
```

> Secrets policy: credentials live only in a local, git-ignored `.env`. Never
> commit real values (Constitution Principle I).
