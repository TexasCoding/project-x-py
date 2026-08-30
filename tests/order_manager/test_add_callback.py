"""C1: OrderManager.add_callback must forward to EventBus."""

import warnings

import pytest

from project_x_py.event_bus import EventType


@pytest.mark.asyncio
async def test_add_callback_invokes_on_mapped_event(order_manager):
    """Calling add_callback then emitting the mapped event invokes the callback."""
    called: list[object] = []

    async def on_fill(event):
        called.append(event)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        await order_manager.add_callback("order_filled", on_fill)

    await order_manager.event_bus.emit(EventType.ORDER_FILLED, {"order_id": 42})

    assert len(called) == 1
    assert called[0].data["order_id"] == 42


@pytest.mark.asyncio
async def test_add_callback_unknown_event_raises(order_manager):
    async def on_event(event):
        pass

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        with pytest.raises(ValueError, match="Unknown event type"):
            await order_manager.add_callback("not_a_real_event", on_event)
