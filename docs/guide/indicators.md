# Technical Indicators Guide

This guide covers the comprehensive technical indicators library in ProjectX Python SDK v3.3.4+. The indicators library provides 58+ technical analysis functions built on Polars DataFrames for high-performance financial analysis.

## Overview

ProjectX includes a complete technical analysis library similar to TA-Lib, optimized for modern Python with Polars DataFrames. All indicators are designed for both real-time analysis and backtesting with vectorized operations for maximum performance.

### Key Features

- **58+ Technical Indicators**: Complete coverage of momentum, overlap, volatility, and volume indicators
- **Pattern Recognition**: Advanced patterns including Fair Value Gaps, Order Blocks, and Waddah Attar Explosion
- **Dual Interface**: Both class-based and function-based APIs
- **Polars Integration**: High-performance DataFrame operations with method chaining
- **TA-Lib Compatibility**: Familiar naming and parameter conventions
- **Real-time Updates**: Seamless integration with streaming data
- **Caching and Validation**: Built-in performance optimizations

## Getting Started

### Basic Usage

```python
import asyncio
import polars as pl
from project_x_py import TradingSuite
from project_x_py.indicators import RSI, SMA, MACD

async def basic_indicators():
    # Get market data
    suite = await TradingSuite.create(["MNQ"])
    mnq_data = suite["MNQ"].data
    data = await mnq_data.get_data("5min", bars=100)

    # Method chaining with pipe (recommended)
    analyzed_data = (data
        .pipe(SMA, period=20)        # Simple Moving Average
        .pipe(RSI, period=14)        # Relative Strength Index
        .pipe(MACD)                  # MACD with default parameters
    )

    # Check the results
    latest_values = analyzed_data.tail(1)
    print(f"Latest SMA(20): {latest_values['sma_20'][0]:.2f}")
    print(f"Latest RSI(14): {latest_values['rsi_14'][0]:.2f}")
    print(f"Latest MACD: {latest_values['macd'][0]:.4f}")
```

### Available Indicator Categories

The indicators are organized into logical categories:

```python
from project_x_py.indicators import (
    # Overlap Studies (Trend Following)
    SMA, EMA, DEMA, TEMA, WMA, BBANDS, SAR, MIDPOINT,

    # Momentum Indicators
    RSI, MACD, STOCH, CCI, ADX, AROON, PPO, ROC, WILLR,

    # Volatility Indicators
    ATR, NATR, TRANGE, STDDEV,

    # Volume Indicators
    OBV, VWAP, AD, ADOSC, MFI,

    # Pattern Recognition (Advanced)
    FVG,        # Fair Value Gap
    ORDERBLOCK, # Order Block Detection
    WAE,        # Waddah Attar Explosion
    LORENZ,     # Lorenz Formula (Chaos Theory)
)
```

## Overlap Studies (Trend Following)

Overlap studies are typically plotted on the same scale as price data and help identify trend direction and support/resistance levels.

### Moving Averages

```python
async def moving_averages():
    suite = await TradingSuite.create(["MNQ"])
    mnq_data = suite["MNQ"].data
    data = await mnq_data.get_data("15min", bars=200)

    # Simple Moving Average
    data_with_sma = data.pipe(SMA, period=20)

    # Exponential Moving Average (more responsive)
    data_with_ema = data.pipe(EMA, period=20)

    # Double Exponential Moving Average (even more responsive)
    data_with_dema = data.pipe(DEMA, period=20)

    # Triple Exponential Moving Average
    data_with_tema = data.pipe(TEMA, period=20)

    # Weighted Moving Average
    data_with_wma = data.pipe(WMA, period=20)

    # Combine multiple moving averages
    ma_data = (data
        .pipe(SMA, period=10)   # Fast MA
        .pipe(SMA, period=20)   # Medium MA
        .pipe(SMA, period=50)   # Slow MA
        .pipe(EMA, period=20)   # EMA for comparison
    )

    # Moving average crossover analysis
    latest = ma_data.tail(5)

    fast_ma = latest['sma_10'][-1]
    slow_ma = latest['sma_20'][-1]

    if fast_ma > slow_ma:
        print("= Bullish MA crossover")
    else:
        print("= Bearish MA crossover")

    # Check for golden cross (50 SMA above 200 SMA)
    data_long_term = await mnq_data.get_data("1hr", bars=300)
    long_term_ma = (data_long_term
        .pipe(SMA, period=50)
        .pipe(SMA, period=200)
    )

    latest_long = long_term_ma.tail(1)
    if latest_long['sma_50'][0] > latest_long['sma_200'][0]:
        print("< Golden Cross - Long-term bullish")
```

### Bollinger Bands

```python
async def bollinger_bands_analysis():
    suite = await TradingSuite.create(["MNQ"])
    mnq_data = suite["MNQ"].data
    data = await mnq_data.get_data("5min", bars=100)

    # Standard Bollinger Bands (20-period, 2 std dev)
    bb_data = data.pipe(BBANDS, period=20, std_dev=2)

    # Bollinger Bands provide three values:
    # - bb_upper: Upper band
    # - bb_middle: Middle band (SMA)
    # - bb_lower: Lower band

    latest = bb_data.tail(1)
    current_price = latest['close'][0]
    upper_band = latest['bb_upper'][0]
    middle_band = latest['bb_middle'][0]
    lower_band = latest['bb_lower'][0]

    print(f"Current Price: ${current_price:.2f}")
    print(f"Upper Band: ${upper_band:.2f}")
    print(f"Middle Band: ${middle_band:.2f}")
    print(f"Lower Band: ${lower_band:.2f}")

    # Band width (volatility measure)
    band_width = (upper_band - lower_band) / middle_band
    print(f"Band Width: {band_width:.4f}")

    # Price position within bands
    bb_position = (current_price - lower_band) / (upper_band - lower_band)
    print(f"BB Position: {bb_position:.2f} (0=lower, 1=upper)")

    # Trading signals
    if current_price <= lower_band:
        print("=5 Price at lower band - potential bounce")
    elif current_price >= upper_band:
        print("=4 Price at upper band - potential reversal")
    elif bb_position < 0.2:
        print("= Price in lower 20% - oversold region")
    elif bb_position > 0.8:
        print("= Price in upper 20% - overbought region")
```

