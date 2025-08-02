"""Tests for AsyncRealtimeDataManager."""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import polars as pl
import pytest
import pytz

from project_x_py import ProjectX, ProjectXRealtimeClient
AsyncProjectX = ProjectX
AsyncProjectXRealtimeClient = ProjectXRealtimeClient
from project_x_py.models import Instrument
from project_x_py.realtime_data_manager import RealtimeDataManager


def mock_instrument(id="MGC-123", name="MGC"):
    """Helper to create a mock instrument."""
    mock = MagicMock(spec=Instrument)
    mock.id = id
    mock.name = name
    mock.tickSize = 0.1
    mock.tickValue = 10.0
    mock.pointValue = 10.0
    mock.currency = "USD"
    mock.contractMultiplier = 10.0
    mock.mainExchange = "CME"
    mock.type = 1
    mock.sector = "Commodities"
    mock.subsector = "Metals"
    mock.activeContract = id
    mock.nearContract = id
    mock.farContract = id
    mock.expirationDates = []
    return mock


@pytest.fixture
def mock_async_client():
    """Create a mock AsyncProjectX client."""
    client = MagicMock(spec=ProjectX)
    client.get_instrument = AsyncMock()
    client.get_bars = AsyncMock()
    return client


@pytest.fixture
def mock_realtime_client():
    """Create a mock AsyncProjectXRealtimeClient."""
    client = MagicMock()
    client.subscribe_market_data = AsyncMock(return_value=True)
    client.unsubscribe_market_data = AsyncMock()
    client.add_callback = AsyncMock()
    return client


@pytest.fixture
def data_manager(mock_async_client, mock_realtime_client):
    """Create an AsyncRealtimeDataManager instance."""
    return RealtimeDataManager(
        instrument="MGC",
        project_x=mock_async_client,
        realtime_client=mock_realtime_client,
        timeframes=["1min", "5min"],
    )


@pytest.mark.asyncio
async def test_data_manager_initialization(mock_async_client, mock_realtime_client):
    """Test AsyncRealtimeDataManager initialization."""
    manager = RealtimeDataManager(
        instrument="MGC",
        project_x=mock_async_client,
        realtime_client=mock_realtime_client,
        timeframes=["1min", "5min", "15min"],
    )

    assert manager.instrument == "MGC"
    assert manager.project_x == mock_async_client
    assert manager.realtime_client == mock_realtime_client
    assert len(manager.timeframes) == 3
    assert "1min" in manager.timeframes
    assert "5min" in manager.timeframes
    assert "15min" in manager.timeframes
    assert isinstance(manager.data_lock, asyncio.Lock)


@pytest.mark.asyncio
async def test_initialize_success(data_manager, mock_async_client):
    """Test successful initialization with historical data loading."""
    # Mock instrument lookup
    mock_async_client.get_instrument.return_value = mock_instrument("MGC-123", "MGC")

    # Mock historical data
    mock_bars = pl.DataFrame(
        {
            "timestamp": [datetime.now()] * 10,
            "open": [2045.0] * 10,
            "high": [2050.0] * 10,
            "low": [2040.0] * 10,
            "close": [2048.0] * 10,
            "volume": [100] * 10,
        }
    )
    mock_async_client.get_bars.return_value = mock_bars

    result = await data_manager.initialize(initial_days=1)

    assert result is True
    assert data_manager.contract_id == "MGC-123"
    assert "1min" in data_manager.data
    assert "5min" in data_manager.data
    assert len(data_manager.data["1min"]) == 10
    assert len(data_manager.data["5min"]) == 10


@pytest.mark.asyncio
async def test_initialize_instrument_not_found(data_manager, mock_async_client):
    """Test initialization when instrument is not found."""
    mock_async_client.get_instrument.return_value = None

    result = await data_manager.initialize(initial_days=1)

    assert result is False
    assert data_manager.contract_id is None


@pytest.mark.asyncio
async def test_start_realtime_feed(data_manager, mock_realtime_client):
    """Test starting real-time feed."""
    data_manager.contract_id = "MGC-123"

    result = await data_manager.start_realtime_feed()

    assert result is True
    assert data_manager.is_running is True
    # Note: subscribe_market_data is not called because it's not implemented yet
    assert mock_realtime_client.add_callback.call_count == 2  # quote and trade


@pytest.mark.asyncio
async def test_stop_realtime_feed(data_manager, mock_realtime_client):
    """Test stopping real-time feed."""
    data_manager.contract_id = "MGC-123"
    data_manager.is_running = True

    await data_manager.stop_realtime_feed()

    assert data_manager.is_running is False
    # Note: unsubscribe_market_data is not called because it's not implemented yet


@pytest.mark.asyncio
async def test_process_quote_update(data_manager):
    """Test processing quote updates."""
    data_manager.contract_id = "MGC-123"
    data_manager.data["1min"] = pl.DataFrame()

    quote_data = {
        "contractId": "MGC-123",
        "bidPrice": 2045.0,
        "askPrice": 2046.0,
    }

    await data_manager._on_quote_update(quote_data)

    assert len(data_manager.current_tick_data) == 1
    assert data_manager.current_tick_data[0]["price"] == 2045.5  # Mid price
    assert data_manager.memory_stats["ticks_processed"] == 1


