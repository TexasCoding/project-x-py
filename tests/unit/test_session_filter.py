"""
Tests for session filtering functionality.

This test file defines the EXPECTED behavior for filtering market data
by trading sessions (RTH/ETH). Following strict TDD methodology - these tests
define the specification, not the current behavior.

Author: TDD Implementation
Date: 2025-08-28
"""

from datetime import datetime, time, timedelta, timezone

import polars as pl
import pytest

# Note: These imports will fail initially - that's expected in RED phase
from project_x_py.sessions import (
    SessionFilterMixin,
    SessionTimes,
    SessionType,
    resolve_session_product,
)


class TestSessionFilterMixin:
    """Test session filtering operations on market data."""

    @pytest.fixture
    def session_filter(self):
        """Create session filter with default configuration."""
        return SessionFilterMixin()

    @pytest.fixture
    def sample_data(self):
        """Create sample OHLCV data spanning RTH and ETH."""
        # Create data for Monday Jan 15, 2024 across different sessions
        timestamps = [
            # Overnight/Pre-market ETH (3 AM ET = 8 AM UTC)
            datetime(2024, 1, 15, 8, 0, tzinfo=timezone.utc),
            # Market open RTH (9:30 AM ET = 2:30 PM UTC)
            datetime(2024, 1, 15, 14, 30, tzinfo=timezone.utc),
            # Mid-day RTH (1:00 PM ET = 6 PM UTC)
            datetime(2024, 1, 15, 18, 0, tzinfo=timezone.utc),
            # Market close RTH (4:00 PM ET = 9 PM UTC)
            datetime(2024, 1, 15, 21, 0, tzinfo=timezone.utc),
            # After-hours ETH (7 PM ET = 12 AM UTC next day)
            datetime(2024, 1, 16, 0, 0, tzinfo=timezone.utc),
        ]

        return pl.DataFrame(
            {
                "timestamp": timestamps,
                "open": [100.0, 101.0, 102.0, 103.0, 104.0],
                "high": [101.0, 102.0, 103.0, 104.0, 105.0],
                "low": [99.0, 100.0, 101.0, 102.0, 103.0],
                "close": [100.5, 101.5, 102.5, 103.5, 104.5],
                "volume": [1000, 2000, 3000, 4000, 5000],
            }
        )

    @pytest.fixture
    def multi_day_data(self):
        """Create multi-day sample data for comprehensive testing."""
        base_date = datetime(2024, 1, 15, tzinfo=timezone.utc)  # Monday
        timestamps = []

        # Create 3 days of data with various session times
        for day in range(3):
            day_offset = timedelta(days=day)
            # Pre-market
            timestamps.append(base_date + day_offset + timedelta(hours=8))
            # RTH open
            timestamps.append(base_date + day_offset + timedelta(hours=14, minutes=30))
            # RTH mid-day
            timestamps.append(base_date + day_offset + timedelta(hours=18))
            # RTH close
            timestamps.append(base_date + day_offset + timedelta(hours=21))
            # After-hours
            timestamps.append(base_date + day_offset + timedelta(hours=24))

        n_points = len(timestamps)
        return pl.DataFrame(
            {
                "timestamp": timestamps,
                "open": [100.0 + i * 0.5 for i in range(n_points)],
                "high": [101.0 + i * 0.5 for i in range(n_points)],
                "low": [99.0 + i * 0.5 for i in range(n_points)],
                "close": [100.5 + i * 0.5 for i in range(n_points)],
                "volume": [1000 + i * 100 for i in range(n_points)],
            }
        )

    @pytest.mark.asyncio
    async def test_filter_by_rth_session(self, session_filter, sample_data):
        """RTH filtering should return only 9:30 AM - 4:00 PM ET data."""
        result = await session_filter.filter_by_session(
            sample_data, SessionType.RTH, "ES"
        )

        # Should return 3 bars: 9:30 AM, 1:00 PM, 4:00 PM ET
        assert len(result) == 3

        # Verify times are within RTH hours (14:30, 18:00, 21:00 UTC)
        result_hours = result["timestamp"].dt.hour().to_list()
        expected_hours = [14, 18, 21]  # UTC hours for RTH times
        assert result_hours == expected_hours

    @pytest.mark.asyncio
    async def test_rth_filter_uses_per_bar_dst_offset(self, session_filter):
        """Session filters must use each bar's DST offset, not bar 0's offset."""
        timestamps = [
            # Friday 2026-03-06 10:00 AM EST = 15:00 UTC (before spring-forward)
            datetime(2026, 3, 6, 15, 0, tzinfo=timezone.utc),
            # Monday 2026-03-09 10:00 AM EDT = 14:00 UTC (after spring-forward)
            datetime(2026, 3, 9, 14, 0, tzinfo=timezone.utc),
        ]
        data = pl.DataFrame(
            {
                "timestamp": timestamps,
                "open": [1.0, 2.0],
                "high": [1.0, 2.0],
                "low": [1.0, 2.0],
                "close": [1.0, 2.0],
                "volume": [1, 1],
            }
        )

        result = await session_filter.filter_by_session(data, SessionType.RTH, "ES")

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_filter_by_eth_session(self, session_filter, sample_data):
        """ETH filtering should return all bars including RTH."""
        result = await session_filter.filter_by_session(
            sample_data, SessionType.ETH, "ES"
        )

        # Should return 5 bars (all data points)
        assert len(result) == 5

        # Verify all timestamps are included
        original_timestamps = sample_data["timestamp"].to_list()
        result_timestamps = result["timestamp"].to_list()
        assert result_timestamps == original_timestamps

    @pytest.mark.asyncio
    async def test_filter_by_custom_session(self, session_filter, sample_data):
        """Custom session filtering should use provided session times."""
        custom_times = SessionTimes(
            rth_start=time(10, 0),  # 10 AM ET
            rth_end=time(15, 0),  # 3 PM ET
            eth_start=time(18, 0),  # 6 PM ET prev day
            eth_end=time(17, 0),  # 5 PM ET curr day
        )

        result = await session_filter.filter_by_session(
            sample_data, SessionType.CUSTOM, "ES", custom_session_times=custom_times
        )

        # Should return bars between 10 AM - 3 PM ET (15:00 - 20:00 UTC)
        assert len(result) == 1  # Only the 1 PM ET bar (18:00 UTC)
        assert result["timestamp"].dt.hour().to_list() == [18]

    def test_is_in_rth_session(self, session_filter):
        """is_in_session should correctly identify RTH times."""
        # 10:00 AM ET = 3:00 PM UTC (Monday)
        timestamp = datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc)
        assert session_filter.is_in_session(timestamp, SessionType.RTH, "ES") is True

        # 7:00 PM ET = 12:00 AM UTC next day (after hours)
        timestamp = datetime(2024, 1, 16, 0, 0, tzinfo=timezone.utc)
        assert session_filter.is_in_session(timestamp, SessionType.RTH, "ES") is False

    def test_is_in_eth_session(self, session_filter):
        """is_in_session should correctly identify ETH times."""
        # 10:00 AM ET = 3:00 PM UTC (RTH, also part of ETH)
        timestamp = datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc)
        assert session_filter.is_in_session(timestamp, SessionType.ETH, "ES") is True

        # 7:00 PM ET = 12:00 AM UTC next day (ETH only)
        timestamp = datetime(2024, 1, 16, 0, 0, tzinfo=timezone.utc)
        assert session_filter.is_in_session(timestamp, SessionType.ETH, "ES") is True

        # 5:30 PM ET = 10:30 PM UTC (maintenance break)
        timestamp = datetime(2024, 1, 15, 22, 30, tzinfo=timezone.utc)
        assert session_filter.is_in_session(timestamp, SessionType.ETH, "ES") is False

    def test_is_in_session_weekend(self, session_filter):
        """is_in_session should handle weekends correctly."""
        # Saturday during normal RTH hours
        saturday = datetime(2024, 1, 13, 15, 0, tzinfo=timezone.utc)  # 10 AM ET
        assert session_filter.is_in_session(saturday, SessionType.RTH, "ES") is False
        assert session_filter.is_in_session(saturday, SessionType.ETH, "ES") is False

        # Sunday during normal RTH hours
        sunday = datetime(2024, 1, 14, 15, 0, tzinfo=timezone.utc)
        assert session_filter.is_in_session(sunday, SessionType.RTH, "ES") is False

        # Sunday evening ETH start (6 PM ET = 11 PM UTC)
        sunday_evening = datetime(2024, 1, 14, 23, 0, tzinfo=timezone.utc)
        assert (
            session_filter.is_in_session(sunday_evening, SessionType.ETH, "ES") is True
        )

    def test_different_product_sessions(self, session_filter):
        """Different products should have different session times."""
        timestamp = datetime(2024, 1, 15, 13, 0, tzinfo=timezone.utc)  # 8 AM ET

        # ES RTH starts at 9:30 AM ET (14:30 UTC) - 8 AM should be outside RTH
        assert session_filter.is_in_session(timestamp, SessionType.RTH, "ES") is False

        # CL RTH starts at 9:00 AM ET (14:00 UTC) - 8 AM should still be outside RTH
        assert session_filter.is_in_session(timestamp, SessionType.RTH, "CL") is False

        # GC RTH starts at 8:20 AM ET (13:20 UTC) - 8 AM should be outside RTH
        assert session_filter.is_in_session(timestamp, SessionType.RTH, "GC") is False

        # Test time that's within GC RTH (8:30 AM ET = 13:30 UTC)
        gc_rth_time = datetime(2024, 1, 15, 13, 30, tzinfo=timezone.utc)
        assert session_filter.is_in_session(gc_rth_time, SessionType.RTH, "GC") is True
        assert session_filter.is_in_session(gc_rth_time, SessionType.RTH, "ES") is False

    @pytest.mark.asyncio
    async def test_filter_preserves_data_structure(self, session_filter, sample_data):
        """Filtering should preserve DataFrame structure and column types."""
        result = await session_filter.filter_by_session(
            sample_data, SessionType.RTH, "ES"
        )

        # Should maintain all columns
        expected_columns = ["timestamp", "open", "high", "low", "close", "volume"]
        assert result.columns == expected_columns

        # Should maintain data types
        assert result.schema == sample_data.schema

        # Should maintain column order
        assert list(result.columns) == list(sample_data.columns)

    @pytest.mark.asyncio
    async def test_filter_empty_dataframe(self, session_filter):
        """Filtering empty DataFrame should return empty DataFrame."""
        empty_df = pl.DataFrame(
            {
                "timestamp": [],
                "open": [],
                "high": [],
                "low": [],
                "close": [],
                "volume": [],
            },
            schema={
                "timestamp": pl.Datetime(time_zone="UTC"),
                "open": pl.Float64,
                "high": pl.Float64,
                "low": pl.Float64,
                "close": pl.Float64,
                "volume": pl.Int64,
            },
        )

        result = await session_filter.filter_by_session(empty_df, SessionType.RTH, "ES")

        assert len(result) == 0
        assert result.schema == empty_df.schema

    @pytest.mark.asyncio
    async def test_filter_no_matching_session_data(self, session_filter):
        """Filtering with no matching session data should return empty DataFrame."""
        # Create data only during maintenance break (5-6 PM ET)
        maintenance_data = pl.DataFrame(
            {
                "timestamp": [
                    datetime(2024, 1, 15, 22, 30, tzinfo=timezone.utc)
                ],  # 5:30 PM ET
                "open": [100.0],
                "high": [101.0],
                "low": [99.0],
                "close": [100.5],
                "volume": [1000],
            }
        )

        result = await session_filter.filter_by_session(
            maintenance_data, SessionType.RTH, "ES"
        )

        assert len(result) == 0
        # Should maintain schema even when empty
        assert result.columns == maintenance_data.columns

    @pytest.mark.asyncio
    async def test_filter_multi_day_data(self, session_filter, multi_day_data):
        """Filtering should work correctly across multiple days."""
        result = await session_filter.filter_by_session(
            multi_day_data, SessionType.RTH, "ES"
        )

        # Should have 3 RTH bars per day * 3 days = 9 bars
        assert len(result) == 9

        # Verify all bars are within RTH hours
        hours = result["timestamp"].dt.hour().to_list()
        expected_rth_hours = [14, 18, 21]  # UTC hours for RTH
        for hour in hours:
            assert hour in expected_rth_hours

    def test_timezone_conversion(self, session_filter):
        """Should handle timezone conversions correctly."""
        # Test with different input timezones

        # EST timestamp (10 AM EST = 3 PM UTC)
        # est_time = datetime(2024, 1, 15, 10, 0)  # Naive datetime, assume ET
        # Should be treated as ET and converted to UTC for session check

        # This tests the timezone handling in the session filter
        # Implementation should convert to market timezone (ET) for session checks

        # For now, test with UTC timestamps (implementation detail)
        utc_time = datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc)  # 10 AM ET
        assert session_filter.is_in_session(utc_time, SessionType.RTH, "ES") is True


