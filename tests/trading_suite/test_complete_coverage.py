"""
Complete test coverage for TradingSuite module following TDD principles.

This test suite ensures 100% coverage by testing all code paths, edge cases,
and error conditions. Tests define expected behavior - if tests fail,
the implementation is wrong, not the tests.

Author: TDD Complete Coverage Suite
Date: 2025-01-30
"""

import asyncio
import json
import warnings
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, PropertyMock, call, patch

import orjson
import pytest
import yaml

from project_x_py import Features, TradingSuite, TradingSuiteConfig
from project_x_py.event_bus import EventBus, EventType
from project_x_py.exceptions import ProjectXAuthenticationError, ProjectXError
from project_x_py.models import Account, Instrument
from project_x_py.order_manager import OrderManager
from project_x_py.orderbook import OrderBook
from project_x_py.position_manager import PositionManager
from project_x_py.realtime import ProjectXRealtimeClient
from project_x_py.realtime_data_manager import RealtimeDataManager
from project_x_py.risk_manager import ManagedTrade, RiskConfig, RiskManager
from project_x_py.sessions import SessionConfig, SessionType
from project_x_py.statistics import StatisticsAggregator
from project_x_py.trading_suite import InstrumentContext
from project_x_py.types.stats_types import TradingSuiteStats


class TestTradingSuiteConfig:
    """Test TradingSuiteConfig methods for configuration generation."""

    def test_get_order_manager_config_with_custom(self):
        """Test order manager config with custom configuration."""
        custom_config = {
            "enable_bracket_orders": False,
            "enable_trailing_stops": False,
            "auto_risk_management": False,
            "enable_order_validation": False,
        }
        config = TradingSuiteConfig(
            instrument="MNQ",
            order_manager_config=custom_config
        )

        result = config.get_order_manager_config()
        assert result == custom_config

    def test_get_order_manager_config_with_risk_manager_feature(self):
        """Test order manager config generation with risk manager feature."""
        config = TradingSuiteConfig(
            instrument="MNQ",
            features=[Features.RISK_MANAGER]
        )

        result = config.get_order_manager_config()
        assert result["enable_bracket_orders"] is True
        assert result["auto_risk_management"] is True
        assert result["enable_trailing_stops"] is True
        assert result["enable_order_validation"] is True

    def test_get_order_manager_config_without_risk_manager(self):
        """Test order manager config generation without risk manager."""
        config = TradingSuiteConfig(instrument="MNQ")

        result = config.get_order_manager_config()
        assert result["enable_bracket_orders"] is False
        assert result["auto_risk_management"] is False
        assert result["enable_trailing_stops"] is True
        assert result["enable_order_validation"] is True

    def test_get_position_manager_config_with_custom(self):
        """Test position manager config with custom configuration."""
        custom_config = {
            "enable_risk_monitoring": True,
            "enable_correlation_analysis": True,
            "enable_portfolio_rebalancing": True,
        }
        config = TradingSuiteConfig(
            instrument="ES",
            position_manager_config=custom_config
        )

        result = config.get_position_manager_config()
        assert result == custom_config

    def test_get_position_manager_config_with_features(self):
        """Test position manager config generation with features."""
        config = TradingSuiteConfig(
            instrument="ES",
            features=[Features.RISK_MANAGER, Features.PERFORMANCE_ANALYTICS]
        )

        result = config.get_position_manager_config()
        assert result["enable_risk_monitoring"] is True
        assert result["enable_correlation_analysis"] is True
        assert result["enable_portfolio_rebalancing"] is False

    def test_get_data_manager_config_with_custom(self):
        """Test data manager config with custom configuration."""
        custom_config = {
            "max_bars_per_timeframe": 2000,
            "enable_tick_data": False,
            "enable_level2_data": True,
            "data_validation": False,
            "auto_cleanup": False,
            "enable_dynamic_limits": False,
        }
        config = TradingSuiteConfig(
            instrument="MGC",
            data_manager_config=custom_config
        )

        result = config.get_data_manager_config()
        assert result == custom_config

    def test_get_data_manager_config_with_orderbook_feature(self):
        """Test data manager config generation with orderbook feature."""
        config = TradingSuiteConfig(
            instrument="MGC",
            features=[Features.ORDERBOOK]
        )

        result = config.get_data_manager_config()
        assert result["enable_level2_data"] is True
        assert result["enable_dynamic_limits"] is True
        assert result["resource_config"]["memory_target_percent"] == 15.0

    def test_get_orderbook_config_with_custom(self):
        """Test orderbook config with custom configuration."""
        custom_config = {
            "max_depth_levels": 50,
            "max_trade_history": 500,
            "enable_analytics": True,
            "enable_pattern_detection": False,
        }
        config = TradingSuiteConfig(
            instrument="CL",
            orderbook_config=custom_config
        )

        result = config.get_orderbook_config()
        assert result == custom_config

    def test_get_orderbook_config_with_analytics_feature(self):
        """Test orderbook config generation with analytics feature."""
        config = TradingSuiteConfig(
            instrument="CL",
            features=[Features.PERFORMANCE_ANALYTICS]
        )

        result = config.get_orderbook_config()
        assert result["enable_analytics"] is True
        assert result["enable_pattern_detection"] is True
        assert result["max_depth_levels"] == 100

    def test_get_risk_config_with_custom(self):
        """Test risk config with custom configuration."""
        custom_config = RiskConfig(
            max_risk_per_trade=Decimal("0.02"),
            max_daily_loss=Decimal("0.05"),
            max_positions=5,
            use_stop_loss=False,
            use_take_profit=False,
            use_trailing_stops=False,
            default_risk_reward_ratio=Decimal("3.0"),
        )
        config = TradingSuiteConfig(
            instrument="NQ",
            risk_config=custom_config
        )

        result = config.get_risk_config()
        assert result == custom_config

    def test_get_risk_config_default(self):
        """Test risk config default generation."""
        config = TradingSuiteConfig(instrument="NQ")

        result = config.get_risk_config()
        assert result.max_risk_per_trade == Decimal("0.01")
        assert result.max_daily_loss == Decimal("0.03")
        assert result.max_positions == 3
        assert result.use_stop_loss is True
        assert result.use_take_profit is True
        assert result.use_trailing_stops is True
        assert result.default_risk_reward_ratio == Decimal("2.0")


