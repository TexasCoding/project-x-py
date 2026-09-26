"""realtime.disconnect joins hub receive tasks before it returns (#98)."""

import asyncio
import contextlib
from unittest.mock import MagicMock

import pytest

from project_x_py.models import ProjectXConfig
from project_x_py.realtime.async_hub import AsyncHubConnection
from project_x_py.realtime.core import ProjectXRealtimeClient

_TIMEOUT = 1.0


@pytest.mark.asyncio
async def test_hub_stop_joins_receive_task_before_returning() -> None:
    """AsyncHubConnection.stop waits until the hub run() task has exited."""
    connection = AsyncHubConnection(
        "https://example.test/hubs/market", hub_name="market"
    )
    entered = asyncio.Event()
    release = asyncio.Event()
    stop_task: asyncio.Task[None] | None = None

    async def receive_loop() -> None:
        entered.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            # Stay cancelled-but-alive until released, so stop() is observably
            # joined to this task instead of racing a one-turn cancellation.
            await release.wait()
            raise

    connection._run_task = asyncio.create_task(receive_loop(), name="hub:market")
    try:
        await asyncio.wait_for(entered.wait(), timeout=_TIMEOUT)

        stop_task = asyncio.create_task(connection.stop())
        await asyncio.sleep(0)
        assert not stop_task.done()

        release.set()
        await asyncio.wait_for(stop_task, timeout=_TIMEOUT)
        assert connection._run_task is None
    finally:
        release.set()
        if stop_task is not None and not stop_task.done():
            stop_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await stop_task
        task = connection._run_task
        if task is not None and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


@pytest.mark.asyncio
async def test_realtime_disconnect_awaits_both_hub_stops() -> None:
    """ProjectXRealtimeClient.disconnect does not return until both hubs stop."""
    config = MagicMock(spec=ProjectXConfig)
    config.user_hub_url = "https://example.test/hubs/user"
    config.market_hub_url = "https://example.test/hubs/market"
    client = ProjectXRealtimeClient(
        jwt_token="test_jwt_token",
        account_id="test_account",
        config=config,
    )

    user_release = asyncio.Event()
    market_release = asyncio.Event()
    user_stopped = asyncio.Event()
    market_stopped = asyncio.Event()

    class _Hub:
        def __init__(self, release: asyncio.Event, stopped: asyncio.Event) -> None:
            self._release = release
            self._stopped = stopped

        async def stop(self) -> None:
            self._stopped.set()
            await self._release.wait()

    client.user_connection = _Hub(user_release, user_stopped)  # type: ignore[assignment]
    client.market_connection = _Hub(market_release, market_stopped)  # type: ignore[assignment]
    client.user_connected = True
    client.market_connected = True

    disconnect_task = asyncio.create_task(client.disconnect())
    try:
        await asyncio.wait_for(user_stopped.wait(), timeout=_TIMEOUT)
        await asyncio.sleep(0)
        # Hubs are stopped one after another; the market hub is still up until
        # the user hub stop returns, and disconnect itself has not returned.
        assert not market_stopped.is_set()
        assert not disconnect_task.done()

        user_release.set()
        await asyncio.wait_for(market_stopped.wait(), timeout=_TIMEOUT)
        await asyncio.sleep(0)
        assert not disconnect_task.done()

        market_release.set()
        await asyncio.wait_for(disconnect_task, timeout=_TIMEOUT)
    finally:
        user_release.set()
        market_release.set()
        if not disconnect_task.done():
            disconnect_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await disconnect_task
    assert client.user_connected is False
    assert client.market_connected is False
