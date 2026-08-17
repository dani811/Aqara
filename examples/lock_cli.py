#!/usr/bin/env python3
"""Compat wrapper — the runner now ships as the packaged `aqara` command.

`pip install -e .` puts `aqara` on your PATH (see `aqara --help`). This shim keeps
`python examples/lock_cli.py …` working by delegating to the same entry point.
"""

from aqara_u200_ble.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
