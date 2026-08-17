# Feature Specification: Identificación de dispositivos por el aire + captura del inventario cloud

**Feature Branch**: `feature/016-device-inventory`

**Created**: 2026-08-17

**Status**: Draft

**Input**: Reconocer la cerradura y poder listar/identificar dispositivos por nombre, fabricante y **modelo**. Enriquecer el anuncio BLE decodificando el payload de fabricante 0x0B27 (producto/modelo) para identificar el modelo sin conectar; y sentar la captura del endpoint cloud de inventario (lista de dispositivos de la cuenta) que hoy no está capturado, mediante una herramienta read-only que ejecuta el usuario con sus credenciales (el asistente nunca las ve).

## Overview

Hoy `scan()` devuelve candidatos con nombre, fabricante y servicios, pero **no
sabe el modelo**. El anuncio de la U200 incluye un payload de fabricante
`0x0B27` (13 bytes observados: `2808 039c 51 ...`) cuyo `product_id` (u16 LE en
el offset 2) vale **`0x9C03`** — verificado hoy en vivo y coincidente con lo que
el parser real `xiaomi-ble` leyó en la investigación original. Ese `product_id`
identifica el **modelo** sin conectar.

Esta feature: (1) decodifica ese payload y expone `product_id`/`model` en el
candidato de escaneo, de modo que un listado por el aire diga "U200"; (2) como
el **inventario de la cuenta** (endpoint cloud que lista todos los dispositivos:
did, modelo `lumi.lock.*`, nombre, habitación, estado) **no está capturado**,
entrega una herramienta read-only para que el usuario lo capture con su propia
sesión, y documenta la evidencia sanitizada para una feature posterior que
exponga `list_devices()`.

Fuera de alcance (evidencia): el Device Information Service GATT `0x180A` solo
dice "Silicon Labs / Blue Gecko" — inútil para el modelo (descartado en vivo).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Identificar el modelo por el aire, sin conectar (Priority: P1)

Un consumidor escanea y, además de nombre/fabricante/servicios, ve el **modelo**
del dispositivo (p. ej. "U200") deducido del anuncio, para reconocer la cerradura
entre varios dispositivos sin conectarse a ninguno.

**Why this priority**: es el "identificar por nombre/manufacturer/module" pedido,
y es 100% offline (no requiere credenciales, app ni conexión).

**Independent Test**: con el payload real de fabricante `0x0B27` observado, el
candidato expone `product_id=0x9C03` y `model="U200"`; con un fabricante `0x0B27`
de payload desconocido, `product_id` se decodifica pero `model` queda `None`; sin
fabricante, ambos `None`.

**Acceptance Scenarios**:

1. **Given** un anuncio de la U200 con su payload de fabricante, **When** se
   escanea, **Then** el candidato incluye `manufacturer_payload` (crudo),
   `product_id` y `model="U200"`.
2. **Given** un dispositivo con fabricante `0x0B27` pero payload demasiado corto o
   producto no catalogado, **When** se escanea, **Then** `product_id` se decodifica
   si hay bytes suficientes y `model` queda `None` (nunca inventa un modelo).
3. **Given** un listado de varios candidatos, **When** se imprime, **Then** cada
   uno muestra su modelo (o "?") junto a nombre/señal/razones.

---

### User Story 2 - Capturar el inventario cloud de la cuenta (Priority: P2)

El usuario quiere que la librería, a futuro, liste los dispositivos de su cuenta
(para no configurar el did a mano). Como el endpoint no está capturado, ejecuta
una herramienta read-only que, con sus credenciales en línea (el asistente no las
ve), prueba endpoints candidatos de inventario y **guarda la evidencia
sanitizada** (forma de la respuesta, sin secretos) para implementarlo después.

**Why this priority**: desbloquea `list_devices()` sin adivinar el protocolo;
respeta la Constitución (evidencia + secretos) y la política de que el asistente
no ve credenciales.

