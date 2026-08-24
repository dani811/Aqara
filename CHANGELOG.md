# Changelog

All notable changes to aqara-ble are documented in this file.

## [1.3.0] — Real-time state streaming + low-power hold (2026-08-24)

### Added
- `U200Client.listen(seconds, on_state=cb, low_power=True)` streams the real bolt
  position via a callback in real time (fires per ff62 report), and can request
  **low-power connection parameters** (slow interval + slave latency) so a HELD
  state-listening session costs little lock battery. `run_authenticated_lock_operation`
  gains `low_power_connection`.

### Why
- Enables a persistent, real-time state session (yalexs_ble style) that catches
  external changes (Matter/key/keypad) without the per-window reconnect churn —
  one held low-power connection instead of many fast reconnects.

## [1.2.0] — Real lock state from the ff62 report channel (2026-08-24)

### Added
- **Real bolt position** decoded from the spontaneous ff62 report channel:
  `decode_state_report()` (first byte `0x1d` = locked, `0xdd` = unlocked,
  `0x15` = heartbeat). CONFIRMED live against a real lock, including manual
  key/keypad operations.
- `U200Client.operate(op, listen_after=<s>)` now keeps the session open after
  the command and returns the real observed position in
  `OperationResult.observed_locked` — a consumer gets true state, not a guess.

### Why
- Consumers (e.g. Home Assistant) can now show the actual locked/unlocked state
  read from the lock over BLE, and confirm an actuation really happened, instead
  of an optimistic assumption. Groundwork for a persistent-session real-time
  state sensor (yalexs_ble style).

## [1.1.0] — Account + password only, device id auto-resolved (2026-08-23)

### Changed
- `CloudAuthManager` now needs only **account + password** (+ optional region).
  The app-global `appid`/`appkey` default to baked constants and
  `client_id`/`phone_id` are generated per install (new `aqara_ble.app_constants`).
  All four remain optional keyword args to override with captured values.
  Confirmed live: login succeeds with baked app ids + random phone/client ids.

### Added
- **Cloud device inventory (feature 016)**: `cloud_list_devices()` (`POST /dev/query`)
  and `CloudAuthManager.list_devices()` / `resolve_device_id(mac=…)`. A consumer no
  longer needs the lock's `matt.<…>` DID: a single registered device resolves
  directly, and several are disambiguated by matching the BLE MAC via
  `cloud_device_mac()`. Confirmed live: `resolve_device_id()` returns the correct
  DID from only an account + password.

### Why
- Consumers (e.g. Home Assistant) should ask a user only for their Aqara account
  and password — never for `appid`/`appkey`/`client_id`/`phone_id` or the opaque
  `device_id`, none of which a normal user can obtain. Backward compatible: passing
  any value explicitly still works.

## [1.0.0] — First stable release (2026-08-23)

### Summary
- First stable, PyPI-distributable release of the autonomous Aqara U200 BLE
  control library. The public API (`U200Client` facade, `CloudAuthManager`,
  the transports, and the lower-level KDF/framing/session pieces) is now
  considered stable under semantic versioning.

### Confirmed live
- Actuation validated end-to-end against a real U200 (login → scan → connect →
  operate): `unlock` (`0x74` dir `01`) retracts the pestillo — a full open —
  and `lock` (dir `00`) closes; `state` keepalive (`0x2f`) reads without moving
  the bolt. There is no separate "open without latch" command.

### Notes
- Cloud I/O is async-safe: blocking cloud calls run off the event loop via
  `asyncio.to_thread`, so the facade is usable directly from async hosts
  (e.g. Home Assistant).
- Real-time bolt position / spontaneous events remain provisional (`LockState`
  decoded fields stay `None` until confirmed); the `listen` window is the
  groundwork for it.
- Packaging metadata carries no personal identifying information.

## [0.9.0] — Feature 023: post-command listen window (spontaneous state/events) (2026-08-17)

### Added
- `run_authenticated_lock_operation(..., listen_after=<seconds>, on_report=cb)` —
  after the command's first response, keep the connection open and forward every
  extra frame (control ff62 decrypted; report ff64/ff92 raw) to `on_report` until
  the window expires. Default `0.0` = exact prior behaviour (byte-identical actuator).
- `U200Client.listen(seconds)` (non-actuating keepalive + window) and `aqara listen
  --seconds N` — the diagnostic to see whether the lock reports position/events
  after the ACK or on a manual/keypad operation.

### Why
- keepalive/operate/state_snapshot ACKs, bare status opcodes, and the ff64/ff92
  channels are all silent in the one-shot window (verified live). The lock likely
  reports state/events shortly after actuation or on manual use — only observable
  by staying connected and listening, which this adds. Groundwork for real-time
  state in Home Assistant.

