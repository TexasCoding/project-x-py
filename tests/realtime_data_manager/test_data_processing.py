"""
Comprehensive tests for realtime_data_manager.data_processing module.

Following project-x-py TDD methodology:
1. Write tests FIRST defining expected behavior
2. Test what code SHOULD do, not what it currently does
3. Fix implementation if tests reveal bugs
4. Never change tests to match broken code

Test Coverage Goals:
- DataProcessingMixin tick processing functionality
- Quote and trade callback handling
- OHLCV bar creation and updates
- Multi-timeframe processing
- Race condition prevention with fine-grained locking
- Atomic transactions and rollback mechanisms
- Error handling and partial failure recovery
- Memory management and performance optimization
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, Mock, patch, call
from datetime import datetime, timezone
from collections import deque

import polars as pl

from project_x_py.realtime_data_manager.data_processing import DataProcessingMixin
from project_x_py.types.trading import TradeLogType


class MockRealtimeDataManager(DataProcessingMixin):
    """Mock class implementing DataProcessingMixin for testing."""

    def __init__(self, tick_size=0.25, timezone_obj=timezone.utc):
        # Initialize required attributes
        self.tick_size = tick_size
        self.timezone = timezone_obj
        self.logger = Mock()
        self.data_lock = asyncio.Lock()
        self.current_tick_data = deque(maxlen=1000)
        self.timeframes = {
            "1min": {"interval": 1, "unit": 2},  # 1 minute
            "5min": {"interval": 5, "unit": 2},  # 5 minutes
        }
        self.data = {
            "1min": pl.DataFrame(),
            "5min": pl.DataFrame(),
        }
        self.last_bar_times = {}
        self.memory_stats = {"ticks_processed": 0}
        self.is_running = True

        # Initialize parent
        super().__init__()

    # Mock methods that would be provided by other mixins
    def _parse_and_validate_quote_payload(self, quote_data):
        """Mock quote payload validation."""
        if not isinstance(quote_data, dict):
            return None
        return quote_data

    def _parse_and_validate_trade_payload(self, trade_data):
        """Mock trade payload validation."""
        if not isinstance(trade_data, dict):
            return None
        return trade_data

    def _symbol_matches_instrument(self, symbol):
        """Mock symbol matching."""
        return symbol in ["MNQ", "MNQU25"]

    async def _trigger_callbacks(self, event_type, data):
        """Mock callback triggering."""
        pass

    async def _cleanup_old_data(self):
        """Mock cleanup."""
        pass

    async def track_error(self, error, context, details=None):
        """Mock error tracking."""
        pass

    async def track_quote_processed(self):
        """Mock quote tracking."""
        pass

    async def track_trade_processed(self):
        """Mock trade tracking."""
        pass

    async def track_tick_processed(self):
        """Mock tick tracking."""
        pass

    async def track_bar_created(self, timeframe):
        """Mock bar creation tracking."""
        pass

    async def track_bar_updated(self, timeframe):
        """Mock bar update tracking."""
        pass

    async def record_timing(self, metric, duration_ms):
        """Mock timing recording."""
        pass

    async def increment(self, metric, value=1):
        """Mock metric increment."""
        pass


class TestDataProcessingMixinQuoteHandling:
    """Test quote update processing functionality."""

    @pytest.fixture
    def processor(self):
        """DataProcessingMixin instance for testing."""
        return MockRealtimeDataManager()

    @pytest.mark.asyncio
    async def test_on_quote_update_valid_data(self, processor):
        """Test processing valid quote update data."""
        quote_callback_data = {
            "data": {
                "symbol": "MNQ",
                "bestBid": 19000.25,
                "bestAsk": 19000.75,
                "lastPrice": 19000.50,
                "volume": 1000
            }
        }

        # Mock the tick processing method to track calls
        processor._process_tick_data = AsyncMock()

        # Process quote update
        await processor._on_quote_update(quote_callback_data)

        # Should call _process_tick_data with correct tick data
        processor._process_tick_data.assert_called_once()
        call_args = processor._process_tick_data.call_args[0][0]

        assert call_args["price"] == 19000.50  # lastPrice used when available
        assert call_args["volume"] == 0  # Quote updates have no volume
        assert call_args["type"] == "quote"
        assert call_args["source"] == "gateway_quote"
        assert isinstance(call_args["timestamp"], datetime)

    @pytest.mark.asyncio
    async def test_on_quote_update_no_last_price_uses_mid(self, processor):
        """Test quote update without lastPrice uses mid price."""
        quote_callback_data = {
            "data": {
                "symbol": "MNQ",
                "bestBid": 19000.00,
                "bestAsk": 19001.00,
                # No lastPrice
                "volume": 500
            }
        }

        processor._process_tick_data = AsyncMock()

        await processor._on_quote_update(quote_callback_data)

        processor._process_tick_data.assert_called_once()
        call_args = processor._process_tick_data.call_args[0][0]

        # Should use mid price
        assert call_args["price"] == 19000.50  # (19000 + 19001) / 2
        assert call_args["volume"] == 0

    @pytest.mark.asyncio
    async def test_on_quote_update_wrong_symbol_ignored(self, processor):
        """Test quote update for wrong symbol is ignored."""
        quote_callback_data = {
            "data": {
                "symbol": "WRONG_SYMBOL",
                "bestBid": 19000.00,
                "bestAsk": 19001.00,
            }
        }

        processor._process_tick_data = AsyncMock()

        await processor._on_quote_update(quote_callback_data)

        # Should not process tick for wrong symbol
        processor._process_tick_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_quote_update_invalid_payload_ignored(self, processor):
        """Test invalid quote payload is ignored."""
        # Mock validation to return None
        processor._parse_and_validate_quote_payload = Mock(return_value=None)
        processor._process_tick_data = AsyncMock()

        await processor._on_quote_update({"invalid": "data"})

        processor._process_tick_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_quote_update_error_handling(self, processor):
        """Test error handling in quote processing."""
        # Make _process_tick_data raise an exception
        processor._process_tick_data = AsyncMock(side_effect=Exception("Processing error"))
        processor.track_error = AsyncMock()

        quote_callback_data = {
            "data": {
                "symbol": "MNQ",
                "bestBid": 19000.00,
                "bestAsk": 19001.00,
            }
        }

        # Should not raise exception, should handle gracefully
        await processor._on_quote_update(quote_callback_data)

        # Should track the error
        processor.track_error.assert_called_once()
        error_call = processor.track_error.call_args
        assert isinstance(error_call[0][0], Exception)
        assert error_call[0][1] == "quote_update"


class TestDataProcessingMixinTradeHandling:
    """Test trade update processing functionality."""

    @pytest.fixture
    def processor(self):
        """DataProcessingMixin instance for testing."""
        return MockRealtimeDataManager()

    @pytest.mark.asyncio
    async def test_on_trade_update_valid_data(self, processor):
        """Test processing valid trade update data."""
        trade_callback_data = {
            "data": {
                "symbolId": "MNQ",
                "price": 19001.25,
                "volume": 50,
                "type": TradeLogType.BUY
            }
        }

        processor._process_tick_data = AsyncMock()

        await processor._on_trade_update(trade_callback_data)

        processor._process_tick_data.assert_called_once()
        call_args = processor._process_tick_data.call_args[0][0]

        assert call_args["price"] == 19001.25
        assert call_args["volume"] == 50
        assert call_args["type"] == "trade"
        assert call_args["trade_side"] == "buy"
        assert call_args["source"] == "gateway_trade"

    @pytest.mark.asyncio
    async def test_on_trade_update_sell_side(self, processor):
        """Test trade update with sell side."""
        trade_callback_data = {
            "data": {
                "symbolId": "MNQ",
                "price": 19000.75,
                "volume": 25,
                "type": TradeLogType.SELL
            }
        }

        processor._process_tick_data = AsyncMock()

        await processor._on_trade_update(trade_callback_data)

        call_args = processor._process_tick_data.call_args[0][0]
        assert call_args["trade_side"] == "sell"

    @pytest.mark.asyncio
    async def test_on_trade_update_unknown_trade_type(self, processor):
        """Test trade update with unknown trade type."""
        trade_callback_data = {
            "data": {
                "symbolId": "MNQ",
                "price": 19000.75,
                "volume": 25,
                "type": 999  # Unknown type
            }
        }

        processor._process_tick_data = AsyncMock()

        await processor._on_trade_update(trade_callback_data)

        call_args = processor._process_tick_data.call_args[0][0]
        assert call_args["trade_side"] == "unknown"

    @pytest.mark.asyncio
    async def test_on_trade_update_wrong_symbol_ignored(self, processor):
        """Test trade update for wrong symbol is ignored."""
        trade_callback_data = {
            "data": {
                "symbolId": "WRONG_SYMBOL",
                "price": 19000.75,
                "volume": 25,
                "type": TradeLogType.BUY
            }
        }

        processor._process_tick_data = AsyncMock()

        await processor._on_trade_update(trade_callback_data)

        processor._process_tick_data.assert_not_called()


class TestDataProcessingMixinTickProcessing:
    """Test core tick processing functionality."""

    @pytest.fixture
    def processor(self):
        """DataProcessingMixin instance with sample data."""
        proc = MockRealtimeDataManager()

        # Initialize with empty DataFrames
        proc.data = {
            "1min": pl.DataFrame(),
            "5min": pl.DataFrame(),
        }
        return proc

    @pytest.mark.asyncio
    async def test_process_tick_data_first_bar_creation(self, processor):
        """Test creation of first bar from tick data."""
        tick = {
            "timestamp": datetime(2025, 1, 1, 10, 0, 15, tzinfo=timezone.utc),
            "price": 19000.50,
            "volume": 100,
        }

        await processor._process_tick_data(tick)

        # Should create first bar for each timeframe
        for tf_key in ["1min", "5min"]:
            data = processor.data[tf_key]
            assert data.height == 1  # One bar created

            # Check bar data
            bar = data.to_dicts()[0]
            assert bar["open"] == 19000.50
            assert bar["high"] == 19000.50
            assert bar["low"] == 19000.50
            assert bar["close"] == 19000.50
            assert bar["volume"] >= 1  # Volume should be at least 1

    @pytest.mark.asyncio
    async def test_process_tick_data_bar_update(self, processor):
        """Test updating existing bar with new tick."""
        # Create initial bar
        initial_time = datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        initial_bar = pl.DataFrame({
            "timestamp": [initial_time],
            "open": [19000.00],
            "high": [19000.00],
            "low": [19000.00],
            "close": [19000.00],
            "volume": [50]
        })

        processor.data["1min"] = initial_bar
        processor.last_bar_times["1min"] = initial_time

        # Process tick for same minute (should update existing bar)
        tick = {
            "timestamp": datetime(2025, 1, 1, 10, 0, 30, tzinfo=timezone.utc),
            "price": 19001.25,
            "volume": 25,
        }

        await processor._process_tick_data(tick)

        # Should still have one bar, but updated
        data = processor.data["1min"]
        assert data.height == 1

        bar = data.to_dicts()[0]
        assert bar["open"] == 19000.00  # Open unchanged
        assert bar["high"] == 19001.25  # High updated
        assert bar["low"] == 19000.00   # Low unchanged
        assert bar["close"] == 19001.25 # Close updated to latest price
        assert bar["volume"] >= 75      # Volume increased

    @pytest.mark.asyncio
    async def test_process_tick_data_new_bar_creation(self, processor):
        """Test creation of new bar when time advances."""
        # Create initial bar for 10:00
        initial_time = datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        initial_bar = pl.DataFrame({
            "timestamp": [initial_time],
            "open": [19000.00],
            "high": [19001.00],
            "low": [18999.00],
            "close": [19000.50],
            "volume": [100]
        })

        processor.data["1min"] = initial_bar
        processor.last_bar_times["1min"] = initial_time

        # Mock callback triggering to track new bar events
        processor._trigger_callbacks = AsyncMock()

        # Process tick for next minute (should create new bar)
        tick = {
            "timestamp": datetime(2025, 1, 1, 10, 1, 15, tzinfo=timezone.utc),
            "price": 19002.00,
            "volume": 75,
        }

        await processor._process_tick_data(tick)

        # Should have two bars now
        data = processor.data["1min"]
        assert data.height == 2

        # Check new bar
        new_bar = data.tail(1).to_dicts()[0]
        assert new_bar["open"] == 19002.00
        assert new_bar["close"] == 19002.00
        assert new_bar["volume"] >= 75

        # Should trigger new bar callback
        # Allow time for async task to complete
        await asyncio.sleep(0.01)

    @pytest.mark.asyncio
    async def test_process_tick_data_not_running_ignored(self, processor):
        """Test tick processing ignored when manager not running."""
        processor.is_running = False
        processor._update_timeframe_data_atomic = AsyncMock()

        tick = {
            "timestamp": datetime.now(timezone.utc),
            "price": 19000.00,
            "volume": 50,
        }

        await processor._process_tick_data(tick)

        # Should not process any timeframes
        processor._update_timeframe_data_atomic.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_tick_data_rate_limiting(self, processor):
        """Test rate limiting prevents excessive updates."""
        tick = {
            "timestamp": datetime.now(timezone.utc),
            "price": 19000.00,
            "volume": 50,
        }

        # Process multiple ticks in rapid succession
        tasks = []
        for _ in range(10):
            tasks.append(processor._process_tick_data(tick))

        await asyncio.gather(*tasks)

        # Due to rate limiting, not all should be processed
        # Exact count depends on timing, but should be limited
        assert processor.memory_stats["ticks_processed"] < 10

    @pytest.mark.asyncio
    async def test_process_tick_data_error_handling(self, processor):
        """Test error handling in tick processing."""
        processor._update_timeframe_data_atomic = AsyncMock(
            side_effect=Exception("Update error")
        )
        processor.track_error = AsyncMock()
        processor.record_timing = AsyncMock()

        tick = {
            "timestamp": datetime.now(timezone.utc),
            "price": 19000.00,
            "volume": 50,
        }

        # Should not raise exception
        await processor._process_tick_data(tick)

        # Should track the error
        processor.track_error.assert_called()
        processor.record_timing.assert_called()


class TestDataProcessingMixinAtomicOperations:
    """Test atomic transaction and rollback functionality."""

    @pytest.fixture
    def processor(self):
        """DataProcessingMixin instance for testing."""
        proc = MockRealtimeDataManager()

        # Set up initial data
        initial_data = pl.DataFrame({
            "timestamp": [datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)],
            "open": [19000.00],
            "high": [19000.00],
            "low": [19000.00],
            "close": [19000.00],
            "volume": [100]
        })
        proc.data["1min"] = initial_data
        proc.last_bar_times["1min"] = datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)

        return proc

    @pytest.mark.asyncio
    async def test_update_timeframe_data_atomic_success(self, processor):
        """Test successful atomic update operation."""
        timestamp = datetime(2025, 1, 1, 10, 1, 0, tzinfo=timezone.utc)

        # Mock the actual update to succeed
        processor._update_timeframe_data = AsyncMock(return_value={"new_bar": True})

        result = await processor._update_timeframe_data_atomic(
            "1min", timestamp, 19001.00, 50
        )

        assert result == {"new_bar": True}
        processor._update_timeframe_data.assert_called_once()

        # Transaction should be cleaned up
        assert len(processor._update_transactions) == 0

    @pytest.mark.asyncio
    async def test_update_timeframe_data_atomic_rollback(self, processor):
        """Test rollback on failed atomic update."""
        timestamp = datetime(2025, 1, 1, 10, 1, 0, tzinfo=timezone.utc)

        # Store original data
        original_data = processor.data["1min"].clone()
        original_bar_time = processor.last_bar_times["1min"]

        # Mock update to fail
        processor._update_timeframe_data = AsyncMock(
            side_effect=Exception("Update failed")
        )

        with pytest.raises(Exception, match="Update failed"):
            await processor._update_timeframe_data_atomic(
                "1min", timestamp, 19001.00, 50
            )

        # Data should be rolled back to original state
        assert processor.data["1min"].equals(original_data)
        assert processor.last_bar_times["1min"] == original_bar_time

        # Transaction should be cleaned up
        assert len(processor._update_transactions) == 0

    @pytest.mark.asyncio
    async def test_rollback_transaction_with_no_original_data(self, processor):
        """Test rollback when no original data existed."""
        # Remove data to simulate new timeframe
        del processor.data["1min"]
        del processor.last_bar_times["1min"]

        # Create transaction
        transaction_id = "1min_test"
        processor._update_transactions[transaction_id] = {
            "timeframe": "1min",
            "original_data": None,
            "original_bar_time": None,
        }

        await processor._rollback_transaction(transaction_id)

        # Should not add data back
        assert "1min" not in processor.data
        assert "1min" not in processor.last_bar_times

    @pytest.mark.asyncio
    async def test_handle_partial_failures_low_success_rate(self, processor):
        """Test handling of partial failures with low success rate."""
        failed_timeframes = [
            ("1min", Exception("Error 1")),
            ("5min", Exception("Error 2")),
        ]
        successful_updates = ["15min"]  # Only 1/3 success rate

        processor.track_error = AsyncMock()
        processor.increment = AsyncMock()

        await processor._handle_partial_failures(failed_timeframes, successful_updates)

        # Should track each error
        assert processor.track_error.call_count == 2

        # Should log critical error for low success rate
        error_logs = [call.args for call in processor.logger.error.call_args_list]
        assert any("Critical: Low success rate" in str(args) for args in error_logs)

        # Should update statistics
        processor.increment.assert_any_call("partial_update_failures", 2)
        processor.increment.assert_any_call("successful_timeframe_updates", 1)


class TestDataProcessingMixinBarTimeCalculation:
    """Test bar time calculation functionality."""

    @pytest.fixture
    def processor(self):
        """DataProcessingMixin instance for testing."""
        return MockRealtimeDataManager()

    def test_calculate_bar_time_minutes(self, processor):
        """Test bar time calculation for minute intervals."""
        # 5-minute intervals
        timestamp = datetime(2025, 1, 1, 10, 23, 45, tzinfo=timezone.utc)

        bar_time = processor._calculate_bar_time(timestamp, 5, 2)  # 5 minutes

        # Should round down to nearest 5-minute boundary
        expected = datetime(2025, 1, 1, 10, 20, 0, tzinfo=timezone.utc)
        assert bar_time == expected

    def test_calculate_bar_time_seconds(self, processor):
        """Test bar time calculation for second intervals."""
        # 30-second intervals
        timestamp = datetime(2025, 1, 1, 10, 0, 47, 500000, tzinfo=timezone.utc)

        bar_time = processor._calculate_bar_time(timestamp, 30, 1)  # 30 seconds

        # Should round down to nearest 30-second boundary
        expected = datetime(2025, 1, 1, 10, 0, 30, 0, tzinfo=timezone.utc)
        assert bar_time == expected

    def test_calculate_bar_time_timezone_naive(self, processor):
        """Test bar time calculation with timezone-naive input."""
        # Timezone-naive timestamp
        timestamp = datetime(2025, 1, 1, 10, 23, 45)

        bar_time = processor._calculate_bar_time(timestamp, 1, 2)  # 1 minute

        # Should localize to configured timezone and calculate correctly
        expected = datetime(2025, 1, 1, 10, 23, 0, tzinfo=timezone.utc)
        assert bar_time == expected
        assert bar_time.tzinfo is not None

    def test_calculate_bar_time_unsupported_unit(self, processor):
        """Test error handling for unsupported time unit."""
        timestamp = datetime.now(timezone.utc)

        with pytest.raises(ValueError, match="Unsupported time unit: 99"):
            processor._calculate_bar_time(timestamp, 1, 99)


class TestDataProcessingMixinPerformanceAndSafety:
    """Test performance optimizations and safety mechanisms."""

    @pytest.fixture
    def processor(self):
        """DataProcessingMixin instance for testing."""
        proc = MockRealtimeDataManager()
        proc.data["1min"] = pl.DataFrame()
        return proc

    @pytest.mark.asyncio
    async def test_fine_grained_locking_per_timeframe(self, processor):
        """Test that each timeframe has its own lock."""
        # Get locks for different timeframes
        lock1 = processor._get_timeframe_lock("1min")
        lock2 = processor._get_timeframe_lock("5min")
        lock3 = processor._get_timeframe_lock("1min")  # Same as lock1

        # Different timeframes should have different locks
        assert lock1 is not lock2

        # Same timeframe should return same lock
        assert lock1 is lock3

    @pytest.mark.asyncio
    async def test_concurrent_timeframe_processing(self, processor):
        """Test concurrent processing of different timeframes."""
        # Set up data for multiple timeframes
        for tf in ["1min", "5min", "15min"]:
            processor.data[tf] = pl.DataFrame()
            processor.timeframes[tf] = {"interval": 1, "unit": 2}

        # Mock atomic update to track concurrent calls
        processor._update_timeframe_data_atomic = AsyncMock()

        tick = {
            "timestamp": datetime.now(timezone.utc),
            "price": 19000.00,
            "volume": 50,
        }

        await processor._process_tick_data(tick)

        # Should call atomic update for each timeframe
        assert processor._update_timeframe_data_atomic.call_count == 3

    @pytest.mark.asyncio
    async def test_memory_stats_tracking(self, processor):
        """Test memory statistics are properly tracked."""
        initial_ticks = processor.memory_stats["ticks_processed"]

        tick = {
            "timestamp": datetime.now(timezone.utc),
            "price": 19000.00,
            "volume": 50,
        }

        await processor._process_tick_data(tick)

        # Should increment tick count
        assert processor.memory_stats["ticks_processed"] > initial_ticks

    @pytest.mark.asyncio
    async def test_current_tick_data_storage(self, processor):
        """Test current tick data is properly stored."""
        initial_count = len(processor.current_tick_data)

        tick = {
            "timestamp": datetime.now(timezone.utc),
            "price": 19000.00,
            "volume": 50,
        }

        await processor._process_tick_data(tick)

        # Should add tick to current data
        assert len(processor.current_tick_data) > initial_count

        # Latest tick should be the one we added
        latest_tick = processor.current_tick_data[-1]
        assert latest_tick["price"] == 19000.00


class TestDataProcessingMixinIntegration:
    """Test integration scenarios and edge cases."""

    @pytest.fixture
    def processor(self):
        """DataProcessingMixin instance with realistic setup."""
        proc = MockRealtimeDataManager()

        # Set up multiple timeframes
        proc.timeframes = {
            "1min": {"interval": 1, "unit": 2},
            "5min": {"interval": 5, "unit": 2},
            "15min": {"interval": 15, "unit": 2},
        }
        proc.data = {tf: pl.DataFrame() for tf in proc.timeframes}

        return proc

    @pytest.mark.asyncio
    async def test_quote_to_tick_to_bar_flow(self, processor):
        """Test complete flow from quote update to bar creation."""
        # Mock methods
        processor._trigger_callbacks = AsyncMock()

        # Send quote update
        quote_data = {
            "data": {
                "symbol": "MNQ",
                "bestBid": 19000.00,
                "bestAsk": 19000.50,
                "lastPrice": 19000.25,
                "volume": 1000
            }
        }

        await processor._on_quote_update(quote_data)

        # Should create bars in all timeframes
        for tf_key in processor.timeframes:
            data = processor.data[tf_key]
            assert data.height == 1

            bar = data.to_dicts()[0]
            assert bar["close"] == 19000.25  # Uses lastPrice
            assert bar["volume"] == 0  # Quote updates have no volume

    @pytest.mark.asyncio
    async def test_trade_to_tick_to_bar_flow(self, processor):
        """Test complete flow from trade update to bar creation."""
        # Mock methods
        processor._trigger_callbacks = AsyncMock()

        # Send trade update
        trade_data = {
            "data": {
                "symbolId": "MNQ",
                "price": 19001.50,
                "volume": 75,
                "type": TradeLogType.BUY
            }
        }

        await processor._on_trade_update(trade_data)

        # Should create bars in all timeframes
        for tf_key in processor.timeframes:
            data = processor.data[tf_key]
            assert data.height == 1

            bar = data.to_dicts()[0]
            assert bar["close"] == 19001.50
            assert bar["volume"] >= 75  # Trade volume should be included

    @pytest.mark.asyncio
    async def test_mixed_quote_and_trade_updates(self, processor):
        """Test processing mixed quote and trade updates with same timestamp."""
        processor._trigger_callbacks = AsyncMock()

        # Disable rate limiting for this test
        processor._min_update_interval = 0.0

        # Use direct tick processing with controlled timestamps
        fixed_time = datetime(2025, 1, 1, 10, 0, 30, tzinfo=timezone.utc)

        # Process quote tick first
        quote_tick = {
            "timestamp": fixed_time,
            "price": 19000.25,  # Mid price
            "volume": 0,  # Quote has no volume
        }
        await processor._process_tick_data(quote_tick)

        # Small delay to avoid rate limiting
        await asyncio.sleep(0.002)

        # Process trade tick with same timestamp (should update existing bar)
        trade_tick = {
            "timestamp": fixed_time,  # Same timestamp
            "price": 19001.00,
            "volume": 50,
        }
        await processor._process_tick_data(trade_tick)

        # Should update existing bars
        for tf_key in processor.timeframes:
            data = processor.data[tf_key]
            assert data.height == 1  # Still one bar (same timestamp)

            bar = data.to_dicts()[0]
            assert bar["close"] == 19001.00  # Updated to trade price
            assert bar["high"] >= 19001.00   # Should include both prices
            assert bar["volume"] == 50       # Should have trade volume

    @pytest.mark.asyncio
    async def test_high_frequency_tick_processing(self, processor):
        """Test processing high frequency ticks efficiently."""
        processor._trigger_callbacks = AsyncMock()

        # Send many ticks rapidly
        tasks = []
        for i in range(100):
            tick = {
                "timestamp": datetime.now(timezone.utc),
                "price": 19000.00 + i * 0.25,
                "volume": 10,
            }
            tasks.append(processor._process_tick_data(tick))

        # Process all concurrently
        await asyncio.gather(*tasks, return_exceptions=True)

        # Should handle efficiently without errors
        assert processor.memory_stats["ticks_processed"] > 0

        # Data should be consistent
        for tf_key in processor.timeframes:
            data = processor.data[tf_key]
            assert data.height > 0  # Should have created bars


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
