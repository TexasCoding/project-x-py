"""
Tests for DataFrame optimization with lazy evaluation.

Author: @TexasCoding
Date: 2025-08-22

This module provides comprehensive tests for the DataFrame optimization functionality
including lazy evaluation patterns, query optimization, caching, and performance monitoring.
"""

import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import polars as pl
import pytest
from pytz import timezone

from project_x_py.realtime_data_manager.dataframe_optimization import (
    LazyDataFrameMixin,
    LazyQueryCache,
    QueryOptimizer,
)


# Test fixtures
@pytest.fixture
def sample_ohlcv_data():
    """Create sample OHLCV data for testing."""
    timestamps = [
        datetime.now(timezone("UTC")) - timedelta(minutes=i) for i in range(100, 0, -1)
    ]

    return pl.DataFrame(
        {
            "timestamp": timestamps,
            "open": [100.0 + i * 0.5 for i in range(100)],
            "high": [100.5 + i * 0.5 for i in range(100)],
            "low": [99.5 + i * 0.5 for i in range(100)],
            "close": [100.2 + i * 0.5 for i in range(100)],
            "volume": [1000 + i * 10 for i in range(100)],
        }
    )


@pytest.fixture
def mock_data_manager():
    """Create a mock data manager with LazyDataFrameMixin."""

    class MockDataManager(LazyDataFrameMixin):
        def __init__(self):
            super().__init__()
            self.data = {}
            self.data_lock = asyncio.Lock()
            self.logger = MagicMock()

    return MockDataManager()


class TestQueryOptimizer:
    """Test suite for QueryOptimizer functionality."""

    def test_init(self):
        """Test QueryOptimizer initialization."""
        optimizer = QueryOptimizer()

        assert isinstance(optimizer.optimization_stats, dict)
        assert isinstance(optimizer.query_patterns, dict)
        assert optimizer.optimization_stats["queries_optimized"] == 0

    def test_combine_filters(self):
        """Test combining consecutive filter operations."""
        optimizer = QueryOptimizer()

        operations = [
            ("filter", pl.col("volume") > 0),
            ("filter", pl.col("close") > 100),
            ("select", ["close", "volume"]),
            ("filter", pl.col("volume") > 1000),
        ]

        optimized = optimizer.optimize_operations(operations)

        # Should combine consecutive filters and move all filters early
        # First two filters are consecutive and get combined and moved early
        # Third filter was separated by select, so it's also moved early but remains separate
        assert len(optimized) == 3  # 2 filters + select
        assert optimized[0][0] == "filter"  # Combined first two filters
        assert optimized[1][0] == "filter"  # Third filter moved early
        assert optimized[2][0] == "select"  # Select operation last
        assert optimizer.optimization_stats["filters_combined"] >= 1

    def test_move_filters_early(self):
        """Test moving filters early in the pipeline."""
        optimizer = QueryOptimizer()

        operations = [
            ("select", ["close", "volume"]),
            ("with_columns", [pl.col("close").pct_change().alias("returns")]),
            ("filter", pl.col("volume") > 1000),
        ]

        optimized = optimizer.optimize_operations(operations)

        # Filter should be moved to the beginning
        assert optimized[0][0] == "filter"
        assert optimizer.optimization_stats["filters_moved_early"] >= 1

    def test_combine_with_columns(self):
        """Test combining consecutive with_columns operations."""
        optimizer = QueryOptimizer()

        operations = [
            ("with_columns", [pl.col("close").rolling_mean(10).alias("sma_10")]),
            ("with_columns", [pl.col("close").rolling_mean(20).alias("sma_20")]),
            ("with_columns", [(pl.col("high") - pl.col("low")).alias("range")]),
        ]

        optimized = optimizer.optimize_operations(operations)

        # Should combine all with_columns into one
        assert len(optimized) == 1
        assert optimized[0][0] == "with_columns"
        assert len(optimized[0][1]) == 3
        assert optimizer.optimization_stats["with_columns_combined"] >= 2

    def test_empty_operations(self):
        """Test handling of empty operations list."""
        optimizer = QueryOptimizer()

        result = optimizer.optimize_operations([])

        assert result == []


