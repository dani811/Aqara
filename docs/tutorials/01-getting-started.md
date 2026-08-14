# 01 — Getting started

## Install

```bash
git clone https://github.com/dani811/Aqara.git
cd Aqara
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"          # add ,bumble or ,ble for a transport
```

## Verify the toolchain

```bash
ruff check .          # lint
ruff format --check . # formatting
mypy aqara_u200_ble   # strict typing
pytest                # unit tests
```

All green means the protocol primitives (CRC, framing, control codec) are
intact. The CRC self-check is the canary: if it stops reproducing the app's
value, the frozen crypto changed and something is wrong.

## What's installed

The `aqara_u200_ble` package — cloud KDF/login, the BLE auth handshake, and the
AES-CCM control channel. Next: [capture your credentials](02-capture-credentials.md).
