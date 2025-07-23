"""
ProjectX API Client for TopStepX Futures Trading

A comprehensive Python client for the ProjectX Gateway API, providing access to:
- Market data retrieval
- Account management
- Order placement, modification, and cancellation
- Position management
- Trade history and analysis
- Real-time data streams

Author: TexasCoding
Date: June 2025
"""

from typing import Any, Optional

__version__ = "1.0.9"
__author__ = "TexasCoding"

# Core client classes
from .client import ProjectX

# Configuration management
from .config import (
    ConfigManager,
    check_environment,
    create_config_template,
    load_default_config,
)

# Exceptions
from .exceptions import (
    ProjectXAuthenticationError,
    ProjectXConnectionError,
    ProjectXDataError,
    ProjectXError,
    ProjectXInstrumentError,
    ProjectXOrderError,
    ProjectXPositionError,
    ProjectXRateLimitError,
    ProjectXServerError,
)

# Technical Analysis - Import from indicators module for backward compatibility
from .indicators import (
    calculate_adx,
    calculate_atr,
    calculate_bollinger_bands,
    calculate_commodity_channel_index,
    calculate_ema,
    calculate_macd,
    calculate_obv,
    calculate_rsi,
    # TA-Lib style functions
    calculate_sma,
    calculate_stochastic,
    calculate_vwap,
    calculate_williams_r,
)

# Data models
from .models import (
    Account,
    BracketOrderResponse,
    # Trading entities
    Instrument,
    Order,
    OrderPlaceResponse,
    Position,
    # Configuration
    ProjectXConfig,
    Trade,
)
from .order_manager import OrderManager
from .orderbook import OrderBook
from .position_manager import PositionManager
from .realtime import ProjectXRealtimeClient
from .realtime_data_manager import ProjectXRealtimeDataManager

# Utility functions
from .utils import (
    RateLimiter,
    # Market analysis utilities
    analyze_bid_ask_spread,
    # Risk and portfolio analysis
    calculate_correlation_matrix,
    calculate_max_drawdown,
    calculate_portfolio_metrics,
    calculate_position_sizing,
    calculate_position_value,
    calculate_risk_reward_ratio,
    calculate_sharpe_ratio,
    calculate_tick_value,
    calculate_volatility_metrics,
    calculate_volume_profile,
    convert_timeframe_to_seconds,
    create_data_snapshot,
    detect_candlestick_patterns,
    detect_chart_patterns,
    extract_symbol_from_contract_id,
    format_price,
    format_volume,
    get_env_var,
    get_market_session_info,
    get_polars_last_value as _get_polars_last_value,
    get_polars_rows as _get_polars_rows,
    is_market_hours,
    round_to_tick_size,
    setup_logging,
    validate_contract_id,
)

# Public API - these are the main classes users should import
__all__ = [
    "Account",
    "BracketOrderResponse",
    "ConfigManager",
    "Instrument",
    "Order",
    "OrderBook",
    "OrderManager",
    "OrderPlaceResponse",
    "Position",
    "PositionManager",
    "ProjectX",
    "ProjectXAuthenticationError",
    "ProjectXConfig",
    "ProjectXConnectionError",
    "ProjectXDataError",
    "ProjectXError",
    "ProjectXInstrumentError",
    "ProjectXOrderError",
    "ProjectXPositionError",
    "ProjectXRateLimitError",
    "ProjectXRealtimeClient",
    "ProjectXRealtimeDataManager",
    "ProjectXServerError",
    "RateLimiter",
    "Trade",
    # Enhanced technical analysis and trading utilities
    "analyze_bid_ask_spread",
    "calculate_adx",
    "calculate_atr",
    "calculate_bollinger_bands",
    "calculate_commodity_channel_index",
    "calculate_correlation_matrix",
    "calculate_ema",
    "calculate_macd",
    "calculate_max_drawdown",
    "calculate_portfolio_metrics",
    "calculate_position_sizing",
    "calculate_position_value",
    "calculate_risk_reward_ratio",
    "calculate_rsi",
    "calculate_sharpe_ratio",
    "calculate_sma",
    "calculate_stochastic",
    "calculate_tick_value",
    "calculate_volatility_metrics",
    "calculate_volume_profile",
    "calculate_williams_r",
    "check_environment",
    "convert_timeframe_to_seconds",
    "create_config_template",
    "create_data_manager",
    "create_data_snapshot",
    "create_order_manager",
    "create_orderbook",
    "create_position_manager",
    "create_realtime_client",
    "create_trading_suite",
    "detect_candlestick_patterns",
    "detect_chart_patterns",
    "extract_symbol_from_contract_id",
    "format_price",
    "format_volume",
    "get_env_var",
    "get_market_session_info",
    "is_market_hours",
    "load_default_config",
    "round_to_tick_size",
    "setup_logging",
    "validate_contract_id",
]


