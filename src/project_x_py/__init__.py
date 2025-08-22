"""
ProjectX Python SDK for Trading Applications

Author: @TexasCoding
Date: 2025-08-02

Overview:
    A comprehensive Python SDK for the ProjectX Trading Platform Gateway API, providing
    developers with tools to build sophisticated trading strategies and applications.
    This library offers comprehensive access to real-time market data, order management,
    position tracking, and advanced analytics for algorithmic trading.

Key Features:
    - Real-time market data streaming and historical data access
    - Comprehensive order management (market, limit, stop, bracket orders)
    - Position tracking and portfolio analytics
    - Level 2 orderbook depth and market microstructure analysis
    - Advanced technical indicators and pattern recognition
    - Risk management and position sizing tools
    - Multi-timeframe data management and analysis
    - WebSocket-based real-time updates and event handling
    - Comprehensive statistics and analytics system with health monitoring
    - Fine-grained locking and async-first performance optimization

Core Components:
    - TradingSuite: All-in-one trading environment with automatic initialization
    - ProjectX: Main client for API interactions and authentication
    - OrderManager: Order placement, modification, and tracking
    - PositionManager: Position monitoring, analytics, and risk management
    - OrderBook: Level 2 market depth analysis and order flow
    - RealtimeDataManager: Multi-timeframe real-time data processing
    - ProjectXRealtimeClient: WebSocket-based real-time connections
    - Statistics Module: Comprehensive async statistics system with health monitoring

Trading Capabilities:
    - Market data retrieval and real-time streaming
    - Account management and authentication
    - Order placement, modification, and cancellation
    - Position management and portfolio analytics
    - Trade history and execution analysis
    - Advanced technical indicators and market analysis
    - Level 2 orderbook depth and market microstructure
    - Risk management and position sizing
    - Real-time statistics tracking and performance monitoring
    - Health scoring and system analytics with multi-format export

Example Usage:
    ```python
    from project_x_py import TradingSuite

    # Simple one-line setup with TradingSuite v3
    suite = await TradingSuite.create("MGC", timeframes=["1min", "5min", "15min"])

    # Everything is ready to use:
    bars = await suite.client.get_bars("MGC", days=5)

    # Place orders
    response = await suite.orders.place_market_order(
        contract_id=suite.instrument_info.id,
        side=0,  # Buy
        size=1,
    )

    # Track positions
    positions = await suite.positions.get_all_positions()

    # Access real-time data
    current_price = await suite.data.get_current_price()

    # Get comprehensive statistics (v3.3.0+)
    stats = await suite.get_stats()
    print(f"System Health: {stats['health_score']}/100")
    print(f"API Success Rate: {stats['api_success_rate']:.1%}")

    # Export statistics to multiple formats
    prometheus_metrics = await suite.export_stats("prometheus")
    csv_data = await suite.export_stats("csv")

    # Clean shutdown
    await suite.disconnect()
    ```

Architecture Benefits:
    - Async-first design for high-performance trading applications
    - Comprehensive error handling and retry logic
    - Rate limiting and connection management
    - Real-time data processing with WebSocket integration
    - Modular design for flexible trading system development
    - Type-safe operations with comprehensive validation

**Important**: This is a development toolkit/SDK, not a trading strategy itself.
It provides the infrastructure to help developers create their own trading applications
that integrate with the ProjectX platform.

Version: 3.3.0
Author: TexasCoding

See Also:
    - `client`: Main client for API interactions
    - `order_manager`: Order management and tracking
    - `position_manager`: Position monitoring and analytics
    - `orderbook`: Level 2 market depth analysis
    - `realtime_data_manager`: Real-time data processing
    - `indicators`: Technical analysis and indicators
    - `utils`: Utility functions and calculations
"""

__version__ = "3.3.4"
__author__ = "TexasCoding"

# Core client classes - renamed from Async* to standard names
# Enable uvloop for better async performance (if available and not on Windows)
import sys

from project_x_py.client import ProjectX

# Configuration management
from project_x_py.config import (
    ConfigManager,
    create_custom_config,
    load_default_config,
    load_topstepx_config,
)

# Data management
from project_x_py.data import MemoryMappedStorage, TimeSeriesStorage

# Event system
from project_x_py.event_bus import EventBus, EventType

# Exceptions
from project_x_py.exceptions import (
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
from project_x_py.indicators import (
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
from project_x_py.models import (
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
from project_x_py.order_manager import OrderManager
from project_x_py.order_templates import (
    ATRStopTemplate,
    BreakoutTemplate,
    OrderTemplate,
    RiskRewardTemplate,
    ScalpingTemplate,
    get_template,
)

# Deprecated: These are re-exported for backward compatibility only
# Use TradingSuite.track_order() and TradingSuite.order_chain() instead
from project_x_py.order_tracker import (
    OrderChainBuilder,  # Deprecated: Use TradingSuite.order_chain()
    OrderLifecycleError,
    OrderTracker,  # Deprecated: Use TradingSuite.track_order()
)
from project_x_py.orderbook import (
    OrderBook,
    create_orderbook,
)
from project_x_py.position_manager import PositionManager
from project_x_py.realtime import ProjectXRealtimeClient as ProjectXRealtimeClient
from project_x_py.realtime_data_manager import RealtimeDataManager
from project_x_py.trading_suite import Features, TradingSuite, TradingSuiteConfig

# Type definitions - Import comprehensive type system
from project_x_py.types import (
    # Response types for API operations
    HealthStatusResponse,
    OrderManagerConfig,
    # Core types
    OrderSide,
    OrderStatus,
    OrderType,
    PerformanceStatsResponse,
    PortfolioMetricsResponse,
    PositionManagerConfig,
    PositionType,
    RiskAnalysisResponse,
)

# Utility functions
from project_x_py.utils import (
    RateLimiter,
    # Risk and portfolio analysis
    calculate_max_drawdown,
    calculate_portfolio_metrics,
    calculate_sharpe_ratio,
    # Utilities
    get_env_var,
    round_to_tick_size,
    setup_logging,
)

if sys.platform != "win32":
    try:
        import uvloop

        uvloop.install()
    except ImportError:
        pass  # uvloop not available, use default event loop

__all__ = [
    # Data Models
    "Account",
    "BracketOrderResponse",
    # Configuration
    "ConfigManager",
    # Event System
    "EventBus",
    "EventType",
    "Features",
    "HealthStatusResponse",
    "Instrument",
    "Order",
    # Core classes (now async-only but with original names)
    "OrderBook",
    "OrderChainBuilder",
    "OrderLifecycleError",
    "OrderManager",
    "OrderManagerConfig",
    "OrderPlaceResponse",
    "OrderTemplate",
    "OrderTracker",
    "OrderSide",
    "OrderStatus",
    "OrderType",
    "PerformanceStatsResponse",
    "PortfolioMetricsResponse",
    "Position",
    "PositionManager",
    "PositionManagerConfig",
    "PositionType",
    "ProjectX",
    # Data management
    "MemoryMappedStorage",
    "TimeSeriesStorage",
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
    "RiskAnalysisResponse",
    "Trade",
    "TradingSuite",
    "TradingSuiteConfig",
    # Version info
    "__author__",
    "__version__",
    # Order Templates
    "ATRStopTemplate",
    "BreakoutTemplate",
    "RiskRewardTemplate",
    "ScalpingTemplate",
    "get_template",
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
    "create_orderbook",
    "get_env_var",
    "load_default_config",
    "load_topstepx_config",
    "round_to_tick_size",
    "setup_logging",
]
