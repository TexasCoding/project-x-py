"""
Core RealtimeDataManager class for efficient real-time OHLCV data management.

Author: @TexasCoding
Date: 2025-08-02

Overview:
    Provides the main RealtimeDataManager class that handles real-time market data
    processing across multiple timeframes. Implements efficient OHLCV (Open, High, Low, Close, Volume)
    data management with WebSocket integration, automatic bar creation, and comprehensive memory management.

Key Features:
    - Multi-timeframe OHLCV data management with real-time updates
    - WebSocket integration for zero-latency tick processing
    - Automatic bar creation and maintenance across all timeframes
    - Memory-efficient sliding window storage with automatic cleanup
    - Event-driven callback system for new bars and data updates
    - Timezone-aware timestamp handling (default: CME Central Time)
    - Thread-safe operations with asyncio locks
    - Comprehensive health monitoring and statistics

Architecture:
    - Mixin-based design for modular functionality
    - Dependency injection for ProjectX client and realtime client
    - Event-driven processing with callback system
    - Memory management with automatic cleanup
    - Thread-safe operations with proper locking

Performance Benefits:
    - 95% reduction in API calls compared to polling
    - Sub-second data freshness with WebSocket feeds
    - Synchronized data across all timeframes
    - Minimal latency for trading signals
    - Resilience to network issues

Note:
    This class is the core implementation of the real-time data manager. For most
    applications, it is recommended to interact with it through the `TradingSuite`
    (`suite.data`), which handles its lifecycle and integration automatically.
    The example below demonstrates direct, low-level instantiation and usage.

Example Usage:
    ```python
    # V3.1: TradingSuite manages data manager automatically
    from project_x_py import TradingSuite, EventType

    # V3.1: Create suite with integrated data manager
    suite = await TradingSuite.create(
        "MNQ",  # Using E-mini NASDAQ futures
        timeframes=["1min", "5min", "15min", "1hr"],
        initial_days=5,
        timezone="America/Chicago",  # CME timezone
    )

    # V3.1: Data manager is automatically initialized with historical data
    print(f"Data manager ready for {suite.instrument}")


    # V3.1: Register callbacks via suite's event bus
    @suite.events.on(EventType.NEW_BAR)
    async def on_new_bar(event):
        timeframe = event.data["timeframe"]
        bar_data = event.data["data"]
        print(f"New {timeframe} bar:")
        print(f"  Open: {bar_data['open']}, High: {bar_data['high']}")
        print(f"  Low: {bar_data['low']}, Close: {bar_data['close']}")
        print(f"  Volume: {bar_data['volume']}")


    # V3.1: Access multi-timeframe OHLCV data via suite.data
    data_5m = await suite.data.get_data("5min", bars=100)
    data_15m = await suite.data.get_data("15min", bars=50)
    mtf_data = await suite.data.get_mtf_data()  # All timeframes at once

    # V3.1: Get current market price
    current_price = await suite.data.get_current_price()

    # V3.1: Monitor memory and performance
    stats = suite.data.get_memory_stats()
    print(f"Data points stored: {stats['total_data_points']}")

    # V3.1: Cleanup is automatic
    await suite.disconnect()

    # V3.1: Low-level direct usage (advanced users only)
    # from project_x_py.realtime_data_manager import RealtimeDataManager
    # manager = RealtimeDataManager(
    #     instrument="MNQ",
    #     project_x=client,
    #     realtime_client=realtime_client,
    #     timeframes=["1min", "5min"],
    #     event_bus=event_bus,
    # )
    # await manager.initialize(initial_days=5)
    # await manager.start_realtime_feed()
    ```

Supported Timeframes:
    - Second-based: "1sec", "5sec", "10sec", "15sec", "30sec"
    - Minute-based: "1min", "5min", "15min", "30min"
    - Hour-based: "1hr", "4hr"
    - Day-based: "1day"
    - Week-based: "1week"
    - Month-based: "1month"

See Also:
    - `realtime_data_manager.callbacks.CallbackMixin`
    - `realtime_data_manager.data_access.DataAccessMixin`
    - `realtime_data_manager.data_processing.DataProcessingMixin`
    - `realtime_data_manager.memory_management.MemoryManagementMixin`
    - `realtime_data_manager.validation.ValidationMixin`
"""

import asyncio
import contextlib
import time
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import polars as pl
import pytz

from project_x_py.client.base import ProjectXBase
from project_x_py.exceptions import (
    ProjectXError,
    ProjectXInstrumentError,
)
from project_x_py.models import Instrument
from project_x_py.realtime_data_manager.callbacks import CallbackMixin
from project_x_py.realtime_data_manager.data_access import DataAccessMixin
from project_x_py.realtime_data_manager.data_processing import DataProcessingMixin
from project_x_py.realtime_data_manager.dataframe_optimization import LazyDataFrameMixin
from project_x_py.realtime_data_manager.dst_handling import DSTHandlingMixin
from project_x_py.realtime_data_manager.dynamic_resource_limits import (
    DynamicResourceMixin,
)
from project_x_py.realtime_data_manager.memory_management import MemoryManagementMixin
from project_x_py.realtime_data_manager.mmap_overflow import MMapOverflowMixin
from project_x_py.realtime_data_manager.validation import (
    DataValidationMixin,
    ValidationMixin,
)
from project_x_py.statistics.base import BaseStatisticsTracker
from project_x_py.statistics.bounded_statistics import BoundedStatisticsMixin
from project_x_py.types.config_types import DataManagerConfig
from project_x_py.types.stats_types import ComponentStats, RealtimeDataManagerStats
from project_x_py.utils import (
    ErrorMessages,
    LogContext,
    LogMessages,
    ProjectXLogger,
    format_error_message,
    handle_errors,
)
from project_x_py.utils.lock_optimization import (
    AsyncRWLock,
    LockFreeBuffer,
    LockOptimizationMixin,
)

if TYPE_CHECKING:
    from project_x_py.client import ProjectXBase
    from project_x_py.realtime import ProjectXRealtimeClient


class _DummyEventBus:
    """A dummy event bus that does nothing, for use when no event bus is provided."""

    async def on(self, _event_type: Any, _callback: Any) -> None:
        """No-op event registration."""

    async def emit(
        self, _event_type: Any, _data: Any, _source: str | None = None
    ) -> None:
        """No-op event emission."""


