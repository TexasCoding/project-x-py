# ProjectX Python SDK

[![Python Version](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Performance](https://img.shields.io/badge/performance-optimized-brightgreen.svg)](#performance-optimizations)
[![Async](https://img.shields.io/badge/async-native-brightgreen.svg)](#async-architecture)

A **high-performance async Python SDK** for the [ProjectX Trading Platform](https://www.projectx.com/) Gateway API. This library enables developers to build sophisticated trading strategies and applications by providing comprehensive async access to futures trading operations, historical market data, real-time streaming, technical analysis, and advanced market microstructure tools with enterprise-grade performance optimizations.

> **Note**: This is a **client library/SDK**, not a trading strategy. It provides the tools and infrastructure to help developers create their own trading strategies that integrate with the ProjectX platform.

## 🎯 What is ProjectX?

[ProjectX](https://www.projectx.com/) is a cutting-edge web-based futures trading platform that provides:
- **TradingView Charts**: Advanced charting with hundreds of indicators
- **Risk Controls**: Auto-liquidation, profit targets, daily loss limits
- **Unfiltered Market Data**: Real-time depth of market data with millisecond updates
- **REST API**: Comprehensive API for custom integrations
- **Mobile & Web Trading**: Native browser-based trading platform

This Python SDK acts as a bridge between your trading strategies and the ProjectX platform, handling all the complex API interactions, data processing, and real-time connectivity.

## 🚀 v3.5.3 - Complete Documentation & Testing Improvements

**Latest Version**: v3.5.3 - Comprehensive documentation updates, complete test coverage for realtime_data_manager module, and modernized all code examples. Fixed type safety issues and achieved 100% test passing rate across the SDK.

**Key Benefits**:
- 🎯 **Multi-Asset Strategies**: Trade ES vs NQ pairs, commodity spreads, sector rotation
- 📊 **Portfolio Management**: Unified risk management across multiple instruments
- 🔄 **Parallel Processing**: Efficient concurrent data processing and order management
- 🛡️ **Backward Compatible**: Existing single-instrument code continues to work
- ⚡ **Performance Optimized**: Parallel context creation and resource sharing

See [CHANGELOG.md](CHANGELOG.md) for complete v3.5.3 bug fixes, testing improvements, and documentation updates.

### 📦 Production Stability Guarantee

Since v3.1.1, this project maintains:
- ✅ Backward compatibility between minor versions
- ✅ Deprecation warnings for at least 2 minor versions before removal
- ✅ Breaking changes only in major releases (4.0.0+)
- ✅ Strict semantic versioning (MAJOR.MINOR.PATCH)

### Key Features

- **TradingSuite Class**: Unified entry point for simplified SDK usage
- **One-line Initialization**: `TradingSuite.create()` handles all setup
- **Feature Flags**: Easy enabling of optional components
- **Context Manager Support**: Automatic cleanup with `async with` statements
- **Unified Event Handling**: Built-in EventBus for all components
- **Performance Optimized**: Connection pooling, caching, and WebSocket batching
- **Memory Management**: Automatic overflow to disk with transparent access

### Why Async?

- **Concurrent Operations**: Execute multiple API calls simultaneously
- **Non-blocking I/O**: Handle real-time data feeds without blocking
- **Better Resource Usage**: Single thread handles thousands of concurrent operations
- **WebSocket Native**: Perfect for real-time trading applications
- **Modern Python**: Leverages Python 3.12+ async features

### Migration to v3.0+

If you're upgrading from v2.x, key changes include TradingSuite replacing factories:

```python
# Old (v2.x)
suite = await create_initialized_trading_suite(\"MNQ\", client)

# New (v3.0+)
suite = await TradingSuite.create(\"MNQ\")
```

## ✨ Key Features

### Core Trading Operations (All Async)
- **Authentication & Account Management**: Multi-account support with async session management
- **Order Management**: Place, modify, cancel orders with real-time async updates
- **Position Tracking**: Real-time position monitoring with P&L calculations
- **Market Data**: Historical and real-time data with async streaming
- **Risk Management**: Portfolio analytics and risk metrics

### Advanced Features
- **59+ Technical Indicators**: Full TA-Lib compatibility with Polars optimization including new pattern indicators
- **Level 2 OrderBook**: Depth analysis, iceberg detection, spoofing detection with 6 pattern types
- **Real-time WebSockets**: Async streaming for quotes, trades, and account updates
- **Performance Optimized**: Connection pooling, intelligent caching, memory management
- **Pattern Recognition**: Fair Value Gaps, Order Blocks, Waddah Attar Explosion, and Lorenz Formula indicators
- **Market Manipulation Detection**: Advanced spoofing detection with confidence scoring
- **Financial Precision**: All calculations use Decimal type for exact precision
- **Enterprise Error Handling**: Production-ready error handling with decorators and structured logging
- **Comprehensive Type Safety**: Full TypedDict and Protocol definitions for IDE support and static analysis
- **Advanced Statistics & Analytics**: 100% async-first statistics system with comprehensive health monitoring and performance tracking
- **Multi-format Export**: Statistics export in JSON, Prometheus, CSV, and Datadog formats with data sanitization
- **Component-Specific Tracking**: Enhanced statistics for OrderManager, PositionManager, OrderBook, and more
- **Health Monitoring**: Intelligent 0-100 health scoring with configurable thresholds and degradation detection
- **Performance Optimization**: TTL caching, parallel collection, and circular buffers for memory efficiency
- **Comprehensive Testing**: 1,300+ tests with complete code quality compliance and extensive TDD methodology

## 📦 Installation

### Using UV (Recommended)
```bash
uv add project-x-py
```

### Using pip
```bash
pip install project-x-py
```

### Development Installation
```bash
git clone https://github.com/yourusername/project-x-py.git
cd project-x-py
uv sync  # or: pip install -e ".[dev]"
```

## 🚀 Quick Start

### Basic Usage

```python
import asyncio
from project_x_py import TradingSuite

async def main():
    suite = await TradingSuite.create(\"MNQ\")

    print(f\"Connected to account: {suite.client.account_info.name}\")

    # Get instrument info if needed
    instrument = await suite.client.get_instrument(suite.instrument_id or \"MNQ\")
    print(f\"Trading {instrument.name} - Tick size: ${instrument.tickSize}\")

    data = await suite.client.get_bars(\"MNQ\", days=5)
    print(f\"Retrieved {len(data)} bars\")

    positions = await suite.positions.get_all_positions()
    for position in positions:
        print(f\"Position: {position.size} @ ${position.averagePrice}\")

    # New v3.3.0: Get comprehensive statistics (async-first API)
    stats = await suite.get_stats()
    print(f\"System Health: {stats['health_score']:.1f}/100\")
    print(f\"Total API Calls: {stats['total_api_calls']}\")
    print(f\"Memory Usage: {stats['memory_usage_mb']:.1f} MB\")

    # Export statistics to multiple formats
    prometheus_metrics = await suite.export_stats(\"prometheus\")
    csv_data = await suite.export_stats(\"csv\")

    await suite.disconnect()

if __name__ == \"__main__\":
    asyncio.run(main())
```

### Multi-Instrument Trading (NEW in v3.5.0)

Manage multiple instruments simultaneously for advanced trading strategies:

```python
import asyncio
from project_x_py import TradingSuite

async def multi_instrument_example():
    # Multi-instrument setup - trade multiple futures simultaneously
    suite = await TradingSuite.create(
        instruments=["MNQ", "ES", "MGC"],  # E-mini NASDAQ, S&P 500, Gold
        timeframes=["1min", "5min"],
        enable_orderbook=True,
        enable_risk_management=True
    )

    print(f"Managing {len(suite)} instruments: {list(suite.keys())}")

    # Access specific instruments via dictionary-like interface
    mnq_context = suite["MNQ"]
    es_context = suite["ES"]
    mgc_context = suite["MGC"]

    # Get current prices for all instruments
    for symbol, context in suite.items():
        current_price = await context.data.get_current_price()
        print(f"{symbol}: ${current_price:.2f}")

    # Execute pairs trading strategy (ES vs MNQ correlation)
    es_data = await es_context.data.get_data("5min", bars=100)
    mnq_data = await mnq_context.data.get_data("5min", bars=100)

    # Analyze spread between ES and MNQ for pairs trading
    es_price = es_data.select("close").to_series().to_list()[-1]
    mnq_price = mnq_data.select("close").to_series().to_list()[-1]
    spread = es_price * 50 - mnq_price * 20  # Contract value normalized

    print(f"ES/MNQ Spread: ${spread:.2f}")

    # Portfolio-level position management
    total_exposure = 0
    for symbol, context in suite.items():
        positions = await context.positions.get_all_positions()
        for pos in positions:
            exposure = abs(pos.size * pos.averagePrice)
            total_exposure += exposure
            print(f"{symbol} Exposure: ${exposure:,.2f}")

    print(f"Total Portfolio Exposure: ${total_exposure:,.2f}")

    await suite.disconnect()

# Backward compatibility - existing single-instrument code still works
async def backward_compatible_example():
    # This still works but shows deprecation warnings
    suite = await TradingSuite.create("MNQ")  # Single instrument (legacy)
    data = await suite.data.get_data("5min")  # Direct access (deprecated)

    # Recommended: Use explicit multi-instrument syntax
    suite = await TradingSuite.create(["MNQ"])  # List notation
    data = await suite["MNQ"].data.get_data("5min")  # Explicit access

    await suite.disconnect()

if __name__ == "__main__":
    asyncio.run(multi_instrument_example())
```

**Migration from v3.4.x**:
- Single instrument: `TradingSuite.create("MNQ")` → `TradingSuite.create(["MNQ"])`
- Access managers: `suite.data` → `suite["MNQ"].data`
- All existing code continues to work with deprecation warnings

📚 **Full Example**: See `examples/26_multi_instrument_trading.py` for comprehensive multi-instrument strategies.

### Session Filtering (v3.4.0 - Experimental)

Filter market data and indicators by trading session (RTH vs ETH):

```python
import asyncio
from project_x_py import TradingSuite, SessionConfig, SessionType

async def session_example():
    # RTH-only trading (9:30 AM - 4:00 PM ET)
    rth_suite = await TradingSuite.create(
        ["MNQ"],  # v3.5.0: Use list notation
        timeframes=["1min", "5min"],
        session_config=SessionConfig(session_type=SessionType.RTH)
    )

    # ETH trading (24-hour excluding maintenance breaks)
    eth_suite = await TradingSuite.create(
        ["MNQ"],  # v3.5.0: Use list notation
        timeframes=["1min", "5min"],
        session_config=SessionConfig(session_type=SessionType.ETH)
    )

    # v3.5.0: Use explicit instrument access
    rth_data = await rth_suite["MNQ"].data.get_session_data("1min")
    eth_data = await eth_suite["MNQ"].data.get_session_data("1min")

    print(f"RTH bars: {len(rth_data):,}")  # ~390 bars per day
    print(f"ETH bars: {len(eth_data):,}")  # ~1,410 bars per day (366% more)

    await rth_suite.disconnect()
    await eth_suite.disconnect()

if __name__ == "__main__":
    asyncio.run(session_example())
```

⚠️ **Note**: Session filtering is experimental. Test thoroughly in paper trading before production use.

📚 **Full Example**: See `examples/sessions/16_eth_vs_rth_sessions_demo.py` for comprehensive demonstration of all session features.

### Trading Suite (Enhanced in v3.5.0)

The easiest way to get started with single or multi-instrument trading:

```python
import asyncio
from project_x_py import TradingSuite, EventType

async def main():
    # v3.5.0: Multi-instrument support
    suite = await TradingSuite.create(
        instruments=["MNQ", "ES"],  # Multiple instruments
        timeframes=["5min", "15min", "1hr"],
        enable_orderbook=True,
        enable_risk_management=True
    )

    # Register event handlers (events are instrument-specific)
    async def on_new_bar(event):
        # Event data includes instrument symbol
        symbol = event.data.get('symbol', 'Unknown')
        timeframe = event.data['timeframe']
        bar_close = event.data['data']['close']
        print(f"New {symbol} {timeframe} bar: ${bar_close}")

    async def on_trade(event):
        symbol = event.data.get('symbol', 'Unknown')
        print(f"{symbol} Trade: {event.data['size']} @ ${event.data['price']}")

    # Register the handlers
    await suite.on(EventType.NEW_BAR, on_new_bar)
    await suite.on(EventType.TRADE_TICK, on_trade)

    # v3.5.0: Access components by instrument
    for symbol, context in suite.items():
        data = await context.data.get_data("5min")
        orderbook = context.orderbook  # Available when enabled
        order_manager = context.orders
        position_manager = context.positions
        print(f"{symbol}: {len(data)} bars loaded")

    # Single instrument access (for backward compatibility)
    if len(suite) == 1:
        # Single instrument - can still access directly with deprecation warning
        single_data = await suite.data.get_data("5min")  # Shows warning

        # Recommended: Use explicit access
        symbol = list(suite.keys())[0]
        single_data = await suite[symbol].data.get_data("5min")

    await suite.disconnect()

if __name__ == \"__main__\":
    asyncio.run(main())
```

### Real-time Trading Example

```python
import asyncio
from project_x_py import TradingSuite

async def on_tick(event):
    tick_data = event.data
    symbol = tick_data.get('symbol', 'Unknown')
    print(f\"{symbol} Price: ${tick_data['price']}\")

async def main():
    # v3.5.0: Use list notation for single or multiple instruments
    suite = await TradingSuite.create([\"MNQ\"])

    # Get the instrument context
    mnq = suite[\"MNQ\"]

    # Register tick callback on the specific instrument
    await mnq.data.add_callback(\"tick\", on_tick)

    current_price = await mnq.data.get_current_price()

    # Place bracket order using the instrument context
    response = await mnq.orders.place_bracket_order(
        contract_id=mnq.instrument.id,  # v3.5.0: Access via context
        side=0,  # Buy
        size=1,
        entry_price=current_price,
        stop_loss_price=current_price - 10,
        take_profit_price=current_price + 15
    )

    print(f\"Order placed: {response}\")

    await asyncio.sleep(60)
    await suite.disconnect()

# Multi-instrument real-time example
async def multi_instrument_realtime():
    suite = await TradingSuite.create([\"MNQ\", \"ES\"])

    async def on_multi_tick(event):
        tick_data = event.data
        symbol = tick_data.get('symbol', 'Unknown')
        print(f\"{symbol}: ${tick_data['price']:.2f}\")

    # Register callback for all instruments
    for symbol, context in suite.items():
        await context.data.add_callback(\"tick\", on_multi_tick)

    # Monitor both instruments
    await asyncio.sleep(30)
    await suite.disconnect()

if __name__ == \"__main__\":
    asyncio.run(main())
    # asyncio.run(multi_instrument_realtime())  # Uncomment for multi-instrument
```

## ⚡ Event Handling Best Practices

### Avoiding Deadlocks (Fixed in v3.1.6)

Prior to v3.1.6, calling `suite.data` methods from within event handlers could cause deadlocks. This has been fixed, but for best performance:

```python
# Best: Use event data directly
async def on_new_bar(event):
    # Bar data is provided in the event
    bar = event.data['data']
    print(f"Close: {bar['close']}, Volume: {bar['volume']}")

# Register the handler
await suite.on(EventType.NEW_BAR, on_new_bar)

# Also OK (v3.1.6+): Access data methods if needed
async def on_new_bar_with_context(event):
    # Safe in v3.1.6+, but slightly slower
    current_price = await suite.data.get_current_price()
    historical = await suite.data.get_data("5min", bars=20)

await suite.on(EventType.NEW_BAR, on_new_bar_with_context)
```

## 📚 Documentation

### Authentication

Set environment variables:
```bash
export PROJECT_X_API_KEY="your_api_key"
export PROJECT_X_USERNAME="your_username"
```

Or use a config file (`~/.config/projectx/config.json`):
```json
{
    "api_key": "your_api_key",
    "username": "your_username",
    "api_url": "https://api.topstepx.com/api",
    "websocket_url": "wss://api.topstepx.com",
    "timezone": "US/Central"
}
```

### Available Features

TradingSuite supports optional features that can be enabled during initialization:

| Feature | String Value | Description |
|---------|-------------|-------------|
| **OrderBook** | `"orderbook"` | Level 2 market depth, bid/ask analysis, iceberg detection |
| **Risk Manager** | `"risk_manager"` | Position sizing, risk validation, managed trades |
| **Session Filtering** | Built-in (v3.4.0) | RTH/ETH session filtering (experimental) |
| **Trade Journal** | `"trade_journal"` | Trade logging and performance tracking (future) |
| **Performance Analytics** | `"performance_analytics"` | Advanced metrics and analysis (future) |
| **Auto Reconnect** | `"auto_reconnect"` | Automatic WebSocket reconnection (future) |

**Note:** PositionManager and OrderManager are always included and don't require feature flags.

```python
# Enable specific features
suite = await TradingSuite.create(
    "MNQ",
    features=["orderbook", "risk_manager"]
)

# Access feature-specific components
if suite.orderbook:  # Only available when orderbook feature is enabled
    spread = await suite.orderbook.get_bid_ask_spread()

if suite.risk_manager:  # Only available when risk_manager feature is enabled
    sizing = await suite.risk_manager.calculate_position_size(
        entry_price=100.0,
        stop_loss=99.0
    )
```

### Component Overview

#### ProjectX Client
The underlying async client, accessible via suite.client:
```python
suite = await TradingSuite.create(\"MNQ\")
# Use suite.client for direct API operations
```

#### OrderManager
Async order management via suite.orders:
```python
await suite.orders.place_market_order(suite.instrument.id, side=0, size=1)
await suite.orders.modify_order(order_id, new_price=100.50)
await suite.orders.cancel_order(order_id)
```

#### PositionManager
Async position tracking and analytics:
```python
positions = await suite.positions.get_all_positions()
pnl = await suite.positions.get_portfolio_pnl()
await suite.positions.close_position(contract_id)
```

#### RealtimeDataManager
Async multi-timeframe data management:
```python
# Data manager is automatically initialized
data = await suite.data.get_data("15min")
current_price = await suite.data.get_current_price()
```

#### OrderBook
Async Level 2 market depth analysis (when enabled):
```python
# Enable orderbook in features when creating suite
suite = await TradingSuite.create("MNQ", features=["orderbook"])

spread = await suite.orderbook.get_bid_ask_spread()
imbalance = await suite.orderbook.get_market_imbalance()
icebergs = await suite.orderbook.detect_iceberg_orders()
```

#### RiskManager
Risk management and managed trades (requires feature flag):
```python
# Enable risk manager in features
suite = await TradingSuite.create("MNQ", features=["risk_manager"])

# Risk manager integrates with PositionManager automatically
# Use for position sizing and risk validation
sizing = await suite.risk_manager.calculate_position_size(
    entry_price=100.0,
    stop_loss=99.0,
    risk_percent=0.02  # Risk 2% of account
)

# Use managed trades for automatic risk management
async with suite.managed_trade(max_risk_percent=0.01) as trade:
    # Market price fetched automatically (v3.1.11+)
    result = await trade.enter_long(
        stop_loss=current_price - 50,
        take_profit=current_price + 100
    )
```

**Note:** RiskManager requires the `"risk_manager"` feature flag and automatically integrates with PositionManager for comprehensive risk tracking.

### Statistics & Analytics (REDESIGNED in v3.3.0)

Complete async-first statistics system with advanced monitoring and export capabilities:

```python
# Get comprehensive system statistics (async-first API)
stats = await suite.get_stats()

# Health scoring (0-100) with intelligent monitoring
print(f"System Health: {stats['health_score']:.1f}/100")

# Performance metrics with enhanced tracking
print(f"API Calls: {stats['total_api_calls']}")
print(f"Success Rate: {stats['api_success_rate']:.1%}")
print(f"Memory Usage: {stats['memory_usage_mb']:.1f} MB")

# Component-specific statistics (all async for consistency)
order_stats = await suite.orders.get_stats()
print(f"Fill Rate: {order_stats['fill_rate']:.1%}")
print(f"Average Fill Time: {order_stats['avg_fill_time_ms']:.0f}ms")

position_stats = await suite.positions.get_stats()
print(f"Win Rate: {position_stats.get('win_rate', 0):.1%}")

# Multi-format export capabilities
prometheus_metrics = await suite.export_stats("prometheus")
csv_data = await suite.export_stats("csv")
datadog_metrics = await suite.export_stats("datadog")

# Real-time health monitoring with degradation detection
health_score = await suite.get_health_score()
if health_score < 70:
    print("⚠️ System health degraded - check components")
    component_health = await suite.get_component_health()
    for name, health in component_health.items():
        if health['error_count'] > 0:
            print(f"  {name}: {health['error_count']} errors")
```

**Key Features (v3.3.0):**
- **100% Async Architecture**: All statistics methods use async/await for optimal performance
- **Multi-format Export**: JSON, Prometheus, CSV, and Datadog formats with data sanitization
- **Component-Specific Tracking**: Enhanced statistics for all managers with specialized metrics
- **Health Monitoring**: Intelligent 0-100 health scoring with configurable thresholds
- **Performance Optimization**: TTL caching, parallel collection, and circular buffers
- **Memory Efficiency**: Circular buffers and lock-free reads for frequently accessed metrics
- **Comprehensive Testing**: 45+ tests covering all aspects of the async statistics system

### Technical Indicators

All 59+ indicators work with async data pipelines:
```python
import polars as pl
from project_x_py.indicators import RSI, SMA, MACD, FVG, ORDERBLOCK, WAE

# Get data - multiple ways
data = await client.get_bars("ES", days=30)  # Last 30 days

# Or use specific time range (v3.1.5+)
from datetime import datetime
start = datetime(2025, 1, 1, 9, 30)
end = datetime(2025, 1, 10, 16, 0)
data = await client.get_bars("ES", start_time=start, end_time=end)

# Apply traditional indicators
data = data.pipe(SMA, period=20).pipe(RSI, period=14)

# Apply pattern recognition indicators
data_with_fvg = FVG(data, min_gap_size=0.001, check_mitigation=True)
data_with_ob = ORDERBLOCK(data, min_volume_percentile=70)
data_with_wae = WAE(data, sensitivity=150)

# Or use class-based interface
from project_x_py.indicators import OrderBlock, FVG, WAE
ob = OrderBlock()
data_with_ob = ob.calculate(data, use_wicks=True)
```

#### New Pattern Indicators (v2.0.2)
- **Fair Value Gap (FVG)**: Identifies price imbalance areas
- **Order Block**: Detects institutional order zones
- **Waddah Attar Explosion (WAE)**: Strong trend and breakout detection

## 🏗️ Examples

The `examples/` directory contains comprehensive async examples:

### Core Functionality
- **00_trading_suite_demo.py** - Complete TradingSuite demonstration
- **01_basic_client_connection.py** - Async authentication and basic operations
- **02_order_management.py** - Async order placement and management
- **03_position_management.py** - Async position tracking and P&L
- **04_realtime_data.py** - Real-time async data streaming

### Advanced Features
- **05_orderbook_analysis.py** - Async market depth analysis
- **06_advanced_orderbook.py** - Advanced orderbook analytics
- **06_multi_timeframe_strategy.py** - Async multi-timeframe trading
- **07_technical_indicators.py** - Using indicators with async data
- **08_order_and_position_tracking.py** - Integrated async monitoring
- **09_get_check_available_instruments.py** - Interactive async instrument search

### Multi-Instrument Trading (NEW in v3.5.0)
- **26_multi_instrument_trading.py** - Complete multi-instrument trading demo
- **Portfolio management** - Risk management across multiple instruments
- **Pairs trading** - ES vs MNQ spread analysis and correlation strategies
- **Cross-market analysis** - Commodities, indices, and currency futures

### Event System & Data Access
- **10_unified_event_system.py** - Event-driven trading with EventBus
- **11_simplified_data_access.py** - Simplified data access patterns
- **12_simplified_multi_timeframe.py** - Multi-timeframe analysis
- **12_simplified_strategy.py** - Simplified strategy using auto-initialization

### Risk Management & Order Lifecycle
- **13_enhanced_models.py** - Enhanced data models demonstration
- **15_order_lifecycle_tracking.py** - Complete order lifecycle monitoring
- **15_risk_management.py** - Risk management features
- **16_managed_trades.py** - ManagedTrade context manager usage
- **16_join_orders.py** - Advanced order joining techniques

## 🔧 Configuration

### TradingSuiteConfig Options

Use parameters in TradingSuite.create()

### Performance Tuning

Configure caching and memory limits:
```python
# In OrderBook
orderbook = OrderBook(
    instrument="ES",
    max_trades=10000,  # Trade history limit
    max_depth_entries=1000,  # Depth per side
    cache_ttl=300  # 5 minutes
)

# In ProjectXRealtimeDataManager (integrated with TradingSuite)
# Data manager is configured via DataManagerConfig
from project_x_py.realtime_data_manager.types import DataManagerConfig

config = DataManagerConfig(
    max_bars_per_timeframe=1000,
    enable_mmap_overflow=True,
    enable_dynamic_limits=True
)
```

## 🔍 Error Handling & Logging (v2.0.5+)

### Structured Error Handling

All async operations use typed exceptions with automatic retry and logging:

```python
from project_x_py.exceptions import (
    ProjectXAuthenticationError,
    ProjectXOrderError,
    ProjectXRateLimitError
)
from project_x_py.utils import configure_sdk_logging

# Configure logging for production
configure_sdk_logging(
    level=logging.INFO,
    format_json=True,  # JSON logs for production
    log_file="/var/log/projectx/trading.log"
)

try:
    async with ProjectX.from_env() as client:
        await client.authenticate()  # Automatic retry on network errors
except ProjectXAuthenticationError as e:
    # Structured error with context
    print(f"Authentication failed: {e}")
except ProjectXRateLimitError as e:
    # Automatic backoff already attempted
    print(f"Rate limit exceeded: {e}")
```

### Error Handling Decorators

The SDK uses decorators for consistent error handling:

```python
# All API methods have built-in error handling
@handle_errors("place order")
@retry_on_network_error(max_attempts=3)
@validate_response(required_fields=["orderId"])
async def place_order(self, ...):
    # Method implementation
```

## 🔧 Troubleshooting

### Common Issues

#### Authentication Issues
```python
# Error: "PROJECT_X_API_KEY environment variable is required"
# Solution: Set environment variables before running
export PROJECT_X_API_KEY="your_api_key"
export PROJECT_X_USERNAME="your_username"

# Or use config file at ~/.config/projectx/config.json
```

#### Instrument Not Found
```python
# Error: "Instrument MNQ not found"
# Solution: Verify instrument symbol is correct
# Common symbols: "MNQ", "MES", "MGC", "ES", "NQ"
```

#### Connection Timeouts
```python
# The TradingSuite handles connections automatically
# If you need custom timeout handling:
try:
    suite = await TradingSuite.create(
        "MNQ",
        timeout=30  # Custom timeout in seconds
    )
except Exception as e:
    print(f"Connection failed: {e}")
```

#### Memory Issues with Long-Running Strategies
```python
# The suite automatically manages memory, but for long-running strategies:
# 1. Use reasonable initial_days (3-7 is usually sufficient)
# 2. The data manager automatically maintains sliding windows
# 3. OrderBook has built-in memory limits
```

#### Rate Limiting
```python
# The SDK handles rate limiting automatically, but if you encounter issues:
# 1. Reduce concurrent API calls
# 2. Add delays between operations
# 3. Use batch operations where available
```

## 📌 Versioning Policy

As of v3.1.1, this project follows strict [Semantic Versioning](https://semver.org/):

- **PATCH** (x.x.N): Bug fixes only, no API changes
- **MINOR** (x.N.x): New features, backward compatible, deprecation warnings added
- **MAJOR** (N.x.x): Breaking changes allowed, deprecated features removed

### Deprecation Policy
- Features marked as deprecated will include clear migration instructions
- Deprecated features maintained for at least 2 minor versions
- Removal only occurs in major version releases

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup
```bash
# Clone repository
git clone https://github.com/yourusername/project-x-py.git
cd project-x-py

# Install with dev dependencies
uv sync

# Run tests
uv run pytest

# Format code
uv run ruff format .

# Lint
uv run ruff check .
```

## 📄 License

This project is licensed under the MIT License - see [LICENSE](LICENSE) file for details.

## 🔗 Resources

- [ProjectX Platform](https://www.projectx.com/)
- [API Documentation](https://documenter.getpostman.com/view/24500417/2s9YRCXrKF)
- [GitHub Repository](https://github.com/yourusername/project-x-py)
- [PyPI Package](https://pypi.org/project/project-x-py/)

## ⚠️ Disclaimer

This SDK is for educational and development purposes. Trading futures involves substantial risk of loss and is not suitable for all investors. Past performance is not indicative of future results. Always test your strategies thoroughly before using real funds.
