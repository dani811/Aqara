#!/usr/bin/env python3
"""Read-only probe for the Aqara ``/app/dev/voice/list`` cloud endpoint.

Purpose (track A, language OTA): the language-download flow stalls at 0% and
was root-caused to a JS span *above* both BLE and the CDN download — most
likely ``getPageParams().fileInfo`` coming back empty/malformed for this
account+language. ``VoiceOtaPage.startOta()`` reads that ``fileInfo`` from the
row the language picker built out of the ``GET /app/dev/voice/list`` response
(``cloudLangList`` in Redux). So the concrete next test is: fetch that response
for THIS account and check whether each language row — Français especially —
carries a real, parseable ``fileInfo`` right now.

This is a pure cloud call (no BLE, no phone). It signs with the exact same
scheme as ``fetch_offline_passwords()`` (``make_local_signer`` /
``compute_sign`` — appid/nonce/time/token/body/appkey, never the method/path).
It is **read-only**: GET only, never writes/actuates anything.

The endpoint's exact query params were never captured, so this tries a few
variants (parameterless, ``did=``, ``did=&model=``) and reports which one the
server accepts. Credentials come from the environment; nothing sensitive is
printed. A sanitized dump (did/mac/token redacted) is written under the
git-ignored ``captures/`` tree.

    set -a; . ./.env; set +a
    .venv/bin/python tools/probe_voice_list.py

Add extra query variants with --query (repeatable), e.g.
    --query "did=$AQARA_DEVICE_ID&lang=fr"
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples"))


def _load_dotenv(path: Path) -> None:
    """Populate os.environ from a .env file WITHOUT shell interpretation.

    The account's real .env holds values with ``&``/``!`` that break
    ``. ./.env`` under zsh; this parser splits on the first ``=`` only,
    strips one layer of matching quotes, and never expands anything. Existing
    environment variables win (so an explicit export still overrides the file).
    """
    if not path.is_file():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key, value)


_load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from auth_from_env import auth_from_env  # noqa: E402

from aqara_ble.kdf import REGION_BASE_URLS, _tls_context  # noqa: E402

_PATH = "/app/dev/voice/list"

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


def signed_get(base: str, path: str, query: str, signer, timeout: float = 15.0):
    # For GETs the Aqara sign preimage puts the raw query string in the "body"
    # position; the same string also rides on the URL. Match that here.
    headers = {
        k: v
        for k, v in dict(signer(path, query)).items()
        if k.lower() not in ("host", "content-length")
    }
    headers.setdefault("Accept", "application/json")
    headers["Accept-Encoding"] = "identity"
    url = base + path + (f"?{query}" if query else "")
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_tls_context()) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except Exception as exc:  # network/TLS
        return -1, f"{type(exc).__name__}: {exc}"


def _parse_file_info(raw):
    """Return (ok, parsed-or-note). fileInfo is usually a JSON *string*."""
    if raw is None:
        return False, "<missing>"
    if isinstance(raw, (dict, list)):
        return True, raw
    if isinstance(raw, str):
        if not raw.strip():
            return False, "<empty string>"
        try:
            return True, json.loads(raw)
        except ValueError:
            return False, f"<unparseable str, {len(raw)} chars>"
    return False, f"<{type(raw).__name__}>"


def summarize(body: str) -> None:
    try:
        obj = json.loads(body)
    except ValueError:
        print(f"      <non-JSON, {len(body)} bytes>")
        return
    if not isinstance(obj, dict):
        print(f"      top-level {type(obj).__name__}")
        return
    code = obj.get("code")
    msg = obj.get("message")
    print(f"      code={code!r} message={msg!r} keys={sorted(obj)[:10]}")
    result = obj.get("result")
    rows = None
    if isinstance(result, list):
        rows = result
    elif isinstance(result, dict):
        # sometimes wrapped, e.g. {"list": [...]} or {"voiceList": [...]}
        for k in ("list", "voiceList", "langList", "data", "items"):
            if isinstance(result.get(k), list):
                rows = result[k]
                print(f"      result is dict; using result[{k!r}]")
                break
        if rows is None:
            print(f"      result dict keys={sorted(result)[:12]}")
    if not rows:
        return
    print(f"      {len(rows)} language row(s):")
    for row in rows:
        if not isinstance(row, dict):
            print(f"        - {row!r}")
            continue
        lang = (
            row.get("lang")
            or row.get("language")
            or row.get("langCode")
            or row.get("code")
            or row.get("name")
            or "?"
        )
        ok, info = _parse_file_info(row.get("fileInfo"))
        detail = ""
        if ok and isinstance(info, dict):
            files = info.get("fileInfo") or info.get("files")
            nfiles = len(files) if isinstance(files, list) else "?"
            detail = f"url={'yes' if info.get('url') else 'NO'} files={nfiles}"
        elif ok:
            detail = f"parsed {type(info).__name__}"
        flag = "OK " if ok else "!! "
        marker = " <-- FRANÇAIS" if str(lang).lower() in ("fr", "français", "francais", "french") else ""
        print(f"        {flag}lang={lang!r} fileInfo={info if not ok else detail}{marker}")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--query", action="append", default=[], help="extra query-string variant (repeatable)")
    ap.add_argument("--out", default="captures", help="dir for sanitized dumps (git-ignored)")
    args = ap.parse_args()

    try:
        auth = auth_from_env()
    except (ValueError, KeyError) as exc:
        print(f"[config] {exc}: set AQARA_ACCOUNT / AQARA_PASSWORD (+ app ids) in the environment")
        return 4

    did = os.environ.get("AQARA_DEVICE_ID", "").strip()
    print("[login] authenticating (credentials never printed)…")
    try:
        signer = auth.build_signer()
    except Exception as exc:
        print(f"[login] FAILED: {exc}")
        return 1
    base = REGION_BASE_URLS.get(auth.region, REGION_BASE_URLS["EU"])
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    variants = [""]
    if did:
        variants += [f"did={did}", f"did={did}&model="]
    variants += args.query

    print(f"[probe] GET {base}{_PATH}  ({len(variants)} query variant(s))\n")
    for i, query in enumerate(variants):
        status, body = signed_get(base, _PATH, query, signer)
        shown_q = query.replace(did, "<did>") if did and query else (query or "<none>")
        print(f"  [{i}] status={status:>4}  query={shown_q}")
        summarize(body)
        if status == 200 and '"result"' in body:
            safe = out_dir / f"voice_list.{i}.sanitized.json"
            safe.write_text(redact(body))
            print(f"      ↳ sanitized dump: {safe}")
        print()

    print("[done] Check whether the Français row above shows 'OK' with a real url + files.")
    print("       If it shows '!!' (missing/empty/unparseable fileInfo), that is the root")
    print("       cause of the 0% stall. Share the sanitized dump — no secrets in it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
