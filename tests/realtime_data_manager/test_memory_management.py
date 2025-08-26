"""
Comprehensive tests for realtime_data_manager.memory_management module.

Following project-x-py TDD methodology:
1. Write tests FIRST defining expected behavior
2. Test what code SHOULD do, not what it currently does
3. Fix implementation if tests reveal bugs
4. Never change tests to match broken code

Test Coverage Goals:
- MemoryManagementMixin cleanup functionality
- Buffer overflow handling and detection
- Dynamic buffer sizing and data sampling
- Memory statistics tracking and reporting
- Background cleanup task management
- Performance optimization with garbage collection
- Error handling and recovery mechanisms
"""

import asyncio
import gc
import pytest
import time
from unittest.mock import AsyncMock, Mock, patch, call
from datetime import datetime, timezone
from collections import deque

import polars as pl

from project_x_py.realtime_data_manager.memory_management import MemoryManagementMixin


class MockRealtimeDataManager(MemoryManagementMixin):
    """Mock class implementing MemoryManagementMixin for testing."""

    def __init__(self, max_bars=1000, tick_buffer_size=100, cleanup_interval=300):
        # Initialize required attributes
        self.logger = Mock()
        self.last_cleanup = 0.0
        self.cleanup_interval = cleanup_interval
        self.data_lock = asyncio.Lock()
        self.timeframes = {
            "1min": {"interval": 1, "unit": 2},  # 1 minute
            "5min": {"interval": 5, "unit": 2},  # 5 minutes
            "30sec": {"interval": 30, "unit": 1}, # 30 seconds
        }
        self.data = {
            "1min": pl.DataFrame(),
            "5min": pl.DataFrame(),
            "30sec": pl.DataFrame(),
        }
        self.max_bars_per_timeframe = max_bars
        self.current_tick_data = deque(maxlen=tick_buffer_size)
        self.tick_buffer_size = tick_buffer_size
        self.memory_stats = {
            "bars_processed": 0,
            "ticks_processed": 0,
            "quotes_processed": 0,
            "trades_processed": 0,
            "timeframe_stats": {},
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
            "bars_cleaned": 0,
            "last_cleanup": 0.0,
        }
        self.is_running = True
        self.last_bar_times = {}

        # Initialize parent
        super().__init__()

    # Mock methods for statistics
    async def increment(self, metric, value=1):
        """Mock increment method."""
        pass


class TestMemoryManagementMixinBasicFunctionality:
    """Test basic memory management functionality."""

    @pytest.fixture
    def memory_manager(self):
        """MemoryManagementMixin instance for testing."""
        return MockRealtimeDataManager()

    def test_initialization(self, memory_manager):
        """Test proper initialization of memory management attributes."""
        # Should initialize cleanup task as None
        assert memory_manager._cleanup_task is None

        # Should initialize buffer overflow attributes
        assert hasattr(memory_manager, '_buffer_overflow_thresholds')
        assert hasattr(memory_manager, '_dynamic_buffer_enabled')
        assert hasattr(memory_manager, '_overflow_alert_callbacks')
        assert hasattr(memory_manager, '_sampling_ratios')

        # Should have default values
        assert memory_manager._dynamic_buffer_enabled is True
        assert isinstance(memory_manager._overflow_alert_callbacks, list)
        assert len(memory_manager._overflow_alert_callbacks) == 0

    def test_configure_dynamic_buffer_sizing_enabled(self, memory_manager):
        """Test configuring dynamic buffer sizing with enabled state."""
        # Configure with enabled
        memory_manager.configure_dynamic_buffer_sizing(
            enabled=True,
            initial_thresholds={"1min": 500, "5min": 1000}
        )

        # Should enable dynamic buffering
        assert memory_manager._dynamic_buffer_enabled is True

        # Should set custom thresholds
        assert memory_manager._buffer_overflow_thresholds["1min"] == 500
        assert memory_manager._buffer_overflow_thresholds["5min"] == 1000

    def test_configure_dynamic_buffer_sizing_defaults(self, memory_manager):
        """Test configuring dynamic buffer sizing with default thresholds."""
        # Configure without custom thresholds
        memory_manager.configure_dynamic_buffer_sizing(enabled=True)

        # Should set default thresholds based on timeframe unit
        assert memory_manager._buffer_overflow_thresholds["30sec"] == 5000  # seconds
        assert memory_manager._buffer_overflow_thresholds["1min"] == 2000   # minutes
        assert memory_manager._buffer_overflow_thresholds["5min"] == 2000   # minutes

    def test_configure_dynamic_buffer_sizing_disabled(self, memory_manager):
        """Test disabling dynamic buffer sizing."""
        memory_manager.configure_dynamic_buffer_sizing(enabled=False)

        assert memory_manager._dynamic_buffer_enabled is False


