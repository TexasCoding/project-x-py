# ProjectX Python Client

[![Python Version](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A **professional Python client** for the TopStepX ProjectX Gateway API, designed for institutional traders and quantitative analysts. This library provides comprehensive access to futures trading operations, historical market data, real-time streaming, and a complete technical analysis suite.

## 📊 Project Status

**Current Version**: v0.2.0 (Active Development)

✅ **Production Ready**:
- Complete futures trading API integration (orders, positions, trades)
- Historical market data with multiple timeframes
- Account management and authentication
- Real-time WebSocket connections
- Order and position management with error handling
- Professional-grade code with full type hints
- **🎯 NEW: Comprehensive Technical Indicators Library (25+ indicators)**
- **📊 TA-Lib Compatible Interface with Polars DataFrames**
- **🧊 Institutional-Grade Level 2 Orderbook & Market Microstructure Analysis**
- **📈 Advanced Portfolio and Risk Analysis Tools**

🔮 **Planned Features** (v0.3.0+):
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

### 🎯 Technical Analysis Library (Production Ready)
#### **Comprehensive Indicators Suite - TA-Lib Compatible**
- **📈 Overlap Studies** - SMA, EMA, BBANDS, DEMA, TEMA, WMA, MIDPOINT
- **⚡ Momentum Indicators** - RSI, MACD, STOCH, WILLR, CCI, ROC, MOM, STOCHRSI  
- **📊 Volatility Indicators** - ATR, ADX, NATR, TRANGE, ULTOSC
- **📦 Volume Indicators** - OBV, VWAP, AD, ADOSC
- **🔧 Dual Interface** - Class-based and function-based (TA-Lib style)
- **⚡ Polars-Native** - Built specifically for Polars DataFrames
- **📚 Discovery Tools** - Get available indicators, groups, and descriptions

### 📊 Advanced Market Microstructure (Production Ready)
#### **Institutional-Grade Level 2 Orderbook Analysis**
- **🎯 Level 2 Orderbook** - Full market depth processing and visualization
- **📊 Order Flow Analysis** - Buy/sell pressure detection and trade flow metrics
- **🧊 Iceberg Detection** - Hidden order identification algorithms (simplified & advanced)
- **📈 Volume Profile** - Market structure analysis with POC and value areas
- **⚖️ Market Imbalance** - Real-time imbalance detection and alerts
- **🏗️ Support/Resistance** - Dynamic level identification from order flow
- **💧 Liquidity Analysis** - Significant price level detection with volume concentration
- **🔄 Cumulative Delta** - Net buying/selling pressure tracking
- **🎯 Order Clustering** - Price level grouping and institutional flow detection

### 🛠️ Professional Quality
- **🔧 Production Architecture** - Modular design with comprehensive error handling
- **📝 Full Type Safety** - Complete type hints for IDE support and code quality
- **⚙️ Flexible Configuration** - Environment variables, config files, and runtime options
- **🔍 Comprehensive Logging** - Structured logging for debugging and monitoring
- **🧪 Testing Framework** - Unit and integration tests for reliability
- **🎨 Code Quality** - Black formatting, Ruff linting, and MyPy type checking

### 📊 Analysis & Utilities (Production Ready)
- **📈 Portfolio Analytics** - Performance metrics, Sharpe ratio, max drawdown
- **⚖️ Risk Management** - Position sizing, risk/reward ratios, volatility metrics
- **📊 Statistical Analysis** - Correlation matrices, pattern recognition
- **🕯️ Candlestick Patterns** - Doji, hammer, shooting star detection
- **💰 Trading Utilities** - Tick calculations, market hours, data snapshots



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

### 3. Technical Analysis with Indicators
```python
from project_x_py.indicators import RSI, SMA, MACD, BBANDS

# Get historical data
data = client.get_data("MGC", days=30, interval=60)  # 30 days, 1-hour bars

# Class-based interface
rsi = RSI()
sma = SMA()
macd = MACD()

data_with_indicators = (
    data
    .pipe(rsi.calculate, period=14)
    .pipe(sma.calculate, period=20)
    .pipe(sma.calculate, period=50)  # Add 50-period SMA
    .pipe(macd.calculate, fast_period=12, slow_period=26)
)

# Check latest values
latest = data_with_indicators.tail(1)
print(f"RSI(14): {latest['rsi_14'].item():.2f}")
print(f"SMA(20): ${latest['sma_20'].item():.2f}")
print(f"SMA(50): ${latest['sma_50'].item():.2f}")
print(f"MACD: {latest['macd'].item():.4f}")
print(f"MACD Signal: {latest['macd_signal'].item():.4f}")

# TA-Lib style functions (direct usage)
from project_x_py.indicators import RSI, SMA, BBANDS

data = RSI(data, period=14)  # Add RSI
data = SMA(data, period=20)  # Add 20-period SMA
data = BBANDS(data, period=20, std_dev=2.0)  # Add Bollinger Bands

# Discover available indicators
from project_x_py.indicators import get_all_indicators, get_indicator_groups

print("Available indicators:", get_all_indicators())
print("Indicator groups:", get_indicator_groups())
```

### 4. Advanced Technical Analysis
```python
import polars as pl
from project_x_py.indicators import *

# Multi-timeframe analysis
data_1h = client.get_data("MGC", days=30, interval=60)   # 1-hour
data_4h = client.get_data("MGC", days=120, interval=240) # 4-hour

# Add comprehensive indicators
analysis_1h = (
    data_1h
    .pipe(RSI, period=14)
    .pipe(MACD, fast_period=12, slow_period=26, signal_period=9)
    .pipe(BBANDS, period=20, std_dev=2.0)
    .pipe(ATR, period=14)
    .pipe(ADX, period=14)
)

analysis_4h = (
    data_4h
    .pipe(SMA, period=20)
    .pipe(SMA, period=50)
    .pipe(EMA, period=21)
    .pipe(STOCH, k_period=14, d_period=3)
    .pipe(WILLR, period=14)
)

# Trading signal logic
latest_1h = analysis_1h.tail(1)
latest_4h = analysis_4h.tail(1)

# Example: Bullish setup detection
rsi = latest_1h['rsi_14'].item()
macd_hist = latest_1h['macd_histogram'].item()
price = latest_1h['close'].item()
bb_upper = latest_1h['bb_upper_20'].item()
atr = latest_1h['atr_14'].item()

# 4H trend filter
sma_20_4h = latest_4h['sma_20'].item()
sma_50_4h = latest_4h['sma_50'].item()
trend_bullish = sma_20_4h > sma_50_4h

if (30 <= rsi <= 70 and           # RSI in normal range
    macd_hist > 0 and             # MACD bullish momentum
    price < bb_upper and          # Not overbought
    trend_bullish):               # 4H uptrend
    
    print(f"🎯 BULLISH SETUP DETECTED:")
    print(f"   Price: ${price:.2f}")
    print(f"   RSI: {rsi:.1f}")
    print(f"   MACD Histogram: {macd_hist:.4f}")
    print(f"   ATR: {atr:.2f}")
    print(f"   4H Trend: {'✅ Bullish' if trend_bullish else '❌ Bearish'}")
```

### 5. Portfolio Analysis & Risk Management
```python
from project_x_py import (
    calculate_portfolio_metrics,
    calculate_position_sizing,
    calculate_volatility_metrics,
    calculate_sharpe_ratio
)

# Get recent trades for analysis
from datetime import datetime, timedelta
end_date = datetime.now()
start_date = end_date - timedelta(days=30)
trades = client.search_trades(start_date)

# Portfolio performance analysis
if trades:
    trade_list = [{"pnl": t.profitAndLoss, "timestamp": t.timestamp} for t in trades]
    portfolio_metrics = calculate_portfolio_metrics(trade_list, initial_balance=50000)
    
    print(f"📊 30-Day Portfolio Performance:")
    print(f"   Total P&L: ${portfolio_metrics['total_pnl']:.2f}")
    print(f"   Win Rate: {portfolio_metrics['win_rate']:.1%}")
    print(f"   Profit Factor: {portfolio_metrics['profit_factor']:.2f}")
    print(f"   Max Drawdown: {portfolio_metrics['max_drawdown']:.2%}")

# Risk management for new trades
account = client.get_account_info()
entry_price = 2050.0
stop_loss = 2040.0

position_sizing = calculate_position_sizing(
    account_balance=account.balance,
    risk_per_trade=0.02,  # 2% risk per trade
    entry_price=entry_price,
    stop_loss_price=stop_loss,
    tick_value=1.0
)

print(f"💰 Position Sizing Analysis:")
print(f"   Recommended Size: {position_sizing['position_size']} contracts")
print(f"   Dollar Risk: ${position_sizing['actual_dollar_risk']:.2f}")
print(f"   Risk Percentage: {position_sizing['actual_risk_percent']:.2%}")

# Volatility analysis
vol_metrics = calculate_volatility_metrics(data, price_column="close")
print(f"📈 Volatility Analysis:")
print(f"   Daily Volatility: {vol_metrics['volatility']:.2%}")
print(f"   Annualized Volatility: {vol_metrics['annualized_volatility']:.2%}")
```

### 6. Real-Time Data Streaming
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
    instrument = client.get_instrument("MGC")
    contract_id = instrument.activeContract
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

### 7. Advanced Market Microstructure Analysis
```python
from project_x_py import OrderBook

# Initialize Level 2 orderbook
orderbook = OrderBook("MGC")

# Process real-time market depth data (from WebSocket feed)
def on_market_depth(data):
    orderbook.process_market_depth(data)

# Add callback to realtime client
realtime.add_callback("market_depth", on_market_depth)

# Get comprehensive market analysis
advanced_metrics = orderbook.get_advanced_market_metrics()

# Check for institutional iceberg orders
icebergs = advanced_metrics["iceberg_detection"]
print(f"🧊 Detected {len(icebergs['potential_icebergs'])} potential icebergs")

# Analyze market imbalance
imbalance = advanced_metrics["market_imbalance"]
print(f"⚖️ Market direction: {imbalance['direction']} (confidence: {imbalance['confidence']})")

# Get volume profile with POC
volume_profile = advanced_metrics["volume_profile"]
poc = volume_profile["poc"]
if poc:
    print(f"📊 Point of Control: ${poc['price']:.2f} with {poc['volume']} volume")

# Dynamic support/resistance levels
sr_levels = advanced_metrics["support_resistance"]
print(f"🏗️ Found {len(sr_levels['support_levels'])} support levels")
print(f"🚧 Found {len(sr_levels['resistance_levels'])} resistance levels")

# Order flow analysis
trade_flow = advanced_metrics["trade_flow"]
print(f"📈 Buy Volume: {trade_flow['buy_volume']:,}")
print(f"📉 Sell Volume: {trade_flow['sell_volume']:,}")

# Liquidity analysis
liquidity = advanced_metrics["liquidity_analysis"]
print(f"💧 Significant bid levels: {len(liquidity['bid_liquidity'])}")
print(f"💧 Significant ask levels: {len(liquidity['ask_liquidity'])}")
```

## 🎯 Technical Indicators Reference

### Overlap Studies (Trend Following)
```python
from project_x_py.indicators import SMA, EMA, BBANDS, DEMA, TEMA, WMA, MIDPOINT

# Simple Moving Average
data = SMA(data, period=20)

# Exponential Moving Average  
data = EMA(data, period=21)

# Bollinger Bands
data = BBANDS(data, period=20, std_dev=2.0)

# Double Exponential Moving Average
data = DEMA(data, period=20)

# Triple Exponential Moving Average
data = TEMA(data, period=20)

# Weighted Moving Average
data = WMA(data, period=20)

# Midpoint over period
data = MIDPOINT(data, period=14)
```

### Momentum Indicators
```python
from project_x_py.indicators import RSI, MACD, STOCH, WILLR, CCI, ROC, MOM, STOCHRSI

# Relative Strength Index
data = RSI(data, period=14)

# MACD
data = MACD(data, fast_period=12, slow_period=26, signal_period=9)

# Stochastic Oscillator
data = STOCH(data, k_period=14, d_period=3)

# Williams %R
data = WILLR(data, period=14)

# Commodity Channel Index
data = CCI(data, period=20)

# Rate of Change
data = ROC(data, period=10)

# Momentum
data = MOM(data, period=10)

# Stochastic RSI
data = STOCHRSI(data, rsi_period=14, stoch_period=14, k_period=3, d_period=3)
```

### Volatility Indicators
```python
from project_x_py.indicators import ATR, ADX, NATR, TRANGE, ULTOSC

# Average True Range
data = ATR(data, period=14)

# Average Directional Index
data = ADX(data, period=14)

# Normalized Average True Range
data = NATR(data, period=14)

# True Range
data = TRANGE(data)

# Ultimate Oscillator
data = ULTOSC(data, period1=7, period2=14, period3=28)
```

### Volume Indicators
```python
from project_x_py.indicators import OBV, VWAP, AD, ADOSC

# On-Balance Volume
data = OBV(data)

# Volume Weighted Average Price
data = VWAP(data, period=20)  # Rolling VWAP
data = VWAP(data)             # Cumulative VWAP

# Accumulation/Distribution Line
data = AD(data)

# A/D Oscillator
data = ADOSC(data, fast_period=3, slow_period=10)
```

## 📖 Working Examples

### Multi-Indicator Strategy
```python
import polars as pl
from project_x_py.indicators import *

# Load data
data = client.get_data("MGC", days=60, interval=60)  # 60 days, 1-hour

# Comprehensive technical analysis
analysis = (
    data
    # Trend indicators
    .pipe(SMA, period=20)
    .pipe(SMA, period=50) 
    .pipe(EMA, period=21)
    .pipe(BBANDS, period=20, std_dev=2.0)
    
    # Momentum indicators
    .pipe(RSI, period=14)
    .pipe(MACD, fast_period=12, slow_period=26, signal_period=9)
    .pipe(STOCH, k_period=14, d_period=3)
    
    # Volatility indicators
    .pipe(ATR, period=14)
    .pipe(ADX, period=14)
    
    # Volume indicators
    .pipe(OBV)
    .pipe(VWAP, period=20)
)

# Trading signal generation
latest = analysis.tail(1)

# Extract signals
price = latest['close'].item()
sma_20 = latest['sma_20'].item()
sma_50 = latest['sma_50'].item()
rsi = latest['rsi_14'].item()
macd_hist = latest['macd_histogram'].item()
atr = latest['atr_14'].item()
adx = latest['adx_14'].item()

# Signal logic
trend_up = sma_20 > sma_50
momentum_bullish = rsi > 50 and macd_hist > 0
trending_market = adx > 25

if trend_up and momentum_bullish and trending_market:
    print(f"🟢 BULLISH SIGNAL")
    print(f"   Entry: ${price:.2f}")
    print(f"   Stop: ${price - (2 * atr):.2f}")  # 2x ATR stop
    print(f"   Target: ${price + (3 * atr):.2f}")  # 3x ATR target
elif not trend_up and not momentum_bullish and trending_market:
    print(f"🔴 BEARISH SIGNAL")
    print(f"   Entry: ${price:.2f}")
    print(f"   Stop: ${price + (2 * atr):.2f}")
    print(f"   Target: ${price - (3 * atr):.2f}")
else:
    print(f"⚪ NO CLEAR SIGNAL - Market consolidating")
```

### Custom Indicator Discovery
```python
from project_x_py.indicators import *

# Discover all available indicators
all_indicators = get_all_indicators()
print(f"Total indicators available: {len(all_indicators)}")

# Get indicators by category
groups = get_indicator_groups()
for category, indicators in groups.items():
    print(f"\n{category.upper()} ({len(indicators)} indicators):")
    for indicator in indicators:
        description = get_indicator_info(indicator)
        print(f"  {indicator}: {description}")

# Example output:
# OVERLAP (7 indicators):
#   SMA: Simple Moving Average - arithmetic mean of prices over a period
#   EMA: Exponential Moving Average - weighted moving average with more weight on recent prices
#   BBANDS: Bollinger Bands - moving average with upper and lower bands based on standard deviation
#   ...
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

## 📚 Documentation

### API Reference
- **[Client Documentation](docs/client.md)** - Main ProjectX client usage
- **[Indicators Documentation](docs/indicators.md)** - Technical analysis library
- **[Real-Time Documentation](docs/realtime.md)** - WebSocket and streaming data
- **[Configuration Guide](docs/configuration.md)** - Setup and configuration options
- **[Examples](examples/)** - Comprehensive usage examples

### Examples & Demos
- `basic_usage.py` - Getting started with trading operations
- `comprehensive_analysis_demo.py` - Complete technical analysis showcase
- `orderbook_usage.py` - Level 2 orderbook analysis examples
- `advanced_market_analysis_example.py` - Market microstructure demos
- `iceberg_comparison_demo.py` - Iceberg detection algorithms

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
- [x] **Technical Indicators Library** - 25+ indicators with TA-Lib compatibility
- [x] **Level 2 Orderbook Processing** - Full market depth analysis and visualization
- [x] **Advanced Order Flow Analysis** - Buy/sell pressure detection and trade flow metrics
- [x] **Iceberg Order Detection** - Hidden institutional order identification algorithms
- [x] **Volume Profile Analysis** - Point of Control and Value Area calculations
- [x] **Market Imbalance Detection** - Real-time imbalance monitoring and alerts
- [x] **Dynamic Support/Resistance** - Algorithmic level identification from market structure
- [x] **Liquidity Analysis** - Significant price level detection with volume concentration
- [x] **Portfolio Analytics** - Performance metrics, risk analysis, position sizing
- [x] **Professional Architecture** - Type safety, error handling, configuration management
- [x] **Comprehensive Documentation** - Full API docs, examples, and guides

### 🚧 In Active Development (v0.3.0 - Target: Q2 2025)
- [ ] **Machine Learning Integration** - Pattern recognition and predictive analytics
- [ ] **Advanced Backtesting Engine** - Historical testing with tick-level precision
- [ ] **Strategy Development Framework** - Built-in tools for systematic trading
- [ ] **Production Market Microstructure** - Real-time institutional-grade analysis
- [ ] **Advanced Portfolio Management** - Multi-asset correlation and risk monitoring

### 📋 Planned Features (v0.4.0+)
- [ ] **Cloud-Based Data Pipeline** - Scalable data processing infrastructure
- [ ] **Professional Dashboard** - Web-based interface for monitoring and analysis
- [ ] **Custom Indicator Framework** - User-defined technical indicators
- [ ] **API Rate Optimization** - Advanced caching and request optimization
- [ ] **Mobile Application** - iOS/Android app for portfolio monitoring

### 📊 Release Timeline
- **v0.2.x** (Current) - Technical indicators and analytics library (Complete)
- **v0.3.0** (Q2 2025) - Machine learning integration and strategy framework
- **v0.4.0** (Q4 2025) - Advanced backtesting and production microstructure
- **v1.0.0** (2026) - Production-ready institutional platform

### 🏗️ Contributing to Development
- 📋 View current progress in [GitHub Issues](https://github.com/TexasCoding/project-x-py/issues)
- 💬 Discuss features in [GitHub Discussions](https://github.com/TexasCoding/project-x-py/discussions)
- 🔧 Submit PRs for bug fixes and improvements
- 📧 Contact maintainer for major feature collaboration

---

<div align="center">

**Built with ❤️ for professional traders and quantitative analysts**

[⭐ Star us on GitHub](https://github.com/TexasCoding/project-x-py) • [📖 Read the Docs](https://project-x-py.readthedocs.io) • [🐛 Report Issues](https://github.com/TexasCoding/project-x-py/issues)

*"Professional-grade technical analysis and institutional market microstructure analysis"*

</div>
