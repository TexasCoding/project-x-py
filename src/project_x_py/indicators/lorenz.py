"""
ProjectX Indicators - Lorenz Formula Indicator

Author: @TexasCoding
Date: 2025-01-31

Overview:
    Implements the Lorenz Formula indicator which applies chaos theory to market
    analysis. The Lorenz equations, originally developed for atmospheric modeling,
    are adapted to create a dynamic indicator that responds to market volatility,
    trend strength, and volume patterns.

Key Features:
    - Transforms OHLCV data into a chaotic dynamical system
    - Dynamic parameter calculation from market conditions
    - Three output values (x, y, z) representing different aspects of market chaos
    - Configurable sensitivity through dt (time step) parameter
    - Volume-weighted dissipation for liquidity analysis

Mathematical Foundation:
    The Lorenz system is defined by three coupled differential equations:
    dx/dt = σ(y - x)
    dy/dt = x(ρ - z) - y
    dz/dt = xy - βz

    Where parameters are derived from market data:
    - σ (sigma): Volatility factor from price returns standard deviation
    - ρ (rho): Trend strength from close/mean ratio
    - β (beta): Dissipation rate from volume/mean ratio

Example Usage:
    ```python
    from project_x_py.indicators import LORENZ

    # Calculate Lorenz indicator
    data_with_lorenz = LORENZ(ohlcv_data, window=14, dt=0.01)

    # Use z-value for signal generation
    signals = data_with_lorenz.filter(
        pl.col("lorenz_z") > pl.col("lorenz_z").rolling_mean(20)
    )
    ```

See Also:
    - `project_x_py.indicators.volatility.ATR` for volatility measurement
    - `project_x_py.indicators.momentum` for trend indicators
    - `project_x_py.indicators.base.BaseIndicator`
"""

from typing import Any

import numpy as np
import polars as pl

from project_x_py.indicators.base import BaseIndicator


