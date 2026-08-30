# Risk Management Guide

Risk management is crucial for successful trading. The ProjectX SDK provides comprehensive risk management tools through the RiskManager component and ManagedTrade class to help protect your capital and automate risk-based position sizing.

## Overview

The SDK's risk management system provides:

- **Position sizing** based on risk amount and stop distance
- **Account-level risk limits** (daily loss, position count, position size)
- **Real-time risk monitoring** with comprehensive metrics
- **ManagedTrade** for automated risk-controlled order execution
- **Risk metrics calculation** (win rate, profit factor, Sharpe ratio, max drawdown)
- **Integration** with all trading components through statistics tracking

**Recommended path:** use `ManagedTrade` (or `suite.managed_trade()`) for entries. It sizes the trade, validates it, and attaches OCO stop/target orders.

**Backstop:** enabling `features=["risk_manager"]` also sets `auto_risk_management` on `OrderManager`. Direct `suite.orders.place_market_order` / `place_limit_order` / `place_join_*` calls then run `RiskManager.validate_trade` *before* the HTTP request and refuse the entry when `is_valid` is False. Protective types (stop, stop-limit, trailing stop) skip this gate so attaching stops cannot be blocked because `max_positions` already includes the live position. This auto-gate is an extra safety net, not a replacement for `ManagedTrade`.

## Getting Started

### Enable Risk Manager

```python
from project_x_py import TradingSuite, Features

async def basic_risk_setup():
    # Enable risk manager feature
    suite = await TradingSuite.create(
        "MNQ",
        features=[Features.RISK_MANAGER]
    )

    # Check if risk manager is available
    if suite.risk_manager:
        print("Risk Manager enabled")

        # Get comprehensive risk metrics
        metrics = await suite.risk_manager.get_risk_metrics()
        print(f"Max position size: {metrics.position_limit}")
        print(f"Daily loss limit: {metrics.daily_loss_limit:.2%}")
        print(f"Current portfolio risk: {metrics.current_risk:.2f}")

    await suite.disconnect()
```

### Basic Risk Configuration

```python
from project_x_py.risk_manager import RiskConfig
from decimal import Decimal

async def configure_risk():
    # Define risk parameters using Decimal for precision
    risk_config = RiskConfig(
        max_position_size=5,                           # Max 5 contracts per position
        max_daily_loss_amount=Decimal("1000.0"),       # Max $1000 daily loss
        max_risk_per_trade=Decimal("0.02"),            # 2% of account per trade
        default_risk_reward_ratio=Decimal("2.0"),      # 1:2 risk/reward
        use_stop_loss=True,                            # Always use stops
        default_stop_distance=Decimal("25")            # 25 ticks (× tickSize) default stops
    )

    suite = await TradingSuite.create(
        "MNQ",
        features=[Features.RISK_MANAGER],
        risk_config=risk_config
    )

    await suite.disconnect()
```

## Position Sizing

### Risk-Based Position Sizing

```python
async def risk_based_sizing():
    suite = await TradingSuite.create("MNQ", features=[Features.RISK_MANAGER])

    if suite.risk_manager:
        # Calculate position size based on risk parameters
        sizing = await suite.risk_manager.calculate_position_size(
            entry_price=21050.0,    # Entry price
            stop_loss=21025.0,      # Stop loss price
            risk_amount=200.0       # Risk $200 per trade
        )

        print(f"Position size: {sizing.position_size} contracts")
        print(f"Risk amount: ${sizing.risk_amount:.2f}")
        print(f"Risk percent: {sizing.risk_percent:.2%}")
        print(f"Sizing method: {sizing.sizing_method}")

        # Alternative: Calculate based on account percentage
        sizing_pct = await suite.risk_manager.calculate_position_size(
            entry_price=21050.0,
            stop_loss=21025.0,
            risk_percent=0.02  # 2% of account
        )

        print(f"Position size (2% risk): {sizing_pct.position_size} contracts")
        print(f"Account balance: ${sizing_pct.account_balance:.2f}")

    await suite.disconnect()
```

