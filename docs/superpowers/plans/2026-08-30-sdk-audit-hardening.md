# SDK Audit Hardening Implementation Plan

> **For agentic workers:** Execute these tasks with TDD. Global constraints below apply to every task.

**Goal:** Close official Gateway API gaps and fix live-trading correctness bugs found in the 2026-08-30 multi-agent audit.

**Architecture:** Keep `TradingSuite.create()` as the public entry point. Add missing Gateway REST methods on existing mixins (`AuthenticationMixin`, `MarketDataMixin`, `OrderManager`, `PositionManager`). Do not invent unofficial HTTP paths. Filter on the client when Gateway request models omit a field.

**Tech Stack:** Python 3.12+, asyncio, httpx, Polars, Decimal, pytest-asyncio.

## Global Constraints

- Python 3.12+ type hints: `X | Y`, `dict[str, Any]`. No pandas.
- Prices: `Decimal` internally; tick-size align before sending orders.
- Official Gateway contract is `https://api.topstepx.com/swagger/v1/swagger.json` (saved at `.grok/review-2026-08-30/gateway-swagger.json`).
- Mutating POSTs (`/Order/place|cancel|modify`, `/Position/closeContract|partialCloseContract`) must never be retried after timeout/disconnect/5xx/401/429/ReadError.
- Public APIs stay compatible; deprecate for 2 minor versions.
- Tests: `@pytest.mark.asyncio`, `uv run pytest`. Examples: `./test.sh` only.
- Conventional Commits.

---

## Priority 0 — Live-money bugs

1. Partial close payload `closeSize` → `size`
2. Native bracket success must never place a second entry
3. Position-order tracking: honor nested `{entry,stop,target}_orders` lists
4. JWT refresh must not self-deadlock on `_connection_lock`
5. Health mixin `connect`/`disconnect` must run (MRO)
6. OrderBook depth: accept GatewayDepth dict + `volume` (fallback `size`)
7. Position sizing must use `tickSize`/`tickValue` when instrument is provided
8. `/Order/searchOpen` send only `accountId`; filter contract/side locally
9. No 401/429 retry on mutating POSTs; treat `httpx.ReadError` as uncertain
10. `list_accounts` uses `Account.from_api`
11. `get_all_positions` raises on search failure; prune vanished positions

## Priority 1 — Official API coverage

12. `POST /Auth/validate` (token refresh → `newToken`)
13. `POST /Auth/logout`
14. `GET /Status/ping`
15. `POST /Contract/searchById` for `CON.*` ids
16. `POST /Contract/available`
17. `POST /Order/searchById` in `get_order_by_id`
18. `POST /Order/v2/query` for Suspended bracket children
19. `get_bars(live=...)` + 20,000 bar cap + unit 7 (Tick)
20. `modify_order(trail_price=...)`
21. Omit `linkedOrderId` unless set
22. `OrderStatus.PENDING_CANCELLATION=7`, `SUSPENDED=8`

## Priority 2 — Reliability / cleanup

23. Emit order events after releasing `order_lock`
24. `_wait_for_order_fill` uses `EventBus.off`
25. Trailing stop only ratchets in the favorable direction
26. Market unsubscribe loops per contract id (match subscribe)
27. `UnsubscribeAccounts` with no args (match `SubscribeAccounts`)
28. Unmarked pytest tests default to `unit`
29. Stale docstring fields (`netPos`, `buyAvgPrice`, `filledQty`)
30. Order tracker deprecation text: remove in v5.0.0 not v4.0.0

---

## Status

Shipped on `fix/sdk-audit-hardening` (2026-08-30). Leftovers (risk OCO, realtime watchdog, docs/shims, extra tests) are in `docs/superpowers/plans/2026-08-30-remaining-audit-items.md`.

## Out of scope (do not do in this pass)

- `Auth/loginApp` (firm/app login, not trader API-key flow)
- Implementing real TRADE_JOURNAL / news-event calendar
- Rewriting all 59+ indicators to TA-Lib golden values
- Changing public OrderTracker removal (still 5.0.0)
