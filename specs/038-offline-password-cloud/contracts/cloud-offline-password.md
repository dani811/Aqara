# Contract: `aqara_ble.kdf` — offline-password cloud calls

Esto es una librería, no un servicio HTTP propio — el "contrato" es la firma
pública Python de las dos funciones nuevas, más la forma exacta del wire
HTTP que replican (evidencia, no diseño propio).

## `fetch_offline_passwords`

```python
def fetch_offline_passwords(
    device_id: str,
    auth_headers: Mapping[str, str] | None,
    base_url: str,
    signer: Signer | None = None,
) -> OfflinePasswordBatch: ...
```

**Wire HTTP replicado** (evidencia: `docs/devices/u200/operations.md`,
2026-08-30):

```text
GET {base_url}/dev/bluetooth/lock/passwd
Headers: mismas de build_cloud_auth_headers()/make_local_signer()
Body: (vacío)
```

**Respuesta esperada** (forma real capturada):

```json
{"result":{"passwd":["651399","637408","..."]},"code":0,"requestId":"...","message":"Success","msgDetails":"Success"}
```

**Comportamiento**:
- `code == 0` → `OfflinePasswordBatch(codes=tuple(result["passwd"]), window_start_ms=.., window_end_ms=..)`.
- `code != 0` → `CloudServiceError` (vía `_unwrap_aqara_result`, sin cambios).
- `result.passwd` ausente o vacío → `codes=()` (lista vacía, NO es un error).
- Nunca abre ninguna conexión BLE/GATT.

## `fetch_offline_password_log`

```python
def fetch_offline_password_log(
    device_id: str,
    start_time_ms: int,
    end_time_ms: int,
    auth_headers: Mapping[str, str] | None,
    base_url: str,
    signer: Signer | None = None,
) -> tuple[OfflinePasswordLogEntry, ...]: ...
```

**Wire HTTP replicado**:

```text
GET {base_url}/dev/bluetooth/lock/password/log/query?did={device_id}&startTime={start_time_ms}&endTime={end_time_ms}
```

(el `did`/`startTime`/`endTime` en query string está confirmado por la
captura de esta sesión para ESTE endpoint de histórico — a diferencia del
endpoint `passwd`, cuyos parámetros exactos aún no se recuperaron byte a
byte, ver User Story 3 del spec).

**Respuesta esperada** (forma real capturada):

```json
{"result":[{"createTime":"1788123833807","startTime":"1788123600000","endTime":"1788124200000","did":"matt.73cb7865154223b90e81d000"}],"code":0,"requestId":"...","message":"Success","msgDetails":"Success"}
```

**Comportamiento**:
- `code == 0` → tupla de `OfflinePasswordLogEntry`, una por elemento de
  `result` que tenga los 4 campos requeridos (los que no los tengan se
  descartan, no rompen la llamada — ver data-model.md).
- `code != 0` → `CloudServiceError`.
- Nunca abre ninguna conexión BLE/GATT.

## Modo de depuración (User Story 3 / FR-007)

Con `U200_DEBUG` en el entorno (mecanismo ya existente, extendido por esta
feature — ver research.md Decisión 5), ambas llamadas imprimen a stderr,
**antes** de enviar la petición:

```text
[U200] GET https://rpc-ger.aqara.com/app/v1.0/lumi/dev/bluetooth/lock/passwd
[U200]   headers: {Lang: ..., Cuty: ..., ..., Sign: <redacted>, Token: <redacted>}
```

`Sign` y `Token` MUST aparecer redactados incluso en este modo (Constitución
I) — el resto de cabeceras (método, ruta, `Time`, `Nonce`, `Appid`, etc.) se
imprimen tal cual para poder compararlas con una captura simultánea de la
app real.
