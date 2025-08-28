"""
Advanced tests for OrderManager core - Testing untested paths following strict TDD.

These tests are written FIRST to define expected behavior, not to match existing code.
If these tests fail, the implementation must be fixed to match the expected behavior.
"""

import asyncio
import time
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from project_x_py.exceptions import ProjectXAuthenticationError, ProjectXOrderError
from project_x_py.models import Order, OrderPlaceResponse
from project_x_py.order_manager.core import OrderManager
from project_x_py.types.trading import OrderStatus


class TestOrderManagerInitialization:
    """Test OrderManager initialization paths that are currently untested."""

    @pytest.mark.asyncio
    async def test_initialize_with_realtime_connection_failure(self, order_manager):
        """Real-time connection failure should be handled gracefully."""
        # TDD: Define expected behavior when real-time connection fails
        realtime_client = MagicMock()
        realtime_client.user_connected = False
        realtime_client.connect = AsyncMock(return_value=False)
        realtime_client.add_callback = AsyncMock()  # Mock the async callback setup

        # Should return False but not crash
        result = await order_manager.initialize(realtime_client)
        assert result is False
        assert order_manager._realtime_enabled is False
        assert realtime_client.connect.called

    @pytest.mark.asyncio
    async def test_initialize_with_realtime_already_connected(self, order_manager):
        """Should handle already connected real-time client."""
        realtime_client = MagicMock()
        realtime_client.user_connected = True  # Already connected
        realtime_client.connect = AsyncMock()  # Mock connect method
        realtime_client.subscribe_user_updates = AsyncMock(return_value=True)
        realtime_client.add_callback = AsyncMock()  # Mock the async callback setup

        result = await order_manager.initialize(realtime_client)
        assert result is True
        assert order_manager._realtime_enabled is True
        # Should not try to connect again since already connected
        realtime_client.connect.assert_not_called()

    @pytest.mark.asyncio
    async def test_initialize_with_subscribe_failure(self, order_manager):
        """Should handle subscription failure gracefully."""
        realtime_client = MagicMock()
        realtime_client.user_connected = False
        realtime_client.connect = AsyncMock(return_value=True)
        realtime_client.subscribe_user_updates = AsyncMock(return_value=False)
        realtime_client.add_callback = AsyncMock()  # Mock the async callback setup

        result = await order_manager.initialize(realtime_client)
        assert result is True  # Still returns True but with warning
        assert order_manager._realtime_enabled is True
        assert realtime_client.subscribe_user_updates.called

    @pytest.mark.asyncio
    async def test_initialize_exception_handling(self, order_manager):
        """Should handle unexpected exceptions during initialization."""
        realtime_client = MagicMock()
        realtime_client.user_connected = False
        realtime_client.connect = AsyncMock(side_effect=Exception("Network error"))

        result = await order_manager.initialize(realtime_client)
        assert result is False
        assert order_manager._realtime_enabled is False


