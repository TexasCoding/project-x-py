"""Tests for get_bars paging, contract stitch, and short-range warning (#134)."""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock

import polars as pl
import pytest
import pytz

from project_x_py.exceptions import ProjectXConnectionError
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


@pytest.mark.asyncio
async def test_get_bars_stops_when_full_page_does_not_advance(history_client):
    """A full page whose min timestamp equals the requested end must not re-request."""
    end = datetime.datetime(2026, 8, 2, 0, 0, 0, tzinfo=pytz.UTC)
    history_client._make_request = AsyncMock(
        return_value={
            "success": True,
            "bars": [
                _bar("2026-08-02T00:00:00+00:00", 2.0),
                _bar("2026-08-02T00:00:00+00:00", 1.0),
            ],
        }
    )
    start = datetime.datetime(2026, 7, 31, 0, 0, 0, tzinfo=pytz.UTC)
    await history_client.get_bars(
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
    assert len(history_calls) == 1


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
    async def make_request(
        method: str, endpoint: str, data: dict | None = None, **_kwargs
    ):
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
async def test_get_bars_stitches_60_minute_prior_month(history_client):
    async def make_request(
        method: str, endpoint: str, data: dict | None = None, **_kwargs
    ):
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
    await history_client.get_bars(
        "MNQ",
        interval=60,
        unit=2,
        start_time=start,
        end_time=end,
        partial=False,
    )
    endpoints = [call.args[1] for call in history_client._make_request.await_args_list]
    assert "/Contract/searchById" in endpoints


@pytest.mark.asyncio
async def test_get_bars_overlap_keeps_later_month(history_client):
    overlap_ts = "2026-06-18T00:00:00+00:00"

    async def make_request(
        method: str, endpoint: str, data: dict | None = None, **_kwargs
    ):
        if endpoint == "/History/retrieveBars":
            cid = (data or {}).get("contractId")
            if cid == "CON.F.US.MNQ.U26":
                return {
                    "success": True,
                    "bars": [
                        _bar(overlap_ts, 9.0),
                        _bar("2026-07-01T00:00:00+00:00", 10.0),
                    ],
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
    endpoints = [call.args[1] for call in history_client._make_request.await_args_list]
    assert "/Contract/searchById" in endpoints
    overlap = bars.filter(pl.col("close") == 9.0)
    assert len(overlap) == 1
    assert len(bars.filter(pl.col("close") == 1.0)) == 0


@pytest.mark.asyncio
async def test_get_bars_does_not_stitch_ticks(history_client):
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
        interval=1,
        unit=7,
        start_time=start,
        end_time=end,
        partial=False,
    )
    endpoints = [call.args[1] for call in history_client._make_request.await_args_list]
    assert "/Contract/searchById" not in endpoints


@pytest.mark.asyncio
async def test_get_bars_keeps_same_timestamp_ticks(history_client):
    """Paging must not unique-by-timestamp; two ticks can share ``t``."""
    history_client.HISTORY_BAR_LIMIT = 20_000
    same_t = "2026-08-02T00:00:00+00:00"
    history_client._make_request = AsyncMock(
        return_value={
            "success": True,
            "bars": [
                _bar(same_t, 1.0),
                _bar(same_t, 2.0),
            ],
        }
    )
    start = datetime.datetime(2026, 8, 1, tzinfo=pytz.UTC)
    end = datetime.datetime(2026, 8, 3, tzinfo=pytz.UTC)
    bars = await history_client.get_bars(
        "MNQ",
        interval=1,
        unit=7,
        start_time=start,
        end_time=end,
        partial=False,
    )
    assert len(bars) == 2


@pytest.mark.asyncio
async def test_get_bars_failed_active_retrieve_does_not_stitch(history_client):
    history_client._make_request = AsyncMock(
        return_value={"success": False, "errorMessage": "retrieve failed"}
    )
    start = datetime.datetime(2026, 3, 31, tzinfo=pytz.UTC)
    end = datetime.datetime(2026, 8, 1, tzinfo=pytz.UTC)
    bars = await history_client.get_bars(
        "MNQ",
        interval=1,
        unit=3,
        start_time=start,
        end_time=end,
        partial=False,
    )
    endpoints = [call.args[1] for call in history_client._make_request.await_args_list]
    assert "/Contract/searchById" not in endpoints
    assert bars.is_empty()


@pytest.mark.asyncio
async def test_get_bars_stops_after_four_consecutive_search_by_id_misses(
    history_client,
):
    async def make_request(
        method: str, endpoint: str, data: dict | None = None, **_kwargs
    ):
        if endpoint == "/History/retrieveBars":
            return {
                "success": True,
                "bars": [_bar("2026-07-02T00:00:00+00:00", 2.0)],
            }
        if endpoint == "/Contract/searchById":
            return {"success": True, "contract": None}
        raise AssertionError(f"unexpected {endpoint}")

    history_client._make_request = AsyncMock(side_effect=make_request)
    history_client.HISTORY_BAR_LIMIT = 20_000
    start = datetime.datetime(2026, 1, 1, tzinfo=pytz.UTC)
    end = datetime.datetime(2026, 7, 2, tzinfo=pytz.UTC)
    bars = await history_client.get_bars(
        "MNQ",
        interval=1,
        unit=3,
        start_time=start,
        end_time=end,
        partial=False,
    )
    search_calls = [
        call
        for call in history_client._make_request.await_args_list
        if call.args[1] == "/Contract/searchById"
    ]
    assert len(search_calls) == 4
    assert len(bars) == 1


@pytest.mark.asyncio
async def test_get_bars_skips_prior_month_retrieve_error(history_client):
    async def make_request(
        method: str, endpoint: str, data: dict | None = None, **_kwargs
    ):
        if endpoint == "/History/retrieveBars":
            cid = (data or {}).get("contractId")
            if cid == "CON.F.US.MNQ.U26":
                return {
                    "success": True,
                    "bars": [_bar("2026-07-02T00:00:00+00:00", 2.0)],
                }
            if cid == "CON.F.US.MNQ.M26":
                raise ProjectXConnectionError("prior month retrieve failed")
            if cid == "CON.F.US.MNQ.K26":
                return {"success": False, "errorMessage": "no bars"}
            if cid == "CON.F.US.MNQ.H26":
                return {
                    "success": True,
                    "bars": [_bar("2026-03-01T00:00:00+00:00", 1.0)],
                }
            return {"success": True, "bars": []}
        if endpoint == "/Contract/searchById":
            cid = (data or {}).get("contractId")
            if cid in {"CON.F.US.MNQ.M26", "CON.F.US.MNQ.K26", "CON.F.US.MNQ.H26"}:
                return {
                    "success": True,
                    "contract": {
                        "id": cid,
                        "name": "MNQ",
                        "description": "prior",
                        "tickSize": 0.25,
                        "tickValue": 0.5,
                        "activeContract": False,
                    },
                }
            return {"success": True, "contract": None}
        raise AssertionError(f"unexpected {endpoint}")

    history_client._make_request = AsyncMock(side_effect=make_request)
    history_client.HISTORY_BAR_LIMIT = 20_000
    start = datetime.datetime(2026, 3, 1, tzinfo=pytz.UTC)
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
