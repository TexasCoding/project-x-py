"""Order Block type is mutually exclusive; 5-bar fixture."""

import polars as pl

from project_x_py.indicators import ORDERBLOCK


def test_five_bar_fixture_mutually_exclusive_types():
    # Bar 0: down candle → bullish OB once bar 1 breaks its high.
    # Bar 2: up candle → bearish OB once bar 3 breaks its low.
    data = pl.DataFrame(
        {
            "open": [105.0, 101.0, 107.0, 109.0, 105.0],
            "high": [106.0, 108.0, 110.0, 110.0, 106.0],
            "low": [100.0, 101.0, 106.0, 104.0, 103.0],
            "close": [101.0, 107.0, 109.0, 105.0, 104.0],
            "volume": [1000, 800, 700, 900, 600],
        }
    )
    result = ORDERBLOCK(data, min_volume_percentile=0, lookback_periods=2)

    both = result.filter(pl.col("ob_bullish") & pl.col("ob_bearish"))
    assert both.height == 0

    assert result["ob_bullish"][0] is True
    assert result["ob_bearish"][0] is False
    assert result["ob_bearish"][2] is True
    assert result["ob_bullish"][2] is False
