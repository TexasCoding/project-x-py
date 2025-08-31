# Statistics & Analytics API

Comprehensive async-first statistics system with health monitoring and performance tracking (v3.3.0+).

## Overview

The statistics system provides centralized collection and analysis of performance metrics across all SDK components. Features include:

- **100% Async Architecture**: All statistics methods use async/await for optimal performance
- **Multi-format Export**: JSON, Prometheus, CSV, and Datadog formats with data sanitization
- **Component-Specific Tracking**: Enhanced statistics for all managers with specialized metrics
- **Health Monitoring**: Intelligent 0-100 health scoring with configurable thresholds
- **Performance Optimization**: TTL caching, parallel collection, and circular buffers
- **Memory Efficiency**: Circular buffers and lock-free reads for frequently accessed metrics

## Core Components

### StatisticsAggregator

Central component that collects and aggregates statistics from all registered components.

```python
from project_x_py.statistics import StatisticsAggregator

# Usually created automatically by TradingSuite
aggregator = StatisticsAggregator()
await aggregator.register_component("orders", order_manager)
stats = await aggregator.get_comprehensive_stats()
```

### HealthMonitor

Calculates health scores (0-100) based on various system metrics.

```python
from project_x_py.statistics.health import HealthMonitor

monitor = HealthMonitor()
health_score = await monitor.calculate_health(stats)
breakdown = await monitor.get_health_breakdown(stats)
```

### BaseStatisticsTracker

Base class for component statistics tracking with built-in error tracking and performance metrics.

```python
from project_x_py.statistics.base import BaseStatisticsTracker

tracker = BaseStatisticsTracker("my_component")
await tracker.increment("operations_count")
await tracker.record_timing("operation", 150.5)
stats = await tracker.get_stats()
```

### StatsExporter

Exports statistics to various formats (Prometheus, CSV, Datadog, JSON).

```python
from project_x_py.statistics.export import StatsExporter

exporter = StatsExporter()
prometheus_data = await exporter.to_prometheus(stats)
csv_data = await exporter.to_csv(stats)
datadog_metrics = await exporter.to_datadog(stats)
```

## TradingSuite Statistics

### Getting Statistics

```python
from project_x_py import TradingSuite

async def get_comprehensive_statistics():
    suite = await TradingSuite.create(["MNQ"])

    # Get comprehensive system statistics (async-first API)
    # NOTE: Method is get_stats(), not get_statistics()
    stats = await suite.get_stats()

    # Stats structure includes suite-level metrics
    print(f"Component Count: {stats['components']}")
    print(f"Total Operations: {stats['total_operations']}")
    print(f"Total Errors: {stats['total_errors']}")
    print(f"Memory Usage: {stats['memory_usage_mb']:.1f} MB")

    # Access component-specific stats if available
    if 'order_manager' in stats:
        print(f"Orders Placed: {stats['order_manager'].get('orders_placed', 0)}")

    await suite.disconnect()
```

### Component-Specific Statistics

```python
async def component_statistics():
    suite = await TradingSuite.create(["MNQ"], features=["orderbook"])
    mnq_context = suite["MNQ"]

    # Component-specific statistics (all async for consistency)
    # Note: Components use get_stats() method
    order_stats = await mnq_context.orders.get_stats()
    print(f"Orders Placed: {order_stats.get('orders_placed', 0)}")
    print(f"Orders Filled: {order_stats.get('orders_filled', 0)}")
    print(f"Error Count: {order_stats.get('error_count', 0)}")

    position_stats = await mnq_context.positions.get_stats()
    print(f"Positions Opened: {position_stats.get('positions_opened', 0)}")
    print(f"Positions Closed: {position_stats.get('positions_closed', 0)}")

    # OrderBook statistics (if enabled)
    if mnq_context.orderbook:
        orderbook_stats = await mnq_context.orderbook.get_statistics()
        print(f"Depth Updates: {orderbook_stats.get('depth_updates', 0)}")
        print(f"Trade Updates: {orderbook_stats.get('trade_updates', 0)}")

    await suite.disconnect()
```

## Export Capabilities

### Multi-format Export

```python
from project_x_py.statistics.export import StatsExporter

async def export_statistics():
    suite = await TradingSuite.create(["MNQ"])

    # Get statistics from suite
    stats = await suite.get_stats()

    # Create exporter and export to various formats
    exporter = StatsExporter()

    # Export to different formats
    prometheus_metrics = await exporter.to_prometheus(stats)
    csv_data = await exporter.to_csv(stats, include_timestamp=True)
    datadog_metrics = await exporter.to_datadog(stats, prefix="projectx")

    # JSON export is just the raw stats dict
    import json
    json_data = json.dumps(stats, indent=2)

    # Save to files
    with open("metrics.prom", "w") as f:
        f.write(prometheus_metrics)

    with open("stats.csv", "w") as f:
        f.write(csv_data)

    with open("stats.json", "w") as f:
        f.write(json_data)

    await suite.disconnect()
```

