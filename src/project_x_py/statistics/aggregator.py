"""
Centralized statistics aggregation for ProjectX SDK.

Author: @TexasCoding
Date: 2025-08-21

Overview:
    StatisticsAggregator provides centralized collection and aggregation of statistics
    from all registered SDK components. Features parallel collection using asyncio.gather(),
    cross-component metrics calculation, health score aggregation, and performance
    optimization through TTL caching. Handles component failures gracefully with
    timeout protection and partial result recovery.

Key Features:
    - 100% async architecture with parallel component collection
    - Centralized registration system for statistics providers
    - Cross-component metrics calculation (total errors, combined P&L, etc.)
    - Health score aggregation with weighted averages
    - TTL caching for performance optimization (5-second default)
    - Graceful error handling with timeout protection (1 second per component)
    - Partial result recovery when some components fail
    - Type-safe statistics using ComprehensiveStats and TradingSuiteStats

Components Supported:
    - TradingSuite: Suite-level statistics and component orchestration
    - OrderManager: Order lifecycle and execution metrics
    - PositionManager: P&L analysis and position tracking
    - RealtimeDataManager: Data throughput and latency monitoring
    - OrderBook: Market microstructure and depth analysis
    - RiskManager: Risk assessment and managed trade monitoring

Cross-Component Metrics:
    - Total errors across all components
    - Overall health score (weighted average)
    - System-wide performance metrics (API calls, response times)
    - Combined P&L from position and risk managers
    - Total memory usage and resource utilization
    - Aggregated data throughput and processing rates

Example Usage:
    ```python
    from project_x_py.statistics.aggregator import StatisticsAggregator

    # Initialize aggregator
    aggregator = StatisticsAggregator()

    # Register components
    await aggregator.register_component("trading_suite", trading_suite)
    await aggregator.register_component("order_manager", order_manager)

    # Get comprehensive statistics
    stats = await aggregator.get_comprehensive_stats()
    print(f"Overall Health: {stats['suite']['health_score']}")

    # Get suite-level statistics only
    suite_stats = await aggregator.get_suite_stats()
    print(f"Total Errors: {suite_stats['total_errors']}")
    ```

Performance Considerations:
    - Parallel collection reduces total time from sum of components to max component time
    - TTL caching prevents redundant expensive operations within 5-second windows
    - Timeout protection (1 second per component) prevents hanging on failed components
    - Memory-efficient partial result handling for large-scale deployments
    - Graceful degradation ensures aggregator remains functional even with component failures

See Also:
    - `project_x_py.statistics.base`: Base statistics tracking infrastructure
    - `project_x_py.statistics.collector`: Component-specific collection
    - `project_x_py.types.stats_types`: TypedDict definitions for type safety
"""

import asyncio
import inspect
import time
from typing import TYPE_CHECKING, Any, Protocol

from project_x_py.statistics.base import BaseStatisticsTracker
from project_x_py.statistics.collector import ComponentCollector
from project_x_py.types.stats_types import (
    ComponentStats,
    ComprehensiveStats,
    TradingSuiteStats,
)

if TYPE_CHECKING:
    pass


class ComponentProtocol(Protocol):
    """
    Protocol for components that can provide statistics.

    Note: While the v3.3.0 statistics system is 100% async internally,
    this protocol supports both sync and async methods for backward
    compatibility during migration. New components should implement
    only the async methods.
    """

    async def get_statistics(self) -> dict[str, Any] | None:
        """Get component statistics (async - PREFERRED)."""
        ...

    async def get_health_score(self) -> float:
        """Get component health score (0-100) - async only."""
        ...


