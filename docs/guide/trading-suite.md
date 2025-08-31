# Trading Suite Guide

The TradingSuite is the recommended entry point for building trading applications with the ProjectX SDK. **In v3.5.0, it has been revolutionized with multi-instrument support**, enabling simultaneous management of multiple futures contracts while maintaining full backward compatibility. It provides a unified interface that combines all components (client, order management, position tracking, real-time data, and optional features) into a single, easy-to-use container.

## Why Use TradingSuite?

The TradingSuite simplifies SDK usage by:

- **One-line initialization** - No complex setup or dependency management
- **Multi-instrument support (v3.5.0)** - Manage multiple contracts simultaneously
- **Automatic component wiring** - All components work together seamlessly
- **Built-in configuration** - Sensible defaults with easy customization
- **Feature flags** - Enable only what you need
- **Unified event system** - Single place to handle all trading events
- **Dictionary-like access** - Intuitive `suite["SYMBOL"]` syntax
- **Event isolation** - Proper separation between instruments
- **Parallel processing** - Efficient concurrent operations

## Quick Start

### Single Instrument Setup (Backward Compatible)

```python
import asyncio
from project_x_py import TradingSuite

async def main():
    # Traditional single instrument (still supported)
    suite = await TradingSuite.create(["MNQ"])  # List notation recommended
    mnq = suite["MNQ"]  # Access instrument context

    # Everything is ready:
    # - Client authenticated
    # - Real-time data connected
    # - Order and position managers initialized

    # Get current price
    price = await mnq.data.get_current_price()
    print(f"MNQ Current Price: ${price:.2f}")

    # Clean shutdown
    await suite.disconnect()

asyncio.run(main())
```

### Multi-Instrument Setup (v3.5.0 New)

```python
async def multi_instrument_main():
    # Revolutionary multi-instrument support
    suite = await TradingSuite.create(
        instruments=["MNQ", "ES", "MGC"],  # Multiple futures
        timeframes=["1min", "5min"],
        features=["orderbook", "risk_manager"]
    )

    print(f"Managing {len(suite)} instruments: {list(suite.keys())}")

    # Dictionary-like access to each instrument
    mnq_context = suite["MNQ"]
    es_context = suite["ES"]
    mgc_context = suite["MGC"]

    # Get prices for all instruments
    for symbol, context in suite.items():
        price = await context.data.get_current_price()
        print(f"{symbol}: ${price:.2f}")

    await suite.disconnect()

asyncio.run(multi_instrument_main())
```

### Multi-Timeframe Setup

```python
async def multi_timeframe_setup():
    # Setup with multiple timeframes for analysis
    suite = await TradingSuite.create(
        ["MNQ"],  # Single instrument with multiple timeframes
        timeframes=["1min", "5min", "15min"],
        initial_days=10  # Load 10 days of historical data
    )

    mnq = suite["MNQ"]

    # Access different timeframe data
    bars_1min = await mnq.data.get_data("1min")
    bars_5min = await mnq.data.get_data("5min")
    bars_15min = await mnq.data.get_data("15min")

    print(f"MNQ 1min bars: {len(bars_1min)}")
    print(f"MNQ 5min bars: {len(bars_5min)}")
    print(f"MNQ 15min bars: {len(bars_15min)}")

    await suite.disconnect()

# Multi-instrument with multiple timeframes
async def multi_instrument_timeframes():
    suite = await TradingSuite.create(
        ["MNQ", "ES"],  # List of instruments
        timeframes=["1min", "5min", "15min"]
    )

    # Each instrument has all timeframes available
    for symbol, context in suite.items():
        bars_5min = await context.data.get_data("5min")
        print(f"{symbol} 5min bars: {len(bars_5min)}")

    await suite.disconnect()

asyncio.run(multi_timeframe_setup())
```

### Multi-Instrument with Optional Features

