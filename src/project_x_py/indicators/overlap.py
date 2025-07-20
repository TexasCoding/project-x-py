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

        # Calculate WMA using polars operations
        def wma_calc(series: list[float]) -> list[float | None]:
            """Calculate WMA for a series"""
            n = len(series)
            if n < period:
                return [None] * n

            result: list[float | None] = []
            for i in range(n):
                if i < period - 1:
                    result.append(None)
                else:
                    values = series[i - period + 1 : i + 1]
                    weighted_sum = sum(val * (j + 1) for j, val in enumerate(values))
                    weight_sum = sum(range(1, period + 1))
                    wma_value = weighted_sum / weight_sum
                    result.append(wma_value)

            return result

        # Apply WMA calculation
        values = data[column].to_list()
        wma_values = wma_calc(values)

        return data.with_columns(
            pl.Series(name=f"wma_{period}", values=wma_values, dtype=pl.Float64)
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


class MIDPRICE(OverlapIndicator):
    """Midpoint Price over period indicator."""

    def __init__(self):
        super().__init__(
            name="MIDPRICE",
            description="Midpoint Price - average of highest high and lowest low over period",
        )

    def calculate(
        self,
        data: pl.DataFrame,
        high_column: str = "high",
        low_column: str = "low",
        period: int = 14,
    ) -> pl.DataFrame:
        """
        Calculate Midpoint Price over period.

        Args:
            data: DataFrame with OHLCV data
            high_column: Column name for high prices
            low_column: Column name for low prices
            period: Lookback period

        Returns:
            DataFrame with midprice column added
        """
        self.validate_data(data, [high_column, low_column])
        self.validate_period(period, min_period=1)
        self.validate_data_length(data, period)

        return data.with_columns(
            (
                (
                    pl.col(high_column).rolling_max(window_size=period)
                    + pl.col(low_column).rolling_min(window_size=period)
                )
                / 2
            ).alias(f"midprice_{period}")
        )


class HT_TRENDLINE(OverlapIndicator):
    """Hilbert Transform - Instantaneous Trendline indicator."""

    def __init__(self):
        super().__init__(
            name="HT_TRENDLINE",
            description="Hilbert Transform - Instantaneous Trendline",
        )

    def calculate(
        self,
        data: pl.DataFrame,
        column: str = "close",
    ) -> pl.DataFrame:
        """
        Calculate Hilbert Transform - Instantaneous Trendline.

        Args:
            data: DataFrame with OHLCV data
            column: Column to calculate trendline for

        Returns:
            DataFrame with HT trendline column added
        """
        self.validate_data(data, [column])

        # Simplified Hilbert Transform implementation
        # This is a basic implementation - full HT is more complex
        return data.with_columns(
            pl.col(column).ewm_mean(alpha=0.0625).alias("ht_trendline")
        )


class KAMA(OverlapIndicator):
    """Kaufman Adaptive Moving Average indicator."""

    def __init__(self):
        super().__init__(
            name="KAMA",
            description="Kaufman Adaptive Moving Average - adaptive moving average that adjusts to market volatility",
        )

    def calculate(
        self,
        data: pl.DataFrame,
        column: str = "close",
        period: int = 30,
        fast_sc: float = 2.0,
        slow_sc: float = 30.0,
    ) -> pl.DataFrame:
        """
        Calculate Kaufman Adaptive Moving Average.

        Args:
            data: DataFrame with OHLCV data
            column: Column to calculate KAMA for
            period: Period for efficiency ratio calculation
            fast_sc: Fast smoothing constant
            slow_sc: Slow smoothing constant

        Returns:
            DataFrame with KAMA column added
        """
        self.validate_data(data, [column])
        self.validate_period(period, min_period=2)

        def kama_calc(series: list[float]) -> list[float | None]:
            """Calculate KAMA for a series"""
            n = len(series)
            if n < period + 1:
                return [None] * n

            result: list[float | None] = [None] * n

            # Initialize first KAMA value with SMA
            result[period] = sum(series[: period + 1]) / (period + 1)

            fast_alpha = 2.0 / (fast_sc + 1.0)
            slow_alpha = 2.0 / (slow_sc + 1.0)

            for i in range(period + 1, n):
                # Calculate change over period
                change = abs(series[i] - series[i - period])

                # Calculate volatility (sum of absolute changes)
                volatility = sum(
                    abs(series[j] - series[j - 1]) for j in range(i - period + 1, i + 1)
                )

                # Calculate efficiency ratio
                er = change / volatility if volatility != 0 else 0

                # Calculate smoothing constant
                sc = (er * (fast_alpha - slow_alpha) + slow_alpha) ** 2

                # Calculate KAMA
                prev_kama = result[i - 1]
                if prev_kama is not None:
                    result[i] = prev_kama + sc * (series[i] - prev_kama)

            return result

        values = data[column].to_list()
        kama_values = kama_calc(values)

        return data.with_columns(
            pl.Series(name=f"kama_{period}", values=kama_values, dtype=pl.Float64)
        )


class MA(OverlapIndicator):
    """Generic Moving Average indicator with different MA types."""

    def __init__(self):
        super().__init__(
            name="MA",
            description="Moving Average - generic moving average with selectable type",
        )

    def calculate(
        self,
        data: pl.DataFrame,
        column: str = "close",
        period: int = 30,
        ma_type: str = "sma",
    ) -> pl.DataFrame:
        """
        Calculate Moving Average of specified type.

        Args:
            data: DataFrame with OHLCV data
            column: Column to calculate MA for
            period: Period for moving average
            ma_type: Type of moving average ('sma', 'ema', 'wma', 'dema', 'tema')

        Returns:
            DataFrame with MA column added
        """
        self.validate_data(data, [column])
        self.validate_period(period, min_period=1)

        ma_type = ma_type.lower()

        if ma_type == "sma":
            return SMA().calculate(data, column, period)
        elif ma_type == "ema":
            return EMA().calculate(data, column, period)
        elif ma_type == "wma":
            return WMA().calculate(data, column, period)
        elif ma_type == "dema":
            return DEMA().calculate(data, column, period)
        elif ma_type == "tema":
            return TEMA().calculate(data, column, period)
        else:
            raise ValueError(f"Unsupported MA type: {ma_type}")


class MAMA(OverlapIndicator):
    """MESA Adaptive Moving Average indicator."""

    def __init__(self):
        super().__init__(
            name="MAMA",
            description="MESA Adaptive Moving Average - adaptive moving average based on dominant cycle",
        )

    def calculate(
        self,
        data: pl.DataFrame,
        column: str = "close",
        fast_limit: float = 0.5,
        slow_limit: float = 0.05,
    ) -> pl.DataFrame:
        """
        Calculate MESA Adaptive Moving Average.

        Args:
            data: DataFrame with OHLCV data
            column: Column to calculate MAMA for
            fast_limit: Fast limit for adaptation
            slow_limit: Slow limit for adaptation

        Returns:
            DataFrame with MAMA and FAMA columns added
        """
        self.validate_data(data, [column])

        def mama_calc(
            series: list[float],
        ) -> tuple[list[float | None], list[float | None]]:
            """Calculate MAMA and FAMA for a series"""
            n = len(series)
            if n < 6:
                return [None] * n, [None] * n

            mama: list[float | None] = [None] * n
            fama: list[float | None] = [None] * n

            # Initialize
            mama[5] = series[5]
            fama[5] = series[5]

            for i in range(6, n):
                # Simplified MESA algorithm
                # In practice, this would involve complex Hilbert Transform calculations
                price = series[i]

                # Simplified adaptive factor calculation
                alpha = min(fast_limit, max(slow_limit, 0.1))

                # Calculate MAMA
                prev_mama = mama[i - 1]
                if prev_mama is not None:
                    mama[i] = alpha * price + (1 - alpha) * prev_mama
                else:
                    mama[i] = price

                # Calculate FAMA (Following Adaptive Moving Average)
                prev_fama = fama[i - 1]
                current_mama = mama[i]
                if prev_fama is not None and current_mama is not None:
                    fama[i] = 0.5 * alpha * current_mama + (1 - 0.5 * alpha) * prev_fama
                elif current_mama is not None:
                    fama[i] = current_mama

            return mama, fama

        values = data[column].to_list()
        mama_values, fama_values = mama_calc(values)

        return data.with_columns(
            [
                pl.Series(name="mama", values=mama_values, dtype=pl.Float64),
                pl.Series(name="fama", values=fama_values, dtype=pl.Float64),
            ]
        )


class MAVP(OverlapIndicator):
    """Moving Average with Variable Period indicator."""

    def __init__(self):
        super().__init__(
            name="MAVP",
            description="Moving Average with Variable Period - moving average with dynamically changing period",
        )

    def calculate(
        self,
        data: pl.DataFrame,
        column: str = "close",
        periods_column: str = "periods",
        min_period: int = 2,
        max_period: int = 30,
        ma_type: str = "sma",
    ) -> pl.DataFrame:
        """
        Calculate Moving Average with Variable Period.

        Args:
            data: DataFrame with OHLCV data
            column: Column to calculate MA for
            periods_column: Column containing period values
            min_period: Minimum period value
            max_period: Maximum period value
            ma_type: Type of moving average

        Returns:
            DataFrame with MAVP column added
        """
        self.validate_data(data, [column])

        # If periods column doesn't exist, create a default one
        if periods_column not in data.columns:
            # Use a simple adaptive period based on volatility
            data = data.with_columns(pl.lit(min_period).alias(periods_column))

        # Simplified implementation - use fixed period for now
        # In practice, this would dynamically adjust the period
        return data.with_columns(
            pl.col(column).rolling_mean(window_size=min_period).alias("mavp")
        )


class SAR(OverlapIndicator):
    """Parabolic SAR indicator."""

    def __init__(self):
        super().__init__(
            name="SAR",
            description="Parabolic SAR - stop and reverse system for trend following",
        )

    def calculate(
        self,
        data: pl.DataFrame,
        high_column: str = "high",
        low_column: str = "low",
        acceleration: float = 0.02,
        maximum: float = 0.2,
    ) -> pl.DataFrame:
        """
        Calculate Parabolic SAR.

        Args:
            data: DataFrame with OHLCV data
            high_column: Column name for high prices
            low_column: Column name for low prices
            acceleration: Acceleration factor
            maximum: Maximum acceleration factor

        Returns:
            DataFrame with SAR column added
        """
        self.validate_data(data, [high_column, low_column])

        def sar_calc(highs: list[float], lows: list[float]) -> list[float | None]:
            """Calculate SAR values"""
            n = len(highs)
            if n < 2:
                return [None] * n

            sar: list[float | None] = [None] * n
            trend: list[int] = [0] * n
            af: list[float] = [0.0] * n
            ep: list[float] = [0.0] * n

            # Initialize
            sar[1] = lows[0]
            trend[1] = 1  # 1 for uptrend, -1 for downtrend
            af[1] = acceleration
            ep[1] = highs[1]

            for i in range(2, n):
                prev_sar = sar[i - 1]
                if prev_sar is None:
                    prev_sar = lows[0]

                # Calculate new SAR
                new_sar = prev_sar + af[i - 1] * (ep[i - 1] - prev_sar)

                # Determine trend
                if trend[i - 1] == 1:  # Uptrend
                    if lows[i] <= new_sar:
                        # Trend reversal to downtrend
                        trend[i] = -1
                        sar[i] = ep[i - 1]
                        af[i] = acceleration
                        ep[i] = lows[i]
                    else:
                        # Continue uptrend
                        trend[i] = 1
                        if highs[i] > ep[i - 1]:
                            ep[i] = highs[i]
                            af[i] = min(af[i - 1] + acceleration, maximum)
                        else:
                            ep[i] = ep[i - 1]
                            af[i] = af[i - 1]

                        # Adjust SAR
                        sar[i] = min(
                            new_sar, lows[i - 1], lows[i - 2] if i > 2 else lows[i - 1]
                        )

                else:  # Downtrend
                    if highs[i] >= new_sar:
                        # Trend reversal to uptrend
                        trend[i] = 1
                        sar[i] = ep[i - 1]
                        af[i] = acceleration
                        ep[i] = highs[i]
                    else:
                        # Continue downtrend
                        trend[i] = -1
                        if lows[i] < ep[i - 1]:
                            ep[i] = lows[i]
                            af[i] = min(af[i - 1] + acceleration, maximum)
                        else:
                            ep[i] = ep[i - 1]
                            af[i] = af[i - 1]

                        # Adjust SAR
                        sar[i] = max(
                            new_sar,
                            highs[i - 1],
                            highs[i - 2] if i > 2 else highs[i - 1],
                        )

            return sar

        highs = data[high_column].to_list()
        lows = data[low_column].to_list()
        sar_values = sar_calc(highs, lows)

        return data.with_columns(
            pl.Series(name="sar", values=sar_values, dtype=pl.Float64)
        )


class SAREXT(OverlapIndicator):
    """Parabolic SAR - Extended indicator."""

    def __init__(self):
        super().__init__(
            name="SAREXT",
            description="Parabolic SAR - Extended with additional parameters",
        )

    def calculate(
        self,
        data: pl.DataFrame,
        high_column: str = "high",
        low_column: str = "low",
        start_value: float = 0.0,
        offset_on_reverse: float = 0.0,
        acceleration_init_long: float = 0.02,
        acceleration_long: float = 0.02,
        acceleration_max_long: float = 0.2,
        acceleration_init_short: float = 0.02,
        acceleration_short: float = 0.02,
        acceleration_max_short: float = 0.2,
    ) -> pl.DataFrame:
        """
        Calculate Parabolic SAR - Extended.

        Args:
            data: DataFrame with OHLCV data
            high_column: Column name for high prices
            low_column: Column name for low prices
            start_value: Starting value
            offset_on_reverse: Offset on reversal
            acceleration_init_long: Initial acceleration for long
            acceleration_long: Acceleration increment for long
            acceleration_max_long: Maximum acceleration for long
            acceleration_init_short: Initial acceleration for short
            acceleration_short: Acceleration increment for short
            acceleration_max_short: Maximum acceleration for short

        Returns:
            DataFrame with SAREXT column added
        """
        self.validate_data(data, [high_column, low_column])

        # For simplicity, use regular SAR with different parameters
        # Full SAREXT implementation would handle all these parameters separately
        result = SAR().calculate(
            data, high_column, low_column, acceleration_long, acceleration_max_long
        )

        return result.rename({"sar": "sarext"})


class T3(OverlapIndicator):
    """Triple Exponential Moving Average (T3) indicator."""

    def __init__(self):
        super().__init__(
            name="T3",
            description="Triple Exponential Moving Average (T3) - Tillson T3 moving average",
        )

    def calculate(
        self,
        data: pl.DataFrame,
        column: str = "close",
        period: int = 5,
        v_factor: float = 0.7,
    ) -> pl.DataFrame:
        """
        Calculate T3 Moving Average.

        Args:
            data: DataFrame with OHLCV data
            column: Column to calculate T3 for
            period: Period for moving average
            v_factor: Volume factor (0-1)

        Returns:
            DataFrame with T3 column added
        """
        self.validate_data(data, [column])
        self.validate_period(period, min_period=1)

        alpha = ema_alpha(period)
        c1 = -v_factor * v_factor * v_factor
        c2 = 3 * v_factor * v_factor + 3 * v_factor * v_factor * v_factor
        c3 = (
            -6 * v_factor * v_factor - 3 * v_factor - 3 * v_factor * v_factor * v_factor
        )
        c4 = 1 + 3 * v_factor + v_factor * v_factor * v_factor + 3 * v_factor * v_factor

        # Calculate series of EMAs
        data_with_ema1 = data.with_columns(
            pl.col(column).ewm_mean(alpha=alpha).alias("e1")
        )

        data_with_ema2 = data_with_ema1.with_columns(
            pl.col("e1").ewm_mean(alpha=alpha).alias("e2")
        )

        data_with_ema3 = data_with_ema2.with_columns(
            pl.col("e2").ewm_mean(alpha=alpha).alias("e3")
        )

        data_with_ema4 = data_with_ema3.with_columns(
            pl.col("e3").ewm_mean(alpha=alpha).alias("e4")
        )

        data_with_ema5 = data_with_ema4.with_columns(
            pl.col("e4").ewm_mean(alpha=alpha).alias("e5")
        )

        data_with_ema6 = data_with_ema5.with_columns(
            pl.col("e5").ewm_mean(alpha=alpha).alias("e6")
        )

        # Calculate T3
        result = data_with_ema6.with_columns(
            (
                c1 * pl.col("e6")
                + c2 * pl.col("e5")
                + c3 * pl.col("e4")
                + c4 * pl.col("e3")
            ).alias(f"t3_{period}")
        )

        # Remove temporary columns
        return result.drop(["e1", "e2", "e3", "e4", "e5", "e6"])


class TRIMA(OverlapIndicator):
    """Triangular Moving Average indicator."""

    def __init__(self):
        super().__init__(
            name="TRIMA",
            description="Triangular Moving Average - double smoothed moving average",
        )

    def calculate(
        self,
        data: pl.DataFrame,
        column: str = "close",
        period: int = 20,
    ) -> pl.DataFrame:
        """
        Calculate Triangular Moving Average.

        Args:
            data: DataFrame with OHLCV data
            column: Column to calculate TRIMA for
            period: Period for moving average

        Returns:
            DataFrame with TRIMA column added
        """
        self.validate_data(data, [column])
        self.validate_period(period, min_period=1)

        if period % 2 == 1:
            # Odd period
            n1 = (period + 1) // 2
            n2 = n1
        else:
            # Even period
            n1 = period // 2
            n2 = n1 + 1

        # Calculate first SMA
        data_with_sma1 = data.with_columns(
            pl.col(column).rolling_mean(window_size=n1).alias("sma1_temp")
        )

        # Calculate second SMA of the first SMA
        result = data_with_sma1.with_columns(
            pl.col("sma1_temp").rolling_mean(window_size=n2).alias(f"trima_{period}")
        )

        # Remove temporary column
        return result.drop(["sma1_temp"])


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


def calculate_dema(
    data: pl.DataFrame, column: str = "close", period: int = 20
) -> pl.DataFrame:
    """Calculate Double Exponential Moving Average (convenience function)."""
    return DEMA().calculate(data, column=column, period=period)


def calculate_tema(
    data: pl.DataFrame, column: str = "close", period: int = 20
) -> pl.DataFrame:
    """Calculate Triple Exponential Moving Average (convenience function)."""
    return TEMA().calculate(data, column=column, period=period)


def calculate_wma(
    data: pl.DataFrame, column: str = "close", period: int = 20
) -> pl.DataFrame:
    """Calculate Weighted Moving Average (convenience function)."""
    return WMA().calculate(data, column=column, period=period)


def calculate_midpoint(
    data: pl.DataFrame, column: str = "close", period: int = 14
) -> pl.DataFrame:
    """Calculate Midpoint (convenience function)."""
    return MIDPOINT().calculate(data, column=column, period=period)


def calculate_midprice(
    data: pl.DataFrame,
    high_column: str = "high",
    low_column: str = "low",
    period: int = 14,
) -> pl.DataFrame:
    """Calculate Midpoint Price (convenience function)."""
    return MIDPRICE().calculate(
        data, high_column=high_column, low_column=low_column, period=period
    )


def calculate_ht_trendline(data: pl.DataFrame, column: str = "close") -> pl.DataFrame:
    """Calculate Hilbert Transform Trendline (convenience function)."""
    return HT_TRENDLINE().calculate(data, column=column)


def calculate_kama(
    data: pl.DataFrame,
    column: str = "close",
    period: int = 30,
    fast_sc: float = 2.0,
    slow_sc: float = 30.0,
) -> pl.DataFrame:
    """Calculate Kaufman Adaptive Moving Average (convenience function)."""
    return KAMA().calculate(
        data, column=column, period=period, fast_sc=fast_sc, slow_sc=slow_sc
    )


def calculate_ma(
    data: pl.DataFrame, column: str = "close", period: int = 30, ma_type: str = "sma"
) -> pl.DataFrame:
    """Calculate generic Moving Average (convenience function)."""
    return MA().calculate(data, column=column, period=period, ma_type=ma_type)


def calculate_mama(
    data: pl.DataFrame,
    column: str = "close",
    fast_limit: float = 0.5,
    slow_limit: float = 0.05,
) -> pl.DataFrame:
    """Calculate MESA Adaptive Moving Average (convenience function)."""
    return MAMA().calculate(
        data, column=column, fast_limit=fast_limit, slow_limit=slow_limit
    )


def calculate_sar(
    data: pl.DataFrame,
    high_column: str = "high",
    low_column: str = "low",
    acceleration: float = 0.02,
    maximum: float = 0.2,
) -> pl.DataFrame:
    """Calculate Parabolic SAR (convenience function)."""
    return SAR().calculate(
        data,
        high_column=high_column,
        low_column=low_column,
        acceleration=acceleration,
        maximum=maximum,
    )


def calculate_t3(
    data: pl.DataFrame, column: str = "close", period: int = 5, v_factor: float = 0.7
) -> pl.DataFrame:
    """Calculate T3 Moving Average (convenience function)."""
    return T3().calculate(data, column=column, period=period, v_factor=v_factor)


def calculate_trima(
    data: pl.DataFrame, column: str = "close", period: int = 20
) -> pl.DataFrame:
    """Calculate Triangular Moving Average (convenience function)."""
    return TRIMA().calculate(data, column=column, period=period)
