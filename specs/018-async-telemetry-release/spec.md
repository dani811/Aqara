# Feature Specification: Cierre de deuda async (telemetría + test) y release 0.5.0 para Home Assistant

**Feature Branch**: `fix/018-async-telemetry-release`

**Created**: 2026-08-17

**Status**: Draft

**Input**: Cerrar las peticiones de la integración consumidora `dani811/haos_aqara`
sobre esta librería. Issue #1 (cloud I/O async-safe) ya está resuelta por la
feature 012; quedan dos defectos verificados de esa misma línea — #3 (la
telemetría DEBUG registra el id del hilo del event loop, no el del worker) y #2
(el test de responsividad exige >0 en vez de ≥80%) — y la #4 (publicar un release
fijable en `manifest.json`). El repo ya va por 0.5.0 (no 0.2.0) y las URLs de
`pyproject.toml` no apuntan al repositorio real.

## Overview

La integración de Home Assistant `haos_aqara` (su PR #2 está en draft, bloqueado)
necesita de esta librería: (a) que el límite cloud sea async-safe — **ya hecho**
(feature 012, `_run_cloud_phase` usa `await asyncio.to_thread`) — y (b) un
**release fijable**. Antes de publicar quedan dos defectos pequeños pero reales de
la línea async, ambos verificados en el código actual:

- **#3**: `_run_cloud_phase` llama `threading.get_ident()` **después** del
  `await`, ya de vuelta en el hilo del event loop → el log "worker thread N"
  miente (no es el worker). Es un defecto de **observabilidad**, no de
  comportamiento.
- **#2**: `test_slow_cloud_does_not_stall_event_loop` afirma
  `len(...) > 0`, que pasa con 1/5 (20%) y no prueba el criterio ≥80% que la
  feature 012 documenta.

Esta feature corrige ambos y **publica el release** (versión y URLs correctas,
gate completo, wheel verificada, tag inmutable) para cerrar #4 y desbloquear
`haos_aqara`. #1 se cierra como ya resuelta.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Telemetría de hilo correcta (#3) (Priority: P1)

Un operador que activa el log DEBUG ve, en el registro de finalización de una fase
cloud, el id del **hilo worker que ejecutó** la llamada bloqueante, no el del
event loop.

**Independent Test**: ejecutar una fase cloud cuyo helper devuelve su propio
`get_ident()`; el id registrado coincide con el del worker y **difiere** del hilo
principal/event loop.

**Acceptance Scenarios**:
1. **Given** una fase cloud, **When** completa, **Then** el DEBUG reporta el id
   del hilo que ejecutó el helper (no el del loop).
2. **Given** el fix, **When** se revisa, **Then** no se añade a los logs ninguna
   URL, cabecera, payload, id de dispositivo, credencial ni material cripto.

### User Story 2 - El test exige ≥80% (#2) (Priority: P1)

El test de responsividad del event loop falla si menos del 80% de las tareas
ligeras concurrentes completan mientras una llamada cloud lenta está en su worker.

**Independent Test**: con N tareas programadas, la aserción exige ≥⌈0.8·N⌉
completadas, sin umbrales de milisegundos frágiles.

**Acceptance Scenarios**:
1. **Given** 5 tareas, **When** corre el test, **Then** exige ≥4 completadas.
2. **Given** el criterio, **When** se calcula, **Then** es genérico respecto al
   número de tareas y no usa asserts de tiempo en ms.

### User Story 3 - Release 0.5.0 fijable por Home Assistant (#4) (Priority: P1)

`haos_aqara` puede fijar la librería en su `manifest.json` a una versión estable
publicada, con URLs de proyecto correctas y una wheel que instala limpia.

**Independent Test**: el gate completo (`pytest`, `ruff`, `mypy --strict`, build)
pasa; la wheel contiene `aqara_u200_ble` y `py.typed`; existe un tag inmutable de
la versión.

**Acceptance Scenarios**:
1. **Given** el repo, **When** se corrige `pyproject.toml`, **Then** las URLs
   apuntan al repositorio/issue tracker reales.
2. **Given** el commit validado, **When** se publica, **Then** hay un tag
   inmutable de la versión y la wheel instala en un entorno limpio.
3. **Given** el release, **When** se documenta, **Then** queda claro el artefacto
   y versión exactos para el `requirements` de HA.

### Edge Cases

- El fix de #3 no debe cambiar la API pública ni el comportamiento BLE/cloud.
- Si en el futuro se cambia N de tareas, el umbral del test se recalcula solo.
- La versión publicada es la **actual (0.5.0)**, no la 0.2.0 caducada de la issue.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `_run_cloud_phase` MUST capturar el id del hilo **dentro** de la
  ejecución del worker y registrar ese id (no el del event loop).
- **FR-002**: Un test MUST probar que el id de worker registrado/capturado
  difiere del hilo del event loop.
- **FR-003**: El fix de telemetría MUST NOT cambiar la API pública ni el
  comportamiento; `asyncio.to_thread` sigue siendo el límite.
- **FR-004**: Ningún log MUST añadir datos sensibles (URLs, cabeceras, payloads,
  ids de dispositivo, credenciales, material de sesión/cripto, mensajes crudos de
  excepción).
- **FR-005**: `test_slow_cloud_does_not_stall_event_loop` MUST exigir ≥80% de
  completadas, con umbral derivado del número programado y sin asserts de ms.
- **FR-006**: `pyproject.toml` MUST tener URLs correctas del repositorio real y la
  versión publicable actual.
- **FR-007**: El gate de release (`pytest`, `ruff`, `mypy --strict`, build) MUST
  pasar; la wheel MUST contener `aqara_u200_ble` y `py.typed`.
- **FR-008**: MUST crearse un tag inmutable de la versión desde el commit validado.
- **FR-009**: La documentación MUST indicar el artefacto/versión exactos para el
  `requirements` de Home Assistant.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El DEBUG de una fase cloud muestra el id del worker real (test lo
  prueba: worker ≠ event loop).
- **SC-002**: El test de responsividad falla por debajo del 80% y pasa con el
  código async correcto.
- **SC-003**: Gate completo verde; wheel con `py.typed` instala limpia; tag
  publicado.
- **SC-004**: `haos_aqara` puede fijar la versión en `manifest.json` y cerrar su
  dependencia; issues #1–#4 quedan resueltas.

## Assumptions

- La versión a publicar es **0.5.0** (estado real del repo), reinterpretando la
  #4 que hablaba de 0.2.0.
- El repositorio canónico es el remoto real (`github.com/dani811/Aqara`); se
  corrigen las URLs a él.
- No se añade comportamiento específico de Home Assistant a la librería (non-goal
  de la #4): el adaptador HA sigue siendo de `haos_aqara`.
