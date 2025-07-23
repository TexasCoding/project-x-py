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

# Overlap Studies (Trend Indicators)
from .overlap import (
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
from .volatility import (
    ATR as ATRIndicator,
    NATR as NATRIndicator,
    TRANGE as TRANGEIndicator,
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
__version__ = "1.0.9"
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


def MIDPRICE(data, high_column="high", low_column="low", period=14):
    """Midpoint Price over period (TA-Lib style)."""
    return MIDPRICEIndicator().calculate(
        data, high_column=high_column, low_column=low_column, period=period
    )


def HT_TRENDLINE(data, column="close"):
    """Hilbert Transform - Instantaneous Trendline (TA-Lib style)."""
    return HT_TRENDLINEIndicator().calculate(data, column=column)


def KAMA(data, column="close", period=30, fast_sc=2.0, slow_sc=30.0):
    """Kaufman Adaptive Moving Average (TA-Lib style)."""
    return KAMAIndicator().calculate(
        data, column=column, period=period, fast_sc=fast_sc, slow_sc=slow_sc
    )


def MA(data, column="close", period=30, ma_type="sma"):
    """Moving Average (TA-Lib style)."""
    return MAIndicator().calculate(data, column=column, period=period, ma_type=ma_type)


def MAMA(data, column="close", fast_limit=0.5, slow_limit=0.05):
    """MESA Adaptive Moving Average (TA-Lib style)."""
    return MAMAIndicator().calculate(
        data, column=column, fast_limit=fast_limit, slow_limit=slow_limit
    )


def MAVP(
    data,
    column="close",
    periods_column="periods",
    min_period=2,
    max_period=30,
    ma_type="sma",
):
    """Moving Average with Variable Period (TA-Lib style)."""
    return MAVPIndicator().calculate(
        data,
        column=column,
        periods_column=periods_column,
        min_period=min_period,
        max_period=max_period,
        ma_type=ma_type,
    )


def SAR(data, high_column="high", low_column="low", acceleration=0.02, maximum=0.2):
    """Parabolic SAR (TA-Lib style)."""
    return SARIndicator().calculate(
        data,
        high_column=high_column,
        low_column=low_column,
        acceleration=acceleration,
        maximum=maximum,
    )


def SAREXT(
    data,
    high_column="high",
    low_column="low",
    start_value=0.0,
    offset_on_reverse=0.0,
    acceleration_init_long=0.02,
    acceleration_long=0.02,
    acceleration_max_long=0.2,
    acceleration_init_short=0.02,
    acceleration_short=0.02,
    acceleration_max_short=0.2,
):
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


def T3(data, column="close", period=5, v_factor=0.7):
    """Triple Exponential Moving Average (T3) (TA-Lib style)."""
    return T3Indicator().calculate(
        data, column=column, period=period, v_factor=v_factor
    )


def TRIMA(data, column="close", period=20):
    """Triangular Moving Average (TA-Lib style)."""
    return TRIMAIndicator().calculate(data, column=column, period=period)


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


# NEW MOMENTUM INDICATORS (TA-LIB STYLE)


def ADX(data, high_column="high", low_column="low", close_column="close", period=14):
    """Average Directional Movement Index (TA-Lib style)."""
    return calculate_adx(
        data,
        high_column=high_column,
        low_column=low_column,
        close_column=close_column,
        period=period,
    )


def ADXR(data, high_column="high", low_column="low", close_column="close", period=14):
    """Average Directional Movement Index Rating (TA-Lib style)."""
    return ADXRIndicator().calculate(
        data,
        high_column=high_column,
        low_column=low_column,
        close_column=close_column,
        period=period,
    )


def APO(data, column="close", fast_period=12, slow_period=26, ma_type="ema"):
    """Absolute Price Oscillator (TA-Lib style)."""
    return APOIndicator().calculate(
        data,
        column=column,
        fast_period=fast_period,
        slow_period=slow_period,
        ma_type=ma_type,
    )


def AROON(data, high_column="high", low_column="low", period=14):
    """Aroon (TA-Lib style)."""
    return calculate_aroon(
        data,
        high_column=high_column,
        low_column=low_column,
        period=period,
    )


def AROONOSC(data, high_column="high", low_column="low", period=14):
    """Aroon Oscillator (TA-Lib style)."""
    return AROONOSCIndicator().calculate(
        data,
        high_column=high_column,
        low_column=low_column,
        period=period,
    )


def BOP(
    data, high_column="high", low_column="low", open_column="open", close_column="close"
):
    """Balance of Power (TA-Lib style)."""
    return BOPIndicator().calculate(
        data,
        high_column=high_column,
        low_column=low_column,
        open_column=open_column,
        close_column=close_column,
    )


def CMO(data, column="close", period=14):
    """Chande Momentum Oscillator (TA-Lib style)."""
    return CMOIndicator().calculate(data, column=column, period=period)


def DX(data, high_column="high", low_column="low", close_column="close", period=14):
    """Directional Movement Index (TA-Lib style)."""
    return DXIndicator().calculate(
        data,
        high_column=high_column,
        low_column=low_column,
        close_column=close_column,
        period=period,
    )


def MACDEXT(
    data,
    column="close",
    fast_period=12,
    slow_period=26,
    signal_period=9,
    fast_ma_type="ema",
    slow_ma_type="ema",
    signal_ma_type="ema",
):
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


def MACDFIX(data, column="close", signal_period=9):
    """MACD Fix 12/26 (TA-Lib style)."""
    return MACDFIXIndicator().calculate(
        data, column=column, signal_period=signal_period
    )


def MFI(
    data,
    high_column="high",
    low_column="low",
    close_column="close",
    volume_column="volume",
    period=14,
):
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
    data, high_column="high", low_column="low", close_column="close", period=14
):
    """Minus Directional Indicator (TA-Lib style)."""
    return MINUS_DIIndicator().calculate(
        data,
        high_column=high_column,
        low_column=low_column,
        close_column=close_column,
        period=period,
    )


def MINUS_DM(data, high_column="high", low_column="low", period=14):
    """Minus Directional Movement (TA-Lib style)."""
    return MINUS_DMIndicator().calculate(
        data,
        high_column=high_column,
        low_column=low_column,
        period=period,
    )


def PLUS_DI(
    data, high_column="high", low_column="low", close_column="close", period=14
):
    """Plus Directional Indicator (TA-Lib style)."""
    return PLUS_DIIndicator().calculate(
        data,
        high_column=high_column,
        low_column=low_column,
        close_column=close_column,
        period=period,
    )


def PLUS_DM(data, high_column="high", low_column="low", period=14):
    """Plus Directional Movement (TA-Lib style)."""
    return PLUS_DMIndicator().calculate(
        data,
        high_column=high_column,
        low_column=low_column,
        period=period,
    )


def PPO(
    data, column="close", fast_period=12, slow_period=26, signal_period=9, ma_type="ema"
):
    """Percentage Price Oscillator (TA-Lib style)."""
    return calculate_ppo(
        data,
        column=column,
        fast_period=fast_period,
        slow_period=slow_period,
        signal_period=signal_period,
    )


def ROCP(data, column="close", period=10):
    """Rate of Change Percentage (TA-Lib style)."""
    return ROCPIndicator().calculate(data, column=column, period=period)


def ROCR(data, column="close", period=10):
    """Rate of Change Ratio (TA-Lib style)."""
    return ROCRIndicator().calculate(data, column=column, period=period)


def ROCR100(data, column="close", period=10):
    """Rate of Change Ratio 100 scale (TA-Lib style)."""
    return ROCR100Indicator().calculate(data, column=column, period=period)


def STOCHF(
    data,
    high_column="high",
    low_column="low",
    close_column="close",
    k_period=14,
    d_period=3,
):
    """Stochastic Fast (TA-Lib style)."""
    return STOCHFIndicator().calculate(
        data,
        high_column=high_column,
        low_column=low_column,
        close_column=close_column,
        k_period=k_period,
        d_period=d_period,
    )


def TRIX(data, column="close", period=14):
    """TRIX (TA-Lib style)."""
    return TRIXIndicator().calculate(data, column=column, period=period)


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
def ATR(data, high_column="high", low_column="low", close_column="close", period=14):
    """Average True Range (TA-Lib style)."""
    return calculate_atr(
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
        "volatility": ["ATR", "NATR", "TRANGE"],
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
    "calculate_dema",
    "calculate_tema",
    "calculate_wma",
    "calculate_midpoint",
    "calculate_midprice",
    "calculate_ht_trendline",
    "calculate_kama",
    "calculate_ma",
    "calculate_mama",
    "calculate_sar",
    "calculate_t3",
    "calculate_trima",
    "calculate_rsi",
    "calculate_macd",
    "calculate_stochastic",
    "calculate_williams_r",
    "calculate_commodity_channel_index",
    "calculate_atr",
    "calculate_adx",
    "calculate_aroon",
    "calculate_money_flow_index",
    "calculate_ppo",
    "calculate_ultimate_oscillator",
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
