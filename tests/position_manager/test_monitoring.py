"""
Comprehensive tests for PositionMonitoringMixin.

Tests cover:
- Position alerts (add/remove)
- Alert threshold checking (max_loss, max_gain, pnl_threshold)
- Monitoring loop functionality
- Start/stop monitoring
- Real-time vs polling modes
- Error handling and edge cases
- Thread safety with locks
- Alert callbacks and notifications
"""

import asyncio
import logging
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from project_x_py.models import Position
from project_x_py.position_manager.monitoring import PositionMonitoringMixin
from project_x_py.types.response_types import PositionAnalysisResponse
from project_x_py.types.trading import PositionType


@pytest.fixture
def mock_position():
    """Create a mock position."""
    position = Mock(spec=Position)
    position.id = 123
    position.contractId = "MNQ"
    position.symbol = "MNQ"
    position.contractNumber = 1
    position.size = 2
    position.type = PositionType.LONG
    position.entryPrice = 18000.0
    position.entryTime = datetime.now()
    position.marketPrice = 18050.0
    position.dailyPnL = 100.0
    position.realizedPnL = 0.0
    position.unrealizedPnL = 100.0
    position.accountId = 456
    return position


@pytest.fixture
def monitoring_mixin():
    """Create a PositionMonitoringMixin instance with required attributes."""

    class TestPositionMonitoring(PositionMonitoringMixin):
        def __init__(self):
            super().__init__()
            self.position_lock = asyncio.Lock()
            self.logger = logging.getLogger(__name__)
            self.stats = {}
            self._realtime_enabled = False
            self.project_x = AsyncMock()
            self.data_manager = None

            # Mock methods from other mixins
            self._trigger_callbacks = AsyncMock()
            self.refresh_positions = AsyncMock(return_value=True)
            self.calculate_position_pnl = AsyncMock(
                return_value=PositionAnalysisResponse(
                    unrealized_pnl=150.0,
                    realized_pnl=0.0,
                    total_pnl=150.0,
                    entry_price=18000.0,
                    current_price=18050.0,
                    position_size=2,
                    point_value=5.0,
                )
            )

    return TestPositionMonitoring()


class TestPositionAlerts:
    """Test position alert management."""

    @pytest.mark.asyncio
    async def test_add_position_alert(self, monitoring_mixin):
        """Test adding a position alert."""
        await monitoring_mixin.add_position_alert(
            "MNQ", max_loss=-500.0, max_gain=1000.0, pnl_threshold=250.0
        )

        assert "MNQ" in monitoring_mixin.position_alerts
        alert = monitoring_mixin.position_alerts["MNQ"]
        assert alert["max_loss"] == -500.0
        assert alert["max_gain"] == 1000.0
        assert alert["pnl_threshold"] == 250.0
        assert "created" in alert
        assert alert["triggered"] is False

    @pytest.mark.asyncio
    async def test_add_position_alert_partial(self, monitoring_mixin):
        """Test adding alert with only some thresholds."""
        await monitoring_mixin.add_position_alert("ES", max_loss=-300.0)

        alert = monitoring_mixin.position_alerts["ES"]
        assert alert["max_loss"] == -300.0
        assert alert["max_gain"] is None
        assert alert["pnl_threshold"] is None

    @pytest.mark.asyncio
    async def test_add_position_alert_overwrites(self, monitoring_mixin):
        """Test that adding alert overwrites existing one."""
        await monitoring_mixin.add_position_alert("NQ", max_loss=-100.0)
        await monitoring_mixin.add_position_alert("NQ", max_gain=200.0)

        alert = monitoring_mixin.position_alerts["NQ"]
        assert alert["max_loss"] is None  # Overwritten
        assert alert["max_gain"] == 200.0

    @pytest.mark.asyncio
    async def test_remove_position_alert(self, monitoring_mixin):
        """Test removing a position alert."""
        await monitoring_mixin.add_position_alert("YM", max_loss=-250.0)
        assert "YM" in monitoring_mixin.position_alerts

        await monitoring_mixin.remove_position_alert("YM")
        assert "YM" not in monitoring_mixin.position_alerts

    @pytest.mark.asyncio
    async def test_remove_nonexistent_alert(self, monitoring_mixin):
        """Test removing non-existent alert doesn't raise error."""
        await monitoring_mixin.remove_position_alert("RTY")  # Should not raise


