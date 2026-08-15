# Implementation Plan: Cloud I/O Async-Safe

**Branch**: `012-cloud-io-async` | **Date**: 2026-08-15 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/012-cloud-io-async/spec.md`

## Summary

**Objective**: Make `run_authenticated_lock_operation()` async-safe for Home Assistant by offloading blocking cloud I/O to a worker thread using `asyncio.to_thread()`, keeping the BLE/GATT choreography on the caller's event loop.

**Technical Approach**:
- Wrap `cloud_get_public_key()` and `get_session_material()` calls with `asyncio.to_thread()`
- Implement per-device concurrency control: reject concurrent operations with `OperationInProgressError`
- No automatic retries; cloud failures immediately abort session
- DEBUG-level logging only; strict secret protection
- 100% backward compatible; no public API changes except new exception type

## Technical Context

**Language/Version**: Python 3.10+ (project target)

**Primary Dependencies**: 
- `asyncio` (stdlib; Python 3.9+)
- `cryptography` (existing; AES-CCM, RSA)
- `urllib` (existing; blocking cloud I/O)

**Storage**: None (session ephemeral)

**Testing**: `pytest` (existing test suite)

**Target Platform**: Linux/macOS/Windows (via Bleak native stacks or Bumble HCI relay)

**Project Type**: Python library (async BLE protocol + cloud KDF)

**Performance Goals**: 
- Event loop responsiveness: <10ms latency for other tasks during cloud I/O
- Cloud call latency: 2-5 seconds typical (network-bound, no change)
- BLE choreography: <500ms (protocol-driven, unchanged)

**Constraints**: 
- No breaking changes (backward compatible)
- No new external dependencies
- Existing tests must pass
- Secrets must never appear in logs

**Scale/Scope**: 
- Single feature boundary change: cloud call offload
- No protocol/crypto changes
- No UI/CLI changes

## Constitution Check

*GATE: Must pass before Phase 1 design. Re-check after implementation.*

✅ **No Constitution Violations**

- ✅ **Article I (Frozen Protocol)**: CRC-16, framing, AES-CCM, KDF unchanged
- ✅ **Article II (Backward Compatibility)**: Public signature unchanged; only threading boundary moves
- ✅ **Article III (No Secrets in Logs)**: DEBUG-level logging enforced; tests validate secret exclusion
- ✅ **Article IV (Best-Effort Reliability)**: Optional capabilities unchanged; BLE flow unchanged
- ✅ **Article V (Testability)**: All existing tests continue to pass; new tests verify async behavior

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
aqara_u200_ble/
├── session.py            # MODIFIED: wrap cloud calls with asyncio.to_thread()
├── __init__.py           # MODIFIED: export OperationInProgressError
└── [other modules unchanged]

tests/
├── test_async_cloud_boundary.py   # NEW: async-safety tests
├── test_session_flow.py            # EXISTING: still passes
└── [other tests unchanged]
```

**Structure Decision**: Single library package. No new modules needed; changes are localized to session.py and new exception. Tests added alongside existing test suite.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |

## Phase 0: Research (Completed)

**Status**: ✅ Completed via `/speckit-clarify` + `/speckit-plan`

**Output**: [research.md](research.md)

**Findings**:
- ✅ Threading mechanism: `asyncio.to_thread()` (no alternatives needed)
- ✅ Concurrency control: Reject via `OperationInProgressError`
- ✅ Error handling: Fail-fast; no automatic retries
- ✅ Logging: DEBUG-level only; strict secret protection
- ✅ Exception propagation: Unwrapped; original type preserved

**Unknowns Resolved**: None remaining (spec clarifications answered all questions)

---

## Phase 1: Design (Completed)

**Status**: ✅ Completed

**Outputs**:
- ✅ [data-model.md](data-model.md) — Entity definitions, state transitions, validation rules
- ✅ [contracts/public-api.md](contracts/public-api.md) — Public API contract, backward compatibility guarantees
- ✅ [quickstart.md](quickstart.md) — End-to-end validation scenarios

**Key Artifacts**:
- New exception: `OperationInProgressError` (public)
- Modified function: `run_authenticated_lock_operation()` (internal threading, signature unchanged)
- State tracking: Per-device concurrency flag (internal)

---

## Phase 2: Implementation (Ready for `/speckit-tasks`)

**Next Command**: `/speckit-tasks`

**Expected Task Breakdown**:
1. Define `OperationInProgressError` exception class
2. Add per-device concurrency tracking to session layer
3. Wrap `cloud_get_public_key()` with `asyncio.to_thread()`
4. Wrap `get_session_material()` with `asyncio.to_thread()`
5. Add DEBUG-level logging for cloud operations
6. Implement concurrency rejection logic
7. Add test: concurrent operations rejected
8. Add test: cloud I/O doesn't block event loop
9. Add test: no secrets in logs
10. Add test: exception propagation
11. Verify all existing tests pass
12. Run quality gates (ruff, mypy, pytest)
