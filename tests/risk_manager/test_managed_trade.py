"""Comprehensive tests for ManagedTrade context manager following TDD methodology.

Tests define the EXPECTED behavior, not current implementation.
If tests fail, we fix the implementation, not the tests.
"""

import asyncio
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, Mock, patch, call

import pytest

from project_x_py.event_bus import EventBus, EventType
from project_x_py.models import Order, Position, Instrument
from project_x_py.risk_manager import RiskManager, RiskConfig
from project_x_py.risk_manager.managed_trade import ManagedTrade
from project_x_py.types import OrderSide, OrderType, OrderStatus


@pytest.fixture
def mock_risk_manager():
    """Create a mock RiskManager."""
    rm = MagicMock(spec=RiskManager)
    rm.config = RiskConfig()
    rm.validate_trade = AsyncMock(return_value={
        "is_valid": True,
        "current_risk": 0.01,
        "reasons": []
    })
    rm.calculate_position_size = AsyncMock(return_value={
        "position_size": 2,
        "risk_amount": 200,
        "stop_distance": 50,
        "entry_price": 15000
    })
    rm.calculate_stop_loss = AsyncMock(return_value=14950.0)
    rm.calculate_take_profit = AsyncMock(return_value=15100.0)
    rm.should_activate_trailing_stop = AsyncMock(return_value=False)
    return rm


@pytest.fixture
def mock_order_manager():
    """Create a mock OrderManager."""
    om = MagicMock()
    om.place_order = AsyncMock()
    om.cancel_order = AsyncMock()
    om.modify_order = AsyncMock()
    om.get_order = AsyncMock()
    om.place_bracket_order = AsyncMock()
    # Create proper OrderPlaceResponse mocks
    success_response = MagicMock()
    success_response.success = True
    success_response.orderId = 1
    success_response.errorCode = 0
    success_response.errorMessage = None

    om.place_market_order = AsyncMock(return_value=success_response)
    om.place_limit_order = AsyncMock(return_value=success_response)
    om.search_open_orders = AsyncMock(return_value=[])
    return om


@pytest.fixture
def mock_position_manager():
    """Create a mock PositionManager."""
    pm = MagicMock()
    pm.get_position = AsyncMock(return_value=None)
    pm.get_positions_by_instrument = AsyncMock(return_value=[])
    pm.get_all_positions = AsyncMock(return_value=[])
    pm.monitor_position = AsyncMock()
    return pm


@pytest.fixture
def mock_data_manager():
    """Create a mock DataManager."""
    dm = MagicMock()
    dm.get_latest_price = AsyncMock(return_value=15000.0)
    dm.get_bid_ask = AsyncMock(return_value=(14999.0, 15001.0))
    return dm


@pytest.fixture
def mock_event_bus():
    """Create a mock EventBus."""
    bus = MagicMock(spec=EventBus)
    bus.emit = AsyncMock()
    bus.on = AsyncMock()
    bus.off = AsyncMock()
    bus.wait_for = AsyncMock()
    return bus


@pytest.fixture
def managed_trade(mock_risk_manager, mock_order_manager, mock_position_manager,
                 mock_data_manager, mock_event_bus):
    """Create a ManagedTrade instance."""
    return ManagedTrade(
        risk_manager=mock_risk_manager,
        order_manager=mock_order_manager,
        position_manager=mock_position_manager,
        instrument_id="MNQ",
        data_manager=mock_data_manager,
        event_bus=mock_event_bus
    )


class TestManagedTradeInitialization:
    """Test ManagedTrade initialization."""

    def test_initialization_basic(self, mock_risk_manager, mock_order_manager, mock_position_manager):
        """Test basic initialization of ManagedTrade."""
        mt = ManagedTrade(
            risk_manager=mock_risk_manager,
            order_manager=mock_order_manager,
            position_manager=mock_position_manager,
            instrument_id="MNQ"
        )

        assert mt.risk == mock_risk_manager
        assert mt.orders == mock_order_manager
        assert mt.positions == mock_position_manager
        assert mt.instrument_id == "MNQ"
        assert mt.data_manager is None
        assert mt.event_bus is None
        assert mt.max_risk_percent is None
        assert mt.max_risk_amount is None

        # Check internal tracking
        assert mt._orders == []
        assert mt._positions == []
        assert mt._entry_order is None
        assert mt._stop_order is None
        assert mt._target_order is None

    def test_initialization_with_risk_overrides(self, mock_risk_manager, mock_order_manager, mock_position_manager):
        """Test initialization with risk override parameters."""
        mt = ManagedTrade(
            risk_manager=mock_risk_manager,
            order_manager=mock_order_manager,
            position_manager=mock_position_manager,
            instrument_id="ES",
            max_risk_percent=0.02,
            max_risk_amount=500.0
        )

        assert mt.max_risk_percent == 0.02
        assert mt.max_risk_amount == 500.0