def get_version() -> str:
    """Get the current version of the ProjectX package."""
    return __version__


def quick_start() -> dict:
    """
    Get quick start information for the ProjectX package.

    Returns:
        Dict with setup instructions and examples
    """
    return {
        "version": __version__,
        "setup_instructions": [
            "1. Set environment variables:",
            "   export PROJECT_X_API_KEY='your_api_key'",
            "   export PROJECT_X_USERNAME='your_username'",
            "",
            "2. Basic usage:",
            "   from project_x_py import ProjectX",
            "   client = ProjectX.from_env()",
            "   instruments = client.search_instruments('MGC')",
            "   data = client.get_data('MGC', days=5)",
        ],
        "examples": {
            "basic_client": "client = ProjectX.from_env()",
            "get_instruments": "instruments = client.search_instruments('MGC')",
            "get_data": "data = client.get_data('MGC', days=5, interval=15)",
            "place_order": "response = client.place_market_order('CONTRACT_ID', 0, 1)",
            "get_positions": "positions = client.search_open_positions()",
        },
        "documentation": "https://github.com/your-repo/project-x-py",
        "support": "Create an issue at https://github.com/your-repo/project-x-py/issues",
    }


def check_setup() -> dict:
    """
    Check if the ProjectX package is properly set up.

    Returns:
        Dict with setup status and recommendations
    """
    try:
        from .config import check_environment

        env_status = check_environment()

        status = {
            "environment_configured": env_status["auth_configured"],
            "config_file_exists": env_status["config_file_exists"],
            "issues": [],
            "recommendations": [],
        }

        if not env_status["auth_configured"]:
            status["issues"].append("Missing required environment variables")
            status["recommendations"].extend(
                [
                    "Set PROJECT_X_API_KEY environment variable",
                    "Set PROJECT_X_USERNAME environment variable",
                ]
            )

        if env_status["missing_required"]:
            status["missing_variables"] = env_status["missing_required"]

        if env_status["environment_overrides"]:
            status["environment_overrides"] = env_status["environment_overrides"]

        if not status["issues"]:
            status["status"] = "Ready to use"
        else:
            status["status"] = "Setup required"

        return status

    except Exception as e:
        return {
            "status": "Error checking setup",
            "error": str(e),
            "recommendations": [
                "Ensure all dependencies are installed",
                "Check package installation",
            ],
        }


def diagnose_issues() -> dict:
    """
    Diagnose common setup issues and provide recommendations.

    Returns:
        Dict with diagnostics and fixes
    """
    diagnostics = check_setup()
    diagnostics["issues"] = []
    diagnostics["recommendations"] = []

    # Check dependencies
    try:
        import polars
        import pytz
        import requests
    except ImportError as e:
        diagnostics["issues"].append(f"Missing dependency: {e.name}")
        diagnostics["recommendations"].append(f"Install with: pip install {e.name}")

    # Check network connectivity
    try:
        requests.get("https://www.google.com", timeout=5)
    except requests.RequestException:
        diagnostics["issues"].append("Network connectivity issue")
        diagnostics["recommendations"].append("Check internet connection")

    # Check config validity
    try:
        config = load_default_config()
        ConfigManager().validate_config(config)
    except ValueError as e:
        diagnostics["issues"].append(f"Invalid configuration: {e!s}")
        diagnostics["recommendations"].append("Fix config file or env vars")

    if not diagnostics["issues"]:
        diagnostics["status"] = "All systems operational"
    else:
        diagnostics["status"] = "Issues detected"

    return diagnostics


