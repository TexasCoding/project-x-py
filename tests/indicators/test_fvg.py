"""FVG must require the middle candle not to fill the zone."""

import polars as pl

from project_x_py.indicators import FVG


def _bars(rows: list[tuple[float, float, float, float]]) -> pl.DataFrame:
    """rows: (open, high, low, close)."""
    return pl.DataFrame(
        {
            "open": [r[0] for r in rows],
            "high": [r[1] for r in rows],
            "low": [r[2] for r in rows],
            "close": [r[3] for r in rows],
            "volume": [100] * len(rows),
        }
    )


def test_bullish_fvg_requires_middle_candle_not_fill():
    # c1 high=100, c3 low=102 → gap. Middle low stays above 100 → valid.
    valid = _bars(
        [
            (99.0, 100.0, 98.0, 99.5),
            (100.5, 105.0, 100.5, 104.0),
            (104.0, 106.0, 102.0, 105.0),
        ]
    )
    result = FVG(valid)
    assert result["fvg_bullish"][2] is True

    # Same gap but middle wick fills down through candle1 high.
    filled = _bars(
        [
            (99.0, 100.0, 98.0, 99.5),
            (100.5, 105.0, 99.0, 104.0),
            (104.0, 106.0, 102.0, 105.0),
        ]
    )
    filled_result = FVG(filled)
    assert filled_result["fvg_bullish"][2] is False


def test_bearish_fvg_requires_middle_candle_not_fill():
    # c1 low=100, c3 high=98 → gap. Middle high stays below 100 → valid.
    valid = _bars(
        [
            (101.0, 102.0, 100.0, 100.5),
            (99.5, 99.5, 95.0, 96.0),
            (96.0, 98.0, 94.0, 95.0),
        ]
    )
    result = FVG(valid)
    assert result["fvg_bearish"][2] is True

    # Middle wick rallies into candle1 low.
    filled = _bars(
        [
            (101.0, 102.0, 100.0, 100.5),
            (99.5, 101.0, 95.0, 96.0),
            (96.0, 98.0, 94.0, 95.0),
        ]
    )
    filled_result = FVG(filled)
    assert filled_result["fvg_bearish"][2] is False


def test_mitigation_sets_flag_without_wiping_historical_fvg():
    data = _bars(
        [
            (99.0, 100.0, 98.0, 99.5),
            (100.5, 105.0, 100.5, 104.0),
            (104.0, 106.0, 102.0, 105.0),
            (101.0, 103.0, 99.5, 100.0),  # retrace into the gap
        ]
    )
    result = FVG(data, check_mitigation=True)
    assert result["fvg_bullish"][2] is True
    assert "fvg_mitigated" in result.columns
    assert result["fvg_mitigated"][2] is True
