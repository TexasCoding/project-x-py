# Position Management Guide

This guide covers comprehensive position management and tracking using ProjectX Python SDK v3.3.4+. All position operations are fully asynchronous and provide real-time monitoring capabilities.

## Overview

The PositionManager provides complete position lifecycle management including tracking, risk monitoring, performance analytics, and automated position reconciliation. All operations are designed for high-performance trading applications.

### Key Features

- **Real-time Position Tracking**: Live position updates via WebSocket
- **Performance Analytics**: Comprehensive P&L analysis and metrics
- **Risk Monitoring**: Position-based risk calculations and alerts
- **Portfolio Management**: Multi-instrument portfolio tracking
- **Position Reconciliation**: Automatic position validation and cleanup
- **Event-Driven Updates**: Real-time position change notifications

## Getting Started

### Basic Setup

```python
import asyncio
from decimal import Decimal
from project_x_py import TradingSuite

async def main():
    # Initialize with position management capabilities
    suite = await TradingSuite.create("MNQ")

    # Position manager is automatically available
    position_manager = suite.positions

    # Get current account information
    account = suite.client.account_info
    print(f"Account: {account.name}")
    print(f"Balance: ${account.balance}")
```

## Position Tracking

### Current Position Status

```python
async def check_current_positions():
    suite = await TradingSuite.create("MNQ")

    # Get specific position
    mnq_position = await suite.positions.get_position("MNQ")

    if mnq_position:
        print(f"MNQ Position:")
        print(f"  Size: {mnq_position.size} contracts")
        print(f"  Average Price: ${mnq_position.averagePrice}")
        print(f"  Unrealized P&L: ${mnq_position.unrealized_pnl(current_price)}")
    else:
        print("No MNQ position")

    # Get all positions
    all_positions = await suite.positions.get_all_positions()

    print(f"\nAll positions ({len(all_positions)}):")
    for position in all_positions:
        print(f"  {position.contractId}: {position.size} @ ${position.averagePrice}")

    all_positions = await suite.positions.get_all_positions()
    long_positions = [p for p in all_positions if p.is_long]
    short_positions = [p for p in all_positions if p.is_short]
```

### Real-time Position Monitoring

```python
from project_x_py import EventType

async def setup_position_monitoring():
    suite = await TradingSuite.create("MNQ")

    # Event-driven position updates
    async def on_position_update(event):
        position_data = event.data

        print(f"Position Update: {position_data['contractId']}")
        print(f"  Size: {position_data['size']}")
        print(f"  P&L: ${position_data['unrealizedPnL']:.2f}")

        # Check for risk alerts
        if abs(position_data.get('unrealizedPnL', 0)) > 500:
            print("  Large unrealized loss detected!")

    # Register position event handlers
    await suite.on(EventType.POSITION_UPDATED, on_position_update)

    # Alternative: Polling-based monitoring
    async def monitor_positions():
        """Poll positions every few seconds."""
        while True:
            try:
                positions = await suite.positions.get_all_positions()

                total_pnl = sum(p.unrealizedPnL or 0 for p in positions)
                print(f"Portfolio P&L: ${total_pnl:.2f}")

                # Risk monitoring
                for position in positions:
                    if position.unrealizedPnL and position.unrealizedPnL < -1000:
                        print(f"= Risk Alert: {position.contractId} down ${abs(position.unrealizedPnL):.2f}")

            except Exception as e:
                print(f"Monitor error: {e}")

            await asyncio.sleep(5)  # Poll every 5 seconds

    # Run monitoring concurrently
    monitor_task = asyncio.create_task(monitor_positions())

    # Keep running for events
    await asyncio.sleep(60)

    # Cleanup
    monitor_task.cancel()
```

## Performance Analytics

### P&L Analysis

