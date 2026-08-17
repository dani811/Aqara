# Implementation Plan: Identificación por el aire + captura del inventario cloud

**Branch**: `feature/016-device-inventory` | **Date**: 2026-08-17 | **Spec**: [spec.md](spec.md)

## Summary

Decodificar el payload de fabricante `0x0B27` del anuncio para exponer
`product_id`/`model` en `ScanCandidate` (offline, verificado). Añadir una
herramienta read-only (`tools/probe_cloud_endpoints.py`) que el usuario ejecuta
con sus credenciales para capturar el endpoint de inventario cloud, con volcado
sanitizado. Documentar evidencia. Ningún byte de protocolo cambia; `list_devices()`
queda para una feature posterior con la evidencia capturada.

## Technical Context

**Language**: Python ≥3.10. **Deps**: sin nuevas (usa `bleak`/`bumble` opcionales
existentes y el firmante cloud actual). **Testing**: pytest, unidad sin radio/red.
**Constraints**: Constitución II (protocolo intacto), I/IV (sin secretos; evidencia
sanitizada; herramienta read-only). **Scope**: `transport.py` (decode), tabla de
modelos, `tools/probe_cloud_endpoints.py`, docs de referencia, ~8 tests.

## Constitution Check

| Principio | Estado | Cómo |
| --- | --- | --- |
| I Secretos | ✅ | La herramienta no imprime/persiste secretos; volcado a ruta git-ignored con redacción; la librería no lee entorno. |
| II Protocolo | ✅ | Solo añade campos derivados del anuncio; `reasons`/`score`/tramas intactos. |
| III SDD | ✅ | spec→plan→tasks→implement en `feature/016-*`. |
| IV Evidencia | ✅ | `product_id=0x9C03` citado (anuncio real + xiaomi-ble); endpoint de inventario se captura, no se adivina. |
| V Calidad | ✅ | Tipado, tests de decodificación, ruff/mypy. |
| VI Ramas | ✅ | rama propia, merge `--no-ff`. |

**Gate**: PASS.

## Project Structure

```text
aqara_u200_ble/
├── transport.py     # ScanCandidate += manufacturer_payload/product_id/model; decode en identify_candidate
├── models.py        # NUEVO: MODEL_BY_PRODUCT_ID {0x9C03:"U200"} + decode_manufacturer_payload()
tools/
├── probe_cloud_endpoints.py   # NUEVO: sonda read-only del inventario (la ejecuta el usuario)
docs/reference/
├── ble-transport.md / cloud-login.md   # evidencia: product_id U200, endpoints observados + pendiente
tests/
├── test_device_identity.py    # NUEVO: decode del payload, tabla de modelos, candidato ampliado
examples/lock_cli.py           # scan imprime el modelo
```

**Structure Decision**: la decodificación vive en un módulo `models.py` pequeño y
puro (fácil de testear y ampliar); `transport.py` solo la invoca.

## Complexity Tracking

Sin violaciones.
