"""
Tests for connection_management.py module.

This test suite provides comprehensive coverage for the ConnectionManagementMixin class,
following Test-Driven Development (TDD) principles to validate expected behavior
and uncover potential bugs.

Coverage areas:
- Connection setup and initialization
- JWT authentication and URL construction
- Dual-hub connection management (user and market hubs)
- SignalR event handler registration
- Connection lifecycle (connect/disconnect)
- Automatic reconnection and error handling
- JWT token refresh with deadlock prevention
- Connection state recovery mechanisms
- Statistics and health monitoring
- Thread-safe async operations
"""

import asyncio
import contextlib
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from project_x_py.realtime.connection_management import ConnectionManagementMixin


class MockProjectXRealtimeClient(ConnectionManagementMixin):
    """Mock client implementing the protocol for testing."""

    def __init__(self, jwt_token: str = "test_token", account_id: str = "test_account"):
        super().__init__()
        self.jwt_token = jwt_token
        self.account_id = account_id
        self.logger = Mock()

        # Connection state attributes
        self.user_connected = False
        self.market_connected = False
        self.setup_complete = False

        # Event objects for connection signaling
        self.user_hub_ready = asyncio.Event()
        self.market_hub_ready = asyncio.Event()

        # Connection objects (will be mocked)
        self.user_connection = None
        self.market_connection = None

        # URLs for hub connections
        self.user_hub_url = "https://gateway.example.com/user"
        self.market_hub_url = "https://gateway.example.com/market"

        # Statistics tracking
        self.stats = {
            "events_received": 0,
            "connection_errors": 0,
            "last_event_time": None,
            "connected_time": None,
        }

        # Subscription tracking
        self._subscribed_contracts = set()

        # Thread synchronization
        self._connection_lock = asyncio.Lock()

    # Mock forward methods that would be in other mixins
    async def _forward_account_update(self, data: dict[str, Any]) -> None:
        pass

    async def _forward_position_update(self, data: dict[str, Any]) -> None:
        pass

    async def _forward_order_update(self, data: dict[str, Any]) -> None:
        pass

    async def _forward_trade_execution(self, data: dict[str, Any]) -> None:
        pass

    async def _forward_quote_update(self, data: dict[str, Any]) -> None:
        pass

    async def _forward_market_trade(self, data: dict[str, Any]) -> None:
        pass

    async def _forward_market_depth(self, data: dict[str, Any]) -> None:
        pass

    # Mock subscription methods
    async def subscribe_user_updates(self) -> None:
        pass

    async def subscribe_market_data(self, contracts: list[str]) -> None:
        self._subscribed_contracts.update(contracts)


@pytest.fixture
def mock_client():
    """Create a mock ProjectX realtime client."""
    return MockProjectXRealtimeClient()


@pytest.fixture
def mock_hub_connection():
    """Create a mock SignalR HubConnection."""
    connection = Mock()
    connection.start = Mock()
    connection.stop = Mock()
    connection.on = Mock()
    connection.on_open = Mock()
    connection.on_close = Mock()
    connection.on_error = Mock()
    return connection


@pytest.fixture
def mock_hub_builder():
    """Create a mock HubConnectionBuilder."""
    builder = Mock()
    connection = Mock()

    # Chain the builder methods - must include all methods in the chain
    builder.with_url.return_value = builder
    builder.configure_logging.return_value = builder  # Missing method!
    builder.with_automatic_reconnect.return_value = builder
    builder.build.return_value = connection

    # Setup connection mocks
    connection.start = Mock()
    connection.stop = Mock()
    connection.on = Mock()
    connection.on_open = Mock()
    connection.on_close = Mock()
    connection.on_error = Mock()

    return builder, connection


def create_mock_hub_builder():
    """Helper function to create mock hub builder and connection."""
    builder = Mock()
    connection = Mock()

    # Chain the builder methods - must include all methods in the chain
    builder.with_url.return_value = builder
    builder.configure_logging.return_value = builder  # Missing method!
    builder.with_automatic_reconnect.return_value = builder
    builder.build.return_value = connection

    # Setup connection mocks
    connection.start = Mock()
    connection.stop = Mock()
    connection.on = Mock()
    connection.on_open = Mock()
    connection.on_close = Mock()
    connection.on_error = Mock()

    return builder, connection


