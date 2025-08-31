# mypy: disable-error-code="unreachable"
"""
Health monitoring and scoring system for ProjectX SDK components.

Author: @TexasCoding
Date: 2025-08-21

Overview:
    Provides comprehensive health monitoring with intelligent scoring algorithms
    that evaluate system health based on multiple factors including error rates,
    performance metrics, connection stability, resource usage, and data quality.
    All operations are 100% async with configurable thresholds and alert levels.

Key Features:
    - Multi-factor health scoring (0-100 scale)
    - Weighted health categories with configurable thresholds
    - Actionable health alerts and recommendations
    - Smooth scoring transitions to prevent false alerts
    - Graceful handling of missing statistics
    - Trend analysis for early warning detection
    - Performance-optimized calculations

Health Categories:
    - Error Rates (25% weight): Lower error rates = higher scores
    - Performance (20% weight): Response times, latency, throughput
    - Connection Stability (20% weight): WebSocket connections, reconnections
    - Resource Usage (15% weight): Memory, CPU, API calls
    - Data Quality (15% weight): Validation errors, data gaps
    - Component Status (5% weight): Active, connected, etc.

Alert Levels:
    - HEALTHY (80-100): All systems operating normally
    - WARNING (60-79): Minor issues detected, monitoring recommended
    - DEGRADED (40-59): Significant issues, intervention suggested
    - CRITICAL (0-39): System failure risk, immediate action required

Example Usage:
    ```python
    from project_x_py.statistics.health import HealthMonitor

    monitor = HealthMonitor()

    # Calculate overall health score
    health_score = await monitor.calculate_health(comprehensive_stats)
    print(f"System Health: {health_score}%")

    # Get detailed breakdown
    breakdown = await monitor.get_health_breakdown(comprehensive_stats)
    print(f"Error Score: {breakdown['errors']}")
    print(f"Performance Score: {breakdown['performance']}")

    # Check for alerts
    alerts = await monitor.get_health_alerts(comprehensive_stats)
    for alert in alerts:
        print(f"{alert['level']}: {alert['message']}")
    ```

Configuration:
    Health scoring thresholds are configurable via constructor parameters,
    allowing customization for different deployment environments and
    performance requirements.

See Also:
    - `project_x_py.types.stats_types.ComprehensiveStats`: Input statistics type
    - `project_x_py.statistics.aggregator`: Statistics collection and aggregation
    - `project_x_py.statistics.base`: Base statistics tracking infrastructure
"""

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, NotRequired, TypedDict

from project_x_py.types.stats_types import ComprehensiveStats


class AlertLevel(Enum):
    """Health alert severity levels."""

    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"


class HealthAlert(TypedDict):
    """Health alert with severity and actionable information."""

    level: str  # AlertLevel enum value
    category: str  # Health category that triggered alert
    message: str  # Human-readable alert message
    metric: str  # Specific metric that caused the alert
    current_value: float | int | str  # Current value of the metric
    threshold: float | int  # Threshold that was exceeded
    recommendation: str  # Suggested action to resolve the issue


class HealthBreakdown(TypedDict):
    """Detailed breakdown of health scores by category."""

    errors: float  # Error rate health score (0-100)
    performance: float  # Performance health score (0-100)
    connection: float  # Connection stability health score (0-100)
    resources: float  # Resource usage health score (0-100)
    data_quality: float  # Data quality health score (0-100)
    component_status: float  # Component status health score (0-100)

    # Weighted scores
    weighted_total: float  # Final weighted health score
    overall_score: float  # Alias for weighted_total (backward compatibility)

    # Additional metadata
    missing_categories: NotRequired[list[str]]  # Categories with no data
    calculation_time_ms: NotRequired[float]  # Time taken to calculate


@dataclass
class HealthThresholds:
    """Configurable thresholds for health scoring."""

    # Error rate thresholds (errors per 1000 operations)
    error_rate_excellent: float = 1.0  # < 0.1% error rate
    error_rate_good: float = 5.0  # < 0.5% error rate
    error_rate_warning: float = 20.0  # < 2% error rate
    error_rate_critical: float = 50.0  # >= 5% error rate

    # Performance thresholds (milliseconds)
    response_time_excellent: float = 100.0  # < 100ms
    response_time_good: float = 500.0  # < 500ms
    response_time_warning: float = 2000.0  # < 2s
    response_time_critical: float = 5000.0  # >= 5s

    # Connection stability thresholds
    reconnection_excellent: int = 0  # No reconnections
    reconnection_good: int = 2  # <= 2 reconnections/hour
    reconnection_warning: int = 10  # <= 10 reconnections/hour
    reconnection_critical: int = 30  # > 30 reconnections/hour

    # Resource usage thresholds (percentage)
    memory_usage_excellent: float = 50.0  # < 50% memory usage
    memory_usage_good: float = 70.0  # < 70% memory usage
    memory_usage_warning: float = 85.0  # < 85% memory usage
    memory_usage_critical: float = 95.0  # >= 95% memory usage

    # Data quality thresholds
    validation_error_excellent: float = 0.1  # < 0.01% validation errors
    validation_error_good: float = 1.0  # < 0.1% validation errors
    validation_error_warning: float = 5.0  # < 0.5% validation errors
    validation_error_critical: float = 10.0  # >= 1% validation errors


