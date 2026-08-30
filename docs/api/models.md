# Data Models

Comprehensive data models and type definitions for trading operations, market data, and API responses.

## Overview

The models module provides strongly-typed data structures for all SDK operations including trading entities, API responses, configuration objects, and market data structures.


## Core Trading Models

### Account Information


```python
# Example account usage
async with ProjectX.from_env() as client:
    await client.authenticate()
    account = client.get_account_info()

    print(f"Account ID: {account.account_id}")
    print(f"Balance: ${account.balance:,.2f}")
    print(f"Available: ${account.available_balance:,.2f}")
    print(f"Margin Used: ${account.margin_used:,.2f}")
```

### Order Models




```python
# Example order models usage
from project_x_py import TradingSuite

async def order_models_example():
    suite = await TradingSuite.create(["MNQ"])
    mnq_context = suite["MNQ"]

    # Place order and get response
    response = await mnq_context.orders.place_limit_order(
        contract_id=mnq_context.instrument_info.id,
        side=0,  # Buy
        size=1,
        limit_price=21000.0
    )

    # Access response fields
    print(f"Order ID: {response.order_id}")
    print(f"Status: {response.status}")
    print(f"Message: {response.message}")

    # Get order details
    order = await mnq_context.orders.get_order(response.order_id)
    print(f"Order Size: {order.size}")
    print(f"Order Price: ${order.price:.2f}")
    print(f"Time in Force: {order.time_in_force}")

    await suite.disconnect()
```

### Position Models


```python
# Example position usage
async def position_models_example():
    suite = await TradingSuite.create(["MNQ"])
    mnq_positions = suite["MNQ"].positions

    position = await mnq_positions.get_position("MNQ")
    if position:
        print(f"Instrument: {position.instrument}")
        print(f"Size: {position.size}")
        print(f"Average Price: ${position.avg_price:.2f}")
        print(f"Unrealized P&L: ${position.unrealized_pnl:.2f}")
        print(f"Market Value: ${position.market_value:.2f}")
        print(f"Open Time: {position.open_time}")

    await suite.disconnect()
```

### Trade Models


```python
# Example trade usage
async def trade_models_example():
    suite = await TradingSuite.create(["MNQ"])

    # Get recent trades
    trades = await suite.client.get_recent_trades(limit=10)

    for trade in trades:
        print(f"Trade ID: {trade.trade_id}")
        print(f"Order ID: {trade.order_id}")
        print(f"Instrument: {trade.instrument}")
        print(f"Side: {trade.side}")
        print(f"Quantity: {trade.quantity}")
        print(f"Price: ${trade.price:.2f}")
        print(f"Commission: ${trade.commission:.2f}")
        print(f"Timestamp: {trade.timestamp}")
        print("---")

    await suite.disconnect()
```

## Market Data Models

### Instrument Information


```python
# Example instrument usage
async def instrument_models_example():
    async with ProjectX.from_env() as client:
        await client.authenticate()

        # Get instrument details
        instrument = await client.get_instrument("MNQ")

        print(f"Symbol: {instrument.symbol}")
        print(f"Description: {instrument.description}")
        print(f"Exchange: {instrument.exchange}")
        print(f"Currency: {instrument.currency}")
        print(f"Tick Size: {instrument.tick_size}")
        print(f"Tick Value: ${instrument.tick_value}")
        print(f"Contract Size: {instrument.contract_size}")
        print(f"Margin Requirement: ${instrument.margin_requirement:.2f}")
```

### OHLCV Bar Data

Market data is typically represented as Polars DataFrames with standardized column names:

```python
# Standard OHLCV DataFrame structure
import polars as pl

# Example DataFrame schema
bars_schema = {
    "timestamp": pl.Datetime,
    "open": pl.Float64,
    "high": pl.Float64,
    "low": pl.Float64,
    "close": pl.Float64,
    "volume": pl.Int64
}

# Example usage
async def bar_data_example():
    async with ProjectX.from_env() as client:
        await client.authenticate()

        # Get OHLCV bars (returns Polars DataFrame)
        bars = await client.get_bars("MNQ", days=5, interval=60)

        print(f"Data shape: {bars.shape}")
        print(f"Columns: {bars.columns}")
        print(f"Latest close: ${bars.tail(1)['close'].item():.2f}")

        # Access individual columns
        closes = bars["close"]
        volumes = bars["volume"]
        timestamps = bars["timestamp"]
```

### Quote Data

```python
# Quote data structure
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

@dataclass
class Quote:
    """Real-time quote data."""
    instrument: str
    bid: Decimal
    ask: Decimal
    bid_size: int
    ask_size: int
    timestamp: datetime

    @property
    def spread(self) -> Decimal:
        """Calculate bid-ask spread."""
        return self.ask - self.bid

    @property
    def mid_price(self) -> Decimal:
        """Calculate mid-point price."""
        return (self.bid + self.ask) / 2

# Example quote usage
async def quote_example():
    suite = await TradingSuite.create(["MNQ"])
    mnq_data = suite["MNQ"].data

    quote = await mnq_data.get_current_quote()
    print(f"Bid: ${quote.bid:.2f} x {quote.bid_size}")
    print(f"Ask: ${quote.ask:.2f} x {quote.ask_size}")
    print(f"Spread: ${quote.spread:.2f}")
    print(f"Mid: ${quote.mid_price:.2f}")

    await suite.disconnect()
```

### Tick Data

```python
@dataclass
class Tick:
    """Individual tick data."""
    instrument: str
    price: Decimal
    size: int
    timestamp: datetime
    side: str  # "buy", "sell", or "unknown"

# Example tick usage
async def tick_example():
    suite = await TradingSuite.create(["MNQ"])
    mnq_data = suite["MNQ"].data
    await mnq_data.subscribe_to_trades()

    # Wait for tick data
    await asyncio.sleep(30)

    ticks = await mnq_data.get_recent_ticks(count=20)
    for tick in ticks[-5:]:  # Last 5 ticks
        print(f"${tick.price:.2f} x {tick.size} ({tick.side}) @ {tick.timestamp}")

    await suite.disconnect()
```

## Configuration Models

### ProjectXConfig


```python
# Example configuration usage
from project_x_py.models import ProjectXConfig

# Create custom configuration
config = ProjectXConfig(
    api_key="your_api_key"  # pragma: allowlist secret,
    username="your_username",
    api_url="https://api.topstepx.com/api",
    timeout_seconds=60,
    retry_attempts=5,
    rate_limit_calls=100,
    enable_caching=True,
    cache_ttl_seconds=300
)

# Use configuration with client
async with ProjectX(config) as client:
    await client.authenticate()
    # Use client with custom config
```

### Component Configurations

```python
from project_x_py.types import (
    OrderManagerConfig,
    PositionManagerConfig,
    DataManagerConfig,
    OrderbookConfig
)

# Order Manager Configuration
order_config = OrderManagerConfig(
    max_concurrent_orders=10,
    default_timeout=30.0,
    retry_attempts=3,
    enable_order_tracking=True,
    track_performance=True
)

# Position Manager Configuration
position_config = PositionManagerConfig(
    track_unrealized=True,
    calculate_metrics=True,
    update_frequency=1.0,
    enable_trade_journal=True
)

# Data Manager Configuration
data_config = DataManagerConfig(
    max_bars_per_timeframe=1000,
    enable_tick_data=True,
    data_validation=True,
    auto_cleanup=True,
    compression_enabled=True
)

# OrderBook Configuration
orderbook_config = OrderbookConfig(
    max_depth_levels=10,
    max_trade_history=1000,
    enable_analytics=True,
    enable_pattern_detection=True,
)
```

## Response Models

### API Response Types