class TestConnectionManagementMixin:
    """Test suite for ConnectionManagementMixin."""

    def test_init_sets_default_attributes(self, mock_client):
        """Test that __init__ properly initializes connection management attributes."""
        assert mock_client._loop is None
        assert hasattr(mock_client, '_connection_lock')
        assert isinstance(mock_client._connection_lock, asyncio.Lock)

    @pytest.mark.asyncio
    @patch('project_x_py.realtime.connection_management.HubConnectionBuilder')
    async def test_setup_connections_creates_user_hub(self, mock_builder_class, mock_client):
        """Test that setup_connections creates user hub with correct URL and JWT token."""
        builder, connection = create_mock_hub_builder()
        mock_builder_class.return_value = builder

        await mock_client.setup_connections()

        # Verify user hub URL includes JWT token as query parameter
        expected_user_url = f"{mock_client.user_hub_url}?access_token={mock_client.jwt_token}"
        builder.with_url.assert_any_call(expected_user_url)

        # Verify automatic reconnection is configured
        builder.with_automatic_reconnect.assert_called()

        # Verify connection is built and stored
        assert mock_client.user_connection is not None

    @pytest.mark.asyncio
    @patch('project_x_py.realtime.connection_management.HubConnectionBuilder')
    async def test_setup_connections_creates_market_hub(self, mock_builder_class, mock_client):
        """Test that setup_connections creates market hub with correct URL and JWT token."""
        builder, connection = create_mock_hub_builder()
        mock_builder_class.return_value = builder

        await mock_client.setup_connections()

        # Verify market hub URL includes JWT token as query parameter
        expected_market_url = f"{mock_client.market_hub_url}?access_token={mock_client.jwt_token}"
        builder.with_url.assert_any_call(expected_market_url)

        # Verify connection is built and stored
        assert mock_client.market_connection is not None

    @pytest.mark.asyncio
    @patch('project_x_py.realtime.connection_management.HubConnectionBuilder')
    async def test_setup_connections_registers_event_handlers(self, mock_builder_class, mock_client):
        """Test that setup_connections registers all required event handlers."""
        builder, connection = create_mock_hub_builder()
        mock_builder_class.return_value = builder

        await mock_client.setup_connections()

        # Verify connection event handlers are registered
        connection.on_open.assert_called()
        connection.on_close.assert_called()
        connection.on_error.assert_called()

        # Verify ProjectX Gateway event handlers are registered
        expected_user_events = [
            "GatewayUserAccount",
            "GatewayUserPosition",
            "GatewayUserOrder",
            "GatewayUserTrade"
        ]

        expected_market_events = [
            "GatewayQuote",
            "GatewayTrade",
            "GatewayDepth"
        ]

        # Check that all event handlers were registered
        for event in expected_user_events + expected_market_events:
            assert any(call[0][0] == event for call in connection.on.call_args_list), f"Event {event} not registered"

    @pytest.mark.asyncio
    @patch('project_x_py.realtime.connection_management.HubConnectionBuilder')
    async def test_setup_connections_sets_completion_flag(self, mock_builder_class, mock_client):
        """Test that setup_connections sets setup_complete flag to True."""
        builder, connection = create_mock_hub_builder()
        mock_builder_class.return_value = builder

        assert mock_client.setup_complete is False

        await mock_client.setup_connections()

        assert mock_client.setup_complete is True

    @pytest.mark.asyncio
    async def test_connect_calls_setup_if_not_complete(self, mock_client):
        """Test that connect() calls setup_connections if setup not complete."""
        with patch.object(mock_client, 'setup_connections', new_callable=AsyncMock) as mock_setup:
            with patch.object(mock_client, '_start_connection_async', new_callable=AsyncMock):
                mock_client.setup_complete = False
                mock_client.user_connection = Mock()
                mock_client.market_connection = Mock()

                # Mock the event waits to avoid timeout
                mock_client.user_hub_ready.set()
                mock_client.market_hub_ready.set()
                mock_client.user_connected = True
                mock_client.market_connected = True

                await mock_client.connect()

                mock_setup.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_stores_event_loop(self, mock_client):
        """Test that connect() stores the current event loop."""
        with patch.object(mock_client, 'setup_connections', new_callable=AsyncMock):
            with patch.object(mock_client, '_start_connection_async', new_callable=AsyncMock):
                mock_client.setup_complete = True
                mock_client.user_connection = Mock()
                mock_client.market_connection = Mock()

                # Mock successful connection
                mock_client.user_hub_ready.set()
                mock_client.market_hub_ready.set()
                mock_client.user_connected = True
                mock_client.market_connected = True

                result = await mock_client.connect()

                assert mock_client._loop is not None
                assert result is True

    @pytest.mark.asyncio
    async def test_connect_returns_false_if_no_event_loop(self, mock_client):
        """Test that connect() returns False if no event loop is running."""
        with patch('asyncio.get_running_loop', side_effect=RuntimeError("No running event loop")):
            result = await mock_client.connect()
            assert result is False

    @pytest.mark.asyncio
    async def test_connect_starts_both_connections(self, mock_client):
        """Test that connect() starts both user and market connections."""
        with patch.object(mock_client, 'setup_connections', new_callable=AsyncMock):
            with patch.object(mock_client, '_start_connection_async', new_callable=AsyncMock) as mock_start:
                mock_client.setup_complete = True
                mock_client.user_connection = Mock()
                mock_client.market_connection = Mock()

                # Mock successful connection
                mock_client.user_hub_ready.set()
                mock_client.market_hub_ready.set()
                mock_client.user_connected = True
                mock_client.market_connected = True

                await mock_client.connect()

                # Verify both connections were started
                assert mock_start.call_count == 2
                mock_start.assert_any_call(mock_client.user_connection, "user")
                mock_start.assert_any_call(mock_client.market_connection, "market")

    @pytest.mark.asyncio
    async def test_connect_returns_false_if_user_connection_missing(self, mock_client):
        """Test that connect() returns False if user connection is None."""
        with patch.object(mock_client, 'setup_connections', new_callable=AsyncMock):
            mock_client.setup_complete = True
            mock_client.user_connection = None  # Missing connection
            mock_client.market_connection = Mock()

            result = await mock_client.connect()

            assert result is False

    @pytest.mark.asyncio
    async def test_connect_returns_false_if_market_connection_missing(self, mock_client):
        """Test that connect() returns False if market connection is None."""
        with patch.object(mock_client, 'setup_connections', new_callable=AsyncMock):
            mock_client.setup_complete = True
            mock_client.user_connection = Mock()
            mock_client.market_connection = None  # Missing connection

            result = await mock_client.connect()

            assert result is False

    @pytest.mark.asyncio
    async def test_connect_waits_for_both_hubs_ready(self, mock_client):
        """Test that connect() waits for both user and market hubs to be ready."""
        with patch.object(mock_client, 'setup_connections', new_callable=AsyncMock):
            with patch.object(mock_client, '_start_connection_async', new_callable=AsyncMock):
                mock_client.setup_complete = True
                mock_client.user_connection = Mock()
                mock_client.market_connection = Mock()

                # Don't set the events initially
                mock_client.user_connected = False
                mock_client.market_connected = False

                # Set events after a short delay to test waiting
                async def set_events_delayed():
                    await asyncio.sleep(0.1)
                    mock_client.user_hub_ready.set()
                    mock_client.market_hub_ready.set()
                    mock_client.user_connected = True
                    mock_client.market_connected = True

                # Start the delayed task
                asyncio.create_task(set_events_delayed())

                result = await mock_client.connect()

                assert result is True

    @pytest.mark.asyncio
    async def test_connect_returns_false_on_timeout(self, mock_client):
        """Test that connect() returns False if connection timeout is reached."""
        with patch.object(mock_client, 'setup_connections', new_callable=AsyncMock):
            with patch.object(mock_client, '_start_connection_async', new_callable=AsyncMock):
                mock_client.setup_complete = True
                mock_client.user_connection = Mock()
                mock_client.market_connection = Mock()

                # Don't set the ready events to cause timeout
                mock_client.user_connected = False
                mock_client.market_connected = False

                # Use a very short timeout for testing
                with patch('asyncio.wait_for', side_effect=TimeoutError()):
                    result = await mock_client.connect()

                assert result is False

    @pytest.mark.asyncio
    async def test_connect_updates_stats_on_success(self, mock_client):
        """Test that connect() updates connection statistics on successful connection."""
        with patch.object(mock_client, 'setup_connections', new_callable=AsyncMock):
            with patch.object(mock_client, '_start_connection_async', new_callable=AsyncMock):
                mock_client.setup_complete = True
                mock_client.user_connection = Mock()
                mock_client.market_connection = Mock()

                # Mock successful connection
                mock_client.user_hub_ready.set()
                mock_client.market_hub_ready.set()
                mock_client.user_connected = True
                mock_client.market_connected = True

                # Record time before connection
                before_time = datetime.now()

                result = await mock_client.connect()

                # Record time after connection
                after_time = datetime.now()

                assert result is True
                assert mock_client.stats["connected_time"] is not None
                assert before_time <= mock_client.stats["connected_time"] <= after_time

    @pytest.mark.asyncio
    async def test_start_connection_async_runs_in_executor(self, mock_client):
        """Test that _start_connection_async runs SignalR start() in executor."""
        mock_connection = Mock()

        with patch('asyncio.get_running_loop') as mock_get_loop:
            mock_loop = AsyncMock()
            mock_get_loop.return_value = mock_loop

            await mock_client._start_connection_async(mock_connection, "test")

            # Verify that start() was called through run_in_executor
            mock_loop.run_in_executor.assert_called_once_with(None, mock_connection.start)

    @pytest.mark.asyncio
    async def test_disconnect_stops_both_connections(self, mock_client):
        """Test that disconnect() stops both user and market connections."""
        mock_user_connection = Mock()
        mock_market_connection = Mock()
        mock_client.user_connection = mock_user_connection
        mock_client.market_connection = mock_market_connection

        with patch('asyncio.get_running_loop') as mock_get_loop:
            mock_loop = AsyncMock()
            mock_get_loop.return_value = mock_loop

            await mock_client.disconnect()

            # Verify both connections were stopped through executor
            assert mock_loop.run_in_executor.call_count == 2
            mock_loop.run_in_executor.assert_any_call(None, mock_user_connection.stop)
            mock_loop.run_in_executor.assert_any_call(None, mock_market_connection.stop)

    @pytest.mark.asyncio
    async def test_disconnect_updates_connection_flags(self, mock_client):
        """Test that disconnect() sets connection flags to False."""
        mock_client.user_connection = Mock()
        mock_client.market_connection = Mock()
        mock_client.user_connected = True
        mock_client.market_connected = True

        with patch('asyncio.get_running_loop') as mock_get_loop:
            mock_get_loop.return_value = AsyncMock()

            await mock_client.disconnect()

            assert mock_client.user_connected is False
            assert mock_client.market_connected is False

    def test_on_user_hub_open_sets_connection_flag(self, mock_client):
        """Test that _on_user_hub_open sets user_connected flag and ready event."""
        mock_client.user_connected = False

        mock_client._on_user_hub_open()

        assert mock_client.user_connected is True
        assert mock_client.user_hub_ready.is_set()

    def test_on_user_hub_close_clears_connection_flag(self, mock_client):
        """Test that _on_user_hub_close clears user_connected flag and ready event."""
        mock_client.user_connected = True
        mock_client.user_hub_ready.set()

        mock_client._on_user_hub_close()

        assert mock_client.user_connected is False
        assert not mock_client.user_hub_ready.is_set()

    def test_on_market_hub_open_sets_connection_flag(self, mock_client):
        """Test that _on_market_hub_open sets market_connected flag and ready event."""
        mock_client.market_connected = False

        mock_client._on_market_hub_open()

        assert mock_client.market_connected is True
        assert mock_client.market_hub_ready.is_set()

    def test_on_market_hub_close_clears_connection_flag(self, mock_client):
        """Test that _on_market_hub_close clears market_connected flag and ready event."""
        mock_client.market_connected = True
        mock_client.market_hub_ready.set()

        mock_client._on_market_hub_close()

        assert mock_client.market_connected is False
        assert not mock_client.market_hub_ready.is_set()

    def test_on_connection_error_ignores_completion_messages(self, mock_client):
        """Test that _on_connection_error ignores SignalR CompletionMessage."""
        # Create a mock error that looks like CompletionMessage
        mock_error = Mock()
        mock_error.__class__.__name__ = "CompletionMessage"

        initial_error_count = mock_client.stats["connection_errors"]

        mock_client._on_connection_error("user", mock_error)

        # Should not increment error count for CompletionMessage
        assert mock_client.stats["connection_errors"] == initial_error_count

    def test_on_connection_error_logs_real_errors(self, mock_client):
        """Test that _on_connection_error logs and counts real errors."""
        mock_error = Exception("Real connection error")

        initial_error_count = mock_client.stats["connection_errors"]

        mock_client._on_connection_error("market", mock_error)

        # Should increment error count for real errors
        assert mock_client.stats["connection_errors"] == initial_error_count + 1

    def test_is_connected_requires_both_hubs(self, mock_client):
        """Test that is_connected() returns True only when both hubs are connected."""
        # Neither connected
        mock_client.user_connected = False
        mock_client.market_connected = False
        assert mock_client.is_connected() is False

        # Only user connected
        mock_client.user_connected = True
        mock_client.market_connected = False
        assert mock_client.is_connected() is False

        # Only market connected
        mock_client.user_connected = False
        mock_client.market_connected = True
        assert mock_client.is_connected() is False

        # Both connected
        mock_client.user_connected = True
        mock_client.market_connected = True
        assert mock_client.is_connected() is True

    def test_get_stats_returns_comprehensive_data(self, mock_client):
        """Test that get_stats() returns all relevant statistics."""
        # Set up some test data
        mock_client.user_connected = True
        mock_client.market_connected = False
        mock_client.stats["events_received"] = 100
        mock_client.stats["connection_errors"] = 5
        mock_client._subscribed_contracts.add("MNQ")
        mock_client._subscribed_contracts.add("ES")

        stats = mock_client.get_stats()

        # Verify all expected fields are present
        expected_fields = [
            "events_received",
            "connection_errors",
            "last_event_time",
            "connected_time",
            "user_connected",
            "market_connected",
            "subscribed_contracts"
        ]

        for field in expected_fields:
            assert field in stats

        # Verify specific values
        assert stats["user_connected"] is True
        assert stats["market_connected"] is False
        assert stats["events_received"] == 100
        assert stats["connection_errors"] == 5
        assert stats["subscribed_contracts"] == 2

    @pytest.mark.asyncio
    async def test_update_jwt_token_stores_original_state(self, mock_client):
        """Test that update_jwt_token stores original state for recovery."""
        original_token = "original_token"
        new_token = "new_token"
        mock_client.jwt_token = original_token
        mock_client.setup_complete = True
        mock_client._subscribed_contracts.add("MNQ")

        with patch.object(mock_client, 'disconnect', new_callable=AsyncMock):
            with patch.object(mock_client, 'connect', new_callable=AsyncMock, return_value=False):
                with patch.object(mock_client, '_recover_connection_state', new_callable=AsyncMock) as mock_recover:

                    result = await mock_client.update_jwt_token(new_token)

                    # Should call recovery with original state
                    mock_recover.assert_called_once()
                    args = mock_recover.call_args[0]
                    assert args[0] == original_token  # original_token
                    assert args[1] is True  # original_setup_complete
                    assert "MNQ" in args[2]  # original_subscriptions

    @pytest.mark.asyncio
    async def test_update_jwt_token_disconnects_before_update(self, mock_client):
        """Test that update_jwt_token disconnects before updating token."""
        with patch.object(mock_client, 'disconnect', new_callable=AsyncMock) as mock_disconnect:
            with patch.object(mock_client, 'connect', new_callable=AsyncMock, return_value=True):
                with patch.object(mock_client, 'subscribe_user_updates', new_callable=AsyncMock):

                    await mock_client.update_jwt_token("new_token")

                    mock_disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_jwt_token_updates_token_and_resets_setup(self, mock_client):
        """Test that update_jwt_token updates the JWT token and resets setup flag."""
        original_token = "original_token"
        new_token = "new_token"
        mock_client.jwt_token = original_token
        mock_client.setup_complete = True

        with patch.object(mock_client, 'disconnect', new_callable=AsyncMock):
            with patch.object(mock_client, 'connect', new_callable=AsyncMock, return_value=True):
                with patch.object(mock_client, 'subscribe_user_updates', new_callable=AsyncMock):

                    result = await mock_client.update_jwt_token(new_token)

                    assert result is True
                    assert mock_client.jwt_token == new_token

    @pytest.mark.asyncio
    async def test_update_jwt_token_resubscribes_on_success(self, mock_client):
        """Test that update_jwt_token re-subscribes to user and market data on success."""
        mock_client._subscribed_contracts.add("MNQ")
        mock_client._subscribed_contracts.add("ES")

        with patch.object(mock_client, 'disconnect', new_callable=AsyncMock):
            with patch.object(mock_client, 'connect', new_callable=AsyncMock, return_value=True):
                with patch.object(mock_client, 'subscribe_user_updates', new_callable=AsyncMock) as mock_user_sub:
                    with patch.object(mock_client, 'subscribe_market_data', new_callable=AsyncMock) as mock_market_sub:

                        result = await mock_client.update_jwt_token("new_token")

                        assert result is True
                        mock_user_sub.assert_called_once()
                        # Set order is not guaranteed, so check that both contracts are present
                        mock_market_sub.assert_called_once()
                        called_contracts = mock_market_sub.call_args[0][0]
                        assert set(called_contracts) == {"MNQ", "ES"}

    @pytest.mark.asyncio
    async def test_update_jwt_token_handles_timeout(self, mock_client):
        """Test that update_jwt_token handles timeout gracefully."""
        with patch.object(mock_client, '_recover_connection_state', new_callable=AsyncMock) as mock_recover:
            with patch('asyncio.timeout', side_effect=TimeoutError()):

                result = await mock_client.update_jwt_token("new_token", timeout=5.0)

                assert result is False
                mock_recover.assert_called_once()

    @pytest.mark.asyncio
    async def test_recover_connection_state_restores_original_token(self, mock_client):
        """Test that _recover_connection_state restores the original JWT token."""
        original_token = "original_token"
        mock_client.jwt_token = "failed_token"

        with patch.object(mock_client, 'connect', new_callable=AsyncMock, return_value=True):
            with patch.object(mock_client, 'subscribe_user_updates', new_callable=AsyncMock):

                await mock_client._recover_connection_state(original_token, True, [])

                assert mock_client.jwt_token == original_token

    @pytest.mark.asyncio
    async def test_recover_connection_state_clears_connection_flags(self, mock_client):
        """Test that _recover_connection_state clears connection flags initially."""
        mock_client.user_connected = True
        mock_client.market_connected = True
        mock_client.user_hub_ready.set()
        mock_client.market_hub_ready.set()

        with patch.object(mock_client, 'connect', new_callable=AsyncMock, return_value=False):

            await mock_client._recover_connection_state("token", True, [])

            # Should be cleared during recovery attempt
            assert mock_client.user_connected is False
            assert mock_client.market_connected is False
            assert not mock_client.user_hub_ready.is_set()
            assert not mock_client.market_hub_ready.is_set()

    @pytest.mark.asyncio
    async def test_recover_connection_state_attempts_reconnection(self, mock_client):
        """Test that _recover_connection_state attempts to reconnect with original token."""
        with patch.object(mock_client, 'connect', new_callable=AsyncMock, return_value=True) as mock_connect:
            with patch.object(mock_client, 'subscribe_user_updates', new_callable=AsyncMock):

                await mock_client._recover_connection_state("original_token", True, ["MNQ"])

                mock_connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_recover_connection_state_restores_subscriptions(self, mock_client):
        """Test that _recover_connection_state restores original subscriptions."""
        original_subscriptions = ["MNQ", "ES"]

        with patch.object(mock_client, 'connect', new_callable=AsyncMock, return_value=True):
            with patch.object(mock_client, 'subscribe_user_updates', new_callable=AsyncMock) as mock_user_sub:
                with patch.object(mock_client, 'subscribe_market_data', new_callable=AsyncMock) as mock_market_sub:

                    await mock_client._recover_connection_state("token", True, original_subscriptions)

                    mock_user_sub.assert_called_once()
                    mock_market_sub.assert_called_once_with(original_subscriptions)

    @pytest.mark.asyncio
    async def test_recover_connection_state_handles_recovery_timeout(self, mock_client):
        """Test that _recover_connection_state handles recovery timeout gracefully."""
        with patch('asyncio.timeout', side_effect=TimeoutError()):

            await mock_client._recover_connection_state("token", True, [])

            # Should end up in disconnected state
            assert mock_client.user_connected is False
            assert mock_client.market_connected is False

    @pytest.mark.asyncio
    async def test_recover_connection_state_handles_exceptions(self, mock_client):
        """Test that _recover_connection_state handles exceptions during recovery."""
        with patch.object(mock_client, 'connect', side_effect=Exception("Recovery failed")):

            await mock_client._recover_connection_state("token", True, [])

            # Should end up in clean disconnected state
            assert mock_client.user_connected is False
            assert mock_client.market_connected is False
            assert not mock_client.user_hub_ready.is_set()
            assert not mock_client.market_hub_ready.is_set()


