# Data model — 015 Cliente U200 de alto nivel

## ScanCandidate (frozen dataclass, `transport.py`)

| Campo | Tipo | Notas |
| --- | --- | --- |
| `address` | `str` | MAC (bumble/Linux) o identificador del sistema (CoreBluetooth). |
| `name` | `str \| None` | nombre anunciado (`DoorLocker` esperado). |
| `rssi` | `int \| None` | dBm. |
| `service_uuids` | `tuple[str, ...]` | UUIDs anunciados, normalizados a minúsculas. |
| `manufacturer_data` | `Mapping[int, bytes]` | company id → payload (`0x0B27` esperado). |
| `reasons` | `frozenset[str]` | subconjunto de `{"mac","name","service","manufacturer"}`. |
| `score` | `int` | mac 8 + name 4 + service 2 + manufacturer 1. |
| `raw` | `Any` | objeto del stack (p.ej. `BLEDevice`) para reconectar; excluido de `repr`. |

Reglas: `is_preferred = "name" in reasons or "service" in reasons or "mac" in reasons`. Orden natural por `score` desc, `rssi` desc.

## Transport (Protocol, `transport.py`)

- `async scan(timeout: float, *, mac: str | None) -> list[ScanCandidate]`
- `async connect(target: ScanCandidate | str, *, timeout: float) -> GattClient` — incluye descubrimiento de servicios/características; devuelve un `GattClient` (protocolo de `gatt.py`).
- `async disconnect() -> None` — idempotente, acotado en tiempo.
- `name: str` — `"bleak"` / `"bumble"` (para errores/logs).

Implementaciones: `BleakTransport()`; `BumbleTransport(port: str, *, local_address="F0:F1:F2:F3:F4:F5")`.

## FlowPhase (StrEnum, `client.py`)

`LOGIN`, `SCAN`, `CONNECT`, `DISCOVER`, `OPERATION`, `DISCONNECT`.

## U200ClientError(RuntimeError) / AmbiguousDeviceError / NoDeviceFoundError

- `phase: FlowPhase`, `message`; `__cause__` = excepción original. `AmbiguousDeviceError.candidates: list[ScanCandidate]`.

## U200Client (`client.py`)

Estado: `auth: CloudAuthManager`, `transport: Transport`, `device_id`, `region`, `candidate: ScanCandidate | None`, `_gatt: GattClient | None`, timeouts. Transiciones: `connect()` (login perezoso → scan/opcional → connect → discover) → **connected** → `lock()/unlock()/operate()` (N veces) → `close()` → **closed** (operar en closed → `U200ClientError(phase=OPERATION)`).

`repr`: `U200Client(device_id=…, transport=…, connected=…)` — nunca auth/token/material.

## OperationResult (dataclass)

`operation: LockOperation`, `response_hex: str | None`, `session: SessionMaterial` (para diagnóstico; su `repr` ya no muestra claves — verificar) → la fachada devuelve `response_hex` en `lock()/unlock()` y `OperationResult` en `operate()`.
