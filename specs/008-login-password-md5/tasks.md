---

description: "Task list for feature 008 — login password MD5 fix"
---

# Tasks: Login password MD5 fix

**Input**: Design documents from `/specs/008-login-password-md5/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included — FR-006 explicitly requires a regression test pinning the RSA plaintext.

**Status**: Retrospective. The fix and its tests already exist on
`feature/008-login-password-md5`; tasks are recorded as completed (`[X]`) to
document the unit of change, per Constitution Principle III.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1)

---

## Phase 1: Setup

**Purpose**: No new project scaffolding — this is a fix within an existing library.

- [X] T001 Confirm the fix lands on branch `feature/008-login-password-md5` (Constitution VI)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish the evidence the fix depends on.

- [X] T002 Confirm the captured RSA input for a test password equals its lowercase-hex MD5, not the raw password (research.md)

**Checkpoint**: Evidence confirmed — the transform can be implemented against a known target.

---

## Phase 3: User Story 1 - Mint a token from account + password, headless (Priority: P1) 🎯 MVP

**Goal**: Correct credentials return a usable token; wrong credentials surface an authentication failure.

**Independent Test**: run `tools/refresh_token.py` with correct credentials against the real EU server → `code=0` + JWT; with a wrong password → reported `code=810` auth failure.

### Tests for User Story 1

- [X] T003 [P] [US1] Pin the RSA plaintext as `MD5(password)` lowercase hex, decrypting our own ciphertext with a matched throwaway key and a throwaway non-credential password, in tests/test_kdf.py
- [X] T004 [P] [US1] Assert the login body carries RSA-shaped ciphertext (128 bytes) and never the raw password, in tests/test_kdf.py
- [X] T005 [P] [US1] Assert the login is unauthenticated (no Token/UserId/Requestid; `Token=` omitted) and that `--sign-with-stored` adds identity headers, in tests/test_kdf.py
- [X] T006 [P] [US1] Assert `login()` returns the token (and userId) and surfaces `code=810` distinguishably, in tests/test_kdf.py

### Implementation for User Story 1

- [X] T007 [US1] Fix `encrypt_login_password` to RSA-encrypt `MD5(password).hexdigest()` (lowercase hex), in aqara_u200_ble/kdf.py (FR-001)
- [X] T008 [US1] Update `kdf.login` docstring to record the verified `code=0` status and the MD5 transform, in aqara_u200_ble/kdf.py (FR-007)

**Checkpoint**: Autonomous login returns a real token, verified end-to-end (SC-001..SC-003).

---

## Phase 4: Polish & Cross-Cutting Concerns

**Purpose**: Documentation and messaging that track the same fact (FR-005, FR-007).

- [X] T009 [P] Correct the `code=810` message so it does not claim "wrong password" alone (wrong password OR unregistered account), in tools/refresh_token.py (FR-005)
- [X] T010 [P] Correct the tool README login-status wording, in tools/README.md (FR-007)
- [X] T011 [P] Correct the account-login section of docs/protocol/cloud-api.md (FR-007)
- [X] T012 [P] Add the reference capture hook tools/capture_login_flow.js (FR-006 evidence path)
- [X] T013 Run the network-free suite and ruff; confirm green (SC-004)

---

## Dependencies & Execution Order

- **Setup (Phase 1)** → **Foundational (Phase 2)** → **User Story 1 (Phase 3)** → **Polish (Phase 4)**.
- T007 depends on T002 (evidence) and is validated by T003–T006.
- T009–T012 are independent of each other ([P]); T013 runs last.

## Implementation Strategy

Single-story MVP: the fix (T007) plus its regression pin (T003) is the whole
deliverable's core; the remaining tasks are the tests that guard it and the docs
that stop the old false claim from returning.

## Notes

- Retrospective: all tasks completed on `feature/008-login-password-md5`.
- Out of scope (tracked elsewhere): the lock open/status command work (pack + Mijia CRC trailer) and the US/CN region-URL corrections.
