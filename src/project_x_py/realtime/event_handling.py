"""
Event handling and callback management for real-time client.

Author: @TexasCoding
Date: 2025-08-02

Overview:
    Provides event handling and callback management functionality for the ProjectX
    real-time client, including event forwarding, callback registration, and
    cross-thread event processing for asyncio compatibility.

Key Features:
    - Event forwarding from SignalR to registered callbacks
    - Support for both async and sync callbacks
    - Cross-thread event scheduling for asyncio compatibility
    - Error isolation to prevent callback failures
    - Thread-safe callback registration and management
    - Event statistics and flow monitoring

Event Handling Capabilities:
    - User events: Account, position, order, and trade updates
    - Market events: Quote, trade, and market depth data
    - Cross-thread event processing for SignalR compatibility
    - Callback registration and management
    - Event statistics and health monitoring
    - Error handling and recovery

Example Usage:
    ```python
    # Register callbacks for different event types
    async def on_position_update(data):
        print(f"Position update: {data}")


    async def on_quote_update(data):
        contract = data["contract_id"]
        quote = data["data"]
        print(f"{contract}: {quote['bid']} x {quote['ask']}")


    await client.add_callback("position_update", on_position_update)
    await client.add_callback("quote_update", on_quote_update)

    # Remove specific callbacks
    await client.remove_callback("position_update", on_position_update)

    # Multiple callbacks for same event
    await client.add_callback("trade_execution", log_trade)
    await client.add_callback("trade_execution", update_pnl)
    ```

Event Types:
    User Events:
        - account_update: Balance, margin, buying power changes
        - position_update: Position opens, changes, closes
        - order_update: Order placement, fills, cancellations
        - trade_execution: Individual trade fills

    Market Events:
        - quote_update: Bid/ask price changes
        - market_trade: Executed market trades
        - market_depth: Order book updates

See Also:
    - `realtime.core.ProjectXRealtimeClient`
    - `realtime.connection_management.ConnectionManagementMixin`
    - `realtime.subscriptions.SubscriptionsMixin`
"""

import asyncio
from collections.abc import Callable, Coroutine
from datetime import datetime
from typing import TYPE_CHECKING, Any

from project_x_py.realtime.batched_handler import OptimizedRealtimeHandler
from project_x_py.utils.task_management import TaskManagerMixin

if TYPE_CHECKING:
    import logging


