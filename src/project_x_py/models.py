"""
ProjectX Data Models

Author: TexasCoding
Date: June 2025

This module contains all data model classes for the ProjectX API client.
"""

from dataclasses import dataclass


@dataclass
class Instrument:
    """
    Represents a tradeable financial instrument/contract.

    Attributes:
        id (str): Unique contract identifier used in API calls
        name (str): Contract name/symbol (e.g., "MGCH25")
        description (str): Human-readable description of the contract
        tickSize (float): Minimum price movement (e.g., 0.1)
        tickValue (float): Dollar value per tick movement
        activeContract (bool): Whether the contract is currently active for trading

    Example:
        >>> print(f"Trading {instrument.name}")
        >>> print(
        ...     f"Tick size: ${instrument.tickSize}, Tick value: ${instrument.tickValue}"
        ... )
    """

    id: str
    name: str
    description: str
    tickSize: float
    tickValue: float
    activeContract: bool
    symbolId: str | None = None


@dataclass
class Account:
    """
    Represents a trading account with balance and permissions.

    Attributes:
        id (int): Unique account identifier
        name (str): Account name/label
        balance (float): Current account balance in dollars
        canTrade (bool): Whether trading is enabled for this account
        isVisible (bool): Whether the account is visible in the interface
        simulated (bool): Whether this is a simulated/demo account

    Example:
        >>> print(f"Account: {account.name}")
        >>> print(f"Balance: ${account.balance:,.2f}")
        >>> print(f"Trading enabled: {account.canTrade}")
    """

    id: int
    name: str
    balance: float
    canTrade: bool
    isVisible: bool
    simulated: bool


@dataclass
class Order:
    """
    Represents a trading order with all its details.

    Attributes:
        id (int): Unique order identifier
        accountId (int): Account that placed the order
        contractId (str): Contract being traded
        creationTimestamp (str): When the order was created (ISO format)
        updateTimestamp (Optional[str]): When the order was last updated
        status (int): Order status code:
            0=Unknown, 1=Pending, 2=Filled, 3=Cancelled, 4=Rejected
        type (int): Order type:
            1=Limit, 2=Market, 4=Stop, 5=TrailingStop, 6=JoinBid, 7=JoinAsk
        side (int): Order side: 0=Buy, 1=Sell
        size (int): Number of contracts
        fillVolume (Optional[int]): Number of contracts filled (partial fills)
        limitPrice (Optional[float]): Limit price (for limit orders)
        stopPrice (Optional[float]): Stop price (for stop orders)

    Example:
        >>> side_str = "Buy" if order.side == 0 else "Sell"
        >>> print(f"Order {order.id}: {side_str} {order.size} {order.contractId}")
    """

    id: int
    accountId: int
    contractId: str
    creationTimestamp: str
    updateTimestamp: str | None
    status: int
    type: int
    side: int
    size: int
    fillVolume: int | None = None
    limitPrice: float | None = None
    stopPrice: float | None = None


@dataclass
class OrderPlaceResponse:
    """
    Response from placing an order.

    Attributes:
        orderId (int): ID of the newly created order
        success (bool): Whether the order placement was successful
        errorCode (int): Error code (0 = success)
        errorMessage (Optional[str]): Error message if placement failed

    Example:
        >>> if response.success:
        ...     print(f"Order placed successfully with ID: {response.orderId}")
        ... else:
        ...     print(f"Order failed: {response.errorMessage}")
    """

    orderId: int
    success: bool
    errorCode: int
    errorMessage: str | None


@dataclass
class Position:
    """
    Represents an open trading position.

    Attributes:
        id (int): Unique position identifier
        accountId (int): Account holding the position
        contractId (str): Contract of the position
        creationTimestamp (str): When the position was opened (ISO format)
        type (int): Position type code (1=LONG, 2=SHORT)
        size (int): Position size (number of contracts, always positive)
        averagePrice (float): Average entry price of the position

    Note:
        This model contains only the fields returned by ProjectX API.
        For P&L calculations, use PositionManager.calculate_position_pnl() method.

    Example:
        >>> direction = "LONG" if position.type == 1 else "SHORT"
        >>> print(
        ...     f"{direction} {position.size} {position.contractId} @ ${position.averagePrice}"
        ... )
    """

    id: int
    accountId: int
    contractId: str
    creationTimestamp: str
    type: int
    size: int
    averagePrice: float


