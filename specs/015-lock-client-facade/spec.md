# Feature Specification: Cliente U200 de alto nivel (fachada: login → escaneo → conexión → operación)

**Feature Branch**: `feature/015-lock-client-facade`

**Created**: 2026-08-17

**Status**: Draft

**Input**: User description: "Fachada de alto nivel de la librería (cliente U200): la librería empaquetada debe ofrecer, en un solo flujo coherente y con una API pública clara: (1) login inicial al cloud de Aqara con usuario y contraseña (sin token manual), (2) mecanismo de reautenticación automática si el token falla (code 108) reutilizando CloudAuthManager, (3) escaneo BLE e identificación de la cerradura por nombre anunciado ("DoorLocker"), fabricante 0x0B27 y/o servicios expuestos (fcb9/ff60/ff90), con MAC opcional como filtro; (4) conexión y descubrimiento de servicios/características GATT sobre el transporte elegido (Bluetooth nativo vía bleak o controlador HCI externo ESP32-S3 vía Bumble, ambos detrás de una misma abstracción de transporte que hace scan+connect+discover); (5) flujo de operación (lock/unlock y el resto del catálogo) que encadena todo lo anterior: `client = await U200Client.connect(auth=..., transport=..., mac=...)`; `await client.lock()`. Hoy todas las piezas existen (kdf/auth/scanner/session/bumble_transport) pero están sueltas y cada runner (tools/bumble_lock.py, examples/*) las cablea a mano; el escáner solo imprime, no devuelve dispositivos ni identifica por servicios, y no hay transporte bleak empaquetado (hay que restringir servicios en macOS/CoreBluetooth para que no falle el descubrimiento de descriptores). Además, incluir en tools/ el firmware ESP-IDF "esp32s3_hci_usb" (controlador BLE HCI H4 sobre USB-Serial-JTAG) con el que se ha verificado hoy la ruta Bumble, y un único runner de ejemplo que use la fachada."

## Overview

Hoy la librería tiene todas las piezas del flujo — login cloud con renovación
automática (feature 014), escáner pasivo, adaptador para controlador externo,
sesión autenticada y catálogo de operaciones — pero **no las ofrece como un
flujo**. Cada consumidor (los runners de `tools/` y `examples/`) tiene que
cablearlas a mano: abrir el transporte, conectar por MAC, descubrir servicios,
envolver el cliente, construir el firmante y llamar a la sesión. El escáner solo
imprime por pantalla, no devuelve candidatos ni sabe reconocer la cerradura por
los servicios que anuncia; y el transporte Bluetooth nativo del sistema no está
empaquetado (funciona, pero con un ajuste que hoy solo vive en un script suelto).

Esta feature entrega la **fachada de la librería**: una única puerta de entrada
que, dadas las credenciales de cuenta y la elección de radio, hace por sí sola
login, escaneo e identificación de la cerradura, conexión y descubrimiento, y
expone las operaciones del catálogo (bloquear, desbloquear, …) como llamadas
directas. Con ella un consumidor (un desarrollador, la integración de Home
Assistant) bloquea la puerta en tres líneas y sin conocer el protocolo. Incluye
además, como herramienta reproducible, el firmware que convierte un ESP32‑S3 en
el controlador Bluetooth externo con el que se ha verificado la ruta hoy, y un
único ejemplo que use la fachada (reemplazando los runners cableados a mano).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Bloquear la cerradura con la fachada, en un solo flujo (Priority: P1)

Un desarrollador configura las credenciales de su cuenta y elige el transporte
(Bluetooth del propio equipo, o un controlador externo indicando su puerto). Pide
a la librería «conéctate a mi cerradura» y después «bloquea». La librería hace
login por sí sola, encuentra la cerradura por el aire, se conecta, descubre lo que
necesita y ejecuta la operación, devolviendo el resultado. Ninguna de las fases
intermedias requiere código del consumidor.