class TestMemoryManagementMixinBufferOverflow:
    """Test buffer overflow detection and handling."""

    @pytest.fixture
    def memory_manager(self):
        """MemoryManagementMixin instance with configured buffer."""
        manager = MockRealtimeDataManager(max_bars=100)
        manager.configure_dynamic_buffer_sizing(enabled=True)
        return manager

    @pytest.mark.asyncio
    async def test_check_buffer_overflow_no_data(self, memory_manager):
        """Test buffer overflow check with no data."""
        is_overflow, utilization = await memory_manager._check_buffer_overflow("1min")

        # Should return no overflow for empty data
        assert is_overflow is False
        assert utilization == 0.0

    @pytest.mark.asyncio
    async def test_check_buffer_overflow_normal_usage(self, memory_manager):
        """Test buffer overflow check with normal usage."""
        # Create sample data (50 bars, threshold is 2000, so ~2.5% utilization)
        sample_data = pl.DataFrame({
            "timestamp": [datetime.now(timezone.utc) for _ in range(50)],
            "open": [100.0] * 50,
            "high": [101.0] * 50,
            "low": [99.0] * 50,
            "close": [100.5] * 50,
            "volume": [1000] * 50,
        })
        memory_manager.data["1min"] = sample_data

        is_overflow, utilization = await memory_manager._check_buffer_overflow("1min")

        # Should not trigger overflow at low utilization
        assert is_overflow is False
        assert utilization < 95.0
        assert utilization > 0.0

    @pytest.mark.asyncio
    async def test_check_buffer_overflow_critical_usage(self, memory_manager):
        """Test buffer overflow check at critical usage level."""
        # Create data that exceeds 95% of threshold (2000 * 0.96 = 1920 bars)
        sample_data = pl.DataFrame({
            "timestamp": [datetime.now(timezone.utc) for _ in range(1920)],
            "open": [100.0] * 1920,
            "high": [101.0] * 1920,
            "low": [99.0] * 1920,
            "close": [100.5] * 1920,
            "volume": [1000] * 1920,
        })
        memory_manager.data["1min"] = sample_data

        is_overflow, utilization = await memory_manager._check_buffer_overflow("1min")

        # Should trigger overflow at high utilization
        assert is_overflow is True
        assert utilization >= 95.0

    @pytest.mark.asyncio
    async def test_handle_buffer_overflow_alert_callbacks(self, memory_manager):
        """Test overflow handling triggers alert callbacks."""
        # Add mock callbacks
        sync_callback = Mock()
        async_callback = AsyncMock()

        memory_manager.add_overflow_alert_callback(sync_callback)
        memory_manager.add_overflow_alert_callback(async_callback)

        # Trigger overflow handling
        await memory_manager._handle_buffer_overflow("1min", 97.5)

        # Should call both callbacks
        sync_callback.assert_called_once_with("1min", 97.5)
        async_callback.assert_called_once_with("1min", 97.5)

    @pytest.mark.asyncio
    async def test_handle_buffer_overflow_with_error_callback(self, memory_manager):
        """Test overflow handling with failing callback."""
        # Add callback that raises error
        failing_callback = Mock(side_effect=Exception("Callback error"))
        working_callback = Mock()

        memory_manager.add_overflow_alert_callback(failing_callback)
        memory_manager.add_overflow_alert_callback(working_callback)

        # Should handle error gracefully
        await memory_manager._handle_buffer_overflow("1min", 97.5)

        # Both callbacks should be called, error should be logged
        failing_callback.assert_called_once()
        working_callback.assert_called_once()
        memory_manager.logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_handle_buffer_overflow_applies_sampling(self, memory_manager):
        """Test overflow handling applies data sampling."""
        # Create large dataset
        sample_data = pl.DataFrame({
            "timestamp": [datetime.now(timezone.utc) for _ in range(1000)],
            "open": [100.0 + i * 0.1 for i in range(1000)],
            "high": [101.0 + i * 0.1 for i in range(1000)],
            "low": [99.0 + i * 0.1 for i in range(1000)],
            "close": [100.5 + i * 0.1 for i in range(1000)],
            "volume": [1000] * 1000,
        })
        memory_manager.data["1min"] = sample_data

        # Trigger overflow handling
        await memory_manager._handle_buffer_overflow("1min", 97.5)

        # Should reduce data size
        final_size = len(memory_manager.data["1min"])
        expected_target = int(memory_manager.max_bars_per_timeframe * 0.7)  # 70% of max
        assert final_size <= expected_target
        assert final_size < 1000  # Should be reduced from original


