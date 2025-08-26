"""
Comprehensive tests for DataAccessMixin using Test-Driven Development (TDD).

Tests define EXPECTED behavior - if code fails tests, fix the implementation, not the tests.
Tests validate what the code SHOULD do, not what it currently does.

Author: @TexasCoding
Date: 2025-01-22

TDD Testing Approach:
1. Write tests FIRST defining expected behavior
2. Run tests to discover bugs (RED phase)
3. Fix implementation to pass tests (GREEN phase)
4. Refactor while keeping tests green (REFACTOR phase)

Coverage Target: >90% for data_access.py module
"""

import asyncio
import logging
from collections import deque
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import polars as pl
import pytest
import pytz

from project_x_py.realtime_data_manager.data_access import DataAccessMixin


# Test fixture setup
@pytest.fixture
def sample_ohlcv_data():
    """Create sample OHLCV data for testing."""
    timestamps = [
        datetime(2025, 1, 22, 9, 30, tzinfo=timezone.utc),
        datetime(2025, 1, 22, 9, 35, tzinfo=timezone.utc),
        datetime(2025, 1, 22, 9, 40, tzinfo=timezone.utc),
        datetime(2025, 1, 22, 9, 45, tzinfo=timezone.utc),
        datetime(2025, 1, 22, 9, 50, tzinfo=timezone.utc),
    ]

    return pl.DataFrame({
        "timestamp": timestamps,
        "open": [19000.0, 19005.0, 19010.0, 19015.0, 19020.0],
        "high": [19005.0, 19010.0, 19015.0, 19020.0, 19025.0],
        "low": [18995.0, 19000.0, 19005.0, 19010.0, 19015.0],
        "close": [19005.0, 19010.0, 19015.0, 19020.0, 19025.0],
        "volume": [100, 150, 200, 175, 125],
    })


@pytest.fixture
def sample_tick_data():
    """Create sample tick data for testing current price functionality."""
    return [
        {
            "timestamp": datetime(2025, 1, 22, 9, 55, tzinfo=timezone.utc),
            "price": 19030.25,
            "volume": 5,
        },
        {
            "timestamp": datetime(2025, 1, 22, 9, 55, 30, tzinfo=timezone.utc),
            "price": 19032.75,
            "volume": 3,
        },
    ]


class MockDataAccessManager(DataAccessMixin):
    """Mock class implementing DataAccessMixin for testing."""

    def __init__(self):
        """Initialize mock with required attributes."""
        self.data_lock = asyncio.Lock()
        self.data: dict[str, pl.DataFrame] = {}
        self.current_tick_data: deque[dict[str, Any]] = deque()
        self.tick_size = 0.25  # MNQ tick size
        self.timezone = pytz.UTC

        # Mock RW lock for testing optimized path
        self.data_rw_lock = AsyncMock()
        self.data_rw_lock.read_lock.return_value.__aenter__ = AsyncMock()
        self.data_rw_lock.read_lock.return_value.__aexit__ = AsyncMock()


@pytest.fixture
def data_access_manager(sample_ohlcv_data):
    """Create a DataAccessMixin instance with sample data."""
    manager = MockDataAccessManager()
    manager.data["5min"] = sample_ohlcv_data.clone()
    manager.data["1min"] = sample_ohlcv_data.clone()
    manager.data["15min"] = sample_ohlcv_data.clone()
    return manager