class TestAlertChecking:
    """Test alert checking logic."""

    @pytest.mark.asyncio
    async def test_check_alerts_size_change(self, monitoring_mixin, mock_position):
        """Test alert triggers on position size change."""
        old_position = Mock(spec=Position)
        old_position.size = 1
        mock_position.size = 3

        await monitoring_mixin.add_position_alert("MNQ")
        await monitoring_mixin._check_position_alerts("MNQ", mock_position, old_position)

        monitoring_mixin._trigger_callbacks.assert_called_once()
        call_args = monitoring_mixin._trigger_callbacks.call_args
        assert call_args[0][0] == "position_alert"
        assert "size changed by 2" in call_args[0][1]["message"]
        assert monitoring_mixin.position_alerts["MNQ"]["triggered"] is True

    @pytest.mark.asyncio
    async def test_check_alerts_already_triggered(self, monitoring_mixin, mock_position):
        """Test alert doesn't retrigger once triggered."""
        await monitoring_mixin.add_position_alert("MNQ")
        monitoring_mixin.position_alerts["MNQ"]["triggered"] = True

        old_position = Mock(spec=Position)
        old_position.size = 1
        mock_position.size = 3

        await monitoring_mixin._check_position_alerts("MNQ", mock_position, old_position)
        monitoring_mixin._trigger_callbacks.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_alerts_max_loss(self, monitoring_mixin, mock_position):
        """Test max loss alert trigger."""
        monitoring_mixin.data_manager = AsyncMock()
        monitoring_mixin.data_manager.get_current_price = AsyncMock(return_value=17900.0)

        instrument = Mock()
        instrument.contractMultiplier = 5.0
        monitoring_mixin.project_x.get_instrument = AsyncMock(return_value=instrument)

        monitoring_mixin.calculate_position_pnl = AsyncMock(
            return_value={"unrealized_pnl": -600.0}
        )

        await monitoring_mixin.add_position_alert("MNQ", max_loss=-500.0)
        await monitoring_mixin._check_position_alerts("MNQ", mock_position, None)

        monitoring_mixin._trigger_callbacks.assert_called_once()
        call_args = monitoring_mixin._trigger_callbacks.call_args
        assert "breached max loss" in call_args[0][1]["message"]
        assert monitoring_mixin.position_alerts["MNQ"]["triggered"] is True

    @pytest.mark.asyncio
    async def test_check_alerts_max_gain(self, monitoring_mixin, mock_position):
        """Test max gain alert trigger."""
        monitoring_mixin.data_manager = AsyncMock()
        monitoring_mixin.data_manager.get_current_price = AsyncMock(return_value=18200.0)

        instrument = Mock()
        instrument.contractMultiplier = 5.0
        monitoring_mixin.project_x.get_instrument = AsyncMock(return_value=instrument)

        monitoring_mixin.calculate_position_pnl = AsyncMock(
            return_value={"unrealized_pnl": 1200.0}
        )

        await monitoring_mixin.add_position_alert("MNQ", max_gain=1000.0)
        await monitoring_mixin._check_position_alerts("MNQ", mock_position, None)

        monitoring_mixin._trigger_callbacks.assert_called_once()
        call_args = monitoring_mixin._trigger_callbacks.call_args
        assert "reached max gain" in call_args[0][1]["message"]

    @pytest.mark.asyncio
    async def test_check_alerts_pnl_error_handling(self, monitoring_mixin, mock_position):
        """Test alert checking handles P&L calculation errors gracefully."""
        monitoring_mixin.data_manager = AsyncMock()
        monitoring_mixin.data_manager.get_current_price = AsyncMock(
            side_effect=Exception("Price error")
        )

        await monitoring_mixin.add_position_alert("MNQ", max_loss=-500.0)

        # Should handle error gracefully and check size change instead
        old_position = Mock(spec=Position)
        old_position.size = 1
        mock_position.size = 2

        await monitoring_mixin._check_position_alerts("MNQ", mock_position, old_position)

        # Should still trigger for size change
        monitoring_mixin._trigger_callbacks.assert_called_once()
        assert "size changed" in monitoring_mixin._trigger_callbacks.call_args[0][1]["message"]

    @pytest.mark.asyncio
    async def test_check_alerts_no_price_data(self, monitoring_mixin, mock_position):
        """Test alert checking when no price data available."""
        monitoring_mixin.data_manager = AsyncMock()
        monitoring_mixin.data_manager.get_current_price = AsyncMock(return_value=None)

        await monitoring_mixin.add_position_alert("MNQ", max_gain=1000.0)

        old_position = Mock(spec=Position)
        old_position.size = mock_position.size  # No size change

        await monitoring_mixin._check_position_alerts("MNQ", mock_position, old_position)

        # Should not trigger without price data or size change
        monitoring_mixin._trigger_callbacks.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_alerts_no_alert_configured(self, monitoring_mixin, mock_position):
        """Test checking alerts when none configured for contract."""
        old_position = Mock(spec=Position)
        old_position.size = 1
        mock_position.size = 3

        await monitoring_mixin._check_position_alerts("ES", mock_position, old_position)
        monitoring_mixin._trigger_callbacks.assert_not_called()


