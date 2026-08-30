# Technical Indicators

64 named indicators, Polars implementations; **not** a full TA-Lib port.

Package-level names such as `RSI`, `SMA`, `MACD`, and `ATR` are **functions** (`RSI(df, period=14)`). Use `RSIIndicator` / `SMAIndicator` / `MACDIndicator` / `ATRIndicator` for the class API.

Stubs (not Hilbert / MESA / TA-Lib numerical ports):

- `HT_TRENDLINE` — slow EMA (`ewm_mean(alpha=0.0625)`), not Hilbert
- `MAMA` — constant alpha, not MESA Hilbert
- `MAVP` — ignores periods column, SMA(min_period)
- `SAREXT` — SAR renamed; extra params ignored

## Overview

The indicators module provides both class-based and function-based interfaces for technical analysis, optimized for Polars DataFrames.


## Quick Start

```python
import asyncio
from project_x_py.indicators import RSI, SMA, MACD, BBANDS
from project_x_py import ProjectX

async def analyze_market():
    # Get market data
    async with ProjectX.from_env() as client:
        await client.authenticate()
        data = await client.get_bars('MNQ', days=30, interval=60)

    # Function interface (package import)
    data = RSI(data, period=14)

    # Class interface
    from project_x_py.indicators import RSIIndicator
    data_with_rsi = RSIIndicator().calculate(data, period=14)

    # TA-Lib style functions (direct usage)
    data = RSI(data, period=14)        # Add RSI
    data = SMA(data, period=20)        # Add 20-period SMA
    data = BBANDS(data, period=20)     # Add Bollinger Bands

    return data

# Run the analysis
data = asyncio.run(analyze_market())
```

## Base Classes






## Overlap Studies (Trend Indicators)








## Momentum Indicators









## Volatility Indicators






## Volume Indicators





## Pattern Recognition Indicators




## Usage Examples

### Basic Usage

```python
import asyncio
from project_x_py.indicators import RSI, SMA, MACD
from project_x_py import ProjectX

async def basic_analysis():
    # Load your data (Polars DataFrame with OHLCV columns)
    async with ProjectX.from_env() as client:
        await client.authenticate()
        data = await client.get_bars('MNQ', days=30, interval=60)

    # Add indicators using TA-Lib style functions
    data = RSI(data, period=14)
    data = SMA(data, period=20)
    data = SMA(data, period=50)
    data = MACD(data, fast_period=12, slow_period=26, signal_period=9)

    # Check latest values
    latest = data.tail(1)
    print(f"RSI: {latest['rsi_14'].item():.2f}")
    print(f"SMA(20): ${latest['sma_20'].item():.2f}")

asyncio.run(basic_analysis())
```

### Class-Based Interface

```python
from project_x_py.indicators import RSI, SMA, BBANDS

# Create indicator instances
rsi = RSI()
sma = SMA()
bb = BBANDS()

# Calculate indicators
data_with_rsi = rsi.calculate(data, period=14)
data_with_sma = sma.calculate(data_with_rsi, period=20)
data_with_bb = bb.calculate(data_with_sma, period=20, std_dev=2.0)
```

### Multi-Indicator Strategy

```python
import asyncio
import polars as pl
from project_x_py.indicators import *
from project_x_py import ProjectX

async def multi_indicator_analysis():
    # Get data
    async with ProjectX.from_env() as client:
        await client.authenticate()
        data = await client.get_bars('MNQ', days=60, interval=60)

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

        # Pattern recognition
        .pipe(FVG, min_gap_size=0.001, check_mitigation=True)
        .pipe(ORDERBLOCK, min_volume_percentile=70)
        .pipe(WAE, sensitivity=150)
    )

    return analysis

# Run the strategy
result = asyncio.run(multi_indicator_analysis())
```

### Pattern Recognition Examples

