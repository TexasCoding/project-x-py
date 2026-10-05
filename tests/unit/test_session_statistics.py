"""
Tests for session statistics and analysis functionality.

This test file defines the EXPECTED behavior for calculating trading
statistics by session (RTH/ETH). Following strict TDD methodology - these
tests define the specification, not the current behavior.

Author: TDD Implementation
Date: 2025-08-28
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List

import polars as pl
import pytest

# Note: These imports will fail initially - that's expected in RED phase
from project_x_py.sessions import (
    SessionAnalytics,
    SessionConfig,
    SessionFilterMixin,
    SessionStatistics,
    SessionType,
)


class TestSessionStatistics:
    """Test session statistics calculations."""

    @pytest.fixture
    def session_stats(self):
        """Create session statistics calculator."""
        return SessionStatistics()

    @pytest.fixture
    def sample_session_data(self):
        """Create sample data with clear RTH/ETH distinction."""
        # Monday Jan 15, 2024 - Mixed session data
        timestamps_and_sessions = [
            # Pre-market ETH (3 AM ET = 8 AM UTC)
            (datetime(2024, 1, 15, 8, 0, tzinfo=timezone.utc), "ETH"),
            # RTH Open (9:30 AM ET = 14:30 UTC)
            (datetime(2024, 1, 15, 14, 30, tzinfo=timezone.utc), "RTH"),
            # RTH Mid-day (1:00 PM ET = 18:00 UTC)
            (datetime(2024, 1, 15, 18, 0, tzinfo=timezone.utc), "RTH"),
            # RTH Close (4:00 PM ET = 21:00 UTC)
            (datetime(2024, 1, 15, 21, 0, tzinfo=timezone.utc), "RTH"),
            # After-hours ETH (7 PM ET = 12 AM UTC next day)
            (datetime(2024, 1, 16, 0, 0, tzinfo=timezone.utc), "ETH"),
        ]

        return pl.DataFrame({
            "timestamp": [ts for ts, _ in timestamps_and_sessions],
            "open": [100.0, 101.0, 102.0, 103.0, 104.0],
            "high": [102.0, 103.0, 104.0, 105.0, 106.0],
            "low": [99.0, 100.0, 101.0, 102.0, 103.0],
            "close": [101.5, 102.5, 103.5, 104.5, 105.5],
            "volume": [5000, 10000, 15000, 8000, 3000],  # Higher volume during RTH
            "session": [session for _, session in timestamps_and_sessions]
        })

    @pytest.fixture
    def price_level_data(self):
        """Create data for testing price levels and ranges."""
        return pl.DataFrame({
            "timestamp": [
                datetime(2024, 1, 15, 14, 30, tzinfo=timezone.utc),  # RTH
                datetime(2024, 1, 15, 18, 0, tzinfo=timezone.utc),   # RTH
                datetime(2024, 1, 16, 0, 0, tzinfo=timezone.utc),    # ETH
            ],
            "open": [100.0, 105.0, 102.0],
            "high": [108.0, 110.0, 103.0],  # RTH has wider range
            "low": [98.0, 103.0, 101.0],
            "close": [107.0, 108.0, 102.5],
            "volume": [20000, 25000, 5000]
        })

    @pytest.mark.asyncio
    async def test_calculate_session_stats_basic(self, session_stats, sample_session_data):
        """Should calculate basic statistics for each session."""
        stats = await session_stats.calculate_session_stats(sample_session_data, "ES")

        # Should contain required statistics
        required_keys = [
            "rth_volume", "eth_volume",
            "rth_vwap", "eth_vwap",
            "rth_range", "eth_range",
            "rth_high", "rth_low",
            "eth_high", "eth_low"
        ]

        for key in required_keys:
            assert key in stats, f"Missing statistic: {key}"
            assert stats[key] is not None, f"Statistic {key} is None"

    @pytest.mark.asyncio
    async def test_session_volume_calculations(self, session_stats, sample_session_data):
        """Should calculate volume correctly for each session."""
        stats = await session_stats.calculate_session_stats(sample_session_data, "ES")

        # RTH volume: 10000 + 15000 + 8000 = 33000
        expected_rth_volume = 33000
        assert stats["rth_volume"] == expected_rth_volume

        # ETH volume: all bars (5000 + 10000 + 15000 + 8000 + 3000 = 41000)
        expected_eth_volume = 41000
        assert stats["eth_volume"] == expected_eth_volume

        # RTH should be subset of ETH
        assert stats["rth_volume"] < stats["eth_volume"]

    @pytest.mark.asyncio
    async def test_session_vwap_calculations(self, session_stats, sample_session_data):
        """Should calculate VWAP correctly for each session."""
        stats = await session_stats.calculate_session_stats(sample_session_data, "ES")

        # RTH VWAP calculation:
        # Bar 1: close=102.5, volume=10000
        # Bar 2: close=103.5, volume=15000
        # Bar 3: close=104.5, volume=8000
        # VWAP = (102.5*10000 + 103.5*15000 + 104.5*8000) / (10000+15000+8000)
        expected_rth_vwap = (102.5*10000 + 103.5*15000 + 104.5*8000) / 33000

        assert abs(stats["rth_vwap"] - expected_rth_vwap) < 0.01, \
            f"RTH VWAP {stats['rth_vwap']} != expected {expected_rth_vwap}"

        # ETH VWAP should include all data points
        eth_numerator = (101.5*5000 + 102.5*10000 + 103.5*15000 + 104.5*8000 + 105.5*3000)
        expected_eth_vwap = eth_numerator / 41000

        assert abs(stats["eth_vwap"] - expected_eth_vwap) < 0.01, \
            f"ETH VWAP {stats['eth_vwap']} != expected {expected_eth_vwap}"

    @pytest.mark.asyncio
    async def test_session_range_calculations(self, session_stats, price_level_data):
        """Should calculate price ranges correctly for each session."""
        stats = await session_stats.calculate_session_stats(price_level_data, "ES")

        # RTH data: high=[108, 110], low=[98, 103]
        # RTH range = max(108, 110) - min(98, 103) = 110 - 98 = 12
        expected_rth_range = 12.0
        assert abs(stats["rth_range"] - expected_rth_range) < 0.01

        # ETH data includes all: high=[108, 110, 103], low=[98, 103, 101]
        # ETH range = max(108, 110, 103) - min(98, 103, 101) = 110 - 98 = 12
        expected_eth_range = 12.0
        assert abs(stats["eth_range"] - expected_eth_range) < 0.01

    @pytest.mark.asyncio
    async def test_session_high_low_levels(self, session_stats, price_level_data):
        """Should calculate session high/low levels correctly."""
        stats = await session_stats.calculate_session_stats(price_level_data, "ES")

        # RTH high/low
        assert stats["rth_high"] == 110.0  # Max of RTH highs
        assert stats["rth_low"] == 98.0    # Min of RTH lows

        # ETH high/low
        assert stats["eth_high"] == 110.0  # Max of all highs
        assert stats["eth_low"] == 98.0    # Min of all lows

    @pytest.mark.asyncio
    async def test_session_stats_empty_data(self, session_stats):
        """Should handle empty data gracefully."""
        empty_data = pl.DataFrame({
            "timestamp": [],
            "open": [],
            "high": [],
            "low": [],
            "close": [],
            "volume": []
        }, schema={
            "timestamp": pl.Datetime(time_zone="UTC"),
            "open": pl.Float64,
            "high": pl.Float64,
            "low": pl.Float64,
            "close": pl.Float64,
            "volume": pl.Int64
        })

        stats = await session_stats.calculate_session_stats(empty_data, "ES")

        # Should return default/zero values for all statistics
        assert stats["rth_volume"] == 0
        assert stats["eth_volume"] == 0
        assert stats["rth_vwap"] == 0.0
        assert stats["eth_vwap"] == 0.0

    @pytest.mark.asyncio
    async def test_session_stats_different_products(self, session_stats, sample_session_data):
        """Should calculate stats correctly for different products."""
        es_stats = await session_stats.calculate_session_stats(sample_session_data, "ES")
        cl_stats = await session_stats.calculate_session_stats(sample_session_data, "CL")

        # Different products have different RTH hours, so volumes should differ
        # ES RTH: 9:30 AM - 4:00 PM ET (includes 4 PM bar)
        # CL RTH: 9:00 AM - 2:30 PM ET (excludes 4 PM bar)
        assert es_stats["rth_volume"] > cl_stats["rth_volume"]
        assert es_stats["rth_volume"] == 33000  # 10000 + 15000 + 8000
        assert cl_stats["rth_volume"] == 25000  # 10000 + 15000 (missing 4 PM)

        # Both should have same ETH volume (all data)
        assert es_stats["eth_volume"] == cl_stats["eth_volume"]


class TestSessionAnalytics:
    """Test advanced session analytics and comparisons."""

    @pytest.fixture
    def session_analytics(self):
        """Create session analytics calculator."""
        return SessionAnalytics()

    @pytest.fixture
    def multi_session_data(self):
        """Create multi-day data for analytics testing."""
        base_date = datetime(2024, 1, 15, tzinfo=timezone.utc)
        data_points = []

        for day in range(5):  # 5 trading days
            day_offset = timedelta(days=day)

            # RTH session data
            for hour_offset in [14.5, 18, 21]:  # 9:30 AM, 1 PM, 4 PM ET in UTC
                timestamp = base_date + day_offset + timedelta(hours=hour_offset)
                price_base = 100 + day * 2  # Trending up over days

                data_points.append({
                    "timestamp": timestamp,
                    "open": price_base + hour_offset/10,
                    "high": price_base + hour_offset/10 + 1,
                    "low": price_base + hour_offset/10 - 1,
                    "close": price_base + hour_offset/10 + 0.5,
                    "volume": 10000 + hour_offset * 1000  # Volume varies by time
                })

            # ETH session data
            eth_timestamp = base_date + day_offset + timedelta(hours=2)  # 9 PM ET prev day
            data_points.append({
                "timestamp": eth_timestamp,
                "open": price_base - 0.5,
                "high": price_base + 0.5,
                "low": price_base - 1.5,
                "close": price_base,
                "volume": 3000  # Lower overnight volume
            })

        return pl.DataFrame(data_points)

    @pytest.mark.asyncio
    async def test_session_comparison_analytics(self, session_analytics, multi_session_data):
        """Should provide comparative analytics between sessions."""
        comparison = await session_analytics.compare_sessions(multi_session_data, "ES")

        # Should include comparison metrics
        required_metrics = [
            "rth_vs_eth_volume_ratio",
            "rth_vs_eth_volatility_ratio",
            "session_participation_rate",
            "rth_premium_discount",
            "overnight_gap_average"
        ]

        for metric in required_metrics:
            assert metric in comparison, f"Missing metric: {metric}"

    @pytest.mark.asyncio
    async def test_session_volume_profile(self, session_analytics, multi_session_data):
        """Should calculate volume profile by session."""
        profile = await session_analytics.get_session_volume_profile(multi_session_data, "ES")

        # Should contain volume distribution
        assert "rth_volume_by_hour" in profile
        assert "eth_volume_by_hour" in profile
        assert "peak_volume_time" in profile

        # Volume profile should show RTH concentration
        assert profile["peak_volume_time"]["session"] == "RTH"

    @pytest.mark.asyncio
    async def test_session_volatility_analysis(self, session_analytics, multi_session_data):
        """Should analyze volatility by session."""
        volatility = await session_analytics.analyze_session_volatility(multi_session_data, "ES")

        assert "rth_realized_volatility" in volatility
        assert "eth_realized_volatility" in volatility
        assert "volatility_ratio" in volatility
        assert "volatility_clustering" in volatility

    @pytest.mark.asyncio
    async def test_session_gap_analysis(self, session_analytics, multi_session_data):
        """Should analyze gaps between sessions."""
        gaps = await session_analytics.analyze_session_gaps(multi_session_data, "ES")

        assert "average_overnight_gap" in gaps
        assert "gap_frequency" in gaps
        assert "gap_fill_rate" in gaps
        assert "largest_gap" in gaps

        # Should identify gap patterns
        assert isinstance(gaps["gap_frequency"], dict)

    @pytest.mark.asyncio
    async def test_session_efficiency_metrics(self, session_analytics, multi_session_data):
        """Should calculate session efficiency metrics."""
        efficiency = await session_analytics.calculate_efficiency_metrics(multi_session_data, "ES")

        assert "rth_price_efficiency" in efficiency
        assert "eth_price_efficiency" in efficiency
        assert "rth_volume_efficiency" in efficiency
        assert "session_liquidity_ratio" in efficiency


@pytest.fixture
def large_session_dataset():
    """Create large dataset for performance testing."""
    start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
    data_points = []

    # Create 50,000 data points (roughly 3 months of 1-minute data)
    for i in range(50000):
        timestamp = start_date + timedelta(minutes=i)
        price = 100.0 + (i % 1000) * 0.01  # Price oscillation

        data_points.append({
            "timestamp": timestamp,
            "open": price,
            "high": price + 0.5,
            "low": price - 0.5,
            "close": price + 0.25,
            "volume": 1000 + (i % 100) * 10
        })

    return pl.DataFrame(data_points)


class TestSessionStatisticsPerformance:
    """Test performance characteristics of session statistics."""

    @pytest.mark.asyncio
    async def test_large_dataset_statistics_performance(self, large_session_dataset):
        """Session statistics should be performant on large datasets."""
        session_stats = SessionStatistics()

        import time
        start_time = time.time()

        stats = await session_stats.calculate_session_stats(large_session_dataset, "ES")

        end_time = time.time()
        duration = end_time - start_time

        # Performance requirement: should complete within 2 seconds
        assert duration < 2.0, f"Statistics calculation took {duration:.2f}s, expected < 2.0s"

        # Should return valid results
        assert stats["rth_volume"] > 0
        assert stats["eth_volume"] > stats["rth_volume"]

    @pytest.mark.asyncio
    async def test_session_analytics_performance(self, large_session_dataset):
        """Advanced analytics should be performant."""
        session_analytics = SessionAnalytics()

        import time
        start_time = time.time()

        comparison = await session_analytics.compare_sessions(large_session_dataset, "ES")

        end_time = time.time()
        duration = end_time - start_time

        # Should complete advanced analytics within 3 seconds
        assert duration < 3.0, f"Analytics took {duration:.2f}s, expected < 3.0s"
        assert "rth_vs_eth_volume_ratio" in comparison


class TestSessionStatisticsIntegration:
    """Test integration with session filtering and configuration."""

    @pytest.fixture
    def integrated_session_system(self):
        """Create integrated session system."""
        config = SessionConfig(session_type=SessionType.RTH)
        filter_mixin = SessionFilterMixin()
        statistics = SessionStatistics()

        return {
            "config": config,
            "filter": filter_mixin,
            "statistics": statistics
        }

    @pytest.fixture
    def mixed_product_data(self):
        """Create data spanning different products and sessions."""
        return {
            "ES": pl.DataFrame({
                "timestamp": [
                    datetime(2024, 1, 15, 14, 30, tzinfo=timezone.utc),  # RTH
                    datetime(2024, 1, 15, 22, 0, tzinfo=timezone.utc),   # ETH
                ],
                "open": [100.0, 101.0],
                "high": [102.0, 103.0],
                "low": [99.0, 100.0],
                "close": [101.5, 102.5],
                "volume": [10000, 3000]
            }),
            "CL": pl.DataFrame({
                "timestamp": [
                    datetime(2024, 1, 15, 14, 0, tzinfo=timezone.utc),   # RTH for CL (9 AM ET)
                    datetime(2024, 1, 15, 20, 0, tzinfo=timezone.utc),   # ETH
                ],
                "open": [70.0, 70.5],
                "high": [71.0, 71.5],
                "low": [69.5, 70.0],
                "close": [70.8, 71.2],
                "volume": [15000, 2000]
            })
        }

    @pytest.mark.asyncio
    async def test_integrated_session_workflow(self, integrated_session_system, mixed_product_data):
        """Should work seamlessly with filtering and statistics."""
        system = integrated_session_system

        for product, data in mixed_product_data.items():
            # Filter data by session
            rth_data = await system["filter"].filter_by_session(
                data, SessionType.RTH, product
            )

            # Calculate statistics on filtered data
            stats = await system["statistics"].calculate_session_stats(data, product)

            # Verify integration works
            assert len(rth_data) > 0, f"No RTH data for {product}"
            assert stats["rth_volume"] > 0, f"No RTH volume for {product}"

    @pytest.mark.asyncio
    async def test_session_stats_with_custom_config(self, mixed_product_data):
        """Should work with custom session configurations."""
        # Custom session times for ES
        from project_x_py.sessions import SessionTimes
        custom_times = SessionTimes(
            rth_start=datetime.strptime("10:00", "%H:%M").time(),
            rth_end=datetime.strptime("15:00", "%H:%M").time(),
            eth_start=datetime.strptime("18:00", "%H:%M").time(),
            eth_end=datetime.strptime("17:00", "%H:%M").time()
        )

        config = SessionConfig(
            session_type=SessionType.CUSTOM,
            product_sessions={"ES": custom_times}
        )

        statistics = SessionStatistics(config=config)
        stats = await statistics.calculate_session_stats(mixed_product_data["ES"], "ES")

        # Should calculate stats with custom session times
        assert stats is not None
        assert "rth_volume" in stats

    def test_session_statistics_caching(self):
        """Should cache frequently accessed statistics."""
        session_stats = SessionStatistics()

        # Should implement caching for performance
        assert hasattr(session_stats, '_stats_cache') or hasattr(session_stats, 'cache_enabled')

    @pytest.mark.asyncio
    async def test_session_statistics_memory_efficiency(self, large_session_dataset):
        """Should be memory efficient with large datasets."""
        import os

        import psutil

        process = psutil.Process(os.getpid())
        memory_before = process.memory_info().rss / 1024 / 1024  # MB

        session_stats = SessionStatistics()
        stats = await session_stats.calculate_session_stats(large_session_dataset, "ES")

        memory_after = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = memory_after - memory_before

        # Should not use excessive memory (< 100MB increase for 50k rows)
        assert memory_increase < 100, f"Memory usage increased by {memory_increase:.1f}MB"

        # Should still return valid results
        assert stats["rth_volume"] > 0


class TestSessionStatisticsEdgeCases:
    """Test edge cases and uncovered lines in statistics.py."""

    @pytest.fixture
    def stats(self):
        from project_x_py.sessions.statistics import SessionStatistics
        return SessionStatistics()

    @pytest.mark.asyncio
    async def test_calculate_session_stats_empty_dataframe(self, stats):
        """Test calculate_session_stats with empty DataFrame."""
        empty_df = pl.DataFrame({
            "timestamp": [],
            "open": [],
            "high": [],
            "low": [],
            "close": [],
            "volume": []
        }, schema={
            "timestamp": pl.Datetime(time_zone="UTC"),
            "open": pl.Float64,
            "high": pl.Float64,
            "low": pl.Float64,
            "close": pl.Float64,
            "volume": pl.Int64
        })

        result = await stats.calculate_session_stats(empty_df, "ES")

        # Should return empty stats structure
        expected_keys = [
            "rth_volume", "eth_volume", "rth_vwap", "eth_vwap",
            "rth_range", "eth_range", "rth_high", "rth_low", "eth_high", "eth_low"
        ]
        for key in expected_keys:
            assert key in result
            assert result[key] == 0 or result[key] == 0.0

    def test_safe_convert_to_float_edge_cases(self, stats):
        """Test _safe_convert_to_float with various input types."""
        # None input
        assert stats._safe_convert_to_float(None) == 0.0

        # Valid int
        assert stats._safe_convert_to_float(42) == 42.0

        # Valid float
        assert stats._safe_convert_to_float(3.14) == 3.14

        # String input (invalid)
        assert stats._safe_convert_to_float("not_a_number") == 0.0

        # List input (invalid)
        assert stats._safe_convert_to_float([1, 2, 3]) == 0.0

        # Boolean input (should work as it's int-like)
        assert stats._safe_convert_to_float(True) == 1.0
        assert stats._safe_convert_to_float(False) == 0.0

    def test_calculate_high_low_range_empty_data(self, stats):
        """Test _calculate_high_low_range with empty DataFrame."""
        empty_df = pl.DataFrame({
            "high": [],
            "low": []
        }, schema={"high": pl.Float64, "low": pl.Float64})

        result = stats._calculate_high_low_range(empty_df)

        # Should handle empty data gracefully
        expected = {"high": 0.0, "low": 0.0, "range": 0.0}
        assert result == expected

    def test_calculate_high_low_range_none_values(self, stats):
        """Test _calculate_high_low_range with None values from Polars."""
        # Create DataFrame with actual None values
        df_with_none = pl.DataFrame({
            "high": [None, None],
            "low": [None, None]
        })

        result = stats._calculate_high_low_range(df_with_none)

        # Should handle None values safely
        assert result["high"] == 0.0
        assert result["low"] == 0.0
        assert result["range"] == 0.0

    def test_calculate_vwap_empty_data(self, stats):
        """Test _calculate_vwap with empty DataFrame."""
        empty_df = pl.DataFrame({
            "close": [],
            "volume": []
        }, schema={"close": pl.Float64, "volume": pl.Int64})

        result = stats._calculate_vwap(empty_df)
        assert result == 0.0

    def test_calculate_vwap_zero_volume(self, stats):
        """Test _calculate_vwap with zero total volume."""
        zero_volume_df = pl.DataFrame({
            "close": [100.0, 101.0, 102.0],
            "volume": [0, 0, 0]
        })

        result = stats._calculate_vwap(zero_volume_df)
        # Should return 0.0 to avoid division by zero
        assert result == 0.0

    def test_calculate_vwap_volume_weighted_average(self, stats):
        """Test _calculate_vwap uses volume weighting, not a simple mean."""
        data = pl.DataFrame({
            "close": [100.0, 200.0],
            "volume": [1, 3],
        })

        result = stats._calculate_vwap(data)

        # (100*1 + 200*3) / (1+3) = 175; simple mean would be 150
        assert result == 175.0
        assert isinstance(result, float)

    def test_calculate_vwap_single_bar_equals_close(self, stats):
        """Test _calculate_vwap of a single bar equals that bar's close."""
        data = pl.DataFrame({
            "close": [4905.25],
            "volume": [10000],
        })

        result = stats._calculate_vwap(data)
        assert result == 4905.25
        assert isinstance(result, float)

    def test_calculate_volume_precision(self, stats):
        """Test _calculate_volume handles large numbers correctly."""
        large_volume_df = pl.DataFrame({
            "volume": [1_000_000, 2_000_000, 3_000_000]
        })

        result = stats._calculate_volume(large_volume_df)
        assert result == 6_000_000
        assert isinstance(result, int)