```python
async def analyze_position_performance():
    suite = await TradingSuite.create("MNQ")

    # Get detailed P&L breakdown
    pnl_summary = await suite.positions.get_portfolio_pnl()

    print("Portfolio Performance:")
    print(f"  Realized P&L: ${pnl_summary['realized_pnl']:.2f}")
    print(f"  Unrealized P&L: ${pnl_summary['unrealized_pnl']:.2f}")
    print(f"  Total P&L: ${pnl_summary['total_pnl']:.2f}")
    print(f"  Day P&L: ${pnl_summary['day_pnl']:.2f}")

    # Per-instrument P&L
    for instrument, pnl_data in pnl_summary['by_instrument'].items():
        print(f"\n{instrument}:")
        print(f"  Position: {pnl_data['size']} contracts")
        print(f"  Avg Price: ${pnl_data['avg_price']:.2f}")
        print(f"  Current P&L: ${pnl_data['pnl']:.2f}")
        print(f"  Return %: {pnl_data['return_pct']:.2f}%")

    # Get historical performance
    from datetime import datetime, timedelta

    yesterday = datetime.now() - timedelta(days=1)

    daily_performance = await suite.positions.get_performance_metrics(
        start_date=yesterday,
        end_date=datetime.now()
    )

    print(f"\n24H Performance:")
    print(f"  Trades: {daily_performance['trade_count']}")
    print(f"  Win Rate: {daily_performance['win_rate']:.1%}")
    print(f"  Avg Win: ${daily_performance['avg_win']:.2f}")
    print(f"  Avg Loss: ${daily_performance['avg_loss']:.2f}")
    print(f"  Profit Factor: {daily_performance['profit_factor']:.2f}")
```

### Advanced Analytics

```python
async def detailed_analytics():
    suite = await TradingSuite.create("MNQ")

    # Get position analytics
    analytics = await suite.positions.get_position_analytics("MNQ")

    if analytics:
        print("MNQ Position Analytics:")
        print(f"  Duration: {analytics['hold_duration']}")
        print(f"  Entry Time: {analytics['entry_time']}")
        print(f"  Max Profit: ${analytics['max_unrealized_profit']:.2f}")
        print(f"  Max Loss: ${analytics['max_unrealized_loss']:.2f}")
        print(f"  Volatility: {analytics['price_volatility']:.2%}")

        # Risk metrics
        print(f"\nRisk Metrics:")
        print(f"  VaR (95%): ${analytics['value_at_risk_95']:.2f}")
        print(f"  Expected Shortfall: ${analytics['expected_shortfall']:.2f}")
        print(f"  Beta: {analytics['beta']:.2f}")
        print(f"  Sharpe Ratio: {analytics['sharpe_ratio']:.2f}")

    # Portfolio-level analytics
    portfolio_analytics = await suite.positions.get_portfolio_analytics()

    print(f"\nPortfolio Analytics:")
    print(f"  Total Exposure: ${portfolio_analytics['total_exposure']:.2f}")
    print(f"  Diversification Ratio: {portfolio_analytics['diversification_ratio']:.2f}")
    print(f"  Correlation Matrix: {portfolio_analytics['correlation_matrix']}")
```

## Risk Monitoring

### Position-Based Risk Calculations

```python
async def monitor_position_risk():
    suite = await TradingSuite.create("MNQ", features=["risk_manager"])

    # Get current risk metrics
    risk_metrics = await suite.positions.get_risk_metrics()

    print("Portfolio Risk Metrics:")
    print(f"  Total Risk: ${risk_metrics['total_risk']:.2f}")
    print(f"  Max Position Risk: ${risk_metrics['max_position_risk']:.2f}")
    print(f"  Portfolio Margin: ${risk_metrics['portfolio_margin']:.2f}")
    print(f"  Available Margin: ${risk_metrics['available_margin']:.2f}")

    # Per-position risk
    for position_risk in risk_metrics['positions']:
        print(f"\n{position_risk['instrument']}:")
        print(f"  Position Risk: ${position_risk['position_risk']:.2f}")
        print(f"  Margin Required: ${position_risk['margin_required']:.2f}")
        print(f"  Risk Contribution: {position_risk['risk_contribution']:.1%}")

    # Check risk limits
    for instrument in ["MNQ", "MES"]:
        position = await suite.positions.get_position(instrument)
        if position:
            risk_check = await suite.positions.check_position_risk(
                instrument, position.size
            )

            if risk_check['exceeded_limits']:
                print(f"= Risk limit exceeded for {instrument}!")
                for limit in risk_check['violated_limits']:
                    print(f"  - {limit['type']}: {limit['current']} > {limit['limit']}")
```

