"""
ProjectX Data Models

Author: @TexasCoding
Date: 2025-08-02

Overview:
    Contains all data model classes for the ProjectX API client. Provides
    comprehensive data structures for trading entities, configuration,
    and real-time events. All models use dataclasses for type safety
    and automatic serialization/deserialization.

Key Features:
    - Comprehensive trading entity models (Instrument, Order, Position, Trade)
    - Configuration models with default values
    - Real-time event models for WebSocket data
    - Type-safe dataclass implementations
    - Automatic serialization/deserialization
    - Comprehensive field documentation and examples

Data Models:
    - Trading Entities: Instrument, Order, Position, Trade, Account
    - Configuration: ProjectXConfig with default TopStepX endpoints
    - Responses: OrderPlaceResponse, BracketOrderResponse
    - Events: OrderUpdateEvent, PositionUpdateEvent, MarketDataEvent

Example Usage:
    ```python
    from project_x_py.models import (
        Instrument,
        Order,
        Position,
        Trade,
        Account,
        ProjectXConfig,
        OrderPlaceResponse,
    )

    # Create instrument model
    instrument = Instrument(
        id="CON.F.US.MNQ.U25",
        name="MNQU25",
        description="E-mini NASDAQ-100 Futures September 2025",
        tickSize=0.25,
        tickValue=0.50,
        activeContract=True,
    )

    # Create order model
    order = Order(
        id=12345,
        accountId=1001,
        contractId="CON.F.US.MNQ.U25",
        creationTimestamp="2024-01-01T10:00:00Z",
        updateTimestamp="2024-01-01T10:00:05Z",
        status=OrderStatus.OPEN,
        type=OrderType.LIMIT,
        side=OrderSide.BUY,
        size=5,
        limitPrice=2050.0,
    )

    # Create position model
    position = Position(
        id=67890,
        accountId=1001,
        contractId="CON.F.US.MNQ.U25",
        creationTimestamp="2024-01-01T10:00:00Z",
        type=PositionType.LONG,
        size=5,
        averagePrice=2050.0,
    )

    # Create configuration
    config = ProjectXConfig(
        api_url="https://api.topstepx.com/api",
        user_hub_url="https://rtc.topstepx.com/hubs/user",
        market_hub_url="https://rtc.topstepx.com/hubs/market",
        timezone="America/Chicago",
    )
    ```

Trading Entity Models:
    - Instrument: Tradeable financial instruments with tick information
    - Order: Trading orders with status, type, and execution details
    - Position: Open trading positions with size and average price
    - Trade: Executed trades with P&L and fee information
    - Account: Trading accounts with balance and permissions

Configuration Models:
    - ProjectXConfig: Client configuration with endpoints and settings
    - Default TopStepX endpoints for production use
    - Customizable for different ProjectX deployments
    - Comprehensive validation and error handling

Event Models:
    - OrderUpdateEvent: Real-time order status updates
    - PositionUpdateEvent: Real-time position changes
    - MarketDataEvent: Real-time market data updates

Model Features:
    - Type-safe dataclass implementations
    - Comprehensive field documentation
    - Automatic serialization/deserialization
    - Validation and error handling
    - Default values for optional fields
    - Enum support for status and type fields

See Also:
    - `config`: Configuration management utilities
    - `exceptions`: Error handling for model validation
    - `types`: Type definitions and protocols
"""

from collections.abc import Mapping
from dataclasses import dataclass, fields
from typing import Any, TypeVar, Union, cast

T = TypeVar("T")


def _from_api(  # noqa: UP047
    cls: type[T],
    data: Mapping[str, Any],
    aliases: Mapping[str, str] | None = None,
) -> T:
    """Build a dataclass from Gateway JSON, ignoring unknown additive fields."""
    values = dict(data)
    if aliases:
        for source, dest in aliases.items():
            if dest not in values and source in values:
                values[dest] = values[source]
    known = {field.name for field in fields(cast(Any, cls))}
    return cls(**{name: values[name] for name in known if name in values})


__all__ = [
    "Account",
    "BracketOrderResponse",
    "Instrument",
    "MarketDataEvent",
    "Order",
    "OrderPlaceResponse",
    "OrderUpdateEvent",
    "Position",
    "PositionUpdateEvent",
    "ProjectXConfig",
    "Trade",
]


