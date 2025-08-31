# Lorenz Formula Indicator

## Overview

The Lorenz Formula indicator applies chaos theory to financial market analysis by adapting the famous Lorenz attractor equations to trading. Originally developed for atmospheric modeling, the Lorenz system creates a dynamic three-dimensional attractor that responds to market volatility, trend strength, and volume patterns.

This indicator is particularly powerful for:
- Detecting market instability and potential breakouts
- Identifying regime changes between trending and ranging markets
- Capturing hidden patterns not visible through traditional indicators
- Providing early warning signals for major market moves

## Mathematical Foundation

The Lorenz system consists of three coupled differential equations:

```
dx/dt = σ(y - x)
dy/dt = x(ρ - z) - y
dz/dt = xy - βz
```

Where the parameters are dynamically calculated from market data:
- **σ (sigma)**: Volatility factor scaled from rolling standard deviation of returns
- **ρ (rho)**: Trend strength derived from close price relative to its rolling mean
- **β (beta)**: Dissipation rate calculated from volume relative to its rolling mean

## Installation & Import

```python
from project_x_py.indicators import LORENZ, calculate_lorenz, LORENZIndicator
```

## Basic Usage

### Simple Implementation

```python
import polars as pl
from project_x_py.indicators import LORENZ

# Assuming you have OHLCV data in a DataFrame
df_with_lorenz = LORENZ(df)

# Access the three output components
x_values = df_with_lorenz["lorenz_x"]
y_values = df_with_lorenz["lorenz_y"]
z_values = df_with_lorenz["lorenz_z"]  # Primary signal
```

### Custom Parameters

```python
# Fine-tune the indicator for your specific needs
df_with_lorenz = LORENZ(
    df,
    window=20,           # Rolling window for parameter calculation
    dt=0.01,            # Time step (smaller = more stable)
    volatility_scale=0.02  # Expected volatility for normalization
)
```

## Parameter Guide

### Key Parameters

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `window` | 14 | 10-30 | Rolling window for calculating volatility, trends, and volume ratios |
| `dt` | 1.0 | 0.01-1.0 | Time step for Euler discretization. Controls sensitivity |
| `volatility_scale` | 0.02 | 0.01-0.05 | Expected volatility for normalizing sigma parameter |
| `initial_x` | 0.0 | Any | Initial X state value |
| `initial_y` | 1.0 | Any | Initial Y state value |
| `initial_z` | 0.0 | Any | Initial Z state value |

### Parameter Tuning Guidelines

#### Time Step (dt)
- **Small dt (0.01-0.1)**: More stable, gradual changes, better for longer timeframes
- **Medium dt (0.1-0.5)**: Balanced responsiveness and stability
- **Large dt (0.5-1.0)**: More sensitive, faster response, suitable for scalping

#### Window Size
- **Short window (10-14)**: More responsive to recent market changes
- **Medium window (15-20)**: Balanced between noise and lag
- **Long window (21-30)**: Smoother parameters, more stable signals

#### Volatility Scale
- **Forex/Indices**: 0.01-0.02 (lower volatility markets)
- **Stocks**: 0.02-0.03 (moderate volatility)
- **Crypto/Commodities**: 0.03-0.05 (higher volatility)

## Trading Signals

### 1. Z-Value Momentum Signal

The primary signal comes from the Z component:

```python
# Basic momentum signal
signal_df = LORENZ(df, window=14, dt=0.1)

# Generate buy/sell signals
signal_df = signal_df.with_columns([
    pl.when(pl.col("lorenz_z") > 0).then(pl.lit("BULLISH"))
    .when(pl.col("lorenz_z") < 0).then(pl.lit("BEARISH"))
    .otherwise(pl.lit("NEUTRAL"))
    .alias("market_bias")
])
```

### 2. Z-Value Crossover Strategy

```python
# Calculate moving average of Z values
signal_df = LORENZ(df, window=14, dt=0.1)
signal_df = signal_df.with_columns([
    pl.col("lorenz_z").rolling_mean(window_size=10).alias("z_ma")
])

# Generate crossover signals
signal_df = signal_df.with_columns([
    pl.when(
        (pl.col("lorenz_z") > pl.col("z_ma")) &
        (pl.col("lorenz_z").shift(1) <= pl.col("z_ma").shift(1))
    ).then(pl.lit("BUY"))
    .when(
        (pl.col("lorenz_z") < pl.col("z_ma")) &
        (pl.col("lorenz_z").shift(1) >= pl.col("z_ma").shift(1))
    ).then(pl.lit("SELL"))
    .otherwise(pl.lit("HOLD"))
    .alias("signal")
])
```

### 3. Chaos Magnitude Strategy

Measure the distance from origin to detect market volatility:

```python
# Calculate chaos magnitude
regime_df = LORENZ(df, window=20, dt=0.05)
regime_df = regime_df.with_columns([
    (
        pl.col("lorenz_x")**2 +
        pl.col("lorenz_y")**2 +
        pl.col("lorenz_z")**2
    ).sqrt().alias("chaos_magnitude")
])

# Classify market regimes
regime_df = regime_df.with_columns([
    pl.when(pl.col("chaos_magnitude") < 10)
    .then(pl.lit("STABLE"))
    .when(pl.col("chaos_magnitude") < 50)
    .then(pl.lit("TRANSITIONAL"))
    .otherwise(pl.lit("CHAOTIC"))
    .alias("market_regime")
])

# Trade based on regime
# - STABLE: Range trading strategies
# - TRANSITIONAL: Prepare for breakouts
# - CHAOTIC: Trend following or stay out
```

### 4. Divergence Detection

Identify divergences between price and Lorenz Z:

```python
# Calculate price trend and Z trend
df_lorenz = LORENZ(df, window=14, dt=0.1)

# Add trend indicators
df_lorenz = df_lorenz.with_columns([
    pl.col("close").rolling_mean(5).alias("price_ma"),
    pl.col("lorenz_z").rolling_mean(5).alias("z_ma")
])

# Detect divergences
df_lorenz = df_lorenz.with_columns([
    # Bullish divergence: Price making lower lows, Z making higher lows
    pl.when(
        (pl.col("close") < pl.col("close").shift(20)) &
        (pl.col("lorenz_z") > pl.col("lorenz_z").shift(20))
    ).then(pl.lit("BULLISH_DIV"))
    # Bearish divergence: Price making higher highs, Z making lower highs
    .when(
        (pl.col("close") > pl.col("close").shift(20)) &
        (pl.col("lorenz_z") < pl.col("lorenz_z").shift(20))
    ).then(pl.lit("BEARISH_DIV"))
    .otherwise(pl.lit(""))
    .alias("divergence")
])
```

## Advanced Strategies

### 1. Multi-Timeframe Lorenz Analysis

```python
# Calculate Lorenz on multiple timeframes
df_5min = LORENZ(df_5min, window=14, dt=0.1)
df_15min = LORENZ(df_15min, window=14, dt=0.05)
df_1hour = LORENZ(df_1hour, window=14, dt=0.01)

# Trade when all timeframes align
# - All Z values positive = Strong buy
# - All Z values negative = Strong sell
# - Mixed signals = Stay out
```

### 2. Lorenz + RSI Confluence

```python
from project_x_py.indicators import RSI, LORENZ

# Calculate both indicators
df = LORENZ(df, window=14, dt=0.1)
df = RSI(df, period=14)

# Strong signals when both align
df = df.with_columns([
    pl.when(
        (pl.col("lorenz_z") > 0) &
        (pl.col("lorenz_z").shift(1) <= 0) &
        (pl.col("rsi_14") < 35)
    ).then(pl.lit("STRONG_BUY"))
    .when(
        (pl.col("lorenz_z") < 0) &
        (pl.col("lorenz_z").shift(1) >= 0) &
        (pl.col("rsi_14") > 65)
    ).then(pl.lit("STRONG_SELL"))
    .otherwise(pl.lit("WAIT"))
    .alias("confluence_signal")
])
```

### 3. Volatility-Adjusted Position Sizing

```python
# Use chaos magnitude for position sizing
df = LORENZ(df, window=14, dt=0.1)
df = df.with_columns([
    (pl.col("lorenz_x")**2 + pl.col("lorenz_y")**2 + pl.col("lorenz_z")**2).sqrt()
    .alias("chaos_magnitude")
])

# Normalize chaos magnitude to 0-1 range
df = df.with_columns([
    (pl.col("chaos_magnitude") / pl.col("chaos_magnitude").max())
    .alias("volatility_factor")
])

# Adjust position size inversely to volatility
df = df.with_columns([
    pl.when(pl.col("volatility_factor") < 0.3)
    .then(pl.lit(1.0))  # Full position in stable markets
    .when(pl.col("volatility_factor") < 0.6)
    .then(pl.lit(0.5))  # Half position in transitional markets
    .otherwise(pl.lit(0.25))  # Quarter position in chaotic markets
    .alias("position_size_multiplier")
])
```

## Complete Trading System Example

