"""
ProjectX Indicators - Technical Analysis Library

Author: @TexasCoding
Date: 2025-08-02

Overview:
    ProjectX Indicators provides a comprehensive, extensible technical analysis library
    similar to TA-Lib, built on Polars DataFrames for high-performance financial analysis.
    It offers both class-based and function-based interfaces for over 60 technical indicators,
    with seamless integration for vectorized backtesting and strategy development in ProjectX
    and beyond.

Key Features:
    - Wide range of indicators: trend/overlap, momentum, volatility, volume, and patterns
    - Class-based and TA-Lib-style function interface for flexible usage
    - All indicators operate on Polars DataFrames for speed and modern analytics
    - Utilities for indicator discovery, grouping, and docstring access
    - Clean API and naming convention for easy scripting and research
    - Built-in caching and validation for optimal performance
    - Support for custom indicators through base classes

Indicator Categories:
    - Overlap Studies: SMA, EMA, BBANDS, DEMA, TEMA, WMA, SAR, etc.
    - Momentum Indicators: RSI, MACD, STOCH, CCI, ADX, AROON, etc.
    - Volatility Indicators: ATR, NATR, TRANGE, STDDEV
    - Volume Indicators: OBV, VWAP, AD, ADOSC
    - Pattern Indicators: FVG (Fair Value Gap), ORDERBLOCK, WAE (Waddah Attar Explosion)

Example Usage:
    ```python
    # Class-based interface
    from project_x_py.indicators import RSI, SMA

    rsi = RSI()
    data_with_rsi = rsi.calculate(ohlcv_data, period=14)

    # Function-based interface (TA-Lib style)
    from project_x_py.indicators import calculate_rsi, calculate_sma

    data_with_rsi = calculate_rsi(ohlcv_data, period=14)
    data_with_sma = calculate_sma(ohlcv_data, period=20)

    # Pattern detection
    from project_x_py.indicators import FVG, ORDERBLOCK

    fvg_data = FVG().calculate(ohlcv_data, min_gap_size=0.001)
    order_blocks = ORDERBLOCK().calculate(ohlcv_data, min_volume_percentile=75)
    ```

Performance Notes:
    - All indicators use vectorized operations for optimal speed
    - Built-in caching prevents redundant calculations
    - Memory-efficient Polars DataFrame operations
    - Supports large datasets with minimal memory overhead

See Also:
    - `project_x_py.indicators.base` (abstract base classes/utilities)
    - `project_x_py.indicators.momentum`
    - `project_x_py.indicators.overlap`
    - `project_x_py.indicators.volume`
    - `project_x_py.indicators.volatility`
    - `project_x_py.indicators.order_block`
    - `project_x_py.indicators.fvg`
    - `project_x_py.indicators.waddah_attar`
"""

from typing import Any

import polars as pl

# Base classes and utilities
# Pattern Indicators
from project_x_py.indicators.fvg import FVG as FVGIndicator, calculate_fvg

# Momentum Indicators
from project_x_py.indicators.momentum import (
    # NEW MOMENTUM INDICATORS
    ADX as ADXIndicator,
    ADXR as ADXRIndicator,
    APO as APOIndicator,
    AROON as AROONIndicator,
    AROONOSC as AROONOSCIndicator,
    BOP as BOPIndicator,
    CCI as CCIIndicator,
    CMO as CMOIndicator,
    DX as DXIndicator,
    MACD as MACDIndicator,
    MACDEXT as MACDEXTIndicator,
    MACDFIX as MACDFIXIndicator,
    MFI as MFIIndicator,
    MINUS_DI as MINUS_DIIndicator,
    MINUS_DM as MINUS_DMIndicator,
    MOM as MOMIndicator,
    PLUS_DI as PLUS_DIIndicator,
    PLUS_DM as PLUS_DMIndicator,
    PPO as PPOIndicator,
    ROC as ROCIndicator,
    ROCP as ROCPIndicator,
    ROCR as ROCRIndicator,
    ROCR100 as ROCR100Indicator,
    RSI as RSIIndicator,
    STOCH as STOCHIndicator,
    STOCHF as STOCHFIndicator,
    STOCHRSI as STOCHRSIIndicator,
    TRIX as TRIXIndicator,
    ULTOSC as ULTOSCIndicator,
    WILLR as WILLRIndicator,
    # NEW CONVENIENCE FUNCTIONS
    calculate_adx,
    calculate_aroon,
    calculate_commodity_channel_index,
    calculate_macd,
    calculate_money_flow_index,
    calculate_ppo,
    calculate_rsi,
    calculate_stochastic,
    calculate_ultimate_oscillator,
    calculate_williams_r,
)
from project_x_py.indicators.order_block import (
    OrderBlock as OrderBlockIndicator,
    calculate_order_block,
)

