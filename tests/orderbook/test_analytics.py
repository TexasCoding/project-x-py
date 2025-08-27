"""
Comprehensive test suite for orderbook analytics module.

Tests the MarketAnalytics class which provides advanced quantitative analytics
for orderbook data, including market imbalance, liquidity analysis, trade flow,
and statistical summaries.

Author: @TexasCoding
Date: 2025-01-27
"""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import polars as pl
import pytest

from project_x_py.orderbook.analytics import MarketAnalytics
from project_x_py.orderbook.base import OrderBookBase


@pytest.fixture
def mock_orderbook_base():
    """Create a mock OrderBookBase with test data."""
    ob = MagicMock(spec=OrderBookBase)
    ob.timezone = UTC
    ob.orderbook_lock = asyncio.Lock()
    ob.instrument = "MNQ"

    # Mock the _get_best_bid_ask_unlocked method
    ob._get_best_bid_ask_unlocked = MagicMock(return_value={
        "bid": 21000.0,
        "ask": 21001.0,
        "spread": 1.0,
        "mid_price": 21000.5,
        "timestamp": datetime.now(UTC),
    })

    # Set up test orderbook data
    ob.orderbook_bids = pl.DataFrame({
        "price": [21000.0, 20999.0, 20998.0, 20997.0, 20996.0],
        "volume": [10, 20, 15, 25, 30],
        "timestamp": [datetime.now(UTC)] * 5,
    })

    ob.orderbook_asks = pl.DataFrame({
        "price": [21001.0, 21002.0, 21003.0, 21004.0, 21005.0],
        "volume": [15, 25, 20, 30, 10],
        "timestamp": [datetime.now(UTC)] * 5,
    })

    # Set up recent trades
    ob.recent_trades = pl.DataFrame({
        "price": [21000.5, 21000.0, 21001.0, 20999.5, 21000.5],
        "volume": [5, 10, 3, 7, 8],
        "timestamp": [
            datetime.now(UTC) - timedelta(minutes=i) for i in range(5)
        ],
        "side": ["buy", "sell", "buy", "sell", "buy"],
        "spread_at_trade": [1.0, 1.0, 1.0, 1.0, 1.0],
        "mid_price_at_trade": [21000.5] * 5,
        "best_bid_at_trade": [21000.0] * 5,
        "best_ask_at_trade": [21001.0] * 5,
        "order_type": ["market"] * 5,
    })

    # Set up best price history
    ob.best_bid_history = [
        {"price": 20999.0 + i, "timestamp": datetime.now(UTC) - timedelta(minutes=10-i)}
        for i in range(10)
    ]

    ob.best_ask_history = [
        {"price": 21001.0 + i, "timestamp": datetime.now(UTC) - timedelta(minutes=10-i)}
        for i in range(10)
    ]

    # Set up cumulative delta history
    from collections import deque
    ob.cumulative_delta_history = deque([
        {"delta": 5, "timestamp": datetime.now(UTC) - timedelta(minutes=5)},
        {"delta": -3, "timestamp": datetime.now(UTC) - timedelta(minutes=4)},
        {"delta": 8, "timestamp": datetime.now(UTC) - timedelta(minutes=3)},
        {"delta": -2, "timestamp": datetime.now(UTC) - timedelta(minutes=2)},
        {"delta": 10, "timestamp": datetime.now(UTC) - timedelta(minutes=1)},
    ], maxlen=1000)

    ob.spread_history = [
        {"spread": 1.0, "timestamp": datetime.now(UTC) - timedelta(minutes=i)}
        for i in range(10, 0, -1)
    ]

    # Additional attributes needed by get_trade_flow_summary
    ob.vwap_numerator = 2100050.0  # Example: sum(price * volume)
    ob.vwap_denominator = 100.0     # Example: sum(volume)
    ob.trade_flow_stats = {
        "aggressive_buy_volume": 16,
        "aggressive_sell_volume": 17,
        "passive_buy_volume": 5,
        "passive_sell_volume": 7,
        "market_maker_trades": 2,
    }
    ob.cumulative_delta = -1
    ob.session_start_time = datetime.now(UTC) - timedelta(hours=1)

    # Additional attributes needed by get_statistics
    ob.level2_update_count = 150
    ob.last_orderbook_update = datetime.now(UTC)
    ob.order_type_stats = {
        "market": 3,
        "limit": 2,
    }

    # Mock methods needed
    ob._get_orderbook_bids_unlocked = MagicMock(side_effect=lambda levels: ob.orderbook_bids.head(levels) if levels else ob.orderbook_bids)
    ob._get_orderbook_asks_unlocked = MagicMock(side_effect=lambda levels: ob.orderbook_asks.head(levels) if levels else ob.orderbook_asks)

    return ob


