"""
Protocol definitions for type checking across the ProjectX SDK.

Author: @TexasCoding
Date: 2025-08-02

Overview:
    Consolidates all protocol definitions used for type checking throughout the SDK,
    ensuring consistent interfaces between components. Provides comprehensive interface
    definitions for all major SDK components and their interactions.

Key Features:
    - Protocol definitions for all major SDK components
    - Interface validation for component interactions
    - Type safety for async/await patterns
    - Comprehensive attribute and method definitions
    - Support for mixin-based architecture
    - Type checking for real-time data flows

Protocol Categories:
    - Client Protocols: ProjectXClientProtocol for main client interface
    - Manager Protocols: OrderManagerProtocol, PositionManagerProtocol for business logic
    - Real-time Protocols: ProjectXRealtimeClientProtocol, RealtimeDataManagerProtocol
    - Component Interfaces: Comprehensive interface definitions for all SDK components

Example Usage:
    ```python
    from project_x_py.types.protocols import (
        ProjectXClientProtocol,
        OrderManagerProtocol,
        PositionManagerProtocol,
        RealtimeDataManagerProtocol,
    )


    # Implement protocol for custom client
    class MyCustomClient:
        def __init__(self):
            self.session_token: str = ""
            self._authenticated: bool = False
            self.logger = logging.getLogger(__name__)

        async def authenticate(self) -> None:
            # Implementation
            pass

        async def get_instrument(self, symbol: str) -> Instrument:
            # Implementation
            pass


    # Type checking ensures protocol compliance
    def process_client(client: ProjectXClientProtocol) -> None:
        # Can safely use all protocol methods
        pass


    # Use in manager implementations
    class MyOrderManager:
        def __init__(self, project_x: ProjectXClientProtocol):
            self.project_x = project_x

        async def place_order(self, contract_id: str, side: int) -> OrderPlaceResponse:
            # Implementation using protocol methods
            pass
    ```

Protocol Definitions:
    - ProjectXClientProtocol: Main client interface with authentication, HTTP, cache, and trading methods
    - OrderManagerProtocol: Order management interface with tracking, placement, and modification methods
    - PositionManagerProtocol: Position management interface with tracking, analytics, and operations
    - RealtimeDataManagerProtocol: Real-time data management interface with processing and access methods
    - ProjectXRealtimeClientProtocol: Real-time client interface with connection and event handling

Interface Benefits:
    - Compile-time type checking for all component interactions
    - Clear interface definitions for component development
    - Support for dependency injection and testing
    - Consistent method signatures across implementations
    - Type safety for async/await patterns and real-time data flows

See Also:
    - `types.base`: Core type definitions and constants
    - `types.trading`: Trading operation types and enums
    - `types.market_data`: Market data structures and configurations
"""

import asyncio
import datetime
import logging
from collections import defaultdict
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any, Protocol

import httpx
import polars as pl
from cachetools import TTLCache  # type: ignore

from project_x_py.types.base import HubConnection
from project_x_py.types.response_types import (
    PerformanceStatsResponse,
    PortfolioMetricsResponse,
    PositionAnalysisResponse,
    RiskAnalysisResponse,
)
from project_x_py.types.stats_types import PositionManagerStats

if TYPE_CHECKING:
    from project_x_py.client.base import ProjectXBase
    from project_x_py.models import (
        Account,
        Instrument,
        Order,
        OrderPlaceResponse,
        Position,
        ProjectXConfig,
        Trade,
    )
    from project_x_py.order_manager import OrderManager
    from project_x_py.realtime import ProjectXRealtimeClient
    from project_x_py.utils.async_rate_limiter import RateLimiter


