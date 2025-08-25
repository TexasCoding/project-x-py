"""
Async bracket order strategies for ProjectX.

Author: @TexasCoding
Date: 2025-08-02

Overview:
    Provides mixin logic for placing and managing bracket orders—sophisticated, three-legged
    order strategies consisting of entry, stop loss, and take profit orders. Ensures risk
    controls are established atomically and linked to positions for robust trade automation.

Key Features:
    - Place async bracket orders (entry, stop, target) as a single operation
    - Price/side validation and position link management
    - Automatic risk management: stops and targets managed with entry
    - Integrates with core OrderManager and position tracking
    - Comprehensive error handling and validation
    - Real-time tracking of all bracket components

Bracket Order Components:
    - Entry Order: Primary order to establish position (limit or market)
    - Stop Loss Order: Risk management order triggered if price moves against position
    - Take Profit Order: Profit target order triggered if price moves favorably

The bracket order ensures that risk management is in place immediately when the entry
order fills, providing consistent trade management without manual intervention.

Example Usage:
    ```python
    # V3.1: Place bracket orders with TradingSuite
    import asyncio
    from project_x_py import TradingSuite


    async def main():
        # Initialize suite with integrated order manager
        suite = await TradingSuite.create("MNQ")

        # Get current market price for realistic order placement
        current_price = await suite.data.get_current_price()

        # V3.1: Place a bullish bracket order (buy with stop below, target above)
        bracket = await suite.orders.place_bracket_order(
            contract_id=suite.instrument_id,
            side=0,  # Buy
            size=1,
            entry_price=current_price - 10.0,  # Enter below market
            stop_loss_price=current_price - 30.0,  # Risk: $30 per contract
            take_profit_price=current_price + 20.0,  # Reward: $30 per contract
            entry_type="limit",  # Can also use "market"
        )

        print(f"Bracket order placed successfully:")
        print(f"  Entry Order ID: {bracket.entry_order_id}")
        print(f"  Stop Loss ID: {bracket.stop_order_id}")
        print(f"  Take Profit ID: {bracket.target_order_id}")

        # V3.1: Place a bearish bracket order (sell with stop above, target below)
        short_bracket = await suite.orders.place_bracket_order(
            contract_id=suite.instrument_id,
            side=1,  # Sell
            size=2,
            entry_price=current_price + 10.0,  # Enter above market for short
            stop_loss_price=current_price + 30.0,  # Stop above for short
            take_profit_price=current_price - 20.0,  # Target below for short
        )

        await suite.disconnect()


    asyncio.run(main())
    ```

See Also:
    - `order_manager.core.OrderManager`
    - `order_manager.position_orders`
    - `order_manager.order_types`
"""

import asyncio
import logging
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from project_x_py.exceptions import ProjectXOrderError
from project_x_py.models import BracketOrderResponse, OrderPlaceResponse
from project_x_py.utils.error_handler import retry_on_network_error

from .error_recovery import (
    OperationRecoveryManager,
    OperationType,
    OrderReference,
    RecoveryOperation,
)

if TYPE_CHECKING:
    from project_x_py.types import OrderManagerProtocol

logger = logging.getLogger(__name__)


