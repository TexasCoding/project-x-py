# Stats Re-entry and Rolling-Contract History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop `TradingSuite.get_stats()` from recursively collecting itself (#133), and make `get_bars()` page the 20k Gateway cap, stitch expired months for hourly+, and warn when the returned window is short (#134).

**Architecture:** #133 is a collection-path fix in `StatisticsAggregator`: skip the `"trading_suite"` component and cancel child tasks on timeout. #134 adds a pure CME calendar helper, then `get_bars()` pages `/History/retrieveBars`, stitches prior months via `searchById` for hourly+, and logs a warning when history is truncated. `get_instrument()` stays active-contract-only.

**Tech Stack:** Python 3.12+, pytest-asyncio, AsyncMock, Polars, existing `httpx` client mixins.

## Global Constraints

- Python 3.12+ type hints: `X | Y`, `dict[str, Any]`, `list[int]`. No `Optional`/`Union`/`Dict`.
- Async tests use `@pytest.mark.asyncio`. Do not use `asyncio.run()` in tests.
- Polars only for DataFrames. Never import pandas.
- Wrap HTTP/API failures in `project_x_py.exceptions`. No bare `except:`.
- Public APIs stay compatible: `get_bars` / `get_stats` signatures unchanged; no stitch on/off flag.
- `get_instrument()` remains active contract for trading. Stitching is history-only.
- Sub-hour bars (`unit == 1`, or `unit == 2` and `interval < 60`) never stitch.
- `HISTORY_BAR_LIMIT` stays 20_000. Tests may set a smaller instance attribute.
- Do not export `PROJECT_X_API_KEY` or `PROJECT_X_USERNAME`. Unit tests use mocks only.
- Conventional Commits (`fix:`, `feat:`, `docs:`).
- Run tests with `uv run pytest`. Examples would use `./test.sh` (not needed here).

## File map

| File | Role |
|---|---|
| `src/project_x_py/statistics/aggregator.py` | Skip `"trading_suite"` collection; cancel tasks on timeout; keep partial results |
| `src/project_x_py/client/contract_calendar.py` | Pure CME month-code parse / prior-id iterator |
| `src/project_x_py/client/market_data.py` | Page retrieveBars, stitch hourly+, warn if short |
| `tests/statistics/test_statistics_module.py` | #133 tests on `TestStatisticsAggregator` |
| `tests/client/test_contract_calendar.py` | Calendar unit tests |
| `tests/client/test_get_bars_history.py` | Paging, stitch, warning tests |
| `CHANGELOG.md` | Unreleased notes for #133 and #134 |

---

### Task 1: Skip `trading_suite` stats collection

**Files:**
- Modify: `src/project_x_py/statistics/aggregator.py` (`_collect_all_components`, `_collect_component_stats`)
- Test: `tests/statistics/test_statistics_module.py`

**Interfaces:**
- Consumes: existing `StatisticsAggregator.register_component`, `_collect_all_components`, `_collect_component_stats`, `__setattr__` pending `"trading_suite"`
- Produces: `_collect_all_components` never calls `get_stats()` / `get_statistics()` on a component named `"trading_suite"`; `_collect_component_stats("trading_suite", …)` returns `None`

- [ ] **Step 1: Write the failing tests**

Append these methods to `class TestStatisticsAggregator` in `tests/statistics/test_statistics_module.py` (after `test_collect_component_stats_timeout_does_not_fall_through`):

```python
    @pytest.mark.asyncio
    async def test_collect_component_stats_skips_trading_suite(self):
        """Issue #133: never invoke get_stats on the suite component."""
        aggregator = StatisticsAggregator()

        class Suite:
            async def get_stats(self) -> dict:
                raise AssertionError("trading_suite.get_stats must not be called")

        stats = await aggregator._collect_component_stats("trading_suite", Suite())
        assert stats is None

    @pytest.mark.asyncio
    async def test_collect_all_components_skips_trading_suite(self):
        """Issue #133: fallback collection must not re-enter suite.get_stats()."""
        aggregator = StatisticsAggregator()

        class Suite:
            async def get_stats(self) -> dict:
                raise AssertionError("trading_suite.get_stats must not be called")

        class Orders:
            async def get_stats(self) -> dict:
                return {"status": "ok", "operations": 1}

        await aggregator.register_component("trading_suite", Suite())
        await aggregator.register_component("order_manager", Orders())
        aggregator._collector = None

        stats = await aggregator._collect_all_components()
        assert "trading_suite" not in stats
        assert stats["order_manager"] == {"status": "ok", "operations": 1}

    @pytest.mark.asyncio
    async def test_suite_get_stats_does_not_reenter(self):
        """Issue #133: aggregator.trading_suite = suite must not recurse."""
        aggregator = StatisticsAggregator(component_timeout=0.5)
        calls = {"n": 0}

        class FakeSuite:
            suite_id = "test-suite"
            instrument = "MNQ"
            created_at = time.time()

            async def get_stats(self) -> dict:
                calls["n"] += 1
                if calls["n"] > 3:
                    raise AssertionError("unbounded get_stats re-entry")
                return await aggregator.aggregate_stats()

        suite = FakeSuite()
        aggregator.trading_suite = suite
        aggregator._collector = None

        stats = await asyncio.wait_for(suite.get_stats(), timeout=2.0)
        assert calls["n"] == 1
        assert stats is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/statistics/test_statistics_module.py::TestStatisticsAggregator::test_collect_component_stats_skips_trading_suite tests/statistics/test_statistics_module.py::TestStatisticsAggregator::test_collect_all_components_skips_trading_suite tests/statistics/test_statistics_module.py::TestStatisticsAggregator::test_suite_get_stats_does_not_reenter -v
```

