# Data Manager API

Real-time data processing and management with WebSocket streaming, multi-timeframe support, and efficient memory management.

## Overview

The `ProjectXRealtimeDataManager` handles real-time market data streaming via WebSocket connections, processes OHLCV bar data across multiple timeframes, and provides efficient data access with automatic memory management.

## Quick Start

```python
from project_x_py import TradingSuite
import asyncio

async def basic_data_usage():
    # Create suite with real-time data
    suite = await TradingSuite.create(
        ["MNQ"],
        timeframes=["1min", "5min", "15min"]
    )

    # Access the integrated data manager for the specific instrument
    data_manager = suite["MNQ"].data

    # Get current price
    current_price = await data_manager.get_current_price()
    if current_price:
        print(f"Current MNQ Price: ${current_price:.2f}")

    # Get latest bars
    bars_1min = await data_manager.get_data("1min")
    bars_5min = await data_manager.get_data("5min")

    if bars_1min is not None:
        print(f"1min bars: {len(bars_1min)}")
    if bars_5min is not None:
        print(f"5min bars: {len(bars_5min)}")

    await suite.disconnect()

asyncio.run(basic_data_usage())
```

## Core Data Access Methods

### Getting Bar Data

```python
async def accessing_bar_data():
    suite = await TradingSuite.create(["MNQ"], timeframes=["1min", "5min"])
    mnq_data = suite["MNQ"].data

    # Get data for a specific timeframe (copy of the in-memory cache)
    bars = await mnq_data.get_data("1min")
    if bars is not None and not bars.is_empty():
        print(f"Retrieved {len(bars)} bars")

        latest_bar = bars.tail(1)
        print(f"Latest close: ${latest_bar['close'][0]:.2f}")

    # Limit to the most recent N bars
    recent_bars = await mnq_data.get_data("5min", bars=20)

    # Optional lock timeout (seconds). Default is data_lock_timeout (5.0).
    recent_or_stale = await mnq_data.get_data("1min", timeout=2.0)

    await suite.disconnect()

asyncio.run(accessing_bar_data())
```

### Current Price Methods

```python
async def price_access():
    suite = await TradingSuite.create(["MNQ"], timeframes=["1min"])
    mnq_data = suite["MNQ"].data

    # Get current price (from latest tick or bar)
    current_price = await mnq_data.get_current_price()
    if current_price:
        print(f"Current price: ${current_price:.2f}")

    # Get latest price from specific timeframe
    latest_price = await mnq_data.get_latest_price()
    if latest_price:
        print(f"Latest price: ${latest_price:.2f}")

    # Get price range statistics
    price_range = await mnq_data.get_price_range(
        timeframe="1min",
        bars=100  # Last 100 bars
    )
    if price_range:
        print(f"High: ${price_range['high']:.2f}")
        print(f"Low: ${price_range['low']:.2f}")
        print(f"Range: ${price_range['range']:.2f}")

    await suite.disconnect()

asyncio.run(price_access())
```

### Volume Statistics

```python
async def volume_stats():
    suite = await TradingSuite.create(["MNQ"], timeframes=["1min", "5min"])
    mnq_data = suite["MNQ"].data

    # Get volume statistics
    vol_stats = await mnq_data.get_volume_stats(timeframe="1min")
    if vol_stats:
        print(f"Total volume: {vol_stats['total']:,}")
        print(f"Average volume: {vol_stats['average']:.0f}")
        print(f"Relative to average: {vol_stats['relative']:.1%}")

    await suite.disconnect()

asyncio.run(volume_stats())
```

### Session-filtered bars

```python
from project_x_py import TradingSuite, SessionConfig, SessionType

async def session_bars():
    suite = await TradingSuite.create(
        ["MNQ"],
        timeframes=["1min", "5min"],
        session_config=SessionConfig(session_type=SessionType.RTH),
    )
    mnq = suite["MNQ"].data

    # Bounded: copies under the read lock (default 2s), then filters.
    # On timeout returns the last successful snapshot, or None.
    rth = await mnq.get_session_data("1min", SessionType.RTH)
    eth = await mnq.get_session_data("1min", SessionType.ETH, timeout=1.0)

    await suite.disconnect()

asyncio.run(session_bars())
```

`get_session_data()` will not hold the bar-cache lock while filtering, and it
will not wait forever if a writer is stuck. Configure the defaults with
`data_lock_timeout` and `session_data_timeout` on `DataManagerConfig`.

## Memory Management

### Memory Statistics and Control

```python
async def memory_management():
    suite = await TradingSuite.create(["MNQ"], timeframes=["1min", "5min"])
    mnq_data = suite["MNQ"].data

    # Get memory statistics
    memory_stats = await mnq_data.get_memory_stats()
    print(f"Total bars in memory: {memory_stats.total_bars:,}")
    print(f"Memory usage: {memory_stats.memory_usage_mb:.2f} MB")
    print(f"Cache efficiency: {memory_stats.cache_efficiency:.1%}")

    # Get resource statistics
    resource_stats = await mnq_data.get_resource_stats()
    print(f"CPU usage: {resource_stats['cpu_percent']:.1f}%")
    print(f"Threads: {resource_stats['num_threads']}")

    # Cleanup old data
    await mnq_data.cleanup()

    await suite.disconnect()

asyncio.run(memory_management())
```

