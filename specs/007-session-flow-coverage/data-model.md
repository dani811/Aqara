# Phase 1 Data Model: Verifiable unlock choreography

**Feature**: 007-session-flow-coverage · **Date**: 2026-08-14

No persisted data and no new public type. The model is the fake lock, the script
that configures it, and the record it keeps.

## Entities

### `FakeLockClient` (test double)

Implements the transport surface the session consumes (see
[contracts/transport-surface.md](./contracts/transport-surface.md)) and plays the
lock's side of the exchange.

| Field | Meaning |
| --- | --- |
| `notify_callbacks` | uuid → callback stored by `start_notify` |
| `events` | ordered `list[str]` — the exchange record |
| `written_frames` | ordered `list[bytes]` of reassembled auth frames |
| `control_writes` | ordered `list[bytes]` written to the control characteristic |
| `script` | the `LockScript` driving its answers |
| `_auth_buffer` | fragments received since the last complete frame |

**Behaviour**: on a write to the auth characteristic it buffers fragments until
the terminator, reassembles, and answers per the script. On a write to the
control characteristic it optionally answers an encrypted response.

### `LockScript` (scripted answer set)

| Field | Default | Effect |
| --- | --- | --- |
| `empty_acks_before_key` | `0` | how many bodyless `0x06` frames precede the public key |
| `send_public_key` | `True` | whether the key ever arrives (`False` exercises the endless-ACK failure) |
| `verify_ack_frame_type` | `0x07` | the kind answered to the verify frame (`0x06` exercises the mismatch error) |
| `control_response` | a payload | `None` = no answer (timeout path); short bytes = truncated-response path |
| `optional_capabilities` | `"none"` | `none` \| `present` \| `failing` — how the low-level extras behave |

### Exchange record

The `events` list, appended in real order. Vocabulary:

```text
notify:ff62 · notify:ff64 · notify:ff92 · notify:ff08   (subscriptions enabled)
mtu · read_by_type:2a01 · write_by_type:2b29 · conn_update · le_features
write:auth · write:control
stop_notify:ff62 · …                                     (subscriptions released)
```

**Validation rules asserted against it**:

1. The four `notify:*` entries appear in `PRE_AUTH_NOTIFY_ORDER` and before any
   `write:*`.
2. `write:auth` (public key) precedes `write:auth` (verify) precedes
   `write:control`.
3. Every `notify:X` has a matching `stop_notify:X`, on success and on failure.

## State transitions of the fake

```text
                  write:auth(0x06)          write:auth(0x07)        write:control
   idle ──────────────────────────► keyed ──────────────────────► verified ─────────► done
                │  answers N empty ACKs,          │ answers an ACK          │ optionally
                │  then the 65-byte key           │ of the scripted kind    │ answers an
                │  (or never, per script)         │                         │ encrypted frame
                └── script.send_public_key = False keeps it in `idle`,
                    which the session reports as "no public key received"
```

## Relationships

`FakeLockClient` is consumed by `run_authenticated_lock_operation` exactly as a
`bleak` client or `BumbleGattAdapter` would be. It builds its answers with
`build_auth_message` / `fragment_auth_message` (feature 004) and its control
response with `encrypt_control_payload` (feature 004), using throwaway fixtures.
