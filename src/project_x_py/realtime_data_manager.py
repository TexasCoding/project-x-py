#!/usr/bin/env python3
"""
Real-time Data Manager for OHLCV Data

Author: TexasCoding
Date: June 2025

This module provides efficient real-time OHLCV data management by:
1. Loading initial historical data for all timeframes once at startup
2. Receiving real-time market data from ProjectX WebSocket feeds
3. Resampling real-time data into multiple timeframes (5s, 15s, 1m, 5m, 15m, 1h, 4h)
4. Maintaining synchronized OHLCV bars across all timeframes
5. Eliminating the need for repeated API calls during live trading

Key Benefits:
- 95% reduction in API calls (from every 5 minutes to once at startup)
- Sub-second data updates vs 5-minute polling delays
- Perfect synchronization between timeframes
- Resilient to API outages during trading
- Clean separation from orderbook functionality

Architecture:
- Accepts ProjectXRealtimeClient instance (dependency injection)
- Registers callbacks for real-time price updates
- Focuses solely on OHLCV bar management
- Thread-safe operations for concurrent access
"""

import asyncio
import contextlib
import gc
import logging
import threading
import time
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime
from typing import Any

import polars as pl
import pytz

from project_x_py import ProjectX
from project_x_py.realtime import ProjectXRealtimeClient


