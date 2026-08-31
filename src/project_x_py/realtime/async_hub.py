"""Async SignalR hub adapter backed by pysignalr.

Keeps a signalrcore-compatible builder/connection surface so existing tests
and call sites can keep using HubConnectionBuilder, on/on_open/start/stop/send.

Incoming WebSocket frames are capped at ``HUB_RECEIVE_MAX_SIZE`` bytes
(pysignalr / websockets default: 1 MiB). This is a frame-size limit, not a
message-count buffer. A 10 KB cap close-loops TopstepX DOM snapshots with
WS 1009 (message too big).
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable
from contextlib import suppress
from typing import Any
from urllib.parse import parse_qs, urlparse

from project_x_py.utils import ProjectXLogger

logger = ProjectXLogger.get_logger(__name__)

# pysignalr.transport.websocket.DEFAULT_MAX_SIZE — incoming frame size in bytes.
HUB_RECEIVE_MAX_SIZE = 2**20


async def invoke_maybe(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Call a sync or async function and await the result when needed."""
    result = fn(*args, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


class AsyncHubConnection:
    """Thin wrapper around pysignalr.SignalRClient with the legacy hub API."""

    def __init__(self, url: str, hub_name: str | None = None) -> None:
        self.url = url
        self.hub_name = hub_name or "hub"
        self._client: Any | None = None
        self._run_task: asyncio.Task[None] | None = None
        self._open_handlers: list[Callable[[], Any]] = []
        self._close_handlers: list[Callable[[], Any]] = []
        self._error_handlers: list[Callable[[Any], Any]] = []
        self._event_handlers: dict[str, list[Callable[..., Any]]] = {}
        self._send_lock = asyncio.Lock()

    def _token_factory(self) -> str:
        parsed = urlparse(self.url)
        token = parse_qs(parsed.query).get("access_token", [""])[0]
        return token

    def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client

        from pysignalr.client import SignalRClient

        self._client = SignalRClient(
            url=self.url,
            access_token_factory=self._token_factory,
            ping_interval=10,
            retry_sleep=1.0,
            retry_multiplier=1.5,
            retry_count=10,
            max_size=HUB_RECEIVE_MAX_SIZE,
        )

        async def _on_open() -> None:
            for handler in self._open_handlers:
                await invoke_maybe(handler)

        async def _on_close() -> None:
            for handler in self._close_handlers:
                await invoke_maybe(handler)

        async def _on_error(message: Any) -> None:
            for handler in self._error_handlers:
                await invoke_maybe(handler, message)

        self._client.on_open(_on_open)
        self._client.on_close(_on_close)
        self._client.on_error(_on_error)

        for event, handlers in self._event_handlers.items():
            for handler in handlers:
                self._bind_event(event, handler)

        return self._client

    def _bind_event(self, event: str, handler: Callable[..., Any]) -> None:
        client = self._ensure_client()

        async def _wrapped(arguments: Any) -> None:
            if isinstance(arguments, list | tuple):
                result = handler(*arguments)
            else:
                result = handler(arguments)
            if inspect.isawaitable(result):
                await result

        client.on(event, _wrapped)

    def on(self, event: str, handler: Callable[..., Any]) -> None:
        self._event_handlers.setdefault(event, []).append(handler)
        if self._client is not None:
            self._bind_event(event, handler)

    def on_open(self, handler: Callable[[], Any]) -> None:
        self._open_handlers.append(handler)

    def on_close(self, handler: Callable[[], Any]) -> None:
        self._close_handlers.append(handler)

    def on_error(self, handler: Callable[[Any], Any]) -> None:
        self._error_handlers.append(handler)

    async def start(self) -> None:
        if self._run_task is not None and not self._run_task.done():
            return
        # Drop a finished client so run() is not reused after stop/error.
        self._client = None
        client = self._ensure_client()
        self._run_task = asyncio.create_task(client.run(), name=f"hub:{self.hub_name}")

    async def stop(self) -> None:
        if self._run_task is not None and not self._run_task.done():
            self._run_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._run_task
        self._run_task = None
        self._client = None

    async def send(self, method: str, arguments: list[Any] | None = None) -> None:
        client = self._ensure_client()
        async with self._send_lock:
            await client.send(method, arguments or [])


class HubConnectionBuilder:
    """signalrcore-compatible builder that produces AsyncHubConnection."""

    def __init__(self) -> None:
        self._url = ""
        self._hub_name = "hub"

    def with_url(self, url: str, hub_name: str | None = None) -> HubConnectionBuilder:
        self._url = url
        if hub_name:
            self._hub_name = hub_name
        return self

    def configure_logging(self, *args: Any, **kwargs: Any) -> HubConnectionBuilder:
        return self

    def with_automatic_reconnect(
        self, *args: Any, **kwargs: Any
    ) -> HubConnectionBuilder:
        return self

    def build(self) -> AsyncHubConnection:
        return AsyncHubConnection(self._url, hub_name=self._hub_name)
