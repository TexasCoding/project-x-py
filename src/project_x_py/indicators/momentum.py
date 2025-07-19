"""
ProjectX Indicators - Momentum Indicators

Author: TexasCoding
Date: June 2025

Momentum indicators measure the rate of change in price movements,
helping identify overbought/oversold conditions and trend strength.
"""

import polars as pl

from .base import (
    MomentumIndicator,
    ema_alpha,
    rolling_sum_negative,
    rolling_sum_positive,
    safe_division,
)


class RSI(MomentumIndicator):
    """Relative Strength Index indicator."""

    def __init__(self):
        super().__init__(
            name="RSI",
            description="Relative Strength Index - momentum oscillator measuring speed and change of price movements",
        )

    def calculate(
        self,
        data: pl.DataFrame,
        column: str = "close",
        period: int = 14,
    ) -> pl.DataFrame:
        """
        Calculate Relative Strength Index.

        Args:
            data: DataFrame with OHLCV data
            column: Column to calculate RSI for
            period: Period for RSI calculation

        Returns:
            DataFrame with RSI column added

        Example:
            >>> rsi = RSI()
            >>> data_with_rsi = rsi.calculate(ohlcv_data, period=14)
            >>> print(data_with_rsi.columns)  # Now includes 'rsi_14'
        """
        self.validate_data(data, [column])
        self.validate_period(period, min_period=1)
        self.validate_data_length(data, period + 1)

        # Calculate price changes
        data_with_changes = data.with_columns(
            pl.col(column).diff().alias("price_change")
        )

        # Separate gains and losses
        data_with_gains_losses = data_with_changes.with_columns(
            [
                pl.when(pl.col("price_change") > 0)
                .then(pl.col("price_change"))
                .otherwise(0)
                .alias("gain"),
                pl.when(pl.col("price_change") < 0)
                .then(-pl.col("price_change"))
                .otherwise(0)
                .alias("loss"),
            ]
        )

        # Calculate average gains and losses using EMA (Wilder's smoothing)
        alpha = 1.0 / period  # Wilder's smoothing factor
        data_with_averages = data_with_gains_losses.with_columns(
            [
                pl.col("gain").ewm_mean(alpha=alpha, adjust=False).alias("avg_gain"),
                pl.col("loss").ewm_mean(alpha=alpha, adjust=False).alias("avg_loss"),
            ]
        )

        # Calculate RSI
        result = data_with_averages.with_columns(
            (
                100
                - (100 / (1 + safe_division(pl.col("avg_gain"), pl.col("avg_loss"))))
            ).alias(f"rsi_{period}")
        )

        # Remove intermediate columns
        return result.drop(["price_change", "gain", "loss", "avg_gain", "avg_loss"])


class MACD(MomentumIndicator):
    """Moving Average Convergence Divergence indicator."""

    def __init__(self):
        super().__init__(
            name="MACD",
            description="Moving Average Convergence Divergence - trend-following momentum indicator",
        )

    def calculate(
        self,
        data: pl.DataFrame,
        column: str = "close",
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
    ) -> pl.DataFrame:
        """
        Calculate Moving Average Convergence Divergence (MACD).

        Args:
            data: DataFrame with OHLCV data
            column: Column to calculate MACD for
            fast_period: Fast EMA period
            slow_period: Slow EMA period
            signal_period: Signal line EMA period

        Returns:
            DataFrame with MACD columns added

        Example:
            >>> macd = MACD()
            >>> data_with_macd = macd.calculate(ohlcv_data)
            >>> # Now includes macd, macd_signal, macd_histogram
        """
        self.validate_data(data, [column])
        self.validate_period(fast_period, min_period=1)
        self.validate_period(slow_period, min_period=1)
        self.validate_period(signal_period, min_period=1)

        if fast_period >= slow_period:
            raise ValueError("Fast period must be less than slow period")

        # Calculate fast and slow EMAs
        fast_alpha = ema_alpha(fast_period)
        slow_alpha = ema_alpha(slow_period)
        signal_alpha = ema_alpha(signal_period)

        # Calculate MACD line (fast EMA - slow EMA)
        result = data.with_columns(
            [
                pl.col(column).ewm_mean(alpha=fast_alpha).alias("ema_fast"),
                pl.col(column).ewm_mean(alpha=slow_alpha).alias("ema_slow"),
            ]
        ).with_columns((pl.col("ema_fast") - pl.col("ema_slow")).alias("macd"))

        # Calculate signal line (EMA of MACD)
        result = result.with_columns(
            pl.col("macd").ewm_mean(alpha=signal_alpha).alias("macd_signal")
        )

        # Calculate MACD histogram
        result = result.with_columns(
            (pl.col("macd") - pl.col("macd_signal")).alias("macd_histogram")
        )

        # Remove intermediate columns
        return result.drop(["ema_fast", "ema_slow"])


