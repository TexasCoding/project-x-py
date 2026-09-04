"""
Session filtering functionality for market data.

Provides mixins and utilities to filter market data by trading sessions
(RTH/ETH) with support for different products and custom session times.

Author: TDD Implementation
Date: 2025-08-28
"""

from datetime import UTC, date, datetime, time
from typing import Any

import polars as pl
import pytz

from .config import (
    DEFAULT_SESSIONS,
    SessionConfig,
    SessionTimes,
    SessionType,
    resolve_session_product,
)

# For broader compatibility, we'll catch ValueError and re-raise with our message


class SessionFilterMixin:
    """Mixin class providing session filtering capabilities."""

    # Configurable performance thresholds
    LAZY_EVAL_THRESHOLD = 100_000  # Rows before using lazy evaluation
    CACHE_MAX_SIZE = 1000  # Maximum cache entries
    CACHE_TTL_SECONDS = 3600  # Cache time-to-live in seconds

    # Cached timezone object for performance
    _market_tz = None

    def __init__(
        self,
        config: SessionConfig | None = None,
        lazy_eval_threshold: int | None = None,
        cache_max_size: int | None = None,
        cache_ttl: int | None = None,
    ):
        """Initialize with optional session configuration and performance settings.

        Args:
            config: Session configuration
            lazy_eval_threshold: Number of rows before using lazy evaluation
            cache_max_size: Maximum number of cache entries
            cache_ttl: Cache time-to-live in seconds
        """
        self.config = config or SessionConfig()
        self._session_boundary_cache: dict[str, Any] = {}
        self._cache_timestamps: dict[str, float] = {}

        # Allow overriding performance thresholds
        self.lazy_eval_threshold = lazy_eval_threshold or self.LAZY_EVAL_THRESHOLD
        self.cache_max_size = cache_max_size or self.CACHE_MAX_SIZE
        self.cache_ttl = cache_ttl or self.CACHE_TTL_SECONDS

    def _get_cached_session_boundaries(
        self, data_hash: str, product: str, session_type: str
    ) -> tuple[list[int], list[int]]:
        """Get cached session boundaries for performance optimization with TTL and size limits."""
        import time

        cache_key = f"{data_hash}_{product}_{session_type}"
        current_time = time.time()

        # Check if cached result exists and is still valid
        if cache_key in self._session_boundary_cache:
            # Check TTL (backward compatible - if no timestamp, treat as valid)
            if cache_key in self._cache_timestamps:
                cache_age = current_time - self._cache_timestamps[cache_key]
                if cache_age < self.cache_ttl:
                    cached_result = self._session_boundary_cache[cache_key]
                    if isinstance(cached_result, tuple) and len(cached_result) == 2:
                        return cached_result
                else:
                    # Expired - remove from cache
                    del self._session_boundary_cache[cache_key]
                    del self._cache_timestamps[cache_key]
            else:
                # No timestamp entry (backward compatibility) - treat as valid
                cached_result = self._session_boundary_cache[cache_key]
                if isinstance(cached_result, tuple) and len(cached_result) == 2:
                    # Add timestamp for future TTL checks
                    self._cache_timestamps[cache_key] = current_time
                    return cached_result

        # Enforce cache size limit with LRU eviction
        if (
            len(self._session_boundary_cache) >= self.cache_max_size
            and self._cache_timestamps
        ):
            oldest_key = min(
                self._cache_timestamps.keys(), key=lambda k: self._cache_timestamps[k]
            )
            del self._session_boundary_cache[oldest_key]
            del self._cache_timestamps[oldest_key]

        # Calculate and cache boundaries (simplified implementation)
        boundaries: tuple[list[int], list[int]] = ([], [])
        self._session_boundary_cache[cache_key] = boundaries
        self._cache_timestamps[cache_key] = current_time
        return boundaries

    def _use_lazy_evaluation(self, data: pl.DataFrame) -> pl.LazyFrame:
        """Convert DataFrame to LazyFrame for better memory efficiency."""
        return data.lazy()

    def _optimize_filtering(self, data: pl.DataFrame) -> pl.DataFrame:
        """Apply optimized filtering strategies for large datasets."""
        # Use configurable threshold for lazy evaluation
        if len(data) > self.lazy_eval_threshold:
            lazy_df = self._use_lazy_evaluation(data)
            # Would implement optimized lazy operations here
            return lazy_df.collect()

        # For smaller datasets, use standard filtering
        return data

    async def filter_by_session(
        self,
        data: pl.DataFrame,
        session_type: SessionType,
        product: str,
        custom_session_times: SessionTimes | None = None,
    ) -> pl.DataFrame:
        """Filter DataFrame by session type."""
        # Early return for empty data
        if data.is_empty():
            return data

        # Validate inputs and prepare data
        data = self._validate_and_prepare_data(data)
        session_times = self._get_session_times(product, custom_session_times)

        # Apply session filtering
        return self._apply_session_filter(data, session_type, session_times, product)

    def _validate_and_prepare_data(self, data: pl.DataFrame) -> pl.DataFrame:
        """Validate required columns and prepare data for filtering."""
        self._validate_required_columns(data)
        data = self._validate_and_convert_timestamps(data)
        return self._optimize_filtering(data)

    def _validate_required_columns(self, data: pl.DataFrame) -> None:
        """Validate that all required columns are present."""
        required_columns = ["timestamp", "open", "high", "low", "close", "volume"]
        missing_columns = [col for col in required_columns if col not in data.columns]
        if missing_columns:
            raise ValueError(f"Missing required column: {', '.join(missing_columns)}")

    def _validate_and_convert_timestamps(self, data: pl.DataFrame) -> pl.DataFrame:
        """Validate timestamp column type and convert if necessary."""
        valid_timestamp_types = [
            pl.Datetime,
            pl.Datetime("us"),
            pl.Datetime("us", "UTC"),
        ]

        if data["timestamp"].dtype not in valid_timestamp_types:
            try:
                return data.with_columns(
                    pl.col("timestamp").str.to_datetime().dt.replace_time_zone("UTC")
                )
            except (ValueError, Exception) as e:
                raise ValueError(
                    "Invalid timestamp format - must be datetime or convertible string"
                ) from e

        return data

    def _get_session_times(
        self, product: str, custom_session_times: SessionTimes | None
    ) -> SessionTimes:
        """Get session times for the given product."""
        if custom_session_times:
            return custom_session_times

        resolved = resolve_session_product(product)
        if resolved in DEFAULT_SESSIONS:
            return DEFAULT_SESSIONS[resolved]

        raise ValueError(f"Unknown product: {product}")

    def _apply_session_filter(
        self,
        data: pl.DataFrame,
        session_type: SessionType,
        session_times: SessionTimes,
        product: str,
    ) -> pl.DataFrame:
        """Apply the appropriate session filter based on session type."""
        if session_type == SessionType.ETH:
            return self._filter_eth_hours(data, product)
        elif session_type == SessionType.RTH:
            return self._filter_rth_hours(data, session_times)
        elif session_type == SessionType.CUSTOM:
            return self._filter_custom_session(data, session_times)
        else:
            raise ValueError(f"Unsupported session type: {session_type}")

    def _filter_custom_session(
        self, data: pl.DataFrame, session_times: SessionTimes
    ) -> pl.DataFrame:
        """Filter data for custom session times."""
        return self._filter_rth_hours(data, session_times)

    def _ensure_utc_timestamps(self, data: pl.DataFrame) -> pl.DataFrame:
        """Ensure the timestamp column is timezone-aware UTC for conversions."""
        dtype = data["timestamp"].dtype
        time_zone = getattr(dtype, "time_zone", None)
        if time_zone is None:
            return data.with_columns(pl.col("timestamp").dt.replace_time_zone("UTC"))
        return data

    def _ny_timestamp(self) -> pl.Expr:
        """Per-bar America/New_York timestamp (handles DST without UTC hour math)."""
        return pl.col("timestamp").dt.convert_time_zone("America/New_York")

    def _filter_rth_hours(
        self, data: pl.DataFrame, session_times: SessionTimes
    ) -> pl.DataFrame:
        """Filter data to RTH hours only using each bar's New York local time."""
        if data.is_empty():
            return data

        data = self._ensure_utc_timestamps(data)
        ny_ts = self._ny_timestamp()
        ny_time = ny_ts.dt.time()

        # Inclusive of the configured end time (e.g. 16:00:00 ET)
        return data.filter(
            (ny_time >= session_times.rth_start)
            & (ny_time <= session_times.rth_end)
            & (ny_ts.dt.weekday() <= 5)
        )

    def _filter_eth_hours(self, data: pl.DataFrame, product: str) -> pl.DataFrame:
        """Filter data to ETH hours excluding maintenance breaks."""
        # ETH excludes maintenance breaks which vary by product
        # Most US futures: maintenance break 5:00 PM - 6:00 PM ET daily
        maintenance_breaks = self._get_maintenance_breaks(product)

        if not maintenance_breaks or data.is_empty():
            return data

        data = self._ensure_utc_timestamps(data)
        ny_time = self._ny_timestamp().dt.time()

        keep = pl.lit(True)
        for break_start, break_end in maintenance_breaks:
            if break_start <= break_end:
                in_break = (ny_time >= break_start) & (ny_time < break_end)
            else:
                # Break crosses midnight in local time
                in_break = (ny_time >= break_start) | (ny_time < break_end)
            keep = keep & ~in_break

        return data.filter(keep)

    def _get_maintenance_breaks(self, product: str) -> list[tuple[time, time]]:
        """Get maintenance break times for product."""
        from datetime import time

        # Standard maintenance breaks by product category
        maintenance_schedule = {
            # Equity futures: 5:00 PM - 6:00 PM ET daily
            "equity_futures": [(time(17, 0), time(18, 0))],
            # Energy futures: 5:00 PM - 6:00 PM ET daily
            "energy_futures": [(time(17, 0), time(18, 0))],
            # Metal futures: 5:00 PM - 6:00 PM ET daily
            "metal_futures": [(time(17, 0), time(18, 0))],
            # Treasury futures: 4:00 PM - 6:00 PM ET daily (longer break)
            "treasury_futures": [(time(16, 0), time(18, 0))],
        }

        # Map products to categories
        product_categories = {
            "ES": "equity_futures",
            "MES": "equity_futures",
            "NQ": "equity_futures",
            "MNQ": "equity_futures",
            "YM": "equity_futures",
            "MYM": "equity_futures",
            "M2K": "equity_futures",
            "RTY": "equity_futures",
            "CL": "energy_futures",
            "MCL": "energy_futures",
            "QM": "energy_futures",
            "NG": "energy_futures",
            "HO": "energy_futures",
            "GC": "metal_futures",
            "MGC": "metal_futures",
            "QO": "metal_futures",
            "SI": "metal_futures",
            "SIL": "metal_futures",
            "QI": "metal_futures",
            "HG": "metal_futures",
            "ZN": "treasury_futures",
            "ZB": "treasury_futures",
            "ZF": "treasury_futures",
        }

        category = product_categories.get(
            product, "equity_futures"
        )  # Default to equity
        return maintenance_schedule.get(category, [])

    def is_in_session(
        self, timestamp: datetime | str, session_type: SessionType, product: str
    ) -> bool:
        """Check if timestamp is within specified session for product."""
        # Type safety check - raise error for non-datetime inputs
        if not isinstance(timestamp, datetime):
            raise ValueError(
                f"timestamp must be a datetime object, got {type(timestamp).__name__}"
            )

        session_times = self._get_session_times_for_product(product)
        market_time = self._convert_to_market_time(timestamp)

        # Early checks that apply to all sessions
        if self._is_market_holiday(market_time.date()):
            return False

        if self._is_weekend_outside_eth(timestamp, market_time, session_type):
            return False

        if self._is_maintenance_break(market_time.time(), product):
            return False

        # Apply session-specific logic
        return self._check_session_hours(
            session_type, session_times, market_time.time()
        )

    def _get_session_times_for_product(self, product: str) -> SessionTimes:
        """Get session times for the specified product."""
        resolved = resolve_session_product(product)
        if resolved not in DEFAULT_SESSIONS:
            raise ValueError(f"Unknown product: {product}")
        return DEFAULT_SESSIONS[resolved]

    def _convert_to_market_time(self, timestamp: datetime | str) -> datetime:
        """Convert timestamp to market timezone (ET)."""
        from datetime import datetime as dt_class

        # Use cached timezone object for performance
        if SessionFilterMixin._market_tz is None:
            SessionFilterMixin._market_tz = pytz.timezone("America/New_York")
        market_tz = SessionFilterMixin._market_tz

        # Handle string timestamps
        if isinstance(timestamp, str):
            try:
                # Try parsing ISO format strings like "2024-01-15T15:00:00Z"
                if timestamp.endswith("Z"):
                    timestamp = dt_class.fromisoformat(timestamp.replace("Z", "+00:00"))
                else:
                    timestamp = dt_class.fromisoformat(timestamp)
            except ValueError:
                raise ValueError(
                    f"Unable to parse timestamp string: {timestamp}"
                ) from None

        if timestamp.tzinfo:
            return timestamp.astimezone(market_tz)
        else:
            # Assume UTC if no timezone
            utc_time = timestamp.replace(tzinfo=UTC)
            return utc_time.astimezone(market_tz)

    def _is_market_holiday(self, date: date) -> bool:
        """Check if the given date is a market holiday."""
        # Simplified holiday check - just Christmas and New Year's Eve
        return (date.month == 12 and date.day == 25) or (
            date.month == 12 and date.day == 31
        )

    def _is_weekend_outside_eth(
        self,
        timestamp: datetime | str,
        market_time: datetime,
        session_type: SessionType,
    ) -> bool:
        """Check if it's weekend outside of ETH trading hours."""
        if market_time.weekday() < 5:  # Weekday
            return False

        # Weekend - check for Sunday evening ETH exception
        return not (
            market_time.weekday() == 6
            and market_time.hour >= 18
            and session_type == SessionType.ETH
        )

    def _is_maintenance_break(self, current_time: time, product: str = "ES") -> bool:
        """Check if current time is during maintenance break for the given product."""
        maintenance_breaks = self._get_maintenance_breaks(product)

        for break_start, break_end in maintenance_breaks:
            # Check if current time falls within any maintenance break
            if break_start <= current_time < break_end:
                return True

        return False

    def _check_session_hours(
        self, session_type: SessionType, session_times: SessionTimes, current_time: time
    ) -> bool:
        """Check if current time falls within the specified session hours."""
        if session_type == SessionType.RTH:
            return session_times.rth_start <= current_time < session_times.rth_end
        elif session_type == SessionType.ETH:
            # ETH hours: If not maintenance break, not weekend, not holiday, it's ETH
            return True

        return False
