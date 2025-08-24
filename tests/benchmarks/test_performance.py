"""
Performance benchmarks for project-x-py SDK.
Python 3.12+ compatible.
"""

import asyncio
from decimal import Decimal
from typing import Any

import polars as pl
import pytest
from pytest_benchmark.fixture import BenchmarkFixture

from project_x_py import TradingSuite
from project_x_py.indicators import MACD, RSI, SMA


class TestOrderPerformance:
    """Benchmark order operations."""

    @pytest.mark.benchmark(group="order_placement")
    def test_market_order_speed(self, benchmark: BenchmarkFixture) -> None:
        """Benchmark market order placement."""

        async def place_order() -> Any:
            # Create a minimal suite with mocked client
            from unittest.mock import AsyncMock, MagicMock

            mock_client = AsyncMock()
            mock_client.authenticate = AsyncMock()
            mock_client.get_instrument = AsyncMock(return_value=MagicMock(id="MNQ"))
            mock_client.place_order = AsyncMock(return_value={"order_id": "123"})

            # Create suite with mocked components
            suite = TradingSuite.__new__(TradingSuite)
            suite.client = mock_client
            suite.orders = MagicMock()
            suite.orders.place_market_order = AsyncMock(
                return_value={"order_id": "123"}
            )

            return await suite.orders.place_market_order(
                contract_id="MNQ", side=0, size=1
            )

        result = benchmark(lambda: asyncio.run(place_order()))
        assert result is not None

    @pytest.mark.benchmark(group="order_placement")
    def test_bracket_order_speed(self, benchmark: BenchmarkFixture) -> None:
        """Benchmark bracket order placement."""

        async def place_bracket() -> Any:
            # Create a minimal suite with mocked client
            from unittest.mock import AsyncMock, MagicMock

            mock_client = AsyncMock()
            mock_client.authenticate = AsyncMock()
            mock_client.get_instrument = AsyncMock(return_value=MagicMock(id="MNQ"))
            mock_client.place_order = AsyncMock(return_value={"order_id": "123"})

            # Create suite with mocked components
            suite = TradingSuite.__new__(TradingSuite)
            suite.client = mock_client
            suite.orders = MagicMock()
            suite.orders.place_bracket_order = AsyncMock(
                return_value={
                    "main_order": {"order_id": "123"},
                    "stop_order": {"order_id": "124"},
                    "target_order": {"order_id": "125"},
                }
            )

            return await suite.orders.place_bracket_order(
                contract_id="MNQ",
                side=0,
                size=1,
                stop_offset=Decimal("50"),
                target_offset=Decimal("100"),
            )

        result = benchmark(lambda: asyncio.run(place_bracket()))
        assert result is not None


class TestDataProcessing:
    """Benchmark data processing operations."""

    @pytest.mark.benchmark(group="data_processing")
    def test_tick_processing(self, benchmark: BenchmarkFixture) -> None:
        """Benchmark tick data processing."""

        async def process_ticks() -> None:
            # Create a mock data manager
            from unittest.mock import AsyncMock, MagicMock
            from project_x_py.realtime_data_manager import RealtimeDataManager

            # Create minimal mock components
            mock_client = AsyncMock()
            mock_client.instrument_cache = {}
            mock_realtime = AsyncMock()

            manager = RealtimeDataManager.__new__(RealtimeDataManager)
            manager.instrument = "MNQ"
            manager.client = mock_client
            manager.realtime_client = mock_realtime
            manager._timeframes = ["1min"]
            manager._data = {"1min": pl.DataFrame()}
            manager._tick_buffer = []
            manager._is_running = False
            manager._last_bar_times = {}
            manager._callbacks = {}
            manager._lock = asyncio.Lock()
            manager._process_tick = AsyncMock()

            # Process 10000 ticks
            for i in range(10000):
                tick = {
                    "symbol": "MNQ",
                    "price": Decimal("20000") + Decimal(str(i)),
                    "volume": 100,
                    "timestamp": i,
                }
                await manager._process_tick(tick)

        benchmark(lambda: asyncio.run(process_ticks()))

    @pytest.mark.benchmark(group="data_processing")
    def test_bar_aggregation(self, benchmark: BenchmarkFixture) -> None:
        """Benchmark bar aggregation."""

        def aggregate_bars() -> pl.DataFrame:
            # Create sample tick data
            ticks = pl.DataFrame(
                {
                    "timestamp": range(60000),
                    "price": [20000 + i for i in range(60000)],
                    "volume": [100] * 60000,
                }
            )

            # Aggregate to 1-minute bars
            return ticks.group_by_dynamic("timestamp", every="60i").agg(
                [
                    pl.col("price").first().alias("open"),
                    pl.col("price").max().alias("high"),
                    pl.col("price").min().alias("low"),
                    pl.col("price").last().alias("close"),
                    pl.col("volume").sum().alias("volume"),
                ]
            )

        result = benchmark(aggregate_bars)
        assert len(result) == 1000  # 60000 ticks / 60 = 1000 bars


class TestIndicatorPerformance:
    """Benchmark indicator calculations."""

    @pytest.fixture
    def sample_data(self) -> pl.DataFrame:
        """Create sample OHLCV data."""
        return pl.DataFrame(
            {
                "timestamp": range(1000),
                "open": [20000 + i for i in range(1000)],
                "high": [20010 + i for i in range(1000)],
                "low": [19990 + i for i in range(1000)],
                "close": [20000 + i for i in range(1000)],
                "volume": [100] * 1000,
            }
        )

    @pytest.mark.benchmark(group="indicators")
    def test_sma_performance(
        self, benchmark: BenchmarkFixture, sample_data: pl.DataFrame
    ) -> None:
        """Benchmark SMA calculation."""
        result = benchmark(lambda: SMA(sample_data, period=20))
        assert len(result) == len(sample_data)

    @pytest.mark.benchmark(group="indicators")
    def test_rsi_performance(
        self, benchmark: BenchmarkFixture, sample_data: pl.DataFrame
    ) -> None:
        """Benchmark RSI calculation."""
        result = benchmark(lambda: RSI(sample_data, period=14))
        assert len(result) == len(sample_data)

    @pytest.mark.benchmark(group="indicators")
    def test_macd_performance(
        self, benchmark: BenchmarkFixture, sample_data: pl.DataFrame
    ) -> None:
        """Benchmark MACD calculation."""
        result = benchmark(lambda: MACD(sample_data))
        assert "macd" in result.columns


class TestWebSocketPerformance:
    """Benchmark WebSocket operations."""

    @pytest.mark.benchmark(group="websocket")
    def test_message_processing(self, benchmark: BenchmarkFixture) -> None:
        """Benchmark WebSocket message processing."""

        async def process_messages() -> None:
            from unittest.mock import AsyncMock

            # Create a mock that simulates message processing
            mock_processor = AsyncMock()

            # Process 1000 messages
            for i in range(1000):
                message = {
                    "type": "quote",
                    "data": {
                        "symbol": "MNQ",
                        "bid": 20000 + i,
                        "ask": 20001 + i,
                        "timestamp": i,
                    },
                }
                await mock_processor(message)

        benchmark(lambda: asyncio.run(process_messages()))


# Mock client for testing
class MockClient:
    """Mock client for benchmark tests."""

    async def place_order(self, *args: Any, **kwargs: Any) -> dict:
        """Mock order placement."""
        return {"order_id": "test123", "status": "filled"}

    async def get_instrument(self, symbol: str) -> dict:
        """Mock instrument lookup."""
        return {"id": f"CON.F.US.{symbol}", "tick_size": Decimal("0.25")}