class ProjectXClientProtocol(Protocol):
    """Protocol defining the interface that client mixins expect."""

    # Authentication attributes
    session_token: str
    token_expiry: "datetime.datetime | None"
    _authenticated: bool
    username: str
    api_key: str
    account_name: str | None
    account_info: "Account | None"
    logger: logging.Logger

    # HTTP client attributes
    _client: "httpx.AsyncClient | None"
    headers: dict[str, str]
    base_url: str
    config: "ProjectXConfig"
    rate_limiter: "RateLimiter"
    api_call_count: int

    # Cache attributes
    cache_hit_count: int
    cache_ttl: int
    last_cache_cleanup: float

    # Optimized cache attributes
    _opt_instrument_cache: Any  # LRUCache[str, Instrument]
    _opt_instrument_cache_time: dict[str, float]
    _opt_market_data_cache: Any  # TTLCache[str, bytes]
    _opt_market_data_cache_time: dict[str, float]

    # Authentication methods
    def _should_refresh_token(self) -> bool: ...
    async def authenticate(self) -> None: ...
    async def _refresh_authentication(self) -> None: ...
    async def _ensure_authenticated(self) -> None: ...
    async def list_accounts(self) -> list["Account"]: ...

    # HTTP methods
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        retry_count: int = 0,
    ) -> Any: ...
    async def _create_client(self) -> httpx.AsyncClient: ...
    async def _ensure_client(self) -> httpx.AsyncClient: ...
    async def get_health_status(self) -> PerformanceStatsResponse: ...

    # Cache methods
    async def _cleanup_cache(self) -> None: ...
    def get_cached_instrument(self, symbol: str) -> "Instrument | None": ...
    def cache_instrument(self, symbol: str, instrument: "Instrument") -> None: ...
    def get_cached_market_data(self, cache_key: str) -> pl.DataFrame | None: ...
    def cache_market_data(self, cache_key: str, data: pl.DataFrame) -> None: ...
    def clear_all_caches(self) -> None: ...

    # Market data methods
    async def get_instrument(self, symbol: str, live: bool = False) -> "Instrument": ...
    async def search_instruments(
        self, query: str, live: bool = False
    ) -> list["Instrument"]: ...
    async def get_bars(
        self,
        symbol: str,
        days: int = 8,
        interval: int = 5,
        unit: int = 2,
        limit: int | None = None,
        partial: bool = True,
    ) -> pl.DataFrame: ...
    def _select_best_contract(
        self, instruments: list[dict[str, Any]], search_symbol: str
    ) -> dict[str, Any]: ...

    # Trading methods
    async def get_positions(self) -> list["Position"]: ...
    async def search_open_positions(
        self, account_id: int | None = None
    ) -> list["Position"]: ...
    async def search_trades(
        self,
        start_date: "datetime.datetime | None" = None,
        end_date: "datetime.datetime | None" = None,
        contract_id: str | None = None,
        account_id: int | None = None,
        limit: int = 100,
    ) -> list["Trade"]: ...


