# Contract: what the session requires of a transport

**Feature**: 007-session-flow-coverage · **Date**: 2026-08-14

`run_authenticated_lock_operation` takes `bleak_client: Any` and consumes it by
duck typing. This documents that implicit contract — the thing the fake must
honour, and the thing any real adapter must provide.

## Required — the unlock cannot run without these

| Member | Shape | Used for |
| --- | --- | --- |
| `start_notify(uuid, callback)` | async | Subscribing to each characteristic in `PRE_AUTH_NOTIFY_ORDER`. The callback is invoked as `callback(sender, bytearray)` |
| `stop_notify(uuid)` | async | Releasing them in the `finally`; exceptions suppressed |
| `write_gatt_char(uuid, data, response=False)` | async | Auth fragments and the encrypted control write |

A transport missing any of these fails the unlock. `start_notify` failures are
tolerated per characteristic (some adapters expose a subset).

## Optional — strictly best-effort

Probed with `getattr(client, name, None)`; absent means "skip silently", and any
exception raised is caught and ignored. They replicate what the phone's OS does
by itself.

| Member | Shape | Replicates |
| --- | --- | --- |
| `get_remote_le_features()` | async → int | HCI LE Read Remote Features |
| `request_mtu(size)` | async → int | ATT Exchange MTU |
| `read_by_type(uuid16)` | async → list[bytes] | GATT-caching preamble (0x2A01, 0x2B2A) |
| `write_by_type(uuid16, value)` | async | Client Supported Features (0x2B29) |
| `update_connection_parameters(interval_ms, latency, supervision_timeout_ms)` | async | LE Connection Update |

**Contract**: a client offering **none** of these completes an unlock
identically to one offering all of them, except for the extra exchanges. This is
what makes a plain `bleak` client usable, and it is asserted, not assumed.

## Observable order

```text
le_features? → mtu? → conn_update? → notify ff62,ff64,ff92,ff08
  → write auth 0x06 (public key)
  → [lock: empty ACKs…] → [lock: public key]
  → write auth 0x07 (verify data)
  → [lock: ACK 0x07]
  → write control (encrypted operation)
  → [lock: encrypted response, optional]
  → stop_notify ×4
```

Steps marked `?` are the optional capabilities. `read_by_type` /
`write_by_type` are attempted inside the preamble when present.

## Non-contract

The session never assumes a connection method, a disconnect method, MTU size, or
any bleak-specific type. It never inspects the client's class. That is what lets
one code path serve native bleak, the Bumble/ESP32 adapter, and this fake.
