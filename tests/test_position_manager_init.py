"""
Test suite for PositionManager initialization
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from project_x_py import ProjectX
from project_x_py.position_manager import PositionManager
from project_x_py.realtime import ProjectXRealtimeClient
from project_x_py.exceptions import ProjectXError


class TestPositionManagerInit:
    """Test cases for PositionManager initialization"""
    
    def test_basic_initialization(self):
        """Test basic position manager initialization"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        
        # Act
        position_manager = PositionManager(mock_client)
        
        # Assert
        assert position_manager.project_x == mock_client
        assert position_manager._positions == {}
        assert position_manager._realtime_client is None
        assert position_manager._realtime_enabled is False
        assert position_manager._callbacks == {
            'position_update': [],
            'position_closed': [],
            'pnl_update': []
        }
    
    def test_initialize_without_realtime(self):
        """Test initialization without real-time client"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        position_manager = PositionManager(mock_client)
        
        # Act
        result = position_manager.initialize()
        
        # Assert
        assert result is True
        assert position_manager._realtime_enabled is False
    
    def test_initialize_with_realtime_client(self):
        """Test initialization with real-time client"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        mock_realtime = Mock(spec=ProjectXRealtimeClient)
        position_manager = PositionManager(mock_client)
        
        # Act
        result = position_manager.initialize(realtime_client=mock_realtime)
        
        # Assert
        assert result is True
        assert position_manager._realtime_client == mock_realtime
        assert position_manager._realtime_enabled is True
        # Verify callbacks were registered
        mock_realtime.add_callback.assert_called()
    
    def test_reinitialize_capability(self):
        """Test that position manager can be reinitialized"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        position_manager = PositionManager(mock_client)
        
        # Act & Assert
        # First initialization
        assert position_manager.initialize() is True
        
        # Second initialization should also work
        assert position_manager.initialize() is True
    
    def test_initialization_clears_existing_positions(self):
        """Test that initialization clears existing positions"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        position_manager = PositionManager(mock_client)
        position_manager._positions = {"MGC": Mock()}  # Add existing position
        
        # Act
        position_manager.initialize()
        
        # Assert
        assert position_manager._positions == {}
    
    def test_position_manager_attributes(self):
        """Test position manager has expected attributes"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        
        # Act
        position_manager = PositionManager(mock_client)
        
        # Assert
        assert hasattr(position_manager, 'get_all_positions')
        assert hasattr(position_manager, 'get_position')
        assert hasattr(position_manager, 'calculate_position_pnl')
        assert hasattr(position_manager, 'get_portfolio_pnl')
        assert hasattr(position_manager, 'get_risk_metrics')
        assert hasattr(position_manager, 'calculate_position_size')
        assert hasattr(position_manager, 'update_position')
        assert hasattr(position_manager, 'close_position')
    
    def test_position_update_callback_registration(self):
        """Test that position update callbacks are registered with realtime client"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        mock_realtime = Mock(spec=ProjectXRealtimeClient)
        position_manager = PositionManager(mock_client)
        
        # Act
        position_manager.initialize(realtime_client=mock_realtime)
        
        # Assert
        # Check that position update callback was registered
        calls = mock_realtime.add_callback.call_args_list
        callback_types = [call[0][0] for call in calls]
        assert 'position_update' in callback_types
    
    def test_initialization_error_handling(self):
        """Test error handling during initialization"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        mock_realtime = Mock(spec=ProjectXRealtimeClient)
        mock_realtime.add_callback.side_effect = Exception("Connection error")
        position_manager = PositionManager(mock_client)
        
        # Act & Assert
        # Should handle error gracefully
        result = position_manager.initialize(realtime_client=mock_realtime)
        assert result is False  # Or handle error appropriately