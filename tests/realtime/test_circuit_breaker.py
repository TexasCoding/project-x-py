"""
Tests for the Circuit Breaker pattern implementation in realtime module.

Author: @TexasCoding
Date: 2025-08-22

Overview:
    Comprehensive test suite for the circuit breaker implementation, covering
    all states, failure scenarios, recovery mechanisms, and integration with
    the existing event handling system.

Test Categories:
    - Basic circuit breaker functionality
    - State transitions (CLOSED -> OPEN -> HALF_OPEN -> CLOSED)
    - Failure detection and threshold handling
    - Timeout and slow call protection
    - Exponential backoff and recovery
    - Fallback handlers
    - Integration with EventHandlingMixin
    - Metrics and monitoring
    - Configuration and customization

Testing Strategy:
    - Unit tests for individual components
    - Integration tests for mixin functionality
    - Performance tests for high-frequency scenarios
    - Error injection tests for failure scenarios
    - Recovery scenario testing
"""

import asyncio
import logging
import time
from unittest.mock import MagicMock

import pytest

from project_x_py.exceptions import ProjectXError
from project_x_py.realtime.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitBreakerMetrics,
    CircuitBreakerMixin,
    CircuitState,
)


@pytest.fixture
def circuit_config():
    """Create a test circuit breaker configuration."""
    return CircuitBreakerConfig(
        failure_threshold=3,
        time_window_seconds=10.0,
        timeout_seconds=1.0,
        recovery_timeout=2.0,
        half_open_max_calls=2,
        exponential_backoff_multiplier=2.0,
        max_recovery_time=30.0,
        slow_call_threshold=0.5,
    )


@pytest.fixture
def circuit_breaker(circuit_config):
    """Create a test circuit breaker."""
    logger = logging.getLogger("test_circuit")
    return CircuitBreaker("test_circuit", circuit_config, logger)


@pytest.fixture
def mock_logger():
    """Create a mock logger."""
    return MagicMock()


class MockEventHandler(CircuitBreakerMixin):
    """Mock event handler class for testing circuit breaker mixin."""

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger("test_handler")
        self.callbacks = {}
        self.callback_calls = []
        self.should_fail = False
        self.should_timeout = False
        self.delay = 0.0

    async def _trigger_callbacks(self, event_type: str, data: dict) -> None:
        """Mock callback triggering with configurable failure modes."""
        self.callback_calls.append((event_type, data))

        if self.delay > 0:
            await asyncio.sleep(self.delay)

        if self.should_timeout:
            await asyncio.sleep(10.0)  # Simulate timeout

        if self.should_fail:
            raise ProjectXError("Simulated callback failure")


class TestCircuitBreakerMetrics:
    """Test circuit breaker metrics tracking."""

    @pytest.mark.asyncio
    async def test_metrics_initialization(self):
        """Test metrics initialization."""
        metrics = CircuitBreakerMetrics(time_window_seconds=60.0)

        assert metrics.time_window_seconds == 60.0
        assert metrics.total_calls == 0
        assert metrics.total_failures == 0
        assert metrics.total_successes == 0
        assert metrics.get_failure_rate() == 0.0
        assert len(metrics.failures) == 0

    @pytest.mark.asyncio
    async def test_success_recording(self):
        """Test recording successful calls."""
        metrics = CircuitBreakerMetrics()

        metrics.record_success(0.1)
        metrics.record_success(0.2)

        assert metrics.total_successes == 2
        assert metrics.total_calls == 2
        assert metrics.get_failure_rate() == 0.0
        assert metrics.avg_response_time > 0
        assert metrics.max_response_time == 0.2

    @pytest.mark.asyncio
    async def test_failure_recording(self):
        """Test recording failed calls."""
        metrics = CircuitBreakerMetrics()

        metrics.record_failure(0.5)
        metrics.record_failure()

        assert metrics.total_failures == 2
        assert metrics.total_calls == 2
        assert metrics.get_failure_rate() == 1.0
        assert metrics.last_failure_time is not None

    @pytest.mark.asyncio
    async def test_timeout_recording(self):
        """Test recording timeouts."""
        metrics = CircuitBreakerMetrics()

        metrics.record_timeout()

        assert metrics.total_timeouts == 1
        assert metrics.total_failures == 1  # Timeouts count as failures
        assert metrics.get_failure_rate() == 1.0

    @pytest.mark.asyncio
    async def test_slow_call_recording(self):
        """Test recording slow calls."""
        metrics = CircuitBreakerMetrics()

        metrics.record_slow_call(2.0)
        metrics.record_success(0.1)

        assert metrics.total_slow_calls == 1
        assert metrics.get_slow_call_rate() == 0.5

    @pytest.mark.asyncio
    async def test_sliding_window(self):
        """Test sliding time window functionality."""
        metrics = CircuitBreakerMetrics(time_window_seconds=0.1)

        # Record some failures
        metrics.record_failure()
        metrics.record_failure()

        assert metrics.get_current_window_failures() == 2

        # Wait for window to expire
        await asyncio.sleep(0.2)

        # Old failures should be cleaned up
        assert metrics.get_current_window_failures() == 0

    @pytest.mark.asyncio
    async def test_state_change_recording(self):
        """Test recording state changes."""
        metrics = CircuitBreakerMetrics()

        metrics.record_state_change(CircuitState.OPEN)
        metrics.record_state_change(CircuitState.HALF_OPEN)

        assert metrics.circuit_opened_count == 1
        assert len(metrics.state_changes) == 2
        assert metrics.state_changes[0][1] == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_metrics_export(self):
        """Test metrics export to dictionary."""
        metrics = CircuitBreakerMetrics()

        metrics.record_success(0.1)
        metrics.record_failure(0.2)
        metrics.record_timeout()

        data = metrics.to_dict()

        assert data["total_calls"] == 3
        assert data["total_successes"] == 1
        assert data["total_failures"] == 2
        assert data["total_timeouts"] == 1
        assert "failure_rate" in data
        assert "avg_response_time" in data


