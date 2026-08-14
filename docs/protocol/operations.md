# Lock operations — payload map

> Reverse-engineered by decrypting the AES-CCM control channel with the real
> session key and correlating each frame with an app action. Payloads are
> protocol opcodes, not secrets (Constitution Principles I & IV).

This layer turns a human intent into wire-ready command bytes and dispatches them
through a **caller-provided authenticated transport**. It never opens BLE, holds
keys, or encrypts — the session (feature 004) supplies the transport.

## Lock operation payloads

| Operation | Payload (hex) | Write prefix | Notes |
|-----------|---------------|--------------|-------|
| `UNLOCK` (open) | `74010100b917` | `0x01` | Real captured command — opened the bolt from our own session (feature 009). `0x74` = BLE_OPEN_LOCK, byte 1 `0x01` = open |
| `LOCK` (close) | `740002003a12` | `0x01` | Real captured command — byte 1 `0x00` = close |
| `KEEPALIVE` | `2f012f` | `0x01` | Status poll; the leading counter rotates |
| `STATE_SNAPSHOT` | `334e74746a201c00003049` | `0x01` | Extended state seen around control-page interactions |

The actuation opcode is `0x74` and byte 1 is the direction (`01` open / `00`
close). These were captured live from the app's `encryptAESCCM` input (feature
009) and replayed successfully. The values `1f031f` / `200320` shipped as
LOCK/UNLOCK before feature 009 were **never** the real actuators — the lock is
silent to them — and are retained in code only as clearly-marked legacy.

### Command builder

The frame is `74 <dir:1> <seq:2 LE> <trailer:2 LE>` where `dir` is `01` open /
`00` close and the trailer is **additive** (not a CRC): `trailer = base_dir + seq`,
`base_open = 0x17b8`, `base_close = 0x1238`. Cracked from nine live captures
(the trailer increments by 1 with the sequence). `build_operate_frame(open, seq)`
synthesises any command; `UNLOCK`/`LOCK` are the `seq=1` case. The lock ignores
the sequence across sessions, so `seq=1` per fresh session is fine. The bases were
derived from one device and may be device-specific. See `specs/009-lock-open-spike`.

Each operation is sent encrypted:
`control_write = write_prefix + AES-CCM(sessionKey, nonce, payload)` (the crypto is
feature 004). This layer produces the `payload` and `write_prefix`.

### Intent aliases

Intents are case-insensitive and accept common English/Spanish aliases:

| Canonical | Aliases |
|-----------|---------|
| `KEEPALIVE` | keepalive, keep-alive, heartbeat |
| `LOCK` | lock, bloquear, cerrar |
| `UNLOCK` | unlock, desbloquear, abrir |
| `STATE_SNAPSHOT` | snapshot, state-snapshot, estado |

Unknown intents raise a clear error rather than guessing.

## Voice / alert volume

Volume presets map to captured control requests (feature 002 framing:
kind|command|body|trailer):

| Preset | Aliases | Serialized request (hex) |
|--------|---------|--------------------------|
| `MEDIUM` | medium, medio | `01 d3 02d13e15 d5fddfe4` |
| `HIGH` | high, alto | `01 d3 02d23e16 5faddd09` |

`build_voice_volume_write(preset).bytes` returns the serialized `ControlRequest`;
`set_voice_volume(transport, preset)` writes those bytes through the transport.

## Transport ports

Two minimal caller-provided interfaces keep this layer decoupled from BLE:

- `SessionOperationTransport.send_plaintext_operation(payload: bytes)` — for lock
  operations, where the session applies AES-CCM before writing.
- `ControlWriteTransport.write(payload: bytes)` — for already-authenticated
  control bytes.

Both are satisfied by the BLE session (feature 004) or the end-to-end flow
(feature 005).
