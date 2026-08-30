"""
Type definitions for API responses from ProjectX Gateway.

Author: @TexasCoding
Date: 2025-08-02

Overview:
    Provides comprehensive TypedDict definitions for all API response structures
    from the ProjectX Gateway. These type definitions replace generic Any types
    with specific, type-safe structures that enable better IDE support and
    type checking throughout the SDK.

Key Features:
    - Complete TypedDict definitions for all API responses
    - Nested structure support for complex responses
    - Optional field handling for partial responses
    - Type-safe field access with IDE autocomplete
    - Comprehensive documentation for each response type

Response Categories:
    - Authentication: Login, token refresh responses
    - Market Data: Bars, quotes, instrument search responses
    - Trading: Order placement, modification, cancellation responses
    - Account: Account info, balance, permissions responses
    - Position: Position details, P&L calculation responses
    - WebSocket: Real-time event payload structures

Example Usage:
    ```python
    from project_x_py.types.api_responses import (
        InstrumentResponse,
        OrderResponse,
        PositionResponse,
        BarDataResponse,
    )


    async def process_instrument(response: InstrumentResponse) -> None:
        # Type-safe access to all fields
        print(f"Symbol: {response['name']}")
        print(f"Tick size: {response['tickSize']}")


    async def process_bars(response: BarDataResponse) -> None:
        for bar in response["bars"]:
            print(f"Time: {bar['timestamp']}, Close: {bar['close']}")
    ```

See Also:
    - `types.response_types`: High-level response models
    - `types.protocols`: Protocol definitions for components
    - `models`: Data model classes for entities
"""

from typing import NotRequired, TypedDict


class AuthLoginResponse(TypedDict):
    """Response from authentication login."""

    token: str
    expiresIn: NotRequired[int]
    accountId: NotRequired[int]
    accountName: NotRequired[str]
    canTrade: NotRequired[bool]
    simulated: NotRequired[bool]


class AccountResponse(TypedDict):
    """Account information response."""

    id: int
    name: str
    balance: float
    canTrade: bool
    isVisible: bool
    simulated: bool


class InstrumentResponse(TypedDict):
    """Instrument/contract information response."""

    id: str
    name: str
    description: str
    tickSize: float
    tickValue: float
    activeContract: bool
    symbolId: NotRequired[str]
    contractMultiplier: NotRequired[float]
    tradingHours: NotRequired[str]
    lastTradingDay: NotRequired[str]


class OrderResponse(TypedDict):
    """Order information response."""

    id: int
    accountId: int
    contractId: str
    creationTimestamp: str
    updateTimestamp: NotRequired[str]
    status: (
        int  # 0=None, 1=Open, 2=Filled, 3=Cancelled, 4=Expired, 5=Rejected, 6=Pending
    )
    type: int  # 0=Unknown, 1=Limit, 2=Market, 3=StopLimit, 4=Stop, 5=TrailingStop, 6=JoinBid, 7=JoinAsk
    side: int  # 0=Bid/Buy, 1=Ask/Sell
    size: int
    symbolId: NotRequired[str]
    fillVolume: NotRequired[int]
    limitPrice: NotRequired[float]
    stopPrice: NotRequired[float]
    filledPrice: NotRequired[float]
    customTag: NotRequired[str]


class OrderPlacementResponse(TypedDict):
    """Response from placing an order."""

    orderId: int
    success: bool
    errorCode: int
    errorMessage: NotRequired[str]


class PositionResponse(TypedDict):
    """Position information response."""

    id: int
    accountId: int
    contractId: str
    creationTimestamp: str
    type: int  # 0=UNDEFINED, 1=LONG, 2=SHORT
    size: int
    averagePrice: float
    contractDisplayName: NotRequired[str]


class TradeResponse(TypedDict):
    """Trade execution response."""

    id: int
    accountId: int
    contractId: str
    creationTimestamp: str
    price: float
    profitAndLoss: NotRequired[float]  # None for half-turn trades
    fees: NotRequired[float]
    commissions: NotRequired[float]
    side: int  # 0=Buy, 1=Sell
    size: int
    voided: bool
    orderId: int