class StatisticsAggregator(BaseStatisticsTracker):
    """
    Centralized statistics aggregation for all ProjectX SDK components.

    Provides parallel collection from registered components, cross-component
    metrics calculation, health score aggregation, and performance optimization
    through TTL caching. Handles component failures gracefully with timeout
    protection and partial result recovery.

    Features:
        - Async component registration and management
        - Parallel statistics collection using asyncio.gather()
        - Cross-component metrics calculation (total errors, combined P&L)
        - Health score aggregation with weighted averages
        - TTL caching for expensive operations (5-second default)
        - Timeout protection (1 second per component)
        - Graceful error handling with partial results
        - Type-safe statistics using ComprehensiveStats

    Performance Optimizations:
        - Parallel collection reduces total time to max component time
        - TTL caching prevents redundant calculations within cache window
        - Timeout protection prevents hanging on failed components
        - Memory-efficient handling of large statistics datasets
    """

    def __init__(self, cache_ttl: float = 5.0, component_timeout: float = 1.0):
        """
        Initialize the statistics aggregator.

        Args:
            cache_ttl: Cache TTL in seconds for expensive operations (default: 5.0)
            component_timeout: Timeout in seconds for individual component collection (default: 1.0)
        """
        super().__init__("statistics_aggregator", cache_ttl=cache_ttl)
        self.component_timeout = component_timeout

        # Registered components for statistics collection
        self._components: dict[str, Any] = {}
        self._component_lock = asyncio.Lock()

        # Specialized collectors
        self._collector: ComponentCollector | None = None

        # Cross-component metrics tracking
        self._last_comprehensive_collection: float | None = None
        self._last_suite_collection: float | None = None

    async def register_component(self, name: str, component: Any) -> None:
        """
        Register a component for statistics collection.

        Components should implement at least one of: get_stats(), get_statistics(),
        get_memory_stats(), or get_health_score() methods. The aggregator will
        automatically detect which methods are available and use them appropriately.

        Args:
            name: Unique name for the component
            component: Component instance to register

        Raises:
            ValueError: If component name is already registered
        """
        async with self._component_lock:
            if name in self._components:
                await self.track_error(
                    ValueError(f"Component '{name}' already registered"),
                    "Component registration",
                    {"component_name": name},
                )
                raise ValueError(f"Component '{name}' already registered")

            self._components[name] = component
            await self.increment("components_registered")
            await self.set_status("active")

            # Set up specialized collector for TradingSuite
            if name == "trading_suite" and hasattr(component, "orders"):
                self._collector = ComponentCollector(component)

    async def unregister_component(self, name: str) -> None:
        """
        Remove a component from statistics collection.

        Args:
            name: Name of the component to remove

        Raises:
            KeyError: If component name is not registered
        """
        async with self._component_lock:
            if name not in self._components:
                await self.track_error(
                    KeyError(f"Component '{name}' not registered"),
                    "Component unregistration",
                    {"component_name": name},
                )
                raise KeyError(f"Component '{name}' not registered")

            del self._components[name]
            await self.increment("components_unregistered")

            # Clear collector if trading suite is removed
            if name == "trading_suite":
                self._collector = None

            # Update status
            if not self._components:
                await self.set_status("idle")

    async def get_comprehensive_stats(self) -> ComprehensiveStats:
        """
        Get comprehensive statistics from all registered components.

        Collects statistics from all components in parallel using asyncio.gather(),
        calculates cross-component metrics, and aggregates health scores. Uses
        TTL caching to optimize performance for repeated calls within the cache window.

        Returns:
            ComprehensiveStats with suite, component, connection, and performance data

        Performance:
            - Parallel collection reduces total time to max component time
            - TTL caching prevents redundant expensive operations
            - Timeout protection ensures responsiveness even with failed components
        """
        await self.set_status("collecting")
        collection_start = time.time()

        try:
            # Check cache first
            cached_stats = await self._get_cached_value("comprehensive_stats")
            if cached_stats is not None:
                await self.increment("cache_hits")
                return cached_stats

            # Collect from all components in parallel
            component_stats = await self._collect_all_components()

            # Get suite-level statistics
            suite_stats = await self._build_suite_stats(component_stats)

            # Build comprehensive statistics
            stats: ComprehensiveStats = {
                "suite": suite_stats,
                "generated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
                "collection_time_ms": round((time.time() - collection_start) * 1000, 2),
            }

            # Add component-specific statistics if available
            if "order_manager" in component_stats:
                stats["order_manager"] = component_stats["order_manager"]
            if "position_manager" in component_stats:
                stats["position_manager"] = component_stats["position_manager"]
            if "data_manager" in component_stats:
                stats["data_manager"] = component_stats["data_manager"]
            if "orderbook" in component_stats:
                stats["orderbook"] = component_stats["orderbook"]
            if "risk_manager" in component_stats:
                stats["risk_manager"] = component_stats["risk_manager"]

            # Add connection and performance statistics if available
            if "realtime" in component_stats:
                stats["realtime"] = component_stats["realtime"]
            if "http_client" in component_stats:
                stats["http_client"] = component_stats["http_client"]
            if "cache" in component_stats:
                stats["cache"] = component_stats["cache"]
            if "memory" in component_stats:
                stats["memory"] = component_stats["memory"]

            # Cache the result
            await self._set_cached_value("comprehensive_stats", stats)
            await self.increment("comprehensive_collections")
            await self.record_timing(
                "comprehensive_collection", (time.time() - collection_start) * 1000
            )
            await self.set_status("active")

            self._last_comprehensive_collection = time.time()
            return stats

        except Exception as e:
            await self.track_error(e, "Comprehensive statistics collection failed")
            await self.set_status("error")

            # Return minimal stats on error
            return self._get_error_stats(collection_start)

    async def get_suite_stats(self) -> TradingSuiteStats:
        """
        Get TradingSuite-level statistics with cross-component metrics.

        Provides suite-level view of the system including component status,
        cross-component metrics, and overall health scoring. Optimized for
        frequent polling with TTL caching and efficient component collection.

        Returns:
            TradingSuiteStats with suite-level metrics and component summary

        Performance:
            - Lighter weight than comprehensive stats collection
            - Focuses on suite-level metrics and cross-component calculations
            - TTL caching for frequent polling scenarios
        """
        # Register pending components if needed (compatibility layer)
        if hasattr(self, "_pending_components") and self._pending_components:
            await self._register_all_pending_components()

        await self.set_status("collecting")
        collection_start = time.time()

        try:
            # Check cache first
            cached_stats = await self._get_cached_value("suite_stats")
            if cached_stats is not None:
                await self.increment("cache_hits")
                return cached_stats

            # Collect component data
            component_stats = await self._collect_all_components()

            # Build suite statistics
            suite_stats = await self._build_suite_stats(component_stats)

            # Cache the result
            await self._set_cached_value("suite_stats", suite_stats)
            await self.increment("suite_collections")
            await self.record_timing(
                "suite_collection", (time.time() - collection_start) * 1000
            )
            await self.set_status("active")

            self._last_suite_collection = time.time()
            return suite_stats

        except Exception as e:
            await self.track_error(e, "Suite statistics collection failed")
            await self.set_status("error")

            # Return minimal stats on error
            return await self._get_minimal_suite_stats()

    async def _collect_all_components(self) -> dict[str, Any]:
        """
        Collect statistics from all registered components in parallel.

        Uses asyncio.gather() to collect statistics from all components
        simultaneously, with timeout protection and graceful error handling.
        Failed components don't prevent collection from other components.

        Returns:
            Dictionary of component statistics keyed by component name
        """
        if not self._components:
            return {}

        # If we have a collector, use it for detailed component stats
        if self._collector is not None:
            try:
                return await asyncio.wait_for(
                    self._collector.collect(),
                    timeout=self.component_timeout * len(self._components),
                )
            except TimeoutError:
                await self.track_error(
                    TimeoutError("Component collector timed out"),
                    "Parallel component collection",
                )
            except Exception as e:
                await self.track_error(e, "Component collector failed")

        # Fallback to direct component collection
        async with self._component_lock:
            components = list(self._components.items())

        collectible = [
            (name, component)
            for name, component in components
            if name != "trading_suite"
        ]

        tasks = []
        for name, component in collectible:
            task = asyncio.create_task(self._collect_component_stats(name, component))
            tasks.append(task)

        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=self.component_timeout * max(len(collectible), 1),
            )

            component_stats = {}
            for (name, _), result in zip(collectible, results, strict=False):
                if isinstance(result, Exception):
                    await self.track_error(
                        result,
                        f"Failed to collect statistics from {name}",
                        {"component_name": name},
                    )
                elif result is not None:
                    component_stats[name] = result

            return component_stats

        except TimeoutError:
            await self.track_error(
                TimeoutError("Component collection timed out"),
                "Parallel component collection",
            )
            return {}

    async def _invoke_stats_method(self, method: Any) -> Any:
        """Call a stats method, awaiting it when it is async or returns a coroutine."""
        if asyncio.iscoroutinefunction(method):
            return await asyncio.wait_for(method(), timeout=self.component_timeout)
        result = method()
        if inspect.isawaitable(result):
            return await asyncio.wait_for(result, timeout=self.component_timeout)
        return result

    async def _collect_component_stats(
        self, name: str, component: Any
    ) -> dict[str, Any] | None:
        """
        Collect statistics from a single component with timeout protection.

        Tries multiple methods to get statistics from the component:
        1. get_statistics() (async or sync)
        2. get_stats() (async or sync)
        3. get_memory_stats() (async or sync)
        4. Direct stats attribute access

        Args:
            name: Component name for error reporting
            component: Component instance to collect from

        Returns:
            Component statistics dictionary or None if collection fails
        """
        if name == "trading_suite":
            return None
        try:
            start_time = time.time()

            # Try get_statistics() first (async or sync)
            if hasattr(component, "get_statistics"):
                try:
                    result = await self._invoke_stats_method(component.get_statistics)
                    if result:
                        await self.record_timing(
                            f"{name}_collection", (time.time() - start_time) * 1000
                        )
                        return dict(result) if isinstance(result, dict) else None
                except TimeoutError:
                    await self.track_error(
                        TimeoutError("Component statistics timed out"),
                        f"get_statistics timeout for {name}",
                        {"component_name": name},
                    )
                    return None
                except (AttributeError, TypeError):
                    pass

            # Try get_stats() (async or sync — TradingSuite/data manager are async)
            if hasattr(component, "get_stats"):
                try:
                    result = await self._invoke_stats_method(component.get_stats)
                    if result:
                        await self.record_timing(
                            f"{name}_collection", (time.time() - start_time) * 1000
                        )
                        return dict(result) if isinstance(result, dict) else None
                except TimeoutError:
                    await self.track_error(
                        TimeoutError("Component statistics timed out"),
                        f"get_stats timeout for {name}",
                        {"component_name": name},
                    )
                    return None
                except (AttributeError, TypeError):
                    pass

            # Try get_memory_stats() (async or sync)
            if hasattr(component, "get_memory_stats"):
                try:
                    result = await self._invoke_stats_method(component.get_memory_stats)
                    if result:
                        await self.record_timing(
                            f"{name}_collection", (time.time() - start_time) * 1000
                        )
                        return dict(result) if isinstance(result, dict) else None
                except TimeoutError:
                    await self.track_error(
                        TimeoutError("Component statistics timed out"),
                        f"get_memory_stats timeout for {name}",
                        {"component_name": name},
                    )
                    return None
                except (AttributeError, TypeError):
                    pass

            # Try direct stats attribute
            if hasattr(component, "stats"):
                try:
                    result = dict(component.stats) if component.stats else None
                    if result:
                        await self.record_timing(
                            f"{name}_collection", (time.time() - start_time) * 1000
                        )
                        return result
                except (AttributeError, TypeError):
                    pass

            return None

        except Exception as e:
            await self.track_error(
                e,
                f"Component statistics collection failed for {name}",
                {"component_name": name},
            )
            return None

    async def _build_suite_stats(
        self, component_stats: dict[str, Any]
    ) -> TradingSuiteStats:
        """
        Build TradingSuite statistics with cross-component metrics.

        Aggregates statistics from all components to create suite-level metrics
        including total errors, overall health score, and system-wide performance
        indicators. Calculates cross-component derived metrics.

        Args:
            component_stats: Dictionary of component statistics

        Returns:
            TradingSuiteStats with aggregated suite-level metrics
        """
        # Get trading suite component for basic info
        trading_suite = self._components.get("trading_suite")

        # Basic suite information
        suite_id = (
            getattr(trading_suite, "suite_id", "unknown")
            if trading_suite
            else "unknown"
        )
        instrument = (
            getattr(trading_suite, "instrument", "unknown")
            if trading_suite
            else "unknown"
        )
        created_at = (
            getattr(trading_suite, "created_at", time.time())
            if trading_suite
            else time.time()
        )

        if isinstance(created_at, int | float):
            created_at_str = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(created_at))
        else:
            created_at_str = str(created_at)

        uptime_seconds = int(
            time.time()
            - (created_at if isinstance(created_at, int | float) else time.time())
        )

        # Calculate cross-component metrics
        cross_metrics = await self._calculate_cross_metrics(component_stats)

        # Build component status summary
        components: dict[str, ComponentStats] = {}
        for name, stats in component_stats.items():
            if isinstance(stats, dict):
                component_stat: ComponentStats = {
                    "name": name,
                    "status": stats.get("status", "unknown"),
                    "uptime_seconds": int(stats.get("uptime_seconds", 0)),
                    "last_activity": stats.get("last_activity"),
                    "error_count": int(stats.get("error_count", 0)),
                    "memory_usage_mb": float(stats.get("memory_usage_mb", 0.0)),
                }
                # Add optional performance_metrics if present
                perf_metrics = stats.get("performance_metrics")
                if perf_metrics:
                    component_stat["performance_metrics"] = perf_metrics
                components[name] = component_stat

        # Determine overall status
        if not components:
            status = "disconnected"
            connected = False
        elif any(comp.get("status") == "error" for comp in components.values()):
            status = "error"
            connected = False
        elif all(
            comp.get("status") in ["connected", "active"]
            for comp in components.values()
        ):
            status = "active"
            connected = True
        else:
            status = "connecting"
            connected = False

        # Connection status
        realtime_connected = False
        user_hub_connected = False
        market_hub_connected = False

        if trading_suite and hasattr(trading_suite, "data"):
            data_manager = trading_suite.data
            if hasattr(data_manager, "is_connected"):
                try:
                    if asyncio.iscoroutinefunction(data_manager.is_connected):
                        realtime_connected = await data_manager.is_connected()
                    else:
                        realtime_connected = data_manager.is_connected()
                except Exception:
                    pass

        # Features and timeframes
        features_enabled = []
        timeframes = []

        if trading_suite:
            if hasattr(trading_suite, "features"):
                features_enabled = list(trading_suite.features)
            if hasattr(trading_suite, "timeframes"):
                timeframes = list(trading_suite.timeframes)

        # Build the suite statistics
        suite_stats: TradingSuiteStats = {
            "suite_id": suite_id,
            "instrument": instrument,
            "created_at": created_at_str,
            "uptime_seconds": uptime_seconds,
            "status": status,
            "connected": connected,
            "components": components,
            "realtime_connected": realtime_connected,
            "user_hub_connected": user_hub_connected,
            "market_hub_connected": market_hub_connected,
            "total_api_calls": cross_metrics["total_api_calls"],
            "successful_api_calls": cross_metrics["successful_api_calls"],
            "failed_api_calls": cross_metrics["failed_api_calls"],
            "avg_response_time_ms": cross_metrics["avg_response_time_ms"],
            "cache_hit_rate": cross_metrics["cache_hit_rate"],
            "memory_usage_mb": cross_metrics["memory_usage_mb"],
            "active_subscriptions": cross_metrics["active_subscriptions"],
            "message_queue_size": cross_metrics["message_queue_size"],
            "features_enabled": features_enabled,
            "timeframes": timeframes,
            "total_errors": cross_metrics["total_errors"],
            "health_score": cross_metrics["health_score"],
        }

        return suite_stats

    async def _calculate_cross_metrics(
        self, component_stats: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Calculate cross-component metrics from all component statistics.

        Aggregates metrics across all components to provide system-wide
        performance indicators, error totals, combined P&L, and overall
        health scoring.

        Args:
            component_stats: Dictionary of component statistics

        Returns:
            Dictionary with calculated cross-component metrics
        """
        # Initialize aggregated metrics
        total_errors = 0
        total_api_calls = 0
        successful_api_calls = 0
        failed_api_calls = 0
        response_times = []
        cache_hits = 0
        cache_total = 0
        memory_usage_mb = 0.0
        active_subscriptions = 0
        message_queue_size = 0
        health_scores = []

        # Aggregate metrics from all components
        for _, stats in component_stats.items():
            if not isinstance(stats, dict):
                continue

            # Error counts
            total_errors += stats.get("error_count", 0)

            # API call metrics
            if "total_requests" in stats:  # HTTP client stats
                total_api_calls += stats.get("total_requests", 0)
                successful_api_calls += stats.get("successful_requests", 0)
                failed_api_calls += stats.get("failed_requests", 0)

            # Response time metrics
            avg_response = stats.get("avg_response_time_ms", 0)
            if avg_response > 0:
                response_times.append(avg_response)

            # Cache metrics
            if "cache_hits" in stats:
                cache_hits += stats.get("cache_hits", 0)
                cache_total += stats.get("cache_hits", 0) + stats.get("cache_misses", 0)

            # Memory usage
            memory_usage_mb += stats.get("memory_usage_mb", 0.0)

            # Connection metrics
            active_subscriptions += stats.get("subscriptions_active", 0)
            active_subscriptions += stats.get("active_subscriptions", 0)
            message_queue_size += stats.get("message_queue_size", 0)

            # Health scores for aggregation
            if "health_score" in stats:
                health_scores.append(stats["health_score"])

        # Calculate derived metrics
        avg_response_time_ms = (
            sum(response_times) / len(response_times) if response_times else 0.0
        )
        cache_hit_rate = (cache_hits / cache_total) if cache_total > 0 else 0.0

        # Calculate overall health score (weighted average)
        if health_scores:
            health_score = sum(health_scores) / len(health_scores)
        else:
            # Default health calculation based on errors and activity
            base_health = 100.0
            if total_errors > 0 and total_api_calls > 0:
                error_rate = total_errors / max(total_api_calls, 1)
                base_health = max(0, 100 - (error_rate * 100))
            health_score = base_health

        return {
            "total_errors": total_errors,
            "total_api_calls": total_api_calls,
            "successful_api_calls": successful_api_calls,
            "failed_api_calls": failed_api_calls,
            "avg_response_time_ms": round(avg_response_time_ms, 2),
            "cache_hit_rate": round(cache_hit_rate, 4),
            "memory_usage_mb": round(memory_usage_mb, 2),
            "active_subscriptions": active_subscriptions,
            "message_queue_size": message_queue_size,
            "health_score": round(health_score, 1),
        }

    async def _get_minimal_suite_stats(self) -> TradingSuiteStats:
        """
        Get minimal suite statistics for error scenarios.

        Returns basic suite statistics when normal collection fails,
        ensuring the aggregator can always return some useful information.

        Returns:
            TradingSuiteStats with minimal default values
        """
        current_time = time.time()

        return {
            "suite_id": "error",
            "instrument": "unknown",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(current_time)),
            "uptime_seconds": 0,
            "status": "error",
            "connected": False,
            "components": {},
            "realtime_connected": False,
            "user_hub_connected": False,
            "market_hub_connected": False,
            "total_api_calls": 0,
            "successful_api_calls": 0,
            "failed_api_calls": 0,
            "avg_response_time_ms": 0.0,
            "cache_hit_rate": 0.0,
            "memory_usage_mb": 0.0,
            "active_subscriptions": 0,
            "message_queue_size": 0,
            "features_enabled": [],
            "timeframes": [],
            "total_errors": 1,  # Count the collection failure
            "health_score": 0.0,
        }

    def _get_error_stats(self, collection_start: float) -> ComprehensiveStats:
        """
        Get error statistics for comprehensive collection failures.

        Args:
            collection_start: Timestamp when collection started

        Returns:
            ComprehensiveStats with error information
        """
        current_time = time.time()

        # Create minimal suite stats
        suite_stats: TradingSuiteStats = {
            "suite_id": "error",
            "instrument": "unknown",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(current_time)),
            "uptime_seconds": 0,
            "status": "error",
            "connected": False,
            "components": {},
            "realtime_connected": False,
            "user_hub_connected": False,
            "market_hub_connected": False,
            "total_api_calls": 0,
            "successful_api_calls": 0,
            "failed_api_calls": 0,
            "avg_response_time_ms": 0.0,
            "cache_hit_rate": 0.0,
            "memory_usage_mb": 0.0,
            "active_subscriptions": 0,
            "message_queue_size": 0,
            "features_enabled": [],
            "timeframes": [],
            "total_errors": 1,
            "health_score": 0.0,
        }

        return {
            "suite": suite_stats,
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
            "collection_time_ms": round((current_time - collection_start) * 1000, 2),
        }

    async def get_registered_components(self) -> list[str]:
        """
        Get list of registered component names.

        Returns:
            List of component names currently registered
        """
        async with self._component_lock:
            return list(self._components.keys())

    async def get_component_count(self) -> int:
        """
        Get number of registered components.

        Returns:
            Number of components currently registered
        """
        async with self._component_lock:
            return len(self._components)

    async def clear_all_components(self) -> None:
        """
        Remove all registered components.

        Useful for cleanup or testing scenarios.
        """
        async with self._component_lock:
            component_count = len(self._components)
            self._components.clear()
            self._collector = None
            await self.increment("components_cleared", component_count)
            await self.set_status("idle")

    # Compatibility layer for TradingSuite v3.2.x and earlier
    async def aggregate_stats(self, force_refresh: bool = False) -> TradingSuiteStats:
        """
        Compatibility method for TradingSuite integration.

        This method provides backward compatibility with the old StatisticsAggregator
        interface used by TradingSuite. New code should use get_suite_stats().

        Args:
            force_refresh: Force refresh bypassing cache

        Returns:
            TradingSuiteStats: Aggregated statistics from all components
        """
        # Clear cache if force refresh requested
        if force_refresh:
            self._cache.clear()

        return await self.get_suite_stats()

    def __setattr__(self, name: str, value: Any) -> None:
        """
        Compatibility layer for direct component assignment.

        Supports the old pattern where TradingSuite sets components directly:
        aggregator.order_manager = order_manager
        aggregator.data_manager = data_manager
        etc.
        """
        # Handle component assignments for backward compatibility
        component_mapping = {
            "trading_suite": "trading_suite",
            "order_manager": "order_manager",
            "position_manager": "position_manager",
            "data_manager": "realtime_data_manager",
            "orderbook": "orderbook",
            "risk_manager": "risk_manager",
            "client": "client",
            "realtime_client": "realtime_client",
        }

        if name in component_mapping and value is not None:
            # Store components for lazy registration during stats calls
            if not hasattr(self, "_pending_components"):
                self._pending_components = {}
            self._pending_components[component_mapping[name]] = value

        # Always call parent __setattr__
        super().__setattr__(name, value)

    async def _register_all_pending_components(self) -> None:
        """Register all components that were set via direct assignment."""
        if not hasattr(self, "_pending_components"):
            return

        # Make a copy to avoid modification during iteration
        pending_copy = dict(self._pending_components)

        for name, component in pending_copy.items():
            try:
                await self.register_component(name, component)
                # Remove successfully registered component
                self._pending_components.pop(name, None)
            except Exception as e:
                # Log error but don't fail - this is for backward compatibility
                import logging

                logging.getLogger(__name__).warning(
                    f"Failed to auto-register component {name}: {e}"
                )

    async def _register_pending_component(self, name: str, component: Any) -> None:
        """Helper to register components set via direct assignment."""
        try:
            await self.register_component(name, component)
        except Exception as e:
            # Log error but don't fail - this is for backward compatibility
            import logging

            logging.getLogger(__name__).warning(
                f"Failed to auto-register component {name}: {e}"
            )


__all__ = [
    "StatisticsAggregator",
    "ComponentProtocol",
]
