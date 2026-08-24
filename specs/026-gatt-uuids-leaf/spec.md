# Feature Specification: Fix transport→session Layering Inversion (GATT UUIDs Leaf Module)

**Feature Branch**: `chore/026-gatt-uuids-leaf`

**Created**: 2026-08-20

**Status**: Draft

**Input**: User description: "Cleanup phase 2a — Fix the transport→session layering inversion by extracting the GATT identity constants into a leaf module. transport.py imports service UUIDs from session.py (the top authenticated-protocol layer), so the lowest radio layer depends upward. Pure move/refactor: no constant value, wire byte, framing or crypto changes; public API unchanged; tests stay green."

## Overview

`aqara_ble/transport.py` (the low-level radio layer) imports
`AUTH_SERVICE_UUID`, `CONTROL_SERVICE_UUID`, `AUX_SERVICE_UUID` from
`aqara_ble/session.py` (the top authenticated-protocol/orchestration layer),
where the GATT UUID constants happen to be defined. This is a layering inversion:
the lowest layer depends on the highest one purely for identity constants, so
importing `transport` (or `scanner`/`client`) eagerly drags in
`session → auth → kdf → cryptography`, and it contradicts
[docs/architecture.md](../../docs/architecture.md) which classifies
service/characteristic UUIDs and ATT handles as **device-specific leaf data**.

This feature moves those constants into a new leaf module
(`aqara_ble/gatt_uuids.py`) with zero internal imports, and has both
`session.py` and `transport.py` import them **downward**. It is a pure
relocation: no value, wire byte, framing, or cryptographic behaviour changes, and
the public import surface stays identical.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The radio layer no longer depends on the protocol layer (Priority: P1)

As a maintainer (and as a Home Assistant integrator), I need the transport/radio
layer to stand on its own so the module graph is a clean downward DAG and the
architecture matches its own documented layer map.

**Why this priority**: This is the entire point of the refactor — removing the one
inverted edge that the architecture review flagged.

**Independent Test**: Static check that `transport.py` contains no
`from .session import ...`; and that no module imports a GATT UUID/handle constant
upward from `session`. Import `aqara_ble.gatt_uuids` and confirm it pulls in
no other package module.

**Acceptance Scenarios**:

1. **Given** the refactor, **When** the import graph is inspected, **Then**
   `transport.py` no longer imports from `session.py`, and the GATT UUID constants
   are imported from the new leaf module by every consumer.
2. **Given** the leaf module, **When** it is imported in isolation, **Then** it
   imports no other `aqara_ble` module (it is a true leaf).

---

### User Story 2 - Nothing observable changes for consumers (Priority: P1)

As a consumer of the library (Home Assistant, the CLI, tests), I must see no
change: the same names import from the same places, and the lock behaves
byte-identically.

**Why this priority**: A refactor that breaks the public API or alters wire bytes
would be worse than the inversion it fixes; fidelity is non-negotiable
(Constitution Principle II).

**Independent Test**: The public `__all__` still exports every name it did before;
`from aqara_ble import <name>` works for all moved constants; the full test
suite (incl. the secret-hygiene guard) passes; the moved constant values are
byte-identical to before.

**Acceptance Scenarios**:

1. **Given** the moved constants, **When** their values are compared to the
   pre-refactor values, **Then** every value is identical (string-for-string,
   tuple-for-tuple).
2. **Given** the public package, **When** `__all__` is enumerated, **Then** it
   contains exactly the same names as before (none added, none removed).
3. **Given** the canonical public import style (`from aqara_ble import X`) for
   every moved name, **When** it runs after the refactor, **Then** it resolves
   unchanged. Submodule import styles are preserved only where a name is still
   backed by that module (e.g. `from aqara_ble.transport import
   U200_SERVICE_UUIDS`); the one in-repo test relying on a now-unbacked submodule
   path was repointed to the canonical path.
4. **Given** the whole test suite, **When** it runs, **Then** it passes with the
   same behaviour (no test changed to accommodate the move, beyond import paths if
   strictly necessary).

### Edge Cases

- A consumer importing a moved constant via the canonical package path
  (`from aqara_ble import X`) must still succeed for every moved name. A
  consumer relying on an internal submodule path is only guaranteed where that
  module still uses the name; the canonical package path is the supported one.
