#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# SPDX-FileCopyrightText: 2026 dani811 <https://github.com/dani811/Aqara>
#
# This file is part of Aqara BLE, licensed under the GNU Affero General Public
# License v3.0 (AGPL-3.0-only). You may use, study, share and modify it; any
# distributed or network-served derivative must stay licensed under the AGPL
# and keep this notice. See the LICENSE file for the full terms.

"""Compat wrapper — the runner now ships as the packaged `aqara` command.

`pip install -e .` puts `aqara` on your PATH (see `aqara --help`). This shim keeps
`python examples/lock_cli.py …` working by delegating to the same entry point.
"""

from aqara_ble.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
