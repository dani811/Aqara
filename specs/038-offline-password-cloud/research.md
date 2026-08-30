# Phase 0 Research: Contraseña sin conexión (códigos cloud del U200)

Todas las incógnitas de esta feature se resolvieron leyendo el código
existente de `aqara_ble/kdf.py` + `cloud_crypto.py` y la captura de tráfico de
esta sesión (`docs/devices/u200/operations.md`). No hubo que investigar nada
externo al repo — se documenta aquí para que `/speckit-tasks` no tenga que
re-derivarlo.

## Decisión 1: ¿la ruta va con `base_url` existente o hace falta uno nuevo?

**Decision**: reutilizar `REGION_BASE_URLS` tal cual (`https://rpc-ger.aqara.com
/app/v1.0/lumi` para EU) y añadir la ruta relativa `/dev/bluetooth/lock/passwd`.

**Rationale**: la ruta completa observada en la captura fue
`GET /app/v1.0/lumi/dev/bluetooth/lock/passwd`. `REGION_BASE_URLS["EU"]` ya
vale `"https://rpc-ger.aqara.com/app/v1.0/lumi"` — coincide exactamente con el
prefijo, igual que `_PATH_PUBLICKEY = "/dev/bluetooth/login/assure/publickey"`
ya sigue el mismo patrón (`.../lumi` + `/dev/bluetooth/...`).

**Alternatives considered**: un `base_url` nuevo específico para este
endpoint — descartado, el host y el prefijo son idénticos a los ya usados, no
hay ninguna evidencia de un host distinto.

## Decisión 2: ¿hace falta un algoritmo de firma nuevo para una petición GET?

**Decision**: no. Reutilizar `make_local_signer`/`compute_sign` sin cambios.

**Rationale**: `compute_sign` (en `cloud_crypto.py`) firma
`Appid={appid}&Nonce={nonce}&Time={time}&Token={token}&{body}&{appkey}` — no
incluye el método HTTP ni la ruta en absoluto. Para una petición GET sin
cuerpo, `body=""` es un valor perfectamente válido de entrada a esa misma
fórmula. La captura de esta sesión decodificó campos de cabecera coherentes
con este esquema (un valor tipo timestamp en millis, dos valores tipo
hex/nonce) en la petición real — no se pudo mapear cada nombre de cabecera al
100% por la tabla HPACK desincronizada, pero nada contradice que sea el mismo
esquema ya implementado.

**Alternatives considered**: firmar sobre `method + path` (esquemas
HMAC-sobre-URL habituales en otras nubes) — descartado, `compute_sign`'s
fórmula ya confirmada (contra 3 firmas reales, comentario en
`cloud_crypto.py`) no incluye esos campos; inventar una variante nueva sin
evidencia violaría la Constitución II.

## Decisión 3: ¿cómo emitir un GET con la infraestructura HTTP actual?

**Decision**: generalizar `_post_json` en un `_request_json(method, url,
payload, ...)` interno; `_post_json` pasa a ser un wrapper de compatibilidad
(`method="POST"`) para no tocar ninguna llamada existente. Para `method="GET"`
con `payload={}`, `data=None` (no se manda `Content-Length`/cuerpo en la
petición real).

**Rationale**: toda la lógica de manejo de respuesta (gzip, x-aes128gcm,
`CloudServiceError` vía `_unwrap_aqara_result`, el log de depuración
`U200_DEBUG`) ya es correcta e idéntica para ambos métodos — solo cambia cómo
se construye el `urlrequest.Request` (verbo + presencia de cuerpo).

**Alternatives considered**: una función `_get_json` totalmente separada,
duplicando el manejo de respuesta — descartado, viola DRY sin necesidad; el
propio código ya factoriza correctamente todo lo que no depende del verbo.

## Decisión 4: ¿de dónde sale la "ventana de validez" de cada código?

**Decision**: `fetch_offline_passwords()` calcula la ventana actual
localmente como `start = (now_ms // 600_000) * 600_000`, `end = start +
600_000`, y la devuelve junto a la lista de códigos — documentado
explícitamente como **valor derivado, no proveniente de esta respuesta
concreta del servidor**, distinto de `fetch_offline_password_log()` (que sí
devuelve `createTime`/`startTime`/`endTime` tal cual el servidor los da, por
código ya emitido).

**Rationale**: la respuesta real capturada de `GET .../lock/passwd` es
`{"result":{"passwd":[...]},"code":0,...}` — **no** incluye ventana por
código. La ventana de 10 minutos SÍ está confirmada por evidencia
independiente (el endpoint de histórico, en 3 muestras, con `startTime`/
`endTime` exactos múltiplos de 600000ms). Devolver la ventana calculada es
útil (es lo que el usuario final ve como "Caduca" en la app, menos el margen
de +10min que la propia app añade solo a la UI) y no es una invención: es una
regla confirmada, solo que no viene en ESTE payload concreto — de ahí la
distinción explícita en el modelo de datos entre "campo del servidor" y
"campo derivado y documentado como tal", que es lo que pide el spec (FR-003)
al decir "sin inventar ni derivar campos que el servidor no proporcione" para
los campos que si vienen del servidor, sin prohibir un campo adicional
derivado y etiquetado como tal.

**Alternatives considered**: no exponer ninguna ventana desde
`fetch_offline_passwords()`, obligando a llamar también a
`fetch_offline_password_log()` para tener la ventana — descartado por
peor ergonomía (dos llamadas de red para un dato determinista y ya
confirmado), pero SÍ se expone `fetch_offline_password_log()` por separado
para quien quiera la ventana confirmada servidor-a-servidor de códigos ya
usados/emitidos.

## Decisión 5: verificación en vivo de la ruta exacta (User Story 3 / FR-007)

**Decision**: extender el mecanismo de depuración YA EXISTENTE
(`U200_DEBUG` en `_post_json`/`_request_json`, que ya imprime `f"[U200] {url}
-> {result}"` en la respuesta) para que también imprima la petición saliente
(método, URL completa, cabeceras no sensibles) antes de enviarla — no se crea
un mecanismo de depuración nuevo y paralelo.

**Rationale**: consistencia (Constitución V); el hook ya existe y ya es el
lugar correcto; solo había que añadir la línea de log de la petición, que
faltaba (hoy solo loguea la respuesta).

**Alternatives considered**: un parámetro `debug=True` por función —
descartado, rompería el patrón de un único interruptor de entorno ya usado en
todo el módulo.

## Resumen de incógnitas NEEDS CLARIFICATION

Ninguna. Las 5 decisiones anteriores cubren todo lo marcado como incierto en
el Technical Context del plan; no queda ningún `NEEDS CLARIFICATION` sin
resolver.