class TestCircuitBreaker:
    """Test the circuit breaker mechanism for order status checks."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_threshold(self, order_manager):
        """Circuit breaker should open after failure threshold is reached."""
        # Set low threshold for testing
        order_manager.status_check_circuit_breaker_threshold = 3
        order_manager._circuit_breaker_failure_count = 0

        # Simulate failures
        for _ in range(3):
            await order_manager._record_circuit_breaker_failure()

        assert order_manager._circuit_breaker_state == "open"
        assert order_manager._circuit_breaker_failure_count == 3

    @pytest.mark.asyncio
    async def test_circuit_breaker_resets_after_time(self, order_manager):
        """Circuit breaker should reset to half-open after reset time."""
        order_manager.status_check_circuit_breaker_reset_time = 0.1  # 100ms for testing
        order_manager._circuit_breaker_state = "open"
        order_manager._circuit_breaker_last_failure_time = time.time() - 0.2

        # Check if circuit breaker should reset
        if await order_manager._should_attempt_circuit_breaker_recovery():
            order_manager._circuit_breaker_state = "half-open"

        assert order_manager._circuit_breaker_state == "half-open"

    @pytest.mark.asyncio
    async def test_circuit_breaker_closes_on_success(self, order_manager):
        """Circuit breaker should close on successful operation."""
        order_manager._circuit_breaker_state = "half-open"
        order_manager._circuit_breaker_failure_count = 5

        await order_manager._record_circuit_breaker_success()

        assert order_manager._circuit_breaker_state == "closed"
        assert order_manager._circuit_breaker_failure_count == 0

    @pytest.mark.asyncio
    async def test_circuit_breaker_prevents_operations_when_open(self, order_manager):
        """Circuit breaker should prevent operations when open."""
        order_manager._circuit_breaker_state = "open"
        order_manager._circuit_breaker_last_failure_time = time.time()

        # Should skip operations when circuit breaker is open
        should_proceed = await order_manager._check_circuit_breaker()
        assert should_proceed is False


class TestOrderStatusChecking:
    """Test order status checking with retries and fallbacks."""

    @pytest.mark.asyncio
    async def test_is_order_filled_with_retry_backoff(self, order_manager):
        """Should retry with exponential backoff on failure."""
        order_manager.status_check_max_attempts = 3
        order_manager.status_check_initial_delay = 0.01
        order_manager.status_check_backoff_factor = 2.0
        order_manager._realtime_enabled = False

        call_count = 0
        async def failing_get_order(*args):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Network error")
            return Order(
                id=123, accountId=1, contractId="MNQ",
                creationTimestamp="2024-01-01", updateTimestamp=None,
                status=OrderStatus.FILLED, type=1, side=0, size=1
            )

        order_manager.get_order_by_id = failing_get_order

        start_time = time.time()
        result = await order_manager.is_order_filled(123)
        elapsed = time.time() - start_time

        assert result is True
        assert call_count == 3
        # Should have delays between retries
        assert elapsed >= 0.02  # At least initial_delay + backoff

    @pytest.mark.asyncio
    async def test_is_order_filled_all_attempts_fail(self, order_manager):
        """Should return False when all retry attempts fail."""
        order_manager.status_check_max_attempts = 2
        order_manager.status_check_initial_delay = 0.01
        order_manager._realtime_enabled = False

        async def always_failing(*args):
            raise Exception("Persistent network error")

        order_manager.get_order_by_id = always_failing

        result = await order_manager.is_order_filled(999)
        assert result is False

    @pytest.mark.asyncio
    async def test_is_order_filled_with_jitter(self, order_manager):
        """Should add jitter to prevent thundering herd."""
        order_manager.status_check_max_attempts = 2
        order_manager.status_check_initial_delay = 0.1
        order_manager._realtime_enabled = True
        order_manager.order_status_cache = {}

        # Mock to simulate cache miss then API call
        order_manager.get_tracked_order_status = AsyncMock(return_value=None)
        order_manager.get_order_by_id = AsyncMock(side_effect=[
            Exception("First attempt fails"),
            Order(id=555, accountId=1, contractId="MNQ",
                  creationTimestamp="2024-01-01", updateTimestamp=None,
                  status=OrderStatus.OPEN, type=1, side=0, size=1)
        ])

        result = await order_manager.is_order_filled(555)
        assert result is False
        assert order_manager.get_order_by_id.call_count == 2


class TestPriceAlignmentAndValidation:
    """Test price alignment and validation edge cases."""

    @pytest.mark.asyncio
    async def test_place_order_with_invalid_tick_size(self, order_manager):
        """Should handle tick size validation failures gracefully."""
        with patch('project_x_py.order_manager.utils.validate_price_tick_size') as mock_validate:
            mock_validate.side_effect = Exception("Invalid tick size")

            order_manager.project_x._make_request = AsyncMock(
                return_value={"success": True, "orderId": 100}
            )

            # Should still place order despite validation failure
            response = await order_manager.place_order(
                contract_id="INVALID",
                order_type=1,
                side=0,
                size=1,
                limit_price=100.123456  # Invalid price
            )
            assert response.orderId == 100

    @pytest.mark.asyncio
    async def test_place_order_aligns_all_price_types(self, order_manager):
        """Should align limit, stop, and trail prices to tick size."""
        # The fixture already mocks align_price_to_tick_size to return the input
        # We need to re-patch it with our custom behavior
        with patch('project_x_py.order_manager.core.align_price_to_tick_size') as mock_align:
            mock_align.side_effect = lambda price, *args, **kwargs: round(price, 2) if price else None

            order_manager.project_x._make_request = AsyncMock(
                return_value={"success": True, "orderId": 200}
            )

            await order_manager.place_order(
                contract_id="MNQ",
                order_type=1,
                side=0,
                size=1,
                limit_price=100.777,
                stop_price=99.333,
                trail_price=1.999
            )

            # Should have aligned all three prices
            assert mock_align.call_count == 3
            call_args = order_manager.project_x._make_request.call_args[1]["data"]
            assert call_args.get("limitPrice") == 100.78
            assert call_args.get("stopPrice") == 99.33
            assert call_args.get("trailPrice") == 2.00


class TestConcurrentOrderOperations:
    """Test concurrent order operations and thread safety."""

    @pytest.mark.asyncio
    async def test_concurrent_order_placement(self, order_manager):
        """Should handle concurrent order placement safely."""
        order_manager.project_x._make_request = AsyncMock(
            side_effect=[
                {"success": True, "orderId": i} for i in range(10)
            ]
        )

        # Place 10 orders concurrently
        tasks = [
            order_manager.place_market_order("MNQ", 0, 1)
            for _ in range(10)
        ]

        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        assert all(isinstance(r, OrderPlaceResponse) for r in results)
        assert order_manager.stats["orders_placed"] == 10

    @pytest.mark.asyncio
    async def test_concurrent_order_cancellation(self, order_manager):
        """Should handle concurrent cancellations safely."""
        # Setup tracked orders
        for i in range(5):
            order_manager.tracked_orders[str(i)] = {"status": 1}
            order_manager.order_status_cache[str(i)] = 1

        order_manager.project_x._make_request = AsyncMock(
            return_value={"success": True}
        )

        # Cancel orders concurrently
        tasks = [order_manager.cancel_order(i) for i in range(5)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        assert all(r is True for r in results)
        assert order_manager.stats["orders_cancelled"] == 5

    @pytest.mark.asyncio
    async def test_order_lock_prevents_race_conditions(self, order_manager):
        """Order lock should prevent race conditions in statistics."""
        async def slow_response(*args, **kwargs):
            await asyncio.sleep(0.01)
            return {"success": True, "orderId": 1}

        order_manager.project_x._make_request = AsyncMock(side_effect=slow_response)

        initial_count = order_manager.stats["orders_placed"]

        # Try to place orders concurrently
        tasks = [order_manager.place_market_order("MNQ", 0, 1) for _ in range(5)]
        await asyncio.gather(*tasks)

        # Stats should be correctly incremented despite concurrency
        assert order_manager.stats["orders_placed"] == initial_count + 5


class TestOrderStatisticsHealth:
    """Test order statistics and health check functionality."""

    @pytest.mark.asyncio
    async def test_get_health_status(self, order_manager):
        """Should return comprehensive health status."""
        # Set up some statistics
        order_manager.stats["orders_placed"] = 100
        order_manager.stats["orders_filled"] = 80
        order_manager.stats["orders_rejected"] = 5
        order_manager._circuit_breaker_state = "closed"

        health = await order_manager.get_health_status()

        assert "status" in health
        assert "metrics" in health
        assert health["metrics"]["fill_rate"] == 0.8
        assert health["metrics"]["rejection_rate"] == 0.05
        assert health["circuit_breaker_state"] == "closed"

    @pytest.mark.asyncio
    async def test_get_health_status_unhealthy(self, order_manager):
        """Should detect unhealthy conditions."""
        order_manager.stats["orders_placed"] = 100
        order_manager.stats["orders_rejected"] = 30  # High rejection rate
        order_manager._circuit_breaker_state = "open"

        health = await order_manager.get_health_status()

        assert health["status"] == "unhealthy"
        assert health["metrics"]["rejection_rate"] == 0.3
        assert "high_rejection_rate" in health.get("issues", [])

    @pytest.mark.asyncio
    async def test_calculate_fill_rate_with_zero_orders(self, order_manager):
        """Should handle zero division in fill rate calculation."""
        order_manager.stats["orders_placed"] = 0
        order_manager.stats["orders_filled"] = 0

        stats = order_manager.get_order_statistics()
        assert stats["fill_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_statistics_update_on_order_lifecycle(self, order_manager):
        """Statistics should update correctly through order lifecycle."""
        order_manager.project_x._make_request = AsyncMock(
            return_value={"success": True, "orderId": 777}
        )

        # Place order
        await order_manager.place_limit_order("MNQ", 0, 1, 17000)
        assert order_manager.stats["orders_placed"] == 1
        assert order_manager.stats["limit_orders"] == 1

        # Simulate fill
        order_manager.tracked_orders["777"] = {"status": 1}
        order_manager.order_status_cache["777"] = 2  # Filled
        await order_manager._update_order_statistics_on_fill({"size": 1, "limitPrice": 17000})

        assert order_manager.stats["orders_filled"] == 1
        # total_volume is incremented both when placing (size=1) and filling (size=1)
        assert order_manager.stats["total_volume"] == 2


class TestErrorRecoveryIntegration:
    """Test integration with error recovery manager."""

    @pytest.mark.asyncio
    async def test_recovery_manager_initialization(self, order_manager):
        """Recovery manager should be properly initialized."""
        assert hasattr(order_manager, '_recovery_manager')
        assert order_manager._recovery_manager is not None
        assert order_manager._recovery_manager.order_manager == order_manager

    @pytest.mark.asyncio
    async def test_recovery_manager_handles_partial_failures(self, order_manager):
        """Recovery manager should handle partial operation failures."""
        recovery_manager = order_manager._recovery_manager

        # Start an operation
        operation = await recovery_manager.start_operation("bracket_order")
        assert operation is not None
        assert operation.type == "bracket_order"

        # Add orders to operation
        await recovery_manager.add_order_to_operation(
            operation.id, "1", "entry", {"limit_price": 100}
        )
        await recovery_manager.add_order_to_operation(
            operation.id, "2", "stop", {"stop_price": 95}
        )

        # Record partial failure
        await recovery_manager.record_order_failure(operation.id, "2", "Network error")

        # Should track failed order
        assert operation.orders["2"]["status"] == "failed"
        assert operation.orders["2"]["error"] == "Network error"


class TestMemoryManagement:
    """Test memory management and cleanup."""

    @pytest.mark.asyncio
    async def test_cleanup_task_starts_on_initialize(self, order_manager):
        """Cleanup task should start when initialized with realtime."""
        realtime_client = MagicMock()
        realtime_client.user_connected = True
        realtime_client.subscribe_user_updates = AsyncMock(return_value=True)

        with patch.object(order_manager, '_start_cleanup_task') as mock_cleanup:
            mock_cleanup.return_value = asyncio.sleep(0)
            await order_manager.initialize(realtime_client)
            mock_cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_order_cache_cleanup(self, order_manager):
        """Old orders should be cleaned from cache."""
        # Add old orders to cache
        old_time = time.time() - 7200  # 2 hours old
        order_manager.tracked_orders["old1"] = {"timestamp": old_time, "status": 2}
        order_manager.tracked_orders["old2"] = {"timestamp": old_time, "status": 3}
        order_manager.tracked_orders["recent"] = {"timestamp": time.time(), "status": 1}

        # Run cleanup
        await order_manager._cleanup_old_orders()

        # Old completed orders should be removed
        assert "old1" not in order_manager.tracked_orders
        assert "old2" not in order_manager.tracked_orders
        assert "recent" in order_manager.tracked_orders


class TestAccountHandling:
    """Test account ID handling and validation."""

    @pytest.mark.asyncio
    async def test_place_order_with_invalid_account_id(self, order_manager):
        """Should validate account ID before placing order."""
        order_manager.project_x.account_info.id = 12345

        with pytest.raises(ProjectXOrderError) as exc_info:
            await order_manager.place_order(
                contract_id="MNQ",
                order_type=1,
                side=0,
                size=1,
                account_id=99999  # Invalid account ID
            )
        assert "account" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_search_orders_uses_correct_account(self, order_manager):
        """Should use correct account ID when searching orders."""
        order_manager.project_x.account_info.id = 55555
        order_manager.project_x._make_request = AsyncMock(
            return_value={"success": True, "orders": []}
        )

        await order_manager.search_open_orders(account_id=55555)

        call_args = order_manager.project_x._make_request.call_args
        assert call_args[1]["data"]["accountId"] == 55555


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_place_order_with_zero_size(self, order_manager):
        """Should reject orders with zero size."""
        with pytest.raises(ProjectXOrderError) as exc_info:
            await order_manager.place_order(
                contract_id="MNQ",
                order_type=1,
                side=0,
                size=0,  # Invalid size
                limit_price=17000
            )
        assert "size" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_place_order_with_negative_price(self, order_manager):
        """Should reject orders with negative prices."""
        with pytest.raises(ProjectXOrderError) as exc_info:
            await order_manager.place_order(
                contract_id="MNQ",
                order_type=1,
                side=0,
                size=1,
                limit_price=-100  # Invalid price
            )
        assert "price" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_modify_order_with_no_changes(self, order_manager):
        """Should handle modification with no actual changes."""
        order_manager.get_order_by_id = AsyncMock(
            return_value=Order(
                id=123, accountId=1, contractId="MNQ",
                creationTimestamp="2024-01-01", updateTimestamp=None,
                status=1, type=1, side=0, size=1,
                limitPrice=17000.0
            )
        )

        # Try to modify with same values
        result = await order_manager.modify_order(123)
        assert result is True  # No-op is considered successful

    @pytest.mark.asyncio
    async def test_cancel_already_filled_order(self, order_manager):
        """Should not cancel already filled orders."""
        order_manager.tracked_orders["999"] = {"status": 2}  # Already filled
        order_manager.order_status_cache["999"] = 2

        with pytest.raises(ProjectXOrderError) as exc_info:
            await order_manager.cancel_order(999)
        assert "already filled" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_get_order_by_id_with_invalid_cache_data(self, order_manager):
        """Should handle invalid cached data gracefully."""
        order_manager._realtime_enabled = True
        order_manager.get_tracked_order_status = AsyncMock(
            return_value={"invalid": "data"}  # Missing required fields
        )
        order_manager.project_x._make_request = AsyncMock(
            return_value={"success": True, "orders": []}
        )

        result = await order_manager.get_order_by_id(888)
        assert result is None
        # Should fall back to API
        assert order_manager.project_x._make_request.called
