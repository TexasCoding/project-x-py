#!/usr/bin/env python3
"""
Lock Coordinator for Thread-Safe Component Interactions

This module provides coordination between different components (OrderManager,
PositionManager, RealtimeClient) to prevent race conditions and ensure
consistent data access patterns.
"""

import threading
from collections.abc import Generator
from contextlib import contextmanager


class LockCoordinator:
    """
    Coordinates locks between different components to prevent deadlocks and race conditions.

    This class ensures that when multiple components need to access shared data,
    they do so in a consistent order to prevent deadlocks.
    """

    def __init__(self):
        """Initialize the lock coordinator."""
        # Master lock for coordinating component access
        self._master_lock = threading.RLock()

        # Component-specific locks in a consistent order to prevent deadlocks
        self._realtime_lock = threading.RLock()
        self._order_lock = threading.RLock()
        self._position_lock = threading.RLock()

        # Lock hierarchy to prevent deadlocks (always acquire in this order)
        self._lock_hierarchy = [
            self._realtime_lock,  # 1. Realtime client (data source)
            self._order_lock,  # 2. Order manager
            self._position_lock,  # 3. Position manager
        ]

    @property
    def realtime_lock(self) -> threading.RLock:
        """Get the realtime client lock."""
        return self._realtime_lock

    @property
    def order_lock(self) -> threading.RLock:
        """Get the order manager lock."""
        return self._order_lock

    @property
    def position_lock(self) -> threading.RLock:
        """Get the position manager lock."""
        return self._position_lock

    @contextmanager
    def coordinated_access(self, *components: str) -> Generator[None, None, None]:
        """
        Acquire locks for multiple components in a safe order.

        Args:
            *components: Component names ('realtime', 'order', 'position')

        Example:
            >>> with coordinator.coordinated_access("realtime", "order"):
            ...     # Access data from both components safely
            ...     pass
        """
        # Map component names to locks
        component_locks = {
            "realtime": self._realtime_lock,
            "order": self._order_lock,
            "position": self._position_lock,
        }

        # Get locks in hierarchy order to prevent deadlocks
        requested_locks = []
        for lock in self._lock_hierarchy:
            for component in components:
                if component_locks.get(component) == lock:
                    requested_locks.append(lock)
                    break

        # Acquire locks in order
        acquired_locks = []
        try:
            for lock in requested_locks:
                lock.acquire()
                acquired_locks.append(lock)
            yield
        finally:
            # Release locks in reverse order
            for lock in reversed(acquired_locks):
                lock.release()

    @contextmanager
    def all_components_locked(self) -> Generator[None, None, None]:
        """
        Acquire all component locks for major operations.

        Use this for operations that need to modify data across multiple components.
        """
        with self.coordinated_access("realtime", "order", "position"):
            yield


# Global lock coordinator instance (singleton pattern)
_global_coordinator: LockCoordinator | None = None
_coordinator_lock = threading.Lock()


def get_lock_coordinator() -> LockCoordinator:
    """
    Get the global lock coordinator instance.

    Returns:
        LockCoordinator: The singleton coordinator instance
    """
    global _global_coordinator

    if _global_coordinator is None:
        with _coordinator_lock:
            if _global_coordinator is None:
                _global_coordinator = LockCoordinator()

    return _global_coordinator
