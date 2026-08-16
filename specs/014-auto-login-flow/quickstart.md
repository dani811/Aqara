# Quickstart — Validación de la feature 014

Cómo comprobar que el encaje del login cumple la spec. Comandos desde la raíz del
repo. Los tests no hacen I/O real (cloud simulado, `FakeLockClient`).

## Gates automáticos

```bash
ruff check aqara_u200_ble tests examples
ruff format --check aqara_u200_ble tests examples
mypy aqara_u200_ble
pytest -q
```

**Esperado**: los cuatro en verde.

## Escenarios de test (FR-012)

| # | Escenario | SC |
| --- | --- | --- |
| a | Solo credenciales (sin token) → `auth.get_token()` hace login → la operación completa el flujo | SC-001 |
| b | El cloud responde `108` en fase cloud → reautentica (`handle_expired_token`) + re-ejecuta la operación una vez → éxito | SC-002 |
| c | Credenciales inválidas → `CloudServiceError(code=810)` → falla **sin** login-retry, mensaje que nombra la causa | SC-003 |
| d | Con logging DEBUG, ningún secreto (token, password, sessionKey, nonce, verifyData) aparece en `caplog` — en éxito y en fallo | SC-004 |
| e | Camino con `signer` explícito (sin `auth`) sigue funcionando | SC-005 |
| f | `108` **después** de despachar el actuador → **no** reintenta (cero doble apertura) | SC-008 |
| g | `auth` y `signer` ambos, o ninguno → `ValueError` claro antes de tocar red/radio | C1.1 |

## Gate de pureza del paquete (SC-007)

```bash
# El paquete no debe cargar credenciales, pedir input, ni exponer CLI
# (los flags de runtime U200_DEBUG / U200_INSECURE_TLS sí están permitidos):
grep -rInE 'getpass|input\(|def from_env|if __name__ == "__main__"' aqara_u200_ble/ \
  && echo "FAIL: utilidad/interactividad en el paquete" \
  || echo "OK: paquete sin utilidades/interactividad"
# Las conveniencias viven fuera:
test -f examples/auth_from_env.py && echo "OK auth_from_env en examples"
test ! -f poc_real_lock_unlock.py && echo "OK PoC fuera de la raíz"
```

## Gate de no-interactividad (SC-006)

```bash
grep -rInE 'input\(|getpass' aqara_u200_ble/ && echo "FAIL: interactividad en el paquete" || echo "OK: no interactivo"
```

## Comprobación manual (estilo Home Assistant)

```python
from aqara_u200_ble import CloudAuthManager, run_authenticated_lock_operation

# El consumidor (HA) inyecta credenciales desde su almacenamiento seguro:
auth = CloudAuthManager(
    account=..., password=..., appid=..., appkey=...,
    client_id=..., phone_id=..., region="EU",
)
# ... conectar el transporte (client) ...
# await run_authenticated_lock_operation(
#     client=client, device_id=..., auth_headers=None, region="EU",
#     base_url=None, operation="keepalive", auth=auth,   # sin token manual
# )
```

**Esperado**: la primera operación hace login sola; si el token caduca entre
operaciones, la siguiente se reautentica y se re-ejecuta una vez sin intervención.
