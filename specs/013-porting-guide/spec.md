# Feature Specification: Guía metódica de portabilidad Aqara (unificación de documentación)

**Feature Branch**: `docs/013-porting-guide`

**Created**: 2026-08-15

**Status**: Draft

**Input**: User description: "Reorganización y unificación de la documentación del proyecto Aqara BLE en una guía metódica de portabilidad. Fusionar el conocimiento verificado de los dos proyectos (el proyecto original de ingeniería inversa, con documentación rica pero desordenada; y el proyecto refinado actual) en una única documentación clara, concisa y sin bandazos, que permita a un colaborador nuevo portar la librería a otro dispositivo de la familia Aqara (p.ej. la U400) siguiendo un proceso paso a paso, sin tropezar en los mismos escollos (el muro del CRC-16, el login, etc.). Separar con claridad la capa transversal reutilizable/agnóstica del dispositivo frente a lo específico de cada dispositivo. Contexto: la integración principal es Home Assistant, pero la librería debe poder controlarlo todo. Restricción NO NEGOCIABLE: no se suben APKs, credenciales, cuentas ni tokens. Esta feature es SOLO reorganización de documentación."

## Overview

Este repo es **el resultado**. Antes hubo material de exploración (una prueba de
concepto) que consolidó mucho conocimiento verificado —protocolo, operaciones,
handshake, capa BLE completa, herramientas de instrumentación, artefactos de
captura— pero de forma desordenada, con hallazgos mezclados con callejones sin
salida y con material sensible entremezclado. Ese material vive **fuera** de este
repo y **no forma parte del producto**: es solo la cantera de la que se extrae el
conocimiento.

El problema a resolver es que hoy la documentación de este repo está limpia pero
**incompleta**: da por sabido mucho contexto y no explica el proceso que
permitiría repetir el trabajo para otro dispositivo. Como consecuencia, cuesta
recordar con seguridad cómo está montada la librería.

Esta feature **no escribe código de producto**: consolida en este repo, en **una
única documentación coherente**, todo el conocimiento verificado (incluido el que
hoy solo existe en ese material de exploración), de modo que sirva de guía
metódica para que un colaborador nuevo pueda **portar la librería a otro
dispositivo de la familia Aqara**. El caso de referencia resuelto es la **U200**;
la U400 se usa solo como ejemplo ilustrativo de destino.

La documentación resultante se presenta como **un solo proyecto**: no narra que
hubo una prueba de concepto previa ni "otro proyecto", ni contrapone versiones —
esa procedencia es contexto interno de cómo se produce la doc, no contenido de la
doc.

La guía es **práctica y orientada a la solución**: cada escollo conocido (de
forma destacada el CRC-16 del `0610` y el login cloud) se presenta con **su
solución concreta y accionable** —qué es, cómo se resuelve, cómo verificar que
está bien— no como una crónica del esfuerzo que costó descubrirlo. El objetivo es
que el lector **no vuelva a tropezar**, no que reviva la investigación.

El principio rector es la **separación de capas**: la documentación debe dejar
nítidamente distinguido qué es **transversal y reutilizable** para cualquier
dispositivo Aqara (framing CRC-16/ARC, login cloud AES-GCM+RSA con `compute_sign`
y KDF, y toda la capa Bluetooth: GATT, canal de auth `0610`/`0710`, canal de
control AES-CCM) frente a qué es **específico de un dispositivo** (mapa GATT
concreto, catálogo de operaciones/opcodes, quirks del firmware). Esa frontera es
lo que hará posible la futura conversión a multi-dispositivo (spec posterior).

## Clarifications

### Session 2026-08-15

- Q: ¿En qué idioma debe escribirse la documentación consolidada? → A: Inglés
  (coherente con el repo existente: README, LICENSE, constitución y `docs/` ya
  están en inglés). El poco contenido en español se traduce.
- Q: ¿Cómo abordamos la reorganización de `docs/`? → A: Estructura nueva y limpia
  (diseñar un árbol `docs/` nuevo y migrar el contenido a él), cuidando no dejar
  enlaces internos rotos.
- Q: ¿Cómo se verifica SC-001/SC-002 ("un colaborador nuevo puede portar sin
  tropezar")? → A: Con un tester externo real (una persona ajena al proyecto
  valida de verdad el proceso). Es un criterio de cierre que puede requerir
  disponibilidad de esa persona.
- Q: ¿Qué profundidad de Home Assistant debe cubrir esta doc? → A: Solo anotarlo
  como destino/integración principal prevista; no se escribe una guía de
  integración HA en esta feature.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Portar a un dispositivo nuevo siguiendo el proceso (Priority: P1)

