"""Tests for the market data functionality of ProjectX client."""

import datetime
import time
from unittest.mock import patch

import polars as pl
import pytest
import pytz

from project_x_py import ProjectX
from project_x_py.exceptions import ProjectXInstrumentError
from project_x_py.utils.async_rate_limiter import RateLimiter


class TestMarketData:
    """Tests for the market data functionality of the ProjectX client."""

    @pytest.mark.asyncio
    async def test_get_instrument(
        self, mock_httpx_client, mock_auth_response, mock_instrument_response
    ):
        """Test getting instrument data."""
        auth_response, accounts_response = mock_auth_response
        mock_httpx_client.request.side_effect = [
            auth_response,  # Initial auth
            accounts_response,  # Initial accounts
            mock_instrument_response,  # Instrument search
        ]

        with patch("httpx.AsyncClient", return_value=mock_httpx_client):
            async with ProjectX("testuser", "test-api-key") as client:
                # Initialize required attributes
                client.api_call_count = 0
                client._opt_instrument_cache = {}
                client._opt_instrument_cache_time = {}
                client._opt_market_data_cache = {}
                client._opt_market_data_cache_time = {}
                client.cache_ttl = 300
                client.last_cache_cleanup = time.time()
                client.cache_hit_count = 0
                client.rate_limiter = RateLimiter(max_requests=100, window_seconds=60)
                await client.authenticate()

                instrument = await client.get_instrument("MGC")

                assert instrument is not None
                assert instrument.id == "123"
                assert instrument.name == "Micro Gold Futures"

                # Should have cached the result
                assert "MGC" in client._opt_instrument_cache

    @pytest.mark.asyncio
    async def test_get_instrument_uses_search_by_id(self, initialized_client):
        """Full contract IDs must call POST /Contract/searchById."""
        from unittest.mock import AsyncMock

        initialized_client._authenticated = True
        initialized_client.token_expiry = datetime.datetime.now(
            pytz.UTC
        ) + datetime.timedelta(hours=1)
        initialized_client._ensure_authenticated = AsyncMock(return_value=None)
        initialized_client.get_cached_instrument = lambda _symbol: None
        initialized_client._make_request = AsyncMock(
            return_value={
                "success": True,
                "contract": {
                    "id": "CON.F.US.MNQ.U25",
                    "name": "MNQU25",
                    "description": "Micro Nasdaq",
                    "tickSize": 0.25,
                    "tickValue": 0.5,
                    "activeContract": True,
                    "symbolId": "F.US.MNQ",
                },
            }
        )
        instrument = await initialized_client.get_instrument("CON.F.US.MNQ.U25")
        assert instrument.id == "CON.F.US.MNQ.U25"
        assert (
            initialized_client._make_request.await_args.args[1]
            == "/Contract/searchById"
        )

    @pytest.mark.asyncio
    async def test_get_instrument_search_payload_and_endpoint(self, initialized_client):
        """Symbol lookup posts /Contract/search with searchText and live."""
        from unittest.mock import AsyncMock

        initialized_client._ensure_authenticated = AsyncMock(return_value=None)
        initialized_client.get_cached_instrument = lambda _symbol: None
        initialized_client.cache_instrument = lambda *_args, **_kwargs: None
        initialized_client._make_request = AsyncMock(
            return_value={
                "success": True,
                "contracts": [
                    {
                        "id": "CON.F.US.MNQ.U25",
                        "name": "MNQU25",
                        "description": "Micro Nasdaq",
                        "tickSize": 0.25,
                        "tickValue": 0.5,
                        "activeContract": True,
                        "symbolId": "F.US.MNQ",
                    }
                ],
            }
        )

        instrument = await initialized_client.get_instrument("MNQ")

        assert instrument.id == "CON.F.US.MNQ.U25"
        method, endpoint = initialized_client._make_request.await_args.args
        payload = initialized_client._make_request.await_args.kwargs["data"]
        assert method == "POST"
        assert endpoint == "/Contract/search"
        assert payload["searchText"] == "MNQ"
        assert payload["live"] is False

    @pytest.mark.asyncio
    async def test_search_instruments_live_only(self, initialized_client):
        """search_instruments forwards live=True on /Contract/search."""
        from unittest.mock import AsyncMock

        initialized_client._ensure_authenticated = AsyncMock(return_value=None)
        initialized_client._make_request = AsyncMock(
            return_value={"success": True, "contracts": []}
        )

        instruments = await initialized_client.search_instruments("MNQ", live=True)

        assert instruments == []
        method, endpoint = initialized_client._make_request.await_args.args
        payload = initialized_client._make_request.await_args.kwargs["data"]
        assert method == "POST"
        assert endpoint == "/Contract/search"
        assert payload == {"searchText": "MNQ", "live": True}

    @pytest.mark.asyncio
    async def test_get_instrument_from_cache(
        self, mock_httpx_client, mock_auth_response, mock_instrument
    ):
        """Test getting instrument data from cache."""
        auth_response, accounts_response = mock_auth_response
        mock_httpx_client.request.side_effect = [
            auth_response,  # Initial auth
            accounts_response,  # Initial accounts
        ]

        with patch("httpx.AsyncClient", return_value=mock_httpx_client):
            async with ProjectX("testuser", "test-api-key") as client:
                # Initialize required attributes
                client.api_call_count = 0
                client._opt_instrument_cache = {}
                client._opt_instrument_cache_time = {}
                client._opt_market_data_cache = {}
                client._opt_market_data_cache_time = {}
                client.cache_ttl = 300
                client.last_cache_cleanup = time.time()
                client.cache_hit_count = 0
                client.rate_limiter = RateLimiter(max_requests=100, window_seconds=60)
                await client.authenticate()

                # Add to cache
                client.cache_instrument("MGC", mock_instrument)

                # Should get from cache without API call
                instrument = await client.get_instrument("MGC")

                assert instrument is not None
                assert instrument.id == "123"

                # Should only have made the auth calls
                assert mock_httpx_client.request.call_count == 2

    @pytest.mark.asyncio
    async def test_get_instrument_not_found(
        self, mock_httpx_client, mock_auth_response, mock_response
    ):
        """Test error handling when instrument not found."""
        auth_response, accounts_response = mock_auth_response
        not_found_response = mock_response(
            json_data={"success": False, "message": "No instruments found"}
        )

        mock_httpx_client.request.side_effect = [
            auth_response,  # Initial auth
            accounts_response,  # Initial accounts
            not_found_response,  # Instrument search
        ]

        with patch("httpx.AsyncClient", return_value=mock_httpx_client):
            async with ProjectX("testuser", "test-api-key") as client:
                # Initialize required attributes
                client.api_call_count = 0
                client._opt_instrument_cache = {}
                client._opt_instrument_cache_time = {}
                client._opt_market_data_cache = {}
                client._opt_market_data_cache_time = {}
                client.cache_ttl = 300
                client.last_cache_cleanup = time.time()
                client.cache_hit_count = 0
                client.rate_limiter = RateLimiter(max_requests=100, window_seconds=60)
                await client.authenticate()

                with pytest.raises(ProjectXInstrumentError) as exc_info:
                    await client.get_instrument("INVALID")

                assert "Instrument not found: INVALID" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_search_instruments(
        self, mock_httpx_client, mock_auth_response, mock_instrument_response
    ):
        """Test searching for instruments."""
        auth_response, accounts_response = mock_auth_response
        mock_httpx_client.request.side_effect = [
            auth_response,  # Initial auth
            accounts_response,  # Initial accounts
            mock_instrument_response,  # Instrument search
        ]

        with patch("httpx.AsyncClient", return_value=mock_httpx_client):
            async with ProjectX("testuser", "test-api-key") as client:
                # Initialize required attributes
                client.api_call_count = 0
                client._opt_instrument_cache = {}
                client._opt_instrument_cache_time = {}
                client._opt_market_data_cache = {}
                client._opt_market_data_cache_time = {}
                client.cache_ttl = 300
                client.last_cache_cleanup = time.time()
                client.cache_hit_count = 0
                client.rate_limiter = RateLimiter(max_requests=100, window_seconds=60)
                await client.authenticate()

                instruments = await client.search_instruments("gold")

                assert len(instruments) == 1
                assert instruments[0].id == "123"
                assert instruments[0].name == "Micro Gold Futures"

    @pytest.mark.asyncio
    async def test_search_instruments_empty_result(
        self, mock_httpx_client, mock_auth_response, mock_response
    ):
        """Test searching for instruments with empty result."""
        auth_response, accounts_response = mock_auth_response
        empty_response = mock_response(json_data={"success": True, "contracts": []})

        mock_httpx_client.request.side_effect = [
            auth_response,  # Initial auth
            accounts_response,  # Initial accounts
            empty_response,  # Instrument search
        ]

        with patch("httpx.AsyncClient", return_value=mock_httpx_client):
            async with ProjectX("testuser", "test-api-key") as client:
                # Initialize required attributes
                client.api_call_count = 0
                client._opt_instrument_cache = {}
                client._opt_instrument_cache_time = {}
                client._opt_market_data_cache = {}
                client._opt_market_data_cache_time = {}
                client.cache_ttl = 300
                client.last_cache_cleanup = time.time()
                client.cache_hit_count = 0
                client.rate_limiter = RateLimiter(max_requests=100, window_seconds=60)
                await client.authenticate()

                instruments = await client.search_instruments("nonexistent")

                assert len(instruments) == 0

    @pytest.mark.asyncio
    async def test_select_best_contract(self, mock_httpx_client):
        """Test selecting best contract from search results."""
        with patch("httpx.AsyncClient", return_value=mock_httpx_client):
            async with ProjectX("testuser", "test-api-key") as client:
                # Initialize required attributes
                client.api_call_count = 0
                client._opt_instrument_cache = {}
                client._opt_instrument_cache_time = {}
                client._opt_market_data_cache = {}
                client._opt_market_data_cache_time = {}
                client.cache_ttl = 300
                client.last_cache_cleanup = time.time()
                client.cache_hit_count = 0
                client.rate_limiter = RateLimiter(max_requests=100, window_seconds=60)
                # Test with empty list
                with pytest.raises(ProjectXInstrumentError):
                    client._select_best_contract([], "MGC")

                # Test with exact match (uses 'name' field, not 'symbol')
                contracts = [
                    {"symbol": "ES", "name": "ES"},
                    {"symbol": "MGC", "name": "MGC"},
                    {"symbol": "MNQ", "name": "MNQ"},
                ]

                result = client._select_best_contract(contracts, "MGC")
                assert result["name"] == "MGC"

                # Test with futures contracts
                futures_contracts = [
                    {"symbol": "MGC", "name": "MGC"},
                    {"symbol": "MGCM23", "name": "MGCM23"},
                    {"symbol": "MGCZ23", "name": "MGCZ23"},
                ]

                result = client._select_best_contract(futures_contracts, "MGC")
                assert result["name"] == "MGC"

                # When no exact match, should pick first one
                result = client._select_best_contract(contracts, "unknown")
                assert result["name"] == "ES"

    @pytest.mark.asyncio
    async def test_get_bars(
        self,
        mock_httpx_client,
        mock_auth_response,
        mock_instrument_response,
        mock_bars_response,
    ):
        """Test getting market data bars."""
        auth_response, accounts_response = mock_auth_response
        mock_httpx_client.request.side_effect = [
            auth_response,  # Initial auth
            accounts_response,  # Initial accounts
            mock_instrument_response,  # Instrument search
            mock_bars_response,  # Bars data
        ]

        with patch("httpx.AsyncClient", return_value=mock_httpx_client):
            async with ProjectX("testuser", "test-api-key") as client:
                # Initialize required attributes
                client.api_call_count = 0
                client._opt_instrument_cache = {}
                client._opt_instrument_cache_time = {}
                client._opt_market_data_cache = {}
                client._opt_market_data_cache_time = {}
                client.cache_ttl = 300
                client.last_cache_cleanup = time.time()
                client.cache_hit_count = 0
                client.rate_limiter = RateLimiter(max_requests=100, window_seconds=60)
                await client.authenticate()

                bars = await client.get_bars("MGC", days=5, interval=5)

                # Verify dataframe structure
                assert not bars.is_empty()
                assert "timestamp" in bars.columns
                assert "open" in bars.columns
                assert "high" in bars.columns
                assert "low" in bars.columns
                assert "close" in bars.columns
                assert "volume" in bars.columns

                # Verify timestamp conversion to time_zone
                assert bars["timestamp"].dtype.time_zone == "America/Chicago"

                # Should cache the result
                cache_key = "MGC_5_5_2_True_False"
                assert cache_key in client._opt_market_data_cache

    @pytest.mark.asyncio
    async def test_get_bars_preserves_extra_api_columns(
        self,
        mock_httpx_client,
        mock_auth_response,
        mock_instrument_response,
        mock_response,
    ):
        """Extra fields in the bars API response are preserved, canonical first."""
        auth_response, accounts_response = mock_auth_response
        now = datetime.datetime.now(pytz.UTC)
        bars_data = [
            {
                "t": (now - datetime.timedelta(minutes=i * 5)).isoformat(),
                "o": 1900.0 + i,
                "h": 1905.0 + i,
                "l": 1895.0 + i,
                "c": 1902.0 + i,
                "v": 100 + i,
                "symbol": "MGC",
                "n": i,
            }
            for i in range(3)
        ]
        bars_response = mock_response(json_data={"success": True, "bars": bars_data})
        mock_httpx_client.request.side_effect = [
            auth_response,
            accounts_response,
            mock_instrument_response,
            bars_response,
        ]

        with patch("httpx.AsyncClient", return_value=mock_httpx_client):
            async with ProjectX("testuser", "test-api-key") as client:
                client.api_call_count = 0
                client._opt_instrument_cache = {}
                client._opt_instrument_cache_time = {}
                client._opt_market_data_cache = {}
                client._opt_market_data_cache_time = {}
                client.cache_ttl = 300
                client.last_cache_cleanup = time.time()
                client.cache_hit_count = 0
                client.rate_limiter = RateLimiter(max_requests=100, window_seconds=60)
                await client.authenticate()

                bars = await client.get_bars("MGC", days=5, interval=5)

                assert bars.columns[:6] == [
                    "timestamp",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                ]
                assert "symbol" in bars.columns
                assert "n" in bars.columns

    @pytest.mark.asyncio
    async def test_get_bars_from_cache(self, mock_httpx_client, mock_auth_response):
        """Test getting bars from cache."""
        auth_response, accounts_response = mock_auth_response
        mock_httpx_client.request.side_effect = [
            auth_response,  # Initial auth
            accounts_response,  # Initial accounts
        ]

        with patch("httpx.AsyncClient", return_value=mock_httpx_client):
            async with ProjectX("testuser", "test-api-key") as client:
                # Initialize required attributes
                client.api_call_count = 0
                client._opt_instrument_cache = {}
                client._opt_instrument_cache_time = {}
                client._opt_market_data_cache = {}
                client._opt_market_data_cache_time = {}
                client.cache_ttl = 300
                client.last_cache_cleanup = time.time()
                client.cache_hit_count = 0
                client.rate_limiter = RateLimiter(max_requests=100, window_seconds=60)
                await client.authenticate()

                # Add to cache
                test_bars = pl.DataFrame(
                    {
                        "timestamp": pl.datetime_range(
                            start=pl.datetime(2023, 1, 1),
                            end=pl.datetime(2023, 1, 2),
                            interval="1h",
                            time_zone="UTC",
                            eager=True,
                        ),
                        "open": [1900.0] * 25,
                        "high": [1910.0] * 25,
                        "low": [1890.0] * 25,
                        "close": [1905.0] * 25,
                        "volume": [100] * 25,
                    }
                )

                cache_key = "MGC_5_5_2_True_False"
                client.cache_market_data(cache_key, test_bars)

                # Should get from cache without API call
                bars = await client.get_bars("MGC", days=5, interval=5)

                assert bars is not None
                assert bars.equals(test_bars)

                # Should only have made the auth calls
                assert mock_httpx_client.request.call_count == 2

    @pytest.mark.asyncio
    async def test_get_bars_empty_response(
        self,
        mock_httpx_client,
        mock_auth_response,
        mock_instrument_response,
        mock_response,
    ):
        """Test handling empty bar data response."""
        auth_response, accounts_response = mock_auth_response
        empty_bars_response = mock_response(json_data={"success": True, "bars": []})

        mock_httpx_client.request.side_effect = [
            auth_response,  # Initial auth
            accounts_response,  # Initial accounts
            mock_instrument_response,  # Instrument search
            empty_bars_response,  # Empty bars data
        ]

        with patch("httpx.AsyncClient", return_value=mock_httpx_client):
            async with ProjectX("testuser", "test-api-key") as client:
                # Initialize required attributes
                client.api_call_count = 0
                client._opt_instrument_cache = {}
                client._opt_instrument_cache_time = {}
                client._opt_market_data_cache = {}
                client._opt_market_data_cache_time = {}
                client.cache_ttl = 300
                client.last_cache_cleanup = time.time()
                client.cache_hit_count = 0
                client.rate_limiter = RateLimiter(max_requests=100, window_seconds=60)
                await client.authenticate()

                bars = await client.get_bars("MGC", days=1, interval=1)

                # Should return empty dataframe
                assert bars.is_empty()

    @pytest.mark.asyncio
    async def test_get_bars_error_response(
        self,
        mock_httpx_client,
        mock_auth_response,
        mock_instrument_response,
        mock_response,
    ):
        """Test handling error in bar data response."""
        auth_response, accounts_response = mock_auth_response
        error_response = mock_response(
            json_data={
                "success": False,
                "errorMessage": "Historical data not available",
            }
        )

        mock_httpx_client.request.side_effect = [
            auth_response,  # Initial auth
            accounts_response,  # Initial accounts
            mock_instrument_response,  # Instrument search
            error_response,  # Error response
        ]

        with patch("httpx.AsyncClient", return_value=mock_httpx_client):
            async with ProjectX("testuser", "test-api-key") as client:
                # Initialize required attributes
                client.api_call_count = 0
                client._opt_instrument_cache = {}
                client._opt_instrument_cache_time = {}
                client._opt_market_data_cache = {}
                client._opt_market_data_cache_time = {}
                client.cache_ttl = 300
                client.last_cache_cleanup = time.time()
                client.cache_hit_count = 0
                client.rate_limiter = RateLimiter(max_requests=100, window_seconds=60)
                await client.authenticate()

                # Should handle error gracefully and return empty dataframe
                bars = await client.get_bars("MGC", days=1, interval=1)
                assert bars.is_empty()

    @pytest.mark.asyncio
    async def test_get_bars_with_different_parameters(
        self,
        mock_httpx_client,
        mock_auth_response,
        mock_instrument_response,
        mock_response,
        mock_bars_data,
    ):
        """Test getting bars with different time parameters."""
        auth_response, accounts_response = mock_auth_response
        daily_bars_response = mock_response(
            json_data={"success": True, "bars": mock_bars_data}
        )
        hourly_bars_response = mock_response(
            json_data={
                "success": True,
                "bars": mock_bars_data,  # Same data but used for hourly bars
            }
        )

        # Define a request counter and a matcher function to handle different types of bar requests
        request_counter = 0

        def request_matcher(**kwargs):
            nonlocal request_counter

            # For bar data requests, check the request structure
            method = kwargs.get("method", "")
            url = kwargs.get("url", "")
            json_data = kwargs.get("json", {})

            if method == "POST" and "/History/retrieveBars" in url:
                unit = json_data.get("unit")

                if unit == 4:  # Daily bars
                    return daily_bars_response
                elif unit == 3:  # Hourly bars
                    return hourly_bars_response

            # For other requests, use sequence
            responses = [
                auth_response,  # Initial auth
                accounts_response,  # Initial accounts
                mock_instrument_response,  # First instrument search
                mock_instrument_response,  # Second instrument search
            ]

            if request_counter < len(responses):
                response = responses[request_counter]
                request_counter += 1
                return response

            # Fallback for any other requests
            return mock_response(json_data={"success": True})

        mock_httpx_client.request.side_effect = request_matcher

        with patch("httpx.AsyncClient", return_value=mock_httpx_client):
            async with ProjectX("testuser", "test-api-key") as client:
                # Initialize required attributes
                client.api_call_count = 0
                client._opt_instrument_cache = {}
                client._opt_instrument_cache_time = {}
                client._opt_market_data_cache = {}
                client._opt_market_data_cache_time = {}
                client.cache_ttl = 300
                client.last_cache_cleanup = time.time()
                client.cache_hit_count = 0
                client.rate_limiter = RateLimiter(max_requests=100, window_seconds=60)
                await client.authenticate()

                # Daily bars
                daily_bars = await client.get_bars("MGC", days=30, interval=1, unit=4)
                assert not daily_bars.is_empty()

                # Hourly bars
                hourly_bars = await client.get_bars("MGC", days=7, interval=1, unit=3)
                assert not hourly_bars.is_empty()

                # Different cache keys should be used
                assert "MGC_30_1_4_True_False" in client._opt_market_data_cache
                assert "MGC_7_1_3_True_False" in client._opt_market_data_cache

    @pytest.mark.asyncio
    async def test_get_bars_with_start_and_end_time(
        self,
        mock_httpx_client,
        mock_auth_response,
        mock_instrument_response,
        mock_bars_response,
    ):
        """Test getting bars with start_time and end_time parameters."""
        auth_response, accounts_response = mock_auth_response
        mock_httpx_client.request.side_effect = [
            auth_response,  # Initial auth
            accounts_response,  # Initial accounts
            mock_instrument_response,  # Instrument search
            mock_bars_response,  # Bars data
        ]

        with patch("httpx.AsyncClient", return_value=mock_httpx_client):
            async with ProjectX("testuser", "test-api-key") as client:
                # Initialize required attributes
                client.api_call_count = 0
                client._opt_instrument_cache = {}
                client._opt_instrument_cache_time = {}
                client._opt_market_data_cache = {}
                client._opt_market_data_cache_time = {}
                client.cache_ttl = 300
                client.last_cache_cleanup = time.time()
                client.cache_hit_count = 0
                client.rate_limiter = RateLimiter(max_requests=100, window_seconds=60)
                await client.authenticate()

                # Test with both start_time and end_time
                start = datetime.datetime(2025, 1, 1, 9, 30)
                end = datetime.datetime(2025, 1, 5, 16, 0)

                bars = await client.get_bars(
                    "MGC", start_time=start, end_time=end, interval=15
                )

                # Verify dataframe structure
                assert not bars.is_empty()
                assert "timestamp" in bars.columns
                assert "open" in bars.columns

                # Should use time-based cache key with market timezone
                # Client uses America/Chicago by default
                market_tz = pytz.timezone("America/Chicago")
                start_tz = market_tz.localize(start)
                end_tz = market_tz.localize(end)
                cache_key = (
                    f"MGC_{start_tz.isoformat()}_{end_tz.isoformat()}_15_2_True_False"
                )
                assert cache_key in client._opt_market_data_cache

    @pytest.mark.asyncio
    async def test_get_bars_with_only_start_time(
        self,
        mock_httpx_client,
        mock_auth_response,
        mock_instrument_response,
        mock_bars_response,
    ):
        """Test getting bars with only start_time parameter."""
        auth_response, accounts_response = mock_auth_response
        mock_httpx_client.request.side_effect = [
            auth_response,  # Initial auth
            accounts_response,  # Initial accounts
            mock_instrument_response,  # Instrument search
            mock_bars_response,  # Bars data
        ]

        with patch("httpx.AsyncClient", return_value=mock_httpx_client):
            async with ProjectX("testuser", "test-api-key") as client:
                # Initialize required attributes
                client.api_call_count = 0
                client._opt_instrument_cache = {}
                client._opt_instrument_cache_time = {}
                client._opt_market_data_cache = {}
                client._opt_market_data_cache_time = {}
                client.cache_ttl = 300
                client.last_cache_cleanup = time.time()
                client.cache_hit_count = 0
                client.rate_limiter = RateLimiter(max_requests=100, window_seconds=60)
                await client.authenticate()

                # Test with only start_time (end_time should default to now)
                start = datetime.datetime(2025, 1, 1, 9, 30)

                bars = await client.get_bars("MGC", start_time=start, interval=5)

                # Verify dataframe structure
                assert not bars.is_empty()
                assert "timestamp" in bars.columns

    @pytest.mark.asyncio
    async def test_get_bars_with_only_end_time(
        self,
        mock_httpx_client,
        mock_auth_response,
        mock_instrument_response,
        mock_bars_response,
    ):
        """Test getting bars with only end_time parameter."""
        auth_response, accounts_response = mock_auth_response
        mock_httpx_client.request.side_effect = [
            auth_response,  # Initial auth
            accounts_response,  # Initial accounts
            mock_instrument_response,  # Instrument search
            mock_bars_response,  # Bars data
        ]

        with patch("httpx.AsyncClient", return_value=mock_httpx_client):
            async with ProjectX("testuser", "test-api-key") as client:
                # Initialize required attributes
                client.api_call_count = 0
                client._opt_instrument_cache = {}
                client._opt_instrument_cache_time = {}
                client._opt_market_data_cache = {}
                client._opt_market_data_cache_time = {}
                client.cache_ttl = 300
                client.last_cache_cleanup = time.time()
                client.cache_hit_count = 0
                client.rate_limiter = RateLimiter(max_requests=100, window_seconds=60)
                await client.authenticate()

                # Test with only end_time (start_time should default to days ago)
                end = datetime.datetime(2025, 1, 5, 16, 0)

                bars = await client.get_bars(
                    "MGC",
                    end_time=end,
                    days=3,  # Should use this for start_time calculation
                    interval=60,
                )

                # Verify dataframe structure
                assert not bars.is_empty()
                assert "timestamp" in bars.columns

    @pytest.mark.asyncio
    async def test_get_bars_with_timezone_aware_times(
        self,
        mock_httpx_client,
        mock_auth_response,
        mock_instrument_response,
        mock_bars_response,
    ):
        """Test getting bars with timezone-aware datetime parameters."""
        auth_response, accounts_response = mock_auth_response
        mock_httpx_client.request.side_effect = [
            auth_response,  # Initial auth
            accounts_response,  # Initial accounts
            mock_instrument_response,  # Instrument search
            mock_bars_response,  # Bars data
        ]

        with patch("httpx.AsyncClient", return_value=mock_httpx_client):
            async with ProjectX("testuser", "test-api-key") as client:
                # Initialize required attributes
                client.api_call_count = 0
                client._opt_instrument_cache = {}
                client._opt_instrument_cache_time = {}
                client._opt_market_data_cache = {}
                client._opt_market_data_cache_time = {}
                client.cache_ttl = 300
                client.last_cache_cleanup = time.time()
                client.cache_hit_count = 0
                client.rate_limiter = RateLimiter(max_requests=100, window_seconds=60)
                await client.authenticate()

                # Test with timezone-aware datetimes
                chicago_tz = pytz.timezone("America/Chicago")
                start = chicago_tz.localize(datetime.datetime(2025, 1, 1, 9, 30))
                end = chicago_tz.localize(datetime.datetime(2025, 1, 5, 16, 0))

                bars = await client.get_bars(
                    "MGC", start_time=start, end_time=end, interval=30
                )

                # Verify dataframe structure
                assert not bars.is_empty()
                assert "timestamp" in bars.columns

                # Cache key should use the same timezone as provided (Chicago)
                cache_key = f"MGC_{start.isoformat()}_{end.isoformat()}_30_2_True_False"
                assert cache_key in client._opt_market_data_cache

    @pytest.mark.asyncio
    async def test_get_bars_time_params_override_days(
        self,
        mock_httpx_client,
        mock_auth_response,
        mock_instrument_response,
        mock_bars_response,
    ):
        """Test that start_time/end_time override the days parameter."""
        auth_response, accounts_response = mock_auth_response
        mock_httpx_client.request.side_effect = [
            auth_response,  # Initial auth
            accounts_response,  # Initial accounts
            mock_instrument_response,  # Instrument search
            mock_bars_response,  # Bars data
        ]

        with patch("httpx.AsyncClient", return_value=mock_httpx_client):
            async with ProjectX("testuser", "test-api-key") as client:
                # Initialize required attributes
                client.api_call_count = 0
                client._opt_instrument_cache = {}
                client._opt_instrument_cache_time = {}
                client._opt_market_data_cache = {}
                client._opt_market_data_cache_time = {}
                client.cache_ttl = 300
                client.last_cache_cleanup = time.time()
                client.cache_hit_count = 0
                client.rate_limiter = RateLimiter(max_requests=100, window_seconds=60)
                await client.authenticate()

                # Test that time params override days
                start = datetime.datetime(2025, 1, 1, 9, 30)
                end = datetime.datetime(2025, 1, 2, 16, 0)

                bars = await client.get_bars(
                    "MGC",
                    days=100,  # This should be ignored
                    start_time=start,
                    end_time=end,
                    interval=15,
                )

                # Verify that the cache key uses the time range, not days
                # Client uses America/Chicago by default
                market_tz = pytz.timezone("America/Chicago")
                start_tz = market_tz.localize(start)
                end_tz = market_tz.localize(end)
                time_based_key = (
                    f"MGC_{start_tz.isoformat()}_{end_tz.isoformat()}_15_2_True_False"
                )
                days_based_key = "MGC_100_15_2_True_False"

                assert time_based_key in client._opt_market_data_cache
                assert days_based_key not in client._opt_market_data_cache
