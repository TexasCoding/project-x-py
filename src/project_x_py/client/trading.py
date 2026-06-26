"""
Async trading queries: positions and trade history for ProjectX accounts.

Author: @TexasCoding
Date: 2025-08-02

Overview:
    Supplies async methods for querying open positions and executed trades for the currently
    authenticated account. Integrates tightly with the authentication/session lifecycle and
    other mixins, enabling streamlined access to P&L, trade analysis, and reporting data.
    All queries require a valid session and leverage ProjectX's unified API request logic.

Key Features:
    - Query current open positions for the selected account
    - Search historical trades with flexible date range and contract filters
    - Async error handling and robust integration with authentication
    - Typed results as Position and Trade model objects for analysis/reporting
    - Designed for use in trading bots, dashboards, and research scripts

Example Usage:
    ```python
    import asyncio
    from datetime import datetime, timedelta
    from project_x_py import ProjectX


    async def main():
        # V3: Query trading data asynchronously
        async with ProjectX.from_env() as client:
            await client.authenticate()

            # Get current open positions
            positions = await client.search_open_positions()
            for pos in positions:
                print(f"Position: {pos.contractId}")
                print(f"  Size: {pos.netPos}")
                print(f"  Avg Price: ${pos.buyAvgPrice:.2f}")
                print(f"  Unrealized P&L: ${pos.unrealizedPnl:.2f}")

            # Get recent trades (last 7 days)
            start_date = datetime.now() - timedelta(days=7)
            trades = await client.search_trades(start_date=start_date, limit=50)

            # Analyze trades by contract
            contracts = {}
            for trade in trades:
                if trade.contractId not in contracts:
                    contracts[trade.contractId] = []
                contracts[trade.contractId].append(trade)

            for contract_id, contract_trades in contracts.items():
                total_volume = sum(abs(t.filledQty) for t in contract_trades)
                print(
                    f"{contract_id}: {len(contract_trades)} trades, volume: {total_volume}"
                )


    asyncio.run(main())
    ```

See Also:
    - `project_x_py.client.auth.AuthenticationMixin`
    - `project_x_py.client.base.ProjectXBase`
    - `project_x_py.client.market_data.MarketDataMixin`
"""

import datetime
import logging
from datetime import timedelta
from typing import Any

import pytz

from project_x_py.exceptions import ProjectXError
from project_x_py.models import Position, Trade
from project_x_py.utils.deprecation import deprecated

logger = logging.getLogger(__name__)


