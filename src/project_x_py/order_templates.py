"""
Common order templates for simplified trading strategies.

Author: SDK v3.0.0
Date: 2025-08-04

Overview:
    Provides pre-configured order templates for common trading scenarios,
    making it easy to implement standard trading patterns without complex
    order configuration logic.

Key Features:
    - Pre-configured risk/reward ratios
    - ATR-based dynamic stop losses
    - Breakout order templates
    - Scalping configurations
    - Position sizing helpers
    - Risk management integration

Example Usage:
    ```python
    # Use a template for 2:1 risk/reward
    template = RiskRewardTemplate(risk_reward_ratio=2.0)
    order = await template.create_order(
        suite,
        side=OrderSide.BUY,
        risk_amount=100,  # Risk $100
    )

    # ATR-based stops
    atr_template = ATRStopTemplate(atr_multiplier=2.0)
    order = await atr_template.create_order(suite, side=OrderSide.BUY, size=1)
    ```
"""

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from project_x_py.indicators import ATR
from project_x_py.models import BracketOrderResponse

# OrderChainBuilder was deprecated and removed - using OrderManager directly

if TYPE_CHECKING:
    from project_x_py.trading_suite import TradingSuite

logger = logging.getLogger(__name__)


class OrderTemplate(ABC):
    """Base class for order templates."""

    @abstractmethod
    async def create_order(
        self,
        suite: "TradingSuite",
        side: int,
        size: int | None = None,
        **kwargs: Any,
    ) -> BracketOrderResponse:
        """Create an order using this template."""


class RiskRewardTemplate(OrderTemplate):
    """
    Template for orders with fixed risk/reward ratios.

    Creates bracket orders with stop loss and take profit levels
    based on a specified risk/reward ratio.
    """

    def __init__(
        self,
        risk_reward_ratio: float = 2.0,
        stop_distance: float | None = None,
        use_limit_entry: bool = True,
    ):
        """
        Initialize risk/reward template.

        Args:
            risk_reward_ratio: Ratio of potential profit to risk (e.g., 2.0 = 2:1)
            stop_distance: Fixed stop distance in points (optional)
            use_limit_entry: Use limit orders for entry (vs market)
        """
        self.risk_reward_ratio = risk_reward_ratio
        self.stop_distance = stop_distance
        self.use_limit_entry = use_limit_entry

    async def create_order(
        self,
        suite: "TradingSuite",
        side: int,
        size: int | None = None,
        risk_amount: float | None = None,
        risk_percent: float | None = None,
        entry_offset: float = 0,
        **kwargs: Any,
    ) -> BracketOrderResponse:
        """
        Create an order with fixed risk/reward ratio.

        Args:
            suite: TradingSuite instance
            side: Order side (0=BUY, 1=SELL)
            size: Order size (calculated from risk if not provided)
            risk_amount: Dollar amount to risk
            risk_percent: Percentage of account to risk
            entry_offset: Offset from current price for limit entry

        Returns:
            BracketOrderResponse with order details
        """
        # Get current price
        current_price = await suite.data.get_current_price()
        if not current_price:
            raise ValueError("Cannot get current price")

        # Calculate entry price
        if self.use_limit_entry:
            if side == 0:  # BUY
                entry_price = current_price - entry_offset
            else:  # SELL
                entry_price = current_price + entry_offset
        else:
            entry_price = current_price

        # Determine stop distance
        if self.stop_distance:
            stop_dist = self.stop_distance
        else:
            # Use 1% of price as default
            stop_dist = current_price * 0.01 if current_price else 0.0

        # Calculate position size if needed
        if size is None:
            if risk_amount:
                # Size = Risk Amount / Stop Distance
                # suite.instrument is already an Instrument object after initialization
                instrument = suite.instrument
                tick_value = instrument.tickValue if instrument else 1.0
                size = int(risk_amount / (stop_dist * tick_value))
            elif risk_percent:
                # Get account balance
                account = suite.client.account_info
                if not account:
                    raise ValueError("No account information available")
                risk_amount = float(account.balance) * risk_percent
                # suite.instrument is already an Instrument object after initialization
                instrument = suite.instrument
                tick_value = instrument.tickValue if instrument else 1.0
                size = int(risk_amount / (stop_dist * tick_value))
            else:
                raise ValueError("Must provide size, risk_amount, or risk_percent")

        # Calculate stop and target prices
        # Defensive check - size should be set by now, but verify for safety
        if size is None:  # pragma: no cover
            raise ValueError("Size is required")

        if not suite.instrument_id:
            raise ValueError("No instrument ID available")

        target_dist = stop_dist * self.risk_reward_ratio

        if side == 0:  # Buy
            stop_loss_price = entry_price - stop_dist
            take_profit_price = entry_price + target_dist
        else:  # Sell
            stop_loss_price = entry_price + stop_dist
            take_profit_price = entry_price - target_dist

        # Use OrderManager's bracket order functionality
        if self.use_limit_entry:
            result = await suite.orders.place_bracket_order(
                contract_id=suite.instrument_id,
                side=side,
                size=size,
                entry_price=entry_price,
                stop_loss_price=stop_loss_price,
                take_profit_price=take_profit_price,
                entry_type="limit",
            )
        else:
            result = await suite.orders.place_bracket_order(
                contract_id=suite.instrument_id,
                side=side,
                size=size,
                entry_price=entry_price,
                stop_loss_price=stop_loss_price,
                take_profit_price=take_profit_price,
                entry_type="market",
            )

        logger.info(
            f"Created {self.risk_reward_ratio}:1 R/R bracket order - "
            f"Entry: ${entry_price:.2f}, Stop: ${stop_loss_price:.2f}, "
            f"Target: ${take_profit_price:.2f}"
        )

        return result


