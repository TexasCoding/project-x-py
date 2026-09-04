# Trading Sessions Guide

!!! warning "Experimental Feature"
    The ETH vs RTH Trading Sessions feature is experimental and has not been thoroughly tested with live market data. Use with caution in production environments. Session boundaries may need adjustment based on specific contract specifications.

## Overview

The Trading Sessions module enables you to filter and analyze market data based on different trading sessions:

- **RTH (Regular Trading Hours)**: Pit hours (typically 9:30 AM - 4:00 PM ET for equity index futures)
- **ETH (Electronic Trading Hours)**: All hours except the daily maintenance break
- **CUSTOM**: Caller-supplied `SessionTimes`

This feature is particularly useful for:
- Separating overnight volatility from regular session price action
- Calculating session-specific technical indicators
- Analyzing volume profiles by session type
- Backtesting strategies with session-aware logic

## Quick Start

### Basic Session Filtering

```python
from project_x_py.sessions import SessionConfig, SessionType, SessionFilterMixin
import polars as pl

# Create session configurations
rth_config = SessionConfig(session_type=SessionType.RTH)
eth_config = SessionConfig(session_type=SessionType.ETH)

# Initialize filter
session_filter = SessionFilterMixin()

# Filter data by session (async method)
rth_data = await session_filter.filter_by_session(
    data,
    SessionType.RTH,
    "ES",
)

eth_data = await session_filter.filter_by_session(
    data,
    SessionType.ETH,
    "ES"
)
```

## Session Configuration

### SessionType Enum

```python
from project_x_py.sessions import SessionType

SessionType.RTH     # Regular Trading Hours only
SessionType.ETH     # Electronic Trading Hours (excludes maintenance)
SessionType.CUSTOM  # Caller-supplied SessionTimes
```

### Product-Specific Sessions

Different futures products have different session schedules:

```python
from project_x_py.sessions import SessionConfig, DEFAULT_SESSIONS

# Access predefined session times
equity_times = DEFAULT_SESSIONS["ES"]  # ES, NQ, MNQ, MES
energy_times = DEFAULT_SESSIONS["CL"]  # CL, NG
treasury_times = DEFAULT_SESSIONS["ZN"]  # ZN, ZB

# Create config with product-specific times
config = SessionConfig(
    session_type=SessionType.RTH
)

# Get session times for a product
session_times = config.get_session_times("ES")
print(f"RTH: {session_times.rth_start} - {session_times.rth_end}")
```

### Custom Session Times

```python
from project_x_py.sessions import SessionTimes
from datetime import time

# Define custom session times
custom_times = SessionTimes(
    rth_start=time(9, 0),   # 9:00 AM
    rth_end=time(15, 30),    # 3:30 PM
    eth_start=time(18, 0),   # 6:00 PM
    eth_end=time(17, 0)      # 5:00 PM next day
)

# Use custom times in config
custom_config = SessionConfig(
    session_type=SessionType.RTH,
    session_times=custom_times
)
```

### Checking Market Status

```python
from datetime import datetime, timezone

config = SessionConfig(session_type=SessionType.RTH)

# Check if market is open
timestamp = datetime.now(timezone.utc)
is_open = config.is_market_open(timestamp, "ES")

# Get current session
current = config.get_current_session(timestamp, "ES")
# Returns: "RTH", "ETH", or "BREAK"
```

## Session-Aware Indicators

### Session VWAP Calculation

```python
from project_x_py.sessions import calculate_session_vwap

# Calculate VWAP for RTH session only
rth_vwap_data = await calculate_session_vwap(
    data,
    SessionType.RTH,
    "ES"
)
# Adds 'session_vwap' column to DataFrame
```

### Anchored VWAP

```python
from project_x_py.sessions import calculate_anchored_vwap

# Anchor VWAP to session open
anchored_data = await calculate_anchored_vwap(
    data,
    anchor_point="session_open"  # or "session_high", "session_low"
)
# Adds 'anchored_vwap' column
```

### Session Levels