class TestMonitoringLoop:
    """Test monitoring loop functionality."""

    @pytest.mark.asyncio
    async def test_monitoring_loop_runs(self, monitoring_mixin):
        """Test monitoring loop runs and refreshes positions."""
        monitoring_mixin._monitoring_active = True

        async def stop_after_iterations():
            await asyncio.sleep(0.1)
            monitoring_mixin._monitoring_active = False

        # Run monitoring loop with quick interval
        loop_task = asyncio.create_task(monitoring_mixin._monitoring_loop(0.05))
        stop_task = asyncio.create_task(stop_after_iterations())

        await asyncio.gather(stop_task)
        loop_task.cancel()

        # Should have refreshed positions at least once
        assert monitoring_mixin.refresh_positions.call_count >= 1

    @pytest.mark.asyncio
    async def test_monitoring_loop_handles_errors(self, monitoring_mixin):
        """Test monitoring loop continues after errors."""
        monitoring_mixin._monitoring_active = True
        monitoring_mixin.refresh_positions = AsyncMock(
            side_effect=[Exception("Refresh error"), True, True]
        )

        async def stop_after_delay():
            await asyncio.sleep(0.15)
            monitoring_mixin._monitoring_active = False

        loop_task = asyncio.create_task(monitoring_mixin._monitoring_loop(0.05))
        stop_task = asyncio.create_task(stop_after_delay())

        await stop_task
        loop_task.cancel()

        # Should have attempted refresh multiple times despite error
        assert monitoring_mixin.refresh_positions.call_count >= 2


class TestStartStopMonitoring:
    """Test start/stop monitoring functionality."""

    @pytest.mark.asyncio
    async def test_start_monitoring_polling_mode(self, monitoring_mixin):
        """Test starting monitoring in polling mode."""
        await monitoring_mixin.start_monitoring(refresh_interval=60)

        assert monitoring_mixin._monitoring_active is True
        assert monitoring_mixin._monitoring_task is not None
        assert "monitoring_started" in monitoring_mixin.stats

        # Clean up
        await monitoring_mixin.stop_monitoring()

    @pytest.mark.asyncio
    async def test_start_monitoring_realtime_mode(self, monitoring_mixin):
        """Test starting monitoring in real-time mode."""
        monitoring_mixin._realtime_enabled = True

        await monitoring_mixin.start_monitoring()

        assert monitoring_mixin._monitoring_active is True
        assert monitoring_mixin._monitoring_task is None  # No polling task in realtime
        assert "monitoring_started" in monitoring_mixin.stats

        # Clean up
        await monitoring_mixin.stop_monitoring()

    @pytest.mark.asyncio
    async def test_start_monitoring_already_active(self, monitoring_mixin):
        """Test starting monitoring when already active."""
        monitoring_mixin._monitoring_active = True

        with patch.object(monitoring_mixin.logger, "warning") as mock_warning:
            await monitoring_mixin.start_monitoring()
            mock_warning.assert_called_once_with("⚠️ Position monitoring already active")

    @pytest.mark.asyncio
    async def test_stop_monitoring(self, monitoring_mixin):
        """Test stopping monitoring."""
        # Start monitoring first
        await monitoring_mixin.start_monitoring()
        task = monitoring_mixin._monitoring_task

        await monitoring_mixin.stop_monitoring()

        assert monitoring_mixin._monitoring_active is False
        assert monitoring_mixin._monitoring_task is None
        if task:
            # Task should be cancelled or cancelling
            assert task.cancelled() or task.cancelling()

    @pytest.mark.asyncio
    async def test_stop_monitoring_not_active(self, monitoring_mixin):
        """Test stopping monitoring when not active."""
        monitoring_mixin._monitoring_active = False
        monitoring_mixin._monitoring_task = None

        # Should not raise error
        await monitoring_mixin.stop_monitoring()
        assert monitoring_mixin._monitoring_active is False


