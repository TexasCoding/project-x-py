"""Test async task management and cleanup."""

import asyncio
from unittest.mock import MagicMock

import pytest

from project_x_py.utils.task_management import AsyncContextManager, TaskManagerMixin


class TestTaskManager(TaskManagerMixin):
    """Test implementation of TaskManagerMixin."""

    def __init__(self):
        super().__init__()
        self._init_task_manager()
        self.tasks_completed = []

    async def long_running_task(self, task_id: str):
        """Simulate a long-running task."""
        try:
            await asyncio.sleep(10)  # Won't actually complete
            self.tasks_completed.append(task_id)
        except asyncio.CancelledError:
            # Task was cancelled
            raise

    async def failing_task(self):
        """Simulate a task that fails."""
        await asyncio.sleep(0.1)
        raise ValueError("Task failed!")


@pytest.mark.asyncio
class TestTaskManagement:
    """Test task management functionality."""

    async def test_task_tracking(self):
        """Test that tasks are properly tracked."""
        manager = TestTaskManager()

        # Create some tasks
        task1 = manager._create_task(manager.long_running_task("task1"), name="task1")
        task2 = manager._create_task(
            manager.long_running_task("task2"), name="task2", persistent=True
        )

        # Check stats
        stats = manager.get_task_stats()
        assert stats["total_tasks"] >= 2
        assert stats["pending_tasks"] >= 2
        assert stats["persistent_tasks"] == 1

        # Cleanup
        await manager._cleanup_tasks(timeout=0.5)

        # Verify tasks were cancelled
        assert task1.cancelled()
        assert task2.cancelled()

    async def test_task_cleanup_on_exit(self):
        """Test that tasks are cleaned up in context manager."""

        class TestAsyncManager(AsyncContextManager):
            def __init__(self):
                super().__init__()
                self.task_started = False
                self.task_completed = False

            async def background_work(self):
                self.task_started = True
                await asyncio.sleep(10)  # Won't complete
                self.task_completed = True

        manager = TestAsyncManager()

        async with manager:
            # Start a background task
            task = manager._create_task(
                manager.background_work(), name="background", persistent=True
            )

            # Verify task started
            await asyncio.sleep(0.1)
            assert manager.task_started
            assert not manager.task_completed

        # After exiting context, task should be cancelled
        assert task.cancelled()
        assert not manager.task_completed

    async def test_task_error_handling(self):
        """Test that task errors are tracked."""
        manager = TestTaskManager()

        # Create a failing task
        task = manager._create_task(manager.failing_task(), name="failing_task")

        # Wait for task to fail
        await asyncio.sleep(0.2)

        # Check that error was tracked
        assert len(manager._task_errors) == 1
        assert isinstance(manager._task_errors[0], ValueError)
        assert str(manager._task_errors[0]) == "Task failed!"

        # Cleanup
        await manager._cleanup_tasks()

    async def test_multiple_cleanup_calls(self):
        """Test that multiple cleanup calls are safe."""
        manager = TestTaskManager()

        # Create some tasks
        for i in range(5):
            manager._create_task(manager.long_running_task(f"task{i}"), name=f"task{i}")

        # Multiple cleanup calls should be safe
        await manager._cleanup_tasks(timeout=0.5)
        await manager._cleanup_tasks(timeout=0.5)
        await manager._cleanup_tasks(timeout=0.5)

        # Check stats
        stats = manager.get_task_stats()
        assert stats["cancelled_tasks"] >= 5

    async def test_persistent_vs_weak_tasks(self):
        """Test difference between persistent and weak tasks."""
        manager = TestTaskManager()

        # Create weak task (in WeakSet)
        weak_task = manager._create_task(
            manager.long_running_task("weak"), name="weak_task", persistent=False
        )

        # Create persistent task
        persistent_task = manager._create_task(
            manager.long_running_task("persistent"),
            name="persistent_task",
            persistent=True,
        )

        # Persistent task should be in persistent set
        assert persistent_task in manager._persistent_tasks
        assert weak_task not in manager._persistent_tasks

        # Both should be tracked
        stats = manager.get_task_stats()
        assert stats["total_tasks"] >= 2
        assert stats["persistent_tasks"] == 1

        # Cleanup
        await manager._cleanup_tasks(timeout=0.5)

    async def test_task_completion_callback(self):
        """Test that task completion removes from persistent set."""
        manager = TestTaskManager()

        async def quick_task():
            await asyncio.sleep(0.01)
            return "done"

        # Create persistent task
        task = manager._create_task(quick_task(), name="quick", persistent=True)

        # Task should be in persistent set
        assert task in manager._persistent_tasks

        # Wait for completion
        await task

        # Should be removed from persistent set
        assert task not in manager._persistent_tasks


@pytest.mark.asyncio
class TestRealWorldIntegration:
    """Test integration with real components."""

    async def test_realtime_event_handling_cleanup(self):
        """Test that EventHandlingMixin properly cleans up tasks."""
        from project_x_py.realtime.event_handling import EventHandlingMixin

        class TestEventHandler(EventHandlingMixin):
            def __init__(self):
                super().__init__()
                self._loop = asyncio.get_event_loop()
                self.callbacks = {}
                self._callback_lock = asyncio.Lock()
                self.logger = MagicMock()

            async def disconnect(self):
                pass

        handler = TestEventHandler()

        # Simulate some background tasks
        async def dummy_work():
            await asyncio.sleep(10)

        # Create tasks like the real implementation would
        for i in range(3):
            handler._create_task(dummy_work(), name=f"forward_event_{i}")

        # Check tasks are tracked
        stats = handler.get_task_stats()
        assert stats["pending_tasks"] >= 3

        # Cleanup
        await handler.cleanup()

        # All tasks should be cancelled
        stats = handler.get_task_stats()
        assert stats["cancelled_tasks"] >= 3

    async def test_memory_management_cleanup(self):
        """Test that MemoryManagementMixin properly cleans up tasks."""
        from project_x_py.realtime_data_manager.memory_management import (
            MemoryManagementMixin,
        )

        class TestMemoryManager(MemoryManagementMixin):
            def __init__(self):
                super().__init__()
                self.logger = MagicMock()
                self.is_running = True
                self.cleanup_interval = 0.1
                self.last_cleanup = 0

            async def _periodic_cleanup(self):
                while self.is_running:
                    await asyncio.sleep(self.cleanup_interval)

        manager = TestMemoryManager()

        # Start cleanup task
        manager.start_cleanup_task()

        # Verify task is running
        assert manager._cleanup_task is not None
        assert not manager._cleanup_task.done()

        # Stop cleanup
        manager.is_running = False
        await manager.stop_cleanup_task()

        # Task should be cleaned up
        assert manager._cleanup_task is None
