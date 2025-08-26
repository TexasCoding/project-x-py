"""
Comprehensive tests for PositionTrackingMixin.

Tests cover:
- Real-time callback setup and teardown
- Position queue processing
- Position update handling (single and batch)
- Position closure detection
- Position history tracking
- Payload validation
- Account update handling
- Event callbacks and EventBus integration
- Order synchronization
- Thread safety and error handling
"""

import asyncio
import logging
from collections import deque
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from project_x_py.models import Position
from project_x_py.position_manager.tracking import PositionTrackingMixin
from project_x_py.types.trading import PositionType


@pytest.fixture
def mock_position_data():
    """Create mock position data."""
    return {
        "contractId": "MNQ",
        "type": 1,  # LONG
        "size": 2,
        "averagePrice": 18000.0,
        "id": 12345,
        "accountId": 67890,
        "creationTimestamp": "2025-08-25T10:00:00Z"
    }


@pytest.fixture
def mock_position():
    """Create a mock Position object."""
    position = Mock(spec=Position)
    position.contractId = "MNQ"
    position.type = PositionType.LONG
    position.size = 2
    position.averagePrice = 18000.0
    position.id = 12345
    position.accountId = 67890
    position.creationTimestamp = "2025-08-25T10:00:00Z"
    return position


@pytest.fixture
def tracking_mixin():
    """Create a PositionTrackingMixin instance with required attributes."""

    class TestPositionTracking(PositionTrackingMixin):
        def __init__(self):
            super().__init__()
            self.realtime_client = AsyncMock()
            self.logger = logging.getLogger(__name__)
            self.position_lock = asyncio.Lock()
            self.stats = {
                "realized_pnl": 0.0,
                "closed_positions": 0,
                "winning_positions": 0,
                "losing_positions": 0,
                "open_positions": 0,
                "gross_profit": 0.0,
                "gross_loss": 0.0,
                "best_position_pnl": 0.0,
                "worst_position_pnl": 0.0,
            }
            self.order_manager = None
            self._order_sync_enabled = False
            self.event_bus = AsyncMock()

            # Mock methods from other mixins
            self._check_position_alerts = AsyncMock()
            self._trigger_callbacks = AsyncMock()

    return TestPositionTracking()


class TestRealtimeCallbacks:
    """Test real-time callback setup and management."""

    @pytest.mark.asyncio
    async def test_setup_realtime_callbacks(self, tracking_mixin):
        """Test setting up real-time callbacks."""
        await tracking_mixin._setup_realtime_callbacks()

        # Should register callbacks
        assert tracking_mixin.realtime_client.add_callback.call_count == 2
        tracking_mixin.realtime_client.add_callback.assert_any_call(
            "position_update", tracking_mixin._on_position_update
        )
        tracking_mixin.realtime_client.add_callback.assert_any_call(
            "account_update", tracking_mixin._on_account_update
        )

        # Should start position processor
        assert tracking_mixin._processing_enabled is True
        assert tracking_mixin._position_processor_task is not None

        # Clean up
        await tracking_mixin._stop_position_processor()

    @pytest.mark.asyncio
    async def test_setup_realtime_callbacks_no_client(self, tracking_mixin):
        """Test setup with no real-time client."""
        tracking_mixin.realtime_client = None
        await tracking_mixin._setup_realtime_callbacks()

        # Should not start processor
        assert tracking_mixin._position_processor_task is None

    @pytest.mark.asyncio
    async def test_start_stop_position_processor(self, tracking_mixin):
        """Test starting and stopping position processor."""
        # Start processor
        await tracking_mixin._start_position_processor()
        assert tracking_mixin._processing_enabled is True
        assert tracking_mixin._position_processor_task is not None
        task = tracking_mixin._position_processor_task

        # Start again - should not create new task
        await tracking_mixin._start_position_processor()
        assert tracking_mixin._position_processor_task == task

        # Stop processor
        await tracking_mixin._stop_position_processor()
        assert tracking_mixin._processing_enabled is False
        assert tracking_mixin._position_processor_task is None


