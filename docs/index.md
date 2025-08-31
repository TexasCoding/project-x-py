# ProjectX Python SDK

[![PyPI version](https://img.shields.io/pypi/v/project-x-py.svg)](https://pypi.org/project/project-x-py/)
[![Python versions](https://img.shields.io/pypi/pyversions/project-x-py.svg)](https://pypi.org/project/project-x-py/)
[![License](https://img.shields.io/github/license/TexasCoding/project-x-py.svg)](https://github.com/TexasCoding/project-x-py/blob/main/LICENSE)
[![Documentation Status](https://readthedocs.org/projects/project-x-py/badge/?version=latest)](https://project-x-py.readthedocs.io/en/latest/?badge=latest)

**project-x-py** is a high-performance **async Python SDK** for the [ProjectX Trading Platform](https://www.projectx.com/) Gateway API. This library enables developers to build sophisticated trading strategies and applications by providing comprehensive async access to futures trading operations, real-time market data, Level 2 orderbook analysis, and a complete technical analysis suite with 58+ TA-Lib compatible indicators including pattern recognition.

!!! note "Version 3.5.3 - Complete Documentation & Testing Improvements"
    **Latest Release**: Comprehensive documentation updates, complete test coverage for realtime_data_manager module, and modernized all code examples. Fixed type safety issues and achieved 100% test passing rate across the SDK. Previous releases introduced multi-instrument support enabling traders to manage multiple futures contracts simultaneously with pairs trading, cross-market arbitrage, and portfolio-level risk management. Full backward compatibility maintained.

!!! note "Stable Production Release"
    Since v3.1.1, this project maintains strict semantic versioning with backward compatibility between minor versions. Breaking changes only occur in major version releases (4.0.0+). Deprecation warnings are provided for at least 2 minor versions before removal.

!!! important "Client Library/SDK"
    This is a **client library/SDK**, not a trading strategy. It provides the tools and infrastructure to help developers create their own trading strategies that integrate with the ProjectX platform.

## Quick Start

Install the package:

```bash
uv add project-x-py
```

Or with pip:

```bash
pip install project-x-py
```

Set up your credentials:

```bash
export PROJECT_X_API_KEY='your_api_key'  # pragma: allowlist secret
export PROJECT_X_USERNAME='your_username'
```

Start trading:

```python
import asyncio
from project_x_py import TradingSuite
from project_x_py.indicators import RSI, SMA, MACD

async def main():
    # V3.5: Multi-instrument TradingSuite for advanced strategies
    suite = await TradingSuite.create(
        instruments=["MNQ", "ES", "MGC"],  # Multiple instruments
        timeframes=["1min", "5min"],
        features=["orderbook", "risk_manager"]
    )

    # Access specific instruments
    mnq_context = suite["MNQ"]
    es_context = suite["ES"]

    # Get market data with technical analysis
    mnq_data = await suite.client.get_bars('MNQ', days=30, interval=60)
    mnq_data = RSI(mnq_data, period=14)  # Add RSI
    mnq_data = SMA(mnq_data, period=20)  # Add moving average

    # Multi-instrument trading
    await mnq_context.orders.place_limit_order(
        contract_id=mnq_context.instrument_info.id,
        side=0, size=1, limit_price=21050.0
    )

    # Portfolio-level analytics
    for symbol, context in suite.items():
        price = await context.data.get_current_price()
        print(f"{symbol}: ${price:.2f}")

    await suite.disconnect()

# Run the async function
asyncio.run(main())
```

## Key Features

### 🚀 Core Trading Features
- **Multi-Instrument Support (v3.5.0)**: Simultaneous trading across multiple futures contracts
- Complete order management (market, limit, stop, bracket orders)
- Real-time position tracking and portfolio management
- Advanced risk management and position sizing
- **Cross-Instrument Analytics**: Pairs trading, spread analysis, correlation strategies
- Multi-account support

### 📊 Market Data & Analysis
- **Multi-Instrument Data Streams (v3.5.0)**: Concurrent data processing for multiple contracts
- Async historical OHLCV data with multiple timeframes
- Real-time market data feeds via async WebSocket
- **Level 2 orderbook analysis** with institutional-grade features
- **59+ Technical Indicators** with TA-Lib compatibility (RSI, MACD, Bollinger Bands, Pattern Recognition, Lorenz Formula, etc.)
- **Advanced market microstructure** analysis (iceberg detection, order flow, volume profile)
- **Market Manipulation Detection**: 6 spoofing pattern types with regulatory compliance features
- **100% Async Statistics System**: Health monitoring, multi-format export, component tracking
- **Cross-Market Analysis**: Correlation matrices, spread calculations, sector rotation signals

### 🔧 Developer Tools
- Comprehensive Python typing support
- Extensive examples and tutorials
- Built-in logging and debugging tools
- Flexible configuration management

### ⚡ Real-time Capabilities
- Async live market data streaming
- Real-time order and position updates
- Async event-driven architecture
- WebSocket-based connections with async handlers

### 🛡️ Enterprise Features (v3.3.4)
- EventBus architecture for unified event handling
- Factory functions with dependency injection
- JWT-based authentication system
- Centralized error handling with decorators
- Structured JSON logging for production
- Automatic retry with exponential backoff
- Rate limit management
- Comprehensive type safety (mypy compliant)
- **Financial Precision**: Decimal type for exact calculations
- **Advanced Memory Management**: Bounded buffers, automatic cleanup
- **Performance Optimized**: 80% faster algorithms, O(N log N) complexity

## Architecture Overview

### Core Components

**TradingSuite** - Multi-instrument trading environment with automatic initialization
```python
# Single instrument (backward compatible)
suite = await TradingSuite.create(["MNQ"], features=["orderbook", "risk_manager"])

# Multiple instruments (v3.5.0 new capability)
suite = await TradingSuite.create(["MNQ", "ES", "MGC"], features=["orderbook", "risk_manager"])
mnq_context = suite["MNQ"]  # Access specific instrument
```

**ProjectX Client** - Main client for API interactions and authentication
- Async authentication and JWT token management
- HTTP connection pooling with retry logic
- Intelligent caching for instruments
- Rate limiting and connection management

**Order Management**
- **OrderManager**: Comprehensive async order operations
- **Bracket Orders**: OCO and bracket order logic
- **Position Orders**: Position-based order management
- **Order Tracking**: Order state tracking and lifecycle management

**Position & Risk Management**
- **PositionManager**: Async position tracking and analytics
- **RiskManager**: Integrated risk management with ManagedTrade
- **Risk Analytics**: Performance metrics and monitoring

**Real-time Data Processing**
- **RealtimeDataManager**: Async WebSocket data processing
- **OrderBook**: Level 2 market depth with spoofing detection
- **Event System**: Unified EventBus for cross-component communication

**Technical Analysis**
- **59+ Indicators**: TA-Lib compatible with Polars DataFrames
- **Pattern Recognition**: Fair Value Gaps, Order Blocks, Waddah Attar, Lorenz Formula
- **Advanced Patterns**: Iceberg detection, market manipulation

**Statistics & Monitoring (v3.3.0)**
- **100% Async Architecture**: All statistics methods use async/await
- **Multi-format Export**: JSON, Prometheus, CSV, Datadog with data sanitization
- **Health Monitoring**: 0-100 health scoring with configurable thresholds
- **Performance Optimization**: TTL caching, parallel collection, circular buffers

## Documentation Structure

### [Getting Started](getting-started/installation.md)
- [Installation](getting-started/installation.md)
- [Quick Start](getting-started/quickstart.md)
- [Authentication](getting-started/authentication.md)
- [Configuration](getting-started/configuration.md)

### [User Guide](guide/trading-suite.md)
- [Trading Suite](guide/trading-suite.md) - Main entry point
- [Order Management](guide/orders.md) - Placing and managing orders
- [Position Tracking](guide/positions.md) - Portfolio management
- [Real-time Data](guide/realtime.md) - WebSocket streaming
- [Technical Indicators](guide/indicators.md) - 59+ analysis tools
- [Risk Management](guide/risk.md) - Position sizing and limits
- [Order Book](guide/orderbook.md) - Level 2 market depth

### [API Reference](api/client.md)
- [Client](api/client.md) - Core client functionality
- [Trading Suite](api/trading-suite.md) - Unified trading interface
- [Order Manager](api/order-manager.md) - Order operations
- [Position Manager](api/position-manager.md) - Position tracking
- [Data Manager](api/data-manager.md) - Market data access
- [Indicators](api/indicators.md) - Technical analysis
- [Models](api/models.md) - Data structures

### [Examples](examples/basic.md)
- [Basic Usage](examples/basic.md) - Getting started examples
- [Advanced Trading](examples/advanced.md) - Complex strategies
- [Real-time Data](examples/realtime.md) - WebSocket examples
- [Backtesting](examples/backtesting.md) - Historical analysis
- [Notebooks](examples/notebooks/index.md) - Interactive examples

### [Development](development/contributing.md)
- [Contributing](development/contributing.md) - How to contribute
- [Testing](development/testing.md) - Testing guidelines
- [Agents](development/agents.md) - Development agents
- [Architecture](development/architecture.md) - System design

### [Migration](migration/v3-to-v4.md)
- [v3 to v4](migration/v3-to-v4.md) - Major version migration
- [Breaking Changes](migration/breaking-changes.md) - Change history

## Recent Changes

### v3.5.3 - Complete Documentation & Testing Improvements (2025-01-31)
- **Fixed**: Mypy error with `get_overflow_stats()` method signatures in mmap overflow handling
- **Fixed**: Type safety issues in overflow statistics reporting
- **Fixed**: All tests now passing for realtime_data_manager module (100% pass rate)
- **Updated**: All documentation to be 100% accurate with actual implementation
- **Updated**: All 25+ examples to use modern TradingSuite API and component access patterns
- **Improved**: Documentation accuracy and API consistency across the SDK

### v3.5.2 - TradingSuite with Enhanced Testing & Documentation (2025-01-31)
- **Fixed**: Session management methods using incorrect attribute names (`_contexts` instead of `_instruments`)
- **Fixed**: Critical implementation bugs discovered during comprehensive testing
- **Updated**: All documentation to correctly reflect the actual API implementation
- **Added**: 51 new tests for 100% TradingSuite coverage
- **Improved**: Test-driven development approach with 88 total tests for TradingSuite

### v3.5.1 - Critical Bug Fixes (2025-01-30)
- **Fixed**: Context manager re-entry issue in TradingSuite
- **Fixed**: ManagedTrade missing property accessors
- **Fixed**: Event loop handling in `get_stats_sync()` for nested async contexts
- **Fixed**: Inconsistent deprecation warnings for direct component access
- **Fixed**: Config file validation order (extension check before file operations)
- **Fixed**: Session management methods in multi-instrument mode

### v3.5.0 - Multi-Instrument TradingSuite (2025-01-25)
- **MAJOR**: Revolutionary multi-instrument support for simultaneous contract management
- **Added**: `InstrumentContext` dataclass for encapsulating instrument-specific managers
- **Added**: Dictionary-like container protocol with `suite["SYMBOL"]` access
- **Added**: Parallel creation and initialization of multiple instrument contexts
- **Added**: Event isolation between instruments for proper separation
- **Added**: Granular resource management with fail-safe cleanup
- **Added**: Cross-instrument analytics and portfolio-level operations
- **Added**: Comprehensive migration guide and backward compatibility
- **Added**: Example: `examples/26_multi_instrument_trading.py`
- **Enhancement**: Zero breaking changes - all existing code continues to work

### v3.4.0 - ETH vs RTH Trading Sessions (2025-08-28)
- **Added**: Trading Sessions module for ETH/RTH filtering (EXPERIMENTAL)
- **Added**: SessionConfig and SessionFilterMixin for session-based data filtering
- **Added**: Session-aware indicators and statistics calculations
- **Added**: Automatic maintenance break exclusion (5-6 PM ET daily)
- **Added**: TradingSuite integration with `session_config` parameter
- **Added**: Comprehensive example in `examples/sessions/16_eth_vs_rth_sessions_demo.py`
- **Warning**: This feature is experimental and not thoroughly tested with live data

### v3.3.6 - Major Quality Assurance Release (2025-08-28)
- **Fixed**: Achieved zero mypy errors, zero linting issues, zero IDE diagnostics
- **Fixed**: Order Manager module complete overhaul with protocol compliance
- **Fixed**: TradingSuite duplicate subscription issues
- **Added**: 100+ new comprehensive tests for edge cases
- **Improved**: Complete test coverage with all 1,300+ tests passing

See the complete [changelog](changelog.md) for all version history.

## License

MIT License - see [LICENSE](https://github.com/TexasCoding/project-x-py/blob/main/LICENSE) for details.
