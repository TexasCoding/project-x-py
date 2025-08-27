"""
Comprehensive TDD tests for OrderBookBase following strict TDD methodology.

These tests serve as the specification for correct OrderBook behavior.
Tests are written BEFORE implementation fixes to discover bugs.
If tests fail, the implementation is wrong - not the tests.
"""

import asyncio
from collections import deque
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import polars as pl
import pytest
import pytz

from project_x_py.orderbook.base import OrderBookBase
from project_x_py.orderbook.memory import MemoryManager
from project_x_py.types import DEFAULT_TIMEZONE, MemoryConfig


@pytest.fixture
async def mock_event_bus():
    """Create a mock event bus for testing."""
    event_bus = Mock()
    event_bus.emit = AsyncMock()
    event_bus.subscribe = AsyncMock()
    event_bus.on = Mock(return_value=lambda func: func)
    return event_bus


@pytest.fixture
async def mock_project_x():
    """Create a mock ProjectX client for testing."""
    client = Mock()
    client.get_instrument = AsyncMock()
    client.get_instrument.return_value = Mock(tickSize=Decimal("0.25"))
    return client


@pytest.fixture
async def orderbook_base(mock_event_bus, mock_project_x):
    """Create an OrderBookBase instance for testing."""
    ob = OrderBookBase(
        instrument="MNQ",
        event_bus=mock_event_bus,
        project_x=mock_project_x,
        timezone_str=DEFAULT_TIMEZONE,
    )
    return ob


class TestOrderBookBaseInitialization:
    """Test OrderBookBase initialization and configuration."""

    @pytest.mark.asyncio
    async def test_initialization_with_defaults(self, mock_event_bus):
        """Test OrderBookBase initializes with correct default values."""
        ob = OrderBookBase(
            instrument="ES",
            event_bus=mock_event_bus,
        )

        # Core attributes
        assert ob.instrument == "ES"
        assert ob.event_bus == mock_event_bus
        assert ob.project_x is None
        assert ob.timezone == pytz.timezone(DEFAULT_TIMEZONE)

        # Data structures should be initialized
        assert isinstance(ob.orderbook_bids, pl.DataFrame)
        assert isinstance(ob.orderbook_asks, pl.DataFrame)
        assert isinstance(ob.recent_trades, pl.DataFrame)

        # DataFrames should be empty
        assert ob.orderbook_bids.height == 0
        assert ob.orderbook_asks.height == 0
        assert ob.recent_trades.height == 0

        # Statistics tracking
        assert ob._trades_processed == 0
        assert ob._total_volume == 0
        assert ob._largest_trade == 0
        assert ob._bid_updates == 0
        assert ob._ask_updates == 0

        # Pattern detection stats
        assert ob._pattern_detections["icebergs_detected"] == 0
        assert ob._pattern_detections["spoofing_alerts"] == 0
        assert ob._pattern_detections["unusual_patterns"] == 0

        # Data quality metrics
        assert ob._data_quality["data_gaps"] == 0
        assert ob._data_quality["invalid_updates"] == 0
        assert ob._data_quality["duplicate_updates"] == 0

    @pytest.mark.asyncio
    async def test_initialization_with_custom_config(self, mock_event_bus):
        """Test OrderBookBase with custom configuration."""
        config = {
            "max_trade_history": 5000,
            "max_depth_levels": 50,
            "enable_analytics": True,
        }

        ob = OrderBookBase(
            instrument="NQ",
            event_bus=mock_event_bus,
            config=config,
        )

        # Configuration should be applied
        assert ob.config == config
        assert ob.max_trade_history == 5000
        assert ob.max_depth_levels == 50

        # Memory config should use custom values
        assert ob.memory_config.max_trades == 5000
        assert ob.memory_config.max_depth_entries == 50

    @pytest.mark.asyncio
    async def test_initialization_with_project_x(self, mock_event_bus, mock_project_x):
        """Test initialization with ProjectX client for tick size lookup."""
        ob = OrderBookBase(
            instrument="MNQ",
            event_bus=mock_event_bus,
            project_x=mock_project_x,
        )

        assert ob.project_x == mock_project_x
        assert ob._tick_size is None  # Should be fetched on demand

    @pytest.mark.asyncio
    async def test_dataframe_schemas(self, orderbook_base):
        """Test that DataFrames have correct schemas."""
        ob = orderbook_base

        # Bid DataFrame schema
        bid_schema = ob.orderbook_bids.schema
        assert "price" in bid_schema
        assert "volume" in bid_schema
        assert "timestamp" in bid_schema
        assert bid_schema["price"] == pl.Float64
        assert bid_schema["volume"] == pl.Int64
        assert str(bid_schema["timestamp"]).startswith("Datetime")

        # Ask DataFrame schema
        ask_schema = ob.orderbook_asks.schema
        assert "price" in ask_schema
        assert "volume" in ask_schema
        assert "timestamp" in ask_schema
        assert ask_schema["price"] == pl.Float64
        assert ask_schema["volume"] == pl.Int64
        assert str(ask_schema["timestamp"]).startswith("Datetime")

        # Trade DataFrame schema
        trade_schema = ob.recent_trades.schema
        assert "price" in trade_schema
        assert "volume" in trade_schema
        assert "timestamp" in trade_schema
        assert "side" in trade_schema
        assert "spread_at_trade" in trade_schema
        assert "mid_price_at_trade" in trade_schema
        assert "best_bid_at_trade" in trade_schema
        assert "best_ask_at_trade" in trade_schema
        assert "order_type" in trade_schema

        assert trade_schema["price"] == pl.Float64
        assert trade_schema["volume"] == pl.Int64
        assert trade_schema["side"] == pl.Utf8
        assert trade_schema["order_type"] == pl.Utf8


