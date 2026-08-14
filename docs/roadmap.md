# Roadmap & known debt

Durable record of what is done, what is pending, and the known limitations —
so nothing lives only in chat or an assistant's memory.

## Status

The library is fully migrated to Spec-Driven Development and green:

- Constitution v1.0.0 + features 001–005 (specify → clarify → plan → tasks →
  implement), each merged to `develop` via `--no-ff`.
- Tooling (`tools/`) and documentation migrated.
- Gates: `ruff` clean · `mypy --strict` clean · 51 unit tests · 0 secrets.

## Pending work

### 1. Security debt — TLS verification disabled (fix/tls-verification)

**Priority: high.** The cloud client disables TLS certificate verification:

- [`aqara_u200_ble/kdf.py:494`](../aqara_u200_ble/kdf.py#L494) —
  `ssl_context.check_hostname = False`
- [`aqara_u200_ble/kdf.py:495`](../aqara_u200_ble/kdf.py#L495) —
  `ssl_context.verify_mode = ssl.CERT_NONE`

The inline comment marks it "TEMPORARY for development/testing on macOS". It is a
real MITM risk. It was migrated **verbatim** (the "no logic change" rule), so
fixing it is a behavior change and belongs on its own `fix/tls-verification`
branch: restore default verification, allow an explicit opt-out only via an
environment flag, and add a test.

### 2. Push `develop` to the remote

All work is local. Push `develop` to `github.com/dani811/Aqara` (and optionally
the merged branches) when ready to publish.

### 3. Formal Spec Kit analysis (`/speckit-analyze`)

The five features were produced by executing each `SKILL.md`'s steps manually,
because the skills were installed mid-session and the loader did not register
them. In a **fresh session** with the repo open, the `/speckit-*` skills load at
startup; run `/speckit-analyze` over the five features for the formal
spec↔plan↔tasks↔constitution consistency report (and optionally
`/speckit-checklist`). See [tools/](../tools/README.md) is unrelated; this is the
`.claude/skills/speckit-*` set.

### 4. Branch pruning (optional)

The merged `feature/001…005`, `chore/*`, and `docs/*` branches can be deleted for
a tidier list; their history is preserved in `develop`. `archive/manual-migration`
is intentionally kept as the reverse-engineering backup.

## Known limitations (by design)

- **Live BLE flow is not unit-tested.** `run_authenticated_lock_operation` and the
  passive scan need real hardware and optional backends; they are validated live,
  not in unit tests (Constitution Principle V). Unit tests cover the pure logic
  (CRC, framing, fragmentation, AES-CCM, signing, lookup).
- **Only the EU region is confirmed.** Other regional endpoints follow the same
  URL pattern but are unverified (see
  [spec 001, Assumptions](../specs/001-cloud-kdf-login/spec.md)).
- **Session material is cloud-derived.** Deriving `sessionKey` locally was
  investigated and abandoned (server-held secret); the cloud remains authoritative.
