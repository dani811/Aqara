# Implementation Plan: Encaje del login autónomo en el flujo (auto-login + auto-refresh)

**Branch**: `feature/014-auto-login-flow` | **Date**: 2026-08-15 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/014-auto-login-flow/spec.md`

## Summary

Enchufar el login autónomo en el flujo de operación. `run_authenticated_lock_operation`
aceptará un **proveedor de auth** (`CloudAuthManager`, construido por el consumidor
con sus credenciales) del que obtiene el token y al que pide renovación. Cuando una
llamada cloud falle por token expirado (`code 108`) **antes de actuar**, se
reautentica y se **re-ejecuta la operación entera una vez**; ante credenciales
inválidas (`code 810`) u otros códigos, falla sin reintentar. El token vive **solo
en memoria**; la librería no persiste secretos. Además se **purifica el paquete**:
`from_env` y los scripts CLI/PoC salen de `aqara_ble/` a `examples/`.

Para distinguir códigos de forma robusta (hoy se lanza `RuntimeError` con `code=`
en el texto) se introduce una excepción tipada `CloudServiceError` con `.code`.

## Technical Context

**Language/Version**: Python 3.11+ (igual que el paquete actual).

**Primary Dependencies**: Ninguna nueva. Reutiliza `kdf.login`,
`CloudAuthManager` (auth.py), `make_local_signer`, y el patrón async de la 012
(`_run_cloud_phase` / `asyncio.to_thread`). Sin `requests` (urllib).

**Storage**: Ninguno. Token **solo en memoria** (en el `CloudAuthManager`);
credenciales inyectadas por el consumidor; nada se persiste (Principio I).

**Testing**: pytest, sin I/O de red ni radio — cloud simulado (monkeypatch de
`cloud_get_public_key`/`get_session_material`/`login`) y `FakeLockClient`. Gates:
`ruff`, `ruff format`, `mypy --strict`, `pytest`.

**Target Platform**: Librería Python; consumidor de referencia = integración Home
Assistant (headless, no interactivo).

**Project Type**: Single project (librería `aqara_ble/`).

**Constraints**: no interactivo (sin `input`/`getpass` en el flujo); sin secretos
en logs (whitelist de la 012); reintento máximo 1 y **solo antes de actuar**;
retrocompatibilidad del camino con `signer` explícito.

**Scale/Scope**: Cambios acotados a `kdf.py`, `auth.py`, `session.py`,
`__init__.py` + tests + `examples/` + `.env.example`. No incluye multi-dispositivo.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Aplicación | Estado |
| --- | --- | --- |
| I. Seguridad e higiene de secretos (NO NEGOCIABLE) | La librería no persiste credenciales ni token (token en memoria; credenciales inyectadas). Se retira `from_env` del paquete. Sin secretos en logs. `.env.example` solo placeholders (dev). | ✅ PASS |
| II. Fidelidad de protocolo | No se toca la criptografía de login ni el wire; solo se añade una excepción tipada sobre el `code=` ya existente y el cableado del token. | ✅ PASS |
| III. Spec-Driven | specify → clarify → plan → tasks → implement. | ✅ PASS |
| IV. Evidencia y reproducibilidad | Los códigos `108`/`810` provienen de la RE (documentados en `kdf.py`); los tests reproducen el comportamiento con cloud simulado. | ✅ PASS |
| V. Calidad y estándares | API tipada; tests de lógica pura sin red/radio; ruff+mypy limpios. | ✅ PASS |
| VI. Disciplina de ramas | `feature/014-auto-login-flow`, merge `--no-ff`. | ✅ PASS |

**Resultado**: sin violaciones. Complexity Tracking vacío.

## Project Structure

### Documentation (this feature)

```text
specs/014-auto-login-flow/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── public-api.md
└── tasks.md   # /speckit-tasks
```

### Source changes (repository)

```text
aqara_ble/
├── kdf.py         # + CloudServiceError(code, message, endpoint); raise it in _unwrap_aqara_result
├── auth.py        # CloudAuthManager pure (credentials in __init__); remove from_env;
│                  #   distinguish 810 (non-retryable) in _login; keep get_token/handle_expired_token
├── session.py     # run_authenticated_lock_operation: add `auth` param; derive signer from token;
│                  #   on CloudServiceError code 108 pre-actuation -> reauth + re-run once (guarded)
└── __init__.py    # export CloudServiceError; keep CloudAuthManager; no from_env in package

examples/          # dev-only conveniences OUT of the package (purity)
├── auth_from_env.py        # build a CloudAuthManager from os.environ (was CloudAuthManager.from_env)
├── real_lock_unlock.py     # moved from repo-root poc_real_lock_unlock.py
└── run_real_lock_unlock.py # moved from repo root

tests/
└── test_auto_login_flow.py # scenarios (a)-(f); mocks only, no network/radio

.env.example       # add AQARA_ACCOUNT / AQARA_PASSWORD (dev-only, documented as such)
tools/refresh_token.py       # legacy CLI stays in tools/ (already outside the package)
```

**Structure Decision**: cambios acotados al paquete existente + una nueva carpeta
`examples/` para las conveniencias que hoy ensucian el paquete o la raíz. El
`CloudAuthManager` permanece en la librería (es el proveedor de auth del contrato),
pero **pierde `from_env`** — esa carga de entorno pasa a `examples/auth_from_env.py`.
El detalle de la API pública nueva vive en [contracts/public-api.md](contracts/public-api.md).

## Complexity Tracking

> Sin violaciones de la Constitución. No aplica.