class TestMultiInstrumentContexts:
    """Test multi-instrument context creation and management."""

    @pytest.mark.asyncio
    async def test_create_instrument_contexts_success(self):
        """Test successful parallel creation of multiple instrument contexts."""
        mock_client = self._create_mock_client()
        mock_realtime = self._create_mock_realtime_client()
        config = TradingSuiteConfig(
            instrument="MNQ",
            features=[Features.ORDERBOOK, Features.RISK_MANAGER]
        )

        with patch("project_x_py.trading_suite.RealtimeDataManager") as MockDataManager, \
             patch("project_x_py.trading_suite.OrderManager") as MockOrderManager, \
             patch("project_x_py.trading_suite.PositionManager") as MockPositionManager, \
             patch("project_x_py.trading_suite.OrderBook") as MockOrderBook, \
             patch("project_x_py.trading_suite.RiskManager") as MockRiskManager, \
             patch("project_x_py.trading_suite.EventBus") as MockEventBus:

            # Set up mocks
            MockDataManager.return_value = Mock(spec=RealtimeDataManager)
            MockOrderManager.return_value = Mock(spec=OrderManager)
            MockPositionManager.return_value = Mock(spec=PositionManager)
            MockOrderBook.return_value = Mock(spec=OrderBook)
            MockRiskManager.return_value = Mock(spec=RiskManager)
            MockEventBus.return_value = Mock(spec=EventBus)

            contexts = await TradingSuite._create_instrument_contexts(
                ["MNQ", "MES", "MCL"],
                mock_client,
                mock_realtime,
                config
            )

            # Verify all contexts were created
            assert len(contexts) == 3
            assert "MNQ" in contexts
            assert "MES" in contexts
            assert "MCL" in contexts

            # Verify each context has all components
            for symbol, context in contexts.items():
                assert context.symbol == symbol
                assert context.instrument_info is not None
                assert context.data is not None
                assert context.orders is not None
                assert context.positions is not None
                assert context.orderbook is not None  # Feature enabled
                assert context.risk_manager is not None  # Feature enabled

    @pytest.mark.asyncio
    async def test_create_instrument_contexts_partial_failure(self):
        """Test cleanup when one context fails during parallel creation."""
        mock_client = self._create_mock_client()
        # Make the second instrument fail
        mock_client.get_instrument.side_effect = [
            self._create_mock_instrument("MNQ"),
            Exception("Failed to get MES instrument"),
            self._create_mock_instrument("MCL"),
        ]
        mock_realtime = self._create_mock_realtime_client()
        config = TradingSuiteConfig(instrument="MNQ")

        with patch("project_x_py.trading_suite.RealtimeDataManager") as MockDataManager, \
             patch("project_x_py.trading_suite.OrderManager") as MockOrderManager, \
             patch("project_x_py.trading_suite.PositionManager") as MockPositionManager, \
             patch("project_x_py.trading_suite.EventBus") as MockEventBus:

            # Set up mocks
            MockDataManager.return_value = Mock(spec=RealtimeDataManager)
            MockOrderManager.return_value = Mock(spec=OrderManager)
            MockPositionManager.return_value = Mock(spec=PositionManager)
            MockEventBus.return_value = Mock(spec=EventBus)

            # Mock cleanup for partial contexts
            cleanup_mock = AsyncMock()
            with patch.object(TradingSuite, "_cleanup_contexts", cleanup_mock):
                with pytest.raises(Exception, match="Failed to get MES instrument"):
                    await TradingSuite._create_instrument_contexts(
                        ["MNQ", "MES", "MCL"],
                        mock_client,
                        mock_realtime,
                        config
                    )

                # Verify cleanup was called
                cleanup_mock.assert_called()

    @pytest.mark.asyncio
    async def test_cleanup_contexts(self):
        """Test cleanup of partially created contexts."""
        # Create mock contexts with cleanup methods
        context1 = InstrumentContext(
            symbol="MNQ",
            instrument_info=self._create_mock_instrument("MNQ"),
            data=AsyncMock(spec=RealtimeDataManager),
            orders=AsyncMock(spec=OrderManager),
            positions=AsyncMock(spec=PositionManager),
            orderbook=AsyncMock(spec=OrderBook),
            risk_manager=AsyncMock(spec=RiskManager),
        )

        context2 = InstrumentContext(
            symbol="MES",
            instrument_info=self._create_mock_instrument("MES"),
            data=AsyncMock(spec=RealtimeDataManager),
            orders=AsyncMock(spec=OrderManager),
            positions=AsyncMock(spec=PositionManager),
            orderbook=None,  # No orderbook
            risk_manager=None,  # No risk manager
        )

        contexts = {"MNQ": context1, "MES": context2}

        # Call cleanup
        await TradingSuite._cleanup_contexts(contexts)

        # Verify cleanup was called on all components
        context1.data.cleanup.assert_called_once()
        context1.orders.cleanup.assert_called_once()
        context1.positions.cleanup.assert_called_once()
        context1.orderbook.cleanup.assert_called_once()
        context1.risk_manager.cleanup.assert_called_once()

        context2.data.cleanup.assert_called_once()
        context2.orders.cleanup.assert_called_once()
        context2.positions.cleanup.assert_called_once()
        # Orderbook and risk_manager should not be called (None)

    @pytest.mark.asyncio
    async def test_cleanup_contexts_with_errors(self):
        """Test cleanup continues even if some components fail."""
        # Create context with failing cleanup
        context = InstrumentContext(
            symbol="MNQ",
            instrument_info=self._create_mock_instrument("MNQ"),
            data=AsyncMock(spec=RealtimeDataManager),
            orders=AsyncMock(spec=OrderManager),
            positions=AsyncMock(spec=PositionManager),
            orderbook=AsyncMock(spec=OrderBook),
            risk_manager=None,
        )

        # Make data cleanup fail
        context.data.cleanup.side_effect = Exception("Data cleanup failed")

        contexts = {"MNQ": context}

        # Cleanup should not raise even with errors
        await TradingSuite._cleanup_contexts(contexts)

        # Verify other cleanups were still called
        context.orders.cleanup.assert_called_once()
        context.positions.cleanup.assert_called_once()
        context.orderbook.cleanup.assert_called_once()

    def _create_mock_client(self):
        """Create a mock ProjectX client."""
        mock_client = AsyncMock()
        mock_client.authenticate = AsyncMock()
        mock_client.account_info = Mock(id=12345)
        mock_client.session_token = "test_jwt_token"
        mock_client.config = Mock()
        mock_client.get_instrument = AsyncMock(return_value=self._create_mock_instrument("MNQ"))
        return mock_client

    def _create_mock_realtime_client(self):
        """Create a mock realtime client."""
        mock_realtime = AsyncMock(spec=ProjectXRealtimeClient)
        mock_realtime.connect = AsyncMock()
        mock_realtime.disconnect = AsyncMock()
        mock_realtime.subscribe_user_updates = AsyncMock()
        mock_realtime.subscribe_market_data = AsyncMock()
        mock_realtime.is_connected.return_value = True
        return mock_realtime

    def _create_mock_instrument(self, symbol):
        """Create a mock instrument."""
        return Mock(
            id=f"CON.F.US.{symbol}.U25",
            symbol=symbol,
            name=f"Micro E-mini {symbol}",
            spec=Instrument
        )