class TestMemoryManagementMixinDataSampling:
    """Test data sampling functionality."""

    @pytest.fixture
    def memory_manager(self):
        """MemoryManagementMixin instance for testing."""
        manager = MockRealtimeDataManager(max_bars=100)
        manager.configure_dynamic_buffer_sizing(enabled=True)
        return manager

    @pytest.mark.asyncio
    async def test_apply_data_sampling_empty_data(self, memory_manager):
        """Test data sampling with empty dataset."""
        # Should handle empty data gracefully
        await memory_manager._apply_data_sampling("1min")

        # Should remain empty
        assert memory_manager.data["1min"].is_empty()

    @pytest.mark.asyncio
    async def test_apply_data_sampling_small_dataset(self, memory_manager):
        """Test data sampling with dataset smaller than target."""
        # Create small dataset (50 bars, target is 70% of 100 = 70)
        sample_data = pl.DataFrame({
            "timestamp": [datetime.now(timezone.utc) for _ in range(50)],
            "open": [100.0] * 50,
            "high": [101.0] * 50,
            "low": [99.0] * 50,
            "close": [100.5] * 50,
            "volume": [1000] * 50,
        })
        memory_manager.data["1min"] = sample_data

        await memory_manager._apply_data_sampling("1min")

        # Should keep all data (no sampling needed)
        assert len(memory_manager.data["1min"]) == 50

    @pytest.mark.asyncio
    async def test_apply_data_sampling_large_dataset(self, memory_manager):
        """Test data sampling with dataset requiring reduction."""
        # Create large dataset (200 bars, target is 70% of 100 = 70)
        sample_data = pl.DataFrame({
            "timestamp": [datetime.now(timezone.utc) for _ in range(200)],
            "open": [100.0 + i * 0.1 for i in range(200)],
            "high": [101.0 + i * 0.1 for i in range(200)],
            "low": [99.0 + i * 0.1 for i in range(200)],
            "close": [100.5 + i * 0.1 for i in range(200)],
            "volume": [1000] * 200,
        })
        memory_manager.data["1min"] = sample_data

        await memory_manager._apply_data_sampling("1min")

        # Should reduce to target size (70% of max = 70)
        final_size = len(memory_manager.data["1min"])
        target_size = int(memory_manager.max_bars_per_timeframe * 0.7)
        assert final_size == target_size
        assert final_size < 200

    @pytest.mark.asyncio
    async def test_apply_data_sampling_preserves_recent_data(self, memory_manager):
        """Test data sampling preserves most recent data."""
        # Create dataset with identifiable recent data
        recent_timestamp = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        older_timestamp = datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)

        sample_data = pl.DataFrame({
            "timestamp": [older_timestamp] * 150 + [recent_timestamp] * 50,
            "open": [100.0] * 150 + [200.0] * 50,  # Recent data has different prices
            "high": [101.0] * 150 + [201.0] * 50,
            "low": [99.0] * 150 + [199.0] * 50,
            "close": [100.5] * 150 + [200.5] * 50,
            "volume": [1000] * 200,
        })
        memory_manager.data["1min"] = sample_data
        memory_manager.last_bar_times["1min"] = recent_timestamp

        await memory_manager._apply_data_sampling("1min")

        # Check that recent data is preserved
        final_data = memory_manager.data["1min"]
        recent_bars = final_data.filter(pl.col("timestamp") == recent_timestamp)

        # Should preserve some/all recent data
        assert len(recent_bars) > 0

        # Should have correct sampling ratio
        assert "1min" in memory_manager._sampling_ratios
        assert 0 < memory_manager._sampling_ratios["1min"] < 1

    @pytest.mark.asyncio
    async def test_apply_data_sampling_updates_last_bar_time(self, memory_manager):
        """Test data sampling updates last bar time correctly."""
        recent_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        # Create dataset with recent data
        sample_data = pl.DataFrame({
            "timestamp": [recent_time],
            "open": [100.0],
            "high": [101.0],
            "low": [99.0],
            "close": [100.5],
            "volume": [1000],
        })
        memory_manager.data["1min"] = sample_data
        memory_manager.last_bar_times["1min"] = recent_time

        await memory_manager._apply_data_sampling("1min")

        # Should maintain last bar time
        assert memory_manager.last_bar_times["1min"] == recent_time


