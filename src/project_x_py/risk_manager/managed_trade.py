"""Managed trade context manager for risk-controlled trading."""

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from project_x_py.event_bus import EventType
from project_x_py.types import OrderSide, OrderStatus, OrderType
from project_x_py.types.protocols import OrderManagerProtocol, PositionManagerProtocol

if TYPE_CHECKING:
    from project_x_py.models import Order, Position

    from .core import RiskManager

logger = logging.getLogger(__name__)


class ManagedTrade:
    """Context manager for risk-managed trade execution.

    Automatically handles:
    - Position sizing based on risk parameters
    - Trade validation against risk rules
    - Stop-loss and take-profit attachment
    - Position monitoring and adjustment
    - Cleanup on exit
    """

    def __init__(
        self,
        risk_manager: "RiskManager",
        order_manager: OrderManagerProtocol,
        position_manager: PositionManagerProtocol,
        instrument_id: str,
        data_manager: Any | None = None,
        event_bus: Any | None = None,
        max_risk_percent: float | None = None,
        max_risk_amount: float | None = None,
    ):
        """Initialize managed trade.

        Args:
            risk_manager: Risk manager instance
            order_manager: Order manager instance
            position_manager: Position manager instance
            instrument_id: Instrument/contract ID to trade
            data_manager: Optional data manager for market price fetching
            event_bus: Optional event bus for event-driven waits
            max_risk_percent: Override max risk percentage
            max_risk_amount: Override max risk dollar amount
        """
        self.risk = risk_manager
        self.orders = order_manager
        self.positions = position_manager
        self.instrument_id = instrument_id
        self.data_manager = data_manager
        self.event_bus = event_bus
        self.max_risk_percent = max_risk_percent
        self.max_risk_amount = max_risk_amount

        # Track orders and positions created
        self._orders: list[Order] = []
        self._positions: list[Position] = []
        self._entry_order: Order | None = None
        self._stop_order: Order | None = None
        self._target_order: Order | None = None
        self._trade_result: dict[str, Any] | None = None
        self._risk_amount: float = 0.0

    async def __aenter__(self) -> "ManagedTrade":
        """Enter managed trade context."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        """Exit managed trade context with cleanup."""
        try:
            # Only cancel unfilled entry orders, NOT stop/target orders
            # Stop and target orders should remain active to protect the position
            for order in self._orders:
                # Only cancel working entry orders, not stop/target protective orders
                if (
                    order.is_working
                    and order != self._stop_order
                    and order != self._target_order
                ):
                    try:
                        await self.orders.cancel_order(order.id)
                        logger.info(f"Cancelled unfilled entry order {order.id}")
                    except Exception as e:
                        logger.error(f"Error cancelling order {order.id}: {e}")

            # Log trade summary
            if self._entry_order:
                active_stops = (
                    1 if self._stop_order and self._stop_order.is_working else 0
                )
                active_targets = (
                    1 if self._target_order and self._target_order.is_working else 0
                )
                logger.info(
                    f"Managed trade completed for {self.instrument_id}: "
                    f"Entry: {self._entry_order.status_str}, "
                    f"Positions: {len(self._positions)}, "
                    f"Active stops: {active_stops}, Active targets: {active_targets}"
                )

        except Exception as e:
            logger.error(f"Error in managed trade cleanup: {e}")

        # Don't suppress exceptions
        return False

    async def enter_long(
        self,
        entry_price: float | None = None,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        size: int | None = None,
        order_type: OrderType = OrderType.MARKET,
    ) -> dict[str, Any]:
        """Enter a long position with risk management.

        Args:
            entry_price: Limit order price (None for market)
            stop_loss: Stop loss price (auto-calculated if not provided)
            take_profit: Take profit price (calculated if not provided)
            size: Position size (calculated if not provided)
            order_type: Order type (default: MARKET)

        Returns:
            Dictionary with order details and risk metrics
        """
        # Prevent concurrent entries
        if self._entry_order:
            raise ValueError("Trade already has entry order")

        # Auto-calculate stop loss if not provided
        if stop_loss is None and self.risk.config.use_stop_loss:
            if entry_price is None:
                entry_price = await self._get_market_price()
            if entry_price is None:
                raise ValueError("Entry price required for stop loss calculation")
            stop_loss = await self.risk.calculate_stop_loss(
                entry_price=entry_price, side=OrderSide.BUY
            )

        # Use market price if no entry price
        if entry_price is None and order_type != OrderType.MARKET:
            raise ValueError("Entry price required for limit orders")

        # Calculate position size if not provided
        if size is None:
            if entry_price is None:
                # Get current market price from data manager
                entry_price = await self._get_market_price()

            if stop_loss is not None:  # Type guard for mypy
                sizing = await self.risk.calculate_position_size(
                    entry_price=entry_price,
                    stop_loss=stop_loss,
                    risk_percent=self.max_risk_percent,
                    risk_amount=self.max_risk_amount,
                )
                size = sizing["position_size"]
            else:
                # Use default size if no stop loss
                size = 1

        # Validate trade
        mock_order = self._create_mock_order(
            side=OrderSide.BUY,
            size=size,
            price=entry_price,
            order_type=order_type,
        )

        validation = await self.risk.validate_trade(mock_order)
        if not validation["is_valid"]:
            raise ValueError(f"Trade validation failed: {validation['reasons']}")

        # Place entry order
        if order_type == OrderType.MARKET:
            order_result = await self.orders.place_market_order(
                contract_id=self.instrument_id,
                side=OrderSide.BUY,
                size=size,
            )
        else:
            if entry_price is None:
                raise ValueError("Entry price is required for limit orders")
            order_result = await self.orders.place_limit_order(
                contract_id=self.instrument_id,
                side=OrderSide.BUY,
                size=size,
                limit_price=entry_price,
            )

        if order_result.success:
            # Get the actual order object
            orders = await self.orders.search_open_orders()
            self._entry_order = next(
                (o for o in orders if o.id == order_result.orderId), None
            )
            if self._entry_order:
                self._orders.append(self._entry_order)

        # Wait for fill if market order
        if order_type == OrderType.MARKET and self._entry_order:
            # Wait for market order to fill before proceeding
            await self._wait_for_order_fill(self._entry_order, timeout_seconds=10)

        # Get position and attach risk orders
        positions = await self.positions.get_all_positions()
        position = next(
            (p for p in positions if p.contractId == self.instrument_id), None
        )

        if position:
            self._positions.append(position)

            # Attach risk orders
            risk_orders = await self.risk.attach_risk_orders(
                position=position,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )

            if "bracket_order" in risk_orders:
                bracket = risk_orders["bracket_order"]
                # BracketOrderResponse has stop_order_id and target_order_id
                if bracket.stop_order_id:
                    # Get the actual order object
                    orders = await self.orders.search_open_orders()
                    self._stop_order = next(
                        (o for o in orders if o.id == bracket.stop_order_id), None
                    )
                    if self._stop_order:
                        self._orders.append(self._stop_order)
                if bracket.target_order_id:
                    # Get the actual order object
                    orders = await self.orders.search_open_orders()
                    self._target_order = next(
                        (o for o in orders if o.id == bracket.target_order_id), None
                    )
                    if self._target_order:
                        self._orders.append(self._target_order)

        return {
            "entry_order": self._entry_order,
            "stop_order": self._stop_order,
            "target_order": self._target_order,
            "position": position,
            "size": size,
            "risk_amount": size * abs(entry_price - (stop_loss or 0.0))
            if entry_price and stop_loss
            else None,
            "validation": validation,
        }

    async def enter_short(
        self,
        entry_price: float | None = None,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        size: int | None = None,
        order_type: OrderType = OrderType.MARKET,
    ) -> dict[str, Any]:
        """Enter a short position with risk management.

        Args:
            entry_price: Limit order price (None for market)
            stop_loss: Stop loss price (required)
            take_profit: Take profit price (calculated if not provided)
            size: Position size (calculated if not provided)
            order_type: Order type (default: MARKET)

        Returns:
            Dictionary with order details and risk metrics
        """
        # Prevent concurrent entries
        if self._entry_order:
            raise ValueError("Trade already has entry order")

        if stop_loss is None:
            raise ValueError("Stop loss is required for risk management")

        # Use market price if no entry price
        if entry_price is None and order_type != OrderType.MARKET:
            raise ValueError("Entry price required for limit orders")

        # Calculate position size if not provided
        if size is None:
            if entry_price is None:
                # Get current market price
                entry_price = await self._get_market_price()

            if stop_loss is not None:  # Type guard for mypy
                sizing = await self.risk.calculate_position_size(
                    entry_price=entry_price,
                    stop_loss=stop_loss,
                    risk_percent=self.max_risk_percent,
                    risk_amount=self.max_risk_amount,
                )
                size = sizing["position_size"]

        # Validate trade
        mock_order = self._create_mock_order(
            side=OrderSide.SELL,
            size=size,
            price=entry_price,
            order_type=order_type,
        )

        validation = await self.risk.validate_trade(mock_order)
        if not validation["is_valid"]:
            raise ValueError(f"Trade validation failed: {validation['reasons']}")

        # Place entry order
        if order_type == OrderType.MARKET:
            order_result = await self.orders.place_market_order(
                contract_id=self.instrument_id,
                side=OrderSide.SELL,
                size=size,
            )
        else:
            if entry_price is None:
                raise ValueError("Entry price is required for limit orders")
            order_result = await self.orders.place_limit_order(
                contract_id=self.instrument_id,
                side=OrderSide.SELL,
                size=size,
                limit_price=entry_price,
            )

        if order_result.success:
            # Get the actual order object
            orders = await self.orders.search_open_orders()
            self._entry_order = next(
                (o for o in orders if o.id == order_result.orderId), None
            )
            if self._entry_order:
                self._orders.append(self._entry_order)

        # Wait for fill if market order
        if order_type == OrderType.MARKET and self._entry_order:
            # Wait for market order to fill before proceeding
            await self._wait_for_order_fill(self._entry_order, timeout_seconds=10)

        # Get position and attach risk orders
        positions = await self.positions.get_all_positions()
        position = next(
            (p for p in positions if p.contractId == self.instrument_id), None
        )

        if position:
            self._positions.append(position)

            # Attach risk orders
            risk_orders = await self.risk.attach_risk_orders(
                position=position,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )

            if "bracket_order" in risk_orders:
                bracket = risk_orders["bracket_order"]
                # BracketOrderResponse has stop_order_id and target_order_id
                if bracket.stop_order_id:
                    # Get the actual order object
                    orders = await self.orders.search_open_orders()
                    self._stop_order = next(
                        (o for o in orders if o.id == bracket.stop_order_id), None
                    )
                    if self._stop_order:
                        self._orders.append(self._stop_order)
                if bracket.target_order_id:
                    # Get the actual order object
                    orders = await self.orders.search_open_orders()
                    self._target_order = next(
                        (o for o in orders if o.id == bracket.target_order_id), None
                    )
                    if self._target_order:
                        self._orders.append(self._target_order)

        return {
            "entry_order": self._entry_order,
            "stop_order": self._stop_order,
            "target_order": self._target_order,
            "position": position,
            "size": size,
            "risk_amount": size * abs(entry_price - (stop_loss or 0.0))
            if entry_price and stop_loss
            else None,
            "validation": validation,
        }

    async def scale_in(
        self,
        additional_size: int,
        new_stop_loss: float | None = None,
    ) -> dict[str, Any]:
        """Scale into existing position with risk checks.

        Args:
            additional_size: Additional contracts to add
            new_stop_loss: New stop loss for entire position

        Returns:
            Dictionary with scale-in details
        """
        if not self.risk.config.scale_in_enabled:
            raise ValueError("Scale-in is disabled in risk configuration")

        if not self._positions:
            raise ValueError("No existing position to scale into")

        # Validate additional size
        position = self._positions[0]
        is_long = position.is_long

        # Place scale-in order
        order_result = await self.orders.place_market_order(
            contract_id=self.instrument_id,
            side=OrderSide.BUY if is_long else OrderSide.SELL,
            size=additional_size,
        )

        if order_result.success:
            # Get the actual order object
            orders = await self.orders.search_open_orders()
            scale_order = next(
                (o for o in orders if o.id == order_result.orderId), None
            )
            if scale_order:
                self._orders.append(scale_order)

        # Adjust stop loss if provided
        if new_stop_loss and self._stop_order:
            await self.risk.adjust_stops(
                position=position,
                new_stop=new_stop_loss,
                order_id=str(self._stop_order.id),
            )

        return {
            "scale_order": scale_order if "scale_order" in locals() else None,
            "new_position_size": position.size + additional_size,
            "stop_adjusted": new_stop_loss is not None,
        }

    async def scale_out(
        self,
        exit_size: int,
        limit_price: float | None = None,
    ) -> dict[str, Any]:
        """Scale out of position with partial exit.

        Args:
            exit_size: Number of contracts to exit
            limit_price: Limit price for exit (market if None)

        Returns:
            Dictionary with scale-out details
        """
        if not self.risk.config.scale_out_enabled:
            raise ValueError("Scale-out is disabled in risk configuration")

        if not self._positions:
            raise ValueError("No position to scale out of")

        position = self._positions[0]
        is_long = position.is_long

        if exit_size > position.size:
            raise ValueError("Exit size exceeds position size")

        # Place scale-out order
        if limit_price:
            order_result = await self.orders.place_limit_order(
                contract_id=self.instrument_id,
                side=OrderSide.SELL if is_long else OrderSide.BUY,
                size=exit_size,
                limit_price=limit_price,
            )
        else:
            order_result = await self.orders.place_market_order(
                contract_id=self.instrument_id,
                side=OrderSide.SELL if is_long else OrderSide.BUY,
                size=exit_size,
            )

        if order_result.success:
            # Get the actual order object
            orders = await self.orders.search_open_orders()
            scale_order = next(
                (o for o in orders if o.id == order_result.orderId), None
            )
            if scale_order:
                self._orders.append(scale_order)

        return {
            "exit_order": order_result,
            "remaining_size": position.size - exit_size,
            "exit_type": "limit" if limit_price else "market",
        }

    async def adjust_stop(self, new_stop_loss: float) -> bool:
        """Adjust stop loss for current position.

        Args:
            new_stop_loss: New stop loss price

        Returns:
            True if adjustment successful
        """
        if not self._positions or not self._stop_order:
            logger.warning("No position or stop order to adjust")
            return False

        return await self.risk.adjust_stops(
            position=self._positions[0],
            new_stop=new_stop_loss,
            order_id=str(self._stop_order.id),
        )

    async def close_position(self) -> dict[str, Any] | None:
        """Close entire position at market.

        Returns:
            Dictionary with close details or None if no position
        """
        if not self._positions:
            return None

        position = self._positions[0]
        is_long = position.is_long

        # Cancel existing stop/target orders
        for order in [self._stop_order, self._target_order]:
            if order and order.is_working:
                try:
                    await self.orders.cancel_order(order.id)
                except Exception as e:
                    logger.error(f"Error cancelling order: {e}")

        # Place market order to close
        close_result = await self.orders.place_market_order(
            contract_id=self.instrument_id,
            side=OrderSide.SELL if is_long else OrderSide.BUY,
            size=position.size,
        )

        if close_result.success:
            # Get the actual order object
            orders = await self.orders.search_open_orders()
            close_order = next(
                (o for o in orders if o.id == close_result.orderId), None
            )
            if close_order:
                self._orders.append(close_order)

        return {
            "close_order": close_order if "close_order" in locals() else None,
            "closed_size": position.size,
            "orders_cancelled": [
                o.id
                for o in [self._stop_order, self._target_order]
                if o and o.is_working
            ],
        }

    def _create_mock_order(
        self,
        side: OrderSide,
        size: int,
        price: float | None,
        order_type: OrderType,
    ) -> "Order":
        """Create mock order for validation."""
        # This is a simplified mock - adjust based on actual Order model
        from datetime import datetime

        from project_x_py.models import Order

        # Create a proper Order instance
        return Order(
            id=0,  # Mock ID
            accountId=0,  # Mock account ID
            contractId=self.instrument_id,
            creationTimestamp=datetime.now().isoformat(),
            updateTimestamp=None,
            status=6,  # Pending
            type=order_type.value if hasattr(order_type, "value") else order_type,
            side=side.value if hasattr(side, "value") else side,
            size=size,
            limitPrice=price,
            stopPrice=None,
            fillVolume=None,
            filledPrice=None,
            customTag=None,
        )

    async def _get_market_price(self) -> float:
        """Get current market price for instrument.

        Returns:
            Current market price as a float

        Raises:
            RuntimeError: If unable to fetch market price
        """
        if not self.data_manager:
            raise RuntimeError(
                "No data manager available for market price fetching. "
                "Please provide entry_price explicitly or initialize ManagedTrade with a data_manager."
            )

        # Try to get the most recent price from smallest available timeframe
        timeframes_to_try = ["1sec", "15sec", "1min", "5min"]

        for timeframe in timeframes_to_try:
            try:
                # Get the most recent bar
                data = await self.data_manager.get_data(timeframe, bars=1)

                if data is not None and not data.is_empty():
                    # Return the close price of the most recent bar
                    close_price = data["close"].tail(1)[0]
                    return float(close_price)
            except Exception:
                # Try next timeframe if this one fails
                continue

        # If we still don't have data, try to get current price directly
        try:
            current_price = await self.data_manager.get_current_price()
            if current_price is not None:
                return float(current_price)
        except Exception:
            pass

        raise RuntimeError(
            f"Unable to fetch current market price for {self.instrument_id} - no data available. "
            "Please ensure data manager is connected and receiving data."
        )

    async def _wait_for_order_fill(
        self, order: "Order", timeout_seconds: int = 10
    ) -> bool:
        """Waits for an order to fill, using an event-driven approach if possible."""
        if not self.event_bus:
            logger.warning(
                "No event_bus available on ManagedTrade, falling back to polling for order fill."
            )
            return await self._poll_for_order_fill(order, timeout_seconds)

        fill_event = asyncio.Event()
        filled_successfully = False

        async def order_fill_handler(event: Any) -> None:
            nonlocal filled_successfully
            # Extract data from Event object
            event_data = event.data if hasattr(event, "data") else event
            if isinstance(event_data, dict):
                # Check both direct order_id and order.id from Order object
                event_order_id = event_data.get("order_id")
                if not event_order_id and "order" in event_data:
                    order_obj = event_data.get("order")
                    if order_obj and hasattr(order_obj, "id"):
                        event_order_id = order_obj.id
                if event_order_id == order.id:
                    filled_successfully = True
                    fill_event.set()

        async def order_terminal_handler(event: Any) -> None:
            nonlocal filled_successfully
            # Extract data from Event object
            event_data = event.data if hasattr(event, "data") else event
            if isinstance(event_data, dict):
                # Check both direct order_id and order.id from Order object
                event_order_id = event_data.get("order_id")
                if not event_order_id and "order" in event_data:
                    order_obj = event_data.get("order")
                    if order_obj and hasattr(order_obj, "id"):
                        event_order_id = order_obj.id
                if event_order_id == order.id:
                    filled_successfully = False
                    fill_event.set()

        await self.event_bus.on(EventType.ORDER_FILLED, order_fill_handler)
        await self.event_bus.on(EventType.ORDER_CANCELLED, order_terminal_handler)
        await self.event_bus.on(EventType.ORDER_REJECTED, order_terminal_handler)

        try:
            await asyncio.wait_for(fill_event.wait(), timeout=timeout_seconds)
        except TimeoutError:
            logger.warning(f"Timeout waiting for order {order.id} to fill via event.")
            filled_successfully = False
        finally:
            # Important: Clean up the event handlers to prevent memory leaks
            if hasattr(self.event_bus, "remove_callback"):
                await self.event_bus.remove_callback(
                    EventType.ORDER_FILLED, order_fill_handler
                )
                await self.event_bus.remove_callback(
                    EventType.ORDER_CANCELLED, order_terminal_handler
                )
                await self.event_bus.remove_callback(
                    EventType.ORDER_REJECTED, order_terminal_handler
                )

        return filled_successfully

    async def _poll_for_order_fill(
        self, order: "Order", timeout_seconds: int = 10
    ) -> bool:
        """Wait for an order to fill by polling its status."""
        start_time = asyncio.get_event_loop().time()
        check_interval = 0.5  # Check every 500ms

        while (asyncio.get_event_loop().time() - start_time) < timeout_seconds:
            try:
                # Get updated order status
                orders = await self.orders.search_open_orders()
                updated_order = next((o for o in orders if o.id == order.id), None)

                if updated_order:
                    # Update our reference
                    if updated_order.is_filled:
                        logger.info(f"Order {order.id} filled successfully")
                        return True
                    elif updated_order.is_terminal and not updated_order.is_filled:
                        logger.warning(
                            f"Order {order.id} terminated without fill: {updated_order.status_str}"
                        )
                        return False
                else:
                    # Order not found in open orders, might be filled
                    # Check if position exists
                    positions = await self.positions.get_all_positions()
                    position = next(
                        (p for p in positions if p.contractId == self.instrument_id),
                        None,
                    )
                    if position:
                        logger.info(
                            f"Order {order.id} appears to be filled (position found)"
                        )
                        return True

                await asyncio.sleep(check_interval)
            except Exception as e:
                logger.error(f"Error checking order fill status: {e}")
                await asyncio.sleep(check_interval)

        logger.warning(f"Timeout waiting for order {order.id} to fill")
        return False

    async def wait_for_fill(self, timeout: float = 30.0) -> bool:
        """Wait for entry order to be filled."""
        if not self._entry_order:
            return False

        import time

        start_time = time.time()
        while time.time() - start_time < timeout:
            orders = await self.orders.search_open_orders()
            order = next((o for o in orders if o.id == self._entry_order.id), None)
            if order and order.status in [2, 3]:  # Filled or partially filled
                return True
            await asyncio.sleep(1)

        return False

    async def monitor_position(self) -> dict[str, Any]:
        """Monitor and return current position status."""
        if not self._positions:
            positions = await self.positions.get_all_positions()
            self._positions = [
                p for p in positions if p.contractId == self.instrument_id
            ]

        if self._positions:
            position = self._positions[0]
            return {
                "position": position,
                "pnl": getattr(position, "unrealized", 0),
                "size": position.size,
            }

        return {"position": None, "pnl": 0, "size": 0}

    async def adjust_stop_loss(self, new_stop: float) -> bool:
        """Adjust stop loss order to new price."""
        if not self._stop_order:
            return False

        try:
            await self.orders.modify_order(
                order_id=self._stop_order.id, stop_price=new_stop
            )
            self._stop_order.stopPrice = new_stop
            return True
        except Exception:
            return False

    async def get_trade_summary(self) -> dict[str, Any]:
        """Get summary of current trade."""
        position_status = await self.monitor_position()

        # Extract summary details
        entry_price = None
        size = None
        status = "pending"

        if self._entry_order:
            entry_price = getattr(self._entry_order, "limitPrice", None) or getattr(
                self._entry_order, "price", None
            )
            size = getattr(self._entry_order, "size", None)
            order_status = getattr(self._entry_order, "status", None)
            if order_status == OrderStatus.FILLED.value or order_status == 2:
                status = "open"

        if self._trade_result:
            status = "closed"

        position = position_status.get("position")
        unrealized_pnl = 0.0
        if position:
            unrealized_pnl = getattr(position, "unrealized", 0.0)
            if not size:
                size = getattr(position, "size", None)

        return {
            "instrument": self.instrument_id,
            "entry_order": self._entry_order,
            "entry_price": entry_price,
            "size": size,
            "stop_order": self._stop_order,
            "target_order": self._target_order,
            "position": position,
            "pnl": position_status["pnl"],
            "unrealized_pnl": unrealized_pnl,
            "risk_amount": getattr(self, "_risk_amount", 0),
            "trade_result": getattr(self, "_trade_result", None),
            "status": status,
        }

    async def emergency_exit(self) -> bool:
        """Emergency exit all positions and orders."""
        try:
            # Cancel all orders
            import contextlib

            for order in self._orders:
                if order and hasattr(order, "id"):
                    with contextlib.suppress(Exception):
                        await self.orders.cancel_order(order.id)

            # Close position if exists
            if self._positions:
                await self.close_position()

            return True
        except Exception:
            return False

    async def enter_market(
        self, size: int, side: str = "BUY", stop_loss: float | None = None
    ) -> dict[str, Any]:
        """Enter position with market order."""
        return (
            await self.enter_long(size=size, stop_loss=stop_loss)
            if side == "BUY"
            else await self.enter_short(size=size, stop_loss=stop_loss)
        )

    async def enter_bracket(
        self, size: int, entry_price: float, stop_loss: float, take_profit: float
    ) -> dict[str, Any]:
        """Enter position with bracket order."""
        return await self.enter_long(
            size=size,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

    async def exit_partial(self, size: int) -> bool:
        """Exit partial position."""
        if not self._positions or self._positions[0].size < size:
            return False

        try:
            position = self._positions[0]
            # Use integer values for side: 1=BUY, 2=SELL
            side = 2 if position.is_long else 1
            await self.orders.place_market_order(
                contract_id=self.instrument_id, side=side, size=size
            )
            return True
        except Exception:
            return False

    def is_filled(self) -> bool:
        """Check if entry order is FULLY filled."""
        if not self._entry_order:
            return False
        # Check if fully filled (not just partially)
        if self._entry_order.status == 2:  # FILLED status
            # Check if filled_quantity equals size for full fill
            if hasattr(self._entry_order, "filled_quantity") and hasattr(
                self._entry_order, "size"
            ):
                return getattr(self._entry_order, "filled_quantity", 0) == getattr(
                    self._entry_order, "size", 0
                )
            return True  # If no quantity info, assume filled means fully filled
        return False

    async def check_trailing_stop(self) -> bool:
        """Check and adjust trailing stop if needed."""
        if not self._positions or not self._stop_order:
            return False

        # Get current price (simplified for now)
        current_price = await self._get_current_market_price()
        if not current_price:
            return False

        position = self._positions[0]
        risk_amount = getattr(self, "_risk_amount", 100)
        # For long positions
        if position.is_long:
            trail_distance = risk_amount / position.size if position.size else 100
            new_stop = current_price - trail_distance
            if (
                self._stop_order
                and self._stop_order.stopPrice is not None
                and new_stop > self._stop_order.stopPrice
            ):
                return await self.adjust_stop_loss(new_stop)
        else:
            # For short positions
            trail_distance = risk_amount / position.size if position.size else 100
            new_stop = current_price + trail_distance
            if (
                self._stop_order
                and self._stop_order.stopPrice
                and new_stop < self._stop_order.stopPrice
            ):
                return await self.adjust_stop_loss(new_stop)

        return False

    async def _get_current_market_price(self) -> float | None:
        """Get current market price."""
        try:
            if self.data_manager:
                return await self.data_manager.get_latest_price(self.instrument_id)
            return None
        except Exception:
            return None

    async def get_summary(self) -> dict[str, Any]:
        """Get comprehensive trade summary."""
        return await self.get_trade_summary()

    async def record_trade_result(self, result: dict[str, Any]) -> None:
        """Record trade result for performance tracking."""
        self._trade_result = result

        # Extract entry details from entry order if available
        entry_price = result.get("entry_price", 0)
        size = result.get("size", 0)
        side = result.get("side", 1)

        if self._entry_order:
            if entry_price == 0:
                entry_price = getattr(self._entry_order, "limitPrice", 0) or getattr(
                    self._entry_order, "price", 0
                )
            if size == 0:
                size = getattr(self._entry_order, "size", 0)
            if side == 1:  # Default value
                order_side = getattr(self._entry_order, "side", OrderSide.BUY.value)
                # Convert to OrderSide enum if it's an integer
                if isinstance(order_side, int):
                    side = OrderSide(order_side)
                else:
                    side = order_side

        # Add to risk manager's trade history
        if self.risk and hasattr(self.risk, "add_trade_result"):
            await self.risk.add_trade_result(
                instrument=self.instrument_id,
                pnl=result.get("pnl", 0),
                entry_price=entry_price,
                exit_price=result.get("exit_price", 0),
                size=size,
                side=side,
            )

        # Send to statistics tracking if available
        if hasattr(self, "event_bus") and self.event_bus:
            try:
                from project_x_py.event_bus import Event, EventType
            except ImportError:
                # Events module not available
                return
            await self.event_bus.emit(
                Event(type=EventType.POSITION_CLOSED, data=result)
            )

    async def calculate_position_size(
        self,
        entry_price: float,
        stop_loss: float,
        risk_percent: float | None = None,
        risk_amount: float | None = None,
    ) -> int:
        """Calculate position size based on risk parameters."""
        # Use risk overrides if not provided
        if risk_percent is None and self.max_risk_percent is not None:
            risk_percent = self.max_risk_percent
        if risk_amount is None and self.max_risk_amount is not None:
            risk_amount = self.max_risk_amount

        result = await self.risk.calculate_position_size(
            entry_price=entry_price,
            stop_loss=stop_loss,
            risk_percent=risk_percent,
            risk_amount=risk_amount,
        )
        # Handle both dict and object return types
        if isinstance(result, dict):
            return result["position_size"]
        # This line is actually unreachable since calculate_position_size always returns dict
        # But kept for defensive programming
        return getattr(result, "position_size", 1)  # type: ignore[unreachable]

    async def _get_account_balance(self) -> float:
        """Get current account balance."""
        # Try to get from risk manager's client
        if hasattr(self.risk, "client") and self.risk.client:
            accounts = await self.risk.client.list_accounts()
            if accounts:
                return float(accounts[0].balance)
        return 100000.0  # Default for testing
