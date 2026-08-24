# Implementation Plan: Async telemetry/test fixes + release 0.5.0

**Branch**: `fix/018-async-telemetry-release` | **Date**: 2026-08-17 | **Spec**: [spec.md](spec.md)

## Summary

Corregir dos defectos verificados de la línea async (telemetría del thread id #3;
aserto ≥80% #2), corregir URLs de `pyproject.toml`, correr el gate completo,
construir y verificar la wheel (con `py.typed`), y crear el tag `v0.5.0`. Cierra
#2/#3/#4 y desbloquea `haos_aqara`; #1 se cierra por resuelta (feature 012).

## Technical Context

**Language**: Python ≥3.10. **Deps**: sin nuevas (build ya en extra dev).
**Testing**: pytest (nuevo test de worker-id; refuerzo del test 80%), sin I/O.
**Constraints**: Constitución I (sin secretos en logs), II (comportamiento/bytes
intactos — solo cambia el valor de un log y un aserto de test), V (mypy strict,
ruff), VI (rama `fix/018-*`, merge `--no-ff`). **Scope**: `session.py`
(`_run_cloud_phase`), `tests/test_async_cloud_boundary.py`, `pyproject.toml`,
docs de release, tag.

## Constitution Check

| Principio | Estado | Cómo |
| --- | --- | --- |
| I Secretos | ✅ | El fix solo cambia un id numérico de hilo (no sensible); ningún dato nuevo en logs. |
| II Protocolo/comportamiento | ✅ | `to_thread` sigue siendo el límite; no cambian bytes, API ni orden BLE. |
| III SDD | ✅ | spec→plan→tasks→implement en rama propia. |
| IV Evidencia | ✅ | Defectos citados por file:line; test que demuestra worker≠loop. |
| V Calidad | ✅ | mypy strict, ruff, pytest; wheel verificada. |
| VI Ramas | ✅ | `fix/018-*`, merge `--no-ff`, tag inmutable. |

**Gate**: PASS.

## Project Structure

```text
aqara_ble/session.py            # _run_cloud_phase: capturar worker id dentro del hilo
tests/test_async_cloud_boundary.py   # #2 aserto ≥80% genérico; #3 test worker≠loop
pyproject.toml                       # URLs correctas (repo real); versión 0.5.0 (ya)
docs/ or RELEASE notes               # artefacto/versión para HA manifest.json
```

**Structure Decision**: cambios mínimos y quirúrgicos; el release es proceso
(gate + build + tag), no código nuevo.

## Complexity Tracking

Sin violaciones.