class TestMemoryManagementMixinCallbackManagement:
    """Test overflow alert callback management."""

    @pytest.fixture
    def memory_manager(self):
        """MemoryManagementMixin instance for testing."""
        return MockRealtimeDataManager()

    def test_add_overflow_alert_callback(self, memory_manager):
        """Test adding overflow alert callbacks."""
        callback1 = Mock()
        callback2 = Mock()

        memory_manager.add_overflow_alert_callback(callback1)
        memory_manager.add_overflow_alert_callback(callback2)

        # Should add both callbacks
        assert len(memory_manager._overflow_alert_callbacks) == 2
        assert callback1 in memory_manager._overflow_alert_callbacks
        assert callback2 in memory_manager._overflow_alert_callbacks

    def test_remove_overflow_alert_callback(self, memory_manager):
        """Test removing overflow alert callbacks."""
        callback1 = Mock()
        callback2 = Mock()

        memory_manager.add_overflow_alert_callback(callback1)
        memory_manager.add_overflow_alert_callback(callback2)

        # Remove one callback
        memory_manager.remove_overflow_alert_callback(callback1)

        # Should remove specified callback only
        assert len(memory_manager._overflow_alert_callbacks) == 1
        assert callback1 not in memory_manager._overflow_alert_callbacks
        assert callback2 in memory_manager._overflow_alert_callbacks

    def test_remove_nonexistent_callback(self, memory_manager):
        """Test removing callback that doesn't exist."""
        callback1 = Mock()
        callback2 = Mock()

        memory_manager.add_overflow_alert_callback(callback1)

        # Try to remove callback that wasn't added
        memory_manager.remove_overflow_alert_callback(callback2)

        # Should not affect existing callbacks
        assert len(memory_manager._overflow_alert_callbacks) == 1
        assert callback1 in memory_manager._overflow_alert_callbacks