# Overlap Studies (Trend Indicators)
from project_x_py.indicators.overlap import (
    BBANDS as BBANDSIndicator,
    DEMA as DEMAIndicator,
    EMA as EMAIndicator,
    HT_TRENDLINE as HT_TRENDLINEIndicator,
    KAMA as KAMAIndicator,
    MA as MAIndicator,
    MAMA as MAMAIndicator,
    MAVP as MAVPIndicator,
    MIDPOINT as MIDPOINTIndicator,
    MIDPRICE as MIDPRICEIndicator,
    SAR as SARIndicator,
    SAREXT as SAREXTIndicator,
    SMA as SMAIndicator,
    T3 as T3Indicator,
    TEMA as TEMAIndicator,
    TRIMA as TRIMAIndicator,
    WMA as WMAIndicator,
    calculate_bollinger_bands,
    calculate_dema,
    calculate_ema,
    calculate_ht_trendline,
    calculate_kama,
    calculate_ma,
    calculate_mama,
    calculate_midpoint,
    calculate_midprice,
    calculate_sar,
    calculate_sma,
    calculate_t3,
    calculate_tema,
    calculate_trima,
    calculate_wma,
)

# Volatility Indicators
from project_x_py.indicators.volatility import (
    ATR as ATRIndicator,
    NATR as NATRIndicator,
    STDDEV as STDDEVIndicator,
    TRANGE as TRANGEIndicator,
    calculate_atr,
    calculate_stddev,
)

# Volume Indicators
from project_x_py.indicators.volume import (
    AD as ADIndicator,
    ADOSC as ADOSCIndicator,
    OBV as OBVIndicator,
    VWAP as VWAPIndicator,
    calculate_obv,
    calculate_vwap,
)
from project_x_py.indicators.waddah_attar import WAE as WAEIndicator, calculate_wae

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
from .candlestick import (
    BullishEngulfing as BullishEngulfingIndicator,
    Doji as DojiIndicator,
    Hammer as HammerIndicator,
    ShootingStar as ShootingStarIndicator,
    calculate_bullishengulfing,
    calculate_doji,
    calculate_hammer,
    calculate_shootingstar,
)

# Version info
__version__ = "3.3.3"
__author__ = "TexasCoding"


# TA-Lib Style Function Interface
# These functions provide direct access to indicators with TA-Lib naming conventions


# Overlap Studies
def SMA(data: pl.DataFrame, column: str = "close", period: int = 20) -> pl.DataFrame:
    """Simple Moving Average (TA-Lib style)."""
    return calculate_sma(data, column=column, period=period)


def EMA(data: pl.DataFrame, column: str = "close", period: int = 20) -> pl.DataFrame:
    """Exponential Moving Average (TA-Lib style)."""
    return calculate_ema(data, column=column, period=period)


def BBANDS(
    data: pl.DataFrame, column: str = "close", period: int = 20, std_dev: float = 2.0
) -> pl.DataFrame:
    """Bollinger Bands (TA-Lib style)."""
    return calculate_bollinger_bands(
        data, column=column, period=period, std_dev=std_dev
    )


def DEMA(data: pl.DataFrame, column: str = "close", period: int = 20) -> pl.DataFrame:
    """Double Exponential Moving Average (TA-Lib style)."""
    return DEMAIndicator().calculate(data, column=column, period=period)


def TEMA(data: pl.DataFrame, column: str = "close", period: int = 20) -> pl.DataFrame:
    """Triple Exponential Moving Average (TA-Lib style)."""
    return TEMAIndicator().calculate(data, column=column, period=period)


def WMA(data: pl.DataFrame, column: str = "close", period: int = 20) -> pl.DataFrame:
    """Weighted Moving Average (TA-Lib style)."""
    return WMAIndicator().calculate(data, column=column, period=period)


def MIDPOINT(
    data: pl.DataFrame, column: str = "close", period: int = 14
) -> pl.DataFrame:
    """Midpoint over period (TA-Lib style)."""
    return MIDPOINTIndicator().calculate(data, column=column, period=period)


def MIDPRICE(
    data: pl.DataFrame,
    high_column: str = "high",
    low_column: str = "low",
    period: int = 14,
) -> pl.DataFrame:
    """Midpoint Price over period (TA-Lib style)."""
    return MIDPRICEIndicator().calculate(
        data, high_column=high_column, low_column=low_column, period=period
    )


def HT_TRENDLINE(data: pl.DataFrame, column: str = "close") -> pl.DataFrame:
    """Hilbert Transform - Instantaneous Trendline (TA-Lib style)."""
    return HT_TRENDLINEIndicator().calculate(data, column=column)


