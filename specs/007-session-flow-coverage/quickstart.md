# Quickstart: validating the unlock choreography

**Feature**: 007-session-flow-coverage · **Date**: 2026-08-14

No lock, no credentials, no network — that is the point of the feature.

## Prerequisites

```bash
cd <repo root>
source .venv/bin/activate
pip install -e ".[dev]"
```

## Scenario 1 — the choreography tests pass

```bash
pytest tests/test_session_flow.py -v
```

**Expected**: every test green, in well under a second. Names map to the user
stories: `test_full_unlock_*` (US1), `test_*_acks_*` / `test_*_wrong_ack_*`
(US2), `test_optional_capabilities_*` (US3), `test_notifications_released_*`
(US4).

## Scenario 2 — the guard actually guards (US1, SC-002)

Break the choreography on purpose and confirm the suite notices:

```bash
# In aqara_u200_ble/session.py, reverse PRE_AUTH_NOTIFY_ORDER, then:
pytest tests/test_session_flow.py -q
git checkout aqara_u200_ble/session.py
```

**Expected**: the order assertion fails. A guard that stays green when the thing
it guards is broken is not a guard — verify this once by hand.

## Scenario 3 — the whole suite stays fast (SC-006)

```bash
pytest -q --durations=5
```

**Expected**: total under five seconds; no single choreography test near a
second. If one is, the `asyncio.sleep` patch is not being applied.

## Scenario 4 — nothing in production moved (SC-007, FR-010)

```bash
git diff develop --stat -- aqara_u200_ble/
```

**Expected**: empty. The feature adds tests and documentation only.

## Scenario 5 — the gates

```bash
ruff check . && ruff format --check .
mypy aqara_u200_ble
pytest
```

**Expected**: all clean.

## What this does *not* prove

That a real U200 accepts the sequence. The fake answers what the captures say the
lock answers; it cannot tell you the radio, timing, or the lock's own firmware
agree. The live tutorial run
([03-first-unlock.md](../../docs/tutorials/03-first-unlock.md)) remains the only
evidence of that, and the roadmap says so.
