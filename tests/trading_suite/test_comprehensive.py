"""
Comprehensive TDD test suite for TradingSuite module.

This test suite follows strict Test-Driven Development principles:
1. Tests define the EXPECTED behavior, not current behavior
2. If tests fail, the implementation is wrong, not the test
3. Tests serve as the specification for how the system SHOULD work
4. Tests focus on behavior and outcomes, not implementation details

Author: TDD Test Suite
Date: 2025-01-30
"""

import asyncio
from decimal import Decimal
from pathlib import Path
from types import TracebackType
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, PropertyMock, call, patch

import pytest
import yaml

from project_x_py import EventType, Features, TradingSuite, TradingSuiteConfig
from project_x_py.event_bus import Event, EventBus
from project_x_py.exceptions import (
    ProjectXAuthenticationError,
    ProjectXConnectionError,
    ProjectXError,
)
from project_x_py.models import Account, Instrument
from project_x_py.order_tracker import OrderChainBuilder, OrderTracker
from project_x_py.risk_manager import ManagedTrade, RiskConfig
from project_x_py.sessions import SessionConfig, SessionType
from project_x_py.trading_suite import InstrumentContext
from project_x_py.types.stats_types import TradingSuiteStats


class TestTradingSuiteInitialization:
    """Test suite for TradingSuite initialization and configuration."""

    @pytest.mark.asyncio
    async def test_create_single_instrument_with_defaults(self):
        """Test that TradingSuite creates correctly with minimal configuration."""
        # Define expected behavior: Suite should initialize with sensible defaults
        mock_client = self._create_mock_client()
        mock_realtime = self._create_mock_realtime_client()

        with self._patch_dependencies(mock_client, mock_realtime):
            suite = await TradingSuite.create("MNQ")

            # Expected: Suite should be properly initialized
            assert suite is not None
            assert suite.symbol == "MNQ"  # Should preserve original symbol
            assert suite.instrument_id is not None  # Should have full contract ID
            assert suite.is_connected is True
            assert suite._initialized is True
            assert suite._connected is True

            # Expected: Default configuration should be applied
            assert suite.config.timeframes == ["5min"]
            assert suite.config.features == []
            assert suite.config.initial_days == 5
            assert suite.config.auto_connect is True
            assert suite.config.timezone == "America/Chicago"

            # Expected: Core components should be initialized
            assert suite.data is not None
            assert suite.orders is not None
            assert suite.positions is not None
            assert suite.events is not None
            assert suite._stats_aggregator is not None

            # Expected: Optional components should not be initialized by default
            assert suite.orderbook is None
            assert suite.risk_manager is None

    @pytest.mark.asyncio
    async def test_create_with_custom_configuration(self):
        """Test that custom configuration is properly applied."""
        mock_client = self._create_mock_client()
        mock_realtime = self._create_mock_realtime_client()

        with self._patch_dependencies(mock_client, mock_realtime):
            suite = await TradingSuite.create(
                "ES",
                timeframes=["1min", "5min", "15min"],
                features=["orderbook", "risk_manager"],
                initial_days=30,
                auto_connect=False,
                timezone="America/New_York"
            )

            # Expected: Custom configuration should be applied
            assert suite.config.instrument == "ES"
            assert suite.config.timeframes == ["1min", "5min", "15min"]
            assert Features.ORDERBOOK in suite.config.features
            assert Features.RISK_MANAGER in suite.config.features
            assert suite.config.initial_days == 30
            assert suite.config.auto_connect is False
            assert suite.config.timezone == "America/New_York"

            # Expected: auto_connect=False should prevent initialization
            assert suite._initialized is False
            assert suite._connected is False

    @pytest.mark.asyncio
    async def test_create_multi_instrument_suite(self):
        """Test creation of multi-instrument trading suite."""
        mock_client = self._create_mock_client()
        mock_realtime = self._create_mock_realtime_client()

        with self._patch_dependencies(mock_client, mock_realtime):
            # Expected: Should support list of instruments
            suite = await TradingSuite.create(
                instruments=["MNQ", "MES", "MCL"],
                timeframes=["1min", "5min"]
            )

            # Expected: Suite should contain all instruments
            assert len(suite) == 3
            assert "MNQ" in suite
            assert "MES" in suite
            assert "MCL" in suite

            # Expected: Each instrument should have its own context
            mnq_context = suite["MNQ"]
            assert isinstance(mnq_context, InstrumentContext)
            assert mnq_context.symbol == "MNQ"
            assert mnq_context.data is not None
            assert mnq_context.orders is not None
            assert mnq_context.positions is not None

            # Expected: Container protocol should work
            assert list(suite.keys()) == ["MNQ", "MES", "MCL"]
            assert len(list(suite.values())) == 3
            assert len(list(suite.items())) == 3

    @pytest.mark.asyncio
    async def test_create_with_risk_manager_feature(self):
        """Test that risk manager is properly initialized when feature is enabled."""
        mock_client = self._create_mock_client()
        mock_realtime = self._create_mock_realtime_client()

        with self._patch_dependencies(mock_client, mock_realtime):
            suite = await TradingSuite.create(
                "MNQ",
                features=["risk_manager"]
            )

            # Expected: Risk manager should be initialized
            assert suite.risk_manager is not None

            # Expected: Risk manager should be properly configured
            risk_config = suite.config.get_risk_config()
            assert risk_config.max_risk_per_trade == Decimal("0.01")
            assert risk_config.max_daily_loss == Decimal("0.03")
            assert risk_config.max_positions == 3

            # Expected: Position manager should have risk manager reference
            assert suite.positions.risk_manager == suite.risk_manager

    @pytest.mark.asyncio
    async def test_create_with_orderbook_feature(self):
        """Test that orderbook is properly initialized when feature is enabled."""
        mock_client = self._create_mock_client()
        mock_realtime = self._create_mock_realtime_client()
        mock_orderbook = MagicMock()
        mock_orderbook.initialize = AsyncMock(return_value=True)
        mock_orderbook.cleanup = AsyncMock(return_value=None)

        with self._patch_dependencies(mock_client, mock_realtime):
            with patch("project_x_py.trading_suite.OrderBook", return_value=mock_orderbook):
                suite = await TradingSuite.create(
                    "MNQ",
                    features=["orderbook"]
                )

                # Expected: Orderbook should be initialized
                assert suite.orderbook is not None
                assert suite.orderbook == mock_orderbook

                # Expected: Orderbook should be initialized with correct parameters
                mock_orderbook.initialize.assert_called_once_with(
                    realtime_client=mock_realtime,
                    subscribe_to_depth=True,
                    subscribe_to_quotes=True
                )

    @pytest.mark.asyncio
    async def test_from_config_yaml(self, tmp_path):
        """Test creation from YAML configuration file."""
        # Create a test config file
        config_path = tmp_path / "test_config.yaml"
        config_data = {
            "instrument": "MNQ",
            "timeframes": ["1min", "5min", "15min"],
            "features": ["orderbook", "risk_manager"],
            "initial_days": 10,
            "timezone": "America/New_York"
        }
        with open(config_path, "w") as f:
            yaml.dump(config_data, f)

        mock_client = self._create_mock_client()
        mock_realtime = self._create_mock_realtime_client()

        with self._patch_dependencies(mock_client, mock_realtime):
            suite = await TradingSuite.from_config(str(config_path))

            # Expected: Configuration from file should be applied
            assert suite.config.instrument == "MNQ"
            assert suite.config.timeframes == ["1min", "5min", "15min"]
            assert Features.ORDERBOOK in suite.config.features
            assert Features.RISK_MANAGER in suite.config.features
            assert suite.config.initial_days == 10
            assert suite.config.timezone == "America/New_York"

    @pytest.mark.asyncio
    async def test_from_config_json(self, tmp_path):
        """Test creation from JSON configuration file."""
        import orjson

        config_path = tmp_path / "test_config.json"
        config_data = {
            "instrument": "ES",
            "timeframes": ["1min"],
            "features": ["orderbook"],
            "initial_days": 20
        }
        with open(config_path, "wb") as f:
            f.write(orjson.dumps(config_data))

        mock_client = self._create_mock_client()
        mock_realtime = self._create_mock_realtime_client()

        with self._patch_dependencies(mock_client, mock_realtime):
            suite = await TradingSuite.from_config(str(config_path))

            # Expected: Configuration from JSON should be applied
            assert suite.config.instrument == "ES"
            assert suite.config.timeframes == ["1min"]
            assert Features.ORDERBOOK in suite.config.features

    @pytest.mark.asyncio
    async def test_from_env(self):
        """Test creation using environment variables."""
        mock_client = self._create_mock_client()
        mock_realtime = self._create_mock_realtime_client()

        with self._patch_dependencies(mock_client, mock_realtime):
            suite = await TradingSuite.from_env(
                "MNQ",
                timeframes=["1min", "5min"]
            )

            # Expected: Should use environment variables for auth
            assert suite.config.instrument == "MNQ"
            assert suite.config.timeframes == ["1min", "5min"]

    @pytest.mark.asyncio
    async def test_manual_connect_when_auto_connect_disabled(self):
        """Test manual connection when auto_connect is disabled."""
        mock_client = self._create_mock_client()
        mock_realtime = self._create_mock_realtime_client()

        with self._patch_dependencies(mock_client, mock_realtime):
            suite = await TradingSuite.create(
                "MNQ",
                auto_connect=False
            )

            # Expected: Should not be connected initially
            assert suite._initialized is False
            assert suite._connected is False

            # Expected: Manual connect should initialize everything
            await suite.connect()
            assert suite._initialized is True
            assert suite._connected is True

    @pytest.mark.asyncio
    async def test_initialization_failure_cleanup(self):
        """Test that resources are cleaned up if initialization fails."""
        mock_client = self._create_mock_client()
        mock_realtime = self._create_mock_realtime_client()

        # Make initialization fail
        mock_realtime.connect = AsyncMock(side_effect=ConnectionError("Connection failed"))

        with self._patch_dependencies(mock_client, mock_realtime):
            with pytest.raises(ConnectionError):
                await TradingSuite.create("MNQ")

            # Expected: Cleanup should be called on failure
            mock_realtime.disconnect.assert_called()

    # Helper methods
    def _create_mock_client(self):
        """Create a properly configured mock client."""
        mock_client = MagicMock()
        mock_client.account_info = Account(
            id=12345,
            name="TEST_ACCOUNT",
            balance=100000.0,
            canTrade=True,
            isVisible=True,
            simulated=True
        )
        mock_client.session_token = "mock_jwt_token"
        mock_client.config = MagicMock()
        mock_client.authenticate = AsyncMock()
        mock_client.get_instrument = AsyncMock(
            return_value=Instrument(
                id="CON.F.US.MNQ.U25",
                name="MNQ",
                description="Micro E-mini NASDAQ-100",
                tickSize=0.25,
                tickValue=0.50,
                activeContract=True
            )
        )
        mock_client.search_all_orders = AsyncMock(return_value=[])
        mock_client.search_open_positions = AsyncMock(return_value=[])
        return mock_client

    def _create_mock_realtime_client(self):
        """Create a properly configured mock realtime client."""
        mock_realtime = MagicMock()
        mock_realtime.connect = AsyncMock(return_value=True)
        mock_realtime.disconnect = AsyncMock(return_value=None)
        mock_realtime.subscribe_user_updates = AsyncMock(return_value=True)
        mock_realtime.subscribe_market_data = AsyncMock(return_value=True)
        mock_realtime.is_connected = MagicMock(return_value=True)
        return mock_realtime

    def _patch_dependencies(self, mock_client, mock_realtime):
        """Create a context manager with all necessary patches."""
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_client
        mock_context.__aexit__.return_value = None

        mock_data_manager = MagicMock()
        mock_data_manager.initialize = AsyncMock(return_value=True)
        mock_data_manager.start_realtime_feed = AsyncMock(return_value=True)
        mock_data_manager.stop_realtime_feed = AsyncMock(return_value=None)
        mock_data_manager.cleanup = AsyncMock(return_value=None)

        mock_position_manager = MagicMock()
        mock_position_manager.initialize = AsyncMock(return_value=True)

        mock_order_manager = MagicMock()
        mock_order_manager.initialize = AsyncMock(return_value=True)

        from contextlib import ExitStack
        stack = ExitStack()
        stack.enter_context(patch("project_x_py.trading_suite.ProjectX.from_env", return_value=mock_context))
        stack.enter_context(patch("project_x_py.trading_suite.ProjectXRealtimeClient", return_value=mock_realtime))
        stack.enter_context(patch("project_x_py.trading_suite.RealtimeDataManager", return_value=mock_data_manager))
        stack.enter_context(patch("project_x_py.trading_suite.PositionManager", return_value=mock_position_manager))
        stack.enter_context(patch("project_x_py.trading_suite.OrderManager", return_value=mock_order_manager))

        return stack