### Parabolic SAR

```python
async def parabolic_sar():
    suite = await TradingSuite.create(["MNQ"])
    mnq_data = suite["MNQ"].data
    data = await mnq_data.get_data("15min", bars=100)

    # Parabolic SAR for trend following
    sar_data = data.pipe(SAR, acceleration=0.02, maximum=0.2)

    latest_rows = sar_data.tail(5)

    for i in range(len(latest_rows)):
        price = latest_rows['close'][i]
        sar = latest_rows['sar'][i]

        if price > sar:
            trend = "Bullish"
        else:
            trend = "Bearish"

        print(f"Price: ${price:.2f}, SAR: ${sar:.2f} - {trend}")

    # SAR trend change detection
    current_sar = latest_rows['sar'][-1]
    prev_sar = latest_rows['sar'][-2]
    current_price = latest_rows['close'][-1]
    prev_price = latest_rows['close'][-2]

    # Detect SAR flip (trend change)
    if (prev_price <= prev_sar and current_price > current_sar):
        print("= SAR flipped bullish - trend change up")
    elif (prev_price >= prev_sar and current_price < current_sar):
        print("=4 SAR flipped bearish - trend change down")
```

## Momentum Indicators

Momentum indicators help identify the strength and direction of price movements, overbought/oversold conditions, and potential reversals.

### RSI (Relative Strength Index)

```python
async def rsi_analysis():
    suite = await TradingSuite.create(["MNQ"])
    mnq_data = suite["MNQ"].data
    data = await mnq_data.get_data("5min", bars=100)

    # Standard RSI (14-period)
    rsi_data = data.pipe(RSI, period=14)

    latest_rsi = rsi_data['rsi_14'].tail(5)

    for rsi in latest_rsi:
        if rsi >= 70:
            signal = "=4 Overbought"
        elif rsi <= 30:
            signal = "= Oversold"
        elif rsi > 50:
            signal = "= Bullish momentum"
        else:
            signal = "= Bearish momentum"

        print(f"RSI: {rsi:.1f} - {signal}")

    # RSI divergence analysis (advanced)
    recent_data = rsi_data.tail(20)

    # Look for price vs RSI divergence
    price_trend = recent_data['close'][-1] - recent_data['close'][-10]
    rsi_trend = recent_data['rsi_14'][-1] - recent_data['rsi_14'][-10]

    if price_trend > 0 and rsi_trend < 0:
        print("=  Bearish divergence - price up but RSI down")
    elif price_trend < 0 and rsi_trend > 0:
        print("=  Bullish divergence - price down but RSI up")

    # Multiple timeframe RSI
    data_15min = await mnq_data.get_data("15min", bars=100)
    data_1hr = await mnq_data.get_data("1hr", bars=100)

    rsi_15min = data_15min.pipe(RSI, period=14)['rsi_14'][-1]
    rsi_1hr = data_1hr.pipe(RSI, period=14)['rsi_14'][-1]

    print(f"\nMulti-timeframe RSI:")
    print(f"5min RSI: {rsi_data['rsi_14'][-1]:.1f}")
    print(f"15min RSI: {rsi_15min:.1f}")
    print(f"1hr RSI: {rsi_1hr:.1f}")
```

### MACD (Moving Average Convergence Divergence)

```python
async def macd_analysis():
    suite = await TradingSuite.create(["MNQ"])
    mnq_data = suite["MNQ"].data
    data = await mnq_data.get_data("15min", bars=200)

    # Standard MACD (12, 26, 9)
    macd_data = data.pipe(MACD, fast_period=12, slow_period=26, signal_period=9)

    # MACD provides three values:
    # - macd: MACD line (fast EMA - slow EMA)
    # - macd_signal: Signal line (EMA of MACD)
    # - macd_histogram: Histogram (MACD - Signal)

    latest = macd_data.tail(5)

    for i in range(len(latest)):
        macd_line = latest['macd'][i]
        signal_line = latest['macd_signal'][i]
        histogram = latest['macd_histogram'][i]

        # MACD signals
        if macd_line > signal_line and histogram > 0:
            signal = "= Bullish"
        elif macd_line < signal_line and histogram < 0:
            signal = "=4 Bearish"
        else:
            signal = " Neutral"

        print(f"MACD: {macd_line:.4f}, Signal: {signal_line:.4f}, Hist: {histogram:.4f} - {signal}")

    # MACD crossover detection
    current_hist = latest['macd_histogram'][-1]
    prev_hist = latest['macd_histogram'][-2]

    if prev_hist <= 0 and current_hist > 0:
        print("= MACD bullish crossover!")
    elif prev_hist >= 0 and current_hist < 0:
        print("= MACD bearish crossover!")

    # MACD zero line analysis
    current_macd = latest['macd'][-1]
    if current_macd > 0:
        print("= MACD above zero - uptrend")
    else:
        print("= MACD below zero - downtrend")
```

### Stochastic Oscillator

```python
async def stochastic_analysis():
    suite = await TradingSuite.create(["MNQ"])
    mnq_data = suite["MNQ"].data
    data = await mnq_data.get_data("5min", bars=100)

    # Stochastic (default: 5,3,3)
    stoch_data = data.pipe(STOCH, k_period=5, d_period=3, d_ma_type=0)

    # Stochastic provides two values:
    # - stoch_k: %K line (fast stochastic)
    # - stoch_d: %D line (slow stochastic, MA of %K)

    latest = stoch_data.tail(5)

    for i in range(len(latest)):
        k_value = latest['stoch_k'][i]
        d_value = latest['stoch_d'][i]

        # Overbought/Oversold levels
        if k_value >= 80 and d_value >= 80:
            signal = "=4 Overbought"
        elif k_value <= 20 and d_value <= 20:
            signal = "= Oversold"
        elif k_value > d_value:
            signal = "= %K above %D - bullish"
        else:
            signal = "= %K below %D - bearish"

        print(f"Stoch %K: {k_value:.1f}, %D: {d_value:.1f} - {signal}")

    # Stochastic crossover
    current_k = latest['stoch_k'][-1]
    current_d = latest['stoch_d'][-1]
    prev_k = latest['stoch_k'][-2]
    prev_d = latest['stoch_d'][-2]

    if prev_k <= prev_d and current_k > current_d:
        if current_k < 20:  # Oversold crossover
            print("= Bullish stochastic crossover in oversold region!")
    elif prev_k >= prev_d and current_k < current_d:
        if current_k > 80:  # Overbought crossover
            print("= Bearish stochastic crossover in overbought region!")
```

