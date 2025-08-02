"""Tests for AsyncOrderBook."""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import polars as pl
import pytest

from project_x_py.orderbook import OrderBook
from project_x_py.realtime import ProjectXRealtimeClient
RealtimeClient = ProjectXRealtimeClient  # back-compat for existing code


@pytest.fixture
def mock_async_client():
    """Create a mock AsyncProjectX client."""
    client = MagicMock()
    client.get_instrument = AsyncMock()
    return client


@pytest.fixture
def mock_realtime_client():
    """Create a mock AsyncProjectXRealtimeClient."""
    client = MagicMock()
    client.add_callback = AsyncMock()
    return client


@pytest.fixture
def orderbook(mock_async_client):
    """Create an AsyncOrderBook instance."""
    return OrderBook("MGC", client=mock_async_client)


@pytest.mark.asyncio
async def test_orderbook_initialization(mock_async_client):
    """Test AsyncOrderBook initialization."""
    orderbook = OrderBook("MGC", timezone="America/New_York")

    assert orderbook.instrument == "MGC"
    assert str(orderbook.timezone) == "America/New_York"
    assert isinstance(orderbook.orderbook_lock, asyncio.Lock)


@pytest.mark.asyncio
async def test_initialize_with_realtime_client(
    orderbook, mock_realtime_client, mock_async_client
):
    """Test initialization with real-time client."""
    # Mock instrument info
    mock_instrument = MagicMock()
    mock_instrument.tickSize = 0.1
    mock_async_client.get_instrument.return_value = mock_instrument

    result = await orderbook.initialize(mock_realtime_client)

    assert result is True
    assert orderbook.tick_size == 0.1
    assert hasattr(orderbook, "realtime_client")
    assert (
        mock_realtime_client.add_callback.call_count == 2
    )  # market_depth and quote_update


@pytest.mark.asyncio
async def test_initialize_without_realtime_client(orderbook, mock_async_client):
    """Test initialization without real-time client."""
    # Mock instrument info
    mock_instrument = MagicMock()
    mock_instrument.tickSize = 0.25
    mock_async_client.get_instrument.return_value = mock_instrument

    result = await orderbook.initialize()

    assert result is True
    assert orderbook.tick_size == 0.25
    assert not hasattr(orderbook, "realtime_client")


@pytest.mark.asyncio
async def test_process_market_depth_bid_ask(orderbook):
    """Test processing market depth with bid and ask updates."""
    depth_data = {
        "contract_id": "MGC-H25",
        "data": [
            {"price": 2045.0, "volume": 10, "type": 2},  # Bid
            {"price": 2046.0, "volume": 15, "type": 1},  # Ask
            {"price": 2044.0, "volume": 5, "type": 2},  # Bid
            {"price": 2047.0, "volume": 20, "type": 1},  # Ask
        ],
    }

    await orderbook.process_market_depth(depth_data)

    # Check bid side
    assert len(orderbook.orderbook_bids) == 2
    assert 2045.0 in orderbook.orderbook_bids["price"].to_list()
    assert 2044.0 in orderbook.orderbook_bids["price"].to_list()

    # Check ask side
    assert len(orderbook.orderbook_asks) == 2
    assert 2046.0 in orderbook.orderbook_asks["price"].to_list()
    assert 2047.0 in orderbook.orderbook_asks["price"].to_list()

    # Check statistics
    assert orderbook.order_type_stats["type_1_count"] == 2  # Asks
    assert orderbook.order_type_stats["type_2_count"] == 2  # Bids


@pytest.mark.asyncio
async def test_process_market_depth_trade(orderbook):
    """Test processing market depth with trade updates."""
    # First set up some bid/ask levels
    depth_data = {
        "contract_id": "MGC-H25",
        "data": [
            {"price": 2045.0, "volume": 10, "type": 2},  # Bid
            {"price": 2046.0, "volume": 15, "type": 1},  # Ask
        ],
    }
    await orderbook.process_market_depth(depth_data)

    # Now process a trade
    trade_data = {
        "contract_id": "MGC-H25",
        "data": [
            {"price": 2045.5, "volume": 5, "type": 5},  # Trade
        ],
    }
    await orderbook.process_market_depth(trade_data)

    # Check trade was recorded
    assert len(orderbook.recent_trades) == 1
    trade = orderbook.recent_trades.to_dicts()[0]
    assert trade["price"] == 2045.5
    assert trade["volume"] == 5
    assert trade["side"] == "sell"  # Below mid price
    assert orderbook.order_type_stats["type_5_count"] == 1