### Automated Risk Alerts

```python
class PositionRiskMonitor:
    def __init__(self, suite):
        self.suite = suite
        self.risk_thresholds = {
            'max_position_loss': Decimal('1000'),
            'max_portfolio_loss': Decimal('2000'),
            'max_position_size': 10,
            'correlation_limit': 0.8
        }

    async def setup_monitoring(self):
        """Setup automated risk monitoring."""

        # Register for position updates
        await self.suite.on(EventType.POSITION_UPDATED, self.check_position_risk)

        # Start background risk monitoring
        self.monitor_task = asyncio.create_task(self.continuous_monitoring())

    async def check_position_risk(self, event):
        """Check risk on position updates."""
        position_data = event.data

        # Check individual position loss
        unrealized_pnl = position_data.get('unrealizedPnL', 0)
        if unrealized_pnl < -self.risk_thresholds['max_position_loss']:
            await self.trigger_risk_alert(
                "Position Loss Limit",
                f"{position_data['contractId']} loss: ${abs(unrealized_pnl):.2f}"
            )

        # Check position size
        size = abs(position_data.get('size', 0))
        if size > self.risk_thresholds['max_position_size']:
            await self.trigger_risk_alert(
                "Position Size Limit",
                f"{position_data['contractId']} size: {size} contracts"
            )

    async def continuous_monitoring(self):
        """Continuous portfolio risk monitoring."""
        while True:
            try:
                # Check portfolio P&L
                portfolio_pnl = await self.suite.positions.get_portfolio_pnl()
                total_pnl = portfolio_pnl['unrealized_pnl']

                if total_pnl < -self.risk_thresholds['max_portfolio_loss']:
                    await self.trigger_risk_alert(
                        "Portfolio Loss Limit",
                        f"Portfolio loss: ${abs(total_pnl):.2f}"
                    )

                # Check correlations
                correlation_matrix = await self.suite.positions.get_correlation_matrix()
                high_correlations = [
                    (pair, corr) for pair, corr in correlation_matrix.items()
                    if abs(corr) > self.risk_thresholds['correlation_limit']
                ]

                if high_correlations:
                    for pair, corr in high_correlations:
                        await self.trigger_risk_alert(
                            "High Correlation",
                            f"{pair}: {corr:.2f}"
                        )

            except Exception as e:
                print(f"Risk monitoring error: {e}")

            await asyncio.sleep(30)  # Check every 30 seconds

    async def trigger_risk_alert(self, alert_type, message):
        """Trigger risk alert actions."""
        print(f"= RISK ALERT: {alert_type}")
        print(f"   {message}")

        # Could add:
        # - Email notifications
        # - Slack/Discord alerts
        # - Automatic position reduction
        # - Emergency exit orders

# Usage
async def run_risk_monitoring():
    suite = await TradingSuite.create("MNQ")

    monitor = PositionRiskMonitor(suite)
    await monitor.setup_monitoring()

    # Your trading logic here...

    # Keep monitoring running
    await asyncio.sleep(300)  # 5 minutes
```

## Position Operations

### Opening and Closing Positions

```python
async def position_operations():
    suite = await TradingSuite.create("MNQ")

    # Open new position via market order
    entry_response = await suite.orders.place_market_order(
        contract_id="MNQ",
        side=0,  # Buy
        size=2
    )

    print(f"Entry order: {entry_response.order_id}")

    # Wait for fill and check position
    await asyncio.sleep(5)

    position = await suite.positions.get_position("MNQ")
    if position and position.size > 0:
        print(f"Position opened: {position.size} contracts @ ${position.averagePrice}")

        # Close partial position
        await suite.positions.close_position(
            contract_id="MNQ",
            size=1  # Close 1 contract
        )

        # Check remaining position
        updated_position = await suite.positions.get_position("MNQ")
        print(f"Remaining: {updated_position.size} contracts")

        # Close entire position
        await suite.positions.close_position("MNQ")  # Close all

        # Verify closure
        final_position = await suite.positions.get_position("MNQ")
        if not final_position or final_position.size == 0:
            print("Position fully closed")
```