class TestContainerProtocol:
    """Test container protocol methods for TradingSuite."""

    @pytest.mark.asyncio
    async def test_getitem_single_instrument(self):
        """Test __getitem__ with single instrument suite."""
        suite = await self._create_suite_with_contexts(["MNQ"])

        # Access by symbol should work
        context = suite["MNQ"]
        assert isinstance(context, InstrumentContext)
        assert context.symbol == "MNQ"

    @pytest.mark.asyncio
    async def test_getitem_multi_instrument(self):
        """Test __getitem__ with multi-instrument suite."""
        suite = await self._create_suite_with_contexts(["MNQ", "MES", "MCL"])

        # Access each instrument
        mnq = suite["MNQ"]
        mes = suite["MES"]
        mcl = suite["MCL"]

        assert mnq.symbol == "MNQ"
        assert mes.symbol == "MES"
        assert mcl.symbol == "MCL"

    @pytest.mark.asyncio
    async def test_getitem_key_error(self):
        """Test __getitem__ raises KeyError for unknown symbol."""
        suite = await self._create_suite_with_contexts(["MNQ"])

        with pytest.raises(KeyError):
            _ = suite["UNKNOWN"]

    @pytest.mark.asyncio
    async def test_len(self):
        """Test __len__ returns correct instrument count."""
        suite_single = await self._create_suite_with_contexts(["MNQ"])
        suite_multi = await self._create_suite_with_contexts(["MNQ", "MES", "MCL"])

        assert len(suite_single) == 1
        assert len(suite_multi) == 3

    @pytest.mark.asyncio
    async def test_iter(self):
        """Test __iter__ returns instrument symbols."""
        suite = await self._create_suite_with_contexts(["MNQ", "MES", "MCL"])

        symbols = list(suite)
        assert symbols == ["MNQ", "MES", "MCL"]

    @pytest.mark.asyncio
    async def test_contains(self):
        """Test __contains__ for instrument membership."""
        suite = await self._create_suite_with_contexts(["MNQ", "MES"])

        assert "MNQ" in suite
        assert "MES" in suite
        assert "MCL" not in suite
        assert "UNKNOWN" not in suite

    @pytest.mark.asyncio
    async def test_keys(self):
        """Test keys() returns instrument symbols."""
        suite = await self._create_suite_with_contexts(["MNQ", "MES"])

        keys = list(suite.keys())
        assert keys == ["MNQ", "MES"]

    @pytest.mark.asyncio
    async def test_values(self):
        """Test values() returns instrument contexts."""
        suite = await self._create_suite_with_contexts(["MNQ", "MES"])

        values = list(suite.values())
        assert len(values) == 2
        assert all(isinstance(v, InstrumentContext) for v in values)
        assert values[0].symbol == "MNQ"
        assert values[1].symbol == "MES"

    @pytest.mark.asyncio
    async def test_items(self):
        """Test items() returns (symbol, context) pairs."""
        suite = await self._create_suite_with_contexts(["MNQ", "MES"])

        items = list(suite.items())
        assert len(items) == 2
        assert items[0] == ("MNQ", suite["MNQ"])
        assert items[1] == ("MES", suite["MES"])

    async def _create_suite_with_contexts(self, symbols):
        """Helper to create suite with mock contexts."""
        mock_client = AsyncMock()
        mock_client.account_info = Mock(id=12345)
        mock_realtime = AsyncMock(spec=ProjectXRealtimeClient)
        config = TradingSuiteConfig(instrument=symbols[0] if symbols else "MNQ")

        # Create mock contexts
        contexts = {}
        for symbol in symbols:
            contexts[symbol] = InstrumentContext(
                symbol=symbol,
                instrument_info=Mock(id=f"CON.F.US.{symbol}.U25"),
                data=Mock(spec=RealtimeDataManager),
                orders=Mock(spec=OrderManager),
                positions=Mock(spec=PositionManager),
                orderbook=None,
                risk_manager=None,
            )

        return TradingSuite(mock_client, mock_realtime, config, contexts)


