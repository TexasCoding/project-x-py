# Risk Manager API

Comprehensive async risk management system with position sizing, risk validation, stop-loss management, and portfolio risk monitoring.

## Overview

The RiskManager provides automated risk management capabilities for trading operations. It handles position sizing calculations, trade validation against risk limits, automatic stop-loss and take-profit order placement, and comprehensive risk analytics.

**ManagedTrade remains the recommended path** for entries (sizing, validation, OCO stop/target). Enabling `features=["risk_manager"]` also turns on an `OrderManager` auto-gate: entry `place_*` calls run `validate_trade` before HTTP and refuse invalid trades. Protective orders (stop / stop-limit / trailing stop) skip the gate. Use the auto-gate as a backstop, not as the primary risk workflow.

**Key Features:**
- Risk-based position sizing with Kelly criterion support
- Daily loss limits and trade count restrictions
- Automatic stop-loss and take-profit order placement
- Real-time portfolio risk monitoring
- Trailing stop functionality
- Comprehensive risk metrics and analytics
- Statistics integration for performance tracking

## Quick Start

```python
from project_x_py import TradingSuite, Features

async def basic_risk_management():
    # Enable risk manager feature
    suite = await TradingSuite.create(
        ["MNQ"],
        features=[Features.RISK_MANAGER]
    )

    # Access the integrated risk manager
    risk = suite["MNQ"].risk_manager

    # Calculate position size based on risk
    sizing = await risk.calculate_position_size(
        entry_price=21000.0,
        stop_loss=20975.0,
        risk_percent=0.02  # Risk 2% of account
    )

    print(f"Position size: {sizing.position_size}")
    print(f"Risk amount: ${sizing.risk_amount:.2f}")

    await suite.disconnect()
```

## Classes

### RiskManager

Core risk management class that handles all risk-related operations.

#### Constructor

```python
RiskManager(
    project_x: ProjectXClientProtocol,
    order_manager: OrderManagerProtocol,
    event_bus: EventBus,
    position_manager: PositionManagerProtocol | None = None,
    config: RiskConfig | None = None,
    data_manager: RealtimeDataManagerProtocol | None = None
)
```

**Parameters:**
- `project_x`: ProjectX client instance for account and instrument operations
- `order_manager`: Order manager for placing and managing protective orders
- `event_bus`: Event bus for risk-related events and notifications
- `position_manager`: Position manager (can be set later via `set_position_manager()`)
- `config`: Risk configuration (uses defaults if not provided)
- `data_manager`: Optional data manager for market price fetching and ATR calculations

#### Methods

##### Position Sizing

###### `calculate_position_size()`

```python
async def calculate_position_size(
    self,
    entry_price: float,
    stop_loss: float,
    risk_amount: float | None = None,
    risk_percent: float | None = None,
    instrument: Instrument | None = None,
    use_kelly: bool | None = None,
) -> PositionSizingResponse
```

Calculate optimal position size based on risk parameters.

**Parameters:**
- `entry_price`: Planned entry price
- `stop_loss`: Stop loss price
- `risk_amount`: Fixed dollar amount to risk (overrides percentage)
- `risk_percent`: Percentage of account to risk (defaults to config value)
- `instrument`: Instrument for tick size calculation
- `use_kelly`: Override config to use/not use Kelly criterion

**Returns:** `PositionSizingResponse` with calculated size and risk metrics

**Example:**
```python
# Risk-based position sizing
sizing = await risk_manager.calculate_position_size(
    entry_price=21000.0,
    stop_loss=20975.0,
    risk_percent=0.01,  # Risk 1% of account
)

print(f"Position size: {sizing.position_size} contracts")
print(f"Risk amount: ${sizing.risk_amount:.2f}")
print(f"Risk percent: {sizing.risk_percent:.2%}")
```

##### Trade Validation

###### `validate_trade()`

```python
async def validate_trade(
    self,
    order: Order,
    current_positions: list[Position] | None = None,
) -> RiskValidationResponse
```

Validate a trade against all configured risk rules.

**Parameters:**
- `order`: Order to validate against risk limits
- `current_positions`: Current positions (fetched if not provided)