class TestTradingSuiteEventHandling:
    """Test suite for TradingSuite event handling and callbacks."""

    @pytest.mark.asyncio
    async def test_event_registration_and_emission(self):
        """Test that events can be registered and properly emitted."""
        mock_client = self._create_mock_client()
        mock_realtime = self._create_mock_realtime_client()

        with self._patch_dependencies(mock_client, mock_realtime):
            suite = await TradingSuite.create("MNQ")

            # Expected: Event handlers should be registerable
            handler_called = False
            event_data = None

            async def test_handler(event):
                nonlocal handler_called, event_data
                handler_called = True
                event_data = event.data

            await suite.on(EventType.NEW_BAR, test_handler)

            # Expected: Emitting event should trigger handler
            test_event = Event(
                type=EventType.NEW_BAR,
                data={"timeframe": "1min", "close": 16500.0}
            )
            await suite.events.emit(EventType.NEW_BAR, test_event.data)

            # Give async handler time to execute
            await asyncio.sleep(0.01)

            assert handler_called is True
            assert event_data["timeframe"] == "1min"
            assert event_data["close"] == 16500.0

    @pytest.mark.asyncio
    async def test_once_event_handler(self):
        """Test that once() handlers are only called once."""
        mock_client = self._create_mock_client()
        mock_realtime = self._create_mock_realtime_client()

        with self._patch_dependencies(mock_client, mock_realtime):
            suite = await TradingSuite.create("MNQ")

            call_count = 0

            async def once_handler(event):
                nonlocal call_count
                call_count += 1

            await suite.once(EventType.ORDER_FILLED, once_handler)

            # Expected: Handler should only be called once
            await suite.events.emit(EventType.ORDER_FILLED, {"order_id": "123"})
            await suite.events.emit(EventType.ORDER_FILLED, {"order_id": "456"})

            await asyncio.sleep(0.01)
            assert call_count == 1

    @pytest.mark.asyncio
    async def test_off_removes_handler(self):
        """Test that off() properly removes event handlers."""
        mock_client = self._create_mock_client()
        mock_realtime = self._create_mock_realtime_client()

        with self._patch_dependencies(mock_client, mock_realtime):
            suite = await TradingSuite.create("MNQ")

            handler_called = False

            async def test_handler(event):
                nonlocal handler_called
                handler_called = True

            await suite.on(EventType.POSITION_OPENED, test_handler)
            await suite.off(EventType.POSITION_OPENED, test_handler)

            # Expected: Handler should not be called after removal
            await suite.events.emit(EventType.POSITION_OPENED, {"position_id": "123"})
            await asyncio.sleep(0.01)

            assert handler_called is False

    @pytest.mark.asyncio
    async def test_wait_for_event(self):
        """Test waiting for specific events."""
        mock_client = self._create_mock_client()
        mock_realtime = self._create_mock_realtime_client()

        with self._patch_dependencies(mock_client, mock_realtime):
            suite = await TradingSuite.create("MNQ")

            # Expected: wait_for should return when event is emitted
            async def emit_after_delay():
                await asyncio.sleep(0.05)
                await suite.events.emit(EventType.ORDER_FILLED, {"order_id": "123", "price": 16500.0})

            asyncio.create_task(emit_after_delay())

            result = await suite.wait_for(EventType.ORDER_FILLED, timeout=1.0)
            assert result.data["order_id"] == "123"
            assert result.data["price"] == 16500.0

    @pytest.mark.asyncio
    async def test_wait_for_event_timeout(self):
        """Test that wait_for raises TimeoutError when event doesn't occur."""
        mock_client = self._create_mock_client()
        mock_realtime = self._create_mock_realtime_client()

        with self._patch_dependencies(mock_client, mock_realtime):
            suite = await TradingSuite.create("MNQ")

            # Expected: Should raise TimeoutError
            with pytest.raises(asyncio.TimeoutError):
                await suite.wait_for(EventType.ORDER_FILLED, timeout=0.1)

    # Helper methods
    def _create_mock_client(self):
        """Create a properly configured mock client."""
        mock_client = MagicMock()
        mock_client.account_info = Account(
            id=12345,
            name="TEST_ACCOUNT",
            balance=100000.0,
            canTrade=True,
            isVisible=True,
            simulated=True
        )
        mock_client.session_token = "mock_jwt_token"
        mock_client.config = MagicMock()
        mock_client.authenticate = AsyncMock()
        mock_client.get_instrument = AsyncMock(
            return_value=Instrument(
                id="CON.F.US.MNQ.U25",
                name="MNQ",
                description="Micro E-mini NASDAQ-100",
                tickSize=0.25,
                tickValue=0.50,
                activeContract=True
            )
        )
        return mock_client

    def _create_mock_realtime_client(self):
        """Create a properly configured mock realtime client."""
        mock_realtime = MagicMock()
        mock_realtime.connect = AsyncMock(return_value=True)
        mock_realtime.disconnect = AsyncMock(return_value=None)
        mock_realtime.subscribe_user_updates = AsyncMock(return_value=True)
        mock_realtime.subscribe_market_data = AsyncMock(return_value=True)
        mock_realtime.is_connected = MagicMock(return_value=True)
        return mock_realtime

    def _patch_dependencies(self, mock_client, mock_realtime):
        """Create a context manager with all necessary patches."""
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_client
        mock_context.__aexit__.return_value = None

        mock_data_manager = MagicMock()
        mock_data_manager.initialize = AsyncMock(return_value=True)
        mock_data_manager.start_realtime_feed = AsyncMock(return_value=True)
        mock_data_manager.stop_realtime_feed = AsyncMock(return_value=None)
        mock_data_manager.cleanup = AsyncMock(return_value=None)

        mock_position_manager = MagicMock()
        mock_position_manager.initialize = AsyncMock(return_value=True)

        mock_order_manager = MagicMock()
        mock_order_manager.initialize = AsyncMock(return_value=True)

        from contextlib import ExitStack
        stack = ExitStack()
        stack.enter_context(patch("project_x_py.trading_suite.ProjectX.from_env", return_value=mock_context))
        stack.enter_context(patch("project_x_py.trading_suite.ProjectXRealtimeClient", return_value=mock_realtime))
        stack.enter_context(patch("project_x_py.trading_suite.RealtimeDataManager", return_value=mock_data_manager))
        stack.enter_context(patch("project_x_py.trading_suite.PositionManager", return_value=mock_position_manager))
        stack.enter_context(patch("project_x_py.trading_suite.OrderManager", return_value=mock_order_manager))

        return stack


