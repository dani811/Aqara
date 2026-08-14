---
description: "Task list for feature 001 — Cloud login & key derivation"
---

# Tasks: Cloud login & key derivation

**Input**: Design documents from `specs/001-cloud-kdf-login/`

**Prerequisites**: plan.md (required), spec.md (required for user stories)

**Tests**: INCLUDED. The constitution (Principle V) mandates tests for pure logic
(signing, nonce, HKDF, encoding). Network calls are NOT unit-tested.

**Organization**: Tasks are grouped by user story so each can be verified
independently. This is a **retrospective migration**: the implementation already
exists and was verified live; tasks cover bringing it in unchanged, adding the
pure-logic tests, and documenting the wire contract.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 (public key), US2 (login), US3 (verify/session material)

## Path Conventions

Single library project: package at `aqara_u200_ble/`, tests at `tests/`, protocol
docs at `docs/protocol/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Packaging and tooling so the module can be imported and tested.

- [X] T001 Add `pyproject.toml` with package metadata, `cryptography>=43` runtime
  dependency, and a `dev` extra (`pytest`, `ruff`, `mypy`).
- [X] T002 [P] Create the package skeleton: `aqara_u200_ble/__init__.py` and
  `aqara_u200_ble/py.typed` (PEP 561 typed marker).
- [X] T003 [P] Configure `ruff` + `mypy` settings in `pyproject.toml`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The pure cryptographic primitives every story relies on.

**⚠️ CRITICAL**: These must land before any story's cloud call is meaningful.

- [X] T004 Migrate the HKDF-SHA256 primitives (`hkdf_extract`, `hkdf_expand`,
  `hkdf_sha256`) into `aqara_u200_ble/kdf.py` — unchanged, behavior-preserving.
- [X] T005 Migrate the request-signing core (`compute_nonce`, `compute_sign`) into
  `aqara_u200_ble/kdf.py`, preserving the exact formula and the token-omitted
  login variant (Principle II).

**Checkpoint**: Primitives importable; ready for per-story cloud calls.

---

## Phase 3: User Story 1 — Obtain a session's public key (Priority: P1) 🎯 MVP

**Goal**: Fetch a session's 65-byte SECP256R1 public key from the cloud, headless.

**Independent Test**: With valid credentials + owned device, call the public-key
retrieval and assert a 65-byte `04`-prefixed point; a mis-signed request is rejected.

### Tests for User Story 1

- [X] T006 [P] [US1] `tests/test_kdf.py::test_compute_sign_matches_documented_formula_with_token` —
  assert `compute_sign` reproduces a captured (sanitized) signature vector.
- [X] T007 [P] [US1] `tests/test_kdf.py::test_compute_nonce_is_uppercase_md5_of_request_id` — nonce
  is uppercase MD5 of the request id.

### Implementation for User Story 1

- [X] T008 [US1] Migrate the signer factory (`make_local_signer`) and auth-header
  builder (`build_cloud_auth_headers`, `_REQUIRED_AUTH_HEADERS`) into `kdf.py`.
- [X] T009 [US1] Migrate `REGION_BASE_URLS`, `_PATH_PUBLICKEY`, the HTTP helper
  (`_post_json`), result unwrapping (`_unwrap_aqara_result`), and
  `cloud_get_public_key` — unchanged.
- [X] T010 [US1] Export the public-key call and signer from
  `aqara_u200_ble/__init__.py`.

**Checkpoint**: US1 functional — public key retrievable end-to-end.

---

## Phase 4: User Story 2 — Authenticate an account without the app (Priority: P1)

**Goal**: Exchange username/password for an account token, headless.

**Independent Test**: Correct credentials → usable token; wrong password → auth
failure (not a crypto/transport error).

### Tests for User Story 2

- [X] T011 [P] [US2] `tests/test_kdf.py::test_encrypt_login_password_has_rsa1024_shape` —
  `encrypt_login_password` output has the expected RSA envelope shape.
- [X] T012 [P] [US2] `tests/test_kdf.py::test_aes128gcm_body_roundtrip` —
  `aes128gcm_encrypt_body` / `aes128gcm_decrypt_body` round-trip a known plaintext.

### Implementation for User Story 2

- [X] T013 [US2] Migrate `encrypt_login_password`, the `x-aes128gcm` codec
  (`_aes128gcm_nonce`, `aes128gcm_encrypt_body`, `aes128gcm_decrypt_body`),
  `_PATH_LOGIN`, and `login` — unchanged (Principle II).
- [X] T014 [US2] Export `login` from `aqara_u200_ble/__init__.py`.

**Checkpoint**: US1 AND US2 both work independently.

---

## Phase 5: User Story 3 — Complete the key exchange (Priority: P2)

**Goal**: Submit the lock's device public key, receive session material.

**Independent Test**: Given a device public key from a live session, verification
returns session key + nonce + verify data of documented sizes.

### Implementation for User Story 3

- [X] T015 [US3] Migrate `_PATH_VERIFY`, `cloud_verify`, and `get_session_material`
  into `kdf.py` — unchanged.
- [X] T016 [US3] Export `cloud_verify` / `get_session_material` from the package.

**Checkpoint**: All stories independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T017 [P] Author `docs/protocol/cloud-api.md`: signing formula, login envelope,
  `x-aes128gcm` encoding, endpoint set — with sanitized examples only (Principle IV).
- [X] T018 Secret-hygiene sweep: confirm no token/appkey/device id/capture appears
  in `kdf.py`, tests, or docs; all sensitive values are parameters (Principle I).
- [X] T019 [P] `mypy aqara_u200_ble/kdf.py` and `ruff check` pass clean.
- [X] T020 Run `pytest tests/test_kdf.py` — all pure-logic tests green, no network.
- [X] T021 [P] Cover FR-008 (service-level error codes): `tests/test_kdf.py::test_service_error_code_is_surfaced_with_its_details`,
  `::test_success_codes_unwrap_the_result`, `::test_payload_without_result_is_returned_whole`,
  `::test_missing_code_field_is_not_an_error` — a non-zero `code` must raise with
  code/message/endpoint and stay distinguishable from a transport failure.
  *(Added 2026-08-14 after `/speckit-analyze` found FR-008 implemented but untasked
  and untested.)*

---

## Dependencies & Execution Order

- **Setup (Phase 1)** → **Foundational (Phase 2)** blocks all stories.
- **US1** and **US2** are both P1 and independent (different call paths); either can
  be the MVP slice. **US3 (P2)** depends conceptually on a live device public key
  (feature 004) but its cloud code is independent to migrate and unit-scope.
- **Polish (Phase 6)** after stories land.

### Within Each User Story

- Tests written to assert captured/known behavior, then the unchanged code is
  brought in and the tests confirm fidelity (Principle II).
- Primitives (Phase 2) before any story call.

### Parallel Opportunities

- T002/T003 in setup; T006/T007 and T011/T012 test pairs; T017/T019/T021 in polish.

---

## Notes

- This migration must not alter wire bytes or crypto logic (Principle II). Tests
  pin the observable behavior so any drift is caught.
- Commit per phase or logical group; keep secrets out of every commit (Principle I).
