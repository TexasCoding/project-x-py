"""Comprehensive tests for OrderManager tracking functionality."""

import asyncio
import time
from collections import deque
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cachetools import TTLCache

from project_x_py.event_bus import EventBus, EventType
from project_x_py.models import Order, OrderPlaceResponse
from project_x_py.order_manager.tracking import OrderTrackingMixin


class MockOrderManager(OrderTrackingMixin):
    """Mock OrderManager that includes tracking mixin for testing."""

    def __init__(self):
        super().__init__()
        self.project_x = MagicMock()
        self.realtime_client = None
        self._realtime_enabled = False
        self.order_lock = asyncio.Lock()
        self.event_bus = EventBus()
        self.stats = {"orders_filled": 0, "orders_rejected": 0, "orders_expired": 0}

    async def cancel_order(self, order_id: int, account_id: int | None = None) -> bool:
        """Mock cancel_order method."""
        return True

    async def increment(self, stat_name: str) -> None:
        """Mock increment method for statistics."""
        self.stats[stat_name] = self.stats.get(stat_name, 0) + 1


@pytest.fixture
def mock_order_manager():
    """Create a mock order manager with tracking mixin."""
    return MockOrderManager()


@pytest.fixture
def sample_order_data():
    """Sample order data for testing."""
    return {
        "id": 12345,
        "status": 1,
        "contractId": "MNQ",
        "side": 0,
        "size": 2,
        "price": 17000.0,
        "fills": [],
        "type": 2,
        "accountId": 67890,
        "filledSize": 0,
        "remainingSize": 2,
    }


