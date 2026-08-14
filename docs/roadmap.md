# Roadmap & known debt

Durable record of what is done, what is pending, and the known limitations —
so nothing lives only in chat or an assistant's memory.

## Status

The library is fully migrated to Spec-Driven Development and green:

- Constitution v1.0.0 + features 001–005 (specify → clarify → plan → tasks →
  implement), each merged to `develop` via `--no-ff`.
- Feature 006 (`fix/tls-verification`) closes the high-priority security debt;
  feature 007 puts the unlock choreography under test.
- Tooling (`tools/`) and documentation migrated.
- Gates: `ruff check` + `ruff format --check` clean · `mypy --strict` clean ·
  91 unit tests · 0 secrets.

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

### ✅ Formal Spec Kit analysis (`/speckit-analyze`)

The five migrated features were produced by following each `SKILL.md` by hand,
because the skills had been installed mid-session and the loader never registered
them. In a fresh session they do register, and `/speckit-analyze` has now run
over 001–005 (and over 006, before it was implemented).

Result: **0 critical findings, 0 constitution conflicts, 0 unresolved
clarification markers**; 36 of 38 functional requirements had explicit task
coverage, and the test suite turned out to be *broader* than the tasks asked for
(nine tests no task requested). The findings were about traceability, not
correctness, and are fixed in `docs/analyze-remediation`:

- all 81 tasks across 001–005 were still `[ ]` despite being implemented and
  merged — now marked done;
- 21 tasks named tests that never existed under that name (`test_build_unlock` vs
  `test_build_unlock_payload_and_prefix`, …) — now aligned, so a `pytest -k`
  copied from `tasks.md` actually runs;
- spec 001 carried stale cross-references (calling the BLE handshake "feature
  002") and, more importantly, the assumption that TLS was "out of scope" —
  the premise that let the 006 defect through review. Both corrected in place.

The two coverage gaps it found are closed (see below).

### ✅ Coverage gaps from the analysis (`chore/coverage-gaps`)

The two requirements `/speckit-analyze` found implemented but untasked are
closed:

- **001 FR-008** (service-level error codes) had no test at all — the gap that
  mattered, since the cloud answers HTTP 200 with a non-zero `code` for expired
  tokens, bad signatures, and ownership failures. Four tests now pin that a
  service error raises with its code, message, and endpoint, and that its wording
  stays distinguishable from a transport failure; plus the success paths
  (`code` 0/"0"/absent, flat payloads with no `result` envelope).
- **004 FR-003** (the retained `app_token` argument) was already tested; only the
  task entry was missing.

No production code changed — the behaviour was already correct, it was simply
unverified. 76 tests (70 → 76).

### ✅ Formatter gate (`chore/ruff-format`)

`ruff check` was clean but `ruff format --check .` flagged 7 files it would
reformat — a discrepancy that predated feature 006 (verified against a clean
`develop`); the migration had recorded the gate as green from a different
formatter run.

Fixed mechanically. Two things were done deliberately rather than blindly:

- `session.py`'s CRC-16 table is fenced with `# fmt: off` / `# fmt: on` so it
  keeps its captured 16-per-row shape. Left to the formatter it became 256
  single-value lines — noise that would hide tampering in a table that is frozen
  protocol data (Article V).
- The result was proven behaviour-preserving by comparing the **AST** of every
  reformatted Python file against its pre-change version (all identical) and
  re-checking the CRC table's hash. Whitespace only.

## Pending work

### 1. Push `develop` to the remote

All work is local. Push `develop` to `github.com/dani811/Aqara` (and optionally
the merged branches) when ready to publish.

### 2. Branch pruning (optional)

The merged `feature/001…005`, `chore/*`, and `docs/*` branches can be deleted for
a tidier list; their history is preserved in `develop`. `archive/manual-migration`
is intentionally kept as the reverse-engineering backup.

## Known limitations (by design)

- **The radio is not unit-tested — the choreography now is.** Narrowed by feature
  007. `run_authenticated_lock_operation`'s *sequence* (notification order, the
  public-key and verify frames, tolerance of the lock's empty ACKs, the encrypted
  control write, subscription cleanup) is asserted against a scripted stand-in
  lock in `tests/test_session_flow.py`, with no radio and no network. What stays
  hardware-only is whether a **real** U200 accepts that sequence — timing, the
  radio, and the lock's firmware. Only the live tutorial run is evidence of that.
  The passive scan remains untested for the same reason.
- **Only the EU region is confirmed.** Other regional endpoints follow the same
  URL pattern but are unverified (see
  [spec 001, Assumptions](../specs/001-cloud-kdf-login/spec.md)).
- **Session material is cloud-derived.** Deriving `sessionKey` locally was
  investigated and abandoned (server-held secret); the cloud remains authoritative.
