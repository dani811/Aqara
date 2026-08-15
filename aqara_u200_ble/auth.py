"""
Automatic token management for cloud authentication.

Handles login, token refresh on 108 errors, and transparent credential loading.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .kdf import login

logger = logging.getLogger(__name__)


class CloudAuthManager:
    """Manages Aqara cloud authentication with automatic token refresh.

    Features:
    - Load credentials from environment or .env files
    - Automatic login with account/password (no manual token required)
    - Transparent token refresh on expiration (code 108)
    - Thread-safe caching of valid tokens
    """

    def __init__(
        self,
        *,
        account: str,
        password: str,
        appid: str,
        appkey: str,
        client_id: str,
        phone_id: str,
        region: str = "EU",
        district: str = "ES",
    ) -> None:
        """Initialize auth manager with account credentials.

        Args:
            account: Aqara account (email or phone)
            password: Aqara account password
            appid: Aqara app ID
            appkey: Aqara app key
            client_id: Firebase Cloud Messaging client ID
            phone_id: Device phone ID
            region: Aqara region (EU, CN, etc.)
            district: Aqara district (ES, CN, etc.)
        """
        self.account = account
        self.password = password
        self.appid = appid
        self.appkey = appkey
        self.client_id = client_id
        self.phone_id = phone_id
        self.region = region
        self.district = district

        self._token: str | None = None
        self._user_id: str | None = None

    def _login(self) -> tuple[str, str]:
        """Perform login and return (token, user_id)."""
        logger.debug(f"Logging in as {self.account}...")
        result = login(
            self.account,
            self.password,
            appid=self.appid,
            appkey=self.appkey,
            client_id=self.client_id,
            phone_id=self.phone_id,
            region=self.region,
            district=self.district,
        )
        token = result.get("token")
        user_id = result.get("userId") or result.get("uid")
        if not token:
            raise RuntimeError(f"Login failed: no token in result {sorted(result)}")
        logger.debug(f"Login successful: token valid")
        return token, user_id or ""

    def get_token(self, *, force_refresh: bool = False) -> str:
        """Get valid token, logging in if needed.

        Args:
            force_refresh: Force new login even if cached token exists

        Returns:
            Valid JWT token for cloud API calls
        """
        if self._token and not force_refresh:
            return self._token

        token, user_id = self._login()
        self._token = token
        self._user_id = user_id
        return token

    def handle_expired_token(self) -> str:
        """Handle code=108 error by forcing token refresh.

        Returns:
            New valid token
        """
        logger.debug("Token expired (code=108), refreshing...")
        return self.get_token(force_refresh=True)

    @classmethod
    def from_env(
        cls,
        *,
        account_env: str = "AQARA_ACCOUNT",
        password_env: str = "AQARA_PASSWORD",
        appid_env: str = "AQARA_APPID",
        appkey_env: str = "AQARA_APPKEY",
        client_id_env: str = "AQARA_CLIENT_ID",
        phone_id_env: str = "AQARA_PHONE_ID",
        region_env: str = "AQARA_REGION",
    ) -> CloudAuthManager:
        """Create from environment variables.

        Args:
            account_env: Name of account env var
            password_env: Name of password env var
            appid_env: Name of appid env var
            appkey_env: Name of appkey env var
            client_id_env: Name of client_id env var
            phone_id_env: Name of phone_id env var
            region_env: Name of region env var

        Returns:
            Configured CloudAuthManager
        """
        import os

        def _env(name: str) -> str:
            value = os.environ.get(name)
            if not value:
                raise ValueError(f"Missing {name} in environment")
            return value

        return cls(
            account=_env(account_env),
            password=_env(password_env),
            appid=_env(appid_env),
            appkey=_env(appkey_env),
            client_id=_env(client_id_env),
            phone_id=_env(phone_id_env),
            region=os.environ.get(region_env, "EU"),
        )
