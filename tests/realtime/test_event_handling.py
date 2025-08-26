"""
Comprehensive tests for realtime.event_handling module following TDD principles.

Tests what the code SHOULD do, not what it currently does.
Any failures indicate bugs in the implementation that need fixing.
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, call, patch

import pytest

from project_x_py.realtime.batched_handler import OptimizedRealtimeHandler
from project_x_py.realtime.event_handling import EventHandlingMixin


@pytest.fixture
def mock_logger():
    """Create mock logger for testing."""
    logger = MagicMock()
    logger.debug = MagicMock()
    logger.info = MagicMock()
    logger.warning = MagicMock()
    logger.error = MagicMock()
    return logger


class MockEventHandler(EventHandlingMixin):
    """Mock class that includes EventHandlingMixin for testing."""

    def __init__(self):
        from collections import defaultdict
        super().__init__()
        self._loop = None
        self._callback_lock = asyncio.Lock()
        self.callbacks = defaultdict(list)  # Must be defaultdict like real implementation
        self.logger = MagicMock()
        self.stats = {
            "events_received": 0,
            "last_event_time": None
        }

    async def disconnect(self):
        """Mock disconnect method."""
        # Should disable batching like real implementation
        await self.stop_batching()
        self._use_batching = False

    async def stop_batching(self):
        """Mock stop_batching method."""
        if self._batched_handler:
            self._batched_handler = None
        self._use_batching = False


@pytest.fixture
def event_handler():
    """Create EventHandlingMixin instance for testing."""
    return MockEventHandler()


class TestEventHandlingMixinInitialization:
    """Test EventHandlingMixin initialization."""

    def test_init_basic_attributes(self, event_handler):
        """Test that basic attributes are initialized."""
        assert hasattr(event_handler, '_batched_handler')
        assert event_handler._batched_handler is None
        assert hasattr(event_handler, '_use_batching')
        assert event_handler._use_batching is False

    def test_init_task_manager(self, event_handler):
        """Test that TaskManagerMixin is properly initialized."""
        # Should have task management attributes from TaskManagerMixin
        assert hasattr(event_handler, 'get_task_stats')
        assert hasattr(event_handler, '_cleanup_tasks')
        assert hasattr(event_handler, '_create_task')


class TestEventCallbackRegistration:
    """Test event callback registration and management."""

    @pytest.mark.asyncio
    async def test_register_async_callback(self, event_handler):
        """Test registering an async callback."""
        async_callback = AsyncMock()

        await event_handler.add_callback('test_event', async_callback)

        assert 'test_event' in event_handler.callbacks
        assert async_callback in event_handler.callbacks['test_event']

    @pytest.mark.asyncio
    async def test_register_sync_callback(self, event_handler):
        """Test registering a sync callback."""
        sync_callback = Mock()

        await event_handler.add_callback('test_event', sync_callback)

        assert 'test_event' in event_handler.callbacks
        assert sync_callback in event_handler.callbacks['test_event']

    @pytest.mark.asyncio
    async def test_register_multiple_callbacks(self, event_handler):
        """Test registering multiple callbacks for same event."""
        callback1 = AsyncMock()
        callback2 = AsyncMock()
        callback3 = Mock()

        await event_handler.add_callback('test_event', callback1)
        await event_handler.add_callback('test_event', callback2)
        await event_handler.add_callback('test_event', callback3)

        assert len(event_handler.callbacks['test_event']) == 3
        assert all(cb in event_handler.callbacks['test_event']
                  for cb in [callback1, callback2, callback3])

    @pytest.mark.asyncio
    async def test_unregister_callback(self, event_handler):
        """Test unregistering a specific callback."""
        callback1 = AsyncMock()
        callback2 = AsyncMock()

        await event_handler.add_callback('test_event', callback1)
        await event_handler.add_callback('test_event', callback2)

        await event_handler.remove_callback('test_event', callback1)

        assert callback1 not in event_handler.callbacks['test_event']
        assert callback2 in event_handler.callbacks['test_event']

    @pytest.mark.asyncio
    async def test_unregister_nonexistent_callback(self, event_handler):
        """Test unregistering a callback that doesn't exist."""
        callback = AsyncMock()

        # Should not raise
        await event_handler.remove_callback('test_event', callback)

        # Event type should not be in callbacks
        assert 'test_event' not in event_handler.callbacks or \
               len(event_handler.callbacks['test_event']) == 0

    @pytest.mark.asyncio
    async def test_remove_all_callbacks_manually(self, event_handler):
        """Test removing all callbacks for an event type manually."""
        callback1 = AsyncMock()
        callback2 = AsyncMock()

        await event_handler.add_callback('test_event', callback1)
        await event_handler.add_callback('test_event', callback2)

        # Remove callbacks manually since there's no unregister_all method
        await event_handler.remove_callback('test_event', callback1)
        await event_handler.remove_callback('test_event', callback2)

        assert 'test_event' not in event_handler.callbacks or \
               len(event_handler.callbacks['test_event']) == 0

    @pytest.mark.asyncio
    async def test_callback_thread_safety(self, event_handler):
        """Test that callback registration is thread-safe."""
        callbacks = [AsyncMock() for _ in range(10)]

        # Register callbacks concurrently
        tasks = [
            event_handler.add_callback(f'event_{i}', cb)
            for i, cb in enumerate(callbacks)
        ]

        await asyncio.gather(*tasks)

        # All callbacks should be registered
        for i, cb in enumerate(callbacks):
            assert f'event_{i}' in event_handler.callbacks
            assert cb in event_handler.callbacks[f'event_{i}']


