# Feature Specification: Lock operations

**Feature Branch**: `feature/003-lock-operations`

**Created**: 2026-08-14

**Status**: Retrospective (reconstructed from decrypted control-channel captures)

**Input**: User description: "Lock operations: build lock/unlock/keepalive command payloads and voice-volume control writes, dispatched through a caller-provided authenticated transport"

> **Retrospective note (Constitution Principle III)**: The operation payloads
> here were recovered by decrypting the real control channel and correlating each
> frame with an app action. This document reconstructs the intended behavior
> honestly. Payloads are protocol constants (opcodes), not secrets.

## Clarifications

### Session 2026-08-14

Scanned for high-impact ambiguities (`/speckit-clarify`). None block. Resolved
inline:

- **Transport ownership** — this feature builds command bytes and hands them to a
  *caller-provided* authenticated transport; it never opens BLE or holds keys
  itself. The session/transport is feature 004/005.
- **Lock vs unlock payload identity** — an earlier capture mislabeled `1f031f`;
  it was confirmed as **LOCK**, with `200320` as **UNLOCK**. The historical alias
  is retained but clearly marked.

No questions were escalated to the user.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Build a lock/unlock command (Priority: P1)

An integrator wants to turn a human intent ("unlock", "lock", "keepalive") into
the exact command bytes plus the write prefix the lock expects, so a transport can
send it.

**Why this priority**: Locking and unlocking are the product's reason to exist.
Producing the correct payload and prefix for an intent is the core capability.

**Independent Test**: Ask for "unlock" and assert the payload and write prefix
match the confirmed capture; ask for an unsupported intent and assert a clear
rejection. Delivers value alone: intent → wire-ready command.

**Acceptance Scenarios**:

1. **Given** the intent "unlock" (or a supported alias), **When** a command is
   built, **Then** the payload equals the confirmed unlock bytes and the write
   prefix matches the opcode.
2. **Given** the intent "lock", **When** a command is built, **Then** the payload
   equals the confirmed lock bytes (distinct from unlock).
3. **Given** an unrecognized intent, **When** a command is requested, **Then** it
   is rejected with a clear error.

---

### User Story 2 - Dispatch an operation through a transport (Priority: P1)

An integrator holds an authenticated session (feature 004/005) exposing a simple
"send these bytes" transport, and wants to dispatch a built operation through it
and get back a record of what was sent.

**Why this priority**: A command that cannot be dispatched is inert. Sending via a
caller-provided transport keeps this feature decoupled from BLE while still
delivering the end action.

**Independent Test**: Pass a fake transport, dispatch "unlock", and assert the
transport received exactly the built payload and the returned record matches.

**Acceptance Scenarios**:

1. **Given** a transport and an intent, **When** the operation is dispatched,
   **Then** the transport receives exactly the operation's payload bytes and the
   returned record reflects the operation.

---

### User Story 3 - Set the voice/alert volume (Priority: P2)

An integrator wants to change the lock's voice/alert volume to a named preset
(medium/high) by sending the observed control request.

**Why this priority**: Settings like volume are secondary to lock/unlock but part
of full autonomous control. P2 because it is a convenience, not the core action.

**Independent Test**: Build the "high" volume write and assert its serialized bytes
equal the captured control request; dispatch via a fake transport and assert those
bytes were sent.

**Acceptance Scenarios**:

1. **Given** a supported preset name, **When** the volume write is built, **Then**
   its bytes equal the captured control request for that preset.
2. **Given** a transport and a preset, **When** the volume is set, **Then** the
   transport receives exactly those bytes.
3. **Given** an unsupported preset, **When** requested, **Then** it is rejected.

---

### Edge Cases

- **Alias and case handling**: intents/presets accept common Spanish/English
  aliases and are case-insensitive; unknown values raise a clear error.
- **Unsupported operation for prefix lookup**: only operations with a known write
  prefix can be built into a write; others are rejected rather than guessed.
- **Transport failure**: an exception from the caller's transport propagates
  unchanged — this feature does not swallow send errors.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST map a human intent (with common aliases,
  case-insensitive) to a canonical lock operation, rejecting unknown intents.
- **FR-002**: The system MUST build, for a supported operation, the exact command
  payload bytes and the write prefix observed for that operation.
- **FR-003**: The system MUST keep lock and unlock as distinct, correctly labeled
  operations, preserving the historical alias without confusing the two.
- **FR-004**: The system MUST dispatch a built operation through a
  caller-provided authenticated transport, sending exactly the operation's payload
  and returning a record of what was sent.
- **FR-005**: The system MUST map a named volume preset (with aliases) to the
  captured control request, and MUST reject unsupported presets.
- **FR-006**: The system MUST serialize a volume write to the exact bytes of the
  captured control request (reusing the control-channel framing, feature 002).
- **FR-007**: The system MUST NOT open BLE connections, hold session keys, or
  perform encryption itself; it depends on a caller-supplied transport.

### Key Entities

- **Lock operation**: a canonical operation (lock, unlock, keepalive, state
  snapshot) with its observed payload and write prefix.
- **Lock operation write**: the built command — operation, payload bytes, write
  prefix — ready for a transport.
- **Voice-volume write**: a named preset bound to a captured control request whose
  serialization is the wire payload.
- **Transport (port)**: a minimal caller-provided interface that accepts payload
  bytes; the boundary between this feature and the authenticated session.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For every supported intent, the built payload and prefix match the
  confirmed capture 100% of the time.
- **SC-002**: Lock and unlock never produce the same payload; the distinction
  holds for 100% of builds.
- **SC-003**: Dispatching sends exactly the built payload bytes to the transport
  (byte-for-byte) and returns a faithful record.
- **SC-004**: Every supported volume preset serializes to the captured control
  request byte-for-byte.
- **SC-005**: Unknown intents/presets are rejected 100% of the time with a clear
  error.
- **SC-006**: No secret or personal capture appears in source or tests; payloads
  are protocol constants (verifiable by inspection).

## Assumptions

- Operation payloads are protocol opcodes recovered from decrypted captures, not
  personal records; committing them is within the secrets policy (Principle I).
- The authenticated transport is provided by the BLE session (feature 004) or the
  end-to-end flow (feature 005); this feature is transport-agnostic.
- The catalogued operations and volume presets cover what has been observed; the
  set grows as more commands are decoded.
- Voice-volume trailers are the observed request tails; they are treated as part
  of the captured control request, not as session-derived secrets.
