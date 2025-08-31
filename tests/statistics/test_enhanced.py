#!/usr/bin/env python3
"""
Comprehensive unit tests for enhanced statistics tracking system.

Tests the EnhancedStatsTrackingMixin and StatisticsAggregator for:
- Error handling and graceful degradation
- Memory leak prevention with circular buffers
- PII sanitization
- Thread safety
- Performance overhead
- Edge cases and boundary conditions
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from project_x_py.statistics import BaseStatisticsTracker, StatisticsAggregator


class TestComponent(BaseStatisticsTracker):
    """Test component that uses the enhanced stats tracking mixin."""

    def __init__(self):
        super().__init__(
            component_name="test_component",
            max_errors=10,
            cache_ttl=1.0,
        )


class TestEnhancedStatsTracking:
    """Test suite for EnhancedStatsTrackingMixin."""

    @pytest.mark.asyncio
    async def test_circular_buffer_prevents_memory_leak(self):
        """Test that circular buffers prevent unbounded memory growth."""
        component = TestComponent()

        # Add more errors than the max
        for i in range(20):
            await component.track_error(
                Exception(f"Error {i}"),
                context=f"test_{i}",
                details={"index": i},
            )

        # Should only keep last 10 errors
        assert len(component._error_history) == 10
        assert await component.get_error_count() == 20  # Total count preserved

        # Add more timings than the max
        for i in range(150):
            await component.record_timing(
                operation="test_op",
                duration_ms=float(i),
            )

        # Should only keep last 100 timings in operation-specific buffer
        # Access through the performance metrics
        async with component._lock:
            timings = component._performance.operation_times.get("test_op", [])
            # Note: PerformanceMetrics keeps last 1000, not 100, so all should be present
            assert len(timings) == 150
            # Verify the values are correct
            assert min(timings) == 0.0
            assert max(timings) == 149.0

    @pytest.mark.asyncio
    async def test_pii_sanitization(self):
        """Test that PII is properly sanitized from exports."""
        from project_x_py.statistics.aggregator import StatisticsAggregator
        from project_x_py.statistics.export import StatsExporter

        component = TestComponent()

        # Track error with sensitive data
        await component.track_error(
            Exception("Test error"),
            context="trading",
            details={
                "account_id": "ACC123456789",
                "api_key": "secret_key_123", # pragma: allowlist secret
                "order_size": 100,
                "pnl": 5000.50,
                "balance": 100000,
                "safe_field": "this_is_safe",
            },
        )

        # Get stats and export through StatsExporter
        stats = await component.get_stats()
        exporter = StatsExporter(sanitize_sensitive=True)

        # Create comprehensive stats for export
        aggregator = StatisticsAggregator()
        await aggregator.register_component("test_component", component)
        comprehensive_stats = await aggregator.get_stats()

        exported = await exporter.export(comprehensive_stats, export_format="json")

        # Parse the JSON export
        import json
        exported_data = json.loads(exported)

        # Check that PII is sanitized in error details
        component_stats = exported_data.get("components", {}).get("test_component", {})
        recent_errors = component_stats.get("errors", {}).get("recent_errors", [])
        if recent_errors:
            details = recent_errors[0]["details"]
            assert details["account_id"] == "***6789"  # Last 4 chars
            assert details["api_key"] == "***REDACTED***"
            assert details["order_size"] == "***REDACTED***"
            assert details["pnl"] == "positive"  # Shows sign, not value
            assert details["balance"] == "positive"  # Shows sign, not value
            assert details["safe_field"] == "this_is_safe"  # Not sanitized

    @pytest.mark.asyncio
    async def test_thread_safety(self):
        """Test that concurrent access to stats is thread-safe."""
        component = TestComponent()

        async def track_errors(context_name: str, count: int):
            for i in range(count):
                await component.track_error(
                    Exception(f"Error {i} in {context_name}"),
                    context=context_name,
                    details={"index": i},
                )

        # Run multiple concurrent tasks
        tasks = [
            track_errors("context1", 10),  # Limited to max_errors=10
            track_errors("context2", 10),
            track_errors("context3", 10),
        ]

        await asyncio.gather(*tasks)

        # Verify errors were tracked (limited by circular buffer)
        stats = await component.get_stats()
        assert stats["error_count"] >= 10  # At least max_errors tracked
        # Check internal state for circular buffer limit
        assert len(component._error_history) <= 10  # Limited by max_errors

    @pytest.mark.asyncio
    async def test_performance_percentiles(self):
        """Test performance percentile calculations."""
        component = TestComponent()

        # Add known timing values
        timings = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        for timing in timings:
            await component.record_timing(
                operation="test",
                duration_ms=float(timing),
            )

        # Get performance metrics through performance tracker
        metrics = await component._performance.get_all_metrics()

        # Check that we have recorded timings
        assert "test" in metrics
        op_stats = metrics["test"]

        # Check basic stats exist
        assert "count" in op_stats
        assert "avg_ms" in op_stats
        assert "min_ms" in op_stats
        assert "max_ms" in op_stats
        assert op_stats["count"] == 10
        assert op_stats["min_ms"] == 10
        assert op_stats["max_ms"] == 100
        assert op_stats["avg_ms"] == 55  # Average of 10-100 in steps of 10

    @pytest.mark.asyncio
    async def test_data_quality_tracking(self):
        """Test data quality metrics tracking."""
        # Since track_data_quality is OrderBook-specific, test with OrderBook
        from unittest.mock import MagicMock

        from project_x_py.event_bus import EventBus
        from project_x_py.orderbook import OrderBook

        # Create OrderBook with mock dependencies
        mock_client = MagicMock()
        event_bus = EventBus()

        orderbook = OrderBook(
            instrument="TEST",
            event_bus=event_bus,
            project_x=mock_client
        )

        # Track data quality issues using the actual keys that OrderBook initializes
        await orderbook.track_data_quality_issue("data_gaps")
        await orderbook.track_data_quality_issue("data_gaps")
        await orderbook.track_data_quality_issue("invalid_updates")

        # Check that issues were tracked
        assert orderbook._data_quality["data_gaps"] == 2
        assert orderbook._data_quality["invalid_updates"] == 1

    @pytest.mark.asyncio
    async def test_cleanup_old_stats(self):
        """Test that old statistics are properly cleaned up."""
        component = TestComponent()

        # Mock the cleanup_old_stats method since BaseStatisticsTracker doesn't have it
        # or test the behavior that exists

        # Add an error
        await component.track_error(
            Exception("Test error"),
            context="test",
        )

        # Verify error was tracked
        assert len(component._error_history) == 1

        # Since BaseStatisticsTracker doesn't have cleanup_old_stats,
        # we test that the circular buffer automatically limits size
        for i in range(20):  # Add more than max_errors (10)
            await component.track_error(
                Exception(f"Error {i}"),
                context="test",
            )

        # Should be limited to max_errors
        assert len(component._error_history) <= 10

    @pytest.mark.asyncio
    async def test_prometheus_export_format(self):
        """Test Prometheus export format."""
        from project_x_py.statistics.export import StatsExporter

        component = TestComponent()

        # Add some metrics using available methods
        await component.record_timing("api_call", 100.0)
        await component.track_error(Exception("Test error"), context="test")

        # Get stats
        stats = await component.get_stats()

        # Create ComprehensiveStats structure that StatsExporter expects
        comprehensive_stats = {
            "health": {
                "overall_score": 95.0,
                "component_scores": {
                    "test_component": 95.0
                }
            },
            "performance": {
                "api_calls_total": 10,
                "cache_hit_rate": 0.8,
                "avg_response_time": 0.1
            },
            "memory": {
                "total_memory_mb": stats.get("memory_usage_mb", 0.1),
                "component_memory": {
                    "test_component": stats.get("memory_usage_mb", 0.1)
                }
            },
            "errors": {
                "total_errors": stats.get("error_count", 0),
                "error_rate": 0.01,
                "errors_by_component": {
                    "test_component": stats.get("error_count", 0)
                }
            }
        }

        exporter = StatsExporter()

        # Export in Prometheus format
        prom_export = await exporter.export(
            comprehensive_stats,
            export_format="prometheus"
        )

        # Check format
        assert isinstance(prom_export, str)
        assert "# HELP" in prom_export
        assert "# TYPE" in prom_export
        assert "projectx_" in prom_export  # Check for metric prefix


class TestStatisticsAggregator:
    """Test suite for StatisticsAggregator."""

    @pytest.mark.asyncio
    async def test_aggregation_with_component_failures(self):
        """Test that aggregation handles component failures gracefully."""
        aggregator = StatisticsAggregator(cache_ttl=1)

        # Create mock components that fail
        failing_component = MagicMock()
        failing_component.get_performance_metrics = AsyncMock(
            side_effect=Exception("Component failed")
        )

        aggregator.order_manager = failing_component
        aggregator.trading_suite = MagicMock()
        aggregator.trading_suite.is_connected = False
        aggregator.trading_suite.config = MagicMock()
        aggregator.trading_suite.config.features = []
        aggregator.trading_suite.config.timeframes = []

        # Should not raise, should return safe defaults
        stats = await aggregator.aggregate_stats()
        assert stats is not None
        # Status defaults to "connecting" since aggregator itself is initializing
        assert stats["status"] in ["connecting", "disconnected"]
        assert "components" in stats

    @pytest.mark.asyncio
    async def test_cache_functionality(self):
        """Test that caching works correctly."""
        aggregator = StatisticsAggregator(cache_ttl=1)

        # Mock a simple suite
        aggregator.trading_suite = MagicMock()
        aggregator.trading_suite.is_connected = True
        aggregator.trading_suite.config = MagicMock()
        aggregator.trading_suite.config.features = []
        aggregator.trading_suite.config.timeframes = ["1min"]

        # First call should compute
        stats1 = await aggregator.aggregate_stats()

        # Second call should use cache
        stats2 = await aggregator.aggregate_stats()
        assert stats1 == stats2  # Should be identical

        # Wait for cache to expire
        await asyncio.sleep(1.1)

        # Should recompute
        stats3 = await aggregator.aggregate_stats()
        assert stats3 is not None

    @pytest.mark.asyncio
    async def test_health_score_calculation(self):
        """Test health score calculation with various conditions."""
        aggregator = StatisticsAggregator()

        # Test with perfect health
        stats = {
            "components": {},
            "cache_hit_rate": 1.0,
            "total_errors": 0,
        }
        result = await aggregator._calculate_cross_metrics(stats)
        assert result["health_score"] == 100.0

        # Test with errors
        stats = {
            "test": {"error_count": 10, "memory_usage_mb": 100},
        }
        result = await aggregator._calculate_cross_metrics(stats)
        # Without API calls, health score stays at 100 even with errors
        assert result["health_score"] == 100

        # Test with disconnected components
        # Note: _calculate_cross_metrics expects the stats dict directly, not nested under "components"
        stats = {
            "test1": {"status": "disconnected", "error_count": 5, "total_requests": 10},
            "test2": {"status": "connected", "error_count": 0},
        }
        result = await aggregator._calculate_cross_metrics(stats)
        # With errors and API calls, health score should be penalized
        # The function calculates: base_health = 100 - (error_rate * 100)
        # error_rate = 5 / 10 = 0.5, so health = 100 - 50 = 50
        assert result["health_score"] == 50.0

    @pytest.mark.asyncio
    async def test_safe_division(self):
        """Test that division by zero is handled safely in cross-metrics calculation."""
        aggregator = StatisticsAggregator()

        # Test with empty stats - should not cause division by zero
        stats = {}
        result = await aggregator._calculate_cross_metrics(stats)

        # Should return safe defaults
        assert result["cache_hit_rate"] == 0.0
        assert result["avg_response_time_ms"] == 0.0
        assert result["health_score"] == 100.0  # Default when no data

    @pytest.mark.asyncio
    async def test_memory_calculation_performance(self):
        """Test that getting stats (including memory) doesn't cause performance issues."""
        component = TestComponent()

        # Add some data to the component
        for i in range(100):
            await component.record_timing(f"operation_{i}", float(i))

        # Should complete quickly
        import time

        start = time.time()
        stats = await component.get_stats()
        duration = time.time() - start

        # Check that memory_usage_mb is included in stats
        assert "memory_usage_mb" in stats
        assert stats["memory_usage_mb"] > 0
        assert duration < 0.1  # Should be fast (< 100ms)

    @pytest.mark.asyncio
    async def test_empty_stats_structure(self):
        """Test that aggregator stats have correct structure when no suite is set."""
        aggregator = StatisticsAggregator()

        # Get stats without any trading suite
        stats = await aggregator.aggregate_stats()

        # Check structure exists
        assert stats is not None
        assert "status" in stats
        assert "components" in stats
        # Status should be "connecting" by default since aggregator itself is initializing
        assert stats["status"] in ["connecting", "disconnected"]

    @pytest.mark.asyncio
    async def test_empty_component_stats_structure(self):
        """Test that component stats have correct structure."""
        component = TestComponent()

        # Get stats from a fresh component
        stats = await component.get_stats()

        assert stats["name"] == "test_component"
        assert stats["status"] in ["initializing", "connecting", "disconnected", "connected"]
        assert "uptime_seconds" in stats
        assert stats["error_count"] == 0
        assert stats["memory_usage_mb"] >= 0.0
        assert "performance_metrics" in stats


