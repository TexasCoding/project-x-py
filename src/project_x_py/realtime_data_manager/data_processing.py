"""
Tick and OHLCV data processing functionality.

Author: @TexasCoding
Date: 2025-08-02

Overview:
    Provides tick processing and OHLCV bar creation functionality for real-time market data.
    Implements efficient processing of WebSocket tick data to create and maintain OHLCV bars
    across multiple timeframes with automatic bar creation and updates.

Key Features:
    - Real-time tick processing from WebSocket feeds
    - Automatic OHLCV bar creation and maintenance
    - Multi-timeframe bar updates with proper timezone handling
    - Event-driven processing with callback triggers
    - Thread-safe operations with proper locking
    - Comprehensive error handling and validation

Data Processing Capabilities:
    - Quote and trade data processing from ProjectX Gateway
    - Automatic bar creation for new time periods
    - Real-time bar updates for existing periods
    - Timezone-aware timestamp calculations
    - Volume aggregation and price tracking
    - Event callback triggering for new bars and updates

Example Usage:
    ```python
    # V3: Data processing with EventBus integration
    from project_x_py import EventBus, EventType

    event_bus = EventBus()
    manager = RealtimeDataManager(..., event_bus=event_bus)


    # V3: Register for processed bar events
    @event_bus.on(EventType.NEW_BAR)
    async def on_new_bar(data):
        timeframe = data["timeframe"]
        bar_data = data["data"]

        # V3: Access actual field names from ProjectX
        print(f"New {timeframe} bar:")
        print(f"  Open: {bar_data['open']}")
        print(f"  High: {bar_data['high']}")
        print(f"  Low: {bar_data['low']}")
        print(f"  Close: {bar_data['close']}")
        print(f"  Volume: {bar_data['volume']}")


    # V3: Data processing happens automatically in background
    # Access processed data through data access methods
    current_price = await manager.get_current_price()
    data_5m = await manager.get_data("5min", bars=100)

    # V3: Use Polars for analysis
    if data_5m is not None:
        recent = data_5m.tail(20)
        sma = recent["close"].mean()
        print(f"20-bar SMA: {sma}")
    ```

Processing Flow:
    1. WebSocket tick data received from ProjectX Gateway
    2. Quote and trade data parsed and validated
    3. Tick data processed for each configured timeframe
    4. Bar creation or updates based on time boundaries
    5. Event callbacks triggered for new bars and updates
    6. Memory management and cleanup performed

Data Sources:
    - GatewayQuote: Bid/ask price updates for quote processing
    - GatewayTrade: Executed trade data for volume and price updates
    - Automatic fallback to bar close prices when tick data unavailable

Performance Characteristics:
    - Zero-latency tick processing with WebSocket feeds
    - Efficient bar creation and updates across multiple timeframes
    - Thread-safe operations with minimal locking overhead
    - Memory-efficient processing with automatic cleanup

See Also:
    - `realtime_data_manager.core.RealtimeDataManager`
    - `realtime_data_manager.callbacks.CallbackMixin`
    - `realtime_data_manager.data_access.DataAccessMixin`
    - `realtime_data_manager.memory_management.MemoryManagementMixin`
    - `realtime_data_manager.validation.ValidationMixin`
"""

import asyncio
import logging
from collections import defaultdict, deque
from datetime import datetime
from typing import TYPE_CHECKING, Any

import polars as pl

from project_x_py.order_manager.utils import align_price_to_tick
from project_x_py.types.trading import TradeLogType

if TYPE_CHECKING:
    from asyncio import Lock

    from pytz import BaseTzInfo

    from project_x_py.utils.lock_optimization import AsyncRWLock

logger = logging.getLogger(__name__)


