"""
Batched WebSocket message handler for improved throughput.

This module provides high-performance message batching for WebSocket data,
reducing overhead and improving throughput by processing messages in batches.

FIXED: Configurable poll interval to reduce CPU usage.
See: https://github.com/TexasCoding/project-x-py/issues/82
"""

import asyncio
import contextlib
import time
from collections import deque
from collections.abc import Callable, Coroutine
from typing import Any

from project_x_py.utils import ProjectXLogger

logger = ProjectXLogger.get_logger(__name__)


class BatchedWebSocketHandler:
    """
    High-performance batched message handler for WebSocket connections.

    This handler collects messages into batches and processes them together,
    reducing overhead from individual message processing and improving throughput.

    Features:
        - Configurable batch size and timeout
        - Configurable poll interval for CPU efficiency
        - Automatic batch processing when size or time threshold is reached
        - Non-blocking message queueing
        - Graceful error handling per batch
        - Performance metrics tracking
    """

    # Default poll interval when waiting for messages (in seconds)
    # Higher values = lower CPU usage but slightly higher latency
    # 0.05s (50ms) provides good balance between responsiveness and CPU efficiency
    DEFAULT_POLL_INTERVAL = 0.05  # Changed from 0.01 (10ms) to reduce CPU usage

    def __init__(
        self,
        batch_size: int = 100,
        batch_timeout: float = 0.1,
        poll_interval: float | None = None,  # NEW: Configurable poll interval
        process_callback: Callable[[list[dict[str, Any]]], Coroutine[Any, Any, None]]
        | None = None,
    ):
        """
        Initialize the batched WebSocket handler.

        Args:
            batch_size: Maximum number of messages per batch (default: 100)
            batch_timeout: Maximum time to wait for batch to fill in seconds (default: 0.1)
            poll_interval: Interval for polling when queue is empty (default: 0.05s)
                          Lower values = more responsive but higher CPU usage
                          Higher values = lower CPU usage but slightly higher latency
            process_callback: Async callback to process message batches
        """
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.poll_interval = poll_interval or self.DEFAULT_POLL_INTERVAL  # NEW
        self.process_callback = process_callback

        # Message queue using deque for O(1) append/popleft
        self.message_queue: deque[dict[str, Any]] = deque(maxlen=10000)
        self.processing = False
        self._processing_task: asyncio.Task[None] | None = None

        # Performance metrics
        self.batches_processed = 0
        self.messages_processed = 0
        self.total_processing_time = 0.0
        self.last_batch_time = time.time()

        # Circuit breaker state
        self.failed_batches = 0
        self.circuit_breaker_tripped_at: float | None = None
        self.circuit_breaker_timeout = 60.0  # 60 seconds

        # Lock for thread safety
        self._lock = asyncio.Lock()

        # Event to signal immediate flush
        self._flush_event = asyncio.Event()

    async def handle_message(self, message: dict[str, Any]) -> None:
        """
        Add a message to the batch queue for processing.

        Args:
            message: WebSocket message to process
        """
        # Add to queue (non-blocking)
        self.message_queue.append(message)

        # Start batch processing if not already running
        if not self.processing and (
            not self._processing_task or self._processing_task.done()
        ):
            self._processing_task = asyncio.create_task(self._process_batch())

    async def _process_batch(self) -> None:
        """Process messages in batches with timeout."""
        async with self._lock:
            if self.processing:
                return

            # Check circuit breaker
            if self.circuit_breaker_tripped_at:
                if (
                    time.time() - self.circuit_breaker_tripped_at
                ) > self.circuit_breaker_timeout:
                    logger.warning("Resetting circuit breaker.")
                    self.circuit_breaker_tripped_at = None
                    self.failed_batches = 0
                else:
                    return  # Circuit breaker is tripped, do not process

            self.processing = True

        try:
            batch: list[dict[str, Any]] = []
            deadline = time.time() + self.batch_timeout

            # Collect messages until batch is full or timeout or flush is requested
            while (
                time.time() < deadline
                and len(batch) < self.batch_size
                and not self._flush_event.is_set()
            ):
                if self.message_queue:
                    # Get all available messages up to batch size
                    while self.message_queue and len(batch) < self.batch_size:
                        batch.append(self.message_queue.popleft())
                else:
                    # Wait a bit for more messages or flush event
                    remaining = deadline - time.time()
                    if remaining > 0:
                        try:
                            # Wait for either timeout or flush event
                            # FIXED: Use configurable poll_interval instead of hardcoded 0.01
                            await asyncio.wait_for(
                                self._flush_event.wait(),
                                timeout=min(self.poll_interval, remaining),
                            )
                            # Flush was triggered, break the loop
                            break
                        except TimeoutError:
                            # Normal timeout, continue
                            pass

            # If flush was triggered, get any remaining messages
            if self._flush_event.is_set():
                while self.message_queue and len(batch) < 10000:  # Safety limit
                    batch.append(self.message_queue.popleft())
                self._flush_event.clear()

            # Process the batch if we have messages
            if batch:
                start_time = time.time()

                if self.process_callback:
                    try:
                        await self.process_callback(batch)
                        # Reset failure count on success
                        self.failed_batches = 0
                    except asyncio.CancelledError:
                        # Re-raise cancellation for proper shutdown
                        raise
                    except Exception as e:
                        logger.error(
                            f"Error processing batch of {len(batch)} messages: {e}",
                            exc_info=True,
                        )
                        # Track failures for circuit breaker
                        self.failed_batches += 1
                        if self.failed_batches > 10:
                            logger.critical(
                                f"Batch processing circuit breaker triggered for {self.circuit_breaker_timeout}s."
                            )
                            self.circuit_breaker_tripped_at = time.time()
                            self.processing = False
                            return  # Stop processing

                # Update metrics
                processing_time = time.time() - start_time
                self.batches_processed += 1
                self.messages_processed += len(batch)
                self.total_processing_time += processing_time
                self.last_batch_time = time.time()

                logger.debug(
                    f"Processed batch: {len(batch)} messages in {processing_time:.3f}s "
                    f"(avg: {processing_time / len(batch) * 1000:.1f}ms/msg)"
                )

        finally:
            self.processing = False

            # If there are still messages, schedule another batch
            if self.message_queue:
                task = asyncio.create_task(self._process_batch())
                # Fire and forget - we don't need to await the task
                task.add_done_callback(lambda t: None)

    async def flush(self) -> None:
        """Force processing of all queued messages immediately."""
        # Signal the processing task to flush immediately
        self._flush_event.set()

        # Wait for the current processing task to complete if it exists
        if self._processing_task and not self._processing_task.done():
            with contextlib.suppress(asyncio.TimeoutError, asyncio.CancelledError):
                await asyncio.wait_for(self._processing_task, timeout=1.0)

        # Process any remaining messages that weren't picked up
        if self.message_queue:
            batch = list(self.message_queue)
            self.message_queue.clear()

            if self.process_callback and batch:
                try:
                    await self.process_callback(batch)
                    self.batches_processed += 1
                    self.messages_processed += len(batch)
                except Exception as e:
                    logger.error(f"Error flushing batch of {len(batch)} messages: {e}")

        # Clear the flush event for next time
        self._flush_event.clear()
        self.processing = False

    def get_stats(self) -> dict[str, Any]:
        """
        Get performance statistics for the batch handler.

        Returns:
            Dict containing performance metrics
        """
        avg_batch_size = (
            self.messages_processed / self.batches_processed
            if self.batches_processed > 0
            else 0
        )
        avg_processing_time = (
            self.total_processing_time / self.batches_processed
            if self.batches_processed > 0
            else 0
        )

        return {
            "batches_processed": self.batches_processed,
            "messages_processed": self.messages_processed,
            "queued_messages": len(self.message_queue),
            "avg_batch_size": avg_batch_size,
            "avg_processing_time_ms": avg_processing_time * 1000,
            "total_processing_time_s": self.total_processing_time,
            "last_batch_timestamp": self.last_batch_time,
            "batch_size_limit": self.batch_size,
            "batch_timeout_ms": self.batch_timeout * 1000,
            "poll_interval_ms": self.poll_interval * 1000,  # NEW
        }

    async def stop(self) -> None:
        """Stop the batch handler and process remaining messages."""
        # Signal flush to trigger immediate processing
        self._flush_event.set()

        # Wait for current processing to complete
        if self._processing_task and not self._processing_task.done():
            try:
                await asyncio.wait_for(self._processing_task, timeout=1.0)
            except (TimeoutError, asyncio.CancelledError):
                self._processing_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._processing_task

        # Process any remaining messages that weren't handled
        await self.flush()

        logger.info(
            f"Batch handler stopped. Processed {self.messages_processed} messages "
            f"in {self.batches_processed} batches"
        )


