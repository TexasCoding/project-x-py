"""
Comprehensive tests for PositionManager reporting functionality.

Tests statistics gathering, history tracking, report generation, and validation status.
"""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from project_x_py.models import Position
from project_x_py.position_manager.reporting import PositionReportingMixin
from project_x_py.types import PositionType


class TestPositionReportingMixin:
    """Comprehensive tests for PositionReportingMixin functionality."""

    @pytest.fixture
    def mock_client(self):
        """Create mock ProjectX client."""
        client = AsyncMock()
        client.account_info = MagicMock()
        client.account_info.name = "TEST_ACCOUNT"
        client.account_info.id = 12345
        client.account_info.balance = 100000.0
        return client

    @pytest.fixture
    def reporting_mixin(self, mock_client):
        """Create PositionReportingMixin instance with mocked dependencies."""

        class TestReportingManager(PositionReportingMixin):
            def __init__(self, client):
                self.client = client
                self.project_x = client
                self.account_info = client.account_info

                # Position tracking
                self.tracked_positions = {}
                self.position_history = {}
                self.position_alerts = {}
                self.position_lock = AsyncMock()

                # Real-time settings
                self._realtime_enabled = True

                # Statistics tracking
                self.stats = {
                    "open_positions": 0,
                    "closed_positions": 5,
                    "total_positions": 0,
                    "position_updates": 0,
                    "total_pnl": 2500.0,
                    "realized_pnl": 1500.0,
                    "unrealized_pnl": 1000.0,
                    "best_position_pnl": 1000.0,
                    "worst_position_pnl": -500.0,
                    "avg_hold_time_minutes": 30.0,
                    "longest_hold_time_minutes": 120.0,
                    "winning_positions": 3,
                    "gross_profit": 2000.0,
                    "gross_loss": -500.0,
                    "sharpe_ratio": 1.5,
                    "max_drawdown": 0.05,
                    "total_risk": 0.02,
                    "max_position_risk": 0.01,
                    "portfolio_correlation": 0.3,
                    "var_95": 1000.0,
                    "risk_calculations": 100,
                    "last_position_update": datetime.now(timezone.utc),
                }

                # Mock logger
                self.logger = MagicMock()

            async def get_all_positions(self, account_id=None):
                """Return tracked positions as list."""
                return list(self.tracked_positions.values())

            async def get_portfolio_pnl(self):
                """Mock portfolio P&L calculation."""
                return {
                    "total_pnl": self.stats["total_pnl"],
                    "realized_pnl": self.stats["realized_pnl"],
                    "unrealized_pnl": self.stats["unrealized_pnl"],
                    "positions": [],
                }

            async def get_risk_metrics(self, account_id=None):
                """Mock risk metrics."""
                return {
                    "current_risk": 31900.0,
                    "max_risk": 0.02,
                    "daily_loss": 0.0,
                    "daily_loss_limit": 0.03,
                    "position_count": len(self.tracked_positions),
                    "position_limit": 5,
                    "daily_trades": 10,
                    "daily_trade_limit": 20,
                    "win_rate": 0.6,
                    "profit_factor": 4.0,
                    "sharpe_ratio": 1.5,
                    "max_drawdown": 0.05,
                    "position_risks": [],
                    "risk_per_trade": 0.01,
                    "account_balance": 100000.0,
                    "margin_used": 3190.0,
                    "margin_available": 96810.0,
                }


        return TestReportingManager(mock_client)

    @pytest.fixture
    def sample_positions(self):
        """Create sample positions for testing."""
        return {
            "pos1": Position(
                id=1,
                accountId=12345,
                contractId="MNQ",
                creationTimestamp=datetime.now(timezone.utc).isoformat(),
                type=PositionType.LONG.value,
                size=2,
                averagePrice=20000.0,
            ),
            "pos2": Position(
                id=2,
                accountId=12345,
                contractId="ES",
                creationTimestamp=datetime.now(timezone.utc).isoformat(),
                type=PositionType.SHORT.value,
                size=-1,
                averagePrice=5000.0,
            ),
            "pos3": Position(
                id=3,
                accountId=12345,
                contractId="NQ",
                creationTimestamp=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
                type=PositionType.LONG.value,
                size=0,  # Closed position
                averagePrice=15000.0,
            ),
        }

    @pytest.mark.asyncio
    async def test_get_position_statistics_basic(self, reporting_mixin, sample_positions):
        """Test basic position statistics retrieval."""
        reporting_mixin.tracked_positions = sample_positions

        stats = await reporting_mixin.get_position_statistics()

        assert isinstance(stats, dict)
        assert stats["open_positions"] == 2  # Only non-zero positions
        assert stats["total_positions"] == 3
        assert stats["total_pnl"] == 2500.0
        assert stats["realized_pnl"] == 1500.0
        assert stats["unrealized_pnl"] == 1000.0
        assert stats["position_updates"] == 1

    @pytest.mark.asyncio
    async def test_get_position_statistics_performance_metrics(self, reporting_mixin, sample_positions):
        """Test performance metrics calculation in statistics."""
        reporting_mixin.tracked_positions = sample_positions

        stats = await reporting_mixin.get_position_statistics()

        # Check performance metrics
        assert stats["win_rate"] == 0.6  # 3 winning out of 5 closed
        assert stats["profit_factor"] == 4.0  # 2000 / 500
        assert stats["sharpe_ratio"] == 1.5
        assert stats["max_drawdown"] == 0.05
        assert "best_position_pnl" in stats
        assert "worst_position_pnl" in stats

    @pytest.mark.asyncio
    async def test_get_position_statistics_empty(self, reporting_mixin):
        """Test statistics with no positions."""
        reporting_mixin.tracked_positions = {}

        stats = await reporting_mixin.get_position_statistics()

        assert stats["open_positions"] == 0
        assert stats["total_positions"] == 0
        assert stats["avg_position_size"] == 0.0
        assert stats["largest_position"] == 0

    @pytest.mark.asyncio
    async def test_get_position_statistics_position_sizing(self, reporting_mixin, sample_positions):
        """Test position sizing statistics."""
        reporting_mixin.tracked_positions = sample_positions

        stats = await reporting_mixin.get_position_statistics()

        # Check position sizing metrics
        assert stats["avg_position_size"] == 1.5  # (2 + 1) / 2 (excluding closed)
        assert stats["largest_position"] == 2
        assert stats["avg_hold_time_minutes"] == 30.0
        assert stats["longest_hold_time_minutes"] == 120.0

    @pytest.mark.asyncio
    async def test_get_position_statistics_risk_metrics(self, reporting_mixin):
        """Test risk-related statistics."""
        reporting_mixin.tracked_positions = {}

        stats = await reporting_mixin.get_position_statistics()

        assert stats["total_risk"] == 0.02
        assert stats["max_position_risk"] == 0.01
        assert stats["portfolio_correlation"] == 0.3
        assert stats["var_95"] == 1000.0
        assert stats["risk_calculations"] == 100

    @pytest.mark.asyncio
    async def test_get_position_statistics_timestamp_handling(self, reporting_mixin):
        """Test timestamp formatting in statistics."""
        reporting_mixin.tracked_positions = {}

        stats = await reporting_mixin.get_position_statistics()

        assert stats["last_position_update"] is not None
        assert isinstance(stats["last_position_update"], str)
        # Verify ISO format
        datetime.fromisoformat(stats["last_position_update"])

    @pytest.mark.asyncio
    async def test_get_position_history_basic(self, reporting_mixin):
        """Test position history retrieval."""
        # Setup history
        test_history = [
            {
                "timestamp": datetime.now(timezone.utc) - timedelta(minutes=30),
                "position": {"size": 1},
                "size_change": 1,
            },
            {
                "timestamp": datetime.now(timezone.utc) - timedelta(minutes=15),
                "position": {"size": 2},
                "size_change": 1,
            },
            {
                "timestamp": datetime.now(timezone.utc),
                "position": {"size": 0},
                "size_change": -2,
            },
        ]
        reporting_mixin.position_history["MNQ"] = test_history

        history = await reporting_mixin.get_position_history("MNQ")

        assert len(history) == 3
        assert history[0]["size_change"] == 1
        assert history[-1]["size_change"] == -2

    @pytest.mark.asyncio
    async def test_get_position_history_with_limit(self, reporting_mixin):
        """Test position history with limit."""
        # Create large history
        test_history = [
            {
                "timestamp": datetime.now(timezone.utc) - timedelta(minutes=i),
                "position": {"size": i},
                "size_change": 1,
            }
            for i in range(200, 0, -1)
        ]
        reporting_mixin.position_history["ES"] = test_history

        history = await reporting_mixin.get_position_history("ES", limit=50)

        assert len(history) == 50
        # Should return most recent entries
        assert history[-1]["position"]["size"] == 1

    @pytest.mark.asyncio
    async def test_get_position_history_nonexistent(self, reporting_mixin):
        """Test history for non-existent contract."""
        history = await reporting_mixin.get_position_history("NONEXISTENT")

        assert history == []

    @pytest.mark.asyncio
    async def test_get_position_history_thread_safety(self, reporting_mixin):
        """Test thread safety of history access."""
        reporting_mixin.position_history["TEST"] = [{"data": "test"}]

        history = await reporting_mixin.get_position_history("TEST")

        # Verify lock was acquired
        reporting_mixin.position_lock.__aenter__.assert_called()
        assert len(history) == 1

    @pytest.mark.asyncio
    async def test_export_portfolio_report_comprehensive(self, reporting_mixin, sample_positions):
        """Test comprehensive portfolio report generation."""
        reporting_mixin.tracked_positions = sample_positions

        # Add some alerts
        reporting_mixin.position_alerts = {
            "alert1": {"triggered": False},
            "alert2": {"triggered": True},
            "alert3": {"triggered": False},
        }

        report = await reporting_mixin.export_portfolio_report()

        assert isinstance(report, dict)
        assert "report_timestamp" in report
        assert isinstance(report["report_timestamp"], datetime)

        # Check portfolio summary
        summary = report["portfolio_summary"]
        assert summary["total_positions"] == 3
        assert summary["total_pnl"] == 2500.0
        assert summary["total_exposure"] == 31900.0
        assert summary["portfolio_risk"] == 0.02

    @pytest.mark.asyncio
    async def test_export_portfolio_report_positions(self, reporting_mixin, sample_positions):
        """Test positions section of portfolio report."""
        reporting_mixin.tracked_positions = sample_positions

        report = await reporting_mixin.export_portfolio_report()

        assert "positions" in report
        assert len(report["positions"]) == 3
        # Verify positions are actual Position objects
        for pos in report["positions"]:
            assert hasattr(pos, "id")
            assert hasattr(pos, "contractId")

    @pytest.mark.asyncio
    async def test_export_portfolio_report_risk_analysis(self, reporting_mixin):
        """Test risk analysis section of portfolio report."""
        reporting_mixin.tracked_positions = {}

        report = await reporting_mixin.export_portfolio_report()

        assert "risk_analysis" in report
        risk = report["risk_analysis"]
        assert risk["current_risk"] == 31900.0
        assert risk["max_risk"] == 0.02
        assert risk["position_count"] == 0

    @pytest.mark.asyncio
    async def test_export_portfolio_report_statistics(self, reporting_mixin):
        """Test statistics section of portfolio report."""
        reporting_mixin.tracked_positions = {}

        report = await reporting_mixin.export_portfolio_report()

        assert "statistics" in report
        stats = report["statistics"]
        # Fixed - now properly awaits get_position_statistics()
        assert stats["total_pnl"] == 2500.0
        assert stats["realized_pnl"] == 1500.0

    @pytest.mark.asyncio
    async def test_export_portfolio_report_alerts(self, reporting_mixin):
        """Test alerts section of portfolio report."""
        reporting_mixin.position_alerts = {
            "alert1": {"triggered": False},
            "alert2": {"triggered": True},
            "alert3": {"triggered": False},
            "alert4": {"triggered": True},
            "alert5": {"triggered": True},
        }

        report = await reporting_mixin.export_portfolio_report()

        assert "alerts" in report
        alerts = report["alerts"]
        assert alerts["active_alerts"] == 2  # Not triggered
        assert alerts["triggered_alerts"] == 3  # Triggered

    @pytest.mark.asyncio
    async def test_export_portfolio_report_json_serializable(self, reporting_mixin):
        """Test that report can be JSON serialized."""
        reporting_mixin.tracked_positions = {}

        report = await reporting_mixin.export_portfolio_report()

        # Should be JSON serializable (with datetime handling)
        json_str = json.dumps(report, default=str)
        assert len(json_str) > 0

    def test_get_realtime_validation_status_basic(self, reporting_mixin):
        """Test basic real-time validation status."""
        status = reporting_mixin.get_realtime_validation_status()

        assert isinstance(status, dict)
        assert status["realtime_enabled"] is True
        assert status["tracked_positions_count"] == 0

    def test_get_realtime_validation_status_payload_validation(self, reporting_mixin):
        """Test payload validation configuration."""
        status = reporting_mixin.get_realtime_validation_status()

        assert "payload_validation" in status
        validation = status["payload_validation"]
        assert validation["enabled"] is True
        assert "required_fields" in validation
        assert len(validation["required_fields"]) == 7
        assert "id" in validation["required_fields"]
        assert "size" in validation["required_fields"]

    def test_get_realtime_validation_status_position_type_enum(self, reporting_mixin):
        """Test position type enum validation."""
        status = reporting_mixin.get_realtime_validation_status()

        validation = status["payload_validation"]
        assert "position_type_enum" in validation
        enum_map = validation["position_type_enum"]
        assert enum_map["Undefined"] == 0
        assert enum_map["Long"] == 1
        assert enum_map["Short"] == 2

    def test_get_realtime_validation_status_compliance(self, reporting_mixin):
        """Test ProjectX compliance status."""
        status = reporting_mixin.get_realtime_validation_status()

        assert "projectx_compliance" in status
        compliance = status["projectx_compliance"]
        assert "gateway_user_position_format" in compliance
        assert "position_type_enum" in compliance
        assert "closure_logic" in compliance
        assert "payload_structure" in compliance

        # All should be compliant
        for key, value in compliance.items():
            assert "✅" in value

    def test_get_realtime_validation_status_closure_detection(self, reporting_mixin):
        """Test closure detection configuration."""
        status = reporting_mixin.get_realtime_validation_status()

        validation = status["payload_validation"]
        assert validation["closure_detection"] == "size == 0 (not type == 0)"

    def test_get_realtime_validation_status_statistics_copy(self, reporting_mixin):
        """Test that statistics are copied not referenced."""
        status = reporting_mixin.get_realtime_validation_status()

        assert "statistics" in status
        stats = status["statistics"]

        # Modify the returned stats
        original_value = stats["total_pnl"]
        stats["total_pnl"] = 999999.0

        # Original should be unchanged
        assert reporting_mixin.stats["total_pnl"] == original_value

    def test_get_realtime_validation_status_with_positions(self, reporting_mixin, sample_positions):
        """Test validation status with tracked positions."""
        reporting_mixin.tracked_positions = sample_positions

        status = reporting_mixin.get_realtime_validation_status()

        assert status["tracked_positions_count"] == 3

    @pytest.mark.asyncio
    async def test_statistics_calculation_edge_cases(self, reporting_mixin):
        """Test edge cases in statistics calculations."""
        # Test with no closed positions
        reporting_mixin.stats["closed_positions"] = 0
        reporting_mixin.stats["winning_positions"] = 0
        reporting_mixin.stats["gross_profit"] = 0
        reporting_mixin.stats["gross_loss"] = 0

        stats = await reporting_mixin.get_position_statistics()

        assert stats["win_rate"] == 0.0
        assert stats["profit_factor"] == 0.0

    @pytest.mark.asyncio
    async def test_statistics_null_timestamp_handling(self, reporting_mixin):
        """Test handling of null last_position_update."""
        reporting_mixin.stats["last_position_update"] = None
        reporting_mixin.tracked_positions = {}

        stats = await reporting_mixin.get_position_statistics()

        assert stats["last_position_update"] is None

    @pytest.mark.asyncio
    async def test_report_generation_performance(self, reporting_mixin):
        """Test performance of report generation with many positions."""
        import time

        # Create many positions
        large_positions = {
            f"pos{i}": Position(
                id=i,
                accountId=12345,
                contractId=f"TEST{i}",
                creationTimestamp=datetime.now(timezone.utc).isoformat(),
                type=PositionType.LONG.value if i % 2 == 0 else PositionType.SHORT.value,
                size=i % 5 + 1,
                averagePrice=10000.0 + i * 100,
            )
            for i in range(100)
        }
        reporting_mixin.tracked_positions = large_positions

        start = time.time()
        report = await reporting_mixin.export_portfolio_report()
        duration = time.time() - start

        assert duration < 1.0  # Should complete within 1 second
        assert report["portfolio_summary"]["total_positions"] == 100