### ATR-Based Position Sizing

```python
from project_x_py.indicators import ATR

async def atr_based_sizing():
    suite = await TradingSuite.create("MNQ", features=[Features.RISK_MANAGER], timeframes=["5min"])

    # Get recent data and calculate ATR
    bars = await suite.data.get_data("5min", bars=100)
    data_with_atr = bars.pipe(ATR, period=14)

    current_atr = data_with_atr["atr_14"].tail(1).item()
    current_price = await suite.data.get_current_price()

    if suite.risk_manager:
        # Calculate stop loss using ATR
        stop_loss = await suite.risk_manager.calculate_stop_loss(
            entry_price=current_price,
            side=OrderSide.BUY,
            atr_value=current_atr
        )

        # Calculate position size with ATR-based stop
        sizing = await suite.risk_manager.calculate_position_size(
            entry_price=current_price,
            stop_loss=stop_loss,
            risk_amount=250.0
        )

        print(f"Current ATR: {current_atr:.2f}")
        print(f"Stop loss: {stop_loss:.2f}")
        print(f"Position size: {sizing.position_size} contracts")

    await suite.disconnect()
```

## ManagedTrade

The ManagedTrade class provides automated risk-controlled trading with built-in position sizing and risk management.

### Basic ManagedTrade

```python
from project_x_py.risk_manager import ManagedTrade
from project_x_py.types import OrderType

async def basic_managed_trade():
    suite = await TradingSuite.create("MNQ", features=[Features.RISK_MANAGER])

    # Create a managed trade context
    async with ManagedTrade(
        risk_manager=suite.risk_manager,
        order_manager=suite.orders,
        position_manager=suite.positions,
        instrument_id=suite.instrument_id,
        data_manager=suite.data,
        max_risk_percent=0.02  # Risk 2% per trade
    ) as trade:

        # Execute long trade with automatic risk management
        result = await trade.enter_long(
            entry_price=21050.0,
            stop_loss=21025.0,      # 25-point stop
            take_profit=21100.0,    # 50-point target
            order_type=OrderType.LIMIT
        )

        if result["entry_order"]:
            print(f"Trade executed successfully:")
            print(f"  Size: {result['size']} contracts")
            print(f"  Risk: ${result['risk_amount']:.2f}")
            print(f"  Entry: {result['entry_order'].id}")
            if result['stop_order']:
                print(f"  Stop: {result['stop_order'].id}")
            if result['target_order']:
                print(f"  Target: {result['target_order'].id}")

            # Wait for fill and monitor
            filled = await trade.wait_for_fill(timeout=60)
            if filled:
                print("Position filled - monitoring...")

    await suite.disconnect()
```

### Advanced ManagedTrade with Scaling

```python
async def advanced_managed_trade():
    suite = await TradingSuite.create("MNQ", features=[Features.RISK_MANAGER])

    # Configure for scaling operations
    config = RiskConfig(
        scale_in_enabled=True,   # Allow position scaling
        scale_out_enabled=True,  # Allow partial exits
        max_position_size=10     # Higher limit for scaling
    )

    suite.risk_manager.config = config

    async with ManagedTrade(
        risk_manager=suite.risk_manager,
        order_manager=suite.orders,
        position_manager=suite.positions,
        instrument_id=suite.instrument_id,
        data_manager=suite.data
    ) as trade:

        # Initial entry
        result = await trade.enter_long(
            entry_price=21050.0,
            order_type=OrderType.LIMIT
        )

        if result["entry_order"]:
            # Wait for initial fill
            filled = await trade.wait_for_fill()

            if filled:
                print("Initial position filled")

                # Scale in if price moves favorably
                scale_result = await trade.scale_in(
                    additional_size=1,
                    new_stop_loss=21040.0  # Adjust stop for larger position
                )
                print(f"Scaled in - new size: {scale_result['new_position_size']}")

                # Later, scale out for partial profits
                exit_result = await trade.scale_out(
                    exit_size=1,
                    limit_price=21075.0
                )
                print(f"Partial exit - remaining: {exit_result['remaining_size']}")

    await suite.disconnect()
```

