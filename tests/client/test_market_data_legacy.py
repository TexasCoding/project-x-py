"""Tests for the market data module of ProjectX client."""

from datetime import datetime
from unittest.mock import AsyncMock, Mock

import polars as pl
import pytest
import pytz

from project_x_py.client.market_data import MarketDataMixin
from project_x_py.exceptions import ProjectXError, ProjectXInstrumentError
from project_x_py.models import Instrument


class MockMarketDataClient(MarketDataMixin):
    """Mock client that includes MarketDataMixin for testing."""

    def __init__(self):
        super().__init__()
        self.base_url = "https://api.test.com"
        self._http_client = AsyncMock()
        self._make_request = AsyncMock()
        self._ensure_authenticated = AsyncMock()
        self._authenticated = False
        self.config = Mock()
        self.config.timezone = "America/Chicago"
        self.logger = Mock()
        # Mock cache methods
        self.get_cached_instrument = Mock(return_value=None)
        self.cache_instrument = Mock()
        self.get_cached_market_data = Mock(return_value=None)
        self.cache_market_data = Mock()


class TestMarketDataMixin:
    """Test suite for MarketDataMixin class."""

    @pytest.fixture
    def market_client(self):
        """Create a mock client with MarketDataMixin for testing."""
        return MockMarketDataClient()

    @pytest.mark.asyncio
    async def test_get_instrument_success(self, market_client):
        """Test successful instrument retrieval."""
        mock_response = {
            "success": True,
            "contracts": [
                {
                    "id": "CON.F.US.MNQ.U25",
                    "name": "MNQU25",
                    "description": "Micro E-mini Nasdaq-100 Sep 2025",
                    "tickSize": 0.25,
                    "tickValue": 12.5,
                    "activeContract": True,
                    "symbolId": "MNQ",
                }
            ],
        }
        market_client._make_request.return_value = mock_response

        instrument = await market_client.get_instrument("MNQ")

        assert instrument.id == "CON.F.US.MNQ.U25"
        assert instrument.name == "MNQU25"
        assert instrument.description == "Micro E-mini Nasdaq-100 Sep 2025"
        assert instrument.tickSize == 0.25
        assert instrument.tickValue == 12.5
        assert instrument.activeContract is True
        market_client.cache_instrument.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_instrument_with_cache_hit(self, market_client):
        """Test instrument retrieval when cache has the data."""
        cached_instrument = Instrument(
            id="CON.F.US.MNQ.U25",
            name="MNQU25",
            description="Micro E-mini Nasdaq-100 Sep 2025",
            tickSize=0.25,
            tickValue=12.5,
            activeContract=True,
            symbolId="MNQ",
        )
        market_client.get_cached_instrument.return_value = cached_instrument

        instrument = await market_client.get_instrument("MNQ")

        assert instrument == cached_instrument
        market_client._make_request.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_instrument_direct_contract_id(self, market_client):
        """Test getting instrument by direct contract ID."""
        mock_response = {
            "success": True,
            "contracts": [
                {
                    "id": "CON.F.US.MNQ.U25",
                    "name": "MNQU25",
                    "description": "Micro E-mini Nasdaq-100 futures",
                    "tickSize": 0.25,
                    "tickValue": 12.5,
                    "activeContract": True,
                    "symbolId": "MNQ",
                }
            ],
        }
        market_client._make_request.return_value = mock_response

        instrument = await market_client.get_instrument("CON.F.US.MNQ.U25")

        assert instrument.id == "CON.F.US.MNQ.U25"
        # Should search by ID when format matches CON.*
        market_client._make_request.assert_called_once()
        call_args = market_client._make_request.call_args
        # Check that it uses /Contract/search endpoint
        assert call_args[0][1] == "/Contract/search"

    @pytest.mark.asyncio
    async def test_get_instrument_no_results(self, market_client):
        """Test instrument retrieval with no results."""
        mock_response = {"success": True, "contracts": []}
        market_client._make_request.return_value = mock_response

        with pytest.raises(ProjectXInstrumentError, match="Instrument not found"):
            await market_client.get_instrument("INVALID")

    @pytest.mark.asyncio
    async def test_get_instrument_api_error(self, market_client):
        """Test instrument retrieval with API error."""
        mock_response = {"success": False, "error": "API Error"}
        market_client._make_request.return_value = mock_response

        with pytest.raises(ProjectXError):  # Will be wrapped by handle_errors
            await market_client.get_instrument("MNQ")

    @pytest.mark.asyncio
    async def test_search_instruments_success(self, market_client):
        """Test successful instrument search."""
        mock_response = {
            "success": True,
            "contracts": [
                {
                    "id": "CON.F.US.MNQ.U25",
                    "name": "MNQU25",
                    "description": "Micro E-mini Nasdaq-100 futures",
                    "tickSize": 0.25,
                    "tickValue": 12.5,
                    "activeContract": True,
                    "symbolId": "MNQ",
                },
                {
                    "id": "CON.F.US.MNQ.Z25",
                    "name": "MNQZ25",
                    "description": "Micro E-mini Nasdaq-100 futures",
                    "tickSize": 0.25,
                    "tickValue": 12.5,
                    "activeContract": True,
                    "symbolId": "MNQ",
                },
            ],
        }
        market_client._make_request.return_value = mock_response

        instruments = await market_client.search_instruments("MNQ")

        assert len(instruments) == 2
        assert instruments[0].name == "MNQU25"
        assert instruments[1].name == "MNQZ25"

    @pytest.mark.asyncio
    async def test_search_instruments_live_only(self, market_client):
        """Test instrument search with live-only filter."""
        mock_response = {"success": True, "contracts": []}
        market_client._make_request.return_value = mock_response

        instruments = await market_client.search_instruments("MNQ", live=True)

        assert instruments == []
        # Check that live parameter was passed
        call_args = market_client._make_request.call_args
        assert "data" in call_args[1]
        assert call_args[1]["data"]["live"] is True

    @pytest.mark.asyncio
    async def test_get_bars_success(self, market_client):
        """Test successful bar data retrieval."""
        # Mock instrument response
        instrument_response = {
            "success": True,
            "contracts": [
                {
                    "id": "CON.F.US.MNQ.U25",
                    "name": "MNQU25",
                    "description": "Micro E-mini Nasdaq-100 futures",
                    "tickSize": 0.25,
                    "tickValue": 12.5,
                    "activeContract": True,
                    "symbolId": "MNQ",
                }
            ],
        }

        # Mock bars response
        bars_response = {
            "success": True,
            "bars": [
                {
                    "t": "2025-01-15T14:00:00Z",
                    "o": 21000.0,
                    "h": 21050.0,
                    "l": 20950.0,
                    "c": 21025.0,
                    "v": 1500,
                },
                {
                    "t": "2025-01-15T14:05:00Z",
                    "o": 21025.0,
                    "h": 21075.0,
                    "l": 21020.0,
                    "c": 21070.0,
                    "v": 2000,
                },
            ],
        }

        market_client._make_request.side_effect = [instrument_response, bars_response]

        bars = await market_client.get_bars("MNQ", days=1, interval=5)

        assert isinstance(bars, pl.DataFrame)
        assert len(bars) == 2
        assert "timestamp" in bars.columns
        assert "open" in bars.columns
        assert "high" in bars.columns
        assert "low" in bars.columns
        assert "close" in bars.columns
        assert "volume" in bars.columns
        assert bars["close"][0] == 21025.0
        assert bars["volume"][1] == 2000

    @pytest.mark.asyncio
    async def test_get_bars_with_cache_hit(self, market_client):
        """Test bar data retrieval when cache has the data."""
        cached_bars = pl.DataFrame(
            {
                "timestamp": [datetime.now(pytz.UTC)],
                "open": [21000.0],
                "high": [21050.0],
                "low": [20950.0],
                "close": [21025.0],
                "volume": [1500],
            }
        )
        market_client.get_cached_market_data.return_value = cached_bars

        bars = await market_client.get_bars("MNQ", days=1)

        assert bars.equals(cached_bars)
        market_client._make_request.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_bars_with_time_range(self, market_client):
        """Test bar data retrieval with specific time range."""
        # Mock instrument response
        instrument_response = {
            "success": True,
            "contracts": [
                {
                    "id": "CON.F.US.MNQ.U25",
                    "name": "MNQU25",
                    "description": "Micro E-mini Nasdaq-100 futures",
                    "tickSize": 0.25,
                    "tickValue": 12.5,
                    "activeContract": True,
                    "symbolId": "MNQ",
                }
            ],
        }

        # Mock bars response
        bars_response = {"success": True, "bars": []}

        market_client._make_request.side_effect = [instrument_response, bars_response]

        start_time = datetime(2025, 1, 1, 9, 30)
        end_time = datetime(2025, 1, 1, 16, 0)

        bars = await market_client.get_bars(
            "MNQ", start_time=start_time, end_time=end_time, interval=15
        )

        # Verify the request included time range parameters
        calls = market_client._make_request.call_args_list
        bars_call = calls[1]
        assert "data" in bars_call[1]
        assert "startTime" in bars_call[1]["data"]
        assert "endTime" in bars_call[1]["data"]

    @pytest.mark.asyncio
    async def test_get_bars_empty_response(self, market_client):
        """Test bar data retrieval with empty response."""
        # Mock instrument response
        instrument_response = {
            "success": True,
            "contracts": [
                {
                    "id": "CON.F.US.MNQ.U25",
                    "name": "MNQU25",
                    "description": "Micro E-mini Nasdaq-100 futures",
                    "tickSize": 0.25,
                    "tickValue": 12.5,
                    "activeContract": True,
                    "symbolId": "MNQ",
                }
            ],
        }

        bars_response = {"success": True, "bars": []}

        market_client._make_request.side_effect = [instrument_response, bars_response]

        bars = await market_client.get_bars("MNQ", days=1)

        assert isinstance(bars, pl.DataFrame)
        assert len(bars) == 0
        # Empty DataFrame won't have columns

    @pytest.mark.asyncio
    async def test_get_bars_api_error(self, market_client):
        """Test bar data retrieval with API error."""
        # Mock instrument response
        instrument_response = {
            "success": True,
            "contracts": [
                {
                    "id": "CON.F.US.MNQ.U25",
                    "name": "MNQU25",
                    "description": "Micro E-mini Nasdaq-100 futures",
                    "tickSize": 0.25,
                    "tickValue": 12.5,
                    "activeContract": True,
                    "symbolId": "MNQ",
                }
            ],
        }

        market_client._make_request.side_effect = [
            instrument_response,
            Exception("API Error"),
        ]

        with pytest.raises(Exception, match="API Error"):
            await market_client.get_bars("MNQ", days=1)

    def test_select_best_contract_exact_match(self, market_client):
        """Test contract selection with exact symbol match."""
        instruments = [
            {"name": "MNQ", "description": "Base MNQ"},
            {"name": "MNQU25", "description": "MNQ Sep 2025"},
            {"name": "MNQZ25", "description": "MNQ Dec 2025"},
        ]

        result = market_client._select_best_contract(instruments, "MNQ")

        assert result["name"] == "MNQ"

    def test_select_best_contract_futures_front_month(self, market_client):
        """Test contract selection for futures front month."""
        instruments = [
            {"name": "MNQZ25", "description": "MNQ Dec 2025"},
            {"name": "MNQU25", "description": "MNQ Sep 2025"},
            {"name": "MNQH26", "description": "MNQ Mar 2026"},
        ]

        result = market_client._select_best_contract(instruments, "MNQ")

        # Should select the chronologically first (front month)
        assert result["name"] == "MNQH26"

    def test_select_best_contract_no_instruments(self, market_client):
        """Test contract selection with no instruments."""
        with pytest.raises(ProjectXInstrumentError, match="No instruments found"):
            market_client._select_best_contract([], "MNQ")

    def test_select_best_contract_case_insensitive(self, market_client):
        """Test contract selection is case insensitive."""
        instruments = [
            {"name": "mnq", "description": "Base MNQ"},
            {"name": "MNQU25", "description": "MNQ Sep 2025"},
        ]

        result = market_client._select_best_contract(instruments, "MNQ")

        assert result["name"] == "mnq"

    @pytest.mark.asyncio
    async def test_get_bars_different_intervals(self, market_client):
        """Test bar data retrieval with different interval units."""
        # Mock responses
        instrument_response = {
            "success": True,
            "contracts": [
                {
                    "id": "CON.F.US.ES.U25",
                    "name": "ESU25",
                    "description": "E-mini S&P 500 futures",
                    "tickSize": 0.25,
                    "tickValue": 12.5,
                    "activeContract": True,
                    "symbolId": "ES",
                }
            ],
        }

        bars_response = {"success": True, "bars": []}

        market_client._make_request.side_effect = [
            instrument_response,
            bars_response,
            instrument_response,
            bars_response,
            instrument_response,
            bars_response,
        ]

        # Test minute bars
        bars = await market_client.get_bars("ES", days=1, interval=15, unit=2)
        assert isinstance(bars, pl.DataFrame)

        # Test hourly bars
        bars = await market_client.get_bars("ES", days=7, interval=1, unit=3)
        assert isinstance(bars, pl.DataFrame)

        # Test daily bars
        bars = await market_client.get_bars("ES", days=30, interval=1, unit=4)
        assert isinstance(bars, pl.DataFrame)

    @pytest.mark.asyncio
    async def test_authentication_check(self, market_client):
        """Test that methods ensure authentication."""
        # Mock responses for each method
        instrument_response = {"success": True, "contracts": []}

        market_client._make_request.return_value = instrument_response

        # Test get_instrument
        try:
            await market_client.get_instrument("MNQ")
        except Exception:
            pass
        market_client._ensure_authenticated.assert_called()

        # Reset mock
        market_client._ensure_authenticated.reset_mock()

        # Test search_instruments
        await market_client.search_instruments("MNQ")
        market_client._ensure_authenticated.assert_called()

        # Reset mock
        market_client._ensure_authenticated.reset_mock()

        # Test get_bars (will fail but that's ok)
        try:
            await market_client.get_bars("MNQ")
        except Exception:
            pass
        market_client._ensure_authenticated.assert_called()
