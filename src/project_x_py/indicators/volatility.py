"""
ProjectX Indicators - Volatility Indicators

Author: TexasCoding
Date: June 2025

Volatility indicators measure the rate of price fluctuations,
helping traders understand market volatility and potential breakouts.
"""

import polars as pl

from .base import VolatilityIndicator, safe_division


class ATR(VolatilityIndicator):
    """Average True Range indicator."""

    def __init__(self):
        super().__init__(
            name="ATR",
            description="Average True Range - measures market volatility by analyzing the range of price movements",
        )

    def calculate(
        self,
        data: pl.DataFrame,
        high_column: str = "high",
        low_column: str = "low",
        close_column: str = "close",
        period: int = 14,
    ) -> pl.DataFrame:
        """
        Calculate Average True Range (ATR).

        Args:
            data: DataFrame with OHLCV data
            high_column: High price column
            low_column: Low price column
            close_column: Close price column
            period: ATR period

        Returns:
            DataFrame with ATR column added

        Example:
            >>> atr = ATR()
            >>> data_with_atr = atr.calculate(ohlcv_data)
            >>> print(data_with_atr.columns)  # Now includes 'atr_14'
        """
        required_cols = [high_column, low_column, close_column]
        self.validate_data(data, required_cols)
        self.validate_period(period, min_period=1)
        self.validate_data_length(data, 2)  # Need at least 2 rows for prev_close

        # Calculate True Range components
        result = (
            data.with_columns(
                [
                    pl.col(close_column).shift(1).alias("prev_close"),
                ]
            )
            .with_columns(
                [
                    # TR1: High - Low
                    (pl.col(high_column) - pl.col(low_column)).alias("tr1"),
                    # TR2: |High - Previous Close|
                    (pl.col(high_column) - pl.col("prev_close")).abs().alias("tr2"),
                    # TR3: |Low - Previous Close|
                    (pl.col(low_column) - pl.col("prev_close")).abs().alias("tr3"),
                ]
            )
            .with_columns(
                # True Range = max(TR1, TR2, TR3)
                pl.max_horizontal(["tr1", "tr2", "tr3"]).alias("true_range")
            )
            .with_columns(
                # ATR = EMA of True Range (Wilder's smoothing)
                pl.col("true_range")
                .ewm_mean(alpha=1.0 / period, adjust=False)
                .alias(f"atr_{period}")
            )
        )

        # Remove intermediate columns
        return result.drop(["prev_close", "tr1", "tr2", "tr3", "true_range"])


