# Implementation Plan: Read-only status query probe

**Branch**: `feature/021-status-query` | **Date**: 2026-08-17 | **Spec**: [spec.md](spec.md)

## Summary

`operation` en la sesión solo se usa para construir el write. Hago que
`build_lock_operation_write` **acepte y devuelva** un `LockOperationWrite` ya
construido → puedo pasar una trama de consulta genérica por el flujo existente sin
tocar el path de actuación. Añado `build_control_query_write(sub_cmd, data)`,
`U200Client.query()`, y `aqara query <nombre>` acotado a una lista blanca de
opcodes de estado/batería. `LockState(source="query")`. Igualdad de bytes en
lock/unlock.

## Technical Context

**Language**: Python ≥3.10, stdlib. **Testing**: pytest (fake responde a la
consulta; igualdad de bytes del actuador). **Constraints**: Constitución II
(actuador intacto — la única extensión es un passthrough opt-in), I (sin
secretos), V (tipado, tests). Seguridad física: CLI solo lista blanca de consulta,
nunca `SET_*`. **Scope**: `lock_ops.py` (passthrough + `build_control_query_write`
+ tipo de `LockOperationWrite.operation`), `client.py` (`query`), `cli.py`
(`query` + whitelist), `lock_state` source, docs, ~7 tests.

## Constitution Check

| Principio | Estado | Cómo |
| --- | --- | --- |
| I Secretos | ✅ | Consulta no expone secretos; respuesta es estado, no material. |
| II Protocolo | ✅ | El actuador no cambia (passthrough opt-in; test de igualdad de bytes). |
| III SDD | ✅ | spec→plan→tasks→implement. |
| IV Evidencia | ✅ | Opcodes citados del catálogo (feature 010); marcados NO confirmados. |
| V Calidad | ✅ | Tipado, tests, ruff/mypy. |
| VI Ramas | ✅ | rama propia, merge `--no-ff`. |

**Gate**: PASS. Riesgo físico mitigado: CLI acotada a consulta read-only.

## Project Structure

```text
aqara_ble/lock_ops.py    # build_lock_operation_write passthrough; build_control_query_write(); operation: LockOperation|str
aqara_ble/client.py      # U200Client.query(sub_cmd, data) -> LockState(source="query")
aqara_ble/lock_state.py  # SOURCE_QUERY
aqara_ble/cli.py         # `aqara query <name|hex>` acotado (whitelist STATUS_QUERIES)
tests/test_status_query.py    # query bytes; passthrough; actuador byte-equal; CLI whitelist
docs/devices/u200/operations.md / validation.md  # opcodes permitidos + procedimiento
```

**Structure Decision**: passthrough de `LockOperationWrite` = cambio mínimo y
opt-in; la superficie peligrosa (SET_*) se contiene en la CLI por lista blanca.

## Complexity Tracking

Sin violaciones. Límite: si ningún opcode reporta posición, hace falta la vía de
eventos (sesión persistente), no cubierta aquí.
