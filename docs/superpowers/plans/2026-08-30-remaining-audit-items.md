# Remaining SDK Audit Items

> **Status:** Implemented on `fix/remaining-audit-items` and shipped as **v4.1.0**.

**Goal:** Finish the leftover findings from the 2026-08-30 multi-agent SDK audit after the Gateway/live-money pass on `fix/sdk-audit-hardening`.

**Architecture:** Keep `TradingSuite.create()` as the public entry point. Risk and realtime fixes stay inside existing mixins. Do not invent unofficial Gateway endpoints. Prefer making documented APIs work over deleting them; raise or warn honestly when a shim is a no-op.

**Tech Stack:** Python 3.12+, asyncio, httpx, pysignalr, Polars, Decimal, pytest-asyncio.

**Sources:** `.grok/review-2026-08-30/{04-realtime,05-orderbook-risk,08-custom-features,09-test-coverage,10-cleanup}.md` and the first-wave plan `docs/superpowers/plans/2026-08-30-sdk-audit-hardening.md`.

## Global Constraints

- Python 3.12+ type hints: `X | Y`, `dict[str, Any]`. No pandas.
- Prices: `Decimal`; tick-size align before sending or modifying orders.
- Public APIs stay compatible; `@deprecated` for at least 2 minor versions; remove only in a major.
- Mutating POSTs are never retried after timeout/disconnect/5xx/401/429/`ReadError`.
- Tests: `@pytest.mark.asyncio`, `uv run pytest`. Live examples: `./test.sh` only.
- Conventional Commits. User-facing behavior changes need `CHANGELOG.md`.

## Already done (do not re-implement)

First wave (`fix/sdk-audit-hardening`) closed: partial-close `size`, native-bracket no second entry, nested position-order tracking, JWT lock, health MRO, GatewayDepth dict/`volume`, tickValue sizing, trailing-stop ratchet, official searchOpen/search fields, mutating 401/429/ReadError, `Account.from_api`, `get_all_positions` raise+prune, Auth validate/logout, Contract searchById/available, Order searchById + v2/query, Status/ping, `get_bars(live=)` + 20k cap + Tick unit 7, `modify_order(trail_price=)`, OrderStatus 7/8, omit null `linkedOrderId`, emit after `order_lock`, EventBus.off, per-contract unsubscribe, unmarked tests = `unit`.

---

## Wave A — Risk path still can reverse an account

These are live-money. Do this wave first, as one PR.

### A1: Protective orders must be OCO

**Files:** `src/project_x_py/risk_manager/core.py` (`attach_risk_orders` ~499-517), `src/project_x_py/risk_manager/managed_trade.py`, `tests/risk_manager/`.

`attach_risk_orders` places a stop and a take-profit independently. If the target fills, the stop stays working and can open an opposite position.

- [ ] **Write failing tests**
  - `test_target_fill_cancels_working_stop`
  - `test_stop_fill_cancels_working_target`
- [ ] **Implement:** place both legs via `OrderManager.place_bracket_order` / `linked_order_id` / `track_oco_orders`. On either fill, cancel the sibling.
- [ ] **Run:** `uv run pytest tests/risk_manager/ -q`

### A2: `features=["risk_manager"]` must gate `suite.orders.place_*`

**Files:** `src/project_x_py/order_manager/core.py` (`auto_risk_management` assigned, never read), `src/project_x_py/trading_suite.py:208`.

Direct `place_market_order` bypasses daily loss, max size, and hours.

- [ ] **Write failing test:** validation failure → `_make_request` not called.
- [ ] **Implement:** if `auto_risk_management` is True, `place_order` awaits `risk_manager.validate_trade(...)` **before** HTTP and refuses when `is_valid is False`.
- [ ] **Docs:** state that `ManagedTrade` is still the recommended path; auto-gate is an extra backstop.

### A3: Daily loss / trade counters from real fills

**Files:** `src/project_x_py/risk_manager/core.py` (`record_trade_result`, `validate_trade`), EventBus `POSITION_CLOSED` / `ORDER_FILLED`.

Counters only move if the caller records PnL. `avoid_news_events` defaults True and is never consulted.

- [ ] **Write failing test:** closed losing position → next `validate_trade` fails when over `max_daily_loss`.
- [ ] **Implement:** subscribe to position/trade events; update `_daily_loss` / `_daily_trades` from actual fills. Implement `avoid_news_events` or remove it from `RiskConfig` (deprecate 2 minors if public).