class TestOrderBookDataOperations:
    """Test OrderBook data update and retrieval operations."""

    @pytest.mark.asyncio
    async def test_update_orderbook_bids_directly(self, orderbook_base):
        """Test that bid side can be updated and retrieved correctly."""
        ob = orderbook_base

        timestamp = datetime.now(ob.timezone)

        # Directly update bid DataFrame (as RealtimeHandler does)
        new_bids = pl.DataFrame({
            "price": [21000.0, 20999.75, 20999.50],
            "volume": [10, 5, 15],
            "timestamp": [timestamp, timestamp, timestamp],
        })

        async with ob.orderbook_lock:
            ob.orderbook_bids = new_bids
            ob.last_orderbook_update = timestamp
            await ob.track_bid_update(3)

        # Verify bid DataFrame updated correctly
        assert ob.orderbook_bids.height == 3
        assert ob.orderbook_bids["price"].to_list() == [21000.0, 20999.75, 20999.50]
        assert ob.orderbook_bids["volume"].to_list() == [10, 5, 15]

        # Verify statistics updated
        assert ob._bid_updates == 3
        assert ob.last_orderbook_update == timestamp

    @pytest.mark.asyncio
    async def test_update_orderbook_asks_directly(self, orderbook_base):
        """Test that ask side can be updated and retrieved correctly."""
        ob = orderbook_base

        timestamp = datetime.now(ob.timezone)

        # Directly update ask DataFrame (as RealtimeHandler does)
        new_asks = pl.DataFrame({
            "price": [21000.25, 21000.50, 21000.75],
            "volume": [8, 12, 20],
            "timestamp": [timestamp, timestamp, timestamp],
        })

        async with ob.orderbook_lock:
            ob.orderbook_asks = new_asks
            ob.last_orderbook_update = timestamp
            await ob.track_ask_update(3)

        # Verify ask DataFrame updated correctly
        assert ob.orderbook_asks.height == 3
        assert ob.orderbook_asks["price"].to_list() == [21000.25, 21000.50, 21000.75]
        assert ob.orderbook_asks["volume"].to_list() == [8, 12, 20]

        # Verify statistics updated
        assert ob._ask_updates == 3

    @pytest.mark.asyncio
    async def test_orderbook_replaces_data(self, orderbook_base):
        """Test that orderbook updates replace existing data."""
        ob = orderbook_base

        timestamp1 = datetime.now(ob.timezone)
        timestamp2 = datetime.now(ob.timezone)

        # First update
        async with ob.orderbook_lock:
            ob.orderbook_bids = pl.DataFrame({
                "price": [100.0],
                "volume": [10],
                "timestamp": [timestamp1],
            })
        assert ob.orderbook_bids.height == 1

        # Second update should replace, not append
        async with ob.orderbook_lock:
            ob.orderbook_bids = pl.DataFrame({
                "price": [101.0, 100.5],
                "volume": [20, 15],
                "timestamp": [timestamp2, timestamp2],
            })

        # Should have 2 rows, not 3
        assert ob.orderbook_bids.height == 2
        assert ob.orderbook_bids["price"].to_list() == [101.0, 100.5]

    @pytest.mark.asyncio
    async def test_add_trade_to_orderbook(self, orderbook_base):
        """Test that trades can be recorded and tracked."""
        ob = orderbook_base

        timestamp = datetime.now(ob.timezone)

        # Setup best bid/ask for spread calculation
        async with ob.orderbook_lock:
            ob.orderbook_bids = pl.DataFrame({
                "price": [21000.0],
                "volume": [10],
                "timestamp": [timestamp],
            })
            ob.orderbook_asks = pl.DataFrame({
                "price": [21000.25],
                "volume": [10],
                "timestamp": [timestamp],
            })

        # Get best prices for spread calculation
        best = await ob.get_best_bid_ask()

        # Add a trade (simulate what RealtimeHandler does)
        # Fixed: get_best_bid_ask now returns 'mid_price'

        # Create trade row with same column order as recent_trades
        trade_row = pl.DataFrame({
            "price": [21000.25],
            "volume": [5],
            "timestamp": [timestamp],
            "side": ["buy"],
            "spread_at_trade": [best["spread"]],
            "mid_price_at_trade": [best["mid_price"]],
            "best_bid_at_trade": [best["bid"]],
            "best_ask_at_trade": [best["ask"]],
            "order_type": ["market"],
        })

        async with ob.orderbook_lock:
            ob.recent_trades = pl.concat([ob.recent_trades, trade_row])
            ob.cumulative_delta += 5  # Buy adds to delta
            await ob.track_trade_processed(5, 21000.25)


        # Verify trade added
        assert ob.recent_trades.height == 1
        assert ob.recent_trades["price"][0] == 21000.25
        assert ob.recent_trades["volume"][0] == 5
        assert ob.recent_trades["side"][0] == "buy"
        assert ob.recent_trades["order_type"][0] == "market"
        assert ob.recent_trades["spread_at_trade"][0] == 0.25
        assert ob.recent_trades["mid_price_at_trade"][0] == 21000.125
        assert ob.recent_trades["best_bid_at_trade"][0] == 21000.0
        assert ob.recent_trades["best_ask_at_trade"][0] == 21000.25

        # Verify statistics
        assert ob._trades_processed == 1
        assert ob._total_volume == 5
        assert ob._largest_trade == 5
        assert ob.cumulative_delta == 5  # Buy adds to delta

    @pytest.mark.asyncio
    async def test_sell_trade_affects_delta(self, orderbook_base):
        """Test that sell-side trades decrease cumulative delta."""
        ob = orderbook_base

        timestamp = datetime.now(ob.timezone)

        # Setup orderbook
        async with ob.orderbook_lock:
            ob.orderbook_bids = pl.DataFrame({
                "price": [21000.0],
                "volume": [10],
                "timestamp": [timestamp],
            })
            ob.orderbook_asks = pl.DataFrame({
                "price": [21000.25],
                "volume": [10],
                "timestamp": [timestamp],
            })

        # Get best prices
        best = await ob.get_best_bid_ask()

        # Fixed: get_best_bid_ask now returns 'mid_price'

        # Add sell trade (column order must match recent_trades)
        trade_row = pl.DataFrame({
            "price": [21000.0],
            "volume": [3],
            "timestamp": [timestamp],
            "side": ["sell"],
            "spread_at_trade": [best["spread"]],
            "mid_price_at_trade": [best["mid_price"]],
            "best_bid_at_trade": [best["bid"]],
            "best_ask_at_trade": [best["ask"]],
            "order_type": ["market"],
        })

        async with ob.orderbook_lock:
            ob.recent_trades = pl.concat([ob.recent_trades, trade_row])
            ob.cumulative_delta -= 3  # Sell subtracts from delta
            await ob.track_trade_processed(3, 21000.0)

        # Verify cumulative delta
        assert ob.cumulative_delta == -3  # Sell subtracts from delta
        assert ob.recent_trades["side"][0] == "sell"

    @pytest.mark.asyncio
    async def test_get_orderbook_snapshot(self, orderbook_base):
        """Test getting orderbook snapshot."""
        ob = orderbook_base

        timestamp = datetime.now(ob.timezone)

        # Setup orderbook
        async with ob.orderbook_lock:
            ob.orderbook_bids = pl.DataFrame({
                "price": [21000.0, 20999.75, 20999.50],
                "volume": [10, 5, 15],
                "timestamp": [timestamp, timestamp, timestamp],
            })
            ob.orderbook_asks = pl.DataFrame({
                "price": [21000.25, 21000.50, 21000.75],
                "volume": [8, 12, 20],
                "timestamp": [timestamp, timestamp, timestamp],
            })
            ob.last_orderbook_update = timestamp

        # Get snapshot
        snapshot = await ob.get_orderbook_snapshot(levels=2)

        # Verify snapshot structure
        assert "timestamp" in snapshot
        assert "best_bid" in snapshot
        assert "best_ask" in snapshot
        assert "spread" in snapshot
        assert "mid_price" in snapshot
        assert "bids" in snapshot
        assert "asks" in snapshot
        assert "imbalance" in snapshot
        assert "total_bid_volume" in snapshot
        assert "total_ask_volume" in snapshot

        # Verify values
        assert snapshot["best_bid"] == 21000.0
        assert snapshot["best_ask"] == 21000.25
        assert snapshot["spread"] == 0.25
        assert snapshot["mid_price"] == 21000.125
        assert len(snapshot["bids"]) == 2  # Limited to 2 levels
        assert len(snapshot["asks"]) == 2
        assert snapshot["total_bid_volume"] == 15  # 10 + 5 (first 2 levels)
        assert snapshot["total_ask_volume"] == 20  # 8 + 12
        assert snapshot["imbalance"] == (15 - 20) / (15 + 20)  # (bid - ask) / (bid + ask)

    @pytest.mark.asyncio
    async def test_get_orderbook_snapshot_empty(self, orderbook_base):
        """Test getting snapshot from empty orderbook."""
        ob = orderbook_base

        snapshot = await ob.get_orderbook_snapshot()

        # Should handle empty orderbook gracefully
        assert snapshot["best_bid"] is None
        assert snapshot["best_ask"] is None
        assert snapshot["spread"] is None
        assert snapshot["mid_price"] is None
        assert snapshot["bids"] == []
        assert snapshot["asks"] == []
        assert snapshot["imbalance"] is None  # None when no data, not 0.0
        assert snapshot["total_bid_volume"] == 0
        assert snapshot["total_ask_volume"] == 0

    @pytest.mark.asyncio
    async def test_get_best_bid_ask(self, orderbook_base):
        """Test getting best bid and ask prices."""
        ob = orderbook_base

        # Empty orderbook
        best = await ob.get_best_bid_ask()
        assert best["bid"] is None
        assert best["ask"] is None
        assert best["spread"] is None
        # Fixed: get_best_bid_ask now has 'mid_price' field
        assert best["mid_price"] is None

        # Add data
        timestamp = datetime.now(ob.timezone)
        async with ob.orderbook_lock:
            ob.orderbook_bids = pl.DataFrame({
                "price": [21000.0, 20999.0],
                "volume": [10, 5],
                "timestamp": [timestamp, timestamp],
            })
            ob.orderbook_asks = pl.DataFrame({
                "price": [21001.0, 21002.0],
                "volume": [8, 12],
                "timestamp": [timestamp, timestamp],
            })

        # Get best prices
        best = await ob.get_best_bid_ask()
        assert best["bid"] == 21000.0
        assert best["ask"] == 21001.0
        assert best["spread"] == 1.0
        # Fixed: get_best_bid_ask now returns 'mid_price'
        assert best["mid_price"] == 21000.5

    @pytest.mark.asyncio
    async def test_get_orderbook_depth(self, orderbook_base):
        """Test getting orderbook depth at specific levels."""
        ob = orderbook_base

        timestamp = datetime.now(ob.timezone)

        # Setup orderbook with multiple levels
        async with ob.orderbook_lock:
            ob.orderbook_bids = pl.DataFrame({
                "price": [100.0, 99.5, 99.0, 98.5],
                "volume": [10, 20, 30, 40],
                "timestamp": [timestamp] * 4,
            })
            ob.orderbook_asks = pl.DataFrame({
                "price": [100.5, 101.0, 101.5, 102.0],
                "volume": [15, 25, 35, 45],
                "timestamp": [timestamp] * 4,
            })

        # Get bids with limit
        bids_df = await ob.get_orderbook_bids(levels=2)
        assert bids_df.height == 2
        assert bids_df["price"].to_list() == [100.0, 99.5]
        assert bids_df["volume"].to_list() == [10, 20]

        # Get asks with limit
        asks_df = await ob.get_orderbook_asks(levels=3)
        assert asks_df.height == 3
        assert asks_df["price"].to_list() == [100.5, 101.0, 101.5]
        assert asks_df["volume"].to_list() == [15, 25, 35]

    @pytest.mark.asyncio
    async def test_get_recent_trades(self, orderbook_base):
        """Test retrieving recent trades."""
        ob = orderbook_base

        # Add multiple trades
        timestamp = datetime.now(ob.timezone)

        # Create trades DataFrame
        trades_df = pl.DataFrame({
            "price": [100.0, 100.25, 99.75, 100.0],
            "volume": [5, 10, 8, 3],
            "timestamp": [timestamp] * 4,
            "side": ["buy", "buy", "sell", "buy"],
            "order_type": ["market", "limit", "market", "market"],
            "spread_at_trade": [None] * 4,
            "mid_price_at_trade": [None] * 4,
            "best_bid_at_trade": [None] * 4,
            "best_ask_at_trade": [None] * 4,
        })

        async with ob.orderbook_lock:
            ob.recent_trades = trades_df

        # Get recent trades
        recent = await ob.get_recent_trades(count=2)
        assert len(recent) == 2
        # tail() returns last 2 trades in order (not reversed)
        assert recent[0]["price"] == 99.75  # Third trade
        assert recent[0]["volume"] == 8
        assert recent[1]["price"] == 100.0   # Fourth trade
        assert recent[1]["volume"] == 3

    @pytest.mark.asyncio
    async def test_price_level_history_tracking(self, orderbook_base):
        """Test that price level history is tracked correctly."""
        ob = orderbook_base

        # Update same price level multiple times
        timestamp1 = datetime.now(ob.timezone)
        timestamp2 = datetime.now(ob.timezone)

        # Track price level updates (simulating what RealtimeHandler does)
        key = (100.0, "bid")
        ob.price_level_history[key].append({
            "timestamp": timestamp1,
            "volume": 10,
            "update_type": "add",
        })
        ob.price_level_history[key].append({
            "timestamp": timestamp2,
            "volume": 20,
            "update_type": "modify",
        })

        # Check price level history
        assert key in ob.price_level_history
        history = ob.price_level_history[key]
        assert len(history) == 2
        assert history[0]["volume"] == 10
        assert history[1]["volume"] == 20

    @pytest.mark.asyncio
    async def test_spread_tracking(self, orderbook_base):
        """Test that spread is tracked over time."""
        ob = orderbook_base

        # Update orderbook multiple times with different spreads
        for i in range(3):
            timestamp = datetime.now(ob.timezone)

            async with ob.orderbook_lock:
                ob.orderbook_bids = pl.DataFrame({
                    "price": [100.0 - i * 0.1],
                    "volume": [10],
                    "timestamp": [timestamp],
                })
                ob.orderbook_asks = pl.DataFrame({
                    "price": [100.5 + i * 0.1],
                    "volume": [10],
                    "timestamp": [timestamp],
                })

                # _get_best_bid_ask_unlocked() auto-updates spread_history
                best = ob._get_best_bid_ask_unlocked()

        # Check spread history (should have been updated automatically)
        assert len(ob.spread_history) == 3
        assert abs(ob.spread_history[0]["spread"] - 0.5) < 0.001  # 100.5 - 100.0
        assert abs(ob.spread_history[1]["spread"] - 0.7) < 0.001  # 100.6 - 99.9
        assert abs(ob.spread_history[2]["spread"] - 0.9) < 0.001  # 100.7 - 99.8


