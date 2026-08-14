# Cloud API

The Aqara cloud provides the ephemeral key material for the BLE handshake. All
calls are HTTPS with a signed header set; no `requests` dependency — the
library uses `urllib`.

## Endpoints used

| Endpoint | Purpose | Returns |
| --- | --- | --- |
| `POST /user/guard-code/login` | account login | JWT token |
| `POST /dev/bluetooth/login/assure/publickey` | request ephemeral EC key | `cloudPublicKey` |
| `POST /dev/bluetooth/login/assure/verify` | verify lock pubkey | `sessionKey`, `nonce`, `verifyData` |
| `GET  /dev/bluetooth/query?did=…` | device material | `macAddress`, `ltmk` |

## Request signing

Each request carries `Appid`, `Nonce`, `Time`, `Token`, `UserId`, and a `Sign`:

```text
Sign = MD5("Appid={appid}&Nonce={nonce}&Time={time}&Token={token}&{body}&{appkey}")
Nonce = MD5(Requestid).upper()
```

- Computed over the **plaintext** body even when the body travels encrypted.
- `GET`s sign the query string as the body.
- Without a token (login) the `Token=` field is omitted entirely.

Implemented as `kdf.compute_sign` / `kdf.make_local_signer`. Login encrypts the
password with RSA and the body with AES-128-GCM (`kdf.encrypt_login_password`,
`kdf.aes128gcm_encrypt_body`).

## Account login

`POST /user/guard-code/login` exchanges account + password for a JWT, with no
previous token. The body is double-wrapped:

```text
password_field = base64( RSA_PKCS1v15( MD5(password).hexdigest() ) )   # lowercase hex, 32 ASCII chars
body           = x-aes128gcm( {"account","district","encryptType":2,"guardCode","password"} )
```

The RSA plaintext is **`MD5(password)` in lowercase hex (32 ASCII chars), not the
raw password** — confirmed by a Frida capture of `Cipher.doFinal` in the app (the
RSA input for a test password was its lowercase-hex MD5, not the password bytes).
Verified end-to-end against the real EU server: correct credentials return
`code=0` and a usable token.

> **Bug history (2026-08-14).** `encrypt_login_password` RSA-encrypted the raw
> password, so the server compared it against the expected MD5 and answered
> `code=810` for *every* credential — including valid ones. `810` is ambiguous
> (wrong password **or** unregistered account: a nonexistent account returns the
> same code), which is why the failure was long misread as "the envelope is
> right, the password is wrong". The fix simply applied the RE note's own
> finding (`docs/login-cuenta.md` §2), which had never made it into the code.

> Tokens are invalidated when the account logs in elsewhere. Capture yours
> fresh (see the tutorials) and put it in `.env` — never in code.

## Transport security

Every cloud call verifies the server's TLS certificate chain against the
platform trust store **and** its hostname. This matters more here than in an
average HTTP client: the `verify` response carries the session material that
opens a physical door, so an unauthenticated channel would let anyone on the
path impersonate the cloud.

One escape hatch exists, for machines whose CA store is unusable:

| Variable | Effect |
| --- | --- |
| `U200_INSECURE_TLS=1` (or `true`/`yes`/`on`) | Disables certificate and hostname checks, printing a warning to stderr on every request |
| unset, empty, `0`, `false`, anything else | Verification enforced (the default) |

Parsing is fail-safe: only an explicit affirmative disables the check, so a typo
cannot silently downgrade the connection. When verification fails, the raised
`RuntimeError` names both plausible causes — a broken local trust store or an
intercepted connection — and the flag.

> **History**: this verification was disabled unconditionally until feature 006
> ([spec](../../specs/006-tls-verification/spec.md)); the code had been migrated
> verbatim from the reverse-engineering phase, where the check had been switched
> off to work around a macOS trust-store problem.
