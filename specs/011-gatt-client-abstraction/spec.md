# Feature Specification: GATT client abstraction (transport-independent protocol)

**Feature Branch**: `feature/011-gatt-client-abstraction`

**Created**: 2026-08-15

**Status**: Retrospective (reconstructed 2026-08-17 from commit 4d0f5c0 and the shipped code)

**Input**: "Desacoplar la capa de sesión de un cliente BLE concreto: definir la interfaz GATT tipada de la que depende `run_authenticated_lock_operation`, para que la librería funcione con cualquier transporte (Bleak nativo, Bumble, o el Bluetooth manager de Home Assistant) sin acoplarse a una implementación."

> **Retrospective note (Constitution Principle III)**: This feature was built and
> merged (commit `4d0f5c0`, 2026-08-15) before its spec directory existed — it is
> the one gap in the `specs/NNN-*` sequence (010 → 012). This document
> reconstructs the intent and contract honestly from the shipped `gatt.py`,
> `session.py` diff and `tests/test_gatt_abstraction.py`; nothing here is
> aspirational. No secrets are involved (it is a typing/interface layer).

## Context

Through feature 010 the session layer (`run_authenticated_lock_operation`) took a
parameter literally named `bleak_client: Any` and called BLE methods on it
directly. That tied the core protocol to Bleak by convention and lost all typing:
any object was accepted, and the optional low-level capabilities (MTU,
Read-By-Type, connection update) were poked at with `getattr(bleak_client, …)`
with no declared contract.

This feature introduces a **typed, structural interface** — `GattClient` (and an
extended `AdvancedGattClient`) as `typing.Protocol`s — that the session depends on
instead of a concrete client. `session.py` renames `bleak_client` → `client:
GattClient`. Because Protocols are structural, `BleakClient`, `BumbleGattAdapter`
and test mocks all satisfy it **without** subclassing, and a future Home Assistant
Bluetooth transport can too. The optional capabilities become an explicit,
best-effort extended protocol rather than undocumented `getattr` probing.

This is the seam every later transport work (feature 015's `Transport` +
`BleakTransport`/`BumbleTransport`) builds on.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The session accepts any conforming client (Priority: P1)

An integrator drives `run_authenticated_lock_operation` with their own BLE client
(Bleak, Bumble adapter, HA Bluetooth, or a fake) as long as it provides the
minimal GATT surface — no subclassing, no import of a base class.

**Why this priority**: it is the whole point — decoupling the protocol from a
specific radio so the library is reusable.

**Independent Test**: `tests/test_gatt_abstraction.py` runs the full authenticated
flow against a `MinimalGattClient` that implements only the required methods; the
operation completes.

**Acceptance Scenarios**:
1. **Given** a client with only `write_gatt_char`/`start_notify`/`stop_notify`,
   **When** it drives the flow, **Then** the operation completes.
2. **Given** `BumbleGattAdapter`, **When** used as before, **Then** it still works
   unchanged (it satisfies the protocol structurally).
3. **Given** any conforming object, **When** passed as `client`, **Then** no
   subclassing or base-class import is required (structural typing).

### User Story 2 - Optional low-level capabilities are truly optional (Priority: P1)

A minimal client that lacks the advanced primitives (LE features, MTU exchange,
Read-By-Type, data-length, connection-parameter update) still completes the core
flow; those capabilities are attempted best-effort and skipped when absent.

**Why this priority**: native stacks (bleak/CoreBluetooth) do not expose these;
requiring them would break the native path.

**Independent Test**: the flow succeeds with a client that defines none of the
optional methods; their absence triggers the documented best-effort skip.

**Acceptance Scenarios**:
1. **Given** a client without any optional method, **When** the pre-auth runs,
   **Then** each missing capability is skipped and the flow still succeeds.
2. **Given** the extended interface, **When** a client provides an optional
   method, **Then** the session uses it.

### Edge Cases

- An optional capability that raises must not abort the flow (best-effort).
- The abstraction MUST NOT change the wire sequence or bytes — only the type of
  the parameter and how capabilities are discovered.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The library MUST define a typed `GattClient` structural interface
  (`typing.Protocol`) with the minimal GATT surface the session needs:
  `write_gatt_char`, `start_notify`, `stop_notify`.
- **FR-002**: The library MUST define an extended `AdvancedGattClient` protocol
  declaring the optional best-effort capabilities (`get_remote_le_features`,
  `request_mtu`, `read_by_type`, `write_by_type`, `set_data_length`,
  `update_connection_parameters`).
- **FR-003**: `run_authenticated_lock_operation` MUST depend on `GattClient`
  (parameter `client: GattClient`), not on a concrete Bleak type.
- **FR-004**: Conformance MUST be structural: `BleakClient`, `BumbleGattAdapter`
  and mocks satisfy the interface without subclassing.
- **FR-005**: Optional capabilities MUST remain best-effort — discovered
  dynamically and skipped (without failing the flow) when a client lacks them.
- **FR-006**: The change MUST be behavior-preserving: no change to framing, CRC,
  crypto, CCCD order or the wire sequence (Constitution II).
- **FR-007**: `GattClient` MUST be exported from the package public API.
  (`AdvancedGattClient` is an internal contract used structurally via `getattr`
  discovery; as shipped it is **not** exported — the optional capabilities are
  probed by name, not by importing the protocol.)

### Key Entities

- **GattClient**: the minimal typed contract the session requires from a transport.
- **AdvancedGattClient**: the extended, optional, best-effort capability surface.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The full authenticated flow completes against a client implementing
  only the three required methods (proved without radio).
- **SC-002**: The existing Bumble path and all prior session-flow tests remain
  green — zero behavior change.
- **SC-003**: `GattClient` is importable from `aqara_u200_ble` and in `__all__`.
- **SC-004**: The session no longer references a concrete Bleak type in its
  signature.

## Assumptions

- Structural typing (`Protocol`) is preferred over an ABC so third-party clients
  need no import/inheritance (matches the shipped design).
- The optional capabilities stay best-effort because native OS stacks do not
  expose them; only external HCI controllers (Bumble) do.
- This retrospective spec documents the merged implementation; it introduces no
  new work.
