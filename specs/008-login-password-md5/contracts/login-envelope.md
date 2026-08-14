# Contract: account-login envelope

The public surface this feature touches is the account-login call and the pure
password-encryption helper. Both are exported from `aqara_u200_ble`.

## `encrypt_login_password(password: str) -> str`

- **Input**: the account password (UTF-8).
- **Output**: base64 ASCII of the RSA-1024/PKCS#1 v1.5 ciphertext of
  `MD5(password)` rendered as 32 lowercase hex characters.
- **Invariants**:
  - `len(base64.b64decode(output)) == 128` (RSA-1024 block).
  - Non-deterministic: two calls with the same password differ (PKCS#1 v1.5 pad).
  - The RSA plaintext equals `MD5(password).hexdigest()` — verifiable by
    decrypting with a matched key (see the regression test).
  - The raw password never appears in the output or any log.

## `login(account, password, *, appid, appkey, client_id, phone_id, …) -> dict`

- **Request**: `POST {region_base}/user/guard-code/login`, body double-wrapped
  (RSA on `password`, AES-128-GCM on the JSON), **unauthenticated** (no
  Token/UserId/Requestid headers; `Token=` omitted from the signature preimage).
- **Success**: cloud `code=0`; returns the `result` dict including `token`
  (and `userId`, `expiresIn`, `userInfo`).
- **Auth failure**: cloud `code=810`; raised as a `RuntimeError` that names the
  endpoint and code, distinguishable from transport/crypto errors. The message
  MUST NOT assert "wrong password" as the sole cause (it also means an
  unregistered account).
- **No prior token required**: a dead stored token does not block the refresh.

## Observed reference

The RSA input captured from the official app for a test password was that
password's lowercase-hex MD5 (32 ASCII chars), not the raw password. The
regression test pins this *shape* using a throwaway non-credential password; no
real account password is embedded (Constitution Principle I).
