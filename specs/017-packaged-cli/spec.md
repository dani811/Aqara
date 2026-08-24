# Feature Specification: CLI empaquetado, fino sobre la API de la librería

**Feature Branch**: `feature/017-packaged-cli`

**Created**: 2026-08-17

**Status**: Draft

**Input**: "La librería debe ser un CLI, abstracto de la lógica para que otras integraciones se acoplen fácilmente." Un comando `aqara` instalado con el paquete, que sea una capa **fina** sobre la API pública (`U200Client`, transportes, `scan`, `CloudAuthManager`) sin lógica propia; toda la lógica vive en la librería, que es la superficie de acoplamiento para integraciones (Home Assistant, etc.). Hoy el único runner es `examples/lock_cli.py`, fuera del paquete y no instalable como comando.

## Overview

Hoy operar la cerradura desde la terminal exige `python examples/lock_cli.py …`
(un script fuera del paquete, no instalado). Y aunque la librería ya expone una
API limpia (`U200Client`, `BleakTransport`/`BumbleTransport`, `scan`,
`CloudAuthManager`), no hay un **comando** que la acompañe ni una frontera
explícita "CLI = adaptador fino / librería = lógica".

Esta feature empaqueta un **CLI `aqara`** instalado con el paquete
(`pip install` → comando en el PATH) que es un **adaptador delgado**: parsea
argumentos, carga credenciales (de flags o del entorno/`.env`, porque la
librería nunca lee el entorno), construye los objetos de la API y llama a sus
métodos, e imprime. **Ninguna decisión de protocolo, red o BLE vive en el CLI**;
todo está en la librería, de modo que cualquier integración se acopla importando
la misma API que usa el CLI, sin copiar cableado.

Invariante clave: `import aqara_ble` sigue siendo **puro** (sin leer
entorno, argv ni stdout); el módulo del CLI es un consumidor que solo se carga al
ejecutar el comando, no al importar la librería.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Operar la cerradura con el comando `aqara` (Priority: P1)

Tras instalar el paquete, un usuario ejecuta `aqara lock` / `aqara unlock` /
`aqara scan` / `aqara operate <op>` / `aqara login` desde cualquier directorio,
eligiendo transporte con `--transport bleak|bumble`. El comando hace login,
escaneo, conexión y operación a través de la librería.

**Why this priority**: es el objetivo — que la librería *sea* un CLI instalable.

**Independent Test**: `aqara --help` y cada subcomando existen tras
`pip install -e .`; con la API simulada (transporte/nube fake) el subcomando
invoca los métodos correctos de la API y devuelve el código de salida esperado,
sin lógica de protocolo en el CLI.

**Acceptance Scenarios**:

1. **Given** el paquete instalado, **When** el usuario ejecuta `aqara lock`,
   **Then** el comando construye `CloudAuthManager` + transporte + `U200Client`
   y llama `lock()`, imprimiendo el resultado y saliendo con 0 en éxito.
2. **Given** `aqara scan`, **When** se ejecuta, **Then** imprime los candidatos
   con nombre/modelo/razones que devuelve `scan()` (sin decidir nada por su
   cuenta).
3. **Given** faltan credenciales, **When** se ejecuta una operación, **Then**
   sale con un código de configuración claro y un mensaje que dice qué falta,
   sin imprimir secretos.
4. **Given** un fallo de una fase (login/scan/connect/operation), **When**
   ocurre, **Then** el CLI reporta la fase (de `U200ClientError.phase`) y un
   código de salida distinto por clase de error.

### User Story 2 - La librería es la superficie de acoplamiento; el CLI no tiene lógica (Priority: P1)

Un integrador (p. ej. Home Assistant) se acopla **importando la librería**
(`U200Client`, transportes, `scan`, `CloudAuthManager`) — exactamente lo que usa
el CLI — sin depender del CLI ni reimplementar cableado. Importar la librería no
arrastra el CLI ni lee el entorno.

**Why this priority**: "abstracto de la lógica para que otras integraciones se
acoplen fácilmente" es el requisito explícito.

