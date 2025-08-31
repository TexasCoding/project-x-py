"""Comprehensive tests for the trading module of ProjectX client."""

import datetime
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
import pytz

from project_x_py.client.trading import TradingMixin
from project_x_py.exceptions import ProjectXError
from project_x_py.models import Account


class MockTradingClient(TradingMixin):
    """Mock client that includes TradingMixin for testing."""

    def __init__(self):
        super().__init__()
        self.base_url = "https://api.test.com"
        self._http_client = AsyncMock()
        self._make_request = AsyncMock()
        self._ensure_authenticated = AsyncMock()
        self.account_info = None


class TestTradingMixin:
    """Test suite for TradingMixin class."""

    @pytest.fixture
    def trading_client(self):
        """Create a mock client with TradingMixin for testing."""
        return MockTradingClient()

    @pytest.mark.asyncio
    async def test_get_positions_deprecated(self, trading_client):
        """Test that get_positions shows deprecation warning."""
        trading_client.account_info = Account(
            id=12345,
            name="Test Account",
            balance=10000.0,
            canTrade=True,
            isVisible=True,
            simulated=False,
        )

        mock_response = {
            "success": True,
            "positions": [
                {
                    "id": "pos1",
                    "accountId": 12345,
                    "contractId": "MNQ",
                    "creationTimestamp": datetime.datetime.now(pytz.UTC).isoformat(),
                    "size": 2,
                    "averagePrice": 15000.0,
                    "type": 1,
                }
            ],
        }
        trading_client._make_request.return_value = mock_response

        with pytest.warns(DeprecationWarning, match="(get_positions|Method renamed)"):
            positions = await trading_client.get_positions()

        assert len(positions) == 1
        assert positions[0].contractId == "MNQ"

    @pytest.mark.asyncio
    async def test_search_open_positions_success(self, trading_client):
        """Test successful position search."""
        trading_client.account_info = Account(
            id=12345,
            name="Test Account",
            balance=10000.0,
            canTrade=True,
            isVisible=True,
            simulated=False,
        )

        mock_response = {
            "success": True,
            "positions": [
                {
                    "id": "pos1",
                    "accountId": 12345,
                    "contractId": "ES",
                    "creationTimestamp": datetime.datetime.now(pytz.UTC).isoformat(),
                    "size": 1,
                    "averagePrice": 4500.0,
                    "type": 1,
                },
                {
                    "id": "pos2",
                    "accountId": 12345,
                    "contractId": "NQ",
                    "creationTimestamp": datetime.datetime.now(pytz.UTC).isoformat(),
                    "size": 2,
                    "averagePrice": 15000.0,
                    "type": 2,  # SHORT type
                },
            ],
        }
        trading_client._make_request.return_value = mock_response

        positions = await trading_client.search_open_positions()

        assert len(positions) == 2
        assert positions[0].contractId == "ES"
        assert positions[0].size == 1
        assert positions[0].type == 1  # LONG
        assert positions[1].contractId == "NQ"
        assert positions[1].size == 2
        assert positions[1].type == 2  # SHORT
        trading_client._ensure_authenticated.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_open_positions_with_account_id(self, trading_client):
        """Test position search with specific account ID."""
        # No account_info set, but provide explicit account_id
        custom_account_id = 67890

        mock_response = {
            "success": True,
            "positions": [
                {
                    "id": "pos1",
                    "accountId": custom_account_id,
                    "contractId": "MGC",
                    "creationTimestamp": datetime.datetime.now(pytz.UTC).isoformat(),
                    "size": 10,
                    "averagePrice": 1900.0,
                    "type": 1,
                }
            ],
        }
        trading_client._make_request.return_value = mock_response

        positions = await trading_client.search_open_positions(
            account_id=custom_account_id
        )

        assert len(positions) == 1
        assert positions[0].accountId == custom_account_id

        # Verify the request was made with the custom account ID
        trading_client._make_request.assert_called_once_with(
            "POST", "/Position/searchOpen", data={"accountId": custom_account_id}
        )

    @pytest.mark.asyncio
    async def test_search_open_positions_no_account(self, trading_client):
        """Test error when no account is available."""
        # No account_info and no account_id provided
        trading_client.account_info = None

        with pytest.raises(ProjectXError, match="No account ID available"):
            await trading_client.search_open_positions()

    @pytest.mark.asyncio
    async def test_search_open_positions_list_response(self, trading_client):
        """Test handling of list response format (new API)."""
        trading_client.account_info = Account(
            id=12345,
            name="Test Account",
            balance=10000.0,
            canTrade=True,
            isVisible=True,
            simulated=False,
        )

        # API returns list directly (new format)
        mock_response = [
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
        trading_client._make_request.return_value = mock_response

        positions = await trading_client.search_open_positions()

        assert len(positions) == 1
        assert positions[0].contractId == "CL"

    @pytest.mark.asyncio
    async def test_search_open_positions_empty(self, trading_client):
        """Test empty position response."""
        trading_client.account_info = Account(
            id=12345,
            name="Test Account",
            balance=10000.0,
            canTrade=True,
            isVisible=True,
            simulated=False,
        )

        mock_response = {"success": True, "positions": []}
        trading_client._make_request.return_value = mock_response

        positions = await trading_client.search_open_positions()

        assert positions == []

    @pytest.mark.asyncio
    async def test_search_open_positions_none_response(self, trading_client):
        """Test None response handling."""
        trading_client.account_info = Account(
            id=12345,
            name="Test Account",
            balance=10000.0,
            canTrade=True,
            isVisible=True,
            simulated=False,
        )

        trading_client._make_request.return_value = None

        positions = await trading_client.search_open_positions()

        assert positions == []

    @pytest.mark.asyncio
    async def test_search_open_positions_failed_response(self, trading_client):
        """Test handling of failed API response."""
        trading_client.account_info = Account(
            id=12345,
            name="Test Account",
            balance=10000.0,
            canTrade=True,
            isVisible=True,
            simulated=False,
        )

        mock_response = {"success": False, "error": "API Error"}
        trading_client._make_request.return_value = mock_response

        positions = await trading_client.search_open_positions()

        assert positions == []

    @pytest.mark.asyncio
    async def test_search_open_positions_invalid_response_type(self, trading_client):
        """Test handling of invalid response type."""
        trading_client.account_info = Account(
            id=12345,
            name="Test Account",
            balance=10000.0,
            canTrade=True,
            isVisible=True,
            simulated=False,
        )

        # Invalid response type (string instead of list/dict)
        trading_client._make_request.return_value = "invalid response"

        positions = await trading_client.search_open_positions()

        assert positions == []

    @pytest.mark.asyncio
    async def test_search_trades_success(self, trading_client):
        """Test successful trade search."""
        trading_client.account_info = Account(
            id=12345,
            name="Test Account",
            balance=10000.0,
            canTrade=True,
            isVisible=True,
            simulated=False,
        )

        mock_response = [
            {
                "id": 1,
                "accountId": 12345,
                "contractId": "ES",
                "creationTimestamp": datetime.datetime.now(pytz.UTC).isoformat(),
                "price": 4500.0,
                "profitAndLoss": 50.0,
                "fees": 2.50,
                "side": 0,  # Buy
                "size": 2,
                "voided": False,
                "orderId": 100,
            },
            {
                "id": 2,
                "accountId": 12345,
                "contractId": "NQ",
                "creationTimestamp": (
                    datetime.datetime.now(pytz.UTC) - timedelta(hours=1)
                ).isoformat(),
                "price": 15000.0,
                "profitAndLoss": None,  # Half-turn trade
                "fees": 2.25,
                "side": 1,  # Sell
                "size": 1,
                "voided": False,
                "orderId": 101,
            },
        ]
        trading_client._make_request.return_value = mock_response

        trades = await trading_client.search_trades()

        assert len(trades) == 2
        assert trades[0].contractId == "ES"
        assert trades[0].size == 2
        assert trades[0].price == 4500.0
        assert trades[0].side == 0  # Buy
        assert trades[1].contractId == "NQ"
        assert trades[1].size == 1
        assert trades[1].side == 1  # Sell
        trading_client._ensure_authenticated.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_trades_with_date_range(self, trading_client):
        """Test trade search with custom date range."""
        trading_client.account_info = Account(
            id=12345,
            name="Test Account",
            balance=10000.0,
            canTrade=True,
            isVisible=True,
            simulated=False,
        )

        start_date = datetime.datetime(2025, 1, 1, 9, 30, tzinfo=pytz.UTC)
        end_date = datetime.datetime(2025, 1, 15, 16, 0, tzinfo=pytz.UTC)

        mock_response = []
        trading_client._make_request.return_value = mock_response

        trades = await trading_client.search_trades(
            start_date=start_date,
            end_date=end_date,
        )

        # Verify the request parameters
        trading_client._make_request.assert_called_once_with(
            "GET",
            "/trades/search",
            params={
                "accountId": 12345,
                "startDate": start_date.isoformat(),
                "endDate": end_date.isoformat(),
                "limit": 100,
            },
        )

    @pytest.mark.asyncio
    async def test_search_trades_with_contract_filter(self, trading_client):
        """Test trade search with contract ID filter."""
        trading_client.account_info = Account(
            id=12345,
            name="Test Account",
            balance=10000.0,
            canTrade=True,
            isVisible=True,
            simulated=False,
        )

        mock_response = [
            {
                "id": 1,
                "accountId": 12345,
                "contractId": "MNQ",
                "creationTimestamp": datetime.datetime.now(pytz.UTC).isoformat(),
                "price": 15000.0,
                "profitAndLoss": 75.0,
                "fees": 2.25,
                "side": 0,  # Buy
                "size": 3,
                "voided": False,
                "orderId": 102,
            }
        ]
        trading_client._make_request.return_value = mock_response

        trades = await trading_client.search_trades(contract_id="MNQ", limit=50)

        assert len(trades) == 1
        assert trades[0].contractId == "MNQ"

        # Verify contract_id was included in request
        call_args = trading_client._make_request.call_args
        assert call_args[1]["params"]["contractId"] == "MNQ"
        assert call_args[1]["params"]["limit"] == 50

    @pytest.mark.asyncio
    async def test_search_trades_custom_account_id(self, trading_client):
        """Test trade search with custom account ID."""
        # No account_info, use explicit account_id
        custom_account_id = 67890

        mock_response = []
        trading_client._make_request.return_value = mock_response

        trades = await trading_client.search_trades(account_id=custom_account_id)

        # Verify the request used custom account ID
        call_args = trading_client._make_request.call_args
        assert call_args[1]["params"]["accountId"] == custom_account_id

    @pytest.mark.asyncio
    async def test_search_trades_no_account(self, trading_client):
        """Test error when no account is available for trade search."""
        trading_client.account_info = None

        with pytest.raises(ProjectXError, match="No account information available"):
            await trading_client.search_trades()

    @pytest.mark.asyncio
    async def test_search_trades_default_dates(self, trading_client):
        """Test default date range (30 days)."""
        trading_client.account_info = Account(
            id=12345,
            name="Test Account",
            balance=10000.0,
            canTrade=True,
            isVisible=True,
            simulated=False,
        )

        mock_response = []
        trading_client._make_request.return_value = mock_response

        # Mock datetime.now to get consistent test results
        mock_now = datetime.datetime(2025, 1, 15, 12, 0, tzinfo=pytz.UTC)
        with patch("project_x_py.client.trading.datetime") as mock_datetime:
            mock_datetime.datetime.now.return_value = mock_now
            mock_datetime.timedelta = timedelta

            trades = await trading_client.search_trades()

        # Verify date range is approximately 30 days
        call_args = trading_client._make_request.call_args
        params = call_args[1]["params"]

        start_date = datetime.datetime.fromisoformat(params["startDate"])
        end_date = datetime.datetime.fromisoformat(params["endDate"])

        date_diff = end_date - start_date
        assert 29 <= date_diff.days <= 31

    @pytest.mark.asyncio
    async def test_search_trades_with_start_date_only(self, trading_client):
        """Test trade search with only start date provided."""
        trading_client.account_info = Account(
            id=12345,
            name="Test Account",
            balance=10000.0,
            canTrade=True,
            isVisible=True,
            simulated=False,
        )

        start_date = datetime.datetime(2025, 1, 1, 9, 30, tzinfo=pytz.UTC)

        mock_response = []
        trading_client._make_request.return_value = mock_response

        # Mock datetime.now for end_date default
        mock_now = datetime.datetime(2025, 1, 15, 12, 0, tzinfo=pytz.UTC)
        with patch("project_x_py.client.trading.datetime") as mock_datetime:
            mock_datetime.datetime.now.return_value = mock_now
            mock_datetime.timedelta = timedelta

            trades = await trading_client.search_trades(start_date=start_date)

        # Verify end_date defaulted to now
        call_args = trading_client._make_request.call_args
        params = call_args[1]["params"]

        assert params["startDate"] == start_date.isoformat()
        end_date = datetime.datetime.fromisoformat(params["endDate"])
        assert end_date == mock_now

    @pytest.mark.asyncio
    async def test_search_trades_with_end_date_only(self, trading_client):
        """Test trade search with only end date provided."""
        trading_client.account_info = Account(
            id=12345,
            name="Test Account",
            balance=10000.0,
            canTrade=True,
            isVisible=True,
            simulated=False,
        )

        end_date = datetime.datetime(2025, 1, 15, 16, 0, tzinfo=pytz.UTC)

        mock_response = []
        trading_client._make_request.return_value = mock_response

        trades = await trading_client.search_trades(end_date=end_date)

        # Verify start_date is 30 days before end_date
        call_args = trading_client._make_request.call_args
        params = call_args[1]["params"]

        start_date = datetime.datetime.fromisoformat(params["startDate"])
        assert params["endDate"] == end_date.isoformat()

        date_diff = end_date - start_date
        assert 29 <= date_diff.days <= 31

    @pytest.mark.asyncio
    async def test_search_trades_empty_response(self, trading_client):
        """Test handling of empty trade response."""
        trading_client.account_info = Account(
            id=12345,
            name="Test Account",
            balance=10000.0,
            canTrade=True,
            isVisible=True,
            simulated=False,
        )

        trading_client._make_request.return_value = []

        trades = await trading_client.search_trades()

        assert trades == []

    @pytest.mark.asyncio
    async def test_search_trades_none_response(self, trading_client):
        """Test handling of None response."""
        trading_client.account_info = Account(
            id=12345,
            name="Test Account",
            balance=10000.0,
            canTrade=True,
            isVisible=True,
            simulated=False,
        )

        trading_client._make_request.return_value = None

        trades = await trading_client.search_trades()

        assert trades == []

    @pytest.mark.asyncio
    async def test_search_trades_invalid_response_type(self, trading_client):
        """Test handling of invalid response type."""
        trading_client.account_info = Account(
            id=12345,
            name="Test Account",
            balance=10000.0,
            canTrade=True,
            isVisible=True,
            simulated=False,
        )

        # Invalid response type (dict instead of list)
        trading_client._make_request.return_value = {"trades": []}

        trades = await trading_client.search_trades()

        assert trades == []

    @pytest.mark.asyncio
    async def test_authentication_called_for_all_methods(self, trading_client):
        """Test that all methods ensure authentication."""
        trading_client.account_info = Account(
            id=12345,
            name="Test Account",
            balance=10000.0,
            canTrade=True,
            isVisible=True,
            simulated=False,
        )

        trading_client._make_request.return_value = []

        # Test search_open_positions
        await trading_client.search_open_positions()
        assert trading_client._ensure_authenticated.call_count == 1

        # Test search_trades
        await trading_client.search_trades()
        assert trading_client._ensure_authenticated.call_count == 2

        # Test get_positions (deprecated)
        with pytest.warns(DeprecationWarning, match="(get_positions|Method renamed)"):
            await trading_client.get_positions()
        assert trading_client._ensure_authenticated.call_count == 3