- `PRE_AUTH_NOTIFY_ORDER`, which is built from other moved UUIDs, must be defined
  in the leaf so its members resolve without reaching back into `session`.
- Any lazily-imported optional transport (`bumble_transport`) must not be forced
  to load just to obtain the constants.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A new leaf module `aqara_ble/gatt_uuids.py` MUST hold the GATT
  service/characteristic UUID string constants, the `CONTROL_NOTIFY2_UUID`,
  `GATT_CACHING_PREAMBLE_UUID16`, `PRE_AUTH_NOTIFY_ORDER`, and the U200 service
  UUID tuples (`U200_SERVICE_UUIDS`, `U200_SERVICE_UUID16`).
- **FR-002**: The leaf module MUST NOT import any other `aqara_ble` module.
- **FR-003**: `transport.py` MUST obtain the service UUIDs and service-UUID tuples
  from the leaf module and MUST NOT import anything from `session.py`.
- **FR-004**: The single definition site of the moved constants MUST be the leaf
  module; `__init__.py` MUST import them from the leaf (single source of truth),
  and `session.py`/`transport.py` MUST import (downward) only the ones they use
  internally. The canonical public path is the top-level package
  (`from aqara_ble import <name>`), which is preserved unchanged. Submodule
  re-export paths (`from aqara_ble.session import <SERVICE_UUID>`) that a name
  no longer backs internally are NOT preserved; the one in-repo test that used such
  a path was repointed to the canonical public path (allowed as an import-path-only
  edit).
- **FR-005**: Every moved constant's VALUE MUST be byte-identical to its previous
  definition — no renaming of values, no reformatting of UUID strings/tuples.
- **FR-006**: The public `__all__` in `__init__.py` MUST export exactly the same
  set of names as before (the moved names still reachable via
  `from aqara_ble import <name>`).
- **FR-007**: No wire byte, frame, CRC, or cryptographic path may change; the only
  diff is the relocation of constant definitions and the corresponding imports.
- **FR-008**: The full existing test suite AND the secret-hygiene guard MUST pass
  unchanged (no behavioural test edits).

### Key Entities *(include if feature involves data)*

- **GATT identity constants**: the service/characteristic UUID strings, the ATT
  caching-preamble UUID16 tuple, the pre-auth CCCD-enable order, and the U200
  service UUID tuples — device-specific leaf data with no dependencies.
- **Leaf module**: `aqara_ble/gatt_uuids.py` — the new zero-dependency home
  for those constants.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A search of `transport.py` for `from .session import` returns 0
  matches after the refactor.
- **SC-002**: `gatt_uuids.py` contains 0 imports of any other `aqara_ble`
  module (a true leaf). (Note: importing any submodule still runs the package
  `__init__`, which by design imports the full public API; the leaf's own
  dependency count is what SC-002 measures.)
- **SC-003**: The set of names in `aqara_ble.__all__` is identical before and
  after (0 added, 0 removed).
- **SC-004**: Every moved constant compares equal to its pre-refactor value (100%
  identical).
- **SC-005**: The full test suite passes with the same number of tests as before
  (0 tests removed/skipped) plus the secret-hygiene guard green.

## Assumptions

- The single source of truth for the moved constants is the leaf module;
  `__init__.py` imports them from the leaf so the public `from aqara_ble
  import X` path is unchanged. `session.py`/`transport.py` import only what they
  use internally (which keeps `from aqara_ble.transport import
  U200_SERVICE_UUIDS` working, since transport still uses it). Unbacked submodule
  re-exports are intentionally NOT maintained (avoids `X as X` noise that fights
  the linter); the canonical public path is the supported contract.
- The connection-tuning constants that live in `session.py` and are used ONLY by
  the session orchestrator (data-length, connection-interval, supervision-timeout,
  client-supported-features) are NOT identity data and stay in `session.py`; only
  the GATT identity/preamble/order constants move. This keeps the leaf cohesive
  and the change minimal.
- The architecture doc already describes UUIDs/handles as device-specific leaf
  data, so no doc rewrite is required beyond an optional pointer to the new module.

## Out of Scope

- Splitting `kdf.py` (phase 2b) or `session.py`'s framing/codec/orchestrator
  (phase 2c).
- Any behavioural change, dead-code removal, or `__all__` slimming.
- Moving the session-only connection-tuning constants.