**Returns:** `RiskValidationResponse` with validation result and detailed reasons

**Validation Checks:**
- Daily trade count limit
- Maximum concurrent positions
- Position size limits
- Daily loss limits (dollar amount and percentage)
- Portfolio risk concentration
- Trading hours restrictions
- Correlated position limits

**Example:**
```python
# Create mock order for validation
mock_order = Order(
    id=0,
    contractId="CON.F.US.MNQ.U25",
    side=OrderSide.BUY,
    size=2,
    # ... other required fields
)

# Validate against risk rules
validation = await risk_manager.validate_trade(mock_order)

if validation.is_valid:
    print("Trade approved")
    print(f"Current daily trades: {validation.daily_trades}")
else:
    print(f"Trade rejected: {validation.reasons}")
    print(f"Warnings: {validation.warnings}")
```

##### Risk Order Management

###### `attach_risk_orders()`

```python
async def attach_risk_orders(
    self,
    position: Position,
    stop_loss: float | None = None,
    take_profit: float | None = None,
    use_trailing: bool | None = None,
) -> dict[str, Any]
```

Automatically attach stop-loss and take-profit orders to a position.

**Parameters:**
- `position`: Position to protect with risk orders
- `stop_loss`: Override stop loss price (calculated if not provided)
- `take_profit`: Override take profit price (calculated if not provided)
- `use_trailing`: Override trailing stop configuration

**Returns:** Dictionary with order details and risk metrics

**Stop Loss Calculation:**
- `"fixed"`: Uses `default_stop_distance` **ticks** (`distance * tickSize`; tickSize defaults to `1.0` if no instrument)
- `"atr"`: Uses ATR * `default_stop_atr_multiplier`
- `"percentage"`: Uses percent of entry (`entry * pct / 100`)

**Example:**
```python
# Attach risk orders to existing position
risk_orders = await risk_manager.attach_risk_orders(
    position=current_position,
    stop_loss=20975.0,  # Custom stop price
    take_profit=21050.0  # Custom target price
)

if risk_orders["bracket_order"].success:
    print(f"Stop order: {risk_orders['bracket_order'].stop_order_id}")
    print(f"Target order: {risk_orders['bracket_order'].target_order_id}")
    print(f"Risk/reward ratio: {risk_orders['risk_reward_ratio']}")
```

###### `adjust_stops()`

```python
async def adjust_stops(
    self,
    position: Position,
    new_stop: float,
    order_id: str | None = None,
) -> bool
```

Adjust stop-loss order for a position.

**Parameters:**
- `position`: Position whose stop loss to adjust
- `new_stop`: New stop loss price
- `order_id`: Specific order ID to modify (found automatically if not provided)

**Returns:** `True` if adjustment successful

**Example:**
```python
# Adjust stop loss to breakeven
success = await risk_manager.adjust_stops(
    position=current_position,
    new_stop=current_position.averagePrice
)

if success:
    print("Stop adjusted to breakeven")
```

##### Risk Analysis

###### `get_risk_metrics()`

```python
async def get_risk_metrics(self) -> RiskAnalysisResponse
```

Get comprehensive risk metrics and portfolio analysis.

**Returns:** `RiskAnalysisResponse` with detailed risk metrics

**Metrics Included:**
- Current risk exposure and limits
- Daily loss tracking
- Position count and limits
- Win rate and profit factor
- Sharpe ratio and max drawdown
- Individual position risks

**Example:**
```python
# Get comprehensive risk analysis
metrics = await risk_manager.get_risk_metrics()

print(f"Current risk: ${metrics.current_risk:.2f}")
print(f"Daily loss: ${metrics.daily_loss:.2f}")
print(f"Position count: {metrics.position_count}/{metrics.position_limit}")
print(f"Win rate: {metrics.win_rate:.1%}")
print(f"Sharpe ratio: {metrics.sharpe_ratio:.2f}")
print(f"Max drawdown: {metrics.max_drawdown:.2f}")

# Position-specific risks
for pos_risk in metrics.position_risks:
    print(f"{pos_risk['symbol']}: ${pos_risk['risk_amount']:.2f} "
          f"({pos_risk['risk_percent']:.2%})")
```