class TradingMixin:
    """Mixin class providing trading functionality."""

    # These attributes are provided by the base class
    account_info: Any  # Account object

    async def _ensure_authenticated(self) -> None:
        """Provided by AuthenticationMixin."""

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        retry_count: int = 0,
    ) -> Any:
        """Provided by HttpMixin."""
        _ = (method, endpoint, data, params, headers, retry_count)

    @deprecated(
        reason="Method renamed for API consistency",
        version="3.0.0",
        removal_version="4.0.0",
        replacement="search_open_positions()",
    )
    async def get_positions(self) -> list[Position]:
        """
        DEPRECATED: Get all open positions for the authenticated account.

        This method is deprecated and will be removed in a future version.
        Please use `search_open_positions()` instead, which provides the same
        functionality with a more consistent API endpoint.

        Args:
            self: The client instance.

        Returns:
            A list of Position objects representing current holdings.
        """
        # Deprecation warning handled by decorator
        return await self.search_open_positions()

    async def search_open_positions(
        self, account_id: int | None = None
    ) -> list[Position]:
        """
        Search for open positions for the currently authenticated account.

        This is the recommended method for retrieving all current open positions.
        It provides a snapshot of the portfolio including position size, entry price,
        unrealized P&L, and other key details.

        Args:
            account_id: Optional account ID to filter positions. If not provided,
                the currently authenticated account's ID will be used.

        Returns:
            List of Position objects representing current holdings.

        Raises:
            ProjectXError: If no account is selected or the API call fails.

        Example:
            >>> # V3: Search open positions with P&L calculation
            >>> positions = await client.search_open_positions()
            >>> # Calculate total P&L
            >>> total_unrealized = sum(pos.unrealizedPnl for pos in positions)
            >>> total_realized = sum(pos.realizedPnl for pos in positions)
            >>> print(f"Open positions: {len(positions)}")
            >>> print(f"Total Unrealized P&L: ${total_unrealized:,.2f}")
            >>> print(f"Total Realized P&L: ${total_realized:,.2f}")
            >>> print(f"Total P&L: ${total_unrealized + total_realized:,.2f}")
        """
        await self._ensure_authenticated()

        # Use the account_id from the authenticated account if not provided
        if account_id is None and self.account_info:
            account_id = self.account_info.id

        if account_id is None:
            raise ProjectXError("No account ID available for position search")

        payload = {"accountId": account_id}
        response = await self._make_request(
            "POST", "/Position/searchOpen", data=payload
        )

        # Handle both list response (new API) and dict response (legacy)
        if response is None:
            return []

        # If response is a list, use it directly
        if isinstance(response, list):
            positions_data = response
        # If response is a dict with success/positions structure
        elif isinstance(response, dict):
            if not response.get("success", False):
                return []
            positions_data = response.get("positions", [])
        else:
            return []

        return [Position(**pos) for pos in positions_data]

    async def search_trades(
        self,
        start_date: datetime.datetime | None = None,
        end_date: datetime.datetime | None = None,
        contract_id: str | None = None,
        account_id: int | None = None,
        limit: int = 100,
    ) -> list[Trade]:
        """
        Search trade execution history for analysis and reporting.

        Retrieves executed trades within the specified date range, useful for
        performance analysis, tax reporting, and strategy evaluation.

        Args:
            start_date: Start date for trade search (default: 30 days ago)
            end_date: End date for trade search (default: now)
            contract_id: Optional contract ID filter for specific instrument
            account_id: Account ID to search (uses default account if None)
            limit: Maximum number of trades to return (default: 100)

        Returns:
            List[Trade]: List of executed trades with detailed information including:
                - contractId: Instrument that was traded
                - size: Trade size (positive=buy, negative=sell)
                - price: Execution price
                - timestamp: Execution time
                - commission: Trading fees

        Raises:
            ProjectXError: If trade search fails or no account information available

        Example:
            >>> # V3: Search and analyze trade history
            >>> from datetime import datetime, timedelta
            >>> import pytz
            >>> # Get last 7 days of trades
            >>> end_date = datetime.now(pytz.UTC)
            >>> start_date = end_date - timedelta(days=7)
            >>> trades = await client.search_trades(
            ...     start_date=start_date, end_date=end_date, limit=100
            ... )
            >>> # Analyze trades
            >>> total_volume = 0
            >>> total_commission = 0
            >>> for trade in trades:
            >>>     print(f"Trade ID: {trade.id}")
            >>>     print(f"  Contract: {trade.contractId}")
            >>>     print(f"  Side: {'BUY' if trade.filledQty > 0 else 'SELL'}")
            >>>     print(f"  Quantity: {abs(trade.filledQty)}")
            >>>     print(f"  Price: ${trade.fillPrice:.2f}")
            >>>     print(f"  Commission: ${trade.commission:.2f}")
            >>>     print(f"  Time: {trade.fillTime}")
            >>>     total_volume += abs(trade.filledQty)
            >>>     total_commission += trade.commission
            >>> print(f"\nSummary:")
            >>> print(f"Total trades: {len(trades)}")
            >>> print(f"Total volume: {total_volume}")
            >>> print(f"Total commission: ${total_commission:.2f}")
        """
        await self._ensure_authenticated()

        if account_id is None:
            if not self.account_info:
                raise ProjectXError("No account information available")
            account_id = self.account_info.id

        # Default date range
        if end_date is None:
            end_date = datetime.datetime.now(pytz.UTC)
        if start_date is None:
            start_date = end_date - timedelta(days=30)

        # Prepare request payload for Gateway API
        payload = {
            "accountId": account_id,
            "startTimestamp": start_date.isoformat(),
            "endTimestamp": end_date.isoformat(),
        }

        if contract_id:
            payload["contractId"] = contract_id

        response = await self._make_request("POST", "/Trade/search", data=payload)

        if response is None:
            return []

        if isinstance(response, list):
            trades_data = response
        elif isinstance(response, dict):
            if not response.get("success", False):
                return []
            trades_data = response.get("trades", [])
        else:
            return []

        return [Trade(**trade) for trade in trades_data[:limit]]