# Package-level convenience functions
def create_client(
    username: str | None = None,
    api_key: str | None = None,
    config: ProjectXConfig | None = None,
    account_name: str | None = None,
) -> ProjectX:
    """
    Create a ProjectX client with flexible initialization.

    Args:
        username: Username (uses env var if None)
        api_key: API key (uses env var if None)
        config: Configuration object (uses defaults if None)
        account_name: Optional account name to select specific account

    Returns:
        ProjectX client instance

    Example:
        >>> # Using environment variables
        >>> client = create_client()
        >>> # Using explicit credentials
        >>> client = create_client("username", "api_key")
        >>> # Using specific account
        >>> client = create_client(account_name="Main Trading Account")
    """
    if username is None or api_key is None:
        return ProjectX.from_env(config=config, account_name=account_name)
    else:
        return ProjectX(
            username=username, api_key=api_key, config=config, account_name=account_name
        )


def create_realtime_client(
    jwt_token: str, account_id: str, config: ProjectXConfig | None = None
) -> ProjectXRealtimeClient:
    """
    Create a ProjectX real-time client.

    Args:
        jwt_token: JWT authentication token
        account_id: Account ID for subscriptions
        config: Configuration object (uses defaults if None)

    Returns:
        ProjectXRealtimeClient instance
    """
    if config is None:
        config = load_default_config()

    return ProjectXRealtimeClient(
        jwt_token=jwt_token,
        account_id=account_id,
        user_hub_url=config.user_hub_url,
        market_hub_url=config.market_hub_url,
    )


def create_data_manager(
    instrument: str,
    project_x: ProjectX,
    realtime_client: ProjectXRealtimeClient,
    timeframes: list[str] | None = None,
    config: ProjectXConfig | None = None,
) -> ProjectXRealtimeDataManager:
    """
    Create a ProjectX real-time OHLCV data manager with dependency injection.

    Args:
        instrument: Trading instrument symbol
        project_x: ProjectX client instance
        realtime_client: ProjectXRealtimeClient instance for real-time data
        timeframes: List of timeframes to track (default: ["5min"])
        config: Configuration object (uses defaults if None)

    Returns:
        ProjectXRealtimeDataManager instance
    """
    if timeframes is None:
        timeframes = ["5min"]

    if config is None:
        config = load_default_config()

    return ProjectXRealtimeDataManager(
        instrument=instrument,
        project_x=project_x,
        realtime_client=realtime_client,
        timeframes=timeframes,
        timezone=config.timezone,
    )


def create_orderbook(
    instrument: str,
    config: ProjectXConfig | None = None,
) -> "OrderBook":
    """
    Create a ProjectX OrderBook for advanced market depth analysis.

    Args:
        instrument: Trading instrument symbol
        config: Configuration object (uses defaults if None)

    Returns:
        OrderBook instance
    """
    if config is None:
        config = load_default_config()

    return OrderBook(
        instrument=instrument,
        timezone=config.timezone,
    )


def create_order_manager(
    project_x: ProjectX,
    realtime_client: ProjectXRealtimeClient | None = None,
) -> OrderManager:
    """
    Create a ProjectX OrderManager for comprehensive order operations.

    Args:
        project_x: ProjectX client instance
        realtime_client: Optional ProjectXRealtimeClient for real-time order tracking

    Returns:
        OrderManager instance

    Example:
        >>> order_manager = create_order_manager(project_x, realtime_client)
        >>> order_manager.initialize()
        >>> # Place orders
        >>> response = order_manager.place_market_order("MGC", 0, 1)
        >>> bracket = order_manager.place_bracket_order(
        ...     "MGC", 0, 1, 2045.0, 2040.0, 2055.0
        ... )
        >>> # Manage orders
        >>> orders = order_manager.search_open_orders()
        >>> order_manager.cancel_order(order_id)
    """
    order_manager = OrderManager(project_x)
    order_manager.initialize(realtime_client=realtime_client)
    return order_manager


