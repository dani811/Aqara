"""Secret-hygiene guard — Constitution Principle I (feature 025).

Fails if a real-looking device MAC, or a private-key block, appears in any
git-tracked file outside an explicit allow-list of synthetic placeholders. This
prevents re-introducing the class of leak that once put the reference lock's real
MAC into version control (see ``specs/025-security-hygiene-mac/spec.md``).

Scans ONLY git-tracked files, so ``.env`` / ``captures/`` / ``artifacts/`` (all
gitignored, and where real values legitimately live locally) are never read.
Runs as an ordinary unit test, so it executes in the normal ``pytest`` invocation
and in CI without any opt-in.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

# A MAC-shaped token, e.g. ``AA:BB:CC:DD:EE:FF``.
_MAC_RE = re.compile(r"\b(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}\b")
_PRIVKEY_RE = re.compile(
    r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"
)

# Synthetic MACs allowed in tracked source (documentation / test placeholders).
# Any MAC-shaped token NOT matching one of these fails the guard.
_ALLOWED_MAC_EXACT = {
    "AA:BB:CC:DD:EE:FF",  # canonical fake placeholder (spec-sanctioned)
    "11:22:33:44:55:66",  # sequential placeholder
    "F0:F1:F2:F3:F4:F5",  # bumble local-address placeholder (transport.py)
    "00:00:00:00:00:00",  # null address
    "FF:FF:FF:FF:FF:FF",  # broadcast address
}
_ALLOWED_MAC_PATTERNS = (
    re.compile(r"^CA:FE:00:00:00:[0-9A-F]{2}$"),          # "cafe" test-device family
    re.compile(r"^DE:AD:BE:EF:[0-9A-F]{2}:[0-9A-F]{2}$"),  # "deadbeef" family
)


def _tracked_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [_ROOT / p for p in out.stdout.split("\0") if p]


def _is_allowed_mac(mac: str) -> bool:
    up = mac.upper()
    if up in _ALLOWED_MAC_EXACT:
        return True
    return any(p.match(up) for p in _ALLOWED_MAC_PATTERNS)


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None  # binary or unreadable — skip


def test_no_real_mac_in_tracked_files() -> None:
    offenders: list[str] = []
    for path in _tracked_files():
        text = _read_text(path)
        if text is None:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            for match in _MAC_RE.finditer(line):
                if not _is_allowed_mac(match.group(0)):
                    rel = path.relative_to(_ROOT)
                    offenders.append(f"{rel}:{lineno}: {match.group(0)}")
    assert not offenders, (
        "Real-looking MAC(s) found in tracked files (Constitution Principle I).\n"
        "Use a placeholder from the allow-list in tests/test_secret_hygiene.py:\n  "
        + "\n  ".join(offenders)
    )


def test_no_private_key_block_in_tracked_files() -> None:
    offenders: list[str] = []
    for path in _tracked_files():
        text = _read_text(path)
        if text is None:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _PRIVKEY_RE.search(line):
                offenders.append(f"{path.relative_to(_ROOT)}:{lineno}")
    assert not offenders, (
        "Private-key block(s) found in tracked files (Constitution Principle I):\n  "
        + "\n  ".join(offenders)
    )
