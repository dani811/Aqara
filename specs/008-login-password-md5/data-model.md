# Phase 1 Data Model: Login password MD5 fix

This feature adds no new persistent entities; it corrects the transform applied
to one field of an existing request. The relevant data shapes:

## Account credential (input, transient)

| Field | Type | Notes |
|-------|------|-------|
| `account` | string | email / account identifier; travels in the body in clear (inside the AES-GCM envelope) |
| `password` | string | UTF-8; **never** stored, **never** on the wire in clear |

Transform (the fix):

```text
password_field = base64( RSA_PKCS1v15( MD5(password).hexdigest() ) )
                                        └─ 32 lowercase hex ASCII chars ─┘
```

## Login request body (existing, one field corrected)

| Field | Value |
|-------|-------|
| `account` | the account identifier |
| `district` | `"ES"` (default) |
| `encryptType` | `2` (RSA envelope for the password) |
| `guardCode` | `""` unless a second factor is required |
| `password` | the corrected `password_field` above |

The whole body is then AES-128-GCM wrapped (`x-aes128gcm`) — unchanged by this feature.

## Account token (output)

| Field | Type | Notes |
|-------|------|-------|
| `token` | JWT string | success credential; its `account` claim matches the input account |
| `userId` | string | returned alongside the token; used to sign later authenticated requests |
| `expiresIn` | number | server-reported lifetime (advisory; a login elsewhere invalidates the token regardless) |

## State transition

```text
credentials ──login──▶ code=0  → token (usable)
                   └──▶ code=810 → authentication failure (wrong password OR unregistered account)
```

Before the fix, the second edge was taken for **all** inputs. After the fix,
correct credentials take the first edge.