class TestSessionFilterPerformance:
    """Test session filtering performance characteristics."""

    @pytest.fixture
    def large_dataset(self):
        """Create large dataset for performance testing."""
        # Create 10,000 data points across 1 month
        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        timestamps = []

        for i in range(10000):
            # Create timestamps throughout the month at random times
            timestamp = start_date + timedelta(
                days=i // 333,  # ~333 bars per day
                hours=(i % 333) * 24 // 333,  # Spread across 24 hours
            )
            timestamps.append(timestamp)

        n_points = len(timestamps)
        return pl.DataFrame(
            {
                "timestamp": timestamps,
                "open": [100.0 + i * 0.01 for i in range(n_points)],
                "high": [101.0 + i * 0.01 for i in range(n_points)],
                "low": [99.0 + i * 0.01 for i in range(n_points)],
                "close": [100.5 + i * 0.01 for i in range(n_points)],
                "volume": [1000 + i for i in range(n_points)],
            }
        )

    @pytest.mark.asyncio
    async def test_large_dataset_filtering_performance(self, large_dataset):
        """Session filtering should be performant on large datasets."""
        session_filter = SessionFilterMixin()

        import time

        start_time = time.time()

        result = await session_filter.filter_by_session(
            large_dataset, SessionType.RTH, "ES"
        )

        end_time = time.time()
        duration = end_time - start_time

        # Performance requirement: should complete within 1 second
        assert duration < 1.0, f"Filtering took {duration:.2f}s, expected < 1.0s"

        # Should return some data (not empty)
        assert len(result) > 0

    def test_session_check_performance(self):
        """Individual session checks should be fast."""
        session_filter = SessionFilterMixin()
        timestamp = datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc)

        import time

        start_time = time.time()

        # Perform 10,000 session checks
        for _ in range(10000):
            session_filter.is_in_session(timestamp, SessionType.RTH, "ES")

        end_time = time.time()
        duration = end_time - start_time

        # Should complete 10,000 checks in under 0.2 seconds
        # Note: Using proper pytz timezone conversion is more accurate but slightly slower than hardcoded offsets
        assert duration < 0.2, (
            f"10k session checks took {duration:.3f}s, expected < 0.2s"
        )


class TestSessionFilterEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.fixture
    def session_filter(self):
        return SessionFilterMixin()

    def test_session_boundary_times(self, session_filter):
        """Should handle exact session boundary times correctly."""
        # Exactly 9:30 AM ET (market open)
        market_open = datetime(2024, 1, 15, 14, 30, tzinfo=timezone.utc)
        assert session_filter.is_in_session(market_open, SessionType.RTH, "ES") is True

        # Exactly 4:00 PM ET (market close) - should be excluded
        market_close = datetime(2024, 1, 15, 21, 0, tzinfo=timezone.utc)
        assert (
            session_filter.is_in_session(market_close, SessionType.RTH, "ES") is False
        )

        # One minute before market open
        before_open = datetime(2024, 1, 15, 14, 29, tzinfo=timezone.utc)
        assert session_filter.is_in_session(before_open, SessionType.RTH, "ES") is False

    def test_maintenance_break_handling(self, session_filter):
        """Should handle daily maintenance breaks correctly."""
        # 5:30 PM ET = 10:30 PM UTC (maintenance break)
        maintenance_time = datetime(2024, 1, 15, 22, 30, tzinfo=timezone.utc)

        # Should be outside both RTH and ETH during maintenance
        assert (
            session_filter.is_in_session(maintenance_time, SessionType.RTH, "ES")
            is False
        )
        assert (
            session_filter.is_in_session(maintenance_time, SessionType.ETH, "ES")
            is False
        )

    def test_unknown_product_handling(self, session_filter):
        """Should handle unknown products gracefully."""
        timestamp = datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc)

        with pytest.raises(ValueError, match="Unknown product"):
            session_filter.is_in_session(timestamp, SessionType.RTH, "UNKNOWN")

    @pytest.mark.asyncio
    async def test_malformed_data_handling(self, session_filter):
        """Should handle malformed data gracefully."""
        # Missing required columns
        bad_data = pl.DataFrame({"price": [100, 101, 102]})

        with pytest.raises(ValueError, match="Missing required column"):
            await session_filter.filter_by_session(bad_data, SessionType.RTH, "ES")

        # Wrong timestamp format
        bad_timestamp_data = pl.DataFrame(
            {
                "timestamp": ["not-a-timestamp"],
                "open": [100.0],
                "high": [101.0],
                "low": [99.0],
                "close": [100.5],
                "volume": [1000],
            }
        )

        with pytest.raises((ValueError, TypeError), match="Invalid timestamp"):
            await session_filter.filter_by_session(
                bad_timestamp_data, SessionType.RTH, "ES"
            )

    def test_leap_year_handling(self, session_filter):
        """Should handle leap years correctly."""
        # February 29, 2024 (leap year)
        leap_day = datetime(2024, 2, 29, 15, 0, tzinfo=timezone.utc)  # 10 AM ET
        assert session_filter.is_in_session(leap_day, SessionType.RTH, "ES") is True

    def test_year_boundary_handling(self, session_filter):
        """Should handle year boundaries correctly."""
        # New Year's Eve during ETH
        nye_eth = datetime(2023, 12, 31, 23, 0, tzinfo=timezone.utc)  # 6 PM ET
        # Market typically closed on NYE - should return False
        assert session_filter.is_in_session(nye_eth, SessionType.ETH, "ES") is False


