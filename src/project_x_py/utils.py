"""
ProjectX Utility Functions

This module contains utility functions used throughout the ProjectX client.
"""

import logging
import os
import re
import time
from datetime import datetime, timedelta
from typing import Any

import polars as pl
import pytz


def get_polars_rows(df: pl.DataFrame) -> int:
    """Get number of rows from polars DataFrame safely."""
    return getattr(df, "n_rows", 0)


def get_polars_last_value(df: pl.DataFrame, column: str) -> Any:
    """Get the last value from a polars DataFrame column safely."""
    if df.is_empty():
        return None
    return df.select(pl.col(column)).tail(1).item()


def setup_logging(
    level: str = "INFO",
    format_string: str | None = None,
    filename: str | None = None,
) -> logging.Logger:
    """
    Set up logging configuration for the ProjectX client.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_string: Custom format string for log messages
        filename: Optional filename to write logs to

    Returns:
        Logger instance
    """
    if format_string is None:
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    logging.basicConfig(
        level=getattr(logging, level.upper()), format=format_string, filename=filename
    )

    return logging.getLogger("project_x_py")


def get_env_var(name: str, default: Any = None, required: bool = False) -> str:
    """
    Get environment variable with optional default and validation.

    Args:
        name: Environment variable name
        default: Default value if not found
        required: Whether the variable is required

    Returns:
        Environment variable value

    Raises:
        ValueError: If required variable is missing
    """
    value = os.getenv(name, default)
    if required and value is None:
        raise ValueError(f"Required environment variable '{name}' not found")
    return value


def format_price(price: float, decimals: int = 2) -> str:
    """Format price for display."""
    return f"${price:,.{decimals}f}"


def format_volume(volume: int) -> str:
    """Format volume for display."""
    if volume >= 1_000_000:
        return f"{volume / 1_000_000:.1f}M"
    elif volume >= 1_000:
        return f"{volume / 1_000:.1f}K"
    else:
        return str(volume)


def is_market_hours(timezone: str = "America/Chicago") -> bool:
    """
    Check if it's currently market hours (CME futures).

    Args:
        timezone: Timezone to check (default: CME time)

    Returns:
        bool: True if market is open
    """
    tz = pytz.timezone(timezone)
    now = datetime.now(tz)

    # CME futures markets are generally open Sunday 5 PM to Friday 4 PM CT
    # with a daily maintenance break from 4 PM to 5 PM CT
    weekday = now.weekday()  # Monday = 0, Sunday = 6
    hour = now.hour

    # Friday after 4 PM CT
    if weekday == 4 and hour >= 16:
        return False

    # Saturday (closed)
    if weekday == 5:
        return False

    # Sunday before 5 PM CT
    if weekday == 6 and hour < 17:
        return False

    # Daily maintenance break (4 PM - 5 PM CT)
    return hour != 16


# ================================================================================
# NEW UTILITY FUNCTIONS FOR STRATEGY DEVELOPERS
# ================================================================================


def validate_contract_id(contract_id: str) -> bool:
    """
    Validate ProjectX contract ID format.

    Args:
        contract_id: Contract ID to validate

    Returns:
        bool: True if valid format

    Example:
        >>> validate_contract_id("CON.F.US.MGC.M25")
        True
        >>> validate_contract_id("MGC")
        True
        >>> validate_contract_id("invalid.contract")
        False
    """
    # Full contract ID format: CON.F.US.MGC.M25
    full_pattern = r"^CON\.F\.US\.[A-Z]{2,4}\.[FGHJKMNQUVXZ]\d{2}$"

    # Simple symbol format: MGC, NQ, etc.
    simple_pattern = r"^[A-Z]{2,4}$"

    return bool(
        re.match(full_pattern, contract_id) or re.match(simple_pattern, contract_id)
    )


