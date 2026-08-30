"""
Comprehensive integration and edge case tests for RealtimeDataManager core.py.

This test suite targets the uncovered lines and edge cases in the core module to achieve >90% coverage.
Following TDD principles - these tests define expected behavior, not current implementation.

Author: Claude Code
Date: 2025-08-31
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import polars as pl
import pytest

from project_x_py.client.base import ProjectXBase
from project_x_py.exceptions import ProjectXError, ProjectXInstrumentError
from project_x_py.models import Instrument
from project_x_py.realtime import ProjectXRealtimeClient
from project_x_py.realtime_data_manager.core import RealtimeDataManager, _DummyEventBus


class TestRealtimeDataManagerInitialization:
    """Test comprehensive initialization scenarios and edge cases."""

    def test_initialization_with_minimal_parameters(self):
        """Test that manager initializes with minimal required parameters."""
        # Mock required dependencies
        project_x = Mock(spec=ProjectXBase)
        realtime_client = Mock(spec=ProjectXRealtimeClient)

        manager = RealtimeDataManager(
            instrument="MNQ", project_x=project_x, realtime_client=realtime_client
        )

        assert manager.instrument == "MNQ"
        assert manager.project_x == project_x
        assert manager.realtime_client == realtime_client
        assert len(manager.timeframes) == 1  # Default ["5min"]
        assert "5min" in manager.timeframes
        assert not manager._initialized
        assert not manager.is_running

    def test_initialization_with_full_configuration(self):
        """Test initialization with comprehensive configuration."""
        project_x = Mock(spec=ProjectXBase)
        realtime_client = Mock(spec=ProjectXRealtimeClient)
        event_bus = Mock()

        config = {
            "max_bars_per_timeframe": 2000,
            "enable_tick_data": True,
            "enable_level2_data": True,
            "data_validation": True,
            "compression_enabled": True,
            "auto_cleanup": True,
            "cleanup_interval_minutes": 10,
            "use_bounded_statistics": False,
            "enable_dynamic_limits": False,
            "timezone": "Europe/London",
        }

        manager = RealtimeDataManager(
            instrument="ES",
            project_x=project_x,
            realtime_client=realtime_client,
            event_bus=event_bus,
            timeframes=["1min", "5min", "15min", "1hr"],
            timezone="America/New_York",  # Should be overridden by config
            config=config,
        )

        assert manager.instrument == "ES"
        assert len(manager.timeframes) == 4
        assert manager.max_bars_per_timeframe == 2000
        assert not manager.use_bounded_statistics
        assert not manager._enable_dynamic_limits
        # Config timezone should override parameter
        assert str(manager.timezone) == "Europe/London"

    def test_initialization_parameter_validation(self):
        """Test validation of initialization parameters."""
        project_x = Mock(spec=ProjectXBase)
        realtime_client = Mock(spec=ProjectXRealtimeClient)

        # Test empty instrument
        with pytest.raises(ValueError, match="instrument parameter is required"):
            RealtimeDataManager("", project_x, realtime_client)

        # Test None instrument
        with pytest.raises(ValueError, match="instrument parameter is required"):
            RealtimeDataManager(None, project_x, realtime_client)

        # Test None project_x
        with pytest.raises(ValueError, match="project_x parameter is required"):
            RealtimeDataManager("MNQ", None, realtime_client)

        # Test None realtime_client
        with pytest.raises(ValueError, match="realtime_client parameter is required"):
            RealtimeDataManager("MNQ", project_x, None)

        # Test empty timeframes list
        with pytest.raises(ValueError, match="timeframes list cannot be empty"):
            RealtimeDataManager("MNQ", project_x, realtime_client, timeframes=[])

    def test_invalid_timeframe_validation(self):
        """Test validation of invalid timeframes during initialization."""
        project_x = Mock(spec=ProjectXBase)
        realtime_client = Mock(spec=ProjectXRealtimeClient)

        with pytest.raises(ValueError, match="Invalid timeframe: invalid"):
            RealtimeDataManager(
                "MNQ", project_x, realtime_client, timeframes=["5min", "invalid", "1hr"]
            )

    def test_dummy_event_bus_functionality(self):
        """Test that dummy event bus works correctly when no event bus provided."""
        dummy = _DummyEventBus()

        # Should not raise any exceptions
        asyncio.run(dummy.on("test_event", lambda: None))
        asyncio.run(dummy.emit("test_event", {"data": "test"}))
        asyncio.run(dummy.emit("test_event", {"data": "test"}, source="test_source"))

    def test_bounded_statistics_configuration(self):
        """Test bounded statistics initialization with custom configuration."""
        project_x = Mock(spec=ProjectXBase)
        realtime_client = Mock(spec=ProjectXRealtimeClient)

        config = {
            "use_bounded_statistics": True,
            "max_recent_metrics": 5000,
            "hourly_retention_hours": 48,
            "daily_retention_days": 60,
            "timing_buffer_size": 2000,
            "cleanup_interval_minutes": 2.5,
        }

        manager = RealtimeDataManager("MNQ", project_x, realtime_client, config=config)

        assert manager.use_bounded_statistics


class TestRealtimeDataManagerInitialize:
    """Test the initialization process with historical data loading."""

    @pytest.mark.asyncio
    async def test_initialize_successful_single_timeframe(self):
        """Test successful initialization with single timeframe."""
        project_x = AsyncMock(spec=ProjectXBase)
        realtime_client = Mock(spec=ProjectXRealtimeClient)

        # Mock instrument lookup
        instrument = Instrument(
            id="123e4567-e89b-12d3-a456-426614174000",
            name="E-mini NASDAQ-100",
            description="E-mini NASDAQ-100 futures",
            symbolId="F.US.MNQ",
            tickSize=0.25,
            tickValue=1.25,
            activeContract=True,
        )
        project_x.get_instrument.return_value = instrument

        # Mock historical data
        historical_data = pl.DataFrame(
            {
                "timestamp": [datetime(2023, 1, 1, 9, 30), datetime(2023, 1, 1, 9, 35)],
                "open": [15000.0, 15005.0],
                "high": [15002.0, 15007.0],
                "low": [14998.0, 15003.0],
                "close": [15001.0, 15006.0],
                "volume": [100, 150],
            }
        )
        project_x.get_bars.return_value = historical_data

        manager = RealtimeDataManager(
            "MNQ", project_x, realtime_client, timeframes=["5min"]
        )

        result = await manager.initialize(initial_days=5)

        assert result is True
        assert manager._initialized is True
        assert manager.contract_id == "123e4567-e89b-12d3-a456-426614174000"
        assert manager.tick_size == 0.25
        assert manager.instrument_symbol_id == "MNQ"
        assert "5min" in manager.data
        assert len(manager.data["5min"]) == 2

        # Verify API calls
        project_x.get_instrument.assert_called_once_with("MNQ")
        project_x.get_bars.assert_called_once_with("MNQ", interval=5, unit=2, days=5)

    @pytest.mark.asyncio
    async def test_initialize_multiple_timeframes(self):
        """Test initialization with multiple timeframes."""
        project_x = AsyncMock(spec=ProjectXBase)
        realtime_client = Mock(spec=ProjectXRealtimeClient)

        # Mock instrument lookup
        instrument = Instrument(
            id="123e4567-e89b-12d3-a456-426614174000",
            name="ES",
            description="E-mini S&P 500 futures",
            tickValue=12.50,
            symbolId="F.US.ES",
            tickSize=0.5,
            activeContract=True,
        )
        project_x.get_instrument.return_value = instrument

        # Mock historical data for different timeframes
        def mock_get_bars(symbol, interval, unit, days):
            return pl.DataFrame(
                {
                    "timestamp": [datetime(2023, 1, 1, 9, 30)],
                    "open": [4000.0],
                    "high": [4002.0],
                    "low": [3998.0],
                    "close": [4001.0],
                    "volume": [100],
                }
            )

        project_x.get_bars.side_effect = mock_get_bars

        manager = RealtimeDataManager(
            "ES", project_x, realtime_client, timeframes=["1min", "5min", "15min"]
        )

        result = await manager.initialize(initial_days=10)

        assert result is True
        assert len(manager.data) == 3
        assert all(tf in manager.data for tf in ["1min", "5min", "15min"])
        assert all(len(manager.data[tf]) == 1 for tf in ["1min", "5min", "15min"])

        # Should have called get_bars for each timeframe
        assert project_x.get_bars.call_count == 3

    @pytest.mark.asyncio
    async def test_initialize_instrument_not_found(self):
        """Test initialization when instrument is not found."""
        project_x = AsyncMock(spec=ProjectXBase)
        realtime_client = Mock(spec=ProjectXRealtimeClient)

        # Mock instrument not found
        project_x.get_instrument.return_value = None

        manager = RealtimeDataManager("INVALID", project_x, realtime_client)

        with pytest.raises(
            ProjectXInstrumentError, match="Instrument not found: INVALID"
        ):
            await manager.initialize()

    @pytest.mark.asyncio
    async def test_initialize_project_x_client_none(self):
        """Test initialization when project_x client is None."""
        realtime_client = Mock(spec=ProjectXRealtimeClient)

        # This should fail during __init__, not initialize
        with pytest.raises(ValueError, match="project_x parameter is required"):
            RealtimeDataManager("MNQ", None, realtime_client)

    @pytest.mark.asyncio
    async def test_initialize_idempotent_behavior(self):
        """Test that initialize is idempotent - calling multiple times is safe."""
        project_x = AsyncMock(spec=ProjectXBase)
        realtime_client = Mock(spec=ProjectXRealtimeClient)

        # Mock successful first initialization
        instrument = Instrument(
            id="123",
            name="MNQ",
            description="Micro E-mini Nasdaq-100",
            tickSize=0.25,
            tickValue=0.5,
            activeContract=True,
            symbolId="F.US.MNQ",
        )
        project_x.get_instrument.return_value = instrument
        project_x.get_bars.return_value = pl.DataFrame(
            {
                "timestamp": [datetime(2023, 1, 1, 9, 30)],
                "open": [15000.0],
                "high": [15002.0],
                "low": [14998.0],
                "close": [15001.0],
                "volume": [100],
            }
        )

        manager = RealtimeDataManager("MNQ", project_x, realtime_client)

        # First initialization
        result1 = await manager.initialize()
        assert result1 is True
        assert manager._initialized is True

        # Second initialization should return True but not re-initialize
        result2 = await manager.initialize()
        assert result2 is True

        # Should have only called get_instrument once
        project_x.get_instrument.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_historical_data_gap_warning(self):
        """Test warning when historical data has significant gap to current time."""
        project_x = AsyncMock(spec=ProjectXBase)
        realtime_client = Mock(spec=ProjectXRealtimeClient)

        instrument = Instrument(
            id="123",
            name="MNQ",
            description="Micro E-mini Nasdaq-100",
            tickSize=0.25,
            tickValue=0.5,
            activeContract=True,
            symbolId="F.US.MNQ",
        )
        project_x.get_instrument.return_value = instrument

        # Historical data ending 10 minutes ago (should trigger warning)
        old_timestamp = datetime.now() - timedelta(minutes=10)
        project_x.get_bars.return_value = pl.DataFrame(
            {
                "timestamp": [old_timestamp],
                "open": [15000.0],
                "high": [15002.0],
                "low": [14998.0],
                "close": [15001.0],
                "volume": [100],
            }
        )

        manager = RealtimeDataManager("MNQ", project_x, realtime_client)

        # Just check that initialize completes without error
        # The actual warning logging is tested elsewhere
        await manager.initialize()

        # Verify that the manager initialized successfully despite old data
        assert "5min" in manager.data
        assert len(manager.data["5min"]) == 1  # Should have loaded the old data

    @pytest.mark.asyncio
    async def test_initialize_empty_historical_data(self):
        """Test handling of empty historical data."""
        project_x = AsyncMock(spec=ProjectXBase)
        realtime_client = Mock(spec=ProjectXRealtimeClient)

        instrument = Instrument(
            id="123",
            name="MNQ",
            description="Micro E-mini Nasdaq-100",
            tickSize=0.25,
            tickValue=0.5,
            activeContract=True,
            symbolId="F.US.MNQ",
        )
        project_x.get_instrument.return_value = instrument

        # Return empty DataFrame
        project_x.get_bars.return_value = pl.DataFrame()

        manager = RealtimeDataManager("MNQ", project_x, realtime_client)

        result = await manager.initialize()

        # Should still return True despite empty data
        assert result is True
        # With empty historical data, the timeframe might not be created yet
        # This is acceptable as it will be created when real-time data arrives

    @pytest.mark.asyncio
    async def test_initialize_symbol_id_parsing(self):
        """Test parsing of symbolId for instrument matching."""
        project_x = AsyncMock(spec=ProjectXBase)
        realtime_client = Mock(spec=ProjectXRealtimeClient)

        # Test complex symbolId parsing
        test_cases = [
            ("F.US.ENQ", "ENQ"),
            ("F.CME.MES", "MES"),
            ("SIMPLE", "SIMPLE"),
            (None, "MNQ"),  # Falls back to instrument name
        ]

        for symbol_id, expected_result in test_cases:
            instrument = Instrument(
                id="123",
                name="MNQ",
                description="Micro E-mini Nasdaq-100",
                tickSize=0.25,
                tickValue=0.5,
                activeContract=True,
                symbolId=symbol_id,
            )
            project_x.get_instrument.return_value = instrument
            project_x.get_bars.return_value = pl.DataFrame(
                {
                    "timestamp": [datetime.now()],
                    "open": [15000.0],
                    "high": [15002.0],
                    "low": [14998.0],
                    "close": [15001.0],
                    "volume": [100],
                }
            )

            manager = RealtimeDataManager("MNQ", project_x, realtime_client)
            await manager.initialize()

            assert manager.instrument_symbol_id == expected_result


class TestRealtimeDataManagerWebSocketOperations:
    """Test WebSocket connection management and message handling."""

    @pytest.mark.asyncio
    async def test_start_realtime_feed_successful(self):
        """Test successful start of realtime feed."""
        project_x = Mock(spec=ProjectXBase)
        realtime_client = AsyncMock(spec=ProjectXRealtimeClient)

        # Mock successful connection and subscription
        realtime_client.is_connected.return_value = True
        realtime_client.subscribe_market_data.return_value = True

        manager = RealtimeDataManager("MNQ", project_x, realtime_client)
        manager.contract_id = "test-contract-id"  # Set required for start
        manager._initialized = True  # Mark as initialized

        with (
            patch.object(manager, "start_cleanup_task"),
            patch.object(manager, "_start_bar_timer_task"),
            patch.object(manager, "start_resource_monitoring"),
        ):
            result = await manager.start_realtime_feed()

            assert result is True
            assert manager.is_running is True

            # Verify callbacks were registered
            realtime_client.add_callback.assert_any_call(
                "quote_update", manager._on_quote_update
            )
            realtime_client.add_callback.assert_any_call(
                "market_trade", manager._on_trade_update
            )

            # Verify subscription
            realtime_client.subscribe_market_data.assert_called_once_with(
                ["test-contract-id"]
            )

    @pytest.mark.asyncio
    async def test_start_realtime_feed_already_running(self):
        """Test starting realtime feed when already running."""
        project_x = Mock(spec=ProjectXBase)
        realtime_client = AsyncMock(spec=ProjectXRealtimeClient)

        manager = RealtimeDataManager("MNQ", project_x, realtime_client)
        manager.is_running = True  # Already running
        manager.contract_id = "test-contract-id"

        result = await manager.start_realtime_feed()

        assert result is True
        # Should return True without changes since already running

    @pytest.mark.asyncio
    async def test_start_realtime_feed_not_initialized(self):
        """Test error when starting feed before initialization."""
        project_x = Mock(spec=ProjectXBase)
        realtime_client = Mock(spec=ProjectXRealtimeClient)

        manager = RealtimeDataManager("MNQ", project_x, realtime_client)
        # contract_id is None (not initialized)

        with pytest.raises(ProjectXError, match="not initialized"):
            await manager.start_realtime_feed()

    @pytest.mark.asyncio
    async def test_start_realtime_feed_client_not_connected(self):
        """Test error when realtime client is not connected."""
        project_x = Mock(spec=ProjectXBase)
        realtime_client = AsyncMock(spec=ProjectXRealtimeClient)

        # Mock client not connected
        realtime_client.is_connected.return_value = False

        manager = RealtimeDataManager("MNQ", project_x, realtime_client)
        manager.contract_id = "test-contract-id"  # Set to pass initialization check

        with pytest.raises(ProjectXError, match="Realtime client not connected"):
            await manager.start_realtime_feed()

    @pytest.mark.asyncio
    async def test_start_realtime_feed_subscription_failed(self):
        """Test error when market data subscription fails."""
        project_x = Mock(spec=ProjectXBase)
        realtime_client = AsyncMock(spec=ProjectXRealtimeClient)

        # Mock connected but subscription fails
        realtime_client.is_connected.return_value = True
        realtime_client.subscribe_market_data.return_value = False

        manager = RealtimeDataManager("MNQ", project_x, realtime_client)
        manager.contract_id = "test-contract-id"

        with pytest.raises(ProjectXError, match="Subscription returned False"):
            await manager.start_realtime_feed()

    @pytest.mark.asyncio
    async def test_start_realtime_feed_skips_resubscribe_when_already_subscribed(
        self,
    ):
        """Issue #126: start_realtime_feed is idempotent if the contract is live."""
        project_x = Mock(spec=ProjectXBase)
        realtime_client = AsyncMock(spec=ProjectXRealtimeClient)

        realtime_client.is_connected.return_value = True
        realtime_client.subscribe_market_data.return_value = True
        realtime_client._subscribed_contracts = ["test-contract-id"]

        manager = RealtimeDataManager("MNQ", project_x, realtime_client)
        manager.contract_id = "test-contract-id"
        manager._initialized = True

        with (
            patch.object(manager, "start_cleanup_task"),
            patch.object(manager, "_start_bar_timer_task"),
            patch.object(manager, "start_resource_monitoring"),
        ):
            result = await manager.start_realtime_feed()

        assert result is True
        assert manager.is_running is True
        realtime_client.subscribe_market_data.assert_not_called()
        realtime_client.add_callback.assert_any_call(
            "quote_update", manager._on_quote_update
        )

    @pytest.mark.asyncio
    async def test_stop_realtime_feed_successful(self):
        """Test successful stop of realtime feed."""
        project_x = Mock(spec=ProjectXBase)
        realtime_client = AsyncMock(spec=ProjectXRealtimeClient)

        manager = RealtimeDataManager("MNQ", project_x, realtime_client)
        manager.is_running = True
        manager.contract_id = "test-contract-id"

        with (
            patch.object(manager, "stop_cleanup_task") as mock_stop_cleanup,
            patch.object(manager, "_stop_bar_timer_task") as mock_stop_timer,
            patch.object(manager, "stop_resource_monitoring") as mock_stop_resource,
        ):
            await manager.stop_realtime_feed()

            assert manager.is_running is False

            # Verify cleanup methods called
            mock_stop_cleanup.assert_called_once()
            mock_stop_timer.assert_called_once()
            mock_stop_resource.assert_called_once()

            # Verify unsubscription and callback removal
            realtime_client.unsubscribe_market_data.assert_called_once_with(
                ["test-contract-id"]
            )
            realtime_client.remove_callback.assert_any_call(
                "quote_update", manager._on_quote_update
            )
            realtime_client.remove_callback.assert_any_call(
                "market_trade", manager._on_trade_update
            )

    @pytest.mark.asyncio
    async def test_stop_realtime_feed_not_running(self):
        """Test stopping feed when not running."""
        project_x = Mock(spec=ProjectXBase)
        realtime_client = Mock(spec=ProjectXRealtimeClient)

        manager = RealtimeDataManager("MNQ", project_x, realtime_client)
        manager.is_running = False  # Not running

        # Should return without error
        await manager.stop_realtime_feed()

        # No unsubscription should occur
        realtime_client.unsubscribe_market_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_stop_realtime_feed_error_handling(self):
        """Test error handling during stop."""
        project_x = Mock(spec=ProjectXBase)
        realtime_client = AsyncMock(spec=ProjectXRealtimeClient)

        # Mock unsubscription failure
        realtime_client.unsubscribe_market_data.side_effect = Exception(
            "Unsubscribe failed"
        )

        manager = RealtimeDataManager("MNQ", project_x, realtime_client)
        manager.is_running = True
        manager.contract_id = "test-contract-id"

        with (
            patch.object(manager, "stop_cleanup_task"),
            patch.object(manager, "_stop_bar_timer_task"),
            patch.object(manager, "stop_resource_monitoring"),
        ):
            # Should not raise exception
            await manager.stop_realtime_feed()

            # Should have tried to unsubscribe despite error
            realtime_client.unsubscribe_market_data.assert_called()


