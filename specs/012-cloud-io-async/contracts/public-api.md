# Public API Contract: Cloud I/O Async-Safe

**Feature**: 012 - Cloud I/O Async-Safe

**Date**: 2026-08-15

**Audience**: Consumers of `aqara_ble` library (Home Assistant, CLI tools, scripts)

---

## Backward Compatibility

✅ **100% backward compatible**

The existing public function signature for `run_authenticated_lock_operation()` **does not change**:

```python
async def run_authenticated_lock_operation(
    *,
    client: GattClient,  # Renamed from bleak_client in feature 011
    device_id: str,
    auth_headers: dict[str, str] | None,
    region: str,
    base_url: str | None,
    operation: LockOperation | str,
    notify_timeout: float = 8.0,
    signer: Any = None,
) -> tuple[SessionMaterial, LockOperationWrite, str | None]:
    """Authenticate with lock, send command, return session material & response."""
```

**No changes to**:
- Parameter names (except `client`, already changed in feature 011)
- Return type
- Return value semantics
- Documented exceptions (except new `OperationInProgressError`)
- Wire bytes or protocol behavior

---

## New Public Exception

### OperationInProgressError

**Type**: `asyncio.InvalidStateError` or `RuntimeError` subclass

**Raised When**: `run_authenticated_lock_operation()` is called while another call is already in progress for the same lock device.

**Usage**:

```python
from aqara_ble import OperationInProgressError, run_authenticated_lock_operation

try:
    material, write, response = await run_authenticated_lock_operation(
        client=my_client,
        device_id="device-123",
        # ... other args
    )
except OperationInProgressError as e:
    print(f"Operation already in progress: {e}")
    # Caller may retry after the first operation completes
    # or implement its own queueing/serialization strategy
```

**Attributes**:
- `str(e)` — Human-readable message
- `e.__cause__` — None (not a wrapped exception)

**Handling Strategy**:
- Caller should wait for the first operation to complete, then retry
- Or caller implements its own async queue/lock to serialize operations
- Different lock devices can have concurrent operations

---

## Internal Changes (Not Public)

The following changes are **internal implementation details** not exposed to consumers:

1. ✅ Cloud calls (`cloud_get_public_key`, `get_session_material`) are executed in worker threads via `asyncio.to_thread()`
2. ✅ No automatic retries for cloud failures (already captured by existing exception handling)
3. ✅ DEBUG-level logging added (controlled by environment variable; no public API change)
4. ✅ Concurrency tracking added (per-device flag; not exposed)
5. ✅ Exception context preserved (already true; no change)

---

## Stability Guarantees

| Aspect | Guarantee |
|--------|-----------|
| **Function signature** | Stable (unchanged from feature 011) |
| **Return type** | Stable (unchanged) |
| **Return semantics** | Stable (unchanged) |
| **Exception types** | Stable + one new (OperationInProgressError) |
| **Wire bytes** | Stable (unchanged) |
| **Cryptography** | Stable (unchanged) |
| **Protocol behavior** | Stable (unchanged) |
| **Responsiveness** | **Improved** (event loop no longer blocked by cloud I/O) |

---

## Migration Guide for Consumers

### Home Assistant Integration

**Before** (would have blocked event loop):
```python
# This could stall the entire HA event loop during cloud I/O
material, write, response = await run_authenticated_lock_operation(
    client=bleak_client,
    device_id=device_id,
    # ...
)
```

**After** (event loop remains responsive):
```python
# Same call, but now:
# - Cloud I/O runs in a worker thread
# - Event loop remains responsive to other tasks
# - If called concurrently, raises OperationInProgressError

try:
    material, write, response = await run_authenticated_lock_operation(
        client=bleak_client,
        device_id=device_id,
        # ...
    )
except OperationInProgressError:
    # Handle concurrent call; retry or queue
    pass
```

### CLI Tools

No changes required. Cloud I/O is now async-safe but remains synchronous from the caller's perspective.

---

## No Public Additions Except Exception

- ✅ No new classes (except `OperationInProgressError`)
- ✅ No new functions
- ✅ No new parameters
- ✅ No new return types
- ✅ No changes to `SessionMaterial`, `LockOperationWrite`, or other public types
- ✅ No configuration requirements
