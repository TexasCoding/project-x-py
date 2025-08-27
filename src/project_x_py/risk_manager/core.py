"""Core risk management functionality."""

import asyncio
import contextlib
import logging
import statistics
from collections import deque
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Optional

from project_x_py.exceptions import InvalidOrderParameters
from project_x_py.statistics.base import BaseStatisticsTracker
from project_x_py.types import (
    OrderSide,
    OrderType,
    PositionSizingResponse,
    RiskAnalysisResponse,
    RiskValidationResponse,
)
from project_x_py.types.protocols import (
    OrderManagerProtocol,
    PositionManagerProtocol,
    ProjectXClientProtocol,
    RealtimeDataManagerProtocol,
)

from .config import RiskConfig

if TYPE_CHECKING:
    from project_x_py.event_bus import EventBus
    from project_x_py.models import Account, Instrument, Order, Position

logger = logging.getLogger(__name__)


class RiskManager(BaseStatisticsTracker):
    """Comprehensive risk management system for trading.

    Handles position sizing, risk validation, stop-loss management,
    and portfolio risk monitoring.
    """

    def __init__(
        self,
        project_x: ProjectXClientProtocol,
        order_manager: OrderManagerProtocol,
        event_bus: "EventBus",
        position_manager: PositionManagerProtocol | None = None,
        config: RiskConfig | None = None,
        data_manager: Optional["RealtimeDataManagerProtocol"] = None,
    ):
        """Initialize risk manager.

        Args:
            project_x: ProjectX client instance
            order_manager: Order manager instance
            event_bus: Event bus for risk events
            position_manager: Optional position manager instance (can be set later)
            config: Risk configuration (uses defaults if not provided)
            data_manager: Optional data manager for market data
        """
        self.client = project_x
        self.orders = order_manager
        self.positions = position_manager
        self.position_manager = (
            position_manager  # Also store as position_manager for compatibility
        )
        self.event_bus = event_bus
        self.config = config or RiskConfig()
        self.data_manager = data_manager
        # Initialize statistics tracking with new system
        super().__init__("risk_manager", max_errors=100, cache_ttl=5.0)

        # Track daily losses and trades
        self._daily_loss = Decimal("0")
        self._daily_trades = 0
        self._last_reset_date = datetime.now().date()

        # Track trade history for Kelly criterion
        self._trade_history: deque[dict[str, Any]] = deque(maxlen=100)
        self._win_rate = 0.0
        self._avg_win = Decimal("0")
        self._avg_loss = Decimal("0")

        # Track current risk exposure
        self._current_risk = Decimal("0")
        self._max_drawdown = Decimal("0")

        # Track asyncio tasks for proper cleanup
        self._active_tasks: set[asyncio.Task[Any]] = set()
        self._trailing_stop_tasks: dict[
            str, asyncio.Task[Any]
        ] = {}  # position_id -> task

        # Thread-safe lock for daily reset operations
        self._daily_reset_lock = asyncio.Lock()

        # Initialize risk management statistics
        self._init_task = asyncio.create_task(self._initialize_risk_stats())
        self._active_tasks.add(self._init_task)

    async def _initialize_risk_stats(self) -> None:
        """Initialize risk management statistics."""
        try:
            await self.set_status("initializing")
            await self.set_gauge("max_daily_trades", self.config.max_daily_trades)
            await self.set_gauge("max_positions", self.config.max_positions)
            await self.set_gauge("max_position_size", self.config.max_position_size)
            await self.set_gauge(
                "max_risk_per_trade", float(self.config.max_risk_per_trade) * 100
            )
            await self.set_gauge(
                "max_portfolio_risk", float(self.config.max_portfolio_risk) * 100
            )
            await self.set_gauge(
                "max_daily_loss", float(self.config.max_daily_loss) * 100
            )
            await self.set_status("active")
        except Exception as e:
            logger.error(f"Error initializing risk stats: {e}")
            await self.track_error(e, "initialize_risk_stats")

    def set_position_manager(self, position_manager: PositionManagerProtocol) -> None:
        """Set the position manager after initialization to resolve circular dependency.

        This method should be called after RiskManager initialization but before
        any risk validation or position-related operations.

        Args:
            position_manager: The position manager instance to use for position operations
        """
        if self.positions is not None:
            logger.warning("Position manager already set, replacing existing instance")

        self.positions = position_manager
        self.position_manager = position_manager
        logger.debug("Position manager successfully integrated with RiskManager")

    async def calculate_position_size(
        self,
        entry_price: float,
        stop_loss: float,
        risk_amount: float | None = None,
        risk_percent: float | None = None,
        instrument: Optional["Instrument"] = None,
        use_kelly: bool | None = None,
    ) -> PositionSizingResponse:
        """Calculate optimal position size based on risk parameters.

        Args:
            entry_price: Planned entry price
            stop_loss: Stop loss price
            risk_amount: Fixed dollar amount to risk (overrides percentage)
            risk_percent: Percentage of account to risk (default from config)
            instrument: Instrument for tick size calculation
            use_kelly: Override config to use/not use Kelly criterion

        Returns:
            PositionSizingResponse with calculated size and risk metrics
        """
        import time

        start_time = time.time()
        try:
            # Get account info
            account = await self._get_account_info()
            account_balance = float(account.balance)

            # Reset daily counters if needed (thread-safe)
            await self._check_daily_reset()

            # Determine risk amount
            if risk_amount is None:
                # Use provided risk_percent, or default to config if None
                if risk_percent is None:
                    risk_percent = float(self.config.max_risk_per_trade)
                risk_amount = account_balance * risk_percent

            # Apply maximum risk limits
            if self.config.max_risk_per_trade_amount:
                risk_amount = min(
                    risk_amount, float(self.config.max_risk_per_trade_amount)
                )

            # If risk is zero, return zero position size
            if risk_amount == 0:
                return PositionSizingResponse(
                    position_size=0,
                    risk_amount=0.0,
                    risk_percent=0.0,
                    entry_price=entry_price,
                    stop_loss=stop_loss,
                    tick_size=float(instrument.tickSize) if instrument else 0.25,
                    account_balance=account_balance,
                    kelly_fraction=None,
                    max_position_size=self.config.max_position_size,
                    sizing_method="zero_risk",
                )

            # Calculate price difference and position size
            price_diff = abs(entry_price - stop_loss)
            if price_diff == 0:
                raise InvalidOrderParameters(
                    "Entry and stop loss prices cannot be equal"
                )

            # Basic position size calculation
            position_size = int(risk_amount / price_diff)

            # Apply Kelly criterion if enabled
            if (
                use_kelly or (use_kelly is None and self.config.use_kelly_criterion)
            ) and len(self._trade_history) >= self.config.min_trades_for_kelly:
                kelly_size = self._calculate_kelly_size(
                    position_size, account_balance, entry_price
                )
                position_size = min(position_size, kelly_size)

            # Apply position size limits
            position_size = min(position_size, self.config.max_position_size)

            # Calculate actual risk
            actual_risk = position_size * price_diff
            actual_risk_percent = actual_risk / account_balance

            # Get tick size for the instrument
            tick_size = 0.25  # Default
            if instrument:
                tick_size = float(instrument.tickSize)

            result = PositionSizingResponse(
                position_size=position_size,
                risk_amount=actual_risk,
                risk_percent=actual_risk_percent,
                entry_price=entry_price,
                stop_loss=stop_loss,
                tick_size=tick_size,
                account_balance=account_balance,
                kelly_fraction=self._calculate_kelly_fraction()
                if self.config.use_kelly_criterion
                else None,
                max_position_size=self.config.max_position_size,
                sizing_method="kelly" if use_kelly else "fixed_risk",
            )

            # Track successful operation
            duration_ms = (time.time() - start_time) * 1000
            await self.record_timing("calculate_position_size", duration_ms)
            await self.increment("position_size_calculations")
            await self.set_gauge("last_position_size", position_size)
            await self.set_gauge("last_risk_amount", actual_risk)
            await self.set_gauge("last_risk_percent", actual_risk_percent * 100)

            return result

        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            # Track failed operation
            duration_ms = (time.time() - start_time) * 1000
            await self.record_timing("calculate_position_size_failed", duration_ms)
            await self.increment("position_size_calculation_errors")
            await self.track_error(e, "calculate_position_size")
            raise

    async def validate_trade(
        self,
        order: "Order",
        current_positions: list["Position"] | None = None,
    ) -> RiskValidationResponse:
        """Validate a trade against risk rules.

        Args:
            order: Order to validate
            current_positions: Current positions (fetched if not provided)

        Returns:
            RiskValidationResponse with validation result and reasons

        Raises:
            ValueError: If position manager not set (circular dependency not resolved)
        """
        import time

        start_time = time.time()
        try:
            reasons = []
            warnings = []
            is_valid = True

            if self.positions is None:
                raise ValueError(
                    "Position manager not set. Call set_position_manager() to resolve circular dependency."
                )

            # Get current positions if not provided
            if current_positions is None:
                current_positions = await self.positions.get_all_positions()

            # Check daily trade limit
            if self._daily_trades >= self.config.max_daily_trades:
                is_valid = False
                reasons.append(
                    f"Daily trade limit reached ({self.config.max_daily_trades})"
                )

            # Check maximum positions
            if len(current_positions) >= self.config.max_positions:
                is_valid = False
                reasons.append(
                    f"Maximum positions limit reached ({self.config.max_positions})"
                )

            # Check position size limit
            if order.size > self.config.max_position_size:
                is_valid = False
                reasons.append(
                    f"Position size exceeds limit ({self.config.max_position_size})"
                )

            # Check daily loss limit
            account = await self._get_account_info()
            account_balance = float(account.balance)

            if self.config.max_daily_loss_amount:
                if float(self._daily_loss) >= self.config.max_daily_loss_amount:
                    is_valid = False
                    reasons.append(
                        f"Daily loss limit reached (${self.config.max_daily_loss_amount})"
                    )
            else:
                daily_loss_percent = float(self._daily_loss) / account_balance
                if daily_loss_percent >= self.config.max_daily_loss:
                    is_valid = False
                    reasons.append(
                        f"Daily loss limit reached ({self.config.max_daily_loss * 100}%)"
                    )

            # Check portfolio risk
            total_risk = await self._calculate_portfolio_risk(current_positions)
            if total_risk > self.config.max_portfolio_risk:
                warnings.append(
                    f"Portfolio risk high ({total_risk * 100:.1f}% vs "
                    f"{self.config.max_portfolio_risk * 100}% limit)"
                )

            # Check trading hours if restricted
            if (
                self.config.restrict_trading_hours
                and not self._is_within_trading_hours()
            ):
                is_valid = False
                reasons.append("Outside allowed trading hours")

            # Check for correlated positions
            correlated_count = await self._count_correlated_positions(
                order.contractId, current_positions
            )
            if correlated_count >= self.config.max_correlated_positions:
                warnings.append(
                    f"Multiple correlated positions ({correlated_count} positions)"
                )

            result = RiskValidationResponse(
                is_valid=is_valid,
                reasons=reasons,
                warnings=warnings,
                current_risk=float(self._current_risk),
                daily_loss=float(self._daily_loss),
                daily_trades=self._daily_trades,
                position_count=len(current_positions),
                portfolio_risk=total_risk,
            )

            # Track successful operation
            duration_ms = (time.time() - start_time) * 1000
            await self.record_timing("validate_trade", duration_ms)
            await self.increment("trade_validations")
            await self.increment("valid_trades" if is_valid else "invalid_trades")
            await self.set_gauge("current_portfolio_risk", total_risk)
            await self.set_gauge("daily_trades_count", self._daily_trades)
            await self.set_gauge("daily_loss_amount", float(self._daily_loss))

            return result

        except Exception as e:
            import traceback

            logger.error(f"Error validating trade: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Track failed operation
            duration_ms = (time.time() - start_time) * 1000
            await self.record_timing("validate_trade_failed", duration_ms)
            await self.increment("trade_validation_errors")
            await self.track_error(e, "validate_trade")
            return RiskValidationResponse(
                is_valid=False,
                reasons=[f"Validation error: {e!s}"],
                warnings=[],
                current_risk=0.0,
                daily_loss=0.0,
                daily_trades=0,
                position_count=0,
                portfolio_risk=0.0,
            )

    async def attach_risk_orders(
        self,
        position: "Position",
        stop_loss: float | None = None,
        take_profit: float | None = None,
        use_trailing: bool | None = None,
    ) -> dict[str, Any]:
        """Automatically attach stop-loss and take-profit orders to a position.

        Args:
            position: Position to protect
            stop_loss: Override stop loss price
            take_profit: Override take profit price
            use_trailing: Override trailing stop configuration

        Returns:
            Dictionary with attached order details
        """
        try:
            instrument = await self.client.get_instrument(position.contractId)
            tick_size = float(instrument.tickSize)

            # Determine position direction
            is_long = position.is_long
            position_size = position.size
            entry_price = float(position.averagePrice)

            # Calculate stop loss if not provided
            if stop_loss is None and self.config.use_stop_loss:
                if self.config.stop_loss_type == "atr":
                    if not self.data_manager:
                        logger.warning(
                            "ATR stop loss configured but no data manager is available. "
                            "Falling back to fixed stop."
                        )
                        stop_distance = (
                            float(self.config.default_stop_distance) * tick_size
                        )
                    else:
                        # Fetch data to calculate ATR. A common period for ATR is 14.
                        # We need enough data for the calculation. Let's fetch 50 bars.
                        # A default timeframe of '15min' is reasonable for ATR stops.
                        ohlc_data = await self.data_manager.get_data(
                            timeframe="15min", bars=50
                        )
                        if ohlc_data is None or ohlc_data.height < 14:
                            logger.warning(
                                "Not enough data to calculate ATR. Falling back to fixed stop."
                            )
                            stop_distance = (
                                float(self.config.default_stop_distance) * tick_size
                            )
                        else:
                            from project_x_py.indicators import calculate_atr

                            data_with_atr = calculate_atr(ohlc_data, period=14)
                            latest_atr = data_with_atr["atr_14"].tail(1).item()
                            if latest_atr:
                                stop_distance = latest_atr * float(
                                    self.config.default_stop_atr_multiplier
                                )
                            else:
                                logger.warning(
                                    "ATR calculation resulted in None. Falling back to fixed stop."
                                )
                                stop_distance = (
                                    float(self.config.default_stop_distance) * tick_size
                                )
                elif self.config.stop_loss_type == "percentage":
                    stop_distance = entry_price * (
                        float(self.config.default_stop_distance) / 100
                    )
                else:  # fixed
                    stop_distance = float(self.config.default_stop_distance) * tick_size

                stop_loss = (
                    entry_price - stop_distance
                    if is_long
                    else entry_price + stop_distance
                )

            # Calculate take profit if not provided
            if take_profit is None and self.config.use_take_profit and stop_loss:
                risk = abs(entry_price - stop_loss)
                reward = risk * float(self.config.default_risk_reward_ratio)
                take_profit = entry_price + reward if is_long else entry_price - reward

            # Place bracket order
            # For an existing position, we need to place exit orders
            # These are opposite side to the position
            exit_side = OrderSide.SELL if is_long else OrderSide.BUY

            # Place stop loss order
            stop_response = None
            if stop_loss:
                stop_response = await self.orders.place_stop_order(
                    contract_id=position.contractId,
                    side=exit_side,
                    size=position_size,
                    stop_price=stop_loss,
                )

            # Place take profit order
            target_response = None
            if take_profit:
                target_response = await self.orders.place_limit_order(
                    contract_id=position.contractId,
                    side=exit_side,
                    size=position_size,
                    limit_price=take_profit,
                )

            # Track risk order placement
            await self.increment("risk_orders_attached")
            if stop_loss:
                await self.increment("stop_loss_orders_placed")
            if take_profit:
                await self.increment("take_profit_orders_placed")

            # Create bracket response structure
            from project_x_py.models import BracketOrderResponse

            bracket_response = BracketOrderResponse(
                success=bool(stop_response or target_response),
                entry_order_id=None,  # No entry for existing position
                stop_order_id=stop_response.orderId
                if stop_response and stop_response.success
                else None,
                target_order_id=target_response.orderId
                if target_response and target_response.success
                else None,
                entry_price=entry_price,
                stop_loss_price=stop_loss or 0.0,
                take_profit_price=take_profit or 0.0,
                entry_response=None,
                stop_response=stop_response,
                target_response=target_response,
                error_message=None,
            )

            # Setup trailing stop if configured
            use_trailing = (
                use_trailing
                if use_trailing is not None
                else self.config.use_trailing_stops
            )
            if use_trailing and self.config.trailing_stop_distance > 0:
                # Monitor position for trailing stop activation
                trailing_task = asyncio.create_task(
                    self._monitor_trailing_stop(
                        position,
                        {
                            "stop_order_id": bracket_response.stop_order_id,
                            "target_order_id": bracket_response.target_order_id,
                        },
                    )
                )
                # Track the task for cleanup
                self._active_tasks.add(trailing_task)
                self._trailing_stop_tasks[str(position.id)] = trailing_task

                # Add task completion callback to remove from tracking
                trailing_task.add_done_callback(
                    lambda t: self._cleanup_task(t, str(position.id))
                )

            # Emit risk order placed event
            await self.event_bus.emit(
                "risk_orders_placed",
                {
                    "position": position,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "bracket_order": bracket_response,
                    "use_trailing": use_trailing,
                },
            )

            return {
                "position_id": position.id,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "bracket_order": bracket_response,
                "use_trailing": use_trailing,
                "risk_reward_ratio": float(self.config.default_risk_reward_ratio),
            }

        except Exception as e:
            logger.error(f"Error attaching risk orders: {e}")
            raise

    async def adjust_stops(
        self,
        position: "Position",
        new_stop: float,
        order_id: str | None = None,
    ) -> bool:
        """Adjust stop-loss order for a position.

        Args:
            position: Position to adjust
            new_stop: New stop loss price
            order_id: Specific order ID to modify (finds it if not provided)

        Returns:
            True if adjustment successful
        """
        try:
            # Find stop order if not provided
            if order_id is None:
                orders = await self.orders.search_open_orders()
                stop_orders = [
                    o
                    for o in orders
                    if o.contractId == position.contractId
                    and o.type in [4, 3]  # STOP=4, STOP_LIMIT=3
                    and o.side
                    != (OrderSide.BUY if position.is_long else OrderSide.SELL)
                ]

                if not stop_orders:
                    logger.warning(f"No stop order found for position {position.id}")
                    return False

                order_id = str(stop_orders[0].id)

            # Modify the order
            success = await self.orders.modify_order(
                order_id=int(order_id),
                stop_price=new_stop,
            )

            if success:
                await self.increment("stop_adjustments")
                await self.event_bus.emit(
                    "stop_adjusted",
                    {
                        "position": position,
                        "new_stop": new_stop,
                        "order_id": order_id,
                    },
                )
            else:
                await self.increment("stop_adjustment_failures")

            return success

        except Exception as e:
            logger.error(f"Error adjusting stop: {e}")
            return False

    async def get_risk_metrics(self) -> RiskAnalysisResponse:
        """Get current risk metrics and analysis.

        Returns:
            Comprehensive risk analysis

        Raises:
            ValueError: If position manager not set (circular dependency not resolved)
        """
        try:
            if self.positions is None:
                raise ValueError(
                    "Position manager not set. Call set_position_manager() to resolve circular dependency."
                )

            account = await self._get_account_info()
            positions = await self.positions.get_all_positions()

            # Calculate metrics
            _total_risk = await self._calculate_portfolio_risk(positions)
            position_risks = []

            for pos in positions:
                risk = await self._calculate_position_risk(pos)
                position_risks.append(
                    {
                        "position_id": pos.id,
                        "symbol": self._extract_symbol(pos.contractId),
                        "risk_amount": float(risk["amount"]),
                        "risk_percent": float(risk["percent"]),
                    }
                )

            return RiskAnalysisResponse(
                current_risk=float(self._current_risk),
                max_risk=float(self.config.max_portfolio_risk),
                daily_loss=float(self._daily_loss),
                daily_loss_limit=float(self.config.max_daily_loss),
                position_count=len(positions),
                position_limit=self.config.max_positions,
                daily_trades=self._daily_trades,
                daily_trade_limit=self.config.max_daily_trades,
                win_rate=self._win_rate,
                profit_factor=self._calculate_profit_factor(),
                sharpe_ratio=self._calculate_sharpe_ratio(),
                max_drawdown=float(self._max_drawdown),
                position_risks=position_risks,
                risk_per_trade=float(self.config.max_risk_per_trade),
                account_balance=float(account.balance),
                margin_used=0.0,  # Not available in Account model
                margin_available=float(account.balance),  # Simplified
            )

        except Exception as e:
            logger.error(f"Error getting risk metrics: {e}")
            raise

    # Helper methods

    async def _get_account_info(self) -> "Account":
        """Get current account information."""
        accounts = await self.client.list_accounts()
        if accounts:
            return accounts[0]
        raise ValueError(
            "No account found. RiskManager cannot proceed without account information."
        )

    async def _check_daily_reset(self) -> None:
        """Reset daily counters if new day (thread-safe)."""
        current_date = datetime.now().date()
        if current_date > self._last_reset_date:
            async with self._daily_reset_lock:
                # Double-check after acquiring lock to prevent race condition
                if current_date > self._last_reset_date:
                    logger.info(
                        f"Daily reset: {self._last_reset_date} -> {current_date}, "
                        f"Daily loss: ${self._daily_loss}, Daily trades: {self._daily_trades}"
                    )
                    self._daily_loss = Decimal("0")
                    self._daily_trades = 0
                    self._last_reset_date = current_date

                    # Update daily reset metrics
                    await self.increment("daily_resets")
                    await self.set_gauge("days_since_start", 0)  # Reset day counter

    def _calculate_kelly_fraction(self) -> float:
        """Calculate Kelly criterion fraction."""
        if self._win_rate == 0 or self._avg_loss == 0:
            return 0.0

        # Kelly formula: f = (p * b - q) / b
        # where p = win rate, q = loss rate, b = avg win / avg loss
        p = self._win_rate
        q = 1 - p
        b = float(self._avg_win / self._avg_loss) if self._avg_loss > 0 else 0

        if b == 0:
            return 0.0

        kelly = (p * b - q) / b

        # Apply Kelly fraction from config (partial Kelly)
        return max(0.0, min(kelly * float(self.config.kelly_fraction), 0.25))

    def _calculate_kelly_size(
        self,
        base_size: int,
        account_balance: float,
        entry_price: float,
    ) -> int:
        """Calculate position size using Kelly criterion."""
        kelly_fraction = self._calculate_kelly_fraction()
        if kelly_fraction <= 0:
            return base_size

        # Calculate Kelly-adjusted position value
        kelly_value = account_balance * kelly_fraction
        kelly_size = int(kelly_value / entry_price)

        return min(base_size, kelly_size)

    async def _calculate_portfolio_risk(self, positions: list["Position"]) -> float:
        """Calculate total portfolio risk."""
        if not positions:
            return 0.0

        account = await self._get_account_info()
        account_balance = float(account.balance)

        total_risk = Decimal("0")
        for pos in positions:
            risk = await self._calculate_position_risk(pos)
            total_risk += risk["amount"]

        return float(total_risk / Decimal(str(account_balance)))

    async def _calculate_position_risk(
        self, position: "Position"
    ) -> dict[str, Decimal]:
        """Calculate risk for a single position."""
        # Find stop loss order
        orders: list[Order] = await self.orders.search_open_orders()
        stop_orders = [
            o
            for o in orders
            if o.contractId == position.contractId
            and o.type in [OrderType.STOP, OrderType.STOP_LIMIT]
        ]

        if stop_orders:
            stop_price_value = stop_orders[0].stopPrice or stop_orders[0].limitPrice
            if stop_price_value is not None:
                stop_price = float(stop_price_value)
                risk = abs(float(position.averagePrice) - stop_price) * position.size
            else:
                # Use default stop distance if no valid stop price
                risk = float(self.config.default_stop_distance) * position.size
        else:
            # Use default stop distance if no stop order
            risk = float(self.config.default_stop_distance) * position.size

        account = await self._get_account_info()
        risk_percent = risk / float(account.balance)

        return {
            "amount": Decimal(str(risk)),
            "percent": Decimal(str(risk_percent)),
        }

    def _is_within_trading_hours(self) -> bool:
        """Check if current time is within allowed trading hours."""
        if not self.config.restrict_trading_hours:
            return True

        now = datetime.now().time()
        for start_str, end_str in self.config.allowed_trading_hours:
            start = datetime.strptime(start_str, "%H:%M").time()
            end = datetime.strptime(end_str, "%H:%M").time()

            if start <= now <= end:
                return True

        return False

    async def _count_correlated_positions(
        self,
        contract_id: str,
        positions: list["Position"],
    ) -> int:
        """Count positions in correlated instruments."""
        # For now, simple implementation - count positions in same base symbol
        base_symbol = self._extract_symbol(contract_id)

        count = 0
        for pos in positions:
            if self._extract_symbol(pos.contractId) == base_symbol:
                count += 1

        return count

    def _extract_symbol(self, contract_id: str) -> str:
        """Extract base symbol from contract ID."""
        # Example: "CON.F.US.MNQ.U24" -> "MNQ"
        parts = contract_id.split(".")
        return parts[3] if len(parts) > 3 else contract_id

    async def _get_market_price(self, contract_id: str) -> float:
        """Get current market price for a contract."""
        if not self.data_manager:
            raise RuntimeError("Data manager not available for market price fetching.")

        # This assumes the data_manager is configured for the correct instrument.
        timeframes_to_try = ["1sec", "15sec", "1min", "5min"]

        for timeframe in timeframes_to_try:
            try:
                data = await self.data_manager.get_data(timeframe, bars=1)
                if data is not None and not data.is_empty():
                    return float(data["close"].tail(1).item())
            except Exception:
                continue

        try:
            current_price = await self.data_manager.get_current_price()
            if current_price is not None:
                return float(current_price)
        except Exception:
            pass

        raise RuntimeError(f"Unable to fetch current market price for {contract_id}")

    async def _monitor_trailing_stop(
        self,
        position: "Position",
        _bracket_order: dict[str, Any],
    ) -> None:
        """Monitor position for trailing stop activation."""
        try:
            await self.increment("trailing_stops_monitored")
            is_long = position.is_long
            entry_price = float(position.averagePrice)

            while True:
                # Get current price
                if self.positions is None:
                    raise ValueError(
                        "Position manager not set. Call set_position_manager() to resolve circular dependency."
                    )

                current_positions = await self.positions.get_all_positions()
                current_pos = next(
                    (p for p in current_positions if p.id == position.id), None
                )

                if not current_pos:
                    # Position closed
                    break

                # Get current market price
                try:
                    current_price = await self._get_market_price(position.contractId)
                except RuntimeError as e:
                    logger.warning(
                        f"Could not fetch price for trailing stop on {position.contractId}: {e}"
                    )
                    await asyncio.sleep(10)  # Wait longer if price is unavailable
                    continue

                profit = (
                    (current_price - entry_price)
                    if is_long
                    else (entry_price - current_price)
                )

                if profit >= float(self.config.trailing_stop_trigger):
                    # Adjust stop to trail
                    new_stop = (
                        current_price - float(self.config.trailing_stop_distance)
                        if is_long
                        else current_price + float(self.config.trailing_stop_distance)
                    )

                    await self.increment("trailing_stop_adjustments")
                    await self.adjust_stops(current_pos, new_stop)

                await asyncio.sleep(5)  # Check every 5 seconds

        except asyncio.CancelledError:
            logger.info(
                f"Trailing stop monitoring cancelled for position {position.id}"
            )
        except Exception as e:
            logger.error(f"Error monitoring trailing stop: {e}")
        finally:
            # Clean up the task reference
            if str(position.id) in self._trailing_stop_tasks:
                del self._trailing_stop_tasks[str(position.id)]

    def _calculate_profit_factor(self) -> float:
        """Calculate profit factor from trade history."""
        if not self._trade_history:
            return 0.0

        gross_profit = sum(t["pnl"] for t in self._trade_history if t["pnl"] > 0)
        gross_loss = abs(sum(t["pnl"] for t in self._trade_history if t["pnl"] < 0))

        return gross_profit / gross_loss if gross_loss > 0 else 0.0

    def _calculate_sharpe_ratio(self) -> float:
        """Calculate Sharpe ratio from trade history."""
        if len(self._trade_history) < 2:
            return 0.0

        returns = [t["pnl"] for t in self._trade_history]
        if not returns:
            return 0.0

        avg_return = statistics.mean(returns)
        std_return = statistics.stdev(returns)

        if std_return == 0:
            return 0.0

        # Annualized Sharpe (assuming daily returns and 252 trading days)
        sharpe_ratio: float = (avg_return / std_return) * (252**0.5)
        return sharpe_ratio

    async def _get_gauge_value(self, metric: str, default: float = 0.0) -> float:
        """Helper to get current gauge value safely."""
        async with self._lock:
            value = self._gauges.get(metric, default)
            return float(value) if value is not None else default

    def get_memory_stats(self) -> dict[str, float]:
        """Get memory statistics synchronously for backward compatibility."""
        try:
            # Calculate basic memory estimates without async
            base_size = 0.1  # Base overhead in MB

            # Estimate data structure sizes
            trade_history_size = len(self._trade_history) * 0.001  # ~1KB per trade
            config_size = 0.05  # Config overhead

            # Risk-specific memory estimates
            risk_data_size = 0.02  # Risk calculation cache

            total_memory = base_size + trade_history_size + config_size + risk_data_size

            return {
                "total_mb": round(total_memory, 2),
                "trade_history_mb": round(trade_history_size, 3),
                "base_overhead_mb": round(base_size, 2),
                "risk_data_mb": round(risk_data_size, 3),
                "config_mb": round(config_size, 3),
            }
        except Exception as e:
            logger.error(f"Error calculating memory stats: {e}")
            return {
                "total_mb": 0.0,
                "error_code": 1.0,  # Use numeric error code instead of string
            }

    async def record_trade_result(
        self,
        position_id: str,
        pnl: float,
        duration_seconds: int,
    ) -> None:
        """Record trade result for risk analysis.

        Args:
            position_id: Position identifier
            pnl: Profit/loss amount
            duration_seconds: Trade duration
        """
        self._trade_history.append(
            {
                "position_id": position_id,
                "pnl": pnl,
                "duration": duration_seconds,
                "timestamp": datetime.now(),
            }
        )

        # Update statistics
        self._update_trade_statistics()

        # Update daily loss
        if pnl < 0:
            self._daily_loss += Decimal(str(abs(pnl)))
            await self.increment("losing_trades")
            current_largest_loss = await self._get_gauge_value("largest_loss", 0.0)
            await self.set_gauge("largest_loss", max(abs(pnl), current_largest_loss))
        else:
            await self.increment("winning_trades")
            current_largest_win = await self._get_gauge_value("largest_win", 0.0)
            await self.set_gauge("largest_win", max(pnl, current_largest_win))

        # Increment daily trades
        self._daily_trades += 1
        await self.increment("total_trades")
        await self.set_gauge("win_rate_percent", self._win_rate * 100)
        await self.set_gauge("avg_win_amount", float(self._avg_win))
        await self.set_gauge("avg_loss_amount", float(self._avg_loss))

        # Emit event
        await self.event_bus.emit(
            "trade_recorded",
            {
                "position_id": position_id,
                "pnl": pnl,
                "duration": duration_seconds,
                "daily_loss": float(self._daily_loss),
                "daily_trades": self._daily_trades,
            },
        )

    def _cleanup_task(
        self, task: asyncio.Task[Any], position_id: str | None = None
    ) -> None:
        """Clean up completed or cancelled tasks."""
        try:
            # Remove from active tasks
            self._active_tasks.discard(task)

            # Remove from trailing stop tasks if position_id provided
            if position_id and position_id in self._trailing_stop_tasks:
                del self._trailing_stop_tasks[position_id]

            # Log task completion
            if task.cancelled():
                logger.debug(f"Task cancelled: {task.get_name()}")
            elif task.exception():
                logger.warning(f"Task completed with exception: {task.exception()}")
            else:
                logger.debug(f"Task completed successfully: {task.get_name()}")
        except Exception as e:
            logger.error(f"Error cleaning up task: {e}")

    async def stop_trailing_stops(self, position_id: str | None = None) -> None:
        """Stop trailing stop monitoring for specific position or all positions.

        Args:
            position_id: Position to stop monitoring (None for all positions)
        """
        try:
            if position_id:
                # Stop specific trailing stop task
                if position_id in self._trailing_stop_tasks:
                    task = self._trailing_stop_tasks[position_id]
                    if not task.done():
                        task.cancel()
                        with contextlib.suppress(asyncio.CancelledError):
                            await task
                    del self._trailing_stop_tasks[position_id]
                    self._active_tasks.discard(task)
                    logger.info(
                        f"Stopped trailing stop monitoring for position {position_id}"
                    )
            else:
                # Stop all trailing stop tasks
                tasks_to_cancel = list(self._trailing_stop_tasks.values())
                for task in tasks_to_cancel:
                    if not task.done():
                        task.cancel()

                # Wait for all cancellations to complete
                if tasks_to_cancel:
                    await asyncio.gather(*tasks_to_cancel, return_exceptions=True)

                # Clear tracking
                self._trailing_stop_tasks.clear()
                logger.info("Stopped all trailing stop monitoring")

        except Exception as e:
            logger.error(f"Error stopping trailing stops: {e}")

    async def check_daily_reset(self) -> None:
        """Check and perform daily reset if needed."""
        async with self._daily_reset_lock:
            today = datetime.now().date()
            if today > self._last_reset_date:
                self._daily_loss = Decimal("0")
                self._daily_trades = 0
                self._last_reset_date = today
                await self.increment("daily_reset")

    async def calculate_stop_loss(
        self, entry_price: float, side: OrderSide, atr_value: float | None = None
    ) -> float:
        """Calculate stop loss price."""
        if self.config.stop_loss_type == "fixed":
            distance = float(self.config.default_stop_distance)
            return (
                entry_price - distance
                if side == OrderSide.BUY
                else entry_price + distance
            )

        elif self.config.stop_loss_type == "percentage":
            pct = float(self.config.default_stop_distance)
            return (
                entry_price * (1 - pct)
                if side == OrderSide.BUY
                else entry_price * (1 + pct)
            )

        elif self.config.stop_loss_type == "atr" and atr_value:
            distance = atr_value * float(self.config.default_stop_atr_multiplier)
            return (
                entry_price - distance
                if side == OrderSide.BUY
                else entry_price + distance
            )

        # Default fallback
        return entry_price - 50 if side == OrderSide.BUY else entry_price + 50

    async def calculate_take_profit(
        self,
        entry_price: float,
        stop_loss: float,
        side: OrderSide,
        risk_reward_ratio: float | None = None,
    ) -> float:
        """Calculate take profit price."""
        if risk_reward_ratio is None:
            risk_reward_ratio = float(self.config.default_risk_reward_ratio)

        risk = abs(entry_price - stop_loss)
        reward = risk * risk_reward_ratio

        return entry_price + reward if side == OrderSide.BUY else entry_price - reward

    async def should_activate_trailing_stop(
        self, entry_price: float, current_price: float, side: OrderSide
    ) -> bool:
        """Check if trailing stop should be activated."""
        if not self.config.use_trailing_stops:
            return False

        profit = (
            current_price - entry_price
            if side == OrderSide.BUY
            else entry_price - current_price
        )
        trigger = float(self.config.trailing_stop_trigger)

        return profit >= trigger

    def calculate_trailing_stop(self, current_price: float, side: OrderSide) -> float:
        """Calculate trailing stop price."""
        distance = float(self.config.trailing_stop_distance)
        return (
            current_price - distance
            if side == OrderSide.BUY
            else current_price + distance
        )

    async def analyze_portfolio_risk(self) -> dict[str, Any]:
        """Analyze portfolio risk."""
        try:
            positions = []
            if self.positions:
                positions = await self.positions.get_all_positions()

            total_risk = 0.0
            position_risks = []

            for pos in positions:
                risk = await self._calculate_position_risk(pos)
                total_risk += float(risk["amount"])  # Convert Decimal to float
                position_risks.append(
                    {
                        "instrument": pos.contractId,
                        "risk": risk,
                        "size": getattr(pos, "netQuantity", getattr(pos, "size", 0)),
                    }
                )

            return {
                "total_risk": total_risk,
                "position_risks": position_risks,
                "risk_metrics": await self.get_risk_metrics(),
                "recommendations": [],
            }
        except Exception as e:
            logger.error(f"Error analyzing portfolio risk: {e}")
            return {
                "total_risk": 0,
                "position_risks": [],
                "risk_metrics": {},
                "recommendations": [],
                "error": str(e),
            }

    async def analyze_trade_risk(
        self,
        instrument: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        position_size: int,
    ) -> dict[str, Any]:
        """Analyze individual trade risk."""
        risk_amount = abs(entry_price - stop_loss) * position_size
        reward_amount = abs(take_profit - entry_price) * position_size

        account = await self._get_account_info()
        risk_percent = (risk_amount / account.balance) if account.balance > 0 else 0

        return {
            "risk_amount": risk_amount,
            "reward_amount": reward_amount,
            "risk_reward_ratio": reward_amount / risk_amount if risk_amount > 0 else 0,
            "risk_percent": risk_percent,
        }

    async def add_trade_result(
        self,
        instrument: str,
        pnl: float,
        entry_price: float | None = None,
        exit_price: float | None = None,
        size: int | None = None,
        side: OrderSide | None = None,
    ) -> None:
        """Add trade result to history."""
        trade = {
            "instrument": instrument,
            "pnl": pnl,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "size": size,
            "side": side,
            "timestamp": datetime.now(),
        }

        self._trade_history.append(trade)

        # Update daily loss
        if pnl < 0:
            self._daily_loss += Decimal(str(abs(pnl)))

        # Update statistics
        await self.update_trade_statistics()

    async def update_trade_statistics(self) -> None:
        """Update trade statistics from history."""
        if len(self._trade_history) < 2:
            return

        wins = [t for t in self._trade_history if t["pnl"] > 0]
        losses = [t for t in self._trade_history if t["pnl"] < 0]

        total_trades = len(self._trade_history)
        self._win_rate = len(wins) / total_trades if total_trades > 0 else 0

        if wins:
            self._avg_win = Decimal(str(sum(t["pnl"] for t in wins) / len(wins)))

        if losses:
            self._avg_loss = Decimal(
                str(abs(sum(t["pnl"] for t in losses) / len(losses)))
            )

    async def calculate_kelly_position_size(
        self, base_size: int, win_rate: float, avg_win: float, avg_loss: float
    ) -> int:
        """Calculate Kelly position size."""
        if avg_loss == 0 or win_rate == 0:
            return base_size

        # Kelly formula: f = (p * b - q) / b
        # where p = win rate, q = loss rate, b = win/loss ratio
        b = avg_win / avg_loss
        p = win_rate
        q = 1 - win_rate

        kelly = (p * b - q) / b

        # Apply Kelly fraction
        kelly *= float(self.config.kelly_fraction)

        # Ensure reasonable bounds
        kelly = max(0, min(kelly, 0.25))  # Cap at 25%

        # Round to nearest integer instead of truncating
        return round(base_size * (1 + kelly))

    async def cleanup(self) -> None:
        """Clean up all resources and cancel active tasks."""
        try:
            logger.info("Starting RiskManager cleanup...")

            # Cancel all active tasks
            active_tasks: list[asyncio.Task[Any]] = list(self._active_tasks)
            for task in active_tasks:
                if not task.done():
                    task.cancel()

            # Cancel all trailing stop tasks
            trailing_tasks: list[asyncio.Task[Any]] = list(
                self._trailing_stop_tasks.values()
            )
            for task in trailing_tasks:
                if not task.done():
                    task.cancel()

            # Wait for all tasks to complete cancellation
            all_tasks = active_tasks + trailing_tasks
            if all_tasks:
                await asyncio.gather(*all_tasks, return_exceptions=True)

            # Clear tracking
            self._active_tasks.clear()
            self._trailing_stop_tasks.clear()

            logger.info("RiskManager cleanup completed")

        except Exception as e:
            logger.error(f"Error during RiskManager cleanup: {e}")

    def _update_trade_statistics(self) -> None:
        """Update win rate and average win/loss statistics."""
        if not self._trade_history:
            return

        wins = [t for t in self._trade_history if t["pnl"] > 0]
        losses = [t for t in self._trade_history if t["pnl"] < 0]

        self._win_rate = (
            len(wins) / len(self._trade_history) if self._trade_history else 0
        )
        self._avg_win = (
            Decimal(str(statistics.mean([t["pnl"] for t in wins])))
            if wins
            else Decimal("0")
        )
        self._avg_loss = (
            Decimal(str(abs(statistics.mean([t["pnl"] for t in losses]))))
            if losses
            else Decimal("0")
        )