class TestPositionQueueProcessing:
    """Test position update queue processing."""

    @pytest.mark.asyncio
    async def test_position_processor_processes_queue(self, tracking_mixin, mock_position_data):
        """Test that position processor processes queued items."""
        # Mock the process method
        tracking_mixin._process_position_data = AsyncMock()

        # Start processor
        await tracking_mixin._start_position_processor()

        # Add items to queue
        await tracking_mixin._position_update_queue.put(mock_position_data)
        await tracking_mixin._position_update_queue.put({"contractId": "ES"})

        # Wait for processing
        await asyncio.sleep(0.1)

        # Should have processed both items
        assert tracking_mixin._process_position_data.call_count >= 2

        # Clean up
        await tracking_mixin._stop_position_processor()

    @pytest.mark.asyncio
    async def test_position_processor_handles_errors(self, tracking_mixin, mock_position_data):
        """Test processor continues after errors."""
        # Mock process to fail once then succeed
        tracking_mixin._process_position_data = AsyncMock(
            side_effect=[Exception("Process error"), None, None]
        )

        # Start processor
        await tracking_mixin._start_position_processor()

        # Add items
        for _ in range(3):
            await tracking_mixin._position_update_queue.put(mock_position_data)

        # Wait for processing
        await asyncio.sleep(0.1)

        # Should process all items despite error
        assert tracking_mixin._process_position_data.call_count >= 3

        # Clean up
        await tracking_mixin._stop_position_processor()

    @pytest.mark.asyncio
    async def test_get_queue_size(self, tracking_mixin, mock_position_data):
        """Test getting queue size."""
        assert tracking_mixin.get_queue_size() == 0

        await tracking_mixin._position_update_queue.put(mock_position_data)
        assert tracking_mixin.get_queue_size() == 1

        await tracking_mixin._position_update_queue.put(mock_position_data)
        assert tracking_mixin.get_queue_size() == 2


class TestPositionUpdateHandling:
    """Test handling of position updates."""

    @pytest.mark.asyncio
    async def test_on_position_update_single(self, tracking_mixin, mock_position_data):
        """Test handling single position update."""
        await tracking_mixin._on_position_update(mock_position_data)
        assert tracking_mixin._position_update_queue.qsize() == 1

    @pytest.mark.asyncio
    async def test_on_position_update_list(self, tracking_mixin, mock_position_data):
        """Test handling list of position updates."""
        updates = [mock_position_data, {"contractId": "ES"}, {"contractId": "NQ"}]
        await tracking_mixin._on_position_update(updates)
        assert tracking_mixin._position_update_queue.qsize() == 3

    @pytest.mark.asyncio
    async def test_on_position_update_error_handling(self, tracking_mixin):
        """Test error handling in position update."""
        # Mock queue to raise error
        tracking_mixin._position_update_queue.put = AsyncMock(side_effect=Exception("Queue error"))

        # Should handle error gracefully
        await tracking_mixin._on_position_update({"contractId": "MNQ"})
        # No assertion - just ensure no exception propagated

    @pytest.mark.asyncio
    async def test_on_account_update(self, tracking_mixin):
        """Test account update handling."""
        account_data = {"balance": 50000, "margin": 10000}
        await tracking_mixin._on_account_update(account_data)

        tracking_mixin._trigger_callbacks.assert_called_once_with("account_update", account_data)


class TestPayloadValidation:
    """Test position payload validation."""

    def test_validate_valid_payload(self, tracking_mixin, mock_position_data):
        """Test validation of valid payload."""
        assert tracking_mixin._validate_position_payload(mock_position_data) is True

    def test_validate_missing_required_fields(self, tracking_mixin):
        """Test validation with missing required fields."""
        # Missing contractId
        invalid = {"type": 1, "size": 2, "averagePrice": 18000.0}
        assert tracking_mixin._validate_position_payload(invalid) is False

        # Missing type
        invalid = {"contractId": "MNQ", "size": 2, "averagePrice": 18000.0}
        assert tracking_mixin._validate_position_payload(invalid) is False

    def test_validate_invalid_position_type(self, tracking_mixin):
        """Test validation with invalid position type."""
        invalid = {
            "contractId": "MNQ",
            "type": 99,  # Invalid type
            "size": 2,
            "averagePrice": 18000.0
        }
        assert tracking_mixin._validate_position_payload(invalid) is False

    def test_validate_invalid_size_type(self, tracking_mixin):
        """Test validation with invalid size type."""
        invalid = {
            "contractId": "MNQ",
            "type": 1,
            "size": "not_a_number",  # Invalid size
            "averagePrice": 18000.0
        }
        assert tracking_mixin._validate_position_payload(invalid) is False

    def test_validate_undefined_position_type(self, tracking_mixin):
        """Test validation with undefined position type (0)."""
        valid = {
            "contractId": "MNQ",
            "type": 0,  # UNDEFINED is valid
            "size": 2,
            "averagePrice": 18000.0
        }
        assert tracking_mixin._validate_position_payload(valid) is True


