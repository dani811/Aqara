# Feature Specification: Capturar los canales de reporte ff64/ff92 (diagnóstico de estado/eventos)

**Feature Branch**: `feature/022-report-channels`

**Created**: 2026-08-17

**Status**: Draft

**Input**: Los opcodes de estado sondeados a pelo (0x07/0xE5) no obtuvieron respuesta: mandar el opcode solo no es un comando válido. Pero el flujo se suscribe a ff64 (CONTROL_NOTIFY2) y ff92 (AUX_NOTIFY) — los canales de los REPORT_* — y **descarta** sus payloads. Esta feature los captura bajo `U200_DEBUG` para descubrir si la cerradura empuja estado/eventos por ahí, sin cambiar el protocolo.

## Overview

Vía confirmada muerta: keepalive/operate/state_snapshot son ACKs estáticos, y los
opcodes de estado enviados como byte suelto son ignorados por la cerradura. El
siguiente lugar donde puede estar el estado son los **canales de reporte** ff64/ff92,
que hoy habilitamos (porque la app lo hace) pero cuyo contenido tiramos
(`on_notify_ignored → pass`). Esta feature registra lo que llega por esos canales
bajo `U200_DEBUG`, para ver en vivo si la cerradura reporta posición/eventos —
base del futuro trabajo de eventos/sesión persistente. No cambia el protocolo ni el
path de actuación.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ver qué llega por ff64/ff92 (Priority: P1)

Un investigador ejecuta una operación con `U200_DEBUG=1` y ve en stderr cualquier
frame que la cerradura empuje por ff64/ff92, etiquetado por canal.

**Independent Test**: el helper `_debug_report(channel, data)` imprime a stderr solo
cuando `U200_DEBUG` está activo, con el canal y el hex.

**Acceptance Scenarios**:
1. **Given** `U200_DEBUG=1`, **When** llega un frame por ff64/ff92, **Then** se
   registra `report ff64: <hex>` en stderr.
2. **Given** sin `U200_DEBUG`, **When** llega, **Then** no se imprime nada.

### Edge Cases
- Sin cambios de protocolo: los canales ya estaban suscritos; solo se registra su
  contenido en vez de descartarlo.

## Requirements *(mandatory)*

- **FR-001**: El flujo MUST registrar (bajo `U200_DEBUG`) los frames de ff64/ff92,
  etiquetados por canal, en vez de descartarlos.
- **FR-002**: MUST NOT cambiar tramas/CRC/cifrado/orden de CCCD ni el path de
  actuación.
- **FR-003**: MUST NOT registrar secretos (los frames de reporte son estado, no
  material sensible; no se tocan claves/tokens).

## Success Criteria *(mandatory)*

- **SC-001**: Con `U200_DEBUG=1`, un `aqara operate ...` muestra los frames de
  ff64/ff92 si la cerradura empuja algo.
- **SC-002**: Suite verde; ningún test de protocolo cambia.

## Assumptions
- Los REPORT_* de la app llegan por ff64/ff92; capturarlos es el paso previo a
  decidir la vía de eventos (sesión persistente).
