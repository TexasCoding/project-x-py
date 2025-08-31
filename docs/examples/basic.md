# Basic Usage Examples

This page demonstrates the most fundamental usage patterns of the ProjectX Python SDK v3.3.4. All examples use async/await patterns and are designed for beginners getting started with the SDK.

## Prerequisites

Before running these examples, ensure you have:

- Valid ProjectX API credentials
- Environment variables set (`PROJECT_X_API_KEY`, `PROJECT_X_USERNAME`, `PROJECT_X_ACCOUNT_NAME`)
- Python 3.11+ with the SDK installed

## 1. TradingSuite Quick Start

The `TradingSuite` is the recommended way to get started. It provides a unified interface to all SDK components.

```python
#!/usr/bin/env python
"""
Basic TradingSuite usage - the recommended way to start
"""
import asyncio
import logging
from project_x_py import TradingSuite

async def main():
    # One-line setup - creates and connects everything
    suite = await TradingSuite.create(
        ["MNQ"],  # Micro E-mini NASDAQ
        timeframes=["1min", "5min"],  # Optional: specific timeframes
        initial_days=3  # Optional: historical data to load
    )
    mnq_context = suite["MNQ"]

    print(f"Connected: {suite.is_connected}")
    print(f"Instrument: {mnq_context.symbol}")
    print(f"Current Price: {await mnq_context.data.get_current_price()}")

    # Access all managers directly
    print(f"Data Manager: {type(mnq_context.data).__name__}")
    print(f"Order Manager: {type(mnq_context.orders).__name__}")
    print(f"Position Manager: {type(mnq_context.positions).__name__}")

if __name__ == "__main__":
    asyncio.run(main())
```

## 2. Basic Client Connection

For lower-level access, you can use the `ProjectX` client directly:

```python
#!/usr/bin/env python
"""
Basic client connection and authentication
"""
import asyncio
from project_x_py import ProjectX

async def main():
    # Create client with environment variables
    async with ProjectX.from_env() as client:
        # Authenticate (happens automatically)
        await client.authenticate()

        # Get account information
        account_info = await client.get_account_info()
        print(f"Account: {account_info}")

        # Get instrument information
        instruments = await client.get_instruments()
        mnq = next((i for i in instruments if i.symbol == "MNQ"), None)
        print(f"MNQ Contract: {mnq}")

        # Get historical market data
        bars = await client.get_bars("MNQ", days=1)
        print(f"Retrieved {len(bars)} bars")
        print(f"Latest bar: {bars[-1] if bars else 'No data'}")

if __name__ == "__main__":
    asyncio.run(main())
```

## 3. Market Data Basics

Getting historical and current market data:

```python
#!/usr/bin/env python
"""
Basic market data retrieval
"""
import asyncio
from datetime import datetime, timedelta
from project_x_py import TradingSuite

async def main():
    suite = await TradingSuite.create(["MNQ"], timeframes=["1min", "5min"])
    mnq_data = suite["MNQ"].data

    # Get current market data
    current_price = await mnq_data.get_current_price()
    print(f"Current Price: ${current_price:,.2f}")

    # Get historical bars for different timeframes
    bars_1min = await mnq_data.get_data("1min")
    bars_5min = await mnq_data.get_data("5min")

    print(f"1min bars: {len(bars_1min)} records")
    print(f"5min bars: {len(bars_5min)} records")

    # Get bars with specific date range
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=2)

    recent_bars = await suite.client.get_bars(
        "MNQ",
        start_time=start_time,
        end_time=end_time
    )
    print(f"Recent 2-hour bars: {len(recent_bars)}")

    # Display latest bar information
    if len(bars_1min) > 0:
        latest = bars_1min[-1]
        print(f"Latest 1min bar:")
        print(f"  Time: {latest['timestamp']}")
        print(f"  OHLC: ${latest['open']:.2f} / ${latest['high']:.2f} / ${latest['low']:.2f} / ${latest['close']:.2f}")
        print(f"  Volume: {latest['volume']}")

if __name__ == "__main__":
    asyncio.run(main())
```

## 4. Basic Position Monitoring

Monitor your current positions:

