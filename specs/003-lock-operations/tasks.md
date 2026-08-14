---
description: "Task list for feature 003 — Lock operations"
---

# Tasks: Lock operations

**Input**: Design documents from `specs/003-lock-operations/`

**Prerequisites**: plan.md, spec.md; feature 002 (control framing) merged.

**Tests**: INCLUDED — pure-logic mapping/dispatch via fake transports (Principle V).

**Organization**: Grouped by user story. Retrospective migration of `lock_ops.py`
and `volume.py` unchanged, plus their pytest suites.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable · **[Story]**: US1 build · US2 dispatch · US3 volume

## Phase 1: Setup

- [ ] T001 Confirm both modules are stdlib-only except `volume.py`'s import of
  `aqara_u200_ble.protocol.ControlRequest` (feature 002); no new dependencies.

## Phase 2: Foundational

- [ ] T002 Migrate `lock_ops.py` unchanged: `LockOperation` enum, the
  `SessionOperationTransport` port, and `LockOperationWrite` dataclass.
- [ ] T003 Migrate `volume.py` unchanged: `VoiceVolumePreset` enum, the
  `ControlWriteTransport` port, `VoiceVolumeWrite` dataclass, and the captured
  `_VOICE_VOLUME_REQUESTS` map.

**Checkpoint**: Types and captured constants importable.

## Phase 3: User Story 1 — Build a lock/unlock command (Priority: P1) 🎯 MVP

**Goal**: Intent → exact payload + write prefix; reject unknown intents.

### Tests for User Story 1

- [ ] T004 [P] [US1] `tests/test_lock_ops.py::test_build_unlock` — "unlock" →
  payload `200320`, prefix `0x03`.
- [ ] T005 [P] [US1] `tests/test_lock_ops.py::test_lock_distinct_from_unlock` —
  "lock" → `1f031f`, and lock payload ≠ unlock payload.
- [ ] T006 [P] [US1] `tests/test_lock_ops.py::test_alias_and_case_insensitive` —
  "Desbloquear", "abrir", "UNLOCK" all normalize to UNLOCK; unknown raises.

### Implementation for User Story 1

- [ ] T007 [US1] Migrate `normalize_lock_operation` and
  `build_lock_operation_write` (payload + prefix map) into `lock_ops.py` —
  unchanged.

**Checkpoint**: US1 functional.

## Phase 4: User Story 2 — Dispatch through a transport (Priority: P1)

**Goal**: Send the built payload via an injected transport; return a record.

### Tests for User Story 2

- [ ] T008 [P] [US2] `tests/test_lock_ops.py::test_send_dispatches_payload` — a
  fake transport receives exactly the built payload; the returned write matches.

### Implementation for User Story 2

- [ ] T009 [US2] Migrate `send_lock_operation` into `lock_ops.py` — unchanged.

**Checkpoint**: US1 AND US2 verified.

## Phase 5: User Story 3 — Set voice/alert volume (Priority: P2)

**Goal**: Named preset → captured control request bytes; dispatch via transport.

### Tests for User Story 3

- [ ] T010 [P] [US3] `tests/test_volume.py::test_build_high_volume_bytes` — "high"
  serializes to the captured control request bytes.
- [ ] T011 [P] [US3] `tests/test_volume.py::test_set_volume_dispatches` — a fake
  transport receives exactly those bytes; unsupported preset raises.

### Implementation for User Story 3

- [ ] T012 [US3] Migrate `normalize_voice_volume_preset`,
  `build_voice_volume_write`, `write_voice_volume`, `set_voice_volume` into
  `volume.py` — unchanged.

**Checkpoint**: All stories verified.

## Phase 6: Polish & Cross-Cutting

- [ ] T013 Extend `aqara_u200_ble/__init__.py` to export the operations surface
  (`LockOperation`, `LockOperationWrite`, `build_lock_operation_write`,
  `normalize_lock_operation`, `send_lock_operation`, `VoiceVolumePreset`,
  `VoiceVolumeWrite`, `build_voice_volume_write`, `normalize_voice_volume_preset`,
  `write_voice_volume`, `set_voice_volume`).
- [ ] T014 [P] Author `docs/protocol/operations.md`: operation payload map
  (lock/unlock/keepalive/state) and the voice-volume requests.
- [ ] T015 Secret-hygiene sweep: confirm no credential/personal capture in the two
  modules, tests, or docs (Principle I).
- [ ] T016 [P] `ruff check` + `mypy --strict` clean; `pytest` green (no network).

## Dependencies & Execution Order

- Setup → Foundational (types/constants) blocks the stories.
- US1 (build) and US2 (dispatch) are the P1 MVP; US3 (volume) is P2 on top.
- Polish (exports, docs, sweep, gates) last.

## Notes

- No wire/logic change (Principle II); fake-transport tests pin the dispatch
  behavior without any BLE.
- `volume.py` reuses feature 002's `ControlRequest`; keep that import intact.
