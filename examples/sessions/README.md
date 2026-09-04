# ETH vs RTH Trading Sessions - Complete Usage Guide

*Last Updated: 2025-08-31*
*Version: 3.5.5*
*Feature Status: ✅ Implemented & Tested*

## Overview

The ETH vs RTH Trading Sessions feature provides comprehensive session-aware trading capabilities throughout the ProjectX SDK. This allows you to filter all market data, indicators, and trading operations based on Electronic Trading Hours (ETH) vs Regular Trading Hours (RTH).

### Key Benefits
- **Accurate backtesting** with proper session boundaries
- **Session-specific analytics** (RTH vs ETH volume, VWAP, etc.)
- **Indicator calculations** that respect market sessions
- **Real-time session filtering** for live trading
- **Product-specific configurations** for all major futures

---

## Quick Start

### Basic Setup
```python
from project_x_py import TradingSuite
from project_x_py.sessions import SessionConfig, SessionType, SessionTimes

# Option 1: RTH-only trading (recommended for most strategies)
session_config = SessionConfig(session_type=SessionType.RTH)
suite = await TradingSuite.create(
    "MNQ",  # or ["MNQ", "MES"] for multiple instruments
    timeframes=["1min", "5min"],
    session_config=session_config,
    initial_days=5
)

# Option 2: ETH-only (overnight sessions)
session_config = SessionConfig(session_type=SessionType.ETH)
suite = await TradingSuite.create(
    "MNQ",
    timeframes=["1min", "5min"],
    session_config=session_config
)

# Option 3: Default (ETH — all hours except the maintenance break)
suite = await TradingSuite.create("MNQ")  # SessionType.ETH by default
```

### Immediate Usage
```python
# Access data manager through context
mnq_context = suite["MNQ"]

# Get session-filtered data
rth_data = await mnq_context.data.get_session_data("5min", SessionType.RTH)
eth_data = await mnq_context.data.get_session_data("5min", SessionType.ETH)

# Check for data availability
if rth_data is not None and not rth_data.is_empty():
    print(f"RTH bars: {len(rth_data):,}")

# Get session statistics
stats = await mnq_context.data.get_session_statistics("5min")
if stats:
    print(f"RTH Volume: {stats['rth_volume']:,}")
```

---

## Session Configuration

### SessionType Enum
```python
from project_x_py.sessions import SessionType

SessionType.RTH     # Regular Trading Hours only
SessionType.ETH     # Electronic Trading Hours (excludes maintenance)
SessionType.CUSTOM  # Caller-supplied SessionTimes
```

### SessionConfig Options
```python
from project_x_py.sessions import SessionConfig, SessionTimes
from datetime import time

# Basic configuration
config = SessionConfig(
    session_type=SessionType.RTH  # RTH, ETH, or CUSTOM
)

# Custom session times
custom_times = SessionTimes(
    rth_start=time(9, 30),   # 9:30 AM ET
    rth_end=time(16, 0),     # 4:00 PM ET
    eth_start=time(18, 0),   # 6:00 PM ET
    eth_end=time(17, 0)      # 5:00 PM ET next day
)

config = SessionConfig(
    session_type=SessionType.RTH,
    session_times=custom_times
)
```

### Built-in Product Sessions
The SDK includes pre-configured session times in the DEFAULT_SESSIONS dictionary:

```python
from project_x_py.sessions import DEFAULT_SESSIONS

# Access predefined session times
equity_times = DEFAULT_SESSIONS["ES"]  # ES, NQ, MNQ, MES, YM, RTY
energy_times = DEFAULT_SESSIONS["CL"]  # CL, NG
metals_times = DEFAULT_SESSIONS["GC"]  # GC, SI
treasury_times = DEFAULT_SESSIONS["ZN"] # ZN, ZB, ZF, ZT
```

| Product | RTH Hours (ET) | Description |
|---------|----------------|-------------|
| ES, NQ, YM, RTY, MNQ, MES | 9:30 AM - 4:00 PM | Equity index futures |
| CL, NG | 9:00 AM - 2:30 PM | Energy futures |
| GC, SI | 8:20 AM - 1:30 PM | Precious metals |
| ZN, ZB, ZF, ZT | 8:20 AM - 3:00 PM | Treasury futures |

