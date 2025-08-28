"""
Advanced tests for OrderTrackingMixin - Testing untested paths following strict TDD.

These tests define EXPECTED behavior for order tracking edge cases.
"""

import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from project_x_py.exceptions import ProjectXOrderError
from project_x_py.models import Order
from project_x_py.types.trading import OrderStatus, OrderType


class TestOrderTrackingCallbacks:
    """Test order tracking callback system."""

    @pytest.mark.asyncio
    async def test_register_order_callback(self, order_manager):
        """Should register callbacks for specific order events."""
        callback = AsyncMock()

        await order_manager.register_order_callback("fill", callback)

        assert "fill" in order_manager.order_callbacks
        assert callback in order_manager.order_callbacks["fill"]

    @pytest.mark.asyncio
    async def test_register_multiple_callbacks_same_event(self, order_manager):
        """Should support multiple callbacks for same event."""
        callback1 = AsyncMock()
        callback2 = AsyncMock()
        callback3 = AsyncMock()

        await order_manager.register_order_callback("cancel", callback1)
        await order_manager.register_order_callback("cancel", callback2)
        await order_manager.register_order_callback("cancel", callback3)

        assert len(order_manager.order_callbacks["cancel"]) == 3
        assert all(cb in order_manager.order_callbacks["cancel"]
                  for cb in [callback1, callback2, callback3])

    @pytest.mark.asyncio
    async def test_trigger_order_callbacks(self, order_manager):
        """Should trigger all callbacks for an event."""
        callback1 = AsyncMock()
        callback2 = AsyncMock()

        order_manager.order_callbacks["fill"] = [callback1, callback2]

        order_data = {"order_id": "123", "status": OrderStatus.FILLED, "size": 5}
        await order_manager._trigger_order_callbacks("fill", order_data)

        callback1.assert_called_once_with(order_data)
        callback2.assert_called_once_with(order_data)

    @pytest.mark.asyncio
    async def test_trigger_callbacks_handles_exceptions(self, order_manager):
        """Should handle callback exceptions gracefully."""
        failing_callback = AsyncMock(side_effect=Exception("Callback error"))
        working_callback = AsyncMock()

        order_manager.order_callbacks["reject"] = [failing_callback, working_callback]

        order_data = {"order_id": "456", "status": OrderStatus.REJECTED}

        # Should not crash even if callback fails
        await order_manager._trigger_order_callbacks("reject", order_data)

        # Working callback should still be called
        working_callback.assert_called_once_with(order_data)

    @pytest.mark.asyncio
    async def test_unregister_order_callback(self, order_manager):
        """Should be able to unregister callbacks."""
        callback = AsyncMock()

        await order_manager.register_order_callback("fill", callback)
        assert callback in order_manager.order_callbacks["fill"]

        await order_manager.unregister_order_callback("fill", callback)
        assert callback not in order_manager.order_callbacks.get("fill", [])