```python
from project_x_py.indicators import FVG, OrderBlock, WAE

# Fair Value Gap Detection
fvg = FVG()
data_with_fvg = fvg.calculate(
    data,
    min_gap_size=0.001,  # 0.1% minimum gap
    check_mitigation=True,  # Track if gaps get filled
    mitigation_threshold=0.5  # 50% fill threshold
)

# Order Block Identification
ob = OrderBlock()
data_with_ob = ob.calculate(
    data,
    min_volume_percentile=70,  # Top 30% volume
    lookback_periods=3,  # Look for 3-candle patterns
    use_wicks=True  # Consider wicks in patterns
)

# Waddah Attar Explosion
wae = WAE()
data_with_wae = wae.calculate(
    data,
    sensitivity=150,  # Trend sensitivity
    dead_zone_period=100,  # ATR period for filtering
    dead_zone_mult=3.6  # Dead zone multiplier
)

# Confluence Trading: Combine all three
confluence_data = (
    data
    .pipe(FVG, check_mitigation=True)
    .pipe(ORDERBLOCK, min_volume_percentile=80)
    .pipe(WAE, sensitivity=150)
)

# Find strong signals where patterns align
strong_bullish = confluence_data.filter(
    (pl.col("fvg_bullish") == True) &
    (pl.col("ob_bullish") == True) &
    (pl.col("wae_explosion_up") > 0)
)
```

### Indicator Discovery

```python
from project_x_py.indicators import get_all_indicators, get_indicator_groups

# List all available indicators
all_indicators = get_all_indicators()
print(f"Total indicators: {len(all_indicators)}")

# Get indicators by category
groups = get_indicator_groups()
for category, indicators in groups.items():
    print(f"{category}: {indicators}")

# Get information about specific indicator
rsi_info = get_indicator_info('RSI')
print(f"RSI: {rsi_info}")
```

### Error Handling

```python
from project_x_py.indicators import IndicatorError

try:
    # This will raise an error if the column doesn't exist
    data_with_rsi = RSI(data, column='nonexistent_column', period=14)
except IndicatorError as e:
    print(f"Indicator error: {e}")

try:
    # This will raise an error if period is too large
    data_with_sma = SMA(data, period=1000)  # More than available data
except IndicatorError as e:
    print(f"Invalid period: {e}")
```

## Performance Tips

1. **Use Polars methods**: Indicators are optimized for Polars DataFrames
2. **Chain operations**: Use `.pipe()` for efficient chaining
3. **Reuse instances**: Create indicator instances once and reuse them
4. **Batch calculations**: Calculate multiple indicators in one pass when possible
5. **Async data fetching**: Fetch data once and apply all indicators

```python
async def efficient_analysis():
    # Fetch data once
    async with ProjectX.from_env() as client:
        await client.authenticate()
        data = await client.get_bars('MNQ', days=30)

    # Efficient: Chain multiple indicators
    data = (
        data
        .pipe(RSI, period=14)
        .pipe(SMA, period=20)
        .pipe(MACD)
    )

    # Less efficient: Separate calculations
    # data = RSI(data, period=14)
    # data = SMA(data, period=20)
    # data = MACD(data)

    return data
```

## TA-Lib Compatibility

The indicators are designed to be compatible with TA-Lib naming and parameter conventions:

| TA-Lib Function | project-x-py Equivalent | Notes |
|----------------|-------------------------|-------|
| `talib.SMA(close, timeperiod=20)` | `SMA(data, period=20)` | Uses 'close' column by default |
| `talib.RSI(close, timeperiod=14)` | `RSI(data, period=14)` | Identical calculation method |
| `talib.BBANDS(close, timeperiod=20)` | `BBANDS(data, period=20, std_dev=2.0)` | Returns upper, middle, lower bands |
| `talib.MACD(close)` | `MACD(data)` | Returns MACD line, signal, histogram |

## Convenience Functions

### Overlap Studies




### Momentum Indicators






### Volatility Indicators



### Volume Indicators



### Pattern Recognition




## Discovery Functions




## Utility Functions
