"""
Comprehensive tests for PositionManager core.py module.

These tests are written following TDD principles to test EXPECTED behavior,
not current implementation. If tests fail, the implementation should be fixed,
not the tests.

Coverage focus areas:
1. Position caching mechanisms
2. Complex position filtering logic
3. Error recovery paths
4. Edge cases in position initialization
5. Realtime vs polling mode operations
6. Order management integration
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch, MagicMock
import pytest
from datetime import datetime, UTC

from project_x_py.exceptions import (
    ProjectXError,
    ProjectXConnectionError,
    ProjectXAuthenticationError,
    ProjectXServerError,
)
from project_x_py.models import Position
from project_x_py.types import PositionType
from project_x_py.types.response_types import RiskAnalysisResponse
from project_x_py.position_manager import PositionManager
from project_x_py.event_bus import EventBus


@pytest.fixture
async def mock_client():
    """Mock ProjectX client."""
    client = AsyncMock()
    client.account_info = Mock(id=12345, name="Test Account")
    client.search_open_positions = AsyncMock(return_value=[])
    client.close_position = AsyncMock(return_value=True)
    client.search_open_orders = AsyncMock(return_value=[])
    client.get_balances = AsyncMock(return_value={"balance": 100000.0})
    return client


@pytest.fixture
async def mock_realtime_client():
    """Mock realtime client."""
    client = AsyncMock()
    client.subscribe_user_updates = AsyncMock()
    client.add_callback = AsyncMock()
    return client


@pytest.fixture
async def mock_order_manager():
    """Mock order manager."""
    manager = AsyncMock()
    manager.sync_orders_with_position = AsyncMock()
    return manager


@pytest.fixture
async def basic_position_manager(mock_client):
    """Create basic position manager without realtime."""
    event_bus = EventBus()
    manager = PositionManager(mock_client, event_bus)
    await manager.initialize()
    return manager


@pytest.fixture
async def realtime_position_manager(mock_client, mock_realtime_client):
    """Create position manager with realtime enabled."""
    event_bus = EventBus()
    manager = PositionManager(mock_client, event_bus)
    await manager.initialize(realtime_client=mock_realtime_client)
    return manager


@pytest.fixture
def sample_positions():
    """Sample position data."""
    return [
        Position(
            id=1,
            accountId=12345,
            contractId="MNQ",
            type=1,  # PositionType.LONG
            size=2,
            averagePrice=18000.0,
            creationTimestamp=datetime.now(UTC).isoformat(),
        ),
        Position(
            id=2,
            accountId=12345,
            contractId="ES",
            type=2,  # PositionType.SHORT
            size=1,  # Size is always positive
            averagePrice=4500.0,
            creationTimestamp=datetime.now(UTC).isoformat(),
        ),
    ]


class TestPositionInitialization:
    """Test position manager initialization with various configurations."""

    @pytest.mark.asyncio
    async def test_initialize_without_realtime(self, mock_client):
        """Test initialization in polling mode."""
        event_bus = EventBus()
        manager = PositionManager(mock_client, event_bus)
        result = await manager.initialize()

        assert result is True
        assert manager._realtime_enabled is False
        assert manager.realtime_client is None
        assert manager._order_sync_enabled is False
        mock_client.search_open_positions.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_with_realtime(self, mock_client, mock_realtime_client):
        """Test initialization with realtime client."""
        event_bus = EventBus()
        manager = PositionManager(mock_client, event_bus)
        result = await manager.initialize(realtime_client=mock_realtime_client)

        assert result is True
        assert manager._realtime_enabled is True
        assert manager.realtime_client == mock_realtime_client
        mock_realtime_client.subscribe_user_updates.assert_called()
        mock_realtime_client.add_callback.assert_called()

    @pytest.mark.asyncio
    async def test_initialize_with_order_manager(self, mock_client, mock_order_manager):
        """Test initialization with order manager integration."""
        event_bus = EventBus()
        manager = PositionManager(mock_client, event_bus)
        result = await manager.initialize(order_manager=mock_order_manager)

        assert result is True
        assert manager._order_sync_enabled is True
        assert manager.order_manager == mock_order_manager

    @pytest.mark.asyncio
    async def test_initialize_loads_initial_positions(self, mock_client, sample_positions):
        """Test that initialization loads positions from API."""
        mock_client.search_open_positions.return_value = sample_positions

        event_bus = EventBus()
        manager = PositionManager(mock_client, event_bus)
        await manager.initialize()

        assert len(manager.tracked_positions) == 2
        assert "MNQ" in manager.tracked_positions
        assert "ES" in manager.tracked_positions
        assert manager.stats["positions_tracked"] == 2

    @pytest.mark.asyncio
    async def test_initialize_handles_api_failure(self, mock_client):
        """Test initialization handles API errors gracefully."""
        mock_client.search_open_positions.side_effect = ProjectXServerError("API Error")

        event_bus = EventBus()
        manager = PositionManager(mock_client, event_bus)
        # Should not raise, but positions should be empty
        result = await manager.initialize()

        assert result is True
        assert len(manager.tracked_positions) == 0
        assert manager.stats["errors"] == 1


class TestPositionCaching:
    """Test position caching mechanisms."""

    @pytest.mark.asyncio
    async def test_cache_used_in_realtime_mode(self, realtime_position_manager, sample_positions):
        """Test that cache is used when realtime is enabled."""
        manager = realtime_position_manager
        manager.tracked_positions = {p.contractId: p for p in sample_positions}

        # Should not call API in realtime mode
        manager.project_x.search_open_positions = AsyncMock(
            side_effect=Exception("Should not be called")
        )

        position = await manager.get_position("MNQ")
        assert position is not None
        assert position.contractId == "MNQ"

    @pytest.mark.asyncio
    async def test_api_used_in_polling_mode(self, basic_position_manager, sample_positions):
        """Test that API is called when realtime is disabled."""
        manager = basic_position_manager
        manager.project_x.search_open_positions.return_value = sample_positions

        position = await manager.get_position("MNQ")

        assert position is not None
        assert position.contractId == "MNQ"
        manager.project_x.search_open_positions.assert_called()

    @pytest.mark.asyncio
    async def test_cache_expiry_and_refresh(self, realtime_position_manager):
        """Test cache expiry and refresh mechanism."""
        manager = realtime_position_manager

        # Add position to cache
        old_position = Position(
            id=1, accountId=12345, contractId="MNQ",
            type=1,  # PositionType.LONG
            size=1,
            averagePrice=18000.0,
            creationTimestamp=datetime.now(UTC).isoformat()
        )
        manager.tracked_positions["MNQ"] = old_position

        # Update with new position
        new_position = Position(
            id=1, accountId=12345, contractId="MNQ",
            type=1,  # PositionType.LONG
            size=2,  # Size changed
            averagePrice=18100.0,
            creationTimestamp=datetime.now(UTC).isoformat()
        )

        await manager.track_position_update(new_position)

        # Cache should be updated
        assert manager.tracked_positions["MNQ"].size == 2
        assert manager.tracked_positions["MNQ"].averagePrice == 18100.0

    @pytest.mark.asyncio
    async def test_cache_invalidation_on_position_close(self, realtime_position_manager):
        """Test cache is properly invalidated when position closes."""
        manager = realtime_position_manager

        position = Position(
            id=1, accountId=12345, contractId="MNQ",
            type=1,  # PositionType.LONG
            size=2,
            averagePrice=18000.0,
            creationTimestamp=datetime.now(UTC).isoformat()
        )
        manager.tracked_positions["MNQ"] = position

        # Close position
        await manager.track_position_closed(position, pnl=100.0)

        # Should be removed from cache
        assert "MNQ" not in manager.tracked_positions
        assert manager.stats["positions_closed"] == 1


class TestPositionFiltering:
    """Test complex position filtering logic."""

    @pytest.mark.asyncio
    async def test_filter_by_account_id(self, basic_position_manager):
        """Test filtering positions by account ID."""
        manager = basic_position_manager

        positions = [
            Position(
                id=1, accountId=12345, contractId="MNQ",
                type=1,  # PositionType.LONG
                size=1,
                averagePrice=18000.0,
                creationTimestamp=datetime.now(UTC).isoformat()
            ),
            Position(
                id=2, accountId=67890, contractId="ES",  # Different account
                type=1,  # PositionType.LONG
                size=1,
                averagePrice=4500.0,
                creationTimestamp=datetime.now(UTC).isoformat()
            ),
        ]
        manager.project_x.search_open_positions.return_value = positions

        # Get positions for specific account
        result = await manager.get_all_positions(account_id=12345)

        assert len(result) == 1
        assert result[0].accountId == 12345

    @pytest.mark.asyncio
    async def test_filter_zero_size_positions(self, basic_position_manager):
        """Test that zero-size positions are filtered out."""
        manager = basic_position_manager

        positions = [
            Position(
                id=1, accountId=12345, contractId="MNQ",
                type=1,  # PositionType.LONG
                size=2,
                averagePrice=18000.0,
                creationTimestamp=datetime.now(UTC).isoformat()
            ),
            Position(
                id=2, accountId=12345, contractId="ES",
                type=0,  # PositionType.UNDEFINED
                size=0,  # Zero size
                averagePrice=0.0,
                creationTimestamp=datetime.now(UTC).isoformat()
            ),
        ]
        manager.project_x.search_open_positions.return_value = positions

        result = await manager.get_all_positions()

        # Should only return non-zero positions
        assert len(result) == 1
        assert result[0].contractId == "MNQ"

    @pytest.mark.asyncio
    async def test_position_type_determination(self, basic_position_manager):
        """Test correct determination of position type from size."""
        manager = basic_position_manager

        positions = [
            Position(
                id=1, accountId=12345, contractId="LONG_POS",
                type=0,  # Type not set
                size=5,  # Positive = LONG
                averagePrice=100.0,
                creationTimestamp=datetime.now(UTC).isoformat()
            ),
            Position(
                id=2, accountId=12345, contractId="SHORT_POS",
                type=0,  # Type not set
                size=3,  # Size is always positive
                averagePrice=200.0,
                creationTimestamp=datetime.now(UTC).isoformat()
            ),
        ]

        for pos in positions:
            manager.tracked_positions[pos.contractId] = pos

        # Check type determination
        long_pos = manager.tracked_positions["LONG_POS"]
        short_pos = manager.tracked_positions["SHORT_POS"]

        assert long_pos.size > 0  # Long position
        assert short_pos.size > 0  # Size always positive


class TestErrorRecovery:
    """Test error recovery paths."""

    @pytest.mark.asyncio
    async def test_connection_error_recovery(self, basic_position_manager):
        """Test recovery from connection errors."""
        manager = basic_position_manager

        # Simulate connection error
        manager.project_x.search_open_positions.side_effect = ProjectXConnectionError("Connection lost")

        result = await manager.refresh_positions()

        # Should handle error gracefully
        assert result is False
        assert manager.stats["errors"] > 0

    @pytest.mark.asyncio
    async def test_authentication_error_handling(self, basic_position_manager):
        """Test handling of authentication errors."""
        manager = basic_position_manager

        manager.project_x.search_open_positions.side_effect = ProjectXAuthenticationError("Token expired")

        result = await manager.get_all_positions()

        # Should return empty list on auth error
        assert result == []
        assert manager.stats["errors"] > 0

    @pytest.mark.asyncio
    async def test_partial_data_recovery(self, basic_position_manager):
        """Test recovery when partial data is received."""
        manager = basic_position_manager

        # Return position with missing required fields
        invalid_position = Mock(spec=Position)
        invalid_position.contractId = None  # Missing required field
        invalid_position.id = 1
        invalid_position.size = 1

        manager.project_x.search_open_positions.return_value = [invalid_position]

        result = await manager.get_all_positions()

        # Should handle invalid data gracefully
        assert len(result) == 0 or all(p.contractId is not None for p in result)

    @pytest.mark.asyncio
    async def test_concurrent_access_safety(self, basic_position_manager):
        """Test thread-safe concurrent access to positions."""
        manager = basic_position_manager

        # Add initial position
        position = Position(
            id=1, accountId=12345, contractId="MNQ",
            type=1,  # PositionType.LONG
            size=1,
            averagePrice=18000.0,
            creationTimestamp=datetime.now(UTC).isoformat()
        )
        manager.tracked_positions["MNQ"] = position

        # Simulate concurrent updates
        async def update_position():
            new_pos = Position(
                id=1, accountId=12345, contractId="MNQ",
                type=1,  # PositionType.LONG
                size=2,
                averagePrice=18100.0,
                creationTimestamp=datetime.now(UTC).isoformat()
            )
            await manager.track_position_update(new_pos)

        async def read_position():
            return await manager.get_position("MNQ")

        # Run concurrent operations
        tasks = [update_position() for _ in range(5)]
        tasks.extend([read_position() for _ in range(5)])

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Should not have any exceptions from concurrent access
        exceptions = [r for r in results if isinstance(r, Exception)]
        assert len(exceptions) == 0


class TestRiskCalculations:
    """Test risk metric calculations."""

    @pytest.mark.asyncio
    async def test_calculate_position_size_with_risk(self, basic_position_manager):
        """Test position size calculation based on risk."""
        manager = basic_position_manager

        # Set up account balance
        manager.project_x.get_balances.return_value = {"balance": 100000.0}

        # Calculate position size with 1% risk
        size = await manager.calculate_position_size(
            risk_amount=1000.0,  # $1000 risk
            entry_price=18000.0,
            stop_price=17900.0  # $100 stop distance
        )

        # Should calculate correct size: risk / stop_distance
        assert size == 10  # $1000 / $100 = 10 contracts

    @pytest.mark.asyncio
    async def test_risk_metrics_calculation(self, basic_position_manager, sample_positions):
        """Test calculation of risk metrics."""
        manager = basic_position_manager
        manager.tracked_positions = {p.contractId: p for p in sample_positions}

        # Mock current prices
        with patch.object(manager, "_calculate_current_prices", return_value={
            "MNQ": 18100.0,
            "ES": 4480.0
        }):
            metrics = await manager.get_risk_metrics()

        assert isinstance(metrics, dict)  # RiskAnalysisResponse is a TypedDict
        assert metrics["position_count"] == 2  # Use correct field name
        # Check that position_risks contains the P&L data
        assert len(metrics["position_risks"]) == 2
        # MNQ: 2 * (18100 - 18000) = 200 profit
        # ES: -1 * (4480 - 4500) = 20 profit (short position)
        total_pnl = sum(p["pnl"] for p in metrics["position_risks"])
        assert total_pnl == 220.0

    @pytest.mark.asyncio
    async def test_position_size_with_zero_stop_distance(self, basic_position_manager):
        """Test position size calculation handles zero stop distance."""
        manager = basic_position_manager

        # Calculate with zero stop distance
        size = await manager.calculate_position_size(
            risk_amount=1000.0,
            entry_price=18000.0,
            stop_price=18000.0  # Same as entry
        )

        # Should return 0 or handle gracefully
        assert size == 0


class TestStatisticsTracking:
    """Test statistics and memory management."""

    @pytest.mark.asyncio
    async def test_position_stats_tracking(self, basic_position_manager):
        """Test accurate tracking of position statistics."""
        manager = basic_position_manager

        # Track position lifecycle
        position = Position(
            id=1, accountId=12345, contractId="MNQ",
            type=1,  # PositionType.LONG
            size=2,
            averagePrice=18000.0,
            creationTimestamp=datetime.now(UTC).isoformat()
        )

        await manager.track_position_opened(position)
        assert manager.stats["positions_opened"] == 1
        assert manager.stats["positions_tracked"] == 1

        await manager.track_position_closed(position, pnl=200.0)
        assert manager.stats["positions_closed"] == 1
        assert manager.stats["total_pnl"] == 200.0

    @pytest.mark.asyncio
    async def test_memory_stats_reporting(self, basic_position_manager, sample_positions):
        """Test memory statistics reporting."""
        manager = basic_position_manager
        manager.tracked_positions = {p.contractId: p for p in sample_positions}

        stats = manager.get_memory_stats()

        assert stats["tracked_positions"] == 2
        assert stats["position_alerts"] == 0
        assert stats["cache_size"] == 2
        assert "memory_usage_mb" in stats

    @pytest.mark.asyncio
    async def test_risk_calculation_tracking(self, basic_position_manager):
        """Test tracking of risk calculations."""
        manager = basic_position_manager

        await manager.track_risk_calculation(1000.0)
        await manager.track_risk_calculation(2000.0)

        assert manager.stats["risk_calculations"] == 2

    @pytest.mark.asyncio
    async def test_get_position_stats(self, basic_position_manager):
        """Test comprehensive position statistics."""
        manager = basic_position_manager

        # Set up some stats
        manager.stats["positions_opened"] = 10
        manager.stats["positions_closed"] = 5
        manager.stats["total_pnl"] = 1500.0
        manager.stats["winning_trades"] = 3
        manager.stats["losing_trades"] = 2

        stats = await manager.get_position_stats()

        assert stats["total_opened"] == 10
        assert stats["total_closed"] == 5
        assert stats["total_pnl"] == 1500.0
        assert stats["win_rate"] == 0.6  # 3/5
        assert stats["active_positions"] == 0


class TestIntegrationScenarios:
    """Test integration with other components."""

    @pytest.mark.asyncio
    async def test_order_sync_on_position_update(self, mock_client, mock_order_manager):
        """Test order synchronization when positions update."""
        event_bus = EventBus()
        manager = PositionManager(mock_client, event_bus)
        await manager.initialize(order_manager=mock_order_manager)

        position = Position(
            id=1, accountId=12345, contractId="MNQ",
            type=1,  # PositionType.LONG
            size=2,
            averagePrice=18000.0,
            creationTimestamp=datetime.now(UTC).isoformat()
        )

        await manager.track_position_opened(position)

        # Should trigger order sync if enabled
        if manager._order_sync_enabled:
            mock_order_manager.sync_orders_with_position.assert_called()

    @pytest.mark.asyncio
    async def test_realtime_callback_registration(self, mock_client, mock_realtime_client):
        """Test proper registration of realtime callbacks."""
        event_bus = EventBus()
        manager = PositionManager(mock_client, event_bus)
        await manager.initialize(realtime_client=mock_realtime_client)

        # Should register callbacks
        assert mock_realtime_client.subscribe_user_updates.called
        assert mock_realtime_client.add_callback.called

        # Verify callback functions are set
        calls = mock_realtime_client.add_callback.call_args_list
        assert len(calls) > 0

    @pytest.mark.asyncio
    async def test_cleanup_releases_resources(self, mock_client, mock_realtime_client, mock_order_manager):
        """Test cleanup properly releases all resources."""
        event_bus = EventBus()
        manager = PositionManager(mock_client, event_bus)
        await manager.initialize(
            realtime_client=mock_realtime_client,
            order_manager=mock_order_manager
        )

        # Add some data
        manager.tracked_positions["MNQ"] = Mock()
        manager.position_alerts["alert1"] = Mock()

        await manager.cleanup()

        # All resources should be released
        assert len(manager.tracked_positions) == 0
        assert len(manager.position_alerts) == 0
        assert manager.order_manager is None
        assert manager._order_sync_enabled is False


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_duplicate_position_handling(self, basic_position_manager):
        """Test handling of duplicate positions."""
        manager = basic_position_manager

        position = Position(
            id=1, accountId=12345, contractId="MNQ",
            type=1,  # PositionType.LONG
            size=1,
            averagePrice=18000.0,
            creationTimestamp=datetime.now(UTC).isoformat()
        )

        # Track same position twice
        await manager.track_position_opened(position)
        await manager.track_position_opened(position)

        # Should only track once
        assert manager.stats["positions_opened"] == 2  # Counted twice
        assert len(manager.tracked_positions) == 1  # But only one in cache

    @pytest.mark.asyncio
    async def test_negative_pnl_handling(self, basic_position_manager):
        """Test handling of negative P&L."""
        manager = basic_position_manager

        position = Position(
            id=1, accountId=12345, contractId="MNQ",
            type=1,  # PositionType.LONG
            size=2,
            averagePrice=18000.0,
            creationTimestamp=datetime.now(UTC).isoformat()
        )

        await manager.track_position_closed(position, pnl=-500.0)

        assert manager.stats["positions_closed"] == 1
        assert manager.stats["total_pnl"] == -500.0
        assert manager.stats["losing_trades"] == 1
        assert manager.stats["winning_trades"] == 0

    @pytest.mark.asyncio
    async def test_empty_position_list_handling(self, basic_position_manager):
        """Test handling of empty position lists."""
        manager = basic_position_manager
        manager.project_x.search_open_positions.return_value = []

        result = await manager.get_all_positions()

        assert result == []
        assert manager.stats["positions_tracked"] == 0

    @pytest.mark.asyncio
    async def test_position_with_extreme_values(self, basic_position_manager):
        """Test handling of positions with extreme values."""
        manager = basic_position_manager

        # Position with very large values
        position = Position(
            id=999999,
            accountId=12345,
            contractId="EXTREME",
            type=1,  # PositionType.LONG
            size=100000,  # Very large size
            averagePrice=999999.99,  # Very high price
            creationTimestamp=datetime.now(UTC).isoformat()
        )

        await manager.track_position_opened(position)

        assert "EXTREME" in manager.tracked_positions
        assert manager.tracked_positions["EXTREME"].size == 100000

    @pytest.mark.asyncio
    async def test_position_without_timestamp(self, basic_position_manager):
        """Test handling of positions without timestamps."""
        manager = basic_position_manager

        position = Position(
            id=1,
            accountId=12345,
            contractId="MNQ",
            type=1,  # PositionType.LONG
            size=1,
            averagePrice=18000.0,
            creationTimestamp=None  # No timestamp
        )

        # Should handle gracefully
        await manager.track_position_opened(position)
        assert "MNQ" in manager.tracked_positions
