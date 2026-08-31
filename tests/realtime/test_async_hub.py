"""Tests for the pysignalr hub adapter."""

import asyncio

import pytest

from project_x_py.realtime import async_hub
from project_x_py.realtime.async_hub import AsyncHubConnection, HubConnectionBuilder


def test_hub_receive_max_size_is_websocket_frame_bytes() -> None:
    """Issue #128: max_size is incoming WebSocket frame bytes, not a message count.

    TopstepX MNQ/MES DOM snapshots exceed 10 KB; a 10_000 cap close-loops with
    WS 1009 (message too big). Use pysignalr's 1 MiB default.
    """
    from pysignalr.transport.websocket import DEFAULT_MAX_SIZE

    assert hasattr(async_hub, "HUB_RECEIVE_MAX_SIZE")
    assert async_hub.HUB_RECEIVE_MAX_SIZE == DEFAULT_MAX_SIZE
    assert async_hub.HUB_RECEIVE_MAX_SIZE >= 2**20
    assert async_hub.HUB_RECEIVE_MAX_SIZE > 10_000

    connection = (
        HubConnectionBuilder().with_url("https://example.test/hubs/user").build()
    )
    captured: dict = {}

    class FakeSignalRClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def on_open(self, *args, **kwargs):
            return None

        def on_close(self, *args, **kwargs):
            return None

        def on_error(self, *args, **kwargs):
            return None

        def on(self, *args, **kwargs):
            return None

    import pysignalr.client as pysignalr_client

    original = pysignalr_client.SignalRClient
    pysignalr_client.SignalRClient = FakeSignalRClient  # type: ignore[misc]
    try:
        connection._ensure_client()
    finally:
        pysignalr_client.SignalRClient = original  # type: ignore[misc]

    assert captured.get("max_size") == DEFAULT_MAX_SIZE


def test_hub_task_name_does_not_include_access_token() -> None:
    connection = (
        HubConnectionBuilder()
        .with_url(
            "https://rtc.topstepx.com/hubs/user?access_token=super-secret",
            hub_name="user",
        )
        .build()
    )
    assert connection.hub_name == "user"
    assert "access_token" not in f"hub:{connection.hub_name}"
    assert connection.url.startswith("https://rtc.topstepx.com/hubs/user")


@pytest.mark.asyncio
async def test_send_serializes_concurrent_calls() -> None:
    """Issue #126: overlapping send() on one hub must not race pysignalr."""
    connection = AsyncHubConnection(
        "https://example.test/hubs/market", hub_name="market"
    )
    in_flight = 0
    max_in_flight = 0
    started = asyncio.Event()
    release = asyncio.Event()

    class FakeClient:
        async def send(self, method: str, arguments: list) -> None:
            nonlocal in_flight, max_in_flight
            in_flight += 1
            max_in_flight = max(max_in_flight, in_flight)
            started.set()
            await release.wait()
            in_flight -= 1

    connection._client = FakeClient()

    first = asyncio.create_task(connection.send("SubscribeContractQuotes", ["MNQ"]))
    await started.wait()
    second = asyncio.create_task(connection.send("SubscribeContractQuotes", ["MES"]))
    # Give the second send a chance to overlap if there is no lock.
    await asyncio.sleep(0.02)
    assert max_in_flight == 1
    release.set()
    await asyncio.gather(first, second)
    assert max_in_flight == 1


def _install_fake_signalr_client(connection: AsyncHubConnection) -> list[object]:
    """Patch pysignalr so start()/stop() can run without a network."""
    clients: list[object] = []

    class FakeSignalRClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.started = asyncio.Event()
            clients.append(self)

        def on_open(self, *args, **kwargs):
            return None

        def on_close(self, *args, **kwargs):
            return None

        def on_error(self, *args, **kwargs):
            return None

        def on(self, *args, **kwargs):
            return None

        async def run(self) -> None:
            self.started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                raise

    import pysignalr.client as pysignalr_client

    original = pysignalr_client.SignalRClient
    pysignalr_client.SignalRClient = FakeSignalRClient  # type: ignore[misc]
    connection._signalr_original = original  # type: ignore[attr-defined]
    return clients


@pytest.mark.asyncio
async def test_stop_resets_client_so_start_can_reconnect() -> None:
    """Issue #129: reusing a pysignalr client after stop raises
    'Cannot connect while not disconnected'. Drop the client on stop.
    """
    connection = AsyncHubConnection(
        "https://example.test/hubs/market", hub_name="market"
    )
    import pysignalr.client as pysignalr_client

    original = pysignalr_client.SignalRClient
    clients = _install_fake_signalr_client(connection)
    try:
        await connection.start()
        await clients[0].started.wait()  # type: ignore[attr-defined]
        first_client = connection._client
        assert first_client is not None

        await connection.stop()
        assert connection._client is None
        assert connection._run_task is None

        await connection.start()
        assert connection._client is not None
        assert connection._client is not first_client
        await connection.stop()
    finally:
        pysignalr_client.SignalRClient = original  # type: ignore[misc]