class STOCH(MomentumIndicator):
    """Stochastic Oscillator indicator."""

    def __init__(self):
        super().__init__(
            name="STOCH",
            description="Stochastic Oscillator - momentum indicator comparing closing price to price range",
        )

    def calculate(
        self,
        data: pl.DataFrame,
        high_column: str = "high",
        low_column: str = "low",
        close_column: str = "close",
        k_period: int = 14,
        d_period: int = 3,
    ) -> pl.DataFrame:
        """
        Calculate Stochastic Oscillator.

        Args:
            data: DataFrame with OHLCV data
            high_column: High price column
            low_column: Low price column
            close_column: Close price column
            k_period: %K period
            d_period: %D smoothing period

        Returns:
            DataFrame with Stochastic columns added

        Example:
            >>> stoch = STOCH()
            >>> data_with_stoch = stoch.calculate(ohlcv_data)
            >>> # Now includes stoch_k, stoch_d
        """
        required_cols = [high_column, low_column, close_column]
        self.validate_data(data, required_cols)
        self.validate_period(k_period, min_period=1)
        self.validate_period(d_period, min_period=1)
        self.validate_data_length(data, k_period)

        # Calculate %K
        result = data.with_columns(
            [
                pl.col(high_column)
                .rolling_max(window_size=k_period)
                .alias("highest_high"),
                pl.col(low_column)
                .rolling_min(window_size=k_period)
                .alias("lowest_low"),
            ]
        ).with_columns(
            (
                100
                * safe_division(
                    pl.col(close_column) - pl.col("lowest_low"),
                    pl.col("highest_high") - pl.col("lowest_low"),
                )
            ).alias(f"stoch_k_{k_period}")
        )

        # Calculate %D (SMA of %K)
        result = result.with_columns(
            pl.col(f"stoch_k_{k_period}")
            .rolling_mean(window_size=d_period)
            .alias(f"stoch_d_{d_period}")
        )

        # Remove intermediate columns
        return result.drop(["highest_high", "lowest_low"])


