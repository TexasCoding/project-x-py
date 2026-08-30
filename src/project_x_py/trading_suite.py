"""
Unified TradingSuite class for simplified SDK initialization and management.

Author: @TexasCoding
Date: 2025-08-04

Overview:
    Provides a single, intuitive entry point for creating a complete trading
    environment with all components properly configured and connected. This
    replaces the complex factory functions with a clean, simple API.

Key Features:
    - Single-line initialization with sensible defaults
    - Automatic component wiring and dependency injection
    - Built-in connection management and error recovery
    - Feature flags for optional components
    - Configuration file and environment variable support

Example Usage:
    ```python
    # Simple one-liner with defaults
    suite = await TradingSuite.create("MNQ")

    # With specific configuration
    suite = await TradingSuite.create(
        "MNQ",
        timeframes=["1min", "5min", "15min"],
        features=["orderbook", "risk_manager"],
    )

    # From configuration file
    suite = await TradingSuite.from_config("config/trading.yaml")
    ```
"""

import asyncio
from collections.abc import Iterator
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from types import TracebackType
from typing import Any, cast

import orjson
import yaml

from project_x_py.client import ProjectX
from project_x_py.client.base import ProjectXBase
from project_x_py.event_bus import EventBus, EventType
from project_x_py.models import Instrument
from project_x_py.order_manager import OrderManager
from project_x_py.order_tracker import OrderChainBuilder, OrderTracker
from project_x_py.orderbook import OrderBook
from project_x_py.position_manager import PositionManager
from project_x_py.realtime import ProjectXRealtimeClient
from project_x_py.realtime_data_manager import RealtimeDataManager
from project_x_py.risk_manager import ManagedTrade, RiskConfig, RiskManager
from project_x_py.sessions import SessionConfig, SessionType
from project_x_py.statistics import StatisticsAggregator
from project_x_py.types.config_types import (
    DataManagerConfig,
    OrderbookConfig,
    OrderManagerConfig,
    PositionManagerConfig,
)
from project_x_py.types.protocols import ProjectXClientProtocol
from project_x_py.types.stats_types import TradingSuiteStats
from project_x_py.utils import ProjectXLogger

logger = ProjectXLogger.get_logger(__name__)


@dataclass(frozen=True)
class InstrumentContext:
    """
    Encapsulates all managers and data for a single financial instrument.

    This class holds all the components needed to trade and analyze a single
    instrument, providing a clean interface for multi-instrument trading.

    Attributes:
        symbol: The instrument symbol (e.g., "MNQ", "ES")
        instrument_info: The Instrument object with contract details
        data: Real-time data manager for OHLCV data
        orders: Order management system
        positions: Position tracking system
        event_bus: Event bus for this instrument's events
        orderbook: Level 2 market depth (optional)
        risk_manager: Risk management system (optional)
    """

    symbol: str
    instrument_info: Instrument
    data: RealtimeDataManager
    orders: OrderManager
    positions: PositionManager
    event_bus: EventBus
    orderbook: OrderBook | None = None
    risk_manager: RiskManager | None = None

    async def on(self, event: EventType | str, handler: Any) -> None:
        """
        Register event handler on this instrument's event bus.

        Args:
            event: Event type to listen for
            handler: Async callable to handle events
        """
        await self.event_bus.on(event, handler)

    async def once(self, event: EventType | str, handler: Any) -> None:
        """
        Register one-time event handler on this instrument's event bus.

        Args:
            event: Event type to listen for
            handler: Async callable to handle event once
        """
        await self.event_bus.once(event, handler)

    async def off(
        self, event: EventType | str | None = None, handler: Any | None = None
    ) -> None:
        """
        Remove event handler(s) from this instrument's event bus.

        Args:
            event: Event type to remove handler from (None for all)
            handler: Specific handler to remove (None for all)
        """
        await self.event_bus.off(event, handler)

    async def wait_for(
        self, event: EventType | str, timeout: float | None = None
    ) -> Any:
        """
        Wait for specific event to occur on this instrument's event bus.

        Args:
            event: Event type to wait for
            timeout: Optional timeout in seconds

        Returns:
            Event object when received

        Raises:
            TimeoutError: If timeout expires
        """
        return await self.event_bus.wait_for(event, timeout)


class Features(str, Enum):
    """Available feature flags for TradingSuite.

    Working flags: ``ORDERBOOK``, ``RISK_MANAGER``.

    ``TRADE_JOURNAL`` and ``AUTO_RECONNECT`` are kept for compatibility; they
    warn and have no effect. Realtime reconnect is independent of
    ``AUTO_RECONNECT``. ``PERFORMANCE_ANALYTICS`` currently only sets unused
    config flags (``enable_correlation_analysis``, ``enable_analytics``).
    """

    ORDERBOOK = "orderbook"
    RISK_MANAGER = "risk_manager"
    TRADE_JOURNAL = "trade_journal"  # Reserved; warns and has no effect
    PERFORMANCE_ANALYTICS = "performance_analytics"  # Sets unused config flags
    AUTO_RECONNECT = "auto_reconnect"  # Reserved; warns and has no effect


