---
description: "Task list for feature 007 — Verifiable unlock choreography"
---

# Tasks: Verifiable unlock choreography

**Input**: Design documents from `specs/007-session-flow-coverage/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md,
contracts/transport-surface.md, quickstart.md. Features 001–006 merged.

**Tests**: This feature *is* tests. Every user-story task produces an assertion;
none of them performs network or radio I/O (Principle V).

**Organization**: Grouped by user story. US1 (the sequence) is the MVP.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable (independent test functions)
- **[Story]**: US1 sequence · US2 stalling · US3 optional capabilities · US4 cleanup

## Path Conventions

Library layout: package at `aqara_ble/`, tests at `tests/`, docs at `docs/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the seams the fake will use actually exist.

- [X] T001 Confirm `run_authenticated_lock_operation` consumes its client by duck
  typing (`bleak_client: Any`, optional members probed with `getattr`) in
  `aqara_ble/session.py`, so no production seam must be added (FR-010).
- [X] T002 Confirm `session.py` binds `cloud_get_public_key` /
  `get_session_material` in its own namespace (`from .kdf import …`), fixing the
  monkeypatch target as `aqara_ble.session`, not `aqara_ble.kdf`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The fake lock every story drives. Nothing can be asserted before it
exists.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T003 Create `tests/test_session_flow.py` with the module docstring stating
  what the file proves (choreography) and what it does not (that a real lock
  accepts it), plus the throwaway fixtures: a 65-byte EC public key, a 16-byte
  AES-CCM key, and a nonce — none of them real material (FR-008).
- [X] T004 Add the `LockScript` dataclass to `tests/test_session_flow.py` with the
  fields from data-model.md (`empty_acks_before_key`, `send_public_key`,
  `verify_ack_frame_type`, `control_response`, `optional_capabilities`).
- [X] T005 Add `FakeLockClient` to `tests/test_session_flow.py`: `start_notify` /
  `stop_notify` / `write_gatt_char`, fragment buffering and reassembly, the
  `events` record, and script-driven answers pushed back through the stored
  notify callbacks (contracts/transport-surface.md).
- [X] T006 Add the shared `run_unlock(...)` helper to `tests/test_session_flow.py`:
  patches `asyncio.sleep` to a no-op, patches the two cloud functions on
  `aqara_ble.session`, and drives the coroutine with `asyncio.run` (FR-009).

**Checkpoint**: A scripted lock can be driven end to end; assertions can begin.

---

## Phase 3: User Story 1 — The unlock sequence is guarded (Priority: P1) 🎯 MVP

**Goal**: A complete unlock runs against the fake and its observable order is
pinned.

**Independent Test**: `pytest tests/test_session_flow.py -k full_unlock` passes,
and reversing `PRE_AUTH_NOTIFY_ORDER` in production makes it fail.

- [X] T007 [P] [US1] `tests/test_session_flow.py::test_full_unlock_returns_material_write_and_response`
  — the call returns the session material, the dispatched operation, and the
  decrypted control response (FR-001).
- [X] T008 [P] [US1] `tests/test_session_flow.py::test_notifications_enabled_in_captured_order_before_any_write`
  — the four subscriptions match the **literal captured order** (`ff62`, `ff64`,
  `ff92`, `ff08`) and precede every write (FR-002). Asserting against
  `PRE_AUTH_NOTIFY_ORDER` would compare the code to itself; see the T022 outcome.
- [X] T009 [P] [US1] `tests/test_session_flow.py::test_write_order_is_pubkey_then_verify_then_control`
  — the auth frame kinds are `0x06` then `0x07`, and the control write is last
  (FR-002).
- [X] T010 [P] [US1] `tests/test_session_flow.py::test_control_write_carries_the_operation_prefix_and_ciphertext`
  — the control write is the operation's write prefix followed by ciphertext that
  decrypts back to the operation payload (FR-007).

**Checkpoint**: The choreography cannot be silently reordered.

---

## Phase 4: User Story 2 — The lock's stalling stays tolerated (Priority: P1)

**Goal**: Empty ACKs before the key are survived; an endless stream fails clearly;
a wrong verify ACK fails clearly.

**Independent Test**: `pytest tests/test_session_flow.py -k ack` passes.

- [X] T011 [P] [US2] `tests/test_session_flow.py::test_empty_acks_before_public_key_are_tolerated`
  — three bodyless `0x06` frames then the key: the unlock still succeeds
  (FR-003).
- [X] T012 [P] [US2] `tests/test_session_flow.py::test_only_empty_acks_fails_with_specific_message`
  — the key never arrives: `RuntimeError` naming that no public key was received,
  distinct from a timeout (FR-003).
- [X] T013 [P] [US2] `tests/test_session_flow.py::test_wrong_verify_ack_frame_type_is_rejected`
  — the verify step answered `0x06`: `RuntimeError` naming expected and received
  (FR-004).

**Checkpoint**: The project's most expensive discovery is protected.

---

## Phase 5: User Story 3 — A plain transport still works (Priority: P2)

**Goal**: The optional low-level capabilities are provably best-effort.

**Independent Test**: `pytest tests/test_session_flow.py -k optional` passes.