```python
# Example response handling
async def response_handling_example():
    try:
        async with ProjectX.from_env() as client:
            response = await client.authenticate()

            # Check response status
            if response.success:
                print(f"Authentication successful: {response.message}")
                print(f"User ID: {response.user_id}")
                print(f"Token expires: {response.expires_at}")
            else:
                print(f"Authentication failed: {response.error}")

    except ProjectXAuthenticationError as e:
        print(f"Auth error: {e}")
```

### Trading Response Types




```python
# Example trading response usage
async def trading_response_example():
    suite = await TradingSuite.create(["MNQ"])
    mnq_context = suite["MNQ"]

    # Place order and handle response
    response = await mnq_context.orders.place_limit_order(
        contract_id=mnq_context.instrument_info.id,
        side=0,
        size=1,
        limit_price=21000.0
    )

    if response.success:
        print(f"Order placed successfully: {response.order_id}")
    else:
        print(f"Order failed: {response.error_message}")
        print(f"Error code: {response.error_code}")

    await suite.disconnect()
```

## Statistics & Analytics Models

### Statistics Types




```python
# Example statistics usage
async def statistics_example():
    suite = await TradingSuite.create(["MNQ"])
    mnq_context = suite["MNQ"]

    # Get comprehensive statistics
    stats = await suite.get_stats()

    # Access typed statistics
    print(f"Health Score: {stats.health_score}")
    print(f"API Success Rate: {stats.api_success_rate:.1%}")
    print(f"Total API Calls: {stats.total_api_calls}")
    print(f"Memory Usage: {stats.memory_usage_mb:.1f} MB")

    # Component-specific statistics
    order_stats = await mnq_context.orders.get_stats()
    print(f"Total Orders: {order_stats.total_orders}")
    print(f"Fill Rate: {order_stats.fill_rate:.1%}")
    print(f"Average Fill Time: {order_stats.avg_fill_time_ms:.0f}ms")

    await suite.disconnect()
```

## Enum Types

### Order Types




```python
from project_x_py.types import OrderSide, OrderType, OrderStatus

# Example enum usage
async def enum_example():
    suite = await TradingSuite.create(["MNQ"])
    mnq_context = suite["MNQ"]

    # Using enums for type safety
    response = await mnq_context.orders.place_order(
        contract_id=mnq_context.instrument_info.id,
        side=OrderSide.BUY,           # Type-safe enum
        order_type=OrderType.LIMIT,   # Type-safe enum
        size=1,
        price=21000.0
    )

    # Check order status with enum
    if response.status == OrderStatus.FILLED:
        print("Order filled successfully")
    elif response.status == OrderStatus.PENDING:
        print("Order is pending")
    elif response.status == OrderStatus.REJECTED:
        print("Order was rejected")

    await suite.disconnect()
```

### Position Types



```python
from project_x_py.types import PositionType, PositionStatus

# Example position enum usage
async def position_enum_example():
    suite = await TradingSuite.create(["MNQ"])
    mnq_positions = suite["MNQ"].positions

    position = await mnq_positions.get_position("MNQ")
    if position:
        # Check position type
        if position.position_type == PositionType.LONG:
            print("Long position")
        elif position.position_type == PositionType.SHORT:
            print("Short position")

        # Check position status
        if position.status == PositionStatus.OPEN:
            print("Position is open")
        elif position.status == PositionStatus.CLOSED:
            print("Position is closed")

    await suite.disconnect()
```

## Custom Model Creation

### Creating Custom Models

