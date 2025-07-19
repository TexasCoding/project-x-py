"""
ProjectX Indicators - Base Classes

Author: TexasCoding
Date: June 2025

Base classes and common functionality for technical indicators.
"""

from abc import ABC, abstractmethod

import polars as pl


class IndicatorError(Exception):
    """Custom exception for indicator calculation errors."""


class BaseIndicator(ABC):
    """
    Base class for all technical indicators.

    Provides common validation, error handling, and utility methods
    that all indicators can inherit from.
    """

    def __init__(self, name: str, description: str = ""):
        """
        Initialize base indicator.

        Args:
            name: Indicator name
            description: Optional description
        """
        self.name = name
        self.description = description

    def validate_data(self, data: pl.DataFrame, required_columns: list[str]) -> None:
        """
        Validate input DataFrame and required columns.

        Args:
            data: Input DataFrame
            required_columns: List of required column names

        Raises:
            IndicatorError: If validation fails
        """
        if data is None:
            raise IndicatorError("Data cannot be None")

        if data.is_empty():
            raise IndicatorError("Data cannot be empty")

        for col in required_columns:
            if col not in data.columns:
                raise IndicatorError(f"Required column '{col}' not found in data")

    def validate_period(self, period: int, min_period: int = 1) -> None:
        """
        Validate period parameter.

        Args:
            period: Period value to validate
            min_period: Minimum allowed period

        Raises:
            IndicatorError: If period is invalid
        """
        if not isinstance(period, int) or period < min_period:
            raise IndicatorError(f"Period must be an integer >= {min_period}")

    def validate_data_length(self, data: pl.DataFrame, min_length: int) -> None:
        """
        Validate that data has sufficient length for calculation.

        Args:
            data: Input DataFrame
            min_length: Minimum required data length

        Raises:
            IndicatorError: If data is too short
        """
        if len(data) < min_length:
            raise IndicatorError(
                f"Insufficient data: need at least {min_length} rows, got {len(data)}"
            )

    @abstractmethod
    def calculate(self, data: pl.DataFrame, **kwargs) -> pl.DataFrame:
        """
        Calculate the indicator values.

        Args:
            data: Input DataFrame with OHLCV data
            **kwargs: Additional parameters specific to each indicator

        Returns:
            DataFrame with indicator columns added
        """

    def __call__(self, data: pl.DataFrame, **kwargs) -> pl.DataFrame:
        """
        Allow indicator to be called directly.

        Args:
            data: Input DataFrame
            **kwargs: Additional parameters

        Returns:
            DataFrame with indicator values
        """
        return self.calculate(data, **kwargs)


class OverlapIndicator(BaseIndicator):
    """Base class for overlap study indicators (trend-following)."""

    def __init__(self, name: str, description: str = ""):
        super().__init__(name, description)
        self.category = "overlap"


class MomentumIndicator(BaseIndicator):
    """Base class for momentum indicators."""

    def __init__(self, name: str, description: str = ""):
        super().__init__(name, description)
        self.category = "momentum"


class VolatilityIndicator(BaseIndicator):
    """Base class for volatility indicators."""

    def __init__(self, name: str, description: str = ""):
        super().__init__(name, description)
        self.category = "volatility"


class VolumeIndicator(BaseIndicator):
    """Base class for volume indicators."""

    def __init__(self, name: str, description: str = ""):
        super().__init__(name, description)
        self.category = "volume"


# Utility functions for common calculations
def safe_division(
    numerator: pl.Expr, denominator: pl.Expr, default: float = 0.0
) -> pl.Expr:
    """
    Safe division that handles division by zero.

    Args:
        numerator: Numerator expression
        denominator: Denominator expression
        default: Default value when denominator is zero

    Returns:
        Polars expression for safe division
    """
    return pl.when(denominator != 0).then(numerator / denominator).otherwise(default)


def rolling_sum_positive(expr: pl.Expr, window: int) -> pl.Expr:
    """
    Calculate rolling sum of positive values only.

    Args:
        expr: Polars expression
        window: Rolling window size

    Returns:
        Polars expression for rolling sum of positive values
    """
    return pl.when(expr > 0).then(expr).otherwise(0).rolling_sum(window_size=window)


def rolling_sum_negative(expr: pl.Expr, window: int) -> pl.Expr:
    """
    Calculate rolling sum of absolute negative values.

    Args:
        expr: Polars expression
        window: Rolling window size

    Returns:
        Polars expression for rolling sum of absolute negative values
    """
    return pl.when(expr < 0).then(-expr).otherwise(0).rolling_sum(window_size=window)


def ema_alpha(period: int) -> float:
    """
    Calculate EMA alpha (smoothing factor) from period.

    Args:
        period: EMA period

    Returns:
        Alpha value for EMA calculation
    """
    return 2.0 / (period + 1)
