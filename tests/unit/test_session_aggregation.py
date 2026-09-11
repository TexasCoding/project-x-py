"""Tests for session-aware OHLCV aggregation (#140)."""

from datetime import datetime
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from project_x_py.sessions import (
    SessionConfig,
    SessionTimes,
    SessionType,
    aggregate_session_bars,
)

NY = ZoneInfo("America/New_York")
CHI = ZoneInfo("America/Chicago")


def _ohlcv(
    timestamps: list[datetime],
    opens: list[float] | None = None,
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    closes: list[float] | None = None,
    volumes: list[int] | None = None,
) -> pl.DataFrame:
    n = len(timestamps)
    return pl.DataFrame(
        {
            "timestamp": timestamps,
            "open": opens or [float(i) for i in range(n)],
            "high": highs or [float(i) + 1.0 for i in range(n)],
            "low": lows or [float(i) - 1.0 for i in range(n)],
            "close": closes or [float(i) + 0.5 for i in range(n)],
            "volume": volumes or [100 * (i + 1) for i in range(n)],
        }
    )


class TestAggregateSessionBars:
    def test_overnight_bars_belong_to_next_trading_date(self) -> None:
        # Sunday 18:00 ET through Monday 16:00 ET is trading date Monday 2024-01-15.
        bars = _ohlcv(
            [
                datetime(2024, 1, 14, 18, 0, tzinfo=NY),  # session open
                datetime(2024, 1, 14, 22, 0, tzinfo=NY),  # overnight
                datetime(2024, 1, 15, 9, 30, tzinfo=NY),
                datetime(2024, 1, 15, 16, 0, tzinfo=NY),  # last hour before 17:00 ET
            ],
            opens=[29610.25, 29620.0, 29700.0, 29500.0],
            highs=[29650.0, 29680.0, 29764.75, 29550.0],
            lows=[29600.0, 29610.0, 29650.0, 29424.50],
            closes=[29620.0, 29670.0, 29580.0, 29525.50],
            volumes=[10, 20, 30, 40],
        )

        result = aggregate_session_bars(bars, product="MNQ", interval="1d")

        assert result.height == 1
        assert result["trading_date"][0] == datetime(2024, 1, 15).date()
        assert result["open"][0] == pytest.approx(29610.25)
        assert result["high"][0] == pytest.approx(29764.75)
        assert result["low"][0] == pytest.approx(29424.50)
        assert result["close"][0] == pytest.approx(29525.50)
        assert result["volume"][0] == 100
        start = result["timestamp"][0]
        assert start.hour == 18
        assert start.day == 14

    def test_maintenance_break_bars_are_excluded(self) -> None:
        bars = _ohlcv(
            [
                datetime(2024, 1, 15, 16, 0, tzinfo=NY),
                datetime(2024, 1, 15, 17, 0, tzinfo=NY),  # maintenance
                datetime(2024, 1, 15, 17, 30, tzinfo=NY),  # maintenance
            ],
            opens=[100.0, 999.0, 998.0],
            highs=[101.0, 1000.0, 999.0],
            lows=[99.0, 1.0, 2.0],
            closes=[100.5, 500.0, 400.0],
            volumes=[10, 9999, 8888],
        )

        result = aggregate_session_bars(bars, product="MNQ", interval="1d")

        assert result.height == 1
        assert result["open"][0] == pytest.approx(100.0)
        assert result["high"][0] == pytest.approx(101.0)
        assert result["low"][0] == pytest.approx(99.0)
        assert result["close"][0] == pytest.approx(100.5)
        assert result["volume"][0] == 10

    def test_chicago_timestamps_match_cme_equity_session(self) -> None:
        # 17:00 CT previous day through 16:00 CT is the CME equity-index session.
        bars = _ohlcv(
            [
                datetime(2026, 9, 7, 17, 0, tzinfo=CHI),
                datetime(2026, 9, 8, 9, 0, tzinfo=CHI),
                datetime(2026, 9, 8, 15, 0, tzinfo=CHI),
            ],
            opens=[29610.25, 29700.0, 29540.0],
            highs=[29620.0, 29764.75, 29560.0],
            lows=[29600.0, 29680.0, 29424.50],
            closes=[29615.0, 29580.0, 29525.50],
            volumes=[1, 2, 3],
        )

        result = aggregate_session_bars(
            bars,
            product="CON.F.US.MNQ.U26",
            interval="1d",
            session_type=SessionType.ETH,
        )

        assert result.height == 1
        assert result["trading_date"][0] == datetime(2026, 9, 8).date()
        chicago_start = result["timestamp"][0].astimezone(CHI)
        assert chicago_start.hour == 17
        assert chicago_start.day == 7
        assert result["open"][0] == pytest.approx(29610.25)
        assert result["close"][0] == pytest.approx(29525.50)

    def test_rth_session_uses_pit_hours_only(self) -> None:
        bars = _ohlcv(
            [
                datetime(2024, 1, 15, 8, 0, tzinfo=NY),  # ETH, exclude
                datetime(2024, 1, 15, 9, 30, tzinfo=NY),
                datetime(2024, 1, 15, 15, 59, tzinfo=NY),
                datetime(2024, 1, 15, 18, 0, tzinfo=NY),  # ETH, exclude
            ],
            opens=[1.0, 10.0, 12.0, 99.0],
            highs=[2.0, 15.0, 16.0, 100.0],
            lows=[0.5, 9.0, 11.0, 90.0],
            closes=[1.5, 11.0, 13.0, 98.0],
            volumes=[5, 20, 30, 50],
        )

        result = aggregate_session_bars(
            bars, product="MNQ", interval="1d", session_type=SessionType.RTH
        )

        assert result.height == 1
        assert result["open"][0] == pytest.approx(10.0)
        assert result["high"][0] == pytest.approx(16.0)
        assert result["low"][0] == pytest.approx(9.0)
        assert result["close"][0] == pytest.approx(13.0)
        assert result["volume"][0] == 50

    def test_custom_session_times(self) -> None:
        from datetime import time

        config = SessionConfig(
            session_type=SessionType.CUSTOM,
            product_sessions={
                "MNQ": SessionTimes(
                    rth_start=time(10, 0),
                    rth_end=time(12, 0),
                    eth_start=time(18, 0),
                    eth_end=time(17, 0),
                )
            },
        )
        bars = _ohlcv(
            [
                datetime(2024, 1, 15, 9, 30, tzinfo=NY),
                datetime(2024, 1, 15, 10, 0, tzinfo=NY),
                datetime(2024, 1, 15, 11, 0, tzinfo=NY),
                datetime(2024, 1, 15, 13, 0, tzinfo=NY),
            ]
        )

        result = aggregate_session_bars(
            bars,
            product="MNQ",
            interval="1d",
            session_type=SessionType.CUSTOM,
            session_config=config,
        )

        assert result.height == 1
        assert result["open"][0] == pytest.approx(1.0)
        assert result["close"][0] == pytest.approx(2.5)

    def test_include_partial_false_drops_current_session(self) -> None:
        now = datetime(2024, 1, 15, 12, 0, tzinfo=NY)
        bars = _ohlcv(
            [
                datetime(2024, 1, 14, 18, 0, tzinfo=NY),
                datetime(2024, 1, 15, 10, 0, tzinfo=NY),
            ]
        )

        included = aggregate_session_bars(
            bars, product="MNQ", interval="1d", include_partial=True, now=now
        )
        excluded = aggregate_session_bars(
            bars, product="MNQ", interval="1d", include_partial=False, now=now
        )

        assert included.height == 1
        assert included["is_partial"][0] is True
        assert excluded.height == 0

    def test_completed_historical_session_is_not_partial(self) -> None:
        now = datetime(2024, 1, 16, 12, 0, tzinfo=NY)
        bars = _ohlcv(
            [
                datetime(2024, 1, 14, 18, 0, tzinfo=NY),
                datetime(2024, 1, 15, 16, 0, tzinfo=NY),
            ]
        )

        result = aggregate_session_bars(
            bars, product="MNQ", interval="1d", include_partial=True, now=now
        )

        assert result.height == 1
        assert result["is_partial"][0] is False

    def test_holiday_intraday_session_is_kept(self) -> None:
        # Christmas 2024 is a Wednesday. Gateway daily bars may skip a short
        # holiday session that is present in hourly data.
        bars = _ohlcv(
            [
                datetime(2024, 12, 24, 18, 0, tzinfo=NY),
                datetime(2024, 12, 25, 10, 0, tzinfo=NY),
            ]
        )

        result = aggregate_session_bars(bars, product="MNQ", interval="1d")

        assert result.height == 1
        assert result["trading_date"][0] == datetime(2024, 12, 25).date()

    def test_dst_spring_forward_session_bounds(self) -> None:
        # 2024-03-10 spring forward. Sunday 18:00 EDT starts Monday's session.
        bars = _ohlcv(
            [
                datetime(2024, 3, 10, 18, 0, tzinfo=NY),
                datetime(2024, 3, 11, 10, 0, tzinfo=NY),
            ]
        )

        result = aggregate_session_bars(bars, product="MNQ", interval="1d")

        assert result.height == 1
        assert result["trading_date"][0] == datetime(2024, 3, 11).date()
        start = result["timestamp"][0].astimezone(NY)
        assert start.hour == 18
        assert start.day == 10

    def test_root_and_month_code_products_resolve(self) -> None:
        bars = _ohlcv([datetime(2024, 1, 15, 10, 0, tzinfo=NY)])

        root = aggregate_session_bars(bars, product="MNQ", interval="1d")
        month = aggregate_session_bars(bars, product="MNQH26", interval="1d")

        assert root.height == 1
        assert month.height == 1
        assert root["trading_date"][0] == month["trading_date"][0]

    def test_empty_input_returns_empty_schema(self) -> None:
        empty = pl.DataFrame(
            {
                "timestamp": [],
                "open": [],
                "high": [],
                "low": [],
                "close": [],
                "volume": [],
            }
        ).cast(
            {
                "timestamp": pl.Datetime(time_zone="UTC"),
                "open": pl.Float64,
                "high": pl.Float64,
                "low": pl.Float64,
                "close": pl.Float64,
                "volume": pl.Int64,
            }
        )

        result = aggregate_session_bars(empty, product="MNQ", interval="1d")

        assert result.is_empty()
        for col in (
            "timestamp",
            "trading_date",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "is_partial",
        ):
            assert col in result.columns

    def test_unsupported_interval_raises(self) -> None:
        bars = _ohlcv([datetime(2024, 1, 15, 10, 0, tzinfo=NY)])

        with pytest.raises(ValueError, match="interval"):
            aggregate_session_bars(bars, product="MNQ", interval="5min")

    def test_unsorted_bars_still_use_session_open_and_close(self) -> None:
        bars = _ohlcv(
            [
                datetime(2024, 1, 15, 16, 0, tzinfo=NY),
                datetime(2024, 1, 14, 18, 0, tzinfo=NY),
                datetime(2024, 1, 15, 10, 0, tzinfo=NY),
            ],
            opens=[12.0, 10.0, 11.0],
            highs=[12.5, 10.5, 15.0],
            lows=[11.0, 9.5, 10.0],
            closes=[12.2, 10.2, 14.0],
            volumes=[3, 1, 2],
        )

        result = aggregate_session_bars(bars, product="MNQ", interval="1d")

        assert result.height == 1
        assert result["open"][0] == pytest.approx(10.0)
        assert result["close"][0] == pytest.approx(12.2)
        assert result["high"][0] == pytest.approx(15.0)
        assert result["volume"][0] == 6


