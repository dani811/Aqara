# Phase 1 — Data Model

## Entidades

### CloudAuthManager (existente, se mantiene en la librería)
- **Rol**: proveedor de auth; guarda credenciales, obtiene/renueva el token.
- **Estado**: `account`, `password`, `appid`, `appkey`, `client_id`, `phone_id`,
  `region`, `district` (credenciales, inmutables tras construcción); `_token`,
  `_user_id` (token en **memoria**, mutable).
- **Operaciones (contrato usado por el flujo)**:
  - `get_token(*, force_refresh=False) -> str` — token válido; hace login si no hay
    o si `force_refresh`.
  - `handle_expired_token() -> str` — fuerza refresh (login) y devuelve token nuevo.
  - `user_id` disponible tras login (para el signer).
- **Cambios**: se **elimina** `from_env` (pasa a `examples/`). `_login` traduce
  `810` a error no-reintentable claro.
- **Invariantes**: nunca persiste a disco; nunca registra secretos.

### CloudServiceError (nueva, en kdf.py)
- **Rol**: error tipado de respuesta de servicio del cloud.
- **Atributos**: `code: int | str`, `message: str | None`, `endpoint: str`.
- **Relación**: subclase de `RuntimeError` (retrocompat). La lanza
  `_unwrap_aqara_result` cuando `code ∉ {0,"0",None}`.
- **Semántica de códigos**: `108` = token expirado (renovable); `810` = credencial
  incorrecta/cuenta no registrada (no renovable); otros = fallo no renovable.

### Token (valor, en memoria)
- JWT de sesión; vida corta; se invalida al iniciar sesión en otro sitio.
- Ciclo: *ausente* → (login) → *válido en memoria* → (108) → (refresh) → *válido*.
- Nunca se escribe a disco por la librería.

### Signer (función)
- `signer(path_rel, body_str) -> headers`. Construido desde el token vigente
  (`make_local_signer`). Tras un refresh, el flujo **reconstruye** el signer con el
  token nuevo antes de re-ejecutar.

## Máquina de estados del flujo (retry)

```text
                 ┌─────────────────────────────────────────────┐
 start ─▶ ensure token (auth.get_token) ─▶ cloud+BLE phases ─▶ actuate ─▶ done
                 │                              │  (pre-actuación)   │
                 │                    CloudServiceError 108?         │ (flag actuated=True)
                 │                              │ yes & !actuated     │
                 │                              ▼                     │
                 │                    handle_expired_token()          │
                 │                    rebuild signer                  │
                 │                    re-run once (attempts<=1) ──────┘
                 │
                 └─ 810 / otros / attempts agotados ─▶ raise (sin bucle)
```

## Enumeración

- **RetryOutcome**: `ok` | `reauth_then_ok` | `failed_non_retryable` |
  `failed_after_reauth`.

## Reglas

1. Exactamente uno de `{auth, signer}` en `run_authenticated_lock_operation`.
2. Máximo **1** reautenticación por operación.
3. Reautenticar **solo** si el `108` ocurre con `actuated == False`.
4. `810` y códigos ≠ 108 → no reautenticar; error claro.
5. Token y credenciales nunca en logs ni en disco.