def extract_symbol_from_contract_id(contract_id: str) -> str | None:
    """
    Extract the base symbol from a full contract ID.

    Args:
        contract_id: Full contract ID or symbol

    Returns:
        str: Base symbol (e.g., "MGC" from "CON.F.US.MGC.M25")
        None: If extraction fails

    Example:
        >>> extract_symbol_from_contract_id("CON.F.US.MGC.M25")
        'MGC'
        >>> extract_symbol_from_contract_id("MGC")
        'MGC'
    """
    if not contract_id:
        return None

    # If it's already a simple symbol, return it
    if re.match(r"^[A-Z]{2,4}$", contract_id):
        return contract_id

    # Extract from full contract ID
    match = re.match(r"^CON\.F\.US\.([A-Z]{2,4})\.[FGHJKMNQUVXZ]\d{2}$", contract_id)
    return match.group(1) if match else None


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
    if tick_size <= 0:
        return 0.0

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
    if tick_size <= 0:
        return 0.0

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

    Example:
        >>> round_to_tick_size(2050.37, 0.1)
        2050.4
    """
    if tick_size <= 0:
        return price

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

    Example:
        >>> # Long trade: entry=2050, stop=2045, target=2065
        >>> calculate_risk_reward_ratio(2050, 2045, 2065)
        3.0
    """
    risk = abs(entry_price - stop_price)
    reward = abs(target_price - entry_price)

    if risk <= 0:
        return 0.0

    return reward / risk


def get_market_session_info(timezone: str = "America/Chicago") -> dict[str, Any]:
    """
    Get detailed market session information.

    Args:
        timezone: Market timezone

    Returns:
        dict: Market session details

    Example:
        >>> info = get_market_session_info()
        >>> print(f"Market open: {info['is_open']}")
        >>> print(f"Next session: {info['next_session_start']}")
    """
    tz = pytz.timezone(timezone)
    now = datetime.now(tz)
    weekday = now.weekday()
    hour = now.hour

    # Initialize variables
    next_open = None
    next_close = None

    # Calculate next session times
    if weekday == 4 and hour >= 16:  # Friday after close
        # Next open is Sunday 5 PM
        days_until_sunday = (6 - weekday) % 7
        next_open = now.replace(hour=17, minute=0, second=0, microsecond=0)
        next_open += timedelta(days=days_until_sunday)
    elif weekday == 5:  # Saturday
        # Next open is Sunday 5 PM
        next_open = now.replace(hour=17, minute=0, second=0, microsecond=0)
        next_open += timedelta(days=1)
    elif weekday == 6 and hour < 17:  # Sunday before open
        # Opens today at 5 PM
        next_open = now.replace(hour=17, minute=0, second=0, microsecond=0)
    elif hour == 16:  # Daily maintenance
        # Reopens in 1 hour
        next_open = now.replace(hour=17, minute=0, second=0, microsecond=0)
    else:
        # Market is open, next close varies
        if weekday == 4:  # Friday
            next_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
        else:  # Other days
            next_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
            if now.hour >= 16:
                next_close += timedelta(days=1)

    is_open = is_market_hours(timezone)

    session_info = {
        "is_open": is_open,
        "current_time": now,
        "timezone": timezone,
        "weekday": now.strftime("%A"),
    }

    if not is_open and next_open:
        session_info["next_session_start"] = next_open
        session_info["time_until_open"] = next_open - now
    elif is_open and next_close:
        session_info["next_session_end"] = next_close
        session_info["time_until_close"] = next_close - now

    return session_info


def convert_timeframe_to_seconds(timeframe: str) -> int:
    """
    Convert timeframe string to seconds.

    Args:
        timeframe: Timeframe (e.g., "1min", "5min", "1hr", "1day")

    Returns:
        int: Timeframe in seconds

    Example:
        >>> convert_timeframe_to_seconds("5min")
        300
        >>> convert_timeframe_to_seconds("1hr")
        3600
    """
    timeframe = timeframe.lower()

    # Parse number and unit
    import re

    match = re.match(r"(\d+)(.*)", timeframe)
    if not match:
        return 0

    number = int(match.group(1))
    unit = match.group(2)

    # Convert to seconds
    multipliers = {
        "s": 1,
        "sec": 1,
        "second": 1,
        "seconds": 1,
        "m": 60,
        "min": 60,
        "minute": 60,
        "minutes": 60,
        "h": 3600,
        "hr": 3600,
        "hour": 3600,
        "hours": 3600,
        "d": 86400,
        "day": 86400,
        "days": 86400,
        "w": 604800,
        "week": 604800,
        "weeks": 604800,
    }

    return number * multipliers.get(unit, 0)


