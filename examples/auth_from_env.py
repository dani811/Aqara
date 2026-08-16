"""Dev-only: build a CloudAuthManager from environment variables.

This helper lives **outside** the `aqara_u200_ble` package on purpose: the library
never reads the environment. In production (e.g. Home Assistant) the consumer
injects credentials from its own secure storage and constructs `CloudAuthManager`
directly. This is a convenience for local runs that keep secrets in a git-ignored
`.env`.
"""

from __future__ import annotations

import os

from aqara_u200_ble import CloudAuthManager


def _env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"Missing {name} in environment (see .env.example)")
    return value


def auth_from_env(
    *,
    account_env: str = "AQARA_ACCOUNT",
    password_env: str = "AQARA_PASSWORD",
    appid_env: str = "AQARA_APPID",
    appkey_env: str = "AQARA_APPKEY",
    client_id_env: str = "AQARA_CLIENT_ID",
    phone_id_env: str = "AQARA_PHONE_ID",
    region_env: str = "AQARA_REGION",
) -> CloudAuthManager:
    """Construct a `CloudAuthManager` from environment variables (dev convenience)."""
    return CloudAuthManager(
        account=_env(account_env),
        password=_env(password_env),
        appid=_env(appid_env),
        appkey=_env(appkey_env),
        client_id=_env(client_id_env),
        phone_id=_env(phone_id_env),
        region=os.environ.get(region_env, "EU"),
    )
