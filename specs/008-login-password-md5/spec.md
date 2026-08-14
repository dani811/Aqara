# Feature Specification: Login password MD5 fix

**Feature Branch**: `feature/008-login-password-md5`

**Created**: 2026-08-14

**Status**: Retrospective (documents a fix already implemented and verified end-to-end; see Principle III)

**Input**: User description: "Corregir el login de cuenta para que sea realmente autónomo. El endpoint POST /user/guard-code/login espera que el campo `password` sea RSA-1024/PKCS#1v1.5 del MD5 de la contraseña en hex minúscula, NO la contraseña en crudo."

## Context

Feature 001 (cloud login & key derivation) shipped a login that never actually
returned a token: the account-login request encrypted the raw password with the
login RSA key, but the server expects the RSA plaintext to be `MD5(password)` in
lowercase hex. The mismatch made the cloud answer `code=810` ("Error de
contraseña o cuenta no registrada") for **every** credential, including ones the
official app accepts. Because `810` is also the answer for a genuinely wrong
password or an unregistered account, the failure was long misread as "the
envelope is correct, only the password is wrong", and the `login()` path shipped
with no test exercising it. This feature closes that gap so Feature 001's
User Story 2 (correct credentials → usable token) is finally satisfied.

The correct transform was already recorded in the reverse-engineering notes
(`docs/login-cuenta.md` §2, from a Frida capture of `Cipher.doFinal`) but had
never been applied to the code.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Mint a token from account + password, headless (Priority: P1)

An integrator holding a valid Aqara account (email + password) and the
installation identifiers (appid, appkey, client id, phone id) exchanges those
credentials for an account token from Python alone, with no mobile app and no
previously captured token.

**Why this priority**: the account token is the entry credential for every
signed cloud request. Without a working autonomous login, a dead token is a dead
end that forces a Frida capture from the phone.

**Independent Test**: run the token-refresh path with correct credentials
against the real EU server and confirm it returns `code=0` and a usable JWT;
run it with a deliberately wrong password and confirm it is reported as an
authentication failure, not a crypto/transport error.

**Acceptance Scenarios**:

1. **Given** correct account credentials and installation identifiers, **When**
   the integrator logs in, **Then** the cloud returns a usable account token
   (a JWT whose account claim matches the credentials).
2. **Given** an incorrect password, **When** the integrator logs in, **Then**
   the result is reported as an authentication failure (`code=810`) surfaced
   distinguishably from a transport or crypto error.
3. **Given** a dead stored token, **When** the integrator refreshes, **Then**
   the refresh succeeds without any previous live token (the request is
   unauthenticated).

### Edge Cases

- The password contains non-ASCII or symbol characters: the transform hashes the
  UTF-8 bytes of the password, so any password the app accepts is handled.
- `code=810` is ambiguous (wrong password **or** unregistered account **or**,
  before this fix, a malformed request): user-facing messaging MUST NOT claim
  "wrong password" as the sole cause.
- The stored token's `exp` claim still shows time remaining but the token was
  invalidated by a login elsewhere (`code=108`): out of scope here, but the
  refresh path is the remedy.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The account-login request MUST place, in the encrypted `password`
  field, the RSA-1024/PKCS#1 v1.5 ciphertext of `MD5(password)` rendered as
  lowercase hexadecimal (32 ASCII characters) — never the raw password bytes.
- **FR-002**: With correct credentials the login MUST yield a usable account
  token; with an incorrect password it MUST surface an authentication failure
  distinguishable from transport/crypto errors.
- **FR-003**: The login MUST remain unauthenticated (no prior token required):
  no Token/UserId/Requestid headers and the `Token=` field omitted from the
  signature preimage.
- **FR-004**: The password MUST NOT appear in clear anywhere in the request
  body, logs, or stored files.
- **FR-005**: User-facing handling of `code=810` MUST describe both plausible
  causes (wrong password or unregistered account) rather than asserting a single
  cause.
- **FR-006**: The pure transform (`MD5(password)` hex → RSA plaintext) MUST be
  covered by a test that pins the plaintext shape (lowercase-hex MD5, not the raw
  password) using a throwaway non-credential password, without performing network
  I/O and without embedding any real account password.
- **FR-007**: Documentation asserting login behavior (library docstrings, tool
  README, protocol docs) MUST match the verified reality and MUST NOT claim
  autonomous login works by any evidence other than a `code=0` token.

### Key Entities *(include if feature involves data)*

- **Account credential**: email/account identifier + password; the password is
  never stored and only ever leaves as `RSA(MD5(password))`.
- **Account token**: the JWT returned on success; the entry credential for
  signed cloud requests.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A login with correct credentials against the real cloud returns a
  usable token (verified: `code=0`, JWT with matching account claim).
- **SC-002**: A login with an incorrect password is reported as an
  authentication failure, not as a crypto or transport error.
- **SC-003**: The autonomous refresh path requires zero previously captured
  token — account + password + installation identifiers are sufficient.
- **SC-004**: The regression is guarded by a deterministic, network-free test
  that fails if the RSA plaintext reverts to the raw password.

## Assumptions

- The installation identifiers (appid, appkey, client id, phone id) and the
  login RSA public key are already available in `.env` / the library, bootstrapped
  by the existing one-time Frida capture (out of scope here).
- The default region is EU (`rpc-ger.aqara.com`), the region against which the
  fix was verified end-to-end.
- This spec is retrospective: the fix and its tests are already implemented on
  this branch; the spec documents intent and evidence after the fact, per
  Constitution Principle III.