### MMap Overflow Support

The data manager includes memory-mapped file overflow support for handling large datasets:

```python
async def overflow_configuration():
    from project_x_py.realtime_data_manager.types import DataManagerConfig

    # Configure with overflow enabled
    config = DataManagerConfig(
        enable_mmap_overflow=True,
        overflow_threshold=0.8,  # Overflow at 80% capacity
        mmap_storage_path="/path/to/overflow/storage"
    )

    suite = await TradingSuite.create(
        ["MNQ"],
        timeframes=["1min"],
        data_manager_config=config
    )

    mnq_data = suite["MNQ"].data

    # Monitor overflow statistics
    overflow_stats = await mnq_data.get_overflow_stats("1min")
    if overflow_stats:
        print(f"Bars overflowed: {overflow_stats['total_overflowed_bars']}")
        print(f"Disk usage: {overflow_stats['disk_storage_size_mb']:.2f} MB")

    await suite.disconnect()

asyncio.run(overflow_configuration())
```

## Performance Optimization

### DataFrame Optimization

The data manager includes built-in DataFrame optimization:

```python
async def dataframe_optimization():
    suite = await TradingSuite.create(["MNQ"], timeframes=["1min"])
    mnq_data = suite["MNQ"].data

    # Optimize data access patterns
    optimization_result = await mnq_data.optimize_data_access_patterns()
    print(f"Cache hits improved by: {optimization_result['cache_improvement']:.1%}")
    print(f"Access time reduced by: {optimization_result['time_reduction']:.1%}")

    await suite.disconnect()

asyncio.run(dataframe_optimization())
```

### Lock Optimization

```python
async def lock_optimization():
    suite = await TradingSuite.create(["MNQ"], timeframes=["1min"])
    mnq_data = suite["MNQ"].data

    # Get lock optimization statistics
    lock_stats = await mnq_data.get_lock_optimization_stats()
    print(f"Lock acquisitions: {lock_stats['total_acquisitions']}")
    print(f"Average wait time: {lock_stats['avg_wait_time_ms']:.2f}ms")
    print(f"Contention rate: {lock_stats['contention_rate']:.1%}")

    await suite.disconnect()

asyncio.run(lock_optimization())
```

## DST Handling

The data manager includes sophisticated Daylight Saving Time handling:

```python
async def dst_handling():
    from project_x_py.realtime_data_manager.types import DataManagerConfig

    # Configure with DST awareness
    config = DataManagerConfig(
        session_type="RTH",  # Regular Trading Hours
        timezone="America/New_York"
    )

    suite = await TradingSuite.create(
        ["MNQ"],
        timeframes=["1min"],
        data_manager_config=config
    )

    # DST transitions are handled automatically
    # The data manager will adjust bar timestamps and handle
    # missing/duplicate hours during transitions

    await suite.disconnect()

asyncio.run(dst_handling())
```

## Statistics and Monitoring

### Component Statistics

```python
async def component_statistics():
    suite = await TradingSuite.create(["MNQ"], timeframes=["1min", "5min"])
    mnq_data = suite["MNQ"].data

    # Get comprehensive statistics
    stats = await mnq_data.get_stats()
    print(f"Component: {stats.component_type}")
    print(f"Health score: {stats.health_score:.1f}/100")
    print(f"Uptime: {stats.uptime_seconds}s")

    # Performance metrics
    for metric, value in stats.performance_metrics.items():
        print(f"{metric}: {value}")

    # Get bounded statistics (with size limits)
    bounded_stats = await mnq_data.get_bounded_statistics()
    if bounded_stats:
        print(f"Recent operations: {bounded_stats['recent_operations']}")
        print(f"Error rate: {bounded_stats['error_rate']:.2%}")

    await suite.disconnect()

asyncio.run(component_statistics())
```

### Health Monitoring

```python
async def health_monitoring():
    suite = await TradingSuite.create(["MNQ"], timeframes=["1min"])
    mnq_data = suite["MNQ"].data

    # Get health score
    health_score = await mnq_data.get_health_score()
    print(f"Health score: {health_score:.1f}/100")

    if health_score < 80:
        print("Warning: Data manager health is degraded")

        # Check specific issues
        stats = await mnq_data.get_stats()
        if stats.error_count > 0:
            print(f"Errors detected: {stats.error_count}")

    await suite.disconnect()

asyncio.run(health_monitoring())
```

## Real-time Feed Management

### Starting and Stopping Feeds

