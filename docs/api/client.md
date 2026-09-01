# Client API

Core ProjectX client for API interactions, authentication, market data access, and trading operations.

## Overview

The ProjectX client provides the foundation for all SDK operations with comprehensive async support, authentication management, connection pooling, and intelligent caching.


## Quick Start

```python
import asyncio
from project_x_py import ProjectX

async def basic_client_usage():
    # Create client from environment variables
    async with ProjectX.from_env() as client:
        # Authenticate automatically
        await client.authenticate()

        # Get account information (sync accessor after authenticate)
        account = client.get_account_info()
        print(f"Balance: ${account.balance:,.2f}")

        # Get market data
        bars = await client.get_bars("MNQ", days=5, interval=60)
        print(f"Retrieved {len(bars)} bars")

asyncio.run(basic_client_usage())
```

## Authentication

### Environment-based Setup

```python
import os
from project_x_py import ProjectX

# Set environment variables
os.environ["PROJECT_X_API_KEY"] = "your_api_key"  # pragma: allowlist secret
os.environ["PROJECT_X_USERNAME"] = "your_username"

async def env_authentication():
    # Create client from environment
    async with ProjectX.from_env() as client:
        await client.authenticate()
        print(f"Authenticated account: {client.account_info.name}")

asyncio.run(env_authentication())
```

### Manual Configuration

```python
from project_x_py import ProjectX
from project_x_py.models import ProjectXConfig

async def manual_authentication():
    # Manual configuration
    config = ProjectXConfig(
        api_url="https://api.topstepx.com/api",
        timeout_seconds=30,
        retry_attempts=3,
    )

    async with ProjectX(
        username="your_username",
        api_key="your_api_key",  # pragma: allowlist secret
        config=config,
    ) as client:
        await client.authenticate()
        print(f"Account: {client.account_info.name}")
        print(f"Token prefix: {client.get_session_token()[:20]}...")

asyncio.run(manual_authentication())
```

### Token Management

```python
async def token_management():
    async with ProjectX.from_env() as client:
        await client.authenticate()

        token = client.get_session_token()
        print(f"Session token acquired: {bool(token)}")
        # JWT refresh is handled automatically before expiry.

asyncio.run(token_management())
```

## Market Data

### Historical Data

`get_bars(symbol, days=8, interval=5, unit=2, ...)` returns a Polars
DataFrame. `interval` is the count of `unit`s (1=second, 2=minute, 3=hour,
4=day, 5=week, 6=month, 7=tick). The first argument is the symbol, not
`instrument=`.

```python
from datetime import datetime

async def historical_data():
    async with ProjectX.from_env() as client:
        await client.authenticate()

        # 5-minute bars, last 5 days (unit defaults to 2 = minutes)
        bars = await client.get_bars("MNQ", days=5, interval=5)
        print(f"Retrieved {len(bars)} bars")
        print(f"Columns: {bars.columns}")

        # Hourly bars across a date range (stitches expired months)
        hourly = await client.get_bars(
            "MNQ",
            interval=1,
            unit=3,
            start_time=datetime(2026, 3, 31),
            end_time=datetime(2026, 8, 23),
        )
        print(f"Hourly bars: {len(hourly)}")

        # One contract month only — pass the full Gateway id
        september = await client.get_bars(
            "CON.F.US.MNQ.U26", days=5, interval=15
        )

asyncio.run(historical_data())
```

### Contract rolls and Gateway limits

`get_instrument("MNQ")` always returns the **active** listed contract
(front month). That is what you trade and subscribe to.

Historical bars are different:

| Request | What Gateway / the SDK return |
|---|---|
| Product root (`"MNQ"`) **hourly or coarser** (`unit >= 3` except ticks, or 60-minute bars) | SDK walks prior months via `Contract/searchById` and concatenates them. Overlap keeps the later month. |
| Product root **sub-hour minutes, seconds, or ticks** | Active contract only. Expired months have **no** 5m/15m/1m history. |
| Full id (`"CON.F.US.MNQ.U26"`) | That month only. |
| More than 20,000 bars in one window | SDK pages `/History/retrieveBars`. Same-timestamp tick rows are kept. |

There is no continuous-contract id (`CON.F.US.MNQ` / `F.US.MNQ` return no
bars). If the returned timestamps start after your `start_time`, a warning
is logged — that is Gateway coverage, not a silent SDK clip.

