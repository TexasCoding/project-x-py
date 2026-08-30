"""Event-driven architecture for ProjectX SDK v3.0.0.

This module provides a unified event system for all SDK components,
replacing scattered callback systems with a centralized event bus.
"""

import asyncio
import contextvars
import logging
from collections import defaultdict
from collections.abc import Callable, Coroutine
from enum import Enum
from typing import Any
from weakref import WeakSet

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Unified event types for all SDK components."""

    # Market Data Events
    NEW_BAR = "new_bar"
    DATA_UPDATE = "data_update"
    QUOTE_UPDATE = "quote_update"
    TRADE_TICK = "trade_tick"
    ORDERBOOK_UPDATE = "orderbook_update"
    MARKET_DEPTH_UPDATE = "market_depth_update"

    # Order Events
    ORDER_PLACED = "order_placed"
    ORDER_FILLED = "order_filled"
    ORDER_PARTIAL_FILL = "order_partial_fill"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_REJECTED = "order_rejected"
    ORDER_EXPIRED = "order_expired"
    ORDER_MODIFIED = "order_modified"

    # Position Events
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    POSITION_UPDATED = "position_updated"
    POSITION_PNL_UPDATE = "position_pnl_update"

    # Risk Events
    RISK_LIMIT_WARNING = "risk_limit_warning"
    RISK_LIMIT_EXCEEDED = "risk_limit_exceeded"
    STOP_LOSS_TRIGGERED = "stop_loss_triggered"
    TAKE_PROFIT_TRIGGERED = "take_profit_triggered"

    # System Events
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"
    AUTHENTICATED = "authenticated"
    FEED_STALE = "feed_stale"
    ERROR = "error"
    WARNING = "warning"

    # Performance Events
    MEMORY_WARNING = "memory_warning"
    RATE_LIMIT_WARNING = "rate_limit_warning"
    LATENCY_WARNING = "latency_warning"


class Event:
    """Container for event data."""

    def __init__(self, type: EventType | str, data: Any, source: str | None = None):
        """Initialize event.

        Args:
            type: Event type (EventType enum or string)
            data: Event payload data
            source: Optional source component name
        """
        # Allow both enum and arbitrary string event types
        self.type: EventType | str

        if isinstance(type, EventType):
            self.type = type
        else:
            try:
                self.type = EventType(type)
            except Exception:
                # Allow arbitrary event names (legacy/tests)
                self.type = type  # keep raw string
        self.data = data
        self.source = source
        self.timestamp = asyncio.get_running_loop().time()


class EventBus:
    """Unified event system for all SDK components.

    Provides centralized event handling with support for:
    - Multiple handlers per event
    - One-time handlers
    - Wildcard event subscriptions
    - Async event emission
    - Weak references to prevent memory leaks
    """

    def __init__(self) -> None:
        """Initialize EventBus."""
        # Use defaultdict for cleaner handler management
        self._handlers: dict[
            EventType, list[Callable[[Event], Coroutine[Any, Any, None]]]
        ] = defaultdict(list)
        self._once_handlers: dict[
            EventType, list[Callable[[Event], Coroutine[Any, Any, None]]]
        ] = defaultdict(list)
        self._wildcard_handlers: list[Callable[[Event], Coroutine[Any, Any, None]]] = []

        # Track active tasks to prevent garbage collection
        self._active_tasks: WeakSet[asyncio.Task[Any]] = WeakSet()

        # Event history for debugging (optional, configurable)
        self._history_enabled = False
        self._event_history: list[Event] = []
        self._max_history_size = 1000

        # Legacy string-event handlers (for tests/back-compat)
        self._legacy_handlers: dict[
            str, list[Callable[[Event], Coroutine[Any, Any, None]]]
        ] = defaultdict(list)

        # Detect wait_for() called from inside emit() on this bus (deadlock).
        self._in_emit_handler: contextvars.ContextVar[bool] = contextvars.ContextVar(
            "eventbus_in_emit_handler", default=False
        )

    # v3 primary API
    async def on(
        self,
        event: EventType | str,
        handler: Callable[[Event], Coroutine[Any, Any, None]],
    ) -> None:
        """Register handler for event type.

        Args:
            event: Event type to listen for
            handler: Async callable to handle events
        """
        event_type = event if isinstance(event, EventType) else EventType(event)

        if not asyncio.iscoroutinefunction(handler):
            raise ValueError(f"Handler {handler.__name__} must be async")

        self._handlers[event_type].append(handler)
        logger.debug(f"Registered handler {handler.__name__} for {event_type.value}")

    # Back-compat alias for tests expecting subscribe(name, event, handler)
    async def subscribe(
        self,
        _name: str,
        event: EventType | str,
        handler: Callable[[Event], Coroutine[Any, Any, None]],
    ) -> None:
        # Route to enum or legacy string map
        if isinstance(event, EventType):
            await self.on(event, handler)
        else:
            if not asyncio.iscoroutinefunction(handler):
                raise ValueError(f"Handler {handler.__name__} must be async")
            self._legacy_handlers[str(event)].append(handler)

    async def once(
        self,
        event: EventType | str,
        handler: Callable[[Event], Coroutine[Any, Any, None]],
    ) -> None:
        """Register one-time handler for event type.

        Handler will be automatically removed after first invocation.

        Args:
            event: Event type to listen for
            handler: Async callable to handle event once
        """
        event_type = event if isinstance(event, EventType) else EventType(event)

        if not asyncio.iscoroutinefunction(handler):
            raise ValueError(f"Handler {handler.__name__} must be async")

        self._once_handlers[event_type].append(handler)
        logger.debug(
            f"Registered one-time handler {handler.__name__} for {event_type.value}"
        )

    async def on_any(
        self, handler: Callable[[Event], Coroutine[Any, Any, None]]
    ) -> None:
        """Register handler for all events.

        Args:
            handler: Async callable to handle all events
        """
        if not asyncio.iscoroutinefunction(handler):
            raise ValueError(f"Handler {handler.__name__} must be async")

        self._wildcard_handlers.append(handler)
        logger.debug(f"Registered wildcard handler {handler.__name__}")

    async def off(
        self,
        event: EventType | str | None = None,
        handler: Callable[[Event], Coroutine[Any, Any, None]] | None = None,
    ) -> None:
        """Remove event handler(s).

        Args:
            event: Event type to remove handler from (None for all)
            handler: Specific handler to remove (None for all)
        """
        if event is None:
            # Remove all handlers
            self._handlers.clear()
            self._once_handlers.clear()
            if handler is None:
                self._wildcard_handlers.clear()
            else:
                self._wildcard_handlers = [
                    h for h in self._wildcard_handlers if h != handler
                ]
        else:
            event_type = event if isinstance(event, EventType) else EventType(event)

            if handler is None:
                # Remove all handlers for this event
                self._handlers[event_type].clear()
                self._once_handlers[event_type].clear()
            else:
                # Remove specific handler
                self._handlers[event_type] = [
                    h for h in self._handlers[event_type] if h != handler
                ]
                self._once_handlers[event_type] = [
                    h for h in self._once_handlers[event_type] if h != handler
                ]

    def has_handlers(self, event: EventType | str | None = None) -> bool:
        """Return True if any handler would run for the event (or any event)."""
        if self._wildcard_handlers:
            return True
        if event is None:
            return bool(self._handlers or self._once_handlers or self._legacy_handlers)
        if isinstance(event, EventType):
            return bool(self._handlers.get(event) or self._once_handlers.get(event))
        return bool(self._legacy_handlers.get(str(event)))

    async def emit(
        self, event: EventType | str, data: Any, source: str | None = None
    ) -> None:
        """Emit event to all registered handlers.

        Args:
            event: Event type to emit
            data: Event payload data
            source: Optional source component name
        """
        if not self._history_enabled and not self.has_handlers(event):
            return
        event_obj = Event(event, data, source)

        # Store in history if enabled
        if self._history_enabled:
            self._event_history.append(event_obj)
            if len(self._event_history) > self._max_history_size:
                self._event_history.pop(0)

        # Get all handlers for this event
        handlers: list[Callable[[Event], Coroutine[Any, Any, None]]] = []

        # Regular and once handlers for enum events
        if isinstance(event_obj.type, EventType):
            handlers.extend(self._handlers.get(event_obj.type, []))
            once_handlers = self._once_handlers.get(event_obj.type, [])
            handlers.extend(once_handlers)
            if once_handlers:
                self._once_handlers[event_obj.type] = []
        else:
            # Legacy string event handlers
            handlers.extend(self._legacy_handlers.get(str(event_obj.type), []))

        # Wildcard handlers
        handlers.extend(self._wildcard_handlers)

        # Execute all handlers concurrently and wait for completion
        if handlers:
            tasks: list[asyncio.Task[Any]] = []
            for handler in handlers:
                task = asyncio.create_task(self._execute_handler(handler, event_obj))
                self._active_tasks.add(task)
                tasks.append(task)

            # Await handlers to ensure deterministic completion in tests
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _execute_handler(
        self, handler: Callable[[Event], Coroutine[Any, Any, None]], event: Event
    ) -> None:
        """Execute event handler with error handling.

        Args:
            handler: Async callable to execute
            event: Event object to pass to handler
        """
        token = self._in_emit_handler.set(True)
        try:
            await handler(event)
        except Exception as e:
            event_type_str = (
                event.type.value
                if isinstance(event.type, EventType)
                else str(event.type)
            )
            logger.error(
                f"Error in event handler {handler.__name__} for {event_type_str}: {e}"
            )
            # Emit error event (but avoid infinite recursion)
            if event.type != EventType.ERROR:
                await self.emit(
                    EventType.ERROR,
                    {
                        "original_event": event_type_str,
                        "handler": handler.__name__,
                        "error": str(e),
                    },
                    source="EventBus",
                )
        finally:
            self._in_emit_handler.reset(token)

    async def wait_for(
        self, event: EventType | str, timeout: float | None = None
    ) -> Event:
        """Wait for specific event to occur.

        Handlers must not call ``wait_for`` on the same bus from inside ``emit``.
        That nests ``asyncio.wait_for`` on a Future that cannot complete until
        the current emit finishes, and deadlocks the bus. Re-entrant calls
        raise ``RuntimeError`` immediately.

        Args:
            event: Event type to wait for
            timeout: Optional timeout in seconds

        Returns:
            Event object when received

        Raises:
            asyncio.TimeoutError: If timeout expires
            RuntimeError: If called from an emit handler on this bus
        """
        if self._in_emit_handler.get():
            raise RuntimeError(
                "EventBus.wait_for cannot be called from inside an emit handler "
                "on the same bus (deadlock). Wait from outside the handler."
            )
        event_type = event if isinstance(event, EventType) else EventType(event)
        future: asyncio.Future[Event] = asyncio.Future()

        async def handler(evt: Event) -> None:
            if not future.done():
                future.set_result(evt)

        await self.once(event_type, handler)

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except TimeoutError:
            # Remove handler if timeout
            await self.off(event_type, handler)
            raise

    def enable_history(self, max_size: int = 1000) -> None:
        """Enable event history for debugging.

        Args:
            max_size: Maximum number of events to store
        """
        self._history_enabled = True
        self._max_history_size = max_size
        self._event_history = []

    def get_history(self) -> list[Event]:
        """Get event history.

        Returns:
            List of recent events (empty if history disabled)
        """
        return self._event_history.copy()

    def clear_history(self) -> None:
        """Clear event history."""
        self._event_history.clear()

    def get_handler_count(self, event: EventType | str | None = None) -> int:
        """Get number of registered handlers.

        Args:
            event: Event type to check (None for total)

        Returns:
            Number of handlers
        """
        if event is None:
            total = sum(len(handlers) for handlers in self._handlers.values())
            total += sum(len(handlers) for handlers in self._once_handlers.values())
            total += len(self._wildcard_handlers)
            total += sum(len(handlers) for handlers in self._legacy_handlers.values())
            return total
        else:
            if isinstance(event, EventType):
                count = len(self._handlers.get(event, []))
                count += len(self._once_handlers.get(event, []))
                count += len(self._wildcard_handlers)
                return count
            else:
                count = len(self._legacy_handlers.get(str(event), []))
                count += len(self._wildcard_handlers)
                return count

    async def forward_to(self, target_bus: "EventBus") -> None:
        """
        Forward all events from this bus to the target bus.

        This sets up a wildcard handler that forwards all events to another EventBus,
        enabling event propagation from instrument-specific buses to the main suite bus.

        Args:
            target_bus: The EventBus to forward events to
        """

        async def forwarder(event: Event) -> None:
            """Forward event to target bus."""
            await target_bus.emit(event.type, event.data, event.source)

        await self.on_any(forwarder)
