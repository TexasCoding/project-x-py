"""
Configuration type definitions for ProjectX SDK components.

Author: @TexasCoding
Date: 2025-08-04

Overview:
    Contains comprehensive TypedDict and dataclass definitions for all configuration
    types used throughout the SDK. Replaces generic dict[str, Any] usage with
    structured, type-safe configuration definitions.

Key Features:
    - TradingSuite configuration with feature flags and settings
    - Component-specific configuration types for all managers
    - Real-time client and WebSocket configuration
    - Performance tuning and memory management settings
    - Rate limiting and connection management configuration
    - Indicator calculation and analysis configuration

Type Categories:
    - Suite Configuration: TradingSuiteConfig, FeatureConfig
    - Component Configuration: OrderManagerConfig, PositionManagerConfig, DataManagerConfig
    - Connection Configuration: RealtimeConfig, WebSocketConfig, HTTPConfig
    - Performance Configuration: CacheConfig, RateLimitConfig, MemoryConfig
    - Analysis Configuration: IndicatorConfig, RiskConfig, OrderbookConfig

Example Usage:
    ```python
    from project_x_py.types.config_types import (
        TradingSuiteConfig,
        OrderManagerConfig,
        RealtimeConfig,
        CacheConfig,
    )

    # Configure TradingSuite
    suite_config = TradingSuiteConfig(
        features=["orderbook", "realtime_tracking"],
        timeframes=["1min", "5min", "15min"],
        initial_days=5,
        auto_connect=True,
    )

    # Configure OrderManager
    order_config = OrderManagerConfig(
        enable_bracket_orders=True,
        auto_risk_management=True,
        max_order_size=100,
        default_order_type="limit",
    )

    # Configure real-time client
    realtime_config = RealtimeConfig(
        reconnect_attempts=5,
        heartbeat_interval=30,
        message_timeout=10,
        enable_compression=True,
    )
    ```

Benefits:
    - Type safety for all configuration objects
    - Clear documentation of available configuration options
    - Validation of configuration values at compile time
    - Consistent configuration patterns across components
    - Easy configuration serialization and deserialization

See Also:
    - `types.base`: Core type definitions and constants
    - `types.response_types`: API response type definitions
    - `types.trading`: Trading operation types and enums
    - `models`: Data model classes and configuration
"""

from dataclasses import dataclass
from typing import Any, Literal, NotRequired, TypedDict


# TradingSuite Configuration Types
class TradingSuiteConfig(TypedDict):
    """Configuration for TradingSuite initialization."""

    features: NotRequired[
        list[str]
    ]  # Feature flags: "orderbook", "realtime_tracking", etc.
    timeframes: NotRequired[list[str]]  # e.g., ["1min", "5min", "15min"]
    initial_days: NotRequired[int]  # Historical data to load
    auto_connect: NotRequired[bool]  # Auto-connect real-time feeds
    enable_logging: NotRequired[bool]  # Enable detailed logging
    log_level: NotRequired[str]  # "DEBUG", "INFO", "WARNING", "ERROR"
    performance_mode: NotRequired[bool]  # Enable performance optimizations


class FeatureConfig(TypedDict):
    """Configuration for individual features."""

    orderbook: NotRequired[bool]
    realtime_tracking: NotRequired[bool]
    risk_management: NotRequired[bool]
    portfolio_analytics: NotRequired[bool]
    pattern_detection: NotRequired[bool]
    advanced_orders: NotRequired[bool]
    market_scanner: NotRequired[bool]
    backtesting: NotRequired[bool]


# Component Configuration Types
class OrderManagerConfig(TypedDict):
    """Configuration for OrderManager component."""

    enable_bracket_orders: NotRequired[bool]
    enable_trailing_stops: NotRequired[bool]
    auto_risk_management: NotRequired[bool]
    max_order_size: NotRequired[int]
    max_orders_per_minute: NotRequired[int]
    default_order_type: NotRequired[str]  # "market", "limit", "stop"
    enable_order_validation: NotRequired[bool]
    require_confirmation: NotRequired[bool]
    auto_cancel_on_close: NotRequired[bool]
    order_timeout_minutes: NotRequired[int]

    # Order state validation retry configuration
    status_check_max_attempts: NotRequired[int]  # Max retry attempts (default: 5)
    status_check_initial_delay: NotRequired[
        float
    ]  # Initial delay in seconds (default: 0.5)
    status_check_backoff_factor: NotRequired[
        float
    ]  # Exponential backoff multiplier (default: 2.0)
    status_check_max_delay: NotRequired[
        float
    ]  # Max delay between retries (default: 30.0)
    status_check_circuit_breaker_threshold: NotRequired[
        int
    ]  # Failures before circuit opens (default: 10)
    status_check_circuit_breaker_reset_time: NotRequired[
        float
    ]  # Time before circuit reset (default: 300.0)