```python
from project_x_py.sessions import calculate_session_levels

# Calculate session high/low/open/close
levels_data = await calculate_session_levels(data)
# Adds columns: 'session_high', 'session_low', 'session_open', 'session_close'
```

### Cumulative Volume

```python
from project_x_py.sessions import calculate_session_cumulative_volume

# Calculate cumulative volume within sessions
volume_data = await calculate_session_cumulative_volume(data)
# Adds 'cumulative_volume' column that resets at session boundaries
```

### Session-Relative Indicators

```python
from project_x_py.sessions import (
    calculate_relative_to_vwap,
    calculate_percent_from_open
)

# Calculate price relative to VWAP
relative_data = await calculate_relative_to_vwap(data)
# Adds 'relative_to_vwap' column (percentage above/below VWAP)

# Calculate percent change from session open
percent_data = await calculate_percent_from_open(data)
# Adds 'percent_from_open' column
```

## Session Statistics

### Basic Statistics

```python
from project_x_py.sessions import SessionStatistics

# Initialize statistics calculator
stats = SessionStatistics()

# Calculate session statistics
session_stats = await stats.calculate_session_stats(data, "ES")

# Returns dictionary with:
# - rth_volume, eth_volume
# - rth_vwap, eth_vwap
# - rth_high, rth_low, rth_range
# - eth_high, eth_low, eth_range
```

### Session Analytics

```python
from project_x_py.sessions import SessionAnalytics

analytics = SessionAnalytics()

# Compare RTH vs ETH sessions
comparison = await analytics.compare_sessions(data, "ES")
# Returns volume ratios, volatility comparison, etc.

# Get volume profile by hour
volume_profile = await analytics.get_session_volume_profile(data, "ES")
# Returns hourly volume distribution

# Analyze session volatility
volatility = await analytics.analyze_session_volatility(data, "ES")
# Returns volatility metrics by session

# Analyze gaps between sessions
gaps = await analytics.analyze_session_gaps(data, "ES")
# Returns gap statistics

# Calculate efficiency metrics
efficiency = await analytics.calculate_efficiency_metrics(data, "ES")
# Returns session efficiency indicators
```

## Advanced Usage

### Session Alert Generation

```python
from project_x_py.sessions import generate_session_alerts

# Define alert conditions
conditions = {
    "breakout": "close > sma_10",
    "overbought": "rsi_14 > 70",
    "at_high": "high == session_high"
}

# Generate alerts based on conditions
alerts_data = await generate_session_alerts(data, conditions)
# Adds 'alerts' column with triggered alert names
```

### Time Aggregation with Sessions

```python
from project_x_py.sessions import aggregate_with_sessions

# Aggregate 1-minute bars to 5-minute with session awareness
aggregated = await aggregate_with_sessions(
    data,
    timeframe="5min",
    session_type=SessionType.RTH
)
# Ensures aggregation respects session boundaries
```

### Manual Session Filtering

```python
from project_x_py.sessions import SessionFilterMixin, SessionType
from datetime import datetime, timezone

# Create filter instance
filter_mixin = SessionFilterMixin()

# Async batch filtering
filtered_data = await filter_mixin.filter_by_session(
    data,
    SessionType.RTH,
    "ES",
    custom_session_times=custom_times  # Optional
)
```

## Live `get_session_data` (v4.2.1+)

Call this from `on_bar`. It copies bars under a **bounded** read lock
(default 2 seconds), then filters after the lock is released:

```python
from project_x_py.sessions import SessionType

rth = await suite["MNQ"].data.get_session_data("1min", SessionType.RTH)
# optional: timeout=1.0
```

If the bar cache is mid-update and the lock does not release in time, the
call returns the last successful snapshot (or `None` on the first attempt)
instead of hanging. Configure defaults with `session_data_timeout` and
`data_lock_timeout` on the data-manager config.

`session_type` may be omitted; it then uses `session_config.session_type`.
Gateway contract ids (`CON.F.US.MNQ.H26`) resolve to the product calendar
via `resolve_session_product()`.

## Performance Considerations

### Caching and Optimization

The session filtering system includes several optimizations:

1. **Boundary Caching**: Session boundaries are cached to avoid recalculation
2. **Lazy Evaluation**: Large datasets (>100k rows) use lazy evaluation
3. **Efficient Filtering**: Uses Polars' vectorized operations for speed

```python
# The system automatically optimizes based on data size
large_data = pl.DataFrame(...)  # 100k+ rows

# Automatically uses lazy evaluation for large datasets
filtered = await filter_mixin.filter_by_session(
    large_data,
    SessionType.RTH,
    "ES"
)
```

### Memory Management

```python
# For very large datasets, process in chunks
async def process_large_dataset(data: pl.DataFrame):
    filter_mixin = SessionFilterMixin()

    # Split into daily chunks
    for date in data['timestamp'].dt.date().unique():
        daily_data = data.filter(pl.col('timestamp').dt.date() == date)

        # Process daily chunk
        rth_daily = await filter_mixin.filter_by_session(
            daily_data,
            SessionType.RTH,
            "ES"
        )

        # Process and clear memory
        process_day(rth_daily)
        del daily_data, rth_daily
```

## Complete Examples

### Example: Session Comparison

```python
import asyncio
import polars as pl
from datetime import datetime, timedelta, timezone
from project_x_py.sessions import (
    SessionFilterMixin,
    SessionStatistics,
    SessionAnalytics,
    SessionType,
    calculate_session_vwap
)

async def compare_sessions(data: pl.DataFrame):
    # Initialize components
    filter_mixin = SessionFilterMixin()
    stats = SessionStatistics()
    analytics = SessionAnalytics()

    # Filter data by session
    rth_data = await filter_mixin.filter_by_session(
        data, SessionType.RTH, "ES"
    )
    eth_data = await filter_mixin.filter_by_session(
        data, SessionType.ETH, "ES"
    )

    # Check for empty data
    if rth_data is None or rth_data.is_empty() or eth_data is None or eth_data.is_empty():
        print("Insufficient data for comparison")
        return

    # Calculate VWAPs
    rth_vwap = await calculate_session_vwap(rth_data, SessionType.RTH, "ES")
    eth_vwap = await calculate_session_vwap(eth_data, SessionType.ETH, "ES")

    # Get statistics
    session_stats = await stats.calculate_session_stats(data, "ES")

    # Compare sessions
    comparison = await analytics.compare_sessions(data, "ES")

    if session_stats and comparison:
        print(f"RTH Volume: {session_stats.get('rth_volume', 0):,}")
        print(f"ETH Volume: {session_stats.get('eth_volume', 0):,}")
        print(f"RTH Range: ${session_stats.get('rth_range', 0):.2f}")
        print(f"ETH Range: ${session_stats.get('eth_range', 0):.2f}")
        if 'rth_vs_eth_volume_ratio' in comparison:
            print(f"Volume Ratio: {comparison['rth_vs_eth_volume_ratio']:.2f}")

# Run example
# asyncio.run(compare_sessions(your_data))
```

### Example: Overnight Gap Analysis

```python
from project_x_py.sessions import SessionFilterMixin, SessionType

async def analyze_overnight_gaps(data: pl.DataFrame):
    filter_mixin = SessionFilterMixin()

    # Get Friday RTH close
    friday_rth = await filter_mixin.filter_by_session(
        data.filter(pl.col('timestamp').dt.weekday() == 5),
        SessionType.RTH,
        "ES"
    )

    # Get Monday RTH open
    monday_rth = await filter_mixin.filter_by_session(
        data.filter(pl.col('timestamp').dt.weekday() == 1),
        SessionType.RTH,
        "ES"
    )

    if friday_rth is not None and not friday_rth.is_empty() and monday_rth is not None and not monday_rth.is_empty():
        friday_close = friday_rth['close'][-1]
        monday_open = monday_rth['open'][0]

        gap = monday_open - friday_close
        gap_pct = (gap / friday_close) * 100

        print(f"Weekend Gap: ${gap:.2f} ({gap_pct:.2%})")

        # Trading decision based on gap
        if abs(gap_pct) > 0.5:  # 0.5% gap threshold
            print(f"Significant gap detected - consider fade strategy")
```