```python
async def feature_setup():
    # Enable optional features for multiple instruments
    suite = await TradingSuite.create(
        ["MNQ", "ES"],  # List of instruments
        timeframes=["1min", "5min"],
        features=["orderbook", "risk_manager"],
    )

    # Each instrument has its own feature instances
    total_exposure = 0.0
    for symbol, context in suite.items():
        print(f"\n{symbol} Features:")

        # Level 2 order book data (per instrument)
        if context.orderbook:
            snapshot = await context.orderbook.get_orderbook_snapshot()
            print(
                f"  Order book depth: {len(snapshot['bids'])} bids, {len(snapshot['asks'])} asks"
            )

        # Risk management tools (per instrument)
        if context.risk_manager:
            # Access risk configuration
            config = context.risk_manager.config
            print(f"  Max position size: {config.max_position_size}")

            # Get current risk metrics
            metrics = await context.risk_manager.get_risk_metrics()
            print(f"  Current risk: ${metrics['current_risk']:,.2f}")
            print(f"  Margin used: ${metrics['margin_used']:,.2f}")
            total_exposure += metrics["margin_used"]

    # Portfolio-level risk summary
    print(f"\nTotal Portfolio Exposure: ${total_exposure:,.2f}")

    await suite.disconnect()


asyncio.run(feature_setup())
```

## Configuration Options

### Basic Configuration

```python
from project_x_py import TradingSuite

async def basic_config():
    suite = await TradingSuite.create(
        "ES",                      # E-mini S&P 500 (positional argument)
        timeframes=["5min"],       # Single timeframe
        initial_days=5,            # 5 days of history
        timezone="America/New_York", # Eastern timezone
        auto_connect=True          # Auto-connect (default)
    )

    await suite.disconnect()
```

### Advanced Configuration

```python
from project_x_py.types import (
    OrderManagerConfig,
    PositionManagerConfig,
    DataManagerConfig
)

async def advanced_config():
    # Custom component configurations
    order_config = OrderManagerConfig(
        max_concurrent_orders=5,
        default_timeout=60.0,
        retry_attempts=3
    )

    position_config = PositionManagerConfig(
        track_unrealized=True,
        calculate_metrics=True,
        update_frequency=2.0  # Update every 2 seconds
    )

    data_config = DataManagerConfig(
        max_bars_per_timeframe=2000,
        enable_tick_data=True,
        data_validation=True
    )

    suite = await TradingSuite.create(
        "MNQ",  # Positional argument
        timeframes=["1min", "5min"],
        features=["orderbook"],
        order_manager_config=order_config,
        position_manager_config=position_config,
        data_manager_config=data_config
    )

    await suite.disconnect()
```

### Configuration from File

Create a configuration file:

```yaml
# config/trading.yaml
instrument: "MNQ"
timeframes:
  - "1min"
  - "5min"
  - "15min"
features:
  - "orderbook"
  - "risk_manager"
initial_days: 7
timezone: "America/Chicago"

order_manager:
  max_concurrent_orders: 10
  default_timeout: 30.0

position_manager:
  track_unrealized: true
  calculate_metrics: true

data_manager:
  max_bars_per_timeframe: 1500
  enable_tick_data: true
```

Load from configuration:

```python
async def config_from_file():
    # Load configuration from YAML file
    suite = await TradingSuite.from_config("config/trading.yaml")

    # Or from dictionary
    config_dict = {
        "instrument": "MNQ",
        "timeframes": ["1min", "5min"],
        "features": ["orderbook"]
    }
    suite = await TradingSuite.from_dict(config_dict)

    await suite.disconnect()
```

## Core Components

### Client Access

```python
async def client_access():
    suite = await TradingSuite.create("MNQ")

    # Access the underlying ProjectX client
    client = suite.client

    # Get account information
    account = await client.get_account_info()
    print(f"Account Balance: ${account.balance:,.2f}")

    # Get historical data via client
    historical_bars = await client.get_bars("MNQ", days=30, interval=300)
    print(f"Historical bars: {len(historical_bars)}")

    await suite.disconnect()
```

### Order Management

#### Single Instrument Order Management

```python
async def order_management():
    suite = await TradingSuite.create(["MNQ"])
    mnq = suite["MNQ"]

    # Access the integrated order manager for MNQ
    orders = mnq.orders

    # Place different order types
    market_order = await orders.place_market_order(
        contract_id=mnq.instrument_id,
        side=0,  # Buy
        size=1
    )

    limit_order = await orders.place_limit_order(
        contract_id=mnq.instrument_id,
        side=0,  # Buy
        size=1,
        limit_price=21000.0
    )

    # Advanced bracket order
    bracket_order = await orders.place_bracket_order(
        contract_id=mnq.instrument_id,
        side=0,  # Buy
        size=1,
        entry_price=21050.0,
        stop_offset=25.0,   # $25 stop loss
        target_offset=50.0  # $50 profit target
    )

    print(f"MNQ Bracket order placed: {bracket_order.main_order_id}")

    await suite.disconnect()
```

