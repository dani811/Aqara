# Security audit — tracked-tree secret sweep (2026-08-20)

Evidence for FR-004 / User Story 2. Full sweep of all git-tracked files for
real-looking secrets. Result: the reference lock's real MAC was the **only** real
secret in version control; it has been removed (HEAD) and purged from history
(`git filter-repo`, 2026-08-20).

## Patterns swept
MAC addresses, private-key blocks, auth tokens / long hex or base64 blobs,
`lumi.`/`matt.` device ids, and non-author email addresses — over `git grep` of
the tracked tree.

## Findings & triage (every match accounted for)

| Match | Where | Verdict |
| --- | --- | --- |
| `AA:BB:CC:DD:EE:FF` | `tests/test_cli.py` (was) | **REMOVED** — real lock MAC → placeholder; purged from history |
| `AA:BB:CC:DD:EE:FF` | tests, spec | placeholder (allow-listed) |
| `11:22:33:44:55:66` | tests | placeholder (allow-listed) |
| `CA:FE:00:00:00:01` / `:02` | tests | synthetic "cafe" test device (allow-listed) |
| `F0:F1:F2:F3:F4:F5` | `transport.py` | bumble local-address placeholder (allow-listed) |
| SHA-256 hashes | `.specify/integrations/claude.manifest.json` | speckit skill integrity hashes — not secrets |
| RSA public key (DER b64) | `aqara_u200_ble/kdf.py` | Aqara login **public** key — not a secret |
| `000102030405` | docs (System ID) | SoC default, not a device secret |
| `22160062+dani811@users.noreply.github.com` | `pyproject.toml` | package author identity (allow-listed) |

No private-key blocks, auth tokens, or real device ids found in tracked files.

## Residual allow-list
Enforced by `tests/test_secret_hygiene.py` (`_ALLOWED_MAC_EXACT` +
`_ALLOWED_MAC_PATTERNS`). Any MAC-shaped token outside it, or any private-key
block, fails the guard in `pytest` and in CI (`.github/workflows/tests.yml`).

## Out of scope (flagged for the user)
Existing git history was rewritten to remove the value, but GitHub may retain the
old commit by SHA (dangling) until garbage-collected, and any cached views/mirrors
may linger. A BLE MAC alone does not grant access (auth is EC + AES-CCM + cloud
session), so no credential rotation applies. If full erasure is wanted, ask GitHub
Support to run GC on the repo.
