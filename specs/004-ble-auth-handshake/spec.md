# Feature Specification: BLE authentication handshake

**Feature Branch**: `feature/004-ble-auth-handshake`

**Created**: 2026-08-14

**Status**: Retrospective (reconstructed from reverse-engineering; verified live)

**Input**: User description: "BLE authentication handshake: build 0610/0710 frames with the CRC-16/ARC header field, fragment/reassemble, parse, and AES-CCM control payload crypto; the CRC-16 discovery that unblocked autonomy"

> **Retrospective note (Constitution Principle III)**: This is the capability that
> broke a six-month wall. The header field long assumed to be a "random app
> token" is actually a **CRC-16/ARC of the exchanged public key**. This document
> reconstructs the behavior honestly; the CRC discovery and the live confirmation
> are recorded truthfully, not as if foreseen.

## Clarifications

### Session 2026-08-14

Scanned for high-impact ambiguities (`/speckit-clarify`). None block; the frame
layout and CRC are pinned by captured frames and confirmed live. Resolved inline:

- **The mystery header field** — bytes 7–8 of the `0610`/`0710` header are the
  little-endian CRC-16/ARC of the body, **not** a random token. Sending a random
  value is exactly what produced the historical empty-ACK wall.
- **CRC variant** — CRC-16/ARC (poly `0x8005` reflected, init `0x0000`,
  reflected in/out), distinct from the control channel's CRC-HQX (feature 002).
- **Backward-compatible parameter** — an `app_token` argument is retained on the
  builder but ignored, so older call sites do not break while the CRC governs the
  wire.

No questions were escalated to the user.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Build an acceptable handshake frame (Priority: P1)

An integrator with the cloud's ephemeral public key needs to build the `0610`
frame the lock will accept — with the correct header and, crucially, the correct
CRC-16 field — so the lock responds with its own public key instead of an empty
rejection.

**Why this priority**: This is *the* unlock of autonomy. Without a correctly-CRC'd
frame, the lock never returns its public key and no session can ever form. Every
other capability is downstream of this frame being right.

**Independent Test**: Build a `0610` frame for a known public key and assert the
header layout and CRC field are byte-exact against a captured app frame; assert an
altered body changes the CRC. Delivers value alone: it produces the exact bytes
the lock accepts.

**Acceptance Scenarios**:

1. **Given** a public-key body, **When** a `0610` frame is built, **Then** the
   header's CRC field equals the CRC-16/ARC of that body (little-endian) and the
   length field matches the body length.
2. **Given** the same body with any byte changed, **When** a frame is built,
   **Then** the CRC field changes accordingly.
3. **Given** an unsupported frame type, **When** a build is attempted, **Then** it
   is rejected with a clear error.

---

### User Story 2 - Fragment and reassemble a frame for BLE (Priority: P1)

An integrator must split a handshake frame into the direction-tagged fragments the
BLE characteristic carries, and reassemble the lock's fragmented reply back into a
whole frame.

**Why this priority**: BLE writes/notifies are size-limited; the frame only
crosses the link in fragments. Fragmentation that is not an exact inverse of
reassembly corrupts the handshake. P1 because it is required for the frame to
actually reach the lock intact.

**Independent Test**: Fragment a frame outbound, flip the direction tag to the
inbound value, reassemble, and assert the result equals the original frame.

**Acceptance Scenarios**:

1. **Given** a handshake frame, **When** it is fragmented outbound and reassembled
   inbound, **Then** the reassembled bytes equal the original frame.
2. **Given** fragments with an unexpected direction or out-of-order sequence,
   **When** reassembly is attempted, **Then** it is rejected with a clear error.

---

### User Story 3 - Protect control payloads for the session (Priority: P2)

Once a session exists, an integrator needs to encrypt an outgoing command payload
and decrypt an incoming one using the session's key and nonce, so commands and
responses are protected exactly as the lock expects.

**Why this priority**: Commands only work once wrapped in the session's AES-CCM.
P2 because it depends on a session (this feature's handshake plus the cloud
exchange) already existing.

**Independent Test**: Encrypt a payload and decrypt it back with the same key and
nonce, asserting the original plaintext returns and the ciphertext carries the
short authentication tag.

