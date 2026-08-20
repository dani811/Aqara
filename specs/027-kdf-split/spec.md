# Feature Specification: Split kdf.py into cloud_crypto (pure) + kdf (HTTP client)

**Feature Branch**: `chore/027-kdf-split`

**Created**: 2026-08-20

**Status**: Draft

**Input**: User description: "Cleanup phase 2b — split kdf.py (842 LOC): extract the pure cryptography (HKDF, Sign, RSA login-password, x-aes128gcm codec) into cloud_crypto.py, leaving kdf.py as the HTTP client / orchestration layer. Pure move: no value/wire/crypto change, public API unchanged, tests green."

## Overview

`aqara_u200_ble/kdf.py` (842 LOC) was misnamed and mixed two concerns: pure,
deterministic cryptography (HKDF-SHA256, the native request `Sign`, the RSA-1024
login-password envelope, the `x-aes128gcm` body codec) and the network client
(TLS, `urlopen`, endpoints, `login`/`cloud_get_public_key`/`cloud_verify`/
`get_session_material`). Co-locating byte-exact crypto with live HTTP made the
crypto harder to reason about and impossible to import without the HTTP surface.

This feature extracts the pure crypto into a new leaf module
`aqara_u200_ble/cloud_crypto.py` (no network, no `kdf` import). `kdf.py` becomes
the HTTP client/orchestration layer and imports what it needs from
`cloud_crypto`. It is a pure relocation: every value and algorithm is
byte-identical, the public API is unchanged, and no wire byte or cryptographic
path changes (Constitution Principle II).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Pure crypto is separated from network I/O (Priority: P1)

As a maintainer, I need the byte-exact cryptography to live apart from the HTTP
client so it can be read, audited, and unit-tested without any transport.

**Why this priority**: This separation is the whole point — it isolates the
fidelity-critical crypto from the I/O and shrinks the giant module.

**Independent Test**: `cloud_crypto.py` imports no other `aqara_u200_ble` module
and no `urllib`/`ssl`; `kdf.py` no longer defines any crypto primitive and imports
them from `cloud_crypto`. Both import cleanly.

**Acceptance Scenarios**:

1. **Given** the split, **When** `cloud_crypto.py` is inspected, **Then** it
   contains HKDF, Sign, RSA login-password and the `x-aes128gcm` codec, imports no
   package submodule, and performs no network/TLS I/O.
2. **Given** the split, **When** `kdf.py` is inspected, **Then** it defines no
   crypto primitive, imports the ones it uses from `cloud_crypto`, and retains the
   HTTP client, endpoints, `CloudServiceError`, and the `login`/`cloud_*`/
   `get_session_material` orchestration.

---

### User Story 2 - Nothing observable changes for consumers (Priority: P1)

As a consumer (Home Assistant, the CLI, tests), I must see no change: the public
API is identical and every cloud call behaves byte-for-byte as before.

**Why this priority**: Fidelity is non-negotiable (Principle II); a refactor that
alters crypto output or the public surface would be a regression.

**Independent Test**: `__all__` is unchanged; deterministic crypto outputs (HKDF
vector, `compute_nonce`, `compute_sign`, an `x-aes128gcm` round-trip) are
identical to pre-split; the full suite passes.

**Acceptance Scenarios**:

1. **Given** the moved functions, **When** deterministic outputs are compared to
   pre-split values, **Then** they are identical.
2. **Given** the public package, **When** `__all__` is enumerated, **Then** it is
   the same set as before (0 added, 0 removed).
3. **Given** the whole test suite, **When** it runs, **Then** it passes; the only
   test edits are import-path/monkeypatch-target updates (the RSA-key monkeypatch
   now targets `cloud_crypto`), never behavioural changes.

### Edge Cases

- The RSA login-password test monkeypatches the module-level public-key constant;
  after the move that constant lives in `cloud_crypto`, so the test must patch it
  there (patching `kdf` would silently no-op). This is covered by an import-target
  edit.
- `auth.py` imported `Signer`/`make_local_signer` from `kdf`; these are crypto and
  move, so `auth.py` imports them from `cloud_crypto` (HTTP names still from `kdf`).
- Tools/tests importing HTTP names (`login`, `REGION_BASE_URLS`, `_tls_context`,
  `_unwrap_aqara_result`) from `kdf` are unaffected (those stay in `kdf`).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A new module `aqara_u200_ble/cloud_crypto.py` MUST contain the pure
  crypto: `Signer`, `hkdf_extract/expand/sha256`, `compute_nonce/compute_sign/
  make_local_signer`, `_LOGIN_RSA_PUBKEY_DER_B64`/`encrypt_login_password`,
  `_aes128gcm_nonce`/`aes128gcm_encrypt_body`/`aes128gcm_decrypt_body`.
- **FR-002**: `cloud_crypto.py` MUST import no other `aqara_u200_ble` module and
  MUST perform no network or TLS I/O.
- **FR-003**: `kdf.py` MUST define no crypto primitive and MUST import the ones it
  uses from `cloud_crypto`; it retains the HTTP client, endpoints, error type and
  orchestration.
- **FR-004**: Every moved function/constant MUST be byte-identical to its previous
  definition (same algorithm, same bytes).
- **FR-005**: The public `__all__` MUST export exactly the same names as before,
  reachable via `from aqara_u200_ble import <name>`.
- **FR-006**: No wire byte, header, or cryptographic output may change; the diff is
  the relocation plus the corresponding imports and monkeypatch-target updates.
- **FR-007**: The full test suite AND the secret-hygiene guard MUST pass; ruff and
  mypy (run locally) MUST be clean.

### Key Entities *(include if feature involves data)*

- **Pure cloud crypto**: HKDF, Sign, RSA login-password, `x-aes128gcm` codec —
  deterministic, network-free, fidelity-critical.
- **cloud_crypto.py**: the new leaf home for that crypto.
- **kdf.py**: the cloud HTTP client / orchestration layer (kept name to avoid
  breaking `from aqara_u200_ble.kdf import ...`).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `cloud_crypto.py` contains 0 imports of any other `aqara_u200_ble`
  module and 0 `urllib`/`ssl` imports.
- **SC-002**: `kdf.py` contains 0 crypto-primitive definitions and 0 `hashlib`/
  `hmac`/`base64`/`cryptography` imports.
- **SC-003**: Deterministic crypto outputs (HKDF vector, nonce, sign, AES-GCM
  round-trip) are 100% identical before and after.
- **SC-004**: `aqara_u200_ble.__all__` is identical before and after.
- **SC-005**: The full test suite passes (same count, 0 skipped for the move) plus
  the secret-hygiene guard; ruff and mypy clean.

## Assumptions

- Keeping the module name `kdf.py` (rather than renaming to `cloud_http.py`) is the
  right risk/value trade-off: it preserves every `from aqara_u200_ble.kdf import
  ...` path (used by `auth`, tools, tests) with no churn; a rename is a separate,
  optional, cosmetic change.
- `__init__.py` imports the crypto names from `cloud_crypto` (single source of
  truth) and the HTTP names from `kdf`; the public top-level surface is unchanged.
- The HKDF helpers, though off the live session-material path (that comes from the
  cloud `/verify` response), remain public because they are part of the documented
  API and used by tests/offline analysis.

## Out of Scope

- Splitting `session.py` (phase 2c) and any dead-code removal (later phase).
- Renaming `kdf.py`, trimming `__all__`, or removing the off-path HKDF helpers.
- Any behavioural or wire-protocol change.
