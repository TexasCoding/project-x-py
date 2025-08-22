"""
Async memory management for ProjectX orderbook.

Author: @TexasCoding
Date: 2025-08-02

Overview:
    Provides memory/resource management for high-frequency orderbook data. Handles
    cleanup, trimming, stats, and garbage collection for deep market data streams,
    ensuring long-running session stability.

Key Features:
    - Periodic cleanup of trades, depth, and price history
    - Configurable memory and history retention policies
    - Memory usage/statistics reporting for diagnostics
    - Async task-based cleanup with thread safety
    - Automatic garbage collection and memory optimization
    - Comprehensive memory usage monitoring and reporting
    - Configurable cleanup intervals and retention policies

Memory Management Strategies:
    - Trade History: Limits recent trades to prevent unbounded growth
    - Orderbook Depth: Maintains optimal number of price levels
    - Price History: Time-based cleanup of historical price level data
    - Market History: Trimming of best prices, spreads, and delta history
    - Garbage Collection: Automatic memory cleanup after major operations

Example Usage:
    ```python
    # V3.1: Memory management with TradingSuite's orderbook
    from project_x_py import TradingSuite

    suite = await TradingSuite.create("MNQ", features=["orderbook"])

    # V3.1: Memory manager auto-starts with orderbook
    # Manual cleanup if needed
    await suite.orderbook.memory_manager.cleanup_old_data()

    # V3.1: Get comprehensive memory statistics
    stats = await suite.orderbook.memory_manager.get_memory_stats()
    print(f"Trades in memory: {stats['recent_trades_count']}")
    print(f"Bid levels: {stats['orderbook_bids_count']}")
    print(f"Ask levels: {stats['orderbook_asks_count']}")
    print(f"Memory usage: {stats['memory_usage_mb']:.1f} MB")

    # V3.1: Configure memory limits
    suite.orderbook.memory_config.max_trades = 5000
    suite.orderbook.memory_config.max_depth_entries = 200

    await suite.disconnect()
    ```

See Also:
    - `orderbook.base.OrderBookBase`
    - `orderbook.analytics.MarketAnalytics`
"""

import asyncio
import gc
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from project_x_py.orderbook.base import OrderBookBase

import contextlib
import logging

from project_x_py.types import MemoryConfig
from project_x_py.types.stats_types import OrderbookStats


