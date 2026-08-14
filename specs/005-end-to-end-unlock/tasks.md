---
description: "Task list for feature 005 — End-to-end autonomous unlock"
---

# Tasks: End-to-end autonomous unlock

**Input**: Design documents from `specs/005-end-to-end-unlock/`

**Prerequisites**: plan.md, spec.md; features 001–004 merged.

**Tests**: INCLUDED for pure logic (adapter lookup, discovery constants, package
API). The live unlock and real scan need hardware — validated live, not unit-tested
(Principle V).

**Organization**: Grouped by user story. Retrospective migration of `scanner.py`
and `bumble_transport.py` unchanged, plus the composition into a live flow.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable · **[Story]**: US1 discovery · US2 transport · US3 e2e

## Phase 1: Setup

- [ ] T001 Confirm both modules import without optional backends (`bleak` lazy in
  `scanner`, `bumble` under `TYPE_CHECKING` in `bumble_transport`); no new hard deps.

## Phase 2: Foundational

- [ ] T002 Migrate `scanner.py` unchanged: `AQARA_COMPANY_ID`, `EXPECTED_NAME`, and
  the passive `scan` coroutine (lazy `bleak` with a clear error if absent).

**Checkpoint**: Discovery constants/import available.

## Phase 3: User Story 2 — Low-level GATT transport (Priority: P1) 🎯 MVP

**Goal**: Adapter resolves characteristics and exposes the pre-auth primitives.

### Tests for User Story 2

- [ ] T003 [P] [US2] `tests/test_transport.py::test_find_by_short_uuid` — a fake
  peer with the auth characteristic → `_find("...ff07...")` returns it.
- [ ] T004 [P] [US2] `tests/test_transport.py::test_find_missing_raises` — absent
  characteristic → `KeyError`.
- [ ] T005 [P] [US2] `tests/test_transport.py::test_find_by_uuid16` — a 16-bit
  characteristic is resolved by its 16-bit UUID.

### Implementation for User Story 2

- [ ] T006 [US2] Migrate `bumble_transport.py` unchanged: `BumbleGattAdapter` with
  `_find`/`_find_by_uuid16`, `write_gatt_char`, `start_notify`/`stop_notify`,
  `read_by_type`/`write_by_type`, and the timeout-bounded `get_remote_le_features`,
  `request_mtu`, `set_data_length`, `update_connection_parameters`.

**Checkpoint**: US2 functional — adapter lookup verified.

## Phase 4: User Story 1 — Discover the lock (Priority: P2)

**Goal**: Passive scan reports candidates; hints keypad activation when silent.

### Tests for User Story 1

- [ ] T007 [P] [US1] `tests/test_transport.py::test_scanner_constants` —
  `AQARA_COMPANY_ID == 0x0B27`, `EXPECTED_NAME == "DoorLocker"`.

### Implementation for User Story 1

- [ ] T008 [US1] (covered by T002 migration) — verify `scan` performs no writes.

**Checkpoint**: US1 + US2 verified.

## Phase 5: User Story 3 — Full autonomous unlock (Priority: P1)

**Goal**: Compose 001–004 over a transport to unlock a real lock.

### Tests for User Story 3

- [ ] T009 [P] [US3] `tests/test_package_api.py::test_public_api_complete` — every
  name in `__all__` is importable; the package imports with no optional backend.

### Implementation for User Story 3

- [ ] T010 [US3] Extend `aqara_u200_ble/__init__.py` to export `scan` and
  `BumbleGattAdapter`; the end-to-end entrypoint `run_authenticated_lock_operation`
  is already exported (feature 004).
- [ ] T011 [US3] (live, not unit-tested) The composed flow — discover → connect via
  a transport → handshake → dispatch unlock — is validated against a real lock.

**Checkpoint**: End-to-end path assembled; live unlock confirmed.

## Phase 6: Polish & Cross-Cutting

- [ ] T012 [P] Author `docs/tutorials/end-to-end-unlock.md`: run the full autonomous
  unlock from zero (credentials from `.env`, transport choice, dispatch).
- [ ] T013 Secret-hygiene sweep: no credential/MAC/capture in the two modules,
  tests, or docs (Principle I).
- [ ] T014 [P] `ruff check` + `mypy --strict` clean; `pytest` green (no network).
  Behavior-preserving style/type cleanups only, pinned by the tests (Principle II).

## Dependencies & Execution Order

- Setup → Foundational (scanner) → US2 (transport, MVP) → US1 (discovery) → US3
  (compose + live) → Polish.
- US3's live step depends on all prior features and real hardware; its unit-level
  proof is the package-API completeness test.

## Notes

- Optional backends stay optional (FR-006); the package-API test guards it.
- No wire/logic change (Principle II); the adapter lookup and constants are pinned
  by tests, the transport primitives by live btsnoop evidence.