##### Configuration Management

###### `set_position_manager()`

```python
def set_position_manager(self, position_manager: PositionManagerProtocol) -> None
```

Set the position manager to resolve circular dependencies.

**Parameters:**
- `position_manager`: Position manager instance for risk calculations

**Note:** This method must be called before any position-related operations if not provided in constructor.

##### Stop Loss Calculations

###### `calculate_stop_loss()`

```python
async def calculate_stop_loss(
    self,
    entry_price: float,
    side: OrderSide,
    atr_value: float | None = None,
    instrument: Instrument | None = None,
) -> float
```

Calculate stop loss price based on configuration.

**Parameters:**
- `entry_price`: Entry price for the trade
- `side`: Order side (BUY or SELL)
- `atr_value`: ATR value for dynamic stop calculation
- `instrument`: Optional instrument (tickSize used for fixed stops; defaults to `1.0`)

**Returns:** Calculated stop loss price

**Example:**
```python
# Calculate stop loss for long position
stop_price = await risk_manager.calculate_stop_loss(
    entry_price=21000.0,
    side=OrderSide.BUY,
    atr_value=15.0  # Current ATR
)
print(f"Stop loss: {stop_price}")
```

###### `calculate_take_profit()`

```python
async def calculate_take_profit(
    self,
    entry_price: float,
    stop_loss: float,
    side: OrderSide,
    risk_reward_ratio: float | None = None,
) -> float
```

Calculate take profit price based on risk/reward ratio.

**Parameters:**
- `entry_price`: Entry price for the trade
- `stop_loss`: Stop loss price
- `side`: Order side (BUY or SELL)
- `risk_reward_ratio`: Risk/reward ratio (uses config default if None)

**Returns:** Calculated take profit price

##### Trade Recording

###### `record_trade_result()`

```python
async def record_trade_result(
    self,
    position_id: str,
    pnl: float,
    duration_seconds: int,
) -> None
```

Record trade result for risk analysis and Kelly criterion calculations.

**Parameters:**
- `position_id`: Position identifier
- `pnl`: Profit/loss amount
- `duration_seconds`: Trade duration in seconds

**Example:**
```python
# Record completed trade
await risk_manager.record_trade_result(
    position_id="pos_123",
    pnl=150.0,  # $150 profit
    duration_seconds=3600  # 1 hour trade
)
```

###### `add_trade_result()`

```python
async def add_trade_result(
    self,
    instrument: str,
    pnl: float,
    entry_price: float | None = None,
    exit_price: float | None = None,
    size: int | None = None,
    side: OrderSide | None = None,
) -> None
```

Add trade result with detailed information to history.

**Parameters:**
- `instrument`: Instrument identifier
- `pnl`: Profit/loss amount
- `entry_price`: Entry price
- `exit_price`: Exit price
- `size`: Position size
- `side`: Order side

##### Portfolio Analysis

###### `analyze_portfolio_risk()`

```python
async def analyze_portfolio_risk(self) -> dict[str, Any]
```

Analyze overall portfolio risk and concentration.

**Returns:** Dictionary with portfolio risk analysis

**Example:**
```python
analysis = await risk_manager.analyze_portfolio_risk()
print(f"Total risk: ${analysis['total_risk']:.2f}")
print(f"Position count: {len(analysis['position_risks'])}")
```

###### `analyze_trade_risk()`

```python
async def analyze_trade_risk(
    self,
    instrument: str,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    position_size: int,
) -> dict[str, Any]
```

Analyze risk/reward for a specific trade setup.

**Parameters:**
- `instrument`: Instrument identifier
- `entry_price`: Planned entry price
- `stop_loss`: Stop loss price
- `take_profit`: Take profit price
- `position_size`: Position size in contracts

**Returns:** Dictionary with risk/reward analysis

##### Cleanup

###### `cleanup()`

```python
async def cleanup(self) -> None
```

Clean up all resources and cancel active tasks (trailing stops, monitoring).

**Example:**
```python
# Proper cleanup before shutdown
await risk_manager.cleanup()
```

