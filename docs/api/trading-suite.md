# Trading Suite API

Unified trading interface combining all managers into a single, easy-to-use entry point for complete trading operations.

## Overview

The TradingSuite is the primary interface for trading operations, combining all managers into a unified interface. It provides automatic component initialization, dependency injection, and configuration management.

::: project_x_py.trading_suite.TradingSuite

## Quick Start

### Basic Setup

```python
from project_x_py import TradingSuite

async def main():
    # Simple one-liner with defaults
    suite = await TradingSuite.create(["MNQ"])

    # Everything is ready - client authenticated, realtime connected
    await suite.disconnect()

asyncio.run(main())
```

### Advanced Configuration

```python
async def advanced_setup():
    # Single instrument (backward compatible, but list is recommended)
    suite_single = await TradingSuite.create(
        ["MNQ"],  # List notation is preferred
        timeframes=["1min", "5min", "15min"],
        features=["orderbook", "risk_manager"],
        initial_days=10,
        timezone="America/Chicago"
    )

    # Multi-instrument (recommended for v3.5.0+)
    suite_multi = await TradingSuite.create(
        ["MNQ", "MES", "MCL"],  # List of instruments
        timeframes=["1min", "5min", "15min"],
        features=["orderbook", "risk_manager"],
        initial_days=10,
        timezone="America/Chicago"
    )

    # Access components (single instrument)
    if len(suite_single) == 1:
        # New recommended access
        mnq_context = suite_single["MNQ"]
        print(f"Data: {mnq_context.data}")
        print(f"Orders: {mnq_context.orders}")

    # Access components (multi-instrument - recommended)
    for symbol, context in suite_multi.items():
        print(f"{symbol} Data: {context.data}")
        print(f"{symbol} Orders: {context.orders}")
        print(f"{symbol} Positions: {context.positions}")
        if context.orderbook:  # if enabled
            print(f"{symbol} OrderBook: {context.orderbook}")
        if context.risk_manager:  # if enabled
            print(f"{symbol} RiskManager: {context.risk_manager}")

    await suite_single.disconnect()
    await suite_multi.disconnect()
```

### Session Configuration (v3.4.0+)

!!! warning "Experimental Feature"
    Session filtering is experimental and not thoroughly tested with live data. Use with caution in production.

```python
from project_x_py.sessions import SessionConfig, SessionType, SessionTimes

async def session_setup():
    # RTH-only trading (9:30 AM - 4:00 PM ET)
    rth_suite = await TradingSuite.create(
        instruments=["MNQ"],
        timeframes=["1min", "5min"],
        session_config=SessionConfig(session_type=SessionType.RTH)
    )

    # ETH-only analysis (overnight sessions)
    eth_suite = await TradingSuite.create(
        instruments=["ES"],
        session_config=SessionConfig(session_type=SessionType.ETH)
    )

    # Custom session times
    from datetime import time

    custom_config = SessionConfig(
        session_type=SessionType.RTH,
        session_times=SessionTimes(
            rth_start=time(9, 0),
            rth_end=time(15, 30),
            eth_start=time(18, 0),
            eth_end=time(17, 0)
        )
    )

    custom_suite = await TradingSuite.create(
        instruments=["CL"],
        session_config=custom_config
    )

    await rth_suite.disconnect()
    await eth_suite.disconnect()
    await custom_suite.disconnect()
```

### Configuration File Setup

```python
async def config_file_setup():
    # From configuration file
    suite = await TradingSuite.from_config("config/trading.yaml")

    # Or from dictionary
    config = {
        "instruments": ["MNQ"],
        "timeframes": ["1min", "5min"],
        "features": ["orderbook"],
        "initial_days": 5
    }
    suite = await TradingSuite.from_config("suite.json")

    await suite.disconnect()
```

## Multi-Instrument Support (v3.5.0+)

### Creating Multi-Instrument Suites

```python
async def multi_instrument_setup():
    # Create suite with multiple instruments
    suite = await TradingSuite.create(
        ["MNQ", "MES", "MCL"],  # List of instruments
        timeframes=["1min", "5min"],
        features=["orderbook", "risk_manager"]
    )

    # Suite acts as a dictionary
    print(f"Managing {len(suite)} instruments")
    print(f"Instruments: {list(suite.keys())}")

    # Access each instrument context
    for symbol in suite:
        context = suite[symbol]
        print(f"{symbol}: {context.instrument_info.name}")

    await suite.disconnect()
```

