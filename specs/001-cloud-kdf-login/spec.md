# Feature Specification: Cloud login & key derivation

**Feature Branch**: `feature/001-cloud-kdf-login`

**Created**: 2026-08-14

**Status**: Retrospective (reconstructed from reverse-engineering; behavior verified live)

**Input**: User description: "Cloud login and key derivation: RSA+AES-GCM login, HKDF nonce, compute_sign request signing"

> **Retrospective note (Constitution Principle III)**: This capability was
> reverse-engineered from the official Aqara app before the project adopted
> Spec-Driven Development. This document is an honest reconstruction of the
> intended behavior, written after the fact. Every acceptance scenario below was
> confirmed against the real cloud service; nothing here is aspirational.

## Clarifications

### Session 2026-08-14

The specification was scanned for high-impact ambiguities (`/speckit-clarify`).
Because this is a **retrospective** spec whose every acceptance scenario was
already confirmed against the live cloud service, no blocking ambiguities remain.
Three points that could otherwise need clarification are resolved explicitly in
the spec itself:

- **Region coverage** — only the region the project actually used is confirmed;
  others are assumed to follow the same URL pattern (see Assumptions).
- **Local vs. cloud derivation of session material** — resolved as cloud-only;
  local derivation was investigated and abandoned (server-held secret).
- **Signature over plaintext vs. ciphertext** — resolved as plaintext-body
  signing even when the body is transmitted encrypted (FR-004, Edge Cases).

No questions were escalated to the user for this feature.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Obtain a session's public key autonomously (Priority: P1)

An integrator holds a captured account token for their own Aqara account and
wants their Python program — with no phone and no official app running — to ask
the Aqara cloud for the ephemeral public key that a BLE unlock session requires.

**Why this priority**: Without the cloud-provided `cloudPublicKey`, no BLE
authentication handshake can even begin. This is the irreducible first step of
full autonomy and everything else depends on it.

**Independent Test**: Provide valid account credentials and a device identifier,
request the public key, and confirm a well-formed 65-byte uncompressed
SECP256R1 point comes back. Delivers value on its own: it proves the account can
drive the cloud from Python.

**Acceptance Scenarios**:

1. **Given** valid credentials and a device the account owns, **When** the
   program requests the session public key, **Then** the cloud returns a 65-byte
   uncompressed SECP256R1 point (leading `04`).
2. **Given** a request whose signature is computed incorrectly, **When** it is
   sent, **Then** the cloud rejects it with a signature error rather than
   returning key material.

---

### User Story 2 - Authenticate an account without the app (Priority: P1)

An integrator wants to exchange their account username/password for an account
token programmatically, so the whole flow can run headless and refresh its own
credentials.

**Why this priority**: A token is the entry credential for every signed request.
Being able to log in from Python removes the last dependency on the mobile app.

**Independent Test**: Submit correct credentials and confirm a usable account
token is returned; submit deliberately wrong credentials and confirm the service
reports an authentication failure (not a crypto/transport error), proving the
login envelope itself is correct.

**Acceptance Scenarios**:

1. **Given** correct account credentials, **When** the program logs in, **Then**
   it receives a valid account token usable to sign later requests.
2. **Given** an incorrect password, **When** the program logs in, **Then** the
   service reports an authentication failure — demonstrating the request was
   well-formed and reached account validation.

---

### User Story 3 - Complete the key exchange into session material (Priority: P2)

After the lock has produced its own ephemeral public key over BLE (feature 002),
the integrator submits it to the cloud and receives the derived session material
that secures all subsequent lock communication.

**Why this priority**: This closes the key-agreement loop and yields the keys the
control channel (feature 003) consumes. It is P2 only because it depends on the
BLE handshake having produced the lock's public key first.

**Independent Test**: Given a device public key from a live handshake, request
verification and confirm the cloud returns session material of the expected
shape (session key, nonce, verify data).

