# Contract — API pública de la fachada (aqara_u200_ble)

```python
from aqara_u200_ble import CloudAuthManager, U200Client, BleakTransport, BumbleTransport, scan

auth = CloudAuthManager(
    account=..., password=..., appid=..., appkey=..., client_id=..., phone_id=..., region="EU"
)

# 1) sin conocer la MAC (identificación por anuncio):
async with await U200Client.connect(
    auth=auth, transport=BleakTransport(), device_id="lumi1.xxxx"
) as lock:
    await lock.lock()  # -> str | None (respuesta hex de la cerradura)
    await lock.unlock()
    await lock.operate("keepalive")  # -> OperationResult (cualquier LockOperation por nombre/valor)

# 2) controlador externo + MAC conocida:
lock = await U200Client.connect(
    auth=auth,
    transport=BumbleTransport("serial:/dev/cu.usbmodemNNNN,115200"),
    device_id="lumi1.xxxx",
    mac="AA:BB:CC:DD:EE:FF",
)
await lock.lock()
await lock.close()

# 3) solo escanear:
candidates = await scan(
    BleakTransport(), timeout=20
)  # list[ScanCandidate], ordenados por score/rssi
```

## Firmas

- `U200Client.connect(*, auth, transport, device_id, mac=None, region="EU", base_url=None, scan_timeout=30.0, connect_timeout=20.0, notify_timeout=10.0) -> U200Client`
  - `mac` dado → `transport.connect(mac)` directo (sin escaneo) salvo que el transporte no soporte conectar por dirección (bleak/macOS) → escanea filtrando por `mac`.
  - sin `mac` → `scan`; 0 candidatos → `NoDeviceFoundError(phase=SCAN)`; >1 preferentes empatados → `AmbiguousDeviceError`; ninguno preferente (solo fabricante) → `NoDeviceFoundError` con los vistos.
- `U200Client.from_gatt(*, auth, gatt_client, device_id, region="EU", ...)` — para tests / consumidores con cliente ya conectado (Home Assistant).
- `lock() / unlock() -> str | None`; `operate(op: LockOperation | str) -> OperationResult`.
- `close()`; `__aenter__/__aexit__`; `connected: bool`; `candidate`.
- Excepciones: `U200ClientError(phase)`, `NoDeviceFoundError`, `AmbiguousDeviceError`, y se propagan sin envolver `OperationInProgressError` y `CloudServiceError` (810) tal como hoy.
- Dependencia opcional ausente → `ImportError("Instala aqara-u200-ble[ble]")` / `[bumble]` al construir el transporte.

## Invariantes

- La fachada no imprime ni loguea secretos; `repr` seguro.
- Bytes escritos en el GATT por `lock()` == bytes escritos por `run_authenticated_lock_operation(..., operation="lock")` con el mismo fake (test de igualdad).
- Cada fase acotada por `asyncio.wait_for`; `close()` nunca cuelga (timeout 5 s en disconnect).
