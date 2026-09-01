# Stats re-entry and rolling-contract history

Date: 2026-08-31
Status: approved
Issues: [#133](https://github.com/TexasCoding/project-x-py/issues/133),
[#134](https://github.com/TexasCoding/project-x-py/issues/134)
Branch: `fix/133-134-stats-reentry-and-contract-history`

## Problem

Two independent Gateway-SDK bugs. Same release branch; no shared code.

### #133 — `StatisticsAggregator` re-enters `TradingSuite.get_stats()`

`TradingSuite.__init__` assigns `self._stats_aggregator.trading_suite = self`.
`StatisticsAggregator.__setattr__` queues that as pending component
`"trading_suite"`. On `await suite.get_stats()`:

1. `aggregate_stats()` → `get_suite_stats()` → cache miss → `_collect_all_components()`
2. `ComponentCollector.collect()` is preferred, but on timeout or failure the
   fallback iterates `_components`, including the suite itself
3. `_collect_component_stats("trading_suite", suite)` calls `suite.get_stats()`
   before the cache is populated
4. Unbounded `asyncio.create_task(_collect_component_stats(...))` tree

On timeout, `_collect_all_components` returns `{}` without cancelling children,
so tasks leak. On Python 3.13, a cyclic gather plus `asyncio.wait_for` can
`RecursionError` inside `Timeout._on_timeout` (`_GatheringFuture.cancel`).

Live Practice (MNQ+MES, 1s watchdog) froze `status.json` and dumped tens of
thousands of `Task was destroyed but it is pending!` lines for
`_collect_component_stats`.

### #134 — `get_bars` silently truncates windows across rolls

`get_bars("MNQ", start_time=..., end_time=...)` always resolves the **active**
contract via `get_instrument` and issues one `/History/retrieveBars` call.
There is no continuous-contract id in Gateway (`CON.F.US.MNQ` and `F.US.MNQ`
return no bars).

Live probe (2026-08-31, Practice, MNQ):

| Timeframe | Current month (`CON.F.US.MNQ.U26`) | Expired months (`M26`, `H26`, …) |
|---|---|---|
| 1s / 1m / 5m / 15m | Current contract only; 5m/15m from 2026-07-02; 1m hits the 20k cap | Empty |
| Hourly / daily | Backfilled on the front month (U26 daily/hourly from 2025-10-15) | Full lifetime via `Contract/searchById` |

`Contract/search` returns only the active month. `Contract/searchById` still
resolves expired months. `/History/retrieveBars` max is 20,000 bars per
request; a 1-minute window is truncated to the most recent 20k with no paging.

Reproducing the issue example (`interval=15`, `unit=2`, 2026-03-31 → 2026-08-23)
returns 3,322 bars starting 2026-07-02, with no warning.

## Decisions

1. Do not collect `TradingSuite` as a stats component of its own aggregator.
   Keep the assignment for `ComponentCollector` setup and suite metadata.
2. On collection timeout, cancel every child task and keep finished results.
3. `get_instrument()` stays “active contract for trading.” History stitching
   is `get_bars()` only.
4. Page `/History/retrieveBars` whenever a response is a full 20,000-bar page
   and the earliest timestamp is still after the requested start.
5. Stitch expired months **only** for hourly and coarser timeframes, and only
   when the symbol is a product root (not a full `CON.` id).
6. Sub-hour requests stay on the active contract. If the returned range is
   shorter than requested, log a warning and return what Gateway has. Do not
   invent 15-minute series for rolled-off months.
7. No new required public parameters. No stitch on/off flag.

## Out of scope

- Changing realtime subscriptions or order placement to a “continuous” id
- Adjusting or back-adjusting prices at the roll
- Volume-based roll dates (overlap uses timestamp unique, later month wins)
- Paginating or stitching inside `get_session_bars` beyond what `get_bars` does
- New Gateway endpoints or a synthetic continuous contract id
- Python 3.13 `Task.cancel` monkeypatch; breaking the cycle is the fix

## #133 design

### Keep

- `aggregator.trading_suite = suite` in `TradingSuite.__init__` so
  `register_component("trading_suite", …)` still builds `ComponentCollector`
  and `_build_suite_stats` can read `suite_id`, `instrument`, `created_at`.

### Change (`src/project_x_py/statistics/aggregator.py`)

1. `_collect_all_components` skips `name == "trading_suite"` when building the
   fallback task list. `_collect_component_stats` also returns `None`
   immediately for that name (defense in depth).
2. Collector timeout / failure may still fall through to the fallback. That
   fallback must not call `suite.get_stats()`. Skipping the name makes the
   fall-through safe.
3. On fallback `TimeoutError`:
   - `task.cancel()` every not-done child
   - `results = await asyncio.gather(*tasks, return_exceptions=True)`
   - include any non-exception, non-`None` results
   - track the timeout error as today
4. Do not return `{}` solely because the wait timed out if some children
   finished.

`TradingSuite.get_stats()` signature and `TradingSuiteStats` shape stay the
same. Callers do not drop `trading_suite` from `_pending_components` anymore.

## #134 design

### New module: `src/project_x_py/client/contract_calendar.py`

Pure helpers, no I/O, no client.

- `CME_MONTH_CODES = "FGHJKMNQUVXZ"` (Jan→Dec).
- `parse_contract_id(contract_id: str) -> tuple[str, str, int] | None`
  - Match `^CON\.[A-Z]\.[A-Z]{2}\.(.+)\.([FGHJKMNQUVXZ])(\d{1,2})$`
  - Return `(root, month_code, two_digit_year)` e.g. `("MNQ", "U", 26)`.
  - Root may contain digits (`M6E`, `BP6`, `GMET`).
- `iter_prior_contract_ids(contract_id: str)` yields previous month ids in
  reverse calendar order: `CON.F.US.MNQ.U26` → `Q26`, `N26`, `M26`, …, wrapping
  year at `F` → previous `Z`. Two-digit year decrements; no 99→00 special case
  (16 attempts never reach it).

### Stitch predicate

Stitch when **all** of:

- `symbol` does not start with `CON.`
- `unit >= 3` **or** (`unit == 2` and `interval >= 60`)
- after paging the active contract, the frame is empty **or**
  `min(timestamp)` is after the requested `start` (timezone-aware, compared in
  the client timezone)

Never stitch: full contract ids, seconds, ticks (`unit == 7`), minutes with
`interval < 60`.

### Paging (`get_bars` / `_retrieve_bars_paged`)

`HISTORY_BAR_LIMIT` stays 20,000.

1. Request `[start, end]` with `limit=min(computed, 20_000)`.
2. Convert/sort as today. If `len == 20_000` and `min(timestamp) > start`,
   request `[start, min(timestamp)]` (inclusive end; duplicates dropped later)
   and concatenate.
3. Repeat until a page returns fewer than 20,000 rows, `min(timestamp) <= start`,
   the page is empty, or 20 pages have been fetched (400,000-bar cap).
4. Pass through existing payload fields: `live`, `unit`, `unitNumber`,
   `includePartialBar`.

### Stitch (`_stitch_prior_contract_bars`)

Walk `iter_prior_contract_ids(active.id)`:

- `POST /Contract/searchById` with `{contractId}`. A missing/unsuccessful
  contract counts as a miss. Stop after **4 consecutive misses** or **16
  attempts**, or once `min(timestamp) <= start`.
- Four consecutive misses covers quarterly products (2 empty months between
  H/M/U/Z) and gold-style calendars (up to 3 empty months).
- On a hit, page `/History/retrieveBars` for that id over `[start, gap_end]`
  where `gap_end` is the current earliest timestamp, or the original `end` if
  the active series was empty. Same `live`, `unit`, `unitNumber`, and
  `includePartialBar` as the original call.
- Skip months whose retrieve fails; do not fail the whole call.
- Collect frames oldest-month first, then the active/newest frame last.
- `pl.concat`, sort by `timestamp`, `unique(subset=["timestamp"], keep="last")`
  so the nearer front month wins overlap.

### Short-range warning

After paging + optional stitch, if the frame is non-empty and
`min(timestamp) > start + one bar duration`, log a warning that includes
symbol, requested `[start, end]`, actual `[min, max]`, and contract id. Return
the data. Empty remains empty (no extra warning beyond existing empty path).

One bar duration: `interval` of `unit` (1=seconds, 2=minutes, 3=hours, 4=days,
5=weeks as 7 days, 6=months as 30 days, 7=ticks as `interval` seconds).

### Cache

The existing cache key (symbol + range + interval + unit + partial + live)
stores the **final** combined frame. No extra stitch flag in the key.

### Public API

`get_bars(...)` signature unchanged. Docstring states:

- Product-root symbols on hourly+ stitch prior months via `searchById`.
- Sub-hour data is the active contract only (Gateway limitation).
- Windows larger than 20,000 bars are paged.
- A shorter-than-requested range logs a warning.

## Error handling

| Failure | Behavior |
|---|---|
| Active-contract history error | Existing `get_bars` behavior (empty frame / wrapped error) |
| Prior-month `searchById` miss or HTTP error | Count as miss; continue |
| Prior-month `retrieveBars` error | Skip that month; continue |
| Partial stitch | Success; warning if still short |
| Sub-hour hole (e.g. 15m before 2026-07-02) | Warning; return active-contract data |
| Stats component timeout | Cancel children; return finished stats; no task leak |
| Stats component exception | Track error; omit that component |

## Testing

Async pytest, `AsyncMock` / `aioresponses`. No live Gateway in CI.

### #133 — `tests/statistics/`

- Assigning `aggregator.trading_suite = suite` (suite with async `get_stats`
  that calls `aggregate_stats`) must complete once and must not recurse.
- `_collect_all_components` must not invoke `get_stats` on a component named
  `trading_suite`.
- Slow components plus a short `component_timeout` must cancel pending tasks
  (`task.done()` after the call) and must not leave `_collect_component_stats`
  tasks pending.
- Finished components on a timed-out gather still appear in the result dict.

### #134 — `tests/client/` (calendar unit + `get_bars` mocks)

- `parse_contract_id("CON.F.US.MNQ.U26") == ("MNQ", "U", 26)`
- `iter_prior_contract_ids` from U26 yields Q26 then N26 then M26; year wraps
  F26 → Z25.
- Invalid / non-contract strings return `None` / empty iterator.
- `get_bars("CON.F.US.MNQ.U26", unit=3, …)` does **not** call `searchById`.
- `get_bars("MNQ", interval=15, unit=2, …)` does **not** call `searchById`.
- `get_bars("MNQ", interval=1, unit=3, …)` with active bars starting after
  `start` calls `searchById` for prior months and concatenates.
- Overlapping timestamps: later month’s bar is kept.
- A 20,000-row first page triggers a second retrieve with an earlier `endTime`.
- Short series emits a log warning.

## Docs

- `get_bars` docstring in `src/project_x_py/client/market_data.py`
- `CHANGELOG.md` Unreleased: Fixed #133 and #134 (paging + hourly/daily stitch;
  sub-hour limitation documented)

## Implementation order

1. #133 tests then aggregator fix (stops live-loop freeze; no API dependency).
2. `contract_calendar` tests then module.
3. `get_bars` paging tests then implementation.
4. Stitch + warning tests then implementation.
5. Docstring + changelog.