class TestSessionHandling:
    """Test session handling methods."""

    @pytest.mark.asyncio
    async def test_set_session_type_single_instrument(self):
        """Test set_session_type for single instrument suite."""
        suite = await self._create_suite_with_session_support(["MNQ"])

        # Set session type
        await suite.set_session_type(SessionType.RTH)

        # Verify it was called on the data manager
        suite._single_context.data.set_session_type.assert_called_once_with(SessionType.RTH)

    @pytest.mark.asyncio
    async def test_set_session_type_multi_instrument(self):
        """Test set_session_type for multi-instrument suite."""
        suite = await self._create_suite_with_session_support(["MNQ", "MES"])

        # Remove single context to force multi-instrument path
        suite._is_single_instrument = False
        suite._single_context = None

        # Set session type
        await suite.set_session_type(SessionType.ETH)

        # Verify it was called on all data managers
        for context in suite._instruments.values():
            context.data.set_session_type.assert_called_once_with(SessionType.ETH)

    @pytest.mark.asyncio
    async def test_get_session_data_single_instrument(self):
        """Test get_session_data for single instrument."""
        suite = await self._create_suite_with_session_support(["MNQ"])

        # Mock return value
        mock_data = Mock()
        suite._single_context.data.get_session_data.return_value = mock_data

        # Get session data
        result = await suite.get_session_data("5min", SessionType.RTH)

        assert result == mock_data
        suite._single_context.data.get_session_data.assert_called_once_with("5min", SessionType.RTH)

    @pytest.mark.asyncio
    async def test_get_session_data_fallback(self):
        """Test get_session_data fallback when session support not available."""
        suite = await self._create_suite_with_session_support(["MNQ"])

        # Remove session support
        delattr(suite._single_context.data, "get_session_data")

        # Mock regular get_data
        mock_data = Mock()
        suite._single_context.data.get_data = AsyncMock(return_value=mock_data)

        # Should fall back to get_data
        result = await suite.get_session_data("1min")

        assert result == mock_data
        suite._single_context.data.get_data.assert_called_once_with("1min")

    @pytest.mark.asyncio
    async def test_get_session_statistics_single_instrument(self):
        """Test get_session_statistics for single instrument."""
        suite = await self._create_suite_with_session_support(["MNQ"])

        # Mock return value
        mock_stats = {"rth_volume": 1000, "eth_volume": 500}
        suite._single_context.data.get_session_statistics.return_value = mock_stats

        # Get statistics
        result = await suite.get_session_statistics("1min")

        assert result == mock_stats
        suite._single_context.data.get_session_statistics.assert_called_once_with("1min")

    @pytest.mark.asyncio
    async def test_get_session_statistics_no_support(self):
        """Test get_session_statistics when not supported."""
        suite = await self._create_suite_with_session_support(["MNQ"])

        # Remove session statistics support
        delattr(suite._single_context.data, "get_session_statistics")

        # Should return empty dict
        result = await suite.get_session_statistics()

        assert result == {}

    async def _create_suite_with_session_support(self, symbols):
        """Helper to create suite with session-aware data managers."""
        mock_client = AsyncMock()
        mock_client.account_info = Mock(id=12345)
        mock_realtime = AsyncMock(spec=ProjectXRealtimeClient)
        config = TradingSuiteConfig(instrument=symbols[0])

        # Create contexts with session support
        contexts = {}
        for symbol in symbols:
            data_manager = Mock(spec=RealtimeDataManager)
            data_manager.set_session_type = AsyncMock()
            data_manager.get_session_data = AsyncMock()
            data_manager.get_session_statistics = AsyncMock()

            contexts[symbol] = InstrumentContext(
                symbol=symbol,
                instrument_info=Mock(id=f"CON.F.US.{symbol}.U25"),
                data=data_manager,
                orders=Mock(spec=OrderManager),
                positions=Mock(spec=PositionManager),
                orderbook=None,
                risk_manager=None,
            )

        suite = TradingSuite(mock_client, mock_realtime, config, contexts)
        return suite