## Risk Limits and Monitoring

### Trade Validation

```python
from project_x_py.models import Order
from project_x_py.types import OrderSide

async def trade_validation():
    suite = await TradingSuite.create("MNQ", features=[Features.RISK_MANAGER])

    if suite.risk_manager:
        # Create a mock order for validation
        mock_order = Order(
            id=0,
            accountId=0,
            contractId=suite.instrument_id,
            creationTimestamp="2024-01-01T10:00:00Z",
            updateTimestamp=None,
            status=6,  # Pending
            type=1,    # Market
            side=OrderSide.BUY.value,
            size=3,    # Might be too large
            limitPrice=None,
            stopPrice=None,
            fillVolume=None,
            filledPrice=None,
            customTag=None,
        )

        # Validate against risk rules
        validation = await suite.risk_manager.validate_trade(mock_order)

        if validation.is_valid:
            print("Trade approved")
            print(f"Daily trades: {validation.daily_trades}")
            print(f"Portfolio risk: {validation.portfolio_risk:.2%}")
        else:
            print(f"Trade rejected:")
            for reason in validation.reasons:
                print(f"  - {reason}")

            # Show warnings (non-blocking issues)
            for warning in validation.warnings:
                print(f"  Warning: {warning}")

    await suite.disconnect()
```

### Real-time Risk Monitoring

```python
from project_x_py.event_bus import EventType
import asyncio

async def real_time_risk_monitoring():
    suite = await TradingSuite.create("MNQ", features=[Features.RISK_MANAGER])

    # Risk event handlers
    async def on_trade_recorded(event):
        data = event.data
        print(f"Trade recorded: P&L=${data['pnl']:.2f}")
        print(f"Daily loss: ${data['daily_loss']:.2f}")

    # Register event handlers
    await suite.event_bus.on("trade_recorded", on_trade_recorded)

    # Monitor risk continuously
    monitoring_active = True

    async def risk_monitor():
        while monitoring_active:
            if suite.risk_manager:
                # Get current risk metrics
                metrics = await suite.risk_manager.get_risk_metrics()

                print(f"Risk Status:")
                print(f"  Daily loss: ${metrics.daily_loss:.2f} / ${metrics.daily_loss_limit:.2f}")
                print(f"  Positions: {metrics.position_count}/{metrics.position_limit}")
                print(f"  Daily trades: {metrics.daily_trades}/{metrics.daily_trade_limit}")
                print(f"  Win rate: {metrics.win_rate:.1%}")

                # Check critical limits
                loss_ratio = metrics.daily_loss / metrics.daily_loss_limit if metrics.daily_loss_limit else 0
                if loss_ratio > 0.8:  # 80% of daily limit
                    print("⚠️  WARNING: Approaching daily loss limit")

                if metrics.position_count >= metrics.position_limit:
                    print("⚠️  WARNING: Maximum positions reached")

            await asyncio.sleep(30)  # Check every 30 seconds

    # Start monitoring
    monitor_task = asyncio.create_task(risk_monitor())

    # Simulate some trading activity
    await asyncio.sleep(300)  # Monitor for 5 minutes

    # Cleanup
    monitoring_active = False
    monitor_task.cancel()

    try:
        await monitor_task
    except asyncio.CancelledError:
        pass

    await suite.disconnect()
```

## Risk Metrics and Analytics

### Portfolio Risk Analysis