**Independent Test**: `import aqara_ble` no importa el módulo del CLI ni
`argparse`, y no lee variables de entorno; el módulo del CLI no define ninguna
lógica de protocolo/red/BLE (solo parseo, carga de credenciales, llamadas a la
API e impresión).

**Acceptance Scenarios**:

1. **Given** `import aqara_ble`, **When** se importa, **Then** `aqara_ble.cli`
   no está entre los módulos cargados y no se ha leído el entorno.
2. **Given** el módulo del CLI, **When** se revisa, **Then** toda la lógica que
   invoca (login, escaneo, conexión, operación) reside en la API pública, no en
   el CLI.
3. **Given** una integración, **When** se acopla, **Then** usa las mismas
   entradas públicas que el CLI (documentadas), sin importar nada de `cli`.

### Edge Cases

- Credenciales por flags `--account/--password` **o** por entorno/`.env`; los
  flags mandan; si no hay ninguna, error de configuración.
- `--transport bumble` sin puerto (ni `--port` ni `AQARA_ESP32_PORT`): error claro.
- Falta el extra opcional del transporte: el mensaje dice qué instalar (lo da la
  librería).
- Ninguna ruta del CLI imprime contraseña, token ni clave de sesión.
- `aqara` sin subcomando: muestra la ayuda y sale con código de uso.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El paquete MUST declarar un *console script* `aqara` que apunte a
  un `main()` del módulo del CLI dentro del paquete.
- **FR-002**: El CLI MUST ofrecer los subcomandos `login`, `scan`, `lock`,
  `unlock`, `operate <op>`, con `--transport bleak|bumble`, `--port`, `--mac`,
  `--timeout`, y credenciales por `--account/--password` o entorno.
- **FR-003**: El CLI MUST ser un adaptador fino: **toda** la lógica de
  login/escaneo/conexión/operación proviene de la API pública; el CLI solo
  parsea, carga credenciales, llama e imprime.
- **FR-004**: `import aqara_ble` MUST NOT importar el módulo del CLI ni leer
  el entorno; el CLI se carga solo al ejecutar el comando.
- **FR-005**: El CLI MUST mapear resultados a códigos de salida por clase
  (éxito 0; configuración; no encontrado/ambiguo; error de fase; timeout) y
  reportar la fase en los fallos de `U200ClientError`.
- **FR-006**: El CLI MUST NOT imprimir ni registrar secretos.
- **FR-007**: `examples/lock_cli.py` MUST retirarse o quedar como un envoltorio
  que delega en el CLI del paquete (una sola fuente de verdad).
- **FR-008**: La documentación MUST presentar `aqara` como la vía de terminal y
  la API pública como la vía de integración, con el ejemplo de tres líneas.

### Key Entities

- **Comando `aqara`**: adaptador de terminal (parseo, credenciales, impresión,
  códigos de salida). Sin lógica de dominio.
- **Superficie de acoplamiento**: la API pública ya existente (`U200Client`,
  `BleakTransport`/`BumbleTransport`, `scan`, `CloudAuthManager`, errores por
  fase) que consumen por igual el CLI y las integraciones.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Tras `pip install -e .`, `aqara lock` opera la cerradura sin invocar
  Python a mano ni conocer rutas de scripts.
- **SC-002**: Una integración reproduce lo que hace el CLI con **≤ 5 líneas**
  usando solo la API pública (sin importar `cli`).
- **SC-003**: `import aqara_ble` no carga `aqara_ble.cli` ni lee el
  entorno (test automatizado).
- **SC-004**: La suite sigue verde y ningún test de protocolo cambia; el CLI no
  contiene lógica de protocolo/red/BLE.

## Assumptions

- El CLI puede leer entorno/`.env` porque es un **consumidor**, no la librería;
  la pureza se mantiene en los módulos importables del paquete (decisión de la
  feature 014 preservada: la API no lee el entorno).
- Los tests del CLI usan transporte y nube simulados (sin radio ni red), igual
  que `test_client_facade`.
- El comando se llama `aqara` (nombre corto del proyecto).
