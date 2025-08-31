"""
Tests for bounded statistics implementation to prevent memory leaks.

Author: @TexasCoding
Date: 2025-08-22

Test Coverage:
    - BoundedCounter functionality and rotation
    - CircularBuffer fixed-size behavior
    - CleanupScheduler automatic cleanup
    - BoundedStatisticsMixin integration
    - Memory usage validation
    - High-frequency update performance
    - RealtimeDataManager integration
    - Configuration options
"""

import asyncio
import time
from unittest.mock import AsyncMock

import pytest

from project_x_py.statistics.bounded_statistics import (
    BoundedCounter,
    BoundedStatisticsMixin,
    CircularBuffer,
    CleanupScheduler,
    MetricSummary,
    TimestampedValue,
)


class TestTimestampedValue:
    """Test TimestampedValue dataclass."""

    def test_timestamped_value_creation(self):
        """Test creating TimestampedValue."""
        value = TimestampedValue(123.456, 42.0)
        assert value.timestamp == 123.456
        assert value.value == 42.0

    def test_timestamped_value_auto_timestamp(self):
        """Test automatic timestamp assignment."""
        before_time = time.time()
        value = TimestampedValue(0, 42.0)  # Invalid timestamp should be auto-set
        after_time = time.time()

        # Should have been auto-set to current time
        assert before_time <= value.timestamp <= after_time
        assert value.value == 42.0


class TestMetricSummary:
    """Test MetricSummary dataclass."""

    def test_metric_summary_creation(self):
        """Test creating MetricSummary."""
        from datetime import datetime

        start_time = datetime.now()
        end_time = datetime.now()

        summary = MetricSummary(
            period_start=start_time,
            period_end=end_time,
            count=100,
            sum_value=1000.0,
            min_value=5.0,
            max_value=25.0,
            avg_value=10.0,
        )

        assert summary.count == 100
        assert summary.sum_value == 1000.0
        assert summary.avg_value == 10.0

    def test_metric_summary_to_dict(self):
        """Test converting MetricSummary to dictionary."""
        from datetime import datetime

        start_time = datetime(2025, 1, 1, 12, 0, 0)
        end_time = datetime(2025, 1, 1, 13, 0, 0)

        summary = MetricSummary(
            period_start=start_time,
            period_end=end_time,
            count=50,
            sum_value=500.0,
            min_value=2.0,
            max_value=20.0,
            avg_value=10.0,
        )

        result = summary.to_dict()

        assert result["count"] == 50
        assert result["sum"] == 500.0
        assert result["avg"] == 10.0
        assert "period_start" in result
        assert "period_end" in result


class TestBoundedCounter:
    """Test BoundedCounter functionality."""

    @pytest.mark.asyncio
    async def test_bounded_counter_basic_operations(self):
        """Test basic counter operations."""
        counter = BoundedCounter(max_size=100, ttl_seconds=3600.0, name="test_counter")

        # Test increment
        await counter.increment(5.0)
        await counter.increment(3.0)

        current_sum = await counter.get_current_sum()
        current_count = await counter.get_current_count()

        assert current_sum == 8.0
        assert current_count == 2

    @pytest.mark.asyncio
    async def test_bounded_counter_size_limit(self):
        """Test that counter respects size limits."""
        counter = BoundedCounter(max_size=3, ttl_seconds=3600.0, name="limited_counter")

        # Add more items than the limit
        for i in range(5):
            await counter.increment(float(i + 1))

        # Should only have the last 3 items due to deque maxlen
        current_count = await counter.get_current_count()
        current_sum = await counter.get_current_sum()

        assert current_count == 3
        assert current_sum == 12.0  # 3 + 4 + 5

    @pytest.mark.asyncio
    async def test_bounded_counter_ttl_expiration(self):
        """Test TTL-based expiration."""
        counter = BoundedCounter(max_size=100, ttl_seconds=0.1, name="ttl_counter")

        # Add some values
        await counter.increment(10.0)
        await counter.increment(20.0)

        initial_sum = await counter.get_current_sum()
        assert initial_sum == 30.0

        # Wait for TTL expiration
        await asyncio.sleep(0.2)

        # Access should trigger cleanup of expired values
        expired_sum = await counter.get_current_sum()
        expired_count = await counter.get_current_count()

        assert expired_sum == 0.0
        assert expired_count == 0

    @pytest.mark.asyncio
    async def test_bounded_counter_statistics(self):
        """Test getting comprehensive statistics."""
        counter = BoundedCounter(max_size=100, ttl_seconds=3600.0, name="stats_counter")

        # Add some test data
        for i in range(5):
            await counter.increment(float(i + 1))

        stats = await counter.get_statistics()

        assert stats["current_count"] == 5
        assert stats["current_sum"] == 15.0  # 1+2+3+4+5
        assert stats["current_avg"] == 3.0
        assert stats["current_min"] == 1.0
        assert stats["current_max"] == 5.0
        assert stats["total_lifetime_count"] == 5
        assert stats["total_lifetime_sum"] == 15.0
        assert "memory_usage_bytes" in stats


