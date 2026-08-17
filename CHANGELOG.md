# Changelog

All notable changes to aqara-u200-ble are documented in this file.

## [0.4.0] — Feature 016: device model identification over the air (2026-08-17)

### Added
- `ScanCandidate` now exposes `manufacturer_payload`, `product_id` and `model`,
  decoded from the Aqara (`0x0B27`) advertisement — recognise the model (e.g.
  "U200", product id `0x9C03`) without connecting. `aqara_u200_ble.models`
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
  - Exported from public API (`aqara_u200_ble.OperationInProgressError`)

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
from aqara_u200_ble import run_authenticated_lock_operation, OperationInProgressError

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