## Health Monitoring

### Real-time Health Scoring

```python
from project_x_py.statistics.health import HealthMonitor

async def monitor_health():
    suite = await TradingSuite.create(["MNQ"])

    # Get statistics and calculate health
    stats = await suite.get_stats()

    # Use HealthMonitor for health scoring
    monitor = HealthMonitor()
    health_score = await monitor.calculate_health(stats)

    if health_score < 70:
        print(f"⚠️ System health degraded: {health_score:.1f}/100")

        # Get detailed breakdown
        breakdown = await monitor.get_health_breakdown(stats)
        print(f"  Errors: {breakdown['errors']:.1f}/100")
        print(f"  Performance: {breakdown['performance']:.1f}/100")
        print(f"  Resources: {breakdown['resources']:.1f}/100")
        print(f"  Connection: {breakdown['connection']:.1f}/100")

        # Check for alerts
        alerts = await monitor.get_health_alerts(stats)
        for alert in alerts:
            if alert['level'] in ['CRITICAL', 'WARNING']:
                print(f"  {alert['level']}: {alert['message']}")

    await suite.disconnect()
```

### Health Thresholds

```python
from project_x_py.statistics.health import HealthThresholds, HealthMonitor

async def custom_health_monitoring():
    # Configure custom health thresholds
    thresholds = HealthThresholds(
        error_rate_warning=1.0,    # 1% error rate warning
        error_rate_critical=5.0,   # 5% error rate critical
        response_time_warning=500, # 500ms response time warning
        memory_usage_warning=80.0  # 80% memory usage warning
    )

    # Custom category weights (must sum to 1.0)
    weights = {
        "errors": 0.30,           # Emphasize error tracking
        "performance": 0.25,      # Performance is critical
        "connection": 0.20,       # Connection stability
        "resources": 0.15,        # Resource usage
        "data_quality": 0.05,     # Data quality
        "component_status": 0.05  # Component health
    }

    # Initialize custom health monitor
    monitor = HealthMonitor(weights=weights)

    # Use with suite statistics
    suite = await TradingSuite.create(["MNQ"])
    stats = await suite.get_stats()
    health_score = await monitor.calculate_health(stats)

    print(f"Custom Health Score: {health_score:.1f}/100")

    await suite.disconnect()
```

## Data Types

### Statistics Types

```python
from project_x_py.types.stats_types import (
    ComponentStats,        # Base statistics for any component
    ComprehensiveStats,    # Full system statistics
    TradingSuiteStats,     # Trading suite specific stats
    HealthBreakdown,       # Detailed health score breakdown
    HealthAlert,          # Health alert information
)
```

### Health Types

```python
from project_x_py.statistics.health import (
    HealthMonitor,        # Main health monitoring class
    AlertLevel,          # Alert severity levels (INFO, WARNING, CRITICAL)
)
```


## Performance Considerations

### Caching Strategy

The statistics system uses TTL caching to optimize performance:

- **Default TTL**: 5 seconds for expensive operations
- **Parallel Collection**: Components collected concurrently using asyncio.gather()
- **Timeout Protection**: 1 second timeout per component prevents hanging
- **Graceful Degradation**: Partial results returned if some components fail

### Memory Management

- **Circular Buffers**: Error history limited to 100 entries per component
- **Bounded Statistics**: Maximum limits prevent memory exhaustion
- **Lock-free Reads**: Frequently accessed metrics use atomic operations
- **Automatic Cleanup**: Old data cleaned up based on configurable parameters

## Best Practices

1. **Monitor Health Regularly**: Check health scores to detect issues early
2. **Use Appropriate Export Formats**: Prometheus for monitoring, CSV for analysis
3. **Configure Thresholds**: Adjust health thresholds based on your environment
4. **Handle Degradation**: Implement alerts for health score drops
5. **Regular Exports**: Export statistics periodically for historical analysis

## Example: Production Monitoring

```python
import asyncio
from project_x_py import TradingSuite

async def production_monitoring():
    """Complete production monitoring example."""
    suite = await TradingSuite.create(
        ["MNQ"],
        features=["orderbook", "risk_manager"]
    )

    # Run monitoring loop
    while True:
        try:
            # Get comprehensive statistics
            stats = await suite.get_stats()

            # Calculate health score
            monitor = HealthMonitor()
            health = await monitor.calculate_health(stats)

            if health < 80:
                print(f"⚠️ Health Alert: {health:.1f}/100")

                # Get detailed breakdown
                breakdown = await monitor.get_health_breakdown(stats)
                for category, score in breakdown.items():
                    if category != 'overall_score' and category != 'weighted_total':
                        if score < 70:
                            print(f"  {category}: {score:.1f}/100")

            # Export metrics for monitoring system
            exporter = StatsExporter()
            prometheus_data = await exporter.to_prometheus(stats)

            # Save to monitoring endpoint (example)
            # await send_to_monitoring_system(prometheus_data)

            # Performance metrics
            print(f"Total Operations: {stats.get('total_operations', 0)}")
            print(f"Total Errors: {stats.get('total_errors', 0)}")
            print(f"Memory Usage: {stats.get('memory_usage_mb', 0):.1f} MB")

            # Wait before next check
            await asyncio.sleep(30)  # Check every 30 seconds

        except Exception as e:
            print(f"Monitoring error: {e}")
            await asyncio.sleep(60)  # Longer wait on error

# Run monitoring
asyncio.run(production_monitoring())
```