#### Multi-Instrument Order Management

```python
async def multi_instrument_orders():
    suite = await TradingSuite.create(["MNQ", "ES", "MGC"])

    # Place orders across multiple instruments
    tasks = []

    # ES long position
    es_task = suite["ES"].orders.place_limit_order(
        contract_id=suite["ES"].instrument_id,
        side=0, size=1, limit_price=5100.0
    )
    tasks.append(es_task)

    # MNQ short position
    mnq_task = suite["MNQ"].orders.place_limit_order(
        contract_id=suite["MNQ"].instrument_id,
        side=1, size=1, limit_price=21100.0
    )
    tasks.append(mnq_task)

    # Execute all orders concurrently
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for i, result in enumerate(results):
        symbol = ["ES", "MNQ"][i]
        if isinstance(result, Exception):
            print(f"{symbol} order failed: {result}")
        else:
            print(f"{symbol} order placed: {result.order_id}")

    await suite.disconnect()
```

### Position Tracking

#### Single Instrument Position Tracking

```python
async def position_tracking():
    suite = await TradingSuite.create(["MNQ"])
    mnq = suite["MNQ"]

    # Access the integrated position manager for MNQ
    positions = mnq.positions

    # Get current position
    position = await positions.get_position("MNQ")
    if position:
        print(f"MNQ Position:")
        print(f"  Size: {position.size}")
        print(f"  Avg Price: ${position.avg_price:.2f}")
        print(f"  Unrealized P&L: ${position.unrealized_pnl:.2f}")

    await suite.disconnect()
```

#### Multi-Instrument Portfolio Tracking

```python
async def portfolio_tracking():
    suite = await TradingSuite.create(["MNQ", "ES", "MGC"])

    # Track positions across all instruments
    portfolio_value = 0
    total_pnl = 0

    print("Portfolio Positions:")
    for symbol, context in suite.items():
        position = await context.positions.get_position(symbol)
        if position:
            print(f"  {symbol}: {position.size} @ ${position.avg_price:.2f} (P&L: ${position.unrealized_pnl:.2f})")
            portfolio_value += abs(position.size * position.avg_price)
            total_pnl += position.unrealized_pnl
        else:
            print(f"  {symbol}: No position")

    print(f"\nPortfolio Summary:")
    print(f"  Total Value: ${portfolio_value:,.2f}")
    print(f"  Total P&L: ${total_pnl:.2f}")

    # Portfolio-level metrics
    portfolio_metrics = await suite.get_portfolio_metrics()
    print(f"  Diversification Score: {portfolio_metrics.get('diversification_score', 0):.2f}")
    print(f"  Risk Score: {portfolio_metrics.get('risk_score', 0):.2f}")

    await suite.disconnect()
```

### Real-time Data

#### Single Instrument Real-time Data

```python
async def realtime_data():
    suite = await TradingSuite.create(["MNQ"], timeframes=["1min", "5min"])
    mnq = suite["MNQ"]

    # Access the real-time data manager for MNQ
    data = mnq.data

    # Get current price
    current_price = await data.get_current_price()
    print(f"MNQ Current Price: ${current_price:.2f}")

    # Get latest bars
    latest_1min = await data.get_data("1min", count=10)  # Last 10 1-min bars
    latest_5min = await data.get_data("5min", count=5)   # Last 5 5-min bars

    print(f"MNQ Latest 1min bars: {len(latest_1min)}")
    print(f"MNQ Latest 5min bars: {len(latest_5min)}")

    await suite.disconnect()
```

#### Multi-Instrument Real-time Data