Expected: FAIL — first test raises `AssertionError: trading_suite.get_stats must not be called` (or the wait_for times out / RecursionError on the third).

- [ ] **Step 3: Write minimal implementation**

In `src/project_x_py/statistics/aggregator.py`, at the top of `_collect_component_stats` (immediately inside the method, before `try:`), return `None` for the suite name:

```python
    async def _collect_component_stats(
        self, name: str, component: Any
    ) -> dict[str, Any] | None:
        if name == "trading_suite":
            return None
        try:
            start_time = time.time()
            # ... existing body unchanged ...
```

In `_collect_all_components`, filter the fallback task list (replace the loop that currently iterates all `components`):

```python
        async with self._component_lock:
            components = list(self._components.items())

        collectible = [
            (name, component)
            for name, component in components
            if name != "trading_suite"
        ]

        tasks = []
        for name, component in collectible:
            task = asyncio.create_task(self._collect_component_stats(name, component))
            tasks.append(task)

        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=self.component_timeout * max(len(collectible), 1),
            )

            component_stats = {}
            for (name, _), result in zip(collectible, results, strict=False):
                if isinstance(result, Exception):
                    await self.track_error(
                        result,
                        f"Failed to collect statistics from {name}",
                        {"component_name": name},
                    )
                elif result is not None:
                    component_stats[name] = result

            return component_stats

        except TimeoutError:
            await self.track_error(
                TimeoutError("Component collection timed out"),
                "Parallel component collection",
            )
            return {}
```

Keep the collector `wait_for` path above this fallback unchanged.

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest tests/statistics/test_statistics_module.py::TestStatisticsAggregator::test_collect_component_stats_skips_trading_suite tests/statistics/test_statistics_module.py::TestStatisticsAggregator::test_collect_all_components_skips_trading_suite tests/statistics/test_statistics_module.py::TestStatisticsAggregator::test_suite_get_stats_does_not_reenter tests/statistics/test_statistics_module.py::TestStatisticsAggregator -v
```

Expected: PASS for the new tests; existing `TestStatisticsAggregator` tests still pass.

- [ ] **Step 5: Commit**

```bash
git add tests/statistics/test_statistics_module.py src/project_x_py/statistics/aggregator.py
git commit -m "fix: skip TradingSuite as a stats component of itself (#133)"
```

---

### Task 2: Cancel collection tasks on timeout and keep partial results

**Files:**
- Modify: `src/project_x_py/statistics/aggregator.py` (`_collect_all_components` TimeoutError branch)
- Test: `tests/statistics/test_statistics_module.py`

**Interfaces:**
- Consumes: Task 1 `collectible` task list and `asyncio.create_task(_collect_component_stats(...))`
- Produces: on outer `TimeoutError`, every not-done child is cancelled, `await asyncio.gather(*tasks, return_exceptions=True)` runs, finished non-exception results are returned (not `{}`)

- [ ] **Step 1: Write the failing tests**

Append to `class TestStatisticsAggregator`:

```python
    @pytest.mark.asyncio
    async def test_collection_timeout_cancels_pending_tasks(self):
        """Issue #133: timeout must cancel children so they do not leak."""
        aggregator = StatisticsAggregator(component_timeout=0.05)

        class Slow:
            async def get_stats(self) -> dict:
                await asyncio.sleep(30)
                return {"slow": True}

        await aggregator.register_component("slow", Slow())
        aggregator._collector = None

        async def invoke_without_inner_timeout(method: object) -> object:
            return await method()  # type: ignore[misc,operator]

        aggregator._invoke_stats_method = invoke_without_inner_timeout  # type: ignore[method-assign]

        before = {id(task) for task in asyncio.all_tasks()}
        await aggregator._collect_all_components()
        await asyncio.sleep(0)
        leaked = [
            task
            for task in asyncio.all_tasks()
            if id(task) not in before and not task.done()
        ]
        assert leaked == []

    @pytest.mark.asyncio
    async def test_collection_timeout_keeps_finished_results(self):
        """Issue #133: timed-out gather must still return finished components."""
        aggregator = StatisticsAggregator(component_timeout=0.05)

        class Fast:
            async def get_stats(self) -> dict:
                return {"status": "fast"}

        class Slow:
            async def get_stats(self) -> dict:
                await asyncio.sleep(30)
                return {"status": "slow"}

        await aggregator.register_component("fast", Fast())
        await aggregator.register_component("slow", Slow())
        aggregator._collector = None

        async def invoke_without_inner_timeout(method: object) -> object:
            return await method()  # type: ignore[misc,operator]

        aggregator._invoke_stats_method = invoke_without_inner_timeout  # type: ignore[method-assign]

        stats = await aggregator._collect_all_components()
        assert stats.get("fast") == {"status": "fast"}
        assert "slow" not in stats
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/statistics/test_statistics_module.py::TestStatisticsAggregator::test_collection_timeout_cancels_pending_tasks tests/statistics/test_statistics_module.py::TestStatisticsAggregator::test_collection_timeout_keeps_finished_results -v
```

Expected: FAIL — leaked tasks nonempty and/or `stats == {}` so `"fast"` is missing.

- [ ] **Step 3: Write minimal implementation**

Replace the `except TimeoutError:` branch in `_collect_all_components` with:

```python
        except TimeoutError:
            await self.track_error(
                TimeoutError("Component collection timed out"),
                "Parallel component collection",
            )
            for task in tasks:
                if not task.done():
                    task.cancel()
            results = await asyncio.gather(*tasks, return_exceptions=True)
            component_stats: dict[str, Any] = {}
            for (name, _), result in zip(collectible, results, strict=False):
                if isinstance(result, asyncio.CancelledError):
                    continue
                if isinstance(result, Exception):
                    await self.track_error(
                        result,
                        f"Failed to collect statistics from {name}",
                        {"component_name": name},
                    )
                elif result is not None:
                    component_stats[name] = result
            return component_stats
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest tests/statistics/test_statistics_module.py::TestStatisticsAggregator -v
```

Expected: PASS, including both new timeout tests.

- [ ] **Step 5: Commit**

```bash
git add tests/statistics/test_statistics_module.py src/project_x_py/statistics/aggregator.py
git commit -m "fix: cancel stats collection tasks on timeout (#133)"
```

---

### Task 3: CME contract calendar helper

**Files:**
- Create: `src/project_x_py/client/contract_calendar.py`
- Test: `tests/client/test_contract_calendar.py`

**Interfaces:**
- Consumes: nothing from Tasks 1–2
- Produces:
  - `CME_MONTH_CODES: str` = `"FGHJKMNQUVXZ"`
  - `parse_contract_id(contract_id: str) -> tuple[str, str, int] | None`
  - `iter_prior_contract_ids(contract_id: str, max_count: int = 24) -> Iterator[str]`

- [ ] **Step 1: Write the failing tests**

Create `tests/client/test_contract_calendar.py`:

```python
"""Unit tests for CME contract-id calendar helpers."""

