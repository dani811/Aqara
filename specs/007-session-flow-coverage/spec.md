# Feature Specification: Verifiable unlock choreography

**Feature Branch**: `feature/007-session-flow-coverage`

**Created**: 2026-08-14

**Status**: Draft

**Input**: User description: "Cover the live BLE orchestration
(`run_authenticated_lock_operation`) with a scripted fake lock, closing the
'live BLE flow is not unit-tested' known limitation without hardware or radio.
The whole choreography — enabling notifications in the app's captured order,
writing the public-key frame, tolerating the lock's empty ACKs until the real
key arrives, the verify frame, the encrypted control write and the decrypted
response, plus the guaranteed cleanup — has zero automated coverage; a
regression there is only detectable by standing next to the door."

> **Why now**: the roadmap lists "live BLE flow is not unit-tested" as a known
> limitation *by design*, on the grounds that it needs hardware. That is true of
> the radio, but not of the **choreography**: the order of steps, the tolerance
> of empty ACKs, the failure messages, and the cleanup are pure orchestration and
> can be exercised against a stand-in lock. This feature separates the two so the
> genuinely-hardware part stays honest and the rest stops being untested.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A regression in the unlock sequence is caught before the door (Priority: P1)

A maintainer changes something in the session flow — reorders a step, drops a
notification, alters a frame. They learn immediately, from the test suite, that
the choreography no longer matches the captured one, instead of discovering it
while standing at a lock that will not open.

**Why this priority**: This is the whole point. The sequence was recovered over
months of reverse engineering; today nothing guards it. Any single step silently
reordered or dropped reproduces exactly the failure mode the project spent
months escaping (the lock answering an empty ACK forever).

**Independent Test**: Drive one complete unlock against a stand-in lock that
answers scripted frames, and assert the observable sequence: notifications
enabled in the captured order, the public-key frame written before anything else,
the verify frame after the session material is obtained, and the encrypted
control write last. Delivers the guard on its own.

**Acceptance Scenarios**:

1. **Given** a stand-in lock that answers a public key and acknowledges the
   verify step, **When** an unlock runs, **Then** it completes and reports the
   session material, the dispatched operation, and the decrypted response.
2. **Given** the same run, **When** the exchange is inspected, **Then**
   notifications were enabled in the captured app order before any write.
3. **Given** the same run, **When** the written frames are inspected, **Then**
   the public-key frame precedes the verify frame, which precedes the control
   write.
4. **Given** the stand-in lock answers a control response, **When** the run
   finishes, **Then** the response is decrypted and returned in the clear.

---

### User Story 2 - The lock's stalling behaviour stays tolerated (Priority: P1)

The real lock answers the public-key frame with one or more **empty
acknowledgements** before sending its actual key. A maintainer must not be able
to "simplify" that retry tolerance away, and when the lock never sends a key the
failure must say so plainly.

**Why this priority**: This tolerance is the single most expensive discovery in
the project's history and the least obvious line to a newcomer — it looks like a
pointless loop. P1 alongside US1 because losing it reintroduces the original
wall.

**Independent Test**: Script the stand-in lock to answer several empty
acknowledgements before the key, and assert the unlock still succeeds; then
script it to answer only empty acknowledgements, and assert a clear, specific
failure.

**Acceptance Scenarios**:

1. **Given** a lock that answers three empty acknowledgements and then its key,
   **When** an unlock runs, **Then** it succeeds.
2. **Given** a lock that only ever answers empty acknowledgements, **When** an
   unlock runs, **Then** it fails with a message naming that no public key was
   received, distinct from a timeout or a transport error.
3. **Given** a lock that acknowledges the verify step with the wrong frame kind,
   **When** an unlock runs, **Then** it fails with a message naming the expected
   and received kinds.

---

### User Story 3 - A plain transport still works (Priority: P2)

An integrator using an ordinary BLE backend — one that cannot negotiate MTU,
read or write by type, or change connection parameters — completes an unlock
unaffected. Those low-level steps replicate what the phone's operating system
does automatically and must remain strictly optional.

**Why this priority**: The library supports two very different transports. If an
optional capability quietly became mandatory, the common backend would break for
everyone, and only in the field. P2 because it protects a path US1 already
exercises rather than adding a new one.

**Independent Test**: Run the same unlock against a stand-in lock exposing none
of the optional capabilities, and assert it still completes; then against one
whose optional capabilities all raise errors, and assert it still completes.

**Acceptance Scenarios**:

1. **Given** a stand-in lock offering none of the optional low-level
   capabilities, **When** an unlock runs, **Then** it completes normally.
2. **Given** a stand-in lock whose optional capabilities all fail, **When** an
   unlock runs, **Then** the failures are absorbed and the unlock completes.
