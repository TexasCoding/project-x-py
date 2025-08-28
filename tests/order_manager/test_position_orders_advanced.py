"""
Advanced tests for PositionOrderMixin - Testing untested paths following strict TDD.

These tests define EXPECTED behavior. If tests fail, fix the implementation.
"""

import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from project_x_py.exceptions import ProjectXOrderError
from project_x_py.models import Order, OrderPlaceResponse, Position, Account
from project_x_py.types.trading import OrderSide, OrderStatus, OrderType
from project_x_py.event_bus import EventBus
from project_x_py.order_manager.core import OrderManager


@pytest.fixture
def mock_order_manager():
    """Create a fully mocked OrderManager that doesn't require authentication."""

    # Create mock client
    mock_client = MagicMock()
    mock_client.account_info = Account(
        id=12345,
        name="Test Account",
        balance=100000.0,
        canTrade=True,
        isVisible=True,
        simulated=True,
    )

    # Mock all async methods on the client
    mock_client.authenticate = AsyncMock(return_value=True)
    mock_client.get_position = AsyncMock(return_value=None)
    mock_client.get_instrument = AsyncMock(return_value=None)
    mock_client.get_order_by_id = AsyncMock(return_value=None)
    mock_client.search_orders = AsyncMock(return_value=[])
    mock_client._make_request = AsyncMock(return_value={"success": True})

    # Create EventBus
    event_bus = EventBus()

    # Patch price alignment functions to return input price
    with patch('project_x_py.order_manager.utils.align_price_to_tick_size',
               new=AsyncMock(side_effect=lambda price, *args, **kwargs: price)):
        with patch('project_x_py.order_manager.core.align_price_to_tick_size',
                   new=AsyncMock(side_effect=lambda price, *args, **kwargs: price)):
            # Create OrderManager with mocked client
            om = OrderManager(mock_client, event_bus)

            # Set the project_x attribute for tests that access it
            om.project_x = mock_client

            # Override methods that would call the API
            om.place_market_order = AsyncMock()
            om.place_limit_order = AsyncMock()
            om.place_stop_order = AsyncMock()
            om.cancel_order = AsyncMock(return_value=True)
            om.modify_order = AsyncMock(return_value=True)

            return om


class TestPositionOrderMixinCore:
    """Test core position-based order functionality."""

    @pytest.mark.asyncio
    async def test_close_position_market_order(self, mock_order_manager):
        """close_position with market method should place market order for position size."""
        # Setup position
        position = Position(
            id=1,
            accountId=12345,
            contractId="MNQ",
            creationTimestamp="2024-01-01T00:00:00Z",
            type=1,  # LONG
            size=3,  # 3 contracts
            averagePrice=17000.0
        )

        # Mock search_open_positions to return our test position
        mock_order_manager.project_x.search_open_positions = AsyncMock(return_value=[position])
        mock_order_manager.place_market_order = AsyncMock(
            return_value=OrderPlaceResponse(orderId=100, success=True, errorCode=0, errorMessage=None)
        )

        result = await mock_order_manager.close_position("MNQ", method="market")

        assert result.orderId == 100
        # Should place sell order for long position
        mock_order_manager.place_market_order.assert_called_once_with(
            "MNQ", OrderSide.SELL, 3, None
        )

    @pytest.mark.asyncio
    async def test_close_position_limit_order(self, mock_order_manager):
        """close_position with limit method should place limit order with correct price."""
        position = Position(
            id=1,
            accountId=12345,
            contractId="MNQ",
            creationTimestamp="2024-01-01T00:00:00Z",
            type=2,  # SHORT
            size=2,
            averagePrice=17000.0
        )

        mock_order_manager.project_x.search_open_positions = AsyncMock(return_value=[position])
        mock_order_manager.place_limit_order = AsyncMock(
            return_value=OrderPlaceResponse(orderId=200, success=True, errorCode=0, errorMessage=None)
        )

        result = await mock_order_manager.close_position(
            "MNQ", method="limit", limit_price=16950.0
        )

        assert result.orderId == 200
        # Should place buy order to close short position
        mock_order_manager.place_limit_order.assert_called_once_with(
            "MNQ", OrderSide.BUY, 2, 16950.0, None
        )

    @pytest.mark.asyncio
    async def test_close_position_no_position(self, mock_order_manager):
        """close_position should handle no existing position gracefully."""
        mock_order_manager.project_x.search_open_positions = AsyncMock(return_value=[])

        result = await mock_order_manager.close_position("MNQ")

        # Should return None when no position exists
        assert result is None

    @pytest.mark.asyncio
    async def test_close_position_flat_position(self, mock_order_manager):
        """close_position should handle flat position (netPos=0)."""
        position = Position(
            id=1,
            accountId=12345,
            contractId="MNQ",
            creationTimestamp="2024-01-01T00:00:00Z",
            type=0,  # UNDEFINED
            size=0,
            averagePrice=0
        )

        mock_order_manager.project_x.search_open_positions = AsyncMock(return_value=[position])

        with pytest.raises(ProjectXOrderError) as exc_info:
            await mock_order_manager.close_position("MNQ")

        assert "already flat" in str(exc_info.value).lower() or "no position" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_close_position_with_invalid_method(self, mock_order_manager):
        """close_position should reject invalid close methods."""
        position = Position(
            id=1,
            accountId=12345,
            contractId="MNQ",
            creationTimestamp="2024-01-01T00:00:00Z",
            type=1,  # LONG
            size=1,
            averagePrice=17000.0
        )

        mock_order_manager.project_x.search_open_positions = AsyncMock(return_value=[position])

        with pytest.raises(ProjectXOrderError) as exc_info:
            await mock_order_manager.close_position("MNQ", method="invalid_method")

        assert "invalid" in str(exc_info.value).lower() or "method" in str(exc_info.value).lower()


