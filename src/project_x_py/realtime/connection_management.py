"""
Connection management functionality for real-time client.

Author: @TexasCoding
Date: 2025-08-02

Overview:
    Provides connection management functionality for the ProjectX real-time client,
    including SignalR hub setup, connection establishment, reconnection handling,
    and secure JWT token authentication.

Key Features:
    - Dual-hub SignalR connection setup and management
    - Automatic reconnection with exponential backoff
    - JWT token authentication via URL query parameter (ProjectX Gateway requirement)
    - Connection health monitoring and error handling
    - Thread-safe operations with proper lock management
    - Comprehensive connection statistics and health tracking

Connection Management Capabilities:
    - SignalR hub setup with ProjectX Gateway configuration
    - Connection establishment and health monitoring
    - Automatic reconnection with configurable intervals
    - JWT token authentication via URL query parameter (ProjectX Gateway requirement)
    - JWT token refresh and reconnection handling
    - Connection event handling and error processing
    - Statistics tracking and health reporting

Example Usage:
    The functionality of this mixin is consumed through a `ProjectXRealtimeClient` instance.
    For most use cases, this is handled automatically by the `TradingSuite`.

    ```python
    # The following demonstrates the low-level connection lifecycle managed by this mixin.
    # Note: In a typical application, you would use TradingSuite, which handles this.
    from project_x_py import create_realtime_client

    # 1. Initialization (handled by factory or TradingSuite)
    # realtime_client = await create_realtime_client(jwt, account_id)

    # 2. Connection (handled by TradingSuite.create() or client.connect())
    # if await realtime_client.connect():
    #     print("Successfully connected to both User and Market hubs.")

    #     # 3. Health Monitoring
    #     if realtime_client.is_connected():
    #         stats = realtime_client.get_stats()
    #         print(f"Events received so far: {stats['events_received']}")

    #     # 4. Token Refresh (if managing tokens manually)
    #     # new_token = await get_new_token()
    #     # await realtime_client.update_jwt_token(new_token)

    #     # 5. Disconnection (handled by TradingSuite context manager or client.disconnect())
    #     await realtime_client.disconnect()
    ```

See Also:
    - `realtime.core.ProjectXRealtimeClient`
    - `realtime.event_handling.EventHandlingMixin`
    - `realtime.subscriptions.SubscriptionsMixin`
"""

import asyncio
from datetime import datetime
from typing import TYPE_CHECKING, Any

from project_x_py.realtime.async_hub import HubConnectionBuilder, invoke_maybe
from project_x_py.utils import (
    LogContext,
    LogMessages,
    ProjectXLogger,
    handle_errors,
)

if TYPE_CHECKING:
    from project_x_py.types import ProjectXRealtimeClientProtocol

logger = ProjectXLogger.get_logger(__name__)


