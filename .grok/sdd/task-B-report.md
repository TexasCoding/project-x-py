# Wave B Report — Realtime reliability

Worktree: `/Users/jeffreywest/.grok/worktrees/python-project-x-py/subagent-01a052f6-b571-74b1-9d5a-21f7a97ad7ba`
Branch: `fix/remaining-audit-items`
Date: 2026-08-30

## TDD evidence

### RED (failing tests first)

Wrote tests, then ran them against unfixed code:

```
tests/realtime/test_health_monitoring.py::TestStaleFeedWatchdog
tests/realtime/test_event_handling.py::...test_enable_batching_quote_is_processed_without_typeerror
tests/realtime/test_batched_handler.py::...test_depth_batch_processes_every_price_level
tests/realtime/test_async_hub.py::test_hub_receive_buffer_is_capped
tests/realtime_data_manager/test_dst_handling.py::...test_spring_forward_2am_window_chicago_2026
tests/realtime_data_manager/test_data_access.py::...test_rest_fallback_does_not_hold_lock_during_http
tests/event_system/test_event_bus.py::...test_reentrant_wait_for_is_rejected
tests/unit/test_session_filter.py::...test_rth_filter_uses_per_bar_dst_offset
```

Result: **11 failed, 2 passed**. Failures matched the bugs:

| Test | RED failure |
|---|---|
| `test_silent_hub_still_goes_stale` | `emit` never awaited (`last_message <= 0: continue`) |
| `test_user_hub_stale_emits_feed_stale` | user hub not watched |
| `test_failed_reconnect_does_not_reset_timestamp` | timestamp reset **before** reconnect |
| `test_restore_is_serialized` | `AttributeError: _serialized_health_reconnect` |
| batching quote | `TypeError` awaiting sync `_forward_quote_update` |
| depth every row | only last row per contract forwarded |
| hub `max_size` | no `HUB_RECEIVE_MAX_SIZE`; `max_size=None` |
| Chicago 2026-03-08 02:00 | midnight walk detected transition at **2026-03-09 00:00** |
| REST lock | `lock_held_during_http is True` |
| re-entrant `wait_for` | hung until outer 1s timeout |
| per-bar DST session filter | post-spring-forward 10:00 EDT bar dropped |

Existing `test_stale_feed_watchdog_emits_and_reconnects` stayed green throughout.

### GREEN

After implementation: **667 passed** for `tests/realtime/` + `tests/realtime_data_manager/`.
Also green: event bus, session filter/indicators/statistics, utils DST tests (134 in that slice).

`uv run ruff format` on touched files. `uv run mypy` on touched src files: clean.

## B1 — Stale-feed watchdog

**Files:** `src/project_x_py/realtime/health_monitoring.py`, `connection_management.py`, `types/protocols.py`

- Watch **user and market** independently. `EventType.FEED_STALE` payload includes `hub`.
- Silent hub: if `_last_*_message <= 0`, use `_hub_watch_started` (set when the watchdog starts). Never skip “no message yet”.
- Reset last-message timestamps **only after a successful restore** (`_mark_hubs_fresh`). Failed reconnect leaves the timestamp stale so the next loop retries.
- Serialize restore: `_serialized_health_reconnect` + `_restore_in_flight` / `_restore_lock`. Overlapping triggers drop; `on_open` restore is skipped while a health reconnect is in flight.

## B2 — `enable_batching()` TypeError + depth rows

**Files:** `src/project_x_py/realtime/batched_handler.py`

- Batch processor calls `_forward_event_async` (unbatched path), never awaits sync `_forward_quote_update` (which re-entered `handle_quote`).
- Quotes still latest-per-contract. Trades all rows. **Depth: every GatewayDepth row**.
- Legacy test mocks that only implement `_forward_*` still work via inspect fallback.

## B3 — DST 2 AM window

**Files:** `src/project_x_py/realtime_data_manager/dst_handling.py`, `src/project_x_py/sessions/filtering.py`

- `is_dst_transition_period` localizes with `is_dst=None` so 2 AM spring-forward is `NonExistentTimeError` → True.
- `_get_dst_transitions` probes 01:00 and 02:00 local each day (not midnight). Cached per `(zone, year)` (max 8 years). Hourly result cache capped at 96.
- Session RTH/ETH filters convert each bar to `America/New_York` and compare `.dt.time()` — no integer hours added to UTC.

## B4 — Bounded buffers, lock hold times, EventBus

1. `HUB_RECEIVE_MAX_SIZE = 10_000` in `async_hub.py`; documented in the module docstring; passed to pysignalr `max_size`.
2. `get_current_price()` copies bar close under the lock (`_copy_latest_bar_close`), **releases**, then HTTP REST fallback.
3. `EventBus.wait_for` documents the deadlock and raises `RuntimeError` when called from an emit handler on the same bus (`contextvars`).

## Files touched

- `src/project_x_py/realtime/health_monitoring.py`
- `src/project_x_py/realtime/connection_management.py`
- `src/project_x_py/realtime/batched_handler.py`
- `src/project_x_py/realtime/async_hub.py`
- `src/project_x_py/realtime_data_manager/dst_handling.py`
- `src/project_x_py/realtime_data_manager/data_access.py`
- `src/project_x_py/event_bus.py`
- `src/project_x_py/sessions/filtering.py`
- `src/project_x_py/types/protocols.py`
- `CHANGELOG.md` `[Unreleased]`
- Tests under `tests/realtime/`, `tests/realtime_data_manager/`, `tests/event_system/`, `tests/unit/test_session_filter.py`

Did **not** touch `src/project_x_py/risk_manager/`, JWT lock, health-mixin MRO, or `__version__`.

## Concerns

- `_stale_feed_emitted` changed from `bool` to `dict[str, bool]`. Internal attribute; protocol updated. Nothing public.
- pysignalr `max_size=10000` drops the oldest receive-buffer messages under backpressure. Documented; live hubs should still be consumed promptly.
- Session filter now uses Polars `convert_time_zone("America/New_York")`. Naive timestamps are labeled UTC first. Existing RTH/ETH unit tests passed; Wave C still owns ETH labeling (`is_market_open` / BREAK overnight).
- Re-entrant `wait_for` now errors instead of hanging. That is the intended fail-fast; callers that previously deadlocked will see `RuntimeError`.

## Verification

```bash
uv run ruff format <touched files>
uv run pytest tests/realtime/ tests/realtime_data_manager/ -q
# 667 passed
```
