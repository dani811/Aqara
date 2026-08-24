# Implementation Plan: Control channel framing

**Branch**: `feature/002-control-channel-framing` | **Date**: 2026-08-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/002-control-channel-framing/spec.md`

**Note**: Retrospective plan. The `protocol.py` module already exists and is pinned
by captured test vectors; this plan documents its design and gates the unchanged
migration through the Constitution.

## Summary

Provide the pure, dependency-free framing primitives for the lock's control
channel: a `ControlRequest` (kind/command/body/trailer) with parse and serialize
that are exact inverses, a command-name map with a stable fallback, an `ATTPacket`
model for analysis, symbolic ATT handle constants, and a CRC-HQX bulk-integrity
check. No I/O, no crypto, no session state — this is the wire-shape layer every
higher feature depends on.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: Standard library only (`binascii.crc_hqx`, `dataclasses`).
No third-party runtime dependency — this module is intentionally a leaf.

**Storage**: None.

**Testing**: `pytest`. Unit tests replay captured frames as fixtures and assert
exact parse results, round-trip identity, and CRC pass/fail. No network, no BLE.

**Target Platform**: Any OS with Python 3.11+.

**Project Type**: Library (module `aqara_ble/protocol.py`).

**Performance Goals**: Not performance-sensitive; per-frame parsing.

**Constraints**: Parse/serialize MUST be exact inverses (round-trip identity).
The bulk CRC is CRC-HQX (XMODEM), not the handshake's CRC-16/ARC.

**Scale/Scope**: One ~70-line module: `ATTPacket`, `ControlRequest`,
`control_command_name`, `parse_control_request`, `valid_crc`, and the ATT handle
constants.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|-----------|------|--------|
| I. Security & Secret Hygiene | No secrets; test vectors are framing-only fragments | ✅ PASS |
| II. Protocol Fidelity | Parsing/CRC reproduce observed frames exactly; migrated unchanged | ✅ PASS |
| III. Spec-Driven Development | Spec + plan precede the migration | ✅ PASS |
| IV. Evidence & Reproducibility | Behavior pinned by captured vectors; documented in protocol docs | ✅ PASS |
| V. Quality & Standards | Typed, stdlib-only, pure-logic tests, no I/O | ✅ PASS |
| VI. Branch & Change Discipline | Prefixed branch, `--no-ff` merge | ✅ PASS |

No violations. Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/002-control-channel-framing/
├── plan.md
├── spec.md
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
aqara_ble/
├── protocol.py          # THIS FEATURE — ATTPacket, ControlRequest, parsing,
│                        #   command names, ATT handles, CRC-HQX validation
└── __init__.py          # extended to export the control-framing surface

tests/
└── test_protocol.py     # Captured-frame fixtures: parse, round-trip, CRC

docs/protocol/
└── control-channel.md   # Wire contract: frame shape, command map, CRC variant
```

**Structure Decision**: Single leaf module with no internal dependencies. It is
migrated whole; features 003 (operations) and 004 (handshake) import from it.

## Complexity Tracking

> No Constitution Check violations. Section intentionally empty.
