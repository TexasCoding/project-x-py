"""Session-aware OHLCV aggregation.

Gateway daily bars (``get_bars(unit=4)``) do not always match the exchange
session used by TopstepX charts. This module rebuilds session candles from
intraday bars using ``SessionConfig`` / ``DEFAULT_SESSIONS``.

Author: TDD Implementation
Date: 2026-09-11
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import polars as pl

from .config import SessionConfig, SessionTimes, SessionType, resolve_session_product
from .filtering import SessionFilterMixin

_DAILY_INTERVALS = {"1d", "1day", "daily", "session"}
_EXCHANGE_TZ = "America/New_York"
_OHLCV = ("timestamp", "open", "high", "low", "close", "volume")


def aggregate_session_bars(
    data: pl.DataFrame,
    product: str,
    interval: str = "1d",
    session_type: SessionType | str | None = None,
    session_config: SessionConfig | None = None,
    include_partial: bool = True,
    now: datetime | None = None,
) -> pl.DataFrame:
    """Aggregate intraday OHLCV bars into exchange-aligned session candles.

    Overnight ETH bars are assigned to the following trading date. The daily
    maintenance break is excluded. Incomplete current sessions are marked with
    ``is_partial`` so callers can drop them.

    Args:
        data: Intraday Polars OHLCV frame with a ``timestamp`` column.
        product: Root symbol, month code, or Gateway contract id.
        interval: Aggregation interval. ``"1d"`` / ``"session"`` build one
            candle per trading session.
        session_type: ``ETH``, ``RTH``, or ``CUSTOM``. Defaults to
            ``session_config.session_type`` (ETH).
        session_config: Optional session calendar override.
        include_partial: When False, drop the in-progress session.
        now: Clock used to decide partial sessions (default: UTC now).

    Returns:
        Polars DataFrame with session candles: ``timestamp`` (session start),
        ``trading_date``, ``session_start``, ``session_end``, OHLCV, and
        ``is_partial``.
    """
    if interval not in _DAILY_INTERVALS:
        raise ValueError(
            f"Unsupported interval {interval!r}; expected one of {sorted(_DAILY_INTERVALS)}"
        )

    config = session_config or SessionConfig()
    resolved_type = _resolve_session_type(session_type, config)
    session_times = _session_times_for(config, product)
    tz_name = _EXCHANGE_TZ if config.use_exchange_timezone else config.market_timezone
    schema = _empty_schema(tz_name)

    if data.is_empty():
        return pl.DataFrame(schema=schema)

    missing = [col for col in _OHLCV if col not in data.columns]
    if missing:
        raise ValueError(f"Missing required column: {', '.join(missing)}")

    prepared = _prepare_timestamps(data, tz_name)
    tagged = _assign_trading_dates(prepared, resolved_type, session_times, product)
    if tagged.is_empty():
        return pl.DataFrame(schema=schema)

    aggregated = (
        tagged.group_by("trading_date", maintain_order=True)
        .agg(
            [
                pl.col("open").first(),
                pl.col("high").max(),
                pl.col("low").min(),
                pl.col("close").last(),
                pl.col("volume").sum(),
            ]
        )
        .sort("trading_date")
    )

    clock = now or datetime.now(UTC)
    starts: list[datetime] = []
    ends: list[datetime] = []
    partials: list[bool] = []
    zone = ZoneInfo(tz_name)
    clock_local = (
        clock.astimezone(zone)
        if clock.tzinfo
        else clock.replace(tzinfo=UTC).astimezone(zone)
    )

    for trading_date in aggregated["trading_date"].to_list():
        start, end = _session_bounds(trading_date, resolved_type, session_times, zone)
        starts.append(start)
        ends.append(end)
        partials.append(clock_local < end)

    result = aggregated.with_columns(
        [
            pl.Series("timestamp", starts),
            pl.Series("session_start", starts),
            pl.Series("session_end", ends),
            pl.Series("is_partial", partials),
        ]
    ).select(
        [
            "timestamp",
            "trading_date",
            "session_start",
            "session_end",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "is_partial",
        ]
    )
    if not include_partial:
        result = result.filter(~pl.col("is_partial"))
    return result


def _empty_schema(tz_name: str) -> dict[str, pl.DataType]:
    dt: pl.DataType = pl.Datetime(time_zone=tz_name)
    return {
        "timestamp": dt,
        "trading_date": pl.Date(),
        "session_start": dt,
        "session_end": dt,
        "open": pl.Float64(),
        "high": pl.Float64(),
        "low": pl.Float64(),
        "close": pl.Float64(),
        "volume": pl.Int64(),
        "is_partial": pl.Boolean(),
    }


def _resolve_session_type(
    session_type: SessionType | str | None, config: SessionConfig
) -> SessionType:
    raw = session_type if session_type is not None else config.session_type
    if isinstance(raw, SessionType):
        return raw
    return SessionType(raw)


def _session_times_for(config: SessionConfig, product: str) -> SessionTimes:
    overrides = config.product_sessions or {}
    if product in overrides:
        return overrides[product]
    resolved = resolve_session_product(product)
    if resolved in overrides:
        return overrides[resolved]
    return config.get_session_times(resolved)


def _prepare_timestamps(data: pl.DataFrame, tz_name: str) -> pl.DataFrame:
    dtype = data["timestamp"].dtype
    time_zone = getattr(dtype, "time_zone", None)
    if time_zone is None:
        data = data.with_columns(pl.col("timestamp").dt.replace_time_zone("UTC"))
    return data.with_columns(
        pl.col("timestamp").dt.convert_time_zone(tz_name).alias("_session_ts")
    )


def _assign_trading_dates(
    data: pl.DataFrame,
    session_type: SessionType,
    session_times: SessionTimes,
    product: str,
) -> pl.DataFrame:
    ts = pl.col("_session_ts")
    t = ts.dt.time()
    d = ts.dt.date()
    weekday = ts.dt.weekday()  # 1=Monday ... 7=Sunday

    in_break = pl.lit(False)
    for break_start, break_end in SessionFilterMixin()._get_maintenance_breaks(
        resolve_session_product(product)
    ):
        if break_start <= break_end:
            in_break = in_break | ((t >= break_start) & (t < break_end))
        else:
            in_break = in_break | ((t >= break_start) | (t < break_end))

    if session_type == SessionType.ETH:
        keep, trading_date = _eth_mask(t, d, weekday, session_times, in_break)
    else:
        # RTH and CUSTOM use the RTH window on weekdays.
        keep = (
            (t >= session_times.rth_start)
            & (t <= session_times.rth_end)
            & (weekday <= 5)
        )
        trading_date = d

    return (
        data.filter(keep)
        .with_columns(trading_date.alias("trading_date"))
        .sort("_session_ts")
        .drop("_session_ts")
    )


def _eth_mask(
    t: pl.Expr,
    d: pl.Expr,
    weekday: pl.Expr,
    session_times: SessionTimes,
    in_break: pl.Expr,
) -> tuple[pl.Expr, pl.Expr]:
    eth_start = session_times.eth_start
    eth_end = session_times.eth_end
    if eth_start is None or eth_end is None:
        keep = (
            (t >= session_times.rth_start)
            & (t <= session_times.rth_end)
            & (weekday <= 5)
            & ~in_break
        )
        return keep, d

    if eth_start > eth_end:
        in_eth = (t >= eth_start) | (t < eth_end)
        trading_date = (
            pl.when(t >= eth_start).then(d + pl.duration(days=1)).otherwise(d)
        )
    else:
        in_eth = (t >= eth_start) & (t < eth_end)
        trading_date = d

    # CME equity-index Globex: Friday close through Sunday open is shut.
    weekend_closed = (
        ((weekday == 5) & (t >= eth_end))
        | (weekday == 6)
        | ((weekday == 7) & (t < eth_start))
    )
    keep = in_eth & ~in_break & ~weekend_closed
    return keep, trading_date


def _session_bounds(
    trading_date: date,
    session_type: SessionType,
    session_times: SessionTimes,
    zone: ZoneInfo,
) -> tuple[datetime, datetime]:
    if (
        session_type == SessionType.ETH
        and session_times.eth_start
        and session_times.eth_end
    ):
        start = datetime.combine(
            trading_date - timedelta(days=1),
            session_times.eth_start,
            tzinfo=zone,
        )
        end = datetime.combine(trading_date, session_times.eth_end, tzinfo=zone)
        return start, end
    rth_end = session_times.rth_end
    start = datetime.combine(trading_date, session_times.rth_start, tzinfo=zone)
    end = datetime.combine(trading_date, rth_end, tzinfo=zone)
    return start, end