### ADX (Average Directional Index)

```python
async def adx_trend_strength():
    suite = await TradingSuite.create("MNQ")
    data = await suite.data.get_data("15min", bars=100)

    # ADX measures trend strength (not direction)
    adx_data = data.pipe(ADX, period=14)

    # ADX provides three values:
    # - adx: Trend strength (0-100)
    # - plus_di: Positive Directional Indicator
    # - minus_di: Negative Directional Indicator

    latest = adx_data.tail(1)
    adx_value = latest['adx'][0]
    plus_di = latest['plus_di'][0]
    minus_di = latest['minus_di'][0]

    print(f"ADX: {adx_value:.1f}")
    print(f"+DI: {plus_di:.1f}")
    print(f"-DI: {minus_di:.1f}")

    # Trend strength interpretation
    if adx_value >= 50:
        strength = "Very Strong"
    elif adx_value >= 25:
        strength = "Strong"
    elif adx_value >= 20:
        strength = "Moderate"
    else:
        strength = "Weak/Ranging"

    # Trend direction
    if plus_di > minus_di:
        direction = "Bullish"
    else:
        direction = "Bearish"

    print(f"Trend: {direction} {strength} (ADX: {adx_value:.1f})")

    # ADX trend analysis
    recent_adx = adx_data['adx'].tail(5)
    if recent_adx[-1] > recent_adx[-3]:  # ADX rising
        print("= ADX rising - trend strengthening")
    else:
        print("= ADX falling - trend weakening")
```

## Volatility Indicators

Volatility indicators measure the rate of price changes and help identify periods of high and low market activity.

### ATR (Average True Range)

```python
async def atr_volatility():
    suite = await TradingSuite.create("MNQ")
    data = await suite.data.get_data("15min", bars=100)

    # ATR measures volatility
    atr_data = data.pipe(ATR, period=14)

    current_atr = atr_data['atr_14'][-1]
    current_price = data['close'][-1]

    # ATR as percentage of price (normalized volatility)
    atr_percentage = (current_atr / current_price) * 100

    print(f"Current ATR: {current_atr:.2f}")
    print(f"ATR as % of price: {atr_percentage:.2f}%")

    # Compare to historical ATR
    avg_atr = atr_data['atr_14'].tail(50).mean()

    if current_atr > avg_atr * 1.5:
        print("=% High volatility period")
    elif current_atr < avg_atr * 0.5:
        print("=4 Low volatility period")
    else:
        print("= Normal volatility")

    # ATR-based position sizing
    risk_per_trade = 100  # $100 risk
    atr_multiplier = 2.0  # 2x ATR for stop loss

    stop_distance = current_atr * atr_multiplier
    position_size = risk_per_trade / stop_distance

    print(f"\nATR-based position sizing:")
    print(f"Stop distance (2x ATR): ${stop_distance:.2f}")
    print(f"Suggested position size: {position_size:.1f} contracts")

    # ATR bands (price  ATR)
    atr_upper = current_price + current_atr
    atr_lower = current_price - current_atr

    print(f"\nATR Bands:")
    print(f"Upper: ${atr_upper:.2f}")
    print(f"Current: ${current_price:.2f}")
    print(f"Lower: ${atr_lower:.2f}")
```

### Normalized ATR

```python
async def normalized_atr():
    suite = await TradingSuite.create("MNQ")
    data = await suite.data.get_data("1hr", bars=100)

    # NATR (Normalized ATR) - ATR as percentage
    natr_data = data.pipe(NATR, period=14)

    current_natr = natr_data['natr_14'][-1]

    print(f"Normalized ATR: {current_natr:.2f}%")

    # NATR interpretation
    if current_natr > 3.0:
        volatility_level = "Very High"
    elif current_natr > 2.0:
        volatility_level = "High"
    elif current_natr > 1.0:
        volatility_level = "Normal"
    else:
        volatility_level = "Low"

    print(f"Volatility Level: {volatility_level}")

    # Volatility breakout detection
    natr_history = natr_data['natr_14'].tail(20)
    avg_natr = natr_history.mean()

    if current_natr > avg_natr * 1.8:
        print("= Volatility breakout detected!")
```

## Volume Indicators

Volume indicators analyze trading volume to confirm price movements and identify potential reversals.

### OBV (On-Balance Volume)

```python
async def obv_analysis():
    suite = await TradingSuite.create("MNQ")
    data = await suite.data.get_data("15min", bars=100)

    # On-Balance Volume
    obv_data = data.pipe(OBV)

    # OBV trend analysis
    recent_obv = obv_data['obv'].tail(10)
    recent_prices = obv_data['close'].tail(10)

    obv_trend = recent_obv[-1] - recent_obv[-5]
    price_trend = recent_prices[-1] - recent_prices[-5]

    print(f"OBV Trend: {obv_trend:,.0f}")
    print(f"Price Trend: ${price_trend:.2f}")

    # Volume-price divergence
    if price_trend > 0 and obv_trend < 0:
        print("=  Bearish divergence - price up, volume down")
    elif price_trend < 0 and obv_trend > 0:
        print("=  Bullish divergence - price down, volume up")
    elif price_trend > 0 and obv_trend > 0:
        print(" Bullish confirmation - price and volume up")
    elif price_trend < 0 and obv_trend < 0:
        print(" Bearish confirmation - price and volume down")
```

### VWAP (Volume Weighted Average Price)

