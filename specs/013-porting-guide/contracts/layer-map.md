# Contract — Layer Map (transversal vs device-specific)

Clasificación canónica de cada elemento del sistema. La sección "Layer Map" de
`docs/architecture.md` debe reflejar exactamente esta tabla (o un superconjunto),
y cada elemento debe vivir en el documento indicado. Es el criterio de
verificación de SC-003 y de FR-008/009/010.

## Capa transversal (reutilizable en cualquier dispositivo Aqara)

| Elemento | Documento | Notas |
| --- | --- | --- |
| Framing CRC-16/ARC (header `app_token` = CRC del cuerpo) | `reference/framing-crc.md` | La solución del "muro"; algoritmo con palabras propias |
| Login cloud (RSA `encryptType:2` + AES-128-GCM) | `reference/cloud-login.md` | Password RSA, body AES-GCM |
| Firma de petición `compute_sign` (MD5 sobre campos ordenados) | `reference/cloud-login.md` | Reproduce el header del app |
| KDF cloud (`/publickey`, `/verify`) + HKDF | `reference/cloud-login.md` | `sessionKey` derivado cloud-side |
| Modelo GATT (servicios/roles: auth vs control vs OTA vs bulk) | `reference/ble-transport.md` | Roles genéricos, no UUIDs concretos |
| Fragmentación del canal de auth | `reference/ble-transport.md` | Reensamblado de tramas |
| Puertos de transporte de control | `reference/ble-transport.md` | Concepto de puertos |
| Handshake `0610` (KEY_EXCHANGE) / `0710` (AUTH_PROOF) | `reference/auth-handshake.md` | Mecanismo + verificación del CRC |
| Canal de control AES-CCM (tag=4, aad=∅) | `reference/control-channel.md` | Codec de control |
| Integridad de bulk CRC-HQX (YMODEM) | `reference/control-channel.md` | Transferencia masiva |
| Sin bonding SMP; seguridad en capa de aplicación | `architecture.md` | Modelo de confianza |

## Capa específica del dispositivo

| Elemento | Documento (U200) | Notas |
| --- | --- | --- |
| UUIDs propietarios de servicios/características | `devices/u200/gatt-map.md` | `fcb9/ff07/ff08`, `ff60/ff61/ff62/…` |
| Mapa ATT confirmado (handles) | `devices/u200/gatt-map.md` | Handles concretos capturados |
| Catálogo de operaciones/opcodes (SYSTEM/USER/LOG/ALARM/DEVICELOG/XXQ/SYSTEM_EXT/LONG) | `devices/u200/operations.md` | Con `ClaimStatus` por comando |
| Payloads de lock/unlock/keepalive | `devices/u200/operations.md` | Builders de alto nivel |
| Ajustes específicos (volumen de voz/alerta, idioma, auto-lock…) | `devices/u200/operations.md` | Diferenciales confirmados |
| Protocolo de alta del dispositivo (si aplica) | `devices/u200/operations.md` o doc aparte | Reversado; no causa del "muro" |
| Región/endpoint confirmado (EU) | `devices/u200/README.md` | Otras regiones: `unverified` |

## Zona gris (anotar, no resolver aquí)

| Elemento | Decisión en esta feature |
| --- | --- |
| ¿El catálogo de opcodes es común a la familia? | Se documenta como **device-specific** por defecto; promoción a transversal se decide en la spec multi-dispositivo. |

## Regla de completitud

- Todo elemento que aparezca en la documentación de protocolo debe estar en esta
  tabla con su capa asignada. Un elemento sin clasificar es un fallo de SC-003.