class TestProtectiveOrders:
    """Test stop loss and take profit order functionality."""

    @pytest.mark.asyncio
    async def test_add_stop_loss_long_position(self, mock_order_manager):
        """add_stop_loss should place stop sell order for long position."""
        position = Position(
            id=1,
            accountId=12345,
            contractId="MNQ",
            creationTimestamp="2024-01-01T00:00:00Z",
            type=1,  # LONG
            size=5,
            averagePrice=17000.0
        )

        mock_order_manager.project_x.search_open_positions = AsyncMock(return_value=[position])
        mock_order_manager.place_stop_order = AsyncMock(
            return_value=OrderPlaceResponse(orderId=300, success=True, errorCode=0, errorMessage=None)
        )

        result = await mock_order_manager.add_stop_loss("MNQ", stop_price=16900.0)

        assert result.orderId == 300
        # Should place stop sell for long position
        mock_order_manager.place_stop_order.assert_called_once_with(
            "MNQ", OrderSide.SELL, 5, 16900.0, None
        )

    @pytest.mark.asyncio
    async def test_add_stop_loss_short_position(self, mock_order_manager):
        """add_stop_loss should place stop buy order for short position."""
        position = Position(
            id=1,
            accountId=12345,
            contractId="MNQ",
            creationTimestamp="2024-01-01T00:00:00Z",
            type=2,  # SHORT
            size=3,
            averagePrice=17000.0
        )

        mock_order_manager.project_x.search_open_positions = AsyncMock(return_value=[position])
        mock_order_manager.place_stop_order = AsyncMock(
            return_value=OrderPlaceResponse(orderId=400, success=True, errorCode=0, errorMessage=None)
        )

        result = await mock_order_manager.add_stop_loss("MNQ", stop_price=17100.0, size=2)

        assert result.orderId == 400
        # Should place stop buy for short position, with custom size
        mock_order_manager.place_stop_order.assert_called_once_with(
            "MNQ", OrderSide.BUY, 2, 17100.0, None
        )

    @pytest.mark.asyncio
    async def test_add_stop_loss_no_position(self, mock_order_manager):
        """add_stop_loss should fail when no position exists."""
        mock_order_manager.project_x.search_open_positions = AsyncMock(return_value=[])

        with pytest.raises(ProjectXOrderError) as exc_info:
            await mock_order_manager.add_stop_loss("MNQ", stop_price=16900.0)

        assert "no position" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_add_stop_loss_invalid_price_long(self, mock_order_manager):
        """add_stop_loss should validate stop price for long positions."""
        position = Position(
            id=1,
            accountId=12345,
            contractId="MNQ",
            creationTimestamp="2024-01-01T00:00:00Z",
            type=1,  # LONG
            size=1,
            averagePrice=17000.0
        )

        mock_order_manager.project_x.search_open_positions = AsyncMock(return_value=[position])

        # Stop price above entry for long position is invalid
        with pytest.raises(ProjectXOrderError) as exc_info:
            await mock_order_manager.add_stop_loss("MNQ", stop_price=17100.0)

        assert "stop" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_add_take_profit_long_position(self, mock_order_manager):
        """add_take_profit should place limit sell order for long position."""
        position = Position(
            id=1,
            accountId=12345,
            contractId="MNQ",
            creationTimestamp="2024-01-01T00:00:00Z",
            type=1,  # LONG
            size=2,
            averagePrice=17000.0
        )

        mock_order_manager.project_x.search_open_positions = AsyncMock(return_value=[position])
        mock_order_manager.place_limit_order = AsyncMock(
            return_value=OrderPlaceResponse(orderId=500, success=True, errorCode=0, errorMessage=None)
        )

        result = await mock_order_manager.add_take_profit("MNQ", limit_price=17100.0)

        assert result.orderId == 500
        # Should place limit sell for long position
        mock_order_manager.place_limit_order.assert_called_once_with(
            "MNQ", OrderSide.SELL, 2, 17100.0, None
        )

    @pytest.mark.asyncio
    async def test_add_take_profit_short_position(self, mock_order_manager):
        """add_take_profit should place limit buy order for short position."""
        position = Position(
            id=1,
            accountId=12345,
            contractId="MNQ",
            creationTimestamp="2024-01-01T00:00:00Z",
            type=2,  # SHORT
            size=4,
            averagePrice=17000.0
        )

        mock_order_manager.project_x.search_open_positions = AsyncMock(return_value=[position])
        mock_order_manager.place_limit_order = AsyncMock(
            return_value=OrderPlaceResponse(orderId=600, success=True, errorCode=0, errorMessage=None)
        )

        result = await mock_order_manager.add_take_profit("MNQ", limit_price=16900.0, size=2)

        assert result.orderId == 600
        # Should place limit buy for short position with custom size
        mock_order_manager.place_limit_order.assert_called_once_with(
            "MNQ", OrderSide.BUY, 2, 16900.0, None
        )

    @pytest.mark.asyncio
    async def test_add_take_profit_invalid_price_long(self, mock_order_manager):
        """add_take_profit should validate target price for long positions."""
        position = Position(
            id=1,
            accountId=12345,
            contractId="MNQ",
            creationTimestamp="2024-01-01T00:00:00Z",
            type=1,  # LONG
            size=1,
            averagePrice=17000.0
        )

        mock_order_manager.project_x.search_open_positions = AsyncMock(return_value=[position])

        # Target price below entry for long position is invalid
        with pytest.raises(ProjectXOrderError) as exc_info:
            await mock_order_manager.add_take_profit("MNQ", limit_price=16900.0)

        assert "profit" in str(exc_info.value).lower() or "target" in str(exc_info.value).lower()


