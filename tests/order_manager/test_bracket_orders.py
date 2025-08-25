"""Unit tests for bracket order functionality."""

import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from project_x_py.exceptions import ProjectXOrderError
from project_x_py.models import OrderPlaceResponse
from project_x_py.order_manager.bracket_orders import BracketOrderMixin
from project_x_py.order_manager.order_types import OrderTypesMixin


class TestBracketOrderImplementation(BracketOrderMixin, OrderTypesMixin):
    """Test implementation that combines both mixins like the real OrderManager."""

    def __init__(self):
        self.client = MagicMock()
        self.realtime_client = MagicMock()
        # Mock the base place_order method that OrderTypesMixin delegates to
        self.place_order = AsyncMock()
        # Mock other required methods
        self.cancel_order = AsyncMock()
        self._wait_for_order_fill = AsyncMock()
        self._check_order_fill_status = AsyncMock()
        self.get_order_status = AsyncMock()
        self.close_position = AsyncMock()  # Add close_position method for emergency closure
        # Additional attributes that may be accessed
        self.stats = {"bracket_orders": 0}  # Initialize with the key that will be accessed
        self.position_manager = None
        self.recovery_manager = None


class TestBracketOrderMixin:
    """Test suite for BracketOrderMixin."""

    @pytest.fixture
    def mock_order_manager(self):
        """Create a mock order manager with bracket order mixin."""
        return TestBracketOrderImplementation()

    @pytest.mark.asyncio
    async def test_bracket_order_validation_fails(self, mock_order_manager):
        """Test that bracket order validation catches invalid parameters."""
        mixin = mock_order_manager

        # Test buy order with stop loss above entry
        with pytest.raises(
            ProjectXOrderError,
            match=r"Buy order stop loss \(101\.0\) must be below entry \(100\.0\)"
        ):
            await mixin.place_bracket_order(
                contract_id="MNQ",
                side=0,  # Buy
                size=1,
                entry_type="limit",
                entry_price=100.0,
                stop_loss_price=101.0,  # Invalid: above entry for buy
                take_profit_price=105.0,
            )

    @pytest.mark.asyncio
    async def test_bracket_order_success_flow(self, mock_order_manager):
        """Test successful bracket order placement."""
        mixin = mock_order_manager

        # Configure mocks for successful flow
        # The place_order method will be called for market/limit orders via OrderTypesMixin
        mixin.place_order.side_effect = [
            # Entry order (limit)
            OrderPlaceResponse(orderId=1, success=True, errorCode=0, errorMessage=None),
            # Stop order
            OrderPlaceResponse(orderId=2, success=True, errorCode=0, errorMessage=None),
            # Target order (limit)
            OrderPlaceResponse(orderId=3, success=True, errorCode=0, errorMessage=None),
        ]

        mixin._wait_for_order_fill.return_value = True
        mixin._check_order_fill_status.return_value = (True, 1, 0)  # Fully filled

        result = await mixin.place_bracket_order(
            contract_id="MNQ",
            side=0,  # Buy
            size=1,
            entry_type="limit",
            entry_price=100.0,
            stop_loss_price=95.0,
            take_profit_price=105.0,
        )

        assert result.success is True
        assert result.entry_order_id == 1
        assert result.stop_order_id == 2
        assert result.target_order_id == 3

    @pytest.mark.asyncio
    async def test_bracket_order_market_entry(self, mock_order_manager):
        """Test bracket order with market entry."""
        mixin = mock_order_manager

        # Configure mocks
        mixin.place_order.side_effect = [
            # Entry order (market)
            OrderPlaceResponse(orderId=10, success=True, errorCode=0, errorMessage=None),
            # Stop order
            OrderPlaceResponse(orderId=11, success=True, errorCode=0, errorMessage=None),
            # Target order
            OrderPlaceResponse(orderId=12, success=True, errorCode=0, errorMessage=None),
        ]

        mixin._wait_for_order_fill.return_value = True
        mixin._check_order_fill_status.return_value = (True, 2, 0)

        result = await mixin.place_bracket_order(
            contract_id="ES",
            side=1,  # Sell
            size=2,
            entry_type="market",
            entry_price=4500.0,  # Market orders ignore this but it's required by signature
            stop_loss_price=4550.0,
            take_profit_price=4450.0,
        )

        assert result.success is True
        assert result.entry_order_id == 10

    @pytest.mark.asyncio
    async def test_bracket_order_entry_fill_failure(self, mock_order_manager):
        """Test bracket order when entry order fails to fill."""
        mixin = mock_order_manager

        # Configure mocks for entry failure
        mixin.place_order.return_value = OrderPlaceResponse(
            orderId=100, success=True, errorCode=0, errorMessage=None
        )

        mixin._wait_for_order_fill.return_value = False
        mixin._check_order_fill_status.return_value = (False, 0, 1)  # Not filled

        with pytest.raises(
            ProjectXOrderError,
            match=r"did not fill within timeout"
        ):
            await mixin.place_bracket_order(
                contract_id="NQ",
                side=0,
                size=1,
                entry_type="limit",
                entry_price=15000.0,
                stop_loss_price=14950.0,
                take_profit_price=15100.0,
            )

    @pytest.mark.asyncio
    async def test_bracket_order_protective_orders_failure(self, mock_order_manager):
        """Test bracket order when protective orders fail."""
        mixin = mock_order_manager

        # Configure mocks - entry succeeds but stop order fails
        mixin.place_order.side_effect = [
            # Entry order succeeds
            OrderPlaceResponse(orderId=1, success=True, errorCode=0, errorMessage=None),
            # Stop order fails
            OrderPlaceResponse(orderId=2, success=False, errorCode=1, errorMessage="Stop order failed"),
        ]

        mixin._wait_for_order_fill.return_value = True
        mixin._check_order_fill_status.return_value = (True, 1, 0)

        with pytest.raises(
            ProjectXOrderError,
            match=r"unprotected position"
        ):
            await mixin.place_bracket_order(
                contract_id="MNQ",
                side=0,
                size=1,
                entry_type="limit",
                entry_price=100.0,
                stop_loss_price=95.0,
                take_profit_price=105.0,
            )

    @pytest.mark.asyncio
    async def test_bracket_order_invalid_entry_type(self, mock_order_manager):
        """Test bracket order should validate entry type."""
        mixin = mock_order_manager

        # Mock _check_order_fill_status to return empty tuple when called
        mixin._check_order_fill_status.return_value = (False, 0, 0)

        # CORRECT BEHAVIOR: Should raise error for invalid entry types
        with pytest.raises(
            ProjectXOrderError,
            match=r"Invalid entry_type.*Must be 'market' or 'limit'"
        ):
            await mixin.place_bracket_order(
                contract_id="MNQ",
                side=0,
                size=1,
                entry_type="stop",  # Invalid - should only accept 'limit' or 'market'
                entry_price=100.0,
                stop_loss_price=95.0,
                take_profit_price=105.0,
            )

    @pytest.mark.asyncio
    async def test_bracket_order_missing_entry_price_for_limit(self, mock_order_manager):
        """Test bracket order should validate entry price for limit orders."""
        mixin = mock_order_manager

        # CORRECT BEHAVIOR: Should validate and raise proper error for None entry_price
        with pytest.raises(
            ProjectXOrderError,
            match=r"entry_price is required for limit orders"
        ):
            await mixin.place_bracket_order(
                contract_id="MNQ",
                side=0,
                size=1,
                entry_type="limit",
                entry_price=None,  # Should be validated before Decimal conversion
                stop_loss_price=95.0,
                take_profit_price=105.0,
            )

    @pytest.mark.asyncio
    async def test_bracket_order_with_account_id(self, mock_order_manager):
        """Test bracket order with specific account ID."""
        mixin = mock_order_manager

        # Configure mocks
        mixin.place_order.side_effect = [
            OrderPlaceResponse(orderId=1, success=True, errorCode=0, errorMessage=None),
            OrderPlaceResponse(orderId=2, success=True, errorCode=0, errorMessage=None),
            OrderPlaceResponse(orderId=3, success=True, errorCode=0, errorMessage=None),
        ]

        mixin._wait_for_order_fill.return_value = True
        mixin._check_order_fill_status.return_value = (True, 1, 0)

        result = await mixin.place_bracket_order(
            contract_id="MNQ",
            side=0,
            size=1,
            entry_type="limit",
            entry_price=100.0,
            stop_loss_price=95.0,
            take_profit_price=105.0,
            account_id=12345,
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_bracket_order_partial_fill(self, mock_order_manager):
        """Test bracket order handles partial fills correctly."""
        mixin = mock_order_manager

        # Configure mocks for partial fill scenario
        mixin.place_order.side_effect = [
            # Entry order
            OrderPlaceResponse(orderId=1, success=True, errorCode=0, errorMessage=None),
            # Stop order (for partial size)
            OrderPlaceResponse(orderId=2, success=True, errorCode=0, errorMessage=None),
            # Target order (for partial size)
            OrderPlaceResponse(orderId=3, success=True, errorCode=0, errorMessage=None),
        ]

        mixin._wait_for_order_fill.return_value = True
        # Partial fill: 3 out of 5 contracts filled
        mixin._check_order_fill_status.return_value = (False, 3, 2)

        result = await mixin.place_bracket_order(
            contract_id="ES",
            side=0,
            size=5,
            entry_type="limit",
            entry_price=4500.0,
            stop_loss_price=4480.0,
            take_profit_price=4520.0,
        )

        assert result.success is True
        # Verify cancel was called for remaining portion
        mixin.cancel_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_bracket_order_sell_validation(self, mock_order_manager):
        """Test bracket order validation for sell orders."""
        mixin = mock_order_manager

        # Test sell order with stop loss below entry (should fail)
        with pytest.raises(
            ProjectXOrderError,
            match=r"Sell order stop loss \(95\.0\) must be above entry \(100\.0\)"
        ):
            await mixin.place_bracket_order(
                contract_id="MNQ",
                side=1,  # Sell
                size=1,
                entry_type="limit",
                entry_price=100.0,
                stop_loss_price=95.0,  # Invalid: below entry for sell
                take_profit_price=90.0,
            )

    @pytest.mark.asyncio
    async def test_bracket_order_with_recovery_manager(self, mock_order_manager):
        """Test bracket order should use recovery manager for transaction semantics."""
        mixin = mock_order_manager

        # Import OrderReference for proper mocking
        from project_x_py.order_manager.error_recovery import OrderReference

        # Create mock recovery manager
        recovery_manager = MagicMock()

        # Mock start_operation to return a RecoveryOperation-like object
        mock_operation = MagicMock()
        mock_operation.id = "op-123"
        recovery_manager.start_operation = AsyncMock(return_value=mock_operation)

        # Mock add_order_to_operation to return OrderReference objects
        mock_order_ref = OrderReference()
        mock_order_ref.order_id = 1
        recovery_manager.add_order_to_operation = AsyncMock(return_value=mock_order_ref)

        # All these methods need to be AsyncMock since they're awaited
        recovery_manager.record_order_success = AsyncMock()
        recovery_manager.record_order_failure = AsyncMock()
        recovery_manager.complete_operation = AsyncMock(return_value=True)
        recovery_manager.add_oco_pair = AsyncMock()
        recovery_manager.add_position_tracking = AsyncMock()
        recovery_manager.force_rollback_operation = AsyncMock()

        # Configure order mocks
        mixin.place_order.side_effect = [
            OrderPlaceResponse(orderId=1, success=True, errorCode=0, errorMessage=None),
            OrderPlaceResponse(orderId=2, success=True, errorCode=0, errorMessage=None),
            OrderPlaceResponse(orderId=3, success=True, errorCode=0, errorMessage=None),
        ]

        mixin._wait_for_order_fill.return_value = True
        mixin._check_order_fill_status.return_value = (True, 1, 0)

        # Set recovery manager directly
        mixin.recovery_manager = recovery_manager

        # Mock _get_recovery_manager to return the recovery manager
        mixin._get_recovery_manager = MagicMock(return_value=recovery_manager)

        result = await mixin.place_bracket_order(
            contract_id="MNQ",
            side=0,
            size=1,
            entry_type="limit",
            entry_price=100.0,
            stop_loss_price=95.0,
            take_profit_price=105.0,
        )

        assert result.success is True
        # Verify recovery manager was used
        recovery_manager.start_operation.assert_called_once()
        recovery_manager.complete_operation.assert_called_once()

    @pytest.mark.asyncio
    async def test_bracket_order_emergency_close_on_failure(self, mock_order_manager):
        """Test bracket order MUST close position when protective orders fail."""
        mixin = mock_order_manager

        # Configure mocks - entry succeeds, both protective orders fail
        mixin.place_order.side_effect = [
            # Entry order succeeds
            OrderPlaceResponse(orderId=1, success=True, errorCode=0, errorMessage=None),
            # Stop order fails
            OrderPlaceResponse(orderId=None, success=False, errorCode=1, errorMessage="Stop failed"),
            # Target order fails
            OrderPlaceResponse(orderId=None, success=False, errorCode=1, errorMessage="Target failed"),
        ]

        mixin._wait_for_order_fill.return_value = True
        mixin._check_order_fill_status.return_value = (True, 1, 0)

        # Configure close_position mock to return a successful response
        mixin.close_position.return_value = OrderPlaceResponse(
            orderId=999, success=True, errorCode=0, errorMessage=None
        )

        # CORRECT BEHAVIOR: Should raise an error when protective orders fail
        with pytest.raises(
            ProjectXOrderError,
            match=r"CRITICAL.*position was unprotected"
        ):
            await mixin.place_bracket_order(
                contract_id="MNQ",
                side=0,
                size=1,
                entry_type="limit",
                entry_price=100.0,
                stop_loss_price=95.0,
                take_profit_price=105.0,
            )

        # Should have attempted to close the unprotected position
        mixin.close_position.assert_called_once_with("MNQ", account_id=None)