### Position Scaling

```python
async def scale_positions():
    suite = await TradingSuite.create("MNQ")

    # Initial position
    await suite.orders.place_market_order("MNQ", 0, 1)
    await asyncio.sleep(3)

    position = await suite.positions.get_position("MNQ")
    print(f"Initial position: {position.size}")

    # Scale into position (pyramid)
    current_price = await suite.data.get_current_price()

    # Add to winning position
    if position.unrealizedPnL and position.unrealizedPnL > 50:
        print("Position profitable - scaling in")

        await suite.orders.place_market_order("MNQ", 0, 1)  # Add 1 more

        await asyncio.sleep(3)
        updated_position = await suite.positions.get_position("MNQ")
        print(f"Scaled position: {updated_position.size} contracts")
        print(f"New average: ${updated_position.averagePrice}")

    # Scale out of position (profit taking)
    if position.unrealizedPnL and position.unrealizedPnL > 100:
        print("Taking partial profits")

        # Close half the position
        close_size = position.size // 2
        await suite.positions.close_position("MNQ", size=close_size)

        remaining = await suite.positions.get_position("MNQ")
        print(f"Remaining after profit taking: {remaining.size}")
```

### Position Averaging

```python
async def position_averaging():
    suite = await TradingSuite.create("MNQ")

    # Initial entry
    current_price = await suite.data.get_current_price()

    await suite.orders.place_limit_order(
        "MNQ", 0, 1,
        limit_price=Decimal(str(current_price)) - Decimal("25")
    )

    await asyncio.sleep(10)

    position = await suite.positions.get_position("MNQ")
    if not position:
        print("Initial order not filled")
        return

    print(f"Initial: {position.size} @ ${position.averagePrice}")

    # Average down if position moves against us
    if position.unrealizedPnL and position.unrealizedPnL < -100:
        print("Position underwater - averaging down")

        # Add same size at lower price
        current_market = await suite.data.get_current_price()
        avg_price = Decimal(str(current_market)) - Decimal("25")

        await suite.orders.place_limit_order("MNQ", 0, position.size, avg_price)

        await asyncio.sleep(10)

        updated_position = await suite.positions.get_position("MNQ")
        if updated_position.size > position.size:
            print(f"Averaged: {updated_position.size} @ ${updated_position.averagePrice}")
            print(f"Cost basis improved by: ${position.averagePrice - updated_position.averagePrice:.2f}")
```

## Position Reconciliation

### Automatic Position Validation

```python
async def position_reconciliation():
    suite = await TradingSuite.create("MNQ")

    # Get positions from different sources
    api_positions = await suite.positions.get_all_positions()

    # Compare with order-derived positions
    calculated_positions = await suite.positions.calculate_positions_from_orders()

    print("Position Reconciliation:")

    for instrument in set(
        [p.contractId for p in api_positions] +
        list(calculated_positions.keys())
    ):
        api_pos = next((p for p in api_positions if p.contractId == instrument), None)
        calc_pos = calculated_positions.get(instrument, 0)

        api_size = api_pos.size if api_pos else 0

        if api_size != calc_pos:
            print(f"  {instrument} mismatch:")
            print(f"   API: {api_size}")
            print(f"   Calculated: {calc_pos}")
            print(f"   Difference: {api_size - calc_pos}")

            # Auto-reconcile if needed
            await suite.positions.reconcile_position(instrument)
        else:
            print(f" {instrument}: {api_size} (matches)")
```

### Position Cleanup