class PositionManagerConfig(TypedDict):
    """Configuration for PositionManager component."""

    enable_risk_monitoring: NotRequired[bool]
    auto_stop_loss: NotRequired[bool]
    auto_take_profit: NotRequired[bool]
    max_position_size: NotRequired[int]
    max_portfolio_risk: NotRequired[float]  # As percentage
    position_sizing_method: NotRequired[
        str
    ]  # "fixed", "percentage", "kelly", "volatility"
    enable_correlation_analysis: NotRequired[bool]
    enable_portfolio_rebalancing: NotRequired[bool]
    rebalance_frequency_minutes: NotRequired[int]
    risk_calculation_interval: NotRequired[int]


class DataManagerConfig(TypedDict):
    """Configuration for RealtimeDataManager component."""

    max_bars_per_timeframe: NotRequired[int]
    enable_tick_data: NotRequired[bool]
    enable_level2_data: NotRequired[bool]
    buffer_size: NotRequired[int]
    compression_enabled: NotRequired[bool]
    data_validation: NotRequired[bool]
    auto_cleanup: NotRequired[bool]
    cleanup_interval_minutes: NotRequired[int]
    historical_data_cache: NotRequired[bool]
    cache_expiry_hours: NotRequired[int]
    timezone: NotRequired[str]  # Timezone for timestamp handling
    initial_days: NotRequired[int]  # Initial days of historical data to load

    # Dynamic resource management
    enable_dynamic_limits: NotRequired[bool]
    resource_config: NotRequired[dict[str, Any]]


class OrderbookConfig(TypedDict):
    """Configuration for OrderBook component."""

    max_depth_levels: NotRequired[int]
    max_trade_history: NotRequired[int]
    enable_market_by_order: NotRequired[bool]
    enable_analytics: NotRequired[bool]
    enable_pattern_detection: NotRequired[bool]
    snapshot_interval_seconds: NotRequired[int]
    memory_limit_mb: NotRequired[int]
    compression_level: NotRequired[int]  # 0-9
    enable_delta_updates: NotRequired[bool]
    price_precision: NotRequired[int]


# Connection Configuration Types
class RealtimeConfig(TypedDict):
    """Configuration for real-time WebSocket connections."""

    reconnect_attempts: NotRequired[int]
    reconnect_delay_seconds: NotRequired[float]
    heartbeat_interval_seconds: NotRequired[int]
    message_timeout_seconds: NotRequired[int]
    enable_compression: NotRequired[bool]
    buffer_size: NotRequired[int]
    max_message_size: NotRequired[int]
    ping_interval_seconds: NotRequired[int]
    connection_timeout_seconds: NotRequired[int]
    keep_alive: NotRequired[bool]


class WebSocketConfig(TypedDict):
    """Configuration for WebSocket client settings."""

    url: str
    protocols: NotRequired[list[str]]
    headers: NotRequired[dict[str, str]]
    compression: NotRequired[str]  # "deflate", "gzip", None
    max_size: NotRequired[int]  # Maximum message size
    max_queue: NotRequired[int]  # Maximum queue size
    ping_interval: NotRequired[float]
    ping_timeout: NotRequired[float]
    close_timeout: NotRequired[float]
    user_agent_header: NotRequired[str]


class HTTPConfig(TypedDict):
    """Configuration for HTTP client settings."""

    base_url: str
    timeout_seconds: NotRequired[int]
    max_retries: NotRequired[int]
    retry_delay_seconds: NotRequired[float]
    verify_ssl: NotRequired[bool]
    follow_redirects: NotRequired[bool]
    max_redirects: NotRequired[int]
    connection_pool_size: NotRequired[int]
    keep_alive: NotRequired[bool]
    headers: NotRequired[dict[str, str]]


# Performance Configuration Types
class CacheConfig(TypedDict):
    """Configuration for caching behavior."""

    enabled: NotRequired[bool]
    max_size: NotRequired[int]  # Maximum number of cached items
    ttl_seconds: NotRequired[int]  # Time to live
    cleanup_interval: NotRequired[int]  # Cleanup interval in seconds
    persistence: NotRequired[bool]  # Persist cache to disk
    compression: NotRequired[bool]  # Compress cached data
    memory_limit_mb: NotRequired[int]  # Memory limit for cache
    eviction_policy: NotRequired[str]  # "lru", "lfu", "ttl"


class RateLimitConfig(TypedDict):
    """Configuration for rate limiting."""

    requests_per_minute: NotRequired[int]
    burst_limit: NotRequired[int]
    backoff_strategy: NotRequired[str]  # "exponential", "linear", "fixed"
    max_backoff_seconds: NotRequired[float]
    enable_jitter: NotRequired[bool]
    track_by_endpoint: NotRequired[bool]
    global_limit: NotRequired[bool]
    per_connection_limit: NotRequired[int]