class TestSessionAnalyticsEdgeCases:
    """Test edge cases in SessionAnalytics."""

    @pytest.fixture
    def analytics(self):
        from project_x_py.sessions.statistics import SessionAnalytics
        return SessionAnalytics()

    @pytest.mark.asyncio
    async def test_compare_sessions_zero_volume(self, analytics):
        """Test compare_sessions with zero volume scenarios."""
        # Create data with zero ETH volume
        data_with_zero = pl.DataFrame({
            "timestamp": [datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc)],
            "open": [100.0],
            "high": [101.0],
            "low": [99.0],
            "close": [100.5],
            "volume": [1000]  # This will be filtered to show RTH volume only
        })

        result = await analytics.compare_sessions(data_with_zero, "ES")

        # Should handle division by zero gracefully
        assert "rth_vs_eth_volume_ratio" in result
        assert isinstance(result["rth_vs_eth_volume_ratio"], float)

    @pytest.mark.asyncio
    async def test_get_session_volume_profile_empty_data(self, analytics):
        """Test get_session_volume_profile with empty DataFrame."""
        empty_df = pl.DataFrame({
            "timestamp": [],
            "volume": []
        }, schema={
            "timestamp": pl.Datetime(time_zone="UTC"),
            "volume": pl.Int64
        })

        result = await analytics.get_session_volume_profile(empty_df, "ES")

        # Should return default structure
        expected_keys = ["rth_volume_by_hour", "eth_volume_by_hour", "peak_volume_time"]
        for key in expected_keys:
            assert key in result

        # Peak volume time should have defaults
        assert result["peak_volume_time"]["hour"] == 0
        assert result["peak_volume_time"]["volume"] == 0

    @pytest.mark.asyncio
    async def test_get_session_volume_profile_single_hour(self, analytics):
        """Test get_session_volume_profile with single hour of data."""
        single_hour_df = pl.DataFrame({
            "timestamp": [datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc)],
            "volume": [5000]
        })

        result = await analytics.get_session_volume_profile(single_hour_df, "ES")

        # Should identify peak volume time correctly
        peak_time = result["peak_volume_time"]
        assert peak_time["hour"] == 15  # 15:00 UTC
        assert peak_time["volume"] == 5000
        assert peak_time["session"] == "RTH"

    @pytest.mark.asyncio
    async def test_analyze_session_volatility_zero_range(self, analytics):
        """Test analyze_session_volatility with zero ETH range."""
        # Create flat price data (no volatility)
        flat_data = pl.DataFrame({
            "timestamp": [datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc)],
            "open": [100.0],
            "high": [100.0],  # Same as open/close
            "low": [100.0],   # Same as open/close
            "close": [100.0],
            "volume": [1000]
        })

        result = await analytics.analyze_session_volatility(flat_data, "ES")

        # Should handle zero volatility case
        assert "volatility_ratio" in result
        assert isinstance(result["volatility_ratio"], float)