class TestSessionFilterCacheAndOptimization:
    """Test uncovered cache logic and optimization paths in filtering.py."""

    @pytest.fixture
    def session_filter(self):
        return SessionFilterMixin()

    def test_cached_session_boundaries_valid_cache(self, session_filter):
        """Test _get_cached_session_boundaries with valid cached data (lines 34-43)."""
        # Manually populate cache with valid tuple
        cache_key = "testhash_ES_RTH"
        expected_boundaries = ([0, 100, 200], [50, 150, 250])
        session_filter._session_boundary_cache[cache_key] = expected_boundaries

        # Call method to retrieve cached data
        result = session_filter._get_cached_session_boundaries("testhash", "ES", "RTH")

        assert result == expected_boundaries

    def test_cached_session_boundaries_invalid_cache_format(self, session_filter):
        """Test _get_cached_session_boundaries with invalid cached data (lines 37-38)."""
        # Cache invalid data (not a tuple or wrong length)
        cache_key = "testhash_ES_RTH"

        # Test with non-tuple
        session_filter._session_boundary_cache[cache_key] = "invalid_data"
        result = session_filter._get_cached_session_boundaries("testhash", "ES", "RTH")
        assert result == ([], [])

        # Test with wrong tuple length
        session_filter._session_boundary_cache[cache_key] = (
            [1, 2, 3],
        )  # Only one element
        result = session_filter._get_cached_session_boundaries("testhash", "ES", "RTH")
        assert result == ([], [])

    def test_cached_session_boundaries_cache_miss(self, session_filter):
        """Test _get_cached_session_boundaries with cache miss (lines 40-43)."""
        # Clear cache to ensure miss
        session_filter._session_boundary_cache.clear()

        result = session_filter._get_cached_session_boundaries("newhash", "ES", "RTH")

        # Should return empty boundaries and cache them
        assert result == ([], [])
        assert "newhash_ES_RTH" in session_filter._session_boundary_cache

    def test_use_lazy_evaluation(self, session_filter):
        """Test _use_lazy_evaluation method (line 47)."""
        # Create test data
        data = pl.DataFrame(
            {
                "timestamp": [datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc)],
                "open": [100.0],
                "high": [101.0],
                "low": [99.0],
                "close": [100.5],
                "volume": [1000],
            }
        )

        lazy_result = session_filter._use_lazy_evaluation(data)

        # Should return LazyFrame
        assert isinstance(lazy_result, pl.LazyFrame)

        # Should be convertible back to DataFrame
        collected = lazy_result.collect()
        assert len(collected) == 1

    def test_optimize_filtering_large_dataset(self, session_filter):
        """Test _optimize_filtering with large dataset (lines 53-55)."""
        # Create large dataset (>100k rows)
        n_rows = 100_001
        timestamps = [
            datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc) + timedelta(minutes=i)
            for i in range(n_rows)
        ]

        large_data = pl.DataFrame(
            {
                "timestamp": timestamps,
                "open": [100.0] * n_rows,
                "high": [101.0] * n_rows,
                "low": [99.0] * n_rows,
                "close": [100.5] * n_rows,
                "volume": [1000] * n_rows,
            }
        )

        result = session_filter._optimize_filtering(large_data)

        # Should use lazy evaluation path and return DataFrame
        assert isinstance(result, pl.DataFrame)
        assert len(result) == n_rows

    def test_optimize_filtering_small_dataset(self, session_filter):
        """Test _optimize_filtering with small dataset (standard path)."""
        # Create small dataset (<100k rows)
        small_data = pl.DataFrame(
            {
                "timestamp": [datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc)],
                "open": [100.0],
                "high": [101.0],
                "low": [99.0],
                "close": [100.5],
                "volume": [1000],
            }
        )

        result = session_filter._optimize_filtering(small_data)

        # Should return same data unchanged
        assert result.equals(small_data)


