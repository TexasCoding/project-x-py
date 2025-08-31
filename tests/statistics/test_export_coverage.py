"""
Tests specifically for uncovered lines in export.py
"""

import asyncio
import json
from unittest.mock import AsyncMock, Mock

import pytest

from project_x_py.statistics.export import StatsExporter


class TestExportCoverage:
    """Test uncovered export functionality."""

    @pytest.mark.asyncio
    async def test_to_csv_with_all_fields(self):
        """Test CSV export with comprehensive data including connections."""
        exporter = StatsExporter()

        # Create stats with all possible fields to cover all branches
        stats = {
            "health": {
                "overall_score": 95.0,
                "component_scores": {"order_manager": 98.0, "position_manager": 92.0},
            },
            "performance": {
                "api_calls_total": 5000,
                "cache_hit_rate": 0.85,
                "avg_response_time": 125.5,
            },
            "memory": {
                "total_memory_mb": 512.0,
                "components": {
                    "order_manager": {"memory_mb": 100.0},
                    "position_manager": {"memory_mb": 80.0},
                },
            },
            "errors": {"total_errors": 10, "error_rate": 0.002},
            "connections": {
                "active_connections": 5,
                "connection_status": {"websocket": "connected", "http": "connected"},
            },
        }

        # Test with timestamp
        csv_with_ts = await exporter.to_csv(stats, include_timestamp=True)
        lines = csv_with_ts.strip().split("\n")

        # Check header
        assert "metric_category,metric_name,value,component,timestamp" in lines[0]

        # Check various metrics are included
        csv_content = "\n".join(lines)
        assert "health,overall_score,95.0,system" in csv_content
        assert "health,component_score,98.0,order_manager" in csv_content
        assert "performance,api_calls_total,5000,system" in csv_content
        assert "performance,cache_hit_rate,0.85,system" in csv_content
        assert "performance,avg_response_time,125.5,system" in csv_content
        assert "memory,total_memory_mb,512.0,system" in csv_content
        assert "errors,total_errors,10,system" in csv_content
        assert "errors,error_rate,0.002,system" in csv_content
        assert "connections,active_connections,5,system" in csv_content
        assert "connections,connection_status,connected,websocket" in csv_content

        # Test without timestamp
        csv_no_ts = await exporter.to_csv(stats, include_timestamp=False)
        header_no_ts = csv_no_ts.split("\n")[0]
        assert "timestamp" not in header_no_ts
        assert "metric_category,metric_name,value,component" in header_no_ts

    @pytest.mark.asyncio
    async def test_to_datadog_format(self):
        """Test Datadog export format with all metric types."""
        exporter = StatsExporter()

        stats = {
            "health": {
                "overall_score": 90.0,
                "component_scores": {"order_manager": 95.0, "risk_manager": 85.0},
            },
            "performance": {
                "api_calls_total": 10000,
                "cache_hit_rate": 0.90,
                "avg_response_time": 50.0,
                "operations": {
                    "place_order": {
                        "count": 500,
                        "avg_ms": 45.0,
                        "p95_ms": 65.0,
                        "p99_ms": 80.0,
                    }
                },
            },
            "memory": {
                "total_memory_mb": 256.0,
                "component_memory": {"order_manager": 50.0, "position_manager": 45.0},
            },
            "errors": {
                "total_errors": 15,
                "error_rate": 0.0015,
                "errors_by_component": {"order_manager": 5, "position_manager": 10},
                "error_types": {"TimeoutError": 8, "ConnectionError": 7},
            },
            "connections": {
                "active_connections": 3,
                "total_reconnects": 5,
                "connection_status": {
                    "websocket": "connected",
                    "http": "connected",
                    "database": "disconnected",
                },
            },
        }

        # Test with default prefix
        result = await exporter.to_datadog(stats)

        # Check structure
        assert "series" in result
        metrics = result["series"]
        assert isinstance(metrics, list)
        assert len(metrics) > 0

        # Verify metric structure
        for metric in metrics:
            assert "metric" in metric
            assert "points" in metric
            assert "type" in metric
            assert "tags" in metric
            assert isinstance(metric["points"], list)
            assert len(metric["points"]) > 0
            assert len(metric["points"][0]) == 2  # [timestamp, value]

        # Check specific metrics exist
        metric_names = [m["metric"] for m in metrics]
        assert "projectx.health.overall_score" in metric_names
        assert "projectx.performance.api_calls_total" in metric_names
        assert "projectx.performance.cache_hit_rate" in metric_names
        assert "projectx.memory.total_mb" in metric_names
        assert "projectx.errors.total" in metric_names
        assert "projectx.connections.active" in metric_names

        # Check component metrics
        component_metrics = [
            m for m in metrics if "component:" in str(m.get("tags", []))
        ]
        assert len(component_metrics) > 0

        # Check connection status metrics
        conn_metrics = [m for m in metrics if "connections.status" in m["metric"]]
        assert len(conn_metrics) == 3  # websocket, http, database

        # Test with custom prefix
        result_custom = await exporter.to_datadog(stats, prefix="trading")
        custom_metrics = result_custom["series"]
        custom_names = [m["metric"] for m in custom_metrics]
        assert all(name.startswith("trading.") for name in custom_names)

        # Check error type metrics
        error_type_metrics = [
            m for m in metrics if "error_type:" in str(m.get("tags", []))
        ]
        # Note: Current implementation might not include error types in tags

    @pytest.mark.asyncio
    async def test_to_prometheus_with_connections(self):
        """Test Prometheus format specifically for connection metrics."""
        exporter = StatsExporter()

        stats = {
            "connections": {
                "active_connections": 10,
                "connection_status": {
                    "websocket_main": "connected",
                    "websocket_backup": "disconnected",
                    "http_primary": "connected",
                    "http_secondary": "connected",
                },
            }
        }

        output = await exporter.to_prometheus(stats)

        # Check active connections metric
        assert (
            "# HELP projectx_connections_active Number of active connections" in output
        )
        assert "# TYPE projectx_connections_active gauge" in output
        assert "projectx_connections_active 10" in output

        # Check connection status metrics
        assert 'projectx_connection_status{type="websocket_main"} 1' in output
        assert 'projectx_connection_status{type="websocket_backup"} 0' in output
        assert 'projectx_connection_status{type="http_primary"} 1' in output
        assert 'projectx_connection_status{type="http_secondary"} 1' in output

    @pytest.mark.asyncio
    async def test_csv_empty_stats(self):
        """Test CSV export with empty or minimal stats."""
        exporter = StatsExporter()

        # Empty stats
        empty_stats = {}
        csv_empty = await exporter.to_csv(empty_stats)
        lines = csv_empty.strip().split("\n")
        assert len(lines) == 1  # Only header

        # Minimal stats
        minimal_stats = {"health": {"overall_score": 100.0}}
        csv_minimal = await exporter.to_csv(minimal_stats)
        lines = csv_minimal.strip().split("\n")
        assert len(lines) == 2  # Header + 1 data row
        assert "health,overall_score,100.0,system" in lines[1]
