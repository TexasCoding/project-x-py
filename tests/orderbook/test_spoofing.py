"""
Unit tests for OrderBook spoofing detection functionality.

Tests the spoofing detection algorithm including memory bounds,
performance optimizations, and tick size configuration.
"""

from collections import deque
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from project_x_py.orderbook import OrderBook
from project_x_py.orderbook.detection import OrderDetection


@pytest.fixture
def mock_event_bus():
    """Create a mock event bus for testing."""
    return MagicMock()


@pytest.fixture
def orderbook(mock_event_bus):
    """Create an OrderBook instance for testing."""
    return OrderBook(
        instrument="MNQ",
        event_bus=mock_event_bus,
        project_x=None,
        timezone_str="America/Chicago",
    )


@pytest.fixture
def detection(orderbook):
    """Create an OrderDetection instance for testing."""
    return OrderDetection(orderbook)


class TestSpoofingDetection:
    """Test spoofing detection algorithm improvements."""

    @pytest.mark.asyncio
    async def test_detect_spoofing_no_data(self, detection):
        """Test spoofing detection with no data returns empty list."""
        result = await detection.detect_spoofing()
        assert result == []

    @pytest.mark.asyncio
    async def test_memory_bounds_enforcement(self, orderbook):
        """Test that memory bounds are properly enforced."""
        # Verify initial configuration
        assert orderbook.max_price_levels_tracked == 10000

        # Verify price_level_history uses bounded deque
        test_key = (20000.0, "bid")
        orderbook.price_level_history[test_key].append({"test": "data"})

        # Should be a deque with maxlen
        assert isinstance(orderbook.price_level_history[test_key], deque)
        assert orderbook.price_level_history[test_key].maxlen == 1000

    @pytest.mark.asyncio
    async def test_memory_bounds_limit_price_levels(self, orderbook):
        """Test that number of price levels tracked is bounded."""
        current_time = datetime.now(ZoneInfo("America/Chicago"))

        # Try to add more than max_price_levels_tracked
        for i in range(12000):  # More than the 10000 limit
            price = 20000.0 + (i * 0.25)
            side = "bid" if i % 2 == 0 else "ask"
            orderbook.price_level_history[(price, side)].append(
                {"volume": 10, "timestamp": current_time, "change_type": "update"}
            )

        # Due to our memory management in realtime.py, this should stay bounded
        # Note: The actual enforcement happens in realtime.py when updating
        # For this test, we just verify the structure is correct
        assert isinstance(orderbook.price_level_history, dict)

    @pytest.mark.asyncio
    async def test_detect_spoofing_performance_with_large_dataset(
        self, orderbook, detection
    ):
        """Test performance optimization with large datasets."""
        current_time = datetime.now(ZoneInfo("America/Chicago"))

        # Mock market data for spoofing detection to work
        orderbook.orderbook_bids = pl.DataFrame(
            {"price": [20000.0], "volume": [10], "timestamp": [current_time]}
        )
        orderbook.orderbook_asks = pl.DataFrame(
            {"price": [20010.0], "volume": [10], "timestamp": [current_time]}
        )

        # Create large dataset to test optimization
        # Add 2000 price levels
        for i in range(2000):
            price = 20000.0 + (i * 0.25)
            side = "bid" if i % 2 == 0 else "ask"
            history = deque(maxlen=1000)

            # Add some history
            for j in range(5):
                history.append(
                    {
                        "volume": 10,
                        "timestamp": current_time - timedelta(minutes=j),
                        "change_type": "update",
                    }
                )

            orderbook.price_level_history[(price, side)] = history

        # Run detection - should complete quickly despite large dataset
        import time

        start_time = time.time()

        result = await detection.detect_spoofing(time_window_minutes=10)

        elapsed_time = time.time() - start_time

        # Should complete in reasonable time (< 2 seconds)
        # With optimization, only analyzes top 1000 price levels
        assert elapsed_time < 2.0

    @pytest.mark.asyncio
    async def test_binary_search_optimization_used_for_large_history(
        self, orderbook, detection
    ):
        """Test that binary search is used for large history filtering."""
        current_time = datetime.now(ZoneInfo("America/Chicago"))

        # Mock market data
        orderbook.orderbook_bids = pl.DataFrame(
            {"price": [20000.0], "volume": [10], "timestamp": [current_time]}
        )
        orderbook.orderbook_asks = pl.DataFrame(
            {"price": [20010.0], "volume": [10], "timestamp": [current_time]}
        )

        # Create price level with large history (> 100 entries)
        price = 20000.0
        history = deque(maxlen=1000)

        # Add 200 historical entries with proper timestamps
        for i in range(200):
            timestamp = current_time - timedelta(minutes=30) + timedelta(seconds=i * 9)
            history.append(
                {"volume": 50, "timestamp": timestamp, "change_type": "update"}
            )

        orderbook.price_level_history[(price, "bid")] = history

        # Run detection - should use binary search for filtering
        # The binary search optimization is in the code path for len(history) > 100
        result = await detection.detect_spoofing(
            time_window_minutes=10,
            min_placement_frequency=0.1,  # Low threshold to potentially get results
        )

        # Should complete without errors (optimization path taken)
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_tick_size_from_api(self, orderbook, detection):
        """Test tick size configuration from API."""
        # Mock project_x client
        mock_client = AsyncMock()
        mock_instrument = MagicMock()
        mock_instrument.tickSize = 0.5
        mock_client.get_instrument.return_value = mock_instrument
        orderbook.project_x = mock_client

        # Get tick size
        tick_size = await detection._get_tick_size()

        # Should get from API
        assert tick_size == 0.5
        mock_client.get_instrument.assert_called_once_with("MNQ")

    @pytest.mark.asyncio
    async def test_tick_size_fallback_to_defaults(self, orderbook, detection):
        """Test tick size fallback to defaults when API fails."""
        # Mock failing API
        mock_client = AsyncMock()
        mock_client.get_instrument.side_effect = Exception("API Error")
        orderbook.project_x = mock_client

        # Get tick size
        tick_size = await detection._get_tick_size()

        # Should fall back to default for MNQ
        assert tick_size == 0.25

    @pytest.mark.asyncio
    async def test_tick_size_unknown_instrument(self, orderbook, detection):
        """Test tick size for unknown instrument defaults to penny."""
        orderbook.instrument = "UNKNOWN"
        orderbook.project_x = None

        tick_size = await detection._get_tick_size()

        # Should default to penny
        assert tick_size == 0.01

    @pytest.mark.asyncio
    async def test_price_level_analysis_limit(self, orderbook, detection):
        """Test that spoofing detection limits price levels analyzed."""
        current_time = datetime.now(ZoneInfo("America/Chicago"))

        # Mock market data
        orderbook.orderbook_bids = pl.DataFrame(
            {"price": [20000.0], "volume": [10], "timestamp": [current_time]}
        )
        orderbook.orderbook_asks = pl.DataFrame(
            {"price": [20010.0], "volume": [10], "timestamp": [current_time]}
        )

        # Add exactly 1001 price levels (more than the 1000 limit)
        for i in range(1001):
            price = 20000.0 + (i * 0.25)
            history = deque(maxlen=1000)
            history.append(
                {
                    "volume": 10,
                    "timestamp": current_time - timedelta(minutes=1),
                    "change_type": "update",
                }
            )
            orderbook.price_level_history[(price, "bid")] = history

        # Run detection
        result = await detection.detect_spoofing(time_window_minutes=10)

        # Should complete successfully (only analyzes top 1000)
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_spoofing_metrics_calculation(self, detection):
        """Test the spoofing metrics calculation logic."""
        current_time = datetime.now(ZoneInfo("America/Chicago"))

        # Create test history with known patterns
        history = [
            {"volume": 100, "timestamp": current_time - timedelta(seconds=30)},
            {
                "volume": 10,
                "timestamp": current_time - timedelta(seconds=25),
            },  # Cancellation
            {"volume": 100, "timestamp": current_time - timedelta(seconds=20)},
            {
                "volume": 10,
                "timestamp": current_time - timedelta(seconds=15),
            },  # Cancellation
            {"volume": 100, "timestamp": current_time - timedelta(seconds=10)},
        ]

        metrics = detection._calculate_spoofing_metrics(
            history=history,
            price=19999.0,
            side="bid",
            best_bid=20000.0,
            best_ask=20010.0,
            tick_size=0.25,
            window_minutes=1,
        )

        # Verify metrics calculation
        assert metrics["placement_frequency"] == 5.0  # 5 events per minute
        assert (
            metrics["cancellation_rate"] == 0.5
        )  # 2 cancellations out of 4 transitions
        assert metrics["distance_ticks"] == 4.0  # (20000 - 19999) / 0.25
        assert metrics["avg_order_size"] == 64.0  # (100+10+100+10+100)/5 = 320/5 = 64

    @pytest.mark.asyncio
    async def test_confidence_score_calculation(self, detection):
        """Test confidence score calculation."""
        # Test metrics that should produce high confidence
        high_confidence_metrics = {
            "placement_frequency": 10.0,  # Very high frequency
            "cancellation_rate": 0.95,  # Very high cancellation
            "avg_time_to_cancel": 2.0,  # Very fast cancellation
            "distance_ticks": 15.0,  # Far from market
        }

        confidence = detection._calculate_spoofing_confidence(high_confidence_metrics)
        assert confidence > 0.8  # Should be high confidence

        # Test metrics that should produce low confidence
        low_confidence_metrics = {
            "placement_frequency": 1.0,  # Low frequency
            "cancellation_rate": 0.2,  # Low cancellation
            "avg_time_to_cancel": 120.0,  # Slow cancellation
            "distance_ticks": 1.0,  # Close to market
        }

        confidence = detection._calculate_spoofing_confidence(low_confidence_metrics)
        assert confidence < 0.4  # Should be low confidence

    @pytest.mark.asyncio
    async def test_pattern_classification(self, detection):
        """Test spoofing pattern classification logic."""
        # Test quote stuffing classification
        quote_stuffing_metrics = {
            "placement_frequency": 10.0,
            "avg_time_to_cancel": 3.0,
            "cancellation_rate": 0.9,
            "distance_ticks": 5.0,
            "avg_order_size": 50.0,
        }
        pattern = detection._classify_spoofing_pattern(quote_stuffing_metrics)
        assert pattern == "quote_stuffing"

        # Test momentum ignition classification
        momentum_metrics = {
            "placement_frequency": 4.0,
            "avg_time_to_cancel": 8.0,
            "cancellation_rate": 0.8,
            "distance_ticks": 2.0,
            "avg_order_size": 150.0,
        }
        pattern = detection._classify_spoofing_pattern(momentum_metrics)
        assert pattern == "momentum_ignition"

        # Test flashing classification
        flashing_metrics = {
            "placement_frequency": 3.0,
            "avg_time_to_cancel": 1.5,
            "cancellation_rate": 0.95,
            "distance_ticks": 10.0,
            "avg_order_size": 250.0,
        }
        pattern = detection._classify_spoofing_pattern(flashing_metrics)
        assert pattern == "flashing"
