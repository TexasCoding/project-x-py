"""Disconnect-time bounded statistics must not sweep shared counters (#98).

The in-session CleanupScheduler path stays. Teardown only stops that
scheduler; it does not call the counter sweep.
"""

import asyncio
import contextlib
from datetime import datetime
from unittest.mock import AsyncMock, Mock

import polars as pl
import pytest

from project_x_py.client.base import ProjectXBase
from project_x_py.realtime import ProjectXRealtimeClient
from project_x_py.realtime_data_manager.core import RealtimeDataManager
from project_x_py.statistics.bounded_statistics import BoundedStatisticsMixin

_TIMEOUT = 2.0


async def _cancel_scheduler(manager: RealtimeDataManager) -> None:
    """Cancel a scheduler left running if teardown itself does not return."""
    scheduler = getattr(manager, "_cleanup_scheduler", None)
    if scheduler is None:
        return
    for task in (
        getattr(scheduler, "_cleanup_task", None),
        getattr(scheduler, "_memory_task", None),
    ):
        if task is not None and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


def _manager() -> RealtimeDataManager:
    project_x = Mock(spec=ProjectXBase)
    realtime_client = Mock(spec=ProjectXRealtimeClient)
    return RealtimeDataManager("MNQ", project_x, realtime_client)


@pytest.mark.asyncio
async def test_cleanup_does_not_sweep_bounded_statistics_counters() -> None:
    """Teardown must not call the counter sweep that reads shared stats."""
    manager = _manager()
    await manager.increment_bounded("ticks", 1.0)
    await manager._ensure_cleanup_scheduler_started()
    assert manager._cleanup_scheduler._running is True

    manager.data["1min"] = pl.DataFrame(
        {
            "timestamp": [datetime.now()],
            "open": [1.0],
            "high": [1.0],
            "low": [1.0],
            "close": [1.0],
            "volume": [1],
        }
    )
    manager.current_tick_data.append({"price": 1.0, "volume": 1})

    sweep = AsyncMock()
    manager._cleanup_counters = sweep  # type: ignore[method-assign]

    try:
        await asyncio.wait_for(manager.cleanup(), timeout=_TIMEOUT)
    finally:
        await _cancel_scheduler(manager)

    sweep.assert_not_called()
    assert manager._cleanup_scheduler._running is False
    assert len(manager.data) == 0
    assert len(manager.current_tick_data) == 0
    assert manager._initialized is False


@pytest.mark.asyncio
async def test_cleanup_scheduler_stop_error_does_not_block_teardown() -> None:
    """A scheduler stop failure is logged and cached bars are still dropped."""
    manager = _manager()
    manager.data["1min"] = pl.DataFrame({"close": [1.0]})
    manager._cleanup_scheduler.stop = AsyncMock(  # type: ignore[method-assign]
        side_effect=RuntimeError("stop failed")
    )

    await asyncio.wait_for(manager.cleanup(), timeout=_TIMEOUT)

    assert len(manager.data) == 0
    assert manager._initialized is False


def test_in_session_cleanup_scheduler_still_registers_counter_sweep() -> None:
    """Periodic cleanup keeps the counter sweep; only teardown skips it."""
    manager = _manager()
    registered = dict(manager._cleanup_scheduler._cleanup_functions)

    assert registered["bounded_counters"].__func__ is (
        BoundedStatisticsMixin._cleanup_counters
    )
    assert registered["timing_buffers"].__func__ is (
        BoundedStatisticsMixin._cleanup_timing_buffers
    )
    assert registered["bounded_gauges"].__func__ is (
        BoundedStatisticsMixin._cleanup_gauges
    )
