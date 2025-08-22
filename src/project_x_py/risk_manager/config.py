"""Risk management configuration."""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass
class RiskConfig:
    """Configuration for risk management rules and parameters.

    This configuration allows flexible risk management across different
    trading strategies and account sizes.
    """

    # Per-trade risk limits
    max_risk_per_trade: Decimal = Decimal("0.01")  # 1% per trade
    max_risk_per_trade_amount: Decimal | None = None  # Dollar amount limit

    # Daily risk limits
    max_daily_loss: Decimal = Decimal("0.03")  # 3% daily loss
    max_daily_loss_amount: Decimal | None = None  # Dollar amount limit
    max_daily_trades: int = 10  # Maximum trades per day

    # Position limits
    max_position_size: int = 10  # Maximum contracts per position
    max_positions: int = 3  # Maximum concurrent positions
    max_portfolio_risk: Decimal = Decimal("0.05")  # 5% total portfolio risk

    # Stop-loss configuration
    use_stop_loss: bool = True
    stop_loss_type: str = "fixed"  # "fixed", "atr", "percentage"
    default_stop_distance: Decimal = Decimal("50")  # Default stop distance in points
    default_stop_atr_multiplier: Decimal = Decimal(
        "2.0"
    )  # ATR multiplier for dynamic stops

    # Take-profit configuration
    use_take_profit: bool = True
    default_risk_reward_ratio: Decimal = Decimal("2.0")  # 1:2 risk/reward by default

    # Trailing stop configuration
    use_trailing_stops: bool = True
    trailing_stop_distance: Decimal = Decimal("20")  # Points behind current price
    trailing_stop_trigger: Decimal = Decimal(
        "30"
    )  # Profit points before trailing starts

    # Advanced risk rules
    scale_in_enabled: bool = False  # Allow position scaling
    scale_out_enabled: bool = True  # Allow partial exits
    martingale_enabled: bool = False  # DANGEROUS: Double down on losses

    # Time-based rules
    restrict_trading_hours: bool = False
    allowed_trading_hours: list[tuple[str, str]] = field(
        default_factory=lambda: [("09:30", "16:00")]
    )
    avoid_news_events: bool = True
    news_blackout_minutes: int = 30  # Minutes before/after news

    # Correlation limits
    max_correlated_positions: int = 2  # Max positions in correlated instruments
    correlation_threshold: Decimal = Decimal("0.7")  # Correlation coefficient threshold

    # Kelly Criterion parameters (for advanced position sizing)
    use_kelly_criterion: bool = False
    kelly_fraction: Decimal = Decimal("0.25")  # Use 25% of Kelly recommendation
    min_trades_for_kelly: int = 30  # Minimum trades before using Kelly

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary."""
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}
