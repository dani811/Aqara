# Implementation Plan: Capturar ff64/ff92

**Branch**: `feature/022-report-channels` | **Date**: 2026-08-17 | **Spec**: [spec.md](spec.md)

## Summary
Reemplazar `on_notify_ignored` (pass) por handlers por-canal que llaman a un helper
`_debug_report(channel, data)` que imprime bajo `U200_DEBUG`. Diagnóstico puro; el
actuador no cambia.

## Constitution Check
| Principio | Estado |
| --- | --- |
| I Secretos | ✅ frames de estado, no material |
| II Protocolo | ✅ canales ya suscritos; solo se registran |
| III SDD | ✅ |
| V Calidad | ✅ test del helper |
| VI Ramas | ✅ rama propia, `--no-ff` |

## Project Structure
```text
aqara_ble/session.py   # _debug_report() + on_report_notify(channel)
tests/test_session_flow.py  # test del helper (stderr bajo U200_DEBUG)
```