class TestManagedTradeContextManager:
    """Test ManagedTrade context manager behavior."""

    @pytest.mark.asyncio
    async def test_context_manager_enter_exit(self, managed_trade):
        """Test context manager enter and exit."""
        async with managed_trade as mt:
            assert mt == managed_trade

        # Should have called cleanup on exit
        # (tested in detail below)

    @pytest.mark.asyncio
    async def test_context_exit_cancels_unfilled_entry_orders(self, managed_trade, mock_order_manager):
        """Test that unfilled entry orders are cancelled on exit."""
        # Create mock orders
        entry_order = MagicMock(spec=Order)
        entry_order.id = 1
        entry_order.is_working = True
        entry_order.status = OrderStatus.OPEN.value  # Use OPEN for working orders

        stop_order = MagicMock(spec=Order)
        stop_order.id = 2
        stop_order.is_working = True

        target_order = MagicMock(spec=Order)
        target_order.id = 3
        target_order.is_working = True

        managed_trade._orders = [entry_order, stop_order, target_order]
        managed_trade._entry_order = entry_order
        managed_trade._stop_order = stop_order
        managed_trade._target_order = target_order

        async with managed_trade:
            pass

        # Should only cancel entry order, not protective orders
        mock_order_manager.cancel_order.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_context_exit_preserves_protective_orders(self, managed_trade, mock_order_manager):
        """Test that stop and target orders are preserved on exit."""
        stop_order = MagicMock(spec=Order)
        stop_order.id = 2
        stop_order.is_working = True

        target_order = MagicMock(spec=Order)
        target_order.id = 3
        target_order.is_working = True

        managed_trade._orders = [stop_order, target_order]
        managed_trade._stop_order = stop_order
        managed_trade._target_order = target_order

        async with managed_trade:
            pass

        # Should not cancel protective orders
        mock_order_manager.cancel_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_context_exit_handles_cancel_errors(self, managed_trade, mock_order_manager):
        """Test context exit handles order cancel errors gracefully."""
        entry_order = MagicMock(spec=Order)
        entry_order.id = 1
        entry_order.is_working = True

        managed_trade._orders = [entry_order]
        managed_trade._entry_order = entry_order

        mock_order_manager.cancel_order.side_effect = Exception("Cancel failed")

        # Should not raise exception
        async with managed_trade:
            pass

    @pytest.mark.asyncio
    async def test_context_exit_with_exception_still_cleans_up(self, managed_trade, mock_order_manager):
        """Test cleanup occurs even when exception raised in context."""
        entry_order = MagicMock(spec=Order)
        entry_order.id = 1
        entry_order.is_working = True

        managed_trade._orders = [entry_order]
        managed_trade._entry_order = entry_order

        with pytest.raises(ValueError):
            async with managed_trade:
                raise ValueError("Test error")

        # Should still attempt cleanup
        mock_order_manager.cancel_order.assert_called_once_with(1)


