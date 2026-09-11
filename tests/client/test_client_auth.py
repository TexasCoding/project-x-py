"""Tests for the authentication functionality of ProjectX client."""

from unittest.mock import AsyncMock, patch

import pytest

from project_x_py.exceptions import ProjectXAuthenticationError, ProjectXError


class TestClientAuth:
    """Tests for the authentication functionality of ProjectX client."""

    @pytest.mark.asyncio
    async def test_authenticate_success(self, initialized_client, mock_auth_response):
        """Test successful authentication flow."""
        client = initialized_client
        auth_response, accounts_response = mock_auth_response
        client._client.request.side_effect = [auth_response, accounts_response]

        await client.authenticate()

        assert client._authenticated
        assert client.session_token == auth_response.json()["token"]
        assert client.account_info is not None
        assert client.account_info.name == "Test Account"
        assert client.account_info.id == 12345

        # Check correct endpoints were called
        assert client._client.request.call_count == 2
        auth_call = client._client.request.call_args_list[0]
        assert auth_call[1]["method"] == "POST"
        assert auth_call[1]["url"].endswith("/Auth/loginKey")

        accounts_call = client._client.request.call_args_list[1]
        assert accounts_call[1]["method"] == "POST"
        assert accounts_call[1]["url"].endswith("/Account/search")

    @pytest.mark.asyncio
    async def test_authenticate_failure(self, initialized_client, mock_response):
        """Test authentication failure handling."""
        client = initialized_client
        # Mock failed auth response
        failed_response = mock_response(
            status_code=401,
            json_data={"success": False, "message": "Invalid credentials"},
        )
        client._client.request.return_value = failed_response

        with pytest.raises(ProjectXAuthenticationError, match="Authentication failed"):
            await client.authenticate()

        assert not client._authenticated
        assert not client.session_token

    @pytest.mark.asyncio
    async def test_authenticate_with_specific_account(
        self, initialized_client, mock_auth_response
    ):
        """Test authentication with specific account selection."""
        client = initialized_client
        client.account_name = "Secondary Account"

        auth_response, accounts_response = mock_auth_response
        # Add a second account to test selection
        accounts_data = accounts_response.json()
        accounts_data["accounts"].append(
            {
                "id": 67890,
                "name": "Secondary Account",
                "balance": 50000.0,
                "canTrade": True,
                "isVisible": True,
                "simulated": True,
            }
        )
        accounts_response.json.return_value = accounts_data

        client._client.request.side_effect = [auth_response, accounts_response]

        await client.authenticate()

        assert client._authenticated
        assert client.account_info is not None
        assert client.account_info.name == "Secondary Account"
        assert client.account_info.id == 67890

    @pytest.mark.asyncio
    async def test_authenticate_with_invalid_account(
        self, initialized_client, mock_auth_response
    ):
        """Test authentication with non-existent account name."""
        client = initialized_client
        client.account_name = "NonExistent"

        auth_response, accounts_response = mock_auth_response

        client._client.request.side_effect = [auth_response, accounts_response]

        with pytest.raises(ProjectXError) as exc_info:
            await client.authenticate()

        # Verify the error message contains the available account name
        error_msg = str(exc_info.value)
        assert "NonExistent" in error_msg
        assert "Test Account" in error_msg

    @pytest.mark.asyncio
    async def test_token_refresh(
        self, initialized_client, mock_auth_response, mock_response
    ):
        """Test token refresh when expired."""
        from datetime import datetime, timedelta

        import pytz

        client = initialized_client
        auth_response, accounts_response = mock_auth_response

        # Set up initial side effects for authentication
        client._client.request.side_effect = [
            auth_response,  # Initial auth
            accounts_response,  # Initial accounts fetch
        ]

        await client.authenticate()

        # Save initial call count
        initial_calls = client._client.request.call_count

        # Force token expiry
        client.token_expiry = datetime.now(pytz.UTC) - timedelta(minutes=10)

        # Now set up the side effects for the token refresh scenario
        # When _ensure_authenticated detects expired token, it will call authenticate again
        client._client.request.side_effect = [
            auth_response,  # Refresh auth
            accounts_response,  # Refresh accounts
        ]

        # This should trigger token refresh due to expired token
        await client._ensure_authenticated()

        # Should have authenticated twice (initial + refresh)
        assert client._client.request.call_count == initial_calls + 2

        # Check that token refresh happened
        calls = client._client.request.call_args_list
        assert calls[-2][1]["url"].endswith("/Auth/loginKey")
        assert calls[-1][1]["url"].endswith("/Account/search")

    @pytest.mark.asyncio
    async def test_from_env_initialization(
        self, auth_env_vars, mock_httpx_client, mock_auth_response
    ):
        """Test client initialization from environment variables."""
        from project_x_py import ProjectX

        auth_response, accounts_response = mock_auth_response
        mock_httpx_client.request.side_effect = [auth_response, accounts_response]

        with patch("httpx.AsyncClient", return_value=mock_httpx_client):
            async with ProjectX.from_env() as client:
                # Initialize required attributes
                client.api_call_count = 0
                client.rate_limiter = client.rate_limiter  # Ensure it exists

                await client.authenticate()

                assert client._authenticated
                assert client.username == "testuser"
                assert client.api_key == (
                    "test-api-key-1234567890"  # pragma: allowlist secret
                )
                assert client.account_name == "TEST ACCOUNT"

    @pytest.mark.asyncio
    async def test_list_accounts(self, initialized_client, mock_auth_response):
        """Test listing available accounts."""
        client = initialized_client
        auth_response, accounts_response = mock_auth_response
        # Add a second account to test listing multiple accounts
        accounts_data = accounts_response.json()
        accounts_data["accounts"].append(
            {
                "id": 67890,
                "name": "Secondary Account",
                "balance": 50000.0,
                "canTrade": True,
                "isVisible": True,
                "simulated": True,
            }
        )
        accounts_response.json.return_value = accounts_data

        client._client.request.side_effect = [
            auth_response,  # Initial auth
            accounts_response,  # Initial accounts fetch
            accounts_response,  # list_accounts call
        ]

        await client.authenticate()

        accounts = await client.list_accounts()

        assert len(accounts) == 2
        assert accounts[0].name == "Test Account"
        assert accounts[0].id == 12345
        assert accounts[1].name == "Secondary Account"
        assert accounts[1].id == 67890

    @pytest.mark.asyncio
    async def test_list_accounts_still_raises_connection_timeout(
        self, initialized_client
    ):
        """Transport failure stays ProjectXConnectionError, not an empty account list."""
        from project_x_py.exceptions import ProjectXConnectionError

        client = initialized_client
        client._authenticated = True
        client._ensure_authenticated = AsyncMock()
        client._make_request = AsyncMock(
            side_effect=ProjectXConnectionError("ConnectTimeout")
        )

        with pytest.raises(ProjectXConnectionError, match="ConnectTimeout"):
            await client.list_accounts()

    @pytest.mark.asyncio
    async def test_token_extraction(self, initialized_client, mock_auth_response):
        """Test extraction of expiry time from token."""
        client = initialized_client
        auth_response, accounts_response = mock_auth_response
        client._client.request.side_effect = [auth_response, accounts_response]

        await client.authenticate()

        assert client.token_expiry is not None
        # The mock token is set to expire far in the future
        assert client.token_expiry.year > 2200

    @pytest.mark.asyncio
    async def test_get_session_token(self, initialized_client, mock_auth_response):
        """Test getting session token."""
        client = initialized_client
        auth_response, accounts_response = mock_auth_response
        client._client.request.side_effect = [auth_response, accounts_response]

        await client.authenticate()

        token = client.get_session_token()
        assert token == auth_response.json()["token"]

    @pytest.mark.asyncio
    async def test_get_session_token_not_authenticated(self, initialized_client):
        """Test error when getting session token without authentication."""
        client = initialized_client

        with pytest.raises(ProjectXAuthenticationError, match="Not authenticated"):
            client.get_session_token()

    @pytest.mark.asyncio
    async def test_get_account_info(self, initialized_client, mock_auth_response):
        """Test getting account info."""
        client = initialized_client
        auth_response, accounts_response = mock_auth_response
        client._client.request.side_effect = [auth_response, accounts_response]

        await client.authenticate()

        account = client.get_account_info()
        assert account.name == "Test Account"
        assert account.id == 12345
        assert account.balance == 100000.0

    @pytest.mark.asyncio
    async def test_get_account_info_not_authenticated(self, initialized_client):
        """Test error when getting account info without authentication."""
        client = initialized_client

        with pytest.raises(ProjectXAuthenticationError, match="No account selected"):
            client.get_account_info()
