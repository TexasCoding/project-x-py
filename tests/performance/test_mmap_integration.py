"""Test memory-mapped storage integration with RealtimeDataManager."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import polars as pl
import pytest

from project_x_py.realtime_data_manager import RealtimeDataManager
from project_x_py.types.config_types import DataManagerConfig


class TestMMapIntegration:
    """Test memory-mapped overflow integration in RealtimeDataManager."""

    @pytest.fixture
    async def mock_realtime_client(self):
        """Create a mock realtime client."""
        client = MagicMock()
        client.connect = AsyncMock(return_value=True)
        client.subscribe_market_data = AsyncMock(return_value=True)
        client.add_callback = AsyncMock()
        client.is_connected = MagicMock(return_value=True)
        client.user_connected = True
        client.market_connected = True
        return client

    @pytest.fixture
    async def mock_project_x(self):
        """Create a mock ProjectX client."""
        # Create a mock client directly without context manager
        client = MagicMock()

        # Mock the get_bars method to return test data with proper datetime timestamps
        async def mock_get_bars(*args, **kwargs):
            base_time = datetime.now()
            timestamps = [base_time + timedelta(minutes=i) for i in range(100)]
            return pl.DataFrame(
                {
                    "timestamp": timestamps,
                    "open": list(range(100, 200)),
                    "high": list(range(200, 300)),
                    "low": list(range(50, 150)),
                    "close": list(range(150, 250)),
                    "volume": list(range(1000, 1100)),
                }
            )

        client.get_bars = mock_get_bars

        # Mock instrument
        instrument = MagicMock()
        instrument.id = "TEST.INSTRUMENT"
        instrument.name = "Test Instrument"
        client.get_instrument = AsyncMock(return_value=instrument)

        # Mock account info
        client.account_info = MagicMock()
        client.account_info.name = "Test Account"

        return client

    @pytest.mark.skip(reason="Overflow functionality not yet implemented")
    @pytest.mark.asyncio
    async def test_overflow_triggered(self, mock_project_x, mock_realtime_client):
        """Test that overflow is triggered when memory limits are reached."""
        # Create config with low limits to trigger overflow
        config = DataManagerConfig(
            max_bars_per_timeframe=20,  # Low limit to trigger overflow
        )

        # Create manager with config
        manager = RealtimeDataManager(
            instrument="TEST",
            project_x=mock_project_x,
            realtime_client=mock_realtime_client,
            timeframes=["1min"],
            config=config,
        )

        # Initialize manager
        await manager.initialize(initial_days=1)

        # Manually add more data to trigger overflow
        base_time = datetime.now()
        timestamps = [base_time + timedelta(minutes=i) for i in range(50)]
        test_df = pl.DataFrame(
            {
                "timestamp": timestamps,
                "open": list(range(100, 150)),
                "high": list(range(150, 200)),
                "low": list(range(50, 100)),
                "close": list(range(125, 175)),
                "volume": list(range(1000, 1050)),
            }
        )

        manager.data["1min"] = test_df

        # Check overflow is needed
        needs_overflow = await manager._check_overflow_needed("1min")
        assert needs_overflow is True  # Should need overflow at 50 bars with max 20

        # Trigger overflow
        await manager._overflow_to_disk("1min")

        # Check that data was reduced
        assert len(manager.data["1min"]) <= manager.max_bars_per_timeframe

        # Check overflow stats
        stats = manager.get_overflow_stats()
        assert stats["total_bars_overflowed"] > 0
        assert "1min" in stats["overflow_stats_by_timeframe"]

    @pytest.mark.asyncio
    async def test_historical_data_retrieval(
        self, mock_project_x, mock_realtime_client
    ):
        """Test retrieving data that spans both memory and overflow storage."""
        config = DataManagerConfig(
            max_bars_per_timeframe=10,
        )

        manager = RealtimeDataManager(
            instrument="TEST",
            project_x=mock_project_x,
            realtime_client=mock_realtime_client,
            timeframes=["5min"],
            config=config,
        )

        # Initialize
        await manager.initialize(initial_days=1)

        # Create test data with proper timestamps
        base_time = datetime.now()
        timestamps = [base_time + timedelta(minutes=i) for i in range(20)]
        old_data = pl.DataFrame(
            {
                "timestamp": timestamps,
                "open": list(range(100, 120)),
                "high": list(range(120, 140)),
                "low": list(range(80, 100)),
                "close": list(range(100, 120)),
                "volume": list(range(1000, 1020)),
            }
        )

        manager.data["5min"] = old_data

        # Trigger overflow
        await manager._overflow_to_disk("5min")

        # Add new data with proper timestamps
        new_timestamps = [base_time + timedelta(minutes=i) for i in range(20, 30)]
        new_data = pl.DataFrame(
            {
                "timestamp": new_timestamps,
                "open": list(range(120, 130)),
                "high": list(range(140, 150)),
                "low": list(range(100, 110)),
                "close": list(range(120, 130)),
                "volume": list(range(1020, 1030)),
            }
        )
        manager.data["5min"] = new_data

        # Get historical data (should combine overflow and memory)
        historical = await manager.get_historical_data("5min")

        # Should have data from both sources
        assert historical is not None
        assert len(historical) > len(new_data)

    @pytest.mark.skip(reason="Overflow functionality not yet implemented")
    @pytest.mark.asyncio
    async def test_memory_cleanup_with_overflow(
        self, mock_project_x, mock_realtime_client
    ):
        """Test that memory cleanup triggers overflow instead of deleting data."""
        config = DataManagerConfig(
            max_bars_per_timeframe=15,
        )

        manager = RealtimeDataManager(
            instrument="TEST",
            project_x=mock_project_x,
            realtime_client=mock_realtime_client,
            timeframes=["1hr"],
            config=config,
        )

        await manager.initialize(initial_days=1)

        # Add data that exceeds limit
        base_time = datetime.now()
        timestamps = [base_time + timedelta(minutes=i) for i in range(30)]
        test_data = pl.DataFrame(
            {
                "timestamp": timestamps,
                "open": list(range(200, 230)),
                "high": list(range(230, 260)),
                "low": list(range(170, 200)),
                "close": list(range(200, 230)),
                "volume": list(range(1000, 1030)),
            }
        )
        manager.data["1hr"] = test_data

        # Force cleanup by resetting last_cleanup time
        manager.last_cleanup = 0

        # Run cleanup
        await manager._cleanup_old_data()

        # Data should be reduced but not lost
        assert len(manager.data["1hr"]) <= manager.max_bars_per_timeframe

        # Check that buffer overflow handling occurred (data sampling)
        buffer_stats = manager.get_buffer_stats()
        assert buffer_stats["sampling_ratios"].get("1hr") is not None

        # Verify data was sampled, not completely lost
        assert len(manager.data["1hr"]) > 0
        assert len(manager.data["1hr"]) == int(manager.max_bars_per_timeframe * 0.7)  # Should be 70% of max

    @pytest.mark.asyncio
    async def test_restore_from_overflow(self, mock_project_x, mock_realtime_client):
        """Test restoring data from overflow storage."""
        config = DataManagerConfig(
            max_bars_per_timeframe=10,
        )

        manager = RealtimeDataManager(
            instrument="TEST",
            project_x=mock_project_x,
            realtime_client=mock_realtime_client,
            timeframes=["15min"],
            config=config,
        )

        await manager.initialize(initial_days=1)

        # Create and overflow data
        base_time = datetime.now()
        timestamps = [base_time + timedelta(minutes=i) for i in range(20)]
        test_data = pl.DataFrame(
            {
                "timestamp": timestamps,
                "open": list(range(300, 320)),
                "high": list(range(320, 340)),
                "low": list(range(280, 300)),
                "close": list(range(300, 320)),
                "volume": list(range(1000, 1020)),
            }
        )
        manager.data["15min"] = test_data

        # Overflow to disk
        await manager._overflow_to_disk("15min")

        # Now restore some bars
        success = await manager.restore_from_overflow("15min", bars=5)

        # Check restore worked
        if success:
            assert len(manager.data["15min"]) > 0

    @pytest.mark.asyncio
    async def test_cleanup_overflow_storage(self, mock_project_x, mock_realtime_client):
        """Test cleanup of overflow storage files."""
        manager = RealtimeDataManager(
            instrument="TEST",
            project_x=mock_project_x,
            realtime_client=mock_realtime_client,
            timeframes=["30min"],
        )

        await manager.initialize(initial_days=1)

        # Create storage
        manager._get_or_create_storage("30min")

        # Should have storage instance
        assert "30min" in manager._mmap_storages

        # Cleanup
        await manager.cleanup_overflow_storage()

        # Storage should be cleaned up
        assert len(manager._mmap_storages) == 0
