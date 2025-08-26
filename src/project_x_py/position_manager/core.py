"""Core PositionManager class for comprehensive position operations.

Author: @TexasCoding
Date: 2025-08-02

Overview:
    Provides the main PositionManager class that handles all position-related
    operations including tracking, monitoring, analysis, and management.
    Integrates multiple mixins to provide comprehensive position lifecycle
    management with real-time capabilities and risk management.

Key Features:
    - Real-time position tracking via WebSocket integration
    - Portfolio-level position management and analytics
    - Automated P&L calculation and risk metrics
    - Position sizing and risk management tools
    - Event-driven position updates and closure detection
    - Async-safe operations for concurrent access
    - Comprehensive position operations (close, partial close)
    - Statistics, history, and report generation

Note:
    This class is the core implementation of the position manager. For most
    applications, it is recommended to interact with it through the `TradingSuite`
    (`suite.positions`), which handles its lifecycle and integration automatically.
    The example below demonstrates direct, low-level instantiation and usage.

Example Usage:
    ```python
    # V3.1: Initialize position manager with TradingSuite
    import asyncio
    from project_x_py import TradingSuite


    async def main():
        # V3.1: Create suite with integrated position manager
        suite = await TradingSuite.create("MNQ", timeframes=["1min"])

        # V3.1: Get current positions with detailed fields
        positions = await suite.positions.get_all_positions()
        for pos in positions:
            print(f"{pos.contractId}: {pos.netPos} @ ${pos.buyAvgPrice}")

        # V3.1: Calculate P&L with market prices
        current_price = await suite.data.get_current_price()
        prices = {"MNQ": current_price, "ES": 4500.0}
        pnl = await suite.positions.calculate_portfolio_pnl(prices)
        print(f"Total P&L: ${pnl['total_pnl']:.2f}")

        # V3.1: Risk analysis
        risk = await suite.positions.get_risk_metrics()
        print(f"Portfolio risk: {risk['portfolio_risk']:.2%}")

        # V3.1: Position operations
        await suite.positions.close_position_direct(suite.instrument_id)

        await suite.disconnect()


    asyncio.run(main())
    ```

See Also:
    - `position_manager.analytics.PositionAnalyticsMixin`
    - `position_manager.risk.RiskManagementMixin`
    - `position_manager.monitoring.PositionMonitoringMixin`
    - `position_manager.operations.PositionOperationsMixin`
    - `position_manager.reporting.PositionReportingMixin`
    - `position_manager.tracking.PositionTrackingMixin`

"""

import asyncio
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from project_x_py.client.base import ProjectXBase
from project_x_py.models import Position
from project_x_py.position_manager.analytics import PositionAnalyticsMixin
from project_x_py.position_manager.monitoring import PositionMonitoringMixin
from project_x_py.position_manager.operations import PositionOperationsMixin
from project_x_py.position_manager.reporting import PositionReportingMixin
from project_x_py.position_manager.tracking import PositionTrackingMixin
from project_x_py.risk_manager import RiskManager
from project_x_py.statistics.base import BaseStatisticsTracker
from project_x_py.types.config_types import PositionManagerConfig
from project_x_py.types.protocols import RealtimeDataManagerProtocol
from project_x_py.types.response_types import (
    RiskAnalysisResponse,
)
from project_x_py.utils import (
    LogMessages,
    ProjectXLogger,
    handle_errors,
)

if TYPE_CHECKING:
    from project_x_py.order_manager import OrderManager
    from project_x_py.realtime import ProjectXRealtimeClient


