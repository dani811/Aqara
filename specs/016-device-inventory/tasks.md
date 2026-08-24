# Tasks: Identificación de dispositivos + captura del inventario cloud

## Phase 1: US1 — Identificación por el aire (P1)

- [X] T001 [US1] `aqara_ble/models.py`: `MODEL_BY_PRODUCT_ID={0x9C03:"U200"}`, `decode_manufacturer_payload(payload)->(product_id|None, model|None)` (u16 LE offset 2; product_id sin bytes → None; model no catalogado → None) + docstring con la evidencia.
- [X] T002 [US1] `tests/test_device_identity.py`: payload real `2808039c51...`→(0x9C03,"U200"); payload corto→(None,None); product_id desconocido→(id,None).
- [X] T003 [US1] `transport.py`: `ScanCandidate` gana `manufacturer_payload: bytes`, `product_id: int|None`, `model: str|None` (fuera de eq/repr sensible); `identify_candidate` los rellena desde `manufacturer_data[0x0B27]` vía `decode_manufacturer_payload`. Sin tocar reasons/score.
- [X] T004 [US1] Export en `__init__.py` (`decode_manufacturer_payload`, `MODEL_BY_PRODUCT_ID`) + `test_package_api`; tests de candidato ampliado en `test_scanner_identify.py`/`test_device_identity.py`.
- [X] T005 [US1] `examples/lock_cli.py`: `show()` incluye `model=`; ruff/mypy/pytest verdes.

## Phase 2: US2 — Captura del inventario cloud (P2)

- [X] T006 [US2] `tools/probe_cloud_endpoints.py`: lee credenciales del entorno (falla claro si faltan), construye el firmante con `CloudAuthManager`, prueba una lista de rutas candidatas de inventario **solo lectura** (p.ej. `/app/dev/query/detail`, `/dev/lock/query`, `/app/position/query/room/list`, más candidatas de lista), imprime método/código/forma, y vuelca la respuesta a `captures/` (git-ignored) con did/mac/token **redactados**. Sin mutaciones.
- [X] T007 [US2] `docs/reference/cloud-login.md` + `docs/reference/ble-transport.md`: registrar `product_id` U200 (`0x9C03`) y los endpoints cloud observados + estado "inventario pendiente de captura"; `tools/README.md` lista la sonda.

## Phase 3: Polish

- [X] T008 CHANGELOG 0.4.0 (identificación de modelo por el aire + sonda de inventario); `pytest`/`ruff`/`mypy`; `git diff` sin secretos (payloads/dids/mac reales).

## Dependencies
US1 (T001→T005) independiente y shippable. US2 (T006–T007) independiente. Polish al final.

## MVP
US1: reconocer el modelo por el aire, sin credenciales ni conexión.
