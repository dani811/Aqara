# Documentation

Autonomous control of Aqara BLE locks — the protocol, the process to port it to a
new device, and the evidence behind every claim. The **U200** is the solved
reference device.

## Where to go, by goal

### I want to **understand** the system

Start with [architecture.md](architecture.md): the end-to-end pipeline, the
technology (BLE + Thread), the trust model, and the **Layer Map** that separates
what is reusable across the Aqara family from what is specific to one device.

### I want to **port** the library to another device

Follow [porting-guide.md](porting-guide.md): a numbered process (prepare → capture
→ GATT → handshake → control → operations), with the two historic obstacles (the
CRC gate and the login crypto) solved up front, and per-step guidance on what to
reuse vs discover.

### I'm stuck and want to **diagnose** a failure

Go to [diagnostics.md](diagnostics.md): symptom → hypothesis → test for the common
failures.

## The reference (device-agnostic)

The reusable protocol layer lives in [`reference/`](reference/README.md):
[framing-crc](reference/framing-crc.md) ·
[cloud-login](reference/cloud-login.md) ·
[ble-transport](reference/ble-transport.md) ·
[auth-handshake](reference/auth-handshake.md) ·
[control-channel](reference/control-channel.md).

## Devices (device-specific)

Per-device details live under [`devices/`](devices/u200/README.md). Today:
[U200](devices/u200/README.md) — [gatt-map](devices/u200/gatt-map.md) ·
[operations](devices/u200/operations.md) · [validation](devices/u200/validation.md).

## Evidence

Every protocol claim is backed by sanitized proof indexed in
[`evidence/`](evidence/README.md). Raw captures are never committed.

---

Written in English, neutral in voice: it describes what was done and how, backed by
evidence. Nothing sensitive — no secrets, captures, or app source — ever enters the
repository (Constitution Principle I).