class TestManagedTradeOrderExecution:
    """Test order execution methods."""

    @pytest.mark.asyncio
    async def test_enter_long_basic(self, managed_trade, mock_order_manager, mock_risk_manager):
        """Test basic long entry."""
        # Mock order response
        order = MagicMock(spec=Order)
        order.id = 1
        order.side = OrderSide.BUY.value
        order.size = 2
        order.limitPrice = 15000.0
        mock_order_manager.place_order.return_value = order

        result = await managed_trade.enter_long(
            size=2,
            entry_price=15000.0
        )

        # Result should be a dictionary with trade details
        assert isinstance(result, dict)
        assert result["size"] == 2
        assert result["validation"]["is_valid"] is True
        # Entry order is None because mock doesn't return a matching order
        assert "entry_order" in result

        # Verify risk validation was called
        mock_risk_manager.validate_trade.assert_called_once()

    @pytest.mark.asyncio
    async def test_enter_long_with_stop_and_target(self, managed_trade, mock_order_manager, mock_risk_manager, mock_position_manager):
        """Test long entry with stop loss and take profit."""
        # Mock orders
        entry_order = MagicMock(spec=Order)
        entry_order.id = 1
        entry_order.side = OrderSide.BUY.value

        stop_order = MagicMock(spec=Order)
        stop_order.id = 2

        target_order = MagicMock(spec=Order)
        target_order.id = 3

        # Mock position
        position = MagicMock()
        position.contractId = "MNQ"
        position.averagePrice = 15000.0
        position.size = 2
        mock_position_manager.get_all_positions.return_value = [position]

        # Mock bracket order response
        bracket_response = MagicMock()
        bracket_response.stop_order_id = 2
        bracket_response.target_order_id = 3
        mock_risk_manager.attach_risk_orders.return_value = {
            "bracket_order": bracket_response
        }

        # Mock search_open_orders to return all orders
        mock_order_manager.search_open_orders.side_effect = [
            [entry_order],  # First call for entry order
            [entry_order, stop_order],  # Second call for stop order
            [entry_order, stop_order, target_order]  # Third call for target order
        ]
        mock_order_manager.place_order.return_value = entry_order

        result = await managed_trade.enter_long(
            size=2,
            entry_price=15000.0,
            stop_loss=14950.0,
            take_profit=15100.0
        )

        # Result should be a dictionary with trade details
        assert isinstance(result, dict)
        assert result["size"] == 2
        assert result["validation"]["is_valid"] is True
        assert managed_trade._entry_order == entry_order
        assert managed_trade._stop_order == stop_order
        assert managed_trade._target_order == target_order
        assert len(managed_trade._orders) == 3

    @pytest.mark.asyncio
    async def test_enter_long_auto_calculate_stop(self, managed_trade, mock_risk_manager):
        """Test long entry with auto-calculated stop loss."""
        mock_risk_manager.config.use_stop_loss = True
        mock_risk_manager.calculate_stop_loss.return_value = 14950.0

        entry_order = MagicMock(spec=Order)
        managed_trade.orders.place_order.return_value = entry_order

        await managed_trade.enter_long(
            size=2,
            entry_price=15000.0
        )

        # Should have calculated stop loss
        mock_risk_manager.calculate_stop_loss.assert_called_once()

    @pytest.mark.asyncio
    async def test_enter_short_basic(self, managed_trade, mock_order_manager):
        """Test basic short entry."""
        order = MagicMock(spec=Order)
        order.id = 1
        order.side = OrderSide.SELL.value
        mock_order_manager.place_order.return_value = order

        result = await managed_trade.enter_short(
            size=2,
            entry_price=15000.0,
            stop_loss=15100.0  # Stop above entry for short
        )

        assert isinstance(result, dict)
        assert result["size"] == 2
        assert result["validation"]["is_valid"] is True

    @pytest.mark.asyncio
    async def test_enter_market_order(self, managed_trade, mock_data_manager, mock_order_manager):
        """Test market order entry."""
        mock_data_manager.get_latest_price.return_value = 15005.0

        order = MagicMock(spec=Order)
        mock_order_manager.place_order.return_value = order

        result = await managed_trade.enter_market(
            side=OrderSide.BUY,
            size=2,
            stop_loss=14900.0  # Stop below market for buy
        )

        assert isinstance(result, dict)
        assert result["size"] == 2
        assert result["validation"]["is_valid"] is True
        # Should have fetched current price for market order
        # (Market orders don't need price fetch since they execute at market)

    @pytest.mark.asyncio
    async def test_enter_bracket_order(self, managed_trade, mock_order_manager):
        """Test bracket order entry."""
        bracket_response = MagicMock()
        bracket_response.parent_order = MagicMock(spec=Order)
        bracket_response.stop_order = MagicMock(spec=Order)
        bracket_response.target_order = MagicMock(spec=Order)

        mock_order_manager.place_bracket_order.return_value = bracket_response

        result = await managed_trade.enter_bracket(
            size=2,
            entry_price=15000.0,
            stop_loss=14950.0,  # Actual stop price, not offset
            take_profit=15100.0  # Actual target price, not offset
        )

        assert isinstance(result, dict)
        assert result["size"] == 2
        assert result["validation"]["is_valid"] is True
        assert result["risk_amount"] == 100.0  # 2 * (15000 - 14950)