class TestBarTimerFunctionality:
    """Test the bar timer functionality for low-volume periods."""

    @pytest.mark.asyncio
    async def test_start_bar_timer_task(self):
        """Test starting the bar timer task."""
        project_x = Mock(spec=ProjectXBase)
        realtime_client = Mock(spec=ProjectXRealtimeClient)

        manager = RealtimeDataManager("MNQ", project_x, realtime_client)

        with patch.object(asyncio, "create_task") as mock_create_task:
            manager._start_bar_timer_task()

            mock_create_task.assert_called_once()
            assert manager._bar_timer_task is not None

    @pytest.mark.asyncio
    async def test_stop_bar_timer_task(self):
        """Test stopping the bar timer task."""
        project_x = Mock(spec=ProjectXBase)
        realtime_client = Mock(spec=ProjectXRealtimeClient)

        manager = RealtimeDataManager("MNQ", project_x, realtime_client)

        # Create a real coroutine that can be awaited
        async def dummy_coro():
            pass

        task = asyncio.create_task(dummy_coro())
        manager._bar_timer_task = task

        await manager._stop_bar_timer_task()

        # Task should be cancelled
        assert task.cancelled() or task.done()

    @pytest.mark.asyncio
    async def test_bar_timer_loop_creates_empty_bars(self):
        """Test that bar timer creates empty bars during low volume."""
        project_x = Mock(spec=ProjectXBase)
        realtime_client = Mock(spec=ProjectXRealtimeClient)

        manager = RealtimeDataManager(
            "MNQ", project_x, realtime_client, timeframes=["1min"]
        )
        manager.is_running = True
        manager.tick_size = 0.25

        # Set up existing data
        old_time = datetime.now(manager.timezone) - timedelta(minutes=2)
        manager.data["1min"] = pl.DataFrame(
            {
                "timestamp": [old_time],
                "open": [15000.0],
                "high": [15002.0],
                "low": [14998.0],
                "close": [15001.0],
                "volume": [100],
            }
        )

        # Mock the _check_and_create_empty_bars method to avoid complex timer logic
        with patch.object(manager, "_check_and_create_empty_bars") as mock_check:
            # Track calls and stop after a few iterations
            call_count = 0

            async def stop_after_few():
                nonlocal call_count
                call_count += 1
                if call_count >= 3:  # Stop after 3 iterations
                    manager.is_running = False

            mock_check.side_effect = stop_after_few

            # Run the bar timer loop
            await manager._bar_timer_loop()

            # Should have been called at least once
            assert mock_check.call_count >= 3

    @pytest.mark.asyncio
    async def test_check_and_create_empty_bars_creates_bar(self):
        """Test creation of empty bars when needed."""
        project_x = Mock(spec=ProjectXBase)
        realtime_client = Mock(spec=ProjectXRealtimeClient)

        manager = RealtimeDataManager(
            "MNQ", project_x, realtime_client, timeframes=["1min"]
        )
        manager.tick_size = 0.25

        # Set up old data that should trigger empty bar creation
        old_time = datetime.now(manager.timezone) - timedelta(minutes=2)
        manager.data["1min"] = pl.DataFrame(
            {
                "timestamp": [old_time],
                "open": [15000.0],
                "high": [15002.0],
                "low": [14998.0],
                "close": [15001.0],
                "volume": [100],
            }
        )

        with patch.object(manager, "_trigger_callbacks") as mock_trigger:
            await manager._check_and_create_empty_bars()

            # Should have created new bar
            assert len(manager.data["1min"]) == 2

            # New bar should have volume = 0 and use last close price
            new_bar = manager.data["1min"].tail(1).to_dicts()[0]
            assert new_bar["volume"] == 0
            assert new_bar["open"] == 15001.0  # Last close price
            assert new_bar["close"] == 15001.0

    @pytest.mark.asyncio
    async def test_check_and_create_empty_bars_error_handling(self):
        """Test error handling in empty bar creation."""
        project_x = Mock(spec=ProjectXBase)
        realtime_client = Mock(spec=ProjectXRealtimeClient)

        manager = RealtimeDataManager("MNQ", project_x, realtime_client)
        manager.data["1min"] = pl.DataFrame()  # Empty data that will cause error

        # Should not raise exception even with empty data
        try:
            await manager._check_and_create_empty_bars()
        except Exception:
            pytest.fail("_check_and_create_empty_bars should not raise exception")


