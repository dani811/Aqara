# Implementation Plan: Verifiable unlock choreography

**Branch**: `feature/007-session-flow-coverage` | **Date**: 2026-08-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/007-session-flow-coverage/spec.md`

## Summary

Add `tests/test_session_flow.py`: a `FakeLockClient` that implements the duck-typed
surface `run_authenticated_lock_operation` expects (`start_notify`, `stop_notify`,
`write_gatt_char`, and optionally the low-level extras), answering scripted frames
through the stored notify callbacks. The two cloud calls are monkeypatched at their
import site in `aqara_ble.session`. Tests drive the coroutine with
`asyncio.run` and assert the recorded exchange. No production module changes.

## Technical Context

**Language/Version**: Python 3.11+ (developed on 3.14)

**Primary Dependencies**: `pytest`, stdlib `asyncio`. `cryptography` (already a
runtime dependency) provides the AES-CCM used to build the fake control response.
No new dependency, and specifically **not** `pytest-asyncio` — the coroutine is
driven with `asyncio.run` inside ordinary sync tests.

**Storage**: None.

**Testing**: `pytest`. One new file, `tests/test_session_flow.py`. No socket, no
radio: the fake client never touches I/O, and `asyncio.sleep` is neutralized so
the suite does not wait in wall-clock time.

**Target Platform**: Any OS with Python 3.11+.

**Project Type**: Library — this feature adds tests only.

**Performance Goals**: The new file must add well under a second (SC-006). The
production code sleeps 0.04 s per auth fragment and 0.02 s per CCCD; a real-time
run of ~6 fragments plus 4 CCCDs would cost ~0.3 s per test and grow with each
scenario, hence the patched sleep.

**Constraints**:

- No production behaviour change (FR-010): the diff outside `tests/` and `docs/`
  is empty.
- No real secret (FR-008): the fixtures are a throwaway AES-CCM key/nonce and an
  ephemeral EC public key, which is public by definition.
- The fake must stay *duck-typed*, mirroring how `bleak`/`BumbleGattAdapter` are
  consumed — the production code calls `getattr(client, "request_mtu", None)` and
  friends, so absence is expressed by simply not defining the attribute.

**Scale/Scope**: ~260 lines of test code, ~12 test functions.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|-----------|------|--------|
| I. Security & Secret Hygiene | Throwaway key/nonce fixtures; the EC public key is public material; no capture committed | ✅ PASS |
| II. Protocol Fidelity | No wire byte changes. The fake's answers are built with the frame primitives feature 004 already pins byte-exact against captures | ✅ PASS |
| III. Spec-Driven Development | spec → plan → tasks → implement, this being the plan | ✅ PASS |
| IV. Evidence & Reproducibility | The choreography asserted here is the one documented in `docs/protocol/auth-handshake.md`; the tests become executable evidence of it | ✅ PASS |
| V. Quality & Standards | Typed test helpers, `ruff` + `mypy --strict` gates, and — the point of the feature — no network or radio I/O in unit tests | ✅ PASS |
| VI. Branch & Change Discipline | `feature/007-*` matching the Spec Kit number, merged `--no-ff` | ✅ PASS |

**Post-Phase-1 re-check**: unchanged. The design adds one test module and no
production surface. ✅ PASS

### Honesty note on Principle V

Principle V's rule is "unit tests MUST NOT perform network or radio I/O", and the
roadmap's limitation says the live flow "needs real hardware". Both remain true:
this feature does **not** claim the flow is proven against a lock. It proves the
orchestration — order, tolerance, errors, cleanup — against a stand-in. The
roadmap entry is narrowed to say exactly that (SC-008), not deleted.

## Project Structure

### Documentation (this feature)

```text
specs/007-session-flow-coverage/
├── plan.md              # This file
├── spec.md
├── research.md          # Phase 0 — the four design decisions
├── data-model.md        # Phase 1 — fake client, exchange record, script
├── quickstart.md        # Phase 1 — how to run and what to expect
├── contracts/
│   └── transport-surface.md   # Phase 1 — what the session requires of a client
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
tests/
└── test_session_flow.py   # THIS FEATURE — FakeLockClient + choreography tests

docs/
├── roadmap.md             # narrow the "not unit-tested" limitation (SC-008)
└── protocol/auth-handshake.md  # point at the executable choreography
```

**Structure Decision**: A separate test module rather than growing
`tests/test_session.py`. That file pins *pure primitives* (CRC, framing,
AES-CCM); this one drives an async orchestration with a stateful fake. Different
shape, different failure modes, different reasons to be read.

## Design decisions

1. **The fake answers through the callbacks it was handed.** `start_notify(uuid,
   cb)` stores `cb`; `write_gatt_char` reacts by invoking the right callback with
   scripted fragments. That is exactly the inversion the real stack performs, so
   the production code needs no seam added for testability.
2. **Answers are built with `build_auth_message` + `fragment_auth_message(direction=0xDA)`.**
   Hand-rolling the lock's bytes would duplicate the framing logic and drift.
   These primitives are independently verified byte-for-byte against captures in
   feature 004, so this is reuse of proven code, not a circular assumption.
3. **Cloud calls are patched at the session's import site** —
   `monkeypatch.setattr(session, "cloud_get_public_key", …)` and
   `(session, "get_session_material", …)` — because `session.py` imports the
   names directly. Patching `kdf` would not intercept them.
4. **`asyncio.sleep` is patched to a no-op coroutine** for the duration of each
   test. The production sleeps exist to pace CoreBluetooth writes; their timing
   is a radio concern, not a choreography one, and keeping them real would add
   seconds to the suite for nothing.
5. **The verify-frame ACK is answered by frame kind, not by counting writes**, so
   a future reordering fails loudly on the assertion rather than silently
   confusing the fake.

## Complexity Tracking

> No Constitution Check violations. Section intentionally empty.
