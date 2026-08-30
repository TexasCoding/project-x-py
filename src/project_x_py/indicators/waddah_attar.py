"""
ProjectX Indicators - Waddah Attar Explosion (WAE) Indicator

Author: @TexasCoding
Date: 2025-08-02

Overview:
    Implements the Waddah Attar Explosion (WAE) indicator for detecting strong
    trends and breakout conditions. Combines MACD, Bollinger Bands, and ATR-based
    dead zone logic to filter for high-momentum moves with volatility context.

Key Features:
    - Computes explosion line, trend, and dead zone from price/volatility data
    - Configurable MACD/Bollinger/ATR parameters for fine-tuning
    - Flags bullish/bearish breakouts above dead zone threshold
    - Callable as a class or with TA-Lib-style convenience function

Example Usage:
    ```python
    from project_x_py.indicators import WAE

    wae = WAE()
    data_with_wae = wae.calculate(ohlcv_data)
    signals = data_with_wae.filter(pl.col("wae_explosion_above_dz"))
    ```

See Also:
    - `project_x_py.indicators.volatility`
    - `project_x_py.indicators.base.BaseIndicator`
    - `project_x_py.indicators.momentum`
"""

from typing import Any

import polars as pl

from project_x_py.indicators.base import BaseIndicator


class WAE(BaseIndicator):
    """
    Waddah Attar Explosion (WAE) indicator for identifying strong trends and breakouts.

    WAE combines MACD and Bollinger Bands to create a comprehensive trend detection
    system. It generates an "explosion line" that measures trend strength and a
    "dead zone" that filters out ranging markets.

    The indicator is particularly effective at identifying strong trending markets
    and potential breakout opportunities while avoiding false signals during
    consolidation periods.
    """

    def __init__(self) -> None:
        super().__init__(
            name="WAE",
            description="Waddah Attar Explosion - identifies strong trends and potential breakouts using MACD and Bollinger Bands",
        )

    def calculate(
        self,
        data: pl.DataFrame,
        **kwargs: Any,
    ) -> pl.DataFrame:
        """
        Calculate Waddah Attar Explosion (WAE).

        The WAE combines MACD and Bollinger Bands to create an explosion line
        that indicates strong momentum and a dead zone line that filters out
        ranging/consolidating markets.

        Formula (implemented):
        - MACD Line = EMA(fast) - EMA(slow)
        - BB Upper = SMA(bb_period) + (bb_mult * StdDev)
        - BB Lower = SMA(bb_period) - (bb_mult * StdDev)
        - Explosion = (BB_upper - BB_lower) * abs(MACD) * sensitivity / bb_period
        - Trend = 1 if MACD > 0, -1 if MACD < 0
        - Dead Zone = ATR(dead_zone_period) * dead_zone_mult

        This is a MACD × Bollinger-width explosion, not a Hilbert/TA-Lib port.
        Short frames are accepted; ATR dead-zone values stay null until enough
        bars exist for the ATR window.

        Args:
            data: DataFrame with OHLC data
            **kwargs: Additional parameters:
                close_column: Close price column (default: "close")
                high_column: High price column (default: "high")
                low_column: Low price column (default: "low")
                fast_period: Fast EMA period for MACD (default: 20)
                slow_period: Slow EMA period for MACD (default: 40)
                bb_period: Bollinger Bands period (default: 20)
                bb_mult: Bollinger Bands multiplier (default: 2.0)
                sensitivity: Sensitivity multiplier for explosion (default: 150)
                dead_zone_period: ATR period for dead zone (default: 100)
                dead_zone_mult: Multiplier for dead zone ATR (default: 3.6)

        Returns:
            DataFrame with WAE columns added:
            - wae_explosion: Explosion value (strength of trend)
            - wae_trend: Trend direction (1 for bullish, -1 for bearish)
            - wae_dead_zone: Dead zone threshold
            - wae_bullish: Boolean for bullish explosion above dead zone
            - wae_bearish: Boolean for bearish explosion above dead zone
            - wae_explosion_above_dz: Boolean for explosion above dead zone

        Example:
            >>> wae = WAE()
            >>> data_with_wae = wae.calculate(ohlcv_data)
            >>> strong_trends = data_with_wae.filter(pl.col("wae_explosion_above_dz"))
        """
        # Extract parameters from kwargs with defaults
        close_column = kwargs.get("close_column", "close")
        high_column = kwargs.get("high_column", "high")
        low_column = kwargs.get("low_column", "low")
        fast_period = kwargs.get("fast_period", 20)
        slow_period = kwargs.get("slow_period", 40)
        bb_period = kwargs.get("bb_period", 20)
        bb_mult = kwargs.get("bb_mult", 2.0)
        sensitivity = kwargs.get("sensitivity", 150)
        dead_zone_period = kwargs.get("dead_zone_period", 100)
        dead_zone_mult = kwargs.get("dead_zone_mult", 3.6)

        required_cols: list[str] = [close_column, high_column, low_column]
        self.validate_data(data, required_cols)
        # Do not require dead_zone_period bars; ATR simply warms up in-place.
        self.validate_data_length(data, max(slow_period, bb_period, 2))

        # Calculate MACD components
        result = data.with_columns(
            [
                # Fast EMA
                pl.col(close_column)
                .ewm_mean(alpha=2.0 / (fast_period + 1), adjust=False)
                .alias("ema_fast"),
                # Slow EMA
                pl.col(close_column)
                .ewm_mean(alpha=2.0 / (slow_period + 1), adjust=False)
                .alias("ema_slow"),
            ]
        )

        # Calculate MACD line
        result = result.with_columns(
            (pl.col("ema_fast") - pl.col("ema_slow")).alias("macd_line")
        )

        # Calculate Bollinger Bands
        result = result.with_columns(
            [
                # SMA for BB
                pl.col(close_column)
                .rolling_mean(window_size=bb_period)
                .alias("bb_sma"),
                # StdDev for BB
                pl.col(close_column).rolling_std(window_size=bb_period).alias("bb_std"),
            ]
        )

        # Calculate BB bands
        result = result.with_columns(
            [
                (pl.col("bb_sma") + (bb_mult * pl.col("bb_std"))).alias("bb_upper"),
                (pl.col("bb_sma") - (bb_mult * pl.col("bb_std"))).alias("bb_lower"),
            ]
        )

        # Calculate explosion value
        result = result.with_columns(
            [
                # Explosion = (BB_Upper - BB_Lower) * MACD_Line * Sensitivity / BB_Period
                (
                    (pl.col("bb_upper") - pl.col("bb_lower"))
                    * pl.col("macd_line").abs()
                    * sensitivity
                    / bb_period
                ).alias("wae_explosion"),
                # Trend direction
                pl.when(pl.col("macd_line") > 0)
                .then(pl.lit(1))
                .when(pl.col("macd_line") < 0)
                .then(pl.lit(-1))
                .otherwise(pl.lit(0))
                .alias("wae_trend"),
            ]
        )

        # Calculate ATR for dead zone
        result = result.with_columns(
            [
                pl.col(close_column).shift(1).alias("prev_close"),
            ]
        )

        # Calculate True Range components
        result = result.with_columns(
            [
                # TR1: High - Low
                (pl.col(high_column) - pl.col(low_column)).alias("tr1"),
                # TR2: |High - Previous Close|
                (pl.col(high_column) - pl.col("prev_close")).abs().alias("tr2"),
                # TR3: |Low - Previous Close|
                (pl.col(low_column) - pl.col("prev_close")).abs().alias("tr3"),
            ]
        )

        # True Range = max(TR1, TR2, TR3)
        result = result.with_columns(
            pl.max_horizontal(["tr1", "tr2", "tr3"]).alias("true_range")
        )

        # ATR = EMA of True Range
        result = result.with_columns(
            pl.col("true_range")
            .ewm_mean(alpha=1.0 / dead_zone_period, adjust=False)
            .alias("atr")
        )

        # Calculate dead zone
        result = result.with_columns(
            (pl.col("atr") * dead_zone_mult).alias("wae_dead_zone")
        )

        # Determine if explosion is above dead zone
        result = result.with_columns(
            [
                (pl.col("wae_explosion") > pl.col("wae_dead_zone")).alias(
                    "wae_explosion_above_dz"
                ),
                # Bullish signal: explosion above dead zone and trend is positive
                (
                    (pl.col("wae_explosion") > pl.col("wae_dead_zone"))
                    & (pl.col("wae_trend") == 1)
                ).alias("wae_bullish"),
                # Bearish signal: explosion above dead zone and trend is negative
                (
                    (pl.col("wae_explosion") > pl.col("wae_dead_zone"))
                    & (pl.col("wae_trend") == -1)
                ).alias("wae_bearish"),
            ]
        )

        # Clean up intermediate columns
        columns_to_drop: list[str] = [
            "ema_fast",
            "ema_slow",
            "macd_line",
            "bb_sma",
            "bb_std",
            "bb_upper",
            "bb_lower",
            "prev_close",
            "tr1",
            "tr2",
            "tr3",
            "true_range",
            "atr",
        ]
        result = result.drop(columns_to_drop)

        return result


