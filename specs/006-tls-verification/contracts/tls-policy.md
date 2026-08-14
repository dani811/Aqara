# Contract: cloud transport security

**Feature**: 006-tls-verification · **Date**: 2026-08-14

The library's public Python API is unchanged by this fix. What changes is the
*observable contract* of every cloud call and one new environment variable.

## Environment contract

| Variable | Values | Effect | Default |
| --- | --- | --- | --- |
| `U200_INSECURE_TLS` | `1` \| `true` \| `yes` \| `on` (case-insensitive, trimmed) | Disables certificate **and** hostname verification for cloud requests; prints a warning to stderr on every request | unset — verification enforced |
| `U200_INSECURE_TLS` | unset, empty, `0`, `false`, anything else | Verification enforced | — |

Unrecognised values are treated as "off" by design: a typo must never disable
verification.

## Behavioural contract of cloud calls

Applies to `login`, `cloud_get_public_key`, `cloud_verify`, and
`get_session_material` — every function routed through `_post_json`.

| Condition | Before this fix | After this fix |
| --- | --- | --- |
| Valid certificate, trusted CA | succeeds | succeeds — byte-identical request and response |
| Expired / self-signed / untrusted CA | **succeeded silently** | `RuntimeError` naming the cause and `U200_INSECURE_TLS` |
| Hostname mismatch (MITM) | **succeeded silently** | `RuntimeError` naming the cause and `U200_INSECURE_TLS` |
| Any of the above, opt-out active | succeeds | succeeds, with a stderr warning per request |
| Host unreachable / timeout | `RuntimeError` | `RuntimeError` — unchanged, and distinct from a verification failure |

## Error message contract

On a verification failure the raised `RuntimeError` MUST contain:

1. the endpoint URL (as today's transport errors already do),
2. a statement that the server's TLS certificate could not be verified,
3. both plausible causes — an untrusted/misconfigured local trust store, or an
   intercepted connection,
4. the literal string `U200_INSECURE_TLS` as the deliberate override.

## Non-contract (explicitly unchanged)

Request bodies, `Sign`/`Nonce`/`Time` headers, `compute_sign` derivation,
`x-aes128gcm` body encryption, gzip handling, timeouts, and every BLE-side byte.
This fix is invisible on the wire against a non-hostile network.
