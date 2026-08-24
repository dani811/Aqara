# Implementation Plan: Guía metódica de portabilidad Aqara (unificación de documentación)

**Branch**: `docs/013-porting-guide` | **Date**: 2026-08-15 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/013-porting-guide/spec.md`

## Summary

Consolidar en este repo, en una estructura `docs/` **nueva y limpia** y **en
inglés**, todo el conocimiento verificado del proyecto (incluido el que hoy solo
vive en el material de exploración externo), presentándolo como un **único
proyecto** —sin narrar la PoC previa, sin mención de herramientas/IA y sin
exponer secretos, APKs ni código propietario de Aqara.

El eje del entregable es una **guía de portabilidad** práctica y numerada que
lleva a un colaborador nuevo, paso a paso, de cero a controlar otro dispositivo
de la familia Aqara. La guía se apoya en dos pilares de referencia claramente
separados: la **capa transversal reutilizable** (framing CRC-16/ARC, login cloud
AES-GCM+RSA con `compute_sign`+KDF, y toda la capa Bluetooth: GATT, auth
`0610`/`0710`, control AES-CCM) y lo **específico del dispositivo** (mapa GATT
concreto y catálogo de operaciones/opcodes). La U200 es el caso de referencia ya
resuelto; la U400 aparece solo como ejemplo ilustrativo de destino. Los escollos
conocidos (el CRC del `0610`, el login) se presentan **con su solución**, no como
crónica. Esta feature **no toca código de la librería**.

## Technical Context

**Language/Version**: Markdown (GitHub-Flavored), documentación redactada en
**inglés**. Diagramas en ASCII/Mermaid embebidos, sin dependencias externas.

**Primary Dependencies**: Ninguna nueva. La librería Python (`aqara_ble/`) y
sus tests permanecen intactos; se referencian desde la doc pero no se modifican.

**Storage**: Sistema de ficheros, árbol `docs/`. El material sensible sigue en
rutas ignoradas por git (`.env`, `captures/`) y fuera del repo.

**Testing**: (1) verificación de enlaces internos rotos; (2) escaneo de secretos
(gate existente "0 secrets") + comprobación de ausencia de APKs/capturas/código
de Aqara; (3) comprobación de idioma único (inglés); (4) chequeo de completitud
del mapa de capas y de citación de evidencia; (5) **validación por tester externo
real** (cold read) para SC-001/SC-002.

**Target Platform**: Documentación del repositorio (renderizada en GitHub y en
editores Markdown).

**Project Type**: Repositorio de librería (single project); esta feature actúa
solo sobre `docs/` y ficheros de navegación (README/CONTRIBUTING) que enlacen a
la doc.

**Performance Goals**: N/A (documentación).

**Constraints**: Principio I (higiene de secretos) es absoluto; el diff de la
feature debe ser **solo documentación/navegación**, sin cambios en código ni
tests (FR-021, SC-008).

**Scale/Scope**: ~1 guía de portabilidad + ~1 arquitectura + ~1 método de
diagnóstico + 5 documentos de referencia transversal + N documentos por
dispositivo (U200 inicial) + índice de evidencia + punto de entrada.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Aplicación en esta feature | Estado |
| --- | --- | --- |
| I. Seguridad e higiene de secretos (NO NEGOCIABLE) | La doc no incluye secretos, capturas crudas, APKs ni código propietario de Aqara; todo lo trasladado desde el material de exploración se sanitiza de forma irreversible (FR-016/017/018). Gate de escaneo de secretos en quickstart. | ✅ PASS |
| II. Fidelidad de protocolo | La doc describe el protocolo real citando evidencia; no altera bytes ni lógica (no hay código). Las descripciones deben ser byte-exactas a lo capturado (FR-014). | ✅ PASS |
| III. Spec-Driven Development | La feature sigue el flujo specify → clarify → plan → tasks → implement; la doc es retrospectiva y así se declara. | ✅ PASS |
| IV. Evidencia y reproducibilidad | Cada afirmación de protocolo se ancla a evidencia sanitizada o se marca "no verificada" (FR-014). La guía permite reproducir desde cero con material propio del colaborador. | ✅ PASS |
| V. Calidad y estándares | No se toca código; la cláusula de "API tipada + tests" no aplica a esta feature documental. La doc sigue estándares de estructura y claridad. | ✅ PASS (N/A código) |
| VI. Disciplina de ramas | Trabajo en `docs/013-porting-guide`, merge `--no-ff` a `develop`. | ✅ PASS |

**Resultado**: sin violaciones. Complexity Tracking vacío.

## Project Structure

### Documentation (this feature)

```text
specs/013-porting-guide/
├── plan.md              # This file (/speckit-plan)
├── research.md          # Phase 0: decisiones (estructura, migración, sanitización)
├── data-model.md        # Phase 1: entidades documentales + mapa de migración
├── quickstart.md        # Phase 1: guía de validación (gates de la doc)
├── contracts/           # Phase 1: contrato de estructura y de mapa de capas
│   ├── docs-structure.md
│   └── layer-map.md
└── tasks.md             # Phase 2 (/speckit-tasks — NO lo crea /speckit-plan)
```

### Source Code (repository root)

Esta feature no modifica código. Actúa sobre el árbol `docs/`, que se **rediseña
de cero** (estructura nueva y limpia, FR-019) migrando el contenido válido del
`docs/` actual y consolidando el conocimiento del material de exploración.

Árbol `docs/` objetivo:

```text
docs/
├── README.md                     # Punto de entrada único: rutas de lectura por objetivo
│                                 #   (entender · portar · diagnosticar)
├── architecture.md               # Arquitectura, tecnología (BLE+Thread, sin Wi-Fi),
│                                 #   pipeline de fases, modelo de confianza, HA como destino
├── porting-guide.md              # EJE: proceso numerado (6 pasos) para portar un dispositivo,
│                                 #   con escollos+solución y, en cada paso, qué es transversal
│                                 #   vs qué hay que descubrir
├── diagnostics.md                # Método de diagnóstico: síntoma → hipótesis → prueba
│                                 #   (destilado del "muro"; reemplaza al journey/crónica)
├── reference/                    # CAPA TRANSVERSAL (agnóstica del dispositivo)
│   ├── README.md
│   ├── framing-crc.md            # CRC-16/ARC de framing (la solución del "muro")
│   ├── cloud-login.md            # login AES-GCM + RSA, compute_sign, KDF
│   ├── ble-transport.md          # modelo GATT, fragmentación, puertos de transporte
│   ├── auth-handshake.md         # mecanismo 0610/0710 + verificación del CRC
│   └── control-channel.md        # canal de control AES-CCM
├── devices/                      # CAPA ESPECÍFICA DEL DISPOSITIVO
│   └── u200/
│       ├── README.md             # ficha del dispositivo de referencia
│       ├── gatt-map.md           # UUIDs/handles concretos de la U200
│       ├── operations.md         # catálogo completo de operaciones/opcodes
│       └── validation.md         # walkthrough de validación end-to-end (era tutorial)
└── evidence/
    └── README.md                 # índice de evidencia sanitizada (sin capturas crudas)
```

**Structure Decision**: Se adopta la estructura nueva de arriba. La frontera
`reference/` (transversal) ↔ `devices/` (específico) materializa la separación de
capas exigida por FR-008/009/010 y habilita la futura spec multi-dispositivo:
portar = añadir un `devices/<nuevo>/` reusando `reference/` sin cambios. El
mapeo detallado de qué documento actual/where-from alimenta cada destino vive en
[data-model.md](data-model.md) (mapa de migración) y las reglas por documento en
[contracts/](contracts/).

## Complexity Tracking

> Sin violaciones de la Constitución. No aplica.
