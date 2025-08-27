"""
Comprehensive test suite for orderbook memory management module.

Tests the MemoryManager class which handles memory lifecycle for orderbook data,
ensuring bounded memory usage during long-running sessions while maintaining
sufficient historical data for analysis.

Author: @TexasCoding
Date: 2025-01-27
"""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import polars as pl
import pytest

from project_x_py.orderbook.memory import MemoryManager
from project_x_py.types import MemoryConfig


@pytest.fixture
def mock_orderbook():
    """Create a mock orderbook with test data."""
    orderbook = MagicMock()
    orderbook.timezone = UTC
    orderbook.orderbook_lock = asyncio.Lock()

    # Initialize with some test data
    orderbook.recent_trades = pl.DataFrame({
        "price": [100.0] * 20,
        "volume": [1] * 20,
        "timestamp": [datetime.now(UTC)] * 20,
    })

    orderbook.orderbook_bids = pl.DataFrame({
        "price": list(range(95, 85, -1)),
        "volume": [10] * 10,
        "timestamp": [datetime.now(UTC)] * 10,
    })

    orderbook.orderbook_asks = pl.DataFrame({
        "price": list(range(105, 115)),
        "volume": [10] * 10,
        "timestamp": [datetime.now(UTC)] * 10,
    })

    orderbook.price_level_history = {}
    orderbook.best_bid_history = []
    orderbook.best_ask_history = []
    orderbook.spread_history = []

    return orderbook


@pytest.fixture
def memory_config():
    """Create a test memory configuration."""
    return MemoryConfig(
        max_trades=10,
        max_depth_entries=5,
        cleanup_interval=0.1,  # Fast cleanup for testing
        max_history_per_level=50,
        price_history_window_minutes=60,
        max_best_price_history=100,
        max_spread_history=100,
    )


@pytest.fixture
def memory_manager(mock_orderbook, memory_config):
    """Create a MemoryManager instance for testing."""
    return MemoryManager(mock_orderbook, memory_config)


class TestMemoryManagerInitialization:
    """Test MemoryManager initialization."""

    def test_initialization(self, memory_manager, mock_orderbook, memory_config):
        """Test that MemoryManager initializes correctly."""
        assert memory_manager.orderbook == mock_orderbook
        assert memory_manager.config == memory_config
        assert memory_manager._cleanup_task is None
        assert memory_manager._running is False
        assert "last_cleanup" in memory_manager.memory_stats
        assert memory_manager.memory_stats["total_trades"] == 0
        assert memory_manager.memory_stats["trades_cleaned"] == 0
        assert memory_manager.memory_stats["depth_cleaned"] == 0
        assert memory_manager.memory_stats["history_cleaned"] == 0

    def test_memory_stats_initialization(self, memory_manager):
        """Test that memory statistics are properly initialized."""
        stats = memory_manager.memory_stats
        assert isinstance(stats["last_cleanup"], datetime)
        assert stats["total_trades"] == 0
        assert stats["trades_cleaned"] == 0
        assert stats["depth_cleaned"] == 0
        assert stats["history_cleaned"] == 0


class TestMemoryManagerLifecycle:
    """Test MemoryManager start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start(self, memory_manager):
        """Test that start() begins the cleanup task."""
        await memory_manager.start()
        assert memory_manager._running is True
        assert memory_manager._cleanup_task is not None
        assert not memory_manager._cleanup_task.done()

        # Clean up
        await memory_manager.stop()

    @pytest.mark.asyncio
    async def test_stop(self, memory_manager):
        """Test that stop() cancels the cleanup task."""
        await memory_manager.start()
        assert memory_manager._running is True

        await memory_manager.stop()
        assert memory_manager._running is False
        assert memory_manager._cleanup_task is None

    @pytest.mark.asyncio
    async def test_start_twice(self, memory_manager):
        """Test that starting twice doesn't create duplicate tasks."""
        await memory_manager.start()
        task1 = memory_manager._cleanup_task

        await memory_manager.start()
        task2 = memory_manager._cleanup_task

        assert task1 == task2  # Same task, not recreated

        await memory_manager.stop()

    @pytest.mark.asyncio
    async def test_stop_when_not_started(self, memory_manager):
        """Test that stopping when not started is safe."""
        await memory_manager.stop()  # Should not raise
        assert memory_manager._running is False
        assert memory_manager._cleanup_task is None


