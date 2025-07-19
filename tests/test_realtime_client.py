"""
Test file: tests/test_realtime_client.py
Phase 1: Critical Core Testing - Real-time Client Connection
Priority: Critical
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from project_x_py.realtime import ProjectXRealtimeClient, SIGNALR_AVAILABLE
from project_x_py.exceptions import ProjectXConnectionError


# Skip tests if SignalR is not available
pytestmark = pytest.mark.skipif(
    not SIGNALR_AVAILABLE,
    reason="SignalR not available - install signalrcore package"
)


class TestRealtimeClientConnection:
    """Test suite for Real-time Client connection functionality."""

    @pytest.fixture
    def mock_connection(self):
        """Create a mock SignalR connection."""
        with patch('signalrcore.HubConnectionBuilder') as mock_builder:
            mock_connection = Mock()
            mock_connection.start = Mock()
            mock_connection.stop = Mock()
            mock_connection.on = Mock()
            mock_connection.send = Mock()
            
            # Configure the builder to return our mock connection
            mock_builder_instance = Mock()
            mock_builder_instance.with_url.return_value = mock_builder_instance
            mock_builder_instance.configure_logging.return_value = mock_builder_instance
            mock_builder_instance.with_automatic_reconnect.return_value = mock_builder_instance
            mock_builder_instance.build.return_value = mock_connection
            
            mock_builder.return_value = mock_builder_instance
            
            yield mock_connection, mock_builder

    def test_signalr_dependency_check(self):
        """Test that SignalR is available."""
        assert SIGNALR_AVAILABLE is True

    def test_basic_connection(self, mock_connection):
        """Test basic connection establishment."""
        mock_conn, mock_builder = mock_connection
        
        # Create real-time client
        client = ProjectXRealtimeClient(jwt_token="test_token", account_id="1001")
        
        # Test connection
        success = client.connect()
        
        assert success is True
        assert client.connected is True
        mock_conn.start.assert_called_once()

    def test_connection_failure(self, mock_connection):
        """Test handling of connection failures."""
        mock_conn, mock_builder = mock_connection
        
        # Make connection fail
        mock_conn.start.side_effect = Exception("Connection failed")
        
        # Create real-time client
        client = ProjectXRealtimeClient(jwt_token="test_token", account_id="1001")
        
        # Test connection
        success = client.connect()
        
        assert success is False
        assert client.connected is False

    def test_disconnection(self, mock_connection):
        """Test disconnection functionality."""
        mock_conn, mock_builder = mock_connection
        
        # Create and connect client
        client = ProjectXRealtimeClient(jwt_token="test_token", account_id="1001")
        client.connect()
        
        assert client.connected is True
        
        # Test disconnection
        client.disconnect()
        
        assert client.connected is False
        mock_conn.stop.assert_called_once()

    def test_user_data_subscriptions(self, mock_connection):
        """Test subscription to user updates."""
        mock_conn, mock_builder = mock_connection
        
        # Create and connect client
        client = ProjectXRealtimeClient(jwt_token="test_token", account_id="1001")
        client.connect()
        
        # Subscribe to user updates
        success = client.subscribe_user_updates()
        
        assert success is True
        # Verify subscription message was sent
        mock_conn.send.assert_called()
        call_args = mock_conn.send.call_args
        assert "SubscribeUser" in str(call_args)

    def test_market_data_subscriptions(self, mock_connection):
        """Test subscription to market data."""
        mock_conn, mock_builder = mock_connection
        
        # Create and connect client
        client = ProjectXRealtimeClient(jwt_token="test_token", account_id="1001")
        client.connect()
        
        # Subscribe to market data
        contracts = ["CON.F.US.MGC.M25", "CON.F.US.MNQ.M25"]
        success = client.subscribe_market_data(contracts)
        
        assert success is True
        # Verify subscription message was sent
        mock_conn.send.assert_called()

    def test_callback_registration(self, mock_connection):
        """Test callback registration functionality."""
        mock_conn, mock_builder = mock_connection
        
        # Create client
        client = ProjectXRealtimeClient(jwt_token="test_token", account_id="1001")
        
        # Test callback registration
        callback_called = False
        test_data = None
        
        def test_callback(data):
            nonlocal callback_called, test_data
            callback_called = True
            test_data = data
        
        client.add_callback("quote_update", test_callback)
        
        # Verify callback is registered
        assert "quote_update" in client.callbacks
        assert test_callback in client.callbacks["quote_update"]
        
        # Test callback execution
        client._trigger_callbacks("quote_update", {"test": "data"})
        
        assert callback_called is True
        assert test_data == {"test": "data"}

    def test_connection_event_handlers(self, mock_connection):
        """Test that connection event handlers are set up."""
        mock_conn, mock_builder = mock_connection
        
        # Create client
        client = ProjectXRealtimeClient(jwt_token="test_token", account_id="1001")
        
        # Verify event handlers are registered
        mock_conn.on.assert_any_call("QuoteUpdate", client._on_quote_update)
        mock_conn.on.assert_any_call("OrderUpdate", client._on_order_update)
        mock_conn.on.assert_any_call("PositionUpdate", client._on_position_update)
        mock_conn.on.assert_any_call("AccountUpdate", client._on_account_update)

    def test_reconnection_capability(self, mock_connection):
        """Test that automatic reconnection is configured."""
        mock_conn, mock_builder = mock_connection
        
        # Create client
        client = ProjectXRealtimeClient(jwt_token="test_token", account_id="1001")
        
        # Verify automatic reconnection was configured
        mock_builder[1].return_value.with_automatic_reconnect.assert_called()

    def test_multiple_callback_registration(self, mock_connection):
        """Test registering multiple callbacks for the same event."""
        mock_conn, mock_builder = mock_connection
        
        # Create client
        client = ProjectXRealtimeClient(jwt_token="test_token", account_id="1001")
        
        # Register multiple callbacks
        callback1_called = False
        callback2_called = False
        
        def callback1(data):
            nonlocal callback1_called
            callback1_called = True
        
        def callback2(data):
            nonlocal callback2_called
            callback2_called = True
        
        client.add_callback("test_event", callback1)
        client.add_callback("test_event", callback2)
        
        # Trigger callbacks
        client._trigger_callbacks("test_event", {})
        
        assert callback1_called is True
        assert callback2_called is True

    def test_remove_callback(self, mock_connection):
        """Test removing callbacks."""
        mock_conn, mock_builder = mock_connection
        
        # Create client
        client = ProjectXRealtimeClient(jwt_token="test_token", account_id="1001")
        
        # Add and remove callback
        def test_callback(data):
            pass
        
        client.add_callback("test_event", test_callback)
        assert test_callback in client.callbacks["test_event"]
        
        client.remove_callback("test_event", test_callback)
        assert test_callback not in client.callbacks["test_event"]

    def test_connection_state_tracking(self, mock_connection):
        """Test that connection state is properly tracked."""
        mock_conn, mock_builder = mock_connection
        
        # Create client
        client = ProjectXRealtimeClient(jwt_token="test_token", account_id="1001")
        
        # Initially not connected
        assert client.connected is False
        
        # Connect
        client.connect()
        assert client.connected is True
        
        # Disconnect
        client.disconnect()
        assert client.connected is False

    def test_hub_url_configuration(self, mock_connection):
        """Test that hub URLs are properly configured."""
        mock_conn, mock_builder = mock_connection
        
        # Create client with custom hub URL
        custom_url = "https://custom.hub.url"
        client = ProjectXRealtimeClient(
            jwt_token="test_token", 
            account_id="1001",
            user_hub_url=custom_url
        )
        
        # Verify custom URL was used
        mock_builder[1].return_value.with_url.assert_called()
        call_args = mock_builder[1].return_value.with_url.call_args
        assert custom_url in str(call_args)


def run_realtime_client_tests():
    """Helper function to run Real-time Client connection tests."""
    print("Running Phase 1 Real-time Client Connection Tests...")
    pytest.main([__file__, "-v", "-s"])


if __name__ == "__main__":
    run_realtime_client_tests()