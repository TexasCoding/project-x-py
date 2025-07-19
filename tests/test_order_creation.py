"""Test order creation and submission functionality."""
import pytest
from unittest.mock import Mock, patch, MagicMock
import polars as pl
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


class TestOrderCreation:
    """Test suite for order creation functionality."""

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

    def test_market_order_creation(self, order_manager, mock_client):
        """Test creating a market order."""
        # Mock instrument data
        instrument = Instrument(
            id="MGC",
            name="MGC",
            description="Micro Gold Futures",
            tickSize=0.1,
            tickValue=10.0,
            activeContract=True
        )
        mock_client.get_instrument = Mock(return_value=instrument)
        
        # Mock successful order response
        with patch('project_x_py.order_manager.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {
                "success": True,
                "orderId": 12345,
                "errorCode": 0,
                "errorMessage": None
            }
            mock_post.return_value = mock_response
            
            # Create market order
            response = order_manager.place_market_order(
                contract_id="MGC",
                side=0,  # Buy
                size=1
            )
            
            # Verify order creation response
            assert response is not None
            assert response.orderId == 12345
            assert response.success is True
            assert response.errorCode == 0
            
            # Verify API call
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert "/Order/place" in call_args[0][0]
            
            # Check request payload
            json_payload = call_args[1]["json"]
            assert json_payload["contractId"] == "MGC"
            assert json_payload["side"] == 0
            assert json_payload["size"] == 1
            assert json_payload["type"] == 2  # Market order

    def test_limit_order_creation(self, order_manager, mock_client):
        """Test creating a limit order."""
        # Mock instrument data
        instrument = Instrument(
            id="ES",
            name="ES",
            description="E-mini S&P 500 Futures",
            tickSize=0.25,
            tickValue=12.50,
            activeContract=True
        )
        mock_client.get_instrument = Mock(return_value=instrument)
        
        # Mock successful order response
        with patch('project_x_py.order_manager.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {
                "success": True,
                "orderId": 12346,
                "errorCode": 0,
                "errorMessage": None
            }
            mock_post.return_value = mock_response
            
            # Create limit order
            response = order_manager.place_limit_order(
                contract_id="ES",
                side=1,  # Sell
                size=2,
                limit_price=4500.50
            )
            
            # Verify order creation response
            assert response is not None
            assert response.orderId == 12346
            assert response.success is True
            
            # Verify API call
            mock_post.assert_called_once()
            json_payload = mock_post.call_args[1]["json"]
            assert json_payload["contractId"] == "ES"
            assert json_payload["side"] == 1
            assert json_payload["size"] == 2
            assert json_payload["type"] == 1  # Limit order
            assert json_payload["limitPrice"] == 4500.50

    def test_stop_order_creation(self, order_manager, mock_client):
        """Test creating a stop order."""
        # Mock instrument data
        instrument = Instrument(
            id="CL",
            name="CL",
            description="Crude Oil Futures",
            tickSize=0.01,
            tickValue=10.0,
            activeContract=True
        )
        mock_client.get_instrument = Mock(return_value=instrument)
        
        # Mock successful order response
        with patch('project_x_py.order_manager.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {
                "success": True,
                "orderId": 12347,
                "errorCode": 0,
                "errorMessage": None
            }
            mock_post.return_value = mock_response
            
            # Create stop order
            response = order_manager.place_stop_order(
                contract_id="CL",
                side=0,  # Buy
                size=1,
                stop_price=75.50
            )
            
            # Verify response
            assert response is not None
            assert response.orderId == 12347
            assert response.success is True
            
            # Verify API call
            json_payload = mock_post.call_args[1]["json"]
            assert json_payload["type"] == 4  # Stop order
            assert json_payload["stopPrice"] == 75.50

    def test_trailing_stop_order_creation(self, order_manager, mock_client):
        """Test creating a trailing stop order."""
        # Mock instrument data
        instrument = Instrument(
            id="GC",
            name="GC",
            description="Gold Futures",
            tickSize=0.1,
            tickValue=10.0,
            activeContract=True
        )
        mock_client.get_instrument = Mock(return_value=instrument)
        
        # Mock successful order response
        with patch('project_x_py.order_manager.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {
                "success": True,
                "orderId": 12348,
                "errorCode": 0,
                "errorMessage": None
            }
            mock_post.return_value = mock_response
            
            # Create trailing stop order
            response = order_manager.place_trailing_stop_order(
                contract_id="GC",
                side=1,  # Sell
                size=1,
                trail_price=5.0
            )
            
            # Verify response
            assert response is not None
            assert response.orderId == 12348
            assert response.success is True
            
            # Verify API call
            json_payload = mock_post.call_args[1]["json"]
            assert json_payload["type"] == 5  # Trailing stop order
            assert json_payload["trailPrice"] == 5.0

    def test_bracket_order_creation(self, order_manager, mock_client):
        """Test creating a bracket order (entry + stop loss + take profit)."""
        # Mock instrument data
        instrument = Instrument(
            id="NQ",
            name="NQ",
            description="E-mini Nasdaq-100 Futures",
            tickSize=0.25,
            tickValue=5.0,
            activeContract=True
        )
        mock_client.get_instrument = Mock(return_value=instrument)
        
        # Mock order submissions for bracket order
        with patch('project_x_py.order_manager.requests.post') as mock_post:
            # Mock responses for entry, stop, and target orders
            mock_responses = [
                Mock(json=lambda: {
                    "success": True,
                    "orderId": 12349,
                    "errorCode": 0,
                    "errorMessage": None
                }),  # Entry order
                Mock(json=lambda: {
                    "success": True,
                    "orderId": 12350,
                    "errorCode": 0,
                    "errorMessage": None
                }),  # Stop loss order
                Mock(json=lambda: {
                    "success": True,
                    "orderId": 12351,
                    "errorCode": 0,
                    "errorMessage": None
                })   # Take profit order
            ]
            mock_post.side_effect = mock_responses
            
            # Create bracket order
            result = order_manager.place_bracket_order(
                contract_id="NQ",
                side=0,  # Buy
                size=1,
                entry_price=15250.0,
                stop_loss_price=15000.0,
                take_profit_price=15500.0
            )
            
            # Verify bracket order creation
            assert result.success is True
            assert result.entry_order_id == 12349
            assert result.stop_order_id == 12350
            assert result.target_order_id == 12351
            assert result.entry_price == 15250.0
            assert result.stop_loss_price == 15000.0
            assert result.take_profit_price == 15500.0
            
            # Verify three API calls were made
            assert mock_post.call_count == 3

    def test_order_validation_price_alignment(self, order_manager, mock_client):
        """Test that order prices are aligned to tick size."""
        # Mock instrument with specific tick size
        instrument = Instrument(
            id="ES",
            name="ES",
            description="E-mini S&P 500 Futures",
            tickSize=0.25,
            tickValue=12.50,
            activeContract=True
        )
        mock_client.get_instrument = Mock(return_value=instrument)
        
        with patch('project_x_py.order_manager.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {
                "success": True,
                "orderId": 12352,
                "errorCode": 0,
                "errorMessage": None
            }
            mock_post.return_value = mock_response
            
            # Place order with price that needs alignment
            order_manager.place_limit_order(
                contract_id="ES",
                side=0,
                size=1,
                limit_price=4500.37  # Should be aligned to 4500.25 or 4500.50
            )
            
            # Check that price was aligned to tick size
            json_payload = mock_post.call_args[1]["json"]
            limit_price = json_payload["limitPrice"]
            assert limit_price % 0.25 == 0  # Should be divisible by tick size

    def test_order_submission_failure(self, order_manager, mock_client):
        """Test handling order submission failure."""
        # Mock instrument data
        instrument = Instrument(
            id="ES",
            name="ES",
            description="E-mini S&P 500 Futures",
            tickSize=0.25,
            tickValue=12.50,
            activeContract=True
        )
        mock_client.get_instrument = Mock(return_value=instrument)
        
        # Mock order submission failure
        with patch('project_x_py.order_manager.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {
                "success": False,
                "orderId": 0,
                "errorCode": 1,
                "errorMessage": "Market is closed"
            }
            mock_post.return_value = mock_response
            
            # Attempt to submit order
            with pytest.raises(ProjectXOrderError, match="Market is closed"):
                order_manager.place_market_order(
                    contract_id="ES",
                    side=0,
                    size=1
                )

    def test_order_timeout_handling(self, order_manager, mock_client):
        """Test handling order submission timeout."""
        # Mock instrument data
        instrument = Instrument(
            id="ES",
            name="ES",
            description="E-mini S&P 500 Futures",
            tickSize=0.25,
            tickValue=12.50,
            activeContract=True
        )
        mock_client.get_instrument = Mock(return_value=instrument)
        
        # Mock timeout
        import requests
        with patch('project_x_py.order_manager.requests.post') as mock_post:
            mock_post.side_effect = requests.RequestException("Request timeout")
            
            # Attempt to submit order
            with pytest.raises(ProjectXConnectionError):
                order_manager.place_market_order(
                    contract_id="ES",
                    side=0,
                    size=1
                )

    def test_cancel_order(self, order_manager, mock_client):
        """Test order cancellation."""
        with patch('project_x_py.order_manager.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {
                "success": True
            }
            mock_post.return_value = mock_response
            
            # Cancel order
            result = order_manager.cancel_order(order_id=12345)
            
            # Verify cancellation
            assert result is True
            
            # Verify API call
            mock_post.assert_called_once()
            assert "/Order/cancel" in mock_post.call_args[0][0]
            json_payload = mock_post.call_args[1]["json"]
            assert json_payload["orderId"] == 12345

    def test_modify_order(self, order_manager, mock_client):
        """Test order modification."""
        # Mock existing order
        existing_order = Order(
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
        
        with patch.object(order_manager, 'get_order_by_id', return_value=existing_order):
            with patch('project_x_py.order_manager.requests.post') as mock_post:
                mock_response = Mock()
                mock_response.json.return_value = {
                    "success": True
                }
                mock_post.return_value = mock_response
                
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
                
                # Modify order
                result = order_manager.modify_order(
                    order_id=12345,
                    limit_price=4502.0,
                    size=2
                )
                
                # Verify modification
                assert result is True
                
                # Verify API call
                json_payload = mock_post.call_args[1]["json"]
                assert json_payload["orderId"] == 12345
                assert json_payload["limitPrice"] == 4502.0
                assert json_payload["size"] == 2

    def test_search_open_orders(self, order_manager, mock_client):
        """Test searching for open orders."""
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
            
            # Search for open orders
            orders = order_manager.search_open_orders()
            
            # Verify results
            assert len(orders) == 2
            assert orders[0].id == 12345
            assert orders[0].contractId == "ES"
            assert orders[1].id == 12346
            assert orders[1].contractId == "NQ"

    def test_close_position(self, order_manager, mock_client):
        """Test closing a position."""
        # Mock position
        position = Position(
            id=1,
            accountId=1001,
            contractId="ES",
            creationTimestamp=datetime.now(timezone.utc).isoformat(),
            type=1,  # Long
            size=2,
            averagePrice=4500.0
        )
        
        mock_client.search_open_positions = Mock(return_value=[position])
        
        with patch('project_x_py.order_manager.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {
                "success": True,
                "orderId": 12347,
                "errorCode": 0,
                "errorMessage": None
            }
            mock_post.return_value = mock_response
            
            # Close position at market
            response = order_manager.close_position("ES", method="market")
            
            # Verify close order
            assert response is not None
            assert response.orderId == 12347
            
            # Verify order parameters
            json_payload = mock_post.call_args[1]["json"]
            assert json_payload["contractId"] == "ES"
            assert json_payload["side"] == 1  # Sell to close long
            assert json_payload["size"] == 2
            assert json_payload["type"] == 2  # Market order

    def test_add_stop_loss(self, order_manager, mock_client):
        """Test adding a stop loss to an existing position."""
        # Mock position
        position = Position(
            id=1,
            accountId=1001,
            contractId="ES",
            creationTimestamp=datetime.now(timezone.utc).isoformat(),
            type=1,  # Long
            size=1,
            averagePrice=4500.0
        )
        
        mock_client.search_open_positions = Mock(return_value=[position])
        
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
        
        with patch('project_x_py.order_manager.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {
                "success": True,
                "orderId": 12348,
                "errorCode": 0,
                "errorMessage": None
            }
            mock_post.return_value = mock_response
            
            # Add stop loss
            response = order_manager.add_stop_loss("ES", stop_price=4490.0)
            
            # Verify stop loss order
            assert response is not None
            assert response.orderId == 12348
            
            # Verify order parameters
            json_payload = mock_post.call_args[1]["json"]
            assert json_payload["contractId"] == "ES"
            assert json_payload["side"] == 1  # Sell stop for long position
            assert json_payload["size"] == 1
            assert json_payload["type"] == 4  # Stop order
            assert json_payload["stopPrice"] == 4490.0