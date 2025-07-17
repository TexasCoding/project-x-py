# ProjectX Python Client

[![Python Version](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A professional Python client for the **TopStepX ProjectX Gateway API**, providing comprehensive access to futures trading, real-time market data, Level 2 orderbook analysis, and portfolio management. Features advanced market microstructure analysis with sub-second data processing for professional trading applications.

## 🚀 Features

### Core Functionality
- **🏦 Account Management** - Balance monitoring, permissions, account info
- **📊 Market Data** - Historical OHLCV data, multiple timeframes, instrument search
- **📈 Order Management** - Place, modify, cancel orders with automatic price alignment
- **💼 Position Management** - Real-time position tracking, P&L monitoring
- **📋 Trade History** - Comprehensive trade analysis and reporting

### Real-Time Capabilities
- **⚡ WebSocket Streams** - Sub-second market data updates
- **🔄 Live Order Updates** - Instant fill notifications and status changes
- **📊 Real-Time Positions** - Live position monitoring without polling
- **📈 Multi-Timeframe Data** - Synchronized data across multiple timeframes
- **🎯 Level 2 Market Data** - Full orderbook depth with market microstructure analysis
- **📋 Order Flow Analysis** - Real-time trade execution tracking and volume analysis
- **⚖️ Market Pressure Detection** - Buy/sell pressure analysis with volume imbalance tracking
- **🔍 Advanced Order Types** - Processing of all TopStepX order types (bids, asks, trades, modifications)

### Professional Features
- **🛡️ Error Handling** - Comprehensive exception hierarchy with retry logic
- **⚙️ Configuration Management** - Environment variables, config files, defaults
- **📝 Full Type Hints** - Complete typing support for better IDE experience
- **🔧 Rate Limiting** - Built-in API rate limiting and request management
- **📚 Extensive Logging** - Structured logging for debugging and monitoring

## 📦 Installation

### Basic Installation
```bash
pip install project-x-py
```

### With Real-Time Features
```bash
pip install project-x-py[realtime]
```

### Development Installation
```bash
pip install project-x-py[dev]
```

### All Features
```bash
pip install project-x-py[all]
```

## ⚡ Quick Start

### 1. Environment Setup
```bash
export PROJECT_X_API_KEY="your_api_key_here"
export PROJECT_X_USERNAME="your_username_here"
```

### 2. Basic Usage
```python
from project_x_py import ProjectX

# Create client using environment variables
client = ProjectX.from_env()

# Search for instruments
instruments = client.search_instruments("MGC")
print(f"Found {len(instruments)} MGC instruments")

# Get historical data
data = client.get_data("MGC", days=5, interval=15)
print(f"Retrieved {len(data)} bars")

# Check positions
positions = client.search_open_positions()
for pos in positions:
    print(f"{pos.contractId}: {pos.size} @ ${pos.averagePrice}")
```

### 3. Real-Time Data
```python
from project_x_py import ProjectX, ProjectXRealtimeDataManager

# Set up real-time data manager
client = ProjectX.from_env()
account = client.get_account_info()

data_manager = ProjectXRealtimeDataManager(
    instrument="MGC",
    project_x=client,
    account_id=str(account.id)
)

# Initialize with historical data
data_manager.initialize(initial_days=30)

# Start real-time feed
jwt_token = client.get_session_token()
data_manager.start_realtime_feed(jwt_token)

# Access real-time data
current_price = data_manager.get_current_price()
data_5m = data_manager.get_data("5min", bars=100)
mtf_data = data_manager.get_mtf_data()
```

## 📖 Examples

### Level 2 Orderbook Analysis
```python
# See examples/orderbook_usage.py for complete implementation
from project_x_py import ProjectX, ProjectXRealtimeDataManager

# Initialize and start real-time orderbook monitoring
client = ProjectX.from_env()
account = client.get_account_info()

manager = ProjectXRealtimeDataManager("MNQ", client, str(account.id))
manager.initialize()

jwt_token = client.get_session_token()
manager.start_realtime_feed(jwt_token)

# Monitor orderbook for insights
for i in range(30):
    best = manager.get_best_bid_ask()
    depth = manager.get_orderbook_depth(price_range=20.0)
    
    if best['spread'] and best['spread'] > 2.0:
        print(f"Wide spread detected: ${best['spread']:.2f}")
    
    # Check for volume imbalance
    total_vol = depth['bid_volume'] + depth['ask_volume']
    if total_vol > 0:
        imbalance = abs(depth['bid_volume'] - depth['ask_volume']) / total_vol
        if imbalance > 0.3:  # 30% imbalance
            side = "BUY" if depth['bid_volume'] > depth['ask_volume'] else "SELL"
            print(f"Volume imbalance: {imbalance:.1%} favoring {side}")
    
    time.sleep(1)
```

### Order Management
```python
# Place a market order
response = client.place_market_order("CON.F.US.MGC.M25", side=0, size=1)
if response.success:
    print(f"Order placed: {response.orderId}")

# Place a limit order
response = client.place_limit_order(
    contract_id="CON.F.US.MGC.M25",
    side=1,  # Sell
    size=1,
    limit_price=2050.0
)

# Check open orders
open_orders = client.search_open_orders()
for order in open_orders:
    print(f"Order {order.id}: {order.contractId} - Status: {order.status}")
```

### Account Information
```python
# Get account details
account = client.get_account_info()
print(f"Account: {account.name}")
print(f"Balance: ${account.balance:,.2f}")
print(f"Can Trade: {account.canTrade}")

# Get trade history
from datetime import datetime, timedelta
start_date = datetime.now() - timedelta(days=7)
trades = client.search_trades(start_date)

total_pnl = sum(t.profitAndLoss for t in trades if t.profitAndLoss)
print(f"7-day P&L: ${total_pnl:.2f}")
```

### Configuration
```python
from project_x_py import ProjectXConfig, ConfigManager

# Create custom configuration
config = ProjectXConfig(
    timeout_seconds=60,
    retry_attempts=5,
    requests_per_minute=30
)

# Use with client
client = ProjectX.from_env(config=config)

# Save configuration to file
manager = ConfigManager()
manager.save_config(config, "my_config.json")

# Load from file
client = ProjectX.from_config_file("my_config.json")
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

### Level 2 Orderbook & Market Microstructure
```python
# Access real-time Level 2 orderbook data
best_prices = data_manager.get_best_bid_ask()
print(f"Best Bid: ${best_prices['bid']:.2f}")
print(f"Best Ask: ${best_prices['ask']:.2f}")
print(f"Spread: ${best_prices['spread']:.2f}")

# Get orderbook depth (Polars DataFrames)
bids = data_manager.get_orderbook_bids(levels=10)
asks = data_manager.get_orderbook_asks(levels=10)

print("Top 5 Bid Levels:")
for row in bids.head(5).iter_rows():
    price, volume, timestamp, order_type = row
    print(f"  ${price:.2f} | {volume:4d} contracts")

# Analyze orderbook depth within price range
depth = data_manager.get_orderbook_depth(price_range=20.0)
print(f"Volume within ±$20: {depth['bid_volume']} bids, {depth['ask_volume']} asks")

# Get complete orderbook snapshot
snapshot = data_manager.get_orderbook_snapshot(levels=20)
metadata = snapshot['metadata']
print(f"Mid Price: ${metadata['mid_price']:.2f}")
print(f"Volume Imbalance: {metadata['total_bid_volume']} vs {metadata['total_ask_volume']}")
```

### Trade Flow & Order Flow Analysis
```python
# Analyze recent trade executions (Type 5 data)
recent_trades = data_manager.get_recent_trades(count=50)
print(f"Recent trades: {len(recent_trades)} executions")

# Get trade flow summary with buy/sell pressure
trade_flow = data_manager.get_trade_flow_summary(minutes=5)
print(f"5-min Volume: {trade_flow['total_volume']:,} contracts")
print(f"Buy Volume: {trade_flow['buy_volume']:,} ({trade_flow['buy_trades']} trades)")
print(f"Sell Volume: {trade_flow['sell_volume']:,} ({trade_flow['sell_trades']} trades)")
print(f"Buy/Sell Ratio: {trade_flow['buy_sell_ratio']:.2f}")
print(f"VWAP: ${trade_flow['vwap']:.2f}")

# Monitor order type statistics
order_stats = data_manager.get_order_type_statistics()
print(f"Bid Updates: {order_stats['type_2_count']}")
print(f"Ask Updates: {order_stats['type_1_count']}")
print(f"Trade Executions: {order_stats['type_5_count']}")
print(f"Order Modifications: {order_stats['type_9_count'] + order_stats['type_10_count']}")

# Clear trade history for fresh monitoring periods
data_manager.clear_recent_trades()
```

### Real-Time Market Monitoring Example
```python
import time
from datetime import datetime

# Start clean monitoring period
monitoring_start = datetime.now(data_manager.timezone)
data_manager.clear_recent_trades()

print("🔍 Monitoring market microstructure...")
for i in range(60):  # Monitor for 60 seconds
    time.sleep(1)
    
    # Get current market state
    best = data_manager.get_best_bid_ask()
    depth = data_manager.get_orderbook_depth(price_range=10.0)
    
    # Calculate volume imbalance
    total_volume = depth['bid_volume'] + depth['ask_volume']
    if total_volume > 0:
        bid_ratio = depth['bid_volume'] / total_volume * 100
        ask_ratio = depth['ask_volume'] / total_volume * 100
    else:
        bid_ratio = ask_ratio = 0
    
    print(f"[{i+1:2d}s] Mid: ${best['mid']:.2f} | "
          f"Spread: ${best['spread']:.2f} | "
          f"Imbalance: {bid_ratio:.1f}% bids / {ask_ratio:.1f}% asks")
    
    # Alert on significant imbalance
    if bid_ratio > 70:
        print("    🟢 Strong buying pressure detected!")
    elif ask_ratio > 70:
        print("    🔴 Strong selling pressure detected!")

# Final trade flow analysis for monitoring period
final_flow = data_manager.get_trade_flow_summary(minutes=1)
print(f"\n📊 60-second Summary:")
print(f"   Total Volume: {final_flow['total_volume']:,} contracts")
print(f"   Trade Rate: {final_flow['total_volume']/60:.1f} contracts/second")
print(f"   Buy/Sell Pressure: {final_flow['buy_sell_ratio']:.2f}")
```

## 🛠️ Development

### Setup Development Environment
```bash
git clone https://github.com/jeffwest87/project-x-py.git
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
- **[Configuration Guide](docs/configuration.md)** - Setup and configuration options
- **[Examples](examples/)** - Comprehensive usage examples
  - `orderbook_usage.py` - Complete Level 2 orderbook analysis demo
  - `basic_usage.py` - Getting started with trading operations
  - `realtime_monitoring.py` - Multi-timeframe real-time data streaming

### Data Models
- **[Trading Models](docs/models.md)** - Order, Position, Trade, Account objects
- **[Market Data](docs/market_data.md)** - Instrument, OHLCV data structures
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
- **🐛 Bug Reports**: [GitHub Issues](https://github.com/jeffwest87/project-x-py/issues)
- **💬 Discussions**: [GitHub Discussions](https://github.com/jeffwest87/project-x-py/discussions)
- **📧 Email**: [jeff10278@me.com](mailto:jeff10278@me.com)

## 🔮 Roadmap

### Recently Completed ✅
- [x] **Level 2 Market Data** - Complete orderbook depth and market microstructure analysis
- [x] **Order Flow Analysis** - Real-time trade execution tracking with buy/sell pressure detection
- [x] **Advanced Order Types** - Full processing of TopStepX order types (bids, asks, trades, modifications)
- [x] **Market Pressure Detection** - Volume imbalance tracking and market sentiment analysis

### Upcoming Features
- [ ] **Strategy Framework** - Built-in strategy development tools with Level 2 data integration
- [ ] **Advanced Orderbook Analytics** - Iceberg order detection, smart money analysis
- [ ] **Market Regime Detection** - Automated detection of trending vs ranging markets
- [ ] **Backtesting Engine** - Historical strategy testing with tick-level precision
- [ ] **Paper Trading** - Risk-free strategy validation with real-time orderbook simulation
- [ ] **Volume Profile Analysis** - Time & Sales analysis with volume clustering
- [ ] **Advanced Analytics** - Portfolio performance metrics with market microstructure insights
- [ ] **Web Dashboard** - Browser-based monitoring interface with real-time orderbook visualization
- [ ] **Risk Management** - Position sizing and risk controls with market depth consideration

### Version History
- **v0.3.0** - Level 2 orderbook, advanced market microstructure analysis, trade flow monitoring
- **v0.2.0** - Modular architecture, improved error handling, real-time enhancements  
- **v0.1.0** - Initial release with basic trading functionality

---

<div align="center">

**Built with ❤️ for the futures trading community**

[⭐ Star us on GitHub](https://github.com/jeffwest87/project-x-py) • [📖 Read the Docs](https://project-x-py.readthedocs.io) • [🐛 Report Issues](https://github.com/jeffwest87/project-x-py/issues)

</div>