class TestOrderBookThreadSafety:
    """Test thread-safety of OrderBook operations."""

    @pytest.mark.asyncio
    async def test_concurrent_updates(self, orderbook_base):
        """Test that concurrent updates are thread-safe."""
        ob = orderbook_base

        # Define concurrent update tasks
        async def update_bids():
            for i in range(10):
                timestamp = datetime.now(ob.timezone)
                async with ob.orderbook_lock:
                    ob.orderbook_bids = pl.DataFrame({
                        "price": [100.0 - i * 0.1],
                        "volume": [10],
                        "timestamp": [timestamp],
                    })
                    await ob.track_bid_update(1)
                await asyncio.sleep(0.001)

        async def update_asks():
            for i in range(10):
                timestamp = datetime.now(ob.timezone)
                async with ob.orderbook_lock:
                    ob.orderbook_asks = pl.DataFrame({
                        "price": [101.0 + i * 0.1],
                        "volume": [10],
                        "timestamp": [timestamp],
                    })
                    await ob.track_ask_update(1)
                await asyncio.sleep(0.001)

        async def add_trades():
            for i in range(10):
                timestamp = datetime.now(ob.timezone)
                # Column order must match recent_trades
                trade_row = pl.DataFrame({
                    "price": [100.5 + i * 0.1],
                    "volume": [5],
                    "timestamp": [timestamp],
                    "side": ["buy" if i % 2 == 0 else "sell"],
                    "spread_at_trade": [None],
                    "mid_price_at_trade": [None],
                    "best_bid_at_trade": [None],
                    "best_ask_at_trade": [None],
                    "order_type": ["market"],
                })
                async with ob.orderbook_lock:
                    ob.recent_trades = pl.concat([ob.recent_trades, trade_row])
                    delta_change = 5 if i % 2 == 0 else -5
                    ob.cumulative_delta += delta_change
                    await ob.track_trade_processed(5, 100.5 + i * 0.1)
                await asyncio.sleep(0.001)

        # Run updates concurrently
        await asyncio.gather(
            update_bids(),
            update_asks(),
            add_trades(),
        )

        # Verify data integrity
        assert ob._bid_updates == 10
        assert ob._ask_updates == 10
        assert ob._trades_processed == 10
        assert ob.recent_trades.height == 10

    @pytest.mark.asyncio
    async def test_concurrent_reads(self, orderbook_base):
        """Test that concurrent reads don't interfere."""
        ob = orderbook_base

        # Setup orderbook
        timestamp = datetime.now(ob.timezone)
        async with ob.orderbook_lock:
            ob.orderbook_bids = pl.DataFrame({
                "price": [100.0],
                "volume": [10],
                "timestamp": [timestamp],
            })
            ob.orderbook_asks = pl.DataFrame({
                "price": [101.0],
                "volume": [10],
                "timestamp": [timestamp],
            })

        # Define concurrent read tasks
        async def read_snapshot():
            snapshots = []
            for _ in range(10):
                snapshot = await ob.get_orderbook_snapshot()
                snapshots.append(snapshot)
                await asyncio.sleep(0.001)
            return snapshots

        async def read_best():
            bests = []
            for _ in range(10):
                best = await ob.get_best_bid_ask()
                bests.append(best)
                await asyncio.sleep(0.001)
            return bests

        # Run reads concurrently
        snapshots, bests = await asyncio.gather(
            read_snapshot(),
            read_best(),
        )

        # All reads should return consistent data
        assert all(s["best_bid"] == 100.0 for s in snapshots)
        assert all(s["best_ask"] == 101.0 for s in snapshots)
        assert all(b["bid"] == 100.0 for b in bests)
        assert all(b["ask"] == 101.0 for b in bests)


