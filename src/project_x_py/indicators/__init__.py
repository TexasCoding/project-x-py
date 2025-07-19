"""
ProjectX Indicators - Technical Analysis Library

Author: TexasCoding
Date: June 2025

A comprehensive technical analysis library similar to TA-Lib, built on Polars DataFrames.
Provides both class-based and function-based interfaces for technical indicators.

Example usage:
    # Class-based interface
    >>> from project_x_py.indicators import RSI, SMA
    >>> rsi = RSI()
    >>> data_with_rsi = rsi.calculate(ohlcv_data, period=14)

    # Function-based interface (TA-Lib style)
    >>> from project_x_py.indicators import calculate_rsi, calculate_sma
    >>> data_with_rsi = calculate_rsi(ohlcv_data, period=14)
    >>> data_with_sma = calculate_sma(ohlcv_data, period=20)
"""

# Base classes and utilities
from .base import (
    BaseIndicator,
    IndicatorError,
    MomentumIndicator,
    OverlapIndicator,
    VolatilityIndicator,
    VolumeIndicator,
    ema_alpha,
    safe_division,
)

# Momentum Indicators
from .momentum import (
    CCI as CCIIndicator,
    MACD as MACDIndicator,
    MOM as MOMIndicator,
    ROC as ROCIndicator,
    RSI as RSIIndicator,
    STOCH as STOCHIndicator,
    STOCHRSI as STOCHRSIIndicator,
    WILLR as WILLRIndicator,
    calculate_commodity_channel_index,
    calculate_macd,
    calculate_rsi,
    calculate_stochastic,
    calculate_williams_r,
)

# Overlap Studies (Trend Indicators)
from .overlap import (
    BBANDS as BBANDSIndicator,
    DEMA as DEMAIndicator,
    EMA as EMAIndicator,
    MIDPOINT as MIDPOINTIndicator,
    SMA as SMAIndicator,
    TEMA as TEMAIndicator,
    WMA as WMAIndicator,
    calculate_bollinger_bands,
    calculate_ema,
    calculate_sma,
)

# Volatility Indicators
from .volatility import (
    ADX as ADXIndicator,
    ATR as ATRIndicator,
    NATR as NATRIndicator,
    TRANGE as TRANGEIndicator,
    ULTOSC as ULTOSCIndicator,
    calculate_adx,
    calculate_atr,
)

# Volume Indicators
from .volume import (
    AD as ADIndicator,
    ADOSC as ADOSCIndicator,
    OBV as OBVIndicator,
    VWAP as VWAPIndicator,
    calculate_obv,
    calculate_vwap,
)

# Version info
__version__ = "1.0.0"
__author__ = "TexasCoding"


# TA-Lib Style Function Interface
# These functions provide direct access to indicators with TA-Lib naming conventions


# Overlap Studies
def SMA(data, column="close", period=20):
    """Simple Moving Average (TA-Lib style)."""
    return calculate_sma(data, column=column, period=period)


def EMA(data, column="close", period=20):
    """Exponential Moving Average (TA-Lib style)."""
    return calculate_ema(data, column=column, period=period)


def BBANDS(data, column="close", period=20, std_dev=2.0):
    """Bollinger Bands (TA-Lib style)."""
    return calculate_bollinger_bands(
        data, column=column, period=period, std_dev=std_dev
    )


def DEMA(data, column="close", period=20):
    """Double Exponential Moving Average (TA-Lib style)."""
    return DEMAIndicator().calculate(data, column=column, period=period)


def TEMA(data, column="close", period=20):
    """Triple Exponential Moving Average (TA-Lib style)."""
    return TEMAIndicator().calculate(data, column=column, period=period)


def WMA(data, column="close", period=20):
    """Weighted Moving Average (TA-Lib style)."""
    return WMAIndicator().calculate(data, column=column, period=period)


def MIDPOINT(data, column="close", period=14):
    """Midpoint over period (TA-Lib style)."""
    return MIDPOINTIndicator().calculate(data, column=column, period=period)


# Momentum Indicators
def RSI(data, column="close", period=14):
    """Relative Strength Index (TA-Lib style)."""
    return calculate_rsi(data, column=column, period=period)


def MACD(data, column="close", fast_period=12, slow_period=26, signal_period=9):
    """Moving Average Convergence Divergence (TA-Lib style)."""
    return calculate_macd(
        data,
        column=column,
        fast_period=fast_period,
        slow_period=slow_period,
        signal_period=signal_period,
    )


