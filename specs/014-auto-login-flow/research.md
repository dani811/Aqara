# Phase 0 — Research: decisiones de diseño

## D1 — Detección robusta de códigos (108 vs 810)

- **Decisión**: Introducir `CloudServiceError(RuntimeError)` con atributos `code`
  (int|str), `message`, `endpoint`, lanzada por `_unwrap_aqara_result` en `kdf.py`.
  El flujo ramifica sobre `err.code`, no sobre el texto.
- **Rationale**: Hoy se lanza `RuntimeError(f"... code={code} ...")` y distinguir
  `108`/`810` obligaría a parsear cadenas — frágil e i18n-dependiente. Una
  excepción tipada es testeable y explícita (Principio V).
- **Compatibilidad**: `CloudServiceError` **hereda de `RuntimeError`** y conserva
  el mismo mensaje, así que cualquier `except RuntimeError` existente sigue igual.
- **Alternativas descartadas**: parsear el mensaje (frágil); devolver códigos por
  valor de retorno (rompería la firma actual).

## D2 — Cómo entra el token en el flujo

- **Decisión**: `run_authenticated_lock_operation` acepta `auth: CloudAuthManager |
  None`. Si se pasa `auth`, el flujo obtiene el token con `auth.get_token()` y
  construye el signer internamente (con `make_local_signer`, token + user_id). Si se
  pasa `signer` explícito, se usa tal cual (sin auto-refresh). **Exactamente uno**
  de `{auth, signer}` es obligatorio; ambos o ninguno → error de argumento claro.
- **Rationale**: clarify → "proveedor de auth". Mantiene FR-010 (retrocompat con
  `signer`) y desacopla el almacenamiento de credenciales del flujo.
- **Alternativas descartadas**: credenciales sueltas en la firma (más params,
  menos cohesión); callable get_token (más carga en el consumidor).

## D3 — Estrategia de reintento (108) y guarda de idempotencia

- **Decisión**: Envolver el cuerpo de `run_authenticated_lock_operation` en un bucle
  con **como máximo 1 reautenticación**. Si una llamada cloud lanza
  `CloudServiceError` con `code == 108` **y aún no se ha despachado el comando
  actuador**, se llama a `auth.handle_expired_token()` (refresh) y se **re-ejecuta la
  operación entera** una vez. Un flag `actuated` marca el punto de no-retorno (justo
  antes del control write); si el 108 llegara después, se propaga sin reintentar.
- **Rationale**: clarify → "reautenticar la operación entera" + "solo antes de
  actuar". Las llamadas cloud (`publickey`, `verify`) son siempre pre-actuación, así
  que el 108 renovable ocurre antes del flag; la guarda es cinturón-y-tirantes
  contra dobles aperturas (FR-016).
- **Alternativas descartadas**: reintentar solo la llamada fallida (complejo por el
  estado del handshake BLE intermedio); refresco solo proactivo (no cubre
  expiración a mitad).

## D4 — 810 y otros códigos: no renovables

- **Decisión**: `code == 810` (y cualquier código ≠ 108) → **no** reautenticar;
  propagar un error claro que distinga "credenciales/cuenta" de "token expirado".
  En `CloudAuthManager._login`, un `810` se traduce a un error no-reintentable con
  mensaje explícito ("contraseña incorrecta o cuenta no registrada").
- **Rationale**: `810` es ambiguo por diseño y no se resuelve reintentando; evita
  bucles de login (FR-005).

## D5 — Seguridad asyncio del login/refresh

- **Decisión**: El login/refresh es I/O de red; se ejecuta fuera del event loop
  reutilizando el patrón de la 012 (`asyncio.to_thread` / `_run_cloud_phase`). El
  logging del refresh usa la misma whitelist DEBUG (fase/duración/tipo), sin
  secretos.
- **Rationale**: coherencia con la 012 (FR-011, FR-008).

## D6 — Purificación del paquete (utilidades fuera)

- **Decisión**:
  - Quitar `CloudAuthManager.from_env` del paquete; su carga de entorno pasa a
    `examples/auth_from_env.py` como función que construye un `CloudAuthManager`.
  - Mover `poc_real_lock_unlock.py` y `run_real_lock_unlock.py` (raíz) a `examples/`.
  - `tools/refresh_token.py` (CLI legacy) permanece en `tools/` (ya fuera del
    paquete); se mantiene como bootstrap manual/opcional.
- **Rationale**: clarify → "purificar y reubicar ahora"; el paquete `aqara_u200_ble/`
  debe contener solo librería (SC-007).
- **Nota**: los tests que hoy referencian `from_env` o los PoCs se actualizan a la
  nueva ubicación; ningún test hace I/O real.

## D7 — Credenciales de entorno (solo dev)

- **Decisión**: `.env.example` documenta `AQARA_ACCOUNT` y `AQARA_PASSWORD` (además
  de las existentes) **solo** como conveniencia para `examples/auth_from_env.py`. En
  producción (HA) las credenciales las inyecta el consumidor desde su
  almacenamiento seguro (config entry).
- **Rationale**: la librería no persiste secretos; `.env` es dev-only (FR-007/014).
