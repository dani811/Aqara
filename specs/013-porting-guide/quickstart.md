# Quickstart — Validación de la documentación

Cómo comprobar que la reorganización cumple la spec. Cada gate mapea a Success
Criteria y a los contratos. Los comandos se ejecutan desde la raíz del repo.

## Prerrequisitos

- Rama `docs/013-porting-guide`.
- El árbol `docs/` migrado a la estructura de
  [contracts/docs-structure.md](contracts/docs-structure.md).

## Gate 1 — Estructura completa (contrato C1) · FR-019

Comprobar que existen todos los documentos requeridos y que no quedan directorios
antiguos huérfanos:

```bash
# Deben existir:
for f in docs/README.md docs/architecture.md docs/porting-guide.md docs/diagnostics.md \
  docs/reference/README.md docs/reference/framing-crc.md docs/reference/cloud-login.md \
  docs/reference/ble-transport.md docs/reference/auth-handshake.md docs/reference/control-channel.md \
  docs/devices/u200/README.md docs/devices/u200/gatt-map.md docs/devices/u200/operations.md \
  docs/devices/u200/validation.md docs/evidence/README.md; do
  test -f "$f" && echo "OK  $f" || echo "MISSING  $f"
done
# No deben quedar (migrados):
for d in docs/journey docs/protocol docs/tutorials; do
  test -e "$d" && echo "STILL PRESENT  $d" || echo "OK removed  $d"
done
```

**Esperado**: todos `OK`; los tres directorios antiguos `OK removed`.

## Gate 2 — Cero secretos / APKs / capturas / código de Aqara · SC-005, FR-016/017

```bash
# Secretos y material sensible en docs/ (patrones; revisar cualquier hit a mano):
grep -rInE '([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}|[0-9a-f]{32,}|Bearer |BEGIN (RSA|EC|PRIVATE)|LTMK|sessionKey *[:=]' docs/ \
  | grep -vE 'placeholder|example|<[A-Z_]+>|XX' || echo "OK: sin secretos evidentes"
# Sin APKs / capturas / código de Aqara trackeados bajo docs/:
git ls-files docs/ | grep -iE '\.(apk|dex|so|smali|jar|ts)$|btsnoop|bugreport|capture.*\.(log|bin)' \
  && echo "FAIL: artefacto sensible" || echo "OK: sin artefactos sensibles"
```

**Esperado**: sin secretos; sin artefactos.

## Gate 3 — Idioma único (inglés) · SC-007, FR-003

Revisión: ningún documento contiene fragmentos en español. Chequeo asistido de
marcadores frecuentes (revisar hits a mano; algunos términos son válidos):

```bash
grep -rInwE 'función|clave|cerradura|conexión|dispositivo|autenticación|prueba|proceso|así|según' docs/ \
  && echo "REVISAR: posibles restos en español" || echo "OK: sin marcadores de español"
```

**Esperado**: `OK`.

## Gate 4 — Sin enlaces internos rotos · SC-007, FR-020

Verificar cada enlace relativo Markdown dentro de `docs/` y desde README/
CONTRIBUTING (con la herramienta de link-check que use el repo, o manualmente).

**Esperado**: 0 enlaces rotos.

## Gate 5 — Mapa de capas completo · SC-003, FR-008/009/010

Cada elemento de [contracts/layer-map.md](contracts/layer-map.md) aparece en
`docs/architecture.md` (Layer Map) con su capa, y vive en el documento indicado.
Ningún elemento de protocolo queda sin clasificar.

**Esperado**: 100% clasificado; `reference/*` etiqueta `Layer: transversal` y
`devices/u200/*` etiqueta `Layer: device-specific (U200)`.

## Gate 6 — Evidencia o "no verificado" · SC-004, FR-014

Toda afirmación de comportamiento de protocolo en `reference/*` y `devices/*`
tiene o bien una referencia a `evidence/`, o bien la marca `unverified`
(`ClaimStatus`).

**Esperado**: sin afirmaciones "huérfanas".

## Gate 7 — Solo documentación (sin tocar código) · SC-008, FR-021

```bash
git diff --name-only develop...HEAD | grep -vE '^(docs/|specs/013-porting-guide/|README\.md|CONTRIBUTING\.md)$' \
  && echo "FAIL: cambios fuera de documentación" || echo "OK: diff solo documentación"
```

**Esperado**: `OK`.

## Gate 8 — Sin mención de IA/asistentes ni de la PoC previa · FR-022, FR-023

La documentación se presenta como un único proyecto, neutra en cuanto al método
de producción. Chequeo asistido de marcadores (revisar hits a mano):

```bash
grep -rInE 'built with AI|hecho con IA|\bAI-assisted\b|\bClaude\b|\bCodex\b|\bChatGPT\b|asistente de IA|prueba de concepto|proof of concept|\bPoC\b|proyecto (original|refinado)|otro proyecto' docs/ \
  && echo "REVISAR: posible mención de IA/PoC/otro-proyecto" || echo "OK: neutro"
```

**Esperado**: `OK: neutro`.

## Gate 9 — Cold read por tester externo · SC-001, SC-002

Una persona ajena al proyecto, con solo la documentación:

1. Enumera los 6 pasos del proceso (captura → GATT → handshake → control →
   operaciones, + preparación) en orden. → **SC-001**
2. Antes del paso de handshake, identifica el CRC-16 del `0610` y la naturaleza
   del login, citando la sección que lo advierte y da la solución. → **SC-002**

**Esperado**: ambos superados. *Dependencia*: disponibilidad de un tester
externo; si no lo hay al cierre, SC-001/SC-002 quedan pendientes de esa
validación (bloqueo asumido).

## Resumen de trazabilidad

| Gate | Success Criteria | Contrato / FR |
| --- | --- | --- |
| 1 | — | C1 · FR-019 |
| 2 | SC-005 | C2 · FR-016/017 |
| 3 | SC-007 | G1 · FR-003 |
| 4 | SC-007 | G5 · FR-020 |
| 5 | SC-003 | layer-map · FR-008/009/010 |
| 6 | SC-004 | C3 · FR-014 |
| 7 | SC-008 | FR-021 |
| 8 | — | G4 · FR-022/023 |
| 9 | SC-001, SC-002 | User Story 1 · FR-004/005 |