### RiskConfig

Configuration dataclass for risk management parameters.

```python
@dataclass
class RiskConfig:
    # Per-trade risk limits
    max_risk_per_trade: Decimal = Decimal("0.01")  # 1% per trade
    max_risk_per_trade_amount: Decimal | None = None  # Dollar limit

    # Daily risk limits
    max_daily_loss: Decimal = Decimal("0.03")  # 3% daily loss
    max_daily_loss_amount: Decimal | None = None  # Dollar limit
    max_daily_trades: int = 10  # Maximum trades per day

    # Position limits
    max_position_size: int = 10  # Maximum contracts per position
    max_positions: int = 3  # Maximum concurrent positions
    max_portfolio_risk: Decimal = Decimal("0.05")  # 5% total portfolio risk

    # Stop-loss configuration
    use_stop_loss: bool = True
    stop_loss_type: str = "fixed"  # "fixed", "atr", "percentage"
    default_stop_distance: Decimal = Decimal("50")  # Fixed = ticks (× tickSize); percentage = percent of entry
    default_stop_atr_multiplier: Decimal = Decimal("2.0")  # ATR multiplier

    # Take-profit configuration
    use_take_profit: bool = True
    default_risk_reward_ratio: Decimal = Decimal("2.0")  # 1:2 risk/reward

    # Trailing stop configuration
    use_trailing_stops: bool = True
    trailing_stop_distance: Decimal = Decimal("20")  # Points behind price
    trailing_stop_trigger: Decimal = Decimal("30")  # Profit points before trailing

    # Advanced features
    scale_in_enabled: bool = False  # Allow position scaling
    scale_out_enabled: bool = True  # Allow partial exits
    martingale_enabled: bool = False  # DANGEROUS: Double down on losses

    # Time-based rules
    restrict_trading_hours: bool = False
    allowed_trading_hours: list[tuple[str, str]] = [("09:30", "16:00")]
    avoid_news_events: bool = True
    news_blackout_minutes: int = 30  # Minutes before/after news

    # Correlation limits
    max_correlated_positions: int = 2  # Max correlated instruments
    correlation_threshold: Decimal = Decimal("0.7")  # Correlation coefficient

    # Kelly Criterion parameters
    use_kelly_criterion: bool = False
    kelly_fraction: Decimal = Decimal("0.25")  # Use 25% of Kelly recommendation
    min_trades_for_kelly: int = 30  # Minimum trades before using Kelly
```

**Example Configuration:**
```python
from project_x_py.risk_manager import RiskConfig
from decimal import Decimal

# Conservative risk configuration
conservative_config = RiskConfig(
    max_risk_per_trade=Decimal("0.005"),  # 0.5% per trade
    max_daily_loss=Decimal("0.02"),  # 2% daily loss limit
    max_daily_trades=5,  # Max 5 trades per day
    max_position_size=2,  # Max 2 contracts
    max_positions=2,  # Max 2 concurrent positions
    default_stop_distance=Decimal("25"),  # Tight 25-point stops
    default_risk_reward_ratio=Decimal("3.0"),  # 1:3 risk/reward
    use_trailing_stops=True,
    trailing_stop_distance=Decimal("15"),
    use_kelly_criterion=False  # Disable Kelly for conservative approach
)

# Aggressive risk configuration
aggressive_config = RiskConfig(
    max_risk_per_trade=Decimal("0.02"),  # 2% per trade
    max_daily_loss=Decimal("0.05"),  # 5% daily loss limit
    max_daily_trades=20,  # Max 20 trades per day
    max_position_size=10,  # Max 10 contracts
    max_positions=5,  # Max 5 concurrent positions
    stop_loss_type="atr",  # ATR-based stops
    default_stop_atr_multiplier=Decimal("1.5"),  # 1.5x ATR
    use_kelly_criterion=True,  # Enable Kelly sizing
    kelly_fraction=Decimal("0.5"),  # Use 50% of Kelly
    scale_in_enabled=True,  # Allow scaling into positions
)
```

### ManagedTrade

Context manager for risk-managed trade execution with automatic position sizing and risk control.