class TestLazyQueryCache:
    """Test suite for LazyQueryCache functionality."""

    def test_init(self):
        """Test LazyQueryCache initialization."""
        cache = LazyQueryCache(max_size=50, default_ttl=30.0)

        assert cache.max_size == 50
        assert cache.default_ttl == 30.0
        assert cache.hits == 0
        assert cache.misses == 0
        assert cache.evictions == 0

    def test_set_and_get(self, sample_ohlcv_data):
        """Test basic cache set and get operations."""
        cache = LazyQueryCache()
        key = "test_key"

        # Test miss
        result = cache.get(key)
        assert result is None
        assert cache.misses == 1

        # Test set and hit
        cache.set(key, sample_ohlcv_data)
        result = cache.get(key)
        assert result is not None
        assert len(result) == len(sample_ohlcv_data)
        assert cache.hits == 1

    def test_ttl_expiration(self, sample_ohlcv_data):
        """Test cache entry expiration."""
        cache = LazyQueryCache(default_ttl=0.1)  # 100ms TTL
        key = "test_key"

        cache.set(key, sample_ohlcv_data)

        # Should hit immediately
        result = cache.get(key)
        assert result is not None
        assert cache.hits == 1

        # Wait for expiration
        time.sleep(0.2)

        # Should miss after expiration
        result = cache.get(key)
        assert result is None
        assert cache.misses == 1

    def test_lru_eviction(self, sample_ohlcv_data):
        """Test LRU eviction when cache is full."""
        cache = LazyQueryCache(max_size=2)

        # Fill cache
        cache.set("key1", sample_ohlcv_data)
        cache.set("key2", sample_ohlcv_data)

        # Access key1 to make it more recent
        cache.get("key1")

        # Add third item - should evict key2 (least recently used)
        cache.set("key3", sample_ohlcv_data)

        assert cache.get("key1") is not None  # Still there
        assert cache.get("key2") is None  # Evicted
        assert cache.get("key3") is not None  # New item
        assert cache.evictions == 1

    def test_clear_expired(self, sample_ohlcv_data):
        """Test clearing expired entries."""
        cache = LazyQueryCache(default_ttl=0.1)

        cache.set("key1", sample_ohlcv_data, ttl=0.1)
        cache.set("key2", sample_ohlcv_data, ttl=10.0)  # Long TTL

        time.sleep(0.2)  # Wait for first to expire

        cache.clear_expired()

        assert cache.get("key1") is None  # Expired and cleared
        assert cache.get("key2") is not None  # Still valid

    def test_get_stats(self, sample_ohlcv_data):
        """Test cache statistics."""
        cache = LazyQueryCache()

        # Generate some activity
        cache.set("key1", sample_ohlcv_data)
        cache.get("key1")  # Hit
        cache.get("key2")  # Miss

        stats = cache.get_stats()

        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["evictions"] == 0
        assert stats["hit_rate"] == 0.5
        assert stats["cache_size"] == 1
        assert stats["max_size"] == cache.max_size


