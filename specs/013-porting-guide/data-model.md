# Phase 1 — Data Model (entidades documentales)

Esta feature es documental: el "modelo de datos" son los **tipos de documento**,
sus atributos obligatorios, sus relaciones y el **mapa de migración** origen →
destino.

## Entidades documentales

### Entry Point (`docs/README.md`)
- **Rol**: único punto de entrada; enruta al lector por objetivo.
- **Atributos**: rutas de lectura *understand* / *port* / *diagnose*; índice del
  árbol; declaración de idioma (inglés) y de alcance.
- **Relaciones**: enlaza a todos los documentos de primer nivel.

### Architecture (`docs/architecture.md`)
- **Rol**: marco mental del sistema.
- **Atributos**: pipeline de fases (cloud + BLE) con orden y porqué; tecnología
  (BLE + Thread, sin Wi-Fi); modelo de confianza (sin bonding SMP; seguridad en
  capa de aplicación); app oficial como implementación de referencia; **nota HA
  como destino**.
- **Relaciones**: referencia `reference/*` para el detalle de cada fase.

### Porting Guide (`docs/porting-guide.md`) — **eje**
- **Rol**: proceso lineal numerado para portar un dispositivo.
- **Atributos**: pasos ordenados = {0 preparación/entorno, 1 captura de tráfico,
  2 identificación del mapa GATT, 3 resolución del handshake de auth, 4 apertura
  del canal de control, 5 mapeo del catálogo de operaciones}; en cada paso:
  **callout transversal-vs-específico** y, donde aplique, **escollo + solución +
  verificación**; U200 como ejemplo resuelto, U400 como ejemplo de destino.
- **Relaciones**: cada paso enlaza al documento `reference/*` (reutilizable) y a
  `devices/<device>/*` (a rellenar); enlaza a `diagnostics.md` para atascos.

### Diagnostic Method (`docs/diagnostics.md`)
- **Rol**: desatascar la portabilidad.
- **Atributos**: tabla **síntoma → hipótesis → prueba de descarte**; heurísticas
  generalizadas; breve y sin crónica ni cuantificación de esfuerzo.
- **Relaciones**: referenciado desde los pasos de la guía.

### Reference Doc (capa transversal, `docs/reference/*`)
- **Rol**: mecanismo/algoritmo agnóstico del dispositivo.
- **Instancias**: `framing-crc.md`, `cloud-login.md`, `ble-transport.md`,
  `auth-handshake.md`, `control-channel.md`.
- **Atributos obligatorios**: etiqueta **Layer: transversal**; descripción con
  nuestras palabras/pseudocódigo (sin código de Aqara); **cita de evidencia** o
  marca "no verificado"; en inglés.
- **Relaciones**: citados por la guía y por `architecture.md`; anclados a
  `evidence/`.

### Device Doc (capa específica, `docs/devices/<device>/*`)
- **Rol**: lo que cambia por dispositivo.
- **Instancias (U200)**: `README.md`, `gatt-map.md`, `operations.md`,
  `validation.md`.
- **Atributos obligatorios**: etiqueta **Layer: device-specific (U200)**; mapa
  GATT concreto; catálogo de opcodes con estado (confirmado / catalogado / no
  verificado); walkthrough de validación end-to-end.
- **Relaciones**: reutiliza `reference/*`; anclado a `evidence/`.

### Evidence Index (`docs/evidence/README.md`)
- **Rol**: respaldar afirmaciones sin exponer capturas.
- **Atributos**: por afirmación → {tipo de evidencia, método de verificación,
  resultado sanitizado}; nunca capturas crudas.
- **Relaciones**: destino de las citas de `reference/*` y `devices/*`.

### Layer Map (sección en `docs/architecture.md`, contrato en `contracts/layer-map.md`)
- **Rol**: clasificar cada elemento del sistema.
- **Atributos**: por elemento → {nombre, capa ∈ {transversal, device-specific},
  documento donde vive}.

## Enumeraciones

- **Layer**: `transversal` | `device-specific`.
- **ClaimStatus** (afirmaciones de protocolo): `confirmed` (evidencia
  byte-exacta) | `catalogued` (extraído pero no ejercido) | `unverified`.

## Mapa de migración (origen → destino)

> "Repo actual" = `docs/` de este repo. "Exploración" = material externo
> (solo conocimiento, sanitizado y traducido). Ningún artefacto sensible migra.

| Destino nuevo | Origen (repo actual) | Aporte de la exploración (sanitizado) |
| --- | --- | --- |
| `README.md` | `docs/README.md` | — |
| `architecture.md` | `docs/architecture.md` | pipeline end-to-end, modelo de confianza, nota HA |
| `porting-guide.md` | `docs/tutorials/*` (getting-started, capture-credentials, first-unlock) | procedimiento de captura y conexión, orden recomendado |
| `diagnostics.md` | `docs/journey/README.md` (reescrito, sin crónica) | los "descartes por capa" → tabla síntoma/hipótesis/prueba |
| `reference/framing-crc.md` | `docs/protocol/auth-handshake.md` (§CRC) | algoritmo CRC-16/ARC descrito con nuestras palabras |
| `reference/cloud-login.md` | `docs/protocol/cloud-api.md` | login/RSA/AES-GCM/compute_sign, KDF |
| `reference/ble-transport.md` | `docs/architecture.md` (GATT map), `docs/protocol/control-channel.md` (§ATT) | modelo GATT, fragmentación canal auth, puertos |
| `reference/auth-handshake.md` | `docs/protocol/auth-handshake.md` | secuencia KEY_EXCHANGE / AUTH_PROOF `0610`/`0710` |
| `reference/control-channel.md` | `docs/protocol/control-channel.md` | AES-CCM(tag=4, aad=∅), CRC-HQX del bulk |
| `devices/u200/gatt-map.md` | `docs/architecture.md` (tabla GATT) | UUIDs propietarios, mapa ATT confirmado |
| `devices/u200/operations.md` | `docs/protocol/operations.md` | familias de comando y sub-cmds, builders |
| `devices/u200/validation.md` | `docs/tutorials/end-to-end-unlock.md` | receta reproducible |
| `evidence/README.md` | `docs/evidence/README.md` | claims adicionales verificados |

**Reglas de la migración**:
1. Todo destino en inglés; nada canónico queda solo en la exploración (FR-001).
2. Cero secretos / APKs / capturas / código de Aqara (FR-016).
3. Sin enlaces rotos: actualizar también README/CONTRIBUTING del repo (FR-020).
4. Contradicciones resueltas en una dirección, sin narrarlo (FR-002/023).
