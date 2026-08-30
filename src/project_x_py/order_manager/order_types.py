"""
Async order type placement mixin for ProjectX.

Author: @TexasCoding
Date: 2025-08-02

Overview:
    Implements mixin methods for placing specific order types (market, limit,
    stop, trailing stop) in the async OrderManager system. Encapsulates order-type
    validation, parameter handling, and delegates to the unified underlying API.

Key Features:
    - Async placement of market, limit, stop, and trailing stop orders
    - Standardized argument validation and contract handling
    - Integrates with bracket and position order mixins
    - Returns model-typed responses for downstream logic
    - Automatic price alignment to instrument tick sizes
    - Comprehensive error handling and validation

Order Types Supported:
    - Market Orders: Immediate execution at current market price
    - Limit Orders: Execution at specified price or better
    - Stop Orders: Market orders triggered at stop price
    - Trailing Stop Orders: Dynamic stops that follow price movement
    - Join Bid Orders: Limit buy orders at current best bid price
    - Join Ask Orders: Limit sell orders at current best ask price

Each order type method provides a simplified interface for common order placement
scenarios while maintaining full compatibility with the underlying order system.

Example Usage:
    ```python
    # V3.1: Using TradingSuite's integrated order manager
    suite = await TradingSuite.create("MNQ")

    # Get current price for realistic order placement
    current_price = await suite.data.get_current_price()

    await suite.orders.place_limit_order(
        suite.instrument_id, 1, 2, current_price - 10.0
    )
    await suite.orders.place_market_order(suite.instrument_id, 0, 1)
    await suite.orders.place_stop_order(suite.instrument_id, 1, 1, current_price - 20.0)
    await suite.orders.place_trailing_stop_order(suite.instrument_id, 1, 1, 15.0)
    await suite.orders.place_join_bid_order(suite.instrument_id, 1)  # Join bid
    await suite.orders.place_join_ask_order(suite.instrument_id, 1)  # Join ask
    ```

See Also:
    - `order_manager.core.OrderManager`
    - `order_manager.bracket_orders`
    - `order_manager.position_orders`
"""

import logging
from typing import TYPE_CHECKING

from project_x_py.models import OrderPlaceResponse
from project_x_py.types.trading import OrderSide, OrderType

if TYPE_CHECKING:
    from project_x_py.types import OrderManagerProtocol

logger = logging.getLogger(__name__)


