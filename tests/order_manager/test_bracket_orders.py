"""Unit tests for bracket order functionality."""

import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from project_x_py.exceptions import ProjectXOrderError
from project_x_py.models import Order, OrderPlaceResponse
from project_x_py.order_manager.bracket_orders import BracketOrderMixin
from project_x_py.order_manager.error_recovery import OperationRecoveryManager
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
        self.close_position = (
            AsyncMock()
        )  # Add close_position method for emergency closure
        # Additional attributes that may be accessed
        self.stats = {
            "bracket_orders": 0
        }  # Initialize with the key that will be accessed
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
            match=r"Buy order stop loss \(101\.0\) must be below entry \(100\.0\)",
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
            OrderPlaceResponse(
                orderId=10, success=True, errorCode=0, errorMessage=None
            ),
            # Stop order
            OrderPlaceResponse(
                orderId=11, success=True, errorCode=0, errorMessage=None
            ),
            # Target order
            OrderPlaceResponse(
                orderId=12, success=True, errorCode=0, errorMessage=None
            ),
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

        with pytest.raises(ProjectXOrderError, match=r"did not fill within timeout"):
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
            OrderPlaceResponse(
                orderId=2, success=False, errorCode=1, errorMessage="Stop order failed"
            ),
        ]

        mixin._wait_for_order_fill.return_value = True
        mixin._check_order_fill_status.return_value = (True, 1, 0)

        with pytest.raises(ProjectXOrderError, match=r"unprotected position"):
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
            ProjectXOrderError, match=r"Invalid entry_type.*Must be 'market' or 'limit'"
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
    async def test_bracket_order_missing_entry_price_for_limit(
        self, mock_order_manager
    ):
        """Test bracket order should validate entry price for limit orders."""
        mixin = mock_order_manager

        # CORRECT BEHAVIOR: Should validate and raise proper error for None entry_price
        with pytest.raises(
            ProjectXOrderError, match=r"entry_price is required for limit orders"
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
            match=r"Sell order stop loss \(95\.0\) must be above entry \(100\.0\)",
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
            OrderPlaceResponse(
                orderId=None, success=False, errorCode=1, errorMessage="Stop failed"
            ),
            # Target order fails
            OrderPlaceResponse(
                orderId=None, success=False, errorCode=1, errorMessage="Target failed"
            ),
        ]

        mixin._wait_for_order_fill.return_value = True
        mixin._check_order_fill_status.return_value = (True, 1, 0)

        # Configure close_position mock to return a successful response
        mixin.close_position.return_value = OrderPlaceResponse(
            orderId=999, success=True, errorCode=0, errorMessage=None
        )

        # CORRECT BEHAVIOR: Should raise an error when protective orders fail
        with pytest.raises(
            ProjectXOrderError, match=r"CRITICAL.*position was unprotected"
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

    @pytest.mark.asyncio
    async def test_bracket_order_emergency_close_fails(self, mock_order_manager):
        """Test when emergency close also fails after protective orders fail."""
        mixin = mock_order_manager

        # Configure mocks - entry succeeds, both protective orders fail
        mixin.place_order.side_effect = [
            # Entry order succeeds
            OrderPlaceResponse(orderId=1, success=True, errorCode=0, errorMessage=None),
            # Stop order fails
            OrderPlaceResponse(
                orderId=None, success=False, errorCode=1, errorMessage="Stop failed"
            ),
            # Target order fails
            OrderPlaceResponse(
                orderId=None, success=False, errorCode=1, errorMessage="Target failed"
            ),
        ]

        mixin._wait_for_order_fill.return_value = True
        mixin._check_order_fill_status.return_value = (True, 1, 0)

        # Emergency close also fails - this triggers the critical failure path
        mixin.close_position.return_value = OrderPlaceResponse(
            orderId=None, success=False, errorCode=1, errorMessage="Close failed"
        )

        # Should still raise error but with emergency closure failure noted
        with pytest.raises(
            ProjectXOrderError, match=r"CRITICAL.*position was unprotected"
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

        # Should have attempted emergency close
        mixin.close_position.assert_called_once_with("MNQ", account_id=None)

    @pytest.mark.asyncio
    async def test_bracket_order_emergency_close_exception(self, mock_order_manager):
        """Test when emergency close throws exception after protective orders fail."""
        mixin = mock_order_manager

        # Configure mocks - entry succeeds, stop fails, target succeeds
        mixin.place_order.side_effect = [
            # Entry order succeeds
            OrderPlaceResponse(orderId=1, success=True, errorCode=0, errorMessage=None),
            # Stop order fails
            OrderPlaceResponse(
                orderId=None, success=False, errorCode=1, errorMessage="Stop failed"
            ),
            # Target order succeeds (mixed failure scenario)
            OrderPlaceResponse(orderId=2, success=True, errorCode=0, errorMessage=None),
        ]

        mixin._wait_for_order_fill.return_value = True
        mixin._check_order_fill_status.return_value = (True, 1, 0)

        # Emergency close throws exception
        mixin.close_position.side_effect = Exception(
            "Network error during emergency close"
        )

        # Should still raise error with emergency closure exception noted
        with pytest.raises(
            ProjectXOrderError, match=r"CRITICAL.*position was unprotected"
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

        # Should have attempted emergency close
        mixin.close_position.assert_called_once()

    @pytest.mark.asyncio
    async def test_bracket_order_only_stop_fails(self, mock_order_manager):
        """Test when only stop order fails, target succeeds."""
        mixin = mock_order_manager

        # Configure mocks - entry succeeds, stop fails, target succeeds
        mixin.place_order.side_effect = [
            # Entry order succeeds
            OrderPlaceResponse(orderId=1, success=True, errorCode=0, errorMessage=None),
            # Stop order fails
            OrderPlaceResponse(
                orderId=None, success=False, errorCode=1, errorMessage="Stop failed"
            ),
            # Target order succeeds
            OrderPlaceResponse(orderId=2, success=True, errorCode=0, errorMessage=None),
        ]

        mixin._wait_for_order_fill.return_value = True
        mixin._check_order_fill_status.return_value = (True, 1, 0)

        # Configure successful emergency close
        mixin.close_position.return_value = OrderPlaceResponse(
            orderId=999, success=True, errorCode=0, errorMessage=None
        )

        # Should raise error - position is still unprotected without stop loss
        with pytest.raises(
            ProjectXOrderError,
            match=r"CRITICAL.*position was unprotected.*Stop: FAILED.*Target: OK",
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

        # Should have closed position due to missing stop loss
        mixin.close_position.assert_called_once()

    @pytest.mark.asyncio
    async def test_bracket_order_only_target_fails(self, mock_order_manager):
        """Test when only target order fails, stop succeeds."""
        mixin = mock_order_manager

        # Configure mocks - entry succeeds, stop succeeds, target fails
        mixin.place_order.side_effect = [
            # Entry order succeeds
            OrderPlaceResponse(orderId=1, success=True, errorCode=0, errorMessage=None),
            # Stop order succeeds
            OrderPlaceResponse(orderId=2, success=True, errorCode=0, errorMessage=None),
            # Target order fails
            OrderPlaceResponse(
                orderId=None, success=False, errorCode=1, errorMessage="Target failed"
            ),
        ]

        mixin._wait_for_order_fill.return_value = True
        mixin._check_order_fill_status.return_value = (True, 1, 0)

        # Configure successful emergency close
        mixin.close_position.return_value = OrderPlaceResponse(
            orderId=999, success=True, errorCode=0, errorMessage=None
        )

        # Should raise error - position is not fully protected without target
        with pytest.raises(
            ProjectXOrderError,
            match=r"CRITICAL.*position was unprotected.*Stop: OK.*Target: FAILED",
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

        # Should have closed position due to missing take profit
        mixin.close_position.assert_called_once()

    @pytest.mark.asyncio
    async def test_bracket_order_with_recovery_manager_rollback(
        self, mock_order_manager
    ):
        """Test recovery manager rollback when protective orders fail."""
        mixin = mock_order_manager

        # Create a mock recovery manager with proper operation
        mock_recovery = AsyncMock()
        mock_operation = AsyncMock()
        mock_operation.operation_id = "test-op-123"

        # Mock _get_recovery_manager to return our mock
        mixin._get_recovery_manager = MagicMock(return_value=mock_recovery)
        mock_recovery.start_operation.return_value = mock_operation

        # Configure order mocks - entry succeeds, both protective fail
        mixin.place_order.side_effect = [
            # Entry order succeeds
            OrderPlaceResponse(orderId=1, success=True, errorCode=0, errorMessage=None),
            # Stop order fails
            OrderPlaceResponse(
                orderId=None, success=False, errorCode=1, errorMessage="Stop failed"
            ),
            # Target order fails
            OrderPlaceResponse(
                orderId=None, success=False, errorCode=1, errorMessage="Target failed"
            ),
        ]

        mixin._wait_for_order_fill.return_value = True
        mixin._check_order_fill_status.return_value = (True, 1, 0)

        # Configure successful emergency close
        mixin.close_position.return_value = OrderPlaceResponse(
            orderId=999, success=True, errorCode=0, errorMessage=None
        )

        # Should raise error about unprotected position
        with pytest.raises(
            ProjectXOrderError, match=r"CRITICAL.*position was unprotected"
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

        # Should have forced rollback - may be called multiple times due to exception handling
        # The important thing is that it was called at least once
        assert mock_recovery.force_rollback_operation.called
        assert mock_recovery.force_rollback_operation.call_args[0][0] == "test-op-123"

        # Emergency close is called twice due to the nested exception handlers
        # This is expected behavior with the current implementation
        assert mixin.close_position.call_count == 2
        mixin.close_position.assert_any_call("MNQ", account_id=None)

    @pytest.mark.asyncio
    async def test_get_recovery_manager_no_project_x(self, mock_order_manager):
        """Test _get_recovery_manager returns None when project_x not available."""
        mixin = mock_order_manager

        # Remove project_x attribute to simulate test environment
        if hasattr(mixin, "project_x"):
            delattr(mixin, "project_x")

        # Should return None
        result = mixin._get_recovery_manager()
        assert result is None

    @pytest.mark.asyncio
    async def test_get_recovery_manager_with_existing_attribute(
        self, mock_order_manager
    ):
        """Test _get_recovery_manager returns existing recovery_manager attribute."""
        mixin = mock_order_manager

        # Set project_x to enable recovery manager logic
        mixin.project_x = MagicMock()

        # Create a mock recovery manager
        mock_recovery = MagicMock(spec=OperationRecoveryManager)

        # Set it as an attribute
        mixin.recovery_manager = mock_recovery

        # Should return the existing recovery manager
        result = mixin._get_recovery_manager()
        assert result is mock_recovery

    @pytest.mark.asyncio
    async def test_get_recovery_manager_creates_new(self, mock_order_manager):
        """Test _get_recovery_manager creates new instance when needed."""
        mixin = mock_order_manager

        # Set project_x to enable recovery manager logic
        mixin.project_x = MagicMock()

        # Ensure no existing recovery_manager
        mixin._recovery_manager = None
        if hasattr(mixin, "recovery_manager"):
            delattr(mixin, "recovery_manager")

        # Mock the OperationRecoveryManager class
        with patch(
            "project_x_py.order_manager.bracket_orders.OperationRecoveryManager"
        ) as MockRecovery:
            mock_instance = MagicMock(spec=OperationRecoveryManager)
            MockRecovery.return_value = mock_instance

            # Should create and return new instance
            result = mixin._get_recovery_manager()
            assert result is mock_instance
            assert mixin._recovery_manager is mock_instance
            MockRecovery.assert_called_once_with(mixin)

    @pytest.mark.asyncio
    async def test_get_recovery_manager_creation_fails(self, mock_order_manager):
        """Test _get_recovery_manager handles creation failure gracefully."""
        mixin = mock_order_manager

        # Set project_x to enable recovery manager logic
        mixin.project_x = MagicMock()

        # Ensure no existing recovery_manager
        mixin._recovery_manager = None
        if hasattr(mixin, "recovery_manager"):
            delattr(mixin, "recovery_manager")

        # Mock the OperationRecoveryManager to raise exception
        with patch(
            "project_x_py.order_manager.bracket_orders.OperationRecoveryManager"
        ) as MockRecovery:
            MockRecovery.side_effect = Exception("Failed to create recovery manager")

            # Should return None and not raise
            result = mixin._get_recovery_manager()
            assert result is None

    @pytest.mark.asyncio
    async def test_bracket_order_no_recovery_manager_on_success(
        self, mock_order_manager
    ):
        """Test bracket order works without recovery manager when all orders succeed."""
        mixin = mock_order_manager

        # Disable recovery manager
        mixin._get_recovery_manager = MagicMock(return_value=None)

        # Configure all orders to succeed
        mixin.place_order.side_effect = [
            # Entry order succeeds
            OrderPlaceResponse(orderId=1, success=True, errorCode=0, errorMessage=None),
            # Stop order succeeds
            OrderPlaceResponse(orderId=2, success=True, errorCode=0, errorMessage=None),
            # Target order succeeds
            OrderPlaceResponse(orderId=3, success=True, errorCode=0, errorMessage=None),
        ]

        mixin._wait_for_order_fill.return_value = True
        mixin._check_order_fill_status.return_value = (True, 1, 0)
        mixin.add_oco_relationship = AsyncMock()

        # Should succeed without recovery manager
        result = await mixin.place_bracket_order(
            contract_id="MNQ",
            side=0,
            size=1,
            entry_type="limit",
            entry_price=100.0,
            stop_loss_price=95.0,
            take_profit_price=105.0,
        )

        assert result.entry_order_id == 1
        assert result.stop_order_id == 2
        assert result.target_order_id == 3

    @pytest.mark.asyncio
    async def test_fill_status_treats_historical_filled_order_as_filled(
        self, mock_order_manager
    ):
        """Missing open-order cache still reports a filled historical order as filled."""
        mixin = mock_order_manager
        mixin.get_order_by_id = AsyncMock(
            return_value=type(
                "Order",
                (),
                {
                    "fillVolume": 1,
                    "size": 1,
                    "is_filled": True,
                },
            )()
        )

        is_filled, filled, remaining = await BracketOrderMixin._check_order_fill_status(
            mixin, 42
        )

        assert is_filled is True
        assert filled == 1
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_fill_status_uses_trade_history_when_order_missing(
        self, mock_order_manager
    ):
        """Absence from open orders is confirmed via trade history before aborting."""
        mixin = mock_order_manager
        mixin.get_order_by_id = AsyncMock(return_value=None)
        mixin._filled_size_from_trades = AsyncMock(return_value=2)

        is_filled, filled, remaining = await BracketOrderMixin._check_order_fill_status(
            mixin, 99
        )

        assert is_filled is False
        assert filled == 2
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_fill_status_reports_partial_when_tracked_size_known(
        self, mock_order_manager
    ):
        """Trade history of 1 fill against tracked size 2 is a partial fill."""
        mixin = mock_order_manager
        mixin.get_order_by_id = AsyncMock(return_value=None)
        mixin._filled_size_from_trades = AsyncMock(return_value=1)
        mixin.tracked_orders = {"99": {"size": 2}}

        is_filled, filled, remaining = await BracketOrderMixin._check_order_fill_status(
            mixin, 99
        )

        assert is_filled is False
        assert filled == 1
        assert remaining == 1

    @pytest.mark.asyncio
    async def test_native_bracket_places_gateway_brackets(self, mock_order_manager):
        """Native path converts price offsets to ticks and attaches Gateway brackets."""
        mixin = mock_order_manager
        mixin.project_x = MagicMock()
        mixin.place_order = AsyncMock(
            return_value=OrderPlaceResponse(
                orderId=10, success=True, errorCode=0, errorMessage=None
            )
        )
        mixin.search_open_orders = AsyncMock(
            return_value=[
                Order.from_api(
                    {
                        "id": 10,
                        "accountId": 1,
                        "contractId": "MNQ",
                        "creationTimestamp": "2024-01-01T00:00:00Z",
                        "updateTimestamp": None,
                        "status": 1,
                        "type": 1,
                        "side": 0,
                        "size": 1,
                    }
                ),
                Order.from_api(
                    {
                        "id": 11,
                        "accountId": 1,
                        "contractId": "MNQ",
                        "creationTimestamp": "2024-01-01T00:00:00Z",
                        "updateTimestamp": None,
                        "status": 1,
                        "type": 4,
                        "side": 1,
                        "size": 1,
                    }
                ),
                Order.from_api(
                    {
                        "id": 12,
                        "accountId": 1,
                        "contractId": "MNQ",
                        "creationTimestamp": "2024-01-01T00:00:00Z",
                        "updateTimestamp": None,
                        "status": 1,
                        "type": 1,
                        "side": 1,
                        "size": 1,
                    }
                ),
            ]
        )

        with patch(
            "project_x_py.order_manager.utils._get_cached_tick_size",
            new=AsyncMock(return_value=0.25),
        ):
            result = await mixin._try_native_bracket_order(
                contract_id="MNQ",
                side=0,
                size=1,
                entry_price=100.0,
                stop_loss_price=95.0,
                take_profit_price=110.0,
                entry_type="limit",
                account_id=1,
            )

        assert result is not None
        assert result.success is True
        assert result.entry_order_id == 10
        assert result.stop_order_id == 11
        assert result.target_order_id == 12
        kwargs = mixin.place_order.await_args.kwargs
        assert kwargs["stop_loss_bracket"] == {"ticks": 20, "type": 4}
        assert kwargs["take_profit_bracket"] == {"ticks": 40, "type": 1}

    @pytest.mark.asyncio
    async def test_native_bracket_falls_back_when_gateway_rejects(
        self, mock_order_manager
    ):
        """A rejected native place must fall through to the client-side path."""
        mixin = mock_order_manager
        mixin.project_x = MagicMock()
        mixin.place_order = AsyncMock(side_effect=ProjectXOrderError("no native"))

        with patch(
            "project_x_py.order_manager.utils._get_cached_tick_size",
            new=AsyncMock(return_value=0.25),
        ):
            result = await mixin._try_native_bracket_order(
                contract_id="MNQ",
                side=0,
                size=1,
                entry_price=100.0,
                stop_loss_price=95.0,
                take_profit_price=105.0,
                entry_type="limit",
                account_id=1,
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_native_bracket_falls_back_when_children_missing(
        self, mock_order_manager
    ):
        """Native place success must keep the entry even if children are unresolved."""
        mixin = mock_order_manager
        mixin.project_x = MagicMock()
        mixin.place_order = AsyncMock(
            return_value=OrderPlaceResponse(
                orderId=10, success=True, errorCode=0, errorMessage=None
            )
        )
        mixin.search_open_orders = AsyncMock(
            return_value=[
                Order.from_api(
                    {
                        "id": 10,
                        "accountId": 1,
                        "contractId": "MNQ",
                        "creationTimestamp": "2024-01-01T00:00:00Z",
                        "updateTimestamp": None,
                        "status": 1,
                        "type": 1,
                        "side": 0,
                        "size": 1,
                    }
                )
            ]
        )

        with patch(
            "project_x_py.order_manager.utils._get_cached_tick_size",
            new=AsyncMock(return_value=0.25),
        ):
            result = await mixin._try_native_bracket_order(
                contract_id="MNQ",
                side=0,
                size=1,
                entry_price=100.0,
                stop_loss_price=95.0,
                take_profit_price=110.0,
                entry_type="limit",
                account_id=1,
            )

        assert result is not None
        assert result.success is True
        assert result.entry_order_id == 10
        assert result.stop_order_id is None
        assert result.target_order_id is None

    @pytest.mark.asyncio
    async def test_native_bracket_does_not_steal_unrelated_working_orders(
        self, mock_order_manager
    ):
        """An existing working stop of a different size is not the new bracket child."""
        mixin = mock_order_manager
        mixin.project_x = MagicMock()
        mixin.place_order = AsyncMock(
            return_value=OrderPlaceResponse(
                orderId=10, success=True, errorCode=0, errorMessage=None
            )
        )
        mixin.search_open_orders = AsyncMock(
            return_value=[
                Order.from_api(
                    {
                        "id": 10,
                        "accountId": 1,
                        "contractId": "MNQ",
                        "creationTimestamp": "2024-01-01T00:00:00Z",
                        "updateTimestamp": None,
                        "status": 1,
                        "type": 1,
                        "side": 0,
                        "size": 1,
                    }
                ),
                Order.from_api(
                    {
                        "id": 99,
                        "accountId": 1,
                        "contractId": "MNQ",
                        "creationTimestamp": "2024-01-01T00:00:00Z",
                        "updateTimestamp": None,
                        "status": 1,
                        "type": 4,
                        "side": 1,
                        "size": 5,
                    }
                ),
            ]
        )

        with patch(
            "project_x_py.order_manager.utils._get_cached_tick_size",
            new=AsyncMock(return_value=0.25),
        ):
            result = await mixin._try_native_bracket_order(
                contract_id="MNQ",
                side=0,
                size=1,
                entry_price=100.0,
                stop_loss_price=95.0,
                take_profit_price=110.0,
                entry_type="limit",
                account_id=1,
            )

        assert result is not None
        assert result.entry_order_id == 10
        assert result.stop_order_id is None
        assert result.target_order_id is None


def _native_child_order(
    order_id: int, order_type: int, side: int, size: int = 1
) -> Order:
    return Order.from_api(
        {
            "id": order_id,
            "accountId": 12345,
            "contractId": "MNQ",
            "creationTimestamp": "2024-01-01T00:00:00Z",
            "updateTimestamp": None,
            "status": 1,
            "type": order_type,
            "side": side,
            "size": size,
        }
    )


class TestPlaceBracketOrderNativePublicPath:
    """Public place_bracket_order with project_x present must use native first."""

    @pytest.mark.asyncio
    async def test_place_bracket_order_returns_native_when_children_unique(
        self, order_manager, make_order_response
    ):
        """Native children resolve → return native IDs and do not place client-side legs."""
        order_manager.project_x._make_request = AsyncMock(
            return_value=make_order_response(10)
        )
        order_manager.search_open_orders = AsyncMock(
            return_value=[
                _native_child_order(10, 1, 0),
                _native_child_order(11, 4, 1),
                _native_child_order(12, 1, 1),
            ]
        )
        order_manager._wait_for_order_fill = AsyncMock(return_value=True)
        order_manager._check_order_fill_status = AsyncMock(return_value=(True, 1, 0))

        with patch(
            "project_x_py.order_manager.utils._get_cached_tick_size",
            new=AsyncMock(return_value=0.25),
        ):
            result = await order_manager.place_bracket_order(
                contract_id="MNQ",
                side=0,
                size=1,
                entry_type="limit",
                entry_price=100.0,
                stop_loss_price=95.0,
                take_profit_price=110.0,
            )

        assert result.success is True
        assert result.entry_order_id == 10
        assert result.stop_order_id == 11
        assert result.target_order_id == 12
        place_calls = [
            call
            for call in order_manager.project_x._make_request.await_args_list
            if call.args[1] == "/Order/place"
        ]
        assert len(place_calls) == 1
        payload = place_calls[0].kwargs["data"]
        assert payload["type"] == 1
        assert payload["side"] == 0
        assert payload["size"] == 1
        assert payload["stopLossBracket"] == {"ticks": 20, "type": 4}
        assert payload["takeProfitBracket"] == {"ticks": 40, "type": 1}
        order_manager._wait_for_order_fill.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_place_bracket_order_falls_back_when_native_returns_none(
        self, order_manager, make_order_response
    ):
        """Missing tick size → native is None → client-side entry/stop/target still run."""
        order_manager.project_x._make_request = AsyncMock(
            side_effect=[
                make_order_response(1),
                make_order_response(2),
                make_order_response(3),
            ]
        )
        order_manager._wait_for_order_fill = AsyncMock(return_value=True)
        order_manager._check_order_fill_status = AsyncMock(return_value=(True, 1, 0))
        order_manager._get_recovery_manager = MagicMock(return_value=None)

        with patch(
            "project_x_py.order_manager.utils._get_cached_tick_size",
            new=AsyncMock(return_value=None),
        ):
            result = await order_manager.place_bracket_order(
                contract_id="MNQ",
                side=0,
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
        place_calls = [
            call
            for call in order_manager.project_x._make_request.await_args_list
            if call.args[1] == "/Order/place"
        ]
        assert len(place_calls) == 3
        for call in place_calls:
            payload = call.kwargs["data"]
            assert "stopLossBracket" not in payload
            assert "takeProfitBracket" not in payload
        types = [call.kwargs["data"]["type"] for call in place_calls]
        assert types == [1, 4, 1]  # limit entry, stop, limit target

    @pytest.mark.asyncio
    async def test_place_bracket_order_falls_back_when_native_raises(
        self, order_manager, make_order_response
    ):
        """Native place reject → client-side three-leg OCO still runs."""
        order_manager.project_x._make_request = AsyncMock(
            side_effect=[
                ProjectXOrderError("no native brackets"),
                make_order_response(1),
                make_order_response(2),
                make_order_response(3),
            ]
        )
        order_manager._wait_for_order_fill = AsyncMock(return_value=True)
        order_manager._check_order_fill_status = AsyncMock(return_value=(True, 1, 0))
        order_manager._get_recovery_manager = MagicMock(return_value=None)

        with patch(
            "project_x_py.order_manager.utils._get_cached_tick_size",
            new=AsyncMock(return_value=0.25),
        ):
            result = await order_manager.place_bracket_order(
                contract_id="MNQ",
                side=0,
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
        place_calls = [
            call
            for call in order_manager.project_x._make_request.await_args_list
            if call.args[1] == "/Order/place"
        ]
        assert len(place_calls) == 4
        native_payload = place_calls[0].kwargs["data"]
        assert native_payload["stopLossBracket"] == {"ticks": 20, "type": 4}
        for call in place_calls[1:]:
            assert "stopLossBracket" not in call.kwargs["data"]
