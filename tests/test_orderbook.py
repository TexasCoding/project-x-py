"""
Test suite for OrderBook functionality
"""

from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import polars as pl
import pytest

from project_x_py.exceptions import ProjectXError
from project_x_py.orderbook import OrderBook
from project_x_py.realtime import ProjectXRealtimeClient


class TestOrderBook:
    """Test cases for OrderBook market microstructure analytics"""

    def test_basic_initialization(self):
        """Test basic OrderBook initialization"""
        # Act
        orderbook = OrderBook("MGC")

        # Assert
        assert orderbook.instrument == "MGC"
        assert len(orderbook.orderbook_bids) == 0
        assert len(orderbook.orderbook_asks) == 0
        assert len(orderbook.recent_trades) == 0
        assert orderbook.last_orderbook_update is None

    def test_orderbook_snapshot_empty(self):
        """Test orderbook snapshot when no data available"""
        # Arrange
        orderbook = OrderBook("MGC")

        # Act
        snapshot = orderbook.get_orderbook_snapshot()

        # Assert
        assert snapshot is not None
        assert "bids" in snapshot
        assert "asks" in snapshot
        assert "metadata" in snapshot
        assert len(snapshot["bids"]) == 0
        assert len(snapshot["asks"]) == 0
        assert snapshot["metadata"]["best_bid"] is None
        assert snapshot["metadata"]["best_ask"] is None

    def test_orderbook_snapshot_with_data(self):
        """Test orderbook snapshot with available data"""
        # Arrange
        orderbook = OrderBook("MGC")

        # Create sample market depth data
        market_data = {
            "contract_id": "MGC",
            "data": [
                {
                    "price": 2045.0,
                    "volume": 50,
                    "type": 2,
                    "timestamp": datetime.now(),
                },  # Bid
                {
                    "price": 2045.1,
                    "volume": 30,
                    "type": 1,
                    "timestamp": datetime.now(),
                },  # Ask
            ],
        }

        # Act
        orderbook.process_market_depth(market_data)
        snapshot = orderbook.get_orderbook_snapshot()

        # Assert
        assert snapshot is not None
        assert snapshot["metadata"]["best_bid"] == 2045.0
        assert snapshot["metadata"]["best_ask"] == 2045.1
        assert snapshot["metadata"]["spread"] is not None
        assert (
            abs(snapshot["metadata"]["spread"] - 0.1) < 0.0001
        )  # Use tolerance for floating point

    def test_market_depth_processing(self):
        """Test processing market depth data"""
        # Arrange
        orderbook = OrderBook("MGC")

        market_data = {
            "contract_id": "MGC",
            "data": [
                {
                    "price": 2045.2,
                    "volume": 75,
                    "type": 2,
                    "timestamp": datetime.now(),
                },  # Bid
                {
                    "price": 2045.3,
                    "volume": 60,
                    "type": 1,
                    "timestamp": datetime.now(),
                },  # Ask
            ],
        }

        # Act
        orderbook.process_market_depth(market_data)

        # Assert
        best_prices = orderbook.get_best_bid_ask()
        assert best_prices["bid"] == 2045.2
        assert best_prices["ask"] == 2045.3
        assert best_prices["spread"] is not None
        assert (
            abs(best_prices["spread"] - 0.1) < 0.0001
        )  # Use tolerance for floating point
        assert best_prices["mid"] == 2045.25

    def test_best_bid_ask_calculation(self):
        """Test best bid/ask price calculations"""
        # Arrange
        orderbook = OrderBook("MGC")

        market_data = {
            "contract_id": "MGC",
            "data": [
                {
                    "price": 2045.0,
                    "volume": 100,
                    "type": 2,
                    "timestamp": datetime.now(),
                },  # Bid
                {
                    "price": 2045.5,
                    "volume": 50,
                    "type": 1,
                    "timestamp": datetime.now(),
                },  # Ask
            ],
        }

        # Act
        orderbook.process_market_depth(market_data)
        result = orderbook.get_best_bid_ask()

        # Assert
        assert result["bid"] == 2045.0
        assert result["ask"] == 2045.5
        assert result["spread"] == 0.5
        assert result["mid"] == 2045.25

    def test_market_imbalance_calculation(self):
        """Test market imbalance calculation"""
        # Arrange
        orderbook = OrderBook("MGC")

        # Create imbalanced orderbook (more bids than asks)
        market_data = {
            "contract_id": "MGC",
            "data": [
                {
                    "price": 2045.0,
                    "volume": 200,
                    "type": 2,
                    "timestamp": datetime.now(),
                },  # Large bid
                {
                    "price": 2044.9,
                    "volume": 150,
                    "type": 2,
                    "timestamp": datetime.now(),
                },  # Another bid
                {
                    "price": 2045.1,
                    "volume": 50,
                    "type": 1,
                    "timestamp": datetime.now(),
                },  # Small ask
            ],
        }

        # Act
        orderbook.process_market_depth(market_data)
        imbalance = orderbook.get_market_imbalance()

        # Assert
        assert "imbalance_ratio" in imbalance
        assert "direction" in imbalance
        assert "confidence" in imbalance
        # Should be positive (more bid volume)
        assert imbalance["imbalance_ratio"] > 0

    def test_depth_data_processing(self):
        """Test processing multiple depth levels"""
        # Arrange
        orderbook = OrderBook("MGC")

        market_data = {
            "contract_id": "MGC",
            "data": [
                {
                    "price": 2045.0,
                    "volume": 50,
                    "type": 2,
                    "timestamp": datetime.now(),
                },  # Bid level 1
                {
                    "price": 2044.9,
                    "volume": 30,
                    "type": 2,
                    "timestamp": datetime.now(),
                },  # Bid level 2
                {
                    "price": 2044.8,
                    "volume": 20,
                    "type": 2,
                    "timestamp": datetime.now(),
                },  # Bid level 3
                {
                    "price": 2045.1,
                    "volume": 40,
                    "type": 1,
                    "timestamp": datetime.now(),
                },  # Ask level 1
                {
                    "price": 2045.2,
                    "volume": 35,
                    "type": 1,
                    "timestamp": datetime.now(),
                },  # Ask level 2
                {
                    "price": 2045.3,
                    "volume": 25,
                    "type": 1,
                    "timestamp": datetime.now(),
                },  # Ask level 3
            ],
        }

        # Act
        orderbook.process_market_depth(market_data)

        # Assert
        bids = orderbook.get_orderbook_bids(3)
        asks = orderbook.get_orderbook_asks(3)

        assert len(bids) == 3
        assert len(asks) == 3

        # Check sorting (bids: high to low, asks: low to high)
        bid_prices = bids.get_column("price").to_list()
        ask_prices = asks.get_column("price").to_list()

        assert bid_prices == sorted(bid_prices, reverse=True)
        assert ask_prices == sorted(ask_prices)

    def test_liquidity_levels_analysis(self):
        """Test liquidity levels analysis"""
        # Arrange
        orderbook = OrderBook("MGC")

        market_data = {
            "contract_id": "MGC",
            "data": [
                {
                    "price": 2045.0,
                    "volume": 200,
                    "type": 2,
                    "timestamp": datetime.now(),
                },  # Large bid
                {"price": 2044.9, "volume": 40, "type": 2, "timestamp": datetime.now()},
                {
                    "price": 2045.1,
                    "volume": 150,
                    "type": 1,
                    "timestamp": datetime.now(),
                },  # Large ask
                {"price": 2045.2, "volume": 30, "type": 1, "timestamp": datetime.now()},
            ],
        }

        # Act
        orderbook.process_market_depth(market_data)
        liquidity = orderbook.get_liquidity_levels(min_volume=100)

        # Assert
        assert "bid_liquidity" in liquidity
        assert "ask_liquidity" in liquidity

        # Should have significant levels (volume >= 100)
        if len(liquidity["bid_liquidity"]) > 0:
            min_bid_volume = liquidity["bid_liquidity"].get_column("volume").min()
            assert min_bid_volume >= 100

        if len(liquidity["ask_liquidity"]) > 0:
            min_ask_volume = liquidity["ask_liquidity"].get_column("volume").min()
            assert min_ask_volume >= 100

    def test_trade_flow_processing(self):
        """Test trade execution processing"""
        # Arrange
        orderbook = OrderBook("MGC")

        # First add orderbook levels
        market_data = {
            "contract_id": "MGC",
            "data": [
                {
                    "price": 2045.0,
                    "volume": 100,
                    "type": 2,
                    "timestamp": datetime.now(),
                },  # Bid
                {
                    "price": 2045.1,
                    "volume": 80,
                    "type": 1,
                    "timestamp": datetime.now(),
                },  # Ask
                {
                    "price": 2045.1,
                    "volume": 50,
                    "type": 5,
                    "timestamp": datetime.now(),
                },  # Trade at ask
            ],
        }

        # Act
        orderbook.process_market_depth(market_data)
        trades = orderbook.get_recent_trades(10)

        # Assert
        assert len(trades) > 0
        trade_flow = orderbook.get_trade_flow_summary(minutes=5)
        assert "total_volume" in trade_flow
        assert "trade_count" in trade_flow
        assert "buy_volume" in trade_flow
        assert "sell_volume" in trade_flow

    def test_advanced_analytics(self):
        """Test advanced orderbook analytics"""
        # Arrange
        orderbook = OrderBook("MGC")

        # Set up complex orderbook data
        market_data = {
            "contract_id": "MGC",
            "data": [
                {"price": 2045.0, "volume": 80, "type": 2, "timestamp": datetime.now()},
                {"price": 2044.9, "volume": 40, "type": 2, "timestamp": datetime.now()},
                {"price": 2045.1, "volume": 60, "type": 1, "timestamp": datetime.now()},
                {"price": 2045.2, "volume": 30, "type": 1, "timestamp": datetime.now()},
                {
                    "price": 2045.1,
                    "volume": 25,
                    "type": 5,
                    "timestamp": datetime.now(),
                },  # Trade
            ],
        }

        # Act
        orderbook.process_market_depth(market_data)
        analytics = orderbook.get_advanced_market_metrics()

        # Assert
        assert "liquidity_analysis" in analytics
        assert "market_imbalance" in analytics
        assert "orderbook_snapshot" in analytics
        assert "trade_flow" in analytics
        assert "timestamp" in analytics

    def test_order_clusters_detection(self):
        """Test order cluster detection"""
        # Arrange
        orderbook = OrderBook("MGC")

        # Create clustered orders at similar prices
        market_data = {
            "contract_id": "MGC",
            "data": [
                {"price": 2045.0, "volume": 50, "type": 2, "timestamp": datetime.now()},
                {
                    "price": 2045.05,
                    "volume": 40,
                    "type": 2,
                    "timestamp": datetime.now(),
                },  # Close to 2045.0
                {
                    "price": 2045.1,
                    "volume": 45,
                    "type": 2,
                    "timestamp": datetime.now(),
                },  # Close to 2045.0
                {"price": 2045.5, "volume": 30, "type": 1, "timestamp": datetime.now()},
            ],
        }

        # Act
        orderbook.process_market_depth(market_data)
        clusters = orderbook.detect_order_clusters(
            price_tolerance=0.15, min_cluster_size=2
        )

        # Assert
        assert "bid_clusters" in clusters
        assert "ask_clusters" in clusters
        assert "cluster_count" in clusters

    def test_empty_orderbook_analytics(self):
        """Test analytics methods handle empty orderbook gracefully"""
        # Arrange
        orderbook = OrderBook("MGC")

        # Act & Assert - all methods should handle empty state gracefully
        best_prices = orderbook.get_best_bid_ask()
        assert best_prices["bid"] is None
        assert best_prices["ask"] is None
        assert best_prices["spread"] is None

        imbalance = orderbook.get_market_imbalance()
        assert imbalance["imbalance_ratio"] == 0
        assert imbalance["direction"] == "neutral"

        snapshot = orderbook.get_orderbook_snapshot()
        assert snapshot["metadata"]["best_bid"] is None
        assert snapshot["metadata"]["best_ask"] is None

        trades = orderbook.get_recent_trades()
        assert len(trades) == 0

        trade_flow = orderbook.get_trade_flow_summary()
        assert trade_flow["total_volume"] == 0
        assert trade_flow["trade_count"] == 0
