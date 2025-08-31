"""
Tests for the unified EventBus system.

This module tests the EventBus functionality and verifies that events
are properly emitted from all components through the unified system.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from project_x_py.event_bus import Event, EventBus, EventType


@pytest.mark.asyncio
class TestEventBus:
    """Test the EventBus functionality."""

    async def test_event_bus_creation(self):
        """Test EventBus can be created and initialized."""
        bus = EventBus()
        assert bus is not None
        assert bus.get_handler_count() == 0

    async def test_event_registration(self):
        """Test registering event handlers."""
        bus = EventBus()

        # Create a mock handler
        handler = AsyncMock()

        # Register handler
        await bus.on(EventType.NEW_BAR, handler)

        # Check handler count
        assert bus.get_handler_count(EventType.NEW_BAR) == 1

        # Emit event
        await bus.emit(EventType.NEW_BAR, {"test": "data"})

        # Wait a bit for async execution
        await asyncio.sleep(0.1)

        # Verify handler was called
        handler.assert_called_once()
        event = handler.call_args[0][0]
        assert isinstance(event, Event)
        assert event.type == EventType.NEW_BAR
        assert event.data == {"test": "data"}

    async def test_once_handler(self):
        """Test one-time event handlers."""
        bus = EventBus()

        handler = AsyncMock()
        await bus.once(EventType.ORDER_FILLED, handler)

        # Emit twice
        await bus.emit(EventType.ORDER_FILLED, {"order_id": 1})
        await bus.emit(EventType.ORDER_FILLED, {"order_id": 2})

        await asyncio.sleep(0.1)

        # Handler should only be called once
        assert handler.call_count == 1

    async def test_wildcard_handler(self):
        """Test wildcard event handlers."""
        bus = EventBus()

        handler = AsyncMock()
        await bus.on_any(handler)

        # Emit different events
        await bus.emit(EventType.NEW_BAR, {"bar": 1})
        await bus.emit(EventType.ORDER_PLACED, {"order": 1})

        await asyncio.sleep(0.1)

        # Handler should be called for both
        assert handler.call_count == 2

    async def test_wait_for_event(self):
        """Test waiting for specific events."""
        bus = EventBus()

        # Schedule event emission
        async def emit_later():
            await asyncio.sleep(0.5)
            await bus.emit(EventType.POSITION_OPENED, {"position": "test"})

        asyncio.create_task(emit_later())

        # Wait for event
        event = await bus.wait_for(EventType.POSITION_OPENED, timeout=2.0)
        assert event.data == {"position": "test"}

    async def test_wait_for_timeout(self):
        """Test timeout when waiting for events."""
        bus = EventBus()

        with pytest.raises(TimeoutError):
            await bus.wait_for(EventType.POSITION_CLOSED, timeout=0.5)

    async def test_event_history(self):
        """Test event history functionality."""
        bus = EventBus()
        bus.enable_history(max_size=10)

        # Emit some events
        for i in range(5):
            await bus.emit(EventType.QUOTE_UPDATE, {"quote": i})

        # Check history
        history = bus.get_history()
        assert len(history) == 5
        assert all(isinstance(e, Event) for e in history)
        assert history[-1].data == {"quote": 4}

        # Clear history
        bus.clear_history()
        assert len(bus.get_history()) == 0

    async def test_handler_removal(self):
        """Test removing event handlers."""
        bus = EventBus()

        handler1 = AsyncMock()
        handler2 = AsyncMock()

        await bus.on(EventType.NEW_BAR, handler1)
        await bus.on(EventType.NEW_BAR, handler2)

        assert bus.get_handler_count(EventType.NEW_BAR) == 2

        # Remove specific handler
        await bus.off(EventType.NEW_BAR, handler1)
        assert bus.get_handler_count(EventType.NEW_BAR) == 1

        # Emit event
        await bus.emit(EventType.NEW_BAR, {"test": 1})
        await asyncio.sleep(0.1)

        # Only handler2 should be called
        handler1.assert_not_called()
        handler2.assert_called_once()

        # Remove all handlers for event
        await bus.off(EventType.NEW_BAR)
        assert bus.get_handler_count(EventType.NEW_BAR) == 0


@pytest.mark.asyncio
class TestTradingSuiteIntegration:
    """Test EventBus integration with TradingSuite."""

    @pytest.fixture
    async def mock_suite(self):
        """Create a mock TradingSuite with EventBus."""
        # Mock the ProjectX client
        mock_client = MagicMock()
        mock_client.authenticate = AsyncMock()
        mock_client.account_info = MagicMock(id=12345)
        mock_client.get_instrument = AsyncMock(return_value=MagicMock(id="MNQ"))

        # Mock realtime client
        mock_realtime = MagicMock()
        mock_realtime.connect = AsyncMock(return_value=True)
        mock_realtime.subscribe_market_data = AsyncMock()
        mock_realtime.is_connected = MagicMock(return_value=True)
        mock_realtime.disconnect = AsyncMock()

        # Create suite with mocks
        from project_x_py.trading_suite import TradingSuite, TradingSuiteConfig

        config = TradingSuiteConfig("MNQ")
        suite = TradingSuite(mock_client, mock_realtime, config)

        yield suite

        # Cleanup
        await suite.disconnect()

    async def test_suite_event_registration(self, mock_suite):
        """Test registering events through TradingSuite."""
        handler = AsyncMock()

        # Register through suite
        await mock_suite.on(EventType.NEW_BAR, handler)

        # Verify it's registered in the EventBus
        assert mock_suite.events.get_handler_count(EventType.NEW_BAR) == 1

        # Emit through suite's EventBus
        await mock_suite.events.emit(EventType.NEW_BAR, {"bar": "test"})
        await asyncio.sleep(0.1)

        handler.assert_called_once()

    async def test_component_event_emission(self, mock_suite):
        """Test that components emit events through EventBus."""
        # Register handler
        handler = AsyncMock()
        await mock_suite.on(EventType.NEW_BAR, handler)

        # Simulate data manager emitting event
        await mock_suite.data._trigger_callbacks(
            "new_bar", {"timeframe": "5min", "data": {"close": 100}}
        )

        await asyncio.sleep(0.1)

        # Verify handler was called
        handler.assert_called_once()
        event = handler.call_args[0][0]
        assert event.source == "RealtimeDataManager"
        assert event.data["timeframe"] == "5min"

    async def test_order_event_flow(self, mock_suite):
        """Test order events flow through EventBus."""
        handler = AsyncMock()
        await mock_suite.on(EventType.ORDER_PLACED, handler)

        # Simulate order placed
        await mock_suite.orders._trigger_callbacks(
            "order_placed", {"order_id": 12345, "side": 0, "size": 1}
        )

        await asyncio.sleep(0.1)

        handler.assert_called_once()
        event = handler.call_args[0][0]
        assert event.source == "OrderManager"
        assert event.data["order_id"] == 12345

    async def test_position_event_flow(self, mock_suite):
        """Test position events flow through EventBus."""
        opened_handler = AsyncMock()
        closed_handler = AsyncMock()

        await mock_suite.on(EventType.POSITION_OPENED, opened_handler)
        await mock_suite.on(EventType.POSITION_CLOSED, closed_handler)

        # Simulate position opened
        await mock_suite.positions._trigger_callbacks(
            "position_opened", {"contractId": "MNQ", "size": 2}
        )

        # Simulate position closed
        await mock_suite.positions._trigger_callbacks(
            "position_closed", {"contractId": "MNQ", "realizedPnl": 150.0}
        )

        await asyncio.sleep(0.1)

        opened_handler.assert_called_once()
        closed_handler.assert_called_once()

        assert opened_handler.call_args[0][0].source == "PositionManager"
        assert closed_handler.call_args[0][0].source == "PositionManager"

    async def test_orderbook_event_flow(self, mock_suite):
        """Test orderbook events flow through EventBus."""
        # Enable orderbook
        from project_x_py.orderbook import OrderBook

        mock_suite._orderbook = OrderBook("MNQ", event_bus=mock_suite.events)

        handler = AsyncMock()
        await mock_suite.on(EventType.MARKET_DEPTH_UPDATE, handler)

        # Simulate depth update
        await mock_suite._orderbook._trigger_callbacks(
            "market_depth", {"bids": [], "asks": []}
        )

        await asyncio.sleep(0.1)

        handler.assert_called_once()
        assert handler.call_args[0][0].source == "OrderBook"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
