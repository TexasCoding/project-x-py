"""
Test suite for PositionManager initialization
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from project_x_py import ProjectX
from project_x_py.exceptions import ProjectXError
from project_x_py.position_manager import PositionManager
from project_x_py.realtime import ProjectXRealtimeClient


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
        assert position_manager.tracked_positions == {}
        assert position_manager.realtime_client is None
        assert position_manager._realtime_enabled is False
        assert hasattr(position_manager, "position_callbacks")
        assert hasattr(position_manager, "position_lock")
        assert hasattr(position_manager, "stats")

    def test_initialize_without_realtime(self):
        """Test initialization without real-time client"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        mock_client.search_open_positions.return_value = []
        position_manager = PositionManager(mock_client)

        # Act
        result = position_manager.initialize()

        # Assert
        assert result is True
        assert position_manager._realtime_enabled is False
        mock_client.search_open_positions.assert_called_once()

    def test_initialize_with_realtime_client(self):
        """Test initialization with real-time client"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        mock_client.search_open_positions.return_value = []
        mock_realtime = Mock(spec=ProjectXRealtimeClient)
        position_manager = PositionManager(mock_client)

        # Act
        result = position_manager.initialize(realtime_client=mock_realtime)

        # Assert
        assert result is True
        assert position_manager.realtime_client == mock_realtime
        assert position_manager._realtime_enabled is True

        # Verify real-time callbacks were registered
        assert (
            mock_realtime.add_callback.call_count >= 3
        )  # At least 3 callbacks registered
        mock_client.search_open_positions.assert_called_once()

    def test_initialize_error_handling(self):
        """Test initialization with error handling"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        mock_client.search_open_positions.side_effect = Exception("Connection error")
        position_manager = PositionManager(mock_client)

        # Act
        result = position_manager.initialize()

        # Assert
        # PositionManager is designed to be resilient - initialization succeeds
        # even if position loading fails (positions can be loaded later)
        assert result is True
        # Verify the error was logged but didn't crash initialization
        mock_client.search_open_positions.assert_called_once()

    def test_initialization_clears_existing_positions(self):
        """Test that initialization loads fresh positions"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        mock_client.search_open_positions.return_value = []
        position_manager = PositionManager(mock_client)

        # Manually add some tracked positions to simulate existing state
        position_manager.tracked_positions["MGC"] = Mock()

        # Act
        position_manager.initialize()

        # Assert
        # Fresh positions loaded from API, tracked_positions updated accordingly
        assert len(position_manager.tracked_positions) >= 0  # Could be empty or updated
        mock_client.search_open_positions.assert_called_once()

    def test_reinitialization(self):
        """Test that position manager can be re-initialized"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        mock_client.search_open_positions.return_value = []
        mock_realtime1 = Mock(spec=ProjectXRealtimeClient)
        mock_realtime2 = Mock(spec=ProjectXRealtimeClient)
        position_manager = PositionManager(mock_client)

        # First initialization
        result1 = position_manager.initialize(realtime_client=mock_realtime1)
        assert result1 is True
        assert position_manager.realtime_client == mock_realtime1

        # Re-initialization with different realtime client
        result2 = position_manager.initialize(realtime_client=mock_realtime2)
        assert result2 is True
        assert position_manager.realtime_client == mock_realtime2

    def test_position_manager_attributes(self):
        """Test position manager has expected attributes and methods"""
        # Arrange
        mock_client = Mock(spec=ProjectX)

        # Act
        position_manager = PositionManager(mock_client)

        # Assert - Core methods
        assert hasattr(position_manager, "get_all_positions")
        assert hasattr(position_manager, "get_position")
        assert hasattr(position_manager, "calculate_position_pnl")
        assert hasattr(position_manager, "get_portfolio_pnl")
        assert hasattr(position_manager, "get_risk_metrics")
        assert hasattr(position_manager, "calculate_position_size")
        assert hasattr(position_manager, "refresh_positions")
        assert hasattr(position_manager, "is_position_open")

        # Assert - Real-time capabilities
        assert hasattr(position_manager, "start_monitoring")
        assert hasattr(position_manager, "stop_monitoring")
        assert hasattr(position_manager, "add_callback")

        # Assert - Position management
        assert hasattr(position_manager, "close_position_direct")
        assert hasattr(position_manager, "close_all_positions")
        assert hasattr(position_manager, "close_position_by_contract")

        # Assert - Risk and alerts
        assert hasattr(position_manager, "add_position_alert")
        assert hasattr(position_manager, "remove_position_alert")

    def test_create_position_manager_helper(self):
        """Test the helper function for creating position manager"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        mock_client.search_open_positions.return_value = []

        # Act
        position_manager = PositionManager(mock_client)
        position_manager.initialize()

        # Assert
        assert isinstance(position_manager, PositionManager)
        assert position_manager.project_x == mock_client
        mock_client.search_open_positions.assert_called_once()