class TestConnectionManagementIntegration:
    """Integration tests for connection management functionality."""

    @pytest.mark.asyncio
    async def test_full_connection_lifecycle(self, mock_client):
        """Test complete connection lifecycle: setup -> connect -> disconnect."""
        with patch('project_x_py.realtime.connection_management.HubConnectionBuilder') as mock_builder_class:
            builder, connection = create_mock_hub_builder()
            mock_builder_class.return_value = builder

            # Test setup
            await mock_client.setup_connections()
            assert mock_client.setup_complete is True

            # Test connect
            with patch.object(mock_client, '_start_connection_async', new_callable=AsyncMock):
                # Simulate successful connection
                mock_client.user_hub_ready.set()
                mock_client.market_hub_ready.set()
                mock_client.user_connected = True
                mock_client.market_connected = True

                result = await mock_client.connect()
                assert result is True
                assert mock_client.is_connected() is True

            # Test disconnect
            with patch('asyncio.get_running_loop') as mock_get_loop:
                mock_get_loop.return_value = AsyncMock()

                await mock_client.disconnect()
                assert mock_client.user_connected is False
                assert mock_client.market_connected is False

    @pytest.mark.asyncio
    async def test_jwt_token_refresh_with_deadlock_prevention(self, mock_client):
        """Test JWT token refresh with deadlock prevention mechanisms."""
        # Set up initial state
        mock_client._subscribed_contracts.add("MNQ")
        mock_client.setup_complete = True

        # Mock all the methods to simulate successful token refresh
        with patch.object(mock_client, 'disconnect', new_callable=AsyncMock):
            with patch.object(mock_client, 'connect', new_callable=AsyncMock, return_value=True):
                with patch.object(mock_client, 'subscribe_user_updates', new_callable=AsyncMock):
                    with patch.object(mock_client, 'subscribe_market_data', new_callable=AsyncMock):

                        # Test with custom timeout for deadlock prevention
                        result = await mock_client.update_jwt_token("new_token", timeout=15.0)

                        assert result is True
                        assert mock_client.jwt_token == "new_token"

    @pytest.mark.asyncio
    async def test_connection_recovery_after_failed_token_refresh(self, mock_client):
        """Test connection state recovery after failed JWT token refresh."""
        original_token = "original_token"
        mock_client.jwt_token = original_token
        mock_client.setup_complete = True
        mock_client._subscribed_contracts.add("ES")

        # Mock connect to fail, triggering recovery
        with patch.object(mock_client, 'disconnect', new_callable=AsyncMock):
            with patch.object(mock_client, 'connect', new_callable=AsyncMock, return_value=False):
                with patch.object(mock_client, 'subscribe_user_updates', new_callable=AsyncMock):
                    with patch.object(mock_client, 'subscribe_market_data', new_callable=AsyncMock):

                        result = await mock_client.update_jwt_token("failed_token")

                        # Should fail but recover original state
                        assert result is False
                        assert mock_client.jwt_token == original_token

    @pytest.mark.asyncio
    async def test_concurrent_connection_operations(self, mock_client):
        """Test thread safety of concurrent connection operations."""
        # This test ensures that the connection lock prevents race conditions
        async def connect_task():
            with patch.object(mock_client, '_start_connection_async', new_callable=AsyncMock):
                mock_client.user_connection = Mock()
                mock_client.market_connection = Mock()
                mock_client.user_hub_ready.set()
                mock_client.market_hub_ready.set()
                mock_client.user_connected = True
                mock_client.market_connected = True
                return await mock_client.connect()

        async def disconnect_task():
            with patch('asyncio.get_running_loop') as mock_get_loop:
                mock_get_loop.return_value = AsyncMock()
                mock_client.user_connection = Mock()
                mock_client.market_connection = Mock()
                return await mock_client.disconnect()

        # Run operations concurrently
        results = await asyncio.gather(
            connect_task(),
            disconnect_task(),
            return_exceptions=True
        )

        # Both operations should complete without exceptions
        for result in results:
            assert not isinstance(result, Exception)

    def test_statistics_tracking_across_operations(self, mock_client):
        """Test that statistics are properly tracked across various operations."""
        # Test initial stats
        stats = mock_client.get_stats()
        assert stats["events_received"] == 0
        assert stats["connection_errors"] == 0

        # Simulate connection error
        mock_client._on_connection_error("user", Exception("Test error"))

        stats = mock_client.get_stats()
        assert stats["connection_errors"] == 1

        # Test connection state in stats
        mock_client.user_connected = True
        mock_client.market_connected = False

        stats = mock_client.get_stats()
        assert stats["user_connected"] is True
        assert stats["market_connected"] is False
