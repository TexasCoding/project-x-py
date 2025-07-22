#!/usr/bin/env python3
"""
OrderManager for Comprehensive Order Operations

Author: TexasCoding
Date: June 2025

This module provides comprehensive order management capabilities for the ProjectX API:
1. Order placement (market, limit, stop, trailing stop, bracket orders)
2. Order modification and cancellation
3. Order status tracking and search
4. Automatic price alignment to tick sizes
5. Real-time order monitoring integration
6. Advanced order types (OCO, bracket, conditional)

Key Features:
- Thread-safe order operations
- Dependency injection with ProjectX client
- Integration with ProjectXRealtimeClient for live updates
- Automatic price alignment and validation
- Comprehensive error handling and retry logic
- Support for complex order strategies

Architecture:
- Similar to OrderBook and ProjectXRealtimeDataManager
- Clean separation from main client class
- Real-time order tracking capabilities
- Event-driven order status updates
"""

import json
import logging
import threading
from collections import defaultdict
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, Any, Optional

import requests

from .exceptions import (
    ProjectXConnectionError,
    ProjectXDataError,
    ProjectXOrderError,
)
from .models import (
    BracketOrderResponse,
    Order,
    OrderPlaceResponse,
)
from .utils import extract_symbol_from_contract_id

if TYPE_CHECKING:
    from .client import ProjectX
    from .realtime import ProjectXRealtimeClient


