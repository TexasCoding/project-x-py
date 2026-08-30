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
    async def test_get_positions(
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

                positions = await client.get_positions()

                assert len(positions) == 2
                assert positions[0].contractId == "MGC"
                assert positions[0].size == 1
                assert positions[1].contractId == "MNQ"
                assert positions[1].size == 2  # Short position has positive size

    @pytest.mark.asyncio
    async def test_get_positions_empty(
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

                positions = await client.get_positions()

                assert len(positions) == 0

    @pytest.mark.asyncio
    async def test_get_positions_no_account(self, mock_httpx_client):
        """Test error when getting positions without account."""
        with patch("httpx.AsyncClient", return_value=mock_httpx_client):
            async with ProjectX("testuser", "test-api-key") as client:
                # Initialize required attributes
                client.api_call_count = 0
                client.rate_limiter = RateLimiter(max_requests=100, window_seconds=60)
                # No authentication, no account info
                with pytest.raises(ProjectXError):
                    await client.get_positions()

    @pytest.mark.asyncio
    async def test_search_open_positions(
        self, mock_httpx_client, mock_auth_response, mock_response
    ):
        """Test searching open positions."""
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
    async def test_search_open_positions_no_account(self, mock_httpx_client):
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
    async def test_search_open_positions_empty(
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
                data = last_call[1]["json"]

                assert last_call[1]["method"] == "POST"
                assert last_call[1]["url"].endswith("/Trade/search")
                assert data["accountId"] == 12345
                assert data["startTimestamp"] == start_date.isoformat()
                assert data["endTimestamp"] == end_date.isoformat()
                assert data["contractId"] == "MGC"

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
                data = last_call[1]["json"]

                # Should have start date 30 days ago
                start_date = datetime.datetime.fromisoformat(
                    data["startTimestamp"].replace("Z", "+00:00")
                )
                end_date = datetime.datetime.fromisoformat(
                    data["endTimestamp"].replace("Z", "+00:00")
                )

                date_diff = end_date - start_date
                assert 29 <= date_diff.days <= 31  # Approximately 30 days

    @pytest.mark.asyncio
    async def test_search_trades_preserves_null_profit_and_loss(
        self, initialized_client, mock_trades_data
    ):
        """Gateway profitAndLoss: null stays None on Trade, not 0.0."""
        from unittest.mock import AsyncMock

        initialized_client._ensure_authenticated = AsyncMock(return_value=None)
        initialized_client.account_info = type(
            "Account", (), {"id": 12345, "name": "Test"}
        )()
        initialized_client._make_request = AsyncMock(
            return_value={"success": True, "trades": mock_trades_data}
        )

        trades = await initialized_client.search_trades()

        assert len(trades) == 2
        assert trades[0].profitAndLoss is None
        assert trades[0].profitAndLoss != 0.0
        assert trades[1].profitAndLoss == 150.0

    @pytest.mark.asyncio
    async def test_search_trades_failed_gateway_raises(self, initialized_client):
        """success: false from /Trade/search raises, it does not return []."""
        from unittest.mock import AsyncMock

        initialized_client._ensure_authenticated = AsyncMock(return_value=None)
        initialized_client.account_info = type(
            "Account", (), {"id": 12345, "name": "Test"}
        )()
        initialized_client._make_request = AsyncMock(
            return_value={"success": False, "errorMessage": "Trade search failed"}
        )

        with pytest.raises(ProjectXError, match="Trade search failed"):
            await initialized_client.search_trades()

    @pytest.mark.asyncio
    async def test_search_trades_limit_is_applied_locally(self, initialized_client):
        """limit truncates after fetch; Gateway payload must not include limit."""
        from unittest.mock import AsyncMock

        initialized_client._ensure_authenticated = AsyncMock(return_value=None)
        initialized_client.account_info = type(
            "Account", (), {"id": 12345, "name": "Test"}
        )()
        rows = [
            {
                "id": i,
                "accountId": 12345,
                "contractId": "MGC",
                "creationTimestamp": datetime.datetime.now(pytz.UTC).isoformat(),
                "size": 1,
                "price": 1900.0 + i,
                "profitAndLoss": None,
                "fees": 2.5,
                "side": 0,
                "voided": False,
                "orderId": 100 + i,
            }
            for i in range(3)
        ]
        initialized_client._make_request = AsyncMock(
            return_value={"success": True, "trades": rows}
        )

        trades = await initialized_client.search_trades(limit=2)

        assert len(trades) == 2
        payload = initialized_client._make_request.call_args.kwargs["data"]
        assert "limit" not in payload

    @pytest.mark.asyncio
    async def test_search_trades_preserves_gateway_commissions_field(
        self, initialized_client
    ):
        """commissions maps onto fees and is kept on Trade."""
        from unittest.mock import AsyncMock

        initialized_client._ensure_authenticated = AsyncMock(return_value=None)
        initialized_client.account_info = type(
            "Account", (), {"id": 12345, "name": "Test"}
        )()
        initialized_client._make_request = AsyncMock(
            return_value={
                "success": True,
                "trades": [
                    {
                        "id": 1,
                        "accountId": 12345,
                        "contractId": "MNQ",
                        "creationTimestamp": datetime.datetime.now(
                            pytz.UTC
                        ).isoformat(),
                        "price": 15000.0,
                        "profitAndLoss": 75.0,
                        "commissions": 2.25,
                        "side": 0,
                        "size": 3,
                        "voided": False,
                        "orderId": 102,
                        "extraField": "ignored",
                    }
                ],
            }
        )

        trades = await initialized_client.search_trades(contract_id="MNQ")

        assert len(trades) == 1
        assert trades[0].fees == pytest.approx(2.25)
        assert trades[0].commissions == pytest.approx(2.25)

    @pytest.mark.asyncio
    async def test_search_open_positions_failed_response(self, initialized_client):
        """success: false from /Position/searchOpen raises ProjectXError."""
        from unittest.mock import AsyncMock

        initialized_client._ensure_authenticated = AsyncMock(return_value=None)
        initialized_client.account_info = type(
            "Account", (), {"id": 12345, "name": "Test"}
        )()
        initialized_client._make_request = AsyncMock(
            return_value={"success": False, "error": "API Error"}
        )

        with pytest.raises(ProjectXError, match="API Error"):
            await initialized_client.search_open_positions()

    @pytest.mark.asyncio
    async def test_search_open_positions_preserves_display_name(
        self, initialized_client
    ):
        """Position search keeps known display fields and ignores unknown ones."""
        from unittest.mock import AsyncMock

        initialized_client._ensure_authenticated = AsyncMock(return_value=None)
        initialized_client.account_info = type(
            "Account", (), {"id": 12345, "name": "Test"}
        )()
        initialized_client._make_request = AsyncMock(
            return_value={
                "success": True,
                "positions": [
                    {
                        "id": "pos1",
                        "accountId": 12345,
                        "contractId": "CON.F.US.MNQ.Z25",
                        "contractDisplayName": "MNQZ25",
                        "unknownGatewayField": "ignored",
                        "creationTimestamp": datetime.datetime.now(
                            pytz.UTC
                        ).isoformat(),
                        "size": 2,
                        "averagePrice": 21342.25,
                        "type": 1,
                    }
                ],
            }
        )

        positions = await initialized_client.search_open_positions()

        assert len(positions) == 1
        assert positions[0].contractId == "CON.F.US.MNQ.Z25"
        assert positions[0].contractDisplayName == "MNQZ25"
        assert not hasattr(positions[0], "unknownGatewayField")

    @pytest.mark.asyncio
    async def test_get_positions_is_alias_for_search_open_positions(
        self, initialized_client
    ):
        """get_positions is an undeprecated alias, not a warning-emitting leftover."""
        import warnings
        from unittest.mock import AsyncMock

        initialized_client._ensure_authenticated = AsyncMock(return_value=None)
        initialized_client.account_info = type(
            "Account", (), {"id": 12345, "name": "Test"}
        )()
        initialized_client._make_request = AsyncMock(
            return_value={"success": True, "positions": []}
        )

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            positions = await initialized_client.get_positions()

        assert positions == []
        assert not any(issubclass(w.category, DeprecationWarning) for w in caught)
        initialized_client._make_request.assert_awaited_once_with(
            "POST", "/Position/searchOpen", data={"accountId": 12345}
        )

    @pytest.mark.asyncio
    async def test_search_open_positions_list_response(self, initialized_client):
        """A raw list from the Gateway is accepted as the new searchOpen format."""
        from unittest.mock import AsyncMock

        initialized_client._ensure_authenticated = AsyncMock(return_value=None)
        initialized_client.account_info = type(
            "Account", (), {"id": 12345, "name": "Test"}
        )()
        initialized_client._make_request = AsyncMock(
            return_value=[
                {
                    "id": "pos1",
                    "accountId": 12345,
                    "contractId": "CL",
                    "creationTimestamp": datetime.datetime.now(pytz.UTC).isoformat(),
                    "size": 5,
                    "averagePrice": 75.50,
                    "type": 1,
                }
            ]
        )

        positions = await initialized_client.search_open_positions()

        assert len(positions) == 1
        assert positions[0].contractId == "CL"

    @pytest.mark.asyncio
    async def test_search_open_positions_none_response(self, initialized_client):
        """None from searchOpen is an empty book, not an error."""
        from unittest.mock import AsyncMock

        initialized_client._ensure_authenticated = AsyncMock(return_value=None)
        initialized_client.account_info = type(
            "Account", (), {"id": 12345, "name": "Test"}
        )()
        initialized_client._make_request = AsyncMock(return_value=None)

        assert await initialized_client.search_open_positions() == []

    @pytest.mark.asyncio
    async def test_search_open_positions_invalid_response_type(
        self, initialized_client
    ):
        """Non list/dict searchOpen payloads return []."""
        from unittest.mock import AsyncMock

        initialized_client._ensure_authenticated = AsyncMock(return_value=None)
        initialized_client.account_info = type(
            "Account", (), {"id": 12345, "name": "Test"}
        )()
        initialized_client._make_request = AsyncMock(return_value="invalid response")

        assert await initialized_client.search_open_positions() == []

    @pytest.mark.asyncio
    async def test_search_trades_none_and_invalid_response(self, initialized_client):
        """None or unexpected types from /Trade/search return []."""
        from unittest.mock import AsyncMock

        initialized_client._ensure_authenticated = AsyncMock(return_value=None)
        initialized_client.account_info = type(
            "Account", (), {"id": 12345, "name": "Test"}
        )()
        initialized_client._make_request = AsyncMock(return_value=None)
        assert await initialized_client.search_trades() == []

        initialized_client._make_request = AsyncMock(return_value="invalid")
        assert await initialized_client.search_trades() == []

    @pytest.mark.asyncio
    async def test_search_trades_custom_account_id(self, initialized_client):
        """Explicit account_id is sent even when account_info is missing."""
        from unittest.mock import AsyncMock

        initialized_client._ensure_authenticated = AsyncMock(return_value=None)
        initialized_client.account_info = None
        initialized_client._make_request = AsyncMock(return_value=[])

        trades = await initialized_client.search_trades(account_id=67890)

        assert trades == []
        payload = initialized_client._make_request.call_args.kwargs["data"]
        assert payload["accountId"] == 67890
        assert "limit" not in payload
