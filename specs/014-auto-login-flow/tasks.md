---

description: "Task list for feature 014 — Encaje del login autónomo en el flujo"
---

# Tasks: Encaje del login autónomo en el flujo (auto-login + auto-refresh)

**Input**: Design documents from `/specs/014-auto-login-flow/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/public-api.md](contracts/public-api.md), [quickstart.md](quickstart.md)

**Tests**: SÍ (FR-012 los exige). Sin I/O real: cloud simulado (monkeypatch de
`login`/`cloud_get_public_key`/`get_session_material`) y `FakeLockClient`.

**Organization**: por user story; cada una es un incremento verificable.

## Format: `[ID] [P?] [Story] Description`

## Restricciones transversales

- Token **solo en memoria**; la librería **no persiste** credenciales ni token.
- Sin secretos en logs (whitelist DEBUG de la 012). Sin `input`/`getpass` en el flujo.
- Retrocompat: el camino con `signer` explícito sigue funcionando.

---

## Phase 1: Setup

- [X] T001 Create `examples/` directory with a short `examples/README.md` (dev-only conveniences, not part of the library API)

---

## Phase 2: Foundational (blocking prerequisites)

- [X] T002 Add `CloudServiceError(RuntimeError)` with `code`/`message`/`endpoint` in `aqara_u200_ble/kdf.py`; raise it from `_unwrap_aqara_result` when `code ∉ {0,"0",None}` (keep the current message text) and export it in `aqara_u200_ble/__init__.py` `__all__` (contract C2)
- [X] T003 Unit test in `tests/test_auto_login_flow.py`: `_unwrap_aqara_result` raises `CloudServiceError` with the right `code` for 108 and 810, and remains an `except RuntimeError` (C2.2)

**Checkpoint**: typed error available for 108/810 branching.

---

## Phase 3: User Story 1 — Operar solo con credenciales (Priority: P1) 🎯 MVP

**Goal**: A partir de un `CloudAuthManager` inyectado (sin token manual), una
operación completa el flujo obteniendo el token por sí misma.

**Independent Test**: con solo `auth` (credenciales, sin `signer`), cloud simulado
y `FakeLockClient`, la operación completa el flujo (hubo login).

- [X] T004 [US1] Add `auth: CloudAuthManager | None = None` to `run_authenticated_lock_operation` in `aqara_u200_ble/session.py`; enforce **exactly-one-of** `{auth, signer}` with a clear `ValueError` **before** any network/radio; when `auth` is given, obtain the token off-loop (`auth.get_token()` via the 012 async pattern) and build the signer with `make_local_signer(token, user_id)` (contract C1.1–C1.3)
- [X] T005 [P] [US1] Test in `tests/test_auto_login_flow.py`: only `auth` (no token/signer) → login happens and the operation completes; a second operation reuses the cached token (SC-001)
- [X] T006 [P] [US1] Test: passing both `{auth, signer}` or neither → `ValueError` before any I/O (C1.1)
- [X] T006b [P] [US1] Test: the **explicit `signer` path** (no `auth`) still completes the operation with a mocked cloud + `FakeLockClient` — backward compatibility verified, not only relied on via regression (SC-005, FR-010)

**Checkpoint**: MVP — operar sin gestionar tokens.

---

## Phase 4: User Story 2 — Renovación transparente en 108 (Priority: P1)

**Goal**: Si el token expira en fase cloud (antes de actuar), reautenticar y
re-ejecutar la operación una vez; nunca reintentar tras actuar.

**Independent Test**: cloud responde 108 y luego OK → la operación tiene éxito tras
exactamente una reautenticación + re-ejecución.

- [X] T007 [US2] In `aqara_u200_ble/session.py`, wrap the operation body in a **≤1 reauth** loop: on `CloudServiceError(code=108)` while `actuated == False`, call `auth.handle_expired_token()`, rebuild the signer, and re-run the operation once; set the `actuated` flag immediately before the control write; on 108 after actuation, do **not** reauth (contracts C1.4, FR-016)
- [X] T008 [US2] Test: cloud raises 108 on the first cloud call then succeeds → exactly one reauth + re-run → success (SC-002)
- [X] T009 [US2] Test (idempotency): 108 signalled after the actuator was dispatched → **no** retry, no double actuation (SC-008)
- [X] T010 [US2] Test: reauth then the cloud still rejects → clear error, no login loop (US2 scenario 2, FR-004)
- [X] T010b [US2] Test: token fetch/refresh via the `auth` path runs **off the event loop** (does not block) — a slow login does not stall concurrent tasks, mirroring the 012 heartbeat test (FR-011)

**Checkpoint**: el caso que hoy falla, resuelto y acotado.

---

## Phase 5: User Story 3 — Fallo claro sin bucles (810) (Priority: P2)

**Goal**: Credenciales incorrectas/cuenta no registrada (810) → fallo inmediato,
sin reintentar login, con mensaje que nombra la causa.

**Independent Test**: cloud 810 → falla con cero login-retries y mensaje claro.

- [X] T011 [US3] In `aqara_u200_ble/auth.py` `_login`, translate `CloudServiceError(code=810)` into a clear **non-retryable** error distinguishing "credenciales/cuenta" from "token expirado"; ensure the flow reauths **only** on code 108 (FR-005)
- [X] T012 [US3] Test: cloud returns 810 → operation fails with **zero** login-retries and the error names the cause (SC-003)

**Checkpoint**: sin bucles de login.

---

## Phase 6: User Story 4 — No interactivo, seguro y paquete puro (Priority: P2)

**Goal**: La librería no persiste secretos, no es interactiva, no filtra secretos
en logs, y el paquete no contiene utilidades.

**Independent Test**: logs DEBUG sin secretos; el paquete sin `from_env`/CLI/PoC;
sin `input`/`getpass`.

- [X] T013 [P] [US4] Remove `CloudAuthManager.from_env` from `aqara_u200_ble/auth.py`; create `examples/auth_from_env.py` with a function building a `CloudAuthManager` from `os.environ` (dev-only) (C3.3, C4.1)
- [X] T014 [P] [US4] Move `poc_real_lock_unlock.py` and `run_real_lock_unlock.py` from the repo root to `examples/`; fix any path/import references (C4.2)
- [X] T015 [US4] Route login/refresh logging through the DEBUG whitelist (fase/duración/tipo, sin secretos) in `aqara_u200_ble/auth.py` / the flow, reusing the 012 discipline (FR-008)
- [X] T016 [US4] Test: with DEBUG logging, no secret (token, password, sessionKey, nonce, verifyData) appears in `caplog` on success **and** on failure (SC-004)
- [X] T017 [US4] Static/guard test: no `input`/`getpass` and no `from_env`/`os.environ` utility inside `aqara_u200_ble/` (SC-006, SC-007)
- [X] T018 [US4] Update `.env.example`: add `AQARA_ACCOUNT` / `AQARA_PASSWORD` documented as **dev-only** for `examples/auth_from_env.py` (placeholders only)

**Checkpoint**: librería pura y segura.

---

## Phase 7: Polish & Cross-Cutting

- [X] T019 [P] Update existing tests/scripts that referenced `from_env` or the root PoCs to their new locations; keep the whole suite green
- [X] T020 Run [quickstart.md](quickstart.md) gates — `ruff` / `ruff format` / `mypy --strict` / `pytest` + the purity and non-interactive greps — and fix every finding
- [X] T021 [P] Update `docs/devices/u200/validation.md` to show the recommended `auth=<CloudAuthManager>` path (credentials injected, no manual token), keeping the explicit-`signer` note as legacy

---

## Dependencies & Execution Order

- **Setup (T001)** → antes de las tareas de `examples/`.
- **Foundational (T002–T003)** → antes de US2/US3 (necesitan `CloudServiceError`).
- **US1 (T004–T006)** → base del flujo con `auth`; MVP.
- **US2 (T007–T010)** → envuelve el flujo de US1; requiere T004 + T002.
- **US3 (T011–T012)** → requiere T002.
- **US4 (T013–T018)** → T013/T014 en paralelo (ficheros distintos); T017 tras T013.
- **Polish (T019–T021)** → tras el contenido; T020 el último gate.

## Parallel Opportunities

- US1 tests **T005, T006, T006b** en paralelo.
- US4 **T013, T014** en paralelo.
- Polish **T019, T021** en paralelo.

## Implementation Strategy

- **MVP = US1** (T001–T006): operar solo con credenciales — el desbloqueo central.
- **Increment 2 = US2**: renovación transparente en 108 (el caso que hoy falla).
- **Increment 3 = US3**: 810 sin bucles.
- **Increment 4 = US4**: no interactivo, sin secretos en logs, paquete puro.
- **Polish**: reubicaciones, gates verdes, doc de uso recomendado.
