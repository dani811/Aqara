# Phase 1 Data Model: TLS certificate verification

**Feature**: 006-tls-verification · **Date**: 2026-08-14

This fix introduces no persisted data and no new public type. The "model" is the
policy decision and its single input.

## Entities

### Connection security policy

The `ssl.SSLContext` handed to every cloud request. Produced by exactly one
factory, `_tls_context()` in `aqara_u200_ble/kdf.py`.

| Attribute | Secure (default) | Downgraded (opt-out active) |
| --- | --- | --- |
| `check_hostname` | `True` | `False` |
| `verify_mode` | `ssl.CERT_REQUIRED` | `ssl.CERT_NONE` |
| Trust store | platform default | not consulted |
| Side effect | none | warning on stderr |

**Validation rule**: `check_hostname` must be cleared before `verify_mode` is set
to `CERT_NONE` (Python raises `ValueError` otherwise).

### Opt-out switch

| Field | Value |
| --- | --- |
| Name | `U200_INSECURE_TLS` |
| Source | process environment, read per request |
| Affirmative values | `1`, `true`, `yes`, `on` — case-insensitive, whitespace-trimmed |
| Every other value | policy stays secure (unset, empty, `0`, `false`, typos) |
| Scope | cloud HTTPS requests only; no effect on BLE |

## State transitions

```text
                 flag absent / empty / falsey / unrecognised
    request  ────────────────────────────────────────────────►  SECURE policy
       │                                                              │
       │  flag ∈ {1,true,yes,on}                                      ├─ ok → response
       └──────────────────────────►  warning on stderr                └─ cert invalid →
                                     DOWNGRADED policy                   RuntimeError
                                              │                          naming the flag
                                              └─ ok → response
                                                 (no verification performed)
```

There is no persistent state: each request re-reads the environment and rebuilds
the context, so toggling the flag takes effect on the next call.

## Relationships

`_post_json` (the single cloud request funnel) → `_tls_context()` → every public
cloud entry point (`login`, `cloud_get_public_key`, `cloud_verify`,
`get_session_material`). No other module constructs an SSL context.
