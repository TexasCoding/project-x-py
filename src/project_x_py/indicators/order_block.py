"""
ProjectX Indicators - Order Block (OB) Indicator

Author: @TexasCoding
Date: 2025-08-02

Overview:
    Implements the Order Block indicator, which detects likely institutional supply/demand
    zones from price action and volume. Useful for identifying areas where large orders
    may cluster, acting as future support or resistance.

Key Features:
    - Detects bullish and bearish order blocks based on candle/volume logic
    - Configurable volume threshold, mitigation, and lookback
    - Outputs block boundaries, strength, and mitigation status per bar
    - Class and function interfaces for flexible use

Example Usage:
    ```python
    from project_x_py.indicators import OrderBlock

    ob = OrderBlock()
    data_with_ob = ob.calculate(ohlcv_data, min_volume_percentile=70)
    ```

See Also:
    - `project_x_py.indicators.fvg`
    - `project_x_py.indicators.base.BaseIndicator`
    - `project_x_py.indicators.volume`
"""

from typing import Any

import polars as pl

from project_x_py.indicators.base import BaseIndicator


class OrderBlock(BaseIndicator):
    """
    Order Block (OB) indicator for identifying institutional order zones.

    Order Blocks are areas in price action where significant institutional orders
    are believed to have been placed. They are identified by specific price action
    patterns that suggest large market participants have established positions.

    Order Blocks can act as support/resistance zones because institutional orders
    often remain active and can influence price movement when price returns to
    these areas. They are commonly used in institutional trading analysis and
    smart money concepts.
    """

    def __init__(self) -> None:
        super().__init__(
            name="OrderBlock",
            description="Order Block - identifies institutional order zones that may act as support/resistance",
        )

    def calculate(
        self,
        data: pl.DataFrame,
        **kwargs: Any,
    ) -> pl.DataFrame:
        """
        Calculate Order Blocks (OB).

        A bullish order block is identified by:
        - A down candle (close < open) followed by
        - One or more up candles that break the high of the down candle
        - The down candle becomes the bullish order block

        A bearish order block is identified by:
        - An up candle (close > open) followed by
        - One or more down candles that break the low of the up candle
        - The up candle becomes the bearish order block

        Args:
            data: DataFrame with OHLC data
            **kwargs: Additional parameters:
                open_column: Open price column (default: "open")
                high_column: High price column (default: "high")
                low_column: Low price column (default: "low")
                close_column: Close price column (default: "close")
                volume_column: Volume column (default: "volume")
                min_volume_percentile: Minimum volume percentile for valid OB (default: 50)
                check_mitigation: Whether to check if blocks have been mitigated (default: False)
                mitigation_threshold: Percentage of block that needs to be filled (default: 0.5)
                lookback_periods: Number of periods to look back for break (default: 3)
                use_wicks: Whether to use wicks or bodies for OB zones (default: True)

        Returns:
            DataFrame with Order Block columns added:
            - ob_bullish: Boolean indicating bullish order block
            - ob_bearish: Boolean indicating bearish order block
            - ob_top: Top of the order block zone
            - ob_bottom: Bottom of the order block zone
            - ob_volume: Volume of the order block candle
            - ob_strength: Strength score based on volume and price movement
            - ob_mitigated: Boolean indicating if block has been mitigated (if check_mitigation=True)

        Example:
            >>> ob = OrderBlock()
            >>> data_with_ob = ob.calculate(ohlcv_data, min_volume_percentile=70)
            >>> bullish_obs = data_with_ob.filter(pl.col("ob_bullish"))
        """
        # Extract parameters from kwargs with defaults
        open_column = kwargs.get("open_column", "open")
        high_column = kwargs.get("high_column", "high")
        low_column = kwargs.get("low_column", "low")
        close_column = kwargs.get("close_column", "close")
        volume_column = kwargs.get("volume_column", "volume")
        min_volume_percentile = kwargs.get("min_volume_percentile", 50)
        check_mitigation = kwargs.get("check_mitigation", False)
        mitigation_threshold = kwargs.get("mitigation_threshold", 0.5)
        lookback_periods = kwargs.get("lookback_periods", 3)
        use_wicks = kwargs.get("use_wicks", True)

        required_cols: list[str] = [open_column, high_column, low_column, close_column]
        if volume_column in data.columns:
            required_cols.append(volume_column)
            use_volume = True
        else:
            use_volume = False

        self.validate_data(data, required_cols)
        self.validate_data_length(data, lookback_periods + 1)

        # Calculate candle direction
        result = data.with_columns(
            [
                (pl.col(close_column) > pl.col(open_column)).alias("is_bullish_candle"),
                (pl.col(close_column) < pl.col(open_column)).alias("is_bearish_candle"),
            ]
        )

        # Calculate volume percentile if volume is available
        if use_volume:
            result = result.with_columns(
                [
                    pl.col(volume_column)
                    .rank(method="min")
                    .truediv(pl.len())
                    .mul(100)
                    .alias("volume_percentile")
                ]
            )
        else:
            result = result.with_columns(pl.lit(100).alias("volume_percentile"))

        # Initialize order block columns
        ob_bullish = [False] * len(result)
        ob_bearish = [False] * len(result)
        ob_top: list[float | None] = [None] * len(result)
        ob_bottom: list[float | None] = [None] * len(result)
        ob_volume: list[float | None] = [None] * len(result)
        ob_strength: list[float | None] = [None] * len(result)

        # Convert to dict for easier access
        data_dict = result.to_dict()

        # Identify order blocks
        for i in range(lookback_periods, len(result)):
            # Check for bullish order block (bearish candle followed by bullish break)
            for j in range(1, lookback_periods + 1):
                ob_idx = i - j

                # Check if potential OB candle is bearish, current breaks high, and volume is sufficient
                if (
                    data_dict["is_bearish_candle"][ob_idx]
                    and data_dict[high_column][i] > data_dict[high_column][ob_idx]
                    and data_dict["volume_percentile"][ob_idx] >= min_volume_percentile
                ):
                    # Found bullish order block
                    ob_bullish[ob_idx] = True

                    if use_wicks:
                        ob_top[ob_idx] = data_dict[high_column][ob_idx]
                        ob_bottom[ob_idx] = data_dict[low_column][ob_idx]
                    else:
                        ob_top[ob_idx] = max(
                            data_dict[open_column][ob_idx],
                            data_dict[close_column][ob_idx],
                        )
                        ob_bottom[ob_idx] = min(
                            data_dict[open_column][ob_idx],
                            data_dict[close_column][ob_idx],
                        )

                    if use_volume:
                        ob_volume[ob_idx] = data_dict[volume_column][ob_idx]

                    # Calculate strength based on volume and price movement
                    price_move = (
                        abs(
                            data_dict[close_column][ob_idx]
                            - data_dict[open_column][ob_idx]
                        )
                        / data_dict[open_column][ob_idx]
                    )
                    vol_score = data_dict["volume_percentile"][ob_idx] / 100
                    ob_strength[ob_idx] = (price_move * 100 + vol_score) / 2
                    break

            # Check for bearish order block (bullish candle followed by bearish break)
            for j in range(1, lookback_periods + 1):
                ob_idx = i - j

                # Mutually exclusive: a bar already tagged bullish cannot also be bearish
                if ob_bullish[ob_idx]:
                    continue

                # Check if potential OB candle is bullish, current breaks low, and volume is sufficient
                if (
                    data_dict["is_bullish_candle"][ob_idx]
                    and data_dict[low_column][i] < data_dict[low_column][ob_idx]
                    and data_dict["volume_percentile"][ob_idx] >= min_volume_percentile
                ):
                    # Found bearish order block
                    ob_bearish[ob_idx] = True

                    if use_wicks:
                        ob_top[ob_idx] = data_dict[high_column][ob_idx]
                        ob_bottom[ob_idx] = data_dict[low_column][ob_idx]
                    else:
                        ob_top[ob_idx] = max(
                            data_dict[open_column][ob_idx],
                            data_dict[close_column][ob_idx],
                        )
                        ob_bottom[ob_idx] = min(
                            data_dict[open_column][ob_idx],
                            data_dict[close_column][ob_idx],
                        )

                    if use_volume:
                        ob_volume[ob_idx] = data_dict[volume_column][ob_idx]

                    # Calculate strength
                    price_move = (
                        abs(
                            data_dict[close_column][ob_idx]
                            - data_dict[open_column][ob_idx]
                        )
                        / data_dict[open_column][ob_idx]
                    )
                    vol_score = data_dict["volume_percentile"][ob_idx] / 100
                    ob_strength[ob_idx] = (price_move * 100 + vol_score) / 2
                    break

        # Add order block columns
        result = result.with_columns(
            [
                pl.Series("ob_bullish", ob_bullish),
                pl.Series("ob_bearish", ob_bearish),
                pl.Series("ob_top", ob_top),
                pl.Series("ob_bottom", ob_bottom),
                pl.Series("ob_volume", ob_volume),
                pl.Series("ob_strength", ob_strength),
            ]
        )

        # Check for mitigation if requested
        if check_mitigation:
            # Add row index for tracking
            result = result.with_row_index("_row_idx")

            # Find order block indices
            ob_indices = result.filter(
                pl.col("ob_bullish") | pl.col("ob_bearish")
            ).select("_row_idx", "ob_bullish", "ob_top", "ob_bottom")

            # Initialize mitigation column
            mitigated = pl.Series("ob_mitigated", [False] * len(result))

            # Check each order block for mitigation
            for row in ob_indices.iter_rows(named=True):
                ob_idx = row["_row_idx"]
                is_bullish = row["ob_bullish"]
                top_value = row["ob_top"]
                bottom_value = row["ob_bottom"]

                # Skip if top_value or bottom_value is None
                if top_value is None or bottom_value is None:
                    continue

                ob_size = top_value - bottom_value
                mitigation_amount = ob_size * mitigation_threshold

                # Look at subsequent candles for mitigation
                future_data = result.filter(pl.col("_row_idx") > ob_idx)

                if is_bullish:
                    # Bullish OB is mitigated when price goes below bottom_value + mitigation_amount
                    mitigation_level = bottom_value + mitigation_amount
                    mitigated_rows = future_data.filter(
                        pl.col(low_column) <= mitigation_level
                    )
                else:
                    # Bearish OB is mitigated when price goes above top_value - mitigation_amount
                    mitigation_level = top_value - mitigation_amount
                    mitigated_rows = future_data.filter(
                        pl.col(high_column) >= mitigation_level
                    )

                if len(mitigated_rows) > 0:
                    mitigated[ob_idx] = True

            result = result.with_columns(mitigated)
            result = result.drop("_row_idx")

            # Update OB columns to exclude mitigated blocks if requested
            result = result.with_columns(
                [
                    (pl.col("ob_bullish") & ~pl.col("ob_mitigated")).alias(
                        "ob_bullish"
                    ),
                    (pl.col("ob_bearish") & ~pl.col("ob_mitigated")).alias(
                        "ob_bearish"
                    ),
                ]
            )

        # Clean up intermediate columns
        columns_to_drop: list[str] = [
            "is_bullish_candle",
            "is_bearish_candle",
            "volume_percentile",
        ]
        result = result.drop(columns_to_drop)

        return result


