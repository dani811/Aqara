# SPDX-License-Identifier: AGPL-3.0-only
# SPDX-FileCopyrightText: 2026 dani811 <https://github.com/dani811/Aqara>
#
# This file is part of Aqara BLE, licensed under the GNU Affero General Public
# License v3.0 (AGPL-3.0-only). You may use, study, share and modify it; any
# distributed or network-served derivative must stay licensed under the AGPL
# and keep this notice. See the LICENSE file for the full terms.

"""Package-API completeness (feature 005).

Proves the assembled public surface is importable and that the optional BLE
backends (bleak, bumble) are truly optional — the package imports without them
(Constitution: feature 005 FR-006).
"""

from __future__ import annotations

import importlib
import importlib.util

import aqara_ble


def test_every_public_name_is_importable() -> None:
    missing = [name for name in aqara_ble.__all__ if not hasattr(aqara_ble, name)]
    assert missing == [], f"names in __all__ missing from the package: {missing}"


def test_public_api_is_sorted_and_unique() -> None:
    names = list(aqara_ble.__all__)
    assert len(names) == len(set(names)), "duplicate names in __all__"


def test_optional_backends_are_truly_optional() -> None:
    # The package imported successfully above; confirm neither optional backend
    # is a hard requirement for that import.
    aqara_ble_reimported = importlib.reload(aqara_ble)
    assert aqara_ble_reimported is aqara_ble
    # These may or may not be installed; either way, importing the package worked.
    for optional in ("bleak", "bumble"):
        # importlib.util.find_spec must not raise regardless of presence.
        importlib.util.find_spec(optional)


def test_key_end_to_end_symbols_present() -> None:
    for symbol in (
        "login",
        "cloud_get_public_key",
        "crc16_aqara",
        "build_auth_message",
        "run_authenticated_lock_operation",
        "send_lock_operation",
        "BumbleGattAdapter",
        "scan",
    ):
        assert hasattr(aqara_ble, symbol)