class TestTradingSuiteContextManager:
    """Test suite for TradingSuite context manager functionality."""

    @pytest.mark.asyncio
    async def test_context_manager_initialization(self):
        """Test that context manager properly initializes and cleans up."""
        mock_client = self._create_mock_client()
        mock_realtime = self._create_mock_realtime_client()

        with self._patch_dependencies(mock_client, mock_realtime) as mocks:
            async with await TradingSuite.create("MNQ") as suite:
                # Expected: Suite should be initialized within context
                assert suite._initialized is True
                assert suite._connected is True
                assert suite.is_connected is True

            # Expected: Suite should be disconnected after context exit
            mock_realtime.disconnect.assert_called()

    @pytest.mark.asyncio
    async def test_context_manager_exception_handling(self):
        """Test that cleanup happens even when exception occurs in context."""
        mock_client = self._create_mock_client()
        mock_realtime = self._create_mock_realtime_client()
        mock_data_manager = MagicMock()
        mock_data_manager.cleanup = AsyncMock()

        with self._patch_dependencies(mock_client, mock_realtime):
            with pytest.raises(ValueError):
                async with await TradingSuite.create("MNQ") as suite:
                    suite._data = mock_data_manager
                    raise ValueError("Test exception")

            # Expected: Cleanup should still happen
            mock_realtime.disconnect.assert_called()

    @pytest.mark.asyncio
    async def test_multiple_context_manager_entries(self):
        """Test that suite can be used as context manager multiple times."""
        mock_client = self._create_mock_client()
        mock_realtime = self._create_mock_realtime_client()

        with self._patch_dependencies(mock_client, mock_realtime):
            suite = await TradingSuite.create("MNQ", auto_connect=False)

            # First context entry
            async with suite:
                assert suite._initialized is True

            # Expected: Should be able to enter context again
            async with suite:
                assert suite._initialized is True

    # Helper methods
    def _create_mock_client(self):
        """Create a properly configured mock client."""
        mock_client = MagicMock()
        mock_client.account_info = Account(
            id=12345,
            name="TEST_ACCOUNT",
            balance=100000.0,
            canTrade=True,
            isVisible=True,
            simulated=True
        )
        mock_client.session_token = "mock_jwt_token"
        mock_client.config = MagicMock()
        mock_client.authenticate = AsyncMock()
        mock_client.get_instrument = AsyncMock(
            return_value=Instrument(
                id="CON.F.US.MNQ.U25",
                name="MNQ",
                description="Micro E-mini NASDAQ-100",
                tickSize=0.25,
                tickValue=0.50,
                activeContract=True
            )
        )
        return mock_client

    def _create_mock_realtime_client(self):
        """Create a properly configured mock realtime client."""
        mock_realtime = MagicMock()
        mock_realtime.connect = AsyncMock(return_value=True)
        mock_realtime.disconnect = AsyncMock(return_value=None)
        mock_realtime.subscribe_user_updates = AsyncMock(return_value=True)
        mock_realtime.subscribe_market_data = AsyncMock(return_value=True)
        mock_realtime.is_connected = MagicMock(return_value=True)
        return mock_realtime

    def _patch_dependencies(self, mock_client, mock_realtime):
        """Create a context manager with all necessary patches."""
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_client
        mock_context.__aexit__.return_value = None

        mock_data_manager = MagicMock()
        mock_data_manager.initialize = AsyncMock(return_value=True)
        mock_data_manager.start_realtime_feed = AsyncMock(return_value=True)
        mock_data_manager.stop_realtime_feed = AsyncMock(return_value=None)
        mock_data_manager.cleanup = AsyncMock(return_value=None)

        mock_position_manager = MagicMock()
        mock_position_manager.initialize = AsyncMock(return_value=True)

        mock_order_manager = MagicMock()
        mock_order_manager.initialize = AsyncMock(return_value=True)

        from contextlib import ExitStack
        stack = ExitStack()
        stack.enter_context(patch("project_x_py.trading_suite.ProjectX.from_env", return_value=mock_context))
        stack.enter_context(patch("project_x_py.trading_suite.ProjectXRealtimeClient", return_value=mock_realtime))
        stack.enter_context(patch("project_x_py.trading_suite.RealtimeDataManager", return_value=mock_data_manager))
        stack.enter_context(patch("project_x_py.trading_suite.PositionManager", return_value=mock_position_manager))
        stack.enter_context(patch("project_x_py.trading_suite.OrderManager", return_value=mock_order_manager))

        return stack