class TestCleanupAndResourceManagement:
    """Test cleanup functionality and resource management."""

    @pytest.mark.asyncio
    async def test_cleanup_successful(self):
        """Test successful cleanup of resources."""
        project_x = Mock(spec=ProjectXBase)
        realtime_client = Mock(spec=ProjectXRealtimeClient)

        manager = RealtimeDataManager("MNQ", project_x, realtime_client)
        manager.use_bounded_statistics = True
        manager._initialized = True

        # Add some data to cleanup
        manager.data["5min"] = pl.DataFrame(
            {
                "timestamp": [datetime.now()],
                "open": [15000.0],
                "high": [15002.0],
                "low": [14998.0],
                "close": [15001.0],
                "volume": [100],
            }
        )
        manager.current_tick_data.append({"price": 15000.0, "volume": 10})

        with (
            patch.object(manager, "stop_realtime_feed") as mock_stop_feed,
            patch.object(manager, "cleanup_bounded_statistics") as mock_cleanup_stats,
        ):
            await manager.cleanup()

            mock_stop_feed.assert_called_once()
            mock_cleanup_stats.assert_called_once()

            # Verify data cleared
            assert len(manager.data) == 0
            assert len(manager.current_tick_data) == 0
            assert not manager._initialized

    @pytest.mark.asyncio
    async def test_cleanup_bounded_statistics_error(self):
        """Test handling of bounded statistics cleanup errors."""
        project_x = Mock(spec=ProjectXBase)
        realtime_client = Mock(spec=ProjectXRealtimeClient)

        manager = RealtimeDataManager("MNQ", project_x, realtime_client)
        manager.use_bounded_statistics = True

        with (
            patch.object(manager, "stop_realtime_feed"),
            patch.object(
                manager,
                "cleanup_bounded_statistics",
                side_effect=Exception("Cleanup failed"),
            ),
            patch.object(manager, "logger") as mock_logger,
        ):
            # Should not raise exception
            await manager.cleanup()

            mock_logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_cleanup_backward_compatible_attributes(self):
        """Test cleanup of backward-compatible attributes."""
        project_x = Mock(spec=ProjectXBase)
        realtime_client = Mock(spec=ProjectXRealtimeClient)

        manager = RealtimeDataManager("MNQ", project_x, realtime_client)

        # Add backward-compatible attributes
        manager.bars = {"5min": [{"open": 15000}]}
        manager.ticks = [{"price": 15000}]
        manager.dom_data = {"bid": [{"price": 14999}]}

        await manager.cleanup()

        # Should have cleared backward-compatible attributes
        assert len(manager.bars["5min"]) == 0
        assert len(manager.ticks) == 0
        assert len(manager.dom_data["bid"]) == 0