class TestOrderTrackingMixin:
    """Test suite for OrderTrackingMixin functionality."""

    def test_tracking_initialization(self, mock_order_manager):
        """Test that tracking attributes are properly initialized."""
        om = mock_order_manager

        # Test TTL caches
        assert isinstance(om.tracked_orders, TTLCache)
        assert isinstance(om.order_status_cache, TTLCache)
        assert om.tracked_orders.maxsize == 10000
        assert om.tracked_orders.ttl == 3600

        # Test collections
        assert isinstance(om.position_orders, dict)
        assert isinstance(om.order_to_position, dict)
        assert isinstance(om.oco_groups, dict)
        assert isinstance(om._completed_orders, deque)
        assert om._completed_orders.maxlen == 1000

        # Test configuration
        assert om._max_tracked_orders == 10000
        assert om._order_ttl_seconds == 3600
        assert om._cleanup_interval == 300
        assert om._cleanup_enabled is True
        assert om._max_background_tasks == 100
        assert om._max_cancellation_attempts == 3
        assert om._failure_cooldown_seconds == 60

        # Test statistics
        assert "total_orders_tracked" in om._memory_stats
        assert "orders_cleaned" in om._memory_stats
        assert "last_cleanup_time" in om._memory_stats
        assert "peak_tracked_orders" in om._memory_stats

    def test_link_oco_orders_success(self, mock_order_manager):
        """Test successful OCO order linking."""
        om = mock_order_manager

        om._link_oco_orders(101, 102)

        assert om.oco_groups[101] == 102
        assert om.oco_groups[102] == 101

    def test_link_oco_orders_invalid_input(self, mock_order_manager):
        """Test OCO linking with invalid input."""
        om = mock_order_manager

        # Test non-integer input
        with pytest.raises(ValueError, match="Order IDs must be integers"):
            om._link_oco_orders("101", 102)

        # Test same order ID
        with pytest.raises(ValueError, match="Cannot link order to itself"):
            om._link_oco_orders(101, 101)

    def test_link_oco_orders_existing_links(self, mock_order_manager):
        """Test OCO linking with existing links."""
        om = mock_order_manager

        # Set up existing link
        om.oco_groups[101] = 103
        om.oco_groups[103] = 101

        # Link to new order should break existing link
        om._link_oco_orders(101, 102)

        assert om.oco_groups[101] == 102
        assert om.oco_groups[102] == 101
        assert 103 not in om.oco_groups

    def test_unlink_oco_orders(self, mock_order_manager):
        """Test OCO order unlinking."""
        om = mock_order_manager

        # Set up link
        om._link_oco_orders(101, 102)

        # Unlink
        linked_id = om._unlink_oco_orders(101)

        assert linked_id == 102
        assert 101 not in om.oco_groups
        assert 102 not in om.oco_groups

    def test_unlink_oco_orders_no_link(self, mock_order_manager):
        """Test unlinking when no link exists."""
        om = mock_order_manager

        linked_id = om._unlink_oco_orders(101)

        assert linked_id is None

    @pytest.mark.asyncio
    async def test_get_oco_linked_order(self, mock_order_manager):
        """Test getting OCO linked order."""
        om = mock_order_manager

        om._link_oco_orders(101, 102)

        linked_id = await om.get_oco_linked_order(101)
        assert linked_id == 102

        # Test non-existent order
        linked_id = await om.get_oco_linked_order(999)
        assert linked_id is None

    @pytest.mark.asyncio
    async def test_create_managed_task_success(self, mock_order_manager):
        """Test successful managed task creation."""
        om = mock_order_manager

        async def dummy_coro():
            return "success"

        task = om._create_managed_task(dummy_coro(), "test_task")

        assert task is not None
        assert task in om._background_tasks
        assert len(om._background_tasks) == 1

        # Clean up the task
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_create_managed_task_limit_reached(self, mock_order_manager):
        """Test managed task creation when limit is reached."""
        om = mock_order_manager
        om._max_background_tasks = 1

        async def dummy_coro():
            await asyncio.sleep(0.1)
            return "success"

        # Create first task (should succeed)
        task1 = om._create_managed_task(dummy_coro(), "task1")
        assert task1 is not None

        # Create second task (should fail due to limit)
        task2 = om._create_managed_task(dummy_coro(), "task2")
        assert task2 is None

        # Clean up
        task1.cancel()
        try:
            await task1
        except asyncio.CancelledError:
            pass

    def test_create_managed_task_shutdown_in_progress(self, mock_order_manager):
        """Test managed task creation during shutdown."""
        om = mock_order_manager
        om._shutdown_event.set()

        async def dummy_coro():
            return "success"

        task = om._create_managed_task(dummy_coro(), "test_task")
        assert task is None

    def test_should_retry_cancellation_initial(self, mock_order_manager):
        """Test cancellation retry logic for new order."""
        om = mock_order_manager

        should_retry = om._should_retry_cancellation(101)
        assert should_retry is True

    def test_should_retry_cancellation_circuit_breaker(self, mock_order_manager):
        """Test cancellation circuit breaker functionality."""
        om = mock_order_manager

        # Record multiple failures
        current_time = time.time()
        om._cancellation_failures[101] = 3
        om._cancellation_failures["101_last_failure"] = current_time

        should_retry = om._should_retry_cancellation(101)
        assert should_retry is False

    def test_should_retry_cancellation_cooldown_expired(self, mock_order_manager):
        """Test cancellation retry after cooldown expires."""
        om = mock_order_manager

        # Set up old failure
        old_time = time.time() - 3600  # 1 hour ago
        om._cancellation_failures[101] = 3
        om._cancellation_failures["101_last_failure"] = old_time

        should_retry = om._should_retry_cancellation(101)
        assert should_retry is True
        assert om._cancellation_failures[101] == 0

    def test_record_cancellation_failure(self, mock_order_manager):
        """Test recording cancellation failures."""
        om = mock_order_manager

        om._record_cancellation_failure(101)

        assert om._cancellation_failures[101] == 1
        assert "101_last_failure" in om._cancellation_failures

        # Record another failure
        om._record_cancellation_failure(101)
        assert om._cancellation_failures[101] == 2

    def test_record_cancellation_success(self, mock_order_manager):
        """Test recording cancellation success."""
        om = mock_order_manager

        # Set up some failures
        om._cancellation_failures[101] = 2
        om._cancellation_failures["101_last_failure"] = time.time()

        om._record_cancellation_success(101)

        assert 101 not in om._cancellation_failures
        assert "101_last_failure" not in om._cancellation_failures

    def test_extract_order_data_direct_dict(self, mock_order_manager, sample_order_data):
        """Test order data extraction from direct dictionary."""
        om = mock_order_manager

        extracted = om._extract_order_data(sample_order_data)

        assert extracted == sample_order_data
        assert extracted["id"] == 12345

    def test_extract_order_data_list_format(self, mock_order_manager, sample_order_data):
        """Test order data extraction from list formats."""
        om = mock_order_manager

        # Single item list
        extracted = om._extract_order_data([sample_order_data])
        assert extracted == sample_order_data

        # Multiple item list with data as second item
        extracted = om._extract_order_data([12345, sample_order_data])
        assert extracted == sample_order_data

        # Multiple item list with data as first item
        extracted = om._extract_order_data([sample_order_data, "other"])
        assert extracted == sample_order_data

    def test_extract_order_data_nested_format(self, mock_order_manager, sample_order_data):
        """Test order data extraction from nested formats."""
        om = mock_order_manager

        # Data wrapper
        nested = {"data": sample_order_data}
        extracted = om._extract_order_data(nested)
        assert extracted == sample_order_data

        # Result wrapper
        nested = {"result": sample_order_data}
        extracted = om._extract_order_data(nested)
        assert extracted == sample_order_data

        # List in data
        nested = {"data": [sample_order_data]}
        extracted = om._extract_order_data(nested)
        assert extracted == sample_order_data

    def test_extract_order_data_invalid_input(self, mock_order_manager):
        """Test order data extraction with invalid input."""
        om = mock_order_manager

        # None input
        extracted = om._extract_order_data(None)
        assert extracted is None

        # Empty list
        extracted = om._extract_order_data([])
        assert extracted is None

        # String input
        extracted = om._extract_order_data("invalid")
        assert extracted is None

        # Dict without id
        extracted = om._extract_order_data({"status": 1})
        assert extracted is None

    def test_validate_order_data_success(self, mock_order_manager, sample_order_data):
        """Test successful order data validation."""
        om = mock_order_manager

        validated = om._validate_order_data(sample_order_data)

        assert validated is not None
        assert validated["id"] == 12345
        assert isinstance(validated["size"], float)
        assert isinstance(validated["price"], float)

    def test_validate_order_data_invalid_input(self, mock_order_manager):
        """Test order data validation with invalid input."""
        om = mock_order_manager

        # Non-dict input
        validated = om._validate_order_data("invalid")
        assert validated is None

        # Dict without id
        validated = om._validate_order_data({"status": 1})
        assert validated is None

        # Invalid order ID
        validated = om._validate_order_data({"id": "invalid"})
        assert validated is None

    def test_validate_order_data_status_validation(self, mock_order_manager):
        """Test order data validation with various status values."""
        om = mock_order_manager

        # Valid status
        validated = om._validate_order_data({"id": 123, "status": 2})
        assert validated is not None

        # Invalid status (out of range) - should still validate but warn
        validated = om._validate_order_data({"id": 123, "status": 15})
        assert validated is not None

        # Invalid status type
        validated = om._validate_order_data({"id": 123, "status": "invalid"})
        assert validated is not None  # Should still validate, just log warning

    def test_validate_order_data_fills_array(self, mock_order_manager):
        """Test order data validation with fills array."""
        om = mock_order_manager

        # Valid fills array
        validated = om._validate_order_data({
            "id": 123,
            "fills": [{"size": 1, "price": 100.0}]
        })
        assert validated is not None
        assert isinstance(validated["fills"], list)

        # Invalid fills type - should be converted to empty list
        validated = om._validate_order_data({
            "id": 123,
            "fills": "invalid"
        })
        assert validated is not None
        assert validated["fills"] == []

    @pytest.mark.asyncio
    async def test_on_order_update_success(self, mock_order_manager, sample_order_data):
        """Test successful order update processing."""
        om = mock_order_manager

        # Mock the event bus emit method
        om.event_bus.emit = AsyncMock()

        await om._on_order_update(sample_order_data)

        # Check order was added to cache
        order_id_str = str(sample_order_data["id"])
        assert order_id_str in om.tracked_orders
        assert om.order_status_cache[order_id_str] == sample_order_data["status"]

        # Check memory stats were updated
        assert om._memory_stats["total_orders_tracked"] > 0

    @pytest.mark.asyncio
    async def test_on_order_update_invalid_data(self, mock_order_manager):
        """Test order update with invalid data."""
        om = mock_order_manager

        await om._on_order_update(None)
        await om._on_order_update("invalid")
        await om._on_order_update({})

        # No orders should be tracked
        assert len(om.tracked_orders) == 0

    @pytest.mark.asyncio
    async def test_on_order_update_status_change_events(self, mock_order_manager):
        """Test that status changes trigger appropriate events."""
        om = mock_order_manager

        # Mock event bus - add a proper mock
        om.event_bus = MagicMock()
        om.event_bus.emit = AsyncMock()

        # Test filled status with complete order data
        order_data = {
            "id": 123,
            "status": 2,  # Filled
            "accountId": 1,
            "contractId": "MNQ",
            "creationTimestamp": "2024-01-01T00:00:00Z",
            "updateTimestamp": "2024-01-01T00:00:01Z",
            "type": 1,  # Limit
            "side": 0,  # Buy
            "size": 1
        }
        await om._on_order_update(order_data)

        # Should have emitted ORDER_FILLED event
        assert om.event_bus.emit.called
        if om.event_bus.emit.called:
            call_args = om.event_bus.emit.call_args
            assert call_args[0][0] == EventType.ORDER_FILLED

    @pytest.mark.asyncio
    async def test_on_order_update_oco_cancellation(self, mock_order_manager):
        """Test OCO order cancellation on fill."""
        om = mock_order_manager

        # Set up OCO pair
        om._link_oco_orders(123, 456)

        # Mock cancel_order method
        om.cancel_order = AsyncMock(return_value=True)

        # Process fill for first order with complete order data
        order_data = {
            "id": 123,
            "status": 2,  # Filled
            "accountId": 1,
            "contractId": "MNQ",
            "creationTimestamp": "2024-01-01T00:00:00Z",
            "updateTimestamp": "2024-01-01T00:00:01Z",
            "type": 1,  # Limit
            "side": 0,  # Buy
            "size": 1
        }
        await om._on_order_update(order_data)

        # Allow time for background task to complete
        await asyncio.sleep(0.1)

        # Should have attempted to cancel the OCO order
        # Note: The actual cancel call happens in a background task
        # We need to check that the task was created
        assert len(om._background_tasks) > 0 or om.cancel_order.called

    @pytest.mark.asyncio
    async def test_on_order_update_partial_fill_detection(self, mock_order_manager):
        """Test partial fill detection and event emission."""
        om = mock_order_manager

        # Mock event bus
        om.event_bus.emit = AsyncMock()

        order_data = {
            "id": 123,
            "status": 1,  # Partially filled
            "size": 10,
            "fills": [
                {"size": 3, "price": 100.0},
                {"size": 2, "price": 100.5}
            ]
        }

        await om._on_order_update(order_data)

        # Should detect partial fill and trigger callback
        # The partial fill logic triggers when filled_size < total_size > 0
        assert om.event_bus.emit.called

    @pytest.mark.asyncio
    async def test_get_tracked_order_status_immediate(self, mock_order_manager):
        """Test immediate order status retrieval."""
        om = mock_order_manager

        order_data = {"id": 123, "status": 1}
        om.tracked_orders["123"] = order_data

        result = await om.get_tracked_order_status("123")
        assert result == order_data

    @pytest.mark.asyncio
    async def test_get_tracked_order_status_with_wait(self, mock_order_manager):
        """Test order status retrieval with cache wait."""
        om = mock_order_manager
        om._realtime_enabled = True

        # Initially empty
        result = await om.get_tracked_order_status("123", wait_for_cache=True)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_tracked_order_status_populated_during_wait(self, mock_order_manager):
        """Test order status populated during wait."""
        om = mock_order_manager
        om._realtime_enabled = True

        async def populate_cache():
            await asyncio.sleep(0.1)
            order_data = {"id": 123, "status": 1}
            async with om.order_lock:
                om.tracked_orders["123"] = order_data

        # Start background task to populate cache
        asyncio.create_task(populate_cache())

        result = await om.get_tracked_order_status("123", wait_for_cache=True)
        assert result is not None
        assert result["id"] == 123

    @pytest.mark.asyncio
    async def test_trigger_callbacks_with_event_bus(self, mock_order_manager):
        """Test callback triggering through EventBus."""
        om = mock_order_manager

        # Mock event bus
        om.event_bus.emit = AsyncMock()

        test_data = {"order_id": 123, "status": 2}
        await om._trigger_callbacks("order_filled", test_data)

        # Should have emitted through EventBus
        om.event_bus.emit.assert_called_once()
        call_args = om.event_bus.emit.call_args
        assert call_args[0][0] == EventType.ORDER_FILLED
        assert call_args[0][1] == test_data

    @pytest.mark.asyncio
    async def test_trigger_callbacks_no_event_bus(self, mock_order_manager):
        """Test callback handling when no EventBus is available."""
        om = mock_order_manager
        om.event_bus = None

        # Should not raise an exception
        await om._trigger_callbacks("order_filled", {"order_id": 123})

    @pytest.mark.asyncio
    async def test_start_cleanup_task(self, mock_order_manager):
        """Test starting the cleanup background task."""
        om = mock_order_manager

        await om._start_cleanup_task()

        assert om._cleanup_task is not None
        assert not om._cleanup_task.done()

        # Clean up
        await om._stop_cleanup_task()

    @pytest.mark.asyncio
    async def test_stop_cleanup_task(self, mock_order_manager):
        """Test stopping the cleanup background task."""
        om = mock_order_manager

        # Start task first
        await om._start_cleanup_task()
        initial_task = om._cleanup_task

        # Stop task
        await om._stop_cleanup_task()

        assert om._cleanup_enabled is False
        assert initial_task.done()

    @pytest.mark.asyncio
    async def test_shutdown_background_tasks(self, mock_order_manager):
        """Test graceful shutdown of all background tasks."""
        om = mock_order_manager

        # Create some background tasks
        async def dummy_task():
            await asyncio.sleep(1)

        task1 = om._create_managed_task(dummy_task(), "task1")
        task2 = om._create_managed_task(dummy_task(), "task2")

        assert len(om._background_tasks) == 2

        # Shutdown tasks
        await om.shutdown_background_tasks()

        assert om._shutdown_event.is_set()
        assert len(om._background_tasks) == 0

    def test_get_task_monitoring_stats(self, mock_order_manager):
        """Test task monitoring statistics."""
        om = mock_order_manager

        # Add some test data
        om._task_results[123] = "SUCCESS"
        om._task_results[456] = "CANCELLED"
        om._task_results[789] = Exception("Test error")

        stats = om.get_task_monitoring_stats()

        assert stats["active_background_tasks"] == 0
        assert stats["max_background_tasks"] == 100
        # Fix expectations based on how the logic actually works
        assert stats["completed_tasks"] == 2  # SUCCESS + Exception are both "completed"
        assert stats["cancelled_tasks"] == 1
        assert stats["failed_tasks"] == 1
        assert stats["total_task_results"] == 3
        assert stats["shutdown_signaled"] is False

    @pytest.mark.asyncio
    async def test_periodic_cleanup(self, mock_order_manager):
        """Test periodic cleanup functionality."""
        om = mock_order_manager
        om._cleanup_interval = 0.1  # Fast cleanup for testing

        # Add some test data
        current_time = time.time()
        om._completed_orders.append(("123", current_time - 10000))  # Old order
        om.order_to_position[123] = "MNQ"
        om._link_oco_orders(123, 456)

        # Run one cleanup cycle
        await om._cleanup_completed_orders()

        # Old order should be cleaned up
        assert len(om._completed_orders) == 0
        assert 123 not in om.order_to_position
        assert 123 not in om.oco_groups

    def test_get_memory_stats(self, mock_order_manager):
        """Test memory statistics retrieval."""
        om = mock_order_manager

        # Add some test data
        om.tracked_orders["123"] = {"id": 123}
        om.order_status_cache["123"] = 1
        om.position_orders["MNQ"] = {"entry_orders": [123]}

        stats = om.get_memory_stats()

        assert stats["tracked_orders_count"] == 1
        assert stats["cached_statuses_count"] == 1
        assert stats["position_mappings_count"] == 0
        assert stats["monitored_positions_count"] == 1
        assert stats["max_tracked_orders"] == 10000
        assert stats["order_ttl_seconds"] == 3600
        assert "background_tasks" in stats

    @pytest.mark.asyncio
    async def test_configure_memory_limits(self, mock_order_manager):
        """Test memory limit configuration."""
        om = mock_order_manager

        # Add some test data
        for i in range(5):
            om.tracked_orders[str(i)] = {"id": i}
            om.order_status_cache[str(i)] = 1

        # Configure new limits
        await om.configure_memory_limits(
            max_tracked_orders=3,
            order_ttl_seconds=1800,
            cleanup_interval=150
        )

        assert om._max_tracked_orders == 3
        assert om._order_ttl_seconds == 1800
        assert om._cleanup_interval == 150

        # Should have kept most recent 3 orders
        assert len(om.tracked_orders) <= 3

    def test_clear_order_tracking(self, mock_order_manager):
        """Test clearing all tracking data."""
        om = mock_order_manager

        # Add test data
        om.tracked_orders["123"] = {"id": 123}
        om.order_status_cache["123"] = 1
        om.position_orders["MNQ"] = {"entry_orders": [123]}
        om.order_to_position[123] = "MNQ"
        om._link_oco_orders(123, 456)
        om._completed_orders.append(("123", time.time()))
        om._memory_stats["total_orders_tracked"] = 10

        om.clear_order_tracking()

        # All data should be cleared
        assert len(om.tracked_orders) == 0
        assert len(om.order_status_cache) == 0
        assert len(om.position_orders) == 0
        assert len(om.order_to_position) == 0
        assert len(om.oco_groups) == 0
        assert len(om._completed_orders) == 0
        assert om._memory_stats["total_orders_tracked"] == 0

    def test_get_realtime_validation_status(self, mock_order_manager):
        """Test realtime validation status."""
        om = mock_order_manager

        # Add some test data
        om._realtime_enabled = True
        om.tracked_orders["123"] = {"id": 123}
        om.order_status_cache["123"] = 1
        om.position_orders["MNQ"] = {"entry_orders": [123]}

        status = om.get_realtime_validation_status()

        assert status["realtime_enabled"] is True
        assert status["tracked_orders"] == 1
        assert status["order_cache_size"] == 1
        assert status["monitored_positions"] == 1
        assert "memory_health" in status
        assert "usage_ratio" in status["memory_health"]

    @pytest.mark.asyncio
    async def test_wait_for_order_fill_already_filled(self, mock_order_manager):
        """Test waiting for order fill when already filled."""
        om = mock_order_manager

        # Order already filled in cache
        order_data = {"id": 123, "status": 2}  # FILLED
        om.tracked_orders["123"] = order_data

        result = await om._wait_for_order_fill(123, timeout_seconds=1)
        assert result is True

    @pytest.mark.asyncio
    async def test_wait_for_order_fill_event_driven(self, mock_order_manager):
        """Test event-driven order fill waiting."""
        om = mock_order_manager

        async def trigger_fill():
            await asyncio.sleep(0.1)
            # Simulate fill event
            event_data = {
                "order_id": 123,
                "order": {"id": 123},
                "status": 2
            }
            await om.event_bus.emit(EventType.ORDER_FILLED, event_data)

        # Start background task to trigger fill event
        asyncio.create_task(trigger_fill())

        result = await om._wait_for_order_fill(123, timeout_seconds=1)
        assert result is True

    @pytest.mark.asyncio
    async def test_wait_for_order_fill_cancelled(self, mock_order_manager):
        """Test waiting for order fill but order gets cancelled."""
        om = mock_order_manager

        async def trigger_cancel():
            await asyncio.sleep(0.1)
            # Simulate cancel event
            event_data = {
                "order_id": 123,
                "order": {"id": 123},
                "status": 3
            }
            await om.event_bus.emit(EventType.ORDER_CANCELLED, event_data)

        # Start background task to trigger cancel event
        asyncio.create_task(trigger_cancel())

        result = await om._wait_for_order_fill(123, timeout_seconds=1)
        assert result is False

    @pytest.mark.asyncio
    async def test_wait_for_order_fill_timeout(self, mock_order_manager):
        """Test order fill wait timeout."""
        om = mock_order_manager

        result = await om._wait_for_order_fill(123, timeout_seconds=0.1)
        assert result is False

    def test_extract_trade_data_success(self, mock_order_manager):
        """Test successful trade data extraction."""
        om = mock_order_manager

        trade_data = {
            "orderId": 123,
            "size": 2,
            "price": 100.0,
            "timestamp": "2023-01-01T12:00:00Z"
        }

        extracted = om._extract_trade_data(trade_data)
        assert extracted == trade_data

    def test_extract_trade_data_nested(self, mock_order_manager):
        """Test trade data extraction from nested structures."""
        om = mock_order_manager

        trade_data = {"orderId": 123, "size": 2}
        nested = {"data": trade_data}

        extracted = om._extract_trade_data(nested)
        assert extracted == trade_data

    def test_validate_trade_data_success(self, mock_order_manager):
        """Test successful trade data validation."""
        om = mock_order_manager

        trade_data = {"orderId": 123, "size": 2, "price": 100.0}

        validated = om._validate_trade_data(trade_data)
        assert validated is not None
        assert validated["orderId"] == 123

    def test_validate_trade_data_alternative_fields(self, mock_order_manager):
        """Test trade data validation with alternative field names."""
        om = mock_order_manager

        trade_data = {"order_id": 123, "size": 2}

        validated = om._validate_trade_data(trade_data)
        assert validated is not None
        assert validated["orderId"] == 123

    def test_validate_trade_data_invalid(self, mock_order_manager):
        """Test trade data validation with invalid data."""
        om = mock_order_manager

        # No order ID
        validated = om._validate_trade_data({"size": 2})
        assert validated is None

        # Invalid order ID
        validated = om._validate_trade_data({"orderId": "invalid"})
        assert validated is None

    @pytest.mark.asyncio
    async def test_on_trade_execution_success(self, mock_order_manager):
        """Test successful trade execution handling."""
        om = mock_order_manager

        # Set up tracked order
        order_data = {"id": 123, "fills": []}
        om.tracked_orders["123"] = order_data

        trade_data = {"orderId": 123, "size": 2, "price": 100.0}

        await om._on_trade_execution(trade_data)

        # Should have added trade to fills
        assert len(om.tracked_orders["123"]["fills"]) == 1
        assert om.tracked_orders["123"]["fills"][0] == trade_data

    @pytest.mark.asyncio
    async def test_on_trade_execution_untracked_order(self, mock_order_manager):
        """Test trade execution for untracked order."""
        om = mock_order_manager

        trade_data = {"orderId": 999, "size": 2, "price": 100.0}

        # Should not raise an exception
        await om._on_trade_execution(trade_data)

    @pytest.mark.asyncio
    async def test_on_trade_execution_invalid_data(self, mock_order_manager):
        """Test trade execution with invalid data."""
        om = mock_order_manager

        # Should not raise exceptions
        await om._on_trade_execution(None)
        await om._on_trade_execution("invalid")
        await om._on_trade_execution({})

    @pytest.mark.asyncio
    async def test_process_order_update_compat(self, mock_order_manager, sample_order_data):
        """Test backward compatibility wrapper for _process_order_update."""
        om = mock_order_manager

        await om._process_order_update(sample_order_data)

        # Should work the same as _on_order_update
        order_id_str = str(sample_order_data["id"])
        assert order_id_str in om.tracked_orders

    def test_deprecated_add_callback(self, mock_order_manager):
        """Test deprecated add_callback method."""
        om = mock_order_manager

        def dummy_callback(data):
            pass

        # Should not raise an exception (deprecation warning only)
        om.add_callback("order_filled", dummy_callback)

    @pytest.mark.asyncio
    async def test_setup_realtime_callbacks_no_client(self, mock_order_manager):
        """Test realtime callback setup when no client is available."""
        om = mock_order_manager
        om.realtime_client = None

        # Should not raise an exception
        await om._setup_realtime_callbacks()

    @pytest.mark.asyncio
    async def test_setup_realtime_callbacks_with_client(self, mock_order_manager):
        """Test realtime callback setup with client."""
        om = mock_order_manager

        # Mock realtime client
        om.realtime_client = MagicMock()
        om.realtime_client.add_callback = AsyncMock()

        await om._setup_realtime_callbacks()

        # Should have registered callbacks
        assert om.realtime_client.add_callback.call_count == 2


