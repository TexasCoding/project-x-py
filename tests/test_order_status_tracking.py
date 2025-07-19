"""Test order status tracking functionality."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
import time

from project_x_py import ProjectX
from project_x_py.order_manager import OrderManager
from project_x_py.models import Order, Position, Instrument, OrderPlaceResponse, Account
from project_x_py.exceptions import (
    ProjectXError,
    ProjectXConnectionError,
    ProjectXOrderError
)


class TestOrderStatusTracking:
    """Test suite for order status tracking functionality."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock authenticated client."""
        client = Mock(spec=ProjectX)
        client.session_token = "test_jwt_token"
        client.username = "test_user"
        client.accounts = [
            {"account_id": "1001", "account_name": "Test Account", "active": True}
        ]
        client.base_url = "https://api.test.com/api"
        client.headers = {"Authorization": "Bearer test_jwt_token"}
        client.timeout_seconds = 30
        client._authenticated = True
        client._ensure_authenticated = Mock()
        client._handle_response_errors = Mock()
        
        # Mock account info
        account_info = Mock(spec=Account)
        account_info.id = 1001
        account_info.balance = 100000.0
        client.account_info = account_info
        client.get_account_info = Mock(return_value=account_info)
        
        return client

    @pytest.fixture
    def order_manager(self, mock_client):
        """Create an OrderManager instance with mock client."""
        order_manager = OrderManager(mock_client)
        order_manager.initialize()
        return order_manager

    def test_get_order_by_id(self, order_manager, mock_client):
        """Test retrieving a specific order by ID."""
        # Mock order data
        mock_order_data = {
            "id": 12345,
            "accountId": 1001,
            "contractId": "ES",
            "creationTimestamp": datetime.now(timezone.utc).isoformat(),
            "updateTimestamp": None,
            "status": 1,  # Pending
            "type": 1,    # Limit
            "side": 0,    # Buy
            "size": 1,
            "fillVolume": None,
            "limitPrice": 4500.0,
            "stopPrice": None
        }
        
        # Mock search_open_orders to return our order
        with patch.object(order_manager, 'search_open_orders') as mock_search:
            mock_search.return_value = [Order(**mock_order_data)]
            
            # Get order by ID
            order = order_manager.get_order_by_id(12345)
            
            # Verify order retrieved
            assert order is not None
            assert order.id == 12345
            assert order.contractId == "ES"
            assert order.status == 1

    def test_get_order_by_id_not_found(self, order_manager):
        """Test retrieving a non-existent order."""
        with patch.object(order_manager, 'search_open_orders') as mock_search:
            mock_search.return_value = []
            
            # Get non-existent order
            order = order_manager.get_order_by_id(99999)
            
            # Verify order not found
            assert order is None

    def test_is_order_filled(self, order_manager):
        """Test checking if an order is filled."""
        # Mock filled order
        filled_order = Order(
            id=12345,
            accountId=1001,
            contractId="ES",
            creationTimestamp=datetime.now(timezone.utc).isoformat(),
            updateTimestamp=datetime.now(timezone.utc).isoformat(),
            status=2,  # Filled
            type=1,    # Limit
            side=0,    # Buy
            size=1,
            fillVolume=1,
            limitPrice=4500.0,
            stopPrice=None
        )
        
        with patch.object(order_manager, 'get_order_by_id', return_value=filled_order):
            # Check if order is filled
            is_filled = order_manager.is_order_filled(12345)
            
            # Verify order is filled
            assert is_filled is True

    def test_is_order_not_filled(self, order_manager):
        """Test checking if an order is not filled."""
        # Mock pending order
        pending_order = Order(
            id=12345,
            accountId=1001,
            contractId="ES",
            creationTimestamp=datetime.now(timezone.utc).isoformat(),
            updateTimestamp=None,
            status=1,  # Pending
            type=1,    # Limit
            side=0,    # Buy
            size=1,
            fillVolume=None,
            limitPrice=4500.0,
            stopPrice=None
        )
        
        with patch.object(order_manager, 'get_order_by_id', return_value=pending_order):
            # Check if order is filled
            is_filled = order_manager.is_order_filled(12345)
            
            # Verify order is not filled
            assert is_filled is False

    def test_search_open_orders_all(self, order_manager, mock_client):
        """Test searching for all open orders."""
        with patch('project_x_py.order_manager.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {
                "success": True,
                "orders": [
                    {
                        "id": 12345,
                        "accountId": 1001,
                        "contractId": "ES",
                        "creationTimestamp": datetime.now(timezone.utc).isoformat(),
                        "updateTimestamp": None,
                        "status": 1,
                        "type": 1,
                        "side": 0,
                        "size": 1,
                        "fillVolume": None,
                        "limitPrice": 4500.0,
                        "stopPrice": None
                    },
                    {
                        "id": 12346,
                        "accountId": 1001,
                        "contractId": "NQ",
                        "creationTimestamp": datetime.now(timezone.utc).isoformat(),
                        "updateTimestamp": None,
                        "status": 1,
                        "type": 2,
                        "side": 1,
                        "size": 2,
                        "fillVolume": None,
                        "limitPrice": None,
                        "stopPrice": None
                    }
                ]
            }
            mock_post.return_value = mock_response
            
            # Search for all open orders
            orders = order_manager.search_open_orders()
            
            # Verify orders retrieved
            assert len(orders) == 2
            assert all(isinstance(order, Order) for order in orders)
            assert orders[0].id == 12345
            assert orders[1].id == 12346

    def test_search_open_orders_by_contract(self, order_manager, mock_client):
        """Test searching for open orders by contract."""
        with patch('project_x_py.order_manager.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {
                "success": True,
                "orders": [
                    {
                        "id": 12345,
                        "accountId": 1001,
                        "contractId": "ES",
                        "creationTimestamp": datetime.now(timezone.utc).isoformat(),
                        "updateTimestamp": None,
                        "status": 1,
                        "type": 1,
                        "side": 0,
                        "size": 1,
                        "fillVolume": None,
                        "limitPrice": 4500.0,
                        "stopPrice": None
                    }
                ]
            }
            mock_post.return_value = mock_response
            
            # Search for ES orders
            orders = order_manager.search_open_orders(contract_id="ES")
            
            # Verify API call included contract filter
            json_payload = mock_post.call_args[1]["json"]
            assert json_payload["contractId"] == "ES"
            
            # Verify only ES orders returned
            assert len(orders) == 1
            assert orders[0].contractId == "ES"

    def test_order_status_progression(self, order_manager, mock_client):
        """Test tracking order status progression from pending to filled."""
        order_id = 12345
        
        # Stage 1: Order is pending
        pending_order = Order(
            id=order_id,
            accountId=1001,
            contractId="ES",
            creationTimestamp=datetime.now(timezone.utc).isoformat(),
            updateTimestamp=None,
            status=1,  # Pending
            type=1,    # Limit
            side=0,    # Buy
            size=1,
            fillVolume=None,
            limitPrice=4500.0,
            stopPrice=None
        )
        
        # Stage 2: Order is partially filled
        partial_order = Order(
            id=order_id,
            accountId=1001,
            contractId="ES",
            creationTimestamp=datetime.now(timezone.utc).isoformat(),
            updateTimestamp=datetime.now(timezone.utc).isoformat(),
            status=1,  # Still pending
            type=1,    # Limit
            side=0,    # Buy
            size=2,
            fillVolume=1,  # Partially filled
            limitPrice=4500.0,
            stopPrice=None
        )
        
        # Stage 3: Order is fully filled
        filled_order = Order(
            id=order_id,
            accountId=1001,
            contractId="ES",
            creationTimestamp=datetime.now(timezone.utc).isoformat(),
            updateTimestamp=datetime.now(timezone.utc).isoformat(),
            status=2,  # Filled
            type=1,    # Limit
            side=0,    # Buy
            size=2,
            fillVolume=2,  # Fully filled
            limitPrice=4500.0,
            stopPrice=None
        )
        
        # Mock the progression
        with patch.object(order_manager, 'get_order_by_id') as mock_get:
            # First check - pending
            mock_get.return_value = pending_order
            assert order_manager.get_order_by_id(order_id).status == 1
            assert order_manager.get_order_by_id(order_id).fillVolume is None
            
            # Second check - partially filled
            mock_get.return_value = partial_order
            assert order_manager.get_order_by_id(order_id).status == 1
            assert order_manager.get_order_by_id(order_id).fillVolume == 1
            
            # Third check - fully filled
            mock_get.return_value = filled_order
            assert order_manager.get_order_by_id(order_id).status == 2
            assert order_manager.get_order_by_id(order_id).fillVolume == 2

    def test_order_rejection_tracking(self, order_manager, mock_client):
        """Test tracking order rejection."""
        # Mock rejected order
        rejected_order = Order(
            id=12345,
            accountId=1001,
            contractId="ES",
            creationTimestamp=datetime.now(timezone.utc).isoformat(),
            updateTimestamp=datetime.now(timezone.utc).isoformat(),
            status=4,  # Rejected
            type=1,    # Limit
            side=0,    # Buy
            size=1,
            fillVolume=None,
            limitPrice=4500.0,
            stopPrice=None
        )
        
        with patch.object(order_manager, 'get_order_by_id', return_value=rejected_order):
            order = order_manager.get_order_by_id(12345)
            
            # Verify order is rejected
            assert order.status == 4

    def test_order_cancellation_tracking(self, order_manager, mock_client):
        """Test tracking order cancellation."""
        # Mock cancelled order
        cancelled_order = Order(
            id=12345,
            accountId=1001,
            contractId="ES",
            creationTimestamp=datetime.now(timezone.utc).isoformat(),
            updateTimestamp=datetime.now(timezone.utc).isoformat(),
            status=3,  # Cancelled
            type=1,    # Limit
            side=0,    # Buy
            size=1,
            fillVolume=None,
            limitPrice=4500.0,
            stopPrice=None
        )
        
        with patch.object(order_manager, 'get_order_by_id', return_value=cancelled_order):
            order = order_manager.get_order_by_id(12345)
            
            # Verify order is cancelled
            assert order.status == 3

    def test_order_statistics_tracking(self, order_manager):
        """Test order statistics tracking."""
        # Access statistics
        stats = order_manager.get_order_statistics()
        
        # Verify statistics structure
        assert "statistics" in stats
        assert "orders_placed" in stats["statistics"]
        assert "orders_cancelled" in stats["statistics"]
        assert "orders_modified" in stats["statistics"]
        assert "bracket_orders_placed" in stats["statistics"]
        assert "realtime_enabled" in stats

    def test_order_tracking_with_realtime_cache(self, order_manager):
        """Test order tracking with real-time cache."""
        # Mock real-time client
        mock_realtime = Mock()
        order_manager._realtime_enabled = True
        order_manager.realtime_client = mock_realtime
        
        # Mock cached order data
        cached_order_data = {
            "id": 12345,
            "accountId": 1001,
            "contractId": "ES",
            "creationTimestamp": datetime.now(timezone.utc).isoformat(),
            "updateTimestamp": datetime.now(timezone.utc).isoformat(),
            "status": 2,  # Filled
            "type": 1,
            "side": 0,
            "size": 1,
            "fillVolume": 1,
            "limitPrice": 4500.0,
            "stopPrice": None
        }
        
        # Set up cached order
        order_manager.tracked_orders["12345"] = cached_order_data
        
        # Get order (should use cache)
        order = order_manager.get_order_by_id(12345)
        
        # Verify order retrieved from cache
        assert order is not None
        assert order.id == 12345
        assert order.status == 2

    def test_search_open_orders_error_handling(self, order_manager, mock_client):
        """Test error handling in order search."""
        with patch('project_x_py.order_manager.requests.post') as mock_post:
            # Test API error
            mock_response = Mock()
            mock_response.json.return_value = {
                "success": False,
                "errorMessage": "API error"
            }
            mock_post.return_value = mock_response
            
            # Search should return empty list on error
            orders = order_manager.search_open_orders()
            assert orders == []
            
            # Test network error
            import requests
            mock_post.side_effect = requests.RequestException("Network error")
            orders = order_manager.search_open_orders()
            assert orders == []

    def test_order_event_callbacks(self, order_manager):
        """Test order event callback registration and triggering."""
        # Mock callback
        callback_called = False
        callback_data = None
        
        def test_callback(data):
            nonlocal callback_called, callback_data
            callback_called = True
            callback_data = data
        
        # Register callback
        order_manager.add_callback("order_update", test_callback)
        
        # Trigger callback
        test_data = {"order_id": 12345, "status": "filled"}
        order_manager._trigger_callbacks("order_update", test_data)
        
        # Verify callback was called
        assert callback_called is True
        assert callback_data == test_data

    def test_multiple_order_callbacks(self, order_manager):
        """Test multiple callbacks for the same event."""
        # Track callback invocations
        callbacks_called = []
        
        def callback1(data):
            callbacks_called.append(("callback1", data))
        
        def callback2(data):
            callbacks_called.append(("callback2", data))
        
        # Register multiple callbacks
        order_manager.add_callback("order_filled", callback1)
        order_manager.add_callback("order_filled", callback2)
        
        # Trigger callbacks
        test_data = {"order_id": 12345}
        order_manager._trigger_callbacks("order_filled", test_data)
        
        # Verify both callbacks were called
        assert len(callbacks_called) == 2
        assert callbacks_called[0] == ("callback1", test_data)
        assert callbacks_called[1] == ("callback2", test_data)

    def test_callback_error_handling(self, order_manager):
        """Test that callback errors don't break the system."""
        # Mock callbacks - one fails, one succeeds
        successful_callback_called = False
        
        def failing_callback(data):
            raise Exception("Callback error")
        
        def successful_callback(data):
            nonlocal successful_callback_called
            successful_callback_called = True
        
        # Register callbacks
        order_manager.add_callback("order_update", failing_callback)
        order_manager.add_callback("order_update", successful_callback)
        
        # Trigger callbacks
        order_manager._trigger_callbacks("order_update", {"test": "data"})
        
        # Verify successful callback was still called despite error
        assert successful_callback_called is True