class TestPositionDataProcessing:
    """Test processing of position data."""

    @pytest.mark.asyncio
    async def test_process_position_data_new(self, tracking_mixin, mock_position_data):
        """Test processing new position."""
        # Mock Position class to return a mock object
        with patch("project_x_py.position_manager.tracking.Position") as MockPosition:
            mock_pos = Mock()
            mock_pos.contractId = "MNQ"
            mock_pos.size = 2
            mock_pos.averagePrice = 18000.0
            MockPosition.return_value = mock_pos

            await tracking_mixin._process_position_data(mock_position_data)

            # Should track position
            assert "MNQ" in tracking_mixin.tracked_positions
            position = tracking_mixin.tracked_positions["MNQ"]
            assert position.size == 2
            assert position.averagePrice == 18000.0

            # Should trigger callbacks
            tracking_mixin._trigger_callbacks.assert_called()

    @pytest.mark.asyncio
    async def test_process_position_data_wrapped(self, tracking_mixin, mock_position_data):
        """Test processing wrapped position data."""
        wrapped = {"action": 1, "data": mock_position_data}

        with patch("project_x_py.position_manager.tracking.Position") as MockPosition:
            mock_pos = Mock()
            mock_pos.contractId = "MNQ"
            MockPosition.return_value = mock_pos

            await tracking_mixin._process_position_data(wrapped)

            assert "MNQ" in tracking_mixin.tracked_positions

    @pytest.mark.asyncio
    async def test_process_position_data_update(self, tracking_mixin, mock_position_data, mock_position):
        """Test updating existing position."""
        # Add initial position
        tracking_mixin.tracked_positions["MNQ"] = mock_position

        # Update with new size
        update_data = dict(mock_position_data)
        update_data["size"] = 5

        with patch("project_x_py.position_manager.tracking.Position") as MockPosition:
            mock_pos = Mock()
            mock_pos.id = mock_position.id
            mock_pos.accountId = mock_position.accountId
            mock_pos.contractId = "MNQ"
            mock_pos.creationTimestamp = mock_position.creationTimestamp
            mock_pos.type = mock_position.type
            mock_pos.size = 5
            mock_pos.averagePrice = 18000.0
            MockPosition.return_value = mock_pos

            await tracking_mixin._process_position_data(update_data)

            # Should update position
            assert tracking_mixin.tracked_positions["MNQ"].size == 5

    @pytest.mark.asyncio
    async def test_process_position_closure(self, tracking_mixin, mock_position_data, mock_position):
        """Test processing position closure."""
        # Add initial position
        tracking_mixin.tracked_positions["MNQ"] = mock_position

        # Close position
        closure_data = dict(mock_position_data)
        closure_data["size"] = 0
        closure_data["averagePrice"] = 18100.0  # Exit price

        await tracking_mixin._process_position_data(closure_data)

        # Should remove from tracked positions
        assert "MNQ" not in tracking_mixin.tracked_positions

        # Should update stats
        assert tracking_mixin.stats["closed_positions"] == 1
        assert tracking_mixin.stats["winning_positions"] == 1  # Profit from 18000 to 18100
        assert tracking_mixin.stats["realized_pnl"] == 200.0  # (18100-18000) * 2

        # Should trigger position_closed callback
        tracking_mixin._trigger_callbacks.assert_any_call("position_closed", closure_data)

    @pytest.mark.asyncio
    async def test_process_short_position_closure(self, tracking_mixin, mock_position_data):
        """Test closing short position with profit."""
        # Create short position
        short_position = Mock(spec=Position)
        short_position.contractId = "ES"
        short_position.type = PositionType.SHORT
        short_position.size = 3
        short_position.averagePrice = 4500.0

        tracking_mixin.tracked_positions["ES"] = short_position

        # Close with profit (sold at 4500, buy back at 4480)
        closure_data = {
            "contractId": "ES",
            "type": 2,  # SHORT
            "size": 0,
            "averagePrice": 4480.0  # Exit price
        }

        await tracking_mixin._process_position_data(closure_data)

        assert "ES" not in tracking_mixin.tracked_positions
        assert tracking_mixin.stats["realized_pnl"] == 60.0  # (4500-4480) * 3
        assert tracking_mixin.stats["winning_positions"] == 1

    @pytest.mark.asyncio
    async def test_process_position_with_loss(self, tracking_mixin, mock_position, mock_position_data):
        """Test closing position with loss."""
        tracking_mixin.tracked_positions["MNQ"] = mock_position

        # Close with loss
        closure_data = dict(mock_position_data)
        closure_data["size"] = 0
        closure_data["averagePrice"] = 17950.0  # Exit price (loss)

        await tracking_mixin._process_position_data(closure_data)

        assert tracking_mixin.stats["losing_positions"] == 1
        assert tracking_mixin.stats["realized_pnl"] == -100.0  # (17950-18000) * 2

    @pytest.mark.asyncio
    async def test_process_invalid_payload(self, tracking_mixin):
        """Test processing invalid payload."""
        invalid_data = {"invalid": "data"}
        await tracking_mixin._process_position_data(invalid_data)

        # Should not add to tracked positions
        assert len(tracking_mixin.tracked_positions) == 0

    @pytest.mark.asyncio
    async def test_process_missing_contract_id(self, tracking_mixin):
        """Test processing data without contract ID."""
        data = {"type": 1, "size": 2, "averagePrice": 18000.0}
        await tracking_mixin._process_position_data(data)

        assert len(tracking_mixin.tracked_positions) == 0


