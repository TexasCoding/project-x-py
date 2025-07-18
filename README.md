# ProjectX Python Client

[![Python Version](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A **professional Python client** for the TopStepX ProjectX Gateway API, designed for institutional traders and quantitative analysts. This library provides comprehensive access to futures trading operations, historical market data, real-time streaming, and advanced market microstructure analysis.

## 📊 Project Status

**Current Version**: v0.2.0 (Active Development)

✅ **Production Ready**:
- Complete futures trading API integration (orders, positions, trades)
- Historical market data with multiple timeframes
- Account management and authentication
- Real-time WebSocket connections
- Order and position management with error handling
- Professional-grade code with full type hints

🚧 **In Development** (v0.3.0):
- Advanced market microstructure analysis suite
- Level 2 orderbook processing and analytics
- Institutional order flow detection algorithms
- Market imbalance and liquidity analysis tools

📋 **Planned Features**:
- Machine learning integration for pattern recognition
- Advanced backtesting engine with tick-level data
- Professional trading strategy framework

## 🚀 Current Features

### ✅ Core Trading Operations (Production Ready)
- **🏦 Account Management** - Complete account info, balance monitoring, permissions
- **📊 Historical Market Data** - OHLCV data with multiple timeframes (1min to 1day)
- **📈 Order Management** - Place, modify, cancel orders (market, limit, stop, bracket orders)
- **💼 Position Management** - Real-time position tracking, P&L calculations
- **📋 Trade History** - Comprehensive trade search and analysis
- **🔍 Instrument Search** - Find and filter available futures contracts

### ⚡ Real-Time Capabilities (Production Ready)
- **🌐 WebSocket Connections** - Authenticated real-time data streams
- **🔄 Live Order Updates** - Instant order status and fill notifications
- **📊 Position Monitoring** - Real-time position updates without polling
- **📈 Market Data Streaming** - Live price updates and market events
- **🔐 Session Management** - Automatic token refresh and connection handling

### 🚧 Advanced Features (In Development - v0.3.0)
- **🎯 Level 2 Orderbook** - Full market depth analysis and visualization
- **📊 Order Flow Analysis** - Buy/sell pressure detection and trade flow metrics
- **🧊 Iceberg Detection** - Hidden order identification algorithms
- **📈 Volume Profile** - Market structure analysis with POC and value areas
- **⚖️ Market Imbalance** - Real-time imbalance detection and alerts
- **🏗️ Support/Resistance** - Dynamic level identification from order flow

### 🛠️ Professional Quality
- **🔧 Production Architecture** - Modular design with comprehensive error handling
- **📝 Full Type Safety** - Complete type hints for IDE support and code quality
- **⚙️ Flexible Configuration** - Environment variables, config files, and runtime options
- **🔍 Comprehensive Logging** - Structured logging for debugging and monitoring
- **🧪 Testing Framework** - Unit and integration tests for reliability
- **🎨 Code Quality** - Black formatting, Ruff linting, and MyPy type checking

## 📦 Installation

### Quick Install (Recommended)
```bash
# Install with uv (fastest)
uv add project-x-py

# Or with pip
pip install project-x-py
```

### Optional Dependencies
```bash
# Real-time WebSocket features
uv add "project-x-py[realtime]"

# Development tools (linting, testing, type checking)
uv add "project-x-py[dev]" 

# Documentation building
uv add "project-x-py[docs]"

# Everything included
uv add "project-x-py[all]"
```

### Development Setup
```bash
git clone https://github.com/TexasCoding/project-x-py.git
cd project-x-py
uv sync --extra dev --extra docs
```

### System Requirements
- **Python**: 3.12 or higher
- **API Access**: TopStepX account with API credentials
- **Optional**: Real-time data subscription for WebSocket features

## ⚡ Quick Start

### 1. Authentication Setup
```bash
# Set environment variables
export PROJECT_X_API_KEY="your_api_key_here"
export PROJECT_X_USERNAME="your_username_here"

# Or create ~/.config/projectx/config.json
{
  "api_key": "your_api_key",
  "username": "your_username"
}
```

### 2. Basic Trading Operations
```python
from project_x_py import ProjectX

# Initialize client
client = ProjectX.from_env()

# Get account information
account = client.get_account_info()
print(f"Account: {account.name} | Balance: ${account.balance:,.2f}")

# Search for instruments
instruments = client.search_instruments("MGC")  # Micro Gold futures
print(f"Found {len(instruments)} MGC contracts")

# Get historical market data
data = client.get_data("MGC", days=5, interval=15)  # 5 days, 15-min bars
print(f"Retrieved {len(data)} OHLCV bars")
print(f"Latest close: ${data['close'].tail(1).item():.2f}")

# Check current positions
positions = client.search_open_positions()
for pos in positions:
    print(f"{pos.contractId}: {pos.size} contracts @ ${pos.averagePrice:.2f}")
```

### 3. Order Management
```python
# Place a limit order (requires real account/paper trading)
try:
    # Get specific contract ID
    instrument = client.get_instrument("MGC")
    contract_id = instrument.activeContract
    
    # Place limit buy order
    response = client.place_limit_order(
        contract_id=contract_id,
        side=0,  # 0=Buy, 1=Sell
        size=1,  # 1 micro contract
        limit_price=2000.0  # $2000/oz limit
    )
    
    if response.success:
        print(f"✅ Order placed: {response.orderId}")
    else:
        print(f"❌ Order failed: {response.errorMessage}")
        
except Exception as e:
    print(f"Order error: {e}")

# Check open orders
orders = client.search_open_orders()
for order in orders:
    print(f"Order {order.id}: {order.contractId} {order.side} {order.size}@${order.limitPrice}")
```

### 4. Real-Time Data Streaming
```python
from project_x_py import ProjectXRealtimeClient

# Set up real-time client (requires realtime extras)
jwt_token = client.get_session_token()
realtime = ProjectXRealtimeClient(jwt_token, account_id=str(account.id))

# Connect and subscribe to updates
if realtime.connect():
    print("✅ Connected to real-time data")
    
    # Subscribe to user events (orders, positions, trades)
    realtime.subscribe_user_updates()
    
    # Subscribe to market data for specific contracts
    realtime.subscribe_market_data([contract_id])
    
    # Add event handlers
    def on_order_update(data):
        print(f"📈 Order update: {data}")
    
    def on_position_update(data):
        print(f"💼 Position update: {data}")
    
    realtime.add_callback("order_update", on_order_update)
    realtime.add_callback("position_update", on_position_update)
    
    # Keep connection alive (in production, use proper event loop)
    import time
    time.sleep(10)  # Monitor for 10 seconds
    
    realtime.disconnect()
```

## 🚧 Advanced Features Preview (v0.3.0)

The next major version will include advanced market microstructure analysis capabilities. Here's a preview of what's coming:

### 🎯 Planned Advanced Features
- **🧊 Iceberg Detection** - Identify hidden institutional orders
- **💧 Liquidity Analysis** - Find significant price levels with volume concentration
- **📊 Order Flow Analysis** - Real-time buy/sell pressure tracking
- **📈 Volume Profile** - Point of Control and Value Area identification
- **⚖️ Market Imbalance** - Orderbook and trade flow imbalance detection
- **🏗️ Support/Resistance** - Dynamic level detection from market structure

### 🔬 Development Status
These advanced features are currently in active development. For early access or to contribute to development:
- 📋 Check the [GitHub Issues](https://github.com/TexasCoding/project-x-py/issues) for current development tasks
- 💬 Join discussions in [GitHub Discussions](https://github.com/TexasCoding/project-x-py/discussions)
- 📧 Contact the maintainer for collaboration opportunities

## 📖 Working Examples

### Historical Data Analysis
```python
import polars as pl
from datetime import datetime, timedelta

# Get extended historical data
client = ProjectX.from_env()
data = client.get_data("MGC", days=30, interval=60)  # 30 days, 1-hour bars

# Convert to Polars DataFrame for analysis
df = pl.from_pandas(data)

# Calculate technical indicators
df = df.with_columns([
    # Simple moving averages
    pl.col("close").rolling_mean(window_size=20).alias("sma_20"),
    pl.col("close").rolling_mean(window_size=50).alias("sma_50"),
    
    # Price changes
    (pl.col("close") - pl.col("close").shift(1)).alias("price_change"),
    ((pl.col("close") / pl.col("close").shift(1)) - 1).alias("returns"),
    
    # Volume analysis
    pl.col("volume").rolling_mean(window_size=20).alias("avg_volume"),
])

# Find high-volume periods
high_volume = df.filter(pl.col("volume") > pl.col("avg_volume") * 1.5)
print(f"High volume periods: {len(high_volume)}")

# Identify trend changes
trend_changes = df.filter(
    (pl.col("sma_20").shift(1) < pl.col("sma_50").shift(1)) & 
    (pl.col("sma_20") > pl.col("sma_50"))
)
print(f"Bullish crossovers: {len(trend_changes)}")
```

### Portfolio Analysis
```python
from datetime import datetime, timedelta

# Get comprehensive account overview
account = client.get_account_info()
print(f"Account: {account.name} | Balance: ${account.balance:,.2f}")
print(f"Trading Status: {'Active' if account.canTrade else 'View Only'}")

# Analyze recent trading performance
end_date = datetime.now()
start_date = end_date - timedelta(days=30)  # Last 30 days
trades = client.search_trades(start_date)

if trades:
    # Calculate performance metrics
    total_pnl = sum(t.profitAndLoss for t in trades if t.profitAndLoss)
    winning_trades = [t for t in trades if t.profitAndLoss and t.profitAndLoss > 0]
    losing_trades = [t for t in trades if t.profitAndLoss and t.profitAndLoss < 0]
    
    win_rate = len(winning_trades) / len(trades) * 100 if trades else 0
    avg_win = sum(t.profitAndLoss for t in winning_trades) / len(winning_trades) if winning_trades else 0
    avg_loss = sum(t.profitAndLoss for t in losing_trades) / len(losing_trades) if losing_trades else 0
    
    print(f"\n📊 30-Day Performance:")
    print(f"   Total P&L: ${total_pnl:.2f}")
    print(f"   Total Trades: {len(trades)}")
    print(f"   Win Rate: {win_rate:.1f}%")
    print(f"   Avg Win: ${avg_win:.2f}")
    print(f"   Avg Loss: ${avg_loss:.2f}")
    print(f"   Profit Factor: {abs(avg_win/avg_loss):.2f}" if avg_loss != 0 else "   Profit Factor: N/A")

# Current positions analysis
positions = client.search_open_positions()
if positions:
    total_exposure = sum(abs(pos.size * pos.averagePrice) for pos in positions)
    print(f"\n💼 Current Positions:")
    print(f"   Open Positions: {len(positions)}")
    print(f"   Total Exposure: ${total_exposure:,.2f}")
    
    for pos in positions:
        print(f"   {pos.contractId}: {pos.size:+d} @ ${pos.averagePrice:.2f}")
```

### Risk Management Example
```python
# Implement basic risk checks before placing orders
def safe_order_placement(client, contract_id, side, size, limit_price):
    """Place order with basic risk checks"""
    
    # Get account info
    account = client.get_account_info()
    
    # Check if trading is allowed
    if not account.canTrade:
        print("❌ Trading not permitted on this account")
        return None
    
    # Get instrument details for margin calculation
    instrument = client.get_instrument_by_contract(contract_id)
    
    # Estimate order value (simplified)
    order_value = size * limit_price
    
    # Basic balance check (simplified - doesn't account for margins)
    if order_value > account.balance * 0.1:  # Max 10% of balance per trade
        print(f"❌ Order size too large: ${order_value:.2f} > 10% of balance")
        return None
    
    # Check existing exposure
    positions = client.search_open_positions()
    existing_contracts = [pos.contractId for pos in positions]
    
    if contract_id in existing_contracts:
        print(f"⚠️  Warning: Already have position in {contract_id}")
    
    # Place the order
    try:
        response = client.place_limit_order(contract_id, side, size, limit_price)
        if response.success:
            print(f"✅ Order placed: {response.orderId}")
            return response.orderId
        else:
            print(f"❌ Order failed: {response.errorMessage}")
            return None
    except Exception as e:
        print(f"❌ Order error: {e}")
        return None

# Example usage
instrument = client.get_instrument("MGC")
contract_id = instrument.activeContract
order_id = safe_order_placement(client, contract_id, 0, 1, 2000.0)
```

## 🔧 Configuration

### Environment Variables
| Variable | Description | Required |
|----------|-------------|----------|
| `PROJECT_X_API_KEY` | TopStepX API key | ✅ |
| `PROJECT_X_USERNAME` | TopStepX username | ✅ |
| `PROJECTX_API_URL` | Custom API URL | ❌ |
| `PROJECTX_TIMEOUT_SECONDS` | Request timeout | ❌ |
| `PROJECTX_RETRY_ATTEMPTS` | Retry attempts | ❌ |

### Configuration File
Create `~/.config/projectx/config.json`:
```json
{
  "api_url": "https://api.topstepx.com/api",
  "timezone": "America/Chicago",
  "timeout_seconds": 30,
  "retry_attempts": 3,
  "requests_per_minute": 60
}
```

## 🔄 Real-Time Features

### WebSocket Connections
```python
from project_x_py import ProjectXRealtimeClient

# Create real-time client
jwt_token = client.get_session_token()
realtime = ProjectXRealtimeClient(jwt_token, account_id)

# Connect to real-time hubs
if realtime.connect():
    print("Connected to real-time data")
    
    # Subscribe to updates
    realtime.subscribe_user_updates()
    realtime.subscribe_market_data(["CON.F.US.MGC.M25"])

# Add event callbacks
def on_position_update(data):
    print(f"Position update: {data}")

def on_order_fill(data):
    print(f"Order filled: {data}")

realtime.add_callback("position_update", on_position_update)
realtime.add_callback("order_filled", on_order_fill)
```

### Multi-Timeframe Data
```python
# Get synchronized data across timeframes
mtf_data = data_manager.get_mtf_data([
    "1min", "5min", "15min", "1hr"
])

for timeframe, df in mtf_data.items():
    print(f"{timeframe}: {len(df)} bars")
    latest = df.tail(1)
    print(f"Latest {timeframe} close: ${latest['close'].item()}")
```

### Configuration Management
```python
from project_x_py import ProjectXConfig, ConfigManager

# Create custom configuration
config = ProjectXConfig(
    api_url="https://api.topstepx.com/api",
    timeout_seconds=60,
    retry_attempts=5,
    requests_per_minute=30
)

# Use with client
client = ProjectX.from_env(config=config)

# Save configuration to file
manager = ConfigManager()
manager.save_config(config, "my_trading_config.json")

# Load from file later
client = ProjectX.from_config_file("my_trading_config.json")

# Environment-based configuration
import os
os.environ['PROJECTX_TIMEOUT_SECONDS'] = '45'
os.environ['PROJECTX_RETRY_ATTEMPTS'] = '3'
client = ProjectX.from_env()  # Will use environment overrides
```

## 🛠️ Development

### Setup Development Environment
```bash
git clone https://github.com/TexasCoding/project-x-py.git
cd project-x-py

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in development mode
pip install -e .[dev]

# Install pre-commit hooks
pre-commit install
```

### Running Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=project_x_py

# Run specific test categories
pytest -m unit
pytest -m integration
pytest -m "not slow"
```

### Code Quality
```bash
# Format code
black src/ tests/
isort src/ tests/

# Lint code
ruff check src/ tests/
mypy src/

# Run all quality checks
ruff check . && mypy src/ && pytest
```

## 📚 Documentation

### API Reference
- **[Client Documentation](docs/client.md)** - Main ProjectX client usage
- **[Real-Time Documentation](docs/realtime.md)** - WebSocket and streaming data
- **[Advanced Market Analysis Guide](docs/advanced_analysis.md)** - Market microstructure analysis features
- **[Configuration Guide](docs/configuration.md)** - Setup and configuration options
- **[Examples](examples/)** - Comprehensive usage examples
  - `advanced_market_analysis_example.py` - Complete market microstructure analysis demo
  - `orderbook_usage.py` - Level 2 orderbook analysis
  - `basic_usage.py` - Getting started with trading operations
  - `realtime_monitoring.py` - Multi-timeframe real-time data streaming

### Data Models
- **[Trading Models](docs/models.md)** - Order, Position, Trade, Account objects
- **[Market Data](docs/market_data.md)** - Instrument, OHLCV data structures
- **[Advanced Analysis Models](docs/analysis_models.md)** - Liquidity, clustering, delta analysis data structures
- **[Error Handling](docs/errors.md)** - Exception hierarchy and error codes

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Workflow
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass (`pytest`)
6. Run code quality checks (`ruff check . && mypy src/`)
7. Commit your changes (`git commit -m 'Add amazing feature'`)
8. Push to the branch (`git push origin feature/amazing-feature`)
9. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

This software is for educational and research purposes. Trading futures involves substantial risk of loss. Past performance is not indicative of future results. Use at your own risk.

## 🆘 Support

- **📖 Documentation**: [project-x-py.readthedocs.io](https://project-x-py.readthedocs.io)
- **🐛 Bug Reports**: [GitHub Issues](https://github.com/TexasCoding/project-x-py/issues)
- **💬 Discussions**: [GitHub Discussions](https://github.com/TexasCoding/project-x-py/discussions)
- **📧 Email**: [jeff10278@me.com](mailto:jeff10278@me.com)

## 🔮 Development Roadmap

### ✅ Completed (v0.2.0 - Current)
- [x] **Core Trading API** - Complete order management (market, limit, stop, bracket orders)
- [x] **Account Management** - Balance monitoring, permissions, account details
- [x] **Historical Market Data** - OHLCV data with multiple timeframes (1min to 1day)
- [x] **Position Management** - Real-time position tracking and P&L calculations
- [x] **Trade History** - Comprehensive trade search and analysis
- [x] **Real-Time WebSocket** - Live order updates and market data streaming
- [x] **Professional Architecture** - Type safety, error handling, configuration management
- [x] **Comprehensive Documentation** - Full API docs, examples, and guides

### 🚧 In Active Development (v0.3.0 - Target: Q2 2025)
- [ ] **Level 2 Orderbook Processing** - Full market depth analysis and visualization
- [ ] **Advanced Order Flow Analysis** - Buy/sell pressure detection and trade flow metrics
- [ ] **Iceberg Order Detection** - Hidden institutional order identification algorithms
- [ ] **Volume Profile Analysis** - Point of Control and Value Area calculations
- [ ] **Market Imbalance Detection** - Real-time imbalance monitoring and alerts
- [ ] **Dynamic Support/Resistance** - Algorithmic level identification from market structure
- [ ] **Liquidity Analysis** - Significant price level detection with volume concentration

### 📋 Planned Features (v0.4.0+)
- [ ] **Smart Money Flow Analysis** - Institutional vs retail flow detection
- [ ] **Market Regime Detection** - Automated market condition classification
- [ ] **Strategy Development Framework** - Built-in tools for systematic trading
- [ ] **Advanced Backtesting Engine** - Historical testing with tick-level precision
- [ ] **Risk Management Suite** - Portfolio analytics and risk monitoring
- [ ] **Machine Learning Integration** - Pattern recognition and predictive analytics
- [ ] **Professional Dashboard** - Web-based interface for monitoring and analysis

### 📊 Release Timeline
- **v0.2.x** (Current) - Bug fixes and stability improvements
- **v0.3.0** (Q2 2025) - Advanced market microstructure analysis
- **v0.4.0** (Q4 2025) - Strategy framework and backtesting
- **v1.0.0** (2026) - Production-ready institutional platform

### 🏗️ Contributing to Development
- 📋 View current progress in [GitHub Issues](https://github.com/TexasCoding/project-x-py/issues)
- 💬 Discuss features in [GitHub Discussions](https://github.com/TexasCoding/project-x-py/discussions)
- 🔧 Submit PRs for bug fixes and improvements
- 📧 Contact maintainer for major feature collaboration

---

<div align="center">

**Built with ❤️ for professional traders and institutions**

[⭐ Star us on GitHub](https://github.com/TexasCoding/project-x-py) • [📖 Read the Docs](https://project-x-py.readthedocs.io) • [🐛 Report Issues](https://github.com/TexasCoding/project-x-py/issues)

*"Professional-grade market microstructure analysis at your fingertips"*

</div>