class TestCircuitBreaker:
    """Test core circuit breaker functionality."""

    @pytest.mark.asyncio
    async def test_initialization(self, circuit_config):
        """Test circuit breaker initialization."""
        logger = logging.getLogger("test")
        breaker = CircuitBreaker("test", circuit_config, logger)

        assert breaker.name == "test"
        assert breaker.config == circuit_config
        assert breaker.state == CircuitState.CLOSED
        assert breaker.recovery_attempts == 0
        assert len(breaker.fallback_handlers) == 0

    @pytest.mark.asyncio
    async def test_successful_call(self, circuit_breaker):
        """Test successful function execution."""

        async def test_func(value: int) -> int:
            return value * 2

        result = await circuit_breaker.call("test_event", test_func, 5)

        assert result == 10
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.metrics.total_successes == 1

    @pytest.mark.asyncio
    async def test_timeout_protection(self, circuit_breaker):
        """Test timeout protection."""

        async def slow_func() -> None:
            await asyncio.sleep(2.0)  # Longer than timeout

        with pytest.raises(CircuitBreakerError, match="timeout"):
            await circuit_breaker.call("test_event", slow_func)

        assert circuit_breaker.metrics.total_timeouts == 1
        assert circuit_breaker.metrics.total_failures == 1

    @pytest.mark.asyncio
    async def test_exception_handling(self, circuit_breaker):
        """Test exception handling in protected calls."""

        async def failing_func() -> None:
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            await circuit_breaker.call("test_event", failing_func)

        assert circuit_breaker.metrics.total_failures == 1

    @pytest.mark.asyncio
    async def test_slow_call_detection(self, circuit_breaker):
        """Test slow call detection."""

        async def slow_func() -> str:
            await asyncio.sleep(0.6)  # Slower than threshold
            return "done"

        result = await circuit_breaker.call("test_event", slow_func)

        assert result == "done"
        assert circuit_breaker.metrics.total_slow_calls == 1

    @pytest.mark.asyncio
    async def test_circuit_opening(self, circuit_breaker):
        """Test circuit opening when failure threshold is reached."""

        async def failing_func() -> None:
            raise ValueError("Test error")

        # Trigger failures to reach threshold (3)
        for _ in range(3):
            with pytest.raises(ValueError):
                await circuit_breaker.call("test_event", failing_func)

        assert circuit_breaker.state == CircuitState.OPEN
        assert circuit_breaker.metrics.circuit_opened_count == 1

    @pytest.mark.asyncio
    async def test_open_circuit_blocking(self, circuit_breaker):
        """Test that open circuit blocks calls."""
        # Force circuit open
        await circuit_breaker.force_open()

        async def test_func() -> str:
            return "should not execute"

        with pytest.raises(CircuitBreakerError, match="is OPEN"):
            await circuit_breaker.call("test_event", test_func)

    @pytest.mark.asyncio
    async def test_fallback_handler(self, circuit_breaker):
        """Test fallback handler execution when circuit is open."""

        # Set up fallback
        async def fallback_handler() -> str:
            return "fallback_result"

        circuit_breaker.set_fallback_handler("test_event", fallback_handler)

        # Force circuit open
        await circuit_breaker.force_open()

        # Regular function (shouldn't execute)
        async def test_func() -> str:
            return "normal_result"

        result = await circuit_breaker.call("test_event", test_func)

        assert result == "fallback_result"

    @pytest.mark.asyncio
    async def test_recovery_transition(self, circuit_breaker):
        """Test transition from OPEN to HALF_OPEN after recovery timeout."""
        # Force circuit open
        await circuit_breaker.force_open()
        circuit_breaker.last_failure_time = time.time() - 3.0  # Simulate past failure

        async def test_func() -> str:
            return "recovery_test"

        # Should transition to half-open and allow call
        result = await circuit_breaker.call("test_event", test_func)

        assert result == "recovery_test"
        assert circuit_breaker.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_half_open_success_recovery(self, circuit_breaker):
        """Test successful recovery in half-open state."""
        # Set to half-open state
        circuit_breaker.state = CircuitState.HALF_OPEN
        circuit_breaker.half_open_calls = 0

        async def test_func() -> str:
            return "success"

        # Execute successful calls up to the limit
        for _ in range(circuit_breaker.config.half_open_max_calls):
            result = await circuit_breaker.call("test_event", test_func)
            assert result == "success"

        # Circuit should be closed after successful test calls
        assert circuit_breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_half_open_failure_reopening(self, circuit_breaker):
        """Test circuit reopening on failure in half-open state."""
        # Set to half-open state
        circuit_breaker.state = CircuitState.HALF_OPEN
        circuit_breaker.half_open_calls = 0

        async def failing_func() -> None:
            raise ValueError("Test failure")

        # Any failure in half-open should reopen circuit
        with pytest.raises(ValueError):
            await circuit_breaker.call("test_event", failing_func)

        assert circuit_breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_exponential_backoff(self, circuit_breaker):
        """Test exponential backoff in recovery timeout."""
        base_timeout = circuit_breaker.config.recovery_timeout
        multiplier = circuit_breaker.config.exponential_backoff_multiplier

        # Simulate multiple recovery attempts
        circuit_breaker.recovery_attempts = 1
        timeout1 = circuit_breaker._get_recovery_timeout()
        assert timeout1 == base_timeout

        circuit_breaker.recovery_attempts = 2
        timeout2 = circuit_breaker._get_recovery_timeout()
        assert timeout2 == base_timeout * multiplier

        circuit_breaker.recovery_attempts = 3
        timeout3 = circuit_breaker._get_recovery_timeout()
        assert timeout3 == base_timeout * (multiplier**2)

    @pytest.mark.asyncio
    async def test_max_recovery_time_cap(self, circuit_breaker):
        """Test that recovery timeout is capped at max_recovery_time."""
        circuit_breaker.recovery_attempts = 10  # Large number

        timeout = circuit_breaker._get_recovery_timeout()

        assert timeout <= circuit_breaker.config.max_recovery_time

    @pytest.mark.asyncio
    async def test_manual_force_operations(self, circuit_breaker):
        """Test manual force open/close operations."""
        # Test force open
        await circuit_breaker.force_open()
        assert circuit_breaker.state == CircuitState.OPEN

        # Test force closed
        await circuit_breaker.force_closed()
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.recovery_attempts == 0

    @pytest.mark.asyncio
    async def test_fallback_handler_management(self, circuit_breaker):
        """Test fallback handler management."""

        async def handler1() -> str:
            return "handler1"

        async def handler2() -> str:
            return "handler2"

        # Set handlers
        circuit_breaker.set_fallback_handler("event1", handler1)
        circuit_breaker.set_fallback_handler("event2", handler2)

        assert len(circuit_breaker.fallback_handlers) == 2

        # Remove handler
        circuit_breaker.remove_fallback_handler("event1")

        assert len(circuit_breaker.fallback_handlers) == 1
        assert "event2" in circuit_breaker.fallback_handlers

    @pytest.mark.asyncio
    async def test_metrics_export(self, circuit_breaker):
        """Test circuit breaker metrics export."""

        # Generate some activity
        async def test_func() -> str:
            return "test"

        await circuit_breaker.call("test_event", test_func)

        metrics = circuit_breaker.get_metrics()

        assert metrics["name"] == "test_circuit"
        assert metrics["state"] == CircuitState.CLOSED.value
        assert metrics["total_calls"] == 1
        assert metrics["total_successes"] == 1
        assert "config" in metrics
        assert "failure_rate" in metrics