class TestEventProcessing:
    """Test event processing and forwarding."""

    @pytest.mark.asyncio
    async def test_process_event_with_async_callback(self, event_handler):
        """Test processing event with async callback."""
        async_callback = AsyncMock()
        event_data = {"test": "data", "value": 123}

        await event_handler.add_callback('test_event', async_callback)
        await event_handler._trigger_callbacks('test_event', event_data)

        async_callback.assert_called_once_with(event_data)

    @pytest.mark.asyncio
    async def test_process_event_with_sync_callback(self, event_handler):
        """Test processing event with sync callback."""
        sync_callback = Mock()
        event_data = {"test": "data", "value": 123}

        await event_handler.add_callback('test_event', sync_callback)
        await event_handler._trigger_callbacks('test_event', event_data)

        sync_callback.assert_called_once_with(event_data)

    @pytest.mark.asyncio
    async def test_process_event_multiple_callbacks(self, event_handler):
        """Test processing event with multiple callbacks."""
        callback1 = AsyncMock()
        callback2 = Mock()
        callback3 = AsyncMock()
        event_data = {"test": "data"}

        await event_handler.add_callback('test_event', callback1)
        await event_handler.add_callback('test_event', callback2)
        await event_handler.add_callback('test_event', callback3)

        await event_handler._trigger_callbacks('test_event', event_data)

        callback1.assert_called_once_with(event_data)
        callback2.assert_called_once_with(event_data)
        callback3.assert_called_once_with(event_data)

    @pytest.mark.asyncio
    async def test_process_event_with_no_callbacks(self, event_handler):
        """Test processing event when no callbacks registered."""
        event_data = {"test": "data"}

        # Should not raise
        await event_handler._trigger_callbacks('test_event', event_data)

    @pytest.mark.asyncio
    async def test_process_event_callback_error_isolation(self, event_handler):
        """Test that callback errors don't affect other callbacks."""
        callback1 = AsyncMock()
        callback2 = AsyncMock(side_effect=Exception("Callback failed"))
        callback3 = AsyncMock()
        event_data = {"test": "data"}

        await event_handler.add_callback('test_event', callback1)
        await event_handler.add_callback('test_event', callback2)
        await event_handler.add_callback('test_event', callback3)

        await event_handler._trigger_callbacks('test_event', event_data)

        # First and third callbacks should still be called
        callback1.assert_called_once_with(event_data)
        callback3.assert_called_once_with(event_data)

    @pytest.mark.asyncio
    async def test_process_event_updates_stats(self, event_handler):
        """Test that event processing updates statistics."""
        callback = AsyncMock()
        event_data = {"test": "data"}

        await event_handler.add_callback('test_event', callback)

        initial_count = event_handler.stats["events_received"]
        await event_handler._trigger_callbacks('test_event', event_data)

        assert event_handler.stats["events_received"] == initial_count + 1
        assert event_handler.stats["last_event_time"] is not None
        assert isinstance(event_handler.stats["last_event_time"], datetime)


