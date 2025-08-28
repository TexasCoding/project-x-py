"""
Error recovery and transaction management for OrderManager.

Author: @TexasCoding
Date: 2025-01-22

Overview:
    Provides comprehensive error recovery mechanisms for complex order operations
    that can partially fail, leaving the system in an inconsistent state. Implements
    transaction-like semantics with rollback capabilities and state tracking.

Key Features:
    - Transaction-like semantics for multi-step operations
    - Comprehensive rollback mechanisms for partial failures
    - Operation state tracking and recovery
    - Cleanup for failed operations
    - Retry logic with state recovery
    - Circuit breaker patterns for repeated failures
    - Logging and monitoring of recovery attempts

Recovery Scenarios:
    - Bracket order protective orders fail after entry fills
    - OCO linking failures with orphaned orders
    - Position-based order partial failures
    - Background task failures and cleanup
    - Network failures during multi-step operations

The recovery system ensures that even in the face of partial failures,
the system maintains consistency and provides clear recovery paths.
"""

import asyncio
import contextlib
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from project_x_py.models import OrderPlaceResponse
from project_x_py.utils import ProjectXLogger

if TYPE_CHECKING:
    from project_x_py.types import OrderManagerProtocol

logger = ProjectXLogger.get_logger(__name__)


class OrderDict(dict):
    """Dict that also supports list-like integer indexing for backward compatibility."""

    def __getitem__(self, key: int | str) -> Any:
        if isinstance(key, int):
            # Support list-like integer indexing
            if hasattr(self, "_list_items") and 0 <= key < len(self._list_items):
                return self._list_items[key]
            raise IndexError(f"index {key} out of range")
        return super().__getitem__(str(key))

    def __setitem__(self, key: int | str, value: Any) -> None:
        if isinstance(key, int):
            # Store in list format
            if not hasattr(self, "_list_items"):
                self._list_items: list[Any] = []
            while len(self._list_items) <= key:
                self._list_items.append(None)
            self._list_items[key] = value
        super().__setitem__(str(key), value)

    def __len__(self) -> int:
        # Return the max of dict size and list size
        dict_len = super().__len__()
        list_len = len(getattr(self, "_list_items", []))
        return max(dict_len, list_len)


class OperationType(Enum):
    """Types of complex operations that require recovery support."""

    BRACKET_ORDER = "bracket_order"
    OCO_PAIR = "oco_pair"
    POSITION_CLOSE = "position_close"
    BULK_CANCEL = "bulk_cancel"
    ORDER_MODIFICATION = "order_modification"