class ATRStopTemplate(OrderTemplate):
    """
    Template for orders with ATR-based stop losses.

    Uses Average True Range to dynamically set stop distances
    based on current market volatility.
    """

    def __init__(
        self,
        atr_multiplier: float = 2.0,
        atr_period: int = 14,
        target_multiplier: float = 3.0,
        timeframe: str = "5min",
    ):
        """
        Initialize ATR-based template.

        Args:
            atr_multiplier: Multiplier for ATR to set stop distance
            atr_period: Period for ATR calculation
            target_multiplier: Multiplier for target (relative to stop)
            timeframe: Timeframe for ATR calculation
        """
        self.atr_multiplier = atr_multiplier
        self.atr_period = atr_period
        self.target_multiplier = target_multiplier
        self.timeframe = timeframe

    async def create_order(
        self,
        suite: "TradingSuite",
        side: int,
        size: int | None = None,
        use_limit_entry: bool = False,
        entry_offset: float = 0,
        **kwargs: Any,
    ) -> BracketOrderResponse:
        """
        Create an order with ATR-based stops.

        Args:
            suite: TradingSuite instance
            side: Order side (0=BUY, 1=SELL)
            size: Order size
            use_limit_entry: Use limit order for entry
            entry_offset: Offset from current price for limit entry

        Returns:
            BracketOrderResponse with order details
        """
        # Get data for ATR calculation
        data = await suite.data.get_data(self.timeframe, bars=self.atr_period + 1)
        if data is None or len(data) < self.atr_period:
            raise ValueError("Insufficient data for ATR calculation")

        # Calculate ATR
        data_with_atr = data.pipe(ATR, period=self.atr_period)
        current_atr = float(data_with_atr[f"atr_{self.atr_period}"][-1])

        # Get current price
        current_price = await suite.data.get_current_price()
        if not current_price:
            raise ValueError("Cannot get current price")

        # Calculate stop distance
        stop_distance = current_atr * self.atr_multiplier
        target_distance = stop_distance * self.target_multiplier

        logger.info(
            f"ATR-based order: ATR={current_atr:.2f}, "
            f"Stop distance={stop_distance:.2f}, "
            f"Target distance={target_distance:.2f}"
        )

        # Calculate entry and stop prices
        if size is None:
            raise ValueError("Size is required")

        if not suite.instrument_id:
            raise ValueError("No instrument ID available")

        if use_limit_entry:
            if side == 0:  # BUY
                entry_price = current_price - entry_offset
                stop_loss_price = entry_price - stop_distance
                take_profit_price = entry_price + target_distance
            else:  # SELL
                entry_price = current_price + entry_offset
                stop_loss_price = entry_price + stop_distance
                take_profit_price = entry_price - target_distance

            # Place bracket order with limit entry
            return await suite.orders.place_bracket_order(
                contract_id=suite.instrument_id,
                side=side,
                size=size,
                entry_price=entry_price,
                stop_loss_price=stop_loss_price,
                take_profit_price=take_profit_price,
                entry_type="limit",
            )
        else:
            # Market entry - use current price as reference
            if side == 0:  # BUY
                stop_loss_price = current_price - stop_distance
                take_profit_price = current_price + target_distance
            else:  # SELL
                stop_loss_price = current_price + stop_distance
                take_profit_price = current_price - target_distance

            # Place bracket order with market entry
            return await suite.orders.place_bracket_order(
                contract_id=suite.instrument_id,
                side=side,
                size=size,
                entry_price=current_price,
                stop_loss_price=stop_loss_price,
                take_profit_price=take_profit_price,
                entry_type="market",
            )


