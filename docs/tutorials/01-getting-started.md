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

then either this machine's CA store is broken — or the connection is genuinely
being intercepted.

The broken-store case is the common one, and it is worth confirming rather than
guessing. Ask Python where it looks for certificates:

```bash
python -c "import ssl; print(ssl.get_default_verify_paths())"
```

A python.org framework build points at
`/Library/Frameworks/Python.framework/Versions/3.x/etc/openssl/cert.pem`. If
that file **does not exist**, the installer's `Install Certificates.command` was
never run and Python has no root certificates at all — every HTTPS call fails,
not just Aqara's. (Verified on this project's own machine, 2026-08-14: no
`cert.pem`, which is the original reason certificate verification had been
switched off in the code.)

Two fixes, in order of preference:

```bash
# 1. Run the installer's own script (permanent, system-wide for that Python):
/Applications/Python\ 3.x/Install\ Certificates.command

# 2. Or point OpenSSL at certifi's bundle (per-environment):
pip install certifi
echo "SSL_CERT_FILE=$(python -c 'import certifi; print(certifi.where())')" >> .env
```

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
