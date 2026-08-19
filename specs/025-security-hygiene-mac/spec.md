# Feature Specification: Security Hygiene — Sanitize Leaked Device MAC & Prevent Recurrence

**Feature Branch**: `chore/025-security-hygiene-mac`

**Created**: 2026-08-19

**Status**: Draft

**Input**: User description: "Cleanup phase 1 — Security hygiene: sanitize the leaked real device MAC (AA:BB:CC:DD:EE:FF, hardcoded in tests/test_cli.py, committed in 4afdcc5, pushed to the public repo dani811/Aqara — a Constitution Principle I violation) and add a guard that prevents any real-looking secret/MAC from recurring in tracked files. Behavior of the library and wire protocol must not change."

## Overview

The project constitution's Principle I (Security & Secret Hygiene, NON-NEGOTIABLE)
forbids committing device identifiers — MAC addresses "without limitation" —
because the artefacts here control a physical door. A regression fix
(commit `4afdcc5`, `fix(020)`) hardcoded the reference lock's **real** BLE MAC
`AA:BB:CC:DD:EE:FF` into `tests/test_cli.py` (lines 175, 194, 196). That value has
been verified against the lock's live advertisement and is now present in the
public GitHub repository. This feature removes the leaked value from the current
tree and installs an automated guard so the class of mistake cannot silently
recur. It changes no library behaviour and no wire bytes.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The leaked MAC no longer appears in tracked source (Priority: P1)

As the project maintainer, I need the real lock MAC gone from every tracked file
so the public repository stops disclosing a real device identifier, restoring
compliance with Principle I.

**Why this priority**: This is the actual leak. Until it is removed from `HEAD`,
the repository continues to publish a real device identifier on every clone. It
is the reason this feature exists.

**Independent Test**: Grep the whole tracked tree for `AA:BB:CC:DD:EE:FF`; expect
zero matches. Run the test suite; `tests/test_cli.py` still passes and still
exercises the same CLI env-MAC behaviour, now using an obviously-fake placeholder.

**Acceptance Scenarios**:

1. **Given** the current tree contains `AA:BB:CC:DD:EE:FF` in `tests/test_cli.py`,
   **When** the sanitization is applied, **Then** a case-insensitive search of all
   git-tracked files for that exact string returns no matches.
2. **Given** the placeholder replaces the real MAC, **When** the test suite runs,
   **Then** the affected tests still pass and still assert the same CLI
   env-var-to-connect behaviour (the placeholder is threaded through the same
   assertions), so coverage is preserved.
3. **Given** the placeholder value, **When** a human inspects it, **Then** it is
   recognisably synthetic and consistent with the placeholders already used in
   sibling tests (the `AA:BB:CC:DD:EE:FF` family), not a plausibly-real address.

---

### User Story 2 - No other real secret is hiding in the tree (Priority: P1)

As the maintainer, I need confidence that the MAC was the only leak, so I am not
left with a false sense of safety after fixing the one value I already know about.

**Why this priority**: Fixing only the known value while another secret sits
undiscovered would defeat the purpose. The audit is what turns "fixed the MAC" into
"the tree is clean."

**Independent Test**: A one-shot audit sweep over tracked files for real-looking
MACs, tokens, private keys, non-author emails, device ids, and capture blobs
produces a reviewed report with every hit either eliminated or justified as a
documented placeholder / public value / the author's own identity.

**Acceptance Scenarios**:

1. **Given** the audit patterns, **When** the sweep runs over all tracked files,
   **Then** every match is triaged to one of: {removed, documented placeholder,
   known-public value (e.g. the login RSA public key), author identity}, with
   nothing left unexplained.
