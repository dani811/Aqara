# Feature Specification: TLS certificate verification for cloud requests

**Feature Branch**: `fix/tls-verification` (spec directory `006-tls-verification`)

**Created**: 2026-08-14

**Status**: Draft

**Input**: User description: "Restore TLS certificate verification for all Aqara
cloud HTTPS requests. Today the cloud client builds an SSL context with
verification and hostname checking disabled unconditionally (migrated verbatim as
known debt, marked 'TEMPORARY for development/testing on macOS'), so login,
public-key exchange and verify — which carry session material that opens a
physical door — are exposed to machine-in-the-middle. Verification must be on by
default; the insecure path must survive only as a single, explicit,
loudly-warned opt-out via an environment variable, requiring an explicit truthy
value; a certificate failure must produce an actionable error naming that flag;
the policy must live in one place so no call site can build an unverified
context; no request bytes, headers, signing or protocol behaviour may change."

> **Debt note**: This corrects a defect inherited by the 001–005 migration, which
> moved the cloud client **verbatim** under the "no logic change" rule. Roadmap
> item 1 records it as high-priority security debt.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Cloud calls are authenticated by default (Priority: P1)

An integrator uses the library on a normally configured machine. Every call the
library makes to the Aqara cloud — logging in, exchanging the public key, and the
verify step that returns the material used to open a physical door — reaches the
real Aqara service, or fails. It never silently talks to an impostor.

**Why this priority**: This is the defect being fixed. Material that unlocks a
door must not be exchanged over an unauthenticated channel; everything else in
this feature exists to make that default safe to live with.

**Independent Test**: With no environment overrides set, ask the library for the
security policy it applies to a cloud call and confirm it requires a valid,
name-matching server identity. Delivers the fix on its own.

**Acceptance Scenarios**:

1. **Given** no override is set, **When** the library prepares a cloud request,
   **Then** the server's identity must be presented, valid, and match the
   requested host.
2. **Given** a server whose identity is untrusted or mismatched, **When** a cloud
   request is made, **Then** the call fails instead of completing.
3. **Given** a normally configured machine, **When** cloud calls run, **Then**
   they behave exactly as before in every respect other than this check.

---

### User Story 2 - A deliberate, visible opt-out (Priority: P2)

A developer whose machine has a broken system trust store cannot complete the
credential-capture and first-unlock walkthroughs. They accept the risk for that
session and turn the check off with a single documented switch, seeing a warning
each time it takes effect.

**Why this priority**: Without a supported escape hatch, blocked users edit the
library source instead — an invisible, permanent downgrade that is strictly worse
than a documented, noisy one. Secondary to US1 because the default must be safe
first.

**Independent Test**: Turn the switch on and confirm the applied policy no longer
requires a valid identity and that a warning is surfaced; turn it off (or leave
it unset) and confirm the safe policy returns.

**Acceptance Scenarios**:

1. **Given** the opt-out is set to an explicit affirmative value, **When** a
   cloud request is prepared, **Then** identity checking is not enforced.
2. **Given** the opt-out is unset, empty, or set to a negative value, **When** a
   cloud request is prepared, **Then** identity checking stays enforced.
3. **Given** the opt-out is in effect, **When** a cloud request is prepared,
   **Then** a warning naming the opt-out is surfaced to the operator.

---

### User Story 3 - A failure that explains itself (Priority: P3)

A user on that broken-trust-store machine runs the tutorial, hits the new check,
and learns from the error what happened and what their options are.

**Why this priority**: The previous behaviour hid this entire class of failure.
Surfacing it without an actionable message would just relocate the frustration.

**Independent Test**: Cause an identity-verification failure and confirm the
reported error states the cause and names the opt-out.

**Acceptance Scenarios**:

1. **Given** the server identity cannot be verified, **When** the request fails,
   **Then** the error states that verification failed and names the opt-out.

---

### Edge Cases

- **Ambiguous switch values**: only an explicit affirmative (`1`, `true`, `yes`,
  `on`, case-insensitive, surrounding whitespace ignored) disables the check.
  Unset, empty, `0`, `false`, or any other value keeps it enforced — the safe
  reading always wins.
- **Repeated warnings**: the warning accompanies every downgraded request rather
  than being shown once; an insecure session stays visibly insecure.
- **Scope**: only cloud requests are affected. The BLE path carries no such
  channel, and its framing, encryption, and payloads are untouched.
- **Offline/unreachable cloud**: unchanged — connection and timeout failures are
  reported as before, distinct from a verification failure.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Every cloud request MUST verify the server's identity — both its
  certificate chain against the platform's trust store and the hostname — before
  data is exchanged.
- **FR-002**: The system MUST provide exactly one opt-out that disables that
  verification, expressed as an environment variable so it cannot be hard-coded
  by a caller.
- **FR-003**: The opt-out MUST take effect only for an explicit affirmative
  value; unset, empty, and negative values MUST leave verification enforced.
- **FR-004**: While the opt-out is in effect, the system MUST surface a warning
  that states verification is disabled and names the variable responsible.
- **FR-005**: A verification failure MUST be reported with a message that states
  the cause and names the opt-out as the deliberate override.
- **FR-006**: The change MUST NOT alter request bodies, headers, signing, or any
  protocol byte — behaviour is identical except for the identity check.
- **FR-007**: The verification policy MUST be decided in exactly one place, so no
  call site can construct an unverified connection independently.
- **FR-008**: The opt-out MUST be documented alongside the project's other
  environment settings, stating plainly that it removes protection against
  machine-in-the-middle interception.

### Key Entities

- **Connection security policy**: the single decision point that determines
  whether a cloud request verifies the server's identity.
- **Opt-out switch**: the named environment setting that — and only which — can
  downgrade that policy, together with the warning it triggers.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With no overrides set, 100% of cloud requests refuse to exchange
  data with a server whose identity is invalid or mismatched.
- **SC-002**: The opt-out downgrades the policy for explicit affirmative values
  only; unset, empty, and negative values keep it enforced, in 100% of cases.
- **SC-003**: No downgraded request is silent — a warning accompanies every one.
- **SC-004**: Exactly one place in the codebase decides the policy; a search for
  independently constructed connections returns zero results.
- **SC-005**: A verification failure produces a message naming both the cause and
  the opt-out, 100% of the time.
- **SC-006**: All existing behaviour is preserved — the project's quality gates
  (lint, strict typing, full test suite) stay green, with new tests covering the
  default, the opt-out, and negative values.

## Assumptions

- The Aqara cloud endpoints present certificates issued by a publicly trusted
  authority; the original workaround was framed as a local macOS trust-store
  problem, not a server-side one. If a region proved otherwise, that would be new
  evidence requiring its own spec.
- Users who enable the opt-out understand it removes machine-in-the-middle
  protection; the warning and documentation state this plainly.
- The platform's own trust store is authoritative; the project does not ship or
  bundle its own certificate authority set.
- The opt-out follows the existing environment-variable convention already used
  for the project's debug switch, so operators find it where they expect.
- Verification failures caused by a genuinely hostile network are indistinguishable
  from those caused by a broken trust store; the error message therefore describes
  both possibilities rather than assuming one.
