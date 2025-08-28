"""Mock-based fixtures for OrderManager testing that don't require authentication."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from project_x_py.event_bus import EventBus
from project_x_py.models import Account
from project_x_py.order_manager.core import OrderManager


@pytest.fixture
def mock_order_manager():
    """Create a fully mocked OrderManager that doesn't require authentication."""

    # Create mock client
    mock_client = MagicMock()
    mock_client.account_info = Account(
        id=12345,
        name="Test Account",
        balance=100000.0,
        canTrade=True,
        isVisible=True,
        simulated=True,
    )

    # Mock all async methods on the client
    mock_client.authenticate = AsyncMock(return_value=True)
    mock_client.get_position = AsyncMock(return_value=None)
    mock_client.get_instrument = AsyncMock(return_value=None)
    mock_client.get_order_by_id = AsyncMock(return_value=None)
    mock_client.search_orders = AsyncMock(return_value=[])
    mock_client.search_open_positions = AsyncMock(return_value=[])
    mock_client._make_request = AsyncMock(return_value={"success": True})

    # Create EventBus
    event_bus = EventBus()

    # Create patches for price alignment functions
    patch1 = patch('project_x_py.order_manager.utils.align_price_to_tick_size',
                   new=AsyncMock(side_effect=lambda price, *args, **kwargs: price))
    patch2 = patch('project_x_py.order_manager.core.align_price_to_tick_size',
                   new=AsyncMock(side_effect=lambda price, *args, **kwargs: price))

    # Start patches
    patch1.start()
    patch2.start()

    # Create OrderManager with mocked client
    om = OrderManager(mock_client, event_bus)

    # Set the project_x client attribute
    om.project_x = mock_client

    # Override only the core API methods that would call the actual API
    # But preserve mixin methods like close_position
    om.place_market_order = AsyncMock()
    om.place_limit_order = AsyncMock()
    om.place_stop_order = AsyncMock()
    om.cancel_order = AsyncMock()
    om.modify_order = AsyncMock()

    # Return the mocked order manager and stop patches on teardown
    try:
        yield om
    finally:
        patch1.stop()
        patch2.stop()
