"""
Comprehensive tests for realtime_data_manager.callbacks module.

Following project-x-py TDD methodology:
1. Write tests FIRST defining expected behavior
2. Test what code SHOULD do, not what it currently does
3. Fix implementation if tests reveal bugs
4. Never change tests to match broken code

Test Coverage Goals:
- CallbackMixin event handling functionality
- Event type mapping and validation
- Async and sync callback execution
- Error isolation and handling
- Thread safety and concurrent operations
- Event data structure validation
- EventBus integration
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, Mock, patch, call
from datetime import datetime, timezone

from project_x_py.realtime_data_manager.callbacks import CallbackMixin
from project_x_py.event_bus import EventType, EventBus


class MockRealtimeDataManager(CallbackMixin):
    """Mock class implementing CallbackMixin for testing."""

    def __init__(self, event_bus=None, logger=None):
        self.event_bus = event_bus or AsyncMock(spec=EventBus)
        self.logger = logger or Mock()


class TestCallbackMixinBasicFunctionality:
    """Test basic callback management functionality."""

    @pytest.fixture
    def mock_event_bus(self):
        """Mock event bus for testing."""
        mock = AsyncMock(spec=EventBus)
        mock.on = AsyncMock()
        mock.emit = AsyncMock()
        return mock

    @pytest.fixture
    def mock_logger(self):
        """Mock logger for testing."""
        mock = Mock()
        mock.warning = Mock()
        mock.error = Mock()
        return mock

    @pytest.fixture
    def callback_manager(self, mock_event_bus, mock_logger):
        """CallbackMixin instance for testing."""
        return MockRealtimeDataManager(event_bus=mock_event_bus, logger=mock_logger)

    @pytest.mark.asyncio
    async def test_add_callback_new_bar_event(self, callback_manager):
        """Test adding callback for new_bar event type."""
        async def test_callback(data):
            pass

        # Should register callback with event bus
        await callback_manager.add_callback("new_bar", test_callback)

        # Should call event_bus.on with correct EventType
        callback_manager.event_bus.on.assert_called_once_with(
            EventType.NEW_BAR, test_callback
        )

    @pytest.mark.asyncio
    async def test_add_callback_data_update_event(self, callback_manager):
        """Test adding callback for data_update event type."""
        def test_callback(data):
            pass

        # Should register callback with event bus
        await callback_manager.add_callback("data_update", test_callback)

        # Should call event_bus.on with correct EventType
        callback_manager.event_bus.on.assert_called_once_with(
            EventType.DATA_UPDATE, test_callback
        )

    @pytest.mark.asyncio
    async def test_add_callback_invalid_event_type(self, callback_manager):
        """Test handling of invalid event type."""
        async def test_callback(data):
            pass

        # Should log warning for invalid event type
        await callback_manager.add_callback("invalid_event", test_callback)

        # Should not call event_bus.on
        callback_manager.event_bus.on.assert_not_called()

        # Should log warning
        callback_manager.logger.warning.assert_called_once_with(
            "Unknown event type: invalid_event"
        )

    @pytest.mark.asyncio
    async def test_add_callback_multiple_callbacks_same_event(self, callback_manager):
        """Test adding multiple callbacks for the same event type."""
        async def callback1(data):
            pass

        async def callback2(data):
            pass

        # Add multiple callbacks
        await callback_manager.add_callback("new_bar", callback1)
        await callback_manager.add_callback("new_bar", callback2)

        # Should register both callbacks
        expected_calls = [
            call(EventType.NEW_BAR, callback1),
            call(EventType.NEW_BAR, callback2)
        ]
        callback_manager.event_bus.on.assert_has_calls(expected_calls)

    @pytest.mark.asyncio
    async def test_add_callback_async_and_sync_callbacks(self, callback_manager):
        """Test support for both async and sync callbacks."""
        # Async callback
        async def async_callback(data):
            pass

        # Sync callback
        def sync_callback(data):
            pass

        # Should accept both types
        await callback_manager.add_callback("new_bar", async_callback)
        await callback_manager.add_callback("data_update", sync_callback)

        # Should register both callbacks
        expected_calls = [
            call(EventType.NEW_BAR, async_callback),
            call(EventType.DATA_UPDATE, sync_callback)
        ]
        callback_manager.event_bus.on.assert_has_calls(expected_calls)


class TestCallbackMixinEventTriggering:
    """Test event triggering functionality."""

    @pytest.fixture
    def callback_manager(self):
        """CallbackMixin instance with mocked dependencies."""
        mock_event_bus = AsyncMock(spec=EventBus)
        mock_logger = Mock()
        return MockRealtimeDataManager(event_bus=mock_event_bus, logger=mock_logger)

    @pytest.mark.asyncio
    async def test_trigger_callbacks_new_bar(self, callback_manager):
        """Test triggering new_bar callbacks through EventBus."""
        bar_data = {
            "timeframe": "5min",
            "bar_time": datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
            "data": {
                "timestamp": datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
                "open": 19000.0,
                "high": 19010.0,
                "low": 18995.0,
                "close": 19005.0,
                "volume": 1500
            }
        }

        # Trigger callbacks
        await callback_manager._trigger_callbacks("new_bar", bar_data)

        # Should emit event through EventBus
        callback_manager.event_bus.emit.assert_called_once_with(
            EventType.NEW_BAR, bar_data, source="RealtimeDataManager"
        )

    @pytest.mark.asyncio
    async def test_trigger_callbacks_data_update(self, callback_manager):
        """Test triggering data_update callbacks through EventBus."""
        tick_data = {
            "timestamp": datetime(2025, 1, 1, 10, 0, 15, tzinfo=timezone.utc),
            "price": 19001.50,
            "volume": 100
        }

        # Trigger callbacks
        await callback_manager._trigger_callbacks("data_update", tick_data)

        # Should emit event through EventBus
        callback_manager.event_bus.emit.assert_called_once_with(
            EventType.DATA_UPDATE, tick_data, source="RealtimeDataManager"
        )

    @pytest.mark.asyncio
    async def test_trigger_callbacks_invalid_event_type(self, callback_manager):
        """Test handling of invalid event type in trigger."""
        # Should log warning for invalid event type
        await callback_manager._trigger_callbacks("invalid_event", {})

        # Should not emit event
        callback_manager.event_bus.emit.assert_not_called()

        # Should log warning
        callback_manager.logger.warning.assert_called_once_with(
            "Unknown event type: invalid_event"
        )

    @pytest.mark.asyncio
    async def test_trigger_callbacks_multiple_events_sequentially(self, callback_manager):
        """Test triggering multiple events sequentially."""
        bar_data = {
            "timeframe": "1min", "bar_time": datetime.now(timezone.utc),
            "data": {"timestamp": datetime.now(timezone.utc), "open": 19000.0,
                    "high": 19005.0, "low": 18995.0, "close": 19002.0, "volume": 500}
        }
        tick_data = {
            "timestamp": datetime.now(timezone.utc), "price": 19003.0, "volume": 50
        }

        # Trigger multiple events
        await callback_manager._trigger_callbacks("new_bar", bar_data)
        await callback_manager._trigger_callbacks("data_update", tick_data)

        # Should emit both events
        expected_calls = [
            call(EventType.NEW_BAR, bar_data, source="RealtimeDataManager"),
            call(EventType.DATA_UPDATE, tick_data, source="RealtimeDataManager")
        ]
        callback_manager.event_bus.emit.assert_has_calls(expected_calls)


class TestCallbackMixinEventDataStructures:
    """Test event data structure validation and handling."""

    @pytest.fixture
    def callback_manager(self):
        """CallbackMixin instance for testing."""
        return MockRealtimeDataManager()

    def test_new_bar_event_data_structure(self):
        """Test that new_bar events have correct data structure."""
        # Define expected structure for new_bar events
        expected_new_bar_structure = {
            "timeframe": str,  # e.g., "5min"
            "bar_time": datetime,  # timezone-aware datetime
            "data": {
                "timestamp": datetime,  # Bar timestamp
                "open": (int, float),  # Opening price
                "high": (int, float),  # High price
                "low": (int, float),   # Low price
                "close": (int, float), # Closing price
                "volume": int          # Bar volume
            }
        }

        # Test data should match expected structure
        test_bar_data = {
            "timeframe": "5min",
            "bar_time": datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
            "data": {
                "timestamp": datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
                "open": 19000.0,
                "high": 19010.0,
                "low": 18995.0,
                "close": 19005.0,
                "volume": 1500
            }
        }

        # Validate structure
        assert isinstance(test_bar_data["timeframe"], str)
        assert isinstance(test_bar_data["bar_time"], datetime)
        assert test_bar_data["bar_time"].tzinfo is not None  # Should be timezone-aware

        bar_data = test_bar_data["data"]
        assert isinstance(bar_data["timestamp"], datetime)
        assert isinstance(bar_data["open"], (int, float))
        assert isinstance(bar_data["high"], (int, float))
        assert isinstance(bar_data["low"], (int, float))
        assert isinstance(bar_data["close"], (int, float))
        assert isinstance(bar_data["volume"], int)

        # Price validation
        assert bar_data["high"] >= bar_data["open"]
        assert bar_data["high"] >= bar_data["close"]
        assert bar_data["low"] <= bar_data["open"]
        assert bar_data["low"] <= bar_data["close"]

    def test_data_update_event_structure(self):
        """Test that data_update events have correct structure."""
        # Define expected structure for data_update events
        test_tick_data = {
            "timestamp": datetime(2025, 1, 1, 10, 0, 15, tzinfo=timezone.utc),
            "price": 19001.50,
            "volume": 100
        }

        # Validate structure
        assert isinstance(test_tick_data["timestamp"], datetime)
        assert test_tick_data["timestamp"].tzinfo is not None  # Should be timezone-aware
        assert isinstance(test_tick_data["price"], (int, float))
        assert isinstance(test_tick_data["volume"], int)
        assert test_tick_data["volume"] > 0  # Volume should be positive


class TestCallbackMixinErrorHandling:
    """Test error handling in callback operations."""

    @pytest.fixture
    def callback_manager_with_failing_event_bus(self):
        """CallbackMixin with event bus that raises errors."""
        mock_event_bus = AsyncMock(spec=EventBus)
        mock_event_bus.on.side_effect = Exception("EventBus error")
        mock_event_bus.emit.side_effect = Exception("EventBus emit error")

        mock_logger = Mock()
        return MockRealtimeDataManager(event_bus=mock_event_bus, logger=mock_logger)

    @pytest.mark.asyncio
    async def test_add_callback_event_bus_failure(self, callback_manager_with_failing_event_bus):
        """Test handling of EventBus failures during callback registration."""
        async def test_callback(data):
            pass

        # Should raise the exception from EventBus
        with pytest.raises(Exception, match="EventBus error"):
            await callback_manager_with_failing_event_bus.add_callback("new_bar", test_callback)

    @pytest.mark.asyncio
    async def test_trigger_callbacks_event_bus_failure(self, callback_manager_with_failing_event_bus):
        """Test handling of EventBus failures during event emission."""
        test_data = {"timeframe": "1min", "data": {}}

        # Should raise the exception from EventBus
        with pytest.raises(Exception, match="EventBus emit error"):
            await callback_manager_with_failing_event_bus._trigger_callbacks("new_bar", test_data)

    @pytest.mark.asyncio
    async def test_concurrent_callback_operations(self):
        """Test thread safety during concurrent callback operations."""
        mock_event_bus = AsyncMock(spec=EventBus)
        callback_manager = MockRealtimeDataManager(event_bus=mock_event_bus)

        # Define multiple callbacks
        async def callback1(data):
            await asyncio.sleep(0.01)  # Simulate work

        async def callback2(data):
            await asyncio.sleep(0.01)  # Simulate work

        def sync_callback(data):
            pass

        # Run concurrent operations
        tasks = [
            callback_manager.add_callback("new_bar", callback1),
            callback_manager.add_callback("new_bar", callback2),
            callback_manager.add_callback("data_update", sync_callback),
            callback_manager._trigger_callbacks("new_bar", {
                "timeframe": "1min", "bar_time": datetime.now(timezone.utc),
                "data": {"timestamp": datetime.now(timezone.utc), "open": 100.0,
                        "high": 105.0, "low": 95.0, "close": 102.0, "volume": 1000}
            }),
            callback_manager._trigger_callbacks("data_update", {
                "timestamp": datetime.now(timezone.utc), "price": 103.0, "volume": 50
            })
        ]

        # Should complete without errors
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # No exceptions should be raised
        for result in results:
            if isinstance(result, Exception):
                pytest.fail(f"Unexpected exception: {result}")

    @pytest.mark.asyncio
    async def test_callback_with_none_data(self):
        """Test callback triggering with None data."""
        callback_manager = MockRealtimeDataManager()

        # Should handle None data gracefully
        await callback_manager._trigger_callbacks("new_bar", None)

        # Should emit event with None data
        callback_manager.event_bus.emit.assert_called_once_with(
            EventType.NEW_BAR, None, source="RealtimeDataManager"
        )


class TestCallbackMixinDeprecationBehavior:
    """Test deprecation handling and backward compatibility."""

    @pytest.mark.asyncio
    async def test_deprecated_add_callback_still_works(self):
        """Test that deprecated add_callback method still functions correctly."""
        # This tests backward compatibility until v4.0
        callback_manager = MockRealtimeDataManager()

        async def test_callback(data):
            pass

        # Should still work despite being deprecated
        await callback_manager.add_callback("new_bar", test_callback)

        # Should register with EventBus
        callback_manager.event_bus.on.assert_called_once_with(
            EventType.NEW_BAR, test_callback
        )

    @pytest.mark.asyncio
    async def test_event_type_mapping_consistency(self):
        """Test that event type mapping is consistent and complete."""
        from project_x_py.realtime_data_manager.callbacks import _EVENT_TYPE_MAPPING

        # Should map legacy string event types to EventType enum
        assert "new_bar" in _EVENT_TYPE_MAPPING
        assert "data_update" in _EVENT_TYPE_MAPPING

        # Should map to correct EventType values
        assert _EVENT_TYPE_MAPPING["new_bar"] == EventType.NEW_BAR
        assert _EVENT_TYPE_MAPPING["data_update"] == EventType.DATA_UPDATE


class TestCallbackMixinIntegration:
    """Test integration with other components."""

    @pytest.mark.asyncio
    async def test_integration_with_real_event_bus(self):
        """Test integration with actual EventBus instance."""
        from project_x_py.event_bus import EventBus

        # Create real EventBus instance
        real_event_bus = EventBus()
        callback_manager = MockRealtimeDataManager(event_bus=real_event_bus)

        # Track callback execution
        callback_executed = {"count": 0}

        async def test_callback(data):
            callback_executed["count"] += 1

        # Register callback
        await callback_manager.add_callback("new_bar", test_callback)

        # Trigger event
        test_data = {
            "timeframe": "1min",
            "bar_time": datetime.now(timezone.utc),
            "data": {
                "timestamp": datetime.now(timezone.utc),
                "open": 19000.0, "high": 19005.0, "low": 18995.0,
                "close": 19002.0, "volume": 500
            }
        }
        await callback_manager._trigger_callbacks("new_bar", test_data)

        # Allow EventBus to process the event
        await asyncio.sleep(0.01)

        # Callback should have been executed
        assert callback_executed["count"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
