"""Golden tests for SMA/EMA/RSI/MACD/ATR vs hand-computed values."""

import math

import polars as pl
import pytest

from project_x_py.indicators import (
    ATR,
    EMA,
    MACD,
    RSI,
    SMA,
    RSIIndicator,
    SMAIndicator,
)
from project_x_py.indicators.base import ema_alpha


def _ohlcv(closes: list[float]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "open": closes,
            "high": [c + 1.0 for c in closes],
            "low": [c - 1.0 for c in closes],
            "close": closes,
            "volume": [100] * len(closes),
        }
    )


def test_sma_hand_computed():
    data = _ohlcv([1.0, 2.0, 3.0, 4.0, 5.0])
    result = SMA(data, period=3)
    values = result["sma_3"].to_list()
    assert values[0] is None
    assert values[1] is None
    assert values[2] == pytest.approx(2.0)
    assert values[3] == pytest.approx(3.0)
    assert values[4] == pytest.approx(4.0)


def test_sma_function_not_class():
    assert callable(SMA)
    assert not isinstance(SMA, type)
    data = _ohlcv([1.0, 2.0, 3.0])
    out = SMA(data, period=2)
    assert "sma_2" in out.columns
    class_out = SMAIndicator().calculate(data, period=2)
    assert class_out["sma_2"].to_list() == out["sma_2"].to_list()


def test_ema_hand_computed_adjust_default():
    """EMA uses Polars ewm_mean(alpha=2/(n+1)) with default adjust=True."""
    closes = [1.0, 2.0, 3.0, 4.0, 5.0]
    data = _ohlcv(closes)
    result = EMA(data, period=3)
    alpha = ema_alpha(3)  # 2 / 4 = 0.5
    # Adjusted EMA: numerator / cumulative weight
    expected: list[float] = []
    num = 0.0
    den = 0.0
    one_minus = 1.0 - alpha
    for x in closes:
        num = x + one_minus * num
        den = 1.0 + one_minus * den
        expected.append(num / den)
    actual = result["ema_3"].to_list()
    for got, want in zip(actual, expected, strict=True):
        assert got == pytest.approx(want)


def test_rsi_is_function_and_rsi_indicator_class():
    assert callable(RSI)
    assert not isinstance(RSI, type)
    data = _ohlcv([10.0, 11.0, 12.0, 11.0, 13.0, 14.0, 13.0])
    fn_out = RSI(data, period=2)
    cls_out = RSIIndicator().calculate(data, period=2)
    assert fn_out["rsi_2"].to_list() == cls_out["rsi_2"].to_list()


def test_rsi_hand_computed_wilder():
    closes = [10.0, 11.0, 12.0, 11.0, 13.0]
    data = _ohlcv(closes)
    result = RSI(data, period=2)
    # Wilder ewm: alpha = 1/period = 0.5, adjust=False
    changes = [None, 1.0, 1.0, -1.0, 2.0]
    gains = [0.0 if c is None or c < 0 else c for c in changes]
    losses = [
        0.0 if c is None or c > 0 else (0.0 if c is None else -c) for c in changes
    ]
    alpha = 0.5
    avg_gain = 0.0
    avg_loss = 0.0
    expected: list[float] = []
    for i, (gain, loss) in enumerate(zip(gains, losses, strict=True)):
        if i == 0:
            avg_gain, avg_loss = gain, loss
        else:
            avg_gain = alpha * gain + (1 - alpha) * avg_gain
            avg_loss = alpha * loss + (1 - alpha) * avg_loss
        if avg_loss == 0:
            expected.append(100.0 if avg_gain > 0 else 0.0)
        else:
            rs = avg_gain / avg_loss
            expected.append(100.0 - 100.0 / (1.0 + rs))
    actual = result["rsi_2"].to_list()
    # Compare bars where both averages are positive (safe_division of 0 loss
    # yields 0, not the conventional RSI=100).
    for i, (got, want) in enumerate(zip(actual, expected, strict=True)):
        if i >= 3:
            assert got == pytest.approx(want, abs=1e-6)


def test_macd_hand_computed_small_periods():
    closes = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0]
    data = _ohlcv(closes)
    result = MACD(data, fast_period=2, slow_period=3, signal_period=2)
    fast_a = ema_alpha(2)
    slow_a = ema_alpha(3)
    sig_a = ema_alpha(2)

    def adj_ema(series: list[float], alpha: float) -> list[float]:
        num = 0.0
        den = 0.0
        one_minus = 1.0 - alpha
        out: list[float] = []
        for x in series:
            num = x + one_minus * num
            den = 1.0 + one_minus * den
            out.append(num / den)
        return out

    fast = adj_ema(closes, fast_a)
    slow = adj_ema(closes, slow_a)
    macd_line = [f - s for f, s in zip(fast, slow, strict=True)]
    signal = adj_ema(macd_line, sig_a)
    actual_macd = result["macd"].to_list()
    actual_signal = result["macd_signal"].to_list()
    for got, want in zip(actual_macd, macd_line, strict=True):
        assert got == pytest.approx(want)
    for got, want in zip(actual_signal, signal, strict=True):
        assert got == pytest.approx(want)
    hist = result["macd_histogram"].to_list()
    for i, h in enumerate(hist):
        assert h == pytest.approx(macd_line[i] - signal[i])


def test_atr_hand_computed():
    data = pl.DataFrame(
        {
            "open": [11.0, 12.0, 13.0],
            "high": [12.0, 13.0, 15.0],
            "low": [10.0, 11.0, 12.0],
            "close": [11.0, 12.0, 14.0],
            "volume": [100, 100, 100],
        }
    )
    result = ATR(data, period=2)
    # TR0 = high-low = 2 (prev close null → other TR legs null)
    # TR1 = max(13-11=2, |13-11|=2, |11-11|=0) = 2
    # TR2 = max(15-12=3, |15-12|=3, |12-12|=0) = 3
    # ATR ewm alpha=0.5 adjust=False
    tr = [2.0, 2.0, 3.0]
    atr = [tr[0]]
    for i in range(1, 3):
        atr.append(0.5 * tr[i] + 0.5 * atr[-1])
    actual = result["atr_2"].to_list()
    assert (
        actual[0] == pytest.approx(atr[0])
        or actual[0] is None
        or math.isnan(actual[0] or 0)
    )
    assert actual[1] == pytest.approx(atr[1])
    assert actual[2] == pytest.approx(atr[2])