class TestOrderStatusUpdates:
    """Test order status update mechanisms."""

    @pytest.mark.asyncio
    async def test_update_order_status_from_websocket(self, order_manager):
        """Should update order status from WebSocket events."""
        order_manager._realtime_enabled = True
        order_manager.tracked_orders["789"] = {
            "status": OrderStatus.OPEN,
            "size": 10
        }

        # Simulate WebSocket fill event
        fill_event = {
            "order_id": "789",
            "status": OrderStatus.FILLED,
            "filled_size": 10,
            "fill_price": 17000.0
        }

        await order_manager._handle_order_fill_event(fill_event)

        assert order_manager.tracked_orders["789"]["status"] == OrderStatus.FILLED
        assert order_manager.order_status_cache["789"] == OrderStatus.FILLED

    @pytest.mark.asyncio
    async def test_partial_fill_tracking(self, order_manager):
        """Should track partial fills correctly."""
        order_manager.tracked_orders["1000"] = {
            "status": OrderStatus.OPEN,
            "size": 10,
            "filled_size": 0
        }

        # First partial fill
        await order_manager._handle_partial_fill("1000", filled_size=3)
        assert order_manager.tracked_orders["1000"]["filled_size"] == 3
        assert order_manager.tracked_orders["1000"]["status"] == OrderStatus.OPEN

        # Second partial fill
        await order_manager._handle_partial_fill("1000", filled_size=5)
        assert order_manager.tracked_orders["1000"]["filled_size"] == 8

        # Final fill
        await order_manager._handle_partial_fill("1000", filled_size=2)
        assert order_manager.tracked_orders["1000"]["filled_size"] == 10
        assert order_manager.tracked_orders["1000"]["status"] == OrderStatus.FILLED

    @pytest.mark.asyncio
    async def test_order_rejection_tracking(self, order_manager):
        """Should track order rejections with reasons."""
        order_manager.tracked_orders["2000"] = {
            "status": OrderStatus.PENDING,
            "size": 5
        }

        rejection_event = {
            "order_id": "2000",
            "status": OrderStatus.REJECTED,
            "reason": "Insufficient margin"
        }

        await order_manager._handle_order_rejection(rejection_event)

        assert order_manager.tracked_orders["2000"]["status"] == OrderStatus.REJECTED
        assert order_manager.tracked_orders["2000"]["rejection_reason"] == "Insufficient margin"
        assert order_manager.order_status_cache["2000"] == OrderStatus.REJECTED

    @pytest.mark.asyncio
    async def test_order_expiration_tracking(self, order_manager):
        """Should track order expirations."""
        order_manager.tracked_orders["3000"] = {
            "status": OrderStatus.OPEN,
            "timestamp": time.time() - 3700  # Over 1 hour old
        }

        await order_manager._check_order_expiration("3000")

        assert order_manager.tracked_orders["3000"]["status"] == OrderStatus.EXPIRED
        assert order_manager.order_status_cache["3000"] == OrderStatus.EXPIRED


class TestOrderTrackingCleanup:
    """Test order tracking cleanup and memory management."""

    @pytest.mark.asyncio
    async def test_cleanup_old_filled_orders(self, order_manager):
        """Should clean up old filled orders from tracking."""
        old_time = time.time() - 7200  # 2 hours old
        recent_time = time.time() - 300  # 5 minutes old

        order_manager.tracked_orders = {
            "old_filled": {"status": OrderStatus.FILLED, "timestamp": old_time},
            "old_cancelled": {"status": OrderStatus.CANCELLED, "timestamp": old_time},
            "recent_filled": {"status": OrderStatus.FILLED, "timestamp": recent_time},
            "open_order": {"status": OrderStatus.OPEN, "timestamp": old_time}
        }

        await order_manager._cleanup_old_orders()

        # Old completed orders should be removed
        assert "old_filled" not in order_manager.tracked_orders
        assert "old_cancelled" not in order_manager.tracked_orders
        # Recent and open orders should remain
        assert "recent_filled" in order_manager.tracked_orders
        assert "open_order" in order_manager.tracked_orders

    @pytest.mark.asyncio
    async def test_cleanup_preserves_minimum_history(self, order_manager):
        """Should preserve minimum number of recent orders."""
        # Create 100 filled orders with different timestamps
        for i in range(100):
            order_manager.tracked_orders[f"order_{i}"] = {
                "status": OrderStatus.FILLED,
                "timestamp": time.time() - (i * 60)  # Each 1 minute older
            }

        order_manager.min_order_history = 20  # Keep at least 20 orders

        await order_manager._cleanup_old_orders()

        # Should keep at least min_order_history orders
        assert len(order_manager.tracked_orders) >= 20
        # Should have kept the most recent orders
        assert "order_0" in order_manager.tracked_orders
        assert "order_19" in order_manager.tracked_orders

    @pytest.mark.asyncio
    async def test_cleanup_task_runs_periodically(self, order_manager):
        """Cleanup task should run periodically when initialized."""
        order_manager._cleanup_task = None
        order_manager._cleanup_interval = 0.1  # 100ms for testing
        order_manager._cleanup_enabled = True

        with patch.object(order_manager, '_cleanup_completed_orders', new=AsyncMock()) as mock_cleanup:

            # Start cleanup task
            await order_manager._start_cleanup_task()
            assert order_manager._cleanup_task is not None

            # Wait for multiple cleanup cycles
            await asyncio.sleep(0.35)

            # Should have been called multiple times
            assert mock_cleanup.call_count >= 3

            # Stop cleanup task
            if order_manager._cleanup_task:
                order_manager._cleanup_enabled = False
                order_manager._cleanup_task.cancel()
                try:
                    await order_manager._cleanup_task
                except asyncio.CancelledError:
                    pass

    @pytest.mark.asyncio
    async def test_cleanup_handles_concurrent_updates(self, order_manager):
        """Cleanup should handle concurrent order updates safely."""
        # Add orders that will be cleaned
        for i in range(10):
            order_manager.tracked_orders[f"old_{i}"] = {
                "status": OrderStatus.FILLED,
                "timestamp": time.time() - 10000
            }

        async def add_new_orders():
            """Simulate concurrent order additions."""
            await asyncio.sleep(0.01)
            for i in range(5):
                order_manager.tracked_orders[f"new_{i}"] = {
                    "status": OrderStatus.OPEN,
                    "timestamp": time.time()
                }

        # Run cleanup and additions concurrently
        await asyncio.gather(
            order_manager._cleanup_old_orders(),
            add_new_orders()
        )

        # New orders should remain
        for i in range(5):
            assert f"new_{i}" in order_manager.tracked_orders


