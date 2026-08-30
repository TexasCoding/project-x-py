# v4.0 Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make v4.0 safe for live orders, correct on Gateway reconciliation, and documentarily accurate.

**Architecture:** Keep TradingSuite / mixin layout. Fix HTTP retry and realtime restore at the shared mixins so every manager inherits the safety. Native brackets fall back to the existing client-side OCO path when Gateway children cannot be uniquely resolved.

**Tech Stack:** Python 3.12+, pytest-asyncio, httpx, pysignalr, Polars, Hatchling.

## Global Constraints

- 100% async-first; tests use `@pytest.mark.asyncio`
- TDD: failing test first, then minimal implementation
- Polars only; Decimal for prices
- Modern type hints (`X | Y`)
- Backward compatible public APIs except where the v4.0 changelog already documented a break
- Run focused tests with `uv run pytest <file>::<test> -q`; do not invent env vars
- Do not retry mutating broker POSTs
- Do not report a native bracket as successful without uniquely identified child orders
- Credentials stay in env / constructor kwargs, never JSON config
- Patch version: these are post-4.0.0 correctness fixes; bump to **4.0.1**

---

## File map

| File | Responsibility |
|------|----------------|
| `src/project_x_py/client/http.py` | Mutating-endpoint detection, no retry, uncertain errors |
| `src/project_x_py/client/base.py` | Apply `requests_per_minute` to RateLimiter |
| `src/project_x_py/client/auth.py` | `Account.from_api` |
| `src/project_x_py/client/market_data.py` | `Instrument.from_api` |
| `src/project_x_py/client/trading.py` | Raise on failed position/trade search |
| `src/project_x_py/models.py` | `from_api` aliases, Account/Instrument constructors |
| `src/project_x_py/config.py` | Reject non-local `http://` API/hub URLs |
| `src/project_x_py/order_manager/core.py` | max_order_size / integer size / cancel uncertain |
| `src/project_x_py/order_manager/bracket_orders.py` | Native child resolution + partial fills |
| `src/project_x_py/order_manager/tracking.py` | POST `/Order/search` recovery |
| `src/project_x_py/realtime/async_hub.py` | JWT-free task names |
| `src/project_x_py/realtime/connection_management.py` | Restore subscriptions; hub names |
| `src/project_x_py/realtime/health_monitoring.py` | Call restore after reconnect |
| `src/project_x_py/realtime/subscriptions.py` | Track `_user_updates_subscribed` |
| `.github/workflows/release.yml` | GitHub release only (no twine) |
| `.github/workflows/mkdocs-deploy.yml` | workflow_dispatch only |
| `pyproject.toml` | Dynamic hatch version, drop 3.14 classifier, hatch exclude |
| Docs / CHANGELOG / junk files | Phase 3 |

---

### Task 1: No retry on mutating POSTs

**Files:**
- Modify: `src/project_x_py/client/http.py`
- Test: `tests/client/test_http.py`
- Test: `tests/order_manager/test_order_core.py`

**Produces:**
- `MUTATING_ENDPOINTS` frozenset
- `_is_mutating_request(method, endpoint) -> bool`
- Mutating timeout/connect/5xx/cancel → `OrderSubmissionUncertainError` and **one** HTTP attempt

Mutating endpoints: `/Order/place`, `/Order/cancel`, `/Order/modify`, `/Position/closeContract`, `/Position/partialCloseContract`.

GET `/test/endpoint` retries stay as they are.

- [ ] Write failing tests: place POST 503 is attempted once and raises `OrderSubmissionUncertainError`; GET 503 still retries.
- [ ] Implement: skip `@retry_on_network_error` for mutating endpoints (inner execute + conditional retry). Map mutating CancelledError/Timeout/ConnectError/ServerError to `OrderSubmissionUncertainError`.
- [ ] Verify tests pass.

### Task 2: Restore subscriptions after health reconnect

**Files:**
- Modify: `src/project_x_py/realtime/health_monitoring.py`
- Modify: `src/project_x_py/realtime/connection_management.py`
- Modify: `src/project_x_py/realtime/subscriptions.py`
- Modify: `src/project_x_py/realtime/core.py` (`_user_updates_subscribed = False`)
- Test: `tests/realtime/test_health_monitoring.py`

**Produces:** `async def _restore_realtime_subscriptions(self) -> None`

- [ ] Write failing test: after `force_health_reconnect()`, `subscribe_user_updates` and `subscribe_market_data` are called with the prior contract list.
- [ ] Implement restore; set `_user_updates_subscribed` in subscribe/unsubscribe; call restore after successful reconnect; schedule restore from hub `on_open` when flags are set.
- [ ] Verify tests pass.

### Task 3: Native brackets require unique children

**Files:**
- Modify: `src/project_x_py/order_manager/bracket_orders.py`
- Test: `tests/order_manager/test_bracket_orders.py`

**Produces:** `_try_native_bracket_order` returns `None` (fallback) if stop/target cannot be uniquely resolved. Match by protective side + type + size; never the first unmatched working order.

