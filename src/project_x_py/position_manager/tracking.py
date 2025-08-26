"""
Real-time position tracking and callback management for ProjectX position management.

Author: @TexasCoding
Date: 2025-08-02

Overview:
    Provides real-time position tracking and callback management functionality for
    position management. Includes WebSocket integration, position update processing,
    closure detection, and event-driven callback system for custom monitoring.

Key Features:
    - Real-time position tracking via WebSocket integration
    - Position update processing and closure detection
    - Event-driven callback system for custom monitoring
    - Position history tracking and change detection
    - Payload validation and error handling
    - Thread-safe operations with proper lock management

Tracking Capabilities:
    - Real-time position updates via WebSocket feeds
    - Position closure detection (size=0)
    - Position history tracking with change detection
    - Event-driven callbacks for position updates
    - Payload validation and API compliance checking
    - Integration with monitoring and alert systems

Example Usage:
    ```python
    # V3: Using EventBus for unified event handling is the recommended approach.
    # The old add_callback method is deprecated.
    from project_x_py import EventBus, EventType

    event_bus = EventBus()
    # position_manager would be initialized with this event_bus instance.


    # Register for position update events
    @event_bus.on(EventType.POSITION_UPDATED)
    async def on_position_update(data):
        print(f"Position updated: {data.get('contractId')} size: {data.get('size')}")


    # Register for position closure events
    @event_bus.on(EventType.POSITION_CLOSED)
    async def on_position_closed(data):
        print(f"Position closed: {data.get('contractId')}")


    # V3.1: Get position history with TradingSuite
    # history = await suite.positions.get_position_history(suite.instrument_id, limit=10)
    # for entry in history:
    #     print(f"{entry['timestamp']}: {entry['size_change']:+d} contracts")
    ```

See Also:
    - `position_manager.core.PositionManager`
    - `position_manager.monitoring.PositionMonitoringMixin`
    - `position_manager.reporting.PositionReportingMixin`
"""

import asyncio
import contextlib
import logging
from collections import defaultdict, deque
from collections.abc import Callable, Coroutine
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from project_x_py.models import Position
from project_x_py.types.trading import PositionType
from project_x_py.utils.deprecation import deprecated

if TYPE_CHECKING:
    from asyncio import Lock

    from project_x_py.realtime import ProjectXRealtimeClient

logger = logging.getLogger(__name__)