### Container Protocol Methods

```python
async def container_protocol_demo():
    suite = await TradingSuite.create(["MNQ", "MES", "MCL"])

    # Dictionary-like operations
    assert len(suite) == 3                    # Number of instruments
    assert "MNQ" in suite                      # Membership test
    assert list(suite) == ["MNQ", "MES", "MCL"]  # Iteration

    # Access methods
    symbols = list(suite.keys())              # Get all symbols
    contexts = list(suite.values())           # Get all contexts
    items = list(suite.items())               # Get (symbol, context) pairs

    # Direct access
    mnq = suite["MNQ"]                        # Get specific context

    try:
        unknown = suite["UNKNOWN"]            # Raises KeyError
    except KeyError as e:
        print(f"Instrument not found: {e}")

    await suite.disconnect()
```

### Multi-Instrument Trading

```python
async def multi_instrument_trading():
    suite = await TradingSuite.create(
        ["MNQ", "MES", "MCL"],
        features=["orderbook", "risk_manager"]
    )

    # Place orders on multiple instruments
    for symbol, context in suite.items():
        # Each instrument has its own managers
        order = await context.orders.place_market_order(
            contract_id=context.instrument_info.id,
            side=0,  # Buy
            size=1
        )
        print(f"{symbol} order placed: {order.order_id}")

    # Monitor positions across all instruments
    total_exposure = 0
    for symbol, context in suite.items():
        positions = await context.positions.get_all_positions()
        for pos in positions:
            exposure = abs(pos.size * pos.averagePrice)
            total_exposure += exposure
            print(f"{symbol} position: {pos.size} @ ${pos.averagePrice}")

    print(f"Total portfolio exposure: ${total_exposure:,.2f}")

    await suite.disconnect()
```

### Session Management with Multi-Instruments

```python
from project_x_py.sessions import SessionType

async def multi_instrument_sessions():
    suite = await TradingSuite.create(["MNQ", "MES"])

    # Set session type for all instruments
    await suite.set_session_type(SessionType.RTH)

    # Get session data for all instruments (returns dict)
    session_data = await suite.get_session_data("5min", SessionType.RTH)
    # Returns: {"MNQ": DataFrame, "MES": DataFrame}

    for symbol, data in session_data.items():
        if data is not None and not data.is_empty():
            print(f"{symbol} RTH bars: {len(data)}")

    # Get session statistics for all instruments
    session_stats = await suite.get_session_statistics("5min")
    # Returns: {"MNQ": stats_dict, "MES": stats_dict} for multi-instrument
    # or just stats_dict for single instrument

    await suite.disconnect()
```

## Features

### Available Features

::: project_x_py.trading_suite.Features

### Feature Configuration

```python
from project_x_py import Features

# Enable specific features
features = [
    Features.ORDERBOOK,        # Level 2 market depth
    Features.RISK_MANAGER,     # Risk management and position sizing
    Features.AUTO_RECONNECT,   # Automatic reconnection (future)
]

suite = await TradingSuite.create(
    ["MNQ"],
    features=features
)
```

## Configuration

### TradingSuiteConfig

::: project_x_py.trading_suite.TradingSuiteConfig

### Component Configuration

```python
from project_x_py.types import (
    OrderManagerConfig,
    PositionManagerConfig,
    DataManagerConfig,
    OrderbookConfig
)
from project_x_py.risk_manager import RiskConfig
from project_x_py.sessions import SessionConfig, SessionType

async def custom_configuration():
    # Custom component configurations
    order_config = OrderManagerConfig(
        max_concurrent_orders=10,
        default_timeout=30.0,
        retry_attempts=3
    )

    position_config = PositionManagerConfig(
        track_unrealized=True,
        calculate_metrics=True,
        update_frequency=1.0
    )

    risk_config = RiskConfig(
        max_position_size=5,
        max_daily_loss=1000.0,
        max_drawdown_percent=10.0
    )

    # Session configuration (v3.4.0+)
    session_config = SessionConfig(
        session_type=SessionType.RTH
    )

    suite = await TradingSuite.create(
        ["MNQ"],
        order_manager_config=order_config,
        position_manager_config=position_config,
        risk_config=risk_config,
        session_config=session_config  # New in v3.4.0
    )

    await suite.disconnect()
```