```python
async def vwap_analysis():
    suite = await TradingSuite.create("MNQ")
    data = await suite.data.get_data("5min", bars=100)

    # Volume Weighted Average Price
    vwap_data = data.pipe(VWAP)

    current_price = vwap_data['close'][-1]
    current_vwap = vwap_data['vwap'][-1]

    print(f"Current Price: ${current_price:.2f}")
    print(f"VWAP: ${current_vwap:.2f}")

    # Price relative to VWAP
    if current_price > current_vwap:
        print("= Price above VWAP - bullish bias")
        premium = ((current_price - current_vwap) / current_vwap) * 100
        print(f"Premium to VWAP: {premium:.2f}%")
    else:
        print("= Price below VWAP - bearish bias")
        discount = ((current_vwap - current_price) / current_vwap) * 100
        print(f"Discount to VWAP: {discount:.2f}%")

    # VWAP as support/resistance
    recent_data = vwap_data.tail(20)

    # Check how often price bounced off VWAP
    vwap_tests = 0
    vwap_holds = 0

    for i in range(1, len(recent_data)):
        prev_price = recent_data['close'][i-1]
        curr_price = recent_data['close'][i]
        vwap_level = recent_data['vwap'][i]

        # Check for VWAP test (price crosses VWAP)
        if (prev_price > vwap_level > curr_price) or (prev_price < vwap_level < curr_price):
            vwap_tests += 1

            # Check if it held as support/resistance in next few bars
            next_bars = recent_data[i:i+3] if i+3 <= len(recent_data) else recent_data[i:]
            if len(next_bars) > 1:
                if prev_price > vwap_level:  # Testing as support
                    if min(next_bars['low']) >= vwap_level * 0.999:  # Held as support
                        vwap_holds += 1
                else:  # Testing as resistance
                    if max(next_bars['high']) <= vwap_level * 1.001:  # Held as resistance
                        vwap_holds += 1

    if vwap_tests > 0:
        hold_rate = (vwap_holds / vwap_tests) * 100
        print(f"VWAP hold rate: {hold_rate:.1f}% ({vwap_holds}/{vwap_tests})")
```

### Money Flow Index (MFI)

```python
async def mfi_analysis():
    suite = await TradingSuite.create("MNQ")
    data = await suite.data.get_data("15min", bars=100)

    # Money Flow Index (volume-weighted RSI)
    mfi_data = data.pipe(MFI, period=14)

    current_mfi = mfi_data['mfi_14'][-1]

    print(f"MFI: {current_mfi:.1f}")

    # MFI interpretation (similar to RSI but includes volume)
    if current_mfi >= 80:
        print("=4 Overbought with volume confirmation")
    elif current_mfi <= 20:
        print("= Oversold with volume confirmation")
    elif current_mfi > 50:
        print("= Bullish money flow")
    else:
        print("= Bearish money flow")

    # MFI divergence with RSI
    rsi_data = data.pipe(RSI, period=14)
    current_rsi = rsi_data['rsi_14'][-1]

    print(f"RSI: {current_rsi:.1f}")
    print(f"MFI: {current_mfi:.1f}")

    mfi_rsi_diff = abs(current_mfi - current_rsi)

    if mfi_rsi_diff > 15:
        if current_mfi > current_rsi:
            print("= Volume supporting price momentum")
        else:
            print("=  Volume not supporting price momentum")
```

## Pattern Recognition Indicators

Advanced pattern recognition indicators identify sophisticated market structures and institutional trading patterns.

### Fair Value Gap (FVG)

```python
async def fvg_analysis():
    suite = await TradingSuite.create("MNQ")
    data = await suite.data.get_data("5min", bars=200)

    # Fair Value Gap detection
    fvg_data = data.pipe(FVG,
        min_gap_size=0.001,      # Minimum gap size (0.1%)
        check_mitigation=True     # Track if gaps get filled
    )

    # FVG provides several columns:
    # - fvg_bullish: Bullish FVG levels
    # - fvg_bearish: Bearish FVG levels
    # - fvg_mitigated: Whether gap was filled

    # Find active (unfilled) FVGs
    active_fvgs = fvg_data.filter(
        pl.col('fvg_bullish').is_not_null() | pl.col('fvg_bearish').is_not_null()
    ).filter(
        pl.col('fvg_mitigated') == False
    )

    current_price = data['close'][-1]

    print(f"Current Price: ${current_price:.2f}")
    print(f"Active FVGs found: {len(active_fvgs)}")

    # Analyze recent FVGs
    for row in active_fvgs.tail(5).iter_rows(named=True):
        timestamp = row['timestamp']

        if row['fvg_bullish'] is not None:
            gap_level = row['fvg_bullish']
            fvg_type = "Bullish"

            # Distance to current price
            distance = ((gap_level - current_price) / current_price) * 100

            if abs(distance) < 1.0:  # Within 1%
                proximity = "< Near current price"
            else:
                proximity = f"{distance:+.1f}% from current"

        elif row['fvg_bearish'] is not None:
            gap_level = row['fvg_bearish']
            fvg_type = "Bearish"
            distance = ((gap_level - current_price) / current_price) * 100

            if abs(distance) < 1.0:
                proximity = "< Near current price"
            else:
                proximity = f"{distance:+.1f}% from current"

        print(f"{fvg_type} FVG at ${gap_level:.2f} - {proximity}")

    # FVG trading strategy
    nearest_bullish_fvg = None
    nearest_bearish_fvg = None

    # Find nearest unfilled gaps
    for row in active_fvgs.iter_rows(named=True):
        if row['fvg_bullish'] is not None and row['fvg_bullish'] < current_price:
            if nearest_bullish_fvg is None or row['fvg_bullish'] > nearest_bullish_fvg:
                nearest_bullish_fvg = row['fvg_bullish']

        if row['fvg_bearish'] is not None and row['fvg_bearish'] > current_price:
            if nearest_bearish_fvg is None or row['fvg_bearish'] < nearest_bearish_fvg:
                nearest_bearish_fvg = row['fvg_bearish']

    print(f"\nNearest FVG levels:")
    if nearest_bullish_fvg:
        print(f"Support (Bullish FVG): ${nearest_bullish_fvg:.2f}")
    if nearest_bearish_fvg:
        print(f"Resistance (Bearish FVG): ${nearest_bearish_fvg:.2f}")
```

### Order Block Detection

