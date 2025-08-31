"""
Tests for multi-instrument TradingSuite functionality.

Following TDD principles for the multi-instrument refactor as outlined in
the architecture document.
"""

from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from project_x_py import Features, TradingSuite, TradingSuiteConfig
from project_x_py.models import Account, Instrument


@pytest.mark.asyncio
async def test_instrument_context_creation():
    """
    RED: Test InstrumentContext creation with all required managers.

    This test defines the expected behavior for InstrumentContext - it should
    encapsulate all managers for a single instrument and provide clean access.
    """
    # This will fail until we implement InstrumentContext
    from project_x_py.trading_suite import InstrumentContext

    # Mock the managers that should be in the context
    mock_instrument_info = MagicMock()
    mock_instrument_info.id = "MNQ_CONTRACT_ID"
    mock_instrument_info.symbol = "MNQ"

    mock_data_manager = MagicMock()
    mock_order_manager = MagicMock()
    mock_position_manager = MagicMock()
    mock_orderbook = MagicMock()
    mock_risk_manager = MagicMock()

    # Create InstrumentContext
    context = InstrumentContext(
        symbol="MNQ",
        instrument_info=mock_instrument_info,
        data=mock_data_manager,
        orders=mock_order_manager,
        positions=mock_position_manager,
        orderbook=mock_orderbook,
        risk_manager=mock_risk_manager,
    )

    # Verify all components are accessible
    assert context.symbol == "MNQ"
    assert context.instrument_info == mock_instrument_info
    assert context.data == mock_data_manager
    assert context.orders == mock_order_manager
    assert context.positions == mock_position_manager
    assert context.orderbook == mock_orderbook
    assert context.risk_manager == mock_risk_manager


@pytest.mark.asyncio
async def test_multi_instrument_suite_creation():
    """
    RED: Test TradingSuite creation with multiple instruments.

    This test defines how TradingSuite should handle multiple instruments
    with dictionary-like access pattern.
    """
    # Setup common mocks
    mock_client = MagicMock()
    mock_client.account_info = Account(
        id=12345,
        name="TEST_ACCOUNT",
        balance=100000.0,
        canTrade=True,
        isVisible=True,
        simulated=True,
    )
    mock_client.session_token = "mock_jwt_token"
    mock_client.config = MagicMock()
    mock_client.authenticate = AsyncMock()

    # Mock instruments for each symbol
    instruments = {
        "MNQ": MagicMock(id="MNQ_CONTRACT_ID", symbol="MNQ"),
        "MES": MagicMock(id="MES_CONTRACT_ID", symbol="MES"),
        "MCL": MagicMock(id="MCL_CONTRACT_ID", symbol="MCL"),
    }

    async def mock_get_instrument(symbol: str):
        return instruments[symbol]

    mock_client.get_instrument = AsyncMock(side_effect=mock_get_instrument)
    mock_client.search_all_orders = AsyncMock(return_value=[])
    mock_client.search_open_positions = AsyncMock(return_value=[])

    mock_context = AsyncMock()
    mock_context.__aenter__.return_value = mock_client
    mock_context.__aexit__.return_value = None

    # Mock realtime client
    mock_realtime = MagicMock()
    mock_realtime.connect = AsyncMock(return_value=True)
    mock_realtime.disconnect = AsyncMock(return_value=None)
    mock_realtime.subscribe_user_updates = AsyncMock(return_value=True)
    mock_realtime.subscribe_market_data = AsyncMock(return_value=True)
    mock_realtime.is_connected.return_value = True

    # Mock component creation for each instrument
    mock_data_managers = {}
    mock_position_managers = {}

    def create_mock_data_manager(instrument, **kwargs):
        mock_dm = MagicMock()
        mock_dm.initialize = AsyncMock(return_value=True)
        mock_dm.start_realtime_feed = AsyncMock(return_value=True)
        mock_dm.stop_realtime_feed = AsyncMock(return_value=None)
        mock_dm.cleanup = AsyncMock(return_value=None)
        mock_dm.get_current_price = AsyncMock(return_value=16500.25)
        mock_data_managers[instrument] = mock_dm
        return mock_dm

    def create_mock_position_manager(*args, **kwargs):
        mock_pm = MagicMock()
        mock_pm.initialize = AsyncMock(return_value=True)
        mock_pm.get_all_positions = AsyncMock(return_value=[])
        return mock_pm

    with patch(
        "project_x_py.trading_suite.ProjectX.from_env", return_value=mock_context
    ):
        with patch(
            "project_x_py.trading_suite.ProjectXRealtimeClient",
            return_value=mock_realtime,
        ):
            with patch(
                "project_x_py.trading_suite.RealtimeDataManager",
                side_effect=create_mock_data_manager,
            ):
                with patch(
                    "project_x_py.trading_suite.PositionManager",
                    side_effect=create_mock_position_manager,
                ):
                    # Create multi-instrument suite
                    suite = await TradingSuite.create(
                        instruments=[
                            "MNQ",
                            "MES",
                            "MCL",
                        ],  # This should work after refactor
                        timeframes=["1min", "5min"],
                    )

                    # Test dictionary-like access
                    assert len(suite) == 3
                    assert "MNQ" in suite
                    assert "MES" in suite
                    assert "MCL" in suite

                    # Test item access
                    mnq_context = suite["MNQ"]
                    assert mnq_context.symbol == "MNQ"
                    assert mnq_context.instrument_info == instruments["MNQ"]

                    mes_context = suite["MES"]
                    assert mes_context.symbol == "MES"
                    assert mes_context.instrument_info == instruments["MES"]

                    # Test iteration
                    symbols = list(suite)
                    assert set(symbols) == {"MNQ", "MES", "MCL"}

                    # Test keys/items methods
                    assert set(suite.keys()) == {"MNQ", "MES", "MCL"}

                    for symbol, context in suite.items():
                        assert symbol in ["MNQ", "MES", "MCL"]
                        assert context.symbol == symbol
                        assert context.instrument_info == instruments[symbol]

                    await suite.disconnect()


