# Phase 0 Research: Login password MD5 fix

No open `NEEDS CLARIFICATION` remained in the Technical Context; this phase
records the one decision that mattered and the evidence behind it.

## Decision: RSA plaintext is `MD5(password)` in lowercase hex, not the raw password

- **Decision**: `encrypt_login_password(password)` computes
  `hashlib.md5(password.encode("utf-8")).hexdigest()` (32 lowercase hex chars),
  then RSA-1024/PKCS#1 v1.5-encrypts those 32 ASCII bytes, base64 of the result.
- **Rationale**: The Aqara cloud decrypts the RSA `password` field and compares
  it against the MD5 it expects. Feeding the raw password makes every comparison
  fail with `code=810` ("Error de contraseña o cuenta no registrada"),
  regardless of whether the password is correct. This is the single reason the
  login never produced a token.
- **Evidence**:
  - Reverse-engineering note (original project) from a Frida capture of
    `Cipher.doFinal` with `alg=RSA/ECB/PKCS1Padding`: the RSA input for a test
    password was that password's MD5 in lowercase hex (32 ASCII chars), not the
    password bytes. (The captured plaintext password is a real test credential
    and is deliberately not reproduced here — Constitution Principle I.)
  - Reproduced generically: for any password, `MD5(password).hexdigest()` matches
    the shape fed into the RSA.
  - End-to-end: with the fix, correct credentials returned `code=0` and a valid
    JWT from the real EU server; a wrong password returned `code=810` (a genuine
    authentication failure, not a malformed request).
- **Alternatives considered and rejected** (from the original probe
  `tools/test_login.py`, which tried all five):
  - raw password / PKCS1 — rejected: `code=810` for every credential.
  - raw password / OAEP — rejected: wrong padding scheme.
  - `MD5` **upper**-case hex / PKCS1 — rejected: case mismatch.
  - `MD5` lower-case hex / OAEP — rejected: wrong padding scheme.
  - `MD5` lower-case hex / **PKCS1** — **selected**: matches the capture and the
    live `code=0`.

## Secondary observations (not part of this feature's scope)

- `code=810` is ambiguous: the cloud returns it for a wrong password AND for an
  unregistered account (confirmed live with a deliberately nonexistent account).
  Consequence captured in FR-005: user-facing messaging must not claim "wrong
  password" as the sole cause.
- Region probe (incidental): EU and KR reach Aqara's application layer; the
  inferred US and CN hostnames answered an nginx `500`. Only the EU correction
  is in scope; the region note is recorded in `kdf.py` comments, not here.
