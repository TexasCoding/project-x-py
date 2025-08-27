"""
Comprehensive test suite for orderbook profile module.

Tests the VolumeProfile class which provides volume profile analysis,
support/resistance detection, and spread analytics for market structure
analysis.

Author: @TexasCoding
Date: 2025-01-27
"""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import polars as pl
import pytest

from project_x_py.orderbook.profile import VolumeProfile
from project_x_py.orderbook.base import OrderBookBase


@pytest.fixture
def mock_orderbook_base():
    """Create a mock OrderBookBase with test data for profile analysis."""
    ob = MagicMock(spec=OrderBookBase)
    ob.timezone = UTC
    ob.orderbook_lock = asyncio.Lock()
    ob.instrument = "MNQ"

    # Set up recent trades for volume profile analysis
    current_time = datetime.now(UTC)
    ob.recent_trades = pl.DataFrame({
        "price": [21000.0, 21000.5, 21001.0, 20999.5, 21000.0, 21001.5, 20999.0, 21000.5, 21001.0, 21000.0],
        "volume": [10, 15, 20, 12, 18, 8, 25, 14, 16, 22],
        "timestamp": [current_time - timedelta(minutes=i) for i in range(10)],
        "side": ["buy", "sell"] * 5,
        "spread_at_trade": [1.0] * 10,
        "mid_price_at_trade": [21000.5] * 10,
        "best_bid_at_trade": [21000.0] * 10,
        "best_ask_at_trade": [21001.0] * 10,
        "order_type": ["market"] * 10,
    })

    # Set up orderbook data for support/resistance analysis
    ob.orderbook_bids = pl.DataFrame({
        "price": [21000.0, 20999.0, 20998.0, 20997.0, 20996.0],
        "volume": [50, 40, 30, 20, 15],
        "timestamp": [current_time] * 5,
    })

    ob.orderbook_asks = pl.DataFrame({
        "price": [21001.0, 21002.0, 21003.0, 21004.0, 21005.0],
        "volume": [45, 35, 25, 18, 12],
        "timestamp": [current_time] * 5,
    })

    # Set up spread history for spread analysis
    ob.spread_history = [
        {"timestamp": current_time - timedelta(seconds=i), "spread": 1.0 + (i * 0.1)}
        for i in range(20)
    ]

    # Mock best bid/ask history (should be list of dicts with timestamp and price)
    ob.best_bid_history = [
        {"timestamp": current_time - timedelta(minutes=i), "price": 21000.0 - (i * 0.25)}
        for i in range(10)
    ]
    ob.best_ask_history = [
        {"timestamp": current_time - timedelta(minutes=i), "price": 21001.0 + (i * 0.25)}
        for i in range(10)
    ]

    # Mock support/resistance attributes that are set by the methods
    ob.support_levels = []
    ob.resistance_levels = []

    return ob


@pytest.fixture
def volume_profile(mock_orderbook_base):
    """Create a VolumeProfile instance for testing."""
    return VolumeProfile(mock_orderbook_base)


class TestVolumeProfileInitialization:
    """Test VolumeProfile initialization."""

    def test_initialization(self, volume_profile, mock_orderbook_base):
        """Test that VolumeProfile initializes correctly."""
        assert volume_profile.orderbook == mock_orderbook_base
        assert hasattr(volume_profile, "logger")


class TestVolumeProfileAnalysis:
    """Test volume profile analysis."""

    @pytest.mark.asyncio
    async def test_get_volume_profile_basic(self, volume_profile):
        """Test basic volume profile analysis."""
        result = await volume_profile.get_volume_profile(
            time_window_minutes=60,
            price_bins=10
        )

        assert isinstance(result, dict)
        assert "price_bins" in result
        assert "volumes" in result
        assert "poc" in result  # Point of Control
        assert "value_area_high" in result
        assert "value_area_low" in result
        assert "total_volume" in result
        assert "time_window_minutes" in result

        # Check data types
        assert isinstance(result["price_bins"], list)
        assert isinstance(result["volumes"], list)
        assert isinstance(result["total_volume"], int)
        assert result["time_window_minutes"] == 60

    @pytest.mark.asyncio
    async def test_get_volume_profile_different_bins(self, volume_profile):
        """Test volume profile with different bin counts."""
        result_10_bins = await volume_profile.get_volume_profile(price_bins=10)
        result_5_bins = await volume_profile.get_volume_profile(price_bins=5)

        # Different bin counts should produce different granularity
        assert len(result_10_bins["price_bins"]) >= len(result_5_bins["price_bins"])
        assert len(result_10_bins["volumes"]) >= len(result_5_bins["volumes"])

    @pytest.mark.asyncio
    async def test_get_volume_profile_empty_trades(self, volume_profile, mock_orderbook_base):
        """Test volume profile with no trade data."""
        mock_orderbook_base.recent_trades = pl.DataFrame({
            "price": [], "volume": [], "timestamp": [], "side": [],
            "spread_at_trade": [], "mid_price_at_trade": [],
            "best_bid_at_trade": [], "best_ask_at_trade": [],
            "order_type": [],
        })

        result = await volume_profile.get_volume_profile()

        assert result["price_bins"] == []
        assert result["volumes"] == []
        assert result["poc"] is None
        assert result["value_area_high"] is None
        assert result["value_area_low"] is None
        assert result["total_volume"] == 0

    @pytest.mark.asyncio
    async def test_get_volume_profile_single_price(self, volume_profile, mock_orderbook_base):
        """Test volume profile when all trades are at the same price."""
        current_time = datetime.now(UTC)
        mock_orderbook_base.recent_trades = pl.DataFrame({
            "price": [21000.0] * 5,
            "volume": [10, 20, 15, 25, 30],
            "timestamp": [current_time - timedelta(minutes=i) for i in range(5)],
            "side": ["buy", "sell"] * 2 + ["buy"],
            "spread_at_trade": [1.0] * 5,
            "mid_price_at_trade": [21000.5] * 5,
            "best_bid_at_trade": [21000.0] * 5,
            "best_ask_at_trade": [21001.0] * 5,
            "order_type": ["market"] * 5,
        })

        result = await volume_profile.get_volume_profile()

        # When all prices are the same, POC and value area should be that price
        assert result["poc"] == 21000.0
        assert result["value_area_high"] == 21000.0
        assert result["value_area_low"] == 21000.0
        assert result["total_volume"] == 100  # Sum of all volumes


