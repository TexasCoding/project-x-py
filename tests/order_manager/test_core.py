"""Tests for OrderManager core API."""

from unittest.mock import AsyncMock

import pytest

from project_x_py.exceptions import ProjectXOrderError
from project_x_py.models import Order, OrderPlaceResponse


class TestOrderManagerCore:
    """Unit tests for OrderManager core public methods."""

    @pytest.mark.asyncio
    async def test_place_market_order_success(self, order_manager, make_order_response):
        """place_market_order hits /Order/place with correct payload and updates stats."""
        # Patch _make_request to return a success response
        order_manager.project_x._make_request = AsyncMock(
            return_value=make_order_response(42)
        )
        # Should increment orders_placed
        start_count = order_manager.stats["orders_placed"]
        resp = await order_manager.place_market_order("MGC", 0, 2)
        assert isinstance(resp, OrderPlaceResponse)
        assert resp.orderId == 42
        assert order_manager.project_x._make_request.call_count == 1
        call_args = order_manager.project_x._make_request.call_args[1]["data"]
        assert call_args["contractId"] == "MGC"
        assert call_args["type"] == 2
        assert call_args["side"] == 0
        assert call_args["size"] == 2
        assert order_manager.stats["orders_placed"] == start_count + 1

    @pytest.mark.asyncio
    async def test_place_order_error_raises(self, order_manager, make_order_response):
        """place_order raises ProjectXOrderError when API fails."""
        order_manager.project_x._make_request = AsyncMock(
            return_value={"success": False, "errorMessage": "Test error"}
        )
        with pytest.raises(ProjectXOrderError):
            await order_manager.place_order("MGC", 2, 0, 1)

    @pytest.mark.asyncio
    async def test_search_open_orders_populates_cache(
        self, order_manager, make_order_response
    ):
        """search_open_orders converts API dicts to Order objects and populates cache."""
        resp_order = {
            "id": 101,
            "accountId": 12345,
            "contractId": "MGC",
            "creationTimestamp": "2024-01-01T01:00:00Z",
            "updateTimestamp": None,
            "status": 1,
            "type": 1,
            "side": 0,
            "size": 2,
        }
        order_manager.project_x.account_info.id = 12345
        order_manager.project_x._make_request = AsyncMock(
            return_value={"success": True, "orders": [resp_order]}
        )
        orders = await order_manager.search_open_orders()
        assert isinstance(orders[0], Order)
        assert order_manager.tracked_orders[str(resp_order["id"])] == resp_order
        assert order_manager.order_status_cache[str(resp_order["id"])] == 1

    @pytest.mark.asyncio
    async def test_is_order_filled_cache_hit(self, order_manager):
        """is_order_filled returns True from cache and does not call _make_request if cached."""
        order_manager._realtime_enabled = True
        order_manager.order_status_cache["77"] = 2  # 2=Filled
        order_manager.project_x._make_request = AsyncMock()
        result = await order_manager.is_order_filled(77)
        assert result is True
        order_manager.project_x._make_request.assert_not_called()

    @pytest.mark.asyncio
    async def test_is_order_filled_fallback(self, order_manager):
        """is_order_filled falls back to get_order_by_id when not cached."""
        order_manager._realtime_enabled = False
        dummy_order = Order(
            id=55,
            accountId=12345,
            contractId="CL",
            creationTimestamp="2024-01-01T01:00:00Z",
            updateTimestamp=None,
            status=2,
            type=1,
            side=0,
            size=1,
        )
        order_manager.get_order_by_id = AsyncMock(return_value=dummy_order)
        result = await order_manager.is_order_filled(55)
        assert result is True

    @pytest.mark.asyncio
    async def test_cancel_order_success_and_failure(self, order_manager):
        """cancel_order updates caches/stats on success and handles failure."""
        # Setup tracked order
        order_manager.tracked_orders["888"] = {"status": 1}
        order_manager.order_status_cache["888"] = 1
        start = order_manager.stats["orders_cancelled"]
        order_manager.project_x._make_request = AsyncMock(
            return_value={"success": True}
        )
        assert await order_manager.cancel_order(888) is True
        assert order_manager.tracked_orders["888"]["status"] == 3
        assert order_manager.order_status_cache["888"] == 3
        assert order_manager.stats["orders_cancelled"] == start + 1

        order_manager.project_x._make_request = AsyncMock(
            return_value={"success": False, "errorMessage": "fail"}
        )
        with pytest.raises(ProjectXOrderError) as exc_info:
            await order_manager.cancel_order(888)
        assert "Failed to cancel order 888: fail" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_modify_order_success_and_aligns(self, order_manager):
        """modify_order aligns prices, makes API call, returns True on success."""
        dummy_order = Order(
            id=12,
            accountId=12345,
            contractId="MGC",
            creationTimestamp="2024-01-01T01:00:00Z",
            updateTimestamp=None,
            status=1,
            type=1,
            side=0,
            size=1,
        )
        order_manager.get_order_by_id = AsyncMock(return_value=dummy_order)
        order_manager.project_x._make_request = AsyncMock(
            return_value={"success": True}
        )
        assert await order_manager.modify_order(12, limit_price=2000.5) is True

        order_manager.project_x._make_request = AsyncMock(
            return_value={"success": False, "errorMessage": "modification failed"}
        )
        with pytest.raises(ProjectXOrderError) as exc_info:
            await order_manager.modify_order(12, limit_price=2001.5)
        assert "Failed to modify order 12" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_order_statistics(self, order_manager):
        """get_order_statistics returns expected stats."""
        stats = order_manager.get_order_statistics()
        # Check for key statistics fields
        assert "orders_placed" in stats
        assert "orders_filled" in stats
        assert "orders_cancelled" in stats
        assert "fill_rate" in stats
        assert "market_orders" in stats
        assert "limit_orders" in stats
        assert "bracket_orders" in stats

    @pytest.mark.asyncio
    async def test_place_limit_order_success(self, order_manager, make_order_response):
        """place_limit_order hits /Order/place with correct payload."""
        order_manager.project_x._make_request = AsyncMock(
            return_value=make_order_response(43)
        )

        resp = await order_manager.place_limit_order("MNQ", 0, 1, 17000.0)

        assert isinstance(resp, OrderPlaceResponse)
        assert resp.orderId == 43
        call_args = order_manager.project_x._make_request.call_args[1]["data"]
        assert call_args["contractId"] == "MNQ"
        assert call_args["type"] == 1  # Limit order
        assert call_args["side"] == 0
        assert call_args["size"] == 1
        assert call_args["limitPrice"] == 17000.0

    @pytest.mark.asyncio
    async def test_place_stop_order_success(self, order_manager, make_order_response):
        """place_stop_order hits /Order/place with correct payload."""
        order_manager.project_x._make_request = AsyncMock(
            return_value=make_order_response(44)
        )

        resp = await order_manager.place_stop_order("MNQ", 1, 1, 16800.0)

        assert isinstance(resp, OrderPlaceResponse)
        assert resp.orderId == 44
        call_args = order_manager.project_x._make_request.call_args[1]["data"]
        assert call_args["contractId"] == "MNQ"
        assert call_args["type"] == 4  # Stop order (OrderType.STOP = 4)
        assert call_args["side"] == 1
        assert call_args["size"] == 1
        assert call_args["stopPrice"] == 16800.0

    @pytest.mark.asyncio
    async def test_place_order_with_account_id(self, order_manager, make_order_response):
        """place_order includes account_id when provided."""
        order_manager.project_x._make_request = AsyncMock(
            return_value=make_order_response(45)
        )

        resp = await order_manager.place_order("MNQ", 2, 0, 1, account_id=12345)

        call_args = order_manager.project_x._make_request.call_args[1]["data"]
        assert call_args["accountId"] == 12345

    @pytest.mark.asyncio
    async def test_get_order_by_id_success(self, order_manager):
        """get_order_by_id returns Order object on success."""
        order_data = {
            "id": 123,
            "accountId": 12345,
            "contractId": "MNQ",
            "creationTimestamp": "2024-01-01T01:00:00Z",
            "updateTimestamp": None,
            "status": 1,
            "type": 1,
            "side": 0,
            "size": 1,
        }

        # Mock search_open_orders which get_order_by_id uses internally
        order_manager.project_x._make_request = AsyncMock(
            return_value={"success": True, "orders": [order_data]}
        )

        order = await order_manager.get_order_by_id(123)

        assert isinstance(order, Order)
        assert order.id == 123
        assert order.contractId == "MNQ"

        # Should update cache through search_open_orders
        assert order_manager.tracked_orders["123"] == order_data
        assert order_manager.order_status_cache["123"] == 1

    @pytest.mark.asyncio
    async def test_get_order_by_id_not_found(self, order_manager):
        """get_order_by_id returns None when order not found."""
        order_manager.project_x._make_request = AsyncMock(
            return_value={"success": False, "errorMessage": "Order not found"}
        )

        order = await order_manager.get_order_by_id(999)
        assert order is None

    @pytest.mark.asyncio
    async def test_search_open_orders_no_account_id(self, order_manager):
        """search_open_orders uses default account when no ID provided."""
        order_manager.project_x.account_info.id = 12345
        order_manager.project_x._make_request = AsyncMock(
            return_value={"success": True, "orders": []}
        )

        await order_manager.search_open_orders()

        call_args = order_manager.project_x._make_request.call_args[1]["data"]
        assert call_args["accountId"] == 12345

    @pytest.mark.asyncio
    async def test_search_open_orders_with_account_id(self, order_manager):
        """search_open_orders uses provided filters."""
        order_manager.project_x.account_info.id = 12345
        order_manager.project_x._make_request = AsyncMock(
            return_value={"success": True, "orders": []}
        )

        await order_manager.search_open_orders(contract_id="MNQ", side=1)

        call_args = order_manager.project_x._make_request.call_args[1]["data"]
        assert call_args["accountId"] == 12345
        assert call_args["side"] == 1

    @pytest.mark.asyncio
    async def test_search_open_orders_api_error(self, order_manager):
        """search_open_orders handles API errors."""
        order_manager.project_x._make_request = AsyncMock(
            return_value={"success": False, "errorMessage": "API error"}
        )

        with pytest.raises(ProjectXOrderError, match="API error"):
            await order_manager.search_open_orders()

    @pytest.mark.asyncio
    async def test_cancel_order_not_found(self, order_manager):
        """cancel_order handles order not found case."""
        order_manager.project_x._make_request = AsyncMock(
            return_value={"success": False, "errorMessage": "Order not found"}
        )

        with pytest.raises(ProjectXOrderError, match="Failed to cancel order 999: Order not found"):
            await order_manager.cancel_order(999)

    @pytest.mark.asyncio
    async def test_modify_order_not_found(self, order_manager):
        """modify_order handles order not found case."""
        order_manager.get_order_by_id = AsyncMock(return_value=None)

        with pytest.raises(ProjectXOrderError, match="Order not found: 999"):
            await order_manager.modify_order(999, limit_price=17000.0)

    @pytest.mark.asyncio
    async def test_modify_order_no_changes(self, order_manager):
        """modify_order returns True when no changes provided."""
        dummy_order = Order(
            id=123,
            accountId=12345,
            contractId="MNQ",
            creationTimestamp="2024-01-01T01:00:00Z",
            updateTimestamp=None,
            status=1,
            type=1,
            side=0,
            size=1,
        )
        order_manager.get_order_by_id = AsyncMock(return_value=dummy_order)

        # When no changes are provided, modify_order returns True (no-op)
        result = await order_manager.modify_order(123)
        assert result is True

    @pytest.mark.asyncio
    async def test_is_order_filled_not_found(self, order_manager):
        """is_order_filled returns False when order not found."""
        order_manager._realtime_enabled = False
        order_manager.get_order_by_id = AsyncMock(return_value=None)

        result = await order_manager.is_order_filled(999)
        assert result is False

    @pytest.mark.asyncio
    async def test_is_order_filled_various_statuses(self, order_manager):
        """is_order_filled correctly identifies filled vs non-filled statuses."""
        order_manager._realtime_enabled = True

        # Test filled status
        order_manager.order_status_cache["100"] = 2  # Filled
        assert await order_manager.is_order_filled(100) is True

        # Test working status
        order_manager.order_status_cache["101"] = 1  # Working
        assert await order_manager.is_order_filled(101) is False

        # Test cancelled status
        order_manager.order_status_cache["102"] = 3  # Cancelled
        assert await order_manager.is_order_filled(102) is False

        # Test rejected status
        order_manager.order_status_cache["103"] = 5  # Rejected
        assert await order_manager.is_order_filled(103) is False

    @pytest.mark.asyncio
    async def test_initialize_with_realtime_client(self, order_manager):
        """Test initialize method with realtime client."""
        mock_realtime_client = AsyncMock()
        mock_realtime_client.add_callback = AsyncMock()

        await order_manager.initialize(mock_realtime_client)

        assert order_manager.realtime_client == mock_realtime_client
        assert order_manager._realtime_enabled is True

        # Should have set up callbacks
        mock_realtime_client.add_callback.assert_called()

    @pytest.mark.asyncio
    async def test_initialize_without_realtime_client(self, order_manager):
        """Test initialize method without realtime client."""
        await order_manager.initialize(None)

        assert order_manager.realtime_client is None
        assert order_manager._realtime_enabled is False

    def test_get_order_statistics_calculations(self, order_manager):
        """Test order statistics calculations."""
        # Set up test statistics
        order_manager.stats.update({
            "orders_placed": 100,
            "orders_filled": 80,
            "orders_cancelled": 15,
            "market_orders": 30,
            "limit_orders": 70,
            "bracket_orders": 25
        })

        stats = order_manager.get_order_statistics()

        assert stats["orders_placed"] == 100
        assert stats["orders_filled"] == 80
        assert stats["orders_cancelled"] == 15
        assert stats["fill_rate"] == 0.8  # 80/100
        assert stats["market_orders"] == 30
        assert stats["limit_orders"] == 70
        assert stats["bracket_orders"] == 25

    def test_get_order_statistics_zero_division(self, order_manager):
        """Test order statistics with zero orders placed."""
        order_manager.stats.update({
            "orders_placed": 0,
            "orders_filled": 0,
            "orders_cancelled": 0
        })

        stats = order_manager.get_order_statistics()

        assert stats["fill_rate"] == 0.0  # Should handle division by zero