class TestMemoryManagementMixinCleanupOperations:
    """Test cleanup operations and background tasks."""

    @pytest.fixture
    def memory_manager(self):
        """MemoryManagementMixin instance for testing."""
        return MockRealtimeDataManager(max_bars=50, cleanup_interval=0.1)

    @pytest.mark.asyncio
    async def test_cleanup_old_data_interval_check(self, memory_manager):
        """Test cleanup respects interval timing."""
        # Set recent cleanup time
        memory_manager.last_cleanup = time.time()

        # Mock the actual cleanup
        memory_manager._perform_cleanup = AsyncMock()

        # Try to cleanup immediately
        await memory_manager._cleanup_old_data()

        # Should not perform cleanup due to interval
        memory_manager._perform_cleanup.assert_not_called()

    @pytest.mark.asyncio
    async def test_cleanup_old_data_interval_passed(self, memory_manager):
        """Test cleanup executes when interval has passed."""
        # Set old cleanup time
        memory_manager.last_cleanup = time.time() - 1.0  # 1 second ago

        # Mock the actual cleanup
        memory_manager._perform_cleanup = AsyncMock()

        await memory_manager._cleanup_old_data()

        # Should perform cleanup
        memory_manager._perform_cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_perform_cleanup_sliding_window(self, memory_manager):
        """Test cleanup implements sliding window correctly."""
        # Disable dynamic buffer sizing to test pure sliding window behavior
        memory_manager._dynamic_buffer_enabled = False
        memory_manager._buffer_overflow_thresholds.clear()

        # Create data exceeding max_bars_per_timeframe
        large_data = pl.DataFrame({
            "timestamp": [datetime.now(timezone.utc) for _ in range(100)],
            "open": [100.0] * 100,
            "high": [101.0] * 100,
            "low": [99.0] * 100,
            "close": [100.5] * 100,
            "volume": [1000] * 100,
        })
        memory_manager.data["1min"] = large_data

        await memory_manager._perform_cleanup()

        # Should keep only max_bars_per_timeframe (50)
        final_size = len(memory_manager.data["1min"])
        assert final_size == memory_manager.max_bars_per_timeframe

        # Should update memory stats
        assert memory_manager.memory_stats["bars_cleaned"] > 0
        assert memory_manager.memory_stats["total_bars"] == final_size
        assert memory_manager.memory_stats["last_cleanup"] > 0

    @pytest.mark.asyncio
    async def test_perform_cleanup_buffer_overflow_handling(self, memory_manager):
        """Test cleanup handles buffer overflow correctly."""
        # Configure overflow detection
        memory_manager.configure_dynamic_buffer_sizing(enabled=True)
        memory_manager._buffer_overflow_thresholds["1min"] = 10  # Very low threshold

        # Create data that will trigger overflow
        overflow_data = pl.DataFrame({
            "timestamp": [datetime.now(timezone.utc) for _ in range(15)],
            "open": [100.0] * 15,
            "high": [101.0] * 15,
            "low": [99.0] * 15,
            "close": [100.5] * 15,
            "volume": [1000] * 15,
        })
        memory_manager.data["1min"] = overflow_data

        # Mock overflow handling
        memory_manager._handle_buffer_overflow = AsyncMock()

        await memory_manager._perform_cleanup()

        # Should trigger overflow handling
        memory_manager._handle_buffer_overflow.assert_called()

    @pytest.mark.asyncio
    async def test_perform_cleanup_garbage_collection(self, memory_manager):
        """Test cleanup triggers garbage collection when needed."""
        # Create data that will be cleaned
        large_data = pl.DataFrame({
            "timestamp": [datetime.now(timezone.utc) for _ in range(100)],
            "open": [100.0] * 100,
            "high": [101.0] * 100,
            "low": [99.0] * 100,
            "close": [100.5] * 100,
            "volume": [1000] * 100,
        })
        memory_manager.data["1min"] = large_data

        # Mock garbage collection
        with patch('gc.collect') as mock_gc:
            await memory_manager._perform_cleanup()

            # Should call garbage collection after cleanup
            mock_gc.assert_called_once()

    @pytest.mark.asyncio
    async def test_periodic_cleanup_task_lifecycle(self, memory_manager):
        """Test periodic cleanup task starts and stops correctly."""
        # Start cleanup task
        memory_manager.start_cleanup_task()

        # Should create task
        assert memory_manager._cleanup_task is not None
        assert not memory_manager._cleanup_task.done()

        # Stop cleanup task
        await memory_manager.stop_cleanup_task()

        # Should clean up task
        assert memory_manager._cleanup_task is None

    @pytest.mark.asyncio
    async def test_periodic_cleanup_error_handling(self, memory_manager):
        """Test periodic cleanup handles errors gracefully."""
        # Mock cleanup to raise MemoryError
        memory_manager._cleanup_old_data = AsyncMock(side_effect=MemoryError("Out of memory"))

        # Start cleanup task
        memory_manager.start_cleanup_task()

        # Allow task to run briefly
        await asyncio.sleep(0.2)

        # Should log error but continue running
        memory_manager.logger.error.assert_called()
        assert not memory_manager._cleanup_task.done()

        # Clean up
        await memory_manager.stop_cleanup_task()