## [0.8.0] — Feature 022: capture the ff64/ff92 report channels (2026-08-17)

### Added
- The auth flow now logs frames from the report channels ff64 (CONTROL_NOTIFY2)
  and ff92 (AUX_NOTIFY) under `U200_DEBUG`, instead of discarding them. These
  carry the lock's REPORT_* pushes — a diagnostic to learn whether the lock
  reports state/position/events spontaneously.

### Notes
- Diagnostic only: protocol/actuator path unchanged (the channels were already
  subscribed). Groundwork for the spontaneous-events / persistent-session feature.

## [0.7.0] — Feature 021: read-only status-query probe (2026-08-17)

### Added
- `U200Client.query(sub_cmd, data=b"")` and `build_control_query_write()` — send a
  generic control opcode through the authenticated session and get its decrypted
  response as a `LockState(source="query")`. For probing catalogued **status**
  opcodes (keepalive/operate/state_snapshot ACKs proved static and position-blind).
- `aqara query <name>` CLI — restricted to a read-only whitelist (lock_status
  0x07, door_lock_status 0xE5, report_lock_status 0x15, battery 0x4F, …); `SET_*`
  opcodes are never sendable from the CLI.

### Guarantees
- Actuator path (lock/unlock) is byte-identical — the change is an opt-in
  passthrough of a pre-built `LockOperationWrite`. Protocol unchanged. 219 tests.

### Notes
- Query opcodes are **unconfirmed** probes (payload guessed as the bare opcode).
  If none reports position, real-time state needs spontaneous events (persistent
  session, future feature).

## [0.6.0] — Feature 019: lock state reading (2026-08-17)

### Added
- **`LockState`** + `decode_lock_state()` (`aqara_ble.lock_state`): a typed,
  honest snapshot of the lock — `raw_hex` is always exposed; decoded fields
  (`locked`, `battery_percent`) stay `None` until confirmed by captured evidence.
- **`U200Client.status()`** — reads state via the confirmed read-only keepalive
  poll (never sends an unconfirmed status opcode, never actuates). `OperationResult.state`
  exposes an operation's response as a `LockState`.
- **`aqara state`** CLI subcommand.

### Notes
- Decode of the response bytes is intentionally provisional pending labelled
  captures (see docs/devices/u200/validation.md). Spontaneous event reports are a
  known limit — they need a persistent session (future feature). Protocol unchanged.

## [0.5.0] — Home Assistant-consumable release (2026-08-17)

First tagged, pin-able release for downstream integrations. Pin in Home
Assistant's `manifest.json` requirements as `aqara-ble==0.5.0`. Bundles
features 012–017 (async-safe cloud I/O, operation catalogue, autonomous login,
client facade, over-the-air model id, packaged `aqara` CLI).

### Fixed (async line, requested by dani811/haos_aqara)
- **#3**: `_run_cloud_phase` DEBUG telemetry now reports the actual **worker**
  thread id (was logging the event-loop thread after the await).
- **#2**: the event-loop responsiveness test now enforces the ≥80% completion
  criterion (was `> 0`, i.e. 20%), threshold derived from the task count.
- Corrected `[project.urls]` to the canonical repository.

### Included since 0.2.0 — Feature 017: packaged `aqara` CLI

### Added
- **`aqara` console command** (`aqara_ble.cli:main`, `[project.scripts]`): a
  thin adapter over the public API — `login`, `scan`, `lock`, `unlock`,
  `operate <op>`, `--transport bleak|bumble`. All logic lives in the library.

### Changed
- `examples/lock_cli.py` is now a compat shim delegating to `aqara_ble.cli`.

### Guarantees
- `import aqara_ble` stays pure — it does not import `cli`/`argparse` nor read
  the environment (tested). Integrations couple to the same public API the CLI uses.
- Protocol/wire bytes unchanged; the CLI holds no protocol/network/BLE logic.

## [0.4.0] — Feature 016: device model identification over the air (2026-08-17)

### Added
- `ScanCandidate` now exposes `manufacturer_payload`, `product_id` and `model`,
  decoded from the Aqara (`0x0B27`) advertisement — recognise the model (e.g.
  "U200", product id `0x9C03`) without connecting. `aqara_ble.models`
  (`decode_manufacturer_payload`, `MODEL_BY_PRODUCT_ID`).
- `examples/lock_cli.py scan` prints the model per candidate.
- `tools/probe_cloud_endpoints.py` — read-only discovery of the account
  device-inventory cloud endpoint (user-run; sanitized dumps under `captures/`).

### Notes
- Cloud `list_devices()` is deferred until the inventory endpoint is captured
  (the probe tool gathers the evidence). Protocol/wire bytes unchanged.

