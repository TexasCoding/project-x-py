# Backtesting Examples

This page demonstrates how to backtest trading strategies using the ProjectX Python SDK. Learn to test strategies on historical data, evaluate performance, and optimize parameters before live trading.

## Prerequisites

- ProjectX Python SDK installed (Python 3.12+)
- Access to historical market data
- Understanding of trading strategy development
- Basic knowledge of performance metrics

## 1. Simple Strategy Backtesting Framework

Start with a basic backtesting framework:

```python
#!/usr/bin/env python
"""
Simple strategy backtesting framework
"""
import asyncio
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List, Dict, Optional
import polars as pl
from project_x_py import ProjectX
from project_x_py.indicators import SMA, RSI, MACD

@dataclass
class Trade:
    entry_time: datetime
    exit_time: Optional[datetime]
    entry_price: float
    exit_price: Optional[float]
    direction: str  # 'long' or 'short'
    size: int
    pnl: Optional[float] = None
    status: str = 'open'  # 'open', 'closed'

@dataclass
class BacktestResults:
    trades: List[Trade]
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    max_drawdown: float
    sharpe_ratio: float
    max_consecutive_losses: int
    avg_trade_duration: timedelta

class SimpleBacktester:
    def __init__(self, initial_capital: float = 100000.0):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.trades: List[Trade] = []
        self.equity_curve: List[Dict] = []

    async def get_historical_data(self, symbol: str, days: int = 30) -> pl.DataFrame:
        """Get historical data for backtesting."""
        async with ProjectX.from_env() as client:
            await client.authenticate()

            # Calculate date range
            end_time = datetime.now()
            start_time = end_time - timedelta(days=days)

            # Get historical bars
            bars = await client.get_bars(
                symbol,
                start_time=start_time,
                end_time=end_time
            )

            if not bars:
                raise ValueError(f"No historical data available for {symbol}")

            print(f"Retrieved {len(bars)} historical bars for {symbol}")
            return bars

    def simple_sma_crossover_strategy(self, data: pl.DataFrame) -> List[Dict]:
        """Simple SMA crossover strategy."""
        # Calculate SMAs
        sma_fast = data.pipe(SMA, period=10)
        sma_slow = data.pipe(SMA, period=20)

        signals = []

        for i in range(1, len(data)):
            current_time = data['timestamp'][i]
            current_price = data['close'][i]

            # Skip if we don't have enough data for indicators
            if i < 20:
                continue

            prev_fast = sma_fast[i-1]
            curr_fast = sma_fast[i]
            prev_slow = sma_slow[i-1]
            curr_slow = sma_slow[i]

            # Bullish crossover: fast SMA crosses above slow SMA
            if prev_fast <= prev_slow and curr_fast > curr_slow:
                signals.append({
                    'timestamp': current_time,
                    'price': current_price,
                    'signal': 'buy',
                    'fast_sma': curr_fast,
                    'slow_sma': curr_slow
                })

            # Bearish crossover: fast SMA crosses below slow SMA
            elif prev_fast >= prev_slow and curr_fast < curr_slow:
                signals.append({
                    'timestamp': current_time,
                    'price': current_price,
                    'signal': 'sell',
                    'fast_sma': curr_fast,
                    'slow_sma': curr_slow
                })

        return signals

    def execute_backtest(self, data: pl.DataFrame, signals: List[Dict]) -> None:
        """Execute backtest with generated signals."""
        current_position = None
        position_size = 1  # Number of contracts

        for signal in signals:
            signal_time = signal['timestamp']
            signal_price = signal['price']
            signal_type = signal['signal']

            if signal_type == 'buy' and not current_position:
                # Open long position
                current_position = Trade(
                    entry_time=signal_time,
                    exit_time=None,
                    entry_price=signal_price,
                    exit_price=None,
                    direction='long',
                    size=position_size,
                    status='open'
                )

                print(f"LONG entry at ${signal_price:.2f} on {signal_time}")

            elif signal_type == 'sell':
                if current_position and current_position.direction == 'long':
                    # Close long position
                    current_position.exit_time = signal_time
                    current_position.exit_price = signal_price
                    current_position.status = 'closed'

                    # Calculate P&L (MNQ multiplier = 20)
                    price_diff = signal_price - current_position.entry_price
                    current_position.pnl = price_diff * position_size * 20
                    self.capital += current_position.pnl

                    print(f"LONG exit at ${signal_price:.2f}, P&L: ${current_position.pnl:.2f}")

                    self.trades.append(current_position)
                    current_position = None

                # Could also open short position here if desired
                # For simplicity, this example only trades long

        # Close any remaining position at the end
        if current_position:
            last_price = data['close'][-1]
            last_time = data['timestamp'][-1]

            current_position.exit_time = last_time
            current_position.exit_price = last_price
            current_position.status = 'closed'

            price_diff = last_price - current_position.entry_price
            current_position.pnl = price_diff * position_size * 20
            self.capital += current_position.pnl

            self.trades.append(current_position)
            print(f"Closed remaining position at ${last_price:.2f}, P&L: ${current_position.pnl:.2f}")

    def calculate_metrics(self) -> BacktestResults:
        """Calculate backtest performance metrics."""
        if not self.trades:
            raise ValueError("No trades to analyze")

        # Basic trade statistics
        total_trades = len(self.trades)
        winning_trades = sum(1 for trade in self.trades if trade.pnl > 0)
        losing_trades = sum(1 for trade in self.trades if trade.pnl <= 0)
        win_rate = winning_trades / total_trades if total_trades > 0 else 0

        # P&L statistics
        total_pnl = sum(trade.pnl for trade in self.trades)
        winning_pnl = sum(trade.pnl for trade in self.trades if trade.pnl > 0)
        losing_pnl = sum(trade.pnl for trade in self.trades if trade.pnl <= 0)

        # Drawdown calculation
        equity_curve = [self.initial_capital]
        running_capital = self.initial_capital

        for trade in self.trades:
            running_capital += trade.pnl
            equity_curve.append(running_capital)

        peak = self.initial_capital
        max_drawdown = 0

        for equity in equity_curve:
            if equity > peak:
                peak = equity
            drawdown = (peak - equity) / peak if peak > 0 else 0
            max_drawdown = max(max_drawdown, drawdown)

        # Average trade duration
        trade_durations = []
        for trade in self.trades:
            if trade.exit_time and trade.entry_time:
                duration = trade.exit_time - trade.entry_time
                trade_durations.append(duration)

        avg_duration = sum(trade_durations, timedelta()) / len(trade_durations) if trade_durations else timedelta()

        # Consecutive losses
        max_consecutive_losses = 0
        current_consecutive_losses = 0

        for trade in self.trades:
            if trade.pnl <= 0:
                current_consecutive_losses += 1
                max_consecutive_losses = max(max_consecutive_losses, current_consecutive_losses)
            else:
                current_consecutive_losses = 0

        # Simple Sharpe ratio approximation (assuming daily returns)
        if len(self.trades) > 1:
            returns = [trade.pnl / self.initial_capital for trade in self.trades]
            avg_return = sum(returns) / len(returns)
            return_std = (sum((r - avg_return) ** 2 for r in returns) / (len(returns) - 1)) ** 0.5
            sharpe_ratio = (avg_return / return_std) * (252 ** 0.5) if return_std > 0 else 0
        else:
            sharpe_ratio = 0

        return BacktestResults(
            trades=self.trades,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            total_pnl=total_pnl,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            max_consecutive_losses=max_consecutive_losses,
            avg_trade_duration=avg_duration
        )

    def print_results(self, results: BacktestResults) -> None:
        """Print formatted backtest results."""
        print("\n" + "="*60)
        print("BACKTEST RESULTS")
        print("="*60)

        print(f"Initial Capital: ${self.initial_capital:,.2f}")
        print(f"Final Capital: ${self.capital:,.2f}")
        print(f"Total Return: ${results.total_pnl:,.2f} ({(results.total_pnl/self.initial_capital)*100:.2f}%)")

        print(f"\nTrade Statistics:")
        print(f"  Total Trades: {results.total_trades}")
        print(f"  Winning Trades: {results.winning_trades}")
        print(f"  Losing Trades: {results.losing_trades}")
        print(f"  Win Rate: {results.win_rate:.2%}")

        if results.winning_trades > 0:
            avg_winner = sum(trade.pnl for trade in results.trades if trade.pnl > 0) / results.winning_trades
            print(f"  Average Winner: ${avg_winner:.2f}")

        if results.losing_trades > 0:
            avg_loser = sum(trade.pnl for trade in results.trades if trade.pnl <= 0) / results.losing_trades
            print(f"  Average Loser: ${avg_loser:.2f}")

        print(f"\nRisk Metrics:")
        print(f"  Maximum Drawdown: {results.max_drawdown:.2%}")
        print(f"  Max Consecutive Losses: {results.max_consecutive_losses}")
        print(f"  Sharpe Ratio: {results.sharpe_ratio:.2f}")
        print(f"  Average Trade Duration: {results.avg_trade_duration}")

        print(f"\nTrade Details:")
        for i, trade in enumerate(results.trades, 1):
            duration = trade.exit_time - trade.entry_time if trade.exit_time else "N/A"
            print(f"  {i:2}: {trade.direction.upper()} ${trade.entry_price:.2f} -> ${trade.exit_price:.2f} | "
                  f"P&L: ${trade.pnl:.2f} | Duration: {duration}")

        print("="*60)

async def main():
    # Initialize backtester
    backtester = SimpleBacktester(initial_capital=100000.0)

    print("Simple SMA Crossover Strategy Backtest")
    print("Strategy: Long when 10-period SMA crosses above 20-period SMA")
    print("Exit: When 10-period SMA crosses below 20-period SMA")

    # Get historical data
    try:
        data = await backtester.get_historical_data("MNQ", days=30)

        # Generate trading signals
        signals = backtester.simple_sma_crossover_strategy(data)
        print(f"Generated {len(signals)} trading signals")

        # Execute backtest
        backtester.execute_backtest(data, signals)

        # Calculate and display results
        if backtester.trades:
            results = backtester.calculate_metrics()
            backtester.print_results(results)
        else:
            print("No trades were generated during the backtest period")

    except Exception as e:
        print(f"Backtest failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Key Backtesting Concepts

### Strategy Development Workflow

1. **Hypothesis Formation**: Define a testable trading idea
2. **Historical Data Collection**: Gather sufficient data for testing
3. **Strategy Implementation**: Code the entry/exit logic
4. **Parameter Optimization**: Find optimal settings using in-sample data
5. **Out-of-Sample Testing**: Validate on unseen data
6. **Walk-Forward Analysis**: Test robustness over time
7. **Live Paper Trading**: Final validation before real money

### Important Backtesting Pitfalls

- **Look-ahead Bias**: Using future information in decisions
- **Survivorship Bias**: Only testing on currently active instruments
- **Overfitting**: Optimizing too much on historical data
- **Transaction Costs**: Ignoring slippage and commissions
- **Data Quality**: Using unrealistic or poor quality data
- **Market Regime Changes**: Strategies that worked historically may not work in current markets

### Performance Metrics

- **Total Return**: Overall profit/loss
- **Sharpe Ratio**: Risk-adjusted returns
- **Maximum Drawdown**: Worst peak-to-trough decline
- **Win Rate**: Percentage of profitable trades
- **Profit Factor**: Gross profit / Gross loss
- **Average Trade Duration**: Time positions are held

## Best Practices

### Data Management
```python
# Always use sufficient historical data
data = await client.get_bars("MNQ", days=365)  # At least 1 year

# Handle missing data appropriately
if len(data) < minimum_required_bars:
    raise ValueError("Insufficient data for backtesting")
```

### Realistic Assumptions
```python
# Include transaction costs
commission = 2.50  # Per contract per side
slippage = 1 * 0.25  # 1 tick slippage

net_pnl = gross_pnl - (commission * 2) - slippage
```

### Risk Management
```python
# Position sizing based on account equity
max_risk_per_trade = account_balance * 0.02  # 2% risk
position_size = max_risk_per_trade / (stop_distance * 20)  # MNQ multiplier
```

## Next Steps

After mastering backtesting:

1. **Paper Trading**: Test strategies in real-time with fake money
2. **Live Implementation**: Start with small position sizes
3. **Strategy Monitoring**: Track live performance vs backtests
4. **Continuous Optimization**: Adapt strategies to changing markets
5. **Portfolio Management**: Combine multiple uncorrelated strategies

See also:
- [Advanced Trading Examples](advanced.md) for strategy implementation
- [Real-time Data Examples](realtime.md) for live testing
- [Basic Usage Examples](basic.md) for fundamentals
