# Feature Specification: Lectura de estado de la cerradura (sondeo + LockState)

**Feature Branch**: `feature/019-lock-status`

**Created**: 2026-08-17

**Status**: Draft

**Input**: Que la librería pueda **leer** el estado de la cerradura (no solo operarla) para que una integración como Home Assistant reporte estado. Sondeo seguro (usando el keepalive confirmado, read-only), una entidad tipada `LockState` que siempre expone la respuesta cruda descifrada y decodifica los campos confirmables, y un camino de captura para decodificar el resto con muestras reales. Los eventos espontáneos (apertura manual/teclado) dependen de una sesión persistente y quedan fuera de este slice.

## Overview

Hoy la librería **opera** (lock/unlock/keepalive) pero no ofrece "¿cómo está la
cerradura?". Una entidad `lock` de Home Assistant necesita reportar estado, y hoy
el adaptador no tiene de dónde leerlo.

El flujo autenticado ya **devuelve la respuesta descifrada** de la cerradura. El
`keepalive` (`2f012f`) está **confirmado** como comando read-only y responde con
un estado (muestra real de esta sesión: `2f002c06`); las operaciones también
responden (unlock → `74007706`). Esta feature convierte esa respuesta en una
entidad **`LockState`** consultable: `U200Client.status()` hace un keepalive y
devuelve `LockState`, que **siempre** expone la respuesta cruda y decodifica los
campos que podamos **confirmar** con evidencia — sin inventar. Lo que aún no se
pueda decodificar se deja como `raw` con una hipótesis documentada, y el
`quickstart` guía la captura de muestras reales (abierta/cerrada/batería) para
completar el decodificador en una iteración posterior.

**Seguridad física**: solo se envía el keepalive confirmado; **no** se mandan
opcodes de estado catalogados-pero-no-confirmados a la cerradura.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Consultar el estado sin operar (Priority: P1)

Un consumidor (HA) llama a `status()` y obtiene un `LockState` con la respuesta
cruda descifrada y los campos ya confirmados, sin mover el cerrojo.

**Why this priority**: una entidad `lock` de HA no es viable sin lectura de estado.

**Independent Test**: con un `FakeLockClient` que responde a un keepalive con bytes
guionizados, `status()` devuelve un `LockState` cuyo `raw_hex` coincide y cuya
`source` es `keepalive`; no se envía ningún comando de actuación.

**Acceptance Scenarios**:
1. **Given** una sesión, **When** se llama `status()`, **Then** se envía el
   keepalive (confirmado) y se devuelve `LockState(raw_hex=…, source="keepalive")`
   sin actuar el cerrojo.
2. **Given** la respuesta de una operación (`lock`/`unlock`), **When** se pide,
   **Then** también puede exponerse como `LockState(source="operation")` con su
   `raw_hex`.
3. **Given** una respuesta que no podemos decodificar del todo, **When** se
   construye `LockState`, **Then** los campos no confirmados quedan `None` y el
   `raw_hex` siempre está presente (nunca se inventa un estado).

### User Story 2 - Decodificar lo confirmable y capturar el resto (Priority: P2)

Un integrador quiere campos legibles (bloqueada/desbloqueada, batería). La feature
decodifica lo que la evidencia soporta y documenta cómo capturar muestras reales
para el resto.

**Independent Test**: `decode_lock_state(raw, source)` mapea los campos
confirmados en tests con muestras reales; para bytes desconocidos deja `raw` y no
falla.

**Acceptance Scenarios**:
1. **Given** una muestra real confirmada, **When** se decodifica, **Then** el
   campo correspondiente sale poblado.
2. **Given** el `quickstart`, **When** el usuario sondea en estados físicos
   distintos, **Then** obtiene muestras etiquetadas (abierta/cerrada) para
   ampliar el decodificador.

### Edge Cases

- Sin respuesta (timeout de notify): `status()` devuelve `LockState` con
  `raw_hex=None` y una marca de "sin respuesta", nunca un estado inventado.
- La feature no debe cambiar bytes/protocolo: reutiliza keepalive y el descifrado
  existentes.
- Eventos espontáneos: fuera de alcance (dependen de sesión persistente); se anota
  como límite conocido.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: La librería MUST exponer una entidad tipada `LockState` con al menos
  `raw_hex`, `source` (`keepalive`/`operation`), y campos decodificados
  **opcionales** (p. ej. `locked`, `battery_percent`) que son `None` mientras no
  estén confirmados.
- **FR-002**: `U200Client.status()` MUST sondear con el **keepalive confirmado**
  (read-only) y devolver un `LockState`; MUST NOT enviar opcodes de estado no
  confirmados.
- **FR-003**: La respuesta de `lock()`/`unlock()`/`operate()` MUST poder
  exponerse como `LockState(source="operation")` sin perder `response_hex`.
- **FR-004**: `decode_lock_state(raw, source)` MUST decodificar solo campos
  respaldados por evidencia; ante bytes desconocidos deja los campos `None` y
  nunca lanza ni inventa.
- **FR-005**: Ante ausencia de respuesta, `LockState` MUST reflejar "sin
  respuesta" (`raw_hex=None`) sin inventar estado.
- **FR-006**: El CLI MUST ofrecer `aqara state` que imprime el `LockState`
  (incluido `raw_hex`) sin secretos.
- **FR-007**: MUST NOT cambiar tramas/CRC/cifrado; solo añade lectura sobre la
  respuesta ya descifrada (Constitución II).
- **FR-008**: La documentación MUST registrar las muestras reales confirmadas y el
  procedimiento de captura para ampliar el decodificador; y anotar los eventos
  espontáneos como límite conocido (dependen de sesión persistente).

### Key Entities

- **LockState**: instantánea del estado — `raw_hex`, `source`, y campos
  decodificados opcionales con su confianza.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `status()` devuelve un `LockState` con `raw_hex` real contra un
  fake, sin actuar (probado sin radio).
- **SC-002**: 0 estados inventados: campos no confirmados quedan `None`.
- **SC-003**: La suite sigue verde; ningún test de protocolo cambia.
- **SC-004**: `aqara state` imprime el estado real de la cerradura (validación con
  hardware) y el usuario puede capturar muestras etiquetadas para el decodificador.

## Assumptions

- El keepalive es read-only y no mueve el cerrojo (confirmado en la RE y en vivo).
- La respuesta del keepalive/operación codifica estado; su decodificación exacta
  se completa con muestras reales (esta feature entrega el andamiaje honesto + el
  `raw`).
- Los eventos espontáneos requieren mantener la sesión/notificaciones vivas (otra
  feature: sesión persistente); aquí solo hay sondeo bajo demanda.