**Acceptance Scenarios**:

1. **Given** a session key and nonce, **When** a payload is encrypted and then
   decrypted, **Then** the original plaintext is recovered.
2. **Given** an encrypted payload, **When** its length is inspected, **Then** it
   equals the plaintext length plus the 4-byte authentication tag.

---

### Edge Cases

- **Wrong CRC field** (the historical wall): a frame whose CRC does not match its
  body is rejected by the lock with an empty-body status — the exact failure this
  feature exists to prevent.
- **Incomplete frame to the parser**: input shorter than a full header, or whose
  declared body length does not match, is rejected rather than misparsed.
- **Fragment loss on the wire**: the live flow spaces fragment writes to avoid the
  controller dropping fragments (which would make the lock see a truncated key and
  reply empty); the framing logic itself remains an exact inverse.
- **Missing crypto backend**: if the AES-CCM backend is unavailable, encryption
  raises a clear error instead of failing obscurely.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST compute the handshake header integrity field as the
  CRC-16/ARC of the frame body (little-endian), reproducing the app exactly.
- **FR-002**: The system MUST build `0610` and `0710` frames with the exact header
  layout (frame type, body length, CRC field, lock token) and reject unsupported
  frame types.
- **FR-003**: The system MUST retain a backward-compatible token argument on the
  builder while ignoring it, so the CRC alone governs the wire.
- **FR-004**: The system MUST fragment a frame into direction-tagged, sequenced
  fragments and reassemble them as an exact inverse, rejecting unexpected
  directions or out-of-order sequences.
- **FR-005**: The system MUST parse a frame back into its fields (frame type,
  header field, lock token, body), rejecting incomplete or inconsistent input.
- **FR-006**: The system MUST encrypt and decrypt control payloads with the
  session key and nonce using the lock's AES-CCM parameters (short tag), such that
  decrypt(encrypt(x)) == x.
- **FR-007**: The system MUST expose the well-known service/characteristic
  identifiers and the observed pre-authentication ordering as named constants, so
  a transport can reproduce the app's connection sequence.
- **FR-008**: The system MUST NOT embed any real session key, nonce, token, or
  captured personal record; live orchestration takes these from the caller at
  runtime (Principle I).

### Key Entities

- **Handshake frame**: a `0610`/`0710` message — header (type, length, CRC field,
  lock token) plus body — with build/parse that are inverses.
- **Fragment**: a direction-tagged, sequenced slice of a frame as carried by the
  BLE characteristic.
- **Session material**: the session key, nonce, verify data, and the lock's public
  key that secure the control channel.
- **Channel identifiers**: the auth/control/aux service and characteristic UUIDs
  and the pre-auth notification ordering the app performs.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A built `0610` frame is byte-exact against a captured app frame,
  including the CRC field, for the known public key (100% match).
- **SC-002**: The lock returns its public key (not an empty ACK) when driven with
  a correctly-CRC'd frame — the wall is broken (confirmed live).
- **SC-003**: Fragment-then-reassemble reproduces every frame byte-for-byte (100%
  round-trip identity).
- **SC-004**: Encrypt-then-decrypt recovers the original payload 100% of the time;
  ciphertext length is plaintext length plus the 4-byte tag.
- **SC-005**: Build/parse round-trip preserves frame type, lock token, and body.
- **SC-006**: No real session key, nonce, token, or personal capture appears in
  committed source or tests (verifiable by inspection).

## Assumptions

- The cloud public key (feature 001) is available and valid before the handshake
  begins; obtaining it is out of scope here.
- Test vectors are an ephemeral EC public key (public by definition, not a secret)
  and throwaway AES-CCM key/nonce fixtures; no captured session secret is used.
- The live orchestration (`run_authenticated_lock_operation`) requires a real BLE
  transport and lock; it is validated live, not in unit tests (Principle V).
- CRC-16/ARC is the correct handshake variant, distinct from the control channel's
  CRC-HQX (feature 002).
- The many best-effort pre-auth BLE steps (MTU, data-length, GATT-caching preamble,
  CCCD ordering) mirror the app's observed sequence; adapters that cannot perform a
  step skip it without breaking the handshake.
