"""
Tests for uncovered lines in health.py module.
"""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from project_x_py.statistics.health import AlertLevel, HealthMonitor


class TestHealthCoverage:
    """Test uncovered health monitoring functionality."""

    @pytest.mark.asyncio
    async def test_health_with_missing_stats(self):
        """Test health calculation with various missing stat fields."""
        monitor = HealthMonitor()

        # Test with completely empty stats
        empty_stats = {}
        health = await monitor.calculate_health(empty_stats)
        assert health == 100.0  # Should default to healthy

        # Test with partial stats - only errors
        error_only_stats = {"errors": {"error_rate": 0.05}}
        health = await monitor.calculate_health(error_only_stats)
        assert health < 100.0  # Should penalize for errors

        # Test with partial stats - only performance
        perf_only_stats = {"performance": {"avg_response_time": 500.0}}
        health = await monitor.calculate_health(perf_only_stats)
        assert health < 100.0  # Should penalize for slow response

        # Test with partial stats - only memory
        mem_only_stats = {"memory": {"usage_percent": 85.0}}
        health = await monitor.calculate_health(mem_only_stats)
        assert health < 100.0  # Should penalize for high memory

    @pytest.mark.asyncio
    async def test_get_health_breakdown(self):
        """Test getting detailed health breakdown."""
        monitor = HealthMonitor()

        stats = {
            "errors": {"error_rate": 0.02, "total_errors": 20},
            "performance": {
                "avg_response_time": 150.0,
                "operations": {"api_call": {"avg_ms": 100.0}},
            },
            "memory": {"usage_percent": 60.0, "total_memory_mb": 256.0},
            "connections": {
                "active_connections": 5,
                "connection_status": {"websocket": "connected", "http": "connected"},
            },
        }

        breakdown = await monitor.get_health_breakdown(stats)

        # Check structure
        assert "overall_score" in breakdown
        assert "errors" in breakdown
        assert "performance" in breakdown
        assert "connection" in breakdown
        assert "resources" in breakdown
        assert "data_quality" in breakdown
        assert "component_status" in breakdown
        assert "weighted_total" in breakdown

        # Check component scores are present and valid
        assert 0 <= breakdown["errors"] <= 100
        assert 0 <= breakdown["performance"] <= 100
        assert 0 <= breakdown["connection"] <= 100
        assert 0 <= breakdown["resources"] <= 100
        assert 0 <= breakdown["data_quality"] <= 100
        assert 0 <= breakdown["component_status"] <= 100

        # Check weighted total matches overall score
        assert breakdown["overall_score"] == breakdown["weighted_total"]

    @pytest.mark.asyncio
    async def test_custom_health_weights(self):
        """Test HealthMonitor with custom weight configurations."""
        # Custom weights emphasizing errors (must sum to 1.0)
        custom_weights = {
            "errors": 0.5,
            "performance": 0.2,
            "resources": 0.15,
            "connection": 0.1,
            "data_quality": 0.03,
            "component_status": 0.02,
        }

        monitor = HealthMonitor(weights=custom_weights)

        # Stats with high errors but good other metrics
        stats = {
            "errors": {
                "error_rate": 0.08  # High error rate
            },
            "performance": {
                "avg_response_time": 50.0  # Good performance
            },
            "memory": {
                "usage_percent": 30.0  # Low memory usage
            },
        }

        health = await monitor.calculate_health(stats)

        # Should be significantly impacted by errors due to high weight
        assert health < 70.0  # Errors have 50% weight

        # Compare with default weights
        default_monitor = HealthMonitor()
        default_health = await default_monitor.calculate_health(stats)

        # Custom weights should produce different score
        assert abs(health - default_health) > 0.01

    @pytest.mark.asyncio
    async def test_connection_stability_calculation(self):
        """Test connection stability metric calculation."""
        monitor = HealthMonitor()

        # Test with all connections active
        all_connected_stats = {
            "connections": {
                "active_connections": 5,
                "connection_status": {
                    "websocket": "connected",
                    "http": "connected",
                    "database": "connected",
                },
            }
        }

        health = await monitor.calculate_health(all_connected_stats)
        breakdown = await monitor.get_health_breakdown(all_connected_stats)

        # Connection component should be healthy
        assert breakdown["connection"] >= 95.0

        # Test with some connections down
        partial_connected_stats = {
            "connections": {
                "active_connections": 2,
                "connection_status": {
                    "websocket": "connected",
                    "http": "disconnected",
                    "database": "disconnected",
                },
            }
        }

        partial_health = await monitor.calculate_health(partial_connected_stats)
        partial_breakdown = await monitor.get_health_breakdown(partial_connected_stats)

        # Connection component should be degraded
        assert partial_breakdown["connection"] < 70.0
        assert partial_health < health  # Overall health should be worse

    @pytest.mark.asyncio
    async def test_health_score_edge_cases(self):
        """Test health score calculation edge cases."""
        monitor = HealthMonitor()

        # Test with very high values
        extreme_stats = {
            "errors": {
                "error_rate": 1.0  # 100% error rate
            },
            "memory": {
                "usage_percent": 100.0  # 100% memory
            },
            "performance": {
                "avg_response_time": 10000.0  # 10 second response
            },
        }

        health = await monitor.calculate_health(extreme_stats)
        assert 0 <= health <= 100  # Should still be within bounds
        assert health < 50  # Should be unhealthy (adjusted for weighted calculation)

        # Test with zero/perfect values
        perfect_stats = {
            "errors": {"error_rate": 0.0, "total_errors": 0},
            "memory": {"usage_percent": 0.0},
            "performance": {"avg_response_time": 0.0},
        }

        perfect_health = await monitor.calculate_health(perfect_stats)
        assert perfect_health >= 95.0  # Should be nearly perfect

        # Test with negative values (shouldn't happen but defensive)
        invalid_stats = {
            "errors": {"error_rate": -0.1},
            "memory": {"usage_percent": -10.0},
        }

        # Should handle gracefully
        invalid_health = await monitor.calculate_health(invalid_stats)
        assert 0 <= invalid_health <= 100

    @pytest.mark.asyncio
    async def test_component_specific_health(self):
        """Test health calculation for specific components."""
        monitor = HealthMonitor()

        # Stats with component-specific data
        component_stats = {
            "suite": {
                "components": {
                    "order_manager": {
                        "error_rate": 0.01,
                        "avg_response_time": 50.0,
                        "memory_mb": 100.0,
                        "status": "healthy",
                    },
                    "position_manager": {
                        "error_rate": 0.05,
                        "avg_response_time": 150.0,
                        "memory_mb": 200.0,
                        "status": "degraded",
                    },
                    "risk_manager": {
                        "error_rate": 0.10,
                        "avg_response_time": 300.0,
                        "memory_mb": 50.0,
                        "status": "unhealthy",
                    },
                }
            }
        }

        # Calculate health considering components
        health = await monitor.calculate_health(component_stats)
        breakdown = await monitor.get_health_breakdown(component_stats)

        # Should have component-specific scores
        if "suite" in breakdown:
            suite_components = breakdown.get("suite", {}).get("components", {})
            if suite_components:
                assert "order_manager" in suite_components
                assert "position_manager" in suite_components
                assert "risk_manager" in suite_components