### A4: One stop-distance definition

**Files:** `src/project_x_py/risk_manager/core.py` `attach_risk_orders` vs `calculate_stop_loss`.

Fixed stop: attach uses `default_stop_distance * tick_size`; `calculate_stop_loss` uses raw points. Percent: attach divides by 100; `calculate_stop_loss` treats the value as a fraction (`1 - 50` → negative price).

- [ ] **Write failing tests** on MNQ (`tickSize=0.25`) for both call sites (ticks and percent).
- [ ] **Implement:** ticks → `ticks * tickSize`, aligned. Percent → `entry * (pct/100)` everywhere.

### A5: ManagedTrade must not leave a naked position

**Files:** `src/project_x_py/risk_manager/managed_trade.py` (`__aexit__`, `scale_in`, `scale_out`).

`__aexit__` only cancels unfilled entries. Fill + failed `attach_risk_orders` leaves a naked position. `scale_in` skips `validate_trade`. `scale_out` does not shrink protective size.

- [ ] **Write failing tests:** attach failure after fill → flatten or stop present; scale-out → protective size == remainder; scale-in calls `validate_trade`.
- [ ] **Implement:** on exception after fill, flatten or attach stops before leaving. Validate scale-in. After partial exit, modify stop/target size.

---

## Wave B — Realtime reliability

### B1: Stale-feed watchdog

**Files:** `src/project_x_py/realtime/connection_management.py` (watchdog loop), `tests/realtime/`.

Watchdog is market-only; silent if no message ever arrived; resets `_last_market_message` before reconnect (hides a failed reconnect). Both hubs `create_task` restore with no lock; health reconnect can restore again via `on_open`.

- [ ] **Write failing tests:** hub that never received a message still goes stale; failed reconnect does not reset the timestamp; restore is serialized.
- [ ] **Implement:** watch user + market; treat “never messaged after subscribe” as stale; reset timestamp only after a successful restore; one restore in flight.

### B2: `enable_batching()` TypeError

**Files:** `src/project_x_py/realtime/event_handling.py`, `src/project_x_py/realtime/batched_handler.py`.

`enable_batching()` awaits sync `_forward_quote_update` → `TypeError`, then the batch circuit drops the feed.

- [ ] **Write failing test** that enables batching and injects a quote.
- [ ] **Implement:** do not `await` a sync forwarder; process every depth row (GatewayDepth is per level — do not collapse a batch to the last row per contract).

### B3: DST live-bar window

**Files:** `src/project_x_py/realtime_data_manager/dst_handling.py` (`is_dst_transition_period`).

Midnight offset walk misses the 2 AM transition. Session filters apply one DST offset from bar 0.

- [ ] **Write failing test** for America/Chicago spring-forward 02:00 window.
- [ ] **Implement:** detect the 2 AM window, not only midnight. Session filter: per-bar offset, not first-bar offset.

### B4: Bounded buffers and lock hold times

**Files:** realtime hub setup (`max_size=None`), `realtime_data_manager` REST fallback, EventBus.

pysignalr `max_size=None` is unbounded. REST price fallback holds the data read lock across HTTP. EventBus swallows handler exceptions (OK) but nested `wait_for` can deadlock.

- [ ] Cap hub receive buffer; document the cap.
- [ ] Copy price/lock state, release, then HTTP; apply result under the lock.
- [ ] Document EventBus: handlers must not call `wait_for` on the same bus from inside `emit`. Add a test that a re-entrant `wait_for` times out or is rejected.

---

## Wave C — Honesty: docs, shims, and custom math

### C1: `add_callback` shims must work or fail loudly

**Files:** `order_manager/tracking.py`, `orderbook/base.py`, `position_manager/tracking.py`, `realtime_data_manager/callbacks.py`.

OrderManager/OrderBook/PositionManager `add_callback` do not register handlers. OrderBook logs “registered” anyway. Data-manager **does** forward to EventBus.

- [ ] Restore EventBus forwarding (same as data-manager) **or** raise `DeprecationWarning` + `NotImplementedError`.
- [ ] Align removal version to **5.0.0**. Package is already 4.0.1.
- [ ] Put `@deprecated` on `RealtimeDataManager.add_callback` if it stays as a shim.

### C2: OrderTracker is the official suite API