class TestCircularBuffer:
    """Test CircularBuffer functionality."""

    @pytest.mark.asyncio
    async def test_circular_buffer_basic_operations(self):
        """Test basic buffer operations."""
        buffer = CircularBuffer(max_size=5, name="test_buffer")

        # Add some values
        for i in range(3):
            await buffer.append(float(i + 1))

        size = await buffer.get_size()
        assert size == 3

        # Test getting recent values
        recent = await buffer.get_recent(3600.0)  # Last hour
        assert len(recent) == 3
        assert recent == [1.0, 2.0, 3.0]

    @pytest.mark.asyncio
    async def test_circular_buffer_size_limit(self):
        """Test that buffer respects size limits."""
        buffer = CircularBuffer(max_size=3, name="limited_buffer")

        # Add more values than the limit
        for i in range(5):
            await buffer.append(float(i + 1))

        size = await buffer.get_size()
        assert size == 3

        # Should have the last 3 values due to circular nature
        recent = await buffer.get_recent(3600.0)
        assert recent == [3.0, 4.0, 5.0]

    @pytest.mark.asyncio
    async def test_circular_buffer_time_window(self):
        """Test time window queries."""
        buffer = CircularBuffer(max_size=100, name="time_buffer")

        current_time = time.time()

        # Add values with specific timestamps
        await buffer.append(10.0, current_time - 10)  # 10 seconds ago
        await buffer.append(20.0, current_time - 5)  # 5 seconds ago
        await buffer.append(30.0, current_time)  # Now

        # Get values from last 7 seconds
        recent = await buffer.get_recent(7.0)
        assert len(recent) == 2
        assert recent == [20.0, 30.0]

        # Get values from last 3 seconds
        very_recent = await buffer.get_recent(3.0)
        assert len(very_recent) == 1
        assert very_recent == [30.0]

    @pytest.mark.asyncio
    async def test_circular_buffer_statistics(self):
        """Test buffer statistics."""
        buffer = CircularBuffer(max_size=100, name="stats_buffer")

        # Add test data
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        for value in values:
            await buffer.append(value)

        stats = await buffer.get_statistics()

        assert stats["count"] == 5
        assert stats["sum"] == 15.0
        assert stats["avg"] == 3.0
        assert stats["min"] == 1.0
        assert stats["max"] == 5.0
        assert stats["std_dev"] > 0  # Should have some variance
        assert "memory_usage_bytes" in stats

        # Test empty buffer statistics
        empty_buffer = CircularBuffer(max_size=10, name="empty_buffer")
        empty_stats = await empty_buffer.get_statistics()

        assert empty_stats["count"] == 0
        assert empty_stats["sum"] == 0.0
        assert empty_stats["avg"] == 0.0


class TestCleanupScheduler:
    """Test CleanupScheduler functionality."""

    @pytest.mark.asyncio
    async def test_cleanup_scheduler_basic_operations(self):
        """Test basic scheduler operations."""
        scheduler = CleanupScheduler(
            cleanup_interval_seconds=0.1,  # Fast for testing
            memory_check_interval_seconds=0.05,
        )

        # Register a cleanup function
        cleanup_called = False

        async def test_cleanup():
            nonlocal cleanup_called
            cleanup_called = True

        scheduler.register_cleanup_function("test_cleanup", test_cleanup)

        # Start scheduler
        await scheduler.start()

        # Wait for cleanup to be called
        await asyncio.sleep(0.2)

        # Stop scheduler
        await scheduler.stop()

        assert cleanup_called

    @pytest.mark.asyncio
    async def test_cleanup_scheduler_error_handling(self):
        """Test scheduler error handling."""
        scheduler = CleanupScheduler(cleanup_interval_seconds=0.1)

        # Register a cleanup function that raises an error
        async def failing_cleanup():
            raise RuntimeError("Test error")

        scheduler.register_cleanup_function("failing_cleanup", failing_cleanup)

        # Start scheduler - should not crash
        await scheduler.start()
        await asyncio.sleep(0.2)
        await scheduler.stop()

        # Should complete without raising the error

    @pytest.mark.asyncio
    async def test_cleanup_scheduler_multiple_functions(self):
        """Test scheduler with multiple cleanup functions."""
        scheduler = CleanupScheduler(cleanup_interval_seconds=0.1)

        call_count = {"func1": 0, "func2": 0}

        async def cleanup_func1():
            call_count["func1"] += 1

        async def cleanup_func2():
            call_count["func2"] += 1

        scheduler.register_cleanup_function("func1", cleanup_func1)
        scheduler.register_cleanup_function("func2", cleanup_func2)

        await scheduler.start()
        await asyncio.sleep(0.25)  # Allow multiple cycles
        await scheduler.stop()

        # Both functions should have been called
        assert call_count["func1"] > 0
        assert call_count["func2"] > 0