class TestOCOOrderTracking:
    """Test One-Cancels-Other order tracking."""

    @pytest.mark.asyncio
    async def test_track_oco_pair(self, order_manager):
        """Should track OCO order pairs."""
        await order_manager.track_oco_pair("stop_order_1", "limit_order_1")

        assert "stop_order_1" in order_manager.oco_pairs
        assert order_manager.oco_pairs["stop_order_1"] == "limit_order_1"
        assert "limit_order_1" in order_manager.oco_pairs
        assert order_manager.oco_pairs["limit_order_1"] == "stop_order_1"

    @pytest.mark.asyncio
    async def test_handle_oco_fill_cancels_other(self, order_manager):
        """When one OCO order fills, should cancel the other."""
        # Setup OCO pair with string keys but numeric string values (convertible to int)
        order_manager.oco_pairs = {
            "1001": "1002",
            "1002": "1001"
        }
        order_manager.tracked_orders = {
            "1001": {"status": OrderStatus.OPEN},
            "1002": {"status": OrderStatus.OPEN}
        }

        order_manager.cancel_order = AsyncMock(return_value=True)

        # Simulate order 1001 filling
        await order_manager._handle_oco_fill("1001")

        # Should cancel order 1002
        order_manager.cancel_order.assert_called_once_with(1002)
        # OCO pair should be cleaned up
        assert "1001" not in order_manager.oco_pairs
        assert "1002" not in order_manager.oco_pairs

    @pytest.mark.asyncio
    async def test_handle_oco_cancel_removes_pair(self, order_manager):
        """When one OCO order is cancelled, should remove pair tracking."""
        order_manager.oco_pairs = {
            "oco_3": "oco_4",
            "oco_4": "oco_3"
        }

        await order_manager._handle_oco_cancel("oco_3")

        # Pair should be removed but other order not cancelled
        assert "oco_3" not in order_manager.oco_pairs
        assert "oco_4" not in order_manager.oco_pairs

    @pytest.mark.asyncio
    async def test_oco_tracking_with_multiple_pairs(self, order_manager):
        """Should handle multiple OCO pairs independently."""
        # Track multiple pairs
        await order_manager.track_oco_pair("pair1_stop", "pair1_limit")
        await order_manager.track_oco_pair("pair2_stop", "pair2_limit")
        await order_manager.track_oco_pair("pair3_stop", "pair3_limit")

        assert len(order_manager.oco_pairs) == 6  # 3 pairs * 2 entries each

        # Cancel one pair shouldn't affect others
        await order_manager._handle_oco_cancel("pair2_stop")

        assert "pair1_stop" in order_manager.oco_pairs
        assert "pair3_limit" in order_manager.oco_pairs
        assert "pair2_stop" not in order_manager.oco_pairs