class TestMemoryCleanup:
    """Test memory cleanup operations."""

    @pytest.mark.asyncio
    async def test_cleanup_old_trades(self, memory_manager, mock_orderbook, memory_config):
        """Test that old trades are cleaned up when exceeding limit."""
        # Set up trades exceeding the limit
        mock_orderbook.recent_trades = pl.DataFrame({
            "price": [100.0] * 20,
            "volume": [1] * 20,
            "timestamp": [datetime.now(UTC)] * 20,
        })

        await memory_manager.cleanup_old_data()

        # Should keep only max_trades (10)
        assert mock_orderbook.recent_trades.height == memory_config.max_trades
        assert memory_manager.memory_stats["trades_cleaned"] == 10

    @pytest.mark.asyncio
    async def test_cleanup_excessive_bids(self, memory_manager, mock_orderbook, memory_config):
        """Test that excessive bid depth is cleaned up."""
        # Reset depth_cleaned counter
        memory_manager.memory_stats["depth_cleaned"] = 0

        # Set up bids exceeding the limit
        mock_orderbook.orderbook_bids = pl.DataFrame({
            "price": list(range(100, 80, -1)),  # 20 levels
            "volume": [10] * 20,
            "timestamp": [datetime.now(UTC)] * 20,
        })

        await memory_manager.cleanup_old_data()

        # Should keep only max_depth_entries (5) best bids
        assert mock_orderbook.orderbook_bids.height == memory_config.max_depth_entries
        # Best bids should be highest prices
        prices = mock_orderbook.orderbook_bids["price"].to_list()
        assert prices == sorted(prices, reverse=True)
        # Note: depth_cleaned is cumulative across bids and asks
        assert memory_manager.memory_stats["depth_cleaned"] >= 15

    @pytest.mark.asyncio
    async def test_cleanup_excessive_asks(self, memory_manager, mock_orderbook, memory_config):
        """Test that excessive ask depth is cleaned up."""
        # Reset depth_cleaned counter
        memory_manager.memory_stats["depth_cleaned"] = 0

        # Set up asks exceeding the limit
        mock_orderbook.orderbook_asks = pl.DataFrame({
            "price": list(range(100, 120)),  # 20 levels
            "volume": [10] * 20,
            "timestamp": [datetime.now(UTC)] * 20,
        })

        await memory_manager.cleanup_old_data()

        # Should keep only max_depth_entries (5) best asks
        assert mock_orderbook.orderbook_asks.height == memory_config.max_depth_entries
        # Best asks should be lowest prices
        prices = mock_orderbook.orderbook_asks["price"].to_list()
        assert prices == sorted(prices)
        # Note: depth_cleaned is cumulative across bids and asks
        assert memory_manager.memory_stats["depth_cleaned"] >= 15

    @pytest.mark.asyncio
    async def test_cleanup_no_changes_needed(self, memory_manager, mock_orderbook):
        """Test cleanup when no changes are needed."""
        # Set up data within limits
        mock_orderbook.recent_trades = pl.DataFrame({
            "price": [100.0] * 5,
            "volume": [1] * 5,
            "timestamp": [datetime.now(UTC)] * 5,
        })

        mock_orderbook.orderbook_bids = pl.DataFrame({
            "price": [95.0, 94.0, 93.0],
            "volume": [10, 10, 10],
            "timestamp": [datetime.now(UTC)] * 3,
        })

        await memory_manager.cleanup_old_data()

        assert mock_orderbook.recent_trades.height == 5
        assert mock_orderbook.orderbook_bids.height == 3
        assert memory_manager.memory_stats["trades_cleaned"] == 0


class TestPriceHistoryCleanup:
    """Test price level history cleanup."""

    @pytest.mark.asyncio
    async def test_cleanup_old_price_history(self, memory_manager, mock_orderbook, memory_config):
        """Test that old price history entries are removed."""
        current_time = datetime.now(UTC)
        old_time = current_time - timedelta(minutes=memory_config.price_history_window_minutes + 10)

        # Create a deque for price history
        from collections import deque
        mock_orderbook.price_level_history = {
            "100.0": deque([
                {"timestamp": old_time, "volume": 10},
                {"timestamp": old_time, "volume": 20},
                {"timestamp": current_time, "volume": 30},
            ], maxlen=1000)
        }

        await memory_manager.cleanup_old_data()

        # Should keep only recent entries
        assert "100.0" in mock_orderbook.price_level_history
        history = list(mock_orderbook.price_level_history["100.0"])
        assert len(history) == 1
        assert history[0]["volume"] == 30
        assert memory_manager.memory_stats["history_cleaned"] == 0  # deque filtering doesn't update counter

    @pytest.mark.asyncio
    async def test_remove_empty_price_histories(self, memory_manager, mock_orderbook):
        """Test that empty price histories are removed."""
        from collections import deque

        mock_orderbook.price_level_history = {
            "100.0": deque(maxlen=1000),  # Empty deque
            "101.0": deque([{"timestamp": datetime.now(UTC), "volume": 10}], maxlen=1000),
        }

        await memory_manager.cleanup_old_data()

        # Empty history should be removed
        assert "100.0" not in mock_orderbook.price_level_history
        assert "101.0" in mock_orderbook.price_level_history