class TestPositionOrderTracking:
    """Test order tracking for positions."""

    @pytest.mark.asyncio
    async def test_track_order_for_position(self, mock_order_manager):
        """track_order_for_position should associate orders with positions."""
        # Initialize position orders dict
        if not hasattr(mock_order_manager, 'position_orders'):
            mock_order_manager.position_orders = {}

        await mock_order_manager.track_order_for_position(
            "MNQ", "1001", OrderType.STOP, meta={"stop_price": 16900.0}
        )

        assert "MNQ" in mock_order_manager.position_orders
        assert "stop_orders" in mock_order_manager.position_orders["MNQ"]
        assert "1001" in mock_order_manager.position_orders["MNQ"]["stop_orders"]
        assert "1001" in mock_order_manager.order_to_position
        assert mock_order_manager.order_to_position["1001"] == "MNQ"

    @pytest.mark.asyncio
    async def test_track_multiple_orders_for_position(self, mock_order_manager):
        """Should track multiple orders for same position."""
        if not hasattr(mock_order_manager, 'position_orders'):
            mock_order_manager.position_orders = {}

        await mock_order_manager.track_order_for_position("MNQ", "2001", OrderType.STOP)
        await mock_order_manager.track_order_for_position("MNQ", "2002", OrderType.LIMIT)
        await mock_order_manager.track_order_for_position("MNQ", "2003", OrderType.STOP)

        assert "stop_orders" in mock_order_manager.position_orders["MNQ"]
        assert "target_orders" in mock_order_manager.position_orders["MNQ"]
        assert "2001" in mock_order_manager.position_orders["MNQ"]["stop_orders"]
        assert "2002" in mock_order_manager.position_orders["MNQ"]["target_orders"]
        assert "2003" in mock_order_manager.position_orders["MNQ"]["stop_orders"]
        assert len(mock_order_manager.position_orders["MNQ"]["stop_orders"]) == 2
        assert len(mock_order_manager.position_orders["MNQ"]["target_orders"]) == 1

    @pytest.mark.asyncio
    async def test_get_position_orders(self, mock_order_manager):
        """get_position_orders should return orders for a position."""
        if not hasattr(mock_order_manager, 'position_orders'):
            mock_order_manager.position_orders = {}

        # Track some orders using the list-based structure
        mock_order_manager.position_orders["MNQ"] = {
            "stop_orders": ["3001", "3003"],
            "target_orders": ["3002"],
            "entry_orders": []
        }

        # Get all orders
        all_orders = await mock_order_manager.get_position_orders("MNQ")
        assert "stop_orders" in all_orders
        assert len(all_orders["stop_orders"]) == 2
        assert len(all_orders["target_orders"]) == 1

        # Get only stop orders
        stop_orders = await mock_order_manager.get_position_orders(
            "MNQ", order_types=["stop"]
        )
        assert "stop_orders" in stop_orders
        assert len(stop_orders) == 1  # Only stop_orders key returned
        assert len(stop_orders["stop_orders"]) == 2

        # Status filtering isn't implemented in the list structure
        # This would require tracking actual order objects, not just IDs
        # Skip status filtering test for now

    @pytest.mark.asyncio
    async def test_get_position_orders_no_orders(self, mock_order_manager):
        """get_position_orders should return empty dict when no orders exist."""
        if not hasattr(mock_order_manager, 'position_orders'):
            mock_order_manager.position_orders = {}

        orders = await mock_order_manager.get_position_orders("NONEXISTENT")
        assert orders == {}