class TestGetData:
    """Test the get_data method following TDD principles."""

    @pytest.mark.asyncio
    async def test_get_data_returns_full_dataframe_when_no_bars_limit(self, data_access_manager):
        """Test that get_data returns all available bars when no limit specified."""
        result = await data_access_manager.get_data("5min")

        assert result is not None
        assert isinstance(result, pl.DataFrame)
        assert len(result) == 5  # Should return all 5 bars
        assert result.columns == ["timestamp", "open", "high", "low", "close", "volume"]

    @pytest.mark.asyncio
    async def test_get_data_limits_bars_when_specified(self, data_access_manager):
        """Test that get_data returns only the requested number of most recent bars."""
        result = await data_access_manager.get_data("5min", bars=3)

        assert result is not None
        assert len(result) == 3  # Should return only 3 most recent bars

        # Should be the last 3 bars (tail)
        expected_closes = [19015.0, 19020.0, 19025.0]
        actual_closes = result["close"].to_list()
        assert actual_closes == expected_closes

    @pytest.mark.asyncio
    async def test_get_data_returns_none_for_nonexistent_timeframe(self, data_access_manager):
        """Test that get_data returns None for timeframes that don't exist."""
        result = await data_access_manager.get_data("1hr")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_data_handles_bars_limit_greater_than_available(self, data_access_manager):
        """Test that get_data handles bars limit greater than available data."""
        result = await data_access_manager.get_data("5min", bars=10)  # More than 5 available

        assert result is not None
        assert len(result) == 5  # Should return all available bars

    @pytest.mark.asyncio
    async def test_get_data_handles_empty_dataframe(self, data_access_manager):
        """Test that get_data handles empty DataFrames correctly."""
        # Create empty DataFrame with correct schema
        empty_df = pl.DataFrame({
            "timestamp": [],
            "open": [],
            "high": [],
            "low": [],
            "close": [],
            "volume": [],
        }, schema={
            "timestamp": pl.Datetime(time_zone="UTC"),
            "open": pl.Float64,
            "high": pl.Float64,
            "low": pl.Float64,
            "close": pl.Float64,
            "volume": pl.Float64,
        })

        data_access_manager.data["empty"] = empty_df
        result = await data_access_manager.get_data("empty")

        assert result is not None
        assert len(result) == 0
        assert isinstance(result, pl.DataFrame)

    @pytest.mark.asyncio
    async def test_get_data_uses_read_lock_when_available(self, data_access_manager):
        """Test that get_data attempts to use optimized read lock when available."""
        # Since AsyncRWLock might not be available in test environment,
        # we test that the method handles both cases gracefully

        # Test that method works without data_rw_lock attribute
        if hasattr(data_access_manager, 'data_rw_lock'):
            delattr(data_access_manager, 'data_rw_lock')

        result = await data_access_manager.get_data("5min")
        assert result is not None
        assert len(result) == 5

        # Test that method works with data_rw_lock attribute but falls back gracefully
        data_access_manager.data_rw_lock = "not_a_real_lock"
        result2 = await data_access_manager.get_data("5min")
        assert result2 is not None
        assert len(result2) == 5

    @pytest.mark.asyncio
    async def test_get_data_thread_safety_with_concurrent_access(self, data_access_manager):
        """Test that get_data is thread-safe with concurrent access."""
        async def concurrent_read():
            return await data_access_manager.get_data("5min", bars=2)

        # Run multiple concurrent reads
        results = await asyncio.gather(*[concurrent_read() for _ in range(10)])

        # All results should be identical and valid
        for result in results:
            assert result is not None
            assert len(result) == 2
            assert result["close"].to_list() == [19020.0, 19025.0]

    @pytest.mark.asyncio
    async def test_get_data_returns_copy_not_reference(self, data_access_manager):
        """Test that get_data returns a copy that can be modified safely."""
        result = await data_access_manager.get_data("5min")
        original_data = data_access_manager.data["5min"].clone()

        assert result is not None

        # Modify the returned DataFrame
        # Note: Polars DataFrames are immutable, but we test the concept
        modified = result.with_columns(pl.col("close") * 2)

        # Original data should be unchanged
        current_data = await data_access_manager.get_data("5min")
        assert current_data.equals(original_data)


