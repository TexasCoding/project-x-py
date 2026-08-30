"""
Order lifecycle tracking and management for ProjectX SDK v3.0.0.

DEPRECATED: This module is deprecated as of v3.1.14 and will be removed in v4.0.0.
            Use TradingSuite.track_order() and TradingSuite.order_chain() instead.

Author: SDK v3.0.0
Date: 2025-08-04

Overview:
    Provides a context manager for comprehensive order lifecycle tracking with
    automatic state management, async waiting mechanisms, and simplified error
    handling. Eliminates the need for manual order state tracking in strategies.

Key Features:
    - Context manager for automatic cleanup
    - Async waiting for order fills/status changes
    - Automatic timeout handling
    - Order modification and cancellation helpers
    - Order chain builder for complex orders
    - Common order templates
    - Integration with EventBus for real-time updates

Example Usage:
    ```python
    # Simple order tracking
    async with suite.track_order() as tracker:
        order = await suite.orders.place_limit_order(
            contract_id=instrument.id,
            side=OrderSide.BUY,
            size=1,
            price=current_price - 10,
        )

        try:
            filled_order = await tracker.wait_for_fill(timeout=60)
            print(f"Order filled at {filled_order.filledPrice}")
        except TimeoutError:
            await tracker.modify_or_cancel(new_price=current_price - 5)

    # Order chain builder
    order_chain = (
        suite.orders.market_order(size=1)
        .with_stop_loss(offset=50)
        .with_take_profit(offset=100)
        .with_trail_stop(offset=25, trigger_offset=50)
    )

    result = await order_chain.execute()
    ```

See Also:
    - `order_manager.core.OrderManager`
    - `event_bus.EventBus`
    - `models.Order`
"""

import asyncio
import logging
from types import TracebackType
from typing import TYPE_CHECKING, Any, Union

from project_x_py.event_bus import EventType
from project_x_py.models import BracketOrderResponse, Order, OrderPlaceResponse
from project_x_py.utils.deprecation import deprecated, deprecated_class

if TYPE_CHECKING:
    from project_x_py.trading_suite import TradingSuite

logger = logging.getLogger(__name__)


