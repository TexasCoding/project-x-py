"""
Async OrderManager core for ProjectX trading.

Author: @TexasCoding
Date: 2025-08-02

Overview:
    Contains the main OrderManager class, orchestrating all async order operations
    (placement, modification, cancellation, tracking) and integrating mixins for
    bracket, position, and order type strategies. Provides thread-safe, eventful,
    and real-time capable order workflows for automated and manual trading.

Key Features:
    - Unified async API for order lifecycle (market, limit, stop, trailing, OCO)
    - Bracket and position-based order strategies
    - Real-time tracking, event-driven callbacks, and statistics
    - Price alignment, concurrent safety, and health metrics
    - Extensible for custom bots and strategy engines

Example Usage:
    ```python
    # V3.1: Order manager is integrated in TradingSuite
    import asyncio
    from project_x_py import TradingSuite


    async def main():
        # All managers are automatically initialized
        suite = await TradingSuite.create("ES")

        # V3.1: Access instrument ID for orders
        contract_id = suite.instrument_id

        # V3.1: Place orders with automatic price alignment
        await suite.orders.place_limit_order(
            contract_id=contract_id,
            side=0,  # Buy
            size=1,
            limit_price=5000.0,
        )

        # V3.1: Monitor order statistics
        stats = await suite.orders.get_order_statistics()
        print(f"Fill rate: {stats['fill_rate']:.1%}")

        await suite.disconnect()


    asyncio.run(main())
    ```

See Also:
    - `order_manager.bracket_orders`
    - `order_manager.position_orders`
    - `order_manager.order_types`
    - `order_manager.tracking`
"""

import asyncio
import time
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Optional

from project_x_py.exceptions import ProjectXOrderError
from project_x_py.models import Order, OrderPlaceResponse
from project_x_py.statistics import BaseStatisticsTracker
from project_x_py.types.config_types import OrderManagerConfig
from project_x_py.types.stats_types import OrderManagerStats
from project_x_py.types.trading import OrderStatus
from project_x_py.utils import (
    ErrorMessages,
    LogContext,
    LogMessages,
    ProjectXLogger,
    format_error_message,
    handle_errors,
    validate_response,
)

from .bracket_orders import BracketOrderMixin
from .error_recovery import OperationRecoveryManager
from .order_types import OrderTypesMixin
from .position_orders import PositionOrderMixin
from .tracking import OrderTrackingMixin
from .utils import (
    align_price_to_tick_size,
    resolve_contract_id,
    validate_price_tick_size,
)

if TYPE_CHECKING:
    from project_x_py.client import ProjectXBase
    from project_x_py.realtime import ProjectXRealtimeClient

logger = ProjectXLogger.get_logger(__name__)