def calculate_order_block(
    data: pl.DataFrame,
    open_column: str = "open",
    high_column: str = "high",
    low_column: str = "low",
    close_column: str = "close",
    volume_column: str = "volume",
    min_volume_percentile: float = 50,
    check_mitigation: bool = False,
    mitigation_threshold: float = 0.5,
    lookback_periods: int = 3,
    use_wicks: bool = True,
) -> pl.DataFrame:
    """
    Calculate Order Blocks (convenience function).

    See OrderBlock.calculate() for detailed documentation.

    Args:
        data: DataFrame with OHLC data
        open_column: Open price column
        high_column: High price column
        low_column: Low price column
        close_column: Close price column
        volume_column: Volume column
        min_volume_percentile: Minimum volume percentile for valid OB
        check_mitigation: Whether to check if blocks have been mitigated
        mitigation_threshold: Percentage of block that needs to be filled
        lookback_periods: Number of periods to look back for break
        use_wicks: Whether to use wicks or bodies for OB zones

    Returns:
        DataFrame with Order Block columns added
    """
    indicator = OrderBlock()
    return indicator.calculate(
        data,
        open_column=open_column,
        high_column=high_column,
        low_column=low_column,
        close_column=close_column,
        volume_column=volume_column,
        min_volume_percentile=min_volume_percentile,
        check_mitigation=check_mitigation,
        mitigation_threshold=mitigation_threshold,
        lookback_periods=lookback_periods,
        use_wicks=use_wicks,
    )