Un colaborador que nunca ha tocado el proyecto tiene una Aqara U400 y quiere
controlarla desde la librería. Abre la documentación y encuentra un **proceso
lineal, numerado y sin bandazos**: qué necesita preparar, cómo capturar el
tráfico de forma segura, cómo identificar el mapa GATT del nuevo dispositivo,
cómo resolver el handshake de autenticación (con la trampa del CRC ya explicada
por adelantado), cómo abrir el canal de control y cómo mapear el catálogo de
operaciones. En cada paso sabe **qué es reutilizable tal cual** (no lo reinventa)
y **qué tiene que descubrir de nuevo** para su dispositivo.

**Why this priority**: Es el objetivo declarado de la feature. Si esto no se
cumple, la reorganización no ha servido para nada.

**Independent Test**: Se puede validar dando la documentación a alguien ajeno al
proyecto y comprobando que, a partir de ella y de su propio hardware/credenciales,
puede enumerar sin ayuda los pasos a seguir para la U400, identificar qué módulos
existentes reutilizaría y qué tendría que investigar, y reconocer el escollo del
CRC antes de chocar con él.

**Acceptance Scenarios**:

1. **Given** un colaborador nuevo con una U400 y sin contexto previo, **When**
   lee la guía de portabilidad de principio a fin, **Then** puede describir el
   proceso completo (captura → GATT → handshake → control → operaciones) y sabe
   en qué orden abordarlo.
2. **Given** el mismo colaborador en el paso del handshake, **When** consulta la
   sección de autenticación, **Then** encuentra, antes de intentarlo, que el
   campo "aleatorio" de 2 bytes del `0610` es en realidad un CRC-16/ARC sobre la
   clave pública, con la solución accionable: cómo calcularlo y cómo verificar que
   el valor es correcto contra una trama real.
3. **Given** cualquier página de protocolo, **When** el colaborador busca el
   respaldo de una afirmación, **Then** encuentra una referencia a la evidencia
   sanitizada que la sostiene (sin exponer capturas crudas).

---

### User Story 2 - Distinguir la capa transversal de lo específico del dispositivo (Priority: P1)

Un desarrollador quiere saber qué del proyecto es "motor genérico Aqara" y qué
está atado a la U200, para no duplicar trabajo ni tocar lo que no debe. La
documentación presenta un **mapa de capas** explícito: lo transversal (CRC,
login/cloud KDF, capa BLE — GATT, auth, control AES-CCM) queda descrito como
reutilizable y agnóstico; lo específico (mapa GATT concreto de la U200, catálogo
de operaciones/opcodes) queda descrito como sustituible por dispositivo.

**Why this priority**: Es la condición que habilita la futura spec
multi-dispositivo. Sin esta frontera clara, portar seguiría siendo caótico.

**Independent Test**: Para cada elemento del protocolo documentado, un lector
puede clasificarlo sin ambigüedad como "transversal" o "específico del
dispositivo" apoyándose únicamente en la documentación.

**Acceptance Scenarios**:

1. **Given** la documentación de arquitectura, **When** el lector revisa el mapa
   de capas, **Then** cada pieza (CRC, login, GATT, auth, control, operaciones)
   está etiquetada como transversal o específica de dispositivo.
2. **Given** la sección de portabilidad, **When** el lector planifica la U400,
   **Then** la guía indica qué capas espera reutilizar sin cambios y cuáles
   tendrá que redescubrir/adaptar.

---

### User Story 3 - Entender la arquitectura y la tecnología del sistema (Priority: P2)

Alguien que evalúa el proyecto (o retoma el contexto tras meses) quiere entender
en poco tiempo **cómo funciona el conjunto**: la arquitectura de la app oficial
como implementación de referencia, la tecnología del dispositivo (BLE + Thread,
sin Wi-Fi), el papel del cloud, el modelo de confianza (sin bonding SMP, toda la
seguridad en la capa de aplicación) y cómo encajan las siete fases del pipeline.

**Why this priority**: Da el marco mental sin el cual los pasos del proceso no se
entienden; pero es contexto, no el proceso accionable en sí.

**Independent Test**: Un lector puede explicar, tras leer la sección de
arquitectura, por qué la autorización debe vivir entera en el intercambio BLE y
qué aporta el cloud.

**Acceptance Scenarios**:

1. **Given** la documentación de arquitectura, **When** el lector la termina,
   **Then** puede dibujar el pipeline de fases y decir cuáles son cloud y cuáles
   BLE.

---

### User Story 4 - Método de diagnóstico reutilizable (Priority: P3)

