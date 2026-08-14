# Roadmap & known debt

Durable record of what is done, what is pending, and the known limitations —
so nothing lives only in chat or an assistant's memory.

## Status

The library is fully migrated to Spec-Driven Development and green:

- Constitution v1.0.0 + features 001–005 (specify → clarify → plan → tasks →
  implement), each merged to `develop` via `--no-ff`.
- Feature 006 (`fix/tls-verification`) closes the high-priority security debt.
- Tooling (`tools/`) and documentation migrated.
- Gates: `ruff check` clean · `mypy --strict` clean · 70 unit tests · 0 secrets.

## Resolved

### ✅ Security debt — TLS verification (feature 006)

The cloud client disabled certificate and hostname verification unconditionally
("TEMPORARY for development/testing on macOS"), a real MITM risk on every call —
including the `verify` response that carries the door-opening session material.
It had been migrated **verbatim** under the "no logic change" rule, so the fix
was a deliberate behavior change on its own branch.

Now: verification is on by default from a single policy factory
(`kdf._tls_context`), the insecure path survives only as the explicit,
per-request-warned `U200_INSECURE_TLS` opt-out (fail-safe parsing), and a
certificate failure raises an error naming both plausible causes and the flag.
See [`specs/006-tls-verification/`](../specs/006-tls-verification/spec.md) and
[cloud-api.md](protocol/cloud-api.md#transport-security).

## Pending work

### 1. `ruff format --check` fails on 7 pre-existing files

**Priority: low.** `ruff check` is clean, but `ruff format --check .` reports 7
files it would reformat — `aqara_u200_ble/{kdf,scanner,session}.py`,
`tools/{bumble_lock,run_hook}.py`, `docs/tutorials/end-to-end-unlock.md`, and
`tests/test_kdf.py`'s older blocks. These predate feature 006 (verified against
a clean `develop`); the migration recorded the gate as green using a different
formatter run. Fix on a `chore/*` branch with a single mechanical
`ruff format .` — deliberately *not* mixed into a security fix, and worth a
skim of `session.py`'s CRC table diff, which is frozen crypto data.

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