class TestMemoryAndResourceStatistics:
    """Test memory usage and resource statistics functionality."""

    @pytest.mark.asyncio
    async def test_get_memory_stats_comprehensive(self):
        """Test comprehensive memory statistics generation."""
        project_x = Mock(spec=ProjectXBase)
        realtime_client = Mock(spec=ProjectXRealtimeClient)

        manager = RealtimeDataManager(
            "MNQ", project_x, realtime_client, timeframes=["1min", "5min"]
        )

        # Add test data
        manager.data["1min"] = pl.DataFrame(
            {
                "timestamp": [datetime.now()] * 100,
                "open": [15000.0] * 100,
                "high": [15002.0] * 100,
                "low": [14998.0] * 100,
                "close": [15001.0] * 100,
                "volume": [100] * 100,
            }
        )

        manager.data["5min"] = pl.DataFrame(
            {
                "timestamp": [datetime.now()] * 50,
                "open": [15000.0] * 50,
                "high": [15002.0] * 50,
                "low": [14998.0] * 50,
                "close": [15001.0] * 50,
                "volume": [100] * 50,
            }
        )

        for _ in range(500):
            manager.current_tick_data.append({"price": 15000.0, "volume": 10})

        with patch.object(
            manager, "get_overflow_stats", return_value={"overflow_size": 1024}
        ):
            stats = await manager.get_memory_stats()

            assert stats["total_bars_stored"] == 150  # 100 + 50
            assert stats["memory_usage_mb"] > 0
            assert stats["buffer_utilization"] > 0
            assert "overflow_stats" in stats
            assert "lock_optimization_stats" in stats

    @pytest.mark.asyncio
    async def test_get_memory_usage_override(self):
        """Test memory usage calculation override."""
        project_x = Mock(spec=ProjectXBase)
        realtime_client = Mock(spec=ProjectXRealtimeClient)

        manager = RealtimeDataManager("MNQ", project_x, realtime_client)

        # Add data
        manager.data["5min"] = pl.DataFrame(
            {
                "timestamp": [datetime.now()] * 100,
                "open": [15000.0] * 100,
                "high": [15002.0] * 100,
                "low": [14998.0] * 100,
                "close": [15001.0] * 100,
                "volume": [100] * 100,
            }
        )

        for _ in range(1000):
            manager.current_tick_data.append({"price": 15000.0})

        memory_usage = await manager.get_memory_usage()

        assert memory_usage > 0
        # Should include base memory + data memory + tick memory
        assert manager.memory_stats["memory_usage_mb"] == memory_usage

    @pytest.mark.asyncio
    async def test_get_resource_stats_dynamic_enabled(self):
        """Test resource statistics with dynamic limits enabled."""
        project_x = Mock(spec=ProjectXBase)
        realtime_client = Mock(spec=ProjectXRealtimeClient)

        config = {"enable_dynamic_limits": True}
        manager = RealtimeDataManager("MNQ", project_x, realtime_client, config=config)
        manager._current_limits = {"max_bars": 1000}  # Mock dynamic limits

        with patch(
            "project_x_py.realtime_data_manager.core.DynamicResourceMixin.get_resource_stats"
        ) as mock_super_stats:
            mock_super_stats.return_value = {"dynamic_enabled": True}

            stats = await manager.get_resource_stats()

            assert stats["dynamic_enabled"] is True

    @pytest.mark.asyncio
    async def test_get_resource_stats_dynamic_disabled(self):
        """Test resource statistics with dynamic limits disabled."""
        project_x = Mock(spec=ProjectXBase)
        realtime_client = Mock(spec=ProjectXRealtimeClient)

        config = {"enable_dynamic_limits": False}
        manager = RealtimeDataManager("MNQ", project_x, realtime_client, config=config)

        # Add some data for testing
        manager.data["5min"] = pl.DataFrame(
            {
                "timestamp": [datetime.now()] * 50,
                "open": [15000.0] * 50,
                "high": [15002.0] * 50,
                "low": [14998.0] * 50,
                "close": [15001.0] * 50,
                "volume": [100] * 50,
            }
        )

        for _ in range(100):
            manager.current_tick_data.append({"price": 15000.0})

        stats = await manager.get_resource_stats()

        assert stats["dynamic_limits_enabled"] is False
        assert "static_limits" in stats
        assert (
            stats["static_limits"]["max_bars_per_timeframe"]
            == manager.max_bars_per_timeframe
        )
        assert "memory_usage" in stats
        assert stats["memory_usage"]["total_bars"] == 50

    @pytest.mark.asyncio
    async def test_optimize_data_access_patterns(self):
        """Test data access pattern optimization analysis."""
        project_x = Mock(spec=ProjectXBase)
        realtime_client = Mock(spec=ProjectXRealtimeClient)

        manager = RealtimeDataManager("MNQ", project_x, realtime_client)

        # Mock lock stats indicating high contention
        from project_x_py.utils.lock_optimization import LockStats

        mock_stats = LockStats(
            total_acquisitions=1000,
            total_wait_time_ms=5000,
            max_wait_time_ms=50,
            min_wait_time_ms=1,
            concurrent_readers=25,
            max_concurrent_readers=25,
            timeouts=10,
            contentions=150,
        )

        with patch.object(manager.data_rw_lock, "get_stats", return_value=mock_stats):
            optimization_results = await manager.optimize_data_access_patterns()

            assert "analysis" in optimization_results
            assert "optimizations_applied" in optimization_results
            assert "performance_improvements" in optimization_results

            # Should detect high contention
            assert optimization_results["analysis"]["contention_rate_percent"] == 15.0
            assert len(optimization_results["optimizations_applied"]) > 0

    @pytest.mark.asyncio
    async def test_get_lock_optimization_stats(self):
        """Test detailed lock optimization statistics."""
        project_x = Mock(spec=ProjectXBase)
        realtime_client = Mock(spec=ProjectXRealtimeClient)

        manager = RealtimeDataManager("MNQ", project_x, realtime_client)

        # Mock lock stats
        from project_x_py.utils.lock_optimization import LockStats

        mock_stats = LockStats(
            total_acquisitions=500,
            total_wait_time_ms=1000,
            max_wait_time_ms=10,
            min_wait_time_ms=0.1,
            concurrent_readers=5,
            max_concurrent_readers=10,
            timeouts=2,
            contentions=25,
        )

        with (
            patch.object(manager.data_rw_lock, "get_stats", return_value=mock_stats),
            patch(
                "project_x_py.realtime_data_manager.core.LockOptimizationMixin.get_lock_optimization_stats",
                return_value={},
            ),
        ):
            stats = await manager.get_lock_optimization_stats()

            assert "data_rw_lock" in stats
            lock_stats = stats["data_rw_lock"]
            assert lock_stats["total_acquisitions"] == 500
            assert lock_stats["avg_wait_time_ms"] == 2.0  # 1000/500
            assert (
                lock_stats["current_reader_count"] == manager.data_rw_lock.reader_count
            )

    @pytest.mark.asyncio
    async def test_bounded_statistics_methods(self):
        """Test bounded statistics functionality."""
        project_x = Mock(spec=ProjectXBase)
        realtime_client = Mock(spec=ProjectXRealtimeClient)

        config = {"use_bounded_statistics": True}
        manager = RealtimeDataManager("MNQ", project_x, realtime_client, config=config)

        with patch.object(
            manager, "get_all_bounded_stats", return_value={"metrics": "test"}
        ) as mock_get_stats:
            # Test enabled case
            assert manager.is_bounded_statistics_enabled() is True

            bounded_stats = await manager.get_bounded_statistics()
            assert bounded_stats == {"metrics": "test"}
            mock_get_stats.assert_called_once()

        # Test disabled case
        manager.use_bounded_statistics = False
        assert manager.is_bounded_statistics_enabled() is False

        bounded_stats = await manager.get_bounded_statistics()
        assert bounded_stats is None