class OrderManager(
    OrderTrackingMixin,
    OrderTypesMixin,
    BracketOrderMixin,
    PositionOrderMixin,
    BaseStatisticsTracker,
):
    """
    Async comprehensive order management system for ProjectX trading operations.

    This class handles all order-related operations including placement, modification,
    cancellation, and tracking using async/await patterns. It integrates with both the
    AsyncProjectX client and the AsyncProjectXRealtimeClient for live order monitoring.

    Features:
        - Complete async order lifecycle management
        - Bracket order strategies with automatic stop/target placement
        - Real-time order status tracking (fills/cancellations detected from status changes)
        - Automatic price alignment to instrument tick sizes
        - OCO (One-Cancels-Other) order support
        - Position-based order management
        - Async-safe operations for concurrent trading
        - Order callback registration for custom event handling
        - Performance optimization with local order caching
        - Comprehensive error handling and validation
        - Thread-safe operations with async locks

    Order Status Enum Values:
        - 0: None (undefined)
        - 1: Open (active order)
        - 2: Filled (completely executed)
        - 3: Cancelled (cancelled by user or system)
        - 4: Expired (timed out)
        - 5: Rejected (rejected by exchange)
        - 6: Pending (awaiting submission)

    Order Side Enum Values:
        - 0: Buy (bid)
        - 1: Sell (ask)

    Order Type Enum Values:
        - 1: Limit
        - 2: Market
        - 3: StopLimit
        - 4: Stop
        - 5: TrailingStop
        - 6: JoinBid (places limit buy at current best bid)
        - 7: JoinAsk (places limit sell at current best ask)

    The OrderManager combines multiple mixins to provide a unified interface for all
    order-related operations, ensuring consistent behavior and comprehensive functionality
    across different order types and strategies.
    """

    def __init__(
        self,
        project_x_client: "ProjectXBase",
        event_bus: Any,
        config: OrderManagerConfig | None = None,
    ):
        """
        Initialize the OrderManager with an ProjectX client and optional configuration.

        Creates a new instance of the OrderManager that uses the provided ProjectX client
        for API access. This establishes the foundation for order operations but does not
        set up real-time capabilities. To enable real-time order tracking, call the `initialize`
        method with a real-time client after initialization.

        Args:
            project_x_client: ProjectX client instance for API access. This client
                should already be authenticated or authentication should be handled
                separately before attempting order operations.
            event_bus: EventBus instance for unified event handling. Required for all
                event emissions including order placements, fills, and cancellations.
            config: Optional configuration for order management behavior. If not provided,
                default values will be used for all configuration options.
        """
        # Initialize mixins and statistics
        OrderTrackingMixin.__init__(self)
        BaseStatisticsTracker.__init__(
            self, component_name="order_manager", max_errors=100, cache_ttl=5.0
        )

        self.project_x = project_x_client
        self.event_bus = event_bus  # Store the event bus for emitting events
        self.logger = ProjectXLogger.get_logger(__name__)

        # Initialize position order tracking
        self.position_orders: dict[str, dict[str, Any]] = {}

        # Store configuration with defaults
        self.config = config or {}
        self._apply_config_defaults()

        # Async lock for thread safety
        self.order_lock = asyncio.Lock()

        # Real-time integration (optional)
        self.realtime_client: ProjectXRealtimeClient | None = None
        self._realtime_enabled = False

        # Comprehensive statistics tracking
        self.stats: dict[str, Any] = {
            "orders_placed": 0,
            "orders_filled": 0,
            "orders_cancelled": 0,
            "orders_rejected": 0,
            "orders_modified": 0,
            "market_orders": 0,
            "limit_orders": 0,
            "stop_orders": 0,
            "bracket_orders": 0,
            "total_volume": 0,
            "total_value": Decimal("0.0"),
            "largest_order": 0,
            "risk_violations": 0,
            "order_validation_failures": 0,
            "last_order_time": None,
            "fill_times_ms": [],
            "order_response_times_ms": [],
        }

        self.logger.info("AsyncOrderManager initialized")

    def _apply_config_defaults(self) -> None:
        """Apply default values for configuration options."""
        # Set default configuration values
        self.enable_bracket_orders = self.config.get("enable_bracket_orders", True)
        self.enable_trailing_stops = self.config.get("enable_trailing_stops", True)
        self.auto_risk_management = self.config.get("auto_risk_management", False)
        self.max_order_size = self.config.get("max_order_size", 1000)
        self.max_orders_per_minute = self.config.get("max_orders_per_minute", 120)
        self.default_order_type = self.config.get("default_order_type", "limit")
        self.enable_order_validation = self.config.get("enable_order_validation", True)
        self.require_confirmation = self.config.get("require_confirmation", False)
        self.auto_cancel_on_close = self.config.get("auto_cancel_on_close", False)
        self.order_timeout_minutes = self.config.get("order_timeout_minutes", 60)

        # Order state validation retry configuration with enhanced defaults
        self.status_check_max_attempts = self.config.get("status_check_max_attempts", 5)
        self.status_check_initial_delay = self.config.get(
            "status_check_initial_delay", 0.5
        )
        self.status_check_backoff_factor = self.config.get(
            "status_check_backoff_factor", 2.0
        )
        self.status_check_max_delay = self.config.get("status_check_max_delay", 30.0)
        self.status_check_circuit_breaker_threshold = self.config.get(
            "status_check_circuit_breaker_threshold", 10
        )
        self.status_check_circuit_breaker_reset_time = self.config.get(
            "status_check_circuit_breaker_reset_time", 300.0
        )

        # Initialize circuit breaker state
        self._circuit_breaker_failure_count = 0
        self._circuit_breaker_last_failure_time = 0.0
        self._circuit_breaker_state = "closed"  # closed, open, half-open

        # Initialize recovery manager for complex operations
        self._recovery_manager: OperationRecoveryManager = OperationRecoveryManager(
            self
        )

    async def initialize(
        self, realtime_client: Optional["ProjectXRealtimeClient"] = None
    ) -> bool:
        """
        Initialize the AsyncOrderManager with optional real-time capabilities.

        This method configures the AsyncOrderManager for operation, optionally enabling
        real-time order status tracking if a realtime client is provided. Real-time
        tracking significantly improves performance by minimizing API calls and
        providing immediate order status updates through websocket connections.

        When real-time tracking is enabled:
        1. Order status changes are detected immediately
        2. Fills, cancellations and rejections are processed in real-time
        3. The order_manager caches order data to reduce API calls
        4. Callbacks can be triggered for custom event handling
        5. WebSocket connections are established for live updates
        6. Order tracking is optimized for minimal latency

        Args:
            realtime_client: Optional AsyncProjectXRealtimeClient for live order tracking.
                If provided, the order manager will connect to the real-time API
                and subscribe to user updates for order status tracking.

        Returns:
            bool: True if initialization successful, False otherwise.

        Note:
            Real-time tracking is highly recommended for production trading as it
            provides immediate order status updates and significantly reduces API
            rate limit consumption.
        """
        try:
            # Set up real-time integration if provided
            if realtime_client:
                self.realtime_client = realtime_client
                await self._setup_realtime_callbacks()

                # Connect and subscribe to user updates for order tracking
                if not realtime_client.user_connected:
                    if await realtime_client.connect():
                        self.logger.info("🔌 Real-time client connected")
                    else:
                        self.logger.warning("⚠️ Real-time client connection failed")
                        return False

                    # Subscribe to user updates to receive order events (only if we just connected)
                    if await realtime_client.subscribe_user_updates():
                        self.logger.info("📡 Subscribed to user order updates")
                    else:
                        self.logger.warning("⚠️ Failed to subscribe to user updates")
                else:
                    self.logger.info(
                        "📡 Real-time client already connected and subscribed"
                    )

                self._realtime_enabled = True
                self.logger.info(
                    "✅ AsyncOrderManager initialized with real-time capabilities"
                )

                # Start memory management cleanup task
                await self._start_cleanup_task()
            else:
                self.logger.info("✅ AsyncOrderManager initialized (polling mode)")

            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to initialize AsyncOrderManager: {e}")
            return False

    @handle_errors("place order")
    @validate_response(required_fields=["success", "orderId"])
    async def place_order(
        self,
        contract_id: str,
        order_type: int,
        side: int,
        size: int,
        limit_price: float | None = None,
        stop_price: float | None = None,
        trail_price: float | None = None,
        custom_tag: str | None = None,
        linked_order_id: int | None = None,
        account_id: int | None = None,
    ) -> OrderPlaceResponse:
        """
        Place an order with comprehensive parameter support and automatic price alignment.

        This is the core order placement method that all specific order type methods use internally.
        It provides complete control over all order parameters and handles automatic price alignment
        to prevent "Invalid price" errors from the exchange. The method is thread-safe and can be
        called concurrently from multiple tasks.

        The method performs several important operations:
        1. Validates all input parameters (size, prices, etc.)
        2. Aligns all prices to the instrument's tick size
        3. Ensures proper account authentication
        4. Places the order via the ProjectX API
        5. Updates internal statistics and tracking
        6. Logs the operation for debugging

        Args:
            contract_id: The contract ID to trade (e.g., "MGC", "MES", "F.US.EP")
            order_type: Order type integer value (1=Limit, 2=Market, 4=Stop, 5=TrailingStop)
            side: Order side integer value: 0=Buy, 1=Sell
            size: Number of contracts to trade (positive integer)
            limit_price: Limit price for limit orders, automatically aligned to tick size.
            stop_price: Stop price for stop orders, automatically aligned to tick size.
            trail_price: Trail amount for trailing stop orders, automatically aligned to tick size.
            custom_tag: Custom identifier for the order (for your reference)
            linked_order_id: ID of a linked order for OCO (One-Cancels-Other) relationships
            account_id: Account ID. Uses default account from authenticated client if None.

        Returns:
            OrderPlaceResponse: Response containing order ID and status information

        Raises:
            ProjectXOrderError: If order placement fails due to invalid parameters or API errors

        Example:
            >>> # V3: Place a limit buy order with automatic price alignment
            >>> response = await om.place_order(
            ...     contract_id="MGC",
            ...     order_type=1,  # Limit order
            ...     side=0,  # Buy
            ...     size=1,
            ...     limit_price=2050.0,  # Automatically aligned to tick size
            ...     custom_tag="my_strategy_001",  # Optional tag for tracking
            ... )
            >>> print(f"Order placed: {response.orderId}")
            >>> print(f"Success: {response.success}")
            >>> # V3: Place a stop loss order
            >>> stop_response = await om.place_order(
            ...     contract_id="MGC",
            ...     order_type=4,  # Stop order
            ...     side=1,  # Sell
            ...     size=1,
            ...     stop_price=2040.0,  # Automatically aligned to tick size
            ... )
        """
        # Add logging context
        with LogContext(
            self.logger,
            operation="place_order",
            contract_id=contract_id,
            order_type=order_type,
            side=side,
            size=size,
            custom_tag=custom_tag,
        ):
            # Validate inputs
            if not isinstance(contract_id, str) or not contract_id:
                raise ProjectXOrderError(
                    format_error_message(
                        ErrorMessages.INSTRUMENT_INVALID_SYMBOL, symbol=contract_id
                    )
                )

            if size <= 0:
                raise ProjectXOrderError(
                    format_error_message(ErrorMessages.ORDER_INVALID_SIZE, size=size)
                )

            # Validate order side and type against expected enums
            if side not in (0, 1):
                raise ProjectXOrderError(
                    format_error_message(ErrorMessages.ORDER_INVALID_SIDE, side=side)
                )

            if order_type not in {1, 2, 3, 4, 5, 6, 7}:
                raise ProjectXOrderError(
                    format_error_message(
                        ErrorMessages.ORDER_INVALID_TYPE, order_type=order_type
                    )
                )

            self.logger.info(
                LogMessages.ORDER_PLACE,
                extra={
                    "contract_id": contract_id,
                    "order_type": order_type,
                    "side": side,
                    "size": size,
                    "limit_price": limit_price,
                    "stop_price": stop_price,
                },
            )

            # Validate size
            if size <= 0:
                raise ProjectXOrderError(f"Invalid order size: {size}")

            # Validate prices are positive
            if limit_price is not None and limit_price < 0:
                raise ProjectXOrderError(f"Invalid negative price: {limit_price}")
            if stop_price is not None and stop_price < 0:
                raise ProjectXOrderError(f"Invalid negative price: {stop_price}")
            if trail_price is not None and trail_price < 0:
                raise ProjectXOrderError(f"Invalid negative price: {trail_price}")

            # CRITICAL: Validate tick size BEFORE any price operations
            await validate_price_tick_size(
                limit_price, contract_id, self.project_x, "limit_price"
            )
            await validate_price_tick_size(
                stop_price, contract_id, self.project_x, "stop_price"
            )
            await validate_price_tick_size(
                trail_price, contract_id, self.project_x, "trail_price"
            )

            # Convert prices to Decimal for precision, then align to tick size
            decimal_limit_price = (
                Decimal(str(limit_price)) if limit_price is not None else None
            )
            decimal_stop_price = (
                Decimal(str(stop_price)) if stop_price is not None else None
            )
            decimal_trail_price = (
                Decimal(str(trail_price)) if trail_price is not None else None
            )

            # Align all prices to tick size to prevent "Invalid price" errors
            aligned_limit_price = await align_price_to_tick_size(
                float(decimal_limit_price) if decimal_limit_price is not None else None,
                contract_id,
                self.project_x,
            )
            aligned_stop_price = await align_price_to_tick_size(
                float(decimal_stop_price) if decimal_stop_price is not None else None,
                contract_id,
                self.project_x,
            )
            aligned_trail_price = await align_price_to_tick_size(
                float(decimal_trail_price) if decimal_trail_price is not None else None,
                contract_id,
                self.project_x,
            )

            # Use account_info if no account_id provided
            if account_id is None:
                if not self.project_x.account_info:
                    raise ProjectXOrderError(ErrorMessages.ORDER_NO_ACCOUNT)
                account_id = self.project_x.account_info.id
            else:
                # Validate that the provided account_id matches the authenticated account
                if (
                    self.project_x.account_info
                    and account_id != self.project_x.account_info.id
                ):
                    raise ProjectXOrderError(
                        f"Invalid account ID {account_id}. Expected {self.project_x.account_info.id}"
                    )

            # Build order request payload
            payload = {
                "accountId": account_id,
                "contractId": contract_id,
                "type": order_type,
                "side": side,
                "size": size,
                "limitPrice": aligned_limit_price,
                "stopPrice": aligned_stop_price,
                "trailPrice": aligned_trail_price,
                "linkedOrderId": linked_order_id,
            }

            # Only include customTag if it's provided and not None/empty
            if custom_tag:
                payload["customTag"] = custom_tag

            # Place the order with timing
            start_time = time.time()
            response = await self.project_x._make_request(
                "POST", "/Order/place", data=payload
            )
            duration_ms = (time.time() - start_time) * 1000

            # Response should be a dict for order placement
            if not isinstance(response, dict):
                error = ProjectXOrderError("Invalid response format")
                # Track error without holding locks
                await self.track_error(
                    error, "place_order", {"contract_id": contract_id, "side": side}
                )
                await self.record_timing("place_order", duration_ms)
                raise error

            if not response.get("success", False):
                error_msg = response.get("errorMessage", ErrorMessages.ORDER_FAILED)
                error = ProjectXOrderError(error_msg)
                # Track error without holding locks
                await self.track_error(
                    error, "place_order", {"contract_id": contract_id, "side": side}
                )
                await self.record_timing("place_order", duration_ms)
                raise error

            result = OrderPlaceResponse(
                orderId=response.get("orderId", 0),
                success=response.get("success", False),
                errorCode=response.get("errorCode", ""),
                errorMessage=response.get("errorMessage", ""),
            )

            # Track successful operation without holding locks
            await self.record_timing("place_order", duration_ms)
            await self.increment("successful_operations")
            await self.set_gauge("last_order_size", size)
            await self.set_gauge("last_order_type", order_type)

            # Update statistics with order_lock
            async with self.order_lock:
                # Update legacy stats dict for backward compatibility
                self.stats["orders_placed"] += 1
                self.stats["last_order_time"] = datetime.now()
                self.stats["total_volume"] += size
                if size > self.stats["largest_order"]:
                    self.stats["largest_order"] = size

                # Update order type specific statistics
                from project_x_py.types.trading import OrderType

                if order_type == OrderType.LIMIT:
                    self.stats["limit_orders"] += 1
                elif order_type == OrderType.MARKET:
                    self.stats["market_orders"] += 1
                elif order_type == OrderType.STOP or order_type == OrderType.STOP_LIMIT:
                    self.stats["stop_orders"] += 1

                # Update new statistics system
                await self.increment("orders_placed")
                await self.increment("total_volume", size)
                await self.set_gauge("last_order_timestamp", time.time())

                # Calculate order value with Decimal precision if limit price available
                if aligned_limit_price is not None:
                    order_value = Decimal(str(aligned_limit_price)) * Decimal(str(size))
                    current_total_value = self.stats.get("total_value", Decimal("0.0"))
                    if isinstance(current_total_value, int | float):
                        current_total_value = Decimal(str(current_total_value))
                    self.stats["total_value"] = current_total_value + order_value

                # Check if this is the largest order
                if size > self.stats.get("largest_order", 0):
                    await self.set_gauge("largest_order", size)

                self.logger.info(
                    LogMessages.ORDER_PLACED,
                    extra={
                        "order_id": result.orderId,
                        "contract_id": contract_id,
                        "side": side,
                        "size": size,
                    },
                )

                # Emit order placed event
                await self._trigger_callbacks(
                    "order_placed",
                    {
                        "order_id": result.orderId,
                        "contract_id": contract_id,
                        "order_type": order_type,
                        "side": side,
                        "size": size,
                        "limit_price": aligned_limit_price,
                        "stop_price": aligned_stop_price,
                        "trail_price": aligned_trail_price,
                        "custom_tag": custom_tag,
                        "response": result,
                    },
                )

                return result

    @handle_errors("search open orders")
    async def search_open_orders(
        self,
        contract_id: str | None = None,
        side: int | None = None,
        account_id: int | None = None,
    ) -> list[Order]:
        """
        Search for open orders with optional filters.

        Args:
            contract_id: Filter by instrument (optional)
            side: Filter by side 0=Buy, 1=Sell (optional)

        Returns:
            List of Order objects
        """
        if not self.project_x.account_info:
            raise ProjectXOrderError(ErrorMessages.ORDER_NO_ACCOUNT)

        # Use provided account_id or default to current account
        if account_id is not None:
            params = {"accountId": account_id}
        else:
            params = {"accountId": self.project_x.account_info.id}

        if contract_id:
            # Resolve contract
            resolved = await resolve_contract_id(contract_id, self.project_x)
            if resolved and resolved.get("id"):
                params["contractId"] = resolved["id"]

        if side is not None:
            params["side"] = side

        # Retry logic for network failures
        max_retries = 3
        retry_delay = 0.1

        for attempt in range(max_retries):
            try:
                response = await self.project_x._make_request(
                    "POST", "/Order/searchOpen", data=params
                )
                break  # Success, exit retry loop
            except Exception:
                if attempt < max_retries - 1:
                    await asyncio.sleep(
                        retry_delay * (2**attempt)
                    )  # Exponential backoff
                    continue
                else:
                    # Final attempt failed, re-raise
                    raise

        # Response should be a dict for order search
        if not isinstance(response, dict):
            raise ProjectXOrderError("Invalid response format")

        if not response.get("success", False):
            error_msg = response.get("errorMessage", ErrorMessages.ORDER_SEARCH_FAILED)
            raise ProjectXOrderError(error_msg)

        orders = response.get("orders", [])
        # Filter to only include fields that Order model expects
        open_orders = []
        for order_data in orders:
            try:
                order = Order(**order_data)
                open_orders.append(order)

                # Update our cache
                async with self.order_lock:
                    self.tracked_orders[str(order.id)] = order_data
                    self.order_status_cache[str(order.id)] = order.status
            except Exception as e:
                self.logger.warning(
                    "Failed to parse order",
                    extra={"error": str(e), "order_data": order_data},
                )
                continue

        return open_orders

    async def _check_circuit_breaker(self) -> bool:
        """
        Check if circuit breaker allows execution.

        Returns:
            bool: True if request is allowed, False if circuit is open
        """
        current_time = time.time()

        if self._circuit_breaker_state == "open":
            # Check if enough time has passed to attempt reset
            if (
                current_time - self._circuit_breaker_last_failure_time
                >= self.status_check_circuit_breaker_reset_time
            ):
                self._circuit_breaker_state = "half-open"
                self.logger.info("Circuit breaker transitioning to half-open state")
                return True
            return False

        return True

    async def _record_circuit_breaker_success(self) -> None:
        """
        Record successful operation, potentially closing the circuit.
        """
        if self._circuit_breaker_state == "half-open":
            self._circuit_breaker_state = "closed"
            self._circuit_breaker_failure_count = 0
            self.logger.info("Circuit breaker closed after successful operation")

    async def _record_circuit_breaker_failure(self) -> None:
        """
        Record failed operation, potentially opening the circuit.
        """
        self._circuit_breaker_failure_count += 1
        self._circuit_breaker_last_failure_time = time.time()

        if (
            self._circuit_breaker_failure_count
            >= self.status_check_circuit_breaker_threshold
            and self._circuit_breaker_state != "open"
        ):
            self._circuit_breaker_state = "open"
            self.logger.error(
                f"Circuit breaker opened after {self._circuit_breaker_failure_count} failures"
            )

    async def is_order_filled(self, order_id: str | int) -> bool:
        """
        Check if an order has been filled using cached data with API fallback.

        Features enhanced configurable retry logic with exponential backoff,
        circuit breaker pattern for repeated failures, and intelligent market
        condition adaptation.

        Efficiently checks order fill status by first consulting the real-time
        cache (if available) before falling back to API queries with robust
        retry mechanisms optimized for different network latency scenarios.

        Args:
            order_id: Order ID to check (accepts both string and integer)

        Returns:
            bool: True if order status is 2 (Filled), False otherwise
        """
        order_id_str = str(order_id)

        # Check circuit breaker before attempting operations
        if not await self._check_circuit_breaker():
            self.logger.warning(
                f"Circuit breaker is open, skipping order status check for {order_id_str}"
            )
            # Return False to indicate we couldn't verify the order status
            return False

        # Try cached data first with configurable retry for real-time updates
        if self._realtime_enabled:
            for attempt in range(self.status_check_max_attempts):
                try:
                    async with self.order_lock:
                        status = self.order_status_cache.get(order_id_str)
                        if status is not None:
                            await self._record_circuit_breaker_success()
                            return bool(status == OrderStatus.FILLED)

                    if attempt < self.status_check_max_attempts - 1:
                        # Calculate exponential backoff delay with jitter
                        delay = min(
                            self.status_check_initial_delay
                            * (self.status_check_backoff_factor**attempt),
                            self.status_check_max_delay,
                        )
                        # Add small jitter to prevent thundering herd
                        jitter = (
                            delay * 0.1 * (0.5 - asyncio.get_event_loop().time() % 1)
                        )
                        final_delay = max(0.1, delay + jitter)

                        self.logger.debug(
                            f"Retrying order status check for {order_id_str} in {final_delay:.2f}s "
                            f"(attempt {attempt + 1}/{self.status_check_max_attempts})"
                        )
                        await asyncio.sleep(final_delay)

                except Exception as e:
                    self.logger.warning(
                        f"Error checking cached order status for {order_id_str} "
                        f"(attempt {attempt + 1}): {e}"
                    )
                    await self._record_circuit_breaker_failure()

                    if attempt < self.status_check_max_attempts - 1:
                        delay = min(
                            self.status_check_initial_delay
                            * (self.status_check_backoff_factor**attempt),
                            self.status_check_max_delay,
                        )
                        await asyncio.sleep(delay)

        # Fallback to API check with retry logic
        last_exception = None
        for attempt in range(self.status_check_max_attempts):
            try:
                order = await self.get_order_by_id(int(order_id))
                await self._record_circuit_breaker_success()
                return order is not None and order.status == OrderStatus.FILLED

            except Exception as e:
                last_exception = e
                await self._record_circuit_breaker_failure()

                if attempt < self.status_check_max_attempts - 1:
                    delay = min(
                        self.status_check_initial_delay
                        * (self.status_check_backoff_factor**attempt),
                        self.status_check_max_delay,
                    )
                    # Add jitter for API calls to prevent rate limiting
                    jitter = delay * 0.2 * (0.5 - time.time() % 1)
                    final_delay = max(0.5, delay + jitter)

                    self.logger.warning(
                        f"API order status check failed for {order_id_str} "
                        f"(attempt {attempt + 1}/{self.status_check_max_attempts}): {e}. "
                        f"Retrying in {final_delay:.2f}s"
                    )
                    await asyncio.sleep(final_delay)
                else:
                    self.logger.error(
                        f"All {self.status_check_max_attempts} attempts failed for order {order_id_str}. "
                        f"Last error: {e}"
                    )

        # If we get here, all attempts failed
        if last_exception:
            self.logger.error(
                f"Unable to determine order status for {order_id_str} after "
                f"{self.status_check_max_attempts} attempts"
            )

        # Return False to indicate we couldn't verify the order is filled
        return False

    async def get_order_by_id(self, order_id: int) -> Order | None:
        """
        Get detailed order information by ID using cached data with API fallback.

        Args:
            order_id: Order ID to retrieve

        Returns:
            Order object with full details or None if not found
        """
        order_id_str = str(order_id)

        # Try cached data first (realtime optimization)
        if self._realtime_enabled:
            order_data = await self.get_tracked_order_status(order_id_str)
            if order_data:
                try:
                    return Order(**order_data)
                except Exception as e:
                    self.logger.debug(f"Failed to parse cached order data: {e}")

        # Fallback to API search
        try:
            orders = await self.search_open_orders()
            for order in orders:
                if order.id == order_id:
                    return order
            return None
        except Exception as e:
            self.logger.error(f"Failed to get order {order_id}: {e}")
            return None

    @handle_errors("cancel order")
    async def cancel_order(self, order_id: int, account_id: int | None = None) -> bool:
        """
        Cancel an open order.

        Args:
            order_id: Order ID to cancel
            account_id: Account ID. Uses default account if None.

        Returns:
            True if cancellation successful
        """
        self.logger.info(LogMessages.ORDER_CANCEL, extra={"order_id": order_id})

        async with self.order_lock:
            # Check if order is already filled
            order_id_str = str(order_id)
            if order_id_str in self.order_status_cache:
                status = self.order_status_cache[order_id_str]
                if status == OrderStatus.FILLED or status == 2:  # 2 is FILLED
                    raise ProjectXOrderError(
                        f"Cannot cancel order {order_id}: already filled"
                    )

            # Also check tracked orders
            if order_id_str in self.tracked_orders:
                tracked = self.tracked_orders[order_id_str]
                if (
                    tracked.get("status") == OrderStatus.FILLED
                    or tracked.get("status") == 2
                ):
                    raise ProjectXOrderError(
                        f"Cannot cancel order {order_id}: already filled"
                    )

            # Get account ID if not provided
            if account_id is None:
                if not self.project_x.account_info:
                    await self.project_x.authenticate()
                if not self.project_x.account_info:
                    raise ProjectXOrderError(ErrorMessages.ORDER_NO_ACCOUNT)
                account_id = self.project_x.account_info.id

            # Use correct endpoint and payload structure
            payload = {
                "accountId": account_id,
                "orderId": order_id,
            }

            response = await self.project_x._make_request(
                "POST", "/Order/cancel", data=payload
            )

            # Response should be a dict
            if not isinstance(response, dict):
                raise ProjectXOrderError("Invalid response format")

            success = response.get("success", False) if response else False

            if success:
                # Update cache
                if str(order_id) in self.tracked_orders:
                    self.tracked_orders[str(order_id)]["status"] = OrderStatus.CANCELLED
                    self.order_status_cache[str(order_id)] = OrderStatus.CANCELLED

                # Update statistics
                await self.increment("orders_cancelled")
                self.stats["orders_cancelled"] += 1
                self.logger.info(
                    LogMessages.ORDER_CANCELLED, extra={"order_id": order_id}
                )
                return True
            else:
                error_msg = response.get(
                    "errorMessage", ErrorMessages.ORDER_CANCEL_FAILED
                )
                raise ProjectXOrderError(
                    format_error_message(
                        ErrorMessages.ORDER_CANCEL_FAILED,
                        order_id=order_id,
                        reason=error_msg,
                    )
                )

    @handle_errors("modify order")
    async def modify_order(
        self,
        order_id: int,
        limit_price: float | None = None,
        stop_price: float | None = None,
        size: int | None = None,
    ) -> bool:
        """
        Modify an existing order.

        Args:
            order_id: Order ID to modify
            limit_price: New limit price (optional)
            stop_price: New stop price (optional)
            size: New order size (optional)

        Returns:
            True if modification successful
        """
        with LogContext(
            self.logger,
            operation="modify_order",
            order_id=order_id,
            has_limit=limit_price is not None,
            has_stop=stop_price is not None,
            has_size=size is not None,
        ):
            self.logger.info(LogMessages.ORDER_MODIFY, extra={"order_id": order_id})

            # Get existing order details to determine contract_id for price alignment
            existing_order = await self.get_order_by_id(order_id)
            if not existing_order:
                raise ProjectXOrderError(
                    format_error_message(
                        ErrorMessages.ORDER_NOT_FOUND, order_id=order_id
                    )
                )

            contract_id = existing_order.contractId

            # CRITICAL: Validate tick size BEFORE any price operations
            await validate_price_tick_size(
                limit_price, contract_id, self.project_x, "limit_price"
            )
            await validate_price_tick_size(
                stop_price, contract_id, self.project_x, "stop_price"
            )

            # Convert prices to Decimal for precision, then align to tick size
            decimal_limit = (
                Decimal(str(limit_price)) if limit_price is not None else None
            )
            decimal_stop = Decimal(str(stop_price)) if stop_price is not None else None

            # Align prices to tick size
            aligned_limit = await align_price_to_tick_size(
                float(decimal_limit) if decimal_limit is not None else None,
                contract_id,
                self.project_x,
            )
            aligned_stop = await align_price_to_tick_size(
                float(decimal_stop) if decimal_stop is not None else None,
                contract_id,
                self.project_x,
            )

            # Build modification request
            payload: dict[str, Any] = {
                "accountId": self.project_x.account_info.id
                if self.project_x.account_info
                else None,
                "orderId": order_id,
            }

            # Add only the fields that are being modified
            if aligned_limit is not None:
                payload["limitPrice"] = aligned_limit
            if aligned_stop is not None:
                payload["stopPrice"] = aligned_stop
            if size is not None:
                payload["size"] = size

            if len(payload) <= 2:  # Only accountId and orderId
                self.logger.info("No changes specified for order modification")
                return True  # No-op, consider it successful

            # Modify order
            response = await self.project_x._make_request(
                "POST", "/Order/modify", data=payload
            )

            # Response should be a dict
            if not isinstance(response, dict):
                raise ProjectXOrderError("Invalid response format")

            if response and response.get("success", False):
                # Update statistics
                await self.increment("orders_modified")
                async with self.order_lock:
                    self.stats["orders_modified"] += 1

                self.logger.info(
                    LogMessages.ORDER_MODIFIED, extra={"order_id": order_id}
                )

                # Emit order modified event
                await self._trigger_callbacks(
                    "order_modified",
                    {
                        "order_id": order_id,
                        "modifications": {
                            "limit_price": aligned_limit,
                            "stop_price": aligned_stop,
                            "size": size,
                        },
                    },
                )

                return True
            else:
                error_msg = (
                    response.get("errorMessage", ErrorMessages.ORDER_MODIFY_FAILED)
                    if response
                    else ErrorMessages.ORDER_MODIFY_FAILED
                )
                raise ProjectXOrderError(
                    format_error_message(
                        ErrorMessages.ORDER_MODIFY_FAILED,
                        order_id=order_id,
                        reason=error_msg,
                    )
                )

    @handle_errors("cancel all orders")
    async def cancel_all_orders(
        self, contract_id: str | None = None, account_id: int | None = None
    ) -> dict[str, Any]:
        """
        Cancel all open orders, optionally filtered by contract.

        Args:
            contract_id: Optional contract ID to filter orders
            account_id: Account ID. Uses default account if None.

        Returns:
            Dict with cancellation results
        """
        with LogContext(
            self.logger,
            operation="cancel_all_orders",
            contract_id=contract_id,
            account_id=account_id,
        ):
            self.logger.info(
                LogMessages.ORDER_CANCEL_ALL, extra={"contract_id": contract_id}
            )

            orders = await self.search_open_orders(contract_id, account_id)

            results: dict[str, Any] = {
                "total": len(orders),
                "cancelled": 0,
                "failed": 0,
                "errors": [],
            }

            for order in orders:
                try:
                    if await self.cancel_order(order.id, account_id):
                        results["cancelled"] += 1
                    else:
                        results["failed"] += 1
                except Exception as e:
                    results["failed"] += 1
                    results["errors"].append({"order_id": order.id, "error": str(e)})

            self.logger.info(
                LogMessages.ORDER_CANCEL_ALL_COMPLETE,
                extra={
                    "total": results["total"],
                    "cancelled": results["cancelled"],
                    "failed": results["failed"],
                },
            )

            return results

    def _get_recovery_manager(self) -> OperationRecoveryManager:
        """Get the recovery manager instance for complex operations."""
        return self._recovery_manager

    def get_recovery_statistics(self) -> dict[str, Any]:
        """
        Get comprehensive recovery statistics.

        Returns:
            Dictionary with recovery statistics and system health
        """
        return self._recovery_manager.get_recovery_statistics()

    async def get_operation_status(self, operation_id: str) -> dict[str, Any] | None:
        """
        Get status of a recovery operation.

        Args:
            operation_id: ID of the operation to check

        Returns:
            Dictionary with operation status or None if not found
        """
        return self._recovery_manager.get_operation_status(operation_id)

    async def force_rollback_operation(self, operation_id: str) -> bool:
        """
        Force rollback of an active operation.

        Args:
            operation_id: ID of the operation to rollback

        Returns:
            True if rollback was initiated, False if operation not found
        """
        return await self._recovery_manager.force_rollback_operation(operation_id)

    async def cleanup_stale_operations(self, max_age_hours: float = 24.0) -> int:
        """
        Clean up stale recovery operations.

        Args:
            max_age_hours: Maximum age in hours for active operations

        Returns:
            Number of operations cleaned up
        """
        return await self._recovery_manager.cleanup_stale_operations(max_age_hours)

    def get_circuit_breaker_status(self) -> dict[str, Any]:
        """
        Get current circuit breaker status and statistics.

        Returns:
            dict: Circuit breaker statistics including state, failure count,
                  last failure time, and configuration parameters
        """
        return {
            "state": self._circuit_breaker_state,
            "failure_count": self._circuit_breaker_failure_count,
            "last_failure_time": self._circuit_breaker_last_failure_time,
            "threshold": self.status_check_circuit_breaker_threshold,
            "reset_time_seconds": self.status_check_circuit_breaker_reset_time,
            "time_until_reset": max(
                0,
                self.status_check_circuit_breaker_reset_time
                - (time.time() - self._circuit_breaker_last_failure_time),
            )
            if self._circuit_breaker_state == "open"
            else 0,
            "is_healthy": self._circuit_breaker_state != "open",
            "retry_config": {
                "max_attempts": self.status_check_max_attempts,
                "initial_delay": self.status_check_initial_delay,
                "backoff_factor": self.status_check_backoff_factor,
                "max_delay": self.status_check_max_delay,
            },
        }

    async def get_order_statistics_async(self) -> dict[str, Any]:
        """
        Get comprehensive async order management statistics using the new statistics system.

        Returns:
            OrderManagerStats with complete metrics
        """
        # Get base statistics from the new system
        base_stats = await self.get_stats()

        # Get performance metrics
        health_score = await self.get_health_score()

        # Get error information
        error_count = await self.get_error_count()
        recent_errors = await self.get_recent_errors(5)

        # Make quick copies of legacy stats for backward compatibility
        stats_copy = dict(self.stats)
        _tracked_orders_count = len(self.tracked_orders)

        # Count position-order relationships
        total_position_orders = 0
        position_summary = {}
        for contract_id, orders in self.position_orders.items():
            entry_count = len(orders["entry_orders"])
            stop_count = len(orders["stop_orders"])
            target_count = len(orders["target_orders"])
            total_count = entry_count + stop_count + target_count

            if total_count > 0:
                total_position_orders += total_count
                position_summary[contract_id] = {
                    "entry": entry_count,
                    "stop": stop_count,
                    "target": target_count,
                    "total": total_count,
                }

        # Calculate performance metrics
        fill_rate = (
            stats_copy["orders_filled"] / stats_copy["orders_placed"]
            if stats_copy["orders_placed"] > 0
            else 0.0
        )

        rejection_rate = (
            stats_copy["orders_rejected"] / stats_copy["orders_placed"]
            if stats_copy["orders_placed"] > 0
            else 0.0
        )

        # Calculate basic timing metrics
        avg_order_response_time_ms = (
            sum(stats_copy["order_response_times_ms"])
            / len(stats_copy["order_response_times_ms"])
            if stats_copy["order_response_times_ms"]
            else 0.0
        )

        avg_fill_time_ms = (
            sum(stats_copy["fill_times_ms"]) / len(stats_copy["fill_times_ms"])
            if stats_copy["fill_times_ms"]
            else 0.0
        )
        fastest_fill_ms = (
            min(stats_copy["fill_times_ms"]) if stats_copy["fill_times_ms"] else 0.0
        )
        slowest_fill_ms = (
            max(stats_copy["fill_times_ms"]) if stats_copy["fill_times_ms"] else 0.0
        )

        # Ensure total_value is Decimal for precise calculations
        total_value = stats_copy["total_value"]
        if not isinstance(total_value, Decimal):
            total_value = Decimal(str(total_value))

        avg_order_size = (
            stats_copy["total_volume"] / stats_copy["orders_placed"]
            if stats_copy["orders_placed"] > 0
            else 0.0
        )

        return {
            "orders_placed": stats_copy["orders_placed"],
            "orders_filled": stats_copy["orders_filled"],
            "orders_cancelled": stats_copy["orders_cancelled"],
            "orders_rejected": stats_copy["orders_rejected"],
            "orders_modified": stats_copy["orders_modified"],
            # Performance metrics
            "fill_rate": fill_rate,
            "avg_fill_time_ms": avg_fill_time_ms,
            "rejection_rate": rejection_rate,
            # Order types
            "market_orders": stats_copy["market_orders"],
            "limit_orders": stats_copy["limit_orders"],
            "stop_orders": stats_copy["stop_orders"],
            "bracket_orders": stats_copy["bracket_orders"],
            # Timing statistics
            "last_order_time": stats_copy["last_order_time"].isoformat()
            if stats_copy["last_order_time"]
            else None,
            "avg_order_response_time_ms": avg_order_response_time_ms,
            "fastest_fill_ms": fastest_fill_ms,
            "slowest_fill_ms": slowest_fill_ms,
            # Volume and value
            "total_volume": stats_copy["total_volume"],
            "total_value": float(total_value),
            "avg_order_size": avg_order_size,
            "largest_order": stats_copy["largest_order"],
            # Risk metrics
            "risk_violations": stats_copy["risk_violations"],
            "order_validation_failures": stats_copy["order_validation_failures"],
            # New metrics from v3.3.0 statistics system
            "health_score": health_score,
            "error_count": error_count,
            "recent_errors": recent_errors,
            "component_stats": base_stats,
        }

    def get_order_statistics(self) -> OrderManagerStats:
        """
        Get comprehensive order management statistics and system health information.

        Provides detailed metrics about order activity, real-time tracking status,
        position-order relationships, and system health for monitoring and debugging.

        Returns:
            Dict with complete statistics
        """
        # Note: This is now synchronous but thread-safe
        # We make quick copies to minimize time accessing shared data

        # Make a copy of stats to work with
        stats_copy = dict(self.stats)

        # Use internal order tracking
        _tracked_orders_count = len(self.tracked_orders)

        # Count position-order relationships
        total_position_orders = 0
        position_summary = {}
        for contract_id, orders in self.position_orders.items():
            entry_count = len(orders["entry_orders"])
            stop_count = len(orders["stop_orders"])
            target_count = len(orders["target_orders"])
            total_count = entry_count + stop_count + target_count

            if total_count > 0:
                total_position_orders += total_count
                position_summary[contract_id] = {
                    "entry": entry_count,
                    "stop": stop_count,
                    "target": target_count,
                    "total": total_count,
                }

        # Now calculate metrics
        # Calculate performance metrics
        fill_rate = (
            stats_copy["orders_filled"] / stats_copy["orders_placed"]
            if stats_copy["orders_placed"] > 0
            else 0.0
        )

        rejection_rate = (
            stats_copy["orders_rejected"] / stats_copy["orders_placed"]
            if stats_copy["orders_placed"] > 0
            else 0.0
        )

        # Calculate basic timing metrics
        avg_order_response_time_ms = (
            sum(stats_copy["order_response_times_ms"])
            / len(stats_copy["order_response_times_ms"])
            if stats_copy["order_response_times_ms"]
            else 0.0
        )

        avg_fill_time_ms = (
            sum(stats_copy["fill_times_ms"]) / len(stats_copy["fill_times_ms"])
            if stats_copy["fill_times_ms"]
            else 0.0
        )
        fastest_fill_ms = (
            min(stats_copy["fill_times_ms"]) if stats_copy["fill_times_ms"] else 0.0
        )
        slowest_fill_ms = (
            max(stats_copy["fill_times_ms"]) if stats_copy["fill_times_ms"] else 0.0
        )

        # Ensure total_value is Decimal for precise calculations in synchronous method
        total_value_sync = stats_copy["total_value"]
        if not isinstance(total_value_sync, Decimal):
            total_value_sync = Decimal(str(total_value_sync))

        avg_order_size = (
            stats_copy["total_volume"] / stats_copy["orders_placed"]
            if stats_copy["orders_placed"] > 0
            else 0.0
        )

        return {
            "orders_placed": stats_copy["orders_placed"],
            "orders_filled": stats_copy["orders_filled"],
            "orders_cancelled": stats_copy["orders_cancelled"],
            "orders_rejected": stats_copy["orders_rejected"],
            "orders_modified": stats_copy["orders_modified"],
            # Performance metrics
            "fill_rate": fill_rate,
            "avg_fill_time_ms": avg_fill_time_ms,
            "rejection_rate": rejection_rate,
            # Order types
            "market_orders": stats_copy["market_orders"],
            "limit_orders": stats_copy["limit_orders"],
            "stop_orders": stats_copy["stop_orders"],
            "bracket_orders": stats_copy["bracket_orders"],
            # Timing statistics
            "last_order_time": stats_copy["last_order_time"].isoformat()
            if stats_copy["last_order_time"]
            else None,
            "avg_order_response_time_ms": avg_order_response_time_ms,
            "fastest_fill_ms": fastest_fill_ms,
            "slowest_fill_ms": slowest_fill_ms,
            # Volume and value
            "total_volume": stats_copy["total_volume"],
            "total_value": float(total_value_sync),
            "avg_order_size": avg_order_size,
            "largest_order": stats_copy["largest_order"],
            # Risk metrics
            "risk_violations": stats_copy["risk_violations"],
            "order_validation_failures": stats_copy["order_validation_failures"],
        }

    async def cleanup(self) -> None:
        """Clean up resources and connections."""
        self.logger.info("Cleaning up AsyncOrderManager resources")

        # Stop memory management cleanup task
        await self._stop_cleanup_task()

        # Clean up recovery manager operations
        try:
            stale_count = await self.cleanup_stale_operations(
                max_age_hours=0.1
            )  # Clean up very recent operations too
            if stale_count > 0:
                self.logger.info(f"Cleaned up {stale_count} stale recovery operations")
        except Exception as e:
            self.logger.error(f"Error cleaning up recovery operations: {e}")

        # Clear all tracking data
        self.clear_order_tracking()

        # Clean up realtime client if it exists
        if self.realtime_client:
            try:
                await self.realtime_client.disconnect()
            except Exception as e:
                self.logger.error(f"Error disconnecting realtime client: {e}")

        self.logger.info("AsyncOrderManager cleanup complete")

    async def _should_attempt_circuit_breaker_recovery(self) -> bool:
        """Check if enough time has passed to attempt circuit breaker recovery."""
        if self._circuit_breaker_state != "open":
            return False

        time_since_failure = time.time() - self._circuit_breaker_last_failure_time
        return time_since_failure >= self.status_check_circuit_breaker_reset_time

    async def get_health_status(self) -> dict[str, Any]:
        """Get comprehensive health status of the order manager."""
        total_orders = self.stats.get("orders_placed", 0)
        filled_orders = self.stats.get("orders_filled", 0)
        rejected_orders = self.stats.get("orders_rejected", 0)

        fill_rate = filled_orders / total_orders if total_orders > 0 else 0.0
        rejection_rate = rejected_orders / total_orders if total_orders > 0 else 0.0

        health: dict[str, Any] = {
            "status": "healthy",
            "metrics": {
                "fill_rate": fill_rate,
                "rejection_rate": rejection_rate,
                "total_orders": total_orders,
                "orders_filled": filled_orders,
                "orders_rejected": rejected_orders,
            },
            "circuit_breaker_state": self._circuit_breaker_state,
            "issues": [],
        }

        # Determine health status
        if self._circuit_breaker_state == "open":
            health["status"] = "unhealthy"
            health["issues"].append("circuit_breaker_open")

        if rejection_rate > 0.2:  # More than 20% rejection rate
            health["status"] = "unhealthy"
            health["issues"].append("high_rejection_rate")
        elif rejection_rate > 0.1:  # More than 10% rejection rate
            health["status"] = (
                "degraded" if health["status"] == "healthy" else health["status"]
            )
            health["issues"].append("elevated_rejection_rate")

        if fill_rate < 0.5 and total_orders > 10:  # Less than 50% fill rate
            health["status"] = (
                "degraded" if health["status"] == "healthy" else health["status"]
            )
            health["issues"].append("low_fill_rate")

        return health

    async def _update_order_statistics_on_fill(
        self, order_data: dict[str, Any]
    ) -> None:
        """Update statistics when an order fills."""
        self.stats["orders_filled"] += 1

        if "size" in order_data:
            self.stats["total_volume"] += order_data["size"]

        if "limitPrice" in order_data or "limit_price" in order_data:
            price = order_data.get("limitPrice", order_data.get("limit_price", 0))
            if price and "size" in order_data:
                value = Decimal(str(price)) * order_data["size"]
                self.stats["total_value"] += value

    async def _cleanup_old_orders(self) -> None:
        """Clean up old completed orders from tracking."""
        current_time = time.time()
        cutoff_time = current_time - 3600  # Keep orders for 1 hour

        orders_to_remove = []
        for order_id, order_data in self.tracked_orders.items():
            # Keep open orders regardless of age
            if order_data.get("status") in [OrderStatus.OPEN, OrderStatus.PENDING]:
                continue

            # Remove old completed orders
            if order_data.get("timestamp", current_time) < cutoff_time:
                orders_to_remove.append(order_id)

        for order_id in orders_to_remove:
            self.tracked_orders.pop(order_id, None)
            self.order_status_cache.pop(order_id, None)

        if orders_to_remove:
            self.logger.debug(f"Cleaned up {len(orders_to_remove)} old orders")