```python
#!/usr/bin/env python
"""
Basic position monitoring - READ ONLY
"""
import asyncio
from project_x_py import TradingSuite

async def main():
    suite = await TradingSuite.create(["MNQ"])
    mnq_positions = suite["MNQ"].positions

    # Get all current positions
    positions = await mnq_positions.get_all_positions()
    print(f"Total positions: {len(positions)}")

    # Check specific instrument position
    mnq_position = await mnq_positions.get_position("MNQ")
    if mnq_position:
        print(f"MNQ Position:")
        print(f"  Size: {mnq_position.size}")
        print(f"  Side: {'Long' if mnq_position.size > 0 else 'Short' if mnq_position.size < 0 else 'Flat'}")
        print(f"  Average Price: ${mnq_position.average_price:.2f}")
        print(f"  Unrealized P&L: ${mnq_position.unrealized_pnl:.2f}")
        print(f"  Realized P&L: ${mnq_position.realized_pnl:.2f}")
    else:
        print("No MNQ position found")

    # Get portfolio-level statistics
    portfolio_stats = await mnq_positions.get_portfolio_stats()
    print(f"Portfolio Stats:")
    print(f"  Total P&L: ${portfolio_stats.get('total_pnl', 0):.2f}")
    print(f"  Open Positions: {portfolio_stats.get('open_positions', 0)}")

if __name__ == "__main__":
    asyncio.run(main())
```

## 5. Technical Indicators

Using the built-in technical indicators:

```python
#!/usr/bin/env python
"""
Basic technical indicator usage
"""
import asyncio
from project_x_py import TradingSuite
from project_x_py.indicators import SMA, RSI, MACD, ATR

async def main():
    suite = await TradingSuite.create(["MNQ"], timeframes=["5min"], initial_days=5)
    mnq_data = suite["MNQ"].data

    # Get market data
    bars = await mnq_data.get_data("5min")
    print(f"Calculating indicators on {len(bars)} bars")

    # Simple Moving Average
    sma_20 = bars.pipe(SMA, period=20)
    sma_50 = bars.pipe(SMA, period=50)

    # RSI (Relative Strength Index)
    rsi = bars.pipe(RSI, period=14)

    # MACD (Moving Average Convergence Divergence)
    macd_result = bars.pipe(MACD, fast_period=12, slow_period=26, signal_period=9)

    # ATR (Average True Range) for volatility
    atr = bars.pipe(ATR, period=14)

    # Display latest values
    if len(bars) >= 50:  # Ensure we have enough data
        print("Latest Technical Indicators:")
        print(f"  Price: ${bars['close'][-1]:.2f}")
        print(f"  SMA 20: ${sma_20[-1]:.2f}")
        print(f"  SMA 50: ${sma_50[-1]:.2f}")
        print(f"  RSI: {rsi[-1]:.2f}")
        print(f"  MACD: {macd_result['macd'][-1]:.4f}")
        print(f"  MACD Signal: {macd_result['signal'][-1]:.4f}")
        print(f"  MACD Histogram: {macd_result['histogram'][-1]:.4f}")
        print(f"  ATR: ${atr[-1]:.2f}")

        # Simple trend analysis
        current_price = bars['close'][-1]
        if current_price > sma_20[-1] > sma_50[-1]:
            print("  Trend: BULLISH (Price > SMA20 > SMA50)")
        elif current_price < sma_20[-1] < sma_50[-1]:
            print("  Trend: BEARISH (Price < SMA20 < SMA50)")
        else:
            print("  Trend: MIXED")
    else:
        print("Not enough data for all indicators")

if __name__ == "__main__":
    asyncio.run(main())
```

## 6. Event Handling Basics

Setting up basic event handlers:

```python
#!/usr/bin/env python
"""
Basic event handling with TradingSuite
"""
import asyncio
from project_x_py import TradingSuite, EventType

async def main():
    suite = await TradingSuite.create(["MNQ"], timeframes=["1min"])
    mnq_context = suite["MNQ"]

    # Define event handlers
    async def on_new_bar(event):
        bar_data = event.data
        print(f"New 1min bar: ${bar_data['close']:.2f} @ {bar_data['timestamp']}")

    async def on_tick(event):
        tick_data = event.data
        print(f"New tick: ${tick_data.get('price', 0):.2f}")

    # Register event handlers
    await mnq_context.on(EventType.NEW_BAR, on_new_bar)
    await mnq_context.on(EventType.TICK, on_tick)

    print("Listening for events... Press Ctrl+C to exit")

    try:
        # Keep the program running to receive events
        while True:
            await asyncio.sleep(1)

            # Display current data periodically
            current_price = await mnq_context.data.get_current_price()
            print(f"Current price: ${current_price:.2f}")

    except KeyboardInterrupt:
        print("Shutting down...")

if __name__ == "__main__":
    asyncio.run(main())
```