class TestOrderTrackingStatistics:
    """Test order tracking statistics and metrics."""

    @pytest.mark.asyncio
    async def test_calculate_average_fill_time(self, order_manager):
        """Should calculate average order fill time."""
        order_manager.fill_times = []

        # Track some fill times
        await order_manager._record_fill_time("order1", 1500)  # 1.5 seconds
        await order_manager._record_fill_time("order2", 2000)  # 2 seconds
        await order_manager._record_fill_time("order3", 2500)  # 2.5 seconds

        avg_fill_time = order_manager.get_average_fill_time()
        assert avg_fill_time == 2000  # Average of 1500, 2000, 2500

    @pytest.mark.asyncio
    async def test_track_order_type_distribution(self, order_manager):
        """Should track distribution of order types."""
        # Place various order types
        order_manager.stats["market_orders"] = 10
        order_manager.stats["limit_orders"] = 25
        order_manager.stats["stop_orders"] = 15

        distribution = order_manager.get_order_type_distribution()

        assert distribution["market"] == 0.2  # 10/50
        assert distribution["limit"] == 0.5   # 25/50
        assert distribution["stop"] == 0.3    # 15/50

    @pytest.mark.asyncio
    async def test_track_slippage_statistics(self, order_manager):
        """Should track slippage for market orders."""
        order_manager.slippage_data = []

        # Record some slippage
        await order_manager._record_slippage("order1", expected=17000, actual=17002)
        await order_manager._record_slippage("order2", expected=17000, actual=16998)
        await order_manager._record_slippage("order3", expected=17000, actual=17001)

        avg_slippage = order_manager.get_average_slippage()
        assert avg_slippage == pytest.approx(0.333, rel=0.01)  # Average of 2, -2, 1

    @pytest.mark.asyncio
    async def test_track_rejection_reasons(self, order_manager):
        """Should track and categorize rejection reasons."""
        order_manager.rejection_reasons = {}

        # Track various rejections
        await order_manager._track_rejection_reason("Insufficient margin")
        await order_manager._track_rejection_reason("Invalid price")
        await order_manager._track_rejection_reason("Insufficient margin")
        await order_manager._track_rejection_reason("Market closed")
        await order_manager._track_rejection_reason("Insufficient margin")

        top_reasons = order_manager.get_top_rejection_reasons()

        assert top_reasons[0] == ("Insufficient margin", 3)
        assert len(top_reasons) == 3


class TestRealTimeOrderTracking:
    """Test real-time order tracking via WebSocket."""

    @pytest.mark.asyncio
    async def test_setup_realtime_callbacks(self, order_manager):
        """Should setup WebSocket callbacks for order events."""
        realtime_client = MagicMock()
        realtime_client.on_order_update = AsyncMock()
        realtime_client.on_fill = AsyncMock()
        realtime_client.on_cancel = AsyncMock()

        order_manager.realtime_client = realtime_client
        await order_manager._setup_realtime_callbacks()

        # Should register callbacks
        assert realtime_client.on_order_update.called
        assert realtime_client.on_fill.called
        assert realtime_client.on_cancel.called

    @pytest.mark.asyncio
    async def test_handle_realtime_order_update(self, order_manager):
        """Should handle real-time order updates from WebSocket."""
        order_manager._realtime_enabled = True
        order_manager.tracked_orders["5000"] = {
            "status": OrderStatus.PENDING,
            "size": 10
        }

        # Simulate WebSocket order update
        update_event = {
            "order_id": "5000",
            "status": OrderStatus.OPEN,
            "exchange_accepted": True,
            "timestamp": datetime.now().isoformat()
        }

        await order_manager._handle_realtime_order_update(update_event)

        assert order_manager.tracked_orders["5000"]["status"] == OrderStatus.OPEN
        assert order_manager.tracked_orders["5000"]["exchange_accepted"] is True

    @pytest.mark.asyncio
    async def test_handle_realtime_disconnection(self, order_manager):
        """Should handle WebSocket disconnection gracefully."""
        order_manager._realtime_enabled = True
        order_manager.realtime_client = MagicMock()
        order_manager.realtime_client.is_connected = False

        # Should fall back to polling when disconnected
        order_manager.project_x._make_request = AsyncMock(
            return_value={"success": True, "orders": []}
        )

        orders = await order_manager.search_open_orders()

        # Should use API instead of realtime
        assert order_manager.project_x._make_request.called