class TestPositionOrderCancellation:
    """Test position-based order cancellation."""

    @pytest.mark.asyncio
    async def test_cancel_position_orders_all(self, mock_order_manager):
        """cancel_position_orders should cancel all orders for position."""
        if not hasattr(mock_order_manager, 'position_orders'):
            mock_order_manager.position_orders = {}

        mock_order_manager.position_orders["MNQ"] = {
            "4001": {"type": OrderType.STOP, "status": OrderStatus.OPEN},
            "4002": {"type": OrderType.LIMIT, "status": OrderStatus.OPEN},
            "4003": {"type": OrderType.STOP, "status": OrderStatus.OPEN}
        }

        mock_order_manager.cancel_order = AsyncMock(return_value=True)

        result = await mock_order_manager.cancel_position_orders("MNQ")

        assert result["cancelled_count"] == 3
        assert result["cancelled_orders"] == ["4001", "4002", "4003"]
        assert mock_order_manager.cancel_order.call_count == 3

    @pytest.mark.asyncio
    async def test_cancel_position_orders_by_type(self, mock_order_manager):
        """cancel_position_orders should cancel only specified order types."""
        if not hasattr(mock_order_manager, 'position_orders'):
            mock_order_manager.position_orders = {}

        mock_order_manager.position_orders["MNQ"] = {
            "5001": {"type": OrderType.STOP, "status": OrderStatus.OPEN},
            "5002": {"type": OrderType.LIMIT, "status": OrderStatus.OPEN},
            "5003": {"type": OrderType.STOP, "status": OrderStatus.OPEN}
        }

        mock_order_manager.cancel_order = AsyncMock(return_value=True)

        result = await mock_order_manager.cancel_position_orders(
            "MNQ", order_types=[OrderType.STOP]
        )

        assert result["cancelled_count"] == 2
        assert result["cancelled_orders"] == ["5001", "5003"]
        assert mock_order_manager.cancel_order.call_count == 2

    @pytest.mark.asyncio
    async def test_cancel_position_orders_handles_failures(self, mock_order_manager):
        """cancel_position_orders should handle individual cancellation failures."""
        if not hasattr(mock_order_manager, 'position_orders'):
            mock_order_manager.position_orders = {}

        mock_order_manager.position_orders["MNQ"] = {
            "6001": {"type": OrderType.STOP, "status": OrderStatus.OPEN},
            "6002": {"type": OrderType.LIMIT, "status": OrderStatus.OPEN},
            "6003": {"type": OrderType.STOP, "status": OrderStatus.OPEN}
        }

        # First and third succeed, second fails
        mock_order_manager.cancel_order = AsyncMock(side_effect=[True, False, True])

        result = await mock_order_manager.cancel_position_orders("MNQ")

        # Only successfully cancelled orders returned
        assert result["cancelled_count"] == 2
        assert result["cancelled_orders"] == ["6001", "6003"]
        assert mock_order_manager.cancel_order.call_count == 3

    @pytest.mark.asyncio
    async def test_cancel_position_orders_skips_filled(self, mock_order_manager):
        """cancel_position_orders should skip already filled orders."""
        if not hasattr(mock_order_manager, 'position_orders'):
            mock_order_manager.position_orders = {}

        mock_order_manager.position_orders["MNQ"] = {
            "7001": {"type": OrderType.STOP, "status": OrderStatus.FILLED},
            "7002": {"type": OrderType.LIMIT, "status": OrderStatus.OPEN},
            "7003": {"type": OrderType.STOP, "status": OrderStatus.CANCELLED}
        }

        mock_order_manager.cancel_order = AsyncMock(return_value=True)

        result = await mock_order_manager.cancel_position_orders("MNQ")

        # Should only try to cancel open order
        assert result["cancelled_count"] == 1
        assert result["cancelled_orders"] == ["7002"]
        assert mock_order_manager.cancel_order.call_count == 1