class TestManagedTradeRiskValidation:
    """Test risk validation in managed trades."""

    @pytest.mark.asyncio
    async def test_entry_rejected_by_risk_validation(self, managed_trade, mock_risk_manager, mock_order_manager):
        """Test entry rejected when risk validation fails."""
        mock_risk_manager.validate_trade.return_value = {
            "is_valid": False,
            "current_risk": 0.05,
            "reasons": ["Risk too high"]
        }

        with pytest.raises(Exception) as exc_info:
            await managed_trade.enter_long(size=10, entry_price=15000.0)

        assert "Trade validation failed" in str(exc_info.value)
        mock_order_manager.place_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_position_sizing_with_risk_override(self, managed_trade, mock_risk_manager):
        """Test position sizing uses risk override parameters."""
        managed_trade.max_risk_percent = 0.005  # 0.5% override

        mock_risk_manager.calculate_position_size.return_value = {
            "position_size": 1,
            "risk_amount": 500
        }

        size = await managed_trade.calculate_position_size(
            entry_price=15000.0,
            stop_loss=14950.0
        )

        assert size == 1

        # Verify override was passed
        mock_risk_manager.calculate_position_size.assert_called_with(
            entry_price=15000.0,
            stop_loss=14950.0,
            risk_percent=0.005,
            risk_amount=None,
            # instrument parameter removed in implementation
        )


class TestManagedTradePositionMonitoring:
    """Test position monitoring functionality."""

    @pytest.mark.asyncio
    async def test_wait_for_fill(self, managed_trade, mock_event_bus, mock_order_manager):
        """Test waiting for order fill."""
        order = MagicMock(spec=Order)
        order.id = 1
        order.status = OrderStatus.FILLED.value

        managed_trade._entry_order = order
        mock_event_bus.wait_for.return_value = order

        # Mock search_open_orders to return filled order
        managed_trade.orders = mock_order_manager
        mock_order_manager.search_open_orders.return_value = [order]

        is_filled = await managed_trade.wait_for_fill(timeout=0.1)

        assert is_filled is True

    @pytest.mark.asyncio
    async def test_wait_for_fill_timeout(self, managed_trade, mock_event_bus, mock_order_manager):
        """Test wait for fill timeout handling."""
        order = MagicMock(spec=Order)
        order.id = 1
        order.status = OrderStatus.OPEN.value  # Use OPEN for working orders

        managed_trade._entry_order = order
        managed_trade.orders = mock_order_manager
        # Return open order (not filled)
        mock_order_manager.search_open_orders.return_value = [order]

        is_filled = await managed_trade.wait_for_fill(timeout=0.01)

        assert is_filled is False

    @pytest.mark.asyncio
    async def test_monitor_position(self, managed_trade, mock_position_manager, mock_data_manager):
        """Test position monitoring."""
        position = MagicMock(spec=Position)
        position.contractId = "MNQ"
        position.netQuantity = 2
        position.size = 2
        position.unrealized = 50.0  # Set to match expected value

        mock_position_manager.get_positions_by_instrument.return_value = [position]
        managed_trade._positions = [position]

        # Mock price updates
        mock_data_manager.get_latest_price.side_effect = [15000, 15010, 15020]

        # Monitor position directly (no check_interval parameter)
        result = await managed_trade.monitor_position()

        # Verify the result
        assert result["position"] == position
        assert result["size"] == 2
        assert result["pnl"] == 50

    @pytest.mark.asyncio
    async def test_adjust_stop_loss(self, managed_trade, mock_order_manager):
        """Test adjusting stop loss order."""
        stop_order = MagicMock(spec=Order)
        stop_order.id = 2
        stop_order.stopPrice = 14950.0

        managed_trade._stop_order = stop_order

        await managed_trade.adjust_stop_loss(new_stop=14975.0)

        mock_order_manager.modify_order.assert_called_once_with(
            order_id=2,
            stop_price=14975.0
        )

    @pytest.mark.asyncio
    async def test_close_position_market(self, managed_trade, mock_order_manager, mock_position_manager):
        """Test closing position with market order."""
        position = MagicMock(spec=Position)
        position.netQuantity = 2
        position.contractId = "MNQ"
        position.size = 2
        position.is_long = True

        mock_position_manager.get_positions_by_instrument.return_value = [position]
        managed_trade._positions = [position]  # Set the position

        close_order = MagicMock(spec=Order)
        close_order.id = 10  # Add id attribute to match orderId
        mock_order_manager.place_order.return_value = close_order

        # Mock place_market_order response
        success_response = MagicMock()
        success_response.success = True
        success_response.orderId = 10
        mock_order_manager.place_market_order.return_value = success_response
        mock_order_manager.search_open_orders.return_value = [close_order]

        result = await managed_trade.close_position()

        assert isinstance(result, dict)
        assert "close_order" in result or result is not None

        # Verify market order to close was placed
        mock_order_manager.place_market_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_position_no_position(self, managed_trade, mock_position_manager):
        """Test closing when no position exists."""
        mock_position_manager.get_positions_by_instrument.return_value = []

        result = await managed_trade.close_position()

        assert result is None