class ADX(VolatilityIndicator):
    """Average Directional Index indicator."""

    def __init__(self):
        super().__init__(
            name="ADX",
            description="Average Directional Index - measures trend strength regardless of direction",
        )

    def calculate(
        self,
        data: pl.DataFrame,
        high_column: str = "high",
        low_column: str = "low",
        close_column: str = "close",
        period: int = 14,
    ) -> pl.DataFrame:
        """
        Calculate Average Directional Index (ADX).

        Args:
            data: DataFrame with OHLCV data
            high_column: High price column
            low_column: Low price column
            close_column: Close price column
            period: ADX period

        Returns:
            DataFrame with ADX, +DI, -DI columns added

        Example:
            >>> adx = ADX()
            >>> data_with_adx = adx.calculate(ohlcv_data)
            >>> # Now includes adx_14, di_plus_14, di_minus_14
        """
        required_cols = [high_column, low_column, close_column]
        self.validate_data(data, required_cols)
        self.validate_period(period, min_period=1)
        self.validate_data_length(data, 2)

        # Calculate price movements
        result = data.with_columns(
            [
                pl.col(high_column).diff().alias("up_move"),
                (-pl.col(low_column).diff()).alias("down_move"),
            ]
        ).with_columns(
            [
                # Positive and negative directional movements
                pl.when(
                    (pl.col("up_move") > pl.col("down_move")) & (pl.col("up_move") > 0)
                )
                .then(pl.col("up_move"))
                .otherwise(0)
                .alias("dm_plus"),
                pl.when(
                    (pl.col("down_move") > pl.col("up_move"))
                    & (pl.col("down_move") > 0)
                )
                .then(pl.col("down_move"))
                .otherwise(0)
                .alias("dm_minus"),
            ]
        )

        # Calculate True Range for ADX (reuse ATR calculation)
        atr_indicator = ATR()
        result = atr_indicator.calculate(
            result, high_column, low_column, close_column, period
        )

        # Calculate smoothed DM using Wilder's smoothing
        alpha = 1.0 / period
        result = (
            result.with_columns(
                [
                    pl.col("dm_plus")
                    .ewm_mean(alpha=alpha, adjust=False)
                    .alias("dm_plus_smooth"),
                    pl.col("dm_minus")
                    .ewm_mean(alpha=alpha, adjust=False)
                    .alias("dm_minus_smooth"),
                ]
            )
            .with_columns(
                [
                    # Calculate +DI and -DI
                    (
                        100
                        * safe_division(
                            pl.col("dm_plus_smooth"), pl.col(f"atr_{period}")
                        )
                    ).alias(f"di_plus_{period}"),
                    (
                        100
                        * safe_division(
                            pl.col("dm_minus_smooth"), pl.col(f"atr_{period}")
                        )
                    ).alias(f"di_minus_{period}"),
                ]
            )
            .with_columns(
                [
                    # Calculate DX
                    (
                        100
                        * safe_division(
                            (
                                pl.col(f"di_plus_{period}")
                                - pl.col(f"di_minus_{period}")
                            ).abs(),
                            pl.col(f"di_plus_{period}") + pl.col(f"di_minus_{period}"),
                        )
                    ).alias("dx")
                ]
            )
            .with_columns(
                # Calculate ADX (smoothed DX)
                pl.col("dx").ewm_mean(alpha=alpha, adjust=False).alias(f"adx_{period}")
            )
        )

        # Remove intermediate columns
        return result.drop(
            [
                "up_move",
                "down_move",
                "dm_plus",
                "dm_minus",
                "dm_plus_smooth",
                "dm_minus_smooth",
                "dx",
                f"atr_{period}",  # Remove ATR as it's only needed for calculation
            ]
        )


class NATR(VolatilityIndicator):
    """Normalized Average True Range indicator."""

    def __init__(self):
        super().__init__(
            name="NATR",
            description="Normalized Average True Range - ATR as percentage of closing price",
        )

    def calculate(
        self,
        data: pl.DataFrame,
        high_column: str = "high",
        low_column: str = "low",
        close_column: str = "close",
        period: int = 14,
    ) -> pl.DataFrame:
        """
        Calculate Normalized Average True Range (NATR).

        NATR = (ATR / Close) * 100

        Args:
            data: DataFrame with OHLCV data
            high_column: High price column
            low_column: Low price column
            close_column: Close price column
            period: NATR period

        Returns:
            DataFrame with NATR column added
        """
        required_cols = [high_column, low_column, close_column]
        self.validate_data(data, required_cols)
        self.validate_period(period, min_period=1)

        # First calculate ATR
        atr_indicator = ATR()
        result = atr_indicator.calculate(
            data, high_column, low_column, close_column, period
        )

        # Calculate NATR
        result = result.with_columns(
            (100 * safe_division(pl.col(f"atr_{period}"), pl.col(close_column))).alias(
                f"natr_{period}"
            )
        )

        # Remove ATR column as we only need NATR
        return result.drop(f"atr_{period}")


class TRANGE(VolatilityIndicator):
    """True Range indicator."""

    def __init__(self):
        super().__init__(
            name="TRANGE",
            description="True Range - measures the actual range of price movement for a single period",
        )

    def calculate(
        self,
        data: pl.DataFrame,
        high_column: str = "high",
        low_column: str = "low",
        close_column: str = "close",
    ) -> pl.DataFrame:
        """
        Calculate True Range.

        Args:
            data: DataFrame with OHLCV data
            high_column: High price column
            low_column: Low price column
            close_column: Close price column

        Returns:
            DataFrame with True Range column added
        """
        required_cols = [high_column, low_column, close_column]
        self.validate_data(data, required_cols)
        self.validate_data_length(data, 2)

        # Calculate True Range components
        result = (
            data.with_columns(
                [
                    pl.col(close_column).shift(1).alias("prev_close"),
                ]
            )
            .with_columns(
                [
                    # TR1: High - Low
                    (pl.col(high_column) - pl.col(low_column)).alias("tr1"),
                    # TR2: |High - Previous Close|
                    (pl.col(high_column) - pl.col("prev_close")).abs().alias("tr2"),
                    # TR3: |Low - Previous Close|
                    (pl.col(low_column) - pl.col("prev_close")).abs().alias("tr3"),
                ]
            )
            .with_columns(
                # True Range = max(TR1, TR2, TR3)
                pl.max_horizontal(["tr1", "tr2", "tr3"]).alias("trange")
            )
        )

        # Remove intermediate columns
        return result.drop(["prev_close", "tr1", "tr2", "tr3"])


