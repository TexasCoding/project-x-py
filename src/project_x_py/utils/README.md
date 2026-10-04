# Utilities Package

This package contains generic utility functions that provide common functionality across the ProjectX SDK.

## Architecture Principles

### What Belongs in Utils

Utility functions should:
- Be generic and reusable across different contexts
- Work with standard data types (DataFrames, numbers, strings)
- Have no domain-specific knowledge
- Be stateless and pure functions
- Not depend on specific ProjectX models or types

Examples:
- Mathematical calculations (`trading_calculations.py`)
- Data formatting and display (`formatting.py`)
- Environment variable handling (`environment.py`)
- Generic data transformations (`data_utils.py`)

### What Doesn't Belong in Utils

Domain-specific functionality should be in its respective module:
- Orderbook-specific analysis → `orderbook/` package
- Position management logic → `position_manager/` package
- Order handling → `order_manager/` package
- Real-time data processing → `realtime_data_manager/` package

## Module Overview

### Core Utilities

- **async_rate_limiter.py**: Async-safe rate limiting for API calls
- **data_utils.py**: DataFrame transformations and data manipulation
- **environment.py**: Environment variable configuration helpers
- **formatting.py**: Price, quantity, and display formatting
- **logging_utils.py**: Logging configuration and helpers
- **trading_calculations.py**: Generic trading math (tick values, position sizing)

### Analysis Utilities

- **pattern_detection.py**: Technical pattern detection algorithms
- **portfolio_analytics.py**: Portfolio-level calculations and metrics
- **market_utils.py**: Market session and trading hour utilities

Note: Market microstructure analysis (bid-ask spread, volume profile) has been moved to the orderbook package:
- `orderbook.analytics.MarketAnalytics.analyze_dataframe_spread()` - Analyze spread from any DataFrame
- `orderbook.profile.VolumeProfile.calculate_dataframe_volume_profile()` - Calculate volume distribution

## Usage Guidelines

1. **Keep it Simple**: Utilities should do one thing well
2. **Type Safety**: Use type hints for all parameters and returns
3. **Documentation**: Include docstrings with examples
4. **Testing**: All utilities must have comprehensive unit tests
5. **No Side Effects**: Utilities should not modify global state

## Examples

### Using Trading Calculations
```python
from project_x_py.utils import calculate_tick_value, round_to_tick_size

# Calculate dollar value of price movement
tick_value = calculate_tick_value(
    price_change=0.5,  # 5 tick move
    tick_size=0.1,  # MGC tick size
    tick_value=1.0,  # $1 per tick
)  # Returns: 5.0

# Round price to valid tick
price = round_to_tick_size(2050.37, 0.1)  # Returns: 2050.4
```

### Using Market Analysis
```python
from project_x_py.orderbook import MarketAnalytics
import polars as pl

# Analyze spread from historical data
data = pl.DataFrame({"bid": [100.0, 100.1, 100.2], "ask": [100.2, 100.3, 100.4]})

# Use static method for DataFrame analysis
spread_stats = MarketAnalytics.analyze_dataframe_spread(data)
print(f"Average spread: {spread_stats['avg_spread']}")
```

## Future Development

When adding new utilities:
1. Ensure they follow the principles above
2. Add comprehensive tests
3. Update this documentation
4. Consider if functionality belongs in a domain module instead