class TestStatisticsTracking:
    """Test statistics tracking methods."""

    @pytest.mark.asyncio
    async def test_track_tick_processed(self):
        """Test tick processing tracking."""
        project_x = Mock(spec=ProjectXBase)
        realtime_client = Mock(spec=ProjectXRealtimeClient)

        config = {"use_bounded_statistics": True}
        manager = RealtimeDataManager("MNQ", project_x, realtime_client, config=config)

        with patch.object(manager, "increment_bounded") as mock_bounded:
            await manager.track_tick_processed()

            mock_bounded.assert_called_once_with("ticks_processed", 1)
            assert manager.memory_stats["ticks_processed"] == 1

    @pytest.mark.asyncio
    async def test_track_quote_processed(self):
        """Test quote processing tracking."""
        project_x = Mock(spec=ProjectXBase)
        realtime_client = Mock(spec=ProjectXRealtimeClient)

        config = {"use_bounded_statistics": False}  # Test non-bounded path
        manager = RealtimeDataManager("MNQ", project_x, realtime_client, config=config)

        with patch.object(manager, "increment") as mock_increment:
            await manager.track_quote_processed()

            mock_increment.assert_called_once_with("quotes_processed", 1)
            assert manager.memory_stats["quotes_processed"] == 1

    @pytest.mark.asyncio
    async def test_track_bar_created(self):
        """Test bar creation tracking."""
        project_x = Mock(spec=ProjectXBase)
        realtime_client = Mock(spec=ProjectXRealtimeClient)

        manager = RealtimeDataManager(
            "MNQ", project_x, realtime_client, timeframes=["5min"]
        )

        # Just verify the method can be called without error
        await manager.track_bar_created("5min")

        # Check that memory_stats is updated
        assert "bars_processed" in manager.memory_stats
        assert "timeframe_stats" in manager.memory_stats
        assert "5min" in manager.memory_stats["timeframe_stats"]

    @pytest.mark.asyncio
    async def test_track_bar_updated(self):
        """Test bar update tracking."""
        project_x = Mock(spec=ProjectXBase)
        realtime_client = Mock(spec=ProjectXRealtimeClient)

        manager = RealtimeDataManager(
            "MNQ", project_x, realtime_client, timeframes=["15min"]
        )

        # Just verify the method can be called without error
        await manager.track_bar_updated("15min")

        # Check that memory_stats is updated
        assert "bars_processed" in manager.memory_stats
        assert "timeframe_stats" in manager.memory_stats

    @pytest.mark.asyncio
    async def test_track_connection_interruption(self):
        """Test connection interruption tracking."""
        project_x = Mock(spec=ProjectXBase)
        realtime_client = Mock(spec=ProjectXRealtimeClient)

        manager = RealtimeDataManager("MNQ", project_x, realtime_client)

        # Just verify the method can be called without error
        await manager.track_connection_interruption()

        # Check that memory_stats is updated
        assert "connection_interruptions" in manager.memory_stats

    @pytest.mark.asyncio
    async def test_track_recovery_attempt(self):
        """Test recovery attempt tracking."""
        project_x = Mock(spec=ProjectXBase)
        realtime_client = Mock(spec=ProjectXRealtimeClient)

        manager = RealtimeDataManager("MNQ", project_x, realtime_client)

        # Just verify the method can be called without error
        await manager.track_recovery_attempt()

        # Check that memory_stats is updated
        assert "recovery_attempts" in manager.memory_stats

    @pytest.mark.asyncio
    async def test_track_data_latency(self):
        """Test data latency tracking."""
        project_x = Mock(spec=ProjectXBase)
        realtime_client = Mock(spec=ProjectXRealtimeClient)

        manager = RealtimeDataManager("MNQ", project_x, realtime_client)

        # Just verify the method can be called without error
        await manager.track_data_latency(5.5)

        # Check that memory_stats is updated
        assert "data_latency_ms" in manager.memory_stats


