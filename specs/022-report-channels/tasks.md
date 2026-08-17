# Tasks: Capturar ff64/ff92

- [X] T001 `session.py`: `_debug_report(channel, data)` (print bajo U200_DEBUG) + `on_report_notify(channel)` reemplaza `on_notify_ignored`; wiring ff64→"ff64", ff92→"ff92".
- [X] T002 Test del helper en `tests/test_session_flow.py` (silencioso sin flag; registra canal+hex con flag).
- [X] T003 `pytest`/`ruff`/`mypy` verdes; CHANGELOG 0.8.0; merge `--no-ff`.
