# Implementation Plan: Cliente U200 de alto nivel (fachada)

**Branch**: `feature/015-lock-client-facade` | **Date**: 2026-08-17 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/015-lock-client-facade/spec.md`

## Summary

Componer las piezas ya existentes (`CloudAuthManager` 014, `scanner`, `session.run_authenticated_lock_operation`, `BumbleGattAdapter`) en una **fachada pública** `U200Client` + una **abstracción de transporte** (`Transport` con dos implementaciones empaquetadas: `BleakTransport` nativo y `BumbleTransport` para controlador HCI externo por puerto serie). El escáner pasa a **devolver** `ScanCandidate`s identificados por nombre / fabricante / servicios anunciados. Se añade a `tools/` el firmware ESP‑IDF `esp32s3_hci_usb` (H4 sobre USB‑Serial‑JTAG) con receta, y `examples/` queda con **un** runner que usa la fachada. Ningún byte de protocolo cambia.

## Technical Context

**Language/Version**: Python ≥ 3.10 (desarrollo en 3.14 en `.venv`); firmware en C sobre ESP‑IDF 5.3.3.

**Primary Dependencies**: `cryptography` (runtime); extras opcionales `bleak>=0.22` (`.[ble]`) y `bumble>=0.0.200` (`.[bumble]`); ambos importados perezosamente dentro de su transporte.

**Storage**: N/A (nada persistido; credenciales inyectadas por el consumidor).

**Testing**: `pytest` con fakes ya existentes (`tests/test_session_flow.py::FakeLockClient`, `_fake_cloud`); tests unitarios sin radio ni red (Constitución V). Validación real vía `quickstart.md`.

**Target Platform**: macOS/Linux/Windows con Bluetooth nativo (bleak) o cualquier host con un ESP32‑S3 por USB (bumble). Home Assistant como consumidor objetivo.

**Project Type**: librería Python + herramientas (`tools/`) + ejemplos.

**Performance Goals**: flujo completo ≤ 30 s (SC‑002); operaciones sucesivas ≤ 15 s; escaneo por defecto 30 s máx.

**Constraints**: byte a byte idéntico en protocolo (Constitución II); sin secretos en logs/`repr` (I); dependencias BLE opcionales; cada fase acotada por timeout; U200 no soporta bonding (nunca `pair()`); CoreBluetooth requiere restringir servicios en el descubrimiento; la U200 rechaza reconexión inmediata (dejar ~5 s entre intentos).

**Scale/Scope**: 1 dispositivo por cliente; nuevos módulos `client.py`, `transport.py` (+`transports/` si crece), refactor de `scanner.py`; ~6 tests nuevos; 1 firmware (~150 líneas C) + README; 1 ejemplo.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Estado | Cómo se cumple |
| --- | --- | --- |
| I. Secretos | ✅ | La fachada no lee `.env`; `repr` de `U200Client`/transportes no muestra auth ni material; firmware sin credenciales; los ejemplos leen `.env` git‑ignored. |
| II. Fidelidad de protocolo | ✅ | La fachada **solo compone**: llama a `run_authenticated_lock_operation` sin tocar tramas/CRC/CCM/orden de CCCD. Test de regresión: mismos bytes escritos por el `FakeLockClient` con y sin fachada. |
| III. SDD | ✅ | spec → plan → tasks → implement en `feature/015-*`. |
| IV. Evidencia/reproducibilidad | ✅ | `quickstart.md` + `tools/esp32s3_hci_usb/README.md` permiten a un tercero reproducir desde cero (ESP32 borrado → controlador → lock). |
| V. Calidad | ✅ | API tipada, `__all__` actualizado, tests unitarios sin I/O, ruff/mypy verdes. |
| VI. Ramas | ✅ | `feature/015-lock-client-facade` off `develop`, merge `--no-ff`. |

**Gate**: PASS (sin violaciones → Complexity Tracking vacío).

## Project Structure

### Documentation (this feature)

```text
specs/015-lock-client-facade/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── client-api.md        # U200Client / Transport / scan — API pública
│   └── esp32s3-hci-usb.md   # contrato del firmware (H4 sobre USB-Serial-JTAG)
└── tasks.md                 # (/speckit-tasks)
```

### Source Code (repository root)

```text
aqara_u200_ble/
├── client.py            # NUEVO: U200Client (fachada), FlowPhase, U200ClientError
├── transport.py         # NUEVO: Transport (Protocol), ScanCandidate, BleakTransport, BumbleTransport
├── scanner.py           # REFACTOR: identify_candidate()/scan() devuelven ScanCandidate; el print pasa a examples
├── bumble_transport.py  # SIN CAMBIOS de protocolo (BumbleGattAdapter reutilizado por BumbleTransport)
├── session.py           # SIN CAMBIOS
├── auth.py              # SIN CAMBIOS
└── __init__.py          # exporta U200Client, Transport, BleakTransport, BumbleTransport, ScanCandidate, scan

tools/
├── esp32s3_hci_usb/     # NUEVO: firmware ESP-IDF (CMakeLists, sdkconfig.defaults, main/main.c, README.md, idf_env.example.sh)
├── bumble_lock.py       # RETIRADO (reemplazado por examples/lock_cli.py)
├── refresh_token.py     # se mantiene
└── README.md            # actualizado

examples/
├── auth_from_env.py     # se mantiene (construye CloudAuthManager desde .env)
├── lock_cli.py          # NUEVO: único runner real: --transport bleak|bumble, scan|lock|unlock
├── real_lock_unlock.py  # RETIRADO
└── run_real_lock_unlock.py  # RETIRADO

tests/
├── test_scanner_identify.py   # NUEVO: identificación por nombre/fabricante/servicios, filtro MAC, prioridad
├── test_client_facade.py      # NUEVO: flujo con FakeTransport (orden de fases, lock/unlock, errores por fase, repr sin secretos, byte-equality vs. llamada directa)
├── test_transport_contract.py # NUEVO: import perezoso / mensaje de extra faltante; BleakTransport restringe servicios (mock)
└── test_package_api.py        # actualizado (__all__)

docs/
├── README.md, devices/u200/validation.md, architecture.md  # fachada como vía recomendada
```

**Structure Decision**: un solo paquete (`aqara_u200_ble/`) con dos módulos nuevos; el firmware vive en `tools/` como fuente + receta (sin binarios), coherente con "runners/tools" del repo.

## Complexity Tracking

Sin violaciones de la Constitución; tabla no aplicable.