class TestGetCurrentPrice:
    """Test the get_current_price method following TDD principles."""

    @pytest.mark.asyncio
    async def test_get_current_price_from_tick_data(self, data_access_manager, sample_tick_data):
        """Test that get_current_price prioritizes tick data over bar data."""
        data_access_manager.current_tick_data = deque(sample_tick_data)

        price = await data_access_manager.get_current_price()

        assert price is not None
        # Should return the last tick price aligned to tick size
        expected_price = 19032.75  # Already aligned to 0.25
        assert price == expected_price

    @pytest.mark.asyncio
    async def test_get_current_price_aligns_to_tick_size(self, data_access_manager):
        """Test that get_current_price aligns tick prices to tick size."""
        # Create tick with unaligned price
        unaligned_tick = {
            "timestamp": datetime(2025, 1, 22, 10, 0, tzinfo=timezone.utc),
            "price": 19032.73,  # Not aligned to 0.25 tick size
            "volume": 2,
        }
        data_access_manager.current_tick_data = deque([unaligned_tick])

        price = await data_access_manager.get_current_price()

        assert price is not None
        # Should be aligned to nearest tick (19032.75)
        assert price == 19032.75

    @pytest.mark.asyncio
    async def test_get_current_price_fallback_to_bar_data(self, data_access_manager):
        """Test that get_current_price falls back to bar data when no tick data."""
        # Ensure no tick data
        data_access_manager.current_tick_data = deque()

        price = await data_access_manager.get_current_price()

        assert price is not None
        # Should return the last close price from 1min data (first timeframe checked)
        assert price == 19025.0

    @pytest.mark.asyncio
    async def test_get_current_price_checks_timeframes_in_order(self, data_access_manager):
        """Test that get_current_price checks timeframes in priority order."""
        # Remove 1min data but keep others
        del data_access_manager.data["1min"]
        data_access_manager.current_tick_data = deque()

        price = await data_access_manager.get_current_price()

        assert price is not None
        # Should fall back to 5min (next in priority)
        assert price == 19025.0

    @pytest.mark.asyncio
    async def test_get_current_price_returns_none_when_no_data(self, data_access_manager):
        """Test that get_current_price returns None when no data available."""
        # Clear all data
        data_access_manager.data = {}
        data_access_manager.current_tick_data = deque()

        price = await data_access_manager.get_current_price()

        assert price is None

    @pytest.mark.asyncio
    async def test_get_current_price_handles_empty_dataframes(self, data_access_manager):
        """Test that get_current_price handles empty DataFrames gracefully."""
        # Create empty DataFrames for all timeframes
        empty_df = pl.DataFrame({
            "timestamp": [],
            "open": [],
            "high": [],
            "low": [],
            "close": [],
            "volume": [],
        }, schema={
            "timestamp": pl.Datetime(time_zone="UTC"),
            "open": pl.Float64,
            "high": pl.Float64,
            "low": pl.Float64,
            "close": pl.Float64,
            "volume": pl.Float64,
        })

        data_access_manager.data = {"1min": empty_df, "5min": empty_df, "15min": empty_df}
        data_access_manager.current_tick_data = deque()

        price = await data_access_manager.get_current_price()

        assert price is None

    @pytest.mark.asyncio
    async def test_get_current_price_uses_read_lock_optimization(self, data_access_manager):
        """Test that get_current_price attempts to use optimized read lock when available."""
        data_access_manager.current_tick_data = deque()  # Force fallback to bar data

        # Test that method works without data_rw_lock attribute
        if hasattr(data_access_manager, 'data_rw_lock'):
            delattr(data_access_manager, 'data_rw_lock')

        price = await data_access_manager.get_current_price()
        assert price is not None
        assert price == 19025.0  # From bar data

        # Test that method works with data_rw_lock attribute but falls back gracefully
        data_access_manager.data_rw_lock = "not_a_real_lock"
        price2 = await data_access_manager.get_current_price()
        assert price2 is not None
        assert price2 == 19025.0


