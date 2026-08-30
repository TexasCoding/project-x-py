"""
Authentication and account management for ProjectX async clients.

Author: @TexasCoding
Date: 2025-08-02

Overview:
    This module implements the complete authentication lifecycle for ProjectX, including
    secure login using API key and username, JWT token handling, account selection, and
    robust error management. It automatically parses and refreshes authentication tokens,
    supports multiple accounts, and ensures session validity throughout async API usage.
    Integrated as a mixin, it enables seamless auth orchestration for all async clients.

Key Features:
    - Full async login flow with API key and user credentials
    - JWT token parsing, expiry extraction, and proactive refresh logic
    - Multi-account discovery and selection (by name or default)
    - Automatic authentication refresh on token expiry or invalidation
    - Error management with descriptive exceptions for auth failures
    - Utility methods for listing and validating available accounts

Example Usage:
    ```python
    import asyncio
    from project_x_py import ProjectX


    async def main():
        # V3: Using async context manager with automatic authentication
        async with ProjectX.from_env() as client:
            await client.authenticate()

            # V3: Access account info directly
            account = client.get_account_info()
            print(f"Authenticated account: {account.name}")
            print(f"Account ID: {account.id}")
            print(f"Balance: ${account.balance:,.2f}")

            # V3: List all available accounts
            accounts = await client.list_accounts()
            for acc in accounts:
                print(f"{acc.name}: ${acc.balance:,.2f} ({acc.state})")


    asyncio.run(main())
    ```

See Also:
    - `project_x_py.client.base.ProjectXBase` (core client with mixins)
    - `project_x_py.client.http.HttpMixin` (for HTTP request integration)
    - `project_x_py.client.trading.TradingMixin` (trading operations requiring auth)
"""

import base64
import datetime
from datetime import timedelta
from typing import TYPE_CHECKING

import orjson
import pytz

from project_x_py.exceptions import ProjectXAuthenticationError
from project_x_py.models import Account
from project_x_py.utils import (
    ErrorMessages,
    LogMessages,
    ProjectXLogger,
    format_error_message,
    handle_errors,
    validate_response,
)

if TYPE_CHECKING:
    from project_x_py.types import ProjectXClientProtocol

logger = ProjectXLogger.get_logger(__name__)


