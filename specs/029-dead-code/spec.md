# Feature Specification: Dead-code removal + docs-rot cleanup

**Feature Branch**: `chore/029-dead-code`

**Created**: 2026-08-21

**Status**: Draft

**Input**: User description: "Cleanup — remove the genuinely-dead code (accidental leftovers with no consumers) and fix references to docs that don't exist, to leave the tree clean before the physical test. Keep intentional-but-unused public API (build_cloud_auth_headers, operations_catalog, volume) and flag it for a separate decision. No behavioural change."

## Overview

The architecture/dead-code analysis found a small set of **accidental** dead
symbols — leftovers with no consumer anywhere (not even tests) and no coherent
purpose — plus code comments pointing at working docs that were never committed
(`ble-control-handoff.md`, `protocolo.md`). This feature removes the accidental
dead symbols, repoints the dangling doc references to the canonical
`docs/reference/`, and corrects `gatt-map.md` where it described now-removed
constants. It is behaviour-preserving: no wire byte, framing, or crypto changes,
and no live code path loses a symbol it uses.

Intentional-but-currently-unused **public** API (the `build_cloud_auth_headers`
helper, the `operations_catalog` module, the `volume` module) is deliberately
**kept** — removing it is an API-surface product decision, not dead-code cleanup —
and flagged for a separate decision.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Accidental dead symbols are gone (Priority: P1)

As a maintainer, I want the accidental leftovers removed so the public surface and
the modules reflect what the library actually is.

**Why this priority**: These symbols are pure noise — unreferenced, purposeless —
and they inflate the API and the modules.

**Independent Test**: Each removed symbol is absent from the package and from
`__all__`; the full suite passes (nothing referenced them).

**Acceptance Scenarios**:

1. **Given** the removal, **When** the package is imported, **Then**
   `ATTPacket`, the ATT handle constants (`AUTH_WRITE`, `AUTH_NOTIFY`,
   `CONTROL_WRITE`, `CONTROL_NOTIFY`, `BULK_WRITE`, `BULK_NOTIFY`,
   `ATT_CONTROL_WRITE`, `ATT_CONTROL_NOTIFY`), `AdvancedGattClient`, and
   `LockOperation.LEGACY_UNVERIFIED_200320` no longer exist.
2. **Given** the removal, **When** `__all__` is enumerated, **Then** the removed
   public names are gone and every remaining name still resolves.
3. **Given** the full test suite, **When** it runs, **Then** it passes unchanged
   (no test referenced the removed symbols).

---

### User Story 2 - No references to non-existent docs (Priority: P2)

As a reader following the code, I need every doc reference to resolve, per the
Evidence & Reproducibility principle.

**Why this priority**: Dangling references mislead a third party trying to
reproduce the work; lower than removing dead code but still a correctness issue.

**Independent Test**: No tracked source file under `aqara_u200_ble/` or `tools/`
references `ble-control-handoff.md` or `protocolo.md`; `gatt-map.md` no longer
labels cells with removed code-constant names.

**Acceptance Scenarios**:

1. **Given** the cleanup, **When** the code/tools are searched for
   `ble-control-handoff.md` / `protocolo.md`, **Then** there are 0 matches (they
   point to `docs/reference/` instead).
2. **Given** `gatt-map.md`, **When** it is read, **Then** it no longer presents the
   removed constants as symbolic references (handles are described as
   informational; characteristics are resolved by UUID).

### Edge Cases

- Historical spec files under `specs/` may still mention the old working-doc names
  as a record of what was known at the time; those are retrospective and left
  untouched (only active code/tools/doc-map are cleaned).
- `ControlRequest`, `control_command_name`, `parse_control_request`, `valid_crc`
  stay (they have tests / a consumer) — only the truly-unreferenced protocol
  symbols are removed.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Remove the accidental dead symbols: `protocol.ATTPacket` and the ATT
  handle constants; `gatt.AdvancedGattClient`; `LockOperation.LEGACY_UNVERIFIED_200320`.
- **FR-002**: Remove the corresponding names from `__all__`, keeping every
  `*_UUID` name and all still-live symbols.
- **FR-003**: Repoint every `ble-control-handoff.md` / `protocolo.md` reference in
  `aqara_u200_ble/` and `tools/` to `docs/reference/`.
- **FR-004**: Update `docs/devices/u200/gatt-map.md` so it no longer presents the
  removed constants as code symbols (handles = informational; UUID-resolved).
- **FR-005**: No wire byte, framing, or cryptographic path changes; no live code
  path loses a symbol it uses.
- **FR-006**: The full test suite AND the secret-hygiene guard MUST pass; ruff and
  mypy (local) MUST be clean.
- **FR-007**: Intentional-but-unused public API (`build_cloud_auth_headers`,
  `operations_catalog`, `volume`) is KEPT and recorded as a separate decision.

### Key Entities *(include if feature involves data)*

- **Accidental dead symbols**: unreferenced leftovers with no purpose (ATT handle
  constants, `ATTPacket`, `AdvancedGattClient`, one legacy enum member).
- **Dangling doc references**: comments citing uncommitted working docs.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 0 occurrences of the removed symbols in the package; `__all__`
  shrinks from 94 to 85 with every remaining name resolving.
- **SC-002**: 0 references to `ble-control-handoff.md` / `protocolo.md` in
  `aqara_u200_ble/` and `tools/`.
- **SC-003**: `protocol.py` and `gatt.py` shrink (no dead defs) with the full suite
  still green (226 tests) + guard; ruff + mypy clean.
- **SC-004**: No behavioural or wire change (framing/codec/crypto outputs unchanged).

## Assumptions

- Removing accidental dead **public** names (ATT constants, `ATTPacket`) is
  acceptable cleanup even though it shrinks `__all__`; they had no consumers and no
  coherent purpose, and the canonical public path is the facade.
- `build_cloud_auth_headers`, `operations_catalog` and `volume` are intentional
  (documented/tested) surface, so they are kept pending an explicit product
  decision — not swept up as dead code.
- Spec-file mentions of the old working docs are historical record and are left as-is.

## Out of Scope

- Removing/-slimming intentional public API (`operations_catalog`, `volume`,
  `build_cloud_auth_headers`), deduplicating the operate-bytes or the two CRC
  implementations — flagged for a separate decision.
- Any behavioural change or real-lock verification.