class OptimizedRealtimeHandler:
    """
    Optimized handler for real-time data with message batching.

    Integrates batched message processing into the real-time client
    for improved performance with high-frequency data streams.
    """

    # Default poll interval for all handlers (can be overridden)
    DEFAULT_POLL_INTERVAL = 0.05  # 50ms - balances responsiveness and CPU usage

    def __init__(self, realtime_client: Any, poll_interval: float | None = None):
        """
        Initialize optimized handler.

        Args:
            realtime_client: The ProjectX realtime client instance
            poll_interval: Optional poll interval override for all handlers
        """
        self.client = realtime_client
        poll_interval = poll_interval or self.DEFAULT_POLL_INTERVAL

        # Create separate batch handlers for different message types
        # FIXED: Use configurable poll_interval for all handlers
        self.quote_handler = BatchedWebSocketHandler(
            batch_size=200,  # Larger batches for quotes
            batch_timeout=0.05,  # 50ms timeout
            poll_interval=poll_interval,  # NEW
            process_callback=self._process_quote_batch,
        )

        self.trade_handler = BatchedWebSocketHandler(
            batch_size=100,
            batch_timeout=0.1,
            poll_interval=poll_interval,  # NEW
            process_callback=self._process_trade_batch,
        )

        self.depth_handler = BatchedWebSocketHandler(
            batch_size=50,  # Smaller batches for depth updates
            batch_timeout=0.1,
            poll_interval=poll_interval,  # NEW
            process_callback=self._process_depth_batch,
        )

    async def handle_quote(self, data: dict[str, Any]) -> None:
        """Handle incoming quote message."""
        await self.quote_handler.handle_message(data)

    async def handle_trade(self, data: dict[str, Any]) -> None:
        """Handle incoming trade message."""
        await self.trade_handler.handle_message(data)

    async def handle_depth(self, data: dict[str, Any]) -> None:
        """Handle incoming depth message."""
        await self.depth_handler.handle_message(data)

    async def _process_quote_batch(self, batch: list[dict[str, Any]]) -> None:
        """Process a batch of quote messages."""
        # Group quotes by contract for efficient processing
        quotes_by_contract: dict[str, list[dict[str, Any]]] = {}
        for quote in batch:
            contract = quote.get("contract_id", "unknown")
            if contract not in quotes_by_contract:
                quotes_by_contract[contract] = []
            quotes_by_contract[contract].append(quote)

        # Process each contract's quotes
        for _contract, quotes in quotes_by_contract.items():
            # Use only the latest quote for each contract (others are stale)
            latest_quote = quotes[-1]

            # Forward to original handlers
            if hasattr(self.client, "_forward_quote_update"):
                await self.client._forward_quote_update(latest_quote)

    async def _process_trade_batch(self, batch: list[dict[str, Any]]) -> None:
        """Process a batch of trade messages."""
        # All trades are important, process them all
        for trade in batch:
            if hasattr(self.client, "_forward_market_trade"):
                await self.client._forward_market_trade(trade)

    async def _process_depth_batch(self, batch: list[dict[str, Any]]) -> None:
        """Process a batch of depth messages."""
        # Group depth updates by contract
        depth_by_contract: dict[str, list[dict[str, Any]]] = {}
        for depth in batch:
            contract = depth.get("contract_id", "unknown")
            if contract not in depth_by_contract:
                depth_by_contract[contract] = []
            depth_by_contract[contract].append(depth)

        # Use only latest depth update per contract
        for _contract, depths in depth_by_contract.items():
            latest_depth = depths[-1]
            if hasattr(self.client, "_forward_market_depth"):
                await self.client._forward_market_depth(latest_depth)

    def get_all_stats(self) -> dict[str, Any]:
        """Get statistics from all batch handlers."""
        return {
            "quote_handler": self.quote_handler.get_stats(),
            "trade_handler": self.trade_handler.get_stats(),
            "depth_handler": self.depth_handler.get_stats(),
        }

    async def stop(self) -> None:
        """Stop all batch handlers."""
        await self.quote_handler.stop()
        await self.trade_handler.stop()
        await self.depth_handler.stop()