class TestPropertiesAndGetAttr:
    """Test property access and __getattr__ behavior."""

    @pytest.mark.asyncio
    async def test_symbol_property(self):
        """Test symbol property returns original symbol."""
        suite = await self._create_basic_suite("MNQ")
        assert suite.symbol == "MNQ"

    @pytest.mark.asyncio
    async def test_instrument_id_property(self):
        """Test instrument_id property returns full contract ID."""
        suite = await self._create_basic_suite("MNQ")
        suite.instrument = Mock(id="CON.F.US.MNQ.U25")

        assert suite.instrument_id == "CON.F.US.MNQ.U25"

    @pytest.mark.asyncio
    async def test_instrument_id_property_none(self):
        """Test instrument_id property returns None when no instrument."""
        suite = await self._create_basic_suite("MNQ")
        suite.instrument = None

        assert suite.instrument_id is None

    @pytest.mark.asyncio
    async def test_getattr_single_instrument_valid(self):
        """Test __getattr__ for valid attribute in single-instrument mode."""
        suite = await self._create_suite_with_single_context()

        # Create a mock context that allows attribute assignment
        mock_context = Mock()
        mock_context.symbol = "MNQ"
        mock_context.custom_attr = "test_value"

        # Replace the frozen context with the mock
        suite._single_context = mock_context

        # Should access with deprecation warning
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            value = suite.custom_attr

            assert value == "test_value"
            assert len(w) == 1
            assert "deprecated" in str(w[0].message).lower()

    @pytest.mark.asyncio
    async def test_getattr_single_instrument_invalid(self):
        """Test __getattr__ raises AttributeError for invalid attribute."""
        suite = await self._create_suite_with_single_context()

        with pytest.raises(AttributeError, match="has no attribute 'invalid_attr'"):
            _ = suite.invalid_attr

    @pytest.mark.asyncio
    async def test_getattr_multi_instrument_error(self):
        """Test __getattr__ provides helpful error for multi-instrument suites."""
        suite = await self._create_suite_with_multiple_contexts()

        # Force multi-instrument mode
        suite._is_single_instrument = False

        with pytest.raises(AttributeError) as exc_info:
            _ = suite.some_attr

        error_msg = str(exc_info.value)
        assert "multi-instrument suites" in error_msg
        assert "suite['SYMBOL']" in error_msg
        assert "MNQ" in error_msg  # Should list available instruments

    async def _create_basic_suite(self, symbol):
        """Create basic suite for testing."""
        mock_client = AsyncMock()
        mock_client.account_info = Mock(id=12345)
        mock_realtime = AsyncMock(spec=ProjectXRealtimeClient)
        config = TradingSuiteConfig(instrument=symbol)

        return TradingSuite(mock_client, mock_realtime, config)

    async def _create_suite_with_single_context(self):
        """Create suite with single instrument context."""
        mock_client = AsyncMock()
        mock_client.account_info = Mock(id=12345)
        mock_realtime = AsyncMock(spec=ProjectXRealtimeClient)
        config = TradingSuiteConfig(instrument="MNQ")

        context = InstrumentContext(
            symbol="MNQ",
            instrument_info=Mock(id="CON.F.US.MNQ.U25"),
            data=Mock(spec=RealtimeDataManager),
            orders=Mock(spec=OrderManager),
            positions=Mock(spec=PositionManager),
            orderbook=None,
            risk_manager=None,
        )

        suite = TradingSuite(mock_client, mock_realtime, config, {"MNQ": context})
        return suite

    async def _create_suite_with_multiple_contexts(self):
        """Create suite with multiple instrument contexts."""
        mock_client = AsyncMock()
        mock_client.account_info = Mock(id=12345)
        mock_realtime = AsyncMock(spec=ProjectXRealtimeClient)
        config = TradingSuiteConfig(instrument="MNQ")

        contexts = {}
        for symbol in ["MNQ", "MES", "MCL"]:
            contexts[symbol] = InstrumentContext(
                symbol=symbol,
                instrument_info=Mock(id=f"CON.F.US.{symbol}.U25"),
                data=Mock(spec=RealtimeDataManager),
                orders=Mock(spec=OrderManager),
                positions=Mock(spec=PositionManager),
                orderbook=None,
                risk_manager=None,
            )

        suite = TradingSuite(mock_client, mock_realtime, config, contexts)
        return suite


