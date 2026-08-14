# Phase 0 Research: Verifiable unlock choreography

**Feature**: 007-session-flow-coverage · **Date**: 2026-08-14

No `NEEDS CLARIFICATION` markers were carried into the Technical Context. This
records the decisions and what they rule out.

## 1. How to stand in for the lock

**Decision**: a duck-typed `FakeLockClient` that stores the callbacks handed to
`start_notify` and reacts to `write_gatt_char`.

**Rationale**: `run_authenticated_lock_operation` already takes `bleak_client:
Any` and probes optional capabilities with `getattr(..., None)`. That is a
testing seam by construction — no production change is needed to inject a fake,
which is what keeps FR-010 satisfiable.

**Alternatives considered**:

- **A real `bleak` backend against a simulated peripheral** — rejected: radio I/O
  in unit tests violates Principle V and needs an OS-level BLE stack.
- **Refactoring the session to accept an injected protocol object** — rejected:
  a production change made solely for tests, on the one function nobody can
  regression-test on hardware in CI. The riskiest possible refactor.
- **`unittest.mock.AsyncMock`** — rejected: a mock records calls but cannot
  *answer* them. This exchange is a conversation; the fake has to talk back.

## 2. Where to intercept the cloud

**Decision**: `monkeypatch.setattr(session, "cloud_get_public_key", …)` and
`(session, "get_session_material", …)`.

**Rationale**: `session.py` does `from .kdf import cloud_get_public_key,
get_session_material`, binding the names in its own module namespace. Patching
`kdf.cloud_get_public_key` would leave `session`'s binding untouched and the test
would try to reach the network — the failure mode being designed out.

**Alternatives considered**: an HTTP-level fake (patching `urlopen`) — rejected
as over-reach: feature 001 already owns cloud behaviour, and this feature should
fail for choreography reasons only.

## 3. Real time in the tests

**Decision**: patch `asyncio.sleep` to a no-op coroutine per test.

**Rationale**: the production sleeps (0.04 s per auth fragment, 0.02 s per CCCD)
exist to pace CoreBluetooth writes so fragments are not dropped — a radio
concern. Keeping them real would cost roughly 0.3 s per scenario and grow with
every test added, for zero extra assurance (FR-009, SC-006).

**Alternatives considered**:

- **Leaving them real** — rejected on cost, as above.
- **Making the delay a parameter of the production function** — rejected: FR-010
  forbids changing production behaviour for the convenience of the test.

## 4. Where the fake's answers come from

**Decision**: build them with `build_auth_message` and
`fragment_auth_message(..., direction=0xDA)`.

**Rationale**: hand-written byte literals for the lock's side would duplicate the
framing rules and drift the moment either changes. These primitives are pinned
byte-for-byte against real captures by feature 004's tests, so reusing them is
leaning on independently verified code.

**Circularity check** — the honest objection is "you are testing the framing with
the framing". It does not apply: feature 004 asserts the primitives against
*captured bytes*, not against themselves. This feature assumes those primitives
and asserts the **sequence** built on top. If the primitives broke, 004's tests
fail first and loudly.

**Alternatives considered**: committing captured lock frames as fixtures —
attractive for fidelity, rejected under Principle I: real frames come from a real
session with a real device, and sanitizing them irreversibly would leave
something no longer byte-real anyway.

## Behaviour confirmed by reading the production code

- The lock's fragments are direction-tagged `0xDA`; the last fragment is marked
  by `fragment[1] == 0xFF`, which is what `read_full_auth_message` waits for.
- The public-key read loop runs at most **6** times, tolerating empty ACKs and
  accepting the first `0x06` frame whose body is ≥ 33 bytes.
- The control response is optional: a timeout yields `None` rather than an error,
  because the write itself is the action that moves the bolt.
- Cleanup runs in a `finally` that suppresses every exception from `stop_notify`,
  so an adapter that fails to release still lets the original error surface.