```python
# 15-minute March–August will NOT fill from expired months.
# Gateway only keeps sub-hour bars on the current front month.
bars = await client.get_bars(
    "MNQ",
    interval=15,
    unit=2,
    start_time=datetime(2026, 3, 31),
    end_time=datetime(2026, 8, 23),
)
# Expect a warning and data starting when the active month has 15-minute history.
```

### Current Market Data

The REST client does not have `get_current_price` / `get_market_snapshot`.
Live last price comes from `TradingSuite`'s realtime data manager:

```python
from project_x_py import TradingSuite

async def current_market_data():
    suite = await TradingSuite.create("MNQ", timeframes=["1min"])
    price = await suite.data.get_current_price()
    print(f"MNQ Current Price: ${price:.2f}")
    await suite.disconnect()

asyncio.run(current_market_data())
```

### Tick bars

There is no `get_ticks()` REST helper. Tick aggregation is `get_bars` with
`unit=7` (still the active contract only, 20,000-bar pages):

```python
async def tick_bars():
    async with ProjectX.from_env() as client:
        await client.authenticate()
        ticks = await client.get_bars("MNQ", days=1, interval=1, unit=7)
        print(f"Retrieved {len(ticks)} tick bars")

asyncio.run(tick_bars())
```

## Account Information

### Account Details

```python
async def account_information():
    async with ProjectX.from_env() as client:
        await client.authenticate()

        # Get account info
        account = client.get_account_info()
        print(f"Account ID: {account.account_id}")
        print(f"Balance: ${account.balance:,.2f}")
        print(f"Available: ${account.available_balance:,.2f}")
        print(f"Margin Used: ${account.margin_used:,.2f}")
        print(f"Buying Power: ${account.buying_power:,.2f}")

        # Get account status
        status = await client.get_account_status()
        print(f"Status: {status.status}")
        print(f"Trading Enabled: {status.trading_enabled}")
        print(f"Market Data Access: {status.market_data_access}")

asyncio.run(account_information())
```

### Account Metrics

```python
async def account_metrics():
    async with ProjectX.from_env() as client:
        await client.authenticate()

        # Get performance metrics
        metrics = await client.get_account_metrics()
        print(f"Total P&L: ${metrics.total_pnl:,.2f}")
        print(f"Unrealized P&L: ${metrics.unrealized_pnl:,.2f}")
        print(f"Realized P&L: ${metrics.realized_pnl:,.2f}")
        print(f"Daily P&L: ${metrics.daily_pnl:,.2f}")

        # Risk metrics
        risk = await client.get_risk_metrics()
        print(f"Portfolio Value: ${risk.portfolio_value:,.2f}")
        print(f"Maximum Drawdown: {risk.max_drawdown:.2f}%")
        print(f"Sharpe Ratio: {risk.sharpe_ratio:.2f}")

asyncio.run(account_metrics())
```

## Trading Operations

### Order Management

```python
async def basic_trading():
    async with ProjectX.from_env() as client:
        await client.authenticate()

        # Place market order
        market_order = await client.place_market_order(
            instrument="MNQ",
            side=0,  # 0 for buy
            size=1
        )
        print(f"Market Order ID: {market_order.order_id}")

        # Place limit order
        limit_order = await client.place_limit_order(
            instrument="MNQ",
            side=0,  # 0 for buy
            size=1,
            price=21000.0
        )
        print(f"Limit Order ID: {limit_order.order_id}")

        # Place stop order
        stop_order = await client.place_stop_order(
            instrument="MNQ",
            side=1,  # 1 for sell
            size=1,
            stop_price=20950.0
        )
        print(f"Stop Order ID: {stop_order.order_id}")

asyncio.run(basic_trading())
```

### Order Status & Management

```python
async def order_management():
    async with ProjectX.from_env() as client:
        await client.authenticate()

        # Get all orders
        orders = await client.get_orders()
        print(f"Total Orders: {len(orders)}")

        # Get pending orders
        pending_orders = await client.get_orders(status="pending")
        print(f"Pending Orders: {len(pending_orders)}")

        # Get specific order
        if orders:
            order_id = orders[0].order_id
            order_details = await client.get_order(order_id)
            print(f"Order Status: {order_details.status}")
            print(f"Filled Quantity: {order_details.filled_quantity}")

        # Cancel order
        if pending_orders:
            cancel_result = await client.cancel_order(pending_orders[0].order_id)
            print(f"Cancel Result: {cancel_result.success}")

asyncio.run(order_management())
```

