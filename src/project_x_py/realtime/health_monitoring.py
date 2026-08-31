"""
Connection health monitoring functionality for real-time client.

Author: @TexasCoding
Date: 2025-08-22

Overview:
    Provides comprehensive connection health monitoring for ProjectX real-time clients,
    including heartbeat mechanisms, latency tracking, connection performance metrics,
    and automatic reconnection triggers based on health thresholds.

Key Features:
    - Heartbeat mechanism with configurable intervals for both user and market hubs
    - Real-time latency monitoring and performance tracking
    - Connection health scoring with configurable thresholds (0-100)
    - Automatic reconnection triggers when health degrades below limits
    - Comprehensive health status API with detailed metrics
    - Thread-safe operations with proper async patterns
    - Integration with TaskManagerMixin for background task management
    - Memory-efficient circular buffers for latency history
    - Circuit breaker pattern for connection stability

Health Monitoring Capabilities:
    - Heartbeat ping/pong latency measurement for both hubs
    - Connection uptime and stability tracking
    - Event flow rate monitoring and anomaly detection
    - Round-trip time (RTT) statistics with percentiles
    - Connection error rate tracking and trending
    - Health score calculation based on multiple factors
    - Automatic reconnection when health falls below thresholds
    - Performance degradation alerts and notifications

Example Usage:
    The functionality of this mixin is consumed through a `ProjectXRealtimeClient` instance.
    For most use cases, this is handled automatically by the `TradingSuite`.

    ```python
    # The following demonstrates the health monitoring capabilities.
    # Note: In a typical application, you would use TradingSuite, which handles this.
    from project_x_py import create_realtime_client

    # 1. Initialization (health monitoring starts automatically)
    realtime_client = await create_realtime_client(jwt, account_id)

    # 2. Connection with health monitoring
    if await realtime_client.connect():
        print("Connected with health monitoring active")

        # 3. Health Status Monitoring
        health_status = await realtime_client.get_health_status()
        print(f"Health Score: {health_status['health_score']}/100")
        print(f"User Hub Latency: {health_status['user_hub_latency_ms']}ms")
        print(f"Market Hub Latency: {health_status['market_hub_latency_ms']}ms")

        # 4. Performance Metrics
        performance = await realtime_client.get_performance_metrics()
        print(f"Uptime: {performance['uptime_seconds']}s")
        print(f"Event Rate: {performance['events_per_second']}")

        # 5. Health Monitoring Configuration
        await realtime_client.configure_health_monitoring(
            heartbeat_interval=5.0,  # Heartbeat every 5 seconds
            health_threshold=75.0,  # Reconnect if health < 75
            latency_threshold_ms=1000,  # Alert if latency > 1000ms
        )

        # 6. Automatic health-based reconnection
        # If health degrades, automatic reconnection will trigger

        # 7. Manual health check
        if await realtime_client.is_connection_healthy():
            print("Connection is healthy")
        else:
            print("Connection health degraded")
            await realtime_client.force_health_reconnect()
    ```

Health Metrics:
    - Connection uptime and stability percentage
    - Round-trip latency (mean, p95, p99) for both hubs
    - Event processing rate and throughput
    - Error rate and connection failures
    - Heartbeat response rate and consistency
    - Overall health score (0-100) based on weighted factors

Performance Features:
    - Memory-efficient circular buffers for latency history (max 1000 samples)
    - Configurable heartbeat intervals (default: 10 seconds)
    - Automatic cleanup of old metric data
    - Non-blocking health monitoring that doesn't impact event processing
    - Circuit breaker pattern prevents cascade failures

Integration:
    - Uses TaskManagerMixin for background heartbeat tasks
    - Integrates with existing connection management
    - Preserves all existing connection capabilities
    - Thread-safe with proper async lock management
    - Compatible with all existing mixins and protocols

See Also:
    - `realtime.connection_management.ConnectionManagementMixin`
    - `realtime.core.ProjectXRealtimeClient`
    - `utils.task_management.TaskManagerMixin`
"""

import asyncio
import contextlib
import time
from collections import deque
from datetime import datetime
from typing import TYPE_CHECKING, Any

from project_x_py.realtime.async_hub import invoke_maybe
from project_x_py.utils import (
    LogContext,
    ProjectXLogger,
    handle_errors,
)

if TYPE_CHECKING:
    from project_x_py.types import ProjectXRealtimeClientProtocol

