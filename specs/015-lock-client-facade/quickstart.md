# Quickstart — validar 015 (fachada) end-to-end

## Prerrequisitos
- `.venv` con `pip install -e '.[ble,bumble,dev]'`.
- `.env` (git-ignored) con `AQARA_ACCOUNT`, `AQARA_PASSWORD`, `AQARA_APPID`, `AQARA_APPKEY`, `AQARA_CLIENT_ID`, `AQARA_PHONE_ID`, `AQARA_DEVICE_ID`, opcional `AQARA_LOCK_MAC`, `AQARA_ESP32_PORT`.
- La U200 anuncia solo tras tocar el teclado.

## 1. Tests sin hardware
```bash
.venv/bin/pytest -q            # toda la suite verde; incluye test_client_facade / test_scanner_identify / test_transport_contract
.venv/bin/ruff check . && .venv/bin/mypy aqara_u200_ble
```

## 2. Escaneo (nativo)
```bash
.venv/bin/python examples/lock_cli.py --transport bleak scan
# esperado: candidato DoorLocker con reasons={name,...}; ningún dispositivo solo-fabricante marcado como preferente
```

## 3. Bloqueo con Bluetooth nativo
```bash
.venv/bin/python examples/lock_cli.py --transport bleak lock
# esperado: fases login→scan→connect→discover→operation, y "[OK] op=LOCK respuesta=..." en ≤30 s
```

## 4. ESP32‑S3 como controlador + bloqueo por Bumble
```bash
# ver tools/esp32s3_hci_usb/README.md: set-target, build, erase_flash, flash, smoke test HCI
.venv/bin/python examples/lock_cli.py --transport bumble --port serial:/dev/cu.usbmodemXXXX,115200 lock
# esperado: además MTU 247 / Read-By-Type / connection update en U200_DEBUG=1, y el cerrojo se mueve
```

## 5. Reautenticación
Con `AQARA_TOKEN` caducado o ausente el flujo debe seguir funcionando (login por cuenta); con contraseña errónea, error 810 claro sin reintentos.

## Resultados (2026-08-17)

- §1 tests: **189 passed**; `ruff check` / `mypy aqara_u200_ble` limpios.
- §2 `lock_cli.py --transport bleak scan` (macOS): la U200 sale como
  `name='DoorLocker' score=7 reasons={manufacturer,name,service} preferred=True`;
  el dispositivo ajeno `vuart:ktunnel` sale con `score=1 reasons={manufacturer}
  preferred=False` (0 falsos positivos preferentes — SC‑003).
- §4 firmware grabado en un ESP32‑S3 (chip borrado con `erase_flash`); `hci_smoke`
  → Core 5.0 / company 741; `lock_cli.py --transport bumble scan` →
  `name='DoorLocker' reasons={mac,manufacturer,name} preferred=True`.
- **Flujo limpio de primer uso (sin token), ejecutado por el usuario con las
  credenciales en línea** (`AQARA_ACCOUNT=… AQARA_PASSWORD=… lock_cli.py …`, sin
  `AQARA_TOKEN`/`AQARA_USER_ID`):
  - `login` → `[login] OK in 1.5s: token obtained (488 chars, JWT=yes), userId=yes`.
  - `operate keepalive` (bleak, macOS) → handshake completo, `response=2f002c06`,
    total 34.4 s (el escaneo agotaba los 30 s porque solo paraba al ver el nombre).
  - `unlock` (bleak) → `[OK] op=UNLOCK response=74007706 total=26.6s`. **El cerrojo
    se movió con Bluetooth nativo de macOS**, sin ESP32.
  - Ajuste posterior: el escaneo para 2 s después del primer candidato preferente
    (`SCAN_SETTLE_SECONDS`) → `scan` real en 5.9 s; el flujo completo debería quedar
    ≤ 15 s (SC‑002).
- `lock` por `bumble`: pendiente de ejecutar por el usuario (el transporte está
  verificado hasta CCCD/cloud con el firmware del ESP32‑S3).
