"""Tests for performance and memory management."""

import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import polars as pl
import psutil
import pytest
import pytz


@pytest.mark.asyncio
class TestPerformanceMemory:
    """Test performance characteristics and memory management."""

    # Removed: relied on legacy `bars` attribute removed in v3 async architecture
    # The RealtimeDataManager now stores data in `data` frames and manages memory internally.

    # Removed: relied on legacy OrderBook constructor signature and direct trades access

    # Removed: relied on legacy synchronous mocking of client internals and no longer reflects async-only API

    async def test_data_processing_latency(self):
        """Test latency of data processing pipeline."""
        from project_x_py.realtime_data_manager import RealtimeDataManager

        mock_client = MagicMock()
        mock_realtime = MagicMock()

        manager = RealtimeDataManager(
            instrument="MNQ",
            project_x=mock_client,
            realtime_client=mock_realtime,
        )

        # Measure tick processing time
        tick_data = {
            "timestamp": datetime.now(pytz.UTC).isoformat(),
            "price": 15500.0,
            "volume": 10,
        }

        start_time = time.perf_counter()
        # Updated for v3: use public quote update path which internally processes ticks
        await manager._on_quote_update(
            {"data": {"symbol": "MNQ", "bestBid": 15500.0, "bestAsk": 15500.0}}
        )
        processing_time = time.perf_counter() - start_time

        # Should process in under 10ms
        assert processing_time < 0.01

    async def test_callback_execution_performance(self):
        """Test performance of callback execution."""
        from project_x_py.realtime import ProjectXRealtimeClient

        # Create client with mocked dependencies
        client = ProjectXRealtimeClient(
            jwt_token="test",
            account_id="12345",
        )

        # Track callback execution times
        execution_times = []

        async def test_callback(data):
            start = time.perf_counter()
            # Simulate some work
            await asyncio.sleep(0.001)
            execution_times.append(time.perf_counter() - start)

        # Add multiple callbacks
        for _i in range(10):
            await client.add_callback("test_event", test_callback)

        # Trigger callbacks
        start_time = time.perf_counter()
        await client._trigger_callbacks("test_event", {"test": "data"})
        total_time = time.perf_counter() - start_time

        # Should execute all callbacks efficiently
        assert len(execution_times) == 10
        # Total time should be reasonable (callbacks run concurrently)
        assert total_time < 0.1

    async def test_memory_leak_prevention(self):
        """Test that there are no memory leaks in long-running operations."""
        from project_x_py.position_manager import PositionManager

        mock_client = MagicMock()
        mock_realtime = MagicMock()

        manager = PositionManager(mock_client, mock_realtime)

        # Get initial memory usage
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Perform many operations
        for i in range(1000):
            # Add and remove positions
            manager.tracked_positions[f"POS_{i}"] = {
                "contractId": f"POS_{i}",
                "size": 1,
                "averagePrice": 100.0,
            }

            if i > 100:
                # Remove old positions
                old_key = f"POS_{i - 100}"
                if old_key in manager.tracked_positions:
                    del manager.tracked_positions[old_key]

        # Force garbage collection
        import gc

        gc.collect()

        # Check memory usage
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory

        # Memory increase should be minimal (< 50 MB)
        assert memory_increase < 50

    async def test_large_dataset_handling(self):
        """Test handling of large datasets efficiently."""
        from project_x_py.indicators import MACD, RSI, SMA

        # Create large dataset
        size = 10000
        df = pl.DataFrame(
            {
                "timestamp": [
                    datetime.now(pytz.UTC) - timedelta(minutes=i) for i in range(size)
                ],
                "open": [15500.0 + i * 0.1 for i in range(size)],
                "high": [15550.0 + i * 0.1 for i in range(size)],
                "low": [15450.0 + i * 0.1 for i in range(size)],
                "close": [15525.0 + i * 0.1 for i in range(size)],
                "volume": [100 + i for i in range(size)],
            }
        )

        # Apply multiple indicators
        start_time = time.perf_counter()

        result = df.pipe(SMA, period=20).pipe(RSI, period=14).pipe(MACD)

        processing_time = time.perf_counter() - start_time

        # Should process large dataset efficiently (< 1 second)
        assert processing_time < 1.0
        assert len(result) == size

    async def test_connection_pool_efficiency(self):
        """Test HTTP connection pool efficiency."""
        from project_x_py import ProjectX

        client = ProjectX(api_key="test", username="test")
        client._authenticated = True

        # Mock the HTTP client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = lambda: {"success": True, "data": []}

        client._client = MagicMock()
        client._client.request = AsyncMock(return_value=mock_response)

        # Make multiple requests
        start_time = time.perf_counter()

        tasks = []
        for i in range(20):
            task = client._make_request("GET", f"/test/endpoint/{i}")
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        elapsed_time = time.perf_counter() - start_time

        # Should reuse connections efficiently (< 1 second for 20 requests)
        assert elapsed_time < 1.0
        assert all(r["success"] for r in results)

    # Removed: legacy cache performance test relied on previous API behaviors and network mocking patterns

    async def test_event_bus_performance(self):
        """Test EventBus performance with many subscribers."""
        from project_x_py import EventBus

        bus = EventBus()

        # Track callback executions
        callback_count = 0

        async def test_handler(event):
            nonlocal callback_count
            callback_count += 1

        # Subscribe many handlers
        for i in range(100):
            await bus.subscribe(f"handler_{i}", "test_event", test_handler)

        # Emit event
        start_time = time.perf_counter()
        await bus.emit("test_event", {"data": "test"})
        emit_time = time.perf_counter() - start_time

        # Should handle all subscribers efficiently
        assert callback_count == 100
        assert emit_time < 0.1  # Under 100ms for 100 handlers

    async def test_sliding_window_efficiency(self):
        """Test sliding window operations efficiency."""
        from collections import deque

        # Test deque performance for sliding windows
        window_size = 1000
        window = deque(maxlen=window_size)

        # Add many items
        start_time = time.perf_counter()
        for i in range(10000):
            window.append({"value": i})
        append_time = time.perf_counter() - start_time

        # Should maintain fixed size efficiently
        assert len(window) == window_size
        assert append_time < 0.1  # Under 100ms for 10k operations

    async def test_concurrent_position_updates(self):
        """Test handling concurrent position updates efficiently."""
        from project_x_py.position_manager import PositionManager

        mock_client = MagicMock()
        mock_realtime = MagicMock()

        manager = PositionManager(mock_client, mock_realtime)

        # Simulate concurrent position updates
        async def update_position(contract_id, size):
            async with manager.position_lock:
                manager.tracked_positions[contract_id] = {
                    "contractId": contract_id,
                    "size": size,
                    "averagePrice": 100.0,
                }

        # Create many concurrent updates
        start_time = time.perf_counter()

        tasks = []
        for i in range(100):
            task = update_position(f"POS_{i}", i)
            tasks.append(task)

        await asyncio.gather(*tasks)

        elapsed_time = time.perf_counter() - start_time

        # Should handle concurrent updates efficiently
        assert len(manager.tracked_positions) == 100
        assert elapsed_time < 1.0  # Under 1 second for 100 updates

    async def test_orderbook_update_performance(self):
        """Test orderbook update performance."""
        # Removed: legacy constructor/signature; covered by orderbook realtime tests