class TestTradingSuiteOrderManagement:
    """Test suite for TradingSuite order management functionality."""

    @pytest.mark.asyncio
    async def test_track_order_creates_tracker(self):
        """Test that track_order creates a proper OrderTracker."""
        mock_client = self._create_mock_client()
        mock_realtime = self._create_mock_realtime_client()

        with self._patch_dependencies(mock_client, mock_realtime):
            suite = await TradingSuite.create("MNQ")

            # Expected: Should create OrderTracker
            tracker = suite.track_order()
            assert isinstance(tracker, OrderTracker)
            assert tracker.suite == suite

    @pytest.mark.asyncio
    async def test_order_chain_creates_builder(self):
        """Test that order_chain creates a proper OrderChainBuilder."""
        mock_client = self._create_mock_client()
        mock_realtime = self._create_mock_realtime_client()

        with self._patch_dependencies(mock_client, mock_realtime):
            suite = await TradingSuite.create("MNQ")

            # Expected: Should create OrderChainBuilder
            builder = suite.order_chain()
            assert isinstance(builder, OrderChainBuilder)
            assert builder.suite == suite

    @pytest.mark.asyncio
    async def test_managed_trade_requires_risk_manager(self):
        """Test that managed_trade raises error when risk manager not enabled."""
        mock_client = self._create_mock_client()
        mock_realtime = self._create_mock_realtime_client()

        with self._patch_dependencies(mock_client, mock_realtime):
            suite = await TradingSuite.create("MNQ")  # No risk_manager feature

            # Expected: Should raise ValueError
            with pytest.raises(ValueError, match="Risk manager not enabled"):
                suite.managed_trade()

    @pytest.mark.asyncio
    async def test_managed_trade_creates_context(self):
        """Test that managed_trade creates proper ManagedTrade context."""
        mock_client = self._create_mock_client()
        mock_realtime = self._create_mock_realtime_client()

        with self._patch_dependencies(mock_client, mock_realtime):
            suite = await TradingSuite.create("MNQ", features=["risk_manager"])

            # Expected: Should create ManagedTrade
            managed = suite.managed_trade(max_risk_percent=0.02)
            assert isinstance(managed, ManagedTrade)
            assert managed.risk_manager == suite.risk_manager
            assert managed.order_manager == suite.orders
            assert managed.position_manager == suite.positions

    # Helper methods remain the same as previous test classes
    def _create_mock_client(self):
        """Create a properly configured mock client."""
        mock_client = MagicMock()
        mock_client.account_info = Account(
            id=12345,
            name="TEST_ACCOUNT",
            balance=100000.0,
            canTrade=True,
            isVisible=True,
            simulated=True
        )
        mock_client.session_token = "mock_jwt_token"
        mock_client.config = MagicMock()
        mock_client.authenticate = AsyncMock()
        mock_client.get_instrument = AsyncMock(
            return_value=Instrument(
                id="CON.F.US.MNQ.U25",
                name="MNQ",
                description="Micro E-mini NASDAQ-100",
                tickSize=0.25,
                tickValue=0.50,
                activeContract=True
            )
        )
        return mock_client

    def _create_mock_realtime_client(self):
        """Create a properly configured mock realtime client."""
        mock_realtime = MagicMock()
        mock_realtime.connect = AsyncMock(return_value=True)
        mock_realtime.disconnect = AsyncMock(return_value=None)
        mock_realtime.subscribe_user_updates = AsyncMock(return_value=True)
        mock_realtime.subscribe_market_data = AsyncMock(return_value=True)
        mock_realtime.is_connected = MagicMock(return_value=True)
        return mock_realtime

    def _patch_dependencies(self, mock_client, mock_realtime):
        """Create a context manager with all necessary patches."""
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_client
        mock_context.__aexit__.return_value = None

        mock_data_manager = MagicMock()
        mock_data_manager.initialize = AsyncMock(return_value=True)
        mock_data_manager.start_realtime_feed = AsyncMock(return_value=True)
        mock_data_manager.stop_realtime_feed = AsyncMock(return_value=None)
        mock_data_manager.cleanup = AsyncMock(return_value=None)

        mock_position_manager = MagicMock()
        mock_position_manager.initialize = AsyncMock(return_value=True)
        mock_position_manager.risk_manager = None

        mock_order_manager = MagicMock()
        mock_order_manager.initialize = AsyncMock(return_value=True)

        mock_risk_manager = MagicMock()

        from contextlib import ExitStack
        stack = ExitStack()
        stack.enter_context(patch("project_x_py.trading_suite.ProjectX.from_env", return_value=mock_context))
        stack.enter_context(patch("project_x_py.trading_suite.ProjectXRealtimeClient", return_value=mock_realtime))
        stack.enter_context(patch("project_x_py.trading_suite.RealtimeDataManager", return_value=mock_data_manager))
        stack.enter_context(patch("project_x_py.trading_suite.PositionManager", return_value=mock_position_manager))
        stack.enter_context(patch("project_x_py.trading_suite.OrderManager", return_value=mock_order_manager))
        stack.enter_context(patch("project_x_py.trading_suite.RiskManager", return_value=mock_risk_manager))

        return stack