class BreakoutTemplate(OrderTemplate):
    """
    Template for breakout orders.

    Places stop orders above/below key levels with automatic
    stop loss and take profit based on the breakout range.
    """

    def __init__(
        self,
        breakout_offset: float = 2.0,
        stop_at_level: bool = True,
        target_range_multiplier: float = 1.5,
    ):
        """
        Initialize breakout template.

        Args:
            breakout_offset: Points above/below level to place stop order
            stop_at_level: Place stop loss at the breakout level
            target_range_multiplier: Target distance as multiple of range
        """
        self.breakout_offset = breakout_offset
        self.stop_at_level = stop_at_level
        self.target_range_multiplier = target_range_multiplier

    async def create_order(
        self,
        suite: "TradingSuite",
        side: int,
        size: int | None = None,
        breakout_level: float | None = None,
        range_size: float | None = None,
        lookback_bars: int = 20,
        **kwargs: Any,
    ) -> BracketOrderResponse:
        """
        Create a breakout order.

        Args:
            suite: TradingSuite instance
            side: Order side (0=BUY for upside breakout, 1=SELL for downside)
            size: Order size
            breakout_level: Specific level to break (auto-detected if None)
            range_size: Size of the range (auto-calculated if None)
            lookback_bars: Bars to look back for range calculation

        Returns:
            BracketOrderResponse with order details
        """
        # Auto-detect breakout level if not provided
        if breakout_level is None:
            range_stats = await suite.data.get_price_range(
                bars=lookback_bars, timeframe="5min"
            )
            if not range_stats:
                raise ValueError("Cannot calculate price range")

            breakout_level = (
                range_stats["high"] if side == 0 else range_stats["low"]
            )  # BUY=high, SELL=low

            if range_size is None:
                range_size = range_stats["range"]

        # Calculate entry price
        if side == 0:  # BUY
            entry_price = breakout_level + self.breakout_offset
            if range_size is None:
                raise ValueError("Range size is required")
            stop_price = (
                breakout_level if self.stop_at_level else breakout_level - range_size
            )
            target_price = entry_price + (range_size * self.target_range_multiplier)
        else:  # SELL
            entry_price = breakout_level - self.breakout_offset
            if range_size is None:
                raise ValueError("Range size is required")
            stop_price = (
                breakout_level if self.stop_at_level else breakout_level + range_size
            )
            target_price = entry_price - (range_size * self.target_range_multiplier)

        logger.info(
            f"Breakout order: Level={breakout_level:.2f}, "
            f"Entry={entry_price:.2f}, Stop={stop_price:.2f}, "
            f"Target={target_price:.2f}"
        )

        # Build breakout order using bracket order
        if size is None:
            raise ValueError("Size is required")

        if not suite.instrument_id:
            raise ValueError("No instrument ID available")

        # Use stop order as entry type for breakouts
        return await suite.orders.place_bracket_order(
            contract_id=suite.instrument_id,
            side=side,
            size=size,
            entry_price=entry_price,
            stop_loss_price=stop_price,
            take_profit_price=target_price,
            entry_type="stop",  # Stop order for breakout entry
        )


