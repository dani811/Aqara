---

description: "Task list for feature 010 — lock operation & settings catalog"
---

# Tasks: Lock operation & settings catalog

**Input**: Design documents from `/specs/010-operation-catalog/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included — FR-006 requires network-free tests for the catalog and builder.

**Organization**: By user story (US1 catalog, US2 builder, US3 promotion docs).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 / US2 / US3

---

## Phase 1: Setup

- [ ] T001 No new deps — confirm the catalog/builder use the standard library only (plan.md Technical Context)

## Phase 2: Foundational (Blocking Prerequisites)

- [ ] T002 Create `aqara_ble/operations_catalog.py` with `CommandFamily`, `OperationStatus`, `OperationEntry` per data-model.md
- [ ] T003 Export the new public names from `aqara_ble/__init__.py` (`CommandFamily`, `OperationStatus`, `OperationEntry`, `OPERATIONS_CATALOG`, `find_operation`, `operations_in_family`, `build_control_frame`)

**Checkpoint**: types + exports exist; stories can build on them.

---

## Phase 3: User Story 1 - Discover every operation (Priority: P1) 🎯 MVP

**Goal**: a structured, honestly-labelled catalog of all eight families.

**Independent Test**: catalog contains all 8 families with sub-commands, each labelled confirmed/catalogued.

- [ ] T004 [US1] Populate `OPERATIONS_CATALOG` with all eight families from `operaciones-u200.md` (SYSTEM/USER/LOG/ALARM/DEVICELOG/XXQ/SYSTEM_EXT/LONG), all sub-commands, in `aqara_ble/operations_catalog.py`
- [ ] T005 [US1] Mark open/close/keepalive as `CONFIRMED` with their `confirmed_frame`; everything else `CATALOGUED` (FR-002)
- [ ] T006 [US1] Implement `find_operation` and `operations_in_family` lookups (never raise on unknown), in `aqara_ble/operations_catalog.py`
- [ ] T007 [P] [US1] Tests: all 8 families present, sub-commands non-empty, confirmed set == {open, close, keepalive}, lookups behave, in tests/test_operations_catalog.py

**Checkpoint**: catalog is browsable and correctly labelled.

---

## Phase 4: User Story 2 - Build any frame (Priority: P1)

**Goal**: a generic control-frame builder that also reproduces the confirmed operate frame.

**Independent Test**: generic builder equals open/close for `0x74`; emits `main sub data` otherwise.

- [ ] T008 [US2] Add `build_control_frame(main_cmd, sub_cmd, data=b"", seq=1)` in `aqara_ble/lock_ops.py`, delegating `SYSTEM 0x74` to `build_operate_frame` and emitting `main+sub+data` otherwise, with byte-range validation (FR-003)
- [ ] T009 [P] [US2] Tests: `build_control_frame(0x01,0x74,...)` == `build_operate_frame(...)`; generic case emits `main sub data`; out-of-range rejected, in tests/test_operations_catalog.py

**Checkpoint**: any frame can be built; confirmed frames stay byte-exact.

---

## Phase 5: User Story 3 - Promotion procedure (Priority: P2)

**Goal**: documented, reproducible way to confirm a catalogued command's exact data.

- [ ] T010 [US3] Write the full catalog table + confirmed/catalogued legend + promotion procedure into `docs/protocol/operations.md` (FR-005)

**Checkpoint**: a reader can find any operation and knows how to confirm its data.

---

## Phase 6: Polish & Cross-Cutting

- [ ] T011 Run the full suite + ruff; confirm green and no secrets introduced (SC-003, FR-007)
- [ ] T012 [P] Cross-check the catalog covers every family/sub in `operaciones-u200.md` (SC-001) and note any intentionally-omitted entries

---

## Dependencies & Execution Order

- Setup (T001) → Foundational (T002–T003) → US1 (T004–T007) → US2 (T008–T009) → US3 (T010) → Polish (T011–T012).
- T008 depends on `build_operate_frame` (feature 009, already present) and T002.
- Tests (T007, T009) can run in parallel once their targets exist.

## Implementation Strategy

MVP = US1 (the catalog) + US2 (the builder): an integrator can see every operation
and build any frame. US3 is the doc that lets the catalogued majority be promoted
to confirmed over time. No lock actuation in this feature.

## Notes

- Only feature-009-confirmed commands are `CONFIRMED`; the rest are `CATALOGUED`
  until captured — this labelling is the guard against the `1f031f`/`200320` error.
- Opcodes/frame structure are protocol, not secrets (Principle I).
