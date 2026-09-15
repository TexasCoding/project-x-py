# Coalesce Quote/Depth Forwards Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bound SignalR `quote_update` and `market_depth` forwarding so a 1-minute `NEW_BAR` handler still runs within ~1s of bar close during RTH-open floods (#143).

**Architecture:** Latest-wins coalescing at `_schedule_async_task` for `quote_update` and `market_depth` only. One in-flight drain per `(event_type, contract_id)`; extras overwrite a pending slot instead of spawning another `run_coroutine_threadsafe` task. `market_trade` and all user-hub events stay unbounded.

**Tech Stack:** asyncio, `threading.Lock` (SignalR threads), pytest-asyncio, existing `EventHandlingMixin`.

## Global Constraints

- Python 3.12+, async/await only; no pandas; `X | Y` type hints.
- Do not drop `market_trade` (volume/OHLC) or user events (`account_update`, `position_update`, `order_update`, `trade_execution`).
- Quotes are snapshots — latest-wins is correct. Depth is per-level incremental — coalescing may skip intermediate levels during a flood; document that and keep a drop counter. This matches the live consumer workaround that unstarved `NEW_BAR`.
- Coalesce per `(event_type, contract_id)` so MNQ quote flood does not starve MES.
- Coalescing applies even when `enable_batching()` is on (batching still schedules one coroutine per SignalR message today).
- Public API stays compatible. PATCH release 4.3.1.
- Tests live in `tests/realtime/test_event_handling.py` with `@pytest.mark.asyncio`.
- Never set `PROJECT_X_API_KEY` / `PROJECT_X_USERNAME` in the shell.

---

### Task 1: Failing tests for coalesced quote/depth scheduling

**Files:**
- Modify: `tests/realtime/test_event_handling.py`

**Interfaces:**
- Consumes: `EventHandlingMixin._schedule_async_task`, `_forward_quote_update`, `_forward_market_trade`, `_forward_market_depth`, `_forward_order_update`
- Produces: Regression tests that fail on unbounded `run_coroutine_threadsafe` per SignalR message

- [ ] **Step 1: Write the failing tests**

Add `TestCoalescedMarketEventScheduling` covering:

1. Quote flood while a slow quote callback is in-flight delivers the first quote and the latest pending quote, not every intermediate quote.
2. Depth flood is similarly bounded (1 in-flight + latest pending per contract).
3. `market_trade` is never dropped while quotes are flooding.
4. `order_update` / `position_update` are never dropped during a quote flood.
5. After the in-flight quote completes, the pending latest quote is forwarded.
6. MNQ quote flood still delivers the latest MES quote (per-contract keys).
7. A slow quote callback does not prevent a concurrently scheduled `market_trade` from completing quickly (NEW_BAR starvation analogue).
8. Dropped/coalesced counts are visible on the handler.
9. `cleanup()` / disconnect clears coalesce state so later events still schedule.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/realtime/test_event_handling.py::TestCoalescedMarketEventScheduling -v`

Expected: FAIL because every `_schedule_async_task` currently creates a new loop task.

- [ ] **Step 3: Commit tests**

```bash
git add tests/realtime/test_event_handling.py
git commit -m "test: reproduce unbounded quote/depth forward flood (#143)"
```

---

### Task 2: Coalesced scheduling in EventHandlingMixin

**Files:**
- Modify: `src/project_x_py/realtime/event_handling.py`
- Modify: `src/project_x_py/types/protocols.py`
- Modify: `src/project_x_py/realtime/connection_management.py` (`get_stats`)

**Interfaces:**
- Consumes: existing `_schedule_coroutine_threadsafe`, `_forward_event_async`
- Produces:
  - `_COALESCE_EVENTS = frozenset({"quote_update", "market_depth"})`
  - `_schedule_coalesced_event(event_type: str, data: Any) -> None`
  - `async def _drain_coalesced_event(self, key: tuple[str, str]) -> None`
  - `_market_contract_id(args: Any) -> str`
  - stats: `coalesced_quote_dropped`, `coalesced_depth_dropped`

- [ ] **Step 1: Implement latest-wins drain**

Thread-safe pending slot + inflight set. Drain loop pops latest, forwards, repeats until empty, then clears inflight under the same lock.

- [ ] **Step 2: Route quote/depth through coalesced path**

`_forward_quote_update` and `_forward_market_depth` always coalesce (batching included). `_forward_market_trade` and user forwards unchanged.

- [ ] **Step 3: Run tests to verify they pass**

Run: `uv run pytest tests/realtime/test_event_handling.py tests/realtime/test_batched_handler.py -v`

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git commit -m "fix: coalesce quote/depth forwards so NEW_BAR is not starved (#143)"
```

---

### Task 3: Docs, changelog, version 4.3.1

**Files:**
- `CHANGELOG.md`, `docs/changelog.md`, `docs/index.md`, `docs/guide/realtime.md`
- `README.md`, `examples/README.md`
- `src/project_x_py/__init__.py`, `indicators/__init__.py`, `statistics/__init__.py`
- `src/project_x_py/client/http.py` User-Agent

- [ ] **Step 1: Document coalescing behavior** (quotes/depth may skip intermediate updates under load; trades and user events are not dropped)
- [ ] **Step 2: Bump to 4.3.1** (PATCH)
- [ ] **Step 3: Quality gate** `./check_quality.sh` and `uv run pytest`

---

### Task 4: PR, merge, release, PyPI

- Branch: `fix/143-coalesce-quote-depth-forwards`
- PR against `main`, wait for CI
- Squash-merge, pull main
- Tag `v4.3.1` (or let `version-sync.yml` tag on main)
- GitHub release via tag workflow; dispatch `publish-pypi.yml` with `ref=v4.3.1`
