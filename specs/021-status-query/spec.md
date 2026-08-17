# Feature Specification: Sondeo read-only de opcodes de estado (para decodificar la posición)

**Feature Branch**: `feature/021-status-query`

**Created**: 2026-08-17

**Status**: Draft

**Input**: Los comandos legibles hoy (keepalive `2f002c06`, ACK de operar `74007706`, state_snapshot `33003006`) son ACKs estáticos: **no cambian con la posición del cerrojo** (verificado en vivo, cerrojo movido de verdad). Para leer estado real hace falta enviar los opcodes de estado dedicados del catálogo (`LOCK_STATUS 0x07`, `GET_DOOR_LOCK_STATUS 0xE5`, `REPORT_LOCK_STATUS 0x15`, batería `0x4F`), que el CLI aún no sabe enviar. Esta feature añade un envío **read-only acotado** para sondear cuál reporta la posición, sin tocar el path de actuación.

## Overview

La feature 019 entregó `status()` vía keepalive, pero se ha **confirmado en vivo**
que keepalive/operate/state_snapshot devuelven ACKs estáticos que no codifican la
posición. Para avanzar hacia el estado real hay que sondear los opcodes de estado
del catálogo (feature 010) que hoy no son despachables.

Esta feature añade la capacidad de **construir y enviar una trama de control
genérica** (`build_control_frame(sub_cmd, data)`, ya existente) a través de la
sesión autenticada, y exponerla como una **consulta acotada a opcodes de
estado/batería** (nunca `SET_*`). Con ella el usuario sondea `LOCK_STATUS`,
`GET_DOOR_LOCK_STATUS`, etc. en cerrada vs abierta y encontramos cuál cambia; ese
byte alimenta el decodificador de `LockState` (feature 019). El path de actuación
(lock/unlock) queda **byte a byte idéntico**.

**Seguridad física**: la superficie de terminal solo permite una lista blanca de
opcodes de **consulta/estado/batería** (read-only por su nombre en el enum de la
app); los `SET_*` no se exponen. La librería permite enviar cualquier sub-comando
para consumidores avanzados, documentando que es responsabilidad del llamante.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Sondear opcodes de estado para hallar la posición (Priority: P1)

Un usuario ejecuta una consulta de estado (p. ej. `aqara query lock_status`) en
cerrada y en abierta; si la respuesta difiere, ahí está el estado.

**Independent Test**: contra un fake que responde bytes guionizados a un opcode de
consulta, `U200Client.query(0x07)` devuelve un `LockState` con `raw_hex` = esa
respuesta y `source="query"`, y la trama escrita es `build_control_frame(0x07)`.

**Acceptance Scenarios**:
1. **Given** un opcode de consulta, **When** se envía, **Then** la trama en claro
   es exactamente `<sub_cmd> + data` (build_control_frame) con prefijo 0x01, y se
   devuelve la respuesta descifrada como `LockState(source="query")`.
2. **Given** la superficie de terminal, **When** el usuario pide un nombre fuera
   de la lista blanca de consulta, **Then** se rechaza con un mensaje que explica
   que solo se permiten opcodes de estado/batería (no `SET_*`).

### User Story 2 - El path de actuación no cambia (Priority: P1)

**Independent Test**: los bytes escritos por `lock()`/`unlock()` son idénticos a
antes (test de igualdad de bytes con el fake); ningún test de protocolo cambia.

**Acceptance Scenarios**:
1. **Given** `lock()`/`unlock()`, **When** se ejecutan, **Then** producen las
   mismas tramas que antes de esta feature.

### Edge Cases

- Sin respuesta a la consulta: `LockState(responded=False)`, nunca estado inventado.
- Un opcode de consulta puede no responder o responder vacío: se refleja, no se rompe.
- La librería no impide enviar un sub-comando arbitrario (avanzado); la CLI sí lo acota.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: La librería MUST poder enviar una trama de control genérica
  (`build_control_frame(sub_cmd, data)`) por la sesión autenticada y devolver la
  respuesta descifrada, reutilizando el flujo existente (sin tocar el path de
  actuación).
- **FR-002**: `U200Client` MUST exponer `query(sub_cmd, data=b"") -> LockState`
  (source `"query"`).
- **FR-003**: El CLI MUST ofrecer `aqara query <nombre|hex>` **acotado** a una
  lista blanca de opcodes de estado/batería (read-only); MUST rechazar cualquier
  otro (incluidos `SET_*`).
- **FR-004**: El path de actuación (lock/unlock/keepalive/state_snapshot) MUST
  permanecer byte a byte idéntico (test de igualdad).
- **FR-005**: La ausencia de respuesta MUST dar `LockState(responded=False)` sin
  inventar estado.
- **FR-006**: El CLI MUST NOT imprimir secretos; la consulta MUST NOT actuar el
  cerrojo.
- **FR-007**: La documentación MUST listar los opcodes de consulta permitidos,
  marcarlos como **no confirmados** (sondeo) y explicar el objetivo (hallar el
  byte de posición) y el procedimiento de captura.

### Key Entities

- **Consulta de estado**: un sub-comando read-only del catálogo + su respuesta
  descifrada (envuelta en `LockState`).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `aqara query lock_status` envía `07` y muestra la respuesta real de
  la cerradura, sin actuar.
- **SC-002**: El path de actuación no cambia (igualdad de bytes; suite verde).
- **SC-003**: La CLI rechaza opcodes no-consulta (0 riesgo de `SET_*` accidental).
- **SC-004**: El usuario puede sondear cerrada vs abierta y, si algún opcode
  difiere, se decodifica la posición en una iteración.

## Assumptions

- Los opcodes de consulta (`0x07/0x08/0xE5/0x15/0x4F/0x78`) son read-only por su
  nombre en el enum decompilado de la app; el payload exacto es desconocido, así
  que el sondeo envía solo el opcode (sin datos) como primer intento honesto.
- Si ningún opcode de consulta reporta la posición, la vía definitiva es por
  eventos espontáneos (sesión persistente), fuera de alcance aquí.