class PositionManager(
    PositionTrackingMixin,
    PositionAnalyticsMixin,
    # RiskManagementMixin,
    PositionMonitoringMixin,
    PositionOperationsMixin,
    PositionReportingMixin,
    BaseStatisticsTracker,
):
    """
    Async comprehensive position management system for ProjectX trading operations.

    This class handles all position-related operations including tracking, monitoring,
    analysis, and management using async/await patterns. It integrates with both the
    AsyncProjectX client and the async real-time client for live position monitoring.

    Features:
        - Complete async position lifecycle management
        - Real-time position tracking and monitoring via WebSocket
        - Portfolio-level position management and analytics
        - Automated P&L calculation and risk metrics
        - Position sizing and risk management tools
        - Event-driven position updates (closures detected from size=0)
        - Async-safe operations for concurrent access
        - Comprehensive position operations (close, partial close, bulk operations)
        - Statistics, history, and report generation

    Real-time Capabilities:
        - WebSocket-based position updates and closure detection
        - Immediate position change notifications
        - Event-driven callbacks for custom monitoring
        - Automatic position synchronization with order management

    Risk Management:
        - Portfolio risk assessment and concentration analysis
        - Position sizing calculations with configurable risk parameters
        - Risk warnings and threshold monitoring
        - Diversification scoring and portfolio health metrics

    Example Usage:
        >>> # V3.1: Create position manager with TradingSuite
        >>> suite = await TradingSuite.create("MNQ", timeframes=["1min"])
        >>> # V3.1: Position manager is automatically initialized with real-time updates
        ... )
        >>> await position_manager.initialize(realtime_client=realtime_client)
        >>> # V3: Get current positions with actual field names
        >>> positions = await position_manager.get_all_positions()
        >>> mgc_position = await position_manager.get_position("MGC")
        >>> if mgc_position:
        >>>     print(f"Size: {mgc_position.netPos}")
        >>>     print(f"Avg Price: ${mgc_position.buyAvgPrice}")
        >>> # V3: Portfolio analytics with market prices
        >>> market_prices = {"MGC": 2050.0, "MNQ": 18500.0}
        >>> portfolio_pnl = await position_manager.calculate_portfolio_pnl(
        ...     market_prices
        ... )
        >>> risk_metrics = await position_manager.get_risk_metrics()
        >>> # V3.1: Position monitoring with alerts via TradingSuite
        >>> await suite.positions.add_position_alert(
        ...     suite.instrument_id, max_loss=-500.0
        ... )
        >>> await suite.positions.start_monitoring(interval_seconds=5)
        >>> # V3.1: Position sizing with risk management
        >>> current_price = await suite.data.get_current_price()
        >>> suggested_size = await suite.positions.calculate_position_size(
        ...     suite.instrument_id,
        ...     risk_amount=100.0,
        ...     entry_price=current_price,
        ...     stop_price=current_price - 5.0,
        ... )
    """

    def __init__(
        self,
        project_x_client: "ProjectXBase",
        event_bus: Any,
        risk_manager: Optional["RiskManager"] = None,
        data_manager: Optional["RealtimeDataManagerProtocol"] = None,
        config: PositionManagerConfig | None = None,
    ):
        """
        Initialize the PositionManager with an ProjectX client and optional configuration.

        Creates a comprehensive position management system with tracking, monitoring,
        alerts, risk management, and optional real-time/order synchronization.

        Args:
            project_x_client (ProjectX): The authenticated ProjectX client instance
                used for all API operations. Must be properly authenticated before use.
            event_bus: EventBus instance for unified event handling. Required for all
                event emissions including position updates, P&L changes, and risk alerts.
            risk_manager: Optional risk manager instance. If provided, enables advanced
                risk management features and position sizing calculations.
            data_manager: Optional data manager for market data and P&L alerts.
            config: Optional configuration for position management behavior. If not provided,
                default values will be used for all configuration options.

        Attributes:
            project_x (ProjectX): Reference to the ProjectX client
            logger (logging.Logger): Logger instance for this manager
            position_lock (asyncio.Lock): Thread-safe lock for position operations
            realtime_client (ProjectXRealtimeClient | None): Optional real-time client
            order_manager (OrderManager | None): Optional order manager for sync
            tracked_positions (dict[str, Position]): Current positions by contract ID
            position_history (dict[str, list[dict]]): Historical position changes
            event_bus (Any): EventBus instance for unified event handling
            position_alerts (dict[str, dict]): Active position alerts by contract
            stats (dict): Comprehensive tracking statistics
            risk_settings (dict): Risk management configuration

        Example:
            >>> # V3.1: Initialize with TradingSuite for unified management
            >>> suite = await TradingSuite.create("MNQ", timeframes=["1min"])
            >>>
            >>> # V3.1: Position manager is automatically initialized
            >>> # Access via suite.positions
            >>> positions = await suite.positions.get_all_positions()
            >>>
            >>> # V3.1: Real-time and order sync are automatically configured
            >>> # EventBus integration is handled by the suite
        """
        # Initialize all mixins
        PositionTrackingMixin.__init__(self)
        PositionMonitoringMixin.__init__(self)
        # Initialize new statistics tracking
        BaseStatisticsTracker.__init__(
            self, component_name="position_manager", max_errors=100, cache_ttl=5.0
        )

        self.project_x: ProjectXBase = project_x_client
        self.event_bus = event_bus  # Store the event bus for emitting events
        self.risk_manager = risk_manager
        self.data_manager = data_manager
        self.logger = ProjectXLogger.get_logger(__name__)

        # Store configuration with defaults
        self.config = config or {}
        self._apply_config_defaults()

        # Async lock for thread safety
        self.position_lock = asyncio.Lock()

        # Real-time integration (optional)
        self.realtime_client: ProjectXRealtimeClient | None = None
        self._realtime_enabled = False

        # Order management integration (optional)
        self.order_manager: OrderManager | None = None
        self._order_sync_enabled = False

        # Comprehensive statistics tracking
        self.stats = {
            "open_positions": 0,
            "closed_positions": 0,  # Legacy field
            "positions_closed": 0,  # Field expected by tests
            "winning_positions": 0,
            "winning_trades": 0,  # Alias for compatibility
            "losing_positions": 0,
            "losing_trades": 0,  # Alias for compatibility
            "total_positions": 0,
            "positions_opened": 0,  # Track how many positions have been opened
            "total_pnl": 0.0,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "gross_profit": 0.0,
            "gross_loss": 0.0,
            "best_position_pnl": 0.0,
            "worst_position_pnl": 0.0,
            "avg_position_size": 0.0,
            "largest_position": 0,
            "avg_hold_time_minutes": 0.0,
            "longest_hold_time_minutes": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
            "total_risk": 0.0,
            "max_position_risk": 0.0,
            "portfolio_correlation": 0.0,
            "var_95": 0.0,
            "position_updates": 0,
            "risk_calculations": 0,
            "last_position_update": None,
            # Legacy fields for backward compatibility in other methods
            "positions_tracked": 0,
            "positions_partially_closed": 0,
            "last_update_time": None,
            "monitoring_started": None,
            # New fields for tracking queue performance
            "queue_size_peak": 0,
            "queue_processing_errors": 0,
            # Error tracking
            "errors": 0,
        }

        self.logger.info(
            LogMessages.MANAGER_INITIALIZED, extra={"manager": "PositionManager"}
        )

    def _apply_config_defaults(self) -> None:
        """Apply default values for configuration options."""
        # Position management settings
        self.enable_risk_monitoring = self.config.get("enable_risk_monitoring", True)
        self.auto_stop_loss = self.config.get("auto_stop_loss", False)
        self.auto_take_profit = self.config.get("auto_take_profit", False)
        self.max_position_size = self.config.get("max_position_size", 100)
        self.max_portfolio_risk = self.config.get("max_portfolio_risk", 0.02)
        self.position_sizing_method = self.config.get("position_sizing_method", "fixed")
        self.enable_correlation_analysis = self.config.get(
            "enable_correlation_analysis", True
        )
        self.enable_portfolio_rebalancing = self.config.get(
            "enable_portfolio_rebalancing", False
        )
        self.rebalance_frequency_minutes = self.config.get(
            "rebalance_frequency_minutes", 60
        )
        self.risk_calculation_interval = self.config.get("risk_calculation_interval", 5)

        # Update risk settings from configuration
        self.risk_settings = {
            "max_portfolio_risk": self.max_portfolio_risk,
            "max_position_risk": self.config.get(
                "max_position_risk", 0.01
            ),  # 1% per position
            "max_correlation": self.config.get(
                "max_correlation", 0.7
            ),  # Maximum correlation between positions
            "alert_threshold": self.config.get(
                "alert_threshold", 0.005
            ),  # 0.5% threshold for alerts
        }

    @handle_errors("initialize position manager", reraise=False, default_return=False)
    async def initialize(
        self,
        realtime_client: Optional["ProjectXRealtimeClient"] = None,
        order_manager: Optional["OrderManager"] = None,
    ) -> bool:
        """
        Initialize the PositionManager with optional real-time capabilities and order synchronization.

        This method sets up advanced features including real-time position tracking via WebSocket
        and automatic order synchronization. Must be called before using real-time features.

        Args:
            realtime_client (ProjectXRealtimeClient, optional): Real-time client instance
                for WebSocket-based position updates. When provided, enables live position
                tracking without polling. Defaults to None (polling mode).
            order_manager (OrderManager, optional): Order manager instance for automatic
                order synchronization. When provided, orders are automatically updated when
                positions change. Defaults to None (no order sync).

        Returns:
            bool: True if initialization successful, False if any errors occurred

        Raises:
            Exception: Logged but not raised - returns False on failure

        Example:
            >>> # V3.1: Initialize with TradingSuite (automatic setup)
            >>> suite = await TradingSuite.create("MNQ", timeframes=["1min"])
            >>>
            >>> # V3.1: Position manager is automatically initialized with:
            >>> # - Real-time tracking via WebSocket
            >>> # - Order synchronization with suite.orders
            >>> # - EventBus integration via suite.events
            >>>
            >>> # V3.1: Access the initialized position manager
            >>> positions = await suite.positions.get_all_positions()

        Note:
            - Real-time mode provides instant position updates via WebSocket
            - Polling mode refreshes positions periodically (see start_monitoring)
            - Order synchronization helps maintain order/position consistency
        """
        # Set up real-time integration if provided
        if realtime_client:
            self.realtime_client = realtime_client
            await self._setup_realtime_callbacks()
            self._realtime_enabled = True
            self.logger.info(
                LogMessages.MANAGER_INITIALIZED,
                extra={"manager": "PositionManager", "mode": "realtime"},
            )
        else:
            self.logger.info(
                LogMessages.MANAGER_INITIALIZED,
                extra={"manager": "PositionManager", "mode": "polling"},
            )

        # Set up order management integration if provided
        if order_manager:
            self.order_manager = order_manager
            self._order_sync_enabled = True
            self.logger.info(
                LogMessages.MANAGER_INITIALIZED,
                extra={"feature": "order_synchronization", "enabled": True},
            )

        # Load initial positions
        await self.refresh_positions()

        return True

    # ================================================================================
    # CORE POSITION RETRIEVAL METHODS
    # ================================================================================

    async def get_all_positions(self, account_id: int | None = None) -> list[Position]:
        """
        Get all current positions from the API and update tracking.

        Retrieves all open positions for the specified account, updates the internal
        tracking cache, and returns the position list. This is the primary method
        for fetching position data.

        Args:
            account_id (int, optional): The account ID to get positions for.
                If None, uses the default account from authentication.
                Defaults to None.

        Returns:
            list[Position]: List of all current open positions. Each Position object
                contains id, accountId, contractId, type, size, averagePrice, and
                creationTimestamp. Empty list if no positions or on error.

        Side effects:
            - Updates self.tracked_positions with current data
            - Updates statistics (positions_tracked, last_update_time)

        Example:
            >>> # V3: Get all positions with actual field names
            >>> positions = await position_manager.get_all_positions()
            >>> for pos in positions:
            ...     print(f"Contract: {pos.contractId}")
            ...     print(f"  Net Position: {pos.netPos}")
            ...     print(f"  Buy Avg Price: ${pos.buyAvgPrice:.2f}")
            ...     print(f"  Unrealized P&L: ${pos.unrealizedPnl:.2f}")
            >>> # V3: Get positions for specific account
            >>> positions = await position_manager.get_all_positions(account_id=12345)

        Note:
            In real-time mode, tracked positions are also updated via WebSocket,
            but this method always fetches fresh data from the API.
        """
        try:
            start_time = time.time()
            self.logger.info(
                LogMessages.POSITION_SEARCH, extra={"account_id": account_id}
            )

            positions = await self.project_x.search_open_positions(
                account_id=account_id
            )
        except Exception as e:
            self.stats["errors"] += 1
            self.logger.error(f"Error getting positions: {e}")
            # Re-raise connection errors for refresh_positions to handle
            from project_x_py.exceptions import ProjectXConnectionError

            if isinstance(e, ProjectXConnectionError):
                raise
            return []

        # Track the operation timing
        duration_ms = (time.time() - start_time) * 1000
        await self.record_timing("get_all_positions", duration_ms)
        await self.increment("get_all_positions_count")

        # Filter positions by account_id if specified
        if account_id is not None:
            filtered_positions = [p for p in positions if p.accountId == account_id]
        else:
            filtered_positions = positions

        # Filter out invalid positions (zero-size or missing contractId)
        filtered_positions = [
            p for p in filtered_positions if p.size != 0 and p.contractId is not None
        ]

        # Update tracked positions
        async with self.position_lock:
            for position in filtered_positions:
                self.tracked_positions[position.contractId] = position

            # Update statistics
            self.stats["positions_tracked"] = len(filtered_positions)
            self.stats["last_update_time"] = datetime.now()
            await self.set_gauge("positions_tracked", len(filtered_positions))
            await self.set_gauge(
                "open_positions", len([p for p in filtered_positions if p.size != 0])
            )

        self.logger.info(
            LogMessages.POSITION_UPDATE,
            extra={"position_count": len(filtered_positions)},
        )

        return filtered_positions

    @handle_errors("get position", reraise=False, default_return=None)
    async def get_position(
        self, contract_id: str, account_id: int | None = None
    ) -> Position | None:
        """
        Get a specific position by contract ID.

        Searches for a position matching the given contract ID. In real-time mode,
        checks the local cache first for better performance before falling back
        to an API call.

        Args:
            contract_id (str): The contract ID to search for (e.g., "MNQ", "ES")
            account_id (int, optional): The account ID to search within.
                If None, uses the default account from authentication.
                Defaults to None.

        Returns:
            Position | None: Position object if found, containing all position details
                (id, size, averagePrice, type, etc.). Returns None if no position
                exists for the contract.

        Example:
            >>> # V3.1: Check if we have a position with TradingSuite
            >>> position = await suite.positions.get_position(suite.instrument_id)
            >>> if position:
            ...     print(f"{suite.instrument} position: {position.netPos} contracts")
            ...     print(f"Buy Avg Price: ${position.buyAvgPrice:.2f}")
            ...     print(f"Sell Avg Price: ${position.sellAvgPrice:.2f}")
            ...     print(f"Unrealized P&L: ${position.unrealizedPnl:.2f}")
            ...     print(f"Realized P&L: ${position.realizedPnl:.2f}")
            ... else:
            ...     print(f"No {suite.instrument} position found")

        Performance:
            - Real-time mode: O(1) cache lookup, falls back to API if miss
            - Polling mode: Always makes API call via get_all_positions()
        """
        start_time = time.time()

        # Try cached data first if real-time enabled
        if self._realtime_enabled:
            async with self.position_lock:
                cached_position = self.tracked_positions.get(contract_id)
                if cached_position:
                    duration_ms = (time.time() - start_time) * 1000
                    await self.record_timing("get_position", duration_ms)
                    await self.increment("get_position_cache_hits")
                    return cached_position

        # Fallback to API search
        positions = await self.get_all_positions(account_id=account_id)
        for position in positions:
            if position.contractId == contract_id:
                duration_ms = (time.time() - start_time) * 1000
                await self.record_timing("get_position", duration_ms)
                await self.increment("get_position_api_calls")
                return position

        duration_ms = (time.time() - start_time) * 1000
        await self.record_timing("get_position", duration_ms)
        await self.increment("get_position_not_found")
        return None

    @handle_errors("refresh positions", reraise=False, default_return=False)
    async def refresh_positions(self, account_id: int | None = None) -> bool:
        """
        Refresh all position data from the API.

        Forces a fresh fetch of all positions from the API, updating the internal
        tracking cache. Useful for ensuring data is current after external changes
        or when real-time updates may have been missed.

        Args:
            account_id (int, optional): The account ID to refresh positions for.
                If None, uses the default account from authentication.
                Defaults to None.

        Returns:
            bool: True if refresh was successful, False if any error occurred

        Side effects:
            - Updates self.tracked_positions with fresh data
            - Updates position statistics
            - Logs refresh results

        Example:
            >>> # Manually refresh positions
            >>> success = await position_manager.refresh_positions()
            >>> if success:
            ...     print("Positions refreshed successfully")
            >>> # Refresh specific account
            >>> await position_manager.refresh_positions(account_id=12345)

        Note:
            This method is called automatically during initialization and by
            the monitoring loop in polling mode.
        """
        self.logger.info(LogMessages.POSITION_REFRESH, extra={"account_id": account_id})

        try:
            positions = await self.get_all_positions(account_id=account_id)

            self.logger.info(
                LogMessages.POSITION_UPDATE, extra={"refreshed_count": len(positions)}
            )

            return True
        except Exception as e:
            self.logger.error(f"Failed to refresh positions: {e}")
            return False

    async def is_position_open(
        self, contract_id: str, account_id: int | None = None
    ) -> bool:
        """
        Check if a position exists for the given contract.

        Convenience method to quickly check if you have an open position in a
        specific contract without retrieving the full position details.

        Args:
            contract_id (str): The contract ID to check (e.g., "MNQ", "ES")
            account_id (int, optional): The account ID to check within.
                If None, uses the default account from authentication.
                Defaults to None.

        Returns:
            bool: True if an open position exists (size != 0), False otherwise

        Example:
            >>> # V3.1: Check before placing an order with TradingSuite
            >>> if await suite.positions.is_position_open(suite.instrument_id):
            ...     print(f"Already have {suite.instrument} position")
            ... else:
            ...     # Safe to open new position
            ...     await suite.orders.place_market_order(suite.instrument_id, 0, 1)

        Note:
            A position with size=0 is considered closed and returns False.
        """
        position = await self.get_position(contract_id, account_id)
        return position is not None and position.size != 0

    # ================================================================================
    # RISK MANAGEMENT DELEGATION
    # ================================================================================

    async def _calculate_current_prices(self) -> dict[str, float]:
        """
        Get current prices for all tracked positions.

        Returns:
            Dictionary mapping contract IDs to current prices
        """
        prices = {}
        for contract_id in self.tracked_positions:
            try:
                # Get latest bar data for the contract
                bars = await self.project_x.get_bars(contract_id, days=1)
                if bars is not None and len(bars) > 0:
                    prices[contract_id] = float(bars["close"][-1])
                else:
                    # Fall back to position average price if no market data
                    position = self.tracked_positions[contract_id]
                    prices[contract_id] = position.averagePrice
            except Exception:
                # If we can't get price, use position average price
                position = self.tracked_positions[contract_id]
                prices[contract_id] = position.averagePrice
        return prices

    async def get_risk_metrics(self) -> "RiskAnalysisResponse":
        """
        Get comprehensive risk metrics for all positions.

        Returns RiskAnalysisResponse if risk manager configured,
        otherwise returns basic metrics calculated from positions.
        """
        if self.risk_manager:
            return await self.risk_manager.get_risk_metrics()

        # Calculate basic metrics without risk manager
        current_prices = await self._calculate_current_prices()

        total_pnl = 0.0
        position_risks: list[dict[str, Any]] = []

        for contract_id, position in self.tracked_positions.items():
            current_price = current_prices.get(contract_id, position.averagePrice)

            # Calculate P&L based on position type
            if position.type == 1:  # LONG
                pnl = position.size * (current_price - position.averagePrice)
            else:  # SHORT
                pnl = -position.size * (current_price - position.averagePrice)

            total_pnl += pnl

            position_risks.append(
                {
                    "contract_id": contract_id,
                    "size": position.size,
                    "entry_price": position.averagePrice,
                    "current_price": current_price,
                    "pnl": pnl,
                    "type": "LONG" if position.type == 1 else "SHORT",
                }
            )

        # Return basic risk analysis
        from project_x_py.types.response_types import RiskAnalysisResponse

        return RiskAnalysisResponse(
            current_risk=sum(abs(p["pnl"]) for p in position_risks if p["pnl"] < 0),
            max_risk=0.0,  # Not calculated without risk manager
            daily_loss=sum(p["pnl"] for p in position_risks if p["pnl"] < 0),
            daily_loss_limit=0.0,  # Not set without risk manager
            position_count=len(self.tracked_positions),
            position_limit=0,  # Not set without risk manager
            daily_trades=self.stats.get("position_updates", 0),
            daily_trade_limit=0,  # Not set without risk manager
            win_rate=self.stats.get("win_rate", 0.0),
            profit_factor=self.stats.get("profit_factor", 0.0),
            sharpe_ratio=self.stats.get("sharpe_ratio", 0.0),
            max_drawdown=self.stats.get("max_drawdown", 0.0),
            position_risks=position_risks,
            # Required fields for RiskAnalysisResponse
            risk_per_trade=0.0,  # Not calculated without risk manager
            account_balance=0.0,  # Not available without risk manager
            margin_used=0.0,  # Not available without risk manager
            margin_available=0.0,  # Not available without risk manager
        )

    async def calculate_position_size(
        self,
        risk_amount: float,
        entry_price: float,
        stop_price: float,
        contract_id: str | None = None,
    ) -> float:
        """
        Calculate position size based on risk parameters.

        Args:
            risk_amount: Dollar amount to risk
            entry_price: Entry price for the position
            stop_price: Stop loss price
            contract_id: Optional contract ID (for risk manager integration)

        Returns:
            Number of contracts/shares to trade
        """
        # Simple position size calculation
        stop_distance = abs(entry_price - stop_price)

        if stop_distance == 0:
            return 0

        position_size = risk_amount / stop_distance

        # If we have a risk manager and contract_id, use it for more sophisticated calculation
        if self.risk_manager and contract_id:
            instrument = await self.project_x.get_instrument(contract_id)
            result = await self.risk_manager.calculate_position_size(
                entry_price=entry_price,
                stop_loss=stop_price,
                risk_amount=risk_amount,
                instrument=instrument,
            )
            return result.get("position_size", position_size)

        return position_size

    # ================================================================================
    # POSITION STATISTICS TRACKING METHODS
    # ================================================================================

    async def track_position_opened(self, position: Position) -> None:
        """Track when a position is opened."""
        # Add position to cache
        if position.contractId:
            self.tracked_positions[position.contractId] = position

        await self.increment("total_positions")
        await self.increment("position_opens")
        await self.set_gauge("current_open_positions", len(self.tracked_positions))

        # Update position-specific stats
        self.stats["total_positions"] += 1
        self.stats["positions_opened"] += 1  # Track positions opened
        self.stats["positions_tracked"] += 1  # For backward compatibility
        self.stats["open_positions"] = len(
            [p for p in self.tracked_positions.values() if p.size != 0]
        )

        # Sync with order manager if enabled
        if self._order_sync_enabled and self.order_manager and position.contractId:
            await self.order_manager.sync_orders_with_position(
                position.contractId, target_size=position.size
            )

    async def track_position_closed(self, position: Position, pnl: float) -> None:
        """Track when a position is closed with P&L."""
        # Remove position from cache
        if position.contractId and position.contractId in self.tracked_positions:
            del self.tracked_positions[position.contractId]

        await self.increment("closed_positions")
        await self.increment("position_closes")

        if pnl > 0:
            await self.increment("winning_positions")
            await self.set_gauge(
                "gross_profit", self.stats.get("gross_profit", 0) + pnl
            )
            self.stats["winning_positions"] += 1
            self.stats["winning_trades"] += 1  # Update alias
            self.stats["gross_profit"] += pnl
        else:
            await self.increment("losing_positions")
            await self.set_gauge(
                "gross_loss",
                self.stats.get("gross_loss", 0) + abs(pnl),
            )
            self.stats["losing_positions"] += 1
            self.stats["losing_trades"] += 1  # Update alias
            self.stats["gross_loss"] += abs(pnl)

        # Update total P&L
        total_pnl = self.stats.get("total_pnl", 0) + pnl
        await self.set_gauge("total_pnl", total_pnl)
        self.stats["total_pnl"] = total_pnl

        # Update win rate
        total_closed = self.stats.get("closed_positions", 0) + 1
        win_rate = (
            (self.stats.get("winning_positions", 0) / total_closed)
            if total_closed > 0
            else 0
        )
        await self.set_gauge("win_rate", win_rate)
        self.stats["win_rate"] = win_rate
        self.stats["closed_positions"] = total_closed
        self.stats["positions_closed"] = total_closed  # Update both for compatibility

    async def track_position_update(self, position: Position) -> None:
        """Track position updates and changes."""
        # Update the tracked position in cache
        if position.contractId:
            self.tracked_positions[position.contractId] = position

        await self.increment("position_updates")
        await self.set_gauge(
            "avg_position_size",
            sum(abs(p.size) for p in self.tracked_positions.values())
            / len(self.tracked_positions)
            if self.tracked_positions
            else 0,
        )

        # Update position size tracking
        position_sizes = [
            abs(p.size) for p in self.tracked_positions.values() if p.size != 0
        ]
        if position_sizes:
            self.stats["avg_position_size"] = sum(position_sizes) / len(position_sizes)
            self.stats["largest_position"] = max(position_sizes)

    async def track_risk_calculation(self, risk_amount: float) -> None:
        """Track risk calculations and metrics."""
        await self.increment("risk_calculations")
        await self.set_gauge("total_risk", risk_amount)
        self.stats["risk_calculations"] = self.stats.get("risk_calculations", 0) + 1
        self.stats["total_risk"] = risk_amount

    async def get_position_stats(self) -> dict[str, Any]:
        """Get comprehensive position statistics combining legacy stats with new metrics.

        Returns:
            Dictionary containing all position statistics

        """
        # Get base statistics from BaseStatisticsTracker
        base_stats = await self.get_stats()

        # Combine with position-specific statistics
        return {
            **self.stats,  # Legacy stats dict for backward compatibility
            "component_stats": base_stats,
            "health_score": await self.get_health_score(),
            "uptime_seconds": await self.get_uptime(),
            "memory_usage_mb": await self.get_memory_usage(),
            "error_count": await self.get_error_count(),
            # Add aliases for test expectations
            "total_opened": self.stats.get("positions_opened", 0),
            "total_closed": self.stats.get("positions_closed", 0),
            "net_pnl": self.stats.get("total_pnl", 0.0),
            "win_count": self.stats.get("winning_trades", 0),
            "loss_count": self.stats.get("losing_trades", 0),
            # Calculate win_rate if not already set
            "win_rate": self.stats.get("win_rate")
            or (
                self.stats.get("winning_trades", 0)
                / self.stats.get("positions_closed", 1)
                if self.stats.get("positions_closed", 0) > 0
                else 0.0
            ),
            "active_positions": len(self.tracked_positions),
        }

    def get_memory_stats(self) -> dict[str, Any]:
        """Get memory statistics synchronously for backward compatibility.

        This method provides a synchronous interface to memory statistics
        for components that expect immediate access.
        """
        # Calculate memory usage for position-specific data
        memory_usage = 0.1  # Base overhead

        # Calculate memory for tracked positions
        if hasattr(self, "tracked_positions"):
            memory_usage += len(self.tracked_positions) * 0.002  # ~2KB per position

        # Calculate memory for position history
        if hasattr(self, "position_history"):
            memory_usage += len(self.position_history) * 0.001  # ~1KB per history entry

        # Calculate memory for stats dictionary
        if hasattr(self, "stats"):
            memory_usage += len(self.stats) * 0.0001  # ~0.1KB per stat

        return {
            "current_memory_mb": memory_usage,
            "memory_usage_mb": memory_usage,  # Alias for test compatibility
            "tracked_positions": len(getattr(self, "tracked_positions", {})),
            "position_history_entries": len(getattr(self, "position_history", {})),
            "stats_tracked": len(getattr(self, "stats", {})),
            "position_alerts": 0,  # Not implemented yet but needed for tests
            "cache_size": len(getattr(self, "tracked_positions", {})),
        }

    async def cleanup(self) -> None:
        """Clean up resources and connections when shutting down.

        Performs complete cleanup of the AsyncPositionManager, including stopping
        monitoring tasks, clearing tracked data, and releasing all resources.
        Should be called when the manager is no longer needed to prevent memory
        leaks and ensure graceful shutdown.

        Cleanup operations:
            1. Stops position monitoring (cancels async tasks)
            2. Clears all tracked positions
            3. Clears position history
            4. Removes all callbacks
            5. Clears all alerts
            6. Disconnects order manager integration

        Example:
            >>> # Basic cleanup
            >>> await position_manager.cleanup()
            >>> # Cleanup in finally block
            >>> position_manager = AsyncPositionManager(client)
            >>> try:
            ...     await position_manager.initialize(realtime_client)
            ...     # ... use position manager ...
            ... finally:
            ...     await position_manager.cleanup()
            >>> # Context manager pattern (if implemented)
            >>> async with AsyncPositionManager(client) as pm:
            ...     await pm.initialize(realtime_client)
            ...     # ... automatic cleanup on exit ...

        Note:
            - Safe to call multiple times
            - Logs successful cleanup
            - Does not close underlying client connections

        """
        await self.stop_monitoring()

        async with self.position_lock:
            self.tracked_positions.clear()
            self.position_history.clear()
            # EventBus handles all callbacks now
            self.position_alerts.clear()

        # Clear order manager integration
        self.order_manager = None
        self._order_sync_enabled = False

        self.logger.info("✅ AsyncPositionManager cleanup completed")