from project_x_py.client.contract_calendar import (
    CME_MONTH_CODES,
    iter_prior_contract_ids,
    parse_contract_id,
)


def test_cme_month_codes_are_calendar_order():
    assert CME_MONTH_CODES == "FGHJKMNQUVXZ"


def test_parse_contract_id_mnq_u26():
    assert parse_contract_id("CON.F.US.MNQ.U26") == ("MNQ", "U", 26)


def test_parse_contract_id_digit_root():
    assert parse_contract_id("CON.F.US.M6E.U26") == ("M6E", "U", 26)


def test_parse_contract_id_rejects_garbage():
    assert parse_contract_id("MNQ") is None
    assert parse_contract_id("CON.F.US.MNQ") is None
    assert parse_contract_id("") is None


def test_iter_prior_from_u26_starts_q_n_m():
    prior = list(iter_prior_contract_ids("CON.F.US.MNQ.U26", max_count=3))
    assert prior == [
        "CON.F.US.MNQ.Q26",
        "CON.F.US.MNQ.N26",
        "CON.F.US.MNQ.M26",
    ]


def test_iter_prior_wraps_year_at_january():
    prior = list(iter_prior_contract_ids("CON.F.US.MNQ.F26", max_count=1))
    assert prior == ["CON.F.US.MNQ.Z25"]


