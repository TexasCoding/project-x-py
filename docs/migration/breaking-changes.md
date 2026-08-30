# Breaking Changes

This document lists all breaking changes introduced in ProjectX Python SDK releases, providing migration paths and timelines for deprecated features.

## v4.0.0 - Major Release (Shipped 2026-08-29)

**Release Date**: 2026-08-29
**Canonical guide**: [Migration Guide: v3.x to v4.0](v3-to-v4.md)

v4.0 is the TopstepX-only Gateway revival. Use the migration guide for the full upgrade checklist. The changes that actually shipped:

| Removed or changed | Use instead |
|------|------|
| `suite.get_stats_sync()` | `await suite.get_stats()` or `await suite.export_stats()` |
| Import-time `uvloop.install()` | Optional extra: `pip install project-x-py[uvloop]` |
| `suite.journal` / `suite.analytics` | Removed. `Features.TRADE_JOURNAL` and `Features.AUTO_RECONNECT` warn and have no effect |
| Auth TypedDict field `jwt` | Gateway field is `token` |
| Instrument search TypedDict `instruments` | Gateway field is `contracts` |
| signalrcore + websocket-client | pysignalr |
| User-Agent `ProjectX-Python-SDK/2.0.0` | `ProjectX-Python-SDK/4.0.0` |

There is no `migrate_to_v4.py` script. Suite statistics are `get_stats()` / `export_stats()`, not `get_statistics()`.

Single-instrument `suite.data` / `suite.orders` / `suite.positions` are official accessors. Multi-instrument still uses `suite["MNQ"]`.

### Statistics System (already async since v3.3)

v3.3 made statistics async. v4 only removes the leftover sync wrapper:

```python
# v3.x
stats = suite.get_stats_sync()  # removed in 4.0

# v4
stats = await suite.get_stats()
payload = await suite.export_stats("json")
```

### DataFrame Library Changes

**BREAKING**: Pandas support removed, Polars becomes the only supported DataFrame library.

#### What Changed

**Before (v3.x)**:
```python
import pandas as pd
# Could work with either pandas or polars
bars = await client.get_bars("MNQ")
if isinstance(bars, pd.DataFrame):
    bars['sma'] = bars['close'].rolling(20).mean()
```

**After (v4.0)**:
```python
import polars as pl
from project_x_py.indicators import SMA
# Always returns Polars DataFrame
bars = await client.get_bars("MNQ")
sma_values = bars.pipe(SMA, period=20)
```

#### Impact Level: **MEDIUM**

Code using pandas operations must be converted to Polars equivalents.

#### Migration Path

1. **Replace pandas imports** with polars
2. **Convert DataFrame operations** to Polars syntax
3. **Use built-in indicators** instead of manual calculations
4. **Update type annotations** from `pd.DataFrame` to `pl.DataFrame`

### Legacy Mixin Removal

**BREAKING**: Legacy statistics mixins removed.

#### What Changed

**Removed Classes**:
- `EnhancedStatsTrackingMixin` L
- `StatsTrackingMixin` L
- `LegacyStatsManager` L

**Replacement**:
- Use new `BaseStatisticsTracker` and `ComponentCollector` system

#### Impact Level: **LOW**

Only affects code directly using these internal mixins.

## v3.3.0 - Statistics System Overhaul (Released 2025-01-21)

### Async Statistics Implementation

**BREAKING**: Statistics methods changed from synchronous to asynchronous.

#### What Changed

All statistics-related methods now require `await`:

```python
# v3.2.x and earlier
stats = suite.get_stats()                    # L Removed
health = component.get_health_score()       # L Removed
memory = manager.get_memory_stats()         # L Removed

# v3.3.0+
stats = await suite.get_statistics()        #  New async method
health = await component.get_health_score() #  Now async
memory = await manager.get_memory_stats()   #  Now async
```

#### Migration Required

1. Add `await` to all statistics calls
2. Make calling functions async
3. Update tests to use `@pytest.mark.asyncio`

### Legacy Statistics Mixins Deprecated

**DEPRECATED**: Old statistics mixins marked for removal in v4.0.0.

```python
# These are deprecated and will be removed
from project_x_py.utils import EnhancedStatsTrackingMixin  #  Deprecated
from project_x_py.utils import StatsTrackingMixin          #  Deprecated
```

**Replacement**: Use new `BaseStatisticsTracker` system.

