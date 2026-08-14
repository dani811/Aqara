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

> Tokens are invalidated when the account logs in elsewhere. Capture yours
> fresh (see the tutorials) and put it in `.env` — never in code.