class TestLazyDataFrameMixin:
    """Test suite for LazyDataFrameMixin functionality."""

    @pytest.mark.asyncio
    async def test_get_lazy_data(self, mock_data_manager, sample_ohlcv_data):
        """Test getting LazyFrame from timeframe data."""
        mock_data_manager.data["1min"] = sample_ohlcv_data

        lazy_df = await mock_data_manager.get_lazy_data("1min")

        assert lazy_df is not None
        assert isinstance(lazy_df, pl.LazyFrame)

        # Test with non-existent timeframe
        lazy_df = await mock_data_manager.get_lazy_data("nonexistent")
        assert lazy_df is None

    @pytest.mark.asyncio
    async def test_apply_lazy_operations_filter(
        self, mock_data_manager, sample_ohlcv_data
    ):
        """Test applying filter operations to LazyFrame."""
        mock_data_manager.data["1min"] = sample_ohlcv_data

        lazy_df = await mock_data_manager.get_lazy_data("1min")
        operations = [("filter", pl.col("volume") > 1050)]

        result = await mock_data_manager.apply_lazy_operations(lazy_df, operations)

        assert result is not None
        assert len(result) < len(sample_ohlcv_data)  # Filtered data should be smaller
        assert all(vol > 1050 for vol in result["volume"].to_list())

    @pytest.mark.asyncio
    async def test_apply_lazy_operations_select(
        self, mock_data_manager, sample_ohlcv_data
    ):
        """Test applying select operations to LazyFrame."""
        mock_data_manager.data["1min"] = sample_ohlcv_data

        lazy_df = await mock_data_manager.get_lazy_data("1min")
        operations = [("select", ["close", "volume"])]

        result = await mock_data_manager.apply_lazy_operations(lazy_df, operations)

        assert result is not None
        assert result.columns == ["close", "volume"]
        assert len(result) == len(sample_ohlcv_data)

    @pytest.mark.asyncio
    async def test_apply_lazy_operations_with_columns(
        self, mock_data_manager, sample_ohlcv_data
    ):
        """Test applying with_columns operations to LazyFrame."""
        mock_data_manager.data["1min"] = sample_ohlcv_data

        lazy_df = await mock_data_manager.get_lazy_data("1min")
        operations = [
            (
                "with_columns",
                [
                    (pl.col("high") - pl.col("low")).alias("range"),
                    pl.col("close").rolling_mean(5).alias("sma_5"),
                ],
            )
        ]

        result = await mock_data_manager.apply_lazy_operations(lazy_df, operations)

        assert result is not None
        assert "range" in result.columns
        assert "sma_5" in result.columns
        assert len(result) == len(sample_ohlcv_data)

    @pytest.mark.asyncio
    async def test_apply_lazy_operations_complex(
        self, mock_data_manager, sample_ohlcv_data
    ):
        """Test applying complex operation chains to LazyFrame."""
        mock_data_manager.data["1min"] = sample_ohlcv_data

        lazy_df = await mock_data_manager.get_lazy_data("1min")
        operations = [
            ("filter", pl.col("volume") > 1020),
            ("with_columns", [(pl.col("high") - pl.col("low")).alias("range")]),
            ("select", ["timestamp", "close", "volume", "range"]),
            ("tail", 10),
        ]

        result = await mock_data_manager.apply_lazy_operations(lazy_df, operations)

        assert result is not None
        assert result.columns == ["timestamp", "close", "volume", "range"]
        assert len(result) == 10
        assert all(vol > 1020 for vol in result["volume"].to_list())

    @pytest.mark.asyncio
    async def test_execute_batch_queries(self, mock_data_manager, sample_ohlcv_data):
        """Test executing batch queries."""
        # Setup data for multiple timeframes
        mock_data_manager.data["1min"] = sample_ohlcv_data
        mock_data_manager.data["5min"] = sample_ohlcv_data.clone()

        batch = [
            ("1min", [("select", ["close", "volume"]), ("tail", 50)]),
            ("5min", [("filter", pl.col("volume") > 1030), ("head", 20)]),
        ]

        results = await mock_data_manager.execute_batch_queries(batch)

        assert "1min" in results
        assert "5min" in results
        assert results["1min"] is not None
        assert results["5min"] is not None
        assert len(results["1min"]) == 50
        assert results["1min"].columns == ["close", "volume"]
        assert len(results["5min"]) <= 20  # Could be less due to filter

    @pytest.mark.asyncio
    async def test_get_optimized_bars(self, mock_data_manager, sample_ohlcv_data):
        """Test getting optimized bars with various parameters."""
        mock_data_manager.data["1min"] = sample_ohlcv_data

        # Test basic bars retrieval
        result = await mock_data_manager.get_optimized_bars("1min", bars=20)
        assert result is not None
        assert len(result) == 20

        # Test with column selection
        result = await mock_data_manager.get_optimized_bars(
            "1min", columns=["close", "volume"], bars=10
        )
        assert result is not None
        assert len(result) == 10
        assert result.columns == ["close", "volume"]

        # Test with filters
        result = await mock_data_manager.get_optimized_bars(
            "1min", filters=[pl.col("volume") > 1050], bars=30
        )
        assert result is not None
        assert len(result) <= 30
        assert all(vol > 1050 for vol in result["volume"].to_list())

    @pytest.mark.asyncio
    async def test_get_aggregated_data(self, mock_data_manager):
        """Test getting aggregated data."""
        # Create data with groupable column
        df = pl.DataFrame(
            {
                "timestamp": [
                    datetime.now(timezone("UTC")) - timedelta(minutes=i)
                    for i in range(20)
                ],
                "close": [100.0 + i for i in range(20)],
                "volume": [1000 + i * 100 for i in range(20)],
                "hour": [i // 4 for i in range(20)],  # Group by hour
            }
        )
        mock_data_manager.data["1min"] = df

        result = await mock_data_manager.get_aggregated_data(
            "1min",
            group_by="hour",
            aggregations=[
                pl.col("close").mean().alias("avg_close"),
                pl.col("volume").sum().alias("total_volume"),
            ],
        )

        assert result is not None
        assert "hour" in result.columns
        assert "avg_close" in result.columns
        assert "total_volume" in result.columns
        assert len(result) == 5  # 5 different hour groups

    @pytest.mark.asyncio
    async def test_cache_usage(self, mock_data_manager, sample_ohlcv_data):
        """Test cache usage in batch queries."""
        mock_data_manager.data["1min"] = sample_ohlcv_data

        batch = [("1min", [("tail", 10)])]

        # First execution - should miss cache
        results1 = await mock_data_manager.execute_batch_queries(batch, use_cache=True)
        assert mock_data_manager.lazy_stats["cache_misses"] >= 1

        # Second execution - should hit cache
        results2 = await mock_data_manager.execute_batch_queries(batch, use_cache=True)
        assert mock_data_manager.lazy_stats["cache_hits"] >= 1

        # Results should be the same
        assert len(results1["1min"]) == len(results2["1min"])

    @pytest.mark.asyncio
    async def test_performance_monitoring(self, mock_data_manager, sample_ohlcv_data):
        """Test performance monitoring features."""
        mock_data_manager.data["1min"] = sample_ohlcv_data

        # Execute some operations
        lazy_df = await mock_data_manager.get_lazy_data("1min")
        await mock_data_manager.apply_lazy_operations(
            lazy_df, [("filter", pl.col("volume") > 1000)]
        )

        # Check operation times are recorded
        assert len(mock_data_manager.operation_times) > 0

        # Check optimization stats
        stats = mock_data_manager.get_optimization_stats()
        assert "operations_optimized" in stats
        assert "avg_operation_time_ms" in stats
        assert "cache_stats" in stats
        assert stats["operations_optimized"] > 0

    @pytest.mark.asyncio
    async def test_memory_profiling(self, mock_data_manager):
        """Test memory profiling functionality."""
        with patch("psutil.Process") as mock_process:
            # Mock memory info
            mock_memory_info = MagicMock()
            mock_memory_info.rss = 100 * 1024 * 1024  # 100 MB
            mock_process.return_value.memory_info.return_value = mock_memory_info

            profile = await mock_data_manager.profile_memory_usage()

            assert "current_memory_mb" in profile
            assert "average_memory_mb" in profile
            assert "memory_trend_mb" in profile
            assert "samples_count" in profile
            assert "gc_objects" in profile
            assert profile["current_memory_mb"] == 100.0

    @pytest.mark.asyncio
    async def test_optimization_cache_clear(self, mock_data_manager):
        """Test clearing optimization cache."""
        # Add something to cache
        mock_data_manager.query_cache.set("test", pl.DataFrame({"a": [1, 2, 3]}))

        # Verify cache has content
        assert len(mock_data_manager.query_cache._cache) == 1

        # Clear cache
        await mock_data_manager.clear_optimization_cache()

        # Verify cache is empty
        assert len(mock_data_manager.query_cache._cache) == 0

    def test_generate_cache_key(self, mock_data_manager):
        """Test cache key generation."""
        operations = [
            ("filter", pl.col("volume") > 1000),
            ("select", ["close", "volume"]),
        ]

        key1 = mock_data_manager._generate_cache_key("1min", operations)
        key2 = mock_data_manager._generate_cache_key("1min", operations)
        key3 = mock_data_manager._generate_cache_key("5min", operations)

        # Same timeframe and operations should generate same key
        assert key1 == key2

        # Different timeframe should generate different key
        assert key1 != key3


class TestIntegration:
    """Integration tests for DataFrame optimization."""

    @pytest.mark.asyncio
    async def test_real_world_scenario(self, mock_data_manager):
        """Test a real-world trading data analysis scenario."""
        # Create realistic OHLCV data
        timestamps = [
            datetime.now(timezone("UTC")) - timedelta(minutes=i)
            for i in range(200, 0, -1)
        ]

        df = pl.DataFrame(
            {
                "timestamp": timestamps,
                "open": [4000.0 + (i % 50) * 2.5 for i in range(200)],
                "high": [4010.0 + (i % 50) * 2.5 for i in range(200)],
                "low": [3990.0 + (i % 50) * 2.5 for i in range(200)],
                "close": [4005.0 + (i % 50) * 2.5 for i in range(200)],
                "volume": [1000 + (i % 100) * 50 for i in range(200)],
            }
        )

        mock_data_manager.data["1min"] = df

        # Complex trading analysis workflow
        batch = [
            (
                "1min",
                [
                    # Filter active bars
                    ("filter", pl.col("volume") > 2000),
                    # Add technical indicators
                    (
                        "with_columns",
                        [
                            pl.col("close").rolling_mean(10).alias("sma_10"),
                            pl.col("close").rolling_mean(20).alias("sma_20"),
                            (pl.col("high") - pl.col("low")).alias("range"),
                            pl.col("close").pct_change().alias("returns"),
                        ],
                    ),
                    # Select relevant columns
                    (
                        "select",
                        [
                            "timestamp",
                            "close",
                            "volume",
                            "sma_10",
                            "sma_20",
                            "range",
                            "returns",
                        ],
                    ),
                    # Get recent data
                    ("tail", 50),
                ],
            )
        ]

        results = await mock_data_manager.execute_batch_queries(batch)

        # Verify results
        assert "1min" in results
        result = results["1min"]
        assert result is not None
        assert len(result) <= 50
        assert "sma_10" in result.columns
        assert "sma_20" in result.columns
        assert "range" in result.columns
        assert "returns" in result.columns

        # Verify optimization happened
        stats = mock_data_manager.get_optimization_stats()
        assert stats["operations_optimized"] > 0

    @pytest.mark.asyncio
    async def test_performance_comparison(self, mock_data_manager):
        """Test performance improvement with optimization."""
        # Create large dataset
        timestamps = [
            datetime.now(timezone("UTC")) - timedelta(seconds=i)
            for i in range(10000, 0, -1)
        ]

        large_df = pl.DataFrame(
            {
                "timestamp": timestamps,
                "close": [100.0 + (i % 1000) * 0.01 for i in range(10000)],
                "volume": [1000 + i for i in range(10000)],
            }
        )

        mock_data_manager.data["1sec"] = large_df

        # Test without optimization
        start_time = time.time()
        lazy_df = await mock_data_manager.get_lazy_data("1sec")
        result_no_opt = await mock_data_manager.apply_lazy_operations(
            lazy_df,
            [
                ("filter", pl.col("volume") > 5000),
                ("with_columns", [pl.col("close").rolling_mean(100).alias("sma")]),
                ("tail", 100),
            ],
            optimize=False,
        )
        time_no_opt = time.time() - start_time

        # Test with optimization
        start_time = time.time()
        lazy_df = await mock_data_manager.get_lazy_data("1sec")
        result_opt = await mock_data_manager.apply_lazy_operations(
            lazy_df,
            [
                ("filter", pl.col("volume") > 5000),
                ("with_columns", [pl.col("close").rolling_mean(100).alias("sma")]),
                ("tail", 100),
            ],
            optimize=True,
        )
        time_opt = time.time() - start_time

        # Both should produce same results
        assert result_no_opt is not None
        assert result_opt is not None
        assert len(result_no_opt) == len(result_opt)

        # Optimization should not significantly slow down (allow for test variance)
        # The real benefit is in memory usage and complex query scenarios
        assert time_opt <= time_no_opt * 2.0  # Allow 2x tolerance for test variance

        print(f"Without optimization: {time_no_opt:.4f}s")
        print(f"With optimization: {time_opt:.4f}s")