class OrderManagerProtocol(Protocol):
    """Protocol defining the interface that mixins expect from OrderManager."""

    project_x: "ProjectXBase"
    realtime_client: "ProjectXRealtimeClient | None"
    event_bus: Any  # EventBus instance
    order_lock: asyncio.Lock
    _realtime_enabled: bool
    stats: dict[str, Any]  # Comprehensive statistics tracking

    # From tracking mixin - updated to use TTLCache for memory management
    tracked_orders: TTLCache[str, dict[str, Any]]
    order_status_cache: TTLCache[str, int]
    position_orders: dict[str, dict[str, list[int]]]
    order_to_position: dict[int, str]
    oco_groups: dict[int, int]  # order_id -> other_order_id for OCO pairs
    # Memory management attributes for order tracking
    _max_tracked_orders: int
    _order_ttl_seconds: int
    _cleanup_interval: int
    _completed_orders: Any  # deque[tuple[str, float]]
    _memory_stats: dict[str, Any]
    _cleanup_task: "asyncio.Task[None] | None"
    _cleanup_enabled: bool

    # Methods that mixins need
    async def place_order(
        self,
        contract_id: str,
        order_type: int,
        side: int,
        size: int,
        limit_price: float | None = None,
        stop_price: float | None = None,
        trail_price: float | None = None,
        custom_tag: str | None = None,
        linked_order_id: int | None = None,
        account_id: int | None = None,
    ) -> "OrderPlaceResponse": ...

    async def place_market_order(
        self, contract_id: str, side: int, size: int, account_id: int | None = None
    ) -> "OrderPlaceResponse": ...

    async def place_limit_order(
        self,
        contract_id: str,
        side: int,
        size: int,
        limit_price: float,
        account_id: int | None = None,
    ) -> "OrderPlaceResponse": ...

    async def place_stop_order(
        self,
        contract_id: str,
        side: int,
        size: int,
        stop_price: float,
        account_id: int | None = None,
    ) -> "OrderPlaceResponse": ...

    async def get_order_by_id(self, order_id: int) -> "Order | None": ...

    async def cancel_order(
        self, order_id: int, account_id: int | None = None
    ) -> bool: ...

    # Memory management methods
    def get_memory_stats(self) -> dict[str, Any]: ...
    async def _start_cleanup_task(self) -> None: ...
    async def _stop_cleanup_task(self) -> None: ...
    def clear_order_tracking(self) -> None: ...

    async def modify_order(
        self,
        order_id: int,
        limit_price: float | None = None,
        stop_price: float | None = None,
        size: int | None = None,
    ) -> bool: ...

    async def search_open_orders(
        self,
        account_id: int | None = None,
        contract_id: str | None = None,
    ) -> list["Order"]: ...

    async def get_tracked_order_status(
        self, order_id: str, wait_for_cache: bool = False
    ) -> dict[str, Any] | None: ...

    async def track_order_for_position(
        self,
        contract_id: str,
        order_id: int,
        order_type: str = "entry",
        account_id: int | None = None,
    ) -> None: ...

    def untrack_order(self, order_id: int) -> None: ...

    def get_position_orders(self, contract_id: str) -> dict[str, list[int]]: ...

    async def _on_order_update(
        self, order_data: dict[str, Any] | list[Any]
    ) -> None: ...

    async def _on_trade_execution(
        self, trade_data: dict[str, Any] | list[Any]
    ) -> None: ...

    async def cancel_position_orders(
        self,
        contract_id: str,
        order_types: list[str] | None = None,
        account_id: int | None = None,
    ) -> dict[str, int | list[str]]: ...

    async def update_position_order_sizes(
        self, contract_id: str, new_size: int, account_id: int | None = None
    ) -> dict[str, Any]: ...

    async def sync_orders_with_position(
        self,
        contract_id: str,
        target_size: int,
        cancel_orphaned: bool = True,
        account_id: int | None = None,
    ) -> dict[str, Any]: ...

    async def on_position_closed(
        self, contract_id: str, account_id: int | None = None
    ) -> None: ...

    async def _setup_realtime_callbacks(self) -> None: ...

    # Methods used by bracket orders
    async def _wait_for_order_fill(
        self, order_id: int, timeout_seconds: int = 30
    ) -> bool: ...
    def _link_oco_orders(self, order1_id: int, order2_id: int) -> None: ...
    def _unlink_oco_orders(self, order_id: int) -> int | None: ...
    async def _check_order_fill_status(
        self, order_id: int
    ) -> tuple[bool, int, int]: ...
    async def _place_protective_orders_with_retry(
        self,
        contract_id: str,
        side: int,
        size: int,
        stop_loss_price: float,
        take_profit_price: float,
        account_id: int | None = None,
    ) -> tuple[Any, Any]: ...
    async def close_position(
        self,
        contract_id: str,
        method: str = "market",
        limit_price: float | None = None,
        account_id: int | None = None,
    ) -> "OrderPlaceResponse | None": ...

    def _get_recovery_manager(self) -> Any: ...


