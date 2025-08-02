"""
ProjectX Python SDK for Trading Applications

A comprehensive Python SDK for the ProjectX Trading Platform Gateway API, providing developers
with tools to build sophisticated trading strategies and applications. This library offers
comprehensive access to:

- Market data retrieval and real-time streaming
- Account management and authentication
- Order placement, modification, and cancellation
- Position management and portfolio analytics
- Trade history and execution analysis
- Advanced technical indicators and market analysis
- Level 2 orderbook depth and market microstructure

**Important**: This is a development toolkit/SDK, not a trading strategy itself.
It provides the infrastructure to help developers create their own trading applications
that integrate with the ProjectX platform.

Author: TexasCoding
Date: January 2025
"""

from typing import Any

__version__ = "2.0.2"
__author__ = "TexasCoding"

# Core client classes - renamed from Async* to standard names
from .client import ProjectX

# Configuration management
from .config import (
    ConfigManager,
    create_custom_config,
    load_default_config,
    load_topstepx_config,
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
from .orderbook import (
    OrderBook,
    create_orderbook,
)
from .position_manager import PositionManager
from .realtime import ProjectXRealtimeClient as ProjectXRealtimeClient
from .realtime_data_manager import RealtimeDataManager

# --- Legacy async names for backwards compatibility ---
AsyncProjectX = ProjectX
AsyncOrderManager = OrderManager
AsyncPositionManager = PositionManager
AsyncProjectXRealtimeClient = ProjectXRealtimeClient
create_async_trading_suite = create_trading_suite

# Utility functions
from .utils import (
    RateLimiter,
    # Market analysis utilities
    analyze_bid_ask_spread,
    # Risk and portfolio analysis
    calculate_max_drawdown,
    calculate_portfolio_metrics,
    calculate_sharpe_ratio,
    # Utilities
    get_env_var,
    round_to_tick_size,
    setup_logging,
)

__all__ = [
    # Data Models
    "Account",
    "BracketOrderResponse",
    # Configuration
    "ConfigManager",
    "Instrument",
    "Order",
    # Core classes (now async-only but with original names)
    "OrderBook",
    "OrderManager",
    "OrderPlaceResponse",
    "Position",
    "PositionManager",
    "ProjectX",
    # Exceptions
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
    "ProjectXServerError",
    # Utilities
    "RateLimiter",
    "RealtimeDataManager",
    "Trade",
    # Version info
    "__author__",
    "__version__",
    "analyze_bid_ask_spread",
    # Technical Analysis
    "calculate_adx",
    "calculate_atr",
    "calculate_bollinger_bands",
    "calculate_commodity_channel_index",
    "calculate_ema",
    "calculate_macd",
    "calculate_max_drawdown",
    "calculate_obv",
    "calculate_portfolio_metrics",
    "calculate_rsi",
    "calculate_sharpe_ratio",
    "calculate_sma",
    "calculate_stochastic",
    "calculate_vwap",
    "calculate_williams_r",
    "create_custom_config",
    # Factory functions (async-only)
    "create_data_manager",
    "create_order_manager",
    "create_orderbook",
    "create_position_manager",
    "create_realtime_client",
    "create_trading_suite",
    "get_env_var",
    "load_default_config",
    "load_topstepx_config",
    "round_to_tick_size",
    "setup_logging",
    # --- Legacy async names expected by tests ---
    "AsyncProjectX",
    "AsyncOrderManager",
    "AsyncPositionManager",
    "AsyncProjectXRealtimeClient",
    "create_async_trading_suite",
]


# Factory functions - Updated to be async-only
async def create_trading_suite(
    instrument: str,
    project_x: ProjectX,
    jwt_token: str | None = None,
    account_id: str | None = None,
    timeframes: list[str] | None = None,
    enable_orderbook: bool = True,
    config: ProjectXConfig | None = None,
) -> dict[str, Any]:
    """
    Create a complete async trading suite with all components initialized.

    This is the recommended way to set up a trading environment as it ensures
    all components are properly configured and connected.

    Args:
        instrument: Trading instrument symbol (e.g., "MGC", "MNQ")
        project_x: Authenticated ProjectX client instance
        jwt_token: JWT token for real-time connections (optional, will get from client)
        account_id: Account ID for trading (optional, will get from client)
        timeframes: List of timeframes for real-time data (default: ["5min"])
        enable_orderbook: Whether to include OrderBook in suite
        config: Optional custom configuration

    Returns:
        Dictionary containing initialized trading components:
        - realtime_client: Real-time WebSocket client
        - data_manager: Real-time data manager
        - order_manager: Order management system
        - position_manager: Position tracking system
        - orderbook: Level 2 order book (if enabled)

    Example:
        async with ProjectX.from_env() as client:
            await client.authenticate()

            suite = await create_trading_suite(
                instrument="MGC",
                project_x=client,
                timeframes=["1min", "5min", "15min"]
            )

            # Connect real-time services
            await suite["realtime_client"].connect()
            await suite["data_manager"].initialize()
    """
    # Use provided config or get from project_x client
    if config is None:
        config = project_x.config

    # Get JWT token if not provided
    if jwt_token is None:
        jwt_token = project_x.session_token
        if not jwt_token:
            raise ValueError("JWT token is required but not available from client")

    # Get account ID if not provided
    if account_id is None and project_x.account_info:
        account_id = str(project_x.account_info.id)

    if not account_id:
        raise ValueError("Account ID is required but not available")

    # Default timeframes
    if timeframes is None:
        timeframes = ["5min"]

    # Create real-time client
    realtime_client = ProjectXRealtimeClient(
        jwt_token=jwt_token,
        account_id=account_id,
        config=config,
    )

    # Create data manager
    data_manager = RealtimeDataManager(
        instrument=instrument,
        project_x=project_x,
        realtime_client=realtime_client,
        timeframes=timeframes,
    )

    # Create orderbook if enabled
    orderbook = None
    if enable_orderbook:
        orderbook = OrderBook(
            instrument=instrument,
            timezone_str=config.timezone,
            project_x=project_x,
        )

    # Create order manager
    order_manager = OrderManager(project_x)

    # Create position manager
    position_manager = PositionManager(project_x)

    # Build suite dictionary
    suite = {
        "realtime_client": realtime_client,
        "data_manager": data_manager,
        "order_manager": order_manager,
        "position_manager": position_manager,
    }

    if orderbook:
        suite["orderbook"] = orderbook

    return suite


def create_order_manager(
    project_x: ProjectX,
    realtime_client: ProjectXRealtimeClient | None = None,
) -> OrderManager:
    """
    Create an async order manager instance.

    Args:
        project_x: Authenticated ProjectX client
        realtime_client: Optional real-time client for order updates

    Returns:
        Configured OrderManager instance

    Example:
        order_manager = create_order_manager(project_x, realtime_client)
        response = await order_manager.place_market_order(
            contract_id=instrument.id,
            side=0,  # Buy
            size=1
        )
    """
    order_manager = OrderManager(project_x)
    if realtime_client:
        # This would need to be done in an async context
        # For now, just store the client
        order_manager.realtime_client = realtime_client
    return order_manager


def create_position_manager(
    project_x: ProjectX,
    realtime_client: ProjectXRealtimeClient | None = None,
    order_manager: OrderManager | None = None,
) -> PositionManager:
    """
    Create an async position manager instance.

    Args:
        project_x: Authenticated ProjectX client
        realtime_client: Optional real-time client for position updates
        order_manager: Optional order manager for integrated order cleanup

    Returns:
        Configured PositionManager instance

    Example:
        position_manager = create_position_manager(
            project_x,
            realtime_client,
            order_manager
        )
        positions = await position_manager.get_all_positions()
    """
    position_manager = PositionManager(project_x)
    if realtime_client:
        # This would need to be done in an async context
        # For now, just store the client
        position_manager.realtime_client = realtime_client
    if order_manager:
        position_manager.order_manager = order_manager
    return position_manager


def create_realtime_client(
    jwt_token: str,
    account_id: str,
    config: ProjectXConfig | None = None,
) -> ProjectXRealtimeClient:
    """
    Create a real-time WebSocket client instance.

    Args:
        jwt_token: JWT authentication token
        account_id: Account ID for real-time subscriptions
        config: Optional configuration (uses defaults if not provided)

    Returns:
        Configured ProjectXRealtimeClient instance

    Example:
        realtime_client = create_realtime_client(
            jwt_token=client.session_token,
            account_id=str(client.account_info.id)
        )
        await realtime_client.connect()
        await realtime_client.subscribe_user_updates()
    """
    return ProjectXRealtimeClient(
        jwt_token=jwt_token,
        account_id=account_id,
        config=config,
    )


def create_data_manager(
    instrument: str,
    project_x: ProjectX,
    realtime_client: ProjectXRealtimeClient,
    timeframes: list[str] | None = None,
) -> RealtimeDataManager:
    """
    Create a real-time data manager instance.

    Args:
        instrument: Trading instrument symbol (e.g., "MGC", "MNQ")
        project_x: Authenticated ProjectX client
        realtime_client: Real-time client for WebSocket data
        timeframes: List of timeframes to track (default: ["5min"])

    Returns:
        Configured RealtimeDataManager instance

    Example:
        data_manager = create_data_manager(
            instrument="MGC",
            project_x=client,
            realtime_client=realtime_client,
            timeframes=["1min", "5min", "15min"]
        )
        await data_manager.initialize()
        await data_manager.start_realtime_feed()
    """
    if timeframes is None:
        timeframes = ["5min"]

    return RealtimeDataManager(
        instrument=instrument,
        project_x=project_x,
        realtime_client=realtime_client,
        timeframes=timeframes,
    )