@pytest.fixture
def market_analytics(mock_orderbook_base):
    """Create a MarketAnalytics instance for testing."""
    return MarketAnalytics(mock_orderbook_base)


class TestMarketAnalyticsInitialization:
    """Test MarketAnalytics initialization."""

    def test_initialization(self, market_analytics, mock_orderbook_base):
        """Test that MarketAnalytics initializes correctly."""
        assert market_analytics.orderbook == mock_orderbook_base
        assert hasattr(market_analytics, "logger")


class TestMarketImbalance:
    """Test market imbalance analysis."""

    @pytest.mark.asyncio
    async def test_get_market_imbalance_basic(self, market_analytics):
        """Test basic market imbalance calculation."""
        result = await market_analytics.get_market_imbalance(levels=3)

        # Check LiquidityAnalysisResponse fields
        assert "bid_liquidity" in result
        assert "ask_liquidity" in result
        assert "total_liquidity" in result
        assert "depth_imbalance" in result
        assert "liquidity_score" in result
        assert "timestamp" in result

        # With our test data: bids[0:3] = 10+20+15=45, asks[0:3] = 15+25+20=60
        assert result["bid_liquidity"] == 45.0
        assert result["ask_liquidity"] == 60.0
        assert result["total_liquidity"] == 105.0
        assert result["depth_imbalance"] == pytest.approx((45 - 60) / 105)

    @pytest.mark.asyncio
    async def test_get_market_imbalance_all_levels(self, market_analytics):
        """Test market imbalance with all available levels."""
        result = await market_analytics.get_market_imbalance(levels=None)

        # Should use all 5 levels
        assert result["bid_liquidity"] == 100.0  # 10+20+15+25+30
        assert result["ask_liquidity"] == 100.0  # 15+25+20+30+10
        assert result["depth_imbalance"] == 0.0  # Balanced

    @pytest.mark.asyncio
    async def test_get_market_imbalance_analysis_categories(self, market_analytics, mock_orderbook_base):
        """Test different imbalance categories through depth_imbalance field."""
        # Strong buy pressure
        mock_orderbook_base.orderbook_bids = pl.DataFrame({
            "price": [21000.0, 20999.0],
            "volume": [100, 100],
            "timestamp": [datetime.now(UTC)] * 2,
        })
        mock_orderbook_base.orderbook_asks = pl.DataFrame({
            "price": [21001.0, 21002.0],
            "volume": [10, 10],
            "timestamp": [datetime.now(UTC)] * 2,
        })

        result = await market_analytics.get_market_imbalance()
        # depth_imbalance = (200 - 20) / 220 = 0.818
        assert result["depth_imbalance"] > 0.5  # Strong positive imbalance

        # Strong sell pressure
        mock_orderbook_base.orderbook_bids = pl.DataFrame({
            "price": [21000.0, 20999.0],
            "volume": [10, 10],
            "timestamp": [datetime.now(UTC)] * 2,
        })
        mock_orderbook_base.orderbook_asks = pl.DataFrame({
            "price": [21001.0, 21002.0],
            "volume": [100, 100],
            "timestamp": [datetime.now(UTC)] * 2,
        })

        result = await market_analytics.get_market_imbalance()
        # depth_imbalance = (20 - 200) / 220 = -0.818
        assert result["depth_imbalance"] < -0.5  # Strong negative imbalance

    @pytest.mark.asyncio
    async def test_get_market_imbalance_empty_orderbook(self, market_analytics, mock_orderbook_base):
        """Test market imbalance with empty orderbook."""
        mock_orderbook_base.orderbook_bids = pl.DataFrame({
            "price": [], "volume": [], "timestamp": []
        })
        mock_orderbook_base.orderbook_asks = pl.DataFrame({
            "price": [], "volume": [], "timestamp": []
        })

        result = await market_analytics.get_market_imbalance()
        assert result["bid_liquidity"] == 0.0
        assert result["ask_liquidity"] == 0.0
        assert result["total_liquidity"] == 0.0
        assert result["depth_imbalance"] == 0.0