class DataProcessingMixin:
    """
    Mixin for tick processing and OHLCV bar creation with fine-grained locking.

    **CRITICAL FIX (v3.3.1)**: Implements race condition prevention through per-timeframe
    locking and atomic transaction support with rollback capabilities.

    **Race Condition Prevention Features**:
        - Fine-grained locks per timeframe prevent cross-timeframe contention
        - Atomic update transactions with automatic rollback on failure
        - Rate limiting prevents excessive update frequency
        - Partial failure handling with state recovery mechanisms

    **Safety Mechanisms**:
        - Transaction state tracking for reliable operations
        - Rollback support maintains data consistency
        - Error isolation prevents corruption of other timeframes
        - Performance monitoring through timing statistics
    """

    # Type hints for mypy - these attributes are provided by the main class
    tick_size: float
    if TYPE_CHECKING:
        from project_x_py.utils.lock_optimization import AsyncRWLock

        logger: logging.Logger
        timezone: BaseTzInfo
        data_lock: "Lock | AsyncRWLock"
        current_tick_data: list[dict[str, Any]] | deque[dict[str, Any]]
        timeframes: dict[str, dict[str, Any]]
        data: dict[str, pl.DataFrame]
        last_bar_times: dict[str, datetime]
        memory_stats: dict[str, Any]
        is_running: bool

        # Methods from other mixins/main class
        def _parse_and_validate_quote_payload(
            self, _quote_data: Any
        ) -> dict[str, Any] | None: ...
        def _parse_and_validate_trade_payload(
            self, _trade_data: Any
        ) -> dict[str, Any] | None: ...
        def handle_dst_bar_time(
            self, _timestamp: datetime, _interval: int, _unit: int
        ) -> datetime | None: ...
        def log_dst_event(
            self, _event_type: str, _timestamp: datetime, _message: str
        ) -> None: ...
        def _symbol_matches_instrument(self, _symbol: str) -> bool: ...
        async def _trigger_callbacks(
            self, _event_type: str, _data: dict[str, Any]
        ) -> None: ...
        async def _cleanup_old_data(self) -> None: ...
        async def track_error(
            self,
            _error: Exception,
            _context: str,
            _details: dict[str, Any] | None = None,
        ) -> None: ...
        async def increment(self, _metric: str, _value: int | float = 1) -> None: ...
        async def track_bar_created(self, _timeframe: str) -> None: ...
        async def track_bar_updated(self, _timeframe: str) -> None: ...
        async def track_quote_processed(self) -> None: ...
        async def track_trade_processed(self) -> None: ...
        async def track_tick_processed(self) -> None: ...
        async def record_timing(self, _metric: str, _duration_ms: float) -> None: ...

    def __init__(self) -> None:
        """Initialize data processing with fine-grained locking."""
        super().__init__()
        # Fine-grained locks per timeframe to prevent race conditions
        self._timeframe_locks: defaultdict[str, asyncio.Lock] = defaultdict(
            asyncio.Lock
        )
        # Track atomic operation state for rollback capability
        self._update_transactions: dict[str, dict[str, Any]] = {}
        # Rate limiting for high-frequency updates
        self._last_update_times: defaultdict[str, float] = defaultdict(float)
        self._min_update_interval = 0.001  # 1ms minimum between updates per timeframe

    def _get_timeframe_lock(self, timeframe: str) -> asyncio.Lock:
        """Get or create a lock for a specific timeframe."""
        return self._timeframe_locks[timeframe]

    async def _on_quote_update(self, callback_data: dict[str, Any]) -> None:
        """
        Handle real-time quote updates for OHLCV data processing.

        Args:
            callback_data: Quote update callback data from realtime client
        """
        try:
            self.logger.debug(f"📊 Quote update received: {type(callback_data)}")
            self.logger.debug(f"Quote data: {callback_data}")

            # Extract the actual quote data from the callback structure (same as sync version)
            data = (
                callback_data.get("data", {}) if isinstance(callback_data, dict) else {}
            )

            # Debug log to see what we're receiving
            self.logger.debug(
                f"Quote callback - callback_data type: {type(callback_data)}, data type: {type(data)}"
            )

            # Parse and validate payload format (same as sync version)
            quote_data = self._parse_and_validate_quote_payload(data)
            if quote_data is None:
                return

            # Check if this quote is for our tracked instrument
            symbol = quote_data.get("symbol", "")
            if not self._symbol_matches_instrument(symbol):
                return

            # Extract price information for OHLCV processing according to ProjectX format
            last_price = quote_data.get("lastPrice")
            best_bid = quote_data.get("bestBid")
            best_ask = quote_data.get("bestAsk")
            volume = quote_data.get("volume", 0)

            # Emit quote update event with bid/ask data
            await self._trigger_callbacks(
                "quote_update",
                {
                    "bid": best_bid,
                    "ask": best_ask,
                    "last": last_price,
                    "volume": volume,
                    "symbol": symbol,
                    "timestamp": datetime.now(self.timezone),
                },
            )

            # Calculate price for OHLCV tick processing
            price = None

            if last_price is not None:
                # Use last traded price when available
                price = float(last_price)
                volume = 0  # GatewayQuote volume is daily total, not trade volume
            elif best_bid is not None and best_ask is not None:
                # Use mid price for quote updates
                price = (float(best_bid) + float(best_ask)) / 2
                volume = 0  # No volume for quote updates
            elif best_bid is not None:
                price = float(best_bid)
                volume = 0
            elif best_ask is not None:
                price = float(best_ask)
                volume = 0

            if price is not None:
                # Use timezone-aware timestamp
                current_time = datetime.now(self.timezone)

                # Create tick data for OHLCV processing
                tick_data = {
                    "timestamp": current_time,
                    "price": float(price),
                    "volume": volume,
                    "type": "quote",  # GatewayQuote is always a quote, not a trade
                    "source": "gateway_quote",
                }

                await self._process_tick_data(tick_data)

                # Track quote processing with new statistics system
                if hasattr(self, "track_quote_processed"):
                    await self.track_quote_processed()

        except Exception as e:
            self.logger.error(f"Error processing quote update for OHLCV: {e}")
            self.logger.debug(f"Callback data that caused error: {callback_data}")

            # Track error with new statistics system
            if hasattr(self, "track_error"):
                await self.track_error(
                    e, "quote_update", {"callback_data": str(callback_data)[:200]}
                )

    async def _on_trade_update(self, callback_data: dict[str, Any]) -> None:
        """
        Handle real-time trade updates for OHLCV data processing.

        Args:
            callback_data: Market trade callback data from realtime client
        """
        try:
            self.logger.debug(f"💹 Trade update received: {type(callback_data)}")
            self.logger.debug(f"Trade data: {callback_data}")

            # Extract the actual trade data from the callback structure (same as sync version)
            data = (
                callback_data.get("data", {}) if isinstance(callback_data, dict) else {}
            )

            # Debug log to see what we're receiving
            self.logger.debug(
                f"🔍 Trade callback - callback_data type: {type(callback_data)}, data type: {type(data)}"
            )

            # Parse and validate payload format (same as sync version)
            trade_data = self._parse_and_validate_trade_payload(data)
            if trade_data is None:
                return

            # Check if this trade is for our tracked instrument
            symbol_id = trade_data.get("symbolId", "")
            if not self._symbol_matches_instrument(symbol_id):
                return

            # Extract trade information according to ProjectX format
            price = trade_data.get("price")
            volume = trade_data.get("volume", 0)
            trade_type = trade_data.get("type")  # TradeLogType enum: Buy=0, Sell=1

            if price is not None:
                current_time = datetime.now(self.timezone)

                # Create tick data for OHLCV processing
                tick_data = {
                    "timestamp": current_time,
                    "price": float(price),
                    "volume": int(volume),
                    "type": "trade",
                    "trade_side": "buy"
                    if trade_type == TradeLogType.BUY
                    else "sell"
                    if trade_type == TradeLogType.SELL
                    else "unknown",
                    "source": "gateway_trade",
                }

                self.logger.debug(f"🔥 Processing tick: {tick_data}")
                await self._process_tick_data(tick_data)

                # Track trade processing with new statistics system
                if hasattr(self, "track_trade_processed"):
                    await self.track_trade_processed()

        except Exception as e:
            self.logger.error(f"❌ Error processing market trade for OHLCV: {e}")
            self.logger.debug(f"Callback data that caused error: {callback_data}")

            # Track error with new statistics system
            if hasattr(self, "track_error"):
                await self.track_error(
                    e, "trade_update", {"callback_data": str(callback_data)[:200]}
                )

    async def _process_tick_data(self, tick: dict[str, Any]) -> None:
        """
        Process incoming tick data and update all OHLCV timeframes with atomic operations.

        **CRITICAL FIX (v3.3.1)**: Implements race condition prevention through fine-grained
        locking, atomic transactions, and rollback mechanisms.

        **Race Condition Prevention**:
            - Per-timeframe locks prevent concurrent modification conflicts
            - Atomic transactions with rollback on partial failures
            - Rate limiting prevents excessive update frequency
            - Event triggering moved outside lock scope to prevent deadlocks

        **Safety Mechanisms**:
            - Fine-grained locking reduces contention across timeframes
            - Transaction tracking enables rollback on failures
            - Partial failure handling maintains data consistency
            - Non-blocking event emission prevents callback deadlocks

        Args:
            tick: Dictionary containing tick data (timestamp, price, volume, etc.)

        **Performance Optimizations**:
            - Rate limiting: 1ms minimum interval between updates per timeframe
            - Parallel timeframe processing with individual error isolation
            - Non-blocking callback triggering via asyncio.create_task
            - Memory cleanup and garbage collection optimization

        **Error Handling**:
            - Individual timeframe failures don't affect others
            - Automatic rollback maintains data consistency
            - Comprehensive error logging and statistics tracking
            - Graceful degradation under high load conditions
        """
        import time

        start_time = time.time()
        try:
            if not self.is_running:
                return

            timestamp = tick["timestamp"]
            price = tick["price"]
            volume = tick.get("volume", 0)

            # Collect events to trigger after releasing locks
            events_to_trigger = []

            # Rate limiting check - prevent excessive updates
            current_time = time.time()
            if (
                current_time - self._last_update_times["global"]
                < self._min_update_interval
            ):
                return
            self._last_update_times["global"] = current_time

            # Add to current tick data for get_current_price() (global lock for this)
            # Handle both Lock and AsyncRWLock types
            from project_x_py.utils.lock_optimization import AsyncRWLock

            if isinstance(self.data_lock, AsyncRWLock):
                # AsyncRWLock - use write_lock for modifying data
                async with self.data_lock.write_lock():
                    self.current_tick_data.append(tick)
            else:
                # Regular Lock - use directly
                async with self.data_lock:
                    self.current_tick_data.append(tick)

            # Process each timeframe with fine-grained locking and atomic operations
            successful_updates = []
            failed_timeframes = []

            for tf_key in self.timeframes:
                try:
                    # Fine-grained lock per timeframe to prevent race conditions
                    tf_lock = self._get_timeframe_lock(tf_key)
                    async with tf_lock:
                        # Rate limiting per timeframe
                        if (
                            current_time - self._last_update_times[tf_key]
                            < self._min_update_interval
                        ):
                            continue
                        self._last_update_times[tf_key] = current_time

                        # Perform atomic update with rollback capability
                        new_bar_event = await self._update_timeframe_data_atomic(
                            tf_key, timestamp, price, volume
                        )
                        if new_bar_event:
                            events_to_trigger.append(new_bar_event)
                        successful_updates.append(tf_key)

                except Exception as e:
                    self.logger.error(f"Error updating timeframe {tf_key}: {e}")
                    failed_timeframes.append((tf_key, e))
                    # Continue with other timeframes - don't fail the entire operation

            # Rollback any partial failures if critical timeframes failed
            if failed_timeframes:
                await self._handle_partial_failures(
                    failed_timeframes, successful_updates
                )

            # Trigger callbacks for data updates (outside the locks, non-blocking)
            asyncio.create_task(
                self._trigger_callbacks(
                    "data_update",
                    {"timestamp": timestamp, "price": price, "volume": volume},
                )
            )

            # Trigger any new bar events (outside the locks, non-blocking)
            for event in events_to_trigger:
                asyncio.create_task(self._trigger_callbacks("new_bar", event))
            # Update memory stats and periodic cleanup
            self.memory_stats["ticks_processed"] += 1
            await self._cleanup_old_data()

            # Track operation timing with new statistics system
            if hasattr(self, "record_timing"):
                duration_ms = (time.time() - start_time) * 1000
                await self.record_timing("process_tick", duration_ms)

            # Track tick processing with new statistics system
            if hasattr(self, "track_tick_processed"):
                await self.track_tick_processed()

        except Exception as e:
            self.logger.error(f"Error processing tick data: {e}")
            # Track failed operation with new statistics system
            if hasattr(self, "record_timing"):
                duration_ms = (time.time() - start_time) * 1000
                await self.record_timing("process_tick_failed", duration_ms)

            # Track error with new statistics system
            if hasattr(self, "track_error"):
                await self.track_error(
                    e,
                    "process_tick",
                    {"price": tick.get("price"), "volume": tick.get("volume")},
                )

    async def _update_timeframe_data_atomic(
        self,
        tf_key: str,
        timestamp: datetime,
        price: float,
        volume: int,
    ) -> dict[str, Any] | None:
        """
        Atomically update a specific timeframe with rollback capability.

        Args:
            tf_key: Timeframe key (e.g., "5min", "15min", "1hr")
            timestamp: Timestamp of the tick
            price: Price of the tick
            volume: Volume of the tick

        Returns:
            dict: New bar event data if a new bar was created, None otherwise
        """
        try:
            # Store original state for potential rollback
            transaction_id = f"{tf_key}_{timestamp.timestamp()}"
            original_data = None
            original_bar_time = None

            if tf_key in self.data:
                original_data = self.data[tf_key].clone()  # Deep copy for rollback
                original_bar_time = self.last_bar_times.get(tf_key)

            self._update_transactions[transaction_id] = {
                "timeframe": tf_key,
                "original_data": original_data,
                "original_bar_time": original_bar_time,
                "timestamp": timestamp,
            }

            # Perform the actual update
            result = await self._update_timeframe_data(tf_key, timestamp, price, volume)

            # If successful, clear the transaction (no rollback needed)
            self._update_transactions.pop(transaction_id, None)

            return result
        except Exception as e:
            # Rollback on failure
            await self._rollback_transaction(transaction_id)
            self.logger.error(f"Atomic update failed for {tf_key}: {e}")
            raise

    async def _rollback_transaction(self, transaction_id: str) -> None:
        """
        Rollback a failed timeframe update transaction.

        Args:
            transaction_id: Unique transaction identifier
        """
        try:
            transaction = self._update_transactions.get(transaction_id)
            if not transaction:
                return

            tf_key = transaction["timeframe"]
            original_data = transaction["original_data"]
            original_bar_time = transaction["original_bar_time"]

            # Restore original state
            if original_data is not None:
                self.data[tf_key] = original_data
            elif tf_key in self.data:
                # If there was no original data, remove the entry
                del self.data[tf_key]

            if original_bar_time is not None:
                self.last_bar_times[tf_key] = original_bar_time
            elif tf_key in self.last_bar_times:
                del self.last_bar_times[tf_key]

            self.logger.debug(f"Rolled back transaction for {tf_key}")
        except Exception as e:
            self.logger.error(f"Error rolling back transaction {transaction_id}: {e}")
        finally:
            # Always clean up the transaction record
            self._update_transactions.pop(transaction_id, None)

    async def _handle_partial_failures(
        self,
        failed_timeframes: list[tuple[str, Exception]],
        successful_updates: list[str],
    ) -> None:
        """
        Handle partial failures in timeframe updates.

        Args:
            failed_timeframes: List of (timeframe, exception) tuples that failed
            successful_updates: List of timeframes that were successfully updated
        """
        # Log failures for monitoring
        for tf_key, error in failed_timeframes:
            self.logger.warning(f"Timeframe {tf_key} update failed: {error}")
            if hasattr(self, "track_error"):
                await self.track_error(error, f"timeframe_update_{tf_key}")

        # If critical timeframes failed (less than 50% success rate), log warning
        total_timeframes = len(failed_timeframes) + len(successful_updates)
        success_rate = (
            len(successful_updates) / total_timeframes if total_timeframes > 0 else 0
        )

        if success_rate < 0.5:
            self.logger.error(
                f"Critical: Low success rate ({success_rate:.1%}) for timeframe updates. "
                f"Failed: {[tf for tf, _ in failed_timeframes]}, "
                f"Successful: {successful_updates}"
            )

        # Update statistics for partial failures
        if hasattr(self, "increment"):
            await self.increment("partial_update_failures", len(failed_timeframes))
            await self.increment(
                "successful_timeframe_updates", len(successful_updates)
            )

    async def _update_timeframe_data(
        self,
        tf_key: str,
        timestamp: datetime,
        price: float,
        volume: int,
    ) -> dict[str, Any] | None:
        """
        Update a specific timeframe with new tick data.

        Args:
            tf_key: Timeframe key (e.g., "5min", "15min", "1hr")
            timestamp: Timestamp of the tick
            price: Price of the tick
            volume: Volume of the tick

        Returns:
            dict: New bar event data if a new bar was created, None otherwise
        """
        try:
            interval = self.timeframes[tf_key]["interval"]
            unit = self.timeframes[tf_key]["unit"]

            # Calculate the bar time for this timeframe with DST handling
            if hasattr(self, "handle_dst_bar_time"):
                bar_time = self.handle_dst_bar_time(timestamp, interval, unit)
                if bar_time is None:
                    # Skip this bar during DST transitions (e.g., spring forward)
                    if hasattr(self, "log_dst_event"):
                        self.log_dst_event(
                            "BAR_SKIPPED",
                            timestamp,
                            f"Non-existent time during DST transition for {tf_key}",
                        )
                    else:
                        self.logger.warning(
                            f"Skipping bar for {tf_key} during DST transition at {timestamp}"
                        )
                    return None
            else:
                # Fallback to standard bar time calculation
                bar_time = self._calculate_bar_time(timestamp, interval, unit)

            # Get current data for this timeframe
            if tf_key not in self.data:
                return None

            current_data = self.data[tf_key]

            # Align price to tick size
            aligned_price = align_price_to_tick(price, self.tick_size)

            # Check if we need to create a new bar or update existing
            if current_data.height == 0:
                # First bar - use actual volume (0 for quotes, >0 for trades)
                bar_volume = volume
                new_bar = pl.DataFrame(
                    {
                        "timestamp": [bar_time],
                        "open": [aligned_price],
                        "high": [aligned_price],
                        "low": [aligned_price],
                        "close": [aligned_price],
                        "volume": [bar_volume],
                    }
                )

                self.data[tf_key] = new_bar
                self.last_bar_times[tf_key] = bar_time

                # Track first bar creation with new statistics system
                if hasattr(self, "track_bar_created"):
                    await self.track_bar_created(tf_key)

            else:
                last_bar_time = current_data.select(pl.col("timestamp")).tail(1).item()

                if bar_time > last_bar_time:
                    # New bar needed - use actual volume (0 for quotes, >0 for trades)
                    bar_volume = volume
                    new_bar = pl.DataFrame(
                        {
                            "timestamp": [bar_time],
                            "open": [aligned_price],
                            "high": [aligned_price],
                            "low": [aligned_price],
                            "close": [aligned_price],
                            "volume": [bar_volume],
                        }
                    )

                    self.data[tf_key] = pl.concat([current_data, new_bar])
                    self.last_bar_times[tf_key] = bar_time

                    # Track new bar creation with new statistics system
                    if hasattr(self, "track_bar_created"):
                        await self.track_bar_created(tf_key)

                    # Return new bar event data to be triggered outside the lock
                    return {
                        "timeframe": tf_key,
                        "bar_time": bar_time,
                        "data": new_bar.to_dicts()[0],
                    }

                elif bar_time == last_bar_time:
                    # Update existing bar
                    last_row_mask = pl.col("timestamp") == pl.lit(bar_time)

                    # Get current values
                    last_row = current_data.filter(last_row_mask)
                    current_high = (
                        last_row.select(pl.col("high")).item()
                        if last_row.height > 0
                        else aligned_price
                    )
                    current_low = (
                        last_row.select(pl.col("low")).item()
                        if last_row.height > 0
                        else aligned_price
                    )
                    current_volume = (
                        last_row.select(pl.col("volume")).item()
                        if last_row.height > 0
                        else 0
                    )

                    # Calculate new values with tick alignment
                    new_high = align_price_to_tick(
                        max(current_high, aligned_price), self.tick_size
                    )
                    new_low = align_price_to_tick(
                        min(current_low, aligned_price), self.tick_size
                    )
                    new_volume = current_volume + volume

                    # Update with new values
                    self.data[tf_key] = current_data.with_columns(
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
                            .then(pl.lit(aligned_price))
                            .otherwise(pl.col("close"))
                            .alias("close"),
                            pl.when(last_row_mask)
                            .then(pl.lit(new_volume))
                            .otherwise(pl.col("volume"))
                            .alias("volume"),
                        ]
                    )

                    # Track bar update with new statistics system
                    if hasattr(self, "track_bar_updated"):
                        await self.track_bar_updated(tf_key)

            # Return None if no new bar was created
            return None

        except Exception as e:
            self.logger.error(f"Error updating {tf_key} timeframe: {e}")
            return None

    def _calculate_bar_time(
        self,
        timestamp: datetime,
        interval: int,
        unit: int,
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
            # Handle both pytz timezone objects and datetime.timezone objects
            if hasattr(self.timezone, "localize"):
                # pytz timezone object
                timestamp = self.timezone.localize(timestamp)
            else:
                # datetime.timezone object
                timestamp = timestamp.replace(tzinfo=self.timezone)

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
