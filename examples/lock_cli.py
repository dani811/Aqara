#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# SPDX-FileCopyrightText: 2026 dani811 <https://github.com/dani811/Aqara>
#
# Aqara BLE. Source-available under the PolyForm Noncommercial License 1.0.0.
# Noncommercial use only; any commercial or for-profit use requires a separate
# written license from the copyright holder. See the LICENSE file for the terms.

"""Compat wrapper — the runner now ships as the packaged `aqara` command.

`pip install -e .` puts `aqara` on your PATH (see `aqara --help`). This shim keeps
`python examples/lock_cli.py …` working by delegating to the same entry point.
"""

from aqara_ble.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