class TestOrderbookDepth:
    """Test orderbook depth analysis."""

    @pytest.mark.asyncio
    async def test_get_orderbook_depth_basic(self, market_analytics):
        """Test basic orderbook depth analysis."""
        result = await market_analytics.get_orderbook_depth(price_range=5.0)

        # Check MarketImpactResponse fields
        assert "estimated_fill_price" in result
        assert "price_impact_pct" in result
        assert "spread_cost" in result
        assert "market_impact_cost" in result
        assert "total_transaction_cost" in result
        assert "levels_consumed" in result
        assert "remaining_liquidity" in result
        assert "timestamp" in result

        # Basic checks
        assert result["estimated_fill_price"] > 0  # Should have a fill price
        assert result["spread_cost"] >= 0  # Should have non-negative spread cost

    @pytest.mark.asyncio
    async def test_get_orderbook_depth_large_range(self, market_analytics):
        """Test orderbook depth with large price range."""
        result = await market_analytics.get_orderbook_depth(price_range=100.0)

        # Should have valid result with large range
        assert result["estimated_fill_price"] > 0
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_get_orderbook_depth_empty(self, market_analytics, mock_orderbook_base):
        """Test depth analysis with empty orderbook."""
        # Return None for best prices when orderbook is empty
        mock_orderbook_base._get_best_bid_ask_unlocked = MagicMock(return_value={
            "bid": None,
            "ask": None,
            "spread": None,
            "mid_price": None,
            "timestamp": datetime.now(UTC),
        })

        result = await market_analytics.get_orderbook_depth(price_range=5.0)
        assert result["estimated_fill_price"] == 0.0
        assert result["levels_consumed"] == 0
        assert result["remaining_liquidity"] == 0.0


