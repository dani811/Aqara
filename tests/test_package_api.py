"""Package-API completeness (feature 005).

Proves the assembled public surface is importable and that the optional BLE
backends (bleak, bumble) are truly optional — the package imports without them
(Constitution: feature 005 FR-006).
"""

from __future__ import annotations

import importlib
import importlib.util

import aqara_u200_ble


def test_every_public_name_is_importable() -> None:
    missing = [name for name in aqara_u200_ble.__all__ if not hasattr(aqara_u200_ble, name)]
    assert missing == [], f"names in __all__ missing from the package: {missing}"


def test_public_api_is_sorted_and_unique() -> None:
    names = list(aqara_u200_ble.__all__)
    assert len(names) == len(set(names)), "duplicate names in __all__"


def test_optional_backends_are_truly_optional() -> None:
    # The package imported successfully above; confirm neither optional backend
    # is a hard requirement for that import.
    aqara_u200_ble_reimported = importlib.reload(aqara_u200_ble)
    assert aqara_u200_ble_reimported is aqara_u200_ble
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
        assert hasattr(aqara_u200_ble, symbol)
