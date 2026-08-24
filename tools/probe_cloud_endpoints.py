#!/usr/bin/env python3
"""Read-only probe for the Aqara cloud device-inventory endpoint (feature 016).

The endpoint that lists all devices of an account is not captured yet. This tool
lets **you** discover it with your own credentials (the assistant never sees
them): it logs in via `CloudAuthManager`, then issues **read-only** requests to a
list of candidate inventory paths, printing each response's status and top-level
shape, and writing a **sanitized** dump (did/mac/token redacted) under the
git-ignored `captures/` tree so the shape can be turned into `list_devices()`.

It never writes, actuates, or mutates anything. Credentials come from the
environment (same names as examples/lock_cli.py); nothing sensitive is printed.

    AQARA_ACCOUNT=… AQARA_PASSWORD=… \
      .venv/bin/python tools/probe_cloud_endpoints.py

Add your own candidate paths with --path (repeatable).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples"))
from auth_from_env import auth_from_env

from aqara_ble.kdf import REGION_BASE_URLS, _tls_context

# Candidate inventory paths (all GET, read-only). Extend with --path. These are
# the endpoints observed in the original capture notes plus common list shapes.
DEFAULT_PATHS = [
    "/app/dev/query/detail",
    "/dev/lock/query",
    "/app/position/query/room/list",
    "/app/dev/query/list",
    "/app/dev/list",
    "/dev/query/list",
    "/app/family/query/list",
    "/app/position/query/home/list",
]

_REDACT = [
    (
        re.compile(
            r'("(?:did|deviceId|didHash|mac|macAddress|ltmk|token|userId|uid)"\s*:\s*")[^"]*(")'
        ),
        r"\1<redacted>\2",
    ),
    (re.compile(r"\b[0-9a-fA-F]{2}(:[0-9a-fA-F]{2}){5}\b"), "<redacted-mac>"),
    (re.compile(r"\b(matt|lumi)\.[0-9a-zA-Z]+"), r"\1.<redacted>"),
]


def redact(text: str) -> str:
    for pattern, repl in _REDACT:
        text = pattern.sub(repl, text)
    return text


def signed_get(base: str, path: str, signer, timeout: float = 10.0) -> tuple[int, str]:
    # GET: the query string signs in the body position; here we probe with no
    # query (list endpoints are usually parameterless or take the account token).
    headers = {
        k: v
        for k, v in dict(signer(path, "")).items()
        if k.lower() not in ("host", "content-length")
    }
    headers.setdefault("Accept", "application/json")
    headers["Accept-Encoding"] = "identity"
    req = urllib.request.Request(base + path, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_tls_context()) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except Exception as exc:  # network/TLS
        return -1, f"{type(exc).__name__}: {exc}"


def shape(body: str) -> str:
    try:
        obj = json.loads(body)
    except ValueError:
        return f"<non-JSON, {len(body)} bytes>"
    if isinstance(obj, dict):
        code = obj.get("code")
        result = obj.get("result")
        rshape = (
            f"list[{len(result)}]"
            if isinstance(result, list)
            else "dict(" + ",".join(sorted(result)[:8]) + ")"
            if isinstance(result, dict)
            else type(result).__name__
        )
        return f"code={code} result={rshape} keys={sorted(obj)[:8]}"
    return type(obj).__name__


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--path", action="append", default=[], help="extra candidate path (repeatable)")
    ap.add_argument("--out", default="captures", help="dir for sanitized dumps (git-ignored)")
    args = ap.parse_args()

    try:
        auth = auth_from_env()
    except (ValueError, KeyError) as exc:
        print(f"[config] {exc}: set AQARA_ACCOUNT / AQARA_PASSWORD (+ app ids) in the environment")
        return 4

    print("[login] authenticating (credentials never printed)…")
    try:
        signer = auth.build_signer()
    except Exception as exc:
        print(f"[login] FAILED: {exc}")
        return 1
    base = REGION_BASE_URLS.get(auth.region, REGION_BASE_URLS["EU"])
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(
        f"[probe] base={base} (read-only GET on {len(DEFAULT_PATHS) + len(args.path)} candidate paths)\n"
    )
    hits = 0
    for path in DEFAULT_PATHS + args.path:
        status, body = signed_get(base, path, signer)
        print(f"  {status:>4}  {path:<32}  {shape(body)}")
        if status == 200 and '"result"' in body and body.count("{") > 1:
            safe = out_dir / (path.strip("/").replace("/", "_") + ".sanitized.json")
            safe.write_text(redact(body))
            print(f"        ↳ sanitized dump: {safe}")
            hits += 1
    print(
        f"\n[done] {hits} candidate(s) returned a list-like result. Share the sanitized dump(s) "
        f"to design list_devices(). Nothing was written to the account."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
