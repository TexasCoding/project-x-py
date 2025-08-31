"""Simplified tests for the authentication module of ProjectX client."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from project_x_py.client.auth import AuthenticationMixin
from project_x_py.exceptions import ProjectXAuthenticationError
from project_x_py.models import Account


class MockAuthClient(AuthenticationMixin):
    """Mock client that includes AuthenticationMixin for testing."""

    def __init__(self):
        super().__init__()
        self.username = "test_user"
        self.api_key = "test_api_key" # pragma: allowlist secret
        self.account_name = None
        self.base_url = "https://api.test.com"
        self.headers = {}
        self._http_client = AsyncMock()
        self._make_request = AsyncMock()
        self._auth_lock = asyncio.Lock()
        self._authenticated = False
        self.jwt_token = None
        self.session_token = None
        self.account_info = None


class TestAuthenticationMixin:
    """Test suite for AuthenticationMixin class."""

    @pytest.fixture
    def auth_client(self):
        """Create a mock client with AuthenticationMixin for testing."""
        return MockAuthClient()

    @pytest.mark.asyncio
    async def test_authenticate_success(self, auth_client):
        """Test successful authentication flow."""
        # Mock responses for the two API calls
        auth_response = {"token": "test_jwt_token"}
        accounts_response = {
            "success": True,
            "accounts": [
                {
                    "id": 1,
                    "name": "Test Account",
                    "balance": 10000.0,
                    "canTrade": True,
                    "isVisible": True,
                    "simulated": False,
                }
            ],
        }

        auth_client._make_request.side_effect = [auth_response, accounts_response]

        await auth_client.authenticate()

        assert auth_client.session_token == "test_jwt_token"
        assert auth_client.account_info.name == "Test Account"
        assert auth_client._authenticated is True

    @pytest.mark.asyncio
    async def test_authenticate_with_specific_account(self, auth_client):
        """Test authentication with specific account selection."""
        auth_client.account_name = "Second Account"

        auth_response = {"token": "test_jwt_token"}
        accounts_response = {
            "success": True,
            "accounts": [
                {
                    "id": 1,
                    "name": "First Account",
                    "balance": 5000.0,
                    "canTrade": True,
                    "isVisible": True,
                    "simulated": False,
                },
                {
                    "id": 2,
                    "name": "Second Account",
                    "balance": 10000.0,
                    "canTrade": True,
                    "isVisible": True,
                    "simulated": True,
                },
            ],
        }

        auth_client._make_request.side_effect = [auth_response, accounts_response]

        await auth_client.authenticate()

        assert auth_client.account_info.name == "Second Account"
        assert auth_client.account_info.id == 2
        assert auth_client.account_info.simulated is True

    @pytest.mark.asyncio
    async def test_authenticate_no_matching_account(self, auth_client):
        """Test authentication fails when specified account not found."""
        auth_client.account_name = "Nonexistent Account"

        auth_response = {"token": "test_jwt_token"}
        accounts_response = {
            "success": True,
            "accounts": [
                {
                    "id": 1,
                    "name": "Only Account",
                    "balance": 5000.0,
                    "canTrade": True,
                    "isVisible": True,
                    "simulated": False,
                }
            ],
        }

        auth_client._make_request.side_effect = [auth_response, accounts_response]

        from project_x_py.exceptions import ProjectXError

        with pytest.raises(ProjectXError, match="not found"):
            await auth_client.authenticate()

    @pytest.mark.asyncio
    async def test_authenticate_no_accounts(self, auth_client):
        """Test authentication fails when no accounts returned."""
        auth_response = {"token": "test_jwt_token"}
        accounts_response = {"success": True, "accounts": []}

        auth_client._make_request.side_effect = [auth_response, accounts_response]

        with pytest.raises(ProjectXAuthenticationError, match="No accounts found"):
            await auth_client.authenticate()

    @pytest.mark.asyncio
    async def test_ensure_authenticated_when_not_authenticated(self, auth_client):
        """Test _ensure_authenticated triggers authentication."""
        auth_client._authenticated = False
        auth_client.authenticate = AsyncMock()

        await auth_client._ensure_authenticated()

        auth_client.authenticate.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_authenticated_when_authenticated(self, auth_client):
        """Test _ensure_authenticated skips when already authenticated."""
        auth_client._authenticated = True
        auth_client.jwt_token = "valid_token"
        auth_client.account_info = Account(
            id=1,
            name="Test",
            balance=10000.0,
            canTrade=True,
            isVisible=True,
            simulated=False,
        )
        auth_client.authenticate = AsyncMock()
        auth_client._should_refresh_token = lambda: False  # Mock to return False

        await auth_client._ensure_authenticated()

        auth_client.authenticate.assert_not_called()

    def test_should_refresh_token_near_expiry(self, auth_client):
        """Test _should_refresh_token returns True when token is near expiry."""
        import pytz

        auth_client.token_expiry = datetime.now(pytz.UTC) + timedelta(minutes=4)
        assert auth_client._should_refresh_token() is True

    def test_should_refresh_token_plenty_time(self, auth_client):
        """Test _should_refresh_token returns False when token has time."""
        import pytz

        auth_client.token_expiry = datetime.now(pytz.UTC) + timedelta(hours=2)
        assert auth_client._should_refresh_token() is False

    def test_should_refresh_token_no_expiry(self, auth_client):
        """Test _should_refresh_token returns True when no expiry set."""
        auth_client.token_expiry = None
        assert auth_client._should_refresh_token() is True

    @pytest.mark.asyncio
    async def test_list_accounts(self, auth_client):
        """Test listing all available accounts."""
        accounts_response = {
            "success": True,
            "accounts": [
                {
                    "id": 1,
                    "name": "Account 1",
                    "balance": 5000.0,
                    "canTrade": True,
                    "isVisible": True,
                    "simulated": False,
                },
                {
                    "id": 2,
                    "name": "Account 2",
                    "balance": 10000.0,
                    "canTrade": True,
                    "isVisible": True,
                    "simulated": True,
                },
            ],
        }

        auth_client._make_request.return_value = accounts_response
        auth_client._ensure_authenticated = AsyncMock()  # Mock authentication check

        accounts = await auth_client.list_accounts()

        assert len(accounts) == 2
        assert accounts[0].name == "Account 1"
        assert accounts[1].name == "Account 2"

    @pytest.mark.asyncio
    async def test_authentication_error_handling(self, auth_client):
        """Test proper error handling during authentication."""
        auth_client._make_request.side_effect = Exception("Connection failed")

        with pytest.raises(Exception, match="Connection failed"):
            await auth_client.authenticate()

        assert auth_client._authenticated is False
        assert auth_client.jwt_token is None
