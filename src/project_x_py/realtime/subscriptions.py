"""
Subscription management for real-time client.

Author: @TexasCoding
Date: 2025-08-02

Overview:
    Provides subscription management functionality for the ProjectX real-time client,
    including user updates, market data subscriptions, and dynamic subscription
    management for specific contracts and data types.

Key Features:
    - User update subscriptions (account, position, order, trade events)
    - Market data subscriptions (quotes, trades, market depth)
    - Dynamic subscription management for specific contracts
    - Subscription tracking for reconnection handling
    - Thread-safe subscription operations
    - Comprehensive error handling and logging

Subscription Capabilities:
    - User Hub: Account, position, order, and trade subscriptions
    - Market Hub: Quote, trade, and market depth subscriptions
    - Contract-specific market data subscriptions
    - Subscription management and tracking
    - Reconnection handling with subscription restoration
    - Error handling and recovery

Example Usage:
    ```python
    # Subscribe to user updates
    if await client.connect():
        await client.subscribe_user_updates()

        # Subscribe to market data for specific contracts
        await client.subscribe_market_data(["MGC", "NQ", "ES"])

        # Add more contracts dynamically
        await client.subscribe_market_data(["YM"])

        # Unsubscribe from specific contracts
        await client.unsubscribe_market_data(["YM"])

        # Unsubscribe from user updates
        await client.unsubscribe_user_updates()
    ```

Subscription Types:
    User Subscriptions:
        - SubscribeAccounts: Account balance and margin updates
        - SubscribeOrders: Order lifecycle events
        - SubscribePositions: Position changes and closures
        - SubscribeTrades: Trade execution events

    Market Subscriptions:
        - SubscribeContractQuotes: Real-time bid/ask data
        - SubscribeContractTrades: Executed trade data
        - SubscribeContractMarketDepth: Order book data

See Also:
    - `realtime.core.ProjectXRealtimeClient`
    - `realtime.connection_management.ConnectionManagementMixin`
    - `realtime.event_handling.EventHandlingMixin`
"""

import asyncio
from typing import TYPE_CHECKING

from project_x_py.realtime.async_hub import invoke_maybe
from project_x_py.utils import (
    LogContext,
    LogMessages,
    ProjectXLogger,
    handle_errors,
)

if TYPE_CHECKING:
    from project_x_py.types import ProjectXRealtimeClientProtocol

logger = ProjectXLogger.get_logger(__name__)


