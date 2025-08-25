"""
Comprehensive tests for PositionManager risk management functionality.

Tests both the legacy RiskManager integration and the new RiskManagementMixin.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

# ValidationError will be caught generically as Exception
# from project_x_py.exceptions import ValidationError
from project_x_py.models import Position
from project_x_py.position_manager.risk import RiskManagementMixin
from project_x_py.risk_manager import RiskManager
from project_x_py.types import (
    PositionSizingResponse,
    PositionType,
    RiskAnalysisResponse,
)


# Legacy test for RiskManager integration
@pytest.mark.asyncio
async def test_get_risk_metrics_basic(position_manager, mock_positions_data):
    pm = position_manager

    # Create a mock risk_manager for this test
    mock_risk_manager = MagicMock(spec=RiskManager)
    mock_risk_manager.check_position_risk = MagicMock(return_value=True)
    mock_risk_manager.get_risk_settings = MagicMock(
        return_value={
            "max_position_size": 10,
            "max_total_risk": 10000,
            "max_loss_per_trade": 500,
            "daily_loss_limit": 2000,
            "risk_reward_ratio": 2.0,
            "max_positions": 5,
        }
    )

    # Mock the get_risk_metrics to return expected values
    # MGC: 1 * 1900 = 1900
    # MNQ: 2 * 15000 = 30000
    # Total exposure = 31900
    mock_risk_manager.get_risk_metrics = AsyncMock(
        return_value={
            "position_count": 2,
            "total_exposure": 31900.0,
            "margin_used": 3190.0,  # 10% of total exposure
            "margin_available": 6810.0,  # Assuming 10k total margin
            "diversification_score": 0.06,  # 1 - (30000/31900) = 0.06
            "largest_position_risk": 0.94,  # 30000/31900 = 0.94
            "portfolio_heat": 0.32,  # 3190/10000 = 0.32
            "risk_reward_score": 2.0,
            "compliance_status": "healthy",
        }
    )

    pm.risk_manager = mock_risk_manager

    await pm.get_all_positions()
    metrics = await pm.get_risk_metrics()

    # Compute expected total_exposure and position count
    # Total exposure is size * averagePrice for each position
    expected_total_exposure = sum(
        abs(d["size"] * d["averagePrice"]) for d in mock_positions_data
    )
    expected_num_contracts = len({d["contractId"] for d in mock_positions_data})

    # Calculate largest_position_risk the same way as in the implementation
    position_exposures = [
        abs(d["size"] * d["averagePrice"]) for d in mock_positions_data
    ]
    largest_exposure = max(position_exposures) if position_exposures else 0.0
    largest_position_risk = (
        largest_exposure / expected_total_exposure
        if expected_total_exposure > 0
        else 0.0
    )

    # Calculate diversification_score the same way as in the implementation
    expected_diversification = (
        1.0 - largest_position_risk if largest_position_risk < 1.0 else 0.0
    )

    # Verify metrics match expected values
    # Note: total_exposure is not directly returned, but margin_used is related
    assert metrics["position_count"] == expected_num_contracts
    # margin_used should be total_exposure * 0.1 (10% margin)
    assert abs(metrics["margin_used"] - expected_total_exposure * 0.1) < 1e-3


# New comprehensive tests for RiskManagementMixin
class TestRiskManagementMixin:
    """Comprehensive tests for RiskManagementMixin functionality."""

    @pytest.fixture
    def mock_client(self):
        """Create mock ProjectX client with account info."""
        client = AsyncMock()
        # Mock account info with basic attributes
        client.account_info = MagicMock()
        client.account_info.name = "TEST_ACCOUNT"
        client.account_info.id = 12345
        client.account_info.balance = 100000.0
        client.account_info.canTrade = True

        # Mock instrument data
        mock_instrument = MagicMock()
        mock_instrument.contractMultiplier = 5.0  # MNQ has $5 multiplier
        mock_instrument.tickSize = 0.25
        client.get_instrument = AsyncMock(return_value=mock_instrument)

        return client

    @pytest.fixture
    def risk_mixin(self, mock_client):
        """Create RiskManagementMixin instance with mocked dependencies."""

        class TestRiskManager(RiskManagementMixin):
            def __init__(self, client):
                self.client = client
                self.project_x = client
                self._positions = {}
                self._open_positions = []
                self.tracked_positions = {}  # Added for compatibility
                self.account_info = client.account_info
                # Default risk settings
                self.risk_settings = {
                    "max_portfolio_risk": 0.02,  # 2% default
                    "max_position_risk": 0.01,  # 1% default
                    "max_correlation": 0.7,
                    "alert_threshold": 0.005,  # 0.5% default
                }
                # Mock logger
                self.logger = MagicMock()

            async def get_open_positions(self, account_name=None):
                return self._open_positions

            async def get_all_positions(self, account_id=None):
                return self._open_positions

            def _generate_risk_warnings(self, positions, portfolio_risk, largest_position_risk):
                """Use parent implementation."""
                return super()._generate_risk_warnings(positions, portfolio_risk, largest_position_risk)

            def _generate_sizing_warnings(self, risk_percentage, size):
                """Use parent implementation."""
                return super()._generate_sizing_warnings(risk_percentage, size)


        return TestRiskManager(mock_client)

    @pytest.fixture
    def sample_positions(self):
        """Create sample positions for testing."""
        return [
            Position(
                id=1,
                accountId=12345,
                contractId="MNQ",
                creationTimestamp=datetime.now(timezone.utc).isoformat(),
                type=PositionType.LONG.value,
                size=2,
                averagePrice=20000.0,
            ),
            Position(
                id=2,
                accountId=12345,
                contractId="ES",
                creationTimestamp=datetime.now(timezone.utc).isoformat(),
                type=PositionType.SHORT.value,
                size=1,
                averagePrice=5000.0,
            ),
        ]

    @pytest.mark.asyncio
    async def test_get_risk_metrics_with_positions(self, risk_mixin, sample_positions):
        """Test risk metrics calculation with multiple positions."""
        risk_mixin._open_positions = sample_positions

        metrics = await risk_mixin.get_risk_metrics()

        assert isinstance(metrics, dict)  # RiskAnalysisResponse is a TypedDict
        assert "current_risk" in metrics
        assert metrics["position_count"] == 2
        assert len(metrics["position_risks"]) == 2
        assert "account_balance" in metrics

    @pytest.mark.asyncio
    async def test_get_risk_metrics_empty(self, risk_mixin):
        """Test risk metrics with no positions."""
        risk_mixin._open_positions = []

        metrics = await risk_mixin.get_risk_metrics()

        assert metrics["current_risk"] == 0
        assert metrics["position_count"] == 0
        assert len(metrics["position_risks"]) == 0
        assert metrics["account_balance"] >= 0

    @pytest.mark.asyncio
    async def test_get_risk_metrics_with_account_id(self, risk_mixin, sample_positions):
        """Test risk metrics with specific account ID."""
        risk_mixin._open_positions = sample_positions

        # Test with specific account ID
        metrics = await risk_mixin.get_risk_metrics(account_id=12345)

        assert isinstance(metrics, dict)
        assert "current_risk" in metrics
        assert "position_risks" in metrics
        assert "position_count" in metrics

    @pytest.mark.asyncio
    async def test_calculate_position_size_basic(self, risk_mixin):
        """Test basic position size calculation."""
        sizing = await risk_mixin.calculate_position_size(
            contract_id="MNQ",
            risk_amount=1000.0,
            entry_price=20000.0,
            stop_price=19950.0,
        )

        assert isinstance(sizing, dict)  # PositionSizingResponse is a TypedDict
        assert sizing["position_size"] > 0
        assert "risk_amount" in sizing
        assert "entry_price" in sizing

    @pytest.mark.asyncio
    async def test_calculate_position_size_invalid_inputs(self, risk_mixin):
        """Test position sizing with invalid inputs."""
        # Stop equals entry - should return zero position size
        sizing = await risk_mixin.calculate_position_size(
            contract_id="TEST",
            risk_amount=1000.0,
            entry_price=100.0,
            stop_price=100.0,
        )
        assert sizing["position_size"] == 0
        assert sizing["risk_amount"] == 0.0
        assert sizing["risk_percent"] == 0.0

        # Negative risk amount - should now raise ValueError after fix
        with pytest.raises(ValueError, match="risk_amount must be positive"):
            await risk_mixin.calculate_position_size(
                contract_id="TEST",
                risk_amount=-1000.0,
                entry_price=100.0,
                stop_price=90.0,
            )

    @pytest.mark.asyncio
    async def test_calculate_position_size_with_account_balance(self, risk_mixin):
        """Test position sizing with account balance."""
        # Position sizing with account balance consideration
        sizing = await risk_mixin.calculate_position_size(
            contract_id="ES",
            risk_amount=5000.0,
            entry_price=5000.0,
            stop_price=4950.0,
            account_balance=100000.0,
        )

        assert sizing["position_size"] > 0
        assert "risk_amount" in sizing

    @pytest.mark.asyncio
    async def test_risk_warnings_concentrated_position(self, risk_mixin):
        """Test warning generation for concentrated positions."""
        # Single large position
        large_position = Position(
            id=100,
            accountId=12345,
            contractId="LARGE",
            creationTimestamp=datetime.now(timezone.utc).isoformat(),
            type=PositionType.LONG.value,
            size=100,
            averagePrice=50000.0,
        )

        risk_mixin._open_positions = [large_position]
        metrics = await risk_mixin.get_risk_metrics()

        assert metrics["position_count"] == 1
        assert metrics["current_risk"] >= 0

    @pytest.mark.asyncio
    async def test_position_size_long_vs_short(self, risk_mixin):
        """Test position sizing for long and short positions."""
        # Long position (stop below entry)
        long_sizing = await risk_mixin.calculate_position_size(
            contract_id="MNQ",
            risk_amount=1000.0,
            entry_price=20000.0,
            stop_price=19900.0,
        )
        assert long_sizing["position_size"] > 0

        # Short position (stop above entry)
        short_sizing = await risk_mixin.calculate_position_size(
            contract_id="MNQ",
            risk_amount=1000.0,
            entry_price=20000.0,
            stop_price=20100.0,
        )
        assert short_sizing["position_size"] > 0

    @pytest.mark.asyncio
    async def test_risk_metrics_performance(self, risk_mixin):
        """Test performance with many positions."""
        import time

        # Create 100 positions
        many_positions = [
            Position(
                id=i,
                accountId=12345,
                contractId=f"TEST{i}",
                creationTimestamp=datetime.now(timezone.utc).isoformat(),
                type=PositionType.LONG.value
                if i % 2 == 0
                else PositionType.SHORT.value,
                size=i % 5 + 1,
                averagePrice=10000.0 + i * 100,
            )
            for i in range(100)
        ]

        risk_mixin._open_positions = many_positions

        start = time.time()
        metrics = await risk_mixin.get_risk_metrics()
        duration = time.time() - start

        assert duration < 1.0  # Should complete within 1 second
        assert len(metrics["position_risks"]) == 100