## Integration Examples

### Prometheus Integration

```python
from project_x_py.statistics.export import StatsExporter

async def prometheus_integration():
    suite = await TradingSuite.create(["MNQ"])

    # Get stats and export to Prometheus format
    stats = await suite.get_stats()
    exporter = StatsExporter()
    metrics = await exporter.to_prometheus(stats, prefix="projectx")

    # Example Prometheus metrics format:
    # # HELP projectx_total_operations Total operations count
    # # TYPE projectx_total_operations gauge
    # projectx_total_operations 1234
    #
    # # HELP projectx_total_errors Total error count
    # # TYPE projectx_total_errors gauge
    # projectx_total_errors 5
    #
    # # HELP projectx_memory_usage_mb Memory usage in MB
    # # TYPE projectx_memory_usage_mb gauge
    # projectx_memory_usage_mb 85.5

    # Send to Prometheus pushgateway
    # import requests
    # requests.post('http://pushgateway:9091/metrics/job/projectx',
    #               data=metrics)

    await suite.disconnect()
```

### Datadog Integration

```python
from project_x_py.statistics.export import StatsExporter

async def datadog_integration():
    suite = await TradingSuite.create(["MNQ"])

    # Get stats and export to Datadog format
    stats = await suite.get_stats()
    exporter = StatsExporter()
    metrics = await exporter.to_datadog(stats, prefix="projectx")

    # Metrics are returned as a dict with 'series' key
    # Each metric has: metric name, points, type, and tags
    for metric in metrics['series']:
        print(f"{metric['metric']}: {metric['points'][0][1]}")

    # Example: Send to Datadog (requires datadog library)
    # from datadog import api
    #
    # for metric in metrics['series']:
    #     api.Metric.send(
    #         metric=metric['metric'],
    #         points=metric['points'],
    #         tags=metric.get('tags', [])
    #     )

    await suite.disconnect()
```

### CSV Analytics

```python
from project_x_py.statistics.export import StatsExporter

async def csv_analytics():
    suite = await TradingSuite.create(["MNQ"])

    # Get stats and export to CSV format
    stats = await suite.get_stats()
    exporter = StatsExporter()
    csv_data = await exporter.to_csv(stats, include_timestamp=True)

    # Save for analysis
    with open("trading_stats.csv", "w") as f:
        f.write(csv_data)

    # Example: Load with pandas for analysis
    # import pandas as pd
    # df = pd.read_csv("trading_stats.csv")
    # print(df.describe())
    # print(df.groupby('metric_category')['value'].agg(['mean', 'std']))

    await suite.disconnect()
```

## Troubleshooting

### Common Issues

**High Error Rates**
: Check component error counts and logs for specific issues.

**Low Health Scores**
: Review individual component health metrics to identify bottlenecks.

**Memory Usage Spikes**
: Monitor circular buffer sizes and cleanup frequencies.

**Slow Statistics Collection**
: Check network connectivity and component response times.

### Debugging

```python
async def debug_statistics():
    suite = await TradingSuite.create(["MNQ"])

    # Enable debug logging
    import logging
    logging.getLogger("project_x_py.statistics").setLevel(logging.DEBUG)

    # Get raw component statistics
    for component_name in ["orders", "positions", "data"]:
        if hasattr(suite["MNQ"], component_name):
            component = getattr(suite["MNQ"], component_name)
            if hasattr(component, "get_stats"):
                stats = await component.get_stats()
                print(f"{component_name}: {stats}")

    await suite.disconnect()
```

## Examples

The repository includes comprehensive examples demonstrating the statistics system:

- **20_statistics_usage.py** - Complete statistics system demonstration
- **24_bounded_statistics_demo.py** - Memory-bounded statistics with limits
- **19_risk_manager_live_demo.py** - Risk manager statistics in action
- **22_circuit_breaker_protection.py** - Health monitoring with circuit breakers

## See Also

- [Trading Suite](trading-suite.md) - Main entry point for statistics
- [Order Manager](order-manager.md) - Order management statistics
- [Position Manager](position-manager.md) - Position tracking statistics
- [Data Manager](data-manager.md) - Real-time data statistics
- [Order Book](../guide/orderbook.md) - Level 2 orderbook statistics
