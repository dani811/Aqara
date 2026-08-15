# Phase 0 — Research: decisiones de reorganización documental

Todas las incógnitas del Technical Context estaban resueltas por el `/clarify` o
por inspección del repo. Este documento fija las decisiones de diseño y su
justificación.

## D1 — Idioma de la documentación

- **Decisión**: Todo `docs/` en **inglés**.
- **Rationale**: El resto del repo (README, LICENSE, constitución, `docs/`
  actual) ya está en inglés; mantener un solo idioma cumple FR-003 y amplía el
  alcance a colaboradores. El material de exploración (en español/spanglish) se
  traduce y reescribe al integrarse.
- **Alternativas descartadas**: español (obligaría a traducir el repo entero);
  mixto ref-inglés/guía-español (viola "un solo idioma", induce a confusión).

## D2 — Estructura de `docs/`

- **Decisión**: Árbol **nuevo y limpio** con tres zonas: proceso
  (`porting-guide.md` + `diagnostics.md` + `architecture.md`), **capa transversal**
  (`reference/`) y **capa específica** (`devices/<device>/`), más `evidence/` y un
  `README.md` de entrada.
- **Rationale**: La separación física `reference/` ↔ `devices/` es la
  materialización de FR-008/009/010 y el habilitador de la futura
  multi-dispositivo: "portar" pasa a ser "añadir `devices/<nuevo>/` reusando
  `reference/`". El eje de proceso da la "base para empezar a trabajar" (User
  Story 1).
- **Alternativas descartadas**: parchear el `docs/` actual (mantiene el desorden
  y mezcla transversal con específico); estructura híbrida (menos nítida para la
  separación de capas).

## D3 — Qué es transversal vs específico del dispositivo

- **Decisión**:
  - **Transversal** (→ `reference/`): CRC-16/ARC de framing; login cloud
    (AES-GCM + RSA, `compute_sign`, KDF); capa Bluetooth completa (modelo GATT,
    fragmentación del canal auth, mecanismo `0610`/`0710`, canal de control
    AES-CCM, integridad CRC-HQX del bulk).
  - **Específico del dispositivo** (→ `devices/u200/`): UUIDs/handles GATT
    concretos; catálogo de operaciones/opcodes (familias SYSTEM/USER/LOG/ALARM/
    DEVICELOG/XXQ/SYSTEM_EXT/LONG) y sus payloads; quirks de firmware; protocolo
    de alta del dispositivo si aplica.
- **Rationale**: Los mecanismos y algoritmos son comunes a la familia Aqara; lo
  que cambia entre dispositivos es el mapa concreto de servicios y el conjunto de
  operaciones. Esta línea es exactamente la que un porter necesita para no
  reinventar la capa transversal.
- **Zona gris anotada**: el propio mapa de opcodes *puede* solaparse entre
  dispositivos; se documenta como específico por defecto y, si se confirma común,
  se promueve a transversal en la spec multi-dispositivo (fuera de alcance aquí).

## D4 — Tratamiento del "journey" / la crónica de la investigación

- **Decisión**: Sustituir la narrativa cronológica por `diagnostics.md`, un
  **método de diagnóstico** breve: tabla síntoma → hipótesis → prueba para
  descartar, más heurísticas generalizadas (p.ej. "un campo que varía cada sesión
  puede ser checksum/nonce: pruébalo antes de descartarlo").
- **Rationale**: FR-005/FR-015 exigen solución, no crónica; FR-022 prohíbe el
  encuadre "hecho con IA" y FR-023 prohíbe narrar la PoC. El valor reutilizable de
  los "descartes" del material de exploración es el método, no la historia.
- **Alternativas descartadas**: conservar `journey/` (viola FR-022/023 y el tono
  orientado a solución).

## D5 — Escollos con solución (CRC-16 y login)

- **Decisión**: Cada escollo se documenta como: *qué es → cómo se resuelve
  (accionable) → cómo verificar*. El CRC del `0610` vive en
  `reference/framing-crc.md` (algoritmo CRC-16/ARC, con nuestras palabras/
  pseudocódigo) y se referencia desde `reference/auth-handshake.md` y desde el
  paso de handshake de la guía, **antes** de intentarlo. El login vive en
  `reference/cloud-login.md`.
- **Rationale**: FR-005 + Acceptance Scenario 2 de User Story 1. La solución del
  CRC ya existe verificada (130/133 headers, byte-exacta) y debe presentarse como
  hecho con evidencia, no como odisea.

## D6 — Fuentes de conocimiento y sanitización

- **Decisión**: El conocimiento se extrae de (a) el `docs/` actual del repo
  (limpio, ya sanitizado) y (b) el material de exploración externo (rico pero con
  material sensible). De (b) se traslada **solo el conocimiento**, reescrito en
  inglés y con nuestras palabras, tras sanitización irreversible: eliminar MACs,
  claves, tokens, device/user IDs, rutas a APKs/capturas y cualquier fragmento de
  código propietario de Aqara. La procedencia no se menciona en la salida (FR-023).
- **Rationale**: Principios I y IV; FR-016/017/018 y FR-001/002.
- **Regla de contradicción**: ante afirmaciones divergentes, prevalece la
  respaldada por evidencia byte-exacta; la resolución se hace en la producción y
  no se narra.

## D7 — Alcance de Home Assistant

- **Decisión**: `architecture.md` anota que HA es la integración principal
  prevista y qué implica (control de toda la superficie de operaciones, no solo
  abrir/cerrar). No se escribe guía de integración HA.
- **Rationale**: FR-013 tras clarify; mantiene el alcance "solo docs".

## D8 — Verificación / Definición de Hecho

- **Decisión**: Gates de la doc, detallados en [quickstart.md](quickstart.md):
  enlaces internos sin roturas; escaneo de secretos = 0 y sin APKs/capturas/
  código de Aqara; idioma único (inglés); mapa de capas completo (todo elemento
  clasificado); cada afirmación de protocolo con evidencia o marca "no
  verificada"; diff = solo documentación. **SC-001/SC-002** requieren
  adicionalmente la validación de un **tester externo real** (cold read).
- **Rationale**: Success Criteria SC-001..SC-008; dependencia del tester anotada
  como posible bloqueo de cierre.

## D9 — Herencia del `docs/` actual (qué se conserva y migra)

- **Decisión**: El contenido válido del `docs/` actual se migra a la nueva
  estructura (mapa en [data-model.md](data-model.md)); no se pierde nada
  canónico. Los tutoriales de instalación/captura se integran en la guía de
  portabilidad (preparación/captura); el tutorial end-to-end de la U200 pasa a
  `devices/u200/validation.md`.
- **Rationale**: FR-001 (nada canónico fuera del repo) + FR-020 (sin enlaces
  rotos) + FR-019 (estructura nueva).