class LORENZIndicator(BaseIndicator):
    """
    Lorenz Formula indicator for chaos-based market analysis.

    The Lorenz indicator adapts the famous Lorenz attractor equations to financial
    markets, creating a chaotic system that responds to price volatility, trend
    strength, and volume patterns. The resulting x, y, z values can reveal hidden
    market dynamics and potential regime changes.

    The indicator is particularly useful for:
    - Detecting market instability and potential breakouts
    - Identifying regime changes in market behavior
    - Analyzing the interplay between volatility, trend, and volume
    - Generating unique signals not captured by traditional indicators
    """

    def __init__(self) -> None:
        super().__init__(
            name="LORENZ",
            description="Lorenz Formula - chaos theory-based indicator using dynamical systems to analyze market conditions",
        )

    def calculate(
        self,
        data: pl.DataFrame,
        **kwargs: Any,
    ) -> pl.DataFrame:
        """
        Calculate Lorenz Formula indicator.

        The Lorenz system parameters are dynamically calculated from market data:
        - Sigma (σ): Scaled from rolling volatility of returns
        - Rho (ρ): Scaled from close price relative to rolling mean
        - Beta (β): Scaled from volume relative to rolling mean

        The system evolves using Euler method discretization, producing three
        output series (x, y, z) that capture different aspects of market chaos.

        Args:
            data: DataFrame with OHLC and volume data
            **kwargs: Additional parameters:
                close_column: Close price column (default: "close")
                high_column: High price column (default: "high")
                low_column: Low price column (default: "low")
                volume_column: Volume column (default: "volume")
                window: Rolling window for parameter calculations (default: 14)
                dt: Time step for Euler discretization (default: 1.0)
                volatility_scale: Expected volatility for normalization (default: 0.02)
                initial_x: Initial x value (default: 0.0)
                initial_y: Initial y value (default: 1.0)
                initial_z: Initial z value (default: 0.0)

        Returns:
            DataFrame with Lorenz columns added:
            - lorenz_x: X component of Lorenz system
            - lorenz_y: Y component of Lorenz system
            - lorenz_z: Z component (primary signal)

        Example:
            >>> lorenz = LORENZIndicator()
            >>> data_with_lorenz = lorenz.calculate(ohlcv_data, window=20, dt=0.01)
            >>> bullish = data_with_lorenz.filter(pl.col("lorenz_z") > 0)
        """
        # Extract parameters
        close_column = kwargs.get("close_column", "close")
        volume_column = kwargs.get("volume_column", "volume")
        window = kwargs.get("window", 14)
        dt = kwargs.get("dt", 1.0)
        volatility_scale = kwargs.get("volatility_scale", 0.02)
        initial_x = kwargs.get("initial_x", 0.0)
        initial_y = kwargs.get("initial_y", 1.0)
        initial_z = kwargs.get("initial_z", 0.0)

        # Validate data
        required_cols = [close_column, volume_column, "high", "low", "open"]
        self.validate_data(data, required_cols)
        self.validate_data_length(data, window)

        # Calculate returns and rolling statistics
        result = data.with_columns(
            [
                # Percentage returns
                pl.col(close_column).pct_change().alias("returns"),
            ]
        )

        # Add rolling statistics
        result = result.with_columns(
            [
                # Rolling volatility (standard deviation of returns)
                pl.col("returns").rolling_std(window_size=window).alias("volatility"),
                # Rolling mean of close prices
                pl.col(close_column)
                .rolling_mean(window_size=window)
                .alias("close_mean"),
                # Rolling mean of volume
                pl.col(volume_column)
                .rolling_mean(window_size=window)
                .alias("volume_mean"),
            ]
        )

        # Calculate ratios for parameter scaling
        result = result.with_columns(
            [
                # Close to mean ratio (trend strength)
                (pl.col(close_column) / pl.col("close_mean")).alias("close_ratio"),
                # Volume to mean ratio (liquidity)
                (pl.col(volume_column) / pl.col("volume_mean")).alias("volume_ratio"),
            ]
        )

        # Initialize Lorenz state arrays
        n = len(result)
        x = np.full(n, np.nan, dtype=np.float64)
        y = np.full(n, np.nan, dtype=np.float64)
        z = np.full(n, np.nan, dtype=np.float64)

        # Set initial conditions
        x[0] = initial_x
        y[0] = initial_y
        z[0] = initial_z

        # Extract data to numpy for efficient iteration
        volatility_arr = result["volatility"].to_numpy()
        close_ratio_arr = result["close_ratio"].to_numpy()
        volume_ratio_arr = result["volume_ratio"].to_numpy()

        # Euler method integration
        for i in range(1, n):
            # Get current volatility
            vol = volatility_arr[i]

            # Handle NaN in early rows (use default Lorenz parameters)
            if (
                np.isnan(vol)
                or np.isnan(close_ratio_arr[i])
                or np.isnan(volume_ratio_arr[i])
            ):
                sigma = 10.0
                rho = 28.0
                beta = 2.667
            else:
                # Scale parameters based on market data
                # Sigma: volatility factor (typical range 5-15)
                sigma = 10.0 * (vol / volatility_scale)

                # Rho: regime driver (typical range 20-35)
                rho = 28.0 * close_ratio_arr[i]

                # Beta: dissipation rate (typical range 1-4)
                beta = 2.667 * volume_ratio_arr[i]

            # Lorenz equations via Euler method
            dx = sigma * (y[i - 1] - x[i - 1]) * dt
            dy = (x[i - 1] * (rho - z[i - 1]) - y[i - 1]) * dt
            dz = (x[i - 1] * y[i - 1] - beta * z[i - 1]) * dt

            # Update state
            x[i] = x[i - 1] + dx
            y[i] = y[i - 1] + dy
            z[i] = z[i - 1] + dz

            # Prevent explosion (optional stability check)
            # Lorenz can exhibit extreme values in certain parameter regimes
            max_val = 1000.0
            if abs(x[i]) > max_val:
                x[i] = np.sign(x[i]) * max_val
            if abs(y[i]) > max_val:
                y[i] = np.sign(y[i]) * max_val
            if abs(z[i]) > max_val:
                z[i] = np.sign(z[i]) * max_val

        # Add Lorenz components to DataFrame
        result = result.with_columns(
            [
                pl.Series("lorenz_x", x),
                pl.Series("lorenz_y", y),
                pl.Series("lorenz_z", z),
            ]
        )

        # Clean up intermediate columns
        columns_to_drop = [
            "returns",
            "volatility",
            "close_mean",
            "volume_mean",
            "close_ratio",
            "volume_ratio",
        ]
        result = result.drop(columns_to_drop)

        return result


def calculate_lorenz(
    data: pl.DataFrame,
    close_column: str = "close",
    volume_column: str = "volume",
    window: int = 14,
    dt: float = 1.0,
    volatility_scale: float = 0.02,
    initial_x: float = 0.0,
    initial_y: float = 1.0,
    initial_z: float = 0.0,
) -> pl.DataFrame:
    """
    Calculate Lorenz Formula indicator (convenience function).

    See LORENZIndicator.calculate() for detailed documentation.

    Args:
        data: DataFrame with OHLC and volume data
        close_column: Close price column
        volume_column: Volume column
        window: Rolling window for parameter calculations
        dt: Time step for Euler discretization
        volatility_scale: Expected volatility for normalization
        initial_x: Initial x value
        initial_y: Initial y value
        initial_z: Initial z value

    Returns:
        DataFrame with Lorenz x, y, z columns added
    """
    indicator = LORENZIndicator()
    return indicator.calculate(
        data,
        close_column=close_column,
        volume_column=volume_column,
        window=window,
        dt=dt,
        volatility_scale=volatility_scale,
        initial_x=initial_x,
        initial_y=initial_y,
        initial_z=initial_z,
    )


def LORENZ(
    data: pl.DataFrame,
    window: int = 14,
    dt: float = 1.0,
    **kwargs: Any,
) -> pl.DataFrame:
    """
    Lorenz Formula indicator (TA-Lib style).

    Applies chaos theory to market analysis through the Lorenz attractor equations.

    Args:
        data: DataFrame with OHLC and volume data
        window: Rolling window period
        dt: Time step for discretization
        **kwargs: Additional parameters (see calculate_lorenz)

    Returns:
        DataFrame with lorenz_x, lorenz_y, lorenz_z columns
    """
    return calculate_lorenz(data, window=window, dt=dt, **kwargs)