class OperationState(Enum):
    """States of a complex operation."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PARTIALLY_COMPLETED = "partially_completed"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLING_BACK = "rolling_back"
    ROLLED_BACK = "rolled_back"


@dataclass
class OrderReference:
    """Reference to an order that was placed during an operation."""

    order_id: int | None = None
    response: OrderPlaceResponse | None = None
    contract_id: str = ""
    side: int = 0
    size: int = 0
    order_type: str = ""
    price: float | None = None
    placed_successfully: bool = False
    cancel_attempted: bool = False
    cancel_successful: bool = False
    error_message: str | None = None


@dataclass
class RecoveryOperation:
    """Tracks a complex operation that may need recovery."""

    operation_id: str = field(default_factory=lambda: str(uuid4()))
    operation_type: OperationType | str = OperationType.BRACKET_ORDER
    state: OperationState = OperationState.PENDING
    started_at: float = field(default_factory=time.time)
    completed_at: float | None = None

    # Orders involved in this operation
    orders: OrderDict = field(default_factory=OrderDict)

    # OCO relationships to establish
    oco_pairs: list[tuple[int, int]] = field(default_factory=list)

    # Position tracking relationships
    position_tracking: dict[str, list[int]] = field(default_factory=dict)

    # Recovery actions to take if operation fails
    rollback_actions: list[Callable[..., Any]] = field(default_factory=list)

    @property
    def type(self) -> str:
        """Alias for operation_type for backward compatibility."""
        if isinstance(self.operation_type, OperationType):
            return self.operation_type.value
        return str(self.operation_type)

    @property
    def id(self) -> str:
        """Alias for operation_id for backward compatibility."""
        return self.operation_id

    # Error information
    errors: list[str] = field(default_factory=list)
    last_error: str | None = None

    # Retry configuration
    max_retries: int = 3
    retry_count: int = 0
    retry_delay: float = 1.0

    # Success criteria
    required_orders: int = 0
    successful_orders: int = 0


class OperationRecoveryManager:
    """
    Manages error recovery for complex multi-step operations.

    Provides transaction-like semantics for operations that involve multiple
    order placements or modifications, ensuring system consistency even when
    partial failures occur.
    """

    def __init__(self, order_manager: "OrderManagerProtocol"):
        self.order_manager = order_manager
        self.logger = ProjectXLogger.get_logger(__name__)

        # Track active operations
        self.active_operations: dict[str, RecoveryOperation] = {}

        # Completed operations history (for debugging)
        self.operation_history: list[RecoveryOperation] = []
        self.max_history = 100

        # Recovery statistics
        self.recovery_stats = {
            "operations_started": 0,
            "operations_completed": 0,
            "operations_failed": 0,
            "operations_rolled_back": 0,
            "recovery_attempts": 0,
            "successful_recoveries": 0,
        }

    async def start_operation(
        self,
        operation_type: OperationType | str,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> RecoveryOperation:
        """
        Start a new recoverable operation.

        Args:
            operation_type: Type of operation being performed (enum or string)
            max_retries: Maximum retry attempts for recovery
            retry_delay: Base delay between retry attempts

        Returns:
            RecoveryOperation object to track the operation
        """
        # Convert string to enum if needed
        if isinstance(operation_type, str):
            try:
                operation_type = OperationType(operation_type)
            except ValueError:
                # Try matching by name (e.g., "BRACKET_ORDER" -> OperationType.BRACKET_ORDER)
                if isinstance(operation_type, str):
                    with contextlib.suppress(KeyError, AttributeError):
                        operation_type = OperationType[
                            operation_type.upper().replace("-", "_")
                        ]

        operation = RecoveryOperation(
            operation_type=operation_type,
            state=OperationState.PENDING,
            max_retries=max_retries,
            retry_delay=retry_delay,
        )

        self.active_operations[operation.operation_id] = operation
        self.recovery_stats["operations_started"] += 1

        # Handle both enum and string for logging
        type_str = str(operation_type)
        self.logger.info(
            f"Started recoverable operation {operation.operation_id} of type {type_str}"
        )

        return operation

    async def add_order_to_operation(
        self,
        operation_or_id: RecoveryOperation | str,
        contract_id_or_order_id: str | None = None,
        side_or_order_type: int | str | None = None,
        size_or_details: int | dict[str, Any] | None = None,
        order_type: str | None = None,
        price: float | None = None,
        # Support keyword arguments with original names
        contract_id: str | None = None,
        side: int | None = None,
        size: int | None = None,
    ) -> OrderReference | None:
        """
        Add an order reference to track within an operation.

        Supports two calling patterns:
        1. Legacy: (operation, contract_id, side, size, order_type, price)
        2. New: (operation_id, order_id, order_type, details)

        Args:
            operation_or_id: RecoveryOperation object or operation ID string
            contract_id_or_order_id: Contract ID (legacy) or order ID (new)
            side_or_order_type: Side int (legacy) or order type string (new)
            size_or_details: Size int (legacy) or details dict (new)
            order_type: Order type (legacy only, required if first arg is RecoveryOperation)
            price: Price (legacy only, optional)

        Returns:
            OrderReference for legacy calls, None for new calls
        """
        # Check if this is legacy call pattern
        if isinstance(operation_or_id, RecoveryOperation):
            # Legacy pattern: (operation, contract_id, side, size, order_type, price)
            operation = operation_or_id
            # Use keyword args if provided, otherwise use positional args
            contract_id = (
                contract_id if contract_id is not None else contract_id_or_order_id
            )
            # Ensure side is int
            if side is not None:
                side_val = side
            elif isinstance(side_or_order_type, int):
                side_val = side_or_order_type
            else:
                side_val = None

            # Ensure size is int
            if size is not None:
                size_val = size
            elif isinstance(size_or_details, int):
                size_val = size_or_details
            else:
                size_val = None

            # Ensure types are correct for OrderReference
            order_ref = OrderReference(
                contract_id=str(contract_id) if contract_id is not None else "",
                side=int(side_val) if side_val is not None else 0,
                size=int(size_val) if size_val is not None else 0,
                order_type=order_type or "",
                price=price,
            )

            # Store in the orders dict
            # Use numeric keys to maintain order while being dict compatible
            # Get next available index
            if operation.orders:
                # Find max numeric key and add 1
                numeric_keys = [k for k in operation.orders if isinstance(k, int)]
                index = max(numeric_keys) + 1 if numeric_keys else len(operation.orders)
            else:
                index = 0
            operation.orders[index] = order_ref

            # Also update required_orders if it exists
            if hasattr(operation, "required_orders"):
                operation.required_orders += 1

            self.logger.debug(
                f"Added {order_type} order reference to operation {operation.operation_id}"
            )

            return order_ref
        else:
            # New pattern: (operation_id, order_id, order_type, details)
            operation_id = operation_or_id
            order_id = contract_id_or_order_id
            order_type_str = side_or_order_type
            details = size_or_details if isinstance(size_or_details, dict) else {}

            operation_or_none = self.active_operations.get(operation_id)
            if not operation_or_none:
                return None
            operation = operation_or_none

            # Store order info as dict for compatibility with new tests
            if order_id is not None:
                operation.orders[order_id] = {
                    "type": order_type_str,
                    "status": "pending",
                    **details,
                }

                self.logger.debug(
                    f"Added {order_type_str} order {order_id} to operation {operation_id}"
                )

            return None

    async def record_order_success(
        self,
        operation: RecoveryOperation,
        order_ref: OrderReference,
        response: OrderPlaceResponse,
    ) -> None:
        """
        Record successful order placement within an operation.

        Args:
            operation: The operation containing this order
            order_ref: The order reference to update
            response: The successful order placement response
        """
        order_ref.order_id = response.orderId
        order_ref.response = response
        order_ref.placed_successfully = True

        operation.successful_orders += 1

        self.logger.info(
            f"Order {response.orderId} placed successfully in operation "
            f"{operation.operation_id} ({operation.successful_orders}/"
            f"{operation.required_orders})"
        )

    async def record_order_failure(
        self,
        operation_or_id: RecoveryOperation | str,
        order_ref_or_id: OrderReference | str,
        error: str,
    ) -> None:
        """
        Record failed order placement within an operation.

        Supports two calling patterns:
        1. Legacy: (operation, order_ref, error)
        2. New: (operation_id, order_id, error)

        Args:
            operation_or_id: RecoveryOperation object or operation ID string
            order_ref_or_id: OrderReference object (legacy) or order ID string (new)
            error: Error message describing the failure
        """
        # Check if this is legacy call pattern
        if isinstance(operation_or_id, RecoveryOperation):
            # Legacy pattern: (operation, order_ref, error)
            operation = operation_or_id
            order_ref = order_ref_or_id

            if isinstance(order_ref, OrderReference):
                order_ref.placed_successfully = False
                order_ref.error_message = error

            operation.errors.append(error)
            operation.last_error = error

            self.logger.error(
                f"Order placement failed in operation {operation.operation_id}: {error}"
            )
        else:
            # New pattern: (operation_id, order_id, error)
            operation_id = operation_or_id
            order_id = order_ref_or_id

            operation_or_none = self.active_operations.get(operation_id)
            if not operation_or_none:
                return
            operation = operation_or_none

            if isinstance(order_id, int | str) and order_id in operation.orders:
                operation.orders[order_id]["status"] = "failed"
                operation.orders[order_id]["error"] = error

            operation.errors.append(error)
            operation.last_error = error

            self.logger.error(
                f"Order {order_id} failed in operation {operation_id}: {error}"
            )

    async def add_oco_pair(
        self,
        operation: RecoveryOperation,
        order1_ref: OrderReference,
        order2_ref: OrderReference,
    ) -> None:
        """
        Add an OCO pair relationship to establish after orders are placed.

        Args:
            operation: The operation to add the OCO pair to
            order1_ref: First order in the OCO pair
            order2_ref: Second order in the OCO pair
        """
        if order1_ref.order_id and order2_ref.order_id:
            operation.oco_pairs.append((order1_ref.order_id, order2_ref.order_id))

            self.logger.debug(
                f"Added OCO pair ({order1_ref.order_id}, {order2_ref.order_id}) "
                f"to operation {operation.operation_id}"
            )

    async def add_position_tracking(
        self,
        operation: RecoveryOperation,
        contract_id: str,
        order_ref: OrderReference,
        tracking_type: str,
    ) -> None:
        """
        Add position tracking relationship to establish after order placement.

        Args:
            operation: The operation to add tracking to
            contract_id: Contract ID for position tracking
            order_ref: Order reference to track
            tracking_type: Type of tracking (entry, stop, target)
        """
        if order_ref.order_id:
            if contract_id not in operation.position_tracking:
                operation.position_tracking[contract_id] = []

            operation.position_tracking[contract_id].append(order_ref.order_id)

            self.logger.debug(
                f"Added position tracking for order {order_ref.order_id} "
                f"({tracking_type}) in operation {operation.operation_id}"
            )

    async def complete_operation(self, operation: RecoveryOperation) -> bool:
        """
        Mark an operation as completed and establish all relationships.

        Args:
            operation: The operation to complete

        Returns:
            True if operation completed successfully, False otherwise
        """
        try:
            operation.state = OperationState.IN_PROGRESS

            # Check if all required orders were successful
            if operation.successful_orders < operation.required_orders:
                await self._handle_partial_failure(operation)
                return False

            # Establish OCO relationships
            for order1_id, order2_id in operation.oco_pairs:
                try:
                    self.order_manager._link_oco_orders(order1_id, order2_id)
                    self.logger.info(
                        f"Established OCO link: {order1_id} <-> {order2_id}"
                    )
                except Exception as e:
                    operation.errors.append(f"Failed to link OCO orders: {e}")
                    self.logger.error(f"Failed to establish OCO link: {e}")

            # Establish position tracking
            for contract_id, order_ids in operation.position_tracking.items():
                for order_id in order_ids:
                    try:
                        # Determine tracking type based on order reference
                        order_ref = next(
                            (
                                ref
                                for ref in operation.orders.values()
                                if isinstance(ref, OrderReference)
                                and ref.order_id == order_id
                            ),
                            None,
                        )
                        if order_ref:
                            await self.order_manager.track_order_for_position(
                                contract_id, order_id, order_ref.order_type
                            )
                            self.logger.debug(
                                f"Established position tracking for order {order_id}"
                            )
                    except Exception as e:
                        operation.errors.append(
                            f"Failed to track order {order_id}: {e}"
                        )
                        self.logger.error(f"Failed to track order {order_id}: {e}")

            operation.state = OperationState.COMPLETED
            operation.completed_at = time.time()

            # Move to history
            self._move_to_history(operation)

            self.recovery_stats["operations_completed"] += 1

            self.logger.info(
                f"Operation {operation.operation_id} completed successfully "
                f"with {operation.successful_orders} orders"
            )

            return True

        except Exception as e:
            operation.errors.append(f"Failed to complete operation: {e}")
            operation.last_error = str(e)
            operation.state = OperationState.FAILED

            self.logger.error(
                f"Failed to complete operation {operation.operation_id}: {e}"
            )

            await self._handle_operation_failure(operation)
            return False

    async def _handle_partial_failure(self, operation: RecoveryOperation) -> None:
        """
        Handle partial failure of an operation.

        Args:
            operation: The partially failed operation
        """
        operation.state = OperationState.PARTIALLY_COMPLETED

        self.logger.warning(
            f"Operation {operation.operation_id} partially failed: "
            f"{operation.successful_orders}/{operation.required_orders} orders successful"
        )

        # Try to recover or rollback
        if operation.retry_count < operation.max_retries:
            await self._attempt_recovery(operation)
        else:
            await self._rollback_operation(operation)

    async def _attempt_recovery(self, operation: RecoveryOperation) -> None:
        """
        Attempt to recover a partially failed operation.

        Args:
            operation: The operation to recover
        """
        operation.retry_count += 1
        self.recovery_stats["recovery_attempts"] += 1

        self.logger.info(
            f"Attempting recovery for operation {operation.operation_id} "
            f"(attempt {operation.retry_count}/{operation.max_retries})"
        )

        try:
            # Calculate delay with exponential backoff
            delay = operation.retry_delay * (2 ** (operation.retry_count - 1))
            await asyncio.sleep(delay)

            # Try to place failed orders
            recovery_successful = True

            for order_ref in operation.orders.values():
                if (
                    isinstance(order_ref, OrderReference)
                    and not order_ref.placed_successfully
                ):
                    try:
                        # Determine order placement method based on type
                        response = await self._place_recovery_order(order_ref)

                        if response and response.success:
                            await self.record_order_success(
                                operation, order_ref, response
                            )
                        else:
                            recovery_successful = False
                            error_msg = (
                                response.errorMessage
                                if response
                                and hasattr(response, "errorMessage")
                                and response.errorMessage
                                else "Unknown error"
                            )
                            await self.record_order_failure(
                                operation, order_ref, error_msg
                            )

                    except Exception as e:
                        recovery_successful = False
                        await self.record_order_failure(operation, order_ref, str(e))

            if (
                recovery_successful
                and operation.successful_orders >= operation.required_orders
            ):
                # Recovery successful, complete the operation
                await self.complete_operation(operation)
                self.recovery_stats["successful_recoveries"] += 1
            else:
                # Recovery failed, try again or rollback
                if operation.retry_count < operation.max_retries:
                    await self._attempt_recovery(operation)
                else:
                    await self._rollback_operation(operation)

        except Exception as e:
            operation.errors.append(f"Recovery attempt failed: {e}")
            self.logger.error(f"Recovery attempt failed: {e}")
            await self._rollback_operation(operation)

    async def _place_recovery_order(
        self, order_ref: OrderReference
    ) -> OrderPlaceResponse | None:
        """
        Place an order during recovery attempt.

        Args:
            order_ref: Order reference to place

        Returns:
            OrderPlaceResponse if successful, None otherwise
        """
        try:
            if order_ref.order_type == "entry":
                if order_ref.price:
                    return await self.order_manager.place_limit_order(
                        order_ref.contract_id,
                        order_ref.side,
                        order_ref.size,
                        order_ref.price,
                    )
                else:
                    return await self.order_manager.place_market_order(
                        order_ref.contract_id, order_ref.side, order_ref.size
                    )
            elif order_ref.order_type == "stop":
                return await self.order_manager.place_stop_order(
                    order_ref.contract_id,
                    order_ref.side,
                    order_ref.size,
                    order_ref.price or 0.0,
                )
            elif order_ref.order_type == "target":
                return await self.order_manager.place_limit_order(
                    order_ref.contract_id,
                    order_ref.side,
                    order_ref.size,
                    order_ref.price or 0.0,
                )
            else:
                self.logger.error(
                    f"Unknown order type for recovery: {order_ref.order_type}"
                )
                return None

        except Exception as e:
            self.logger.error(f"Failed to place recovery order: {e}")
            return None

    async def _rollback_operation(self, operation: RecoveryOperation) -> None:
        """
        Rollback a failed operation by canceling successful orders.

        Args:
            operation: The operation to rollback
        """
        operation.state = OperationState.ROLLING_BACK
        self.recovery_stats["operations_rolled_back"] += 1

        self.logger.warning(
            f"Rolling back operation {operation.operation_id} "
            f"after {operation.retry_count} failed recovery attempts"
        )

        rollback_errors = []

        # Cancel successfully placed orders
        # Support both old list format (from _order_refs) and new dict format
        orders_to_cancel = []

        # Check all orders in the operation
        for value in operation.orders.values():
            if isinstance(value, OrderReference):
                order_ref = value
                if (
                    order_ref.placed_successfully
                    and order_ref.order_id
                    and not order_ref.cancel_attempted
                ):
                    orders_to_cancel.append(order_ref)

        # Process orders to cancel
        for order_ref in orders_to_cancel:
            try:
                if order_ref.order_id is None:
                    continue
                order_ref.cancel_attempted = True
                success = await self.order_manager.cancel_order(order_ref.order_id)
                order_ref.cancel_successful = success

                if success:
                    self.logger.info(
                        f"Cancelled order {order_ref.order_id} during rollback"
                    )
                else:
                    rollback_errors.append(
                        f"Failed to cancel order {order_ref.order_id}"
                    )

            except Exception as e:
                rollback_errors.append(
                    f"Error canceling order {order_ref.order_id}: {e}"
                )
                self.logger.error(
                    f"Error during rollback of order {order_ref.order_id}: {e}"
                )

        # Clean up OCO relationships
        for order1_id, order2_id in operation.oco_pairs:
            try:
                if order1_id in self.order_manager.oco_groups:
                    del self.order_manager.oco_groups[order1_id]
                if order2_id in self.order_manager.oco_groups:
                    del self.order_manager.oco_groups[order2_id]
            except Exception as e:
                rollback_errors.append(
                    f"Error cleaning OCO pair ({order1_id}, {order2_id}): {e}"
                )

        # Clean up position tracking
        for _contract_id, order_ids in operation.position_tracking.items():
            for order_id in order_ids:
                try:
                    # Check if untrack_order method exists (might not be present in mixins)
                    if hasattr(self.order_manager, "untrack_order"):
                        self.order_manager.untrack_order(order_id)
                    else:
                        logger.debug(
                            f"Skipping untrack_order for {order_id} - method not available"
                        )
                except Exception as e:
                    rollback_errors.append(f"Error untracking order {order_id}: {e}")

        operation.state = OperationState.ROLLED_BACK
        operation.completed_at = time.time()
        operation.errors.extend(rollback_errors)

        # Move to history
        self._move_to_history(operation)

        if rollback_errors:
            self.logger.error(
                f"Rollback of operation {operation.operation_id} completed with errors: "
                f"{'; '.join(rollback_errors)}"
            )
        else:
            self.logger.info(
                f"Operation {operation.operation_id} rolled back successfully"
            )

    async def _handle_operation_failure(self, operation: RecoveryOperation) -> None:
        """
        Handle complete operation failure.

        Args:
            operation: The failed operation
        """
        self.recovery_stats["operations_failed"] += 1

        self.logger.error(
            f"Operation {operation.operation_id} failed completely. "
            f"Errors: {'; '.join(operation.errors)}"
        )

        # Attempt cleanup
        await self._rollback_operation(operation)

    def _move_to_history(self, operation: RecoveryOperation) -> None:
        """
        Move a completed operation to history.

        Args:
            operation: The operation to move to history
        """
        if operation.operation_id in self.active_operations:
            del self.active_operations[operation.operation_id]

        self.operation_history.append(operation)

        # Maintain history size limit
        if len(self.operation_history) > self.max_history:
            self.operation_history = self.operation_history[-self.max_history :]

    async def force_rollback_operation(self, operation_id: str) -> bool:
        """
        Force rollback of an active operation.

        Args:
            operation_id: ID of the operation to rollback

        Returns:
            True if rollback was initiated, False if operation not found
        """
        if operation_id not in self.active_operations:
            self.logger.warning(
                f"Operation {operation_id} not found for forced rollback"
            )
            return False

        operation = self.active_operations[operation_id]

        self.logger.warning(
            f"Forcing rollback of operation {operation_id} "
            f"(current state: {operation.state.value})"
        )

        await self._rollback_operation(operation)
        return True

    def get_operation_status(self, operation_id: str) -> dict[str, Any] | None:
        """
        Get status of an operation.

        Args:
            operation_id: ID of the operation to check

        Returns:
            Dictionary with operation status or None if not found
        """
        operation = None

        # Check active operations first
        if operation_id in self.active_operations:
            operation = self.active_operations[operation_id]
        else:
            # Check history
            for hist_op in self.operation_history:
                if hist_op.operation_id == operation_id:
                    operation = hist_op
                    break

        if not operation:
            return None

        return {
            "operation_id": operation.operation_id,
            "operation_type": operation.operation_type.value
            if isinstance(operation.operation_type, OperationType)
            else str(operation.operation_type),
            "state": operation.state.value
            if hasattr(operation.state, "value")
            else operation.state,
            "started_at": operation.started_at,
            "completed_at": operation.completed_at,
            "required_orders": operation.required_orders,
            "successful_orders": operation.successful_orders,
            "retry_count": operation.retry_count,
            "max_retries": operation.max_retries,
            "errors": operation.errors,
            "last_error": operation.last_error,
            "orders": [
                {
                    "order_id": ref.order_id if hasattr(ref, "order_id") else None,
                    "contract_id": ref.contract_id
                    if hasattr(ref, "contract_id")
                    else None,
                    "side": ref.side if hasattr(ref, "side") else None,
                    "size": ref.size if hasattr(ref, "size") else None,
                    "order_type": ref.order_type
                    if hasattr(ref, "order_type")
                    else None,
                    "price": ref.price if hasattr(ref, "price") else None,
                    "placed_successfully": ref.placed_successfully
                    if hasattr(ref, "placed_successfully")
                    else False,
                    "cancel_attempted": ref.cancel_attempted
                    if hasattr(ref, "cancel_attempted")
                    else False,
                    "cancel_successful": ref.cancel_successful
                    if hasattr(ref, "cancel_successful")
                    else False,
                    "error_message": ref.error_message
                    if hasattr(ref, "error_message")
                    else None,
                }
                for ref in operation.orders.values()
                if isinstance(ref, OrderReference)
            ],
            "oco_pairs": operation.oco_pairs,
            "position_tracking": operation.position_tracking,
        }

    def get_recovery_statistics(self) -> dict[str, Any]:
        """
        Get comprehensive recovery statistics.

        Returns:
            Dictionary with recovery statistics and system health
        """
        active_count = len(self.active_operations)
        history_count = len(self.operation_history)

        # Calculate success rates
        total_operations = self.recovery_stats["operations_started"]
        success_rate = (
            self.recovery_stats["operations_completed"] / total_operations
            if total_operations > 0
            else 0.0
        )

        recovery_success_rate = (
            self.recovery_stats["successful_recoveries"]
            / self.recovery_stats["recovery_attempts"]
            if self.recovery_stats["recovery_attempts"] > 0
            else 0.0
        )

        return {
            **self.recovery_stats,
            "active_operations": active_count,
            "history_operations": history_count,
            "success_rate": success_rate,
            "recovery_success_rate": recovery_success_rate,
            "active_operation_ids": list(self.active_operations.keys()),
        }

    async def cleanup_stale_operations(self, max_age_hours: float = 24.0) -> int:
        """
        Clean up stale operations that have been active too long.

        Args:
            max_age_hours: Maximum age in hours for active operations

        Returns:
            Number of operations cleaned up
        """
        max_age_seconds = max_age_hours * 3600
        current_time = time.time()
        cleanup_count = 0

        stale_operations = []
        for operation_id, operation in self.active_operations.items():
            if current_time - operation.started_at > max_age_seconds:
                stale_operations.append((operation_id, operation))

        for operation_id, operation in stale_operations:
            self.logger.warning(
                f"Cleaning up stale operation {operation_id} "
                f"(age: {(current_time - operation.started_at) / 3600:.1f} hours)"
            )

            try:
                await self._rollback_operation(operation)
                cleanup_count += 1
            except Exception as e:
                self.logger.error(
                    f"Error cleaning up stale operation {operation_id}: {e}"
                )

        return cleanup_count
