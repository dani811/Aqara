# Tasks: CLI empaquetado fino sobre la API

## Phase 1: US1 + US2 — CLI en el paquete (P1)

- [X] T001 Crear `aqara_u200_ble/cli.py` a partir de `examples/lock_cli.py`: `main()` + `async run()`, subcomandos `login/scan/lock/unlock/operate`, flags `--transport/--port/--mac/--timeout/--account/--password`. Carga de credenciales desde flags o entorno/`.env` (reutiliza `examples/auth_from_env.py` o un helper local `_auth_from(args)`); imprime modelo en scan; exit codes por clase; sin secretos. **Cero lógica de protocolo** (solo API pública).
- [X] T002 `pyproject.toml`: `[project.scripts] aqara = "aqara_u200_ble.cli:main"`; quitar `cli.py` del ámbito excluido (que entre en ruff/mypy del paquete); mantener `examples` excluido.
- [X] T003 Garantizar pureza: `aqara_u200_ble/__init__.py` NO importa `cli`; `cli.py` importa `argparse`/`os` solo dentro de sí. Reinstalar editable (`pip install -e .`) para registrar el comando.
- [X] T004 `examples/lock_cli.py`: reducir a un envoltorio (`from aqara_u200_ble.cli import main; raise SystemExit(main())`) o `git rm` y actualizar `examples/README.md` para apuntar a `aqara`.

## Phase 2: Tests + docs

- [X] T005 `tests/test_cli.py`: (a) `import aqara_u200_ble` NO deja `aqara_u200_ble.cli` en `sys.modules` y no lee `os.environ` (monkeypatch os.environ.__getitem__/get con espía o comprobar módulos); (b) dispatch: cada subcomando llama al método esperado de un `U200Client`/transporte fake (parcheando `aqara_u200_ble.cli.U200Client`/`scan`/`auth_from_env`), (c) exit codes por clase (config faltante=4, NoDeviceFound=2, U200ClientError=1, éxito=0), (d) `repr`/salida sin secretos.
- [X] T006 mypy: `cli.py` bajo `strict`; tipar `run(args)`/`main()`. `ruff check`/`format`/`pytest` verdes.
- [X] T007 Docs: `README.md` (sección "CLI: `aqara …`" + nota "integraciones importan la API"), `docs/devices/u200/validation.md` (usar `aqara`), `tools/README.md` si aplica; `CHANGELOG` 0.5.0; bump versión.

## Dependencies
US1+US2 en T001–T004 (mismo módulo). Tests/docs después. 

## MVP
`aqara lock` funciona instalado y `import aqara_u200_ble` sigue puro.
