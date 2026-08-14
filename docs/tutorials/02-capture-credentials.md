# 02 — Capture your credentials

The library needs YOUR account token and device identifiers. They are not
secrets the project ships — they identify your account and your lock, and they
live only in a local, git-ignored `.env`.

```bash
cp .env.example .env
```

Fill in:

| Variable | Where it comes from |
| --- | --- |
| `AQARA_APPID` / `AQARA_APPKEY` | the app's request headers |
| `AQARA_TOKEN` | a fresh JWT from a logged-in app session (short-lived) |
| `AQARA_USER_ID` / `AQARA_PHONE_ID` / `AQARA_CLIENT_ID` | the app's headers |
| `AQARA_DEVICE_ID` | the lock's DID (`matt.…`) |
| `AQARA_LOCK_MAC` | the lock's BLE MAC |

How to capture them (a running, instrumented app session) is described in
[tools/README](../../tools/README.md). **Never commit `.env`.** When the token
expires (it rotates on re-login), just re-capture it.

> Security note: a token grants access to your account. Treat `.env` like a
> password file.