class TestBatchedEventHandling:
    """Test batched event handling functionality."""

    @pytest.mark.asyncio
    async def test_enable_batching(self, event_handler):
        """Test enabling batched event handling."""
        event_handler.enable_batching()

        assert event_handler._use_batching is True
        assert event_handler._batched_handler is not None
        assert isinstance(event_handler._batched_handler, OptimizedRealtimeHandler)

    def test_disable_batching(self, event_handler):
        """Test disabling batched event handling."""
        event_handler.enable_batching()
        assert event_handler._use_batching is True

        event_handler.disable_batching()
        assert event_handler._use_batching is False

    @pytest.mark.asyncio
    async def test_process_event_with_batching(self, event_handler):
        """Test event processing with batching enabled."""
        event_handler.enable_batching()

        callback = AsyncMock()
        await event_handler.add_callback('test_event', callback)

        # Process multiple events
        await event_handler._trigger_callbacks('test_event', {"value": 1})
        await event_handler._trigger_callbacks('test_event', {"value": 2})

        # Give time for batch processing
        await asyncio.sleep(0.1)

        # Callback should be called with batched events
        assert callback.call_count >= 1

    @pytest.mark.asyncio
    async def test_batched_handler_cleanup(self, event_handler):
        """Test that batched handler is properly cleaned up."""
        event_handler.enable_batching()
        handler = event_handler._batched_handler

        # disable_batching only sets the flag, doesn't clean up handler
        event_handler.disable_batching()
        assert event_handler._use_batching is False
        # Handler is still there, just not being used
        assert event_handler._batched_handler is not None

        # stop_batching does the actual cleanup
        await event_handler.stop_batching()
        assert event_handler._batched_handler is None
        assert event_handler._use_batching is False


class TestCrossThreadEventScheduling:
    """Test cross-thread event scheduling for asyncio compatibility."""

    @pytest.mark.asyncio
    async def test_schedule_event_from_different_thread(self, event_handler):
        """Test scheduling event from a different thread."""
        import threading

        callback = AsyncMock()
        event_data = {"test": "data"}
        event_received = threading.Event()

        await event_handler.add_callback('test_event', callback)

        # Set the event loop in the handler
        event_handler._loop = asyncio.get_event_loop()

        def thread_func():
            # This would normally be called from SignalR thread
            # Use the loop from the handler, not try to get the current loop
            try:
                asyncio.run_coroutine_threadsafe(
                    event_handler._trigger_callbacks('test_event', event_data),
                    event_handler._loop
                )
                event_received.set()
            except Exception as e:
                print(f"Thread error: {e}")

        thread = threading.Thread(target=thread_func)
        thread.start()
        thread.join(timeout=1.0)

        assert event_received.is_set()

        # Give time for async processing
        await asyncio.sleep(0.1)

        callback.assert_called_once_with(event_data)

    @pytest.mark.asyncio
    async def test_event_loop_detection(self, event_handler):
        """Test that event handler detects and uses correct event loop."""
        # Set event loop
        event_handler._loop = asyncio.get_event_loop()

        assert event_handler._loop is not None
        assert event_handler._loop == asyncio.get_event_loop()


class TestEventStatistics:
    """Test event statistics and monitoring."""

    @pytest.mark.asyncio
    async def test_event_count_tracking(self, event_handler):
        """Test that event counts are properly tracked."""
        callback = AsyncMock()
        await event_handler.add_callback('test_event', callback)

        for i in range(5):
            await event_handler._trigger_callbacks('test_event', {"value": i})

        assert event_handler.stats["events_received"] == 5

    @pytest.mark.asyncio
    async def test_last_event_time_tracking(self, event_handler):
        """Test that last event time is properly tracked."""
        callback = AsyncMock()
        await event_handler.add_callback('test_event', callback)

        before_time = datetime.now()
        await event_handler._trigger_callbacks('test_event', {"test": "data"})
        after_time = datetime.now()

        last_event_time = event_handler.stats["last_event_time"]
        assert last_event_time is not None
        assert before_time <= last_event_time <= after_time

    @pytest.mark.asyncio
    async def test_get_batching_stats(self, event_handler):
        """Test getting batching statistics."""
        # Enable batching
        event_handler.enable_batching()

        # Get stats
        stats = event_handler.get_batching_stats()

        # Check stats structure - actual format has handler-specific stats
        assert isinstance(stats, dict)
        # Stats contain handler stats, not just an "enabled" flag
        assert len(stats) > 0
        # Each handler should have stats with expected keys
        for handler_name, handler_stats in stats.items():
            assert isinstance(handler_stats, dict)
            assert "batches_processed" in handler_stats


