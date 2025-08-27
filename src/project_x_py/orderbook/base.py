"""
Base async orderbook functionality for ProjectX.

Author: @TexasCoding
Date: 2025-08-02

Overview:
    Defines the core data structures and foundational async methods for the ProjectX
    orderbook system. Implements thread-safe storage, trade history, best price/spread
    tracking, and callback/event infrastructure for all higher-level analytics.

Key Features:
    - Thread-safe Polars DataFrame bid/ask storage
    - Recent trade history, spread, and tick size tracking
    - Price level refreshment for iceberg/cluster analysis
    - Async callback/event registration for orderbook events
    - Configurable memory management and cleanup
    - Real-time data validation and error handling
    - Comprehensive orderbook snapshot generation
    - Trade flow classification and statistics

Core Data Structures:
    - orderbook_bids/asks: Polars DataFrames for price level storage
    - recent_trades: Trade execution history with classification
    - price_level_history: Historical price level updates for analysis
    - best_bid/ask_history: Top-of-book price tracking
    - spread_history: Bid-ask spread monitoring
    - trade_flow_stats: Aggressive/passive trade classification

Example Usage:
    ```python
    # V3: Using OrderBookBase with EventBus
    from project_x_py.events import EventBus, EventType

    event_bus = EventBus()
    base = OrderBookBase("MNQ", event_bus)  # V3: EventBus required


    # V3: Register event handlers via EventBus
    @event_bus.on(EventType.TRADE_TICK)
    async def on_trade(data):
        print(
            f"Trade: {data['size']} @ {data['price']} ({data['side']})"
        )  # V3: actual field names


    @event_bus.on(EventType.MARKET_DEPTH_UPDATE)
    async def on_depth(data):
        print(f"Depth update: {len(data['bids'])} bids, {len(data['asks'])} asks")


    # Get orderbook snapshot
    snapshot = await base.get_orderbook_snapshot(levels=5)
    print(f"Best bid: {snapshot['best_bid']}, Best ask: {snapshot['best_ask']}")
    print(f"Spread: {snapshot['spread']}, Imbalance: {snapshot['imbalance']:.2%}")
    ```

See Also:
    - `orderbook.analytics.MarketAnalytics`
    - `orderbook.detection.OrderDetection`
    - `orderbook.memory.MemoryManager`
"""

import asyncio
import time
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import polars as pl
import pytz

if TYPE_CHECKING:
    from project_x_py.client import ProjectXBase

from project_x_py.exceptions import ProjectXError
from project_x_py.orderbook.memory import MemoryManager
from project_x_py.statistics.base import BaseStatisticsTracker
from project_x_py.types import (
    DEFAULT_TIMEZONE,
    CallbackType,
    DomType,
    MemoryConfig,
)
from project_x_py.types.config_types import OrderbookConfig
from project_x_py.types.market_data import (
    OrderbookSnapshot,
    PriceLevelDict,
)
from project_x_py.utils import (
    LogMessages,
    ProjectXLogger,
    handle_errors,
)
from project_x_py.utils.deprecation import deprecated

logger = ProjectXLogger.get_logger(__name__)


