"""TradingSuite.disconnect stops realtime before freeing per-context state (#98)."""

import asyncio
import contextlib
from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, Mock

import pytest

from project_x_py.order_manager import OrderManager
from project_x_py.orderbook import OrderBook
from project_x_py.position_manager import PositionManager
from project_x_py.realtime import ProjectXRealtimeClient
from project_x_py.realtime_data_manager import RealtimeDataManager
from project_x_py.trading_suite import (
    InstrumentContext,
    TradingSuite,
    TradingSuiteConfig,
)


def _suite_client() -> AsyncMock:
    client = AsyncMock()
    client.account_info = Mock(id=12345)
    return client


def _blocking_disconnect(
    order: list[str], release: asyncio.Event
) -> Callable[[], Awaitable[None]]:
    async def _disconnect() -> None:
        order.append("realtime-start")
        await release.wait()
        order.append("realtime-done")

    return _disconnect


async def _await_disconnect(task: asyncio.Task[None], release: asyncio.Event) -> None:
    """Unblock realtime.disconnect and bound the suite teardown wait."""
    try:
        release.set()
        await asyncio.wait_for(task, timeout=2.0)
    finally:
        if not release.is_set():
            release.set()
        if not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


@pytest.mark.asyncio
async def test_multi_instrument_disconnect_joins_realtime_before_context_cleanup() -> (
    None
):
    """Hub disconnect finishes before any context feed stop or data cleanup."""
    order: list[str] = []
    release = asyncio.Event()
    realtime = AsyncMock(spec=ProjectXRealtimeClient)
    realtime.disconnect = _blocking_disconnect(order, release)

    contexts: dict[str, InstrumentContext] = {}
    for symbol in ("MNQ", "MES"):
        data = AsyncMock(spec=RealtimeDataManager)

        async def stop_feed(symbol: str = symbol) -> None:
            order.append(f"stop-feed:{symbol}")

        async def cleanup(symbol: str = symbol) -> None:
            order.append(f"data-cleanup:{symbol}")

        data.stop_realtime_feed = AsyncMock(side_effect=stop_feed)
        data.cleanup = AsyncMock(side_effect=cleanup)
        orderbook = AsyncMock(spec=OrderBook) if symbol == "MNQ" else None
        if orderbook is not None:

            async def orderbook_cleanup() -> None:
                order.append("orderbook-cleanup")

            orderbook.cleanup = AsyncMock(side_effect=orderbook_cleanup)

        contexts[symbol] = InstrumentContext(
            symbol=symbol,
            instrument_info=Mock(id=f"CON.F.US.{symbol}.U25"),
            data=data,
            orders=Mock(spec=OrderManager),
            positions=Mock(spec=PositionManager),
            event_bus=Mock(),
            orderbook=orderbook,
            risk_manager=None,
        )

    suite = TradingSuite(
        _suite_client(),
        realtime,
        TradingSuiteConfig(instrument="MNQ"),
        contexts,
    )

    task = asyncio.create_task(suite.disconnect())
    try:
        for _ in range(50):
            if "realtime-start" in order:
                break
            await asyncio.sleep(0)

        assert order == ["realtime-start"]
        await _await_disconnect(task, release)
    finally:
        if not release.is_set():
            release.set()
        if not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    done_at = order.index("realtime-done")
    later = order[done_at + 1 :]
    assert "stop-feed:MNQ" in later
    assert "stop-feed:MES" in later
    assert "data-cleanup:MNQ" in later
    assert "data-cleanup:MES" in later
    assert "orderbook-cleanup" in later
    assert suite._connected is False


@pytest.mark.asyncio
async def test_legacy_disconnect_joins_realtime_before_data_cleanup() -> None:
    """Single-instrument disconnect also waits for realtime before data.cleanup."""
    order: list[str] = []
    release = asyncio.Event()
    realtime = AsyncMock(spec=ProjectXRealtimeClient)
    realtime.disconnect = _blocking_disconnect(order, release)

    suite = TradingSuite(
        _suite_client(), realtime, TradingSuiteConfig(instrument="MNQ")
    )
    data = AsyncMock(spec=RealtimeDataManager)

    async def stop_feed() -> None:
        order.append("stop-feed")

    async def cleanup() -> None:
        order.append("data-cleanup")

    data.stop_realtime_feed = AsyncMock(side_effect=stop_feed)
    data.cleanup = AsyncMock(side_effect=cleanup)
    suite._data = data
    orderbook = AsyncMock(spec=OrderBook)

    async def orderbook_cleanup() -> None:
        order.append("orderbook-cleanup")

    orderbook.cleanup = AsyncMock(side_effect=orderbook_cleanup)
    suite._orderbook = orderbook

    task = asyncio.create_task(suite.disconnect())
    try:
        for _ in range(50):
            if "realtime-start" in order:
                break
            await asyncio.sleep(0)

        assert order == ["realtime-start"]
        await _await_disconnect(task, release)
    finally:
        if not release.is_set():
            release.set()
        if not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    assert order.index("realtime-done") < order.index("stop-feed")
    assert order.index("realtime-done") < order.index("data-cleanup")
    assert order.index("realtime-done") < order.index("orderbook-cleanup")
