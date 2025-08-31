"""Tests for error scenarios and edge cases across the SDK."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import pytz

from project_x_py.exceptions import (
    ProjectXDataError,
    ProjectXOrderError,
    ProjectXRateLimitError,
)


@pytest.mark.asyncio
class TestErrorScenarios:
    """Test various error scenarios and edge cases."""

    async def test_authentication_token_expiry_during_operation(self):
        """Test handling of token expiry during a long-running operation."""
        from project_x_py import ProjectX

        client = ProjectX(api_key="test", username="test")
        client._authenticated = True
        client.session_token = "expired_token"
        client.token_expiry = datetime.now(pytz.UTC) - timedelta(minutes=1)

        # Mock the HTTP client
        client._client = MagicMock()

        # First call returns 401, then successful after re-auth
        client._client.request = AsyncMock(
            side_effect=[
                MagicMock(status_code=401),  # Token expired
                MagicMock(
                    status_code=200,
                    json=lambda: {"token": "new_token", "expiresIn": 3600},
                ),  # Re-auth
                MagicMock(
                    status_code=200,
                    json=lambda: {
                        "success": True,
                        "accounts": [
                            {
                                "id": 1,
                                "name": "Test",
                                "balance": 100000,
                                "canTrade": True,
                                "isVisible": True,
                                "simulated": True,
                            }
                        ],
                    },
                ),  # Get accounts
                MagicMock(
                    status_code=200, json=lambda: {"success": True, "data": []}
                ),  # Original request retry
            ]
        )

        # Should handle token refresh transparently
        result = await client._make_request("GET", "/some/endpoint")
        assert result["success"] is True
        assert client.session_token == "new_token"

    async def test_network_timeout_with_retry(self):
        """Test network timeout handling with automatic retry."""
        from project_x_py import ProjectX

        client = ProjectX(api_key="test", username="test")
        client._authenticated = True
        client._client = MagicMock()

        # Simulate timeout then success
        client._client.request = AsyncMock(
            side_effect=[
                httpx.TimeoutException("Request timed out"),
                httpx.TimeoutException("Request timed out"),
                MagicMock(status_code=200, json=lambda: {"success": True}),
            ]
        )

        result = await client._make_request("GET", "/test/endpoint")
        assert result["success"] is True
        assert client._client.request.call_count == 3

    async def test_rate_limit_with_backoff(self):
        """Test rate limit handling with exponential backoff."""
        from project_x_py import ProjectX

        client = ProjectX(api_key="test", username="test")
        client._authenticated = True
        client._client = MagicMock()

        # Mock rate limit response
        client._client.request = AsyncMock(
            return_value=MagicMock(
                status_code=429,
                headers={"Retry-After": "2"},
            )
        )

        with pytest.raises(ProjectXRateLimitError) as exc_info:
            await client._make_request("GET", "/test/endpoint")

        assert "rate limit" in str(exc_info.value).lower()

    async def test_concurrent_position_updates(self):
        """Test handling of concurrent position updates."""
        from project_x_py.position_manager import PositionManager

        mock_client = MagicMock()
        mock_realtime = MagicMock()

        pm = PositionManager(mock_client, mock_realtime)

        # Simulate concurrent position updates
        async def update1():
            await pm._process_position_data(
                {
                    "contractId": "MGC",
                    "size": 5,
                    "type": 1,
                    "averagePrice": 1900.0,
                }
            )

        async def update2():
            await pm._process_position_data(
                {
                    "contractId": "MGC",
                    "size": 3,
                    "type": 1,
                    "averagePrice": 1905.0,
                }
            )

        # Run concurrently
        import asyncio

        await asyncio.gather(update1(), update2())

        # Should have the latest update
        assert "MGC" in pm.tracked_positions
        # One of the updates should win (race condition handled)
        assert pm.tracked_positions["MGC"]["size"] in [3, 5]

    async def test_websocket_reconnection_with_state_recovery(self):
        """Test WebSocket reconnection with state recovery."""
        from project_x_py.realtime import ProjectXRealtimeClient

        client = ProjectXRealtimeClient("test_token", "12345")

        # Mock connection
        with patch("project_x_py.realtime.connection_management.HubConnectionBuilder"):
            # Initial connection
            await client.connect()

            # Subscribe to some data
            client._market_subscriptions = {"MGC", "NQ"}
            client._user_subscriptions = {"orders", "positions"}

            # Simulate disconnect
            client._connected = False

            # Reconnect should restore subscriptions
            await client.connect()

            # Subscriptions should be maintained
            assert "MGC" in client._market_subscriptions
            assert "orders" in client._user_subscriptions

    async def test_order_validation_edge_cases(self):
        """Test order validation with edge cases."""
        from project_x_py.order_manager import OrderManager

        mock_client = MagicMock()
        mock_client.account_info = MagicMock(id=12345)
        mock_realtime = MagicMock()

        om = OrderManager(mock_client, mock_realtime)

        # Test with None values
        with pytest.raises(ProjectXOrderError):
            await om.place_order(None, 2, 0, 1)

        # Test with negative size
        with pytest.raises(ProjectXOrderError):
            await om.place_order("MGC", 2, 0, -1)

        # Test with invalid order type
        with pytest.raises(ProjectXOrderError):
            await om.place_order("MGC", 999, 0, 1)

    async def test_data_corruption_handling(self):
        """Test handling of corrupted data from API."""
        from project_x_py import ProjectX

        client = ProjectX(api_key="test", username="test")
        client._authenticated = True
        client._client = MagicMock()

        # Return corrupted JSON
        client._client.request = AsyncMock(
            return_value=MagicMock(
                status_code=200,
                json=MagicMock(side_effect=ValueError("Invalid JSON")),
            )
        )

        with pytest.raises(ProjectXDataError):
            await client._make_request("GET", "/test/endpoint")

    async def test_memory_cleanup_on_disconnect(self):
        """Test that memory is properly cleaned up on disconnect."""
        from project_x_py.realtime_data_manager import RealtimeDataManager

        mock_client = MagicMock()
        mock_realtime = MagicMock()

        dm = RealtimeDataManager("MGC", mock_client, mock_realtime)

        # Add some data
        dm.bars = {"1min": [{"timestamp": "2024-01-01", "close": 100}] * 1000}
        dm.ticks = [{"price": 100}] * 1000
        dm.dom_data = {"bids": [], "asks": []}

        # Cleanup
        await dm.cleanup()

        # Data should be cleared
        assert len(dm.bars["1min"]) == 0
        assert len(dm.ticks) == 0
        assert dm.dom_data == {"bids": [], "asks": []}

    async def test_partial_fill_handling(self):
        """Test handling of partial order fills."""
        from project_x_py.order_manager import OrderManager

        mock_client = MagicMock()
        mock_realtime = MagicMock()

        om = OrderManager(mock_client, mock_realtime)

        # Place order
        om.tracked_orders["123"] = {
            "id": 123,
            "size": 10,
            "filled": 0,
            "status": 1,  # Working
        }

        # Process partial fill
        await om._process_order_update(
            {
                "id": 123,
                "filled": 3,
                "status": 1,  # Still working
            }
        )

        assert om.tracked_orders["123"]["filled"] == 3
        assert om.tracked_orders["123"]["status"] == 1

        # Process complete fill
        await om._process_order_update(
            {
                "id": 123,
                "filled": 10,
                "status": 2,  # Filled
            }
        )

        assert om.tracked_orders["123"]["filled"] == 10
        assert om.tracked_orders["123"]["status"] == 2

    async def test_position_risk_calculation_with_no_price(self):
        """Test position risk calculation when price data is unavailable."""
        from project_x_py.position_manager import PositionManager

        mock_client = MagicMock()
        mock_realtime = MagicMock()

        pm = PositionManager(mock_client, mock_realtime)

        # Position without current price
        position = MagicMock(
            contractId="MGC",
            size=5,
            averagePrice=1900.0,
            type=1,
        )

        # Should handle missing price gracefully
        result = await pm.calculate_position_pnl(position)

        assert result["unrealized_pnl"] == 0.0
        assert result["error"] == "No current price available"