```python
async def portfolio_risk_analysis():
    suite = await TradingSuite.create("MNQ", features=[Features.RISK_MANAGER])

    if suite.risk_manager:
        # Get comprehensive risk analysis
        metrics = await suite.risk_manager.get_risk_metrics()

        print(f"Portfolio Risk Analysis:")
        print(f"  Current risk: ${metrics.current_risk:.2f}")
        print(f"  Max risk limit: {metrics.max_risk:.2%}")
        print(f"  Daily P&L: ${metrics.daily_loss:.2f}")
        print(f"  Position count: {metrics.position_count}/{metrics.position_limit}")

        # Performance metrics
        print(f"\nPerformance Metrics:")
        print(f"  Win rate: {metrics.win_rate:.1%}")
        print(f"  Profit factor: {metrics.profit_factor:.2f}")
        print(f"  Sharpe ratio: {metrics.sharpe_ratio:.2f}")
        print(f"  Max drawdown: {metrics.max_drawdown:.2f}")

        # Position-specific risks
        print(f"\nPosition Risks:")
        for pos_risk in metrics.position_risks:
            print(f"  {pos_risk['symbol']}: ${pos_risk['risk_amount']:.2f} "
                  f"({pos_risk['risk_percent']:.2%})")

        # Portfolio analysis
        portfolio_analysis = await suite.risk_manager.analyze_portfolio_risk()
        print(f"\nPortfolio Analysis:")
        print(f"  Total risk: ${portfolio_analysis['total_risk']:.2f}")
        print(f"  Position count: {len(portfolio_analysis['position_risks'])}")

    await suite.disconnect()
```

### Individual Trade Analysis

```python
async def trade_risk_analysis():
    suite = await TradingSuite.create("MNQ", features=[Features.RISK_MANAGER])

    if suite.risk_manager:
        # Analyze a potential trade setup
        trade_analysis = await suite.risk_manager.analyze_trade_risk(
            instrument="MNQ",
            entry_price=21050.0,
            stop_loss=21025.0,      # 25-point stop
            take_profit=21100.0,    # 50-point target
            position_size=2
        )

        print(f"Trade Risk Analysis:")
        print(f"  Risk amount: ${trade_analysis['risk_amount']:.2f}")
        print(f"  Reward amount: ${trade_analysis['reward_amount']:.2f}")
        print(f"  Risk/reward ratio: {trade_analysis['risk_reward_ratio']:.2f}")
        print(f"  Risk percentage: {trade_analysis['risk_percent']:.2%}")

        # Decision logic
        if trade_analysis['risk_reward_ratio'] >= 2.0:
            print("✅ Good risk/reward ratio - trade approved")
        else:
            print("❌ Poor risk/reward ratio - consider adjusting")

    await suite.disconnect()
```

## Integration with Trading Components

### Risk-Aware Position Management

```python
async def risk_aware_position_management():
    suite = await TradingSuite.create("MNQ", features=[Features.RISK_MANAGER])

    # Get current position
    position = await suite.positions.get_position_by_contract(suite.instrument_id)

    if position and suite.risk_manager:
        # Attach risk orders to existing position
        risk_orders = await suite.risk_manager.attach_risk_orders(
            position=position,
            stop_loss=20975.0,
            take_profit=21100.0,
            use_trailing=True
        )

        if risk_orders["bracket_order"].success:
            print(f"Risk orders attached:")
            print(f"  Stop order: {risk_orders['bracket_order'].stop_order_id}")
            print(f"  Target order: {risk_orders['bracket_order'].target_order_id}")
            print(f"  Trailing enabled: {risk_orders['use_trailing']}")

            # Later, adjust the stop loss
            success = await suite.risk_manager.adjust_stops(
                position=position,
                new_stop=21000.0  # Move stop to breakeven
            )

            if success:
                print("Stop loss adjusted to breakeven")

    await suite.disconnect()
```

### Automatic Risk Order Placement

```python
async def automatic_risk_orders():
    suite = await TradingSuite.create("MNQ", features=[Features.RISK_MANAGER])

    # Configure risk parameters for automatic order placement
    config = RiskConfig(
        use_stop_loss=True,
        stop_loss_type="atr",  # Use ATR for dynamic stops
        default_stop_atr_multiplier=Decimal("2.0"),  # 2x ATR
        use_take_profit=True,
        default_risk_reward_ratio=Decimal("2.0"),  # 1:2 risk/reward
        use_trailing_stops=True,
        trailing_stop_distance=Decimal("15")  # 15-point trailing distance
    )

    suite.risk_manager.config = config

    # Place a market order
    order_response = await suite.orders.place_market_order(
        contract_id=suite.instrument_id,
        side=OrderSide.BUY,
        size=1
    )

    if order_response.success:
        print(f"Market order placed: {order_response.order_id}")

        # Wait for fill, then get the position
        await asyncio.sleep(5)  # Allow time for fill

        position = await suite.positions.get_position_by_contract(suite.instrument_id)
        if position:
            # Automatically attach risk orders
            risk_orders = await suite.risk_manager.attach_risk_orders(position)

            if risk_orders["bracket_order"].success:
                print("Automatic risk orders attached:")
                print(f"  ATR-based stop: {risk_orders['stop_loss']:.2f}")
                print(f"  2:1 R/R target: {risk_orders['take_profit']:.2f}")

    await suite.disconnect()
```