class TestMemoryManagementMixinStatistics:
    """Test memory statistics and reporting."""

    @pytest.fixture
    def memory_manager(self):
        """MemoryManagementMixin instance with sample data."""
        manager = MockRealtimeDataManager()

        # Add sample data
        sample_data = pl.DataFrame({
            "timestamp": [datetime.now(timezone.utc) for _ in range(50)],
            "open": [100.0] * 50,
            "high": [101.0] * 50,
            "low": [99.0] * 50,
            "close": [100.5] * 50,
            "volume": [1000] * 50,
        })
        manager.data["1min"] = sample_data
        manager.data["5min"] = sample_data.clone()

        # Add sample tick data
        for i in range(25):
            manager.current_tick_data.append({"price": 100.0 + i, "volume": 10})

        return manager

    @pytest.mark.asyncio
    async def test_get_buffer_stats(self, memory_manager):
        """Test comprehensive buffer statistics."""
        memory_manager.configure_dynamic_buffer_sizing(enabled=True)

        stats = await memory_manager.get_buffer_stats()

        # Should include all expected fields
        assert "dynamic_buffer_enabled" in stats
        assert "timeframe_utilization" in stats
        assert "overflow_thresholds" in stats
        assert "sampling_ratios" in stats
        assert "total_overflow_callbacks" in stats

        # Should report correct values
        assert stats["dynamic_buffer_enabled"] is True
        assert stats["total_overflow_callbacks"] == 0

        # Should include utilization for each timeframe
        for tf_key in memory_manager.timeframes:
            assert tf_key in stats["timeframe_utilization"]
            tf_stats = stats["timeframe_utilization"][tf_key]
            assert "current_size" in tf_stats
            assert "threshold" in tf_stats
            assert "utilization_percent" in tf_stats
            assert "is_critical" in tf_stats

    @pytest.mark.asyncio
    async def test_get_memory_stats_comprehensive(self, memory_manager):
        """Test comprehensive memory statistics reporting."""
        # Update some stats for testing
        memory_manager.memory_stats["ticks_processed"] = 1000
        memory_manager.memory_stats["bars_processed"] = 100

        stats = await memory_manager.get_memory_stats()

        # Should include all expected statistics fields
        required_fields = [
            "bars_processed", "ticks_processed", "quotes_processed", "trades_processed",
            "timeframe_stats", "avg_processing_time_ms", "data_latency_ms",
            "buffer_utilization", "total_bars_stored", "memory_usage_mb",
            "compression_ratio", "updates_per_minute", "last_update",
            "data_freshness_seconds", "data_validation_errors", "connection_interruptions",
            "recovery_attempts", "overflow_stats", "buffer_overflow_stats",
            "lock_optimization_stats"
        ]

        for field in required_fields:
            assert field in stats, f"Missing field: {field}"

        # Should calculate buffer utilization correctly
        expected_utilization = len(memory_manager.current_tick_data) / memory_manager.tick_buffer_size
        assert stats["buffer_utilization"] == expected_utilization

        # Should calculate total bars correctly
        expected_total = sum(len(df) for df in memory_manager.data.values())
        assert stats["total_bars_stored"] == expected_total

        # Should estimate memory usage
        assert stats["memory_usage_mb"] >= 0

    @pytest.mark.asyncio
    async def test_get_memory_stats_with_overflow_stats(self, memory_manager):
        """Test memory stats include overflow statistics."""
        # Mock overflow stats method
        mock_overflow_stats = {"disk_overflow_count": 5, "disk_usage_mb": 100.0}
        memory_manager.get_overflow_stats = AsyncMock(return_value=mock_overflow_stats)

        stats = await memory_manager.get_memory_stats()

        # Should include overflow stats
        assert stats["overflow_stats"] == mock_overflow_stats

        # Should include buffer overflow stats
        assert "buffer_overflow_stats" in stats
        assert isinstance(stats["buffer_overflow_stats"], dict)

    @pytest.mark.asyncio
    async def test_get_memory_stats_error_handling(self, memory_manager):
        """Test memory stats gracefully handle errors."""
        # Mock overflow stats to raise error
        memory_manager.get_overflow_stats = AsyncMock(side_effect=Exception("Stats error"))

        stats = await memory_manager.get_memory_stats()

        # Should handle error gracefully
        assert stats["overflow_stats"] == {}

        # Other stats should still work
        assert "total_bars_stored" in stats
        assert "buffer_utilization" in stats