@pytest.mark.asyncio
async def test_process_market_depth_reset(orderbook):
    """Test processing market depth reset."""
    # Add some data with proper schema
    orderbook.orderbook_bids = pl.DataFrame(
        {
            "price": [2045.0],
            "volume": [10],
            "timestamp": [datetime.now()],
            "type": ["bid"],
        },
        schema={
            "price": pl.Float64,
            "volume": pl.Int64,
            "timestamp": pl.Datetime("us"),
            "type": pl.Utf8,
        },
    )
    orderbook.orderbook_asks = pl.DataFrame(
        {
            "price": [2046.0],
            "volume": [15],
            "timestamp": [datetime.now()],
            "type": ["ask"],
        },
        schema={
            "price": pl.Float64,
            "volume": pl.Int64,
            "timestamp": pl.Datetime("us"),
            "type": pl.Utf8,
        },
    )

    # Process reset
    reset_data = {
        "contract_id": "MGC-H25",
        "data": [
            {"price": 0, "volume": 0, "type": 6},  # Reset
        ],
    }
    await orderbook.process_market_depth(reset_data)

    # Check orderbook was cleared
    assert len(orderbook.orderbook_bids) == 0
    assert len(orderbook.orderbook_asks) == 0
    assert orderbook.order_type_stats["type_6_count"] == 1


@pytest.mark.asyncio
async def test_get_orderbook_snapshot(orderbook):
    """Test getting orderbook snapshot."""
    # Set up orderbook data
    depth_data = {
        "contract_id": "MGC-H25",
        "data": [
            {"price": 2045.0, "volume": 10, "type": 2},  # Bid
            {"price": 2044.0, "volume": 5, "type": 2},  # Bid
            {"price": 2046.0, "volume": 15, "type": 1},  # Ask
            {"price": 2047.0, "volume": 20, "type": 1},  # Ask
        ],
    }
    await orderbook.process_market_depth(depth_data)

    snapshot = await orderbook.get_orderbook_snapshot(levels=5)

    assert snapshot["instrument"] == "MGC"
    assert snapshot["best_bid"] == 2045.0
    assert snapshot["best_ask"] == 2046.0
    assert snapshot["spread"] == 1.0
    assert snapshot["mid_price"] == 2045.5
    assert len(snapshot["bids"]) == 2
    assert len(snapshot["asks"]) == 2


@pytest.mark.asyncio
async def test_get_best_bid_ask(orderbook):
    """Test getting best bid and ask prices."""
    # Initially empty
    best_bid, best_ask = await orderbook.get_best_bid_ask()
    assert best_bid is None
    assert best_ask is None

    # Add some levels
    depth_data = {
        "contract_id": "MGC-H25",
        "data": [
            {"price": 2045.0, "volume": 10, "type": 2},  # Bid
            {"price": 2044.0, "volume": 5, "type": 2},  # Bid
            {"price": 2046.0, "volume": 15, "type": 1},  # Ask
            {"price": 2047.0, "volume": 20, "type": 1},  # Ask
        ],
    }
    await orderbook.process_market_depth(depth_data)

    best_bid, best_ask = await orderbook.get_best_bid_ask()
    assert best_bid == 2045.0  # Highest bid
    assert best_ask == 2046.0  # Lowest ask


@pytest.mark.asyncio
async def test_get_bid_ask_spread(orderbook):
    """Test getting bid-ask spread."""
    # Initially no spread
    spread = await orderbook.get_bid_ask_spread()
    assert spread is None

    # Add bid/ask
    depth_data = {
        "contract_id": "MGC-H25",
        "data": [
            {"price": 2045.0, "volume": 10, "type": 2},  # Bid
            {"price": 2046.0, "volume": 15, "type": 1},  # Ask
        ],
    }
    await orderbook.process_market_depth(depth_data)

    spread = await orderbook.get_bid_ask_spread()
    assert spread == 1.0


@pytest.mark.asyncio
async def test_detect_iceberg_orders(orderbook):
    """Test iceberg order detection."""
    # Simulate consistent volume refreshes at same price level
    orderbook.price_level_history[(2045.0, "bid")] = [
        {"volume": 100, "timestamp": datetime.now(orderbook.timezone)},
        {"volume": 95, "timestamp": datetime.now(orderbook.timezone)},
        {"volume": 105, "timestamp": datetime.now(orderbook.timezone)},
        {"volume": 100, "timestamp": datetime.now(orderbook.timezone)},
        {"volume": 98, "timestamp": datetime.now(orderbook.timezone)},
        {"volume": 102, "timestamp": datetime.now(orderbook.timezone)},
    ]

    # Detect icebergs
    result = await orderbook.detect_iceberg_orders(min_refreshes=5, volume_threshold=50)

    assert "iceberg_levels" in result
    assert len(result["iceberg_levels"]) > 0

    # Check first detected iceberg
    iceberg = result["iceberg_levels"][0]
    assert iceberg["price"] == 2045.0
    assert iceberg["side"] == "bid"
    assert iceberg["avg_volume"] == pytest.approx(100, rel=0.1)
    assert iceberg["confidence"] > 0.5


@pytest.mark.asyncio
async def test_symbol_matching(orderbook):
    """Test instrument symbol matching."""
    assert orderbook._symbol_matches_instrument("MGC-H25") is True
    assert orderbook._symbol_matches_instrument("MGC-M25") is True
    assert orderbook._symbol_matches_instrument("MNQ-H25") is False
    assert orderbook._symbol_matches_instrument("") is False


