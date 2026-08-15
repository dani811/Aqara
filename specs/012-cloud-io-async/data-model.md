# Data Model: Cloud I/O Async-Safe

**Feature**: 012 - Cloud I/O Async-Safe

**Date**: 2026-08-15

## Key Entities & State

### 1. OperationInProgressError

**Type**: Exception (new)

**Purpose**: Raised when `run_authenticated_lock_operation()` is called while an operation is already in progress on the same lock device.

**Fields**:
- `message: str` — User-friendly message: "Another lock operation is in progress; wait for it to complete or cancel it"
- `device_id: str` — The lock device ID (optional, for debugging)
- `__cause__: Exception | None` — None (this is a raised error, not a wrap)

**Lifecycle**:
1. Raised immediately when second concurrent call detected
2. Caller catches and handles (e.g., queues retry, displays error to user)
3. Does not modify session state (fail-fast)

**Validation Rules**:
- Must be a new exception class inheriting from `RuntimeError` or `asyncio.InvalidStateError`
- Must be importable from `aqara_u200_ble` (public API)

---

### 2. Session State (Enhanced)

**Type**: Internal state tracker (implicit in `run_authenticated_lock_operation()`)

**Purpose**: Track whether an operation is currently in progress for a given lock device.

**State Variables**:
- `_operation_in_progress: bool` — True if a call to `run_authenticated_lock_operation()` is executing; False otherwise
- Scope: Per lock device (per coroutine context? or global with device tracking?)

**Lifecycle**:
1. Set to False on entry (after checking if already True)
2. Set to True immediately after entry check
3. Set to False in finally block (cleanup guaranteed)

**Validation Rules**:
- **Concurrency model**: Each lock device can have at most one active `run_authenticated_lock_operation()` call
- **No state leakage**: If exception raised, flag must still reset (use `try`/`finally`)

**Note**: The spec clarification says "allow concurrency per different locks". This means we need a way to track which locks have operations in progress. Implementation options:
- Option A: Use a per-device lock (lock.id as key in a global dict)
- Option B: Use an async.Lock per device (more idiomatic)
- Option C: Simple flag if only one device in typical usage (simplest; HA usually controls one lock at a time)

**Recommendation**: Option B (async.Lock per device ID) is most robust and future-proof.

---

### 3. Cloud Call Context (Logging)

**Type**: Internal context for DEBUG logging

**Purpose**: Provide timing and phase information for diagnostics without leaking secrets.

**Fields**:
- `phase: str` — Current phase ("get_public_key" | "get_session_material" | "control_write")
- `start_time: float` — time.time() or similar
- `duration_ms: float` — Computed on log write

**Example Log Entry** (DEBUG level):
```
[BLE] cloud_get_public_key started (thread=WorkerThread-3)
[BLE] cloud_get_public_key completed in 2340ms
```

**Validation Rules**:
- No device_id, auth_headers, public keys, session keys logged
- Duration logged only if > threshold (e.g., > 1 second) to highlight slow calls
- Thread ID logged for correlation with other DEBUG output

---

## State Transitions

```
Initial State (no operation)
    ↓
[call run_authenticated_lock_operation]
    ↓
Check: _operation_in_progress[device_id] == True?
    ├─ YES → raise OperationInProgressError
    │
    └─ NO → Set _operation_in_progress[device_id] = True
           ↓
        [MTU request, CCCD enable, etc.]
           ↓
        [Spawn cloud call in worker thread via asyncio.to_thread]
           ↓
        [Await worker thread result]
           ↓
        [BLE control write, control response read]
           ↓
        [finally] Set _operation_in_progress[device_id] = False
           ↓
        Return (SessionMaterial, LockOperationWrite, response_hex)
```

---

## Storage & Lifecycle

**Scope**: Session-local (per call to `run_authenticated_lock_operation()`)

**Persistence**: None (ephemeral state for the duration of the operation)

**Cleanup**: Guaranteed by `finally` block in `run_authenticated_lock_operation()`

---

## No Data Models Exposed

This feature does **not** introduce new data models visible to users. All state changes are internal to `run_authenticated_lock_operation()`:
- Cloud calls are already happening (just moved to threads)
- SessionMaterial, LockOperationWrite, etc. are unchanged
- Return types unchanged

The new `OperationInProgressError` exception is the only public addition.
