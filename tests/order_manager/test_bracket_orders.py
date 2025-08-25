"""Tests for BracketOrderMixin (validation and successful flows)."""

from unittest.mock import AsyncMock

import pytest

from project_x_py.exceptions import ProjectXOrderError
from project_x_py.models import BracketOrderResponse, OrderPlaceResponse


@pytest.mark.asyncio
class TestBracketOrderMixin:
    """Unit tests for BracketOrderMixin bracket order placement."""

    @pytest.mark.parametrize(
        "side, entry, stop, target, err",
        [
            (0, 100.0, 101.0, 102.0, "stop loss (101.0) must be below entry (100.0)"),
            (0, 100.0, 99.0, 99.0, "take profit (99.0) must be above entry (100.0)"),
            (1, 100.0, 99.0, 98.0, "stop loss (99.0) must be above entry (100.0)"),
            (1, 100.0, 101.0, 101.0, "take profit (101.0) must be below entry (100.0)"),
        ],
    )
    async def test_bracket_order_validation_fails(self, side, entry, stop, target, err):
        """BracketOrderMixin validates stop/take_profit price relationships."""
        from project_x_py.order_manager.bracket_orders import BracketOrderMixin

        mixin = BracketOrderMixin()
        mixin.place_market_order = AsyncMock()
        mixin.place_limit_order = AsyncMock()
        mixin.place_stop_order = AsyncMock()
        mixin.position_orders = {
            "FOO": {"entry_orders": [], "stop_orders": [], "target_orders": []}
        }
        mixin.stats = {"bracket_orders": 0}
        with pytest.raises(ProjectXOrderError) as exc:
            await mixin.place_bracket_order(
                "FOO", side, 1, entry, stop, target, entry_type="limit"
            )
        assert err in str(exc.value)

    async def test_bracket_order_success_flow(self):
        """Successful bracket order path places all three orders and updates stats/caches."""
        from project_x_py.order_manager.bracket_orders import BracketOrderMixin

        mixin = BracketOrderMixin()
        mixin.place_market_order = AsyncMock(
            return_value=OrderPlaceResponse(
                orderId=1, success=True, errorCode=0, errorMessage=None
            )
        )
        mixin.place_limit_order = AsyncMock(
            side_effect=[
                OrderPlaceResponse(
                    orderId=2, success=True, errorCode=0, errorMessage=None
                ),
                OrderPlaceResponse(
                    orderId=3, success=True, errorCode=0, errorMessage=None
                ),
            ]
        )
        mixin.place_stop_order = AsyncMock(
            return_value=OrderPlaceResponse(
                orderId=4, success=True, errorCode=0, errorMessage=None
            )
        )
        mixin.position_orders = {
            "BAR": {"entry_orders": [], "stop_orders": [], "target_orders": []}
        }
        mixin.stats = {"bracket_orders": 0}
        # Mock the methods that are called from bracket_orders
        mixin._wait_for_order_fill = AsyncMock(return_value=True)
        mixin._link_oco_orders = AsyncMock()

        # Mock the new methods added for race condition fix
        mixin.get_order_by_id = AsyncMock(return_value=None)  # Simulate filled order
        mixin._check_order_fill_status = AsyncMock(
            return_value=(True, 2, 0)
        )  # Fully filled
        mixin._place_protective_orders_with_retry = AsyncMock(
            return_value=(
                OrderPlaceResponse(
                    orderId=4, success=True, errorCode=0, errorMessage=None
                ),
                OrderPlaceResponse(
                    orderId=3, success=True, errorCode=0, errorMessage=None
                ),
            )
        )

        # Create a side effect that updates position_orders
        async def mock_track_order(contract_id, order_id, order_type, account_id=None):
            if contract_id not in mixin.position_orders:
                mixin.position_orders[contract_id] = {
                    "entry_orders": [],
                    "stop_orders": [],
                    "target_orders": [],
                }
            if order_type == "entry":
                mixin.position_orders[contract_id]["entry_orders"].append(order_id)
            elif order_type == "stop":
                mixin.position_orders[contract_id]["stop_orders"].append(order_id)
            elif order_type == "target":
                mixin.position_orders[contract_id]["target_orders"].append(order_id)

        mixin.track_order_for_position = AsyncMock(side_effect=mock_track_order)
        mixin.close_position = AsyncMock()
        mixin.cancel_order = AsyncMock()
        mixin.oco_groups = {}

        # Entry type = limit
        resp = await mixin.place_bracket_order(
            "BAR", 0, 2, 100.0, 99.0, 103.0, entry_type="limit"
        )
        assert isinstance(resp, BracketOrderResponse)
        assert resp.success
        assert resp.entry_order_id == 2
        assert resp.stop_order_id == 4
        assert resp.target_order_id == 3
        assert mixin.position_orders["BAR"]["entry_orders"][-1] == 2
        assert mixin.position_orders["BAR"]["stop_orders"][-1] == 4
        assert mixin.position_orders["BAR"]["target_orders"][-1] == 3
        assert mixin.stats["bracket_orders"] == 1

    async def test_bracket_order_market_entry(self):
        """Test bracket order with market entry order."""
        from project_x_py.order_manager.bracket_orders import BracketOrderMixin

        mixin = BracketOrderMixin()
        mixin.place_market_order = AsyncMock(
            return_value=OrderPlaceResponse(
                orderId=1, success=True, errorCode=0, errorMessage=None
            )
        )
        mixin.place_limit_order = AsyncMock(
            return_value=OrderPlaceResponse(
                orderId=2, success=True, errorCode=0, errorMessage=None
            )
        )
        mixin.place_stop_order = AsyncMock(
            return_value=OrderPlaceResponse(
                orderId=3, success=True, errorCode=0, errorMessage=None
            )
        )
        mixin.position_orders = {
            "MNQ": {"entry_orders": [], "stop_orders": [], "target_orders": []}
        }
        mixin.stats = {"bracket_orders": 0}
        mixin._wait_for_order_fill = AsyncMock(return_value=True)
        mixin._link_oco_orders = AsyncMock()
        mixin.get_order_by_id = AsyncMock(return_value=None)
        mixin._check_order_fill_status = AsyncMock(return_value=(True, 2, 0))
        mixin._place_protective_orders_with_retry = AsyncMock(
            return_value=(mixin.place_stop_order.return_value, mixin.place_limit_order.return_value)
        )
        mixin.track_order_for_position = AsyncMock()
        mixin.oco_groups = {}

        # Market entry - entry_price is ignored for market orders but still needs to be provided
        resp = await mixin.place_bracket_order(
            "MNQ", 0, 1, 17000.0, 16800.0, 17200.0, entry_type="market"
        )

        assert resp.success
        mixin.place_market_order.assert_called_once_with("MNQ", 0, 1, None)

    async def test_bracket_order_entry_fill_failure(self):
        """Test bracket order when entry order fails to fill."""
        from project_x_py.order_manager.bracket_orders import BracketOrderMixin

        mixin = BracketOrderMixin()
        mixin.place_limit_order = AsyncMock(
            return_value=OrderPlaceResponse(
                orderId=1, success=True, errorCode=0, errorMessage=None
            )
        )
        mixin.position_orders = {
            "MNQ": {"entry_orders": [], "stop_orders": [], "target_orders": []}
        }
        mixin.stats = {"bracket_orders": 0}
        mixin._wait_for_order_fill = AsyncMock(return_value=False)  # Fill fails
        mixin.cancel_order = AsyncMock(return_value=True)
        mixin.track_order_for_position = AsyncMock()
        mixin.oco_groups = {}

        with pytest.raises(ProjectXOrderError, match="Entry order failed to fill"):
            await mixin.place_bracket_order(
                "MNQ", 0, 1, 17000.0, 16800.0, 17200.0, entry_type="limit"
            )

        # Should have attempted to cancel the entry order
        mixin.cancel_order.assert_called_once_with(1)

    async def test_bracket_order_protective_orders_failure(self):
        """Test bracket order when protective orders fail."""
        from project_x_py.order_manager.bracket_orders import BracketOrderMixin

        mixin = BracketOrderMixin()
        mixin.place_limit_order = AsyncMock(
            return_value=OrderPlaceResponse(
                orderId=1, success=True, errorCode=0, errorMessage=None
            )
        )
        mixin.position_orders = {
            "MNQ": {"entry_orders": [], "stop_orders": [], "target_orders": []}
        }
        mixin.stats = {"bracket_orders": 0}
        mixin._wait_for_order_fill = AsyncMock(return_value=True)
        mixin.get_order_by_id = AsyncMock(return_value=None)
        mixin._check_order_fill_status = AsyncMock(return_value=(True, 2, 0))
        mixin._place_protective_orders_with_retry = AsyncMock(
            side_effect=ProjectXOrderError("Failed to place protective orders")
        )
        mixin.track_order_for_position = AsyncMock()
        mixin.close_position = AsyncMock()
        mixin.oco_groups = {}

        with pytest.raises(ProjectXOrderError, match="Failed to place protective orders"):
            await mixin.place_bracket_order(
                "MNQ", 0, 1, 17000.0, 16800.0, 17200.0, entry_type="limit"
            )

        # Should have attempted to close the position
        mixin.close_position.assert_called_once_with("MNQ")

    async def test_bracket_order_invalid_entry_type(self):
        """Test bracket order with invalid entry type."""
        from project_x_py.order_manager.bracket_orders import BracketOrderMixin

        mixin = BracketOrderMixin()
        mixin.position_orders = {
            "MNQ": {"entry_orders": [], "stop_orders": [], "target_orders": []}
        }
        mixin.stats = {"bracket_orders": 0}

        with pytest.raises(ProjectXOrderError, match="entry_type must be 'market' or 'limit'"):
            await mixin.place_bracket_order(
                "MNQ", 0, 1, 17000.0, 16800.0, 17200.0, entry_type="invalid"
            )

    async def test_bracket_order_missing_entry_price_for_limit(self):
        """Test bracket order missing entry price for limit order."""
        from project_x_py.order_manager.bracket_orders import BracketOrderMixin

        mixin = BracketOrderMixin()
        mixin.position_orders = {
            "MNQ": {"entry_orders": [], "stop_orders": [], "target_orders": []}
        }
        mixin.stats = {"bracket_orders": 0}

        with pytest.raises(ProjectXOrderError, match="entry_price is required for limit orders"):
            await mixin.place_bracket_order(
                "MNQ", 0, 1, None, 16800.0, 17200.0, entry_type="limit"
            )

    async def test_check_order_fill_status(self):
        """Test order fill status checking."""
        from project_x_py.models import Order
        from project_x_py.order_manager.bracket_orders import BracketOrderMixin

        mixin = BracketOrderMixin()

        # Test fully filled order
        filled_order = Order(
            id=123,
            accountId=12345,
            contractId="MNQ",
            side=0,
            size=2,
            status=2,  # Filled
            filledSize=2,
            remainingSize=0
        )

        is_filled, status, remaining = mixin._check_order_fill_status(filled_order)
        assert is_filled is True
        assert status == 2
        assert remaining == 0

        # Test partially filled order
        partial_order = Order(
            id=124,
            accountId=12345,
            contractId="MNQ",
            side=0,
            size=2,
            status=1,  # Working
            filledSize=1,
            remainingSize=1
        )

        is_filled, status, remaining = mixin._check_order_fill_status(partial_order)
        assert is_filled is False
        assert status == 1
        assert remaining == 1

        # Test cancelled order
        cancelled_order = Order(
            id=125,
            accountId=12345,
            contractId="MNQ",
            side=0,
            size=2,
            status=3,  # Cancelled
            filledSize=0,
            remainingSize=2
        )

        is_filled, status, remaining = mixin._check_order_fill_status(cancelled_order)
        assert is_filled is False
        assert status == 3
        assert remaining == 2

    async def test_place_protective_orders_with_retry_success(self):
        """Test successful protective order placement with retry."""
        from project_x_py.order_manager.bracket_orders import BracketOrderMixin

        mixin = BracketOrderMixin()
        mixin.place_stop_order = AsyncMock(
            return_value=OrderPlaceResponse(
                orderId=2, success=True, errorCode=0, errorMessage=None
            )
        )
        mixin.place_limit_order = AsyncMock(
            return_value=OrderPlaceResponse(
                orderId=3, success=True, errorCode=0, errorMessage=None
            )
        )

        stop_resp, target_resp = await mixin._place_protective_orders_with_retry(
            "MNQ", 1, 2, 16800.0, 17200.0, max_attempts=3
        )

        assert stop_resp.orderId == 2
        assert target_resp.orderId == 3
        assert stop_resp.success
        assert target_resp.success

    async def test_place_protective_orders_with_retry_failure(self):
        """Test protective order placement failure after retries."""
        from project_x_py.order_manager.bracket_orders import BracketOrderMixin

        mixin = BracketOrderMixin()
        mixin.place_stop_order = AsyncMock(
            return_value=OrderPlaceResponse(
                orderId=0, success=False, errorCode=1, errorMessage="Stop order failed"
            )
        )
        mixin.place_limit_order = AsyncMock(
            return_value=OrderPlaceResponse(
                orderId=3, success=True, errorCode=0, errorMessage=None
            )
        )

        with pytest.raises(ProjectXOrderError, match="Failed to place protective orders"):
            await mixin._place_protective_orders_with_retry(
                "MNQ", 1, 2, 16800.0, 17200.0, max_attempts=2
            )

    async def test_place_protective_orders_partial_success(self):
        """Test protective orders with partial success (one succeeds, one fails)."""
        from project_x_py.order_manager.bracket_orders import BracketOrderMixin

        mixin = BracketOrderMixin()
        mixin.place_stop_order = AsyncMock(
            return_value=OrderPlaceResponse(
                orderId=2, success=True, errorCode=0, errorMessage=None
            )
        )
        mixin.place_limit_order = AsyncMock(
            return_value=OrderPlaceResponse(
                orderId=0, success=False, errorCode=1, errorMessage="Target order failed"
            )
        )
        mixin.cancel_order = AsyncMock(return_value=True)

        with pytest.raises(ProjectXOrderError, match="Failed to place protective orders"):
            await mixin._place_protective_orders_with_retry(
                "MNQ", 1, 2, 16800.0, 17200.0, max_attempts=2
            )

        # Should have cancelled the successful stop order
        mixin.cancel_order.assert_called_with(2)

    async def test_validate_bracket_prices_edge_cases(self):
        """Test bracket price validation edge cases."""
        from project_x_py.order_manager.bracket_orders import BracketOrderMixin

        mixin = BracketOrderMixin()

        # Test with very small price differences (should still validate correctly)
        # Buy side: entry=100.0, stop=99.99, target=100.01
        try:
            mixin._validate_bracket_prices(0, 100.0, 99.99, 100.01)
        except ProjectXOrderError:
            pytest.fail("Should not raise error for valid small price differences")

        # Sell side: entry=100.0, stop=100.01, target=99.99
        try:
            mixin._validate_bracket_prices(1, 100.0, 100.01, 99.99)
        except ProjectXOrderError:
            pytest.fail("Should not raise error for valid small price differences")

    async def test_bracket_order_with_account_id(self):
        """Test bracket order with specific account ID."""
        from project_x_py.order_manager.bracket_orders import BracketOrderMixin

        mixin = BracketOrderMixin()
        mixin.place_limit_order = AsyncMock(
            return_value=OrderPlaceResponse(
                orderId=1, success=True, errorCode=0, errorMessage=None
            )
        )
        mixin.position_orders = {
            "MNQ": {"entry_orders": [], "stop_orders": [], "target_orders": []}
        }
        mixin.stats = {"bracket_orders": 0}
        mixin._wait_for_order_fill = AsyncMock(return_value=True)
        mixin._link_oco_orders = AsyncMock()
        mixin.get_order_by_id = AsyncMock(return_value=None)
        mixin._check_order_fill_status = AsyncMock(return_value=(True, 2, 0))
        mixin._place_protective_orders_with_retry = AsyncMock(
            return_value=(
                OrderPlaceResponse(orderId=2, success=True, errorCode=0, errorMessage=None),
                OrderPlaceResponse(orderId=3, success=True, errorCode=0, errorMessage=None)
            )
        )
        mixin.track_order_for_position = AsyncMock()
        mixin.oco_groups = {}

        resp = await mixin.place_bracket_order(
            "MNQ", 0, 1, 17000.0, 16800.0, 17200.0, entry_type="limit", account_id=12345
        )

        assert resp.success
        # Verify account_id was passed to place_limit_order
        mixin.place_limit_order.assert_called_with("MNQ", 0, 1, 17000.0, 12345)