## Advanced Risk Strategies

### Kelly Criterion Position Sizing

```python
async def kelly_criterion_sizing():
    # Configure risk manager with Kelly criterion
    config = RiskConfig(
        use_kelly_criterion=True,
        kelly_fraction=Decimal("0.25"),  # Use 25% of Kelly recommendation
        min_trades_for_kelly=10,  # Need 10 trades minimum for Kelly
        max_risk_per_trade=Decimal("0.03")  # Still cap at 3% max
    )

    suite = await TradingSuite.create(
        "MNQ",
        features=[Features.RISK_MANAGER],
        risk_config=config
    )

    if suite.risk_manager:
        # Add some historical trade results for Kelly calculation
        trades = [
            (150, "MNQ"), (-75, "MNQ"), (200, "MNQ"), (-50, "MNQ"), (100, "MNQ"),
            (-100, "MNQ"), (125, "MNQ"), (175, "MNQ"), (-25, "MNQ"), (90, "MNQ")
        ]

        for pnl, instrument in trades:
            await suite.risk_manager.add_trade_result(
                instrument=instrument,
                pnl=pnl,
                entry_price=21000.0,
                exit_price=21000.0 + (pnl / 5),  # Approximate exit price
                size=1,
                side=OrderSide.BUY
            )

        # Calculate position size with Kelly criterion
        sizing = await suite.risk_manager.calculate_position_size(
            entry_price=21050.0,
            stop_loss=21025.0,
            use_kelly=True
        )

        print(f"Kelly-based position sizing:")
        print(f"  Position size: {sizing.position_size} contracts")
        print(f"  Kelly fraction: {sizing.kelly_fraction:.3f}")
        print(f"  Sizing method: {sizing.sizing_method}")
        print(f"  Risk amount: ${sizing.risk_amount:.2f}")

    await suite.disconnect()
```

### Dynamic Risk Scaling

```python
from project_x_py.indicators import ATR

async def dynamic_risk_scaling():
    suite = await TradingSuite.create("MNQ", features=[Features.RISK_MANAGER], timeframes=["5min"])

    async def adjust_risk_for_volatility():
        # Calculate current market volatility
        bars = await suite.data.get_data("5min", bars=100)
        data_with_atr = bars.pipe(ATR, period=14)

        current_atr = data_with_atr["atr_14"].tail(1).item()
        avg_atr = data_with_atr["atr_14"].mean()
        volatility_ratio = current_atr / avg_atr

        print(f"Volatility Analysis:")
        print(f"  Current ATR: {current_atr:.2f}")
        print(f"  Average ATR: {avg_atr:.2f}")
        print(f"  Volatility ratio: {volatility_ratio:.2f}")

        if suite.risk_manager:
            # Adjust risk based on volatility
            base_risk_percent = 0.02  # 2% base risk

            if volatility_ratio > 1.5:  # High volatility
                adjusted_risk = base_risk_percent * 0.7  # Reduce risk
                print(f"High volatility - reducing risk to {adjusted_risk:.2%}")
            elif volatility_ratio < 0.7:  # Low volatility
                adjusted_risk = base_risk_percent * 1.3  # Increase risk
                print(f"Low volatility - increasing risk to {adjusted_risk:.2%}")
            else:
                adjusted_risk = base_risk_percent
                print(f"Normal volatility - maintaining {adjusted_risk:.2%} risk")

            # Calculate position size with adjusted risk
            sizing = await suite.risk_manager.calculate_position_size(
                entry_price=21050.0,
                stop_loss=21025.0,
                risk_percent=adjusted_risk
            )

            print(f"Adjusted position size: {sizing.position_size} contracts")

    # Run volatility-based risk adjustment
    await adjust_risk_for_volatility()
    await suite.disconnect()
```

