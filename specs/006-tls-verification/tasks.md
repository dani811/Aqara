---
description: "Task list for feature 006 — TLS certificate verification for cloud requests"
---

# Tasks: TLS certificate verification for cloud requests

**Input**: Design documents from `specs/006-tls-verification/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md,
contracts/tls-policy.md, quickstart.md. Features 001–005 merged.

**Tests**: INCLUDED — the spec requires them (SC-006) and they are pure policy
assertions with no network I/O (Constitution Principle V).

**Organization**: Grouped by user story. US1 (secure by default) is the MVP and
delivers the fix on its own; US2 (opt-out) and US3 (actionable error) make it
livable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable (different files, no dependencies)
- **[Story]**: US1 secure default · US2 explicit opt-out · US3 actionable failure

## Path Conventions

Library layout: package at `aqara_u200_ble/`, tests at `tests/`, docs at `docs/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the ground truth the fix depends on.

- [X] T001 Verify `aqara_u200_ble/kdf.py` is the only SSL construction site —
  `grep -rn "ssl\." aqara_u200_ble --include="*.py"` returns solely the
  `_post_json` context block (FR-007 precondition).
- [X] T002 Confirm no new dependency is required: the fix uses only `ssl`, `os`,
  `sys`, already imported in `aqara_u200_ble/kdf.py`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The single policy decision point every user story builds on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T003 Add the truthy-value constant `_TRUTHY_ENV_VALUES` and the flag name
  constant `_INSECURE_TLS_ENV = "U200_INSECURE_TLS"` near the other module
  constants in `aqara_u200_ble/kdf.py`.
- [X] T004 Add the private factory `_tls_context() -> ssl.SSLContext` to
  `aqara_u200_ble/kdf.py`, returning `ssl.create_default_context()` unchanged,
  with a docstring stating the policy and the opt-out (data-model.md).

**Checkpoint**: A single function owns the policy; call sites can adopt it.

---

## Phase 3: User Story 1 — Cloud calls are authenticated by default (Priority: P1) 🎯 MVP

**Goal**: Every cloud request verifies chain and hostname, with no override set.

**Independent Test**: With a clean environment, `_tls_context()` returns a context
with `check_hostname=True` and `verify_mode=CERT_REQUIRED`; all existing cloud
behaviour is otherwise unchanged.

### Tests for User Story 1

- [X] T005 [P] [US1] `tests/test_kdf.py::test_tls_context_verifies_by_default` —
  with `U200_INSECURE_TLS` deleted from the environment, assert
  `check_hostname is True` and `verify_mode is ssl.CERT_REQUIRED`.
- [X] T006 [P] [US1] `tests/test_kdf.py::test_tls_context_emits_no_warning_by_default`
  — assert nothing is written to stderr when the policy is secure.

### Implementation for User Story 1

- [X] T007 [US1] Replace the inline three-line insecure context in `_post_json`
  (`aqara_u200_ble/kdf.py`) with `ssl_context = _tls_context()`, deleting the
  "TEMPORARY for development/testing on macOS" comment and its override lines.
- [X] T008 [US1] Confirm nothing else in the request changes — same `data`,
  headers, encoding negotiation, and timeout path (FR-006).

**Checkpoint**: The defect is fixed; the library is secure by default.

---

## Phase 4: User Story 2 — A deliberate, visible opt-out (Priority: P2)

**Goal**: `U200_INSECURE_TLS` downgrades the policy for explicit truthy values
only, and never silently.

**Independent Test**: Set the flag to `1` → verification off plus a stderr
warning; set it to `0`/empty/unset → verification on, no warning.

### Tests for User Story 2

- [X] T009 [P] [US2] `tests/test_kdf.py::test_tls_context_opt_out_disables_verification`
  — with `U200_INSECURE_TLS=1`, assert `check_hostname is False` and
  `verify_mode is ssl.CERT_NONE`.
- [X] T010 [P] [US2] `tests/test_kdf.py::test_tls_context_opt_out_accepts_documented_values`
  — parametrized over `1`, `true`, `TRUE`, `  yes  `, `on`: all downgrade.
- [X] T011 [P] [US2] `tests/test_kdf.py::test_tls_context_falsey_values_stay_secure`
  — parametrized over `""`, `0`, `false`, `no`, `off`, `maybe`: all stay
  `CERT_REQUIRED` (fail-safe parsing, FR-003).
- [X] T012 [P] [US2] `tests/test_kdf.py::test_tls_context_opt_out_warns` — assert
  the stderr text names `U200_INSECURE_TLS` (FR-004).

### Implementation for User Story 2

