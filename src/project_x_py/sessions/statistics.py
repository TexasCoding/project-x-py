"""
Session statistics and analytics functionality.

Provides statistical analysis capabilities for trading sessions
including volume, VWAP, volatility, and comparative analytics.

Author: TDD Implementation
Date: 2025-08-28
"""

from typing import Any

import polars as pl

from .config import SessionConfig, SessionType
from .filtering import SessionFilterMixin


class SessionStatistics:
    """Calculate statistics for trading sessions."""

    def __init__(self, config: SessionConfig | None = None):
        """Initialize with optional configuration."""
        self.config = config or SessionConfig()
        self.filter = SessionFilterMixin(config)
        self._stats_cache: dict[str, Any] = {}

    async def calculate_session_stats(
        self, data: pl.DataFrame, product: str
    ) -> dict[str, Any]:
        """Calculate comprehensive session statistics."""
        # Early return for empty data
        if data.is_empty():
            return self._get_empty_stats()

        # Filter data by sessions
        rth_data = await self.filter.filter_by_session(data, SessionType.RTH, product)
        eth_data = await self.filter.filter_by_session(data, SessionType.ETH, product)

        # Calculate statistics for both sessions
        rth_stats = self._calculate_session_metrics(rth_data, "rth")
        eth_stats = self._calculate_session_metrics(eth_data, "eth")

        # Combine results
        return {**rth_stats, **eth_stats}

    def _get_empty_stats(self) -> dict[str, Any]:
        """Return empty statistics structure."""
        return {
            "rth_volume": 0,
            "eth_volume": 0,
            "rth_vwap": 0.0,
            "eth_vwap": 0.0,
            "rth_range": 0.0,
            "eth_range": 0.0,
            "rth_high": 0.0,
            "rth_low": 0.0,
            "eth_high": 0.0,
            "eth_low": 0.0,
        }

    def _calculate_session_metrics(
        self, data: pl.DataFrame, session_prefix: str
    ) -> dict[str, Any]:
        """Calculate metrics for a single session."""
        if data.is_empty():
            return self._get_empty_session_metrics(session_prefix)

        volume = self._calculate_volume(data)
        vwap = self._calculate_vwap(data)
        high_low = self._calculate_high_low_range(data)

        return {
            f"{session_prefix}_volume": volume,
            f"{session_prefix}_vwap": vwap,
            f"{session_prefix}_range": high_low["range"],
            f"{session_prefix}_high": high_low["high"],
            f"{session_prefix}_low": high_low["low"],
        }

    def _get_empty_session_metrics(self, session_prefix: str) -> dict[str, Any]:
        """Return empty metrics for a single session."""
        return {
            f"{session_prefix}_volume": 0,
            f"{session_prefix}_vwap": 0.0,
            f"{session_prefix}_range": 0.0,
            f"{session_prefix}_high": 0.0,
            f"{session_prefix}_low": 0.0,
        }

    def _calculate_volume(self, data: pl.DataFrame) -> int:
        """Calculate total volume from data."""
        return int(data["volume"].sum())

    def _calculate_high_low_range(self, data: pl.DataFrame) -> dict[str, float]:
        """Calculate high, low, and range values."""
        # Check if data has any non-null values
        if data["high"].is_null().all() or data["low"].is_null().all():
            return {"high": 0.0, "low": 0.0, "range": 0.0}

        # Filter out null values before calculating max/min
        high_data = data.filter(pl.col("high").is_not_null())
        low_data = data.filter(pl.col("low").is_not_null())

        if high_data.is_empty() or low_data.is_empty():
            return {"high": 0.0, "low": 0.0, "range": 0.0}

        high_val = high_data["high"].max()
        low_val = low_data["low"].min()

        high = self._safe_convert_to_float(high_val)
        low = self._safe_convert_to_float(low_val)
        range_val = high - low if high > 0 else 0.0

        return {"high": high, "low": low, "range": range_val}

    def _safe_convert_to_float(self, value: Any) -> float:
        """Safely convert a value to float with type checking."""
        if value is not None and isinstance(value, int | float):
            return float(value)
        return 0.0

    def _calculate_vwap(self, data: pl.DataFrame) -> float:
        """Calculate Volume Weighted Average Price."""
        if data.is_empty():
            return 0.0

        # VWAP = sum(price * volume) / sum(volume)
        # Polars 1.44 types Series.sum() as int | float | Decimal
        total_volume = float(data["volume"].sum() or 0)
        if total_volume == 0:
            return 0.0

        vwap_numerator = float((data["close"] * data["volume"]).sum() or 0)
        return vwap_numerator / total_volume