```python
class ManagedTrade:
    def __init__(
        self,
        risk_manager: RiskManager,
        order_manager: OrderManagerProtocol,
        position_manager: PositionManagerProtocol,
        instrument_id: str,
        data_manager: Any | None = None,
        event_bus: Any | None = None,
        max_risk_percent: float | None = None,
        max_risk_amount: float | None = None,
    )
```

**Parameters:**
- `risk_manager`: Risk manager instance for calculations and validation
- `order_manager`: Order manager for placing trades
- `position_manager`: Position manager for position tracking
- `instrument_id`: Instrument/contract ID to trade
- `data_manager`: Optional data manager for market price fetching
- `event_bus`: Optional event bus for event-driven order tracking
- `max_risk_percent`: Override max risk percentage for this trade
- `max_risk_amount`: Override max risk dollar amount for this trade

#### Methods

##### Position Entry

###### `enter_long()`

```python
async def enter_long(
    self,
    entry_price: float | None = None,
    stop_loss: float | None = None,
    take_profit: float | None = None,
    size: int | None = None,
    order_type: OrderType = OrderType.MARKET,
) -> dict[str, Any]
```

Enter a long position with automatic risk management.

**Parameters:**
- `entry_price`: Limit order price (None for market entry)
- `stop_loss`: Stop loss price (auto-calculated if not provided)
- `take_profit`: Take profit price (auto-calculated if not provided)
- `size`: Position size (auto-calculated if not provided)
- `order_type`: Order type (MARKET or LIMIT)

**Returns:** Dictionary with entry details, orders, and risk metrics

**Example:**
```python
async with ManagedTrade(
    risk_manager=suite["MNQ"].risk_manager,
    order_manager=suite["MNQ"].orders,
    position_manager=suite["MNQ"].positions,
    instrument_id=suite["MNQ"].instrument_info.id,
    max_risk_percent=0.02
) as trade:

    # Enter long position with automatic sizing and risk management
    result = await trade.enter_long(
        entry_price=21000.0,  # Limit entry
        stop_loss=20975.0,    # 25-point stop
        take_profit=21050.0,  # 50-point target
        order_type=OrderType.LIMIT
    )

    if result["entry_order"]:
        print(f"Long position entered:")
        print(f"  Size: {result['size']} contracts")
        print(f"  Risk: ${result['risk_amount']:.2f}")
        print(f"  Entry: {result['entry_order'].id}")
        print(f"  Stop: {result['stop_order'].id if result['stop_order'] else 'None'}")
        print(f"  Target: {result['target_order'].id if result['target_order'] else 'None'}")
```

###### `enter_short()`

```python
async def enter_short(
    self,
    entry_price: float | None = None,
    stop_loss: float | None = None,
    take_profit: float | None = None,
    size: int | None = None,
    order_type: OrderType = OrderType.MARKET,
) -> dict[str, Any]
```

Enter a short position with automatic risk management.

**Parameters:** Same as `enter_long()`

**Returns:** Dictionary with entry details, orders, and risk metrics

##### Position Management

###### `scale_in()`

```python
async def scale_in(
    self,
    additional_size: int,
    new_stop_loss: float | None = None,
) -> dict[str, Any]
```

Scale into existing position with risk validation.

**Parameters:**
- `additional_size`: Additional contracts to add
- `new_stop_loss`: New stop loss for entire position

**Requires:** `scale_in_enabled=True` in RiskConfig

###### `scale_out()`

```python
async def scale_out(
    self,
    exit_size: int,
    limit_price: float | None = None,
) -> dict[str, Any]
```

Scale out of position with partial exit.

**Parameters:**
- `exit_size`: Number of contracts to exit
- `limit_price`: Limit price for exit (market if None)

###### `close_position()`

```python
async def close_position(self) -> dict[str, Any] | None
```

Close entire position at market price.

**Returns:** Dictionary with close details or None if no position

###### `adjust_stop()`

```python
async def adjust_stop(self, new_stop_loss: float) -> bool
```

Adjust stop loss for current position.

**Parameters:**
- `new_stop_loss`: New stop loss price

**Returns:** True if adjustment successful