class TestCircuitBreakerMixin:
    """Test circuit breaker mixin functionality."""

    @pytest.mark.asyncio
    async def test_mixin_initialization(self):
        """Test mixin initialization."""
        handler = MockEventHandler()

        assert not handler._circuit_breaker_enabled
        assert len(handler._circuit_breakers) == 0
        assert handler._global_circuit_breaker is None

    @pytest.mark.asyncio
    async def test_configuration(self):
        """Test circuit breaker configuration."""
        handler = MockEventHandler()

        await handler.configure_circuit_breaker(
            failure_threshold=5,
            timeout_seconds=2.0,
            enable_global_circuit=True,
            enable_per_event_circuits=True,
        )

        assert handler._circuit_breaker_enabled
        assert handler._global_circuit_breaker is not None
        assert handler._circuit_breaker_config.failure_threshold == 5
        assert handler._circuit_breaker_config.timeout_seconds == 2.0

    @pytest.mark.asyncio
    async def test_enable_disable_functionality(self):
        """Test enable/disable functionality."""
        handler = MockEventHandler()

        await handler.enable_circuit_breaker()
        assert handler._circuit_breaker_enabled

        await handler.disable_circuit_breaker()
        assert not handler._circuit_breaker_enabled

    @pytest.mark.asyncio
    async def test_circuit_breaker_bypass_when_disabled(self):
        """Test that circuit breaker is bypassed when disabled."""
        handler = MockEventHandler()
        handler.should_fail = True

        # Circuit breaker disabled - should call original method and raise error
        with pytest.raises(ProjectXError):
            await handler._trigger_callbacks_with_circuit_breaker("test_event", {})

        assert len(handler.callback_calls) == 1

    @pytest.mark.asyncio
    async def test_global_circuit_breaker_protection(self):
        """Test global circuit breaker protection."""
        handler = MockEventHandler()
        await handler.configure_circuit_breaker(
            failure_threshold=2,
            timeout_seconds=0.1,
            enable_global_circuit=True,
        )

        handler.should_fail = True

        # Trigger failures to open global circuit
        for _ in range(3):
            try:
                await handler._trigger_callbacks_with_circuit_breaker("test_event", {})
            except (ProjectXError, CircuitBreakerError):
                pass  # Expected failures

        # Global circuit should be open
        state = await handler.get_circuit_breaker_state()
        assert state == CircuitState.OPEN

        # Further calls should be blocked
        handler.should_fail = False  # Even if we fix the issue
        initial_calls = len(handler.callback_calls)
        await handler._trigger_callbacks_with_circuit_breaker("test_event", {})

        # Should not have been called due to open circuit
        assert (
            len(handler.callback_calls) == initial_calls
        )  # No new calls due to circuit being open

    @pytest.mark.asyncio
    async def test_per_event_circuit_breakers(self):
        """Test per-event circuit breaker creation and isolation."""
        handler = MockEventHandler()
        await handler.configure_circuit_breaker(
            failure_threshold=2,
            enable_global_circuit=False,
            enable_per_event_circuits=True,
        )

        # Test different event types
        await handler._trigger_callbacks_with_circuit_breaker("event1", {})
        await handler._trigger_callbacks_with_circuit_breaker("event2", {})

        # Should have created separate circuit breakers
        assert len(handler._circuit_breakers) == 2
        assert "event1" in handler._circuit_breakers
        assert "event2" in handler._circuit_breakers

    @pytest.mark.asyncio
    async def test_fallback_handler_integration(self):
        """Test fallback handler integration with mixin."""
        handler = MockEventHandler()
        await handler.configure_circuit_breaker(
            failure_threshold=1,
            enable_global_circuit=False,
        )

        # Set up fallback
        fallback_calls = []

        async def fallback_handler(*args, **kwargs):
            fallback_calls.append((args, kwargs))

        await handler.set_circuit_breaker_fallback("test_event", fallback_handler)

        # Trigger failure to open circuit
        handler.should_fail = True
        try:
            await handler._trigger_callbacks_with_circuit_breaker("test_event", {})
        except (ProjectXError, CircuitBreakerError):
            pass  # Expected failure

        # Next call should use fallback
        await handler._trigger_callbacks_with_circuit_breaker(
            "test_event", {"data": "test"}
        )

        assert len(fallback_calls) == 1

    @pytest.mark.asyncio
    async def test_timeout_protection_integration(self):
        """Test timeout protection in mixin."""
        handler = MockEventHandler()
        await handler.configure_circuit_breaker(
            timeout_seconds=0.1,
            failure_threshold=1,
        )

        # Simulate slow callback
        handler.delay = 0.2  # Longer than timeout

        # Should timeout and open circuit
        try:
            await handler._trigger_callbacks_with_circuit_breaker("test_event", {})
        except (ProjectXError, CircuitBreakerError):
            pass  # Expected timeout/failure

        # Check global circuit state (since we didn't enable per-event circuits)
        state = await handler.get_circuit_breaker_state(None)  # None for global
        assert state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_force_operations(self):
        """Test manual force operations through mixin."""
        handler = MockEventHandler()
        await handler.configure_circuit_breaker()

        # Force specific event circuit open
        await handler.force_circuit_breaker_open("test_event")
        state = await handler.get_circuit_breaker_state("test_event")
        assert state == CircuitState.OPEN

        # Force specific event circuit closed
        await handler.force_circuit_breaker_closed("test_event")
        state = await handler.get_circuit_breaker_state("test_event")
        assert state == CircuitState.CLOSED

        # Test global operations
        await handler.configure_circuit_breaker(enable_global_circuit=True)
        await handler.force_circuit_breaker_open()  # Global
        state = await handler.get_circuit_breaker_state()  # Global
        assert state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_metrics_collection(self):
        """Test metrics collection through mixin."""
        handler = MockEventHandler()
        # Use only per-event circuits (global circuit takes precedence when both are enabled)
        await handler.configure_circuit_breaker(
            enable_global_circuit=False,
            enable_per_event_circuits=True,
        )

        # Generate some activity
        await handler._trigger_callbacks_with_circuit_breaker("event1", {})
        await handler._trigger_callbacks_with_circuit_breaker("event2", {})

        # Get individual metrics
        event1_metrics = await handler.get_circuit_breaker_metrics("event1")
        assert event1_metrics["total_calls"] == 1

        # Get all metrics
        all_metrics = await handler.get_all_circuit_breaker_metrics()
        assert all_metrics["enabled"]
        assert all_metrics["global"] is None  # No global circuit configured
        assert "per_event" in all_metrics
        assert len(all_metrics["per_event"]) == 2

    @pytest.mark.asyncio
    async def test_cleanup(self):
        """Test circuit breaker cleanup."""
        handler = MockEventHandler()
        # Configure with per-event circuits only
        await handler.configure_circuit_breaker(
            enable_global_circuit=False, enable_per_event_circuits=True
        )

        # Create some circuit breakers
        await handler._trigger_callbacks_with_circuit_breaker("event1", {})
        await handler._trigger_callbacks_with_circuit_breaker("event2", {})

        assert len(handler._circuit_breakers) == 2

        # Cleanup
        await handler._cleanup_circuit_breakers()

        assert len(handler._circuit_breakers) == 0
        assert handler._global_circuit_breaker is None


