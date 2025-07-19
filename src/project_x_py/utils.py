"""
ProjectX Utility Functions

Author: TexasCoding
Date: June 2025

This module contains utility functions used throughout the ProjectX client.
Note: Technical indicators have been moved to the indicators module.
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
# STATISTICAL ANALYSIS FUNCTIONS
# ================================================================================


def calculate_correlation_matrix(
    data: pl.DataFrame,
    columns: list[str] | None = None,
    method: str = "pearson",
) -> pl.DataFrame:
    """
    Calculate correlation matrix for specified columns.

    Args:
        data: DataFrame with numeric data
        columns: Columns to include (default: all numeric columns)
        method: Correlation method ("pearson", "spearman")

    Returns:
        DataFrame with correlation matrix

    Example:
        >>> corr_matrix = calculate_correlation_matrix(
        ...     ohlcv_data, ["open", "high", "low", "close"]
        ... )
        >>> print(corr_matrix)
    """
    if columns is None:
        # Auto-detect numeric columns
        columns = [
            col
            for col, dtype in zip(data.columns, data.dtypes, strict=False)
            if dtype in [pl.Float64, pl.Float32, pl.Int64, pl.Int32]
        ]

    if not columns:
        raise ValueError("No numeric columns found")

    # Simple correlation calculation using polars
    correlations = {}
    for col1 in columns:
        correlations[col1] = {}
        for col2 in columns:
            if col1 == col2:
                correlations[col1][col2] = 1.0
            else:
                # Calculate Pearson correlation
                corr_result = data.select(
                    [pl.corr(col1, col2).alias("correlation")]
                ).item(0, "correlation")
                correlations[col1][col2] = (
                    corr_result if corr_result is not None else 0.0
                )

    # Convert to DataFrame
    corr_data = []
    for col1 in columns:
        row = {"column": col1}
        for col2 in columns:
            row[col2] = correlations[col1][col2]
        corr_data.append(row)

    return pl.from_dicts(corr_data)


def calculate_volatility_metrics(
    data: pl.DataFrame,
    price_column: str = "close",
    return_column: str | None = None,
    window: int = 20,
) -> dict[str, Any]:
    """
    Calculate various volatility metrics.

    Args:
        data: DataFrame with price data
        price_column: Price column for calculations
        return_column: Pre-calculated returns column (optional)
        window: Window for rolling calculations

    Returns:
        Dict with volatility metrics

    Example:
        >>> vol_metrics = calculate_volatility_metrics(ohlcv_data)
        >>> print(f"Annualized Volatility: {vol_metrics['annualized_volatility']:.2%}")
    """
    if price_column not in data.columns:
        raise ValueError(f"Column '{price_column}' not found in data")

    # Calculate returns if not provided
    if return_column is None:
        data = data.with_columns(pl.col(price_column).pct_change().alias("returns"))
        return_column = "returns"

    if data.is_empty():
        return {"error": "No data available"}

    try:
        # Calculate various volatility measures
        returns_data = data.select(pl.col(return_column)).drop_nulls()

        if returns_data.is_empty():
            return {"error": "No valid returns data"}

        std_dev = returns_data.std().item()
        mean_return = returns_data.mean().item()

        # Calculate rolling volatility
        rolling_vol = (
            data.with_columns(
                pl.col(return_column)
                .rolling_std(window_size=window)
                .alias("rolling_vol")
            )
            .select("rolling_vol")
            .drop_nulls()
        )

        metrics = {
            "volatility": std_dev or 0.0,
            "annualized_volatility": (std_dev or 0.0)
            * (252**0.5),  # Assuming 252 trading days
            "mean_return": mean_return or 0.0,
            "annualized_return": (mean_return or 0.0) * 252,
        }

        if not rolling_vol.is_empty():
            metrics.update(
                {
                    "avg_rolling_volatility": rolling_vol.mean().item() or 0.0,
                    "max_rolling_volatility": rolling_vol.max().item() or 0.0,
                    "min_rolling_volatility": rolling_vol.min().item() or 0.0,
                }
            )

        return metrics

    except Exception as e:
        return {"error": str(e)}


def calculate_sharpe_ratio(
    data: pl.DataFrame,
    return_column: str = "returns",
    risk_free_rate: float = 0.02,
    periods_per_year: int = 252,
) -> float:
    """
    Calculate Sharpe ratio.

    Args:
        data: DataFrame with returns data
        return_column: Returns column name
        risk_free_rate: Annual risk-free rate
        periods_per_year: Number of periods per year

    Returns:
        Sharpe ratio

    Example:
        >>> # First calculate returns
        >>> data = data.with_columns(pl.col("close").pct_change().alias("returns"))
        >>> sharpe = calculate_sharpe_ratio(data)
        >>> print(f"Sharpe Ratio: {sharpe:.2f}")
    """
    if return_column not in data.columns:
        raise ValueError(f"Column '{return_column}' not found in data")

    returns_data = data.select(pl.col(return_column)).drop_nulls()

    if returns_data.is_empty():
        return 0.0

    try:
        mean_return = returns_data.mean().item() or 0.0
        std_return = returns_data.std().item() or 0.0

        if std_return == 0:
            return 0.0

        # Annualize the metrics
        annualized_return = mean_return * periods_per_year
        annualized_volatility = std_return * (periods_per_year**0.5)

        # Calculate Sharpe ratio
        excess_return = annualized_return - risk_free_rate
        return excess_return / annualized_volatility

    except Exception:
        return 0.0


def calculate_max_drawdown(
    data: pl.DataFrame,
    price_column: str = "close",
) -> dict[str, Any]:
    """
    Calculate maximum drawdown.

    Args:
        data: DataFrame with price data
        price_column: Price column name

    Returns:
        Dict with drawdown metrics

    Example:
        >>> dd_metrics = calculate_max_drawdown(ohlcv_data)
        >>> print(f"Max Drawdown: {dd_metrics['max_drawdown']:.2%}")
    """
    if price_column not in data.columns:
        raise ValueError(f"Column '{price_column}' not found in data")

    if data.is_empty():
        return {"max_drawdown": 0.0, "max_drawdown_duration": 0}

    try:
        # Calculate cumulative maximum (peak) using rolling_max with large window
        data_length = len(data)
        data_with_peak = data.with_columns(
            pl.col(price_column).rolling_max(window_size=data_length).alias("peak")
        )

        # Calculate drawdown
        data_with_dd = data_with_peak.with_columns(
            ((pl.col(price_column) / pl.col("peak")) - 1).alias("drawdown")
        )

        # Get maximum drawdown
        max_dd = data_with_dd.select(pl.col("drawdown").min()).item() or 0.0

        # Calculate drawdown duration (simplified)
        dd_series = data_with_dd.select("drawdown").to_series()
        max_duration = 0
        current_duration = 0

        for dd in dd_series:
            if dd < 0:  # In drawdown
                current_duration += 1
                max_duration = max(max_duration, current_duration)
            else:  # Recovery
                current_duration = 0

        return {
            "max_drawdown": max_dd,
            "max_drawdown_duration": max_duration,
        }

    except Exception as e:
        return {"error": str(e)}


# ================================================================================
# PATTERN RECOGNITION HELPERS
# ================================================================================


def detect_candlestick_patterns(
    data: pl.DataFrame,
    open_col: str = "open",
    high_col: str = "high",
    low_col: str = "low",
    close_col: str = "close",
) -> pl.DataFrame:
    """
    Detect basic candlestick patterns.

    Args:
        data: DataFrame with OHLCV data
        open_col: Open price column
        high_col: High price column
        low_col: Low price column
        close_col: Close price column

    Returns:
        DataFrame with pattern detection columns added

    Example:
        >>> patterns = detect_candlestick_patterns(ohlcv_data)
        >>> doji_count = patterns.filter(pl.col("doji") == True).height
        >>> print(f"Doji patterns found: {doji_count}")
    """
    required_cols = [open_col, high_col, low_col, close_col]
    for col in required_cols:
        if col not in data.columns:
            raise ValueError(f"Column '{col}' not found in data")

    # Calculate basic metrics
    result = data.with_columns(
        [
            (pl.col(close_col) - pl.col(open_col)).alias("body"),
            (pl.col(high_col) - pl.col(low_col)).alias("range"),
            (pl.col(high_col) - pl.max_horizontal([open_col, close_col])).alias(
                "upper_shadow"
            ),
            (pl.min_horizontal([open_col, close_col]) - pl.col(low_col)).alias(
                "lower_shadow"
            ),
        ]
    )

    # Pattern detection
    result = result.with_columns(
        [
            # Doji: Very small body relative to range
            (pl.col("body").abs() <= 0.1 * pl.col("range")).alias("doji"),
            # Hammer: Small body, long lower shadow, little upper shadow
            (
                (pl.col("body").abs() <= 0.3 * pl.col("range"))
                & (pl.col("lower_shadow") >= 2 * pl.col("body").abs())
                & (pl.col("upper_shadow") <= 0.1 * pl.col("range"))
            ).alias("hammer"),
            # Shooting Star: Small body, long upper shadow, little lower shadow
            (
                (pl.col("body").abs() <= 0.3 * pl.col("range"))
                & (pl.col("upper_shadow") >= 2 * pl.col("body").abs())
                & (pl.col("lower_shadow") <= 0.1 * pl.col("range"))
            ).alias("shooting_star"),
            # Bullish/Bearish flags
            (pl.col("body") > 0).alias("bullish_candle"),
            (pl.col("body") < 0).alias("bearish_candle"),
            # Long body candles (strong moves)
            (pl.col("body").abs() >= 0.7 * pl.col("range")).alias("long_body"),
        ]
    )

    # Remove intermediate calculation columns
    return result.drop(["body", "range", "upper_shadow", "lower_shadow"])


def detect_chart_patterns(
    data: pl.DataFrame,
    price_column: str = "close",
    window: int = 20,
) -> dict[str, Any]:
    """
    Detect basic chart patterns.

    Args:
        data: DataFrame with price data
        price_column: Price column to analyze
        window: Window size for pattern detection

    Returns:
        Dict with detected patterns and their locations

    Example:
        >>> patterns = detect_chart_patterns(ohlcv_data)
        >>> print(f"Double tops found: {len(patterns['double_tops'])}")
    """
    if price_column not in data.columns:
        raise ValueError(f"Column '{price_column}' not found in data")

    if len(data) < window * 2:
        return {"error": "Insufficient data for pattern detection"}

    try:
        prices = data.select(pl.col(price_column)).to_series().to_list()

        patterns = {
            "double_tops": [],
            "double_bottoms": [],
            "breakouts": [],
            "trend_reversals": [],
        }

        # Simple pattern detection logic
        for i in range(window, len(prices) - window):
            local_max = max(prices[i - window : i + window + 1])
            local_min = min(prices[i - window : i + window + 1])
            current_price = prices[i]

            # Double top detection (simplified)
            if current_price == local_max:
                # Look for another high nearby
                for j in range(i + window // 2, min(i + window, len(prices))):
                    if (
                        abs(prices[j] - current_price) / current_price < 0.02
                    ):  # Within 2%
                        patterns["double_tops"].append(
                            {
                                "index1": i,
                                "index2": j,
                                "price": current_price,
                                "strength": local_max - local_min,
                            }
                        )
                        break

            # Double bottom detection (simplified)
            if current_price == local_min:
                # Look for another low nearby
                for j in range(i + window // 2, min(i + window, len(prices))):
                    if (
                        abs(prices[j] - current_price) / current_price < 0.02
                    ):  # Within 2%
                        patterns["double_bottoms"].append(
                            {
                                "index1": i,
                                "index2": j,
                                "price": current_price,
                                "strength": local_max - local_min,
                            }
                        )
                        break

        return patterns

    except Exception as e:
        return {"error": str(e)}


# ================================================================================
# PORTFOLIO ANALYSIS TOOLS
# ================================================================================


def calculate_portfolio_metrics(
    trades: list[dict],
    initial_balance: float = 100000.0,
) -> dict[str, Any]:
    """
    Calculate comprehensive portfolio performance metrics.

    Args:
        trades: List of trade dictionaries with 'pnl', 'size', 'timestamp' fields
        initial_balance: Starting portfolio balance

    Returns:
        Dict with portfolio metrics

    Example:
        >>> trades = [
        ...     {"pnl": 500, "size": 1, "timestamp": "2024-01-01"},
        ...     {"pnl": -200, "size": 2, "timestamp": "2024-01-02"},
        ... ]
        >>> metrics = calculate_portfolio_metrics(trades)
        >>> print(f"Total Return: {metrics['total_return']:.2%}")
    """
    if not trades:
        return {"error": "No trades provided"}

    try:
        # Extract P&L values
        pnls = [trade.get("pnl", 0) for trade in trades]
        total_pnl = sum(pnls)

        # Basic metrics
        total_trades = len(trades)
        winning_trades = [pnl for pnl in pnls if pnl > 0]
        losing_trades = [pnl for pnl in pnls if pnl < 0]

        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
        avg_win = sum(winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = sum(losing_trades) / len(losing_trades) if losing_trades else 0

        # Profit factor
        gross_profit = sum(winning_trades)
        gross_loss = abs(sum(losing_trades))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

        # Returns
        total_return = total_pnl / initial_balance

        # Calculate equity curve for drawdown
        equity_curve = [initial_balance]
        for pnl in pnls:
            equity_curve.append(equity_curve[-1] + pnl)

        # Max drawdown
        peak = equity_curve[0]
        max_dd = 0
        max_dd_duration = 0
        current_dd_duration = 0

        for equity in equity_curve[1:]:
            if equity > peak:
                peak = equity
                current_dd_duration = 0
            else:
                dd = (peak - equity) / peak
                max_dd = max(max_dd, dd)
                current_dd_duration += 1
                max_dd_duration = max(max_dd_duration, current_dd_duration)

        # Expectancy
        expectancy = (win_rate * avg_win) + ((1 - win_rate) * avg_loss)

        return {
            "total_trades": total_trades,
            "total_pnl": total_pnl,
            "total_return": total_return,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "max_drawdown": max_dd,
            "max_drawdown_duration": max_dd_duration,
            "expectancy": expectancy,
            "gross_profit": gross_profit,
            "gross_loss": gross_loss,
            "largest_win": max(pnls) if pnls else 0,
            "largest_loss": min(pnls) if pnls else 0,
        }

    except Exception as e:
        return {"error": str(e)}


def calculate_position_sizing(
    account_balance: float,
    risk_per_trade: float,
    entry_price: float,
    stop_loss_price: float,
    tick_value: float = 1.0,
) -> dict[str, Any]:
    """
    Calculate optimal position size based on risk management.

    Args:
        account_balance: Current account balance
        risk_per_trade: Risk per trade as decimal (e.g., 0.02 for 2%)
        entry_price: Entry price for the trade
        stop_loss_price: Stop loss price
        tick_value: Dollar value per tick

    Returns:
        Dict with position sizing information

    Example:
        >>> sizing = calculate_position_sizing(50000, 0.02, 2050, 2040, 1.0)
        >>> print(f"Position size: {sizing['position_size']} contracts")
    """
    try:
        # Calculate risk per share/contract
        price_risk = abs(entry_price - stop_loss_price)

        if price_risk == 0:
            return {"error": "No price risk (entry equals stop loss)"}

        # Calculate dollar risk
        dollar_risk_per_contract = price_risk * tick_value

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


# ================================================================================
# MARKET MICROSTRUCTURE ANALYSIS
# ================================================================================


def analyze_bid_ask_spread(
    data: pl.DataFrame,
    bid_column: str = "bid",
    ask_column: str = "ask",
    mid_column: str | None = None,
) -> dict[str, Any]:
    """
    Analyze bid-ask spread characteristics.

    Args:
        data: DataFrame with bid/ask data
        bid_column: Bid price column
        ask_column: Ask price column
        mid_column: Mid price column (optional, will calculate if not provided)

    Returns:
        Dict with spread analysis

    Example:
        >>> spread_analysis = analyze_bid_ask_spread(market_data)
        >>> print(f"Average spread: ${spread_analysis['avg_spread']:.4f}")
    """
    required_cols = [bid_column, ask_column]
    for col in required_cols:
        if col not in data.columns:
            raise ValueError(f"Column '{col}' not found in data")

    if data.is_empty():
        return {"error": "No data provided"}

    try:
        # Calculate mid price if not provided
        if mid_column is None:
            data = data.with_columns(
                ((pl.col(bid_column) + pl.col(ask_column)) / 2).alias("mid_price")
            )
            mid_column = "mid_price"

        # Calculate spread metrics
        analysis_data = (
            data.with_columns(
                [
                    (pl.col(ask_column) - pl.col(bid_column)).alias("spread"),
                    (
                        (pl.col(ask_column) - pl.col(bid_column)) / pl.col(mid_column)
                    ).alias("relative_spread"),
                ]
            )
            .select(["spread", "relative_spread"])
            .drop_nulls()
        )

        if analysis_data.is_empty():
            return {"error": "No valid spread data"}

        return {
            "avg_spread": analysis_data.select(pl.col("spread").mean()).item() or 0.0,
            "median_spread": analysis_data.select(pl.col("spread").median()).item()
            or 0.0,
            "min_spread": analysis_data.select(pl.col("spread").min()).item() or 0.0,
            "max_spread": analysis_data.select(pl.col("spread").max()).item() or 0.0,
            "avg_relative_spread": analysis_data.select(
                pl.col("relative_spread").mean()
            ).item()
            or 0.0,
            "spread_volatility": analysis_data.select(pl.col("spread").std()).item()
            or 0.0,
        }

    except Exception as e:
        return {"error": str(e)}


def calculate_volume_profile(
    data: pl.DataFrame,
    price_column: str = "close",
    volume_column: str = "volume",
    num_bins: int = 50,
) -> dict[str, Any]:
    """
    Calculate volume profile analysis.

    Args:
        data: DataFrame with price and volume data
        price_column: Price column
        volume_column: Volume column
        num_bins: Number of price bins

    Returns:
        Dict with volume profile analysis

    Example:
        >>> profile = calculate_volume_profile(ohlcv_data)
        >>> print(f"Point of Control: ${profile['poc_price']:.2f}")
    """
    required_cols = [price_column, volume_column]
    for col in required_cols:
        if col not in data.columns:
            raise ValueError(f"Column '{col}' not found in data")

    if data.is_empty():
        return {"error": "No data provided"}

    try:
        min_price = data.select(pl.col(price_column).min()).item()
        max_price = data.select(pl.col(price_column).max()).item()
        breaks = [
            min_price + i * ((max_price - min_price) / num_bins)
            for i in range(num_bins + 1)
        ]

        binned = data.with_columns(pl.col(price_column).cut(breaks=breaks).alias("bin"))

        profile = (
            binned.group_by("bin")
            .agg(
                pl.col(volume_column).sum().alias("total_volume"),
                pl.col(price_column).mean().alias("avg_price"),
                pl.col(volume_column).count().alias("trade_count"),
                pl.col(volume_column)
                .filter(pl.col("side") == "buy")
                .sum()
                .alias("buy_volume"),
                pl.col(volume_column)
                .filter(pl.col("side") == "sell")
                .sum()
                .alias("sell_volume"),
            )
            .sort("bin")
        )

        # Find Point of Control (POC) - price level with highest volume
        poc_price = profile.select(pl.col("avg_price")).item()
        poc_volume = profile.select(pl.col("total_volume")).item()

        # Calculate Value Area (70% of volume)
        total_volume = profile.select(pl.col("total_volume")).sum().item()
        target_volume = total_volume * 0.7

        # Sort by volume to find value area
        sorted_levels = profile.sort("total_volume", descending=True).to_dicts()

        value_area_volume = 0
        value_area_high = poc_price
        value_area_low = poc_price

        for level in sorted_levels:
            value_area_volume += level["total_volume"]
            value_area_high = max(value_area_high, level["avg_price"])
            value_area_low = min(value_area_low, level["avg_price"])

            if value_area_volume >= target_volume:
                break

        return {
            "poc_price": poc_price,
            "poc_volume": poc_volume,
            "value_area_high": value_area_high,
            "value_area_low": value_area_low,
            "value_area_volume": value_area_volume,
            "total_volume": total_volume,
            "num_price_levels": len(profile),
            "volume_profile": profile.to_dicts(),
        }

    except Exception as e:
        return {"error": str(e)}