Un colaborador que ataca un dispositivo nuevo se atasca en un paso (p.ej. un ACK
vacío en el handshake) y quiere una **checklist de diagnóstico**: qué hipótesis
descartar y con qué prueba, para llegar rápido a la causa. La documentación
ofrece ese método de forma **breve y generalizada** —heurísticas del tipo "un
campo que cambia cada sesión puede ser un checksum/nonce, pruébalo antes de
descartarlo"— sin narrar la cronología ni el esfuerzo que costó al equipo
original.

**Why this priority**: Acelera el diagnóstico al portar y evita repetir errores;
es apoyo, no el proceso principal, y debe ocupar poco.

**Independent Test**: Ante un síntoma dado (p.ej. ACK vacío en el `0610`), el
lector obtiene de la documentación una lista de causas a comprobar y cómo
descartarlas.

**Acceptance Scenarios**:

1. **Given** un síntoma de fallo durante la portabilidad, **When** el lector
   consulta el método de diagnóstico, **Then** encuentra hipótesis a descartar y
   la prueba para cada una, expresadas de forma aplicable a cualquier dispositivo,
   sin relato cronológico del esfuerzo.

---

### Edge Cases

- **Contradicciones en el conocimiento de origen**: cuando el material de origen
  afirma cosas distintas sobre el protocolo, la documentación consolidada debe
  resolver la discrepancia en una sola dirección (sin "bandazos"); esa resolución
  se hace durante la producción y no se narra en la salida.
- **Afirmación sin evidencia**: un hallazgo que no tenga captura/derivación que lo
  respalde debe marcarse explícitamente como no verificado, no presentarse como
  hecho.
- **Material sensible en el origen**: el material de exploración contiene MACs,
  claves, tokens y rutas a APKs/capturas. Nada de eso puede acabar en el repo; la
  información se traslada solo tras sanitización irreversible.
- **Contenido específico de la U200 disfrazado de genérico**: un detalle atado a
  la U200 que se presente como transversal induciría a error al portar; debe
  quedar etiquetado como específico.
- **Enlaces rotos tras la reorganización**: mover/renombrar documentos no debe
  dejar referencias colgando dentro de la documentación.

## Requirements *(mandatory)*

### Functional Requirements

**Unificación y coherencia**

- **FR-001**: La documentación MUST consolidar en este repo todo el conocimiento
  verificado, incluido el que hoy solo existe en el material de exploración
  externo, en un único cuerpo documental coherente, sin dejar conocimiento
  canónico fuera del repo.
- **FR-002**: La documentación MUST resolver toda contradicción entre las fuentes
  de conocimiento en una única dirección, sin presentar versiones alternativas
  del mismo hecho de protocolo como igualmente válidas.
- **FR-003**: La documentación MUST estar redactada de forma clara y concisa **en
  inglés**, de forma coherente con el resto del repo (README, LICENSE,
  constitución, `docs/`). Cualquier contenido heredado en español MUST traducirse;
  no se mezclan idiomas dentro de la documentación publicada.
- **FR-023**: La documentación resultante MUST presentarse como un único proyecto:
  MUST NOT mencionar que hubo una prueba de concepto previa ni "otro proyecto",
  ni contraponer versiones/fuentes. La procedencia del conocimiento es contexto
  interno del proceso de producción, no contenido publicado.

**Guía de portabilidad (proceso)**

- **FR-004**: La documentación MUST incluir una guía de portabilidad que describa,
  como proceso lineal y numerado, los pasos para llevar la librería a otro
  dispositivo de la familia Aqara, cubriendo al menos: preparación/entorno,
  captura de tráfico, identificación del mapa GATT, resolución del handshake de
  autenticación, apertura del canal de control y mapeo del catálogo de
  operaciones.
- **FR-005**: Para cada escollo conocido —de forma destacada el CRC-16 del `0610`
  y las particularidades del login cloud— la guía MUST dar su **solución concreta
  y accionable**: qué es el escollo, cómo se resuelve paso a paso y cómo verificar
  que la solución es correcta. La advertencia va **antes** del paso donde
  aparecería, para evitarlo en vez de sufrirlo. La guía MUST NOT sustituir la
  solución por el relato de cuánto costó descubrirla.
- **FR-006**: Para cada paso del proceso, la guía MUST indicar qué es reutilizable
  sin cambios (capa transversal) y qué debe descubrirse/adaptarse para el nuevo
  dispositivo (capa específica).