- [X] T014 [P] [US3] `tests/test_session_flow.py::test_unlock_without_any_optional_capability`
  — a client exposing none of the five completes normally (FR-005).
- [X] T015 [P] [US3] `tests/test_session_flow.py::test_unlock_when_optional_capabilities_raise`
  — every optional member raises; the failures are absorbed and the unlock
  completes (FR-005).
- [X] T016 [P] [US3] `tests/test_session_flow.py::test_optional_capabilities_are_exercised_when_present`
  — a client offering all five records them in the captured relative order
  (FR-005, contracts/transport-surface.md).

**Checkpoint**: Neither transport can be broken by a change to the other's path.

---

## Phase 6: User Story 4 — Subscriptions are always released (Priority: P3)

**Goal**: No leaked notifications, on either path.

**Independent Test**: `pytest tests/test_session_flow.py -k released` passes.

- [X] T017 [P] [US4] `tests/test_session_flow.py::test_notifications_released_after_success`
  — every `notify:X` has a matching `stop_notify:X` (FR-006).
- [X] T018 [P] [US4] `tests/test_session_flow.py::test_notifications_released_after_failure`
  — same, when the flow raises mid-way (FR-006).

**Checkpoint**: All four stories functional.

---

## Phase 7: Edge cases & Polish

- [X] T019 [P] `tests/test_session_flow.py::test_missing_control_response_is_tolerated`
  — no answer to the control write: the operation still succeeds with `None` as
  the response (FR-007).
- [X] T020 [P] `tests/test_session_flow.py::test_truncated_control_response_is_rejected`
  — a 1-byte answer raises rather than decrypting garbage (FR-007).
- [X] T021 Verify no production module changed: `git diff develop --stat --
  aqara_ble/` is empty (FR-010, SC-007).
- [X] T022 Run the guard-the-guard check from quickstart scenario 2 — break
  `PRE_AUTH_NOTIFY_ORDER`, confirm a test fails, restore (SC-002).
- [X] T023 [P] Narrow the "live BLE flow is not unit-tested" limitation in
  `docs/roadmap.md` to the part that genuinely needs hardware (SC-008).
- [X] T024 [P] Point `docs/protocol/auth-handshake.md` at the executable
  choreography as evidence (Principle IV).
- [X] T025 Run the gates: `ruff check . && ruff format --check .`,
  `mypy aqara_ble`, `pytest -q --durations=5` (SC-006).
- [X] T026 Secret scan the diff (Principle I) and merge into `develop` with
  `--no-ff` (Principle VI).

> **T022 outcome (recorded, not just claimed)**: six mutations were applied to
> `session.py` one at a time — reversed notification order, empty-ACK tolerance
> removed, control write stripped of its opcode prefix, cleanup deleted,
> verify-ACK check removed, and an optional capability made mandatory. Each was
> caught. The first run of T008 did **not** catch the reversed order, because it
> asserted against `PRE_AUTH_NOTIFY_ORDER` itself — comparing the code to itself.
> It now asserts the literal captured order (`ff62, ff64, ff92, ff08`).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies; it only confirms facts about existing code.
- **Foundational (Phase 2)**: needs Phase 1 — BLOCKS every story, since all of
  them drive `FakeLockClient`.
- **US1 (Phase 3)**: needs Phase 2. Delivers the guard alone.
- **US2 (Phase 4)**: needs Phase 2; exercises `LockScript` fields US1 leaves at
  their defaults.
- **US3 (Phase 5)**: needs Phase 2; independent of US1/US2 assertions.
- **US4 (Phase 6)**: needs Phase 2; its failure case reuses US2's script.
- **Polish (Phase 7)**: after the stories being shipped.

### Within Each User Story

Each task is one independent test function in the same file — they can be written
together and run in any order.

### Parallel Opportunities

- Every `[P]` task inside a story is an independent test function.
- T023/T024 touch different documentation files.
- The stories themselves are independent once Phase 2 lands; only the shared file
  makes concurrent editing awkward.

---

## Parallel Example: User Story 1

```bash
# Write US1's four assertions together (independent test functions):
Task: "test_full_unlock_returns_material_write_and_response"
Task: "test_notifications_enabled_in_captured_order_before_any_write"
Task: "test_write_order_is_pubkey_then_verify_then_control"
Task: "test_control_write_carries_the_operation_prefix_and_ciphertext"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 → Phase 2 (`FakeLockClient`) → Phase 3.
2. **STOP and VALIDATE**: run quickstart scenario 2 — deliberately break the
   order in production and confirm the new test fails. An unverified guard is
   worse than none, because it reads as coverage.

### Incremental Delivery

1. US1 → the sequence is pinned.
2. US2 → the empty-ACK tolerance cannot be "simplified" away.
3. US3 → neither transport can be broken by the other's path.
4. US4 → no leaked subscriptions.
5. Polish → edge cases, docs, gates, merge.

---

## Notes

- This feature adds **no production code**. If a test cannot be written without
  changing `session.py`, stop and re-plan rather than reshaping production code
  around the test.
- What the fake proves is the choreography, never that a real lock accepts it;
  keep that distinction in the roadmap wording (T023).
- Commit per phase.