class TestCumulativeDelta:
    """Test cumulative delta analysis."""

    @pytest.mark.asyncio
    async def test_get_cumulative_delta_basic(self, market_analytics):
        """Test basic cumulative delta calculation."""
        result = await market_analytics.get_cumulative_delta(time_window_minutes=10)

        assert "cumulative_delta" in result
        assert "buy_volume" in result
        assert "sell_volume" in result
        assert "neutral_volume" in result
        assert "total_volume" in result
        assert "period_minutes" in result
        assert "trade_count" in result
        assert "delta_per_trade" in result

        # From test data: buy trades = 5+3+8=16, sell trades = 10+7=17
        assert result["buy_volume"] == 16
        assert result["sell_volume"] == 17
        assert result["cumulative_delta"] == -1  # buy - sell
        assert result["trade_count"] == 5
        assert result["period_minutes"] == 10

    @pytest.mark.asyncio
    async def test_get_cumulative_delta_time_filtered(self, market_analytics, mock_orderbook_base):
        """Test cumulative delta with time window filtering."""
        # Set up trades with specific timestamps
        now = datetime.now(UTC)
        mock_orderbook_base.recent_trades = pl.DataFrame({
            "price": [21000.0] * 6,
            "volume": [10] * 6,
            "timestamp": [
                now - timedelta(minutes=30),  # Outside window
                now - timedelta(minutes=5),   # Inside window
                now - timedelta(minutes=4),   # Inside window
                now - timedelta(minutes=3),   # Inside window
                now - timedelta(minutes=2),   # Inside window
                now - timedelta(minutes=1),   # Inside window
            ],
            "side": ["buy", "buy", "sell", "buy", "sell", "buy"],
            "spread_at_trade": [1.0] * 6,
            "mid_price_at_trade": [21000.5] * 6,
            "best_bid_at_trade": [21000.0] * 6,
            "best_ask_at_trade": [21001.0] * 6,
            "order_type": ["market"] * 6,
        })

        result = await market_analytics.get_cumulative_delta(time_window_minutes=10)

        # Should only include last 5 trades (not the one 30 minutes ago)
        assert result["trade_count"] == 5
        assert result["buy_volume"] == 30  # 3 buy trades
        assert result["sell_volume"] == 20  # 2 sell trades
        assert result["cumulative_delta"] == 10

    @pytest.mark.asyncio
    async def test_get_cumulative_delta_no_trades(self, market_analytics, mock_orderbook_base):
        """Test cumulative delta with no trades."""
        mock_orderbook_base.recent_trades = pl.DataFrame({
            "price": [], "volume": [], "timestamp": [], "side": [],
            "spread_at_trade": [], "mid_price_at_trade": [],
            "best_bid_at_trade": [], "best_ask_at_trade": [],
            "order_type": [],
        })

        result = await market_analytics.get_cumulative_delta()
        assert result["cumulative_delta"] == 0
        assert result["buy_volume"] == 0
        assert result["sell_volume"] == 0
        assert result["neutral_volume"] == 0
        # No trade_count field when recent_trades is empty


class TestLiquidityAnalysis:
    """Test liquidity analysis methods."""

    @pytest.mark.asyncio
    async def test_get_liquidity_levels(self, market_analytics):
        """Test identification of significant liquidity levels."""
        result = await market_analytics.get_liquidity_levels(
            min_volume=20,  # Only levels with volume >= 20
            levels=5
        )

        assert isinstance(result, dict)
        assert "significant_bid_levels" in result
        assert "significant_ask_levels" in result
        assert "total_bid_liquidity" in result
        assert "total_ask_liquidity" in result
        assert "liquidity_imbalance" in result
        assert "min_volume_threshold" in result

        # From test data: bid levels >= 20: 20999(20), 20997(25), 20996(30)
        assert len(result["significant_bid_levels"]) == 3
        assert result["total_bid_liquidity"] == 75  # 20+25+30

        # From test data: ask levels >= 20: 21002(25), 21003(20), 21004(30)
        assert len(result["significant_ask_levels"]) == 3
        assert result["total_ask_liquidity"] == 75  # 25+20+30

    @pytest.mark.asyncio
    async def test_get_liquidity_levels_high_threshold(self, market_analytics):
        """Test liquidity levels with high volume threshold."""
        result = await market_analytics.get_liquidity_levels(
            min_volume=1000  # Very high threshold
        )

        # No levels should meet this threshold
        assert len(result["significant_bid_levels"]) == 0
        assert len(result["significant_ask_levels"]) == 0
        assert result["total_bid_liquidity"] == 0
        assert result["total_ask_liquidity"] == 0


class TestTradeFlowSummary:
    """Test trade flow summary methods."""

    @pytest.mark.asyncio
    async def test_get_trade_flow_summary(self, market_analytics):
        """Test trade flow summary calculation."""
        result = await market_analytics.get_trade_flow_summary()

        assert isinstance(result, dict)
        assert "aggressive_buy_volume" in result
        assert "aggressive_sell_volume" in result
        assert "passive_buy_volume" in result
        assert "passive_sell_volume" in result
        assert "market_maker_trades" in result
        assert "cumulative_delta" in result
        assert "vwap" in result
        assert "session_start" in result
        assert "total_trades" in result
        assert "avg_trade_size" in result
        assert "max_trade_size" in result
        assert "min_trade_size" in result

        # Check values from mock data
        assert result["aggressive_buy_volume"] == 16
        assert result["aggressive_sell_volume"] == 17
        assert result["cumulative_delta"] == -1
        assert result["vwap"] == pytest.approx(21000.5)  # 2100050.0 / 100.0
        assert result["total_trades"] == 5  # From recent_trades