## v3.2.0 - Type System Enhancement (Released 2025-08-17)

### Type Hierarchy Changes

**BREAKING**: Updated type relationships between client protocols.

#### What Changed

**Before**:
```python
class MyClient(ProjectXBase):  # L No longer valid
    pass
```

**After**:
```python
from project_x_py.types import ProjectXClientProtocol

class MyClient(ProjectXClientProtocol):  #  Use protocol
    pass
```

#### Impact Level: **LOW**

Only affects custom client implementations.

### Response Type Handling

**BREAKING**: Improved handling of `dict|list` union response types.

#### What Changed

Response handling now properly handles union types:

```python
# This now works correctly in all cases
response = await client.api_call()  # Returns Dict[str, Any] | List[Dict]
if isinstance(response, dict):
    # Handle dict response
    pass
elif isinstance(response, list):
    # Handle list response
    pass
```

## v3.1.0 - Event System Enhancement (Released 2025-01-15)

### Event Data Structure Changes

**BREAKING**: Event data structures updated for consistency.

#### What Changed

**Before**:
```python
async def handle_order_fill(event):
    order_id = event.data.order_id  # L Sometimes missing
    # Inconsistent data structure
```

**After**:
```python
async def handle_order_fill(event):
    # Handle both structures for backward compatibility
    order_id = event.data.get('order_id') or event.data.get('order', {}).get('id')
    fill_price = event.data.get('fill_price', 0)
```

#### Impact Level: **MEDIUM**

Event handlers need to handle both data structures during transition period.

## v3.0.0 - TradingSuite Introduction (Released 2024-12-15)

### TradingSuite Unified API

**BREAKING**: Introduction of `TradingSuite` as the primary API entry point.

#### What Changed

**Before (v2.x)**:
```python
# Multiple separate components
client = ProjectX.from_env()
order_manager = OrderManager(client)
position_manager = PositionManager(client)
data_manager = RealtimeDataManager(...)

# Manual connection management
await client.authenticate()
await data_manager.start()
```

**After (v3.0)**:
```python
# Single unified interface
suite = await TradingSuite.create("MNQ", timeframes=["1min"])
# Everything is connected and ready

# Access components through suite
await suite.orders.place_market_order(...)
position = await suite.positions.get_position("MNQ")
bars = await suite.data.get_data("1min")
```

#### Impact Level: **HIGH**

Complete restructuring of how components are initialized and used.

#### Migration Path

1. **Replace separate component initialization** with `TradingSuite.create()`
2. **Update component access** to use suite properties
3. **Remove manual connection management** code
4. **Update import statements**

### OrderBook Integration

**BREAKING**: OrderBook now requires explicit feature flag.

#### What Changed

**Before**: OrderBook was always available
**After**: Must be explicitly enabled:

```python
# Enable orderbook feature
suite = await TradingSuite.create(
    "MNQ",
    features=["orderbook"]  # Explicit feature flag
)

if hasattr(suite, 'orderbook'):
    book_data = await suite.orderbook.get_book_snapshot()
```

## v2.4.0 - Package Structure Refactor (Released 2024-10-01)

### Multi-file Package Structure

**BREAKING**: Converted monolithic modules to multi-file packages.

#### What Changed

**Before**:
```python
from project_x_py.order_manager import OrderManager        # L Old structure
from project_x_py.position_manager import PositionManager  # L Old structure
```

**After**:
```python
from project_x_py.order_manager import OrderManager        #  Works (re-exported)
from project_x_py.position_manager import PositionManager  #  Works (re-exported)

# Or import from new package structure
from project_x_py.order_manager.core import OrderManager
from project_x_py.position_manager.core import PositionManager
```

#### Impact Level: **LOW**

Public imports remained the same due to re-exports.

## v2.0.0 - Async-First Architecture (Released 2024-06-01)

### Complete Async Migration

**BREAKING**: Removed all synchronous APIs.

#### What Changed

**Before (v1.x)**:
```python
# Synchronous methods available
client = ProjectX()
client.authenticate()                    # L Removed
bars = client.get_bars("MNQ")           # L Removed
orders = client.get_orders()            # L Removed
```

**After (v2.0)**:
```python
# Only async methods available
async with ProjectX.from_env() as client:
    await client.authenticate()          #  Async only
    bars = await client.get_bars("MNQ")  #  Async only
    orders = await client.get_orders()   #  Async only
```