class BarData(TypedDict):
    """Individual OHLCV bar data."""

    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class BarDataResponse(TypedDict):
    """Response from bar data request."""

    contractId: str
    bars: list[BarData]
    interval: int
    unit: int


class QuoteData(TypedDict):
    """Market quote data."""

    contractId: str
    bid: float
    bidSize: int
    ask: float
    askSize: int
    last: float
    lastSize: int
    timestamp: str


class MarketDepthLevel(TypedDict):
    """Single level of market depth."""

    price: float
    size: int
    orders: NotRequired[int]


class MarketDepthResponse(TypedDict):
    """Market depth/orderbook response."""

    contractId: str
    timestamp: str
    bids: list[MarketDepthLevel]
    asks: list[MarketDepthLevel]


class InstrumentSearchResponse(TypedDict):
    """Response from instrument search."""

    contracts: list[InstrumentResponse]
    success: NotRequired[bool]
    totalCount: NotRequired[int]


# WebSocket event payloads
class AccountUpdatePayload(TypedDict):
    """Real-time account update event."""

    accountId: int
    balance: float
    equity: NotRequired[float]
    margin: NotRequired[float]
    timestamp: str


class PositionUpdatePayload(TypedDict):
    """Real-time position update event."""

    positionId: int
    accountId: int
    contractId: str
    type: int
    size: int
    averagePrice: float
    timestamp: str


class OrderUpdatePayload(TypedDict):
    """Real-time order update event."""

    orderId: int
    accountId: int
    contractId: str
    status: int
    fillVolume: NotRequired[int]
    filledPrice: NotRequired[float]
    timestamp: str


class TradeExecutionPayload(TypedDict):
    """Real-time trade execution event."""

    tradeId: int
    orderId: int
    accountId: int
    contractId: str
    price: float
    size: int
    side: int
    profitAndLoss: NotRequired[float]
    fees: float
    timestamp: str


class QuoteUpdatePayload(TypedDict):
    """Real-time quote update event."""

    contractId: str
    bid: NotRequired[float]
    bidSize: NotRequired[int]
    ask: NotRequired[float]
    askSize: NotRequired[int]
    last: NotRequired[float]
    lastSize: NotRequired[int]
    timestamp: str


class MarketTradePayload(TypedDict):
    """Real-time market trade event."""

    contractId: str
    price: float
    size: int
    side: int  # 0=Buy, 1=Sell
    timestamp: str
    tradeId: NotRequired[str]


class MarketDepthUpdatePayload(TypedDict):
    """Real-time market depth update event."""

    contractId: str
    side: int  # 0=Bid, 1=Ask
    action: int  # 0=Add, 1=Update, 2=Delete
    price: float
    size: int
    timestamp: str


# Composite responses
class OrderSearchResponse(TypedDict):
    """Response from order search."""

    orders: list[OrderResponse]
    totalCount: int


class PositionSearchResponse(TypedDict):
    """Response from position search."""

    positions: list[PositionResponse]
    totalCount: int


class TradeSearchResponse(TypedDict):
    """Response from trade search."""

    trades: list[TradeResponse]
    totalCount: int


class AccountListResponse(TypedDict):
    """Response from listing accounts."""

    accounts: list[AccountResponse]


# Error responses
class ErrorResponse(TypedDict):
    """Standard error response."""

    errorCode: int
    errorMessage: str
    details: NotRequired[dict[str, str]]


__all__ = [
    "AccountListResponse",
    "AccountResponse",
    "AccountUpdatePayload",
    "AuthLoginResponse",
    "BarData",
    "BarDataResponse",
    "ErrorResponse",
    "InstrumentResponse",
    "InstrumentSearchResponse",
    "MarketDepthLevel",
    "MarketDepthResponse",
    "MarketDepthUpdatePayload",
    "MarketTradePayload",
    "OrderPlacementResponse",
    "OrderResponse",
    "OrderSearchResponse",
    "OrderUpdatePayload",
    "PositionResponse",
    "PositionSearchResponse",
    "PositionUpdatePayload",
    "QuoteData",
    "QuoteUpdatePayload",
    "TradeExecutionPayload",
    "TradeResponse",
    "TradeSearchResponse",
]