class TestBoundedStatisticsMixin:
    """Test BoundedStatisticsMixin functionality."""

    class TestComponent(BoundedStatisticsMixin):
        """Test component that uses BoundedStatisticsMixin."""

        def __init__(self, **kwargs):
            super().__init__(**kwargs)

    @pytest.mark.asyncio
    async def test_bounded_statistics_mixin_counters(self):
        """Test bounded counter functionality in mixin."""
        component = self.TestComponent(
            max_recent_metrics=100,
            cleanup_interval_minutes=60.0,  # Long interval for testing
        )

        # Test counter operations
        await component.increment_bounded("test_metric", 5.0)
        await component.increment_bounded("test_metric", 3.0)

        stats = await component.get_bounded_counter_stats("test_metric")
        assert stats is not None
        assert stats["current_sum"] == 8.0
        assert stats["current_count"] == 2

    @pytest.mark.asyncio
    async def test_bounded_statistics_mixin_gauges(self):
        """Test bounded gauge functionality in mixin."""
        component = self.TestComponent()

        # Test gauge operations
        await component.set_gauge_bounded("temperature", 25.5)
        await component.set_gauge_bounded("temperature", 26.0)
        await component.set_gauge_bounded("temperature", 24.8)

        stats = await component.get_bounded_gauge_stats("temperature")
        assert stats is not None
        assert stats["count"] == 3
        assert stats["avg"] == pytest.approx((25.5 + 26.0 + 24.8) / 3, rel=1e-2)

    @pytest.mark.asyncio
    async def test_bounded_statistics_mixin_timing(self):
        """Test bounded timing functionality in mixin."""
        component = self.TestComponent(timing_buffer_size=50)

        # Test timing operations
        await component.record_timing_bounded("api_call", 150.0)
        await component.record_timing_bounded("api_call", 200.0)
        await component.record_timing_bounded("api_call", 125.0)

        stats = await component.get_bounded_timing_stats("api_call")
        assert stats is not None
        assert stats["count"] == 3
        assert stats["avg"] == pytest.approx((150.0 + 200.0 + 125.0) / 3, rel=1e-2)
        assert stats["min"] == 125.0
        assert stats["max"] == 200.0

    @pytest.mark.asyncio
    async def test_bounded_statistics_mixin_comprehensive_stats(self):
        """Test getting all bounded statistics."""
        component = self.TestComponent()

        # Add various types of metrics
        await component.increment_bounded("requests", 10)
        await component.increment_bounded("errors", 2)
        await component.set_gauge_bounded("cpu_usage", 75.5)
        await component.record_timing_bounded("response_time", 250.0)

        all_stats = await component.get_all_bounded_stats()

        assert "counters" in all_stats
        assert "gauges" in all_stats
        assert "timing" in all_stats
        assert "memory_usage" in all_stats

        assert "requests" in all_stats["counters"]
        assert "errors" in all_stats["counters"]
        assert "cpu_usage" in all_stats["gauges"]
        assert "response_time" in all_stats["timing"]

        memory_info = all_stats["memory_usage"]
        assert "total_bytes" in memory_info
        assert "total_mb" in memory_info
        assert "num_counters" in memory_info

    @pytest.mark.asyncio
    async def test_bounded_statistics_memory_limits(self):
        """Test that bounded statistics respect memory limits."""
        component = self.TestComponent(
            max_recent_metrics=5,  # Very small limit for testing
            timing_buffer_size=3,
        )

        # Add more data than the limits
        for i in range(10):
            await component.increment_bounded("test_counter", float(i))
            await component.record_timing_bounded("test_timing", float(i * 10))

        # Check that limits are respected
        counter_stats = await component.get_bounded_counter_stats("test_counter")
        timing_stats = await component.get_bounded_timing_stats("test_timing")

        assert counter_stats["current_count"] <= 5  # Should be limited
        assert timing_stats["count"] <= 3  # Should be limited


