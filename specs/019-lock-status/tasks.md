# Tasks: Lectura de estado (LockState)

## Phase 1: LockState + decode (US1/US2)

- [X] T001 `aqara_u200_ble/lock_state.py`: `LockState` (frozen dataclass: `raw_hex: str|None`, `source: str`, `locked: bool|None=None`, `battery_percent: int|None=None`, `responded: bool`) + `decode_lock_state(raw: bytes|None, source: str) -> LockState`. Decodifica SOLO lo confirmado (hoy: ninguno con certeza → raw + responded); documenta la hipótesis del byte de dirección en la respuesta de operate (`74 00 77 06`).
- [X] T002 `tests/test_lock_state.py`: raw preservado; sin respuesta → responded=False/raw_hex=None; campos no confirmados = None; bytes basura no lanzan.
- [X] T003 `client.py`: `async status() -> LockState` (llama `operate(KEEPALIVE)`, envuelve la respuesta con `decode_lock_state(source="keepalive")`); `OperationResult.state` o método para exponer `LockState(source="operation")` sin perder `response_hex`.
- [X] T004 Export en `__init__.py` (`LockState`, `decode_lock_state`) + `test_package_api`.

## Phase 2: CLI + docs

- [X] T005 `cli.py`: subcomando `state` → construye cliente y hace `status()`, imprime `LockState` (incluye `raw_hex`), sin secretos; exit codes por clase; test de dispatch en `test_cli.py`.
- [X] T006 Docs: `docs/devices/u200/operations.md` (muestras reales: keepalive `2f002c06`, unlock `74007706`; estado "respuesta observada, decode pendiente"); `validation.md` (`aqara state` + cómo capturar abierta/cerrada); anotar eventos espontáneos como límite (sesión persistente). CHANGELOG 0.6.0; bump versión.

## Phase 3: Verify
- [X] T007 `pytest`/`ruff`/`mypy` verdes; merge `--no-ff`; (validación real `aqara state` la corre el usuario para capturar muestras).

## Dependencies
US1 (T001–T004) antes que CLI/docs. 

## MVP
`status()` devuelve `LockState` con `raw` real; base honesta para decodificar con muestras.