@deprecated_class(
    reason="Use TradingSuite.track_order() for integrated order tracking",
    version="3.1.14",
    removal_version="5.0.0",
    replacement="TradingSuite.track_order()",
)
class OrderTracker:
    """
    Context manager for comprehensive order lifecycle tracking.

    DEPRECATED: Use TradingSuite.track_order() instead. Will be removed in v4.0.0.

    Provides automatic order state management with async waiting capabilities,
    eliminating the need for manual order status polling and complex state
    tracking in trading strategies.

    Features:
        - Automatic order status tracking via EventBus
        - Async waiting for specific order states
        - Timeout handling with automatic cleanup
        - Order modification and cancellation helpers
        - Fill detection and reporting
        - Thread-safe operation
    """

    def __init__(self, trading_suite: "TradingSuite", order: Order | None = None):
        """
        Initialize OrderTracker.

        Args:
            trading_suite: TradingSuite instance for access to components
            order: Optional order to track immediately
        """
        self.suite = trading_suite
        self.order_manager = trading_suite.orders
        self.event_bus = trading_suite.events
        self.order = order
        self.order_id: int | None = order.id if order else None

        # State tracking
        self._fill_event = asyncio.Event()
        self._status_events: dict[int, asyncio.Event] = {}
        self._current_status: int | None = order.status if order else None
        self._filled_order: Order | None = None
        self._error: Exception | None = None

        # Event handlers
        self._event_handlers: list[tuple[EventType, Any]] = []

    async def __aenter__(self) -> "OrderTracker":
        """Enter the context manager and set up tracking."""
        # Register event handlers
        await self._setup_event_handlers()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit the context manager and clean up."""
        await self.cleanup()

    async def _setup_event_handlers(self) -> None:
        """Set up EventBus handlers for order tracking."""

        # Handler for order fills
        async def on_fill(data: dict[str, Any]) -> None:
            order = data.get("order")
            if order and order.id == self.order_id:
                self._filled_order = order
                self._current_status = 2  # FILLED
                self._fill_event.set()

        # Handler for status changes
        async def on_status_change(data: dict[str, Any]) -> None:
            order = data.get("order")
            if order and order.id == self.order_id:
                new_status = order.status
                self._current_status = new_status

                # Set status-specific events
                if new_status in self._status_events:
                    self._status_events[new_status].set()

                # Handle terminal states
                if new_status in (3, 4, 5):  # CANCELLED, EXPIRED, REJECTED
                    self._error = OrderLifecycleError(
                        f"Order {self.order_id} reached terminal state: {new_status}"
                    )

        # Register handlers
        self._event_handlers = [
            (EventType.ORDER_FILLED, on_fill),
            (EventType.ORDER_CANCELLED, on_status_change),
            (EventType.ORDER_REJECTED, on_status_change),
            (EventType.ORDER_EXPIRED, on_status_change),
        ]

        for event_type, handler in self._event_handlers:
            await self.event_bus.on(event_type, handler)

    async def cleanup(self) -> None:
        """Clean up event handlers and resources."""
        # Unregister event handlers
        for event_type, handler in self._event_handlers:
            await self.event_bus.off(event_type, handler)

        self._event_handlers.clear()

    def track(self, order: Union[Order, OrderPlaceResponse, int]) -> "OrderTracker":
        """
        Start tracking a specific order.

        Args:
            order: Order object, OrderPlaceResponse, or order ID to track

        Returns:
            Self for method chaining
        """
        if isinstance(order, Order):
            self.order = order
            self.order_id = order.id
            self._current_status = order.status
        elif isinstance(order, OrderPlaceResponse):
            self.order_id = order.orderId
            self._current_status = 1  # OPEN (assumed for new orders)
        else:  # int
            self.order_id = order
            self._current_status = None

        return self

    async def wait_for_fill(self, timeout: float = 30.0) -> Order:
        """
        Wait for the order to be filled.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            Filled Order object

        Raises:
            TimeoutError: If order is not filled within timeout
            OrderLifecycleError: If order reaches terminal non-filled state
        """
        if not self.order_id:
            raise ValueError("No order is being tracked")

        try:
            await asyncio.wait_for(self._fill_event.wait(), timeout=timeout)

            if self._error:
                raise self._error

            if self._filled_order:
                return self._filled_order
            else:
                # Fetch latest order data
                order = await self.order_manager.get_order_by_id(self.order_id)
                if order and order.status == 2:  # FILLED
                    return order
                else:
                    raise OrderLifecycleError(
                        "Order fill event received but order not filled"
                    )

        except TimeoutError:
            raise TimeoutError(
                f"Order {self.order_id} not filled within {timeout} seconds"
            ) from None

    async def wait_for_status(self, status: int, timeout: float = 30.0) -> Order:
        """
        Wait for the order to reach a specific status.

        Args:
            status: Target order status to wait for
            timeout: Maximum time to wait in seconds

        Returns:
            Order object with the target status

        Raises:
            TimeoutError: If status is not reached within timeout
            OrderLifecycleError: If order reaches incompatible terminal state
        """
        if not self.order_id:
            raise ValueError("No order is being tracked")

        # Create event for this status if not exists
        if status not in self._status_events:
            self._status_events[status] = asyncio.Event()

        # Check current status before waiting
        if self._current_status == status:
            order = await self.order_manager.get_order_by_id(self.order_id)
            if order and order.status == status:
                return order

        # Wait for the event
        try:
            await asyncio.wait_for(self._status_events[status].wait(), timeout=timeout)
        except TimeoutError:
            # After timeout, check the status one last time via API
            order = await self.order_manager.get_order_by_id(self.order_id)
            if order and order.status == status:
                return order
            raise TimeoutError(
                f"Order {self.order_id} did not reach status {status} within {timeout} seconds"
            ) from None

        # After event is received
        if self._error and status != self._current_status:
            raise self._error

        order = await self.order_manager.get_order_by_id(self.order_id)
        if order and order.status == status:
            return order
        else:
            # This can happen if event fires but API state is not yet consistent,
            # or if another status update arrived quickly.
            raise OrderLifecycleError(
                f"Status event received but order not in expected state {status}. Current state: {order.status if order else 'not found'}"
            )

    async def modify_or_cancel(
        self, new_price: float | None = None, new_size: int | None = None
    ) -> bool:
        """
        Attempt to modify the order, or cancel if modification fails.

        Args:
            new_price: New limit price for the order
            new_size: New size for the order

        Returns:
            True if modification succeeded, False if order was cancelled
        """
        if not self.order_id:
            raise ValueError("No order is being tracked")

        try:
            if new_price is not None or new_size is not None:
                # Attempt modification
                success = await self.order_manager.modify_order(
                    self.order_id, limit_price=new_price, size=new_size
                )

                if success:
                    logger.info(f"Order {self.order_id} modified successfully")
                    return True

        except Exception as e:
            logger.warning(f"Failed to modify order {self.order_id}: {e}")

        # Modification failed, cancel the order
        try:
            await self.order_manager.cancel_order(self.order_id)
            logger.info(f"Order {self.order_id} cancelled")
            return False
        except Exception as e:
            logger.error(f"Failed to cancel order {self.order_id}: {e}")
            raise

    async def get_current_status(self) -> Order | None:
        """
        Get the current order status.

        Returns:
            Current Order object or None if not found
        """
        if not self.order_id:
            return None

        return await self.order_manager.get_order_by_id(self.order_id)

    @property
    def is_filled(self) -> bool:
        """Check if the order has been filled."""
        return self._current_status == 2

    @property
    def is_working(self) -> bool:
        """Check if the order is still working (open or pending)."""
        return self._current_status in (1, 6)  # OPEN or PENDING

    @property
    def is_terminal(self) -> bool:
        """Check if the order is in a terminal state."""
        return self._current_status in (
            2,
            3,
            4,
            5,
        )  # FILLED, CANCELLED, EXPIRED, REJECTED


@deprecated_class(
    reason="Use TradingSuite.order_chain() for integrated order chain building",
    version="3.1.14",
    removal_version="5.0.0",
    replacement="TradingSuite.order_chain()",
)
class OrderChainBuilder:
    """
    Fluent API for building complex order chains.

    DEPRECATED: Use TradingSuite.order_chain() instead. Will be removed in v4.0.0.

    Allows creating multi-part orders (entry + stops + targets) with a
    clean, chainable syntax that's easy to read and maintain.

    Example:
        ```python
        order_chain = (
            OrderChainBuilder(suite)
            .market_order(size=2)
            .with_stop_loss(offset=50)
            .with_take_profit(offset=100)
            .with_trail_stop(offset=25, trigger_offset=50)
        )

        result = await order_chain.execute()
        ```
    """

    def __init__(self, trading_suite: "TradingSuite"):
        """Initialize the order chain builder."""
        self.suite = trading_suite
        self.order_manager = trading_suite.orders

        # Order configuration
        self.entry_type = "market"
        self.side: int | None = None
        self.size: int | None = None
        self.entry_price: float | None = None
        self.contract_id: str | None = None

        # Risk orders
        self.stop_loss: dict[str, Any] | None = None
        self.take_profit: dict[str, Any] | None = None
        self.trail_stop: dict[str, Any] | None = None

    def market_order(self, size: int, side: int = 0) -> "OrderChainBuilder":
        """Configure a market order as entry."""
        self.entry_type = "market"
        self.size = size
        self.side = side
        return self

    def limit_order(
        self, size: int, price: float, side: int = 0
    ) -> "OrderChainBuilder":
        """Configure a limit order as entry."""
        self.entry_type = "limit"
        self.size = size
        self.entry_price = price
        self.side = side
        return self

    def stop_order(self, size: int, price: float, side: int = 0) -> "OrderChainBuilder":
        """Configure a stop order as entry."""
        self.entry_type = "stop"
        self.size = size
        self.entry_price = price
        self.side = side
        return self

    def for_instrument(self, contract_id: str) -> "OrderChainBuilder":
        """Set the instrument for the order chain."""
        self.contract_id = contract_id
        return self

    def with_stop_loss(
        self, offset: float | None = None, price: float | None = None
    ) -> "OrderChainBuilder":
        """Add a stop loss to the order chain."""
        self.stop_loss = {"offset": offset, "price": price}
        return self

    def with_take_profit(
        self,
        offset: float | None = None,
        price: float | None = None,
    ) -> "OrderChainBuilder":
        """Add a take profit to the order chain."""
        self.take_profit = {"offset": offset, "price": price}
        return self

    def with_trail_stop(
        self, offset: float, trigger_offset: float | None = None
    ) -> "OrderChainBuilder":
        """Add a trailing stop to the order chain."""
        self.trail_stop = {"offset": offset, "trigger_offset": trigger_offset}
        return self

    async def execute(self) -> BracketOrderResponse:
        """
        Execute the order chain.

        Returns:
            BracketOrderResponse with all order IDs

        Raises:
            ValueError: If required parameters are missing
            OrderLifecycleError: If order placement fails
        """
        # Validate configuration
        if self.size is None:
            raise ValueError("Order size is required")
        if self.side is None:
            raise ValueError("Order side is required")
        if not self.contract_id and not self.suite.instrument_id:
            raise ValueError("Contract ID is required")

        contract_id = self.contract_id or self.suite.instrument_id
        if not contract_id:
            raise ValueError("Contract ID is required")

        # Calculate risk order prices if needed
        current_price = await self.suite.data.get_current_price()
        if not current_price:
            raise ValueError("Cannot get current price for risk calculations")

        # Build bracket order parameters
        if self.entry_type == "market":
            # For market orders, use current price for risk calculations
            entry_price = current_price
        else:
            entry_price = self.entry_price or current_price

        # Calculate stop loss price
        stop_loss_price = None
        if self.stop_loss:
            if self.stop_loss["price"]:
                stop_loss_price = self.stop_loss["price"]
            elif self.stop_loss["offset"]:
                if self.side == 0:  # BUY
                    stop_loss_price = entry_price - self.stop_loss["offset"]
                else:  # SELL
                    stop_loss_price = entry_price + self.stop_loss["offset"]

        # Calculate take profit price
        take_profit_price = None
        if self.take_profit:
            if self.take_profit["price"]:
                take_profit_price = self.take_profit["price"]
            elif self.take_profit["offset"]:
                if self.side == 0:  # BUY
                    take_profit_price = entry_price + self.take_profit["offset"]
                else:  # SELL
                    take_profit_price = entry_price - self.take_profit["offset"]

        # Execute the appropriate order type
        if stop_loss_price or take_profit_price:
            # Use bracket order
            # For market orders, pass the current price as entry_price for validation
            bracket_entry_price = (
                entry_price if self.entry_type != "market" else current_price
            )
            assert self.side is not None  # Already checked above
            assert self.size is not None  # Already checked above
            result = await self.order_manager.place_bracket_order(
                contract_id=contract_id,
                side=self.side,
                size=self.size,
                entry_price=bracket_entry_price,
                stop_loss_price=stop_loss_price or 0.0,
                take_profit_price=take_profit_price or 0.0,
                entry_type=self.entry_type,
            )

            # Add trailing stop if configured
            if self.trail_stop and result.success and result.stop_order_id:
                logger.info(
                    f"Replacing stop order {result.stop_order_id} with trailing stop."
                )
                try:
                    await self.order_manager.cancel_order(result.stop_order_id)
                    trail_offset = self.trail_stop["offset"]
                    stop_side = 1 if self.side == 0 else 0  # Opposite of entry

                    trail_response = await self.order_manager.place_trailing_stop_order(
                        contract_id=contract_id,
                        side=stop_side,
                        size=self.size,
                        trail_price=trail_offset,
                    )
                    if trail_response.success:
                        logger.info(
                            f"Trailing stop order placed: {trail_response.orderId}"
                        )
                        # Note: The BracketOrderResponse does not have a field for the trailing stop ID.
                        # The original stop_order_id will remain in the response.
                    else:
                        logger.error(
                            f"Failed to place trailing stop: {trail_response.errorMessage}"
                        )
                except Exception as e:
                    logger.error(f"Error replacing stop with trailing stop: {e}")

            return result

        else:
            # Simple order without brackets
            if self.entry_type == "market":
                response = await self.order_manager.place_market_order(
                    contract_id=contract_id, side=self.side, size=self.size
                )
            elif self.entry_type == "limit":
                if self.entry_price is None:
                    raise ValueError("Entry price is required for limit orders")
                response = await self.order_manager.place_limit_order(
                    contract_id=contract_id,
                    side=self.side,
                    size=self.size,
                    limit_price=self.entry_price,
                )
            else:  # stop
                if self.entry_price is None:
                    raise ValueError("Entry price is required for stop orders")
                response = await self.order_manager.place_stop_order(
                    contract_id=contract_id,
                    side=self.side,
                    size=self.size,
                    stop_price=self.entry_price,
                )

            # Convert to BracketOrderResponse format
            return BracketOrderResponse(
                success=response.success,
                entry_order_id=response.orderId if response.success else None,
                stop_order_id=None,
                target_order_id=None,
                entry_price=entry_price,
                stop_loss_price=stop_loss_price or 0.0,
                take_profit_price=take_profit_price or 0.0,
                entry_response=response,
                stop_response=None,
                target_response=None,
                error_message=response.errorMessage,
            )


class OrderLifecycleError(Exception):
    """Exception raised when order lifecycle encounters an error."""


# Convenience function for creating order trackers
@deprecated(
    reason="Use TradingSuite.track_order() for integrated tracking",
    version="3.1.14",
    removal_version="5.0.0",
    replacement="TradingSuite.track_order()",
)
def track_order(
    trading_suite: "TradingSuite",
    order: Union[Order, OrderPlaceResponse, int] | None = None,
) -> OrderTracker:
    """
    Create an OrderTracker instance.

    Args:
        trading_suite: TradingSuite instance
        order: Optional order to track immediately

    Returns:
        OrderTracker instance

    Example:
        ```python
        async with track_order(suite) as tracker:
            order = await suite.orders.place_limit_order(...)
            tracker.track(order)
            filled = await tracker.wait_for_fill()
        ```
    """
    # Deprecation warning handled by decorator
    tracker = OrderTracker(trading_suite)
    if order:
        if isinstance(order, Order | OrderPlaceResponse):
            tracker.track(order)
        else:  # int
            tracker.order_id = order
    return tracker