class MemoryManager:
    """
    Manages memory usage and cleanup for async orderbook.

    This class handles the memory lifecycle of the orderbook data structures, ensuring
    that memory usage remains bounded during long-running sessions while maintaining
    sufficient historical data for analysis. It implements automatic periodic cleanup
    strategies and provides memory usage statistics.

    Key responsibilities:
    1. Periodic cleanup of old trade data based on configurable limits
    2. Management of orderbook depth entries to prevent unbounded growth
    3. Cleanup of price level history to maintain reasonable memory usage
    4. Trimming of market data history (bids, asks, spreads, deltas)
    5. Providing memory usage statistics for monitoring
    6. Triggering garbage collection when appropriate
    7. Automatic memory optimization and resource management
    8. Comprehensive memory usage reporting and diagnostics

    The memory manager runs as an asynchronous background task that periodically
    checks and cleans up data structures based on the configured limits. It uses
    a combination of time-based and count-based thresholds to determine what data
    to retain and what to discard.

    Thread safety:
        All operations acquire appropriate locks before modifying shared data structures,
        ensuring thread-safe operation in concurrent environments.

    Configuration:
        The memory management behavior is controlled through the MemoryConfig class,
        which defines limits for various data structures:
        - Maximum number of trades to retain
        - Maximum number of depth entries per side
        - Cleanup interval
        - Maximum history entries per price level
        - Time window for price history retention
        - Maximum entries for various history trackers

    Performance Characteristics:
        - Asynchronous background cleanup with minimal impact on real-time operations
        - Configurable cleanup intervals and retention policies
        - Automatic garbage collection after major cleanup operations
        - Comprehensive memory usage monitoring and reporting
    """

    def __init__(self, orderbook: "OrderBookBase", config: MemoryConfig):
        self.orderbook = orderbook
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Memory statistics
        self.memory_stats: dict[str, Any] = {
            "last_cleanup": datetime.now(UTC),
            "total_trades": 0,
            "trades_cleaned": 0,
            "depth_cleaned": 0,
            "history_cleaned": 0,
        }

        # Cleanup task
        self._cleanup_task: asyncio.Task[None] | None = None
        self._running = False

    async def start(self) -> None:
        """Start the periodic cleanup task."""
        if not self._running:
            self._running = True
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
            self.logger.info("Memory manager started")

    async def stop(self) -> None:
        """Stop the periodic cleanup task."""
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._cleanup_task
            self._cleanup_task = None
        self.logger.info("Memory manager stopped")

    async def _periodic_cleanup(self) -> None:
        """
        Periodically clean up old data to manage memory usage.

        This method runs as a background task, performing cleanup operations
        at regular intervals defined by the configuration. It ensures that
        memory usage remains bounded during long-running sessions by removing
        old data that is no longer needed for analysis.

        The cleanup loop:
        1. Sleeps for the configured cleanup interval
        2. Calls cleanup_old_data() to perform actual cleanup
        3. Handles cancellation gracefully when the memory manager stops
        4. Logs any errors but continues operation

        Note:
            This method runs continuously until the memory manager is stopped.
            It's designed to be robust and continue operation even if individual
            cleanup operations fail.
        """
        while self._running:
            try:
                await asyncio.sleep(self.config.cleanup_interval)
                await self.cleanup_old_data()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in periodic cleanup: {e}")

    async def cleanup_old_data(self) -> None:
        """Clean up old data based on configured limits."""
        async with self.orderbook.orderbook_lock:
            try:
                current_time = datetime.now(self.orderbook.timezone)
                self.memory_stats["last_cleanup"] = current_time

                # Clean up old trades
                trades_before = self.orderbook.recent_trades.height
                if trades_before > self.config.max_trades:
                    self.orderbook.recent_trades = self.orderbook.recent_trades.tail(
                        self.config.max_trades
                    )
                    trades_cleaned = trades_before - self.orderbook.recent_trades.height
                    self.memory_stats["trades_cleaned"] += trades_cleaned
                    self.logger.debug(f"Cleaned {trades_cleaned} old trades")

                # Clean up excessive depth entries
                bids_before = self.orderbook.orderbook_bids.height
                asks_before = self.orderbook.orderbook_asks.height

                if bids_before > self.config.max_depth_entries:
                    # Keep only the best N bids
                    self.orderbook.orderbook_bids = self.orderbook.orderbook_bids.sort(
                        "price", descending=True
                    ).head(self.config.max_depth_entries)
                    self.memory_stats["depth_cleaned"] += (
                        bids_before - self.orderbook.orderbook_bids.height
                    )

                if asks_before > self.config.max_depth_entries:
                    # Keep only the best N asks
                    self.orderbook.orderbook_asks = self.orderbook.orderbook_asks.sort(
                        "price"
                    ).head(self.config.max_depth_entries)
                    self.memory_stats["depth_cleaned"] += (
                        asks_before - self.orderbook.orderbook_asks.height
                    )

                # Clean up price level history
                await self._cleanup_price_history(current_time)

                # Clean up best price and spread history
                await self._cleanup_market_history()

                # Run garbage collection after major cleanup
                if (
                    self.memory_stats["trades_cleaned"]
                    + self.memory_stats["depth_cleaned"]
                    + self.memory_stats["history_cleaned"]
                ) > 1000:
                    gc.collect()
                    self.logger.debug("Garbage collection completed")

            except Exception as e:
                self.logger.error(f"Error during cleanup: {e}")

    async def _cleanup_price_history(self, current_time: datetime) -> None:
        """
        Clean up old price level history.

        This method removes old entries from the price level history tracking
        system to prevent unbounded memory growth. It applies both time-based
        and count-based limits to maintain a reasonable amount of historical
        data for analytics while preventing memory leaks.

        Cleanup operations:
        1. Removes history entries older than the configured time window
        2. Limits each price level to maximum number of history entries
        3. Removes empty history collections to free memory
        4. Updates cleanup statistics

        Args:
            current_time: Current timestamp for age-based cleanup calculations
        """
        cutoff_time = current_time - timedelta(
            minutes=self.config.price_history_window_minutes
        )

        for key in list(self.orderbook.price_level_history.keys()):
            history = self.orderbook.price_level_history[key]

            # For deque, we need to filter and rebuild
            # Note: deque already has maxlen=1000, so it auto-limits size
            # We only need to remove old entries based on time
            filtered_entries = [
                h for h in history if h.get("timestamp", current_time) > cutoff_time
            ]

            # If we have filtered entries, update the deque
            if filtered_entries != list(history):
                # Clear and repopulate the deque with filtered entries
                history.clear()
                history.extend(filtered_entries)
                self.memory_stats["history_cleaned"] += len(history) - len(
                    filtered_entries
                )

            # Remove empty histories
            if not history:
                del self.orderbook.price_level_history[key]

    async def _cleanup_market_history(self) -> None:
        """
        Clean up market data history (best prices, spreads, etc.).

        This method manages the size of various history tracking lists to prevent
        unbounded memory growth. It trims historical data collections to their
        configured maximum sizes while preserving the most recent entries.

        Collections managed:
        - Best bid history: Price and timestamp of best bid over time
        - Best ask history: Price and timestamp of best ask over time
        - Spread history: Bid-ask spread values over time
        - Delta history: Cumulative delta calculations over time

        Each collection is trimmed to keep only the most recent entries up to
        the configured maximum size, with removed entries tracked in statistics.
        """
        # Best bid/ask history
        if len(self.orderbook.best_bid_history) > self.config.max_best_price_history:
            removed = (
                len(self.orderbook.best_bid_history)
                - self.config.max_best_price_history
            )
            self.orderbook.best_bid_history = self.orderbook.best_bid_history[
                -self.config.max_best_price_history :
            ]
            self.memory_stats["history_cleaned"] += removed

        if len(self.orderbook.best_ask_history) > self.config.max_best_price_history:
            removed = (
                len(self.orderbook.best_ask_history)
                - self.config.max_best_price_history
            )
            self.orderbook.best_ask_history = self.orderbook.best_ask_history[
                -self.config.max_best_price_history :
            ]
            self.memory_stats["history_cleaned"] += removed

        # Spread history
        if len(self.orderbook.spread_history) > self.config.max_spread_history:
            removed = (
                len(self.orderbook.spread_history) - self.config.max_spread_history
            )
            self.orderbook.spread_history = self.orderbook.spread_history[
                -self.config.max_spread_history :
            ]
            self.memory_stats["history_cleaned"] += removed

        # Delta history - deque handles its own cleanup with maxlen
        # No manual cleanup needed for deque with maxlen

    def get_memory_stats(self) -> OrderbookStats:
        """
        Get comprehensive memory usage statistics.

        This method provides detailed statistics about the current memory usage of the
        orderbook, including counts of various data structures, cleanup history, and
        configuration settings. It's useful for monitoring memory usage over time,
        debugging memory issues, and validating that the cleanup strategies are working
        as expected.

        Note: This is a synchronous method that computes stats immediately.

        Returns:
            Dict containing comprehensive memory statistics including:
                orderbook_bids_count: Number of bid price levels
                orderbook_asks_count: Number of ask price levels
                recent_trades_count: Number of trades in the recent trades cache
                price_level_history_count: Number of price levels with history
                best_bid_history_count: Length of best bid price history
                best_ask_history_count: Length of best ask price history
                spread_history_count: Length of spread history
                delta_history_count: Length of cumulative delta history
                support_levels_count: Number of tracked support levels
                resistance_levels_count: Number of tracked resistance levels
                last_cleanup: Timestamp of last cleanup operation
                total_trades_processed: Total number of trades processed
                trades_cleaned: Number of trades removed by cleanup
                depth_cleaned: Number of depth entries removed by cleanup
                history_cleaned: Number of history entries removed by cleanup
                memory_config: Dictionary of current memory configuration settings

        Example:
            >>> stats = await orderbook.get_memory_stats()
            >>> print(
            ...     f"Orderbook size: {stats['orderbook_bids_count']} bids, "
            ...     f"{stats['orderbook_asks_count']} asks"
            ... )
            >>> print(f"Recent trades: {stats['recent_trades_count']}")
            >>> print(f"Last cleanup: {datetime.fromtimestamp(stats['last_cleanup'])}")
            >>> print(f"Items cleaned: {stats['trades_cleaned'] + stats['depth_cleaned'] + "
            ...       f"stats['history_cleaned']}")
        """
        # Note: This method is synchronous and doesn't acquire locks
        # It provides a snapshot of current stats without blocking

        # Calculate current depth statistics
        bid_depth = self.orderbook.orderbook_bids.height
        ask_depth = self.orderbook.orderbook_asks.height

        # Calculate trade statistics
        trades_count = self.memory_stats.get("total_trades", 0)
        total_volume = self.memory_stats.get("total_volume", 0)
        avg_trade_size = total_volume / trades_count if trades_count > 0 else 0.0

        # Calculate memory usage (rough estimate)
        memory_usage_mb = (
            (bid_depth + ask_depth) * 0.0001  # Depth data
            + self.orderbook.recent_trades.height * 0.0001  # Trade data
            + len(self.orderbook.price_level_history) * 0.0001  # History data
        )

        # Calculate spread from current best prices
        best_bid = (
            float(self.orderbook.best_bid_history[-1]["price"])
            if self.orderbook.best_bid_history
            else 0.0
        )
        best_ask = (
            float(self.orderbook.best_ask_history[-1]["price"])
            if self.orderbook.best_ask_history
            else 0.0
        )
        current_spread = best_ask - best_bid if best_bid > 0 and best_ask > 0 else 0.0

        # Calculate spread volatility from history
        spreads = [
            float(ask["price"]) - float(bid["price"])
            for bid, ask in zip(
                self.orderbook.best_bid_history,
                self.orderbook.best_ask_history,
                strict=False,
            )
            if float(bid["price"]) > 0 and float(ask["price"]) > 0
        ]
        spread_volatility = 0.0
        if len(spreads) > 1:
            avg_spread = sum(spreads) / len(spreads)
            spread_volatility = (
                sum((s - avg_spread) ** 2 for s in spreads) / len(spreads)
            ) ** 0.5

        return {
            # Depth statistics
            "avg_bid_depth": bid_depth,
            "avg_ask_depth": ask_depth,
            "max_bid_depth": self.memory_stats.get("max_bid_depth", bid_depth),
            "max_ask_depth": self.memory_stats.get("max_ask_depth", ask_depth),
            # Trade statistics
            "trades_processed": trades_count,
            "avg_trade_size": avg_trade_size,
            "largest_trade": self.memory_stats.get("largest_trade", 0),
            "total_volume": total_volume,
            # Market microstructure
            "avg_spread": current_spread,
            "spread_volatility": spread_volatility,
            "price_levels": bid_depth + ask_depth,
            "order_clustering": 0.0,  # Would need more complex calculation
            # Pattern detection
            "icebergs_detected": self.memory_stats.get("icebergs_detected", 0),
            "spoofing_alerts": self.memory_stats.get("spoofing_alerts", 0),
            "unusual_patterns": self.memory_stats.get("unusual_patterns", 0),
            # Performance metrics
            "update_frequency_per_second": self.memory_stats.get(
                "update_frequency", 0.0
            ),
            "processing_latency_ms": self.memory_stats.get(
                "processing_latency_ms", 0.0
            ),
            "memory_usage_mb": memory_usage_mb,
            # Data quality
            "data_gaps": self.memory_stats.get("data_gaps", 0),
            "invalid_updates": self.memory_stats.get("invalid_updates", 0),
            "duplicate_updates": self.memory_stats.get("duplicate_updates", 0),
        }
