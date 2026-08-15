---

description: "Task list for feature 013 — Guía metódica de portabilidad Aqara"
---

# Tasks: Guía metódica de portabilidad Aqara (unificación de documentación)

**Input**: Design documents from `/specs/013-porting-guide/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Esta feature es documental. No hay tests automatizados de código; la
verificación son los **gates del [quickstart.md](quickstart.md)** (estructura,
secretos, idioma, enlaces, mapa de capas, evidencia, diff-solo-docs, cold read).

**Organization**: Tareas agrupadas por user story. Cada story es un incremento
entregable y verificable de forma independiente.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Puede ir en paralelo (fichero distinto, sin dependencias pendientes)
- **[Story]**: A qué user story pertenece (US1..US4)
- Toda tarea incluye rutas de fichero concretas

## Restricciones transversales (aplican a TODA tarea de escritura)

- Todo en **inglés** (FR-003) · **cero secretos/APKs/capturas/código de Aqara**
  (FR-016/017) · **sin mención de IA/asistentes ni de la PoC previa** (FR-022/023)
  · cada afirmación de protocolo con **evidencia o marca `unverified`** (FR-014).

---

## Phase 1: Setup

- [X] T001 Create the new `docs/` skeleton directories `docs/reference/`, `docs/devices/u200/`, `docs/evidence/` per [contracts/docs-structure.md](contracts/docs-structure.md) (C1)
- [X] T002 [P] Add a short "Documentation conventions" block (Layer label values `transversal` / `device-specific`; `ClaimStatus` = `confirmed`/`catalogued`/`unverified`; evidence-citation style) to `CONTRIBUTING.md`
- [X] T003 Harvest and **sanitize** the source knowledge into a git-ignored working note under the scratchpad (cross-referencing the current `docs/` and the external exploration material), stripping every secret, MAC, key, token, device/user ID, APK/capture path and any Aqara source code — this note is NOT committed (Principle I, FR-017)

**Checkpoint**: skeleton + conventions + a sanitized knowledge base ready to write from.

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: Scaffolding that every user story links to. No story content yet.

- [X] T004 Create `docs/README.md` entry point with reading paths (**understand** / **port** / **diagnose**) and the tree index; forward links to the docs created later are allowed (FR-019)
- [X] T005 Create `docs/architecture.md` skeleton with section headings only: end-to-end pipeline, technology (BLE + Thread), trust model, **Layer Map** placeholder, Home Assistant note
- [X] T006 Create `docs/evidence/README.md` sanitized evidence-index scaffold (claim → evidence kind → verification method), seeded from the current `docs/evidence/README.md`

**Checkpoint**: navigation and anchors exist; user stories can proceed.

---

## Phase 3: User Story 1 — Portar siguiendo el proceso (Priority: P1) 🎯 MVP

**Goal**: A numbered, solution-oriented porting guide that takes a newcomer from
zero to controlling another Aqara device, flagging obstacles (with fixes) up front
and marking, per step, what is reusable vs what must be discovered.

**Independent Test**: A cold reader enumerates the six steps (prepare → capture →
GATT → handshake → control → operations) in order and, before the handshake step,
identifies the `0610` CRC-16 and the login nature with the section that gives the
solution (SC-001/SC-002, quickstart Gate 9).

- [X] T007 [US1] Write the numbered process in `docs/porting-guide.md` (steps 0–5: prepare/environment, capture traffic, identify GATT map, resolve auth handshake, open control channel, map operations catalog), framing **U200 as the solved reference** and **U400 only as an illustrative target example** (FR-007)
- [X] T008 [US1] In `docs/porting-guide.md`, add the escollo callouts **with solution + verification** — the `0610` CRC-16 and the cloud login — placed **before** their step, linking to `docs/reference/framing-crc.md`, `docs/reference/auth-handshake.md`, `docs/reference/cloud-login.md` (FR-005)
- [X] T009 [US1] In `docs/porting-guide.md`, add per-step "**transversal (reuse)** vs **device-specific (discover)**" callouts with cross-links to `docs/reference/` and `docs/devices/u200/` (FR-006)
- [X] T010 [US1] Fold the capture/preparation procedure (from the current `docs/tutorials/01-getting-started.md` and `02-capture-credentials.md`) into steps 0–1 of `docs/porting-guide.md`, without any sensitive artifact (FR-018)

**Checkpoint**: the guide stands alone as the MVP; links to reference/device docs resolve once US2 lands.

---

## Phase 4: User Story 2 — Separar capa transversal vs específica (Priority: P1)

**Goal**: The reusable, device-agnostic reference (`reference/`) and the
device-specific reference (`devices/u200/`) physically separated, plus the Layer
Map classifying every element.

**Independent Test**: For each element in [contracts/layer-map.md](contracts/layer-map.md),
a reader classifies it as transversal or device-specific using only the docs; the
`reference/` vs `devices/` split makes the boundary unambiguous (SC-003, Gate 5).

- [X] T011 [P] [US2] Write `docs/reference/framing-crc.md` (`Layer: transversal`) — CRC-16/ARC framing and how to verify it, in own words/pseudocode (no Aqara source)
- [X] T012 [P] [US2] Write `docs/reference/cloud-login.md` (`Layer: transversal`) — RSA (`encryptType:2`) + AES-128-GCM login, `compute_sign`, cloud KDF (`/publickey`, `/verify`), HKDF
- [X] T013 [P] [US2] Write `docs/reference/ble-transport.md` (`Layer: transversal`) — GATT service/role model, auth-channel fragmentation, transport ports
- [X] T014 [P] [US2] Write `docs/reference/auth-handshake.md` (`Layer: transversal`) — `0610` (KEY_EXCHANGE) / `0710` (AUTH_PROOF) mechanism + CRC verification
- [X] T015 [P] [US2] Write `docs/reference/control-channel.md` (`Layer: transversal`) — AES-CCM control channel (tag=4, aad=∅) + CRC-HQX bulk integrity
- [X] T016 [US2] Write `docs/reference/README.md` indexing the transversal layer (after T011–T015)
- [X] T017 [P] [US2] Write `docs/devices/u200/gatt-map.md` (`Layer: device-specific (U200)`) — concrete service/characteristic UUIDs and confirmed ATT handles
- [X] T018 [P] [US2] Write `docs/devices/u200/operations.md` (`Layer: device-specific (U200)`) — full opcode catalog (SYSTEM/USER/LOG/ALARM/DEVICELOG/XXQ/SYSTEM_EXT/LONG) with `ClaimStatus` per command
- [X] T019 [P] [US2] Write `docs/devices/u200/validation.md` — reproducible end-to-end validation walkthrough (migrated from `docs/tutorials/end-to-end-unlock.md`)
- [X] T020 [US2] Write `docs/devices/u200/README.md` — device fact sheet (confirmed EU region; other regions `unverified`; links to gatt-map/operations/validation)
- [X] T021 [US2] Fill the **Layer Map** section in `docs/architecture.md` per [contracts/layer-map.md](contracts/layer-map.md) — every element classified and pointing to its home doc (after reference/ and devices/ exist)

**Checkpoint**: layer separation is real and complete; the future multi-device spec can add `devices/<new>/` reusing `reference/`.

---

## Phase 5: User Story 3 — Entender la arquitectura (Priority: P2)

**Goal**: The mental model — the phase pipeline, the technology, the trust model,
and Home Assistant as the intended integration.

**Independent Test**: After reading `docs/architecture.md`, a reader can draw the
phase pipeline and say which phases are cloud and which are BLE (SC of US3).

- [X] T022 [US3] Write the `docs/architecture.md` narrative: the phase pipeline (cloud + BLE) with order and rationale, technology (BLE + Thread, no Wi-Fi), trust model (no SMP bonding; security at the application layer), and the Home Assistant-as-target note without an HA integration guide (FR-011/012/013)

**Checkpoint**: architecture readable end to end (Layer Map already added in US2).

---

## Phase 6: User Story 4 — Método de diagnóstico (Priority: P3)

**Goal**: A short, generalized diagnostic method to unblock porting, replacing the
old chronicle.

**Independent Test**: Given a symptom (e.g. an empty ACK on `0610`), the reader
gets a list of hypotheses and the test to rule each out (SC of US4).

- [X] T023 [US4] Write `docs/diagnostics.md` — a **symptom → hypothesis → ruling-out test** table plus generalized heuristics, distilled from the "descartes por capa" of the current `docs/journey/` (rewritten, no chronology, no effort/time framing) (FR-015/022)

**Checkpoint**: diagnostics available and linked from the porting guide steps.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T024 Migrate any remaining canonical content and **remove** the old directories `docs/journey/`, `docs/protocol/`, `docs/tutorials/` (FR-001; nothing canonical left outside the new tree)
- [X] T025 [P] Update `README.md` and `CONTRIBUTING.md` (repo root) links to point at the new `docs/` structure — no broken links (FR-020)
- [X] T026 Run [quickstart.md](quickstart.md) Gates 1–8 (structure, secrets, English-only, internal links, Layer-Map completeness, evidence/`unverified`, docs-only diff, and no AI/PoC/other-project mentions) and fix every finding (SC-003/004/005/007/008, FR-022/023)
- [ ] T027 Arrange the **external cold-read** validation (Gate 9, SC-001/SC-002); record the outcome, or mark it pending if no external tester is available at close

---

## Dependencies & Execution Order

- **Setup (T001–T003)** → before everything.
- **Foundational (T004–T006)** → before all user stories.
- **US1 (T007–T010)**: authored as the MVP; its links to `reference/`/`devices/`
  resolve once US2 lands (forward links allowed).
- **US2 (T011–T021)**: T011–T015 parallel; T016 after T011–T015; T017–T019
  parallel; T020 after T017–T019; T021 after `reference/` and `devices/` exist.
- **US3 (T022)**: edits `architecture.md` (skeleton from T005); sequence after
  T021 to avoid editing the same file concurrently.
- **US4 (T023)**: independent; can start any time after Foundational.
- **Polish (T024–T027)**: after all story content exists. T026 before T027.

## Parallel Opportunities

- Setup: T002 ∥ (T001, T003 sequential-ish since T003 reads the new layout).
- US2 reference docs: **T011, T012, T013, T014, T015** all in parallel.
- US2 device docs: **T017, T018, T019** in parallel.
- Polish: **T025** parallel with T024.

## Implementation Strategy

- **MVP = User Story 1** (T001–T010): the numbered porting guide with obstacles
  solved up front. Delivers "a newcomer has the base to start" on its own.
- **Increment 2 = User Story 2**: fills the separated transversal/device reference
  the guide links to; unlocks the future multi-device spec.
- **Increments 3–4 = US3, US4**: architecture narrative and diagnostic method.
- **Polish**: migrate-and-remove old dirs, fix links, run all gates, external cold
  read.