class PositionManagerProtocol(Protocol):
    """Protocol defining the interface that mixins expect from PositionManager."""

    project_x: "ProjectXBase"
    logger: Any
    event_bus: Any  # EventBus instance
    position_lock: asyncio.Lock
    realtime_client: "ProjectXRealtimeClient | None"
    _realtime_enabled: bool
    order_manager: "OrderManager | None"
    _order_sync_enabled: bool
    tracked_positions: dict[str, "Position"]
    position_history: dict[str, list[dict[str, Any]]]
    _monitoring_active: bool
    _monitoring_task: "asyncio.Task[None] | None"
    position_alerts: dict[str, dict[str, Any]]
    stats: dict[str, Any]
    risk_settings: dict[str, Any]

    # Methods required by mixins
    async def _setup_realtime_callbacks(self) -> None: ...
    async def _on_position_update(
        self, data: dict[str, Any] | list[dict[str, Any]]
    ) -> None: ...
    async def _on_account_update(self, data: dict[str, Any]) -> None: ...
    async def _process_position_data(
        self, position_data: dict[str, Any]
    ) -> "Position | None": ...
    async def _trigger_callbacks(
        self, event_type: str, data: dict[str, Any]
    ) -> None: ...
    def _validate_position_payload(self, position_data: dict[str, Any]) -> bool: ...
    async def _check_position_alerts(
        self,
        contract_id: str,
        current_position: "Position",
        old_position: "Position | None",
    ) -> None: ...
    async def get_all_positions(
        self, account_id: int | None = None
    ) -> list["Position"]: ...
    async def get_position(
        self, contract_id: str, account_id: int | None = None
    ) -> "Position | None": ...
    async def refresh_positions(self, account_id: int | None = None) -> int: ...
    async def close_position_direct(
        self, contract_id: str, account_id: int | None = None
    ) -> dict[str, Any]: ...
    async def partially_close_position(
        self, contract_id: str, reduce_by: int, account_id: int | None = None
    ) -> dict[str, Any]: ...
    async def calculate_position_pnl(
        self,
        position: "Position",
        current_price: float,
        point_value: float | None = None,
    ) -> "PositionAnalysisResponse": ...
    async def get_portfolio_pnl(
        self,
        account_id: int | None = None,
    ) -> "PortfolioMetricsResponse": ...
    async def get_risk_metrics(self) -> "RiskAnalysisResponse": ...
    def get_position_statistics(
        self,
    ) -> "PositionManagerStats": ...
    async def _monitoring_loop(self, refresh_interval: int) -> None: ...
    async def stop_monitoring(self) -> None: ...
    async def _verify_and_remove_closed_position(self, contract_id: str) -> bool: ...