class HealthMonitor:
    """
    Comprehensive health monitoring with intelligent scoring algorithms.

    Evaluates system health across multiple dimensions including error rates,
    performance metrics, connection stability, resource usage, and data quality.
    Provides actionable insights with configurable thresholds and alert levels.

    Features:
        - Multi-factor health scoring with weighted categories
        - Configurable thresholds for different environments
        - Smooth scoring transitions to prevent alert flapping
        - Graceful handling of missing statistics
        - Performance-optimized async calculations
        - Actionable alerts with specific recommendations
    """

    def __init__(
        self,
        thresholds: HealthThresholds | None = None,
        weights: dict[str, float] | None = None,
    ):
        """
        Initialize the health monitor with configurable thresholds and weights.

        Args:
            thresholds: Custom health thresholds (uses defaults if None)
            weights: Custom category weights (uses defaults if None)
        """
        self.thresholds: HealthThresholds = thresholds or HealthThresholds()

        # Default category weights (must sum to 1.0)
        self.weights = weights or {
            "errors": 0.25,  # Error rates are most critical
            "performance": 0.20,  # Performance impacts user experience
            "connection": 0.20,  # Connection stability is crucial
            "resources": 0.15,  # Resource usage affects sustainability
            "data_quality": 0.15,  # Data quality affects decisions
            "component_status": 0.05,  # Component status is basic indicator
        }

        # Validate weights sum to 1.0
        total_weight = sum(self.weights.values())
        if abs(total_weight - 1.0) > 0.001:
            raise ValueError(f"Health weights must sum to 1.0, got {total_weight}")

        # Cache for expensive calculations
        self._cache: dict[str, tuple[Any, float]] = {}
        self._cache_ttl = 5.0  # 5-second cache

        # Async lock for thread safety
        self._lock = asyncio.Lock()

    async def calculate_health(self, stats: ComprehensiveStats) -> float:
        """
        Calculate overall health score based on comprehensive statistics.

        Args:
            stats: Comprehensive statistics from all components

        Returns:
            Health score between 0-100 (100 = perfect health)
        """
        # Create cache key based on stats content
        # Use a simple hash of the stats dict for caching
        try:
            # Convert stats to JSON string and hash it
            stats_str = json.dumps(stats, sort_keys=True, default=str)
            stats_hash = hashlib.md5(
                stats_str.encode(), usedforsecurity=False
            ).hexdigest()[:8]
            cache_key = f"overall_health_{stats_hash}"
        except (TypeError, ValueError):
            # If we can't serialize stats, don't use cache
            cache_key = None

        # Check cache first if we have a valid key
        if cache_key:
            cached_score = await self._get_cached_value(cache_key)
            if cached_score is not None:
                return float(cached_score)

        # Calculate scores for each category
        error_score = await self._score_errors(stats)
        performance_score = await self._score_performance(stats)
        connection_score = await self._score_connection(stats)
        resources_score = await self._score_resources(stats)
        data_quality_score = await self._score_data_quality(stats)
        component_status_score = await self._score_component_status(stats)

        # Calculate weighted average
        weighted_score = (
            error_score * self.weights["errors"]
            + performance_score * self.weights["performance"]
            + connection_score * self.weights["connection"]
            + resources_score * self.weights["resources"]
            + data_quality_score * self.weights["data_quality"]
            + component_status_score * self.weights["component_status"]
        )

        # Ensure score is within bounds
        final_score = max(0.0, min(100.0, weighted_score))

        # Cache the result if we have a valid cache key
        if cache_key:
            await self._set_cached_value(cache_key, final_score)

        return round(final_score, 1)

    async def get_health_breakdown(self, stats: ComprehensiveStats) -> HealthBreakdown:
        """
        Get detailed breakdown of health scores by category.

        Args:
            stats: Comprehensive statistics from all components

        Returns:
            Detailed health breakdown with scores for each category
        """
        start_time = time.time()

        # Calculate scores for each category
        error_score = await self._score_errors(stats)
        performance_score = await self._score_performance(stats)
        connection_score = await self._score_connection(stats)
        resources_score = await self._score_resources(stats)
        data_quality_score = await self._score_data_quality(stats)
        component_status_score = await self._score_component_status(stats)

        # Calculate weighted total
        weighted_total = (
            error_score * self.weights["errors"]
            + performance_score * self.weights["performance"]
            + connection_score * self.weights["connection"]
            + resources_score * self.weights["resources"]
            + data_quality_score * self.weights["data_quality"]
            + component_status_score * self.weights["component_status"]
        )

        # Track missing categories
        missing_categories = []
        if not self._has_error_data(stats):
            missing_categories.append("errors")
        if not self._has_performance_data(stats):
            missing_categories.append("performance")
        if not self._has_connection_data(stats):
            missing_categories.append("connection")
        if not self._has_resource_data(stats):
            missing_categories.append("resources")
        if not self._has_data_quality_data(stats):
            missing_categories.append("data_quality")

        calculation_time = (time.time() - start_time) * 1000  # Convert to ms

        breakdown: HealthBreakdown = {
            "errors": round(error_score, 1),
            "performance": round(performance_score, 1),
            "connection": round(connection_score, 1),
            "resources": round(resources_score, 1),
            "data_quality": round(data_quality_score, 1),
            "component_status": round(component_status_score, 1),
            "weighted_total": round(weighted_total, 1),
            "overall_score": round(
                weighted_total, 1
            ),  # Alias for backward compatibility
        }

        if missing_categories:
            breakdown["missing_categories"] = missing_categories

        breakdown["calculation_time_ms"] = round(calculation_time, 2)

        return breakdown

    async def get_health_alerts(self, stats: ComprehensiveStats) -> list[HealthAlert]:
        """
        Generate health alerts based on current statistics.

        Args:
            stats: Comprehensive statistics from all components

        Returns:
            List of health alerts with severity levels and recommendations
        """
        alerts: list[HealthAlert] = []

        # Check error rates
        error_alerts = await self._check_error_alerts(stats)
        alerts.extend(error_alerts)

        # Check performance metrics
        performance_alerts = await self._check_performance_alerts(stats)
        alerts.extend(performance_alerts)

        # Check connection stability
        connection_alerts = await self._check_connection_alerts(stats)
        alerts.extend(connection_alerts)

        # Check resource usage
        resource_alerts = await self._check_resource_alerts(stats)
        alerts.extend(resource_alerts)

        # Check data quality
        data_quality_alerts = await self._check_data_quality_alerts(stats)
        alerts.extend(data_quality_alerts)

        # Sort alerts by severity (critical first)
        severity_order = {"CRITICAL": 0, "DEGRADED": 1, "WARNING": 2, "HEALTHY": 3}
        alerts.sort(key=lambda x: severity_order.get(x["level"], 3))

        return alerts

    async def _score_errors(self, stats: ComprehensiveStats) -> float:
        """
        Score error rates across all components.

        Returns:
            Error health score (0-100, higher is better)
        """
        if not self._has_error_data(stats):
            return 100.0  # Assume healthy if no error data

        total_errors = 0
        total_operations = 0

        # Aggregate error counts from all components if available
        if "suite" in stats and "components" in stats["suite"]:
            for _, component_stats in stats["suite"]["components"].items():
                error_count = component_stats.get("error_count", 0)
                total_errors += error_count

                # Estimate total operations based on component type
                if "performance_metrics" in component_stats:
                    perf_metrics = component_stats["performance_metrics"]
                    for _, metrics in perf_metrics.items():
                        if isinstance(metrics, dict) and "count" in metrics:
                            total_operations += metrics["count"]

        # Also check direct errors dict
        if "errors" in stats and stats["errors"] is not None:
            total_errors += stats["errors"].get("total_errors", 0)

        # Add API call statistics if available
        if "http_client" in stats:
            http_stats = stats["http_client"]
            total_operations += http_stats.get("total_requests", 0)
            total_errors += http_stats.get("failed_requests", 0)

        # Calculate error rate per 1000 operations
        if total_operations > 0:
            error_rate = (total_errors / total_operations) * 1000
        elif (
            "errors" in stats
            and stats["errors"] is not None
            and "error_rate" in stats["errors"]
        ):
            # Use provided error rate if no operations to calculate from
            error_rate = stats["errors"]["error_rate"] * 1000  # Convert to per 1000
        else:
            error_rate = 0.0

        # Score based on thresholds
        if error_rate <= self.thresholds.error_rate_excellent:
            return 100.0
        elif error_rate <= self.thresholds.error_rate_good:
            # Linear interpolation between 100 and 80
            ratio = (error_rate - self.thresholds.error_rate_excellent) / (
                self.thresholds.error_rate_good - self.thresholds.error_rate_excellent
            )
            return 100.0 - (ratio * 20.0)
        elif error_rate <= self.thresholds.error_rate_warning:
            # Linear interpolation between 80 and 40
            ratio = (error_rate - self.thresholds.error_rate_good) / (
                self.thresholds.error_rate_warning - self.thresholds.error_rate_good
            )
            return 80.0 - (ratio * 40.0)
        elif error_rate <= self.thresholds.error_rate_critical:
            # Linear interpolation between 40 and 10
            ratio = (error_rate - self.thresholds.error_rate_warning) / (
                self.thresholds.error_rate_critical - self.thresholds.error_rate_warning
            )
            return 40.0 - (ratio * 30.0)
        else:
            return 0.0

    async def _score_performance(self, stats: ComprehensiveStats) -> float:
        """
        Score performance metrics including response times and latency.

        Returns:
            Performance health score (0-100, higher is better)
        """
        if not self._has_performance_data(stats):
            return 100.0  # Assume healthy if no performance data

        avg_response_time = 0.0
        if "suite" in stats:
            avg_response_time = stats["suite"].get("avg_response_time_ms", 0.0)
        elif "performance" in stats and stats["performance"] is not None:
            avg_response_time = (
                stats["performance"].get("avg_response_time", 0.0) or 0.0
            )

        # Also check component-level performance metrics
        total_response_time = (
            avg_response_time if avg_response_time is not None else 0.0
        )
        metric_count = 1 if avg_response_time and avg_response_time > 0 else 0

        if "suite" in stats and "components" in stats["suite"]:
            for component_stats in stats["suite"]["components"].values():
                if "performance_metrics" in component_stats:
                    perf_metrics = component_stats["performance_metrics"]
                    for _, metrics in perf_metrics.items():
                        if isinstance(metrics, dict) and "avg_ms" in metrics:
                            total_response_time += metrics["avg_ms"]
                            metric_count += 1

        if metric_count == 0:
            return 100.0

        avg_performance_time = total_response_time / metric_count

        # Score based on thresholds
        if avg_performance_time <= self.thresholds.response_time_excellent:
            return 100.0
        elif avg_performance_time <= self.thresholds.response_time_good:
            # Linear interpolation between 100 and 80
            ratio = (avg_performance_time - self.thresholds.response_time_excellent) / (
                self.thresholds.response_time_good
                - self.thresholds.response_time_excellent
            )
            return 100.0 - (ratio * 20.0)
        elif avg_performance_time <= self.thresholds.response_time_warning:
            # Linear interpolation between 80 and 40
            ratio = (avg_performance_time - self.thresholds.response_time_good) / (
                self.thresholds.response_time_warning
                - self.thresholds.response_time_good
            )
            return 80.0 - (ratio * 40.0)
        elif avg_performance_time <= self.thresholds.response_time_critical:
            # Linear interpolation between 40 and 10
            ratio = (avg_performance_time - self.thresholds.response_time_warning) / (
                self.thresholds.response_time_critical
                - self.thresholds.response_time_warning
            )
            return 40.0 - (ratio * 30.0)
        else:
            return 0.0

    async def _score_connection(self, stats: ComprehensiveStats) -> float:
        """
        Score connection stability including WebSocket connections and reconnections.

        Returns:
            Connection health score (0-100, higher is better)
        """
        if not self._has_connection_data(stats):
            return 100.0  # Assume healthy if no connection data

        # Check real-time connection status
        realtime_connected = False
        user_hub_connected = False
        market_hub_connected = False

        if "suite" in stats:
            realtime_connected = stats["suite"].get("realtime_connected", False)
            user_hub_connected = stats["suite"].get("user_hub_connected", False)
            market_hub_connected = stats["suite"].get("market_hub_connected", False)
        elif "connections" in stats and stats["connections"] is not None:
            # Use connections dict if available
            conn_status = stats["connections"].get("connection_status", {})
            active_conns = stats["connections"].get("active_connections", 0)
            connected_count = sum(
                1 for status in conn_status.values() if status == "connected"
            )
            if connected_count > 0:
                connection_score = (
                    (connected_count / len(conn_status)) * 100 if conn_status else 100.0
                )
            else:
                connection_score = 50.0 if active_conns > 0 else 0.0
            return connection_score

        # Base score from connection status
        connections_up = sum(
            [realtime_connected, user_hub_connected, market_hub_connected]
        )
        connection_score = (connections_up / 3.0) * 50.0  # 50% for basic connectivity

        # Check reconnection rates if available
        reconnection_penalty = 0.0
        if "realtime" in stats:
            realtime_stats = stats["realtime"]
            reconnection_attempts = realtime_stats.get("reconnection_attempts", 0)
            uptime_hours = realtime_stats.get("connection_uptime_seconds", 0) / 3600

            if uptime_hours > 0:
                reconnections_per_hour = reconnection_attempts / uptime_hours

                if reconnections_per_hour <= self.thresholds.reconnection_excellent:
                    reconnection_penalty = 0.0
                elif reconnections_per_hour <= self.thresholds.reconnection_good:
                    ratio = (
                        reconnections_per_hour - self.thresholds.reconnection_excellent
                    ) / (
                        self.thresholds.reconnection_good
                        - self.thresholds.reconnection_excellent
                    )
                    reconnection_penalty = ratio * 10.0
                elif reconnections_per_hour <= self.thresholds.reconnection_warning:
                    ratio = (
                        reconnections_per_hour - self.thresholds.reconnection_good
                    ) / (
                        self.thresholds.reconnection_warning
                        - self.thresholds.reconnection_good
                    )
                    reconnection_penalty = 10.0 + (ratio * 20.0)
                else:
                    reconnection_penalty = 40.0

        # Stability score (remaining 50%)
        stability_score = max(0.0, 50.0 - reconnection_penalty)

        return min(100.0, connection_score + stability_score)

    async def _score_resources(self, stats: ComprehensiveStats) -> float:
        """
        Score resource usage including memory and API calls.

        Returns:
            Resource usage health score (0-100, higher is better)
        """
        if not self._has_resource_data(stats):
            return 100.0  # Assume healthy if no resource data

        # Memory usage scoring (primary resource metric)
        memory_score = 100.0
        if "memory" in stats:
            memory_stats = stats["memory"]
            # Support both 'memory_usage_percent' and 'usage_percent' for backward compatibility
            memory_usage_percent = memory_stats.get(
                "memory_usage_percent", memory_stats.get("usage_percent", 0.0)
            )

            if memory_usage_percent <= self.thresholds.memory_usage_excellent:  # type: ignore[operator]
                memory_score = 100.0
            elif memory_usage_percent <= self.thresholds.memory_usage_good:  # type: ignore[operator]
                ratio = (
                    memory_usage_percent - self.thresholds.memory_usage_excellent  # type: ignore[operator]
                ) / (
                    self.thresholds.memory_usage_good
                    - self.thresholds.memory_usage_excellent
                )
                memory_score = 100.0 - (ratio * 20.0)
            elif memory_usage_percent <= self.thresholds.memory_usage_warning:  # type: ignore[operator]
                ratio = (memory_usage_percent - self.thresholds.memory_usage_good) / (  # type: ignore[operator]
                    self.thresholds.memory_usage_warning
                    - self.thresholds.memory_usage_good
                )
                memory_score = 80.0 - (ratio * 40.0)
            elif memory_usage_percent <= self.thresholds.memory_usage_critical:  # type: ignore[operator]
                ratio = (
                    memory_usage_percent - self.thresholds.memory_usage_warning  # type: ignore[operator]
                ) / (
                    self.thresholds.memory_usage_critical
                    - self.thresholds.memory_usage_warning
                )
                memory_score = 40.0 - (ratio * 30.0)
            else:
                memory_score = 0.0

        # API call efficiency (secondary metric)
        api_efficiency_score = 100.0
        cache_hit_rate = 1.0
        if "suite" in stats:
            cache_hit_rate = stats["suite"].get("cache_hit_rate", 1.0)
        elif "performance" in stats and stats["performance"] is not None:
            cache_hit_rate = stats["performance"].get("cache_hit_rate", 1.0)
        if cache_hit_rate < 0.5:  # Less than 50% cache hit rate
            api_efficiency_score = cache_hit_rate * 100.0

        # Combine scores (memory 70%, API efficiency 30%)
        return (memory_score * 0.7) + (api_efficiency_score * 0.3)

    async def _score_data_quality(self, stats: ComprehensiveStats) -> float:
        """
        Score data quality including validation errors and data gaps.

        Returns:
            Data quality health score (0-100, higher is better)
        """
        if not self._has_data_quality_data(stats):
            return 100.0  # Assume healthy if no data quality data

        total_validation_errors = 0
        total_data_points = 0

        # Check data manager statistics
        if "data_manager" in stats:
            data_stats = stats["data_manager"]
            validation_errors = data_stats.get("data_validation_errors", 0)
            total_bars = data_stats.get("bars_processed", 0)
            total_ticks = data_stats.get("ticks_processed", 0)

            total_validation_errors += validation_errors
            total_data_points += total_bars + total_ticks

        # Check orderbook statistics
        if "orderbook" in stats:
            orderbook_stats = stats["orderbook"]
            invalid_updates = orderbook_stats.get("invalid_updates", 0)
            duplicate_updates = orderbook_stats.get("duplicate_updates", 0)
            total_trades = orderbook_stats.get("trades_processed", 0)

            total_validation_errors += invalid_updates + duplicate_updates
            total_data_points += total_trades

        # Calculate validation error rate per 1000 data points
        if total_data_points > 0:
            validation_error_rate = (total_validation_errors / total_data_points) * 1000
        else:
            validation_error_rate = 0.0

        # Score based on thresholds
        if validation_error_rate <= self.thresholds.validation_error_excellent:
            return 100.0
        elif validation_error_rate <= self.thresholds.validation_error_good:
            ratio = (
                validation_error_rate - self.thresholds.validation_error_excellent
            ) / (
                self.thresholds.validation_error_good
                - self.thresholds.validation_error_excellent
            )
            return 100.0 - (ratio * 20.0)
        elif validation_error_rate <= self.thresholds.validation_error_warning:
            ratio = (validation_error_rate - self.thresholds.validation_error_good) / (
                self.thresholds.validation_error_warning
                - self.thresholds.validation_error_good
            )
            return 80.0 - (ratio * 40.0)
        elif validation_error_rate <= self.thresholds.validation_error_critical:
            ratio = (
                validation_error_rate - self.thresholds.validation_error_warning
            ) / (
                self.thresholds.validation_error_critical
                - self.thresholds.validation_error_warning
            )
            return 40.0 - (ratio * 30.0)
        else:
            return 0.0

    async def _score_component_status(self, stats: ComprehensiveStats) -> float:
        """
        Score component status (active, connected, etc.).

        Returns:
            Component status health score (0-100, higher is better)
        """
        total_components = 0
        if "suite" in stats and "components" in stats["suite"]:
            total_components = len(stats["suite"]["components"])

        if total_components == 0:
            return 100.0

        healthy_components = 0.0
        if "suite" in stats and "components" in stats["suite"]:
            for component_stats in stats["suite"]["components"].values():
                status = component_stats.get("status", "unknown")
                if status in ["connected", "active"]:
                    healthy_components += 1
                elif status in ["initializing"]:
                    healthy_components += 0.7  # Partial credit for initializing

        return (healthy_components / total_components) * 100.0

    # Alert generation methods

    async def _check_error_alerts(self, stats: ComprehensiveStats) -> list[HealthAlert]:
        """Generate alerts for error rates."""
        alerts: list[HealthAlert] = []

        if not self._has_error_data(stats):
            return alerts

        # Calculate total error rate
        total_errors = 0
        if "suite" in stats and "components" in stats["suite"]:
            total_errors = sum(
                comp_stats.get("error_count", 0)
                for comp_stats in stats["suite"]["components"].values()
            )
        elif "errors" in stats:
            total_errors = stats["errors"].get("total_errors", 0)

        total_operations = 0
        if "suite" in stats and "components" in stats["suite"]:
            for component_stats in stats["suite"]["components"].values():
                if "performance_metrics" in component_stats:
                    perf_metrics = component_stats["performance_metrics"]
                    for _, metrics in perf_metrics.items():
                        if isinstance(metrics, dict) and "count" in metrics:
                            total_operations += metrics["count"]

        if total_operations > 0:
            error_rate = (total_errors / total_operations) * 1000

            if error_rate >= self.thresholds.error_rate_critical:
                alerts.append(
                    {
                        "level": AlertLevel.CRITICAL.value,
                        "category": "errors",
                        "message": f"Critical error rate detected: {error_rate:.1f} errors per 1000 operations",
                        "metric": "error_rate",
                        "current_value": error_rate,
                        "threshold": self.thresholds.error_rate_critical,
                        "recommendation": "Investigate error sources immediately and implement fixes",
                    }
                )
            elif error_rate >= self.thresholds.error_rate_warning:
                alerts.append(
                    {
                        "level": AlertLevel.DEGRADED.value,
                        "category": "errors",
                        "message": f"Elevated error rate: {error_rate:.1f} errors per 1000 operations",
                        "metric": "error_rate",
                        "current_value": error_rate,
                        "threshold": self.thresholds.error_rate_warning,
                        "recommendation": "Monitor error patterns and consider implementing error handling improvements",
                    }
                )
            elif error_rate >= self.thresholds.error_rate_good:
                alerts.append(
                    {
                        "level": AlertLevel.WARNING.value,
                        "category": "errors",
                        "message": f"Increased error rate: {error_rate:.1f} errors per 1000 operations",
                        "metric": "error_rate",
                        "current_value": error_rate,
                        "threshold": self.thresholds.error_rate_good,
                        "recommendation": "Review recent changes and monitor error trends",
                    }
                )

        return alerts

    async def _check_performance_alerts(
        self, stats: ComprehensiveStats
    ) -> list[HealthAlert]:
        """Generate alerts for performance metrics."""
        alerts: list[HealthAlert] = []

        if not self._has_performance_data(stats):
            return alerts

        # Get average response time from suite or performance dict
        avg_response_time = 0.0
        if "suite" in stats:
            avg_response_time = stats["suite"].get("avg_response_time_ms", 0.0)
        elif "performance" in stats and stats["performance"] is not None:
            avg_response_time = stats["performance"].get("avg_response_time", 0.0)

        if avg_response_time >= self.thresholds.response_time_critical:
            alerts.append(
                {
                    "level": AlertLevel.CRITICAL.value,
                    "category": "performance",
                    "message": f"Critical response time: {avg_response_time:.0f}ms average",
                    "metric": "avg_response_time_ms",
                    "current_value": avg_response_time,
                    "threshold": self.thresholds.response_time_critical,
                    "recommendation": "Investigate performance bottlenecks and optimize critical paths",
                }
            )
        elif avg_response_time >= self.thresholds.response_time_warning:
            alerts.append(
                {
                    "level": AlertLevel.DEGRADED.value,
                    "category": "performance",
                    "message": f"Slow response time: {avg_response_time:.0f}ms average",
                    "metric": "avg_response_time_ms",
                    "current_value": avg_response_time,
                    "threshold": self.thresholds.response_time_warning,
                    "recommendation": "Profile application performance and consider caching optimizations",
                }
            )
        elif avg_response_time >= self.thresholds.response_time_good:
            alerts.append(
                {
                    "level": AlertLevel.WARNING.value,
                    "category": "performance",
                    "message": f"Elevated response time: {avg_response_time:.0f}ms average",
                    "metric": "avg_response_time_ms",
                    "current_value": avg_response_time,
                    "threshold": self.thresholds.response_time_good,
                    "recommendation": "Monitor performance trends and review recent deployments",
                }
            )

        return alerts

    async def _check_connection_alerts(
        self, stats: ComprehensiveStats
    ) -> list[HealthAlert]:
        """Generate alerts for connection stability."""
        alerts: list[HealthAlert] = []

        # Check basic connectivity
        realtime_connected = False
        user_hub_connected = False
        market_hub_connected = False

        if "suite" in stats:
            realtime_connected = stats["suite"].get("realtime_connected", False)
            user_hub_connected = stats["suite"].get("user_hub_connected", False)
            market_hub_connected = stats["suite"].get("market_hub_connected", False)
        elif "connections" in stats and stats["connections"] is not None:
            # Use connections dict if available
            conn_status = stats["connections"].get("connection_status", {})
            active_conns = stats["connections"].get("active_connections", 0)
            connected_count = sum(
                1 for status in conn_status.values() if status == "connected"
            )
            # Generate alerts based on connection count
            if connected_count == 0 and active_conns == 0:
                alerts.append(
                    {
                        "level": AlertLevel.CRITICAL.value,
                        "category": "connection",
                        "message": "No active connections",
                        "metric": "active_connections",
                        "current_value": 0,
                        "threshold": 1,
                        "recommendation": "Check network connectivity and service status",
                    }
                )
            elif connected_count < len(conn_status) // 2:  # Less than half connected
                alerts.append(
                    {
                        "level": AlertLevel.DEGRADED.value,
                        "category": "connection",
                        "message": f"Only {connected_count}/{len(conn_status)} connections active",
                        "metric": "connected_count",
                        "current_value": connected_count,
                        "threshold": len(conn_status) // 2,
                        "recommendation": "Check connectivity for disconnected services",
                    }
                )
            return alerts

        if not realtime_connected or not user_hub_connected or not market_hub_connected:
            disconnected_hubs = []
            if not realtime_connected:
                disconnected_hubs.append("realtime")
            if not user_hub_connected:
                disconnected_hubs.append("user_hub")
            if not market_hub_connected:
                disconnected_hubs.append("market_hub")

            alerts.append(
                {
                    "level": AlertLevel.CRITICAL.value,
                    "category": "connection",
                    "message": f"Connection failure: {', '.join(disconnected_hubs)} disconnected",
                    "metric": "connection_status",
                    "current_value": f"{len(disconnected_hubs)} disconnected",
                    "threshold": 0,
                    "recommendation": "Check network connectivity and authentication credentials",
                }
            )

        # Check reconnection rates
        if "realtime" in stats:
            realtime_stats = stats["realtime"]
            reconnection_attempts = realtime_stats.get("reconnection_attempts", 0)
            uptime_hours = realtime_stats.get("connection_uptime_seconds", 0) / 3600

            if uptime_hours > 0:
                reconnections_per_hour = reconnection_attempts / uptime_hours

                if reconnections_per_hour >= self.thresholds.reconnection_critical:
                    alerts.append(
                        {
                            "level": AlertLevel.CRITICAL.value,
                            "category": "connection",
                            "message": f"Excessive reconnections: {reconnections_per_hour:.1f} per hour",
                            "metric": "reconnections_per_hour",
                            "current_value": reconnections_per_hour,
                            "threshold": self.thresholds.reconnection_critical,
                            "recommendation": "Investigate network stability and connection handling",
                        }
                    )
                elif reconnections_per_hour >= self.thresholds.reconnection_warning:
                    alerts.append(
                        {
                            "level": AlertLevel.DEGRADED.value,
                            "category": "connection",
                            "message": f"Frequent reconnections: {reconnections_per_hour:.1f} per hour",
                            "metric": "reconnections_per_hour",
                            "current_value": reconnections_per_hour,
                            "threshold": self.thresholds.reconnection_warning,
                            "recommendation": "Monitor network conditions and consider connection timeout adjustments",
                        }
                    )

        return alerts

    async def _check_resource_alerts(
        self, stats: ComprehensiveStats
    ) -> list[HealthAlert]:
        """Generate alerts for resource usage."""
        alerts: list[HealthAlert] = []

        if "memory" in stats:
            memory_stats = stats["memory"]
            # Support both field names for backward compatibility
            memory_usage_percent = memory_stats.get(
                "memory_usage_percent", memory_stats.get("usage_percent", 0.0)
            )

            if memory_usage_percent >= self.thresholds.memory_usage_critical:  # type: ignore[operator]
                alerts.append(
                    {
                        "level": AlertLevel.CRITICAL.value,
                        "category": "resources",
                        "message": f"Critical memory usage: {memory_usage_percent:.1f}%",
                        "metric": "memory_usage_percent",
                        "current_value": memory_usage_percent,  # type: ignore[typeddict-item]
                        "threshold": self.thresholds.memory_usage_critical,
                        "recommendation": "Immediately review memory leaks and restart if necessary",
                    }
                )
            elif memory_usage_percent >= self.thresholds.memory_usage_warning:  # type: ignore[operator]
                alerts.append(
                    {
                        "level": AlertLevel.DEGRADED.value,
                        "category": "resources",
                        "message": f"High memory usage: {memory_usage_percent:.1f}%",
                        "metric": "memory_usage_percent",
                        "current_value": memory_usage_percent,  # type: ignore[typeddict-item]
                        "threshold": self.thresholds.memory_usage_warning,
                        "recommendation": "Monitor memory trends and consider implementing cleanup routines",
                    }
                )
            elif memory_usage_percent >= self.thresholds.memory_usage_good:  # type: ignore[operator]
                alerts.append(
                    {
                        "level": AlertLevel.WARNING.value,
                        "category": "resources",
                        "message": f"Elevated memory usage: {memory_usage_percent:.1f}%",
                        "metric": "memory_usage_percent",
                        "current_value": memory_usage_percent,  # type: ignore[typeddict-item]
                        "threshold": self.thresholds.memory_usage_good,
                        "recommendation": "Review memory usage patterns and optimize data structures",
                    }
                )

        return alerts

    async def _check_data_quality_alerts(
        self, stats: ComprehensiveStats
    ) -> list[HealthAlert]:
        """Generate alerts for data quality issues."""
        alerts: list[HealthAlert] = []

        # Check data validation errors
        if "data_manager" in stats:
            data_stats = stats["data_manager"]
            validation_errors = data_stats.get("data_validation_errors", 0)
            total_data_points = data_stats.get("bars_processed", 0) + data_stats.get(
                "ticks_processed", 0
            )

            if total_data_points > 0:
                validation_error_rate = (validation_errors / total_data_points) * 1000

                if validation_error_rate >= self.thresholds.validation_error_critical:
                    alerts.append(
                        {
                            "level": AlertLevel.CRITICAL.value,
                            "category": "data_quality",
                            "message": f"Critical data validation error rate: {validation_error_rate:.1f} per 1000 data points",
                            "metric": "validation_error_rate",
                            "current_value": validation_error_rate,
                            "threshold": self.thresholds.validation_error_critical,
                            "recommendation": "Investigate data sources and validation logic immediately",
                        }
                    )
                elif validation_error_rate >= self.thresholds.validation_error_warning:
                    alerts.append(
                        {
                            "level": AlertLevel.DEGRADED.value,
                            "category": "data_quality",
                            "message": f"High data validation error rate: {validation_error_rate:.1f} per 1000 data points",
                            "metric": "validation_error_rate",
                            "current_value": validation_error_rate,
                            "threshold": self.thresholds.validation_error_warning,
                            "recommendation": "Review data validation rules and data source quality",
                        }
                    )

        return alerts

    # Helper methods for checking data availability

    def _has_error_data(self, stats: ComprehensiveStats) -> bool:
        """Check if error data is available."""
        # Check if suite and components exist
        if "suite" not in stats or "components" not in stats.get("suite", {}):
            # Fall back to checking for errors dict (and that it's not None)
            return "errors" in stats and stats["errors"] is not None
        return any(
            comp_stats.get("error_count", 0) > 0 or "performance_metrics" in comp_stats
            for comp_stats in stats["suite"]["components"].values()
        )

    def _has_performance_data(self, stats: ComprehensiveStats) -> bool:
        """Check if performance data is available."""
        if "suite" in stats:
            return stats["suite"].get("avg_response_time_ms", 0.0) > 0 or any(
                "performance_metrics" in comp_stats
                for comp_stats in stats.get("suite", {}).get("components", {}).values()
            )
        # Fall back to checking for performance dict (and that it has valid data)
        if "performance" in stats and stats["performance"] is not None:
            # Check if there's actual numeric data
            avg_response_time = stats["performance"].get("avg_response_time")
            return avg_response_time is not None and avg_response_time != 0
        return False

    def _has_connection_data(self, stats: ComprehensiveStats) -> bool:
        """Check if connection data is available."""
        if "suite" in stats:
            suite_data = stats["suite"]
            return (
                "realtime_connected" in suite_data
                or "user_hub_connected" in suite_data
                or "market_hub_connected" in suite_data
                or "realtime" in stats
            )
        # Fall back to checking for connections dict
        return "connections" in stats

    def _has_resource_data(self, stats: ComprehensiveStats) -> bool:
        """Check if resource data is available."""
        if "suite" in stats:
            return (
                "memory" in stats
                or stats["suite"].get("memory_usage_mb", 0.0) > 0
                or "cache_hit_rate" in stats["suite"]
            )
        # Fall back to checking for memory dict
        return "memory" in stats

    def _has_data_quality_data(self, stats: ComprehensiveStats) -> bool:
        """Check if data quality data is available."""
        return "data_manager" in stats or "orderbook" in stats

    # Cache management methods

    async def _get_cached_value(self, cache_key: str) -> Any | None:
        """Get cached value if not expired."""
        async with self._lock:
            if cache_key in self._cache:
                value, timestamp = self._cache[cache_key]
                if time.time() - timestamp < self._cache_ttl:
                    return value
            return None

    async def _set_cached_value(self, cache_key: str, value: Any) -> None:
        """Set cached value with current timestamp."""
        async with self._lock:
            self._cache[cache_key] = (value, time.time())


__all__ = [
    "HealthMonitor",
    "HealthThresholds",
    "HealthAlert",
    "HealthBreakdown",
    "AlertLevel",
]