class TestSupportResistanceLevels:
    """Test support and resistance level detection."""

    @pytest.mark.asyncio
    async def test_get_support_resistance_levels_basic(self, volume_profile):
        """Test basic support/resistance level detection."""
        result = await volume_profile.get_support_resistance_levels(
            lookback_minutes=120,
            min_touches=2,
            price_tolerance=0.25
        )

        assert isinstance(result, dict)
        assert "support_levels" in result
        assert "resistance_levels" in result
        assert "strongest_support" in result
        assert "strongest_resistance" in result
        assert "current_price" in result

        # Check data types
        assert isinstance(result["support_levels"], list)
        assert isinstance(result["resistance_levels"], list)

    @pytest.mark.asyncio
    async def test_get_support_resistance_levels_empty_data(self, volume_profile, mock_orderbook_base):
        """Test support/resistance detection with no data."""
        mock_orderbook_base.recent_trades = pl.DataFrame({
            "price": [], "volume": [], "timestamp": [], "side": [],
            "spread_at_trade": [], "mid_price_at_trade": [],
            "best_bid_at_trade": [], "best_ask_at_trade": [],
            "order_type": [],
        })
        mock_orderbook_base.orderbook_bids = pl.DataFrame({
            "price": [], "volume": [], "timestamp": []
        })
        mock_orderbook_base.orderbook_asks = pl.DataFrame({
            "price": [], "volume": [], "timestamp": []
        })

        result = await volume_profile.get_support_resistance_levels()

        assert result["support_levels"] == []
        assert result["resistance_levels"] == []
        assert result["strongest_support"] is None
        assert result["strongest_resistance"] is None

    @pytest.mark.asyncio
    async def test_get_support_resistance_levels_different_params(self, volume_profile):
        """Test support/resistance with different parameter combinations."""
        strict_result = await volume_profile.get_support_resistance_levels(
            min_touches=5,
            price_tolerance=0.1
        )

        lenient_result = await volume_profile.get_support_resistance_levels(
            min_touches=2,
            price_tolerance=0.5
        )

        # Lenient parameters should find more levels than strict ones
        assert len(lenient_result["support_levels"]) >= len(strict_result["support_levels"])
        assert len(lenient_result["resistance_levels"]) >= len(strict_result["resistance_levels"])


