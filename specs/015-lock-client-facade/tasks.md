---

description: "Tasks — 015 Cliente U200 de alto nivel (fachada)"
---

# Tasks: Cliente U200 de alto nivel (fachada: login → escaneo → conexión → operación)

**Input**: Design documents from `/specs/015-lock-client-facade/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/client-api.md, contracts/esp32s3-hci-usb.md, quickstart.md

**Tests**: incluidos (la Constitución V exige tests para lógica pura y el spec exige tests de flujo con transportes simulados — SC‑004).

**Organization**: por historia de usuario; US1 (fachada) y US2 (escaneo) son P1; US3 transportes empaquetados; US4 firmware + ejemplo único.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

- [X] T001 Confirmar rama `feature/015-lock-client-facade` limpia sobre `develop` y `.venv` con `pip install -e '.[ble,bumble,dev]'` (`git status`, `pytest -q` verde de partida)
- [X] T002 [P] Crear esqueletos vacíos con docstring de módulo: `aqara_u200_ble/transport.py`, `aqara_u200_ble/client.py`, `tests/test_scanner_identify.py`, `tests/test_client_facade.py`, `tests/test_transport_contract.py`

## Phase 2: Foundational (bloqueante)

- [X] T003 Definir en `aqara_u200_ble/transport.py`: `ScanCandidate` (frozen dataclass con `address,name,rssi,service_uuids,manufacturer_data,reasons,score,raw` — `raw` excluido de `repr`/`eq`), `Transport` (Protocol: `name`, `scan`, `connect`, `disconnect`), constantes `EXPECTED_NAME="DoorLocker"`, `AQARA_COMPANY_ID=0x0B27`, `U200_SERVICE_UUIDS` (fcb9/ff60/ff90 desde `session.py`) según `data-model.md`
- [X] T004 Definir en `aqara_u200_ble/client.py`: `FlowPhase` (StrEnum LOGIN/SCAN/CONNECT/DISCOVER/OPERATION/DISCONNECT), `U200ClientError(RuntimeError)` con `phase`, `NoDeviceFoundError`, `AmbiguousDeviceError(candidates)`, `OperationResult` dataclass
- [X] T005 Exportar los nuevos símbolos en `aqara_u200_ble/__init__.py` (`U200Client`, `Transport`, `ScanCandidate`, `BleakTransport`, `BumbleTransport`, `FlowPhase`, `U200ClientError`, `NoDeviceFoundError`, `AmbiguousDeviceError`, `OperationResult`, `identify_candidate`) y actualizar `tests/test_package_api.py`

## Phase 3: US2 — Escaneo e identificación (P1) *(antes que US1 porque US1 la consume)*

**Goal**: `scan()` devuelve `ScanCandidate`s identificados por nombre/fabricante/servicios con filtro MAC y prioridad.

**Independent Test**: `tests/test_scanner_identify.py` con anuncios simulados (name‑only, manufacturer‑only, service‑only, ajeno, mac‑match).

- [X] T006 [P] [US2] Tests en `tests/test_scanner_identify.py`: `identify_candidate()` asigna `reasons`/`score` correctos para los 5 anuncios; `select_preferred()` elige name/service sobre manufacturer‑only; empate sin MAC → `AmbiguousDeviceError`; filtro `mac` deja uno; lista vacía → `NoDeviceFoundError` con mensaje que menciona el teclado
- [X] T007 [US2] Implementar en `aqara_u200_ble/scanner.py`: `identify_candidate(address, name, rssi, service_uuids, manufacturer_data, *, mac=None, raw=None) -> ScanCandidate | None` (normaliza UUIDs a minúsculas, acepta 16‑bit `fcb9` y 128‑bit), `select_preferred(candidates, *, mac=None) -> ScanCandidate` (reglas R4), y `async scan(transport, timeout=30.0, *, mac=None) -> list[ScanCandidate]` (delegando en `transport.scan`, ordenado por score/rssi). Mantener el antiguo comportamiento de impresión fuera del paquete (mover al ejemplo T020)
- [X] T008 [US2] Ejecutar `pytest tests/test_scanner_identify.py -q` y `ruff check` en verde

## Phase 4: US1 — Fachada `U200Client` (P1)

**Goal**: `await U200Client.connect(auth=…, transport=…, device_id=…)` + `lock()/unlock()/operate()`; cada fase acotada y etiquetada.

**Independent Test**: `tests/test_client_facade.py` con `FakeTransport` que devuelve el `FakeLockClient` de `tests/test_session_flow.py` y `_fake_cloud`.

- [X] T009 [P] [US1] Crear `tests/conftest.py` (o helper en `tests/test_client_facade.py`) con `FakeTransport(candidates, gatt_client)` que registra el orden de llamadas `scan/connect/disconnect`, y fixture reutilizando `FakeLockClient` + `_fake_cloud` (importar/mover a `tests/fakes.py` si hace falta sin cambiar `test_session_flow.py`)
- [X] T010 [P] [US1] Tests en `tests/test_client_facade.py`: (a) orden de fases login→scan→connect→operation en `connect()+lock()`; (b) `unlock()` y luego `lock()` sobre el mismo cliente sin nuevo scan/connect; (c) `operate("keepalive")` devuelve `OperationResult`; (d) `mac` dado → sin scan; (e) 0 candidatos → `NoDeviceFoundError(phase=SCAN)`; (f) fallo de transporte en connect → `U200ClientError(phase=CONNECT)` con `__cause__`; (g) operar tras `close()` → `U200ClientError(phase=OPERATION)`; (h) `repr(client)` no contiene password/token/session key; (i) **igualdad de bytes**: los writes registrados por el fake con `client.lock()` == los de `run_authenticated_lock_operation(..., operation="lock", auth=auth)` directo; (j) `async with` cierra y llama `transport.disconnect()`
- [X] T011 [US1] Implementar `U200Client` en `aqara_u200_ble/client.py`: `connect()` classmethod (login perezoso: `await asyncio.to_thread(auth.build_signer)` solo para validar credenciales pronto → fase LOGIN; scan/select vía `scanner`; `transport.connect` con `wait_for`; guarda `candidate`, `_gatt`), `from_gatt()`, `lock()`, `unlock()`, `operate()` (delegan en `session.run_authenticated_lock_operation(client=self._gatt, device_id, auth=self.auth, region, base_url, operation, notify_timeout)` envolviendo excepciones no‑protocolo en `U200ClientError(phase=OPERATION)` pero dejando pasar `OperationInProgressError`/`CloudServiceError`), `close()` (disconnect con `wait_for(5)`), `__aenter__/__aexit__`, `connected`, `__repr__` seguro
- [X] T012 [US1] Ejecutar `pytest tests/test_client_facade.py tests/test_session_flow.py -q`, `ruff check .`, `mypy aqara_u200_ble` en verde

## Phase 5: US3 — Transportes empaquetados (P2)

**Goal**: `BleakTransport()` y `BumbleTransport(port)` cumplen `Transport`; import perezoso con mensaje de extra.

**Independent Test**: `tests/test_transport_contract.py` con módulos `bleak`/`bumble` simulados vía `monkeypatch.setitem(sys.modules, …)`.

- [X] T013 [P] [US3] Tests en `tests/test_transport_contract.py`: (a) `BleakTransport()` sin `bleak` → `ImportError` que menciona `aqara-u200-ble[ble]`; ídem `BumbleTransport` → `[bumble]`; (b) `BleakTransport.connect` construye `BleakClient(..., services=[AUTH,CONTROL,AUX])` (fake `bleak` module que captura kwargs); (c) `BleakTransport.scan` mapea `BLEDevice/AdvertisementData` → `ScanCandidate` vía `identify_candidate` y respeta `mac`; (d) `BumbleTransport.connect` usa `ConnectionParametersPreferences(45/45/0/5000)`, no llama `pair()`, descubre servicios+características y devuelve `BumbleGattAdapter`; (e) `disconnect()` idempotente y acotado
- [X] T014 [US3] Implementar `BleakTransport` en `aqara_u200_ble/transport.py`: `scan` con `BleakScanner(detection_callback)` hasta `timeout` (o antes si `mac` casa), `connect(target)` acepta `ScanCandidate` (usa `raw` BLEDevice) o `str` (si es MAC y la plataforma no permite conectar por dirección → escaneo previo filtrando), `BleakClient(dev, timeout, services=[…])`, `disconnect` con `wait_for`
- [X] T015 [US3] Implementar `BumbleTransport(port, local_address=…)` en `aqara_u200_ble/transport.py`: `open_transport(port)`, `Device.with_hci`, `power_on`; `scan` con `device.start_scanning()`+`on('advertisement')` → `identify_candidate`; `connect(mac|candidate)` con las prefs de conexión reales, `Peer.discover_services()`+`discover_characteristics()` (timeouts), devuelve `BumbleGattAdapter(peer)`; `disconnect` cierra conexión (`wait_for 5s`) y transporte; nunca `pair()` (comentario con la evidencia de `tools/bumble_lock.py`)
- [X] T016 [US3] Ejecutar `pytest -q` completo, `ruff`, `mypy` en verde

## Phase 6: US4 — Firmware ESP32‑S3 + ejemplo único (P3)

**Goal**: `tools/esp32s3_hci_usb/` reproducible sin binarios; `examples/lock_cli.py` es el único runner real.

**Independent Test**: seguir `tools/esp32s3_hci_usb/README.md` (build/erase/flash/smoke) y `quickstart.md` §4.

- [X] T017 [P] [US4] Copiar el firmware verificado hoy a `tools/esp32s3_hci_usb/` (`CMakeLists.txt`, `sdkconfig.defaults` sin la línea `BT_LE_HCI_INTERFACE_USE_RAM` desconocida, `main/CMakeLists.txt`, `main/main.c`) y añadir `idf_env.example.sh` con rutas placeholder (`IDF_PATH`, `IDF_TOOLS_PATH`) y `.gitignore` local (`build/`, `sdkconfig`, `sdkconfig.old`)
- [X] T018 [P] [US4] Escribir `tools/esp32s3_hci_usb/README.md`: qué es (H4 sobre USB‑Serial‑JTAG, consola en UART0), requisitos (ESP‑IDF 5.3.x), `idf.py set-target esp32s3 && idf.py build`, `esptool erase_flash` + `write_flash`, smoke test HCI con Bumble (`Host.reset()` → Core 5.0/company 741), puerto en `.env` (`AQARA_ESP32_PORT=serial:/dev/cu.usbmodemNNNN,115200`), advertencias (no reconectar a la U200 en <5 s; sin bonding)
- [X] T019 [P] [US4] Añadir `tools/hci_smoke.py` (Bumble `Host.reset()` + imprime `local_version`, sin secretos) y referenciarlo en el README
- [X] T020 [US4] Crear `examples/lock_cli.py` (argparse: `--transport bleak|bumble`, `--port`, `--mac`, `--timeout`; subcomandos `scan|lock|unlock|operate <name>`; carga `.env` como hoy; usa `examples/auth_from_env.py` + `U200Client`; imprime candidatos con `reasons`, y fases/errores con `phase`; sin secretos)
- [X] T021 [US4] Retirar `tools/bumble_lock.py`, `examples/real_lock_unlock.py`, `examples/run_real_lock_unlock.py` (`git rm`) y actualizar `examples/README.md` y `tools/README.md` (tabla de runners: `lock_cli.py`, `refresh_token.py`, `hci_smoke.py`, firmware)
- [X] T022 [US4] (login+keepalive+unlock reales con bleak; scan real con bumble; `lock` por bumble pendiente del usuario) Validación real según `quickstart.md` §2–§4 con ambos transportes (requiere `AQARA_ACCOUNT/PASSWORD` en `.env`); anotar resultados (sin secretos) en `specs/015-lock-client-facade/quickstart.md` "Resultados"

## Phase 7: Polish

- [X] T023 [P] Actualizar `README.md`, `docs/README.md`, `docs/architecture.md` (Layer Map: transport/client), `docs/devices/u200/validation.md` (§3–§4 con la fachada de 3 líneas) y `.env.example` (comentario: `AQARA_TOKEN` legado; `AQARA_ESP32_PORT` para `BumbleTransport`)
- [X] T024 [P] `CHANGELOG.md`: entrada 0.3.0 (fachada, transportes, escáner con identificación, firmware ESP32‑S3, runners retirados) y bump `version` en `pyproject.toml`
- [X] T025 Pasada final: `pytest -q`, `ruff check .`, `ruff format --check .`, `mypy aqara_u200_ble`; revisar `git diff` por secretos (MACs/puertos reales/tokens) antes de commit

## Dependencies

- Phase 1 → Phase 2 → (US2 → US1) → US3 → US4 → Polish.
- US2 (T006–T008) precede a US1 porque `U200Client.connect` usa `select_preferred`.
- US3 depende de US2 (`identify_candidate`) y de la interfaz `Transport` (T003); no depende de US1.
- US4 depende de US1+US3 para el ejemplo (T020) y la validación real (T022); T017–T019 (firmware) son independientes y pueden ir en paralelo desde el principio.

## Parallel examples

- Tras T005: T006 ‖ T009/T010 ‖ T013 ‖ T017/T018/T019 (archivos distintos).
- T023 ‖ T024 tras T021.

## Implementation strategy

- **MVP** = Phase 1–4 (US2+US1): la fachada funciona con `from_gatt()` y con cualquier `Transport` (aunque el consumidor lo escriba); tests verdes sin hardware.
- Incremento 2 = US3 (transportes empaquetados) → validación real con bleak (ya verificado hoy hasta el cloud).
- Incremento 3 = US4 (firmware + ejemplo único + retirar runners) → validación real por Bumble.