def KAMA(
    data: pl.DataFrame,
    column: str = "close",
    period: int = 30,
    fast_sc: float = 2.0,
    slow_sc: float = 30.0,
) -> pl.DataFrame:
    """Kaufman Adaptive Moving Average (TA-Lib style)."""
    return KAMAIndicator().calculate(
        data, column=column, period=period, fast_sc=fast_sc, slow_sc=slow_sc
    )


def MA(
    data: pl.DataFrame, column: str = "close", period: int = 30, ma_type: str = "sma"
) -> pl.DataFrame:
    """Moving Average (TA-Lib style)."""
    return MAIndicator().calculate(data, column=column, period=period, ma_type=ma_type)


def MAMA(
    data: pl.DataFrame,
    column: str = "close",
    fast_limit: float = 0.5,
    slow_limit: float = 0.05,
) -> pl.DataFrame:
    """MESA Adaptive Moving Average (TA-Lib style)."""
    return MAMAIndicator().calculate(
        data, column=column, fast_limit=fast_limit, slow_limit=slow_limit
    )


def MAVP(
    data: pl.DataFrame,
    column: str = "close",
    periods_column: str = "periods",
    min_period: int = 2,
    max_period: int = 30,
    ma_type: str = "sma",
) -> pl.DataFrame:
    """Moving Average with Variable Period (TA-Lib style)."""
    return MAVPIndicator().calculate(
        data,
        column=column,
        periods_column=periods_column,
        min_period=min_period,
        max_period=max_period,
        ma_type=ma_type,
    )


def SAR(
    data: pl.DataFrame,
    high_column: str = "high",
    low_column: str = "low",
    acceleration: float = 0.02,
    maximum: float = 0.2,
) -> pl.DataFrame:
    """Parabolic SAR (TA-Lib style)."""
    return SARIndicator().calculate(
        data,
        high_column=high_column,
        low_column=low_column,
        acceleration=acceleration,
        maximum=maximum,
    )