class TestSpreadAnalysis:
    """Test spread analysis functionality."""

    @pytest.mark.asyncio
    async def test_get_spread_analysis_basic(self, volume_profile):
        """Test basic spread analysis."""
        result = await volume_profile.get_spread_analysis(window_minutes=30)

        assert isinstance(result, dict)
        # Check for LiquidityAnalysisResponse fields
        assert "bid_liquidity" in result
        assert "ask_liquidity" in result
        assert "total_liquidity" in result
        assert "avg_spread" in result
        assert "spread_volatility" in result
        assert "liquidity_score" in result
        assert "market_depth_score" in result
        assert "resilience_score" in result
        assert "tightness_score" in result
        assert "immediacy_score" in result
        assert "depth_imbalance" in result
        assert "effective_spread" in result
        assert "realized_spread" in result
        assert "price_impact" in result
        assert "timestamp" in result

        # Check data types
        assert isinstance(result["bid_liquidity"], float)
        assert isinstance(result["ask_liquidity"], float)
        assert isinstance(result["total_liquidity"], float)
        assert isinstance(result["avg_spread"], float)
        assert isinstance(result["spread_volatility"], float)
        assert isinstance(result["liquidity_score"], float)

    @pytest.mark.asyncio
    async def test_get_spread_analysis_no_history(self, volume_profile, mock_orderbook_base):
        """Test spread analysis with no spread history."""
        mock_orderbook_base.spread_history = []

        result = await volume_profile.get_spread_analysis()

        # Should return zero values when no data
        assert result["bid_liquidity"] == 0.0
        assert result["ask_liquidity"] == 0.0
        assert result["total_liquidity"] == 0.0
        assert result["avg_spread"] == 0.0
        assert result["spread_volatility"] == 0.0
        assert result["liquidity_score"] == 0.0

    @pytest.mark.asyncio
    async def test_get_spread_analysis_different_windows(self, volume_profile):
        """Test spread analysis with different time windows."""
        short_window = await volume_profile.get_spread_analysis(window_minutes=15)
        long_window = await volume_profile.get_spread_analysis(window_minutes=60)

        # Both should return valid results
        assert isinstance(short_window, dict)
        assert isinstance(long_window, dict)
        assert "avg_spread" in short_window
        assert "avg_spread" in long_window


class TestErrorHandling:
    """Test error handling in profile analysis."""

    @pytest.mark.asyncio
    async def test_handle_exceptions_gracefully(self, volume_profile, mock_orderbook_base):
        """Test that all methods handle exceptions gracefully."""
        # Create invalid data that might cause exceptions
        mock_orderbook_base.recent_trades = None
        mock_orderbook_base.orderbook_bids = None
        mock_orderbook_base.orderbook_asks = None
        mock_orderbook_base.spread_history = None

        # All methods should handle errors without raising
        vp_result = await volume_profile.get_volume_profile()
        sr_result = await volume_profile.get_support_resistance_levels()
        spread_result = await volume_profile.get_spread_analysis()

        # Check that results contain error information or safe defaults
        assert vp_result is not None
        assert sr_result is not None
        assert spread_result is not None


class TestThreadSafety:
    """Test thread safety of profile operations."""

    @pytest.mark.asyncio
    async def test_concurrent_profile_operations(self, volume_profile):
        """Test that concurrent profile operations are safe."""
        tasks = [
            volume_profile.get_volume_profile(),
            volume_profile.get_support_resistance_levels(),
            volume_profile.get_spread_analysis(),
            volume_profile.get_volume_profile(price_bins=5),
            volume_profile.get_support_resistance_levels(min_touches=1),
        ]

        # All should complete without deadlock
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Check that results were returned (even if analysis found nothing)
        for result in results:
            assert result is not None
            assert not isinstance(result, Exception)


class TestDataValidation:
    """Test data validation and edge cases."""

    @pytest.mark.asyncio
    async def test_volume_profile_with_negative_volumes(self, volume_profile, mock_orderbook_base):
        """Test volume profile handles negative volumes appropriately."""
        current_time = datetime.now(UTC)
        mock_orderbook_base.recent_trades = pl.DataFrame({
            "price": [21000.0, 21001.0, 21002.0],
            "volume": [10, -5, 20],  # Negative volume (should be handled)
            "timestamp": [current_time - timedelta(minutes=i) for i in range(3)],
            "side": ["buy", "sell", "buy"],
            "spread_at_trade": [1.0] * 3,
            "mid_price_at_trade": [21000.5] * 3,
            "best_bid_at_trade": [21000.0] * 3,
            "best_ask_at_trade": [21001.0] * 3,
            "order_type": ["market"] * 3,
        })

        result = await volume_profile.get_volume_profile()

        # Should handle negative volumes gracefully
        assert result is not None
        assert isinstance(result["total_volume"], int)

    @pytest.mark.asyncio
    async def test_support_resistance_with_extreme_prices(self, volume_profile, mock_orderbook_base):
        """Test support/resistance with extreme price values."""
        current_time = datetime.now(UTC)
        mock_orderbook_base.recent_trades = pl.DataFrame({
            "price": [1.0, 1000000.0, 50000.0],  # Extreme price range
            "volume": [10, 15, 20],
            "timestamp": [current_time - timedelta(minutes=i) for i in range(3)],
            "side": ["buy", "sell", "buy"],
            "spread_at_trade": [1.0] * 3,
            "mid_price_at_trade": [21000.5] * 3,
            "best_bid_at_trade": [21000.0] * 3,
            "best_ask_at_trade": [21001.0] * 3,
            "order_type": ["market"] * 3,
        })

        result = await volume_profile.get_support_resistance_levels()

        # Should handle extreme prices without crashing
        assert result is not None
        assert isinstance(result["support_levels"], list)
        assert isinstance(result["resistance_levels"], list)


# Run tests with coverage reporting
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=src/project_x_py/orderbook/profile", "--cov-report=term-missing"])
