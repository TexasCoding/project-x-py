# Configuration

## Configuration Options

The ProjectX Python SDK can be configured through multiple methods:

1. Environment variables
2. Configuration files
3. Programmatic configuration

## Environment Variables

### Required Variables

```bash
PROJECT_X_API_KEY=your-api-key
PROJECT_X_USERNAME=your-username
```

### Optional Variables

```bash
# API endpoint (for different environments)
PROJECTX_API_URL=https://api.topstepx.com/api

# Request timeout in seconds (default: 30)
PROJECTX_TIMEOUT_SECONDS=60

# Retry attempts for failed requests (default: 3)
PROJECTX_RETRY_ATTEMPTS=5

# Account name (if you have multiple accounts)
PROJECT_X_ACCOUNT_NAME=your-account-name

# Enable debug logging
PROJECTX_DEBUG=true
```

## Configuration File

Create a configuration file at `~/.config/projectx/config.json`:

```json
{
  "api_url": "https://api.topstepx.com/api",
  "user_hub_url": "https://rtc.topstepx.com/hubs/user",
  "market_hub_url": "https://rtc.topstepx.com/hubs/market",
  "timeout_seconds": 30,
  "retry_attempts": 3,
  "timezone": "America/Chicago"
}
```

Credentials are **not** read from this file. Use `PROJECT_X_API_KEY` and `PROJECT_X_USERNAME`, or pass them to `TradingSuite.create(username=..., api_key=...)`.

## Programmatic Configuration

### Using ProjectXConfig

```python
from project_x_py import ProjectX, ProjectXConfig

config = ProjectXConfig(
    api_url="https://api.topstepx.com/api",
    user_hub_url="https://rtc.topstepx.com/hubs/user",
    market_hub_url="https://rtc.topstepx.com/hubs/market",
    timeout_seconds=60,
    retry_attempts=5,
)

async with ProjectX(
    username="your-username",
    api_key="your-api-key",  # pragma: allowlist secret
    config=config,
) as client:
    await client.authenticate()
```

### TradingSuite Configuration

```python
from project_x_py import TradingSuite

# Basic configuration
suite = await TradingSuite.create(
    instruments=["MNQ"],
    timeframes=["1min", "5min", "15min"],
    features=["orderbook", "risk_manager"],
    initial_days=10
)

# Advanced configuration
suite = await TradingSuite.create(
    instruments=["MNQ"],
    timeframes=["1min"],
    features=["orderbook"],
    initial_days=5,
    config={
        "orderbook": {
            "max_depth_entries": 500,
            "max_trades": 5000
        },
        "data_manager": {
            "max_bars_per_timeframe": 2000,
            "tick_buffer_size": 5000
        },
        "risk_manager": {
            "max_position_size": 10,
            "max_daily_loss": 1000
        }
    }
)
```

## Component-Specific Configuration

### OrderBook Configuration

```python
from project_x_py import OrderBook

orderbook = OrderBook(
    instrument="MNQ",
    realtime_client=realtime_client,
    max_depth_entries=1000,  # Max order book levels per side
    max_trades=10000,  # Max trades to keep in memory
    update_throttle_ms=100  # Minimum time between updates
)
```

### Data Manager Configuration

```python
from project_x_py import create_data_manager

data_manager = create_data_manager(
    instrument="MNQ",
    client=client,
    realtime_client=realtime_client,
    timeframes=["1min", "5min"],
    max_bars_per_timeframe=5000,
    tick_buffer_size=10000,
    enable_tick_aggregation=True
)
```

### Risk Manager Configuration

```python
from project_x_py.risk_manager import RiskManager, RiskConfig

risk_config = RiskConfig(
    max_position_size=10,
    max_daily_loss=1000.0,
    max_daily_trades=50,
    max_open_orders=10,
    trailing_stop_activation=50.0,
    trailing_stop_distance=20.0
)

risk_manager = RiskManager(
    client=client,
    config=risk_config
)
```

## Performance Tuning

### Connection Pooling

```python
# Configure HTTP connection pooling
import httpx

async with ProjectX.from_env() as client:
    # Custom HTTP client with larger pool
    client._http_client = httpx.AsyncClient(
        limits=httpx.Limits(
            max_keepalive_connections=20,
            max_connections=100,
            keepalive_expiry=30
        )
    )
```

### Cache Configuration

```python
# Configure instrument cache
async with ProjectX.from_env() as client:
    # Set cache TTL (time-to-live) in seconds
    client._cache_ttl = 600  # 10 minutes

    # Clear cache manually if needed
    client._instrument_cache.clear()
```

### Rate Limiting

```python
# Configure rate limiting
from project_x_py.utils import AsyncRateLimiter

rate_limiter = AsyncRateLimiter(
    max_requests=100,
    window_seconds=60,
    burst_size=20
)

async with ProjectX.from_env() as client:
    client._rate_limiter = rate_limiter
```

## Logging Configuration

```python
import logging
from project_x_py.utils import setup_logging

# Basic logging
logging.basicConfig(level=logging.INFO)

# Advanced logging with custom format
setup_logging(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    log_file="projectx.log"
)

# Component-specific logging
logging.getLogger("project_x_py.realtime").setLevel(logging.DEBUG)
logging.getLogger("project_x_py.order_manager").setLevel(logging.INFO)
```

## Environment-Specific Settings

### Development

```python
# Development settings
config = ProjectXConfig(
    api_url="https://api.topstepx.com/api",
    timeout_seconds=60,
    retry_attempts=5,
    debug=True
)
```

### Production

```python
# Production settings
config = ProjectXConfig(
    api_url="https://api.topstepx.com/api",
    timeout_seconds=30,
    retry_attempts=3,
    debug=False,
    rate_limit_max_requests=50,
    rate_limit_window_seconds=60
)
```

## Next Steps

- [Trading Suite](../guide/trading-suite.md) - Complete trading setup
- [Performance](../development/architecture.md) - Performance optimization
- [API Reference](../api/client.md) - Detailed API documentation
