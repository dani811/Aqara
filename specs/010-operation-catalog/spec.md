# Feature Specification: Lock operation & settings catalog

**Feature Branch**: `feature/010-operation-catalog`

**Created**: 2026-08-14

**Status**: Draft

**Input**: User description: "Catálogo completo de operaciones y ajustes de la cerradura U200 + builder genérico de comandos de control, marcando qué está confirmado en vivo vs solo catalogado."

## Context

Feature 009 opened the bolt autonomously and cracked the control frame:
`74 <dir> <seq:2 LE> <trailer:2 LE>` with an additive trailer. But `0x74`
(open/close) is one of ~120 operations the lock understands. The app's own
command enum (`BleCommandConstant.ts`) was decompiled in the reverse-engineering
project and lists every operation across eight command families. This feature
brings that full map into the library as a structured, honest catalog plus a
generic frame builder — so an integrator can see everything the lock can do and
build any command, while never mistaking a decompiled-but-unverified opcode for
a confirmed one.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Discover every operation the lock supports (Priority: P1)

An integrator wants a single, structured list of every operation and setting the
U200 exposes over BLE — open/close, status, battery, volume, language, auto-lock,
motor, alarms, users, credentials, logs, OTA, Matter — organised by command
family, so they know what is possible without decompiling the app themselves.

**Why this priority**: the catalog is the deliverable's core; without it there is
nothing to build against. It is also usable on its own (read-only reference).

**Independent Test**: open the catalog and confirm it contains all eight families
(`SYSTEM 01`, `USER 02`, `LOG 03`, `ALARM 04`, `DEVICELOG 05`, `XXQ 06`,
`SYSTEM_EXT 07`, `LONG 3f`) with their sub-commands, and that each entry is
labelled with its verification status.

**Acceptance Scenarios**:

1. **Given** the catalog, **When** the integrator looks up an operation (e.g.
   "set volume"), **Then** they find its command family, sub-command byte, and
   whether it is confirmed-live or catalogued-only.
2. **Given** the catalog, **When** they filter for confirmed operations, **Then**
   they get exactly the ones verified against the real lock (open, close,
   keepalive), distinct from the decompiled-only majority.

### User Story 2 - Build the wire frame for any operation (Priority: P1)

An integrator wants to construct the plaintext frame for an arbitrary operation
(family + sub-command + data), reusing the confirmed control-frame structure, so
they can drive operations beyond open/close through the existing session.

**Why this priority**: a catalog you cannot act on is just documentation; the
builder turns the map into something executable.

**Independent Test**: build a frame for a known operation and confirm its bytes
match the documented structure; build open/close and confirm they equal the
feature-009 values.

**Acceptance Scenarios**:

1. **Given** a family, sub-command and data, **When** the integrator builds a
   frame, **Then** it follows the confirmed control-frame structure and is
   accepted by the same encryption/transport path used for open/close.
2. **Given** open (family SYSTEM, sub `0x74`, direction open), **When** built via
   the generic builder, **Then** it equals the confirmed `74010100b917` (seq 1).

### User Story 3 - Know how to confirm an uncatalogued command's exact data (Priority: P2)

An integrator wants documented, reproducible steps to obtain the exact `data`
bytes of any catalogued-only command, so they can promote it to confirmed.

**Why this priority**: most entries are family+sub only; the path to their exact
parameters must be written down, not folklore.

**Independent Test**: follow the documented capture procedure for one command and
obtain its plaintext `mainCmd subCmd data`.

**Acceptance Scenarios**:

1. **Given** a catalogued-only command, **When** the integrator follows the
   documented procedure (read the app builder, or capture live), **Then** they
   recover its exact plaintext and can mark it confirmed.

### Edge Cases

- An operation with empty data (e.g. a status get) vs a structured one (e.g. add
  user with schedule): the builder must handle both.
- A sub-command byte that collides with another family's byte: entries are always
  qualified by their family, never by the sub-byte alone.
- A decompiled opcode that turns out wrong when captured (as `1f031f`/`200320`
  did): the catalog's status field must make "not yet verified" unmistakable.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The library MUST expose a structured catalog of every operation from
  the decompiled command enum, grouped by the eight command families, each entry
  carrying its family, sub-command byte, human name, and a verification status.
- **FR-002**: Each catalog entry MUST be marked **confirmed-live** (verified
  against the real lock) or **catalogued** (from decompilation, exact data
  unverified). Open, close, and keepalive are the initial confirmed set.
- **FR-003**: The library MUST provide a generic control-frame builder that
  produces the plaintext for a given family, sub-command and data, following the
  confirmed control-frame structure, and MUST reproduce the confirmed open/close
  frames as a special case.
- **FR-004**: The catalog and builder MUST NOT actuate the lock; this feature
  delivers reference + construction only. (Only the already-confirmed commands
  have ever been sent.)
- **FR-005**: Documentation MUST describe the reproducible procedure to obtain a
  catalogued command's exact `data` (read the app builder, or live capture via
  the instrumented app), so entries can be promoted to confirmed.
- **FR-006**: Pure catalog/builder logic MUST be covered by network-free tests,
  including a test that the builder reproduces the confirmed open/close frames.
- **FR-007**: No secrets are introduced (opcodes and frame structure are protocol,
  not secrets); protocol claims marked confirmed MUST cite real evidence.

### Key Entities *(include if data involved)*

- **Command family**: the first frame byte (`SYSTEM`, `USER`, …) with its reply
  byte (`mainCmd | 0x80`).
- **Operation entry**: family + sub-command byte + name + verification status
  (+ optional exact data once confirmed).
- **Control frame**: the plaintext the builder produces
  (`mainCmd subCmd data` for level-3 commands; the `0x74` operate frame is the
  confirmed instance with its additive trailer).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The catalog covers all eight families and their sub-commands from
  the decompiled enum — an integrator finds any documented operation without
  reading the app.
- **SC-002**: Every entry is unambiguously labelled confirmed-live or catalogued,
  and the confirmed set matches exactly what has been verified on the lock.
- **SC-003**: The generic builder reproduces the confirmed open/close frames and
  can construct a frame for any family+sub+data, proven by network-free tests.
- **SC-004**: A documented, reproducible procedure exists to recover any
  catalogued command's exact data and promote it to confirmed.

## Assumptions

- The decompiled `BleCommandConstant.ts` map (in the RE project's
  `operaciones-u200.md`) is the source of truth for the family/sub-command list;
  this feature consolidates and honestly labels it, not re-decompiles it.
- The confirmed control-frame structure from feature 009
  (`74 <dir> <seq:2 LE> <trailer:2 LE>`, additive trailer) is the reference; the
  generic level-3 frame is `mainCmd subCmd data` and whether other families carry
  the same trailer/sequence is unverified and marked as such.
- Executing arbitrary catalogued operations against the physical lock is **out of
  scope** here (a later feature per operation), except those already confirmed.
- The instrumented-app capture path (Frida gadget) from feature 009 is the
  documented way to confirm a command's exact data.