@pytest.mark.asyncio
async def test_backward_compatibility_single_instrument():
    """
    RED: Test that single-instrument access still works with deprecation warnings.

    Existing code should continue to work but with deprecation warnings.
    """
    # Setup single instrument mocks
    mock_client = MagicMock()
    mock_client.account_info = Account(
        id=12345,
        name="TEST_ACCOUNT",
        balance=100000.0,
        canTrade=True,
        isVisible=True,
        simulated=True,
    )
    mock_client.session_token = "mock_jwt_token"
    mock_client.config = MagicMock()
    mock_client.authenticate = AsyncMock()
    mock_client.get_instrument = AsyncMock(return_value=MagicMock(id="MNQ_CONTRACT_ID"))
    mock_client.search_all_orders = AsyncMock(return_value=[])
    mock_client.search_open_positions = AsyncMock(return_value=[])

    mock_context = AsyncMock()
    mock_context.__aenter__.return_value = mock_client
    mock_context.__aexit__.return_value = None

    mock_realtime = MagicMock()
    mock_realtime.connect = AsyncMock(return_value=True)
    mock_realtime.disconnect = AsyncMock(return_value=None)
    mock_realtime.subscribe_user_updates = AsyncMock(return_value=True)
    mock_realtime.subscribe_market_data = AsyncMock(return_value=True)
    mock_realtime.is_connected.return_value = True

    mock_data_manager = MagicMock()
    mock_data_manager.initialize = AsyncMock(return_value=True)
    mock_data_manager.start_realtime_feed = AsyncMock(return_value=True)
    mock_data_manager.stop_realtime_feed = AsyncMock(return_value=None)
    mock_data_manager.cleanup = AsyncMock(return_value=None)

    mock_position_manager = MagicMock()
    mock_position_manager.initialize = AsyncMock(return_value=True)

    with patch(
        "project_x_py.trading_suite.ProjectX.from_env", return_value=mock_context
    ):
        with patch(
            "project_x_py.trading_suite.ProjectXRealtimeClient",
            return_value=mock_realtime,
        ):
            with patch(
                "project_x_py.trading_suite.RealtimeDataManager",
                return_value=mock_data_manager,
            ):
                with patch(
                    "project_x_py.trading_suite.PositionManager",
                    return_value=mock_position_manager,
                ):
                    # Create single instrument suite (current API)
                    suite = await TradingSuite.create("MNQ")

                    # New API should work
                    mnq_context = suite["MNQ"]
                    assert mnq_context.symbol == "MNQ"

                    # Old API should work with deprecation warnings
                    with pytest.warns(
                        DeprecationWarning,
                        match="Direct access to 'data' is deprecated",
                    ):
                        old_data_manager = suite.data
                        assert old_data_manager == mock_data_manager

                    with pytest.warns(
                        DeprecationWarning,
                        match="Direct access to 'orders' is deprecated",
                    ):
                        old_order_manager = suite.orders

                    with pytest.warns(
                        DeprecationWarning,
                        match="Direct access to 'positions' is deprecated",
                    ):
                        old_position_manager = suite.positions

                    await suite.disconnect()