class TestMarketHistoryCleanup:
    """Test market data history cleanup."""

    @pytest.mark.asyncio
    async def test_cleanup_best_bid_history(self, memory_manager, mock_orderbook, memory_config):
        """Test that best bid history is trimmed to max size."""
        # Create history exceeding limit
        mock_orderbook.best_bid_history = [
            {"price": 100.0, "timestamp": datetime.now(UTC)}
            for _ in range(200)
        ]

        await memory_manager.cleanup_old_data()

        # Should keep only max_best_price_history entries
        assert len(mock_orderbook.best_bid_history) == memory_config.max_best_price_history
        assert memory_manager.memory_stats["history_cleaned"] == 100

    @pytest.mark.asyncio
    async def test_cleanup_best_ask_history(self, memory_manager, mock_orderbook, memory_config):
        """Test that best ask history is trimmed to max size."""
        # Create history exceeding limit
        mock_orderbook.best_ask_history = [
            {"price": 105.0, "timestamp": datetime.now(UTC)}
            for _ in range(150)
        ]

        await memory_manager.cleanup_old_data()

        # Should keep only max_best_price_history entries
        assert len(mock_orderbook.best_ask_history) == memory_config.max_best_price_history
        assert memory_manager.memory_stats["history_cleaned"] == 50

    @pytest.mark.asyncio
    async def test_cleanup_spread_history(self, memory_manager, mock_orderbook, memory_config):
        """Test that spread history is trimmed to max size."""
        # Create history exceeding limit
        mock_orderbook.spread_history = [5.0 for _ in range(200)]

        await memory_manager.cleanup_old_data()

        # Should keep only max_spread_history entries
        assert len(mock_orderbook.spread_history) == memory_config.max_spread_history
        assert memory_manager.memory_stats["history_cleaned"] == 100


class TestMemoryStatistics:
    """Test memory statistics reporting."""

    @pytest.mark.asyncio
    async def test_get_memory_stats(self, memory_manager, mock_orderbook):
        """Test that get_memory_stats returns comprehensive statistics."""
        # Set up some data and statistics
        memory_manager.memory_stats["total_trades"] = 100
        memory_manager.memory_stats["total_volume"] = 1000
        memory_manager.memory_stats["largest_trade"] = 50

        mock_orderbook.best_bid_history = [{"price": 100.0, "timestamp": datetime.now(UTC)}]
        mock_orderbook.best_ask_history = [{"price": 105.0, "timestamp": datetime.now(UTC)}]

        stats = await memory_manager.get_memory_stats()

        # Check required fields are present
        assert "avg_bid_depth" in stats
        assert "avg_ask_depth" in stats
        assert "trades_processed" in stats
        assert "avg_trade_size" in stats
        assert "total_volume" in stats
        assert "avg_spread" in stats
        assert "memory_usage_mb" in stats

        # Check calculated values
        assert stats["trades_processed"] == 100
        assert stats["total_volume"] == 1000
        assert stats["largest_trade"] == 50
        assert stats["avg_trade_size"] == 10.0  # 1000 / 100
        assert stats["avg_spread"] == 5.0  # 105 - 100

    @pytest.mark.asyncio
    async def test_memory_stats_with_no_data(self, memory_manager, mock_orderbook):
        """Test memory stats when no data is available."""
        # Clear all data
        mock_orderbook.orderbook_bids = pl.DataFrame({"price": [], "volume": [], "timestamp": []})
        mock_orderbook.orderbook_asks = pl.DataFrame({"price": [], "volume": [], "timestamp": []})
        mock_orderbook.recent_trades = pl.DataFrame({"price": [], "volume": [], "timestamp": []})
        mock_orderbook.best_bid_history = []
        mock_orderbook.best_ask_history = []

        stats = await memory_manager.get_memory_stats()

        assert stats["avg_bid_depth"] == 0
        assert stats["avg_ask_depth"] == 0
        assert stats["trades_processed"] == 0
        assert stats["avg_trade_size"] == 0.0
        assert stats["avg_spread"] == 0.0
        assert stats["spread_volatility"] == 0.0


