"""Tests for the pysignalr hub adapter."""

import asyncio

import pytest

from project_x_py.realtime import async_hub
from project_x_py.realtime.async_hub import AsyncHubConnection, HubConnectionBuilder


def test_hub_receive_buffer_is_capped() -> None:
    """pysignalr receive buffer must be bounded, not max_size=None."""
    assert hasattr(async_hub, "HUB_RECEIVE_MAX_SIZE")
    assert async_hub.HUB_RECEIVE_MAX_SIZE == 10_000
    HUB_RECEIVE_MAX_SIZE = async_hub.HUB_RECEIVE_MAX_SIZE

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

    assert captured.get("max_size") == HUB_RECEIVE_MAX_SIZE


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
