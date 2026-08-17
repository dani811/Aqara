# Research — 015 Cliente U200 de alto nivel

Todo lo de abajo está verificado en vivo el 2026-08-17 (macOS 24.6, `.venv` Python 3.14, bleak actual, bumble 0.0.233, ESP32‑S3 rev 0.2 en `/dev/cu.usbmodemNNNN`).

## R1. Forma de la fachada

- **Decision**: `U200Client` con constructor async `await U200Client.connect(*, auth, transport, device_id, mac=None, region="EU", scan_timeout=30, connect_timeout=20, discovery_timeout=15, notify_timeout=10)`; métodos `lock()`, `unlock()`, `operate(op)`, `close()`; soporte `async with`. Cada operación delega en `session.run_authenticated_lock_operation(client=gatt, device_id, auth=auth, operation=…)` — que ya hace preámbulo, handshake, reautenticación 108 (una vez, antes de actuar) y control cifrado.
- **Rationale**: 014 ya resolvió login/refresh dentro de la sesión; la fachada no debe duplicar esa lógica ni tocar el protocolo (Constitución II). Cada operación repite el handshake completo sobre la misma conexión — es lo que hacen hoy los runners (unlock → lock en la misma conexión) y funciona.
- **Alternatives**: mantener sesión AES‑CCM entre operaciones (evitaría re‑handshake) → requiere refactorizar `session.py`; fuera de alcance, no altera bytes pero sí la secuencia observada. Se anota como mejora futura.

## R2. Abstracción de transporte

- **Decision**: `Transport` (Protocol) con `scan(timeout, mac) -> list[ScanCandidate]`, `connect(candidate|mac, timeout) -> GattClient` (incluye descubrimiento de servicios/características) y `disconnect()`. Dos implementaciones: `BleakTransport()` y `BumbleTransport(port)`.
- **Rationale**: escanear/conectar/descubrir es distinto por stack (bleak conecta por objeto `BLEDevice`; bumble por MAC + `Peer.discover_*`); el resto del flujo consume el `GattClient` ya definido en `gatt.py`.
- **Alternatives**: pasar un cliente ya conectado (como hoy) → sigue exigiendo cableado manual; se mantiene posible (`U200Client.from_gatt(client, ...)`) para tests y consumidores avanzados.

## R3. bleak en macOS/CoreBluetooth

- **Hallazgo**: `BleakClient(dev)` falla en `_get_services` con `CBErrorDomain Code=8 "The specified UUID is not allowed for this operation"` al descubrir descriptores de una característica ajena. **Con `services=[AUTH_SERVICE_UUID, CONTROL_SERVICE_UUID, AUX_SERVICE_UUID]` conecta y el flujo llega a los CCCD y al cloud.** Verificado hoy.
- **Decision**: `BleakTransport.connect` pasa siempre esa lista de servicios; MTU/Read‑By‑Type/conn‑update se omiten (best‑effort ya soportado por la sesión).
- **Nota**: en macOS `device.address` es un UUID de CoreBluetooth, no la MAC → el filtro por MAC no aplica; identificar por anuncio (R4).

## R4. Identificación en el escaneo

- **Hallazgo**: filtrar solo por fabricante `0x0B27` produjo un falso positivo hoy (`vuart:ktunnel`, RSSI −56). El nombre `DoorLocker` es fiable; los servicios anunciados (si vienen) `fcb9`/`ff60`/`ff90` también.
- **Decision**: `ScanCandidate(address, name, rssi, service_uuids, manufacturer_data, reasons: set[str], score)`; motivos `name`, `service`, `manufacturer`, `mac`. Score: mac(8) + name(4) + service(2) + manufacturer(1). Candidato preferente = score máximo con `name` o `service` presentes; solo‑fabricante nunca se elige automáticamente. Empate sin MAC → `AmbiguousDeviceError` con la lista.
- **Rationale**: FR‑003/FR‑005/SC‑003.

## R5. Bumble sobre ESP32‑S3

- **Hallazgo**: no había firmware en el repo; el ESP32 llevaba otro proyecto (`madoka-eso32`) y solo expone el USB‑Serial‑JTAG nativo (VID 303a / PID 1001). Los ejemplos ESP‑IDF `controller_hci_uart_*` sacan HCI por UART (pines), no por USB.
- **Decision**: firmware propio `esp32s3_hci_usb`: controlador BLE Espressif en modo *controller‑only* + VHCI, puenteado con framing H4 sobre `usb_serial_jtag` (driver de IDF, sin componentes externos). Consola en UART0 para que USB solo lleve HCI. Bumble lo abre con `serial:/dev/cu.usbmodemXXXX,115200` (baud ignorado en USB). Verificado: `HCI Reset` + `Read Local Version` → Core 5.0, company 741; flujo real hasta CCCD/cloud con Read‑By‑Type, MTU 247, LE features y connection update.
- **Rationale**: única ruta que expone los primitivos de bajo nivel; reproducible con el ESP‑IDF 5.3.3 que ya tiene el usuario (receta en `idf_env.example.sh`).
- **Alternatives**: TinyUSB CDC (necesita `esp_tinyusb` gestionado y descarga); Zephyr `hci_usb` (clase USB Bluetooth → transporte `usb:`; soporte S3 incierto). Descartadas por complejidad.
- **Cuidado**: la U200 corta la conexión si se reconecta inmediatamente ("DISCONNECTION COMPLETE: unknown handle" durante discovery); esperar ~5 s entre intentos. `connection.disconnect()` de Bumble puede colgar → siempre `wait_for` (ya lo hace el runner actual; el transporte lo hereda).

## R6. Estado del token

- **Hallazgo**: `AQARA_TOKEN` en `.env` está caducado (`code 108`); `.env` no tiene `AQARA_ACCOUNT/AQARA_PASSWORD`. Con `CloudAuthManager` (014) la fachada hace login sola y no depende de ese token.
- **Decision**: el ejemplo único usa `examples/auth_from_env.py` (cuenta+contraseña); `AQARA_TOKEN` queda como legado en `.env.example`.

## R7. Concurrencia y timeouts

- **Decision**: reutilizar `OperationInProgressError` (por `device_id`) para dos operaciones concurrentes; cada fase con `asyncio.wait_for` y error `U200ClientError(phase=…)` que envuelve la causa (`__cause__`) sin secretos.
