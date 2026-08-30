"""
Statistics export module for ProjectX SDK.

Provides export functionality for statistics in multiple formats:
- JSON (human-readable, pretty-printed)
- Prometheus (metrics format for monitoring)
- CSV (tabular data export)
- Datadog (optional, for Datadog metrics)
"""

import csv
import json
import re
from datetime import UTC, datetime
from io import StringIO
from typing import Any, ClassVar, Union

from project_x_py.types.stats_types import ComprehensiveStats


class StatsExporter:
    """Export statistics in multiple formats for monitoring and analysis."""

    # Sensitive fields to sanitize
    SENSITIVE_FIELDS: ClassVar[set[str]] = {
        "account_id",
        "account_number",
        "token",
        "api_key",
        "password",
        "secret",
        "auth_token",
        "session_token",
        "jwt_token",
        "bearer_token",
    }

    def __init__(self, sanitize_sensitive: bool = True):
        """
        Initialize the stats exporter.

        Args:
            sanitize_sensitive: Whether to sanitize sensitive data fields
        """
        self.sanitize_sensitive = sanitize_sensitive

    async def to_json(
        self,
        stats: ComprehensiveStats,
        pretty: bool = False,
        include_timestamp: bool = True,
    ) -> str:
        """
        Export statistics as JSON.

        Args:
            stats: Statistics to export
            pretty: Whether to pretty-print the JSON
            include_timestamp: Whether to include export timestamp

        Returns:
            JSON string representation of stats
        """
        data = self._stats_to_dict(stats)

        if include_timestamp:
            data["export_timestamp"] = (
                datetime.now(UTC).isoformat().replace("+00:00", "Z")
            )

        if self.sanitize_sensitive:
            data = self._sanitize_data(data)

        if pretty:
            return json.dumps(data, indent=2, sort_keys=True, default=str)
        else:
            return json.dumps(data, separators=(",", ":"), default=str)

    async def to_prometheus(
        self, stats: ComprehensiveStats, prefix: str = "projectx"
    ) -> str:
        """
        Export statistics in Prometheus format.

        Args:
            stats: Statistics to export
            prefix: Metric name prefix

        Returns:
            Prometheus format string
        """
        if self.sanitize_sensitive:
            stats = self._sanitize_data(dict(stats))

        lines = []
        timestamp = int(datetime.now(UTC).timestamp() * 1000)

        # Health metrics
        health_stats = stats.get("health")
        if health_stats:
            metric_name = f"{prefix}_health_score"
            lines.append(f"# HELP {metric_name} Overall system health score (0-100)")
            lines.append(f"# TYPE {metric_name} gauge")
            lines.append(f"{metric_name} {health_stats['overall_score']} {timestamp}")

            # Component health
            for component, score in health_stats["component_scores"].items():
                component_clean = self._sanitize_prometheus_label(component)
                lines.append(
                    f'{prefix}_component_health{{component="{component_clean}"}} {score} {timestamp}'
                )

        # Performance metrics
        performance_stats = stats.get("performance")
        if performance_stats:
            # API calls
            if performance_stats.get("api_calls_total"):
                metric_name = f"{prefix}_api_calls_total"
                lines.append(f"# HELP {metric_name} Total number of API calls")
                lines.append(f"# TYPE {metric_name} counter")
                lines.append(
                    f"{metric_name} {performance_stats['api_calls_total']} {timestamp}"
                )

            # Cache metrics
            if performance_stats.get("cache_hit_rate") is not None:
                metric_name = f"{prefix}_cache_hit_rate"
                lines.append(f"# HELP {metric_name} Cache hit rate (0-1)")
                lines.append(f"# TYPE {metric_name} gauge")
                lines.append(
                    f"{metric_name} {performance_stats['cache_hit_rate']} {timestamp}"
                )

            # Response time
            if performance_stats.get("avg_response_time") is not None:
                metric_name = f"{prefix}_response_time_seconds"
                lines.append(f"# HELP {metric_name} Average response time in seconds")
                lines.append(f"# TYPE {metric_name} gauge")
                lines.append(
                    f"{metric_name} {performance_stats['avg_response_time']} {timestamp}"
                )

        # Memory metrics
        memory_stats = stats.get("memory")
        if memory_stats:
            # Total memory
            if memory_stats.get("total_memory_mb"):
                metric_name = f"{prefix}_memory_total_mb"
                lines.append(f"# HELP {metric_name} Total memory usage in MB")
                lines.append(f"# TYPE {metric_name} gauge")
                lines.append(
                    f"{metric_name} {memory_stats['total_memory_mb']} {timestamp}"
                )

            # Component memory
            for component, memory_mb in memory_stats.get(
                "component_memory", {}
            ).items():
                component_clean = self._sanitize_prometheus_label(component)
                lines.append(
                    f'{prefix}_component_memory_mb{{component="{component_clean}"}} {memory_mb} {timestamp}'
                )

        # Error metrics
        error_stats = stats.get("errors")
        if error_stats:
            # Total errors
            if error_stats.get("total_errors"):
                metric_name = f"{prefix}_errors_total"
                lines.append(f"# HELP {metric_name} Total number of errors")
                lines.append(f"# TYPE {metric_name} counter")
                lines.append(f"{metric_name} {error_stats['total_errors']} {timestamp}")

            # Error rate
            if error_stats.get("error_rate") is not None:
                metric_name = f"{prefix}_error_rate"
                lines.append(f"# HELP {metric_name} Error rate (0-1)")
                lines.append(f"# TYPE {metric_name} gauge")
                lines.append(f"{metric_name} {error_stats['error_rate']} {timestamp}")

            # Errors by component
            for component, count in error_stats.get("errors_by_component", {}).items():
                component_clean = self._sanitize_prometheus_label(component)
                lines.append(
                    f'{prefix}_component_errors_total{{component="{component_clean}"}} {count} {timestamp}'
                )

        # Connection metrics
        connection_stats = stats.get("connections")
        if connection_stats:
            # Active connections
            if connection_stats.get("active_connections"):
                metric_name = f"{prefix}_connections_active"
                lines.append(f"# HELP {metric_name} Number of active connections")
                lines.append(f"# TYPE {metric_name} gauge")
                lines.append(
                    f"{metric_name} {connection_stats['active_connections']} {timestamp}"
                )

            # Connection status by type
            for conn_type, status in connection_stats.get(
                "connection_status", {}
            ).items():
                conn_type_clean = self._sanitize_prometheus_label(conn_type)
                status_value = 1 if status == "connected" else 0
                lines.append(
                    f'{prefix}_connection_status{{type="{conn_type_clean}"}} {status_value} {timestamp}'
                )

        return "\n".join(lines) + "\n"

    async def to_csv(
        self, stats: ComprehensiveStats, include_timestamp: bool = True
    ) -> str:
        """
        Export statistics as CSV.

        Args:
            stats: Statistics to export
            include_timestamp: Whether to include export timestamp

        Returns:
            CSV string representation of stats
        """
        if self.sanitize_sensitive:
            stats = self._sanitize_data(dict(stats))

        output = StringIO()
        writer = csv.writer(output)

        # Header
        headers = ["metric_category", "metric_name", "value", "component"]
        if include_timestamp:
            headers.append("timestamp")

        writer.writerow(headers)

        timestamp = (
            datetime.now(UTC).isoformat().replace("+00:00", "Z")
            if include_timestamp
            else None
        )

        # Flatten stats into rows
        rows = []

        # Health metrics
        health_stats = stats.get("health")
        if health_stats:
            rows.append(
                ["health", "overall_score", health_stats["overall_score"], "system"]
            )
            for component, score in health_stats.get("component_scores", {}).items():
                rows.append(["health", "component_score", score, component])

        # Performance metrics
        performance_stats = stats.get("performance")
        if performance_stats:
            if performance_stats.get("api_calls_total"):
                rows.append(
                    [
                        "performance",
                        "api_calls_total",
                        performance_stats["api_calls_total"],
                        "system",
                    ]
                )
            if performance_stats.get("cache_hit_rate") is not None:
                rows.append(
                    [
                        "performance",
                        "cache_hit_rate",
                        performance_stats["cache_hit_rate"],
                        "system",
                    ]
                )
            if performance_stats.get("avg_response_time") is not None:
                rows.append(
                    [
                        "performance",
                        "avg_response_time",
                        performance_stats["avg_response_time"],
                        "system",
                    ]
                )

        # Memory metrics
        memory_stats = stats.get("memory")
        if memory_stats:
            if memory_stats.get("total_memory_mb"):
                rows.append(
                    [
                        "memory",
                        "total_memory_mb",
                        memory_stats["total_memory_mb"],
                        "system",
                    ]
                )
            for component, memory_mb in memory_stats.get(
                "component_memory", {}
            ).items():
                rows.append(["memory", "component_memory_mb", memory_mb, component])

        # Error metrics
        error_stats = stats.get("errors")
        if error_stats:
            if error_stats.get("total_errors"):
                rows.append(
                    ["errors", "total_errors", error_stats["total_errors"], "system"]
                )
            if error_stats.get("error_rate") is not None:
                rows.append(
                    ["errors", "error_rate", error_stats["error_rate"], "system"]
                )
            for component, count in error_stats.get("errors_by_component", {}).items():
                rows.append(["errors", "component_errors", count, component])

        # Connection metrics
        connection_stats = stats.get("connections")
        if connection_stats:
            if connection_stats.get("active_connections"):
                rows.append(
                    [
                        "connections",
                        "active_connections",
                        connection_stats["active_connections"],
                        "system",
                    ]
                )
            for conn_type, status in connection_stats.get(
                "connection_status", {}
            ).items():
                rows.append(["connections", "connection_status", status, conn_type])

        # If no rows were generated from standard stats, handle custom structures
        if not rows:
            # Flatten any custom dictionary structure
            def flatten_dict(
                d: dict[str, Any], parent_key: str = "", sep: str = "_"
            ) -> dict[str, Any]:
                items: list[tuple[str, Any]] = []
                for k, v in d.items():
                    new_key = f"{parent_key}{sep}{k}" if parent_key else k
                    if isinstance(v, dict):
                        items.extend(flatten_dict(v, new_key, sep=sep).items())
                    else:
                        items.append((new_key, v))
                return dict(items)

            flat_stats = flatten_dict(dict(stats))
            for key, value in flat_stats.items():
                # Split the key to get category and name
                parts = key.split("_", 1)
                category = parts[0] if parts else "custom"
                name = parts[1] if len(parts) > 1 else key
                # Try to extract component from key
                component = "system"
                if "order_manager" in key:
                    component = "order_manager"
                elif "position_manager" in key:
                    component = "position_manager"
                elif "realtime" in key:
                    component = "realtime"
                row = [category, name, value, component]
                if include_timestamp:
                    row.append(timestamp)
                rows.append(row)

        # Write rows
        for row in rows:
            if include_timestamp and len(row) == 4:
                row.append(timestamp)
            writer.writerow(row)

        return output.getvalue()

    async def to_datadog(
        self, stats: ComprehensiveStats, prefix: str = "projectx"
    ) -> dict[str, Any]:
        """
        Export statistics for Datadog.

        Args:
            stats: Statistics to export
            prefix: Metric name prefix

        Returns:
            Dictionary formatted for Datadog API
        """
        if self.sanitize_sensitive:
            stats = self._sanitize_data(dict(stats))

        metrics = []
        timestamp = int(datetime.now(UTC).timestamp())

        # Health metrics
        health_stats = stats.get("health")
        if health_stats:
            metrics.append(
                {
                    "metric": f"{prefix}.health.overall_score",
                    "points": [[timestamp, health_stats["overall_score"]]],
                    "type": "gauge",
                    "tags": ["service:projectx"],
                }
            )

            for component, score in health_stats.get("component_scores", {}).items():
                metrics.append(
                    {
                        "metric": f"{prefix}.health.component_score",
                        "points": [[timestamp, score]],
                        "type": "gauge",
                        "tags": ["service:projectx", f"component:{component}"],
                    }
                )

        # Performance metrics
        performance_stats = stats.get("performance")
        if performance_stats:
            if performance_stats.get("api_calls_total"):
                metrics.append(
                    {
                        "metric": f"{prefix}.performance.api_calls_total",
                        "points": [[timestamp, performance_stats["api_calls_total"]]],
                        "type": "count",
                        "tags": ["service:projectx"],
                    }
                )

            if performance_stats.get("cache_hit_rate") is not None:
                metrics.append(
                    {
                        "metric": f"{prefix}.performance.cache_hit_rate",
                        "points": [[timestamp, performance_stats["cache_hit_rate"]]],
                        "type": "gauge",
                        "tags": ["service:projectx"],
                    }
                )

            if performance_stats.get("avg_response_time") is not None:
                metrics.append(
                    {
                        "metric": f"{prefix}.performance.avg_response_time",
                        "points": [[timestamp, performance_stats["avg_response_time"]]],
                        "type": "gauge",
                        "tags": ["service:projectx"],
                    }
                )

        # Memory metrics
        memory_stats = stats.get("memory")
        if memory_stats:
            if memory_stats.get("total_memory_mb"):
                metrics.append(
                    {
                        "metric": f"{prefix}.memory.total_mb",
                        "points": [[timestamp, memory_stats["total_memory_mb"]]],
                        "type": "gauge",
                        "tags": ["service:projectx"],
                    }
                )

            for component, memory_mb in memory_stats.get(
                "component_memory", {}
            ).items():
                metrics.append(
                    {
                        "metric": f"{prefix}.memory.component_mb",
                        "points": [[timestamp, memory_mb]],
                        "type": "gauge",
                        "tags": ["service:projectx", f"component:{component}"],
                    }
                )

        # Error metrics
        error_stats = stats.get("errors")
        if error_stats:
            if error_stats.get("total_errors"):
                metrics.append(
                    {
                        "metric": f"{prefix}.errors.total",
                        "points": [[timestamp, error_stats["total_errors"]]],
                        "type": "count",
                        "tags": ["service:projectx"],
                    }
                )

            if error_stats.get("error_rate") is not None:
                metrics.append(
                    {
                        "metric": f"{prefix}.errors.rate",
                        "points": [[timestamp, error_stats["error_rate"]]],
                        "type": "gauge",
                        "tags": ["service:projectx"],
                    }
                )

            for component, count in error_stats.get("errors_by_component", {}).items():
                metrics.append(
                    {
                        "metric": f"{prefix}.errors.component_total",
                        "points": [[timestamp, count]],
                        "type": "count",
                        "tags": ["service:projectx", f"component:{component}"],
                    }
                )

        # Connection metrics
        connection_stats = stats.get("connections")
        if connection_stats:
            if connection_stats.get("active_connections"):
                metrics.append(
                    {
                        "metric": f"{prefix}.connections.active",
                        "points": [[timestamp, connection_stats["active_connections"]]],
                        "type": "gauge",
                        "tags": ["service:projectx"],
                    }
                )

            for conn_type, status in connection_stats.get(
                "connection_status", {}
            ).items():
                status_value = 1 if status == "connected" else 0
                metrics.append(
                    {
                        "metric": f"{prefix}.connections.status",
                        "points": [[timestamp, status_value]],
                        "type": "gauge",
                        "tags": ["service:projectx", f"type:{conn_type}"],
                    }
                )

        return {"series": metrics}

    async def export(
        self, stats: ComprehensiveStats, export_format: str = "json", **kwargs: Any
    ) -> Union[str, dict[str, Any]]:
        """
        Generic export method.

        Args:
            stats: Statistics to export
            export_format: Export format ('json', 'prometheus', 'csv', 'datadog')
            **kwargs: Format-specific options

        Returns:
            Exported data as string or dict

        Raises:
            ValueError: If format is not supported
        """
        format_lower = export_format.lower()

        if format_lower == "json":
            return await self.to_json(stats, **kwargs)
        elif format_lower == "prometheus":
            return await self.to_prometheus(stats, **kwargs)
        elif format_lower == "csv":
            return await self.to_csv(stats, **kwargs)
        elif format_lower == "datadog":
            return await self.to_datadog(stats, **kwargs)
        else:
            raise ValueError(f"Unsupported export format: {export_format}")

    def _stats_to_dict(self, stats: ComprehensiveStats) -> dict[str, Any]:
        """Convert ComprehensiveStats to dictionary."""
        # Check if this appears to be a structured ComprehensiveStats
        # by looking for standard stats keys
        has_standard_keys = any(
            key in stats
            for key in [
                "health",
                "performance",
                "memory",
                "errors",
                "connections",
                "trading",
            ]
        )

        # If no standard keys found, just return the dict as-is
        # This handles test cases and non-standard data structures
        if not has_standard_keys:
            return dict(stats)

        # Process standard ComprehensiveStats structure
        result: dict[str, Any] = {}

        health_stats = stats.get("health")
        if health_stats:
            result["health"] = {
                "overall_score": health_stats["overall_score"],
                "component_scores": dict(health_stats["component_scores"]),
                "issues": list(health_stats["issues"]),
            }

        performance_stats = stats.get("performance")
        if performance_stats:
            result["performance"] = {
                "api_calls_total": performance_stats["api_calls_total"],
                "cache_hit_rate": performance_stats["cache_hit_rate"],
                "avg_response_time": performance_stats["avg_response_time"],
                "requests_per_second": performance_stats["requests_per_second"],
            }

        memory_stats = stats.get("memory")
        if memory_stats:
            result["memory"] = {
                "total_memory_mb": memory_stats["total_memory_mb"],
                "component_memory": dict(memory_stats["component_memory"]),
                "peak_memory_mb": memory_stats.get("peak_memory_mb"),
            }

        error_stats = stats.get("errors")
        if error_stats:
            result["errors"] = {
                "total_errors": error_stats["total_errors"],
                "error_rate": error_stats["error_rate"],
                "errors_by_component": dict(error_stats["errors_by_component"]),
                "recent_errors": [
                    {
                        "timestamp": error["timestamp"]
                        if error.get("timestamp")
                        else None,
                        "component": error["component"],
                        "error_type": error["error_type"],
                        "message": error["message"],
                        "severity": error["severity"],
                    }
                    for error in error_stats["recent_errors"]
                ],
            }

        connection_stats = stats.get("connections")
        if connection_stats:
            result["connections"] = {
                "active_connections": connection_stats["active_connections"],
                "connection_status": dict(connection_stats["connection_status"]),
                "connection_uptime": dict(connection_stats["connection_uptime"]),
            }

        trading_stats = stats.get("trading")
        if trading_stats:
            result["trading"] = {
                "orders_today": trading_stats["orders_today"],
                "fills_today": trading_stats["fills_today"],
                "active_positions": trading_stats["active_positions"],
                "pnl_today": float(pnl_value)
                if (pnl_value := trading_stats.get("pnl_today")) is not None
                else None,
            }

        # Also preserve any suite data if present
        if "suite" in stats:
            result["suite"] = stats["suite"]

        return result

    def _sanitize_data(self, data: Any) -> Any:
        """Recursively sanitize sensitive data."""
        if isinstance(data, dict):
            return {
                key: "***REDACTED***"
                if key.lower() in self.SENSITIVE_FIELDS
                else self._sanitize_data(value)
                for key, value in data.items()
            }
        elif isinstance(data, list):
            return [self._sanitize_data(item) for item in data]
        else:
            return data

    def _sanitize_prometheus_label(self, label: str) -> str:
        """Sanitize label for Prometheus format."""
        # Replace invalid characters with underscores
        return re.sub(r"[^a-zA-Z0-9_]", "_", label)