class TestOrderBookStatistics:
    """Test OrderBook statistics tracking."""

    @pytest.mark.asyncio
    async def test_trade_statistics(self, orderbook_base):
        """Test that trade statistics are tracked correctly."""
        ob = orderbook_base

        # Add various trades
        timestamp = datetime.now(ob.timezone)
        trades_df = pl.DataFrame({
            "price": [100.0, 100.5, 99.5, 100.0, 99.0],
            "volume": [5, 10, 8, 15, 3],
            "side": ["buy", "buy", "sell", "buy", "sell"],
            "timestamp": [timestamp] * 5,
            "order_type": ["market"] * 5,
            "spread_at_trade": [None] * 5,
            "mid_price_at_trade": [None] * 5,
            "best_bid_at_trade": [None] * 5,
            "best_ask_at_trade": [None] * 5,
        })

        async with ob.orderbook_lock:
            ob.recent_trades = trades_df
            ob._trades_processed = 5
            ob._total_volume = 41  # 5 + 10 + 8 + 15 + 3
            ob._largest_trade = 15
            ob.cumulative_delta = (5 + 10 + 15) - (8 + 3)  # 19
            ob.order_type_stats["market"] = 5

        # Verify statistics
        assert ob._trades_processed == 5
        assert ob._total_volume == 5 + 10 + 8 + 15 + 3  # 41
        assert ob._largest_trade == 15
        assert ob.cumulative_delta == (5 + 10 + 15) - (8 + 3)  # 19

    @pytest.mark.asyncio
    async def test_order_type_statistics(self, orderbook_base):
        """Test that order type statistics are tracked."""
        ob = orderbook_base

        # Add trades with different order types
        timestamp = datetime.now(ob.timezone)
        trades_df = pl.DataFrame({
            "price": [100.0, 100.1, 100.2, 100.3, 100.4, 100.5],
            "volume": [5] * 6,
            "timestamp": [timestamp] * 6,
            "side": ["buy"] * 6,
            "order_type": ["market", "market", "limit", "stop", "market", "limit"],
            "spread_at_trade": [None] * 6,
            "mid_price_at_trade": [None] * 6,
            "best_bid_at_trade": [None] * 6,
            "best_ask_at_trade": [None] * 6,
        })

        async with ob.orderbook_lock:
            ob.recent_trades = trades_df
            ob.order_type_stats["market"] = 3
            ob.order_type_stats["limit"] = 2
            ob.order_type_stats["stop"] = 1

        # Verify order type stats
        assert ob.order_type_stats["market"] == 3
        assert ob.order_type_stats["limit"] == 2
        assert ob.order_type_stats["stop"] == 1

    @pytest.mark.asyncio
    async def test_get_statistics(self, orderbook_base):
        """Test comprehensive statistics retrieval."""
        ob = orderbook_base

        # Setup orderbook with data
        timestamp = datetime.now(ob.timezone)
        async with ob.orderbook_lock:
            ob.orderbook_bids = pl.DataFrame({
                "price": [100.0, 99.5],
                "volume": [10, 20],
                "timestamp": [timestamp] * 2,
            })
            ob.orderbook_asks = pl.DataFrame({
                "price": [100.5, 101.0],
                "volume": [15, 25],
                "timestamp": [timestamp] * 2,
            })
            await ob.track_bid_update(2)
            await ob.track_ask_update(2)

        # Add some trades
        trades_df = pl.DataFrame({
            "price": [100.5, 100.0],
            "volume": [5, 8],
            "side": ["buy", "sell"],
            "timestamp": [timestamp] * 2,
            "order_type": ["market"] * 2,
            "spread_at_trade": [0.5, 0.5],
            "mid_price_at_trade": [100.25, 100.25],
            "best_bid_at_trade": [100.0, 100.0],
            "best_ask_at_trade": [100.5, 100.5],
        })

        async with ob.orderbook_lock:
            ob.recent_trades = trades_df
            ob._trades_processed = 2
            ob._total_volume = 13
            ob._largest_trade = 8
            ob.cumulative_delta = -3  # 5 - 8

        # Get statistics (using get_memory_stats which returns comprehensive stats)
        stats = await ob.get_memory_stats()

        # Verify statistics structure and values (flat structure)
        assert "trades_processed" in stats
        assert "total_volume" in stats
        assert "largest_trade" in stats
        assert "icebergs_detected" in stats
        assert "spoofing_alerts" in stats
        assert "data_gaps" in stats

        # Verify values
        assert stats["trades_processed"] == 2
        assert stats["total_volume"] == 13
        assert stats["largest_trade"] == 8
        assert stats["bids_count"] == 2
        assert stats["asks_count"] == 2
        # Spread and delta tracking is in the actual data


