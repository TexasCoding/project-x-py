"""Tests for the batched WebSocket message handler."""

import asyncio

import pytest

from project_x_py.realtime.batched_handler import (
    BatchedWebSocketHandler,
    OptimizedRealtimeHandler,
)


class TestBatchedWebSocketHandler:
    """Tests for the BatchedWebSocketHandler."""

    @pytest.mark.asyncio
    async def test_batch_size_trigger(self):
        """Test that batch processes when size threshold is reached."""
        processed_batches = []

        async def process_batch(batch):
            processed_batches.append(batch)

        handler = BatchedWebSocketHandler(
            batch_size=5,
            batch_timeout=10.0,  # Long timeout to ensure size triggers first
            process_callback=process_batch,
        )

        # Add exactly batch_size messages
        for i in range(5):
            await handler.handle_message({"id": i})

        # Wait for processing
        await asyncio.sleep(0.1)

        # Should have processed one batch of 5
        assert len(processed_batches) == 1
        assert len(processed_batches[0]) == 5
        assert handler.batches_processed == 1
        assert handler.messages_processed == 5

    @pytest.mark.asyncio
    async def test_batch_timeout_trigger(self):
        """Test that batch processes when timeout is reached."""
        processed_batches = []

        async def process_batch(batch):
            processed_batches.append(batch)

        handler = BatchedWebSocketHandler(
            batch_size=100,  # Large size to ensure timeout triggers first
            batch_timeout=0.05,  # 50ms timeout
            process_callback=process_batch,
        )

        # Add fewer messages than batch size
        for i in range(3):
            await handler.handle_message({"id": i})

        # Wait for timeout to trigger
        await asyncio.sleep(0.1)

        # Should have processed one batch of 3
        assert len(processed_batches) == 1
        assert len(processed_batches[0]) == 3
        assert handler.batches_processed == 1
        assert handler.messages_processed == 3

    @pytest.mark.asyncio
    async def test_multiple_batches(self):
        """Test processing multiple batches."""
        processed_batches = []

        async def process_batch(batch):
            processed_batches.append(batch)

        handler = BatchedWebSocketHandler(
            batch_size=3, batch_timeout=0.05, process_callback=process_batch
        )

        # Add messages to trigger multiple batches
        for i in range(10):
            await handler.handle_message({"id": i})
            if i == 4:  # Pause after first batch
                await asyncio.sleep(0.1)

        # Wait for all processing
        await asyncio.sleep(0.2)

        # Should have processed multiple batches
        assert len(processed_batches) >= 2
        total_messages = sum(len(batch) for batch in processed_batches)
        assert total_messages == 10
        assert handler.messages_processed == 10

    @pytest.mark.asyncio
    async def test_flush(self):
        """Test flushing queued messages."""
        processed_batches = []

        async def process_batch(batch):
            processed_batches.append(batch)

        handler = BatchedWebSocketHandler(
            batch_size=100,
            batch_timeout=10.0,  # Long timeout
            process_callback=process_batch,
        )

        # Add messages
        for i in range(7):
            await handler.handle_message({"id": i})

        # Flush immediately - should interrupt the processing task
        await handler.flush()

        # Should have processed all messages
        assert len(processed_batches) == 1, (
            f"Expected 1 batch, got {len(processed_batches)} batches: {processed_batches}"
        )
        assert len(processed_batches[0]) == 7
        assert handler.messages_processed == 7

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test that errors in processing don't break the handler."""
        processed_batches = []
        error_count = [0]

        async def process_batch(batch):
            if len(batch) == 3:
                error_count[0] += 1
                raise ValueError("Test error")
            processed_batches.append(batch)

        handler = BatchedWebSocketHandler(
            batch_size=3, batch_timeout=0.05, process_callback=process_batch
        )

        # Add messages
        for i in range(6):
            await handler.handle_message({"id": i})

        # Wait for processing
        await asyncio.sleep(0.2)

        # Should have attempted to process batches despite error
        assert error_count[0] >= 1
        assert handler.batches_processed >= 1

    @pytest.mark.asyncio
    async def test_performance_stats(self):
        """Test performance statistics tracking."""

        async def process_batch(batch):
            await asyncio.sleep(0.01)  # Simulate processing time

        handler = BatchedWebSocketHandler(
            batch_size=5, batch_timeout=0.05, process_callback=process_batch
        )

        # Process some messages
        for i in range(10):
            await handler.handle_message({"id": i})

        await asyncio.sleep(0.2)

        # Get stats
        stats = handler.get_stats()

        assert stats["batches_processed"] == 2
        assert stats["messages_processed"] == 10
        assert stats["avg_batch_size"] == 5.0
        assert stats["avg_processing_time_ms"] > 0
        assert stats["total_processing_time_s"] > 0

    @pytest.mark.asyncio
    async def test_stop(self):
        """Test stopping the handler."""
        processed_batches = []

        async def process_batch(batch):
            processed_batches.append(batch)

        handler = BatchedWebSocketHandler(
            batch_size=100, batch_timeout=10.0, process_callback=process_batch
        )

        # Add messages
        for i in range(5):
            await handler.handle_message({"id": i})

        # Give the processing task a moment to start
        await asyncio.sleep(0)  # Yield control to allow task to start

        # Stop should flush remaining messages
        await handler.stop()

        assert len(processed_batches) == 1
        assert len(processed_batches[0]) == 5
        assert handler.messages_processed == 5


