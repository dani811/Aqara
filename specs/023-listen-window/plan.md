# Implementation Plan: Ventana de escucha post-comando

**Branch**: `feature/023-listen-window` | **Date**: 2026-08-17 | **Spec**: [spec.md](spec.md)

## Summary
Añadir `listen_after`/`on_report` (aditivo, default off) a
`run_authenticated_lock_operation`: report_queue para ff64/ff92; tras la primera
respuesta, drenar control_queue (ff62, descifrar) y report_queue hasta expirar,
reenviando por `on_report`. `U200Client.listen()` + `aqara listen`. Actuador
byte-idéntico (default 0.0).

## Constitution Check
| Principio | Estado |
| --- | --- |
| I Secretos | ✅ frames de estado, no material |
| II Protocolo | ✅ aditivo opt-in; default byte-idéntico (test de igualdad) |
| III SDD | ✅ |
| V Calidad | ✅ tests del reenvío + igualdad |
| VI Ramas | ✅ rama propia, --no-ff |

## Project Structure
```text
aqara_ble/session.py   # listen_after/on_report + report_queue + listen loop
aqara_ble/client.py    # U200Client.listen()
aqara_ble/cli.py       # aqara listen --seconds
tests/test_listen_window.py # reenvío + default off + sin callback
```
