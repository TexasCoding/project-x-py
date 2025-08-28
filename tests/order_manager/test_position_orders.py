"""Tests for PositionOrderMixin helpers and tracking."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from project_x_py.exceptions import ProjectXOrderError
from project_x_py.models import OrderPlaceResponse
from project_x_py.order_manager.position_orders import PositionOrderMixin


@pytest.mark.asyncio
class TestPositionOrderMixin:
    """Unit tests for PositionOrderMixin helpers (track, untrack, add_stop_loss, add_take_profit)."""

    async def test_track_and_untrack_order(self):
        """track_order_for_position and untrack_order mutate position_orders/order_to_position correctly."""
        mixin = PositionOrderMixin()
        mixin.order_lock = asyncio.Lock()
        mixin.position_orders = {}
        mixin.order_to_position = {}

        await mixin.track_order_for_position("BAZ", 1001, "entry")
        assert 1001 in mixin.order_to_position
        assert mixin.order_to_position[1001] == "BAZ"
        assert mixin.position_orders["BAZ"]["entry_orders"] == [1001]

        mixin.untrack_order(1001)
        assert 1001 not in mixin.order_to_position
        assert mixin.position_orders["BAZ"]["entry_orders"] == []

    async def test_add_stop_loss_success(self):
        """add_stop_loss places stop order and tracks it."""
        mixin = PositionOrderMixin()
        mixin.project_x = MagicMock()
        position = MagicMock(contractId="QWE", size=2)
        mixin.project_x.search_open_positions = AsyncMock(return_value=[position])
        mixin.place_stop_order = AsyncMock(
            return_value=OrderPlaceResponse(
                orderId=201, success=True, errorCode=0, errorMessage=None
            )
        )
        mixin.track_order_for_position = AsyncMock()
        resp = await mixin.add_stop_loss("QWE", 99.0)
        assert resp.orderId == 201
        mixin.track_order_for_position.assert_awaited_once_with(
            "QWE", 201, "stop", None
        )

    async def test_add_stop_loss_no_position(self):
        """add_stop_loss raises error if no position found."""
        mixin = PositionOrderMixin()
        mixin.project_x = MagicMock()
        mixin.project_x.search_open_positions = AsyncMock(return_value=[])
        mixin.place_stop_order = AsyncMock()
        with pytest.raises(ProjectXOrderError) as exc_info:
            await mixin.add_stop_loss("AAA", 100.0)
        assert "no position" in str(exc_info.value).lower()

    async def test_add_take_profit_success(self):
        """add_take_profit places limit order and tracks it."""
        mixin = PositionOrderMixin()
        mixin.project_x = MagicMock()
        position = MagicMock(contractId="ZXC", size=3)
        mixin.project_x.search_open_positions = AsyncMock(return_value=[position])
        mixin.place_limit_order = AsyncMock(
            return_value=OrderPlaceResponse(
                orderId=301, success=True, errorCode=0, errorMessage=None
            )
        )
        mixin.track_order_for_position = AsyncMock()
        resp = await mixin.add_take_profit("ZXC", 120.0)
        assert resp.orderId == 301
        mixin.track_order_for_position.assert_awaited_once_with(
            "ZXC", 301, "target", None
        )

    async def test_add_take_profit_no_position(self):
        """add_take_profit raises error if no position found."""
        mixin = PositionOrderMixin()
        mixin.project_x = MagicMock()
        mixin.project_x.search_open_positions = AsyncMock(return_value=[])
        mixin.place_limit_order = AsyncMock()
        with pytest.raises(ProjectXOrderError) as exc_info:
            await mixin.add_take_profit("TUV", 55.0)
        assert "no position" in str(exc_info.value).lower()

    async def test_track_order_for_position_multiple_types(self):
        """Test tracking multiple order types for same position."""
        mixin = PositionOrderMixin()
        mixin.order_lock = asyncio.Lock()
        mixin.position_orders = {}
        mixin.order_to_position = {}

        # Track entry order
        await mixin.track_order_for_position("MNQ", 100, "entry")

        # Track stop order
        await mixin.track_order_for_position("MNQ", 101, "stop")

        # Track target order
        await mixin.track_order_for_position("MNQ", 102, "target")

        assert mixin.position_orders["MNQ"]["entry_orders"] == [100]
        assert mixin.position_orders["MNQ"]["stop_orders"] == [101]
        assert mixin.position_orders["MNQ"]["target_orders"] == [102]

        assert mixin.order_to_position[100] == "MNQ"
        assert mixin.order_to_position[101] == "MNQ"
        assert mixin.order_to_position[102] == "MNQ"

    async def test_track_order_for_position_with_account_id(self):
        """Test tracking order with specific account ID."""
        mixin = PositionOrderMixin()
        mixin.order_lock = asyncio.Lock()
        mixin.position_orders = {}
        mixin.order_to_position = {}

        await mixin.track_order_for_position("MNQ", 100, "entry", account_id=12345)

        assert mixin.position_orders["MNQ"]["entry_orders"] == [100]
        assert mixin.order_to_position[100] == "MNQ"

    async def test_track_order_for_position_existing_contract(self):
        """Test tracking order for contract that already exists."""
        mixin = PositionOrderMixin()
        mixin.order_lock = asyncio.Lock()
        mixin.position_orders = {
            "MNQ": {"entry_orders": [99], "stop_orders": [], "target_orders": []}
        }
        mixin.order_to_position = {99: "MNQ"}

        await mixin.track_order_for_position("MNQ", 100, "entry")

        assert mixin.position_orders["MNQ"]["entry_orders"] == [99, 100]
        assert mixin.order_to_position[100] == "MNQ"

    def test_untrack_order_not_found(self):
        """Test untracking order that doesn't exist."""
        mixin = PositionOrderMixin()
        mixin.position_orders = {}
        mixin.order_to_position = {}

        # Should not raise exception
        mixin.untrack_order(999)

    def test_untrack_order_removes_from_position_orders(self):
        """Test untracking order removes it from position_orders structure."""
        mixin = PositionOrderMixin()
        mixin.position_orders = {
            "MNQ": {"entry_orders": [100, 101], "stop_orders": [102], "target_orders": []}
        }
        mixin.order_to_position = {100: "MNQ", 101: "MNQ", 102: "MNQ"}

        mixin.untrack_order(100)

        assert mixin.position_orders["MNQ"]["entry_orders"] == [101]
        assert 100 not in mixin.order_to_position
        assert 101 in mixin.order_to_position  # Others remain
        assert 102 in mixin.order_to_position

    async def test_add_stop_loss_with_account_id(self):
        """Test add_stop_loss with specific account ID."""
        mixin = PositionOrderMixin()
        mixin.project_x = MagicMock()
        position = MagicMock(contractId="MNQ", size=1, type=1)  # Long position (PositionType.LONG=1)
        mixin.project_x.search_open_positions = AsyncMock(return_value=[position])
        mixin.place_stop_order = AsyncMock(
            return_value=OrderPlaceResponse(
                orderId=200, success=True, errorCode=0, errorMessage=None
            )
        )
        mixin.track_order_for_position = AsyncMock()

        resp = await mixin.add_stop_loss("MNQ", 16800.0, account_id=12345)

        assert resp.orderId == 200
        # Should place sell stop for long position
        mixin.place_stop_order.assert_called_once_with("MNQ", 1, 1, 16800.0, 12345)
        mixin.track_order_for_position.assert_awaited_once_with(
            "MNQ", 200, "stop", 12345
        )

    async def test_add_stop_loss_short_position(self):
        """Test add_stop_loss for short position (opposite side)."""
        mixin = PositionOrderMixin()
        mixin.project_x = MagicMock()
        position = MagicMock(contractId="MNQ", size=-1, type=2)  # Short position (PositionType.SHORT=2)
        mixin.project_x.search_open_positions = AsyncMock(return_value=[position])
        mixin.place_stop_order = AsyncMock(
            return_value=OrderPlaceResponse(
                orderId=201, success=True, errorCode=0, errorMessage=None
            )
        )
        mixin.track_order_for_position = AsyncMock()

        resp = await mixin.add_stop_loss("MNQ", 17200.0)

        # Should place buy stop for short position
        mixin.place_stop_order.assert_called_once_with("MNQ", 0, 1, 17200.0, None)

    async def test_add_take_profit_with_account_id(self):
        """Test add_take_profit with specific account ID."""
        mixin = PositionOrderMixin()
        mixin.project_x = MagicMock()
        position = MagicMock(contractId="MNQ", size=1, type=1)  # Long position (PositionType.LONG=1)
        mixin.project_x.search_open_positions = AsyncMock(return_value=[position])
        mixin.place_limit_order = AsyncMock(
            return_value=OrderPlaceResponse(
                orderId=300, success=True, errorCode=0, errorMessage=None
            )
        )
        mixin.track_order_for_position = AsyncMock()

        resp = await mixin.add_take_profit("MNQ", 17200.0, account_id=12345)

        assert resp.orderId == 300
        # Should place sell limit for long position
        mixin.place_limit_order.assert_called_once_with("MNQ", 1, 1, 17200.0, 12345)
        mixin.track_order_for_position.assert_awaited_once_with(
            "MNQ", 300, "target", 12345
        )

    async def test_add_take_profit_short_position(self):
        """Test add_take_profit for short position (opposite side)."""
        mixin = PositionOrderMixin()
        mixin.project_x = MagicMock()
        position = MagicMock(contractId="MNQ", size=-1, type=2)  # Short position (PositionType.SHORT=2)
        mixin.project_x.search_open_positions = AsyncMock(return_value=[position])
        mixin.place_limit_order = AsyncMock(
            return_value=OrderPlaceResponse(
                orderId=301, success=True, errorCode=0, errorMessage=None
            )
        )
        mixin.track_order_for_position = AsyncMock()

        resp = await mixin.add_take_profit("MNQ", 16800.0)

        # Should place buy limit for short position
        mixin.place_limit_order.assert_called_once_with("MNQ", 0, 1, 16800.0, None)

    async def test_close_position_success(self):
        """Test close_position method success."""
        mixin = PositionOrderMixin()
        mixin.project_x = MagicMock()

        position = MagicMock(contractId="MNQ", size=2, type=1)  # Long 2 contracts (PositionType.LONG=1)
        mixin.project_x.search_open_positions = AsyncMock(return_value=[position])
        mixin.place_market_order = AsyncMock(
            return_value=OrderPlaceResponse(
                orderId=400, success=True, errorCode=0, errorMessage=None
            )
        )

        resp = await mixin.close_position("MNQ")

        assert resp.orderId == 400
        # Should place market sell order to close long position
        mixin.place_market_order.assert_called_once_with("MNQ", 1, 2, None)

    async def test_close_position_short(self):
        """Test close_position for short position."""
        mixin = PositionOrderMixin()
        mixin.project_x = MagicMock()

        position = MagicMock(contractId="MNQ", size=-1, type=2)  # Short 1 contract (PositionType.SHORT=2)
        mixin.project_x.search_open_positions = AsyncMock(return_value=[position])
        mixin.place_market_order = AsyncMock(
            return_value=OrderPlaceResponse(
                orderId=401, success=True, errorCode=0, errorMessage=None
            )
        )

        resp = await mixin.close_position("MNQ")

        # Should place market buy order to close short position
        mixin.place_market_order.assert_called_once_with("MNQ", 0, 1, None)

    async def test_close_position_not_found(self):
        """Test close_position when no position exists."""
        mixin = PositionOrderMixin()
        mixin.project_x = MagicMock()
        mixin.project_x.search_open_positions = AsyncMock(return_value=[])

        resp = await mixin.close_position("NONEXISTENT")

        assert resp is None

    async def test_close_position_with_account_id(self):
        """Test close_position with specific account ID."""
        mixin = PositionOrderMixin()
        mixin.project_x = MagicMock()

        position = MagicMock(contractId="MNQ", size=1, type=1)  # Long position
        mixin.project_x.search_open_positions = AsyncMock(return_value=[position])
        mixin.place_market_order = AsyncMock(
            return_value=OrderPlaceResponse(
                orderId=402, success=True, errorCode=0, errorMessage=None
            )
        )

        resp = await mixin.close_position("MNQ", account_id=12345)

        assert resp.orderId == 402
        mixin.place_market_order.assert_called_once_with("MNQ", 1, 1, 12345)