```python
async def cleanup_positions():
    suite = await TradingSuite.create("MNQ")

    # Close all small positions (dust)
    all_positions = await suite.positions.get_all_positions()

    for position in all_positions:
        if abs(position.size) < 1:  # Fractional positions
            print(f"Cleaning up dust position: {position.contractId} ({position.size})")
            await suite.positions.close_position(position.contractId)

    # Close positions with small P&L impact
    for position in all_positions:
        if position.marketValue and abs(position.marketValue) < 100:  # <$100 value
            print(f"Closing small position: {position.contractId}")
            await suite.positions.close_position(position.contractId)

    # Emergency position cleanup
    emergency_instruments = ["OLD_CONTRACT", "EXPIRED_FUTURES"]

    for instrument in emergency_instruments:
        position = await suite.positions.get_position(instrument)
        if position and position.size != 0:
            print(f"Emergency close: {instrument}")
            await suite.positions.emergency_close(instrument)
```

## Portfolio Management

### Multi-Instrument Portfolio

```python
async def manage_portfolio():
    # Initialize suite for multiple instruments
    suite = await TradingSuite.create("MNQ")  # Primary instrument

    # Add additional instruments for portfolio
    instruments = ["MNQ", "MES", "MGC", "MCL"]

    # Get portfolio overview
    portfolio = await suite.positions.get_portfolio_summary()

    print("Portfolio Summary:")
    print(f"  Total Value: ${portfolio['total_value']:.2f}")
    print(f"  Total P&L: ${portfolio['total_pnl']:.2f}")
    print(f"  Day P&L: ${portfolio['day_pnl']:.2f}")
    print(f"  Positions: {len(portfolio['positions'])}")

    # Analyze portfolio composition
    for position in portfolio['positions']:
        weight = (position['market_value'] / portfolio['total_value']) * 100
        print(f"  {position['instrument']}: {weight:.1f}% (${position['market_value']:.0f})")

    # Portfolio rebalancing
    target_weights = {
        'MNQ': 40,  # 40% target
        'MES': 30,  # 30% target
        'MGC': 20,  # 20% target
        'MCL': 10   # 10% target
    }

    await rebalance_portfolio(suite, portfolio, target_weights)

async def rebalance_portfolio(suite, portfolio, target_weights):
    """Rebalance portfolio to target weights."""

    total_value = portfolio['total_value']

    for instrument, target_pct in target_weights.items():
        target_value = total_value * (target_pct / 100)

        # Find current position
        current_pos = next(
            (p for p in portfolio['positions'] if p['instrument'] == instrument),
            None
        )

        current_value = current_pos['market_value'] if current_pos else 0
        difference = target_value - current_value

        if abs(difference) > 100:  # Only rebalance if >$100 difference

            # Get instrument info for sizing
            instrument_info = await suite.client.get_instrument(instrument)
            contract_value = instrument_info.contractSize * instrument_info.lastPrice

            contracts_needed = int(difference / contract_value)

            if contracts_needed > 0:
                print(f"Buying {contracts_needed} {instrument} contracts")
                await suite.orders.place_market_order(instrument, 0, contracts_needed)
            elif contracts_needed < 0:
                print(f"Selling {abs(contracts_needed)} {instrument} contracts")
                await suite.orders.place_market_order(instrument, 1, abs(contracts_needed))
```

### Portfolio Performance Tracking