def STOCH(
    data,
    high_column="high",
    low_column="low",
    close_column="close",
    k_period=14,
    d_period=3,
):
    """Stochastic Oscillator (TA-Lib style)."""
    return calculate_stochastic(
        data,
        high_column=high_column,
        low_column=low_column,
        close_column=close_column,
        k_period=k_period,
        d_period=d_period,
    )


def WILLR(data, high_column="high", low_column="low", close_column="close", period=14):
    """Williams %R (TA-Lib style)."""
    return calculate_williams_r(
        data,
        high_column=high_column,
        low_column=low_column,
        close_column=close_column,
        period=period,
    )


def CCI(
    data,
    high_column="high",
    low_column="low",
    close_column="close",
    period=20,
    constant=0.015,
):
    """Commodity Channel Index (TA-Lib style)."""
    return calculate_commodity_channel_index(
        data,
        high_column=high_column,
        low_column=low_column,
        close_column=close_column,
        period=period,
        constant=constant,
    )


def ROC(data, column="close", period=10):
    """Rate of Change (TA-Lib style)."""
    return ROCIndicator().calculate(data, column=column, period=period)


def MOM(data, column="close", period=10):
    """Momentum (TA-Lib style)."""
    return MOMIndicator().calculate(data, column=column, period=period)


def STOCHRSI(
    data, column="close", rsi_period=14, stoch_period=14, k_period=3, d_period=3
):
    """Stochastic RSI (TA-Lib style)."""
    return STOCHRSIIndicator().calculate(
        data,
        column=column,
        rsi_period=rsi_period,
        stoch_period=stoch_period,
        k_period=k_period,
        d_period=d_period,
    )


# Volatility Indicators
def ATR(data, high_column="high", low_column="low", close_column="close", period=14):
    """Average True Range (TA-Lib style)."""
    return calculate_atr(
        data,
        high_column=high_column,
        low_column=low_column,
        close_column=close_column,
        period=period,
    )


def ADX(data, high_column="high", low_column="low", close_column="close", period=14):
    """Average Directional Index (TA-Lib style)."""
    return calculate_adx(
        data,
        high_column=high_column,
        low_column=low_column,
        close_column=close_column,
        period=period,
    )


def NATR(data, high_column="high", low_column="low", close_column="close", period=14):
    """Normalized Average True Range (TA-Lib style)."""
    return NATRIndicator().calculate(
        data,
        high_column=high_column,
        low_column=low_column,
        close_column=close_column,
        period=period,
    )


def TRANGE(data, high_column="high", low_column="low", close_column="close"):
    """True Range (TA-Lib style)."""
    return TRANGEIndicator().calculate(
        data, high_column=high_column, low_column=low_column, close_column=close_column
    )


def ULTOSC(
    data,
    high_column="high",
    low_column="low",
    close_column="close",
    period1=7,
    period2=14,
    period3=28,
):
    """Ultimate Oscillator (TA-Lib style)."""
    return ULTOSCIndicator().calculate(
        data,
        high_column=high_column,
        low_column=low_column,
        close_column=close_column,
        period1=period1,
        period2=period2,
        period3=period3,
    )


# Volume Indicators
def OBV(data, close_column="close", volume_column="volume"):
    """On-Balance Volume (TA-Lib style)."""
    return calculate_obv(data, close_column=close_column, volume_column=volume_column)


def VWAP(
    data,
    high_column="high",
    low_column="low",
    close_column="close",
    volume_column="volume",
    period=None,
):
    """Volume Weighted Average Price (TA-Lib style)."""
    return calculate_vwap(
        data,
        high_column=high_column,
        low_column=low_column,
        close_column=close_column,
        volume_column=volume_column,
        period=period,
    )


def AD(
    data,
    high_column="high",
    low_column="low",
    close_column="close",
    volume_column="volume",
):
    """Accumulation/Distribution Line (TA-Lib style)."""
    return ADIndicator().calculate(
        data,
        high_column=high_column,
        low_column=low_column,
        close_column=close_column,
        volume_column=volume_column,
    )


def ADOSC(
    data,
    high_column="high",
    low_column="low",
    close_column="close",
    volume_column="volume",
    fast_period=3,
    slow_period=10,
):
    """Accumulation/Distribution Oscillator (TA-Lib style)."""
    return ADOSCIndicator().calculate(
        data,
        high_column=high_column,
        low_column=low_column,
        close_column=close_column,
        volume_column=volume_column,
        fast_period=fast_period,
        slow_period=slow_period,
    )


