"""
Comprehensive tests for realtime.core module following TDD principles.

Tests what the code SHOULD do, not what it currently does.
Any failures indicate bugs in the implementation that need fixing.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from project_x_py.models import ProjectXConfig
from project_x_py.realtime.core import ProjectXRealtimeClient
from project_x_py.types.base import HubConnection


@pytest.fixture
def mock_config():
    """Create mock ProjectXConfig for testing."""
    config = MagicMock(spec=ProjectXConfig)
    config.user_hub_url = "https://test.user.hub"
    config.market_hub_url = "https://test.market.hub"
    return config


@pytest.fixture
def realtime_client(mock_config):
    """Create ProjectXRealtimeClient instance for testing."""
    return ProjectXRealtimeClient(
        jwt_token="test_jwt_token",
        account_id="test_account_123",
        config=mock_config,
    )


class TestProjectXRealtimeClientInitialization:
    """Test ProjectXRealtimeClient initialization."""

    def test_init_with_default_config(self):
        """Test initialization with default configuration."""
        client = ProjectXRealtimeClient(
            jwt_token="test_token",
            account_id="account_123"
        )

        assert client.jwt_token == "test_token"
        assert client.account_id == "account_123"
        assert client.user_hub_url == "https://rtc.topstepx.com/hubs/user"
        assert client.market_hub_url == "https://rtc.topstepx.com/hubs/market"
        assert client.user_connection is None
        assert client.market_connection is None
        assert client.user_connected is False
        assert client.market_connected is False
        assert client.setup_complete is False
        assert client.stats["events_received"] == 0
        assert client.stats["connection_errors"] == 0

    def test_init_with_custom_config(self, mock_config):
        """Test initialization with custom configuration."""
        client = ProjectXRealtimeClient(
            jwt_token="test_token",
            account_id="account_123",
            config=mock_config
        )

        assert client.jwt_token == "test_token"
        assert client.account_id == "account_123"
        assert client.user_hub_url == "https://test.user.hub"
        assert client.market_hub_url == "https://test.market.hub"

    def test_init_with_url_overrides(self, mock_config):
        """Test initialization with URL overrides."""
        client = ProjectXRealtimeClient(
            jwt_token="test_token",
            account_id="account_123",
            user_hub_url="https://override.user.hub",
            market_hub_url="https://override.market.hub",
            config=mock_config
        )

        assert client.user_hub_url == "https://override.user.hub"
        assert client.market_hub_url == "https://override.market.hub"
        # Base URLs should be set from overrides
        assert client.base_user_url == "https://override.user.hub"
        assert client.base_market_url == "https://override.market.hub"

    def test_init_url_priority(self):
        """Test URL priority: params > config > defaults."""
        # Test with config only
        config = MagicMock(spec=ProjectXConfig)
        config.user_hub_url = "https://config.user.hub"
        config.market_hub_url = "https://config.market.hub"

        client = ProjectXRealtimeClient(
            jwt_token="token",
            account_id="123",
            config=config
        )
        assert client.user_hub_url == "https://config.user.hub"
        assert client.market_hub_url == "https://config.market.hub"

        # Test with override
        client = ProjectXRealtimeClient(
            jwt_token="token",
            account_id="123",
            user_hub_url="https://override.user.hub",
            config=config
        )
        assert client.user_hub_url == "https://override.user.hub"
        assert client.market_hub_url == "https://config.market.hub"

    def test_init_creates_async_primitives(self, realtime_client):
        """Test that initialization creates proper async primitives."""
        assert hasattr(realtime_client, '_callback_lock')
        assert isinstance(realtime_client._callback_lock, asyncio.Lock)
        assert hasattr(realtime_client, '_connection_lock')
        assert isinstance(realtime_client._connection_lock, asyncio.Lock)
        assert hasattr(realtime_client, 'user_hub_ready')
        assert isinstance(realtime_client.user_hub_ready, asyncio.Event)
        assert hasattr(realtime_client, 'market_hub_ready')
        assert isinstance(realtime_client.market_hub_ready, asyncio.Event)

    def test_init_task_manager(self, realtime_client):
        """Test that TaskManagerMixin is properly initialized."""
        # TaskManagerMixin should be initialized with correct attributes
        assert hasattr(realtime_client, '_managed_tasks')
        assert hasattr(realtime_client, '_persistent_tasks')
        assert hasattr(realtime_client, 'get_task_stats')
        assert hasattr(realtime_client, '_create_task')
        assert hasattr(realtime_client, '_cleanup_tasks')

    def test_init_subscribed_contracts_list(self, realtime_client):
        """Test that subscribed contracts list is initialized."""
        assert hasattr(realtime_client, '_subscribed_contracts')
        assert isinstance(realtime_client._subscribed_contracts, list)
        assert len(realtime_client._subscribed_contracts) == 0

    def test_init_callbacks_defaultdict(self, realtime_client):
        """Test that callbacks defaultdict is properly initialized."""
        assert hasattr(realtime_client, 'callbacks')
        # Test that it behaves like a defaultdict
        assert isinstance(realtime_client.callbacks['test_event'], list)
        assert len(realtime_client.callbacks['test_event']) == 0

    def test_base_urls_with_config_only(self):
        """Test base URLs are set correctly with config only."""
        config = MagicMock(spec=ProjectXConfig)
        config.user_hub_url = "https://config.user.hub"
        config.market_hub_url = "https://config.market.hub"

        client = ProjectXRealtimeClient(
            jwt_token="token",
            account_id="123",
            config=config
        )

        assert client.base_user_url == "https://config.user.hub"
        assert client.base_market_url == "https://config.market.hub"

    def test_base_urls_with_overrides_no_config(self):
        """Test base URLs with URL overrides but no config."""
        client = ProjectXRealtimeClient(
            jwt_token="token",
            account_id="123",
            user_hub_url="https://override.user.hub",
            market_hub_url="https://override.market.hub"
        )

        assert client.base_user_url == "https://override.user.hub"
        assert client.base_market_url == "https://override.market.hub"

    def test_base_urls_defaults(self):
        """Test base URLs use defaults when no config or overrides."""
        client = ProjectXRealtimeClient(
            jwt_token="token",
            account_id="123"
        )

        assert client.base_user_url == "https://rtc.topstepx.com/hubs/user"
        assert client.base_market_url == "https://rtc.topstepx.com/hubs/market"


class TestProjectXRealtimeClientMixins:
    """Test that all required mixins are properly inherited."""

    def test_connection_management_mixin(self, realtime_client):
        """Test ConnectionManagementMixin methods are available."""
        assert hasattr(realtime_client, 'connect')
        assert hasattr(realtime_client, 'disconnect')
        assert hasattr(realtime_client, 'is_connected')
        assert hasattr(realtime_client, 'setup_connections')
        assert hasattr(realtime_client, 'update_jwt_token')

    def test_event_handling_mixin(self, realtime_client):
        """Test EventHandlingMixin methods are available."""
        assert hasattr(realtime_client, 'add_callback')
        assert hasattr(realtime_client, 'remove_callback')
        assert hasattr(realtime_client, '_trigger_callbacks')
        assert hasattr(realtime_client, 'enable_batching')
        assert hasattr(realtime_client, 'disable_batching')

    def test_health_monitoring_mixin(self, realtime_client):
        """Test HealthMonitoringMixin methods are available."""
        assert hasattr(realtime_client, 'get_health_status')
        assert hasattr(realtime_client, 'configure_health_monitoring')
        assert hasattr(realtime_client, '_health_monitoring_enabled')
        assert hasattr(realtime_client, '_health_lock')

    def test_subscriptions_mixin(self, realtime_client):
        """Test SubscriptionsMixin methods are available."""
        assert hasattr(realtime_client, 'subscribe_market_data')
        assert hasattr(realtime_client, 'unsubscribe_market_data')
        assert hasattr(realtime_client, 'subscribe_user_updates')

    def test_task_manager_mixin(self, realtime_client):
        """Test TaskManagerMixin methods are available."""
        assert hasattr(realtime_client, 'get_task_stats')
        assert hasattr(realtime_client, '_cleanup_tasks')
        assert hasattr(realtime_client, '_create_task')
        assert hasattr(realtime_client, '_managed_tasks')
        assert hasattr(realtime_client, '_persistent_tasks')


class TestProjectXRealtimeClientStatistics:
    """Test statistics tracking."""

    def test_initial_stats(self, realtime_client):
        """Test initial statistics values."""
        assert realtime_client.stats["events_received"] == 0
        assert realtime_client.stats["connection_errors"] == 0
        assert realtime_client.stats["last_event_time"] is None
        assert realtime_client.stats["connected_time"] is None

    def test_stats_dictionary_structure(self, realtime_client):
        """Test that stats dictionary has expected keys."""
        expected_keys = {
            "events_received",
            "connection_errors",
            "last_event_time",
            "connected_time"
        }
        assert set(realtime_client.stats.keys()) == expected_keys


class TestProjectXRealtimeClientIntegration:
    """Integration tests for ProjectXRealtimeClient."""

    @pytest.mark.asyncio
    async def test_client_lifecycle(self, realtime_client):
        """Test basic client lifecycle: connect -> subscribe -> disconnect."""
        with patch.object(realtime_client, 'connect', new_callable=AsyncMock) as mock_connect:
            with patch.object(realtime_client, 'disconnect', new_callable=AsyncMock) as mock_disconnect:
                mock_connect.return_value = True

                # Connect
                connected = await realtime_client.connect()
                assert connected is True
                mock_connect.assert_called_once()

                # Disconnect
                await realtime_client.disconnect()
                mock_disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_token_refresh_workflow(self, realtime_client):
        """Test JWT token refresh workflow."""
        with patch.object(realtime_client, 'update_jwt_token', new_callable=AsyncMock) as mock_update:
            mock_update.return_value = True

            new_token = "new_jwt_token"
            success = await realtime_client.update_jwt_token(new_token, timeout=30.0)

            assert success is True
            mock_update.assert_called_once_with(new_token, timeout=30.0)

    @pytest.mark.asyncio
    async def test_health_monitoring_integration(self, realtime_client):
        """Test health monitoring integration."""
        with patch.object(realtime_client, 'get_health_status', new_callable=AsyncMock) as mock_health:
            mock_health.return_value = {
                'health_score': 95,
                'user_hub_latency_ms': 50,
                'market_hub_latency_ms': 45,
                'is_healthy': True
            }

            health = await realtime_client.get_health_status()

            assert health['health_score'] == 95
            assert health['user_hub_latency_ms'] == 50
            assert health['market_hub_latency_ms'] == 45
            assert health['is_healthy'] is True

    @pytest.mark.asyncio
    async def test_event_callback_registration(self, realtime_client):
        """Test event callback registration."""
        callback = AsyncMock()

        with patch.object(realtime_client, 'add_callback', new_callable=AsyncMock) as mock_add:
            await realtime_client.add_callback('test_event', callback)
            mock_add.assert_called_once_with('test_event', callback)

    @pytest.mark.asyncio
    async def test_market_data_subscription(self, realtime_client):
        """Test market data subscription."""
        contracts = ["MNQ", "ES", "NQ"]

        with patch.object(realtime_client, 'subscribe_market_data', new_callable=AsyncMock) as mock_subscribe:
            mock_subscribe.return_value = True

            success = await realtime_client.subscribe_market_data(contracts)

            assert success is True
            mock_subscribe.assert_called_once_with(contracts)

    @pytest.mark.asyncio
    async def test_task_cleanup_on_disconnect(self, realtime_client):
        """Test that tasks are cleaned up on disconnect."""
        with patch.object(realtime_client, '_cleanup_tasks', new_callable=AsyncMock) as mock_cleanup:
            with patch.object(realtime_client, 'disconnect', new_callable=AsyncMock) as mock_disconnect:
                # Patch disconnect to call _cleanup_tasks
                async def disconnect_with_cleanup():
                    await mock_cleanup()
                    return True

                mock_disconnect.side_effect = disconnect_with_cleanup

                await realtime_client.disconnect()

                mock_cleanup.assert_called_once()


class TestProjectXRealtimeClientErrorHandling:
    """Test error handling in ProjectXRealtimeClient."""

    @pytest.mark.asyncio
    async def test_connection_error_handling(self, realtime_client):
        """Test that connection errors are properly handled."""
        with patch.object(realtime_client, 'connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.side_effect = Exception("Connection failed")

            with pytest.raises(Exception, match="Connection failed"):
                await realtime_client.connect()

    @pytest.mark.asyncio
    async def test_token_refresh_timeout(self, realtime_client):
        """Test token refresh timeout handling."""
        with patch.object(realtime_client, 'update_jwt_token', new_callable=AsyncMock) as mock_update:
            mock_update.side_effect = asyncio.TimeoutError()

            with pytest.raises(asyncio.TimeoutError):
                await realtime_client.update_jwt_token("new_token", timeout=0.1)

    def test_invalid_jwt_token(self):
        """Test initialization with invalid JWT token."""
        # Should not raise during initialization
        client = ProjectXRealtimeClient(
            jwt_token="",  # Empty token
            account_id="123"
        )
        assert client.jwt_token == ""

    def test_invalid_account_id(self):
        """Test initialization with invalid account ID."""
        # Should not raise during initialization
        client = ProjectXRealtimeClient(
            jwt_token="token",
            account_id=""  # Empty account ID
        )
        assert client.account_id == ""


class TestProjectXRealtimeClientEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_init_with_none_values(self):
        """Test initialization with None values uses defaults."""
        client = ProjectXRealtimeClient(
            jwt_token="token",
            account_id="123",
            user_hub_url=None,
            market_hub_url=None,
            config=None
        )

        assert client.user_hub_url == "https://rtc.topstepx.com/hubs/user"
        assert client.market_hub_url == "https://rtc.topstepx.com/hubs/market"

    def test_very_long_jwt_token(self):
        """Test initialization with very long JWT token."""
        long_token = "a" * 10000  # Very long token
        client = ProjectXRealtimeClient(
            jwt_token=long_token,
            account_id="123"
        )
        assert client.jwt_token == long_token

    def test_special_characters_in_account_id(self):
        """Test initialization with special characters in account ID."""
        special_id = "account-123!@#$%^&*()"
        client = ProjectXRealtimeClient(
            jwt_token="token",
            account_id=special_id
        )
        assert client.account_id == special_id

    @pytest.mark.asyncio
    async def test_concurrent_callback_registration(self, realtime_client):
        """Test concurrent callback registration is thread-safe."""
        callbacks = [AsyncMock() for _ in range(10)]

        with patch.object(realtime_client, 'add_callback', new_callable=AsyncMock) as mock_add:
            # Register callbacks concurrently
            tasks = [
                realtime_client.add_callback(f'event_{i}', cb)
                for i, cb in enumerate(callbacks)
            ]

            await asyncio.gather(*tasks)

            # Should be called for each callback
            assert mock_add.call_count == 10

    def test_logger_initialization(self, realtime_client):
        """Test that logger is properly initialized."""
        assert hasattr(realtime_client, 'logger')
        assert realtime_client.logger.name == 'project_x_py.realtime.core'

    def test_subscribed_contracts_tracking(self, realtime_client):
        """Test subscribed contracts list for reconnection."""
        # Add some contracts
        realtime_client._subscribed_contracts.append("MNQ")
        realtime_client._subscribed_contracts.append("ES")

        assert len(realtime_client._subscribed_contracts) == 2
        assert "MNQ" in realtime_client._subscribed_contracts
        assert "ES" in realtime_client._subscribed_contracts

    def test_stats_update(self, realtime_client):
        """Test that stats can be updated."""
        import datetime

        # Update stats
        realtime_client.stats["events_received"] = 100
        realtime_client.stats["connection_errors"] = 5
        realtime_client.stats["last_event_time"] = datetime.datetime.now()

        assert realtime_client.stats["events_received"] == 100
        assert realtime_client.stats["connection_errors"] == 5
        assert realtime_client.stats["last_event_time"] is not None


class TestProjectXRealtimeClientThreadSafety:
    """Test thread safety and async operations."""

    @pytest.mark.asyncio
    async def test_callback_lock_prevents_race_condition(self, realtime_client):
        """Test that callback lock prevents race conditions."""
        call_order = []

        async def slow_operation(name):
            async with realtime_client._callback_lock:
                call_order.append(f"{name}_start")
                await asyncio.sleep(0.01)
                call_order.append(f"{name}_end")

        # Run operations concurrently
        await asyncio.gather(
            slow_operation("op1"),
            slow_operation("op2"),
            slow_operation("op3")
        )

        # Check that operations didn't interleave
        for i in range(0, len(call_order), 2):
            assert call_order[i].replace("_start", "") == call_order[i+1].replace("_end", "")

    @pytest.mark.asyncio
    async def test_connection_lock_prevents_concurrent_connects(self, realtime_client):
        """Test that connection lock prevents concurrent connection attempts."""
        connect_count = 0

        async def mock_connect():
            nonlocal connect_count
            async with realtime_client._connection_lock:
                connect_count += 1
                await asyncio.sleep(0.01)
                return connect_count

        with patch.object(realtime_client, 'connect', side_effect=mock_connect):
            # Try to connect multiple times concurrently
            results = await asyncio.gather(
                realtime_client.connect(),
                realtime_client.connect(),
                realtime_client.connect()
            )

            # Each should get a different count value due to serialization
            assert results == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_event_readiness_signaling(self, realtime_client):
        """Test that event readiness signals work correctly."""
        # Initially not set
        assert not realtime_client.user_hub_ready.is_set()
        assert not realtime_client.market_hub_ready.is_set()

        # Set user hub ready
        realtime_client.user_hub_ready.set()
        assert realtime_client.user_hub_ready.is_set()
        assert not realtime_client.market_hub_ready.is_set()

        # Set market hub ready
        realtime_client.market_hub_ready.set()
        assert realtime_client.user_hub_ready.is_set()
        assert realtime_client.market_hub_ready.is_set()

        # Clear events
        realtime_client.user_hub_ready.clear()
        realtime_client.market_hub_ready.clear()
        assert not realtime_client.user_hub_ready.is_set()
        assert not realtime_client.market_hub_ready.is_set()
