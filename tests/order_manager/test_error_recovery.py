"""Comprehensive tests for OrderManager error recovery functionality."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from project_x_py.models import OrderPlaceResponse
from project_x_py.order_manager.error_recovery import (
    OperationRecoveryManager,
    OperationState,
    OperationType,
    OrderReference,
    RecoveryOperation,
)


class MockOrderManager:
    """Mock OrderManager for testing error recovery."""

    def __init__(self):
        self.oco_groups = {}
        self.project_x = MagicMock()

    def _link_oco_orders(self, order1_id: int, order2_id: int) -> None:
        """Mock OCO linking."""
        self.oco_groups[order1_id] = order2_id
        self.oco_groups[order2_id] = order1_id

    async def track_order_for_position(
        self, contract_id: str, order_id: int, order_type: str
    ) -> None:
        """Mock position tracking."""

    async def cancel_order(self, order_id: int, account_id: int | None = None) -> bool:
        """Mock cancel order."""
        return True

    async def place_market_order(
        self, contract_id: str, side: int, size: int
    ) -> OrderPlaceResponse:
        """Mock market order placement."""
        return OrderPlaceResponse(
            orderId=123,
            success=True,
            errorCode=0,
            errorMessage=None
        )

    async def place_limit_order(
        self, contract_id: str, side: int, size: int, price: float
    ) -> OrderPlaceResponse:
        """Mock limit order placement."""
        return OrderPlaceResponse(
            orderId=124,
            success=True,
            errorCode=0,
            errorMessage=None
        )

    async def place_stop_order(
        self, contract_id: str, side: int, size: int, price: float
    ) -> OrderPlaceResponse:
        """Mock stop order placement."""
        return OrderPlaceResponse(
            orderId=125,
            success=True,
            errorCode=0,
            errorMessage=None
        )


@pytest.fixture
def mock_order_manager():
    """Create a mock order manager."""
    return MockOrderManager()


@pytest.fixture
def recovery_manager(mock_order_manager):
    """Create a recovery manager with mock order manager."""
    return OperationRecoveryManager(mock_order_manager)


@pytest.fixture
def sample_order_response():
    """Sample successful order response."""
    return OrderPlaceResponse(
        orderId=123,
        success=True,
        errorCode=0,
        errorMessage=None
    )


class TestOrderReference:
    """Test OrderReference dataclass."""

    def test_order_reference_initialization(self):
        """Test OrderReference initialization with defaults."""
        ref = OrderReference()

        assert ref.order_id is None
        assert ref.response is None
        assert ref.contract_id == ""
        assert ref.side == 0
        assert ref.size == 0
        assert ref.order_type == ""
        assert ref.price is None
        assert ref.placed_successfully is False
        assert ref.cancel_attempted is False
        assert ref.cancel_successful is False
        assert ref.error_message is None

    def test_order_reference_with_values(self):
        """Test OrderReference with specific values."""
        response = OrderPlaceResponse(orderId=123, success=True, errorCode=0, errorMessage=None)

        ref = OrderReference(
            order_id=123,
            response=response,
            contract_id="MNQ",
            side=0,
            size=2,
            order_type="entry",
            price=17000.0,
            placed_successfully=True
        )

        assert ref.order_id == 123
        assert ref.response == response
        assert ref.contract_id == "MNQ"
        assert ref.side == 0
        assert ref.size == 2
        assert ref.order_type == "entry"
        assert ref.price == 17000.0
        assert ref.placed_successfully is True


class TestRecoveryOperation:
    """Test RecoveryOperation dataclass."""

    def test_recovery_operation_initialization(self):
        """Test RecoveryOperation initialization with defaults."""
        op = RecoveryOperation()

        assert len(op.operation_id) > 0  # UUID generated
        assert op.operation_type == OperationType.BRACKET_ORDER
        assert op.state == OperationState.PENDING
        assert op.started_at > 0
        assert op.completed_at is None
        assert len(op.orders) == 0
        assert len(op.oco_pairs) == 0
        assert len(op.position_tracking) == 0
        assert len(op.rollback_actions) == 0
        assert len(op.errors) == 0
        assert op.last_error is None
        assert op.max_retries == 3
        assert op.retry_count == 0
        assert op.retry_delay == 1.0
        assert op.required_orders == 0
        assert op.successful_orders == 0

    def test_recovery_operation_with_values(self):
        """Test RecoveryOperation with specific values."""
        op = RecoveryOperation(
            operation_type=OperationType.OCO_PAIR,
            state=OperationState.IN_PROGRESS,
            max_retries=5,
            retry_delay=2.0
        )

        assert op.operation_type == OperationType.OCO_PAIR
        assert op.state == OperationState.IN_PROGRESS
        assert op.max_retries == 5
        assert op.retry_delay == 2.0


class TestOperationRecoveryManager:
    """Test OperationRecoveryManager functionality."""

    def test_recovery_manager_initialization(self, mock_order_manager):
        """Test recovery manager initialization."""
        manager = OperationRecoveryManager(mock_order_manager)

        assert manager.order_manager == mock_order_manager
        assert len(manager.active_operations) == 0
        assert len(manager.operation_history) == 0
        assert manager.max_history == 100

        # Test statistics initialization
        stats = manager.recovery_stats
        assert stats["operations_started"] == 0
        assert stats["operations_completed"] == 0
        assert stats["operations_failed"] == 0
        assert stats["operations_rolled_back"] == 0
        assert stats["recovery_attempts"] == 0
        assert stats["successful_recoveries"] == 0

    @pytest.mark.asyncio
    async def test_start_operation(self, recovery_manager):
        """Test starting a new recovery operation."""
        operation = await recovery_manager.start_operation(
            OperationType.BRACKET_ORDER,
            max_retries=5,
            retry_delay=2.0
        )

        assert operation.operation_type == OperationType.BRACKET_ORDER
        assert operation.state == OperationState.PENDING
        assert operation.max_retries == 5
        assert operation.retry_delay == 2.0

        # Should be in active operations
        assert operation.operation_id in recovery_manager.active_operations
        assert recovery_manager.recovery_stats["operations_started"] == 1

    @pytest.mark.asyncio
    async def test_add_order_to_operation(self, recovery_manager):
        """Test adding order reference to operation."""
        operation = await recovery_manager.start_operation(OperationType.BRACKET_ORDER)

        order_ref = await recovery_manager.add_order_to_operation(
            operation,
            contract_id="MNQ",
            side=0,
            size=2,
            order_type="entry",
            price=17000.0
        )

        assert order_ref.contract_id == "MNQ"
        assert order_ref.side == 0
        assert order_ref.size == 2
        assert order_ref.order_type == "entry"
        assert order_ref.price == 17000.0

        assert len(operation.orders) == 1
        assert operation.required_orders == 1
        assert operation.orders[0] == order_ref

    @pytest.mark.asyncio
    async def test_record_order_success(self, recovery_manager, sample_order_response):
        """Test recording successful order placement."""
        operation = await recovery_manager.start_operation(OperationType.BRACKET_ORDER)
        order_ref = await recovery_manager.add_order_to_operation(
            operation, "MNQ", 0, 2, "entry"
        )

        await recovery_manager.record_order_success(
            operation, order_ref, sample_order_response
        )

        assert order_ref.order_id == sample_order_response.orderId
        assert order_ref.response == sample_order_response
        assert order_ref.placed_successfully is True
        assert operation.successful_orders == 1

    @pytest.mark.asyncio
    async def test_record_order_failure(self, recovery_manager):
        """Test recording failed order placement."""
        operation = await recovery_manager.start_operation(OperationType.BRACKET_ORDER)
        order_ref = await recovery_manager.add_order_to_operation(
            operation, "MNQ", 0, 2, "entry"
        )

        error_msg = "Insufficient funds"
        await recovery_manager.record_order_failure(operation, order_ref, error_msg)

        assert order_ref.placed_successfully is False
        assert order_ref.error_message == error_msg
        assert error_msg in operation.errors
        assert operation.last_error == error_msg

    @pytest.mark.asyncio
    async def test_add_oco_pair(self, recovery_manager, sample_order_response):
        """Test adding OCO pair relationship."""
        operation = await recovery_manager.start_operation(OperationType.OCO_PAIR)

        order1_ref = await recovery_manager.add_order_to_operation(
            operation, "MNQ", 0, 2, "stop"
        )
        order2_ref = await recovery_manager.add_order_to_operation(
            operation, "MNQ", 1, 2, "target"
        )

        # Set order IDs
        order1_ref.order_id = 123
        order2_ref.order_id = 124

        await recovery_manager.add_oco_pair(operation, order1_ref, order2_ref)

        assert (123, 124) in operation.oco_pairs

    @pytest.mark.asyncio
    async def test_add_oco_pair_no_order_ids(self, recovery_manager):
        """Test adding OCO pair when orders don't have IDs yet."""
        operation = await recovery_manager.start_operation(OperationType.OCO_PAIR)

        order1_ref = await recovery_manager.add_order_to_operation(
            operation, "MNQ", 0, 2, "stop"
        )
        order2_ref = await recovery_manager.add_order_to_operation(
            operation, "MNQ", 1, 2, "target"
        )

        await recovery_manager.add_oco_pair(operation, order1_ref, order2_ref)

        # Should not add pair without order IDs
        assert len(operation.oco_pairs) == 0

    @pytest.mark.asyncio
    async def test_add_position_tracking(self, recovery_manager):
        """Test adding position tracking relationship."""
        operation = await recovery_manager.start_operation(OperationType.BRACKET_ORDER)

        order_ref = await recovery_manager.add_order_to_operation(
            operation, "MNQ", 0, 2, "entry"
        )
        order_ref.order_id = 123

        await recovery_manager.add_position_tracking(
            operation, "MNQ", order_ref, "entry"
        )

        assert "MNQ" in operation.position_tracking
        assert 123 in operation.position_tracking["MNQ"]

    @pytest.mark.asyncio
    async def test_add_position_tracking_no_order_id(self, recovery_manager):
        """Test adding position tracking when order has no ID."""
        operation = await recovery_manager.start_operation(OperationType.BRACKET_ORDER)

        order_ref = await recovery_manager.add_order_to_operation(
            operation, "MNQ", 0, 2, "entry"
        )

        await recovery_manager.add_position_tracking(
            operation, "MNQ", order_ref, "entry"
        )

        # Should not add tracking without order ID
        assert len(operation.position_tracking) == 0

    @pytest.mark.asyncio
    async def test_complete_operation_success(self, recovery_manager, sample_order_response):
        """Test successful operation completion."""
        operation = await recovery_manager.start_operation(OperationType.BRACKET_ORDER)

        # Add and complete orders
        order_ref = await recovery_manager.add_order_to_operation(
            operation, "MNQ", 0, 2, "entry"
        )
        await recovery_manager.record_order_success(
            operation, order_ref, sample_order_response
        )

        result = await recovery_manager.complete_operation(operation)

        assert result is True
        assert operation.state == OperationState.COMPLETED
        assert operation.completed_at is not None

        # Should be moved to history
        assert operation.operation_id not in recovery_manager.active_operations
        assert len(recovery_manager.operation_history) == 1
        assert recovery_manager.recovery_stats["operations_completed"] == 1

    @pytest.mark.asyncio
    async def test_complete_operation_with_oco_pairs(self, recovery_manager, mock_order_manager):
        """Test operation completion with OCO pair establishment."""
        operation = await recovery_manager.start_operation(OperationType.OCO_PAIR)

        # Add two orders
        order1_ref = await recovery_manager.add_order_to_operation(
            operation, "MNQ", 0, 2, "stop"
        )
        order2_ref = await recovery_manager.add_order_to_operation(
            operation, "MNQ", 1, 2, "target"
        )

        # Record success
        response1 = OrderPlaceResponse(orderId=123, success=True, errorCode=0, errorMessage=None)
        response2 = OrderPlaceResponse(orderId=124, success=True, errorCode=0, errorMessage=None)

        await recovery_manager.record_order_success(operation, order1_ref, response1)
        await recovery_manager.record_order_success(operation, order2_ref, response2)

        # Add OCO pair
        await recovery_manager.add_oco_pair(operation, order1_ref, order2_ref)

        result = await recovery_manager.complete_operation(operation)

        assert result is True
        assert operation.state == OperationState.COMPLETED

        # Should have linked OCO orders in manager
        assert mock_order_manager.oco_groups[123] == 124
        assert mock_order_manager.oco_groups[124] == 123

    @pytest.mark.asyncio
    async def test_complete_operation_partial_failure(self, recovery_manager):
        """Test operation completion with partial failure."""
        operation = await recovery_manager.start_operation(
            OperationType.BRACKET_ORDER,
            max_retries=0  # Disable recovery attempts
        )

        # Add two orders but only one succeeds
        order1_ref = await recovery_manager.add_order_to_operation(
            operation, "MNQ", 0, 2, "entry"
        )
        order2_ref = await recovery_manager.add_order_to_operation(
            operation, "MNQ", 0, 2, "stop"
        )

        # Only first order succeeds
        response = OrderPlaceResponse(orderId=123, success=True, errorCode=0, errorMessage=None)
        await recovery_manager.record_order_success(operation, order1_ref, response)
        await recovery_manager.record_order_failure(
            operation, order2_ref, "Failed to place"
        )

        result = await recovery_manager.complete_operation(operation)

        assert result is False
        assert operation.state in [OperationState.PARTIALLY_COMPLETED, OperationState.ROLLING_BACK, OperationState.ROLLED_BACK]

    @pytest.mark.asyncio
    async def test_handle_partial_failure_with_retry(self, recovery_manager):
        """Test partial failure handling with retry."""
        operation = await recovery_manager.start_operation(
            OperationType.BRACKET_ORDER, max_retries=1, retry_delay=0.1
        )

        order_ref = await recovery_manager.add_order_to_operation(
            operation, "MNQ", 0, 2, "entry"
        )

        await recovery_manager.record_order_failure(operation, order_ref, "Network error")

        # Mock _place_recovery_order to succeed on retry
        recovery_manager._place_recovery_order = AsyncMock(
            return_value=OrderPlaceResponse(orderId=123, success=True, errorCode=0, errorMessage=None)
        )

        await recovery_manager._handle_partial_failure(operation)

        # Should have attempted recovery
        assert recovery_manager.recovery_stats["recovery_attempts"] >= 1

    @pytest.mark.asyncio
    async def test_handle_partial_failure_max_retries_exceeded(self, recovery_manager):
        """Test partial failure handling when max retries exceeded."""
        operation = await recovery_manager.start_operation(
            OperationType.BRACKET_ORDER, max_retries=0  # No retries
        )

        order_ref = await recovery_manager.add_order_to_operation(
            operation, "MNQ", 0, 2, "entry"
        )

        await recovery_manager.record_order_failure(operation, order_ref, "Network error")

        await recovery_manager._handle_partial_failure(operation)

        # Should go straight to rollback
        assert operation.state == OperationState.ROLLED_BACK

    @pytest.mark.asyncio
    async def test_attempt_recovery_success(self, recovery_manager):
        """Test successful recovery attempt."""
        operation = await recovery_manager.start_operation(OperationType.BRACKET_ORDER)

        order_ref = await recovery_manager.add_order_to_operation(
            operation, "MNQ", 0, 2, "entry", price=17000.0
        )

        # Mock successful recovery
        recovery_manager._place_recovery_order = AsyncMock(
            return_value=OrderPlaceResponse(orderId=123, success=True, errorCode=0, errorMessage=None)
        )

        await recovery_manager._attempt_recovery(operation)

        assert operation.retry_count == 1
        assert recovery_manager.recovery_stats["recovery_attempts"] == 1

    @pytest.mark.asyncio
    async def test_attempt_recovery_failure(self, recovery_manager):
        """Test failed recovery attempt."""
        operation = await recovery_manager.start_operation(
            OperationType.BRACKET_ORDER, max_retries=1
        )

        order_ref = await recovery_manager.add_order_to_operation(
            operation, "MNQ", 0, 2, "entry"
        )

        # Mock failed recovery
        recovery_manager._place_recovery_order = AsyncMock(
            return_value=OrderPlaceResponse(orderId=0, success=False, errorCode=1, errorMessage="Still failed")
        )

        await recovery_manager._attempt_recovery(operation)

        # Should eventually rollback after retries
        assert operation.state == OperationState.ROLLED_BACK

    @pytest.mark.asyncio
    async def test_place_recovery_order_entry_limit(self, recovery_manager, mock_order_manager):
        """Test placing recovery order for entry limit order."""
        order_ref = OrderReference(
            contract_id="MNQ",
            side=0,
            size=2,
            order_type="entry",
            price=17000.0
        )

        mock_order_manager.place_limit_order = AsyncMock(
            return_value=OrderPlaceResponse(orderId=123, success=True, errorCode=0, errorMessage=None)
        )

        result = await recovery_manager._place_recovery_order(order_ref)

        assert result is not None
        assert result.orderId == 123
        mock_order_manager.place_limit_order.assert_called_once_with(
            "MNQ", 0, 2, 17000.0
        )

    @pytest.mark.asyncio
    async def test_place_recovery_order_entry_market(self, recovery_manager, mock_order_manager):
        """Test placing recovery order for entry market order."""
        order_ref = OrderReference(
            contract_id="MNQ",
            side=0,
            size=2,
            order_type="entry",
            price=None
        )

        mock_order_manager.place_market_order = AsyncMock(
            return_value=OrderPlaceResponse(orderId=123, success=True, errorCode=0, errorMessage=None)
        )

        result = await recovery_manager._place_recovery_order(order_ref)

        assert result is not None
        assert result.orderId == 123
        mock_order_manager.place_market_order.assert_called_once_with("MNQ", 0, 2)

    @pytest.mark.asyncio
    async def test_place_recovery_order_stop(self, recovery_manager, mock_order_manager):
        """Test placing recovery order for stop order."""
        order_ref = OrderReference(
            contract_id="MNQ",
            side=1,
            size=2,
            order_type="stop",
            price=16900.0
        )

        mock_order_manager.place_stop_order = AsyncMock(
            return_value=OrderPlaceResponse(orderId=125, success=True, errorCode=0, errorMessage=None)
        )

        result = await recovery_manager._place_recovery_order(order_ref)

        assert result is not None
        assert result.orderId == 125
        mock_order_manager.place_stop_order.assert_called_once_with(
            "MNQ", 1, 2, 16900.0
        )

    @pytest.mark.asyncio
    async def test_place_recovery_order_target(self, recovery_manager, mock_order_manager):
        """Test placing recovery order for target order."""
        order_ref = OrderReference(
            contract_id="MNQ",
            side=1,
            size=2,
            order_type="target",
            price=17100.0
        )

        mock_order_manager.place_limit_order = AsyncMock(
            return_value=OrderPlaceResponse(orderId=124, success=True, errorCode=0, errorMessage=None)
        )

        result = await recovery_manager._place_recovery_order(order_ref)

        assert result is not None
        assert result.orderId == 124
        mock_order_manager.place_limit_order.assert_called_once_with(
            "MNQ", 1, 2, 17100.0
        )

    @pytest.mark.asyncio
    async def test_place_recovery_order_unknown_type(self, recovery_manager):
        """Test placing recovery order with unknown order type."""
        order_ref = OrderReference(
            contract_id="MNQ",
            side=0,
            size=2,
            order_type="unknown",
            price=17000.0
        )

        result = await recovery_manager._place_recovery_order(order_ref)

        assert result is None

    @pytest.mark.asyncio
    async def test_place_recovery_order_exception(self, recovery_manager, mock_order_manager):
        """Test place recovery order with exception."""
        order_ref = OrderReference(
            contract_id="MNQ",
            side=0,
            size=2,
            order_type="entry",
            price=17000.0
        )

        mock_order_manager.place_limit_order = AsyncMock(
            side_effect=Exception("Network error")
        )

        result = await recovery_manager._place_recovery_order(order_ref)

        assert result is None

    @pytest.mark.asyncio
    async def test_rollback_operation(self, recovery_manager, mock_order_manager):
        """Test operation rollback."""
        operation = await recovery_manager.start_operation(OperationType.BRACKET_ORDER)

        # Add successful order
        order_ref = await recovery_manager.add_order_to_operation(
            operation, "MNQ", 0, 2, "entry"
        )
        response = OrderPlaceResponse(
            orderId=123, success=True, errorCode=0, errorMessage=None
        )
        await recovery_manager.record_order_success(operation, order_ref, response)

        # Add OCO pair
        order_ref.order_id = 123
        operation.oco_pairs.append((123, 124))
        mock_order_manager.oco_groups[123] = 124
        mock_order_manager.oco_groups[124] = 123

        # Add position tracking
        operation.position_tracking["MNQ"] = [123]

        mock_order_manager.cancel_order = AsyncMock(return_value=True)

        await recovery_manager._rollback_operation(operation)

        assert operation.state == OperationState.ROLLED_BACK
        assert operation.completed_at is not None

        # Should have cancelled orders
        mock_order_manager.cancel_order.assert_called_once_with(123)

        # Should have cleaned up OCO groups
        assert 123 not in mock_order_manager.oco_groups
        assert 124 not in mock_order_manager.oco_groups

        # Should be in history
        assert operation.operation_id not in recovery_manager.active_operations
        assert len(recovery_manager.operation_history) == 1

    @pytest.mark.asyncio
    async def test_rollback_operation_cancel_failure(self, recovery_manager, mock_order_manager):
        """Test operation rollback with cancellation failures."""
        operation = await recovery_manager.start_operation(OperationType.BRACKET_ORDER)

        order_ref = await recovery_manager.add_order_to_operation(
            operation, "MNQ", 0, 2, "entry"
        )
        response = OrderPlaceResponse(
            orderId=123, success=True, errorCode=0, errorMessage=None
        )
        await recovery_manager.record_order_success(operation, order_ref, response)

        # Mock cancel to fail
        mock_order_manager.cancel_order = AsyncMock(return_value=False)

        await recovery_manager._rollback_operation(operation)

        assert operation.state == OperationState.ROLLED_BACK
        assert order_ref.cancel_attempted is True
        assert order_ref.cancel_successful is False

        # Should have error in operation
        assert len(operation.errors) > 0

    @pytest.mark.asyncio
    async def test_rollback_operation_with_untrack_method(self, recovery_manager, mock_order_manager):
        """Test rollback operation when untrack_order method exists."""
        operation = await recovery_manager.start_operation(OperationType.BRACKET_ORDER)

        order_ref = await recovery_manager.add_order_to_operation(
            operation, "MNQ", 0, 2, "entry"
        )
        order_ref.order_id = 123
        operation.position_tracking["MNQ"] = [123]

        # Add untrack_order method
        mock_order_manager.untrack_order = MagicMock()

        await recovery_manager._rollback_operation(operation)

        # Should have called untrack_order
        mock_order_manager.untrack_order.assert_called_once_with(123)

    @pytest.mark.asyncio
    async def test_handle_operation_failure(self, recovery_manager):
        """Test handling complete operation failure."""
        operation = await recovery_manager.start_operation(OperationType.BRACKET_ORDER)

        await recovery_manager._handle_operation_failure(operation)

        assert recovery_manager.recovery_stats["operations_failed"] == 1
        assert operation.state == OperationState.ROLLED_BACK

    def test_move_to_history(self, recovery_manager):
        """Test moving operation to history."""
        operation = RecoveryOperation()
        recovery_manager.active_operations[operation.operation_id] = operation

        recovery_manager._move_to_history(operation)

        assert operation.operation_id not in recovery_manager.active_operations
        assert len(recovery_manager.operation_history) == 1
        assert recovery_manager.operation_history[0] == operation

    def test_move_to_history_size_limit(self, recovery_manager):
        """Test history size limit enforcement."""
        recovery_manager.max_history = 2

        # Add operations to history
        for _i in range(5):
            op = RecoveryOperation()
            recovery_manager.operation_history.append(op)

        # Add one more to trigger size limit
        new_op = RecoveryOperation()
        recovery_manager.active_operations[new_op.operation_id] = new_op
        recovery_manager._move_to_history(new_op)

        # Should maintain size limit
        assert len(recovery_manager.operation_history) == 2

    @pytest.mark.asyncio
    async def test_force_rollback_operation(self, recovery_manager):
        """Test forcing rollback of an active operation."""
        operation = await recovery_manager.start_operation(OperationType.BRACKET_ORDER)

        result = await recovery_manager.force_rollback_operation(operation.operation_id)

        assert result is True
        assert operation.state == OperationState.ROLLED_BACK

    @pytest.mark.asyncio
    async def test_force_rollback_nonexistent_operation(self, recovery_manager):
        """Test forcing rollback of non-existent operation."""
        result = await recovery_manager.force_rollback_operation("nonexistent")

        assert result is False

    def test_get_operation_status_active(self, recovery_manager):
        """Test getting status of active operation."""
        operation = RecoveryOperation(
            operation_type=OperationType.BRACKET_ORDER,
            state=OperationState.IN_PROGRESS
        )
        recovery_manager.active_operations[operation.operation_id] = operation

        status = recovery_manager.get_operation_status(operation.operation_id)

        assert status is not None
        assert status["operation_id"] == operation.operation_id
        assert status["operation_type"] == OperationType.BRACKET_ORDER.value
        assert status["state"] == OperationState.IN_PROGRESS.value
        assert status["required_orders"] == 0
        assert status["successful_orders"] == 0
        assert "orders" in status
        assert "oco_pairs" in status
        assert "position_tracking" in status

    def test_get_operation_status_history(self, recovery_manager):
        """Test getting status of operation in history."""
        operation = RecoveryOperation(
            operation_type=OperationType.OCO_PAIR,
            state=OperationState.COMPLETED
        )
        recovery_manager.operation_history.append(operation)

        status = recovery_manager.get_operation_status(operation.operation_id)

        assert status is not None
        assert status["operation_type"] == OperationType.OCO_PAIR.value
        assert status["state"] == OperationState.COMPLETED.value

    def test_get_operation_status_not_found(self, recovery_manager):
        """Test getting status of non-existent operation."""
        status = recovery_manager.get_operation_status("nonexistent")

        assert status is None

    def test_get_recovery_statistics(self, recovery_manager):
        """Test getting recovery statistics."""
        # Add some test data
        recovery_manager.recovery_stats.update({
            "operations_started": 10,
            "operations_completed": 7,
            "operations_failed": 2,
            "recovery_attempts": 5,
            "successful_recoveries": 3
        })

        operation = RecoveryOperation()
        recovery_manager.active_operations[operation.operation_id] = operation

        stats = recovery_manager.get_recovery_statistics()

        assert stats["operations_started"] == 10
        assert stats["operations_completed"] == 7
        assert stats["operations_failed"] == 2
        assert stats["recovery_attempts"] == 5
        assert stats["successful_recoveries"] == 3
        assert stats["active_operations"] == 1
        assert stats["history_operations"] == 0
        assert stats["success_rate"] == 0.7  # 7/10
        assert stats["recovery_success_rate"] == 0.6  # 3/5
        assert operation.operation_id in stats["active_operation_ids"]

    def test_get_recovery_statistics_empty(self, recovery_manager):
        """Test getting recovery statistics with no data."""
        stats = recovery_manager.get_recovery_statistics()

        assert stats["operations_started"] == 0
        assert stats["operations_completed"] == 0
        assert stats["success_rate"] == 0.0
        assert stats["recovery_success_rate"] == 0.0
        assert stats["active_operations"] == 0
        assert stats["history_operations"] == 0

    @pytest.mark.asyncio
    async def test_cleanup_stale_operations(self, recovery_manager):
        """Test cleaning up stale operations."""
        # Create old operation
        old_time = time.time() - (25 * 3600)  # 25 hours ago
        operation = RecoveryOperation()
        operation.started_at = old_time
        recovery_manager.active_operations[operation.operation_id] = operation

        # Create recent operation
        recent_operation = RecoveryOperation()
        recovery_manager.active_operations[recent_operation.operation_id] = recent_operation

        cleanup_count = await recovery_manager.cleanup_stale_operations(max_age_hours=24.0)

        assert cleanup_count == 1
        assert operation.operation_id not in recovery_manager.active_operations
        assert recent_operation.operation_id in recovery_manager.active_operations

    def test_operation_types_enum(self):
        """Test OperationType enum values."""
        assert OperationType.BRACKET_ORDER.value == "bracket_order"
        assert OperationType.OCO_PAIR.value == "oco_pair"
        assert OperationType.POSITION_CLOSE.value == "position_close"
        assert OperationType.BULK_CANCEL.value == "bulk_cancel"
        assert OperationType.ORDER_MODIFICATION.value == "order_modification"

    def test_operation_states_enum(self):
        """Test OperationState enum values."""
        assert OperationState.PENDING.value == "pending"
        assert OperationState.IN_PROGRESS.value == "in_progress"
        assert OperationState.PARTIALLY_COMPLETED.value == "partially_completed"
        assert OperationState.COMPLETED.value == "completed"
        assert OperationState.FAILED.value == "failed"
        assert OperationState.ROLLING_BACK.value == "rolling_back"
        assert OperationState.ROLLED_BACK.value == "rolled_back"


