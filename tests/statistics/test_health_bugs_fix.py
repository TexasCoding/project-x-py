"""
Test file to verify that the health.py bugs are fixed.
"""

import pytest
from project_x_py.statistics.health import HealthMonitor


class TestHealthBugFixes:
    """Test that the bugs in health.py are fixed."""

    @pytest.mark.asyncio
    async def test_missing_suite_key_bug_fixed(self):
        """Test that missing 'suite' key doesn't cause KeyError."""
        monitor = HealthMonitor()

        # Test with stats that don't have 'suite' key
        stats_no_suite = {
            "errors": {
                "total_errors": 100,
                "error_rate": 0.1
            },
            "performance": {
                "avg_response_time": 200.0
            },
            "memory": {
                "usage_percent": 60.0
            }
        }

        # Should not crash with KeyError
        health = await monitor.calculate_health(stats_no_suite)
        assert 0 <= health <= 100

        # Test breakdown as well
        breakdown = await monitor.get_health_breakdown(stats_no_suite)
        assert "overall_score" in breakdown
        assert 0 <= breakdown["overall_score"] <= 100

    @pytest.mark.asyncio
    async def test_empty_stats_handling(self):
        """Test that completely empty stats are handled."""
        monitor = HealthMonitor()

        # Completely empty
        empty_stats = {}
        health_empty = await monitor.calculate_health(empty_stats)
        assert health_empty == 100.0  # Should default to healthy

        # Empty nested dicts
        nested_empty = {
            "suite": {},
            "errors": {},
            "performance": {}
        }
        health_nested = await monitor.calculate_health(nested_empty)
        assert 0 <= health_nested <= 100

    @pytest.mark.asyncio
    async def test_partial_suite_data(self):
        """Test stats with suite but no components."""
        monitor = HealthMonitor()

        stats_no_components = {
            "suite": {
                "avg_response_time_ms": 150.0,
                "cache_hit_rate": 0.75
                # No 'components' key
            },
            "errors": {
                "error_rate": 0.02
            }
        }

        # Should handle missing components
        health = await monitor.calculate_health(stats_no_components)
        assert 0 <= health <= 100

        breakdown = await monitor.get_health_breakdown(stats_no_components)
        assert breakdown is not None