class TestOrderTrackingEdgeCases:
    """Test edge cases in order tracking."""

    @pytest.mark.asyncio
    async def test_track_order_with_duplicate_id(self, order_manager):
        """Should handle duplicate order IDs gracefully."""
        order_manager.tracked_orders["dup_1"] = {
            "status": OrderStatus.FILLED,
            "timestamp": time.time() - 100
        }

        # Try to track new order with same ID
        new_order = {
            "order_id": "dup_1",
            "status": OrderStatus.OPEN,
            "timestamp": time.time()
        }

        await order_manager._track_new_order(new_order)

        # Should update with new order (newer timestamp)
        assert order_manager.tracked_orders["dup_1"]["status"] == OrderStatus.OPEN

    @pytest.mark.asyncio
    async def test_handle_out_of_order_status_updates(self, order_manager):
        """Should handle status updates arriving out of order."""
        order_manager.tracked_orders["6000"] = {
            "status": OrderStatus.OPEN,
            "timestamp": time.time(),
            "sequence": 1
        }

        # Receive filled status with newer sequence
        await order_manager._handle_status_update("6000", OrderStatus.FILLED, sequence=3)
        assert order_manager.tracked_orders["6000"]["status"] == OrderStatus.FILLED

        # Receive older pending status (should ignore)
        await order_manager._handle_status_update("6000", OrderStatus.PENDING, sequence=2)
        assert order_manager.tracked_orders["6000"]["status"] == OrderStatus.FILLED  # Should not change

    @pytest.mark.asyncio
    async def test_recover_lost_order_updates(self, order_manager):
        """Should recover from lost order updates."""
        order_manager._realtime_enabled = True
        order_manager.tracked_orders["7000"] = {
            "status": OrderStatus.OPEN,
            "last_update": time.time() - 120  # 2 minutes old
        }

        # Simulate recovery check
        order_manager.project_x._make_request = AsyncMock(
            return_value={
                "success": True,
                "orders": [{
                    "id": 7000,
                    "status": OrderStatus.FILLED,
                    "filledSize": 10
                }]
            }
        )

        await order_manager._recover_stale_orders()

        # Should update from API
        assert order_manager.tracked_orders["7000"]["status"] == OrderStatus.FILLED

    @pytest.mark.asyncio
    async def test_handle_order_modification_tracking(self, order_manager):
        """Should track order modifications."""
        order_manager.tracked_orders["8000"] = {
            "status": OrderStatus.OPEN,
            "size": 10,
            "limit_price": 17000.0,
            "modifications": []
        }

        # Track modification
        await order_manager._track_order_modification("8000", {
            "size": 5,
            "limit_price": 17010.0,
            "timestamp": time.time()
        })

        assert order_manager.tracked_orders["8000"]["size"] == 5
        assert order_manager.tracked_orders["8000"]["limit_price"] == 17010.0
        assert len(order_manager.tracked_orders["8000"]["modifications"]) == 1

    @pytest.mark.asyncio
    async def test_order_tracking_with_network_failures(self, order_manager):
        """Should handle network failures during order tracking."""
        order_manager._realtime_enabled = False

        # Simulate network failures
        order_manager.project_x._make_request = AsyncMock(
            side_effect=[
                Exception("Network error"),
                Exception("Timeout"),
                {"success": True, "orders": []}  # Eventually succeeds
            ]
        )

        with patch('asyncio.sleep', return_value=None):  # Skip delays in test
            orders = await order_manager.search_open_orders()

        assert orders == []
        assert order_manager.project_x._make_request.call_count == 3