##### Trade Monitoring

###### `wait_for_fill()`

```python
async def wait_for_fill(self, timeout: float = 30.0) -> bool
```

Wait for entry order to be filled.

**Parameters:**
- `timeout`: Maximum wait time in seconds

**Returns:** True if order filled within timeout

###### `monitor_position()`

```python
async def monitor_position(self) -> dict[str, Any]
```

Get current position status and P&L.

**Returns:** Dictionary with position details and unrealized P&L

###### `get_trade_summary()`

```python
async def get_trade_summary(self) -> dict[str, Any]
```

Get comprehensive trade summary with all details.

**Returns:** Dictionary with complete trade information

## Usage Examples

### Basic Risk-Managed Trading

```python
from project_x_py import TradingSuite, Features
from project_x_py.risk_manager import RiskConfig, ManagedTrade
from decimal import Decimal

async def basic_risk_trading():
    # Setup with risk management
    config = RiskConfig(
        max_risk_per_trade=Decimal("0.01"),  # 1% risk per trade
        max_daily_loss=Decimal("0.03"),      # 3% daily loss limit
        use_stop_loss=True,
        default_stop_distance=Decimal("25"), # 25-point stops
        default_risk_reward_ratio=Decimal("2.0")  # 1:2 risk/reward
    )

    suite = await TradingSuite.create(
        ["MNQ"],
        features=[Features.RISK_MANAGER],
        risk_config=config
    )
    mnq_context = suite["MNQ"]

    # Execute risk-managed trade
    async with ManagedTrade(
        risk_manager=mnq_context.risk_manager,
        order_manager=mnq_context.orders,
        position_manager=mnq_context.positions,
        instrument_id=mnq_context.instrument_info.id,
        data_manager=mnq_context.data,
        max_risk_percent=0.015  # Override to 1.5% for this trade
    ) as trade:

        # Enter long with automatic position sizing
        result = await trade.enter_long(
            entry_price=21000.0,
            order_type=OrderType.LIMIT
        )

        if result["entry_order"]:
            print(f"Trade executed:")
            print(f"  Position size: {result['size']} contracts")
            print(f"  Risk amount: ${result['risk_amount']:.2f}")

            # Wait for fill
            filled = await trade.wait_for_fill(timeout=60)

            if filled:
                print("Position filled successfully")

                # Monitor position
                while True:
                    status = await trade.monitor_position()
                    print(f"P&L: ${status['pnl']:.2f}")

                    # Exit condition example
                    if status['pnl'] >= 100:  # Take profits at $100
                        await trade.scale_out(1)  # Partial exit
                        break
                    elif status['pnl'] <= -50:  # Emergency exit
                        await trade.close_position()
                        break

                    await asyncio.sleep(5)  # Check every 5 seconds

    # Get final risk metrics
    metrics = await mnq_context.risk_manager.get_risk_metrics()
    print(f"Daily P&L: ${metrics.daily_loss:.2f}")
    print(f"Trades today: {metrics.daily_trades}")

    await suite.disconnect()
```

### Advanced Portfolio Risk Management

```python
async def advanced_portfolio_risk():
    # Setup multiple instruments with correlation limits
    config = RiskConfig(
        max_risk_per_trade=Decimal("0.02"),
        max_positions=5,
        max_correlated_positions=2,  # Max 2 correlated positions
        correlation_threshold=Decimal("0.7"),
        use_kelly_criterion=True,
        kelly_fraction=Decimal("0.25")
    )

    suite = await TradingSuite.create(
        ["MNQ", "ES", "RTY"],
        features=[Features.RISK_MANAGER],
        risk_config=config
    )

    # Portfolio risk monitoring
    async def monitor_portfolio_risk():
        while True:
            # This would ideally be a single call to a portfolio-level risk manager
            # For this example, we'll check the risk manager of the primary instrument
            analysis = await suite["MNQ"].risk_manager.analyze_portfolio_risk()

            print(f"Portfolio Risk Analysis:")
            print(f"  Total risk: ${analysis['total_risk']:.2f}")
            print(f"  Position count: {len(analysis['position_risks'])}")

            # Check for excessive risk
            for pos_risk in analysis['position_risks']:
                if pos_risk['risk']['percent'] > 0.03:  # 3% position risk
                    print(f"High risk position detected: {pos_risk['instrument']}")

            await asyncio.sleep(60)  # Check every minute

    # Start monitoring task
    monitor_task = asyncio.create_task(monitor_portfolio_risk())

    try:
        # Execute trades with portfolio-wide risk awareness
        # In a real scenario, you would have logic to decide which instrument to trade
        print("Trading logic would be executed here.")
        await asyncio.sleep(1)

    finally:
        monitor_task.cancel()
        await suite.disconnect()
```

