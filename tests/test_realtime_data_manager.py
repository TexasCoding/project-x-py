"""
Test suite for Real-time Data Manager functionality
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import polars as pl
from project_x_py import ProjectX
from project_x_py.realtime_data_manager import ProjectXRealtimeDataManager
from project_x_py.realtime import ProjectXRealtimeClient
from project_x_py.exceptions import ProjectXError


class TestRealtimeDataManager:
    """Test cases for real-time data management functionality"""
    
    def test_basic_initialization(self):
        """Test basic data manager initialization"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        account_id = "test_account"
        
        # Act
        data_manager = ProjectXRealtimeDataManager("MGC", mock_client, account_id)
        
        # Assert
        assert data_manager.instrument == "MGC"
        assert data_manager.project_x == mock_client
        assert data_manager.account_id == account_id
        assert data_manager._data == {}
        assert data_manager._current_price is None
        assert data_manager._realtime_client is None
    
    def test_historical_data_loading(self):
        """Test loading historical data on initialization"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        
        # Mock historical data for different timeframes
        mock_data_5min = pl.DataFrame({
            "timestamp": [datetime.now() - timedelta(minutes=i*5) for i in range(10)],
            "open": [2045.0 + i for i in range(10)],
            "high": [2046.0 + i for i in range(10)],
            "low": [2044.0 + i for i in range(10)],
            "close": [2045.5 + i for i in range(10)],
            "volume": [100 + i*10 for i in range(10)]
        })
        
        mock_client.get_data.return_value = mock_data_5min
        
        data_manager = ProjectXRealtimeDataManager("MGC", mock_client, "test_account")
        
        # Act
        success = data_manager.initialize(initial_days=7)
        
        # Assert
        assert success is True
        mock_client.get_data.assert_called()
        
        # Check that data was stored
        data_5min = data_manager.get_data("5min")
        assert len(data_5min) > 0
        assert "timestamp" in data_5min.columns
    
    def test_multiple_timeframe_data(self):
        """Test handling data for multiple timeframes"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        
        # Create different data for different timeframes
        def mock_get_data(instrument, days=None, interval=None, **kwargs):
            base_data = {
                "timestamp": [datetime.now() - timedelta(minutes=i) for i in range(5)],
                "open": [2045.0] * 5,
                "high": [2046.0] * 5,
                "low": [2044.0] * 5,
                "close": [2045.5] * 5,
                "volume": [100] * 5
            }
            return pl.DataFrame(base_data)
        
        mock_client.get_data.side_effect = mock_get_data
        
        data_manager = ProjectXRealtimeDataManager("MGC", mock_client, "test_account")
        data_manager.initialize(timeframes=["1min", "5min", "15min"])
        
        # Act
        data_1min = data_manager.get_data("1min")
        data_5min = data_manager.get_data("5min")
        data_15min = data_manager.get_data("15min")
        
        # Assert
        assert len(data_1min) > 0
        assert len(data_5min) > 0
        assert len(data_15min) > 0
    
    def test_get_data_with_bars_limit(self):
        """Test getting limited number of bars"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        
        # Create 100 bars of data
        large_data = pl.DataFrame({
            "timestamp": [datetime.now() - timedelta(minutes=i) for i in range(100)],
            "open": [2045.0] * 100,
            "high": [2046.0] * 100,
            "low": [2044.0] * 100,
            "close": [2045.5] * 100,
            "volume": [100] * 100
        })
        
        mock_client.get_data.return_value = large_data
        
        data_manager = ProjectXRealtimeDataManager("MGC", mock_client, "test_account")
        data_manager.initialize()
        
        # Act
        limited_data = data_manager.get_data("5min", bars=20)
        
        # Assert
        assert len(limited_data) == 20
    
    def test_mtf_data_retrieval(self):
        """Test multi-timeframe data retrieval"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        
        def mock_get_data(instrument, days=None, interval=None, **kwargs):
            return pl.DataFrame({
                "timestamp": [datetime.now()],
                "open": [2045.0],
                "high": [2046.0],
                "low": [2044.0],
                "close": [2045.5],
                "volume": [100]
            })
        
        mock_client.get_data.side_effect = mock_get_data
        
        data_manager = ProjectXRealtimeDataManager("MGC", mock_client, "test_account")
        data_manager.initialize(timeframes=["1min", "5min", "15min"])
        
        # Act
        mtf_data = data_manager.get_mtf_data()
        
        # Assert
        assert isinstance(mtf_data, dict)
        assert "1min" in mtf_data
        assert "5min" in mtf_data
        assert "15min" in mtf_data
        
        for tf, data in mtf_data.items():
            assert isinstance(data, pl.DataFrame)
            assert len(data) > 0
    
    @patch('project_x_py.realtime_data_manager.ProjectXRealtimeClient')
    def test_realtime_feed_start(self, mock_realtime_class):
        """Test starting real-time data feed"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        mock_client._jwt_token = "test_token"
        
        mock_realtime_instance = Mock()
        mock_realtime_instance.connect.return_value = True
        mock_realtime_instance.subscribe_market_data.return_value = True
        mock_realtime_class.return_value = mock_realtime_instance
        
        data_manager = ProjectXRealtimeDataManager("MGC", mock_client, "test_account")
        data_manager.initialize()
        
        # Act
        success = data_manager.start_realtime_feed()
        
        # Assert
        assert success is True
        mock_realtime_instance.connect.assert_called_once()
        mock_realtime_instance.subscribe_market_data.assert_called()
        mock_realtime_instance.add_callback.assert_called()
    
    def test_realtime_price_update(self):
        """Test handling real-time price updates"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        data_manager = ProjectXRealtimeDataManager("MGC", mock_client, "test_account")
        data_manager.initialize()
        
        # Simulate price update
        price_data = {
            "instrument": "MGC",
            "bid": 2045.2,
            "ask": 2045.3,
            "last": 2045.25,
            "timestamp": datetime.now()
        }
        
        # Act
        data_manager._handle_price_update(price_data)
        current_price = data_manager.get_current_price()
        
        # Assert
        assert current_price == 2045.25
    
    def test_realtime_bar_aggregation(self):
        """Test aggregating tick data into bars"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        data_manager = ProjectXRealtimeDataManager("MGC", mock_client, "test_account")
        data_manager.initialize()
        
        # Initialize with some historical data
        data_manager._data["1min"] = pl.DataFrame({
            "timestamp": [datetime.now() - timedelta(minutes=1)],
            "open": [2045.0],
            "high": [2045.5],
            "low": [2044.5],
            "close": [2045.2],
            "volume": [100]
        })
        
        # Simulate multiple tick updates
        base_time = datetime.now()
        for i in range(10):
            tick_data = {
                "price": 2045.0 + (i * 0.1),
                "volume": 10,
                "timestamp": base_time + timedelta(seconds=i*6)
            }
            data_manager._update_bars_from_tick(tick_data)
        
        # Act
        updated_data = data_manager.get_data("1min")
        
        # Assert
        assert len(updated_data) >= 1
        # Latest bar should have been updated with new data
    
    def test_stop_realtime_feed(self):
        """Test stopping real-time data feed"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        mock_realtime = Mock(spec=ProjectXRealtimeClient)
        
        data_manager = ProjectXRealtimeDataManager("MGC", mock_client, "test_account")
        data_manager._realtime_client = mock_realtime
        data_manager._realtime_connected = True
        
        # Act
        data_manager.stop_realtime_feed()
        
        # Assert
        mock_realtime.disconnect.assert_called_once()
        assert data_manager._realtime_connected is False
    
    def test_data_quality_checks(self):
        """Test data quality validation"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        
        # Create data with gaps
        timestamps = [datetime.now() - timedelta(minutes=i*5) for i in range(10)]
        timestamps[5] = timestamps[4] - timedelta(minutes=30)  # Create a gap
        
        gapped_data = pl.DataFrame({
            "timestamp": timestamps,
            "open": [2045.0] * 10,
            "high": [2046.0] * 10,
            "low": [2044.0] * 10,
            "close": [2045.5] * 10,
            "volume": [100] * 10
        })
        
        mock_client.get_data.return_value = gapped_data
        
        data_manager = ProjectXRealtimeDataManager("MGC", mock_client, "test_account")
        
        # Act
        data_manager.initialize()
        quality_report = data_manager.check_data_quality()
        
        # Assert
        assert quality_report["has_gaps"] is True
        assert quality_report["gap_count"] > 0
    
    def test_current_price_fallback(self):
        """Test current price fallback when no real-time feed"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        mock_client.get_current_price.return_value = 2045.5
        
        data_manager = ProjectXRealtimeDataManager("MGC", mock_client, "test_account")
        data_manager.initialize()
        
        # Act
        # No real-time feed, should fall back to client method
        current_price = data_manager.get_current_price()
        
        # Assert
        assert current_price == 2045.5
        mock_client.get_current_price.assert_called_with("MGC")
    
    def test_callback_registration(self):
        """Test callback registration for data updates"""
        # Arrange
        mock_client = Mock(spec=ProjectX)
        data_manager = ProjectXRealtimeDataManager("MGC", mock_client, "test_account")
        data_manager.initialize()
        
        callback_called = False
        callback_data = None
        
        def test_callback(data):
            nonlocal callback_called, callback_data
            callback_called = True
            callback_data = data
        
        # Act
        data_manager.add_callback('price_update', test_callback)
        
        # Simulate price update
        data_manager._handle_price_update({
            "instrument": "MGC",
            "last": 2045.5
        })
        
        # Assert
        assert callback_called is True
        assert callback_data["last"] == 2045.5