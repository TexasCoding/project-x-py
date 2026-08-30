"""
Trading-related type definitions for orders and positions.

Author: @TexasCoding
Date: 2025-08-02

Overview:
    Contains type definitions for trading operations including order management,
    position tracking, and execution statistics. Provides comprehensive type safety
    for all trading-related operations and data structures.

Key Features:
    - Order side and type enumerations for trading operations
    - Order status tracking and management
    - Position side definitions for long/short positions
    - Order statistics tracking and reporting
    - Type safety for all trading operations
    - Comprehensive enum definitions for ProjectX trading

Type Categories:
    - Order Types: OrderSide, OrderType, OrderStatus for order management
    - Position Types: PositionType for position tracking

Example Usage:
    ```python
    from project_x_py.types.trading import (
        OrderSide,
        OrderType,
        OrderStatus,
        PositionType,
    )


    # Use order side enumeration
    def place_order(side: OrderSide, size: int) -> None:
        if side == OrderSide.BUY:
            print(f"Placing buy order for {size} contracts")
        else:
            print(f"Placing sell order for {size} contracts")


    # Use order type enumeration
    def create_order(order_type: OrderType, price: float) -> None:
        if order_type == OrderType.MARKET:
            print("Creating market order")
        elif order_type == OrderType.LIMIT:
            print(f"Creating limit order at {price}")
        elif order_type == OrderType.STOP:
            print(f"Creating stop order at {price}")


    # Use order status tracking
    def track_order_status(status: OrderStatus) -> None:
        if status == OrderStatus.OPEN:
            print("Order is open and active")
        elif status == OrderStatus.FILLED:
            print("Order has been filled")
        elif status == OrderStatus.CANCELLED:
            print("Order has been cancelled")


    # Use position side enumeration
    def manage_position(type: PositionType, size: int) -> None:
        if type == PositionType.LONG:
            print(f"Long position: {size} contracts")
        elif type == PositionType.SHORT:
            print(f"Short position: {size} contracts")
        else:
            print("Undefined position")
    ```

Order Types:
    - OrderSide: BUY=0, SELL=1 for order direction
    - OrderType: LIMIT=1, MARKET=2, STOP_LIMIT=3, STOP=4, TRAILING_STOP=5, JOIN_BID=6, JOIN_ASK=7
    - OrderStatus: NONE=0, OPEN=1, FILLED=2, CANCELLED=3, EXPIRED=4, REJECTED=5, PENDING=6, PENDING_CANCELLATION=7, SUSPENDED=8

Position Types:
    - PositionType: UNDEFINED=0, LONG=1, SHORT=2 for position direction

Statistics Types:

Trading Operations:
    - Order placement with side and type specifications
    - Order status tracking and management
    - Position side management for long/short positions
    - Order statistics tracking for performance analysis

See Also:
    - `types.base`: Core type definitions and constants
    - `types.market_data`: Market data structures and configurations
    - `types.protocols`: Protocol definitions for type checking
"""

from enum import IntEnum


class OrderSide(IntEnum):
    """Order side enumeration."""

    BUY = 0
    SELL = 1


class OrderType(IntEnum):
    """Order type enumeration."""

    LIMIT = 1
    MARKET = 2
    STOP_LIMIT = 3
    STOP = 4
    TRAILING_STOP = 5
    JOIN_BID = 6
    JOIN_ASK = 7


class OrderStatus(IntEnum):
    """Order status enumeration (Gateway OrderStatus)."""

    NONE = 0
    OPEN = 1
    FILLED = 2
    CANCELLED = 3
    EXPIRED = 4
    REJECTED = 5
    PENDING = 6
    PENDING_CANCELLATION = 7
    SUSPENDED = 8


class PositionType(IntEnum):
    """Position type enumeration."""

    UNDEFINED = 0
    LONG = 1
    SHORT = 2


class TradeLogType(IntEnum):
    """Trade type enumeration. Used for trade logging."""

    BUY = 0
    SELL = 1


__all__ = [
    "OrderSide",
    "OrderStatus",
    "OrderType",
    "PositionType",
    "TradeLogType",
]
