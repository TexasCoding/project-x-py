"""
Test suite for Position Manager tracking functionality
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import polars as pl
from project_x_py import ProjectX
from project_x_py.position_manager import PositionManager
from project_x_py.models import Position, Fill
from project_x_py.exceptions import ProjectXError


class TestPositionTracking:
    """Test cases for position tracking functionality"""
    
    def test_get_all_positions_empty(self):
        """Test getting all positions when none exist"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        mock_client.search_open_positions.return_value = []
        position_manager = PositionManager(mock_client)
        position_manager.initialize()
        
        # Act
        positions = position_manager.get_all_positions()
        
        # Assert
        assert positions == []
        mock_client.search_open_positions.assert_called_once()
    
    def test_get_all_positions_with_data(self):
        """Test getting all positions with existing positions"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        mock_positions = [
            Position(
                contract_id="CON.F.US.MGC.M25",
                instrument="MGC",
                side=0,  # Long
                quantity=5,
                average_price=2045.5,
                realized_pnl=0.0,
                unrealized_pnl=50.0
            ),
            Position(
                contract_id="CON.F.US.MES.H25",
                instrument="MES",
                side=1,  # Short
                quantity=2,
                average_price=5400.0,
                realized_pnl=-25.0,
                unrealized_pnl=10.0
            )
        ]
        mock_client.search_open_positions.return_value = mock_positions
        position_manager = PositionManager(mock_client)
        position_manager.initialize()
        
        # Act
        positions = position_manager.get_all_positions()
        
        # Assert
        assert len(positions) == 2
        assert positions[0].instrument == "MGC"
        assert positions[1].instrument == "MES"
    
    def test_get_position_exists(self):
        """Test getting a specific position that exists"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        mock_position = Position(
            contract_id="CON.F.US.MGC.M25",
            instrument="MGC",
            side=0,
            quantity=3,
            average_price=2045.0
        )
        mock_client.search_open_positions.return_value = [mock_position]
        position_manager = PositionManager(mock_client)
        position_manager.initialize()
        
        # Act
        position = position_manager.get_position("MGC")
        
        # Assert
        assert position is not None
        assert position.instrument == "MGC"
        assert position.quantity == 3
    
    def test_get_position_not_exists(self):
        """Test getting a position that doesn't exist"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        mock_client.search_open_positions.return_value = []
        position_manager = PositionManager(mock_client)
        position_manager.initialize()
        
        # Act
        position = position_manager.get_position("MGC")
        
        # Assert
        assert position is None
    
    def test_calculate_position_pnl(self):
        """Test P&L calculation for a position"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        mock_position = Position(
            contract_id="CON.F.US.MGC.M25",
            instrument="MGC",
            side=0,  # Long
            quantity=2,
            average_price=2045.0,
            realized_pnl=100.0,
            unrealized_pnl=50.0
        )
        mock_client.search_open_positions.return_value = [mock_position]
        position_manager = PositionManager(mock_client)
        position_manager.initialize()
        
        # Act
        pnl = position_manager.calculate_position_pnl("MGC")
        
        # Assert
        assert pnl is not None
        assert pnl["unrealized_pnl"] == 50.0
        assert pnl["realized_pnl"] == 100.0
        assert pnl["total_pnl"] == 150.0
    
    def test_calculate_position_pnl_no_position(self):
        """Test P&L calculation when position doesn't exist"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        mock_client.search_open_positions.return_value = []
        position_manager = PositionManager(mock_client)
        position_manager.initialize()
        
        # Act
        pnl = position_manager.calculate_position_pnl("MGC")
        
        # Assert
        assert pnl is not None
        assert pnl["unrealized_pnl"] == 0.0
        assert pnl["realized_pnl"] == 0.0
        assert pnl["total_pnl"] == 0.0
    
    def test_update_position(self):
        """Test updating a position"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        position_manager = PositionManager(mock_client)
        position_manager.initialize()
        
        new_position = Position(
            contract_id="CON.F.US.MGC.M25",
            instrument="MGC",
            side=0,
            quantity=5,
            average_price=2046.0
        )
        
        # Act
        position_manager.update_position(new_position)
        
        # Assert
        assert "MGC" in position_manager._positions
        assert position_manager._positions["MGC"].quantity == 5
    
    def test_close_position(self):
        """Test closing a position"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        position_manager = PositionManager(mock_client)
        position_manager.initialize()
        
        # Add a position
        position = Position(
            contract_id="CON.F.US.MGC.M25",
            instrument="MGC",
            side=0,
            quantity=3,
            average_price=2045.0
        )
        position_manager._positions["MGC"] = position
        
        # Act
        position_manager.close_position("MGC")
        
        # Assert
        assert "MGC" not in position_manager._positions
    
    def test_position_from_fills(self):
        """Test position creation from fills"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        position_manager = PositionManager(mock_client)
        position_manager.initialize()
        
        # Simulate multiple fills
        fills = [
            Fill(
                instrument="MGC",
                side=0,  # Buy
                quantity=2,
                price=2045.0,
                timestamp=datetime.now()
            ),
            Fill(
                instrument="MGC",
                side=0,  # Buy
                quantity=3,
                price=2046.0,
                timestamp=datetime.now()
            ),
            Fill(
                instrument="MGC",
                side=1,  # Sell
                quantity=1,
                price=2047.0,
                timestamp=datetime.now()
            )
        ]
        
        # Act
        for fill in fills:
            position_manager.process_fill(fill)
        
        # Assert
        position = position_manager._positions.get("MGC")
        assert position is not None
        assert position.quantity == 4  # 2 + 3 - 1
        # Average price should be weighted: ((2*2045) + (3*2046)) / 5 for the buys
        expected_avg = ((2 * 2045.0) + (3 * 2046.0)) / 5
        assert abs(position.average_price - expected_avg) < 0.01
    
    def test_position_update_callbacks(self):
        """Test that position update callbacks are triggered"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        position_manager = PositionManager(mock_client)
        position_manager.initialize()
        
        callback_called = False
        update_data = None
        
        def test_callback(data):
            nonlocal callback_called, update_data
            callback_called = True
            update_data = data
        
        position_manager.add_callback('position_update', test_callback)
        
        # Act
        new_position = Position(
            contract_id="CON.F.US.MGC.M25",
            instrument="MGC",
            side=0,
            quantity=2,
            average_price=2045.0
        )
        position_manager.update_position(new_position)
        
        # Assert
        assert callback_called
        assert update_data == new_position