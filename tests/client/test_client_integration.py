"""Integration tests for the ProjectX client."""

import pytest

from project_x_py.exceptions import (
    ProjectXAuthenticationError,
    ProjectXDataError,
)
from project_x_py.models import Instrument


class TestClientIntegration:
    """Integration tests for the ProjectX client."""

    @pytest.mark.asyncio
    async def test_caching_workflow(self, initialized_client):
        """Test workflow with caching."""
        client = initialized_client

        # Create a mock instrument
        instrument = Instrument(
            id="123",
            name="Micro Gold Futures",
            description="Micro Gold Futures Contract",
            tickSize=0.10,
            tickValue=10.0,
            activeContract=True,
        )

        # First, we add it to cache
        client.cache_instrument("MGC", instrument)

        # Then we retrieve it from cache
        cached_instrument = client.get_cached_instrument("MGC")
        assert cached_instrument is not None
        assert cached_instrument.id == "123"
        assert cached_instrument.name == "Micro Gold Futures"

        # Cache hit count should be 1
        assert client.cache_hit_count == 1

        # Clear caches
        client.clear_all_caches()

        # Cache should be empty now
        empty_instrument = client.get_cached_instrument("MGC")
        assert empty_instrument is None

    @pytest.mark.asyncio
    async def test_auth_market_data_workflow(
        self,
        initialized_client,
        mock_auth_response,
        mock_instrument_response,
        mock_bars_response,
    ):
        """Test authentication and market data workflow."""
        client = initialized_client
        auth_response, accounts_response = mock_auth_response

        # Setup response sequence
        client._client.request.side_effect = [
            auth_response,  # Authentication
            accounts_response,  # Account info
            mock_instrument_response,  # Instrument lookup
            mock_bars_response,  # Market data bars
        ]

        # Step 1: Authenticate
        await client.authenticate()
        assert client._authenticated is True
        assert client.session_token == auth_response.json()["token"]
        assert client.account_info is not None

        # Step 2: Get instrument data
        instrument = await client.get_instrument("MGC")
        assert instrument is not None
        assert "MGC" in client._opt_instrument_cache

        # Step 3: Get market data
        bars = await client.get_bars("MGC", days=5, interval=5)
        assert not bars.is_empty()
        assert "timestamp" in bars.columns
        assert "open" in bars.columns

        # Step 4: Verify cache is populated
        cache_key = "MGC_5_5_2_True"
        assert cache_key in client._opt_market_data_cache

    @pytest.mark.asyncio
    async def test_trading_workflow(
        self,
        initialized_client,
        mock_auth_response,
        mock_positions_response,
        mock_trades_response,
    ):
        """Test trading workflow with positions and trades."""
        client = initialized_client
        auth_response, accounts_response = mock_auth_response

        # Setup response sequence
        client._client.request.side_effect = [
            auth_response,  # Authentication
            accounts_response,  # Account info
            mock_positions_response,  # Positions
            mock_trades_response,  # Trades
        ]

        # Step 1: Authenticate
        await client.authenticate()
        assert client._authenticated is True

        # Step 2: Get positions
        positions = await client.search_open_positions()
        assert len(positions) == 2
        assert positions[0].contractId == "MGC"
        assert positions[1].contractId == "MNQ"

        # Step 3: Get trade history
        trades = await client.search_trades()
        assert len(trades) == 2
        assert trades[0].contractId == "MGC"
        assert trades[1].contractId == "MNQ"

    @pytest.mark.asyncio
    async def test_auth_error_handling(self, initialized_client, mock_response):
        """Test authentication error handling."""
        client = initialized_client

        # Setup auth failure response
        client._client.request.return_value = mock_response(
            status_code=401,
            json_data={"success": False, "message": "Authentication failed"},
        )

        # Test auth failure
        with pytest.raises(ProjectXAuthenticationError):
            await client.authenticate()

    @pytest.mark.asyncio
    async def test_instrument_not_found(
        self, initialized_client, mock_auth_response, mock_response
    ):
        """Test instrument not found error handling."""
        client = initialized_client
        auth_response, accounts_response = mock_auth_response

        # Setup response sequence
        client._client.request.side_effect = [
            auth_response,  # Authentication succeeds
            accounts_response,  # Account info succeeds
            mock_response(
                status_code=404,
                json_data={"success": False, "message": "Instrument not found"},
            ),
        ]

        # Authenticate first
        await client.authenticate()
        assert client._authenticated is True

        # Test instrument not found error
        with pytest.raises(ProjectXDataError):
            await client.get_instrument("INVALID")
