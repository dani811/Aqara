# Tasks: Read-only status query probe

## Phase 1: Envío de consulta (US1/US2)

- [X] T001 `lock_ops.py`: `LockOperationWrite.operation: LockOperation | str`; `build_lock_operation_write` devuelve el argumento tal cual si ya es `LockOperationWrite` (passthrough); nuevo `build_control_query_write(sub_cmd: int, data: bytes=b"") -> LockOperationWrite` (payload=`build_control_frame`, prefix 0x01, operation=`f"query:0x{sub_cmd:02x}"`).
- [X] T002 `lock_state.py`: añadir `SOURCE_QUERY="query"`.
- [X] T003 `client.py`: `async query(sub_cmd: int, data: bytes=b"") -> LockState` → construye el write y llama `run_authenticated_lock_operation(operation=<write>, ...)`; envuelve la respuesta con `decode_lock_state(source=SOURCE_QUERY)`.
- [X] T004 `tests/test_status_query.py`: (a) `build_control_query_write(0x07)` payload==b"\x07", prefix 0x01; (b) passthrough de `build_lock_operation_write`; (c) **igualdad de bytes** del actuador lock/unlock vs antes (fake); (d) `query()` escribe `build_control_frame` y devuelve LockState(source="query", raw==respuesta fake); sin respuesta → responded=False.

## Phase 2: CLI acotada + docs

- [X] T005 `cli.py`: `STATUS_QUERIES = {"lock_status":0x07,"tongue_status":0x08,"door_lock_status":0xE5,"report_lock_status":0x15,"battery":0x4F,"lithium_battery":0x78}`; subcomando `query <name>` (o `--hex XX` opcional acotado a esos valores); rechaza cualquier otro con mensaje (solo consulta/batería, nunca SET_*); imprime la respuesta; test de dispatch + rechazo en `test_cli.py`.
- [X] T006 Docs: `operations.md` (opcodes de consulta permitidos, marcados NO confirmados; objetivo: hallar el byte de posición); `validation.md` (procedimiento: `aqara query lock_status` en cerrada vs abierta). CHANGELOG 0.7.0; bump versión.

## Phase 3: Verify
- [X] T007 `pytest`/`ruff`/`mypy` verdes; merge `--no-ff`; (sondeo real lo corre el usuario).

## Dependencies
US1 (T001–T004) antes de CLI/docs.

## MVP
`U200Client.query()` + `aqara query lock_status` envían un opcode de estado read-only y muestran la respuesta; actuador intacto.