---

## TradingSuite Integration

### Creating Session-Aware TradingSuite
```python
# Method 1: With session config (recommended)
session_config = SessionConfig(session_type=SessionType.RTH)
suite = await TradingSuite.create(
    "MNQ",  # or ["MNQ", "MES"] for multiple
    timeframes=["1min", "5min", "15min"],
    session_config=session_config,
    features=["orderbook", "risk_manager"],
    initial_days=5
)

# Method 2: Change session type after creation
suite = await TradingSuite.create("MNQ")
await suite.set_session_type(SessionType.RTH)
```

### Session Methods
```python
# Access the instrument context
mnq_context = suite["MNQ"]

# Change session type for all instruments
await suite.set_session_type(SessionType.RTH)

# Get session-filtered data (through data manager)
rth_data = await mnq_context.data.get_session_data("5min", SessionType.RTH)
eth_data = await mnq_context.data.get_session_data("5min", SessionType.ETH)

# For multi-instrument suites
all_rth_data = await suite.get_session_data("5min", SessionType.RTH)
# Returns: {"MNQ": DataFrame, "MES": DataFrame}

# Get session statistics
stats = await mnq_context.data.get_session_statistics("5min")
```

### Session Statistics
```python
# For single instrument
mnq_context = suite["MNQ"]
stats = await mnq_context.data.get_session_statistics("5min")

if stats:
    # Available statistics:
    print(f"RTH Volume: {stats.get('rth_volume', 0):,}")
    print(f"ETH Volume: {stats.get('eth_volume', 0):,}")
    print(f"RTH VWAP: ${stats.get('rth_vwap', 0):.2f}")
    print(f"ETH VWAP: ${stats.get('eth_vwap', 0):.2f}")
    print(f"RTH Range: ${stats.get('rth_range', 0):.2f}")
    print(f"ETH Range: ${stats.get('eth_range', 0):.2f}")

# For multi-instrument
all_stats = await suite.get_session_statistics("5min")
# Returns: {"MNQ": stats_dict, "MES": stats_dict}
```

---

## Working with Session Data

### Using Data Manager Methods
```python
from project_x_py import TradingSuite
from project_x_py.sessions import SessionConfig, SessionType

# Create suite
suite = await TradingSuite.create(
    "MNQ",
    timeframes=["1min", "5min"],
    session_config=SessionConfig(session_type=SessionType.RTH),
    initial_days=5
)

mnq_context = suite["MNQ"]

# Get session-filtered data
rth_data = await mnq_context.data.get_session_data("5min", SessionType.RTH)
eth_data = await mnq_context.data.get_session_data("5min", SessionType.ETH)

# Always check for data availability
if rth_data is not None and not rth_data.is_empty():
    print(f"RTH bars: {len(rth_data):,}")
    print(f"First bar: {rth_data['timestamp'][0]}")
    print(f"Last bar: {rth_data['timestamp'][-1]}")
```

### Session Filtering with SessionFilterMixin
```python
from project_x_py.sessions import SessionFilterMixin, SessionType

# Create filter
session_filter = SessionFilterMixin()

# Get all data first
all_data = await mnq_context.data.get_data("5min")

if all_data is not None and not all_data.is_empty():
    # Filter to specific session
    rth_filtered = await session_filter.filter_by_session(
        all_data, SessionType.RTH, "MNQ"
    )
    eth_filtered = await session_filter.filter_by_session(
        all_data, SessionType.ETH, "MNQ"
    )

    print(f"All bars: {len(all_data):,}")
    print(f"RTH filtered: {len(rth_filtered):,}")
    print(f"ETH filtered: {len(eth_filtered):,}")

---

## Session-Aware Indicators

### Basic Usage
```python
from project_x_py.indicators import SMA, EMA, RSI, MACD

# Get RTH-only data
mnq_context = suite["MNQ"]
rth_data = await mnq_context.data.get_session_data("5min", SessionType.RTH)

