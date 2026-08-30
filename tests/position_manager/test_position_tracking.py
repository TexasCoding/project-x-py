from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_validate_position_payload_valid_invalid(
    position_manager, mock_positions_data
):
    pm = position_manager
    valid = pm._validate_position_payload(mock_positions_data[0])
    assert valid is True

    # Missing required field
    invalid = dict(mock_positions_data[0])
    invalid.pop("contractId")
    assert pm._validate_position_payload(invalid) is False

    # Invalid type
    invalid2 = dict(mock_positions_data[0])
    invalid2["size"] = "not_a_number"
    assert pm._validate_position_payload(invalid2) is False


@pytest.mark.asyncio
async def test_process_position_data_open_and_close(
    position_manager, mock_positions_data
):
    pm = position_manager
    # Patch callback
    pm._trigger_callbacks = AsyncMock()
    position_data = dict(mock_positions_data[0])

    # Open/update
    await pm._process_position_data(position_data)
    key = position_data["contractId"]
    assert key in pm.tracked_positions

    # Close
    closure_data = dict(position_data)
    closure_data["size"] = 0
    await pm._process_position_data(closure_data)
    assert key not in pm.tracked_positions
    assert pm.stats["closed_positions"] == 1
    closed = [
        call.args[1]
        for call in pm._trigger_callbacks.await_args_list
        if call.args and call.args[0] == "position_closed"
    ]
    assert closed
    assert closed[0]["contractId"] == key
    assert "pnl" in closed[0]
