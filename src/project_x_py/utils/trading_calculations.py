"""
Trading-related calculations for position sizing, risk management, and price calculations.

Author: @TexasCoding
Date: 2025-08-02

Overview:
    Provides trading-related calculations for position sizing, risk management,
    and price calculations. Includes tick value calculations, position sizing
    based on risk management, price rounding to tick sizes, and risk/reward
    ratio calculations for trading strategy development.

Key Features:
    - Tick value calculations for different instruments
    - Position sizing based on risk management principles
    - Price rounding to valid tick sizes
    - Risk/reward ratio calculations
    - Position value calculations
    - Comprehensive risk management tools

Trading Calculations:
    - Tick value and price movement calculations
    - Position sizing with risk management
    - Price alignment to tick size requirements
    - Risk/reward ratio analysis
    - Position value and exposure calculations
    - Risk management and sizing optimization

Example Usage:
    ```python
    from project_x_py.utils import (
        calculate_tick_value,
        calculate_position_sizing,
        round_to_tick_size,
        calculate_risk_reward_ratio,
        calculate_position_value,
    )

    # Calculate tick value for price movement
    tick_value = calculate_tick_value(0.5, 0.1, 1.0)  # 5 ticks
    print(f"Tick value: ${tick_value}")

    # Calculate position sizing based on risk
    sizing = calculate_position_sizing(50000, 0.02, 2050, 2040, 1.0)
    print(f"Position size: {sizing['position_size']} contracts")
    print(f"Risk per trade: {sizing['actual_risk_percent']:.2%}")

    # Round price to valid tick size
    price = round_to_tick_size(2050.37, 0.1)
    print(f"Rounded price: {price}")

    # Calculate risk/reward ratio
    ratio = calculate_risk_reward_ratio(2050, 2045, 2065)
    print(f"Risk/Reward ratio: {ratio:.2f}")

    # Calculate position value
    value = calculate_position_value(5, 2050.0, 1.0, 0.1)
    print(f"Position value: ${value:,.2f}")
    ```

Risk Management Features:
    - Position sizing based on account balance and risk tolerance
    - Risk per trade calculation and validation
    - Price risk and dollar risk calculations
    - Actual vs. target risk percentage tracking
    - Risk management optimization and validation
    - Comprehensive risk analysis and reporting

Tick Value Calculations:
    - Dollar value of price movements
    - Tick size validation and error handling
    - Multi-instrument tick value support
    - Precision calculations for accurate pricing
    - Error handling for invalid inputs

Position Sizing:
    - Risk-based position sizing algorithms
    - Account balance and risk tolerance integration
    - Stop loss and entry price calculations
    - Position size optimization and validation
    - Risk percentage tracking and reporting
    - Comprehensive sizing analysis

Performance Characteristics:
    - Fast calculation algorithms for real-time trading
    - Memory-efficient calculations
    - Type-safe operations with proper validation
    - Optimized for high-frequency trading scenarios
    - Comprehensive error handling and validation

See Also:
    - `utils.portfolio_analytics`: Portfolio analysis and metrics
    - `utils.pattern_detection`: Pattern detection for trading signals
    - `utils.data_utils`: Data processing and analysis
"""

from typing import Any


def calculate_tick_value(
    price_change: float, tick_size: float, tick_value: float
) -> float:
    """
    Calculate dollar value of a price change.

    Args:
        price_change: Price difference
        tick_size: Minimum price movement
        tick_value: Dollar value per tick

    Returns:
        float: Dollar value of the price change

    Example:
        >>> # MGC moves 5 ticks
        >>> calculate_tick_value(0.5, 0.1, 1.0)
        5.0
    """
    # Validate inputs
    if tick_size <= 0:
        raise ValueError(f"tick_size must be positive, got {tick_size}")
    if tick_value < 0:
        raise ValueError(f"tick_value cannot be negative, got {tick_value}")
    if not isinstance(price_change, int | float):
        raise TypeError(f"price_change must be numeric, got {type(price_change)}")

    num_ticks = abs(price_change) / tick_size
    return num_ticks * tick_value


def calculate_position_value(
    size: int, price: float, tick_value: float, tick_size: float
) -> float:
    """
    Calculate total dollar value of a position.

    Args:
        size: Number of contracts
        price: Current price
        tick_value: Dollar value per tick
        tick_size: Minimum price movement

    Returns:
        float: Total position value in dollars

    Example:
        >>> # 5 MGC contracts at $2050
        >>> calculate_position_value(5, 2050.0, 1.0, 0.1)
        102500.0
    """
    # Validate inputs
    if tick_size <= 0:
        raise ValueError(f"tick_size must be positive, got {tick_size}")
    if tick_value < 0:
        raise ValueError(f"tick_value cannot be negative, got {tick_value}")
    if price < 0:
        raise ValueError(f"price cannot be negative, got {price}")
    if not isinstance(size, int):
        raise TypeError(f"size must be an integer, got {type(size)}")

    ticks_per_point = 1.0 / tick_size
    value_per_point = ticks_per_point * tick_value
    return abs(size) * price * value_per_point


