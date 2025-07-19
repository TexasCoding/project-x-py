"""
Test suite for Integration Testing - End-to-End Workflows
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import time
import polars as pl
from project_x_py import ProjectX
from project_x_py.order_manager import OrderManager, create_order_manager
from project_x_py.position_manager import PositionManager, create_position_manager
from project_x_py.realtime_data_manager import ProjectXRealtimeDataManager
from project_x_py.realtime import ProjectXRealtimeClient
from project_x_py.utils import create_trading_suite
from project_x_py.models import Order, Position, Instrument, Fill
from project_x_py.exceptions import ProjectXError


class TestEndToEndWorkflows:
    """Test cases for complete trading workflows"""
    
    @patch('project_x_py.realtime.ProjectXRealtimeClient')
    def test_complete_trading_workflow(self, mock_realtime_class):
        """Test complete trading workflow from authentication to order execution"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        mock_client._jwt_token = "test_token"
        mock_client._account_id = "test_account"
        
        # Mock authentication
        mock_client.authenticate.return_value = True
        
        # Mock instrument data
        mock_instrument = Instrument(
            id="CON.F.US.MGC.M25",
            name="MGCH25",
            tickSize=0.1,
            tickValue=10.0
        )
        mock_client.get_instrument.return_value = mock_instrument
        mock_client.get_current_price.return_value = 2045.0
        
        # Mock order placement
        mock_client._make_request.return_value = {
            "orderId": "12345",
            "status": "Submitted"
        }
        
        # Act
        # 1. Initialize managers
        order_manager = create_order_manager(mock_client)
        position_manager = create_position_manager(mock_client)
        
        # 2. Place a test order
        response = order_manager.place_limit_order(
            "MGC", side=0, size=1, price=2040.0  # Buy limit below market
        )
        
        # 3. Check order status
        mock_order = Order(
            id="12345",
            contract_id="CON.F.US.MGC.M25",
            side=0,
            size=1,
            price=2040.0,
            status="Open"
        )
        mock_client.search_open_orders.return_value = [mock_order]
        orders = order_manager.search_open_orders()
        
        # 4. Cancel the order
        mock_client._make_request.return_value = {"success": True}
        cancel_result = order_manager.cancel_order("12345")
        
        # Assert
        assert response.success is True
        assert response.order_id == "12345"
        assert len(orders) == 1
        assert orders[0].id == "12345"
        assert cancel_result is True
    
    @patch('project_x_py.realtime.ProjectXRealtimeClient')
    def test_position_lifecycle_workflow(self, mock_realtime_class):
        """Test complete position lifecycle from open to close"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        mock_instrument = Instrument(
            id="CON.F.US.MGC.M25",
            tickSize=0.1,
            tickValue=10.0
        )
        mock_client.get_instrument.return_value = mock_instrument
        mock_client.get_current_price.return_value = 2045.0
        
        order_manager = OrderManager(mock_client)
        position_manager = PositionManager(mock_client)
        
        order_manager.initialize()
        position_manager.initialize()
        
        # Act
        # 1. Open position with market order
        mock_client._make_request.return_value = {
            "orderId": "entry_order",
            "status": "Filled",
            "fillPrice": 2045.0
        }
        entry_response = order_manager.place_market_order("MGC", side=0, size=2)
        
        # 2. Simulate position creation
        mock_position = Position(
            contract_id="CON.F.US.MGC.M25",
            instrument="MGC",
            side=0,
            quantity=2,
            average_price=2045.0,
            unrealized_pnl=0.0
        )
        mock_client.search_open_positions.return_value = [mock_position]
        
        # 3. Add stop loss
        mock_client._make_request.return_value = {
            "orderId": "stop_order",
            "status": "Submitted"
        }
        stop_response = order_manager.add_stop_loss("MGC", 2040.0)
        
        # 4. Check position P&L (price moved up)
        mock_client.get_current_price.return_value = 2048.0
        position_manager._positions["MGC"] = mock_position
        mock_position.unrealized_pnl = 60.0  # 2 contracts * 30 ticks * $10
        
        pnl = position_manager.calculate_position_pnl("MGC")
        
        # 5. Close position
        mock_client._make_request.return_value = {
            "orderId": "close_order",
            "status": "Filled"
        }
        close_response = order_manager.close_position("MGC")
        
        # Assert
        assert entry_response.success is True
        assert stop_response.success is True
        assert pnl["unrealized_pnl"] == 60.0
        assert close_response.success is True
    
    def test_multi_timeframe_analysis_workflow(self):
        """Test multi-timeframe data analysis workflow"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        
        # Mock historical data for different timeframes
        def mock_get_data(instrument, days=None, interval=None, **kwargs):
            base_price = 2045.0
            num_bars = 100
            
            data = pl.DataFrame({
                "timestamp": [datetime.now() - timedelta(minutes=i*interval) for i in range(num_bars)],
                "open": [base_price + (i % 5) for i in range(num_bars)],
                "high": [base_price + (i % 5) + 1 for i in range(num_bars)],
                "low": [base_price + (i % 5) - 1 for i in range(num_bars)],
                "close": [base_price + (i % 5) + 0.5 for i in range(num_bars)],
                "volume": [100 + (i * 10) for i in range(num_bars)]
            })
            return data
        
        mock_client.get_data.side_effect = mock_get_data
        mock_client._jwt_token = "test_token"
        
        # Act
        # 1. Initialize data manager
        data_manager = ProjectXRealtimeDataManager("MGC", mock_client, "test_account")
        data_manager.initialize(timeframes=["5min", "15min", "1hour"])
        
        # 2. Get multi-timeframe data
        mtf_data = data_manager.get_mtf_data()
        
        # 3. Analyze each timeframe
        analysis_results = {}
        for timeframe, data in mtf_data.items():
            if len(data) > 0:
                analysis_results[timeframe] = {
                    "trend": "up" if data["close"][-1] > data["close"][0] else "down",
                    "volatility": data["close"].std(),
                    "volume_trend": "increasing" if data["volume"][-1] > data["volume"][0] else "decreasing"
                }
        
        # Assert
        assert len(mtf_data) == 3
        assert all(tf in mtf_data for tf in ["5min", "15min", "1hour"])
        assert len(analysis_results) > 0
        assert all("trend" in result for result in analysis_results.values())
    
    def test_risk_management_workflow(self):
        """Test risk management integration across order and position managers"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        mock_client.get_account_balance.return_value = 10000.0
        
        mock_instrument = Instrument(
            id="CON.F.US.MGC.M25",
            tickSize=0.1,
            tickValue=10.0,
            marginRequirement=500.0
        )
        mock_client.get_instrument.return_value = mock_instrument
        
        # Mock existing positions using all available margin
        mock_positions = [
            Position(
                contract_id="CON.F.US.MGC.M25",
                instrument="MGC",
                side=0,
                quantity=18,  # 18 * $500 = $9000 margin
                margin_requirement=9000.0
            )
        ]
        mock_client.search_open_positions.return_value = mock_positions
        
        order_manager = OrderManager(mock_client)
        position_manager = PositionManager(mock_client)
        
        order_manager.initialize()
        position_manager.initialize()
        
        # Act & Assert
        # 1. Calculate available margin
        risk_metrics = position_manager.get_risk_metrics()
        assert risk_metrics["free_margin"] == 1000.0  # $10k - $9k
        
        # 2. Try to place order requiring more margin than available
        # This should be rejected by risk management
        with pytest.raises(ProjectXError):  # Should raise risk error
            order_manager.place_market_order("MGC", side=0, size=3)  # Needs $1500
    
    @patch('project_x_py.realtime.SIGNALR_AVAILABLE', True)
    @patch('project_x_py.realtime.HubConnectionBuilder')
    def test_realtime_data_integration(self, mock_hub_builder):
        """Test real-time data integration workflow"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        mock_client._jwt_token = "test_token"
        mock_client._account_id = "test_account"
        
        # Mock SignalR connection
        mock_connection = Mock()
        mock_connection.build.return_value = mock_connection
        mock_connection.start.return_value = True
        mock_hub_builder.return_value = mock_connection
        
        # Act
        # 1. Create trading suite with real-time components
        suite = create_trading_suite(
            "MGC", mock_client, "test_token", "test_account"
        )
        
        # 2. Initialize components
        suite["order_manager"].initialize(realtime_client=suite["realtime_client"])
        suite["position_manager"].initialize(realtime_client=suite["realtime_client"])
        
        # Mock historical data loading
        mock_client.get_data.return_value = pl.DataFrame({
            "timestamp": [datetime.now()],
            "open": [2045.0],
            "high": [2046.0],
            "low": [2044.0],
            "close": [2045.5],
            "volume": [100]
        })
        
        suite["data_manager"].initialize()
        
        # 3. Connect real-time client
        connected = suite["realtime_client"].connect()
        
        # Assert
        assert connected is True
        assert suite["order_manager"]._realtime_enabled is True
        assert suite["position_manager"]._realtime_enabled is True
        assert "orderbook" in suite
        
        # Verify all components are properly connected
        assert suite["realtime_client"] is not None
        assert suite["data_manager"] is not None
        assert suite["order_manager"] is not None
        assert suite["position_manager"] is not None
    
    def test_error_recovery_workflow(self):
        """Test error recovery and retry mechanisms"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        order_manager = OrderManager(mock_client)
        order_manager.initialize()
        
        # Simulate intermittent failures
        call_count = 0
        
        def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            
            if call_count < 3:
                # Fail first 2 attempts
                raise ProjectXConnectionError("Network timeout")
            else:
                # Succeed on 3rd attempt
                return {"orderId": "12345", "status": "Submitted"}
        
        mock_client._make_request.side_effect = mock_request
        mock_client.get_instrument.return_value = Instrument(
            id="CON.F.US.MGC.M25",
            tickSize=0.1,
            tickValue=10.0
        )
        
        # Act
        # Should retry and eventually succeed
        response = order_manager.place_limit_order("MGC", 0, 1, 2045.0)
        
        # Assert
        assert call_count == 3  # Failed twice, succeeded on third
        assert response.success is True
        assert response.order_id == "12345"