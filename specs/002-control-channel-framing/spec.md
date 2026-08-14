# Feature Specification: Control channel framing

**Feature Branch**: `feature/002-control-channel-framing`

**Created**: 2026-08-14

**Status**: Retrospective (reconstructed from reverse-engineering; verified against captures)

**Input**: User description: "Control channel framing: parse AES-CCM control requests (kind/command/body/trailer), command naming, ATT packet model, CRC-HQX validation"

> **Retrospective note (Constitution Principle III)**: These primitives were
> reverse-engineered from real BLE captures before SDD adoption. This document
> reconstructs the intended behavior honestly. Every parsing rule and CRC check
> below is confirmed against captured frames (see the Assumptions and the
> protocol docs).

## Clarifications

### Session 2026-08-14

Scanned for high-impact ambiguities (`/speckit-clarify`). This feature is small,
pure, and fully pinned by captured test vectors, so no blocking ambiguities
remain. Two points resolved inline:

- **Which frames count as control requests** — only those whose first byte is
  `0x01` or `0x03` and that are at least 7 bytes long; anything else is rejected
  (it is not a control request this layer handles).
- **CRC variant** — the bulk-transfer integrity check is CRC-HQX (CRC-16/XMODEM,
  big-endian trailer), distinct from the CRC-16/ARC used by the auth handshake
  (feature 004). Both are documented explicitly to avoid confusion.

No questions were escalated to the user for this feature.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Decode a control request into its parts (Priority: P1)

A developer analyzing or building lock traffic needs to take a raw control-channel
payload and split it into its meaningful parts — the request kind, the command
byte, the command body, and the integrity trailer — so higher layers can reason
about what the frame does.

**Why this priority**: Every lock command (open, keepalive, volume, user
management) travels as a control request. Without a reliable way to split a frame
into kind/command/body/trailer, no command can be interpreted or constructed.
This is the foundation the operations layer (feature 003) builds on.

**Independent Test**: Feed a captured control frame and assert the four parts come
out exactly as observed; feed a too-short or wrong-prefix frame and assert it is
rejected. Delivers value alone: it turns opaque bytes into structured requests.

**Acceptance Scenarios**:

1. **Given** a captured voice-volume control frame, **When** it is parsed, **Then**
   the kind, command, body, and 4-byte trailer match the captured values exactly.
2. **Given** a captured keepalive control frame, **When** it is parsed, **Then**
   the command is recognized and body/trailer are split correctly.
3. **Given** a frame shorter than the minimum length or with an unrecognized
   prefix, **When** parsing is attempted, **Then** it is rejected with a clear
   error rather than producing a malformed request.

---

### User Story 2 - Round-trip a control request back to bytes (Priority: P2)

A developer constructing a command wants to build a control request from its parts
and serialize it back to the exact byte sequence the lock expects.

**Why this priority**: Building commands (feature 003) depends on serialization
being the exact inverse of parsing. It is P2 because it is only useful once
parsing (US1) exists to validate against.

**Independent Test**: Construct a request from known parts, serialize it, and
confirm the bytes equal the original captured frame (parse → serialize is
identity).

**Acceptance Scenarios**:

1. **Given** a request built from a captured frame's parts, **When** it is
   serialized, **Then** the output equals the original frame byte-for-byte.

---

### User Story 3 - Validate bulk-transfer integrity (Priority: P3)

A developer processing bulk-transfer blocks needs to confirm a block's trailing
checksum matches its contents, to detect corruption or misframing.

**Why this priority**: Integrity checking guards the larger data transfers. It is
P3 because the common command path (US1/US2) does not require it; it matters for
the bulk channel specifically.

**Independent Test**: Take a captured block plus its checksum and confirm it
validates; flip a byte and confirm it fails.

**Acceptance Scenarios**:

1. **Given** a captured block with its correct trailing checksum, **When**
   validated, **Then** the check passes.
2. **Given** the same block with any content byte altered, **When** validated,
   **Then** the check fails.

---

### Edge Cases

- **Empty or 1-byte input to the integrity check**: treated as invalid (cannot
  contain both data and a 2-byte checksum) rather than raising.
- **Unknown command byte**: naming falls back to a stable `command-0xNN` label so
  logs and analysis never break on an unseen command.
- **Frame with a valid prefix but fewer than 7 bytes**: rejected — there is not
  enough room for command + body + a 4-byte trailer.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST split a control-channel payload into request kind,
  command byte, command body, and a 4-byte integrity trailer.
- **FR-002**: The system MUST accept only payloads whose leading byte marks a
  control request (`0x01` or `0x03`) and that are at least 7 bytes long; all
  others MUST be rejected with a clear error.
- **FR-003**: The system MUST serialize a control request back to bytes such that
  parsing then serializing a captured frame reproduces it exactly.
- **FR-004**: The system MUST provide a human-readable name for known command
  bytes and a stable fallback label for unknown ones.
- **FR-005**: The system MUST validate a bulk block against its trailing 16-bit
  checksum, returning false for any altered content and for inputs too short to
  contain a checksum.
- **FR-006**: The system MUST expose a structured representation of an observed
  ATT packet (framing metadata plus its value) for analysis pipelines.
- **FR-007**: The system MUST name the well-known ATT handles used by the auth,
  control, and bulk channels so higher layers reference them symbolically.

### Key Entities

- **Control request**: a parsed frame — kind, command, body, trailer — with a
  byte serialization that is the inverse of parsing.
- **ATT packet**: an observed link-layer packet with its framing metadata
  (connection, direction, opcode, handle) and payload value.
- **Channel handles**: the symbolic ATT handle constants for the auth, control,
  and bulk write/notify characteristics.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of captured control frames parse into kind/command/body/trailer
  matching the capture exactly.
- **SC-002**: Parse-then-serialize reproduces every captured frame byte-for-byte
  (round-trip identity holds for 100% of samples).
- **SC-003**: The integrity check passes for every intact captured block and fails
  for 100% of single-byte-mutated blocks.
- **SC-004**: Unknown command bytes always yield a stable, non-crashing label.
- **SC-005**: No real secret or raw capture appears in committed source or tests;
  test vectors are minimal fixtures (verifiable by inspection).

## Assumptions

- Test vectors are short, sanitized fragments taken from real captures (e.g. a
  voice-volume frame and a keepalive frame); they encode framing structure only,
  not account or session secrets.
- This feature covers only the *framing/parsing* of the control channel. The
  AES-CCM encryption/decryption that protects these frames, and the session that
  produces the keys, are specified with the BLE handshake (feature 004).
- The command-to-name map covers the commands observed so far; it is expected to
  grow as more commands are catalogued (feature 003).
- CRC-HQX (XMODEM) is the correct integrity variant for the bulk channel, distinct
  from the handshake's CRC-16/ARC.