def test_iter_prior_empty_for_invalid_id():
    assert list(iter_prior_contract_ids("MNQ")) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/client/test_contract_calendar.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'project_x_py.client.contract_calendar'`.

- [ ] **Step 3: Write minimal implementation**

Create `src/project_x_py/client/contract_calendar.py`:

```python
"""CME futures month codes and prior-contract-id iteration.

Used by historical bar stitching. No I/O.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

CME_MONTH_CODES = "FGHJKMNQUVXZ"

_CONTRACT_ID_RE = re.compile(
    r"^CON\.[A-Z]\.[A-Z]{2}\.(.+)\.([FGHJKMNQUVXZ])(\d{1,2})$"
)


def parse_contract_id(contract_id: str) -> tuple[str, str, int] | None:
    """Return (root, month_code, two_digit_year) or None if not a CON. id."""
    match = _CONTRACT_ID_RE.match(contract_id)
    if match is None:
        return None
    root, month_code, year_s = match.groups()
    return root, month_code, int(year_s)


def iter_prior_contract_ids(
    contract_id: str, max_count: int = 24
) -> Iterator[str]:
    """Yield previous CME month ids, wrapping F → previous-year Z.

    Bounded by ``max_count`` so callers can ``list()`` safely.
    """
    parsed = parse_contract_id(contract_id)
    if parsed is None or max_count <= 0:
        return
    _root, month_code, year = parsed
    prefix = contract_id.rsplit(".", 1)[0]
    idx = CME_MONTH_CODES.index(month_code)
    yielded = 0
    while yielded < max_count:
        idx -= 1
        if idx < 0:
            idx = len(CME_MONTH_CODES) - 1
            year -= 1
            if year < 0:
                return
        yield f"{prefix}.{CME_MONTH_CODES[idx]}{year:02d}"
        yielded += 1
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest tests/client/test_contract_calendar.py -v
```

Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add src/project_x_py/client/contract_calendar.py tests/client/test_contract_calendar.py
git commit -m "feat: add CME contract calendar for prior-month history (#134)"
```

---

### Task 4: Page `/History/retrieveBars` at the 20k cap

**Files:**
- Modify: `src/project_x_py/client/market_data.py` (`get_bars` and new private helpers)
- Test: `tests/client/test_get_bars_history.py`

**Interfaces:**
- Consumes: existing `get_instrument`, `_make_request`, `HISTORY_BAR_LIMIT`, timezone conversion in `get_bars`
- Produces:
  - `_dataframe_from_bars_response(self, response: Any) -> pl.DataFrame`
  - `_retrieve_bars_paged(self, contract_id: str, start_date: datetime.datetime, end_date: datetime.datetime, interval: int, unit: int, live: bool, partial: bool, page_limit: int) -> tuple[pl.DataFrame, bool]`
    - `bool` is `True` when the first Gateway call returned `success: true`
  - `get_bars` uses paging instead of a single retrieveBars call

- [ ] **Step 1: Write the failing tests**

Create `tests/client/test_get_bars_history.py`:

```python
"""Tests for get_bars paging, contract stitch, and short-range warning (#134)."""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock

import pytest
import pytz

from project_x_py.models import Instrument


def _bar(ts: str, close: float = 100.0) -> dict[str, object]:
    return {
        "t": ts,
        "o": close,
        "h": close,
        "l": close,
        "c": close,
        "v": 1,
    }


def _instrument() -> Instrument:
    return Instrument(
        id="CON.F.US.MNQ.U26",
        name="MNQU6",
        description="Micro E-mini Nasdaq-100: September 2026",
        tickSize=0.25,
        tickValue=0.5,
        activeContract=True,
        symbolId="F.US.MNQ",
    )


@pytest.fixture
def history_client(initialized_client):
    client = initialized_client
    client._ensure_authenticated = AsyncMock(return_value=None)
    client.get_cached_instrument = lambda _symbol: None
    client.cache_instrument = lambda *_args, **_kwargs: None
    client.get_cached_market_data = lambda _key: None
    client.cache_market_data = lambda *_args, **_kwargs: None
    client.get_instrument = AsyncMock(return_value=_instrument())
    client.HISTORY_BAR_LIMIT = 2
    return client


@pytest.mark.asyncio
async def test_get_bars_pages_when_first_response_is_full(history_client):
    """A full page must trigger a second retrieveBars with an earlier endTime."""
    history_client._make_request = AsyncMock(
        side_effect=[
            {
                "success": True,
                "bars": [
                    _bar("2026-08-02T00:00:00+00:00", 2.0),
                    _bar("2026-08-01T00:00:00+00:00", 1.0),
                ],
            },
            {
                "success": True,
                "bars": [
                    _bar("2026-07-31T00:00:00+00:00", 0.0),
                ],
            },
        ]
    )
    start = datetime.datetime(2026, 7, 31, 0, 0, 0, tzinfo=pytz.UTC)
    end = datetime.datetime(2026, 8, 2, 0, 0, 0, tzinfo=pytz.UTC)
    bars = await history_client.get_bars(
        "MNQ",
        interval=1,
        unit=4,
        start_time=start,
        end_time=end,
        partial=False,
    )
    history_calls = [
        call
        for call in history_client._make_request.await_args_list
        if call.args[1] == "/History/retrieveBars"
    ]
    assert len(history_calls) == 2
    second_end = history_calls[1].kwargs["data"]["endTime"]
    assert second_end.startswith("2026-08-01")
    assert len(bars) == 3
    assert bars["timestamp"].min() is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/client/test_get_bars_history.py::test_get_bars_pages_when_first_response_is_full -v
```

Expected: FAIL — only one `/History/retrieveBars` call, `len(history_calls) == 2` assertion fails.

- [ ] **Step 3: Write minimal implementation**

In `src/project_x_py/client/market_data.py`, add helpers on `MarketDataMixin` (after `_select_best_contract`, before `list_available_contracts` is fine; or immediately above `get_bars`). Then change `get_bars` to call `_retrieve_bars_paged` instead of a single `_make_request`.

Helpers:

```python
    def _dataframe_from_bars_response(self, response: Any) -> pl.DataFrame:
        if not response or not isinstance(response, dict):
            return pl.DataFrame()
        if not response.get("success", False):
            error_msg = response.get("errorMessage", "Unknown error")
            self.logger.error(
                LogMessages.DATA_ERROR,
                extra={"operation": "get_history", "error": error_msg},
            )
            return pl.DataFrame()
        bars_data = response.get("bars", [])
        if not bars_data:
            return pl.DataFrame()
        data = (
            pl.DataFrame(bars_data)
            .sort("t")
            .rename(
                {
                    "t": "timestamp",
                    "o": "open",
                    "h": "high",
                    "l": "low",
                    "c": "close",
                    "v": "volume",
                }
            )
        )
        canonical = ["timestamp", "open", "high", "low", "close", "volume"]
        extra = [column for column in data.columns if column not in canonical]
        data = data.select(canonical + extra)
        try:
            data = data.with_columns(
                pl.col("timestamp")
                .str.to_datetime()
                .dt.replace_time_zone("UTC")
                .dt.convert_time_zone(self.config.timezone)
            )
        except Exception:
            try:
                data = data.with_columns(
                    pl.col("timestamp")
                    .str.to_datetime(time_zone="UTC")
                    .dt.convert_time_zone(self.config.timezone)
                )
            except Exception:
                data = data.with_columns(
                    pl.when(pl.col("timestamp").str.contains("[+-]\\d{2}:\\d{2}$|Z$"))
                    .then(pl.col("timestamp").str.to_datetime())
                    .otherwise(
                        pl.col("timestamp")
                        .str.to_datetime()
                        .dt.replace_time_zone("UTC")
                    )
                    .dt.convert_time_zone(self.config.timezone)
                    .alias("timestamp")
                )
        if data.is_empty():
            return data
        return data.sort("timestamp")

    async def _retrieve_bars_paged(
        self,
        contract_id: str,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
        interval: int,
        unit: int,
        live: bool,
        partial: bool,
        page_limit: int,
    ) -> tuple[pl.DataFrame, bool]:
        frames: list[pl.DataFrame] = []
        page_end = end_date
        first_ok = False
        cap = max(1, min(int(page_limit), self.HISTORY_BAR_LIMIT))
        for page_index in range(20):
            payload = {
                "contractId": contract_id,
                "live": live,
                "startTime": start_date.astimezone(pytz.UTC).isoformat(),
                "endTime": page_end.astimezone(pytz.UTC).isoformat(),
                "unit": unit,
                "unitNumber": interval,
                "limit": cap,
                "includePartialBar": partial,
            }
            response = await self._make_request(
                "POST", "/History/retrieveBars", data=payload
            )
            if page_index == 0:
                if (
                    not response
                    or not isinstance(response, dict)
                    or not response.get("success", False)
                ):
                    if response and isinstance(response, dict):
                        self._dataframe_from_bars_response(response)
                    return pl.DataFrame(), False
                first_ok = True
            frame = self._dataframe_from_bars_response(response)
            if frame.is_empty():
                break
            frames.append(frame)
            earliest = frame["timestamp"].min()
            if len(frame) < self.HISTORY_BAR_LIMIT:
                break
            if earliest is None or earliest <= start_date:
                break
            page_end = earliest
        if not frames:
            return pl.DataFrame(), first_ok
        data = pl.concat(frames).unique(subset=["timestamp"], keep="last")
        return data.sort("timestamp"), True
```

In `get_bars`, after `instrument = await self.get_instrument(symbol)` and computing `limit`, replace the single retrieveBars + DataFrame conversion block with:

```python
        data, gateway_ok = await self._retrieve_bars_paged(
            instrument.id,
            start_date,
            end_date,
            interval,
            unit,
            live,
            partial,
            limit,
        )
        if not gateway_ok:
            return pl.DataFrame()
        if data.is_empty():
            return data
        self.cache_market_data(cache_key, data)
        return data
```

Delete the old inline payload / `_make_request` / rename / timezone block that this replaces. Keep cache-hit return and `get_instrument` as they are.

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest tests/client/test_get_bars_history.py::test_get_bars_pages_when_first_response_is_full tests/client/test_market_data.py -v
```

Expected: PASS. Existing `get_bars` tests still pass (they mock a single successful bars response).

- [ ] **Step 5: Commit**

```bash
git add src/project_x_py/client/market_data.py tests/client/test_get_bars_history.py
git commit -m "fix: page History/retrieveBars at the 20k cap (#134)"
```

---

### Task 5: Stitch prior months for hourly and coarser `get_bars`

**Files:**
- Modify: `src/project_x_py/client/market_data.py`
- Test: `tests/client/test_get_bars_history.py`

**Interfaces:**
- Consumes: Task 3 `iter_prior_contract_ids(contract_id: str, max_count: int = 24) -> Iterator[str]`; Task 4 `_retrieve_bars_paged(...) -> tuple[pl.DataFrame, bool]`
- Produces:
  - `_should_stitch_contracts(symbol: str, unit: int, interval: int) -> bool`
  - `_stitch_prior_contract_bars(...) -> pl.DataFrame`
  - `get_bars("MNQ", unit=3)` stitches; `get_bars("CON.…")` and 15-minute do not

- [ ] **Step 1: Write the failing tests**

Append to `tests/client/test_get_bars_history.py`:

```python
@pytest.mark.asyncio
async def test_get_bars_does_not_stitch_full_contract_id(history_client):
    history_client._make_request = AsyncMock(
        return_value={
            "success": True,
            "bars": [_bar("2026-08-01T00:00:00+00:00")],
        }
    )
    start = datetime.datetime(2026, 3, 31, tzinfo=pytz.UTC)
    end = datetime.datetime(2026, 8, 1, tzinfo=pytz.UTC)
    await history_client.get_bars(
        "CON.F.US.MNQ.U26",
        interval=1,
        unit=3,
        start_time=start,
        end_time=end,
        partial=False,
    )
    endpoints = [call.args[1] for call in history_client._make_request.await_args_list]
    assert "/Contract/searchById" not in endpoints


@pytest.mark.asyncio
async def test_get_bars_does_not_stitch_15_minute(history_client):
    history_client._make_request = AsyncMock(
        return_value={
            "success": True,
            "bars": [_bar("2026-07-02T22:30:00+00:00")],
        }
    )
    start = datetime.datetime(2026, 3, 31, tzinfo=pytz.UTC)
    end = datetime.datetime(2026, 8, 23, tzinfo=pytz.UTC)
    await history_client.get_bars(
        "MNQ",
        interval=15,
        unit=2,
        start_time=start,
        end_time=end,
        partial=False,
    )
    endpoints = [call.args[1] for call in history_client._make_request.await_args_list]
    assert "/Contract/searchById" not in endpoints


@pytest.mark.asyncio
async def test_get_bars_stitches_hourly_prior_month(history_client):
    async def make_request(method: str, endpoint: str, data: dict | None = None, **_kwargs):
        if endpoint == "/History/retrieveBars":
            cid = (data or {}).get("contractId")
            if cid == "CON.F.US.MNQ.U26":
                return {
                    "success": True,
                    "bars": [_bar("2026-07-02T00:00:00+00:00", 2.0)],
                }
            if cid == "CON.F.US.MNQ.M26":
                return {
                    "success": True,
                    "bars": [_bar("2026-06-01T00:00:00+00:00", 1.0)],
                }
            return {"success": True, "bars": []}
        if endpoint == "/Contract/searchById":
            cid = (data or {}).get("contractId")
            if cid == "CON.F.US.MNQ.M26":
                return {
                    "success": True,
                    "contract": {
                        "id": cid,
                        "name": "MNQM6",
                        "description": "June",
                        "tickSize": 0.25,
                        "tickValue": 0.5,
                        "activeContract": False,
                    },
                }
            return {"success": True, "contract": None}
        raise AssertionError(f"unexpected {endpoint}")

    history_client._make_request = AsyncMock(side_effect=make_request)
    history_client.HISTORY_BAR_LIMIT = 20_000
    start = datetime.datetime(2026, 6, 1, tzinfo=pytz.UTC)
    end = datetime.datetime(2026, 7, 2, tzinfo=pytz.UTC)
    bars = await history_client.get_bars(
        "MNQ",
        interval=1,
        unit=3,
        start_time=start,
        end_time=end,
        partial=False,
    )
    endpoints = [call.args[1] for call in history_client._make_request.await_args_list]
    assert "/Contract/searchById" in endpoints
    assert len(bars) == 2
    closes = bars.sort("timestamp")["close"].to_list()
    assert closes == [1.0, 2.0]


@pytest.mark.asyncio
async def test_get_bars_overlap_keeps_later_month(history_client):
    overlap_ts = "2026-06-18T00:00:00+00:00"

    async def make_request(method: str, endpoint: str, data: dict | None = None, **_kwargs):
        if endpoint == "/History/retrieveBars":
            cid = (data or {}).get("contractId")
            if cid == "CON.F.US.MNQ.U26":
                return {
                    "success": True,
                    "bars": [_bar(overlap_ts, 9.0), _bar("2026-07-01T00:00:00+00:00", 10.0)],
                }
            if cid == "CON.F.US.MNQ.M26":
                return {
                    "success": True,
                    "bars": [_bar(overlap_ts, 1.0)],
                }
            return {"success": True, "bars": []}
        if endpoint == "/Contract/searchById":
            cid = (data or {}).get("contractId")
            if cid == "CON.F.US.MNQ.M26":
                return {
                    "success": True,
                    "contract": {
                        "id": cid,
                        "name": "MNQM6",
                        "description": "June",
                        "tickSize": 0.25,
                        "tickValue": 0.5,
                        "activeContract": False,
                    },
                }
            return {"success": True, "contract": None}
        raise AssertionError(f"unexpected {endpoint}")

    history_client._make_request = AsyncMock(side_effect=make_request)
    history_client.HISTORY_BAR_LIMIT = 20_000
    start = datetime.datetime(2026, 6, 1, tzinfo=pytz.UTC)
    end = datetime.datetime(2026, 7, 1, tzinfo=pytz.UTC)
    bars = await history_client.get_bars(
        "MNQ",
        interval=1,
        unit=3,
        start_time=start,
        end_time=end,
        partial=False,
    )
    overlap = bars.filter(pl.col("close") == 9.0)
    assert len(overlap) == 1
    assert len(bars.filter(pl.col("close") == 1.0)) == 0
```

Add `import polars as pl` at the top of the test file.

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/client/test_get_bars_history.py::test_get_bars_stitches_hourly_prior_month tests/client/test_get_bars_history.py::test_get_bars_overlap_keeps_later_month -v
```

Expected: FAIL — `/Contract/searchById` not called; `len(bars) == 2` fails.

- [ ] **Step 3: Write minimal implementation**

Add to `MarketDataMixin` in `src/project_x_py/client/market_data.py`:

```python
    @staticmethod
    def _should_stitch_contracts(symbol: str, unit: int, interval: int) -> bool:
        if symbol.startswith("CON."):
            return False
        if unit >= 3:
            return True
        return unit == 2 and interval >= 60

    async def _stitch_prior_contract_bars(
        self,
        active_contract_id: str,
        existing: pl.DataFrame,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
        interval: int,
        unit: int,
        live: bool,
        partial: bool,
        page_limit: int,
    ) -> pl.DataFrame:
        from project_x_py.client.contract_calendar import iter_prior_contract_ids

        if existing.is_empty():
            current_earliest: datetime.datetime = end_date
        else:
            current_earliest = existing["timestamp"].min()
        collected: list[pl.DataFrame] = []
        misses = 0
        attempts = 0
        for prior_id in iter_prior_contract_ids(active_contract_id, max_count=16):
            attempts += 1
            if attempts > 16:
                break
            if current_earliest <= start_date:
                break
            try:
                by_id = await self._make_request(
                    "POST", "/Contract/searchById", data={"contractId": prior_id}
                )
            except Exception:
                misses += 1
                if misses >= 4:
                    break
                continue
            contract = (
                by_id.get("contract")
                if isinstance(by_id, dict) and by_id.get("success")
                else None
            )
            if not isinstance(contract, dict):
                misses += 1
                if misses >= 4:
                    break
                continue
            misses = 0
            chunk, chunk_ok = await self._retrieve_bars_paged(
                prior_id,
                start_date,
                current_earliest,
                interval,
                unit,
                live,
                partial,
                page_limit,
            )
            if not chunk_ok or chunk.is_empty():
                continue
            collected.append(chunk)
            earliest = chunk["timestamp"].min()
            if earliest is not None and earliest < current_earliest:
                current_earliest = earliest
        collected.reverse()
        frames = [frame for frame in collected if not frame.is_empty()]
        if not existing.is_empty():
            frames.append(existing)
        if not frames:
            return existing
        return (
            pl.concat(frames)
            .unique(subset=["timestamp"], keep="last")
            .sort("timestamp")
        )
```

In `get_bars`, after `_retrieve_bars_paged` and the `if not gateway_ok: return empty` check, before cache:

```python
        if self._should_stitch_contracts(symbol, unit, interval) and (
            data.is_empty()
            or data["timestamp"].min() > start_date
        ):
            data = await self._stitch_prior_contract_bars(
                instrument.id,
                data,
                start_date,
                end_date,
                interval,
                unit,
                live,
                partial,
                limit,
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest tests/client/test_get_bars_history.py tests/client/test_market_data.py tests/client/test_contract_calendar.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/project_x_py/client/market_data.py tests/client/test_get_bars_history.py
git commit -m "feat: stitch expired contracts for hourly+ get_bars (#134)"
```

---

### Task 6: Short-range warning, docstring, changelog

**Files:**
- Modify: `src/project_x_py/client/market_data.py` (`get_bars` docstring + warning)
- Modify: `CHANGELOG.md` Unreleased section
- Test: `tests/client/test_get_bars_history.py`

**Interfaces:**
- Consumes: Task 4 paged frame; Task 5 optional stitch; `start_date` / `end_date` already timezone-aware
- Produces: warning log when `min(timestamp) > start_date + one bar duration`; docstring describes paging, stitch, and sub-hour limitation; changelog entries for #133 and #134

- [ ] **Step 1: Write the failing test**

Append to `tests/client/test_get_bars_history.py`:

```python
@pytest.mark.asyncio
async def test_get_bars_warns_when_range_is_short(history_client, caplog):
    import logging

    history_client._make_request = AsyncMock(
        return_value={
            "success": True,
            "bars": [_bar("2026-07-02T22:30:00+00:00")],
        }
    )
    start = datetime.datetime(2026, 3, 31, tzinfo=pytz.UTC)
    end = datetime.datetime(2026, 8, 23, tzinfo=pytz.UTC)
    with caplog.at_level(logging.WARNING, logger="project_x_py.client.market_data"):
        bars = await history_client.get_bars(
            "MNQ",
            interval=15,
            unit=2,
            start_time=start,
            end_time=end,
            partial=False,
        )
    assert not bars.is_empty()
    assert any("shorter than requested" in rec.message for rec in caplog.records)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/client/test_get_bars_history.py::test_get_bars_warns_when_range_is_short -v
```

Expected: FAIL — no warning containing `"shorter than requested"`.

- [ ] **Step 3: Write minimal implementation**

Add helper and call it from `get_bars` after stitch, before cache:

```python
    @staticmethod
    def _bar_duration(unit: int, interval: int) -> datetime.timedelta:
        if unit == 1:
            return datetime.timedelta(seconds=interval)
        if unit == 2:
            return datetime.timedelta(minutes=interval)
        if unit == 3:
            return datetime.timedelta(hours=interval)
        if unit == 4:
            return datetime.timedelta(days=interval)
        if unit == 5:
            return datetime.timedelta(days=7 * interval)
        if unit == 6:
            return datetime.timedelta(days=30 * interval)
        return datetime.timedelta(seconds=interval)

    def _warn_if_short_history(
        self,
        symbol: str,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
        data: pl.DataFrame,
        unit: int,
        interval: int,
        contract_id: str,
    ) -> None:
        if data.is_empty():
            return
        actual_min = data["timestamp"].min()
        actual_max = data["timestamp"].max()
        if actual_min is None or actual_min <= start_date + self._bar_duration(
            unit, interval
        ):
            return
        logger.warning(
            "Historical bars for %s shorter than requested: requested [%s, %s] "
            "actual [%s, %s] contract=%s",
            symbol,
            start_date,
            end_date,
            actual_min,
            actual_max,
            contract_id,
        )
```

Call after stitch / before `cache_market_data`:

```python
        self._warn_if_short_history(
            symbol, start_date, end_date, data, unit, interval, instrument.id
        )
```

Update the `get_bars` docstring Args/behavior to include:

```
Product-root symbols (e.g. ``MNQ``) on hourly or coarser timeframes
(``unit >= 3``, or ``unit == 2`` and ``interval >= 60``) fetch prior
contract months via ``/Contract/searchById`` and concatenate them.
Sub-hour bars are the active contract only (Gateway does not keep
intraday history on expired months). Windows larger than 20,000 bars
are paged. If the returned timestamps start after the requested
``start_time``, a warning is logged.
```

In `CHANGELOG.md`, replace the Unreleased `None.` with:

```markdown
## [Unreleased]

### Fixed

- `StatisticsAggregator` no longer registers `TradingSuite` as a stats
  component of itself. `suite.get_stats()` was re-entering
  `_collect_component_stats` until the event loop froze and leaked
  thousands of pending tasks. Collection timeouts now cancel child
  tasks and keep finished results (#133).
- `get_bars()` pages `/History/retrieveBars` at the 20,000-bar Gateway
  cap. For product-root symbols on hourly and coarser timeframes it
  stitches expired months via `Contract/searchById`. Sub-hour history
  remains the active contract only; a warning is logged when the
  returned window is shorter than requested (#134).
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest tests/client/test_get_bars_history.py tests/client/test_market_data.py tests/statistics/test_statistics_module.py::TestStatisticsAggregator tests/client/test_contract_calendar.py -v
uv run ruff format src/project_x_py/statistics/aggregator.py src/project_x_py/client/market_data.py src/project_x_py/client/contract_calendar.py tests/statistics/test_statistics_module.py tests/client/test_contract_calendar.py tests/client/test_get_bars_history.py
uv run ruff check src/project_x_py/statistics/aggregator.py src/project_x_py/client/market_data.py src/project_x_py/client/contract_calendar.py tests/statistics/test_statistics_module.py tests/client/test_contract_calendar.py tests/client/test_get_bars_history.py --fix
uv run mypy src/project_x_py/statistics/aggregator.py src/project_x_py/client/market_data.py src/project_x_py/client/contract_calendar.py
```

Expected: tests PASS; ruff/mypy clean.

- [ ] **Step 5: Commit**

```bash
git add src/project_x_py/client/market_data.py tests/client/test_get_bars_history.py CHANGELOG.md
git commit -m "fix: warn when get_bars window is truncated (#134)"
```

---

## Spec coverage

| Spec requirement | Task |
|---|---|
| Skip `"trading_suite"` in `_collect_all_components` and `_collect_component_stats` | 1 |
| Keep `aggregator.trading_suite = suite` for collector/metadata | 1 (no change to `__setattr__`) |
| Cancel children on timeout; keep finished results | 2 |
| `contract_calendar.parse_contract_id` / `iter_prior_contract_ids` | 3 |
| Page retrieveBars at 20k, max 20 pages | 4 |
| First-call Gateway failure does not stitch | 4 (`gateway_ok`) + 5 (only stitch after `gateway_ok`) |
| Stitch hourly+ product roots only; never stitch `CON.` or sub-hour | 5 |
| 4 consecutive `searchById` misses / 16 attempts | 5 |
| Overlap: unique timestamp keep last (later month wins) | 5 |
| Warn when `min(timestamp) > start + one bar` | 6 |
| Docstring + CHANGELOG | 6 |
| No new public parameters; `get_instrument` unchanged | all |

## Placeholder scan

No TBD / TODO / “implement later” / “similar to Task N” without code.

## Type consistency

- `parse_contract_id(...) -> tuple[str, str, int] | None`
- `iter_prior_contract_ids(contract_id: str, max_count: int = 24) -> Iterator[str]`
- `_retrieve_bars_paged(...) -> tuple[pl.DataFrame, bool]`
- `_should_stitch_contracts(symbol: str, unit: int, interval: int) -> bool`
- `_stitch_prior_contract_bars(...) -> pl.DataFrame`
- `_bar_duration(unit: int, interval: int) -> datetime.timedelta`