## 7. Basic Statistics and Health Monitoring

Monitor SDK performance and health:

```python
#!/usr/bin/env python
"""
Basic statistics and health monitoring
"""
import asyncio
from project_x_py import TradingSuite

async def main():
    suite = await TradingSuite.create("MNQ", timeframes=["1min", "5min"])

    # Get suite statistics
    stats = await suite.get_stats()
    print("TradingSuite Statistics:")
    print(f"  Total Operations: {stats.get('total_operations', 0)}")
    print(f"  Total Errors: {stats.get('total_errors', 0)}")
    print(f"  Memory Usage: {stats.get('memory_usage_mb', 0):.1f} MB")
    print(f"  Component Count: {stats.get('components', 0)}")

    # Calculate health score using HealthMonitor
    from project_x_py.statistics.health import HealthMonitor
    monitor = HealthMonitor()
    health_score = await monitor.calculate_health(stats)
    print(f"\nOverall Health Score: {health_score:.1f}/100")
    status = "EXCELLENT" if health_score >= 90 else "GOOD" if health_score >= 70 else "WARNING" if health_score >= 50 else "CRITICAL"
    print(f"Status: {status}")

    # Get detailed health breakdown
    breakdown = await monitor.get_health_breakdown(stats)
    print("\nHealth Breakdown:")
    for category, score in breakdown.items():
        if category not in ['overall_score', 'weighted_total']:
            print(f"  {category}: {score:.1f}/100")

    # Memory usage is already in stats
    memory_mb = stats.get('memory_usage_mb', 0)
    print(f"\nMemory Usage:")
    for component, memory_info in memory_stats.items():
        print(f"  {component}: {memory_info}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Error Handling Best Practices

Always include proper error handling in your applications:

```python
#!/usr/bin/env python
"""
Proper error handling patterns
"""
import asyncio
import logging
from project_x_py import TradingSuite, ProjectXException, AuthenticationError

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    try:
        suite = await TradingSuite.create(["MNQ"], timeframes=["1min"])
        mnq_context = suite["MNQ"]

        # Attempt to get data with error handling
        try:
            current_price = await mnq_context.data.get_current_price()
            logger.info(f"Current price: ${current_price:.2f}")
        except ProjectXException as e:
            logger.error(f"Failed to get current price: {e}")

        # Attempt to get positions with error handling
        try:
            positions = await mnq_context.positions.get_all_positions()
            logger.info(f"Retrieved {len(positions)} positions")
        except ProjectXException as e:
            logger.error(f"Failed to get positions: {e}")

    except AuthenticationError as e:
        logger.error(f"Authentication failed: {e}")
        logger.error("Check your API credentials and account permissions")
    except ProjectXException as e:
        logger.error(f"SDK error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
```

## Running the Examples

To run any of these examples:

1. **Using the test script** (recommended):
   ```bash
   ./test.sh /path/to/your_example.py
   ```

2. **Manually with environment variables**:
   ```bash
   export PROJECT_X_API_KEY="your_api_key"  # pragma: allowlist secret
   export PROJECT_X_USERNAME="your_username"
   export PROJECT_X_ACCOUNT_NAME="your_account_name"
   uv run python your_example.py
   ```

## Next Steps

Once you're comfortable with these basic examples:

1. **Explore Advanced Examples**: Check out [Advanced Trading](advanced.md) for complex strategies
2. **Real-time Processing**: Learn about [Real-time Data](realtime.md) handling
3. **Order Placement**: Study the order management examples ( places real orders!)
4. **Custom Indicators**: Build your own technical indicators
5. **Event-Driven Architecture**: Create sophisticated event-driven trading systems

## Safety Reminders

- **Always test with demo accounts first**
- **Use micro contracts (MNQ) to minimize risk**
- **Include proper error handling and logging**
- **Monitor positions and orders closely**
- **Set appropriate stop losses and risk limits**

For production usage, always implement comprehensive risk management and position sizing algorithms.