class TestMemoryManagementMixinIntegration:
    """Test integration scenarios and edge cases."""

    @pytest.fixture
    def memory_manager(self):
        """MemoryManagementMixin instance for integration testing."""
        return MockRealtimeDataManager(max_bars=100, cleanup_interval=0.05)

    @pytest.mark.asyncio
    async def test_full_memory_management_lifecycle(self, memory_manager):
        """Test complete memory management lifecycle."""
        # Configure dynamic buffer sizing
        memory_manager.configure_dynamic_buffer_sizing(enabled=True)

        # Add overflow alert callback
        alert_callback = AsyncMock()
        memory_manager.add_overflow_alert_callback(alert_callback)

        # Start cleanup task
        memory_manager.start_cleanup_task()

        # Create large dataset that will trigger overflow
        large_data = pl.DataFrame({
            "timestamp": [datetime.now(timezone.utc) for _ in range(3000)],
            "open": [100.0 + i * 0.01 for i in range(3000)],
            "high": [101.0 + i * 0.01 for i in range(3000)],
            "low": [99.0 + i * 0.01 for i in range(3000)],
            "close": [100.5 + i * 0.01 for i in range(3000)],
            "volume": [1000] * 3000,
        })
        memory_manager.data["1min"] = large_data

        # Force cleanup (wait for interval)
        memory_manager.last_cleanup = 0.0  # Force cleanup
        await memory_manager._cleanup_old_data()

        # Should reduce data size
        final_size = len(memory_manager.data["1min"])
        assert final_size < 3000

        # Should have updated stats
        stats = await memory_manager.get_memory_stats()
        assert stats["total_bars_stored"] == final_size
        assert stats["bars_processed"] >= 0

        # Clean up
        await memory_manager.stop_cleanup_task()

    @pytest.mark.asyncio
    async def test_concurrent_cleanup_and_data_access(self, memory_manager):
        """Test concurrent cleanup and data access operations."""
        # Create data
        sample_data = pl.DataFrame({
            "timestamp": [datetime.now(timezone.utc) for _ in range(200)],
            "open": [100.0] * 200,
            "high": [101.0] * 200,
            "low": [99.0] * 200,
            "close": [100.5] * 200,
            "volume": [1000] * 200,
        })
        memory_manager.data["1min"] = sample_data

        # Force cleanup time
        memory_manager.last_cleanup = 0.0

        # Run cleanup and stats gathering concurrently
        cleanup_task = asyncio.create_task(memory_manager._cleanup_old_data())
        stats_task = asyncio.create_task(memory_manager.get_memory_stats())
        buffer_stats_task = asyncio.create_task(memory_manager.get_buffer_stats())

        # Should complete without errors
        results = await asyncio.gather(cleanup_task, stats_task, buffer_stats_task, return_exceptions=True)

        # Check no exceptions occurred
        for result in results:
            assert not isinstance(result, Exception), f"Unexpected error: {result}"

        # Should have valid stats
        stats, buffer_stats = results[1], results[2]
        assert isinstance(stats, dict)
        assert isinstance(buffer_stats, dict)

    @pytest.mark.asyncio
    async def test_memory_pressure_scenario(self, memory_manager):
        """Test behavior under memory pressure conditions."""
        # Configure low thresholds to simulate pressure
        memory_manager.configure_dynamic_buffer_sizing(
            enabled=True,
            initial_thresholds={"1min": 50, "5min": 50, "30sec": 50}
        )

        # Create data for all timeframes
        for tf_key in memory_manager.timeframes:
            pressure_data = pl.DataFrame({
                "timestamp": [datetime.now(timezone.utc) for _ in range(75)],
                "open": [100.0] * 75,
                "high": [101.0] * 75,
                "low": [99.0] * 75,
                "close": [100.5] * 75,
                "volume": [1000] * 75,
            })
            memory_manager.data[tf_key] = pressure_data

        # Force cleanup
        memory_manager.last_cleanup = 0.0
        await memory_manager._cleanup_old_data()

        # All timeframes should be reduced
        for tf_key in memory_manager.timeframes:
            final_size = len(memory_manager.data[tf_key])
            assert final_size < 75, f"Timeframe {tf_key} not reduced: {final_size}"

        # Should maintain consistent data structures
        stats = await memory_manager.get_memory_stats()
        assert stats["total_bars_stored"] > 0
        assert all(isinstance(v, (int, float, str, type(None))) for v in stats.values() if not isinstance(v, dict))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
