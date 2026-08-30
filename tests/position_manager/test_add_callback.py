"""C1: PositionManager.add_callback must forward to EventBus."""

import warnings

import pytest

from project_x_py.event_bus import EventType


@pytest.mark.asyncio
async def test_add_callback_invokes_on_mapped_event(position_manager):
    called: list[object] = []

    async def on_update(event):
        called.append(event)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        await position_manager.add_callback("position_update", on_update)

    await position_manager.event_bus.emit(
        EventType.POSITION_UPDATED, {"contractId": "MNQ", "size": 2}
    )

    assert len(called) == 1
    assert called[0].data["size"] == 2


@pytest.mark.asyncio
async def test_add_callback_unknown_event_raises(position_manager):
    async def on_event(event):
        pass

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        with pytest.raises(ValueError, match="Unknown event type"):
            await position_manager.add_callback("not_a_real_event", on_event)