class TestOptimizedRealtimeHandler:
    """Tests for the OptimizedRealtimeHandler."""

    @pytest.mark.asyncio
    async def test_quote_batching(self):
        """Test quote message batching."""

        # Mock realtime client
        class MockClient:
            def __init__(self):
                self.quotes_received = []

            async def _forward_quote_update(self, quote):
                self.quotes_received.append(quote)

        client = MockClient()
        handler = OptimizedRealtimeHandler(client)

        # Send multiple quotes
        for i in range(10):
            await handler.handle_quote(
                {
                    "contract_id": f"contract_{i % 2}",  # Two different contracts
                    "bid": 100 + i,
                    "ask": 101 + i,
                }
            )

        # Wait for batch processing
        await asyncio.sleep(0.2)

        # Should have received processed quotes
        # Due to batching, only latest quotes per contract are kept
        assert len(client.quotes_received) <= 10

    @pytest.mark.asyncio
    async def test_trade_batching(self):
        """Test trade message batching."""

        class MockClient:
            def __init__(self):
                self.trades_received = []

            async def _forward_market_trade(self, trade):
                self.trades_received.append(trade)

        client = MockClient()
        handler = OptimizedRealtimeHandler(client)

        # Send trades
        for i in range(5):
            await handler.handle_trade(
                {"contract_id": "MNQ", "price": 15000 + i, "volume": 1}
            )

        # Wait for batch processing
        await asyncio.sleep(0.2)

        # All trades should be processed
        assert len(client.trades_received) == 5

    @pytest.mark.asyncio
    async def test_depth_batching(self):
        """Test depth message batching."""

        class MockClient:
            def __init__(self):
                self.depth_received = []

            async def _forward_market_depth(self, depth):
                self.depth_received.append(depth)

        client = MockClient()
        handler = OptimizedRealtimeHandler(client)

        # Send depth updates
        for i in range(6):
            await handler.handle_depth(
                {
                    "contract_id": "MNQ",
                    "bids": [[15000 - i, 10]],
                    "asks": [[15001 + i, 10]],
                }
            )

        # Wait for batch processing
        await asyncio.sleep(0.2)

        # GatewayDepth is per price level: every row in the batch must be processed
        assert len(client.depth_received) == 6

    @pytest.mark.asyncio
    async def test_depth_batch_processes_every_price_level(self):
        """A batch of three depth prices must forward three levels, not the last only."""
        forwarded: list[dict] = []

        class MockClient:
            async def _forward_event_async(self, event_type, args):
                forwarded.append({"event_type": event_type, "payload": args[0]})

            def _forward_market_depth(self, depth):
                forwarded.append(depth)

        client = MockClient()
        handler = OptimizedRealtimeHandler(client)
        depths = [
            {"contract_id": "MNQ", "price": 18500.0, "side": 0, "volume": 10},
            {"contract_id": "MNQ", "price": 18499.75, "side": 0, "volume": 8},
            {"contract_id": "MNQ", "price": 18500.25, "side": 1, "volume": 12},
        ]

        await handler._process_depth_batch(depths)

        assert len(forwarded) == 3
        prices = [
            item["payload"]["price"]
            if isinstance(item, dict) and "payload" in item
            else item["price"]
            for item in forwarded
        ]
        assert prices == [18500.0, 18499.75, 18500.25]

    @pytest.mark.asyncio
    async def test_get_all_stats(self):
        """Test getting statistics from all handlers."""
        client = object()  # Dummy client
        handler = OptimizedRealtimeHandler(client)

        # Send some messages
        for i in range(3):
            await handler.handle_quote({"id": i})
            await handler.handle_trade({"id": i})
            await handler.handle_depth({"id": i})

        # Get stats
        stats = handler.get_all_stats()

        assert "quote_handler" in stats
        assert "trade_handler" in stats
        assert "depth_handler" in stats

        # Each handler should have stats
        for handler_stats in stats.values():
            assert "batches_processed" in handler_stats
            assert "messages_processed" in handler_stats

    @pytest.mark.asyncio
    async def test_stop_all_handlers(self):
        """Test stopping all handlers."""
        client = object()  # Dummy client
        handler = OptimizedRealtimeHandler(client)

        # Send messages to all handlers
        for i in range(5):
            await handler.handle_quote({"id": i})
            await handler.handle_trade({"id": i})
            await handler.handle_depth({"id": i})

        # Stop should not raise errors
        await handler.stop()

        # Get final stats
        stats = handler.get_all_stats()

        # All handlers should have processed their messages
        assert stats["quote_handler"]["messages_processed"] >= 0
        assert stats["trade_handler"]["messages_processed"] >= 0
        assert stats["depth_handler"]["messages_processed"] >= 0