**Independent Test**: la herramienta se ejecuta con credenciales, hace solo
peticiones de lectura, imprime qué endpoints responden y escribe un volcado
sanitizado bajo un directorio git-ignored; sin credenciales, aborta con un
mensaje claro.

**Acceptance Scenarios**:

1. **Given** credenciales de cuenta en el entorno, **When** el usuario lanza la
   herramienta, **Then** prueba una lista de rutas candidatas de inventario (solo
   GET/lectura), informa el código/forma de cada respuesta y no muta nada.
2. **Given** una respuesta con lista de dispositivos, **When** se guarda, **Then**
   el volcado va a un directorio git-ignored y **redacta** did/mac/token antes de
   escribir.
3. **Given** faltan credenciales, **When** se lanza, **Then** aborta con un
   mensaje que dice qué variables faltan (nunca las imprime).

---

### Edge Cases

- Payload de fabricante de <4 bytes: `product_id=None`, `model=None`.
- Varios `product_id` del mismo modelo en el futuro: la tabla mapea id→modelo; ids
  desconocidos no rompen el escaneo.
- La herramienta de captura nunca escribe secretos en claro; si no puede redactar,
  no escribe.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `identify_candidate`/`ScanCandidate` MUST exponer el payload de
  fabricante `0x0B27` crudo (`manufacturer_payload`) y, cuando haya bytes,
  `product_id` (u16 little-endian en offset 2 del payload).
- **FR-002**: El sistema MUST mapear `product_id` conocidos a `model`
  (`0x9C03 → "U200"`); un id no catalogado deja `model=None` sin error.
- **FR-003**: La decodificación MUST NO alterar la lógica de `reasons`/`score` ni
  el protocolo; es información añadida.
- **FR-004**: El listado (escáner/ejemplo) MUST mostrar el modelo por candidato.
- **FR-005**: El repo MUST incluir una herramienta read-only que el usuario
  ejecuta con sus credenciales para **descubrir/capturar** el endpoint de
  inventario cloud, haciendo solo peticiones de lectura.
- **FR-006**: La herramienta MUST NO imprimir ni persistir secretos en claro;
  cualquier volcado va a una ruta git-ignored y con did/mac/token redactados.
- **FR-007**: La documentación de referencia MUST registrar, con evidencia
  sanitizada, el `product_id` del U200 y los endpoints cloud ya observados
  (`/dev/bluetooth/query`, `/app/dev/query/detail`) y el estado "pendiente de
  captura" del endpoint de lista de dispositivos.

### Key Entities

- **Modelo de dispositivo**: `product_id` (entero del anuncio) → nombre de modelo
  ("U200"); tabla ampliable.
- **Candidato de escaneo (ampliado)**: gana `manufacturer_payload`, `product_id`,
  `model`.
- **Volcado de evidencia**: respuesta cloud sanitizada (did/mac/token redactados)
  guardada localmente para diseñar `list_devices()`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un escaneo de la U200 real muestra `model="U200"` sin conectar.
- **SC-002**: 0 modelos inventados: todo `product_id` no catalogado da `model=None`.
- **SC-003**: La suite sigue verde y ningún test de protocolo cambia.
- **SC-004**: El usuario puede lanzar la herramienta de captura con sus
  credenciales en línea sin que el asistente las vea, y obtener un volcado
  sanitizado que permita diseñar `list_devices()`.

## Assumptions

- `product_id=0x9C03` identifica el modelo U200 (evidencia: anuncio real 2026-08-17
  + parser xiaomi-ble de la investigación original). No es un identificador por
  unidad.
- El resto del payload de fabricante (contador, bytes finales) queda como crudo;
  su semántica exacta no se afirma sin más muestras.
- El endpoint de inventario existe (la app muestra la lista) pero su forma exacta
  se captura en una sesión del usuario; `list_devices()` se implementa en una
  feature posterior con esa evidencia.
- Las credenciales las inyecta el usuario; la librería no lee el entorno.
