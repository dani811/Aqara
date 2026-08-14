# Feature Specification: End-to-end autonomous unlock

**Feature Branch**: `feature/005-end-to-end-unlock`

**Created**: 2026-08-14

**Status**: Retrospective (reconstructed from reverse-engineering; verified live)

**Input**: User description: "End-to-end autonomous unlock: BLE discovery (scanner) and a Bumble/ESP32 GATT transport adapter that lets run_authenticated_lock_operation drive a real lock, tying features 001-004 together"

> **Retrospective note (Constitution Principle III)**: This feature assembles the
> prior four into a working end-to-end unlock over real hardware. It is
> reconstructed honestly; the transport quirks documented here (MTU hangs,
> low-level GATT primitives) are real lessons from live sessions.

## Clarifications

### Session 2026-08-14

Scanned for high-impact ambiguities (`/speckit-clarify`). None block. Resolved
inline:

- **Which transport** — the end-to-end flow runs over any object satisfying the
  BLE client shape `run_authenticated_lock_operation` expects. Two are supported:
  native (bleak) and a Bumble adapter for an external controller (e.g. ESP32-S3
  over HCI) that exposes the low-level GATT primitives the lock's pre-auth needs.
- **Why Bumble at all** — the lock's pre-auth sequence uses Read-By-Type and
  data-length/MTU control that native stacks do not expose; the adapter provides
  them.
- **Discovery caveat** — the observed lock only advertises after its keypad is
  physically activated; discovery reflects that reality rather than assuming it
  always advertises.

No questions were escalated to the user.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Discover the lock (Priority: P2)

An integrator wants to passively scan for the lock and confirm its presence
(name/manufacturer) before attempting to connect, without writing to any device.

**Why this priority**: Discovery is a helpful precondition but not strictly on the
unlock critical path once the address is known. P2.

**Independent Test**: Run a passive scan and confirm a matching advertisement is
reported (or a clear "activate the keypad" hint when nothing advertises), with no
writes performed.

**Acceptance Scenarios**:

1. **Given** the lock is advertising, **When** a passive scan runs, **Then** a
   candidate is reported with its name, address, RSSI, and manufacturer data.
2. **Given** nothing advertises, **When** the scan finishes, **Then** the user is
   told the keypad may need physical activation.

---

### User Story 2 - Provide a low-level GATT transport (Priority: P1)

An integrator using an external BLE controller wants an adapter that presents the
same client interface `run_authenticated_lock_operation` expects, including the
low-level GATT primitives (Read-By-Type, MTU, data-length, connection update) that
the lock's pre-auth sequence requires.

**Why this priority**: The handshake's pre-auth steps fail on stacks that cannot
issue these primitives. The adapter is what makes an autonomous, non-app transport
actually complete the handshake. P1.

**Independent Test**: Against a fake peer exposing services/characteristics, the
adapter resolves a characteristic by its short UUID and raises clearly when it is
absent — proving the lookup the write/notify path depends on.

**Acceptance Scenarios**:

1. **Given** a peer exposing the auth/control characteristics, **When** the adapter
   resolves one by its short UUID, **Then** it returns the matching characteristic.
2. **Given** a peer missing a requested characteristic, **When** resolution is
   attempted, **Then** it fails with a clear lookup error.
3. **Given** a standard 16-bit characteristic, **When** resolved by its 16-bit
   UUID, **Then** the correct characteristic is returned.

---

### User Story 3 - Run the full autonomous unlock (Priority: P1)

An integrator wants to drive a real lock end-to-end: connect via a transport, run
the authenticated handshake, and dispatch an operation (e.g. unlock) — with no app
and no phone.

**Why this priority**: This is the product goal — full autonomous control. P1.

**Independent Test**: With a real transport and lock, running the end-to-end flow
completes the handshake and returns the session material plus a record of the
dispatched operation (validated live; not a unit test).

**Acceptance Scenarios**:

1. **Given** a connected transport and valid credentials, **When** the end-to-end
   unlock runs, **Then** the handshake completes and the unlock operation is
   dispatched, returning the session material and operation record.

---

### Edge Cases

- **Missing optional dependency**: if the scanner's or adapter's optional BLE
  backend is not installed, the caller gets a clear, actionable error rather than
  an obscure import failure.
- **Lock disconnects mid-request**: low-level GATT requests are bounded by their
  own short timeouts so a mid-request disconnect cannot hang the flow forever.
- **Adapter cleanup**: unsubscribing from a characteristic that is already gone
  does not raise; cleanup is best-effort.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST passively scan for the lock and report matching
  advertisements (name/manufacturer) without writing to any device, and MUST hint
  at physical keypad activation when nothing advertises.
- **FR-002**: The system MUST provide a transport adapter that presents the client
  interface the authenticated flow expects (write, subscribe/unsubscribe) over an
  external controller's peer.
- **FR-003**: The adapter MUST resolve a characteristic by its short (vendor) UUID
  and by its 16-bit UUID, failing with a clear error when absent.
- **FR-004**: The adapter MUST expose the low-level GATT primitives the lock's
  pre-auth needs (Read-By-Type, MTU exchange, data-length extension, connection
  update), each bounded by its own timeout.
- **FR-005**: The system MUST let `run_authenticated_lock_operation` drive a real
  lock end-to-end through such a transport, returning the session material and the
  dispatched operation record.
- **FR-006**: Optional BLE backends MUST be truly optional: absence yields a clear
  error, and the package MUST import without them installed.
- **FR-007**: The system MUST NOT embed any real credential, address, or captured
  record; discovery output and live runs use the caller's own environment
  (Principle I).

### Key Entities

- **Scanner**: passive discovery that matches the lock's advertisement and reports
  candidates without connecting.
- **Transport adapter**: presents a uniform BLE client over an external
  controller's peer, including low-level GATT primitives.
- **End-to-end run**: the composed flow (discover → connect → handshake → dispatch)
  that yields session material and an operation record.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A passive scan reports a matching lock advertisement with no writes,
  or gives the keypad-activation hint when none is seen.
- **SC-002**: The adapter resolves present characteristics 100% of the time and
  fails clearly for absent ones.
- **SC-003**: The package imports successfully with neither optional BLE backend
  installed.
- **SC-004**: End-to-end, a real lock is unlocked with no app or phone — the
  project goal — returning session material and an operation record (confirmed
  live).
- **SC-005**: No real credential, MAC, or captured record appears in committed
  source or tests (verifiable by inspection).

## Assumptions

- The end-to-end run and discovery require real hardware and optional BLE backends;
  they are validated live, not in unit tests (Principle V). Unit tests cover the
  adapter's pure lookup logic against a fake peer and the discovery constants.
- The Bumble adapter targets an external controller (e.g. ESP32-S3 over HCI) chosen
  because it exposes GATT primitives native stacks do not.
- The observed lock advertises only after physical keypad activation; this is a
  property of the device, not a defect of the scanner.
- Features 001–004 are present and correct; this feature composes them and supplies
  the transport/discovery to reach a real lock.