class BracketOrderMixin:
    """
    Mixin for bracket order functionality with comprehensive error recovery.

    Provides methods for placing and managing bracket orders, which are sophisticated
    three-legged order strategies that combine entry, stop loss, and take profit orders
    into a single atomic operation. This ensures consistent risk management and trade
    automation with transaction-like semantics and rollback capabilities.
    Features:
        - Transaction-like bracket order placement
        - Automatic rollback on partial failures
        - Recovery mechanisms for network issues
        - State tracking for complex operations
        - Comprehensive error handling and logging
    """

    def __init__(self) -> None:
        """Initialize the recovery manager for bracket orders."""
        super().__init__()
        # Initialize recovery manager - will be properly set up in the main class
        self._recovery_manager: OperationRecoveryManager | None = None

    def _get_recovery_manager(self) -> OperationRecoveryManager | None:
        """Get or create the recovery manager instance.

        Returns None in test environments where full infrastructure isn't available.
        """
        # Check if we're in a test environment without full infrastructure
        if not hasattr(self, "project_x"):
            return None

        # First check if recovery_manager attribute exists and is already set
        if (
            hasattr(self, "recovery_manager")
            and getattr(self, "recovery_manager", None) is not None
        ):
            return getattr(self, "recovery_manager", None)

        if not self._recovery_manager:
            try:
                # Type: ignore because self will be OrderManager when this mixin is used
                self._recovery_manager = OperationRecoveryManager(self)  # type: ignore[arg-type]
            except Exception as e:
                logger.debug(f"Could not initialize recovery manager: {e}")
                return None
        return self._recovery_manager

    async def _check_order_fill_status(
        self: "OrderManagerProtocol", order_id: int
    ) -> tuple[bool, int, int]:
        """
        Check if order is filled, partially filled, or unfilled.

        Returns:
            tuple[bool, int, int]: (is_fully_filled, filled_size, remaining_size)
        """
        try:
            order = await self.get_order_by_id(order_id)
            if not order:
                return False, 0, 0

            filled_size = order.fillVolume or 0
            total_size = order.size
            remaining_size = total_size - filled_size
            is_fully_filled = filled_size >= total_size

            return is_fully_filled, filled_size, remaining_size
        except Exception as e:
            logger.warning(f"Failed to check order {order_id} fill status: {e}")
            return False, 0, 0

    @retry_on_network_error(max_attempts=3, initial_delay=0.5, backoff_factor=2.0)
    async def _place_protective_orders_with_retry(
        self: "OrderManagerProtocol",
        contract_id: str,
        side: int,
        size: int,
        stop_loss_price: float,
        take_profit_price: float,
        account_id: int | None = None,
    ) -> tuple[Any, Any]:
        """
        Place protective orders with retry logic and exponential backoff.

        Returns:
            tuple: (stop_response, target_response)
        """
        # Place stop loss (opposite side)
        stop_side = 1 if side == 0 else 0
        stop_response = await self.place_stop_order(
            contract_id, stop_side, size, stop_loss_price, account_id
        )

        # Place take profit (opposite side)
        target_response = await self.place_limit_order(
            contract_id, stop_side, size, take_profit_price, account_id
        )

        if (
            not stop_response
            or not stop_response.success
            or not target_response
            or not target_response.success
        ):
            raise ProjectXOrderError("Failed to place one or both protective orders.")

        return stop_response, target_response

    async def place_bracket_order(
        self: "OrderManagerProtocol",
        contract_id: str,
        side: int,
        size: int,
        entry_price: float | None,
        stop_loss_price: float,
        take_profit_price: float,
        entry_type: str = "limit",
        account_id: int | None = None,
    ) -> BracketOrderResponse:
        """
        Place a bracket order with comprehensive error recovery and transaction semantics.

        A bracket order is a sophisticated order strategy that consists of three linked orders:
        1. Entry order (limit or market) - The primary order to establish a position
        2. Stop loss order - Risk management order that's triggered if price moves against position
        3. Take profit order - Profit target order that's triggered if price moves favorably

        This implementation provides transaction-like semantics with automatic rollback on partial
        failures. If any step fails after the entry order is filled, the system will attempt
        recovery and rollback to maintain consistency.

        Recovery Features:
        - Automatic retry for network failures during protective order placement
        - Complete rollback if recovery fails (cancels entry order or closes position)
        - State tracking throughout the entire operation
        - Comprehensive logging of all recovery attempts
        - Circuit breaker for repeated failures

        Args:
            contract_id: The contract ID to trade (e.g., "MGC", "MES", "F.US.EP")
            side: Order side: 0=Buy, 1=Sell
            size: Number of contracts to trade (positive integer)
            entry_price: Entry price for the position (required for limit orders, None for market)
            stop_loss_price: Stop loss price for risk management
            take_profit_price: Take profit price (profit target)
            entry_type: Entry order type: "limit" (default) or "market"
            account_id: Account ID. Uses default account if None.

        Returns:
            BracketOrderResponse with comprehensive information and recovery status

        Raises:
            ProjectXOrderError: If bracket order validation or placement fails completely
        """
        # Validate entry_type parameter
        entry_type_lower = entry_type.lower()
        if entry_type_lower not in ["market", "limit"]:
            raise ProjectXOrderError(
                f"Invalid entry_type '{entry_type}'. Must be 'market' or 'limit'."
            )

        # Validate entry_price for limit orders
        if entry_type_lower == "limit" and entry_price is None:
            raise ProjectXOrderError(
                "entry_price is required for limit orders. Use entry_type='market' for market orders."
            )

        # Initialize recovery manager for this operation (if available)
        recovery_manager: OperationRecoveryManager | None = self._get_recovery_manager()
        operation: RecoveryOperation | None = None

        if recovery_manager:
            operation = await recovery_manager.start_operation(
                OperationType.BRACKET_ORDER, max_retries=3, retry_delay=1.0
            )

        try:
            # CRITICAL: Validate tick sizes BEFORE any price operations
            if hasattr(self, "project_x") and self.project_x:
                from .utils import validate_price_tick_size

                if entry_price is not None:  # Only validate if not market order
                    await validate_price_tick_size(
                        entry_price, contract_id, self.project_x, "entry_price"
                    )
                await validate_price_tick_size(
                    stop_loss_price, contract_id, self.project_x, "stop_loss_price"
                )
                await validate_price_tick_size(
                    take_profit_price, contract_id, self.project_x, "take_profit_price"
                )

            # Convert prices to Decimal for precise comparisons
            # For market orders, use a placeholder for entry_decimal that won't affect validation
            if entry_type_lower == "market":
                # For market orders, we need to determine validation based on side
                # Buy: stop should be below target, Sell: stop should be above target
                stop_decimal = Decimal(str(stop_loss_price))
                target_decimal = Decimal(str(take_profit_price))

                # Validate stop and target relationship for market orders
                if side == 0:  # Buy
                    if stop_decimal >= target_decimal:
                        raise ProjectXOrderError(
                            f"Buy order: stop loss ({stop_loss_price}) must be below take profit ({take_profit_price})"
                        )
                else:  # Sell
                    if stop_decimal <= target_decimal:
                        raise ProjectXOrderError(
                            f"Sell order: stop loss ({stop_loss_price}) must be above take profit ({take_profit_price})"
                        )
                # Skip entry price validations for market orders
                entry_decimal = None
            else:
                # Limit order validation with entry price
                entry_decimal = Decimal(str(entry_price))
                stop_decimal = Decimal(str(stop_loss_price))
                target_decimal = Decimal(str(take_profit_price))

            # Validate prices using Decimal precision (only for limit orders)
            if (
                entry_decimal is not None
            ):  # Only validate against entry for limit orders
                if side == 0:  # Buy
                    if stop_decimal >= entry_decimal:
                        raise ProjectXOrderError(
                            f"Buy order stop loss ({stop_loss_price}) must be below entry ({entry_price})"
                        )
                    if target_decimal <= entry_decimal:
                        raise ProjectXOrderError(
                            f"Buy order take profit ({take_profit_price}) must be above entry ({entry_price})"
                        )
                else:  # Sell
                    if stop_decimal <= entry_decimal:
                        raise ProjectXOrderError(
                            f"Sell order stop loss ({stop_loss_price}) must be above entry ({entry_price})"
                        )
                    if target_decimal >= entry_decimal:
                        raise ProjectXOrderError(
                            f"Sell order take profit ({take_profit_price}) must be below entry ({entry_price})"
                        )

            # Add order references to the recovery operation (if available)
            entry_ref: OrderReference | None = None
            stop_ref: OrderReference | None = None
            target_ref: OrderReference | None = None

            # Determine protective order side (opposite of entry)
            protective_side: int = 1 if side == 0 else 0

            if recovery_manager and operation:
                entry_ref = await recovery_manager.add_order_to_operation(
                    operation,
                    contract_id,
                    side,
                    size,
                    "entry",
                    entry_price if entry_type.lower() != "market" else None,
                )

                stop_ref = await recovery_manager.add_order_to_operation(
                    operation,
                    contract_id,
                    protective_side,
                    size,
                    "stop",
                    stop_loss_price,
                )

                target_ref = await recovery_manager.add_order_to_operation(
                    operation,
                    contract_id,
                    protective_side,
                    size,
                    "target",
                    take_profit_price,
                )

            # Place entry order
            entry_response: OrderPlaceResponse
            if entry_type_lower == "market":
                entry_response = await self.place_market_order(
                    contract_id, side, size, account_id
                )
            else:  # limit
                # entry_price is guaranteed to not be None here due to validation
                entry_response = await self.place_limit_order(
                    contract_id,
                    side,
                    size,
                    entry_price,  # type: ignore[arg-type]
                    account_id,
                )

            if not entry_response or not entry_response.success:
                raise ProjectXOrderError("Failed to place entry order for bracket.")

            entry_order_id = entry_response.orderId
            logger.info(
                f"Bracket entry order {entry_order_id} placed. Waiting for fill..."
            )

            # STEP 2: Wait for entry order to fill and handle partial fills
            logger.info(f"Waiting for entry order {entry_order_id} to fill...")

            # Initialize fill tracking variables
            filled_size = 0
            is_fully_filled = False
            remaining_size = 0

            try:
                is_filled = await self._wait_for_order_fill(
                    entry_order_id, timeout_seconds=60
                )

                # Check fill status after timeout or fill event
                (
                    is_fully_filled,
                    filled_size,
                    remaining_size,
                ) = await self._check_order_fill_status(entry_order_id)

                if not is_filled and not is_fully_filled and filled_size == 0:
                    # Order completely unfilled - cancel and abort
                    logger.warning(
                        f"Bracket entry order {entry_order_id} did not fill. Operation aborted."
                    )
                    try:
                        await self.cancel_order(entry_order_id, account_id)
                    except Exception as cancel_error:
                        logger.error(
                            f"Failed to cancel unfilled entry order: {cancel_error}"
                        )

                    raise ProjectXOrderError(
                        f"Bracket entry order {entry_order_id} did not fill within timeout."
                    )

                elif filled_size > 0 and not is_fully_filled:
                    # Partially filled - use filled size for protective orders
                    logger.warning(
                        f"Entry order {entry_order_id} partially filled: {filled_size}/{filled_size + remaining_size}. "
                        f"Using filled quantity for protective orders."
                    )

                    # Cancel remaining portion
                    try:
                        await self.cancel_order(entry_order_id, account_id)
                    except Exception as cancel_error:
                        logger.error(
                            f"Failed to cancel remaining portion: {cancel_error}"
                        )

                    # Update size for protective orders
                    size = filled_size

                    # Update all order references with the actual filled size
                    if stop_ref:
                        stop_ref.size = size
                    if target_ref:
                        target_ref.size = size

                elif not is_fully_filled and filled_size == 0:
                    # Undefined state - recheck once
                    logger.warning(
                        f"Entry order {entry_order_id} in undefined state. Rechecking..."
                    )
                    await asyncio.sleep(1)

                    (
                        is_fully_filled,
                        filled_size,
                        remaining_size,
                    ) = await self._check_order_fill_status(entry_order_id)

                    if filled_size == 0:
                        # Still unfilled, cancel and abort
                        try:
                            await self.cancel_order(entry_order_id, account_id)
                        except Exception as cancel_error:
                            logger.error(f"Failed to cancel order: {cancel_error}")

                        raise ProjectXOrderError(
                            f"Entry order {entry_order_id} failed to fill after recheck."
                        )
                    else:
                        # Actually partially filled
                        size = filled_size
                        if stop_ref:
                            stop_ref.size = size
                        if target_ref:
                            target_ref.size = size

                logger.info(
                    f"Entry order {entry_order_id} filled (size: {size}). Proceeding with protective orders."
                )

                # Record entry order success with recovery manager
                if recovery_manager and operation and entry_ref:
                    entry_ref.order_id = entry_order_id  # Update with actual order ID
                    await recovery_manager.record_order_success(
                        operation, entry_ref, entry_response
                    )

            except Exception as e:
                error_msg = f"Error during entry order fill processing: {e}"
                if recovery_manager and operation and entry_ref:
                    await recovery_manager.record_order_failure(
                        operation, entry_ref, error_msg
                    )
                raise ProjectXOrderError(error_msg) from e

            # STEP 3: Place protective orders with recovery management
            logger.info("Placing protective orders (stop loss and take profit)...")

            try:
                # Place stop loss order
                logger.debug(f"Placing stop loss at {stop_loss_price}")
                stop_response: OrderPlaceResponse = await self.place_stop_order(
                    contract_id, protective_side, size, stop_loss_price, account_id
                )

                if stop_response and stop_response.success:
                    if recovery_manager and operation and stop_ref:
                        await recovery_manager.record_order_success(
                            operation, stop_ref, stop_response
                        )
                    logger.info(f"Stop loss order placed: {stop_response.orderId}")
                else:
                    error_msg = (
                        stop_response.errorMessage
                        if stop_response
                        and hasattr(stop_response, "errorMessage")
                        and stop_response.errorMessage
                        else "Unknown error"
                    )
                    if recovery_manager and operation and stop_ref:
                        await recovery_manager.record_order_failure(
                            operation, stop_ref, error_msg
                        )
                    logger.error(f"Stop loss order failed: {error_msg}")

                # Place take profit order
                logger.debug(f"Placing take profit at {take_profit_price}")
                target_response: OrderPlaceResponse = await self.place_limit_order(
                    contract_id, protective_side, size, take_profit_price, account_id
                )

                if target_response and target_response.success:
                    if recovery_manager and operation and target_ref:
                        await recovery_manager.record_order_success(
                            operation, target_ref, target_response
                        )
                    logger.info(f"Take profit order placed: {target_response.orderId}")
                else:
                    error_msg = (
                        target_response.errorMessage
                        if target_response
                        and hasattr(target_response, "errorMessage")
                        and target_response.errorMessage
                        else "Unknown error"
                    )
                    if recovery_manager and operation and target_ref:
                        await recovery_manager.record_order_failure(
                            operation, target_ref, error_msg
                        )
                    logger.error(f"Take profit order failed: {error_msg}")

                # CRITICAL BUG FIX: Check if protective orders failed
                stop_failed = not stop_response or not stop_response.success
                target_failed = not target_response or not target_response.success

                if stop_failed or target_failed:
                    # CRITICAL: Position is unprotected! Must close immediately
                    logger.critical(
                        f"CRITICAL: Protective orders failed! Position is UNPROTECTED. "
                        f"Stop: {'FAILED' if stop_failed else 'OK'}, "
                        f"Target: {'FAILED' if target_failed else 'OK'}. "
                        f"Attempting emergency position closure..."
                    )

                    try:
                        # Attempt to close the unprotected position immediately
                        close_response = await self.close_position(
                            contract_id, account_id=account_id
                        )

                        if close_response and close_response.success:
                            logger.info(
                                f"Emergency position closure successful. Order ID: {close_response.orderId}"
                            )
                        else:
                            logger.critical(
                                f"Emergency position closure FAILED! Manual intervention required for {contract_id}!"
                            )
                    except Exception as close_error:
                        logger.critical(
                            f"EMERGENCY CLOSURE EXCEPTION for {contract_id}: {close_error}. "
                            f"MANUAL INTERVENTION REQUIRED!"
                        )

                    # Force rollback if recovery manager available
                    if recovery_manager and operation:
                        await recovery_manager.force_rollback_operation(
                            operation.operation_id
                        )

                    # Raise error to indicate failure
                    raise ProjectXOrderError(
                        f"CRITICAL: Bracket order failed - position was unprotected. "
                        f"Emergency closure attempted. Stop: {'FAILED' if stop_failed else 'OK'}, "
                        f"Target: {'FAILED' if target_failed else 'OK'}."
                    )

                # Add OCO relationship for protective orders if both succeeded
                if (
                    recovery_manager
                    and operation
                    and stop_ref
                    and target_ref
                    and stop_response
                    and stop_response.success
                    and target_response
                    and target_response.success
                ):
                    await recovery_manager.add_oco_pair(operation, stop_ref, target_ref)

                # Add position tracking for all orders
                if recovery_manager and operation:
                    if entry_ref and entry_ref.order_id:
                        await recovery_manager.add_position_tracking(
                            operation, contract_id, entry_ref, "entry"
                        )
                    if stop_ref and stop_ref.order_id:
                        await recovery_manager.add_position_tracking(
                            operation, contract_id, stop_ref, "stop"
                        )
                    if target_ref and target_ref.order_id:
                        await recovery_manager.add_position_tracking(
                            operation, contract_id, target_ref, "target"
                        )
                else:
                    # Fallback position tracking when recovery manager is not available
                    if hasattr(self, "track_order_for_position") and callable(
                        self.track_order_for_position
                    ):
                        await self.track_order_for_position(
                            contract_id, entry_order_id, "entry", account_id
                        )
                        if stop_response and stop_response.success:
                            await self.track_order_for_position(
                                contract_id, stop_response.orderId, "stop", account_id
                            )
                        if target_response and target_response.success:
                            await self.track_order_for_position(
                                contract_id,
                                target_response.orderId,
                                "target",
                                account_id,
                            )

                # Attempt to complete the operation (this handles recovery if needed)
                operation_completed = True  # Default to success for test environments
                if recovery_manager and operation:
                    operation_completed = await recovery_manager.complete_operation(
                        operation
                    )

                if operation_completed:
                    # Success! All orders placed and relationships established
                    self.stats["bracket_orders"] += 1

                    logger.info(
                        f"✅ Bracket order completed successfully: "
                        f"Entry={entry_order_id}, Stop={stop_ref.order_id if stop_ref else stop_response.orderId if stop_response else None}, "
                        f"Target={target_ref.order_id if target_ref else target_response.orderId if target_response else None}"
                    )

                    return BracketOrderResponse(
                        success=True,
                        entry_order_id=entry_order_id,
                        stop_order_id=stop_ref.order_id
                        if stop_ref
                        else (stop_response.orderId if stop_response else None),
                        target_order_id=target_ref.order_id
                        if target_ref
                        else (target_response.orderId if target_response else None),
                        entry_price=entry_price if entry_price is not None else 0.0,
                        stop_loss_price=stop_loss_price,
                        take_profit_price=take_profit_price,
                        entry_response=entry_response,
                        stop_response=stop_response,
                        target_response=target_response,
                        error_message=None,
                    )
                else:
                    # Operation failed and was rolled back
                    error_details = ""
                    if operation and hasattr(operation, "errors"):
                        error_details = f" Errors: {'; '.join(operation.errors)}"
                    error_msg = f"Bracket order operation failed and was rolled back.{error_details}"
                    logger.error(error_msg)

                    return BracketOrderResponse(
                        success=False,
                        entry_order_id=entry_order_id,
                        stop_order_id=stop_ref.order_id
                        if stop_ref
                        else (stop_response.orderId if stop_response else None),
                        target_order_id=target_ref.order_id
                        if target_ref
                        else (target_response.orderId if target_response else None),
                        entry_price=entry_price if entry_price is not None else 0.0,
                        stop_loss_price=stop_loss_price,
                        take_profit_price=take_profit_price,
                        entry_response=entry_response,
                        stop_response=stop_response,
                        target_response=target_response,
                        error_message=error_msg,
                    )

            except Exception as e:
                # Critical failure during protective order placement
                logger.error(
                    f"Critical failure during protective order placement: {e}. "
                    f"Position may be unprotected! Attempting emergency recovery."
                )

                # Force rollback of the operation
                if recovery_manager and operation:
                    await recovery_manager.force_rollback_operation(
                        operation.operation_id
                    )

                # If entry order was filled but protective orders failed,
                # attempt emergency position closure as last resort
                if entry_ref and entry_ref.order_id and filled_size > 0:
                    try:
                        logger.critical(
                            f"Attempting emergency closure of unprotected position for {contract_id}"
                        )
                        await self.close_position(contract_id, account_id=account_id)
                        logger.info("Emergency position closure completed")

                    except Exception as close_error:
                        logger.critical(
                            f"EMERGENCY POSITION CLOSURE FAILED for {contract_id}: {close_error}. "
                            f"MANUAL INTERVENTION REQUIRED!"
                        )

                raise ProjectXOrderError(
                    f"CRITICAL: Bracket order failed with unprotected position. "
                    f"Recovery attempted. Original error: {e}"
                ) from e

        except Exception as e:
            # Final catch-all error handling
            logger.error(f"Bracket order operation failed completely: {e}")

            # Ensure operation is cleaned up
            if (
                recovery_manager
                and operation
                and operation.operation_id in recovery_manager.active_operations
            ):
                try:
                    await recovery_manager.force_rollback_operation(
                        operation.operation_id
                    )
                except Exception as cleanup_error:
                    logger.error(f"Failed to cleanup operation: {cleanup_error}")

            raise ProjectXOrderError(f"Bracket order operation failed: {e}") from e
