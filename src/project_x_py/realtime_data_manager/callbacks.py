"""
Callback management and event handling for real-time data updates.

Author: @TexasCoding
Date: 2025-08-02

Overview:
    Provides callback management and event handling functionality for real-time data updates.
    Implements an event-driven system that allows registering callbacks for specific data events,
    enabling reactive trading systems that respond to real-time market events.

Key Features:
    - Event-driven callback system for real-time data processing
    - Support for both async and sync callbacks
    - Multiple callbacks per event type
    - Error isolation to prevent callback failures
    - Thread-safe callback registration and management
    - Comprehensive event data structures

Event Types:
    - "new_bar": Triggered when a new OHLCV bar is created in any timeframe
    - "data_update": Triggered on every tick update with price and volume information

Callback Capabilities:
    - Registration and removal of callbacks for specific events
    - Support for both synchronous and asynchronous callback functions
    - Error handling and isolation to prevent callback failures
    - Event data structures with comprehensive market information
    - Thread-safe operations with proper error handling

Example Usage:
    ```python
    # V3.1: TradingSuite provides integrated event handling
    from project_x_py import TradingSuite, EventType

    # V3.1: Create suite with data manager and event bus
    suite = await TradingSuite.create(
        "MNQ",
        timeframes=["1min", "5min", "15min"],
        initial_days=5,
    )


    # V3.1: Register callbacks through suite's event bus
    @suite.events.on(EventType.NEW_BAR)
    async def on_new_bar(event):
        tf = event.data["timeframe"]
        bar = event.data["data"]
        print(
            f"New {tf} bar: O={bar['open']}, H={bar['high']}, L={bar['low']}, C={bar['close']}"
        )

        # V3.1: Implement trading logic with actual field names
        if tf == "5min" and bar["close"] > bar["open"]:
            # Bullish bar detected
            print(f"Bullish 5min bar detected at {event.data['bar_time']}")

            # V3.1: Emit custom events for strategy
            await suite.events.emit(
                EventType.CUSTOM,
                {"event": "bullish_signal", "timeframe": tf, "price": bar["close"]},
            )


    # V3.1: Register for tick updates
    @suite.events.on(EventType.DATA_UPDATE)
    async def on_tick(event):
        # This is called on every tick - keep it lightweight!
        data = event.data
        print(f"Price: {data['price']}, Volume: {data['volume']}")


    # V3.1: Alternative registration method
    async def bar_callback(event):
        print(f"Bar update: {event.data}")


    await suite.on(EventType.NEW_BAR, bar_callback)
    ```

Event Data Structures:
    "new_bar" event data contains:
        {
            "timeframe": "5min",                  # The timeframe of the bar
            "bar_time": datetime(2023,5,1,10,0),  # Bar timestamp (timezone-aware)
            "data": {                             # Complete bar data
                "timestamp": datetime(...),       # Bar timestamp
                "open": 1950.5,                   # Opening price
                "high": 1955.2,                   # High price
                "low": 1950.0,                    # Low price
                "close": 1954.8,                  # Closing price
                "volume": 128                     # Bar volume
            }
        }

    "data_update" event data contains:
        {
            "timestamp": datetime(2023,5,1,10,0,15),  # Tick timestamp
            "price": 1954.75,                         # Current price
            "volume": 1                               # Tick volume
        }

See Also:
    - `realtime_data_manager.core.RealtimeDataManager`
    - `realtime_data_manager.data_access.DataAccessMixin`
    - `realtime_data_manager.data_processing.DataProcessingMixin`
    - `realtime_data_manager.memory_management.MemoryManagementMixin`
    - `realtime_data_manager.validation.ValidationMixin`
"""

import logging
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any

from project_x_py.event_bus import EventType

if TYPE_CHECKING:
    from project_x_py.types import RealtimeDataManagerProtocol

logger = logging.getLogger(__name__)


_EVENT_TYPE_MAPPING = {
    "new_bar": EventType.NEW_BAR,
    "data_update": EventType.DATA_UPDATE,
    "quote_update": EventType.QUOTE_UPDATE,
    "trade_tick": EventType.TRADE_TICK,
    "market_trade": EventType.TRADE_TICK,
}


class CallbackMixin:
    """Mixin for event handling through EventBus."""

    async def add_callback(
        self: "RealtimeDataManagerProtocol",
        event_type: str,
        callback: Callable[[dict[str, Any]], Coroutine[Any, Any, None] | None],
    ) -> None:
        """
        DEPRECATED: Use TradingSuite.on() with EventType enum instead.

        This method is provided for backward compatibility only and will be removed in v4.0.
        Please migrate to the new EventBus system:

        ```python
        # Old way (deprecated)
        await data_manager.add_callback("new_bar", callback)

        # New way
        await suite.on(EventType.NEW_BAR, callback)
        ```

        Args:
            event_type: Type of event to listen for
            callback: Function or coroutine to call when the event occurs

        Event Data Structures:
            "new_bar" event data contains:
                {
                    "timeframe": "5min",                  # The timeframe of the bar
                    "bar_time": datetime(2023,5,1,10,0),  # Bar timestamp (timezone-aware)
                    "data": {                             # Complete bar data
                        "timestamp": datetime(...),       # Bar timestamp
                        "open": 1950.5,                   # Opening price
                        "high": 1955.2,                   # High price
                        "low": 1950.0,                    # Low price
                        "close": 1954.8,                  # Closing price
                        "volume": 128                     # Bar volume
                    }
                }

            "data_update" event data contains:
                {
                    "timestamp": datetime(2023,5,1,10,0,15),  # Tick timestamp
                    "price": 1954.75,                         # Current price
                    "volume": 1                               # Tick volume
                }

        Example:
            ```python
            # Register an async callback for new bar events
            async def on_new_bar(data):
                tf = data["timeframe"]
                bar = data["data"]
                print(
                    f"New {tf} bar: O={bar['open']}, H={bar['high']}, L={bar['low']}, C={bar['close']}"
                )

                # Implement trading logic based on the new bar
                if tf == "5min" and bar["close"] > bar["open"]:
                    # Bullish bar detected
                    print(f"Bullish 5min bar detected at {data['bar_time']}")

                    # Trigger trading logic (implement your strategy here)
                    # await strategy.on_bullish_bar(data)


            # Register the callback
            await data_manager.add_callback("new_bar", on_new_bar)


            # You can also use regular (non-async) functions
            def on_data_update(data):
                # This is called on every tick - keep it lightweight!
                print(f"Price update: {data['price']}")


            await data_manager.add_callback("data_update", on_data_update)
            ```

        Note:
            - Multiple callbacks can be registered for the same event type
            - Callbacks are executed sequentially for each event
            - For high-frequency events like "data_update", keep callbacks lightweight
              to avoid processing bottlenecks
            - Exceptions in callbacks are caught and logged, preventing them from
              affecting the data manager's operation
        """
        if event_type in _EVENT_TYPE_MAPPING:
            await self.event_bus.on(_EVENT_TYPE_MAPPING[event_type], callback)
        else:
            self.logger.warning(f"Unknown event type: {event_type}")

    async def _trigger_callbacks(
        self: "RealtimeDataManagerProtocol", event_type: str, data: dict[str, Any]
    ) -> None:
        """
        Emit events through EventBus.

        Args:
            event_type: Type of event to trigger
            data: Data to pass to callbacks
        """
        if event_type in _EVENT_TYPE_MAPPING:
            await self.event_bus.emit(
                _EVENT_TYPE_MAPPING[event_type], data, source="RealtimeDataManager"
            )
        else:
            self.logger.warning(f"Unknown event type: {event_type}")
