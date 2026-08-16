"""
Automatic token management for cloud authentication.

Handles login, token refresh on 108 errors, and transparent credential loading.
"""

from __future__ import annotations

import logging

from .kdf import CloudServiceError, Signer, login, make_local_signer

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
        """Perform login and return (token, user_id).

        A ``code 810`` (wrong password / unregistered account) is translated into
        a clear, **non-retryable** error so the caller never loops on it — it is
        not a token expiry. No credential is logged.
        """
        logger.debug("cloud login: starting")
        try:
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
        except CloudServiceError as exc:
            if exc.is_code(810):
                raise RuntimeError(
                    "Aqara login rejected the credentials (code 810): wrong "
                    "password, or the account is not registered in this region. "
                    "This is not a token expiry and is not retried."
                ) from exc
            raise
        token = result.get("token")
        user_id = result.get("userId") or result.get("uid")
        if not token:
            raise RuntimeError(f"Login failed: no token in result {sorted(result)}")
        logger.debug("cloud login: succeeded")
        return token, user_id or ""

    def build_signer(self, *, force_refresh: bool = False) -> Signer:
        """Build a cloud request signer bound to a valid token (logging in if
        needed). Used by the operation flow to sign cloud calls and to rebuild
        the signer after a token refresh."""
        token = self.get_token(force_refresh=force_refresh)
        return make_local_signer(
            appid=self.appid,
            appkey=self.appkey,
            token=token,
            user_id=self._user_id or "",
            client_id=self.client_id,
            phone_id=self.phone_id,
            area=self.region,
        )

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
        """Handle a ``code=108`` (token expired) by forcing a fresh login.

        Returns:
            New valid token
        """
        logger.debug("cloud token: refreshing (expired)")
        return self.get_token(force_refresh=True)

    # NOTE: environment-based construction lives OUTSIDE the library, in
    # examples/auth_from_env.py (Feature 014). The library never reads the
    # environment: the consumer (e.g. Home Assistant) injects credentials.