@pytest.mark.asyncio
async def test_process_trade_update(data_manager):
    """Test processing trade updates."""
    data_manager.contract_id = "MGC-123"
    data_manager.data["1min"] = pl.DataFrame()

    trade_data = {
        "contractId": "MGC-123",
        "price": 2045.5,
        "size": 10,
    }

    await data_manager._on_trade_update(trade_data)

    assert len(data_manager.current_tick_data) == 1
    assert data_manager.current_tick_data[0]["price"] == 2045.5
    assert data_manager.current_tick_data[0]["volume"] == 10
    assert data_manager.memory_stats["ticks_processed"] == 1


@pytest.mark.asyncio
async def test_get_data(data_manager):
    """Test getting OHLCV data for a timeframe."""
    test_data = pl.DataFrame(
        {
            "timestamp": [datetime.now()] * 5,
            "open": [2045.0] * 5,
            "high": [2050.0] * 5,
            "low": [2040.0] * 5,
            "close": [2048.0] * 5,
            "volume": [100] * 5,
        }
    )
    data_manager.data["5min"] = test_data

    # Get all data
    result = await data_manager.get_data("5min")
    assert result is not None
    assert len(result) == 5

    # Get limited bars
    result = await data_manager.get_data("5min", bars=3)
    assert result is not None
    assert len(result) == 3


@pytest.mark.asyncio
async def test_get_current_price_from_ticks(data_manager):
    """Test getting current price from tick data."""
    data_manager.current_tick_data = [
        {"price": 2045.0},
        {"price": 2046.0},
        {"price": 2047.0},
    ]

    price = await data_manager.get_current_price()
    assert price == 2047.0


@pytest.mark.asyncio
async def test_get_current_price_from_bars(data_manager):
    """Test getting current price from bar data when no ticks."""
    data_manager.current_tick_data = []
    data_manager.data["1min"] = pl.DataFrame(
        {
            "timestamp": [datetime.now()],
            "open": [2045.0],
            "high": [2050.0],
            "low": [2040.0],
            "close": [2048.0],
            "volume": [100],
        }
    )

    price = await data_manager.get_current_price()
    assert price == 2048.0


@pytest.mark.asyncio
async def test_get_mtf_data(data_manager):
    """Test getting multi-timeframe data."""
    data_1min = pl.DataFrame({"close": [2045.0]})
    data_5min = pl.DataFrame({"close": [2046.0]})
    data_manager.data = {"1min": data_1min, "5min": data_5min}

    mtf_data = await data_manager.get_mtf_data()

    assert len(mtf_data) == 2
    assert "1min" in mtf_data
    assert "5min" in mtf_data
    assert mtf_data["1min"]["close"][0] == 2045.0
    assert mtf_data["5min"]["close"][0] == 2046.0


@pytest.mark.asyncio
async def test_memory_cleanup(data_manager):
    """Test memory cleanup functionality."""
    # Set up data that exceeds limits
    large_data = pl.DataFrame(
        {
            "timestamp": [datetime.now()] * 2000,
            "open": [2045.0] * 2000,
            "high": [2050.0] * 2000,
            "low": [2040.0] * 2000,
            "close": [2048.0] * 2000,
            "volume": [100] * 2000,
        }
    )
    data_manager.data["1min"] = large_data
    data_manager.last_cleanup = 0  # Force cleanup

    await data_manager._cleanup_old_data()

    # Should keep only half of max_bars_per_timeframe
    assert len(data_manager.data["1min"]) == 500


@pytest.mark.asyncio
async def test_calculate_bar_time(data_manager):
    """Test bar time calculation for different timeframes."""
    tz = pytz.timezone("America/Chicago")
    test_time = datetime(2024, 1, 1, 12, 34, 56, tzinfo=tz)

    # Test 1 minute bars
    bar_time = data_manager._calculate_bar_time(test_time, {"interval": 1, "unit": 2})
    assert bar_time.minute == 34
    assert bar_time.second == 0

    # Test 5 minute bars
    bar_time = data_manager._calculate_bar_time(test_time, {"interval": 5, "unit": 2})
    assert bar_time.minute == 30
    assert bar_time.second == 0

    # Test 15 second bars
    bar_time = data_manager._calculate_bar_time(test_time, {"interval": 15, "unit": 1})
    assert bar_time.second == 45


@pytest.mark.asyncio
async def test_callback_system(data_manager):
    """Test callback registration and triggering."""
    callback_data = []

    async def test_callback(data):
        callback_data.append(data)

    await data_manager.add_callback("test_event", test_callback)
    await data_manager._trigger_callbacks("test_event", {"test": "data"})

    assert len(callback_data) == 1
    assert callback_data[0]["test"] == "data"


@pytest.mark.asyncio
async def test_validation_status(data_manager):
    """Test getting validation status."""
    data_manager.is_running = True
    data_manager.contract_id = "MGC-123"
    data_manager.memory_stats["ticks_processed"] = 100

    status = data_manager.get_realtime_validation_status()

    assert status["is_running"] is True
    assert status["contract_id"] == "MGC-123"
    assert status["instrument"] == "MGC"
    assert status["ticks_processed"] == 100
    assert "projectx_compliance" in status


@pytest.mark.asyncio
async def test_cleanup(data_manager):
    """Test cleanup method."""
    data_manager.is_running = True
    data_manager.data = {"1min": pl.DataFrame({"close": [2045.0]})}
    data_manager.current_tick_data = [{"price": 2045.0}]

    await data_manager.cleanup()

    assert data_manager.is_running is False
    assert len(data_manager.data) == 0
    assert len(data_manager.current_tick_data) == 0