2. **Given** the triage, **When** it completes, **Then** the residual allow-list of
   justified matches is written down (in the spec's evidence or a short note) so a
   future reader understands why each surviving pattern is safe.

---

### User Story 3 - The leak cannot silently recur (Priority: P2)

As the maintainer, I need an automated check that fails when a real-looking
secret or MAC is (re)introduced into tracked files, so Principle I is enforced by
tooling and not only by vigilance.

**Why this priority**: Prevention is what makes the fix durable, but it depends on
the tree first being clean (Stories 1–2). Hence P2.

**Independent Test**: With the guard in place, deliberately introduce a
real-looking MAC into a tracked file and run the guard: it fails and names the
offending file/line. Remove it: the guard passes. The guard runs as part of the
normal test/CI invocation, not as an opt-in extra.

**Acceptance Scenarios**:

1. **Given** the guard exists, **When** the normal test suite runs on a clean tree,
   **Then** the guard passes.
2. **Given** a tracked file is modified to contain a real-looking MAC (any value
   outside the documented placeholder allow-list), **When** the guard runs,
   **Then** it fails and reports the file and line.
3. **Given** a legitimate placeholder (e.g. `AA:BB:CC:DD:EE:FF`) in a tracked file,
   **When** the guard runs, **Then** it does not flag it (no false positive on the
   sanctioned placeholders).
4. **Given** the guard is wired into CI, **When** a push or pull request runs,
   **Then** the guard executes automatically and a failure blocks the green status.

### Edge Cases

- A MAC that legitimately must appear as an example in documentation → must be a
  sanctioned placeholder from the allow-list, otherwise the guard flags it.
- The author's own email (`22160062+dani811@users.noreply.github.com`) appears in `pyproject.toml`
  as package authorship → must be allow-listed as identity, not treated as a leak.
- The embedded login RSA **public** key and `System ID 000102030405` (SoC default)
  are not secrets → must not trip the guard.
- The guard must scan only tracked files, never `.env`, `captures/`, `artifacts/`,
  or other gitignored paths (those legitimately hold real values locally).
- Binary/large tracked files (if any) must not break or hang the guard.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The exact string `AA:BB:CC:DD:EE:FF` (case-insensitive) MUST NOT
  appear in any git-tracked file after this feature.
- **FR-002**: Every occurrence of that MAC in `tests/test_cli.py` MUST be replaced
  with a single obviously-fake placeholder consistent with the existing
  `AA:BB:CC:DD:EE:FF` placeholder convention, preserving each test's intent and
  assertions.
- **FR-003**: The test(s) that used the MAC MUST continue to exercise the same CLI
  env-MAC behaviour and MUST pass after the replacement (no loss of coverage, no
  skipped tests).
- **FR-004**: A one-time audit MUST sweep all tracked files for real-looking MACs,
  auth tokens, private keys, device ids, capture blobs, and non-author emails, and
  MUST classify each hit as removed / documented-placeholder / known-public /
  author-identity, leaving no unexplained match.
- **FR-005**: An automated guard MUST fail when a real-looking MAC (or other
  configured secret pattern) is present in a tracked file, and MUST report the
  offending file and line.
- **FR-006**: The guard MUST recognise a small, explicit allow-list of sanctioned
  placeholders and known-public/identity values, so those do not cause failures.
- **FR-007**: The guard MUST run as part of the project's normal automated checks
  (the test suite) AND be wired into CI so it runs on every push / pull request.
- **FR-008**: The guard MUST inspect only git-tracked files and MUST NOT read
  gitignored paths (`.env`, `captures/`, `artifacts/`, caches).
- **FR-009**: No library module, public API, or wire-protocol byte may change; the
  diff is confined to test data, the new guard, its allow-list, and CI wiring.
- **FR-010**: The feature MUST document, as a flagged follow-up for the user to
  decide, that sanitizing `HEAD` does not purge the value from existing git
  history; history rewrite is explicitly out of scope here.

### Key Entities *(include if feature involves data)*

- **Leaked value**: the real lock MAC `AA:BB:CC:DD:EE:FF` — the single known
  secret being removed.
- **Placeholder allow-list**: the finite set of sanctioned non-secret patterns the
  guard tolerates (fake MAC family, the login RSA public key, SoC default System
  ID, the author's own email).
- **Secret guard**: the automated check (test + CI step) that scans tracked files
  and fails on a real-looking secret outside the allow-list.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A case-insensitive search of all tracked files for `AA:BB:CC:DD:EE:FF`
  returns 0 matches.
- **SC-002**: The full test suite passes (all 197+ tests), with the previously
  MAC-bearing tests still asserting the same behaviour — 0 tests removed or skipped
  to achieve the fix.
- **SC-003**: Deliberately inserting a real-looking MAC into any tracked file causes
  the guard to fail and name the file/line 100% of the time; removing it restores a
  passing guard.
- **SC-004**: The guard produces 0 false positives on the sanctioned placeholder /
  public / identity values present in the tree today.
- **SC-005**: The audit report accounts for 100% of pattern matches in the tracked
  tree (each either removed or explicitly justified).
- **SC-006**: CI runs the guard on every push / PR (verifiable in the workflow run
  log), and a seeded secret makes the run red.

## Assumptions

- Rewriting existing git history to purge the MAC from past commits is a separate,
  user-owned decision and is **out of scope** for this feature; this feature makes
  `HEAD` clean and prevents recurrence. The value is a BLE MAC, not a credential
  that by itself grants access, so a HEAD-only fix is an acceptable minimum while
  the history decision is pending.
- The obviously-fake placeholder `AA:BB:CC:DD:EE:FF` (already used in sibling
  tests) is an acceptable substitute; the tests do not depend on the specific MAC
  value, only on it being threaded consistently through env → connect.
- The guard is a lightweight pattern check over tracked files (a pytest test plus a
  CI step), not a full entropy-based secret scanner; the project's threat model is
  "no real device/account artefact in version control," which pattern matching over
  the known shapes (MAC, token, key headers, capture extensions) covers.
- The author identity `22160062+dani811@users.noreply.github.com` in packaging metadata is intended
  and allow-listed, not a leak.
- The project currently has no test CI (only `publish.yml`); wiring the guard into
  CI implies adding a minimal test/lint workflow, which is in scope insofar as it
  hosts the guard (a broader test-CI feature remains a later cleanup phase).

## Out of Scope

- Rewriting or force-pushing git history (`git filter-repo`/BFG) to purge the MAC
  from past commits — flagged for the user's decision, not done here.
- The architecture and dead-code cleanup blocks (layering inversion, `kdf.py` /
  `session.py` splits, dead-symbol removal, `__all__` slimming) — later phases.
- Any change to library behaviour, public API surface, or wire protocol.
