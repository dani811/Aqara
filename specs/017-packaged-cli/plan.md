# Implementation Plan: CLI empaquetado fino sobre la API

**Branch**: `feature/017-packaged-cli` | **Date**: 2026-08-17 | **Spec**: [spec.md](spec.md)

## Summary

Mover el runner a `aqara_u200_ble/cli.py` (adaptador fino), registrar el *console
script* `aqara` en `pyproject.toml`, y garantizar que `import aqara_u200_ble` no
carga el CLI ni lee el entorno. `examples/lock_cli.py` pasa a un envoltorio de una
línea que delega en `aqara_u200_ble.cli:main`. Ningún byte de protocolo cambia; la
API pública es la única superficie de acoplamiento.

## Technical Context

**Language**: Python ≥3.10, solo stdlib para el CLI (argparse). **Deps**: sin
nuevas. **Testing**: pytest; el CLI se prueba con transporte/nube fake y con
`aqara ... --help`/dispatch, sin radio ni red. **Constraints**: Constitución II
(protocolo intacto), I (sin secretos; el CLI puede leer entorno, la API no — se
preserva la decisión de 014 con un test de que `import aqara_u200_ble` no importa
`cli` ni lee env). **Scope**: `cli.py` nuevo, `pyproject` script, envoltorio de
ejemplo, ~6 tests, docs.

## Constitution Check

| Principio | Estado | Cómo |
| --- | --- | --- |
| I Secretos / pureza | ✅ | `cli.py` (consumidor) lee entorno; la API importable no. Test: `import aqara_u200_ble` no carga `cli` ni toca `os.environ`. Sin secretos impresos. |
| II Protocolo | ✅ | El CLI no contiene lógica de protocolo; solo llama a la API. |
| III SDD | ✅ | spec→plan→tasks→implement en rama propia. |
| IV Evidencia | ✅ | N/A (sin protocolo nuevo). |
| V Calidad | ✅ | Tipado, tests de dispatch/pureza, ruff/mypy; `cli.py` entra en el lint del paquete (ya no excluido como examples/). |
| VI Ramas | ✅ | rama propia, merge `--no-ff`. |

**Gate**: PASS.

## Project Structure

```text
aqara_u200_ble/
├── cli.py           # NUEVO: adaptador de terminal (argparse, credenciales, print, exit codes)
├── __init__.py      # SIN importar cli (mantiene el import puro)
pyproject.toml       # [project.scripts] aqara = "aqara_u200_ble.cli:main"; cli.py fuera del extend-exclude
examples/
├── lock_cli.py      # queda como envoltorio: `from aqara_u200_ble.cli import main` (compat)
├── auth_from_env.py # se mantiene (helper de credenciales desde .env, reutilizado por cli.py)
tests/
├── test_cli.py      # NUEVO: dispatch por subcomando con API fake; import-puro; sin secretos; exit codes
docs/                # README + validation: `aqara` como vía de terminal
```

**Structure Decision**: el CLI vive en el paquete como módulo aparte no importado
por `__init__`, así el comando se instala pero `import aqara_u200_ble` sigue puro.
La carga de credenciales desde `.env`/entorno se concentra en `cli.py`
(reutilizando `examples/auth_from_env.py`), único punto que toca el entorno.

## Complexity Tracking

Sin violaciones.
