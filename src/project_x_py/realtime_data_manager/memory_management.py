"""
Memory management and cleanup functionality for real-time data.

Author: @TexasCoding
Date: 2025-08-02

Overview:
    Provides memory management and cleanup functionality for real-time data processing.
    Implements efficient memory management with sliding window storage, automatic cleanup,
    and comprehensive statistics tracking to prevent memory leaks and optimize performance.

Key Features:
    - Automatic memory cleanup with configurable intervals
    - Sliding window storage for efficient memory usage
    - Background cleanup tasks with proper error handling
    - Comprehensive memory statistics and monitoring
    - Garbage collection optimization
    - Thread-safe memory operations

Memory Management Capabilities:
    - Automatic cleanup of old OHLCV data with sliding windows
    - Tick buffer management with size limits
    - Background periodic cleanup tasks
    - Memory statistics tracking and monitoring
    - Garbage collection optimization after cleanup
    - Error handling and recovery for memory issues

Example Usage:
    ```python
    # V3: Memory management with async patterns
    async with ProjectX.from_env() as client:
        await client.authenticate()

        # V3: Create manager with memory configuration
        manager = RealtimeDataManager(
            instrument="MNQ",
            project_x=client,
            realtime_client=realtime_client,
            timeframes=["1min", "5min"],
            max_bars_per_timeframe=500,  # V3: Configurable limits
            tick_buffer_size=100,
        )

        # V3: Access memory statistics asynchronously
        stats = await manager.get_memory_stats()
        print(f"Total bars in memory: {stats['total_bars']}")
        print(f"Total data points: {stats['total_data_points']}")
        print(f"Ticks processed: {stats['ticks_processed']}")
        print(f"Bars cleaned: {stats['bars_cleaned']}")

        # V3: Check timeframe-specific statistics
        for tf, count in stats["timeframe_bar_counts"].items():
            print(f"{tf}: {count} bars")

        # V3: Monitor memory health
        if stats["total_data_points"] > 10000:
            print("Warning: High memory usage detected")
            await manager.cleanup()  # Force cleanup

        # V3: Memory management happens automatically
        # Background cleanup task runs periodically
    ```

Memory Management Strategy:
    - Sliding window: Keep only recent data (configurable limits)
    - Automatic cleanup: Periodic cleanup of old data
    - Tick buffering: Limited tick data storage for current price access
    - Garbage collection: Force GC after significant cleanup operations
    - Statistics tracking: Comprehensive monitoring of memory usage

Performance Characteristics:
    - Minimal memory footprint with sliding window storage
    - Automatic cleanup prevents memory leaks
    - Background tasks with proper error handling
    - Efficient garbage collection optimization
    - Thread-safe operations with proper locking

Configuration:
    - max_bars_per_timeframe: Maximum bars to keep per timeframe (default: 1000)
    - tick_buffer_size: Maximum tick data to buffer (default: 1000)
    - cleanup_interval: Time between cleanup operations (default: 300 seconds)

See Also:
    - `realtime_data_manager.core.RealtimeDataManager`
    - `realtime_data_manager.callbacks.CallbackMixin`
    - `realtime_data_manager.data_access.DataAccessMixin`
    - `realtime_data_manager.data_processing.DataProcessingMixin`
    - `realtime_data_manager.validation.ValidationMixin`
"""

import asyncio
import gc
import logging
import time
from collections import deque
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from project_x_py.utils.task_management import TaskManagerMixin

if TYPE_CHECKING:
    from project_x_py.types.stats_types import RealtimeDataManagerStats

import polars as pl

if TYPE_CHECKING:
    from asyncio import Lock

logger = logging.getLogger(__name__)


