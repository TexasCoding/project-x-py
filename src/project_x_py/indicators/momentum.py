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

        # Optimized RSI calculation with chained operations
        alpha = 1.0 / period  # Wilder's smoothing factor

        result = (
            data.with_columns(
                [
                    # Calculate price changes and immediately process gains/losses
                    pl.col(column).diff().alias("price_change")
                ]
            )
            .with_columns(
                [
                    # Separate gains and losses in single operation
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
            .with_columns(
                [
                    # Calculate averages and RSI in final chain
                    pl.col("gain")
                    .ewm_mean(alpha=alpha, adjust=False)
                    .fill_null(0)
                    .alias("avg_gain"),
                    pl.col("loss")
                    .ewm_mean(alpha=alpha, adjust=False)
                    .fill_null(0)
                    .alias("avg_loss"),
                ]
            )
            .with_columns(
                [
                    # Calculate RSI with safe division
                    (
                        100
                        - (
                            100
                            / (
                                1
                                + safe_division(pl.col("avg_gain"), pl.col("avg_loss"))
                            )
                        )
                    ).alias(f"rsi_{period}")
                ]
            )
            .drop(["price_change", "gain", "loss", "avg_gain", "avg_loss"])
        )

        return result


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


# NEW MOMENTUM INDICATORS TO MATCH TA-LIB


class ADX(MomentumIndicator):
    """Average Directional Movement Index indicator."""

    def __init__(self):
        super().__init__(
            name="ADX",
            description="Average Directional Movement Index - measures trend strength regardless of direction",
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
        Calculate ADX, +DI, and -DI.

        Args:
            data: DataFrame with OHLCV data
            high_column: High price column
            low_column: Low price column
            close_column: Close price column
            period: Smoothing period

        Returns:
            DataFrame with ADX, +DI, -DI columns added
        """
        required_cols = [high_column, low_column, close_column]
        self.validate_data(data, required_cols)
        self.validate_period(period, min_period=1)
        self.validate_data_length(data, period + 1)

        alpha = 1.0 / period

        # Calculate True Range and Directional Movement
        result = data.with_columns(
            [
                # True Range components
                (pl.col(high_column) - pl.col(low_column)).alias("h_l"),
                (pl.col(high_column) - pl.col(close_column).shift(1))
                .abs()
                .alias("h_c"),
                (pl.col(low_column) - pl.col(close_column).shift(1)).abs().alias("l_c"),
                # Directional Movement
                (pl.col(high_column) - pl.col(high_column).shift(1)).alias("high_diff"),
                (pl.col(low_column).shift(1) - pl.col(low_column)).alias("low_diff"),
            ]
        ).with_columns(
            [
                # True Range
                pl.max_horizontal(["h_l", "h_c", "l_c"]).alias("tr"),
                # Plus and Minus DM
                pl.when(
                    (pl.col("high_diff") > pl.col("low_diff"))
                    & (pl.col("high_diff") > 0)
                )
                .then(pl.col("high_diff"))
                .otherwise(0)
                .alias("plus_dm"),
                pl.when(
                    (pl.col("low_diff") > pl.col("high_diff"))
                    & (pl.col("low_diff") > 0)
                )
                .then(pl.col("low_diff"))
                .otherwise(0)
                .alias("minus_dm"),
            ]
        )

        # Smooth TR, +DM, -DM using Wilder's smoothing
        result = result.with_columns(
            [
                pl.col("tr").ewm_mean(alpha=alpha, adjust=False).alias("atr"),
                pl.col("plus_dm")
                .ewm_mean(alpha=alpha, adjust=False)
                .alias("plus_dm_smooth"),
                pl.col("minus_dm")
                .ewm_mean(alpha=alpha, adjust=False)
                .alias("minus_dm_smooth"),
            ]
        )

        # Calculate +DI and -DI
        result = result.with_columns(
            [
                (100 * safe_division(pl.col("plus_dm_smooth"), pl.col("atr"))).alias(
                    f"plus_di_{period}"
                ),
                (100 * safe_division(pl.col("minus_dm_smooth"), pl.col("atr"))).alias(
                    f"minus_di_{period}"
                ),
            ]
        )

        # Calculate DX and ADX
        result = result.with_columns(
            (
                100
                * safe_division(
                    (pl.col(f"plus_di_{period}") - pl.col(f"minus_di_{period}")).abs(),
                    pl.col(f"plus_di_{period}") + pl.col(f"minus_di_{period}"),
                )
            ).alias("dx")
        ).with_columns(
            pl.col("dx").ewm_mean(alpha=alpha, adjust=False).alias(f"adx_{period}")
        )

        # Clean up intermediate columns
        return result.drop(
            [
                "h_l",
                "h_c",
                "l_c",
                "high_diff",
                "low_diff",
                "tr",
                "plus_dm",
                "minus_dm",
                "atr",
                "plus_dm_smooth",
                "minus_dm_smooth",
                "dx",
            ]
        )


class ADXR(MomentumIndicator):
    """Average Directional Movement Index Rating indicator."""

    def __init__(self):
        super().__init__(
            name="ADXR",
            description="Average Directional Movement Index Rating - smoothed version of ADX",
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
        Calculate ADXR.

        Args:
            data: DataFrame with OHLCV data
            high_column: High price column
            low_column: Low price column
            close_column: Close price column
            period: Period for calculation

        Returns:
            DataFrame with ADXR column added
        """
        # First calculate ADX
        adx_indicator = ADX()
        data_with_adx = adx_indicator.calculate(
            data, high_column, low_column, close_column, period
        )

        adx_col = f"adx_{period}"

        # ADXR is the average of current ADX and ADX from period bars ago
        return data_with_adx.with_columns(
            ((pl.col(adx_col) + pl.col(adx_col).shift(period)) / 2).alias(
                f"adxr_{period}"
            )
        )


class APO(MomentumIndicator):
    """Absolute Price Oscillator indicator."""

    def __init__(self):
        super().__init__(
            name="APO",
            description="Absolute Price Oscillator - difference between fast and slow EMA",
        )

    def calculate(
        self,
        data: pl.DataFrame,
        column: str = "close",
        fast_period: int = 12,
        slow_period: int = 26,
        ma_type: str = "ema",
    ) -> pl.DataFrame:
        """
        Calculate APO.

        Args:
            data: DataFrame with OHLCV data
            column: Column to calculate APO for
            fast_period: Fast MA period
            slow_period: Slow MA period
            ma_type: Type of moving average (ema, sma)

        Returns:
            DataFrame with APO column added
        """
        self.validate_data(data, [column])
        self.validate_period(fast_period, min_period=1)
        self.validate_period(slow_period, min_period=1)

        if fast_period >= slow_period:
            raise ValueError("Fast period must be less than slow period")

        if ma_type.lower() == "ema":
            fast_alpha = ema_alpha(fast_period)
            slow_alpha = ema_alpha(slow_period)

            result = data.with_columns(
                [
                    pl.col(column).ewm_mean(alpha=fast_alpha).alias("fast_ma"),
                    pl.col(column).ewm_mean(alpha=slow_alpha).alias("slow_ma"),
                ]
            )
        else:  # SMA
            result = data.with_columns(
                [
                    pl.col(column)
                    .rolling_mean(window_size=fast_period)
                    .alias("fast_ma"),
                    pl.col(column)
                    .rolling_mean(window_size=slow_period)
                    .alias("slow_ma"),
                ]
            )

        result = result.with_columns(
            (pl.col("fast_ma") - pl.col("slow_ma")).alias(
                f"apo_{fast_period}_{slow_period}"
            )
        )

        return result.drop(["fast_ma", "slow_ma"])


class AROON(MomentumIndicator):
    """Aroon indicator."""

    def __init__(self):
        super().__init__(
            name="AROON",
            description="Aroon - identifies when trends are likely to change direction",
        )

    def calculate(
        self,
        data: pl.DataFrame,
        high_column: str = "high",
        low_column: str = "low",
        period: int = 14,
    ) -> pl.DataFrame:
        """
        Calculate Aroon Up and Aroon Down.

        Args:
            data: DataFrame with OHLCV data
            high_column: High price column
            low_column: Low price column
            period: Lookback period

        Returns:
            DataFrame with Aroon Up and Aroon Down columns added
        """
        required_cols = [high_column, low_column]
        self.validate_data(data, required_cols)
        self.validate_period(period, min_period=1)
        self.validate_data_length(data, period)

        # Calculate periods since highest high and lowest low
        result = data.with_columns(
            [
                pl.col(high_column)
                .rolling_max(window_size=period)
                .alias("highest_high"),
                pl.col(low_column).rolling_min(window_size=period).alias("lowest_low"),
            ]
        )

        # Calculate periods since highest high and lowest low
        # Aroon Up = ((period - periods since highest high) / period) * 100
        # Aroon Down = ((period - periods since lowest low) / period) * 100

        # Create a helper function to find periods since extreme values
        def periods_since_extreme(data_with_rolling, col_name, extreme_col, period_val):
            # For each row, find how many periods ago the extreme occurred
            result_data = data_with_rolling.with_row_index("idx")

            # Create rolling window indices for vectorized calculation
            indices = []
            for i in range(len(result_data)):
                start_idx = max(0, i - period_val + 1)
                window_data = result_data[start_idx : i + 1]
                if len(window_data) > 0:
                    if extreme_col == "highest_high":
                        extreme_idx = window_data[col_name].arg_max()
                    else:  # lowest_low
                        extreme_idx = window_data[col_name].arg_min()
                    periods_since = len(window_data) - 1 - extreme_idx
                    indices.append(periods_since)
                else:
                    indices.append(period_val - 1)

            return pl.Series(indices)

        # Calculate Aroon Up and Down using rolling_map
        def aroon_up_calc(s):
            if len(s) >= period:
                max_idx = s.arg_max()
                if max_idx is not None:
                    return 100.0 * (period - (len(s) - 1 - max_idx)) / period
            return None

        def aroon_down_calc(s):
            if len(s) >= period:
                min_idx = s.arg_min()
                if min_idx is not None:
                    return 100.0 * (period - (len(s) - 1 - min_idx)) / period
            return None

        result = result.with_columns(
            [
                # Aroon Up: periods since highest high
                pl.col(high_column)
                .rolling_map(aroon_up_calc, window_size=period)
                .alias(f"aroon_up_{period}"),
                # Aroon Down: periods since lowest low
                pl.col(low_column)
                .rolling_map(aroon_down_calc, window_size=period)
                .alias(f"aroon_down_{period}"),
            ]
        )

        return result.drop(["highest_high", "lowest_low"])


class AROONOSC(MomentumIndicator):
    """Aroon Oscillator indicator."""

    def __init__(self):
        super().__init__(
            name="AROONOSC",
            description="Aroon Oscillator - difference between Aroon Up and Aroon Down",
        )

    def calculate(
        self,
        data: pl.DataFrame,
        high_column: str = "high",
        low_column: str = "low",
        period: int = 14,
    ) -> pl.DataFrame:
        """
        Calculate Aroon Oscillator.

        Args:
            data: DataFrame with OHLCV data
            high_column: High price column
            low_column: Low price column
            period: Lookback period

        Returns:
            DataFrame with Aroon Oscillator column added
        """
        # Calculate Aroon first
        aroon_indicator = AROON()
        data_with_aroon = aroon_indicator.calculate(
            data, high_column, low_column, period
        )

        # Calculate oscillator as difference
        return data_with_aroon.with_columns(
            (pl.col(f"aroon_up_{period}") - pl.col(f"aroon_down_{period}")).alias(
                f"aroon_osc_{period}"
            )
        )


class BOP(MomentumIndicator):
    """Balance of Power indicator."""

    def __init__(self):
        super().__init__(
            name="BOP",
            description="Balance of Power - measures buying vs selling pressure",
        )

    def calculate(
        self,
        data: pl.DataFrame,
        high_column: str = "high",
        low_column: str = "low",
        open_column: str = "open",
        close_column: str = "close",
    ) -> pl.DataFrame:
        """
        Calculate Balance of Power.

        Args:
            data: DataFrame with OHLCV data
            high_column: High price column
            low_column: Low price column
            open_column: Open price column
            close_column: Close price column

        Returns:
            DataFrame with BOP column added
        """
        required_cols = [high_column, low_column, open_column, close_column]
        self.validate_data(data, required_cols)

        return data.with_columns(
            safe_division(
                pl.col(close_column) - pl.col(open_column),
                pl.col(high_column) - pl.col(low_column),
            ).alias("bop")
        )


class CMO(MomentumIndicator):
    """Chande Momentum Oscillator indicator."""

    def __init__(self):
        super().__init__(
            name="CMO",
            description="Chande Momentum Oscillator - momentum indicator without smoothing",
        )

    def calculate(
        self,
        data: pl.DataFrame,
        column: str = "close",
        period: int = 14,
    ) -> pl.DataFrame:
        """
        Calculate Chande Momentum Oscillator.

        Args:
            data: DataFrame with OHLCV data
            column: Column to calculate CMO for
            period: Period for calculation

        Returns:
            DataFrame with CMO column added
        """
        self.validate_data(data, [column])
        self.validate_period(period, min_period=1)
        self.validate_data_length(data, period + 1)

        result = (
            data.with_columns(pl.col(column).diff().alias("price_change"))
            .with_columns(
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
            .with_columns(
                [
                    pl.col("gain").rolling_sum(window_size=period).alias("sum_gains"),
                    pl.col("loss").rolling_sum(window_size=period).alias("sum_losses"),
                ]
            )
            .with_columns(
                (
                    100
                    * safe_division(
                        pl.col("sum_gains") - pl.col("sum_losses"),
                        pl.col("sum_gains") + pl.col("sum_losses"),
                    )
                ).alias(f"cmo_{period}")
            )
        )

        return result.drop(["price_change", "gain", "loss", "sum_gains", "sum_losses"])


class DX(MomentumIndicator):
    """Directional Movement Index indicator."""

    def __init__(self):
        super().__init__(
            name="DX",
            description="Directional Movement Index - measures directional movement",
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
        Calculate DX.

        Args:
            data: DataFrame with OHLCV data
            high_column: High price column
            low_column: Low price column
            close_column: Close price column
            period: Period for calculation

        Returns:
            DataFrame with DX column added
        """
        # Calculate ADX first (which includes DX calculation)
        adx_indicator = ADX()
        data_with_adx = adx_indicator.calculate(
            data, high_column, low_column, close_column, period
        )

        # DX was calculated as intermediate step in ADX, need to recalculate
        result = data_with_adx.with_columns(
            (
                100
                * safe_division(
                    (pl.col(f"plus_di_{period}") - pl.col(f"minus_di_{period}")).abs(),
                    pl.col(f"plus_di_{period}") + pl.col(f"minus_di_{period}"),
                )
            ).alias(f"dx_{period}")
        )

        return result


class MACDEXT(MomentumIndicator):
    """MACD with controllable MA type indicator."""

    def __init__(self):
        super().__init__(
            name="MACDEXT",
            description="MACD with controllable MA type - extended MACD with different MA types",
        )

    def calculate(
        self,
        data: pl.DataFrame,
        column: str = "close",
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
        fast_ma_type: str = "ema",
        slow_ma_type: str = "ema",
        signal_ma_type: str = "ema",
    ) -> pl.DataFrame:
        """
        Calculate MACD with controllable MA types.

        Args:
            data: DataFrame with OHLCV data
            column: Column to calculate MACD for
            fast_period: Fast MA period
            slow_period: Slow MA period
            signal_period: Signal line MA period
            fast_ma_type: Fast MA type (ema, sma)
            slow_ma_type: Slow MA type (ema, sma)
            signal_ma_type: Signal MA type (ema, sma)

        Returns:
            DataFrame with MACD columns added
        """
        self.validate_data(data, [column])
        self.validate_period(fast_period, min_period=1)
        self.validate_period(slow_period, min_period=1)
        self.validate_period(signal_period, min_period=1)

        if fast_period >= slow_period:
            raise ValueError("Fast period must be less than slow period")

        # Calculate fast MA
        if fast_ma_type.lower() == "ema":
            fast_alpha = ema_alpha(fast_period)
            result = data.with_columns(
                pl.col(column).ewm_mean(alpha=fast_alpha).alias("fast_ma")
            )
        else:  # SMA
            result = data.with_columns(
                pl.col(column).rolling_mean(window_size=fast_period).alias("fast_ma")
            )

        # Calculate slow MA
        if slow_ma_type.lower() == "ema":
            slow_alpha = ema_alpha(slow_period)
            result = result.with_columns(
                pl.col(column).ewm_mean(alpha=slow_alpha).alias("slow_ma")
            )
        else:  # SMA
            result = result.with_columns(
                pl.col(column).rolling_mean(window_size=slow_period).alias("slow_ma")
            )

        # Calculate MACD line
        result = result.with_columns(
            (pl.col("fast_ma") - pl.col("slow_ma")).alias("macdext")
        )

        # Calculate signal line
        if signal_ma_type.lower() == "ema":
            signal_alpha = ema_alpha(signal_period)
            result = result.with_columns(
                pl.col("macdext").ewm_mean(alpha=signal_alpha).alias("macdext_signal")
            )
        else:  # SMA
            result = result.with_columns(
                pl.col("macdext")
                .rolling_mean(window_size=signal_period)
                .alias("macdext_signal")
            )

        # Calculate histogram
        result = result.with_columns(
            (pl.col("macdext") - pl.col("macdext_signal")).alias("macdext_histogram")
        )

        return result.drop(["fast_ma", "slow_ma"])


class MACDFIX(MomentumIndicator):
    """MACD Fix 12/26 indicator."""

    def __init__(self):
        super().__init__(
            name="MACDFIX",
            description="MACD Fix 12/26 - MACD with fixed 12/26 periods",
        )

    def calculate(
        self,
        data: pl.DataFrame,
        column: str = "close",
        signal_period: int = 9,
    ) -> pl.DataFrame:
        """
        Calculate MACD with fixed 12/26 periods.

        Args:
            data: DataFrame with OHLCV data
            column: Column to calculate MACD for
            signal_period: Signal line period

        Returns:
            DataFrame with MACD Fix columns added
        """
        # Use standard MACD with fixed 12/26 periods
        macd_indicator = MACD()
        return macd_indicator.calculate(
            data,
            column=column,
            fast_period=12,
            slow_period=26,
            signal_period=signal_period,
        ).rename(
            {
                "macd": "macdfix",
                "macd_signal": "macdfix_signal",
                "macd_histogram": "macdfix_histogram",
            }
        )


class MFI(MomentumIndicator):
    """Money Flow Index indicator."""

    def __init__(self):
        super().__init__(
            name="MFI",
            description="Money Flow Index - volume-weighted RSI",
        )

    def calculate(
        self,
        data: pl.DataFrame,
        high_column: str = "high",
        low_column: str = "low",
        close_column: str = "close",
        volume_column: str = "volume",
        period: int = 14,
    ) -> pl.DataFrame:
        """
        Calculate Money Flow Index.

        Args:
            data: DataFrame with OHLCV data
            high_column: High price column
            low_column: Low price column
            close_column: Close price column
            volume_column: Volume column
            period: Period for calculation

        Returns:
            DataFrame with MFI column added
        """
        required_cols = [high_column, low_column, close_column, volume_column]
        self.validate_data(data, required_cols)
        self.validate_period(period, min_period=1)
        self.validate_data_length(data, period + 1)

        # Calculate typical price and raw money flow
        result = (
            data.with_columns(
                [
                    (
                        (
                            pl.col(high_column)
                            + pl.col(low_column)
                            + pl.col(close_column)
                        )
                        / 3
                    ).alias("typical_price"),
                ]
            )
            .with_columns(
                [
                    (pl.col("typical_price") * pl.col(volume_column)).alias(
                        "raw_money_flow"
                    ),
                    pl.col("typical_price").diff().alias("price_change"),
                ]
            )
            .with_columns(
                [
                    pl.when(pl.col("price_change") > 0)
                    .then(pl.col("raw_money_flow"))
                    .otherwise(0)
                    .alias("positive_money_flow"),
                    pl.when(pl.col("price_change") < 0)
                    .then(pl.col("raw_money_flow"))
                    .otherwise(0)
                    .alias("negative_money_flow"),
                ]
            )
            .with_columns(
                [
                    pl.col("positive_money_flow")
                    .rolling_sum(window_size=period)
                    .alias("positive_mf_sum"),
                    pl.col("negative_money_flow")
                    .rolling_sum(window_size=period)
                    .alias("negative_mf_sum"),
                ]
            )
            .with_columns(
                (
                    100
                    - (
                        100
                        / (
                            1
                            + safe_division(
                                pl.col("positive_mf_sum"), pl.col("negative_mf_sum")
                            )
                        )
                    )
                ).alias(f"mfi_{period}")
            )
        )

        return result.drop(
            [
                "typical_price",
                "raw_money_flow",
                "price_change",
                "positive_money_flow",
                "negative_money_flow",
                "positive_mf_sum",
                "negative_mf_sum",
            ]
        )


class PLUS_DI(MomentumIndicator):
    """Plus Directional Indicator."""

    def __init__(self):
        super().__init__(
            name="PLUS_DI",
            description="Plus Directional Indicator - measures positive directional movement",
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
        Calculate +DI.

        Args:
            data: DataFrame with OHLCV data
            high_column: High price column
            low_column: Low price column
            close_column: Close price column
            period: Period for calculation

        Returns:
            DataFrame with +DI column added
        """
        # Calculate ADX first (which includes +DI)
        adx_indicator = ADX()
        return adx_indicator.calculate(
            data, high_column, low_column, close_column, period
        )


class MINUS_DI(MomentumIndicator):
    """Minus Directional Indicator."""

    def __init__(self):
        super().__init__(
            name="MINUS_DI",
            description="Minus Directional Indicator - measures negative directional movement",
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
        Calculate -DI.

        Args:
            data: DataFrame with OHLCV data
            high_column: High price column
            low_column: Low price column
            close_column: Close price column
            period: Period for calculation

        Returns:
            DataFrame with -DI column added
        """
        # Calculate ADX first (which includes -DI)
        adx_indicator = ADX()
        return adx_indicator.calculate(
            data, high_column, low_column, close_column, period
        )


class PLUS_DM(MomentumIndicator):
    """Plus Directional Movement."""

    def __init__(self):
        super().__init__(
            name="PLUS_DM",
            description="Plus Directional Movement - raw positive directional movement",
        )

    def calculate(
        self,
        data: pl.DataFrame,
        high_column: str = "high",
        low_column: str = "low",
        period: int = 14,
    ) -> pl.DataFrame:
        """
        Calculate +DM.

        Args:
            data: DataFrame with OHLCV data
            high_column: High price column
            low_column: Low price column
            period: Period for smoothing

        Returns:
            DataFrame with +DM column added
        """
        required_cols = [high_column, low_column]
        self.validate_data(data, required_cols)
        self.validate_period(period, min_period=1)
        self.validate_data_length(data, period + 1)

        alpha = 1.0 / period

        result = (
            data.with_columns(
                [
                    (pl.col(high_column) - pl.col(high_column).shift(1)).alias(
                        "high_diff"
                    ),
                    (pl.col(low_column).shift(1) - pl.col(low_column)).alias(
                        "low_diff"
                    ),
                ]
            )
            .with_columns(
                pl.when(
                    (pl.col("high_diff") > pl.col("low_diff"))
                    & (pl.col("high_diff") > 0)
                )
                .then(pl.col("high_diff"))
                .otherwise(0)
                .alias("plus_dm_raw")
            )
            .with_columns(
                pl.col("plus_dm_raw")
                .ewm_mean(alpha=alpha, adjust=False)
                .alias(f"plus_dm_{period}")
            )
        )

        return result.drop(["high_diff", "low_diff", "plus_dm_raw"])


class MINUS_DM(MomentumIndicator):
    """Minus Directional Movement."""

    def __init__(self):
        super().__init__(
            name="MINUS_DM",
            description="Minus Directional Movement - raw negative directional movement",
        )

    def calculate(
        self,
        data: pl.DataFrame,
        high_column: str = "high",
        low_column: str = "low",
        period: int = 14,
    ) -> pl.DataFrame:
        """
        Calculate -DM.

        Args:
            data: DataFrame with OHLCV data
            high_column: High price column
            low_column: Low price column
            period: Period for smoothing

        Returns:
            DataFrame with -DM column added
        """
        required_cols = [high_column, low_column]
        self.validate_data(data, required_cols)
        self.validate_period(period, min_period=1)
        self.validate_data_length(data, period + 1)

        alpha = 1.0 / period

        result = (
            data.with_columns(
                [
                    (pl.col(high_column) - pl.col(high_column).shift(1)).alias(
                        "high_diff"
                    ),
                    (pl.col(low_column).shift(1) - pl.col(low_column)).alias(
                        "low_diff"
                    ),
                ]
            )
            .with_columns(
                pl.when(
                    (pl.col("low_diff") > pl.col("high_diff"))
                    & (pl.col("low_diff") > 0)
                )
                .then(pl.col("low_diff"))
                .otherwise(0)
                .alias("minus_dm_raw")
            )
            .with_columns(
                pl.col("minus_dm_raw")
                .ewm_mean(alpha=alpha, adjust=False)
                .alias(f"minus_dm_{period}")
            )
        )

        return result.drop(["high_diff", "low_diff", "minus_dm_raw"])


class PPO(MomentumIndicator):
    """Percentage Price Oscillator indicator."""

    def __init__(self):
        super().__init__(
            name="PPO",
            description="Percentage Price Oscillator - percentage difference between fast and slow MA",
        )

    def calculate(
        self,
        data: pl.DataFrame,
        column: str = "close",
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
        ma_type: str = "ema",
    ) -> pl.DataFrame:
        """
        Calculate PPO.

        Args:
            data: DataFrame with OHLCV data
            column: Column to calculate PPO for
            fast_period: Fast MA period
            slow_period: Slow MA period
            signal_period: Signal line period
            ma_type: Type of moving average (ema, sma)

        Returns:
            DataFrame with PPO columns added
        """
        self.validate_data(data, [column])
        self.validate_period(fast_period, min_period=1)
        self.validate_period(slow_period, min_period=1)
        self.validate_period(signal_period, min_period=1)

        if fast_period >= slow_period:
            raise ValueError("Fast period must be less than slow period")

        if ma_type.lower() == "ema":
            fast_alpha = ema_alpha(fast_period)
            slow_alpha = ema_alpha(slow_period)
            signal_alpha = ema_alpha(signal_period)

            result = data.with_columns(
                [
                    pl.col(column).ewm_mean(alpha=fast_alpha).alias("fast_ma"),
                    pl.col(column).ewm_mean(alpha=slow_alpha).alias("slow_ma"),
                ]
            )
        else:  # SMA
            result = data.with_columns(
                [
                    pl.col(column)
                    .rolling_mean(window_size=fast_period)
                    .alias("fast_ma"),
                    pl.col(column)
                    .rolling_mean(window_size=slow_period)
                    .alias("slow_ma"),
                ]
            )

        # Calculate PPO as percentage
        result = result.with_columns(
            (
                100
                * safe_division(
                    pl.col("fast_ma") - pl.col("slow_ma"), pl.col("slow_ma")
                )
            ).alias("ppo")
        )

        # Calculate signal line
        if ma_type.lower() == "ema":
            result = result.with_columns(
                pl.col("ppo").ewm_mean(alpha=signal_alpha).alias("ppo_signal")
            )
        else:
            result = result.with_columns(
                pl.col("ppo")
                .rolling_mean(window_size=signal_period)
                .alias("ppo_signal")
            )

        # Calculate histogram
        result = result.with_columns(
            (pl.col("ppo") - pl.col("ppo_signal")).alias("ppo_histogram")
        )

        return result.drop(["fast_ma", "slow_ma"])


class ROCP(MomentumIndicator):
    """Rate of Change Percentage indicator."""

    def __init__(self):
        super().__init__(
            name="ROCP",
            description="Rate of Change Percentage - (price-prevPrice)/prevPrice",
        )

    def calculate(
        self,
        data: pl.DataFrame,
        column: str = "close",
        period: int = 10,
    ) -> pl.DataFrame:
        """
        Calculate Rate of Change Percentage.

        Args:
            data: DataFrame with OHLCV data
            column: Column to calculate ROCP for
            period: Lookback period

        Returns:
            DataFrame with ROCP column added
        """
        self.validate_data(data, [column])
        self.validate_period(period, min_period=1)
        self.validate_data_length(data, period + 1)

        return data.with_columns(
            safe_division(
                pl.col(column) - pl.col(column).shift(period),
                pl.col(column).shift(period),
            ).alias(f"rocp_{period}")
        )


class ROCR(MomentumIndicator):
    """Rate of Change Ratio indicator."""

    def __init__(self):
        super().__init__(
            name="ROCR",
            description="Rate of Change Ratio - price/prevPrice",
        )

    def calculate(
        self,
        data: pl.DataFrame,
        column: str = "close",
        period: int = 10,
    ) -> pl.DataFrame:
        """
        Calculate Rate of Change Ratio.

        Args:
            data: DataFrame with OHLCV data
            column: Column to calculate ROCR for
            period: Lookback period

        Returns:
            DataFrame with ROCR column added
        """
        self.validate_data(data, [column])
        self.validate_period(period, min_period=1)
        self.validate_data_length(data, period + 1)

        return data.with_columns(
            safe_division(
                pl.col(column),
                pl.col(column).shift(period),
            ).alias(f"rocr_{period}")
        )


class ROCR100(MomentumIndicator):
    """Rate of Change Ratio 100 scale indicator."""

    def __init__(self):
        super().__init__(
            name="ROCR100",
            description="Rate of Change Ratio 100 scale - (price/prevPrice)*100",
        )

    def calculate(
        self,
        data: pl.DataFrame,
        column: str = "close",
        period: int = 10,
    ) -> pl.DataFrame:
        """
        Calculate Rate of Change Ratio 100 scale.

        Args:
            data: DataFrame with OHLCV data
            column: Column to calculate ROCR100 for
            period: Lookback period

        Returns:
            DataFrame with ROCR100 column added
        """
        self.validate_data(data, [column])
        self.validate_period(period, min_period=1)
        self.validate_data_length(data, period + 1)

        return data.with_columns(
            (
                100
                * safe_division(
                    pl.col(column),
                    pl.col(column).shift(period),
                )
            ).alias(f"rocr100_{period}")
        )


class STOCHF(MomentumIndicator):
    """Stochastic Fast indicator."""

    def __init__(self):
        super().__init__(
            name="STOCHF",
            description="Stochastic Fast - fast stochastic without smoothing",
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
        Calculate Fast Stochastic.

        Args:
            data: DataFrame with OHLCV data
            high_column: High price column
            low_column: Low price column
            close_column: Close price column
            k_period: %K period
            d_period: %D period

        Returns:
            DataFrame with Fast Stochastic columns added
        """
        required_cols = [high_column, low_column, close_column]
        self.validate_data(data, required_cols)
        self.validate_period(k_period, min_period=1)
        self.validate_period(d_period, min_period=1)
        self.validate_data_length(data, k_period)

        # Calculate raw %K (no smoothing)
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
            ).alias(f"stochf_k_{k_period}")
        )

        # Calculate %D as SMA of %K
        result = result.with_columns(
            pl.col(f"stochf_k_{k_period}")
            .rolling_mean(window_size=d_period)
            .alias(f"stochf_d_{d_period}")
        )

        return result.drop(["highest_high", "lowest_low"])


class TRIX(MomentumIndicator):
    """TRIX indicator."""

    def __init__(self):
        super().__init__(
            name="TRIX",
            description="TRIX - 1-day Rate-Of-Change of a Triple Smooth EMA",
        )

    def calculate(
        self,
        data: pl.DataFrame,
        column: str = "close",
        period: int = 14,
    ) -> pl.DataFrame:
        """
        Calculate TRIX.

        Args:
            data: DataFrame with OHLCV data
            column: Column to calculate TRIX for
            period: Period for EMA smoothing

        Returns:
            DataFrame with TRIX column added
        """
        self.validate_data(data, [column])
        self.validate_period(period, min_period=1)
        self.validate_data_length(data, period * 3 + 1)

        alpha = ema_alpha(period)

        # Calculate triple smoothed EMA
        result = (
            data.with_columns(pl.col(column).ewm_mean(alpha=alpha).alias("ema1"))
            .with_columns(pl.col("ema1").ewm_mean(alpha=alpha).alias("ema2"))
            .with_columns(pl.col("ema2").ewm_mean(alpha=alpha).alias("ema3"))
        )

        # Calculate 1-day rate of change of triple EMA
        result = result.with_columns(
            (
                10000
                * safe_division(
                    pl.col("ema3") - pl.col("ema3").shift(1),
                    pl.col("ema3").shift(1),
                )
            ).alias(f"trix_{period}")
        )

        return result.drop(["ema1", "ema2", "ema3"])


class ULTOSC(MomentumIndicator):
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
            period1: Short period
            period2: Medium period
            period3: Long period

        Returns:
            DataFrame with Ultimate Oscillator column added
        """
        required_cols = [high_column, low_column, close_column]
        self.validate_data(data, required_cols)
        self.validate_period(period1, min_period=1)
        self.validate_period(period2, min_period=1)
        self.validate_period(period3, min_period=1)
        self.validate_data_length(data, period3 + 1)

        if not (period1 < period2 < period3):
            raise ValueError(
                "Periods must be in ascending order: period1 < period2 < period3"
            )

        # Calculate True Range and Buying Pressure
        result = data.with_columns(
            [
                # True Range components
                (pl.col(high_column) - pl.col(low_column)).alias("h_l"),
                (pl.col(high_column) - pl.col(close_column).shift(1))
                .abs()
                .alias("h_c"),
                (pl.col(low_column) - pl.col(close_column).shift(1)).abs().alias("l_c"),
                # Buying Pressure
                (
                    pl.col(close_column)
                    - pl.min_horizontal(
                        [pl.col(low_column), pl.col(close_column).shift(1)]
                    )
                ).alias("bp"),
            ]
        ).with_columns(
            # True Range
            pl.max_horizontal(["h_l", "h_c", "l_c"]).alias("tr")
        )

        # Calculate averages for each period
        result = result.with_columns(
            [
                pl.col("bp").rolling_sum(window_size=period1).alias("bp_sum1"),
                pl.col("tr").rolling_sum(window_size=period1).alias("tr_sum1"),
                pl.col("bp").rolling_sum(window_size=period2).alias("bp_sum2"),
                pl.col("tr").rolling_sum(window_size=period2).alias("tr_sum2"),
                pl.col("bp").rolling_sum(window_size=period3).alias("bp_sum3"),
                pl.col("tr").rolling_sum(window_size=period3).alias("tr_sum3"),
            ]
        ).with_columns(
            [
                safe_division(pl.col("bp_sum1"), pl.col("tr_sum1")).alias("avg1"),
                safe_division(pl.col("bp_sum2"), pl.col("tr_sum2")).alias("avg2"),
                safe_division(pl.col("bp_sum3"), pl.col("tr_sum3")).alias("avg3"),
            ]
        )

        # Calculate Ultimate Oscillator
        result = result.with_columns(
            (
                100 * (4 * pl.col("avg1") + 2 * pl.col("avg2") + pl.col("avg3")) / 7
            ).alias(f"ultosc_{period1}_{period2}_{period3}")
        )

        # Clean up intermediate columns
        return result.drop(
            [
                "h_l",
                "h_c",
                "l_c",
                "bp",
                "tr",
                "bp_sum1",
                "tr_sum1",
                "bp_sum2",
                "tr_sum2",
                "bp_sum3",
                "tr_sum3",
                "avg1",
                "avg2",
                "avg3",
            ]
        )


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


def calculate_aroon(
    data: pl.DataFrame,
    high_column: str = "high",
    low_column: str = "low",
    period: int = 14,
) -> pl.DataFrame:
    """Calculate Aroon (convenience function)."""
    return AROON().calculate(
        data,
        high_column=high_column,
        low_column=low_column,
        period=period,
    )


def calculate_money_flow_index(
    data: pl.DataFrame,
    high_column: str = "high",
    low_column: str = "low",
    close_column: str = "close",
    volume_column: str = "volume",
    period: int = 14,
) -> pl.DataFrame:
    """Calculate MFI (convenience function)."""
    return MFI().calculate(
        data,
        high_column=high_column,
        low_column=low_column,
        close_column=close_column,
        volume_column=volume_column,
        period=period,
    )


def calculate_ppo(
    data: pl.DataFrame,
    column: str = "close",
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> pl.DataFrame:
    """Calculate PPO (convenience function)."""
    return PPO().calculate(
        data,
        column=column,
        fast_period=fast_period,
        slow_period=slow_period,
        signal_period=signal_period,
    )


def calculate_ultimate_oscillator(
    data: pl.DataFrame,
    high_column: str = "high",
    low_column: str = "low",
    close_column: str = "close",
    period1: int = 7,
    period2: int = 14,
    period3: int = 28,
) -> pl.DataFrame:
    """Calculate Ultimate Oscillator (convenience function)."""
    return ULTOSC().calculate(
        data,
        high_column=high_column,
        low_column=low_column,
        close_column=close_column,
        period1=period1,
        period2=period2,
        period3=period3,
    )
