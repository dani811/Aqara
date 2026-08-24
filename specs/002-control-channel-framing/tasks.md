---
description: "Task list for feature 002 — Control channel framing"
---

# Tasks: Control channel framing

**Input**: Design documents from `specs/002-control-channel-framing/`

**Prerequisites**: plan.md, spec.md

**Tests**: INCLUDED — pure-logic parsing/CRC (Principle V), captured-frame fixtures.

**Organization**: Grouped by user story. Retrospective migration of the unchanged
`protocol.py` leaf module plus its pytest fixtures.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable · **[Story]**: US1 parse · US2 round-trip · US3 CRC

## Phase 1: Setup

- [X] T001 Confirm `protocol.py` is a stdlib-only leaf (no internal imports); no
  new dependencies needed in `pyproject.toml`.

## Phase 2: Foundational

- [X] T002 Migrate the dataclasses and constants into `aqara_ble/protocol.py`
  unchanged: `ATTPacket`, `ControlRequest`, the ATT handle constants
  (`AUTH_WRITE`/`AUTH_NOTIFY`/`CONTROL_WRITE`/`CONTROL_NOTIFY`/`BULK_WRITE`/
  `BULK_NOTIFY` and the `ATT_CONTROL_*` aliases).

**Checkpoint**: Types and constants importable.

## Phase 3: User Story 1 — Decode a control request (Priority: P1) 🎯 MVP

**Goal**: Split a control payload into kind/command/body/trailer; reject bad frames.

### Tests for User Story 1

- [X] T003 [P] [US1] `tests/test_protocol.py::test_parses_voice_volume_request` —
  `01d302d13e15d5fddfe4` → kind 0x01, cmd 0xD3, body `02d13e15`, trailer `d5fddfe4`.
- [X] T004 [P] [US1] `tests/test_protocol.py::test_parses_keepalive_request` —
  `01fe01fc158b3609` → cmd 0xFE, body `01fc`, trailer `158b3609`.
- [X] T005 [P] [US1] `tests/test_protocol.py::test_rejects_too_short_control_request` +
  `tests/test_protocol.py::test_rejects_unrecognized_prefix` —
  a <7-byte frame and a wrong-prefix frame both raise `ValueError`.

### Implementation for User Story 1

- [X] T006 [US1] Migrate `parse_control_request` and `control_command_name`
  (with `_COMMAND_NAMES`) into `protocol.py` — unchanged.

**Checkpoint**: US1 functional — frames decode and bad frames reject.

## Phase 4: User Story 2 — Round-trip to bytes (Priority: P2)

**Goal**: Serialize a request back to the exact captured bytes.

### Tests for User Story 2

- [X] T007 [P] [US2] `tests/test_protocol.py::test_control_request_roundtrip_is_identity` —
  `parse(frame).as_bytes() == frame` for both captured frames.

### Implementation for User Story 2

- [X] T008 [US2] Confirm `ControlRequest.as_bytes` is present and is the exact
  inverse of `parse_control_request` (migrated with the dataclass in T002).

**Checkpoint**: US1 AND US2 both verified.

## Phase 5: User Story 3 — Bulk integrity (Priority: P3)

**Goal**: Validate a bulk block against its CRC-HQX trailer.

### Tests for User Story 3

- [X] T009 [P] [US3] `tests/test_protocol.py::test_valid_crc_accepts_captured_block` —
  a captured block plus its `crc_hqx` trailer validates true.
- [X] T010 [P] [US3] `tests/test_protocol.py::test_valid_crc_rejects_mutation` —
  flipping one content byte makes it false; a <2-byte input is false.

### Implementation for User Story 3

- [X] T011 [US3] Migrate `valid_crc` into `protocol.py` — unchanged.

**Checkpoint**: All stories verified.

## Phase 6: Polish & Cross-Cutting

- [X] T012 Extend `aqara_ble/__init__.py` to export the control-framing
  surface (`ATTPacket`, `ControlRequest`, `parse_control_request`,
  `control_command_name`, `valid_crc`, ATT handle constants).
- [X] T013 [P] Author `docs/protocol/control-channel.md`: frame shape
  (kind/command/body/trailer), command map, and the CRC-HQX vs CRC-16/ARC note.
- [X] T014 Secret-hygiene sweep: confirm no secret/capture in `protocol.py`,
  tests, or docs (Principle I).
- [X] T015 [P] `ruff check` + `mypy --strict` clean; `pytest` green (no network).

## Dependencies & Execution Order

- Setup → Foundational (types/constants) blocks the stories.
- US1 (P1) is the MVP; US2 and US3 are independent verifications on top.
- Polish (exports, docs, sweep, gates) last.

## Notes

- `protocol.py` is a dependency-free leaf; migrating it unblocks features 003 and
  004 which import from it.
- No wire/logic change (Principle II); fixtures pin the observable behavior.