**Files:** `order_tracker.py`, `trading_suite.py` `track_order()` / `order_chain()`.

`suite.track_order()` instantiates `@deprecated_class` types. Module docs still mention v4.0.0 removal (decorator is 5.0.0). The “no warning on suite methods” test mocks the methods.

- [ ] Drop `@deprecated_class` from `OrderTracker` / `OrderChainBuilder`.
- [ ] Keep `@deprecated` only on standalone re-exports.
- [ ] Rewrite `test_trading_suite_methods_no_deprecation` to call the real suite methods.

### C3: Indicator and README claims

**Files:** `README.md`, `docs/api/indicators.md`, `src/project_x_py/indicators/`.

- Not “full TA-Lib”: `HT_TRENDLINE`, `MAMA`, `MAVP`, `SAREXT` are stubs.
- `from project_x_py.indicators import RSI` is a **function**; docs show `RSI().calculate(...)`.
- FVG ignores the middle candle; Order Block can be both bull and bear; WAE formula ≠ docstring.
- README “6 spoofing pattern types” is six labels on one volume-change heuristic. Guide APIs `enable_spoofing_detection`, `EventType.SPOOFING_DETECTED`, `get_full_orderbook`, `calculate_price_impact` do not exist.

- [ ] Docs: “64 named indicators, Polars implementations; not a full TA-Lib port.” Document stubs.
- [ ] Export classes as `RSIIndicator` (Lorenz pattern) and keep `RSI` as the function.
- [ ] Either implement the advertised spoofing APIs **or** delete the claims.
- [ ] Golden tests for SMA/EMA/RSI/MACD/ATR vs known values; FVG uses the middle candle.

### C4: Sessions RTH vs ETH

**Files:** `src/project_x_py/sessions/`.

`is_market_open` treats ETH as RTH. Overnight 00:00–06:00 is labeled BREAK. DataFrame filters use one DST offset from bar 0.

- [ ] Failing tests: ETH hours are open for ETH config; 00:00–06:00 is ETH not BREAK; DST spring-forward.
- [ ] Fix labeling and per-bar offset (depends on B3).

### C5: Remaining no-ops and stats

- `Features.TRADE_JOURNAL` / `AUTO_RECONNECT`: warn-and-noop. Remove from docs next to working flags, or implement AUTO_RECONNECT (watchdog already exists).
- `PERFORMANCE_ANALYTICS` sets flags nobody reads — wire or drop.
- `StatisticsAggregator` multi-instrument TODO (`trading_suite.py` ~942): first-symbol-only stats. Either implement or document as single-instrument.
- Stats export: redact secrets in Prometheus/CSV/Datadog, not only JSON. Missing health inputs should not score 100.
- `order_templates.py` / `calculate_position_sizing`: `stop_points * tickValue` sizes MNQ ~4× too large (same class of bug as Wave A sizing). Use ticks × tickValue.

---

## Wave D — Test hygiene (regression-proof)

**From** `.grok/review-2026-08-30/09-test-coverage.md`.

- [ ] JoinBid/JoinAsk: assert `POST /Order/place` `type=6/7` (not only mock `place_order`).
- [ ] Public `place_bracket_order` success path with `project_x` present (native path).
- `OrderSubmissionUncertainError` for `/Order/modify` and position close/partial-close.
- Trade half-turn: `profitAndLoss is None` through `search_trades` / `Trade.from_api`.
- Depth tests: seed `"volume"` and assert bid/ask DataFrame contents (partially started in first wave).
- Port then delete overlapping `*_legacy.py` client tests.
- Rewrite `close_all_positions` tests that skip the assertion because of a tracking bug.

---

## Suggested PR split

| PR | Wave | Title |
|---|---|---|
| 1 | A | `fix: OCO protective orders and risk gating` |
| 2 | B | `fix: realtime stale-feed, batching, and DST` |
| 3 | C | `fix: callback shims, tracker deprecation, and honest docs` |
| 4 | D | `test: Gateway payload and error-path coverage` |

Each PR is independently reviewable. A depends on nothing in this remaining set. B is independent of A. C is mostly docs/API honesty. D can land with A/B as tests are written.

## Out of scope

- `Auth/loginApp` (firm/app login, not the trader API-key flow).
- Implementing a news calendar for `avoid_news_events` if the flag is removed.
- Full TA-Lib numerical parity for all 150+ functions.
- Removing `OrderTracker` (it **is** the suite API).