**Why this priority**: es el propósito de la librería ("bloquear la cerradura
usando la librería"); sin este flujo cada consumidor reinventa el cableado y la
integración de Home Assistant no es viable.

**Independent Test**: con credenciales válidas y una cerradura al alcance, un
script de ~5 líneas (crear auth, conectar, `lock()`) mueve el cerrojo. En
pruebas sin hardware, el mismo flujo se verifica con un transporte simulado que
registra el orden de las fases (login → escaneo → conexión → descubrimiento →
operación).

**Acceptance Scenarios**:

1. **Given** credenciales de cuenta válidas y la cerradura anunciándose, **When**
   el consumidor conecta y pide `lock`, **Then** la librería realiza login,
   localiza la cerradura, conecta, descubre servicios y ejecuta el bloqueo, y
   devuelve el resultado de la operación (o la ausencia de respuesta, si el
   cerrojo se movió sin contestar).
2. **Given** el mismo cliente ya conectado, **When** el consumidor pide `unlock`
   y luego `lock`, **Then** ambas operaciones se ejecutan en secuencia sobre la
   misma conexión, sin repetir escaneo ni login.
3. **Given** el consumidor pide otra operación del catálogo (p. ej. volumen de
   voz), **When** la invoca por su nombre, **Then** la fachada la ejecuta con la
   misma sesión, sin que el consumidor construya tramas.

---

### User Story 2 - Encontrar e identificar la cerradura sin conocer su MAC (Priority: P1)

Un consumidor no sabe (o no quiere configurar) la dirección de su cerradura. Pide
a la librería que escanee y ésta devuelve la lista de candidatos que **parecen
una U200**, identificados por lo que anuncian: nombre, identificador de
fabricante y/o los servicios expuestos. Si el consumidor sí conoce la MAC, la usa
como filtro adicional. Si hay un único candidato, la conexión puede hacerse
directamente contra él.

**Why this priority**: sin identificación por servicios el escáner actual da
falsos positivos (hoy un dispositivo ajeno con el mismo identificador de
fabricante se confundió con la cerradura) y obliga a conocer la MAC de antemano,
que en el transporte nativo de algunos sistemas ni siquiera está disponible.

**Independent Test**: con anuncios simulados (uno con nombre correcto, uno con
solo el fabricante correcto pero sin servicios, uno con los servicios correctos y
otro nombre, uno ajeno) el escaneo devuelve exactamente los candidatos U200 con
su motivo de identificación, y el filtro por MAC reduce la lista a uno.

**Acceptance Scenarios**:

1. **Given** una cerradura anunciándose y otros dispositivos alrededor, **When**
   el consumidor pide escanear, **Then** obtiene los candidatos que cumplen los
   criterios de identificación (nombre esperado, fabricante esperado o servicios
   esperados), cada uno con dirección, señal y el motivo por el que se le
   consideró candidato.
2. **Given** un dispositivo ajeno que comparte solo el identificador de
   fabricante y no anuncia nombre ni servicios de la cerradura, **When** se
   escanea, **Then** no se le trata como candidato preferente (nunca se conecta
   automáticamente a él si hay un candidato mejor).
3. **Given** el consumidor indica una MAC, **When** escanea o conecta, **Then**
   solo se considera el dispositivo con esa dirección.
4. **Given** ninguna cerradura anuncia durante el tiempo de escaneo, **When** el
   escaneo termina, **Then** la librería informa que no hubo candidatos y
   recuerda que la U200 solo anuncia tras activar su teclado.

---

### User Story 3 - Elegir el transporte (radio del sistema o controlador externo) sin cambiar el resto (Priority: P2)

Un consumidor en un portátil usa el Bluetooth del propio sistema; otro, en un
servidor sin Bluetooth o que necesita los primitivos de bajo nivel, conecta un
ESP32‑S3 por USB. Ambos usan la misma fachada: solo cambia el objeto de
transporte que le pasan. El transporte se encarga de escanear, conectar y
descubrir servicios a su manera; el resto del flujo es idéntico.

**Why this priority**: la portabilidad (macOS/Linux/Home Assistant vs.
controlador externo) es un objetivo declarado del proyecto y hoy la ruta nativa
solo existe como script suelto con un ajuste no empaquetado.

**Independent Test**: el mismo test de flujo pasa con el transporte nativo
simulado y con el transporte externo simulado; y contra hardware real, la
misma operación funciona con ambos transportes.

**Acceptance Scenarios**:

1. **Given** el consumidor elige el transporte nativo, **When** conecta,
   **Then** el descubrimiento de servicios se restringe a los servicios que la
   cerradura necesita, de forma que no falle en sistemas que rechazan
   descubrir descriptores de servicios ajenos.
2. **Given** el consumidor elige el transporte por controlador externo con un
   puerto, **When** conecta, **Then** el transporte abre el controlador, escanea
   o conecta por dirección, descubre servicios y características y entrega un
   cliente listo para la sesión.
3. **Given** falta la dependencia opcional del transporte elegido, **When** se
   intenta usar, **Then** el error indica claramente qué extra instalar.

---

### User Story 4 - Poner un ESP32‑S3 como controlador Bluetooth de forma reproducible (Priority: P3)

Un colaborador con un ESP32‑S3 quiere usarlo como controlador externo. Encuentra
en el repositorio el firmware, la receta para compilarlo y grabarlo, y la
verificación mínima de que el controlador responde, más el ejemplo único que usa
la fachada con ese transporte.

**Why this priority**: es lo que ha permitido hoy verificar la ruta de bajo nivel
(la única que expone todos los primitivos que la cerradura usa en el preámbulo);
si no se guarda, la próxima persona tiene que reinventarlo.

**Independent Test**: siguiendo la receta, un ESP32‑S3 recién borrado queda
como controlador y responde a la comprobación básica; el ejemplo único bloquea la
cerradura con él.

**Acceptance Scenarios**:

1. **Given** un ESP32‑S3 conectado por USB, **When** se sigue la receta,
   **Then** queda grabado y aparece como puerto serie que responde como
   controlador Bluetooth.
2. **Given** el firmware grabado, **When** se ejecuta el ejemplo único con la
   fachada y ese transporte, **Then** la operación llega hasta el final.

---

### Edge Cases

- El token expira entre la conexión BLE y la operación: la fachada reutiliza el
  mecanismo de reautenticación existente (renovar y reintentar una vez, nunca
  después de actuar).
- Credenciales incorrectas (`code 810`): error claro y no reintentable; nunca un
  bucle de login.
- La cerradura corta la conexión durante el descubrimiento (reconexión demasiado
  seguida): la fachada informa el fallo con la fase en la que ocurrió y no
  cuelga; el consumidor puede reintentar.
- Varios candidatos válidos y sin MAC: la fachada no elige a ciegas; expone la
  lista y requiere que el consumidor especifique (o conecta al único candidato
  con nombre y servicios correctos si es exactamente uno).
- Operación pedida sobre un cliente ya desconectado: error explícito, sin
  reconexión silenciosa (el consumidor decide).
- Dos operaciones concurrentes sobre el mismo cliente: se rechaza la segunda con
  el error de operación en curso ya existente.
- Ningún secreto (contraseña, token, clave de sesión) aparece en logs ni en
  representaciones textuales del cliente.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: La librería MUST exponer una única fachada de cliente que, a partir
  de un proveedor de autenticación de cuenta (usuario + contraseña; el existente
  de la feature 014) y un transporte, realice el flujo completo: login → escaneo
  e identificación (o conexión directa por dirección) → conexión → descubrimiento
  → operación.
- **FR-002**: La fachada MUST reutilizar el mecanismo de reautenticación existente
  (renovar el token expirado y reintentar una vez antes de actuar; nunca reintentar
  credenciales incorrectas ni tras actuar).
- **FR-003**: La librería MUST ofrecer un escaneo que **devuelva** candidatos (no
  solo los imprima), identificando la cerradura por: nombre anunciado esperado,
  identificador de fabricante esperado y/o servicios anunciados esperados; cada
  candidato MUST incluir dirección, intensidad de señal y el/los motivos de
  identificación.
- **FR-004**: El escaneo MUST aceptar una dirección MAC opcional como filtro
  exclusivo, y un tiempo máximo de escaneo.
- **FR-005**: La fachada MUST priorizar como candidato preferente el que cumpla
  nombre y/o servicios sobre el que solo cumpla fabricante; con más de un
  candidato igual de bueno y sin MAC MUST negarse a elegir y devolver la lista.
- **FR-006**: La librería MUST ofrecer una abstracción de transporte con dos
  implementaciones empaquetadas — Bluetooth nativo del sistema y controlador
  externo por puerto — cada una responsable de escanear, conectar y descubrir
  servicios/características, entregando un cliente compatible con la sesión
  existente.
- **FR-007**: El transporte nativo MUST restringir el descubrimiento a los
  servicios de la cerradura para funcionar en sistemas cuyo stack rechaza
  descubrir descriptores de otros servicios.
- **FR-008**: Cada transporte MUST fallar con un mensaje que indique el extra a
  instalar cuando falte su dependencia opcional.
- **FR-009**: La fachada MUST exponer `lock` y `unlock` como métodos directos y
  el resto de operaciones del catálogo por nombre, todas sobre la misma conexión
  y sesión, y devolver la respuesta de la cerradura (o su ausencia).
- **FR-010**: La fachada MUST poder cerrarse de forma limpia (desconectar y
  liberar el transporte), también como gestor de contexto asíncrono, y acotar con
  tiempo cada fase para no colgar nunca al consumidor.
- **FR-011**: Los errores de la fachada MUST indicar la fase (login, escaneo,
  conexión, descubrimiento, operación) en la que se produjeron.
- **FR-012**: La fachada y los transportes MUST NOT registrar ni exponer secretos
  (contraseña, token, clave de sesión, nonce) en logs o `repr`.
- **FR-013**: El repositorio MUST incluir en `tools/` el firmware que convierte un
  ESP32‑S3 en controlador Bluetooth externo por USB (fuente, configuración y
  receta de compilación/grabado/verificación), sin binarios ni secretos.
- **FR-014**: `examples/` MUST quedar con un único runner de flujo real que use la
  fachada (elección de transporte por configuración), reemplazando los runners
  cableados a mano; `tools/bumble_lock.py` MUST delegar en la fachada o
  retirarse en favor de ese ejemplo.
- **FR-015**: El comportamiento de protocolo (tramas, CRC, cifrado, orden de
  CCCD, preámbulo) MUST permanecer byte a byte igual: la fachada solo compone
  piezas existentes.
- **FR-016**: La documentación de entrada (README, docs de validación) MUST
  presentar la fachada como la forma recomendada de uso, con el ejemplo de tres
  líneas.

### Key Entities *(include if feature involves data)*

- **Cliente U200 (fachada)**: objeto conectado a una cerradura concreta; conoce su
  proveedor de auth, su transporte y su conexión activa; expone operaciones y
  cierre.
- **Candidato de escaneo**: dispositivo visto por el aire que parece una U200:
  dirección, nombre anunciado, señal, servicios anunciados y motivos de
  identificación.
- **Transporte**: la radio elegida (nativa o controlador externo por puerto);
  sabe escanear, conectar a un candidato/dirección y descubrir servicios,
  entregando el cliente GATT que consume la sesión.
- **Fase de flujo**: login, escaneo, conexión, descubrimiento, operación — usada
  para acotar tiempos y para etiquetar errores.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un consumidor bloquea la cerradura con **≤ 5 líneas** de código
  (crear auth, elegir transporte, conectar, `lock`, cerrar), sin conocer tramas,
  UUIDs, tokens ni handles.
- **SC-002**: Contra hardware real, el flujo completo (login incluido) termina en
  **≤ 30 s** en cada transporte, y en **≤ 15 s** en operaciones sucesivas sobre
  la misma conexión.
- **SC-003**: El escaneo identifica la cerradura real como candidato preferente y
  **no** conecta a dispositivos ajenos que solo comparten identificador de
  fabricante (0 falsos positivos en el conjunto de anuncios de prueba).
- **SC-004**: El mismo conjunto de tests de flujo pasa con ambos transportes
  simulados; la suite completa sigue en verde y ningún test de protocolo cambia.
- **SC-005**: Un colaborador con un ESP32‑S3 lo deja como controlador y ejecuta el
  ejemplo único siguiendo solo la receta del repositorio, sin ayuda externa.
- **SC-006**: `examples/` queda con un solo runner real y ningún runner del repo
  cablea el flujo a mano.

## Assumptions

- Las credenciales (cuenta, contraseña, appid/appkey, client/phone id) siguen
  siendo inyectadas por el consumidor; la librería no lee `.env` (los ejemplos sí,
  como hasta ahora).
- La cerradura anuncia solo tras activar su teclado; el escaneo tiene un tiempo
  máximo por defecto razonable (~30 s) y lo comunica al fallar.
- La identificación por servicios usa los servicios ya catalogados de la U200
  (auth `fcb9`, control `ff60`, auxiliar `ff90`); si el anuncio no incluye
  servicios, bastan nombre y/o fabricante.
- El transporte nativo puede no exponer la MAC real (identificadores del
  sistema); en ese caso el filtro por MAC no aplica y se identifica por anuncio.
- El firmware del ESP32‑S3 se guarda como fuente y receta (compilable con el
  ESP‑IDF que ya usa el proyecto vecino); no se versionan binarios.
- Los primitivos de bajo nivel (MTU, Read‑By‑Type, connection update) siguen
  siendo best‑effort: presentes con el controlador externo, omitidos con el
  nativo, como hoy.