class AuthenticationMixin:
    """Mixin class providing authentication functionality."""

    # These attributes are provided by the base class
    username: str
    api_key: str
    account_name: str | None
    headers: dict[str, str]

    def __init__(self) -> None:
        """Initialize authentication attributes."""
        super().__init__()
        self.session_token = ""
        self.token_expiry: datetime.datetime | None = None
        self._authenticated = False
        self.account_info: Account | None = None

    async def _refresh_authentication(self: "ProjectXClientProtocol") -> None:
        """
        Refresh authentication if token is expired or about to expire.

        This method checks if the current authentication token needs refreshing
        based on its expiration time and initiates a full re-authentication
        if necessary. It's used internally to maintain session validity during
        long-running operations without requiring explicit user intervention.

        The refresh logic is controlled by the _should_refresh_token method,
        which implements the token expiration policy (currently refreshing
        when a token is within 5 minutes of expiration).
        """
        if self._should_refresh_token():
            if await self.validate_session():
                return
            await self.authenticate()

    def _should_refresh_token(self: "ProjectXClientProtocol") -> bool:
        """
        Check if the authentication token should be refreshed.

        This method determines whether the current JWT token needs to be refreshed
        based on its expiration time. It implements the token refresh policy by
        checking:

        1. If no token expiry exists (not authenticated or expiry unknown)
        2. If the token is within 5 minutes of expiration (configurable buffer)

        Returns:
            bool: True if token refresh is needed, False otherwise
        """
        if not self.token_expiry:
            return True

        # Refresh if token expires in less than 5 minutes
        buffer_time = timedelta(minutes=5)
        return datetime.datetime.now(pytz.UTC) >= (self.token_expiry - buffer_time)

    async def validate_session(self: "ProjectXClientProtocol") -> bool:
        """Refresh the JWT via POST /Auth/validate when the current session is valid.

        Returns:
            True if the session is valid (and ``newToken`` was applied when present).
        """
        if not self.session_token:
            return False
        try:
            response = await self._make_request("POST", "/Auth/validate")
        except Exception as e:
            logger.debug("Auth/validate failed: %s", e)
            return False
        if not isinstance(response, dict) or not response.get("success"):
            return False
        new_token = response.get("newToken") or response.get("token")
        if isinstance(new_token, str) and new_token:
            self.session_token = new_token
            self.headers["Authorization"] = f"Bearer {self.session_token}"
            try:
                token_parts = self.session_token.split(".")
                if len(token_parts) >= 2:
                    token_payload = token_parts[1]
                    token_payload += "=" * (4 - len(token_payload) % 4)
                    decoded = base64.urlsafe_b64decode(token_payload)
                    token_data = orjson.loads(decoded)
                    self.token_expiry = datetime.datetime.fromtimestamp(
                        token_data["exp"], tz=pytz.UTC
                    )
            except Exception as e:
                logger.debug("Could not parse refreshed JWT expiry: %s", e)
        return True

    async def logout(self: "ProjectXClientProtocol") -> bool:
        """End the Gateway session via POST /Auth/logout."""
        try:
            if self.session_token:
                await self._make_request("POST", "/Auth/logout")
        except Exception as e:
            logger.debug("Auth/logout failed: %s", e)
            return False
        finally:
            self.session_token = ""
            self._authenticated = False
            self.token_expiry = None
            self.headers.pop("Authorization", None)
        return True

    @handle_errors("authenticate")
    async def authenticate(self: "ProjectXClientProtocol") -> None:
        """
        Authenticate with ProjectX API and select account.

        This method handles the complete authentication flow:
        1. Authenticates with username and API key
        2. Retrieves available accounts
        3. Selects the specified account or first available

        The authentication token is automatically refreshed when needed
        during API calls.

        Raises:
            ProjectXAuthenticationError: If authentication fails
            ValueError: If specified account is not found

        Example:
            >>> # V3: Async authentication with error handling
            >>> async with ProjectX.from_env() as client:
            >>>     try:
            >>>         await client.authenticate()
            >>>         account = client.account_info  # Access account info after auth
            >>>         print(f"Authenticated account: {account.name}")
            >>>         print(f"Account ID: {account.id}")
            >>>         print(f"Balance: ${account.balance:,.2f}")
            >>>     except ProjectXAuthenticationError as e:
            >>>         print(f"Authentication failed: {e}")
        """
        logger.debug(LogMessages.AUTH_START, extra={"username": self.username})

        # Authenticate and get token
        auth_data = {
            "userName": self.username,
            "apiKey": self.api_key,
        }

        response = await self._make_request("POST", "/Auth/loginKey", data=auth_data)

        if not response:
            raise ProjectXAuthenticationError(ErrorMessages.AUTH_FAILED)

        self.session_token = response["token"]
        self.headers["Authorization"] = f"Bearer {self.session_token}"

        # Parse token to get expiry
        try:
            token_parts = self.session_token.split(".")
            if len(token_parts) >= 2:
                # Add padding if necessary
                token_payload = token_parts[1]
                token_payload += "=" * (4 - len(token_payload) % 4)
                decoded = base64.urlsafe_b64decode(token_payload)
                token_data = orjson.loads(decoded)
                self.token_expiry = datetime.datetime.fromtimestamp(
                    token_data["exp"], tz=pytz.UTC
                )
        except Exception as e:
            logger.warning(LogMessages.AUTH_TOKEN_PARSE_FAILED, extra={"error": str(e)})
            # Set a default expiry of 1 hour
            self.token_expiry = datetime.datetime.now(pytz.UTC) + timedelta(hours=1)

        # Get accounts using the same endpoint as sync client
        payload = {"onlyActiveAccounts": True}
        accounts_response = await self._make_request(
            "POST", "/Account/search", data=payload
        )
        if (
            not accounts_response
            or not isinstance(accounts_response, dict)
            or not accounts_response.get("success", False)
        ):
            raise ProjectXAuthenticationError(ErrorMessages.API_REQUEST_FAILED)

        accounts_data = accounts_response.get("accounts", [])
        accounts = [Account.from_api(acc) for acc in accounts_data]

        if not accounts:
            raise ProjectXAuthenticationError(ErrorMessages.AUTH_NO_ACCOUNTS)

        # Select account
        if self.account_name:
            # Find specific account
            selected_account = None
            for account in accounts:
                if account.name.upper() == self.account_name.upper():
                    selected_account = account
                    break

            if not selected_account:
                available = ", ".join(acc.name for acc in accounts)
                raise ValueError(
                    format_error_message(
                        ErrorMessages.ACCOUNT_NOT_FOUND,
                        account_name=self.account_name,
                        available_accounts=available,
                    )
                )
        else:
            # Use first account
            selected_account = accounts[0]

        self.account_info = selected_account
        self._authenticated = True
        logger.debug(
            LogMessages.AUTH_SUCCESS,
            extra={
                "account_name": selected_account.name,
                "account_id": selected_account.id,
            },
        )

    async def _ensure_authenticated(self: "ProjectXClientProtocol") -> None:
        """
        Ensure client is authenticated before making API calls.

        This method checks the authentication state and token validity before
        allowing API operations to proceed. If the client is not authenticated
        or if the authentication token is expired/about to expire, it will
        automatically trigger the full authentication flow.

        The method performs two key checks:
        1. Whether the client has successfully authenticated (_authenticated flag)
        2. Whether the token needs refreshing (via _should_refresh_token)

        This provides a seamless authentication experience by handling token
        expiration transparently without requiring explicit refresh calls.

        Note:
            This method is called internally by API methods and doesn't need
            to be called directly in normal usage.
        """
        if not self._authenticated or self._should_refresh_token():
            await self.authenticate()

    @handle_errors("list accounts")
    @validate_response(required_fields=["success", "accounts"])
    async def list_accounts(self: "ProjectXClientProtocol") -> list[Account]:
        """
        List all accounts available to the authenticated user.

        Returns:
            List of Account objects

        Raises:
            ProjectXError: If account listing fails

        Example:
            >>> # V3: List all active accounts with detailed information
            >>> accounts = await client.list_accounts()
            >>> for account in accounts:
            >>>     print(f"Account: {account.name}")
            >>>     print(f"  ID: {account.id}")
            >>>     print(f"  Balance: ${account.balance:,.2f}")
            >>>     print(f"  State: {account.state}")
            >>>     print(f"  Type: {account.type}")
        """
        await self._ensure_authenticated()

        payload = {"onlyActiveAccounts": True}
        response = await self._make_request("POST", "/Account/search", data=payload)

        if (
            not response
            or not isinstance(response, dict)
            or not response.get("success", False)
        ):
            return []

        accounts_data = response.get("accounts", [])
        return [Account.from_api(acc) for acc in accounts_data]
