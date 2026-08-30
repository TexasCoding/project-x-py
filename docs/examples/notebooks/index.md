# Jupyter Notebook Examples

The `notebooks/` tree is not currently shipped in this repository. Use the
Python scripts under [`examples/`](https://github.com/TexasCoding/project-x-py/tree/main/examples)
for runnable v4.0 samples.

The links below are historical placeholders and may 404 until notebooks are republished.

## Available Notebooks

### Getting Started
- **[Basic Connection](https://github.com/TexasCoding/project-x-py/blob/main/notebooks/01_basic_connection.ipynb)** - First steps with the SDK
- **[Trading Suite Setup](https://github.com/TexasCoding/project-x-py/blob/main/notebooks/02_trading_suite.ipynb)** - Complete trading environment setup
- **[Market Data Exploration](https://github.com/TexasCoding/project-x-py/blob/main/notebooks/03_market_data.ipynb)** - Working with historical and real-time data

### Trading Strategies
- **[Simple Moving Average Strategy](https://github.com/TexasCoding/project-x-py/blob/main/notebooks/10_sma_strategy.ipynb)** - Basic trend following
- **[RSI Mean Reversion](https://github.com/TexasCoding/project-x-py/blob/main/notebooks/11_rsi_reversion.ipynb)** - Oversold/overbought trading
- **[Volume Profile Trading](https://github.com/TexasCoding/project-x-py/blob/main/notebooks/12_volume_profile.ipynb)** - Key level identification

### Technical Analysis
- **[Indicator Showcase](https://github.com/TexasCoding/project-x-py/blob/main/notebooks/20_indicators.ipynb)** - All 59+ indicators demonstrated
- **[Pattern Recognition](https://github.com/TexasCoding/project-x-py/blob/main/notebooks/21_patterns.ipynb)** - FVG and Order Block detection
- **[Multi-Timeframe Analysis](https://github.com/TexasCoding/project-x-py/blob/main/notebooks/22_mtf_analysis.ipynb)** - Confluence across timeframes

### Risk Management
- **[Position Sizing](https://github.com/TexasCoding/project-x-py/blob/main/notebooks/30_position_sizing.ipynb)** - Kelly Criterion and fixed risk
- **[Portfolio Analytics](https://github.com/TexasCoding/project-x-py/blob/main/notebooks/31_portfolio.ipynb)** - Performance metrics and analysis
- **[Risk Metrics](https://github.com/TexasCoding/project-x-py/blob/main/notebooks/32_risk_metrics.ipynb)** - Sharpe, Sortino, and drawdown

### Market Microstructure
- **[OrderBook Analysis](https://github.com/TexasCoding/project-x-py/blob/main/notebooks/40_orderbook.ipynb)** - Level 2 data exploration
- **[Order Flow](https://github.com/TexasCoding/project-x-py/blob/main/notebooks/41_order_flow.ipynb)** - Trade classification and imbalance
- **[Spoofing Detection](https://github.com/TexasCoding/project-x-py/blob/main/notebooks/42_spoofing.ipynb)** - Identifying manipulation patterns

## Running the Notebooks

### Prerequisites

```bash
# Install Jupyter and dependencies
pip install jupyter notebook ipywidgets plotly pandas

# Install the SDK
pip install project-x-py[all]
```

### Environment Setup

Create a `.env` file in the notebooks directory:

```bash
PROJECT_X_API_KEY=your-api-key
PROJECT_X_USERNAME=your-username
```

### Launch Jupyter

```bash
# Clone the repository
git clone https://github.com/TexasCoding/project-x-py.git
cd project-x-py/notebooks

# Start Jupyter
jupyter notebook
```

## Notebook Features

### Interactive Visualizations
- Real-time chart updates with Plotly
- Interactive order book visualization
- Candlestick charts with indicators
- Performance dashboards

### Live Data Integration
- Connect to real-time WebSocket feeds
- Stream market data into notebooks
- Place and monitor orders interactively
- Real-time position tracking

### Educational Content
- Step-by-step explanations
- Code cells with detailed comments
- Markdown cells with theory
- Exercise cells for practice

## Best Practices

### Safety First
```python
# Always use paper trading for testing
suite = await TradingSuite.create(
    ["MNQ"],
    mode="paper"  # Paper trading mode
)
```

### Memory Management
```python
# Clean up resources in notebooks
try:
    # Your trading code here
    pass
finally:
    await suite.disconnect()
```

### Async in Notebooks
```python
# Use nest_asyncio for async support
import nest_asyncio
nest_asyncio.apply()

# Now you can use await directly
suite = await TradingSuite.create(["MNQ"])
```

## Contributing Notebooks

We welcome notebook contributions! Please ensure:

1. **Clear objectives** - State what the notebook demonstrates
2. **Runnable code** - Test with paper trading account
3. **Documentation** - Explain concepts and code
4. **Visualizations** - Use charts to illustrate points
5. **Safety warnings** - Include risk disclaimers

## Example Notebook Structure

```python
# Cell 1: Setup
import asyncio
import nest_asyncio
from project_x_py import TradingSuite
import plotly.graph_objects as go
import pandas as pd

nest_asyncio.apply()

# Cell 2: Connect
suite = await TradingSuite.create(
    ["MNQ"],
    timeframes=["1min", "5min"],
    features=["orderbook"]
)

# Cell 3: Analysis
# Your strategy or analysis code

# Cell 4: Visualization
fig = go.Figure(data=[
    go.Candlestick(
        x=df['timestamp'],
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close']
    )
])
fig.show()

# Cell 5: Cleanup
await suite.disconnect()
```

## Resources

- [ProjectX Python SDK Documentation](https://texascoding.github.io/project-x-py/)
- [GitHub Repository](https://github.com/TexasCoding/project-x-py)
- [PyPI Package](https://pypi.org/project/project-x-py/)
- [Discord Community](https://discord.gg/projectx)

## License

All notebooks are provided under the MIT License. Use at your own risk for educational purposes only.