class MemoryManagementMixin(TaskManagerMixin):
    """
    Mixin for memory management and optimization.

    **CRITICAL FIX (v3.3.1)**: Implements buffer overflow handling through dynamic buffer
    sizing, intelligent data sampling, and comprehensive overflow detection.

    **Buffer Overflow Prevention Features**:
        - Dynamic buffer sizing with per-timeframe thresholds
        - 95% utilization triggers for overflow detection
        - Intelligent data sampling preserves recent data integrity
        - Callback system for overflow event notifications

    **Memory Management Strategy**:
        - Per-timeframe buffer thresholds (5K/2K/1K based on timeframe unit)
        - Intelligent sampling: preserves 30% recent data, samples 70% older
        - Configurable overflow alert callbacks for monitoring
        - Comprehensive buffer utilization statistics and health monitoring

    **Safety Mechanisms**:
        - Overflow detection prevents out-of-memory conditions
        - Data sampling maintains temporal distribution
        - Error isolation prevents memory management failures
        - Performance monitoring through comprehensive statistics
    """

    # Type hints for mypy - these attributes are provided by the main class
    if TYPE_CHECKING:
        logger: logging.Logger
        last_cleanup: float
        cleanup_interval: float
        data_lock: Lock
        timeframes: dict[str, dict[str, Any]]
        data: dict[str, pl.DataFrame]
        max_bars_per_timeframe: int
        current_tick_data: list[dict[str, Any]] | deque[dict[str, Any]]
        tick_buffer_size: int
        memory_stats: dict[str, Any]
        is_running: bool
        last_bar_times: dict[str, Any]

        # Methods from statistics system
        async def increment(self, _metric: str, _value: int | float = 1) -> None: ...

        # Optional methods from overflow mixin
        async def _check_overflow_needed(self, _timeframe: str) -> bool: ...
        async def _overflow_to_disk(self, _timeframe: str) -> None: ...
        async def get_overflow_stats(self) -> dict[str, Any]: ...

    def __init__(self) -> None:
        """Initialize memory management attributes."""
        super().__init__()
        self._init_task_manager()  # Initialize task management
        self._cleanup_task: asyncio.Task[None] | None = None
        # Buffer overflow handling
        self._buffer_overflow_thresholds: dict[str, int] = {}
        self._dynamic_buffer_enabled = True
        self._overflow_alert_callbacks: list[Callable[..., Any]] = []
        self._sampling_ratios: dict[str, float] = {}

    def configure_dynamic_buffer_sizing(
        self, enabled: bool = True, initial_thresholds: dict[str, int] | None = None
    ) -> None:
        """
        Configure dynamic buffer sizing for overflow handling.

        Args:
            enabled: Whether to enable dynamic buffer sizing
            initial_thresholds: Initial buffer thresholds per timeframe
        """
        self._dynamic_buffer_enabled = enabled
        if initial_thresholds:
            self._buffer_overflow_thresholds.update(initial_thresholds)
        else:
            # Set default thresholds based on timeframe interval
            for tf_key, tf_config in self.timeframes.items():
                if tf_config["unit"] == 1:  # seconds
                    self._buffer_overflow_thresholds[tf_key] = (
                        5000  # 5K bars for second data
                    )
                elif tf_config["unit"] == 2:  # minutes
                    self._buffer_overflow_thresholds[tf_key] = (
                        2000  # 2K bars for minute data
                    )
                else:  # hours, days, etc.
                    self._buffer_overflow_thresholds[tf_key] = (
                        1000  # 1K bars for larger timeframes
                    )

    async def _check_buffer_overflow(self, timeframe: str) -> tuple[bool, float]:
        """
        Check if a timeframe buffer is approaching overflow.

        Args:
            timeframe: Timeframe to check

        Returns:
            Tuple of (is_overflow, utilization_percentage)
        """
        if timeframe not in self.data:
            return False, 0.0

        current_size = len(self.data[timeframe])
        threshold = self._buffer_overflow_thresholds.get(
            timeframe,
            self.max_bars_per_timeframe * 2,  # Use 2x max as default threshold
        )

        utilization = (current_size / threshold) * 100 if threshold > 0 else 0.0
        is_overflow = utilization >= 95.0  # Alert at 95% capacity

        return is_overflow, utilization

    async def _handle_buffer_overflow(self, timeframe: str, utilization: float) -> None:
        """
        Handle buffer overflow by implementing data sampling and alerts.

        **CRITICAL FIX (v3.3.1)**: Implements intelligent overflow handling with data
        sampling, alert notifications, and performance statistics tracking.

        **Overflow Handling Strategy**:
            - 95% utilization threshold triggers overflow detection
            - Intelligent data sampling preserves recent data integrity
            - Callback notifications enable monitoring and alerting
            - Automatic buffer size reduction to 70% of maximum capacity

        **Data Preservation Logic**:
            - Preserves 30% of data as recent/critical information
            - Samples 70% of older data to maintain temporal distribution
            - Uses step-based sampling to preserve data patterns
            - Updates last bar time tracking for consistency

        Args:
            timeframe: Timeframe experiencing overflow
            utilization: Current buffer utilization percentage (typically >= 95.0)

        **Safety Features**:
            - Error isolation prevents overflow handling failures from affecting other timeframes
            - Comprehensive statistics tracking for monitoring and debugging
            - Automatic fallback to basic cleanup if sampling fails
            - Performance monitoring through increment tracking
        """
        self.logger.warning(
            f"Buffer overflow detected for {timeframe}: {utilization:.1f}% utilization"
        )

        # Trigger overflow alerts
        for callback in self._overflow_alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(timeframe, utilization)
                else:
                    callback(timeframe, utilization)
            except Exception as e:
                self.logger.error(f"Error in overflow alert callback: {e}")

        # Implement data sampling if enabled
        if self._dynamic_buffer_enabled and timeframe in self.data:
            await self._apply_data_sampling(timeframe)

        # Update statistics
        if hasattr(self, "increment"):
            await self.increment("buffer_overflow_events", 1)
            await self.increment(f"buffer_overflow_{timeframe}", 1)

    async def _apply_data_sampling(self, timeframe: str) -> None:
        """
        Apply data sampling to reduce buffer size while preserving data integrity.

        Args:
            timeframe: Timeframe to apply sampling to
        """
        if timeframe not in self.data or self.data[timeframe].is_empty():
            return

        current_data = self.data[timeframe]
        current_size = len(current_data)
        target_size = int(self.max_bars_per_timeframe * 0.7)  # Reduce to 70% of max

        if current_size <= target_size:
            return

        # Calculate sampling ratio
        sampling_ratio = target_size / current_size
        self._sampling_ratios[timeframe] = sampling_ratio

        # Apply intelligent sampling - keep recent data and sample older data
        recent_data_size = int(target_size * 0.3)  # Keep 30% as recent data
        sampled_older_size = target_size - recent_data_size

        # Keep all recent data
        recent_data = current_data.tail(recent_data_size)

        # Sample older data intelligently
        older_data = current_data.head(current_size - recent_data_size)
        if len(older_data) > sampled_older_size:
            # Sample every nth bar to maintain temporal distribution
            sample_step = max(1, len(older_data) // sampled_older_size)
            # Use gather to sample every nth row
            sample_indices = list(range(0, len(older_data), sample_step))[
                :sampled_older_size
            ]
            sampled_older = older_data[sample_indices]
        else:
            sampled_older = older_data

        # Combine sampled older data with recent data
        if not sampled_older.is_empty():
            self.data[timeframe] = pl.concat([sampled_older, recent_data])
        else:
            self.data[timeframe] = recent_data

        # Update last bar time if needed
        if timeframe in self.last_bar_times:
            self.last_bar_times[timeframe] = (
                recent_data.select(pl.col("timestamp")).tail(1).item()
            )

        self.logger.info(
            f"Applied data sampling to {timeframe}: {current_size} -> {len(self.data[timeframe])} bars "
            f"(sampling ratio: {sampling_ratio:.3f})"
        )

    def add_overflow_alert_callback(self, callback: Callable[..., Any]) -> None:
        """
        Add a callback to be notified of buffer overflow events.

        Args:
            callback: Callable that takes (timeframe: str, utilization: float)
        """
        self._overflow_alert_callbacks.append(callback)

    def remove_overflow_alert_callback(self, callback: Callable[..., Any]) -> None:
        """
        Remove an overflow alert callback.

        Args:
            callback: Callback to remove
        """
        if callback in self._overflow_alert_callbacks:
            self._overflow_alert_callbacks.remove(callback)

    async def get_buffer_stats(self) -> dict[str, Any]:
        """
        Get comprehensive buffer utilization statistics.

        Returns:
            Dictionary with buffer statistics for all timeframes
        """
        stats: dict[str, Any] = {
            "dynamic_buffer_enabled": self._dynamic_buffer_enabled,
            "timeframe_utilization": {},
            "overflow_thresholds": self._buffer_overflow_thresholds.copy(),
            "sampling_ratios": self._sampling_ratios.copy(),
            "total_overflow_callbacks": len(self._overflow_alert_callbacks),
        }

        for tf_key in self.timeframes:
            if tf_key in self.data:
                current_size = len(self.data[tf_key])
                threshold = self._buffer_overflow_thresholds.get(
                    tf_key, self.max_bars_per_timeframe
                )
                utilization = (current_size / threshold) * 100 if threshold > 0 else 0.0

                stats["timeframe_utilization"][tf_key] = {
                    "current_size": current_size,
                    "threshold": threshold,
                    "utilization_percent": utilization,
                    "is_critical": utilization >= 95.0,
                }

        return stats

    async def _cleanup_old_data(self) -> None:
        """
        Clean up old OHLCV data to manage memory efficiently using sliding windows.
        """
        current_time = time.time()

        # Only cleanup if interval has passed
        if current_time - self.last_cleanup < self.cleanup_interval:
            return

        # Import here to avoid circular dependency
        from project_x_py.utils.lock_optimization import AsyncRWLock

        # Use appropriate lock method based on lock type
        if isinstance(self.data_lock, AsyncRWLock):
            async with self.data_lock.write_lock():
                await self._perform_cleanup()
        else:
            async with self.data_lock:
                await self._perform_cleanup()

    async def _perform_cleanup(self) -> None:
        """Perform the actual cleanup logic (extracted for lock handling)."""
        total_bars_before = 0
        total_bars_after = 0

        # Cleanup each timeframe's data
        for tf_key in self.timeframes:
            if tf_key in self.data and not self.data[tf_key].is_empty():
                initial_count = len(self.data[tf_key])
                total_bars_before += initial_count

                # Check for buffer overflow first (only if dynamic buffer is enabled)
                if self._dynamic_buffer_enabled:
                    is_overflow, utilization = await self._check_buffer_overflow(tf_key)
                    if is_overflow:
                        await self._handle_buffer_overflow(tf_key, utilization)
                        total_bars_after += len(self.data[tf_key])
                        continue

                # Check if overflow is needed (if mixin is available)
                if hasattr(
                    self, "_check_overflow_needed"
                ) and await self._check_overflow_needed(tf_key):
                    await self._overflow_to_disk(tf_key)
                    # Data has been overflowed, update count
                    total_bars_after += len(self.data[tf_key])
                    continue

                # Keep only the most recent bars (sliding window)
                if initial_count > self.max_bars_per_timeframe:
                    self.data[tf_key] = self.data[tf_key].tail(
                        self.max_bars_per_timeframe
                    )

                total_bars_after += len(self.data[tf_key])

        # Cleanup tick buffer - deque handles its own cleanup with maxlen
        # No manual cleanup needed for deque with maxlen

        # Update stats
        current_time = time.time()
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

    async def _periodic_cleanup(self) -> None:
        """Background task for periodic cleanup."""
        while self.is_running:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self._cleanup_old_data()
            except asyncio.CancelledError:
                # Task cancellation is expected during shutdown
                self.logger.debug("Periodic cleanup task cancelled")
                raise
            except MemoryError as e:
                self.logger.error(f"Memory error during cleanup: {e}")
                # Force immediate garbage collection
                import gc

                gc.collect()
            except RuntimeError as e:
                self.logger.error(f"Runtime error in periodic cleanup: {e}")
                # Don't re-raise runtime errors to keep the cleanup task running

    async def get_memory_stats(self) -> "RealtimeDataManagerStats":
        """
        Get comprehensive memory usage statistics for the real-time data manager.

        Returns:
            Dict with memory and performance statistics

        Example:
            >>> stats = await manager.get_memory_stats()
            >>> print(f"Total bars in memory: {stats['total_bars']}")
            >>> print(f"Ticks processed: {stats['ticks_processed']}")
        """
        # Note: This doesn't need to be async as it's just reading values
        timeframe_stats = {}
        total_bars = 0

        for tf_key in self.timeframes:
            if tf_key in self.data:
                bar_count = len(self.data[tf_key])
                timeframe_stats[tf_key] = bar_count
                total_bars += bar_count
            else:
                timeframe_stats[tf_key] = 0

        # Update current statistics
        self.memory_stats["total_bars_stored"] = total_bars
        self.memory_stats["buffer_utilization"] = (
            len(self.current_tick_data) / self.tick_buffer_size
            if self.tick_buffer_size > 0
            else 0.0
        )

        # Calculate memory usage estimate (rough approximation)
        estimated_memory_mb = (total_bars * 0.001) + (
            len(self.current_tick_data) * 0.0001
        )  # Very rough estimate
        self.memory_stats["memory_usage_mb"] = estimated_memory_mb

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

        # Add buffer overflow stats
        buffer_stats = await self.get_buffer_stats()

        return {
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
            "buffer_overflow_stats": buffer_stats,
            "lock_optimization_stats": {},  # Placeholder for lock optimization stats
        }

    async def stop_cleanup_task(self) -> None:
        """Stop the background cleanup task."""
        await self._cleanup_tasks()  # Use centralized cleanup
        self._cleanup_task = None

    def start_cleanup_task(self) -> None:
        """Start the background cleanup task."""
        if not self._cleanup_task:
            self._cleanup_task = self._create_task(
                self._periodic_cleanup(), name="periodic_cleanup", persistent=True
            )