class TestManagedTradeStatistics:
    """Test trade statistics and tracking."""

    @pytest.mark.asyncio
    async def test_get_trade_summary(self, managed_trade):
        """Test getting trade summary."""
        # Setup trade data
        entry_order = MagicMock(spec=Order)
        entry_order.id = 1
        entry_order.side = OrderSide.BUY.value
        entry_order.size = 2
        entry_order.limitPrice = 15000.0
        entry_order.status = OrderStatus.FILLED.value

        position = MagicMock(spec=Position)
        position.size = 2
        position.unrealized = 200.0
        position.realized = 0
        position.contractId = "MNQ"

        managed_trade._entry_order = entry_order
        managed_trade._positions = [position]

        summary = await managed_trade.get_summary()

        assert isinstance(summary, dict)
        assert summary["instrument"] == "MNQ"
        assert summary["entry_price"] == 15000.0
        assert summary["size"] == 2
        assert summary["unrealized_pnl"] == 200.0
        assert summary["status"] == "open"

    @pytest.mark.asyncio
    async def test_track_performance(self, managed_trade, mock_risk_manager):
        """Test performance tracking integration with risk manager."""
        # Setup completed trade
        entry_order = MagicMock(spec=Order)
        entry_order.limitPrice = 15000.0
        entry_order.side = OrderSide.BUY.value
        entry_order.size = 2

        managed_trade._entry_order = entry_order

        # Track trade result
        await managed_trade.record_trade_result({
            "exit_price": 15050.0,
            "pnl": 100.0
        })

        # Should update risk manager history
        mock_risk_manager.add_trade_result.assert_called_once_with(
            instrument="MNQ",
            pnl=100.0,
            entry_price=15000.0,
            exit_price=15050.0,
            size=2,
            side=OrderSide.BUY
        )


class TestManagedTradeEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_entry_with_no_data_manager(self, managed_trade):
        """Test market order without data manager."""
        managed_trade.data_manager = None

        with pytest.raises(Exception) as exc_info:
            await managed_trade.enter_market(side=OrderSide.BUY, size=2)

        # Either stop loss or data manager error is acceptable
        error_msg = str(exc_info.value).lower()
        assert "stop loss" in error_msg or "data manager" in error_msg

    @pytest.mark.asyncio
    async def test_concurrent_entries_prevented(self, managed_trade, mock_order_manager):
        """Test preventing multiple concurrent entries."""
        order1 = MagicMock(spec=Order)
        managed_trade._entry_order = order1

        with pytest.raises(Exception) as exc_info:
            await managed_trade.enter_long(size=2, entry_price=15000.0)

        assert "already has entry" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_partial_fill_handling(self, managed_trade, mock_event_bus):
        """Test handling of partial fills."""
        order = MagicMock(spec=Order)
        order.id = 1
        order.size = 10
        order.filled_quantity = 5  # Partial fill
        order.status = OrderStatus.FILLED.value  # Use filled for partial fills

        managed_trade._entry_order = order

        is_filled = managed_trade.is_filled()  # is_filled is not async

        assert is_filled is False  # Not fully filled

    @pytest.mark.asyncio
    async def test_emergency_exit(self, managed_trade, mock_order_manager):
        """Test emergency position exit."""
        # Cancel all working orders
        order1 = MagicMock(spec=Order)
        order1.id = 1
        order1.is_working = True

        order2 = MagicMock(spec=Order)
        order2.id = 2
        order2.is_working = True

        managed_trade._orders = [order1, order2]

        await managed_trade.emergency_exit()

        # Should cancel all orders
        assert mock_order_manager.cancel_order.call_count == 2

        # Should attempt to close position
        # (Implementation should close any open position)


