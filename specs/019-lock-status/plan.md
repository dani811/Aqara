# Implementation Plan: Lectura de estado (LockState)

**Branch**: `feature/019-lock-status` | **Date**: 2026-08-17 | **Spec**: [spec.md](spec.md)

## Summary

Nuevo `aqara_ble/lock_state.py` con `LockState` + `decode_lock_state()`
(honesto: `raw` siempre, campos confirmados sólo con evidencia). `U200Client`
gana `status()` (keepalive confirmado, read-only) y `OperationResult`/operaciones
pueden exponer `LockState(source="operation")`. CLI `aqara state`. Sin cambios de
protocolo.

## Technical Context

**Language**: Python ≥3.10, stdlib. **Deps**: ninguna. **Testing**: pytest con
`FakeLockClient` (respuesta de keepalive guionizada) y muestras reales para el
decoder. **Constraints**: Constitución II (solo lectura sobre la respuesta ya
descifrada; keepalive es el único comando enviado, confirmado), I (sin secretos),
V (tipado, tests sin I/O). **Scope**: `lock_state.py` nuevo, `client.py`
(`status()` + exponer LockState), `cli.py` (`state`), `__init__` export, docs,
~6 tests.

## Constitution Check

| Principio | Estado | Cómo |
| --- | --- | --- |
| I Secretos | ✅ | `LockState` no lleva material sensible; `raw` es estado de puerta, no secreto. |
| II Protocolo | ✅ | Solo keepalive (confirmado) + descifrado existente; sin tramas nuevas. |
| III SDD | ✅ | spec→plan→tasks→implement. |
| IV Evidencia | ✅ | Decodifica sólo lo confirmado; muestras reales citadas; captura documentada. |
| V Calidad | ✅ | Tipado, tests, ruff/mypy. |
| VI Ramas | ✅ | rama propia, merge `--no-ff`. |

**Gate**: PASS.

## Project Structure

```text
aqara_ble/lock_state.py   # NUEVO: LockState + decode_lock_state()
aqara_ble/client.py       # status() (keepalive) + LockState desde operaciones
aqara_ble/cli.py          # subcomando `state`
aqara_ble/__init__.py     # export LockState, decode_lock_state
tests/test_lock_state.py       # decode honesto + status() con fake
docs/devices/u200/operations.md / validation.md  # muestras + captura; límite eventos
```

**Structure Decision**: el decodificador vive en un módulo puro y ampliable;
`status()` reutiliza el keepalive confirmado — cero riesgo físico.

## Complexity Tracking

Sin violaciones. Límite conocido declarado: eventos espontáneos requieren sesión
persistente (feature futura), no se abordan aquí.