class TestPositionHistory:
    """Test position history tracking."""

    @pytest.mark.asyncio
    async def test_position_history_tracking(self, tracking_mixin, mock_position_data):
        """Test that position history is tracked."""
        # Process multiple updates
        await tracking_mixin._process_position_data(mock_position_data)

        update1 = dict(mock_position_data)
        update1["size"] = 3
        await tracking_mixin._process_position_data(update1)

        update2 = dict(mock_position_data)
        update2["size"] = 1
        await tracking_mixin._process_position_data(update2)

        # Check history
        history = tracking_mixin.position_history["MNQ"]
        assert len(history) == 3
        assert history[0]["size_change"] == 2  # Initial
        assert history[1]["size_change"] == 1  # 3-2
        assert history[2]["size_change"] == -2  # 1-3

    @pytest.mark.asyncio
    async def test_position_history_max_length(self, tracking_mixin, mock_position_data):
        """Test that position history respects max length."""
        # History has maxlen=1000
        tracking_mixin.position_history["MNQ"] = deque(maxlen=3)  # Override for testing

        # Add multiple entries
        for i in range(5):
            data = dict(mock_position_data)
            data["size"] = i
            await tracking_mixin._process_position_data(data)

        # Should only keep last 3
        assert len(tracking_mixin.position_history["MNQ"]) == 3


class TestOrderSynchronization:
    """Test order manager synchronization."""

    @pytest.mark.asyncio
    async def test_order_sync_enabled(self, tracking_mixin, mock_position_data):
        """Test order synchronization when enabled."""
        tracking_mixin._order_sync_enabled = True
        tracking_mixin.order_manager = AsyncMock()
        tracking_mixin.order_manager.on_position_changed = AsyncMock()
        tracking_mixin.order_manager.on_position_closed = AsyncMock()

        with patch("project_x_py.position_manager.tracking.Position") as MockPosition:
            mock_pos = Mock()
            mock_pos.contractId = "MNQ"
            mock_pos.id = 1
            mock_pos.accountId = 67890
            mock_pos.creationTimestamp = "2025-08-25T10:00:00Z"
            mock_pos.type = 1
            mock_pos.size = 2
            mock_pos.averagePrice = 18000.0
            MockPosition.return_value = mock_pos

            await tracking_mixin._process_position_data(mock_position_data)

            # Should call on_position_changed even for new position (old_size=0, new_size=2)
            tracking_mixin.order_manager.on_position_changed.assert_called_once_with("MNQ", 0, 2)

    @pytest.mark.asyncio
    async def test_order_sync_disabled(self, tracking_mixin, mock_position_data):
        """Test no order sync when disabled."""
        tracking_mixin._order_sync_enabled = False
        tracking_mixin.order_manager = AsyncMock()
        tracking_mixin.order_manager.on_position_changed = AsyncMock()
        tracking_mixin.order_manager.on_position_closed = AsyncMock()

        with patch("project_x_py.position_manager.tracking.Position") as MockPosition:
            mock_pos = Mock()
            mock_pos.contractId = "MNQ"
            MockPosition.return_value = mock_pos

            await tracking_mixin._process_position_data(mock_position_data)

            # Should not call any order sync methods when disabled
            tracking_mixin.order_manager.on_position_changed.assert_not_called()
            tracking_mixin.order_manager.on_position_closed.assert_not_called()

    @pytest.mark.asyncio
    async def test_order_sync_no_manager(self, tracking_mixin, mock_position_data):
        """Test order sync with no order manager."""
        tracking_mixin._order_sync_enabled = True
        tracking_mixin.order_manager = None

        # Should handle gracefully
        await tracking_mixin._process_position_data(mock_position_data)


