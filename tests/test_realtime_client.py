"""
Test file: tests/test_realtime_client.py
Phase 1: Critical Core Testing - Real-time Client Connection
Priority: Critical
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from project_x_py.exceptions import ProjectXConnectionError
from project_x_py.realtime import SIGNALR_AVAILABLE, ProjectXRealtimeClient

# Skip tests if SignalR is not available
pytestmark = pytest.mark.skipif(
    not SIGNALR_AVAILABLE, reason="SignalR not available - install signalrcore package"
)


class TestRealtimeClientConnection:
    """Test suite for Real-time Client connection functionality."""

    @pytest.fixture
    def mock_connection(self):
        """Create a mock SignalR connection."""
        with patch("project_x_py.realtime.HubConnectionBuilder") as mock_builder:
            # Create separate mock connections for user and market hubs
            mock_user_connection = Mock()
            mock_market_connection = Mock()

            # Set up connection method mocks
            mock_user_connection.start = Mock()
            mock_user_connection.stop = Mock()
            mock_user_connection.on = Mock()
            mock_user_connection.on_open = Mock()
            mock_user_connection.on_close = Mock()
            mock_user_connection.on_error = Mock()
            mock_user_connection.send = Mock()

            mock_market_connection.start = Mock()
            mock_market_connection.stop = Mock()
            mock_market_connection.on = Mock()
            mock_market_connection.on_open = Mock()
            mock_market_connection.on_close = Mock()
            mock_market_connection.on_error = Mock()
            mock_market_connection.send = Mock()

            # Store callbacks that get registered
            user_open_callbacks = []
            market_open_callbacks = []

            # Mock the on_open method to store callbacks
            def store_user_callback(callback):
                user_open_callbacks.append(callback)

            def store_market_callback(callback):
                market_open_callbacks.append(callback)

            mock_user_connection.on_open.side_effect = store_user_callback
            mock_market_connection.on_open.side_effect = store_market_callback

            # Mock start to trigger the callbacks
            def trigger_user_connection():
                for callback in user_open_callbacks:
                    callback()

            def trigger_market_connection():
                for callback in market_open_callbacks:
                    callback()

            mock_user_connection.start.side_effect = trigger_user_connection
            mock_market_connection.start.side_effect = trigger_market_connection

            # Configure the builder to return our mock connections alternately
            mock_builder_instance = Mock()
            mock_builder_instance.with_url.return_value = mock_builder_instance
            mock_builder_instance.configure_logging.return_value = mock_builder_instance
            mock_builder_instance.with_automatic_reconnect.return_value = (
                mock_builder_instance
            )

            # Return different connections for user and market hubs
            build_call_count = 0

            def build_side_effect():
                nonlocal build_call_count
                build_call_count += 1
                if build_call_count == 1:
                    return mock_user_connection
                else:
                    return mock_market_connection

            mock_builder_instance.build.side_effect = build_side_effect
            mock_builder.return_value = mock_builder_instance

            yield (mock_user_connection, mock_market_connection), mock_builder

    def test_signalr_dependency_check(self):
        """Test that SignalR is available."""
        assert SIGNALR_AVAILABLE is True

    def test_basic_connection(self, mock_connection):
        """Test basic connection establishment."""
        (mock_user_conn, mock_market_conn), mock_builder = mock_connection

        # Create real-time client
        client = ProjectXRealtimeClient(jwt_token="test_token", account_id="1001")

        # Test connection
        success = client.connect()

        assert success is True
        assert client.is_connected() is True
        mock_user_conn.start.assert_called_once()
        mock_market_conn.start.assert_called_once()

    def test_connection_failure(self, mock_connection):
        """Test handling of connection failures."""
        (mock_user_conn, mock_market_conn), mock_builder = mock_connection

        # Make connection fail
        mock_user_conn.start.side_effect = Exception("Connection failed")

        # Create real-time client
        client = ProjectXRealtimeClient(jwt_token="test_token", account_id="1001")

        # Test connection
        success = client.connect()

        assert success is False
        assert client.is_connected() is False

    def test_disconnection(self, mock_connection):
        """Test disconnection functionality."""
        (mock_user_conn, mock_market_conn), mock_builder = mock_connection

        # Create and connect client
        client = ProjectXRealtimeClient(jwt_token="test_token", account_id="1001")
        client.connect()

        assert client.is_connected() is True

        # Test disconnection
        client.disconnect()

        assert client.is_connected() is False
        mock_user_conn.stop.assert_called_once()
        mock_market_conn.stop.assert_called_once()

    def test_user_data_subscriptions(self, mock_connection):
        """Test subscription to user updates."""
        (mock_user_conn, mock_market_conn), mock_builder = mock_connection

        # Create and connect client
        client = ProjectXRealtimeClient(jwt_token="test_token", account_id="1001")
        client.connect()

        # Subscribe to user updates
        success = client.subscribe_user_updates()

        assert success is True
        # Verify subscription message was sent
        mock_user_conn.send.assert_called()
        call_args = mock_user_conn.send.call_args
        assert "Subscribe" in str(call_args)

    def test_market_data_subscriptions(self, mock_connection):
        """Test subscription to market data."""
        (mock_user_conn, mock_market_conn), mock_builder = mock_connection

        # Create and connect client
        client = ProjectXRealtimeClient(jwt_token="test_token", account_id="1001")
        client.connect()

        # Subscribe to market data
        contracts = ["CON.F.US.MGC.M25", "CON.F.US.MNQ.M25"]
        success = client.subscribe_market_data(contracts)

        assert success is True
        # Verify subscription message was sent
        mock_market_conn.send.assert_called()

    def test_callback_registration(self, mock_connection):
        """Test callback registration functionality."""
        (mock_user_conn, mock_market_conn), mock_builder = mock_connection

        # Create client
        client = ProjectXRealtimeClient(jwt_token="test_token", account_id="1001")

        # Test callback registration
        callback_called = False

        def test_callback(data):
            nonlocal callback_called
            callback_called = True

        client.add_callback("test_event", test_callback)

        # Trigger callback
        client._trigger_callbacks("test_event", {})

        assert callback_called is True

    def test_connection_event_handlers(self, mock_connection):
        """Test that connection event handlers are set up."""
        (mock_user_conn, mock_market_conn), mock_builder = mock_connection

        # Create client and connect to trigger setup_connections
        client = ProjectXRealtimeClient(jwt_token="test_token", account_id="1001")
        client.connect()  # This triggers setup_connections where event handlers are registered

        # Verify event handlers are registered on the market connection
        mock_market_conn.on.assert_any_call("GatewayQuote", client._on_quote_update)

        # Verify event handlers are registered on the user connection
        mock_user_conn.on.assert_any_call("GatewayUserOrder", client._on_order_update)
        mock_user_conn.on.assert_any_call(
            "GatewayUserPosition", client._on_position_update
        )
        mock_user_conn.on.assert_any_call(
            "GatewayUserAccount", client._on_account_update
        )

    def test_reconnection_capability(self, mock_connection):
        """Test that automatic reconnection is configured."""
        (mock_user_conn, mock_market_conn), mock_builder = mock_connection

        # Create client and connect to trigger setup_connections
        client = ProjectXRealtimeClient(jwt_token="test_token", account_id="1001")
        client.connect()  # This triggers setup_connections where builder methods are called

        # Verify automatic reconnection was configured
        mock_builder.return_value.with_automatic_reconnect.assert_called()

    def test_multiple_callback_registration(self, mock_connection):
        """Test registering multiple callbacks for the same event."""
        (mock_user_conn, mock_market_conn), mock_builder = mock_connection

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
        (mock_user_conn, mock_market_conn), mock_builder = mock_connection

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
        (mock_user_conn, mock_market_conn), mock_builder = mock_connection

        # Create client
        client = ProjectXRealtimeClient(jwt_token="test_token", account_id="1001")

        # Initially not connected
        assert client.is_connected() is False

        # Connect
        client.connect()
        assert client.is_connected() is True

        # Disconnect
        client.disconnect()
        assert client.is_connected() is False

    def test_hub_url_configuration(self, mock_connection):
        """Test that hub URLs are properly configured."""
        (mock_user_conn, mock_market_conn), mock_builder = mock_connection

        # Create client with custom hub URL
        custom_url = "https://custom.hub.url"
        client = ProjectXRealtimeClient(
            jwt_token="test_token", account_id="1001", user_hub_url=custom_url
        )
        client.connect()  # This triggers setup_connections where builder methods are called

        # Verify custom URL was used - check all calls since both user and market hubs are set up
        mock_builder.return_value.with_url.assert_called()
        all_calls = mock_builder.return_value.with_url.call_args_list

        # Check that one of the calls includes our custom URL
        custom_url_found = False
        for call in all_calls:
            if custom_url in str(call):
                custom_url_found = True
                break

        assert custom_url_found, (
            f"Custom URL {custom_url} not found in calls: {all_calls}"
        )


def run_realtime_client_tests():
    """Helper function to run Real-time Client connection tests."""
    print("Running Phase 1 Real-time Client Connection Tests...")
    pytest.main([__file__, "-v", "-s"])


if __name__ == "__main__":
    run_realtime_client_tests()
