# Cloud login, signing & KDF

**Layer:** transversal

> The cloud side supplies the ephemeral key material the BLE handshake needs. All
> calls are HTTPS with a signed header set. No example here carries a real token,
> key, or account identifier (Constitution Principles I & IV).

## Endpoints

| Endpoint | Purpose | Returns |
| --- | --- | --- |
| `POST /user/guard-code/login` | account login | JWT token |
| `POST /dev/bluetooth/login/assure/publickey` | request ephemeral EC key | `cloudPublicKey` |
| `POST /dev/bluetooth/login/assure/verify` | verify the lock's pubkey | `sessionKey`, `nonce`, `verifyData` |
| `GET  /dev/bluetooth/query?did=…` | device material | device address, `ltmk` |
| `GET  /app/dev/query/detail` | device detail (observed) | model/area (`"area":"EU"`) |
| account **device inventory** | list of account devices | **not captured yet** — see `tools/probe_cloud_endpoints.py` |

The `publickey` → (BLE handshake) → `verify` pair is the KDF: `publickey` issues
an ephemeral EC key to send to the lock, and `verify` takes the lock's returned
key and derives the session material.

## Request signing

Each request carries `Appid`, `Nonce`, `Time`, `Token`, `UserId`, and a `Sign`:

```text
Sign  = MD5("Appid={appid}&Nonce={nonce}&Time={time}&Token={token}&{body}&{appkey}")
Nonce = MD5(Requestid).upper()
```

- The signature is computed over the **plaintext** body even when the body
  travels encrypted.
- `GET` requests sign the query string in the body position.
- **Login is unauthenticated**: with no token, the `Token=` field is omitted
  entirely from the preimage (no `Token`/`UserId`/`Requestid` headers).

## Account login (the crypto that bites)

`POST /user/guard-code/login` exchanges account + password for a JWT. The body is
double-wrapped:

```text
password_field = base64( RSA_PKCS1v15( MD5(password) as lowercase hex, 32 ASCII chars ) )
body           = x-aes128gcm( {"account","district","encryptType":2,"guardCode","password"} )
```

The one detail that costs days if missed: the RSA plaintext is **`MD5(password)`
in lowercase hex (32 ASCII characters), not the raw password**. Encrypting the
raw password makes the server compare it against the expected MD5 and reject
*every* credential — including correct ones — with an ambiguous "wrong password
or unregistered account" code. Confirmed by hooking the app's RSA call: the input
for a test password was its lowercase-hex MD5. `status: confirmed`.

## Session material

`sessionKey`, `nonce`, and `verifyData` come back from `verify` and are derived
**cloud-side** from `verifyData` plus the lock's ephemeral public key. They are
**not reusable across sessions** — each handshake needs a fresh exchange. Deriving
the session key locally was investigated and abandoned (a server-held secret is
involved); the cloud remains authoritative.

## Transport security

Verify the server's TLS certificate chain **and** hostname on every call. This
matters more than in an average client: the `verify` response carries the material
that opens a physical door, so an unauthenticated channel would let anyone on the
path impersonate the cloud. Provide an explicit, per-request-warned opt-out only
for machines whose CA store is genuinely unusable, and parse that opt-out
fail-safe (only an explicit affirmative disables it) so a typo cannot silently
downgrade the connection.

## Porting note

Endpoints, the signing preimage, and the login crypto are account/cloud concerns,
not lock-specific — they are expected to be identical for other Aqara devices in
the same region. Only the EU region is confirmed; other regional endpoints follow
the same URL pattern but are `unverified`.


## Device inventory (feature 016 — pending capture)

The app lists every device of the account (did, model `lumi.lock.*`, name, room,
online) but the endpoint is **not captured**. Discover it read-only with your own
session: `tools/probe_cloud_endpoints.py` (you run it with your credentials; the
assistant never sees them). It probes candidate paths, prints each response shape,
and writes a **sanitized** dump under the git-ignored `captures/` tree. Once the
shape is known, `AqaraCloud.list_devices()` can be implemented from that evidence.