class TestDisconnectAndCleanup:
    """Test disconnect and cleanup methods."""

    @pytest.mark.asyncio
    async def test_disconnect_single_instrument(self):
        """Test disconnect for single instrument suite."""
        mock_client = AsyncMock()
        mock_client.account_info = Mock(id=12345)
        mock_realtime = AsyncMock(spec=ProjectXRealtimeClient)
        config = TradingSuiteConfig(instrument="MNQ")

        # Create suite with legacy single instrument mode
        suite = TradingSuite(mock_client, mock_realtime, config)
        suite._data = AsyncMock(spec=RealtimeDataManager)
        suite._orderbook = AsyncMock(spec=OrderBook)
        suite._connected = True
        suite._initialized = True

        # Disconnect
        await suite.disconnect()

        # Verify cleanup was called
        suite._data.stop_realtime_feed.assert_called_once()
        suite._data.cleanup.assert_called_once()
        suite._orderbook.cleanup.assert_called_once()
        mock_realtime.disconnect.assert_called_once()

        assert suite._connected is False
        assert suite._initialized is False

    @pytest.mark.asyncio
    async def test_disconnect_multi_instrument(self):
        """Test disconnect for multi-instrument suite."""
        mock_client = AsyncMock()
        mock_client.account_info = Mock(id=12345)
        mock_realtime = AsyncMock(spec=ProjectXRealtimeClient)
        config = TradingSuiteConfig(instrument="MNQ")

        # Create contexts
        contexts = {}
        for symbol in ["MNQ", "MES"]:
            data = AsyncMock(spec=RealtimeDataManager)
            orderbook = AsyncMock(spec=OrderBook) if symbol == "MNQ" else None

            contexts[symbol] = InstrumentContext(
                symbol=symbol,
                instrument_info=Mock(id=f"CON.F.US.{symbol}.U25"),
                data=data,
                orders=Mock(spec=OrderManager),
                positions=Mock(spec=PositionManager),
                orderbook=orderbook,
                risk_manager=None,
            )

        suite = TradingSuite(mock_client, mock_realtime, config, contexts)
        suite._connected = True
        suite._initialized = True

        # Disconnect
        await suite.disconnect()

        # Verify cleanup for all contexts
        contexts["MNQ"].data.stop_realtime_feed.assert_called_once()
        contexts["MNQ"].data.cleanup.assert_called_once()
        contexts["MNQ"].orderbook.cleanup.assert_called_once()

        contexts["MES"].data.stop_realtime_feed.assert_called_once()
        contexts["MES"].data.cleanup.assert_called_once()
        # MES has no orderbook, so cleanup should not be called

        mock_realtime.disconnect.assert_called_once()
        assert suite._connected is False
        assert suite._initialized is False

    @pytest.mark.asyncio
    async def test_disconnect_with_client_context(self):
        """Test disconnect properly cleans up client context."""
        mock_client_context = AsyncMock()
        mock_client = AsyncMock()
        mock_client.account_info = Mock(id=12345)
        mock_realtime = AsyncMock(spec=ProjectXRealtimeClient)
        config = TradingSuiteConfig(instrument="MNQ")

        suite = TradingSuite(mock_client, mock_realtime, config)
        suite._client_context = mock_client_context
        suite._connected = True

        # Disconnect
        await suite.disconnect()

        # Verify client context was cleaned up
        mock_client_context.__aexit__.assert_called_once_with(None, None, None)

    @pytest.mark.asyncio
    async def test_disconnect_client_context_error(self):
        """Test disconnect continues even if client context cleanup fails."""
        mock_client_context = AsyncMock()
        mock_client_context.__aexit__.side_effect = Exception("Context cleanup failed")

        mock_client = AsyncMock()
        mock_client.account_info = Mock(id=12345)
        mock_realtime = AsyncMock(spec=ProjectXRealtimeClient)
        config = TradingSuiteConfig(instrument="MNQ")

        suite = TradingSuite(mock_client, mock_realtime, config)
        suite._client_context = mock_client_context
        suite._connected = True

        # Disconnect should not raise
        await suite.disconnect()

        # Should still complete disconnect
        assert suite._connected is False
        assert suite._initialized is False


