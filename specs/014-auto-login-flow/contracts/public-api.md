# Contract — Public API changes

Cambios de superficie pública de `aqara_u200_ble`. Criterio de verificación de la
implementación y de los tests.

## 1. `run_authenticated_lock_operation` — nuevo parámetro `auth`

```text
async def run_authenticated_lock_operation(
    *,
    client: GattClient,
    device_id: str,
    auth_headers: dict[str, str] | None,
    region: str,
    base_url: str | None,
    operation: LockOperation | str,
    notify_timeout: float = 8.0,
    signer: Any = None,          # camino legacy: token estático, sin auto-refresh
    auth: CloudAuthManager | None = None,   # NUEVO: proveedor de auth con auto-refresh
) -> tuple[SessionMaterial, LockOperationWrite, str | None]
```

- **C1.1**: MUST aceptarse **exactamente uno** de `{signer, auth}`. Ninguno o
  ambos → `ValueError` claro (antes de tocar red/radio).
- **C1.2**: Con `auth`, el flujo obtiene el token (`auth.get_token()`) y construye
  el signer internamente antes de las llamadas cloud.
- **C1.3**: Con `signer`, comportamiento idéntico al actual (sin auto-refresh) —
  retrocompatible (FR-010). La firma sigue siendo keyword-only.
- **C1.4**: Ante `CloudServiceError(code=108)` en fase cloud **pre-actuación**, el
  flujo llama `auth.handle_expired_token()`, reconstruye el signer y **re-ejecuta la
  operación una vez**. Máximo 1 reautenticación.
- **C1.5**: Ante `code=810` u otros códigos, o si el 108 ocurre tras despachar el
  actuador, **no** reautentica; propaga error claro.

## 2. `CloudServiceError` (nueva, exportada)

```text
class CloudServiceError(RuntimeError):
    code: int | str
    message: str | None
    endpoint: str
```

- **C2.1**: La lanza `_unwrap_aqara_result` cuando `code ∉ {0, "0", None}`.
- **C2.2**: MUST heredar de `RuntimeError` y conservar el texto actual del mensaje
  (retrocompat con `except RuntimeError`).
- **C2.3**: Exportada en `aqara_u200_ble.__all__`.

## 3. `CloudAuthManager` (existente, ajustes)

- **C3.1**: Construible con credenciales por argumentos (`__init__`); MUST NOT
  requerir leer ficheros/entorno.
- **C3.2**: `get_token(force_refresh=False)` y `handle_expired_token()` como
  contrato para el flujo; token cacheado en memoria.
- **C3.3**: `from_env` **eliminado del paquete** (movido a
  `examples/auth_from_env.py`).
- **C3.4**: `_login` MUST traducir `810` a error no-reintentable con mensaje que
  distinga credenciales/cuenta de token expirado; MUST NOT registrar la contraseña.

## 4. Conveniencias fuera del paquete (`examples/`)

- **C4.1**: `examples/auth_from_env.py` expone una función que construye un
  `CloudAuthManager` desde `os.environ` (dev-only). No forma parte de la API de la
  librería.
- **C4.2**: `poc_real_lock_unlock.py` y `run_real_lock_unlock.py` viven en
  `examples/`, no en la raíz ni en el paquete.

## 5. No-secretos y no-interactivo (transversal)

- **C5.1**: Ninguna ruta del flujo llama `input`/`getpass`.
- **C5.2**: Token, contraseña, credenciales y material de sesión nunca aparecen en
  logs (whitelist DEBUG de la 012), en ningún camino.
