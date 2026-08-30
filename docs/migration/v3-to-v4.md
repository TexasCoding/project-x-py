# Migration Guide: v3.x to v4.0

v4.0 is a major release for the TopstepX-only ProjectX Gateway. It removes
long-deprecated surfaces, aligns HTTP and WebSocket clients with the current
Gateway, and ships the order and realtime fixes that accumulated while the
SDK was unmaintained.

## What actually shipped

- Tolerant `Order.from_api()`, `Position.from_api()`, and `Trade.from_api()`
- Native Gateway brackets (`stopLossBracket` / `takeProfitBracket`)
- `OrderSubmissionUncertainError` when an HTTP cancel is interrupted
- REST `/Trade/search` and `/Order/search` with official timestamps
- pysignalr instead of signalrcore
- Stale-feed watchdog (`EventType.FEED_STALE`) and REST price fallback
- Diagonal Polars concat so live bars can append onto wider historical frames
- `TradingSuite.export_stats()` (json, prometheus, csv, datadog)
- `projectx-check` / `projectx-config` CLI entry points
- Official TopstepX URLs: `https://api.topstepx.com` and `https://rtc.topstepx.com`

## Breaking changes

| v3.x | v4.0 |
|------|------|
| `suite.get_stats_sync()` | `await suite.get_stats()` or `await suite.export_stats()` |
| `get_positions()` deprecation warning | `get_positions()` is a documented alias of `search_open_positions()` |
| `suite.data` / `suite.orders` deprecation warnings | Official single-instrument accessors. Multi-instrument still uses `suite["MNQ"]` |
| signalrcore + websocket-client | pysignalr (`websockets`) |
| uvloop installed at import | Optional extra: `pip install project-x-py[uvloop]` |
| Auth TypedDict field `jwt` | Gateway field is `token` |
| Instrument search TypedDict `instruments` | Gateway field is `contracts` |
| User-Agent `ProjectX-Python-SDK/2.0.0` | `ProjectX-Python-SDK/4.0.0` |
| Placeholder `suite.journal` / `suite.analytics` | Removed. `Features.TRADE_JOURNAL` and `Features.AUTO_RECONNECT` warn and have no effect |

`OrderTracker` and `create_orderbook()` remain available. Prefer
`TradingSuite.track_order()` / `TradingSuite.create(..., features=["orderbook"])`.

## Authentication and URLs

ProjectX is Topstep-exclusive. Defaults are:

```python
api_url = "https://api.topstepx.com/api"
user_hub_url = "https://rtc.topstepx.com/hubs/user"
market_hub_url = "https://rtc.topstepx.com/hubs/market"
```

`realtime_url` is a legacy config field and is not used for hub connections.

Credentials still come from `PROJECT_X_API_KEY` and `PROJECT_X_USERNAME`, or
from `TradingSuite.create(username=..., api_key=...)`.

## Orders

Prefer native Gateway brackets when placing an entry:

```python
await suite.orders.place_order(
    contract_id=contract_id,
    side=0,
    size=1,
    order_type=1,
    limit_price=21000.0,
    stop_loss_bracket={"ticks": 16, "type": 4},
    take_profit_bracket={"ticks": 32, "type": 1},
)
```

If the Gateway rejects native brackets, the SDK still falls back to the
client-side OCO path. Fill detection now reconciles through `/Order/search`
and trades instead of treating “not in open orders” as unfilled.

If a place/cancel HTTP call is cancelled, times out, or gets a 5xx after the
request may have been sent, the SDK raises `OrderSubmissionUncertainError`
and does **not** retry. Reconcile with `get_order_by_id()` before retrying.

## Realtime

The SignalR client is now pysignalr. `HubConnectionBuilder` is still the
public construction API used by tests and extensions.

- `connect()` captures the running event loop before hub setup
- `GatewayLogout` is handled on both hubs
- Market silence longer than `stale_feed_seconds` (default 30s) emits
  `EventType.FEED_STALE` and forces a health reconnect
- `get_current_price()` falls back to REST bars when ticks are stale

## Statistics

```python
stats = await suite.get_stats()
payload = await suite.export_stats("json")
```

`get_stats_sync()` is gone. Do not call sync wrappers from an async context.

## Dependencies removed from the default extra

- `requests` (HTTP is httpx)
- `plotly`
- `msgpack-python`
- `signalrcore` / `websocket-client`
- `uvloop` (install `[uvloop]` if you want it; the SDK will not install it
  as an import-time side effect)

## Upgrade checklist

1. Upgrade: `pip install -U project-x-py` or `uv add project-x-py==4.0.0`
2. Replace `get_stats_sync()` with `await get_stats()`
3. Confirm env vars still point at TopstepX (`api.topstepx.com` / `rtc.topstepx.com`)
4. Catch `OrderSubmissionUncertainError` around place/cancel
5. Subscribe to `EventType.FEED_STALE` if you need stale-feed alerts
6. Drop any code that imported `signalrcore` through this package