class RealtimeDataManagerProtocol(Protocol):
    """Protocol defining the interface for RealtimeDataManager components."""

    # Core attributes
    instrument: str
    project_x: "ProjectXBase | None"
    realtime_client: "ProjectXRealtimeClient"
    event_bus: Any  # EventBus instance
    logger: Any
    timezone: Any  # pytz.tzinfo.BaseTzInfo

    # Timeframe configuration
    timeframes: dict[str, dict[str, Any]]

    # Data storage
    data: dict[str, pl.DataFrame]
    current_tick_data: Any  # Can be list or deque
    last_bar_times: dict[str, datetime.datetime]

    # Synchronization
    data_lock: "asyncio.Lock | Any"  # Can be Lock or AsyncRWLock
    is_running: bool
    indicator_cache: defaultdict[str, dict[str, Any]]

    # Contract and subscription
    contract_id: str | None

    # Memory management settings
    max_bars_per_timeframe: int
    tick_buffer_size: int
    cleanup_interval: float
    last_cleanup: float
    memory_stats: dict[str, Any]

    # Background tasks
    _cleanup_task: "asyncio.Task[None] | None"

    # Methods required by mixins
    async def _cleanup_old_data(self) -> None: ...
    async def _periodic_cleanup(self) -> None: ...
    async def _trigger_callbacks(
        self, _event_type: str, _data: dict[str, Any]
    ) -> None: ...
    async def _on_quote_update(self, callback_data: dict[str, Any]) -> None: ...
    async def _on_trade_update(self, callback_data: dict[str, Any]) -> None: ...
    async def _process_tick_data(self, tick: dict[str, Any]) -> None: ...
    async def _update_timeframe_data(
        self, tf_key: str, timestamp: datetime.datetime, price: float, volume: int
    ) -> dict[str, Any] | None: ...
    def _calculate_bar_time(
        self, timestamp: datetime.datetime, interval: int, unit: int
    ) -> datetime.datetime: ...
    def _parse_and_validate_trade_payload(
        self, _trade_data: Any
    ) -> dict[str, Any] | None: ...
    def _parse_and_validate_quote_payload(
        self, _quote_data: Any
    ) -> dict[str, Any] | None: ...
    def _symbol_matches_instrument(self, _symbol: str) -> bool: ...

    # Public interface methods
    async def initialize(self, initial_days: int = 1) -> bool: ...
    async def start_realtime_feed(self) -> bool: ...
    async def stop_realtime_feed(self) -> None: ...
    async def get_data(
        self, timeframe: str = "5min", bars: int | None = None
    ) -> pl.DataFrame | None: ...
    async def get_current_price(self) -> float | None: ...
    async def get_mtf_data(self) -> dict[str, pl.DataFrame]: ...
    async def add_callback(
        self,
        event_type: str,
        callback: Callable[[dict[str, Any]], Coroutine[Any, Any, None] | None],
    ) -> None: ...
    def get_memory_stats(self) -> Any: ...  # Returns RealtimeDataManagerStats
    def get_realtime_validation_status(self) -> dict[str, Any]: ...
    async def cleanup(self) -> None: ...

    # Memory management methods
    def start_cleanup_task(self) -> None: ...
    async def stop_cleanup_task(self) -> None: ...


