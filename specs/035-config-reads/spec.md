# Feature Specification: Config Reads (volume, direction, auto-lock, language)

**Feature Branch**: `feat/035-config-reads`

**Created**: 2026-08-26

**Status**: Draft — **premise revised 2026-08-26** (see note below)

**Input**: User description: "Fase A — lecturas de configuración restantes del U200 por BLE (solo lectura, sin actuar ni escribir): volumen (0xC3), dirección de apertura (0xC0), auto-lock (0xAE), idioma (0x68). Reutilizar el frame de lectura genérico existente. Decodificar honestamente (None hasta confirmar con captura real correlacionada con la app). Exponer como entidades read-only en haos_aqara. Sin escrituras ni gestión de usuarios/contraseñas."

> **⚠️ Revised understanding (2026-08-26).** The original premise — "reuse the
> generic read frame; these may not be BLE-readable" — was **overturned** by
> decrypting the official app's own BLE session (keystream-reuse attack; the app
> uses a static AES-CCM nonce). Findings, now the basis for this feature (full
> detail in [settings-protocol.md](../../docs/devices/u200/settings-protocol.md)):
>
> 1. A read frame is `<opcode> <KIND> <body>`, and the **KIND byte** (command
>    family: 01 SYSTEM / 02 / 03 / 04) is required — the generic `build_read_query_write`
>    (kind absent) only works for kind-01 opcodes. Volume is `0xc3` kind 04 / `0x02`
>    kind 02; language `0x68` kind 01; alarm volume `0x84` kind 02.
> 2. There are **two tiers**. Free reads (door type, battery, auto-lock `0xae`,
>    direction `0xc0`, work mode `0xee`, verify-fail `0x94`, …) answer any
>    authenticated session. **Elevation-gated** reads (volume, language, alarm
>    volume, finger, lock-setting) answer only after the app's connect-time setup
>    burst (set-time `0x33` and/or access-log sync `0x13`) — the exact trigger is
>    an open A/B test.
> 3. Reads therefore use a **persistent session** (one auth, many frames) —
>    `U200Client.read_burst` / `follow_up_ops` (committed under this branch).
>
> So: NOT cloud-only, NOT Matter — genuinely BLE-readable. The requirements below
> are updated accordingly; the "honest None until confirmed" rule still holds for
> the value ENUMS (which need an app-correlated change-and-reread)."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Read the four remaining config settings over BLE (Priority: P1)

As an owner of an Aqara U200 running the BLE-only integration, I want the lock's
volume, opening direction, auto-lock, and language settings surfaced from the
device itself — with no cloud and no Matter — so I can see the lock's real
configuration alongside the settings already exposed (door type, assist turn,
pull spring).

**Why this priority**: These four are the last catalogued **read-only** settings
whose payload is not yet decoded. They carry no actuation risk, need no physical
lock operation, and complete the "read the lock's configuration" surface — the
highest-value, lowest-risk remaining work.

**Independent Test**: With a real U200 in reach of the HA Bluetooth adapter,
issuing each read returns either a confirmed typed value (once its byte layout is
pinned) or `None` (honestly "unknown"), never an invented value.

**Acceptance Scenarios**:

1. **Given** a reachable lock, **When** the volume setting is read, **Then** the
   decoded value matches what the phone app shows for that lock at that moment.
2. **Given** a reachable lock, **When** any of the four settings is read before
   its byte layout has been confirmed by a captured, app-correlated frame,
   **Then** the result is `None` (unknown) and the raw response is still available.
3. **Given** an unreachable lock, **When** a read is attempted, **Then** it fails
   cleanly without inventing a value or crashing the integration.

---

### User Story 2 - See the settings as entities in Home Assistant (Priority: P2)

As a Home Assistant user, I want the four settings shown as read-only entities,
updated on demand (the existing pull model + Refresh button), so they live next
to the lock's other settings without adding background BLE traffic.

**Why this priority**: Delivers the reads to the user surface, but depends on
Story 1 (the decoders) landing first.

**Independent Test**: After a Refresh, each new entity shows the confirmed value
or `unknown`, and no new polling task is introduced.

**Acceptance Scenarios**:

1. **Given** the integration is loaded, **When** the user presses Refresh, **Then**
   the four new entities update alongside the existing settings in one on-demand pass.
2. **Given** a setting whose byte layout is not yet confirmed, **When** its entity
   updates, **Then** it reports `unknown` rather than a placeholder value.