class SubscriptionsMixin:
    """Mixin for subscription management functionality."""

    @handle_errors("subscribe user updates", reraise=False, default_return=False)
    async def subscribe_user_updates(self: "ProjectXRealtimeClientProtocol") -> bool:
        """
        Subscribe to all user-specific real-time updates.

        Enables real-time streaming of account-specific events including positions,
        orders, trades, and account balance changes. Must be connected to user hub.

        Subscriptions:
            - Account updates: Balance, buying power, margin changes
            - Position updates: New positions, size changes, closures
            - Order updates: New orders, fills, cancellations, modifications
            - Trade executions: Individual fills with prices and timestamps

        Returns:
            bool: True if all subscriptions successful, False otherwise

        Example:
            >>> # Basic subscription
            >>> if await client.connect():
            ...     if await client.subscribe_user_updates():
            ...         print("Subscribed to user events")
            >>> # With callbacks
            >>> async def on_position_update(data):
            ...     print(f"Position update: {data}")
            >>> await client.add_callback("position_update", on_position_update)
            >>> await client.subscribe_user_updates()
            >>> # Multiple accounts (if supported)
            >>> client1 = ProjectXRealtimeClient(jwt, "12345")
            >>> client2 = ProjectXRealtimeClient(jwt, "67890")
            >>> await client1.connect()
            >>> await client2.connect()
            >>> await client1.subscribe_user_updates()  # Account 12345 events
            >>> await client2.subscribe_user_updates()  # Account 67890 events

        ProjectX Methods Called:
            - SubscribeAccounts: General account updates
            - SubscribeOrders: Order lifecycle events
            - SubscribePositions: Position changes
            - SubscribeTrades: Trade executions

        Note:
            - Account ID is converted to int for ProjectX API
            - All subscriptions are account-specific
            - Must re-subscribe after reconnection
        """
        with LogContext(
            logger,
            operation="subscribe_user_updates",
            account_id=self.account_id,
        ):
            if not self.user_connected:
                logger.error(
                    LogMessages.WS_ERROR, extra={"error": "User hub not connected"}
                )
                return False

            try:
                await asyncio.wait_for(self.user_hub_ready.wait(), timeout=5.0)
            except TimeoutError:
                logger.error(
                    LogMessages.WS_ERROR,
                    extra={"error": "User hub not ready for subscriptions after 5s"},
                )
                return False

            logger.debug(
                LogMessages.DATA_SUBSCRIBE,
                extra={"channel": "user_updates", "account_id": self.account_id},
            )
            if self.user_connection is None:
                logger.error(
                    LogMessages.WS_ERROR,
                    extra={"error": "User connection not available"},
                )
                return False

            await invoke_maybe(self.user_connection.send, "SubscribeAccounts", [])
            await invoke_maybe(
                self.user_connection.send, "SubscribeOrders", [int(self.account_id)]
            )
            await invoke_maybe(
                self.user_connection.send, "SubscribePositions", [int(self.account_id)]
            )
            await invoke_maybe(
                self.user_connection.send, "SubscribeTrades", [int(self.account_id)]
            )

            logger.debug(
                LogMessages.DATA_SUBSCRIBE,
                extra={"status": "success", "channel": "user_updates"},
            )
            return True

    @handle_errors("subscribe market data", reraise=False, default_return=False)
    async def subscribe_market_data(
        self: "ProjectXRealtimeClientProtocol", contract_ids: list[str]
    ) -> bool:
        """
        Subscribe to market data for specific contracts.

        Enables real-time streaming of quotes, trades, and market depth for specified
        contracts. Each contract receives all three data types automatically.

        Args:
            contract_ids (list[str]): List of ProjectX contract IDs to subscribe.
                Can be symbol names or full contract IDs.
                Examples: ["MGC", "NQ"] or ["CON.F.US.MGC.M25", "CON.F.US.NQ.M25"]

        Returns:
            bool: True if all subscriptions successful, False otherwise

        Data Types Subscribed:
            - Quotes: Bid/ask prices, sizes, and timestamps
            - Trades: Executed trades with price, size, and aggressor
            - Market Depth: Full order book with multiple price levels

        Example:
            >>> # Subscribe to single contract
            >>> await client.subscribe_market_data(["MNQ"])
            >>>
            >>> # Subscribe to multiple contracts
            >>> contracts = ["MNQ", "ES", "NQ", "YM"]
            >>> if await client.subscribe_market_data(contracts):
            ...     print(f"Subscribed to {len(contracts)} contracts")
            >>> # With data handling
            >>> async def on_quote(data):
            ...     contract = data["contract_id"]
            ...     quote = data["data"]
            ...     print(f"{contract}: {quote['bid']} x {quote['ask']}")
            >>> await client.add_callback("quote_update", on_quote)
            >>> await client.subscribe_market_data(["MGC"])
            >>> # Add contracts dynamically
            >>> await client.subscribe_market_data(["ES"])  # Adds to existing

        ProjectX Methods Called:
            - SubscribeContractQuotes: Real-time bid/ask
            - SubscribeContractTrades: Executed trades
            - SubscribeContractMarketDepth: Order book

        Side Effects:
            - Adds contracts to self._subscribed_contracts for reconnection
            - Triggers immediate data flow for liquid contracts

        Note:
            - Subscriptions are additive - doesn't unsubscribe existing
            - Duplicate subscriptions are filtered automatically
            - Contract IDs are case-sensitive
        """
        with LogContext(
            logger,
            operation="subscribe_market_data",
            contract_count=len(contract_ids),
            contracts=contract_ids[:5],  # Log first 5 contracts
        ):
            if not self.market_connected:
                logger.error(
                    LogMessages.WS_ERROR, extra={"error": "Market hub not connected"}
                )
                return False

            try:
                await asyncio.wait_for(self.market_hub_ready.wait(), timeout=5.0)
            except TimeoutError:
                logger.error(
                    LogMessages.WS_ERROR,
                    extra={"error": "Market hub not ready for subscriptions after 5s"},
                )
                return False

            logger.debug(
                LogMessages.DATA_SUBSCRIBE,
                extra={"channel": "market_data", "count": len(contract_ids)},
            )

            # Store for reconnection (avoid duplicates)
            for contract_id in contract_ids:
                if contract_id not in self._subscribed_contracts:
                    self._subscribed_contracts.append(contract_id)

            for contract_id in contract_ids:
                if self.market_connection is None:
                    logger.error(
                        LogMessages.WS_ERROR,
                        extra={"error": "Market connection not available"},
                    )
                    return False

                try:
                    await invoke_maybe(
                        self.market_connection.send,
                        "SubscribeContractQuotes",
                        [contract_id],
                    )
                    await invoke_maybe(
                        self.market_connection.send,
                        "SubscribeContractTrades",
                        [contract_id],
                    )
                    await invoke_maybe(
                        self.market_connection.send,
                        "SubscribeContractMarketDepth",
                        [contract_id],
                    )
                except Exception as e:
                    logger.error(
                        LogMessages.WS_ERROR,
                        extra={"error": f"Failed to subscribe to {contract_id}: {e!s}"},
                    )
                    return False

            logger.debug(
                LogMessages.DATA_SUBSCRIBE,
                extra={
                    "status": "success",
                    "channel": "market_data",
                    "count": len(contract_ids),
                },
            )
            return True

    @handle_errors("unsubscribe user updates", reraise=False, default_return=False)
    async def unsubscribe_user_updates(self: "ProjectXRealtimeClientProtocol") -> bool:
        """
        Unsubscribe from all user-specific real-time updates.

        Stops real-time streaming of account-specific events. Useful for reducing
        bandwidth or switching accounts. Callbacks remain registered.

        Returns:
            bool: True if unsubscription successful, False otherwise

        Example:
            >>> # Temporary pause
            >>> await client.unsubscribe_user_updates()
            >>> # ... do something else ...
            >>> await client.subscribe_user_updates()  # Re-enable
            >>>
            >>> # Clean shutdown
            >>> await client.unsubscribe_user_updates()
            >>> await client.disconnect()

        Note:
            - Does not remove registered callbacks
            - Can re-subscribe without re-registering callbacks
            - Stops events for: accounts, positions, orders, trades
        """
        with LogContext(
            logger,
            operation="unsubscribe_user_updates",
            account_id=self.account_id,
        ):
            if not self.user_connected:
                logger.error(
                    LogMessages.WS_ERROR, extra={"error": "User hub not connected"}
                )
                return False

            if self.user_connection is None:
                logger.error(
                    LogMessages.WS_ERROR,
                    extra={"error": "User connection not available"},
                )
                return False

            logger.debug(
                LogMessages.DATA_UNSUBSCRIBE, extra={"channel": "user_updates"}
            )
            account_id_arg = [int(self.account_id)]
            await invoke_maybe(
                self.user_connection.send, "UnsubscribeAccounts", account_id_arg
            )
            await invoke_maybe(
                self.user_connection.send, "UnsubscribeOrders", account_id_arg
            )
            await invoke_maybe(
                self.user_connection.send, "UnsubscribePositions", account_id_arg
            )
            await invoke_maybe(
                self.user_connection.send, "UnsubscribeTrades", account_id_arg
            )

            logger.debug(
                LogMessages.DATA_UNSUBSCRIBE,
                extra={"status": "success", "channel": "user_updates"},
            )
            return True

    @handle_errors("unsubscribe market data", reraise=False, default_return=False)
    async def unsubscribe_market_data(
        self: "ProjectXRealtimeClientProtocol", contract_ids: list[str]
    ) -> bool:
        """
        Unsubscribe from market data for specific contracts.

        Stops real-time streaming for specified contracts. Other subscribed
        contracts continue to stream. Useful for dynamic subscription management.

        Args:
            contract_ids (list[str]): List of contract IDs to unsubscribe.
                Should match the IDs used in subscribe_market_data().

        Returns:
            bool: True if unsubscription successful, False otherwise

        Example:
            >>> # Unsubscribe specific contracts
            >>> await client.unsubscribe_market_data(["MNQ", "ES"])
            >>>
            >>> # Dynamic subscription management
            >>> active_contracts = ["ES", "NQ", "YM", "RTY"]
            >>> await client.subscribe_market_data(active_contracts)
            >>> # Later, reduce to just ES and NQ
            >>> await client.unsubscribe_market_data(["YM", "RTY"])
            >>>
            >>> # Unsubscribe all tracked contracts
            >>> all_contracts = client._subscribed_contracts.copy()
            >>> await client.unsubscribe_market_data(all_contracts)

        Side Effects:
            - Removes contracts from self._subscribed_contracts
            - Stops quotes, trades, and depth for specified contracts

        Note:
            - Only affects specified contracts
            - Callbacks remain registered for future subscriptions
            - Safe to call with non-subscribed contracts
        """
        with LogContext(
            logger,
            operation="unsubscribe_market_data",
            contract_count=len(contract_ids),
            contracts=contract_ids[:5],
        ):
            if not self.market_connected:
                logger.error(
                    LogMessages.WS_ERROR, extra={"error": "Market hub not connected"}
                )
                return False

            logger.debug(
                LogMessages.DATA_UNSUBSCRIBE,
                extra={"channel": "market_data", "count": len(contract_ids)},
            )

            # Remove from stored contracts
            for contract_id in contract_ids:
                if contract_id in self._subscribed_contracts:
                    self._subscribed_contracts.remove(contract_id)

            if self.market_connection is None:
                logger.error(
                    LogMessages.WS_ERROR,
                    extra={"error": "Market connection not available"},
                )
                return False

            await invoke_maybe(
                self.market_connection.send, "UnsubscribeContractQuotes", contract_ids
            )
            await invoke_maybe(
                self.market_connection.send, "UnsubscribeContractTrades", contract_ids
            )
            await invoke_maybe(
                self.market_connection.send,
                "UnsubscribeContractMarketDepth",
                contract_ids,
            )

            logger.debug(
                LogMessages.DATA_UNSUBSCRIBE,
                extra={
                    "status": "success",
                    "channel": "market_data",
                    "count": len(contract_ids),
                },
            )
            return True