class TestOperationRecoveryEdgeCases:
    """Test edge cases and error conditions for operation recovery."""

    @pytest.mark.asyncio
    async def test_complete_operation_with_exception(self, recovery_manager, mock_order_manager):
        """Test operation completion with exception during completion."""
        operation = await recovery_manager.start_operation(OperationType.BRACKET_ORDER)

        order_ref = await recovery_manager.add_order_to_operation(
            operation, "MNQ", 0, 2, "entry"
        )
        response = OrderPlaceResponse(
            orderId=123, success=True, errorCode=0, errorMessage=None
        )
        await recovery_manager.record_order_success(operation, order_ref, response)

        # Mock _link_oco_orders to raise exception
        mock_order_manager._link_oco_orders = MagicMock(
            side_effect=Exception("OCO linking failed")
        )

        # Add OCO pair to trigger exception
        operation.oco_pairs.append((123, 124))

        result = await recovery_manager.complete_operation(operation)

        # Operation should succeed even if OCO linking fails
        # (orders were placed successfully, just linking failed)
        assert result is True
        assert operation.state == OperationState.COMPLETED
        assert any("Failed to link OCO orders" in error for error in operation.errors)

    @pytest.mark.asyncio
    async def test_rollback_operation_with_cancel_exception(self, recovery_manager, mock_order_manager):
        """Test rollback with exception during cancellation."""
        operation = await recovery_manager.start_operation(OperationType.BRACKET_ORDER)

        order_ref = await recovery_manager.add_order_to_operation(
            operation, "MNQ", 0, 2, "entry"
        )
        response = OrderPlaceResponse(
            orderId=123, success=True, errorCode=0, errorMessage=None
        )
        await recovery_manager.record_order_success(operation, order_ref, response)

        # Mock cancel_order to raise exception
        mock_order_manager.cancel_order = AsyncMock(
            side_effect=Exception("Cancel failed")
        )

        await recovery_manager._rollback_operation(operation)

        assert operation.state == OperationState.ROLLED_BACK
        assert order_ref.cancel_attempted is True
        assert order_ref.cancel_successful is False

        # Should have error for cancellation failure
        assert any("Error canceling order" in error for error in operation.errors)

    @pytest.mark.asyncio
    async def test_rollback_oco_cleanup_exception(self, recovery_manager, mock_order_manager):
        """Test rollback with exception during OCO cleanup."""
        operation = await recovery_manager.start_operation(OperationType.OCO_PAIR)
        operation.oco_pairs.append((123, 124))

        # Create mock oco_groups that raises exception on deletion
        mock_oco_groups = MagicMock()
        mock_oco_groups.__delitem__ = MagicMock(side_effect=KeyError("Not found"))
        mock_oco_groups.__contains__ = MagicMock(return_value=True)
        mock_order_manager.oco_groups = mock_oco_groups

        await recovery_manager._rollback_operation(operation)

        assert operation.state == OperationState.ROLLED_BACK
        # Should have error for OCO cleanup failure
        assert any("Error cleaning OCO pair" in error for error in operation.errors)

    @pytest.mark.asyncio
    async def test_position_tracking_exception(self, recovery_manager, mock_order_manager):
        """Test position tracking with exception."""
        operation = await recovery_manager.start_operation(OperationType.BRACKET_ORDER)

        order_ref = await recovery_manager.add_order_to_operation(
            operation, "MNQ", 0, 2, "entry"
        )
        response = OrderPlaceResponse(
            orderId=123, success=True, errorCode=0, errorMessage=None
        )
        await recovery_manager.record_order_success(operation, order_ref, response)

        operation.position_tracking["MNQ"] = [123]

        # Mock track_order_for_position to raise exception
        mock_order_manager.track_order_for_position = AsyncMock(
            side_effect=Exception("Tracking failed")
        )

        result = await recovery_manager.complete_operation(operation)

        # Should still complete but with error logged
        assert result is True  # Still completes despite tracking error
        assert any("Failed to track order 123" in error for error in operation.errors)

    def test_recovery_operation_with_rollback_actions(self):
        """Test RecoveryOperation with rollback actions."""
        def dummy_action():
            pass

        operation = RecoveryOperation()
        operation.rollback_actions.append(dummy_action)

        assert len(operation.rollback_actions) == 1
        assert operation.rollback_actions[0] == dummy_action
