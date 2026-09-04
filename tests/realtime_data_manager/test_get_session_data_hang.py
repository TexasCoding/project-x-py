"""Regression tests for get_session_data hang (#137)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from project_x_py.realtime_data_manager.data_access import DataAccessMixin
from project_x_py.sessions import SessionFilterMixin, SessionType
from project_x_py.utils.lock_optimization import AsyncRWLock


def _rth_bars(n: int = 5) -> pl.DataFrame:
    """Build a small RTH MNQ frame in UTC (14:30 UTC == 9:30 ET in January)."""
    ny = ZoneInfo("America/New_York")
    start = datetime(2026, 1, 5, 9, 30, tzinfo=ny)
    rows = [start + timedelta(minutes=i) for i in range(n)]
    return pl.DataFrame(
        {
            "timestamp": [t.astimezone(ZoneInfo("UTC")) for t in rows],
            "open": [21000.0] * n,
            "high": [21001.0] * n,
            "low": [20999.0] * n,
            "close": [21000.25 + i for i in range(n)],
            "volume": [100] * n,
        }
    )


class SessionDataManager(DataAccessMixin):
    """Minimal DataAccessMixin host with a real AsyncRWLock."""

    def __init__(self) -> None:
        self.data: dict[str, pl.DataFrame] = {}
        self.current_tick_data: list[dict[str, object]] = []
        self.tick_size = 0.25
        self.timezone = ZoneInfo("UTC")
        self.instrument = "MNQ"
        self.session_filter = SessionFilterMixin()
        self.session_config = None
        self.data_rw_lock = AsyncRWLock("test-session-data")
        self.data_lock = self.data_rw_lock
        self.data_lock_timeout = 0.2
        self.session_data_timeout = 0.2
        self._last_data_snapshot: dict[str, pl.DataFrame] = {}
        self._last_session_snapshot: dict[tuple[str, str], pl.DataFrame] = {}


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_session_data_times_out_when_write_lock_held() -> None:
    manager = SessionDataManager()
    manager.data["1min"] = _rth_bars()

    async def hold_write() -> None:
        async with manager.data_rw_lock.write_lock():
            await asyncio.sleep(5)

    holder = asyncio.create_task(hold_write())
    await asyncio.sleep(0.03)
    start = asyncio.get_running_loop().time()
    result = await manager.get_session_data("1min", SessionType.RTH)
    elapsed = asyncio.get_running_loop().time() - start
    holder.cancel()
    await asyncio.gather(holder, return_exceptions=True)

    assert elapsed < 1.0
    assert result is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_session_data_returns_last_known_on_timeout() -> None:
    manager = SessionDataManager()
    manager.data["1min"] = _rth_bars()
    first = await manager.get_session_data("1min", SessionType.RTH)
    assert first is not None
    assert len(first) == 5

    async def hold_write() -> None:
        async with manager.data_rw_lock.write_lock():
            await asyncio.sleep(5)

    holder = asyncio.create_task(hold_write())
    await asyncio.sleep(0.03)
    stale = await manager.get_session_data("1min", SessionType.RTH)
    holder.cancel()
    await asyncio.gather(holder, return_exceptions=True)

    assert stale is not None
    assert stale["close"].to_list() == first["close"].to_list()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_session_data_does_not_hold_lock_during_filter() -> None:
    manager = SessionDataManager()
    manager.data["1min"] = _rth_bars()
    filter_started = asyncio.Event()
    writer_acquired = asyncio.Event()

    original_filter = manager.session_filter.filter_by_session

    async def slow_filter(*args: object, **kwargs: object) -> pl.DataFrame:
        filter_started.set()
        await writer_acquired.wait()
        return await original_filter(*args, **kwargs)

    manager.session_filter.filter_by_session = slow_filter  # type: ignore[method-assign]

    async def try_write() -> None:
        await filter_started.wait()
        async with manager.data_rw_lock.write_lock(timeout=0.5):
            writer_acquired.set()

    result, _ = await asyncio.wait_for(
        asyncio.gather(
            manager.get_session_data("1min", SessionType.RTH, timeout=2.0),
            try_write(),
        ),
        timeout=3.0,
    )
    assert result is not None
    assert writer_acquired.is_set()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_data_returns_clone_not_live_frame() -> None:
    manager = SessionDataManager()
    manager.data["1min"] = _rth_bars()
    copied = await manager.get_data("1min")
    assert copied is not None
    mutated = copied.with_columns(pl.col("close") * 0)
    assert mutated["close"].to_list() != manager.data["1min"]["close"].to_list()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_session_data_defaults_session_type_from_config() -> None:
    from project_x_py.sessions import SessionConfig

    manager = SessionDataManager()
    manager.session_config = SessionConfig(session_type=SessionType.RTH)
    manager.session_filter = SessionFilterMixin(config=manager.session_config)
    manager.data["1min"] = _rth_bars()
    result = await manager.get_session_data("1min")
    assert result is not None
    assert len(result) == 5


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_session_data_resolves_contract_id_product() -> None:
    manager = SessionDataManager()
    manager.instrument = "CON.F.US.MNQ.H26"
    manager.data["1min"] = _rth_bars()
    result = await manager.get_session_data("1min", SessionType.RTH)
    assert result is not None
    assert len(result) == 5


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_session_data_cancellation_releases_lock() -> None:
    manager = SessionDataManager()
    manager.data["1min"] = _rth_bars()
    manager.session_data_timeout = 5.0
    manager.data_lock_timeout = 5.0

    async def hold_write() -> None:
        async with manager.data_rw_lock.write_lock():
            await asyncio.sleep(5)

    holder = asyncio.create_task(hold_write())
    await asyncio.sleep(0.03)
    reader = asyncio.create_task(manager.get_session_data("1min", SessionType.RTH))
    await asyncio.sleep(0.03)
    reader.cancel()
    with pytest.raises(asyncio.CancelledError):
        await reader
    holder.cancel()
    await asyncio.gather(holder, return_exceptions=True)
    assert manager.data_rw_lock.reader_count == 0
    async with manager.data_rw_lock.write_lock(timeout=0.2):
        pass
