---
description: "Task list for feature 004 — BLE authentication handshake"
---

# Tasks: BLE authentication handshake

**Input**: Design documents from `specs/004-ble-auth-handshake/`

**Prerequisites**: plan.md, spec.md; features 001/002/003 merged.

**Tests**: INCLUDED — pure logic (CRC, framing, fragmentation, AES-CCM). The async
BLE orchestration is excluded from unit tests (needs hardware, Principle V).

**Organization**: Grouped by user story. Retrospective migration of `session.py`
unchanged, plus its pytest suite pinning the CRC breakthrough.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable · **[Story]**: US1 build/CRC · US2 fragmentation · US3 AES-CCM

## Phase 1: Setup

- [ ] T001 Confirm `session.py` imports resolve (kdf/protocol/lock_ops present);
  no new dependency beyond `cryptography` (already declared).

## Phase 2: Foundational

- [ ] T002 Migrate the constants and dataclasses unchanged: the UUIDs
  (`AUTH_*`/`CONTROL_*`/`AUX_*`), `GATT_CACHING_PREAMBLE_UUID16`,
  `PRE_AUTH_NOTIFY_ORDER`, `SessionMaterial`, `AuthMessage`, and the `_CRC16_TABLE`.

**Checkpoint**: Constants/types importable.

## Phase 3: User Story 1 — Build an acceptable handshake frame (Priority: P1) 🎯 MVP

**Goal**: Frame with the correct CRC-16/ARC header field; reject bad frame types.

### Tests for User Story 1

- [ ] T003 [P] [US1] `tests/test_session.py::test_crc16_matches_captured_frame` —
  `crc16_aqara(body)` equals the captured header CRC (`0x15ed`) for the captured
  `0610` public-key body. **Pins the breakthrough.**
- [ ] T004 [P] [US1] `tests/test_session.py::test_build_auth_message_layout` —
  header type/length/CRC-field/lock-token are byte-exact; `app_token` is ignored.
- [ ] T005 [P] [US1] `tests/test_session.py::test_build_rejects_bad_frame_type` —
  an unsupported frame type raises `ValueError`.

### Implementation for User Story 1

- [ ] T006 [US1] Migrate `crc16_aqara` and `build_auth_message` — unchanged.

**Checkpoint**: US1 functional — correctly-CRC'd frames build.

## Phase 4: User Story 2 — Fragment and reassemble (Priority: P1)

**Goal**: Fragment/reassemble as exact inverses; reject bad direction/sequence.

### Tests for User Story 2

- [ ] T007 [P] [US2] `tests/test_session.py::test_fragmentation_roundtrip` —
  fragment outbound (0x5A), flip to inbound (0xDA), reassemble → original frame.
- [ ] T008 [P] [US2] `tests/test_session.py::test_build_parse_roundtrip` —
  `parse_auth_message(build_auth_message(...))` preserves type/lock-token/body.

### Implementation for User Story 2

- [ ] T009 [US2] Migrate `fragment_auth_message`, `assemble_auth_fragments`, and
  `parse_auth_message` — unchanged.

**Checkpoint**: US1 AND US2 verified.

## Phase 5: User Story 3 — Protect control payloads (Priority: P2)

**Goal**: AES-CCM encrypt/decrypt round-trip with the session key/nonce.

### Tests for User Story 3

- [ ] T010 [P] [US3] `tests/test_session.py::test_control_payload_roundtrip` —
  `decrypt(encrypt(pt)) == pt` with a throwaway key/nonce; ciphertext is
  `len(pt) + 4` (short tag). No captured session secret used.

### Implementation for User Story 3

- [ ] T011 [US3] Migrate `encrypt_control_payload` / `decrypt_control_payload` —
  unchanged.

**Checkpoint**: All pure-logic stories verified.

## Phase 6: Live Orchestration (migrated, not unit-tested)

- [ ] T012 Migrate `run_authenticated_lock_operation` unchanged — the async flow
  that sequences the app's pre-auth steps (MTU, data-length, GATT-caching preamble,
  CCCD ordering), performs the handshake, and dispatches the operation. Validated
  live (Principle V); excluded from unit tests (needs a real BLE controller).

## Phase 7: Polish & Cross-Cutting

- [ ] T013 Extend `aqara_u200_ble/__init__.py` with the handshake/session surface
  (CRC, build/parse/fragment/assemble, AES-CCM, `SessionMaterial`, UUID + order
  constants, `run_authenticated_lock_operation`).
- [ ] T014 [P] Author `docs/protocol/auth-handshake.md`: header layout, the
  CRC-16/ARC field (with the wall story), and fragmentation.
- [ ] T015 Secret-hygiene sweep: confirm no session key/nonce/token/personal
  capture in `session.py`, tests, or docs (Principle I).
- [ ] T016 [P] `ruff check` + `mypy --strict` clean; `pytest` green (no network).
  Behavior-preserving style/type cleanups only, pinned by the tests (Principle II).

## Dependencies & Execution Order

- Setup → Foundational (constants/CRC table) blocks the stories.
- US1 (build/CRC) is the MVP and the breakthrough; US2 (fragmentation) and US3
  (AES-CCM) verify on top. The live flow (Phase 6) is migrated after the pure logic.
- Polish (exports, docs, sweep, gates) last.

## Notes

- No wire/crypto change (Principle II); the CRC vector and round-trips pin behavior.
- `session.py` closes the internal dependency graph (imports 001/002/003); its
  outputs feed the end-to-end flow (feature 005).
