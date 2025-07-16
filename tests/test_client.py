"""
Unit tests for the ProjectX client.
"""

import pytest
from unittest.mock import Mock, patch
from project_x_py import ProjectX, ProjectXConfig
from project_x_py.exceptions import ProjectXAuthenticationError, ProjectXError


class TestProjectXClient:
    """Test suite for the main ProjectX client."""

    def test_init_with_credentials(self):
        """Test client initialization with explicit credentials."""
        client = ProjectX(username="test_user", api_key="test_key")
        
        assert client.username == "test_user"
        assert client.api_key == "test_key"
        assert not client._authenticated
        assert client.session_token == ""

    def test_init_with_config(self):
        """Test client initialization with custom configuration."""
        config = ProjectXConfig(
            timeout_seconds=60,
            retry_attempts=5
        )
        
        client = ProjectX(
            username="test_user", 
            api_key="test_key",
            config=config
        )
        
        assert client.config.timeout_seconds == 60
        assert client.config.retry_attempts == 5

    def test_init_missing_credentials(self):
        """Test that initialization fails with missing credentials."""
        with pytest.raises(ValueError, match="Both username and api_key are required"):
            ProjectX(username="", api_key="test_key")
        
        with pytest.raises(ValueError, match="Both username and api_key are required"):
            ProjectX(username="test_user", api_key="")

    @patch('project_x_py.client.requests.post')
    def test_authenticate_success(self, mock_post):
        """Test successful authentication."""
        # Mock successful authentication response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "token": "test_jwt_token"
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        client = ProjectX(username="test_user", api_key="test_key")
        client._authenticate()
        
        assert client._authenticated
        assert client.session_token == "test_jwt_token"
        assert client.headers["Authorization"] == "Bearer test_jwt_token"
        
        # Verify the request was made correctly
        mock_post.assert_called_once()
        # Check that the URL contains the login endpoint
        args, kwargs = mock_post.call_args  # type: ignore
        assert "Auth/loginKey" in args[0]

    @patch('project_x_py.client.requests.post')
    def test_authenticate_failure(self, mock_post):
        """Test authentication failure."""
        # Mock failed authentication response
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {
            "success": False,
            "errorMessage": "Invalid credentials"
        }
        mock_response.raise_for_status.side_effect = Exception("401 Unauthorized")
        mock_post.return_value = mock_response
        
        client = ProjectX(username="test_user", api_key="test_key")
        
        with pytest.raises(ProjectXAuthenticationError):
            client._authenticate()

    @patch('project_x_py.client.requests.post')
    def test_get_account_info_success(self, mock_post):
        """Test successful account info retrieval."""
        # Mock authentication
        auth_response = Mock()
        auth_response.status_code = 200
        auth_response.json.return_value = {
            "success": True,
            "token": "test_token"
        }
        auth_response.raise_for_status.return_value = None
        
        # Mock account search
        account_response = Mock()
        account_response.status_code = 200
        account_response.json.return_value = {
            "success": True,
            "accounts": [{
                "id": 12345,
                "name": "Test Account",
                "balance": 50000.0,
                "canTrade": True,
                "isVisible": True,
                "simulated": False
            }]
        }
        account_response.raise_for_status.return_value = None
        
        mock_post.side_effect = [auth_response, account_response]
        
        client = ProjectX(username="test_user", api_key="test_key")
        account = client.get_account_info()
        
        assert account is not None
        assert account.id == 12345
        assert account.name == "Test Account"
        assert account.balance == 50000.0
        assert account.canTrade is True

    def test_get_session_token(self):
        """Test getting session token triggers authentication."""
        client = ProjectX(username="test_user", api_key="test_key")
        
        with patch.object(client, '_ensure_authenticated') as mock_auth:
            client.session_token = "test_token"
            token = client.get_session_token()
            
            mock_auth.assert_called_once()
            assert token == "test_token"

    def test_health_status(self):
        """Test health status reporting."""
        client = ProjectX(username="test_user", api_key="test_key")
        
        status = client.get_health_status()
        
        assert isinstance(status, dict)
        assert "authenticated" in status
        assert "has_session_token" in status
        assert "config" in status
        assert status["authenticated"] is False


class TestProjectXConfig:
    """Test suite for ProjectX configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ProjectXConfig()
        
        assert config.api_url == "https://api.topstepx.com/api"
        assert config.timezone == "America/Chicago"
        assert config.timeout_seconds == 30
        assert config.retry_attempts == 3

    def test_custom_config(self):
        """Test custom configuration values."""
        config = ProjectXConfig(
            timeout_seconds=60,
            retry_attempts=5,
            requests_per_minute=30
        )
        
        assert config.timeout_seconds == 60
        assert config.retry_attempts == 5
        assert config.requests_per_minute == 30


@pytest.fixture
def mock_client():
    """Fixture providing a mocked ProjectX client."""
    with patch('project_x_py.client.requests.post') as mock_post:
        # Mock successful authentication
        auth_response = Mock()
        auth_response.status_code = 200
        auth_response.json.return_value = {
            "success": True,
            "token": "test_token"
        }
        auth_response.raise_for_status.return_value = None
        mock_post.return_value = auth_response
        
        client = ProjectX(username="test_user", api_key="test_key")
        client._authenticate()
        
        yield client


class TestProjectXIntegration:
    """Integration tests that require authentication."""

    def test_authenticated_client_operations(self, mock_client):
        """Test operations with an authenticated client."""
        assert mock_client._authenticated
        assert mock_client.session_token == "test_token"
        
        # Test that headers are set correctly
        expected_headers = {
            "Authorization": "Bearer test_token",
            "accept": "text/plain",
            "Content-Type": "application/json",
        }
        assert mock_client.headers == expected_headers 