#### Impact Level: **HIGH**

Complete rewrite of client code required.

### Context Manager Requirement

**BREAKING**: Client must be used as async context manager.

#### What Changed

**Before**:
```python
client = ProjectX()
# Manual resource management
```

**After**:
```python
async with ProjectX.from_env() as client:
    # Automatic resource management
    pass
```

## Deprecation Policy

### Deprecation Timeline

The ProjectX SDK follows a structured deprecation policy:

1. **Deprecation Warning** (Minor release): Feature marked as deprecated
2. **Grace Period** (2 minor versions): Feature still works but logs warnings
3. **Removal** (Next major release): Feature completely removed

### Current Deprecations

#### Active Deprecations (Will be removed in v4.0)

| Feature | Deprecated In | Removal In | Replacement |
|---------|---------------|------------|-------------|
| `EnhancedStatsTrackingMixin` | v3.1.0 | v4.0.0 | `BaseStatisticsTracker` |
| `StatsTrackingMixin` | v3.1.0 | v4.0.0 | `BaseStatisticsTracker` |
| Pandas DataFrame support | v3.2.0 | v4.0.0 | Polars DataFrames |

#### Recently Removed

| Feature | Deprecated In | Removed In | Replacement |
|---------|---------------|------------|-------------|
| Sync statistics methods | v3.1.0 | v3.3.0 | Async statistics methods |
| Legacy event data format | v3.0.0 | v3.1.0 | New event structure |

### Deprecation Warnings

When using deprecated features, you'll see warnings like:

```python
DeprecationWarning: EnhancedStatsTrackingMixin is deprecated since v3.1.0
and will be removed in v4.0.0. Use BaseStatisticsTracker instead.
```

## Migration Tools

### Automated Migration Scripts

```bash
# Download migration tools
git clone https://github.com/TexasCoding/project-x-py-migration-tools.git

# Run migration for specific version
python migrate_to_v3.py --input ./your_code --output ./migrated_code
python migrate_to_v4.py --input ./your_code --output ./migrated_code

# Check for deprecation usage
python check_deprecated_usage.py ./your_code
```

### IDE Support

Install the ProjectX migration extension for VS Code:

```bash
code --install-extension projectx.migration-helper
```

Features:
- Highlights deprecated API usage
- Provides quick fixes for common migrations
- Shows replacement suggestions

## Testing Migrations

### Backward Compatibility Testing

```python
import pytest
from project_x_py import TradingSuite

@pytest.mark.asyncio
async def test_backward_compatibility():
    """Test that migrated code works correctly."""

    # Test v3.x style usage still works
    suite = await TradingSuite.create("MNQ")

    # Test new async statistics
    stats = await suite.get_statistics()
    assert isinstance(stats, dict)

    # Test Polars integration
    bars = await suite.data.get_data("1min")
    assert hasattr(bars, 'pipe')  # Polars DataFrame method

    print(" Migration compatibility test passed")
```

### Version Compatibility Matrix

| Your Code Version | SDK Version | Compatible | Notes |
|-------------------|-------------|------------|-------|
| v1.x code | v2.0+ | L | Complete rewrite required |
| v2.x code | v3.0+ |  | TradingSuite migration needed |
| v3.0 code | v3.3+ |  | Minor async statistics changes |
| v3.x code | v4.0+ |  | Statistics system migration needed |

## Getting Migration Help

### Resources

1. **Migration Guides**: Detailed guides in [docs/migration/](./v3-to-v4.md)
2. **Examples**: Updated examples for each version
3. **Migration Scripts**: Automated conversion tools
4. **Community Support**: GitHub Discussions and Issues

### Professional Migration Support

For enterprise clients requiring migration assistance:

- **Migration Planning**: Architecture review and migration strategy
- **Code Conversion**: Professional code migration services
- **Testing Support**: Comprehensive migration testing
- **Training**: Team training on new APIs and patterns

Contact: [support@projectx.com](mailto:support@projectx.com)

## Summary

Breaking changes are introduced thoughtfully with:

- **Clear migration paths** for all breaking changes
- **Automated migration tools** where possible
- **Extended support periods** for deprecated features
- **Comprehensive documentation** and examples
- **Community support** throughout migration process

The ProjectX SDK's evolution ensures you always have access to the most modern, performant, and secure trading infrastructure while providing smooth upgrade paths.
