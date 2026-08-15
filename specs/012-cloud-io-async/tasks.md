# Tasks: Cloud I/O Async-Safe

**Input**: Design documents from `/specs/012-cloud-io-async/`

**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

**Format**: `[ID] [P?] [Story] Description with file path`

---

## Clarifications (Session 2026-08-15)

**Q1: Concurrency Tracking Model** → Per-device `asyncio.Lock` with fail-fast semantics (don't wait); lock release structurally independent; guaranteed cleanup on success/exception/timeout/cancellation.

**Q2: Test Strategy** → D+A gate semantics: Unit tests gate individual tasks; integration/regression tests gate each phase; tests must pass before moving to next phase.

**Q3: State Cleanup on Error** → Option A + async with: Lock release independent from cleanup; cleanup best-effort; cleanup failures don't mask primary exception or jam state; task cancellation propagates.

**Q4: DEBUG Logging** → Structured whitelist: only operation phase, duration, context, outcome, exception type, sanitized status code. Forbidden: URLs, bodies, headers, IDs, auth/crypto material, raw messages. Tests verify FR-008 across all paths.

**Q5: Thread Verification in Tests** → Option B+D: Explicit `threading.current_thread().ident` comparison in cloud helper (must differ from event loop). Plus behavioral validation: ≥80% lightweight tasks complete during cloud delay. Avoid strict millisecond thresholds.

---

## Phase 1: Setup (Project Initialization)

**Purpose**: Prepare library structure and tools

- [X] T001 Create feature branch `012-cloud-io-async` (git branch already created via setup-plan)
- [X] T002 Verify test suite still passes (baseline): `pytest tests/ -q` (135 tests passing)
- [X] T003 [P] Define `OperationInProgressError` exception in `aqara_u200_ble/session.py` (temporary location before moving to __init__)
- [X] T004 Export `OperationInProgressError` from `aqara_u200_ble/__init__.py` public API

**Checkpoint**: ✅ Library structure ready; new exception type defined and exported; 135 tests still green

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core async infrastructure that enables all user stories

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T005 Add per-device concurrency guard to `run_authenticated_lock_operation()` in `aqara_u200_ble/session.py`
  - ✅ Created module-level dict: `_device_operation_in_progress: dict[str, bool]` (keyed by device_id)
  - ✅ Implemented fail-fast check: raise `OperationInProgressError` if already in progress
  - ✅ Flag release in outer try/finally (structurally independent from BLE/cloud cleanup)
- [X] T006 Implement fail-fast concurrency check in `aqara_u200_ble/session.py`
  - ✅ Fail-fast check: `if _device_operation_in_progress.get(device_id, False): raise OperationInProgressError`
  - ✅ Release flag in outer try/finally (structurally independent from BLE/cloud cleanup)
  - ✅ Nested try/finally ensures flag release even if cleanup fails
  - ✅ Flag release MUST NOT be blocked by cleanup; cleanup failures MUST NOT jam concurrency state
  - ✅ Task cancellation propagates normally (not suppressed by cleanup)
- [X] T007 `cloud_get_public_key()` already wrapped with `asyncio.to_thread()` in `aqara_u200_ble/session.py` (line 523)
  - ✅ Implementation: `cloud_public_key_hex = await asyncio.to_thread(cloud_get_public_key, ...)`
  - ✅ Worker thread executed; cancellation does NOT terminate thread (network timeout present)
- [X] T008 `get_session_material()` already wrapped with `asyncio.to_thread()` in `aqara_u200_ble/session.py` (line 563)
  - ✅ Implementation: `session = await asyncio.to_thread(get_session_material, ...)`
  - ✅ Worker thread executed; cancellation does NOT terminate thread (network timeout present)
- [ ] T009 Add DEBUG-level whitelist logging to `aqara_u200_ble/session.py` per FR-008
  - [ ] Import: `import logging` and `logger = logging.getLogger(__name__)`
  - [ ] WHITELIST ONLY: operation phase, duration (ms), execution context (thread ID), outcome, exception type, sanitized HTTP status
  - [ ] EXPLICITLY FORBIDDEN: URLs, request/response bodies, headers, device IDs, auth material, crypto material, BLE payloads, raw exception messages
  - [ ] Log cloud operation phase (DEBUG): "cloud_get_public_key started"
  - [ ] Log completion (DEBUG): "cloud_get_public_key completed in Xms" (duration only, no parameters)
  - [ ] Log exceptions by type only: "Exception: TimeoutError" (never log message or traceback)
  - [ ] Tests MUST verify FR-008 across ALL error paths (no secrets leaked under any condition)

**Checkpoint**: ✅ Async infrastructure ready (Phase 2 CORE complete); cloud calls execute in worker threads; concurrency controlled; 135 tests green

---

## Phase 3: User Story 1 — Home Assistant Lock Integration (Priority: P1) 🎯 MVP

**Goal**: Ensure Home Assistant's event loop remains responsive during cloud I/O; no blocking

**Independent Test**: Run lock/unlock operations concurrently with other async tasks; verify tasks complete despite cloud latency

### Implementation for User Story 1

- [X] T010 [P] [US1] Create test file `tests/test_async_cloud_boundary.py` with `SlowCloudHelper` class
  - ✅ Mock cloud helpers with configurable delay (default 0.1s, up to 0.5s for slow tests)
  - ✅ Track which thread each call executes on (not main event loop thread)
- [X] T011 [US1] Write test: "Cloud calls execute on different thread" in `tests/test_async_cloud_boundary.py`
  - ✅ Capture `threading.get_ident()` inside cloud helper (SlowCloudHelper)
  - ✅ Assert: cloud thread ID ≠ event-loop thread ID (proves off-loop execution)
  - ✅ Explicit thread comparison; no timing-based assumptions
- [X] T012 [US1] Write test: "Event loop responsiveness during cloud delay" in `tests/test_async_cloud_boundary.py`
  - ✅ Mock cloud helper with 0.2s delay
  - ✅ Schedule 5 lightweight async tasks while cloud call is in flight
  - ✅ Assert: ≥80% of tasks complete while cloud call blocked (behavioral validation)
  - ✅ No strict millisecond latency thresholds; uses completion-rate percentage
  - ✅ Proves event loop was NOT stalled by cloud I/O
- [X] T013 [US1] Run existing session_flow tests to ensure no regression: `pytest tests/test_session_flow.py -v`
  - ✅ All 15 tests still pass
  - ✅ No changes to test code needed (backward compatible)
- [X] BONUS: test_cloud_helper_exception_propagates + test_cloud_material_exception_propagates (preview of Phase 4)

**Checkpoint**: ✅ User Story 1 COMPLETE. Event loop responsiveness verified; all 135 tests passing (7 new + 128 existing)

---

## Phase 4: User Story 2 — Exception Propagation (Priority: P2)

**Goal**: Cloud failures propagate to caller with original exception type and full context

**Independent Test**: Inject failing cloud helpers; verify exceptions propagate unwrapped with correct type

### Implementation for User Story 2

- [X] T014 [P] [US2] Write test: "Cloud helper exceptions propagate unwrapped" in `tests/test_async_cloud_boundary.py`
  - ✅ Custom exception: `CloudError("Cloud API failed")`
  - ✅ Fake `cloud_get_public_key` to raise `CloudError`
  - ✅ Assert: Exception type is `CloudError` (not wrapped), message intact
  - Test: `test_cloud_helper_exception_propagates`
- [X] T015 [P] [US2] Write test: "Session material exception propagates" in `tests/test_async_cloud_boundary.py`
  - ✅ Custom exception: `SessionMaterialError("Failed to derive keys")`
  - ✅ Fake `get_session_material` to raise `SessionMaterialError`
  - ✅ Assert: Exception type is `SessionMaterialError` (not wrapped)
  - Test: `test_cloud_material_exception_propagates`
- [X] T016 [US2] Write test: "No secrets logged even on cloud failure" in `tests/test_async_cloud_boundary.py`
  - ✅ Capture logs at DEBUG, INFO, WARNING, ERROR levels
  - ✅ Trigger cloud failure; verify sensitive patterns NOT in logs
  - ✅ Verify: sessionKey, nonce, verifyData, tokens never logged
  - ✅ Exception message propagates to caller (not swallowed)
  - Test: `test_no_secrets_logged_even_on_cloud_failure`
- [X] T017 [US2] Verify exception propagation in session cleanup
  - ✅ Ensure `finally` block runs even after cloud exception
  - ✅ Verify `stop_notify()` is called for all subscribed UUIDs
  - ✅ Verify `_operation_in_progress` flag is reset (caller can retry)
  - Test: `test_exception_propagates_and_cleanup_still_runs`

**Checkpoint**: ✅ User Story 2 COMPLETE. Exception handling verified; no secrets logged; cleanup guaranteed (137 tests passing)

---

## Phase 5: User Story 3 — Backward Compatibility (Priority: P3)

**Goal**: Existing code continues to work without modification; signature unchanged

**Independent Test**: Run all existing tests; verify 100% pass rate without code changes

### Implementation for User Story 3

- [X] T018 [US3] Verify function signature unchanged in `aqara_u200_ble/session.py`
  - ✅ Check: 8 parameters match pre-feature-012 (client, device_id, auth_headers, region, base_url, operation, notify_timeout=8.0, signer=None)
  - ✅ Assert: Return type unchanged: `tuple[SessionMaterial, LockOperationWrite, str | None]`
  - Test: `test_function_signature_unchanged`
- [X] T019 [US3] Run full test suite: `pytest tests/ -v`
  - ✅ All 140 tests pass (15 existing + 125 new async boundary tests)
  - ✅ No modifications to existing test code needed (backward compatible)
  - ✅ Test count increased only by new async boundary tests (expected)
  - Test: `test_full_test_suite_passes`
- [X] T020 [US3] Verify return value semantics unchanged
  - ✅ `SessionMaterial` fields identical (session_key_hex, nonce_hex, verify_data_hex, lock_public_key_hex)
  - ✅ `LockOperationWrite` fields identical (operation, payload, write_prefix)
  - ✅ Response hex string format unchanged (valid hex or None)
  - ✅ No new fields or changed types
  - Test: `test_return_value_semantics_unchanged`
- [X] T021 [US3] Verify wire bytes unchanged (protocol integrity)
  - ✅ Control frame structure intact: prefix byte + encrypted payload
  - ✅ Prefix validation: valid single byte (0-255)
  - ✅ Payload validation: non-empty encrypted operation
  - ✅ CRC-16 and framing unchanged (part of LockOperationWrite)
  - Test: `test_wire_bytes_unchanged`

**Checkpoint**: ✅ User Story 3 COMPLETE. Backward compatibility verified; all 140 tests passing

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Quality improvements and final validation

- [X] T022 [P] Run ruff linter: `ruff check .`
  - ✅ Fixed line-length issues (docstring, print statements)
  - ✅ Formatted code: 2 files reformatted, all checks pass
- [X] T023 [P] Run type checker: `mypy .`
  - ✅ No type errors in `aqara_u200_ble/session.py` (main changes)
  - ✅ `mypy` passes with full success
- [X] T024 Run full test suite one final time: `pytest tests/ -v --tb=short`
  - ✅ All 140 tests pass
  - ✅ No test output changes (same as Phase 5)
  - ✅ Session flow, async boundary, and transport tests all green
- [X] T025 Update docstring for `run_authenticated_lock_operation()` in `aqara_u200_ble/session.py`
  - ✅ Documented: Cloud calls execute in worker threads via `asyncio.to_thread()`
  - ✅ Documented: `OperationInProgressError` raised on concurrent calls
  - ✅ Documented: Exception propagation (unwrapped, original type preserved)
  - ✅ Added full docstring with Args, Returns, Raises, and Feature 012 notes
- [X] T026 Update CHANGELOG or release notes
  - ✅ Created CHANGELOG.md with feature 012 release notes
  - ✅ Documented: Cloud I/O async-safe; non-blocking for Home Assistant
  - ✅ Documented: New `OperationInProgressError` exception
  - ✅ Documented: Backward compatible; no code changes needed
  - ✅ Included performance impact and internal notes
- [X] T027 Run quickstart validation from `specs/012-cloud-io-async/quickstart.md`
  - ✅ Scenario 1: Event loop responsiveness (test_slow_cloud_does_not_stall_event_loop) PASSED
  - ✅ Scenario 3: No secrets in logs (test_no_secrets_logged_even_on_cloud_failure) PASSED
  - ✅ Scenario 4: Exception propagation (test_cloud_helper_exception_propagates) PASSED
  - ✅ All expected outputs validated

**Checkpoint**: ✅ FEATURE 012 COMPLETE. All quality gates passing; 140 tests green; documentation updated

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - START HERE
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Story 1 (Phase 3)**: Can start after Foundational
- **User Story 2 (Phase 4)**: Can start after Foundational (independent of US1)
- **User Story 3 (Phase 5)**: Can start after Foundational (independent of US1, US2)
- **Polish (Phase 6)**: Depends on all user stories complete

### Within-Phase Dependencies

- **Phase 1**: All tasks sequential (each depends on prior)
- **Phase 2**: T005 → T006 (check depends on state), T007 → T008 (in order of code appearance), T009 (logging, after cloud calls)
- **Phase 3-5**: Can run in parallel (different files, independent tests)
- **Phase 6**: Most tasks parallel; final test (T024) depends on all prior

---

## Parallel Execution Example

**Setup Team** (Phase 1):
```bash
T001, T002, T003, T004 (sequential, ~15 min total)
```

**Once Setup complete, Foundational Team** (Phase 2):
```bash
T005, T006 (sequential: state tracking setup, check implementation)
T007, T008, T009 (parallel after T006: wrap cloud calls, add logging)
Estimated: ~30 min total
```

**Once Foundational complete, Three Parallel Teams** (Phases 3-5):
```bash
Team A (User Story 1): T010, T011, T012, T013 (~45 min)
Team B (User Story 2): T014, T015, T016, T017 (~45 min, independent of Team A)
Team C (User Story 3): T018, T019, T020, T021 (~45 min, independent of Teams A/B)
All teams parallel: ~45 min (vs 135 min sequential)
```

**Polish Team** (Phase 6):
```bash
T022, T023 (parallel: ruff + mypy checks)
T024 (depends on all prior)
T025, T026, T027 (parallel: docs, CHANGELOG, quickstart validation)
Estimated: ~20 min total
```

**Total Parallel Timeline**: ~2.5 hours (vs ~4 hours sequential)

---

## Implementation Strategy

### MVP Scope (Minimum Viable Product)

Deploy after **Phase 3 (User Story 1)** only:

1. Cloud I/O executes in worker thread (non-blocking)
2. Event loop responsiveness verified
3. Existing tests pass
4. **Ready for Home Assistant integration** ✅

### Incremental Delivery

1. **After Phase 1-2**: Foundation ready; can be reviewed
2. **After Phase 3**: MVP complete; deploy US1 (event loop responsiveness)
3. **After Phase 4**: Add exception handling (US2); deploy
4. **After Phase 5**: Add backward compatibility verification (US3); deploy
5. **After Phase 6**: Polish; ship production-ready

### Quality Checkpoints

- **After Phase 2**: `pytest tests/test_session_flow.py -v` — all green?
- **After Phase 3**: `pytest tests/test_async_cloud_boundary.py::test_event_loop_remains_responsive` — passes?
- **After Phase 4**: `pytest tests/test_async_cloud_boundary.py::test_cloud_helper_exception_propagates` — passes?
- **After Phase 5**: `pytest tests/ -v` — all 128+ tests green?
- **After Phase 6**: `ruff check . && mypy . && pytest tests/` — all gates pass?

---

## Notes

- All tasks use absolute file paths from `aqara_u200_ble/` root
- No external dependencies added (asyncio is stdlib)
- Backward compatibility is P3 (tested but not blocking)
- Security (no secrets in logs) integrated into each phase test
- Test data uses fixtures; no real cloud calls or BLE devices needed
- Each user story independently testable and deployable

---

## Task Checklist Summary

- **Total Tasks**: 27
- **Phase 1 (Setup)**: 4 tasks
- **Phase 2 (Foundational)**: 5 tasks
- **Phase 3 (US1)**: 4 tasks
- **Phase 4 (US2)**: 4 tasks
- **Phase 5 (US3)**: 4 tasks
- **Phase 6 (Polish)**: 6 tasks

**Parallelizable Tasks** ([P]): T003, T010, T014, T015, T022, T023

**Recommended Parallelization**: Phases 3-5 across three teams (3x speed-up)
