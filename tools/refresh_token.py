#!/usr/bin/env python3
"""Mint a fresh cloud token from your account password and store it in `.env`.

The Aqara cloud invalidates a token as soon as the account logs in anywhere
else, regardless of the `exp` claim — so a token that looks valid for days can
be dead already (the cloud answers `code=108, Token has expired`). This tool
re-logs in to get a fresh one.

**It needs a working token to sign the login request.** That is the cloud's
design, not a bug here: `/user/guard-code/login` is signed with an existing
token (`sign_token`), and the server rejects an empty one. If your stored token
is not merely expired but *invalidated*, this will fail too, and the only way
back is capturing a fresh token from the app (docs/tutorials/02-capture-credentials.md).

The password is read with `getpass`: it is never echoed, never stored, never
written to `.env`, and never passed as an argument (where it would land in your
shell history and in `ps`).

Usage:

    set -a; . ./.env; set +a
    python tools/refresh_token.py            # prompts for account + password
"""

from __future__ import annotations

import base64
import getpass
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aqara_u200_ble.kdf import login

ENV_PATH = Path(__file__).resolve().parents[1] / ".env"


def _env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(
            f"Missing {name}. Copy .env.example to .env, fill it in, and export it "
            f"(e.g. `set -a; . ./.env; set +a`) before running."
        )
    return value


def _jwt_claims(token: str) -> dict[str, object]:
    """Best-effort decode of a JWT payload. Never verifies — display only."""

    try:
        payload = token.split(".")[1]
        padded = payload + "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(padded))
    except Exception:  # a malformed token is not fatal here
        return {}
    return claims if isinstance(claims, dict) else {}


def _describe(token: str) -> str:
    claims = _jwt_claims(token)
    exp = claims.get("exp")
    account = claims.get("account", "?")
    if isinstance(exp, int):
        remaining = exp - int(time.time())
        when = time.strftime("%Y-%m-%d %H:%M", time.localtime(exp))
        state = f"expires {when} ({remaining // 86400}d {remaining % 86400 // 3600}h left)"
        if remaining <= 0:
            state = f"EXPIRED {when}"
    else:
        state = "no exp claim"
    return f"account={account} {state}"


def _store_token(token: str) -> None:
    """Replace AQARA_TOKEN in `.env`, leaving every other line untouched."""

    if not ENV_PATH.exists():
        raise SystemExit(f"{ENV_PATH} does not exist; nothing to update.")
    original = ENV_PATH.read_text()
    updated, count = re.subn(
        r"^AQARA_TOKEN=.*$", f"AQARA_TOKEN={token}", original, count=1, flags=re.M
    )
    if count == 0:
        updated = original.rstrip("\n") + f"\nAQARA_TOKEN={token}\n"
    ENV_PATH.write_text(updated)


def main() -> int:
    stored_token = _env("AQARA_TOKEN")
    claims = _jwt_claims(stored_token)
    print(f"[*] stored token: {_describe(stored_token)}")

    default_account = str(claims.get("account", ""))
    prompt = f"Aqara account [{default_account}]: " if default_account else "Aqara account: "
    account = input(prompt).strip() or default_account
    if not account:
        raise SystemExit("An account is required.")
    password = getpass.getpass("Aqara password (not echoed, not stored): ")
    if not password:
        raise SystemExit("A password is required.")
    guard_code = input("Guard code if the cloud asks for one [none]: ").strip()

    print(f"[*] logging in as {account} ...", flush=True)
    try:
        result = login(
            account,
            password,
            appid=_env("AQARA_APPID"),
            appkey=_env("AQARA_APPKEY"),
            client_id=_env("AQARA_CLIENT_ID"),
            phone_id=_env("AQARA_PHONE_ID"),
            region=os.environ.get("AQARA_REGION", "EU"),
            area=os.environ.get("AQARA_REGION", "EU"),
            guard_code=guard_code,
            # The cloud signs this request with the *existing* token. A dead one
            # is worth trying: the endpoint may only check the signature.
            sign_token=stored_token,
            user_id=_env("AQARA_USER_ID"),
        )
    except RuntimeError as exc:
        message = str(exc)
        print(f"[FAIL] {message}", file=sys.stderr)
        if "108" in message or "expired" in message.lower():
            print(
                "\nThe stored token is not just expired, it was invalidated (Aqara "
                "kills a token when the account logs in elsewhere), and the login "
                "endpoint needs a live one to sign with. Capture a fresh token from "
                "the app instead: docs/tutorials/02-capture-credentials.md",
                file=sys.stderr,
            )
        return 1

    token = result.get("token")
    if not isinstance(token, str) or not token:
        print(f"[FAIL] login succeeded but returned no token: {sorted(result)}", file=sys.stderr)
        return 1

    _store_token(token)
    print(f"[OK] new token: {_describe(token)}")
    print(f"[OK] written to {ENV_PATH} (git-ignored). Re-export it:")
    print("     set -a; . ./.env; set +a")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