# Helper functions for indicator discovery
def get_indicator_groups():
    """Get available indicator groups."""
    return {
        "overlap": ["SMA", "EMA", "BBANDS", "DEMA", "TEMA", "WMA", "MIDPOINT"],
        "momentum": ["RSI", "MACD", "STOCH", "WILLR", "CCI", "ROC", "MOM", "STOCHRSI"],
        "volatility": ["ATR", "ADX", "NATR", "TRANGE", "ULTOSC"],
        "volume": ["OBV", "VWAP", "AD", "ADOSC"],
    }


def get_all_indicators():
    """Get list of all available indicators."""
    groups = get_indicator_groups()
    all_indicators = []
    for group_indicators in groups.values():
        all_indicators.extend(group_indicators)
    return sorted(all_indicators)


def get_indicator_info(indicator_name):
    """Get information about a specific indicator."""
    indicator_map = {
        # Overlap Studies
        "SMA": "Simple Moving Average - arithmetic mean of prices over a period",
        "EMA": "Exponential Moving Average - weighted moving average with more weight on recent prices",
        "BBANDS": "Bollinger Bands - moving average with upper and lower bands based on standard deviation",
        "DEMA": "Double Exponential Moving Average - reduces lag of traditional EMA",
        "TEMA": "Triple Exponential Moving Average - further reduces lag compared to DEMA",
        "WMA": "Weighted Moving Average - linear weighted moving average",
        "MIDPOINT": "Midpoint over period - average of highest high and lowest low",
        # Momentum Indicators
        "RSI": "Relative Strength Index - momentum oscillator measuring speed and change of price movements",
        "MACD": "Moving Average Convergence Divergence - trend-following momentum indicator",
        "STOCH": "Stochastic Oscillator - momentum indicator comparing closing price to price range",
        "WILLR": "Williams %R - momentum indicator showing overbought/oversold levels",
        "CCI": "Commodity Channel Index - momentum oscillator identifying cyclical trends",
        "ROC": "Rate of Change - momentum indicator measuring percentage change in price",
        "MOM": "Momentum - measures the amount of change in price over a specified time period",
        "STOCHRSI": "Stochastic RSI - applies Stochastic oscillator formula to RSI values",
        # Volatility Indicators
        "ATR": "Average True Range - measures market volatility by analyzing the range of price movements",
        "ADX": "Average Directional Index - measures trend strength regardless of direction",
        "NATR": "Normalized Average True Range - ATR as percentage of closing price",
        "TRANGE": "True Range - measures the actual range of price movement for a single period",
        "ULTOSC": "Ultimate Oscillator - momentum oscillator using three timeframes",
        # Volume Indicators
        "OBV": "On-Balance Volume - cumulative indicator relating volume to price change",
        "VWAP": "Volume Weighted Average Price - average price weighted by volume",
        "AD": "Accumulation/Distribution Line - volume-based indicator showing money flow",
        "ADOSC": "Accumulation/Distribution Oscillator - difference between fast and slow A/D Line EMAs",
    }

    return indicator_map.get(indicator_name.upper(), "Indicator not found")


# Make the most commonly used indicators easily accessible
__all__ = [
    # Base classes
    "BaseIndicator",
    "IndicatorError",
    "MomentumIndicator",
    "OverlapIndicator",
    "VolatilityIndicator",
    "VolumeIndicator",
    # Class-based indicators (import from modules)
    "SMA",
    "EMA",
    "BBANDS",
    "DEMA",
    "TEMA",
    "WMA",
    "MIDPOINT",
    "RSI",
    "MACD",
    "STOCH",
    "WILLR",
    "CCI",
    "ROC",
    "MOM",
    "STOCHRSI",
    "ATR",
    "ADX",
    "NATR",
    "TRANGE",
    "ULTOSC",
    "OBV",
    "VWAP",
    "AD",
    "ADOSC",
    # Function-based indicators (convenience functions)
    "calculate_sma",
    "calculate_ema",
    "calculate_bollinger_bands",
    "calculate_rsi",
    "calculate_macd",
    "calculate_stochastic",
    "calculate_williams_r",
    "calculate_commodity_channel_index",
    "calculate_atr",
    "calculate_adx",
    "calculate_obv",
    "calculate_vwap",
    # Helper functions
    "get_indicator_groups",
    "get_all_indicators",
    "get_indicator_info",
    # Utilities
    "ema_alpha",
    "safe_division",
]