class ScalpingTemplate(OrderTemplate):
    """
    Template for quick scalping trades.

    Optimized for fast entry/exit with tight stops and
    quick profit targets.
    """

    def __init__(
        self,
        stop_ticks: int = 4,
        target_ticks: int = 8,
        use_market_entry: bool = True,
        max_spread_ticks: int = 2,
    ):
        """
        Initialize scalping template.

        Args:
            stop_ticks: Stop loss distance in ticks
            target_ticks: Take profit distance in ticks
            use_market_entry: Use market orders for quick entry
            max_spread_ticks: Maximum spread to allow entry
        """
        self.stop_ticks = stop_ticks
        self.target_ticks = target_ticks
        self.use_market_entry = use_market_entry
        self.max_spread_ticks = max_spread_ticks

    async def create_order(
        self,
        suite: "TradingSuite",
        side: int,
        size: int | None = None,
        check_spread: bool = True,
        **kwargs: Any,
    ) -> BracketOrderResponse:
        """
        Create a scalping order.

        Args:
            suite: TradingSuite instance
            side: Order side (0=BUY, 1=SELL)
            size: Order size
            check_spread: Check bid/ask spread before entry

        Returns:
            BracketOrderResponse with order details
        """
        # Get instrument for tick size
        # suite.instrument is already an Instrument object after initialization
        instrument = suite.instrument
        if not instrument:
            raise ValueError("Cannot get instrument details")

        tick_size = instrument.tickSize

        # Check spread if requested
        if check_spread and hasattr(suite, "orderbook") and suite.orderbook:
            orderbook = suite.orderbook
            spread = await orderbook.get_bid_ask_spread()

            if spread is not None:
                spread_ticks = spread / tick_size
                if spread_ticks > self.max_spread_ticks:
                    raise ValueError(
                        f"Spread too wide: {spread_ticks:.1f} ticks "
                        f"(max: {self.max_spread_ticks})"
                    )

        # Calculate stop and target distances
        stop_distance = self.stop_ticks * tick_size
        target_distance = self.target_ticks * tick_size

        # Build scalping order using bracket order
        if size is None:
            raise ValueError("Size is required")

        if not suite.instrument_id:
            raise ValueError("No instrument ID available")

        if self.use_market_entry:
            # Get current price for market entry calculations
            current_price = await suite.data.get_current_price()
            if not current_price:
                raise ValueError("Cannot get current price")

            # Calculate stop and target prices based on side
            if side == 0:  # BUY
                stop_loss_price = current_price - stop_distance
                take_profit_price = current_price + target_distance
            else:  # SELL
                stop_loss_price = current_price + stop_distance
                take_profit_price = current_price - target_distance

            result = await suite.orders.place_bracket_order(
                contract_id=suite.instrument_id,
                side=side,
                size=size,
                entry_price=current_price,
                stop_loss_price=stop_loss_price,
                take_profit_price=take_profit_price,
                entry_type="market",
            )
        else:
            # Use limit at current price
            current_price = await suite.data.get_current_price()
            if not current_price:
                raise ValueError("Cannot get current price")

            # Calculate stop and target prices
            if side == 0:  # BUY
                stop_loss_price = current_price - stop_distance
                take_profit_price = current_price + target_distance
            else:  # SELL
                stop_loss_price = current_price + stop_distance
                take_profit_price = current_price - target_distance

            result = await suite.orders.place_bracket_order(
                contract_id=suite.instrument_id,
                side=side,
                size=size,
                entry_price=current_price,
                stop_loss_price=stop_loss_price,
                take_profit_price=take_profit_price,
                entry_type="limit",
            )

        logger.info(
            f"Scalping bracket order placed: {self.stop_ticks} tick stop, "
            f"{self.target_ticks} tick target"
        )

        return result


# Pre-configured template instances for common scenarios
TEMPLATES = {
    # Conservative templates
    "conservative_rr": RiskRewardTemplate(risk_reward_ratio=1.5, use_limit_entry=True),
    "conservative_atr": ATRStopTemplate(atr_multiplier=1.5, target_multiplier=2.0),
    # Standard templates
    "standard_rr": RiskRewardTemplate(risk_reward_ratio=2.0),
    "standard_atr": ATRStopTemplate(atr_multiplier=2.0, target_multiplier=3.0),
    "standard_breakout": BreakoutTemplate(),
    # Aggressive templates
    "aggressive_rr": RiskRewardTemplate(risk_reward_ratio=3.0, use_limit_entry=False),
    "aggressive_atr": ATRStopTemplate(atr_multiplier=2.5, target_multiplier=4.0),
    "aggressive_scalp": ScalpingTemplate(stop_ticks=3, target_ticks=9),
    # Scalping templates
    "tight_scalp": ScalpingTemplate(stop_ticks=2, target_ticks=4),
    "normal_scalp": ScalpingTemplate(stop_ticks=4, target_ticks=8),
    "wide_scalp": ScalpingTemplate(stop_ticks=6, target_ticks=12),
}


def get_template(name: str) -> OrderTemplate:
    """
    Get a pre-configured order template by name.

    Available templates:
        - conservative_rr: 1.5:1 risk/reward with limit entry
        - conservative_atr: 1.5x ATR stop, 2x target
        - standard_rr: 2:1 risk/reward
        - standard_atr: 2x ATR stop, 3x target
        - standard_breakout: Breakout with stop at level
        - aggressive_rr: 3:1 risk/reward with market entry
        - aggressive_atr: 2.5x ATR stop, 4x target
        - aggressive_scalp: 3 tick stop, 9 tick target
        - tight_scalp: 2 tick stop, 4 tick target
        - normal_scalp: 4 tick stop, 8 tick target
        - wide_scalp: 6 tick stop, 12 tick target

    Args:
        name: Template name

    Returns:
        OrderTemplate instance

    Example:
        ```python
        template = get_template("standard_rr")
        order = await template.create_order(suite, side=0, risk_amount=100)
        ```
    """
    if name not in TEMPLATES:
        raise ValueError(
            f"Unknown template: {name}. Available: {', '.join(TEMPLATES.keys())}"
        )
    return TEMPLATES[name]
