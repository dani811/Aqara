# Implementation Plan: BLE authentication handshake

**Branch**: `feature/004-ble-auth-handshake` | **Date**: 2026-08-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/004-ble-auth-handshake/spec.md`

**Note**: Retrospective plan for the project's central module. `session.py` already
exists and was confirmed live; this plan gates its unchanged migration and pins the
CRC breakthrough with a concrete test vector.

## Summary

Reconstruct the `0610`/`0710` authentication handshake exactly as the lock expects:
build frames whose header integrity field is the **CRC-16/ARC of the body** (the
discovery that broke the wall), fragment/reassemble them for BLE, parse replies,
and protect control payloads with AES-CCM (short tag). The pure logic is fully
testable offline; the live BLE orchestration (`run_authenticated_lock_operation`)
sequences the app's observed pre-auth steps and is validated against a real lock.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: `cryptography` (AES-CCM). `asyncio` + a caller-provided
BLE client (bleak/bumble, injected — not imported here as a hard dep) for the live
flow. Imports features 001 (`kdf`), 002 (`protocol`), 003 (`lock_ops`).

**Storage**: None. Session material and headers come from the caller at runtime.

**Testing**: `pytest`. Unit tests pin the CRC table against a captured frame,
build/parse round-trips, fragment/reassemble identity, and AES-CCM
encrypt/decrypt round-trip with throwaway keys. The async BLE flow is out of unit
scope (needs hardware) — verified live (Principle V).

**Target Platform**: Any OS with Python 3.11+; the live flow needs a BLE controller.

**Project Type**: Library (`aqara_ble/session.py`).

**Performance Goals**: Fragment writes are deliberately spaced (~40 ms) so the
controller does not drop fragments — a correctness constraint, not a perf target.

**Constraints**: Header CRC MUST be CRC-16/ARC little-endian over the body.
Fragmentation MUST be an exact inverse. No secret embedded (Principle I).

**Scale/Scope**: One ~590-line module: CRC table + `crc16_aqara`,
`build_auth_message`, `fragment_auth_message`, `assemble_auth_fragments`,
`parse_auth_message`, `encrypt_control_payload`/`decrypt_control_payload`,
`SessionMaterial`, the UUID/order constants, and `run_authenticated_lock_operation`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|-----------|------|--------|
| I. Security & Secret Hygiene | No session key/nonce/token embedded; test vectors are a public key + throwaway crypto fixtures | ✅ PASS |
| II. Protocol Fidelity | CRC, framing, AES-CCM reproduce captures byte-exact; migrated unchanged | ✅ PASS |
| III. Spec-Driven Development | Spec + plan precede the migration | ✅ PASS |
| IV. Evidence & Reproducibility | CRC pinned by a captured frame; live wall-break documented | ✅ PASS |
| V. Quality & Standards | Typed, pure-logic tested; async BLE flow excluded from unit tests | ✅ PASS |
| VI. Branch & Change Discipline | Prefixed branch, `--no-ff` merge | ✅ PASS |

No violations. Complexity Tracking not required. (The module is large and
branch-heavy by nature — the same wide-flow rationale the constitution's tooling
config already accepts via the PLR ignores.)

## Project Structure

### Documentation (this feature)

```text
specs/004-ble-auth-handshake/
├── plan.md
├── spec.md
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
aqara_ble/
├── session.py           # THIS FEATURE — CRC, frame build/parse, fragmentation,
│                        #   AES-CCM control crypto, UUID/order constants, and the
│                        #   live run_authenticated_lock_operation orchestration
└── __init__.py          # extended to export the handshake/session surface

tests/
└── test_session.py      # CRC vector, build/parse, fragment round-trip, AES-CCM

docs/protocol/
└── auth-handshake.md    # Header layout, the CRC-16/ARC field, fragmentation
```

**Structure Decision**: `session.py` is migrated whole (files are not split, per
"no logic change"). It sits at the top of the internal dependency graph — importing
kdf, protocol, and lock_ops — which is why it is sequenced after them.

## Complexity Tracking

> No Constitution Check violations. Section intentionally empty.