```python
async def order_block_analysis():
    suite = await TradingSuite.create("MNQ")
    data = await suite.data.get_data("15min", bars=200)

    # Order Block detection (institutional order zones)
    ob_data = data.pipe(ORDERBLOCK,
        min_volume_percentile=70,    # Only high volume bars
        lookback_periods=20,         # Look back 20 periods
        use_wicks=True              # Include wick analysis
    )

    # Order Block provides:
    # - ob_bullish: Bullish order block levels
    # - ob_bearish: Bearish order block levels
    # - ob_strength: Order block strength (0-1)
    # - ob_age: How many bars ago the order block formed

    # Find recent order blocks
    recent_obs = ob_data.filter(
        pl.col('ob_bullish').is_not_null() | pl.col('ob_bearish').is_not_null()
    ).tail(10)

    current_price = data['close'][-1]

    print(f"Current Price: ${current_price:.2f}")
    print(f"Recent Order Blocks:")

    for row in recent_obs.iter_rows(named=True):
        if row['ob_bullish'] is not None:
            level = row['ob_bullish']
            ob_type = "Bullish"
            strength = row.get('ob_strength', 0)
            age = row.get('ob_age', 0)

            distance_pct = ((level - current_price) / current_price) * 100

            print(f"  {ob_type} OB: ${level:.2f} (Strength: {strength:.2f}, Age: {age}) - {distance_pct:+.1f}%")

        elif row['ob_bearish'] is not None:
            level = row['ob_bearish']
            ob_type = "Bearish"
            strength = row.get('ob_strength', 0)
            age = row.get('ob_age', 0)

            distance_pct = ((level - current_price) / current_price) * 100

            print(f"  {ob_type} OB: ${level:.2f} (Strength: {strength:.2f}, Age: {age}) - {distance_pct:+.1f}%")

    # Order block trading levels
    support_levels = []
    resistance_levels = []

    for row in recent_obs.iter_rows(named=True):
        if row['ob_bullish'] is not None and row['ob_bullish'] < current_price:
            support_levels.append({
                'level': row['ob_bullish'],
                'strength': row.get('ob_strength', 0),
                'age': row.get('ob_age', 0)
            })
        elif row['ob_bearish'] is not None and row['ob_bearish'] > current_price:
            resistance_levels.append({
                'level': row['ob_bearish'],
                'strength': row.get('ob_strength', 0),
                'age': row.get('ob_age', 0)
            })

    # Sort by proximity and strength
    support_levels.sort(key=lambda x: (current_price - x['level'], -x['strength']))
    resistance_levels.sort(key=lambda x: (x['level'] - current_price, -x['strength']))

    if support_levels:
        nearest_support = support_levels[0]
        print(f"\nNearest Support: ${nearest_support['level']:.2f} (Strength: {nearest_support['strength']:.2f})")

    if resistance_levels:
        nearest_resistance = resistance_levels[0]
        print(f"Nearest Resistance: ${nearest_resistance['level']:.2f} (Strength: {nearest_resistance['strength']:.2f})")
```

### Waddah Attar Explosion (WAE)

```python
async def wae_analysis():
    suite = await TradingSuite.create("MNQ")
    data = await suite.data.get_data("15min", bars=200)

    # Waddah Attar Explosion (trend explosion detector)
    wae_data = data.pipe(WAE,
        sensitivity=150,    # Sensitivity parameter
        fast_length=20,     # Fast MA length
        slow_length=40,     # Slow MA length
        bb_length=20,       # Bollinger Band length
        multiplier=2.0      # BB multiplier
    )

    # WAE provides:
    # - wae_explosion_up: Upward explosion strength
    # - wae_explosion_down: Downward explosion strength
    # - wae_trend: Current trend direction
    # - wae_dead_zone: Dead zone (low volatility) indicator

    latest = wae_data.tail(5)

    for i in range(len(latest)):
        explosion_up = latest['wae_explosion_up'][i] or 0
        explosion_down = latest['wae_explosion_down'][i] or 0
        trend = latest['wae_trend'][i]
        dead_zone = latest['wae_dead_zone'][i] or 0

        # Determine signal strength
        if explosion_up > 0:
            strength = explosion_up
            signal = f"= Bullish explosion ({strength:.1f})"
        elif explosion_down > 0:
            strength = explosion_down
            signal = f"= Bearish explosion ({strength:.1f})"
        elif dead_zone > 0:
            signal = f"=4 Dead zone ({dead_zone:.1f})"
        else:
            signal = " Neutral"

        print(f"WAE: {signal}, Trend: {trend}")

    # WAE trend change detection
    current_data = latest.tail(1)
    prev_data = latest.tail(2).head(1)

    current_trend = current_data['wae_trend'][0]
    prev_trend = prev_data['wae_trend'][0] if len(prev_data) > 0 else current_trend

    if current_trend != prev_trend:
        print(f"= WAE trend change: {prev_trend}  {current_trend}")

    # Explosion magnitude analysis
    recent_explosions_up = [x for x in latest['wae_explosion_up'] if x is not None and x > 0]
    recent_explosions_down = [x for x in latest['wae_explosion_down'] if x is not None and x > 0]

    if recent_explosions_up:
        avg_up = sum(recent_explosions_up) / len(recent_explosions_up)
        max_up = max(recent_explosions_up)
        print(f"Recent bullish explosions - Avg: {avg_up:.1f}, Max: {max_up:.1f}")

    if recent_explosions_down:
        avg_down = sum(recent_explosions_down) / len(recent_explosions_down)
        max_down = max(recent_explosions_down)
        print(f"Recent bearish explosions - Avg: {avg_down:.1f}, Max: {max_down:.1f}")
```

### Lorenz Formula (Chaos Theory)

The Lorenz Formula indicator applies chaos theory to market analysis, creating a dynamic attractor that responds to volatility, trend, and volume.