## Risk Management Best Practices

### 1. Always Define Your Risk

```python
# ✅ Good: Define risk before entering trade
async with ManagedTrade(
    risk_manager=suite.risk_manager,
    order_manager=suite.orders,
    position_manager=suite.positions,
    instrument_id=suite.instrument_id,
    max_risk_percent=0.02  # Clear 2% risk per trade
) as trade:
    result = await trade.enter_long(entry_price=21050.0)

# ❌ Bad: Arbitrary position sizing without risk consideration
await suite.orders.place_market_order(
    contract_id=suite.instrument_id,
    side=OrderSide.BUY,
    size=5  # Why 5? No risk-based reasoning
)
```

### 2. Use Stop Losses Always

```python
# ✅ Good: Every position has a stop loss
config = RiskConfig(
    use_stop_loss=True,
    stop_loss_type="atr",  # Dynamic ATR-based stops
    default_stop_atr_multiplier=Decimal("2.0")
)

# ❌ Bad: No stop loss configuration
config = RiskConfig(
    use_stop_loss=False  # Dangerous - no protection
)
```

### 3. Monitor Risk Continuously

```python
# ✅ Good: Active risk monitoring
async def continuous_monitoring():
    while trading_active:
        metrics = await suite.risk_manager.get_risk_metrics()

        if metrics.daily_loss > metrics.daily_loss_limit * 0.8:
            print("WARNING: Approaching daily loss limit")

        await asyncio.sleep(60)

# ❌ Bad: No risk monitoring after trade placement
# Place trades and ignore running exposure
```

### 4. Validate Every Trade

```python
# ✅ Good: Validate all trades against risk rules
validation = await suite.risk_manager.validate_trade(order)
if not validation.is_valid:
    print(f"Trade rejected: {validation.reasons}")
    return  # Don't place the trade

# ❌ Bad: Skip validation and risk account blow-up
# Place orders without checking risk limits
```

### 5. Record Trade Results

```python
# ✅ Good: Track performance for improvement
await suite.risk_manager.record_trade_result(
    position_id="pos_123",
    pnl=trade_pnl,
    duration_seconds=trade_duration
)

# ❌ Bad: No performance tracking
# Miss opportunities for strategy optimization
```

### 6. Use Risk Configuration Properly

```python
# ✅ Good: Thoughtful risk configuration
config = RiskConfig(
    max_risk_per_trade=Decimal("0.01"),      # 1% per trade max
    max_daily_loss=Decimal("0.03"),          # 3% daily loss limit
    max_positions=3,                          # Limit concurrent positions
    use_stop_loss=True,                      # Always use stops
    default_risk_reward_ratio=Decimal("2.0"), # Minimum 1:2 R/R
    restrict_trading_hours=True,             # Trade only during market hours
    allowed_trading_hours=[("09:30", "16:00")]
)

# ❌ Bad: Unsafe default configuration
config = RiskConfig()  # Using defaults without understanding implications
```

## Statistics and Performance Tracking

The risk manager integrates with the statistics system to provide comprehensive performance tracking:

```python
async def risk_statistics():
    suite = await TradingSuite.create("MNQ", features=[Features.RISK_MANAGER])

    # Get risk manager statistics
    stats = await suite.risk_manager.get_statistics()

    print(f"Risk Manager Statistics:")
    print(f"  Status: {stats['status']}")
    print(f"  Position size calculations: {stats.get('position_size_calculations', 0)}")
    print(f"  Trade validations: {stats.get('trade_validations', 0)}")
    print(f"  Valid trades: {stats.get('valid_trades', 0)}")
    print(f"  Invalid trades: {stats.get('invalid_trades', 0)}")

    # Performance metrics
    print(f"\nPerformance Metrics:")
    print(f"  Win rate: {stats.get('win_rate_percent', 0):.1f}%")
    print(f"  Total trades: {stats.get('total_trades', 0)}")
    print(f"  Winning trades: {stats.get('winning_trades', 0)}")
    print(f"  Losing trades: {stats.get('losing_trades', 0)}")
    print(f"  Largest win: ${stats.get('largest_win', 0):.2f}")
    print(f"  Largest loss: ${stats.get('largest_loss', 0):.2f}")

    # Risk metrics
    print(f"\nRisk Metrics:")
    print(f"  Risk orders attached: {stats.get('risk_orders_attached', 0)}")
    print(f"  Stop adjustments: {stats.get('stop_adjustments', 0)}")
    print(f"  Trailing stops monitored: {stats.get('trailing_stops_monitored', 0)}")

    await suite.disconnect()
```

## Cleanup and Resource Management

Always properly clean up risk manager resources:

```python
async def proper_cleanup():
    suite = await TradingSuite.create("MNQ", features=[Features.RISK_MANAGER])

    try:
        # Your trading logic here
        pass
    finally:
        # Ensure proper cleanup
        if suite.risk_manager:
            await suite.risk_manager.cleanup()  # Stops trailing stops, cleans up tasks
        await suite.disconnect()
```

## Common Patterns

### Pattern 1: Conservative Risk Management

```python
# Setup for conservative trading
conservative_config = RiskConfig(
    max_risk_per_trade=Decimal("0.005"),     # 0.5% per trade
    max_daily_loss=Decimal("0.02"),          # 2% daily loss limit
    max_positions=2,                         # Max 2 concurrent positions
    use_trailing_stops=True,                 # Use trailing stops
    default_risk_reward_ratio=Decimal("3.0") # Minimum 1:3 R/R
)
```

### Pattern 2: Aggressive Growth Strategy

```python
# Setup for aggressive trading
aggressive_config = RiskConfig(
    max_risk_per_trade=Decimal("0.03"),      # 3% per trade
    max_daily_loss=Decimal("0.10"),          # 10% daily loss limit
    max_positions=5,                         # Max 5 concurrent positions
    use_kelly_criterion=True,                # Use Kelly sizing
    scale_in_enabled=True,                   # Allow position scaling
    martingale_enabled=False                 # Never use martingale!
)
```

### Pattern 3: Professional Risk Management

```python
# Professional-grade risk management
professional_config = RiskConfig(
    max_risk_per_trade=Decimal("0.01"),      # 1% per trade
    max_daily_loss=Decimal("0.03"),          # 3% daily loss limit
    max_positions=3,                         # Limit positions for focus
    stop_loss_type="atr",                    # Dynamic ATR stops
    use_trailing_stops=True,                 # Protect profits
    restrict_trading_hours=True,             # Trade only market hours
    avoid_news_events=True,                  # Avoid news volatility
    max_correlated_positions=2               # Limit correlation exposure
)
```

## Conclusion

Risk management is the foundation of successful trading. The ProjectX SDK provides comprehensive tools to:

- **Automate position sizing** based on risk amount and account balance
- **Validate trades** against comprehensive risk rules
- **Monitor risk in real-time** with detailed metrics and alerts
- **Manage positions** with automatic stop-loss and take-profit orders
- **Track performance** with integrated statistics and analytics
- **Scale positions** safely with built-in validation

The ManagedTrade class makes it easy to implement consistent risk management across all your trading strategies. Start with conservative settings and gradually adjust based on your experience and market conditions.

**Remember**: The goal is not to eliminate risk (impossible in trading) but to manage and control it systematically. Consistent application of risk management rules is more important than perfect market timing.

## See Also

- [Risk Manager API](../api/risk-manager.md) - Complete API reference
- [Position Management](positions.md) - Portfolio and position tracking
- [Order Management](orders.md) - Risk-integrated order placement
- [Statistics](../api/statistics.md) - Performance metrics and analytics