```python
async def multi_realtime_data():
    suite = await TradingSuite.create(
        instruments=["MNQ", "ES", "MGC"],
        timeframes=["1min", "5min"]
    )

    # Get current prices for all instruments
    print("Current Prices:")
    for symbol, context in suite.items():
        current_price = await context.data.get_current_price()
        print(f"  {symbol}: ${current_price:.2f}")

    # Get latest 5min bars for all instruments
    print("\nLatest 5min Data:")
    for symbol, context in suite.items():
        latest_5min = await context.data.get_data("5min", count=1)
        if len(latest_5min) > 0:
            latest_bar = latest_5min.tail(1)
            close_price = latest_bar["close"].item()
            volume = latest_bar["volume"].item()
            print(f"  {symbol}: Close ${close_price:.2f}, Volume {volume:,}")

    await suite.disconnect()
```

## Optional Features

### OrderBook (Level 2 Data)

```python
from project_x_py import Features

async def orderbook_feature():
    suite = await TradingSuite.create(
        "MNQ",
        features=[Features.ORDERBOOK]
    )

    # Access Level 2 order book
    if suite.orderbook:
        depth = await suite.orderbook.get_depth()
        trades = await suite.orderbook.get_recent_trades()

        print(f"Order Book:")
        print(f"  Best Bid: ${depth.best_bid:.2f}")
        print(f"  Best Ask: ${depth.best_ask:.2f}")
        print(f"  Spread: ${depth.spread:.2f}")
        print(f"  Recent Trades: {len(trades)}")

        # Get market microstructure data
        microstructure = await suite.orderbook.get_microstructure_analysis()
        print(f"  Order Flow Imbalance: {microstructure.order_flow_imbalance:.2f}")

    await suite.disconnect()
```

### Risk Manager

```python
async def risk_manager_feature():
    suite = await TradingSuite.create(
        "MNQ",
        features=[Features.RISK_MANAGER]
    )

    # Access risk management tools
    if suite.risk_manager:
        # Get risk limits
        limits = await suite.risk_manager.get_limits()
        print(f"Risk Limits:")
        print(f"  Max Position Size: {limits.max_position_size}")
        print(f"  Max Daily Loss: ${limits.max_daily_loss:.2f}")

        # Check if trade is allowed
        trade_allowed = await suite.risk_manager.check_trade_allowed(
            instrument="MNQ",
            side=0,  # Buy
            size=2
        )
        print(f"Trade allowed: {trade_allowed}")

        # Get current risk metrics
        risk_metrics = await suite.risk_manager.get_risk_metrics()
        print(f"Current Risk: ${risk_metrics.current_risk:.2f}")

    await suite.disconnect()
```

## Event Handling

### Setting Up Event Handlers

#### Single Instrument Event Handling

```python
from project_x_py import EventType

async def event_handling():
    suite = await TradingSuite.create(["MNQ"], timeframes=["1min"])
    mnq = suite["MNQ"]

    # Define event handlers for MNQ
    async def on_new_bar(event):
        print(f"MNQ New {event.timeframe} bar:")
        print(f"  Close: ${event.data.close:.2f}")
        print(f"  Volume: {event.data.volume:,}")

    async def on_order_filled(event):
        print(f"MNQ Order filled: {event.order_id}")
        print(f"  Price: ${event.fill_price:.2f}")
        print(f"  Quantity: {event.fill_quantity}")

    async def on_position_changed(event):
        position = event.data
        print(f"MNQ Position changed:")
        print(f"  New size: {position.size}")
        print(f"  Unrealized P&L: ${position.unrealized_pnl:.2f}")

    # Register event handlers for MNQ
    await mnq.on(EventType.NEW_BAR, on_new_bar)
    await mnq.on(EventType.ORDER_FILLED, on_order_filled)
    await mnq.on(EventType.POSITION_CHANGED, on_position_changed)

    # Keep the application running to receive events
    await asyncio.sleep(300)  # Run for 5 minutes

    await suite.disconnect()
```

#### Multi-Instrument Event Handling