class WILLR(MomentumIndicator):
    """Williams %R indicator."""

    def __init__(self):
        super().__init__(
            name="WILLR",
            description="Williams %R - momentum indicator showing overbought/oversold levels",
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
        Calculate Williams %R.

        Args:
            data: DataFrame with OHLCV data
            high_column: High price column
            low_column: Low price column
            close_column: Close price column
            period: Lookback period

        Returns:
            DataFrame with Williams %R column added

        Example:
            >>> willr = WILLR()
            >>> data_with_wr = willr.calculate(ohlcv_data)
            >>> # Now includes williams_r_14
        """
        required_cols = [high_column, low_column, close_column]
        self.validate_data(data, required_cols)
        self.validate_period(period, min_period=1)
        self.validate_data_length(data, period)

        return (
            data.with_columns(
                [
                    pl.col(high_column)
                    .rolling_max(window_size=period)
                    .alias("highest_high"),
                    pl.col(low_column)
                    .rolling_min(window_size=period)
                    .alias("lowest_low"),
                ]
            )
            .with_columns(
                (
                    -100
                    * safe_division(
                        pl.col("highest_high") - pl.col(close_column),
                        pl.col("highest_high") - pl.col("lowest_low"),
                    )
                ).alias(f"williams_r_{period}")
            )
            .drop(["highest_high", "lowest_low"])
        )


class CCI(MomentumIndicator):
    """Commodity Channel Index indicator."""

    def __init__(self):
        super().__init__(
            name="CCI",
            description="Commodity Channel Index - momentum oscillator identifying cyclical trends",
        )

    def calculate(
        self,
        data: pl.DataFrame,
        high_column: str = "high",
        low_column: str = "low",
        close_column: str = "close",
        period: int = 20,
        constant: float = 0.015,
    ) -> pl.DataFrame:
        """
        Calculate Commodity Channel Index (CCI).

        Args:
            data: DataFrame with OHLCV data
            high_column: High price column
            low_column: Low price column
            close_column: Close price column
            period: CCI period
            constant: CCI constant (typically 0.015)

        Returns:
            DataFrame with CCI column added

        Example:
            >>> cci = CCI()
            >>> data_with_cci = cci.calculate(ohlcv_data)
            >>> # Now includes cci_20
        """
        required_cols = [high_column, low_column, close_column]
        self.validate_data(data, required_cols)
        self.validate_period(period, min_period=1)
        self.validate_data_length(data, period)

        if constant <= 0:
            raise ValueError("CCI constant must be positive")

        # Calculate Typical Price
        result = data.with_columns(
            (
                (pl.col(high_column) + pl.col(low_column) + pl.col(close_column)) / 3
            ).alias("typical_price")
        )

        # Calculate Simple Moving Average of Typical Price
        result = result.with_columns(
            pl.col("typical_price").rolling_mean(window_size=period).alias("sma_tp")
        )

        # Calculate Mean Deviation
        result = result.with_columns(
            (pl.col("typical_price") - pl.col("sma_tp"))
            .abs()
            .rolling_mean(window_size=period)
            .alias("mean_deviation")
        )

        # Calculate CCI
        result = result.with_columns(
            safe_division(
                pl.col("typical_price") - pl.col("sma_tp"),
                constant * pl.col("mean_deviation"),
            ).alias(f"cci_{period}")
        )

        # Remove intermediate columns
        return result.drop(["typical_price", "sma_tp", "mean_deviation"])


class ROC(MomentumIndicator):
    """Rate of Change indicator."""

    def __init__(self):
        super().__init__(
            name="ROC",
            description="Rate of Change - momentum indicator measuring percentage change in price",
        )

    def calculate(
        self,
        data: pl.DataFrame,
        column: str = "close",
        period: int = 10,
    ) -> pl.DataFrame:
        """
        Calculate Rate of Change.

        Args:
            data: DataFrame with OHLCV data
            column: Column to calculate ROC for
            period: Lookback period

        Returns:
            DataFrame with ROC column added
        """
        self.validate_data(data, [column])
        self.validate_period(period, min_period=1)
        self.validate_data_length(data, period + 1)

        return data.with_columns(
            (
                100
                * safe_division(
                    pl.col(column) - pl.col(column).shift(period),
                    pl.col(column).shift(period),
                )
            ).alias(f"roc_{period}")
        )


class MOM(MomentumIndicator):
    """Momentum indicator."""

    def __init__(self):
        super().__init__(
            name="MOM",
            description="Momentum - measures the amount of change in price over a specified time period",
        )

    def calculate(
        self,
        data: pl.DataFrame,
        column: str = "close",
        period: int = 10,
    ) -> pl.DataFrame:
        """
        Calculate Momentum.

        Args:
            data: DataFrame with OHLCV data
            column: Column to calculate momentum for
            period: Lookback period

        Returns:
            DataFrame with momentum column added
        """
        self.validate_data(data, [column])
        self.validate_period(period, min_period=1)
        self.validate_data_length(data, period + 1)

        return data.with_columns(
            (pl.col(column) - pl.col(column).shift(period)).alias(f"mom_{period}")
        )


class STOCHRSI(MomentumIndicator):
    """Stochastic RSI indicator."""

    def __init__(self):
        super().__init__(
            name="STOCHRSI",
            description="Stochastic RSI - applies Stochastic oscillator formula to RSI values",
        )

    def calculate(
        self,
        data: pl.DataFrame,
        column: str = "close",
        rsi_period: int = 14,
        stoch_period: int = 14,
        k_period: int = 3,
        d_period: int = 3,
    ) -> pl.DataFrame:
        """
        Calculate Stochastic RSI.

        Args:
            data: DataFrame with OHLCV data
            column: Column to calculate StochRSI for
            rsi_period: RSI calculation period
            stoch_period: Stochastic calculation period
            k_period: %K smoothing period
            d_period: %D smoothing period

        Returns:
            DataFrame with StochRSI columns added
        """
        self.validate_data(data, [column])
        self.validate_period(rsi_period, min_period=1)
        self.validate_period(stoch_period, min_period=1)
        self.validate_period(k_period, min_period=1)
        self.validate_period(d_period, min_period=1)

        # First calculate RSI
        rsi_indicator = RSI()
        data_with_rsi = rsi_indicator.calculate(data, column=column, period=rsi_period)
        rsi_col = f"rsi_{rsi_period}"

        # Apply Stochastic formula to RSI
        result = data_with_rsi.with_columns(
            [
                pl.col(rsi_col).rolling_max(window_size=stoch_period).alias("rsi_high"),
                pl.col(rsi_col).rolling_min(window_size=stoch_period).alias("rsi_low"),
            ]
        ).with_columns(
            (
                100
                * safe_division(
                    pl.col(rsi_col) - pl.col("rsi_low"),
                    pl.col("rsi_high") - pl.col("rsi_low"),
                )
            ).alias("stochrsi_raw")
        )

        # Smooth %K and %D
        result = result.with_columns(
            [
                pl.col("stochrsi_raw")
                .rolling_mean(window_size=k_period)
                .alias(f"stochrsi_k_{k_period}"),
            ]
        ).with_columns(
            pl.col(f"stochrsi_k_{k_period}")
            .rolling_mean(window_size=d_period)
            .alias(f"stochrsi_d_{d_period}")
        )

        # Remove intermediate columns
        return result.drop(["rsi_high", "rsi_low", "stochrsi_raw"])


# Convenience functions for backwards compatibility and TA-Lib style usage
def calculate_rsi(
    data: pl.DataFrame, column: str = "close", period: int = 14
) -> pl.DataFrame:
    """Calculate RSI (convenience function)."""
    return RSI().calculate(data, column=column, period=period)


def calculate_macd(
    data: pl.DataFrame,
    column: str = "close",
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> pl.DataFrame:
    """Calculate MACD (convenience function)."""
    return MACD().calculate(
        data,
        column=column,
        fast_period=fast_period,
        slow_period=slow_period,
        signal_period=signal_period,
    )


def calculate_stochastic(
    data: pl.DataFrame,
    high_column: str = "high",
    low_column: str = "low",
    close_column: str = "close",
    k_period: int = 14,
    d_period: int = 3,
) -> pl.DataFrame:
    """Calculate Stochastic (convenience function)."""
    return STOCH().calculate(
        data,
        high_column=high_column,
        low_column=low_column,
        close_column=close_column,
        k_period=k_period,
        d_period=d_period,
    )


def calculate_williams_r(
    data: pl.DataFrame,
    high_column: str = "high",
    low_column: str = "low",
    close_column: str = "close",
    period: int = 14,
) -> pl.DataFrame:
    """Calculate Williams %R (convenience function)."""
    return WILLR().calculate(
        data,
        high_column=high_column,
        low_column=low_column,
        close_column=close_column,
        period=period,
    )


def calculate_commodity_channel_index(
    data: pl.DataFrame,
    high_column: str = "high",
    low_column: str = "low",
    close_column: str = "close",
    period: int = 20,
    constant: float = 0.015,
) -> pl.DataFrame:
    """Calculate CCI (convenience function)."""
    return CCI().calculate(
        data,
        high_column=high_column,
        low_column=low_column,
        close_column=close_column,
        period=period,
        constant=constant,
    )
