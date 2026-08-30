# Feature Specification: Contraseña sin conexión (códigos cloud del U200)

**Feature Branch**: `feat/038-offline-password-cloud`

**Created**: 2026-08-30

**Status**: Draft

**Input**: User description: "Implement fetching Aqara U200 'offline password' (Contraseña sin conexión) codes via the cloud API, in aqara_ble. Confirmed this session (docs/devices/u200/operations.md): the codes are NOT computed locally — the Aqara cloud server pre-generates a batch of 8 six-digit one-time codes per 10-minute UTC-epoch-aligned window and hands them back via an authenticated HTTPS call, `GET /app/v1.0/lumi/dev/bluetooth/lock/passwd`, using the same header/signing scheme already implemented and proven byte-identical to the official app (specs/037-cloud-session-mitm). Add a cloud-client method to aqara_ble that calls this endpoint and returns the available codes + their validity window, without any BLE connection to the lock. The exact query parameters/headers weren't fully recovered byte-for-byte (mid-connection HPACK desync during capture) — needs a live-capture verification step."

## Overview

"Contraseña sin conexión" (offline password) es la función de la app que genera
un código numérico de un solo uso, pensado para dar acceso puntual a alguien sin
compartir una contraseña permanente ni requerir que el teléfono de esa persona
esté emparejado por Bluetooth con la cerradura. Tres sesiones de ingeniería
inversa asumieron que el código se calculaba localmente en el teléfono a partir
de una semilla por cerradura (como sugiere la patente de Aqara, US11120656B2) y
buscaron esa semilla sin éxito, primero de forma estática (decompilando la app) y
luego enganchando en vivo toda primitiva de cifrado accesible en el proceso de la
app — con resultado negativo limpio en ambos casos.

Esta sesión encontró la explicación real: **el código no se calcula en el
teléfono, lo genera el servidor cloud de Aqara** y el teléfono simplemente lo
pide por HTTPS. Confirmado con captura de tráfico en vivo (ver
`docs/devices/u200/operations.md`, sección "2026-08-30 (resolved)"): la
respuesta del servidor contiene exactamente los mismos códigos que la app
mostró en pantalla en ese instante. Esto **cierra el bloqueo histórico**: no
hace falta ninguna semilla ni ningún algoritmo — es una llamada cloud
autenticada más, del mismo tipo que la librería ya sabe hacer para el login y
la lectura de ajustes.

Esta feature añade esa llamada a `aqara_ble` como un método del cliente cloud,
reutilizando el esquema de firma/cabeceras ya implementado (y ya demostrado
idéntico al de la app oficial). El resultado es una función que **no requiere
conexión BLE con la cerradura en absoluto** — coherente con el propio nombre de
la función ("sin conexión"): funciona incluso sin Bluetooth ni hub, porque tanto
el teléfono como la cerradura ya comparten el mismo servidor cloud como fuente
de verdad.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Obtener un código de un solo uso sin BLE (Priority: P1)

Un consumidor de la librería (p. ej. la integración de Home Assistant) pide un
código de acceso temporal para la cerradura sin necesitar una sesión BLE activa
ni que el usuario esté físicamente cerca del dispositivo.

**Why this priority**: es la funcionalidad completa que un usuario final
reconoce como "Contraseña sin conexión" en la app — sin esto, la feature no
existe.

**Independent Test**: con un cliente cloud simulado (fake HTTP) que responde con
el JSON real capturado (`{"result":{"passwd":["651399","637408",...]},"code":0,
...}`), el nuevo método devuelve la lista de códigos disponibles sin abrir
ninguna conexión BLE.

**Acceptance Scenarios**:

1. **Given** una sesión cloud autenticada (login ya realizado), **When** se
   llama al nuevo método, **Then** se hace una petición GET autenticada al
   endpoint de contraseñas del dispositivo y se devuelven los códigos de la
   respuesta, sin ningún intento de conexión BLE.
2. **Given** una respuesta con varios códigos pendientes en la ventana actual,
   **When** se piden, **Then** la librería expone todos los códigos disponibles
   (no solo el primero) junto con la ventana de validez (inicio/fin).
3. **Given** el servidor no tiene códigos pendientes para la ventana actual,
   **When** se piden, **Then** la librería devuelve una lista vacía, no un error.

### User Story 2 - Consultar el historial de códigos ya emitidos (Priority: P2)

Un consumidor quiere saber qué códigos se han emitido y en qué ventana de
tiempo, para poder invalidar/auditar accesos temporales.

**Why this priority**: útil para trazabilidad, pero no bloquea el caso de uso
principal (obtener un código nuevo).

**Independent Test**: con el mismo fake HTTP respondiendo al endpoint de
histórico (`.../password/log/query`) con el JSON real capturado
(`{"result":[{"createTime","startTime","endTime","did"},...]}`), el método
devuelve las entradas con sus tres marcas de tiempo.

**Acceptance Scenarios**:

1. **Given** un rango de tiempo, **When** se consulta el historial, **Then** se
   devuelven las entradas emitidas en ese rango con `createTime`/`startTime`/
   `endTime`.

### User Story 3 - Verificar en vivo la petición exacta (Priority: P3)

Antes de confiar en la implementación contra la cerradura real del
mantenedor, hace falta confirmar que la petición que construye la librería es
la misma, byte a byte, que la que envía la app — ya que la captura de esta
sesión no recuperó todas las cabeceras/parámetros exactos (tabla HPACK
desincronizada a mitad de conexión).

**Why this priority**: reduce el riesgo de que la implementación "funcione a
medias" (p. ej. falte un parámetro y el servidor devuelva un error genérico o
una lista vacía en vez de fallar claramente).

