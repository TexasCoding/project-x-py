"""
Async ProjectX Realtime Client for ProjectX Gateway API

This module provides an async Python client for the ProjectX real-time API, which provides
access to the ProjectX trading platform real-time events via SignalR WebSocket connections.



Key Features:
- Full async/await support for all operations
- Asyncio-based connection management
- Non-blocking event processing
- Async callbacks for all events
"""

import asyncio
import logging
from collections import defaultdict
from collections.abc import Callable, Coroutine
from datetime import datetime
from typing import TYPE_CHECKING, Any

try:
    from signalrcore.hub_connection_builder import HubConnectionBuilder
except ImportError:
    HubConnectionBuilder = None

from .utils import RateLimiter

if TYPE_CHECKING:
    from .models import ProjectXConfig


class ProjectXRealtimeClient:
    """
    Async real-time client for ProjectX Gateway API WebSocket connections.

    This class provides an async interface for ProjectX SignalR connections and
    forwards all events to registered managers. It does NOT cache data or perform
    business logic - that's handled by the specialized managers.

    Features:
        - Async SignalR WebSocket connections to ProjectX Gateway hubs
        - Event forwarding to registered async managers
        - Automatic reconnection with exponential backoff
        - JWT token refresh and reconnection
        - Connection health monitoring
        - Async event callbacks

    Architecture:
        - Pure event forwarding (no business logic)
        - No data caching (handled by managers)
        - No payload parsing (managers handle ProjectX formats)
        - Minimal stateful operations

    Real-time Hubs (per ProjectX Gateway docs):
        - User Hub: Account, position, and order updates
        - Market Hub: Quote, trade, and market depth data

    Example:
        >>> # Create async client with ProjectX Gateway URLs
        >>> client = ProjectXRealtimeClient(jwt_token, account_id)
        >>> # Register async managers for event handling
        >>> await client.add_callback("position_update", position_manager.handle_update)
        >>> await client.add_callback("order_update", order_manager.handle_update)
        >>> await client.add_callback("quote_update", data_manager.handle_quote)
        >>>
        >>> # Connect and subscribe
        >>> if await client.connect():
        ...     await client.subscribe_user_updates()
        ...     await client.subscribe_market_data(["CON.F.US.MGC.M25"])

    Event Types (per ProjectX Gateway docs):
        User Hub: GatewayUserAccount, GatewayUserPosition, GatewayUserOrder, GatewayUserTrade
        Market Hub: GatewayQuote, GatewayDepth, GatewayTrade

    Integration:
        - AsyncPositionManager handles position events and caching
        - AsyncOrderManager handles order events and tracking
        - AsyncRealtimeDataManager handles market data and caching
        - This client only handles connections and event forwarding
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
            >>> # Using default TopStepX endpoints
            >>> client = ProjectXRealtimeClient(jwt_token, "12345")
            >>>
            >>> # Using custom config
            >>> config = ProjectXConfig(
            ...     user_hub_url="https://custom.api.com/hubs/user",
            ...     market_hub_url="https://custom.api.com/hubs/market",
            ... )
            >>> client = ProjectXRealtimeClient(jwt_token, "12345", config=config)
            >>>
            >>> # Override specific URL
            >>> client = ProjectXRealtimeClient(
            ...     jwt_token,
            ...     "12345",
            ...     market_hub_url="https://test.api.com/hubs/market",
            ... )

        Note:
            - JWT token is appended as access_token query parameter
            - Both hubs must connect successfully for full functionality
            - SignalR connections are established lazily on connect()
        """
        self.jwt_token = jwt_token
        self.account_id = account_id

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

        # Build complete URLs with authentication
        self.user_hub_url = f"{final_user_url}?access_token={jwt_token}"
        self.market_hub_url = f"{final_market_url}?access_token={jwt_token}"

        # Set up base URLs for token refresh
        if config:
            # Use config URLs if provided
            self.base_user_url = config.user_hub_url
            self.base_market_url = config.market_hub_url
        elif user_hub_url and market_hub_url:
            # Use provided URLs
            self.base_user_url = user_hub_url
            self.base_market_url = market_hub_url
        else:
            # Default to TopStepX endpoints
            self.base_user_url = "https://rtc.topstepx.com/hubs/user"
            self.base_market_url = "https://rtc.topstepx.com/hubs/market"

        # SignalR connection objects
        self.user_connection = None
        self.market_connection = None

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

        self.rate_limiter = RateLimiter(requests_per_minute=60)

        # Async locks for thread-safe operations
        self._callback_lock = asyncio.Lock()
        self._connection_lock = asyncio.Lock()

        # Store the event loop for cross-thread task scheduling
        self._loop = None

    async def setup_connections(self):
        """
        Set up SignalR hub connections with ProjectX Gateway configuration.

        Initializes both user and market hub connections with proper event handlers,
        automatic reconnection, and ProjectX-specific event mappings. Must be called
        before connect() or is called automatically on first connect().

        Hub Configuration:
            - User Hub: Account, position, order, and trade events
            - Market Hub: Quote, trade, and market depth events
            - Both hubs: Automatic reconnection with exponential backoff
            - Keep-alive: 10 second interval
            - Reconnect intervals: [1, 3, 5, 5, 5, 5] seconds

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
            ImportError: If signalrcore package is not installed
            Exception: If connection setup fails

        Note:
            This method is idempotent - safe to call multiple times.
            Sets self.setup_complete = True when successful.
        """
        try:
            if HubConnectionBuilder is None:
                raise ImportError("signalrcore is required for real-time functionality")

            async with self._connection_lock:
                # Build user hub connection
                self.user_connection = (
                    HubConnectionBuilder()
                    .with_url(self.user_hub_url)
                    .configure_logging(
                        logging.INFO,
                        socket_trace=False,
                        handler=logging.StreamHandler(),
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

                # Build market hub connection
                self.market_connection = (
                    HubConnectionBuilder()
                    .with_url(self.market_hub_url)
                    .configure_logging(
                        logging.INFO,
                        socket_trace=False,
                        handler=logging.StreamHandler(),
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

                # Market Hub Events
                self.market_connection.on("GatewayQuote", self._forward_quote_update)
                self.market_connection.on("GatewayTrade", self._forward_market_trade)
                self.market_connection.on("GatewayDepth", self._forward_market_depth)

                self.logger.info("✅ ProjectX Gateway connections configured")
                self.setup_complete = True

        except Exception as e:
            self.logger.error(f"❌ Failed to setup ProjectX connections: {e}")
            raise

    async def connect(self) -> bool:
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
            >>> client = ProjectXRealtimeClient(jwt_token, account_id)
            >>> if await client.connect():
            ...     print("Connected to ProjectX Gateway")
            ...     # Subscribe to updates
            ...     await client.subscribe_user_updates()
            ...     await client.subscribe_market_data(["MGC", "NQ"])
            ... else:
            ...     print("Connection failed")

        Side Effects:
            - Sets self.user_connected and self.market_connected flags
            - Updates connection statistics
            - Stores event loop reference

        Note:
            - Both hubs must connect for success
            - SignalR connections run in thread executor for async compatibility
            - Automatic reconnection is configured but initial connect may fail
        """
        if not self.setup_complete:
            await self.setup_connections()

        # Store the event loop for cross-thread task scheduling
        self._loop = asyncio.get_event_loop()

        self.logger.info("🔌 Connecting to ProjectX Gateway...")

        try:
            async with self._connection_lock:
                # Start both connections
                if self.user_connection:
                    await self._start_connection_async(self.user_connection, "user")
                else:
                    self.logger.error("❌ User connection not available")
                    return False

                if self.market_connection:
                    await self._start_connection_async(self.market_connection, "market")
                else:
                    self.logger.error("❌ Market connection not available")
                    return False

                # Wait for connections to establish
                await asyncio.sleep(0.5)

                if self.user_connected and self.market_connected:
                    self.stats["connected_time"] = datetime.now()
                    self.logger.info("✅ ProjectX Gateway connections established")
                    return True
                else:
                    self.logger.error("❌ Failed to establish all connections")
                    return False

        except Exception as e:
            self.logger.error(f"❌ Connection error: {e}")
            self.stats["connection_errors"] += 1
            return False

    async def _start_connection_async(self, connection, name: str):
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
        # SignalR connections are synchronous, so we run them in executor
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, connection.start)
        self.logger.info(f"✅ {name.capitalize()} hub connection started")

    async def disconnect(self):
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
        self.logger.info("📴 Disconnecting from ProjectX Gateway...")

        async with self._connection_lock:
            if self.user_connection:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self.user_connection.stop)
                self.user_connected = False

            if self.market_connection:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self.market_connection.stop)
                self.market_connected = False

            self.logger.info("✅ Disconnected from ProjectX Gateway")

    async def subscribe_user_updates(self) -> bool:
        """
        Subscribe to all user-specific real-time updates.

        Enables real-time streaming of account-specific events including positions,
        orders, trades, and account balance changes. Must be connected to user hub.

        Subscriptions:
            - Account updates: Balance, buying power, margin changes
            - Position updates: New positions, size changes, closures
            - Order updates: New orders, fills, cancellations, modifications
            - Trade executions: Individual fills with prices and timestamps

        Returns:
            bool: True if all subscriptions successful, False otherwise

        Example:
            >>> # Basic subscription
            >>> if await client.connect():
            ...     if await client.subscribe_user_updates():
            ...         print("Subscribed to user events")
            >>> # With callbacks
            >>> async def on_position_update(data):
            ...     print(f"Position update: {data}")
            >>> await client.add_callback("position_update", on_position_update)
            >>> await client.subscribe_user_updates()
            >>> # Multiple accounts (if supported)
            >>> client1 = ProjectXRealtimeClient(jwt, "12345")
            >>> client2 = ProjectXRealtimeClient(jwt, "67890")
            >>> await client1.connect()
            >>> await client2.connect()
            >>> await client1.subscribe_user_updates()  # Account 12345 events
            >>> await client2.subscribe_user_updates()  # Account 67890 events

        ProjectX Methods Called:
            - SubscribeAccounts: General account updates
            - SubscribeOrders: Order lifecycle events
            - SubscribePositions: Position changes
            - SubscribeTrades: Trade executions

        Note:
            - Account ID is converted to int for ProjectX API
            - All subscriptions are account-specific
            - Must re-subscribe after reconnection
        """
        if not self.user_connected:
            self.logger.error("❌ User hub not connected")
            return False

        try:
            self.logger.info(f"📡 Subscribing to user updates for {self.account_id}")
            if self.user_connection is None:
                self.logger.error("❌ User connection not available")
                return False
            # ProjectX Gateway expects Subscribe method with account ID
            loop = asyncio.get_event_loop()

            # Subscribe to account updates
            await loop.run_in_executor(
                None,
                self.user_connection.send,
                "SubscribeAccounts",
                [],  # Empty list for accounts subscription
            )

            # Subscribe to order updates
            await loop.run_in_executor(
                None,
                self.user_connection.send,
                "SubscribeOrders",
                [int(self.account_id)],  # List with int account ID
            )

            # Subscribe to position updates
            await loop.run_in_executor(
                None,
                self.user_connection.send,
                "SubscribePositions",
                [int(self.account_id)],  # List with int account ID
            )

            # Subscribe to trade updates
            await loop.run_in_executor(
                None,
                self.user_connection.send,
                "SubscribeTrades",
                [int(self.account_id)],  # List with int account ID
            )

            self.logger.info("✅ Subscribed to user updates")
            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to subscribe to user updates: {e}")
            return False

    async def subscribe_market_data(self, contract_ids: list[str]) -> bool:
        """
        Subscribe to market data for specific contracts.

        Enables real-time streaming of quotes, trades, and market depth for specified
        contracts. Each contract receives all three data types automatically.

        Args:
            contract_ids (list[str]): List of ProjectX contract IDs to subscribe.
                Can be symbol names or full contract IDs.
                Examples: ["MGC", "NQ"] or ["CON.F.US.MGC.M25", "CON.F.US.NQ.M25"]

        Returns:
            bool: True if all subscriptions successful, False otherwise

        Data Types Subscribed:
            - Quotes: Bid/ask prices, sizes, and timestamps
            - Trades: Executed trades with price, size, and aggressor
            - Market Depth: Full order book with multiple price levels

        Example:
            >>> # Subscribe to single contract
            >>> await client.subscribe_market_data(["MGC"])
            >>>
            >>> # Subscribe to multiple contracts
            >>> contracts = ["MGC", "NQ", "ES", "YM"]
            >>> if await client.subscribe_market_data(contracts):
            ...     print(f"Subscribed to {len(contracts)} contracts")
            >>> # With data handling
            >>> async def on_quote(data):
            ...     contract = data["contract_id"]
            ...     quote = data["data"]
            ...     print(f"{contract}: {quote['bid']} x {quote['ask']}")
            >>> await client.add_callback("quote_update", on_quote)
            >>> await client.subscribe_market_data(["MGC"])
            >>> # Add contracts dynamically
            >>> await client.subscribe_market_data(["ES"])  # Adds to existing

        ProjectX Methods Called:
            - SubscribeContractQuotes: Real-time bid/ask
            - SubscribeContractTrades: Executed trades
            - SubscribeContractMarketDepth: Order book

        Side Effects:
            - Adds contracts to self._subscribed_contracts for reconnection
            - Triggers immediate data flow for liquid contracts

        Note:
            - Subscriptions are additive - doesn't unsubscribe existing
            - Duplicate subscriptions are filtered automatically
            - Contract IDs are case-sensitive
        """
        if not self.market_connected:
            self.logger.error("❌ Market hub not connected")
            return False

        try:
            self.logger.info(
                f"📊 Subscribing to market data for {len(contract_ids)} contracts"
            )

            # Store for reconnection (avoid duplicates)
            for contract_id in contract_ids:
                if contract_id not in self._subscribed_contracts:
                    self._subscribed_contracts.append(contract_id)

            # Subscribe using ProjectX Gateway methods (same as sync client)
            loop = asyncio.get_event_loop()
            for contract_id in contract_ids:
                # Subscribe to quotes
                if self.market_connection is None:
                    self.logger.error("❌ Market connection not available")
                    return False
                await loop.run_in_executor(
                    None,
                    self.market_connection.send,
                    "SubscribeContractQuotes",
                    [contract_id],
                )
                # Subscribe to trades
                await loop.run_in_executor(
                    None,
                    self.market_connection.send,
                    "SubscribeContractTrades",
                    [contract_id],
                )
                # Subscribe to market depth
                await loop.run_in_executor(
                    None,
                    self.market_connection.send,
                    "SubscribeContractMarketDepth",
                    [contract_id],
                )

            self.logger.info(f"✅ Subscribed to {len(contract_ids)} contracts")
            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to subscribe to market data: {e}")
            return False

    async def unsubscribe_user_updates(self) -> bool:
        """
        Unsubscribe from all user-specific real-time updates.

        Stops real-time streaming of account-specific events. Useful for reducing
        bandwidth or switching accounts. Callbacks remain registered.

        Returns:
            bool: True if unsubscription successful, False otherwise

        Example:
            >>> # Temporary pause
            >>> await client.unsubscribe_user_updates()
            >>> # ... do something else ...
            >>> await client.subscribe_user_updates()  # Re-enable
            >>>
            >>> # Clean shutdown
            >>> await client.unsubscribe_user_updates()
            >>> await client.disconnect()

        Note:
            - Does not remove registered callbacks
            - Can re-subscribe without re-registering callbacks
            - Stops events for: accounts, positions, orders, trades
        """
        if not self.user_connected:
            self.logger.error("❌ User hub not connected")
            return False

        if self.user_connection is None:
            self.logger.error("❌ User connection not available")
            return False

        try:
            loop = asyncio.get_event_loop()

            # Unsubscribe from account updates
            await loop.run_in_executor(
                None,
                self.user_connection.send,
                "UnsubscribeAccounts",
                self.account_id,
            )

            # Unsubscribe from order updates

            await loop.run_in_executor(
                None,
                self.user_connection.send,
                "UnsubscribeOrders",
                [self.account_id],
            )

            # Unsubscribe from position updates

            await loop.run_in_executor(
                None,
                self.user_connection.send,
                "UnsubscribePositions",
                self.account_id,
            )

            # Unsubscribe from trade updates

            await loop.run_in_executor(
                None,
                self.user_connection.send,
                "UnsubscribeTrades",
                self.account_id,
            )

            self.logger.info("✅ Unsubscribed from user updates")
            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to unsubscribe from user updates: {e}")
            return False

    async def unsubscribe_market_data(self, contract_ids: list[str]) -> bool:
        """
        Unsubscribe from market data for specific contracts.

        Stops real-time streaming for specified contracts. Other subscribed
        contracts continue to stream. Useful for dynamic subscription management.

        Args:
            contract_ids (list[str]): List of contract IDs to unsubscribe.
                Should match the IDs used in subscribe_market_data().

        Returns:
            bool: True if unsubscription successful, False otherwise

        Example:
            >>> # Unsubscribe specific contracts
            >>> await client.unsubscribe_market_data(["MGC", "SI"])
            >>>
            >>> # Dynamic subscription management
            >>> active_contracts = ["ES", "NQ", "YM", "RTY"]
            >>> await client.subscribe_market_data(active_contracts)
            >>> # Later, reduce to just ES and NQ
            >>> await client.unsubscribe_market_data(["YM", "RTY"])
            >>>
            >>> # Unsubscribe all tracked contracts
            >>> all_contracts = client._subscribed_contracts.copy()
            >>> await client.unsubscribe_market_data(all_contracts)

        Side Effects:
            - Removes contracts from self._subscribed_contracts
            - Stops quotes, trades, and depth for specified contracts

        Note:
            - Only affects specified contracts
            - Callbacks remain registered for future subscriptions
            - Safe to call with non-subscribed contracts
        """
        if not self.market_connected:
            self.logger.error("❌ Market hub not connected")
            return False

        try:
            self.logger.info(f"🛑 Unsubscribing from {len(contract_ids)} contracts")

            # Remove from stored contracts
            for contract_id in contract_ids:
                if contract_id in self._subscribed_contracts:
                    self._subscribed_contracts.remove(contract_id)

            # ProjectX Gateway expects Unsubscribe method
            loop = asyncio.get_event_loop()
            if self.market_connection is None:
                self.logger.error("❌ Market connection not available")
                return False

            # Unsubscribe from quotes
            await loop.run_in_executor(
                None,
                self.market_connection.send,
                "UnsubscribeContractQuotes",
                [contract_ids],
            )

            # Unsubscribe from trades
            await loop.run_in_executor(
                None,
                self.market_connection.send,
                "UnsubscribeContractTrades",
                [contract_ids],
            )

            # Unsubscribe from market depth
            await loop.run_in_executor(
                None,
                self.market_connection.send,
                "UnsubscribeContractMarketDepth",
                [contract_ids],
            )

            self.logger.info(f"✅ Unsubscribed from {len(contract_ids)} contracts")
            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to unsubscribe from market data: {e}")
            return False

    async def add_callback(
        self,
        event_type: str,
        callback: Callable[[dict[str, Any]], Coroutine[Any, Any, None] | None],
    ):
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
    ):
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

    async def _trigger_callbacks(self, event_type: str, data: dict[str, Any]):
        """
        Trigger all callbacks for a specific event type asynchronously.

        Executes all registered callbacks for an event type in order. Handles both
        async and sync callbacks. Exceptions are caught to prevent one callback
        from affecting others.

        Args:
            event_type (str): Event type to trigger callbacks for
            data (dict[str, Any]): Event data to pass to callbacks

        Callback Execution:
            - Async callbacks: Awaited directly
            - Sync callbacks: Called directly
            - Exceptions: Logged but don't stop other callbacks
            - Order: Same as registration order

        Note:
            This is an internal method called by event forwarding methods.
        """
        callbacks = self.callbacks.get(event_type, [])
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    # Handle sync callbacks
                    callback(data)
            except Exception as e:
                self.logger.error(f"Error in {event_type} callback: {e}")

    # Connection event handlers
    def _on_user_hub_open(self):
        """
        Handle user hub connection open.

        Called by SignalR when user hub connection is established.
        Sets connection flag and logs success.

        Side Effects:
            - Sets self.user_connected = True
            - Logs connection success
        """
        self.user_connected = True
        self.logger.info("✅ User hub connected")

    def _on_user_hub_close(self):
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
        self.logger.warning("❌ User hub disconnected")

    def _on_market_hub_open(self):
        """
        Handle market hub connection open.

        Called by SignalR when market hub connection is established.
        Sets connection flag and logs success.

        Side Effects:
            - Sets self.market_connected = True
            - Logs connection success
        """
        self.market_connected = True
        self.logger.info("✅ Market hub connected")

    def _on_market_hub_close(self):
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
        self.logger.warning("❌ Market hub disconnected")

    def _on_connection_error(self, hub: str, error):
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
            self.logger.debug(f"SignalR completion message from {hub} hub: {error}")
            return

        # Log actual errors
        self.logger.error(f"❌ {hub.capitalize()} hub error: {error}")
        self.stats["connection_errors"] += 1

    # Event forwarding methods (cross-thread safe)
    def _forward_account_update(self, *args):
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

    def _forward_position_update(self, *args):
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

    def _forward_order_update(self, *args):
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

    def _forward_trade_execution(self, *args):
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

    def _forward_quote_update(self, *args):
        """
        Forward quote update to registered callbacks.

        Receives GatewayQuote events from SignalR and schedules async
        processing. Real-time bid/ask updates.

        Args:
            *args: Variable arguments from SignalR containing quote data

        Event Data Format:
            Callbacks receive: {"contract_id": str, "data": quote_dict}
        """
        self._schedule_async_task("quote_update", args)

    def _forward_market_trade(self, *args):
        """
        Forward market trade to registered callbacks.

        Receives GatewayTrade events from SignalR and schedules async
        processing. Public trade tape data.

        Args:
            *args: Variable arguments from SignalR containing trade data

        Event Data Format:
            Callbacks receive: {"contract_id": str, "data": trade_dict}
        """
        self._schedule_async_task("market_trade", args)

    def _forward_market_depth(self, *args):
        """
        Forward market depth to registered callbacks.

        Receives GatewayDepth events from SignalR and schedules async
        processing. Full order book updates.

        Args:
            *args: Variable arguments from SignalR containing depth data

        Event Data Format:
            Callbacks receive: {"contract_id": str, "data": depth_dict}
        """
        self._schedule_async_task("market_depth", args)

    def _schedule_async_task(self, event_type: str, data):
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
                print(f"Error scheduling async task: {e}")
        else:
            # Fallback - try to create task in current loop context
            try:
                task = asyncio.create_task(self._forward_event_async(event_type, data))
                # Fire and forget - we don't need to await the task
                task.add_done_callback(lambda t: None)
            except RuntimeError:
                # No event loop available, log and continue
                print(f"No event loop available for {event_type} event")

    async def _forward_event_async(self, event_type: str, args):
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
            - Increments event counter
            - Updates last event timestamp
            - Triggers all registered callbacks

        Example Data Flow:
            >>> # SignalR sends: ["MGC", {"bid": 2050, "ask": 2051}]
            >>> # Callbacks receive: {"contract_id": "MGC", "data": {"bid": 2050, "ask": 2051}}

        Note:
            This method runs in the asyncio event loop, ensuring thread safety
            for callback execution.
        """
        self.stats["events_received"] += 1
        self.stats["last_event_time"] = datetime.now()

        # Log event (debug level)
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

    def is_connected(self) -> bool:
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

    def get_stats(self) -> dict[str, Any]:
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
        return {
            **self.stats,
            "user_connected": self.user_connected,
            "market_connected": self.market_connected,
            "subscribed_contracts": len(self._subscribed_contracts),
        }

    async def update_jwt_token(self, new_jwt_token: str) -> bool:
        """
        Update JWT token and reconnect with new credentials.

        Handles JWT token refresh for expired or updated tokens. Disconnects current
        connections, updates URLs with new token, and re-establishes all subscriptions.

        Args:
            new_jwt_token (str): New JWT authentication token from AsyncProjectX

        Returns:
            bool: True if reconnection successful with new token

        Process:
            1. Disconnect existing connections
            2. Update token and connection URLs
            3. Reset connection state
            4. Reconnect to both hubs
            5. Re-subscribe to user updates
            6. Re-subscribe to previous market data

        Example:
            >>> # Token refresh on expiry
            >>> async def refresh_connection():
            ...     # Get new token
            ...     await project_x.authenticate()
            ...     new_token = project_x.session_token
            ...     # Update real-time client
            ...     if await realtime_client.update_jwt_token(new_token):
            ...         print("Reconnected with new token")
            ...     else:
            ...         print("Reconnection failed")
            >>> # Scheduled token refresh
            >>> async def token_refresh_loop():
            ...     while True:
            ...         await asyncio.sleep(3600)  # Every hour
            ...         await refresh_connection()

        Side Effects:
            - Disconnects and reconnects both hubs
            - Re-subscribes to all previous subscriptions
            - Updates internal token and URLs

        Note:
            - Callbacks are preserved during reconnection
            - Market data subscriptions are restored automatically
            - Brief data gap during reconnection process
        """
        self.logger.info("🔑 Updating JWT token and reconnecting...")

        # Disconnect existing connections
        await self.disconnect()

        # Update token
        self.jwt_token = new_jwt_token

        # Update URLs with new token
        self.user_hub_url = f"{self.base_user_url}?access_token={new_jwt_token}"
        self.market_hub_url = f"{self.base_market_url}?access_token={new_jwt_token}"

        # Reset setup flag to force new connection setup
        self.setup_complete = False

        # Reconnect
        if await self.connect():
            # Re-subscribe to user updates
            await self.subscribe_user_updates()

            # Re-subscribe to market data
            if self._subscribed_contracts:
                await self.subscribe_market_data(self._subscribed_contracts)

            self.logger.info("✅ Reconnected with new JWT token")
            return True
        else:
            self.logger.error("❌ Failed to reconnect with new JWT token")
            return False

    async def cleanup(self):
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
        async with self._callback_lock:
            self.callbacks.clear()
        self.logger.info("✅ AsyncProjectXRealtimeClient cleanup completed")