def create_data_snapshot(data: pl.DataFrame, description: str = "") -> dict[str, Any]:
    """
    Create a comprehensive snapshot of DataFrame for debugging/analysis.

    Args:
        data: Polars DataFrame
        description: Optional description

    Returns:
        dict: Data snapshot with statistics

    Example:
        >>> snapshot = create_data_snapshot(ohlcv_data, "MGC 5min data")
        >>> print(f"Rows: {snapshot['row_count']}")
        >>> print(f"Timespan: {snapshot['timespan']}")
    """
    if data.is_empty():
        return {
            "description": description,
            "row_count": 0,
            "columns": [],
            "empty": True,
        }

    snapshot = {
        "description": description,
        "row_count": len(data),
        "columns": data.columns,
        "dtypes": {
            col: str(dtype)
            for col, dtype in zip(data.columns, data.dtypes, strict=False)
        },
        "empty": False,
        "created_at": datetime.now(),
    }

    # Add time range if timestamp column exists
    timestamp_cols = [col for col in data.columns if "time" in col.lower()]
    if timestamp_cols:
        ts_col = timestamp_cols[0]
        try:
            first_time = data.select(pl.col(ts_col)).head(1).item()
            last_time = data.select(pl.col(ts_col)).tail(1).item()
            snapshot["time_range"] = {"start": first_time, "end": last_time}
            snapshot["timespan"] = (
                str(last_time - first_time) if hasattr(last_time, "__sub__") else None
            )
        except Exception:
            pass

    # Add basic statistics for numeric columns
    numeric_cols = [
        col
        for col, dtype in zip(data.columns, data.dtypes, strict=False)
        if dtype in [pl.Float64, pl.Float32, pl.Int64, pl.Int32]
    ]

    if numeric_cols:
        try:
            stats = {}
            for col in numeric_cols[:5]:  # Limit to first 5 numeric columns
                col_data = data.select(pl.col(col))
                stats[col] = {
                    "min": col_data.min().item(),
                    "max": col_data.max().item(),
                    "mean": col_data.mean().item(),
                }
            snapshot["statistics"] = stats
        except Exception:
            pass

    return snapshot