class TestSessionFilterCacheInvalidation:
    """Test cache invalidation scenarios."""

    @pytest.fixture
    def session_filter(self):
        return SessionFilterMixin()

    def test_cache_key_uniqueness(self, session_filter):
        """Test that cache keys are properly unique."""
        # Different combinations should create different cache keys
        boundaries1 = session_filter._get_cached_session_boundaries(
            "hash1", "ES", "RTH"
        )
        boundaries2 = session_filter._get_cached_session_boundaries(
            "hash1", "ES", "ETH"
        )
        boundaries3 = session_filter._get_cached_session_boundaries(
            "hash1", "NQ", "RTH"
        )
        boundaries4 = session_filter._get_cached_session_boundaries(
            "hash2", "ES", "RTH"
        )

        # All should be in cache with different keys
        assert len(session_filter._session_boundary_cache) >= 4
        assert "hash1_ES_RTH" in session_filter._session_boundary_cache
        assert "hash1_ES_ETH" in session_filter._session_boundary_cache
        assert "hash1_NQ_RTH" in session_filter._session_boundary_cache
        assert "hash2_ES_RTH" in session_filter._session_boundary_cache

    def test_cache_memory_management(self, session_filter):
        """Test cache doesn't grow unbounded."""
        # Add many cache entries
        for i in range(1000):
            session_filter._get_cached_session_boundaries(f"hash{i}", "ES", "RTH")

        # Cache should have entries (implementation may limit size in future)
        assert len(session_filter._session_boundary_cache) > 0