class ProjectXRealtimeDataManager:
    """
    Optimized real-time OHLCV data manager for efficient multi-timeframe trading data.

    This class focuses exclusively on OHLCV (Open, High, Low, Close, Volume) data management
    across multiple timeframes through real-time tick processing. Orderbook functionality
    is handled by the separate OrderBook class.

    Core Concept:
        Traditional approach: Poll API every 5 minutes for each timeframe = 20+ API calls/hour
        Real-time approach: Load historical once + live tick processing = 1 API call + WebSocket

        Result: 95% reduction in API calls with sub-second data freshness

    Architecture:
        1. Initial Load: Fetches comprehensive historical OHLCV data for all timeframes once
        2. Real-time Feed: Receives live market data via injected ProjectXRealtimeClient
        3. Tick Processing: Updates all timeframes simultaneously from each price tick
        4. Data Synchronization: Maintains perfect alignment across timeframes
        5. Memory Management: Automatic cleanup with configurable limits

    Supported Timeframes:
        - 5 seconds: High-frequency scalping
        - 15 seconds: Short-term momentum
        - 1 minute: Quick entries
        - 5 minutes: Primary timeframe for entry signals
        - 15 minutes: Trend confirmation and filtering
        - 1 hour: Intermediate trend analysis
        - 4 hours: Long-term trend and bias

    Features:
        - Zero-latency OHLCV updates via WebSocket
        - Automatic bar creation and maintenance
        - Thread-safe multi-timeframe access
        - Memory-efficient sliding window storage
        - Timezone-aware timestamp handling (CME Central Time)
        - Event callbacks for new bars and data updates
        - Comprehensive health monitoring and statistics
        - Dependency injection for realtime client

    Data Flow:
        Market Tick → Realtime Client → Data Manager → Timeframe Update → Callbacks

    Benefits:
        - Real-time strategy execution with fresh OHLCV data
        - Eliminated polling delays and timing gaps
        - Reduced API rate limiting concerns
        - Improved strategy performance through instant signals
        - Clean separation from orderbook functionality
        - Single WebSocket connection shared across components

    Memory Management:
        - Maintains last 1000 bars per timeframe (~3.5 days of 5min data)
        - Automatic cleanup of old data to prevent memory growth
        - Efficient DataFrame operations with copy-on-write
        - Thread-safe data access with RLock synchronization

    Example Usage:
        >>> # Create shared realtime client
        >>> realtime_client = ProjectXRealtimeClient(jwt_token, account_id)
        >>> realtime_client.connect()
        >>>
        >>> # Initialize data manager with dependency injection
        >>> manager = ProjectXRealtimeDataManager("MGC", project_x, realtime_client)
        >>>
        >>> # Load historical data for all timeframes
        >>> if manager.initialize(initial_days=30):
        ...     print("Historical data loaded successfully")
        >>>
        >>> # Start real-time feed (registers callbacks with existing client)
        >>> if manager.start_realtime_feed():
        ...     print("Real-time OHLCV feed active")
        >>>
        >>> # Access multi-timeframe OHLCV data
        >>> data_5m = manager.get_data("5min", bars=100)
        >>> data_15m = manager.get_data("15min", bars=50)
        >>> mtf_data = manager.get_mtf_data()
        >>>
        >>> # Get current market price
        >>> current_price = manager.get_current_price()

    Thread Safety:
        - All public methods are thread-safe
        - RLock protection for data structures
        - Safe concurrent access from multiple strategies
        - Atomic operations for data updates

    Performance:
        - Sub-second OHLCV updates vs 5+ minute polling
        - Minimal CPU overhead with efficient resampling
        - Memory-efficient storage with automatic cleanup
        - Optimized for high-frequency trading applications
        - Single WebSocket connection for multiple consumers
    """

    def __init__(
        self,
        instrument: str,
        project_x: ProjectX,
        realtime_client: ProjectXRealtimeClient,
        timeframes: list[str] | None = None,
        timezone: str = "America/Chicago",
    ):
        """
        Initialize the real-time OHLCV data manager.

        Args:
            instrument: Trading instrument (e.g., "MGC", "MNQ")
            project_x: ProjectX client for initial data loading
            realtime_client: ProjectXRealtimeClient instance for real-time data
            timeframes: List of timeframes to track (default: ["5min"])
            timezone: Timezone for timestamp handling (default: "America/Chicago")
        """
        if timeframes is None:
            timeframes = ["5min"]

        self.instrument = instrument
        self.project_x = project_x
        self.realtime_client = realtime_client

        self.logger = logging.getLogger(__name__)

        # Set timezone for consistent timestamp handling
        self.timezone = pytz.timezone(timezone)  # CME timezone

        timeframes_dict = {
            "1sec": {"interval": 1, "unit": 1, "name": "1sec"},
            "5sec": {"interval": 5, "unit": 1, "name": "5sec"},
            "10sec": {"interval": 10, "unit": 1, "name": "10sec"},
            "15sec": {"interval": 15, "unit": 1, "name": "15sec"},
            "30sec": {"interval": 30, "unit": 1, "name": "30sec"},
            "1min": {"interval": 1, "unit": 2, "name": "1min"},
            "5min": {"interval": 5, "unit": 2, "name": "5min"},
            "15min": {"interval": 15, "unit": 2, "name": "15min"},
            "30min": {"interval": 30, "unit": 2, "name": "30min"},
            "1hr": {"interval": 60, "unit": 3, "name": "1hr"},
            "4hr": {"interval": 240, "unit": 3, "name": "4hr"},
            "1day": {"interval": 1, "unit": 4, "name": "1day"},
            "1week": {"interval": 1, "unit": 5, "name": "1week"},
            "1month": {"interval": 1, "unit": 6, "name": "1month"},
        }

        # Initialize timeframes as dict mapping timeframe names to configs
        self.timeframes = {}
        for tf in timeframes:
            if tf not in timeframes_dict:
                raise ValueError(
                    f"Invalid timeframe: {tf}, valid timeframes are: {list(timeframes_dict.keys())}"
                )
            self.timeframes[tf] = timeframes_dict[tf]

        # OHLCV data storage for each timeframe
        self.data: dict[str, pl.DataFrame] = {}

        # Real-time data components
        self.current_tick_data: list[dict] = []
        self.last_bar_times: dict[
            str, datetime
        ] = {}  # Track last bar time for each timeframe

        # Threading and synchronization
        self.data_lock = threading.RLock()
        self.is_running = False
        self.callbacks: dict[str, list[Callable]] = defaultdict(list)
        self.background_tasks: set[asyncio.Task] = set()
        self.indicator_cache: defaultdict[str, dict] = defaultdict(dict)

        # Store reference to main event loop for async callback execution from threads
        self.main_loop = None
        with contextlib.suppress(RuntimeError):
            self.main_loop = asyncio.get_running_loop()

        # Contract ID for real-time subscriptions
        self.contract_id: str | None = None

        # Memory management settings
        self.max_bars_per_timeframe = 1000  # Keep last 1000 bars per timeframe
        self.tick_buffer_size = 1000  # Max tick data to buffer
        self.cleanup_interval = 300  # 5 minutes between cleanups
        self.last_cleanup = time.time()

        # Performance monitoring
        self.memory_stats = {
            "total_bars": 0,
            "bars_cleaned": 0,
            "ticks_processed": 0,
            "last_cleanup": time.time(),
        }

        self.logger.info(f"RealtimeDataManager initialized for {instrument}")

    def _cleanup_old_data(self) -> None:
        """
        Clean up old OHLCV data to manage memory efficiently using sliding windows.
        """
        current_time = time.time()

        # Only cleanup if interval has passed
        if current_time - self.last_cleanup < self.cleanup_interval:
            return

        with self.data_lock:
            total_bars_before = 0
            total_bars_after = 0

            # Cleanup each timeframe's data
            for tf_key in self.timeframes:
                if tf_key in self.data and not self.data[tf_key].is_empty():
                    initial_count = len(self.data[tf_key])
                    total_bars_before += initial_count

                    # Keep only the most recent bars (sliding window)
                    if initial_count > self.max_bars_per_timeframe:
                        self.data[tf_key] = self.data[tf_key].tail(
                            self.max_bars_per_timeframe // 2
                        )

                    total_bars_after += len(self.data[tf_key])

            # Cleanup tick buffer
            if len(self.current_tick_data) > self.tick_buffer_size:
                self.current_tick_data = self.current_tick_data[
                    -self.tick_buffer_size // 2 :
                ]

            # Update stats
            self.last_cleanup = current_time
            self.memory_stats["bars_cleaned"] += total_bars_before - total_bars_after
            self.memory_stats["total_bars"] = total_bars_after
            self.memory_stats["last_cleanup"] = current_time

            # Log cleanup if significant
            if total_bars_before != total_bars_after:
                self.logger.debug(
                    f"DataManager cleanup - Bars: {total_bars_before}→{total_bars_after}, "
                    f"Ticks: {len(self.current_tick_data)}"
                )

                # Force garbage collection after cleanup
                gc.collect()

    def get_memory_stats(self) -> dict:
        """
        Get current memory usage statistics.

        Returns:
            Dictionary with memory statistics
        """
        with self.data_lock:
            timeframe_stats = {}
            total_bars = 0

            for tf_key in self.timeframes:
                if tf_key in self.data:
                    bar_count = len(self.data[tf_key])
                    timeframe_stats[tf_key] = bar_count
                    total_bars += bar_count
                else:
                    timeframe_stats[tf_key] = 0

            return {
                "timeframe_bar_counts": timeframe_stats,
                "total_bars": total_bars,
                "tick_buffer_size": len(self.current_tick_data),
                "max_bars_per_timeframe": self.max_bars_per_timeframe,
                "max_tick_buffer": self.tick_buffer_size,
                **self.memory_stats,
            }

    def initialize(self, initial_days: int = 1) -> bool:
        """
        Initialize the data manager by loading historical OHLCV data for all timeframes.

        Args:
            initial_days: Number of days of historical data to load initially

        Returns:
            bool: True if initialization successful
        """
        try:
            self.logger.info(
                f"🔄 Initializing real-time OHLCV data manager for {self.instrument}..."
            )

            # Load historical data for each timeframe
            for tf_key, tf_config in self.timeframes.items():
                interval = tf_config["interval"]
                unit = tf_config["unit"]

                # Ensure minimum from initial_days parameter
                data_days = max(initial_days, initial_days)

                unit_name = "minute" if unit == 2 else "second"
                self.logger.info(
                    f"📊 Loading {data_days} days of {interval}-{unit_name} historical data..."
                )

                # Add timeout and retry logic for historical data loading
                data = None
                max_retries = 3

                for attempt in range(max_retries):
                    try:
                        self.logger.info(
                            f"🔄 Attempt {attempt + 1}/{max_retries} to load {self.instrument} {interval}-{unit_name} data..."
                        )

                        # Load historical OHLCV data
                        data = self.project_x.get_data(
                            instrument=self.instrument,
                            days=data_days,
                            interval=interval,
                            unit=unit,
                            partial=True,
                        )

                        if data is not None and len(data) > 0:
                            self.logger.info(
                                f"✅ Successfully loaded {self.instrument} {interval}-{unit_name} data on attempt {attempt + 1}"
                            )
                            break
                        else:
                            self.logger.warning(
                                f"⚠️ No data returned for {self.instrument} {interval}-{unit_name} (attempt {attempt + 1})"
                            )
                            if attempt < max_retries - 1:
                                self.logger.info("🔄 Retrying in 2 seconds...")
                                import time

                                time.sleep(2)
                            continue

                    except Exception as e:
                        self.logger.warning(
                            f"❌ Exception loading {self.instrument} {interval}-{unit_name} data: {e}"
                        )
                        if attempt < max_retries - 1:
                            self.logger.info("🔄 Retrying in 2 seconds...")
                            import time

                            time.sleep(2)
                        continue

                if data is not None and len(data) > 0:
                    with self.data_lock:
                        # Data is already a polars DataFrame from get_data()
                        data_copy = data

                        # Ensure timezone is handled properly
                        if "timestamp" in data_copy.columns:
                            timestamp_col = data_copy.get_column("timestamp")
                            if timestamp_col.dtype == pl.Datetime:
                                # Convert timezone if needed
                                data_copy = data_copy.with_columns(
                                    pl.col("timestamp")
                                    .dt.replace_time_zone("UTC")
                                    .dt.convert_time_zone(str(self.timezone.zone))
                                )

                        self.data[tf_key] = data_copy
                        if len(data_copy) > 0:
                            self.last_bar_times[tf_key] = (
                                data_copy.select(pl.col("timestamp")).tail(1).item()
                            )

                    self.logger.info(
                        f"✅ Loaded {len(data)} bars of {interval}-{unit_name} OHLCV data"
                    )
                else:
                    self.logger.error(
                        f"❌ Failed to load {interval}-{unit_name} historical data"
                    )
                    return False

            # Get contract ID for real-time subscriptions
            instrument_obj = self.project_x.get_instrument(self.instrument)
            if instrument_obj:
                self.contract_id = instrument_obj.id
                self.logger.info(f"📡 Contract ID: {self.contract_id}")
            else:
                self.logger.error(f"❌ Failed to get contract ID for {self.instrument}")
                return False

            self.logger.info("✅ Real-time OHLCV data manager initialization complete")
            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to initialize real-time data manager: {e}")
            return False

    def start_realtime_feed(self) -> bool:
        """
        Start the real-time OHLCV data feed by registering callbacks with the existing realtime client.

        Returns:
            bool: True if real-time feed started successfully
        """
        try:
            if not self.contract_id:
                self.logger.error("❌ Cannot start real-time feed: No contract ID")
                return False

            if not self.realtime_client:
                self.logger.error(
                    "❌ Cannot start real-time feed: No realtime client provided"
                )
                return False

            self.logger.info("🚀 Starting real-time OHLCV data feed...")

            # Register callbacks for real-time price updates
            self.realtime_client.add_callback("quote_update", self._on_quote_update)
            self.realtime_client.add_callback("market_trade", self._on_market_trade)

            self.logger.info("📊 OHLCV callbacks registered successfully")

            # Subscribe to market data for our contract (if not already subscribed)
            self.logger.info(
                f"📡 Ensuring subscription to market data for contract: {self.contract_id}"
            )

            # The realtime client should already be connected and subscribed
            # We just need to ensure our contract is in the subscription list
            success = self.realtime_client.subscribe_market_data([self.contract_id])
            if not success:
                self.logger.warning(
                    f"⚠️ Failed to subscribe to market data for {self.contract_id} (may already be subscribed)"
                )
                # Don't return False here as the subscription might already exist

            self.is_running = True
            self.logger.info("✅ Real-time OHLCV data feed started successfully")
            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to start real-time feed: {e}")
            return False

    def stop_realtime_feed(self):
        """Stop the real-time OHLCV data feed and clean up callbacks."""
        try:
            self.logger.info("🛑 Stopping real-time OHLCV data feed...")
            self.is_running = False

            # Remove our callbacks from the realtime client
            if self.realtime_client:
                self.realtime_client.remove_callback(
                    "quote_update", self._on_quote_update
                )
                self.realtime_client.remove_callback(
                    "market_trade", self._on_market_trade
                )

            self.logger.info("✅ Real-time OHLCV data feed stopped")

        except Exception as e:
            self.logger.error(f"❌ Error stopping real-time feed: {e}")

    def _on_quote_update(self, data: dict):
        """
        Handle real-time quote updates for OHLCV data processing.

        Args:
            data: Quote update data containing price information
        """
        try:
            contract_id = data.get("contract_id")
            quote_data = data.get("data", {})

            if contract_id != self.contract_id:
                return

            # Extract price information for OHLCV processing
            if isinstance(quote_data, dict):
                # Handle TopStepX field name variations
                current_bid = quote_data.get("bestBid") or quote_data.get("bid")
                current_ask = quote_data.get("bestAsk") or quote_data.get("ask")

                # Maintain quote state for handling partial updates
                if not hasattr(self, "_last_quote_state"):
                    self._last_quote_state: dict[str, float | None] = {
                        "bid": None,
                        "ask": None,
                    }

                # Update quote state with new data
                if current_bid is not None:
                    self._last_quote_state["bid"] = float(current_bid)
                if current_ask is not None:
                    self._last_quote_state["ask"] = float(current_ask)

                # Use most recent bid/ask values
                bid = self._last_quote_state["bid"]
                ask = self._last_quote_state["ask"]

                # Get last price for trade detection
                last_price = (
                    quote_data.get("lastPrice")
                    or quote_data.get("last")
                    or quote_data.get("price")
                )

                # Determine if this is a trade update or quote update
                is_trade_update = last_price is not None and "volume" in quote_data

                # Calculate price for OHLCV tick processing
                price = None
                volume = 0

                if is_trade_update and last_price is not None:
                    price = float(last_price)
                    volume = int(quote_data.get("volume", 0))
                elif bid is not None and ask is not None:
                    price = (bid + ask) / 2  # Mid price for quote updates
                    volume = 0  # No volume for quote updates
                elif bid is not None:
                    price = bid  # Use bid if only bid available
                    volume = 0
                elif ask is not None:
                    price = ask  # Use ask if only ask available
                    volume = 0

                if price is not None:
                    # Use timezone-aware timestamp
                    current_time = datetime.now(self.timezone)

                    # Create tick data for OHLCV processing
                    tick_data = {
                        "timestamp": current_time,
                        "price": float(price),
                        "volume": volume,
                        "type": "trade" if is_trade_update else "quote",
                    }

                    self._process_tick_data(tick_data)

        except Exception as e:
            self.logger.error(f"Error processing quote update for OHLCV: {e}")

    def _on_market_trade(self, data: dict) -> None:
        """
        Process market trade data for OHLCV updates.

        Args:
            data: Market trade data
        """
        try:
            contract_id = data.get("contract_id")
            if contract_id != self.contract_id:
                return

            trade_data = data.get("data", {})
            if isinstance(trade_data, dict):
                price = trade_data.get("price")
                volume = trade_data.get("volume", 0)

                if price is not None:
                    current_time = datetime.now(self.timezone)

                    tick_data = {
                        "timestamp": current_time,
                        "price": float(price),
                        "volume": int(volume),
                        "type": "trade",
                    }

                    self._process_tick_data(tick_data)

        except Exception as e:
            self.logger.error(f"❌ Error processing market trade for OHLCV: {e}")

    def _update_timeframe_data(
        self, tf_key: str, timestamp: datetime, price: float, volume: int
    ):
        """
        Update a specific timeframe with new tick data.

        Args:
            tf_key: Timeframe key (e.g., "5min", "15min", "1hr")
            timestamp: Timestamp of the tick
            price: Price of the tick
            volume: Volume of the tick
        """
        try:
            interval = self.timeframes[tf_key]["interval"]
            unit = self.timeframes[tf_key]["unit"]

            # Calculate the bar time for this timeframe
            bar_time = self._calculate_bar_time(timestamp, interval, unit)

            # Get current data for this timeframe
            if tf_key not in self.data:
                return

            current_data = self.data[tf_key].lazy()

            # Check if we need to create a new bar or update existing
            if current_data.collect().height == 0:
                # First bar - ensure minimum volume for pattern detection
                bar_volume = max(volume, 1) if volume > 0 else 1
                new_bar = pl.DataFrame(
                    {
                        "timestamp": [bar_time],
                        "open": [price],
                        "high": [price],
                        "low": [price],
                        "close": [price],
                        "volume": [bar_volume],
                    }
                ).lazy()

                self.data[tf_key] = new_bar.collect()
                self.last_bar_times[tf_key] = bar_time

            else:
                last_bar_time = (
                    current_data.select(pl.col("timestamp")).tail(1).collect().item()
                )

                if bar_time > last_bar_time:
                    # New bar needed
                    bar_volume = max(volume, 1) if volume > 0 else 1
                    new_bar = pl.DataFrame(
                        {
                            "timestamp": [bar_time],
                            "open": [price],
                            "high": [price],
                            "low": [price],
                            "close": [price],
                            "volume": [bar_volume],
                        }
                    ).lazy()

                    current_data = pl.concat([current_data, new_bar])

                    self.last_bar_times[tf_key] = bar_time

                    # Trigger new bar callback
                    self._trigger_callbacks(
                        "new_bar",
                        {
                            "timeframe": tf_key,
                            "bar_time": bar_time,
                            "data": new_bar.collect().to_dicts()[0],
                        },
                    )

                elif bar_time == last_bar_time:
                    # Update existing bar
                    last_row_mask = pl.col("timestamp") == pl.lit(bar_time)

                    # Get current values using collect
                    last_row = current_data.filter(last_row_mask).collect()
                    current_high = (
                        last_row.select(pl.col("high")).item()
                        if last_row.height > 0
                        else price
                    )
                    current_low = (
                        last_row.select(pl.col("low")).item()
                        if last_row.height > 0
                        else price
                    )
                    current_volume = (
                        last_row.select(pl.col("volume")).item()
                        if last_row.height > 0
                        else 0
                    )

                    # Calculate new values
                    new_high = max(current_high, price)
                    new_low = min(current_low, price)
                    new_volume = max(current_volume + volume, 1)

                    # Update lazily
                    current_data = current_data.with_columns(
                        [
                            pl.when(last_row_mask)
                            .then(pl.lit(new_high))
                            .otherwise(pl.col("high"))
                            .alias("high"),
                            pl.when(last_row_mask)
                            .then(pl.lit(new_low))
                            .otherwise(pl.col("low"))
                            .alias("low"),
                            pl.when(last_row_mask)
                            .then(pl.lit(price))
                            .otherwise(pl.col("close"))
                            .alias("close"),
                            pl.when(last_row_mask)
                            .then(pl.lit(new_volume))
                            .otherwise(pl.col("volume"))
                            .alias("volume"),
                        ]
                    )

            # Prune memory
            if current_data.collect().height > 1000:
                current_data = current_data.tail(1000)

            self.data[tf_key] = current_data.collect()

        except Exception as e:
            self.logger.error(f"Error updating {tf_key} timeframe: {e}")

    def _calculate_bar_time(
        self, timestamp: datetime, interval: int, unit: int
    ) -> datetime:
        """
        Calculate the bar time for a given timestamp and interval.

        Args:
            timestamp: The tick timestamp (should be timezone-aware)
            interval: Bar interval value
            unit: Time unit (1=seconds, 2=minutes)

        Returns:
            datetime: The bar time (start of the bar period) - timezone-aware
        """
        # Ensure timestamp is timezone-aware
        if timestamp.tzinfo is None:
            timestamp = self.timezone.localize(timestamp)

        if unit == 1:  # Seconds
            # Round down to the nearest interval in seconds
            total_seconds = timestamp.second + timestamp.microsecond / 1000000
            rounded_seconds = (int(total_seconds) // interval) * interval
            bar_time = timestamp.replace(second=rounded_seconds, microsecond=0)
        elif unit == 2:  # Minutes
            # Round down to the nearest interval in minutes
            minutes = (timestamp.minute // interval) * interval
            bar_time = timestamp.replace(minute=minutes, second=0, microsecond=0)
        else:
            raise ValueError(f"Unsupported time unit: {unit}")

        return bar_time

    def _process_tick_data(self, tick: dict):
        """
        Process incoming tick data and update all OHLCV timeframes.

        Args:
            tick: Dictionary containing tick data (timestamp, price, volume, etc.)
        """
        try:
            if not self.is_running:
                return

            timestamp = tick["timestamp"]
            price = tick["price"]
            volume = tick.get("volume", 0)

            # Update each timeframe
            with self.data_lock:
                for tf_key in self.timeframes:
                    self._update_timeframe_data(tf_key, timestamp, price, volume)

            # Trigger callbacks for data updates
            self._trigger_callbacks(
                "data_update",
                {"timestamp": timestamp, "price": price, "volume": volume},
            )

            # Update memory stats and periodic cleanup
            self.memory_stats["ticks_processed"] += 1
            self._cleanup_old_data()

        except Exception as e:
            self.logger.error(f"Error processing tick data: {e}")

    def get_data(
        self, timeframe: str = "5min", bars: int | None = None
    ) -> pl.DataFrame | None:
        """
        Get OHLCV data for a specific timeframe.

        Args:
            timeframe: Timeframe key ("15sec", "1min", "5min", "15min")
            bars: Number of recent bars to return (None for all)

        Returns:
            pl.DataFrame: OHLCV data for the timeframe
        """
        try:
            with self.data_lock:
                if timeframe not in self.data:
                    self.logger.warning(f"No data available for timeframe {timeframe}")
                    return None

                data = self.data[timeframe].clone()

                if bars and len(data) > bars:
                    data = data.tail(bars)

                return data

        except Exception as e:
            self.logger.error(f"Error getting data for timeframe {timeframe}: {e}")
            return None

    def get_data_with_indicators(
        self,
        timeframe: str = "5min",
        bars: int | None = None,
        indicators: list[str] | None = None,
    ) -> pl.DataFrame | None:
        """Get OHLCV data with optional computed indicators."""
        data = self.get_data(timeframe, bars)
        if data is None or indicators is None or not indicators:
            return data

        cache_key = f"{timeframe}_{bars}_" + "_".join(sorted(indicators))

        if cache_key in self.indicator_cache[timeframe]:
            return self.indicator_cache[timeframe][cache_key]

        # TODO: Implement indicator computation here or import from indicators module
        # For example:
        # computed = data.with_columns(pl.col("close").rolling_mean(20).alias("sma_20"))
        # self.indicator_cache[timeframe][cache_key] = computed
        # return computed
        return data  # Return without indicators for now

    def get_mtf_data(
        self, timeframes: list[str] | None = None, bars: int | None = None
    ) -> dict[str, pl.DataFrame]:
        """
        Get multi-timeframe OHLCV data.

        Args:
            timeframes: List of timeframes to return (None for all)
            bars: Number of recent bars per timeframe (None for all)

        Returns:
            dict: Dictionary mapping timeframe keys to OHLCV DataFrames
        """
        if timeframes is None:
            timeframes = list(self.timeframes.keys())

        mtf_data = {}

        for tf in timeframes:
            data = self.get_data(tf, bars)
            if data is not None and len(data) > 0:
                mtf_data[tf] = data

        return mtf_data

    def get_current_price(self) -> float | None:
        """Get the current market price from the most recent OHLCV data."""
        try:
            # Use the fastest timeframe available for current price
            fastest_tf = None
            for tf in ["5sec", "15sec", "30sec", "1min", "5min"]:
                if tf in self.timeframes:
                    fastest_tf = tf
                    break

            if fastest_tf:
                data = self.get_data(fastest_tf, bars=1)
                if data is not None and len(data) > 0:
                    return float(data.select(pl.col("close")).tail(1).item())

            return None

        except Exception as e:
            self.logger.error(f"Error getting current price: {e}")
            return None

    def add_callback(self, event_type: str, callback: Callable):
        """
        Add a callback for specific OHLCV events.

        Args:
            event_type: Type of event ('data_update', 'new_bar', etc.)
            callback: Callback function to execute
        """
        self.callbacks[event_type].append(callback)
        self.logger.debug(f"Added OHLCV callback for {event_type}")

    def remove_callback(self, event_type: str, callback: Callable):
        """Remove a callback for specific events."""
        if callback in self.callbacks[event_type]:
            self.callbacks[event_type].remove(callback)
            self.logger.debug(f"Removed OHLCV callback for {event_type}")

    def set_main_loop(self, loop=None):
        """Set the main event loop for async callback execution from threads."""
        if loop is None:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                self.logger.debug("No running event loop found when setting main loop")
                return
        self.main_loop = loop
        self.logger.debug("Main event loop set for async callback execution")

    def _trigger_callbacks(self, event_type: str, data: dict):
        """Trigger all callbacks for a specific event type, handling both sync and async callbacks."""
        for callback in self.callbacks[event_type]:
            try:
                if asyncio.iscoroutinefunction(callback):
                    # Handle async callback from thread context
                    if self.main_loop and not self.main_loop.is_closed():
                        # Schedule the coroutine in the main event loop from this thread
                        asyncio.run_coroutine_threadsafe(callback(data), self.main_loop)
                    else:
                        # Try to get current loop or use main_loop
                        try:
                            current_loop = asyncio.get_running_loop()
                            task = current_loop.create_task(callback(data))
                            self.background_tasks.add(task)
                            task.add_done_callback(self.background_tasks.discard)
                        except RuntimeError:
                            self.logger.warning(
                                f"⚠️ Cannot execute async {event_type} callback - no event loop available"
                            )
                            continue
                else:
                    # Handle sync callback normally
                    callback(data)
            except Exception as e:
                self.logger.error(f"Error in {event_type} callback: {e}")

    def get_statistics(self) -> dict:
        """Get statistics about the real-time OHLCV data manager."""
        stats: dict[str, Any] = {
            "is_running": self.is_running,
            "contract_id": self.contract_id,
            "instrument": self.instrument,
            "timeframes": {},
            "realtime_client_available": self.realtime_client is not None,
            "realtime_client_connected": self.realtime_client.is_connected()
            if self.realtime_client
            else False,
        }

        with self.data_lock:
            for tf_key in self.timeframes:
                if tf_key in self.data:
                    data = self.data[tf_key]
                    stats["timeframes"][tf_key] = {
                        "bars": len(data),
                        "latest_time": data.select(pl.col("timestamp")).tail(1).item()
                        if len(data) > 0
                        else None,
                        "latest_price": float(
                            data.select(pl.col("close")).tail(1).item()
                        )
                        if len(data) > 0
                        else None,
                    }

        return stats

    def health_check(self) -> bool:
        """
        Perform a health check on the real-time OHLCV data manager.

        Returns:
            bool: True if healthy, False if issues detected
        """
        try:
            # Check if running
            if not self.is_running:
                self.logger.warning("Health check: Real-time OHLCV feed not running")
                return False

            # Check realtime client connection
            if not self.realtime_client or not self.realtime_client.is_connected():
                self.logger.warning("Health check: Realtime client not connected")
                return False

            # Check if we have recent data
            current_time = datetime.now()

            with self.data_lock:
                for tf_key, data in self.data.items():
                    if len(data) == 0:
                        self.logger.warning(
                            f"Health check: No OHLCV data for timeframe {tf_key}"
                        )
                        return False

                    latest_time = data.select(pl.col("timestamp")).tail(1).item()
                    # Convert to datetime for comparison if needed
                    if hasattr(latest_time, "to_pydatetime"):
                        latest_time = latest_time.to_pydatetime()
                    elif hasattr(latest_time, "tz_localize"):
                        latest_time = latest_time.tz_localize(None)

                    time_diff = (current_time - latest_time).total_seconds()

                    # Calculate timeframe-aware staleness threshold
                    tf_config = self.timeframes.get(tf_key, {})
                    interval = tf_config.get("interval", 5)
                    unit = tf_config.get("unit", 2)  # 1=seconds, 2=minutes

                    if unit == 1:  # Seconds-based timeframes
                        max_age_seconds = interval * 4  # Allow 4x the interval
                    else:  # Minute-based timeframes
                        max_age_seconds = (
                            interval * 60 * 1.2 + 180
                        )  # 1.2x interval + 3min buffer

                    if time_diff > max_age_seconds:
                        self.logger.warning(
                            f"Health check: Stale OHLCV data for timeframe {tf_key} ({time_diff / 60:.1f} minutes old, threshold: {max_age_seconds / 60:.1f} minutes)"
                        )
                        return False

            return True

        except Exception as e:
            self.logger.error(f"Error in health check: {e}")
            return False

    def cleanup_old_data(self, max_bars_per_timeframe: int = 1000):
        """
        Clean up old OHLCV data to manage memory usage in long-running sessions.

        Args:
            max_bars_per_timeframe: Maximum number of bars to keep per timeframe
        """
        try:
            with self.data_lock:
                for tf_key in self.timeframes:
                    if (
                        tf_key in self.data
                        and len(self.data[tf_key]) > max_bars_per_timeframe
                    ):
                        old_length = len(self.data[tf_key])
                        self.data[tf_key] = self.data[tf_key].tail(
                            max_bars_per_timeframe
                        )
                        new_length = len(self.data[tf_key])

                        self.logger.debug(
                            f"Cleaned up {tf_key} OHLCV data: {old_length} -> {new_length} bars"
                        )

        except Exception as e:
            self.logger.error(f"Error cleaning up old OHLCV data: {e}")

    def force_data_refresh(self) -> bool:
        """
        Force a complete OHLCV data refresh by reloading historical data.
        Useful for recovery from data corruption or extended disconnections.

        Returns:
            bool: True if refresh successful
        """
        try:
            self.logger.info("🔄 Forcing complete OHLCV data refresh...")

            # Stop real-time feed temporarily
            was_running = self.is_running
            if was_running:
                self.stop_realtime_feed()

            # Clear existing data
            with self.data_lock:
                self.data.clear()
                self.last_bar_times.clear()

            # Reload historical data
            success = self.initialize()

            # Restart real-time feed if it was running
            if was_running and success:
                success = self.start_realtime_feed()

            if success:
                self.logger.info("✅ OHLCV data refresh completed successfully")
            else:
                self.logger.error("❌ OHLCV data refresh failed")

            return success

        except Exception as e:
            self.logger.error(f"❌ Error during OHLCV data refresh: {e}")
            return False
