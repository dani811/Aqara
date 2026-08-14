# Phase 0 Research: TLS certificate verification

**Feature**: 006-tls-verification · **Date**: 2026-08-14

The Technical Context carried no `NEEDS CLARIFICATION` markers; this file records
the four decisions that shaped the design and what was rejected.

## 1. Where the insecure context comes from

**Finding**: [`aqara_u200_ble/kdf.py`](../../aqara_u200_ble/kdf.py) builds the
context inline inside `_post_json`, the single funnel through which every cloud
call passes (`login`, `cloud_get_public_key`, `cloud_verify`, and therefore
`get_session_material`). A package-wide search for `ssl` returns exactly one
construction site, so a single factory covers 100% of cloud traffic (FR-007,
SC-004).

**Rationale**: no per-endpoint work is needed; fixing the funnel fixes everything.

**Alternatives considered**: an `HTTPSHandler`/opener installed globally —
rejected, it mutates process-wide `urllib` state that a host application also
uses.

## 2. Opt-out mechanism

**Decision**: environment variable `U200_INSECURE_TLS`, read per request.

**Rationale**: the module already reads `U200_DEBUG` the same way, so operators
find it where they expect; an environment switch cannot be baked into library
code by a caller, which is precisely the failure mode being fixed (FR-002).

**Alternatives considered**:

- **Function/constructor parameter** — rejected: a call site could hard-code
  `verify=False` permanently and invisibly.
- **No opt-out at all** — rejected: users on a broken macOS trust store would be
  blocked from the tutorials and would patch the library source instead, which is
  a worse, undocumented downgrade.
- **`AQARA_*` prefix** — rejected: `AQARA_*` names in `.env.example` are *account
  and device identity* values; `U200_*` is the library's own behaviour namespace.

## 3. Flag parsing

**Decision**: `os.environ.get(...)`, `.strip().lower()`, membership in
`{"1", "true", "yes", "on"}`.

**Rationale**: fail-safe. Anything unrecognised — `""`, `"0"`, `"no"`, a typo —
leaves verification enabled (FR-003). The inverse (disable unless explicitly
`"0"`) would turn a typo into a silent security hole.

**Alternatives considered**: "any non-empty value is truthy" — rejected because
`U200_INSECURE_TLS=0` reads to a human as *off* and must behave that way.

## 4. Making an insecure run visible, and a failure actionable

**Decision**: `print(..., file=sys.stderr)` on every downgraded context; and, on
`ssl.SSLCertVerificationError`, raise a `RuntimeError` naming both plausible
causes and the flag.

**Rationale**: matches the module's existing stderr convention and satisfies
FR-004/FR-005. Because the context is built per request, the warning repeats —
intended: an insecure session stays visibly insecure.

**Alternatives considered**: `warnings.warn` — rejected: the default filter shows
a given warning once per location, so a long run would look clean after the first
call. `logging` — rejected: the library configures no logger, so a host app with
no handler would swallow the message entirely.

## Python behaviour confirmed

- `ssl.create_default_context()` returns `check_hostname=True`,
  `verify_mode=CERT_REQUIRED`, loading the platform trust store — so the fix is
  "stop overriding the default", not "add verification".
- `check_hostname` must be set to `False` *before* `verify_mode = CERT_NONE`;
  the reverse order raises `ValueError`. The factory preserves that order.
- `urlopen` surfaces certificate failures as `urllib.error.URLError` whose
  `.reason` is the `ssl.SSLCertVerificationError` — the hook used for the
  actionable message.
