# Implementation Plan: Login password MD5 fix

**Branch**: `feature/008-login-password-md5` | **Date**: 2026-08-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/008-login-password-md5/spec.md`

## Summary

The account-login request must encrypt `MD5(password)` (lowercase hex, 32 ASCII
chars) with the login RSA key, not the raw password. Applying that one transform
in `encrypt_login_password` turns the perpetual `code=810` into a real `code=0`
token, satisfying Feature 001's User Story 2. The change is behavior-altering at
the wire level and is therefore backed by captured evidence (a Frida capture of
`Cipher.doFinal`). Scope is the login envelope only; a regression test pins the
transform, and documentation is corrected to match verified reality.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: `cryptography` (RSA PKCS#1 v1.5, AES-GCM, HKDF); standard-library `hashlib`, `urllib`

**Storage**: `.env` (git-ignored) for installation identifiers and tokens; no database

**Testing**: pytest; unit tests are network-free (Constitution Principle V)

**Target Platform**: cross-platform CPython (developed on macOS)

**Project Type**: single Python library (`aqara_ble`) with companion tools

**Performance Goals**: N/A (a single login round-trip)

**Constraints**: no network/radio I/O in unit tests; no real secrets in the repo; password never in clear on the wire, in logs, or on disk

**Scale/Scope**: one function (`encrypt_login_password`), its `login` caller, one tool, three docs, one reference capture script

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Security & Secret Hygiene** — ✅ PASS. No secret committed. The test uses a
  throwaway non-credential password; the real test-account password used to verify
  live was never written to the repo. The password is hashed then RSA-encrypted,
  never logged in clear.
- **II. Protocol Fidelity** — ✅ PASS. The change alters wire bytes (the `password`
  field), justified by captured evidence: the Frida capture showing the app feeds
  `MD5(password)` (lowercase hex) into `Cipher.doFinal` (RSA). Verified end-to-end
  against the real EU server (`code=0`).
- **III. Spec-Driven Development** — ✅ PASS, with the honesty caveat this principle
  requires: this spec/plan is **retrospective** and labelled as such; it documents a
  fix reconstructed after the fact, not designed up front.
- **IV. Evidence & Reproducibility** — ✅ PASS. Evidence is the original RE project's
  capture note and is reproduced generically: for any password, its lowercase-hex MD5
  matches the captured RSA-input shape. `capture_login_flow.js` lets a third party
  re-capture it. The captured plaintext password is a real test credential and is not
  reproduced in the repo (Principle I).
- **V. Quality & Standards** — ✅ PASS. Pure transform covered by a deterministic,
  network-free test; typed public API preserved; ruff clean.
- **VI. Branch & Change Discipline** — ✅ PASS. Work is on `feature/008-login-password-md5`;
  merges to trunk with `--no-ff`.

No violations → Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/008-login-password-md5/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── login-envelope.md  # Phase 1 output
├── checklists/
│   └── requirements.md  # from /speckit-specify
└── tasks.md             # from /speckit-tasks
```

### Source Code (repository root)

```text
aqara_ble/
└── kdf.py               # encrypt_login_password (the fix) + login (docstring)

tools/
├── refresh_token.py     # 810 error message corrected
├── README.md            # login-status wording corrected
└── capture_login_flow.js  # reference capture (new)

docs/protocol/
└── cloud-api.md         # account-login section corrected

tests/
└── test_kdf.py          # login tests + the MD5-plaintext regression pin
```

**Structure Decision**: Single-library layout (existing). The fix lives in the
one crypto module `aqara_ble/kdf.py`; everything else is tests and docs that
track the same fact.

## Complexity Tracking

> No Constitution Check violations. Nothing to justify.