if rth_data is not None and not rth_data.is_empty():
    # Apply indicators to session-filtered data
    with_indicators = (rth_data
        .pipe(SMA, period=20)
        .pipe(EMA, period=12)
        .pipe(RSI, period=14)
        .pipe(MACD)
    )

    # All indicators calculated only on RTH data
    print("Columns:", with_indicators.columns)

    # Check last values
    if "rsi_14" in with_indicators.columns:
        last_rsi = with_indicators["rsi_14"][-1]
        if last_rsi is not None:
            print(f"Last RSI: {float(last_rsi):.2f}")
```

### Session-Specific Indicators
```python
from project_x_py.sessions import (
    calculate_session_vwap,
    calculate_session_levels,
    calculate_anchored_vwap,
    calculate_session_cumulative_volume,
    calculate_relative_to_vwap,
    calculate_percent_from_open
)

# Session VWAP (resets at session boundaries)
vwap_data = await calculate_session_vwap(
    rth_data,
    SessionType.RTH,
    "MNQ"
)

if "session_vwap" in vwap_data.columns:
    last_vwap = vwap_data["session_vwap"][-1]
    if last_vwap is not None:
        print(f"Session VWAP: ${float(last_vwap):.2f}")

# Session high/low/open/close levels
levels_data = await calculate_session_levels(rth_data)

# Cumulative volume
volume_data = await calculate_session_cumulative_volume(rth_data)

# Anchored VWAP from session open
anchored_data = await calculate_anchored_vwap(
    rth_data,
    anchor_point="session_open"
)

# Price relative to VWAP
relative_data = await calculate_relative_to_vwap(vwap_data)

# Percent from session open
percent_data = await calculate_percent_from_open(levels_data)
```

### Multi-Session Comparison
```python
# Compare RTH vs ETH indicators
mnq_context = suite["MNQ"]
rth_data = await mnq_context.data.get_session_data("5min", SessionType.RTH)
eth_data = await mnq_context.data.get_session_data("5min", SessionType.ETH)

if (rth_data is not None and not rth_data.is_empty() and
    eth_data is not None and not eth_data.is_empty()):

    # Apply same indicator to both sessions
    rth_with_sma = rth_data.pipe(SMA, period=20)
    eth_with_sma = eth_data.pipe(SMA, period=20)

    # Analyze differences
    if "sma_20" in rth_with_sma.columns and "sma_20" in eth_with_sma.columns:
        rth_mean = rth_with_sma["sma_20"].drop_nulls().mean()
        eth_mean = eth_with_sma["sma_20"].drop_nulls().mean()

        if rth_mean is not None and eth_mean is not None:
            print(f"RTH SMA(20) Average: ${float(rth_mean):.2f}")
            print(f"ETH SMA(20) Average: ${float(eth_mean):.2f}")
            print(f"Difference: ${abs(float(rth_mean) - float(eth_mean)):.2f}")
```

---

## Real-Time Session Filtering

### Using TradingSuite (Recommended)
```python
# TradingSuite handles all real-time setup automatically
suite = await TradingSuite.create(
    "MNQ",
    timeframes=["1min", "5min"],
    session_config=SessionConfig(session_type=SessionType.RTH),
    initial_days=5
)

# Real-time data is automatically filtered by session
mnq_context = suite["MNQ"]

# Get current price (RTH-filtered)
current_price = await mnq_context.data.get_current_price()
if current_price:
    print(f"Current RTH Price: ${current_price:.2f}")

# Data is continuously updated and session-filtered
rth_data = await mnq_context.data.get_session_data("1min", SessionType.RTH)
```

### Market Status Checking
```python
from datetime import datetime, timezone

# Check current market status
config = SessionConfig(session_type=SessionType.RTH)
current_time = datetime.now(timezone.utc)

# Check if market is open
is_open = config.is_market_open(current_time, "MNQ")
print(f"RTH Market is: {'OPEN' if is_open else 'CLOSED'}")

# Get current session
current_session = config.get_current_session(current_time, "MNQ")
print(f"Current session: {current_session}")  # Returns: "RTH", "ETH", or "BREAK"