class RateLimiter:
    """
    Simple rate limiter for API calls.

    Example:
        >>> limiter = RateLimiter(requests_per_minute=60)
        >>> with limiter:
        ...     # Make API call
        ...     response = api_call()
    """

    def __init__(self, requests_per_minute: int = 60):
        """Initialize rate limiter."""
        self.requests_per_minute = requests_per_minute
        self.min_interval = 60.0 / requests_per_minute
        self.last_request_time = 0.0

    def __enter__(self):
        """Context manager entry - enforce rate limit."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.min_interval:
            sleep_time = self.min_interval - time_since_last
            time.sleep(sleep_time)

        self.last_request_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""

    def wait_if_needed(self) -> None:
        """Wait if needed to respect rate limit."""
        with self:
            pass


# ================================================================================
# DATA ANALYSIS HELPERS
# ================================================================================


def calculate_sma(
    data: pl.DataFrame, column: str = "close", period: int = 20
) -> pl.DataFrame:
    """
    Calculate Simple Moving Average.

    Args:
        data: DataFrame with OHLCV data
        column: Column to calculate SMA for
        period: Period for moving average

    Returns:
        DataFrame with SMA column added

    Example:
        >>> data_with_sma = calculate_sma(ohlcv_data, period=20)
        >>> print(data_with_sma.columns)  # Now includes 'sma_20'
    """
    if column not in data.columns:
        raise ValueError(f"Column '{column}' not found in data")

    return data.with_columns(
        pl.col(column).rolling_mean(window_size=period).alias(f"sma_{period}")
    )


def calculate_ema(
    data: pl.DataFrame, column: str = "close", period: int = 20
) -> pl.DataFrame:
    """
    Calculate Exponential Moving Average.

    Args:
        data: DataFrame with OHLCV data
        column: Column to calculate EMA for
        period: Period for moving average

    Returns:
        DataFrame with EMA column added

    Example:
        >>> data_with_ema = calculate_ema(ohlcv_data, period=20)
        >>> print(data_with_ema.columns)  # Now includes 'ema_20'
    """
    if column not in data.columns:
        raise ValueError(f"Column '{column}' not found in data")

    alpha = 2.0 / (period + 1)

    return data.with_columns(
        pl.col(column).ewm_mean(alpha=alpha).alias(f"ema_{period}")
    )


def calculate_rsi(
    data: pl.DataFrame, column: str = "close", period: int = 14
) -> pl.DataFrame:
    """
    Calculate Relative Strength Index.

    Args:
        data: DataFrame with OHLCV data
        column: Column to calculate RSI for
        period: Period for RSI calculation

    Returns:
        DataFrame with RSI column added

    Example:
        >>> data_with_rsi = calculate_rsi(ohlcv_data, period=14)
        >>> print(data_with_rsi.columns)  # Now includes 'rsi_14'
    """
    if column not in data.columns:
        raise ValueError(f"Column '{column}' not found in data")

    # Calculate price changes
    data_with_changes = data.with_columns(pl.col(column).diff().alias("price_change"))

    # Separate gains and losses
    data_with_gains_losses = data_with_changes.with_columns(
        [
            pl.when(pl.col("price_change") > 0)
            .then(pl.col("price_change"))
            .otherwise(0)
            .alias("gain"),
            pl.when(pl.col("price_change") < 0)
            .then(-pl.col("price_change"))
            .otherwise(0)
            .alias("loss"),
        ]
    )

    # Calculate average gains and losses
    data_with_averages = data_with_gains_losses.with_columns(
        [
            pl.col("gain").rolling_mean(window_size=period).alias("avg_gain"),
            pl.col("loss").rolling_mean(window_size=period).alias("avg_loss"),
        ]
    )

    # Calculate RSI
    result = data_with_averages.with_columns(
        (100 - (100 / (1 + pl.col("avg_gain") / pl.col("avg_loss")))).alias(
            f"rsi_{period}"
        )
    )

    # Remove intermediate columns
    return result.drop(["price_change", "gain", "loss", "avg_gain", "avg_loss"])


def calculate_bollinger_bands(
    data: pl.DataFrame, column: str = "close", period: int = 20, std_dev: float = 2.0
) -> pl.DataFrame:
    """
    Calculate Bollinger Bands.

    Args:
        data: DataFrame with OHLCV data
        column: Column to calculate bands for
        period: Period for moving average
        std_dev: Standard deviation multiplier

    Returns:
        DataFrame with Bollinger Bands columns added

    Example:
        >>> data_with_bb = calculate_bollinger_bands(ohlcv_data)
        >>> print(data_with_bb.columns)  # Now includes bb_upper, bb_lower, bb_middle
    """
    if column not in data.columns:
        raise ValueError(f"Column '{column}' not found in data")

    return data.with_columns(
        [
            # Middle band (SMA)
            pl.col(column).rolling_mean(window_size=period).alias("bb_middle"),
            # Upper band
            (
                pl.col(column).rolling_mean(window_size=period)
                + std_dev * pl.col(column).rolling_std(window_size=period)
            ).alias("bb_upper"),
            # Lower band
            (
                pl.col(column).rolling_mean(window_size=period)
                - std_dev * pl.col(column).rolling_std(window_size=period)
            ).alias("bb_lower"),
        ]
    )


def find_support_resistance_levels(
    data: pl.DataFrame,
    price_column: str = "close",
    volume_column: str = "volume",
    min_touches: int = 3,
    tolerance_pct: float = 0.1,
) -> list[dict[str, Any]]:
    """
    Find support and resistance levels from price data.

    Args:
        data: DataFrame with OHLCV data
        price_column: Column containing prices
        volume_column: Column containing volume
        min_touches: Minimum number of touches to confirm level
        tolerance_pct: Price tolerance as percentage

    Returns:
        List of support/resistance levels with metadata

    Example:
        >>> levels = find_support_resistance_levels(ohlcv_data)
        >>> for level in levels:
        ...     print(f"Level: ${level['price']:.2f}, Touches: {level['touches']}")
    """
    if data.is_empty() or price_column not in data.columns:
        return []

    # Get price levels and their frequencies
    prices = data.select(pl.col(price_column)).to_series().to_list()
    volumes = (
        data.select(pl.col(volume_column)).to_series().to_list()
        if volume_column in data.columns
        else [1] * len(prices)
    )

    # Simple algorithm to find levels with multiple touches
    levels = []
    price_tolerance = tolerance_pct / 100

    for _, price in enumerate(prices):
        touches = []
        total_volume = 0

        for j, other_price in enumerate(prices):
            if abs(other_price - price) / price <= price_tolerance:
                touches.append(j)
                total_volume += volumes[j]

        if len(touches) >= min_touches:
            # Check if we already have a similar level
            duplicate = False
            for existing_level in levels:
                if abs(existing_level["price"] - price) / price <= price_tolerance:
                    duplicate = True
                    break

            if not duplicate:
                levels.append(
                    {
                        "price": price,
                        "touches": len(touches),
                        "total_volume": total_volume,
                        "first_touch_index": min(touches),
                        "last_touch_index": max(touches),
                        "strength": len(touches)
                        * total_volume
                        / len(prices),  # Combined metric
                    }
                )

    # Sort by strength (descending)
    return sorted(levels, key=lambda x: x["strength"], reverse=True)