class TradingSuiteConfig:
    """Configuration for TradingSuite initialization."""

    def __init__(
        self,
        instrument: str,
        timeframes: list[str] | None = None,
        features: list[Features] | None = None,
        initial_days: int = 5,
        auto_connect: bool = True,
        timezone: str = "America/Chicago",
        order_manager_config: OrderManagerConfig | None = None,
        position_manager_config: PositionManagerConfig | None = None,
        data_manager_config: DataManagerConfig | None = None,
        orderbook_config: OrderbookConfig | None = None,
        risk_config: RiskConfig | None = None,
        session_config: SessionConfig | None = None,
    ):
        self.instrument = instrument
        self.timeframes = timeframes or ["5min"]
        self.features = features or []
        self.initial_days = initial_days
        self.auto_connect = auto_connect
        self.timezone = timezone
        self.order_manager_config = order_manager_config
        self.position_manager_config = position_manager_config
        self.data_manager_config = data_manager_config
        self.orderbook_config = orderbook_config
        self.risk_config = risk_config
        self.session_config = session_config

    def get_order_manager_config(self) -> OrderManagerConfig:
        """
        Get configuration for OrderManager.

        Returns:
            OrderManagerConfig: The configuration for the OrderManager.
        """
        if self.order_manager_config:
            return self.order_manager_config
        return {
            "enable_bracket_orders": Features.RISK_MANAGER in self.features,
            "enable_trailing_stops": True,
            "auto_risk_management": Features.RISK_MANAGER in self.features,
            "enable_order_validation": True,
        }

    def get_position_manager_config(self) -> PositionManagerConfig:
        """
        Get configuration for PositionManager.

        Returns:
            PositionManagerConfig: The configuration for the PositionManager.
        """
        if self.position_manager_config:
            return self.position_manager_config
        return {
            "enable_risk_monitoring": Features.RISK_MANAGER in self.features,
            "enable_correlation_analysis": Features.PERFORMANCE_ANALYTICS
            in self.features,
            "enable_portfolio_rebalancing": False,
        }

    def get_data_manager_config(self) -> DataManagerConfig:
        """
        Get configuration for RealtimeDataManager.

        Returns:
            DataManagerConfig: The configuration for the RealtimeDataManager.
        """
        if self.data_manager_config:
            return self.data_manager_config
        return {
            "max_bars_per_timeframe": 1000,
            "enable_tick_data": True,
            "enable_level2_data": Features.ORDERBOOK in self.features,
            "data_validation": True,
            "auto_cleanup": True,
            "enable_dynamic_limits": True,  # Enable dynamic resource limits by default
            "resource_config": {
                "memory_target_percent": 15.0,  # Use 15% of available memory
                "memory_pressure_threshold": 0.8,  # Scale down at 80% memory usage
                "cpu_pressure_threshold": 0.8,  # Scale down at 80% CPU usage
                "monitoring_interval": 30.0,  # Monitor every 30 seconds
            },
        }

    def get_orderbook_config(self) -> OrderbookConfig:
        """
        Get configuration for OrderBook.

        Returns:
            OrderbookConfig: The configuration for the OrderBook.
        """
        if self.orderbook_config:
            return self.orderbook_config
        return {
            "max_depth_levels": 100,
            "max_trade_history": 1000,
            "enable_analytics": Features.PERFORMANCE_ANALYTICS in self.features,
            "enable_pattern_detection": True,
        }

    def get_risk_config(self) -> RiskConfig:
        """
        Get configuration for RiskManager.

        Returns:
            RiskConfig: The configuration for the RiskManager.
        """
        if self.risk_config:
            return self.risk_config
        return RiskConfig(
            max_risk_per_trade=Decimal("0.01"),  # 1% per trade
            max_daily_loss=Decimal("0.03"),  # 3% daily loss
            max_positions=3,
            use_stop_loss=True,
            use_take_profit=True,
            use_trailing_stops=True,
            default_risk_reward_ratio=Decimal("2.0"),
        )