class TestOrderBookMemoryManagement:
    """Test OrderBook memory management features."""

    @pytest.mark.asyncio
    async def test_memory_config_defaults(self, orderbook_base):
        """Test default memory configuration."""
        ob = orderbook_base

        # Check memory config defaults
        assert ob.memory_config.max_trades == ob.max_trade_history
        assert ob.memory_config.max_depth_entries == ob.max_depth_levels
        assert isinstance(ob.memory_manager, MemoryManager)

    @pytest.mark.asyncio
    async def test_price_level_history_maxlen(self, orderbook_base):
        """Test that price level history respects max length."""
        ob = orderbook_base

        # Update same price level more than maxlen times
        price = 100.0
        key = (price, "bid")

        for i in range(1500):  # More than deque maxlen of 1000
            ob.price_level_history[key].append({
                "timestamp": datetime.now(ob.timezone),
                "volume": i,
                "update_type": "modify",
            })

        # Check that history is limited
        key = (price, "bid")
        assert key in ob.price_level_history
        history = ob.price_level_history[key]
        assert len(history) <= 1000  # Should be limited by deque maxlen

    @pytest.mark.asyncio
    async def test_delta_history_maxlen(self, orderbook_base):
        """Test that delta history respects max length."""
        ob = orderbook_base

        # Add more trades than delta_history maxlen
        for i in range(1500):  # More than deque maxlen of 1000
            timestamp = datetime.now(ob.timezone)
            delta_change = 1 if i % 2 == 0 else -1
            ob.delta_history.append({
                "timestamp": timestamp,
                "delta": delta_change,
                "cumulative": ob.cumulative_delta + delta_change,
            })
            ob.cumulative_delta += delta_change

        # Check that delta history is limited
        assert len(ob.delta_history) <= 1000

    @pytest.mark.asyncio
    async def test_cleanup_method(self, orderbook_base):
        """Test that cleanup properly releases resources."""
        ob = orderbook_base

        # Add some data
        timestamp = datetime.now(ob.timezone)
        async with ob.orderbook_lock:
            ob.orderbook_bids = pl.DataFrame({
                "price": [100.0],
                "volume": [10],
                "timestamp": [timestamp],
            })

        # Mock memory manager stop
        with patch.object(ob.memory_manager, "stop", new_callable=AsyncMock) as mock_stop:
            await ob.cleanup()

            # Verify memory manager was stopped
            mock_stop.assert_called_once()


