# Implementation Plan: TLS certificate verification for cloud requests

**Branch**: `fix/tls-verification` | **Date**: 2026-08-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/006-tls-verification/spec.md`

## Summary

Replace the unconditional "verify nothing" SSL context in the cloud client with a
single policy factory that returns a **verified** `ssl.SSLContext` by default and
downgrades only when `U200_INSECURE_TLS` is explicitly truthy — emitting a stderr
warning each time it does. A certificate failure is re-raised with a message that
names the flag. Nothing else about the request changes: same body, same headers,
same signing, same framing.

## Technical Context

**Language/Version**: Python 3.11+ (developed on 3.14)

**Primary Dependencies**: Standard library only for this change (`ssl`, `os`,
`sys`, `urllib`). No new dependency.

**Storage**: None. The flag is read from the process environment at request time.

**Testing**: `pytest`. Unit tests assert the *policy*, not the network: build the
context with a patched environment (`monkeypatch.setenv` / `delenv`) and assert
`check_hostname` / `verify_mode`, plus the warning on stderr (`capsys`). No socket
is opened — Principle V forbids network I/O in unit tests.

**Target Platform**: Any OS with Python 3.11+; the opt-out exists for macOS
installs whose CA store is unusable.

**Project Type**: Library — one module touched (`aqara_ble/kdf.py`).

**Performance Goals**: Not performance-sensitive. Context construction is
per-request, as it already is today.

**Constraints**:

- No wire-visible change (FR-006): bodies, headers, signing, encoding untouched.
- Single decision point (FR-007): exactly one `ssl.create_default_context()` call
  site in the package.
- Fail safe: any non-affirmative flag value keeps verification on (FR-003).

**Scale/Scope**: ~35 lines added in `kdf.py` (one private factory + error
enrichment), 5 unit tests, `.env.example` + docs entries.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|-----------|------|--------|
| I. Security & Secret Hygiene | No secret touched; the change *strengthens* the threat model ("treat all key material as door keys" — the material now travels over an authenticated channel) | ✅ PASS |
| II. Protocol Fidelity | Transport-layer trust decision only; zero wire bytes, framing, or derivations change. No capture evidence needed because no protocol behaviour changes | ✅ PASS |
| III. Spec-Driven Development | spec → plan → tasks → implement, this document being the plan | ✅ PASS |
| IV. Evidence & Reproducibility | Reproducible by unit test (policy assertions) and by tutorial run; the debt itself is documented in `docs/roadmap.md` | ✅ PASS |
| V. Quality & Standards | Typed, stdlib-only, unit tests assert pure policy with no network I/O; `ruff` + `mypy --strict` gates apply | ✅ PASS |
| VI. Branch & Change Discipline | `fix/tls-verification` (prefixed, non-trunk), merged `--no-ff` | ✅ PASS |

**Post-Phase-1 re-check**: unchanged — the design adds one private function and
one error message; no new dependency, no new module, no protocol surface. ✅ PASS

No violations. Complexity Tracking not required.

### Behaviour-change justification (Principle II nuance)

The 001–005 migration rule was "no logic change", which is why this defect
survived. This feature is *deliberately* a behaviour change, scoped to the
transport's trust decision. It is not a protocol change: an attacker-free network
produces byte-identical traffic before and after. What changes is what happens on
a **hostile or misconfigured** network — previously: silent success; now: a
refusal the operator can override deliberately.

## Project Structure

### Documentation (this feature)

```text
specs/006-tls-verification/
├── plan.md              # This file
├── spec.md
├── research.md          # Phase 0 — flag naming, parsing, failure surfacing
├── data-model.md        # Phase 1 — the policy + flag entities
├── quickstart.md        # Phase 1 — how to validate the fix
├── contracts/
│   └── tls-policy.md    # Phase 1 — env-var contract + observable behaviour
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
aqara_ble/
└── kdf.py               # THIS FIX — `_tls_context()` factory + enriched
                         #   certificate-failure error inside `_post_json`

tests/
└── test_kdf.py          # THIS FIX — policy tests (default, opt-out, falsey,
                         #   unset, warning emitted)

.env.example             # documents U200_INSECURE_TLS with its warning
docs/protocol/cloud-api.md   # transport-security note
docs/tutorials/01-getting-started.md  # troubleshooting entry for cert failures
docs/roadmap.md          # debt item 1 closed
```

**Structure Decision**: The change lives entirely in the existing cloud client
module — the only place in the package that speaks HTTPS. A new module would add
an import edge for ~20 lines of policy; keeping it private in `kdf.py` next to
`_post_json` satisfies FR-007 (one decision point) with the least surface.

## Design decisions

1. **Factory, not a parameter.** `_tls_context()` is module-private and takes no
   arguments. A `verify: bool = True` parameter on `_post_json` would let a
   future call site hard-code insecurity — exactly what FR-002 forbids. The
   environment is the only lever.
2. **Read the environment per call**, matching the existing `U200_DEBUG` pattern.
   No module-level caching: a long-lived process can toggle it, and tests need no
   reload machinery.
3. **Strict truthiness.** `{"1", "true", "yes", "on"}` after `strip().lower()`.
   Everything else — including typos — keeps verification on, so a mistyped flag
   fails safe rather than silently insecure.
4. **Warning to stderr via `print`**, consistent with `U200_DEBUG`'s existing
   output channel in this module. `warnings.warn` would be deduplicated by the
   default filter, contradicting the spec's "every downgraded request is loud".
5. **Error enrichment at the `URLError` boundary.** `urlopen` wraps
   `ssl.SSLCertVerificationError` in `URLError.reason`; the handler detects that
   case and raises a message naming both causes (hostile network vs. broken trust
   store) and the flag, per FR-005.

## Complexity Tracking

> No Constitution Check violations. Section intentionally empty.
