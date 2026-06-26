"""
Tests for API response TypedDict definitions.

Author: @TexasCoding
Date: 2025-08-17
"""

from typing import get_type_hints

from project_x_py.types.api_responses import (
    AccountResponse,
    AccountUpdatePayload,
    AuthLoginResponse,
    BarData,
    BarDataResponse,
    ErrorResponse,
    InstrumentResponse,
    MarketDepthLevel,
    MarketDepthResponse,
    OrderResponse,
    OrderSearchResponse,
    OrderUpdatePayload,
    PositionResponse,
    PositionSearchResponse,
    PositionUpdatePayload,
    QuoteData,
    TradeExecutionPayload,
    TradeResponse,
    TradeSearchResponse,
)


class TestAPIResponseTypes:
    """Test suite for API response TypedDict definitions."""

    def test_auth_login_response_structure(self):
        """Test AuthLoginResponse has correct fields."""
        hints = get_type_hints(AuthLoginResponse, include_extras=True)

        # Required fields
        assert "jwt" in hints
        assert hints["jwt"] is str
        assert "expiresIn" in hints
        assert hints["expiresIn"] is int
        assert "accountId" in hints
        assert hints["accountId"] is int

    def test_account_response_structure(self):
        """Test AccountResponse has correct fields."""
        hints = get_type_hints(AccountResponse, include_extras=True)

        assert "id" in hints
        assert hints["id"] is int
        assert "name" in hints
        assert hints["name"] is str
        assert "balance" in hints
        assert hints["balance"] is float
        assert "canTrade" in hints
        assert hints["canTrade"] is bool

    def test_instrument_response_structure(self):
        """Test InstrumentResponse has correct fields."""
        hints = get_type_hints(InstrumentResponse, include_extras=True)

        # Required fields
        assert "id" in hints
        assert hints["id"] is str
        assert "name" in hints
        assert "tickSize" in hints
        assert hints["tickSize"] is float
        assert "tickValue" in hints
        assert hints["tickValue"] is float
        assert "activeContract" in hints
        assert hints["activeContract"] is bool

        # Optional fields should be NotRequired
        assert "symbolId" in hints
        assert "contractMultiplier" in hints

    def test_order_response_structure(self):
        """Test OrderResponse has correct fields."""
        hints = get_type_hints(OrderResponse, include_extras=True)

        # Core fields
        assert "id" in hints
        assert hints["id"] is int
        assert "accountId" in hints
        assert "contractId" in hints
        assert hints["contractId"] is str
        assert "status" in hints
        assert hints["status"] is int
        assert "type" in hints
        assert hints["type"] is int
        assert "side" in hints
        assert hints["side"] is int
        assert "size" in hints
        assert hints["size"] is int

        # Optional price fields
        assert "limitPrice" in hints
        assert "stopPrice" in hints
        assert "filledPrice" in hints

    def test_position_response_structure(self):
        """Test PositionResponse has correct fields."""
        hints = get_type_hints(PositionResponse, include_extras=True)

        assert "id" in hints
        assert hints["id"] is int
        assert "accountId" in hints
        assert "contractId" in hints
        assert "type" in hints
        assert hints["type"] is int  # 0=UNDEFINED, 1=LONG, 2=SHORT
        assert "size" in hints
        assert hints["size"] is int
        assert "averagePrice" in hints
        assert hints["averagePrice"] is float
        assert "contractDisplayName" in hints

    def test_trade_response_structure(self):
        """Test TradeResponse has correct fields."""
        hints = get_type_hints(TradeResponse, include_extras=True)

        assert "id" in hints
        assert hints["id"] is int
        assert "price" in hints
        assert hints["price"] is float
        assert "size" in hints
        assert hints["size"] is int
        assert "side" in hints
        assert hints["side"] is int
        assert "fees" in hints
        assert hints["fees"] is float

        # Optional P&L (None for half-turn trades)
        assert "profitAndLoss" in hints

    def test_bar_data_structure(self):
        """Test BarData OHLCV structure."""
        hints = get_type_hints(BarData, include_extras=True)

        # OHLCV fields
        assert "timestamp" in hints
        assert hints["timestamp"] is str
        assert "open" in hints
        assert hints["open"] is float
        assert "high" in hints
        assert hints["high"] is float
        assert "low" in hints
        assert hints["low"] is float
        assert "close" in hints
        assert hints["close"] is float
        assert "volume" in hints
        assert hints["volume"] is int

    def test_quote_data_structure(self):
        """Test QuoteData market quote structure."""
        hints = get_type_hints(QuoteData, include_extras=True)

        assert "contractId" in hints
        assert hints["contractId"] is str
        assert "bid" in hints
        assert hints["bid"] is float
        assert "bidSize" in hints
        assert hints["bidSize"] is int
        assert "ask" in hints
        assert hints["ask"] is float
        assert "askSize" in hints
        assert hints["askSize"] is int

    def test_market_depth_level_structure(self):
        """Test MarketDepthLevel structure."""
        hints = get_type_hints(MarketDepthLevel, include_extras=True)

        assert "price" in hints
        assert hints["price"] is float
        assert "size" in hints
        assert hints["size"] is int
        assert "orders" in hints  # Optional

    def test_websocket_payload_structures(self):
        """Test WebSocket event payload structures."""
        # Account update
        account_hints = get_type_hints(AccountUpdatePayload, include_extras=True)
        assert "accountId" in account_hints
        assert "balance" in account_hints
        assert "timestamp" in account_hints

        # Position update
        position_hints = get_type_hints(PositionUpdatePayload, include_extras=True)
        assert "positionId" in position_hints
        assert "contractId" in position_hints
        assert "size" in position_hints
        assert "averagePrice" in position_hints

        # Order update
        order_hints = get_type_hints(OrderUpdatePayload, include_extras=True)
        assert "orderId" in order_hints
        assert "status" in order_hints
        assert "timestamp" in order_hints

        # Trade execution
        trade_hints = get_type_hints(TradeExecutionPayload, include_extras=True)
        assert "tradeId" in trade_hints
        assert "orderId" in trade_hints
        assert "price" in trade_hints
        assert "size" in trade_hints

    def test_composite_response_structures(self):
        """Test composite response structures."""
        # Order search
        order_search_hints = get_type_hints(OrderSearchResponse, include_extras=True)
        assert "orders" in order_search_hints
        assert "totalCount" in order_search_hints

        # Position search
        position_search_hints = get_type_hints(
            PositionSearchResponse, include_extras=True
        )
        assert "positions" in position_search_hints
        assert "totalCount" in position_search_hints

        # Trade search
        trade_search_hints = get_type_hints(TradeSearchResponse, include_extras=True)
        assert "trades" in trade_search_hints
        assert "totalCount" in trade_search_hints

    def test_error_response_structure(self):
        """Test ErrorResponse structure."""
        hints = get_type_hints(ErrorResponse, include_extras=True)

        assert "errorCode" in hints
        assert hints["errorCode"] is int
        assert "errorMessage" in hints
        assert hints["errorMessage"] is str
        assert "details" in hints  # Optional

    def test_real_world_response_creation(self):
        """Test creating responses with real-world data."""
        # Create a valid auth response
        auth_response: AuthLoginResponse = {
            "jwt": "eyJ0eXAiOiJKV1QiLCJhbGc...",
            "expiresIn": 3600,
            "accountId": 12345,
            "accountName": "TestAccount",
            "canTrade": True,
            "simulated": False,
        }

        assert auth_response["jwt"].startswith("eyJ")
        assert auth_response["expiresIn"] == 3600

        # Create a valid instrument response
        instrument: InstrumentResponse = {
            "id": "CON.F.US.MNQ.U25",
            "name": "MNQU25",
            "description": "E-mini NASDAQ-100 Futures",
            "tickSize": 0.25,
            "tickValue": 0.50,
            "activeContract": True,
        }

        assert instrument["id"] == "CON.F.US.MNQ.U25"
        assert instrument["tickSize"] == 0.25

        # Create a position with optional fields
        position: PositionResponse = {
            "id": 67890,
            "accountId": 12345,
            "contractId": "CON.F.US.MNQ.U25",
            "contractDisplayName": "MNQU25",
            "creationTimestamp": "2024-01-01T10:00:00Z",
            "type": 1,  # LONG
            "size": 5,
            "averagePrice": 16500.25,
        }

        assert position["type"] == 1
        assert position["size"] == 5
        assert position["contractDisplayName"] == "MNQU25"

    def test_market_data_responses(self):
        """Test market data response structures."""
        # Bar data response
        bar_response: BarDataResponse = {
            "contractId": "CON.F.US.MNQ.U25",
            "bars": [
                {
                    "timestamp": "2024-01-01T09:30:00Z",
                    "open": 16500.0,
                    "high": 16525.0,
                    "low": 16495.0,
                    "close": 16520.0,
                    "volume": 1250,
                }
            ],
            "interval": 5,
            "unit": 2,
        }

        assert len(bar_response["bars"]) == 1
        assert bar_response["bars"][0]["close"] == 16520.0

        # Market depth response
        depth_response: MarketDepthResponse = {
            "contractId": "CON.F.US.MNQ.U25",
            "timestamp": "2024-01-01T09:30:00Z",
            "bids": [
                {"price": 16519.75, "size": 10},
                {"price": 16519.50, "size": 25},
            ],
            "asks": [
                {"price": 16520.00, "size": 15},
                {"price": 16520.25, "size": 30},
            ],
        }

        assert len(depth_response["bids"]) == 2
        assert depth_response["bids"][0]["price"] == 16519.75

    def test_optional_fields_handling(self):
        """Test that optional fields work correctly."""
        # Minimal order response (only required fields)
        minimal_order: OrderResponse = {
            "id": 12345,
            "accountId": 1001,
            "contractId": "CON.F.US.MNQ.U25",
            "creationTimestamp": "2024-01-01T10:00:00Z",
            "status": 1,
            "type": 2,
            "side": 0,
            "size": 5,
        }

        assert minimal_order["id"] == 12345
        assert "limitPrice" not in minimal_order

        # Full order response with optional fields
        full_order: OrderResponse = {
            "id": 12345,
            "accountId": 1001,
            "contractId": "CON.F.US.MNQ.U25",
            "creationTimestamp": "2024-01-01T10:00:00Z",
            "updateTimestamp": "2024-01-01T10:00:05Z",
            "status": 2,
            "type": 1,
            "side": 0,
            "size": 5,
            "fillVolume": 5,
            "limitPrice": 16500.0,
            "filledPrice": 16499.75,
            "customTag": "my_strategy_001",
        }

        assert full_order["limitPrice"] == 16500.0
        assert full_order["customTag"] == "my_strategy_001"
