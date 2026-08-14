# Tools

The instrumentation used to reverse-engineer and now to drive the U200. Two
kinds: **runners** (talk to the lock) and **capture hooks** (observe the app).

> Secrets policy: no tool carries live credentials. Runners read them from a
> git-ignored `.env` (see [`../.env.example`](../.env.example)); captures are
> written under a git-ignored `captures/` tree. The one-off Frida scratch
> scripts from the investigation are RE ephemera and are intentionally not
> shipped — the reusable ones below are.

## Runners

| Tool | What it does |
| --- | --- |
| [`bumble_lock.py`](bumble_lock.py) | Full autonomous flow via an ESP32-S3 HCI controller + Bumble: cloud auth → BLE handshake (with the CRC fix) → verify → AES-CCM control. Config from `.env`. |
| [`refresh_token.py`](refresh_token.py) | Mints a fresh cloud token from your account password (prompted, never stored) and rewrites `AQARA_TOKEN` in `.env`. No previous token needed. |
| [`run_hook.py`](run_hook.py) | Thin launcher for Frida capture scripts against the instrumented app. |

> **Token lifetime.** Aqara invalidates a token the moment the account logs in
> anywhere else — the app on your phone will do it — regardless of the `exp`
> claim, so the cloud answers `code=108, Token has expired` on a token whose
> date is still days away. That is not a dead end: `/user/guard-code/login` is an
> **unauthenticated** request (no Token/UserId/Requestid headers, and `Token=`
> omitted from the signature preimage), so `refresh_token.py` mints a new token
> from account + password alone. The Frida capture below is only needed to
> bootstrap the *other* values — `Appid`, `Appkey`, `ClientId`, `PhoneId`, and
> the device DID.
>
> **History (2026-08-14).** This path returned `code=810` for every credential
> for a while, because `encrypt_login_password` RSA-encrypted the raw password
> when the server expects `RSA(MD5(password))` (lowercase hex). The `810` — same
> code the cloud gives a wrong password *or* an unregistered account — was
> mistaken for "the envelope is right, only the password is wrong". Fixed once
> the RE note's own finding (`docs/login-cuenta.md` §2) was actually applied;
> now verified end-to-end (`code=0`, real JWT).

## Capture hooks (Frida)

| Tool | What it captures |
| --- | --- |
| [`capture_publickey_flow.js`](capture_publickey_flow.js) | The `/publickey` + `/verify` HTTP flow and the `ff07`/`ff08` frames — how you capture your own `.env` values and confirm the handshake. |
| [`capture_login_flow.js`](capture_login_flow.js) | A real **account login** from the app: the plaintext that enters the RSA, the login URL/headers/body, and any digest of a short string. Kept as the reference capture for the login envelope (it confirmed the RSA input is `MD5(password)` hex). |

## The instrumentation stack (what was used)

The reverse engineering combined several layers; documented here so the
approach is reproducible:

- **Frida** on a repackaged app (gadget, `on_load: wait`) — hooked okhttp for
  the cloud calls, `BluetoothGatt` for the BLE writes/notifies, and
  `AqEdUtils.encryptAESCCM` for control-channel plaintext.
- **Bumble + ESP32-S3** — a from-scratch BLE central over an HCI controller, to
  drive the lock without any Android at all.
- **A native Android probe app** — plain `android.bluetooth`, no Aqara code, to
  isolate "is it the app or the radio?" (it was neither — see
  [the journey](../docs/journey/README.md)).
- **tshark / btsnoop** — HCI-level byte-diffs of app vs. our central.
- **jadx / Hermes decompilation** — to read the app's own frame builders
  (`getAiotLongPackageList`, `CrcUtils.ts`, `BleCommandConstant.ts`), which is
  where the CRC and the operation map came from.

## Capturing your credentials

1. Instrument the app with `run_hook.py capture_publickey_flow.js`.
2. Operate the lock once; read the `/publickey` request headers.
3. Copy `Appid`, `Token`, `UserId`, `PhoneId`, `ClientId` and the device DID
   into your `.env`. See [tutorial 02](../docs/tutorials/02-capture-credentials.md).