class ProjectXRealtimeClientProtocol(Protocol):
    """Protocol defining the interface for ProjectXRealtimeClient components."""

    # Core attributes
    jwt_token: str
    account_id: str
    user_hub_url: str
    market_hub_url: str
    base_user_url: str
    base_market_url: str
    config: "ProjectXConfig"

    # Connection objects
    user_connection: HubConnection | None
    market_connection: HubConnection | None

    # Connection state
    user_connected: bool
    market_connected: bool
    setup_complete: bool

    # Callbacks and stats
    callbacks: defaultdict[str, list[Any]]
    stats: dict[str, Any]

    # Subscriptions
    _subscribed_contracts: list[str]

    # Logging
    logger: Any

    # Async locks and events
    _callback_lock: asyncio.Lock
    _connection_lock: asyncio.Lock
    user_hub_ready: asyncio.Event
    market_hub_ready: asyncio.Event

    # Event loop
    _loop: asyncio.AbstractEventLoop | None

    # Batching support (optimized)
    _batched_handler: Any | None  # OptimizedRealtimeHandler
    _use_batching: bool

    # Health monitoring attributes
    heartbeat_interval: float
    health_threshold: float
    latency_threshold_ms: float
    max_latency_samples: int
    _health_monitoring_enabled: bool
    _heartbeat_tasks: dict[str, Any]  # dict[str, asyncio.Task[Any]]
    _health_lock: asyncio.Lock
    _connection_start_time: float
    _last_user_heartbeat: float
    _last_market_heartbeat: float
    _user_heartbeat_pending: bool
    _market_heartbeat_pending: bool
    _user_latencies: Any  # Deque[float]
    _market_latencies: Any  # Deque[float]
    _total_heartbeats_sent: int
    _user_heartbeats_failed: int
    _market_heartbeats_failed: int
    _connection_failures: int
    _last_health_score: float
    _events_received_last_check: int
    _last_performance_check: float

    # Methods required by mixins
    async def setup_connections(self) -> None: ...
    async def connect(self) -> bool: ...
    async def disconnect(self) -> None: ...
    async def _start_connection_async(self, connection: Any, name: str) -> None: ...
    def _on_user_hub_open(self) -> None: ...
    def _on_user_hub_close(self) -> None: ...
    def _on_market_hub_open(self) -> None: ...
    def _on_market_hub_close(self) -> None: ...
    def _on_connection_error(self, hub: str, error: Any) -> None: ...
    async def add_callback(
        self,
        event_type: str,
        callback: Callable[[dict[str, Any]], Coroutine[Any, Any, None] | None],
    ) -> None: ...
    async def remove_callback(
        self,
        event_type: str,
        callback: Callable[[dict[str, Any]], Coroutine[Any, Any, None] | None],
    ) -> None: ...
    async def _trigger_callbacks(
        self, event_type: str, data: dict[str, Any]
    ) -> None: ...
    def _forward_account_update(self, *args: Any) -> None: ...
    def _forward_position_update(self, *args: Any) -> None: ...
    def _forward_order_update(self, *args: Any) -> None: ...
    def _forward_trade_execution(self, *args: Any) -> None: ...
    def _forward_quote_update(self, *args: Any) -> None: ...
    def _forward_market_trade(self, *args: Any) -> None: ...
    def _forward_market_depth(self, *args: Any) -> None: ...
    def _schedule_async_task(self, event_type: str, data: Any) -> None: ...
    async def _forward_event_async(self, event_type: str, args: Any) -> None: ...
    async def subscribe_user_updates(self) -> bool: ...
    async def subscribe_market_data(self, contract_ids: list[str]) -> bool: ...
    async def unsubscribe_user_updates(self) -> bool: ...
    async def unsubscribe_market_data(self, contract_ids: list[str]) -> bool: ...
    def is_connected(self) -> bool: ...
    def get_stats(self) -> dict[str, Any]: ...
    async def update_jwt_token(
        self, new_jwt_token: str, timeout: float = 30.0
    ) -> bool: ...
    async def _recover_connection_state(
        self,
        original_token: str,
        original_setup_complete: bool,
        original_subscriptions: list[str],
    ) -> None: ...
    async def cleanup(self) -> None: ...
    def get_task_stats(self) -> dict[str, Any]: ...

    # Health monitoring methods
    async def configure_health_monitoring(
        self,
        heartbeat_interval: float = 10.0,
        health_threshold: float = 70.0,
        latency_threshold_ms: float = 2000.0,
        max_latency_samples: int = 1000,
    ) -> None: ...
    async def get_health_status(self) -> dict[str, Any]: ...
    async def get_performance_metrics(self) -> dict[str, Any]: ...
    async def is_connection_healthy(self, threshold: float | None = None) -> bool: ...
    async def force_health_reconnect(self) -> bool: ...
    def _init_health_monitoring(self) -> None: ...
    async def _start_health_monitoring(self) -> None: ...
    async def _stop_health_monitoring(self) -> None: ...
    async def _user_heartbeat_loop(self) -> None: ...
    async def _market_heartbeat_loop(self) -> None: ...
    async def _send_heartbeat(self, hub: str) -> None: ...
    def _calculate_latency_stats(self, latencies: Any) -> dict[str, float]: ...
    def _calculate_event_rate(self) -> float: ...
    async def _calculate_health_score(self) -> float: ...
    def _calculate_latency_score(self) -> float: ...
    def _calculate_reliability_score(self) -> float: ...
    def _calculate_event_processing_score(self) -> float: ...
    def _calculate_success_rate(self, hub: str) -> float: ...
    def _get_health_status_string(self, health_score: float) -> str: ...
    async def _cleanup_tasks(self, timeout: float = 5.0) -> None: ...
    def _create_task(
        self, coro: Any, name: str | None = None, persistent: bool = False
    ) -> Any: ...


__all__ = [
    "OrderManagerProtocol",
    "PositionManagerProtocol",
    "ProjectXClientProtocol",
    "ProjectXRealtimeClientProtocol",
    "RealtimeDataManagerProtocol",
]