class TestAlertIntegration:
    """Test integration with alert system."""

    @pytest.mark.asyncio
    async def test_check_position_alerts_called(self, tracking_mixin, mock_position_data, mock_position):
        """Test that position alerts are checked."""
        tracking_mixin.tracked_positions["MNQ"] = mock_position

        # Update position
        update_data = dict(mock_position_data)
        update_data["size"] = 5

        with patch("project_x_py.position_manager.tracking.Position") as MockPosition:
            mock_pos = Mock()
            mock_pos.id = mock_position.id
            mock_pos.accountId = mock_position.accountId
            mock_pos.contractId = "MNQ"
            mock_pos.creationTimestamp = mock_position.creationTimestamp
            mock_pos.type = mock_position.type
            mock_pos.size = 5
            mock_pos.averagePrice = mock_position.averagePrice
            MockPosition.return_value = mock_pos

            await tracking_mixin._process_position_data(update_data)

            # Should check alerts
            tracking_mixin._check_position_alerts.assert_called_once()
            call_args = tracking_mixin._check_position_alerts.call_args[0]
            assert call_args[0] == "MNQ"
            assert call_args[1].size == 5  # Current position
            assert call_args[2] == mock_position  # Old position


class TestEventBusIntegration:
    """Test EventBus integration."""

    @pytest.mark.asyncio
    async def test_trigger_callbacks_position_updated(self, tracking_mixin, mock_position_data):
        """Test callbacks are triggered for position updates."""
        with patch("project_x_py.position_manager.tracking.Position") as MockPosition:
            mock_pos = Mock()
            mock_pos.id = 1
            mock_pos.accountId = 67890
            mock_pos.contractId = "MNQ"
            mock_pos.creationTimestamp = "2025-08-25T10:00:00Z"
            mock_pos.type = 1
            mock_pos.size = 2
            mock_pos.averagePrice = 18000.0
            MockPosition.return_value = mock_pos

            await tracking_mixin._process_position_data(mock_position_data)

            # Should trigger position_update callback (for new positions it's position_opened)
            tracking_mixin._trigger_callbacks.assert_any_call("position_opened", mock_position_data)

    @pytest.mark.asyncio
    async def test_trigger_callbacks_position_closed(self, tracking_mixin, mock_position_data, mock_position):
        """Test callbacks are triggered for position closure."""
        tracking_mixin.tracked_positions["MNQ"] = mock_position

        closure_data = dict(mock_position_data)
        closure_data["size"] = 0

        await tracking_mixin._process_position_data(closure_data)

        # Should trigger position_closed callback
        tracking_mixin._trigger_callbacks.assert_any_call("position_closed", closure_data)


class TestErrorHandling:
    """Test error handling in various scenarios."""

    @pytest.mark.asyncio
    async def test_process_position_exception_handling(self, tracking_mixin, mock_position_data):
        """Test exception handling in position processing."""
        # Mock to raise error
        tracking_mixin._trigger_callbacks = AsyncMock(side_effect=Exception("Callback error"))

        # Should handle error gracefully
        await tracking_mixin._process_position_data(mock_position_data)

        # Position should still be tracked
        assert "MNQ" in tracking_mixin.tracked_positions

    @pytest.mark.asyncio
    async def test_processor_task_cancellation(self, tracking_mixin):
        """Test graceful handling of task cancellation."""
        await tracking_mixin._start_position_processor()
        task = tracking_mixin._position_processor_task

        # Cancel the task
        task.cancel()

        # Stop should handle cancellation gracefully
        await tracking_mixin._stop_position_processor()
        assert tracking_mixin._position_processor_task is None


class TestFullIntegration:
    """Full integration tests."""

    @pytest.mark.asyncio
    async def test_full_position_lifecycle(self, tracking_mixin, mock_position_data):
        """Test complete position lifecycle from open to close."""
        # Setup real-time callbacks
        await tracking_mixin._setup_realtime_callbacks()

        # Open position
        await tracking_mixin._on_position_update(mock_position_data)

        # Wait for processing
        await asyncio.sleep(0.1)

        assert "MNQ" in tracking_mixin.tracked_positions

        # Update position
        update = dict(mock_position_data)
        update["size"] = 5
        await tracking_mixin._on_position_update(update)
        await asyncio.sleep(0.1)

        assert tracking_mixin.tracked_positions["MNQ"].size == 5

        # Close position
        closure = dict(mock_position_data)
        closure["size"] = 0
        closure["averagePrice"] = 18100.0
        await tracking_mixin._on_position_update(closure)
        await asyncio.sleep(0.1)

        assert "MNQ" not in tracking_mixin.tracked_positions
        assert tracking_mixin.stats["closed_positions"] == 1

        # Clean up
        await tracking_mixin._stop_position_processor()
