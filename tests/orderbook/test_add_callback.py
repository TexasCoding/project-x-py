"""C1: OrderBook.add_callback must register, not just log."""

import warnings

import pytest

from project_x_py.event_bus import EventBus, EventType
from project_x_py.orderbook.base import OrderBookBase


@pytest.fixture
def orderbook_with_bus():
    bus = EventBus()
    return OrderBookBase(instrument="MNQ", event_bus=bus), bus


@pytest.mark.asyncio
async def test_add_callback_invokes_on_mapped_event(orderbook_with_bus):
    ob, bus = orderbook_with_bus
    called: list[object] = []

    async def on_trade(event):
        called.append(event)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        await ob.add_callback("trade", on_trade)

    await bus.emit(EventType.TRADE_TICK, {"price": 19000.0, "size": 1})

    assert len(called) == 1
    assert called[0].data["price"] == 19000.0


@pytest.mark.asyncio
async def test_unknown_event_raises_and_does_not_log_registered(
    orderbook_with_bus, caplog
):
    ob, _bus = orderbook_with_bus

    async def on_event(event):
        pass

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        with pytest.raises(ValueError, match="Unknown event type"):
            await ob.add_callback("not_a_real_event", on_event)

    assert "Callback registered" not in caplog.text