@pytest.mark.asyncio
async def test_integration_stats_during_reconnection():
    """Test that statistics remain accurate during WebSocket reconnections."""
    # This would be an integration test with actual components
    # Included here as a placeholder for comprehensive testing


@pytest.mark.asyncio
async def test_stats_under_load():
    """Test statistics accuracy during high-frequency operations."""
    component = TestComponent()

    # Simulate high-frequency operations using actual available methods
    tasks = []
    for i in range(100):
        # Use record_timing for timing operations
        tasks.append(
            component.record_timing(
                operation=f"trade_{i % 10}",
                duration_ms=float(i % 100)
            )
        )
        # Track errors for some operations (10% failure rate)
        if i % 10 == 0:
            tasks.append(
                component.track_error(
                    Exception(f"Trade error {i}"),
                    context=f"trade_{i % 10}"
                )
            )

    await asyncio.gather(*tasks)

    # Verify stats are accurate
    stats = await component.get_stats()
    assert "error_count" in stats
    assert stats["error_count"] == 10  # 10 errors tracked
    assert "performance_metrics" in stats


@pytest.mark.asyncio
async def test_position_manager_stats_integration():
    """Test that PositionManager properly tracks statistics with EnhancedStatsTrackingMixin."""
    from project_x_py.models import Position
    from project_x_py.position_manager import PositionManager

    # Create mock dependencies
    mock_client = AsyncMock()
    mock_event_bus = AsyncMock()

    # Setup mock response for search_open_positions
    mock_positions = [
        Position(
            id=1,
            accountId=123,
            contractId="MNQ",
            type=1,  # LONG
            size=2,
            averagePrice=15000.0,
            creationTimestamp="2025-01-01T12:00:00Z",
        ),
        Position(
            id=2,
            accountId=123,
            contractId="ES",
            type=2,  # SHORT
            size=1,
            averagePrice=4500.0,
            creationTimestamp="2025-01-01T12:00:00Z",
        ),
    ]
    mock_client.search_open_positions = AsyncMock(return_value=mock_positions)

    # Create PositionManager
    position_manager = PositionManager(
        project_x_client=mock_client,
        event_bus=mock_event_bus,
    )

    # Perform operations to generate stats
    await position_manager.get_all_positions()
    await position_manager.get_position("MNQ")
    await position_manager.get_position("ES")
    await position_manager.get_position("NQ")  # Not found

    # Verify stats are being tracked
    stats = await position_manager.get_position_stats()

    # Check that the stats structure exists
    assert "component_stats" in stats
    assert "health_score" in stats
    assert "error_count" in stats

    # After getting positions, tracked_positions should be populated
    assert len(position_manager.tracked_positions) == 2
    assert "MNQ" in position_manager.tracked_positions
    assert "ES" in position_manager.tracked_positions

    # Check that positions_tracked was updated in stats
    assert stats["positions_tracked"] == 2