def create_position_manager(
    project_x: ProjectX,
    realtime_client: ProjectXRealtimeClient | None = None,
) -> PositionManager:
    """
    Create a ProjectX PositionManager for comprehensive position operations.

    Args:
        project_x: ProjectX client instance
        realtime_client: Optional ProjectXRealtimeClient for real-time position tracking

    Returns:
        PositionManager instance

    Example:
        >>> position_manager = create_position_manager(project_x, realtime_client)
        >>> position_manager.initialize()
        >>> # Get positions
        >>> positions = position_manager.get_all_positions()
        >>> mgc_position = position_manager.get_position("MGC")
        >>> # Portfolio analytics
        >>> pnl = position_manager.get_portfolio_pnl()
        >>> risk = position_manager.get_risk_metrics()
        >>> # Position monitoring
        >>> position_manager.add_position_alert("MGC", max_loss=-500.0)
        >>> position_manager.start_monitoring()
    """
    position_manager = PositionManager(project_x)
    position_manager.initialize(realtime_client=realtime_client)
    return position_manager


def create_trading_suite(
    instrument: str,
    project_x: ProjectX,
    jwt_token: str,
    account_id: str,
    timeframes: list[str] | None = None,
    config: ProjectXConfig | None = None,
) -> dict[str, Any]:
    """
    Create a complete trading suite with optimized architecture.

    This factory function sets up:
    - Single ProjectXRealtimeClient for WebSocket connection
    - ProjectXRealtimeDataManager for OHLCV data
    - OrderBook for market depth analysis
    - OrderManager for comprehensive order operations
    - PositionManager for position tracking and risk management
    - Proper dependency injection and connection sharing

    Args:
        instrument: Trading instrument symbol
        project_x: ProjectX client instance
        jwt_token: JWT token for WebSocket authentication
        account_id: Account ID for real-time subscriptions
        timeframes: List of timeframes to track (default: ["5min"])
        config: Configuration object (uses defaults if None)

    Returns:
        dict: {"realtime_client": client, "data_manager": manager, "orderbook": orderbook, "order_manager": order_manager, "position_manager": position_manager}

    Example:
        >>> suite = create_trading_suite(
        ...     "MGC", project_x, jwt_token, account_id, ["5sec", "1min", "5min"]
        ... )
        >>> # Connect once
        >>> suite["realtime_client"].connect()
        >>> # Initialize components
        >>> suite["data_manager"].initialize(initial_days=30)
        >>> suite["data_manager"].start_realtime_feed()
        >>> # Place orders
        >>> bracket = suite["order_manager"].place_bracket_order(
        ...     "MGC", 0, 1, 2045.0, 2040.0, 2055.0
        ... )
        >>> # Monitor positions
        >>> suite["position_manager"].add_position_alert("MGC", max_loss=-500.0)
        >>> suite["position_manager"].start_monitoring()
        >>> # Access data
        >>> ohlcv_data = suite["data_manager"].get_data("5min")
        >>> orderbook_snapshot = suite["orderbook"].get_orderbook_snapshot()
        >>> portfolio_pnl = suite["position_manager"].get_portfolio_pnl()
    """
    if timeframes is None:
        timeframes = ["5min"]

    if config is None:
        config = load_default_config()

    # Create single realtime client (shared connection)
    realtime_client = ProjectXRealtimeClient(
        jwt_token=jwt_token,
        account_id=account_id,
        user_hub_url=config.user_hub_url,
        market_hub_url=config.market_hub_url,
    )

    # Create OHLCV data manager with dependency injection
    data_manager = ProjectXRealtimeDataManager(
        instrument=instrument,
        project_x=project_x,
        realtime_client=realtime_client,
        timeframes=timeframes,
        timezone=config.timezone,
    )

    # Create separate orderbook for market depth analysis
    orderbook = OrderBook(
        instrument=instrument,
        timezone=config.timezone,
    )

    # Create order manager for comprehensive order operations
    order_manager = OrderManager(project_x)
    order_manager.initialize(realtime_client=realtime_client)

    # Create position manager for position tracking and risk management
    position_manager = PositionManager(project_x)
    position_manager.initialize(realtime_client=realtime_client)

    return {
        "realtime_client": realtime_client,
        "data_manager": data_manager,
        "orderbook": orderbook,
        "order_manager": order_manager,
        "position_manager": position_manager,
        "config": config,
    }