class TestBackwardCompatibilityProperties:
    """Test backward compatibility properties with real logic."""

    @pytest.mark.asyncio
    async def test_data_property_legacy_mode(self):
        """Test data property in legacy single-instrument mode."""
        mock_client = AsyncMock()
        mock_client.account_info = Mock(id=12345)
        mock_realtime = AsyncMock(spec=ProjectXRealtimeClient)
        config = TradingSuiteConfig(instrument="MNQ")

        suite = TradingSuite(mock_client, mock_realtime, config)
        mock_data = Mock(spec=RealtimeDataManager)
        suite._data = mock_data
        suite._symbol = "MNQ"

        # Access data property
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            data = suite.data

            assert data == mock_data
            assert len(w) == 1
            assert "deprecated" in str(w[0].message).lower()
            assert "suite['MNQ'].data" in str(w[0].message)

    @pytest.mark.asyncio
    async def test_data_property_multi_instrument_mode(self):
        """Test data property in multi-instrument mode."""
        mock_client = AsyncMock()
        mock_client.account_info = Mock(id=12345)
        mock_realtime = AsyncMock(spec=ProjectXRealtimeClient)
        config = TradingSuiteConfig(instrument="MNQ")

        context = InstrumentContext(
            symbol="MNQ",
            instrument_info=Mock(),
            data=Mock(spec=RealtimeDataManager),
            orders=Mock(spec=OrderManager),
            positions=Mock(spec=PositionManager),
            orderbook=None,
            risk_manager=None,
        )

        suite = TradingSuite(mock_client, mock_realtime, config, {"MNQ": context})

        # Access data property
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            data = suite.data

            assert data == context.data
            assert len(w) == 1
            assert "deprecated" in str(w[0].message).lower()

    @pytest.mark.asyncio
    async def test_data_property_no_attribute(self):
        """Test data property raises AttributeError when not available."""
        mock_client = AsyncMock()
        mock_client.account_info = Mock(id=12345)
        mock_realtime = AsyncMock(spec=ProjectXRealtimeClient)
        config = TradingSuiteConfig(instrument="MNQ")

        # Create suite with no contexts (empty dict)
        suite = TradingSuite(mock_client, mock_realtime, config, {})

        # Ensure neither _data attribute nor single context exists
        suite._is_single_instrument = False
        suite._single_context = None
        # Make sure _data attribute doesn't exist
        if hasattr(suite, '_data'):
            delattr(suite, '_data')

        with pytest.raises(AttributeError, match="has no attribute 'data'"):
            _ = suite.data

    @pytest.mark.asyncio
    async def test_all_backward_compat_properties(self):
        """Test all backward compatibility properties work correctly."""
        mock_client = AsyncMock()
        mock_client.account_info = Mock(id=12345)
        mock_realtime = AsyncMock(spec=ProjectXRealtimeClient)
        config = TradingSuiteConfig(instrument="MNQ")

        # Create suite with all components
        suite = TradingSuite(mock_client, mock_realtime, config)
        suite._symbol = "MNQ"
        suite._data = Mock(spec=RealtimeDataManager)
        suite._orders = Mock(spec=OrderManager)
        suite._positions = Mock(spec=PositionManager)
        suite._orderbook = Mock(spec=OrderBook)
        suite._risk_manager = Mock(spec=RiskManager)

        # Test each property generates deprecation warning
        properties_to_test = [
            ("data", suite._data),
            ("orders", suite._orders),
            ("positions", suite._positions),
            ("orderbook", suite._orderbook),
            ("risk_manager", suite._risk_manager),
        ]

        for prop_name, expected_value in properties_to_test:
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                value = getattr(suite, prop_name)

                assert value == expected_value
                assert len(w) == 1
                assert "deprecated" in str(w[0].message).lower()
                assert f"suite['MNQ'].{prop_name}" in str(w[0].message)


