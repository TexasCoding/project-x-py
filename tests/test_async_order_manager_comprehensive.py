"""
Comprehensive async tests for OrderManager converted from synchronous tests.

Tests both sync and async order managers to ensure compatibility.
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from project_x_py import (
    OrderManager,
    ProjectX,
    create_order_manager,
)
from project_x_py.realtime import ProjectXRealtimeClient
RealtimeClient = ProjectXRealtimeClient  # back-compat for existing code


class TestAsyncOrderManagerInitialization:
    """Test suite for Async Order Manager initialization."""

    @pytest.fixture
    async def mock_async_client(self):
        """Create a mock AsyncProjectX client."""
        client = AsyncMock(spec=ProjectX)
        client.account_info = Mock(id="1001", name="Demo Account")
        client.session_token = "test_token"
        return client

    @pytest.mark.asyncio
    async def test_async_basic_initialization(self, mock_async_client):
        """Test basic AsyncOrderManager initialization."""
        order_manager = OrderManager(mock_async_client)

        assert order_manager.project_x == mock_async_client
        assert order_manager.realtime_client is None
        assert order_manager._realtime_enabled is False
        assert hasattr(order_manager, "tracked_orders")
        assert hasattr(order_manager, "stats")

    @pytest.mark.asyncio
    async def test_async_initialize_without_realtime(self, mock_async_client):
        """Test AsyncOrderManager initialization without real-time."""
        order_manager = OrderManager(mock_async_client)

        # Initialize without real-time
        result = await order_manager.initialize()

        assert result is True
        assert order_manager._realtime_enabled is False
        assert order_manager.realtime_client is None

    @pytest.mark.asyncio
    async def test_async_initialize_with_realtime(self, mock_async_client):
        """Test AsyncOrderManager initialization with real-time integration."""
        # Mock async real-time client
        mock_realtime = AsyncMock(spec=RealtimeClient)
        mock_realtime.add_callback = AsyncMock()

        order_manager = OrderManager(mock_async_client)

        # Initialize with real-time
        result = await order_manager.initialize(realtime_client=mock_realtime)

        assert result is True
        assert order_manager._realtime_enabled is True
        assert order_manager.realtime_client == mock_realtime

        # Verify callbacks were registered
        assert mock_realtime.add_callback.call_count >= 2
        mock_realtime.add_callback.assert_any_call(
            "order_update", order_manager._on_order_update
        )
        mock_realtime.add_callback.assert_any_call(
            "trade_execution", order_manager._on_trade_execution
        )

    @pytest.mark.asyncio
    async def test_async_initialize_with_realtime_exception(self, mock_async_client):
        """Test AsyncOrderManager initialization when real-time setup fails."""
        # Mock real-time client that raises exception
        mock_realtime = AsyncMock(spec=RealtimeClient)
        mock_realtime.add_callback.side_effect = Exception("Connection error")

        order_manager = OrderManager(mock_async_client)

        # Initialize with real-time that fails
        result = await order_manager.initialize(realtime_client=mock_realtime)

        # Should return False on failure
        assert result is False
        assert order_manager._realtime_enabled is False

    @pytest.mark.asyncio
    async def test_async_reinitialize_order_manager(self, mock_async_client):
        """Test that AsyncOrderManager can be reinitialized."""
        order_manager = OrderManager(mock_async_client)

        # First initialization
        result1 = await order_manager.initialize()
        assert result1 is True

        # Second initialization should also work
        result2 = await order_manager.initialize()
        assert result2 is True

    @pytest.mark.asyncio
    async def test_create_async_order_manager_helper_function(self):
        """Test the create_async_order_manager helper function."""
        with patch("project_x_py.AsyncOrderManager") as mock_order_manager_class:
            mock_order_manager = AsyncMock()
            mock_order_manager.initialize.return_value = True
            mock_order_manager_class.return_value = mock_order_manager

            client = AsyncMock(spec=ProjectX)

            # Test without real-time
            order_manager = create_order_manager(client)

            assert order_manager == mock_order_manager
            mock_order_manager_class.assert_called_once_with(client)
            # Note: create_async_order_manager doesn't call initialize automatically

    @pytest.mark.asyncio
    async def test_create_async_order_manager_with_realtime(self):
        """Test create_async_order_manager with real-time client."""
        with patch("project_x_py.AsyncOrderManager") as mock_order_manager_class:
            mock_order_manager = AsyncMock()
            mock_order_manager.initialize.return_value = True
            mock_order_manager_class.return_value = mock_order_manager

            client = AsyncMock(spec=ProjectX)
            realtime_client = AsyncMock(spec=RealtimeClient)

            # Test with real-time
            order_manager = create_order_manager(
                client, realtime_client=realtime_client
            )

            assert order_manager == mock_order_manager
            mock_order_manager_class.assert_called_once_with(client, realtime_client)

    @pytest.mark.asyncio
    async def test_async_order_manager_without_account_info(self):
        """Test AsyncOrderManager behavior when client has no account info."""
        client = AsyncMock(spec=ProjectX)
        client.account_info = None

        order_manager = OrderManager(client)
        result = await order_manager.initialize()

        # Should initialize successfully
        assert result is True

    @pytest.mark.asyncio
    async def test_async_order_manager_attributes(self, mock_async_client):
        """Test AsyncOrderManager has expected attributes after initialization."""
        order_manager = OrderManager(mock_async_client)
        await order_manager.initialize()

        # Check expected attributes exist
        assert hasattr(order_manager, "project_x")
        assert hasattr(order_manager, "realtime_client")
        assert hasattr(order_manager, "_realtime_enabled")
        assert hasattr(order_manager, "tracked_orders")
        assert hasattr(order_manager, "order_callbacks")
        assert hasattr(order_manager, "stats")

        # These should be initialized
        assert order_manager.project_x is not None
        assert isinstance(order_manager.tracked_orders, dict)
        assert isinstance(order_manager.stats, dict)

    @pytest.mark.asyncio
    async def test_async_order_operations(self, mock_async_client):
        """Test basic async order operations."""
        # Mock successful order response
        mock_async_client.place_order = AsyncMock(
            return_value=Mock(success=True, orderId="ORD123")
        )
        mock_async_client.search_open_orders = AsyncMock(return_value=[])
        mock_async_client.search_instruments = AsyncMock(
            return_value=[Mock(activeContract="MGC.TEST")]
        )

        order_manager = OrderManager(mock_async_client)
        await order_manager.initialize()

        # Test placing an order
        response = await order_manager.place_market_order("MGC", 0, 1)
        assert response.success is True
        assert response.orderId == "ORD123"

        # Test searching orders
        orders = await order_manager.search_open_orders()
        assert orders == []

    @pytest.mark.asyncio
    async def test_async_concurrent_order_operations(self, mock_async_client):
        """Test concurrent async order operations."""
        # Mock responses
        mock_async_client.search_open_orders = AsyncMock(return_value=[])
        mock_async_client.search_closed_orders = AsyncMock(return_value=[])
        mock_async_client.get_order_status = AsyncMock(
            return_value={"status": "filled"}
        )

        order_manager = OrderManager(mock_async_client)
        await order_manager.initialize()

        # Execute operations concurrently
        results = await asyncio.gather(
            order_manager.search_open_orders(),
            order_manager.search_closed_orders(),
            order_manager.get_order_status("ORD123"),
        )

        assert len(results) == 3
        assert results[0] == []  # open orders
        assert results[1] == []  # closed orders
        assert results[2] == {"status": "filled"}  # order status


class TestSyncAsyncOrderManagerCompatibility:
    """Test compatibility between sync and async order managers."""

    @pytest.fixture
    def mock_sync_client(self):
        """Create a mock sync ProjectX client."""
        client = Mock(spec=ProjectX)
        client.account_info = Mock(id=1001, name="Demo Account")
        client.session_token = "test_token"
        client._authenticated = True
        return client

    @pytest.fixture
    async def mock_async_client(self):
        """Create a mock async ProjectX client."""
        client = AsyncMock(spec=ProjectX)
        client.account_info = Mock(id="1001", name="Demo Account")
        client.session_token = "test_token"
        return client

    def test_sync_order_manager_still_works(self, mock_sync_client):
        """Test that sync order manager still works alongside async."""
        order_manager = OrderManager(mock_sync_client)
        result = order_manager.initialize()

        assert result is True
        assert order_manager.project_x == mock_sync_client

    @pytest.mark.asyncio
    async def test_both_managers_can_coexist(self, mock_sync_client, mock_async_client):
        """Test that both sync and async managers can coexist."""
        # Create both managers
        sync_manager = OrderManager(mock_sync_client)
        async_manager = OrderManager(mock_async_client)

        # Initialize both
        sync_result = sync_manager.initialize()
        async_result = await async_manager.initialize()

        assert sync_result is True
        assert async_result is True

        # Verify they're different instances
        assert type(sync_manager) != type(async_manager)
        assert sync_manager.project_x != async_manager.project_x

    @pytest.mark.asyncio
    async def test_factory_functions_work(self, mock_sync_client, mock_async_client):
        """Test that both factory functions work correctly."""
        # Test sync factory
        sync_manager = create_order_manager(mock_sync_client)
        assert isinstance(sync_manager, OrderManager)

        # Test async factory
        async_manager = create_order_manager(mock_async_client)
        assert isinstance(async_manager, OrderManager)

    @pytest.mark.asyncio
    async def test_async_error_handling(self, mock_async_client):
        """Test error handling in async order manager."""
        # Mock client that raises errors
        mock_async_client.place_order = AsyncMock(
            side_effect=Exception("Network error")
        )

        order_manager = OrderManager(mock_async_client)
        await order_manager.initialize()

        # Should handle errors gracefully (implementation dependent)
        with pytest.raises(Exception):
            await order_manager.place_market_order("MGC", 0, 1)

    @pytest.mark.asyncio
    async def test_async_realtime_callback_handling(self, mock_async_client):
        """Test async real-time callback handling."""
        mock_realtime = AsyncMock(spec=RealtimeClient)
        mock_realtime.add_callback = AsyncMock()

        order_manager = OrderManager(mock_async_client)
        await order_manager.initialize(realtime_client=mock_realtime)

        # Simulate callback execution
        test_order_data = {"orderId": "ORD123", "status": "filled"}

        # Test that callbacks can be called
        if hasattr(order_manager, "_on_order_update"):
            await order_manager._on_order_update(test_order_data)

        # Verify callback was registered
        assert mock_realtime.add_callback.called

    @pytest.mark.asyncio
    async def test_async_performance_vs_sync(self, mock_async_client):
        """Test that async operations can be performed concurrently."""
        # Mock multiple async operations
        mock_async_client.search_open_orders = AsyncMock(
            side_effect=lambda: asyncio.sleep(0.1) or []
        )
        mock_async_client.search_closed_orders = AsyncMock(
            side_effect=lambda: asyncio.sleep(0.1) or []
        )
        mock_async_client.get_order_history = AsyncMock(
            side_effect=lambda: asyncio.sleep(0.1) or []
        )

        order_manager = OrderManager(mock_async_client)
        await order_manager.initialize()

        # Time concurrent execution
        import time

        start_time = time.time()

        results = await asyncio.gather(
            order_manager.search_open_orders(),
            order_manager.search_closed_orders(),
            order_manager.get_order_history(),
        )

        end_time = time.time()

        # Should complete in less time than sequential (0.3s)
        assert end_time - start_time < 0.2  # Concurrent should be faster
        assert len(results) == 3