- [X] T013 [US2] In `_tls_context()` (`aqara_u200_ble/kdf.py`), read the flag,
  normalize with `.strip().lower()`, and when affirmative set `check_hostname =
  False` **before** `verify_mode = ssl.CERT_NONE`, printing the warning to stderr.

**Checkpoint**: Blocked users have a supported, loud escape hatch.

---

## Phase 5: User Story 3 — A failure that explains itself (Priority: P3)

**Goal**: A certificate failure reports the cause and names the opt-out.

**Independent Test**: A `URLError` whose `.reason` is an
`ssl.SSLCertVerificationError` produces a `RuntimeError` naming both the failure
and `U200_INSECURE_TLS`.

### Tests for User Story 3

- [X] T014 [P] [US3] `tests/test_kdf.py::test_certificate_failure_message_names_the_flag`
  — monkeypatch `urlrequest.urlopen` in `aqara_u200_ble.kdf` to raise
  `URLError(ssl.SSLCertVerificationError(...))`, call `_post_json`, and assert the
  raised `RuntimeError` mentions the URL, the verification failure, and
  `U200_INSECURE_TLS` (no socket is opened).

### Implementation for User Story 3

- [X] T015 [US3] In `_post_json`'s `except urlerror.URLError` handler
  (`aqara_u200_ble/kdf.py`), detect `isinstance(exc.reason,
  ssl.SSLCertVerificationError)` and raise the enriched message per
  `contracts/tls-policy.md`; leave all other `URLError` cases byte-identical.

**Checkpoint**: All three stories functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T016 [P] Document `U200_INSECURE_TLS` in `.env.example` with an explicit
  "removes MITM protection — never use on an untrusted network" warning (FR-008).
- [X] T017 [P] Add a transport-security section to `docs/protocol/cloud-api.md`
  stating that cloud calls are verified and how the opt-out behaves.
- [X] T018 [P] Add a troubleshooting entry for certificate failures to
  `docs/tutorials/01-getting-started.md`, pointing at the flag as a last resort.
- [X] T019 Close roadmap debt item 1 in `docs/roadmap.md` — move it from "Pending
  work" to a resolved note referencing this feature.
- [X] T020 Run the quality gates: `ruff check . && ruff format --check .`,
  `mypy aqara_u200_ble`, `pytest` (SC-006).
- [X] T021 Run `specs/006-tls-verification/quickstart.md` scenarios 1–3 and record
  the observed output.
- [X] T022 Secret scan the diff (Principle I) — no credentials, MACs, or IDs.
  Clean: the only matches are pre-existing `.env.example` placeholders and the
  throwaway `FAKE_APPKEY` test fixture.
- [ ] T023 Merge into `develop` with `--no-ff` (Principle VI) — awaiting the
  maintainer's go-ahead; the branch is committed and green.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: needs Phase 1 — BLOCKS all user stories (every
  story asserts on `_tls_context()`).
- **US1 (Phase 3)**: needs Phase 2. Delivers the fix alone.
- **US2 (Phase 4)**: needs Phase 2; extends the same factory as US1, so it
  touches the same function — sequence it after US1 rather than beside it.
- **US3 (Phase 5)**: needs Phase 2 only; touches `_post_json`'s error handler,
  independent of US2's body.
- **Polish (Phase 6)**: after the stories being shipped are complete.

### Within Each User Story

Tests are written first and must fail before the implementation task lands.

### Parallel Opportunities

- All test tasks inside a story ([P]) are independent test functions and can be
  written together.
- T016–T018 touch three different documentation files and are fully parallel.
- US2 and US3 implementation tasks (T013, T015) touch different functions in the
  same file — parallel in principle, but a single small file makes sequential
  editing simpler.

---

## Parallel Example: User Story 2

```bash
# Write US2's four policy tests together (all in tests/test_kdf.py, independent):
Task: "test_tls_context_opt_out_disables_verification"
Task: "test_tls_context_opt_out_accepts_documented_values"
Task: "test_tls_context_falsey_values_stay_secure"
Task: "test_tls_context_opt_out_warns"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup → Phase 2 Foundational → Phase 3 US1.
2. **STOP and VALIDATE**: quickstart scenario 2 plus the full suite. At this
   point the security debt is closed, at the cost of blocking users with a broken
   trust store.

### Incremental Delivery

1. US1 → secure by default (the fix).
2. US2 → the documented escape hatch, so no one patches the source.
3. US3 → the message that turns a confusing failure into a next step.
4. Polish → docs, roadmap, gates, merge.

---

## Notes

- This is a deliberate behaviour change, unlike the 001–005 verbatim migration;
  the justification lives in plan.md ("Behaviour-change justification").
- No wire bytes change: on a non-hostile network the traffic is identical before
  and after (FR-006).
- Commit per phase, keeping the branch history readable.
