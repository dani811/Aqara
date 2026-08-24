# Implementation Plan: End-to-end autonomous unlock

**Branch**: `feature/005-end-to-end-unlock` | **Date**: 2026-08-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/005-end-to-end-unlock/spec.md`

**Note**: Retrospective plan. `scanner.py` and `bumble_transport.py` already exist;
this plan gates their unchanged migration and the composition of features 001–004
into a live end-to-end unlock.

## Summary

Complete the autonomous story: passive discovery (`scanner.py`) plus a Bumble GATT
adapter (`bumble_transport.py`) that presents the client interface
`run_authenticated_lock_operation` expects — including the low-level GATT
primitives (Read-By-Type, MTU, data-length, connection update) the lock's pre-auth
requires. With such a transport, the handshake (feature 004) runs against a real
lock and dispatches an operation (feature 003) using cloud key material (feature
001) and control framing (feature 002). Optional BLE backends stay optional: the
package imports without them.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: Standard library at import time. `bleak` (native scan)
and `bumble` (external-controller GATT) are **optional** extras, imported lazily or
under `TYPE_CHECKING`, so the package imports without either.

**Storage**: None. Credentials/addresses come from the caller/environment.

**Testing**: `pytest`. Unit tests cover the adapter's pure characteristic-lookup
against a fake peer, the discovery constants, and package-API completeness (optional
backends truly optional). The live end-to-end unlock and real scan need hardware and
are validated live (Principle V) — not unit-tested.

**Target Platform**: Any OS with Python 3.11+ for the library; live use needs a BLE
controller (native or ESP32-S3 over HCI via Bumble).

**Project Type**: Library (`aqara_ble/scanner.py`, `aqara_ble/bumble_transport.py`).

**Performance Goals**: Not applicable; correctness and not-hanging dominate.

**Constraints**: Every low-level GATT request MUST be bounded by its own timeout so
a mid-request disconnect cannot hang forever. Optional deps MUST NOT break import
(FR-006). No secret embedded (Principle I).

**Scale/Scope**: `scanner.py` (~48 lines) and `bumble_transport.py` (~140 lines,
`BumbleGattAdapter`).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|-----------|------|--------|
| I. Security & Secret Hygiene | No credential/MAC/capture; addresses from the environment | ✅ PASS |
| II. Protocol Fidelity | Transport reproduces the app's pre-auth GATT primitives; migrated unchanged | ✅ PASS |
| III. Spec-Driven Development | Spec + plan precede the migration | ✅ PASS |
| IV. Evidence & Reproducibility | Transport quirks tied to live btsnoop evidence; tutorial reproduces the run | ✅ PASS |
| V. Quality & Standards | Typed; pure lookup + constants unit-tested; live flow excluded | ✅ PASS |
| VI. Branch & Change Discipline | Prefixed branch, `--no-ff` merge | ✅ PASS |

No violations. Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/005-end-to-end-unlock/
├── plan.md
├── spec.md
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
aqara_ble/
├── scanner.py           # THIS FEATURE — passive discovery (optional bleak)
├── bumble_transport.py  # THIS FEATURE — BumbleGattAdapter (optional bumble)
└── __init__.py          # extended to export scan + BumbleGattAdapter

tests/
├── test_transport.py    # adapter lookup against a fake peer
└── test_package_api.py  # __all__ completeness; imports without optional backends

docs/tutorials/
└── end-to-end-unlock.md # how to run the full autonomous unlock from zero
```

**Structure Decision**: Two transport/discovery modules migrated together. Both are
importable without optional backends (lazy / `TYPE_CHECKING`), which the
package-API test verifies. They sit at the edge of the graph — nothing else imports
them; they carry the composed flow to real hardware.

## Complexity Tracking

> No Constitution Check violations. Section intentionally empty.
