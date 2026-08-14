# Implementation Plan: Lock operations

**Branch**: `feature/003-lock-operations` | **Date**: 2026-08-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/003-lock-operations/spec.md`

**Note**: Retrospective plan. `lock_ops.py` and `volume.py` already exist; this
plan gates their unchanged migration through the Constitution.

## Summary

Turn human intents into wire-ready lock commands and voice-volume control writes,
and dispatch them through a caller-provided authenticated transport. Two small
modules: `lock_ops.py` (lock/unlock/keepalive/state payloads + prefixes + a
transport port) and `volume.py` (named presets bound to captured control requests,
reusing feature 002's `ControlRequest`). No BLE, no keys, no crypto here — the
transport is injected.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: Standard library (`dataclasses`, `enum`, `typing.Protocol`).
`volume.py` imports `ControlRequest` from `aqara_u200_ble.protocol` (feature 002).

**Storage**: None.

**Testing**: `pytest`. Unit tests assert intent→payload/prefix mapping, lock≠unlock,
dispatch-through-a-fake-transport, alias/case handling, volume serialization, and
rejection of unknown intents/presets. No network, no BLE.

**Target Platform**: Any OS with Python 3.11+.

**Project Type**: Library (`aqara_u200_ble/lock_ops.py`, `aqara_u200_ble/volume.py`).

**Performance Goals**: Not performance-sensitive.

**Constraints**: Payloads MUST match captures exactly (Principle II). This feature
MUST NOT perform I/O or encryption; it depends on an injected transport (FR-007).

**Scale/Scope**: `lock_ops.py` (~100 lines) and `volume.py` (~95 lines).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|-----------|------|--------|
| I. Security & Secret Hygiene | Payloads are protocol opcodes, not secrets; no captures | ✅ PASS |
| II. Protocol Fidelity | Payloads/prefixes reproduce decrypted captures; migrated unchanged | ✅ PASS |
| III. Spec-Driven Development | Spec + plan precede the migration | ✅ PASS |
| IV. Evidence & Reproducibility | Payloads tied to decrypted captures; documented in operations doc | ✅ PASS |
| V. Quality & Standards | Typed, stdlib-only, pure-logic tests via fake transports, no I/O | ✅ PASS |
| VI. Branch & Change Discipline | Prefixed branch, `--no-ff` merge | ✅ PASS |

No violations. Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/003-lock-operations/
├── plan.md
├── spec.md
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
aqara_u200_ble/
├── lock_ops.py          # THIS FEATURE — operations, payloads, prefixes, transport port
├── volume.py            # THIS FEATURE — volume presets bound to control requests
└── __init__.py          # extended to export the operations surface

tests/
├── test_lock_ops.py     # intent→payload, lock≠unlock, dispatch, rejection
└── test_volume.py       # preset→bytes, dispatch, rejection

docs/protocol/
└── operations.md        # Operation payload map + volume requests
```

**Structure Decision**: Two cohesive modules migrated together (both are the
"operations" layer). `volume.py` depends on feature 002's `ControlRequest`; both
are consumed by the session (feature 004) via the transport port.

## Complexity Tracking

> No Constitution Check violations. Section intentionally empty.
