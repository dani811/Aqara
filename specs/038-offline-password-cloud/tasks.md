---

description: "Task list for the offline-password cloud fetch feature"
---

# Tasks: Contraseña sin conexión (códigos cloud del U200)

**Input**: Design documents from `specs/038-offline-password-cloud/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/,
quickstart.md — all present.

**Tests**: incluidos. Constitución V exige tests para toda lógica pura sin
I/O real, y esta feature es justo eso (construcción de ruta/petición,
cálculo de ventana, parseo de respuesta) — no es opcional en este proyecto.

**Organization**: por historia de usuario del spec (US1 = pedir códigos
pendientes, US2 = histórico, US3 = verificación en vivo).

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

- [ ] T001 Leer `aqara_ble/kdf.py` completo (ya hecho durante research.md,
  reconfirmar antes de tocar) para no romper `_post_json`'s call sites
  existentes al generalizarlo.

---

## Phase 2: Foundational (bloqueante para US1 y US2)

**Purpose**: la infraestructura HTTP compartida (GET genérico) que ambas
historias necesitan.

**⚠️ CRITICAL**: nada de US1/US2 puede implementarse antes de esto.

- [ ] T002 En `aqara_ble/kdf.py`, generalizar `_post_json` en un
  `_request_json(method, url, payload, auth_headers=None, timeout=10,
  signer=None, path_rel=None, encrypt_appkey=None)` interno: mismo cuerpo
  actual, pero `urlrequest.Request(url, data=data, headers=...,
  method=method)`, con `data=None` cuando `method="GET"` y `payload` está
  vacío (no serializar `{}` como cuerpo en un GET). `_post_json` pasa a ser
  `def _post_json(...): return _request_json("POST", ...)` — ninguna
  llamada existente cambia de comportamiento.
- [ ] T003 [P] En `aqara_ble/kdf.py`, extender el log de depuración
  `U200_DEBUG` (hoy solo imprime la respuesta) para que `_request_json`
  también imprima, ANTES de enviar, `f"[U200] {method} {url}"` y las
  cabeceras no sensibles (todo excepto `Sign`/`Token`, que se imprimen como
  `<redacted>`) — esto es la base de FR-007/US3, pero se hace aquí porque
  vive en el mismo helper que T002.
- [ ] T004 [P] En `aqara_ble/kdf.py`, añadir las constantes
  `_PATH_OFFLINE_PASSWORD = "/dev/bluetooth/lock/passwd"` y
  `_PATH_OFFLINE_PASSWORD_LOG = "/dev/bluetooth/lock/password/log/query"`
  junto a las demás `_PATH_*`.
- [ ] T005 [P] En `aqara_ble/kdf.py`, añadir las dataclasses
  `OfflinePasswordBatch` (`codes: tuple[str, ...]`, `window_start_ms: int`,
  `window_end_ms: int`) y `OfflinePasswordLogEntry` (`create_time_ms: int`,
  `start_time_ms: int`, `end_time_ms: int`, `device_id: str`), `frozen=True`,
  junto a `CloudServiceError` — ver data-model.md para los docstrings de
  cada campo (marcar explícitamente cuáles son derivados vs. del servidor).

**Checkpoint**: `_request_json` soporta GET con logging de depuración; los
tipos de retorno existen. US1 y US2 pueden implementarse en paralelo.

---

## Phase 3: User Story 1 - Obtener un código de un solo uso sin BLE (Priority: P1) 🎯 MVP

**Goal**: `fetch_offline_passwords()` devuelve los códigos pendientes de la
cerradura sin ninguna conexión BLE.

**Independent Test**: con `_request_json` monkeypatcheado para devolver el
JSON real capturado, `fetch_offline_passwords()` devuelve
`OfflinePasswordBatch(codes=("651399","637408",...), ...)` y ninguna función
de transporte BLE se importa/llama en el camino.

### Tests for User Story 1

- [ ] T006 [P] [US1] En `tests/test_kdf.py`, test
  `test_fetch_offline_passwords_parses_the_real_response`: monkeypatchea
  `kdf._request_json` para devolver
  `{"result":{"passwd":["651399","637408"]},"code":0,"requestId":"...",
  "message":"Success","msgDetails":"Success"}` (JSON real de
  `docs/devices/u200/operations.md`) y comprueba
  `batch.codes == ("651399", "637408")`.
- [ ] T007 [P] [US1] En `tests/test_kdf.py`, test
  `test_fetch_offline_passwords_calls_the_get_endpoint`: monkeypatchea
  `kdf._request_json` para capturar sus argumentos y comprueba que se llamó
  con `method="GET"` y `url` terminando en `_PATH_OFFLINE_PASSWORD`
  (`{base_url}/dev/bluetooth/lock/passwd`), sin cuerpo (`payload={}`).
- [ ] T008 [P] [US1] En `tests/test_kdf.py`, test
  `test_fetch_offline_passwords_window_is_a_10_minute_grid`: con `time.time`
  fijado (monkeypatch), comprueba `window_start_ms`/`window_end_ms` son
  múltiplos exactos de 600000 y `window_end_ms - window_start_ms == 600000`.
- [ ] T009 [P] [US1] En `tests/test_kdf.py`, test
  `test_fetch_offline_passwords_empty_list_is_not_an_error`: respuesta
  `{"result":{"passwd":[]},"code":0,...}` → `batch.codes == ()`, sin
  excepción.
- [ ] T010 [P] [US1] En `tests/test_kdf.py`, test
  `test_fetch_offline_passwords_propagates_cloud_service_error`: respuesta
  `{"code":108,"message":"...",...}` → `pytest.raises(CloudServiceError)`
  (reutiliza `_unwrap_aqara_result`, ya probado en otro sitio — este test
  solo confirma que `fetch_offline_passwords` no lo atrapa/oculta).

### Implementation for User Story 1

- [ ] T011 [US1] En `aqara_ble/kdf.py`, implementar
  `fetch_offline_passwords(device_id, auth_headers, base_url, signer=None)
  -> OfflinePasswordBatch`: llama `_request_json("GET",
  f"{base_url}{_PATH_OFFLINE_PASSWORD}", {}, auth_headers, signer=signer,
  path_rel=_PATH_OFFLINE_PASSWORD)`, desenvuelve con
  `_unwrap_aqara_result(data, endpoint=_PATH_OFFLINE_PASSWORD)`, lee
  `result.get("passwd", [])` como `codes`, calcula
  `window_start_ms = (now_ms // 600_000) * 600_000` /
  `window_end_ms = window_start_ms + 600_000` (con `now_ms` inyectable para
  tests vía un parámetro `_now_ms: Callable[[], int] | None = None` interno,
  por defecto `lambda: int(time.time() * 1000)`), construye y devuelve
  `OfflinePasswordBatch`. `device_id` no se usa todavía en la URL/cabeceras
  hasta T023 (US3) confirme dónde va — documentarlo con un comentario
  `# TODO(US3): confirmar si did va en query/cabecera` en vez de adivinar.
- [ ] T012 [US1] En `aqara_ble/__init__.py`, exportar
  `fetch_offline_passwords` y `OfflinePasswordBatch`.

**Checkpoint**: US1 funciona y está probada de forma independiente — MVP
alcanzado.

---

## Phase 4: User Story 2 - Consultar el historial de códigos ya emitidos (Priority: P2)

**Goal**: `fetch_offline_password_log()` devuelve el histórico con sus tres
marcas de tiempo.

**Independent Test**: con `_request_json` monkeypatcheado para devolver el
JSON real de histórico, `fetch_offline_password_log()` devuelve las
entradas con `create_time_ms`/`start_time_ms`/`end_time_ms`/`device_id`
correctos, sin depender de que US1 se haya llamado antes.

### Tests for User Story 2

- [ ] T013 [P] [US2] En `tests/test_kdf.py`, test
  `test_fetch_offline_password_log_parses_the_real_response`: monkeypatchea
  `kdf._request_json` para devolver
  `{"result":[{"createTime":"1788123833807","startTime":"1788123600000",
  "endTime":"1788124200000","did":"matt.73cb7865154223b90e81d000"}],
  "code":0,...}` (JSON real capturado) y comprueba los 4 campos de la
  entrada devuelta.
- [ ] T014 [P] [US2] En `tests/test_kdf.py`, test
  `test_fetch_offline_password_log_builds_the_query_string`: comprueba que
  la URL pasada a `_request_json` incluye
  `did=<device_id>&startTime=<start_time_ms>&endTime=<end_time_ms>` (estos
  tres SÍ están confirmados en query string por la captura de esta sesión,
  a diferencia de US1 — ver contracts/cloud-offline-password.md).
- [ ] T015 [P] [US2] En `tests/test_kdf.py`, test
  `test_fetch_offline_password_log_drops_incomplete_entries`: una entrada
  del array de respuesta sin `createTime` se descarta sin lanzar excepción
  y sin afectar a las demás entradas válidas.

### Implementation for User Story 2

- [ ] T016 [US2] En `aqara_ble/kdf.py`, implementar
  `fetch_offline_password_log(device_id, start_time_ms, end_time_ms,
  auth_headers, base_url, signer=None) -> tuple[OfflinePasswordLogEntry,
  ...]`: construye la query string con `urllib.parse.urlencode`, llama
  `_request_json("GET", f"{base_url}{_PATH_OFFLINE_PASSWORD_LOG}?{qs}", {},
  ...)`, desenvuelve con `_unwrap_aqara_result`, itera `result` (una lista,
  no un dict — ojo, `_unwrap_aqara_result` devuelve el payload completo si
  `result` no es un dict, así que aquí hay que leer `data.get("result")`
  directamente en vez de asumir el desenvuelto genérico), construye una
  `OfflinePasswordLogEntry` por elemento completo y descarta los
  incompletos.
- [ ] T017 [US2] En `aqara_ble/__init__.py`, exportar
  `fetch_offline_password_log` y `OfflinePasswordLogEntry`.

**Checkpoint**: US1 y US2 funcionan de forma independiente entre sí.

---

## Phase 5: User Story 3 - Verificar en vivo la petición exacta (Priority: P3)

**Goal**: confirmar contra hardware real que la petición de US1 coincide con
la de la app, y corregir `fetch_offline_passwords` si no.

**Independent Test**: con `U200_DEBUG=1` y una cuenta/cerradura reales, la
petición logueada coincide (ruta, método, cabeceras no sensibles) con una
captura simultánea de `tools/sslfull.js` + `tools/decode_h2.py`.

### Implementation for User Story 3

- [ ] T018 [US3] Ejecutar el paso 3 de `quickstart.md` contra el hardware
  del mantenedor: lanzar `fetch_offline_passwords()` con `U200_DEBUG=1` a la
  vez que se captura el tráfico real de la app abriendo "Contraseña sin
  conexión" (herramientas ya en `tools/`). Esto es una tarea de
  **verificación manual**, no de código — requiere el móvil y la cuenta del
  mantenedor, no se puede automatizar en CI.
- [ ] T019 [US3] Según el resultado de T018: si la petición coincide,
  eliminar el comentario `# TODO(US3)` de T011 y anotar en
  `docs/devices/u200/operations.md` que la ruta quedó confirmada byte a
  byte. Si NO coincide (p. ej. `did` debía ir en query o en una cabecera
  concreta), ajustar `fetch_offline_passwords` en `aqara_ble/kdf.py` para
  que coincida, sin cambiar su firma pública, y añadir un test (variante de
  T007) que fije el comportamiento correcto.

**Checkpoint**: la implementación de US1 queda confirmada byte a byte contra
hardware real, o corregida y vuelta a confirmar.

---

## Phase 6: Polish

- [ ] T020 [P] Ejecutar `pytest -q` completo (no solo `test_kdf.py`) y
  confirmar que sigue en el mismo estado que antes de esta feature (255/258
  o mejor — los 3 fallos preexistentes documentados esta sesión no son de
  esta feature).
- [ ] T021 [P] Actualizar `docs/devices/u200/operations.md` (sección
  "2026-08-30 (resolved)") con un enlace a las funciones nuevas
  (`fetch_offline_passwords`/`fetch_offline_password_log`) y el resultado de
  T018/T019.
- [ ] T022 Actualizar `CHANGELOG.md` con la nueva funcionalidad (feature
  038) siguiendo el formato ya usado por las entradas anteriores.

---

## Dependencies & Execution Order

- **Setup (T001)**: sin dependencias.
- **Foundational (T002-T005)**: depende de T001; BLOQUEA todo lo demás.
- **US1 (T006-T012)**: depende de Foundational. Independiente de US2/US3.
- **US2 (T013-T017)**: depende de Foundational. Independiente de US1/US3.
- **US3 (T018-T019)**: depende de que US1 exista (verifica su petición);
  requiere hardware real, no puede correr en CI.
- **Polish (T020-T022)**: depende de que US1 (mínimo) esté completa.

### Parallel Opportunities

- T003, T004, T005 son `[P]` entre sí (archivos/símbolos distintos dentro
  del mismo fichero, sin dependencia entre ellos — aplicar con cuidado si se
  hacen en el mismo PR, pero son conceptualmente independientes).
- Todos los tests de US1 (T006-T010) son `[P]` entre sí.
- Todos los tests de US2 (T013-T015) son `[P]` entre sí.
- US1 completa (T006-T012) y US2 completa (T013-T017) pueden hacerse en
  paralelo una vez termina Foundational.

## Implementation Strategy

### MVP First

1. Setup (T001) → Foundational (T002-T005) → US1 (T006-T012).
2. **STOP y VALIDAR**: `pytest tests/test_kdf.py -k offline_password -q` en
   verde, sin red real.
3. Esto ya es el MVP: pedir códigos pendientes funciona y está probado.

### Incremental

1. MVP (arriba).
2. Añadir US2 (histórico) → validar independientemente.
3. Añadir US3 (verificación en vivo, requiere el móvil/cuenta del
   mantenedor) → corregir si hace falta.
4. Polish.