class TestSessionStatisticsConcurrentAccess:
    """Test concurrent access patterns for statistics."""

    @pytest.mark.asyncio
    async def test_concurrent_stats_calculations(self):
        """Test concurrent statistics calculations don't interfere."""
        import asyncio
        from project_x_py.sessions.statistics import SessionStatistics

        stats = SessionStatistics()
        data = pl.DataFrame({
            "timestamp": [datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc)],
            "open": [100.0],
            "high": [101.0],
            "low": [99.0],
            "close": [100.5],
            "volume": [1000]
        })

        async def calc_stats():
            return await stats.calculate_session_stats(data, "ES")

        # Run multiple concurrent calculations
        tasks = [calc_stats() for _ in range(10)]
        results = await asyncio.gather(*tasks)

        # All results should be identical
        first_result = results[0]
        for result in results[1:]:
            assert result == first_result

    @pytest.mark.asyncio
    async def test_concurrent_analytics_operations(self):
        """Test concurrent analytics operations."""
        import asyncio
        from project_x_py.sessions.statistics import SessionAnalytics

        analytics = SessionAnalytics()
        data = pl.DataFrame({
            "timestamp": [datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc)],
            "open": [100.0],
            "high": [101.0],
            "low": [99.0],
            "close": [100.5],
            "volume": [1000]
        })

        async def run_analytics():
            compare_task = analytics.compare_sessions(data, "ES")
            volatility_task = analytics.analyze_session_volatility(data, "ES")
            profile_task = analytics.get_session_volume_profile(data, "ES")

            return await asyncio.gather(compare_task, volatility_task, profile_task)

        # Run concurrent analytics
        results = await run_analytics()

        # Should have 3 different result types
        assert len(results) == 3
        assert all(isinstance(result, dict) for result in results)