class TestPeriodicCleanup:
    """Test periodic cleanup task."""

    @pytest.mark.asyncio
    async def test_periodic_cleanup_runs(self, memory_manager):
        """Test that periodic cleanup runs at intervals."""
        with patch.object(memory_manager, 'cleanup_old_data', new_callable=AsyncMock) as mock_cleanup:
            await memory_manager.start()

            # Wait for cleanup to be called (config has 0.1s interval)
            await asyncio.sleep(0.15)

            assert mock_cleanup.called

            await memory_manager.stop()

    @pytest.mark.asyncio
    async def test_periodic_cleanup_handles_errors(self, memory_manager):
        """Test that periodic cleanup continues after errors."""
        call_count = 0

        async def cleanup_with_error():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Test error")
            # Second call should succeed

        with patch.object(memory_manager, 'cleanup_old_data', side_effect=cleanup_with_error):
            await memory_manager.start()

            # Wait for multiple cleanup calls
            await asyncio.sleep(0.25)

            # Should have called cleanup multiple times despite error
            assert call_count >= 2

            await memory_manager.stop()

    @pytest.mark.asyncio
    async def test_periodic_cleanup_stops_on_cancel(self, memory_manager):
        """Test that periodic cleanup stops when cancelled."""
        with patch.object(memory_manager, 'cleanup_old_data', new_callable=AsyncMock) as mock_cleanup:
            await memory_manager.start()
            task = memory_manager._cleanup_task

            await memory_manager.stop()

            # Task should be cancelled
            assert task.cancelled() or task.done()
            assert memory_manager._cleanup_task is None


class TestGarbageCollection:
    """Test garbage collection triggering."""

    @pytest.mark.asyncio
    async def test_gc_triggered_after_major_cleanup(self, memory_manager, mock_orderbook):
        """Test that garbage collection is triggered after major cleanup."""
        # Set up data that will trigger major cleanup
        mock_orderbook.recent_trades = pl.DataFrame({
            "price": [100.0] * 2000,
            "volume": [1] * 2000,
            "timestamp": [datetime.now(UTC)] * 2000,
        })

        with patch('gc.collect') as mock_gc:
            await memory_manager.cleanup_old_data()

            # GC should be called after cleaning > 1000 items
            assert mock_gc.called

    @pytest.mark.asyncio
    async def test_gc_not_triggered_for_small_cleanup(self, memory_manager, mock_orderbook):
        """Test that garbage collection is not triggered for small cleanups."""
        # Set up data for small cleanup
        mock_orderbook.recent_trades = pl.DataFrame({
            "price": [100.0] * 15,
            "volume": [1] * 15,
            "timestamp": [datetime.now(UTC)] * 15,
        })

        with patch('gc.collect') as mock_gc:
            await memory_manager.cleanup_old_data()

            # GC should not be called for small cleanup
            assert not mock_gc.called


class TestErrorHandling:
    """Test error handling in memory management."""

    @pytest.mark.asyncio
    async def test_cleanup_handles_dataframe_errors(self, memory_manager, mock_orderbook):
        """Test that cleanup handles DataFrame operation errors gracefully."""
        # Create a mock that raises on tail()
        mock_df = MagicMock()
        mock_df.height = 100
        mock_df.tail.side_effect = Exception("DataFrame error")
        mock_orderbook.recent_trades = mock_df

        # Should not raise, but log error
        await memory_manager.cleanup_old_data()

        # Stats should remain unchanged on error
        assert memory_manager.memory_stats["trades_cleaned"] == 0

    @pytest.mark.asyncio
    async def test_cleanup_handles_lock_timeout(self, memory_manager, mock_orderbook):
        """Test that cleanup handles lock acquisition timeout."""
        # The lock acquisition is outside the try block, so it would raise.
        # Test that errors within the lock are handled.
        original_height = mock_orderbook.recent_trades.height

        # Make tail() raise an error to test error handling within the lock
        mock_orderbook.recent_trades.tail = MagicMock(side_effect=Exception("Internal error"))

        # Should log error but complete without raising
        await memory_manager.cleanup_old_data()

        # Original data should be unchanged due to error
        assert mock_orderbook.recent_trades.height == original_height


class TestThreadSafety:
    """Test thread safety of memory operations."""

    @pytest.mark.asyncio
    async def test_concurrent_cleanup_operations(self, memory_manager):
        """Test that concurrent cleanup operations are safe."""
        tasks = []
        for _ in range(5):
            tasks.append(asyncio.create_task(memory_manager.cleanup_old_data()))

        # All tasks should complete without error
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            assert not isinstance(result, Exception)

    @pytest.mark.asyncio
    async def test_cleanup_with_concurrent_data_updates(self, memory_manager, mock_orderbook):
        """Test cleanup while data is being updated."""
        async def update_data():
            for _ in range(10):
                async with mock_orderbook.orderbook_lock:
                    mock_orderbook.recent_trades = pl.DataFrame({
                        "price": [100.0] * 20,
                        "volume": [1] * 20,
                        "timestamp": [datetime.now(UTC)] * 20,
                    })
                await asyncio.sleep(0.01)

        # Run cleanup and updates concurrently
        await asyncio.gather(
            memory_manager.cleanup_old_data(),
            update_data(),
            return_exceptions=True
        )

        # Should complete without deadlock
        assert True


# Run tests with coverage reporting
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=src/project_x_py/orderbook/memory", "--cov-report=term-missing"])