- **FR-007**: La guía MUST usar la **U200 como caso de referencia ya resuelto**
  (la fuente de verdad de todo el conocimiento del proyecto) y un dispositivo aún
  no soportado (p.ej. la U400) únicamente como **ejemplo ilustrativo de destino**
  de una portabilidad, para que el lector vea el proceso aplicado a un caso
  concreto sin confundir lo verificado (U200) con lo hipotético (el nuevo).

**Separación de capas**

- **FR-008**: La documentación MUST presentar un mapa de capas explícito que
  clasifique cada elemento del sistema como transversal/agnóstico del dispositivo
  o específico del dispositivo.
- **FR-009**: La documentación MUST describir como capa transversal reutilizable,
  como mínimo: el framing con CRC-16/ARC, el login cloud (AES-GCM + RSA con
  `compute_sign`) y su KDF, y toda la capa Bluetooth (GATT, canal de auth
  `0610`/`0710`, canal de control AES-CCM).
- **FR-010**: La documentación MUST describir como capa específica del
  dispositivo, como mínimo: el mapa GATT concreto y el catálogo de
  operaciones/opcodes.

**Arquitectura y protocolo**

- **FR-011**: La documentación MUST explicar la arquitectura de la app oficial
  como implementación de referencia y la tecnología del dispositivo (BLE + Thread,
  sin Wi-Fi), el papel del cloud y el modelo de confianza (sin bonding SMP;
  seguridad en la capa de aplicación).
- **FR-012**: La documentación MUST describir el comportamiento del protocolo
  extremo a extremo (el pipeline de fases cloud + BLE) de forma que el lector
  entienda el orden y el porqué de cada fase.
- **FR-013**: La documentación MUST anotar que la integración principal prevista
  es Home Assistant y qué implica eso para la librería (controlar toda la
  superficie de operaciones del dispositivo, no solo abrir/cerrar). Esta feature
  MUST NOT incluir una guía de integración con Home Assistant; solo lo señala como
  destino.

**Evidencia y trazabilidad**

- **FR-014**: Cada afirmación de comportamiento de protocolo MUST estar respaldada
  por una referencia a evidencia sanitizada (captura/derivación descrita), o
  marcada explícitamente como no verificada.
- **FR-015**: La documentación MUST incluir un **método de diagnóstico** breve y
  generalizable (heurísticas y checklist de causas por síntoma) destilado de la
  experiencia previa, orientado a resolver atascos al portar. MUST NOT convertirse
  en una crónica del proceso ni cuantificar el tiempo/esfuerzo invertido; el foco
  es la solución, no la historia.

**Higiene de secretos (NO NEGOCIABLE — Principio I)**

- **FR-016**: La documentación MUST NOT contener ni enlazar dentro del repo
  ningún secreto real ni material sensible: tokens, app keys/IDs, claves RSA/AES,
  LTMK, session keys, device IDs, direcciones MAC, IDs de usuario/teléfono,
  capturas crudas ni APKs. Tampoco MUST incluir el **código fuente propietario de
  la app de Aqara** verbatim (bundles, ficheros `.ts`/`.smali`/`.dex`, etc.): se
  documentan los **hallazgos** derivados (algoritmo del CRC, opcodes, estructura
  de tramas) descritos con nuestras propias palabras/pseudocódigo, no copiando su
  fuente.
- **FR-017**: Todo conocimiento trasladado desde las capturas o la app MUST estar
  sanitizado de forma irreversible (redacción, no codificación reversible) antes
  de incorporarse.
- **FR-018**: La documentación MUST explicar el proceso de captura y las
  herramientas de instrumentación sin incluir los artefactos sensibles,
  indicando que capturas y credenciales viven en rutas ignoradas por git y se
  aportan por el propio colaborador.

**Neutralidad de la redacción**

- **FR-022**: La documentación MUST estar redactada de forma neutra en cuanto al
  método de producción: MUST NOT mencionar herramientas de IA concretas ni
  nombres de asistentes, ni enmarcar el trabajo como "hecho con IA". Se describe
  qué se hizo y cómo (proceso, evidencia), no con qué asistente. Esto incluye
  reescribir el contenido heredado que hoy usa ese encuadre (p.ej. el actual
  `docs/journey/`).

**Estructura y navegación**

- **FR-019**: La reorganización MUST adoptar una **estructura `docs/` nueva y
  limpia** (un árbol rediseñado, no un parcheo del actual) con un punto de entrada
  único que indique en qué orden leer y a dónde ir según el objetivo del lector
  (entender el sistema, portar un dispositivo, o consultar el método de
  diagnóstico). El contenido válido del `docs/` actual MUST migrarse a la nueva
  estructura.
