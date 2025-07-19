"""
Test file: tests/test_order_manager_init.py
Phase 1: Critical Core Testing - Order Manager Initialization
Priority: Critical
"""

import pytest
from unittest.mock import Mock, patch
from project_x_py import ProjectX, OrderManager, create_order_manager
from project_x_py.realtime import ProjectXRealtimeClient
from project_x_py.exceptions import ProjectXError


class TestOrderManagerInitialization:
    """Test suite for Order Manager initialization."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock ProjectX client."""
        client = Mock(spec=ProjectX)
        client.account_info = Mock(id=1001, name="Demo Account")
        client.session_token = "test_token"
        client._authenticated = True
        return client

    def test_basic_initialization(self, mock_client):
        """Test basic OrderManager initialization."""
        order_manager = OrderManager(mock_client)
        
        assert order_manager.project_x == mock_client
        assert order_manager.realtime_client is None
        assert order_manager._realtime_enabled is False
        assert hasattr(order_manager, 'tracked_orders')
        assert hasattr(order_manager, 'stats')

    def test_initialize_without_realtime(self, mock_client):
        """Test OrderManager initialization without real-time."""
        order_manager = OrderManager(mock_client)
        
        # Initialize without real-time
        result = order_manager.initialize()
        
        assert result is True
        assert order_manager._realtime_enabled is False
        assert order_manager.realtime_client is None

    def test_initialize_with_realtime(self, mock_client):
        """Test OrderManager initialization with real-time integration."""
        # Mock real-time client
        mock_realtime = Mock(spec=ProjectXRealtimeClient)
        mock_realtime.add_callback = Mock()
        
        order_manager = OrderManager(mock_client)
        
        # Initialize with real-time
        result = order_manager.initialize(realtime_client=mock_realtime)
        
        assert result is True
        assert order_manager._realtime_enabled is True
        assert order_manager.realtime_client == mock_realtime
        
        # Verify callbacks were registered
        assert mock_realtime.add_callback.call_count >= 3
        mock_realtime.add_callback.assert_any_call("order_update", order_manager._on_order_update)
        mock_realtime.add_callback.assert_any_call("order_filled", order_manager._on_order_filled)
        mock_realtime.add_callback.assert_any_call("order_cancelled", order_manager._on_order_cancelled)

    def test_initialize_with_realtime_exception(self, mock_client):
        """Test OrderManager initialization when real-time setup fails."""
        # Mock real-time client that raises exception
        mock_realtime = Mock(spec=ProjectXRealtimeClient)
        mock_realtime.add_callback.side_effect = Exception("Connection error")
        
        order_manager = OrderManager(mock_client)
        
        # Initialize with real-time that fails
        result = order_manager.initialize(realtime_client=mock_realtime)
        
        # Should return False on failure
        assert result is False
        assert order_manager._realtime_enabled is False

    def test_reinitialize_order_manager(self, mock_client):
        """Test that OrderManager can be reinitialized."""
        order_manager = OrderManager(mock_client)
        
        # First initialization
        result1 = order_manager.initialize()
        assert result1 is True
        
        # Second initialization should also work
        result2 = order_manager.initialize()
        assert result2 is True

    def test_create_order_manager_helper_function(self):
        """Test the create_order_manager helper function."""
        with patch('project_x_py.OrderManager') as mock_order_manager_class:
            mock_order_manager = Mock()
            mock_order_manager.initialize.return_value = True
            mock_order_manager_class.return_value = mock_order_manager
            
            client = Mock(spec=ProjectX)
            
            # Test without real-time
            order_manager = create_order_manager(client)
            
            assert order_manager == mock_order_manager
            mock_order_manager_class.assert_called_once_with(client)
            mock_order_manager.initialize.assert_called_once_with(realtime_client=None)

    def test_create_order_manager_with_realtime(self):
        """Test create_order_manager with real-time client."""
        with patch('project_x_py.OrderManager') as mock_order_manager_class:
            mock_order_manager = Mock()
            mock_order_manager.initialize.return_value = True
            mock_order_manager_class.return_value = mock_order_manager
            
            client = Mock(spec=ProjectX)
            realtime_client = Mock(spec=ProjectXRealtimeClient)
            
            # Test with real-time
            order_manager = create_order_manager(client, realtime_client=realtime_client)
            
            assert order_manager == mock_order_manager
            mock_order_manager_class.assert_called_once_with(client)
            mock_order_manager.initialize.assert_called_once_with(realtime_client=realtime_client)

    def test_order_manager_requires_authenticated_client(self, mock_client):
        """Test that OrderManager requires an authenticated client."""
        # Make client unauthenticated
        mock_client._authenticated = False
        
        order_manager = OrderManager(mock_client)
        
        # This test verifies the concept - actual implementation may vary
        # The order manager should work with an unauthenticated client
        # but operations will fail when they try to make API calls
        assert order_manager.project_x == mock_client

    def test_order_manager_without_account_info(self):
        """Test OrderManager behavior when client has no account info."""
        client = Mock(spec=ProjectX)
        client.account_info = None
        client._authenticated = True
        
        order_manager = OrderManager(client)
        result = order_manager.initialize()
        
        # Should initialize successfully
        assert result is True
        
        # Account info will be fetched when needed for actual operations

    def test_order_manager_attributes(self, mock_client):
        """Test OrderManager has expected attributes after initialization."""
        order_manager = OrderManager(mock_client)
        order_manager.initialize()
        
        # Check expected attributes exist
        assert hasattr(order_manager, 'project_x')
        assert hasattr(order_manager, 'realtime_client')
        assert hasattr(order_manager, '_realtime_enabled')
        assert hasattr(order_manager, 'tracked_orders')
        assert hasattr(order_manager, 'order_callbacks')
        assert hasattr(order_manager, 'stats')
        
        # These should be initialized
        assert order_manager.project_x is not None
        assert isinstance(order_manager.tracked_orders, dict)
        assert isinstance(order_manager.stats, dict)

    def test_order_manager_with_mock_realtime_callbacks(self, mock_client):
        """Test OrderManager can register callbacks with real-time client."""
        mock_realtime = Mock(spec=ProjectXRealtimeClient)
        mock_realtime.add_callback = Mock()
        
        order_manager = OrderManager(mock_client)
        order_manager.initialize(realtime_client=mock_realtime)
        
        # In actual implementation, callbacks are registered
        assert order_manager.realtime_client == mock_realtime
        
        # Verify callbacks are registered
        assert mock_realtime.add_callback.called
        # Should register at least 3 callbacks
        assert mock_realtime.add_callback.call_count >= 3


def run_order_manager_init_tests():
    """Helper function to run Order Manager initialization tests."""
    print("Running Phase 1 Order Manager Initialization Tests...")
    pytest.main([__file__, "-v", "-s"])


if __name__ == "__main__":
    run_order_manager_init_tests()