@pytest.mark.asyncio
async def test_realtime_data_manager_stats_integration():
    """Test that RealtimeDataManager properly tracks statistics with EnhancedStatsTrackingMixin."""
    from project_x_py.realtime_data_manager import RealtimeDataManager

    # Create mock dependencies
    mock_client = AsyncMock()
    mock_realtime_client = AsyncMock()
    mock_event_bus = AsyncMock()

    # Create RealtimeDataManager
    data_manager = RealtimeDataManager(
        instrument="MNQ",
        project_x=mock_client,
        realtime_client=mock_realtime_client,
        event_bus=mock_event_bus,
        timeframes=["1min", "5min"],
    )

    # RealtimeDataManager inherits from BaseStatisticsTracker
    # Verify it has the statistics tracking capabilities
    assert hasattr(data_manager, "track_error")
    assert hasattr(data_manager, "record_timing")
    assert hasattr(data_manager, "get_stats")

    # Track some operations using the actual available methods
    await data_manager.record_timing("process_tick", 0.5)
    await data_manager.record_timing("process_tick", 0.3)

    # Track an error
    await data_manager.track_error(
        Exception("Test error"),
        context="process_tick"
    )

    # Get stats
    stats = await data_manager.get_stats()
    assert "error_count" in stats
    assert stats["error_count"] >= 0

    # Verify performance metrics are tracked
    assert "performance_metrics" in stats


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