class TestThreadSafety:
    """Test thread safety with locks."""

    @pytest.mark.asyncio
    async def test_concurrent_alert_additions(self, monitoring_mixin):
        """Test concurrent alert additions are thread-safe."""

        async def add_alert(contract_id, loss):
            await monitoring_mixin.add_position_alert(contract_id, max_loss=loss)

        # Add multiple alerts concurrently
        tasks = [
            add_alert(f"Contract{i}", -100.0 * i) for i in range(10)
        ]
        await asyncio.gather(*tasks)

        # All alerts should be added
        assert len(monitoring_mixin.position_alerts) == 10
        for i in range(10):
            assert f"Contract{i}" in monitoring_mixin.position_alerts

    @pytest.mark.asyncio
    async def test_concurrent_alert_checks(self, monitoring_mixin, mock_position):
        """Test concurrent alert checks are thread-safe."""
        # Add multiple alerts
        for i in range(5):
            await monitoring_mixin.add_position_alert(f"Contract{i}")

        old_position = Mock(spec=Position)
        old_position.size = 1
        mock_position.size = 2

        async def check_alert(contract_id):
            await monitoring_mixin._check_position_alerts(
                contract_id, mock_position, old_position
            )

        # Check alerts concurrently
        tasks = [check_alert(f"Contract{i}") for i in range(5)]
        await asyncio.gather(*tasks)

        # All alerts should be triggered
        assert monitoring_mixin._trigger_callbacks.call_count == 5


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_check_alerts_new_position(self, monitoring_mixin, mock_position):
        """Test alert checking for new position (no old position)."""
        monitoring_mixin.data_manager = AsyncMock()
        monitoring_mixin.data_manager.get_current_price = AsyncMock(return_value=18100.0)

        instrument = Mock()
        instrument.contractMultiplier = 5.0
        monitoring_mixin.project_x.get_instrument = AsyncMock(return_value=instrument)

        monitoring_mixin.calculate_position_pnl = AsyncMock(
            return_value={"unrealized_pnl": 500.0}
        )

        await monitoring_mixin.add_position_alert("MNQ", max_gain=400.0)
        await monitoring_mixin._check_position_alerts("MNQ", mock_position, None)

        # Should trigger for gain threshold
        monitoring_mixin._trigger_callbacks.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_alerts_missing_contract_multiplier(
        self, monitoring_mixin, mock_position
    ):
        """Test alert checking when instrument lacks contractMultiplier."""
        monitoring_mixin.data_manager = AsyncMock()
        monitoring_mixin.data_manager.get_current_price = AsyncMock(return_value=18100.0)

        instrument = Mock(spec=[])  # No contractMultiplier attribute
        monitoring_mixin.project_x.get_instrument = AsyncMock(return_value=instrument)

        await monitoring_mixin.add_position_alert("MNQ", max_gain=400.0)
        await monitoring_mixin._check_position_alerts("MNQ", mock_position, None)

        # Should use default multiplier of 1.0
        monitoring_mixin.calculate_position_pnl.assert_called_once()
        call_args = monitoring_mixin.calculate_position_pnl.call_args
        assert call_args[0][2] == 1.0  # Default point_value

    @pytest.mark.asyncio
    async def test_monitoring_loop_immediate_stop(self, monitoring_mixin):
        """Test monitoring loop stops immediately when flag is False."""
        monitoring_mixin._monitoring_active = False

        await monitoring_mixin._monitoring_loop(1)

        # Should not refresh positions
        monitoring_mixin.refresh_positions.assert_not_called()

    @pytest.mark.asyncio
    async def test_multiple_alert_thresholds(self, monitoring_mixin, mock_position):
        """Test multiple thresholds where max_loss triggers first."""
        monitoring_mixin.data_manager = AsyncMock()
        monitoring_mixin.data_manager.get_current_price = AsyncMock(return_value=17800.0)

        instrument = Mock()
        instrument.contractMultiplier = 5.0
        monitoring_mixin.project_x.get_instrument = AsyncMock(return_value=instrument)

        monitoring_mixin.calculate_position_pnl = AsyncMock(
            return_value={"unrealized_pnl": -600.0}
        )

        await monitoring_mixin.add_position_alert(
            "MNQ", max_loss=-500.0, max_gain=1000.0
        )
        await monitoring_mixin._check_position_alerts("MNQ", mock_position, None)

        # Should trigger for loss (checked first)
        monitoring_mixin._trigger_callbacks.assert_called_once()
        assert "breached max loss" in monitoring_mixin._trigger_callbacks.call_args[0][1]["message"]

    @pytest.mark.asyncio
    async def test_alert_with_zero_thresholds(self, monitoring_mixin, mock_position):
        """Test alerts with zero thresholds."""
        monitoring_mixin.data_manager = AsyncMock()
        monitoring_mixin.data_manager.get_current_price = AsyncMock(return_value=18000.0)

        instrument = Mock()
        instrument.contractMultiplier = 5.0
        monitoring_mixin.project_x.get_instrument = AsyncMock(return_value=instrument)

        monitoring_mixin.calculate_position_pnl = AsyncMock(
            return_value={"unrealized_pnl": 0.0}
        )

        await monitoring_mixin.add_position_alert("MNQ", max_loss=0.0, max_gain=0.0)
        await monitoring_mixin._check_position_alerts("MNQ", mock_position, None)

        # Should trigger for both thresholds at 0
        monitoring_mixin._trigger_callbacks.assert_called_once()