class OrderTypesMixin:
    """
    Mixin for different order type placement methods.

    Provides simplified methods for placing specific order types (market, limit, stop,
    trailing stop) that delegate to the core place_order method. Each method handles
    the specific parameters and validation required for that order type while maintaining
    consistency with the overall order management system.
    """

    async def place_market_order(
        self: "OrderManagerProtocol",
        contract_id: str,
        side: int,
        size: int,
        account_id: int | None = None,
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
            >>> # V3.1: Place market order
            >>> response = await suite.orders.place_market_order(
            ...     suite.instrument_id, 0, 1
            ... )
        """
        return await self.place_order(
            contract_id=contract_id,
            side=side,
            size=size,
            order_type=OrderType.MARKET,
            account_id=account_id,
        )

    async def place_limit_order(
        self: "OrderManagerProtocol",
        contract_id: str,
        side: int,
        size: int,
        limit_price: float,
        account_id: int | None = None,
        linked_order_id: int | None = None,
    ) -> OrderPlaceResponse:
        """
        Place a limit order (execute only at specified price or better).

        Args:
            contract_id: The contract ID to trade
            side: Order side: 0=Buy, 1=Sell
            size: Number of contracts to trade
            limit_price: Maximum price for buy orders, minimum price for sell orders
            account_id: Account ID. Uses default account if None.
            linked_order_id: Optional OCO sibling order ID.

        Returns:
            OrderPlaceResponse: Response containing order ID and status

        Example:
            >>> # V3.1: Place limit order with realistic price
            >>> current_price = await suite.data.get_current_price()
            >>> response = await suite.orders.place_limit_order(
            ...     suite.instrument_id, 1, 1, current_price - 10.0
            ... )
        """
        return await self.place_order(
            contract_id=contract_id,
            side=side,
            size=size,
            order_type=OrderType.LIMIT,
            limit_price=limit_price,
            linked_order_id=linked_order_id,
            account_id=account_id,
        )

    async def place_stop_order(
        self: "OrderManagerProtocol",
        contract_id: str,
        side: int,
        size: int,
        stop_price: float,
        account_id: int | None = None,
        linked_order_id: int | None = None,
    ) -> OrderPlaceResponse:
        """
        Place a stop order (market order triggered at stop price).

        Args:
            contract_id: The contract ID to trade
            side: Order side: 0=Buy, 1=Sell
            size: Number of contracts to trade
            stop_price: Price level that triggers the market order
            account_id: Account ID. Uses default account if None.
            linked_order_id: Optional OCO sibling order ID.

        Returns:
            OrderPlaceResponse: Response containing order ID and status

        Example:
            >>> # V3.1: Stop loss for long position
            >>> current_price = await suite.data.get_current_price()
            >>> response = await suite.orders.place_stop_order(
            ...     suite.instrument_id, 1, 1, current_price - 20.0
            ... )
        """
        return await self.place_order(
            contract_id=contract_id,
            side=side,
            size=size,
            order_type=OrderType.STOP,
            stop_price=stop_price,
            linked_order_id=linked_order_id,
            account_id=account_id,
        )

    async def place_trailing_stop_order(
        self: "OrderManagerProtocol",
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
            >>> # V3.1: Trailing stop order
            >>> response = await suite.orders.place_trailing_stop_order(
            ...     suite.instrument_id,
            ...     1,
            ...     1,
            ...     15.0,  # Trail by $15
            ... )
        """
        return await self.place_order(
            contract_id=contract_id,
            order_type=OrderType.TRAILING_STOP,
            side=side,
            size=size,
            trail_price=trail_price,
            account_id=account_id,
        )

    async def place_join_bid_order(
        self: "OrderManagerProtocol",
        contract_id: str,
        size: int,
        account_id: int | None = None,
    ) -> OrderPlaceResponse:
        """
        Place a join bid order (limit order at current best bid price).

        Join bid orders automatically place a limit buy order at the current
        best bid price, joining the queue of passive liquidity providers.
        The order will be placed at whatever the best bid price is at the
        time of submission.

        Args:
            contract_id: The contract ID to trade
            size: Number of contracts to trade
            account_id: Account ID. Uses default account if None.

        Returns:
            OrderPlaceResponse: Response containing order ID and status

        Example:
            >>> # V3.1: Join the bid to provide liquidity
            >>> response = await suite.orders.place_join_bid_order(
            ...     suite.instrument_id, 1
            ... )
        """
        return await self.place_order(
            contract_id=contract_id,
            side=OrderSide.BUY,
            size=size,
            order_type=OrderType.JOIN_BID,
            account_id=account_id,
        )

    async def place_join_ask_order(
        self: "OrderManagerProtocol",
        contract_id: str,
        size: int,
        account_id: int | None = None,
    ) -> OrderPlaceResponse:
        """
        Place a join ask order (limit order at current best ask price).

        Join ask orders automatically place a limit sell order at the current
        best ask price, joining the queue of passive liquidity providers.
        The order will be placed at whatever the best ask price is at the
        time of submission.

        Args:
            contract_id: The contract ID to trade
            size: Number of contracts to trade
            account_id: Account ID. Uses default account if None.

        Returns:
            OrderPlaceResponse: Response containing order ID and status

        Example:
            >>> # V3.1: Join the ask to provide liquidity
            >>> response = await suite.orders.place_join_ask_order(
            ...     suite.instrument_id, 1
            ... )
        """
        return await self.place_order(
            contract_id=contract_id,
            side=OrderSide.SELL,
            size=size,
            order_type=OrderType.JOIN_ASK,
            account_id=account_id,
        )
