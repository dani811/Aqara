# Contract — Documentation structure & per-document rules

Este contrato define **qué documentos deben existir** en `docs/` tras la feature
y las **reglas que cada tipo de documento debe cumplir**. Es el criterio contra
el que se valida la implementación (ver [../quickstart.md](../quickstart.md)).

## C1 — Árbol requerido (mínimo)

```text
docs/
├── README.md
├── architecture.md
├── porting-guide.md
├── diagnostics.md
├── reference/
│   ├── README.md
│   ├── framing-crc.md
│   ├── cloud-login.md
│   ├── ble-transport.md
│   ├── auth-handshake.md
│   └── control-channel.md
├── devices/
│   └── u200/
│       ├── README.md
│       ├── gatt-map.md
│       ├── operations.md
│       └── validation.md
└── evidence/
    └── README.md
```

- No deben quedar bajo `docs/` los directorios antiguos que ya no apliquen
  (`journey/`, `protocol/`, `tutorials/`) una vez migrado su contenido.
- Cualquier otro documento nuevo debe encajar en una de las zonas
  (proceso / `reference` / `devices` / `evidence`).

## C2 — Reglas globales (todos los documentos)

- **G1**: Escritos en inglés; sin fragmentos en otro idioma.
- **G2**: Cero secretos y cero material sensible: tokens, app keys/IDs, claves
  RSA/AES, LTMK, session keys, device/user/phone IDs, MACs, capturas crudas,
  APKs.
- **G3**: Sin código fuente propietario de Aqara verbatim (bundles, `.ts`,
  `.smali`, `.dex`). Los hallazgos se describen con palabras propias o
  pseudocódigo.
- **G4**: Sin mención de herramientas de IA/asistentes ni encuadre "hecho con
  IA"; sin narrar la prueba de concepto previa ni contraponer "proyectos".
- **G5**: Sin enlaces internos rotos (dentro de `docs/` y desde README/
  CONTRIBUTING).

## C3 — Reglas por tipo de documento

### `docs/README.md` (Entry Point)
- Ofrece rutas de lectura por objetivo: **understand**, **port**, **diagnose**.
- Enlaza a todos los documentos de primer nivel y a `reference/`, `devices/`,
  `evidence/`.

### `architecture.md`
- Describe el pipeline de fases (cloud + BLE), su orden y su porqué.
- Cubre tecnología (BLE + Thread, sin Wi-Fi) y modelo de confianza (sin bonding
  SMP; seguridad en capa de aplicación).
- Incluye el **Layer Map** (ver `layer-map.md`) o lo enlaza.
- Anota Home Assistant como integración principal prevista; **no** incluye guía
  de integración HA.

### `porting-guide.md` (eje)
- Proceso **numerado** con los pasos {0 preparación, 1 captura, 2 GATT,
  3 handshake, 4 canal de control, 5 operaciones}.
- Cada paso indica **qué es transversal (reusar)** vs **qué descubrir** para el
  dispositivo.
- Los escollos conocidos (CRC del `0610`, login) aparecen **antes** del paso
  correspondiente, con **solución accionable + verificación**, no como crónica.
- Usa U200 como caso resuelto y U400 solo como ejemplo de destino.

### `diagnostics.md`
- Contiene una tabla **síntoma → hipótesis → prueba de descarte** y heurísticas
  generalizadas. Breve; sin cronología ni cuantificación de esfuerzo.

### `reference/*` (capa transversal)
- Cada documento declara al inicio **`Layer: transversal`**.
- Describe mecanismo/algoritmo agnóstico del dispositivo.
- Cada afirmación de comportamiento de protocolo cita evidencia (`evidence/`) o
  se marca `unverified`.

### `devices/<device>/*` (capa específica)
- Cada documento declara **`Layer: device-specific (<device>)`**.
- `gatt-map.md`: UUIDs/handles concretos. `operations.md`: catálogo de opcodes
  con `ClaimStatus` por comando. `validation.md`: walkthrough end-to-end
  reproducible.

### `evidence/README.md`
- Índice claim → {tipo de evidencia, método, resultado sanitizado}. Nunca
  capturas crudas; referencia rutas ignoradas por git para el material local.
