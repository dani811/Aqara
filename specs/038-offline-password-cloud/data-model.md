# Data Model: Contraseña sin conexión (códigos cloud del U200)

Dos dataclasses nuevas en `aqara_ble/kdf.py`, junto al resto del cliente
cloud. Ninguna toca la capa BLE/framing (Constitución II: cambio aditivo,
sin tocar bytes de protocolo existentes).

## `OfflinePasswordBatch`

Resultado de `fetch_offline_passwords()` — el lote de códigos pendientes de
la ventana actual de 10 minutos.

| Campo | Tipo | Origen | Notas |
| --- | --- | --- | --- |
| `codes` | `tuple[str, ...]` | Servidor (`result.passwd`) | Cada elemento es el código de 6 dígitos tal cual lo da el servidor (string, puede tener ceros a la izquierda — **nunca** convertir a `int`). |
| `window_start_ms` | `int` | **Derivado**, no del servidor | `(now_ms // 600_000) * 600_000`. Documentado como derivado en el docstring del campo y de la función. |
| `window_end_ms` | `int` | **Derivado**, no del servidor | `window_start_ms + 600_000`. |

Validación: `codes` puede ser una tupla vacía (no hay códigos pendientes —
NO es un error, ver spec Edge Cases). Si el servidor devuelve `code != 0`,
no se construye un `OfflinePasswordBatch`: se lanza `CloudServiceError`
(reutilizando la ya existente) antes de llegar a construir el resultado.

## `OfflinePasswordLogEntry`

Un elemento de `fetch_offline_password_log()` — un código ya emitido/en
histórico, tal como lo devuelve el servidor, sin ningún campo derivado.

| Campo | Tipo | Origen | Notas |
| --- | --- | --- | --- |
| `create_time_ms` | `int` | Servidor (`createTime`, string) | Convertido a `int` (el servidor lo manda como string decimal). |
| `start_time_ms` | `int` | Servidor (`startTime`, string) | Igual. |
| `end_time_ms` | `int` | Servidor (`endTime`, string) | Igual. |
| `device_id` | `str` | Servidor (`did`) | El DID del dispositivo, `matt.<hex>`. |

Validación: si falta cualquiera de los cuatro campos en una entrada de la
respuesta, esa entrada se descarta (no se inventa un `0`/`""`) y se cuenta
en un aviso opcional de depuración — nunca debe fallar toda la llamada por
una entrada individual incompleta.

## Sin cambios de estado

Ninguna de las dos dataclasses es mutable ni persiste nada localmente — son
una instantánea de lo que el servidor respondió en el momento de la llamada,
igual que el resto de tipos de retorno del cliente cloud (`cloudPublicKey`,
`sessionKey`, etc. son también instantáneas, no estado gestionado por la
librería).
