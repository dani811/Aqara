<!--
Sync Impact Report
==================
Version change: (none) → 1.0.0
Rationale: Initial ratification of the project constitution. MAJOR baseline.

Modified principles: n/a (initial adoption)
Added sections:
  - Core Principles I–VI (Security & Secret Hygiene; Protocol Fidelity;
    Spec-Driven Development; Evidence & Reproducibility; Quality & Standards;
    Branch & Change Discipline)
  - Security Requirements
  - Development Workflow
  - Governance
Removed sections: none

Templates / references reviewed for alignment:
  ✅ .specify/templates/spec-template.md — no constitution conflicts
  ✅ .specify/templates/plan-template.md — Constitution Check gate compatible
  ✅ .specify/templates/tasks-template.md — task categories compatible
  ✅ .gitignore / .env.example — enforce Principle I (secret hygiene)

Follow-up TODOs: none
-->

# aqara-u200-ble Constitution

A fully autonomous Python library that controls the Aqara U200 smart lock over
Bluetooth Low Energy (and its supporting cloud KDF/login), reconstructed by
reverse-engineering the official application. This constitution governs how the
project is built, documented, and evolved.

## Core Principles

### I. Security & Secret Hygiene (NON-NEGOTIABLE)

No real secret ever enters version control. This includes — without limitation —
authentication tokens, app keys, app IDs, RSA/AES key material, LTMK, session
keys, device IDs, MAC addresses, user/phone IDs, client IDs, and any raw radio or
network capture. Every sensitive value MUST load at runtime from a local, ignored
`.env` file; `.env.example` documents the required names with placeholder values
only. Captures, logs, and recordings MUST live under gitignored paths and MAY only
be committed after irreversible sanitization. This principle overrides convenience,
velocity, and every other principle when they conflict: if in doubt, do not commit.

Rationale: the artifacts here can unlock a physical door. A single leaked token or
capture is an unrecoverable, real-world security failure, so secret hygiene is
treated as an absolute, not a best-effort, requirement.

### II. Protocol Fidelity

The library MUST reproduce the lock's real protocol exactly as observed:
CRC-16/ARC framing headers, the AES-CCM control channel, and the cloud
AES-GCM + RSA login with its `compute_sign` derivation. Changes are
behavior-preserving by default — a refactor MUST NOT alter wire bytes, framing,
or cryptographic logic. Any change that does alter protocol behavior MUST be
justified by captured evidence demonstrating the real device expects it.

Rationale: correctness here is defined by byte-for-byte agreement with a device we
do not control and cannot query for a spec. Fidelity to captured reality — not
elegance or assumption — is the only source of truth.

### III. Spec-Driven Development

Every capability is built through the Spec Kit flow:
constitution → specify → clarify → plan → tasks → implement. Feature code MUST NOT
be written without an approved spec and plan. Specs that document already
reverse-engineered behavior MUST be marked as retrospective and remain honest
about what was reconstructed after the fact versus designed up front.

Rationale: the project's value is as much in its auditable trail as in its code.
Spec-first work keeps intent, rationale, and implementation traceable, and keeps
retrospective documentation from masquerading as foresight.

### IV. Evidence & Reproducibility

Claims about protocol behavior MUST be backed by documented, sanitized evidence
(captures, decoded frames, derivations). Tutorials and journey documentation MUST
let an independent third party reproduce the results starting from zero, using only
committed material plus their own credentials.

Rationale: reverse-engineering assertions are worthless if unverifiable. Evidence
and reproducibility convert "it worked on my machine" into a durable, checkable
record others can trust and extend.

### V. Quality & Standards

The project MUST use modern Python packaging (`pyproject.toml`), expose a typed
public API, and cover pure logic (CRC, KDF, framing, encoding) with tests. Unit
tests MUST NOT perform network or radio I/O. The codebase follows prevailing
ecosystem best practices for structure, linting, and dependency management.

Rationale: a security-sensitive library must be legible and testable to be
trustworthy. Deterministic tests over pure logic catch protocol regressions
without needing the physical lock in the loop.

### VI. Branch & Change Discipline

No direct commits to root branches (`develop`, `main`). All work happens on
prefixed branches — `feature/NNN-*`, `docs/*`, `chore/*`, `fix/*`, `refact/*` —
where `NNN` matches the Spec Kit feature number. Branches merge into the trunk
with `--no-ff` so history preserves the unit of change.

Rationale: an auditable, reviewable history is part of the deliverable. Prefixed,
non-fast-forward branches keep every change scoped, named, and revertible.

## Security Requirements

- The repository MUST contain a `.gitignore` that excludes `.env`, capture/log
  directories, and any credential material; and a `.env.example` that enumerates
  required variables with non-sensitive placeholders.
- Before any commit, changes MUST be scanned for secrets. A commit that would
  introduce a real secret MUST be blocked and the value moved to `.env`.
- Sanitization of evidence MUST be irreversible (redaction, not encoding) before
  the evidence is committed.
- Threat model: the library authenticates to and commands a physical lock.
  Contributors MUST treat all key material and captures as door keys.

## Development Workflow

- Each capability begins with `/speckit-specify` and proceeds through `clarify`,
  `plan`, `tasks`, and `implement`; `/speckit-analyze` and `/speckit-checklist`
  are used before implementation when scope or risk warrant it.
- The plan's Constitution Check gate MUST pass before implementation. A violation
  MUST be either removed or recorded in the plan's Complexity Tracking with an
  explicit justification.
- Pure protocol logic MUST ship with tests. Changes touching wire bytes or crypto
  MUST reference the capturing evidence in the PR description.
- Code review MUST verify: no secrets introduced, protocol fidelity preserved,
  spec/plan present, and branch naming compliant.

## Governance

This constitution supersedes ad-hoc practice. When any other document, habit, or
convenience conflicts with it, the constitution wins.

Amendments MUST be proposed on a `docs/*` branch, reviewed, and merged with a
version bump recorded below. Versioning follows semantic rules: MAJOR for
backward-incompatible governance or principle removal/redefinition; MINOR for a
new principle or materially expanded section; PATCH for clarifications and
non-semantic refinements.

Compliance is reviewed at every merge to trunk. Reviewers MUST confirm adherence
to Principles I–VI; unjustified complexity or protocol changes without evidence
MUST be rejected. Runtime development guidance lives in the repository's contributor
and protocol documentation, which MUST remain consistent with this constitution.

**Version**: 1.0.0 | **Ratified**: 2026-08-14 | **Last Amended**: 2026-08-14
