# Tasks: GATT client abstraction (retrospective)

All tasks below were completed in commit `4d0f5c0` (2026-08-15); marked done to
reflect the shipped state.

- [X] T001 Define `GattClient` Protocol (`write_gatt_char`, `start_notify`, `stop_notify`) in `aqara_u200_ble/gatt.py`.
- [X] T002 Define `AdvancedGattClient` Protocol with the optional best-effort capabilities.
- [X] T003 Retype `run_authenticated_lock_operation` parameter `bleak_client: Any` → `client: GattClient` and update internal references / `getattr` probing to `client`.
- [X] T004 Export `GattClient` from `aqara_u200_ble/__init__.py` (`__all__`).
- [X] T005 Tests `tests/test_gatt_abstraction.py`: minimal client completes the flow; optional capabilities absent are skipped; structural conformance; package export.
- [X] T006 Keep the Bumble path and prior session-flow tests green (behavior-preserving).

## Notes
Retrospective feature: no new work; this closes the SDD trace gap (010 → 012).