## Instrument Information

### Available Instruments

```python
async def instrument_information():
    async with ProjectX.from_env() as client:
        await client.authenticate()

        # Get all available instruments
        instruments = await client.get_instruments()
        print(f"Available Instruments: {len(instruments)}")

        for instrument in instruments[:5]:  # Show first 5
            print(f"  {instrument.symbol}: {instrument.description}")
            print(f"    Tick Size: {instrument.tick_size}")
            print(f"    Min Quantity: {instrument.min_quantity}")

        # Get specific instrument details
        # live=True means Gateway live/active *listed* contracts and can
        # exclude TopstepX Practice/sim. get_instrument falls back to
        # live=False with a warning when no listed contract is found.
        mnq_info = await client.get_instrument("MNQ")
        print(f"\nMNQ Details:")
        print(f"  Full Name: {mnq_info.description}")
        print(f"  Exchange: {mnq_info.exchange}")
        print(f"  Currency: {mnq_info.currency}")
        print(f"  Contract Size: {mnq_info.contract_size}")
        print(f"  Tick Size: {mnq_info.tick_size}")
        print(f"  Tick Value: ${mnq_info.tick_value}")

asyncio.run(instrument_information())
```

### Contract Information

```python
async def contract_information():
    async with ProjectX.from_env() as client:
        await client.authenticate()

        # Get contract details
        contract = await client.get_contract("MNQ")
        print(f"Contract ID: {contract.contract_id}")
        print(f"Expiration: {contract.expiration}")
        print(f"Settlement: {contract.settlement_type}")

        # Get trading hours
        hours = await client.get_trading_hours("MNQ")
        print(f"Market Open: {hours.market_open}")
        print(f"Market Close: {hours.market_close}")
        print(f"Pre-market: {hours.pre_market_start}")
        print(f"After-hours: {hours.after_hours_end}")

asyncio.run(contract_information())
```

## Connection Management

### Connection Status

```python
async def connection_management():
    async with ProjectX.from_env() as client:
        # Check connection status
        is_connected = await client.is_connected()
        print(f"Connected: {is_connected}")

        if not is_connected:
            # Reconnect if needed
            await client.reconnect()
            print("Reconnected successfully")

        # Get connection info
        conn_info = await client.get_connection_info()
        print(f"Server: {conn_info.server}")
        print(f"Latency: {conn_info.latency_ms}ms")
        print(f"Connection ID: {conn_info.connection_id}")

asyncio.run(connection_management())
```

### Health Monitoring

```python
async def health_monitoring():
    async with ProjectX.from_env() as client:
        await client.authenticate()

        # Get client health status
        health = await client.get_health_status()
        print(f"Health Score: {health.score}/100")
        print(f"API Calls: {health.api_calls}")
        print(f"Success Rate: {health.success_rate:.1%}")
        print(f"Average Response Time: {health.avg_response_time}ms")

        # Performance statistics
        stats = await client.get_performance_stats()
        print(f"Cache Hit Rate: {stats.cache_hit_rate:.1%}")
        print(f"Connection Pool Usage: {stats.pool_usage:.1%}")
        print(f"Memory Usage: {stats.memory_usage_mb:.1f} MB")

asyncio.run(health_monitoring())
```

## Caching & Performance

### Cache Management

```python
async def cache_management():
    async with ProjectX.from_env() as client:
        await client.authenticate()

        # Enable/disable caching
        client.enable_caching(True)

        # Clear cache
        await client.clear_cache("instruments")  # Specific cache
        await client.clear_cache()               # All caches

        # Get cache statistics
        cache_stats = await client.get_cache_stats()
        print(f"Cache Hits: {cache_stats.hits}")
        print(f"Cache Misses: {cache_stats.misses}")
        print(f"Hit Rate: {cache_stats.hit_rate:.1%}")

        # Set cache TTL
        client.set_cache_ttl("market_data", 30)  # 30 seconds

asyncio.run(cache_management())
```

### Performance Optimization

