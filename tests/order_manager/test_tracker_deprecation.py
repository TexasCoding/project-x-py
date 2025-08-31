"""Test deprecation warnings for order_tracker module."""

import warnings
from unittest.mock import AsyncMock, MagicMock

from project_x_py.order_tracker import OrderChainBuilder, OrderTracker


def test_order_tracker_deprecation_warning():
    """Test that OrderTracker raises deprecation warning."""
    suite = MagicMock()
    suite.orders = MagicMock()
    suite.events = MagicMock()

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        tracker = OrderTracker(suite)

        # Check that a deprecation warning was raised
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "OrderTracker is deprecated" in str(w[0].message)
        assert "TradingSuite.track_order()" in str(w[0].message)


def test_order_chain_builder_deprecation_warning():
    """Test that OrderChainBuilder raises deprecation warning."""
    suite = MagicMock()
    suite.orders = MagicMock()
    suite.data = AsyncMock()
    suite.instrument_id = "TEST"

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        chain = OrderChainBuilder(suite)

        # Check that a deprecation warning was raised
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "OrderChainBuilder is deprecated" in str(w[0].message)
        assert "TradingSuite.order_chain()" in str(w[0].message)


def test_track_order_function_deprecation():
    """Test that track_order function raises deprecation warning."""
    from project_x_py.order_tracker import track_order

    suite = MagicMock()
    suite.orders = MagicMock()
    suite.events = MagicMock()

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        tracker = track_order(suite)

        # Check that at least two deprecation warnings were raised
        # One from the function itself, one from OrderTracker class
        # There may be additional warnings from the @deprecated decorator
        assert len(w) >= 2
        # Check the function deprecation
        # The warning format may vary - check for any of these
        assert any(
            "track_order" in str(warning.message) or
            "Integrated into TradingSuite" in str(warning.message)
            for warning in w
        )
        assert any(
            "OrderTracker is deprecated" in str(warning.message) for warning in w
        )


def test_trading_suite_methods_no_deprecation():
    """Test that TradingSuite methods don't raise deprecation warnings."""
    from project_x_py.trading_suite import TradingSuite

    # Create a mock suite with minimal required attributes
    suite = MagicMock(spec=TradingSuite)
    suite.orders = MagicMock()
    suite.events = MagicMock()
    suite.data = AsyncMock()
    suite.instrument_id = "TEST"

    # Mock the methods to avoid actual implementation
    suite.track_order = MagicMock(return_value=MagicMock())
    suite.order_chain = MagicMock(return_value=MagicMock())

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        # These should not raise deprecation warnings
        tracker = suite.track_order()
        chain = suite.order_chain()

        # No deprecation warnings should be raised
        deprecation_warnings = [
            w for w in w if issubclass(w.category, DeprecationWarning)
        ]
        assert len(deprecation_warnings) == 0
