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

## Troubleshooting: `TLS certificate verification failed`

Cloud calls verify the server's certificate. If one fails with

```text
TLS certificate verification failed for https://rpc-ger.aqara.com/…
```

then either this machine's CA store is broken — common on a fresh macOS Python,
fixed by running `/Applications/Python\ 3.x/Install\ Certificates.command` or
`pip install --upgrade certifi` — or the connection is genuinely being
intercepted.

Only if you have ruled the second out, and only on a network you trust, you can
skip the check for a run:

```bash
U200_INSECURE_TLS=1 python your_script.py   # prints a warning per request
```

This removes protection for the session material that opens your lock. Fix the
trust store instead whenever you can.

## What's installed

The `aqara_u200_ble` package — cloud KDF/login, the BLE auth handshake, and the
AES-CCM control channel. Next: [capture your credentials](02-capture-credentials.md).
