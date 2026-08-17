# Feature Specification: Ventana de escucha post-comando (estado/eventos espontáneos)

**Feature Branch**: `feature/023-listen-window`

**Created**: 2026-08-17

**Status**: Draft

**Input**: Verificado en vivo que keepalive/operate/state_snapshot son ACKs estáticos, los opcodes de estado a pelo se ignoran, y ff64/ff92 están mudos en la ventana de un solo comando. La cerradura probablemente reporta estado/eventos tras el ACK o al operar el teclado; solo se ve manteniendo la conexión y escuchando. Esta feature añade una ventana de escucha post-comando opt-in que reenvía todos los frames (ff62 descifrado, ff64/ff92 crudo), sin cambiar el path de actuación (default 0.0 = idéntico). Base del estado en tiempo real para Home Assistant.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Escuchar reportes espontáneos (Priority: P1)
`aqara listen --seconds N` mantiene la sesión abierta N s tras un keepalive y
muestra cualquier frame que la cerradura empuje.

**Independent Test**: un fake que emite frames extra por ff64/ff92 tras la
respuesta → `on_report` los recibe; con `listen_after=0` no se reenvía nada.

**Acceptance Scenarios**:
1. **Given** `listen_after>0` y `on_report`, **When** llegan frames extra, **Then**
   se reenvían (ff62 descifrado; ff64/ff92 crudo) hasta expirar la ventana.
2. **Given** `listen_after=0` (default), **When** se opera, **Then** comportamiento
   byte-idéntico al anterior (un comando, una respuesta, desconectar).

### Edge Cases
- Sin `on_report`: no reenvía, no rompe.
- La ventana no reintenta ni reautentica (ocurre tras actuar).

## Requirements *(mandatory)*
- **FR-001**: `run_authenticated_lock_operation` MUST aceptar `listen_after` (s) y
  `on_report(channel, data)`; tras la primera respuesta, reenviar frames extra de
  ff62 (descifrado), ff64/ff92 (crudo) hasta expirar.
- **FR-002**: Default `listen_after=0.0` MUST preservar el comportamiento y los
  bytes del actuador exactamente (test de igualdad existente).
- **FR-003**: `U200Client.listen(seconds)` (no actúa) y `aqara listen`.
- **FR-004**: Sin secretos en los frames reenviados (son estado/eventos).

## Success Criteria *(mandatory)*
- **SC-001**: El fake que emite por ff64/ff92 es reenviado por `on_report`.
- **SC-002**: `listen_after=0` no reenvía nada; suite verde; actuador byte-igual.
- **SC-003**: `aqara listen` imprime lo que llega (o "nada") sin actuar.

## Assumptions
- Si aun con la ventana la cerradura no reporta posición, la vía es capturar el
  status-query de la app (Frida, móvil real). El evento de teclado/manual sí debería
  aparecer aquí si se opera durante la ventana.