def SAREXT(
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
    """Parabolic SAR - Extended (TA-Lib style)."""
    return SAREXTIndicator().calculate(
        data,
        high_column=high_column,
        low_column=low_column,
        start_value=start_value,
        offset_on_reverse=offset_on_reverse,
        acceleration_init_long=acceleration_init_long,
        acceleration_long=acceleration_long,
        acceleration_max_long=acceleration_max_long,
        acceleration_init_short=acceleration_init_short,
        acceleration_short=acceleration_short,
        acceleration_max_short=acceleration_max_short,
    )


def T3(
    data: pl.DataFrame, column: str = "close", period: int = 5, v_factor: float = 0.7
) -> pl.DataFrame:
    """Triple Exponential Moving Average (T3) (TA-Lib style)."""
    return T3Indicator().calculate(
        data, column=column, period=period, v_factor=v_factor
    )


def TRIMA(data: pl.DataFrame, column: str = "close", period: int = 20) -> pl.DataFrame:
    """Triangular Moving Average (TA-Lib style)."""
    return TRIMAIndicator().calculate(data, column=column, period=period)


# Momentum Indicators
def RSI(data: pl.DataFrame, column: str = "close", period: int = 14) -> pl.DataFrame:
    """Relative Strength Index (TA-Lib style)."""
    return calculate_rsi(data, column=column, period=period)


def MACD(
    data: pl.DataFrame,
    column: str = "close",
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> pl.DataFrame:
    """Moving Average Convergence Divergence (TA-Lib style)."""
    return calculate_macd(
        data,
        column=column,
        fast_period=fast_period,
        slow_period=slow_period,
        signal_period=signal_period,
    )


def STOCH(
    data: pl.DataFrame,
    high_column: str = "high",
    low_column: str = "low",
    close_column: str = "close",
    k_period: int = 14,
    d_period: int = 3,
) -> pl.DataFrame:
    """Stochastic Oscillator (TA-Lib style)."""
    return calculate_stochastic(
        data,
        high_column=high_column,
        low_column=low_column,
        close_column=close_column,
        k_period=k_period,
        d_period=d_period,
    )


def WILLR(
    data: pl.DataFrame,
    high_column: str = "high",
    low_column: str = "low",
    close_column: str = "close",
    period: int = 14,
) -> pl.DataFrame:
    """Williams %R (TA-Lib style)."""
    return calculate_williams_r(
        data,
        high_column=high_column,
        low_column=low_column,
        close_column=close_column,
        period=period,
    )


def CCI(
    data: pl.DataFrame,
    high_column: str = "high",
    low_column: str = "low",
    close_column: str = "close",
    period: int = 20,
    constant: float = 0.015,
) -> pl.DataFrame:
    """Commodity Channel Index (TA-Lib style)."""
    return calculate_commodity_channel_index(
        data,
        high_column=high_column,
        low_column=low_column,
        close_column=close_column,
        period=period,
        constant=constant,
    )


def ROC(data: pl.DataFrame, column: str = "close", period: int = 10) -> pl.DataFrame:
    """Rate of Change (TA-Lib style)."""
    return ROCIndicator().calculate(data, column=column, period=period)


def MOM(data: pl.DataFrame, column: str = "close", period: int = 10) -> pl.DataFrame:
    """Momentum (TA-Lib style)."""
    return MOMIndicator().calculate(data, column=column, period=period)


def STOCHRSI(
    data: pl.DataFrame,
    column: str = "close",
    rsi_period: int = 14,
    stoch_period: int = 14,
    k_period: int = 3,
    d_period: int = 3,
) -> pl.DataFrame:
    """Stochastic RSI (TA-Lib style)."""
    return STOCHRSIIndicator().calculate(
        data,
        column=column,
        rsi_period=rsi_period,
        stoch_period=stoch_period,
        k_period=k_period,
        d_period=d_period,
    )


# NEW MOMENTUM INDICATORS (TA-LIB STYLE)


def ADX(
    data: pl.DataFrame,
    high_column: str = "high",
    low_column: str = "low",
    close_column: str = "close",
    period: int = 14,
) -> pl.DataFrame:
    """Average Directional Movement Index (TA-Lib style)."""
    return calculate_adx(
        data,
        high_column=high_column,
        low_column=low_column,
        close_column=close_column,
        period=period,
    )


def ADXR(
    data: pl.DataFrame,
    high_column: str = "high",
    low_column: str = "low",
    close_column: str = "close",
    period: int = 14,
) -> pl.DataFrame:
    """Average Directional Movement Index Rating (TA-Lib style)."""
    return ADXRIndicator().calculate(
        data,
        high_column=high_column,
        low_column=low_column,
        close_column=close_column,
        period=period,
    )


def APO(
    data: pl.DataFrame,
    column: str = "close",
    fast_period: int = 12,
    slow_period: int = 26,
    ma_type: str = "ema",
) -> pl.DataFrame:
    """Absolute Price Oscillator (TA-Lib style)."""
    return APOIndicator().calculate(
        data,
        column=column,
        fast_period=fast_period,
        slow_period=slow_period,
        ma_type=ma_type,
    )


def AROON(
    data: pl.DataFrame,
    high_column: str = "high",
    low_column: str = "low",
    period: int = 14,
) -> pl.DataFrame:
    """Aroon (TA-Lib style)."""
    return calculate_aroon(
        data,
        high_column=high_column,
        low_column=low_column,
        period=period,
    )


def AROONOSC(
    data: pl.DataFrame,
    high_column: str = "high",
    low_column: str = "low",
    period: int = 14,
) -> pl.DataFrame:
    """Aroon Oscillator (TA-Lib style)."""
    return AROONOSCIndicator().calculate(
        data,
        high_column=high_column,
        low_column=low_column,
        period=period,
    )


def BOP(
    data: pl.DataFrame,
    high_column: str = "high",
    low_column: str = "low",
    open_column: str = "open",
    close_column: str = "close",
) -> pl.DataFrame:
    """Balance of Power (TA-Lib style)."""
    return BOPIndicator().calculate(
        data,
        high_column=high_column,
        low_column=low_column,
        open_column=open_column,
        close_column=close_column,
    )


def CMO(data: pl.DataFrame, column: str = "close", period: int = 14) -> pl.DataFrame:
    """Chande Momentum Oscillator (TA-Lib style)."""
    return CMOIndicator().calculate(data, column=column, period=period)


def DX(
    data: pl.DataFrame,
    high_column: str = "high",
    low_column: str = "low",
    close_column: str = "close",
    period: int = 14,
) -> pl.DataFrame:
    """Directional Movement Index (TA-Lib style)."""
    return DXIndicator().calculate(
        data,
        high_column=high_column,
        low_column=low_column,
        close_column=close_column,
        period=period,
    )


def MACDEXT(
    data: pl.DataFrame,
    column: str = "close",
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
    fast_ma_type: str = "ema",
    slow_ma_type: str = "ema",
    signal_ma_type: str = "ema",
) -> pl.DataFrame:
    """MACD with controllable MA type (TA-Lib style)."""
    return MACDEXTIndicator().calculate(
        data,
        column=column,
        fast_period=fast_period,
        slow_period=slow_period,
        signal_period=signal_period,
        fast_ma_type=fast_ma_type,
        slow_ma_type=slow_ma_type,
        signal_ma_type=signal_ma_type,
    )


def MACDFIX(
    data: pl.DataFrame, column: str = "close", signal_period: int = 9
) -> pl.DataFrame:
    """MACD Fix 12/26 (TA-Lib style)."""
    return MACDFIXIndicator().calculate(
        data, column=column, signal_period=signal_period
    )


def MFI(
    data: pl.DataFrame,
    high_column: str = "high",
    low_column: str = "low",
    close_column: str = "close",
    volume_column: str = "volume",
    period: int = 14,
) -> pl.DataFrame:
    """Money Flow Index (TA-Lib style)."""
    return calculate_money_flow_index(
        data,
        high_column=high_column,
        low_column=low_column,
        close_column=close_column,
        volume_column=volume_column,
        period=period,
    )


def MINUS_DI(
    data: pl.DataFrame,
    high_column: str = "high",
    low_column: str = "low",
    close_column: str = "close",
    period: int = 14,
) -> pl.DataFrame:
    """Minus Directional Indicator (TA-Lib style)."""
    return MINUS_DIIndicator().calculate(
        data,
        high_column=high_column,
        low_column=low_column,
        close_column=close_column,
        period=period,
    )


def MINUS_DM(
    data: pl.DataFrame,
    high_column: str = "high",
    low_column: str = "low",
    period: int = 14,
) -> pl.DataFrame:
    """Minus Directional Movement (TA-Lib style)."""
    return MINUS_DMIndicator().calculate(
        data,
        high_column=high_column,
        low_column=low_column,
        period=period,
    )


def PLUS_DI(
    data: pl.DataFrame,
    high_column: str = "high",
    low_column: str = "low",
    close_column: str = "close",
    period: int = 14,
) -> pl.DataFrame:
    """Plus Directional Indicator (TA-Lib style)."""
    return PLUS_DIIndicator().calculate(
        data,
        high_column=high_column,
        low_column=low_column,
        close_column=close_column,
        period=period,
    )


def PLUS_DM(
    data: pl.DataFrame,
    high_column: str = "high",
    low_column: str = "low",
    period: int = 14,
) -> pl.DataFrame:
    """Plus Directional Movement (TA-Lib style)."""
    return PLUS_DMIndicator().calculate(
        data,
        high_column=high_column,
        low_column=low_column,
        period=period,
    )


def PPO(
    data: pl.DataFrame,
    column: str = "close",
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
    ma_type: str = "ema",
) -> pl.DataFrame:
    """Percentage Price Oscillator (TA-Lib style)."""
    return calculate_ppo(
        data,
        column=column,
        fast_period=fast_period,
        slow_period=slow_period,
        signal_period=signal_period,
    )


def ROCP(data: pl.DataFrame, column: str = "close", period: int = 10) -> pl.DataFrame:
    """Rate of Change Percentage (TA-Lib style)."""
    return ROCPIndicator().calculate(data, column=column, period=period)


def ROCR(data: pl.DataFrame, column: str = "close", period: int = 10) -> pl.DataFrame:
    """Rate of Change Ratio (TA-Lib style)."""
    return ROCRIndicator().calculate(data, column=column, period=period)


def ROCR100(
    data: pl.DataFrame, column: str = "close", period: int = 10
) -> pl.DataFrame:
    """Rate of Change Ratio 100 scale (TA-Lib style)."""
    return ROCR100Indicator().calculate(data, column=column, period=period)


def STOCHF(
    data: pl.DataFrame,
    high_column: str = "high",
    low_column: str = "low",
    close_column: str = "close",
    k_period: int = 14,
    d_period: int = 3,
) -> pl.DataFrame:
    """Stochastic Fast (TA-Lib style)."""
    return STOCHFIndicator().calculate(
        data,
        high_column=high_column,
        low_column=low_column,
        close_column=close_column,
        k_period=k_period,
        d_period=d_period,
    )


def TRIX(data: pl.DataFrame, column: str = "close", period: int = 14) -> pl.DataFrame:
    """TRIX (TA-Lib style)."""
    return TRIXIndicator().calculate(data, column=column, period=period)


def ULTOSC(
    data: pl.DataFrame,
    high_column: str = "high",
    low_column: str = "low",
    close_column: str = "close",
    period1: int = 7,
    period2: int = 14,
    period3: int = 28,
) -> pl.DataFrame:
    """Ultimate Oscillator (TA-Lib style)."""
    return calculate_ultimate_oscillator(
        data,
        high_column=high_column,
        low_column=low_column,
        close_column=close_column,
        period1=period1,
        period2=period2,
        period3=period3,
    )


# Volatility Indicators
def ATR(
    data: pl.DataFrame,
    high_column: str = "high",
    low_column: str = "low",
    close_column: str = "close",
    period: int = 14,
) -> pl.DataFrame:
    """Average True Range (TA-Lib style)."""
    return calculate_atr(
        data,
        high_column=high_column,
        low_column=low_column,
        close_column=close_column,
        period=period,
    )


def NATR(
    data: pl.DataFrame,
    high_column: str = "high",
    low_column: str = "low",
    close_column: str = "close",
    period: int = 14,
) -> pl.DataFrame:
    """Normalized Average True Range (TA-Lib style)."""
    return NATRIndicator().calculate(
        data,
        high_column=high_column,
        low_column=low_column,
        close_column=close_column,
        period=period,
    )


def TRANGE(
    data: pl.DataFrame,
    high_column: str = "high",
    low_column: str = "low",
    close_column: str = "close",
) -> pl.DataFrame:
    """True Range (TA-Lib style)."""
    return TRANGEIndicator().calculate(
        data, high_column=high_column, low_column=low_column, close_column=close_column
    )


def STDDEV(
    data: pl.DataFrame, column: str = "close", period: int = 5, ddof: int = 1
) -> pl.DataFrame:
    """Standard Deviation (TA-Lib style)."""
    return calculate_stddev(data, column=column, period=period, ddof=ddof)


# Volume Indicators
def OBV(
    data: pl.DataFrame, close_column: str = "close", volume_column: str = "volume"
) -> pl.DataFrame:
    """On-Balance Volume (TA-Lib style)."""
    return calculate_obv(data, close_column=close_column, volume_column=volume_column)


def VWAP(
    data: pl.DataFrame,
    high_column: str = "high",
    low_column: str = "low",
    close_column: str = "close",
    volume_column: str = "volume",
    period: int | None = None,
) -> pl.DataFrame:
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
    data: pl.DataFrame,
    high_column: str = "high",
    low_column: str = "low",
    close_column: str = "close",
    volume_column: str = "volume",
) -> pl.DataFrame:
    """Accumulation/Distribution Line (TA-Lib style)."""
    return ADIndicator().calculate(
        data,
        high_column=high_column,
        low_column=low_column,
        close_column=close_column,
        volume_column=volume_column,
    )


def ADOSC(
    data: pl.DataFrame,
    high_column: str = "high",
    low_column: str = "low",
    close_column: str = "close",
    volume_column: str = "volume",
    fast_period: int = 3,
    slow_period: int = 10,
) -> pl.DataFrame:
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


# Pattern Indicators
def FVG(
    data: pl.DataFrame,
    high_column: str = "high",
    low_column: str = "low",
    close_column: str = "close",
    min_gap_size: float = 0.0,
    min_gap_percent: float = 0.0,
    check_mitigation: bool = False,
    mitigation_threshold: float = 0.5,
) -> pl.DataFrame:
    """Fair Value Gap (TA-Lib style) - uses three-candle pattern."""
    return calculate_fvg(
        data,
        high_column=high_column,
        low_column=low_column,
        close_column=close_column,
        min_gap_size=min_gap_size,
        min_gap_percent=min_gap_percent,
        check_mitigation=check_mitigation,
        mitigation_threshold=mitigation_threshold,
    )


def ORDERBLOCK(
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
    """Order Block (TA-Lib style)."""
    return calculate_order_block(
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


def WAE(
    data: pl.DataFrame,
    close_column: str = "close",
    high_column: str = "high",
    low_column: str = "low",
    fast_period: int = 20,
    slow_period: int = 40,
    bb_period: int = 20,
    bb_mult: float = 2.0,
    sensitivity: int = 150,
    dead_zone_period: int = 100,
    dead_zone_mult: float = 3.6,
) -> pl.DataFrame:
    """Waddah Attar Explosion (TA-Lib style)."""
    return calculate_wae(
        data,
        close_column=close_column,
        high_column=high_column,
        low_column=low_column,
        fast_period=fast_period,
        slow_period=slow_period,
        bb_period=bb_period,
        bb_mult=bb_mult,
        sensitivity=sensitivity,
        dead_zone_period=dead_zone_period,
        dead_zone_mult=dead_zone_mult,
    )


def DOJI(data: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
    """Doji candlestick pattern (TA-Lib style)."""
    return calculate_doji(data, **kwargs)


def HAMMER(data: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
    """Hammer candlestick pattern (TA-Lib style)."""
    return calculate_hammer(data, **kwargs)


def SHOOTINGSTAR(data: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
    """Shooting Star candlestick pattern (TA-Lib style)."""
    return calculate_shootingstar(data, **kwargs)


def BULLISHENGULFING(data: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
    """Bullish Engulfing pattern (TA-Lib style)."""
    return calculate_bullishengulfing(data, **kwargs)


# Helper functions for indicator discovery
def get_indicator_groups() -> dict[str, list[str]]:
    """Get available indicator groups."""
    return {
        "overlap": [
            "SMA",
            "EMA",
            "BBANDS",
            "DEMA",
            "TEMA",
            "WMA",
            "MIDPOINT",
            "MIDPRICE",
            "HT_TRENDLINE",
            "KAMA",
            "MA",
            "MAMA",
            "MAVP",
            "SAR",
            "SAREXT",
            "T3",
            "TRIMA",
        ],
        "momentum": [
            "RSI",
            "MACD",
            "STOCH",
            "WILLR",
            "CCI",
            "ROC",
            "MOM",
            "STOCHRSI",
            "ADX",
            "ADXR",
            "APO",
            "AROON",
            "AROONOSC",
            "BOP",
            "CMO",
            "DX",
            "MACDEXT",
            "MACDFIX",
            "MFI",
            "MINUS_DI",
            "MINUS_DM",
            "PLUS_DI",
            "PLUS_DM",
            "PPO",
            "ROCP",
            "ROCR",
            "ROCR100",
            "STOCHF",
            "TRIX",
            "ULTOSC",
        ],
        "volatility": ["ATR", "NATR", "TRANGE", "STDDEV"],
        "volume": ["OBV", "VWAP", "AD", "ADOSC"],
        "patterns": [
            "FVG",
            "ORDERBLOCK",
            "WAE",
            "DOJI",
            "HAMMER",
            "SHOOTINGSTAR",
            "BULLISHENGULFING",
        ],
    }


def get_all_indicators() -> list[str]:
    """Get list of all available indicators."""
    groups = get_indicator_groups()
    all_indicators = []
    for group_indicators in groups.values():
        all_indicators.extend(group_indicators)
    return sorted(all_indicators)


def get_indicator_info(indicator_name: str) -> str:
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
        "MIDPRICE": "Midpoint Price over period - average of highest high and lowest low",
        "HT_TRENDLINE": "Hilbert Transform - Instantaneous Trendline - trendline based on Hilbert transform",
        "KAMA": "Kaufman Adaptive Moving Average - adaptive moving average that reacts to market volatility",
        "MA": "Moving Average - simple moving average of prices",
        "MAMA": "MESA Adaptive Moving Average - adaptive moving average using MESA algorithm",
        "MAVP": "Moving Average with Variable Period - moving average with customizable periods",
        "SAR": "Parabolic SAR - trend-following indicator",
        "SAREXT": "Parabolic SAR - Extended - extended version of Parabolic SAR",
        "T3": "Triple Exponential Moving Average (T3) - further reduces lag compared to TEMA",
        "TRIMA": "Triangular Moving Average - weighted moving average of prices",
        # Momentum Indicators
        "RSI": "Relative Strength Index - momentum oscillator measuring speed and change of price movements",
        "MACD": "Moving Average Convergence Divergence - trend-following momentum indicator",
        "STOCH": "Stochastic Oscillator - momentum indicator comparing closing price to price range",
        "WILLR": "Williams %R - momentum indicator showing overbought/oversold levels",
        "CCI": "Commodity Channel Index - momentum oscillator identifying cyclical trends",
        "ROC": "Rate of Change - momentum indicator measuring percentage change in price",
        "MOM": "Momentum - measures the amount of change in price over a specified time period",
        "STOCHRSI": "Stochastic RSI - applies Stochastic oscillator formula to RSI values",
        "ADX": "Average Directional Movement Index - measures trend strength regardless of direction",
        "ADXR": "Average Directional Movement Index Rating - smoothed version of ADX",
        "APO": "Absolute Price Oscillator - difference between fast and slow EMA",
        "AROON": "Aroon - identifies when trends are likely to change direction",
        "AROONOSC": "Aroon Oscillator - difference between Aroon Up and Aroon Down",
        "BOP": "Balance of Power - measures buying vs selling pressure",
        "CMO": "Chande Momentum Oscillator - momentum indicator without smoothing",
        "DX": "Directional Movement Index - measures directional movement",
        "MACDEXT": "MACD with controllable MA type - extended MACD with different MA types",
        "MACDFIX": "MACD Fix 12/26 - MACD with fixed 12/26 periods",
        "MFI": "Money Flow Index - volume-weighted RSI",
        "MINUS_DI": "Minus Directional Indicator - measures negative directional movement",
        "MINUS_DM": "Minus Directional Movement - raw negative directional movement",
        "PLUS_DI": "Plus Directional Indicator - measures positive directional movement",
        "PLUS_DM": "Plus Directional Movement - raw positive directional movement",
        "PPO": "Percentage Price Oscillator - percentage difference between fast and slow MA",
        "ROCP": "Rate of Change Percentage - (price-prevPrice)/prevPrice",
        "ROCR": "Rate of Change Ratio - price/prevPrice",
        "ROCR100": "Rate of Change Ratio 100 scale - (price/prevPrice)*100",
        "STOCHF": "Stochastic Fast - fast stochastic without smoothing",
        "TRIX": "TRIX - 1-day Rate-Of-Change of a Triple Smooth EMA",
        "ULTOSC": "Ultimate Oscillator - momentum oscillator using three timeframes",
        # Volatility Indicators
        "ATR": "Average True Range - measures market volatility by analyzing the range of price movements",
        "NATR": "Normalized Average True Range - ATR as percentage of closing price",
        "TRANGE": "True Range - measures the actual range of price movement for a single period",
        "STDDEV": "Standard Deviation - measures the dispersion of prices from the mean",
        # Volume Indicators
        "OBV": "On-Balance Volume - cumulative indicator relating volume to price change",
        "VWAP": "Volume Weighted Average Price - average price weighted by volume",
        "AD": "Accumulation/Distribution Line - volume-based indicator showing money flow",
        "ADOSC": "Accumulation/Distribution Oscillator - difference between fast and slow A/D Line EMAs",
        # Pattern Indicators
        "FVG": "Fair Value Gap - identifies price imbalance areas that may act as support/resistance",
        "ORDERBLOCK": "Order Block - identifies institutional order zones based on price action patterns",
        "WAE": "Waddah Attar Explosion - identifies strong trends and breakouts using MACD and Bollinger Bands",
        "DOJI": "Doji - indecision pattern with open and close nearly equal",
        "HAMMER": "Hammer - bullish reversal with long lower shadow",
        "SHOOTINGSTAR": "Shooting Star - bearish reversal with long upper shadow",
        "BULLISHENGULFING": "Bullish Engulfing - bullish reversal pattern",
    }

    return indicator_map.get(indicator_name.upper(), "Indicator not found")


# Make the most commonly used indicators easily accessible
__all__ = [
    "AD",
    "ADOSC",
    "ADX",
    "ATR",
    "BBANDS",
    "BULLISHENGULFING",
    "CCI",
    "DEMA",
    "DOJI",
    "EMA",
    "FVG",
    "HAMMER",
    "HT_TRENDLINE",
    "KAMA",
    "MA",
    "MACD",
    "MAMA",
    "MAVP",
    "MIDPOINT",
    "MIDPRICE",
    "MOM",
    "NATR",
    "OBV",
    "ORDERBLOCK",
    "ROC",
    "RSI",
    "SAR",
    "SAREXT",
    "SHOOTINGSTAR",
    # Class-based indicators (import from modules)
    "SMA",
    "STDDEV",
    "STOCH",
    "STOCHRSI",
    "T3",
    "TEMA",
    "TRANGE",
    "TRIMA",
    "ULTOSC",
    "VWAP",
    "WAE",
    "WILLR",
    "WMA",
    # Base classes
    "BaseIndicator",
    "IndicatorError",
    "MomentumIndicator",
    "OverlapIndicator",
    "VolatilityIndicator",
    "VolumeIndicator",
    "calculate_adx",
    "calculate_aroon",
    "calculate_atr",
    "calculate_bollinger_bands",
    "calculate_bullishengulfing",
    "calculate_commodity_channel_index",
    "calculate_dema",
    "calculate_doji",
    "calculate_ema",
    "calculate_fvg",
    "calculate_hammer",
    "calculate_ht_trendline",
    "calculate_kama",
    "calculate_ma",
    "calculate_macd",
    "calculate_mama",
    "calculate_midpoint",
    "calculate_midprice",
    "calculate_money_flow_index",
    "calculate_obv",
    "calculate_order_block",
    "calculate_ppo",
    "calculate_rsi",
    "calculate_sar",
    "calculate_shootingstar",
    # Function-based indicators (convenience functions)
    "calculate_sma",
    "calculate_stddev",
    "calculate_stochastic",
    "calculate_t3",
    "calculate_tema",
    "calculate_trima",
    "calculate_ultimate_oscillator",
    "calculate_vwap",
    "calculate_wae",
    "calculate_williams_r",
    "calculate_wma",
    # Utilities
    "ema_alpha",
    "get_all_indicators",
    # Helper functions
    "get_indicator_groups",
    "get_indicator_info",
    "safe_division",
]
