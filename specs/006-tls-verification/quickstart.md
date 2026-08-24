# Quickstart: validating the TLS verification fix

**Feature**: 006-tls-verification · **Date**: 2026-08-14

## Prerequisites

```bash
cd <repo root>
source .venv/bin/activate        # or your own env
pip install -e ".[dev]"
```

No lock, no credentials, and no network are needed for scenarios 1–3.

## Scenario 1 — the gates stay green

```bash
ruff check . && ruff format --check .
mypy aqara_ble
pytest -q
```

**Expected**: all three clean, with the new TLS policy tests included in the
pytest count.

## Scenario 2 — default policy is secure (US1)

```bash
python -c "
from aqara_ble.kdf import _tls_context
ctx = _tls_context()
print('check_hostname:', ctx.check_hostname)
print('verify_mode  :', ctx.verify_mode)
"
```

**Expected**:

```text
check_hostname: True
verify_mode  : 2          # ssl.CERT_REQUIRED
```

> On Python 3.14 an `ssl.VerifyMode` prints as its integer value (`2` =
> `CERT_REQUIRED`, `0` = `CERT_NONE`); on older versions you see
> `VerifyMode.CERT_REQUIRED`. The unit tests compare against the enum members,
> so they are unaffected either way.

## Scenario 3 — the opt-out, and only when explicit (US2)

```bash
U200_INSECURE_TLS=1 python -c "
from aqara_ble.kdf import _tls_context
ctx = _tls_context()
print('check_hostname:', ctx.check_hostname, '| verify_mode:', ctx.verify_mode)
"

U200_INSECURE_TLS=0 python -c "
from aqara_ble.kdf import _tls_context
print(_tls_context().verify_mode)
"
```

**Expected**: the first prints a stderr warning naming `U200_INSECURE_TLS`, then
`check_hostname: False | verify_mode: 0` (`CERT_NONE`). The second prints `2`
(`CERT_REQUIRED`) with no warning — a falsey value changes nothing.

**Observed on 2026-08-14** (Python 3.14.5, macOS):

```text
default -> check_hostname: True | verify_mode: 2
[U200] WARNING: TLS certificate verification is DISABLED (U200_INSECURE_TLS); this connection is not protected against interception.
opt-out -> check_hostname: False | verify_mode: 0
falsey  -> 2
```

Scenario 1 on the same run: `ruff check` clean, `mypy aqara_ble` clean,
`pytest` 70 passed. (`ruff format --check .` flags 7 files that already failed on
a clean `develop` — pre-existing, recorded in [docs/roadmap.md](../../docs/roadmap.md).)

## Scenario 4 — a real cloud call still works (US1, needs credentials)

With a populated `.env` (see [`.env.example`](../../.env.example)):

```bash
python tools/cloud_login.py        # or the tutorial's capture step
```

**Expected**: identical output to before the fix. If it now fails with a
certificate error, that is the fix working — either your machine's trust store is
broken (see the troubleshooting entry in
[docs/tutorials/01-getting-started.md](../../docs/tutorials/01-getting-started.md))
or the connection is being intercepted.

## Scenario 5 — actionable failure message (US3, optional)

Point the client at a host with a self-signed certificate (e.g. a local
`openssl s_server`) and confirm the raised `RuntimeError` names both the
verification failure and `U200_INSECURE_TLS`.

**Expected**: message of the form
`… TLS certificate verification failed … set U200_INSECURE_TLS=1 …`.
