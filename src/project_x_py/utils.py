"""
ProjectX Utility Functions

This module contains utility functions used throughout the ProjectX client.
"""

import os
import logging
from typing import Any, Dict, Optional
import polars as pl


def get_polars_rows(df: pl.DataFrame) -> int:
    """Get number of rows from polars DataFrame safely."""
    return getattr(df, "n_rows", 0)


def get_polars_last_value(df: pl.DataFrame, column: str) -> float:
    """Get last value from a polars DataFrame column safely."""
    try:
        return float(df.select(pl.col(column)).tail(1).item())
    except Exception:
        return 0.0


def setup_logging(
    level: str = "INFO",
    format_string: Optional[str] = None,
    filename: Optional[str] = None,
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


def get_env_var(
    name: str, default: Optional[str] = None, required: bool = False
) -> Optional[str]:
    """
    Get environment variable with optional default and validation.

    Args:
        name: Environment variable name
        default: Default value if not found
        required: Whether the variable is required

    Returns:
        Environment variable value or default

    Raises:
        ValueError: If required variable is not found
    """
    value = os.environ.get(name, default)

    if required and value is None:
        raise ValueError(f"Required environment variable '{name}' not found")

    return value


def validate_contract_id(contract_id: str) -> bool:
    """
    Validate contract ID format.

    Args:
        contract_id: Contract ID to validate

    Returns:
        True if valid format
    """
    if not isinstance(contract_id, str) or not contract_id:
        return False

    # Basic validation - adjust based on TopStepX format requirements
    return "." in contract_id and len(contract_id) > 5


def extract_symbol_from_contract_id(contract_id: str) -> Optional[str]:
    """
    Extract trading symbol from contract ID.

    Args:
        contract_id: Contract ID like "CON.F.US.MGC.M25"

    Returns:
        Symbol like "MGC" or None if extraction fails
    """
    try:
        if "." in contract_id:
            parts = contract_id.split(".")
            if len(parts) >= 4:
                return parts[3]  # MGC from CON.F.US.MGC.M25
        return None
    except Exception:
        return None


def format_price(price: float, decimals: int = 2) -> str:
    """
    Format price for display.

    Args:
        price: Price value
        decimals: Number of decimal places

    Returns:
        Formatted price string
    """
    return f"${price:,.{decimals}f}"


def format_volume(volume: int) -> str:
    """
    Format volume for display.

    Args:
        volume: Volume value

    Returns:
        Formatted volume string
    """
    if volume >= 1_000_000:
        return f"{volume / 1_000_000:.1f}M"
    elif volume >= 1_000:
        return f"{volume / 1_000:.1f}K"
    else:
        return str(volume)


def safe_float(value: Any, default: float = 0.0) -> float:
    """
    Safely convert value to float.

    Args:
        value: Value to convert
        default: Default value if conversion fails

    Returns:
        Float value or default
    """
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    """
    Safely convert value to int.

    Args:
        value: Value to convert
        default: Default value if conversion fails

    Returns:
        Integer value or default
    """
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def merge_dicts(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge two dictionaries, with dict2 values taking precedence.

    Args:
        dict1: First dictionary
        dict2: Second dictionary (takes precedence)

    Returns:
        Merged dictionary
    """
    result = dict1.copy()
    result.update(dict2)
    return result


def calculate_percentage_change(old_value: float, new_value: float) -> float:
    """
    Calculate percentage change between two values.

    Args:
        old_value: Original value
        new_value: New value

    Returns:
        Percentage change
    """
    if old_value == 0:
        return 0.0
    return ((new_value - old_value) / old_value) * 100


def is_market_hours(timezone_str: str = "America/Chicago") -> bool:
    """
    Check if current time is within market hours.

    Args:
        timezone_str: Timezone string

    Returns:
        True if within market hours
    """
    try:
        import pytz
        from datetime import datetime

        tz = pytz.timezone(timezone_str)
        now = datetime.now(tz)

        # Basic market hours check (adjust as needed)
        # CME futures typically trade almost 24/5
        weekday = now.weekday()  # 0=Monday, 6=Sunday

        # Skip weekends (Saturday=5, Sunday=6)
        if weekday == 5:  # Saturday
            return False
        elif weekday == 6:  # Sunday
            # Sunday evening trading starts
            return now.hour >= 17
        else:  # Monday-Friday
            # Trading halt typically 16:00-17:00 CT
            return not (16 <= now.hour < 17)

    except Exception:
        # Default to True if we can't determine
        return True


class RateLimiter:
    """Simple rate limiter for API calls."""

    def __init__(self, max_calls: int, time_window: int = 60):
        """
        Initialize rate limiter.

        Args:
            max_calls: Maximum calls allowed
            time_window: Time window in seconds
        """
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls = []

    def can_proceed(self) -> bool:
        """Check if we can make another call."""
        import time

        now = time.time()

        # Remove old calls outside the time window
        self.calls = [
            call_time for call_time in self.calls if now - call_time < self.time_window
        ]

        return len(self.calls) < self.max_calls

    def record_call(self):
        """Record a new API call."""
        import time

        self.calls.append(time.time())

    def wait_time(self) -> float:
        """Get time to wait before next call is allowed."""
        if self.can_proceed():
            return 0.0

        import time

        now = time.time()

        if self.calls:
            oldest_call = min(self.calls)
            return max(0, self.time_window - (now - oldest_call))

        return 0.0
