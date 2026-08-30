# Implementation Plan: Contraseña sin conexión (códigos cloud del U200)

**Branch**: `feat/038-offline-password-cloud` | **Date**: 2026-08-30 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/038-offline-password-cloud/spec.md`

## Summary

Añadir a `aqara_ble.kdf` dos funciones de cliente cloud, siguiendo el patrón
exacto ya usado por `cloud_get_public_key`/`cloud_list_devices`/`cloud_verify`:

- `fetch_offline_passwords(device_id, auth_headers, base_url, signer=None)` —
  `GET /dev/bluetooth/lock/passwd` (relativo a `base_url`, que ya incluye
  `/app/v1.0/lumi`): devuelve los códigos de un solo uso pendientes para la
  ventana de 10 minutos actual, más esa ventana calculada localmente
  (`floor(now_ms/600000)*600000` — confirmado por evidencia, no inventado).
- `fetch_offline_password_log(device_id, start_time_ms, end_time_ms,
  auth_headers, base_url, signer=None)` — `GET
  /dev/bluetooth/lock/password/log/query` con `did`/`startTime`/`endTime`:
  devuelve el histórico de códigos ya emitidos con sus tres marcas de tiempo.

No hay algoritmo nuevo que implementar: la firma de petición
(`compute_sign`/`make_local_signer`, ya en `cloud_crypto.py`) no depende del
método HTTP ni de la ruta — solo de `appid/nonce/time/token/body/appkey` — así
que una petición GET con cuerpo vacío firma exactamente igual que las POST ya
implementadas. El único cambio de infraestructura es que `_post_json` (nombrado
para POST) necesita una variante/generalización que emita GET sin cuerpo.

## Technical Context

**Language/Version**: Python 3.11+ (según `pyproject.toml` del proyecto)

**Primary Dependencies**: solo librería estándar (`urllib.request`, `json`,
`hashlib`) — mismo patrón que el resto de `kdf.py`; ninguna dependencia nueva.

**Storage**: N/A (llamada cloud sin estado persistente local)

**Testing**: `pytest`, con un `FakeUrlopen`/monkeypatch de
`urlrequest.urlopen` (patrón ya usado en `tests/test_kdf.py` para las otras
funciones cloud) para reproducir las respuestas JSON reales capturadas esta
sesión — cero red/radio real en los tests unitarios (Constitución V).

**Target Platform**: multiplataforma (misma que el resto de `aqara_ble`)

**Project Type**: library (paquete Python `aqara_ble`)

**Performance Goals**: N/A — una llamada HTTP puntual, no hay bucle caliente.

**Constraints**: Constitución I (secret hygiene) — ningún token/sign real en
tests ni logs; Constitución II (fidelidad de protocolo) — la ruta, cabeceras y
forma de la firma deben coincidir con lo observado, sin adivinar nada no
evidenciado.

**Scale/Scope**: dos funciones nuevas + tests + una extensión pequeña de la
utilidad HTTP interna (`_post_json` → soporte GET). No toca la capa BLE en
absoluto.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Security & Secret Hygiene** — PASS. No se introduce ningún secreto real;
  los tests usan cuerpos JSON de respuesta ya sanitizados (solo el `did`
  `matt.73cb7865154223b90e81d000` del mantenedor, ya presente en
  `docs/devices/u200/operations.md` como evidencia — no es una credencial, es
  un identificador de dispositivo, igual que otros DIDs ya documentados en el
  repo).
- **II. Protocol Fidelity** — PASS con una salvedad explícita (ver Assumptions
  del spec y Fase 0): la ruta exacta y el uso de `did` (query vs. header) no
  se recuperaron byte a byte por la desincronización de la tabla HPACK a
  mitad de conexión. Se implementa la hipótesis mejor evidenciada (ver
  research.md) y la propia feature incluye el mecanismo para confirmarla
  en vivo (FR-007) antes de darla por buena — no se declara "confirmado
  byte a byte" hasta que esa verificación pase.
- **III. Spec-Driven Development** — PASS. Esta es la ejecución del flujo
  completo (`/speckit-specify` → este plan → `/speckit-tasks` →
  `/speckit-implement`).
- **IV. Evidence & Reproducibility** — PASS. Toda afirmación de esta feature
  cita la captura de esta sesión (`docs/devices/u200/operations.md`,
  sección "2026-08-30 (resolved)"); los tests fijan esas respuestas reales
  como fixtures reproducibles.
- **V. Quality & Standards** — PASS. Lógica pura (construcción de ruta,
  cálculo de ventana, extracción de campos) cubierta por tests sin I/O real;
  tipado con las mismas convenciones que el resto de `kdf.py`.
- **VI. Branch & Change Discipline** — PASS. Trabajo en `feat/038-*` (número
  de feature `038`, coherente con `specs/038-offline-password-cloud/`), sin
  commits directos a `develop`/`main`.

No hay violaciones que justificar en Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/038-offline-password-cloud/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── cloud-offline-password.md   # Public function contracts (library, not HTTP service)
└── tasks.md             # Phase 2 output (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
aqara_ble/
├── kdf.py            # + _PATH_OFFLINE_PASSWORD, _PATH_OFFLINE_PASSWORD_LOG,
│                      #   OfflinePasswordBatch / OfflinePasswordLogEntry
│                      #   (dataclasses), fetch_offline_passwords(),
│                      #   fetch_offline_password_log(), _request_json()
│                      #   generalizing _post_json for GET/POST
├── cloud_crypto.py    # sin cambios — Signer ya es agnóstico de método/ruta
└── __init__.py        # + exports de las dos funciones nuevas y los dos modelos

tests/
└── test_kdf.py        # + tests con las respuestas JSON reales capturadas
```

**Structure Decision**: todo vive en `aqara_ble/kdf.py` junto al resto del
cliente cloud (mismo módulo que `cloud_get_public_key`/`cloud_list_devices`/
`cloud_verify` — no se crea un módulo nuevo porque esta feature es del mismo
tipo exacto de llamada: cloud autenticada, sin BLE). Los tipos de retorno
(dataclasses ligeras, no dicts sueltos) van directamente en `kdf.py`, junto a
`CloudServiceError` — no en `lock_state.py` (eso es específicamente estado
derivado de BLE) ni en `models.py` (eso es decodificación de advertisement).

## Complexity Tracking

*(vacío — sin violaciones de la Constitución que justificar)*
