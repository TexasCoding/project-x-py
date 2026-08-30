"""
Tests for multi-instrument event system functionality.

These tests define the expected behavior of the event system when using
multiple instruments with TradingSuite. Following TDD principles, these
tests are written to specify how the system SHOULD work.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from project_x_py import TradingSuite
from project_x_py.event_bus import EventType


@pytest.mark.asyncio
async def test_suite_receives_events_from_all_instruments():
    """Test that suite-level event handlers receive events from all instruments."""
    with patch("project_x_py.trading_suite.ProjectX") as mock_client_class, \
         patch("project_x_py.trading_suite.ProjectXRealtimeClient") as mock_realtime_class:

        # Mock main client
        mock_client = AsyncMock()
        mock_client_class.from_env.return_value.__aenter__.return_value = mock_client

        # Mock realtime client
        mock_realtime = AsyncMock()
        mock_realtime_class.return_value = mock_realtime

        # Setup mock responses
        mock_client.authenticate.return_value = None
        # Create enough mock instruments for multiple calls
        def mock_get_instrument(symbol):
            return MagicMock(symbol=symbol, name=symbol, exchange="CME", min_tick=0.25, id=f"id_{symbol}")
        mock_client.get_instrument.side_effect = mock_get_instrument
        mock_client.get_bars.return_value = MagicMock(is_empty=lambda: True)

        # Mock realtime client connection
        mock_realtime.connect.return_value = True
        mock_realtime.is_connected.return_value = True

        suite = await TradingSuite.create(["MNQ", "NQ"], timeframes=["1min"])

        # Track events received at suite level
        events_received = []

        async def on_new_bar(event):
            events_received.append(event)

        # Register handler at suite level
        await suite.on(EventType.NEW_BAR, on_new_bar)

        # Emit events from instrument-specific event buses
        await suite["MNQ"].event_bus.emit(
            EventType.NEW_BAR, {"instrument": "MNQ", "timeframe": "1min", "close": 100.0}
        )
        await suite["NQ"].event_bus.emit(
            EventType.NEW_BAR, {"instrument": "NQ", "timeframe": "1min", "close": 200.0}
        )

        # Allow event propagation
        await asyncio.sleep(0.1)

        # Suite should receive events from both instruments
        assert len(events_received) == 2
        assert any(e.data["instrument"] == "MNQ" for e in events_received)
        assert any(e.data["instrument"] == "NQ" for e in events_received)


@pytest.mark.asyncio
async def test_instrument_context_has_event_methods():
    """Test that InstrumentContext provides wait_for and on methods."""
    with patch("project_x_py.trading_suite.ProjectX") as mock_client_class, \
         patch("project_x_py.trading_suite.ProjectXRealtimeClient") as mock_realtime_class:

        # Mock main client
        mock_client = AsyncMock()
        mock_client_class.from_env.return_value.__aenter__.return_value = mock_client

        # Mock realtime client
        mock_realtime = AsyncMock()
        mock_realtime_class.return_value = mock_realtime

        # Setup mock responses
        mock_client.authenticate.return_value = None
        mock_client.get_instrument.return_value = MagicMock(
            symbol="MNQ", name="MNQ", exchange="CME", min_tick=0.25
        )
        mock_client.get_bars.return_value = MagicMock(is_empty=lambda: True)

        # Mock realtime client connection
        mock_realtime.connect.return_value = True
        mock_realtime.is_connected.return_value = True

        suite = await TradingSuite.create("MNQ", timeframes=["1min"])
        mnq_context = suite["MNQ"]

        # InstrumentContext should have event methods
        assert hasattr(mnq_context, "wait_for")
        assert hasattr(mnq_context, "on")
        assert hasattr(mnq_context, "off")

        # Test that methods are callable
        events_received = []

        async def handler(event):
            events_received.append(event)

        # Should be able to register handler on instrument context
        await mnq_context.on(EventType.NEW_BAR, handler)

        # Emit event to instrument's event bus
        await mnq_context.event_bus.emit(
            EventType.NEW_BAR, {"instrument": "MNQ", "timeframe": "1min", "close": 100.0}
        )

        # Allow event propagation
        await asyncio.sleep(0.1)

        # Handler should have received the event
        assert len(events_received) == 1
        assert events_received[0].data["instrument"] == "MNQ"


@pytest.mark.asyncio
async def test_wait_for_works_at_suite_level():
    """Test that suite.wait_for() receives events from any instrument."""
    with patch("project_x_py.trading_suite.ProjectX") as mock_client_class, \
         patch("project_x_py.trading_suite.ProjectXRealtimeClient") as mock_realtime_class:

        # Mock main client
        mock_client = AsyncMock()
        mock_client_class.from_env.return_value.__aenter__.return_value = mock_client

        # Mock realtime client
        mock_realtime = AsyncMock()
        mock_realtime_class.return_value = mock_realtime

        # Setup mock responses
        mock_client.authenticate.return_value = None
        # Create enough mock instruments for multiple calls
        def mock_get_instrument(symbol):
            return MagicMock(symbol=symbol, name=symbol, exchange="CME", min_tick=0.25, id=f"id_{symbol}")
        mock_client.get_instrument.side_effect = mock_get_instrument
        mock_client.get_bars.return_value = MagicMock(is_empty=lambda: True)

        # Mock realtime client connection
        mock_realtime.connect.return_value = True
        mock_realtime.is_connected.return_value = True

        suite = await TradingSuite.create(["MNQ", "NQ"], timeframes=["1min"])

        # Create a task that waits for an event
        async def wait_for_event():
            event = await suite.wait_for(EventType.NEW_BAR)
            return event

        wait_task = asyncio.create_task(wait_for_event())

        # Give the task time to start waiting
        await asyncio.sleep(0.1)

        # Emit event from one of the instruments
        await suite["NQ"].event_bus.emit(
            EventType.NEW_BAR, {"instrument": "NQ", "timeframe": "1min", "close": 200.0}
        )

        # wait_for should receive the event
        try:
            event = await asyncio.wait_for(wait_task, timeout=1.0)
            assert event.data["instrument"] == "NQ"
            assert event.data["close"] == 200.0
        except asyncio.TimeoutError:
            pytest.fail("suite.wait_for() did not receive event from instrument")


@pytest.mark.asyncio
async def test_wait_for_works_at_instrument_level():
    """Test that instrument_context.wait_for() receives events for that instrument."""
    with patch("project_x_py.trading_suite.ProjectX") as mock_client_class, \
         patch("project_x_py.trading_suite.ProjectXRealtimeClient") as mock_realtime_class:

        # Mock main client
        mock_client = AsyncMock()
        mock_client_class.from_env.return_value.__aenter__.return_value = mock_client

        # Mock realtime client
        mock_realtime = AsyncMock()
        mock_realtime_class.return_value = mock_realtime

        # Setup mock responses
        mock_client.authenticate.return_value = None
        mock_client.get_instrument.return_value = MagicMock(
            symbol="MNQ", name="MNQ", exchange="CME", min_tick=0.25
        )
        mock_client.get_bars.return_value = MagicMock(is_empty=lambda: True)

        # Mock realtime client connection
        mock_realtime.connect.return_value = True
        mock_realtime.is_connected.return_value = True

        suite = await TradingSuite.create("MNQ", timeframes=["1min"])
        mnq_context = suite["MNQ"]

        # Create a task that waits for an event
        async def wait_for_event():
            event = await mnq_context.wait_for(EventType.NEW_BAR)
            return event

        wait_task = asyncio.create_task(wait_for_event())

        # Give the task time to start waiting
        await asyncio.sleep(0.1)

        # Emit event to instrument's event bus
        await mnq_context.event_bus.emit(
            EventType.NEW_BAR, {"instrument": "MNQ", "timeframe": "1min", "close": 100.0}
        )

        # wait_for should receive the event
        try:
            event = await asyncio.wait_for(wait_task, timeout=1.0)
            assert event.data["instrument"] == "MNQ"
            assert event.data["close"] == 100.0
        except asyncio.TimeoutError:
            pytest.fail("instrument_context.wait_for() did not receive event")


@pytest.mark.asyncio
async def test_event_filtering_by_instrument():
    """Test that instrument contexts can filter events by instrument."""
    with patch("project_x_py.trading_suite.ProjectX") as mock_client_class, \
         patch("project_x_py.trading_suite.ProjectXRealtimeClient") as mock_realtime_class:

        # Mock main client
        mock_client = AsyncMock()
        mock_client_class.from_env.return_value.__aenter__.return_value = mock_client

        # Mock realtime client
        mock_realtime = AsyncMock()
        mock_realtime_class.return_value = mock_realtime

        # Setup mock responses
        mock_client.authenticate.return_value = None
        # Create enough mock instruments for multiple calls
        def mock_get_instrument(symbol):
            return MagicMock(symbol=symbol, name=symbol, exchange="CME", min_tick=0.25, id=f"id_{symbol}")
        mock_client.get_instrument.side_effect = mock_get_instrument
        mock_client.get_bars.return_value = MagicMock(is_empty=lambda: True)

        # Mock realtime client connection
        mock_realtime.connect.return_value = True
        mock_realtime.is_connected.return_value = True

        suite = await TradingSuite.create(["MNQ", "NQ"], timeframes=["1min"])

        mnq_events = []
        nq_events = []

        async def mnq_handler(event):
            mnq_events.append(event)

        async def nq_handler(event):
            nq_events.append(event)

        # Register handlers on specific instrument contexts
        await suite["MNQ"].on(EventType.NEW_BAR, mnq_handler)
        await suite["NQ"].on(EventType.NEW_BAR, nq_handler)

        # Emit events from both instruments
        await suite["MNQ"].event_bus.emit(
            EventType.NEW_BAR, {"instrument": "MNQ", "timeframe": "1min", "close": 100.0}
        )
        await suite["NQ"].event_bus.emit(
            EventType.NEW_BAR, {"instrument": "NQ", "timeframe": "1min", "close": 200.0}
        )

        # Allow event propagation
        await asyncio.sleep(0.1)

        # Each handler should only receive events from its instrument
        assert len(mnq_events) == 1
        assert mnq_events[0].data["instrument"] == "MNQ"

        assert len(nq_events) == 1
        assert nq_events[0].data["instrument"] == "NQ"


@pytest.mark.asyncio
async def test_suite_level_handler_receives_all_instruments():
    """Test that a single suite-level handler receives events from all instruments."""
    with patch("project_x_py.trading_suite.ProjectX") as mock_client_class, \
         patch("project_x_py.trading_suite.ProjectXRealtimeClient") as mock_realtime_class:

        # Mock main client
        mock_client = AsyncMock()
        mock_client_class.from_env.return_value.__aenter__.return_value = mock_client

        # Mock realtime client
        mock_realtime = AsyncMock()
        mock_realtime_class.return_value = mock_realtime

        # Setup mock responses
        mock_client.authenticate.return_value = None
        # Create enough mock instruments for multiple calls
        def mock_get_instrument(symbol):
            return MagicMock(symbol=symbol, name=symbol, exchange="CME", min_tick=0.25, id=f"id_{symbol}")
        mock_client.get_instrument.side_effect = mock_get_instrument
        mock_client.get_bars.return_value = MagicMock(is_empty=lambda: True)

        # Mock realtime client connection
        mock_realtime.connect.return_value = True
        mock_realtime.is_connected.return_value = True

        suite = await TradingSuite.create(["MNQ", "NQ", "ES"], timeframes=["1min"])

        all_events = []

        async def universal_handler(event):
            all_events.append(event)

        # Register a single handler at suite level
        await suite.on(EventType.NEW_BAR, universal_handler)

        # Emit events from all instruments
        for symbol in ["MNQ", "NQ", "ES"]:
            await suite[symbol].event_bus.emit(
                EventType.NEW_BAR,
                {
                    "instrument": symbol,
                    "timeframe": "1min",
                    "close": 100.0 * (ord(symbol[0]) - 64),
                },
            )

        # Allow event propagation
        await asyncio.sleep(0.1)

        # Handler should receive events from all instruments
        assert len(all_events) == 3
        instruments = {e.data["instrument"] for e in all_events}
        assert instruments == {"MNQ", "NQ", "ES"}
