# Contributing

This project follows **Spec-Driven Development (SDD)** under the rules in
[`.specify/memory/constitution.md`](.specify/memory/constitution.md). Read it
once — it is short and binding.

## The loop

```text
spec  →  plan  →  tasks  →  implement  →  verify  →  merge
```

1. **Spec.** Create `specs/NNN-<slug>/spec.md` from
   [`.specify/templates/spec-template.md`](.specify/templates/spec-template.md).
   Describe *what* and *why*.
2. **Plan.** Add `plan.md` — the *how*, modules touched, risks.
3. **Tasks.** Add `tasks.md` — ordered, checkable units.
4. **Implement** on a branch, one task per commit where practical.
5. **Verify** — tests + (for protocol work) a real capture and a byte-diff.
6. **Merge** into `develop` via review.

## Branches

Never commit to `develop` directly. Branch names are always prefixed:

| Prefix | Use |
| --- | --- |
| `feature/*` | new capability / behaviour |
| `fix/*` | fix a defect |
| `refact/*` | restructure, no behaviour change |
| `docs/*` | docs, specs, evidence |
| `chore/*` | tooling, deps, scaffolding, CI |

Example: `feature/004-ble-auth-handshake`, `docs/project-docs`.

## Commits

- Conventional-commit style subject: `feat:`, `fix:`, `refactor:`, `docs:`,
  `chore:`, `test:`.
- Explain *why* in the body, not just *what*.
- AI-assisted work records co-authorship:
  `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`.

## Secrets — non-negotiable

Never commit tokens, `appkey`, LTMK, device/account IDs, MAC addresses, or any
`.btsnoop` / `.pcap` / bug-report capture. Real values live in a local,
git-ignored `.env` (see [`.env.example`](.env.example)); captures live under
git-ignored `captures/`. Code carries placeholders only. If you spot a secret
in a diff, stop and rewrite the change.

## Quality gates

Before opening a review, from the repo root:

```bash
ruff check . && ruff format --check .
mypy aqara_u200_ble
pytest
```

## Don't touch the frozen crypto

The verified protocol primitives (Article V of the constitution) are
byte-exact against hardware. Change them only under a spec that re-proves
fidelity; refactors must keep outputs bit-identical.
