"""`aqara` — the packaged command-line adapter over the public API (feature 017).

This module is a **thin** adapter: it parses arguments, loads credentials (from
flags or the environment — the library itself never reads the environment), builds
the public objects (`CloudAuthManager`, a `Transport`, `U200Client`) and calls
their methods, then prints. **No protocol, network or BLE logic lives here** — an
integration couples to the same public API this CLI uses, without importing `cli`.

Purity invariant: `import aqara_ble` must NOT import this module (it is not
imported by the package ``__init__``) and importing the library reads no
environment. This module is loaded only when the ``aqara`` command runs.

    aqara login
    aqara scan  --transport bleak
    aqara lock  --transport bumble --port serial:/dev/cu.usbmodemNNNN,115200
    aqara state
    aqara query lock_status
    aqara listen --seconds 20
    aqara operate keepalive
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

from . import (
    AmbiguousDeviceError,
    BleakTransport,
    BumbleTransport,
    CloudAuthManager,
    NoDeviceFoundError,
    ScanCandidate,
    Transport,
    U200Client,
    U200ClientError,
    scan,
)

# Exit codes by outcome class (FR-005).
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_NOT_FOUND = 2
EXIT_AMBIGUOUS = 3
EXIT_CONFIG = 4
EXIT_TIMEOUT = 5

_REQUIRED_APP_IDS = ("AQARA_APPID", "AQARA_APPKEY", "AQARA_CLIENT_ID", "AQARA_PHONE_ID")

# All SYSTEM read-only opcodes, name -> opcode (mutating/actuating ones excluded
# at the source). `aqara read <name>` sends the correct read frame for each.
from .operations_catalog import system_read_opcodes  # noqa: E402

READ_OPCODES = system_read_opcodes()

# Read-only status/battery opcodes safe to probe (feature 021). Names -> opcode.
# These are query/report opcodes from the app's decompiled enum; SET_* opcodes are
# deliberately NOT here (probing them could change lock settings). UNCONFIRMED.
STATUS_QUERIES: dict[str, int] = {
    "lock_status": 0x07,
    "tongue_status": 0x08,
    "door_lock_status": 0xE5,
    "report_lock_status": 0x15,
    "battery": 0x4F,
    "lithium_battery": 0x78,
    "battery_info": 0xDE,
    "battery_power": 0x50,
}


def _load_dotenv() -> None:
    """Populate os.environ from a .env in cwd or repo root (never overrides)."""

    for candidate in (Path.cwd() / ".env", Path(__file__).resolve().parents[1] / ".env"):
        if candidate.exists():
            for raw in candidate.read_text().splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.split(" #", 1)[0].strip())
            return


def _auth_from(args: argparse.Namespace) -> CloudAuthManager:
    """Build a CloudAuthManager from flags or the environment (CLI-only)."""

    account = args.account or os.environ.get("AQARA_ACCOUNT")
    password = args.password or os.environ.get("AQARA_PASSWORD")
    missing = [
        name
        for name, val in (
            ("AQARA_ACCOUNT/--account", account),
            ("AQARA_PASSWORD/--password", password),
            *((n, os.environ.get(n)) for n in _REQUIRED_APP_IDS),
        )
        if not val
    ]
    if missing:
        raise _ConfigError("missing credentials: " + ", ".join(missing))
    return CloudAuthManager(
        account=account or "",
        password=password or "",
        appid=os.environ["AQARA_APPID"],
        appkey=os.environ["AQARA_APPKEY"],
        client_id=os.environ["AQARA_CLIENT_ID"],
        phone_id=os.environ["AQARA_PHONE_ID"],
        region=os.environ.get("AQARA_REGION", "EU"),
    )


class _ConfigError(RuntimeError):
    """Missing/invalid configuration (maps to EXIT_CONFIG)."""


def _make_transport(args: argparse.Namespace) -> Transport:
    if args.transport == "bleak":
        return BleakTransport()
    port = args.port or os.environ.get("AQARA_ESP32_PORT")
    if not port:
        raise _ConfigError("--transport bumble needs --port or AQARA_ESP32_PORT")
    return BumbleTransport(port)


def _show(c: ScanCandidate) -> str:
    return (
        f"{c.address}  name={c.name!r}  model={c.model or '?'}  rssi={c.rssi}  "
        f"score={c.score}  reasons={{{','.join(sorted(c.reasons))}}}  preferred={c.is_preferred}"
    )


def _device_id() -> str:
    did = os.environ.get("AQARA_DEVICE_ID")
    if not did:
        raise _ConfigError("missing AQARA_DEVICE_ID")
    return did


async def _run(args: argparse.Namespace) -> int:  # noqa: PLR0911 - one exit per outcome
    # login: only the account path, no radio.
    if args.command == "login":
        auth = _auth_from(args)
        started = time.monotonic()
        try:
            await asyncio.to_thread(auth.build_signer)
        except Exception as exc:  # 810/network/TLS
            print(f"[login] FAILED: {exc}")
            return EXIT_ERROR
        token = auth.get_token()
        print(
            f"[login] OK in {time.monotonic() - started:.1f}s: token obtained "
            f"({len(token)} chars, JWT={'yes' if token.count('.') == 2 else 'no'})"
        )
        return EXIT_OK

    transport = _make_transport(args)
    mac = args.mac or os.environ.get("AQARA_LOCK_MAC") or None
    if args.transport == "bleak" and sys.platform == "darwin" and not args.mac:
        # macOS/CoreBluetooth exposes per-app UUIDs, not MACs, so a MAC filter
        # never matches an advertised address. Ignore the env MAC and identify by
        # advertisement instead (an explicit --mac still wins on other platforms).
        mac = None

    if args.command == "scan":
        print(f"[scan] {transport.name}, {args.timeout:g}s (touch the keypad so it advertises)")
        found = await scan(transport, timeout=args.timeout, mac=mac)
        for c in found:
            print("  " + _show(c))
        if not found:
            print("  (no candidates)")
        await transport.disconnect()
        return EXIT_OK if found else EXIT_NOT_FOUND

    auth = _auth_from(args)
    device_id = _device_id()
    started = time.monotonic()
    print(f"[flow] login → scan → connect → discover → {args.command} via {transport.name}")
    try:
        async with await U200Client.connect(
            auth=auth,
            transport=transport,
            device_id=device_id,
            mac=mac,
            region=os.environ.get("AQARA_REGION", "EU"),
            scan_timeout=args.timeout,
        ) as lock:
            if lock.candidate is not None:
                print("[scan] picked " + _show(lock.candidate))
            print(f"[connect] connected in {time.monotonic() - started:.1f}s")
            if args.command == "listen":
                reports = await lock.listen(args.seconds)
                print(f"[listen] {args.seconds:g}s window, {len(reports)} frame(s):")
                for channel, hexdata in reports:
                    print(f"  {channel}: {hexdata}")
                if not reports:
                    print("  (nothing pushed on ff62/ff64/ff92 after the ACK)")
                return EXIT_OK
            if args.command == "query":
                opcode = STATUS_QUERIES[args.query_name]
                st = await lock.query(opcode)
                print(
                    f"[query] {args.query_name} (0x{opcode:02x}) responded={st.responded} "
                    f"raw={st.raw_hex or '(none)'} total={time.monotonic() - started:.1f}s"
                )
                return EXIT_OK
            if args.command == "battery":
                st = await lock.battery()
                print(
                    f"[battery] responded={st.responded} raw={st.raw_hex or '(none)'} "
                    f"percent={st.battery_percent if st.battery_percent is not None else '?'} "
                    f"total={time.monotonic() - started:.1f}s"
                )
                return EXIT_OK
            if args.command == "read":
                opcode = READ_OPCODES[args.read_name]
                st = await lock.read(opcode)
                extra = ""
                if st.locked is not None:
                    extra += f" locked={'LOCKED' if st.locked else 'UNLOCKED'}"
                if st.battery_percent is not None:
                    extra += f" battery={st.battery_percent}%"
                print(
                    f"[read] {args.read_name} (0x{opcode:02x}) responded={st.responded} "
                    f"raw={st.raw_hex or '(none)'}{extra} total={time.monotonic() - started:.1f}s"
                )
                return EXIT_OK
            if args.command == "lockstatus":
                st = await lock.read_lock_status()
                shown = (
                    "LOCKED" if st.locked else "UNLOCKED" if st.locked is False else "?"
                )
                print(
                    f"[lockstatus] responded={st.responded} raw={st.raw_hex or '(none)'} "
                    f"locked={shown} total={time.monotonic() - started:.1f}s"
                )
                return EXIT_OK
            if args.command == "state":
                st = await lock.status()
                print(
                    f"[state] responded={st.responded} raw={st.raw_hex or '(none)'} "
                    f"locked={st.locked if st.locked is not None else '?'} "
                    f"battery={st.battery_percent if st.battery_percent is not None else '?'} "
                    f"total={time.monotonic() - started:.1f}s"
                )
                return EXIT_OK
            if args.command == "lock":
                response, op = await lock.lock(), "LOCK"
            elif args.command == "unlock":
                response, op = await lock.unlock(), "UNLOCK"
            else:
                result = await lock.operate(args.operation)
                response, op = result.response_hex, result.operation.name
            shown = response or "(no response; the bolt may still have moved)"
            print(f"[OK] op={op} response={shown} total={time.monotonic() - started:.1f}s")
            return EXIT_OK
    except AmbiguousDeviceError as exc:
        print(f"[scan] {exc}")
        return EXIT_AMBIGUOUS
    except NoDeviceFoundError as exc:
        print(f"[scan] {exc}")
        return EXIT_NOT_FOUND
    except U200ClientError as exc:
        print(f"[{exc.phase.value}] FAILED: {exc}")
        return EXIT_ERROR


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="aqara",
        description="Control an Aqara U200 lock through the aqara_ble library.",
    )
    p.add_argument("--transport", choices=("bleak", "bumble"), default="bleak")
    p.add_argument("--port", help="bumble transport spec, e.g. serial:/dev/cu.usbmodemNNNN,115200")
    p.add_argument("--mac", help="lock MAC (overrides AQARA_LOCK_MAC); omit to identify by advert")
    p.add_argument("--timeout", type=float, default=30.0, help="scan timeout (seconds)")
    p.add_argument("--account", help="account (overrides AQARA_ACCOUNT)")
    p.add_argument("--password", help="password (overrides AQARA_PASSWORD)")
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("login", "scan", "state", "battery", "lockstatus", "lock", "unlock"):
        sub.add_parser(name)
    ls = sub.add_parser("listen", help="keep the session open and print spontaneous frames")
    ls.add_argument("--seconds", type=float, default=15.0, help="listen window (seconds)")
    q = sub.add_parser("query", help="probe a read-only status/battery opcode")
    q.add_argument("query_name", choices=sorted(STATUS_QUERIES), help="which status opcode to read")
    rd = sub.add_parser("read", help="read any SYSTEM read-only opcode (correct frame)")
    rd.add_argument(
        "read_name", choices=sorted(READ_OPCODES),
        help="which read opcode (see the list); mutating opcodes are not offered",
    )
    op = sub.add_parser("operate")
    op.add_argument("operation", help="LockOperation name or hex (e.g. keepalive)")
    return p


def main(argv: list[str] | None = None) -> int:
    _load_dotenv()
    args = _build_parser().parse_args(argv)
    try:
        return asyncio.run(asyncio.wait_for(_run(args), timeout=120))
    except _ConfigError as exc:
        print(f"[config] {exc}")
        return EXIT_CONFIG
    except TimeoutError:
        print("[!] global timeout (120s): something hung in the radio stack; retry")
        return EXIT_TIMEOUT


if __name__ == "__main__":
    sys.exit(main())
