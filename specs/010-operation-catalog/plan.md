# Implementation Plan: Lock operation & settings catalog

**Branch**: `feature/010-operation-catalog` | **Date**: 2026-08-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/010-operation-catalog/spec.md`

## Summary

Consolidate the app's decompiled command enum into a structured, honestly-labelled
catalog (eight families, ~120 sub-commands) and a generic control-frame builder
that generalises feature 009's `build_operate_frame`. Every entry is tagged
`confirmed` (open/close/keepalive, verified on the lock) or `catalogued`
(decompiled, exact data unverified). No new actuation. A short doc records how to
promote a catalogued entry to confirmed (read the app builder or capture live).

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: standard library only for the catalog/builder (the
existing `cryptography`/transport stack is untouched)

**Storage**: N/A — the catalog is code/data in the package; no persistence

**Testing**: pytest; network-free (Constitution Principle V)

**Target Platform**: cross-platform CPython

**Project Type**: single Python library (`aqara_u200_ble`)

**Performance Goals**: N/A (in-memory lookups and byte assembly)

**Constraints**: no secrets in the repo; no lock actuation beyond the confirmed
commands; every `confirmed` status must cite real evidence (Principle II/IV)

**Scale/Scope**: ~120 catalog entries across 8 families; one generic builder; one
promotion procedure doc

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Security & Secret Hygiene** — ✅ PASS. Opcodes and frame structure are
  protocol, not secrets. No session keys, tokens or passwords enter the catalog.
- **II. Protocol Fidelity** — ✅ PASS. The builder reproduces the confirmed
  open/close frames byte-for-byte; catalogued entries are explicitly marked as
  unverified so nothing masquerades as confirmed wire truth.
- **III. Spec-Driven Development** — ✅ PASS. Spec/plan/tasks precede code. The
  catalog is retrospective documentation of decompiled behaviour and is labelled
  as such per this principle.
- **IV. Evidence & Reproducibility** — ✅ PASS. `confirmed` entries cite feature
  009's live captures; the promotion procedure lets a third party verify any
  catalogued entry from zero.
- **V. Quality & Standards** — ✅ PASS. Pure catalog/builder logic, typed, covered
  by network-free tests. No I/O in the new code.
- **VI. Branch & Change Discipline** — ✅ PASS. Work on `feature/010-operation-catalog`;
  merges `--no-ff`.

No violations → Complexity Tracking empty.

## Project Structure

### Documentation (this feature)

```text
specs/010-operation-catalog/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── catalog-api.md   # Phase 1 output
├── checklists/
│   └── requirements.md  # from /speckit-specify
└── tasks.md             # from /speckit-tasks
```

### Source Code (repository root)

```text
aqara_u200_ble/
├── operations_catalog.py   # NEW: CommandFamily, OperationEntry, CATALOG, lookups
└── lock_ops.py             # build_control_frame() generalising build_operate_frame

docs/protocol/
└── operations.md           # full catalog table + promotion procedure

tests/
└── test_operations_catalog.py  # NEW: coverage/labels + generic builder vs open/close
```

**Structure Decision**: Single-library layout. A new `operations_catalog.py`
holds the data + lookups; the generic frame builder lives with the existing
`lock_ops.py` (next to `build_operate_frame`). The human-readable table lives in
`docs/protocol/operations.md`.

## Complexity Tracking

> No Constitution Check violations. Nothing to justify.
