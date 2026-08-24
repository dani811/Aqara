# Tasks: Async telemetry/test fixes + release 0.5.0

## Phase 1: Fixes (#3, #2)

- [X] T001 [US1] `session.py::_run_cloud_phase`: capturar `threading.get_ident()` **dentro** del callable ejecutado por `asyncio.to_thread` (envolver `fn` en un traza que guarde el id en un holder) y loguear ese id en la línea de "completed"; sin datos sensibles; API/comportamiento intactos.
- [X] T002 [US1] `tests/test_async_cloud_boundary.py`: test nuevo que ejecuta `_run_cloud_phase` con un helper que devuelve su `get_ident()`, y prueba que el id **capturado/logueado** = worker y ≠ hilo del event loop (usar caplog DEBUG o el holder).
- [X] T003 [US2] `tests/test_async_cloud_boundary.py::test_slow_cloud_does_not_stall_event_loop`: derivar `scheduled` del bucle (5) y exigir `>= ceil(0.8*scheduled)`; sin asserts de ms; el fake cloud sigue bloqueando de verdad off-loop.
- [X] T004 Correr `pytest`, `ruff`, `mypy aqara_ble` en verde.

## Phase 2: Release (#4) + cierre #1

- [X] T005 [US3] `pyproject.toml`: corregir `[project.urls]` al repo real (`github.com/dani811/Aqara`); confirmar `version = "0.5.0"`.
- [X] T006 [US3] Gate de release: `pytest`, `ruff check`, `ruff format --check`, `mypy --strict`; `python -m build`; verificar que la wheel contiene `aqara_ble/` y `py.typed` e instala en un venv limpio.
- [X] T007 [US3] `CHANGELOG.md`: marcar 0.5.0 como release; nota "artefacto para HA `manifest.json` requirements". Merge `--no-ff` a `develop`.
- [ ] T008 [US3] Crear tag inmutable `v0.5.0` desde el commit de `develop` validado; `git push` de `develop` + tag; `gh release create v0.5.0`.
- [ ] T009 Cerrar issues con referencia al commit/tag: #1 (resuelta por 012), #2, #3 (esta feature), #4 (release 0.5.0). Comentar en el PR #2 de `haos_aqara` que ya puede fijar `aqara-ble==0.5.0`.

## Dependencies
Phase 1 antes de Phase 2 (release exige el gate verde). T008/T009 son las acciones outward finales.

## MVP
#2 y #3 corregidos y verdes; con eso el release (T005–T009) es mecánico.
