"""Test deprecation warnings for order_tracker module."""

import warnings
from unittest.mock import AsyncMock, MagicMock

from project_x_py.order_tracker import OrderChainBuilder, OrderTracker
from project_x_py.trading_suite import TradingSuite


def test_order_tracker_is_official_api_no_class_deprecation():
    """OrderTracker is the suite API; constructing it must not warn."""
    suite = MagicMock()
    suite.orders = MagicMock()
    suite.events = MagicMock()

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        tracker = OrderTracker(suite)

    deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
    assert deprecation_warnings == []
    assert tracker.suite is suite


def test_order_chain_builder_is_official_api_no_class_deprecation():
    """OrderChainBuilder is the suite API; constructing it must not warn."""
    suite = MagicMock()
    suite.orders = MagicMock()
    suite.data = AsyncMock()
    suite.instrument_id = "TEST"

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        chain = OrderChainBuilder(suite)

    deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
    assert deprecation_warnings == []
    assert chain.suite is suite


def test_track_order_function_deprecation():
    """Standalone track_order helper remains deprecated."""
    from project_x_py.order_tracker import track_order

    suite = MagicMock()
    suite.orders = MagicMock()
    suite.events = MagicMock()

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        tracker = track_order(suite)

    assert any(
        "track_order" in str(warning.message)
        or "Integrated into TradingSuite" in str(warning.message)
        or "TradingSuite.track_order()" in str(warning.message)
        for warning in w
        if issubclass(warning.category, DeprecationWarning)
    )
    assert isinstance(tracker, OrderTracker)


def test_trading_suite_methods_no_deprecation():
    """Real TradingSuite.track_order / order_chain must not warn."""
    suite = MagicMock()
    suite.orders = MagicMock()
    suite.events = MagicMock()
    suite.data = AsyncMock()
    suite.instrument_id = "TEST"

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        tracker = TradingSuite.track_order(suite)
        chain = TradingSuite.order_chain(suite)

    deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
    assert deprecation_warnings == []
    assert isinstance(tracker, OrderTracker)
    assert isinstance(chain, OrderChainBuilder)