```python
async def lorenz_analysis():
    suite = await TradingSuite.create("MNQ")
    data = await suite.data.get_data("15min", bars=200)

    # Lorenz Formula with default parameters
    lorenz_data = data.pipe(LORENZ,
        window=14,              # Rolling window for parameters
        dt=0.1,                 # Time step (smaller = more stable)
        volatility_scale=0.02   # Expected volatility
    )

    # Lorenz provides three components:
    # - lorenz_x: Rate of change in the system
    # - lorenz_y: Momentum accumulation
    # - lorenz_z: Primary trading signal (height)

    latest = lorenz_data.tail(1)
    z_value = latest['lorenz_z'][0]

    # Basic signal interpretation
    if z_value > 0:
        print(f"Bullish bias (Z = {z_value:.2f})")
    elif z_value < 0:
        print(f"Bearish bias (Z = {z_value:.2f})")
    else:
        print("Neutral/Transitional")

    # Calculate chaos magnitude for regime detection
    lorenz_data = lorenz_data.with_columns([
        (pl.col("lorenz_x")**2 +
         pl.col("lorenz_y")**2 +
         pl.col("lorenz_z")**2).sqrt().alias("chaos_magnitude")
    ])

    # Classify market regime
    lorenz_data = lorenz_data.with_columns([
        pl.when(pl.col("chaos_magnitude") < 10)
        .then(pl.lit("STABLE"))
        .when(pl.col("chaos_magnitude") < 50)
        .then(pl.lit("TRANSITIONAL"))
        .otherwise(pl.lit("CHAOTIC"))
        .alias("market_regime")
    ])

    latest_regime = lorenz_data.tail(1)
    regime = latest_regime['market_regime'][0]
    magnitude = latest_regime['chaos_magnitude'][0]

    print(f"Market Regime: {regime} (Magnitude: {magnitude:.2f})")

    # Z-value crossover strategy
    lorenz_data = lorenz_data.with_columns([
        pl.col("lorenz_z").rolling_mean(window_size=10).alias("z_ma")
    ])

    # Detect crossovers
    current = lorenz_data.tail(1)
    previous = lorenz_data.tail(2).head(1)

    z_current = current['lorenz_z'][0]
    z_ma_current = current['z_ma'][0]
    z_previous = previous['lorenz_z'][0] if len(previous) > 0 else z_current
    z_ma_previous = previous['z_ma'][0] if len(previous) > 0 else z_ma_current

    # Check for crossover signals
    if z_previous <= z_ma_previous and z_current > z_ma_current:
        print("🔺 Bullish Z crossover detected!")
    elif z_previous >= z_ma_previous and z_current < z_ma_current:
        print("🔻 Bearish Z crossover detected!")

    # Advanced: Combine with other indicators
    from project_x_py.indicators import RSI

    combined = lorenz_data.pipe(RSI, period=14)
    latest = combined.tail(1)

    z = latest['lorenz_z'][0]
    rsi = latest['rsi_14'][0]

    # Strong signals when both align
    if z > 0 and rsi < 35:
        print("💪 STRONG BUY: Bullish Lorenz + Oversold RSI")
    elif z < 0 and rsi > 65:
        print("💪 STRONG SELL: Bearish Lorenz + Overbought RSI")
```

Key features of the Lorenz indicator:
- **Chaos Theory Application**: Adapts atmospheric modeling to markets
- **Three Components**: X (rate of change), Y (momentum), Z (signal)
- **Dynamic Parameters**: Automatically adjusts to market conditions
- **Regime Detection**: Identifies stable, transitional, and chaotic markets
- **Early Warning System**: Detects instability before major moves

For detailed documentation and advanced strategies, see [Lorenz Indicator Documentation](../indicators/lorenz.md).

## Real-time Indicator Updates

### Streaming Indicator Calculations

```python
from project_x_py import EventType

async def realtime_indicators():
    suite = await TradingSuite.create("MNQ", timeframes=["5min"])

    # Indicator state tracking
    indicator_state = {
        'rsi_values': [],
        'sma_values': [],
        'macd_signals': []
    }

    async def on_new_bar(event):
        """Update indicators on each new bar."""
        bar_data = event.data

        if bar_data['timeframe'] == '5min':
            # Get recent data for indicator calculation
            recent_data = await suite.data.get_data("5min", bars=50)

            # Calculate indicators on new data
            indicator_data = (recent_data
                .pipe(RSI, period=14)
                .pipe(SMA, period=20)
                .pipe(MACD)
            )

            # Extract latest values
            latest = indicator_data.tail(1)

            rsi_val = latest['rsi_14'][0]
            sma_val = latest['sma_20'][0]
            macd_val = latest['macd'][0]
            macd_signal = latest['macd_signal'][0]

            # Update state
            indicator_state['rsi_values'].append(rsi_val)
            indicator_state['sma_values'].append(sma_val)

            # Keep only recent values
            if len(indicator_state['rsi_values']) > 20:
                indicator_state['rsi_values'].pop(0)
                indicator_state['sma_values'].pop(0)

            # Generate signals
            await check_indicator_signals(latest, indicator_state)

    async def check_indicator_signals(latest_data, state):
        """Check for trading signals."""

        current_price = latest_data['close'][0]
        rsi = latest_data['rsi_14'][0]
        sma = latest_data['sma_20'][0]
        macd = latest_data['macd'][0]
        macd_signal = latest_data['macd_signal'][0]

        signals = []

        # RSI signals
        if rsi <= 30:
            signals.append("= RSI Oversold")
        elif rsi >= 70:
            signals.append("=4 RSI Overbought")

        # Price vs SMA
        if current_price > sma:
            signals.append("= Above SMA(20)")
        else:
            signals.append("= Below SMA(20)")

        # MACD signals
        if macd > macd_signal:
            signals.append("= MACD Bullish")
        else:
            signals.append("= MACD Bearish")

        # Print signals
        if signals:
            print(f"\n= Real-time signals @ ${current_price:.2f}:")
            for signal in signals:
                print(f"  {signal}")

    # Register event handler
    await suite.on(EventType.NEW_BAR, on_new_bar)

    print("=4 LIVE: Streaming indicator updates...")

    # Keep running for real-time updates
    await asyncio.sleep(300)  # 5 minutes
```

### Multi-timeframe Indicator Confluence

