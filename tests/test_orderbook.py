"""
Test suite for OrderBook functionality
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import polars as pl
from project_x_py.orderbook import OrderBook
from project_x_py.realtime import ProjectXRealtimeClient
from project_x_py.exceptions import ProjectXError


class TestOrderBook:
    """Test cases for OrderBook market microstructure analytics"""
    
    def test_basic_initialization(self):
        """Test basic OrderBook initialization"""
        # Act
        orderbook = OrderBook("MGC")
        
        # Assert
        assert orderbook.instrument == "MGC"
        assert orderbook._bid_price is None
        assert orderbook._ask_price is None
        assert orderbook._bid_volume is None
        assert orderbook._ask_volume is None
        assert orderbook._last_update is None
        assert orderbook._depth_data == {"bids": [], "asks": []}
    
    def test_orderbook_snapshot_empty(self):
        """Test orderbook snapshot when no data available"""
        # Arrange
        orderbook = OrderBook("MGC")
        
        # Act
        snapshot = orderbook.get_orderbook_snapshot()
        
        # Assert
        assert snapshot is None
    
    def test_orderbook_snapshot_with_data(self):
        """Test orderbook snapshot with available data"""
        # Arrange
        orderbook = OrderBook("MGC")
        
        # Manually set orderbook data
        orderbook._bid_price = 2045.0
        orderbook._ask_price = 2045.1
        orderbook._bid_volume = 50
        orderbook._ask_volume = 30
        orderbook._last_update = datetime.now()
        
        # Act
        snapshot = orderbook.get_orderbook_snapshot()
        
        # Assert
        assert snapshot is not None
        assert snapshot["bid_price"] == 2045.0
        assert snapshot["ask_price"] == 2045.1
        assert snapshot["bid_volume"] == 50
        assert snapshot["ask_volume"] == 30
        assert snapshot["spread"] == 0.1
        assert snapshot["mid_price"] == 2045.05
        assert "timestamp" in snapshot
    
    def test_update_orderbook_data(self):
        """Test updating orderbook with new data"""
        # Arrange
        orderbook = OrderBook("MGC")
        
        # Act
        orderbook.update_orderbook({
            "bid": 2045.2,
            "ask": 2045.3,
            "bid_size": 75,
            "ask_size": 60,
            "timestamp": datetime.now()
        })
        
        # Assert
        assert orderbook._bid_price == 2045.2
        assert orderbook._ask_price == 2045.3
        assert orderbook._bid_volume == 75
        assert orderbook._ask_volume == 60
        assert orderbook._last_update is not None
    
    def test_spread_calculation(self):
        """Test bid-ask spread calculations"""
        # Arrange
        orderbook = OrderBook("MGC")
        orderbook._bid_price = 2045.0
        orderbook._ask_price = 2045.5
        
        # Act
        spread = orderbook.get_spread()
        spread_percentage = orderbook.get_spread_percentage()
        
        # Assert
        assert spread == 0.5
        assert abs(spread_percentage - 0.0244) < 0.0001  # ~0.0244%
    
    def test_orderbook_imbalance(self):
        """Test orderbook imbalance calculation"""
        # Arrange
        orderbook = OrderBook("MGC")
        orderbook._bid_volume = 100
        orderbook._ask_volume = 50
        
        # Act
        imbalance = orderbook.get_order_imbalance()
        
        # Assert
        # Imbalance = (bid_vol - ask_vol) / (bid_vol + ask_vol)
        # = (100 - 50) / (100 + 50) = 50/150 = 0.333...
        assert abs(imbalance - 0.333) < 0.01
    
    def test_depth_data_update(self):
        """Test depth data update with multiple levels"""
        # Arrange
        orderbook = OrderBook("MGC")
        
        depth_data = {
            "bids": [
                {"price": 2045.0, "volume": 50},
                {"price": 2044.9, "volume": 30},
                {"price": 2044.8, "volume": 20}
            ],
            "asks": [
                {"price": 2045.1, "volume": 40},
                {"price": 2045.2, "volume": 35},
                {"price": 2045.3, "volume": 25}
            ]
        }
        
        # Act
        orderbook.update_depth(depth_data)
        
        # Assert
        assert len(orderbook._depth_data["bids"]) == 3
        assert len(orderbook._depth_data["asks"]) == 3
        assert orderbook._depth_data["bids"][0]["price"] == 2045.0
        assert orderbook._depth_data["asks"][0]["price"] == 2045.1
    
    def test_weighted_mid_price(self):
        """Test volume-weighted mid price calculation"""
        # Arrange
        orderbook = OrderBook("MGC")
        orderbook._bid_price = 2045.0
        orderbook._ask_price = 2045.2
        orderbook._bid_volume = 100
        orderbook._ask_volume = 50
        
        # Act
        weighted_mid = orderbook.get_weighted_mid_price()
        
        # Assert
        # Weighted mid = (bid * ask_vol + ask * bid_vol) / (bid_vol + ask_vol)
        # = (2045.0 * 50 + 2045.2 * 100) / 150
        expected = (2045.0 * 50 + 2045.2 * 100) / 150
        assert abs(weighted_mid - expected) < 0.01
    
    def test_liquidity_metrics(self):
        """Test liquidity metrics calculation"""
        # Arrange
        orderbook = OrderBook("MGC")
        
        # Set up depth data
        orderbook._depth_data = {
            "bids": [
                {"price": 2045.0, "volume": 50},
                {"price": 2044.9, "volume": 30},
                {"price": 2044.8, "volume": 20}
            ],
            "asks": [
                {"price": 2045.1, "volume": 40},
                {"price": 2045.2, "volume": 35},
                {"price": 2045.3, "volume": 25}
            ]
        }
        
        # Act
        liquidity = orderbook.get_liquidity_metrics()
        
        # Assert
        assert liquidity["total_bid_volume"] == 100  # 50+30+20
        assert liquidity["total_ask_volume"] == 100  # 40+35+25
        assert liquidity["bid_levels"] == 3
        assert liquidity["ask_levels"] == 3
        assert "average_bid_size" in liquidity
        assert "average_ask_size" in liquidity
    
    def test_advanced_analytics(self):
        """Test advanced orderbook analytics"""
        # Arrange
        orderbook = OrderBook("MGC")
        
        # Set up orderbook data
        orderbook._bid_price = 2045.0
        orderbook._ask_price = 2045.1
        orderbook._bid_volume = 80
        orderbook._ask_volume = 60
        orderbook._depth_data = {
            "bids": [
                {"price": 2045.0, "volume": 80},
                {"price": 2044.9, "volume": 40}
            ],
            "asks": [
                {"price": 2045.1, "volume": 60},
                {"price": 2045.2, "volume": 30}
            ]
        }
        
        # Act
        analytics = orderbook.get_advanced_analytics()
        
        # Assert
        assert isinstance(analytics, dict)
        assert "spread" in analytics
        assert "spread_percentage" in analytics
        assert "order_imbalance" in analytics
        assert "weighted_mid_price" in analytics
        assert "liquidity_score" in analytics
        assert analytics["spread"] == 0.1
    
    def test_price_impact_estimation(self):
        """Test price impact estimation for market orders"""
        # Arrange
        orderbook = OrderBook("MGC")
        
        # Set up depth data
        orderbook._depth_data = {
            "bids": [
                {"price": 2045.0, "volume": 50},
                {"price": 2044.9, "volume": 30},
                {"price": 2044.8, "volume": 20}
            ],
            "asks": [
                {"price": 2045.1, "volume": 40},
                {"price": 2045.2, "volume": 35},
                {"price": 2045.3, "volume": 25}
            ]
        }
        
        # Act
        # Buy order of 60 contracts should consume first ask level (40) 
        # and part of second (20)
        buy_impact = orderbook.estimate_price_impact(60, side="buy")
        
        # Sell order of 70 contracts should consume first bid level (50)
        # and part of second (20)
        sell_impact = orderbook.estimate_price_impact(70, side="sell")
        
        # Assert
        assert buy_impact["average_price"] > 2045.1  # Should be higher than best ask
        assert buy_impact["slippage"] > 0
        assert sell_impact["average_price"] < 2045.0  # Should be lower than best bid
        assert sell_impact["slippage"] > 0
    
    def test_orderbook_velocity(self):
        """Test orderbook velocity tracking"""
        # Arrange
        orderbook = OrderBook("MGC")
        
        # Simulate multiple updates
        for i in range(5):
            orderbook.update_orderbook({
                "bid": 2045.0 + (i * 0.1),
                "ask": 2045.1 + (i * 0.1),
                "bid_size": 50 + i * 10,
                "ask_size": 40 + i * 10,
                "timestamp": datetime.now()
            })
        
        # Act
        velocity = orderbook.get_orderbook_velocity()
        
        # Assert
        assert velocity["update_count"] == 5
        assert velocity["avg_spread_change"] >= 0
        assert "bid_price_volatility" in velocity
        assert "ask_price_volatility" in velocity
    
    def test_empty_orderbook_analytics(self):
        """Test analytics methods handle empty orderbook gracefully"""
        # Arrange
        orderbook = OrderBook("MGC")
        
        # Act & Assert
        assert orderbook.get_spread() is None
        assert orderbook.get_spread_percentage() is None
        assert orderbook.get_order_imbalance() is None
        assert orderbook.get_weighted_mid_price() is None
        
        analytics = orderbook.get_advanced_analytics()
        assert analytics["spread"] is None
        assert analytics["order_imbalance"] is None