class TestTradingSuiteStatistics:
    """Test suite for TradingSuite statistics functionality."""

    @pytest.mark.asyncio
    async def test_get_stats_returns_structured_data(self):
        """Test that get_stats returns properly structured statistics."""
        mock_client = self._create_mock_client()
        mock_realtime = self._create_mock_realtime_client()

        with self._patch_dependencies(mock_client, mock_realtime):
            suite = await TradingSuite.create("MNQ")

            # Expected: get_stats should return TradingSuiteStats
            stats = await suite.get_stats()
            assert isinstance(stats, dict)
            assert "connected" in stats
            assert "instrument" in stats
            assert "components" in stats

    @pytest.mark.asyncio
    async def test_get_stats_sync_deprecated(self):
        """Test that get_stats_sync is deprecated but still works."""
        mock_client = self._create_mock_client()
        mock_realtime = self._create_mock_realtime_client()

        with self._patch_dependencies(mock_client, mock_realtime):
            suite = await TradingSuite.create("MNQ")

            # Expected: Should issue deprecation warning
            with pytest.warns(DeprecationWarning):
                stats = suite.get_stats_sync()
                assert isinstance(stats, dict)

    # Helper methods remain the same
    def _create_mock_client(self):
        """Create a properly configured mock client."""
        mock_client = MagicMock()
        mock_client.account_info = Account(
            id=12345,
            name="TEST_ACCOUNT",
            balance=100000.0,
            canTrade=True,
            isVisible=True,
            simulated=True
        )
        mock_client.session_token = "mock_jwt_token"
        mock_client.config = MagicMock()
        mock_client.authenticate = AsyncMock()
        mock_client.get_instrument = AsyncMock(
            return_value=Instrument(
                id="CON.F.US.MNQ.U25",
                name="MNQ",
                description="Micro E-mini NASDAQ-100",
                tickSize=0.25,
                tickValue=0.50,
                activeContract=True
            )
        )
        return mock_client

    def _create_mock_realtime_client(self):
        """Create a properly configured mock realtime client."""
        mock_realtime = MagicMock()
        mock_realtime.connect = AsyncMock(return_value=True)
        mock_realtime.disconnect = AsyncMock(return_value=None)
        mock_realtime.subscribe_user_updates = AsyncMock(return_value=True)
        mock_realtime.subscribe_market_data = AsyncMock(return_value=True)
        mock_realtime.is_connected = MagicMock(return_value=True)
        return mock_realtime

    def _patch_dependencies(self, mock_client, mock_realtime):
        """Create a context manager with all necessary patches."""
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_client
        mock_context.__aexit__.return_value = None

        mock_data_manager = MagicMock()
        mock_data_manager.initialize = AsyncMock(return_value=True)
        mock_data_manager.start_realtime_feed = AsyncMock(return_value=True)
        mock_data_manager.stop_realtime_feed = AsyncMock(return_value=None)
        mock_data_manager.cleanup = AsyncMock(return_value=None)

        mock_position_manager = MagicMock()
        mock_position_manager.initialize = AsyncMock(return_value=True)

        mock_order_manager = MagicMock()
        mock_order_manager.initialize = AsyncMock(return_value=True)

        from contextlib import ExitStack
        stack = ExitStack()
        stack.enter_context(patch("project_x_py.trading_suite.ProjectX.from_env", return_value=mock_context))
        stack.enter_context(patch("project_x_py.trading_suite.ProjectXRealtimeClient", return_value=mock_realtime))
        stack.enter_context(patch("project_x_py.trading_suite.RealtimeDataManager", return_value=mock_data_manager))
        stack.enter_context(patch("project_x_py.trading_suite.PositionManager", return_value=mock_position_manager))
        stack.enter_context(patch("project_x_py.trading_suite.OrderManager", return_value=mock_order_manager))

        return stack


