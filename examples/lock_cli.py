#!/usr/bin/env python3
"""The one real-hardware runner: drive a U200 through the library facade.

    python examples/lock_cli.py --transport bleak  scan
    python examples/lock_cli.py --transport bleak  lock
    python examples/lock_cli.py --transport bumble unlock          # port from AQARA_ESP32_PORT
    python examples/lock_cli.py --transport bumble --port serial:/dev/cu.usbmodemNNNN,115200 lock
    python examples/lock_cli.py operate keepalive
    python examples/lock_cli.py login              # clean first-use check: account+password only, no radio

Everything else — login, token refresh, scan & identification, connection,
service discovery, the authenticated session — is the library's job
(`aqara_u200_ble.U200Client`). This script only reads the git-ignored `.env`
(dev convenience; the library never touches the environment) and prints.

Required in .env: AQARA_ACCOUNT, AQARA_PASSWORD, AQARA_APPID, AQARA_APPKEY,
AQARA_CLIENT_ID, AQARA_PHONE_ID, AQARA_DEVICE_ID. Optional: AQARA_REGION,
AQARA_LOCK_MAC, AQARA_ESP32_PORT. No secret is ever printed.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from auth_from_env import auth_from_env

from aqara_u200_ble import (
    AmbiguousDeviceError,
    BleakTransport,
    BumbleTransport,
    NoDeviceFoundError,
    ScanCandidate,
    U200Client,
    U200ClientError,
    scan,
)


def load_dotenv() -> None:
    """Minimal .env loader (repo root or cwd). Never overrides exported vars."""

    for candidate in (Path.cwd() / ".env", Path(__file__).resolve().parents[1] / ".env"):
        if candidate.exists():
            for raw_line in candidate.read_text().splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.split(" #", 1)[0].strip())
            return


def make_transport(kind: str, port: str | None) -> BleakTransport | BumbleTransport:
    if kind == "bleak":
        return BleakTransport()
    port = port or os.environ.get("AQARA_ESP32_PORT")
    if not port:
        raise SystemExit("--transport bumble needs --port or AQARA_ESP32_PORT in .env")
    return BumbleTransport(port)


def show(c: ScanCandidate) -> str:
    return (
        f"{c.address}  name={c.name!r}  rssi={c.rssi}  score={c.score}  "
        f"reasons={{{','.join(sorted(c.reasons))}}}  preferred={c.is_preferred}"
    )


async def run(args: argparse.Namespace) -> int:  # noqa: PLR0911 - one exit code per outcome
    if args.command != "login":
        transport = make_transport(args.transport, args.port)
    mac = args.mac or os.environ.get("AQARA_LOCK_MAC") or None
    if args.transport == "bleak" and sys.platform == "darwin" and not args.mac:
        mac = None  # CoreBluetooth hides the MAC: identify by advertisement instead

    if args.command == "scan":
        print(
            f"[scan] {transport.name}, {args.timeout:g}s (touch the keypad so the U200 advertises)"
        )
        found = await scan(transport, timeout=args.timeout, mac=mac)
        for c in found:
            print("  " + show(c))
        if not found:
            print("  (no candidates)")
        await transport.disconnect()
        return 0 if found else 2

    try:
        auth = auth_from_env()
        device_id = os.environ["AQARA_DEVICE_ID"]
    except (ValueError, KeyError) as exc:
        print(f"[config] {exc}: add AQARA_ACCOUNT / AQARA_PASSWORD / AQARA_DEVICE_ID to .env")
        return 4

    if args.command == "login":
        # Proves the clean path: no AQARA_TOKEN / AQARA_USER_ID anywhere, just the
        # account credentials + app identifiers -> a live token. Nothing sensitive printed.
        started = time.monotonic()
        try:
            await asyncio.to_thread(auth.build_signer)
        except Exception as exc:  # 810 (bad credentials), network, TLS...
            print(f"[login] FAILED: {exc}")
            return 1
        token = auth.get_token()
        print(
            f"[login] OK in {time.monotonic() - started:.1f}s: token obtained "
            f"({len(token)} chars, JWT={'yes' if token.count('.') == 2 else 'no'}), "
            f"userId={'yes' if auth._user_id else 'no'}"
        )
        return 0
    region = os.environ.get("AQARA_REGION", "EU")
    started = time.monotonic()
    print(f"[flow] login → scan → connect → discover → {args.command} via {transport.name}")
    try:
        async with await U200Client.connect(
            auth=auth,
            transport=transport,
            device_id=device_id,
            mac=mac,
            region=region,
            scan_timeout=args.timeout,
        ) as lock:
            if lock.candidate is not None:
                print("[scan] picked " + show(lock.candidate))
            print(f"[connect] connected in {time.monotonic() - started:.1f}s")
            if args.command == "lock":
                response = await lock.lock()
                op = "LOCK"
            elif args.command == "unlock":
                response = await lock.unlock()
                op = "UNLOCK"
            else:
                result = await lock.operate(args.operation)
                response, op = result.response_hex, result.operation.name
            print(
                f"[OK] op={op} response={response or '(no response; the bolt may still have moved)'} "
                f"total={time.monotonic() - started:.1f}s"
            )
            return 0
    except AmbiguousDeviceError as exc:
        print(f"[scan] {exc}")
        for c in exc.candidates:
            print("  " + show(c))
        return 3
    except NoDeviceFoundError as exc:
        print(f"[scan] {exc}")
        for c in exc.seen:
            print("  seen: " + show(c))
        return 2
    except U200ClientError as exc:
        print(f"[{exc.phase.value}] FAILED: {exc}")
        return 1


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--transport", choices=("bleak", "bumble"), default="bleak")
    parser.add_argument(
        "--port", help="bumble transport spec, e.g. serial:/dev/cu.usbmodemNNNN,115200"
    )
    parser.add_argument(
        "--mac", help="lock MAC (overrides AQARA_LOCK_MAC); omit to identify by advertisement"
    )
    parser.add_argument("--timeout", type=float, default=30.0, help="scan timeout in seconds")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("login")
    sub.add_parser("scan")
    sub.add_parser("lock")
    sub.add_parser("unlock")
    op = sub.add_parser("operate")
    op.add_argument("operation", help="LockOperation name or hex (e.g. keepalive, state_snapshot)")
    args = parser.parse_args()
    try:
        return asyncio.run(asyncio.wait_for(run(args), timeout=120))
    except TimeoutError:
        print("[!] global timeout (120s): something hung in the radio stack; retry")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
