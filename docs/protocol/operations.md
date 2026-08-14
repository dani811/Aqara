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
| `LOCK` | `1f031f` | `0x03` | Close — confirmed (first captured press) |
| `UNLOCK` | `200320` | `0x03` | Open — confirmed (second captured press) |
| `KEEPALIVE` | `2f012f` | `0x01` | Status poll; the middle counter rotates |
| `STATE_SNAPSHOT` | `334e74746a201c00003049` | `0x01` | Extended state seen around control-page interactions |

The middle byte is the opcode. `1f031f` was historically mislabeled as unlock; it
is **LOCK**. The `UNLOCK_CANDIDATE` alias is retained pointing at the old value but
is clearly marked so the two are never confused.

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