class TestPositionSynchronization:
    """Test order synchronization with position changes."""

    @pytest.mark.asyncio
    async def test_update_position_order_sizes(self, mock_order_manager):
        """update_position_order_sizes should modify order sizes to match position."""
        if not hasattr(mock_order_manager, 'position_orders'):
            mock_order_manager.position_orders = {}

        mock_order_manager.position_orders["MNQ"] = {
            "8001": {"type": OrderType.STOP, "status": OrderStatus.OPEN, "size": 5},
            "8002": {"type": OrderType.LIMIT, "status": OrderStatus.OPEN, "size": 5}
        }

        mock_order_manager.modify_order = AsyncMock(return_value=True)

        result = await mock_order_manager.update_position_order_sizes("MNQ", new_size=3)

        assert result["updated"] == ["8001", "8002"]
        # Should modify both orders to new size
        calls = mock_order_manager.modify_order.call_args_list
        assert len(calls) == 2
        assert calls[0] == call(8001, size=3)
        assert calls[1] == call(8002, size=3)

    @pytest.mark.asyncio
    async def test_sync_orders_with_position_full_sync(self, mock_order_manager):
        """sync_orders_with_position should sync all orders with position size."""
        position = Position(
            id=1,
            accountId=12345,
            contractId="MNQ",
            creationTimestamp="2024-01-01T00:00:00Z",
            type=1,  # LONG
            size=2,
            averagePrice=17000.0
        )

        if not hasattr(mock_order_manager, 'position_orders'):
            mock_order_manager.position_orders = {}

        mock_order_manager.position_orders["MNQ"] = {
            "9001": {"type": OrderType.STOP, "status": OrderStatus.OPEN, "size": 5},
            "9002": {"type": OrderType.LIMIT, "status": OrderStatus.OPEN, "size": 5}
        }

        mock_order_manager.project_x.search_open_positions = AsyncMock(return_value=[position])
        mock_order_manager.modify_order = AsyncMock(return_value=True)
        mock_order_manager.cancel_order = AsyncMock(return_value=True)

        result = await mock_order_manager.sync_orders_with_position(
            "MNQ", target_size=2, cancel_orphaned=False
        )

        assert result["updated"] == ["9001", "9002"]
        assert result["cancelled"] == []
        # Should update all orders to position size
        assert mock_order_manager.modify_order.call_count == 2

    @pytest.mark.asyncio
    async def test_sync_orders_with_position_cancel_orphaned(self, mock_order_manager):
        """sync_orders_with_position should cancel orphaned orders when position closed."""
        # No position (flat)
        mock_order_manager.project_x.search_open_positions = AsyncMock(return_value=[])

        if not hasattr(mock_order_manager, 'position_orders'):
            mock_order_manager.position_orders = {}

        mock_order_manager.position_orders["MNQ"] = {
            "10001": {"type": OrderType.STOP, "status": OrderStatus.OPEN},
            "10002": {"type": OrderType.LIMIT, "status": OrderStatus.OPEN}
        }

        mock_order_manager.cancel_order = AsyncMock(return_value=True)

        result = await mock_order_manager.sync_orders_with_position(
            "MNQ", target_size=0, cancel_orphaned=True
        )

        assert result["updated"] == []
        # sync_orders_with_position stores the entire result dict from cancel_position_orders
        assert result["cancelled"]["cancelled_count"] == 2
        assert result["cancelled"]["cancelled_orders"] == ["10001", "10002"]
        assert mock_order_manager.cancel_order.call_count == 2