# Get session times for the product
session_times = config.get_session_times("MNQ")
print(f"RTH: {session_times.rth_start} - {session_times.rth_end}")
print(f"ETH: {session_times.eth_start} - {session_times.eth_end}")
```

### Session Analytics
```python
from project_x_py.sessions import SessionAnalytics, SessionStatistics

# Get all data
all_data = await mnq_context.data.get_data("5min")

if all_data is not None and not all_data.is_empty():
    # Initialize analytics
    analytics = SessionAnalytics()
    stats = SessionStatistics()

    # Compare sessions
    comparison = await analytics.compare_sessions(all_data, "MNQ")
    if comparison:
        if "rth_vs_eth_volume_ratio" in comparison:
            print(f"Volume Ratio (RTH/ETH): {comparison['rth_vs_eth_volume_ratio']:.2f}x")

    # Get volume profile by hour
    volume_profile = await analytics.get_session_volume_profile(all_data, "MNQ")

    # Analyze session gaps
    gaps = await analytics.analyze_session_gaps(all_data, "MNQ")

    # Calculate efficiency metrics
    efficiency = await analytics.calculate_efficiency_metrics(all_data, "MNQ")
```

---

## Advanced Usage Patterns

### Multi-Instrument Session Management
```python
async def multi_instrument_sessions():
    """Manage sessions across multiple instruments."""

    # Create suite with multiple instruments
    suite = await TradingSuite.create(
        ["MNQ", "MES", "MCL"],
        timeframes=["5min"],
        session_config=SessionConfig(session_type=SessionType.RTH),
        initial_days=5
    )

    # Access each instrument's session data
    for symbol, context in suite.items():
        data = await context.data.get_session_data("5min", SessionType.RTH)

        if data is not None and not data.is_empty():
            print(f"{symbol} RTH bars: {len(data):,}")

            # Calculate metrics
            volume = data["volume"].sum()
            high = data["high"].max()
            low = data["low"].min()

            if high is not None and low is not None:
                range_val = float(high) - float(low)
                print(f"{symbol} Range: ${range_val:.2f}")
            if volume is not None:
                print(f"{symbol} Volume: {int(volume):,}")

    # Get session statistics for all instruments
    all_stats = await suite.get_session_statistics("5min")
    # Returns: {"MNQ": stats_dict, "MES": stats_dict, "MCL": stats_dict}

    await suite.disconnect()
```

### Session Comparison Example
```python
async def compare_rth_vs_eth():
    """Compare RTH and ETH sessions for same instrument."""

    # Create two suites for comparison
    rth_suite = await TradingSuite.create(
        "MNQ",
        timeframes=["5min"],
        session_config=SessionConfig(session_type=SessionType.RTH),
        initial_days=10
    )

    eth_suite = await TradingSuite.create(
        "MNQ",
        timeframes=["5min"],
        session_config=SessionConfig(session_type=SessionType.ETH),
        initial_days=10
    )

    try:
        # Get contexts
        rth_context = rth_suite["MNQ"]
        eth_context = eth_suite["MNQ"]

        # Get session data
        rth_data = await rth_context.data.get_session_data("5min", SessionType.RTH)
        eth_data = await eth_context.data.get_session_data("5min", SessionType.ETH)

        if (rth_data is not None and not rth_data.is_empty() and
            eth_data is not None and not eth_data.is_empty()):

            # Compare volumes
            rth_volume = rth_data["volume"].sum()
            eth_volume = eth_data["volume"].sum()

            print(f"RTH Volume: {int(rth_volume):,}")
            print(f"ETH Volume: {int(eth_volume):,}")

            if eth_volume > 0:
                ratio = rth_volume / eth_volume
                print(f"RTH has {ratio:.2f}x more volume than ETH")

    finally:
        await rth_suite.disconnect()
        await eth_suite.disconnect()