class OrderBookBase(BaseStatisticsTracker):
    """
    Base class for async orderbook with core functionality.

    This class implements the fundamental orderbook infrastructure including data
    structures for storing bid/ask levels, trade history, and related market data.
    It provides thread-safe operations through asyncio locks and establishes the
    foundation for the component-based architecture of the complete orderbook.

    Key responsibilities:
    1. Maintain bid and ask price level data in Polars DataFrames
    2. Track and store recent trades with side classification
    3. Calculate and monitor best bid/ask prices and spreads
    4. Provide thread-safe data access through locks
    5. Implement the callback registration system
    6. Support price level history tracking for advanced analytics
    7. Manage trade flow statistics and classification
    8. Handle real-time data validation and error recovery

    This base class is designed to be extended by the full OrderBook implementation,
    which adds specialized components for analytics, detection algorithms, and real-time
    data handling.

    Thread safety:
        All public methods acquire the appropriate locks before accessing shared data
        structures, making them safe to call from multiple asyncio tasks concurrently.

    Data Structures:
        - orderbook_bids/asks: Polars DataFrames storing price levels with volumes
        - recent_trades: Trade execution history with side classification
        - price_level_history: Historical updates for iceberg/cluster analysis
        - best_bid/ask_history: Top-of-book price tracking over time
        - spread_history: Bid-ask spread monitoring and statistics
        - trade_flow_stats: Aggressive/passive trade classification metrics

    Performance Characteristics:
        - Memory-efficient Polars DataFrame operations
        - Thread-safe concurrent access patterns
        - Real-time data processing capabilities
        - Automatic memory management integration
    """

    def __init__(
        self,
        instrument: str,
        event_bus: Any,
        project_x: "ProjectXBase | None" = None,
        timezone_str: str = DEFAULT_TIMEZONE,
        config: OrderbookConfig | None = None,
    ):
        """
        Initialize the async orderbook base.

        Args:
            instrument: Trading instrument symbol
            project_x: Optional ProjectX client for tick size lookup
            timezone_str: Timezone for timestamps (default: America/Chicago)
            config: Optional configuration for orderbook behavior
        """
        self.instrument = instrument
        self.project_x = project_x
        self.event_bus = event_bus  # Store the event bus for emitting events
        self.timezone = pytz.timezone(timezone_str)
        self.logger = ProjectXLogger.get_logger(__name__)
        # Initialize BaseStatisticsTracker with orderbook-specific component name
        BaseStatisticsTracker.__init__(self, f"orderbook_{instrument}")

        # Store configuration with defaults
        self.config = config or {}
        self._apply_config_defaults()

        # Cache instrument tick size during initialization
        self._tick_size: Decimal | None = None

        # Orderbook-specific statistics
        self._trades_processed = 0
        self._total_volume = 0
        self._largest_trade = 0
        self._bid_updates = 0
        self._ask_updates = 0
        self._spread_samples: list[float] = []
        self._pattern_detections = {
            "icebergs_detected": 0,
            "spoofing_alerts": 0,
            "unusual_patterns": 0,
        }
        self._data_quality = {
            "data_gaps": 0,
            "invalid_updates": 0,
            "duplicate_updates": 0,
        }
        self._last_update_time = 0.0
        self._update_frequency_counter = 0
        self._update_timestamps: list[float] = []

        # Async locks for thread-safe operations
        self.orderbook_lock = asyncio.Lock()
        self._callback_lock = asyncio.Lock()

        # Memory configuration (now uses config settings)
        self.memory_config = MemoryConfig(
            max_trades=self.max_trade_history,
            max_depth_entries=self.max_depth_levels,
        )
        self.memory_manager = MemoryManager(self, self.memory_config)

        # Level 2 orderbook storage with Polars DataFrames
        self.orderbook_bids: pl.DataFrame = pl.DataFrame(
            {
                "price": [],
                "volume": [],
                "timestamp": [],
            },
            schema={
                "price": pl.Float64,
                "volume": pl.Int64,
                "timestamp": pl.Datetime(time_zone=timezone_str),
            },
        )

        self.orderbook_asks: pl.DataFrame = pl.DataFrame(
            {
                "price": [],
                "volume": [],
                "timestamp": [],
            },
            schema={
                "price": pl.Float64,
                "volume": pl.Int64,
                "timestamp": pl.Datetime(time_zone=timezone_str),
            },
        )

        # Trade flow storage (Type 5 - actual executions)
        self.recent_trades: pl.DataFrame = pl.DataFrame(
            {
                "price": [],
                "volume": [],
                "timestamp": [],
                "side": [],  # "buy" or "sell" inferred from price movement
                "spread_at_trade": [],
                "mid_price_at_trade": [],
                "best_bid_at_trade": [],
                "best_ask_at_trade": [],
                "order_type": [],
            },
            schema={
                "price": pl.Float64,
                "volume": pl.Int64,
                "timestamp": pl.Datetime(time_zone=timezone_str),
                "side": pl.Utf8,
                "spread_at_trade": pl.Float64,
                "mid_price_at_trade": pl.Float64,
                "best_bid_at_trade": pl.Float64,
                "best_ask_at_trade": pl.Float64,
                "order_type": pl.Utf8,
            },
        )

        # Orderbook metadata
        self.last_orderbook_update: datetime | None = None
        self.last_level2_data: dict[str, Any] | None = None
        self.level2_update_count = 0

        # Order type statistics
        self.order_type_stats: dict[str, int] = defaultdict(int)

        # Callbacks for orderbook events
        # EventBus is now used for all event handling

        # Price level refresh history for advanced analytics with memory bounds
        # Using deque with maxlen to prevent unbounded memory growth
        from collections import deque

        self.price_level_history: dict[tuple[float, str], deque[dict[str, Any]]] = (
            defaultdict(
                lambda: deque(maxlen=1000)
            )  # Keep last 1000 updates per price level
        )
        self.max_price_levels_tracked = 10000  # Maximum number of price levels to track

        # Best bid/ask tracking
        self.best_bid_history: list[dict[str, Any]] = []
        self.best_ask_history: list[dict[str, Any]] = []
        self.spread_history: list[dict[str, Any]] = []

        # Support/resistance level tracking
        self.support_levels: list[dict[str, Any]] = []
        self.resistance_levels: list[dict[str, Any]] = []

        # Cumulative delta tracking
        self.cumulative_delta = 0
        # Use deque for automatic size management of delta history
        from collections import deque

        self.delta_history: deque[dict[str, Any]] = deque(maxlen=1000)

        # VWAP tracking
        self.vwap_numerator = 0.0
        self.vwap_denominator = 0
        self.session_start_time = datetime.now(self.timezone).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        # Market microstructure analytics
        self.trade_flow_stats: dict[str, int] = defaultdict(int)

    def _apply_config_defaults(self) -> None:
        """Apply default values for configuration options."""
        # Orderbook settings
        self.max_depth_levels = self.config.get("max_depth_levels", 100)
        self.max_trade_history = self.config.get("max_trade_history", 1000)
        self.enable_market_by_order = self.config.get("enable_market_by_order", False)
        self.enable_analytics = self.config.get("enable_analytics", True)
        self.enable_pattern_detection = self.config.get(
            "enable_pattern_detection", True
        )
        self.snapshot_interval_seconds = self.config.get("snapshot_interval_seconds", 1)
        self.memory_limit_mb = self.config.get("memory_limit_mb", 256)
        self.compression_level = self.config.get("compression_level", 1)
        self.enable_delta_updates = self.config.get("enable_delta_updates", True)
        self.price_precision = self.config.get("price_precision", 4)

    def _map_trade_type(self, type_code: int) -> str:
        """Map ProjectX DomType codes to human-readable trade types."""
        try:
            return DomType(type_code).name
        except ValueError:
            return f"Unknown_{type_code}"

    @handle_errors("get tick size", reraise=False, default_return=Decimal("0.01"))
    async def get_tick_size(self) -> Decimal:
        """Get the tick size for the instrument."""
        if self._tick_size is None and self.project_x:
            contract_details = await self.project_x.get_instrument(self.instrument)
            if contract_details and hasattr(contract_details, "tickSize"):
                self._tick_size = Decimal(str(contract_details.tickSize))
            else:
                self._tick_size = Decimal("0.01")  # Default fallback
        return self._tick_size or Decimal("0.01")

    def _get_best_bid_ask_unlocked(self) -> dict[str, Any]:
        """
        Internal method to get best bid/ask without acquiring lock.
        Must be called with orderbook_lock already held.
        """
        try:
            best_bid = None
            best_ask = None

            # Get best bid (highest price) - optimized with chaining
            if self.orderbook_bids.height > 0:
                bid_with_volume = (
                    self.orderbook_bids.filter(pl.col("volume") > 0)
                    .sort("price", descending=True)
                    .head(1)
                )
                if bid_with_volume.height > 0:
                    best_bid = float(bid_with_volume["price"][0])

            # Get best ask (lowest price) - optimized with chaining
            if self.orderbook_asks.height > 0:
                ask_with_volume = (
                    self.orderbook_asks.filter(pl.col("volume") > 0)
                    .sort("price", descending=False)
                    .head(1)
                )
                if ask_with_volume.height > 0:
                    best_ask = float(ask_with_volume["price"][0])

            # Calculate spread and mid price
            spread = None
            mid_price = None
            if best_bid is not None and best_ask is not None:
                spread = best_ask - best_bid
                mid_price = (best_bid + best_ask) / 2

            # Update history
            current_time = datetime.now(self.timezone)
            if best_bid is not None:
                self.best_bid_history.append(
                    {
                        "price": best_bid,
                        "timestamp": current_time,
                    }
                )

            if best_ask is not None:
                self.best_ask_history.append(
                    {
                        "price": best_ask,
                        "timestamp": current_time,
                    }
                )

            if spread is not None:
                self.spread_history.append(
                    {
                        "spread": spread,
                        "timestamp": current_time,
                        "bid": best_bid,
                        "ask": best_ask,
                    }
                )

            return {
                "bid": best_bid,
                "ask": best_ask,
                "spread": spread,
                "mid_price": mid_price,
                "timestamp": current_time,
            }

        except Exception as e:
            self.logger.error(
                LogMessages.DATA_ERROR,
                extra={"operation": "get_best_bid_ask", "error": str(e)},
            )
            return {
                "bid": None,
                "ask": None,
                "spread": None,
                "mid_price": None,
                "timestamp": None,
            }

    @handle_errors(
        "get best bid/ask",
        reraise=False,
        default_return={
            "bid": None,
            "ask": None,
            "spread": None,
            "mid_price": None,
            "timestamp": None,
        },
    )
    async def get_best_bid_ask(self) -> dict[str, Any]:
        """
        Get current best bid and ask prices with spread calculation.

        This method provides the current top-of-book information, including the best
        (highest) bid price, best (lowest) ask price, the calculated spread between
        them, and the timestamp of the calculation. It also updates internal history
        tracking for bid, ask, and spread values.

        The method is thread-safe and acquires the orderbook lock before accessing
        the underlying data structures.

        Returns:
            Dict containing:
                bid: The highest bid price (float or None if no bids)
                ask: The lowest ask price (float or None if no asks)
                spread: The difference between ask and bid (float or None if either missing)
                mid_price: The midpoint between bid and ask ((bid + ask) / 2, or None if either missing)
                timestamp: The time of calculation (datetime)

        Example:
            >>> # V3: Get best bid/ask with spread
            >>> prices = await orderbook.get_best_bid_ask()
            >>> if prices["bid"] is not None and prices["ask"] is not None:
            ...     print(
            ...         f"Bid: {prices['bid']:.2f}, Ask: {prices['ask']:.2f}, "
            ...         f"Spread: {prices['spread']:.2f} ticks"
            ...     )
            ...     # V3: Calculate mid price
            ...     mid = (prices["bid"] + prices["ask"]) / 2
            ...     print(f"Mid price: {mid:.2f}")
            ... else:
            ...     print("Incomplete market data")
        """
        async with self.orderbook_lock:
            return self._get_best_bid_ask_unlocked()

    @handle_errors("get bid-ask spread", reraise=False, default_return=None)
    async def get_bid_ask_spread(self) -> float | None:
        """Get the current bid-ask spread."""
        best_prices = await self.get_best_bid_ask()
        return best_prices.get("spread")

    def _get_orderbook_bids_unlocked(self, levels: int = 10) -> pl.DataFrame:
        """Internal method to get orderbook bids without acquiring lock."""
        try:
            if self.orderbook_bids.height == 0:
                return pl.DataFrame(
                    {"price": [], "volume": [], "timestamp": []},
                    schema={
                        "price": pl.Float64,
                        "volume": pl.Int64,
                        "timestamp": pl.Datetime(time_zone=self.timezone.zone),
                    },
                )

            # Get top N bid levels by price - optimized chaining
            return (
                self.orderbook_bids.lazy()  # Use lazy evaluation for better performance
                .filter(pl.col("volume") > 0)
                .sort("price", descending=True)
                .head(levels)
                .collect()
            )
        except Exception as e:
            self.logger.error(
                LogMessages.DATA_ERROR,
                extra={"operation": "get_orderbook_bids", "error": str(e)},
            )
            return pl.DataFrame()

    @handle_errors("get orderbook bids", reraise=False, default_return=pl.DataFrame())
    async def get_orderbook_bids(self, levels: int = 10) -> pl.DataFrame:
        """Get orderbook bids up to specified levels."""
        async with self.orderbook_lock:
            return self._get_orderbook_bids_unlocked(levels)

    def _get_orderbook_asks_unlocked(self, levels: int = 10) -> pl.DataFrame:
        """Internal method to get orderbook asks without acquiring lock."""
        try:
            if self.orderbook_asks.height == 0:
                return pl.DataFrame(
                    {"price": [], "volume": [], "timestamp": []},
                    schema={
                        "price": pl.Float64,
                        "volume": pl.Int64,
                        "timestamp": pl.Datetime(time_zone=self.timezone.zone),
                    },
                )

            # Get top N ask levels by price - optimized chaining
            return (
                self.orderbook_asks.lazy()  # Use lazy evaluation for better performance
                .filter(pl.col("volume") > 0)
                .sort("price", descending=False)
                .head(levels)
                .collect()
            )
        except Exception as e:
            self.logger.error(
                LogMessages.DATA_ERROR,
                extra={"operation": "get_orderbook_asks", "error": str(e)},
            )
            return pl.DataFrame()

    @handle_errors("get orderbook asks", reraise=False, default_return=pl.DataFrame())
    async def get_orderbook_asks(self, levels: int = 10) -> pl.DataFrame:
        """Get orderbook asks up to specified levels."""
        async with self.orderbook_lock:
            return self._get_orderbook_asks_unlocked(levels)

    @handle_errors("get orderbook snapshot")
    async def get_orderbook_snapshot(self, levels: int = 10) -> OrderbookSnapshot:
        """
        Get a complete snapshot of the current orderbook state.

        This method provides a comprehensive snapshot of the current orderbook state,
        including top-of-book information, bid/ask levels, volume totals, and imbalance
        calculations. It's designed to give a complete picture of the market at a single
        point in time for analysis or display purposes.

        The snapshot includes:
        - Best bid and ask prices with spread
        - Mid-price calculation
        - Specified number of bid and ask levels with prices and volumes
        - Total volume on bid and ask sides
        - Order count on each side
        - Bid/ask imbalance ratio
        - Last update timestamp and update count

        The method is thread-safe and acquires the orderbook lock during execution.

        Args:
            levels: Number of price levels to include on each side (default: 10)

        Returns:
            Dict containing the complete orderbook snapshot with all the fields
            specified above. See OrderbookSnapshot type for details.

        Raises:
            ProjectXError: If an error occurs during snapshot generation

        Example:
            >>> # V3: Get full orderbook with 5 levels on each side
            >>> snapshot = await orderbook.get_orderbook_snapshot(levels=5)
            >>>
            >>> # V3: Print top of book with imbalance
            >>> print(
            ...     f"Best Bid: {snapshot['best_bid']:.2f} ({snapshot['total_bid_volume']} contracts)"
            ... )
            >>> print(
            ...     f"Best Ask: {snapshot['best_ask']:.2f} ({snapshot['total_ask_volume']} contracts)"
            ... )
            >>> print(
            ...     f"Spread: {snapshot['spread']:.2f}, Mid: {snapshot['mid_price']:.2f}"
            ... )
            >>> print(
            ...     f"Imbalance: {snapshot['imbalance']:.2%} ({'Bid Heavy' if snapshot['imbalance'] > 0 else 'Ask Heavy'})"
            ... )
            >>>
            >>> # V3: Display depth with cumulative volume
            >>> cumulative_bid = 0
            >>> print("\nBids:")
            >>> for bid in snapshot["bids"]:
            ...     cumulative_bid += bid["volume"]
            ...     print(
            ...         f"  {bid['price']:.2f}: {bid['volume']:5d} (cum: {cumulative_bid:6d})"
            ...     )
            >>>
            >>> cumulative_ask = 0
            >>> print("\nAsks:")
            >>> for ask in snapshot["asks"]:
            ...     cumulative_ask += ask["volume"]
            ...     print(
            ...         f"  {ask['price']:.2f}: {ask['volume']:5d} (cum: {cumulative_ask:6d})"
            ...     )
        """
        async with self.orderbook_lock:
            try:
                # Get best prices - use unlocked version since we already hold the lock
                best_prices = self._get_best_bid_ask_unlocked()

                # Get bid and ask levels - use unlocked versions
                bids = self._get_orderbook_bids_unlocked(levels)
                asks = self._get_orderbook_asks_unlocked(levels)

                # Convert to lists of PriceLevelDict
                bid_levels: list[PriceLevelDict] = (
                    [
                        {
                            "price": float(row["price"]),
                            "volume": int(row["volume"]),
                            "timestamp": row["timestamp"],
                        }
                        for row in bids.to_dicts()
                    ]
                    if not bids.is_empty()
                    else []
                )

                ask_levels: list[PriceLevelDict] = (
                    [
                        {
                            "price": float(row["price"]),
                            "volume": int(row["volume"]),
                            "timestamp": row["timestamp"],
                        }
                        for row in asks.to_dicts()
                    ]
                    if not asks.is_empty()
                    else []
                )

                # Calculate totals
                total_bid_volume = bids["volume"].sum() if not bids.is_empty() else 0
                total_ask_volume = asks["volume"].sum() if not asks.is_empty() else 0

                # Calculate imbalance
                imbalance = None
                if total_bid_volume > 0 or total_ask_volume > 0:
                    imbalance = (total_bid_volume - total_ask_volume) / (
                        total_bid_volume + total_ask_volume
                    )

                return {
                    "instrument": self.instrument,
                    "timestamp": datetime.now(self.timezone),
                    "best_bid": best_prices["bid"],
                    "best_ask": best_prices["ask"],
                    "spread": best_prices["spread"],
                    "mid_price": best_prices[
                        "mid_price"
                    ],  # Now available from get_best_bid_ask
                    "bids": bid_levels,
                    "asks": ask_levels,
                    "total_bid_volume": int(total_bid_volume),
                    "total_ask_volume": int(total_ask_volume),
                    "bid_count": len(bid_levels),
                    "ask_count": len(ask_levels),
                    "imbalance": imbalance,
                }

            except Exception as e:
                self.logger.error(
                    LogMessages.DATA_ERROR,
                    extra={"operation": "get_orderbook_snapshot", "error": str(e)},
                )
                raise ProjectXError(f"Failed to get orderbook snapshot: {e}") from e

    @handle_errors("get recent trades", reraise=False, default_return=[])
    async def get_recent_trades(self, count: int = 100) -> list[dict[str, Any]]:
        """Get recent trades from the orderbook."""
        async with self.orderbook_lock:
            try:
                if self.recent_trades.height == 0:
                    return []

                # Get most recent trades
                recent = self.recent_trades.tail(count)
                return recent.to_dicts()

            except Exception as e:
                self.logger.error(
                    LogMessages.DATA_ERROR,
                    extra={"operation": "get_recent_trades", "error": str(e)},
                )
                return []

    @handle_errors("get order type statistics", reraise=False, default_return={})
    async def get_order_type_statistics(self) -> dict[str, int]:
        """Get statistics about different order types processed."""
        async with self.orderbook_lock:
            return self.order_type_stats.copy()

    @deprecated(
        reason="Use TradingSuite.on() with EventType enum for event handling",
        version="3.1.0",
        removal_version="4.0.0",
        replacement="TradingSuite.on(EventType.MARKET_DEPTH_UPDATE, callback)",
    )
    @handle_errors("add callback", reraise=False)
    async def add_callback(self, event_type: str, callback: CallbackType) -> None:
        """
        Register a callback for orderbook events.

        This method allows client code to register callbacks that will be triggered when
        specific orderbook events occur. Callbacks can be either synchronous functions or
        asynchronous coroutines. When an event occurs, all registered callbacks for that
        event type will be executed with the event data.

        Supported event types:
        - "depth_update": Triggered when a price level is updated
        - "trade": Triggered when a new trade is processed
        - "best_bid_change": Triggered when the best bid price changes
        - "best_ask_change": Triggered when the best ask price changes
        - "spread_change": Triggered when the bid-ask spread changes
        - "reset": Triggered when the orderbook is reset

        Args:
            event_type: The type of event to listen for (from the list above)
            callback: A callable function or coroutine that will receive the event data.
                The callback should accept a single parameter: a dictionary containing
                the event data specific to that event type.

        Example:
            >>> # Use TradingSuite with EventBus for callbacks
            >>> from project_x_py import TradingSuite, EventType
            >>>
            >>> suite = await TradingSuite.create("MNQ", features=["orderbook"])
            >>>
            >>> @suite.events.on(EventType.TRADE_TICK)
            >>> async def on_trade(event):
            ...     data = event.data
            ...     print(f"Trade: {data['size']} @ {data['price']} ({data['side']})")
            >>>
            >>> @suite.events.on(EventType.MARKET_DEPTH_UPDATE)
            >>> async def on_depth_change(event):
            ...     data = event.data
            ...     print(
            ...         f"New best bid: {data['bids'][0]['price'] if data['bids'] else 'None'}"
            ...     )
            >>> # Events automatically flow through EventBus
        """
        async with self._callback_lock:
            # Deprecation warning handled by decorator
            logger.debug(
                LogMessages.CALLBACK_REGISTERED,
                extra={"event_type": event_type, "component": "orderbook"},
            )

    @deprecated(
        reason="Use TradingSuite.off() with EventType enum for event handling",
        version="3.1.0",
        removal_version="4.0.0",
        replacement="TradingSuite.off(EventType.MARKET_DEPTH_UPDATE, callback)",
    )
    @handle_errors("remove callback", reraise=False)
    async def remove_callback(self, event_type: str, callback: CallbackType) -> None:
        """Remove a registered callback."""
        async with self._callback_lock:
            # Deprecation warning handled by decorator
            logger.debug(
                LogMessages.CALLBACK_REMOVED,
                extra={"event_type": event_type, "component": "orderbook"},
            )

    async def _trigger_callbacks(self, event_type: str, data: dict[str, Any]) -> None:
        """
        Trigger all callbacks for a specific event type.

        This method executes all registered callbacks for a given event type,
        handling both synchronous and asynchronous callback functions. It
        ensures that callback failures don't prevent other callbacks from
        executing or affect the orderbook's operation.

        Args:
            event_type: The type of event that occurred (e.g., "trade", "depth_update")
            data: Event data to pass to the callbacks

        Note:
            Callback errors are logged but do not raise exceptions to prevent
            disrupting the orderbook's operation.
        """
        # Emit event through EventBus
        from project_x_py.event_bus import EventType

        # Map orderbook event types to EventType enum
        event_mapping = {
            "orderbook_update": EventType.ORDERBOOK_UPDATE,
            "market_depth": EventType.MARKET_DEPTH_UPDATE,
            "depth_update": EventType.MARKET_DEPTH_UPDATE,
            "quote_update": EventType.QUOTE_UPDATE,
            "trade": EventType.TRADE_TICK,
        }

        if event_type in event_mapping:
            await self.event_bus.emit(
                event_mapping[event_type], data, source="OrderBook"
            )

        # Legacy callbacks have been removed - use EventBus

    @handle_errors("cleanup", reraise=False)
    async def track_bid_update(self, levels: int = 1) -> None:
        """Track bid-side orderbook updates."""
        await self.increment("bid_updates", levels)
        self._bid_updates += levels
        await self._track_update_frequency()

    async def track_ask_update(self, levels: int = 1) -> None:
        """Track ask-side orderbook updates."""
        await self.increment("ask_updates", levels)
        self._ask_updates += levels
        await self._track_update_frequency()

    async def track_trade_processed(self, volume: int, price: float) -> None:
        """Track trade execution processing."""
        await self.increment("trades_processed", 1)
        await self.increment("total_volume", volume)
        self._trades_processed += 1
        self._total_volume += volume
        if volume > self._largest_trade:
            self._largest_trade = volume
            await self.set_gauge("largest_trade", volume)

    async def track_spread_sample(self, spread: float) -> None:
        """Track spread measurements for volatility calculation."""
        self._spread_samples.append(spread)
        # Keep only last 1000 samples to prevent memory growth
        if len(self._spread_samples) > 1000:
            self._spread_samples = self._spread_samples[-1000:]
        await self.set_gauge("current_spread", spread)

    async def track_pattern_detection(self, pattern_type: str) -> None:
        """Track pattern detection events."""
        if pattern_type in self._pattern_detections:
            self._pattern_detections[pattern_type] += 1
            await self.increment(pattern_type, 1)

    async def track_data_quality_issue(self, issue_type: str) -> None:
        """Track data quality issues."""
        if issue_type in self._data_quality:
            self._data_quality[issue_type] += 1
            await self.increment(issue_type, 1)

    async def _track_update_frequency(self) -> None:
        """Track orderbook update frequency."""
        current_time = time.time()
        self._update_timestamps.append(current_time)

        # Keep only last 60 seconds of timestamps
        cutoff_time = current_time - 60.0
        self._update_timestamps = [
            ts for ts in self._update_timestamps if ts > cutoff_time
        ]

        # Calculate updates per second
        if len(self._update_timestamps) > 1:
            time_span = self._update_timestamps[-1] - self._update_timestamps[0]
            if time_span > 0:
                frequency = len(self._update_timestamps) / time_span
                await self.set_gauge("update_frequency_per_second", frequency)

    async def get_orderbook_memory_usage(self) -> float:
        """Calculate orderbook-specific memory usage in MB."""
        base_memory = await self.get_memory_usage()

        # Add DataFrame memory estimates
        bids_memory = 0.0
        asks_memory = 0.0
        trades_memory = 0.0

        if self.orderbook_bids.height > 0:
            bids_memory = self.orderbook_bids.estimated_size("mb")
        if self.orderbook_asks.height > 0:
            asks_memory = self.orderbook_asks.estimated_size("mb")
        if self.recent_trades.height > 0:
            trades_memory = self.recent_trades.estimated_size("mb")

        # Add history memory estimates
        history_memory = (
            len(self.best_bid_history) * 0.0001  # ~0.1KB per entry
            + len(self.best_ask_history) * 0.0001
            + len(self.spread_history) * 0.0001
            + len(self.price_level_history) * 0.0005  # ~0.5KB per entry
            + len(self._spread_samples) * 0.00001  # ~0.01KB per float
            + len(self._update_timestamps) * 0.00001
        )

        return base_memory + bids_memory + asks_memory + trades_memory + history_memory

    async def get_memory_stats(self) -> dict[str, Any]:
        """
        Get comprehensive memory and statistics.

        Returns orderbook-specific statistics compatible with the collector expectations.
        """
        return await self._get_comprehensive_stats()

    def _get_basic_memory_stats(self) -> dict[str, Any]:
        """Get basic memory stats without async operations."""
        # Calculate basic DataFrame sizes
        bids_rows = self.orderbook_bids.height
        asks_rows = self.orderbook_asks.height
        trades_rows = self.recent_trades.height

        # Estimate memory usage (rough calculation)
        estimated_memory = (
            (bids_rows + asks_rows + trades_rows) * 0.0001  # ~0.1KB per row
            + len(self.best_bid_history) * 0.0001
            + len(self.best_ask_history) * 0.0001
            + len(self.spread_history) * 0.0001
            + 0.5  # Base overhead
        )

        return {
            "memory_usage_mb": round(estimated_memory, 2),
            "bids_count": bids_rows,
            "asks_count": asks_rows,
            "trades_processed": self._trades_processed,
            "total_volume": self._total_volume,
            "largest_trade": self._largest_trade,
            "avg_bid_depth": bids_rows,
            "avg_ask_depth": asks_rows,
            "max_bid_depth": bids_rows,
            "max_ask_depth": asks_rows,
            "avg_trade_size": self._total_volume / max(self._trades_processed, 1),
            "avg_spread": sum(self._spread_samples) / max(len(self._spread_samples), 1)
            if self._spread_samples
            else 0.0,
            "spread_volatility": self._calculate_spread_volatility(),
            "price_levels": bids_rows + asks_rows,
            "order_clustering": 0.0,  # Would need more complex calculation
            "icebergs_detected": self._pattern_detections["icebergs_detected"],
            "spoofing_alerts": self._pattern_detections["spoofing_alerts"],
            "unusual_patterns": self._pattern_detections["unusual_patterns"],
            "update_frequency_per_second": len(self._update_timestamps) / 60.0
            if self._update_timestamps
            else 0.0,
            "processing_latency_ms": 0.0,  # Would need timing measurements
            "data_gaps": self._data_quality["data_gaps"],
            "invalid_updates": self._data_quality["invalid_updates"],
            "duplicate_updates": self._data_quality["duplicate_updates"],
        }

    async def _get_comprehensive_stats(self) -> dict[str, Any]:
        """Get comprehensive statistics using async operations."""
        memory_usage = await self.get_orderbook_memory_usage()

        # Get current spread for volatility calculation
        spread_volatility = self._calculate_spread_volatility()

        # Calculate average trade size
        avg_trade_size = self._total_volume / max(self._trades_processed, 1)

        # Calculate average spread
        avg_spread = (
            sum(self._spread_samples) / max(len(self._spread_samples), 1)
            if self._spread_samples
            else 0.0
        )

        # Calculate update frequency
        update_frequency = 0.0
        if len(self._update_timestamps) > 1:
            time_span = self._update_timestamps[-1] - self._update_timestamps[0]
            if time_span > 0:
                update_frequency = len(self._update_timestamps) / time_span

        return {
            "memory_usage_mb": round(memory_usage, 2),
            "bids_count": self.orderbook_bids.height,
            "asks_count": self.orderbook_asks.height,
            "trades_processed": self._trades_processed,
            "total_volume": self._total_volume,
            "largest_trade": self._largest_trade,
            "avg_bid_depth": self.orderbook_bids.height,
            "avg_ask_depth": self.orderbook_asks.height,
            "max_bid_depth": self.orderbook_bids.height,
            "max_ask_depth": self.orderbook_asks.height,
            "avg_trade_size": round(avg_trade_size, 2),
            "avg_spread": round(avg_spread, 4),
            "spread_volatility": round(spread_volatility, 4),
            "price_levels": self.orderbook_bids.height + self.orderbook_asks.height,
            "order_clustering": 0.0,  # Would need more complex calculation
            "icebergs_detected": self._pattern_detections["icebergs_detected"],
            "spoofing_alerts": self._pattern_detections["spoofing_alerts"],
            "unusual_patterns": self._pattern_detections["unusual_patterns"],
            "update_frequency_per_second": round(update_frequency, 2),
            "processing_latency_ms": 0.0,  # Would need timing measurements
            "data_gaps": self._data_quality["data_gaps"],
            "invalid_updates": self._data_quality["invalid_updates"],
            "duplicate_updates": self._data_quality["duplicate_updates"],
        }

    def _calculate_spread_volatility(self) -> float:
        """Calculate spread volatility from recent samples."""
        if len(self._spread_samples) < 2:
            return 0.0

        mean_spread = sum(self._spread_samples) / len(self._spread_samples)
        variance = sum((x - mean_spread) ** 2 for x in self._spread_samples) / len(
            self._spread_samples
        )
        return float(variance**0.5)  # Standard deviation

    async def cleanup(self) -> None:
        """Clean up resources."""
        await self.memory_manager.stop()
        # EventBus handles all event cleanup
        logger.info(
            LogMessages.CLEANUP_COMPLETE,
            extra={"component": "OrderBook"},
        )
