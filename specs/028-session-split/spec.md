# Feature Specification: Split session.py — extract framing + control codec leaves

**Feature Branch**: `chore/028-session-split`

**Created**: 2026-08-21

**Status**: Draft

**Input**: User description: "Cleanup phase 2c — split session.py (851 LOC): extract the pure wire framing (CRC-16 + auth-message build/fragment/assemble/parse) into framing.py and the AES-CCM control codec into control_codec.py, leaving session.py as the handshake orchestrator. Pure move: no value/wire/crypto change, orchestrator untouched, public API unchanged, tests green. Real-lock actuation verification is deferred to the next physical test (user not with the lock)."

## Overview

`aqara_ble/session.py` mixed pure, byte-exact wire logic (the CRC-16/ARC
table + `crc16_aqara`, the `0610`/`0710` auth-message builder, the 5a/da fragment
(de)serialisers, and the AES-CCM control codec) with the large asynchronous
`run_authenticated_lock_operation` orchestrator that drives the real BLE
handshake. This feature moves the pure logic into two leaf modules —
`framing.py` and `control_codec.py` — and leaves the orchestrator **untouched**
(same code, same call sites, now importing the framing/codec from the leaves).

It is a pure relocation: every value and algorithm is byte-identical, the public
API is unchanged, and no wire byte, frame, CRC, or cryptographic path changes
(Constitution Principle II). Because the actuation path is fidelity-critical and
cannot be exercised without the physical lock, **real-lock lock/unlock
verification is explicitly deferred to the next physical test** (the user was not
with the lock); unit tests + CI prove byte-identity of the pure logic, not the
live radio path.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Framing and codec are separated from the orchestrator (Priority: P1)

As a maintainer, I need the byte-exact framing and cipher to live in small pure
modules, so the fidelity-critical core is readable and unit-testable apart from
the 300-line async orchestrator.

**Why this priority**: This separation is the goal — isolating the wire core from
the handshake choreography and shrinking the giant module.

**Independent Test**: `framing.py` and `control_codec.py` import no other package
module and no I/O; `session.py` defines none of the moved functions and imports
them from the leaves; the orchestrator body is unchanged.

**Acceptance Scenarios**:

1. **Given** the split, **When** the leaves are inspected, **Then** `framing.py`
   holds the CRC table + `crc16_aqara` + auth-message build/fragment/assemble/parse
   + `AuthMessage`, `control_codec.py` holds encrypt/decrypt of the control
   payload, and neither imports another package module or performs network/radio I/O.
2. **Given** the split, **When** `session.py` is inspected, **Then** it defines
   none of the moved functions, imports them from the leaves, and its
   `run_authenticated_lock_operation` orchestrator is byte-for-byte the same logic
   as before (only its import sources changed).

---

### User Story 2 - Nothing observable changes for consumers (Priority: P1)

As a consumer (Home Assistant, the CLI, tests), I must see no change: identical
public API and byte-identical framing/cipher output.

**Why this priority**: Fidelity is non-negotiable (Principle II).

**Independent Test**: `__all__` unchanged; deterministic outputs (a CRC value, a
build→parse round-trip, a fragment→assemble round-trip, an AES-CCM
encrypt→decrypt round-trip) identical to pre-split; the full suite passes with no
behavioural test edits.

**Acceptance Scenarios**:

1. **Given** the moved functions, **When** deterministic outputs are compared to
   pre-split values, **Then** they are identical.
2. **Given** the public package, **When** `__all__` is enumerated, **Then** it is
   the same set as before (0 added, 0 removed).
3. **Given** existing tests that import framing helpers from `aqara_ble` or
   from `aqara_ble.session`, **When** they run, **Then** they pass unchanged —
   the orchestrator still imports (and thus re-exposes) the helpers it uses, and
   `__init__` sources them from the leaves.

### Edge Cases

- Tests import `assemble_auth_fragments`/`fragment_auth_message`/
  `build_auth_message`/`parse_auth_message` from `aqara_ble.session`; those are
  used by the orchestrator so they remain module attributes of `session` and keep
  resolving. `crc16_aqara` is imported top-level and sourced from `framing`.
- `control_codec` keeps the lazy `cryptography` import inside the functions, so
  importing the module never requires the optional dependency.
- **Real-lock behaviour is NOT verified here** — deferred to the physical test.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `aqara_ble/framing.py` MUST contain `AuthMessage`, the CRC-16
  table, `crc16_aqara`, `build_auth_message`, `fragment_auth_message`,
  `assemble_auth_fragments`, `parse_auth_message` — pure, no package import.
- **FR-002**: `aqara_ble/control_codec.py` MUST contain
  `encrypt_control_payload` and `decrypt_control_payload` (lazy `cryptography`
  import preserved), pure, no package import.
- **FR-003**: `session.py` MUST define none of the moved functions, MUST import the
  ones the orchestrator uses from the leaves, and MUST leave
  `run_authenticated_lock_operation` (and its helpers) logically unchanged.
- **FR-004**: Every moved function/constant MUST be byte-identical to its previous
  definition (CRC table, header layout, fragment sequencing, AES-CCM params).
- **FR-005**: The public `__all__` MUST export exactly the same names as before.
- **FR-006**: No wire byte, frame, CRC, or cryptographic path may change.
- **FR-007**: The full test suite AND the secret-hygiene guard MUST pass; ruff and
  mypy (local) MUST be clean.
- **FR-008**: Real-lock actuation (lock/unlock) verification is deferred to the
  next physical test and MUST be recorded as pending; this feature does not claim
  live-radio verification.

### Key Entities *(include if feature involves data)*

- **Wire framing**: CRC-16 + the auth-message header/body layout + fragmentation —
  fidelity-critical, deterministic.
- **Control codec**: AES-CCM (tag_length=4, empty AAD) encrypt/decrypt.
- **framing.py / control_codec.py**: the new leaf homes.
- **session.py**: the handshake orchestrator (unchanged logic).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `framing.py` and `control_codec.py` each contain 0 imports of other
  `aqara_ble` modules and 0 network/radio I/O.
- **SC-002**: `session.py` contains 0 definitions of the moved functions.
- **SC-003**: Deterministic framing/codec outputs are 100% identical before/after.
- **SC-004**: `aqara_ble.__all__` is identical before/after.
- **SC-005**: Full suite passes (same count, 0 skipped) + guard; ruff + mypy clean.
- **SC-006**: A pending "verify real-lock lock/unlock at the physical test" item is
  recorded (memory / physical-test checklist).

## Assumptions

- The orchestrator is the risky part and is deliberately left untouched; only the
  pure leaves are extracted, so the live handshake choreography is unchanged.
- `__init__` sources the moved names from the leaves (single source of truth);
  `session` re-exposes those the orchestrator uses so existing
  `from aqara_ble.session import ...` test imports keep resolving.
- The session-only connection-tuning constants and `SessionMaterial` stay in
  `session.py` (not identity/framing/codec data).
- Real-device verification is a separate, user-gated physical step; byte-identity
  via tests + CI is the strongest guarantee obtainable without the lock.

## Out of Scope

- Any change to `run_authenticated_lock_operation`'s behaviour or structure.
- Dead-code removal, `__all__` slimming, docs-rot cleanup (later phases).
- Real-lock verification (deferred to the physical test).
