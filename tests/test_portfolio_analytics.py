"""
Test suite for Portfolio Analytics functionality
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from project_x_py import ProjectX
from project_x_py.position_manager import PositionManager
from project_x_py.models import Position, Instrument
from project_x_py.exceptions import ProjectXError


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
        assert portfolio_pnl["total_unrealized"] == 0.0
        assert portfolio_pnl["total_realized"] == 0.0
        assert portfolio_pnl["total_pnl"] == 0.0
        assert portfolio_pnl["positions"] == {}
    
    def test_get_portfolio_pnl_with_positions(self):
        """Test portfolio P&L with multiple positions"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        mock_positions = [
            Position(
                contract_id="CON.F.US.MGC.M25",
                instrument="MGC",
                side=0,
                quantity=2,
                average_price=2045.0,
                realized_pnl=100.0,
                unrealized_pnl=50.0
            ),
            Position(
                contract_id="CON.F.US.MES.H25",
                instrument="MES",
                side=1,
                quantity=1,
                average_price=5400.0,
                realized_pnl=-50.0,
                unrealized_pnl=25.0
            )
        ]
        mock_client.search_open_positions.return_value = mock_positions
        position_manager = PositionManager(mock_client)
        position_manager.initialize()
        
        # Act
        portfolio_pnl = position_manager.get_portfolio_pnl()
        
        # Assert
        assert portfolio_pnl["total_unrealized"] == 75.0  # 50 + 25
        assert portfolio_pnl["total_realized"] == 50.0  # 100 - 50
        assert portfolio_pnl["total_pnl"] == 125.0  # 75 + 50
        assert len(portfolio_pnl["positions"]) == 2
        assert "MGC" in portfolio_pnl["positions"]
        assert "MES" in portfolio_pnl["positions"]
    
    def test_get_risk_metrics_empty(self):
        """Test risk metrics with no positions"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        mock_client.search_open_positions.return_value = []
        mock_client.get_account_balance.return_value = 50000.0
        position_manager = PositionManager(mock_client)
        position_manager.initialize()
        
        # Act
        risk_metrics = position_manager.get_risk_metrics()
        
        # Assert
        assert isinstance(risk_metrics, dict)
        assert risk_metrics["portfolio_value"] == 50000.0
        assert risk_metrics["total_exposure"] == 0.0
        assert risk_metrics["position_count"] == 0
        assert risk_metrics["largest_position"] is None
        assert risk_metrics["total_margin_used"] == 0.0
    
    def test_get_risk_metrics_with_positions(self):
        """Test risk metrics with active positions"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        mock_positions = [
            Position(
                contract_id="CON.F.US.MGC.M25",
                instrument="MGC",
                side=0,
                quantity=5,
                average_price=2045.0,
                margin_requirement=500.0
            ),
            Position(
                contract_id="CON.F.US.MES.H25",
                instrument="MES",
                side=1,
                quantity=2,
                average_price=5400.0,
                margin_requirement=1200.0
            )
        ]
        mock_client.search_open_positions.return_value = mock_positions
        mock_client.get_account_balance.return_value = 50000.0
        
        # Mock instruments for exposure calculation
        mock_mgc = Instrument(
            id="CON.F.US.MGC.M25",
            tickValue=10.0,
            tickSize=0.1
        )
        mock_mes = Instrument(
            id="CON.F.US.MES.H25",
            tickValue=5.0,
            tickSize=0.25
        )
        mock_client.get_instrument.side_effect = lambda x: mock_mgc if x == "MGC" else mock_mes
        
        position_manager = PositionManager(mock_client)
        position_manager.initialize()
        
        # Act
        risk_metrics = position_manager.get_risk_metrics()
        
        # Assert
        assert risk_metrics["portfolio_value"] == 50000.0
        assert risk_metrics["position_count"] == 2
        assert risk_metrics["total_margin_used"] == 1700.0  # 500 + 1200
        assert risk_metrics["largest_position"]["instrument"] == "MES"  # Larger margin requirement
        assert risk_metrics["total_exposure"] > 0  # Should calculate based on notional values
    
    def test_calculate_position_size_basic(self):
        """Test basic position sizing calculation"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        mock_instrument = Instrument(
            id="CON.F.US.MGC.M25",
            tickValue=10.0,
            tickSize=0.1
        )
        mock_client.get_instrument.return_value = mock_instrument
        position_manager = PositionManager(mock_client)
        position_manager.initialize()
        
        # Act
        risk_amount = 100.0  # Risk $100
        entry_price = 2045.0
        stop_price = 2040.0  # $5 stop = 50 ticks
        
        size = position_manager.calculate_position_size(
            "MGC", risk_amount, entry_price, stop_price
        )
        
        # Assert
        # Risk per contract = 50 ticks * $10/tick = $500
        # Position size = $100 / $500 = 0.2 contracts
        assert size == 0.2
    
    def test_calculate_position_size_with_max_size(self):
        """Test position sizing with maximum size limit"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        mock_instrument = Instrument(
            id="CON.F.US.MGC.M25",
            tickValue=10.0,
            tickSize=0.1
        )
        mock_client.get_instrument.return_value = mock_instrument
        position_manager = PositionManager(mock_client)
        position_manager.initialize()
        
        # Act
        risk_amount = 10000.0  # Large risk amount
        entry_price = 2045.0
        stop_price = 2044.9  # Tight stop
        max_size = 5
        
        size = position_manager.calculate_position_size(
            "MGC", risk_amount, entry_price, stop_price, max_size=max_size
        )
        
        # Assert
        assert size == max_size  # Should be capped at max_size
    
    def test_calculate_position_size_invalid_stop(self):
        """Test position sizing with invalid stop price"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        mock_instrument = Instrument(
            id="CON.F.US.MGC.M25",
            tickValue=10.0,
            tickSize=0.1
        )
        mock_client.get_instrument.return_value = mock_instrument
        position_manager = PositionManager(mock_client)
        position_manager.initialize()
        
        # Act & Assert
        # Stop price on wrong side of entry (long position with stop above entry)
        with pytest.raises(ValueError):
            position_manager.calculate_position_size(
                "MGC", 100.0, 2045.0, 2050.0, side=0  # Long with stop above
            )
    
    def test_position_concentration_risk(self):
        """Test position concentration risk metrics"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        mock_positions = [
            Position(
                contract_id="CON.F.US.MGC.M25",
                instrument="MGC",
                side=0,
                quantity=10,  # Large position
                average_price=2045.0,
                margin_requirement=1000.0
            ),
            Position(
                contract_id="CON.F.US.MES.H25",
                instrument="MES",
                side=0,
                quantity=1,
                average_price=5400.0,
                margin_requirement=100.0
            )
        ]
        mock_client.search_open_positions.return_value = mock_positions
        mock_client.get_account_balance.return_value = 50000.0
        
        position_manager = PositionManager(mock_client)
        position_manager.initialize()
        
        # Act
        risk_metrics = position_manager.get_risk_metrics()
        
        # Assert
        # MGC represents 90.9% of margin (1000/1100)
        largest_position = risk_metrics["largest_position"]
        assert largest_position["instrument"] == "MGC"
        assert largest_position["margin_percentage"] > 90.0
    
    def test_portfolio_pnl_by_instrument(self):
        """Test getting P&L broken down by instrument"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        mock_positions = [
            Position(
                contract_id="CON.F.US.MGC.M25",
                instrument="MGC",
                side=0,
                quantity=2,
                average_price=2045.0,
                realized_pnl=100.0,
                unrealized_pnl=50.0
            ),
            Position(
                contract_id="CON.F.US.MGC.M25",  # Same instrument, different month
                instrument="MGC",
                side=0,
                quantity=1,
                average_price=2046.0,
                realized_pnl=25.0,
                unrealized_pnl=10.0
            )
        ]
        mock_client.search_open_positions.return_value = mock_positions
        position_manager = PositionManager(mock_client)
        position_manager.initialize()
        
        # Act
        portfolio_pnl = position_manager.get_portfolio_pnl()
        
        # Assert
        # Both positions should be aggregated under MGC
        mgc_pnl = portfolio_pnl["positions"]["MGC"]
        assert mgc_pnl["total_quantity"] == 3
        assert mgc_pnl["unrealized_pnl"] == 60.0  # 50 + 10
        assert mgc_pnl["realized_pnl"] == 125.0  # 100 + 25