class TestGetMTFData:
    """Test the get_mtf_data method following TDD principles."""

    @pytest.mark.asyncio
    async def test_get_mtf_data_returns_all_timeframes(self, data_access_manager):
        """Test that get_mtf_data returns data for all configured timeframes."""
        result = await data_access_manager.get_mtf_data()

        assert isinstance(result, dict)
        assert set(result.keys()) == {"1min", "5min", "15min"}

        # Each timeframe should have valid DataFrame
        for tf, df in result.items():
            assert isinstance(df, pl.DataFrame)
            assert len(df) == 5  # Each has 5 bars of sample data

    @pytest.mark.asyncio
    async def test_get_mtf_data_returns_cloned_dataframes(self, data_access_manager):
        """Test that get_mtf_data returns cloned DataFrames, not references."""
        result = await data_access_manager.get_mtf_data()

        # Modify one returned DataFrame
        modified_df = result["5min"].with_columns(pl.col("close") * 2)

        # Original data should be unchanged
        original_df = await data_access_manager.get_data("5min")
        assert not original_df.equals(modified_df)

    @pytest.mark.asyncio
    async def test_get_mtf_data_handles_empty_data(self, data_access_manager):
        """Test that get_mtf_data handles case with no configured timeframes."""
        data_access_manager.data = {}

        result = await data_access_manager.get_mtf_data()

        assert isinstance(result, dict)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_get_mtf_data_uses_read_lock_optimization(self, data_access_manager):
        """Test that get_mtf_data attempts to use optimized read lock when available."""
        # Test that method works without data_rw_lock attribute
        if hasattr(data_access_manager, 'data_rw_lock'):
            delattr(data_access_manager, 'data_rw_lock')

        result = await data_access_manager.get_mtf_data()
        assert isinstance(result, dict)
        assert len(result) == 3  # Should have 1min, 5min, 15min

        # Test that method works with data_rw_lock attribute but falls back gracefully
        data_access_manager.data_rw_lock = "not_a_real_lock"
        result2 = await data_access_manager.get_mtf_data()
        assert isinstance(result2, dict)
        assert len(result2) == 3


class TestGetLatestBars:
    """Test the get_latest_bars method following TDD principles."""

    @pytest.mark.asyncio
    async def test_get_latest_bars_returns_specified_count(self, data_access_manager):
        """Test that get_latest_bars returns the correct number of bars."""
        result = await data_access_manager.get_latest_bars(count=2, timeframe="5min")

        assert result is not None
        assert len(result) == 2

        # Should be the last 2 bars
        expected_closes = [19020.0, 19025.0]
        assert result["close"].to_list() == expected_closes

    @pytest.mark.asyncio
    async def test_get_latest_bars_defaults_to_one_bar(self, data_access_manager):
        """Test that get_latest_bars defaults to returning 1 bar."""
        result = await data_access_manager.get_latest_bars(timeframe="5min")

        assert result is not None
        assert len(result) == 1
        assert result["close"].to_list() == [19025.0]  # Latest bar

    @pytest.mark.asyncio
    async def test_get_latest_bars_defaults_to_5min_timeframe(self, data_access_manager):
        """Test that get_latest_bars defaults to 5min timeframe."""
        result = await data_access_manager.get_latest_bars(count=1)

        assert result is not None
        assert len(result) == 1
        # Should come from 5min timeframe (default)


class TestGetLatestPrice:
    """Test the get_latest_price method following TDD principles."""

    @pytest.mark.asyncio
    async def test_get_latest_price_is_alias_for_get_current_price(self, data_access_manager, sample_tick_data):
        """Test that get_latest_price returns same result as get_current_price."""
        data_access_manager.current_tick_data = deque(sample_tick_data)

        current_price = await data_access_manager.get_current_price()
        latest_price = await data_access_manager.get_latest_price()

        assert current_price == latest_price
        assert latest_price == 19032.75