class TestRealtimeDataManagerIntegration:
    """Test integration with RealtimeDataManager."""

    @pytest.mark.asyncio
    async def test_realtime_data_manager_bounded_stats_enabled(self):
        """Test RealtimeDataManager with bounded statistics enabled."""
        from project_x_py.realtime_data_manager.core import RealtimeDataManager

        # Create mock clients
        mock_project_x = AsyncMock()
        mock_realtime_client = AsyncMock()
        mock_event_bus = AsyncMock()

        config = {
            "use_bounded_statistics": True,
            "max_recent_metrics": 100,
            "cleanup_interval_minutes": 60.0,
        }

        manager = RealtimeDataManager(
            instrument="TEST",
            project_x=mock_project_x,
            realtime_client=mock_realtime_client,
            event_bus=mock_event_bus,
            config=config,
        )

        # Verify bounded statistics are enabled
        assert manager.is_bounded_statistics_enabled()

        # Test tracking methods use bounded statistics
        await manager.track_tick_processed()
        await manager.track_quote_processed()
        await manager.track_trade_processed()

        # Get bounded statistics
        bounded_stats = await manager.get_bounded_statistics()
        assert bounded_stats is not None
        assert "counters" in bounded_stats
        assert "ticks_processed" in bounded_stats["counters"]
        assert "quotes_processed" in bounded_stats["counters"]
        assert "trades_processed" in bounded_stats["counters"]

    @pytest.mark.asyncio
    async def test_realtime_data_manager_bounded_stats_disabled(self):
        """Test RealtimeDataManager with bounded statistics disabled."""
        from project_x_py.realtime_data_manager.core import RealtimeDataManager

        # Create mock clients
        mock_project_x = AsyncMock()
        mock_realtime_client = AsyncMock()
        mock_event_bus = AsyncMock()

        config = {"use_bounded_statistics": False}

        manager = RealtimeDataManager(
            instrument="TEST",
            project_x=mock_project_x,
            realtime_client=mock_realtime_client,
            event_bus=mock_event_bus,
            config=config,
        )

        # Verify bounded statistics are disabled
        assert not manager.is_bounded_statistics_enabled()

        # Get bounded statistics should return None
        bounded_stats = await manager.get_bounded_statistics()
        assert bounded_stats is None


class TestPerformanceAndMemory:
    """Test performance and memory characteristics."""

    @pytest.mark.asyncio
    async def test_high_frequency_updates(self):
        """Test performance with high-frequency updates."""
        counter = BoundedCounter(max_size=1000, ttl_seconds=3600.0, name="perf_counter")

        # Time high-frequency updates
        start_time = time.time()

        for _i in range(1000):
            await counter.increment(1.0)

        end_time = time.time()

        # Should complete in reasonable time (less than 1 second)
        duration = end_time - start_time
        assert duration < 1.0

        # Verify final state
        final_sum = await counter.get_current_sum()
        final_count = await counter.get_current_count()

        assert final_sum == 1000.0
        assert final_count == 1000

    @pytest.mark.asyncio
    async def test_memory_usage_bounded(self):
        """Test that memory usage remains bounded."""
        component = TestBoundedStatisticsMixin.TestComponent(
            max_recent_metrics=100, timing_buffer_size=50
        )

        # Add a large amount of data
        for i in range(5000):  # Much more than limits
            await component.increment_bounded("test_metric", 1.0)
            await component.record_timing_bounded("test_operation", float(i))

            # Occasionally check memory usage
            if i % 1000 == 0:
                memory_info = await component._get_bounded_memory_usage()
                # Memory should be reasonable (less than 10MB for this test)
                assert memory_info["total_mb"] < 10.0

        # Final memory check
        final_memory = await component._get_bounded_memory_usage()
        assert final_memory["total_mb"] < 10.0

        # Verify that data is properly bounded
        counter_stats = await component.get_bounded_counter_stats("test_metric")
        timing_stats = await component.get_bounded_timing_stats("test_operation")

        assert counter_stats["current_count"] <= 100
        assert timing_stats["count"] <= 50


@pytest.mark.asyncio
async def test_integration_with_cleanup_scheduler():
    """Test integration with automatic cleanup scheduler."""
    component = TestBoundedStatisticsMixin.TestComponent(
        cleanup_interval_minutes=0.01  # Very frequent for testing (0.6 seconds)
    )

    # Add some data
    for _i in range(50):
        await component.increment_bounded("test_metric", 1.0)

    initial_stats = await component.get_bounded_counter_stats("test_metric")
    assert initial_stats["current_count"] == 50

    # Wait for cleanup cycles
    await asyncio.sleep(1.0)

    # Cleanup should have occurred automatically
    # (Though with our TTL settings, data might still be there)
    final_stats = await component.get_bounded_counter_stats("test_metric")
    assert final_stats is not None  # Should still exist

    # Cleanup the component
    await component.cleanup_bounded_statistics()


if __name__ == "__main__":
    # Run tests manually if needed
    pytest.main([__file__, "-v"])