class TestIntegration:
    """Test integration with existing event handling system."""

    @pytest.mark.asyncio
    async def test_integration_with_event_handling_mixin(self):
        """Test integration with existing EventHandlingMixin."""
        # This test simulates how the circuit breaker would integrate
        # with the actual EventHandlingMixin from the realtime module

        class TestEventHandler(CircuitBreakerMixin):
            def __init__(self):
                super().__init__()
                self.logger = logging.getLogger("test")
                self.callbacks = {"test_event": []}
                self.triggered_events = []

            async def _trigger_callbacks(self, event_type: str, data: dict) -> None:
                """Simulate original callback triggering."""
                self.triggered_events.append((event_type, data))

                # Simulate some callback processing time
                await asyncio.sleep(0.01)

        handler = TestEventHandler()
        await handler.configure_circuit_breaker(
            failure_threshold=2,
            timeout_seconds=0.5,
        )

        # Test normal operation
        await handler._trigger_callbacks_with_circuit_breaker(
            "test_event", {"symbol": "MNQ", "price": 18500}
        )

        assert len(handler.triggered_events) == 1
        assert handler.triggered_events[0][0] == "test_event"
        assert handler.triggered_events[0][1]["symbol"] == "MNQ"

    @pytest.mark.asyncio
    async def test_high_frequency_event_protection(self):
        """Test circuit breaker protection under high-frequency events."""
        handler = MockEventHandler()
        # Use per-event circuits for this test to track per-event metrics
        await handler.configure_circuit_breaker(
            failure_threshold=5,
            time_window_seconds=1.0,
            timeout_seconds=0.1,
            enable_global_circuit=False,  # Disable global to test per-event
            enable_per_event_circuits=True,
        )

        # Simulate high-frequency quote updates with some failures
        event_count = 50
        failure_every = 10

        for i in range(event_count):
            if i % failure_every == 0:
                handler.should_fail = True
            else:
                handler.should_fail = False

            try:
                await handler._trigger_callbacks_with_circuit_breaker(
                    "quote_update",
                    {"symbol": "MNQ", "bid": 18500 + i, "ask": 18501 + i},
                )
            except (ProjectXError, CircuitBreakerError):
                pass  # Expected for failures or when circuit opens

        # Circuit should have opened due to failures
        # state = await handler.get_circuit_breaker_state("quote_update")  # Not used, commenting out
        metrics = await handler.get_circuit_breaker_metrics("quote_update")

        # Verify protection was applied
        assert metrics["total_calls"] < event_count  # Some calls blocked
        assert metrics["total_failures"] > 0

    @pytest.mark.asyncio
    async def test_recovery_under_load(self):
        """Test circuit breaker recovery under continued load."""
        handler = MockEventHandler()
        # Use per-event circuits for this test
        await handler.configure_circuit_breaker(
            failure_threshold=3,
            recovery_timeout=0.1,  # Quick recovery for testing
            half_open_max_calls=2,
            enable_global_circuit=False,  # Disable global
            enable_per_event_circuits=True,  # Enable per-event
        )

        # Trigger failures to open circuit
        handler.should_fail = True
        for _ in range(4):
            try:
                await handler._trigger_callbacks_with_circuit_breaker("test_event", {})
            except (ProjectXError, CircuitBreakerError):
                pass

        # Circuit should be open
        state = await handler.get_circuit_breaker_state("test_event")
        assert state == CircuitState.OPEN

        # Wait for recovery period
        await asyncio.sleep(0.2)

        # Fix the issue
        handler.should_fail = False

        # Try recovery calls
        for _ in range(3):  # More than half_open_max_calls
            await handler._trigger_callbacks_with_circuit_breaker("test_event", {})

        # Circuit should be closed again
        state = await handler.get_circuit_breaker_state("test_event")
        assert state == CircuitState.CLOSED