class PositionTrackingMixin:
    """Mixin for real-time position tracking and callback functionality."""

    # Type hints for mypy - these attributes are provided by the main class
    if TYPE_CHECKING:
        from project_x_py.order_manager import OrderManager

        realtime_client: ProjectXRealtimeClient | None
        logger: logging.Logger
        position_lock: Lock
        stats: dict[str, Any]
        order_manager: OrderManager | None
        _order_sync_enabled: bool
        event_bus: Any  # EventBus instance

        # Methods from other mixins
        async def _check_position_alerts(
            self,
            contract_id: str,
            current_position: Position,
            old_position: Position | None,
        ) -> None: ...

    def __init__(self) -> None:
        """Initialize tracking attributes."""
        # Position tracking (maintains local state for business logic)
        self.tracked_positions: dict[str, Position] = {}
        self.position_history: dict[str, deque[dict[str, Any]]] = defaultdict(
            lambda: deque(maxlen=1000)
        )
        # Queue-based processing to prevent race conditions
        self._position_update_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._position_processor_task: asyncio.Task[None] | None = None
        self._processing_enabled = False
        # EventBus is now used for all event handling

    async def _setup_realtime_callbacks(self) -> None:
        """
        Set up callbacks for real-time position monitoring via WebSocket.

        Registers internal callback handlers with the real-time client to process
        position updates and account changes. Called automatically during initialization
        when a real-time client is provided.

        Registered callbacks:
            - position_update: Handles position size/price changes and closures
            - account_update: Handles account-level changes affecting positions

        Note:
            This is an internal method called by initialize(). Do not call directly.
        """
        if not self.realtime_client:
            return

        # Start the queue processor
        await self._start_position_processor()

        # Subscribe to user updates (positions, orders, trades, account)
        if hasattr(self.realtime_client, "subscribe_user_updates"):
            await self.realtime_client.subscribe_user_updates()

        # Register for position events (closures are detected from position updates)
        await self.realtime_client.add_callback(
            "position_update", self._on_position_update
        )
        await self.realtime_client.add_callback(
            "account_update", self._on_account_update
        )

        self.logger.info("🔄 Real-time position callbacks registered")

    async def _start_position_processor(self) -> None:
        """Start the queue-based position processor."""
        if self._position_processor_task and not self._position_processor_task.done():
            return

        self._processing_enabled = True
        self._position_processor_task = asyncio.create_task(self._position_processor())
        self.logger.info("📋 Position queue processor started")

    async def _stop_position_processor(self) -> None:
        """Stop the queue-based position processor."""
        self._processing_enabled = False

        if self._position_processor_task:
            self._position_processor_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._position_processor_task
            self._position_processor_task = None

        self.logger.info("📋 Position queue processor stopped")

    async def _position_processor(self) -> None:
        """Queue-based position processor to prevent race conditions."""
        while self._processing_enabled:
            try:
                # Wait for position update with timeout
                position_data = await asyncio.wait_for(
                    self._position_update_queue.get(), timeout=1.0
                )

                # Process the position update with exclusive lock
                async with self.position_lock:
                    await self._process_position_data(position_data)

                # Mark task as done
                self._position_update_queue.task_done()

            except TimeoutError:
                # Normal timeout, continue processing
                continue
            except asyncio.CancelledError:
                # Task was cancelled, exit gracefully
                break
            except Exception as e:
                self.logger.error(f"Error in position processor: {e}")
                # Continue processing other items

    async def _on_position_update(
        self, data: dict[str, Any] | list[dict[str, Any]]
    ) -> None:
        """
        Handle real-time position updates by queueing them for serial processing.

        Queues incoming position data for processing by the dedicated processor task.
        This prevents race conditions by ensuring all position updates are processed
        serially rather than concurrently.

        Args:
            data (dict): Position update data from real-time feed. Can be:
                - Single position dict with GatewayUserPosition fields
                - List of position dicts
                - Wrapped format: {"action": 1, "data": {position_data}}

        Note:
            - All updates are queued for serial processing
            - Position closure is detected when size == 0 (not type == 0)
            - Type 0 means "Undefined" in PositionType enum, not closed
            - Automatically triggers position_closed callbacks on closure
        """
        try:
            if isinstance(data, list):
                for position_data in data:
                    await self._position_update_queue.put(position_data)
            elif isinstance(data, dict):
                await self._position_update_queue.put(data)

        except Exception as e:
            self.logger.error(f"Error queueing position update: {e}")

    def get_queue_size(self) -> int:
        """Get current size of position update queue."""
        return self._position_update_queue.qsize()

    async def _on_account_update(self, data: dict[str, Any]) -> None:
        """
        Handle account-level updates that may affect positions.

        Processes account update events from the real-time feed and triggers
        registered account_update callbacks for custom handling.

        Args:
            data (dict): Account update data containing balance, margin, and other
                account-level information that may impact position management
        """
        await self._trigger_callbacks("account_update", data)

    def _validate_position_payload(self, position_data: dict[str, Any]) -> bool:
        """
        Validate that position payload matches ProjectX GatewayUserPosition format.

        Ensures incoming position data conforms to the expected schema before processing.
        This validation prevents errors from malformed data and ensures API compliance.

        Expected fields according to ProjectX docs (minimum for real-time updates):
            - contractId (string): The contract ID associated with the position
            - type (int): PositionType enum value:
                * 0 = Undefined (not a closed position)
                * 1 = Long position
                * 2 = Short position
            - size (int): The number of contracts (0 means position is closed)
            - averagePrice (number): The weighted average entry price

        Note:
            Full payloads from API include additional fields like `id`, `accountId`,
            and `creationTimestamp`. Real-time incremental updates may omit these.
            We accept minimal updates and fill reasonable defaults during processing.

        Args:
            position_data (dict): Raw position payload from ProjectX real-time feed

        Returns:
            bool: True if payload contains all required fields with valid values,
                False if validation fails

        Warning:
            Position closure is determined by size == 0, NOT type == 0.
            Type 0 means "Undefined" position type, not a closed position.
        """
        required_fields: set[str] = {"contractId", "type", "size", "averagePrice"}

        missing_fields: set[str] = required_fields - set(position_data.keys())
        if missing_fields:
            self.logger.warning(
                f"Position payload missing required fields: {missing_fields}"
            )
            return False

        # Validate PositionType enum values
        position_type: int | None = position_data.get("type")
        if position_type not in [
            PositionType.UNDEFINED,
            PositionType.LONG,
            PositionType.SHORT,
        ]:
            self.logger.warning(f"Invalid position type: {position_type}")
            return False

        # Validate that size is a number
        size: int | float | None = position_data.get("size")
        if not isinstance(size, int | float):
            self.logger.warning(f"Invalid position size type: {type(size)}")
            return False

        return True

    async def _process_position_data(self, position_data: dict[str, Any]) -> None:
        """
        Process individual position data update and detect position closures.

        Core processing method that handles position updates, maintains tracked positions,
        detects closures, triggers callbacks, and synchronizes with order management.

        ProjectX GatewayUserPosition payload structure:
            - Position is closed when size == 0 (not when type == 0)
            - type=0 means "Undefined" according to PositionType enum
            - type=1 means "Long", type=2 means "Short"

        Args:
            position_data (dict): Position data which can be:
                - Direct position dict with GatewayUserPosition fields
                - Wrapped format: {"action": 1, "data": {actual_position_data}}

        Processing flow:
            1. Extract actual position data from wrapper if needed
            2. Validate payload format
            3. Check if position is closed (size == 0)
            4. Update tracked positions or remove if closed
            5. Trigger appropriate callbacks
            6. Update position history
            7. Check position alerts
            8. Synchronize with order manager if enabled

        Side effects:
            - Updates self.tracked_positions
            - Appends to self.position_history
            - May trigger position_closed or position_update callbacks
            - May trigger position alerts
            - Updates statistics counters
        """
        try:
            # Handle wrapped position data from real-time updates
            # Real-time updates come as: {"action": 1, "data": {position_data}}
            # But direct API calls might provide raw position data
            actual_position_data: dict[str, Any] = position_data
            if "action" in position_data and "data" in position_data:
                actual_position_data = position_data["data"]
                self.logger.debug(
                    f"Extracted position data from wrapper: action={position_data.get('action')}"
                )

            # Validate payload format
            if not self._validate_position_payload(actual_position_data):
                self.logger.error(
                    f"Invalid position payload format: {actual_position_data}"
                )
                return

            contract_id = actual_position_data.get("contractId")
            if not contract_id:
                self.logger.error(f"No contract ID found in {actual_position_data}")
                return

            # Check if this is a position closure
            # Position is closed when size == 0 (not when type == 0)
            # type=0 means "Undefined" according to PositionType enum, not closed
            position_size: int = actual_position_data.get("size", 0)
            is_position_closed: bool = position_size == 0

            # Get the old position before updating
            old_position: Position | None = self.tracked_positions.get(contract_id)
            old_size: int = old_position.size if old_position else 0

            if is_position_closed:
                # Position is closed - calculate realized P&L and update stats
                if old_position:
                    # Assume the averagePrice in the closing update is the exit price
                    exit_price = actual_position_data.get(
                        "averagePrice", old_position.averagePrice
                    )
                    entry_price = old_position.averagePrice
                    size = old_position.size

                    # Use Decimal for precise P&L calculations
                    # For futures, a point_value/multiplier is needed.
                    # Assuming point_value of 1 for now.
                    exit_decimal = Decimal(str(exit_price))
                    entry_decimal = Decimal(str(entry_price))
                    size_decimal = Decimal(str(size))

                    if old_position.type == PositionType.LONG:
                        pnl_decimal = (exit_decimal - entry_decimal) * size_decimal
                    else:  # SHORT
                        pnl_decimal = (entry_decimal - exit_decimal) * size_decimal

                    pnl = float(pnl_decimal)  # Convert back for compatibility
                    self.stats["realized_pnl"] += pnl
                    self.stats["closed_positions"] += 1
                    if pnl > 0:
                        self.stats["winning_positions"] = (
                            self.stats.get("winning_positions", 0) + 1
                        )
                        self.stats["gross_profit"] = (
                            self.stats.get("gross_profit", 0.0) + pnl
                        )
                        if pnl > self.stats.get("best_position_pnl", 0.0):
                            self.stats["best_position_pnl"] = pnl
                    else:
                        self.stats["losing_positions"] = (
                            self.stats.get("losing_positions", 0) + 1
                        )
                        self.stats["gross_loss"] = (
                            self.stats.get("gross_loss", 0.0) + pnl
                        )  # pnl is negative
                        if pnl < self.stats.get("worst_position_pnl", 0.0):
                            self.stats["worst_position_pnl"] = pnl

                # Remove from tracking
                if contract_id in self.tracked_positions:
                    del self.tracked_positions[contract_id]
                    self.logger.info(
                        f"📊 Position closed: {contract_id}, Realized P&L: {pnl:.2f}"
                    )

                # Synchronize orders - cancel related orders when position is closed
                if self._order_sync_enabled and self.order_manager:
                    await self.order_manager.on_position_closed(contract_id)

                # Trigger position_closed callbacks with the closure data
                await self._trigger_callbacks("position_closed", actual_position_data)
            else:
                # Position is open/updated - create or update position
                is_new_position = contract_id not in self.tracked_positions

                if is_new_position:
                    # For new positions, some fields might be missing from the real-time feed.
                    # We create a new object with defaults for any missing critical fields.
                    from datetime import UTC as _UTC, datetime as _dt

                    position_dict: dict[str, Any] = {
                        "id": actual_position_data.get("id", -1),
                        "accountId": actual_position_data.get("accountId", -1),
                        "contractId": contract_id,
                        "creationTimestamp": actual_position_data.get(
                            "creationTimestamp", _dt.now(_UTC).isoformat()
                        ),
                        "type": actual_position_data.get(
                            "type", PositionType.UNDEFINED
                        ),
                        "size": position_size,
                        "averagePrice": actual_position_data.get("averagePrice", 0.0),
                    }
                else:
                    # For existing positions, merge the update with the cached object
                    # to preserve fields like 'id' and 'creationTimestamp'.
                    existing_position = self.tracked_positions[contract_id]
                    # Manually construct dict from the existing position object
                    position_dict = {
                        "id": existing_position.id,
                        "accountId": existing_position.accountId,
                        "contractId": existing_position.contractId,
                        "creationTimestamp": existing_position.creationTimestamp,
                        "type": existing_position.type,
                        "size": existing_position.size,
                        "averagePrice": existing_position.averagePrice,
                    }
                    position_dict.update(actual_position_data)

                position: Position = Position(**position_dict)
                self.tracked_positions[contract_id] = position

                # Emit appropriate event
                if is_new_position:
                    # New position opened
                    await self._trigger_callbacks(
                        "position_opened", actual_position_data
                    )
                    self.stats["open_positions"] = (
                        self.stats.get("open_positions", 0) + 1
                    )
                else:
                    # Existing position updated
                    await self._trigger_callbacks(
                        "position_update", actual_position_data
                    )

                # Synchronize orders - update order sizes if position size changed
                if (
                    self._order_sync_enabled
                    and self.order_manager
                    and old_size != position_size
                ):
                    await self.order_manager.on_position_changed(
                        contract_id, old_size, position_size
                    )

                # Track position history with bounded deque
                self.position_history[contract_id].append(
                    {
                        "timestamp": datetime.now(),
                        "position": actual_position_data.copy(),
                        "size_change": position_size - old_size,
                    }
                )

                # Check alerts
                await self._check_position_alerts(contract_id, position, old_position)

        except Exception as e:
            self.logger.error(f"Error processing position data: {e}")
            self.logger.debug(f"Position data that caused error: {position_data}")

    async def _trigger_callbacks(self, event_type: str, data: Any) -> None:
        """
        Trigger registered callbacks for position events.

        Executes all registered callback functions for a specific event type.
        Handles both sync and async callbacks, with error isolation to prevent
        one failing callback from affecting others.

        Args:
            event_type (str): The type of event to trigger callbacks for:
                - "position_update": Position changed
                - "position_closed": Position fully closed
                - "account_update": Account-level change
                - "position_alert": Alert condition met
            data (Any): Event data to pass to callbacks, typically a dict with
                event-specific information

        Note:
            - Callbacks are executed in registration order
            - Errors in callbacks are logged but don't stop other callbacks
            - Supports both sync and async callback functions
        """
        # Emit event through EventBus
        from project_x_py.event_bus import EventType

        # Map position event types to EventType enum
        event_mapping = {
            "position_opened": EventType.POSITION_OPENED,
            "position_closed": EventType.POSITION_CLOSED,
            "position_update": EventType.POSITION_UPDATED,
            "position_pnl_update": EventType.POSITION_PNL_UPDATE,
            "position_alert": EventType.RISK_LIMIT_WARNING,  # Map alerts to risk warnings
        }

        if event_type in event_mapping:
            emitter = getattr(self.event_bus, "emit", None)
            if emitter is not None:
                result = emitter(
                    event_mapping[event_type], data, source="PositionManager"
                )
                # Support both sync and async emitters
                try:
                    import inspect as _inspect

                    if _inspect.isawaitable(result):
                        await result
                except Exception:  # Fallback: ignore awaitability issues for mocks
                    pass

        # Legacy callbacks have been removed - use EventBus

    async def cleanup_tracking(self) -> None:
        """Clean up tracking resources and stop processor."""
        await self._stop_position_processor()

        # Clear bounded collections
        self.tracked_positions.clear()
        self.position_history.clear()

        # Clear any remaining queue items
        while not self._position_update_queue.empty():
            try:
                self._position_update_queue.get_nowait()
                self._position_update_queue.task_done()
            except asyncio.QueueEmpty:
                break

        self.logger.info("✅ Position tracking cleanup completed")

    @deprecated(
        reason="Use TradingSuite.on() with EventType enum for event handling",
        version="3.1.0",
        removal_version="4.0.0",
        replacement="TradingSuite.on(EventType.POSITION_UPDATED, callback)",
    )
    async def add_callback(
        self,
        event_type: str,
        callback: Callable[[dict[str, Any]], Coroutine[Any, Any, None] | None],
    ) -> None:
        """
        Register a callback function for specific position events.

        Allows you to listen for position updates, closures, account changes, and alerts
        to build custom monitoring and notification systems.

        Args:
            event_type: Type of event to listen for
                - "position_update": Position size or price changes
                - "position_closed": Position fully closed (size = 0)
                - "account_update": Account-level changes
                - "position_alert": Position alert triggered
            callback: Async function to call when event occurs
                Should accept one argument: the event data dict

        Example:
            >>> async def on_position_update(data):
            ...     pos = data.get("data", {})
            ...     print(
            ...         f"Position updated: {pos.get('contractId')} size: {pos.get('size')}"
            ...     )
            >>> await position_manager.add_callback(
            ...     "position_update", on_position_update
            ... )
            >>> async def on_position_closed(data):
            ...     pos = data.get("data", {})
            ...     print(f"Position closed: {pos.get('contractId')}")
            >>> await position_manager.add_callback(
            ...     "position_closed", on_position_closed
            ... )
        """
        self.logger.warning(
            "add_callback is deprecated. Use TradingSuite.on() with EventType enum instead."
        )

    async def get_position_history_size(self, contract_id: str) -> int:
        """Get the current size of position history for a contract."""
        return len(self.position_history.get(contract_id, deque()))