def round_to_tick_size(price: float, tick_size: float) -> float:
    """
    Round price to nearest valid tick.

    Args:
        price: Price to round
        tick_size: Minimum price movement

    Returns:
        float: Price rounded to nearest tick

    Raises:
        ValueError: If tick_size is not positive or price is negative

    Example:
        >>> round_to_tick_size(2050.37, 0.1)
        2050.4
    """
    # Validate inputs
    if tick_size <= 0:
        raise ValueError(f"tick_size must be positive, got {tick_size}")
    if price < 0:
        raise ValueError(f"price cannot be negative, got {price}")

    return round(price / tick_size) * tick_size


def calculate_risk_reward_ratio(
    entry_price: float, stop_price: float, target_price: float
) -> float:
    """
    Calculate risk/reward ratio for a trade setup.

    Args:
        entry_price: Entry price
        stop_price: Stop loss price
        target_price: Profit target price

    Returns:
        float: Risk/reward ratio (reward / risk)

    Raises:
        ValueError: If prices are invalid (e.g., stop/target inversion)

    Example:
        >>> # Long trade: entry=2050, stop=2045, target=2065
        >>> calculate_risk_reward_ratio(2050, 2045, 2065)
        3.0
    """
    if entry_price == stop_price:
        raise ValueError("Entry price and stop price cannot be equal")

    risk = abs(entry_price - stop_price)
    reward = abs(target_price - entry_price)

    is_long = stop_price < entry_price
    if is_long and target_price <= entry_price:
        raise ValueError("For long positions, target must be above entry")
    elif not is_long and target_price >= entry_price:
        raise ValueError("For short positions, target must be below entry")

    if risk <= 0:
        return 0.0

    return reward / risk


def calculate_position_sizing(
    account_balance: float,
    risk_per_trade: float,
    entry_price: float,
    stop_loss_price: float,
    tick_value: float = 1.0,
    tick_size: float = 1.0,
) -> dict[str, Any]:
    """
    Calculate optimal position size based on risk management.

    Dollar risk per contract is ``(price_risk / tick_size) * tick_value``.
    ``tick_size`` defaults to 1.0 so callers that pass dollars-per-point as
    ``tick_value`` keep working. For MNQ use tick_size=0.25, tick_value=0.50.

    Args:
        account_balance: Current account balance
        risk_per_trade: Risk per trade as decimal (e.g., 0.02 for 2%)
        entry_price: Entry price for the trade
        stop_loss_price: Stop loss price
        tick_value: Dollar value per tick
        tick_size: Minimum price increment (default 1.0 for compatibility)

    Returns:
        Dict with position sizing information

    Example:
        >>> sizing = calculate_position_sizing(50000, 0.02, 2050, 2040, 1.0)
        >>> print(f"Position size: {sizing['position_size']} contracts")
    """
    # Validate inputs
    if account_balance <= 0:
        raise ValueError(f"account_balance must be positive, got {account_balance}")
    if not 0 < risk_per_trade <= 1:
        raise ValueError(
            f"risk_per_trade must be between 0 and 1, got {risk_per_trade}"
        )
    if entry_price <= 0:
        raise ValueError(f"entry_price must be positive, got {entry_price}")
    if stop_loss_price <= 0:
        raise ValueError(f"stop_loss_price must be positive, got {stop_loss_price}")
    if tick_value <= 0:
        raise ValueError(f"tick_value must be positive, got {tick_value}")
    if tick_size <= 0:
        raise ValueError(f"tick_size must be positive, got {tick_size}")

    try:
        # Calculate risk per share/contract
        price_risk = abs(entry_price - stop_loss_price)

        if price_risk == 0:
            return {"error": "No price risk (entry equals stop loss)"}

        # ticks * tick_value, not price_risk * tick_value (MNQ is 4 ticks/point)
        ticks = price_risk / tick_size
        dollar_risk_per_contract = ticks * tick_value

        # Calculate maximum dollar risk for this trade
        max_dollar_risk = account_balance * risk_per_trade

        # Calculate position size
        position_size = max_dollar_risk / dollar_risk_per_contract

        # Round down to whole contracts
        position_size = int(position_size)

        # Calculate actual risk
        actual_dollar_risk = position_size * dollar_risk_per_contract
        actual_risk_percent = actual_dollar_risk / account_balance

        return {
            "position_size": position_size,
            "price_risk": price_risk,
            "dollar_risk_per_contract": dollar_risk_per_contract,
            "max_dollar_risk": max_dollar_risk,
            "actual_dollar_risk": actual_dollar_risk,
            "actual_risk_percent": actual_risk_percent,
            "risk_reward_ratio": None,  # Can be calculated if target provided
        }

    except Exception as e:
        return {"error": str(e)}
