# Real-time Data Guide

This guide covers comprehensive real-time data streaming using ProjectX Python SDK v4+. All real-time operations are fully asynchronous and provide high-performance WebSocket connectivity with automatic reconnection, memory management, and enhanced event forwarding for multi-instrument support.

## Overview

The ProjectXRealtimeDataManager provides complete real-time market data streaming including OHLCV bars, tick data, price updates, and multi-timeframe synchronization. All operations are designed for high-frequency trading applications with minimal latency.

### Key Features

- **Multi-timeframe Streaming**: Simultaneous data across multiple timeframes
- **WebSocket Connectivity**: High-performance async WebSocket connections
- **Automatic Memory Management**: Sliding windows with automatic cleanup
- **Event-Driven Architecture**: Real-time callbacks for all data updates
- **Data Synchronization**: Synchronized updates across timeframes
- **Performance Optimization**: DataFrame caching and lock optimization
- **DST Handling**: Automatic Daylight Saving Time transition management
- **MMap Overflow**: Disk-based overflow for large datasets
- **Dynamic Resource Limits**: Adaptive memory and CPU management

## Getting Started

### Basic Real-time Setup

```python
import asyncio
from project_x_py import TradingSuite

async def basic_realtime_setup():
    # Initialize with real-time capabilities
    suite = await TradingSuite.create(
        "MNQ",
        timeframes=["1min", "5min", "15min"],  # Multiple timeframes
        initial_days=2  # Historical data for context
    )

    # Real-time data manager is automatically initialized and connected
    data_manager = suite.data

    print("Real-time connection established!")

    # Get current price
    current_price = await data_manager.get_current_price()
    if current_price:
        print(f"Current MNQ price: ${current_price:.2f}")

    # Get recent data
    recent_1min = await data_manager.get_data("1min", count=10)
    if recent_1min is not None:
        print(f"Last 10 1-minute bars: {len(recent_1min)} rows")

    await suite.disconnect()

asyncio.run(basic_realtime_setup())
```

### Health Monitoring

Monitor the health and status of the real-time data manager:

```python
async def health_monitoring():
    suite = await TradingSuite.create("MNQ")

    # Get health score (0-100)
    health_score = await suite.data.get_health_score()
    print(f"Health Score: {health_score:.1f}/100")

    # Get comprehensive statistics
    stats = await suite.data.get_stats()
    print(f"Component Status: {stats.status}")
    print(f"Uptime: {stats.uptime_seconds}s")
    print(f"Error Count: {stats.error_count}")

    # Memory statistics
    memory_stats = await suite.data.get_memory_stats()
    print(f"Total Bars: {memory_stats.total_bars:,}")
    print(f"Memory Usage: {memory_stats.memory_usage_mb:.2f} MB")

    await suite.disconnect()

asyncio.run(health_monitoring())
```

`suite.data.get_health_score()` is the **data manager** score. WebSocket hub
health is `await suite.realtime.get_health_status()`. As of v4.3.0 that
score drops when a hub's `run()` task is finished or a heartbeat fails with
`Connection is closed`; it no longer stays at 100 while both hubs are down.
Closed-hub heartbeats also schedule reconnect. `list_accounts()` still raises
`ProjectXConnectionError` after HTTP retries — catch it in a watchdog tick.

```python
status = await suite.realtime.get_health_status()
print(status["health_score"], status["user_connected"], status["market_connected"])
```

### Quote and depth coalescing (v4.3.1)

Gateway quote and depth messages can arrive faster than callbacks can run,
especially at the CME RTH open with an orderbook attached. Each SignalR
message used to schedule its own `run_coroutine_threadsafe` task. That
queue could grow without bound and delay data-manager tick processing, so
`NEW_BAR` arrived late (or not at all) while a 1s heartbeat still looked
healthy.

As of v4.3.1 the realtime client keeps **one in-flight forward per
contract** for `quote_update` and `market_depth`. Extra messages replace a
pending slot (latest-wins) instead of enqueueing another task.

