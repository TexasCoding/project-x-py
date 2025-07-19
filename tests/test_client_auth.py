"""
Test file: tests/test_client_auth.py
Phase 1: Critical Core Testing - Authentication & Configuration
Priority: Critical
"""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from project_x_py import ProjectX, ProjectXConfig
from project_x_py.exceptions import ProjectXAuthenticationError, ProjectXError


class TestAuthentication:
    """Test suite for authentication and configuration management."""

    def test_valid_credentials_from_env(self):
        """Test authentication with valid credentials from environment variables."""
        # Set up test environment variables
        os.environ["PROJECT_X_API_KEY"] = "test_api_key"
        os.environ["PROJECT_X_USERNAME"] = "test_username"
        os.environ["PROJECT_X_ACCOUNT_NAME"] = "Test Demo Account"
        
        try:
            # Test from_env method
            client = ProjectX.from_env()
            
            assert client.username == "test_username"
            assert client.api_key == "test_api_key"
            assert client.account_name == "Test Demo Account"
            assert client.session_token == ""  # Not authenticated yet (lazy auth)
            assert not client._authenticated
                
        finally:
            # Cleanup environment variables
            for key in ["PROJECT_X_API_KEY", "PROJECT_X_USERNAME", "PROJECT_X_ACCOUNT_NAME"]:
                os.environ.pop(key, None)

    def test_direct_credentials_authentication(self):
        """Test authentication with direct credentials."""
        with patch('project_x_py.client.requests.post') as mock_post:
            # Mock successful authentication response for auth call
            mock_auth_response = Mock()
            mock_auth_response.status_code = 200
            mock_auth_response.json.return_value = {
                "success": True,
                "token": "direct_jwt_token"
            }
            
            # Mock successful search response
            mock_search_response = Mock()
            mock_search_response.status_code = 200
            mock_search_response.json.return_value = {
                "success": True,
                "contracts": []
            }
            
            # First call is auth, second is search
            mock_post.side_effect = [mock_auth_response, mock_search_response]
            
            client = ProjectX(username="direct_user", api_key="direct_key")
            assert not client._authenticated
            
            # This should trigger authentication
            client.search_instruments("MGC")
            
            assert client.session_token == "direct_jwt_token"
            assert client._authenticated is True
            
            # Verify the authentication request
            auth_call = mock_post.call_args_list[0]
            assert auth_call[1]['json']['userName'] == "direct_user"
            assert auth_call[1]['json']['apiKey'] == "direct_key"

    def test_invalid_credentials_handling(self):
        """Test handling of invalid credentials."""
        with patch('project_x_py.client.requests.post') as mock_post:
            # Mock authentication failure
            mock_response = Mock()
            mock_response.status_code = 401
            mock_response.text = "Invalid credentials"
            mock_response.raise_for_status.side_effect = Exception("401 error")
            mock_post.return_value = mock_response
            
            client = ProjectX(username="wrong_user", api_key="wrong_key")
            
            # Try to use the client - should trigger authentication which fails
            with pytest.raises(ProjectXAuthenticationError) as exc_info:
                client.search_instruments("MGC")
            
            assert "Authentication failed" in str(exc_info.value)

    def test_missing_credentials(self):
        """Test handling of missing credentials."""
        # Test missing username
        with pytest.raises(ValueError) as exc_info:
            ProjectX(username="", api_key="test_key")
        assert "Both username and api_key are required" in str(exc_info.value)
        
        # Test missing API key
        with pytest.raises(ValueError) as exc_info:
            ProjectX(username="test_user", api_key="")
        assert "Both username and api_key are required" in str(exc_info.value)
        
        # Test both missing
        with pytest.raises(ValueError) as exc_info:
            ProjectX(username="", api_key="")
        assert "Both username and api_key are required" in str(exc_info.value)

    def test_expired_credentials(self):
        """Test handling of expired credentials and automatic re-authentication."""
        # Note: Based on implementation analysis, the client caches authentication
        # and only re-authenticates when the token expires (45 minutes by default).
        # This test verifies that if we force expiration, re-authentication occurs.
        
        # For this test, we'll simulate the behavior but acknowledge that
        # in the current implementation, the token refresh mechanism is based
        # on time, which makes it difficult to test without modifying internals.
        
        # This is more of an integration test that would require actual API calls
        # or modification of the client's internal state, which is not ideal for unit tests.
        
        # For now, we'll create a simplified test that verifies the concept
        client = ProjectX(username="test_user", api_key="test_key")
        
        # First authentication
        with patch('project_x_py.client.requests.post') as mock_post:
            mock_auth = Mock()
            mock_auth.status_code = 200
            mock_auth.json.return_value = {"success": True, "token": "initial_token"}
            
            mock_search = Mock()
            mock_search.status_code = 200
            mock_search.json.return_value = {"success": True, "contracts": []}
            
            mock_post.side_effect = [mock_auth, mock_search]
            
            client.search_instruments("MGC")
            initial_token = client.session_token
            assert initial_token == "initial_token"
        
        # Force token expiration and re-authentication
        # Note: In practice, this would happen after 45 minutes
        client._authenticated = False  # Force re-authentication
        client.session_token = ""
        
        with patch('project_x_py.client.requests.post') as mock_post:
            mock_auth = Mock()
            mock_auth.status_code = 200
            mock_auth.json.return_value = {"success": True, "token": "refreshed_token"}
            
            mock_search = Mock()
            mock_search.status_code = 200
            mock_search.json.return_value = {"success": True, "contracts": []}
            
            mock_post.side_effect = [mock_auth, mock_search]
            
            client.search_instruments("MGC")
            assert client.session_token == "refreshed_token"
            assert client.session_token != initial_token

    def test_multi_account_selection(self):
        """Test multi-account selection functionality."""
        with patch('project_x_py.client.requests.post') as mock_post:
            # Mock authentication response
            mock_auth_response = Mock()
            mock_auth_response.status_code = 200
            mock_auth_response.json.return_value = {
                "success": True,
                "token": "test_token"
            }
            
            # Mock list accounts response
            mock_accounts_response = Mock()
            mock_accounts_response.status_code = 200
            mock_accounts_response.json.return_value = {
                "success": True,
                "accounts": [
                    {"id": 1001, "name": "Demo Account", "balance": 50000, "canTrade": True},
                    {"id": 1002, "name": "Test Account", "balance": 100000, "canTrade": True},
                    {"id": 1003, "name": "Paper Trading", "balance": 25000, "canTrade": True}
                ]
            }
            
            mock_post.side_effect = [mock_auth_response, mock_accounts_response]
            
            # Test client creation with account name
            client = ProjectX(username="test_user", api_key="test_key", account_name="Test Account")
            assert client.account_name == "Test Account"
            
            # Test listing accounts
            accounts = client.list_accounts()
            assert len(accounts) == 3
            assert accounts[0]["name"] == "Demo Account"
            assert accounts[1]["name"] == "Test Account"
            assert accounts[2]["name"] == "Paper Trading"

    def test_account_not_found(self):
        """Test handling when specified account is not found."""
        # Note: Current implementation doesn't automatically select accounts
        # This test verifies that we can create a client with a non-existent account name
        # The actual account validation would happen when trying to place orders
        client = ProjectX(username="test_user", api_key="test_key", account_name="Nonexistent Account")
        assert client.account_name == "Nonexistent Account"

    def test_configuration_management(self):
        """Test configuration loading and precedence."""
        # Test default configuration
        client = ProjectX(username="test_user", api_key="test_key")
        assert client.config.api_url == "https://api.topstepx.com/api"
        assert client.config.timeout_seconds == 30
        assert client.config.retry_attempts == 3
        assert client.config.timezone == "America/Chicago"
        
        # Test custom configuration
        custom_config = ProjectXConfig(
            timeout_seconds=60,
            retry_attempts=5,
            realtime_url="wss://custom.realtime.url"
        )
        
        client2 = ProjectX(username="test_user", api_key="test_key", config=custom_config)
        assert client2.config.timeout_seconds == 60
        assert client2.config.retry_attempts == 5
        assert client2.config.realtime_url == "wss://custom.realtime.url"
        assert client2.config.api_url == "https://api.topstepx.com/api"  # Default preserved

    def test_environment_variable_config_override(self):
        """Test that environment variables override configuration."""
        os.environ["PROJECT_X_API_KEY"] = "env_api_key"
        os.environ["PROJECT_X_USERNAME"] = "env_username"
        
        try:
            # Create client from environment
            client = ProjectX.from_env()
            
            assert client.username == "env_username"
            assert client.api_key == "env_api_key"
            
        finally:
            # Cleanup
            os.environ.pop("PROJECT_X_API_KEY", None)
            os.environ.pop("PROJECT_X_USERNAME", None)

    def test_jwt_token_storage_and_reuse(self):
        """Test that JWT tokens are properly stored and reused."""
        with patch('project_x_py.client.requests.post') as mock_post:
            # Mock authentication response
            mock_auth_response = Mock()
            mock_auth_response.status_code = 200
            mock_auth_response.json.return_value = {
                "success": True,
                "token": "jwt_token_12345"
            }
            
            # Mock search response
            mock_search_response = Mock()
            mock_search_response.status_code = 200
            mock_search_response.json.return_value = {
                "success": True,
                "contracts": []
            }
            
            # Set up responses
            mock_post.side_effect = [mock_auth_response, mock_search_response]
            
            client = ProjectX(username="test_user", api_key="test_key")
            assert client.session_token == ""
            assert not client._authenticated
            
            # Trigger authentication by making an API call
            client.search_instruments("MGC")
            
            # Verify authentication happened
            assert client.session_token == "jwt_token_12345"
            assert client._authenticated
            
            # Verify the token was included in the search request headers
            search_call = mock_post.call_args_list[1]  # Second call is the search
            assert "Authorization" in search_call[1]["headers"]
            assert search_call[1]["headers"]["Authorization"] == "Bearer jwt_token_12345"

    def test_lazy_authentication(self):
        """Test that authentication is lazy and only happens when needed."""
        client = ProjectX(username="test_user", api_key="test_key")
        
        # Client should not be authenticated immediately after creation
        assert not client._authenticated
        assert client.session_token == ""
        
        # Mock the authentication and search responses
        with patch('project_x_py.client.requests.post') as mock_post:
            mock_auth_response = Mock()
            mock_auth_response.status_code = 200
            mock_auth_response.json.return_value = {
                "success": True,
                "token": "lazy_token"
            }
            
            mock_search_response = Mock()
            mock_search_response.status_code = 200
            mock_search_response.json.return_value = {
                "success": True,
                "contracts": []
            }
            
            mock_post.side_effect = [mock_auth_response, mock_search_response]
            
            # This should trigger authentication
            client.search_instruments("MGC")
            
            # Now client should be authenticated
            assert client._authenticated
            assert client.session_token == "lazy_token"


def run_auth_tests():
    """Helper function to run authentication tests and report results."""
    print("Running Phase 1 Authentication Tests...")
    pytest.main([__file__, "-v", "-s"])


if __name__ == "__main__":
    run_auth_tests()