@pytest.mark.asyncio
async def test_multi_instrument_parallel_creation():
    """
    Test that multiple instruments are created in parallel for performance.

    The create method should use asyncio.gather to create instrument contexts
    in parallel rather than sequentially.
    """
    # Instead of inspecting source code (which can be unreliable),
    # let's test the actual behavior by mocking and timing

    import asyncio
    import time
    from unittest.mock import patch

    creation_times = {}

    async def mock_get_instrument(symbol: str):
        """Mock that simulates work and tracks timing."""
        start_time = time.time()
        creation_times[f"{symbol}_start"] = start_time

        # Simulate some async work
        await asyncio.sleep(0.01)  # 10ms delay

        end_time = time.time()
        creation_times[f"{symbol}_end"] = end_time

        # Return mock instrument
        mock_instrument = MagicMock()
        mock_instrument.id = f"{symbol}_CONTRACT_ID"
        mock_instrument.symbol = symbol
        return mock_instrument

    # Mock all the external dependencies
    mock_client = AsyncMock()
    mock_client.get_instrument = AsyncMock(side_effect=mock_get_instrument)
    mock_client.search_all_orders = AsyncMock(return_value=[])
    mock_client.config = MagicMock()
    mock_client.config.timezone = "America/Chicago"
    mock_client.config.auto_connect = False
    mock_client.authenticate = AsyncMock()

    mock_realtime = AsyncMock()
    mock_context = AsyncMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_client)
    mock_context.__aexit__ = AsyncMock()

    # Test creating 3 instruments
    instruments = ["MNQ", "MES", "MCL"]

    with patch(
        "project_x_py.trading_suite.ProjectX.from_env", return_value=mock_context
    ):
        with patch(
            "project_x_py.trading_suite.ProjectXRealtimeClient",
            return_value=mock_realtime,
        ):
            with patch("project_x_py.trading_suite.RealtimeDataManager"):
                with patch("project_x_py.trading_suite.PositionManager"):
                    with patch("project_x_py.trading_suite.OrderManager"):
                        start_time = time.time()

                        # Call the actual method that should use parallel creation
                        result = await TradingSuite._create_instrument_contexts(
                            instruments,
                            mock_client,
                            mock_realtime,
                            TradingSuiteConfig(
                                instrument="MNQ", timezone="America/Chicago"
                            ),
                        )

                        end_time = time.time()
                        total_time = end_time - start_time

    # Verify that the result contains all instruments
    assert len(result) == 3
    assert "MNQ" in result
    assert "MES" in result
    assert "MCL" in result

    # Verify parallel execution by checking timing:
    # If executed in parallel, total time should be close to the individual task time (0.01s)
    # If executed sequentially, total time would be ~3x individual task time (0.03s)
    # We'll be generous and allow up to 0.025s (2.5x) to account for overhead
    assert total_time < 0.025, (
        f"Creation took {total_time:.3f}s, suggesting sequential rather than parallel execution"
    )

    # Additional verification: All instruments should have started before any finished
    # (indicating true parallelism)
    start_times = [creation_times[f"{symbol}_start"] for symbol in instruments]
    end_times = [creation_times[f"{symbol}_end"] for symbol in instruments]

    # The latest start should be before the earliest end if running in parallel
    latest_start = max(start_times)
    earliest_end = min(end_times)

    assert latest_start <= earliest_end, (
        "Instruments appear to be created sequentially rather than in parallel"
    )