```python
async def feed_management():
    suite = await TradingSuite.create(["MNQ"], timeframes=["1min"])
    mnq_data = suite["MNQ"].data

    # Start real-time feed
    success = await mnq_data.start_realtime_feed()
    if success:
        print("Real-time feed started")

    # Monitor feed for some time
    await asyncio.sleep(60)

    # Stop real-time feed
    await mnq_data.stop_realtime_feed()
    print("Real-time feed stopped")

    await suite.disconnect()

asyncio.run(feed_management())
```

## Data Validation

### Built-in Validation

```python
async def data_validation():
    suite = await TradingSuite.create(["MNQ"], timeframes=["1min"])
    mnq_data = suite["MNQ"].data

    # Data validation is performed automatically
    # Check validation statistics in memory stats
    memory_stats = await mnq_data.get_memory_stats()

    # Look for validation indicators
    if hasattr(memory_stats, 'validation_errors'):
        print(f"Validation errors: {memory_stats.validation_errors}")

    # Data readiness check
    bars = await mnq_data.get_data("1min")
    if bars is not None and len(bars) > 0:
        print("Data is ready and validated")

    await suite.disconnect()

asyncio.run(data_validation())
```

## Dynamic Resource Limits

The data manager includes dynamic resource management:

```python
async def dynamic_resources():
    suite = await TradingSuite.create(["MNQ"], timeframes=["1min"])
    mnq_data = suite["MNQ"].data

    # Resource limits adjust automatically based on:
    # - Available system memory
    # - CPU usage
    # - Data volume
    # - Number of active timeframes

    # Monitor resource adaptation
    resource_stats = await mnq_data.get_resource_stats()
    print(f"Current memory limit: {resource_stats['memory_limit_mb']:.0f} MB")
    print(f"Adjusted for load: {resource_stats['load_factor']:.2f}x")

    await suite.disconnect()

asyncio.run(dynamic_resources())
```

## Error Handling

### Proper Error Handling Patterns

```python
async def error_handling():
    suite = await TradingSuite.create(["MNQ"], timeframes=["1min"])
    mnq_data = suite["MNQ"].data

    try:
        # Always check for None returns
        data = await mnq_data.get_data("1min")
        if data is None:
            print("No data available yet")
            return

        # Check for empty DataFrames
        if data.is_empty():
            print("Data frame is empty")
            return

        # Safe data access
        if len(data) > 0:
            latest_price = data.tail(1)["close"][0]
            print(f"Latest price: ${latest_price:.2f}")

    except Exception as e:
        print(f"Error accessing data: {e}")

    finally:
        await suite.disconnect()

asyncio.run(error_handling())
```

## Configuration Options

### DataManagerConfig

```python
from project_x_py.realtime_data_manager.types import DataManagerConfig

# Full configuration example
config = DataManagerConfig(
    # Memory management
    max_bars_per_timeframe=1000,
    enable_mmap_overflow=True,
    overflow_threshold=0.8,
    mmap_storage_path="/path/to/storage",

    # Performance
    enable_caching=True,
    cache_size=100,
    optimization_interval=300,

    # DST handling
    session_type="RTH",
    timezone="America/New_York",

    # Resource limits
    enable_dynamic_limits=True,
    memory_threshold_percent=80.0,
    cpu_threshold_percent=70.0,

    # Validation
    validate_data=True,
    max_price_deviation=0.1,  # 10% max deviation

    # Cleanup
    cleanup_interval_seconds=300,
    retention_hours=24
)
```

## Best Practices

### Memory Efficiency

```python
# ✅ Good: Get only needed data
recent_bars = await suite["MNQ"].data.get_data("1min", count=100)

# ❌ Avoid: Getting all data when not needed
all_bars = await suite["MNQ"].data.get_data("1min")  # Gets everything
```

### Null Checking

```python
# ✅ Good: Always check for None
data = await suite["MNQ"].data.get_data("1min")
if data is not None and not data.is_empty():
    # Process data
    pass

# ❌ Bad: Assuming data exists
data = await suite["MNQ"].data.get_data("1min")
latest = data.tail(1)  # May fail if data is None
```

### Resource Cleanup

```python
# ✅ Good: Always cleanup
try:
    suite = await TradingSuite.create(["MNQ"])
    # Use suite
finally:
    await suite.disconnect()

# ✅ Better: Use context manager (if available)
async with await TradingSuite.create(["MNQ"]) as suite:
    # Suite automatically cleaned up
    pass
```

## Performance Tips

1. **Use appropriate timeframes** - Don't subscribe to more timeframes than needed
2. **Enable caching** - For frequently accessed data
3. **Configure overflow** - For long-running sessions with lots of data
4. **Monitor health** - Check health scores regularly
5. **Cleanup regularly** - Use automatic cleanup for long sessions

## See Also

- [Trading Suite API](trading-suite.md) - Main trading interface
- [Real-time Guide](../guide/realtime.md) - Real-time data concepts
- [Examples](../../examples/) - Complete working examples