@dataclass
class Trade:
    """
    Represents an executed trade with P&L information.

    Attributes:
        id (int): Unique trade identifier
        accountId (int): Account that executed the trade
        contractId (str): Contract that was traded
        creationTimestamp (str): When the trade was executed (ISO format)
        price (float): Execution price
        profitAndLoss (Optional[float]): Realized P&L (None for half-turn trades)
        fees (float): Trading fees/commissions
        side (int): Trade side: 0=Buy, 1=Sell
        size (int): Number of contracts traded
        voided (bool): Whether the trade was voided/cancelled
        orderId (int): ID of the order that generated this trade

    Note:
        A profitAndLoss value of None indicates a "half-turn" trade, meaning
        this trade opened or added to a position rather than closing it.

    Example:
        >>> side_str = "Buy" if trade.side == 0 else "Sell"
        >>> pnl_str = f"${trade.profitAndLoss}" if trade.profitAndLoss else "Half-turn"
        >>> print(f"{side_str} {trade.size} @ ${trade.price} - P&L: {pnl_str}")
    """

    id: int
    accountId: int
    contractId: str
    creationTimestamp: str
    price: float
    profitAndLoss: float | None  # null value indicates a half-turn trade
    fees: float
    side: int
    size: int
    voided: bool
    orderId: int


@dataclass
class BracketOrderResponse:
    """
    Response from placing a bracket order with entry, stop loss, and take profit.

    Attributes:
        success (bool): Whether the bracket order was successfully placed
        entry_order_id (Optional[int]): ID of the entry order
        stop_order_id (Optional[int]): ID of the stop loss order
        target_order_id (Optional[int]): ID of the take profit order
        entry_price (float): Entry price used
        stop_loss_price (float): Stop loss price used
        take_profit_price (float): Take profit price used
        entry_response (OrderPlaceResponse): Response from entry order
        stop_response (Optional[OrderPlaceResponse]): Response from stop loss order
        target_response (Optional[OrderPlaceResponse]): Response from take profit order
        error_message (Optional[str]): Error message if bracket order failed

    Example:
        >>> if response.success:
        ...     print(f"Bracket order placed successfully:")
        ...     print(f"  Entry: {response.entry_order_id} @ ${response.entry_price}")
        ...     print(f"  Stop: {response.stop_order_id} @ ${response.stop_loss_price}")
        ...     print(
        ...         f"  Target: {response.target_order_id} @ ${response.take_profit_price}"
        ...     )
        ... else:
        ...     print(f"Bracket order failed: {response.error_message}")
    """

    success: bool
    entry_order_id: int | None
    stop_order_id: int | None
    target_order_id: int | None
    entry_price: float
    stop_loss_price: float
    take_profit_price: float
    entry_response: "OrderPlaceResponse | None"
    stop_response: "OrderPlaceResponse | None"
    target_response: "OrderPlaceResponse | None"
    error_message: str | None


# Configuration classes
@dataclass
class ProjectXConfig:
    """
    Configuration settings for the ProjectX client.

    Attributes:
        api_url (str): Base URL for the API endpoints
        realtime_url (str): URL for real-time WebSocket connections
        user_hub_url (str): URL for user hub WebSocket
        market_hub_url (str): URL for market hub WebSocket
        timezone (str): Timezone for timestamp handling
        timeout_seconds (int): Request timeout in seconds
        retry_attempts (int): Number of retry attempts for failed requests
        retry_delay_seconds (float): Delay between retry attempts
        requests_per_minute (int): Rate limiting - requests per minute
        burst_limit (int): Rate limiting - burst limit
    """

    api_url: str = "https://api.topstepx.com/api"
    realtime_url: str = "wss://realtime.topstepx.com/api"
    user_hub_url: str = "https://rtc.topstepx.com/hubs/user"
    market_hub_url: str = "https://rtc.topstepx.com/hubs/market"
    timezone: str = "America/Chicago"
    timeout_seconds: int = 30
    retry_attempts: int = 3
    retry_delay_seconds: float = 2.0
    requests_per_minute: int = 60
    burst_limit: int = 10


@dataclass
class OrderUpdateEvent:
    orderId: int
    status: int  # 0=Unknown, 1=Pending, 2=Filled, 3=Cancelled, 4=Rejected
    fillVolume: int | None
    updateTimestamp: str


@dataclass
class PositionUpdateEvent:
    positionId: int
    contractId: str
    size: int
    averagePrice: float
    updateTimestamp: str


@dataclass
class MarketDataEvent:
    contractId: str
    lastPrice: float
    bid: float | None
    ask: float | None
    volume: int | None
    timestamp: str
