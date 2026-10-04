"""Tests for Features as enum.StrEnum.

These tests specify string/serialization behavior for TradingSuite feature
flags. StrEnum makes str() and f-strings return the member value (e.g.
"orderbook") instead of "Features.ORDERBOOK".
"""

import json
from enum import StrEnum
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from project_x_py import Features, TradingSuite, TradingSuiteConfig
from project_x_py.models import Account


class TestFeaturesStrEnum:
    """StrEnum membership, string conversion, equality, hashing, serialization."""

    def test_features_is_strenum_subclass(self) -> None:
        assert issubclass(Features, StrEnum)

    def test_members_are_strings(self) -> None:
        assert isinstance(Features.ORDERBOOK, str)
        assert isinstance(Features.RISK_MANAGER, str)

    def test_str_returns_value_not_member_name(self) -> None:
        assert str(Features.ORDERBOOK) == "orderbook"
        assert str(Features.ORDERBOOK) != "Features.ORDERBOOK"
        assert str(Features.RISK_MANAGER) == "risk_manager"

    def test_fstring_and_format_return_value(self) -> None:
        assert f"{Features.RISK_MANAGER}" == "risk_manager"
        assert format(Features.ORDERBOOK) == "orderbook"
        assert f"{Features.ORDERBOOK}" == Features.ORDERBOOK.value

    def test_equality_with_plain_strings(self) -> None:
        assert Features.ORDERBOOK == "orderbook"
        assert Features.RISK_MANAGER == "risk_manager"
        assert Features.TRADE_JOURNAL == "trade_journal"
        assert Features.PERFORMANCE_ANALYTICS == "performance_analytics"
        assert Features.AUTO_RECONNECT == "auto_reconnect"

    def test_construction_from_value(self) -> None:
        assert Features("orderbook") is Features.ORDERBOOK
        assert Features("risk_manager") is Features.RISK_MANAGER

    def test_hashing_and_set_membership_with_strings(self) -> None:
        assert "orderbook" in {Features.ORDERBOOK}
        assert Features.ORDERBOOK in {"orderbook", "risk_manager"}
        assert {Features.ORDERBOOK, "orderbook"} == {"orderbook"}
        assert hash(Features.ORDERBOOK) == hash("orderbook")

    def test_json_dumps_member_and_list(self) -> None:
        assert json.dumps(Features.ORDERBOOK) == '"orderbook"'
        assert json.dumps([Features.ORDERBOOK]) == '["orderbook"]'
        assert json.dumps([Features.ORDERBOOK, Features.RISK_MANAGER]) == (
            '["orderbook", "risk_manager"]'
        )

    def test_value_is_plain_string(self) -> None:
        assert Features.ORDERBOOK.value == "orderbook"
        assert Features.RISK_MANAGER.value == "risk_manager"
        unimplemented = [
            f.value
            for f in [Features.TRADE_JOURNAL, Features.AUTO_RECONNECT]
            if f in {Features.TRADE_JOURNAL, Features.AUTO_RECONNECT}
        ]
        assert unimplemented == ["trade_journal", "auto_reconnect"]

    def test_config_serializes_features_as_plain_values(self) -> None:
        config = TradingSuiteConfig(
            "MNQ",
            features=[Features.ORDERBOOK, Features.RISK_MANAGER],
        )
        assert [f.value for f in config.features] == ["orderbook", "risk_manager"]
        assert json.dumps(config.features) == '["orderbook", "risk_manager"]'
        assert json.dumps([str(f) for f in config.features]) == (
            '["orderbook", "risk_manager"]'
        )


def _mock_authenticated_client() -> MagicMock:
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
    return mock_client


@pytest.mark.asyncio
async def test_create_accepts_string_features_and_records_plain_values() -> None:
    """TradingSuite.create(features=[...]) accepts strings and stores values."""
    mock_client = _mock_authenticated_client()
    mock_context = AsyncMock()
    mock_context.__aenter__.return_value = mock_client
    mock_context.__aexit__.return_value = None

    mock_realtime = MagicMock()
    mock_realtime.connect = AsyncMock(return_value=True)
    mock_realtime.disconnect = AsyncMock(return_value=None)
    mock_realtime.is_connected.return_value = True

    mock_data_manager = MagicMock()
    mock_data_manager.initialize = AsyncMock(return_value=True)
    mock_data_manager.cleanup = AsyncMock(return_value=None)

    mock_position_manager = MagicMock()
    mock_position_manager.initialize = AsyncMock(return_value=True)
    mock_position_manager.risk_manager = None

    mock_order_manager = MagicMock()
    mock_order_manager.initialize = AsyncMock(return_value=True)

    with (
        patch(
            "project_x_py.trading_suite.ProjectX.from_env",
            return_value=mock_context,
        ),
        patch(
            "project_x_py.trading_suite.ProjectXRealtimeClient",
            return_value=mock_realtime,
        ),
        patch(
            "project_x_py.trading_suite.RealtimeDataManager",
            return_value=mock_data_manager,
        ),
        patch(
            "project_x_py.trading_suite.PositionManager",
            return_value=mock_position_manager,
        ),
        patch(
            "project_x_py.trading_suite.OrderManager",
            return_value=mock_order_manager,
        ),
    ):
        suite = await TradingSuite.create(
            "MNQ",
            features=["orderbook", "risk_manager"],
            auto_connect=False,
        )

        assert Features.ORDERBOOK in suite.config.features
        assert Features.RISK_MANAGER in suite.config.features
        assert "orderbook" in suite.config.features
        assert [f.value for f in suite.config.features] == [
            "orderbook",
            "risk_manager",
        ]
        assert json.dumps(suite.config.features) == '["orderbook", "risk_manager"]'
        assert json.dumps([str(f) for f in suite.config.features]) == (
            '["orderbook", "risk_manager"]'
        )