## Component Access

### Core Components

```python
async def component_access():
    suite = await TradingSuite.create(["MNQ"], features=["orderbook", "risk_manager"])

    # Global components (always available)
    client = suite.client              # ProjectX API client
    realtime = suite.realtime         # ProjectXRealtimeClient

    # Single instrument access (new recommended way)
    mnq_context = suite["MNQ"]
    orders = mnq_context.orders          # OrderManager for MNQ
    positions = mnq_context.positions    # PositionManager for MNQ
    data = mnq_context.data              # RealtimeDataManager for MNQ

    # Optional components (per instrument)
    if mnq_context.orderbook:
        orderbook = mnq_context.orderbook   # OrderBook for MNQ
    if mnq_context.risk_manager:
        risk_mgr = mnq_context.risk_manager # RiskManager for MNQ

    # Instrument information
    instrument_info = mnq_context.instrument_info
    instrument_id = mnq_context.instrument_info.id

    await suite.disconnect()
```

## Trading Operations

### Order Management

```python
async def order_operations():
    suite = await TradingSuite.create(["MNQ"])
    mnq_context = suite["MNQ"]

    # Place market order
    market_order = await mnq_context.orders.place_market_order(
        contract_id=mnq_context.instrument_info.id,
        side=0,  # Buy
        size=1
    )

    # Place limit order
    limit_order = await mnq_context.orders.place_limit_order(
        contract_id=mnq_context.instrument_info.id,
        side=0,  # Buy
        size=1,
        limit_price=21050.0
    )

    # Place bracket order
    bracket_result = await mnq_context.orders.place_bracket_order(
        contract_id=mnq_context.instrument_info.id,
        side=0,  # Buy
        size=1,
        entry_price=21050.0,
        stop_offset=25.0,
        target_offset=50.0
    )

    await suite.disconnect()
```

### Position Management

```python
async def position_operations():
    suite = await TradingSuite.create(["MNQ"])
    mnq_positions = suite["MNQ"].positions

    # Get current position
    position = await mnq_positions.get_position("MNQ")
    if position:
        print(f"Size: {position.size}")
        print(f"Avg Price: {position.avg_price}")
        print(f"Unrealized PnL: {position.unrealized_pnl}")

    # Get all positions
    positions = await suite["MNQ"].positions.get_all_positions()

    # Get position metrics
    metrics = await mnq_positions.get_metrics()
    print(f"Total PnL: {metrics.get('total_pnl', 0)}")
    print(f"Win Rate: {metrics.get('win_rate', 0):.1%}")

    await suite.disconnect()
```

### Market Data Access

```python
async def data_access():
    suite = await TradingSuite.create(["MNQ"], timeframes=["1min", "5min"], features=["orderbook"])
    mnq_context = suite["MNQ"]

    # Get historical data via client
    historical = await suite.client.get_bars("MNQ", days=5, interval=60)

    # Get real-time data
    current_price = await mnq_context.data.get_current_price()
    latest_bars_1min = await mnq_context.data.get_data("1min")
    latest_bars_5min = await mnq_context.data.get_data("5min")

    # OrderBook data (if enabled)
    if mnq_context.orderbook:
        depth = await mnq_context.orderbook.get_depth()
        trades = await mnq_context.orderbook.get_recent_trades()

    await suite.disconnect()
```

### Session-Aware Data Access (v3.4.0+)

```python
from project_x_py.sessions import SessionType, SessionConfig

async def session_data_access():
    # Create suite with session configuration
    suite = await TradingSuite.create(
        ["MNQ"],
        timeframes=["1min", "5min"],
        session_config=SessionConfig(session_type=SessionType.RTH)
    )
    mnq_context = suite["MNQ"]

    # Get session-specific data using data manager methods
    rth_data = await mnq_context.data.get_session_data("5min", SessionType.RTH)
    eth_data = await mnq_context.data.get_session_data("5min", SessionType.ETH)

    # Get session statistics from data manager
    session_stats = await mnq_context.data.get_session_statistics("5min")

    if session_stats:
        print(f"RTH Volume: {session_stats.get('rth_volume', 0):,}")
        print(f"ETH Volume: {session_stats.get('eth_volume', 0):,}")
        print(f"RTH VWAP: ${session_stats.get('rth_vwap', 0):.2f}")
        print(f"ETH VWAP: ${session_stats.get('eth_vwap', 0):.2f}")
        print(f"RTH Range: ${session_stats.get('rth_range', 0):.2f}")
        print(f"ETH Range: ${session_stats.get('eth_range', 0):.2f}")

    await suite.disconnect()
```

