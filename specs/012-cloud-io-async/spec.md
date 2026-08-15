# Feature Specification: Cloud I/O Async-Safe

**Feature Branch**: `012-cloud-io-async`

**Created**: 2026-08-15

**Status**: Clarified

**Context**: Issue #1 - Make authenticated BLE session cloud I/O async-safe for Home Assistant

## Clarifications

### Session 2026-08-15

- Q: What should occur if `run_authenticated_lock_operation()` is called concurrently from multiple coroutines? → A: Reject concurrent operations with `OperationInProgressError`; allow concurrency per different locks.
- Q: Should there be automatic retries if cloud calls fail? → A: No automatic retries; cloud failures immediately abort session. Transparent retries would risk duplicate control frames. Caller may implement its own retry policy.
- Q: What observability/logging is required for cloud I/O? → A: DEBUG-level logging only; log successful operations (phase, duration) and failures via typed exceptions. No credentials, headers, session material, or secrets logged. Thread transitions and slow-call timing for diagnostics.

## Overview

`run_authenticated_lock_operation()` is an async BLE choreography that handles the complete authentication and control flow for the Aqara U200 smart lock via Bluetooth. However, it currently calls two synchronous cloud helper functions directly:
- `cloud_get_public_key()` — fetches the lock's public key from Aqara cloud
- `get_session_material()` — derives session keys from the lock's ephemeral public key

These cloud helpers perform blocking network I/O via `urllib` (HTTP requests). This is acceptable for the standalone CLI tool, but it blocks Home Assistant's asyncio event loop when the library is used by `haos_aqara`, preventing other Home Assistant tasks from running concurrently.

## User Scenarios & Testing

### User Story 1 — Home Assistant Lock Integration (Priority: P1)

A Home Assistant user installs the `haos_aqara` custom component to control their Aqara U200 smart lock via Home Assistant. When the user sends a lock/unlock command from Home Assistant's UI, the `run_authenticated_lock_operation()` function is called to execute the command on the device.

**Current problem**: The blocking cloud I/O stalls Home Assistant's event loop for 2-5 seconds, preventing other automations, sensors, and integrations from responding until the cloud calls complete.

**Why this priority**: Without this fix, Home Assistant becomes unresponsive during lock operations, making the integration unusable in production.

**Independent Test**: Can run lock/unlock operations concurrently with other Home Assistant tasks without blocking. Verify by scheduling lightweight async tasks alongside a lock operation and confirming they complete despite the cloud I/O latency.

**Acceptance Scenarios**:

1. **Given** Home Assistant is running with `haos_aqara` installed, **When** a lock operation is triggered, **Then** other Home Assistant tasks (sensors, automations) continue executing concurrently without blocking.
2. **Given** the cloud API is slow (2+ second response time), **When** a lock operation is in progress, **Then** the asyncio event loop remains responsive to other coroutines.

---

### User Story 2 — Exception Propagation (Priority: P1)

When a cloud call fails (network timeout, authentication error, API error), the error is properly propagated to the caller with full context, allowing Home Assistant to handle the failure gracefully.

**Why this priority**: Error handling is critical for reliability. Silent failures or lost exception context would make debugging integration issues extremely difficult.

**Independent Test**: Inject a fake cloud helper that raises an exception. Verify the exception propagates correctly and can be caught by the caller without loss of context.

**Acceptance Scenarios**:

1. **Given** `cloud_get_public_key()` raises an exception, **When** `run_authenticated_lock_operation()` is awaited, **Then** the exception propagates to the caller with the original exception type and message intact.
2. **Given** `get_session_material()` raises an exception, **When** `run_authenticated_lock_operation()` is awaited, **Then** the exception propagates correctly and the BLE connection is cleaned up.

---

### User Story 3 — Backward Compatibility (Priority: P1)

Existing code that calls `run_authenticated_lock_operation()` continues to work without modification. The public function signature and return type remain unchanged.

**Why this priority**: Existing tests and tools must continue to work. Breaking changes require coordinated updates across multiple repositories.

**Independent Test**: Run all existing tests without modification. Verify 100% test pass rate.

**Acceptance Scenarios**:

1. **Given** existing code calls `run_authenticated_lock_operation(client=..., device_id=..., ...)`, **When** the function is invoked, **Then** it returns `(SessionMaterial, LockOperationWrite, str|None)` as before.
2. **Given** all existing tests run against the modified code, **When** tests execute, **Then** all pass without modification.

---

### Edge Cases

- **Concurrent operations**: If `run_authenticated_lock_operation()` is called concurrently from multiple coroutines against the same lock, reject with `OperationInProgressError`. Concurrent operations against different locks remain allowed.
- **Cloud timeout**: If a cloud call times out, the exception is propagated immediately. The session is aborted. No automatic retries.
- **Network disconnection during cloud call**: If the network disconnects while a cloud call is pending, the exception propagates. Session is aborted.
- **BLE disconnection during cloud call**: If the BLE connection is lost while a cloud call is in progress on a worker thread, the cloud call continues to completion (worker thread is independent). Upon cloud call completion, the session cleanup (stop_notify) handles the disconnected state gracefully.

## Requirements

### Functional Requirements

- **FR-001**: The session layer MUST offload blocking cloud calls to a worker thread using `asyncio.to_thread()` to keep BLE/GATT operations on the caller's asyncio event loop.
- **FR-002**: The `run_authenticated_lock_operation()` public signature MUST remain unchanged (backward compatible).
- **FR-003**: Cloud helper exceptions MUST propagate to the caller with original type and context preserved (no wrapping/swallowing).
- **FR-004**: All existing session-flow tests MUST remain green without modification.
- **FR-005**: BLE callbacks and CCCD enable/disable order MUST remain unchanged and produce identical wire bytes.
- **FR-006**: If `run_authenticated_lock_operation()` is called concurrently against the same lock device, the second call MUST immediately raise `OperationInProgressError` without modifying internal state.
- **FR-007**: Cloud failures MUST NOT trigger automatic retries. Exceptions from cloud helpers propagate immediately; the caller must implement retry logic if desired.
- **FR-008**: Observability logging MUST be at DEBUG level only. Successful cloud operations log phase and duration. No credentials, authentication headers, session material, or cryptographic secrets may appear in any log output, including error logs.
- **FR-009**: Tests MUST verify that no secrets are logged even when cloud requests fail with exceptions.

### Key Entities

- **AsyncWorkerThread**: Executes `cloud_get_public_key()` and `get_session_material()` outside the main event loop via `asyncio.to_thread()`.
- **EventLoop**: Caller's asyncio event loop, which remains responsive to other coroutines while cloud I/O executes in a separate thread.
- **CloudHelper**: Synchronous functions (`cloud_get_public_key`, `get_session_material`) that perform blocking network I/O via urllib.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Cloud I/O operations do not block the asyncio event loop — other coroutines scheduled during a cloud call complete without waiting for the cloud call to finish.
- **SC-002**: 100% of existing tests pass without modification (backward compatibility verified).
- **SC-003**: Cloud helper exceptions propagate correctly to the caller without loss of type, message, or context (testable via exception type assertions).
- **SC-004**: A mock slow cloud helper (2+ second delay) does not stall concurrent async tasks; task completion rate > 80% during cloud delay.
- **SC-005**: Lock/unlock operations complete with identical ciphertext and wire bytes before and after this change (protocol integrity verified).
- **SC-006**: Concurrent calls to `run_authenticated_lock_operation()` against the same lock device are rejected with `OperationInProgressError` (no race conditions, no duplicate authentication).
- **SC-007**: No credentials, session keys, or sensitive material appear in logs, even when cloud requests fail with exceptions (verified via log inspection tests).

## Assumptions

- The caller's asyncio event loop is the sole consumer of `run_authenticated_lock_operation()`. Worker thread offloading is appropriate for this use case.
- Existing urllib-based cloud helpers (`cloud_get_public_key`, `get_session_material`) remain unchanged; only their threading boundary changes.
- The lock device remains connected during the cloud I/O (no special handling for mid-operation disconnection is required; normal BLE error handling applies).
- `asyncio.to_thread()` is available (Python 3.9+); project already targets Python 3.10+.
- No additional async wrapper is needed for the cloud helpers; they are called directly in a worker thread.

## Out of Scope

- HTTP layer migration from `urllib` to `aiohttp` (tracked separately)
- Home Assistant integration code or custom components
- Changes to cloud API contracts or authentication methods
- BLE transport or protocol changes