def calculate_wae(
    data: pl.DataFrame,
    close_column: str = "close",
    high_column: str = "high",
    low_column: str = "low",
    fast_period: int = 20,
    slow_period: int = 40,
    bb_period: int = 20,
    bb_mult: float = 2.0,
    sensitivity: float = 150,
    dead_zone_period: int = 100,
    dead_zone_mult: float = 3.6,
) -> pl.DataFrame:
    """
    Calculate Waddah Attar Explosion (convenience function).

    See WAE.calculate() for detailed documentation.

    Args:
        data: DataFrame with OHLC data
        close_column: Close price column
        high_column: High price column
        low_column: Low price column
        fast_period: Fast EMA period for MACD
        slow_period: Slow EMA period for MACD
        bb_period: Bollinger Bands period
        bb_mult: Bollinger Bands multiplier
        sensitivity: Sensitivity multiplier for explosion
        dead_zone_period: ATR period for dead zone
        dead_zone_mult: Multiplier for dead zone ATR

    Returns:
        DataFrame with WAE columns added
    """
    indicator = WAE()
    return indicator.calculate(
        data,
        close_column=close_column,
        high_column=high_column,
        low_column=low_column,
        fast_period=fast_period,
        slow_period=slow_period,
        bb_period=bb_period,
        bb_mult=bb_mult,
        sensitivity=sensitivity,
        dead_zone_period=dead_zone_period,
        dead_zone_mult=dead_zone_mult,
    )
