"""WAE explosion formula and short-frame warmup."""

import polars as pl
import pytest

from project_x_py.indicators import WAE


def test_wae_explosion_matches_documented_formula():
    n = 50
    closes = [100.0 + i * 0.5 for i in range(n)]
    data = pl.DataFrame(
        {
            "open": closes,
            "high": [c + 1.0 for c in closes],
            "low": [c - 1.0 for c in closes],
            "close": closes,
            "volume": [100] * n,
        }
    )
    fast_period, slow_period, bb_period = 5, 10, 8
    bb_mult, sensitivity = 2.0, 150
    result = WAE(
        data,
        fast_period=fast_period,
        slow_period=slow_period,
        bb_period=bb_period,
        bb_mult=bb_mult,
        sensitivity=sensitivity,
        dead_zone_period=10,
        dead_zone_mult=3.6,
    )
    assert "wae_explosion" in result.columns
    # Last bar: compute formula independently.
    ema_fast = data["close"].ewm_mean(alpha=2.0 / (fast_period + 1), adjust=False)
    ema_slow = data["close"].ewm_mean(alpha=2.0 / (slow_period + 1), adjust=False)
    macd = (ema_fast - ema_slow).to_list()[-1]
    bb_std = data["close"].rolling_std(window_size=bb_period).to_list()[-1]
    bb_width = 2.0 * bb_mult * bb_std
    expected = bb_width * abs(macd) * sensitivity / bb_period
    assert result["wae_explosion"][-1] == pytest.approx(expected, rel=1e-6)


def test_wae_does_not_require_100_bar_warmup():
    n = 50
    data = pl.DataFrame(
        {
            "open": [float(i) for i in range(n)],
            "high": [float(i) + 1 for i in range(n)],
            "low": [float(i) - 1 for i in range(n)],
            "close": [float(i) + 0.5 for i in range(n)],
            "volume": [100] * n,
        }
    )
    result = WAE(data)  # default dead_zone_period=100
    assert result.height == n
    assert "wae_explosion" in result.columns