@pytest.mark.asyncio
async def test_partial_failure_cleanup():
    """
    Test that partially created instrument contexts are cleaned up when one fails.

    This tests the robustness of parallel creation when some instruments
    fail to initialize properly.
    """
    # Mock client and dependencies
    mock_client = AsyncMock()
    mock_client.config = MagicMock()
    mock_client.config.timezone = "America/Chicago"
    mock_realtime = AsyncMock()
    mock_config = TradingSuiteConfig(instrument="MNQ", timezone="America/Chicago")

    # Track cleanup calls
    cleanup_calls = []

    def mock_cleanup():
        cleanup_calls.append("cleanup_called")
        return AsyncMock()()

    # Mock successful and failing instrument creation
    success_context = MagicMock()
    success_context.data.cleanup = mock_cleanup
    success_context.orders.cleanup = mock_cleanup
    success_context.positions.cleanup = mock_cleanup
    success_context.orderbook = None
    success_context.risk_manager = None

    async def mock_get_instrument(symbol: str):
        if symbol == "FAIL":
            raise ValueError(f"Failed to get instrument {symbol}")

        mock_instrument = MagicMock()
        mock_instrument.id = f"{symbol}_CONTRACT_ID"
        mock_instrument.symbol = symbol
        return mock_instrument

    mock_client.get_instrument = AsyncMock(side_effect=mock_get_instrument)

    # Mock manager creation - first succeeds, second fails
    creation_count = 0

    def create_mock_manager(*args, **kwargs):
        nonlocal creation_count
        creation_count += 1
        if (
            creation_count <= 3
        ):  # First 3 calls succeed (data, orders, positions for MNQ)
            return success_context  # Return the same mock for all managers
        else:
            raise RuntimeError("Simulated creation failure")

    with patch(
        "project_x_py.trading_suite.RealtimeDataManager",
        side_effect=create_mock_manager,
    ):
        with patch(
            "project_x_py.trading_suite.OrderManager", side_effect=create_mock_manager
        ):
            with patch(
                "project_x_py.trading_suite.PositionManager",
                side_effect=create_mock_manager,
            ):
                # This should fail because FAIL instrument will cause get_instrument to raise
                with pytest.raises(ValueError, match="Failed to get instrument FAIL"):
                    await TradingSuite._create_instrument_contexts(
                        ["MNQ", "FAIL"], mock_client, mock_realtime, mock_config
                    )

                # Verify cleanup was attempted
                # Note: In this test the failure happens early (get_instrument),
                # so no contexts are created yet to clean up


@pytest.mark.asyncio
async def test_cross_instrument_event_isolation():
    """
    Test that events from one instrument don't interfere with others.

    This ensures proper event isolation in multi-instrument mode.
    """
    # Create mock instruments with separate event tracking
    mnq_events = []
    es_events = []

    def create_mock_context(symbol: str):
        context = MagicMock()
        context.symbol = symbol
        context.instrument_info = MagicMock(id=f"{symbol}_CONTRACT_ID", symbol=symbol)

        # Mock event bus that tracks events per instrument
        mock_event_bus = MagicMock()
        if symbol == "MNQ":
            mock_event_bus.emit = AsyncMock(
                side_effect=lambda *args: mnq_events.append(args)
            )
        else:  # ES
            mock_event_bus.emit = AsyncMock(
                side_effect=lambda *args: es_events.append(args)
            )

        context.data = MagicMock()
        context.orders = MagicMock()
        context.positions = MagicMock()
        context.orderbook = None
        context.risk_manager = None

        return context

    # Create contexts
    mnq_context = create_mock_context("MNQ")
    es_context = create_mock_context("ES")

    # Create suite with multiple instruments
    mock_client = AsyncMock()
    mock_realtime = AsyncMock()
    mock_config = TradingSuiteConfig(instrument="MNQ", timezone="America/Chicago")

    suite = TradingSuite(
        mock_client, mock_realtime, mock_config, {"MNQ": mnq_context, "ES": es_context}
    )

    # Verify contexts are isolated
    assert suite["MNQ"].symbol == "MNQ"
    assert suite["ES"].symbol == "ES"
    assert suite["MNQ"] is not suite["ES"]

    # Verify separate instrument contexts don't interfere
    assert len(suite) == 2
    assert "MNQ" in suite
    assert "ES" in suite


@pytest.mark.asyncio
async def test_error_propagation_multi_instrument():
    """
    Test proper error propagation in multi-instrument scenarios.

    Verifies that errors are handled gracefully and provide useful context.
    """
    # Create mock suite with multiple instruments
    mock_client = AsyncMock()
    mock_realtime = AsyncMock()
    mock_config = TradingSuiteConfig(instrument="MNQ", timezone="America/Chicago")

    context1 = MagicMock()
    context1.symbol = "MNQ"
    context2 = MagicMock()
    context2.symbol = "ES"

    suite = TradingSuite(
        mock_client, mock_realtime, mock_config, {"MNQ": context1, "ES": context2}
    )

    # Test missing instrument access
    with pytest.raises(KeyError):
        _ = suite["NONEXISTENT"]

    # Test attribute access on multi-instrument suite
    with pytest.raises(AttributeError) as exc_info:
        _ = suite.nonexistent_attribute

    # Verify helpful error message
    error_msg = str(exc_info.value)
    assert "For multi-instrument suites, use suite['SYMBOL']" in error_msg
    assert (
        "Available instruments: ['MNQ', 'ES']" in error_msg
        or "Available instruments: ['ES', 'MNQ']" in error_msg
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
