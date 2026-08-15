#!/usr/bin/env python3
"""Mint a fresh cloud token from your account password and store it in `.env`.

The Aqara cloud invalidates a token as soon as the account logs in anywhere
else, regardless of the `exp` claim — so a token that looks valid for days can
be dead already (the cloud answers `code=108, Token has expired`). This tool
re-logs in to get a fresh one.

Account + password is enough: `/user/guard-code/login` is an **unauthenticated**
request. Without a token the client sends no Token/UserId/Requestid headers and
omits the `Token=` field from the signature preimage, which is exactly what
`make_local_signer` does when handed an empty token. So a dead stored token does
not block a refresh — that is the whole point of this tool. Verified end-to-end
against the real EU server (2026-08-14): correct credentials return `code=0` and
a usable JWT. (The password is sent as RSA(MD5(password)); see
`kdf.encrypt_login_password` for why the raw-password version returned 810.)

If a region ever did require signing with a live session, `--sign-with-stored`
retries using the token currently in `.env`.

The password is read with `getpass`: it is never echoed, never stored, never
written to `.env`, and never passed as an argument (where it would land in your
shell history and in `ps`).

Usage:

    set -a; . ./.env; set +a
    python tools/refresh_token.py                  # prompts for account + password
    python tools/refresh_token.py --sign-with-stored   # fallback: sign with the stored token
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
    sign_with_stored = "--sign-with-stored" in sys.argv[1:]
    stored_token = os.environ.get("AQARA_TOKEN", "")
    claims = _jwt_claims(stored_token)
    if stored_token:
        print(f"[*] stored token: {_describe(stored_token)}")
    print(
        "[*] login mode: "
        + ("signed with the stored token" if sign_with_stored else "unauthenticated (normal)")
    )

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
            # Empty by default: login is unauthenticated, and passing a dead
            # token would put a `Token=` field back into the signature preimage.
            sign_token=stored_token if sign_with_stored else "",
            user_id=os.environ.get("AQARA_USER_ID", "") if sign_with_stored else "",
        )
    except RuntimeError as exc:
        message = str(exc)
        print(f"[FAIL] {message}", file=sys.stderr)
        if "810" in message or "assword" in message:
            # 810 is ambiguous by design: the cloud returns it both for a wrong
            # password and for an unregistered account. (It was ALSO what the
            # old raw-password bug produced for every credential — now fixed.)
            print(
                "\nCode 810 means the cloud decrypted the password and it did "
                "not match: wrong password, or that account is not registered "
                "in this region.",
                file=sys.stderr,
            )
        elif "108" in message or "expired" in message.lower():
            print(
                "\nThe login endpoint itself answered 108. Retry with "
                "--sign-with-stored, and if that also fails capture a fresh token "
                "from the app: docs/porting-guide.md (step 1)",
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