class TestErrorScenarios:
    """Test various error and edge case scenarios."""

    @pytest.mark.asyncio
    async def test_concurrent_access(self):
        """Test circuit breaker behavior under concurrent access."""
        handler = MockEventHandler()
        await handler.configure_circuit_breaker(
            failure_threshold=5,
            timeout_seconds=0.1,
            enable_global_circuit=False,  # Disable global to test per-event
            enable_per_event_circuits=True,
        )

        async def concurrent_task(task_id: int):
            """Simulate concurrent event processing."""
            for i in range(10):
                try:
                    await handler._trigger_callbacks_with_circuit_breaker(
                        f"event_{task_id}", {"task_id": task_id, "iteration": i}
                    )
                    await asyncio.sleep(0.01)  # Small delay
                except (ProjectXError, CircuitBreakerError):
                    pass  # Handle failures

        # Run multiple concurrent tasks
        tasks = [concurrent_task(i) for i in range(5)]
        await asyncio.gather(*tasks)

        # Verify circuit breakers were created for each event type
        assert len(handler._circuit_breakers) == 5

        # Verify no deadlocks or race conditions occurred
        all_metrics = await handler.get_all_circuit_breaker_metrics()
        assert all_metrics["enabled"]

    @pytest.mark.asyncio
    async def test_configuration_edge_cases(self):
        """Test edge cases in configuration."""
        handler = MockEventHandler()

        # Test with extreme values
        await handler.configure_circuit_breaker(
            failure_threshold=1,  # Very sensitive
            time_window_seconds=0.1,  # Very short window
            timeout_seconds=0.01,  # Very short timeout
            recovery_timeout=0.01,  # Very quick recovery
        )

        assert handler._circuit_breaker_enabled
        assert handler._circuit_breaker_config.failure_threshold == 1

    @pytest.mark.asyncio
    async def test_fallback_handler_errors(self):
        """Test error handling in fallback handlers."""
        handler = MockEventHandler()
        await handler.configure_circuit_breaker(failure_threshold=1)

        # Set up failing fallback
        async def failing_fallback(*_args, **_kwargs):
            raise ValueError("Fallback failed")

        await handler.set_circuit_breaker_fallback("test_event", failing_fallback)

        # Force circuit open
        await handler.force_circuit_breaker_open("test_event")

        # Call should still fail, but circuit breaker should handle fallback error
        await handler._trigger_callbacks_with_circuit_breaker("test_event", {})

        # Should not crash or cause issues
        state = await handler.get_circuit_breaker_state("test_event")
        assert state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_memory_usage_under_stress(self):
        """Test that circuit breaker doesn't leak memory under stress."""
        import gc

        handler = MockEventHandler()
        await handler.configure_circuit_breaker(
            enable_global_circuit=False,  # Disable global to test per-event
            enable_per_event_circuits=True,
        )

        # Generate many events with different types
        for i in range(1000):
            event_type = f"event_{i % 10}"  # 10 different event types
            try:
                await handler._trigger_callbacks_with_circuit_breaker(
                    event_type, {"data": i}
                )
            except Exception:
                pass

        # Force garbage collection
        gc.collect()

        # Should only have 10 circuit breakers (not 1000)
        assert len(handler._circuit_breakers) == 10

        # Metrics should be reasonable
        for circuit_breaker in handler._circuit_breakers.values():
            metrics = circuit_breaker.get_metrics()
            assert metrics["total_calls"] > 0
            assert metrics["total_calls"] <= 1000  # Sanity check