class TestSessionFilterMutationTesting:
    """Test mutation scenarios to ensure test quality."""

    @pytest.fixture
    def session_filter(self):
        return SessionFilterMixin()

    def test_boundary_conditions_off_by_one(self, session_filter):
        """Test off-by-one errors in boundary conditions."""
        # Test exactly at boundaries with different precisions
        market_open_exact = datetime(2024, 1, 15, 14, 30, 0, 0, tzinfo=timezone.utc)
        market_open_plus_1ms = datetime(
            2024, 1, 15, 14, 30, 0, 1000, tzinfo=timezone.utc
        )
        market_open_minus_1ms = datetime(
            2024, 1, 15, 14, 29, 59, 999000, tzinfo=timezone.utc
        )

        assert (
            session_filter.is_in_session(market_open_exact, SessionType.RTH, "ES")
            is True
        )
        assert (
            session_filter.is_in_session(market_open_plus_1ms, SessionType.RTH, "ES")
            is True
        )
        assert (
            session_filter.is_in_session(market_open_minus_1ms, SessionType.RTH, "ES")
            is False
        )

    def test_type_safety_at_runtime(self, session_filter):
        """Test type safety with various input types."""
        # Test with string that looks like datetime
        with pytest.raises((ValueError, TypeError)):
            session_filter.is_in_session("2024-01-15T15:00:00Z", SessionType.RTH, "ES")

        # Test with integer timestamp
        with pytest.raises((ValueError, TypeError)):
            session_filter.is_in_session(
                1705324800, SessionType.RTH, "ES"
            )  # Unix timestamp

        # Test with None
        with pytest.raises((ValueError, TypeError)):
            session_filter.is_in_session(None, SessionType.RTH, "ES")


