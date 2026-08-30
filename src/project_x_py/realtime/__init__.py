"""
Real-time client module for ProjectX Gateway API WebSocket connections.

Author: @TexasCoding
Date: 2025-08-02

Overview:
    Provides the ProjectXRealtimeClient class for managing real-time connections
    to ProjectX SignalR hubs. Enables WebSocket-based streaming of market data,
    position updates, order events, and account information with full async/await
    support and automatic reconnection capabilities.

Key Features:
    - Dual-hub SignalR connections (User Hub + Market Hub)
    - Async/await support for all operations
    - Automatic reconnection with exponential backoff
    - JWT token authentication and refresh handling
    - Event-driven callback system for custom processing
    - Thread-safe operations with proper error handling
    - **Real-time connection health monitoring with heartbeat mechanism**
    - **Latency tracking and performance metrics**
    - **Automatic reconnection based on health thresholds**

Real-time Capabilities:
    - User Hub: Account, position, order, and trade events
    - Market Hub: Quote, trade, and market depth data
    - Event forwarding to registered managers
    - Subscription management for specific contracts
    - **Comprehensive health monitoring and performance tracking**
    - **Health-based automatic reconnection triggers**

Note:
    While this module provides direct access to the real-time client, for most
    trading applications, it is recommended to use the `TradingSuite`. The suite
    manages the real-time client, data processing, and event handling automatically,
    offering a simpler and more robust development experience.

Example Usage:
    For most applications, use TradingSuite which handles the real-time client automatically.
    The example below shows low-level direct usage of `ProjectXRealtimeClient`.

    ```python
    # V3.1: TradingSuite manages real-time client automatically
    import asyncio
    from project_x_py import TradingSuite, EventType


    async def main():
        # V3.1: TradingSuite creates and manages real-time client internally
        suite = await TradingSuite.create(
            "MNQ",
            timeframes=["1min", "5min"],
            initial_days=1,
        )

        # V3.1: Register event handlers via suite's event bus
        async def on_position_update(event):
            data = event.data
            print(f"Position update: {data}")
            if "size" in data:
                print(f"  Size: {data['size']}")
                print(f"  Average Price: ${data.get('averagePrice', 0):.2f}")

        async def on_quote_update(event):
            data = event.data
            if "bid" in data and "ask" in data:
                print(f"{suite.instrument}: {data['bid']} x {data['ask']}")

        # V3.1: Add event handlers via suite's event bus
        await suite.on(EventType.POSITION_UPDATE, on_position_update)
        await suite.on(EventType.QUOTE, on_quote_update)

        # V3.1: Real-time connection and subscriptions are automatic
        print(f"Connected to {suite.instrument} real-time feeds")
        print(f"Account: {suite.client.account_info.name}")

        # V3.1: Process events for 60 seconds
        await asyncio.sleep(60)

        # V3.1: Clean up is automatic with context manager
        await suite.disconnect()


    # V3.1: Low-level direct usage is available for advanced users
    # See documentation for direct ProjectXRealtimeClient usage

    asyncio.run(main())
    ```

See Also:
    - `realtime.core.ProjectXRealtimeClient`
    - `realtime.connection_management.ConnectionManagementMixin`
    - `realtime.event_handling.EventHandlingMixin`
    - `realtime.subscriptions.SubscriptionsMixin`
"""

from project_x_py.realtime.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitBreakerMetrics,
    CircuitBreakerMixin,
    CircuitState,
)
from project_x_py.realtime.core import ProjectXRealtimeClient

__all__ = [
    "ProjectXRealtimeClient",
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerError",
    "CircuitBreakerMixin",
    "CircuitBreakerMetrics",
    "CircuitState",
]