@pytest.mark.asyncio
async def test_callbacks(orderbook):
    """Test callback system."""
    callback_data = []

    async def test_callback(data):
        callback_data.append(data)

    await orderbook.add_callback("market_depth_processed", test_callback)

    # Process some data to trigger callback
    depth_data = {
        "contract_id": "MGC-H25",
        "data": [{"price": 2045.0, "volume": 10, "type": 2}],
    }

    # Simulate the callback trigger that would happen in _on_market_depth_update
    await orderbook.process_market_depth(depth_data)
    await orderbook._trigger_callbacks("market_depth_processed", {"test": "data"})

    assert len(callback_data) == 1
    assert callback_data[0]["test"] == "data"


@pytest.mark.asyncio
async def test_memory_cleanup(orderbook):
    """Test memory cleanup functionality."""
    # Add many trades to exceed limit
    for i in range(200):
        trade_data = {
            "contract_id": "MGC-H25",
            "data": [{"price": 2045.0 + i * 0.1, "volume": 10, "type": 5}],
        }
        await orderbook.process_market_depth(trade_data)

    # Force cleanup
    orderbook.max_trades = 100
    orderbook.last_cleanup = 0

    # Process one more to trigger cleanup
    await orderbook.process_market_depth(
        {"contract_id": "MGC-H25", "data": [{"price": 2050.0, "volume": 5, "type": 5}]}
    )

    # Should have trimmed to half of max_trades
    assert len(orderbook.recent_trades) <= 50


@pytest.mark.asyncio
async def test_quote_update_handling(orderbook):
    """Test handling of quote updates."""
    orderbook.realtime_client = MagicMock()

    quote_data = {
        "contractId": "MGC-H25",
        "bidPrice": 2045.0,
        "askPrice": 2046.0,
        "bidVolume": 10,
        "askVolume": 15,
    }

    await orderbook._on_quote_update(quote_data)

    # Check orderbook was updated
    assert len(orderbook.orderbook_bids) == 1
    assert len(orderbook.orderbook_asks) == 1
    assert orderbook.orderbook_bids["price"][0] == 2045.0
    assert orderbook.orderbook_asks["price"][0] == 2046.0


@pytest.mark.asyncio
async def test_get_memory_stats(orderbook):
    """Test getting memory statistics."""
    # Add some data
    depth_data = {
        "contract_id": "MGC-H25",
        "data": [
            {"price": 2045.0, "volume": 10, "type": 2},
            {"price": 2046.0, "volume": 15, "type": 1},
            {"price": 2045.5, "volume": 5, "type": 5},
        ],
    }
    await orderbook.process_market_depth(depth_data)

    stats = orderbook.get_memory_stats()

    assert stats["total_bid_levels"] == 1
    assert stats["total_ask_levels"] == 1
    assert stats["total_trades"] == 1
    assert stats["update_count"] == 1
    assert "last_cleanup" in stats


@pytest.mark.asyncio
async def test_clear_orderbook(orderbook):
    """Test clearing orderbook data."""
    # Add some data with proper schemas
    orderbook.orderbook_bids = pl.DataFrame(
        {
            "price": [2045.0],
            "volume": [10],
            "timestamp": [datetime.now()],
            "type": ["bid"],
        },
        schema={
            "price": pl.Float64,
            "volume": pl.Int64,
            "timestamp": pl.Datetime("us"),
            "type": pl.Utf8,
        },
    )
    orderbook.orderbook_asks = pl.DataFrame(
        {
            "price": [2046.0],
            "volume": [15],
            "timestamp": [datetime.now()],
            "type": ["ask"],
        },
        schema={
            "price": pl.Float64,
            "volume": pl.Int64,
            "timestamp": pl.Datetime("us"),
            "type": pl.Utf8,
        },
    )
    orderbook.recent_trades = pl.DataFrame(
        {
            "price": [2045.5],
            "volume": [5],
            "timestamp": [datetime.now()],
            "side": ["buy"],
            "spread_at_trade": [1.0],
            "mid_price_at_trade": [2045.5],
            "best_bid_at_trade": [2045.0],
            "best_ask_at_trade": [2046.0],
            "order_type": ["Trade"],
        },
        schema={
            "price": pl.Float64,
            "volume": pl.Int64,
            "timestamp": pl.Datetime("us"),
            "side": pl.Utf8,
            "spread_at_trade": pl.Float64,
            "mid_price_at_trade": pl.Float64,
            "best_bid_at_trade": pl.Float64,
            "best_ask_at_trade": pl.Float64,
            "order_type": pl.Utf8,
        },
    )
    orderbook.level2_update_count = 10

    await orderbook.clear_orderbook()

    assert len(orderbook.orderbook_bids) == 0
    assert len(orderbook.orderbook_asks) == 0
    assert len(orderbook.recent_trades) == 0
    assert orderbook.level2_update_count == 0
    assert all(v == 0 for v in orderbook.order_type_stats.values())


@pytest.mark.asyncio
async def test_cleanup(orderbook):
    """Test cleanup method."""
    # Add some data and callbacks
    orderbook.orderbook_bids = pl.DataFrame({"price": [2045.0], "volume": [10]})
    orderbook.callbacks["test"] = [lambda x: None]

    await orderbook.cleanup()

    assert len(orderbook.orderbook_bids) == 0
    assert len(orderbook.callbacks) == 0
