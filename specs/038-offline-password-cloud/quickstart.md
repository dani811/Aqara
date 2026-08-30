# Quickstart: contraseña sin conexión (códigos cloud)

## 1. Ejecutar los tests (sin red, sin lock)

```bash
.venv/bin/python -m pytest tests/test_kdf.py -k offline_password -q
```

Esperado: verde. Los tests fijan las respuestas JSON reales capturadas esta
sesión como fixtures — cero red real.

## 2. Pedir los códigos pendientes (con hardware/cuenta reales)

```python
from aqara_ble.kdf import fetch_offline_passwords, make_local_signer, REGION_BASE_URLS

signer = make_local_signer(
    appid=...,      # de .env
    appkey=...,
    token=...,
    user_id=...,
    client_id=...,
    phone_id=...,
)
batch = fetch_offline_passwords(
    device_id="matt.<...>",   # el DID de tu cerradura
    auth_headers=None,
    base_url=REGION_BASE_URLS["EU"],
    signer=signer,
)
print(batch.codes)             # p.ej. ('651399', '637408')
print(batch.window_start_ms, batch.window_end_ms)
```

## 3. Verificar en vivo que la petición coincide con la app (User Story 3)

```bash
U200_DEBUG=1 .venv/bin/python -c "..."   # el script del paso 2
```

En paralelo, captura el tráfico real de la app con las herramientas ya en
`tools/` (`tools/sslfull.js` + `tools/decode_h2.py`, ver
`docs/reverse-engineering.md`), abre "Contraseña sin conexión" en la app, y
compara la petición que imprime `U200_DEBUG` (método, ruta, cabeceras no
sensibles) contra la decodificada de la captura. Si difieren en algún
parámetro (p. ej. si `did` va como query en vez de solo por sesión), ajusta
`fetch_offline_passwords()` — la interfaz pública no debería necesitar
cambiar, solo cómo construye la URL/cabeceras internamente.

## 4. Consultar el histórico

```python
from aqara_ble.kdf import fetch_offline_password_log
import time

now_ms = int(time.time() * 1000)
entries = fetch_offline_password_log(
    device_id="matt.<...>",
    start_time_ms=now_ms - 3_600_000,  # última hora
    end_time_ms=now_ms,
    auth_headers=None,
    base_url=REGION_BASE_URLS["EU"],
    signer=signer,
)
for e in entries:
    print(e.create_time_ms, e.start_time_ms, e.end_time_ms, e.device_id)
```

> Ninguna de las dos llamadas abre una conexión BLE — son puramente cloud,
> coherente con lo que la propia función significa ("sin conexión" al hub/
> Bluetooth, no sin conexión a internet).