class RealtimeDataManager(
    DataProcessingMixin,
    MemoryManagementMixin,
    DynamicResourceMixin,
    MMapOverflowMixin,
    CallbackMixin,
    DataAccessMixin,
    LazyDataFrameMixin,
    ValidationMixin,
    DataValidationMixin,
    BoundedStatisticsMixin,
    BaseStatisticsTracker,
    LockOptimizationMixin,
    DSTHandlingMixin,
):
    # Explicit attribute definitions to resolve mixin conflicts
    data_lock: Any  # Will be set to AsyncRWLock in __init__
    log_dst_event: Any  # Will be overridden by mixins
    """
    Async optimized real-time OHLCV data manager for efficient multi-timeframe trading data.

    This class focuses exclusively on OHLCV (Open, High, Low, Close, Volume) data management
    across multiple timeframes through real-time tick processing using async/await patterns.
    It provides a foundation for trading strategies that require synchronized data across
    different timeframes with minimal API usage.

    Core Architecture:
        Traditional approach: Poll API every 5 minutes for each timeframe = 20+ API calls/hour
        Real-time approach: Load historical once + live tick processing = 1 API call + WebSocket
        Result: 95% reduction in API calls with sub-second data freshness

    Key Benefits:
        - Reduction in API rate limit consumption
        - Synchronized data across all timeframes
        - Real-time updates without polling
        - Minimal latency for trading signals
        - Resilience to network issues

    Features:
        - Complete async/await implementation for non-blocking operation
        - Zero-latency OHLCV updates via WebSocket integration
        - Automatic bar creation and maintenance across all timeframes
        - Async-safe multi-timeframe data access with locks
        - Memory-efficient sliding window storage with automatic pruning
        - Timezone-aware timestamp handling (default: CME Central Time)
        - Event callbacks for new bars and real-time data updates
        - Comprehensive health monitoring and statistics

    Available Timeframes:
        - Second-based: "1sec", "5sec", "10sec", "15sec", "30sec"
        - Minute-based: "1min", "5min", "15min", "30min"
        - Hour-based: "1hr", "4hr"
        - Day-based: "1day"
        - Week-based: "1week"
        - Month-based: "1month"

    Example Usage:
        ```python
        # Create shared async realtime client
        async_realtime_client = ProjectXRealtimeClient(config)
        await async_realtime_client.connect()

        # Initialize async data manager with dependency injection
        manager = RealtimeDataManager(
            instrument="MNQ",  # E-mini NASDAQ futures
            project_x=async_project_x_client,  # For historical data loading
            realtime_client=async_realtime_client,
            timeframes=["1min", "5min", "15min", "1hr"],
            timezone="America/Chicago",  # CME timezone
        )

        # Load historical data for all timeframes
        if await manager.initialize(initial_days=30):
            print("Historical data loaded successfully")

        # Start real-time feed (registers callbacks with existing client)
        if await manager.start_realtime_feed():
            print("Real-time OHLCV feed active")


        # Register callback for new bars
        async def on_new_bar(data):
            timeframe = data["timeframe"]
            bar_data = data["data"]
            print(f"New {timeframe} bar: Close={bar_data['close']}")


        await manager.add_callback("new_bar", on_new_bar)

        # Access multi-timeframe OHLCV data in your trading loop
        data_5m = await manager.get_data("5min", bars=100)
        data_15m = await manager.get_data("15min", bars=50)
        mtf_data = await manager.get_mtf_data()  # All timeframes at once

        # Get current market price (latest tick or bar close)
        current_price = await manager.get_current_price()

        # When done, clean up resources
        await manager.cleanup()
        ```

    Note:
        - All methods accessing data are thread-safe with asyncio locks
        - Automatic memory management limits data storage for efficiency
        - All timestamp handling is timezone-aware by default
        - Uses Polars DataFrames for high-performance data operations
    """

    def __init__(
        self,
        instrument: str,
        project_x: "ProjectXBase | None",
        realtime_client: "ProjectXRealtimeClient",
        event_bus: Any | None = None,
        timeframes: list[str] | None = None,
        timezone: str = "America/Chicago",
        config: DataManagerConfig | None = None,
    ):
        """
        Initialize the optimized real-time OHLCV data manager with dependency injection.

        Creates a new instance of the RealtimeDataManager that manages real-time market data
        for a specific trading instrument across multiple timeframes. The manager uses dependency
        injection with ProjectX for historical data loading and ProjectXRealtimeClient
        for live WebSocket market data.

        Args:
            instrument: Trading instrument symbol (e.g., "MNQ", "ES", "NQ").
                This should be the base symbol, not a specific contract.

            project_x: ProjectXBase client instance for initial historical data loading.
                This client should already be authenticated before passing to this constructor.

            realtime_client: ProjectXRealtimeClient instance for live market data.
                The client does not need to be connected yet, as the manager will handle
                connection when start_realtime_feed() is called.

            event_bus: EventBus instance for unified event handling. Required for all
                event emissions including new bars, data updates, and errors.

            timeframes: List of timeframes to track (default: ["5min"] if None provided).
                Available timeframes include:
                - Seconds: "1sec", "5sec", "10sec", "15sec", "30sec"
                - Minutes: "1min", "5min", "15min", "30min"
                - Hours: "1hr", "4hr"
                - Days/Weeks/Months: "1day", "1week", "1month"

            timezone: Timezone for timestamp handling (default: "America/Chicago").
                This timezone is used for all bar calculations and should typically be set to
                the exchange timezone for the instrument (e.g., "America/Chicago" for CME).

            config: Optional configuration for data manager behavior. If not provided,
                default values will be used for all configuration options.

        Raises:
            ValueError: If an invalid timeframe is provided.

        Example:
            ```python
            # Create the required clients first
            px_client = ProjectX()
            await px_client.authenticate()

            # Create and connect realtime client
            realtime_client = ProjectXRealtimeClient(px_client.config)

            # Create data manager with multiple timeframes for Gold mini futures
            data_manager = RealtimeDataManager(
                instrument="MNQ",  # E-mini NASDAQ futures
                project_x=px_client,
                realtime_client=realtime_client,
                timeframes=["1min", "5min", "15min", "1hr"],
                timezone="America/Chicago",  # CME timezone
            )

            # Note: After creating the manager, you need to call:
            # 1. await data_manager.initialize() to load historical data
            # 2. await data_manager.start_realtime_feed() to begin real-time updates
            ```

        Note:
            The manager instance is not fully initialized until you call the initialize() method,
            which loads historical data for all timeframes. After initialization, call
            start_realtime_feed() to begin receiving real-time updates.
        """
        # Validate required parameters
        if instrument is None or instrument == "":
            raise ValueError(
                "instrument parameter is required and cannot be None or empty"
            )
        if project_x is None:
            raise ValueError("project_x parameter is required and cannot be None")
        if realtime_client is None:
            raise ValueError("realtime_client parameter is required and cannot be None")
        if timeframes is not None and len(timeframes) == 0:
            raise ValueError("timeframes list cannot be empty if provided")

        if timeframes is None:
            timeframes = ["5min"]

        # Set basic attributes needed by mixins
        self.instrument: str = instrument
        self.project_x: ProjectXBase | None = project_x
        self.realtime_client: ProjectXRealtimeClient = realtime_client
        # EventBus is optional in tests; fallback to a simple dummy if None
        self.event_bus = event_bus if event_bus is not None else _DummyEventBus()

        self.logger = ProjectXLogger.get_logger(__name__)

        # Store configuration with defaults
        self.config = config or {}

        # Initialize lock optimization first (required by LockOptimizationMixin)
        LockOptimizationMixin.__init__(self)

        # Replace single data_lock with optimized read/write lock for DataFrame operations
        self.data_rw_lock = AsyncRWLock(f"data_manager_{instrument}")

        # Keep backward compatibility - data_lock alias for mixins
        self.data_lock = self.data_rw_lock

        # Lock-free buffer for high-frequency tick data
        self.tick_buffer = LockFreeBuffer[dict[str, Any]](max_size=10000)

        # Initialize timeframes needed by mixins
        self.timeframes: dict[str, dict[str, Any]] = {}

        # Initialize data storage
        self.data: dict[str, pl.DataFrame] = {}

        # Apply defaults which sets max_bars_per_timeframe etc.
        self._apply_config_defaults()

        # Check if bounded statistics are enabled
        self.use_bounded_statistics: bool = bool(
            config.get("use_bounded_statistics", True) if config else True
        )

        # Initialize all mixins (they may need the above attributes)
        super().__init__()

        # Initialize bounded statistics if enabled
        if self.use_bounded_statistics:
            # Extract config values with type safety
            max_recent_metrics = 3600
            hourly_retention_hours = 24
            daily_retention_days = 30
            timing_buffer_size = 1000
            cleanup_interval_minutes = 5.0

            if config:
                # Safely cast config values with proper type conversion
                max_recent_val = config.get("max_recent_metrics", 3600)
                max_recent_metrics = (
                    int(max_recent_val) if max_recent_val is not None else 3600  # type: ignore[call-overload]
                )

                hourly_retention_val = config.get("hourly_retention_hours", 24)
                hourly_retention_hours = (
                    int(hourly_retention_val)  # type: ignore[call-overload]
                    if hourly_retention_val is not None
                    else 24
                )

                daily_retention_val = config.get("daily_retention_days", 30)
                daily_retention_days = (
                    int(daily_retention_val) if daily_retention_val is not None else 30  # type: ignore[call-overload]
                )

                timing_buffer_val = config.get("timing_buffer_size", 1000)
                timing_buffer_size = (
                    int(timing_buffer_val) if timing_buffer_val is not None else 1000  # type: ignore[call-overload]
                )

                cleanup_interval_val = config.get("cleanup_interval_minutes", 5.0)
                cleanup_interval_minutes = (
                    float(cleanup_interval_val)
                    if cleanup_interval_val is not None
                    else 5.0
                )

            BoundedStatisticsMixin.__init__(
                self,
                max_recent_metrics=max_recent_metrics,
                hourly_retention_hours=hourly_retention_hours,
                daily_retention_days=daily_retention_days,
                timing_buffer_size=timing_buffer_size,
                cleanup_interval_minutes=cleanup_interval_minutes,
            )

        # Initialize v3.3.0 statistics system using inheritance (for backward compatibility)
        BaseStatisticsTracker.__init__(
            self, component_name="realtime_data_manager", max_errors=100, cache_ttl=5.0
        )

        # Set initial status asynchronously after init is complete when event loop is available
        self._initial_status_task: asyncio.Task[None] | None = None

        # Set timezone for consistent timestamp handling - prioritize config over parameter
        effective_timezone = config.get("timezone") if config else None
        if effective_timezone is None:
            effective_timezone = timezone
        self.timezone: Any = pytz.timezone(effective_timezone)  # CME timezone default

        timeframes_dict: dict[str, dict[str, Any]] = {
            "1sec": {"interval": 1, "unit": 1, "name": "1sec"},
            "5sec": {"interval": 5, "unit": 1, "name": "5sec"},
            "10sec": {"interval": 10, "unit": 1, "name": "10sec"},
            "15sec": {"interval": 15, "unit": 1, "name": "15sec"},
            "30sec": {"interval": 30, "unit": 1, "name": "30sec"},
            "1min": {"interval": 1, "unit": 2, "name": "1min"},
            "5min": {"interval": 5, "unit": 2, "name": "5min"},
            "15min": {"interval": 15, "unit": 2, "name": "15min"},
            "30min": {"interval": 30, "unit": 2, "name": "30min"},
            "1hr": {"interval": 60, "unit": 2, "name": "1hr"},
            "4hr": {"interval": 240, "unit": 2, "name": "4hr"},
            "1day": {"interval": 1, "unit": 4, "name": "1day"},
            "1week": {"interval": 1, "unit": 5, "name": "1week"},
            "1month": {"interval": 1, "unit": 6, "name": "1month"},
        }

        # Update timeframes with configs (dict already created above)
        for tf in timeframes:
            if tf not in timeframes_dict:
                raise ValueError(
                    f"Invalid timeframe: {tf}, valid timeframes are: {list(timeframes_dict.keys())}"
                )
            self.timeframes[tf] = timeframes_dict[tf]

        # Real-time data components
        # Use deque for automatic size management of tick data
        from collections import deque

        self.current_tick_data: deque[dict[str, Any]] = deque(maxlen=10000)
        self.last_bar_times: dict[str, datetime] = {}

        # Async synchronization
        self.is_running: bool = False
        self._initialized: bool = False
        # EventBus is now used for all event handling
        self.indicator_cache: defaultdict[str, dict[str, Any]] = defaultdict(dict)

        # Contract ID for real-time subscriptions
        self.contract_id: str | None = None
        # Actual symbol ID from the resolved instrument (e.g., "ENQ" when user specifies "NQ")
        self.instrument_symbol_id: str | None = None
        # Tick size for price alignment
        self.tick_size: float = 0.25  # Default, will be updated in initialize()

        # Memory management settings are set in _apply_config_defaults()
        self.last_cleanup: float = time.time()

        # Legacy memory stats for backward compatibility
        self.memory_stats = {
            "bars_processed": 0,
            "ticks_processed": 0,
            "quotes_processed": 0,
            "trades_processed": 0,
            "timeframe_stats": {tf: {"bars": 0, "updates": 0} for tf in timeframes},
            "avg_processing_time_ms": 0.0,
            "data_latency_ms": 0.0,
            "buffer_utilization": 0.0,
            "total_bars_stored": 0,
            "memory_usage_mb": 0.0,
            "compression_ratio": 1.0,
            "updates_per_minute": 0.0,
            "last_update": None,
            "data_freshness_seconds": 0.0,
            "data_validation_errors": 0,
            "connection_interruptions": 0,
            "recovery_attempts": 0,
            # Legacy fields for backward compatibility
            "total_bars": 0,
            "bars_cleaned": 0,
            "last_cleanup": time.time(),
        }

        # Initialize new statistics system counters
        self._init_data_manager_counters()

        # Background cleanup task
        self._cleanup_task: asyncio.Task[None] | None = None

        # Background bar timer task for low-volume periods
        self._bar_timer_task: asyncio.Task[None] | None = None

        # Initialize dynamic resource management
        self._enable_dynamic_limits = (
            config.get("enable_dynamic_limits", True) if config else True
        )
        if self._enable_dynamic_limits:
            # Configure dynamic resource management with defaults
            resource_config = config.get("resource_config", {}) if config else {}
            self.configure_dynamic_resources(**resource_config)
            self.logger.info("Dynamic resource limits enabled")
        else:
            self.logger.info("Dynamic resource limits disabled")

        self.logger.info(
            "RealtimeDataManager initialized", extra={"instrument": instrument}
        )

    def _init_data_manager_counters(self) -> None:
        """Initialize data manager specific counters for new statistics system."""
        # These will be tracked using the new BaseStatisticsTracker async methods
        # Called during __init__ but actual counter setup happens async

    async def get_memory_stats(self) -> "RealtimeDataManagerStats":
        """Get comprehensive memory usage statistics."""
        # Async method for proper I/O handling and new statistics system compatibility

        # Update current statistics from data structures
        timeframe_stats = {}
        total_bars = 0

        for tf_key in self.timeframes:
            if tf_key in self.data:
                bar_count = len(self.data[tf_key])
                timeframe_stats[tf_key] = bar_count
                total_bars += bar_count
            else:
                timeframe_stats[tf_key] = 0

        # Update legacy memory stats
        self.memory_stats["total_bars_stored"] = total_bars
        self.memory_stats["buffer_utilization"] = (
            len(self.current_tick_data) / self.tick_buffer_size
            if self.tick_buffer_size > 0
            else 0.0
        )

        # Calculate memory usage (synchronous version)
        data_memory = sum(
            (len(df) * 6 * 8) / (1024 * 1024)
            for df in self.data.values()
            if df is not None and not df.is_empty()
        )
        tick_memory = (
            len(self.current_tick_data) * 0.0001
            if hasattr(self, "current_tick_data")
            else 0.0
        )
        estimated_memory_mb = 0.1 + data_memory + tick_memory  # Base overhead + data

        self.memory_stats["memory_usage_mb"] = estimated_memory_mb
        self.memory_stats["last_update"] = datetime.now()

        # Add overflow stats if available
        overflow_stats = {}
        if hasattr(self, "get_overflow_stats"):
            try:
                method = self.get_overflow_stats
                if callable(method):
                    # Method is always async now
                    overflow_stats = await method()
            except Exception:
                overflow_stats = {}

        # Add lock optimization stats
        lock_stats = {}
        if hasattr(self, "data_rw_lock"):
            try:
                # Get lock stats asynchronously - this is a sync method so we can't await
                # We'll provide basic stats synchronously
                lock_stats = {
                    "reader_count": getattr(self.data_rw_lock, "reader_count", 0),
                    "lock_name": getattr(self.data_rw_lock, "name", "unknown"),
                }
            except Exception:
                lock_stats = {"error": "Failed to get lock stats"}

        # Return structure that matches RealtimeDataManagerStats TypedDict
        result: RealtimeDataManagerStats = {
            "bars_processed": self.memory_stats["bars_processed"],
            "ticks_processed": self.memory_stats["ticks_processed"],
            "quotes_processed": self.memory_stats["quotes_processed"],
            "trades_processed": self.memory_stats["trades_processed"],
            "timeframe_stats": self.memory_stats["timeframe_stats"],
            "avg_processing_time_ms": self.memory_stats["avg_processing_time_ms"],
            "data_latency_ms": self.memory_stats["data_latency_ms"],
            "buffer_utilization": self.memory_stats["buffer_utilization"],
            "total_bars_stored": self.memory_stats["total_bars_stored"],
            "memory_usage_mb": self.memory_stats["memory_usage_mb"],
            "compression_ratio": self.memory_stats["compression_ratio"],
            "updates_per_minute": self.memory_stats["updates_per_minute"],
            "last_update": (
                self.memory_stats["last_update"].isoformat()
                if self.memory_stats["last_update"]
                else None
            ),
            "data_freshness_seconds": self.memory_stats["data_freshness_seconds"],
            "data_validation_errors": self.memory_stats["data_validation_errors"],
            "connection_interruptions": self.memory_stats["connection_interruptions"],
            "recovery_attempts": self.memory_stats["recovery_attempts"],
            "overflow_stats": overflow_stats,
            "buffer_overflow_stats": overflow_stats.get("buffer_stats", {}),
            "lock_optimization_stats": lock_stats,
        }

        return result

    async def get_resource_stats(self) -> dict[str, Any]:
        """
        Get comprehensive resource management statistics.

        Returns:
            Dictionary with resource statistics and current state
        """
        if self._enable_dynamic_limits and hasattr(self, "_current_limits"):
            # Get resource stats from the DynamicResourceMixin
            return await super().get_resource_stats()
        else:
            # Return basic resource information when dynamic limits are disabled
            return {
                "dynamic_limits_enabled": False,
                "static_limits": {
                    "max_bars_per_timeframe": self.max_bars_per_timeframe,
                    "tick_buffer_size": self.tick_buffer_size,
                },
                "memory_usage": {
                    "total_bars": sum(len(df) for df in self.data.values()),
                    "tick_buffer_utilization": len(self.current_tick_data)
                    / self.tick_buffer_size
                    if self.tick_buffer_size > 0
                    else 0.0,
                },
            }

    def _apply_config_defaults(self) -> None:
        """Apply default values for configuration options."""
        # Data management settings
        self.max_bars_per_timeframe = self.config.get("max_bars_per_timeframe", 1000)
        self.enable_tick_data = self.config.get("enable_tick_data", True)
        self.enable_level2_data = self.config.get("enable_level2_data", False)
        self.buffer_size = self.config.get("buffer_size", 1000)
        self.compression_enabled = self.config.get("compression_enabled", True)
        self.data_validation = self.config.get("data_validation", True)
        self.auto_cleanup = self.config.get("auto_cleanup", True)
        self.cleanup_interval_minutes = self.config.get("cleanup_interval_minutes", 5)
        self.historical_data_cache = self.config.get("historical_data_cache", True)
        self.cache_expiry_hours = self.config.get("cache_expiry_hours", 24)

        # Configuration for historical data loading
        self.default_initial_days = self.config.get("initial_days", 1)

        # Set memory management attributes based on config
        self.tick_buffer_size = self.buffer_size
        self.cleanup_interval = float(
            self.cleanup_interval_minutes * 60
        )  # Convert to seconds

    async def _set_initial_status(self) -> None:
        """Set initial status for statistics tracking."""
        await self.set_status("initializing")
        # Initialize key counters
        await self.increment("component_initialized", 1)
        await self.set_gauge(
            "total_timeframes",
            len(self.timeframes) if hasattr(self, "timeframes") else 0,
        )

    @handle_errors("initialize", reraise=True, default_return=False)
    async def initialize(self, initial_days: int = 1) -> bool:
        """
        Initialize the real-time data manager by loading historical OHLCV data.

        This method performs the initial setup of the data manager by loading historical
        OHLCV data for all configured timeframes. It identifies the correct contract ID
        for the instrument and loads the specified number of days of historical data
        into memory for each timeframe. This provides a baseline of data before real-time
        updates begin.

        Args:
            initial_days: Number of days of historical data to load (default: 1).
                Higher values provide more historical context but consume more memory.
                Typical values are:
                - 1-5 days: For short-term trading and minimal memory usage
                - 30 days: For strategies requiring more historical context
                - 90+ days: For longer-term pattern detection or backtesting

        Returns:
            bool: True if initialization completed successfully for at least one timeframe,
                False if errors occurred for all timeframes or the instrument wasn't found.

        Raises:
            Exception: Any exceptions from the API are caught and logged, returning False.

        Example:
            ```python
            # Initialize with 30 days of historical data
            success = await data_manager.initialize(initial_days=30)

            if success:
                print("Historical data loaded successfully")

                # Check data availability for each timeframe
                memory_stats = data_manager.get_memory_stats()
                for tf, count in memory_stats["timeframe_bar_counts"].items():
                    print(f"Loaded {count} bars for {tf} timeframe")
            else:
                print("Failed to initialize data manager")
            ```

        Note:
            - This method must be called before start_realtime_feed()
            - The method retrieves the contract ID for the instrument, which is needed
              for real-time data subscriptions
            - If data for a specific timeframe fails to load, the method will log a warning
              but continue with the other timeframes
        """
        # Skip if already initialized (idempotent behavior)
        if self._initialized:
            self.logger.debug(
                "Skipping initialization - already initialized",
                extra={"instrument": self.instrument},
            )
            return True

        with LogContext(
            self.logger,
            operation="initialize",
            instrument=self.instrument,
            initial_days=initial_days,
        ):
            self.logger.debug(
                LogMessages.DATA_FETCH,
                extra={"phase": "initialization", "instrument": self.instrument},
            )
            if self.project_x is None:
                raise ProjectXError(
                    format_error_message(
                        ErrorMessages.INTERNAL_ERROR,
                        reason="ProjectX client not initialized",
                    )
                )
            # Get the contract ID for the instrument
            instrument_info: Instrument | None = await self.project_x.get_instrument(
                self.instrument
            )
            if instrument_info is None:
                raise ProjectXInstrumentError(
                    format_error_message(
                        ErrorMessages.INSTRUMENT_NOT_FOUND, symbol=self.instrument
                    )
                )

            # Store the exact contract ID for real-time subscriptions
            self.contract_id = instrument_info.id

            # Store the tick size for price alignment
            self.tick_size = getattr(instrument_info, "tickSize", 0.25)

            # Store the actual symbol ID for matching (e.g., "ENQ" when user specifies "NQ")
            # Extract from symbolId like "F.US.ENQ" -> "ENQ"
            if instrument_info.symbolId and "." in instrument_info.symbolId:
                parts = instrument_info.symbolId.split(".")
                self.instrument_symbol_id = (
                    parts[-1] if parts else instrument_info.symbolId
                )
            else:
                self.instrument_symbol_id = instrument_info.symbolId or self.instrument

            # Load initial data for all timeframes
            # Handle both Lock and AsyncRWLock types
            if isinstance(self.data_lock, AsyncRWLock):
                async with self.data_lock.write_lock():
                    for tf_key, tf_config in self.timeframes.items():
                        await self._load_timeframe_data(tf_key, tf_config, initial_days)
            else:
                async with self.data_lock:
                    for tf_key, tf_config in self.timeframes.items():
                        await self._load_timeframe_data(tf_key, tf_config, initial_days)

        # Update statistics for successful initialization
        await self.set_status("initialized")
        await self.increment("initialization_success", 1)
        await self.set_gauge(
            "total_timeframes_loaded",
            len([tf for tf in self.timeframes if tf in self.data]),
        )

        # Start cleanup scheduler now that event loop is available
        if hasattr(self, "_ensure_cleanup_scheduler_started"):
            await self._ensure_cleanup_scheduler_started()

        # Start initial status task now that event loop is available
        if self._initial_status_task is None:
            self._initial_status_task = asyncio.create_task(self._set_initial_status())

        # Mark as initialized
        self._initialized = True

        self.logger.debug(
            LogMessages.DATA_RECEIVED,
            extra={"status": "initialized", "instrument": self.instrument},
        )
        return True

    async def _load_timeframe_data(
        self, tf_key: str, tf_config: dict[str, Any], initial_days: int
    ) -> None:
        """Load data for a specific timeframe."""
        if self.project_x is None:
            raise ProjectXError(
                format_error_message(
                    ErrorMessages.INTERNAL_ERROR,
                    reason="ProjectX client not initialized",
                )
            )
        bars = await self.project_x.get_bars(
            self.instrument,  # Use base symbol, not contract ID
            interval=tf_config["interval"],
            unit=tf_config["unit"],
            days=initial_days,
        )

        if bars is not None and not bars.is_empty():
            self.data[tf_key] = bars
            # Store the last bar time for proper sync with real-time data
            last_bar_time = bars.select(pl.col("timestamp")).tail(1).item()
            self.last_bar_times[tf_key] = last_bar_time

            # Check for potential gap between historical data and current time
            from datetime import datetime

            current_time = datetime.now(self.timezone)
            # Ensure both datetimes have timezone information for comparison
            if last_bar_time.tzinfo is None:
                # Assume last_bar_time is in the same timezone as configured
                last_bar_time = self.timezone.localize(last_bar_time)
            time_gap = current_time - last_bar_time

            # Warn if historical data is more than 5 minutes old
            if time_gap.total_seconds() > 300:
                self.logger.warning(
                    f"Historical data for {tf_key} ends at {last_bar_time}, "
                    f"{time_gap.total_seconds() / 60:.1f} minutes ago. "
                    "Gap will be filled when real-time data arrives.",
                    extra={
                        "timeframe": tf_key,
                        "gap_minutes": time_gap.total_seconds() / 60,
                    },
                )

            self.logger.debug(
                LogMessages.DATA_RECEIVED,
                extra={"timeframe": tf_key, "bar_count": len(bars)},
            )
        else:
            self.logger.warning(
                LogMessages.DATA_ERROR,
                extra={"timeframe": tf_key, "error": "No data loaded"},
            )

    @handle_errors("start realtime feed", reraise=True, default_return=False)
    async def start_realtime_feed(self) -> bool:
        """
        Start the real-time OHLCV data feed using WebSocket connections.

        This method configures and starts the real-time market data feed for the instrument.
        It registers callbacks with the realtime client to receive market data updates,
        subscribes to the appropriate market data channels, and initiates the background
        cleanup task for memory management.

        The method will:
        1. Register callback handlers for quotes and trades
        2. Subscribe to market data for the instrument's contract ID
        3. Start a background task for periodic memory cleanup

        Returns:
            bool: True if real-time feed started successfully, False if there were errors
                such as connection failures or subscription issues.

        Raises:
            Exception: Any exceptions during setup are caught and logged, returning False.

        Example:
            ```python
            # Initialize data manager first
            await data_manager.initialize(initial_days=10)

            # Start the real-time feed
            if await data_manager.start_realtime_feed():
                print("Real-time OHLCV updates active")

                # Register callback for new bars
                async def on_new_bar(data):
                    print(f"New {data['timeframe']} bar at {data['bar_time']}")

                await data_manager.add_callback("new_bar", on_new_bar)

                # Use the data in your trading loop
                while True:
                    current_price = await data_manager.get_current_price()
                    # Your trading logic here
                    await asyncio.sleep(1)
            else:
                print("Failed to start real-time feed")
            ```

        Note:
            - The initialize() method must be called successfully before calling this method,
              as it requires the contract_id to be set
            - This method is idempotent - calling it multiple times will only establish
              the connection once
            - The method sets up a background task for periodic memory cleanup to prevent
              excessive memory usage
        """
        with LogContext(
            self.logger,
            operation="start_realtime_feed",
            instrument=self.instrument,
            contract_id=self.contract_id,
        ):
            if self.is_running:
                self.logger.warning(
                    LogMessages.DATA_ERROR,
                    extra={"error": "Real-time feed already running"},
                )
                return True

            if not self.contract_id:
                raise ProjectXError(
                    format_error_message(
                        ErrorMessages.INTERNAL_ERROR,
                        reason="not initialized - call initialize() first",
                    )
                )

            # Check if realtime client is connected
            if not self.realtime_client.is_connected():
                raise ProjectXError(
                    format_error_message(
                        ErrorMessages.INTERNAL_ERROR,
                        reason="Realtime client not connected",
                    )
                )

            # Register callbacks first
            await self.realtime_client.add_callback(
                "quote_update", self._on_quote_update
            )
            await self.realtime_client.add_callback(
                "market_trade",
                self._on_trade_update,  # Use market_trade event name
            )

            # Subscribe to market data using the contract ID
            self.logger.debug(
                LogMessages.DATA_SUBSCRIBE, extra={"contract_id": self.contract_id}
            )
            subscription_success = await self.realtime_client.subscribe_market_data(
                [self.contract_id]
            )

            if not subscription_success:
                raise ProjectXError(
                    format_error_message(
                        ErrorMessages.WS_SUBSCRIPTION_FAILED,
                        channel="market data",
                        reason="Subscription returned False",
                    )
                )

            self.logger.debug(
                LogMessages.DATA_SUBSCRIBE,
                extra={"status": "success", "contract_id": self.contract_id},
            )

            self.is_running = True

            # Update statistics for successful connection
            await self.set_status("connected")
            await self.increment("realtime_connections", 1)
            await self.set_gauge("is_running", 1)

            # Start cleanup task
            self.start_cleanup_task()

            # Start bar timer task for low-volume periods
            self._start_bar_timer_task()

            # Start dynamic resource monitoring if enabled
            if self._enable_dynamic_limits:
                self.start_resource_monitoring()

            self.logger.debug(
                LogMessages.DATA_SUBSCRIBE,
                extra={"status": "feed_started", "instrument": self.instrument},
            )
            return True

    async def stop_realtime_feed(self) -> None:
        """
        Stop the real-time OHLCV data feed and cleanup resources.

        Example:
            >>> await manager.stop_realtime_feed()
        """
        try:
            if not self.is_running:
                return

            self.is_running = False

            # Cancel background tasks first
            await self.stop_cleanup_task()
            await self._stop_bar_timer_task()

            # Stop dynamic resource monitoring if enabled
            if self._enable_dynamic_limits:
                await self.stop_resource_monitoring()

            # Unsubscribe from market data and remove callbacks
            if self.contract_id:
                self.logger.info(f"📉 Unsubscribing from {self.contract_id}")
                # Unsubscribe from market data
                await self.realtime_client.unsubscribe_market_data([self.contract_id])

                # Remove callbacks
                await self.realtime_client.remove_callback(
                    "quote_update", self._on_quote_update
                )
                await self.realtime_client.remove_callback(
                    "market_trade", self._on_trade_update
                )

            self.logger.info(f"✅ Real-time feed stopped for {self.instrument}")

        except Exception as e:
            self.logger.error(f"❌ Error stopping real-time feed: {e}")

    async def cleanup(self) -> None:
        """
        Clean up resources when shutting down.

        Example:
            >>> await manager.cleanup()
        """
        await self.stop_realtime_feed()

        # Cleanup bounded statistics if enabled
        if self.use_bounded_statistics:
            try:
                await self.cleanup_bounded_statistics()
            except Exception as e:
                self.logger.error(f"Error cleaning up bounded statistics: {e}")

        # Handle both Lock and AsyncRWLock types
        if isinstance(self.data_lock, AsyncRWLock):
            async with self.data_lock.write_lock():
                self.data.clear()
                self.current_tick_data.clear()
                # EventBus handles all event cleanup
                self.indicator_cache.clear()
        else:
            async with self.data_lock:
                self.data.clear()
                self.current_tick_data.clear()
                # EventBus handles all event cleanup
                self.indicator_cache.clear()

        # Backward-compatible attributes used in some tests/examples
        # Clear these regardless of lock type
        # Use dynamic attribute access safely without type checker complaints
        bars_attr = getattr(self, "bars", None)
        if isinstance(bars_attr, dict):
            for _tf in list(bars_attr.keys()):
                bars_attr[_tf] = []
        ticks_attr = getattr(self, "ticks", None)
        if isinstance(ticks_attr, list):
            ticks_attr.clear()
        dom_attr = getattr(self, "dom_data", None)
        if isinstance(dom_attr, dict):
            for _k in list(dom_attr.keys()):
                dom_attr[_k] = []

        # Mark as not initialized
        self._initialized = False

        self.logger.info("✅ RealtimeDataManager cleanup completed")

    def _start_bar_timer_task(self) -> None:
        """Start the bar timer task for creating bars during low-volume periods."""
        if self._bar_timer_task is None or self._bar_timer_task.done():
            self._bar_timer_task = asyncio.create_task(self._bar_timer_loop())
            self.logger.debug("Bar timer task started")

    async def _stop_bar_timer_task(self) -> None:
        """Stop the bar timer task."""
        if self._bar_timer_task and not self._bar_timer_task.done():
            self._bar_timer_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._bar_timer_task
            self.logger.debug("Bar timer task stopped")

    async def _bar_timer_loop(self) -> None:
        """
        Periodic task to create empty bars during low-volume periods.

        This ensures bars are created at regular intervals even when
        there's no trading activity (important for low-volume instruments).
        """
        try:
            # Find the shortest timeframe interval to check
            min_seconds = float("inf")
            for tf_config in self.timeframes.values():
                interval = tf_config["interval"]
                unit = tf_config["unit"]

                # Convert to seconds based on numeric unit value
                # Unit mapping: {1: seconds, 2: minutes, 4: days, 5: weeks, 6: months}
                unit_seconds_map = {
                    1: 1,  # seconds
                    2: 60,  # minutes
                    4: 86400,  # days
                    5: 604800,  # weeks
                    6: 2629746,  # months (approximate)
                }

                if unit in unit_seconds_map:
                    seconds = interval * unit_seconds_map[unit]
                else:
                    continue  # Skip unsupported units

                min_seconds = min(min_seconds, seconds)

            # Check at least every 5 seconds, but no more than the shortest interval
            check_interval = min(5.0, min_seconds / 3)

            self.logger.debug(f"Bar timer checking every {check_interval} seconds")

            while self.is_running:
                await asyncio.sleep(check_interval)

                # Check each timeframe for stale bars
                await self._check_and_create_empty_bars()

        except asyncio.CancelledError:
            self.logger.debug("Bar timer task cancelled")
            raise
        except Exception as e:
            self.logger.error(f"Error in bar timer loop: {e}")

    async def _check_and_create_empty_bars(self) -> None:
        """
        Check each timeframe and create empty bars if needed.

        This handles low-volume periods where no ticks are coming in,
        ensuring bars are still created at the proper intervals.
        """
        try:
            current_time = datetime.now(self.timezone)
            events_to_trigger = []

            # Handle both Lock and AsyncRWLock types
            if isinstance(self.data_lock, AsyncRWLock):
                async with self.data_lock.read_lock():
                    for tf_key, tf_config in self.timeframes.items():
                        if tf_key not in self.data:
                            continue

                        current_data = self.data[tf_key]
                        if current_data.height == 0:
                            continue

                        # Get the last bar time
                        last_bar_time = (
                            current_data.select(pl.col("timestamp")).tail(1).item()
                        )

                        try:
                            # Calculate what the current bar time should be
                            expected_bar_time = self._calculate_bar_time(
                                current_time, tf_config["interval"], tf_config["unit"]
                            )
                        except Exception as e:
                            self.logger.error(
                                f"Error calculating bar time for {tf_key}: {e}"
                            )
                            continue  # Skip this timeframe if calculation fails

                        # If we're missing bars, create empty ones
                        if expected_bar_time > last_bar_time:
                            # Get the last close price to use for empty bars
                            last_close = (
                                current_data.select(pl.col("close")).tail(1).item()
                            )

                            # Import here to avoid circular import
                            from project_x_py.order_manager.utils import (
                                align_price_to_tick,
                            )

                            # Align the last close price to tick size
                            aligned_close = align_price_to_tick(
                                last_close, self.tick_size
                            )

                            # Create empty bar with last close as OHLC, volume=0
                            # Using DataFrame constructor is efficient for single rows
                            new_bar = pl.DataFrame(
                                {
                                    "timestamp": [expected_bar_time],
                                    "open": [aligned_close],
                                    "high": [aligned_close],
                                    "low": [aligned_close],
                                    "close": [aligned_close],
                                    "volume": [0],  # Zero volume for empty bars
                                }
                            )

                            self.data[tf_key] = pl.concat([current_data, new_bar])
                            self.last_bar_times[tf_key] = expected_bar_time

                            self.logger.debug(
                                f"Created empty bar for {tf_key} at {expected_bar_time} "
                                f"(low volume period)"
                            )

                            # Prepare event to trigger
                            events_to_trigger.append(
                                {
                                    "timeframe": tf_key,
                                    "bar_time": expected_bar_time,
                                    "data": new_bar.to_dicts()[0],
                                }
                            )
            else:
                # Regular Lock - copy the same logic
                async with self.data_lock:
                    for tf_key, tf_config in self.timeframes.items():
                        if tf_key not in self.data:
                            continue

                        current_data = self.data[tf_key]
                        if current_data.height == 0:
                            continue

                        # Get the last bar time
                        last_bar_time = (
                            current_data.select(pl.col("timestamp")).tail(1).item()
                        )

                        try:
                            # Calculate what the current bar time should be
                            expected_bar_time = self._calculate_bar_time(
                                current_time, tf_config["interval"], tf_config["unit"]
                            )
                        except Exception as e:
                            self.logger.error(
                                f"Error calculating bar time for {tf_key}: {e}"
                            )
                            continue  # Skip this timeframe if calculation fails

                        # If we're missing bars, create empty ones
                        if expected_bar_time > last_bar_time:
                            # Get the last close price to use for empty bars
                            last_close = (
                                current_data.select(pl.col("close")).tail(1).item()
                            )

                            # Import here to avoid circular import
                            from project_x_py.order_manager.utils import (
                                align_price_to_tick,
                            )

                            # Align the last close price to tick size
                            aligned_close = align_price_to_tick(
                                last_close, self.tick_size
                            )

                            # Create empty bar with last close as OHLC, volume=0
                            # Using DataFrame constructor is efficient for single rows
                            new_bar = pl.DataFrame(
                                {
                                    "timestamp": [expected_bar_time],
                                    "open": [aligned_close],
                                    "high": [aligned_close],
                                    "low": [aligned_close],
                                    "close": [aligned_close],
                                    "volume": [0],  # Zero volume for empty bars
                                }
                            )

                            self.data[tf_key] = pl.concat([current_data, new_bar])
                            self.last_bar_times[tf_key] = expected_bar_time

                            self.logger.debug(
                                f"Created empty bar for {tf_key} at {expected_bar_time} "
                                f"(low volume period)"
                            )

                            # Prepare event to trigger
                            events_to_trigger.append(
                                {
                                    "timeframe": tf_key,
                                    "bar_time": expected_bar_time,
                                    "data": new_bar.to_dicts()[0],
                                }
                            )

            # Trigger events outside the lock (non-blocking)
            for event in events_to_trigger:
                # Store task reference to avoid warning (though we don't need to track it)
                _ = asyncio.create_task(self._trigger_callbacks("new_bar", event))

        except Exception as e:
            # Track error in new statistics system
            await self.track_error(e, "bar_timer_check")
            self.logger.error(f"Error checking/creating empty bars: {e}")
            # Don't re-raise - bar timer should continue even if one check fails

    async def track_tick_processed(self) -> None:
        """Track a tick being processed."""
        # Use bounded statistics if enabled, otherwise use base statistics
        if self.use_bounded_statistics:
            await self.increment_bounded("ticks_processed", 1)
        else:
            await self.increment("ticks_processed", 1)

        # Update legacy stats for backward compatibility
        self.memory_stats["ticks_processed"] += 1

    async def track_quote_processed(self) -> None:
        """Track a quote being processed."""
        # Use bounded statistics if enabled, otherwise use base statistics
        if self.use_bounded_statistics:
            await self.increment_bounded("quotes_processed", 1)
        else:
            await self.increment("quotes_processed", 1)

        # Update legacy stats for backward compatibility
        self.memory_stats["quotes_processed"] += 1

    async def track_trade_processed(self) -> None:
        """Track a trade being processed."""
        # Use bounded statistics if enabled, otherwise use base statistics
        if self.use_bounded_statistics:
            await self.increment_bounded("trades_processed", 1)
        else:
            await self.increment("trades_processed", 1)

        # Update legacy stats for backward compatibility
        self.memory_stats["trades_processed"] += 1

    async def track_bar_created(self, timeframe: str) -> None:
        """Track a bar being created for a specific timeframe."""
        # Use bounded statistics if enabled, otherwise use base statistics
        if self.use_bounded_statistics:
            await self.increment_bounded("bars_created", 1)
            await self.increment_bounded(f"bars_created_{timeframe}", 1)
        else:
            await self.increment("bars_created", 1)
            await self.increment(f"bars_created_{timeframe}", 1)

        # Update legacy stats for backward compatibility
        self.memory_stats["bars_processed"] += 1
        if timeframe in self.memory_stats["timeframe_stats"]:
            self.memory_stats["timeframe_stats"][timeframe]["bars"] += 1

    async def track_bar_updated(self, timeframe: str) -> None:
        """Track a bar being updated for a specific timeframe."""
        # Use bounded statistics if enabled, otherwise use base statistics
        if self.use_bounded_statistics:
            await self.increment_bounded("bars_updated", 1)
            await self.increment_bounded(f"bars_updated_{timeframe}", 1)
        else:
            await self.increment("bars_updated", 1)
            await self.increment(f"bars_updated_{timeframe}", 1)

        # Update legacy stats for backward compatibility
        if timeframe in self.memory_stats["timeframe_stats"]:
            self.memory_stats["timeframe_stats"][timeframe]["updates"] += 1

    async def track_data_latency(self, latency_ms: float) -> None:
        """Track data processing latency."""
        # Use bounded statistics if enabled, otherwise use base statistics
        if self.use_bounded_statistics:
            await self.record_timing_bounded("data_processing", latency_ms)
        else:
            await self.record_timing("data_processing", latency_ms)

        # Update legacy stats for backward compatibility
        self.memory_stats["data_latency_ms"] = latency_ms

    async def track_connection_interruption(self) -> None:
        """Track a connection interruption."""
        # Use bounded statistics if enabled, otherwise use base statistics
        if self.use_bounded_statistics:
            await self.increment_bounded("connection_interruptions", 1)
        else:
            await self.increment("connection_interruptions", 1)

        await self.set_status("disconnected")

        # Update legacy stats for backward compatibility
        self.memory_stats["connection_interruptions"] += 1

    async def track_recovery_attempt(self) -> None:
        """Track a recovery attempt."""
        # Use bounded statistics if enabled, otherwise use base statistics
        if self.use_bounded_statistics:
            await self.increment_bounded("recovery_attempts", 1)
        else:
            await self.increment("recovery_attempts", 1)

        # Update legacy stats for backward compatibility
        self.memory_stats["recovery_attempts"] += 1

    async def get_memory_usage(self) -> float:
        """Override BaseStatisticsTracker method to provide component-specific memory calculation."""
        base_memory = await super().get_memory_usage()

        # Add data manager specific memory calculations
        data_memory = 0.0
        tick_memory = 0.0

        # Calculate memory for stored bar data
        for _timeframe, df in self.data.items():
            if df is not None and not df.is_empty():
                # Rough estimate: 6 columns * 8 bytes * row count + overhead
                data_memory += (len(df) * 6 * 8) / (1024 * 1024)  # Convert to MB

        # Calculate memory for tick buffer
        if hasattr(self, "current_tick_data"):
            tick_count = len(self.current_tick_data)
            tick_memory = tick_count * 0.0001  # Rough estimate in MB

        total_memory = base_memory + data_memory + tick_memory

        # Update legacy stats for backward compatibility
        self.memory_stats["memory_usage_mb"] = total_memory

        return total_memory

    # Delegate statistics methods to composed _statistics object
    async def increment(self, metric: str, value: int | float = 1) -> None:
        """Increment a counter metric."""
        await super().increment(metric, value)

    async def set_gauge(self, metric: str, value: int | float | Decimal) -> None:
        """Set a gauge metric."""
        await super().set_gauge(metric, value)

    async def record_timing(self, operation: str, duration_ms: float) -> None:
        """Record timing information."""
        await super().record_timing(operation, duration_ms)

    async def track_error(
        self,
        error: Exception | str,
        context: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Track an error occurrence."""
        await super().track_error(
            error if isinstance(error, Exception) else Exception(error),
            context,
            details,
        )

    async def get_stats(self) -> ComponentStats:
        """Get current statistics."""
        return await super().get_stats()

    async def get_health_score(self) -> float:
        """Get health score."""
        return await super().get_health_score()

    async def set_status(self, status: str) -> None:
        """Set component status."""
        await super().set_status(status)

    async def get_bounded_statistics(self) -> dict[str, Any] | None:
        """
        Get bounded statistics if enabled.

        Returns:
            Dictionary with bounded statistics or None if not enabled
        """
        if not self.use_bounded_statistics:
            return None

        try:
            return await self.get_all_bounded_stats()
        except Exception as e:
            self.logger.error(f"Error getting bounded statistics: {e}")
            return None

    def is_bounded_statistics_enabled(self) -> bool:
        """Check if bounded statistics are enabled."""
        return self.use_bounded_statistics

    async def get_lock_optimization_stats(self) -> dict[str, Any]:
        """Get detailed lock optimization statistics."""
        stats = await super().get_lock_optimization_stats()

        # Add data manager specific lock stats
        if hasattr(self, "data_rw_lock"):
            data_lock_stats = await self.data_rw_lock.get_stats()
            stats["data_rw_lock"] = {
                "name": self.data_rw_lock.name,
                "total_acquisitions": data_lock_stats.total_acquisitions,
                "total_wait_time_ms": data_lock_stats.total_wait_time_ms,
                "max_wait_time_ms": data_lock_stats.max_wait_time_ms,
                "min_wait_time_ms": data_lock_stats.min_wait_time_ms,
                "concurrent_readers": data_lock_stats.concurrent_readers,
                "max_concurrent_readers": data_lock_stats.max_concurrent_readers,
                "timeouts": data_lock_stats.timeouts,
                "contentions": data_lock_stats.contentions,
                "current_reader_count": self.data_rw_lock.reader_count,
                "avg_wait_time_ms": (
                    data_lock_stats.total_wait_time_ms
                    / data_lock_stats.total_acquisitions
                    if data_lock_stats.total_acquisitions > 0
                    else 0.0
                ),
            }

        # Add tick buffer stats
        if hasattr(self, "tick_buffer"):
            stats["tick_buffer"] = self.tick_buffer.get_stats()

        return stats

    async def optimize_data_access_patterns(self) -> dict[str, Any]:
        """Analyze and optimize data access patterns based on usage."""
        optimization_results: dict[str, Any] = {
            "analysis": {},
            "optimizations_applied": list[str](),
            "performance_improvements": {},
        }

        # Analyze lock contention
        if hasattr(self, "data_rw_lock"):
            lock_stats = await self.data_rw_lock.get_stats()

            # Calculate metrics
            if lock_stats.total_acquisitions > 0:
                avg_wait = lock_stats.total_wait_time_ms / lock_stats.total_acquisitions
                contention_rate = (
                    lock_stats.contentions / lock_stats.total_acquisitions * 100
                )

                optimization_results["analysis"] = {
                    "avg_wait_time_ms": avg_wait,
                    "contention_rate_percent": contention_rate,
                    "max_concurrent_readers": lock_stats.max_concurrent_readers,
                    "timeout_rate_percent": (
                        lock_stats.timeouts / lock_stats.total_acquisitions * 100
                        if lock_stats.total_acquisitions > 0
                        else 0
                    ),
                }

                # Suggest optimizations
                if contention_rate > 10.0:  # >10% contention
                    optimization_results["optimizations_applied"].append(
                        "High contention detected - consider using lock-free operations for reads"
                    )

                if avg_wait > 5.0:  # >5ms average wait
                    optimization_results["optimizations_applied"].append(
                        "High wait times detected - consider fine-grained locking per timeframe"
                    )

                if lock_stats.max_concurrent_readers > 20:
                    optimization_results["optimizations_applied"].append(
                        "High reader concurrency - R/W lock is optimal for this pattern"
                    )
                    optimization_results["performance_improvements"]["parallelism"] = (
                        f"Allows {lock_stats.max_concurrent_readers} concurrent readers"
                    )

        return optimization_results
