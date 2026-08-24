# Implementation Plan: Cloud login & key derivation

**Branch**: `feature/001-cloud-kdf-login` | **Date**: 2026-08-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-cloud-kdf-login/spec.md`

**Note**: Retrospective plan. The module already exists and was verified live; this
plan documents the design as it stands so future changes have a Constitution gate to
pass through. Migration of the existing, unchanged code is the implementation step.

## Summary

Provide a headless Python client for the Aqara cloud that (a) logs an account in,
(b) signs every authenticated request exactly as the official app does, and
(c) drives the two BLE-session key-exchange endpoints (`publickey`, `verify`).
The technical approach reproduces the app's signing formula
(`Sign = MD5("Appid=…&Nonce=…&Time=…&Token=…&{body}&{appkey}")`, token omitted on
login), its RSA + AES-128-GCM login envelope, and its `x-aes128gcm` body encoding —
all reconstructed from instrumentation and confirmed against the live service.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: `cryptography>=43` (RSA-OAEP/PKCS1, AES-GCM). Standard
library for hashing (MD5/SHA-256/HMAC), HKDF, and HTTP (`urllib.request`) — no
third-party HTTP client, keeping the surface small and auditable.

**Storage**: None. All secrets are passed in by the caller at runtime and never
persisted (Constitution Principle I).

**Testing**: `pytest`. Unit tests cover pure logic only — `compute_sign`,
`compute_nonce`, HKDF vectors, `x-aes128gcm` encode/decode round-trips, and login
password encryption shape. No network in unit tests (Principle V).

**Target Platform**: Any OS with Python 3.11+; the cloud client is transport-only.

**Project Type**: Library (single package `aqara_ble`).

**Performance Goals**: Not performance-sensitive; one request per key-exchange step.
Correctness and fidelity dominate.

**Constraints**: Signature MUST be computed over plaintext body even when the wire
body is encrypted. Region endpoint is an explicit input. No secret in logs.

**Scale/Scope**: One module (`kdf.py`, ~700 lines) exposing HKDF helpers, the signer
factory, login, the `x-aes128gcm` codec, and the three cloud calls
(`cloud_get_public_key`, `cloud_verify`, `get_session_material`).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|-----------|------|--------|
| I. Security & Secret Hygiene | No secret constant in code; all sensitive values are parameters; nothing logged | ✅ PASS — module is parameterized; `.env` supplies values at call sites, not here |
| II. Protocol Fidelity | Signing/login/encoding reproduce the app byte-for-byte; changes need evidence | ✅ PASS — migrating verified code unchanged; wire behavior preserved |
| III. Spec-Driven Development | Spec + plan precede implementation | ✅ PASS — spec.md approved, this plan gates the migration |
| IV. Evidence & Reproducibility | Behavior backed by sanitized evidence, reproducible from zero | ✅ PASS — see `docs/protocol/cloud-api.md`; tutorials cover credential capture |
| V. Quality & Standards | pyproject, typed API, pure-logic tests, no network in unit tests | ✅ PASS — `py.typed` shipped; unit tests target pure functions only |
| VI. Branch & Change Discipline | Prefixed branch, `--no-ff` merge | ✅ PASS — on `feature/001-cloud-kdf-login` |

No violations. Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/001-cloud-kdf-login/
├── plan.md              # This file
├── spec.md              # Feature specification (retrospective)
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # /speckit-tasks output (created next)
```

### Source Code (repository root)

```text
aqara_ble/
├── __init__.py          # Public exports
├── kdf.py               # THIS FEATURE — cloud client: HKDF, signer, login,
│                        #   x-aes128gcm codec, publickey/verify calls
└── py.typed             # PEP 561 typing marker

tests/
└── test_kdf.py          # Pure-logic unit tests (sign, nonce, hkdf, codec)

docs/protocol/
└── cloud-api.md         # Wire contract: signing formula, login envelope, endpoints
```

**Structure Decision**: Single library package. `kdf.py` is self-contained (stdlib
HTTP + `cryptography`), so it migrates as one unit with its focused unit-test module.
Later features (002 BLE handshake, 003 control channel) consume its outputs but do
not modify it.

## Complexity Tracking

> No Constitution Check violations. Section intentionally empty.