class TestOrderTrackingEdgeCases:
    """Test edge cases and error conditions for order tracking."""

    @pytest.mark.asyncio
    async def test_task_callback_exception_handling(self, mock_order_manager):
        """Test that task completion callback handles exceptions."""
        om = mock_order_manager

        # Create task that will raise exception in callback
        async def dummy_coro():
            return "success"

        task = om._create_managed_task(dummy_coro(), "test_task")

        # Manually trigger callback with exception
        callback = task._callbacks[0][0]  # Get the callback function

        # Create a mock task that raises exception in result()
        mock_task = MagicMock()
        mock_task.cancelled.return_value = False
        mock_task.exception.return_value = Exception("Test error")
        mock_task.result.side_effect = Exception("Test error")

        # Should not raise exception
        callback(mock_task)

        # Clean up
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_order_update_with_exception(self, mock_order_manager):
        """Test order update processing with exceptions."""
        om = mock_order_manager

        # Mock validate_order_data to raise exception
        with patch.object(om, '_validate_order_data', side_effect=Exception("Test error")):
            # Should not raise exception, just log error
            await om._on_order_update({"id": 123, "status": 1})

        # No orders should be tracked
        assert len(om.tracked_orders) == 0

    @pytest.mark.asyncio
    async def test_oco_cancellation_with_failure(self, mock_order_manager):
        """Test OCO cancellation when cancel_order fails."""
        om = mock_order_manager

        # Set up OCO pair
        om._link_oco_orders(123, 456)

        # Mock cancel_order to fail
        om.cancel_order = AsyncMock(return_value=False)

        # Process fill for first order
        order_data = {
            "id": 123,
            "status": 2,  # Filled
            "accountId": 1,
            "contractId": "MNQ",
            "creationTimestamp": "2024-01-01T00:00:00Z",
            "updateTimestamp": "2024-01-01T00:00:01Z",
            "type": 1,  # Limit
            "side": 0,  # Buy
            "size": 1
        }
        await om._on_order_update(order_data)

        # Allow time for background task to complete
        await asyncio.sleep(0.1)

        # Should have recorded failure
        assert 456 in om._cancellation_failures

    def test_memory_stats_with_empty_data(self, mock_order_manager):
        """Test memory statistics with empty tracking data."""
        om = mock_order_manager

        stats = om.get_memory_stats()

        # Should handle empty data gracefully
        assert stats["tracked_orders_count"] == 0
        assert stats["cached_statuses_count"] == 0
        assert stats["position_mappings_count"] == 0
        assert stats["monitored_positions_count"] == 0
        assert stats["cleanup_task_running"] is False