```python
async def track_portfolio_performance():
    suite = await TradingSuite.create("MNQ")

    # Daily performance tracking
    performance = await suite.positions.get_daily_performance()

    print("Daily Performance:")
    print(f"  Starting Balance: ${performance['starting_balance']:.2f}")
    print(f"  Current Balance: ${performance['current_balance']:.2f}")
    print(f"  Day P&L: ${performance['day_pnl']:.2f}")
    print(f"  Day Return: {performance['day_return']:.2%}")

    # Trade statistics
    print(f"\nTrade Statistics:")
    print(f"  Trades Today: {performance['trade_count']}")
    print(f"  Win Rate: {performance['win_rate']:.1%}")
    print(f"  Avg Win: ${performance['avg_win']:.2f}")
    print(f"  Avg Loss: ${performance['avg_loss']:.2f}")
    print(f"  Largest Win: ${performance['largest_win']:.2f}")
    print(f"  Largest Loss: ${performance['largest_loss']:.2f}")

    # Risk metrics
    print(f"\nRisk Metrics:")
    print(f"  Volatility: {performance['volatility']:.2%}")
    print(f"  Sharpe Ratio: {performance['sharpe_ratio']:.2f}")
    print(f"  Max Drawdown: {performance['max_drawdown']:.2%}")
    print(f"  Recovery Factor: {performance['recovery_factor']:.2f}")

    # Export performance data
    performance_data = await suite.positions.export_performance_data(
        format='csv',  # or 'json', 'excel'
        start_date=datetime.now() - timedelta(days=30)
    )

    print(f"Performance data exported to: {performance_data['file_path']}")
```

## Best Practices

### 1. Position Size Management

```python
class PositionSizer:
    def __init__(self, account_size: Decimal, risk_per_trade: Decimal = Decimal('0.01')):
        self.account_size = account_size
        self.risk_per_trade = risk_per_trade  # 1% default

    async def calculate_size(self, entry_price: Decimal, stop_price: Decimal,
                           instrument_info) -> int:
        """Calculate position size based on risk."""

        # Risk amount in dollars
        risk_amount = self.account_size * self.risk_per_trade

        # Points at risk
        points_at_risk = abs(entry_price - stop_price)

        # Contract value per point
        contract_multiplier = Decimal(str(instrument_info.contractSize or 1))
        dollar_risk_per_contract = points_at_risk * contract_multiplier

        # Position size
        position_size = risk_amount / dollar_risk_per_contract

        return max(1, int(position_size))  # At least 1 contract

# Usage
async def risk_based_position_sizing():
    suite = await TradingSuite.create("MNQ")

    account_balance = suite.client.account_info.balance
    sizer = PositionSizer(account_balance, risk_per_trade=Decimal('0.02'))  # 2% risk

    current_price = await suite.data.get_current_price()
    entry_price = Decimal(str(current_price))
    stop_price = entry_price - Decimal('50')  # 50 point stop

    instrument = await suite.client.get_instrument("MNQ")

    size = await sizer.calculate_size(entry_price, stop_price, instrument)

    print(f"Calculated position size: {size} contracts")
    print(f"Risk amount: ${sizer.account_size * sizer.risk_per_trade:.2f}")
```

### 2. Position Correlation Management

```python
async def manage_position_correlation():
    suite = await TradingSuite.create("MNQ")

    # Get current positions
    positions = await suite.positions.get_all_positions()

    if len(positions) < 2:
        print("Need at least 2 positions for correlation analysis")
        return

    # Calculate position correlations
    correlation_matrix = await suite.positions.get_correlation_matrix()

    print("Position Correlations:")
    for pair, correlation in correlation_matrix.items():
        print(f"  {pair}: {correlation:.2f}")

        # Alert on high correlation
        if abs(correlation) > 0.8:
            print(f"      High correlation detected!")

            # Consider reducing one position
            instruments = pair.split('-')
            positions_data = [(p.contractId, abs(p.unrealizedPnL or 0)) for p in positions
                            if p.contractId in instruments]

            # Close position with larger loss
            if positions_data:
                worst_instrument = max(positions_data, key=lambda x: x[1])[0]
                print(f"    Consider reducing {worst_instrument} position")
```

### 3. Position Health Monitoring

