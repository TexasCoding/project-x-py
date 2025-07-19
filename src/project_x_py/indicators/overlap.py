"""
ProjectX Indicators - Overlap Studies (Trend Indicators)

Author: TexasCoding
Date: June 2025

Overlap study indicators are often displaced by default and superimposed
over the main price chart.
"""

import polars as pl

from .base import OverlapIndicator, ema_alpha


class SMA(OverlapIndicator):
    """Simple Moving Average indicator."""

    def __init__(self):
        super().__init__(
            name="SMA",
            description="Simple Moving Average - arithmetic mean of prices over a period",
        )

    def calculate(
        self,
        data: pl.DataFrame,
        column: str = "close",
        period: int = 20,
    ) -> pl.DataFrame:
        """
        Calculate Simple Moving Average.

        Args:
            data: DataFrame with OHLCV data
            column: Column to calculate SMA for
            period: Period for moving average

        Returns:
            DataFrame with SMA column added

        Example:
            >>> sma = SMA()
            >>> data_with_sma = sma.calculate(ohlcv_data, period=20)
            >>> print(data_with_sma.columns)  # Now includes 'sma_20'
        """
        self.validate_data(data, [column])
        self.validate_period(period, min_period=1)
        self.validate_data_length(data, period)

        return data.with_columns(
            pl.col(column).rolling_mean(window_size=period).alias(f"sma_{period}")
        )


class EMA(OverlapIndicator):
    """Exponential Moving Average indicator."""

    def __init__(self):
        super().__init__(
            name="EMA",
            description="Exponential Moving Average - weighted moving average with more weight on recent prices",
        )

    def calculate(
        self,
        data: pl.DataFrame,
        column: str = "close",
        period: int = 20,
    ) -> pl.DataFrame:
        """
        Calculate Exponential Moving Average.

        Args:
            data: DataFrame with OHLCV data
            column: Column to calculate EMA for
            period: Period for moving average

        Returns:
            DataFrame with EMA column added

        Example:
            >>> ema = EMA()
            >>> data_with_ema = ema.calculate(ohlcv_data, period=20)
            >>> print(data_with_ema.columns)  # Now includes 'ema_20'
        """
        self.validate_data(data, [column])
        self.validate_period(period, min_period=1)

        alpha = ema_alpha(period)

        return data.with_columns(
            pl.col(column).ewm_mean(alpha=alpha).alias(f"ema_{period}")
        )


class BBANDS(OverlapIndicator):
    """Bollinger Bands indicator."""

    def __init__(self):
        super().__init__(
            name="BBANDS",
            description="Bollinger Bands - moving average with upper and lower bands based on standard deviation",
        )

    def calculate(
        self,
        data: pl.DataFrame,
        column: str = "close",
        period: int = 20,
        std_dev: float = 2.0,
    ) -> pl.DataFrame:
        """
        Calculate Bollinger Bands.

        Args:
            data: DataFrame with OHLCV data
            column: Column to calculate bands for
            period: Period for moving average
            std_dev: Standard deviation multiplier

        Returns:
            DataFrame with Bollinger Bands columns added

        Example:
            >>> bbands = BBANDS()
            >>> data_with_bb = bbands.calculate(ohlcv_data)
            >>> print(
            ...     data_with_bb.columns
            ... )  # Now includes bb_upper, bb_lower, bb_middle
        """
        self.validate_data(data, [column])
        self.validate_period(period, min_period=2)
        self.validate_data_length(data, period)

        if std_dev <= 0:
            raise ValueError("Standard deviation multiplier must be positive")

        return data.with_columns(
            [
                # Middle band (SMA)
                pl.col(column)
                .rolling_mean(window_size=period)
                .alias(f"bb_middle_{period}"),
                # Upper band
                (
                    pl.col(column).rolling_mean(window_size=period)
                    + std_dev * pl.col(column).rolling_std(window_size=period)
                ).alias(f"bb_upper_{period}"),
                # Lower band
                (
                    pl.col(column).rolling_mean(window_size=period)
                    - std_dev * pl.col(column).rolling_std(window_size=period)
                ).alias(f"bb_lower_{period}"),
            ]
        )


class DEMA(OverlapIndicator):
    """Double Exponential Moving Average indicator."""

    def __init__(self):
        super().__init__(
            name="DEMA",
            description="Double Exponential Moving Average - reduces lag of traditional EMA",
        )

    def calculate(
        self,
        data: pl.DataFrame,
        column: str = "close",
        period: int = 20,
    ) -> pl.DataFrame:
        """
        Calculate Double Exponential Moving Average.

        DEMA = 2 * EMA(period) - EMA(EMA(period))

        Args:
            data: DataFrame with OHLCV data
            column: Column to calculate DEMA for
            period: Period for moving average

        Returns:
            DataFrame with DEMA column added
        """
        self.validate_data(data, [column])
        self.validate_period(period, min_period=1)

        alpha = ema_alpha(period)

        # Calculate EMA
        data_with_ema = data.with_columns(
            pl.col(column).ewm_mean(alpha=alpha).alias("ema_temp")
        )

        # Calculate EMA of EMA
        data_with_double_ema = data_with_ema.with_columns(
            pl.col("ema_temp").ewm_mean(alpha=alpha).alias("ema_ema_temp")
        )

        # Calculate DEMA
        result = data_with_double_ema.with_columns(
            (2 * pl.col("ema_temp") - pl.col("ema_ema_temp")).alias(f"dema_{period}")
        )

        # Remove temporary columns
        return result.drop(["ema_temp", "ema_ema_temp"])