class TestGetSessionBarsAggregate:
    @pytest.mark.asyncio
    async def test_get_session_bars_aggregates_hourly_to_daily(self) -> None:
        from unittest.mock import AsyncMock

        from project_x_py import ProjectX

        hourly = _ohlcv(
            [
                datetime(2024, 1, 14, 18, 0, tzinfo=NY),
                datetime(2024, 1, 15, 10, 0, tzinfo=NY),
                datetime(2024, 1, 15, 16, 0, tzinfo=NY),
            ],
            opens=[10.0, 11.0, 12.0],
            highs=[10.5, 15.0, 12.5],
            lows=[9.5, 10.0, 11.0],
            closes=[10.2, 14.0, 12.2],
            volumes=[1, 2, 3],
        )
        client = ProjectX(username="testuser", api_key="test-api-key")
        client.get_bars = AsyncMock(return_value=hourly)

        result = await client.get_session_bars(
            "MNQ",
            timeframe="1hour",
            session_type=SessionType.ETH,
            days=2,
            aggregate="1d",
        )

        assert result.height == 1
        assert result["trading_date"][0] == datetime(2024, 1, 15).date()
        assert result["open"][0] == pytest.approx(10.0)
        assert result["high"][0] == pytest.approx(15.0)
        assert result["close"][0] == pytest.approx(12.2)
        assert client.get_bars.await_args.kwargs.get("interval") == 15
        assert client.get_bars.await_args.kwargs.get("unit") == 2