```python
async def multi_instrument_events():
    suite = await TradingSuite.create(
        instruments=["MNQ", "ES", "MGC"],
        timeframes=["1min", "5min"]
    )

    # Set up event handlers for each instrument
    for symbol, context in suite.items():
        # Create symbol-specific handlers using closures
        def make_handlers(sym):
            async def on_new_bar(event):
                if event.timeframe == "5min":  # Only 5min bars
                    print(f"{sym} 5min bar: ${event.data.close:.2f}")

            async def on_order_filled(event):
                print(f"{sym} Order filled: {event.order_id} @ ${event.fill_price:.2f}")

            async def on_position_changed(event):
                position = event.data
                print(f"{sym} Position: {position.size} (P&L: ${position.unrealized_pnl:.2f})")

            return on_new_bar, on_order_filled, on_position_changed

        # Register handlers for this instrument
        bar_handler, order_handler, position_handler = make_handlers(symbol)
        await context.on(EventType.NEW_BAR, bar_handler)
        await context.on(EventType.ORDER_FILLED, order_handler)
        await context.on(EventType.POSITION_CHANGED, position_handler)

    print("Monitoring events for all instruments...")
    await asyncio.sleep(300)  # Run for 5 minutes
    await suite.disconnect()
```

### Multiple Event Handlers

```python
async def multiple_event_handlers():
    suite = await TradingSuite.create("MNQ", timeframes=["1min", "5min"])

    # Strategy event handler
    async def strategy_handler(event):
        if event.timeframe == "5min":
            # Implement 5-minute strategy logic
            pass

    # Risk management event handler
    async def risk_handler(event):
        # Check risk on every position change
        if hasattr(event, 'data') and hasattr(event.data, 'unrealized_pnl'):
            if event.data.unrealized_pnl < -500:  # $500 loss limit
                print("Risk limit exceeded!")

    # Logging event handler
    async def log_handler(event):
        print(f"Event: {event.event_type} at {event.timestamp}")

    # Register multiple handlers for the same event
    await suite.on(EventType.NEW_BAR, strategy_handler)
    await suite.on(EventType.NEW_BAR, log_handler)
    await suite.on(EventType.POSITION_CHANGED, risk_handler)

    await asyncio.sleep(300)
    await suite.disconnect()
```

## Connection Management

### Context Manager (Recommended)

```python
async def context_manager_usage():
    # Recommended: Use context manager for automatic cleanup
    async with TradingSuite.create("MNQ") as suite:
        # Suite is automatically connected on entry

        current_price = await suite.data.get_current_price()
        print(f"Current Price: ${current_price:.2f}")

        # Place a trade
        order = await suite.orders.place_market_order(
            contract_id=suite.instrument_id,
            side=0,  # Buy
            size=1
        )

        # Suite automatically disconnects on exit
```

### Manual Connection Management

```python
async def manual_connection_management():
    suite = None
    try:
        # Create and connect manually
        suite = await TradingSuite.create("MNQ")

        # Check connection status
        client_connected = await suite.client.is_connected()
        realtime_connected = await suite.realtime.is_connected()

        print(f"Client connected: {client_connected}")
        print(f"Real-time connected: {realtime_connected}")

        # Your trading logic here

    finally:
        if suite:
            await suite.disconnect()
```

### Reconnection Handling

```python
async def reconnection_handling():
    suite = await TradingSuite.create("MNQ", features=["auto_reconnect"])

    # Monitor connection status
    async def on_connection_status(event):
        if event.status == "disconnected":
            print("Connection lost - attempting reconnection...")
        elif event.status == "reconnected":
            print("Connection restored")

    await suite.on(EventType.CONNECTION_STATUS_CHANGED, on_connection_status)

    # Manual reconnection if needed
    if not await suite.client.is_connected():
        await suite.client.reconnect()

    if not await suite.realtime.is_connected():
        await suite.realtime.reconnect()

    await suite.disconnect()
```

## Statistics and Monitoring

### Health Monitoring

```python
async def health_monitoring():
    suite = await TradingSuite.create("MNQ", features=["orderbook"])

    # Get overall health score using HealthMonitor
    from project_x_py.statistics.health import HealthMonitor

    stats = await suite.get_stats()
    monitor = HealthMonitor()
    health_score = await monitor.calculate_health(stats)
    print(f"System Health: {health_score:.1f}/100")

    if health_score < 70:
        # Get detailed health breakdown
        breakdown = await monitor.get_health_breakdown(stats)

        for category, score in breakdown.items():
            if category not in ['overall_score', 'weighted_total'] and score < 70:
                print(f"  {category}: {score:.1f}/100")

    await suite.disconnect()
```