## Event Handling

### Real-time Events

```python
from project_x_py import EventType

async def event_handling():
    suite = await TradingSuite.create(["MNQ"], timeframes=["1min"])
    mnq_context = suite["MNQ"]

    # Register event handlers
    async def on_new_bar(event):
        print(f"New {event.timeframe} bar: {event.data}")

    async def on_order_filled(event):
        print(f"Order filled: {event.order_id}")

    async def on_position_changed(event):
        print(f"Position changed: {event.data}")

    # Register handlers
    await mnq_context.on(EventType.NEW_BAR, on_new_bar)
    await mnq_context.on(EventType.ORDER_FILLED, on_order_filled)
    await mnq_context.on(EventType.POSITION_CHANGED, on_position_changed)

    # Keep running to receive events
    await asyncio.sleep(60)
    await suite.disconnect()
```

## Statistics & Health Monitoring

### Comprehensive Statistics

```python
async def statistics_monitoring():
    suite = await TradingSuite.create(["MNQ"], features=["orderbook", "risk_manager"])
    mnq_context = suite["MNQ"]

    # Get system statistics (async-first API)
    stats = await suite.get_stats()
    print(f"System Health: {stats['health_score']:.1f}/100")
    print(f"API Success Rate: {stats['api_success_rate']:.1%}")
    print(f"Memory Usage: {stats['memory_usage_mb']:.1f} MB")

    # Component-specific statistics
    order_stats = await mnq_context.orders.get_stats()
    position_stats = await mnq_context.positions.get_stats()
    data_stats = await mnq_context.data.get_stats()

    if mnq_context.orderbook:
        orderbook_stats = await mnq_context.orderbook.get_stats()

    # Export statistics
    prometheus_metrics = await suite.export_stats("prometheus")
    csv_data = await suite.export_stats("csv")

    await suite.disconnect()
```

### Health Monitoring

```python
async def health_monitoring():
    suite = await TradingSuite.create(["MNQ"])

    # Real-time health monitoring
    health_score = await suite.get_health_score()
    if health_score < 70:
        print(f" System health degraded: {health_score:.1f}/100")

        # Get component health breakdown
        component_health = await suite.get_component_health()
        for name, health in component_health.items():
            if health['error_count'] > 0:
                print(f"  {name}: {health['error_count']} errors")

    await suite.disconnect()
```

## Risk Management

### ManagedTrade Integration

```python
from project_x_py.risk_manager import ManagedTrade
from project_x_py import Features

async def risk_managed_trading():
    suite = await TradingSuite.create(["MNQ"], features=[Features.RISK_MANAGER])
    mnq_context = suite["MNQ"]

    # Create a managed trade with risk controls
    managed_trade = ManagedTrade(
        risk_manager=mnq_context.risk_manager,
        order_manager=mnq_context.orders,
        position_manager=mnq_context.positions,
        instrument_id=mnq_context.instrument_info.id,
        data_manager=mnq_context.data # Pass data_manager for ATR calculations etc.
    )

    # Execute the trade with automatic risk management
    result = await managed_trade.execute_trade(
        side=0,  # Buy
        entry_signal="RSI oversold + support level",
        stop_loss_type="atr",      # ATR-based stop
        take_profit_type="fixed"   # Fixed target
    )

    if result.success:
        print(f"Trade executed: {result.main_order_id}")
        print(f"Stop Loss: {result.stop_order_id}")
        print(f"Take Profit: {result.target_order_id}")

    await suite.disconnect()
```

## Order Tracking & Lifecycle

### Order Chain Management

