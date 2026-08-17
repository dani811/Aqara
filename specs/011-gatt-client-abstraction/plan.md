# Implementation Plan: GATT client abstraction

**Branch**: `feature/011-gatt-client-abstraction` | **Date**: 2026-08-15 | **Spec**: [spec.md](spec.md)

**Status**: Retrospective (documents commit 4d0f5c0 as shipped).

## Summary

Introduce `GattClient`/`AdvancedGattClient` `typing.Protocol`s in a new
`aqara_u200_ble/gatt.py`; retype `run_authenticated_lock_operation`'s parameter
from `bleak_client: Any` to `client: GattClient`; keep optional low-level
capabilities as best-effort `getattr` discovery declared by the extended protocol.
No wire behavior changes.

## Technical Context

**Language**: Python ≥3.10, stdlib `typing.Protocol` only. **Deps**: none.
**Testing**: `tests/test_gatt_abstraction.py` (minimal client completes the flow;
optional-capability absence is skipped; structural conformance; exports).
**Constraints**: Constitution II (byte/behavior-preserving refactor), V (typed
public API, tests without radio/network).

## Constitution Check

| Principle | Status | How |
| --- | --- | --- |
| I Secrets | ✅ | Pure typing layer; no secrets. |
| II Protocol fidelity | ✅ | Only the parameter type and capability discovery change; wire sequence/bytes identical (verified by unchanged session-flow tests). |
| III SDD | ⚠️→✅ | Built before its spec existed; this retrospective doc closes the gap honestly. |
| IV Evidence | ✅ | Reconstructed from the commit diff and shipped code. |
| V Quality | ✅ | `Protocol`-typed API, tests without I/O, exported in `__all__`. |
| VI Branches | ✅ | Retrospective on `docs/011-*`, merged `--no-ff`. |

## Project Structure

```text
aqara_u200_ble/gatt.py       # NEW: GattClient + AdvancedGattClient protocols
aqara_u200_ble/session.py    # bleak_client: Any -> client: GattClient (+ getattr on client)
aqara_u200_ble/__init__.py   # export GattClient
tests/test_gatt_abstraction.py  # NEW: structural conformance + best-effort optional
```

## Complexity Tracking

None. The only deviation is process (spec authored after the fact), recorded above.
