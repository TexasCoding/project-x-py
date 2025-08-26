"""
Async ProjectX Realtime Client for ProjectX Gateway API

Author: @TexasCoding
Date: 2025-08-02

Overview:
    Provides an async Python client for the ProjectX real-time API, which provides
    access to the ProjectX trading platform real-time events via SignalR WebSocket
    connections. Implements dual-hub architecture for user and market data streams.

Key Features:
    - Full async/await support for all operations
    - Asyncio-based connection management
    - Non-blocking event processing
    - Async callbacks for all events
    - Dual-hub SignalR connections (User + Market)
    - Automatic reconnection with exponential backoff
    - JWT token authentication and refresh handling
    - Thread-safe event processing and callback execution
    - Connection health monitoring and statistics

Architecture:
    - Pure event forwarding (no business logic)
    - No data caching (handled by managers)
    - No payload parsing (managers handle ProjectX formats)
    - Minimal stateful operations
    - Mixin-based design for modular functionality

Real-time Hubs:
    - User Hub: Account, position, and order updates
    - Market Hub: Quote, trade, and market depth data

Note:
    This class forms the low-level foundation for real-time data. For most applications,
    the `TradingSuite` is the recommended entry point as it abstracts away the direct
    management of this client, its connections, and its events.

Example Usage:
    For most applications, use TradingSuite which manages the real-time client
    automatically. The example below shows low-level direct usage.

    ```python
    # V3.1: TradingSuite manages real-time client internally
    import asyncio
    from project_x_py import TradingSuite


    async def main():
        # V3.1: TradingSuite creates and configures real-time client
        suite = await TradingSuite.create(
            "MNQ",
            timeframes=["1min", "5min"],
            initial_days=1,
        )

        # V3.1: Real-time client is accessible if needed
        print(f"User Hub: {suite.realtime_client.user_connected}")
        print(f"Market Hub: {suite.realtime_client.market_connected}")

        # V3.1: Subscriptions are handled automatically
        # suite.realtime_client already subscribed to user updates
        # and market data for the configured instrument

        # V3.1: Process events through suite's managers
        await asyncio.sleep(60)

        # V3.1: Clean disconnect
        await suite.disconnect()


    # V3.1: Low-level direct usage (advanced users only)
    # from project_x_py.realtime import ProjectXRealtimeClient
    # realtime = ProjectXRealtimeClient(
    #     jwt_token=client.session_token,
    #     account_id=str(client.account_info.id),
    # )
    # await realtime.connect()
    # await realtime.subscribe_market_data(["MNQ", "ES"])

    asyncio.run(main())
    ```

Event Types (per ProjectX Gateway docs):
    User Hub: GatewayUserAccount, GatewayUserPosition, GatewayUserOrder, GatewayUserTrade
    Market Hub: GatewayQuote, GatewayDepth, GatewayTrade

Integration:
    - AsyncPositionManager handles position events and caching
    - AsyncOrderManager handles order events and tracking
    - AsyncRealtimeDataManager handles market data and caching
    - This client only handles connections and event forwarding
"""

import asyncio
import logging
from collections import defaultdict
from typing import TYPE_CHECKING, Any

from project_x_py.realtime.connection_management import ConnectionManagementMixin
from project_x_py.realtime.event_handling import EventHandlingMixin
from project_x_py.realtime.health_monitoring import HealthMonitoringMixin
from project_x_py.realtime.subscriptions import SubscriptionsMixin
from project_x_py.types.base import HubConnection
from project_x_py.utils.task_management import TaskManagerMixin

if TYPE_CHECKING:
    from project_x_py.models import ProjectXConfig


