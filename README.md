# ProjectX Python Client

[![Python Version](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A professional Python client for the **TopStepX ProjectX Gateway API**, providing comprehensive access to futures trading, real-time market data, Level 2 orderbook analysis, and **advanced market microstructure analysis**. Features institutional-grade order flow detection, hidden liquidity identification, and professional market intelligence tools used by trading desks worldwide.

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

### 🎯 Advanced Market Microstructure Analysis
- **💧 Liquidity Levels Detection** - Identify significant price levels with substantial volume and liquidity scoring
- **🎯 Order Cluster Analysis** - Detect groups of orders at similar prices with volume-weighted clustering
- **🧊 Iceberg Order Detection** - Spot hidden institutional orders with confidence scoring and size estimation
- **📊 Cumulative Delta Analysis** - Real-time net buying vs selling pressure tracking with momentum detection
- **⚖️ Market Imbalance Monitoring** - Orderbook and trade flow imbalance detection with directional bias analysis
- **📈 Volume Profile Analysis** - Point of Control (POC) identification and Value Area calculation
- **🏗️ Dynamic Support/Resistance** - Real-time level detection from orderbook and volume data with strength scoring
- **🎪 Market Maker Detection** - Identify professional trading activity and institutional flow patterns
- **📊 Complete Market Intelligence** - Comprehensive analysis combining all microstructure metrics

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

### 3. Real-Time Data with Advanced Analysis
```python
from project_x_py import ProjectX, ProjectXRealtimeDataManager

# Set up real-time data manager
client = ProjectX.from_env()
account = client.get_account_info()

data_manager = ProjectXRealtimeDataManager(
    instrument="MNQ",  # E-mini NASDAQ futures
    project_x=client,
    account_id=str(account.id)
)

# Initialize with historical data
data_manager.initialize(initial_days=30)

# Start real-time feed
jwt_token = client.get_session_token()
data_manager.start_realtime_feed(jwt_token)

# Access advanced market microstructure analysis
liquidity = data_manager.get_liquidity_levels(min_volume=200)
icebergs = data_manager.detect_iceberg_orders()
delta = data_manager.get_cumulative_delta(time_window_minutes=30)
imbalance = data_manager.get_market_imbalance()

print(f"🎯 Significant liquidity levels: {len(liquidity['bid_liquidity'])}")
print(f"🧊 Potential icebergs detected: {len(icebergs['potential_icebergs'])}")
print(f"📊 Market momentum: {delta['delta_trend']} (Δ: {delta['cumulative_delta']})")
print(f"⚖️ Market bias: {imbalance['direction']} ({imbalance['confidence']} confidence)")
```

## 📖 Advanced Market Analysis Examples

### 🎯 Institutional Order Detection
```python
# Detect hidden institutional orders (iceberg detection)
icebergs = data_manager.detect_iceberg_orders(
    min_refresh_count=3,
    volume_consistency_threshold=0.8,
    time_window_minutes=10
)

if icebergs['potential_icebergs']:
    print("🚨 Large institutional orders detected:")
    for iceberg in icebergs['potential_icebergs']:
        print(f"  ${iceberg['price']:.2f} {iceberg['side'].upper()} | "
              f"Visible: {iceberg['volume']:,} | "
              f"Est. Hidden: {iceberg['estimated_hidden_size']:,}")
```

### 💧 Liquidity Analysis
```python
# Identify significant liquidity levels
liquidity = data_manager.get_liquidity_levels(
    min_volume=150,  # Minimum contracts for significance
    levels=25        # Analyze top 25 levels per side
)

print(f"📈 Significant bid levels: {len(liquidity['bid_liquidity'])}")
print(f"📉 Significant ask levels: {len(liquidity['ask_liquidity'])}")

# Show top liquidity concentrations
for level in liquidity['bid_liquidity'].head(3).to_dicts():
    print(f"  💰 ${level['price']:.2f}: {level['volume']:,} contracts "
          f"(score: {level['liquidity_score']:.2f})")
```

### 🎯 Order Cluster Detection
```python
# Detect order clustering at key price levels
clusters = data_manager.detect_order_clusters(
    price_tolerance=0.25,    # Quarter-point clustering
    min_cluster_size=3       # Minimum orders per cluster
)

if clusters['bid_clusters']:
    strongest = clusters['analysis']['strongest_bid_cluster']
    print(f"💪 Strongest bid cluster at ${strongest['center_price']:.2f}")
    print(f"   📦 Total volume: {strongest['total_volume']:,}")
    print(f"   🔢 Orders: {strongest['order_count']}")
```

### 📊 Cumulative Delta Analysis
```python
# Track net buying vs selling pressure
delta = data_manager.get_cumulative_delta(time_window_minutes=30)

print(f"📈 Cumulative Delta: {delta['cumulative_delta']:,} contracts")
print(f"📊 Trend: {delta['delta_trend'].upper()}")
print(f"💰 Buy Volume: {delta['analysis']['total_buy_volume']:,}")
print(f"💰 Sell Volume: {delta['analysis']['total_sell_volume']:,}")

# Interpret market momentum
if delta['delta_trend'] == 'strongly_bullish':
    print("🚀 Strong buying momentum - consider long bias")
elif delta['delta_trend'] == 'strongly_bearish':
    print("🐻 Strong selling momentum - consider short bias")
```

### ⚖️ Market Imbalance Detection
```python
# Analyze orderbook and trade flow imbalances
imbalance = data_manager.get_market_imbalance()

print(f"📊 Imbalance Ratio: {imbalance['imbalance_ratio']:.3f}")
print(f"🎯 Direction: {imbalance['direction'].upper()}")
print(f"🔒 Confidence: {imbalance['confidence'].upper()}")

# Get detailed metrics
ob_metrics = imbalance['orderbook_metrics']
print(f"💰 Bid Volume: {ob_metrics['top_bid_volume']:,}")
print(f"💰 Ask Volume: {ob_metrics['top_ask_volume']:,}")
print(f"📊 Ratio: {ob_metrics['bid_ask_ratio']:.2f}")
```

### 📈 Volume Profile Analysis
```python
# Create volume profile and identify key levels
profile = data_manager.get_volume_profile(price_bucket_size=0.25)

# Point of Control (POC) - highest volume price
poc = profile['poc']
print(f"🎯 Point of Control: ${poc['price']:.2f} ({poc['volume']:,} contracts)")

# Value Area (70% of volume)
va = profile['value_area']
print(f"📊 Value Area: ${va['low']:.2f} - ${va['high']:.2f}")
print(f"📊 Coverage: {va['volume_percentage']:.1f}%")
```

### 🏗️ Dynamic Support & Resistance
```python
# Identify real-time support and resistance levels
sr_levels = data_manager.get_support_resistance_levels(lookback_minutes=60)

print(f"🎯 Current Price: ${sr_levels['current_price']:.2f}")
print(f"🏗️ Support Levels: {len(sr_levels['support_levels'])}")
print(f"🚧 Resistance Levels: {len(sr_levels['resistance_levels'])}")

# Show strongest levels
if sr_levels['analysis']['strongest_support']:
    support = sr_levels['analysis']['strongest_support']
    print(f"💪 Key Support: ${support['price']:.2f} (strength: {support['strength']:.2f})")

if sr_levels['analysis']['strongest_resistance']:
    resistance = sr_levels['analysis']['strongest_resistance']
    print(f"🚧 Key Resistance: ${resistance['price']:.2f} (strength: {resistance['strength']:.2f})")
```

### 🎪 Complete Market Intelligence
```python
# Get comprehensive market analysis in one call
analysis = data_manager.get_advanced_market_metrics()

# Market condition assessment
summary = analysis['analysis_summary']
print(f"🔍 Data Quality: {summary['data_quality'].upper()}")
print(f"📈 Market Activity: {summary['market_activity'].upper()}")

# Trade flow insights
trade_flow = analysis['trade_flow']
print(f"📦 Recent Volume: {trade_flow['total_volume']:,} contracts")
print(f"⚖️ Buy/Sell Ratio: {trade_flow['buy_sell_ratio']:.2f}")
print(f"💰 VWAP: ${trade_flow['vwap']:.2f}")

# Orderbook state
ob_snapshot = analysis['orderbook_snapshot']
metadata = ob_snapshot['metadata']
print(f"💰 Best Bid: ${metadata['best_bid']:.2f}")
print(f"💰 Best Ask: ${metadata['best_ask']:.2f}")
print(f"📏 Spread: ${metadata['spread']:.2f}")
```

### 🚨 Real-Time Market Monitoring
```python
import time

# Monitor market for institutional activity
print("🔍 Monitoring for institutional activity...")

for i in range(60):  # 60-second monitoring
    # Check for iceberg orders
    icebergs = data_manager.detect_iceberg_orders()
    
    # Monitor cumulative delta
    delta = data_manager.get_cumulative_delta(time_window_minutes=5)
    
    # Check market imbalance
    imbalance = data_manager.get_market_imbalance()
    
    # Alert conditions
    if len(icebergs['potential_icebergs']) > 0:
        print(f"🧊 [{i+1:2d}s] Iceberg detected: {len(icebergs['potential_icebergs'])} orders")
    
    if abs(delta['cumulative_delta']) > 1000:
        direction = "BUY" if delta['cumulative_delta'] > 0 else "SELL"
        print(f"📊 [{i+1:2d}s] Strong {direction} pressure: Δ{delta['cumulative_delta']:,}")
    
    if imbalance['confidence'] == 'high':
        print(f"⚖️ [{i+1:2d}s] High confidence {imbalance['direction']} bias")
    
    time.sleep(1)
```

## 📖 Traditional Examples

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
- **🐛 Bug Reports**: [GitHub Issues](https://github.com/jeffwest87/project-x-py/issues)
- **💬 Discussions**: [GitHub Discussions](https://github.com/jeffwest87/project-x-py/discussions)
- **📧 Email**: [jeff10278@me.com](mailto:jeff10278@me.com)

## 🔮 Roadmap

### Recently Completed ✅
- [x] **Advanced Market Microstructure Analysis** - Complete suite of institutional-grade analysis tools
- [x] **Liquidity Level Detection** - Identify significant price levels with volume and liquidity scoring
- [x] **Order Cluster Analysis** - Detect and analyze order groupings at key price levels
- [x] **Iceberg Order Detection** - Spot hidden institutional orders with confidence scoring
- [x] **Cumulative Delta Analysis** - Real-time net buying vs selling pressure tracking
- [x] **Market Imbalance Detection** - Orderbook and trade flow imbalance analysis
- [x] **Volume Profile Analysis** - Point of Control and Value Area identification
- [x] **Dynamic Support/Resistance** - Real-time level detection from market microstructure
- [x] **Level 2 Market Data** - Complete orderbook depth and market microstructure analysis
- [x] **Order Flow Analysis** - Real-time trade execution tracking with buy/sell pressure detection
- [x] **Advanced Order Types** - Full processing of TopStepX order types (bids, asks, trades, modifications)
- [x] **Market Pressure Detection** - Volume imbalance tracking and market sentiment analysis

### Upcoming Features
- [ ] **Smart Money Flow Analysis** - Institutional vs retail flow detection and analysis
- [ ] **Market Regime Detection** - Automated detection of trending vs ranging vs volatile markets
- [ ] **Strategy Framework** - Built-in strategy development tools with Level 2 data integration
- [ ] **Advanced Risk Analytics** - Portfolio heat maps with market microstructure risk assessment
- [ ] **Backtesting Engine** - Historical strategy testing with tick-level precision and microstructure simulation
- [ ] **Paper Trading** - Risk-free strategy validation with real-time orderbook simulation
- [ ] **Time & Sales Analysis** - Advanced trade tape analysis with institutional flow detection
- [ ] **Advanced Analytics Dashboard** - Portfolio performance metrics with market microstructure insights
- [ ] **Web Dashboard** - Browser-based monitoring interface with real-time orderbook visualization
- [ ] **Machine Learning Integration** - ML-powered pattern recognition for order flow anomalies

### Version History
- **v0.3.0** - Advanced market microstructure analysis suite with professional-grade capabilities
- **v0.2.0** - Modular architecture, improved error handling, real-time enhancements  
- **v0.1.0** - Initial release with basic trading functionality

---

<div align="center">

**Built with ❤️ for professional traders and institutions**

[⭐ Star us on GitHub](https://github.com/jeffwest87/project-x-py) • [📖 Read the Docs](https://project-x-py.readthedocs.io) • [🐛 Report Issues](https://github.com/jeffwest87/project-x-py/issues)

*"Professional-grade market microstructure analysis at your fingertips"*

</div>