class TestIntegration:
    """Integration tests with full monitoring flow."""

    @pytest.mark.asyncio
    async def test_full_monitoring_flow(self, monitoring_mixin, mock_position):
        """Test complete monitoring flow from start to alert trigger."""
        # Setup alert
        await monitoring_mixin.add_position_alert("MNQ", max_loss=-500.0)

        # Setup data manager for P&L calculation
        monitoring_mixin.data_manager = AsyncMock()
        monitoring_mixin.data_manager.get_current_price = AsyncMock(return_value=17900.0)

        instrument = Mock()
        instrument.contractMultiplier = 5.0
        monitoring_mixin.project_x.get_instrument = AsyncMock(return_value=instrument)

        monitoring_mixin.calculate_position_pnl = AsyncMock(
            return_value={"unrealized_pnl": -550.0}
        )

        # Start monitoring
        await monitoring_mixin.start_monitoring(refresh_interval=0.1)

        # Simulate position update that triggers alert
        await monitoring_mixin._check_position_alerts("MNQ", mock_position, None)

        # Verify alert was triggered
        assert monitoring_mixin.position_alerts["MNQ"]["triggered"] is True
        monitoring_mixin._trigger_callbacks.assert_called_once()

        # Stop monitoring
        await monitoring_mixin.stop_monitoring()
        assert monitoring_mixin._monitoring_active is False

    @pytest.mark.asyncio
    async def test_monitoring_with_multiple_contracts(self, monitoring_mixin):
        """Test monitoring multiple contracts with different alerts."""
        # Setup alerts for multiple contracts
        await monitoring_mixin.add_position_alert("MNQ", max_loss=-500.0)
        await monitoring_mixin.add_position_alert("ES", max_gain=1000.0)
        await monitoring_mixin.add_position_alert("NQ", pnl_threshold=250.0)

        # Start monitoring
        await monitoring_mixin.start_monitoring()
        assert monitoring_mixin._monitoring_active is True

        # Remove one alert
        await monitoring_mixin.remove_position_alert("ES")
        assert "ES" not in monitoring_mixin.position_alerts
        assert "MNQ" in monitoring_mixin.position_alerts
        assert "NQ" in monitoring_mixin.position_alerts

        # Stop monitoring
        await monitoring_mixin.stop_monitoring()