**Acceptance Scenarios**:

1. **Given** a valid device public key from a live session, **When** the program
   requests verification, **Then** the cloud returns session material containing
   a session key, a nonce, and verify data of the documented sizes.

---

### Edge Cases

- **Expired or revoked token**: a signed request with a stale token is rejected
  by the service; the program surfaces the service's error code rather than
  crashing.
- **Wrong region base URL**: a request routed to the wrong regional endpoint
  fails to authenticate; region selection is an explicit input.
- **Malformed device identifier**: the cloud returns an application-level error;
  the program distinguishes it from a transport failure.
- **Signature over ciphertext confusion**: even when the request body travels
  encrypted, the signature is computed over the plaintext body — a signature
  computed over ciphertext is rejected.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST authenticate an account using its username and
  password and return an account token, with no dependency on the mobile app.
- **FR-002**: The system MUST protect the password in the login request using the
  same envelope the official app uses, so the service accepts it.
- **FR-003**: The system MUST attach a valid signature to every authenticated
  request such that the service accepts it, and a tampered or mis-computed
  signature MUST be rejected by the service.
- **FR-004**: The system MUST compute the request signature over the plaintext
  request body even when the transmitted body is encrypted.
- **FR-005**: The system MUST retrieve a session's ephemeral public key for a
  device the account owns, returned as a 65-byte uncompressed SECP256R1 point.
- **FR-006**: The system MUST submit a device-produced public key and receive the
  derived session material (session key, nonce, verify data) for that session.
- **FR-007**: The system MUST allow the caller to select the account's service
  region, and MUST route requests to that region's endpoint.
- **FR-008**: The system MUST surface service-level error codes to the caller so
  authentication, signature, and ownership failures are distinguishable from
  transport failures.
- **FR-009**: The system MUST NOT persist or log real secrets (tokens, keys,
  device identifiers); all such values are provided at call time by the caller
  (Constitution Principle I).

### Key Entities

- **Account credentials**: the username/password and the derived account token
  that authorize requests. Supplied by the caller at runtime; never stored.
- **Signing context**: the per-account values (app identity, key, token, user and
  client identifiers) combined with a per-request nonce and timestamp to produce
  the request signature.
- **Session public key (cloud)**: the 65-byte ephemeral key the cloud issues to
  begin a BLE session.
- **Device public key (lock)**: the 65-byte ephemeral key the lock produces during
  the BLE handshake, submitted back to the cloud.
- **Session material**: the session key, nonce, and verify data the cloud derives
  and returns; consumed by the BLE handshake and control channel.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A caller with valid credentials can obtain a session public key in a
  single request, with zero use of the official app or a phone.
- **SC-002**: 100% of requests carrying a correctly computed signature are
  accepted by the service; requests with an incorrect signature are rejected
  100% of the time.
- **SC-003**: A login with correct credentials yields a usable token; a login with
  an incorrect password is reported as an authentication failure, not a
  crypto/transport error — demonstrating envelope correctness.
- **SC-004**: A device public key from a live session is exchanged for session
  material of the documented shape (session key, nonce, verify data) on the first
  attempt.
- **SC-005**: No real secret ever appears in committed source, tests, logs, or
  fixtures (verifiable by inspection of the repository).

## Assumptions

- The caller owns the target device and possesses a valid account token captured
  from their own account (credential acquisition is documented in the tutorials,
  not performed by this feature).
- The account's service region is known to the caller and provided explicitly;
  only the region actually used by the project is confirmed, others follow the
  same URL pattern.
- Deriving session material locally from long-term key material is out of scope:
  it was investigated and abandoned because the derivation depends on a
  server-held secret. The cloud remains the authority for session material.
- Network transport (TLS, connectivity) is provided by the environment and is out
  of scope for this feature's logic.
- The BLE handshake that produces the device public key is specified separately
  (feature 002); this feature covers only the cloud side of the exchange.