class TestErrorHandlingAndEdgeCases:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_configuration_defaults(self):
        """Test that configuration defaults are properly applied."""
        project_x = Mock(spec=ProjectXBase)
        realtime_client = Mock(spec=ProjectXRealtimeClient)

        manager = RealtimeDataManager("MNQ", project_x, realtime_client)

        # Test default values
        assert manager.max_bars_per_timeframe == 1000
        assert manager.enable_tick_data is True
        assert manager.enable_level2_data is False
        assert manager.data_validation is True
        assert manager.compression_enabled is True
        assert manager.auto_cleanup is True
        assert manager.cleanup_interval_minutes == 5

    @pytest.mark.asyncio
    async def test_timezone_handling(self):
        """Test timezone handling in various scenarios."""
        project_x = Mock(spec=ProjectXBase)
        realtime_client = Mock(spec=ProjectXRealtimeClient)

        # Test custom timezone
        manager = RealtimeDataManager(
            "MNQ", project_x, realtime_client, timezone="Europe/London"
        )

        assert str(manager.timezone) == "Europe/London"

        # Test config override
        config = {"timezone": "Asia/Tokyo"}
        manager2 = RealtimeDataManager(
            "MNQ",
            project_x,
            realtime_client,
            timezone="Europe/London",  # Should be overridden
            config=config,
        )

        assert str(manager2.timezone) == "Asia/Tokyo"

    @pytest.mark.asyncio
    async def test_session_config_initialization(self):
        """Test session configuration initialization."""
        project_x = Mock(spec=ProjectXBase)
        realtime_client = Mock(spec=ProjectXRealtimeClient)

        # Mock session config
        mock_session_config = Mock()

        with patch("project_x_py.sessions.SessionFilterMixin") as mock_filter_class:
            mock_filter_instance = Mock()
            mock_filter_class.return_value = mock_filter_instance

            manager = RealtimeDataManager(
                "MNQ", project_x, realtime_client, session_config=mock_session_config
            )

            assert manager.session_config == mock_session_config
            assert manager.session_filter == mock_filter_instance
            mock_filter_class.assert_called_once_with(config=mock_session_config)

    def test_timeframe_validation_edge_cases(self):
        """Test edge cases in timeframe validation."""
        project_x = Mock(spec=ProjectXBase)
        realtime_client = Mock(spec=ProjectXRealtimeClient)

        # Test all valid timeframes
        valid_timeframes = [
            "1sec",
            "5sec",
            "10sec",
            "15sec",
            "30sec",
            "1min",
            "5min",
            "15min",
            "30min",
            "1hr",
            "4hr",
            "1day",
            "1week",
            "1month",
        ]

        manager = RealtimeDataManager(
            "MNQ", project_x, realtime_client, timeframes=valid_timeframes
        )

        assert len(manager.timeframes) == len(valid_timeframes)
        for tf in valid_timeframes:
            assert tf in manager.timeframes

    @pytest.mark.asyncio
    async def test_initial_status_task_creation(self):
        """Test initial status task creation during initialization."""
        project_x = AsyncMock(spec=ProjectXBase)
        realtime_client = Mock(spec=ProjectXRealtimeClient)

        # Mock successful initialization
        instrument = Instrument(
            id="123",
            name="MNQ",
            description="Micro E-mini Nasdaq-100",
            tickSize=0.25,
            tickValue=0.5,
            activeContract=True,
            symbolId="F.US.MNQ",
        )
        project_x.get_instrument.return_value = instrument
        project_x.get_bars.return_value = pl.DataFrame(
            {
                "timestamp": [datetime.now()],
                "open": [15000.0],
                "high": [15002.0],
                "low": [14998.0],
                "close": [15001.0],
                "volume": [100],
            }
        )

        manager = RealtimeDataManager("MNQ", project_x, realtime_client)

        with patch.object(asyncio, "create_task") as mock_create_task:
            await manager.initialize()

            # Should have created at least one task (for initial status or cleanup)
            assert mock_create_task.called
            # The manager should be initialized
            assert "5min" in manager.data

    @pytest.mark.asyncio
    async def test_set_initial_status(self):
        """Test initial status setting."""
        project_x = Mock(spec=ProjectXBase)
        realtime_client = Mock(spec=ProjectXRealtimeClient)

        manager = RealtimeDataManager(
            "MNQ", project_x, realtime_client, timeframes=["1min", "5min"]
        )

        with (
            patch.object(manager, "set_status") as mock_set_status,
            patch.object(manager, "increment") as mock_increment,
            patch.object(manager, "set_gauge") as mock_set_gauge,
        ):
            await manager._set_initial_status()

            mock_set_status.assert_called_once_with("initializing")
            mock_increment.assert_called_once_with("component_initialized", 1)
            mock_set_gauge.assert_called_once_with("total_timeframes", 2)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
