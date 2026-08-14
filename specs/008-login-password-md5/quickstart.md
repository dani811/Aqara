# Quickstart: verify the login MD5 fix

## Prerequisites

- `.env` filled with `AQARA_APPID`, `AQARA_APPKEY`, `AQARA_CLIENT_ID`,
  `AQARA_PHONE_ID` (bootstrapped by the one-time Frida capture), exported:
  `set -a; . ./.env; set +a`.
- A valid Aqara account + password for the target region (default EU).

## 1. Offline: the transform is pinned (no network, no secrets)

```bash
.venv/bin/python -m pytest tests/test_kdf.py -q
```

Expected: green. The regression test decrypts our own ciphertext with a matched
throwaway key and asserts the RSA plaintext is `MD5(password)` in lowercase hex
(32 ASCII chars), using a throwaway non-credential password. If the code reverts
to raw-password encryption, this test fails.

## 2. Live: correct credentials yield a token

```bash
set -a; . ./.env; set +a
python tools/refresh_token.py          # prompts for account + password
```

Expected: `[OK] new token: account=<you> …` and `AQARA_TOKEN` rewritten in `.env`.
A wrong password prints a `code=810` authentication failure (which the tool now
describes as "wrong password OR unregistered account", never "wrong password"
alone).

## 4. (Optional) Re-capture the evidence from the app

Instrument a real app login and read the RSA input directly:

```bash
python3 tools/run_hook.py tools/capture_login_flow.js --host <phone-ip>:<port> \
  > /tmp/loginflow.log 2>&1 &
# do one account login in the app, then:
grep -E "LOGINFLOW.*(RSA_IN|LOGIN_REQ)" /tmp/loginflow.log
```

The `RSA_IN_SHAPE` line should report "PARECE MD5-hex" and `RSA_IN_UTF8` the
32-char digest. Delete `/tmp/loginflow.log` afterward — it contains your password.