## Response Objects

### PositionSizingResponse

```python
@dataclass
class PositionSizingResponse:
    position_size: int              # Calculated position size in contracts
    risk_amount: float              # Actual risk amount in dollars
    risk_percent: float             # Risk as percentage of account
    entry_price: float              # Entry price used in calculation
    stop_loss: float                # Stop loss price used
    tick_size: float                # Instrument tick size
    account_balance: float          # Current account balance
    kelly_fraction: float | None    # Kelly fraction if applicable
    max_position_size: int          # Maximum allowed position size
    sizing_method: str              # Method used ("fixed_risk", "kelly", etc.)
```

### RiskValidationResponse

```python
@dataclass
class RiskValidationResponse:
    is_valid: bool                  # Whether trade passes all risk checks
    reasons: list[str]              # Reasons for rejection (if any)
    warnings: list[str]             # Warnings but not rejections
    current_risk: float             # Current portfolio risk
    daily_loss: float               # Current daily loss
    daily_trades: int               # Number of trades today
    position_count: int             # Current position count
    portfolio_risk: float           # Total portfolio risk percentage
```

### RiskAnalysisResponse

```python
@dataclass
class RiskAnalysisResponse:
    current_risk: float             # Current risk exposure
    max_risk: float                 # Maximum allowed risk
    daily_loss: float               # Current daily loss
    daily_loss_limit: float         # Daily loss limit
    position_count: int             # Current positions
    position_limit: int             # Maximum positions
    daily_trades: int               # Trades executed today
    daily_trade_limit: int          # Maximum daily trades
    win_rate: float                 # Historical win rate
    profit_factor: float            # Gross profit / gross loss
    sharpe_ratio: float             # Risk-adjusted return metric
    max_drawdown: float             # Maximum drawdown
    position_risks: list[dict]      # Individual position risk details
    risk_per_trade: float           # Risk per trade setting
    account_balance: float          # Current account balance
    margin_used: float              # Used margin
    margin_available: float         # Available margin
```

## Error Handling

The risk manager raises specific exceptions for different error conditions:

```python
from project_x_py.exceptions import InvalidOrderParameters

try:
    sizing = await risk_manager.calculate_position_size(
        entry_price=21000.0,
        stop_loss=21000.0,  # Same as entry - invalid!
        risk_percent=0.01
    )
except InvalidOrderParameters as e:
    print(f"Invalid parameters: {e}")

# Risk validation errors
validation = await risk_manager.validate_trade(order)
if not validation.is_valid:
    # Handle rejection reasons
    for reason in validation.reasons:
        print(f"Rejection reason: {reason}")

    # Check warnings
    for warning in validation.warnings:
        print(f"Warning: {warning}")
```

## Events

The risk manager emits various events through the event bus:

```python
from project_x_py import EventType

# Risk limit exceeded event
async def on_risk_limit(event):
    print(f"Risk limit exceeded: {event.data}")
    # Take protective action

# Risk orders placed event
async def on_risk_orders(event):
    data = event.data
    print(f"Risk orders placed for position {data['position'].id}")
    print(f"Stop loss: {data['stop_loss']}")
    print(f"Take profit: {data['take_profit']}")

# Subscribe to risk events
suite = await TradingSuite.create(["MNQ"], features=[Features.RISK_MANAGER])
mnq_context = suite["MNQ"]

await mnq_context.event_bus.on("risk_limit_exceeded", on_risk_limit)
await mnq_context.event_bus.on("risk_orders_placed", on_risk_orders)
```