class ULTOSC(VolatilityIndicator):
    """Ultimate Oscillator indicator."""

    def __init__(self):
        super().__init__(
            name="ULTOSC",
            description="Ultimate Oscillator - momentum oscillator using three timeframes",
        )

    def calculate(
        self,
        data: pl.DataFrame,
        high_column: str = "high",
        low_column: str = "low",
        close_column: str = "close",
        period1: int = 7,
        period2: int = 14,
        period3: int = 28,
    ) -> pl.DataFrame:
        """
        Calculate Ultimate Oscillator.

        Args:
            data: DataFrame with OHLCV data
            high_column: High price column
            low_column: Low price column
            close_column: Close price column
            period1: First period (fast)
            period2: Second period (medium)
            period3: Third period (slow)

        Returns:
            DataFrame with Ultimate Oscillator column added
        """
        required_cols = [high_column, low_column, close_column]
        self.validate_data(data, required_cols)
        self.validate_period(period1, min_period=1)
        self.validate_period(period2, min_period=1)
        self.validate_period(period3, min_period=1)
        self.validate_data_length(data, max(period1, period2, period3))

        # Calculate True Range
        trange_indicator = TRANGE()
        result = trange_indicator.calculate(data, high_column, low_column, close_column)

        # Calculate Buying Pressure (BP = Close - min(Low, Previous Close))
        result = result.with_columns(
            [
                pl.col(close_column).shift(1).alias("prev_close_uo"),
                (
                    pl.col(close_column)
                    - pl.min_horizontal(
                        [pl.col(low_column), pl.col(close_column).shift(1)]
                    )
                ).alias("buying_pressure"),
            ]
        )

        # Calculate sums for each period
        for period in [period1, period2, period3]:
            result = result.with_columns(
                [
                    pl.col("buying_pressure")
                    .rolling_sum(window_size=period)
                    .alias(f"bp_sum_{period}"),
                    pl.col("trange")
                    .rolling_sum(window_size=period)
                    .alias(f"tr_sum_{period}"),
                ]
            )

        # Calculate Ultimate Oscillator
        result = result.with_columns(
            (
                100
                * (
                    (
                        4
                        * safe_division(
                            pl.col(f"bp_sum_{period1}"), pl.col(f"tr_sum_{period1}")
                        )
                    )
                    + (
                        2
                        * safe_division(
                            pl.col(f"bp_sum_{period2}"), pl.col(f"tr_sum_{period2}")
                        )
                    )
                    + safe_division(
                        pl.col(f"bp_sum_{period3}"), pl.col(f"tr_sum_{period3}")
                    )
                )
                / 7
            ).alias(f"ultosc_{period1}_{period2}_{period3}")
        )

        # Remove intermediate columns
        columns_to_drop = ["prev_close_uo", "buying_pressure", "trange"]
        for period in [period1, period2, period3]:
            columns_to_drop.extend([f"bp_sum_{period}", f"tr_sum_{period}"])

        return result.drop(columns_to_drop)


# Convenience functions for backwards compatibility and TA-Lib style usage
def calculate_atr(
    data: pl.DataFrame,
    high_column: str = "high",
    low_column: str = "low",
    close_column: str = "close",
    period: int = 14,
) -> pl.DataFrame:
    """Calculate ATR (convenience function)."""
    return ATR().calculate(
        data,
        high_column=high_column,
        low_column=low_column,
        close_column=close_column,
        period=period,
    )


def calculate_adx(
    data: pl.DataFrame,
    high_column: str = "high",
    low_column: str = "low",
    close_column: str = "close",
    period: int = 14,
) -> pl.DataFrame:
    """Calculate ADX (convenience function)."""
    return ADX().calculate(
        data,
        high_column=high_column,
        low_column=low_column,
        close_column=close_column,
        period=period,
    )