```python
async def order_lifecycle():
    suite = await TradingSuite.create(["MNQ"])
    mnq_context = suite["MNQ"]

    # Track order lifecycle
    tracker = mnq_context.track_order()

    # Create order chain
    chain = mnq_context.order_chain()

    # Build complex order sequence
    entry_order = await chain.add_market_order(
        contract_id=mnq_context.instrument_info.id,
        side=0,
        size=1
    )

    # Add conditional orders
    await chain.add_stop_order(
        contract_id=mnq_context.instrument_info.id,
        side=1,  # Sell to close
        size=1,
        stop_price=21000.0,
        condition=f"when {entry_order.id} filled"
    )

    # Execute the chain
    await chain.execute()

    await suite.disconnect()
```

## Connection Management

### Lifecycle Management

### Context Manager (Recommended)

```python
async def context_manager_usage():
    # Recommended: Use context manager for automatic cleanup
    async with TradingSuite.create(["MNQ"]) as suite:
        mnq_context = suite["MNQ"]
        # Suite is automatically connected on entry

        current_price = await mnq_context.data.get_current_price()
        print(f"Current Price: ${current_price:.2f}")

        # Place a trade
        order = await mnq_context.orders.place_market_order(
            contract_id=mnq_context.instrument_info.id,
            side=0,  # Buy
            size=1
        )

        # Suite automatically disconnects on exit
```

### Reconnection Handling

```python
async def reconnection_handling():
    suite = await TradingSuite.create(["MNQ"], features=["auto_reconnect"])

    # Check connection status
    client_connected = await suite.client.is_connected()
    realtime_connected = await suite.realtime.is_connected()

    if not client_connected:
        await suite.client.reconnect()

    if not realtime_connected:
        await suite.realtime.reconnect()

    await suite.disconnect()
```

## Configuration Examples

### YAML Configuration

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
  retry_attempts: 3

position_manager:
  track_unrealized: true
  calculate_metrics: true
  update_frequency: 1.0

risk_config:
  max_position_size: 5
  max_daily_loss: 1000.0
  max_drawdown_percent: 10.0

orderbook:
  max_depth_levels: 10
  enable_order_flow: true
  track_volume_profile: true
```

### JSON Configuration

```json
{
  "instrument": "MNQ",
  "timeframes": ["1min", "5min"],
  "features": ["orderbook", "risk_manager"],
  "initial_days": 5,
  "order_manager": {
    "max_concurrent_orders": 5,
    "default_timeout": 30.0
  },
  "risk_config": {
    "max_position_size": 3,
    "max_daily_loss": 500.0
  }
}
```

## Best Practices

### Initialization

```python
# Recommended: Use TradingSuite.create()
suite = await TradingSuite.create(["MNQ"], features=["orderbook"])

# Good: Use context manager for automatic cleanup
async with TradingSuite.create(["MNQ"]) as suite:
    # Trading operations
    pass

# L Not recommended: Manual component initialization
# client = ProjectX.from_env()
# orders = OrderManager(client)  # Too complex
```

### Error Handling

### Error Handling

```python
from project_x_py.exceptions import ProjectXError

async def robust_trading():
    try:
        suite = await TradingSuite.create(["MNQ"])
        mnq_context = suite["MNQ"]

        # Trading operations with error handling
        try:
            order = await mnq_context.orders.place_market_order(
                contract_id=mnq_context.instrument_info.id,
                side=0,
                size=1
            )
        except ProjectXError as e:
            print(f"Order failed: {e}")

    except Exception as e:
        print(f"Suite creation failed: {e}")
    finally:
        if 'suite' in locals():
            await suite.disconnect()
```

### Resource Management

```python
async def resource_management():
    # Monitor resource usage
    suite = await TradingSuite.create(["MNQ"], features=["orderbook"])

    # Periodic health checks
    while True:
        stats = await suite.get_stats()
        memory_mb = stats.get('memory_usage_mb', 0)

        if memory_mb > 100:  # MB threshold
            print(f"High memory usage: {memory_mb:.1f} MB")

        await asyncio.sleep(60)  # Check every minute
```

## See Also

- [Order Manager API](order-manager.md) - Detailed order management
- [Position Manager API](position-manager.md) - Position tracking
- [Statistics API](statistics.md) - Health monitoring and analytics
- [Client API](client.md) - Core client functionality
- [Risk Management Guide](../guide/risk.md) - Risk management concepts