class TestEdgeCasesAndErrorHandling:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_create_with_no_instruments_legacy(self):
        """Test create with instrument parameter (backward compatibility)."""
        mock_client = AsyncMock()
        mock_client.account_info = Mock(id=12345)
        mock_client.session_token = "test_token"
        mock_client.config = Mock()
        mock_client.get_instrument = AsyncMock(return_value=Mock(id="CON.F.US.MNQ.U25"))

        with patch("project_x_py.trading_suite.ProjectX") as MockProjectX, \
             patch("project_x_py.trading_suite.ProjectXRealtimeClient") as MockRealtime, \
             patch("project_x_py.trading_suite.RealtimeDataManager") as MockDataManager, \
             patch("project_x_py.trading_suite.OrderManager") as MockOrderManager, \
             patch("project_x_py.trading_suite.PositionManager") as MockPositionManager:

            # Set up mocks
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_client
            MockProjectX.from_env.return_value = mock_context
            MockRealtime.return_value = AsyncMock(spec=ProjectXRealtimeClient)
            MockDataManager.return_value = Mock(spec=RealtimeDataManager)
            MockOrderManager.return_value = Mock(spec=OrderManager)
            MockPositionManager.return_value = Mock(spec=PositionManager)

            # Use deprecated instrument parameter
            suite = await TradingSuite.create(instrument="MNQ")

            assert suite is not None
            assert suite.symbol == "MNQ"

    @pytest.mark.asyncio
    async def test_from_config_invalid_extension(self):
        """Test from_config with invalid file extension."""
        with pytest.raises(ValueError, match="Unsupported config format"):
            await TradingSuite.from_config("config.txt")

    @pytest.mark.asyncio
    async def test_from_config_file_not_found(self):
        """Test from_config when file doesn't exist."""
        with pytest.raises(FileNotFoundError, match="Configuration file not found"):
            await TradingSuite.from_config("/nonexistent/config.yaml")

    @pytest.mark.asyncio
    async def test_get_stats_sync_with_running_loop(self):
        """Test get_stats_sync when event loop is already running."""
        mock_client = AsyncMock()
        mock_client.account_info = Mock(id=12345)
        mock_realtime = AsyncMock(spec=ProjectXRealtimeClient)
        config = TradingSuiteConfig(instrument="MNQ")

        suite = TradingSuite(mock_client, mock_realtime, config)
        suite._stats_aggregator = Mock(spec=StatisticsAggregator)

        # Mock the async get_stats
        mock_stats = TradingSuiteStats(
            timestamp="2025-01-30T12:00:00",
            health_score=100,
            components={},
            metadata={}
        )
        suite._stats_aggregator.aggregate_stats = AsyncMock(return_value=mock_stats)

        # Test with ThreadPoolExecutor path
        with patch("asyncio.get_running_loop") as mock_get_loop:
            mock_get_loop.side_effect = RuntimeError("No running loop")

            with patch("asyncio.get_event_loop") as mock_get_event_loop:
                mock_loop = Mock()
                mock_loop.is_running.return_value = True
                mock_get_event_loop.return_value = mock_loop

                with patch("concurrent.futures.ThreadPoolExecutor") as MockExecutor:
                    mock_executor = MockExecutor.return_value.__enter__.return_value
                    mock_future = Mock()
                    mock_future.result.return_value = mock_stats
                    mock_executor.submit.return_value = mock_future

                    with warnings.catch_warnings(record=True) as w:
                        warnings.simplefilter("always")
                        result = suite.get_stats_sync()

                        assert result == mock_stats
                        # May have multiple warnings (deprecation + runtime)
                        assert len(w) >= 1
                        # Check that at least one is a deprecation warning
                        deprecation_warnings = [warning for warning in w if "deprecated" in str(warning.message).lower()]
                        assert len(deprecation_warnings) >= 1

    @pytest.mark.asyncio
    async def test_connect_already_connected(self):
        """Test connect when already connected does nothing."""
        mock_client = AsyncMock()
        mock_client.account_info = Mock(id=12345)
        mock_realtime = AsyncMock(spec=ProjectXRealtimeClient)
        config = TradingSuiteConfig(instrument="MNQ")

        suite = TradingSuite(mock_client, mock_realtime, config)
        suite._connected = True
        suite._initialized = True

        # Mock _initialize to track if it's called
        suite._initialize = AsyncMock()

        await suite.connect()

        # Should not call _initialize if already connected
        suite._initialize.assert_not_called()

    @pytest.mark.asyncio
    async def test_context_manager_with_exception(self):
        """Test context manager properly cleans up on exception."""
        mock_client = AsyncMock()
        mock_client.account_info = Mock(id=12345)
        mock_realtime = AsyncMock(spec=ProjectXRealtimeClient)
        config = TradingSuiteConfig(instrument="MNQ")

        suite = TradingSuite(mock_client, mock_realtime, config)
        suite._initialize = AsyncMock()
        suite.disconnect = AsyncMock()

        # Test exception handling
        with pytest.raises(ValueError):
            async with suite:
                raise ValueError("Test error")

        # Verify cleanup was called
        suite.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_is_connected_property(self):
        """Test is_connected property logic."""
        mock_client = AsyncMock()
        mock_client.account_info = Mock(id=12345)
        mock_realtime = AsyncMock(spec=ProjectXRealtimeClient)
        mock_realtime.is_connected.return_value = True
        config = TradingSuiteConfig(instrument="MNQ")

        suite = TradingSuite(mock_client, mock_realtime, config)

        # Not connected initially
        suite._connected = False
        assert suite.is_connected is False

        # Connected but realtime not connected
        suite._connected = True
        mock_realtime.is_connected.return_value = False
        assert suite.is_connected is False

        # Both connected
        mock_realtime.is_connected.return_value = True
        assert suite.is_connected is True