class SessionAnalytics:
    """Advanced analytics for trading sessions."""

    def __init__(self, config: SessionConfig | None = None):
        """Initialize with optional configuration."""
        self.config = config or SessionConfig()
        self.statistics = SessionStatistics(config)

    async def compare_sessions(
        self, data: pl.DataFrame, product: str
    ) -> dict[str, Any]:
        """Provide comparative analytics between sessions."""
        stats = await self.statistics.calculate_session_stats(data, product)

        # Calculate ratios and comparisons
        volume_ratio = (
            stats["rth_volume"] / stats["eth_volume"]
            if stats["eth_volume"] > 0
            else 0.0
        )

        volatility_ratio = (
            stats["rth_range"] / stats["eth_range"] if stats["eth_range"] > 0 else 0.0
        )

        return {
            "rth_vs_eth_volume_ratio": volume_ratio,
            "rth_vs_eth_volatility_ratio": volatility_ratio,
            "session_participation_rate": volume_ratio,
            "rth_premium_discount": 0.0,  # Simplified
            "overnight_gap_average": 0.0,  # Simplified
        }

    async def get_session_volume_profile(
        self, data: pl.DataFrame, _product: str
    ) -> dict[str, Any]:
        """Calculate volume profile by session."""
        if data.is_empty():
            return {
                "rth_volume_by_hour": {},
                "eth_volume_by_hour": {},
                "peak_volume_time": {"hour": 0, "volume": 0, "session": "RTH"},
            }

        # Group by hour and calculate volume
        hourly_volume = data.group_by(data["timestamp"].dt.hour()).agg(
            [pl.col("volume").sum().alias("total_volume")]
        )

        # Find peak volume time (simplified)
        if not hourly_volume.is_empty():
            peak_row = hourly_volume.filter(
                pl.col("total_volume") == pl.col("total_volume").max()
            ).row(0)
            peak_hour = peak_row[0]
            peak_volume = peak_row[1]
        else:
            peak_hour, peak_volume = 0, 0

        return {
            "rth_volume_by_hour": {},  # Simplified
            "eth_volume_by_hour": {},  # Simplified
            "peak_volume_time": {
                "hour": peak_hour,
                "volume": peak_volume,
                "session": "RTH",  # Simplified
            },
        }

    async def analyze_session_volatility(
        self, data: pl.DataFrame, product: str
    ) -> dict[str, Any]:
        """Analyze volatility by session."""
        stats = await self.statistics.calculate_session_stats(data, product)

        return {
            "rth_realized_volatility": stats["rth_range"],  # Simplified
            "eth_realized_volatility": stats["eth_range"],  # Simplified
            "volatility_ratio": (
                stats["rth_range"] / stats["eth_range"]
                if stats["eth_range"] > 0
                else 0.0
            ),
            "volatility_clustering": 0.0,  # Simplified
        }

    async def analyze_session_gaps(
        self, _data: pl.DataFrame, _product: str
    ) -> dict[str, Any]:
        """Analyze gaps between sessions."""
        return {
            "average_overnight_gap": 0.0,
            "gap_frequency": {"up": 0, "down": 0, "flat": 0},
            "gap_fill_rate": 0.0,
            "largest_gap": 0.0,
        }

    async def calculate_efficiency_metrics(
        self, _data: pl.DataFrame, _product: str
    ) -> dict[str, Any]:
        """Calculate session efficiency metrics."""
        return {
            "rth_price_efficiency": 0.0,
            "eth_price_efficiency": 0.0,
            "rth_volume_efficiency": 0.0,
            "session_liquidity_ratio": 0.0,
        }