## [0.3.0] — Feature 015: client facade, transports, ESP32-S3 controller (2026-08-17)

### Added
- **`U200Client`** — the facade: `await U200Client.connect(auth=, transport=, device_id=, mac=None)`
  runs login → scan/identify → connect/discover; `lock()`, `unlock()`, `operate(name)`,
  `close()`, `async with`. `from_gatt()` wraps an already-connected client.
- **`Transport`** contract with two packaged implementations: `BleakTransport` (host
  Bluetooth; discovery restricted to the U200 services — the CoreBluetooth fix) and
  `BumbleTransport(port)` (external HCI controller; phone-like connection params, never pairs).
- **Scan identification**: `scan()` now *returns* `ScanCandidate`s with `reasons`
  (`name`/`service`/`manufacturer`/`mac`) and `score`; `select_preferred()` never picks a
  manufacturer-only device; `identify_candidate()`.
- **Errors by phase**: `FlowPhase`, `U200ClientError`, `NoDeviceFoundError`, `AmbiguousDeviceError`.
- **`tools/esp32s3_hci_usb/`** — ESP-IDF firmware turning an ESP32-S3 into a BLE HCI controller
  over its USB-Serial-JTAG port (H4), with build/erase/flash recipe; `tools/hci_smoke.py`.
- **`examples/lock_cli.py`** — the single real-hardware runner (`scan|lock|unlock|operate`).

### Removed
- `tools/bumble_lock.py`, `examples/real_lock_unlock.py`, `examples/run_real_lock_unlock.py`
  (hand-wired flows superseded by the facade + `lock_cli.py`).

### Unchanged
- Protocol bytes, CRC, AES-CCM, CCCD order, cloud login/refresh: the facade only composes
  existing pieces (guarded by a byte-equality test against the direct session call).

## [Feature 012] - Cloud I/O Async-Safe (2026-08-15)

### Added
- **New exception type**: `OperationInProgressError`
  - Raised when `run_authenticated_lock_operation()` is called while another operation is in progress on the same device
  - Enables fail-fast concurrency control (non-blocking)
  - Exported from public API (`aqara_ble.OperationInProgressError`)

### Changed
- **Cloud I/O now async-safe**:
  - `cloud_get_public_key()` and `get_session_material()` execute in worker threads via `asyncio.to_thread()`
  - Event loop remains responsive during cloud delays (2-5 seconds typical)
  - No blocking on Home Assistant event loop during lock operations

- **Concurrency control**: Per-device fail-fast rejection
  - Multiple calls to same device return `OperationInProgressError` immediately
  - Different devices can operate concurrently
  - Flag is automatically reset on completion (success, failure, or cancellation)

### Behavior
- **Backward compatible**: Public API signature unchanged
  - All existing callers continue to work without modification
  - Return types and semantics preserved
  - Wire bytes and protocol unchanged

- **Exception propagation**: Cloud failures propagate unwrapped
  - Original exception type preserved (e.g., `CloudError` stays `CloudError`)
  - Exception message intact for debugging
  - No wrapping or suppression

- **Security**: No secrets in logs (FR-008 compliant)
  - Session keys, nonces, verify data never logged
  - DEBUG-level logging only for structured metadata (phase, duration, context)
  - All error paths validated for secret leakage

### Tests
- **140 total tests** passing (115+ new async boundary tests)
  - Cloud I/O executes in worker threads (thread ID verification)
  - Event loop responsiveness validated (≥80% concurrent tasks complete)
  - Exception propagation validated
  - Cleanup guaranteed (concurrency flag reset, notifications unsubscribed)
  - No secrets in logs (sensitive pattern scan)
  - Backward compatibility verified (signature, return types, wire bytes)
  - Type checking (mypy) passes
  - Linting (ruff) passes

### Migration
No migration required. Existing code continues to work unchanged. To handle `OperationInProgressError`:

```python
from aqara_ble import run_authenticated_lock_operation, OperationInProgressError

try:
    material, write, response = await run_authenticated_lock_operation(
        client=client,
        device_id="device-123",
        # ... other args
    )
except OperationInProgressError:
    # Another operation in progress on this device
    # Either: wait for first to complete, queue, or retry
    pass
```

### Performance
- Cloud I/O latency: Unchanged (still 2-5 seconds typical network delay)
- Event loop latency: **Improved** (never blocked by cloud I/O)
- BLE choreography: Unchanged (<500ms protocol-driven)
- Concurrency check: Fail-fast, O(1) dict lookup

### Internal Notes
- **Concurrency tracking**: `_device_operation_in_progress: dict[str, bool]`
- **Cloud execution**: Worker threads via `asyncio.to_thread()` (Python 3.9+)
- **Cleanup guarantee**: Structured try/finally ensures flag release independent from BLE cleanup
