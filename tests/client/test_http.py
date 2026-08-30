"""Tests for the HTTP client functionality of ProjectX client."""

from unittest.mock import patch

import httpx
import pytest

from project_x_py import ProjectX
from project_x_py.exceptions import (
    OrderSubmissionUncertainError,
    ProjectXAuthenticationError,
    ProjectXConnectionError,
    ProjectXDataError,
    ProjectXError,
    ProjectXRateLimitError,
    ProjectXServerError,
)


class TestHttpClient:
    """Tests for HTTP client functionality."""

    @pytest.mark.asyncio
    async def test_client_creation(self, mock_httpx_client):
        """Test HTTP client creation."""
        with patch("httpx.AsyncClient", return_value=mock_httpx_client):
            async with ProjectX("testuser", "test-api-key") as client:
                assert client._client is not None
                assert client._client == mock_httpx_client

    @pytest.mark.asyncio
    async def test_successful_request(self, initialized_client, mock_response):
        """Test successful API request."""
        client = initialized_client
        expected_data = {"success": True, "data": "test_value"}
        client._client.request.return_value = mock_response(json_data=expected_data)

        result = await client._make_request("GET", "/test/endpoint")

        assert result == expected_data
        client._client.request.assert_called_once()
        call_args = client._client.request.call_args[1]
        assert call_args["method"] == "GET"
        assert call_args["url"] == f"{client.base_url}/test/endpoint"

    @pytest.mark.asyncio
    async def test_auth_error_handling(self, initialized_client, mock_response):
        """Test authentication error handling."""
        client = initialized_client
        error_response = mock_response(
            status_code=401,
            json_data={"success": False, "message": "Authentication failed"},
        )
        client._client.request.return_value = error_response

        with pytest.raises(ProjectXAuthenticationError):
            await client._make_request("GET", "/test/endpoint")

    @pytest.mark.asyncio
    async def test_not_found_error_handling(self, initialized_client, mock_response):
        """Test not found error handling."""
        client = initialized_client
        error_response = mock_response(
            status_code=404,
            json_data={"success": False, "message": "Resource not found"},
        )
        client._client.request.return_value = error_response

        with pytest.raises(ProjectXDataError):
            await client._make_request("GET", "/test/endpoint")

    @pytest.mark.asyncio
    async def test_rate_limit_error_handling(self, initialized_client, mock_response):
        """Test rate limit error handling."""
        client = initialized_client
        error_response = mock_response(
            status_code=429,
            json_data={"success": False, "message": "Too many requests"},
        )
        error_response.headers.__getitem__ = (
            lambda _, key: "60" if key == "Retry-After" else None
        )

        # Set retry_attempts to 0 to avoid actual retries
        client.config.retry_attempts = 0
        client._client.request.return_value = error_response

        with pytest.raises(ProjectXRateLimitError) as exc_info:
            await client._make_request("GET", "/test/endpoint")

        assert "Rate limit" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_server_error_handling(self, initialized_client, mock_response):
        """Test server error handling."""
        client = initialized_client
        error_response = mock_response(
            status_code=500,
            json_data={"success": False, "message": "Internal server error"},
        )
        client._client.request.return_value = error_response

        with pytest.raises(ProjectXServerError):
            await client._make_request("GET", "/test/endpoint")

    @pytest.mark.asyncio
    async def test_client_error_handling(self, initialized_client, mock_response):
        """Test client error handling."""
        client = initialized_client
        error_response = mock_response(
            status_code=400, json_data={"success": False, "message": "Bad request"}
        )
        client._client.request.return_value = error_response

        with pytest.raises(ProjectXError):
            await client._make_request("GET", "/test/endpoint")

    @pytest.mark.asyncio
    async def test_retry_logic(self, initialized_client, mock_response):
        """Test retry logic for transient errors."""
        client = initialized_client

        # Mock a server error (retry-able) followed by a success response
        error_response = mock_response(status_code=503, json_data={"success": False})
        success_response = mock_response(
            json_data={"success": True, "data": "test_value"}
        )

        client._client.request.side_effect = [error_response, success_response]

        # Reduce max retries for testing
        client.config.retry_attempts = 3

        result = await client._make_request("GET", "/test/endpoint")

        assert result == {"success": True, "data": "test_value"}
        assert client._client.request.call_count == 2  # Initial request + 1 retry

    @pytest.mark.asyncio
    async def test_max_retry_exceeded(self, initialized_client, mock_response):
        """Test max retry exceeded raises error."""
        client = initialized_client

        # Mock server errors that exceed max retries
        error_response = mock_response(status_code=503, json_data={"success": False})

        # Side effect with multiple error responses
        client._client.request.side_effect = [error_response] * 4

        # Reduce max retries for testing
        client.config.retry_attempts = 3

        with pytest.raises(ProjectXServerError):
            await client._make_request("GET", "/test/endpoint")

        assert (
            client._client.request.call_count == 3
        )  # Total attempts (decorator max_attempts=3)

    @pytest.mark.asyncio
    async def test_connection_error_handling(self, initialized_client):
        """Test connection error handling."""
        client = initialized_client

        # Set retry_attempts to 0 to avoid retries
        client.config.retry_attempts = 0

        # Mock a connection error
        client._client.request.side_effect = httpx.ConnectError("Failed to connect")

        with pytest.raises(ProjectXConnectionError) as exc_info:
            await client._make_request("GET", "/test/endpoint")

        assert "Failed to connect" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_timeout_error_handling(self, initialized_client):
        """Test timeout error handling."""
        client = initialized_client

        # Set retry_attempts to 0 to avoid retries
        client.config.retry_attempts = 0

        # Mock a timeout error
        client._client.request.side_effect = httpx.TimeoutException("Request timed out")

        with pytest.raises(ProjectXConnectionError) as exc_info:
            await client._make_request("GET", "/test/endpoint")

        assert "timed out" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_request_with_params(self, initialized_client, mock_response):
        """Test request with query parameters."""
        client = initialized_client

        client._client.request.return_value = mock_response(json_data={"success": True})
        test_params = {"param1": "value1", "param2": 123}

        await client._make_request("GET", "/test/endpoint", params=test_params)

        call_args = client._client.request.call_args[1]
        assert call_args["params"] == test_params

    @pytest.mark.asyncio
    async def test_request_with_data(self, initialized_client, mock_response):
        """Test request with JSON data."""
        client = initialized_client

        client._client.request.return_value = mock_response(json_data={"success": True})
        test_data = {"field1": "value1", "field2": 123}

        await client._make_request("POST", "/test/endpoint", data=test_data)

        call_args = client._client.request.call_args[1]
        assert call_args["json"] == test_data

    @pytest.mark.asyncio
    async def test_health_status(self, initialized_client):
        """Test health status endpoint."""
        client = initialized_client

        # Set some values to test
        client.api_call_count = 10
        client.cache_hit_count = 5
        client._authenticated = True
        client.account_info = type("obj", (object,), {"name": "TestAccount"})()

        health = await client.get_health_status()

        # Verify the structure matches the expected format (flat dictionary)
        assert "api_calls" in health
        assert "cache_hits" in health
        assert "cache_hit_ratio" in health
        assert "total_requests" in health
        assert "active_connections" in health

        # Verify specific values
        assert health["api_calls"] == 10
        assert health["cache_hits"] == 5
        assert health["cache_hit_ratio"] == 5 / 15  # 5/(5+10)
        assert health["total_requests"] == 15
        assert health["active_connections"] == 1  # authenticated

    @pytest.mark.asyncio
    async def test_cancelled_mutating_request_is_uncertain(self, initialized_client):
        """Cancellation of an in-flight place must not look like a clean failure."""
        import asyncio

        client = initialized_client

        async def _cancelled(*_args, **_kwargs):
            raise asyncio.CancelledError()

        client._client.request.side_effect = _cancelled

        with pytest.raises(OrderSubmissionUncertainError):
            await client._make_request("POST", "/Order/place", data={"size": 1})
        assert client._client.request.call_count == 1

    @pytest.mark.asyncio
    async def test_cancelled_get_is_reraised(self, initialized_client):
        """Cancellation of a safe GET still surfaces as CancelledError."""
        import asyncio

        client = initialized_client

        async def _cancelled(*_args, **_kwargs):
            raise asyncio.CancelledError()

        client._client.request.side_effect = _cancelled

        with pytest.raises(asyncio.CancelledError):
            await client._make_request("GET", "/test/endpoint")

    @pytest.mark.asyncio
    async def test_mutating_place_does_not_retry_on_server_error(
        self, initialized_client, mock_response
    ):
        """POST /Order/place must not be retried after a 5xx; treat as uncertain."""
        client = initialized_client
        error_response = mock_response(status_code=503, json_data={"success": False})
        client._client.request.side_effect = [
            error_response,
            error_response,
            error_response,
        ]

        with pytest.raises(OrderSubmissionUncertainError):
            await client._make_request("POST", "/Order/place", data={"size": 1})

        assert client._client.request.call_count == 1

    @pytest.mark.asyncio
    async def test_mutating_place_timeout_is_uncertain(self, initialized_client):
        """A timeout after sending /Order/place is uncertain, not a retryable miss."""
        client = initialized_client
        client._client.request.side_effect = httpx.TimeoutException("timed out")

        with pytest.raises(OrderSubmissionUncertainError):
            await client._make_request("POST", "/Order/place", data={"size": 1})

        assert client._client.request.call_count == 1

    @pytest.mark.asyncio
    async def test_mutating_cancel_connect_error_is_uncertain(self, initialized_client):
        """POST /Order/cancel connection errors must not be retried."""
        client = initialized_client
        client._client.request.side_effect = httpx.ConnectError("Failed to connect")

        with pytest.raises(OrderSubmissionUncertainError):
            await client._make_request("POST", "/Order/cancel", data={"orderId": 1})

        assert client._client.request.call_count == 1