@pytest.mark.performance
class TestPerformance:
    """Performance tests for circuit breaker implementation."""

    @pytest.mark.asyncio
    async def test_overhead_measurement(self):
        """Measure circuit breaker overhead."""
        handler = MockEventHandler()
        # Add a small delay to simulate more realistic callback processing
        handler.delay = 0.0001  # 0.1ms per callback - more realistic

        # Baseline: measure without circuit breaker
        start_time = time.time()
        for _ in range(1000):
            await handler._trigger_callbacks("test_event", {})
        baseline_time = time.time() - start_time

        # Reset for circuit breaker test
        handler.callback_calls.clear()
        await handler.configure_circuit_breaker(
            timeout_seconds=1.0,  # Reasonable timeout that won't trigger
        )

        # Measure with circuit breaker
        start_time = time.time()
        for _ in range(1000):
            await handler._trigger_callbacks_with_circuit_breaker("test_event", {})
        circuit_breaker_time = time.time() - start_time

        # Calculate overhead
        overhead = (circuit_breaker_time - baseline_time) / baseline_time

        # Circuit breaker overhead should be reasonable
        # In CI environments, overhead can be higher due to resource constraints
        # Allow up to 500% overhead in CI, 100% locally
        import os

        max_overhead = 5.0 if os.environ.get("CI") else 1.0
        assert overhead < max_overhead, (
            f"Circuit breaker overhead too high: {overhead:.2%} (max: {max_overhead * 100:.0f}%)"
        )

        print(f"Circuit breaker overhead: {overhead:.2%}")

    @pytest.mark.asyncio
    async def test_high_frequency_performance(self):
        """Test performance under high-frequency events."""
        handler = MockEventHandler()
        await handler.configure_circuit_breaker(
            failure_threshold=100,  # High threshold to avoid opening
            timeout_seconds=10.0,  # High timeout to avoid timeouts
        )

        event_count = 10000
        start_time = time.time()

        for i in range(event_count):
            await handler._trigger_callbacks_with_circuit_breaker(
                "quote_update", {"symbol": "MNQ", "price": 18500 + i}
            )

        total_time = time.time() - start_time
        events_per_second = event_count / total_time

        # Should handle at least 1000 events per second
        assert events_per_second > 1000, (
            f"Performance too low: {events_per_second:.0f} events/sec"
        )

        print(f"High-frequency performance: {events_per_second:.0f} events/sec")


if __name__ == "__main__":
    # Run tests with performance markers
    pytest.main([__file__, "-v", "-m", "not performance"])
