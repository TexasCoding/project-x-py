"""
Tests for dynamic resource limits in realtime data manager.

Author: @TexasCoding
Date: 2025-08-22
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from project_x_py.realtime_data_manager.dynamic_resource_limits import (
    PSUTIL_AVAILABLE,
    DynamicResourceMixin,
    ResourceConfig,
    ResourceLimits,
    SystemResources,
)


class TestResourceLimits:
    """Test ResourceLimits dataclass."""

    def test_resource_limits_creation(self):
        """Test ResourceLimits dataclass creation."""
        limits = ResourceLimits(
            max_bars_per_timeframe=1000,
            tick_buffer_size=500,
            max_concurrent_tasks=4,
            cache_size_limit=200,
            memory_limit_mb=100.0,
            memory_pressure=0.5,
            cpu_pressure=0.3,
            scaling_reason="normal",
        )

        assert limits.max_bars_per_timeframe == 1000
        assert limits.tick_buffer_size == 500
        assert limits.max_concurrent_tasks == 4
        assert limits.cache_size_limit == 200
        assert limits.memory_limit_mb == 100.0
        assert limits.memory_pressure == 0.5
        assert limits.cpu_pressure == 0.3
        assert limits.scaling_reason == "normal"


class TestSystemResources:
    """Test SystemResources dataclass."""

    def test_system_resources_creation(self):
        """Test SystemResources dataclass creation."""
        resources = SystemResources(
            total_memory_mb=8192.0,
            available_memory_mb=4096.0,
            used_memory_mb=4096.0,
            memory_percent=50.0,
            cpu_count=8,
            cpu_percent=25.0,
            process_memory_mb=128.0,
            process_cpu_percent=5.0,
        )

        assert resources.total_memory_mb == 8192.0
        assert resources.available_memory_mb == 4096.0
        assert resources.used_memory_mb == 4096.0
        assert resources.memory_percent == 50.0
        assert resources.cpu_count == 8
        assert resources.cpu_percent == 25.0
        assert resources.process_memory_mb == 128.0
        assert resources.process_cpu_percent == 5.0


class TestResourceConfig:
    """Test ResourceConfig dataclass."""

    def test_resource_config_defaults(self):
        """Test ResourceConfig default values."""
        config = ResourceConfig()

        assert config.memory_target_percent == 15.0
        assert config.memory_pressure_threshold == 0.8
        assert config.memory_scale_down_factor == 0.5
        assert config.memory_scale_up_factor == 1.5
        assert config.cpu_pressure_threshold == 0.8
        assert config.cpu_scale_down_factor == 0.7
        assert config.min_buffer_size == 100
        assert config.max_buffer_size == 50000
        assert config.monitoring_interval == 30.0


class MockDynamicResourceMixin(DynamicResourceMixin):
    """Mock DynamicResourceMixin for testing."""

    def __init__(self):
        # Mock required attributes
        self.logger = MagicMock()
        self.max_bars_per_timeframe = 1000
        self.tick_buffer_size = 1000
        self.memory_stats = {}
        self.data_lock = AsyncMock()
        self.is_running = True

        # Initialize the mixin
        super().__init__()

    def _create_task(self, coro, name=None, persistent=False):
        """Mock task creation."""
        return asyncio.create_task(coro)


class TestDynamicResourceMixin:
    """Test DynamicResourceMixin functionality."""

    @pytest.fixture
    def mixin(self):
        """Create a mock DynamicResourceMixin instance."""
        return MockDynamicResourceMixin()

    def test_mixin_initialization(self, mixin):
        """Test mixin initialization."""
        assert hasattr(mixin, "_resource_config")
        assert isinstance(mixin._resource_config, ResourceConfig)
        assert mixin._current_limits is None
        assert mixin._system_resources is None
        assert len(mixin._memory_pressure_history) == 0
        assert len(mixin._cpu_pressure_history) == 0

    def test_configure_dynamic_resources(self, mixin):
        """Test dynamic resource configuration."""
        mixin.configure_dynamic_resources(
            memory_target_percent=20.0,
            memory_pressure_threshold=0.9,
            cpu_pressure_threshold=0.75,
            monitoring_interval=60.0,
        )

        assert mixin._resource_config.memory_target_percent == 20.0
        assert mixin._resource_config.memory_pressure_threshold == 0.9
        assert mixin._resource_config.cpu_pressure_threshold == 0.75
        assert mixin._resource_config.monitoring_interval == 60.0

    def test_configure_with_bounds(self, mixin):
        """Test configuration with boundary validation."""
        # Test memory target bounds
        mixin.configure_dynamic_resources(memory_target_percent=0.5)  # Too low
        assert mixin._resource_config.memory_target_percent == 1.0

        mixin.configure_dynamic_resources(memory_target_percent=75.0)  # Too high
        assert mixin._resource_config.memory_target_percent == 50.0

        # Test pressure threshold bounds
        mixin.configure_dynamic_resources(memory_pressure_threshold=0.05)  # Too low
        assert mixin._resource_config.memory_pressure_threshold == 0.1

        mixin.configure_dynamic_resources(memory_pressure_threshold=1.5)  # Too high
        assert mixin._resource_config.memory_pressure_threshold == 1.0

    @pytest.mark.asyncio
    async def test_get_fallback_resources(self, mixin):
        """Test fallback resource information when psutil unavailable."""
        resources = await mixin._get_fallback_resources()

        assert isinstance(resources, SystemResources)
        assert resources.total_memory_mb == 8192  # 8GB estimate
        assert resources.available_memory_mb == 4096  # 50% available
        assert resources.cpu_count >= 1
        assert 0 <= resources.memory_percent <= 100
        assert 0 <= resources.cpu_percent <= 100

    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil not available")
    @pytest.mark.asyncio
    async def test_get_system_resources_with_psutil(self, mixin):
        """Test system resource gathering with psutil."""
        resources = await mixin._get_system_resources()

        assert isinstance(resources, SystemResources)
        assert resources.total_memory_mb > 0
        assert resources.available_memory_mb > 0
        assert resources.cpu_count > 0
        assert 0 <= resources.memory_percent <= 100
        assert resources.cpu_percent >= 0

    def test_calculate_memory_pressure(self, mixin):
        """Test memory pressure calculation."""
        resources = SystemResources(
            total_memory_mb=8192,
            available_memory_mb=2048,
            used_memory_mb=6144,
            memory_percent=75.0,
            cpu_count=4,
            cpu_percent=50.0,
            process_memory_mb=512,
            process_cpu_percent=10.0,
        )

        pressure = mixin._calculate_memory_pressure(resources)

        # System pressure: 75% = 0.75
        # Process pressure: 512/2048 = 0.25
        # Combined: (0.75 * 0.7) + (0.25 * 0.3) = 0.525 + 0.075 = 0.6
        expected_pressure = 0.6
        assert abs(pressure - expected_pressure) < 0.01

    def test_calculate_cpu_pressure(self, mixin):
        """Test CPU pressure calculation."""
        resources = SystemResources(
            total_memory_mb=8192,
            available_memory_mb=4096,
            used_memory_mb=4096,
            memory_percent=50.0,
            cpu_count=4,
            cpu_percent=80.0,
            process_memory_mb=256,
            process_cpu_percent=20.0,
        )

        pressure = mixin._calculate_cpu_pressure(resources)

        # System pressure: 80% = 0.8
        # Process pressure: 20% = 0.2, scaled by 0.5 = 0.1
        # Combined: max(0.8, 0.1) = 0.8
        expected_pressure = 0.8
        assert abs(pressure - expected_pressure) < 0.01

    def test_calculate_adaptive_limits_normal(self, mixin):
        """Test adaptive limits calculation under normal conditions."""
        resources = SystemResources(
            total_memory_mb=8192,
            available_memory_mb=4096,
            used_memory_mb=4096,
            memory_percent=50.0,
            cpu_count=4,
            cpu_percent=25.0,
            process_memory_mb=256,
            process_cpu_percent=5.0,
        )

        memory_pressure = 0.4  # Normal
        cpu_pressure = 0.3  # Normal

        limits = mixin._calculate_adaptive_limits(
            resources, memory_pressure, cpu_pressure
        )

        assert isinstance(limits, ResourceLimits)
        assert limits.memory_pressure == memory_pressure
        assert limits.cpu_pressure == cpu_pressure
        assert limits.scaling_reason == "normal"
        assert limits.max_concurrent_tasks == 8  # 4 cores * 2

        # Target memory: 4096 * 0.15 = 614.4 MB
        # Target bars: 614.4 * 1000 = 614400, capped by max
        assert limits.max_bars_per_timeframe <= 50000  # Should be capped

    def test_calculate_adaptive_limits_memory_pressure(self, mixin):
        """Test adaptive limits calculation under memory pressure."""
        resources = SystemResources(
            total_memory_mb=8192,
            available_memory_mb=1024,  # Low available memory
            used_memory_mb=7168,
            memory_percent=87.5,
            cpu_count=4,
            cpu_percent=25.0,
            process_memory_mb=512,
            process_cpu_percent=5.0,
        )

        memory_pressure = 0.9  # High pressure
        cpu_pressure = 0.3  # Normal

        limits = mixin._calculate_adaptive_limits(
            resources, memory_pressure, cpu_pressure
        )

        assert limits.scaling_reason == "memory_pressure"
        # Memory should be scaled down by scale_down_factor (0.5)
        # Target: 1024 * 0.15 * 0.5 = 76.8 MB
        # Should result in smaller buffers
        assert limits.memory_limit_mb < 100

    def test_calculate_adaptive_limits_abundant_memory(self, mixin):
        """Test adaptive limits calculation with abundant memory."""
        resources = SystemResources(
            total_memory_mb=16384,  # 16GB
            available_memory_mb=12288,  # 12GB available
            used_memory_mb=4096,
            memory_percent=25.0,
            cpu_count=8,
            cpu_percent=15.0,
            process_memory_mb=256,
            process_cpu_percent=3.0,
        )

        memory_pressure = 0.2  # Low pressure
        cpu_pressure = 0.15  # Low pressure

        limits = mixin._calculate_adaptive_limits(
            resources, memory_pressure, cpu_pressure
        )

        assert limits.scaling_reason == "abundant_memory"
        # Memory should be scaled up by scale_up_factor (1.5)
        # Target: 12288 * 0.15 * 1.5 = 2764.8 MB
        assert limits.memory_limit_mb > 2000

    def test_calculate_adaptive_limits_cpu_pressure(self, mixin):
        """Test adaptive limits calculation under CPU pressure."""
        resources = SystemResources(
            total_memory_mb=8192,
            available_memory_mb=4096,
            used_memory_mb=4096,
            memory_percent=50.0,
            cpu_count=4,
            cpu_percent=90.0,  # High CPU usage
            process_memory_mb=256,
            process_cpu_percent=25.0,
        )

        memory_pressure = 0.4  # Normal
        cpu_pressure = 0.85  # High pressure

        limits = mixin._calculate_adaptive_limits(
            resources, memory_pressure, cpu_pressure
        )

        # CPU pressure should reduce concurrent tasks
        # Base: 4 * 2 = 8, scaled by 0.7 = 5.6, rounded down to 5
        assert limits.max_concurrent_tasks <= 6

    @pytest.mark.asyncio
    async def test_apply_resource_limits(self, mixin):
        """Test applying resource limits to component."""
        new_limits = ResourceLimits(
            max_bars_per_timeframe=2000,
            tick_buffer_size=1500,
            max_concurrent_tasks=6,
            cache_size_limit=300,
            memory_limit_mb=200.0,
            memory_pressure=0.5,
            cpu_pressure=0.4,
            scaling_reason="test",
        )

        old_max_bars = mixin.max_bars_per_timeframe
        old_tick_buffer = mixin.tick_buffer_size

        await mixin._apply_resource_limits(new_limits)

        assert mixin.max_bars_per_timeframe == 2000
        assert mixin.tick_buffer_size == 1500
        assert mixin._current_limits == new_limits
        assert mixin._resource_stats["resource_adjustments"] == 1

    @pytest.mark.asyncio
    async def test_manual_override(self, mixin):
        """Test manual resource override functionality."""
        overrides = {
            "max_bars_per_timeframe": 5000,
            "tick_buffer_size": 3000,
        }

        await mixin.override_resource_limits(overrides, duration_seconds=60.0)

        assert mixin._resource_config.manual_overrides == overrides
        assert mixin._resource_config.override_expiry is not None
        assert mixin._resource_stats["override_events"] == 1

    def test_should_update_limits(self, mixin):
        """Test limits update decision logic."""
        current = ResourceLimits(
            max_bars_per_timeframe=1000,
            tick_buffer_size=500,
            max_concurrent_tasks=4,
            cache_size_limit=200,
            memory_limit_mb=100.0,
            memory_pressure=0.3,
            cpu_pressure=0.2,
            scaling_reason="normal",
        )

        # Small change - should not update
        new_small = ResourceLimits(
            max_bars_per_timeframe=1050,  # 5% change
            tick_buffer_size=520,
            max_concurrent_tasks=4,
            cache_size_limit=200,
            memory_limit_mb=100.0,
            memory_pressure=0.3,
            cpu_pressure=0.2,
            scaling_reason="normal",
        )

        assert not mixin._should_update_limits(current, new_small)

        # Large change - should update
        new_large = ResourceLimits(
            max_bars_per_timeframe=1200,  # 20% change
            tick_buffer_size=500,
            max_concurrent_tasks=4,
            cache_size_limit=200,
            memory_limit_mb=100.0,
            memory_pressure=0.3,
            cpu_pressure=0.2,
            scaling_reason="normal",
        )

        assert mixin._should_update_limits(current, new_large)

        # Pressure event - should update
        new_pressure = ResourceLimits(
            max_bars_per_timeframe=1000,
            tick_buffer_size=500,
            max_concurrent_tasks=4,
            cache_size_limit=200,
            memory_limit_mb=100.0,
            memory_pressure=0.9,  # High pressure
            cpu_pressure=0.2,
            scaling_reason="memory_pressure",
        )

        assert mixin._should_update_limits(current, new_pressure)

    def test_callback_management(self, mixin):
        """Test resource change callback management."""
        callback1 = MagicMock()
        callback2 = MagicMock()

        # Add callbacks
        mixin.add_resource_change_callback(callback1)
        mixin.add_resource_change_callback(callback2)

        assert len(mixin._resource_change_callbacks) == 2
        assert callback1 in mixin._resource_change_callbacks
        assert callback2 in mixin._resource_change_callbacks

        # Remove callback
        mixin.remove_resource_change_callback(callback1)

        assert len(mixin._resource_change_callbacks) == 1
        assert callback1 not in mixin._resource_change_callbacks
        assert callback2 in mixin._resource_change_callbacks

    @pytest.mark.asyncio
    async def test_get_resource_stats(self, mixin):
        """Test resource statistics collection."""
        # Set up some test data
        mixin._current_limits = ResourceLimits(
            max_bars_per_timeframe=1000,
            tick_buffer_size=500,
            max_concurrent_tasks=4,
            cache_size_limit=200,
            memory_limit_mb=100.0,
            memory_pressure=0.5,
            cpu_pressure=0.3,
            scaling_reason="normal",
        )

        mixin._system_resources = SystemResources(
            total_memory_mb=8192,
            available_memory_mb=4096,
            used_memory_mb=4096,
            memory_percent=50.0,
            cpu_count=4,
            cpu_percent=25.0,
            process_memory_mb=256,
            process_cpu_percent=5.0,
        )

        mixin._memory_pressure_history.extend([0.3, 0.4, 0.5])
        mixin._cpu_pressure_history.extend([0.2, 0.3, 0.3])

        stats = await mixin.get_resource_stats()

        assert stats["dynamic_limits_enabled"] is True
        assert stats["psutil_available"] == PSUTIL_AVAILABLE
        assert "system_resources" in stats
        assert "current_limits" in stats
        assert "pressure_history" in stats
        assert "configuration" in stats

        # Check system resources
        sys_res = stats["system_resources"]
        assert sys_res["total_memory_mb"] == 8192
        assert sys_res["cpu_count"] == 4

        # Check current limits
        limits = stats["current_limits"]
        assert limits["max_bars_per_timeframe"] == 1000
        assert limits["memory_pressure"] == 0.5

        # Check pressure history
        history = stats["pressure_history"]
        assert len(history["memory_pressure"]) == 3
        assert abs(history["avg_memory_pressure"] - 0.4) < 0.01


@pytest.mark.integration
class TestDynamicResourceIntegration:
    """Integration tests for dynamic resource limits."""

    @pytest.mark.asyncio
    async def test_full_monitoring_cycle(self):
        """Test a complete monitoring cycle."""
        mixin = MockDynamicResourceMixin()

        # Configure with fast monitoring for testing
        mixin.configure_dynamic_resources(monitoring_interval=0.1)

        # Start monitoring
        mixin.start_resource_monitoring()

        # Let it run for a short time
        await asyncio.sleep(0.3)

        # Stop monitoring
        await mixin.stop_resource_monitoring()

        # Verify some monitoring occurred
        assert mixin._resource_stats["resource_adjustments"] >= 0
        assert mixin._system_resources is not None

    @pytest.mark.asyncio
    async def test_memory_pressure_simulation(self):
        """Test simulated memory pressure scenario."""
        mixin = MockDynamicResourceMixin()

        # Mock high memory pressure scenario
        with patch.object(mixin, "_get_system_resources") as mock_get_resources:
            mock_get_resources.return_value = SystemResources(
                total_memory_mb=4096,
                available_memory_mb=512,  # Very low available memory
                used_memory_mb=3584,
                memory_percent=87.5,
                cpu_count=4,
                cpu_percent=75.0,
                process_memory_mb=512,
                process_cpu_percent=15.0,
            )

            resources = await mixin._get_system_resources()
            memory_pressure = mixin._calculate_memory_pressure(resources)
            cpu_pressure = mixin._calculate_cpu_pressure(resources)

            # Should detect high memory pressure
            assert memory_pressure > 0.8

            # Calculate adaptive limits
            limits = mixin._calculate_adaptive_limits(
                resources, memory_pressure, cpu_pressure
            )

            # Should scale down due to memory pressure
            assert limits.scaling_reason == "memory_pressure"
            assert limits.memory_limit_mb < 100  # Should be significantly reduced

    @pytest.mark.asyncio
    async def test_abundant_memory_simulation(self):
        """Test simulated abundant memory scenario."""
        mixin = MockDynamicResourceMixin()

        # Mock abundant memory scenario
        with patch.object(mixin, "_get_system_resources") as mock_get_resources:
            mock_get_resources.return_value = SystemResources(
                total_memory_mb=32768,  # 32GB
                available_memory_mb=28672,  # 28GB available
                used_memory_mb=4096,
                memory_percent=12.5,
                cpu_count=16,
                cpu_percent=10.0,
                process_memory_mb=256,
                process_cpu_percent=2.0,
            )

            resources = await mixin._get_system_resources()
            memory_pressure = mixin._calculate_memory_pressure(resources)
            cpu_pressure = mixin._calculate_cpu_pressure(resources)

            # Should detect low memory pressure
            assert memory_pressure < 0.3

            # Calculate adaptive limits
            limits = mixin._calculate_adaptive_limits(
                resources, memory_pressure, cpu_pressure
            )

            # Should scale up due to abundant memory
            assert limits.scaling_reason == "abundant_memory"
            assert limits.memory_limit_mb > 4000  # Should be significantly increased
            assert limits.max_concurrent_tasks == 32  # 16 cores * 2