### Performance Statistics

```python
async def performance_statistics():
    suite = await TradingSuite.create("MNQ")

    # Get comprehensive statistics
    stats = await suite.get_stats()

    print(f"TradingSuite Statistics:")
    print(f"  Total Operations: {stats.get('total_operations', 0):,}")
    print(f"  Total Errors: {stats.get('total_errors', 0)}")
    print(f"  Memory Usage: {stats.get('memory_usage_mb', 0):.1f} MB")
    print(f"  Component Count: {stats.get('components', 0)}")

    # Component-specific statistics from MNQ context
    mnq = suite["MNQ"]
    order_stats = await mnq.orders.get_stats()
    print(f"\nOrder Manager:")
    print(f"  Orders Placed: {order_stats.get('orders_placed', 0)}")
    print(f"  Orders Filled: {order_stats.get('orders_filled', 0)}")
    print(f"  Error Count: {order_stats.get('error_count', 0)}")

    position_stats = await mnq.positions.get_stats()
    print(f"\nPosition Manager:")
    print(f"  Positions Opened: {position_stats.get('positions_opened', 0)}")
    print(f"  Positions Closed: {position_stats.get('positions_closed', 0)}")

    await suite.disconnect()
```

### Statistics Export

```python
async def statistics_export():
    from project_x_py.statistics.export import StatsExporter
    import json

    suite = await TradingSuite.create("MNQ", features=["orderbook"])

    # Get statistics and export in different formats
    stats = await suite.get_stats()
    exporter = StatsExporter()

    # Prometheus format (for monitoring systems)
    prometheus_metrics = await exporter.to_prometheus(stats)
    with open("metrics.prom", "w") as f:
        f.write(prometheus_metrics)

    # CSV format (for analysis)
    csv_data = await exporter.to_csv(stats, include_timestamp=True)
    with open("trading_stats.csv", "w") as f:
        f.write(csv_data)

    # JSON format (for applications)
    json_data = json.dumps(stats, indent=2)
    with open("trading_stats.json", "w") as f:
        f.write(json_data)

    await suite.disconnect()
```

## Complete Trading Example

Here's a complete example that demonstrates most TradingSuite features:

```python
import asyncio
from project_x_py import TradingSuite, EventType
from project_x_py.indicators import RSI, SMA
from datetime import datetime

async def complete_trading_example():
    """Complete trading application using TradingSuite."""

    # Setup with multiple features
    suite = await TradingSuite.create(
        "MNQ",  # Positional argument
        timeframes=["1min", "5min"],
        features=["orderbook", "risk_manager"],
        initial_days=5
    )

    print(f"Connected to {suite.instrument_info.description}")
    print(f"Instrument ID: {suite.instrument_id}")

    # Event handlers
    async def on_new_bar(event):
        """Handle new bar data for strategy logic."""
        if event.timeframe == "5min":
            # Get recent data
            bars = await suite.data.get_data("5min", count=50)

            # Apply technical indicators
            data_with_indicators = bars.pipe(RSI, period=14).pipe(SMA, period=20)

            if len(data_with_indicators) > 20:
                latest = data_with_indicators.tail(1)
                rsi_value = latest["rsi_14"].item()
                sma_value = latest["sma_20"].item()
                close_price = latest["close"].item()

                print(f"5min Bar - Close: ${close_price:.2f}, RSI: {rsi_value:.1f}, SMA: ${sma_value:.2f}")

                # Simple RSI strategy
                current_position = await suite.positions.get_position("MNQ")
                current_size = current_position.size if current_position else 0

                # Entry signals
                if rsi_value < 30 and close_price < sma_value and current_size == 0:
                    print("= RSI Oversold + Below SMA - Going Long")
                    await suite.orders.place_bracket_order(
                        contract_id=suite.instrument_id,
                        side=0,  # Buy
                        size=1,
                        entry_price=None,  # Market order
                        stop_offset=25.0,
                        target_offset=50.0
                    )

                elif rsi_value > 70 and close_price > sma_value and current_size == 0:
                    print("=4 RSI Overbought + Above SMA - Going Short")
                    await suite.orders.place_bracket_order(
                        contract_id=suite.instrument_id,
                        side=1,  # Sell
                        size=1,
                        entry_price=None,  # Market order
                        stop_offset=25.0,
                        target_offset=50.0
                    )

    async def on_order_filled(event):
        """Handle order fills."""
        print(f"Order {event.order_id} filled at ${event.fill_price:.2f}")

    async def on_position_changed(event):
        """Handle position changes."""
        position = event.data
        print(f"= Position Update: {position.size} @ ${position.avg_price:.2f}, P&L: ${position.unrealized_pnl:.2f}")

    # Register event handlers
    await suite.on(EventType.NEW_BAR, on_new_bar)
    await suite.on(EventType.ORDER_FILLED, on_order_filled)
    await suite.on(EventType.POSITION_CHANGED, on_position_changed)

    # Monitor for 10 minutes
    print("= Starting trading strategy...")
    start_time = datetime.now()

    try:
        while True:
            await asyncio.sleep(30)  # Check every 30 seconds

            # Print status update
            from project_x_py.statistics.health import HealthMonitor

            current_price = await suite.data.get_current_price()
            stats = await suite.get_stats()
            monitor = HealthMonitor()
            health_score = await monitor.calculate_health(stats)

            print(f"= MNQ: ${current_price:.2f} | Health: {health_score:.0f}/100")

            # Run for 10 minutes
            if (datetime.now() - start_time).total_seconds() > 600:
                break

    except KeyboardInterrupt:
        print("= Trading interrupted by user")

    finally:
        # Final status report
        print("\n= Final Report:")

        # Get final statistics
        stats = await suite.get_stats()
        print(f"  Total Operations: {stats.get('total_operations', 0):,}")
        print(f"  Total Errors: {stats.get('total_errors', 0)}")

        # Get final position
        position = await suite.positions.get_position("MNQ")
        if position:
            print(f"  Final Position: {position.size} contracts")
            print(f"  Unrealized P&L: ${position.unrealized_pnl:.2f}")
        else:
            print("  No open position")

        # Cleanup
        await suite.disconnect()
        print("= Disconnected successfully")

# Run the example
if __name__ == "__main__":
    asyncio.run(complete_trading_example())
```

## Best Practices

### Initialization

```python
#  Recommended: Use TradingSuite.create()
suite = await TradingSuite.create("MNQ", features=["orderbook"])

#  Good: Use context manager for automatic cleanup
async with TradingSuite.create("MNQ") as suite:
    # Trading operations

# L Not recommended: Manual component initialization
# client = ProjectX.from_env()
# orders = OrderManager(client)  # Too complex, error-prone
```

### Resource Management

```python
#  Good: Monitor resource usage
stats = await suite.get_stats()
if stats.get('memory_usage_mb', 0) > 100:  # 100MB threshold
    print("High memory usage - consider cleanup")

# Good: Use appropriate features
features = ["orderbook"]  # Only what you need
suite = await TradingSuite.create("MNQ", features=features)
```

### Error Handling

```python
# Good: Handle connection errors
try:
    suite = await TradingSuite.create("MNQ")
except ProjectXConnectionError:
    print("Failed to connect - check network and credentials")
except Exception as e:
    print(f"Unexpected error: {e}")

# Good: Check component availability
if suite.orderbook:
    depth = await suite.orderbook.get_depth()
else:
    print("OrderBook not enabled")
```

### Performance

```python
# Good: Use appropriate timeframes
await TradingSuite.create("MNQ", timeframes=["5min", "15min"])  # What you need

# L Wasteful: Too many timeframes
# await TradingSuite.create("MNQ", timeframes=["15sec", "30sec", "1min", "2min", "5min"])

# Good: Batch operations when possible
positions = await suite.positions.get_all_positions()  # Single call
# vs multiple individual calls
```

## Next Steps

- Learn about [Order Management](orders.md) for detailed order handling
- Explore [Position Tracking](positions.md) for portfolio management
- Set up [Real-time Data](realtime.md) for market data streaming
- Use [Technical Indicators](indicators.md) for market analysis
- Implement [Risk Management](risk.md) for capital protection

The TradingSuite provides a solid foundation for building sophisticated trading applications. Start with the basic setup and gradually add features as your needs grow.