@dataclass
class MemoryManagementConfig:
    """Configuration for memory management across components."""

    max_memory_mb: int = 512
    gc_threshold: float = 0.8  # Trigger GC when memory usage exceeds this fraction
    cleanup_interval_seconds: int = 300
    enable_memory_monitoring: bool = True
    memory_alerts: bool = True
    alert_threshold_mb: int = 400
    auto_optimize: bool = True
    debug_memory_usage: bool = False


# Analysis Configuration Types
class IndicatorConfig(TypedDict):
    """Configuration for technical indicator calculations."""

    cache_results: NotRequired[bool]
    parallel_calculation: NotRequired[bool]
    precision: NotRequired[int]  # Decimal places
    smoothing_factor: NotRequired[float]
    lookback_periods: NotRequired[int]
    enable_volume_indicators: NotRequired[bool]
    enable_momentum_indicators: NotRequired[bool]
    enable_volatility_indicators: NotRequired[bool]
    custom_periods: NotRequired[dict[str, int]]  # Custom periods for indicators


class RiskConfig(TypedDict):
    """Configuration for risk management calculations."""

    var_confidence_level: NotRequired[float]  # Value at Risk confidence (0.95, 0.99)
    lookback_days: NotRequired[int]  # Historical data for risk calculations
    monte_carlo_simulations: NotRequired[int]
    stress_test_scenarios: NotRequired[list[str]]
    correlation_threshold: NotRequired[float]
    max_correlation: NotRequired[float]
    enable_scenario_analysis: NotRequired[bool]
    risk_calculation_frequency: NotRequired[str]  # "real-time", "hourly", "daily"


class BacktestConfig(TypedDict):
    """Configuration for backtesting engine."""

    start_date: str  # ISO format date
    end_date: str  # ISO format date
    initial_capital: float
    commission_per_trade: float
    slippage_bps: int  # Basis points
    benchmark: NotRequired[str]  # Benchmark symbol
    rebalance_frequency: NotRequired[str]  # "daily", "weekly", "monthly"
    enable_short_selling: NotRequired[bool]
    max_leverage: NotRequired[float]
    margin_requirement: NotRequired[float]


# Logging Configuration Types
class LoggingConfig(TypedDict):
    """Configuration for logging behavior."""

    level: str  # "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"
    format: NotRequired[str]  # Log format string
    handlers: NotRequired[list[str]]  # "console", "file", "syslog"
    file_path: NotRequired[str]  # Log file path
    max_file_size_mb: NotRequired[int]
    backup_count: NotRequired[int]
    enable_structured_logging: NotRequired[bool]
    include_timestamps: NotRequired[bool]
    include_thread_info: NotRequired[bool]
    log_performance_metrics: NotRequired[bool]


# Environment Configuration Types
class EnvironmentConfig(TypedDict):
    """Configuration for environment-specific settings."""

    environment: Literal["development", "staging", "production"]
    debug_mode: NotRequired[bool]
    verbose_logging: NotRequired[bool]
    enable_profiling: NotRequired[bool]
    mock_external_services: NotRequired[bool]
    test_mode: NotRequired[bool]
    feature_flags: NotRequired[dict[str, bool]]
    external_service_urls: NotRequired[dict[str, str]]


# Combined Configuration Type
class ProjectXSDKConfig(TypedDict):
    """Master configuration combining all component configurations."""

    # Core configuration
    environment: NotRequired[EnvironmentConfig]
    logging: NotRequired[LoggingConfig]

    # Component configurations
    trading_suite: NotRequired[TradingSuiteConfig]
    order_manager: NotRequired[OrderManagerConfig]
    position_manager: NotRequired[PositionManagerConfig]
    data_manager: NotRequired[DataManagerConfig]
    orderbook: NotRequired[OrderbookConfig]

    # Connection configurations
    realtime: NotRequired[RealtimeConfig]
    websocket: NotRequired[WebSocketConfig]
    http: NotRequired[HTTPConfig]

    # Performance configurations
    cache: NotRequired[CacheConfig]
    rate_limit: NotRequired[RateLimitConfig]
    memory: NotRequired[dict[str, Any]]  # MemoryManagementConfig fields

    # Analysis configurations
    indicators: NotRequired[IndicatorConfig]
    risk: NotRequired[RiskConfig]
    backtest: NotRequired[BacktestConfig]


__all__ = [
    "BacktestConfig",
    # Performance Configuration
    "CacheConfig",
    "DataManagerConfig",
    "EnvironmentConfig",
    "FeatureConfig",
    "HTTPConfig",
    # Analysis Configuration
    "IndicatorConfig",
    # System Configuration
    "LoggingConfig",
    "MemoryManagementConfig",
    # Component Configuration
    "OrderManagerConfig",
    "OrderbookConfig",
    "PositionManagerConfig",
    # Combined Configuration
    "ProjectXSDKConfig",
    "RateLimitConfig",
    # Connection Configuration
    "RealtimeConfig",
    "RiskConfig",
    # Suite Configuration
    "TradingSuiteConfig",
    "WebSocketConfig",
]