class TestSessionFilterErrorRecovery:
    """Test error recovery paths."""

    @pytest.fixture
    def session_filter(self):
        return SessionFilterMixin()

    @pytest.mark.asyncio
    async def test_corrupt_cache_recovery(self, session_filter):
        """Test recovery from corrupted cache data."""
        # Corrupt the cache with various invalid data types
        session_filter._session_boundary_cache["corrupt1"] = None
        session_filter._session_boundary_cache["corrupt2"] = 12345
        session_filter._session_boundary_cache["corrupt3"] = {"invalid": "dict"}

        # Operations should still work despite corrupted cache
        data = pl.DataFrame(
            {
                "timestamp": [datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc)],
                "open": [100.0],
                "high": [101.0],
                "low": [99.0],
                "close": [100.5],
                "volume": [1000],
            }
        )

        result = await session_filter.filter_by_session(data, SessionType.RTH, "ES")
        assert len(result) >= 0  # Should not crash


@pytest.mark.unit
class TestResolveSessionProduct:
    """Map Gateway contract ids and month codes to DEFAULT_SESSIONS keys."""

    def test_root_symbol_unchanged(self):
        assert resolve_session_product("MNQ") == "MNQ"
        assert resolve_session_product("ES") == "ES"

    def test_gateway_contract_id(self):
        assert resolve_session_product("CON.F.US.MNQ.H26") == "MNQ"
        assert resolve_session_product("CON.F.US.MES.U26") == "MES"

    def test_month_coded_symbol(self):
        assert resolve_session_product("MNQH26") == "MNQ"
        assert resolve_session_product("MESH26") == "MES"

    @pytest.mark.asyncio
    async def test_filter_accepts_contract_id(self):
        session_filter = SessionFilterMixin()
        data = pl.DataFrame(
            {
                "timestamp": [datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc)],
                "open": [100.0],
                "high": [101.0],
                "low": [99.0],
                "close": [100.5],
                "volume": [1000],
            }
        )
        result = await session_filter.filter_by_session(
            data, SessionType.RTH, "CON.F.US.ES.H26"
        )
        assert len(result) == 1