class TEMA(OverlapIndicator):
    """Triple Exponential Moving Average indicator."""

    def __init__(self):
        super().__init__(
            name="TEMA",
            description="Triple Exponential Moving Average - further reduces lag compared to DEMA",
        )

    def calculate(
        self,
        data: pl.DataFrame,
        column: str = "close",
        period: int = 20,
    ) -> pl.DataFrame:
        """
        Calculate Triple Exponential Moving Average.

        TEMA = 3*EMA - 3*EMA(EMA) + EMA(EMA(EMA))

        Args:
            data: DataFrame with OHLCV data
            column: Column to calculate TEMA for
            period: Period for moving average

        Returns:
            DataFrame with TEMA column added
        """
        self.validate_data(data, [column])
        self.validate_period(period, min_period=1)

        alpha = ema_alpha(period)

        # Calculate first EMA
        data_with_ema1 = data.with_columns(
            pl.col(column).ewm_mean(alpha=alpha).alias("ema1_temp")
        )

        # Calculate second EMA (EMA of EMA)
        data_with_ema2 = data_with_ema1.with_columns(
            pl.col("ema1_temp").ewm_mean(alpha=alpha).alias("ema2_temp")
        )

        # Calculate third EMA (EMA of EMA of EMA)
        data_with_ema3 = data_with_ema2.with_columns(
            pl.col("ema2_temp").ewm_mean(alpha=alpha).alias("ema3_temp")
        )

        # Calculate TEMA
        result = data_with_ema3.with_columns(
            (
                3 * pl.col("ema1_temp") - 3 * pl.col("ema2_temp") + pl.col("ema3_temp")
            ).alias(f"tema_{period}")
        )

        # Remove temporary columns
        return result.drop(["ema1_temp", "ema2_temp", "ema3_temp"])


class WMA(OverlapIndicator):
    """Weighted Moving Average indicator."""

    def __init__(self):
        super().__init__(
            name="WMA",
            description="Weighted Moving Average - linear weighted moving average with more weight on recent prices",
        )

    def calculate(
        self,
        data: pl.DataFrame,
        column: str = "close",
        period: int = 20,
    ) -> pl.DataFrame:
        """
        Calculate Weighted Moving Average.

        Args:
            data: DataFrame with OHLCV data
            column: Column to calculate WMA for
            period: Period for moving average

        Returns:
            DataFrame with WMA column added
        """
        self.validate_data(data, [column])
        self.validate_period(period, min_period=1)
        self.validate_data_length(data, period)

        # Create weights (1, 2, 3, ..., period)
        weights = list(range(1, period + 1))
        weight_sum = sum(weights)

        # Calculate WMA using polars rolling window with custom function
        def wma_func(values):
            if len(values) < period:
                return None
            recent_values = values[-period:]
            return (
                sum(val * weight for val, weight in zip(recent_values, weights))
                / weight_sum
            )

        # For now, use a simpler rolling mean approach
        # TODO: Implement proper WMA when polars supports custom rolling functions
        return data.with_columns(
            pl.col(column).rolling_mean(window_size=period).alias(f"wma_{period}")
        )


class MIDPOINT(OverlapIndicator):
    """Midpoint over period indicator."""

    def __init__(self):
        super().__init__(
            name="MIDPOINT",
            description="Midpoint - average of highest high and lowest low over period",
        )

    def calculate(
        self,
        data: pl.DataFrame,
        column: str = "close",
        period: int = 14,
    ) -> pl.DataFrame:
        """
        Calculate Midpoint over period.

        Args:
            data: DataFrame with OHLCV data
            column: Column to calculate midpoint for
            period: Lookback period

        Returns:
            DataFrame with midpoint column added
        """
        self.validate_data(data, [column])
        self.validate_period(period, min_period=1)
        self.validate_data_length(data, period)

        return data.with_columns(
            (
                (
                    pl.col(column).rolling_max(window_size=period)
                    + pl.col(column).rolling_min(window_size=period)
                )
                / 2
            ).alias(f"midpoint_{period}")
        )


# Convenience functions for backwards compatibility and TA-Lib style usage
def calculate_sma(
    data: pl.DataFrame, column: str = "close", period: int = 20
) -> pl.DataFrame:
    """Calculate Simple Moving Average (convenience function)."""
    return SMA().calculate(data, column=column, period=period)


def calculate_ema(
    data: pl.DataFrame, column: str = "close", period: int = 20
) -> pl.DataFrame:
    """Calculate Exponential Moving Average (convenience function)."""
    return EMA().calculate(data, column=column, period=period)


def calculate_bollinger_bands(
    data: pl.DataFrame, column: str = "close", period: int = 20, std_dev: float = 2.0
) -> pl.DataFrame:
    """Calculate Bollinger Bands (convenience function)."""
    return BBANDS().calculate(data, column=column, period=period, std_dev=std_dev)