- **FR-020**: La migración a la nueva estructura MUST NOT dejar referencias/enlaces
  internos rotos, ni desde dentro de `docs/` ni desde otros ficheros del repo que
  apunten a la documentación (p.ej. README, CONTRIBUTING).

**Límites de alcance**

- **FR-021**: Esta feature MUST NOT modificar el código de la librería ni sus
  pruebas; su entregable es exclusivamente documentación (y, si acaso,
  reubicación/renombrado de documentos existentes).

### Key Entities

- **Guía de portabilidad**: el documento-proceso central; secuencia numerada de
  pasos para llevar la librería a un dispositivo Aqara nuevo, con escollos
  señalados y la frontera transversal/específico marcada en cada paso.
- **Mapa de capas**: la clasificación explícita de cada pieza del sistema como
  transversal (reutilizable) o específica del dispositivo.
- **Referencia de protocolo**: el conjunto de documentos que describen framing,
  auth, canal de control, cloud y operaciones, cada uno anclado a evidencia.
- **Índice de evidencia**: el registro de qué se observó y cómo se verificó, sin
  las capturas crudas.
- **Método de diagnóstico**: checklist breve de causas por síntoma y heurísticas
  de RE, generalizadas y orientadas a desatascar la portabilidad (no una crónica).
- **Material de origen**: el material de exploración externo (fuera del repo) del
  que se extrae el conocimiento verificado; deja de ser relevante una vez
  consolidado aquí y no se referencia en la salida.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un **tester externo real** (una persona ajena al proyecto),
  partiendo solo de la documentación, enumera el proceso completo de portabilidad
  (los seis pasos: captura → GATT → handshake → control → operaciones, más
  preparación) en el orden correcto, sin ayuda externa. La validación por esa
  persona es criterio de cierre de la feature.
- **SC-002**: Ese mismo tester externo identifica el escollo del CRC-16 del `0610`
  y la naturaleza del login **antes** de intentar el handshake, citando la
  sección de la guía que lo advierte y que aporta la solución.
- **SC-003**: Para cada uno de los elementos del sistema listados en el mapa de
  capas, el lector lo clasifica correctamente como transversal o específico del
  dispositivo apoyándose únicamente en la documentación (100% de los elementos
  clasificados sin ambigüedad).
- **SC-004**: El 100% de las afirmaciones de comportamiento de protocolo tienen o
  bien una referencia de evidencia sanitizada, o bien una marca explícita de "no
  verificado".
- **SC-005**: Una revisión de secretos sobre la documentación entregada arroja
  cero secretos reales y cero rutas a APKs/capturas dentro del repo.
- **SC-006**: No queda conocimiento canónico que exista solo en el material de
  exploración externo y no en esta documentación; y no quedan contradicciones sin
  resolver.
- **SC-007**: La documentación no contiene enlaces internos rotos tras la
  reorganización, y toda ella está en inglés (sin fragmentos en otro idioma).
- **SC-008**: El código de la librería y sus pruebas quedan sin cambios respecto
  al inicio de la feature (el diff de la feature es solo documentación/config).

## Assumptions

- El material de exploración accesible localmente (fuera de este repo) es la
  cantera de conocimiento a consolidar; su contenido verificado se considera
  válido salvo contradicción, y su material sensible se descarta. No se referencia
  en la documentación publicada.
- El **dispositivo de referencia** —la única fuente de verdad verificada— es la
  **U200**, que es la que este proyecto tiene resuelta. El dispositivo usado como
  **ejemplo de destino** de una portabilidad hipotética es la **U400** (el
  "siguiente" natural de la familia); no se dispone necesariamente de la U400
  física, así que ese ejemplo es ilustrativo del proceso, no una portabilidad ya
  ejecutada.
- La región confirmada sigue siendo la EU; otras regiones se documentan como no
  verificadas.
- Esta feature es **solo documentación**; la refactorización del paquete a
  multi-dispositivo se abordará en una spec posterior separada, para la cual esta
  documentación (en especial el mapa de capas) es el habilitador.
- Se respeta la constitución del proyecto: Principio I (higiene de secretos) es
  absoluto y prevalece sobre cualquier otra consideración; Principio IV
  (evidencia y reproducibilidad) rige la exigencia de respaldo de las
  afirmaciones.
- El trabajo se realiza en una rama `docs/*` conforme al Principio VI.
- **Dependencia**: el cierre de SC-001/SC-002 requiere la disponibilidad de un
  tester externo real. Si no lo hay en el momento del cierre, esos criterios
  quedan pendientes de esa validación (riesgo de bloqueo asumido conscientemente).
