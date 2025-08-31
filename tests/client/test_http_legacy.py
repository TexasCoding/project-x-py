"""Tests for the HTTP module of ProjectX client."""

from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from project_x_py.client.http import HttpMixin
from project_x_py.exceptions import (
    ProjectXAuthenticationError,
    ProjectXConnectionError,
    ProjectXDataError,
    ProjectXError,
    ProjectXRateLimitError,
    ProjectXServerError,
)


class MockHttpClient(HttpMixin):
    """Mock client that includes HttpMixin for testing."""

    def __init__(self):
        super().__init__()
        self.base_url = "https://api.test.com"
        self.headers = {"X-Test": "test"}
        self.session_token = None
        self.config = Mock()
        self.config.timeout_seconds = 30
        self.rate_limiter = Mock()
        self.rate_limiter.acquire = AsyncMock()
        self.cache_hit_count = 0
        self._refresh_authentication = AsyncMock()


class TestHttpMixin:
    """Test suite for HttpMixin class."""

    @pytest.fixture
    def http_client(self):
        """Create a mock client with HttpMixin for testing."""
        return MockHttpClient()

    @pytest.mark.asyncio
    async def test_create_client(self, http_client):
        """Test HTTP client creation with proper configuration."""
        client = await http_client._create_client()

        assert isinstance(client, httpx.AsyncClient)
        assert client.timeout.connect == 5.0
        assert client.timeout.read == 30
        assert client.follow_redirects is True
        # HTTP/2 is enabled via parameter but not exposed as attribute

        await client.aclose()

    @pytest.mark.asyncio
    async def test_ensure_client_creates_new(self, http_client):
        """Test _ensure_client creates client when none exists."""
        assert http_client._client is None

        client = await http_client._ensure_client()

        assert client is not None
        assert http_client._client is client

        await client.aclose()

    @pytest.mark.asyncio
    async def test_ensure_client_reuses_existing(self, http_client):
        """Test _ensure_client reuses existing client."""
        mock_client = Mock(spec=httpx.AsyncClient)
        http_client._client = mock_client

        client = await http_client._ensure_client()

        assert client is mock_client

    @pytest.mark.asyncio
    async def test_make_request_success(self, http_client):
        """Test successful API request."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True, "data": "test"}

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.request.return_value = mock_response
        http_client._client = mock_client

        result = await http_client._make_request("GET", "/test")

        assert result == {"success": True, "data": "test"}
        assert http_client.api_call_count == 1
        mock_client.request.assert_called_once()
        http_client.rate_limiter.acquire.assert_called_once()

    @pytest.mark.asyncio
    async def test_make_request_with_data_and_params(self, http_client):
        """Test API request with data and parameters."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "ok"}

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.request.return_value = mock_response
        http_client._client = mock_client

        data = {"key": "value"}
        params = {"param": "test"}

        result = await http_client._make_request(
            "POST", "/test", data=data, params=params
        )

        assert result == {"result": "ok"}
        call_args = mock_client.request.call_args
        assert call_args.kwargs["json"] == data
        assert call_args.kwargs["params"] == params

    @pytest.mark.asyncio
    async def test_make_request_with_auth_token(self, http_client):
        """Test that auth token is included in headers."""
        http_client.session_token = "test_token"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.request.return_value = mock_response
        http_client._client = mock_client

        await http_client._make_request("GET", "/test")

        call_args = mock_client.request.call_args
        assert "Authorization" in call_args.kwargs["headers"]
        assert call_args.kwargs["headers"]["Authorization"] == "Bearer test_token"

    @pytest.mark.asyncio
    async def test_make_request_no_auth_for_login(self, http_client):
        """Test that auth token is not included for login endpoint."""
        http_client.session_token = "test_token"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"token": "new_token"}

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.request.return_value = mock_response
        http_client._client = mock_client

        await http_client._make_request("POST", "/Auth/loginKey")

        call_args = mock_client.request.call_args
        # Should not have Authorization header for login endpoint
        assert "Authorization" not in call_args.kwargs["headers"]

    @pytest.mark.asyncio
    @patch("asyncio.sleep", return_value=None)  # Mock sleep to avoid waiting
    async def test_make_request_rate_limit_error(self, mock_sleep, http_client):
        """Test handling of rate limit errors."""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "30"}

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.request.return_value = mock_response
        http_client._client = mock_client

        with pytest.raises(ProjectXRateLimitError, match="Rate limit exceeded"):
            await http_client._make_request("GET", "/test")

    @pytest.mark.asyncio
    async def test_make_request_connection_error(self, http_client):
        """Test handling of connection errors."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.request.side_effect = httpx.ConnectError("Connection failed")
        http_client._client = mock_client

        with pytest.raises(ProjectXConnectionError, match="Connection failed"):
            await http_client._make_request("GET", "/test")

    @pytest.mark.asyncio
    async def test_make_request_timeout_error(self, http_client):
        """Test handling of timeout errors."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.request.side_effect = httpx.TimeoutException("Request timed out")
        http_client._client = mock_client

        with pytest.raises(ProjectXConnectionError, match="Request timed out"):
            await http_client._make_request("GET", "/test")

    @pytest.mark.asyncio
    async def test_make_request_401_refresh_auth(self, http_client):
        """Test that 401 triggers authentication refresh."""
        http_client.session_token = "expired_token"

        # First response: 401 error
        mock_response_401 = Mock()
        mock_response_401.status_code = 401

        # Second response after refresh: success
        mock_response_success = Mock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {"data": "refreshed"}

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.request.side_effect = [mock_response_401, mock_response_success]
        http_client._client = mock_client

        result = await http_client._make_request("GET", "/test")

        assert result == {"data": "refreshed"}
        http_client._refresh_authentication.assert_called_once()
        assert mock_client.request.call_count == 2

    @pytest.mark.asyncio
    async def test_make_request_401_on_login_endpoint(self, http_client):
        """Test that 401 on login endpoint raises error without refresh."""
        mock_response = Mock()
        mock_response.status_code = 401

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.request.return_value = mock_response
        http_client._client = mock_client

        with pytest.raises(ProjectXAuthenticationError, match="Authentication failed"):
            await http_client._make_request("POST", "/Auth/loginKey")

        http_client._refresh_authentication.assert_not_called()

    @pytest.mark.asyncio
    async def test_make_request_404_error(self, http_client):
        """Test handling of 404 errors."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.json.side_effect = Exception("Not JSON")
        mock_response.text = "Not found"

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.request.return_value = mock_response
        http_client._client = mock_client

        with pytest.raises(ProjectXDataError, match="Resource not found"):
            await http_client._make_request("GET", "/test")

    @pytest.mark.asyncio
    async def test_make_request_400_error_with_message(self, http_client):
        """Test handling of 400 errors with error message."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"message": "Invalid request parameters"}

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.request.return_value = mock_response
        http_client._client = mock_client

        with pytest.raises(ProjectXError, match="Invalid request parameters"):
            await http_client._make_request("POST", "/test")

    @pytest.mark.asyncio
    async def test_make_request_400_error_with_error_field(self, http_client):
        """Test handling of 400 errors with error field."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"error": "Bad request"}

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.request.return_value = mock_response
        http_client._client = mock_client

        with pytest.raises(ProjectXError, match="Bad request"):
            await http_client._make_request("POST", "/test")

    @pytest.mark.asyncio
    async def test_make_request_500_error(self, http_client):
        """Test handling of server errors."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal server error occurred"

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.request.return_value = mock_response
        http_client._client = mock_client

        with pytest.raises(ProjectXServerError, match="Server error"):
            await http_client._make_request("GET", "/test")

    @pytest.mark.asyncio
    async def test_make_request_204_no_content(self, http_client):
        """Test handling of 204 No Content response."""
        mock_response = Mock()
        mock_response.status_code = 204

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.request.return_value = mock_response
        http_client._client = mock_client

        result = await http_client._make_request("DELETE", "/test")

        assert result == {}

    @pytest.mark.asyncio
    async def test_make_request_json_parse_error(self, http_client):
        """Test handling of JSON parsing errors."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.request.return_value = mock_response
        http_client._client = mock_client

        with pytest.raises(ProjectXDataError, match="Failed to parse"):
            await http_client._make_request("GET", "/test")

    @pytest.mark.asyncio
    async def test_get_health_status(self, http_client):
        """Test health status reporting."""
        http_client.api_call_count = 10
        http_client.cache_hit_count = 5
        http_client._client = Mock(spec=httpx.AsyncClient)
        http_client._client.is_closed = False

        status = await http_client.get_health_status()

        assert status["api_calls"] == 10
        assert status["cache_hits"] == 5
        assert status["cache_misses"] == 10
        assert status["total_requests"] == 15
        assert status["cache_hit_ratio"] == 5 / 15
        assert status["active_connections"] == 1

    @pytest.mark.asyncio
    async def test_get_health_status_no_requests(self, http_client):
        """Test health status with no requests."""
        status = await http_client.get_health_status()

        assert status["api_calls"] == 0
        assert status["cache_hits"] == 0
        assert status["cache_misses"] == 0
        assert status["total_requests"] == 0
        assert status["cache_hit_ratio"] == 0
        assert status["active_connections"] == 0

    @pytest.mark.asyncio
    async def test_get_health_status_closed_client(self, http_client):
        """Test health status with closed client."""
        http_client._client = Mock(spec=httpx.AsyncClient)
        http_client._client.is_closed = True

        status = await http_client.get_health_status()

        assert status["active_connections"] == 0
