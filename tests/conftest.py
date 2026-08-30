"""Test configuration and fixtures for ProjectX Python SDK."""

import asyncio
import json
import os
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytz

from project_x_py.models import Instrument, ProjectXConfig
from project_x_py.utils.async_rate_limiter import RateLimiter


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Treat unmarked tests as unit tests so the quality-gate marker works."""
    classified = {"unit", "integration", "slow", "realtime", "performance"}
    for item in items:
        if not classified.intersection(item.keywords):
            item.add_marker(pytest.mark.unit)


@pytest.fixture
def mock_response():
    """Create a configurable mock response for API testing."""

    def _create_response(status_code=200, json_data=None, success=True):
        mock_resp = MagicMock()
        mock_resp.status_code = status_code

        if json_data is None:
            json_data = {"success": success}

        mock_resp.json.return_value = json_data
        mock_resp.text = json.dumps(json_data)

        # Add headers dict that supports get method
        headers = {"Content-Type": "application/json"}
        mock_resp.headers = MagicMock()
        mock_resp.headers.__getitem__ = lambda _, key: headers.get(key)
        mock_resp.headers.get = lambda key, default=None: headers.get(key, default)

        return mock_resp

    return _create_response


@pytest.fixture
def test_config():
    """Create a test configuration."""
    return ProjectXConfig(
        api_url="https://test.projectx.com/api",
        timeout_seconds=30,
        retry_attempts=2,
        timezone="UTC",
    )


@pytest.fixture
def auth_env_vars():
    """Set up authentication environment variables for testing."""
    env_vars = {
        "PROJECT_X_USERNAME": "testuser",
        "PROJECT_X_API_KEY": "test-api-key-1234567890",  # pragma: allowlist secret
        "PROJECT_X_ACCOUNT_NAME": "Test Account",
    }
    with patch.dict(os.environ, env_vars):
        yield env_vars


@pytest.fixture
def mock_auth_response(mock_response):
    """Create a mock authentication response."""
    token_payload = {
        "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwiZXhwIjo5OTk5OTk5OTk5LCJuYW1lIjoiSm9obiBEb2UiLCJpYXQiOjE1MTYyMzkwMjJ9.4Adcj3NFYzYLhBtYcAv7m8_GSDgYQvxDN3mPIFc47Hg"
    }
    accounts_payload = {
        "success": True,
        "accounts": [
            {
                "id": 12345,
                "name": "Test Account",
                "balance": 100000.0,
                "canTrade": True,
                "isVisible": True,
                "simulated": True,
            }
        ],
    }
    return mock_response(json_data=token_payload), mock_response(
        json_data=accounts_payload
    )


@pytest.fixture
def mock_instrument():
    """Create a mock instrument object."""
    # Using **kwargs to avoid missing arguments error
    kwargs = {
        "id": "123",
        "name": "Micro Gold Futures",
        "description": "Micro Gold Futures Contract",
        "tickSize": 0.1,
        "tickValue": 1.0,
        "activeContract": True,
    }
    return Instrument(**kwargs)


@pytest.fixture
def mock_instrument_response(mock_response, mock_instrument):
    """Create a mock instrument search response."""
    return mock_response(
        json_data={
            "success": True,
            "contracts": [
                {
                    "id": mock_instrument.id,
                    "name": mock_instrument.name,
                    "description": mock_instrument.description,
                    "tickSize": mock_instrument.tickSize,
                    "tickValue": mock_instrument.tickValue,
                    "activeContract": mock_instrument.activeContract,
                }
            ],
        }
    )


@pytest.fixture
def mock_bars_data():
    """Create mock bars data for testing."""
    now = datetime.now(pytz.UTC)
    data = []
    for i in range(100):
        timestamp = now - timedelta(minutes=i * 5)
        data.append(
            {
                "t": timestamp.isoformat(),
                "o": 1900.0 + i * 0.1,
                "h": 1905.0 + i * 0.1,
                "l": 1895.0 + i * 0.1,
                "c": 1902.0 + i * 0.1,
                "v": 100 + i,
            }
        )
    return data


@pytest.fixture
def mock_bars_response(mock_response, mock_bars_data):
    """Create a mock bars response."""
    return mock_response(json_data={"success": True, "bars": mock_bars_data})


@pytest.fixture
def mock_positions_data():
    """Create mock positions data for testing."""
    return [
        {
            "id": "pos1",
            "accountId": 12345,
            "contractId": "MGC",
            "creationTimestamp": datetime.now(pytz.UTC).isoformat(),
            "size": 1,
            "averagePrice": 1900.0,
            "type": 1,  # Long position (1=Long, 2=Short)
        },
        {
            "id": "pos2",
            "accountId": 12345,
            "contractId": "MNQ",
            "creationTimestamp": datetime.now(pytz.UTC).isoformat(),
            "size": 2,
            "averagePrice": 15000.0,
            "type": 2,  # Short position
        },
    ]


@pytest.fixture
def mock_positions_response(mock_response, mock_positions_data):
    """Create a mock positions response."""
    return mock_response(json_data=mock_positions_data)


@pytest.fixture
def mock_trades_data():
    """Create mock trades data for testing."""
    now = datetime.now(pytz.UTC)
    return [
        {
            "id": "trade1",
            "accountId": 12345,
            "contractId": "MGC",
            "creationTimestamp": (now - timedelta(hours=1)).isoformat(),
            "size": 1,
            "price": 1900.0,
            "profitAndLoss": None,  # Half-turn trade
            "fees": 2.50,
            "side": 0,  # Buy
            "voided": False,
            "orderId": 12345,
        },
        {
            "id": "trade2",
            "accountId": 12345,
            "contractId": "MNQ",
            "creationTimestamp": now.isoformat(),
            "size": 2,
            "price": 15000.0,
            "profitAndLoss": 150.0,
            "fees": 3.60,
            "side": 1,  # Sell
            "voided": False,
            "orderId": 67890,
        },
    ]


@pytest.fixture
def mock_trades_response(mock_response, mock_trades_data):
    """Create a mock trades response."""
    return mock_response(json_data={"success": True, "trades": mock_trades_data})


@pytest.fixture
def mock_httpx_client():
    """Create a mock httpx client."""
    mock_client = AsyncMock()
    mock_client.request = AsyncMock()
    mock_client.aclose = AsyncMock()
    mock_client.is_closed = False  # Add is_closed attribute
    return mock_client


@pytest.fixture
async def initialized_client(mock_httpx_client, test_config):
    """Create a properly initialized ProjectX client for testing.

    This fixture ensures all necessary attributes from mixins are properly initialized.
    """
    from project_x_py import ProjectX

    with patch("httpx.AsyncClient", return_value=mock_httpx_client):
        async with ProjectX("testuser", "test-api-key", config=test_config) as client:
            # Initialize attributes from CacheMixin
            client._instrument_cache = {}
            client._instrument_cache_time = {}
            client._market_data_cache = {}
            client._market_data_cache_time = {}
            client.cache_ttl = 300
            client.last_cache_cleanup = time.time()
            client.cache_hit_count = 0

            # Initialize attributes from AuthenticationMixin
            client.session_token = ""
            client.token_expiry = None
            client._authenticated = False

            # Initialize attributes from HttpMixin
            client._client = mock_httpx_client
            client.api_call_count = 0

            # Initialize RateLimiter
            client.rate_limiter = RateLimiter(max_requests=100, window_seconds=60)

            # Additional initialization as needed
            yield client


@pytest.fixture
def event_loop():
    """Create an event loop for testing."""
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()