```python
class PositionHealthMonitor:
    def __init__(self, suite):
        self.suite = suite
        self.health_checks = {
            'unrealized_loss_limit': Decimal('500'),
            'hold_time_limit': timedelta(hours=4),
            'correlation_limit': 0.75,
            'concentration_limit': 0.3  # Max 30% in one position
        }

    async def check_position_health(self) -> dict:
        """Comprehensive position health check."""

        positions = await self.suite.positions.get_all_positions()
        portfolio_value = sum(abs(p.marketValue or 0) for p in positions)

        health_report = {
            'overall_health': 'HEALTHY',
            'issues': [],
            'recommendations': []
        }

        for position in positions:
            # Check unrealized loss
            if position.unrealizedPnL and position.unrealizedPnL < -self.health_checks['unrealized_loss_limit']:
                health_report['issues'].append(
                    f"{position.contractId}: Large unrealized loss ${abs(position.unrealizedPnL):.2f}"
                )
                health_report['recommendations'].append(
                    f"Consider stop loss for {position.contractId}"
                )

            # Check position concentration
            if portfolio_value > 0:
                concentration = abs(position.marketValue or 0) / portfolio_value
                if concentration > self.health_checks['concentration_limit']:
                    health_report['issues'].append(
                        f"{position.contractId}: High concentration {concentration:.1%}"
                    )
                    health_report['recommendations'].append(
                        f"Diversify away from {position.contractId}"
                    )

            # Check hold time (if available)
            if hasattr(position, 'entry_time') and position.entry_time:
                hold_time = datetime.now() - position.entry_time
                if hold_time > self.health_checks['hold_time_limit']:
                    health_report['issues'].append(
                        f"{position.contractId}: Long hold time {hold_time}"
                    )

        # Set overall health
        if len(health_report['issues']) > 3:
            health_report['overall_health'] = 'CRITICAL'
        elif len(health_report['issues']) > 1:
            health_report['overall_health'] = 'WARNING'

        return health_report

# Usage
async def run_health_check():
    suite = await TradingSuite.create("MNQ")

    monitor = PositionHealthMonitor(suite)
    health = await monitor.check_position_health()

    print(f"Position Health: {health['overall_health']}")

    if health['issues']:
        print("\nIssues:")
        for issue in health['issues']:
            print(f"    {issue}")

    if health['recommendations']:
        print("\nRecommendations:")
        for rec in health['recommendations']:
            print(f"  = {rec}")
```

## Integration with Risk Manager

When using the RiskManager feature, position management becomes even more sophisticated:

```python
async def risk_managed_positions():
    # Enable risk management
    suite = await TradingSuite.create("MNQ", features=["risk_manager"])

    # Set position limits
    await suite.risk_manager.set_position_limit("MNQ", max_contracts=5)
    await suite.risk_manager.set_portfolio_limit(max_exposure=Decimal("50000"))

    # Positions are automatically validated against risk limits
    try:
        # This will be checked against risk limits
        response = await suite.orders.place_market_order("MNQ", 0, 10)  # Large order

    except ProjectXRiskViolationError as e:
        print(f"Order blocked by risk manager: {e}")

        # Get risk recommendations
        recommendations = await suite.risk_manager.get_position_recommendations("MNQ")
        print(f"Recommended max size: {recommendations['max_safe_size']}")

    # Use managed trades for automatic position management
    async with suite.managed_trade(max_risk_percent=0.02) as trade:  # 2% portfolio risk

        # Trade calculates position size automatically
        result = await trade.enter_long(
            entry_price=current_price,
            stop_loss=current_price - Decimal("50"),
            take_profit=current_price + Decimal("100")
        )

        print(f"Managed trade entered: {result.position_size} contracts")

        # Position is automatically managed until context exit
        await asyncio.sleep(300)  # 5 minutes

    # Trade automatically closed when context exits
```

## Summary

The ProjectX PositionManager provides comprehensive position management capabilities:

- **Real-time tracking** with WebSocket position updates
- **Performance analytics** with detailed P&L analysis
- **Risk monitoring** with automated alerts and limits
- **Portfolio management** across multiple instruments
- **Position reconciliation** for data integrity
- **Advanced analytics** including correlation and risk metrics
- **Integration with RiskManager** for automated position validation

All position operations are designed for production trading with proper error handling, real-time updates, and comprehensive risk management features.

---

**Next**: [Real-time Data Guide](realtime.md) | **Previous**: [Order Management Guide](orders.md)