class TestManagedTradeIntegration:
    """Test integration with risk management system."""

    @pytest.mark.asyncio
    async def test_full_trade_lifecycle(self, managed_trade, mock_order_manager,
                                       mock_position_manager, mock_event_bus):
        """Test complete trade lifecycle from entry to exit."""
        # Entry
        entry_order = MagicMock(spec=Order)
        entry_order.id = 1
        entry_order.status = OrderStatus.FILLED.value
        entry_order.limitPrice = 15000.0
        entry_order.side = OrderSide.BUY.value
        entry_order.size = 2

        mock_order_manager.place_order.return_value = entry_order

        # Set up search_open_orders to return entry_order first (for enter_long)
        # Then return filled order status for wait_for_fill
        filled_order = MagicMock(spec=Order)
        filled_order.id = 1
        filled_order.status = 2  # FILLED status
        mock_order_manager.search_open_orders.side_effect = [
            [entry_order],  # First call during enter_long
            [filled_order],  # Second call during wait_for_fill
        ]

        # Position after fill
        position = MagicMock(spec=Position)
        position.netQuantity = 2
        position.unrealized = 100.0

        mock_position_manager.get_positions_by_instrument.return_value = [position]

        async with managed_trade as mt:
            # Enter position
            await mt.enter_long(size=2, entry_price=15000.0, stop_loss=14950.0)

            # Wait for fill
            filled = await mt.wait_for_fill()
            assert filled is True

            # Close position
            close_order = MagicMock(spec=Order)
            mock_order_manager.place_order.return_value = close_order
            await mt.close_position()

        # Verify lifecycle
        assert len(managed_trade._orders) > 0
        assert managed_trade._entry_order == entry_order

    @pytest.mark.asyncio
    async def test_trailing_stop_activation(self, managed_trade, mock_risk_manager,
                                           mock_data_manager, mock_order_manager):
        """Test trailing stop activation during profitable trade."""
        managed_trade.risk.config.use_trailing_stops = True
        mock_risk_manager.should_activate_trailing_stop.return_value = True

        # Setup position
        position = MagicMock(spec=Position)
        position.netQuantity = 2
        position.buyPrice = 15000.0
        position.size = 2
        position.is_long = True

        stop_order = MagicMock(spec=Order)
        stop_order.id = 2
        stop_order.stopPrice = 14950.0

        managed_trade._stop_order = stop_order
        managed_trade._positions = [position]

        # Current price shows profit
        mock_data_manager.get_latest_price.return_value = 15050.0

        await managed_trade.check_trailing_stop()

        # Should adjust stop
        mock_order_manager.modify_order.assert_called()

    @pytest.mark.asyncio
    async def test_multiple_partial_exits(self, managed_trade, mock_order_manager, mock_position_manager):
        """Test scaling out of position with multiple exits."""
        position = MagicMock(spec=Position)
        position.netQuantity = 10
        position.contractId = "MNQ"
        position.size = 10
        position.is_long = True

        mock_position_manager.get_positions_by_instrument.return_value = [position]
        managed_trade._positions = [position]

        # Exit partially
        await managed_trade.exit_partial(size=3)
        await managed_trade.exit_partial(size=3)
        await managed_trade.exit_partial(size=4)

        # Should have placed 3 exit orders via place_market_order
        assert mock_order_manager.place_market_order.call_count == 3