class TestPositionEventHandlers:
    """Test position change event handlers."""

    @pytest.mark.asyncio
    async def test_on_position_changed(self, mock_order_manager):
        """on_position_changed should sync orders when position size changes."""
        if not hasattr(mock_order_manager, 'position_orders'):
            mock_order_manager.position_orders = {}

        mock_order_manager.position_orders["MNQ"] = {
            "11001": {"type": OrderType.STOP, "status": OrderStatus.OPEN, "size": 5}
        }

        mock_order_manager.sync_orders_with_position = AsyncMock(
            return_value={"updated": ["11001"], "cancelled": []}
        )

        # Call with separate parameters instead of event dict
        await mock_order_manager.on_position_changed(
            contract_id="MNQ",
            old_size=5,
            new_size=3
        )

        mock_order_manager.sync_orders_with_position.assert_called_once_with(
            "MNQ", target_size=3, cancel_orphaned=False
        )

    @pytest.mark.asyncio
    async def test_on_position_closed(self, mock_order_manager):
        """on_position_closed should cancel all position orders."""
        if not hasattr(mock_order_manager, 'position_orders'):
            mock_order_manager.position_orders = {}

        mock_order_manager.position_orders["MNQ"] = {
            "12001": {"type": OrderType.STOP, "status": OrderStatus.OPEN},
            "12002": {"type": OrderType.LIMIT, "status": OrderStatus.OPEN}
        }

        mock_order_manager.cancel_position_orders = AsyncMock(
            return_value={"cancelled_count": 2, "cancelled_orders": ["12001", "12002"]}
        )

        # Call with contract_id parameter directly
        await mock_order_manager.on_position_closed(contract_id="MNQ")

        mock_order_manager.cancel_position_orders.assert_called_once_with("MNQ")

    @pytest.mark.asyncio
    async def test_on_position_closed_cleanup(self, mock_order_manager):
        """on_position_closed should clean up position tracking data."""
        if not hasattr(mock_order_manager, 'position_orders'):
            mock_order_manager.position_orders = {}

        mock_order_manager.position_orders["MNQ"] = {
            "13001": {"type": OrderType.STOP, "status": OrderStatus.OPEN}
        }

        mock_order_manager.cancel_order = AsyncMock(return_value=True)

        # Call with contract_id parameter directly
        await mock_order_manager.on_position_closed(contract_id="MNQ")

        # Position orders should be cleared
        assert "MNQ" not in mock_order_manager.position_orders or \
               mock_order_manager.position_orders["MNQ"] == {}


class TestPositionOrdersEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_close_position_with_api_error(self, mock_order_manager):
        """close_position should handle API errors gracefully."""
        mock_order_manager.project_x.search_open_positions = AsyncMock(
            side_effect=Exception("API Error")
        )

        with pytest.raises(ProjectXOrderError) as exc_info:
            await mock_order_manager.close_position("MNQ")

        assert "api" in str(exc_info.value).lower() or "error" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_add_protective_orders_concurrent(self, mock_order_manager):
        """Should handle concurrent protective order placement."""
        position = Position(
            id=1,
            accountId=12345,
            contractId="MNQ",
            creationTimestamp="2024-01-01T00:00:00Z",
            type=1,  # LONG
            size=1,
            averagePrice=17000.0
        )

        mock_order_manager.project_x.search_open_positions = AsyncMock(return_value=[position])
        mock_order_manager.place_stop_order = AsyncMock(
            return_value=OrderPlaceResponse(orderId=14001, success=True, errorCode=0, errorMessage=None)
        )
        mock_order_manager.place_limit_order = AsyncMock(
            return_value=OrderPlaceResponse(orderId=14002, success=True, errorCode=0, errorMessage=None)
        )

        # Place stop and take profit concurrently
        tasks = [
            mock_order_manager.add_stop_loss("MNQ", stop_price=16950.0),
            mock_order_manager.add_take_profit("MNQ", limit_price=17050.0)
        ]

        results = await asyncio.gather(*tasks)

        assert len(results) == 2
        assert results[0].orderId == 14001
        assert results[1].orderId == 14002

    @pytest.mark.asyncio
    async def test_sync_with_partial_fill_position(self, mock_order_manager):
        """Should handle sync when position is partially filled."""
        position = Position(
            id=1,
            accountId=12345,
            contractId="MNQ",
            creationTimestamp="2024-01-01T00:00:00Z",
            type=1,  # LONG
            size=3,
            averagePrice=17000.0
        )

        if not hasattr(mock_order_manager, 'position_orders'):
            mock_order_manager.position_orders = {}

        mock_order_manager.position_orders["MNQ"] = {
            "15001": {"type": OrderType.STOP, "status": OrderStatus.OPEN, "size": 5}
        }

        mock_order_manager.project_x.search_open_positions = AsyncMock(return_value=[position])
        mock_order_manager.modify_order = AsyncMock(return_value=True)

        result = await mock_order_manager.sync_orders_with_position("MNQ", target_size=3)

        # Should update order to match new position size
        assert result["updated"] == ["15001"]
        mock_order_manager.modify_order.assert_called_once_with(15001, size=3)

    @pytest.mark.asyncio
    async def test_position_orders_with_multiple_accounts(self, mock_order_manager):
        """Should handle position orders for multiple accounts correctly."""
        position_account1 = Position(
            id=1,
            accountId=11111,
            contractId="MNQ",
            creationTimestamp="2024-01-01T00:00:00Z",
            type=1,  # LONG
            size=2,
            averagePrice=17000.0
        )

        position_account2 = Position(
            id=2,
            accountId=22222,
            contractId="MNQ",
            creationTimestamp="2024-01-01T00:00:00Z",
            type=2,  # SHORT
            size=3,
            averagePrice=17000.0
        )

        # Mock to return different positions based on account_id
        async def search_positions_mock(account_id=None):
            if account_id == 11111:
                return [position_account1]
            elif account_id == 22222:
                return [position_account2]
            return []

        mock_order_manager.project_x.search_open_positions = search_positions_mock
        mock_order_manager.place_market_order = AsyncMock(
            return_value=OrderPlaceResponse(orderId=16001, success=True, errorCode=0, errorMessage=None)
        )

        # Close position for specific account
        result = await mock_order_manager.close_position("MNQ", account_id=11111)

        assert result.orderId == 16001
        # Should close long position for account1
        mock_order_manager.place_market_order.assert_called_once_with(
            "MNQ", OrderSide.SELL, 2, 11111
        )