```

### Session-Aware Indicators Example
```python
async def session_indicators_demo():
    """Calculate indicators with session awareness."""

    suite = await TradingSuite.create(
        "MNQ",
        timeframes=["5min"],
        session_config=SessionConfig(session_type=SessionType.RTH),
        initial_days=5
    )

    try:
        mnq_context = suite["MNQ"]
        data = await mnq_context.data.get_session_data("5min", SessionType.RTH)

        if data is None or data.is_empty():
            print("No RTH data available")
            return

        # Calculate session VWAP
        from project_x_py.sessions import calculate_session_vwap
        vwap_data = await calculate_session_vwap(data, SessionType.RTH, "MNQ")

        if "session_vwap" in vwap_data.columns:
            last_vwap = vwap_data["session_vwap"][-1]
            if last_vwap is not None:
                print(f"Current Session VWAP: ${float(last_vwap):.2f}")

        # Apply traditional indicators to RTH data
        from project_x_py.indicators import SMA, RSI, MACD
        with_indicators = vwap_data.pipe(SMA, period=20).pipe(RSI, period=14).pipe(MACD)

        # Check signals
        if all(col in with_indicators.columns for col in ["close", "session_vwap", "sma_20", "rsi_14"]):
            last_close = with_indicators["close"][-1]
            last_vwap = with_indicators["session_vwap"][-1]
            last_sma = with_indicators["sma_20"][-1]
            last_rsi = with_indicators["rsi_14"][-1]

            if all(v is not None for v in [last_close, last_vwap, last_sma, last_rsi]):
                # Generate signals
                if float(last_close) > float(last_vwap):
                    print("✓ Price above VWAP (bullish)")
                else:
                    print("✗ Price below VWAP (bearish)")

    finally:
        await suite.disconnect()
```

---

## Performance Optimizations

### Efficient Data Retrieval
```python
# ✅ GOOD: Get session data once, apply multiple indicators
mnq_context = suite["MNQ"]
rth_data = await mnq_context.data.get_session_data("5min", SessionType.RTH)

if rth_data is not None and not rth_data.is_empty():
    with_all_indicators = (rth_data
        .pipe(SMA, period=20)
        .pipe(EMA, period=12)
        .pipe(RSI, period=14)
        .pipe(MACD)
    )

# ❌ BAD: Multiple session data calls
sma_data = await mnq_context.data.get_session_data("5min", SessionType.RTH)
if sma_data is not None:
    sma_data = sma_data.pipe(SMA, period=20)

ema_data = await mnq_context.data.get_session_data("5min", SessionType.RTH)
if ema_data is not None:
    ema_data = ema_data.pipe(EMA, period=12)
```

### Lazy Evaluation for Large Datasets
```python
from project_x_py.sessions import SessionFilterMixin

# The system automatically optimizes based on data size
session_filter = SessionFilterMixin()

# Get large dataset
all_data = await mnq_context.data.get_data("1min")

if all_data is not None and len(all_data) > 100_000:
    print("Large dataset detected - using lazy evaluation")

# Automatically uses lazy evaluation for large datasets
filtered = await session_filter.filter_by_session(
    all_data,
    SessionType.RTH,
    "MNQ"
)
```

### Processing Large Datasets in Chunks
```python
import polars as pl

async def process_large_dataset(data: pl.DataFrame):
    """Process large datasets in daily chunks for memory efficiency."""

    filter_mixin = SessionFilterMixin()

    # Get unique dates
    dates = data['timestamp'].dt.date().unique().sort()

    results = []
    for date in dates:
        # Process one day at a time
        daily_data = data.filter(pl.col('timestamp').dt.date() == date)

        # Filter to RTH for this day
        rth_daily = await filter_mixin.filter_by_session(
            daily_data,
            SessionType.RTH,
            "MNQ"
        )

        if not rth_daily.is_empty():
            # Process this day's data
            daily_stats = {
                'date': date,
                'volume': rth_daily['volume'].sum(),
                'high': rth_daily['high'].max(),
                'low': rth_daily['low'].min()
            }
            results.append(daily_stats)

        # Clear memory
        del daily_data, rth_daily

    return results