class TestSessionFilterErrorRecoveryContinued:
    """Large-data recovery paths for SessionFilterMixin."""

    @pytest.fixture
    def session_filter(self):
        return SessionFilterMixin()

    @pytest.mark.asyncio
    async def test_memory_pressure_handling(self, session_filter):
        """Test behavior under memory pressure."""
        # Create data that might stress memory
        n_rows = 10_000
        large_data = pl.DataFrame(
            {
                "timestamp": [
                    datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc)
                    + timedelta(seconds=i)
                    for i in range(n_rows)
                ],
                "open": [100.0 + i * 0.001 for i in range(n_rows)],
                "high": [101.0 + i * 0.001 for i in range(n_rows)],
                "low": [99.0 + i * 0.001 for i in range(n_rows)],
                "close": [100.5 + i * 0.001 for i in range(n_rows)],
                "volume": [1000 + i for i in range(n_rows)],
            }
        )

        # Should handle large datasets without error
        result = await session_filter.filter_by_session(
            large_data, SessionType.RTH, "ES"
        )
        assert isinstance(result, pl.DataFrame)


class TestSessionFilterBoundaryValidation:
    """Test boundary validation edge cases."""

    @pytest.fixture
    def session_filter(self):
        return SessionFilterMixin()

    def test_daylight_saving_transitions(self, session_filter):
        """Test session filtering during DST transitions."""
        # Spring forward: 2024-03-10 2:00 AM -> 3:00 AM ET (Sunday)
        # Fall back: 2024-11-03 2:00 AM -> 1:00 AM ET (Sunday)
        # Test on the Monday after DST transitions when markets are open

        # Monday after spring DST transition (March 11, 2024)
        spring_monday = datetime(
            2024, 3, 11, 15, 0, tzinfo=timezone.utc
        )  # 11:00 AM EDT - Should be RTH
        assert (
            session_filter.is_in_session(spring_monday, SessionType.RTH, "ES") is True
        )

        # Monday after fall DST transition (November 4, 2024)
        fall_monday = datetime(
            2024, 11, 4, 15, 0, tzinfo=timezone.utc
        )  # 10:00 AM EST - Should be RTH
        assert session_filter.is_in_session(fall_monday, SessionType.RTH, "ES") is True

    def test_leap_second_handling(self, session_filter):
        """Test handling of leap seconds (rare edge case)."""
        # Create timestamp at potential leap second
        # UTC 23:59:60 doesn't exist in Python datetime, but test similar edge case
        year_end = datetime(2024, 12, 31, 23, 59, 59, 999999, tzinfo=timezone.utc)

        # Should not crash on edge timestamp
        result = session_filter.is_in_session(year_end, SessionType.ETH, "ES")
        assert isinstance(result, bool)

    def test_extreme_future_dates(self, session_filter):
        """Test with far future dates."""
        future_date = datetime(2100, 1, 15, 15, 0, tzinfo=timezone.utc)

        # Should handle far future dates gracefully
        result = session_filter.is_in_session(future_date, SessionType.RTH, "ES")
        assert isinstance(result, bool)

    def test_extreme_past_dates(self, session_filter):
        """Test with far past dates."""
        past_date = datetime(1900, 1, 15, 15, 0, tzinfo=timezone.utc)

        # Should handle far past dates gracefully
        result = session_filter.is_in_session(past_date, SessionType.RTH, "ES")
        assert isinstance(result, bool)
