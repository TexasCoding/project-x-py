"""
Shared test fixtures for realtime_data_manager test suite.

Provides common mocks and fixtures used across multiple test files.
Follows the proven testing patterns from other successful modules.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock
from decimal import Decimal
from datetime import datetime, timezone
import polars as pl

from project_x_py.models import Instrument
from project_x_py.event_bus import EventBus
from project_x_py.types.config_types import DataManagerConfig


@pytest.fixture
def sample_instrument():
    """Standard test instrument for all realtime_data_manager tests."""
    return Instrument(
        id="CON.F.US.MNQ.U25",
        name="MNQU25",
        description="Micro E-mini Nasdaq-100",
        tickSize=0.25,
        tickValue=0.50,
        activeContract=True,
        symbolId="MNQ"
    )


@pytest.fixture
def sample_bars_data():
    """Sample OHLCV bar data for testing."""
    return pl.DataFrame({
        "timestamp": [
            datetime(2025, 1, 1, 9, 30),
            datetime(2025, 1, 1, 9, 31),
            datetime(2025, 1, 1, 9, 32),
            datetime(2025, 1, 1, 9, 33),
            datetime(2025, 1, 1, 9, 34),
        ],
        "open": [19000.0, 19005.0, 19002.0, 19008.0, 19006.0],
        "high": [19010.0, 19012.0, 19015.0, 19020.0, 19018.0],
        "low": [18995.0, 18998.0, 18985.0, 19000.0, 18990.0],
        "close": [19005.0, 19002.0, 19008.0, 19006.0, 19012.0],
        "volume": [1500, 1200, 1800, 1600, 1400]
    })


@pytest.fixture
def sample_tick_data():
    """Sample tick data for testing data processing."""
    return [
        {
            "timestamp": datetime(2025, 1, 1, 9, 30, 0),
            "price": Decimal("19000.50"),
            "volume": 100,
            "side": "buy"
        },
        {
            "timestamp": datetime(2025, 1, 1, 9, 30, 15),
            "price": Decimal("19001.00"),
            "volume": 150,
            "side": "sell"
        },
        {
            "timestamp": datetime(2025, 1, 1, 9, 30, 30),
            "price": Decimal("19000.75"),
            "volume": 200,
            "side": "buy"
        }
    ]


@pytest.fixture
def mock_project_x_client(sample_instrument, sample_bars_data):
    """Mock ProjectX client with realistic responses."""
    mock = AsyncMock()

    # Mock instrument lookup
    mock.get_instrument.return_value = sample_instrument

    # Mock historical bars
    mock.get_bars.return_value = sample_bars_data

    # Mock other methods as needed
    mock.authenticate.return_value = True
    mock.is_authenticated.return_value = True

    return mock


@pytest.fixture
def mock_realtime_client():
    """Mock realtime client for WebSocket operations."""
    mock = AsyncMock()

    # Connection state
    mock.is_connected.return_value = True
    mock.connect.return_value = True
    mock.disconnect.return_value = True

    # Subscription methods
    mock.subscribe_to_quotes.return_value = True
    mock.subscribe_to_trades.return_value = True
    mock.unsubscribe_from_quotes.return_value = True
    mock.unsubscribe_from_trades.return_value = True

    # Callback registration
    mock.add_quote_callback = Mock()
    mock.add_trade_callback = Mock()
    mock.remove_quote_callback = Mock()
    mock.remove_trade_callback = Mock()

    return mock


@pytest.fixture
def mock_event_bus():
    """Mock event bus for event system integration."""
    mock = AsyncMock(spec=EventBus)
    mock.emit = AsyncMock()
    mock.on = AsyncMock()
    mock.off = AsyncMock()
    return mock


@pytest.fixture
def default_config():
    """Default DataManagerConfig for testing."""
    return DataManagerConfig(
        max_bars_per_timeframe=1000,
        tick_buffer_size=1000,
        timezone="America/Chicago",
        initial_days=5,
        cleanup_interval=60,
        max_memory_mb=100
    )


@pytest.fixture
def common_timeframes():
    """Standard timeframes used in testing."""
    return ["1min", "5min", "15min", "1hr"]


@pytest.fixture
def realtime_data_manager_setup(mock_project_x_client, mock_realtime_client, mock_event_bus, sample_instrument, default_config):
    """Complete setup for RealtimeDataManager testing."""
    from project_x_py.realtime_data_manager.core import RealtimeDataManager

    def create_manager(instrument=None, timeframes=None, config=None):
        return RealtimeDataManager(
            instrument=instrument or sample_instrument,
            project_x=mock_project_x_client,
            realtime_client=mock_realtime_client,
            event_bus=mock_event_bus,
            timeframes=timeframes or ["1min", "5min"],
            config=config or default_config
        )

    return {
        'create_manager': create_manager,
        'project_x': mock_project_x_client,
        'realtime_client': mock_realtime_client,
        'event_bus': mock_event_bus,
        'instrument': sample_instrument,
        'config': default_config
    }


@pytest.fixture(scope="function")
async def initialized_manager(realtime_data_manager_setup):
    """Pre-initialized RealtimeDataManager for testing."""
    manager = realtime_data_manager_setup['create_manager']()
    await manager.initialize(initial_days=5)

    # Cleanup after test
    yield manager

    try:
        await manager.cleanup()
    except Exception:
        pass  # Ignore cleanup errors in tests


@pytest.fixture(scope="function")
async def running_manager(initialized_manager):
    """Running RealtimeDataManager with active realtime feed."""
    await initialized_manager.start_realtime_feed()

    yield initialized_manager

    try:
        await initialized_manager.stop_realtime_feed()
    except Exception:
        pass  # Ignore cleanup errors in tests


# Assertion helpers for common test patterns
def assert_valid_ohlcv_data(dataframe):
    """Assert that DataFrame contains valid OHLCV data structure."""
    assert isinstance(dataframe, pl.DataFrame)
    required_columns = {"timestamp", "open", "high", "low", "close", "volume"}
    assert required_columns.issubset(set(dataframe.columns))
    assert len(dataframe) > 0


def assert_valid_statistics(stats_dict):
    """Assert that statistics dictionary has expected structure."""
    assert isinstance(stats_dict, dict)
    # Common statistics keys that should be present
    expected_keys = {
        'ticks_processed', 'bars_created', 'callbacks_executed',
        'uptime_seconds', 'last_update'
    }
    # At least some should be present (implementation may vary)
    assert len(set(stats_dict.keys()) & expected_keys) > 0


def assert_health_score_valid(health_score):
    """Assert that health score is in valid range."""
    assert isinstance(health_score, (int, float))
    assert 0 <= health_score <= 100
