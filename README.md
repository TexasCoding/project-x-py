# ProjectX Python Client

[![Python Version](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

# ProjectX Python Client

A **professional Python client** for the TopStepX ProjectX Gateway API, designed for institutional traders and quantitative analysts. This library provides comprehensive access to futures trading operations, historical market data, real-time streaming, technical analysis, and advanced market microstructure tools.

## 📊 Project Status

**Current Version**: v1.0.2 (Active Development)

✅ **Production Ready**:
- Complete futures trading API integration
- Historical and real-time market data
- Advanced technical indicators (25+)
- Institutional-grade orderbook analysis
- Portfolio and risk management tools
- Performance optimizations for large datasets

🔮 **Planned Features**:
- Machine learning integration
- Advanced backtesting
- Strategy framework

## 🚀 Key Features

### Core Trading
- Account management with multi-account support
- Order placement (market, limit, stop, bracket)
- Position tracking and P&L calculations
- Trade history and performance metrics

### Market Data
- Historical OHLCV across timeframes
- Real-time WebSocket streaming
- Tick-level data retrieval

### Technical Analysis
- TA-Lib compatible indicators
- Momentum, volatility, volume, overlap studies
- Polars DataFrame integration

### Microstructure Analysis
- Level 2 orderbook processing
- Iceberg order detection
- Volume profile and POC
- Market imbalance detection
- Support/resistance identification

### Analytics & Risk
- Portfolio performance metrics
- Risk-adjusted position sizing
- Volatility and Sharpe ratio calculations
- Candlestick pattern detection

## 📦 Installation

```bash
uv add project-x-py  # Recommended
pip install project-x-py
```

For real-time features:
```bash
uv add \"project-x-py[realtime]\"
```

## ⚡ Quick Start

```python
from project_x_py import ProjectX
client = ProjectX.from_env()
account = client.get_account_info()
print(f\"Balance: ${account.balance:,.2f}\")
data = client.get_data(\"MGC\", days=5)
print(data.tail())
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
from project_x_py.indicators import get_all_indicators, get_indicator_groups

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

We welcome contributions! Please follow these steps to contribute:

1. Fork the repository on GitHub.
2. Create a feature branch from main (`git checkout -b feature/your-feature`).
3. Make your changes and commit them with clear messages.
4. Add tests for new functionality (use pytest).
5. Run code quality checks: `ruff check .`, `mypy src/`, `black .`.
6. Push your branch and open a Pull Request.

### Adding New Indicators
To add a new technical indicator:
- Create a new class in the appropriate indicators sub-module (e.g., momentum.py).
- Inherit from the base class (e.g., MomentumIndicator).
- Implement the calculate method.
- Add to __init__.py exports and function wrapper if TA-Lib style.
- Add tests in tests/test_indicators.py.
- Update documentation in docs/indicators.md.

For major changes, open an issue first to discuss.

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

### ✅ Completed (v1.0.0+ - Current)
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

### 🚧 In Active Development (v2.0.0+ - Target: Q2 2025)
- [ ] **Machine Learning Integration** - Pattern recognition and predictive analytics
- [ ] **Advanced Backtesting Engine** - Historical testing with tick-level precision
- [ ] **Strategy Development Framework** - Built-in tools for systematic trading
- [ ] **Production Market Microstructure** - Real-time institutional-grade analysis
- [ ] **Advanced Portfolio Management** - Multi-asset correlation and risk monitoring

### 📋 Planned Features (v3.0.0+)
- [ ] **Cloud-Based Data Pipeline** - Scalable data processing infrastructure
- [ ] **Professional Dashboard** - Web-based interface for monitoring and analysis
- [ ] **Custom Indicator Framework** - User-defined technical indicators
- [ ] **API Rate Optimization** - Advanced caching and request optimization
- [ ] **Mobile Application** - iOS/Android app for portfolio monitoring

### 📊 Release Timeline
- **v1.0.0** (Current) - Technical indicators and analytics library (Complete)
- **v2.0.0** (Q2 2025) - Machine learning integration and strategy framework
- **v3.0.0** (Q4 2025) - Advanced backtesting and production microstructure
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

## ⚡ Performance Optimizations
- Polars LazyFrames for deferred computations
- Indicator caching to avoid recomputes
- Vectorized operations in orderbook analysis
- Memory pruning for long-running sessions
- Rate limiting for API stability