```python
import asyncio
import polars as pl
from project_x_py import ProjectX
from project_x_py.indicators import LORENZ, RSI, ATR

async def lorenz_trading_system():
    async with ProjectX.from_env() as client:
        await client.authenticate()

        # Get data
        df = await client.get_bars("MNQ", days=10)

        # Calculate indicators
        df = LORENZ(df, window=14, dt=0.1)
        df = RSI(df, period=14)
        df = ATR(df, period=14)

        # Calculate chaos magnitude
        df = df.with_columns([
            (pl.col("lorenz_x")**2 + pl.col("lorenz_y")**2 + pl.col("lorenz_z")**2)
            .sqrt().alias("chaos_magnitude")
        ])

        # Generate entry signals
        df = df.with_columns([
            # Long entry conditions
            pl.when(
                (pl.col("lorenz_z") > 0) &                    # Bullish Z
                (pl.col("lorenz_z") > pl.col("lorenz_z").shift(1)) &  # Z increasing
                (pl.col("rsi_14") > 30) & (pl.col("rsi_14") < 70) &   # RSI not extreme
                (pl.col("chaos_magnitude") < 100)             # Not too chaotic
            ).then(pl.lit(1))

            # Short entry conditions
            .when(
                (pl.col("lorenz_z") < 0) &                    # Bearish Z
                (pl.col("lorenz_z") < pl.col("lorenz_z").shift(1)) &  # Z decreasing
                (pl.col("rsi_14") > 30) & (pl.col("rsi_14") < 70) &   # RSI not extreme
                (pl.col("chaos_magnitude") < 100)             # Not too chaotic
            ).then(pl.lit(-1))

            .otherwise(pl.lit(0))
            .alias("entry_signal")
        ])

        # Calculate stop loss and take profit
        df = df.with_columns([
            # Stop loss at 2 ATR
            (pl.col("atr_14") * 2).alias("stop_distance"),
            # Take profit at 3 ATR
            (pl.col("atr_14") * 3).alias("target_distance"),
            # Position size based on chaos
            pl.when(pl.col("chaos_magnitude") < 30).then(pl.lit(1.0))
            .when(pl.col("chaos_magnitude") < 60).then(pl.lit(0.75))
            .when(pl.col("chaos_magnitude") < 90).then(pl.lit(0.5))
            .otherwise(pl.lit(0.25))
            .alias("position_size")
        ])

        # Get latest signal
        latest = df.tail(1)
        signal = latest["entry_signal"][0]

        if signal != 0:
            price = latest["close"][0]
            stop_distance = latest["stop_distance"][0]
            target_distance = latest["target_distance"][0]
            size = latest["position_size"][0]

            print(f"Signal: {'LONG' if signal > 0 else 'SHORT'}")
            print(f"Entry Price: {price}")
            print(f"Stop Loss: {price - stop_distance if signal > 0 else price + stop_distance}")
            print(f"Take Profit: {price + target_distance if signal > 0 else price - target_distance}")
            print(f"Position Size: {size * 100}%")

if __name__ == "__main__":
    asyncio.run(lorenz_trading_system())
```

## Interpretation Guide

### Understanding the Components

1. **Lorenz X**: Represents the rate of change in the system
   - Large positive/negative values indicate rapid changes
   - Near zero suggests stability

2. **Lorenz Y**: Represents momentum accumulation
   - Positive values suggest bullish momentum building
   - Negative values suggest bearish momentum building

3. **Lorenz Z**: Primary trading signal (height in the attractor)
   - Positive Z: Bullish market conditions
   - Negative Z: Bearish market conditions
   - Large |Z|: Strong trend or high volatility
   - Z near zero: Transitional phase

### Market Regime Identification

| Chaos Magnitude | Market State | Trading Approach |
|-----------------|--------------|------------------|
| < 10 | Stable/Ranging | Mean reversion, support/resistance |
| 10-50 | Transitional | Prepare for breakouts, reduce position size |
| 50-200 | Trending | Trend following, momentum strategies |
| > 200 | Chaotic/Volatile | Reduce exposure or stay out |

## Best Practices

### DO's
- ✅ Backtest different parameter combinations for your specific market
- ✅ Use smaller dt values (0.01-0.1) for more stable signals
- ✅ Combine with other indicators for confirmation
- ✅ Adjust volatility_scale based on the asset's typical volatility
- ✅ Monitor chaos magnitude for position sizing
- ✅ Use multiple timeframes for better context

### DON'Ts
- ❌ Don't use dt > 1.0 unless you want extremely sensitive signals
- ❌ Don't ignore the chaos magnitude - it indicates market stability
- ❌ Don't trade solely on Z-value crossovers without confirmation
- ❌ Don't use the same parameters for all market conditions
- ❌ Don't ignore divergences between price and Lorenz components

## Common Pitfalls & Solutions

### Problem: Signals are too noisy
**Solution**: Decrease dt parameter (try 0.01-0.05) and increase window size (20-30)

### Problem: Indicator is lagging too much
**Solution**: Increase dt parameter (0.2-0.5) and decrease window size (10-14)

### Problem: Z values hitting limits (±1000)
**Solution**: The system is saturating. Reduce dt or adjust volatility_scale

### Problem: No clear signals in ranging markets
**Solution**: This is normal - Lorenz works best in trending/volatile markets. Consider using chaos magnitude < 10 as a filter to avoid ranging periods

## Performance Considerations

- The indicator uses NumPy arrays for efficient computation
- Calculation time is O(n) where n is the number of bars
- Memory usage is minimal (3 additional float columns)
- Can handle datasets with 100,000+ bars efficiently

## References

- Lorenz, E. N. (1963). "Deterministic Nonperiodic Flow"
- Chaos Theory applications in financial markets
- Nonlinear dynamics in price discovery

## See Also

- [RSI Indicator](./rsi.md) - For momentum confirmation
- [ATR Indicator](./atr.md) - For volatility-based stops
- [MACD Indicator](./macd.md) - For trend confirmation
- [Bollinger Bands](./bollinger_bands.md) - For volatility comparison