class TestStatisticalSummaries:
    """Test statistical summary methods."""

    @pytest.mark.asyncio
    async def test_get_statistics(self, market_analytics):
        """Test comprehensive orderbook statistics."""
        result = await market_analytics.get_statistics()

        assert isinstance(result, dict)
        assert "instrument" in result
        assert "level2_update_count" in result
        assert "last_update" in result
        assert "best_bid" in result
        assert "best_ask" in result
        assert "spread" in result
        assert "mid_price" in result
        assert "bid_depth" in result
        assert "ask_depth" in result
        assert "total_bid_size" in result
        assert "total_ask_size" in result
        assert "total_trades" in result
        assert "buy_trades" in result
        assert "sell_trades" in result
        assert "avg_trade_size" in result
        assert "vwap" in result
        assert "order_type_breakdown" in result

        # Check values
        assert result["instrument"] == "MNQ"
        assert result["level2_update_count"] == 150
        assert result["bid_depth"] == 5
        assert result["ask_depth"] == 5
        assert result["total_bid_size"] == 100
        assert result["total_ask_size"] == 100
        assert result["total_trades"] == 5


class TestErrorHandling:
    """Test error handling in analytics."""

    @pytest.mark.asyncio
    async def test_handle_empty_data_gracefully(self, market_analytics, mock_orderbook_base):
        """Test all methods handle empty data gracefully."""
        # Clear all data
        mock_orderbook_base.orderbook_bids = pl.DataFrame({
            "price": [], "volume": [], "timestamp": []
        })
        mock_orderbook_base.orderbook_asks = pl.DataFrame({
            "price": [], "volume": [], "timestamp": []
        })
        mock_orderbook_base.recent_trades = pl.DataFrame({
            "price": [], "volume": [], "timestamp": [], "side": [],
            "spread_at_trade": [], "mid_price_at_trade": [],
            "best_bid_at_trade": [], "best_ask_at_trade": [],
            "order_type": [],
        })
        mock_orderbook_base.spread_history = []
        mock_orderbook_base.cumulative_delta_history = []

        # All available methods should handle empty data without raising
        imbalance = await market_analytics.get_market_imbalance()
        assert imbalance is not None
        assert imbalance["depth_imbalance"] == 0.0

        depth = await market_analytics.get_orderbook_depth(price_range=5.0)
        assert depth is not None

        delta = await market_analytics.get_cumulative_delta()
        assert delta is not None
        assert delta["cumulative_delta"] == 0

        liquidity = await market_analytics.get_liquidity_levels()
        assert liquidity is not None

        flow = await market_analytics.get_trade_flow_summary()
        assert flow is not None

        stats = await market_analytics.get_statistics()
        assert stats is not None


class TestThreadSafety:
    """Test thread safety of analytics operations."""

    @pytest.mark.asyncio
    async def test_concurrent_analytics_operations(self, market_analytics):
        """Test that concurrent analytics operations are safe."""
        tasks = [
            market_analytics.get_market_imbalance(),
            market_analytics.get_orderbook_depth(price_range=5.0),
            market_analytics.get_cumulative_delta(),
            market_analytics.get_liquidity_levels(),
            market_analytics.get_trade_flow_summary(),
            market_analytics.get_statistics(),
        ]

        # All should complete without deadlock
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # No exceptions should occur
        for i, result in enumerate(results):
            assert not isinstance(result, Exception), f"Task {i} raised: {result}"


# Run tests with coverage reporting
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=src/project_x_py/orderbook/analytics", "--cov-report=term-missing"])