@dataclass
class Instrument:
    """
    Represents a tradeable financial instrument/contract.

    Attributes:
        id (str): Unique contract identifier used in API calls
        name (str): Contract name/symbol (e.g., "MNQU25", "ESH25")
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

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "Instrument":
        """Create an Instrument from API data, ignoring additive unknown fields."""
        return _from_api(cls, data)


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

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "Account":
        """Create an Account from API data, ignoring additive unknown fields."""
        return _from_api(cls, data)


@dataclass
class Order:
    """
    Represents a trading order with all its details.

    Attributes:
        id (int): Unique order identifier
        accountId (int): Account that placed the order
        contractId (str): Contract being traded
        symbolId (Optional[str]): Symbol ID corresponding to the contract
        creationTimestamp (str): When the order was created (ISO format)
        updateTimestamp (Optional[str]): When the order was last updated
        status (int): Order status code (OrderStatus enum):
            0=None, 1=Open, 2=Filled, 3=Cancelled, 4=Expired, 5=Rejected,
            6=Pending, 7=PendingCancellation, 8=Suspended
        type (int): Order type (OrderType enum):
            0=Unknown, 1=Limit, 2=Market, 3=StopLimit, 4=Stop, 5=TrailingStop, 6=JoinBid, 7=JoinAsk
        side (int): Order side (OrderSide enum): 0=Bid, 1=Ask
        size (int): Number of contracts
        fillVolume (Optional[int]): Number of contracts filled (partial fills)
        limitPrice (Optional[float]): Limit price (for limit orders)
        stopPrice (Optional[float]): Stop price (for stop orders)
        filledPrice (Optional[float]): The price at which the order was filled, if any
        customTag (Optional[str]): Custom tag associated with the order, if any

    Example:
        >>> side_str = "Bid" if order.side == 0 else "Ask"
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
    symbolId: str | None = None
    fillVolume: int | None = None
    limitPrice: float | None = None
    stopPrice: float | None = None
    filledPrice: float | None = None
    customTag: str | None = None

    @property
    def is_open(self) -> bool:
        """Check if order is still open."""
        return self.status == 1  # OrderStatus.OPEN

    @property
    def is_filled(self) -> bool:
        """Check if order is completely filled."""
        return self.status == 2  # OrderStatus.FILLED

    @property
    def is_cancelled(self) -> bool:
        """Check if order was cancelled."""
        return self.status == 3  # OrderStatus.CANCELLED

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "Order":
        """Create an Order from API data, ignoring additive unknown fields."""
        return _from_api(cls, data, aliases={"filledSize": "fillVolume"})

    @property
    def is_rejected(self) -> bool:
        """Check if order was rejected."""
        return self.status == 5  # OrderStatus.REJECTED

    @property
    def is_working(self) -> bool:
        """Check if order is working (open or pending)."""
        return self.status in (
            1,
            6,
            7,
            8,
        )  # OPEN, PENDING, PENDING_CANCELLATION, SUSPENDED

    @property
    def is_terminal(self) -> bool:
        """Check if order is in a terminal state."""
        return self.status in (2, 3, 4, 5)  # FILLED, CANCELLED, EXPIRED, REJECTED

    @property
    def is_buy(self) -> bool:
        """Check if this is a buy order."""
        return self.side == 0  # OrderSide.BUY

    @property
    def is_sell(self) -> bool:
        """Check if this is a sell order."""
        return self.side == 1  # OrderSide.SELL

    @property
    def side_str(self) -> str:
        """Get order side as string."""
        return "BUY" if self.is_buy else "SELL"

    @property
    def type_str(self) -> str:
        """Get order type as string."""
        type_map = {
            1: "LIMIT",
            2: "MARKET",
            3: "STOP_LIMIT",
            4: "STOP",
            5: "TRAILING_STOP",
            6: "JOIN_BID",
            7: "JOIN_ASK",
        }
        return type_map.get(self.type, "UNKNOWN")

    @property
    def status_str(self) -> str:
        """Get order status as string."""
        status_map = {
            0: "NONE",
            1: "OPEN",
            2: "FILLED",
            3: "CANCELLED",
            4: "EXPIRED",
            5: "REJECTED",
            6: "PENDING",
            7: "PENDING_CANCELLATION",
            8: "SUSPENDED",
        }
        return status_map.get(self.status, "UNKNOWN")

    @property
    def filled_percent(self) -> float:
        """Get percentage of order that has been filled."""
        if self.fillVolume is None or self.size == 0:
            return 0.0
        return (self.fillVolume / self.size) * 100

    @property
    def remaining_size(self) -> int:
        """Get remaining unfilled size."""
        if self.fillVolume is None:
            return self.size
        return self.size - self.fillVolume

    @property
    def symbol(self) -> str:
        """Extract symbol from contract ID."""
        if "." in self.contractId:
            parts = self.contractId.split(".")
            if len(parts) >= 4:
                return parts[3]
        return self.contractId


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
        type (int): Position type code (PositionType enum):
            0=UNDEFINED, 1=LONG, 2=SHORT
        size (int): Position size (number of contracts, always positive)
        averagePrice (float): Average entry price of the position
        contractDisplayName (Optional[str]): Human-readable contract display name

    Note:
        This model contains only the fields returned by ProjectX API.
        For P&L calculations, use PositionManager.calculate_position_pnl() method.

    Example:
        >>> direction = "LONG" if position.type == PositionType.LONG else "SHORT"
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
    contractDisplayName: str | None = None

    # Allow dict-like access for compatibility in tests/utilities
    def __getitem__(self, key: str) -> Union[int, str, float, None]:
        value = getattr(self, key)
        if value is None or isinstance(value, int | str | float):
            return value
        else:
            raise TypeError(
                f"Attribute {key} has type {type(value)}, expected int, str, or float"
            )

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "Position":
        """Create a Position from API data, ignoring additive unknown fields."""
        return _from_api(cls, data)

    @property
    def is_long(self) -> bool:
        """Check if this is a long position."""
        return self.type == 1  # PositionType.LONG

    @property
    def is_short(self) -> bool:
        """Check if this is a short position."""
        return self.type == 2  # PositionType.SHORT

    @property
    def direction(self) -> str:
        """Get position direction as string."""
        if self.is_long:
            return "LONG"
        elif self.is_short:
            return "SHORT"
        else:
            return "UNDEFINED"

    @property
    def symbol(self) -> str:
        """Extract symbol from contract ID (e.g., 'MNQ' from 'CON.F.US.MNQ.H25')."""
        # Handle different contract ID formats
        if "." in self.contractId:
            parts = self.contractId.split(".")
            if len(parts) >= 4:
                return parts[3]  # Standard format: CON.F.US.MNQ.H25
        return self.contractId  # Fallback to full contract ID

    @property
    def signed_size(self) -> int:
        """Get size with sign (negative for short positions)."""
        return -self.size if self.is_short else self.size

    @property
    def total_cost(self) -> float:
        """Calculate total position cost."""
        return self.size * self.averagePrice

    def unrealized_pnl(self, current_price: float, tick_value: float = 1.0) -> float:
        """
        Calculate unrealized P&L given current price.

        Args:
            current_price: Current market price
            tick_value: Value per point move (default: 1.0)

        Returns:
            Unrealized P&L in dollars
        """
        if self.is_long:
            return (current_price - self.averagePrice) * self.size * tick_value
        elif self.is_short:
            return (self.averagePrice - current_price) * self.size * tick_value
        else:
            return 0.0


@dataclass(slots=True)
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
        commissions (Optional[float]): Gateway commission amount, if provided
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
    commissions: float | None = None

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "Trade":
        """Create a Trade from API data, mapping commissions and ignoring extras."""
        return _from_api(cls, data, aliases={"commissions": "fees"})


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

    Default URLs are set for TopStepX endpoints. For custom ProjectX endpoints,
    update the URLs accordingly using create_custom_config() or direct assignment.

    TopStepX (Default):
    - user_hub_url: "https://rtc.topstepx.com/hubs/user"
    - market_hub_url: "https://rtc.topstepx.com/hubs/market"

    Attributes:
        api_url (str): Base URL for the API endpoints
        realtime_url (str): Legacy field; live hubs use user_hub_url and market_hub_url
        user_hub_url (str): URL for user hub WebSocket (accounts, positions, orders)
        market_hub_url (str): URL for market hub WebSocket (quotes, trades, depth)
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
    status: int  # OrderStatus: 0=None, 1=Open, 2=Filled, 3=Cancelled, 4=Expired, 5=Rejected, 6=Pending
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