```python
async def multi_timeframe_confluence():
    suite = await TradingSuite.create(
        "MNQ",
        timeframes=["5min", "15min", "1hr"]
    )

    confluence_tracker = {
        '5min': {'rsi': None, 'macd': None},
        '15min': {'rsi': None, 'macd': None},
        '1hr': {'rsi': None, 'macd': None}
    }

    async def on_new_bar(event):
        """Track indicator confluence across timeframes."""
        bar_data = event.data
        timeframe = bar_data['timeframe']

        if timeframe in confluence_tracker:
            # Get data for this timeframe
            data = await suite.data.get_data(timeframe, bars=50)

            # Calculate indicators
            indicator_data = (data
                .pipe(RSI, period=14)
                .pipe(MACD)
            )

            latest = indicator_data.tail(1)

            # Update confluence tracker
            confluence_tracker[timeframe]['rsi'] = latest['rsi_14'][0]
            confluence_tracker[timeframe]['macd'] = "bullish" if latest['macd'][0] > latest['macd_signal'][0] else "bearish"

            # Check for confluence
            await check_confluence(confluence_tracker)

    async def check_confluence(tracker):
        """Check for indicator alignment across timeframes."""

        # Collect RSI signals
        rsi_oversold_count = 0
        rsi_overbought_count = 0

        # Collect MACD signals
        macd_bullish_count = 0
        macd_bearish_count = 0

        valid_timeframes = 0

        for tf, indicators in tracker.items():
            if indicators['rsi'] is not None and indicators['macd'] is not None:
                valid_timeframes += 1

                # RSI analysis
                if indicators['rsi'] <= 30:
                    rsi_oversold_count += 1
                elif indicators['rsi'] >= 70:
                    rsi_overbought_count += 1

                # MACD analysis
                if indicators['macd'] == 'bullish':
                    macd_bullish_count += 1
                else:
                    macd_bearish_count += 1

        if valid_timeframes >= 2:  # Need at least 2 timeframes

            # Check for strong confluence
            if rsi_oversold_count >= 2 and macd_bullish_count >= 2:
                print("< STRONG BULLISH CONFLUENCE:")
                print(f"   RSI oversold on {rsi_oversold_count}/{valid_timeframes} timeframes")
                print(f"   MACD bullish on {macd_bullish_count}/{valid_timeframes} timeframes")

            elif rsi_overbought_count >= 2 and macd_bearish_count >= 2:
                print("< STRONG BEARISH CONFLUENCE:")
                print(f"   RSI overbought on {rsi_overbought_count}/{valid_timeframes} timeframes")
                print(f"   MACD bearish on {macd_bearish_count}/{valid_timeframes} timeframes")

            # Print current state
            print(f"\n= Multi-timeframe state:")
            for tf, indicators in tracker.items():
                if indicators['rsi'] is not None:
                    print(f"   {tf}: RSI {indicators['rsi']:.1f}, MACD {indicators['macd']}")

    await suite.on(EventType.NEW_BAR, on_new_bar)

    # Monitor for confluence
    await asyncio.sleep(600)  # 10 minutes
```

## Performance Optimization

### Concurrent Indicator Calculations

```python
async def optimized_indicator_calculation():
    suite = await TradingSuite.create("MNQ")
    data = await suite.data.get_data("15min", bars=200)

    # Define indicator tasks for concurrent execution
    async def calculate_indicator_batch(base_data):
        """Calculate multiple indicators concurrently."""

        # Define all indicator calculations
        tasks = [
            # Momentum indicators
            asyncio.create_task(
                asyncio.get_event_loop().run_in_executor(
                    None, lambda: base_data.pipe(RSI, period=14)
                )
            ),
            asyncio.create_task(
                asyncio.get_event_loop().run_in_executor(
                    None, lambda: base_data.pipe(MACD)
                )
            ),
            asyncio.create_task(
                asyncio.get_event_loop().run_in_executor(
                    None, lambda: base_data.pipe(STOCH)
                )
            ),

            # Trend indicators
            asyncio.create_task(
                asyncio.get_event_loop().run_in_executor(
                    None, lambda: base_data.pipe(SMA, period=20)
                )
            ),
            asyncio.create_task(
                asyncio.get_event_loop().run_in_executor(
                    None, lambda: base_data.pipe(EMA, period=20)
                )
            ),
            asyncio.create_task(
                asyncio.get_event_loop().run_in_executor(
                    None, lambda: base_data.pipe(BBANDS, period=20)
                )
            ),

            # Volatility indicators
            asyncio.create_task(
                asyncio.get_event_loop().run_in_executor(
                    None, lambda: base_data.pipe(ATR, period=14)
                )
            ),

            # Volume indicators
            asyncio.create_task(
                asyncio.get_event_loop().run_in_executor(
                    None, lambda: base_data.pipe(OBV)
                )
            ),
            asyncio.create_task(
                asyncio.get_event_loop().run_in_executor(
                    None, lambda: base_data.pipe(VWAP)
                )
            ),
        ]

        # Execute all calculations concurrently
        results = await asyncio.gather(*tasks)

        # Combine results (merge all indicator columns)
        combined_data = base_data
        for result in results:
            # Extract only new indicator columns
            indicator_cols = [col for col in result.columns if col not in base_data.columns]
            if indicator_cols:
                combined_data = combined_data.with_columns(
                    result.select(indicator_cols)
                )

        return combined_data

    # Measure performance
    import time
    start_time = time.time()

    # Sequential calculation (for comparison)
    sequential_data = (data
        .pipe(RSI, period=14)
        .pipe(MACD)
        .pipe(STOCH)
        .pipe(SMA, period=20)
        .pipe(EMA, period=20)
        .pipe(BBANDS, period=20)
        .pipe(ATR, period=14)
        .pipe(OBV)
        .pipe(VWAP)
    )

    sequential_time = time.time() - start_time

    # Concurrent calculation
    start_time = time.time()
    concurrent_data = await calculate_indicator_batch(data)
    concurrent_time = time.time() - start_time

    print(f"Sequential calculation: {sequential_time:.3f}s")
    print(f"Concurrent calculation: {concurrent_time:.3f}s")
    print(f"Speedup: {sequential_time / concurrent_time:.2f}x")

    # Verify results match
    print(f"Results identical: {sequential_data.equals(concurrent_data)}")
```

### Indicator Caching for Real-time Updates