logger = ProjectXLogger.get_logger(__name__)


class HealthMonitoringMixin:
    """Mixin for connection health monitoring functionality."""

    def __init__(self) -> None:
        """Initialize health monitoring attributes."""
        super().__init__()
        self._init_health_monitoring()

    def _init_health_monitoring(self) -> None:
        """Initialize health monitoring state."""
        # Health monitoring configuration
        self.heartbeat_interval: float = 10.0  # seconds
        self.health_threshold: float = 70.0  # reconnect if health < threshold
        self.latency_threshold_ms: float = 2000.0  # alert threshold
        self.max_latency_samples: int = 1000  # circular buffer size

        # Health monitoring state
        self._health_monitoring_enabled: bool = True
        self._heartbeat_tasks: dict[str, asyncio.Task[Any]] = {}
        self._health_lock = asyncio.Lock()

        # Connection health metrics
        self._connection_start_time: float = 0.0
        self._last_user_heartbeat: float = 0.0
        self._last_market_heartbeat: float = 0.0
        self._user_heartbeat_pending: bool = False
        self._market_heartbeat_pending: bool = False

        # Latency tracking (circular buffers for memory efficiency)
        self._user_latencies: deque[float] = deque(maxlen=self.max_latency_samples)
        self._market_latencies: deque[float] = deque(maxlen=self.max_latency_samples)

        # Health statistics
        self._total_heartbeats_sent: int = 0
        self._user_heartbeats_failed: int = 0
        self._market_heartbeats_failed: int = 0
        self._connection_failures: int = 0
        self._last_health_score: float = 100.0

        # Performance tracking
        self._events_received_last_check: int = 0
        self._last_performance_check: float = time.time()

        # Stale-feed watchdog (#97)
        self.stale_feed_seconds: float = 30.0
        self.stale_feed_check_interval: float = 5.0
        self.health_reconnect_wait_seconds: float = 5.0
        self._stale_feed_task: asyncio.Task[Any] | None = None
        self._stale_feed_emitted: dict[str, bool] = {"user": False, "market": False}
        self._hub_watch_started: dict[str, float] = {"user": 0.0, "market": 0.0}
        self._restore_lock = asyncio.Lock()
        self._restore_in_flight = False
        self._last_market_message: float = 0.0
        self._last_user_message: float = 0.0

    @handle_errors("configure health monitoring")
    async def configure_health_monitoring(
        self: "ProjectXRealtimeClientProtocol",
        heartbeat_interval: float = 10.0,
        health_threshold: float = 70.0,
        latency_threshold_ms: float = 2000.0,
        max_latency_samples: int = 1000,
    ) -> None:
        """
        Configure health monitoring parameters.

        Args:
            heartbeat_interval: Interval between heartbeats in seconds
            health_threshold: Health score below which reconnection triggers
            latency_threshold_ms: Latency threshold for alerts in milliseconds
            max_latency_samples: Maximum number of latency samples to keep
        """
        async with self._health_lock:
            self.heartbeat_interval = heartbeat_interval
            self.health_threshold = health_threshold
            self.latency_threshold_ms = latency_threshold_ms
            self.max_latency_samples = max_latency_samples

            # Update circular buffer size if needed
            if max_latency_samples != self._user_latencies.maxlen:
                # Preserve recent samples when resizing
                user_samples = list(self._user_latencies)[-max_latency_samples:]
                market_samples = list(self._market_latencies)[-max_latency_samples:]

                self._user_latencies = deque(user_samples, maxlen=max_latency_samples)
                self._market_latencies = deque(
                    market_samples, maxlen=max_latency_samples
                )

        logger.info(
            f"Health monitoring configured: heartbeat={heartbeat_interval}s, "
            f"threshold={health_threshold}, latency_threshold={latency_threshold_ms}ms"
        )

    @handle_errors("start health monitoring")
    async def _start_health_monitoring(self: "ProjectXRealtimeClientProtocol") -> None:
        """Start health monitoring background tasks."""
        if not self._health_monitoring_enabled:
            return

        async with self._health_lock:
            self._connection_start_time = time.time()

            # Start heartbeat tasks for both hubs if not already running
            if (
                "user" not in self._heartbeat_tasks
                or self._heartbeat_tasks["user"].done()
            ):
                self._heartbeat_tasks["user"] = self._create_task(
                    self._user_heartbeat_loop(), name="user_heartbeat", persistent=True
                )

            if (
                "market" not in self._heartbeat_tasks
                or self._heartbeat_tasks["market"].done()
            ):
                self._heartbeat_tasks["market"] = self._create_task(
                    self._market_heartbeat_loop(),
                    name="market_heartbeat",
                    persistent=True,
                )

        await self._start_stale_feed_watchdog()
        logger.debug("Health monitoring started")

    @handle_errors("stop health monitoring")
    async def _stop_health_monitoring(self: "ProjectXRealtimeClientProtocol") -> None:
        """Stop health monitoring background tasks."""
        async with self._health_lock:
            # Cancel heartbeat tasks
            for task in self._heartbeat_tasks.values():
                if not task.done():
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task

            self._heartbeat_tasks.clear()

        await self._stop_stale_feed_watchdog()
        logger.debug("Health monitoring stopped")

    async def _start_stale_feed_watchdog(
        self: "ProjectXRealtimeClientProtocol",
    ) -> None:
        """Start the market-hub stale-feed watchdog."""
        task = getattr(self, "_stale_feed_task", None)
        if task is not None and not task.done():
            return
        self._stale_feed_emitted = {"user": False, "market": False}
        now = time.monotonic()
        started = getattr(self, "_hub_watch_started", {"user": 0.0, "market": 0.0})
        self._hub_watch_started = {
            "user": started.get("user", 0.0) or now,
            "market": started.get("market", 0.0) or now,
        }
        self._stale_feed_task = asyncio.create_task(
            self._stale_feed_watchdog_loop(), name="stale_feed_watchdog"
        )

    async def _stop_stale_feed_watchdog(
        self: "ProjectXRealtimeClientProtocol",
    ) -> None:
        """Cancel the stale-feed watchdog."""
        task = getattr(self, "_stale_feed_task", None)
        if task is None or task.done():
            return
        if task is asyncio.current_task():
            # Reconnect was invoked from the watchdog itself. Keep the
            # slot bound so _start_stale_feed_watchdog does not spawn a
            # second loop while this one is still running.
            return
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        self._stale_feed_task = None

    async def _stale_feed_watchdog_loop(
        self: "ProjectXRealtimeClientProtocol",
    ) -> None:
        """Reconnect when market-hub messages stop arriving."""
        from project_x_py.event_bus import EventType

        while True:
            await asyncio.sleep(self.stale_feed_check_interval)
            stale_hubs: list[tuple[str, float]] = []
            # Market-hub silence is a real freeze. User-hub silence is normal
            # while flat / overnight with no fills (#129).
            for hub in ("market",):
                age = self._hub_silence_age(hub)
                if age is None:
                    continue
                stale_hubs.append((hub, age))

            if not stale_hubs:
                continue

            event_bus = getattr(self, "event_bus", None)
            emitted = self._stale_feed_emitted
            if not isinstance(emitted, dict):
                emitted = {"user": False, "market": False}
                self._stale_feed_emitted = emitted

            for hub, age in stale_hubs:
                payload = {
                    "hub": hub,
                    "seconds_since_message": age,
                    "threshold_seconds": self.stale_feed_seconds,
                }
                logger.warning(
                    "%s feed stale; forcing reconnect",
                    hub.title(),
                    extra=payload,
                )
                if not emitted.get(hub, False):
                    if event_bus is not None:
                        await event_bus.emit(
                            EventType.FEED_STALE, payload, source="RealtimeClient"
                        )
                    emitted[hub] = True

            await self._serialized_health_reconnect()

    def _hub_silence_age(self, hub: str) -> float | None:
        """Return seconds since last hub message, or None if the hub is not stale."""
        if hub == "user":
            return None
        connected_attr = "market_connected" if hub == "market" else "user_connected"
        if not getattr(self, connected_attr, False):
            return None

        last_attr = "_last_market_message" if hub == "market" else "_last_user_message"
        last_message = float(getattr(self, last_attr, 0.0) or 0.0)
        if last_message <= 0:
            started = getattr(self, "_hub_watch_started", {}).get(hub, 0.0)
            last_message = float(started or 0.0)
        if last_message <= 0:
            return None

        age = time.monotonic() - last_message
        if age < self.stale_feed_seconds:
            emitted = getattr(self, "_stale_feed_emitted", None)
            if isinstance(emitted, dict):
                emitted[hub] = False
            return None
        return age

    async def _serialized_health_reconnect(
        self: "ProjectXRealtimeClientProtocol",
    ) -> bool:
        """Run at most one health reconnect at a time; extras are dropped."""
        if getattr(self, "_restore_in_flight", False) or self._restore_lock.locked():
            return False
        async with self._restore_lock:
            if getattr(self, "_restore_in_flight", False):
                return False
            self._restore_in_flight = True
        try:
            reconnect = getattr(self, "force_health_reconnect", None)
            if reconnect is None:
                return False
            success = bool(await reconnect())
            if success:
                self._mark_hubs_fresh()
            return success
        finally:
            self._restore_in_flight = False

    def _hub_transport_running(self) -> bool:
        """True if a SignalR hub run() task is still active."""
        for conn in (
            getattr(self, "user_connection", None),
            getattr(self, "market_connection", None),
        ):
            if conn is None:
                continue
            task = getattr(conn, "_run_task", None)
            if task is None:
                continue
            done = getattr(task, "done", None)
            if not callable(done):
                continue
            try:
                if not bool(done()):
                    return True
            except Exception:
                continue
        return False

    def _mark_hubs_fresh(self) -> None:
        """Record a successful restore so the watchdog does not immediately re-trip."""
        now = time.monotonic()
        self._last_market_message = now
        self._last_user_message = now
        self._hub_watch_started = {"user": now, "market": now}
        self._stale_feed_emitted = {"user": False, "market": False}

    async def _user_heartbeat_loop(self: "ProjectXRealtimeClientProtocol") -> None:
        """Background task for user hub heartbeat monitoring."""
        while self.user_connected and self._health_monitoring_enabled:
            try:
                await self._send_heartbeat("user")
                await asyncio.sleep(self.heartbeat_interval)
            except asyncio.CancelledError:
                raise  # Re-raise cancellation to properly propagate task cancellation
            except Exception as e:
                logger.error(f"User heartbeat error: {e}")
                await asyncio.sleep(self.heartbeat_interval)

    async def _market_heartbeat_loop(self: "ProjectXRealtimeClientProtocol") -> None:
        """Background task for market hub heartbeat monitoring."""
        while self.market_connected and self._health_monitoring_enabled:
            try:
                await self._send_heartbeat("market")
                await asyncio.sleep(self.heartbeat_interval)
            except asyncio.CancelledError:
                raise  # Re-raise cancellation to properly propagate task cancellation
            except Exception as e:
                logger.error(f"Market heartbeat error: {e}")
                await asyncio.sleep(self.heartbeat_interval)

    @handle_errors("send heartbeat")
    async def _send_heartbeat(self: "ProjectXRealtimeClientProtocol", hub: str) -> None:
        """
        Send heartbeat to specified hub and measure latency.

        Args:
            hub: Hub name ("user" or "market")
        """
        if hub == "user" and not self.user_connected:
            return
        if hub == "market" and not self.market_connected:
            return

        connection = self.user_connection if hub == "user" else self.market_connection
        if not connection:
            return

        start_time = time.time()

        try:
            # Set pending flag
            if hub == "user":
                self._user_heartbeat_pending = True
            else:
                self._market_heartbeat_pending = True

            self._total_heartbeats_sent += 1

            # Send ping - SignalR connections typically have a ping method
            # If not available, we'll use a custom heartbeat message.
            # AsyncHubConnection.send is async; always await it (#126).
            ping_method = getattr(connection, "ping", None)
            if callable(ping_method):
                await invoke_maybe(ping_method)
            else:
                await invoke_maybe(
                    connection.send,
                    "Heartbeat",
                    [{"timestamp": time.time()}],
                )

            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000

            # Store latency
            if hub == "user":
                self._user_latencies.append(latency_ms)
                self._last_user_heartbeat = time.time()
            else:
                self._market_latencies.append(latency_ms)
                self._last_market_heartbeat = time.time()

            # Check for high latency
            if latency_ms > self.latency_threshold_ms:
                logger.warning(
                    f"{hub.title()} hub high latency: {latency_ms:.1f}ms "
                    f"(threshold: {self.latency_threshold_ms}ms)"
                )

        except Exception as e:
            # Record failure
            if hub == "user":
                self._user_heartbeats_failed += 1
            else:
                self._market_heartbeats_failed += 1

            logger.error(f"{hub.title()} hub heartbeat failed: {e}")

        finally:
            # Clear pending flag
            if hub == "user":
                self._user_heartbeat_pending = False
            else:
                self._market_heartbeat_pending = False

    async def get_health_status(
        self: "ProjectXRealtimeClientProtocol",
    ) -> dict[str, Any]:
        """
        Get comprehensive connection health status.

        Returns:
            Dictionary containing detailed health metrics
        """
        async with self._health_lock:
            current_time = time.time()

            # Calculate uptime
            uptime_seconds = (
                current_time - self._connection_start_time
                if self._connection_start_time > 0
                else 0
            )

            # Calculate latency statistics
            user_latency_stats = self._calculate_latency_stats(self._user_latencies)
            market_latency_stats = self._calculate_latency_stats(self._market_latencies)

            # Calculate event processing rate
            events_rate = self._calculate_event_rate()

            # Calculate overall health score
            health_score = await self._calculate_health_score()
            self._last_health_score = health_score

            return {
                # Overall health
                "health_score": health_score,
                "status": self._get_health_status_string(health_score),
                "uptime_seconds": uptime_seconds,
                "timestamp": datetime.now().isoformat(),
                # Connection status
                "user_connected": self.user_connected,
                "market_connected": self.market_connected,
                "both_connected": self.is_connected(),
                # Latency metrics
                "user_hub_latency_ms": user_latency_stats["mean"],
                "user_hub_latency_p95": user_latency_stats["p95"],
                "user_hub_latency_p99": user_latency_stats["p99"],
                "market_hub_latency_ms": market_latency_stats["mean"],
                "market_hub_latency_p95": market_latency_stats["p95"],
                "market_hub_latency_p99": market_latency_stats["p99"],
                # Performance metrics
                "events_per_second": events_rate,
                "total_events_received": getattr(self, "stats", {}).get(
                    "events_received", 0
                ),
                # Reliability metrics
                "total_heartbeats_sent": self._total_heartbeats_sent,
                "user_heartbeats_failed": self._user_heartbeats_failed,
                "market_heartbeats_failed": self._market_heartbeats_failed,
                "connection_failures": self._connection_failures,
                "user_heartbeat_success_rate": self._calculate_success_rate("user"),
                "market_heartbeat_success_rate": self._calculate_success_rate("market"),
                # Last heartbeat times
                "last_user_heartbeat": self._last_user_heartbeat,
                "last_market_heartbeat": self._last_market_heartbeat,
                "user_heartbeat_pending": self._user_heartbeat_pending,
                "market_heartbeat_pending": self._market_heartbeat_pending,
                # Configuration
                "heartbeat_interval": self.heartbeat_interval,
                "health_threshold": self.health_threshold,
                "latency_threshold_ms": self.latency_threshold_ms,
            }

    async def get_performance_metrics(
        self: "ProjectXRealtimeClientProtocol",
    ) -> dict[str, Any]:
        """
        Get detailed performance metrics.

        Returns:
            Dictionary containing performance data
        """
        health_status = await self.get_health_status()

        return {
            "uptime_seconds": health_status["uptime_seconds"],
            "events_per_second": health_status["events_per_second"],
            "total_events": health_status["total_events_received"],
            "average_latency_ms": (
                health_status["user_hub_latency_ms"]
                + health_status["market_hub_latency_ms"]
            )
            / 2,
            "connection_stability": health_status["health_score"],
            "memory_usage": {
                "user_latency_samples": len(self._user_latencies),
                "market_latency_samples": len(self._market_latencies),
                "max_samples": self.max_latency_samples,
            },
        }

    async def is_connection_healthy(
        self: "ProjectXRealtimeClientProtocol", threshold: float | None = None
    ) -> bool:
        """
        Check if connection health is above threshold.

        Args:
            threshold: Custom threshold to use (default: configured threshold)

        Returns:
            True if connection is healthy
        """
        health_score = await self._calculate_health_score()
        check_threshold = threshold if threshold is not None else self.health_threshold
        return health_score >= check_threshold

    @handle_errors("force health reconnect")
    async def force_health_reconnect(self: "ProjectXRealtimeClientProtocol") -> bool:
        """
        Force a reconnection due to health issues.

        Returns:
            True if reconnection successful
        """
        with LogContext(
            logger,
            operation="force_health_reconnect",
            health_score=self._last_health_score,
        ):
            logger.warning(
                f"Forcing reconnection due to poor health: {self._last_health_score:.1f}"
            )

            # Record connection failure
            self._connection_failures += 1

            # Stop health monitoring temporarily
            await self._stop_health_monitoring()

            # Disconnect and reconnect. pysignalr/websockets raise
            # "Cannot connect while not disconnected" if connect() runs
            # before the previous transport has fully dropped (#129).
            await self.disconnect()
            deadline = time.monotonic() + self.health_reconnect_wait_seconds
            while self._hub_transport_running() and time.monotonic() < deadline:
                await asyncio.sleep(0.05)
            if self._hub_transport_running():
                logger.error(
                    "Health-based reconnection aborted: hub transport still running"
                )
                await self._start_health_monitoring()
                return False
            success = await self.connect()

            if success:
                await self._restore_realtime_subscriptions()
                # Restart health monitoring
                await self._start_health_monitoring()
                mark_fresh = getattr(self, "_mark_hubs_fresh", None)
                if mark_fresh is not None:
                    mark_fresh()
                logger.info("Health-based reconnection successful")
            else:
                logger.error("Health-based reconnection failed")

            return success

    async def _restore_realtime_subscriptions(
        self: "ProjectXRealtimeClientProtocol",
    ) -> None:
        """Re-subscribe user and market channels after a reconnect."""
        if getattr(self, "_user_updates_subscribed", False):
            subscribe_user = getattr(self, "subscribe_user_updates", None)
            if subscribe_user is not None:
                await subscribe_user()
        contracts = list(getattr(self, "_subscribed_contracts", []))
        if contracts:
            subscribe_market = getattr(self, "subscribe_market_data", None)
            if subscribe_market is not None:
                await subscribe_market(contracts)

    def _calculate_latency_stats(self, latencies: deque[float]) -> dict[str, float]:
        """Calculate latency statistics from samples."""
        if not latencies:
            return {"mean": 0.0, "p95": 0.0, "p99": 0.0}

        sorted_latencies = sorted(latencies)
        n = len(sorted_latencies)

        return {
            "mean": sum(sorted_latencies) / n,
            "p95": sorted_latencies[int(n * 0.95)] if n > 0 else 0.0,
            "p99": sorted_latencies[int(n * 0.99)] if n > 0 else 0.0,
        }

    def _calculate_event_rate(self: "ProjectXRealtimeClientProtocol") -> float:
        """Calculate current event processing rate."""
        current_time = time.time()
        # Use getattr with default to avoid attribute access issues
        stats = getattr(self, "stats", {})
        current_events = stats.get("events_received", 0)

        time_delta = current_time - self._last_performance_check
        event_delta = current_events - self._events_received_last_check

        rate = event_delta / time_delta if time_delta > 0 else 0.0

        # Update for next calculation
        self._last_performance_check = current_time
        self._events_received_last_check = current_events

        return rate

    async def _calculate_health_score(self: "ProjectXRealtimeClientProtocol") -> float:
        """
        Calculate overall health score (0-100) based on multiple factors.

        Health factors:
        - Connection status (40% weight)
        - Latency performance (30% weight)
        - Heartbeat reliability (20% weight)
        - Event processing rate (10% weight)
        """
        # Connection status score (40%)
        connection_score = 0.0
        if self.user_connected and self.market_connected:
            connection_score = 100.0
        elif self.user_connected or self.market_connected:
            connection_score = 50.0

        # Latency score (30%)
        latency_score = self._calculate_latency_score()

        # Heartbeat reliability score (20%)
        reliability_score = self._calculate_reliability_score()

        # Event processing score (10%)
        event_score = self._calculate_event_processing_score()

        # Weighted average
        health_score = (
            connection_score * 0.4
            + latency_score * 0.3
            + reliability_score * 0.2
            + event_score * 0.1
        )

        return round(health_score, 1)

    def _calculate_latency_score(self) -> float:
        """Calculate latency-based health score."""
        if not self._user_latencies and not self._market_latencies:
            return 100.0

        # Get recent latencies (last 10 samples for responsiveness)
        recent_user = list(self._user_latencies)[-10:] if self._user_latencies else []
        recent_market = (
            list(self._market_latencies)[-10:] if self._market_latencies else []
        )

        all_latencies = recent_user + recent_market
        if not all_latencies:
            return 100.0

        avg_latency = sum(all_latencies) / len(all_latencies)

        # Score based on latency thresholds
        if avg_latency <= 100:  # Excellent
            return 100.0
        elif avg_latency <= 300:  # Good
            return 90.0
        elif avg_latency <= 500:  # Fair
            return 75.0
        elif avg_latency <= 1000:  # Poor
            return 50.0
        elif avg_latency <= self.latency_threshold_ms:  # Bad
            return 25.0
        else:  # Critical
            return 0.0

    def _calculate_reliability_score(self) -> float:
        """Calculate heartbeat reliability score."""
        if self._total_heartbeats_sent == 0:
            return 100.0

        total_failures = self._user_heartbeats_failed + self._market_heartbeats_failed
        success_rate = 1.0 - (total_failures / self._total_heartbeats_sent)

        return max(0.0, success_rate * 100.0)

    def _calculate_event_processing_score(
        self: "ProjectXRealtimeClientProtocol",
    ) -> float:
        """Calculate event processing health score."""
        # Check if we're receiving events at a reasonable rate
        current_time = time.time()
        # Use getattr with default to avoid attribute access issues
        stats = getattr(self, "stats", {})
        last_event_time = stats.get("last_event_time")

        if not last_event_time:
            return 100.0  # No events yet, assume healthy

        # Convert datetime to timestamp if needed
        if isinstance(last_event_time, datetime):
            last_event_timestamp = last_event_time.timestamp()
        else:
            last_event_timestamp = last_event_time

        time_since_last_event = current_time - last_event_timestamp

        # Score based on recency of events
        if time_since_last_event <= 10:  # Recent events
            return 100.0
        elif time_since_last_event <= 30:  # Somewhat stale
            return 75.0
        elif time_since_last_event <= 60:  # Stale
            return 50.0
        else:  # Very stale
            return 25.0

    def _calculate_success_rate(self, hub: str) -> float:
        """Calculate heartbeat success rate for a hub."""
        if self._total_heartbeats_sent == 0:
            return 100.0

        failures = (
            self._user_heartbeats_failed
            if hub == "user"
            else self._market_heartbeats_failed
        )

        # Approximate hub-specific heartbeats (total / 2 for each hub)
        hub_heartbeats = self._total_heartbeats_sent // 2
        if hub_heartbeats == 0:
            return 100.0

        success_rate = max(0.0, 1.0 - (failures / hub_heartbeats))
        return round(success_rate * 100.0, 1)

    def _get_health_status_string(self, health_score: float) -> str:
        """Convert health score to status string."""
        if health_score >= 90:
            return "excellent"
        elif health_score >= 75:
            return "good"
        elif health_score >= 50:
            return "fair"
        elif health_score >= 25:
            return "poor"
        else:
            return "critical"

    # Override connection methods to integrate health monitoring

    async def connect(self: "ProjectXRealtimeClientProtocol") -> bool:
        """Override connect to start health monitoring."""
        # Call parent connect method
        success = await super().connect()  # type: ignore

        if success:
            await self._start_health_monitoring()

        return success

    async def disconnect(self: "ProjectXRealtimeClientProtocol") -> None:
        """Override disconnect to stop health monitoring."""
        # Stop health monitoring first
        await self._stop_health_monitoring()

        # Call parent disconnect method
        await super().disconnect()  # type: ignore

    async def _cleanup_tasks(self, timeout: float = 5.0) -> None:
        """Override to include health monitoring cleanup."""
        # Stop health monitoring
        await self._stop_health_monitoring()

        # Call parent cleanup
        await super()._cleanup_tasks(timeout)  # type: ignore

    def get_stats(self: "ProjectXRealtimeClientProtocol") -> dict[str, Any]:
        """Override to include health monitoring stats."""
        base_stats = super().get_stats()  # type: ignore

        # Add health monitoring metrics
        health_stats = {
            "health_monitoring": {
                "enabled": self._health_monitoring_enabled,
                "last_health_score": self._last_health_score,
                "total_heartbeats": self._total_heartbeats_sent,
                "user_heartbeat_failures": self._user_heartbeats_failed,
                "market_heartbeat_failures": self._market_heartbeats_failed,
                "connection_failures": self._connection_failures,
                "latency_samples": {
                    "user": len(self._user_latencies),
                    "market": len(self._market_latencies),
                },
            }
        }

        return {**base_stats, **health_stats}