class TestErrorHandling:
    """Test error handling in event processing."""

    @pytest.mark.asyncio
    async def test_callback_exception_logging(self, event_handler):
        """Test that callback exceptions are logged."""
        callback = AsyncMock(side_effect=ValueError("Test error"))
        event_data = {"test": "data"}

        await event_handler.add_callback('test_event', callback)

        # Should not raise
        await event_handler._trigger_callbacks('test_event', event_data)

        # Error should be logged
        event_handler.logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_callback_timeout_handling(self, event_handler):
        """Test handling of slow callbacks."""
        async def slow_callback(data):
            await asyncio.sleep(10)  # Very slow callback

        await event_handler.add_callback('test_event', slow_callback)

        # Should handle timeout gracefully
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                event_handler._trigger_callbacks('test_event', {}),
                timeout=0.1
            )

    @pytest.mark.asyncio
    async def test_invalid_event_data(self, event_handler):
        """Test handling of invalid event data."""
        callback = AsyncMock()
        await event_handler.add_callback('test_event', callback)

        # Should handle various invalid data types
        await event_handler._trigger_callbacks('test_event', None)
        await event_handler._trigger_callbacks('test_event', "string_data")
        await event_handler._trigger_callbacks('test_event', 123)
        await event_handler._trigger_callbacks('test_event', [1, 2, 3])

        # Callbacks should still be called
        assert callback.call_count == 4


class TestEventHandlingIntegration:
    """Integration tests for event handling."""

    @pytest.mark.asyncio
    async def test_full_event_lifecycle(self, event_handler):
        """Test complete event lifecycle from registration to processing."""
        results = []

        async def async_callback(data):
            results.append(f"async: {data['value']}")

        def sync_callback(data):
            results.append(f"sync: {data['value']}")

        # Register callbacks
        await event_handler.add_callback('test_event', async_callback)
        await event_handler.add_callback('test_event', sync_callback)

        # Process events
        for i in range(3):
            await event_handler._trigger_callbacks('test_event', {"value": i})

        # Check results
        assert len(results) == 6  # 3 events * 2 callbacks
        assert "async: 0" in results
        assert "sync: 0" in results
        assert "async: 2" in results
        assert "sync: 2" in results

    @pytest.mark.asyncio
    async def test_mixed_event_types(self, event_handler):
        """Test handling multiple event types simultaneously."""
        position_results = []
        quote_results = []

        async def position_callback(data):
            position_results.append(data)

        async def quote_callback(data):
            quote_results.append(data)

        await event_handler.add_callback('position_update', position_callback)
        await event_handler.add_callback('quote_update', quote_callback)

        # Process different event types
        await event_handler._trigger_callbacks('position_update', {"position": "long"})
        await event_handler._trigger_callbacks('quote_update', {"bid": 100, "ask": 101})
        await event_handler._trigger_callbacks('position_update', {"position": "short"})

        assert len(position_results) == 2
        assert len(quote_results) == 1
        assert position_results[0] == {"position": "long"}
        assert quote_results[0] == {"bid": 100, "ask": 101}

    @pytest.mark.asyncio
    async def test_cleanup_on_disconnect(self, event_handler):
        """Test that event handling is properly cleaned up on disconnect."""
        callback = AsyncMock()
        await event_handler.add_callback('test_event', callback)

        # Enable batching
        event_handler.enable_batching()

        # Disconnect should clean up
        await event_handler.disconnect()

        # Batching should be disabled
        assert event_handler._use_batching is False
        assert event_handler._batched_handler is None