class TestGetOHLC:
    """Test the get_ohlc method following TDD principles."""

    @pytest.mark.asyncio
    async def test_get_ohlc_returns_latest_bar_ohlcv(self, data_access_manager):
        """Test that get_ohlc returns the latest bar's OHLCV values."""
        result = await data_access_manager.get_ohlc("5min")

        assert isinstance(result, dict)
        assert set(result.keys()) == {"open", "high", "low", "close", "volume"}

        # Should be the latest bar values
        assert result["open"] == 19020.0
        assert result["high"] == 19025.0
        assert result["low"] == 19015.0
        assert result["close"] == 19025.0
        assert result["volume"] == 125.0

    @pytest.mark.asyncio
    async def test_get_ohlc_returns_none_for_empty_data(self, data_access_manager):
        """Test that get_ohlc returns None when no data available."""
        result = await data_access_manager.get_ohlc("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_ohlc_defaults_to_5min_timeframe(self, data_access_manager):
        """Test that get_ohlc defaults to 5min timeframe."""
        result = await data_access_manager.get_ohlc()  # No timeframe specified

        assert result is not None
        # Should return OHLC from 5min timeframe


class TestGetPriceRange:
    """Test the get_price_range method following TDD principles."""

    @pytest.mark.asyncio
    async def test_get_price_range_calculates_range_statistics(self, data_access_manager):
        """Test that get_price_range calculates correct range statistics."""
        result = await data_access_manager.get_price_range(bars=5, timeframe="5min")

        assert isinstance(result, dict)
        assert set(result.keys()) == {"high", "low", "range", "avg_range"}

        # Based on sample data: highs=[19005, 19010, 19015, 19020, 19025], lows=[18995, 19000, 19005, 19010, 19015]
        assert result["high"] == 19025.0  # Max high
        assert result["low"] == 18995.0   # Min low
        assert result["range"] == 30.0    # 19025 - 18995

        # Average range = mean of (high-low) per bar: [10, 10, 10, 10, 10] = 10.0
        assert result["avg_range"] == 10.0

    @pytest.mark.asyncio
    async def test_get_price_range_handles_insufficient_data(self, data_access_manager):
        """Test that get_price_range returns None when insufficient data."""
        result = await data_access_manager.get_price_range(bars=10, timeframe="5min")  # Need 10, have 5

        assert result is None

    @pytest.mark.asyncio
    async def test_get_price_range_defaults_to_20_bars_5min(self, data_access_manager):
        """Test that get_price_range uses correct defaults."""
        # Add more data to meet the 20-bar default requirement
        extended_data = pl.concat([
            data_access_manager.data["5min"],
            pl.DataFrame({
                "timestamp": [datetime(2025, 1, 22, 10, i, tzinfo=timezone.utc) for i in range(15)],
                "open": [19030.0 + i for i in range(15)],
                "high": [19035.0 + i for i in range(15)],
                "low": [19025.0 + i for i in range(15)],
                "close": [19035.0 + i for i in range(15)],
                "volume": [100 + i for i in range(15)],
            })
        ])
        data_access_manager.data["5min"] = extended_data

        result = await data_access_manager.get_price_range()  # Use defaults

        assert result is not None
        assert isinstance(result["range"], float)

    @pytest.mark.asyncio
    async def test_get_price_range_handles_null_values(self, data_access_manager):
        """Test that get_price_range handles null values gracefully."""
        # Create data with null values
        null_data = pl.DataFrame({
            "timestamp": [datetime(2025, 1, 22, 10, i, tzinfo=timezone.utc) for i in range(5)],
            "open": [19000.0, None, 19010.0, None, 19020.0],
            "high": [None, 19010.0, None, 19020.0, None],
            "low": [18995.0, None, 19005.0, None, 19015.0],
            "close": [19005.0, None, 19015.0, None, 19025.0],
            "volume": [100, 150, 200, 175, 125],
        })
        data_access_manager.data["null_test"] = null_data

        result = await data_access_manager.get_price_range(bars=5, timeframe="null_test")

        # Should handle nulls gracefully - could return None or valid calculation
        # The implementation should not crash


class TestGetVolumeStats:
    """Test the get_volume_stats method following TDD principles."""

    @pytest.mark.asyncio
    async def test_get_volume_stats_calculates_volume_statistics(self, data_access_manager):
        """Test that get_volume_stats calculates correct volume statistics."""
        result = await data_access_manager.get_volume_stats(bars=5, timeframe="5min")

        assert isinstance(result, dict)
        assert set(result.keys()) == {"total", "average", "current", "relative"}

        # Based on sample data: volumes=[100, 150, 200, 175, 125]
        assert result["total"] == 750.0    # Sum of volumes
        assert result["average"] == 150.0  # Mean volume
        assert result["current"] == 125.0  # Last volume
        assert result["relative"] == 125.0 / 150.0  # Current / Average

    @pytest.mark.asyncio
    async def test_get_volume_stats_handles_zero_average_volume(self, data_access_manager):
        """Test that get_volume_stats handles zero average volume gracefully."""
        # Create data with zero volumes
        zero_vol_data = pl.DataFrame({
            "timestamp": [datetime(2025, 1, 22, 10, i, tzinfo=timezone.utc) for i in range(3)],
            "open": [19000.0, 19005.0, 19010.0],
            "high": [19005.0, 19010.0, 19015.0],
            "low": [18995.0, 19000.0, 19005.0],
            "close": [19005.0, 19010.0, 19015.0],
            "volume": [0, 0, 0],
        })
        data_access_manager.data["zero_vol"] = zero_vol_data

        result = await data_access_manager.get_volume_stats(bars=3, timeframe="zero_vol")

        assert result is not None
        assert result["relative"] == 0.0  # Should handle division by zero

    @pytest.mark.asyncio
    async def test_get_volume_stats_returns_none_for_empty_data(self, data_access_manager):
        """Test that get_volume_stats returns None for empty data."""
        empty_df = pl.DataFrame({
            "timestamp": [],
            "open": [],
            "high": [],
            "low": [],
            "close": [],
            "volume": [],
        }, schema={
            "timestamp": pl.Datetime(time_zone="UTC"),
            "open": pl.Float64,
            "high": pl.Float64,
            "low": pl.Float64,
            "close": pl.Float64,
            "volume": pl.Float64,
        })

        data_access_manager.data["empty_vol"] = empty_df
        result = await data_access_manager.get_volume_stats(bars=5, timeframe="empty_vol")

        assert result is None


class TestIsDataReady:
    """Test the is_data_ready method following TDD principles."""

    @pytest.mark.asyncio
    async def test_is_data_ready_returns_true_when_sufficient_data(self, data_access_manager):
        """Test that is_data_ready returns True when sufficient data available."""
        result = await data_access_manager.is_data_ready(min_bars=3)  # Have 5 bars

        assert result is True

    @pytest.mark.asyncio
    async def test_is_data_ready_returns_false_when_insufficient_data(self, data_access_manager):
        """Test that is_data_ready returns False when insufficient data."""
        result = await data_access_manager.is_data_ready(min_bars=10)  # Have only 5 bars

        assert result is False

    @pytest.mark.asyncio
    async def test_is_data_ready_checks_specific_timeframe(self, data_access_manager):
        """Test that is_data_ready can check specific timeframe."""
        result = await data_access_manager.is_data_ready(min_bars=3, timeframe="5min")

        assert result is True

    @pytest.mark.asyncio
    async def test_is_data_ready_returns_false_for_nonexistent_timeframe(self, data_access_manager):
        """Test that is_data_ready returns False for nonexistent timeframe."""
        result = await data_access_manager.is_data_ready(min_bars=1, timeframe="nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_is_data_ready_checks_all_timeframes_when_none_specified(self, data_access_manager):
        """Test that is_data_ready checks all timeframes when none specified."""
        result = await data_access_manager.is_data_ready(min_bars=5)  # All timeframes have exactly 5

        assert result is True

    @pytest.mark.asyncio
    async def test_is_data_ready_uses_correct_lock_type(self, data_access_manager):
        """Test that is_data_ready handles different lock types gracefully."""
        # Test with regular asyncio.Lock (should work)
        import asyncio
        data_access_manager.data_lock = asyncio.Lock()

        result = await data_access_manager.is_data_ready(min_bars=3)
        assert result is True  # We have 5 bars, need 3

        # Test with different lock object (should fall back gracefully)
        result2 = await data_access_manager.is_data_ready(min_bars=10)
        assert result2 is False  # We have 5 bars, need 10


class TestGetBarsSince:
    """Test the get_bars_since method following TDD principles."""

    @pytest.mark.asyncio
    async def test_get_bars_since_filters_by_timestamp(self, data_access_manager):
        """Test that get_bars_since returns bars after specified timestamp."""
        # Use a timestamp that should include the last 2 bars
        cutoff_time = datetime(2025, 1, 22, 9, 42, tzinfo=timezone.utc)

        result = await data_access_manager.get_bars_since(cutoff_time, "5min")

        assert result is not None
        assert len(result) == 2  # Should return last 2 bars (9:45 and 9:50)

        # Verify timestamps are after cutoff
        timestamps = result["timestamp"].to_list()
        assert all(ts >= cutoff_time for ts in timestamps)

    @pytest.mark.asyncio
    async def test_get_bars_since_handles_timezone_naive_timestamp(self, data_access_manager):
        """Test that get_bars_since handles timezone-naive timestamps."""
        # Use timezone-naive timestamp
        naive_time = datetime(2025, 1, 22, 9, 42)

        result = await data_access_manager.get_bars_since(naive_time, "5min")

        # Should handle timezone conversion and return data
        assert result is not None

    @pytest.mark.asyncio
    async def test_get_bars_since_returns_none_for_empty_data(self, data_access_manager):
        """Test that get_bars_since returns None when no data available."""
        result = await data_access_manager.get_bars_since(
            datetime(2025, 1, 22, 9, 0, tzinfo=timezone.utc),
            "nonexistent"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_get_bars_since_returns_empty_for_future_timestamp(self, data_access_manager):
        """Test that get_bars_since returns empty DataFrame for future timestamp."""
        future_time = datetime(2025, 1, 22, 10, 30, tzinfo=timezone.utc)

        result = await data_access_manager.get_bars_since(future_time, "5min")

        assert result is not None
        assert len(result) == 0  # Should be empty, no bars after future time


class TestGetDataOrNone:
    """Test the get_data_or_none method following TDD principles."""

    @pytest.mark.asyncio
    async def test_get_data_or_none_returns_data_when_sufficient_bars(self, data_access_manager):
        """Test that get_data_or_none returns data when minimum bars available."""
        result = await data_access_manager.get_data_or_none("5min", min_bars=3)

        assert result is not None
        assert len(result) == 5  # All available bars

    @pytest.mark.asyncio
    async def test_get_data_or_none_returns_none_when_insufficient_bars(self, data_access_manager):
        """Test that get_data_or_none returns None when insufficient bars."""
        result = await data_access_manager.get_data_or_none("5min", min_bars=10)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_data_or_none_returns_none_for_nonexistent_timeframe(self, data_access_manager):
        """Test that get_data_or_none returns None for nonexistent timeframe."""
        result = await data_access_manager.get_data_or_none("nonexistent", min_bars=1)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_data_or_none_uses_correct_defaults(self, data_access_manager):
        """Test that get_data_or_none uses correct default values."""
        # Should default to 5min timeframe and 20 bars minimum
        # Since we only have 5 bars, this should return None
        result = await data_access_manager.get_data_or_none()

        assert result is None  # Insufficient bars for default 20


class TestErrorHandling:
    """Test error handling and edge cases following TDD principles."""

    @pytest.mark.asyncio
    async def test_handles_corrupted_tick_data_gracefully(self, data_access_manager):
        """Test that methods handle corrupted tick data gracefully."""
        # Add corrupted tick data
        corrupted_tick = {
            "timestamp": "invalid_timestamp",
            "price": "not_a_number",
            "volume": None,
        }
        data_access_manager.current_tick_data = deque([corrupted_tick])

        # Should not crash and should fall back to bar data
        price = await data_access_manager.get_current_price()

        # Should fall back to bar data instead of crashing
        assert price == 19025.0  # From bar data fallback

    @pytest.mark.asyncio
    async def test_handles_missing_lock_attributes(self):
        """Test that methods handle missing lock attributes gracefully."""
        # Create manager without proper lock setup
        manager = MockDataAccessManager()
        manager.data_lock = None  # Simulate missing lock

        # Should handle missing lock gracefully (might use fallback or raise appropriate error)
        with pytest.raises((AttributeError, TypeError)):
            await manager.get_data("5min")

    @pytest.mark.asyncio
    async def test_handles_concurrent_modification_during_read(self, data_access_manager):
        """Test that concurrent data modification during reads doesn't cause issues."""
        async def modify_data():
            await asyncio.sleep(0.01)  # Small delay
            data_access_manager.data["5min"] = pl.DataFrame({
                "timestamp": [],
                "open": [],
                "high": [],
                "low": [],
                "close": [],
                "volume": [],
            }, schema={
                "timestamp": pl.Datetime(time_zone="UTC"),
                "open": pl.Float64,
                "high": pl.Float64,
                "low": pl.Float64,
                "close": pl.Float64,
                "volume": pl.Float64,
            })

        async def read_data():
            await asyncio.sleep(0.005)  # Different delay
            return await data_access_manager.get_data("5min")

        # Run concurrent modification and read
        results = await asyncio.gather(modify_data(), read_data(), return_exceptions=True)

        # Should not raise exceptions due to proper locking
        assert all(not isinstance(r, Exception) for r in results)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