3. **Given** a stand-in lock that does offer them, **When** an unlock runs,
   **Then** they are exercised in the captured order relative to the rest.

---

### User Story 4 - The session always releases its subscriptions (Priority: P3)

Whatever happens — success, a lock that never answers, a cloud rejection — the
session leaves no notification subscriptions behind on the connection.

**Why this priority**: Leaked subscriptions surface later as duplicated
callbacks or a connection that cannot be reused, far from the cause. P3 because
it degrades the next run rather than failing this one.

**Independent Test**: Assert the subscriptions are released after a successful
run and after a failing one.

**Acceptance Scenarios**:

1. **Given** a successful unlock, **When** it returns, **Then** every enabled
   notification has been released.
2. **Given** an unlock that fails mid-flow, **When** the error propagates,
   **Then** every enabled notification has still been released.

---

### Edge Cases

- **A control response that never arrives**: tolerated — the operation still
  reports success with no decrypted response, because the write itself is the
  action that moves the bolt.
- **A truncated control response**: rejected with a clear error rather than
  decrypted from garbage.
- **Notification setup failing for one characteristic**: absorbed; some
  transports expose a subset. The run continues.
- **Cloud rejection mid-flow**: propagates unchanged — this feature does not
  reinterpret cloud errors (feature 001 owns them).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The unlock choreography MUST be exercisable end to end without a
  radio, a lock, or a network call, using a scripted stand-in for the lock.
- **FR-002**: The exercise MUST assert the observable order of the exchange:
  notifications enabled in the captured order, then the public-key frame, then
  the verify frame, then the encrypted control write.
- **FR-003**: The exercise MUST prove that empty acknowledgements before the
  lock's public key are tolerated, and that an endless stream of them fails with
  a specific, distinguishable message.
- **FR-004**: The exercise MUST prove that an unexpected acknowledgement kind for
  the verify step fails with a message naming what was expected and what arrived.
- **FR-005**: The exercise MUST prove that every optional low-level transport
  capability is best-effort: absent or failing, the unlock still completes.
- **FR-006**: The exercise MUST prove that notification subscriptions are
  released on both the success and the failure path.
- **FR-007**: The exercise MUST prove that the control response is decrypted and
  returned, that its absence is tolerated, and that a truncated one is rejected.
- **FR-008**: The exercise MUST NOT contain any real credential, key, address, or
  captured personal record; every value is a throwaway fixture.
- **FR-009**: The exercise MUST NOT depend on wall-clock waiting, so the suite
  stays fast and deterministic.
- **FR-010**: This feature MUST NOT change any production behaviour; it only adds
  verification of what already exists.

### Key Entities

- **Stand-in lock**: a scripted answering machine that plays the lock's side of
  the exchange — acknowledgements, public key, verify acknowledgement, control
  response — and records everything asked of it.
- **Exchange record**: the ordered list of what the session did (subscriptions
  enabled and released, frames written, optional capabilities attempted), which
  the assertions read.
- **Scripted answer set**: the configurable behaviour of the stand-in — how many
  empty acknowledgements, which acknowledgement kind, whether a control response
  arrives — so one stand-in serves every scenario.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A complete unlock is verified end to end with zero radio, zero
  network, and zero hardware.
- **SC-002**: Reordering or removing any step of the captured sequence causes at
  least one assertion to fail.
- **SC-003**: Both stalling behaviours are covered: tolerated empty
  acknowledgements, and the endless-acknowledgement failure, each with its own
  distinguishable outcome.
- **SC-004**: The unlock completes in 100% of optional-capability configurations
  — all absent, all failing, all present.
- **SC-005**: Subscriptions are released in 100% of runs, success or failure.
- **SC-006**: The full suite still runs in under five seconds on a developer
  machine, with no wall-clock waiting introduced.
- **SC-007**: No production module changes; the diff outside the tests is
  documentation only.
- **SC-008**: The roadmap's "live BLE flow is not unit-tested" limitation is
  narrowed, in writing, to the part that genuinely needs hardware.

## Assumptions

- The stand-in lock reproduces the *shape* of the exchange, not the radio: what
  it proves is that the choreography is intact, never that a real lock accepts
  it. The live tutorial run remains the only evidence of the latter, and the
  roadmap must keep saying so.
- Building the stand-in's answers with the project's own verified frame
  primitives is acceptable — those primitives are independently pinned
  byte-for-byte against captures by feature 004, so this feature does not
  circularly assume them.
- The cloud steps are replaced by fixtures in this exercise; their own behaviour
  is covered by feature 001.
- Ephemeral public keys are public by definition, and the key/nonce fixtures here
  are throwaway values, so nothing in this feature is a door key (Principle I).