class OrderManager:
    """
    Comprehensive order management system for ProjectX trading operations.

    This class handles all order-related operations including placement, modification,
    cancellation, and tracking. It integrates with both the ProjectX API client and
    the real-time client for live order monitoring.

    Features:
        - Complete order lifecycle management
        - Bracket order strategies with automatic stop/target placement
        - Real-time order status tracking
        - Automatic price alignment to instrument tick sizes
        - OCO (One-Cancels-Other) order support
        - Position-based order management
        - Thread-safe operations for concurrent trading

    Example Usage:
        >>> # Create order manager with dependency injection
        >>> order_manager = OrderManager(project_x_client)
        >>> # Initialize with optional real-time client
        >>> order_manager.initialize(realtime_client=realtime_client)
        >>> # Place simple orders
        >>> response = order_manager.place_market_order("MGC", side=0, size=1)
        >>> response = order_manager.place_limit_order("MGC", 1, 1, 2050.0)
        >>> # Place bracket orders (entry + stop + target)
        >>> bracket = order_manager.place_bracket_order(
        ...     contract_id="MGC",
        ...     side=0,  # Buy
        ...     size=1,
        ...     entry_price=2045.0,
        ...     stop_loss_price=2040.0,
        ...     take_profit_price=2055.0,
        ... )
        >>> # Manage existing orders
        >>> orders = order_manager.search_open_orders()
        >>> order_manager.cancel_order(order_id)
        >>> order_manager.modify_order(order_id, new_price=2052.0)
        >>> # Position-based operations
        >>> order_manager.close_position("MGC", method="market")
        >>> order_manager.add_stop_loss("MGC", stop_price=2040.0)
        >>> order_manager.add_take_profit("MGC", target_price=2055.0)
    """

    def __init__(self, project_x_client: "ProjectX"):
        """
        Initialize the OrderManager with a ProjectX client.

        Args:
            project_x_client: ProjectX client instance for API access
        """
        self.project_x = project_x_client
        self.logger = logging.getLogger(__name__)

        # Thread safety
        self.order_lock = threading.RLock()

        # Real-time integration (optional)
        self.realtime_client: ProjectXRealtimeClient | None = None
        self._realtime_enabled = False

        # Order tracking
        self.tracked_orders: dict[str, dict] = {}
        self.order_callbacks: dict[str, list] = defaultdict(list)

        # Statistics
        self.stats = {
            "orders_placed": 0,
            "orders_cancelled": 0,
            "orders_modified": 0,
            "bracket_orders_placed": 0,
            "last_order_time": None,
        }

        self.logger.info("OrderManager initialized")

    def initialize(
        self, realtime_client: Optional["ProjectXRealtimeClient"] = None
    ) -> bool:
        """
        Initialize the OrderManager with optional real-time capabilities.

        Args:
            realtime_client: Optional ProjectXRealtimeClient for live order tracking

        Returns:
            bool: True if initialization successful
        """
        try:
            # Set up real-time integration if provided
            if realtime_client:
                self.realtime_client = realtime_client
                self._setup_realtime_callbacks()
                self._realtime_enabled = True
                self.logger.info(
                    "✅ OrderManager initialized with real-time capabilities"
                )
            else:
                self.logger.info("✅ OrderManager initialized (polling mode)")

            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to initialize OrderManager: {e}")
            return False

    def _setup_realtime_callbacks(self):
        """Set up callbacks for real-time order monitoring."""
        if not self.realtime_client:
            return

        # Register for order events
        self.realtime_client.add_callback("order_update", self._on_order_update)
        self.realtime_client.add_callback("order_filled", self._on_order_filled)
        self.realtime_client.add_callback("order_cancelled", self._on_order_cancelled)

        self.logger.info("🔄 Real-time order callbacks registered")

    def _on_order_update(self, data: dict):
        """Handle real-time order updates."""
        try:
            with self.order_lock:
                if isinstance(data, list) and len(data) > 0:
                    for order_info in data:
                        if isinstance(order_info, dict) and "data" in order_info:
                            order_data = order_info["data"]
                            order_id = str(order_data.get("id", ""))
                            if order_id:
                                self.tracked_orders[order_id] = order_data
                elif isinstance(data, dict):
                    order_id = str(data.get("id", ""))
                    if order_id:
                        self.tracked_orders[order_id] = data

            self._trigger_callbacks("order_update", data)

        except Exception as e:
            self.logger.error(f"Error processing order update: {e}")

    def _on_order_filled(self, data: dict):
        """Handle real-time order fill notifications."""
        self.logger.info(f"✅ Order filled: {data}")
        self._trigger_callbacks("order_filled", data)

    def _on_order_cancelled(self, data: dict):
        """Handle real-time order cancellation notifications."""
        self.logger.info(f"❌ Order cancelled: {data}")
        self._trigger_callbacks("order_cancelled", data)

    def _trigger_callbacks(self, event_type: str, data: Any):
        """Trigger registered callbacks for order events."""
        for callback in self.order_callbacks.get(event_type, []):
            try:
                callback(data)
            except Exception as e:
                self.logger.error(f"Error in {event_type} callback: {e}")

    def add_callback(self, event_type: str, callback):
        """Add a callback for order events."""
        self.order_callbacks[event_type].append(callback)

    # ================================================================================
    # CORE ORDER PLACEMENT METHODS
    # ================================================================================

    def place_market_order(
        self, contract_id: str, side: int, size: int, account_id: int | None = None
    ) -> OrderPlaceResponse:
        """
        Place a market order (immediate execution at current market price).

        Args:
            contract_id: The contract ID to trade
            side: Order side: 0=Buy, 1=Sell
            size: Number of contracts to trade
            account_id: Account ID. Uses default account if None.

        Returns:
            OrderPlaceResponse: Response containing order ID and status

        Example:
            >>> response = order_manager.place_market_order("MGC", 0, 1)
        """
        return self.place_order(
            contract_id=contract_id,
            order_type=2,  # Market order
            side=side,
            size=size,
            account_id=account_id,
        )

    def place_limit_order(
        self,
        contract_id: str,
        side: int,
        size: int,
        limit_price: float,
        account_id: int | None = None,
    ) -> OrderPlaceResponse:
        """
        Place a limit order (execute only at specified price or better).

        Args:
            contract_id: The contract ID to trade
            side: Order side: 0=Buy, 1=Sell
            size: Number of contracts to trade
            limit_price: Maximum price for buy orders, minimum price for sell orders
            account_id: Account ID. Uses default account if None.

        Returns:
            OrderPlaceResponse: Response containing order ID and status

        Example:
            >>> response = order_manager.place_limit_order("MGC", 1, 1, 2050.0)
        """
        return self.place_order(
            contract_id=contract_id,
            order_type=1,  # Limit order
            side=side,
            size=size,
            limit_price=limit_price,
            account_id=account_id,
        )

    def place_stop_order(
        self,
        contract_id: str,
        side: int,
        size: int,
        stop_price: float,
        account_id: int | None = None,
    ) -> OrderPlaceResponse:
        """
        Place a stop order (market order triggered at stop price).

        Args:
            contract_id: The contract ID to trade
            side: Order side: 0=Buy, 1=Sell
            size: Number of contracts to trade
            stop_price: Price level that triggers the market order
            account_id: Account ID. Uses default account if None.

        Returns:
            OrderPlaceResponse: Response containing order ID and status

        Example:
            >>> # Stop loss for long position
            >>> response = order_manager.place_stop_order("MGC", 1, 1, 2040.0)
        """
        return self.place_order(
            contract_id=contract_id,
            order_type=4,  # Stop order
            side=side,
            size=size,
            stop_price=stop_price,
            account_id=account_id,
        )

    def place_trailing_stop_order(
        self,
        contract_id: str,
        side: int,
        size: int,
        trail_price: float,
        account_id: int | None = None,
    ) -> OrderPlaceResponse:
        """
        Place a trailing stop order (stop that follows price by trail amount).

        Args:
            contract_id: The contract ID to trade
            side: Order side: 0=Buy, 1=Sell
            size: Number of contracts to trade
            trail_price: Trail amount (distance from current price)
            account_id: Account ID. Uses default account if None.

        Returns:
            OrderPlaceResponse: Response containing order ID and status

        Example:
            >>> # Trailing stop $5 below current price
            >>> response = order_manager.place_trailing_stop_order("MGC", 1, 1, 5.0)
        """
        return self.place_order(
            contract_id=contract_id,
            order_type=5,  # Trailing stop order
            side=side,
            size=size,
            trail_price=trail_price,
            account_id=account_id,
        )

    def place_order(
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

        Args:
            contract_id: The contract ID to trade
            order_type: Order type:
                1=Limit, 2=Market, 4=Stop, 5=TrailingStop, 6=JoinBid, 7=JoinAsk
            side: Order side: 0=Buy, 1=Sell
            size: Number of contracts to trade
            limit_price: Limit price for limit orders (auto-aligned to tick size)
            stop_price: Stop price for stop orders (auto-aligned to tick size)
            trail_price: Trail amount for trailing stop orders (auto-aligned to tick size)
            custom_tag: Custom identifier for the order
            linked_order_id: ID of a linked order (for OCO, etc.)
            account_id: Account ID. Uses default account if None.

        Returns:
            OrderPlaceResponse: Response containing order ID and status

        Raises:
            ProjectXOrderError: If order placement fails
        """
        self.project_x._ensure_authenticated()

        # Use account_info if no account_id provided
        if account_id is None:
            if not self.project_x.account_info:
                self.project_x.get_account_info()
            if not self.project_x.account_info:
                raise ProjectXOrderError("No account information available")
            account_id = self.project_x.account_info.id

        # Align all prices to tick size to prevent "Invalid price" errors
        aligned_limit_price = self._align_price_to_tick_size(limit_price, contract_id)
        aligned_stop_price = self._align_price_to_tick_size(stop_price, contract_id)
        aligned_trail_price = self._align_price_to_tick_size(trail_price, contract_id)

        url = f"{self.project_x.base_url}/Order/place"
        payload = {
            "accountId": account_id,
            "contractId": contract_id,
            "type": order_type,
            "side": side,
            "size": size,
            "limitPrice": aligned_limit_price,
            "stopPrice": aligned_stop_price,
            "trailPrice": aligned_trail_price,
            "customTag": custom_tag,
            "linkedOrderId": linked_order_id,
        }
        
        # 🔍 DEBUG: Log order parameters to diagnose placement issues
        self.logger.debug(f"🔍 Order Placement Request: {payload}")

        try:
            response = requests.post(
                url,
                headers=self.project_x.headers,
                json=payload,
                timeout=self.project_x.timeout_seconds,
            )
            self.project_x._handle_response_errors(response)

            data = response.json()
            
            # 🔍 DEBUG: Log the actual API response to diagnose issues
            self.logger.debug(f"🔍 Order API Response: {data}")
            
            if not data.get("success", False):
                error_msg = data.get("errorMessage") or "Unknown error - no error message provided"
                self.logger.error(f"Order placement failed: {error_msg}")
                self.logger.error(f"🔍 Full response data: {data}")
                raise ProjectXOrderError(f"Order placement failed: {error_msg}")

            result = OrderPlaceResponse(**data)

            # Update statistics
            with self.order_lock:
                self.stats["orders_placed"] += 1
                self.stats["last_order_time"] = datetime.now()

            self.logger.info(f"✅ Order placed: {result.orderId}")
            return result

        except requests.RequestException as e:
            raise ProjectXConnectionError(f"Order placement request failed: {e}") from e
        except (KeyError, json.JSONDecodeError, TypeError) as e:
            self.logger.error(f"Invalid order placement response: {e}")
            raise ProjectXDataError(f"Invalid order placement response: {e}") from e

    # ================================================================================
    # BRACKET ORDER METHODS
    # ================================================================================

    def _prepare_bracket_prices(
        self,
        entry_price: float,
        stop_loss_price: float,
        take_profit_price: float,
        contract_id: str,
        side: int,
    ) -> tuple[float, float, float]:
        aligned_entry = self._align_price_to_tick_size(entry_price, contract_id)
        aligned_stop = self._align_price_to_tick_size(stop_loss_price, contract_id)
        aligned_target = self._align_price_to_tick_size(take_profit_price, contract_id)

        if aligned_entry is None or aligned_stop is None or aligned_target is None:
            raise ProjectXOrderError("Invalid bracket order prices")

        self._validate_bracket_prices(side, aligned_entry, aligned_stop, aligned_target)
        return aligned_entry, aligned_stop, aligned_target

    def _place_entry_order(
        self,
        contract_id: str,
        side: int,
        size: int,
        entry_type: str,
        aligned_entry: float,
        custom_tag: str | None,
        account_id: int | None,
    ) -> OrderPlaceResponse:
        entry_order_type = 1 if entry_type == "limit" else 2
        return self.place_order(
            contract_id=contract_id,
            order_type=entry_order_type,
            side=side,
            size=size,
            limit_price=aligned_entry if entry_type == "limit" else None,
            custom_tag=f"{custom_tag}_entry" if custom_tag else "bracket_entry",
            account_id=account_id,
        )

    def _place_stop_order(
        self,
        contract_id: str,
        stop_side: int,
        size: int,
        aligned_stop: float,
        entry_response: OrderPlaceResponse,
        custom_tag: str | None,
        account_id: int | None,
    ) -> OrderPlaceResponse:
        return self.place_order(
            contract_id=contract_id,
            order_type=4,
            side=stop_side,
            size=size,
            stop_price=aligned_stop,
            linked_order_id=entry_response.orderId,
            custom_tag=f"{custom_tag}_stop" if custom_tag else "bracket_stop",
            account_id=account_id,
        )

    def _place_target_order(
        self,
        contract_id: str,
        stop_side: int,
        size: int,
        aligned_target: float,
        entry_response: OrderPlaceResponse,
        custom_tag: str | None,
        account_id: int | None,
    ) -> OrderPlaceResponse:
        return self.place_order(
            contract_id=contract_id,
            order_type=1,
            side=stop_side,
            size=size,
            limit_price=aligned_target,
            linked_order_id=entry_response.orderId,
            custom_tag=f"{custom_tag}_target" if custom_tag else "bracket_target",
            account_id=account_id,
        )

    def place_bracket_order(
        self,
        contract_id: str,
        side: int,
        size: int,
        entry_price: float,
        stop_loss_price: float,
        take_profit_price: float,
        entry_type: str = "limit",
        account_id: int | None = None,
        custom_tag: str | None = None,
    ) -> BracketOrderResponse:
        """
        Place a bracket order with entry, stop loss, and take profit.

        A bracket order consists of three orders:
        1. Entry order (limit or market)
        2. Stop loss order (triggered if entry fills and price moves against position)
        3. Take profit order (triggered if entry fills and price moves favorably)

        Args:
            contract_id: The contract ID to trade
            side: Order side: 0=Buy, 1=Sell
            size: Number of contracts to trade
            entry_price: Entry price for the position
            stop_loss_price: Stop loss price (risk management)
            take_profit_price: Take profit price (profit target)
            entry_type: Entry order type: "limit" or "market"
            account_id: Account ID. Uses default account if None.
            custom_tag: Custom identifier for the bracket

        Returns:
            BracketOrderResponse: Comprehensive response with all order details

        Example:
            >>> # Long bracket order
            >>> bracket = order_manager.place_bracket_order(
            ...     contract_id="MGC",
            ...     side=0,  # Buy
            ...     size=1,
            ...     entry_price=2045.0,
            ...     stop_loss_price=2040.0,  # $5 risk
            ...     take_profit_price=2055.0,  # $10 profit target
            ... )
        """
        try:
            aligned_entry, aligned_stop, aligned_target = self._prepare_bracket_prices(
                entry_price, stop_loss_price, take_profit_price, contract_id, side
            )

            entry_response = self._place_entry_order(
                contract_id,
                side,
                size,
                entry_type,
                aligned_entry,
                custom_tag,
                account_id,
            )

            if not entry_response.success:
                return BracketOrderResponse(
                    success=False,
                    entry_order_id=None,
                    stop_order_id=None,
                    target_order_id=None,
                    entry_price=aligned_entry,
                    stop_loss_price=aligned_stop,
                    take_profit_price=aligned_target,
                    entry_response=entry_response,
                    stop_response=None,
                    target_response=None,
                    error_message=f"Entry order failed: {entry_response}",
                )

            stop_side = 1 - side
            stop_response = self._place_stop_order(
                contract_id,
                stop_side,
                size,
                aligned_stop,
                entry_response,
                custom_tag,
                account_id,
            )

            target_response = self._place_target_order(
                contract_id,
                stop_side,
                size,
                aligned_target,
                entry_response,
                custom_tag,
                account_id,
            )

            bracket_success = (
                entry_response.success
                and stop_response.success
                and target_response.success
            )

            result = BracketOrderResponse(
                success=bracket_success,
                entry_order_id=entry_response.orderId
                if entry_response.success
                else None,
                stop_order_id=stop_response.orderId if stop_response.success else None,
                target_order_id=target_response.orderId
                if target_response.success
                else None,
                entry_price=aligned_entry,
                stop_loss_price=aligned_stop,
                take_profit_price=aligned_target,
                entry_response=entry_response,
                stop_response=stop_response,
                target_response=target_response,
                error_message=None
                if bracket_success
                else "Partial bracket order failure",
            )

            if bracket_success:
                self.logger.info(
                    f"✅ Bracket order placed successfully: Entry={entry_response.orderId}, Stop={stop_response.orderId}, Target={target_response.orderId}"
                )
                with self.order_lock:
                    self.stats["bracket_orders_placed"] += 1
            else:
                self.logger.warning("⚠️ Partial bracket order failure")

            return result

        except Exception as e:
            self.logger.error(f"❌ Bracket order failed: {e}")
            return BracketOrderResponse(
                success=False,
                entry_order_id=None,
                stop_order_id=None,
                target_order_id=None,
                entry_price=entry_price,
                stop_loss_price=stop_loss_price,
                take_profit_price=take_profit_price,
                entry_response=None,
                stop_response=None,
                target_response=None,
                error_message=str(e),
            )

    def _validate_bracket_prices(
        self, side: int, entry: float, stop: float, target: float
    ):
        """Validate bracket order price relationships."""
        if side == 0:  # Buy order
            if stop >= entry:
                raise ProjectXOrderError(
                    "For buy orders, stop loss must be below entry price"
                )
            if target <= entry:
                raise ProjectXOrderError(
                    "For buy orders, take profit must be above entry price"
                )
        else:  # Sell order
            if stop <= entry:
                raise ProjectXOrderError(
                    "For sell orders, stop loss must be above entry price"
                )
            if target >= entry:
                raise ProjectXOrderError(
                    "For sell orders, take profit must be below entry price"
                )

    # ================================================================================
    # ORDER MODIFICATION AND CANCELLATION
    # ================================================================================

    def cancel_order(self, order_id: int, account_id: int | None = None) -> bool:
        """
        Cancel an existing order.

        Args:
            order_id: ID of the order to cancel
            account_id: Account ID. Uses default account if None.

        Returns:
            bool: True if cancellation successful

        Example:
            >>> success = order_manager.cancel_order(12345)
        """
        self.project_x._ensure_authenticated()

        if account_id is None:
            if not self.project_x.account_info:
                self.project_x.get_account_info()
            if not self.project_x.account_info:
                raise ProjectXOrderError("No account information available")
            account_id = self.project_x.account_info.id

        url = f"{self.project_x.base_url}/Order/cancel"
        payload = {
            "accountId": account_id,
            "orderId": order_id,
        }

        try:
            response = requests.post(
                url,
                headers=self.project_x.headers,
                json=payload,
                timeout=self.project_x.timeout_seconds,
            )
            self.project_x._handle_response_errors(response)

            data = response.json()
            success = data.get("success", False)

            if success:
                with self.order_lock:
                    self.stats["orders_cancelled"] += 1
                self.logger.info(f"✅ Order {order_id} cancelled successfully")
            else:
                error_msg = data.get("errorMessage", "Unknown error")
                self.logger.error(f"❌ Order cancellation failed: {error_msg}")

            return success

        except requests.RequestException as e:
            self.logger.error(f"❌ Order cancellation request failed: {e}")
            return False
        except (KeyError, json.JSONDecodeError) as e:
            self.logger.error(f"❌ Invalid cancellation response: {e}")
            return False

    def modify_order(
        self,
        order_id: int,
        limit_price: float | None = None,
        stop_price: float | None = None,
        size: int | None = None,
        account_id: int | None = None,
    ) -> bool:
        """
        Modify an existing order.

        Args:
            order_id: ID of the order to modify
            limit_price: New limit price (if applicable)
            stop_price: New stop price (if applicable)
            size: New order size
            account_id: Account ID. Uses default account if None.

        Returns:
            bool: True if modification successful

        Example:
            >>> # Change limit price
            >>> success = order_manager.modify_order(12345, limit_price=2052.0)
            >>> # Change order size
            >>> success = order_manager.modify_order(12345, size=2)
        """
        self.project_x._ensure_authenticated()

        if account_id is None:
            if not self.project_x.account_info:
                self.project_x.get_account_info()
            if not self.project_x.account_info:
                raise ProjectXOrderError("No account information available")
            account_id = self.project_x.account_info.id

        # Get existing order details to determine contract_id for price alignment
        existing_order = self.get_order_by_id(order_id, account_id)
        if not existing_order:
            self.logger.error(f"❌ Cannot modify order {order_id}: Order not found")
            return False

        contract_id = existing_order.contractId

        # Align prices to tick size
        aligned_limit = self._align_price_to_tick_size(limit_price, contract_id)
        aligned_stop = self._align_price_to_tick_size(stop_price, contract_id)

        url = f"{self.project_x.base_url}/Order/modify"
        payload: dict[str, Any] = {
            "accountId": account_id,
            "orderId": order_id,
        }

        # Add only the fields that are being modified
        if aligned_limit is not None:
            payload["limitPrice"] = aligned_limit
        if aligned_stop is not None:
            payload["stopPrice"] = aligned_stop
        if size is not None:
            payload["size"] = size

        try:
            response = requests.post(
                url,
                headers=self.project_x.headers,
                json=payload,
                timeout=self.project_x.timeout_seconds,
            )
            self.project_x._handle_response_errors(response)

            data = response.json()
            success = data.get("success", False)

            if success:
                with self.order_lock:
                    self.stats["orders_modified"] += 1
                self.logger.info(f"✅ Order {order_id} modified successfully")
            else:
                error_msg = data.get("errorMessage", "Unknown error")
                self.logger.error(f"❌ Order modification failed: {error_msg}")

            return success

        except requests.RequestException as e:
            self.logger.error(f"❌ Order modification request failed: {e}")
            return False
        except (KeyError, json.JSONDecodeError) as e:
            self.logger.error(f"❌ Invalid modification response: {e}")
            return False

    def cancel_all_orders(
        self, contract_id: str | None = None, account_id: int | None = None
    ) -> dict[str, Any]:
        """
        Cancel all orders, optionally filtered by contract.

        Args:
            contract_id: Optional contract ID to filter orders
            account_id: Account ID. Uses default account if None.

        Returns:
            Dict with cancellation results

        Example:
            >>> # Cancel all orders
            >>> result = order_manager.cancel_all_orders()
            >>> # Cancel all MGC orders
            >>> result = order_manager.cancel_all_orders(contract_id="MGC")
        """
        orders = self.search_open_orders(contract_id=contract_id, account_id=account_id)

        results = {
            "total_orders": len(orders),
            "cancelled": 0,
            "failed": 0,
            "errors": [],
        }

        for order in orders:
            try:
                if self.cancel_order(order.id, account_id):
                    results["cancelled"] += 1
                else:
                    results["failed"] += 1
            except Exception as e:
                results["failed"] += 1
                results["errors"].append(f"Order {order.id}: {e!s}")

        self.logger.info(
            f"✅ Cancelled {results['cancelled']}/{results['total_orders']} orders"
        )
        return results

    # ================================================================================
    # ORDER SEARCH AND STATUS METHODS
    # ================================================================================

    def search_open_orders(
        self, contract_id: str | None = None, account_id: int | None = None
    ) -> list[Order]:
        """
        Search for open orders, optionally filtered by contract.

        Args:
            contract_id: Optional contract ID to filter orders
            account_id: Account ID. Uses default account if None.

        Returns:
            List[Order]: List of open orders

        Example:
            >>> # Get all open orders
            >>> orders = order_manager.search_open_orders()
            >>> # Get MGC orders only
            >>> mgc_orders = order_manager.search_open_orders(contract_id="MGC")
        """
        self.project_x._ensure_authenticated()

        if account_id is None:
            if not self.project_x.account_info:
                self.project_x.get_account_info()
            if not self.project_x.account_info:
                raise ProjectXOrderError("No account information available")
            account_id = self.project_x.account_info.id

        url = f"{self.project_x.base_url}/Order/searchOpen"
        payload: dict[str, Any] = {"accountId": account_id}

        if contract_id:
            payload["contractId"] = contract_id

        try:
            response = requests.post(
                url,
                headers=self.project_x.headers,
                json=payload,
                timeout=self.project_x.timeout_seconds,
            )
            self.project_x._handle_response_errors(response)

            data = response.json()
            if not data.get("success", False):
                error_msg = data.get("errorMessage", "Unknown error")
                self.logger.error(f"Order search failed: {error_msg}")
                return []

            orders = data.get("orders", [])
            # Filter to only include fields that Order model expects
            expected_fields = {
                'id', 'accountId', 'contractId', 'creationTimestamp', 'updateTimestamp',
                'status', 'type', 'side', 'size', 'fillVolume', 'limitPrice', 'stopPrice'
            }
            filtered_orders = []
            for order in orders:
                if isinstance(order, dict):
                    # Only keep fields that Order model expects
                    filtered_order = {k: v for k, v in order.items() if k in expected_fields}
                    filtered_orders.append(Order(**filtered_order))
                else:
                    filtered_orders.append(Order(**order))
            return filtered_orders

        except requests.RequestException as e:
            self.logger.error(f"❌ Order search request failed: {e}")
            return []
        except (KeyError, json.JSONDecodeError, TypeError) as e:
            self.logger.error(f"❌ Invalid order search response: {e}")
            return []

    def get_order_by_id(
        self, order_id: int, account_id: int | None = None
    ) -> Order | None:
        """
        Get a specific order by ID.

        Args:
            order_id: ID of the order to retrieve
            account_id: Account ID. Uses default account if None.

        Returns:
            Order: Order object if found, None otherwise
        """
        # Try real-time data first if available
        if self._realtime_enabled and self.realtime_client:
            with self.order_lock:
                order_data = self.tracked_orders.get(str(order_id))
                if order_data:
                    try:
                        return Order(**order_data)
                    except Exception as e:
                        self.logger.debug(f"Failed to parse cached order data: {e}")

        # Fallback to API search
        orders = self.search_open_orders(account_id=account_id)
        for order in orders:
            if order.id == order_id:
                return order

        return None

    def is_order_filled(self, order_id: int) -> bool:
        """
        Check if an order has been filled.

        Args:
            order_id: ID of the order to check

        Returns:
            bool: True if order is filled
        """
        if self._realtime_enabled and self.realtime_client:
            return self.realtime_client.is_order_filled(str(order_id))

        # Fallback to API check
        order = self.get_order_by_id(order_id)
        return order is not None and order.status == 2  # 2 = Filled

    # ================================================================================
    # POSITION-BASED ORDER METHODS
    # ================================================================================

    def close_position(
        self,
        contract_id: str,
        method: str = "market",
        limit_price: float | None = None,
        account_id: int | None = None,
    ) -> OrderPlaceResponse | None:
        """
        Close an existing position using market or limit order.

        Args:
            contract_id: Contract ID of position to close
            method: "market" or "limit"
            limit_price: Limit price if using limit order
            account_id: Account ID. Uses default account if None.

        Returns:
            OrderPlaceResponse: Response from closing order

        Example:
            >>> # Close position at market
            >>> response = order_manager.close_position("MGC", method="market")
            >>> # Close position with limit
            >>> response = order_manager.close_position(
            ...     "MGC", method="limit", limit_price=2050.0
            ... )
        """
        # Get current position
        positions = self.project_x.search_open_positions(account_id=account_id)
        position = None
        for pos in positions:
            if pos.contractId == contract_id:
                position = pos
                break

        if not position:
            self.logger.warning(f"⚠️ No open position found for {contract_id}")
            return None

        # Determine order side (opposite of position)
        side = 1 if position.size > 0 else 0  # Sell long, Buy short
        size = abs(position.size)

        # Place closing order
        if method == "market":
            return self.place_market_order(contract_id, side, size, account_id)
        elif method == "limit":
            if limit_price is None:
                raise ProjectXOrderError("Limit price required for limit close")
            return self.place_limit_order(
                contract_id, side, size, limit_price, account_id
            )
        else:
            raise ProjectXOrderError(f"Invalid close method: {method}")

    def add_stop_loss(
        self, contract_id: str, stop_price: float, account_id: int | None = None
    ) -> OrderPlaceResponse | None:
        """
        Add a stop loss order to an existing position.

        Args:
            contract_id: Contract ID of position
            stop_price: Stop loss price
            account_id: Account ID. Uses default account if None.

        Returns:
            OrderPlaceResponse: Response from stop loss order

        Example:
            >>> response = order_manager.add_stop_loss("MGC", 2040.0)
        """
        # Get current position
        positions = self.project_x.search_open_positions(account_id=account_id)
        position = None
        for pos in positions:
            if pos.contractId == contract_id:
                position = pos
                break

        if not position:
            self.logger.warning(f"⚠️ No open position found for {contract_id}")
            return None

        # Determine order side (opposite of position)
        side = 1 if position.size > 0 else 0  # Sell long, Buy short
        size = abs(position.size)

        return self.place_stop_order(contract_id, side, size, stop_price, account_id)

    def add_take_profit(
        self, contract_id: str, target_price: float, account_id: int | None = None
    ) -> OrderPlaceResponse | None:
        """
        Add a take profit order to an existing position.

        Args:
            contract_id: Contract ID of position
            target_price: Take profit price
            account_id: Account ID. Uses default account if None.

        Returns:
            OrderPlaceResponse: Response from take profit order

        Example:
            >>> response = order_manager.add_take_profit("MGC", 2055.0)
        """
        # Get current position
        positions = self.project_x.search_open_positions(account_id=account_id)
        position = None
        for pos in positions:
            if pos.contractId == contract_id:
                position = pos
                break

        if not position:
            self.logger.warning(f"⚠️ No open position found for {contract_id}")
            return None

        # Determine order side (opposite of position)
        side = 1 if position.size > 0 else 0  # Sell long, Buy short
        size = abs(position.size)

        return self.place_limit_order(contract_id, side, size, target_price, account_id)

    # ================================================================================
    # UTILITY METHODS
    # ================================================================================

    def _align_price_to_tick_size(
        self, price: float | None, contract_id: str
    ) -> float | None:
        """
        Align a price to the instrument's tick size.

        Args:
            price: The price to align
            contract_id: Contract ID to get tick size from

        Returns:
            float: Price aligned to tick size
            None: If price is None
        """
        try:
            if price is None:
                return None

            instrument_obj = None

            # Try to get instrument by simple symbol first (e.g., "MNQ")
            if "." not in contract_id:
                instrument_obj = self.project_x.get_instrument(contract_id)
            else:
                # Extract symbol from contract ID (e.g., "CON.F.US.MGC.M25" -> "MGC")
                symbol = extract_symbol_from_contract_id(contract_id)
                if symbol:
                    instrument_obj = self.project_x.get_instrument(symbol)

            if not instrument_obj or not hasattr(instrument_obj, "tickSize"):
                self.logger.warning(
                    f"No tick size available for contract {contract_id}, using original price: {price}"
                )
                return price

            tick_size = instrument_obj.tickSize
            if tick_size is None or tick_size <= 0:
                self.logger.warning(
                    f"Invalid tick size {tick_size} for {contract_id}, using original price: {price}"
                )
                return price

            self.logger.debug(
                f"Aligning price {price} with tick size {tick_size} for {contract_id}"
            )

            # Convert to Decimal for precise calculation
            price_decimal = Decimal(str(price))
            tick_decimal = Decimal(str(tick_size))

            # Round to nearest tick using precise decimal arithmetic
            ticks = (price_decimal / tick_decimal).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
            aligned_decimal = ticks * tick_decimal

            # Determine the number of decimal places needed for the tick size
            tick_str = str(tick_size)
            decimal_places = len(tick_str.split(".")[1]) if "." in tick_str else 0

            # Create the quantization pattern
            if decimal_places == 0:
                quantize_pattern = Decimal("1")
            else:
                quantize_pattern = Decimal("0." + "0" * (decimal_places - 1) + "1")

            result = float(aligned_decimal.quantize(quantize_pattern))

            if result != price:
                self.logger.info(
                    f"Price alignment: {price} -> {result} (tick size: {tick_size})"
                )

            return result

        except Exception as e:
            self.logger.error(f"Error aligning price {price} to tick size: {e}")
            return price  # Return original price if alignment fails

    def get_order_statistics(self) -> dict[str, Any]:
        """
        Get order management statistics.

        Returns:
            Dict with statistics and health information
        """
        with self.order_lock:
            return {
                "statistics": self.stats.copy(),
                "realtime_enabled": self._realtime_enabled,
                "tracked_orders": len(self.tracked_orders),
                "callbacks_registered": {
                    event: len(callbacks)
                    for event, callbacks in self.order_callbacks.items()
                },
                "health_status": "active"
                if self.project_x._authenticated
                else "inactive",
            }

    def cleanup(self):
        """Clean up resources and connections."""
        with self.order_lock:
            self.tracked_orders.clear()
            self.order_callbacks.clear()

        self.logger.info("✅ OrderManager cleanup completed")