class ConnectionManagementMixin:
    """Mixin for connection management functionality."""

    def __init__(self) -> None:
        """Initialize connection management attributes."""
        super().__init__()
        self._loop: asyncio.AbstractEventLoop | None = None

    @handle_errors("setup connections")
    async def setup_connections(self: "ProjectXRealtimeClientProtocol") -> None:
        """
        Set up SignalR hub connections with ProjectX Gateway configuration.

        Initializes both user and market hub connections with secure JWT authentication,
        proper event handlers, automatic reconnection, and ProjectX-specific event mappings.
        Must be called before connect() or is called automatically on first connect().

        Hub Configuration:
            - User Hub: Account, position, order, and trade events
            - Market Hub: Quote, trade, and market depth events
            - Both hubs: Automatic reconnection with exponential backoff
            - Keep-alive: 10 second interval
            - Reconnect intervals: [1, 3, 5, 5, 5, 5] seconds

        Authentication:
            - JWT token in URL query parameter (ProjectX Gateway requirement)

        Event Mappings:
            User Hub Events:
                - GatewayUserAccount -> account_update
                - GatewayUserPosition -> position_update
                - GatewayUserOrder -> order_update
                - GatewayUserTrade -> trade_execution

            Market Hub Events:
                - GatewayQuote -> quote_update
                - GatewayTrade -> market_trade
                - GatewayDepth -> market_depth

        Raises:
            ImportError: If the async SignalR client cannot be imported
            Exception: If connection setup fails

        Note:
            This method is idempotent - safe to call multiple times.
            Sets self.setup_complete = True when successful.
        """
        with LogContext(
            logger,
            operation="setup_connections",
            user_hub=self.user_hub_url,
            market_hub=self.market_hub_url,
        ):
            logger.debug(LogMessages.WS_CONNECT, extra={"phase": "setup"})

            async with self._connection_lock:
                logger.info(
                    "Using URL query parameter for JWT authentication (ProjectX Gateway requirement)"
                )
                # Build user hub connection with JWT as query parameter
                # ProjectX Gateway requires auth tokens in URL for WebSocket connections
                user_url_with_token = (
                    f"{self.user_hub_url}?access_token={self.jwt_token}"
                )
                self.user_connection = (
                    HubConnectionBuilder()
                    .with_url(user_url_with_token, hub_name="user")
                    .configure_logging(
                        logger.level,
                        socket_trace=False,
                        handler=None,
                    )
                    .with_automatic_reconnect(
                        {
                            "type": "interval",
                            "keep_alive_interval": 10,
                            "intervals": [1, 3, 5, 5, 5, 5],
                        }
                    )
                    .build()
                )

                # Build market hub connection with JWT as query parameter
                market_url_with_token = (
                    f"{self.market_hub_url}?access_token={self.jwt_token}"
                )
                self.market_connection = (
                    HubConnectionBuilder()
                    .with_url(market_url_with_token, hub_name="market")
                    .configure_logging(
                        logger.level,
                        socket_trace=False,
                        handler=None,  # Use None to avoid duplicate logging
                    )
                    .with_automatic_reconnect(
                        {
                            "type": "interval",
                            "keep_alive_interval": 10,
                            "intervals": [1, 3, 5, 5, 5, 5],
                        }
                    )
                    .build()
                )

                # Set up connection event handlers
                assert self.user_connection is not None
                assert self.market_connection is not None

                self.user_connection.on_open(lambda: self._on_user_hub_open())
                self.user_connection.on_close(lambda: self._on_user_hub_close())
                self.user_connection.on_error(
                    lambda data: self._on_connection_error("user", data)
                )

                self.market_connection.on_open(lambda: self._on_market_hub_open())
                self.market_connection.on_close(lambda: self._on_market_hub_close())
                self.market_connection.on_error(
                    lambda data: self._on_connection_error("market", data)
                )

                # Set up ProjectX Gateway event handlers (per official documentation)
                # User Hub Events
                self.user_connection.on(
                    "GatewayUserAccount", self._forward_account_update
                )
                self.user_connection.on(
                    "GatewayUserPosition", self._forward_position_update
                )
                self.user_connection.on("GatewayUserOrder", self._forward_order_update)
                self.user_connection.on(
                    "GatewayUserTrade", self._forward_trade_execution
                )
                self.user_connection.on("GatewayLogout", self._on_gateway_logout)

                # Market Hub Events
                self.market_connection.on("GatewayQuote", self._forward_quote_update)
                self.market_connection.on("GatewayTrade", self._forward_market_trade)
                self.market_connection.on("GatewayDepth", self._forward_market_depth)
                self.market_connection.on("GatewayLogout", self._on_gateway_logout)

                logger.debug(
                    LogMessages.WS_CONNECTED, extra={"phase": "setup_complete"}
                )
                self.setup_complete = True

    @handle_errors("connect", reraise=False, default_return=False)
    async def connect(self: "ProjectXRealtimeClientProtocol") -> bool:
        """
        Connect to ProjectX Gateway SignalR hubs asynchronously.

        Establishes connections to both user and market hubs, enabling real-time
        event streaming. Connections are made concurrently for efficiency.

        Returns:
            bool: True if both hubs connected successfully, False otherwise

        Connection Process:
            1. Sets up connections if not already done
            2. Stores event loop for cross-thread operations
            3. Starts user hub connection
            4. Starts market hub connection
            5. Waits for connection establishment
            6. Updates connection statistics

        Example:
            >>> # V3.1: TradingSuite handles connection automatically
            >>> suite = await TradingSuite.create("MNQ", timeframes=["1min"])
            >>> print(f"Connected: {suite.realtime_client.is_connected()}")
            >>> # V3.1: Direct usage (advanced)
            >>> # client = ProjectXRealtimeClient(jwt_token, account_id)
            >>> # if await client.connect():
            >>> #     await client.subscribe_market_data(["MNQ", "ES"])

        Side Effects:
            - Sets self.user_connected and self.market_connected flags
            - Updates connection statistics
            - Stores event loop reference

        Note:
            - Both hubs must connect for success
            - SignalR connections run in thread executor for async compatibility
            - Automatic reconnection is configured but initial connect may fail
        """
        with LogContext(
            logger,
            operation="connect",
            account_id=self.account_id,
        ):
            # Capture the loop before setup so SignalR callbacks can dispatch.
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                logger.error("No running event loop found.")
                return False

            if not self.setup_complete:
                await self.setup_connections()

            logger.debug(LogMessages.WS_CONNECT)

            async with self._connection_lock:
                # Start both connections
                if self.user_connection:
                    await self._start_connection_async(self.user_connection, "user")
                else:
                    logger.error(
                        LogMessages.WS_ERROR,
                        extra={"error": "User connection not available"},
                    )
                    return False

                if self.market_connection:
                    await self._start_connection_async(self.market_connection, "market")
                else:
                    logger.error(
                        LogMessages.WS_ERROR,
                        extra={"error": "Market connection not available"},
                    )
                    return False

                wait_tasks = [
                    asyncio.create_task(self.user_hub_ready.wait()),
                    asyncio.create_task(self.market_hub_ready.wait()),
                ]
                try:
                    _, pending = await asyncio.wait(wait_tasks, timeout=10.0)
                except asyncio.CancelledError:
                    for task in wait_tasks:
                        task.cancel()
                    await asyncio.gather(*wait_tasks, return_exceptions=True)
                    raise

                if pending:
                    for task in pending:
                        task.cancel()
                    await asyncio.gather(*wait_tasks, return_exceptions=True)
                    logger.error(
                        LogMessages.WS_ERROR,
                        extra={
                            "error": "Connection attempt timed out after 10 seconds."
                        },
                    )
                    return False

                if self.user_connected and self.market_connected:
                    self.stats["connected_time"] = datetime.now()
                    if hasattr(self, "_start_stale_feed_watchdog"):
                        await self._start_stale_feed_watchdog()
                    logger.debug(LogMessages.WS_CONNECTED)
                    return True
                else:
                    logger.error(
                        LogMessages.WS_ERROR,
                        extra={"error": "Failed to establish all connections"},
                    )
                    return False

    @handle_errors("start connection")
    async def _start_connection_async(
        self: "ProjectXRealtimeClientProtocol", connection: Any, name: str
    ) -> None:
        """
        Start a SignalR connection asynchronously.

        Wraps the synchronous SignalR start() method to work with asyncio by
        running it in a thread executor.

        Args:
            connection: SignalR HubConnection instance to start
            name (str): Hub name for logging ("user" or "market")

        Note:
            This is an internal method that bridges sync SignalR with async code.
        """
        await invoke_maybe(connection.start)
        logger.debug(LogMessages.WS_CONNECTED, extra={"hub": name})

    @handle_errors("disconnect")
    async def disconnect(self: "ProjectXRealtimeClientProtocol") -> None:
        """
        Disconnect from ProjectX Gateway hubs.

        Gracefully closes both user and market hub connections. Safe to call
        even if not connected. Clears connection flags but preserves callbacks
        and subscriptions for potential reconnection.

        Example:
            >>> # Graceful shutdown
            >>> await client.disconnect()
            >>> print("Disconnected from ProjectX Gateway")
            >>>
            >>> # Can reconnect later
            >>> if await client.connect():
            ...     # Previous subscriptions must be re-established
            ...     await client.subscribe_user_updates()

        Side Effects:
            - Sets self.user_connected = False
            - Sets self.market_connected = False
            - Stops SignalR connections

        Note:
            Does not clear callbacks or subscription lists, allowing for
            reconnection with the same configuration.
        """
        with LogContext(
            logger,
            operation="disconnect",
            account_id=self.account_id,
        ):
            logger.debug(LogMessages.WS_DISCONNECT)

            if hasattr(self, "_stop_stale_feed_watchdog"):
                await self._stop_stale_feed_watchdog()

            async with self._connection_lock:
                if self.user_connection:
                    await invoke_maybe(self.user_connection.stop)
                    self.user_connected = False

                if self.market_connection:
                    await invoke_maybe(self.market_connection.stop)
                    self.market_connected = False

                logger.debug(LogMessages.WS_DISCONNECTED)

    # Connection event handlers
    def _schedule_subscription_restore(
        self: "ProjectXRealtimeClientProtocol",
    ) -> None:
        """Queue subscription restore after a hub reopen (not the first connect)."""
        should_restore = getattr(self, "_user_updates_subscribed", False) or bool(
            getattr(self, "_subscribed_contracts", [])
        )
        if not should_restore:
            return
        restore = getattr(self, "_restore_realtime_subscriptions", None)
        if restore is None:
            return
        loop = getattr(self, "_loop", None)
        if loop is None:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                return
        loop.create_task(restore())

    def _on_user_hub_open(self: "ProjectXRealtimeClientProtocol") -> None:
        """
        Handle user hub connection open.

        Called by SignalR when user hub connection is established.
        Sets connection flag and logs success.

        Side Effects:
            - Sets self.user_connected = True
            - Logs connection success
        """
        self.user_connected = True
        self.user_hub_ready.set()
        self.logger.info("✅ User hub connected")
        self._schedule_subscription_restore()

    def _on_user_hub_close(self: "ProjectXRealtimeClientProtocol") -> None:
        """
        Handle user hub connection close.

        Called by SignalR when user hub connection is lost.
        Clears connection flag and logs warning.

        Side Effects:
            - Sets self.user_connected = False
            - Logs disconnection warning

        Note:
            Automatic reconnection will attempt based on configuration.
        """
        self.user_connected = False
        self.user_hub_ready.clear()
        self.logger.warning("❌ User hub disconnected")

    def _on_market_hub_open(self: "ProjectXRealtimeClientProtocol") -> None:
        """
        Handle market hub connection open.

        Called by SignalR when market hub connection is established.
        Sets connection flag and logs success.

        Side Effects:
            - Sets self.market_connected = True
            - Logs connection success
        """
        self.market_connected = True
        self.market_hub_ready.set()
        self.logger.info("✅ Market hub connected")
        self._schedule_subscription_restore()

    def _on_market_hub_close(self: "ProjectXRealtimeClientProtocol") -> None:
        """
        Handle market hub connection close.

        Called by SignalR when market hub connection is lost.
        Clears connection flag and logs warning.

        Side Effects:
            - Sets self.market_connected = False
            - Logs disconnection warning

        Note:
            Automatic reconnection will attempt based on configuration.
        """
        self.market_connected = False
        self.market_hub_ready.clear()
        self.logger.warning("❌ Market hub disconnected")

    def _on_gateway_logout(self: "ProjectXRealtimeClientProtocol", *args: Any) -> None:
        """Handle GatewayLogout so it is not treated as an unhandled hub event."""
        self.logger.debug("Gateway logout event received", extra={"payload": args})

    def _on_connection_error(
        self: "ProjectXRealtimeClientProtocol", hub: str, error: Any
    ) -> None:
        """
        Handle connection errors.

        Processes errors from SignalR connections. Filters out normal completion
        messages that SignalR sends as part of its protocol.

        Args:
            hub (str): Hub name ("user" or "market")
            error: Error object or message from SignalR

        Side Effects:
            - Increments connection error counter for real errors
            - Logs errors (excludes CompletionMessage)

        Note:
            SignalR CompletionMessage is not an error - it's a normal protocol message.
        """
        # Check if this is a SignalR CompletionMessage (not an error)
        error_type = type(error).__name__
        if "CompletionMessage" in error_type:
            # This is a normal SignalR protocol message, not an error
            logger.debug(f"SignalR completion message from {hub} hub: {error}")
            return

        # Log actual errors
        logger.error(LogMessages.WS_ERROR, extra={"hub": hub, "error": str(error)})
        self.stats["connection_errors"] += 1

    @handle_errors("update JWT token", reraise=False, default_return=False)
    async def update_jwt_token(
        self: "ProjectXRealtimeClientProtocol",
        new_jwt_token: str,
        timeout: float = 30.0,
    ) -> bool:
        """
        Update JWT token and reconnect with new credentials.

        **CRITICAL FIX**: Implements deadlock prevention through timeout-based reconnection
        and connection state recovery mechanisms.

        Handles JWT token refresh for expired or updated tokens. Disconnects current
        connections, updates URLs with new token, and re-establishes all subscriptions.

        **Deadlock Prevention Features (v3.3.1)**:
            - Connection lock timeout prevents indefinite waiting
            - Automatic rollback to original state on failure
            - Connection state recovery preserves subscriptions
            - Comprehensive error handling with cleanup

        Args:
            new_jwt_token (str): New JWT authentication token from AsyncProjectX
            timeout (float): Maximum time in seconds to wait for reconnection (default: 30.0)
                           Prevents deadlocks by ensuring operation completes within timeout

        Returns:
            bool: True if reconnection successful with new token

        Process:
            1. Acquire connection lock with timeout (DEADLOCK PREVENTION)
            2. Store original state for rollback (STATE RECOVERY)
            3. Disconnect existing connections
            4. Update token and connection URLs
            5. Reset connection state
            6. Reconnect to both hubs with timeout
            7. Re-subscribe to user updates
            8. Re-subscribe to previous market data
            9. Implement connection state recovery on failure (ROLLBACK)

        **Safety Mechanisms**:
            - **Timeout Protection**: 30-second default prevents indefinite blocking
            - **State Recovery**: Original connection state restored on failure
            - **Subscription Preservation**: Market data subscriptions restored automatically
            - **Error Isolation**: Failures don't leave client in inconsistent state

        Example:
            >>> # Token refresh with deadlock prevention
            >>> async def refresh_connection():
            ...     # Get new token
            ...     await project_x.authenticate()
            ...     new_token = project_x.session_token
            ...     # Update with timeout for deadlock prevention
            ...     if await realtime_client.update_jwt_token(new_token, timeout=45.0):
            ...         print("Reconnected with new token")
            ...     else:
            ...         print("Reconnection failed, original state recovered")
            >>>
            >>> # Production usage with error handling
            >>> try:
            ...     success = await realtime_client.update_jwt_token(new_token)
            ...     if success:
            ...         logger.info("Token refresh successful")
            ...     else:
            ...         logger.error("Token refresh failed - check logs")
            ... except TimeoutError:
            ...     logger.error("Token refresh timed out - deadlock prevented")

        Side Effects:
            - Disconnects and reconnects both hubs
            - Re-subscribes to all previous subscriptions
            - Updates internal token and URLs
            - Implements recovery mechanism on failure

        **Performance Impact**:
            - Brief data gap during reconnection (~2-5 seconds)
            - Timeout overhead minimal for successful operations
            - State recovery adds safety with minimal performance cost

        Note:
            - Callbacks are preserved during reconnection
            - Market data subscriptions are restored automatically
            - **NEW**: Deadlock prevention eliminates indefinite blocking
            - **NEW**: Connection state recovery prevents inconsistent states
        """
        with LogContext(
            logger,
            operation="update_jwt_token",
            account_id=self.account_id,
            timeout=timeout,
        ):
            logger.debug(LogMessages.AUTH_REFRESH)

            # Store original state for recovery
            original_token = self.jwt_token
            original_setup_complete = self.setup_complete
            original_subscriptions = list(self._subscribed_contracts)
            try:
                # disconnect()/connect() already take _connection_lock. Holding it
                # here deadlocks because asyncio.Lock is not re-entrant.
                async with asyncio.timeout(timeout):
                    await self.disconnect()

                    # Update JWT token
                    self.jwt_token = new_jwt_token

                    # Reset setup flag to force new connection setup
                    self.setup_complete = False

                    # Reconnect with timeout
                    reconnect_success = False
                    try:
                        async with asyncio.timeout(
                            timeout * 0.7
                        ):  # Reserve time for subscriptions
                            reconnect_success = await self.connect()
                    except TimeoutError:
                        logger.error(
                            LogMessages.WS_ERROR,
                            extra={
                                "error": f"Connection timeout after {timeout * 0.7}s"
                            },
                        )
                        reconnect_success = False

                    if reconnect_success:
                        # Re-subscribe to user updates with timeout
                        try:
                            async with asyncio.timeout(
                                timeout * 0.15
                            ):  # Small portion for user updates
                                await self.subscribe_user_updates()
                        except TimeoutError:
                            logger.warning(
                                "User subscription timeout during token refresh"
                            )

                        # Re-subscribe to market data with timeout
                        if original_subscriptions:
                            try:
                                async with asyncio.timeout(
                                    timeout * 0.15
                                ):  # Small portion for market data
                                    await self.subscribe_market_data(
                                        original_subscriptions
                                    )
                            except TimeoutError:
                                logger.warning(
                                    "Market subscription timeout during token refresh"
                                )

                        logger.debug(LogMessages.WS_RECONNECT)
                        return True

                    # Connection failed - initiate recovery
                    logger.error(
                        LogMessages.WS_ERROR,
                        extra={"error": "Failed to reconnect with new JWT token"},
                    )
                    await self._recover_connection_state(
                        original_token,
                        original_setup_complete,
                        original_subscriptions,
                    )
                    return False

            except TimeoutError:
                logger.error(
                    LogMessages.WS_ERROR,
                    extra={"error": f"Token refresh timeout after {timeout}s"},
                )
                # Attempt recovery on timeout
                await self._recover_connection_state(
                    original_token, original_setup_complete, original_subscriptions
                )
                return False
            except Exception as e:
                logger.error(
                    LogMessages.WS_ERROR,
                    extra={"error": f"Token refresh failed: {e}"},
                )
                # Attempt recovery on any other error
                await self._recover_connection_state(
                    original_token, original_setup_complete, original_subscriptions
                )
                return False

    async def _recover_connection_state(
        self: "ProjectXRealtimeClientProtocol",
        original_token: str,
        original_setup_complete: bool,
        original_subscriptions: list[str],
    ) -> None:
        """
        Recover connection state after failed token refresh.

        Attempts to restore the original connection state when token refresh fails.
        This prevents the client from being left in an inconsistent state.

        Args:
            original_token: Original JWT token to restore
            original_setup_complete: Original setup completion state
            original_subscriptions: List of original market data subscriptions
        """
        logger.info("Attempting connection state recovery after failed token refresh")

        try:
            # Restore original token
            self.jwt_token = original_token
            self.setup_complete = original_setup_complete

            # Clear any partial connection state
            self.user_connected = False
            self.market_connected = False
            self.user_hub_ready.clear()
            self.market_hub_ready.clear()

            # Try to reconnect with original token (short timeout)
            recovery_timeout = 10.0
            try:
                async with asyncio.timeout(recovery_timeout):
                    if await self.connect():
                        logger.info(
                            "Successfully recovered connection with original token"
                        )

                        # Restore subscriptions
                        try:
                            await self.subscribe_user_updates()
                            if original_subscriptions:
                                await self.subscribe_market_data(original_subscriptions)
                            logger.info("Successfully restored subscriptions")
                        except Exception as e:
                            logger.warning(f"Failed to restore subscriptions: {e}")
                    else:
                        logger.error("Failed to recover connection state")
                        # Mark as disconnected state
                        self.user_connected = False
                        self.market_connected = False

            except TimeoutError:
                logger.error(f"Connection recovery timeout after {recovery_timeout}s")
                # Mark as disconnected state
                self.user_connected = False
                self.market_connected = False

        except Exception as e:
            logger.error(f"Error during connection state recovery: {e}")
            # Ensure we're in a clean disconnected state
            self.user_connected = False
            self.market_connected = False
            self.user_hub_ready.clear()
            self.market_hub_ready.clear()

    def is_connected(self: "ProjectXRealtimeClientProtocol") -> bool:
        """
        Check if both hubs are connected.

        Returns:
            bool: True only if both user and market hubs are connected

        Example:
            >>> if client.is_connected():
            ...     print("Fully connected")
            ... elif client.user_connected:
            ...     print("Only user hub connected")
            ... elif client.market_connected:
            ...     print("Only market hub connected")
            ... else:
            ...     print("Not connected")

        Note:
            Both hubs must be connected for full functionality.
            Check individual flags for partial connection status.
        """
        return self.user_connected and self.market_connected

    def get_stats(self: "ProjectXRealtimeClientProtocol") -> dict[str, Any]:
        """
        Get connection statistics.

        Provides comprehensive statistics about connection health, event flow,
        and subscription status.

        Returns:
            dict[str, Any]: Statistics dictionary containing:
                - events_received (int): Total events processed
                - connection_errors (int): Total connection errors
                - last_event_time (datetime): Most recent event timestamp
                - connected_time (datetime): When connection established
                - user_connected (bool): User hub connection status
                - market_connected (bool): Market hub connection status
                - subscribed_contracts (int): Number of market subscriptions

        Example:
            >>> stats = client.get_stats()
            >>> print(f"Events received: {stats['events_received']}")
            >>> print(f"Uptime: {datetime.now() - stats['connected_time']}")
            >>> if stats["connection_errors"] > 10:
            ...     print("Warning: High error count")
            >>> # Monitor event flow
            >>> last_event = stats["last_event_time"]
            >>> if last_event and (datetime.now() - last_event).seconds > 60:
            ...     print("Warning: No events for 60 seconds")

        Use Cases:
            - Connection health monitoring
            - Debugging event flow issues
            - Uptime tracking
            - Error rate monitoring
        """
        # Get task statistics from task manager (if available)
        task_stats = {}
        if hasattr(self, "get_task_stats"):
            task_stats = self.get_task_stats()
        return {
            **self.stats,
            "user_connected": self.user_connected,
            "market_connected": self.market_connected,
            "subscribed_contracts": len(self._subscribed_contracts),
            "task_stats": task_stats,
        }
