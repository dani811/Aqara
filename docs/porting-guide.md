# Porting guide — bringing a new Aqara device online

This is the spine of the project: a linear, numbered process to take the library
from zero to controlling **another** Aqara-family device. The U200 is the solved
reference; a device such as the U400 is used below only as an illustrative target.

The guiding idea is the [Layer Map](architecture.md#layer-map--transversal-vs-device-specific):
most of the work is already done and **reusable unchanged** (the transversal
layer, [`reference/`](reference/README.md)); what you actually port is a small,
device-specific surface ([`devices/<device>/`](devices/u200/README.md)).

## Read this first — the two obstacles, already solved

Two things blocked the original work. You do **not** need to rediscover them.

### Obstacle 1 — the CRC gate (this is the big one)

In the `0610` authentication frame, header bytes 7–8 look like a random token.
**They are the [CRC-16/ARC of the frame body](reference/framing-crc.md)** (the
public key), little-endian. Send anything else and the lock replies with an empty
ACK (`status 01`) forever — a byte-perfect frame still fails on this one field.

- **Fix:** compute CRC-16/ARC over the body and place it little-endian in bytes
  7–8. Full algorithm and verification in
  [reference/framing-crc.md](reference/framing-crc.md).
- **Verify:** a wrong value → empty ACK; the correct value → the lock returns its
  public key. That flip is your success signal.

### Obstacle 2 — the login crypto

Account login RSA-encrypts **`MD5(password)` in lowercase hex (32 ASCII chars)**,
not the raw password. The raw-password mistake makes the server reject every
credential with an ambiguous code that reads like "wrong password".

- **Fix + verify:** see [reference/cloud-login.md](reference/cloud-login.md).

Everything else below is mechanical if these two are respected.

## The process

### Step 0 — Prepare the environment

```bash
git clone https://github.com/dani811/Aqara.git
cd Aqara
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"          # add ,bumble or ,ble for a transport
ruff check . && ruff format --check . && mypy aqara_u200_ble && pytest
```

All green means the transversal primitives (CRC, framing, control codec) are
intact — the CRC self-check is the canary. If a cloud call fails with a TLS
certificate error, your machine's CA store is likely broken (fix the trust store;
see [reference/cloud-login.md](reference/cloud-login.md#transport-security)),
not the server.

- **Reuse (transversal):** the whole library and its primitives.
- **Discover (device):** nothing yet.

### Step 1 — Capture traffic (your own account & device)

You need your own account token and the new device's identifiers, captured from a
running, instrumented app session, and placed in a git-ignored `.env`
(`cp .env.example .env`). **Never commit `.env`** (Constitution Principle I).

| Variable | Source |
| --- | --- |
| `AQARA_APPID` / `AQARA_APPKEY` | the app's request headers |
| `AQARA_TOKEN` | a fresh JWT from a logged-in app session (short-lived) |
| `AQARA_USER_ID` / `AQARA_PHONE_ID` / `AQARA_CLIENT_ID` | the app's headers |
| `AQARA_DEVICE_ID` | the new device's DID |
| `AQARA_LOCK_MAC` | the new device's BLE address |

Capture both an **HCI/BLE trace** (for the frames) and the **HTTP flow** (for the
cloud). Tokens rotate on re-login; a fresh one can be minted from account +
password (login is unauthenticated).

- **Reuse (transversal):** the capture method and the cloud login/signing.
- **Discover (device):** your device's identifiers and its raw frames.

### Step 2 — Identify the GATT map

From service discovery on the new device, fill the device-agnostic
[channel roles](reference/ble-transport.md) with concrete values: the
service/characteristic UUIDs and ATT handles for auth, control, OTA, and bulk.
Compare against the U200's map ([devices/u200/gatt-map.md](devices/u200/gatt-map.md))
as a template.

- **Reuse (transversal):** the four-role model, the fragmentation scheme.
- **Discover (device):** the UUIDs and handles → write `devices/<device>/gatt-map.md`.
- **Watch out:** the U200 only advertises after its keypad is activated; a new
  device may gate discovery differently.

### Step 3 — Resolve the authentication handshake

Drive the [`0610`/`0710` exchange](reference/auth-handshake.md): enable
notifications, write the cloud public key in `0610` **with the correct CRC**,
tolerate empty ACKs until the lock's key arrives, run the cloud `verify`, then
write `0710`.

- **Reuse (transversal):** the two-frame mechanism, the 18-byte header layout, and
  the CRC gate (Obstacle 1 — already solved).
- **Discover (device):** reconfirm `lock_token` handling and key sizes against a
  fresh capture.
- **Success signal:** the lock returns its public key instead of an empty ACK.

### Step 4 — Open the control channel

With session material in hand, protect payloads with
[AES-CCM](reference/control-channel.md) (tag=4, empty AAD) and write
`write_prefix + ciphertext` on the control channel.

- **Reuse (transversal):** the AES-CCM parameters and the `kind|command|body|trailer`
  frame shape.
- **Discover (device):** confirm the write prefix and that the frame shape holds.
- **Verify first with a no-op:** send a keepalive-style command so you exercise the
  channel without actuating the bolt.

### Step 5 — Map the operations catalog

Decrypt captured control frames and correlate each with an app action to build the
device's opcode catalog, tagging each entry `confirmed` / `catalogued` /
`unverified`. Use the U200 catalog
([devices/u200/operations.md](devices/u200/operations.md)) as the shape to fill.

- **Reuse (transversal):** the control-frame framing and the promotion workflow
  (capture → correlate → confirm).
- **Discover (device):** the actual opcodes, payload bodies, and any additive
  trailer bases → write `devices/<device>/operations.md`.
- **Note:** the U200's operate-frame trailer bases were derived from one device and
  may differ; re-derive them.

## When you get stuck

Go to [diagnostics.md](diagnostics.md): a symptom → hypothesis → test table for the
common failures (empty ACK, dropped fragments, hanging GATT requests).

## Definition of done for a new device

- `devices/<device>/gatt-map.md` and `operations.md` written, entries tagged.
- The handshake returns the device's public key (CRC gate passed).
- A no-op control command round-trips; then a real actuation is confirmed live.
- No secret, capture, or app source committed; every claim carries evidence or an
  `unverified` tag.
