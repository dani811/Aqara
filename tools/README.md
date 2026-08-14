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
| [`run_hook.py`](run_hook.py) | Thin launcher for Frida capture scripts against the instrumented app. |

## Capture hooks (Frida)

| Tool | What it captures |
| --- | --- |
| [`capture_publickey_flow.js`](capture_publickey_flow.js) | The `/publickey` + `/verify` HTTP flow and the `ff07`/`ff08` frames — how you capture your own `.env` values and confirm the handshake. |

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
