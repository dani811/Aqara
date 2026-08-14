# Feature Specification: Lock open command — control-pack CRC spike

**Feature Branch**: `feature/009-lock-open-command`

**Created**: 2026-08-14

**Status**: Achieved — the lock was opened autonomously with the captured command `74010100b917` (see research.md, Finding 4). The trailer/counter builder remains follow-on work.

**Input**: User description: "Spike de investigación para el comando de apertura BLE de la cerradura. Determinar la tractabilidad del comando de abrir: extraer y reimplementar el framing del pack de control + el trailer (getMijiaCrc16String), validado contra los 3 frames de control conocidos."

## Context

The authenticated BLE session already works end-to-end: the auth handshake CRC
(`crc16_aqara`, §11.58 of the RE journey) is implemented and live-confirmed — a
keepalive round-trips through the AES-CCM control channel. What does **not**
exist is the command that actually moves the bolt. The bundle's authoritative
table says the real open is `01 74` (SYSTEM / BLE_OPEN_LOCK) and status is
`01 e5` (GET_DOOR_LOCK_STATUS), each carried as a control **pack** with its own
framing and a **4-byte trailer** built by `getMijiaCrc16String` /
`getMiotShortPackString`.

The blocker is that trailer. It is **not** a trivial CRC-16: probed against the
three known control frames with CRC-16/ARC and CRC-16/CCITT over body, cmd+body,
and kind+cmd+body — zero matches. There is no reference implementation to port
(the original RE project never built the open command) and no capture of the
open **write** command (only lock→app notifies were captured). So before any
open/status feature can be planned, its tractability must be established.

**This spike does not open the door.** It only determines whether the control-pack
framing + trailer can be reconstructed, and extracts the algorithm if so.

### Known control frames (validation targets)

| Frame (kind·command·body·trailer) | body | trailer |
|---|---|---|
| `01 d3 02d13e15 d5fddfe4` | `02d13e15` | `d5fddfe4` |
| `01 d3 02d23e16 5faddd09` | `02d23e16` | `5faddd09` |
| `01 fe 01fc 158b3609` | `01fc` | `158b3609` |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Establish whether the open command is buildable (Priority: P1)

A developer needs to know, before committing to build the open/status commands,
whether the 4-byte control trailer can be reproduced from first principles. They
extract the control-command builder and the trailer function from the app bundle,
reimplement it, and check it against the three known frames.

**Why this priority**: this is the single gate. If the trailer cannot be
reproduced, no open/status command can be built the autonomous way, and the fall-
back (capturing a real command from the app) must be scheduled instead. Spending
effort on the open command before this is answered risks shipping another
unverified guess.

**Independent Test**: run the reimplemented trailer function over the three known
bodies and confirm it reproduces `d5fddfe4`, `5faddd09`, and `158b3609` exactly.

**Acceptance Scenarios**:

1. **Given** the three known control frames, **When** the reconstructed trailer
   function is run over their bodies, **Then** it reproduces all three trailers
   byte-for-byte (spike **succeeds** → open/status become buildable).
2. **Given** the app bundle cannot be decompiled far enough to read the trailer
   construction, **When** the spike time-box is reached, **Then** the outcome is
   recorded as **blocked**, with the fallback (capture a real command from the
   app, which requires an instrumented app) documented as the next step.

### Edge Cases

- The trailer turns out **not** to be a checksum at all (e.g. an encrypted/MAC
  tail or a pack sequence field): the spike records what it *is*, even if that
  means the frame must be captured rather than computed.
- The bundle is a stripped Hermes blob whose relevant function is unreadable: the
  spike is allowed to conclude "not tractable from the bundle" — that is a valid,
  useful result, not a failure to deliver.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The spike MUST produce a written finding stating whether the 4-byte
  control trailer can be reconstructed from the app bundle, with the evidence.
- **FR-002**: If reconstructable, the spike MUST deliver a pure function
  `trailer(kind, command, body) -> 4 bytes` (name/shape TBD) that reproduces the
  three known frames' trailers exactly, covered by a network-free test.
- **FR-003**: The spike MUST identify the control-pack framing around the trailer
  (field order and meaning of `01 74` open and `01 e5` status), or record that it
  could not.
- **FR-004**: The spike MUST NOT send any command to the physical lock and MUST
  NOT move the bolt — it is analysis only.
- **FR-005**: All evidence used or produced MUST be sanitized and free of secrets
  (Principle I); protocol claims MUST be validated against the real captured
  frames (Principle II) and be reproducible by a third party (Principle IV).
- **FR-006**: The spike MUST end with an explicit go/no-go recommendation for
  building the open (`01 74`) and status (`01 e5`) commands, including the
  fallback path if the answer is no-go.

### Key Entities *(include if data involved)*

- **Control frame**: a decrypted control request — `kind · command · body ·
  trailer(4B)`; the trailer is the unknown under investigation.
- **Trailer function**: the pure mapping from a frame's content to its 4-byte
  tail; the spike's central deliverable if tractable.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The spike produces a definite go/no-go answer on open-command
  tractability (not "maybe") within its time-box.
- **SC-002**: If go, the reconstructed trailer function reproduces 3/3 known
  trailers exactly, proven by a deterministic test.
- **SC-003**: If no-go, the specific blocker and the fallback (instrumented-app
  capture of a real open command) are documented well enough to act on next.
- **SC-004**: No command is sent to the lock and the bolt does not move during
  the spike.

## Assumptions

- The app bundle is available inside the reverse-engineering artifacts
  (`aqara-home-6905`), so decompilation does not depend on the phone.
- The three known control frames are genuine captured plaintext and are the
  correct validation oracle for the trailer.
- The autonomous session layer (handshake, AES-CCM control channel) is already
  working and is out of scope here; this spike only concerns the command payload.
- Follow-on work (implementing `01 74` open and `01 e5` status on the working
  session) is a **separate** phase, gated on this spike returning go.
