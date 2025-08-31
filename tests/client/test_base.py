"""Comprehensive tests for the base module of ProjectX client."""

import os
from unittest.mock import AsyncMock, Mock, patch

import pytest

from project_x_py.client.base import ProjectXBase
from project_x_py.exceptions import ProjectXAuthenticationError
from project_x_py.models import Account, ProjectXConfig


class TestProjectXBase:
    """Test suite for ProjectXBase class."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration."""
        return ProjectXConfig(
            api_url="https://api.test.com",
            realtime_url="wss://realtime.test.com",
            user_hub_url="/tradehub-userhub",
            market_hub_url="/tradehub-markethub",
            timezone="America/Chicago",
            timeout_seconds=30,
            retry_attempts=3,
            retry_delay_seconds=1.0,
            requests_per_minute=100,
            burst_limit=10,
        )

    @pytest.fixture
    def base_client(self, mock_config):
        """Create a ProjectXBase client for testing."""
        return ProjectXBase(
            username="testuser",
            api_key="test-api-key", # pragma: allowlist secret
            config=mock_config,
            account_name="TEST_ACCOUNT",
        )

    def test_initialization(self, base_client):
        """Test client initialization."""
        assert base_client.username == "testuser"
        assert base_client.api_key == "test-api-key" # pragma: allowlist secret
        assert base_client.account_name == "TEST_ACCOUNT"
        assert base_client.base_url == "https://api.test.com"
        assert base_client._client is None
        assert base_client._authenticated is False
        assert base_client.session_token == ""  # Initialized as empty string
        assert base_client.account_info is None
        assert base_client.api_call_count == 0
        assert base_client.cache_hit_count == 0

    def test_initialization_with_defaults(self):
        """Test client initialization with default config."""
        client = ProjectXBase(
            username="user",
            api_key="key", # pragma: allowlist secret
        )
        assert client.username == "user"
        assert client.api_key == "key" # pragma: allowlist secret
        assert client.account_name is None
        assert client.base_url == "https://api.topstepx.com/api"  # Default URL

    @pytest.mark.asyncio
    async def test_context_manager(self, base_client):
        """Test async context manager functionality."""
        mock_http_client = AsyncMock()

        with patch(
            "project_x_py.client.base.httpx.AsyncClient", return_value=mock_http_client
        ):
            async with base_client as client:
                assert client is base_client
                assert base_client._client is not None

            # After exiting context, client should be closed
            mock_http_client.aclose.assert_called_once()
            assert base_client._client is None

    @pytest.mark.asyncio
    async def test_context_manager_with_exception(self, base_client):
        """Test context manager handles exceptions properly."""
        mock_http_client = AsyncMock()

        with patch(
            "project_x_py.client.base.httpx.AsyncClient", return_value=mock_http_client
        ):
            with pytest.raises(ValueError, match="Test exception"):
                async with base_client:
                    raise ValueError("Test exception")

            # Client should still be closed even with exception
            mock_http_client.aclose.assert_called_once()

    def test_get_session_token_when_authenticated(self, base_client):
        """Test getting session token when authenticated."""
        base_client._authenticated = True
        base_client.session_token = "test-session-token"

        token = base_client.get_session_token()
        assert token == "test-session-token"

    def test_get_session_token_when_not_authenticated(self, base_client):
        """Test getting session token when not authenticated."""
        base_client._authenticated = False

        with pytest.raises(ProjectXAuthenticationError, match="Not authenticated"):
            base_client.get_session_token()

    def test_get_session_token_no_token(self, base_client):
        """Test getting session token when authenticated but no token."""
        base_client._authenticated = True
        base_client.session_token = ""  # Empty string counts as no token

        with pytest.raises(ProjectXAuthenticationError, match="Not authenticated"):
            base_client.get_session_token()

    def test_get_account_info_when_available(self, base_client):
        """Test getting account info when available."""
        account = Account(
            id=12345,
            name="Test Account",
            balance=10000.0,
            canTrade=True,
            isVisible=True,
            simulated=False,
        )
        base_client.account_info = account

        result = base_client.get_account_info()
        assert result == account

    def test_get_account_info_when_not_available(self, base_client):
        """Test getting account info when not available."""
        base_client.account_info = None

        with pytest.raises(ProjectXAuthenticationError, match="No account selected"):
            base_client.get_account_info()

    @pytest.mark.asyncio
    async def test_from_env_success(self):
        """Test creating client from environment variables."""
        with patch.dict(
            os.environ,
            {
                "PROJECT_X_USERNAME": "env_user",
                "PROJECT_X_API_KEY": "env_key", # pragma: allowlist secret
                "PROJECT_X_ACCOUNT_NAME": "env_account",
            },
        ):
            with patch("project_x_py.client.base.ConfigManager") as mock_config_manager:
                mock_manager = Mock()
                mock_manager.get_auth_config.return_value = {
                    "username": "env_user",
                    "api_key": "env_key", # pragma: allowlist secret
                }
                mock_config_manager.return_value = mock_manager

                mock_http_client = AsyncMock()
                with patch(
                    "project_x_py.client.base.httpx.AsyncClient",
                    return_value=mock_http_client,
                ):
                    async with ProjectXBase.from_env() as client:
                        assert client.username == "env_user"
                        assert client.api_key == "env_key" # pragma: allowlist secret
                        assert (
                            client.account_name == "ENV_ACCOUNT"
                        )  # Should be uppercase

    @pytest.mark.asyncio
    async def test_from_env_with_custom_account(self):
        """Test creating client from environment with custom account name."""
        with patch.dict(
            os.environ,
            {
                "PROJECT_X_USERNAME": "env_user",
                "PROJECT_X_API_KEY": "env_key", # pragma: allowlist secret
            },
        ):
            with patch("project_x_py.client.base.ConfigManager") as mock_config_manager:
                mock_manager = Mock()
                mock_manager.get_auth_config.return_value = {
                    "username": "env_user",
                    "api_key": "env_key", # pragma: allowlist secret
                }
                mock_config_manager.return_value = mock_manager

                mock_http_client = AsyncMock()
                with patch(
                    "project_x_py.client.base.httpx.AsyncClient",
                    return_value=mock_http_client,
                ):
                    async with ProjectXBase.from_env(
                        account_name="custom_account"
                    ) as client:
                        assert client.account_name == "CUSTOM_ACCOUNT"

    @pytest.mark.asyncio
    async def test_from_env_with_custom_config(self):
        """Test creating client from environment with custom config."""
        custom_config = ProjectXConfig(
            api_url="https://custom.api.com",
            realtime_url="wss://custom.realtime.com",
            user_hub_url="/custom-userhub",
            market_hub_url="/custom-markethub",
            timezone="Europe/London",
            timeout_seconds=60,
            retry_attempts=5,
            retry_delay_seconds=2.0,
            requests_per_minute=200,
            burst_limit=20,
        )

        with patch.dict(
            os.environ,
            {
                "PROJECT_X_USERNAME": "env_user",
                "PROJECT_X_API_KEY": "env_key", # pragma: allowlist secret
            },
        ):
            with patch("project_x_py.client.base.ConfigManager") as mock_config_manager:
                mock_manager = Mock()
                mock_manager.get_auth_config.return_value = {
                    "username": "env_user",
                    "api_key": "env_key", # pragma: allowlist secret
                }
                mock_config_manager.return_value = mock_manager

                mock_http_client = AsyncMock()
                with patch(
                    "project_x_py.client.base.httpx.AsyncClient",
                    return_value=mock_http_client,
                ):
                    async with ProjectXBase.from_env(config=custom_config) as client:
                        assert client.config == custom_config
                        assert client.base_url == "https://custom.api.com"

    @pytest.mark.asyncio
    async def test_from_config_file(self):
        """Test creating client from config file."""
        with patch("project_x_py.client.base.ConfigManager") as mock_config_manager:
            mock_manager = Mock()
            mock_config = ProjectXConfig(
                api_url="https://file.api.com",
                realtime_url="wss://file.realtime.com",
                user_hub_url="/file-userhub",
                market_hub_url="/file-markethub",
                timezone="US/Pacific",
                timeout_seconds=45,
                retry_attempts=4,
                retry_delay_seconds=1.5,
                requests_per_minute=150,
                burst_limit=15,
            )
            mock_manager.load_config.return_value = mock_config
            mock_manager.get_auth_config.return_value = {
                "username": "file_user",
                "api_key": "file_key", # pragma: allowlist secret
            }
            mock_config_manager.return_value = mock_manager

            mock_http_client = AsyncMock()
            with patch(
                "project_x_py.client.base.httpx.AsyncClient",
                return_value=mock_http_client,
            ):
                async with ProjectXBase.from_config_file("test_config.json") as client:
                    assert client.username == "file_user"
                    assert client.api_key == "file_key" # pragma: allowlist secret
                    assert client.base_url == "https://file.api.com"

                    # Verify ConfigManager was called with the config file
                    mock_config_manager.assert_called_once_with("test_config.json")

    @pytest.mark.asyncio
    async def test_from_config_file_with_account_name(self):
        """Test creating client from config file with account name."""
        with patch("project_x_py.client.base.ConfigManager") as mock_config_manager:
            mock_manager = Mock()
            mock_config = ProjectXConfig(
                api_url="https://file.api.com",
                realtime_url="wss://file.realtime.com",
                user_hub_url="/file-userhub",
                market_hub_url="/file-markethub",
                timezone="US/Pacific",
                timeout_seconds=45,
                retry_attempts=4,
                retry_delay_seconds=1.5,
                requests_per_minute=150,
                burst_limit=15,
            )
            mock_manager.load_config.return_value = mock_config
            mock_manager.get_auth_config.return_value = {
                "username": "file_user",
                "api_key": "file_key", # pragma: allowlist secret
            }
            mock_config_manager.return_value = mock_manager

            mock_http_client = AsyncMock()
            with patch(
                "project_x_py.client.base.httpx.AsyncClient",
                return_value=mock_http_client,
            ):
                async with ProjectXBase.from_config_file(
                    "test_config.json", account_name="file_account"
                ) as client:
                    assert client.account_name == "FILE_ACCOUNT"

    def test_headers_property(self, base_client):
        """Test headers property."""
        assert base_client.headers == {"Content-Type": "application/json"}

    def test_config_property(self, mock_config):
        """Test config property."""
        client = ProjectXBase(
            username="user",
            api_key="key", # pragma: allowlist secret
            config=mock_config,
        )
        assert client.config == mock_config
        assert client.config.timezone == "America/Chicago"

    def test_rate_limiter_initialization(self, base_client):
        """Test rate limiter is properly initialized."""
        assert base_client.rate_limiter is not None
        assert base_client.rate_limiter.max_requests == 100
        assert base_client.rate_limiter.window_seconds == 60
