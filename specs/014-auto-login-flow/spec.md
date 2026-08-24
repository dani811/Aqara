# Feature Specification: Encaje del login autónomo en el flujo (auto-login + auto-refresh de token)

**Feature Branch**: `feature/014-auto-login-flow`

**Created**: 2026-08-15

**Status**: Draft

**Input**: User description: "Encaje del login autónomo en el flujo de operación. La librería debe autenticar contra el cloud de Aqara de forma autónoma y no interactiva; si el token no es válido (expirado/inválido) obtiene uno nuevo con login (cuenta+contraseña) y reintenta. Hoy existe CloudAuthManager pero no está enganchado a run_authenticated_lock_operation, que usa un token estático y falla (code 108) al caducar. Sin login no hay librería; bloquea y precede a multi-dispositivo."

## Overview

La librería ya sabe hacer login (`kdf.login`) y ya tiene un gestor de token con
renovación (`CloudAuthManager`: `get_token`, `handle_expired_token`, `from_env`),
pero **ese gestor no está conectado al flujo de operación**. Hoy
`run_authenticated_lock_operation` recibe un `signer` construido con un **token
estático**: cuando ese token caduca, el cloud responde `code 108` ("Token has
expired") y la operación **falla** en lugar de renovarlo.

El resultado práctico es que la librería no es autónoma: obliga a capturar y pegar
un token a mano cada vez que expira (y Aqara lo invalida en cuanto la cuenta entra
desde otro sitio). Para una integración headless como Home Assistant eso no sirve.

Esta feature es el **encaje del login en el flujo**: que a partir de las
credenciales de cuenta la librería obtenga un token válido por sí misma, lo use en
las llamadas cloud, y cuando detecte un token expirado durante una operación haga
login y **reintente automáticamente una vez** — todo sin intervención manual y sin
filtrar secretos. Distinguiendo con claridad el token-expirado (renovable) de las
credenciales-incorrectas (no renovable) para no entrar en bucles de login.

**Sin login autónomo no hay librería usable**: esta feature bloquea y **precede** a
la conversión multi-dispositivo. Cuando funcione end-to-end contra un cerrojo real
será el hito para publicar release y versión oficial.

## Clarifications

### Session 2026-08-15

- Q: ¿Qué hace la 014 con lo que no es librería (from_env, CLI, PoCs)? → A:
  **Purificar y reubicar ahora**. El paquete `aqara_ble/` queda puro
  (credenciales inyectadas); como parte de esta feature, `from_env` sale del
  paquete y `refresh_token.py` + `poc_*.py` se mueven a `examples/` (o `tools/`).
- Q: ¿Cómo recibe el flujo las credenciales del consumidor? → A: mediante un
  **proveedor de auth** (`CloudAuthManager`) ya construido por el consumidor;
  `run_authenticated_lock_operation` le pide token y le pide refrescar.
- Q: Al expirar el token (108) a mitad de operación, ¿qué se reintenta? → A:
  **reautenticar y re-ejecutar la operación entera** una vez con token nuevo.
- Q: ¿El reintento aplica a operaciones que ya movieron el cerrojo? → A: **solo
  antes de actuar**: reintentar únicamente si el 108 ocurre en fase cloud **antes**
  de enviar el comando de control; si ya se actuó, no reintentar (evitar doble
  apertura/cierre).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Operar solo con credenciales de cuenta, sin gestionar tokens (Priority: P1)

Un desarrollador (o la integración de Home Assistant) configura únicamente sus
credenciales de cuenta (cuenta, contraseña y los identificadores de app) y lanza
una operación. La librería obtiene un token válido por sí misma (login) y completa
el flujo, sin que nadie tenga que capturar ni pegar un token.

**Why this priority**: Es el objetivo declarado; sin esto la librería no es
autónoma y no sirve para HA.

**Independent Test**: Con solo credenciales de cuenta (sin token pre-provisto) y un
cloud simulado, una operación autenticada completa el flujo obteniendo el token
automáticamente.

**Acceptance Scenarios**:

1. **Given** credenciales de cuenta válidas y **ningún** token provisto, **When**
   se lanza una operación autenticada, **Then** la librería hace login, usa el
   token obtenido en las llamadas cloud y completa el flujo.
2. **Given** un token válido ya en caché, **When** se lanzan varias operaciones,
   **Then** la librería reutiliza ese token sin volver a hacer login.

---

### User Story 2 - Renovación transparente cuando el token expira (Priority: P1)

Durante una operación, el token caduca y el cloud responde `code 108`. La librería
hace login para obtener un token nuevo y **re-ejecuta la operación entera** una vez,
de modo que tiene éxito sin que el usuario note nada ni tenga que reintentar a mano
— siempre que aún no se haya enviado el comando actuador.

**Why this priority**: Es el corazón del "encaje": el caso que hoy falla. "Login si
token no válido, nuevo token con login."

**Independent Test**: Con un cloud simulado que responde `108` la primera vez y OK
tras un login, la operación tiene éxito tras exactamente una reautenticación +
re-ejecución.

**Acceptance Scenarios**:

1. **Given** un token que el cloud rechaza con `108` en fase cloud (antes de
   actuar), **When** ocurre durante el flujo, **Then** la librería renueva el token
   con login y re-ejecuta la operación una vez, completándola.
2. **Given** que el reintento tras renovar el token **también** falla, **When** se
   agota el único reintento, **Then** la operación falla con un error claro y **no**
   entra en un bucle de logins.

---

### User Story 3 - Fallo claro y sin bucles con credenciales inválidas (Priority: P2)

Si las credenciales son incorrectas o la cuenta no está registrada, el cloud
responde `code 810`. La librería **no** debe tratar eso como "token expirado" ni
reintentar login en bucle: falla de inmediato con un mensaje que nombra la causa
(contraseña incorrecta o cuenta no registrada).

**Why this priority**: Evita bucles de login y mensajes engañosos; `810` es
ambiguo por diseño y no se resuelve reintentando.

**Independent Test**: Con un cloud simulado que responde `810`, el flujo falla sin
realizar reintentos de login y el error nombra la causa.

**Acceptance Scenarios**:

1. **Given** credenciales incorrectas (o cuenta no registrada), **When** la
   librería intenta login, **Then** falla sin reintentar y el error distingue
   "credenciales/cuenta" de "token expirado".

---

### User Story 4 - No interactivo y seguro para Home Assistant (Priority: P2)

La integración se ejecuta headless: la librería nunca pide nada por consola, carga
las credenciales del entorno, y ningún secreto (token, contraseña, material de
sesión) aparece en los logs.

**Why this priority**: Requisito para HA y para la higiene de secretos (Principio
I); si la librería pidiera input o filtrara secretos, no sería usable/segura en
producción.

**Independent Test**: Ninguna ruta del flujo invoca lectura interactiva; con logs a
nivel DEBUG, ningún secreto aparece en la salida, ni en éxito ni en fallo.

**Acceptance Scenarios**:

1. **Given** el flujo completo (incluido login y refresh), **When** se ejecuta con
   logging DEBUG, **Then** no aparece ningún secreto en los logs.
2. **Given** faltan credenciales requeridas al inicializar la autenticación,
   **When** se construye el gestor, **Then** falla con un error claro **antes** de
   tocar el radio o la red, nombrando qué credencial falta.

---

### Edge Cases

- **Expiración a mitad de handshake**: el token caduca entre la llamada de clave
  pública y la de verify (ambas antes de actuar) → se renueva el token y se
  **re-ejecuta la operación entera** una vez con el token nuevo.
- **Expiración tras actuar**: si el `108` llegara después de despachar el comando
  actuador → **no** se reintenta (evitar doble apertura/cierre); se reporta el
  resultado/estado real.
- **Login OK pero el cloud sigue rechazando**: tras renovar el token el reintento
  vuelve a fallar → se falla tras el único reintento, sin bucle.
- **Credencial ausente**: falta cuenta/contraseña/appid… en el entorno → error
  claro al construir el gestor de autenticación, antes de cualquier I/O.
- **Distinción de códigos**: `108` (renovable) vs `810` (no renovable) vs otros
  códigos de servicio (tratados como fallo no renovable, sin login-retry).
- **Concurrencia**: si dos operaciones sobre el mismo dispositivo coinciden, la
  renovación de token no debe romper el control de concurrencia por-dispositivo ya
  existente.
- **Compatibilidad**: quien ya pasa un token/`signer` explícito debe poder seguir
  haciéndolo sin login automático.

## Requirements *(mandatory)*

### Functional Requirements

**Autenticación autónoma**

- **FR-001**: La librería MUST poder ejecutar una operación autenticada a partir de
  **credenciales de cuenta** (cuenta, contraseña, appid, appkey, client_id,
  phone_id, region) **sin** requerir un token pre-capturado.
- **FR-002**: Antes de las llamadas cloud, la librería MUST asegurar un token
  válido automáticamente: si no hay token en caché, hace login; si lo hay, lo
  reutiliza.
- **FR-009**: El token MUST vivir **solo en memoria** dentro del gestor de
  autenticación durante la vida del proceso: se obtiene por login, se cachea y se
  reutiliza, y se renueva (en memoria) al expirar o si se fuerza. La librería MUST
  NOT **persistir el token en disco** (ni en `.env` ni en ningún fichero).
- **FR-013**: El camino autónomo de la librería deriva el token de las credenciales
  recibidas y no depende de un token pre-provisto. La entrada `AQARA_TOKEN` (y la
  utilidad CLI que lo reescribe) queda como bootstrap **legacy/opcional**, ajeno al
  camino de producción.

**Renovación y reintento**

- **FR-003**: Si una llamada cloud falla por token expirado/inválido (`code 108`),
  la librería MUST renovar el token mediante login y **re-ejecutar la operación
  entera** (incluido el handshake) una vez con el token nuevo.
- **FR-004**: La reautenticación por token expirado MUST limitarse a **una vez** por
  operación; si el reintento también falla, MUST propagarse un error claro sin más
  reintentos (sin bucles).
- **FR-016**: El reintento por token expirado MUST aplicarse **solo antes de
  actuar**: únicamente si el `108` ocurre en fase cloud **antes** de enviar el
  comando de control. Si el comando actuador (p.ej. abrir/cerrar) ya se ha
  despachado, la librería MUST NOT reintentar, para no provocar una doble
  actuación del cerrojo.
- **FR-005**: La librería MUST distinguir token-expirado (`108`, renovable) de
  credenciales-incorrectas/cuenta-no-registrada (`810`, no renovable) y MUST NOT
  intentar login-retry ante `810` u otros códigos no renovables; el error MUST
  nombrar la causa probable.

**No interactivo y seguro**

- **FR-006**: El flujo MUST ser **no interactivo**: ninguna ruta MUST leer de
  consola (sin prompts/`input`/`getpass`), para servir a ejecución headless / Home
  Assistant.
- **FR-007**: La librería MUST recibir las credenciales (incluida la **contraseña**)
  **por su API**, inyectadas por el consumidor en runtime. La librería MUST NOT
  **persistir** credenciales ni token, ni exigir leerlas de ningún fichero: el
  almacenamiento seguro es responsabilidad del consumidor (en Home Assistant, el
  *config entry* de HA). Los secretos MUST NOT aparecer en código ni en commits
  (Principio I).
- **FR-014**: El paquete `aqara_ble/` MUST quedar **puro**: sin utilidades que
  no sean librería. La conveniencia de carga de credenciales (`from_env`) y las
  utilidades CLI/PoC (`refresh_token.py`, `poc_*.py`, runners) MUST vivir **fuera**
  del paquete (en `examples/` o `tools/`). Como parte de esta feature MUST
  reubicarse allí lo que hoy esté dentro o mezclado. La librería MUST funcionar sin
  esas conveniencias (credenciales inyectadas directamente).
- **FR-008**: Ningún secreto (token, contraseña, material de sesión, credenciales)
  MUST aparecer en logs, en ningún camino (éxito o fallo), reutilizando la
  disciplina de logging con lista blanca de la feature 012.

**Integración y compatibilidad**

- **FR-010**: La integración MUST mantener compatible el flujo existente: un
  consumidor que aporte un token/`signer` explícito MUST poder seguir operando sin
  login automático.
- **FR-015**: El flujo de operación autenticada MUST aceptar un **proveedor de
  auth** (`CloudAuthManager`) construido por el consumidor con sus credenciales; el
  flujo le solicita el token y le solicita la renovación. El proveedor de auth es
  el mecanismo por el que el token entra y se refresca en el flujo.
- **FR-011**: La obtención/renovación de token (I/O de red) MUST ser segura para
  asyncio: ejecutarse sin bloquear el event loop, coherente con la feature 012.

**Verificación**

- **FR-012**: MUST existir pruebas, sin I/O real (simulando el cloud), que
  verifiquen: (a) sin token → login → opera; (b) token expira en fase cloud →
  reautenticación + re-ejecución con éxito; (c) `810` → falla sin login-retry; (d)
  ningún secreto en logs; (e) el camino con token/`signer` explícito sigue verde;
  (f) idempotencia: un `108` tras despachar el actuador **no** dispara reintento.

### Key Entities

- **Gestor de autenticación** (`CloudAuthManager`, ya existente): mantiene las
  credenciales, obtiene/renueva el token vía login, cachea el token válido.
- **Token**: JWT de sesión cloud; de vida corta; se invalida al iniciar sesión en
  otro sitio; renovable con login. **Vive solo en memoria** (no se persiste): se
  deriva de las credenciales al arrancar y se renueva en memoria al caducar.
- **Credenciales de cuenta**: cuenta, contraseña, appid, appkey, client_id,
  phone_id, region; secretos **inyectados por el consumidor** en runtime; la
  librería no los persiste. Su almacenamiento seguro lo posee el consumidor (en HA,
  el config entry).
- **Signer**: función que firma las peticiones cloud con el token vigente; debe
  reflejar el token renovado tras un refresh.
- **Códigos de servicio**: `108` (token expirado, renovable), `810` (credencial
  incorrecta / cuenta no registrada, no renovable), otros (fallo no renovable).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Partiendo **solo** de credenciales de cuenta (sin token), una
  operación autenticada completa el flujo (cloud simulado) sin que el desarrollador
  aporte ningún token.
- **SC-002**: Cuando el token expira (`108`) en fase cloud, la operación tiene éxito
  tras **exactamente una** reautenticación + re-ejecución de la operación (cloud
  simulado).
- **SC-003**: Con credenciales inválidas (`810`), la operación falla con **cero**
  reintentos de login y un error que nombra la causa.
- **SC-004**: En todos los caminos (éxito y fallo), una revisión de los logs a
  nivel DEBUG arroja **cero** secretos.
- **SC-005**: El camino con token/`signer` explícito sigue funcionando (los tests
  existentes del flujo permanecen verdes).
- **SC-006**: Ninguna ruta del flujo invoca lectura interactiva (sin
  `input`/`getpass`), verificable de forma estática.
- **SC-007**: El paquete `aqara_ble/` no contiene utilidades no-librería: no
  hay CLI/PoC ni carga de `.env`/`from_env` dentro del paquete; esas piezas viven
  en `examples/`/`tools/`.
- **SC-008**: Si el token expira **después** de despachar el comando actuador, la
  librería **no** reintenta (cero dobles aperturas/cierres en el test de
  idempotencia).

## Assumptions

- **La librería no persiste secretos.** Recibe las credenciales por su API y
  mantiene el token solo en memoria. El almacenamiento seguro de las credenciales
  es del consumidor: en Home Assistant, el *config entry* (HA las cifra/gestiona);
  en desarrollo/CLI, un `.env` git-ignored vía el ayudante opcional `from_env`.
- Coexistencia con el modelo legacy: `AQARA_TOKEN` en `.env` y la utilidad CLI
  `refresh_token.py` (que reescribe el token en `.env`) se mantienen como bootstrap
  manual/opcional, **fuera** del camino autónomo de la librería.
- El cloud devuelve `code 108` para token expirado y `code 810` para
  credencial-incorrecta/cuenta-no-registrada (observado en la ingeniería inversa);
  otros códigos se tratan como fallo no renovable.
- Solo la región EU está confirmada.
- Esta feature **reutiliza** `CloudAuthManager` y `kdf.login` existentes; no
  reescribe la criptografía de login (Principio II) — solo la **encaja** en el
  flujo de operación.
- El alcance es el encaje del login en el flujo **y** la purificación del paquete
  (reubicar `from_env`, CLI y PoCs a `examples/`/`tools/`); **no** incluye la
  conversión multi-dispositivo (spec posterior).
- El trabajo se realiza en `feature/014-auto-login-flow` (Principio VI); las
  pruebas no hacen I/O de red ni de radio (Principio V).