## Statistics Integration

The RiskManager extends `BaseStatisticsTracker` and provides comprehensive metrics:

```python
# Get risk manager statistics
stats = await suite["MNQ"].risk_manager.get_statistics()

print(f"Risk Manager Statistics:")
print(f"  Status: {stats['status']}")
print(f"  Position size calculations: {stats.get('position_size_calculations', 0)}")
print(f"  Trade validations: {stats.get('trade_validations', 0)}")
print(f"  Valid trades: {stats.get('valid_trades', 0)}")
print(f"  Invalid trades: {stats.get('invalid_trades', 0)}")
print(f"  Risk orders attached: {stats.get('risk_orders_attached', 0)}")
print(f"  Stop adjustments: {stats.get('stop_adjustments', 0)}")
print(f"  Winning trades: {stats.get('winning_trades', 0)}")
print(f"  Losing trades: {stats.get('losing_trades', 0)}")

# Risk-specific gauges
print(f"Current Metrics:")
print(f"  Win rate: {stats.get('win_rate_percent', 0):.1f}%")
print(f"  Largest win: ${stats.get('largest_win', 0):.2f}")
print(f"  Largest loss: ${stats.get('largest_loss', 0):.2f}")
print(f"  Daily trades: {stats.get('daily_trades_count', 0)}")
print(f"  Portfolio risk: {stats.get('current_portfolio_risk', 0):.2%}")
```

## Best Practices

### 1. Always Configure Risk Limits

```python
# ✓ Good: Define clear risk parameters
config = RiskConfig(
    max_risk_per_trade=Decimal("0.01"),  # Never risk more than 1%
    max_daily_loss=Decimal("0.03"),      # Stop trading at 3% daily loss
    max_positions=3,                     # Limit concurrent positions
    use_stop_loss=True                   # Always use stops
)

# ✗ Bad: Using defaults without understanding them
config = RiskConfig()  # What are the defaults? Do they fit my strategy?
```

### 2. Validate Before Trading

```python
# ✓ Good: Validate every trade against risk rules
validation = await risk_manager.validate_trade(order)
if validation.is_valid:
    # Execute trade
    pass
else:
    logger.warning(f"Trade rejected: {validation.reasons}")

# ✗ Bad: Skip validation and risk blowing account
# Direct order placement without risk checks
```

### 3. Use ManagedTrade for Consistency

```python
# ✓ Good: Consistent risk management with ManagedTrade
suite = await TradingSuite.create(["MNQ"], features=[Features.RISK_MANAGER])
mnq_context = suite["MNQ"]
async with ManagedTrade(
    risk_manager=mnq_context.risk_manager,
    order_manager=mnq_context.orders,
    position_manager=mnq_context.positions,
    instrument_id=mnq_context.instrument_info.id
) as trade:
    result = await trade.enter_long(entry_price=21000.0)
    # Automatic position sizing, stops, targets

# ✗ Bad: Manual risk calculations (error-prone)
# Manual position size = account * 0.01 / (entry - stop)
# Manual order placement
# Manual stop/target attachment
```

### 4. Monitor Risk Continuously

```python
# ✓ Good: Active risk monitoring
async def risk_monitor():
    while trading_active:
        metrics = await risk_manager.get_risk_metrics()
        if metrics.daily_loss > max_daily_loss:
            await emergency_close_all()
        await asyncio.sleep(60)

# ✗ Bad: Set and forget - no monitoring
# Place trades and ignore running risk
```

### 5. Record Trade Results

```python
# ✓ Good: Track performance for Kelly criterion and analysis
await risk_manager.record_trade_result(
    position_id="pos_123",
    pnl=trade_pnl,
    duration_seconds=trade_duration
)

# ✗ Bad: No performance tracking
# Miss opportunities for strategy improvement
```

## See Also

- [Position Manager API](position-manager.md) - Portfolio and position tracking
- [Order Manager API](order-manager.md) - Order placement and management
- [Statistics API](statistics.md) - Performance metrics and analytics
- [Risk Management Guide](../guide/risk.md) - Comprehensive risk management guide