```python
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

@dataclass
class CustomTradingSignal:
    """Custom trading signal model."""
    instrument: str
    signal_type: str  # "buy", "sell", "hold"
    strength: float   # 0.0 to 1.0
    price: Decimal
    timestamp: datetime
    indicators: dict[str, float]
    notes: Optional[str] = None

    def is_strong_signal(self, threshold: float = 0.7) -> bool:
        """Check if signal strength exceeds threshold."""
        return self.strength >= threshold

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "instrument": self.instrument,
            "signal_type": self.signal_type,
            "strength": self.strength,
            "price": float(self.price),
            "timestamp": self.timestamp.isoformat(),
            "indicators": self.indicators,
            "notes": self.notes
        }

# Example custom model usage
async def custom_model_example():
    from project_x_py.indicators import RSI, MACD

    suite = await TradingSuite.create(["MNQ"], timeframes=["5min"])
    mnq_data = suite["MNQ"].data

    # Get data and calculate indicators
    data = await mnq_data.get_data("5min")
    data_with_indicators = data.pipe(RSI, period=14).pipe(MACD)

    if len(data_with_indicators) > 0:
        latest = data_with_indicators.tail(1)

        # Create custom trading signal
        signal = CustomTradingSignal(
            instrument="MNQ",
            signal_type="buy" if latest["rsi_14"].item() < 30 else "hold",
            strength=0.8 if latest["rsi_14"].item() < 30 else 0.3,
            price=Decimal(str(latest["close"].item())),
            timestamp=datetime.now(),
            indicators={
                "rsi": latest["rsi_14"].item(),
                "macd": latest["macd"].item(),
                "signal": latest["macd_signal"].item()
            },
            notes="RSI oversold signal"
        )

        print(f"Signal: {signal.signal_type}")
        print(f"Strength: {signal.strength}")
        print(f"Is strong: {signal.is_strong_signal()}")

    await suite.disconnect()
```

## Model Validation

### Data Validation

```python
from pydantic import BaseModel, validator
from decimal import Decimal
from datetime import datetime

class ValidatedOrder(BaseModel):
    """Order model with validation."""
    instrument: str
    side: int
    size: int
    price: Decimal
    timestamp: datetime

    @validator('side')
    def validate_side(cls, v):
        if v not in [0, 1]:  # 0=Buy, 1=Sell
            raise ValueError('Side must be 0 (Buy) or 1 (Sell)')
        return v

    @validator('size')
    def validate_size(cls, v):
        if v <= 0:
            raise ValueError('Size must be positive')
        return v

    @validator('price')
    def validate_price(cls, v):
        if v <= 0:
            raise ValueError('Price must be positive')
        return v

# Example validation usage
try:
    order = ValidatedOrder(
        instrument="MNQ",
        side=0,
        size=1,
        price=Decimal("21000.0"),
        timestamp=datetime.now()
    )
    print("Order validation passed")
except ValueError as e:
    print(f"Validation error: {e}")
```

## Best Practices

### Model Usage

```python
# Good: Use type hints for better IDE support
from project_x_py.models import Order, Position
from typing import Optional

async def process_order(order: Order) -> Optional[Position]:
    # Type hints provide better IDE support
    if order.status == "filled":
        return await get_position_for_order(order.order_id)
    return None

# Good: Use enums for type safety
from project_x_py.types import OrderSide, OrderType

side = OrderSide.BUY  # Type-safe
order_type = OrderType.LIMIT  # Type-safe

# L Less safe: Using raw strings/integers
# side = 0  # What does 0 mean?
# order_type = "limit"  # Prone to typos
```

### Error Handling

```python
# Good: Handle model validation errors
try:
    suite = await TradingSuite.create(["MNQ"])
    mnq_context = suite["MNQ"]
    response = await mnq_context.orders.place_limit_order(
        contract_id=mnq_context.instrument_info.id,
        side=0,
        size=1,
        limit_price=21000.0
    )

    if not response.success:
        print(f"Order failed: {response.error_message}")

except ValidationError as e:
    print(f"Invalid order parameters: {e}")
except ProjectXOrderError as e:
    print(f"Order execution error: {e}")
```

## See Also

- [Configuration](../getting-started/configuration.md) - Configuration options
- [Trading Guide](../guide/orders.md) - Using models in trading operations