| Event | Under load |
|---|---|
| `quote_update` | Latest payload per contract is delivered; intermediate quotes may be skipped |
| `market_depth` | Latest payload per contract is delivered; intermediate depth rows may be skipped |
| `market_trade` | **Never dropped** — required for volume / OHLC / `NEW_BAR` |
| `order_update`, `position_update`, `account_update`, `trade_execution` | **Never dropped** |

Dropped counts are on `suite.realtime.get_stats()` as
`coalesced_quote_dropped` and `coalesced_depth_dropped`. Quotes are
snapshots, so latest-wins is correct. Depth is per price level, so a flood
may skip intermediate book updates until later rows or a reset arrive.

```python
stats = suite.realtime.get_stats()
print(stats["coalesced_quote_dropped"], stats["coalesced_depth_dropped"])
```

## Real-time Data Access

### Getting Bar Data

Access OHLCV bar data across multiple timeframes:

```python
async def accessing_bar_data():
    suite = await TradingSuite.create("MNQ", timeframes=["1min", "5min"])

    # Get all available data for a timeframe
    all_bars = await suite.data.get_data("1min")

    # Get specific number of bars
    recent_bars = await suite.data.get_data("5min", count=20)

    # Get data for a time range
    from datetime import datetime, timedelta
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=2)

    range_bars = await suite.data.get_data(
        timeframe="1min",
        start_time=start_time,
        end_time=end_time
    )

    # Always check for None returns
    if all_bars is not None and not all_bars.is_empty():
        latest = all_bars.tail(1)
        print(f"Latest 1min close: ${latest['close'][0]:.2f}")

    await suite.disconnect()

asyncio.run(accessing_bar_data())
```

### Current Price and Volume

Get real-time price and volume information:

```python
async def price_and_volume():
    suite = await TradingSuite.create("MNQ", timeframes=["1min"])

    # Current price from latest tick or bar
    current_price = await suite.data.get_current_price()
    if current_price:
        print(f"Current price: ${current_price:.2f}")

    # Latest price from specific timeframe
    latest_price = await suite.data.get_latest_price()
    if latest_price:
        print(f"Latest price: ${latest_price:.2f}")

    # Price range statistics
    price_range = await suite.data.get_price_range(
        timeframe="1min",
        bars=100
    )
    if price_range:
        print(f"100-bar range: ${price_range['low']:.2f} - ${price_range['high']:.2f}")
        print(f"Range size: ${price_range['range']:.2f}")

    # Volume statistics
    vol_stats = await suite.data.get_volume_stats(timeframe="1min")
    if vol_stats:
        print(f"Total volume: {vol_stats['total_volume']:,}")
        print(f"Average volume: {vol_stats['avg_volume']:.0f}")

    await suite.disconnect()

asyncio.run(price_and_volume())
```

## Multi-Timeframe Synchronization

### Working with Multiple Timeframes

```python
async def multi_timeframe_analysis():
    suite = await TradingSuite.create(
        "MNQ",
        timeframes=["1min", "5min", "15min", "1hour"]
    )

    # Get data from all timeframes concurrently
    timeframes = ["1min", "5min", "15min", "1hour"]
    tasks = [suite.data.get_data(tf, count=10) for tf in timeframes]
    results = await asyncio.gather(*tasks)

    # Analyze alignment
    for tf, data in zip(timeframes, results):
        if data is not None and not data.is_empty():
            latest = data.tail(1)
            close = latest['close'][0]
            print(f"{tf:>6}: ${close:.2f}")

    await suite.disconnect()

asyncio.run(multi_timeframe_analysis())
```

## Performance Optimization

### Memory Management

Configure and monitor memory usage:

```python
async def memory_optimization():
    from project_x_py.realtime_data_manager.types import DataManagerConfig

    # Configure memory limits
    config = DataManagerConfig(
        max_bars_per_timeframe=1000,  # Limit bars in memory
        enable_mmap_overflow=True,     # Use disk for overflow
        overflow_threshold=0.8,        # Overflow at 80% capacity
        enable_dynamic_limits=True     # Adaptive limits
    )

    suite = await TradingSuite.create(
        "MNQ",
        timeframes=["1min"],
        data_manager_config=config
    )

    # Monitor memory usage
    memory_stats = await suite.data.get_memory_stats()
    print(f"Memory Usage: {memory_stats.memory_usage_mb:.2f} MB")
    print(f"Cache Efficiency: {memory_stats.cache_efficiency:.1%}")

    # Optimize data access patterns
    optimization = await suite.data.optimize_data_access_patterns()
    print(f"Cache improvement: {optimization['cache_improvement']:.1%}")

    await suite.disconnect()

asyncio.run(memory_optimization())
```

### Lock Optimization

Monitor and optimize lock contention:

```python
async def lock_optimization():
    suite = await TradingSuite.create("MNQ", timeframes=["1min"])

    # Get lock statistics
    lock_stats = await suite.data.get_lock_optimization_stats()
    print(f"Lock acquisitions: {lock_stats['total_acquisitions']}")
    print(f"Average wait time: {lock_stats['avg_wait_time_ms']:.2f}ms")
    print(f"Contention rate: {lock_stats['contention_rate']:.1%}")

    await suite.disconnect()

asyncio.run(lock_optimization())
```

## DST Handling

### Automatic DST Transition Management

```python
async def dst_aware_trading():
    from project_x_py.realtime_data_manager.types import DataManagerConfig

    # Configure with timezone awareness
    config = DataManagerConfig(
        session_type="RTH",  # Regular Trading Hours
        timezone="America/New_York"  # Exchange timezone
    )

    suite = await TradingSuite.create(
        "MNQ",
        timeframes=["1min"],
        data_manager_config=config
    )

    # DST transitions are handled automatically:
    # - Spring forward: Missing hour is skipped
    # - Fall back: Duplicate hour is disambiguated
    # - Bar timestamps are adjusted correctly

    # Data access works normally across DST boundaries
    bars = await suite.data.get_data("1min")
    if bars is not None:
        print(f"Bars across DST: {len(bars)}")

    await suite.disconnect()

asyncio.run(dst_aware_trading())
```

## Advanced Features

### MMap Overflow for Large Datasets

Handle large amounts of historical data with disk overflow:

```python
async def large_dataset_handling():
    from project_x_py.realtime_data_manager.types import DataManagerConfig

    config = DataManagerConfig(
        max_bars_per_timeframe=500,   # Low memory limit
        enable_mmap_overflow=True,    # Enable disk overflow
        overflow_threshold=0.8,        # Trigger at 80%
        mmap_storage_path="/tmp/overflow"  # Storage location
    )

    suite = await TradingSuite.create(
        "MNQ",
        timeframes=["1min"],
        data_manager_config=config,
        initial_days=30  # Large initial dataset
    )

    # Check overflow statistics
    overflow_stats = await suite.data.get_overflow_stats("1min")
    if overflow_stats:
        print(f"Overflowed bars: {overflow_stats['total_overflowed_bars']}")
        print(f"Disk usage: {overflow_stats['disk_storage_size_mb']:.2f} MB")

    # Data access seamlessly combines memory and disk
    all_data = await suite.data.get_data("1min")
    if all_data is not None:
        print(f"Total bars available: {len(all_data)}")

    await suite.disconnect()

asyncio.run(large_dataset_handling())
```

### Dynamic Resource Management

Adaptive resource limits based on system load:

```python
async def dynamic_resources():
    from project_x_py.realtime_data_manager.types import DataManagerConfig

    config = DataManagerConfig(
        enable_dynamic_limits=True,
        memory_threshold_percent=80.0,  # Adjust at 80% memory
        cpu_threshold_percent=70.0      # Adjust at 70% CPU
    )

    suite = await TradingSuite.create(
        "MNQ",
        timeframes=["1min"],
        data_manager_config=config
    )

    # Monitor resource adaptation
    resource_stats = await suite.data.get_resource_stats()
    print(f"Memory limit: {resource_stats.get('memory_limit_mb', 0):.0f} MB")
    print(f"CPU usage: {resource_stats['cpu_percent']:.1f}%")
    print(f"Thread count: {resource_stats['num_threads']}")

    await suite.disconnect()

asyncio.run(dynamic_resources())
```

## Error Handling

### Proper Error Handling Patterns

```python
async def robust_data_access():
    suite = await TradingSuite.create("MNQ", timeframes=["1min"])

    try:
        # Always check for None returns
        data = await suite.data.get_data("1min")
        if data is None:
            print("No data available yet")
            return

        # Check for empty DataFrames
        if data.is_empty():
            print("DataFrame is empty")
            return

        # Safe data access
        if len(data) > 0:
            latest = data.tail(1)
            close_price = latest["close"][0]
            print(f"Latest close: ${close_price:.2f}")

    except Exception as e:
        print(f"Error accessing data: {e}")
        # Log error for debugging
        import logging
        logging.error(f"Data access error: {e}", exc_info=True)

    finally:
        # Always cleanup
        await suite.disconnect()

asyncio.run(robust_data_access())
```

## Best Practices

### 1. Resource Management

```python
# ✅ Good: Limit timeframes to what you need
suite = await TradingSuite.create("MNQ", timeframes=["1min", "5min"])

# ❌ Bad: Too many unnecessary timeframes
suite = await TradingSuite.create("MNQ",
    timeframes=["1sec", "5sec", "10sec", "15sec", "30sec", "1min", "2min", "5min", "15min", "30min", "1hour"])
```

### 2. Data Access

```python
# ✅ Good: Get only needed data
recent = await suite.data.get_data("1min", count=100)

# ❌ Bad: Get all data when you only need recent
all_data = await suite.data.get_data("1min")
recent = all_data.tail(100) if all_data else None
```

### 3. Null Checking

```python
# ✅ Good: Always check for None and empty
data = await suite.data.get_data("1min")
if data is not None and not data.is_empty():
    # Process data safely
    pass

# ❌ Bad: Assume data exists
data = await suite.data.get_data("1min")
latest = data.tail(1)  # May fail!
```

### 4. Cleanup

```python
# ✅ Good: Use try/finally for cleanup
try:
    suite = await TradingSuite.create("MNQ")
    # Use suite
finally:
    await suite.disconnect()

# ✅ Better: Use async context manager (when available)
async with await TradingSuite.create("MNQ") as suite:
    # Suite automatically cleaned up
    pass
```

## Performance Tips

1. **Configure memory limits** - Set appropriate `max_bars_per_timeframe`
2. **Enable overflow** - Use MMap overflow for long-running sessions
3. **Monitor health** - Check health scores and statistics regularly
4. **Optimize access** - Use `count` parameter to limit data retrieval
5. **Enable caching** - DataFrame optimization improves repeated access
6. **Use appropriate timeframes** - Don't subscribe to unnecessary timeframes
7. **Batch operations** - Use `asyncio.gather()` for concurrent operations

## Troubleshooting

### Common Issues

**No data returned**
- Check if real-time feed is started
- Verify authentication and connection
- Allow time for initial data to accumulate

**High memory usage**
- Enable MMap overflow
- Reduce `max_bars_per_timeframe`
- Enable dynamic resource limits
- Call `cleanup()` periodically

**Performance degradation**
- Check lock contention statistics
- Optimize data access patterns
- Reduce number of timeframes
- Enable DataFrame caching

## See Also

- [Data Manager API](../api/data-manager.md) - Complete API reference
- [Trading Suite Guide](../guide/trading-suite.md) - Integrated trading
- [Examples](../../examples/) - Working code examples