**Independent Test**: con la variable de entorno/flag de depuración activada,
la librería imprime/loguea el método, ruta y cabeceras exactas de la petición
saliente (sin loguear el token en claro) antes de enviarla, para poder
compararla con una captura simultánea del tráfico de la app real.

**Acceptance Scenarios**:

1. **Given** el modo de depuración activado, **When** se llama al nuevo
   método, **Then** se registra la petición completa (método, ruta, query,
   cabeceras no sensibles) antes de enviarla.

### Edge Cases

- El servidor devuelve `code != 0` (error de la API cloud, p. ej. sesión
  caducada): el método MUST propagar un error claro, no devolver una lista
  vacía silenciosa que se confunda con "no hay códigos pendientes".
- Se piden códigos justo en el borde de una ventana de 10 minutos: la
  librería no debe intentar "corregir" ni interpretar el `did`/ventana —
  simplemente refleja lo que el servidor devuelve.
- Sin conectividad de red: el método MUST fallar con un error de red claro,
  distinguible de un error de la API.
- El endpoint exacto (parámetros de query, si `did` va en la URL o en
  cabecera) no está confirmado byte a byte todavía — ver User Story 3. La
  implementación MUST poder validarse/corregirse con una única captura en
  vivo sin rediseñar la interfaz pública del método.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: La librería MUST exponer un método del cliente cloud (p. ej.
  `fetch_offline_passwords(device_id)`) que obtiene los códigos de un solo uso
  pendientes para la cerradura indicada, sin abrir ninguna conexión BLE.
- **FR-002**: La petición MUST reutilizar el esquema de autenticación/firma de
  petición ya implementado en la librería (mismas cabeceras `lang/cuty/
  app-version/phone-model/time/sys-type/sys-version/nonce/phoneid/area/appid/
  clientid/userid/token/sign`), no un mecanismo nuevo.
- **FR-003**: El método MUST devolver, por cada código disponible, al menos el
  código de 6 dígitos y la ventana de validez asociada (inicio/fin), tal como
  los expone la respuesta del servidor — sin inventar ni derivar campos que el
  servidor no proporcione.
- **FR-004**: La librería MUST exponer un segundo método (o el mismo con un
  parámetro de rango) para consultar el histórico de códigos ya emitidos
  (`createTime`/`startTime`/`endTime`/`did`), replicando el endpoint hermano de
  histórico ya observado.
- **FR-005**: Ante una respuesta con `code != 0`, el método MUST lanzar/propagar
  un error identificable (no devolver una lista vacía indistinguible de "sin
  códigos pendientes").
- **FR-006**: MUST NOT requerir ni intentar una conexión BLE/GATT en ningún
  punto de este flujo — es puramente un método del cliente cloud.
- **FR-007**: La librería MUST ofrecer una forma de inspeccionar la petición
  saliente exacta (método, ruta, query, cabeceras no sensibles) en modo debug,
  para poder validarla contra una captura en vivo de la app real y corregir
  cualquier parámetro que la captura de esta sesión no haya recuperado.
- **FR-008**: MUST NOT loguear el token de sesión ni el `sign` en claro, ni en
  modo debug.
- **FR-009**: La documentación (`docs/devices/u200/operations.md` y/o un nuevo
  doc de referencia cloud) MUST registrar el endpoint, la forma de la
  respuesta, y el resultado de la verificación en vivo (FR-007) una vez hecha.

### Key Entities

- **OfflinePasswordCode**: un código de un solo uso — valor de 6 dígitos,
  inicio y fin de la ventana de validez de 10 minutos en la que el servidor lo
  generó.
- **OfflinePasswordLogEntry**: una entrada de histórico — `createTime`,
  `startTime`, `endTime`, `did` del dispositivo, tal como la devuelve el
  endpoint de histórico.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Contra un cliente HTTP simulado con las respuestas reales
  capturadas esta sesión, el nuevo método devuelve exactamente los códigos y
  ventanas de esas respuestas, sin conexión BLE alguna (verificable en la
  suite de tests, sin hardware).
- **SC-002**: Con hardware real (la cerradura y cuenta del mantenedor), una
  llamada al método en modo debug produce una petición cuya ruta, método y
  cabeceras no sensibles coinciden con una captura simultánea del tráfico real
  de la app (validación de la User Story 3).
- **SC-003**: Con hardware real, el método devuelve al menos un código válido
  que, introducido en el teclado físico de la cerradura, la abre — o si no se
  prueba físicamente por seguridad, que coincide exactamente con un código
  visible simultáneamente en la app.
- **SC-004**: La suite de tests existente sigue en verde; ningún test de
  protocolo BLE/framing cambia (esta feature no toca esa capa).

## Assumptions

- La cuenta/credenciales ya configuradas en `.env` tienen permiso para leer los
  códigos de la cerradura del mantenedor (mismo nivel de acceso que la app).
- El host y la región (`rpc-<region>.aqara.com`) son los mismos que ya usa el
  resto del cliente cloud de la librería.
- El `did` (device id, formato `matt.<hex>`) necesario para la petición ya es
  obtenible por la librería (se usa en otros flujos existentes) o se puede
  derivar de la configuración de dispositivo ya presente.
- Los parámetros exactos de la petición (si `did`/ventana de tiempo van en
  query string o en cabecera) pueden requerir un ajuste tras la verificación en
  vivo (User Story 3) sin que eso cambie la interfaz pública del método.
- Fuera de alcance de esta feature: crear/gestionar usuarios ("Gestión de
  usuarios" queda explícitamente fuera, por la regla del proyecto de no tocarla
  en la cerradura real), y "Contraseña programada remota" (bloqueada por un
  Matter Controller, feature distinta ya documentada como fuera de alcance).
