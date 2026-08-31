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