class TestTradingSuiteBackwardCompatibility:
    """Test suite for TradingSuite backward compatibility features."""

    @pytest.mark.asyncio
    async def test_single_instrument_backward_compatibility(self):
        """Test that single-instrument mode maintains backward compatibility."""
        mock_client = self._create_mock_client()
        mock_realtime = self._create_mock_realtime_client()
        mock_data_manager = MagicMock()

        with self._patch_dependencies(mock_client, mock_realtime) as patches:
            # Use old API with single instrument parameter
            suite = await TradingSuite.create(instrument="MNQ")
            suite._data = mock_data_manager

            # Expected: Should work with deprecation warning
            with pytest.warns(DeprecationWarning):
                data = suite.data  # Direct access should work with warning
                assert data == mock_data_manager

    @pytest.mark.asyncio
    async def test_multi_instrument_direct_access_error(self):
        """Test that multi-instrument mode gives helpful error for direct access."""
        mock_client = self._create_mock_client()
        mock_realtime = self._create_mock_realtime_client()

        with self._patch_dependencies(mock_client, mock_realtime):
            suite = await TradingSuite.create(instruments=["MNQ", "MES"])

            # Expected: Should raise AttributeError with helpful message
            with pytest.raises(AttributeError, match="For multi-instrument suites"):
                _ = suite.data

    @pytest.mark.asyncio
    async def test_session_type_methods(self):
        """Test session-aware methods for RTH/ETH data filtering."""
        mock_client = self._create_mock_client()
        mock_realtime = self._create_mock_realtime_client()

        # Create data manager mock with session methods
        mock_data_manager = MagicMock()
        mock_data_manager.initialize = AsyncMock()
        mock_data_manager.start_realtime_feed = AsyncMock()
        mock_data_manager.stop_realtime_feed = AsyncMock()
        mock_data_manager.cleanup = AsyncMock()
        mock_data_manager.set_session_type = AsyncMock()
        mock_data_manager.get_session_data = AsyncMock(return_value=MagicMock())
        mock_data_manager.get_session_statistics = AsyncMock(return_value={"rth_volume": 1000})

        # Create context manager for client
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_client
        mock_context.__aexit__.return_value = None

        # Set up all patches including our data manager with session methods
        with patch("project_x_py.trading_suite.ProjectX.from_env", return_value=mock_context):
            with patch("project_x_py.trading_suite.ProjectXRealtimeClient", return_value=mock_realtime):
                with patch("project_x_py.trading_suite.RealtimeDataManager", return_value=mock_data_manager):
                    # Create proper mocks for managers
                    mock_order_manager = MagicMock()
                    mock_order_manager.initialize = AsyncMock()
                    mock_position_manager = MagicMock()
                    mock_position_manager.initialize = AsyncMock()
                    mock_position_manager.refresh_positions = AsyncMock()

                    with patch("project_x_py.trading_suite.OrderManager", return_value=mock_order_manager):
                        with patch("project_x_py.trading_suite.PositionManager", return_value=mock_position_manager):
                            suite = await TradingSuite.create("MNQ")

                            # Expected: Session methods should work
                            await suite.set_session_type(SessionType.RTH)
                            mock_data_manager.set_session_type.assert_called_with(SessionType.RTH)

                            data = await suite.get_session_data("1min", SessionType.RTH)
                            mock_data_manager.get_session_data.assert_called_with("1min", SessionType.RTH)

                            stats = await suite.get_session_statistics("1min")
                            assert stats["rth_volume"] == 1000

    # Helper methods remain the same
    def _create_mock_client(self):
        """Create a properly configured mock client."""
        mock_client = MagicMock()
        mock_client.account_info = Account(
            id=12345,
            name="TEST_ACCOUNT",
            balance=100000.0,
            canTrade=True,
            isVisible=True,
            simulated=True
        )
        mock_client.session_token = "mock_jwt_token"
        mock_client.config = MagicMock()
        mock_client.authenticate = AsyncMock()
        mock_client.get_instrument = AsyncMock(
            return_value=Instrument(
                id="CON.F.US.MNQ.U25",
                name="MNQ",
                description="Micro E-mini NASDAQ-100",
                tickSize=0.25,
                tickValue=0.50,
                activeContract=True
            )
        )
        return mock_client

    def _create_mock_realtime_client(self):
        """Create a properly configured mock realtime client."""
        mock_realtime = MagicMock()
        mock_realtime.connect = AsyncMock(return_value=True)
        mock_realtime.disconnect = AsyncMock(return_value=None)
        mock_realtime.subscribe_user_updates = AsyncMock(return_value=True)
        mock_realtime.subscribe_market_data = AsyncMock(return_value=True)
        mock_realtime.is_connected = MagicMock(return_value=True)
        return mock_realtime

    def _patch_dependencies(self, mock_client, mock_realtime):
        """Create a context manager with all necessary patches."""
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_client
        mock_context.__aexit__.return_value = None

        mock_data_manager = MagicMock()
        mock_data_manager.initialize = AsyncMock(return_value=True)
        mock_data_manager.start_realtime_feed = AsyncMock(return_value=True)
        mock_data_manager.stop_realtime_feed = AsyncMock(return_value=None)
        mock_data_manager.cleanup = AsyncMock(return_value=None)

        mock_position_manager = MagicMock()
        mock_position_manager.initialize = AsyncMock(return_value=True)

        mock_order_manager = MagicMock()
        mock_order_manager.initialize = AsyncMock(return_value=True)

        from contextlib import ExitStack
        stack = ExitStack()
        stack.enter_context(patch("project_x_py.trading_suite.ProjectX.from_env", return_value=mock_context))
        stack.enter_context(patch("project_x_py.trading_suite.ProjectXRealtimeClient", return_value=mock_realtime))
        stack.enter_context(patch("project_x_py.trading_suite.RealtimeDataManager", return_value=mock_data_manager))
        stack.enter_context(patch("project_x_py.trading_suite.PositionManager", return_value=mock_position_manager))
        stack.enter_context(patch("project_x_py.trading_suite.OrderManager", return_value=mock_order_manager))

        return stack


