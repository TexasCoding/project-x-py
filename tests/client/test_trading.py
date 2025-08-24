"""Tests for the trading functionality of ProjectX client."""

import datetime
from unittest.mock import patch

import pytest
import pytz

from project_x_py import ProjectX
from project_x_py.exceptions import ProjectXError
from project_x_py.utils.async_rate_limiter import RateLimiter


class TestTrading:
    """Tests for the trading functionality of the ProjectX client."""

    @pytest.mark.asyncio
    async def test_search_open_positions(
        self, mock_httpx_client, mock_auth_response, mock_positions_response
    ):
        """Test getting positions."""
        auth_response, accounts_response = mock_auth_response
        mock_httpx_client.request.side_effect = [
            auth_response,  # Initial auth
            accounts_response,  # Initial accounts
            mock_positions_response,  # Positions data
        ]

        with patch("httpx.AsyncClient", return_value=mock_httpx_client):
            async with ProjectX("testuser", "test-api-key") as client:
                # Initialize required attributes
                client.api_call_count = 0
                client.rate_limiter = RateLimiter(max_requests=100, window_seconds=60)
                await client.authenticate()

                positions = await client.search_open_positions()

                assert len(positions) == 2
                assert positions[0].contractId == "MGC"
                assert positions[0].size == 1
                assert positions[1].contractId == "MNQ"
                assert positions[1].size == 2  # Short position has positive size

    @pytest.mark.asyncio
    async def test_search_open_positions_empty(
        self, mock_httpx_client, mock_auth_response, mock_response
    ):
        """Test getting positions with empty response."""
        auth_response, accounts_response = mock_auth_response
        empty_response = mock_response(json_data=[])

        mock_httpx_client.request.side_effect = [
            auth_response,  # Initial auth
            accounts_response,  # Initial accounts
            empty_response,  # Empty positions
        ]

        with patch("httpx.AsyncClient", return_value=mock_httpx_client):
            async with ProjectX("testuser", "test-api-key") as client:
                # Initialize required attributes
                client.api_call_count = 0
                client.rate_limiter = RateLimiter(max_requests=100, window_seconds=60)
                await client.authenticate()

                positions = await client.search_open_positions()

                assert len(positions) == 0

    @pytest.mark.asyncio
    async def test_search_open_positions_no_account(self, mock_httpx_client):
        """Test error when getting positions without account."""
        with patch("httpx.AsyncClient", return_value=mock_httpx_client):
            async with ProjectX("testuser", "test-api-key") as client:
                # Initialize required attributes
                client.api_call_count = 0
                client.rate_limiter = RateLimiter(max_requests=100, window_seconds=60)
                # No authentication, no account info
                with pytest.raises(ProjectXError):
                    await client.search_open_positions()

    @pytest.mark.asyncio
    async def test_search_open_positions_basic(
        self, mock_httpx_client, mock_auth_response, mock_response
    ):
        """Test searching open positions with basic functionality."""
        auth_response, accounts_response = mock_auth_response
        positions_response = mock_response(
            json_data={
                "success": True,
                "positions": [
                    {
                        "id": "pos1",
                        "accountId": 12345,
                        "contractId": "MGC",
                        "creationTimestamp": datetime.datetime.now(
                            pytz.UTC
                        ).isoformat(),
                        "size": 1,
                        "averagePrice": 1900.0,
                        "type": 1,  # Long position
                    }
                ],
            }
        )

        mock_httpx_client.request.side_effect = [
            auth_response,  # Initial auth
            accounts_response,  # Initial accounts
            positions_response,  # Positions data
        ]

        with patch("httpx.AsyncClient", return_value=mock_httpx_client):
            async with ProjectX("testuser", "test-api-key") as client:
                # Initialize required attributes
                client.api_call_count = 0
                client.rate_limiter = RateLimiter(max_requests=100, window_seconds=60)
                await client.authenticate()

                positions = await client.search_open_positions()

                assert len(positions) == 1
                assert positions[0].contractId == "MGC"
                assert positions[0].size == 1
                assert positions[0].type == 1  # Long position

    @pytest.mark.asyncio
    async def test_search_open_positions_with_account_id(
        self, mock_httpx_client, mock_auth_response, mock_response
    ):
        """Test searching open positions with specific account ID."""
        auth_response, accounts_response = mock_auth_response
        positions_response = mock_response(
            json_data={
                "success": True,
                "positions": [
                    {
                        "id": "pos1",
                        "accountId": 67890,
                        "contractId": "MNQ",
                        "creationTimestamp": datetime.datetime.now(
                            pytz.UTC
                        ).isoformat(),
                        "size": 3,
                        "averagePrice": 15000.0,
                        "type": 1,
                    }
                ],
            }
        )

        mock_httpx_client.request.side_effect = [
            auth_response,  # Initial auth
            accounts_response,  # Initial accounts
            positions_response,  # Positions data
        ]

        with patch("httpx.AsyncClient", return_value=mock_httpx_client):
            async with ProjectX("testuser", "test-api-key") as client:
                # Initialize required attributes
                client.api_call_count = 0
                client.rate_limiter = RateLimiter(max_requests=100, window_seconds=60)
                await client.authenticate()

                # Search with specific account ID
                positions = await client.search_open_positions(account_id=67890)

                assert len(positions) == 1
                assert positions[0].accountId == 67890
                assert positions[0].contractId == "MNQ"

                # Check that request was made with correct account ID
                last_call = mock_httpx_client.request.call_args_list[-1]
                assert last_call[1]["json"]["accountId"] == 67890

    @pytest.mark.asyncio
    async def test_search_open_positions_no_account_error(self, mock_httpx_client):
        """Test error when searching positions without account."""
        with patch("httpx.AsyncClient", return_value=mock_httpx_client):
            async with ProjectX("testuser", "test-api-key") as client:
                # Initialize required attributes
                client.api_call_count = 0
                client.rate_limiter = RateLimiter(max_requests=100, window_seconds=60)
                # No authentication, no account info
                with pytest.raises(ProjectXError):
                    await client.search_open_positions()

    @pytest.mark.asyncio
    async def test_search_open_positions_empty_response(
        self, mock_httpx_client, mock_auth_response, mock_response
    ):
        """Test searching open positions with empty response."""
        auth_response, accounts_response = mock_auth_response
        empty_response = mock_response(json_data={"success": True, "positions": []})

        mock_httpx_client.request.side_effect = [
            auth_response,  # Initial auth
            accounts_response,  # Initial accounts
            empty_response,  # Empty positions
        ]

        with patch("httpx.AsyncClient", return_value=mock_httpx_client):
            async with ProjectX("testuser", "test-api-key") as client:
                # Initialize required attributes
                client.api_call_count = 0
                client.rate_limiter = RateLimiter(max_requests=100, window_seconds=60)
                await client.authenticate()

                positions = await client.search_open_positions()

                assert len(positions) == 0

    @pytest.mark.asyncio
    async def test_search_trades(
        self, mock_httpx_client, mock_auth_response, mock_trades_response
    ):
        """Test searching trade history."""
        auth_response, accounts_response = mock_auth_response
        mock_httpx_client.request.side_effect = [
            auth_response,  # Initial auth
            accounts_response,  # Initial accounts
            mock_trades_response,  # Trades data
        ]

        with patch("httpx.AsyncClient", return_value=mock_httpx_client):
            async with ProjectX("testuser", "test-api-key") as client:
                # Initialize required attributes
                client.api_call_count = 0
                client.rate_limiter = RateLimiter(max_requests=100, window_seconds=60)
                await client.authenticate()

                # Default parameters
                trades = await client.search_trades()

                assert len(trades) == 2
                assert trades[0].contractId == "MGC"
                assert trades[0].size == 1
                assert trades[0].price == 1900.0
                assert trades[1].contractId == "MNQ"
                assert trades[1].size == 2  # Trade size is positive
                assert trades[1].price == 15000.0

    @pytest.mark.asyncio
    async def test_search_trades_with_filters(
        self, mock_httpx_client, mock_auth_response, mock_trades_response
    ):
        """Test searching trade history with filters."""
        auth_response, accounts_response = mock_auth_response
        mock_httpx_client.request.side_effect = [
            auth_response,  # Initial auth
            accounts_response,  # Initial accounts
            mock_trades_response,  # Trades data
        ]

        with patch("httpx.AsyncClient", return_value=mock_httpx_client):
            async with ProjectX("testuser", "test-api-key") as client:
                # Initialize required attributes
                client.api_call_count = 0
                client.rate_limiter = RateLimiter(max_requests=100, window_seconds=60)
                await client.authenticate()

                # With filters
                start_date = datetime.datetime.now(pytz.UTC) - datetime.timedelta(
                    days=7
                )
                end_date = datetime.datetime.now(pytz.UTC)

                trades = await client.search_trades(
                    start_date=start_date,
                    end_date=end_date,
                    contract_id="MGC",
                    limit=50,
                )

                assert len(trades) == 2

                # Check request parameters
                last_call = mock_httpx_client.request.call_args_list[-1]
                params = last_call[1]["params"]

                assert params["accountId"] == 12345
                assert params["startDate"] == start_date.isoformat()
                assert params["endDate"] == end_date.isoformat()
                assert params["limit"] == 50
                assert params["contractId"] == "MGC"

    @pytest.mark.asyncio
    async def test_search_trades_empty(
        self, mock_httpx_client, mock_auth_response, mock_response
    ):
        """Test searching trades with empty response."""
        auth_response, accounts_response = mock_auth_response
        empty_response = mock_response(json_data=[])

        mock_httpx_client.request.side_effect = [
            auth_response,  # Initial auth
            accounts_response,  # Initial accounts
            empty_response,  # Empty trades
        ]

        with patch("httpx.AsyncClient", return_value=mock_httpx_client):
            async with ProjectX("testuser", "test-api-key") as client:
                # Initialize required attributes
                client.api_call_count = 0
                client.rate_limiter = RateLimiter(max_requests=100, window_seconds=60)
                await client.authenticate()

                trades = await client.search_trades()

                assert len(trades) == 0

    @pytest.mark.asyncio
    async def test_search_trades_no_account(self, mock_httpx_client):
        """Test error when searching trades without account."""
        with patch("httpx.AsyncClient", return_value=mock_httpx_client):
            async with ProjectX("testuser", "test-api-key") as client:
                # Initialize required attributes
                client.api_call_count = 0
                client.rate_limiter = RateLimiter(max_requests=100, window_seconds=60)
                # No authentication, no account info
                with pytest.raises(ProjectXError):
                    await client.search_trades()

    @pytest.mark.asyncio
    async def test_search_trades_date_defaults(
        self, mock_httpx_client, mock_auth_response, mock_response
    ):
        """Test default date handling in trade search."""
        auth_response, accounts_response = mock_auth_response
        trades_response = mock_response(json_data=[])

        mock_httpx_client.request.side_effect = [
            auth_response,  # Initial auth
            accounts_response,  # Initial accounts
            trades_response,  # Empty trades
        ]

        with patch("httpx.AsyncClient", return_value=mock_httpx_client):
            async with ProjectX("testuser", "test-api-key") as client:
                # Initialize required attributes
                client.api_call_count = 0
                client.rate_limiter = RateLimiter(max_requests=100, window_seconds=60)
                await client.authenticate()

                # Call without date parameters
                await client.search_trades()

                # Check default date parameters
                last_call = mock_httpx_client.request.call_args_list[-1]
                params = last_call[1]["params"]

                # Should have start date 30 days ago
                start_date = datetime.datetime.fromisoformat(
                    params["startDate"].replace("Z", "+00:00")
                )
                end_date = datetime.datetime.fromisoformat(
                    params["endDate"].replace("Z", "+00:00")
                )

                date_diff = end_date - start_date
                assert 29 <= date_diff.days <= 31  # Approximately 30 days