class ProjectXRealtimeClient(
    ConnectionManagementMixin,
    EventHandlingMixin,
    HealthMonitoringMixin,
    SubscriptionsMixin,
    TaskManagerMixin,
):
    """
    Async real-time client for ProjectX Gateway API WebSocket connections.

    **CRITICAL FIXES (v3.3.1)**: This class now includes comprehensive safety mechanisms
    to prevent deadlocks, memory leaks, and connection failures in production environments.

    This class provides an async interface for ProjectX SignalR connections and
    forwards all events to registered managers. It does NOT cache data or perform
    business logic - that's handled by the specialized managers.

    **Safety Features (v3.3.1)**:
        - **Task Lifecycle Management**: Automatic tracking and cleanup of async tasks
        - **Deadlock Prevention**: Timeout-based token refresh with state recovery
        - **Memory Leak Protection**: WeakSet-based task tracking prevents accumulation
        - **Connection Recovery**: Automatic rollback to stable state on failures
        - **Health Monitoring**: Comprehensive connection health tracking and automatic recovery

    Features:
        - Async SignalR WebSocket connections to ProjectX Gateway hubs
        - Event forwarding to registered async managers
        - Automatic reconnection with exponential backoff
        - JWT token refresh and reconnection with deadlock prevention
        - **Real-time connection health monitoring with heartbeat mechanism**
        - **Latency tracking and performance metrics**
        - **Automatic reconnection based on health thresholds**
        - Async event callbacks
        - Thread-safe event processing and callback execution
        - Comprehensive connection statistics and health tracking
        - **NEW**: Centralized task management prevents memory leaks
        - **NEW**: Connection state recovery on failures
        - **NEW**: Health-based automatic reconnection triggers

    Architecture:
        - Pure event forwarding (no business logic)
        - No data caching (handled by managers)
        - No payload parsing (managers handle ProjectX formats)
        - Minimal stateful operations
        - Mixin-based design for modular functionality
        - **NEW**: TaskManagerMixin provides automatic task cleanup

    Real-time Hubs (per ProjectX Gateway docs):
        - User Hub: Account, position, and order updates
        - Market Hub: Quote, trade, and market depth data

    Connection Management:
        - Dual-hub SignalR connections with automatic reconnection
        - JWT token authentication via URL query parameter (required by ProjectX Gateway)
        - **Real-time health monitoring with heartbeat latency tracking**
        - **Automatic health-based reconnection when performance degrades**
        - Connection error handling and performance metrics
        - Thread-safe operations with proper lock management
        - **NEW**: Timeout-based operations prevent indefinite blocking
        - **NEW**: Connection state recovery preserves subscriptions
        - **NEW**: Health thresholds trigger automatic recovery

    Event Processing:
        - Cross-thread event scheduling for asyncio compatibility
        - Support for both async and sync callbacks
        - Error isolation to prevent callback failures
        - Event statistics and flow monitoring

    **Task Management (v3.3.1)**:
        - All background tasks are automatically tracked
        - WeakSet-based tracking prevents memory leaks
        - Graceful cancellation with configurable timeouts
        - Error collection and reporting for failed tasks
        - Statistics available via `get_task_stats()`

    Example:
        >>> # V3.1: Use TradingSuite for automatic real-time management
        >>> suite = await TradingSuite.create("MNQ", timeframes=["1min"])
        >>> # V3.1: Access real-time client if needed
        >>> print(f"Connected: {suite.realtime_client.is_connected()}")
        >>>
        >>> # V3.3.1: Task management statistics
        >>> task_stats = suite.realtime_client.get_task_stats()
        >>> print(f"Active tasks: {task_stats['pending_tasks']}")
        >>> print(f"Failed tasks: {task_stats['failed_tasks']}")
        >>>
        >>> # V3.3.1: Health monitoring (NEW)
        >>> health_status = await suite.realtime_client.get_health_status()
        >>> print(f"Health Score: {health_status['health_score']}/100")
        >>> print(f"User Hub Latency: {health_status['user_hub_latency_ms']}ms")
        >>> print(f"Market Hub Latency: {health_status['market_hub_latency_ms']}ms")
        >>>
        >>> # V3.3.1: Configure health monitoring
        >>> await suite.realtime_client.configure_health_monitoring(
        ...     heartbeat_interval=5.0,  # Check every 5 seconds
        ...     health_threshold=75.0,  # Reconnect if health < 75
        ...     latency_threshold_ms=1000,  # Alert if latency > 1000ms
        ... )
        >>>
        >>> # V3.1: Register callbacks via suite's event bus
        >>> from project_x_py import EventType
        >>> async def handle_position(event):
        ...     data = event.data
        ...     print(f"Position: {data.get('contractId')} - {data.get('netPos')}")
        >>> await suite.on(EventType.POSITION_UPDATE, handle_position)
        >>>
        >>> # V3.3.1: Safe token refresh with deadlock prevention
        >>> try:
        ...     success = await suite.realtime_client.update_jwt_token(
        ...         new_token, timeout=30.0
        ...     )
        ...     if not success:
        ...         print(
        ...             "Token refresh failed, connection recovered to original state"
        ...         )
        ... except TimeoutError:
        ...     print("Token refresh timed out, deadlock prevented")

    Event Types (per ProjectX Gateway docs):
        User Hub: GatewayUserAccount, GatewayUserPosition, GatewayUserOrder, GatewayUserTrade
        Market Hub: GatewayQuote, GatewayDepth, GatewayTrade

    Integration:
        - AsyncPositionManager handles position events and caching
        - AsyncOrderManager handles order events and tracking
        - AsyncRealtimeDataManager handles market data and caching
        - This client only handles connections and event forwarding

    **Production Reliability (v3.3.1)**:
        - Zero memory leaks from task accumulation
        - No deadlocks during token refresh operations
        - Automatic recovery from connection failures
        - Comprehensive error handling and logging
        - Performance monitoring through task statistics
    """

    def __init__(
        self,
        jwt_token: str,
        account_id: str,
        user_hub_url: str | None = None,
        market_hub_url: str | None = None,
        config: "ProjectXConfig | None" = None,
    ):
        """
        Initialize async ProjectX real-time client with configurable SignalR connections.

        Creates a dual-hub SignalR client for real-time ProjectX Gateway communication.
        Handles both user-specific events (positions, orders) and market data (quotes, trades).

        Args:
            jwt_token (str): JWT authentication token from AsyncProjectX.authenticate().
                Must be valid and not expired for successful connection.
            account_id (str): ProjectX account ID for user-specific subscriptions.
                Used to filter position, order, and trade events.
            user_hub_url (str, optional): Override URL for user hub endpoint.
                If provided, takes precedence over config URL.
                Defaults to None (uses config or default).
            market_hub_url (str, optional): Override URL for market hub endpoint.
                If provided, takes precedence over config URL.
                Defaults to None (uses config or default).
            config (ProjectXConfig, optional): Configuration object with hub URLs.
                Provides default URLs if direct URLs not specified.
                Defaults to None (uses TopStepX defaults).

        URL Priority:
            1. Direct parameters (user_hub_url, market_hub_url)
            2. Config URLs (config.user_hub_url, config.market_hub_url)
            3. Default TopStepX endpoints

        Example:
            >>> # V3: Using factory function (recommended)
            >>> client = await create_realtime_client(
            ...     jwt_token=client.get_session_token(),
            ...     account_id=str(client.get_account_info().id),
            ... )
            >>> # V3: Using direct instantiation with default endpoints
            >>> client = ProjectXRealtimeClient(jwt_token=jwt_token, account_id="12345")
            >>>
            >>> # V3: Using custom config for different environments
            >>> from project_x_py.models import ProjectXConfig
            >>> config = ProjectXConfig(
            ...     user_hub_url="https://gateway.topstepx.com/hubs/user",
            ...     market_hub_url="https://gateway.topstepx.com/hubs/market",
            ... )
            >>> client = ProjectXRealtimeClient(
            ...     jwt_token=jwt_token, account_id="12345", config=config
            ... )
            >>>
            >>> # V3: Override specific URL for testing
            >>> client = ProjectXRealtimeClient(
            ...     jwt_token=jwt_token,
            ...     account_id="12345",
            ...     market_hub_url="https://test.topstepx.com/hubs/market",
            ... )

        Note:
            - JWT token is passed via URL query parameter (required by ProjectX Gateway)
            - Both hubs must connect successfully for full functionality
            - SignalR connections are established lazily on connect()
        """
        # Initialize parent mixins
        super().__init__()
        self._init_task_manager()  # Initialize task management

        self.jwt_token = jwt_token
        self.account_id = account_id

        # Store config for URL access
        from project_x_py.models import ProjectXConfig

        self.config = config or ProjectXConfig()

        # Determine URLs with priority: params > config > defaults
        if config:
            default_user_url = config.user_hub_url
            default_market_url = config.market_hub_url
        else:
            # Default to TopStepX endpoints
            default_user_url = "https://rtc.topstepx.com/hubs/user"
            default_market_url = "https://rtc.topstepx.com/hubs/market"

        final_user_url = user_hub_url or default_user_url
        final_market_url = market_hub_url or default_market_url

        # Store URLs without tokens (tokens will be passed in headers)
        self.user_hub_url = final_user_url
        self.market_hub_url = final_market_url

        # Set up base URLs for token refresh
        # Priority: direct parameters > config > defaults
        if user_hub_url or market_hub_url:
            # Use provided URLs (with fallback to final URLs which include config/defaults)
            self.base_user_url = user_hub_url or final_user_url
            self.base_market_url = market_hub_url or final_market_url
        elif config:
            # Use config URLs if no direct parameters provided
            self.base_user_url = config.user_hub_url
            self.base_market_url = config.market_hub_url
        else:
            # Default to TopStepX endpoints
            self.base_user_url = "https://rtc.topstepx.com/hubs/user"
            self.base_market_url = "https://rtc.topstepx.com/hubs/market"

        # SignalR connection objects
        self.user_connection: HubConnection | None = None
        self.market_connection: HubConnection | None = None

        # Connection state tracking
        self.user_connected = False
        self.market_connected = False
        self.setup_complete = False

        # Event callbacks (pure forwarding, no caching)
        self.callbacks: defaultdict[str, list[Any]] = defaultdict(list)

        # Basic statistics (no business logic)
        self.stats = {
            "events_received": 0,
            "connection_errors": 0,
            "last_event_time": None,
            "connected_time": None,
        }

        # Track subscribed contracts for reconnection
        self._subscribed_contracts: list[str] = []

        # Logger
        self.logger = logging.getLogger(__name__)

        self.logger.info("AsyncProjectX real-time client initialized")
        self.logger.info(f"User Hub: {final_user_url}")
        self.logger.info(f"Market Hub: {final_market_url}")

        # Async locks for thread-safe operations
        self._callback_lock = asyncio.Lock()
        self._connection_lock = asyncio.Lock()

        # Async events for connection readiness
        self.user_hub_ready = asyncio.Event()
        self.market_hub_ready = asyncio.Event()