class TestSessionStatisticsErrorHandling:
    """Test error handling and recovery scenarios."""

    @pytest.mark.asyncio
    async def test_malformed_data_handling(self):
        """Test handling of malformed data."""
        from project_x_py.sessions.statistics import SessionStatistics

        stats = SessionStatistics()

        # Missing required columns
        bad_data = pl.DataFrame({"price": [100, 101, 102]})

        # Should handle gracefully (may raise exception or return empty stats)
        try:
            result = await stats.calculate_session_stats(bad_data, "ES")
            # If no exception, should return some form of valid response
            assert isinstance(result, dict)
        except Exception as e:
            # If exception is raised, it should be informative
            assert "timestamp" in str(e).lower() or "column" in str(e).lower()

    @pytest.mark.asyncio
    async def test_extreme_price_values(self):
        """Test with extreme price values."""
        import math
        from project_x_py.sessions.statistics import SessionStatistics

        stats = SessionStatistics()

        # Very small prices
        small_price_data = pl.DataFrame({
            "timestamp": [datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc)],
            "open": [0.00001],
            "high": [0.00002],
            "low": [0.000005],
            "close": [0.000015],
            "volume": [1000000]  # Large volume to offset small prices
        })

        result = await stats.calculate_session_stats(small_price_data, "ES")

        # Should handle small values without overflow/underflow
        for key, value in result.items():
            if isinstance(value, float):
                assert not math.isnan(value)
                assert not math.isinf(value)