- [ ] Write failing tests: place success + no children → `None`; existing extra stop of different size is not stolen.
- [ ] Implement retry of `search_open_orders` (2 extra attempts) then fallback.
- [ ] Keep existing unique-child test green.

### Task 4: Stale-order recovery uses POST /Order/search

**Files:**
- Modify: `src/project_x_py/order_manager/tracking.py`
- Test: `tests/order_manager/test_tracking_advanced.py`

- [ ] Write failing test asserting `_make_request("POST", "/Order/search", data=...)` not GET.
- [ ] Implement via `search_orders()` or equivalent POST body with accountId + timestamps.
- [ ] Verify.

### Task 5: Partial fills and filtered trade search

**Files:**
- Modify: `src/project_x_py/order_manager/bracket_orders.py`
- Modify: `src/project_x_py/client/trading.py` (`search_trades` optional `order_id`, tighter default when called from fill check)
- Test: `tests/order_manager/test_bracket_orders.py`

- [ ] When order missing and trades filled 1 of unknown size: `is_filled is False`.
- [ ] When tracked size is 2 and trades sum to 1: `(False, 1, 1)`.
- [ ] `_filled_size_from_trades` passes a short lookback (1 day) and filters `orderId`.

### Task 6: Tolerant constructors + honest search failures

**Files:**
- Modify: `src/project_x_py/models.py`
- Modify: `src/project_x_py/client/auth.py`
- Modify: `src/project_x_py/client/market_data.py`
- Modify: `src/project_x_py/client/trading.py`
- Test: `tests/types/test_models.py`, `tests/client/test_auth_simple.py` or market_data tests, `tests/client/` position/trade search tests

- [ ] `Account.from_api` / `Instrument.from_api` ignore extra fields.
- [ ] Order alias `filledSize` → `fillVolume`.
- [ ] `search_open_positions` / `search_trades` raise `ProjectXError` when dict `success` is false (do not return `[]`).
- [ ] List responses still work.

### Task 7: Order size cap, JWT-free task names, HTTPS hubs, rate-limit config

**Files:**
- Modify: `src/project_x_py/order_manager/core.py`
- Modify: `src/project_x_py/realtime/async_hub.py`
- Modify: `src/project_x_py/realtime/connection_management.py`
- Modify: `src/project_x_py/config.py`
- Modify: `src/project_x_py/client/base.py`
- Modify: `src/project_x_py/client/http.py` (`follow_redirects=False`)
- Tests: order core, realtime hub, config, client base

- [ ] `enable_order_validation` True: `size` must be `int`, `1 <= size <= max_order_size`.
- [ ] Task name is `hub:user` / `hub:market` (no query string).
- [ ] `http://` API/hub URLs rejected unless host is localhost/127.0.0.1.
- [ ] `RateLimiter(max_requests=config.requests_per_minute, window_seconds=60)`.

### Task 8: Docs, CI, version, junk

**Files:** remaining `docs/api/*.md`, `docs/guide/*.md`, `docs/getting-started/authentication.md`, `docs/examples/*.md`, `mkdocs.yml`, `CHANGELOG.md`, `pyproject.toml`, workflows, junk files.

- [ ] API/guide pages match models and public signatures (`orderId`, `averagePrice`, `get_stats()`, `get_order_by_id()`, `orders.close_position`, TopstepX URLs, `ProjectXAuthenticationError`).
- [ ] mkdocs nav: `api/risk-manager.md`, `indicators/lorenz.md`.
- [ ] `release.yml` GitHub release only; `publish-pypi.yml` remains the PyPI publisher.
- [ ] `mkdocs-deploy.yml` `workflow_dispatch` only (keep `docs.yml` as Pages deploy).
- [ ] `pyproject.toml`: `dynamic = ["version"]`, drop Python 3.14 classifier, hatch `force-exclude` `*.bak` `*.backup`.
- [ ] Delete: `DATETIME_PARSING_ISSUE.md`, `examples/possible_issue.py`, `src/**/*.bak`, `src/**/*.backup`, `tests/**/*.bak`, `tests/**/*.backup`.
- [ ] Bump `__version__` to 4.0.1; CHANGELOG `[4.0.1]`.
- [ ] Update `scripts/version_sync.py` README patterns if needed.

### Task 9: Quality gate

- [ ] `uv run pytest tests/client/test_http.py tests/order_manager/test_order_core.py tests/order_manager/test_bracket_orders.py tests/realtime/test_health_monitoring.py tests/types/test_models.py tests/config/test_config.py -q`
- [ ] `uv run ruff check src tests --fix` and `uv run ruff format src tests`
- [ ] `uv run mypy src/project_x_py/client/http.py src/project_x_py/order_manager/bracket_orders.py src/project_x_py/realtime/health_monitoring.py`

---

## Spec coverage

1. Phase 1 items 1–3 → Tasks 1–3
2. Phase 2 items 4–7 → Tasks 4–7
3. Phase 3 items 8–10 → Task 8
4. Verification → Task 9