class EventHandlingMixin(TaskManagerMixin):
    """Mixin for event handling and callback management with optional batching."""

    # Type hints for attributes expected from main class
    if TYPE_CHECKING:
        _loop: asyncio.AbstractEventLoop | None
        _callback_lock: asyncio.Lock
        callbacks: dict[str, list[Callable[..., Any]]]
        logger: logging.Logger
        stats: dict[str, Any]

        async def disconnect(self) -> None: ...

    def __init__(self) -> None:
        """Initialize event handling with batching support."""
        super().__init__()
        self._init_task_manager()  # Initialize task management
        self._batched_handler: OptimizedRealtimeHandler | None = None
        self._use_batching = False

    async def add_callback(
        self,
        event_type: str,
        callback: Callable[[dict[str, Any]], Coroutine[Any, Any, None] | None],
    ) -> None:
        """
        Register an async callback for specific event types.

        Callbacks are triggered whenever matching events are received from ProjectX.
        Multiple callbacks can be registered for the same event type.

        Args:
            event_type (str): Type of event to listen for:
                User Events:
                    - "account_update": Balance, margin, buying power changes
                    - "position_update": Position opens, changes, closes
                    - "order_update": Order placement, fills, cancellations
                    - "trade_execution": Individual trade fills
                Market Events:
                    - "quote_update": Bid/ask price changes
                    - "market_trade": Executed market trades
                    - "market_depth": Order book updates
            callback: Async or sync function to call when event occurs.
                Should accept a single dict parameter with event data.

        Callback Data Format:
            User events: Direct event data dict from ProjectX
            Market events: {"contract_id": str, "data": dict}

        Example:
            >>> # Simple position tracking
            >>> async def on_position(data):
            ...     print(f"Position update: {data}")
            >>> await client.add_callback("position_update", on_position)
            >>> # Advanced order tracking with error handling
            >>> async def on_order(data):
            ...     try:
            ...         order_id = data.get("orderId")
            ...         status = data.get("status")
            ...         print(f"Order {order_id}: {status}")
            ...         if status == "Filled":
            ...             await process_fill(data)
            ...     except Exception as e:
            ...         print(f"Error processing order: {e}")
            >>> await client.add_callback("order_update", on_order)
            >>> # Market data processing
            >>> async def on_quote(data):
            ...     contract = data["contract_id"]
            ...     quote = data["data"]
            ...     mid = (quote["bid"] + quote["ask"]) / 2
            ...     print(f"{contract} mid: {mid}")
            >>> await client.add_callback("quote_update", on_quote)
            >>> # Multiple callbacks for same event
            >>> await client.add_callback("trade_execution", log_trade)
            >>> await client.add_callback("trade_execution", update_pnl)
            >>> await client.add_callback("trade_execution", check_risk)

        Note:
            - Callbacks are called in order of registration
            - Exceptions in callbacks are caught and logged
            - Both async and sync callbacks are supported
            - Callbacks persist across reconnections
        """
        async with self._callback_lock:
            self.callbacks[event_type].append(callback)
            self.logger.debug(f"Registered callback for {event_type}")

    async def remove_callback(
        self,
        event_type: str,
        callback: Callable[[dict[str, Any]], Coroutine[Any, Any, None] | None],
    ) -> None:
        """
        Remove a registered callback.

        Unregisters a specific callback function from an event type. Other callbacks
        for the same event type remain active.

        Args:
            event_type (str): Event type to remove callback from
            callback: The exact callback function reference to remove

        Example:
            >>> # Remove specific callback
            >>> async def my_handler(data):
            ...     print(data)
            >>> await client.add_callback("position_update", my_handler)
            >>> # Later...
            >>> await client.remove_callback("position_update", my_handler)
            >>>
            >>> # Remove using stored reference
            >>> handlers = []
            >>> for i in range(3):
            ...     handler = lambda data: print(f"Handler {i}: {data}")
            ...     handlers.append(handler)
            ...     await client.add_callback("quote_update", handler)
            >>> # Remove second handler only
            >>> await client.remove_callback("quote_update", handlers[1])

        Note:
            - Must pass the exact same function reference
            - No error if callback not found
            - Use clear() on self.callbacks[event_type] to remove all
        """
        async with self._callback_lock:
            if event_type in self.callbacks and callback in self.callbacks[event_type]:
                self.callbacks[event_type].remove(callback)
                self.logger.debug(f"Removed callback for {event_type}")

    async def _trigger_callbacks(self, event_type: str, data: dict[str, Any]) -> None:
        """
        Trigger all registered callbacks for an event type.

        Internal method to execute all callbacks registered for a specific event type.
        Handles both async and sync callbacks, with proper error handling.

        Args:
            event_type: The type of event to trigger callbacks for
            data: Event data to pass to callbacks

        Note:
            - Callbacks are executed in registration order
            - Exceptions in callbacks are caught and logged
            - Does not block on individual callback failures
            - Updates event statistics
        """
        if event_type not in self.callbacks:
            return

        # Update statistics when processing events
        self.stats["events_received"] += 1
        self.stats["last_event_time"] = datetime.now()

        # Get callbacks under lock but execute outside
        async with self._callback_lock:
            callbacks_to_run = list(self.callbacks[event_type])

        for callback in callbacks_to_run:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    callback(data)
            except Exception as e:
                self.logger.error(f"Error in {event_type} callback: {e}", exc_info=True)

    # Event forwarding methods (cross-thread safe)
    def _forward_account_update(self, *args: Any) -> None:
        """
        Forward account update to registered callbacks.

        Receives GatewayUserAccount events from SignalR and schedules async
        processing. Called from SignalR thread, schedules in asyncio loop.

        Args:
            *args: Variable arguments from SignalR containing account data

        Event Data:
            Typically contains balance, buying power, margin, and other
            account-level information.
        """
        self._schedule_async_task("account_update", args)

    def _forward_position_update(self, *args: Any) -> None:
        """
        Forward position update to registered callbacks.

        Receives GatewayUserPosition events from SignalR and schedules async
        processing. Handles position opens, changes, and closes.

        Args:
            *args: Variable arguments from SignalR containing position data

        Event Data:
            Contains position details including size, average price, and P&L.
            Position closure indicated by size = 0.
        """
        self._schedule_async_task("position_update", args)

    def _forward_order_update(self, *args: Any) -> None:
        """
        Forward order update to registered callbacks.

        Receives GatewayUserOrder events from SignalR and schedules async
        processing. Covers full order lifecycle.

        Args:
            *args: Variable arguments from SignalR containing order data

        Event Data:
            Contains order details including status, filled quantity, and prices.
        """
        self._schedule_async_task("order_update", args)

    def _forward_trade_execution(self, *args: Any) -> None:
        """
        Forward trade execution to registered callbacks.

        Receives GatewayUserTrade events from SignalR and schedules async
        processing. Individual fill notifications.

        Args:
            *args: Variable arguments from SignalR containing trade data

        Event Data:
            Contains execution details including price, size, and timestamp.
        """
        self._schedule_async_task("trade_execution", args)

    def enable_batching(self) -> None:
        """Enable message batching for improved throughput with high-frequency data."""
        if not self._batched_handler:
            self._batched_handler = OptimizedRealtimeHandler(self)
        self._use_batching = True

    def disable_batching(self) -> None:
        """Disable message batching and use direct processing."""
        self._use_batching = False

    async def stop_batching(self) -> None:
        """Stop batching and flush any pending messages."""
        if self._batched_handler:
            await self._batched_handler.stop()
            self._batched_handler = None
        self._use_batching = False

    def get_batching_stats(
        self,
    ) -> dict[str, Any] | None:
        """Get performance statistics from the batch handler."""
        if self._batched_handler:
            stats: dict[str, Any] = self._batched_handler.get_all_stats()
            return stats
        return None

    def _forward_quote_update(self, *args: Any) -> None:
        """
        Forward quote update to registered callbacks.

        Receives GatewayQuote events from SignalR and schedules async
        processing. Real-time bid/ask updates.

        Args:
            *args: Variable arguments from SignalR containing quote data

        Event Data Format:
            Callbacks receive: {"contract_id": str, "data": quote_dict}
        """
        if self._use_batching and self._batched_handler and args:
            # Use batched processing for high-frequency quotes
            self._create_task(
                self._batched_handler.handle_quote(args[0]),
                name="handle_quote",
                persistent=False,
            )
        else:
            self._schedule_async_task("quote_update", args)

    def _forward_market_trade(self, *args: Any) -> None:
        """
        Forward market trade to registered callbacks.

        Receives GatewayTrade events from SignalR and schedules async
        processing. Public trade tape data.

        Args:
            *args: Variable arguments from SignalR containing trade data

        Event Data Format:
            Callbacks receive: {"contract_id": str, "data": trade_dict}
        """
        if self._use_batching and self._batched_handler and args:
            # Use batched processing for trades
            self._create_task(
                self._batched_handler.handle_trade(args[0]),
                name="handle_trade",
                persistent=False,
            )
        else:
            self._schedule_async_task("market_trade", args)

    def _forward_market_depth(self, *args: Any) -> None:
        """
        Forward market depth to registered callbacks.

        Receives GatewayDepth events from SignalR and schedules async
        processing. Full order book updates.

        Args:
            *args: Variable arguments from SignalR containing depth data

        Event Data Format:
            Callbacks receive: {"contract_id": str, "data": depth_dict}
        """
        if self._use_batching and self._batched_handler and args:
            # Use batched processing for depth updates
            self._create_task(
                self._batched_handler.handle_depth(args[0]),
                name="handle_depth",
                persistent=False,
            )
        else:
            self._schedule_async_task("market_depth", args)

    def _schedule_async_task(self, event_type: str, data: Any) -> None:
        """
        Schedule async task in the main event loop from any thread.

        Bridges SignalR's threading model with asyncio. SignalR events arrive
        on various threads, but callbacks must run in the asyncio event loop.

        Args:
            event_type (str): Event type for routing
            data: Raw event data from SignalR

        Threading Model:
            - SignalR events: Arrive on SignalR threads
            - This method: Runs on SignalR thread
            - Scheduled task: Runs on asyncio event loop thread
            - Callbacks: Execute in asyncio context

        Error Handling:
            - If loop exists: Uses run_coroutine_threadsafe
            - If no loop: Attempts create_task (may fail)
            - Fallback: Logs to stdout to avoid recursion

        Note:
            Critical for thread safety - ensures callbacks run in proper context.
        """
        if self._loop and not self._loop.is_closed():
            try:
                asyncio.run_coroutine_threadsafe(
                    self._forward_event_async(event_type, data), self._loop
                )
            except Exception as e:
                # Fallback for logging - avoid recursion
                self.logger.error(f"Error scheduling async task: {e}")
        else:
            # Fallback - try to create task in current loop context
            try:
                self._create_task(
                    self._forward_event_async(event_type, data),
                    name=f"forward_{event_type}",
                    persistent=False,
                )
            except RuntimeError:
                # No event loop available, log and continue
                self.logger.error(f"No event loop available for {event_type} event")

    async def _forward_event_async(self, event_type: str, args: Any) -> None:
        """
        Forward event to registered callbacks asynchronously.

        Processes raw SignalR event data and triggers appropriate callbacks.
        Handles different data formats for user vs market events.

        Args:
            event_type (str): Type of event to process
            args: Raw arguments from SignalR (tuple or list)

        Data Processing:
            Market Events (quote, trade, depth):
                - SignalR format 1: [contract_id, data_dict]
                - SignalR format 2: Single dict with contract info
                - Output format: {"contract_id": str, "data": dict}

            User Events (account, position, order, trade):
                - SignalR format: Direct data dict
                - Output format: Same data dict

        Side Effects:
            - Triggers all registered callbacks (statistics updated there)

        Example Data Flow:
            >>> # SignalR sends: ["MNQ", {"bid": 18500, "ask": 18501}]
            >>> # Callbacks receive: {"contract_id": "MNQ", "data": {"bid": 18500, "ask": 18501}}

        Note:
            This method runs in the asyncio event loop, ensuring thread safety
            for callback execution.
        """
        # Log event (debug level)
        # Note: Statistics are updated in _trigger_callbacks to avoid double-counting
        self.logger.debug(
            f"📨 Received {event_type} event: {len(args) if hasattr(args, '__len__') else 'N/A'} items"
        )

        # Parse args and create structured data like sync version
        try:
            if event_type in ["quote_update", "market_trade", "market_depth"]:
                # Market events - parse SignalR format like sync version
                if len(args) == 1:
                    # Single argument - the data payload
                    raw_data = args[0]
                    if isinstance(raw_data, list) and len(raw_data) >= 2:
                        # SignalR format: [contract_id, actual_data_dict]
                        contract_id = raw_data[0]
                        data = raw_data[1]
                    elif isinstance(raw_data, dict):
                        contract_id = raw_data.get(
                            "symbol" if event_type == "quote_update" else "symbolId",
                            "unknown",
                        )
                        data = raw_data
                    else:
                        contract_id = "unknown"
                        data = raw_data
                elif len(args) == 2:
                    # Two arguments - contract_id and data
                    contract_id, data = args
                else:
                    self.logger.warning(
                        f"Unexpected {event_type} args: {len(args)} - {args}"
                    )
                    return

                # Create structured callback data like sync version
                callback_data = {"contract_id": contract_id, "data": data}

            else:
                # User events - single data payload like sync version
                callback_data = args[0] if args else {}

            # Trigger callbacks with structured data
            await self._trigger_callbacks(event_type, callback_data)

        except Exception as e:
            self.logger.error(f"Error processing {event_type} event: {e}")
            self.logger.debug(f"Args received: {args}")

    async def cleanup(self) -> None:
        """
        Clean up resources when shutting down.

        Performs complete cleanup of the real-time client, including disconnecting
        from hubs and clearing all callbacks. Should be called when the client is
        no longer needed.

        Cleanup Operations:
            1. Disconnect from both SignalR hubs
            2. Clear all registered callbacks
            3. Reset connection state

        Example:
            >>> # Basic cleanup
            >>> await client.cleanup()
            >>>
            >>> # In a context manager (if implemented)
            >>> async with AsyncProjectXRealtimeClient(token, account) as client:
            ...     await client.connect()
            ...     # ... use client ...
            ... # cleanup() called automatically
            >>>
            >>> # In a try/finally block
            >>> client = AsyncProjectXRealtimeClient(token, account)
            >>> try:
            ...     await client.connect()
            ...     await client.subscribe_user_updates()
            ...     # ... process events ...
            >>> finally:
            ...     await client.cleanup()

        Note:
            - Safe to call multiple times
            - After cleanup, client must be recreated for reuse
            - Does not affect the JWT token or account ID
        """
        await self.disconnect()
        await self._cleanup_tasks()  # Clean up all managed tasks
        async with self._callback_lock:
            self.callbacks.clear()
        self.logger.info("✅ AsyncProjectXRealtimeClient cleanup completed")