class TestTradingSuiteErrorHandling:
    """Test suite for TradingSuite error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_authentication_failure(self):
        """Test that authentication failures are handled properly."""
        mock_client = MagicMock()
        mock_client.authenticate = AsyncMock(side_effect=ProjectXAuthenticationError("Invalid credentials"))

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_client
        mock_context.__aexit__.return_value = None

        with patch("project_x_py.trading_suite.ProjectX.from_env", return_value=mock_context):
            # Expected: Should raise ProjectXAuthenticationError
            with pytest.raises(ProjectXAuthenticationError, match="Invalid credentials"):
                await TradingSuite.create("MNQ")

    @pytest.mark.asyncio
    async def test_missing_account_info(self):
        """Test handling when account info is missing."""
        mock_client = MagicMock()
        mock_client.account_info = None  # Missing account info
        mock_client.authenticate = AsyncMock()

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_client
        mock_context.__aexit__.return_value = None

        with patch("project_x_py.trading_suite.ProjectX.from_env", return_value=mock_context):
            # Expected: Should raise ValueError
            with pytest.raises(ValueError, match="Failed to authenticate"):
                await TradingSuite.create("MNQ")

    @pytest.mark.asyncio
    async def test_invalid_config_file(self):
        """Test handling of invalid configuration files."""
        # Test non-existent file
        with pytest.raises(FileNotFoundError):
            await TradingSuite.from_config("non_existent_file.yaml")

        # Test unsupported format
        with pytest.raises(ValueError, match="Unsupported config format"):
            await TradingSuite.from_config("test.txt")

    @pytest.mark.asyncio
    async def test_no_instruments_provided(self):
        """Test error when no instruments are provided."""
        mock_client = self._create_mock_client()
        mock_realtime = self._create_mock_realtime_client()

        with self._patch_dependencies(mock_client, mock_realtime):
            # Expected: Should raise ValueError
            with pytest.raises(ValueError, match="Must provide either"):
                await TradingSuite.create()

    @pytest.mark.asyncio
    async def test_realtime_connection_failure(self):
        """Test handling of realtime connection failures."""
        mock_client = self._create_mock_client()
        mock_realtime = MagicMock()
        mock_realtime.connect = AsyncMock(side_effect=ProjectXConnectionError("WebSocket connection failed"))
        mock_realtime.disconnect = AsyncMock()

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_client
        mock_context.__aexit__.return_value = None

        with patch("project_x_py.trading_suite.ProjectX.from_env", return_value=mock_context):
            with patch("project_x_py.trading_suite.ProjectXRealtimeClient", return_value=mock_realtime):
                # Expected: Should raise ProjectXConnectionError and cleanup
                with pytest.raises(ProjectXConnectionError, match="WebSocket connection failed"):
                    await TradingSuite.create("MNQ")

                # Expected: Disconnect should be called for cleanup
                mock_realtime.disconnect.assert_called()

    @pytest.mark.asyncio
    async def test_partial_initialization_cleanup(self):
        """Test that partial initialization is properly cleaned up on failure."""
        mock_client = self._create_mock_client()
        mock_realtime = self._create_mock_realtime_client()

        # Make one instrument fail
        mock_client.get_instrument = AsyncMock(
            side_effect=[
                Instrument(id="MNQ_ID", name="MNQ", description="Micro NASDAQ", tickSize=0.25, tickValue=0.50, activeContract=True),
                Exception("Failed to get MES instrument")
            ]
        )

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_client
        mock_context.__aexit__.return_value = None

        with patch("project_x_py.trading_suite.ProjectX.from_env", return_value=mock_context):
            with patch("project_x_py.trading_suite.ProjectXRealtimeClient", return_value=mock_realtime):
                # Expected: Should raise exception and cleanup partial contexts
                with pytest.raises(Exception, match="Failed to get MES instrument"):
                    await TradingSuite.create(instruments=["MNQ", "MES"])

    # Helper methods
    def _create_mock_client(self):
        """Create a properly configured mock client."""
        mock_client = MagicMock()
        mock_client.account_info = Account(
            id=12345,
            name="TEST_ACCOUNT",
            balance=100000.0,
            canTrade=True,
            isVisible=True,
            simulated=True
        )
        mock_client.session_token = "mock_jwt_token"
        mock_client.config = MagicMock()
        mock_client.authenticate = AsyncMock()
        mock_client.get_instrument = AsyncMock(
            return_value=Instrument(
                id="CON.F.US.MNQ.U25",
                name="MNQ",
                description="Micro E-mini NASDAQ-100",
                tickSize=0.25,
                tickValue=0.50,
                activeContract=True
            )
        )
        return mock_client

    def _create_mock_realtime_client(self):
        """Create a properly configured mock realtime client."""
        mock_realtime = MagicMock()
        mock_realtime.connect = AsyncMock(return_value=True)
        mock_realtime.disconnect = AsyncMock(return_value=None)
        mock_realtime.subscribe_user_updates = AsyncMock(return_value=True)
        mock_realtime.subscribe_market_data = AsyncMock(return_value=True)
        mock_realtime.is_connected = MagicMock(return_value=True)
        return mock_realtime

    def _patch_dependencies(self, mock_client, mock_realtime):
        """Create a context manager with all necessary patches."""
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_client
        mock_context.__aexit__.return_value = None

        from contextlib import ExitStack
        stack = ExitStack()
        stack.enter_context(patch("project_x_py.trading_suite.ProjectX.from_env", return_value=mock_context))
        stack.enter_context(patch("project_x_py.trading_suite.ProjectXRealtimeClient", return_value=mock_realtime))

        return stack


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
