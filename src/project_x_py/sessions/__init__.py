"""
Trading Sessions Module for ETH/RTH functionality.

This module provides session-based market data filtering and analysis
capabilities for Electronic Trading Hours (ETH) and Regular Trading Hours (RTH).

Author: TDD Implementation
Date: 2025-08-28
"""

from .config import (
    DEFAULT_SESSIONS,
    SessionConfig,
    SessionTimes,
    SessionType,
    resolve_session_product,
)
from .filtering import SessionFilterMixin
from .indicators import (
    aggregate_with_sessions,
    calculate_anchored_vwap,
    calculate_percent_from_open,
    calculate_relative_to_vwap,
    calculate_session_cumulative_volume,
    calculate_session_levels,
    calculate_session_vwap,
    generate_session_alerts,
)
from .statistics import SessionAnalytics, SessionStatistics

__all__ = [
    # Configuration
    "SessionConfig",
    "SessionTimes",
    "SessionType",
    "DEFAULT_SESSIONS",
    "resolve_session_product",
    # Filtering
    "SessionFilterMixin",
    # Statistics
    "SessionStatistics",
    "SessionAnalytics",
    # Indicators
    "calculate_session_vwap",
    "calculate_anchored_vwap",
    "calculate_session_levels",
    "calculate_session_cumulative_volume",
    "calculate_relative_to_vwap",
    "calculate_percent_from_open",
    "aggregate_with_sessions",
    "generate_session_alerts",
]