---

### Edge Cases

- A setting's response arrives but with an unexpected length or opcode → decoder
  returns `None`, never raises.
- The read frame succeeds but the value byte is out of the known range (e.g. a
  volume level not in the catalogued set) → labelled `level-N` / `None` per the
  decoder's honesty rule, matching the `decode_door_type` precedent.
- A read times out on a shared ESP32 BLE proxy → surfaces as unknown for that pass;
  the last confirmed value is retained.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The library MUST read the **volume** setting (opcode `0xC3`) over the
  existing generic read frame and expose a typed decoder for its response.
- **FR-002**: The library MUST read the **opening direction** setting (opcode
  `0xC0`) and expose a typed decoder.
- **FR-003**: The library MUST read the **auto-lock** setting (opcode `0xAE`) and
  expose a typed decoder (enabled flag, and delay if the payload carries one).
- **FR-004**: The library MUST read the **language** setting (opcode `0x68`) and
  expose a typed decoder.
- **FR-005**: Each decoder MUST return `None` when the frame is not a recognised
  reply for that opcode, and MUST return `None` (never an invented value) for any
  value byte not yet confirmed against a captured, app-correlated frame — the same
  honesty rule already applied to battery / door type / pull spring.
- **FR-006**: Each read MUST send the correct `<opcode> <KIND> <body>` control
  frame for its family (NOT the kind-less generic `build_read_query_write`, which
  only answers for kind-01 opcodes), and MUST NOT send any actuation command
  (`0x74`). Elevation-gated reads (volume/language/alarm volume) MUST run inside a
  **persistent session** (`read_burst` / `follow_up_ops`) after the elevation
  trigger, since a fresh per-command session reads them cold and gets nothing.
- **FR-007**: The Home Assistant integration MUST expose each of the four settings
  as a **read-only** entity, updated only through the existing on-demand pull and
  Refresh button — no new background polling task.
- **FR-008**: The confirmed byte layout for each opcode MUST be documented in the
  U200 operations docs with the captured sample that confirmed it (opcode promoted
  CATALOGUED → CONFIRMED), and covered by a unit test asserting the real frame
  decodes to the expected value.
- **FR-009**: Until a given opcode's layout is confirmed live, its decoder and
  entity MUST ship in the honest-`None` state rather than being withheld, so the
  raw response is observable to aid the next capture.

### Key Entities *(include if feature involves data)*

- **Volume setting**: the lock's prompt/beep loudness (e.g. off / low / high).
- **Opening direction**: which way the bolt/handle operates (left/right or the
  app's equivalent), read-only here.
- **Auto-lock setting**: whether the lock re-locks automatically, and its delay if
  the payload carries one.
- **Language setting**: the voice-prompt language selected on the lock.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All four settings can be read from a real lock over BLE in a single
  on-demand pass, with **zero** actuation or write commands sent (verifiable from
  the sent-frame log).
- **SC-002**: For every opcode confirmed in this feature, the decoded value matches
  the phone app's displayed value for the same lock at the same time (0 mismatches
  across the captured sample set).
- **SC-003**: No decoder ever returns a non-`None` value for an unconfirmed byte
  layout (100% honesty: unknown stays unknown).
- **SC-004**: The four new entities appear in Home Assistant and refresh through the
  existing Refresh button, adding **no** new background BLE polling task.

## Assumptions

- The opcodes `0xC3` / `0xC0` / `0xAE` / `0x68` are the correct read-only SYSTEM
  reads for volume / direction / auto-lock / language, per the operations catalogue;
  a capture may reveal a paired reply opcode (e.g. `0xDF`↔`0xE0` for door type), in
  which case the reply opcode is used for decoding.
- Confirming each byte layout requires the user to correlate a live read with the
  phone app (as done for door type / assist / pull spring); the deliverable can land
  with some opcodes still in the honest-`None` state pending that correlation.
- No physical operation of the lock is needed (these are settings reads, not events).
- The existing on-demand pull model, Refresh button, and read retry/gap logic in
  haos_aqara are reused unchanged.

## Out of Scope

- Any **write** to these settings (changing volume, direction, auto-lock, language).
- User / credential management (list, add, delete users; fingerprint; NFC).
- Temporary / offline password provisioning.
- The alarm capture and expanded event `source` mapping (tracked separately under
  the ff62 event feed work).
