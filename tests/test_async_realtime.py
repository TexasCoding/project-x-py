"""Tests for AsyncProjectXRealtimeClient."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from project_x_py.models import Account, ProjectXConfig
from project_x_py.realtime import ProjectXRealtimeClient


@pytest.fixture
def mock_config():
    """Create a mock ProjectXConfig."""
    config = MagicMock(spec=ProjectXConfig)
    config.user_hub_url = "https://test.com/hubs/user"
    config.market_hub_url = "https://test.com/hubs/market"
    return config


@pytest.fixture
def realtime_client(mock_config):
    """Create a ProjectXRealtimeClient instance."""
    return ProjectXRealtimeClient(
        jwt_token="test_token",
        account_id="test_account",
        config=mock_config,
    )


@pytest.mark.asyncio
async def test_initialization(mock_config):
    """Test ProjectXRealtimeClient initialization."""
    client = ProjectXRealtimeClient(
        jwt_token="test_token",
        account_id="test_account",
        config=mock_config,
    )

    assert client.jwt_token == "test_token"
    assert client.account_id == "test_account"
    assert client.base_user_url == "https://test.com/hubs/user"
    assert client.base_market_url == "https://test.com/hubs/market"
    assert client.user_hub_url == "https://test.com/hubs/user?access_token=test_token"
    assert (
        client.market_hub_url == "https://test.com/hubs/market?access_token=test_token"
    )
    assert isinstance(client._callback_lock, asyncio.Lock)
    assert isinstance(client._connection_lock, asyncio.Lock)


@pytest.mark.asyncio
async def test_initialization_without_config():
    """Test initialization with default URLs."""
    client = ProjectXRealtimeClient(
        jwt_token="test_token",
        account_id="test_account",
    )

    assert client.base_user_url == "https://rtc.topstepx.com/hubs/user"
    assert client.base_market_url == "https://rtc.topstepx.com/hubs/market"


@pytest.mark.asyncio
async def test_setup_connections_no_signalr():
    """Test setup connections when signalrcore is not available."""
    with patch("project_x_py.realtime.HubConnectionBuilder", None):
        client = ProjectXRealtimeClient(
            jwt_token="test_token", account_id="test_account"
        )

        with pytest.raises(ImportError, match="signalrcore is required"):
            await client.setup_connections()


@pytest.mark.asyncio
async def test_setup_connections_success():
    """Test successful connection setup."""
    mock_builder = MagicMock()
    mock_connection = MagicMock()
    mock_builder.return_value.with_url.return_value = mock_builder
    mock_builder.configure_logging.return_value = mock_builder
    mock_builder.with_automatic_reconnect.return_value = mock_builder
    mock_builder.build.return_value = mock_connection

    with patch("project_x_py.realtime.HubConnectionBuilder", mock_builder):
        client = ProjectXRealtimeClient("test_token", "test_account")
        await client.setup_connections()

        assert client.setup_complete is True
        assert client.user_connection is not None
        assert client.market_connection is not None
        # Check event handlers were registered
        assert mock_connection.on.call_count > 0


@pytest.mark.asyncio
async def test_connect_success():
    """Test successful connection."""
    client = ProjectXRealtimeClient("test_token", "test_account")

    # Mock connections
    mock_user_conn = MagicMock()
    mock_market_conn = MagicMock()
    client.user_connection = mock_user_conn
    client.market_connection = mock_market_conn
    client.setup_complete = True

    # Simulate successful connection
    client.user_connected = True
    client.market_connected = True

    with patch.object(client, "_start_connection_async", AsyncMock()):
        result = await client.connect()

    assert result is True
    assert client.stats["connected_time"] is not None


@pytest.mark.asyncio
async def test_connect_failure():
    """Test connection failure."""
    client = ProjectXRealtimeClient("test_token", "test_account")
    client.setup_complete = True

    # No connections available
    result = await client.connect()

    assert result is False
    assert client.stats["connection_errors"] == 0  # No exception raised


@pytest.mark.asyncio
async def test_disconnect():
    """Test disconnection."""
    client = ProjectXRealtimeClient("test_token", "test_account")

    # Mock connections
    mock_user_conn = MagicMock()
    mock_market_conn = MagicMock()
    client.user_connection = mock_user_conn
    client.market_connection = mock_market_conn
    client.user_connected = True
    client.market_connected = True

    await client.disconnect()

    assert client.user_connected is False
    assert client.market_connected is False


@pytest.mark.asyncio
async def test_subscribe_user_updates_not_connected():
    """Test subscribing to user updates when not connected."""
    client = ProjectXRealtimeClient("test_token", "test_account")
    client.user_connected = False

    result = await client.subscribe_user_updates()

    assert result is False


@pytest.mark.asyncio
async def test_subscribe_user_updates_success():
    """Test successful user updates subscription."""
    client = ProjectXRealtimeClient("test_token", "test_account")
    client.user_connected = True

    mock_connection = MagicMock()
    client.user_connection = mock_connection

    result = await client.subscribe_user_updates()

    assert result is True
    # Verify invoke was called with Subscribe method
    mock_connection.invoke.assert_called_once_with("Subscribe", ["test_account"])


@pytest.mark.asyncio
async def test_subscribe_market_data_success():
    """Test successful market data subscription."""
    client = ProjectXRealtimeClient("test_token", "test_account")
    client.market_connected = True

    mock_connection = MagicMock()
    client.market_connection = mock_connection

    contract_ids = ["CON.F.US.MGC.M25", "CON.F.US.MNQ.H25"]
    result = await client.subscribe_market_data(contract_ids)

    assert result is True
    assert len(client._subscribed_contracts) == 2
    mock_connection.invoke.assert_called_once_with("Subscribe", [contract_ids])


@pytest.mark.asyncio
async def test_unsubscribe_market_data():
    """Test market data unsubscription."""
    client = ProjectXRealtimeClient("test_token", "test_account")
    client.market_connected = True
    client._subscribed_contracts = ["CON.F.US.MGC.M25", "CON.F.US.MNQ.H25"]

    mock_connection = MagicMock()
    client.market_connection = mock_connection

    result = await client.unsubscribe_market_data(["CON.F.US.MGC.M25"])

    assert result is True
    assert len(client._subscribed_contracts) == 1
    assert "CON.F.US.MGC.M25" not in client._subscribed_contracts


@pytest.mark.asyncio
async def test_add_remove_callback():
    """Test adding and removing callbacks."""
    client = ProjectXRealtimeClient("test_token", "test_account")

    async def test_callback(data):
        pass

    # Add callback
    await client.add_callback("position_update", test_callback)
    assert len(client.callbacks["position_update"]) == 1

    # Remove callback
    await client.remove_callback("position_update", test_callback)
    assert len(client.callbacks["position_update"]) == 0


@pytest.mark.asyncio
async def test_trigger_callbacks():
    """Test callback triggering."""
    client = ProjectXRealtimeClient("test_token", "test_account")

    callback_data = []

    async def async_callback(data):
        callback_data.append(("async", data))

    def sync_callback(data):
        callback_data.append(("sync", data))

    await client.add_callback("test_event", async_callback)
    await client.add_callback("test_event", sync_callback)

    test_data = {"test": "data"}
    await client._trigger_callbacks("test_event", test_data)

    assert len(callback_data) == 2
    assert ("async", test_data) in callback_data
    assert ("sync", test_data) in callback_data


@pytest.mark.asyncio
async def test_connection_event_handlers():
    """Test connection event handlers."""
    client = ProjectXRealtimeClient("test_token", "test_account")

    # Test user hub events
    client._on_user_hub_open()
    assert client.user_connected is True

    client._on_user_hub_close()
    assert client.user_connected is False

    # Test market hub events
    client._on_market_hub_open()
    assert client.market_connected is True

    client._on_market_hub_close()
    assert client.market_connected is False

    # Test error handler
    client._on_connection_error("user", "Test error")
    assert client.stats["connection_errors"] == 1


@pytest.mark.asyncio
async def test_forward_event_async():
    """Test async event forwarding."""
    client = ProjectXRealtimeClient("test_token", "test_account")

    callback_data = []

    async def test_callback(data):
        callback_data.append(data)

    await client.add_callback("test_event", test_callback)

    test_data = {"test": "data"}
    await client._forward_event_async("test_event", test_data)

    assert client.stats["events_received"] == 1
    assert client.stats["last_event_time"] is not None
    assert len(callback_data) == 1
    assert callback_data[0] == test_data


@pytest.mark.asyncio
async def test_event_forwarding_methods():
    """Test event forwarding wrapper methods."""
    client = ProjectXRealtimeClient("test_token", "test_account")

    with patch.object(client, "_forward_event_async", AsyncMock()) as mock_forward:
        # Test each forwarding method
        client._forward_account_update({"account": "data"})
        client._forward_position_update({"position": "data"})
        client._forward_order_update({"order": "data"})
        client._forward_trade_execution({"trade": "data"})
        client._forward_quote_update({"quote": "data"})
        client._forward_market_trade({"market_trade": "data"})
        client._forward_market_depth({"depth": "data"})

        # Wait for tasks to be created
        await asyncio.sleep(0.1)

        # Verify forward was called for each event type
        assert mock_forward.call_count >= 7


@pytest.mark.asyncio
async def test_is_connected():
    """Test connection status check."""
    client = ProjectXRealtimeClient("test_token", "test_account")

    assert client.is_connected() is False

    client.user_connected = True
    assert client.is_connected() is False

    client.market_connected = True
    assert client.is_connected() is True


@pytest.mark.asyncio
async def test_get_stats():
    """Test getting statistics."""
    client = ProjectXRealtimeClient("test_token", "test_account")
    client.stats["events_received"] = 100
    client.user_connected = True
    client._subscribed_contracts = ["MGC", "MNQ"]

    stats = client.get_stats()

    assert stats["events_received"] == 100
    assert stats["user_connected"] is True
    assert stats["market_connected"] is False
    assert stats["subscribed_contracts"] == 2


@pytest.mark.asyncio
async def test_update_jwt_token():
    """Test JWT token update and reconnection."""
    client = ProjectXRealtimeClient("test_token", "test_account")
    client._subscribed_contracts = ["MGC"]

    # Mock successful reconnection
    with patch.object(client, "disconnect", AsyncMock()):
        with patch.object(client, "connect", AsyncMock(return_value=True)):
            with patch.object(
                client, "subscribe_user_updates", AsyncMock(return_value=True)
            ):
                with patch.object(
                    client, "subscribe_market_data", AsyncMock(return_value=True)
                ):
                    result = await client.update_jwt_token("new_token")

    assert result is True
    assert client.jwt_token == "new_token"
    assert "new_token" in client.user_hub_url
    assert "new_token" in client.market_hub_url


@pytest.mark.asyncio
async def test_cleanup():
    """Test cleanup method."""
    client = ProjectXRealtimeClient("test_token", "test_account")
    client.callbacks["test"] = [lambda x: None]

    with patch.object(client, "disconnect", AsyncMock()):
        await client.cleanup()

    assert len(client.callbacks) == 0