```python
class IndicatorCache:
    def __init__(self):
        self.cache = {}
        self.cache_timestamps = {}

    def get_cache_key(self, indicator_name: str, params: dict) -> str:
        """Generate cache key for indicator."""
        param_str = "_".join(f"{k}_{v}" for k, v in sorted(params.items()))
        return f"{indicator_name}_{param_str}"

    async def get_or_calculate(self, data: pl.DataFrame, indicator_func, **params):
        """Get cached indicator or calculate if needed."""

        cache_key = self.get_cache_key(indicator_func.__name__, params)
        data_hash = hash(str(data.tail(1)['timestamp'][0]))  # Hash latest timestamp

        # Check if cached result is still valid
        if (cache_key in self.cache and
            self.cache_timestamps.get(cache_key) == data_hash):
            print(f"Cache hit for {cache_key}")
            return self.cache[cache_key]

        # Calculate new result
        print(f"Calculating {cache_key}")
        result = data.pipe(indicator_func, **params)

        # Cache result
        self.cache[cache_key] = result
        self.cache_timestamps[cache_key] = data_hash

        return result

# Usage with caching
async def cached_indicator_updates():
    suite = await TradingSuite.create("MNQ", timeframes=["5min"])
    cache = IndicatorCache()

    async def on_new_bar(event):
        """Efficiently update indicators with caching."""

        if event.data['timeframe'] == '5min':
            data = await suite.data.get_data("5min", bars=100)

            # Use cached calculations
            rsi_data = await cache.get_or_calculate(data, RSI, period=14)
            macd_data = await cache.get_or_calculate(data, MACD)
            sma_data = await cache.get_or_calculate(data, SMA, period=20)

            # Only the new calculations will be performed
            latest = rsi_data.tail(1)
            print(f"RSI: {latest['rsi_14'][0]:.1f}")

    await suite.on(EventType.NEW_BAR, on_new_bar)
    await asyncio.sleep(300)
```

## Best Practices

### 1. Efficient Data Pipeline

```python
# Good: Use method chaining for efficient calculation
def efficient_pipeline(data):
    return (data
        .pipe(SMA, period=20)
        .pipe(RSI, period=14)
        .pipe(MACD)
        .pipe(ATR, period=14)
    )

# Avoid: Multiple separate operations
def inefficient_pipeline(data):
    data1 = data.pipe(SMA, period=20)
    data2 = data1.pipe(RSI, period=14)  # Creates unnecessary copies
    data3 = data2.pipe(MACD)
    return data3.pipe(ATR, period=14)
```

### 2. Parameter Optimization

```python
async def optimize_indicator_parameters():
    """Find optimal parameters for indicators."""

    suite = await TradingSuite.create("MNQ")
    data = await suite.data.get_data("1hr", bars=1000)

    # Test different RSI periods
    best_rsi_period = None
    best_performance = -float('inf')

    for period in range(10, 25):
        # Calculate RSI with different periods
        rsi_data = data.pipe(RSI, period=period)

        # Simple performance metric (example)
        # You would use your actual strategy logic here
        overbought_signals = (rsi_data['rsi_' + str(period)] >= 70).sum()
        oversold_signals = (rsi_data['rsi_' + str(period)] <= 30).sum()

        # Balance of signals (you want some but not too many)
        signal_balance = abs(overbought_signals - oversold_signals)
        performance_score = (overbought_signals + oversold_signals) - signal_balance

        if performance_score > best_performance:
            best_performance = performance_score
            best_rsi_period = period

    print(f"Optimal RSI period: {best_rsi_period}")
    print(f"Performance score: {best_performance}")
```

### 3. Multi-timeframe Indicator Analysis

```python
async def comprehensive_multi_timeframe_analysis():
    """Analyze indicators across multiple timeframes."""

    suite = await TradingSuite.create(
        "MNQ",
        timeframes=["5min", "15min", "1hr", "4hr"]
    )

    timeframe_analysis = {}

    for tf in ["5min", "15min", "1hr", "4hr"]:
        data = await suite.data.get_data(tf, bars=100)

        # Calculate comprehensive indicators
        indicators = (data
            .pipe(RSI, period=14)
            .pipe(MACD)
            .pipe(SMA, period=20)
            .pipe(SMA, period=50)
            .pipe(ATR, period=14)
            .pipe(ADX, period=14)
        )

        latest = indicators.tail(1)

        # Analyze each timeframe
        analysis = {
            'rsi': latest['rsi_14'][0],
            'rsi_signal': 'overbought' if latest['rsi_14'][0] >= 70 else 'oversold' if latest['rsi_14'][0] <= 30 else 'neutral',
            'macd_signal': 'bullish' if latest['macd'][0] > latest['macd_signal'][0] else 'bearish',
            'ma_trend': 'bullish' if latest['sma_20'][0] > latest['sma_50'][0] else 'bearish',
            'atr': latest['atr_14'][0],
            'adx': latest['adx'][0],
            'trend_strength': 'strong' if latest['adx'][0] >= 25 else 'weak'
        }

        timeframe_analysis[tf] = analysis

    # Print comprehensive analysis
    print("= Multi-Timeframe Indicator Analysis:")
    print("-" * 50)

    for tf, analysis in timeframe_analysis.items():
        print(f"\n{tf.upper()} Analysis:")
        print(f"  RSI: {analysis['rsi']:.1f} ({analysis['rsi_signal']})")
        print(f"  MACD: {analysis['macd_signal']}")
        print(f"  MA Trend: {analysis['ma_trend']}")
        print(f"  ADX: {analysis['adx']:.1f} ({analysis['trend_strength']} trend)")

    # Overall confluence assessment
    bullish_signals = sum(1 for a in timeframe_analysis.values()
                         if a['macd_signal'] == 'bullish' and a['ma_trend'] == 'bullish')

    total_timeframes = len(timeframe_analysis)

    print(f"\n< Overall Assessment:")
    print(f"Bullish confluence: {bullish_signals}/{total_timeframes} timeframes")

    if bullish_signals >= total_timeframes * 0.75:
        print("= Strong bullish confluence")
    elif bullish_signals >= total_timeframes * 0.5:
        print("= Moderate bullish bias")
    else:
        print("=4 Bearish or mixed signals")
```

## Summary

The ProjectX Indicators library provides comprehensive technical analysis capabilities:

- **58+ Technical Indicators** covering all major categories
- **Pattern Recognition** with advanced patterns like FVG, Order Blocks, and WAE
- **High Performance** with Polars DataFrame optimization and concurrent calculations
- **Real-time Updates** seamlessly integrated with streaming data
- **Flexible Interface** supporting both functional and object-oriented approaches
- **TA-Lib Compatibility** for easy migration from existing strategies
- **Caching and Optimization** for production-ready performance

All indicators are designed for both backtesting and live trading with proper error handling, validation, and performance optimization.

---

**Next**: [OrderBook Guide](orderbook.md) | **Previous**: [Real-time Data Guide](realtime.md)
