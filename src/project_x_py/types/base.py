"""
Core type definitions used across the ProjectX SDK.

Author: @TexasCoding
Date: 2025-08-02

Overview:
    Contains fundamental types that are used throughout the SDK, including
    callback type definitions, common type aliases, and basic constants.
    Provides the foundation for type safety across all SDK components.

Key Features:
    - Callback type definitions for async and sync functions
    - Common type aliases for IDs and identifiers
    - SDK-wide constants for timezone and precision settings
    - Type safety for callback patterns and data flow
    - Consistent type definitions across all modules

Type Definitions:
    - Callback Types: AsyncCallback, SyncCallback, CallbackType for event handling
    - ID Types: ContractId, AccountId, OrderId, PositionId for entity identification
    - Constants: DEFAULT_TIMEZONE, TICK_SIZE_PRECISION for SDK configuration

Example Usage:
    ```python
    from project_x_py.types.base import (
        AsyncCallback,
        SyncCallback,
        CallbackType,
        ContractId,
        AccountId,
        OrderId,
        PositionId,
        DEFAULT_TIMEZONE,
        TICK_SIZE_PRECISION,
    )


    # Define callback functions with proper typing
    async def async_handler(data: dict[str, Any]) -> None:
        print(f"Async callback: {data}")


    # Use in function signatures
    async def register_callback(callback: AsyncCallback) -> None:
        pass


    # Use type aliases for clarity
    def process_order(order_id: OrderId, contract_id: ContractId) -> None:
        pass


    # Use constants for configuration
    timezone = DEFAULT_TIMEZONE
    precision = TICK_SIZE_PRECISION
    ```

Callback Types:
    - AsyncCallback: Async function that takes dict and returns coroutine
    - SyncCallback: Synchronous function that takes dict and returns None
    - CallbackType: Union of async and sync callbacks for flexible usage

ID Types:
    - ContractId: String identifier for trading contracts
    - AccountId: String identifier for trading accounts
    - OrderId: String identifier for orders
    - PositionId: String identifier for positions

Constants:
    - DEFAULT_TIMEZONE: Default timezone for timestamp handling ("America/Chicago")
    - TICK_SIZE_PRECISION: Decimal precision for tick size calculations (8)

See Also:
    - `types.trading`: Trading operation types and enums
    - `types.market_data`: Market data structures and configurations
    - `types.protocols`: Protocol definitions for type checking
"""

from collections.abc import Callable, Coroutine
from typing import Any

# Type aliases for callbacks
AsyncCallback = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]
SyncCallback = Callable[[dict[str, Any]], None]
CallbackType = AsyncCallback | SyncCallback

# Common constants
DEFAULT_TIMEZONE = "America/Chicago"
TICK_SIZE_PRECISION = 8  # Decimal places for tick size rounding

# Common type aliases
ContractId = str
AccountId = str
OrderId = str
PositionId = str

# SignalR connection type (pysignalr AsyncHubConnection at runtime)
HubConnection = Any

__all__ = [
    "DEFAULT_TIMEZONE",
    "TICK_SIZE_PRECISION",
    "HubConnection",
    "AccountId",
    "AsyncCallback",
    "CallbackType",
    "ContractId",
    "OrderId",
    "PositionId",
    "SyncCallback",
]
