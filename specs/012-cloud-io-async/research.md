# Research & Design Decisions: Cloud I/O Async-Safe

**Feature**: 012 - Cloud I/O Async-Safe

**Date**: 2026-08-15

## Decision 1: Threading Mechanism for Cloud I/O

**Decision**: Use `asyncio.to_thread()` for offloading cloud calls.

**Rationale**:
- Available in Python 3.9+; project targets Python 3.10+
- Built-in asyncio primitive; no external dependencies required
- Simple API: `await asyncio.to_thread(sync_func, *args, **kwargs)`
- Automatically manages executor lifecycle; no manual thread pool management
- Integrates seamlessly with asyncio exception handling and cancellation

**Alternatives Considered**:
- **ThreadPoolExecutor + loop.run_in_executor()**: Manual thread pool management; more control but more boilerplate
- **Create a dedicated thread pool**: Premature optimization; `asyncio.to_thread()` default pool is sufficient for cloud calls (typically 5 concurrent calls max)
- **Rewrite cloud helpers to be async (e.g., aiohttp)**: Out of scope; urllib migration is a separate feature
- **Use multiprocessing**: Overkill for I/O-bound operations; adds serialization overhead

**Status**: ✅ Confirmed

---

## Decision 2: Concurrency Control Strategy

**Decision**: Reject concurrent operations on the same lock device with `OperationInProgressError`.

**Rationale**:
- The lock device cannot authentically handle multiple simultaneous authentication flows
- Each BLE session is tied to unique ephemeral public key exchange
- Rejecting concurrency is simpler than queueing internally and aligns with lock device reality
- Allows the caller (Home Assistant) to implement its own serialization strategy
- Concurrent operations against *different* locks remain allowed

**Alternatives Considered**:
- **Internal queuing**: Would hide concurrency issues from the caller; harder to reason about ordering
- **Silent override**: Dangerous; could lead to race conditions or duplicate auth frames
- **Caller responsibility only (no enforcement)**: Risk of silent failures; better to fail fast

**Status**: ✅ Confirmed

---

## Decision 3: Error Handling & Retry Policy

**Decision**: No automatic retries; cloud failures immediately abort the session.

**Rationale**:
- Once a cloud call fails, the session is in an undefined state (auth frame may or may not have been sent)
- Transparent retry would risk sending duplicate control frames if the first succeeded but was lost in transit
- The caller (Home Assistant) has better visibility into the failure context and can decide whether to retry
- Fail-fast provides immediate feedback; better UX than silent retries that mask transient issues

**Alternatives Considered**:
- **Exponential backoff**: Increases latency on transient errors; hides failure reason from caller
- **Simple retry (N times)**: Still adds latency; doesn't address the duplicate-frame risk
- **Retry only on specific errors (e.g., timeout)**: Complex logic to classify "retryable" errors; error handling at the boundary is fragile

**Status**: ✅ Confirmed

---

## Decision 4: Observability & Logging Strategy

**Decision**: DEBUG-level logging only; successful operations logged at DEBUG; failures communicated via typed exceptions.

**Rationale**:
- Avoids log spam in production (DEBUG disabled by default)
- Exceptions are the primary error signal; logging errors would duplicate information
- DEBUG logging enables diagnostics when enabled (thread transitions, slow calls, operation phases)
- Strict secret protection prevents accidental credential leakage
- Home Assistant has its own logging system; the library provides signals (exceptions), not noise

**Alternatives Considered**:
- **Detailed logging of all calls**: Risk of credential leakage; verbose output in production
- **Error logging only**: Misses valuable timing/diagnostic info; can't correlate phases without DEBUG
- **No logging (caller's responsibility)**: Reduces library observability; harder to debug HA integration issues

**Status**: ✅ Confirmed

---

## Decision 5: Exception Handling & Context Preservation

**Decision**: Cloud exceptions propagate immediately without wrapping; original exception type and message preserved.

**Rationale**:
- Caller can differentiate exception types (network vs. auth vs. API error) and handle accordingly
- No exception wrapping; minimal overhead
- `asyncio.to_thread()` naturally preserves exception context via `raise` in worker thread
- Simplest implementation; caller gets full traceback

**Alternatives Considered**:
- **Wrap in a custom exception**: Hides original exception details; harder to debug
- **Swallow exceptions and return error tuples**: Non-idiomatic Python; caller must check return type

**Status**: ✅ Confirmed

---

## Decision 6: BLE State During Cloud I/O

**Decision**: BLE connection and CCCD subscriptions remain active while cloud calls are in flight on worker threads.

**Rationale**:
- Cloud calls are independent of BLE transport
- If BLE connection drops mid-cloud-call, the cloud call continues (worker thread is decoupled)
- Lock device can send control frames during cloud phase (though unlikely)
- Cleanup (stop_notify) is tolerant of already-disconnected state

**Alternatives Considered**:
- **Pause CCCD subscriptions during cloud calls**: Unnecessary complexity; BLE and cloud are orthogonal
- **Cancel cloud calls if BLE disconnects**: Would require shared state and synchronization; out of scope

**Status**: ✅ Confirmed

---

## Technical Context Summary

| Aspect | Decision |
|--------|----------|
| **Threading** | `asyncio.to_thread()` |
| **Concurrency** | Reject on same device; allow on different devices |
| **Retries** | No automatic retries; fail fast |
| **Logging** | DEBUG-level only; typed exceptions for errors |
| **Exception Handling** | Propagate without wrapping |
| **BLE State** | Independent of cloud I/O |

All technical decisions are **confirmed** and **low-risk**. No unknowns remain.