```

---

## Testing and Validation

### Basic Validation
```python
async def validate_session_setup():
    """Validate your session configuration works correctly."""

    suite = await TradingSuite.create(
        "MNQ",
        timeframes=["5min"],
        session_config=SessionConfig(session_type=SessionType.RTH),
        initial_days=5
    )

    try:
        mnq_context = suite["MNQ"]

        # Test session data retrieval
        rth_data = await mnq_context.data.get_session_data("5min", SessionType.RTH)
        eth_data = await mnq_context.data.get_session_data("5min", SessionType.ETH)

        if rth_data is not None and eth_data is not None:
            print(f"RTH bars: {len(rth_data)}")
            print(f"ETH bars: {len(eth_data)}")

            # ETH should typically have more bars
            if not eth_data.is_empty() and not rth_data.is_empty():
                print(f"ETH has more bars: {len(eth_data) > len(rth_data)}")

        # Test session switching
        await suite.set_session_type(SessionType.RTH)
        await suite.set_session_type(SessionType.ETH)

        print("✅ All validations passed")

    finally:
        await suite.disconnect()
```

### Session Statistics Validation
```python
async def validate_session_statistics():
    """Validate session statistics calculations."""

    suite = await TradingSuite.create(
        "MNQ",
        timeframes=["5min"],
        initial_days=5
    )

    try:
        mnq_context = suite["MNQ"]

        # Get session statistics
        stats = await mnq_context.data.get_session_statistics("5min")

        if stats:
            print("Session Statistics:")

            # Check RTH statistics
            if "rth_volume" in stats and stats["rth_volume"] > 0:
                print(f"✓ RTH Volume: {stats['rth_volume']:,}")

            if "eth_volume" in stats and stats["eth_volume"] > 0:
                print(f"✓ ETH Volume: {stats['eth_volume']:,}")

            # Validate VWAP values
            if "rth_vwap" in stats and stats["rth_vwap"] > 0:
                print(f"✓ RTH VWAP: ${stats['rth_vwap']:.2f}")

            # Check volume ratio
            if stats.get("rth_volume", 0) > 0 and stats.get("eth_volume", 0) > 0:
                ratio = stats["rth_volume"] / stats["eth_volume"]
                print(f"✓ Volume Ratio (RTH/ETH): {ratio:.2f}x")
        else:
            print("⚠ No statistics available - check data availability")

    finally:
        await suite.disconnect()
```

---

## Troubleshooting

### Common Issues

#### Issue: No RTH data returned
```python
# Problem: Data might be None or empty
mnq_context = suite["MNQ"]
rth_data = await mnq_context.data.get_session_data("5min", SessionType.RTH)

if rth_data is None:
    print("No data returned - check connection")
elif rth_data.is_empty():
    print("Empty DataFrame - check if market is open")

# Solution: Check session configuration
config = SessionConfig(session_type=SessionType.RTH)
session_times = config.get_session_times("MNQ")
print(f"RTH hours: {session_times.rth_start} - {session_times.rth_end}")

# Check if market is currently open
from datetime import datetime, timezone
is_open = config.is_market_open(datetime.now(timezone.utc), "MNQ")
print(f"Market open: {is_open}")
```

#### Issue: Session statistics are None or zeros
```python
mnq_context = suite["MNQ"]
stats = await mnq_context.data.get_session_statistics("5min")

if stats is None:
    print("No statistics available")
elif stats.get('rth_volume', 0) == 0:
    print("No RTH volume data")

    # Check data availability
    data = await mnq_context.data.get_data("5min")
    if data is not None:
        print(f"Total bars available: {len(data)}")

    # May need to reinitialize with more days
    print("Consider creating suite with more initial_days")
```

#### Issue: Indicators not respecting sessions
```python
# Problem: Using all data instead of session-filtered
mnq_context = suite["MNQ"]
full_data = await mnq_context.data.get_data("5min")  # Unfiltered cache (RTH + ETH)

if full_data is not None:
    wrong_sma = full_data.pipe(SMA, period=20)  # Uses all data

# Solution: Use session-filtered data
rth_data = await mnq_context.data.get_session_data("5min", SessionType.RTH)

if rth_data is not None and not rth_data.is_empty():
    correct_sma = rth_data.pipe(SMA, period=20)  # Uses only RTH data
```

### Debug Mode
```python
import logging

# Enable session debugging
logging.getLogger("project_x_py.sessions").setLevel(logging.DEBUG)

