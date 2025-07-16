# ProjectX Python Client

[![Python Version](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A professional Python client for the **TopStepX ProjectX Gateway API**, providing comprehensive access to futures trading, real-time market data, and portfolio management.

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
- **🎯 Level 2 Market Data** - Order book depth and market microstructure

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

### Upcoming Features
- [ ] **Strategy Framework** - Built-in strategy development tools
- [ ] **Backtesting Engine** - Historical strategy testing
- [ ] **Paper Trading** - Risk-free strategy validation
- [ ] **Advanced Analytics** - Portfolio performance metrics
- [ ] **Web Dashboard** - Browser-based monitoring interface
- [ ] **Risk Management** - Position sizing and risk controls

### Version History
- **v0.2.0** - Modular architecture, improved error handling, real-time enhancements
- **v0.1.0** - Initial release with basic trading functionality

---

<div align="center">

**Built with ❤️ for the futures trading community**

[⭐ Star us on GitHub](https://github.com/jeffwest87/project-x-py) • [📖 Read the Docs](https://project-x-py.readthedocs.io) • [🐛 Report Issues](https://github.com/jeffwest87/project-x-py/issues)

</div>