class TradingSuite:
    """
    Unified trading suite providing simplified access to all SDK components.

    This class replaces the complex factory functions with a clean, intuitive
    API that handles all initialization, connection, and dependency management
    automatically.

    Attributes:
        instrument: Trading instrument symbol
        data: Real-time data manager for OHLCV data
        orders: Order management system
        positions: Position tracking system
        orderbook: Level 2 market depth (if enabled)
        risk_manager: Risk management system (if enabled)
        client: Underlying ProjectX API client
        realtime: WebSocket connection manager
        config: Suite configuration
        events: Unified event bus for all components
    """

    def __init__(
        self,
        client: ProjectXBase,
        realtime_client: ProjectXRealtimeClient,
        config: TradingSuiteConfig,
        instrument_contexts: dict[str, InstrumentContext] | None = None,
    ):
        """
        Initialize TradingSuite with core components.

        Note: Use the factory methods (create, from_config, from_env) instead
        of instantiating directly.

        Args:
            client: ProjectX API client
            realtime_client: WebSocket realtime client
            config: Suite configuration
            instrument_contexts: Pre-built instrument contexts (for multi-instrument)
        """
        self.client = client
        self.realtime = realtime_client
        self.config = config

        # Multi-instrument support
        self._instruments: dict[str, InstrumentContext] = instrument_contexts or {}
        self._is_single_instrument = len(self._instruments) == 1

        # For backward compatibility - store single context if available
        self._single_context: InstrumentContext | None = (
            next(iter(self._instruments.values()))
            if self._is_single_instrument and self._instruments
            else None
        )

        # Legacy single-instrument properties (for backward compatibility)
        self._symbol = config.instrument  # Store original symbol
        self.instrument: Instrument | None = None  # Will be set during initialization

        # Initialize unified event bus
        self.events = EventBus()

        # Initialize statistics aggregator
        self._stats_aggregator = StatisticsAggregator(
            cache_ttl=5.0,
            component_timeout=1.0,
        )
        self._stats_aggregator.trading_suite = self
        self._stats_aggregator.client = client
        self._stats_aggregator.realtime_client = realtime_client

        # For backward compatibility, create single-instrument components if no contexts provided
        if not instrument_contexts:
            # Initialize core components with typed configs and event bus
            self._data = RealtimeDataManager(
                instrument=config.instrument,
                project_x=client,
                realtime_client=realtime_client,
                timeframes=config.timeframes,
                timezone=config.timezone,
                config=config.get_data_manager_config(),
                event_bus=self.events,
                session_config=config.session_config,  # Pass session configuration
            )

            self._orders = OrderManager(
                client, config=config.get_order_manager_config(), event_bus=self.events
            )

            # Set aggregator references
            self._stats_aggregator.order_manager = self._orders
            self._stats_aggregator.data_manager = self._data

            # Optional components
            self._orderbook: OrderBook | None = None
            self._risk_manager: RiskManager | None = None

            # Create PositionManager first
            self._positions = PositionManager(
                client,
                event_bus=self.events,
                risk_manager=None,  # Will be set later
                data_manager=self._data,
                config=config.get_position_manager_config(),
            )

            # Set aggregator reference
            self._stats_aggregator.position_manager = self._positions

            # Initialize risk manager if enabled and inject dependencies
            if Features.RISK_MANAGER in config.features:
                self._risk_manager = RiskManager(
                    project_x=cast(ProjectXClientProtocol, client),
                    order_manager=self._orders,
                    event_bus=self.events,
                    position_manager=self._positions,
                    config=config.get_risk_config(),
                )
                self._orders.risk_manager = self._risk_manager
                self._positions.risk_manager = self._risk_manager
                self._stats_aggregator.risk_manager = self._risk_manager
        else:
            # Multi-instrument mode - don't set direct attributes, use __getattr__ for backward compatibility
            if self._is_single_instrument and self._single_context:
                self.instrument = self._single_context.instrument_info

                # Set aggregator references
                self._stats_aggregator.order_manager = self._single_context.orders
                self._stats_aggregator.data_manager = self._single_context.data
                self._stats_aggregator.position_manager = self._single_context.positions
                if self._single_context.risk_manager:
                    self._stats_aggregator.risk_manager = (
                        self._single_context.risk_manager
                    )
                if self._single_context.orderbook:
                    self._stats_aggregator.orderbook = self._single_context.orderbook

        # State tracking
        self._connected = False
        self._initialized = False
        self._created_at = datetime.now()
        self._client_context: AbstractAsyncContextManager[ProjectXBase] | None = (
            None  # Will be set by create() method
        )

        instrument_list = (
            list(self._instruments.keys()) if self._instruments else [config.instrument]
        )
        logger.info(
            f"TradingSuite created for {instrument_list} "
            f"with features: {config.features}"
        )

    @classmethod
    async def create(
        cls,
        instruments: str | list[str] | None = None,
        instrument: str | None = None,  # Backward compatibility
        timeframes: list[str] | None = None,
        features: list[str] | None = None,
        session_config: SessionConfig | None = None,
        **kwargs: Any,
    ) -> "TradingSuite":
        """
        Create a fully initialized TradingSuite with sensible defaults.

        This is the primary way to create a trading environment. It handles:
        - Authentication with ProjectX
        - WebSocket connection setup
        - Component initialization
        - Historical data loading
        - Market data subscriptions

        Args:
            instruments: Trading symbol(s) - str for single, list for multiple
            instrument: (Deprecated) Single trading symbol for backward compatibility
            timeframes: Data timeframes (default: ["5min"])
            features: Optional features to enable
            session_config: Optional session configuration
            username: Optional ProjectX username. Must be used with api_key.
            api_key: Optional ProjectX API key. Must be used with username.
            account_name: Optional account name to select during authentication
            **kwargs: Additional configuration options

        Returns:
            Fully initialized and connected TradingSuite

        Example:
            ```python
            # Single instrument (backward compatible)
            suite = await TradingSuite.create("MNQ")

            # Multiple instruments
            suite = await TradingSuite.create(["MNQ", "MES", "MCL"])

            # Access specific instruments
            mnq_context = suite["MNQ"]
            current_price = await mnq_context.data.get_current_price()
            ```
        """
        # Handle backward compatibility and normalize input
        if instruments is None and instrument is not None:
            # Backward compatibility mode
            instrument_list = [instrument]
            primary_instrument = instrument
        elif instruments is not None:
            # New multi-instrument mode
            if isinstance(instruments, str):
                instrument_list = [instruments]
                primary_instrument = instruments
            else:
                instrument_list = instruments
                primary_instrument = instruments[0]  # Use first as primary for config
        else:
            raise ValueError(
                "Must provide either 'instruments' or 'instrument' parameter"
            )

        username = cast(str | None, kwargs.pop("username", None))
        api_key = cast(str | None, kwargs.pop("api_key", None))
        account_name = cast(str | None, kwargs.pop("account_name", None))

        if (username is None) != (api_key is None):
            raise ValueError(
                "Both 'username' and 'api_key' must be provided for direct "
                "TradingSuite authentication"
            )

        resolved_features = [Features(f) for f in (features or [])]
        unimplemented = [
            f.value
            for f in resolved_features
            if f in {Features.TRADE_JOURNAL, Features.AUTO_RECONNECT}
        ]
        if unimplemented:
            logger.warning(
                "Features %s are reserved and have no effect in 4.0",
                unimplemented,
            )

        # Build configuration using primary instrument
        config = TradingSuiteConfig(
            instrument=primary_instrument,
            timeframes=timeframes or ["5min"],
            features=resolved_features,
            session_config=session_config,
            **kwargs,
        )

        # Create and authenticate client
        client_context: AbstractAsyncContextManager[ProjectXBase]
        if username is not None and api_key is not None:
            client_context = ProjectX(
                username=username,
                api_key=api_key,
                account_name=account_name.upper() if account_name else None,
            )
        else:
            client_context = ProjectX.from_env(account_name=account_name)
        client = await client_context.__aenter__()

        try:
            await client.authenticate()

            if not client.account_info:
                raise ValueError("Failed to authenticate with ProjectX")

            # Create realtime client
            realtime_client = ProjectXRealtimeClient(
                jwt_token=client.session_token,
                account_id=str(client.account_info.id),
                config=client.config,
            )

            # Create instrument contexts in parallel
            instrument_contexts = await cls._create_instrument_contexts(
                instrument_list, client, realtime_client, config
            )

            # Create suite instance with contexts
            suite = cls(client, realtime_client, config, instrument_contexts)
            realtime_client.event_bus = suite.events

            # Set up event forwarding from instrument buses to suite bus
            await suite._setup_event_forwarding()

            # Store the context for cleanup later
            suite._client_context = client_context

            # Initialize if auto_connect is enabled
            if config.auto_connect:
                await suite._initialize()

            return suite

        except Exception:
            # Clean up on error
            await client_context.__aexit__(None, None, None)
            raise

    @classmethod
    async def _create_instrument_contexts(
        cls,
        instruments: list[str],
        client: ProjectXBase,
        realtime_client: ProjectXRealtimeClient,
        config: TradingSuiteConfig,
    ) -> dict[str, InstrumentContext]:
        """
        Create InstrumentContext objects for multiple instruments in parallel.

        Args:
            instruments: List of instrument symbols
            client: Authenticated ProjectX client
            realtime_client: WebSocket client
            config: Suite configuration

        Returns:
            Dictionary mapping symbol to InstrumentContext
        """

        async def _create_single_context(symbol: str) -> tuple[str, InstrumentContext]:
            """Create a single instrument context."""
            # Get instrument info
            instrument_info = await client.get_instrument(symbol)

            # Create unified event bus for this instrument
            event_bus = EventBus()

            # Create data manager
            data_manager = RealtimeDataManager(
                instrument=symbol,
                project_x=client,
                realtime_client=realtime_client,
                timeframes=config.timeframes,
                timezone=config.timezone,
                config=config.get_data_manager_config(),
                event_bus=event_bus,
                session_config=config.session_config,
            )

            # Create order manager
            order_manager = OrderManager(
                client, config=config.get_order_manager_config(), event_bus=event_bus
            )

            # Create position manager
            position_manager = PositionManager(
                client,
                event_bus=event_bus,
                risk_manager=None,  # Will be set later if needed
                data_manager=data_manager,
                config=config.get_position_manager_config(),
            )

            # Optional components
            orderbook = None
            if Features.ORDERBOOK in config.features:
                orderbook = OrderBook(
                    symbol,
                    event_bus,
                    project_x=client,
                    timezone_str=config.timezone,
                    config=config.get_orderbook_config(),
                )

            risk_manager = None
            if Features.RISK_MANAGER in config.features:
                risk_manager = RiskManager(
                    project_x=cast(ProjectXClientProtocol, client),
                    order_manager=order_manager,
                    event_bus=event_bus,
                    position_manager=position_manager,
                    config=config.get_risk_config(),
                )
                order_manager.risk_manager = risk_manager
                position_manager.risk_manager = risk_manager

            # Create context
            context = InstrumentContext(
                symbol=symbol,
                instrument_info=instrument_info,
                data=data_manager,
                orders=order_manager,
                positions=position_manager,
                event_bus=event_bus,
                orderbook=orderbook,
                risk_manager=risk_manager,
            )

            return symbol, context

        # Create all contexts in parallel with proper error handling
        # Use a shared dictionary to track contexts as they're created
        created_contexts: dict[str, InstrumentContext] = {}
        cleanup_lock = asyncio.Lock()  # Protect against concurrent cleanup

        async def _create_single_context_with_tracking(
            symbol: str,
        ) -> tuple[str, InstrumentContext]:
            """Create context and track it immediately for cleanup."""
            try:
                symbol_result, context = await _create_single_context(symbol)
                # Track context immediately for cleanup purposes
                async with cleanup_lock:
                    created_contexts[symbol_result] = context
                return symbol_result, context
            except Exception:
                # If this individual context fails, clean up all contexts created so far
                async with cleanup_lock:
                    await cls._cleanup_contexts(created_contexts.copy())
                raise

        try:
            # Create tasks with tracking
            tasks = [
                _create_single_context_with_tracking(symbol) for symbol in instruments
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Check for any exceptions in results
            final_contexts: dict[str, InstrumentContext] = {}
            for result in results:
                if isinstance(result, Exception):
                    # Some context failed, cleanup was already done in the tracking function
                    raise result

                # Type checking: result is definitely a tuple here since it's not an Exception
                symbol, context = cast(tuple[str, InstrumentContext], result)
                final_contexts[symbol] = context

            return final_contexts

        except Exception:
            # Final safety net - ensure cleanup even if something unexpected happens
            async with cleanup_lock:
                await cls._cleanup_contexts(created_contexts.copy())
            raise

    async def _setup_event_forwarding(self) -> None:
        """
        Set up event forwarding from instrument EventBuses to the suite's main EventBus.

        This ensures that events emitted to instrument-specific EventBuses are also
        forwarded to the suite-level EventBus, allowing suite-level handlers to receive
        events from all instruments.
        """
        if not self._instruments:
            return

        for context in self._instruments.values():
            await context.event_bus.forward_to(self.events)

    @classmethod
    async def _cleanup_contexts(cls, contexts: dict[str, InstrumentContext]) -> None:
        """
        Clean up partially created instrument contexts.

        Args:
            contexts: Dictionary of contexts that need cleanup
        """
        if not contexts:
            return

        cleanup_tasks = []
        for symbol, context in contexts.items():
            try:
                # Clean up each context component
                if hasattr(context.data, "cleanup"):
                    cleanup_tasks.append(context.data.cleanup())
                if hasattr(context.orders, "cleanup"):
                    cleanup_tasks.append(context.orders.cleanup())
                if hasattr(context.positions, "cleanup"):
                    cleanup_tasks.append(context.positions.cleanup())
                if context.orderbook and hasattr(context.orderbook, "cleanup"):
                    cleanup_tasks.append(context.orderbook.cleanup())
                if context.risk_manager and hasattr(context.risk_manager, "cleanup"):
                    cleanup_tasks.append(context.risk_manager.cleanup())
            except Exception as e:
                # Log cleanup error but don't fail the overall cleanup
                logger.warning(f"Error cleaning up context for {symbol}: {e}")

        # Run all cleanup tasks in parallel
        if cleanup_tasks:
            try:
                await asyncio.gather(*cleanup_tasks, return_exceptions=True)
            except Exception as e:
                logger.warning(f"Error during parallel context cleanup: {e}")

    @classmethod
    async def from_config(cls, config_path: str) -> "TradingSuite":
        """
        Create TradingSuite from a configuration file.

        Supports both YAML and JSON configuration files.

        Args:
            config_path: Path to configuration file

        Returns:
            Configured TradingSuite instance

        Example:
            ```yaml
            # config/trading.yaml
            instrument: MNQ
            timeframes:
              - 1min
              - 5min
              - 15min
            features:
              - orderbook
              - risk_manager
            initial_days: 30
            ```

            ```python
            # Note: Create the config file first with the above content
            suite = await TradingSuite.from_config("config/trading.yaml")
            ```
        """
        path = Path(config_path)

        # Check file extension first
        if path.suffix not in [".yaml", ".yml", ".json"]:
            raise ValueError(f"Unsupported config format: {path.suffix}")

        # Then check if file exists
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        # Load configuration
        if path.suffix in [".yaml", ".yml"]:
            with open(path) as f:
                data = yaml.safe_load(f)
        elif path.suffix == ".json":
            with open(path, "rb") as f:
                data = orjson.loads(f.read())
        else:
            # This should never happen due to earlier check, but keep for safety
            raise ValueError(f"Unsupported config format: {path.suffix}")

        # Create suite with loaded configuration
        return await cls.create(**data)

    @classmethod
    async def from_env(cls, instrument: str, **kwargs: Any) -> "TradingSuite":
        """
        Create TradingSuite using environment variables for configuration.

        This method automatically loads ProjectX credentials from environment
        variables and applies any additional configuration from kwargs.

        Required environment variables:
        - PROJECT_X_API_KEY
        - PROJECT_X_USERNAME

        Args:
            instrument: Trading instrument symbol
            **kwargs: Additional configuration options

        Returns:
            Configured TradingSuite instance

        Example:
            ```python
            # Uses PROJECT_X_API_KEY and PROJECT_X_USERNAME from environment
            suite = await TradingSuite.from_env("MNQ", timeframes=["1min", "5min"])
            ```
        """
        # Environment variables are automatically used by ProjectX.from_env()
        return await cls.create(instrument, **kwargs)

    async def _initialize(self) -> None:
        """Initialize all components and establish connections."""
        if self._initialized:
            return

        try:
            # Connect to realtime feeds
            logger.info("Connecting to real-time feeds...")
            connected = await self.realtime.connect()
            if not connected:
                from project_x_py.exceptions import ProjectXConnectionError

                raise ProjectXConnectionError(
                    "Failed to establish ProjectX realtime connections"
                )
            await self.realtime.subscribe_user_updates()

            if self._instruments:
                # Multi-instrument mode - initialize all contexts
                await self._initialize_instrument_contexts()
            else:
                # Legacy single-instrument mode (for backward compatibility)
                await self._initialize_legacy_single_instrument()

            self._connected = True
            self._initialized = True
            logger.info("TradingSuite initialization complete")

        except Exception as e:
            logger.error(f"Failed to initialize TradingSuite: {e}")
            await self.disconnect()
            raise

    async def _initialize_instrument_contexts(self) -> None:
        """Initialize all instrument contexts in parallel."""

        async def _initialize_single_context(context: InstrumentContext) -> None:
            """Initialize a single instrument context."""
            # Initialize order manager with realtime client for order tracking
            await context.orders.initialize(realtime_client=self.realtime)

            # Initialize position manager with order manager for cleanup
            await context.positions.initialize(
                realtime_client=self.realtime,
                order_manager=context.orders,
            )

            # Load historical data
            await context.data.initialize(initial_days=self.config.initial_days)

            # Subscribe to market data
            await self.realtime.subscribe_market_data([context.instrument_info.id])

            # Start realtime data feed
            await context.data.start_realtime_feed()

            # Initialize optional components
            if context.orderbook:
                await context.orderbook.initialize(
                    realtime_client=self.realtime,
                    subscribe_to_depth=True,
                    subscribe_to_quotes=True,
                )

        # Initialize all contexts in parallel
        tasks = [
            _initialize_single_context(context)
            for context in self._instruments.values()
        ]
        await asyncio.gather(*tasks)

        # Update statistics aggregator with components
        if self._is_single_instrument and self._single_context:
            # Single instrument mode - use single context
            self._stats_aggregator.order_manager = self._single_context.orders
            self._stats_aggregator.data_manager = self._single_context.data
            self._stats_aggregator.position_manager = self._single_context.positions
            if self._single_context.risk_manager:
                self._stats_aggregator.risk_manager = self._single_context.risk_manager
            if self._single_context.orderbook:
                self._stats_aggregator.orderbook = self._single_context.orderbook
        else:
            # StatisticsAggregator is single-instrument (first symbol) in 4.x.
            if self._instruments:
                first_context = next(iter(self._instruments.values()))
                self._stats_aggregator.order_manager = first_context.orders
                self._stats_aggregator.data_manager = first_context.data
                self._stats_aggregator.position_manager = first_context.positions

    async def _initialize_legacy_single_instrument(self) -> None:
        """Initialize components in legacy single-instrument mode."""
        # Initialize order manager with realtime client for order tracking
        await self._orders.initialize(realtime_client=self.realtime)

        # Initialize position manager with order manager for cleanup
        await self._positions.initialize(
            realtime_client=self.realtime,
            order_manager=self._orders,
        )

        # Load historical data
        logger.info(f"Loading {self.config.initial_days} days of historical data...")
        await self._data.initialize(initial_days=self.config.initial_days)

        # Get instrument info and subscribe to market data
        self.instrument = await self.client.get_instrument(self._symbol)
        if not self.instrument:
            raise ValueError(f"Failed to get instrument info for {self._symbol}")

        await self.realtime.subscribe_market_data([self.instrument.id])

        # Start realtime data feed
        await self._data.start_realtime_feed()

        # Initialize optional components
        if Features.ORDERBOOK in self.config.features:
            logger.info("Initializing orderbook...")
            # Use the actual contract ID for the orderbook to properly match WebSocket updates
            self._orderbook = OrderBook(
                instrument=self.instrument.id,  # Use contract ID instead of symbol
                timezone_str=self.config.timezone,
                project_x=self.client,
                config=self.config.get_orderbook_config(),
                event_bus=self.events,
            )
            await self._orderbook.initialize(
                realtime_client=self.realtime,
                subscribe_to_depth=True,
                subscribe_to_quotes=True,
            )
            self._stats_aggregator.orderbook = self._orderbook

    async def connect(self) -> None:
        """
        Manually connect all components if auto_connect was disabled.

        Example:
            ```python
            suite = await TradingSuite.create("MNQ", auto_connect=False)
            # ... configure components ...
            await suite.connect()
            ```
        """
        if not self._connected:
            await self._initialize()

    async def disconnect(self) -> None:
        """
        Gracefully disconnect all components and clean up resources.

        Example:
            ```python
            await suite.disconnect()
            ```
        """
        logger.info("Disconnecting TradingSuite...")

        # Disconnect realtime FIRST so the SignalR background reader thread is
        # quiesced before any Polars data frames it writes into are freed.
        # Previous order (cleanup contexts -> disconnect realtime) raced native
        # SignalR threads against Polars memory and corrupted the heap on
        # disconnect (Windows STATUS_HEAP_CORRUPTION / 0xc0000374). See #98.
        if self.realtime:
            await self.realtime.disconnect()

        if self._instruments:
            # Multi-instrument mode - disconnect all contexts
            await self._disconnect_instrument_contexts()
        else:
            # Legacy single-instrument mode
            await self._disconnect_legacy_single_instrument()

        # Clean up client context
        if hasattr(self, "_client_context") and self._client_context:
            try:
                await self._client_context.__aexit__(None, None, None)
            except Exception as e:
                logger.error(f"Error cleaning up client context: {e}")
                # Continue with cleanup even if there's an error

        self._connected = False
        self._initialized = False
        logger.info("TradingSuite disconnected")

    async def _disconnect_instrument_contexts(self) -> None:
        """Disconnect all instrument contexts in parallel."""

        async def _disconnect_single_context(context: InstrumentContext) -> None:
            """Disconnect a single instrument context."""
            # Stop data feeds
            if context.data:
                await context.data.stop_realtime_feed()
                await context.data.cleanup()

            # Clean up orderbook
            if context.orderbook:
                await context.orderbook.cleanup()

        # Disconnect all contexts in parallel
        tasks = [
            _disconnect_single_context(context)
            for context in self._instruments.values()
        ]
        await asyncio.gather(*tasks)

    async def _disconnect_legacy_single_instrument(self) -> None:
        """Disconnect components in legacy single-instrument mode."""
        # Stop data feeds
        if hasattr(self, "_data") and self._data:
            await self._data.stop_realtime_feed()
            await self._data.cleanup()

        # Clean up orderbook
        if hasattr(self, "_orderbook") and self._orderbook:
            await self._orderbook.cleanup()

    async def __aenter__(self) -> "TradingSuite":
        """Async context manager entry."""
        # Always ensure we're connected when entering context
        # Context manager should always initialize, regardless of auto_connect setting
        if not self._connected:
            await self._initialize()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Async context manager exit with cleanup."""
        await self.disconnect()

    @property
    def is_connected(self) -> bool:
        """Check if all components are connected and ready."""
        return self._connected and cast(Any, self.realtime).is_connected()

    # Single-instrument accessors. Multi-instrument suites use suite["SYMBOL"].
    @property
    def data(self) -> Any:
        """Realtime data manager for the primary instrument."""
        if hasattr(self, "_data"):
            return self._data
        if self._is_single_instrument and self._single_context:
            return self._single_context.data
        raise AttributeError("'TradingSuite' object has no attribute 'data'")

    @property
    def orders(self) -> Any:
        """Order manager for the primary instrument."""
        if hasattr(self, "_orders"):
            return self._orders
        if self._is_single_instrument and self._single_context:
            return self._single_context.orders
        raise AttributeError("'TradingSuite' object has no attribute 'orders'")

    @property
    def positions(self) -> Any:
        """Position manager for the primary instrument."""
        if hasattr(self, "_positions"):
            return self._positions
        if self._is_single_instrument and self._single_context:
            return self._single_context.positions
        raise AttributeError("'TradingSuite' object has no attribute 'positions'")

    @property
    def orderbook(self) -> Any:
        """Order book for the primary instrument, if the feature is enabled."""
        if hasattr(self, "_orderbook"):
            return self._orderbook
        if self._is_single_instrument and self._single_context:
            return self._single_context.orderbook
        raise AttributeError("'TradingSuite' object has no attribute 'orderbook'")

    @property
    def risk_manager(self) -> Any:
        """Risk manager for the primary instrument, if the feature is enabled."""
        if hasattr(self, "_risk_manager"):
            return self._risk_manager
        if self._is_single_instrument and self._single_context:
            return self._single_context.risk_manager
        raise AttributeError("'TradingSuite' object has no attribute 'risk_manager'")

    @property
    def symbol(self) -> str:
        """Get the original symbol (e.g., 'MNQ') without contract details."""
        return self._symbol

    @property
    def instrument_id(self) -> str | None:
        """Get the full instrument/contract ID (e.g., 'CON.F.US.MNQ.U25')."""
        return self.instrument.id if self.instrument else None

    async def on(self, event: EventType | str, handler: Any) -> None:
        """
        Register event handler through unified event bus.

        This is the single interface for all event handling in the SDK,
        replacing the scattered callback systems across components.

        Args:
            event: Event type to listen for (EventType enum or string)
            handler: Async callable to handle events

        Example:
            ```python
            async def handle_new_bar(event):
                # event.data contains: {'timeframe': str, 'data': bar_dict}
                bar_data = event.data.get("data", {})
                timeframe = event.data.get("timeframe", "")
                print(f"New {timeframe} bar: ${bar_data.get('close', 0):.2f}")


            async def handle_position_closed(event):
                # event.data contains the position object
                position = event.data
                print(f"Position closed: P&L = {position.pnl}")


            async def handle_order_filled(event):
                # event.data contains the order object
                order = event.data
                print(f"Order filled at {order.filledPrice}")


            # Register handlers
            await suite.on(EventType.NEW_BAR, handle_new_bar)
            await suite.on(EventType.POSITION_CLOSED, handle_position_closed)
            await suite.on(EventType.ORDER_FILLED, handle_order_filled)
            ```
        """
        await self.events.on(event, handler)

    async def once(self, event: EventType | str, handler: Any) -> None:
        """
        Register one-time event handler.

        Handler will be automatically removed after first invocation.

        Args:
            event: Event type to listen for
            handler: Async callable to handle event once
        """
        await self.events.once(event, handler)

    async def off(
        self, event: EventType | str | None = None, handler: Any | None = None
    ) -> None:
        """
        Remove event handler(s).

        Args:
            event: Event type to remove handler from (None for all)
            handler: Specific handler to remove (None for all)
        """
        await self.events.off(event, handler)

    def track_order(self, order: Any = None) -> OrderTracker:
        """
        Create an OrderTracker for comprehensive order lifecycle management.

        This provides automatic order state tracking with async waiting capabilities,
        eliminating the need for manual order status polling.

        Args:
            order: Optional order to track immediately (Order, OrderPlaceResponse, or order ID)

        Returns:
            OrderTracker instance (use as context manager)

        Example:
            ```python
            from project_x_py.types.trading import OrderSide

            # Track a new order
            async with suite.track_order() as tracker:
                order = await suite.orders.place_limit_order(
                    contract_id=suite.instrument_id,
                    side=OrderSide.BUY,
                    size=1,
                    price=current_price - 10,
                )
                tracker.track(order)

                try:
                    filled = await tracker.wait_for_fill(timeout=60)
                    print(f"Order filled at {filled.filledPrice}")
                except TimeoutError:
                    await tracker.modify_or_cancel(new_price=current_price - 5)
            ```
        """
        tracker = OrderTracker(self, order)
        return tracker

    def order_chain(self) -> OrderChainBuilder:
        """
        Create an order chain builder for complex order structures.

        Provides a fluent API for building multi-part orders (entry + stops + targets)
        with clean, readable syntax.

        Returns:
            OrderChainBuilder instance

        Example:
            ```python
            # Build a bracket order with stops and targets
            # Note: side=0 for BUY, side=1 for SELL
            order_chain = (
                suite.order_chain()
                .market_order(size=2, side=0)  # BUY 2 contracts
                .with_stop_loss(offset=50)
                .with_take_profit(offset=100)
                .with_trail_stop(offset=25, trigger_offset=50)
            )

            result = await order_chain.execute()

            # Or use a limit entry
            order_chain = (
                suite.order_chain()
                .limit_order(size=1, price=16000, side=0)  # BUY limit
                .with_stop_loss(price=15950)
                .with_take_profit(price=16100)
            )
            ```
        """
        return OrderChainBuilder(self)

    def managed_trade(
        self,
        max_risk_percent: float | None = None,
        max_risk_amount: float | None = None,
    ) -> ManagedTrade:
        """
        Create a managed trade context manager with automatic risk management.

        This provides a high-level interface for executing trades with built-in:
        - Position sizing based on risk parameters
        - Trade validation against risk rules
        - Automatic stop-loss and take-profit attachment
        - Position monitoring and adjustment
        - Cleanup on exit

        Args:
            max_risk_percent: Override max risk percentage for this trade
            max_risk_amount: Override max risk dollar amount for this trade

        Returns:
            ManagedTrade context manager

        Raises:
            ValueError: If risk manager is not enabled

        Example:
            ```python
            # Enter a risk-managed long position
            async with suite.managed_trade(max_risk_percent=0.01) as trade:
                result = await trade.enter_long(
                    stop_loss=current_price - 50,
                    take_profit=current_price + 100,
                )

                # Optional: Scale in
                if market_conditions_favorable:
                    await trade.scale_in(additional_size=1)

                # Optional: Adjust stop
                if price_moved_favorably:
                    await trade.adjust_stop(new_stop_loss=entry_price)

            # Automatic cleanup on exit
            ```
        """
        if not self.risk_manager:
            raise ValueError(
                "Risk manager not enabled. Add 'risk_manager' to features list."
            )

        return ManagedTrade(
            risk_manager=self.risk_manager,
            order_manager=self.orders,  # Use property to access
            position_manager=self.positions,  # Use property to access
            instrument_id=self.instrument_id or self._symbol,
            data_manager=self.data,  # Use property to access
            max_risk_percent=max_risk_percent,
            max_risk_amount=max_risk_amount,
        )

    async def wait_for(
        self, event: EventType | str, timeout: float | None = None
    ) -> Any:
        """
        Wait for specific event to occur.

        Args:
            event: Event type to wait for
            timeout: Optional timeout in seconds

        Returns:
            Event object when received

        Raises:
            TimeoutError: If timeout expires
        """
        return await self.events.wait_for(event, timeout)

    async def get_stats(self) -> TradingSuiteStats:
        """
        Get comprehensive statistics from all components using the aggregator.

        Returns:
            Structured statistics from all active components with accurate metrics
        """
        return await self._stats_aggregator.aggregate_stats()

    async def export_stats(self, export_format: str = "json", **kwargs: Any) -> Any:
        """Export suite statistics as JSON, Prometheus, CSV, or Datadog."""
        from project_x_py.statistics.export import StatsExporter

        stats = await self.get_stats()
        exporter = StatsExporter()
        return await exporter.export(cast(Any, stats), export_format, **kwargs)

    # Session-aware methods
    async def set_session_type(self, session_type: SessionType) -> None:
        """
        Change the active session type for data filtering.

        Args:
            session_type: Type of session to filter for (RTH/ETH)

        Example:
            ```python
            # Switch to RTH-only data
            await suite.set_session_type(SessionType.RTH)
            ```
        """
        # Handle single instrument mode (backward compatibility)
        if self._is_single_instrument and self._single_context:
            if hasattr(self._single_context.data, "set_session_type"):
                await self._single_context.data.set_session_type(session_type)
                logger.info(f"Session type changed to {session_type}")
        # Handle multi-instrument mode
        else:
            for context in self._instruments.values():
                if hasattr(context.data, "set_session_type"):
                    await context.data.set_session_type(session_type)
            if self._instruments:
                logger.info(
                    f"Session type changed to {session_type} for all instruments"
                )

    async def get_session_data(
        self, timeframe: str, session_type: SessionType | None = None
    ) -> Any:
        """
        Get session-filtered market data.

        Args:
            timeframe: Data timeframe (e.g., "1min", "5min")
            session_type: Optional session type override

        Returns:
            Polars DataFrame with session-filtered data

        Example:
            ```python
            # Get RTH-only data
            rth_data = await suite.get_session_data("1min", SessionType.RTH)
            ```
        """
        # Handle single instrument mode (backward compatibility)
        if self._is_single_instrument and self._single_context:
            if hasattr(self._single_context.data, "get_session_data"):
                return await self._single_context.data.get_session_data(
                    timeframe, session_type
                )
            # Fallback to regular data if no session support
            return await self._single_context.data.get_data(timeframe)

        # Handle multi-instrument mode - return dict of data
        result = {}
        for symbol, context in self._instruments.items():
            if hasattr(context.data, "get_session_data"):
                result[symbol] = await context.data.get_session_data(
                    timeframe, session_type
                )
            else:
                result[symbol] = await context.data.get_data(timeframe)
        return result if result else None

    async def get_session_statistics(self, timeframe: str = "1min") -> dict[str, Any]:
        """
        Get session-specific statistics.

        Returns:
            Dictionary containing session statistics like volume, VWAP, etc.

        Example:
            ```python
            stats = await suite.get_session_statistics()
            print(f"RTH Volume: {stats['rth_volume']}")
            print(f"ETH Volume: {stats['eth_volume']}")
            ```
        """
        # Handle single instrument mode (backward compatibility)
        if self._is_single_instrument and self._single_context:
            if hasattr(self._single_context.data, "get_session_statistics"):
                return await self._single_context.data.get_session_statistics(timeframe)
            return {}

        # Handle multi-instrument mode - return dict of stats per instrument
        result = {}
        for symbol, context in self._instruments.items():
            if hasattr(context.data, "get_session_statistics"):
                result[symbol] = await context.data.get_session_statistics(timeframe)
        return result if result else {}

    # --- Container Protocol Methods ---
    def __getitem__(self, symbol: str) -> InstrumentContext:
        """
        Get InstrumentContext for a specific symbol.

        Args:
            symbol: The instrument symbol (e.g., "MNQ", "ES")

        Returns:
            InstrumentContext for the specified symbol

        Raises:
            KeyError: If symbol is not found

        Example:
            ```python
            # Access specific instrument context
            mnq_context = suite["MNQ"]
            current_price = await mnq_context.data.get_current_price()
            ```
        """
        return self._instruments[symbol]

    def __len__(self) -> int:
        """Return the number of instruments in the suite."""
        return len(self._instruments)

    def __iter__(self) -> Iterator[str]:
        """Iterate over instrument symbols."""
        return iter(self._instruments)

    def __contains__(self, symbol: str) -> bool:
        """Check if an instrument symbol is in the suite."""
        return symbol in self._instruments

    def keys(self) -> Iterator[str]:
        """Return an iterator over instrument symbols."""
        return iter(self._instruments.keys())

    def values(self) -> Iterator[InstrumentContext]:
        """Return an iterator over instrument contexts."""
        return iter(self._instruments.values())

    def items(self) -> Iterator[tuple[str, InstrumentContext]]:
        """Return an iterator over (symbol, context) pairs."""
        return iter(self._instruments.items())

    # --- Backward Compatibility ---
    def __getattr__(self, name: str) -> Any:
        """
        Provide backward compatibility for single-instrument access.

        This allows existing code to work while providing deprecation warnings.
        Only works in single-instrument mode.

        Args:
            name: Attribute name being accessed

        Returns:
            The requested attribute from the single instrument context

        Raises:
            AttributeError: If not in single-instrument mode or attribute not found
        """
        if (
            self._is_single_instrument
            and self._single_context
            and hasattr(self._single_context, name)
        ):
            return getattr(self._single_context, name)

        # Provide helpful error message for multi-instrument suites
        if len(self._instruments) > 1:
            available_symbols = list(self._instruments.keys())
            raise AttributeError(
                f"'{type(self).__name__}' object has no attribute '{name}'. "
                f"For multi-instrument suites, use suite['SYMBOL'].{name}. "
                f"Available instruments: {available_symbols}"
            )
        else:
            raise AttributeError(
                f"'{type(self).__name__}' object has no attribute '{name}'"
            )