```python
async def performance_optimization():
    async with ProjectX.from_env() as client:
        await client.authenticate()

        # Batch requests for better performance
        instruments = ["MNQ", "MES", "MGC", "MYM"]

        # Instead of individual calls
        # prices = {}
        # for symbol in instruments:
        #     prices[symbol] = await client.get_current_price(symbol)

        # Use batch call
        prices = await client.get_current_prices(instruments)
        print(f"Batch retrieved {len(prices)} prices")

        # Connection pooling settings
        client.configure_connection_pool(
            max_connections=10,
            max_keepalive_connections=5,
            keepalive_expiry=30.0
        )

asyncio.run(performance_optimization())
```

## Error Handling

### Exception Handling

```python
from project_x_py.exceptions import (
    ProjectXAuthenticationError,
    ProjectXConnectionError,
    ProjectXRateLimitError,
    ProjectXServerError
)

async def error_handling():
    try:
        async with ProjectX.from_env() as client:
            await client.authenticate()

            # This might fail
            bars = await client.get_bars("INVALID_SYMBOL", days=1)

    except ProjectXAuthenticationError:
        print("Authentication failed - check credentials")
    except ProjectXConnectionError:
        print("Connection failed - check network")
    except ProjectXRateLimitError as e:
        print(f"Rate limited - retry after {e.retry_after} seconds")
    except ProjectXServerError as e:
        print(f"Server error: {e.message}")
    except Exception as e:
        print(f"Unexpected error: {e}")

asyncio.run(error_handling())
```

### Retry Logic

```python
import asyncio
from project_x_py.exceptions import ProjectXConnectionError

async def retry_logic():
    max_retries = 3
    retry_delay = 1.0

    for attempt in range(max_retries):
        try:
            async with ProjectX.from_env() as client:
                await client.authenticate()
                bars = await client.get_bars("MNQ", days=1)
                break  # Success

        except ProjectXConnectionError:
            if attempt < max_retries - 1:
                print(f"Attempt {attempt + 1} failed, retrying...")
                await asyncio.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
            else:
                print("All retry attempts failed")
                raise

asyncio.run(retry_logic())
```

## Configuration

### ClientConfig


```python
from project_x_py import ProjectX
from project_x_py.models import ProjectXConfig

async def custom_configuration():
    # Custom client configuration
    config = ProjectXConfig(
        api_key="your_api_key"  # pragma: allowlist secret,
        username="your_username",
        api_url="https://api.topstepx.com/api",
        timeout_seconds=60,        # Extended timeout
        retry_attempts=5,          # More retry attempts
        rate_limit_calls=100,      # Calls per minute
        enable_caching=True,       # Enable caching
        cache_ttl_seconds=300,     # 5-minute cache TTL
        connection_pool_size=10,   # Connection pool size
        max_keepalive_connections=5
    )

    async with ProjectX(config) as client:
        await client.authenticate()
        # Use configured client

asyncio.run(custom_configuration())
```

## Best Practices

### Context Manager Usage

```python
#  Recommended: Always use context manager
async with ProjectX.from_env() as client:
    await client.authenticate()
    # Client automatically disconnects

# L Manual management (not recommended)
client = ProjectX.from_env()
try:
    await client.authenticate()
    # ... operations
finally:
    await client.disconnect()
```

### Error Handling

```python
#  Good: Specific exception handling
try:
    bars = await client.get_bars("MNQ", days=1)
except ProjectXAuthenticationError:
    await client.refresh_token()
    bars = await client.get_bars("MNQ", days=1)  # Retry
except ProjectXRateLimitError as e:
    await asyncio.sleep(e.retry_after)
    # Implement backoff logic

#  Good: Check authentication status
if not await client.is_authenticated():
    await client.authenticate()
```

### Performance

```python
#  Good: Use batch operations
prices = await client.get_current_prices(["MNQ", "MES", "MGC"])

# L Less efficient: Individual calls
# mnq_price = await client.get_current_price("MNQ")
# mes_price = await client.get_current_price("MES")
# mgc_price = await client.get_current_price("MGC")

#  Good: Enable caching for repeated calls
client.enable_caching(True)
instruments = await client.get_instruments()  # Cached after first call
```

## See Also

- [Trading Suite API](trading-suite.md) - Higher-level trading interface
- [Authentication Guide](../getting-started/authentication.md) - Detailed authentication setup
- [Configuration Guide](../getting-started/configuration.md) - Configuration options