## Best Practices

### 1. Use Async Methods

All public indicator functions are async for consistency:

```python
# Correct - use await
vwap_data = await calculate_session_vwap(data, SessionType.RTH, "ES")

# The module handles async operations internally for optimal performance
```

### 2. Handle Empty Results

Always check for None and empty DataFrames after filtering:

```python
rth_data = await filter_mixin.filter_by_session(data, SessionType.RTH, "ES")

if rth_data is None or rth_data.is_empty():
    print("No RTH data available - market may be closed")
    return
```

### 3. Consider Time Zones

Session times are in Eastern Time by default:

```python
from pytz import timezone

# Check current time in ET
et = timezone("US/Eastern")
current_et = datetime.now(et)

# SessionConfig handles timezone conversion automatically
config = SessionConfig(market_timezone="US/Eastern")
```

### 4. Use Product-Specific Sessions

Different products have different trading hours:

```python
# Always specify the product for accurate session times
config = SessionConfig(session_type=SessionType.RTH)

# Get correct session times for each product
es_times = config.get_session_times("ES")  # 9:30 AM - 4:00 PM ET
cl_times = config.get_session_times("CL")  # 9:00 AM - 2:30 PM ET
gc_times = config.get_session_times("GC")  # 8:20 AM - 1:30 PM ET
```

## Troubleshooting

### Common Issues

1. **No data returned for session**
   ```python
   # Check if timestamp is in session
   config = SessionConfig(session_type=SessionType.RTH)
   if not config.is_market_open(datetime.now(timezone.utc), "ES"):
       print("Market is closed for RTH session")
   ```

2. **Incorrect session boundaries**
   ```python
   # Verify session times for your product
   config = SessionConfig()
   times = config.get_session_times("YOUR_PRODUCT")
   print(f"RTH: {times.rth_start} - {times.rth_end}")
   print(f"ETH: {times.eth_start} - {times.eth_end}")
   ```

3. **Performance issues with large datasets**
   ```python
   # The module automatically optimizes for datasets > 100k rows
   # For manual control, check data size:
   if len(data) > 100_000:
       print("Large dataset - using lazy evaluation")
   ```

### Debug Logging

```python
import logging

# Enable debug logging for sessions module
logging.getLogger("project_x_py.sessions").setLevel(logging.DEBUG)

# This will show:
# - Session boundary calculations
# - Filter application details
# - Cache hit/miss information
# - Optimization decisions
```

## API Reference

### Core Classes

- `SessionConfig`: Configuration for session types and times
- `SessionTimes`: Definition of session start/end times
- `SessionType`: Enum for RTH, ETH, CUSTOM
- `SessionFilterMixin`: Main filtering functionality
- `SessionStatistics`: Statistical calculations by session
- `SessionAnalytics`: Advanced analytics and comparisons

### Public Functions

All functions are async and exported from `project_x_py.sessions`:

- `calculate_session_vwap()`: Session-aware VWAP
- `calculate_anchored_vwap()`: Anchored VWAP calculations
- `calculate_session_levels()`: High/low/open/close levels
- `calculate_session_cumulative_volume()`: Cumulative volume
- `calculate_relative_to_vwap()`: Price relative to VWAP
- `calculate_percent_from_open()`: Percent change from open
- `aggregate_with_sessions()`: Time-based aggregation
- `generate_session_alerts()`: Alert generation system

## See Also

- [Session Examples](https://github.com/TexasCoding/project-x-py/tree/main/examples/sessions/) - Complete working examples
  - `01_basic_session_filtering.py` - Basic filtering and market status
  - `02_session_statistics.py` - Session statistics and analytics
  - `03_session_indicators.py` - Session-aware technical indicators
  - `04_session_comparison.py` - RTH vs ETH comparison
  - `05_multi_instrument_sessions.py` - Multi-instrument session management
- [Indicators Guide](indicators.md) - Technical indicator calculations
- [Architecture Documentation](../development/architecture.md) - System design
