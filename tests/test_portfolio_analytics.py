"""
Test suite for Portfolio Analytics functionality
"""

from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest

from project_x_py import ProjectX
from project_x_py.exceptions import ProjectXError
from project_x_py.models import Account, Instrument, Position
from project_x_py.position_manager import PositionManager


class TestPortfolioAnalytics:
    """Test cases for portfolio analytics functionality"""

    def test_get_portfolio_pnl_empty(self):
        """Test portfolio P&L calculation with no positions"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        mock_client.search_open_positions.return_value = []
        position_manager = PositionManager(mock_client)
        position_manager.initialize()

        # Act
        portfolio_pnl = position_manager.get_portfolio_pnl()

        # Assert
        assert isinstance(portfolio_pnl, dict)
        assert portfolio_pnl["position_count"] == 0
        assert portfolio_pnl["positions"] == []
        assert "last_updated" in portfolio_pnl
        assert "note" in portfolio_pnl

    def test_get_portfolio_pnl_with_positions(self):
        """Test portfolio P&L with multiple positions"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        mock_positions = [
            Position(
                id=1,
                accountId=1001,
                contractId="CON.F.US.MGC.M25",
                creationTimestamp="2025-01-01T10:00:00Z",
                type=1,  # LONG
                size=2,
                averagePrice=2045.0,
            ),
            Position(
                id=2,
                accountId=1001,
                contractId="CON.F.US.MES.H25",
                creationTimestamp="2025-01-01T11:00:00Z",
                type=2,  # SHORT
                size=1,
                averagePrice=5400.0,
            ),
        ]
        mock_client.search_open_positions.return_value = mock_positions
        position_manager = PositionManager(mock_client)
        position_manager.initialize()

        # Act
        portfolio_pnl = position_manager.get_portfolio_pnl()

        # Assert
        assert isinstance(portfolio_pnl, dict)
        assert portfolio_pnl["position_count"] == 2
        assert len(portfolio_pnl["positions"]) == 2

        # Check position breakdown
        position_breakdown = portfolio_pnl["positions"]
        mgc_position = next(
            (p for p in position_breakdown if p["contract_id"] == "CON.F.US.MGC.M25"),
            None,
        )
        assert mgc_position is not None
        assert mgc_position["size"] == 2
        assert mgc_position["avg_price"] == 2045.0
        assert mgc_position["direction"] == "LONG"

    def test_get_risk_metrics_empty(self):
        """Test risk metrics with no positions"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        mock_client.search_open_positions.return_value = []
        mock_account = Account(
            id=1001,
            name="Test Account",
            balance=50000.0,
            canTrade=True,
            isVisible=True,
            simulated=False,
        )
        mock_client.get_account_info.return_value = mock_account
        position_manager = PositionManager(mock_client)
        position_manager.initialize()

        # Act
        risk_metrics = position_manager.get_risk_metrics()

        # Assert
        assert isinstance(risk_metrics, dict)
        assert risk_metrics["portfolio_risk"] == 0.0
        assert risk_metrics["largest_position_risk"] == 0.0
        assert risk_metrics["total_exposure"] == 0.0
        assert risk_metrics["position_count"] == 0
        assert risk_metrics["diversification_score"] == 1.0

    def test_get_risk_metrics_with_positions(self):
        """Test risk metrics with active positions"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        mock_positions = [
            Position(
                id=1,
                accountId=1001,
                contractId="CON.F.US.MGC.M25",
                creationTimestamp="2025-01-01T10:00:00Z",
                type=1,  # LONG
                size=5,
                averagePrice=2045.0,
            ),
            Position(
                id=2,
                accountId=1001,
                contractId="CON.F.US.MES.H25",
                creationTimestamp="2025-01-01T11:00:00Z",
                type=2,  # SHORT
                size=2,
                averagePrice=5400.0,
            ),
        ]
        mock_client.search_open_positions.return_value = mock_positions
        mock_account = Account(
            id=1001,
            name="Test Account",
            balance=50000.0,
            canTrade=True,
            isVisible=True,
            simulated=False,
        )
        mock_client.get_account_info.return_value = mock_account
        position_manager = PositionManager(mock_client)
        position_manager.initialize()

        # Act
        risk_metrics = position_manager.get_risk_metrics()

        # Assert
        assert isinstance(risk_metrics, dict)
        assert risk_metrics["position_count"] == 2
        assert risk_metrics["total_exposure"] > 0.0
        assert 0.0 <= risk_metrics["largest_position_risk"] <= 1.0
        assert 0.0 <= risk_metrics["diversification_score"] <= 1.0
        assert isinstance(risk_metrics["risk_warnings"], list)

    def test_calculate_position_size_basic(self):
        """Test basic position sizing calculation"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        mock_instrument = Instrument(
            id="CON.F.US.MGC.M25",
            name="MGC March 2025",
            description="E-mini Gold Futures",
            tickSize=0.1,
            tickValue=10.0,
            activeContract=True,
        )
        mock_account = Account(
            id=1001,
            name="Test Account",
            balance=50000.0,
            canTrade=True,
            isVisible=True,
            simulated=False,
        )
        mock_client.get_instrument.return_value = mock_instrument
        mock_client.get_account_info.return_value = mock_account
        position_manager = PositionManager(mock_client)
        position_manager.initialize()

        # Act
        sizing_result = position_manager.calculate_position_size(
            contract_id="CON.F.US.MGC.M25",
            risk_amount=100.0,
            entry_price=2045.0,
            stop_price=2040.0,
        )

        # Assert
        assert isinstance(sizing_result, dict)
        assert "suggested_size" in sizing_result
        assert "risk_per_contract" in sizing_result
        assert "total_risk" in sizing_result
        assert "risk_percentage" in sizing_result
        assert sizing_result["entry_price"] == 2045.0
        assert sizing_result["stop_price"] == 2040.0
        assert sizing_result["suggested_size"] >= 0

    def test_calculate_position_size_with_max_size(self):
        """Test position sizing with maximum size considerations"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        mock_instrument = Instrument(
            id="CON.F.US.MGC.M25",
            name="MGC March 2025",
            description="E-mini Gold Futures",
            tickSize=0.1,
            tickValue=10.0,
            activeContract=True,
        )
        mock_account = Account(
            id=1001,
            name="Test Account",
            balance=10000.0,  # Smaller account
            canTrade=True,
            isVisible=True,
            simulated=False,
        )
        mock_client.get_instrument.return_value = mock_instrument
        mock_client.get_account_info.return_value = mock_account
        position_manager = PositionManager(mock_client)
        position_manager.initialize()

        # Act
        sizing_result = position_manager.calculate_position_size(
            contract_id="CON.F.US.MGC.M25",
            risk_amount=5000.0,  # Large risk relative to account
            entry_price=2045.0,
            stop_price=2040.0,
        )

        # Assert
        assert isinstance(sizing_result, dict)
        assert sizing_result["risk_percentage"] > 10.0  # Should be high risk percentage
        assert "risk_warnings" in sizing_result
        assert len(sizing_result["risk_warnings"]) > 0  # Should have warnings

    def test_calculate_position_size_invalid_stop(self):
        """Test position sizing with invalid stop price"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        mock_instrument = Instrument(
            id="CON.F.US.MGC.M25",
            name="MGC March 2025",
            description="E-mini Gold Futures",
            tickSize=0.1,
            tickValue=10.0,
            activeContract=True,
        )
        mock_account = Account(
            id=1001,
            name="Test Account",
            balance=50000.0,
            canTrade=True,
            isVisible=True,
            simulated=False,
        )
        mock_client.get_instrument.return_value = mock_instrument
        mock_client.get_account_info.return_value = mock_account
        position_manager = PositionManager(mock_client)
        position_manager.initialize()

        # Act - Same entry and stop price
        sizing_result = position_manager.calculate_position_size(
            contract_id="CON.F.US.MGC.M25",
            risk_amount=100.0,
            entry_price=2045.0,
            stop_price=2045.0,  # Same as entry
        )

        # Assert
        assert isinstance(sizing_result, dict)
        assert "error" in sizing_result
        assert "same" in sizing_result["error"].lower()

    def test_position_concentration_risk(self):
        """Test position concentration risk metrics"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        mock_positions = [
            Position(
                id=1,
                accountId=1001,
                contractId="CON.F.US.MGC.M25",
                creationTimestamp="2025-01-01T10:00:00Z",
                type=1,  # LONG
                size=10,  # Large position
                averagePrice=2045.0,
            ),
            Position(
                id=2,
                accountId=1001,
                contractId="CON.F.US.MES.H25",
                creationTimestamp="2025-01-01T11:00:00Z",
                type=1,  # LONG
                size=1,
                averagePrice=5400.0,
            ),
        ]
        mock_client.search_open_positions.return_value = mock_positions
        position_manager = PositionManager(mock_client)
        position_manager.initialize()

        # Act
        risk_metrics = position_manager.get_risk_metrics()

        # Assert
        assert isinstance(risk_metrics, dict)
        assert risk_metrics["position_count"] == 2
        # MGC position should dominate exposure due to size and price
        assert risk_metrics["largest_position_risk"] > 0.5  # Should be concentrated
        assert risk_metrics["diversification_score"] < 0.5  # Low diversification

    def test_portfolio_pnl_by_instrument(self):
        """Test getting P&L broken down by instrument"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        mock_positions = [
            Position(
                id=1,
                accountId=1001,
                contractId="CON.F.US.MGC.M25",
                creationTimestamp="2025-01-01T10:00:00Z",
                type=1,  # LONG
                size=2,
                averagePrice=2045.0,
            ),
            Position(
                id=2,
                accountId=1001,
                contractId="CON.F.US.MGC.H25",  # Same instrument, different month
                creationTimestamp="2025-01-01T11:00:00Z",
                type=1,  # LONG
                size=1,
                averagePrice=2046.0,
            ),
        ]
        mock_client.search_open_positions.return_value = mock_positions
        position_manager = PositionManager(mock_client)
        position_manager.initialize()

        # Act
        portfolio_pnl = position_manager.get_portfolio_pnl()

        # Assert
        assert isinstance(portfolio_pnl, dict)
        assert portfolio_pnl["position_count"] == 2
        assert len(portfolio_pnl["positions"]) == 2

        # Both positions should be present
        position_breakdown = portfolio_pnl["positions"]
        mgc_m25 = next(
            (p for p in position_breakdown if "MGC.M25" in p["contract_id"]), None
        )
        mgc_h25 = next(
            (p for p in position_breakdown if "MGC.H25" in p["contract_id"]), None
        )

        assert mgc_m25 is not None
        assert mgc_h25 is not None
        assert mgc_m25["size"] == 2
        assert mgc_h25["size"] == 1

    def test_calculate_portfolio_pnl_with_prices(self):
        """Test portfolio P&L calculation with current market prices"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        mock_positions = [
            Position(
                id=1,
                accountId=1001,
                contractId="CON.F.US.MGC.M25",
                creationTimestamp="2025-01-01T10:00:00Z",
                type=1,  # LONG
                size=2,
                averagePrice=2045.0,
            ),
            Position(
                id=2,
                accountId=1001,
                contractId="CON.F.US.MES.H25",
                creationTimestamp="2025-01-01T11:00:00Z",
                type=2,  # SHORT
                size=1,
                averagePrice=5400.0,
            ),
        ]
        mock_client.search_open_positions.return_value = mock_positions
        position_manager = PositionManager(mock_client)
        position_manager.initialize()

        # Act - Use the method that accepts current prices
        current_prices = {
            "CON.F.US.MGC.M25": 2050.0,  # Gained $5 per contract
            "CON.F.US.MES.H25": 5390.0,  # Price dropped $10 (short position gains)
        }
        portfolio_pnl = position_manager.calculate_portfolio_pnl(current_prices)

        # Assert
        assert isinstance(portfolio_pnl, dict)
        assert "total_pnl" in portfolio_pnl
        assert "positions_count" in portfolio_pnl
        assert "position_breakdown" in portfolio_pnl
        assert portfolio_pnl["positions_with_prices"] == 2
        assert portfolio_pnl["positions_without_prices"] == 0

        # Check individual position P&L
        breakdown = portfolio_pnl["position_breakdown"]
        mgc_breakdown = next((p for p in breakdown if "MGC" in p["contract_id"]), None)
        mes_breakdown = next((p for p in breakdown if "MES" in p["contract_id"]), None)

        assert mgc_breakdown is not None
        assert mes_breakdown is not None
        assert mgc_breakdown["unrealized_pnl"] > 0  # LONG position gained (price up)
        assert mes_breakdown["unrealized_pnl"] > 0  # SHORT position gained (price down)
