"""Test order modification and cancellation functionality."""
import pytest
from unittest.mock import Mock, patch, call
from datetime import datetime, timezone
from decimal import Decimal

from project_x_py import ProjectX
from project_x_py.order_manager import OrderManager
from project_x_py.models import Order, Position, Instrument, OrderPlaceResponse, Account
from project_x_py.exceptions import (
    ProjectXError,
    ProjectXConnectionError,
    ProjectXOrderError
)


class TestOrderModification:
    """Test suite for order modification and cancellation functionality."""

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

    @pytest.fixture
    def mock_order(self):
        """Create a mock order for testing."""
        return Order(
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

    def test_modify_order_price(self, order_manager, mock_client, mock_order):
        """Test modifying order price."""
        # Mock instrument for price alignment
        instrument = Instrument(
            id="ES",
            name="ES",
            description="E-mini S&P 500 Futures",
            tickSize=0.25,
            tickValue=12.50,
            activeContract=True
        )
        mock_client.get_instrument = Mock(return_value=instrument)
        
        with patch.object(order_manager, 'get_order_by_id', return_value=mock_order):
            with patch('project_x_py.order_manager.requests.post') as mock_post:
                mock_response = Mock()
                mock_response.json.return_value = {
                    "success": True
                }
                mock_post.return_value = mock_response
                
                # Modify order price
                result = order_manager.modify_order(
                    order_id=12345,
                    limit_price=4502.75
                )
                
                # Verify modification success
                assert result is True
                
                # Verify API call
                mock_post.assert_called_once()
                assert "/Order/modify" in mock_post.call_args[0][0]
                json_payload = mock_post.call_args[1]["json"]
                assert json_payload["orderId"] == 12345
                assert json_payload["limitPrice"] == 4502.75

    def test_modify_order_size(self, order_manager, mock_client, mock_order):
        """Test modifying order size."""
        with patch.object(order_manager, 'get_order_by_id', return_value=mock_order):
            with patch('project_x_py.order_manager.requests.post') as mock_post:
                mock_response = Mock()
                mock_response.json.return_value = {
                    "success": True
                }
                mock_post.return_value = mock_response
                
                # Modify order size
                result = order_manager.modify_order(
                    order_id=12345,
                    size=3
                )
                
                # Verify modification success
                assert result is True
                
                # Verify API call
                json_payload = mock_post.call_args[1]["json"]
                assert json_payload["orderId"] == 12345
                assert json_payload["size"] == 3
                assert "limitPrice" not in json_payload  # Only size was modified

    def test_modify_stop_order_price(self, order_manager, mock_client):
        """Test modifying stop order price."""
        # Create a stop order
        stop_order = Order(
            id=12346,
            accountId=1001,
            contractId="ES",
            creationTimestamp=datetime.now(timezone.utc).isoformat(),
            updateTimestamp=None,
            status=1,  # Pending
            type=4,    # Stop
            side=1,    # Sell
            size=1,
            fillVolume=None,
            limitPrice=None,
            stopPrice=4490.0
        )
        
        # Mock instrument
        instrument = Instrument(
            id="ES",
            name="ES",
            description="E-mini S&P 500 Futures",
            tickSize=0.25,
            tickValue=12.50,
            activeContract=True
        )
        mock_client.get_instrument = Mock(return_value=instrument)
        
        with patch.object(order_manager, 'get_order_by_id', return_value=stop_order):
            with patch('project_x_py.order_manager.requests.post') as mock_post:
                mock_response = Mock()
                mock_response.json.return_value = {
                    "success": True
                }
                mock_post.return_value = mock_response
                
                # Modify stop price
                result = order_manager.modify_order(
                    order_id=12346,
                    stop_price=4485.0
                )
                
                # Verify modification success
                assert result is True
                
                # Verify API call
                json_payload = mock_post.call_args[1]["json"]
                assert json_payload["orderId"] == 12346
                assert json_payload["stopPrice"] == 4485.0

    def test_modify_order_multiple_parameters(self, order_manager, mock_client, mock_order):
        """Test modifying multiple order parameters at once."""
        # Mock instrument
        instrument = Instrument(
            id="ES",
            name="ES",
            description="E-mini S&P 500 Futures",
            tickSize=0.25,
            tickValue=12.50,
            activeContract=True
        )
        mock_client.get_instrument = Mock(return_value=instrument)
        
        with patch.object(order_manager, 'get_order_by_id', return_value=mock_order):
            with patch('project_x_py.order_manager.requests.post') as mock_post:
                mock_response = Mock()
                mock_response.json.return_value = {
                    "success": True
                }
                mock_post.return_value = mock_response
                
                # Modify both price and size
                result = order_manager.modify_order(
                    order_id=12345,
                    limit_price=4505.0,
                    size=2
                )
                
                # Verify modification success
                assert result is True
                
                # Verify both parameters were sent
                json_payload = mock_post.call_args[1]["json"]
                assert json_payload["orderId"] == 12345
                assert json_payload["limitPrice"] == 4505.0
                assert json_payload["size"] == 2

    def test_modify_filled_order(self, order_manager, mock_client):
        """Test that modifying a filled order fails."""
        # Create a filled order
        filled_order = Order(
            id=12347,
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
            with patch('project_x_py.order_manager.requests.post') as mock_post:
                mock_response = Mock()
                mock_response.json.return_value = {
                    "success": False,
                    "errorMessage": "Cannot modify filled order"
                }
                mock_post.return_value = mock_response
                
                # Attempt to modify filled order
                result = order_manager.modify_order(
                    order_id=12347,
                    limit_price=4505.0
                )
                
                # Verify modification failed
                assert result is False

    def test_modify_cancelled_order(self, order_manager, mock_client):
        """Test that modifying a cancelled order fails."""
        # Create a cancelled order
        cancelled_order = Order(
            id=12348,
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
            with patch('project_x_py.order_manager.requests.post') as mock_post:
                mock_response = Mock()
                mock_response.json.return_value = {
                    "success": False,
                    "errorMessage": "Cannot modify cancelled order"
                }
                mock_post.return_value = mock_response
                
                # Attempt to modify cancelled order
                result = order_manager.modify_order(
                    order_id=12348,
                    size=2
                )
                
                # Verify modification failed
                assert result is False

    def test_modify_nonexistent_order(self, order_manager):
        """Test modifying a non-existent order."""
        with patch.object(order_manager, 'get_order_by_id', return_value=None):
            # Attempt to modify non-existent order
            result = order_manager.modify_order(
                order_id=99999,
                limit_price=4505.0
            )
            
            # Verify modification failed
            assert result is False

    def test_modify_order_network_error(self, order_manager, mock_client, mock_order):
        """Test handling network errors during order modification."""
        import requests
        
        with patch.object(order_manager, 'get_order_by_id', return_value=mock_order):
            with patch('project_x_py.order_manager.requests.post') as mock_post:
                mock_post.side_effect = requests.RequestException("Network error")
                
                # Attempt to modify order with network error
                result = order_manager.modify_order(
                    order_id=12345,
                    limit_price=4505.0
                )
                
                # Verify modification failed
                assert result is False

    def test_cancel_single_order(self, order_manager, mock_client):
        """Test cancelling a single order."""
        with patch('project_x_py.order_manager.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {
                "success": True
            }
            mock_post.return_value = mock_response
            
            # Cancel order
            result = order_manager.cancel_order(order_id=12345)
            
            # Verify cancellation success
            assert result is True
            
            # Verify API call
            mock_post.assert_called_once()
            assert "/Order/cancel" in mock_post.call_args[0][0]
            json_payload = mock_post.call_args[1]["json"]
            assert json_payload["orderId"] == 12345
            assert json_payload["accountId"] == 1001

    def test_cancel_order_with_specific_account(self, order_manager, mock_client):
        """Test cancelling an order for a specific account."""
        with patch('project_x_py.order_manager.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {
                "success": True
            }
            mock_post.return_value = mock_response
            
            # Cancel order for specific account
            result = order_manager.cancel_order(order_id=12345, account_id=1002)
            
            # Verify cancellation success
            assert result is True
            
            # Verify correct account ID was used
            json_payload = mock_post.call_args[1]["json"]
            assert json_payload["accountId"] == 1002

    def test_cancel_filled_order(self, order_manager, mock_client):
        """Test that cancelling a filled order fails."""
        with patch('project_x_py.order_manager.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {
                "success": False,
                "errorMessage": "Cannot cancel filled order"
            }
            mock_post.return_value = mock_response
            
            # Attempt to cancel filled order
            result = order_manager.cancel_order(order_id=12347)
            
            # Verify cancellation failed
            assert result is False

    def test_cancel_already_cancelled_order(self, order_manager, mock_client):
        """Test cancelling an already cancelled order."""
        with patch('project_x_py.order_manager.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {
                "success": False,
                "errorMessage": "Order already cancelled"
            }
            mock_post.return_value = mock_response
            
            # Attempt to cancel already cancelled order
            result = order_manager.cancel_order(order_id=12348)
            
            # Verify cancellation failed
            assert result is False

    def test_cancel_all_orders(self, order_manager, mock_client):
        """Test cancelling all open orders."""
        # Mock open orders
        open_orders = [
            Order(
                id=12345,
                accountId=1001,
                contractId="ES",
                creationTimestamp=datetime.now(timezone.utc).isoformat(),
                updateTimestamp=None,
                status=1,
                type=1,
                side=0,
                size=1,
                fillVolume=None,
                limitPrice=4500.0,
                stopPrice=None
            ),
            Order(
                id=12346,
                accountId=1001,
                contractId="NQ",
                creationTimestamp=datetime.now(timezone.utc).isoformat(),
                updateTimestamp=None,
                status=1,
                type=2,
                side=1,
                size=2,
                fillVolume=None,
                limitPrice=None,
                stopPrice=None
            ),
            Order(
                id=12347,
                accountId=1001,
                contractId="ES",
                creationTimestamp=datetime.now(timezone.utc).isoformat(),
                updateTimestamp=None,
                status=1,
                type=4,
                side=1,
                size=1,
                fillVolume=None,
                limitPrice=None,
                stopPrice=4490.0
            )
        ]
        
        with patch.object(order_manager, 'search_open_orders', return_value=open_orders):
            with patch('project_x_py.order_manager.requests.post') as mock_post:
                # Mock successful cancellations
                mock_response = Mock()
                mock_response.json.return_value = {"success": True}
                mock_post.return_value = mock_response
                
                # Cancel all orders
                results = order_manager.cancel_all_orders()
                
                # Verify results
                assert results["total_orders"] == 3
                assert results["cancelled"] == 3
                assert results["failed"] == 0
                assert len(results["errors"]) == 0
                
                # Verify each order was cancelled
                assert mock_post.call_count == 3
                call_order_ids = [
                    call.kwargs["json"]["orderId"] if "json" in call.kwargs else call[1]["json"]["orderId"]
                    for call in mock_post.call_args_list
                ]
                assert 12345 in call_order_ids
                assert 12346 in call_order_ids
                assert 12347 in call_order_ids

    def test_cancel_all_orders_by_contract(self, order_manager, mock_client):
        """Test cancelling all orders for a specific contract."""
        # Mock ES orders only
        es_orders = [
            Order(
                id=12345,
                accountId=1001,
                contractId="ES",
                creationTimestamp=datetime.now(timezone.utc).isoformat(),
                updateTimestamp=None,
                status=1,
                type=1,
                side=0,
                size=1,
                fillVolume=None,
                limitPrice=4500.0,
                stopPrice=None
            ),
            Order(
                id=12347,
                accountId=1001,
                contractId="ES",
                creationTimestamp=datetime.now(timezone.utc).isoformat(),
                updateTimestamp=None,
                status=1,
                type=4,
                side=1,
                size=1,
                fillVolume=None,
                limitPrice=None,
                stopPrice=4490.0
            )
        ]
        
        with patch.object(order_manager, 'search_open_orders', return_value=es_orders) as mock_search:
            with patch('project_x_py.order_manager.requests.post') as mock_post:
                # Mock successful cancellations
                mock_response = Mock()
                mock_response.json.return_value = {"success": True}
                mock_post.return_value = mock_response
                
                # Cancel all ES orders
                results = order_manager.cancel_all_orders(contract_id="ES")
                
                # Verify search was filtered
                mock_search.assert_called_once_with(contract_id="ES", account_id=None)
                
                # Verify results
                assert results["total_orders"] == 2
                assert results["cancelled"] == 2
                assert results["failed"] == 0

    def test_cancel_all_orders_partial_failure(self, order_manager, mock_client):
        """Test cancelling all orders with some failures."""
        # Mock open orders
        open_orders = [
            Order(
                id=12345,
                accountId=1001,
                contractId="ES",
                creationTimestamp=datetime.now(timezone.utc).isoformat(),
                updateTimestamp=None,
                status=1,
                type=1,
                side=0,
                size=1,
                fillVolume=None,
                limitPrice=4500.0,
                stopPrice=None
            ),
            Order(
                id=12346,
                accountId=1001,
                contractId="NQ",
                creationTimestamp=datetime.now(timezone.utc).isoformat(),
                updateTimestamp=None,
                status=1,
                type=2,
                side=1,
                size=2,
                fillVolume=None,
                limitPrice=None,
                stopPrice=None
            )
        ]
        
        with patch.object(order_manager, 'search_open_orders', return_value=open_orders):
            with patch('project_x_py.order_manager.requests.post') as mock_post:
                # Mock mixed results - first succeeds, second fails
                mock_responses = [
                    Mock(json=lambda: {"success": True}),
                    Mock(json=lambda: {"success": False, "errorMessage": "Order already filled"})
                ]
                mock_post.side_effect = mock_responses
                
                # Cancel all orders
                results = order_manager.cancel_all_orders()
                
                # Verify mixed results
                assert results["total_orders"] == 2
                assert results["cancelled"] == 1
                assert results["failed"] == 1

    def test_cancel_order_network_error(self, order_manager, mock_client):
        """Test handling network errors during order cancellation."""
        import requests
        
        with patch('project_x_py.order_manager.requests.post') as mock_post:
            mock_post.side_effect = requests.RequestException("Network error")
            
            # Attempt to cancel order with network error
            result = order_manager.cancel_order(order_id=12345)
            
            # Verify cancellation failed
            assert result is False

    def test_concurrent_modification_handling(self, order_manager, mock_client, mock_order):
        """Test handling concurrent modification attempts."""
        # Mock instrument
        instrument = Instrument(
            id="ES",
            name="ES",
            description="E-mini S&P 500 Futures",
            tickSize=0.25,
            tickValue=12.50,
            activeContract=True
        )
        mock_client.get_instrument = Mock(return_value=instrument)
        
        with patch.object(order_manager, 'get_order_by_id', return_value=mock_order):
            with patch('project_x_py.order_manager.requests.post') as mock_post:
                mock_response = Mock()
                mock_response.json.return_value = {
                    "success": False,
                    "errorMessage": "Order is being modified by another request"
                }
                mock_post.return_value = mock_response
                
                # Attempt concurrent modification
                result = order_manager.modify_order(
                    order_id=12345,
                    limit_price=4505.0
                )
                
                # Verify modification failed due to concurrent access
                assert result is False