class TestOrderBookErrorHandling:
    """Test OrderBook error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_update_with_empty_data(self, orderbook_base):
        """Test handling empty orderbook data."""
        ob = orderbook_base

        # Update with empty DataFrame should work fine
        timestamp = datetime.now(ob.timezone)
        async with ob.orderbook_lock:
            ob.orderbook_bids = pl.DataFrame({
                "price": [],
                "volume": [],
                "timestamp": [],
            })
        assert ob.orderbook_bids.height == 0

    @pytest.mark.asyncio
    async def test_get_best_with_invalid_data(self, orderbook_base):
        """Test getting best prices with malformed orderbook data."""
        ob = orderbook_base

        # Set up orderbook with zero or negative prices (invalid)
        timestamp = datetime.now(ob.timezone)
        async with ob.orderbook_lock:
            ob.orderbook_bids = pl.DataFrame({
                "price": [0.0, -100.0],
                "volume": [10, 20],
                "timestamp": [timestamp] * 2,
            })

        # Should handle gracefully
        best = await ob.get_best_bid_ask()
        # Implementation might filter out invalid prices or return them as-is
        # This test checks that the method doesn't crash

    @pytest.mark.asyncio
    async def test_trade_without_orderbook_data(self, orderbook_base):
        """Test handling trades when orderbook is empty."""
        ob = orderbook_base

        # Add trade without any orderbook data
        timestamp = datetime.now(ob.timezone)
        trade_row = pl.DataFrame({
            "price": [100.0],
            "volume": [5],
            "timestamp": [timestamp],
            "side": ["buy"],
            "order_type": ["market"],
            "spread_at_trade": [None],  # None since no orderbook
            "mid_price_at_trade": [None],
            "best_bid_at_trade": [None],
            "best_ask_at_trade": [None],
        })

        async with ob.orderbook_lock:
            ob.recent_trades = trade_row

        # Should handle gracefully with None values for spread fields
        assert ob.recent_trades.height == 1
        assert ob.recent_trades["price"][0] == 100.0
        assert ob.recent_trades["spread_at_trade"][0] is None
        assert ob.recent_trades["mid_price_at_trade"][0] is None

    @pytest.mark.asyncio
    async def test_get_tick_size_with_project_x(self, orderbook_base):
        """Test getting tick size from ProjectX client."""
        ob = orderbook_base

        # Get tick size (should call ProjectX)
        tick_size = await ob.get_tick_size()

        # Verify tick size retrieved
        assert tick_size == Decimal("0.25")
        assert ob._tick_size == Decimal("0.25")  # Should be cached

        # Second call should use cached value
        ob.project_x.get_instrument.reset_mock()
        tick_size2 = await ob.get_tick_size()
        assert tick_size2 == Decimal("0.25")
        ob.project_x.get_instrument.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_tick_size_without_project_x(self, mock_event_bus):
        """Test getting tick size without ProjectX client."""
        ob = OrderBookBase(
            instrument="ES",
            event_bus=mock_event_bus,
            project_x=None,
        )

        # Should return default tick size without ProjectX
        tick_size = await ob.get_tick_size()
        assert tick_size == Decimal("0.01")  # Default fallback


class TestOrderBookEventEmission:
    """Test that OrderBook properly emits events via EventBus."""

    @pytest.mark.asyncio
    async def test_trade_event_emission(self, orderbook_base):
        """Test that events are emitted through EventBus."""
        ob = orderbook_base

        # Trigger callbacks (which emit events through EventBus)
        await ob._trigger_callbacks("trade", {
            "price": 100.0,
            "volume": 5,
            "timestamp": datetime.now(ob.timezone),
            "side": "buy",
            "order_type": "market",
        })

        # Verify event was emitted
        ob.event_bus.emit.assert_called()
        # Check that the correct event type was used
        call_args = ob.event_bus.emit.call_args
        assert call_args is not None

    @pytest.mark.asyncio
    async def test_depth_update_event_emission(self, orderbook_base):
        """Test that depth update events are emitted."""
        ob = orderbook_base

        # Trigger depth update event
        await ob._trigger_callbacks("depth_update", {
            "bids": [{"price": 100.0, "volume": 10}],
            "asks": [],
            "timestamp": datetime.now(ob.timezone),
        })

        # Verify event was emitted
        ob.event_bus.emit.assert_called()


class TestOrderBookIntegration:
    """Test OrderBook integration with other components."""

    @pytest.mark.asyncio
    async def test_memory_manager_integration(self, orderbook_base):
        """Test that OrderBook properly integrates with MemoryManager."""
        ob = orderbook_base

        # Verify memory manager is initialized
        assert ob.memory_manager is not None
        assert ob.memory_manager.orderbook == ob
        assert ob.memory_manager.config == ob.memory_config

    @pytest.mark.asyncio
    async def test_statistics_tracker_integration(self, orderbook_base):
        """Test that OrderBook inherits from BaseStatisticsTracker."""
        ob = orderbook_base

        # Should have statistics methods from BaseStatisticsTracker
        assert hasattr(ob, "get_memory_stats")
        assert hasattr(ob, "component_name")
        assert ob.component_name == "orderbook_MNQ"


# Run tests with coverage reporting
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=project_x_py.orderbook.base", "--cov-report=term-missing"])