# This will show:
# - Session boundary detection
# - Data filtering operations
# - Memory cleanup activities
# - Session transition events
```

---

## Best Practices

### 1. Choose the Right Session Type
- **RTH**: Most day trading strategies, backtesting with realistic volume
- **ETH**: 24-hour strategies, overnight positions, global markets
- **CUSTOM**: Specific trading windows, exotic products

### 2. Handle Data Availability
```python
# Always check for None and empty DataFrames
mnq_context = suite["MNQ"]
data = await mnq_context.data.get_session_data("5min", SessionType.RTH)

if data is None:
    print("No data returned - check connection or initialization")
    return

if data.is_empty():
    print("Empty DataFrame - market may be closed or no RTH data")
    return

# Safe to process data
print(f"Processing {len(data)} RTH bars")
```

### 3. Error Handling
```python
try:
    mnq_context = suite["MNQ"]
    rth_data = await mnq_context.data.get_session_data("5min", SessionType.RTH)

    if rth_data is None or rth_data.is_empty():
        # Try ETH as fallback
        print("No RTH data, trying ETH...")
        eth_data = await mnq_context.data.get_session_data("5min", SessionType.ETH)

        if eth_data is not None and not eth_data.is_empty():
            print(f"Using ETH data: {len(eth_data)} bars")
            rth_data = eth_data
        else:
            raise ValueError("No session data available")

except Exception as e:
    print(f"Session data error: {e}")
    # Implement fallback strategy
```

### 4. Testing Your Strategy
```python
# Test with different session types
for session_type in [SessionType.RTH, SessionType.ETH]:
    # Create suite with specific session
    suite = await TradingSuite.create(
        "MNQ",
        timeframes=["5min"],
        session_config=SessionConfig(session_type=session_type),
        initial_days=5
    )

    try:
        mnq_context = suite["MNQ"]
        data = await mnq_context.data.get_session_data("5min", session_type)

        if data is not None and not data.is_empty():
            print(f"{session_type.value}: {len(data)} bars")
            # Run your strategy analysis here

    finally:
        await suite.disconnect()
```

---

## Migration Guide

### From Non-Session Code
```python
# OLD: No session awareness
suite = await TradingSuite.create("MNQ")
mnq_context = suite["MNQ"]
data = await mnq_context.data.get_data("5min")  # All data

# NEW: Session-aware
session_config = SessionConfig(session_type=SessionType.RTH)
suite = await TradingSuite.create(
    "MNQ",
    timeframes=["5min"],
    session_config=session_config,
    initial_days=5
)
mnq_context = suite["MNQ"]
data = await mnq_context.data.get_session_data("5min", SessionType.RTH)
```

### Backward Compatibility
All existing code continues to work without changes. The session system is additive:

```python
# This still works exactly as before
suite = await TradingSuite.create("MNQ")  # ETH by default (all hours except maintenance)
mnq_context = suite["MNQ"]
data = await mnq_context.data.get_data("5min")  # Returns all data

# New session features are opt-in
rth_only = await mnq_context.data.get_session_data("5min", SessionType.RTH)
eth_only = await mnq_context.data.get_session_data("5min", SessionType.ETH)
```

---

## Working Examples

Complete working examples are available in this directory:

1. **[01_basic_session_filtering.py](01_basic_session_filtering.py)** - Basic session filtering and market status
2. **[02_session_statistics.py](02_session_statistics.py)** - Session statistics and analytics
3. **[03_session_indicators.py](03_session_indicators.py)** - Session-aware technical indicators
4. **[04_session_comparison.py](04_session_comparison.py)** - RTH vs ETH comparison
5. **[05_multi_instrument_sessions.py](05_multi_instrument_sessions.py)** - Multi-instrument session management

## References

- **Core Module**: `project_x_py.sessions`
- **Configuration**: `project_x_py.sessions.config`
- **Filtering**: `project_x_py.sessions.filtering`
- **Analytics**: `project_x_py.sessions.analytics`
- **Statistics**: `project_x_py.sessions.statistics`
- **Indicators**: Functions exported from `project_x_py.sessions`

---

*This document covers version 3.5.5 of the session features. For updates and additional examples, see the project repository and test files.*
