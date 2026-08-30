"""
ProjectX Indicators - Fair Value Gap (FVG) Indicator

Author: @TexasCoding
Date: 2025-08-02

Overview:
    Implements the Fair Value Gap (FVG) indicator for identifying price imbalances
    and potential support/resistance zones. Detects gaps in price action with
    optional mitigation logic, helping traders spot areas likely to be revisited.

Key Features:
    - Identifies bullish/bearish fair value gaps from OHLC data
    - Supports configurable gap size, mitigation threshold, and custom columns
    - Returns gap boundary, size, and mitigation status for each bar
    - Callable as a class or via TA-Lib-style convenience function

Example Usage:
    ```python
    from project_x_py.indicators import FVG, FVGIndicator

    data_with_fvg = FVG(ohlcv_data, min_gap_size=0.001)
    # or FVGIndicator().calculate(ohlcv_data, min_gap_size=0.001)
    gaps = data_with_fvg.filter(pl.col("fvg_bullish"))
    ```

See Also:
    - `project_x_py.indicators.order_block`
    - `project_x_py.indicators.base.BaseIndicator`
"""

from typing import Any

import polars as pl

from project_x_py.indicators.base import BaseIndicator


class FVG(BaseIndicator):
    """
    Fair Value Gap (FVG) indicator for identifying price imbalances.

    Fair Value Gaps are areas in price action where the market has moved so quickly
    that it has left a "gap" or imbalance. These areas often act as support/resistance
    zones as price tends to return to fill these gaps.

    The indicator identifies both bullish and bearish FVGs based on specific price
    action patterns and can optionally track whether gaps have been mitigated (filled).
    """

    def __init__(self) -> None:
        super().__init__(
            name="FVG",
            description="Fair Value Gap - identifies price imbalance areas that may act as support/resistance",
        )

    def calculate(
        self,
        data: pl.DataFrame,
        **kwargs: Any,
    ) -> pl.DataFrame:
        """
        Calculate Fair Value Gaps (FVG) using three-candle pattern.

        A bullish FVG occurs when:
        - Candle 3's low > Candle 1's high (creating an unfilled gap)
        - Candle 2 (the middle candle) does not fill that zone
          (candle 2's low stays above candle 1's high)

        A bearish FVG occurs when:
        - Candle 3's high < Candle 1's low (creating an unfilled gap)
        - Candle 2 does not fill that zone
          (candle 2's high stays below candle 1's low)

        Args:
            data: DataFrame with OHLC data
            **kwargs: Additional parameters:
                high_column: High price column (default: "high")
                low_column: Low price column (default: "low")
                close_column: Close price column (default: "close")
                min_gap_size: Minimum gap size (in price units) to consider valid (default: 0.0)
                min_gap_percent: Minimum gap size as percentage (default: 0.0)
                check_mitigation: Whether to check if gaps have been mitigated (default: False)
                mitigation_threshold: Percentage of gap that needs to be filled to consider it mitigated (default: 0.5)

        Returns:
            DataFrame with FVG columns added:
            - fvg_bullish: Boolean indicating bullish FVG
            - fvg_bearish: Boolean indicating bearish FVG
            - fvg_bullish_start: Start of bullish gap (candle 1 high)
            - fvg_bullish_end: End of bullish gap (candle 3 low)
            - fvg_bearish_start: Start of bearish gap (candle 1 low)
            - fvg_bearish_end: End of bearish gap (candle 3 high)
            - fvg_gap_size: Size of the gap
            - fvg_gap_percent: Gap size as percentage
            - fvg_mitigated: Boolean indicating if gap has been mitigated (if check_mitigation=True)

        Example:
            >>> fvg = FVG()
            >>> data_with_fvg = fvg.calculate(ohlcv_data, min_gap_size=0.001)
            >>> bullish_gaps = data_with_fvg.filter(pl.col("fvg_bullish"))
        """
        # Extract parameters from kwargs with defaults
        high_column = kwargs.get("high_column", "high")
        low_column = kwargs.get("low_column", "low")
        close_column = kwargs.get("close_column", "close")
        min_gap_size = kwargs.get("min_gap_size", 0.0)
        min_gap_percent = kwargs.get("min_gap_percent", 0.0)
        check_mitigation = kwargs.get("check_mitigation", False)
        mitigation_threshold = kwargs.get("mitigation_threshold", 0.5)

        required_cols: list[str] = [high_column, low_column, close_column]
        self.validate_data(data, required_cols)
        self.validate_data_length(data, 3)  # Need at least 3 candles for pattern

        # Get values for three-candle pattern
        result = data.with_columns(
            [
                # Candle 1 (two bars ago)
                pl.col(high_column).shift(2).alias("candle1_high"),
                pl.col(low_column).shift(2).alias("candle1_low"),
                # Candle 2 (previous bar) - not used in gap detection but kept for potential future use
                pl.col(high_column).shift(1).alias("candle2_high"),
                pl.col(low_column).shift(1).alias("candle2_low"),
                # Candle 3 is current bar
            ]
        )

        # Identify FVGs using three-candle pattern. The middle candle must not
        # fill the imbalance between candle 1 and candle 3.
        result = result.with_columns(
            [
                # Bullish: c3.low > c1.high AND c2.low > c1.high (middle did not fill)
                (
                    (pl.col(low_column) > pl.col("candle1_high"))
                    & (pl.col("candle2_low") > pl.col("candle1_high"))
                ).alias("fvg_bullish_raw"),
                # Bearish: c3.high < c1.low AND c2.high < c1.low (middle did not fill)
                (
                    (pl.col(high_column) < pl.col("candle1_low"))
                    & (pl.col("candle2_high") < pl.col("candle1_low"))
                ).alias("fvg_bearish_raw"),
            ]
        )

        # Calculate gap boundaries and size
        result = result.with_columns(
            [
                # Bullish gap: from candle 1 high to current low
                pl.when(pl.col("fvg_bullish_raw"))
                .then(pl.col("candle1_high"))
                .otherwise(None)
                .alias("fvg_bullish_start"),
                pl.when(pl.col("fvg_bullish_raw"))
                .then(pl.col(low_column))
                .otherwise(None)
                .alias("fvg_bullish_end"),
                # Bearish gap: from candle 1 low to current high
                pl.when(pl.col("fvg_bearish_raw"))
                .then(pl.col("candle1_low"))
                .otherwise(None)
                .alias("fvg_bearish_start"),
                pl.when(pl.col("fvg_bearish_raw"))
                .then(pl.col(high_column))
                .otherwise(None)
                .alias("fvg_bearish_end"),
            ]
        )

        # Calculate gap size and percentage
        result = result.with_columns(
            [
                pl.when(pl.col("fvg_bullish_raw"))
                .then((pl.col("fvg_bullish_end") - pl.col("fvg_bullish_start")).abs())
                .when(pl.col("fvg_bearish_raw"))
                .then((pl.col("fvg_bearish_start") - pl.col("fvg_bearish_end")).abs())
                .otherwise(None)
                .alias("fvg_gap_size"),
                # Calculate gap as percentage of price
                pl.when(pl.col("fvg_bullish_raw"))
                .then(
                    (pl.col("fvg_bullish_end") - pl.col("fvg_bullish_start")).abs()
                    / pl.col("fvg_bullish_start")
                    * 100
                )
                .when(pl.col("fvg_bearish_raw"))
                .then(
                    (pl.col("fvg_bearish_start") - pl.col("fvg_bearish_end")).abs()
                    / pl.col("fvg_bearish_start")
                    * 100
                )
                .otherwise(None)
                .alias("fvg_gap_percent"),
            ]
        )

        # Apply minimum gap size and percentage filters
        result = result.with_columns(
            [
                (
                    pl.col("fvg_bullish_raw")
                    & (pl.col("fvg_gap_size") >= min_gap_size)
                    & (pl.col("fvg_gap_percent") >= min_gap_percent)
                ).alias("fvg_bullish"),
                (
                    pl.col("fvg_bearish_raw")
                    & (pl.col("fvg_gap_size") >= min_gap_size)
                    & (pl.col("fvg_gap_percent") >= min_gap_percent)
                ).alias("fvg_bearish"),
            ]
        )

        # Check for mitigation if requested
        if check_mitigation:
            # Add row index for tracking
            result = result.with_row_index("_row_idx")

            # Find gap indices
            gap_indices = result.filter(
                pl.col("fvg_bullish") | pl.col("fvg_bearish")
            ).select(
                "_row_idx",
                "fvg_bullish",
                "fvg_bullish_start",
                "fvg_bullish_end",
                "fvg_bearish_start",
                "fvg_bearish_end",
            )

            # Initialize mitigation column
            mitigated = pl.Series("fvg_mitigated", [False] * len(result))

            # Check each gap for mitigation
            for row in gap_indices.iter_rows(named=True):
                gap_idx = row["_row_idx"]
                is_bullish = row["fvg_bullish"]

                # Look at subsequent candles for mitigation
                future_data = result.filter(pl.col("_row_idx") > gap_idx)

                if is_bullish and row["fvg_bullish_start"] is not None:
                    gap_start = row["fvg_bullish_start"]
                    gap_end = row["fvg_bullish_end"]
                    gap_size = gap_end - gap_start
                    mitigation_amount = gap_size * mitigation_threshold
                    # Bullish gap is mitigated when price retraces into the gap
                    mitigation_level = gap_start + mitigation_amount
                    mitigated_rows = future_data.filter(
                        pl.col(low_column) <= mitigation_level
                    )
                elif not is_bullish and row["fvg_bearish_start"] is not None:
                    gap_start = row["fvg_bearish_start"]
                    gap_end = row["fvg_bearish_end"]
                    gap_size = gap_start - gap_end
                    mitigation_amount = gap_size * mitigation_threshold
                    # Bearish gap is mitigated when price retraces into the gap
                    mitigation_level = gap_start - mitigation_amount
                    mitigated_rows = future_data.filter(
                        pl.col(high_column) >= mitigation_level
                    )
                else:
                    continue

                if len(mitigated_rows) > 0:
                    mitigated[gap_idx] = True

            result = result.with_columns(mitigated)
            result = result.drop("_row_idx")
            # Keep historical fvg_bullish / fvg_bearish; callers use fvg_mitigated.

        # Clean up intermediate columns
        columns_to_drop: list[str] = [
            "candle1_high",
            "candle1_low",
            "candle2_high",
            "candle2_low",
            "fvg_bullish_raw",
            "fvg_bearish_raw",
        ]

        result = result.drop(columns_to_drop)

        return result


def calculate_fvg(
    data: pl.DataFrame,
    high_column: str = "high",
    low_column: str = "low",
    close_column: str = "close",
    min_gap_size: float = 0.0,
    min_gap_percent: float = 0.0,
    check_mitigation: bool = False,
    mitigation_threshold: float = 0.5,
) -> pl.DataFrame:
    """
    Calculate Fair Value Gaps using three-candle pattern (convenience function).

    See FVG.calculate() for detailed documentation.

    Args:
        data: DataFrame with OHLC data
        high_column: High price column
        low_column: Low price column
        close_column: Close price column
        min_gap_size: Minimum gap size to consider valid
        min_gap_percent: Minimum gap size as percentage
        check_mitigation: Whether to check if gaps have been mitigated
        mitigation_threshold: Percentage of gap that needs to be filled to consider it mitigated

    Returns:
        DataFrame with FVG columns added
    """
    indicator = FVG()
    return indicator.calculate(
        data,
        high_column=high_column,
        low_column=low_column,
        close_column=close_column,
        min_gap_size=min_gap_size,
        min_gap_percent=min_gap_percent,
        check_mitigation=check_mitigation,
        mitigation_threshold=mitigation_threshold,
    )
