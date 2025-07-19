"""
Test suite for Risk Management features
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from project_x_py import ProjectX
from project_x_py.order_manager import OrderManager
from project_x_py.position_manager import PositionManager
from project_x_py.models import Position, Order, Fill, Instrument
from project_x_py.exceptions import ProjectXOrderError, ProjectXRiskError


class TestRiskManagement:
    """Test cases for risk management features"""
    
    def test_position_size_limits(self):
        """Test position size limit enforcement"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        mock_instrument = Instrument(
            id="CON.F.US.MGC.M25",
            tickValue=10.0,
            tickSize=0.1,
            maxPositionSize=50  # Max 50 contracts
        )
        mock_client.get_instrument.return_value = mock_instrument
        
        # Mock existing position
        mock_position = Position(
            contract_id="CON.F.US.MGC.M25",
            instrument="MGC",
            side=0,
            quantity=45  # Already have 45 contracts
        )
        mock_client.search_open_positions.return_value = [mock_position]
        
        order_manager = OrderManager(mock_client)
        order_manager.initialize()
        
        # Act & Assert
        # Should reject order that would exceed position limit
        with pytest.raises(ProjectXRiskError) as exc_info:
            order_manager.place_market_order("MGC", side=0, size=10)  # Would be 55 total
        
        assert "position size limit" in str(exc_info.value).lower()
    
    def test_daily_loss_limit(self):
        """Test daily loss limit enforcement"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        mock_client.get_account_balance.return_value = 50000.0
        
        # Mock today's fills showing losses
        today_fills = [
            Fill(
                instrument="MGC",
                side=0,
                quantity=2,
                price=2045.0,
                realized_pnl=-500.0,
                timestamp=datetime.now()
            ),
            Fill(
                instrument="MES",
                side=1,
                quantity=1,
                price=5400.0,
                realized_pnl=-400.0,
                timestamp=datetime.now()
            )
        ]
        mock_client.get_fills.return_value = today_fills
        
        order_manager = OrderManager(mock_client)
        order_manager.initialize()
        
        # Set daily loss limit
        order_manager.set_daily_loss_limit(1000.0)
        
        # Act & Assert
        # Should reject new order when approaching loss limit
        with pytest.raises(ProjectXRiskError) as exc_info:
            order_manager.place_market_order("MGC", side=0, size=5)
        
        assert "daily loss limit" in str(exc_info.value).lower()
    
    def test_order_validation_against_limits(self):
        """Test order validation against multiple risk limits"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        mock_client.get_account_balance.return_value = 10000.0
        
        mock_instrument = Instrument(
            id="CON.F.US.MGC.M25",
            tickValue=10.0,
            tickSize=0.1,
            marginRequirement=500.0  # $500 per contract
        )
        mock_client.get_instrument.return_value = mock_instrument
        
        order_manager = OrderManager(mock_client)
        order_manager.initialize()
        
        # Set risk limits
        order_manager.set_max_margin_usage(0.5)  # Max 50% margin usage
        
        # Act & Assert
        # Order requiring $10,000 margin (20 contracts * $500) should be rejected
        with pytest.raises(ProjectXRiskError) as exc_info:
            order_manager.place_market_order("MGC", side=0, size=20)
        
        assert "margin" in str(exc_info.value).lower()
    
    def test_risk_metric_calculations(self):
        """Test various risk metric calculations"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        mock_client.get_account_balance.return_value = 50000.0
        
        mock_positions = [
            Position(
                contract_id="CON.F.US.MGC.M25",
                instrument="MGC",
                side=0,
                quantity=5,
                average_price=2045.0,
                margin_requirement=2500.0,
                unrealized_pnl=-200.0
            ),
            Position(
                contract_id="CON.F.US.MES.H25",
                instrument="MES",
                side=1,
                quantity=2,
                average_price=5400.0,
                margin_requirement=2400.0,
                unrealized_pnl=150.0
            )
        ]
        mock_client.search_open_positions.return_value = mock_positions
        
        position_manager = PositionManager(mock_client)
        position_manager.initialize()
        
        # Act
        risk_metrics = position_manager.calculate_risk_metrics()
        
        # Assert
        assert risk_metrics["account_balance"] == 50000.0
        assert risk_metrics["total_margin_used"] == 4900.0  # 2500 + 2400
        assert risk_metrics["margin_usage_percentage"] == 9.8  # 4900/50000 * 100
        assert risk_metrics["total_unrealized_pnl"] == -50.0  # -200 + 150
        assert risk_metrics["free_margin"] == 45100.0  # 50000 - 4900
        assert risk_metrics["margin_level"] > 1000  # (50000 / 4900) * 100
    
    def test_margin_requirements(self):
        """Test margin requirement calculations"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        mock_instrument = Instrument(
            id="CON.F.US.MGC.M25",
            tickValue=10.0,
            tickSize=0.1,
            marginRequirement=500.0,
            maintenanceMargin=400.0
        )
        mock_client.get_instrument.return_value = mock_instrument
        mock_client.get_account_balance.return_value = 5000.0
        
        order_manager = OrderManager(mock_client)
        order_manager.initialize()
        
        # Act & Assert
        # Should calculate required margin before placing order
        required_margin = order_manager.calculate_required_margin("MGC", size=10)
        assert required_margin == 5000.0  # 10 * 500
        
        # Should reject order if insufficient margin
        with pytest.raises(ProjectXRiskError) as exc_info:
            order_manager.place_market_order("MGC", side=0, size=11)  # Needs $5500
        
        assert "insufficient margin" in str(exc_info.value).lower()
    
    def test_account_balance_checks(self):
        """Test account balance validation"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        mock_client.get_account_balance.return_value = 1000.0  # Low balance
        
        order_manager = OrderManager(mock_client)
        order_manager.initialize()
        
        # Set minimum balance requirement
        order_manager.set_minimum_balance(2000.0)
        
        # Act & Assert
        with pytest.raises(ProjectXRiskError) as exc_info:
            order_manager.place_market_order("MGC", side=0, size=1)
        
        assert "minimum balance" in str(exc_info.value).lower()
    
    def test_simultaneous_order_limit(self):
        """Test limit on number of simultaneous orders"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        
        # Mock many open orders
        mock_orders = [
            Order(
                id=f"order_{i}",
                contract_id="CON.F.US.MGC.M25",
                side=0,
                size=1,
                status="Open"
            ) for i in range(10)
        ]
        mock_client.search_open_orders.return_value = mock_orders
        
        order_manager = OrderManager(mock_client)
        order_manager.initialize()
        
        # Set max open orders
        order_manager.set_max_open_orders(10)
        
        # Act & Assert
        with pytest.raises(ProjectXRiskError) as exc_info:
            order_manager.place_limit_order("MGC", side=0, size=1, price=2045.0)
        
        assert "maximum open orders" in str(exc_info.value).lower()
    
    def test_leverage_limits(self):
        """Test leverage limit enforcement"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        mock_client.get_account_balance.return_value = 10000.0
        
        mock_instrument = Instrument(
            id="CON.F.US.MGC.M25",
            tickValue=10.0,
            tickSize=0.1,
            contractSize=100  # 100 oz per contract
        )
        mock_client.get_instrument.return_value = mock_instrument
        mock_client.get_current_price.return_value = 2045.0
        
        position_manager = PositionManager(mock_client)
        position_manager.initialize()
        
        # Set max leverage
        position_manager.set_max_leverage(5.0)
        
        # Act
        # Calculate max position size with 5x leverage
        # Account: $10,000, Max exposure: $50,000
        # Contract value: 100 * $2045 = $204,500
        # Max contracts: $50,000 / $204,500 = 0.24 contracts
        
        max_size = position_manager.calculate_max_position_size("MGC")
        
        # Assert
        assert max_size < 1  # Less than 1 contract with 5x leverage
    
    def test_risk_per_trade_limit(self):
        """Test risk per trade percentage limit"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        mock_client.get_account_balance.return_value = 10000.0
        
        mock_instrument = Instrument(
            id="CON.F.US.MGC.M25",
            tickValue=10.0,
            tickSize=0.1
        )
        mock_client.get_instrument.return_value = mock_instrument
        
        order_manager = OrderManager(mock_client)
        order_manager.initialize()
        
        # Set max risk per trade to 2% of account
        order_manager.set_max_risk_per_trade(0.02)
        
        # Act & Assert
        # With $10,000 account, max risk is $200
        # Stop loss of $5 (50 ticks) = $500 risk per contract
        # Should reject order with size > 0.4 contracts
        
        with pytest.raises(ProjectXRiskError) as exc_info:
            order_manager.place_bracket_order(
                "MGC", 
                side=0, 
                size=1,  # 1 contract = $500 risk > $200 limit
                entry_price=2045.0,
                stop_price=2040.0,  # $5 stop
                target_price=2055.0
            )
        
        assert "risk per trade" in str(exc_info.value).lower()
    
    def test_correlation_risk_check(self):
        """Test correlation risk between positions"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        
        # Mock correlated positions (gold and silver)
        mock_positions = [
            Position(
                contract_id="CON.F.US.MGC.M25",
                instrument="MGC",  # Micro Gold
                side=0,
                quantity=10,
                margin_requirement=5000.0
            ),
            Position(
                contract_id="CON.F.US.SIL.M25",
                instrument="SIL",  # Silver
                side=0,
                quantity=5,
                margin_requirement=3000.0
            )
        ]
        mock_client.search_open_positions.return_value = mock_positions
        
        position_manager = PositionManager(mock_client)
        position_manager.initialize()
        
        # Set correlation limits
        position_manager.set_correlation_groups({
            "precious_metals": ["MGC", "SIL", "GC"],
            "equity_indices": ["MES", "MNQ", "ES", "NQ"]
        })
        position_manager.set_max_correlated_exposure(0.3)  # Max 30% in correlated assets
        
        # Act
        risk_check = position_manager.check_correlation_risk()
        
        # Assert
        assert risk_check["precious_metals"]["exposure_percentage"] > 0
        assert risk_check["precious_metals"]["instruments"] == ["MGC", "SIL"]
        assert risk_check["warnings"] is not None  # Should have correlation warning