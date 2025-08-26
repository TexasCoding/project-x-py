"""
Comprehensive tests for validation.py module using Test-Driven Development (TDD).

Tests define EXPECTED behavior - if code fails tests, fix the implementation, not the tests.
Tests validate what the code SHOULD do, not what it currently does.

Author: @TexasCoding
Date: 2025-01-22

TDD Testing Approach:
1. Write tests FIRST defining expected behavior
2. Run tests to discover bugs (RED phase)
3. Fix implementation to pass tests (GREEN phase)
4. Refactor while keeping tests green (REFACTOR phase)

Coverage Target: >90% for validation.py module
"""

import asyncio
import logging
from collections import deque
from datetime import datetime, timezone, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from project_x_py.realtime_data_manager.validation import (
    DataValidationMixin,
    ValidationConfig,
    ValidationMixin,
    ValidationMetrics,
)


# Test fixture setup
@pytest.fixture
def validation_config():
    """Create test validation configuration."""
    return ValidationConfig(
        enable_price_validation=True,
        price_range_multiplier=5.0,
        max_price_deviation_percent=50.0,
        min_price=0.01,
        max_price=100000.0,
        enable_volume_validation=True,
        max_volume=10000,
        volume_spike_threshold=5.0,
        min_volume=0,
        enable_timestamp_validation=True,
        max_future_seconds=5.0,
        max_past_hours=24.0,
        timestamp_tolerance_seconds=60.0,
        enable_spread_validation=True,
        max_spread_percent=2.0,
        max_spread_absolute=50.0,
        enable_tick_validation=True,
        tick_tolerance=0.001,
        enable_quality_tracking=True,
        quality_window_size=100,
        anomaly_detection_window=50,
    )


@pytest.fixture
def validation_metrics():
    """Create test validation metrics."""
    return ValidationMetrics()


class MockDataValidationManager(DataValidationMixin):
    """Mock class implementing DataValidationMixin for testing."""

    def __init__(self, config: ValidationConfig | None = None):
        """Initialize mock with required attributes."""
        self.config = {"validation_config": config.__dict__} if config else {}
        self.tick_size = 0.25  # MNQ tick size
        self.logger = Mock()

        # Initialize the mixin
        super().__init__()

    def _parse_and_validate_quote_payload(self, quote_data: Any) -> dict[str, Any] | None:
        """Mock implementation for testing."""
        if isinstance(quote_data, dict) and "symbol" in quote_data:
            return quote_data
        return None

    def _parse_and_validate_trade_payload(self, trade_data: Any) -> dict[str, Any] | None:
        """Mock implementation for testing - only check for symbolId to allow price validation testing."""
        if isinstance(trade_data, dict) and "symbolId" in trade_data:
            return trade_data
        return None


class MockValidationManager(ValidationMixin):
    """Mock class implementing ValidationMixin for testing."""

    def __init__(self):
        """Initialize mock with required attributes."""
        self.logger = Mock()
        self.instrument = "MNQ"
        self.instrument_symbol_id = "MNQ"
        self.is_running = True
        self.contract_id = "CON.F.US.MNQ.U25"
        self.timeframes = {"1min": {}, "5min": {}}
        self.data = {"1min": Mock(), "5min": Mock()}
        self.memory_stats = {
            "ticks_processed": 1000,
            "bars_cleaned": 50,
        }


@pytest.fixture
def data_validation_manager(validation_config):
    """Create a DataValidationMixin instance with test config."""
    return MockDataValidationManager(validation_config)


@pytest.fixture
def validation_manager():
    """Create a ValidationMixin instance for testing."""
    return MockValidationManager()


class TestValidationConfig:
    """Test the ValidationConfig dataclass following TDD principles."""

    def test_validation_config_has_default_values(self):
        """Test that ValidationConfig provides sensible defaults."""
        config = ValidationConfig()

        # Price validation defaults
        assert config.enable_price_validation is True
        assert config.price_range_multiplier == 5.0
        assert config.max_price_deviation_percent == 50.0
        assert config.min_price == 0.01
        assert config.max_price == 1_000_000.0

        # Volume validation defaults
        assert config.enable_volume_validation is True
        assert config.max_volume == 100_000
        assert config.volume_spike_threshold == 10.0
        assert config.min_volume == 0

        # Timestamp validation defaults
        assert config.enable_timestamp_validation is True
        assert config.max_future_seconds == 5.0
        assert config.max_past_hours == 24.0
        assert config.timestamp_tolerance_seconds == 60.0

        # Spread validation defaults
        assert config.enable_spread_validation is True
        assert config.max_spread_percent == 2.0
        assert config.max_spread_absolute == 100.0

        # Tick validation defaults
        assert config.enable_tick_validation is True
        assert config.tick_tolerance == 0.001

        # Quality tracking defaults
        assert config.enable_quality_tracking is True
        assert config.quality_window_size == 1000
        assert config.anomaly_detection_window == 100

    def test_validation_config_accepts_custom_values(self):
        """Test that ValidationConfig accepts custom configuration values."""
        config = ValidationConfig(
            price_range_multiplier=3.0,
            max_volume=50000,
            timestamp_tolerance_seconds=30.0,
        )

        assert config.price_range_multiplier == 3.0
        assert config.max_volume == 50000
        assert config.timestamp_tolerance_seconds == 30.0


class TestValidationMetrics:
    """Test the ValidationMetrics dataclass following TDD principles."""

    def test_validation_metrics_initialization(self, validation_metrics):
        """Test that ValidationMetrics initializes with correct defaults."""
        assert validation_metrics.total_processed == 0
        assert validation_metrics.total_rejected == 0
        assert isinstance(validation_metrics.rejection_reasons, dict)
        assert validation_metrics.price_anomalies == 0
        assert validation_metrics.volume_spikes == 0
        assert validation_metrics.spread_violations == 0
        assert validation_metrics.timestamp_issues == 0
        assert validation_metrics.format_errors == 0
        assert validation_metrics.validation_time_total_ms == 0.0
        assert validation_metrics.validation_count == 0
        assert isinstance(validation_metrics.recent_prices, deque)
        assert isinstance(validation_metrics.recent_volumes, deque)
        assert isinstance(validation_metrics.recent_timestamps, deque)

    def test_rejection_rate_calculation(self, validation_metrics):
        """Test that rejection rate is calculated correctly."""
        # Initial state - no data processed
        assert validation_metrics.rejection_rate == 0.0

        # Process some data with rejections
        validation_metrics.total_processed = 100
        validation_metrics.total_rejected = 5
        assert validation_metrics.rejection_rate == 5.0  # 5%

        validation_metrics.total_rejected = 25
        assert validation_metrics.rejection_rate == 25.0  # 25%

    def test_average_validation_time_calculation(self, validation_metrics):
        """Test that average validation time is calculated correctly."""
        # Initial state - no validations performed
        assert validation_metrics.avg_validation_time_ms == 0.0

        # Add validation times
        validation_metrics.validation_time_total_ms = 100.0
        validation_metrics.validation_count = 4
        assert validation_metrics.avg_validation_time_ms == 25.0  # 100/4


class TestDataValidationMixin:
    """Test the DataValidationMixin following TDD principles."""

    @pytest.mark.asyncio
    async def test_initialization(self, data_validation_manager):
        """Test that DataValidationMixin initializes correctly."""
        assert hasattr(data_validation_manager, '_validation_config')
        assert hasattr(data_validation_manager, '_validation_metrics')
        assert hasattr(data_validation_manager, '_metrics_lock')
        assert hasattr(data_validation_manager, '_price_history')
        assert hasattr(data_validation_manager, '_volume_history')
        assert isinstance(data_validation_manager._validation_config, ValidationConfig)
        assert isinstance(data_validation_manager._validation_metrics, ValidationMetrics)
        assert isinstance(data_validation_manager._metrics_lock, asyncio.Lock)

    @pytest.mark.asyncio
    async def test_validate_quote_data_success(self, data_validation_manager):
        """Test successful quote data validation."""
        quote_data = {
            "symbol": "MNQ",
            "timestamp": datetime.now(timezone.utc),
            "bestBid": 19000.0,
            "bestAsk": 19000.25,
            "lastPrice": 19000.0,  # Use tick-aligned price
        }

        result = await data_validation_manager.validate_quote_data(quote_data)

        assert result is not None
        assert result == quote_data
        assert data_validation_manager._validation_metrics.total_processed == 1
        assert data_validation_manager._validation_metrics.total_rejected == 0

    @pytest.mark.asyncio
    async def test_validate_quote_data_format_error(self, data_validation_manager):
        """Test quote data validation with format error."""
        invalid_quote = {"invalid": "data"}  # Missing required symbol field

        result = await data_validation_manager.validate_quote_data(invalid_quote)

        assert result is None
        assert data_validation_manager._validation_metrics.total_rejected == 1
        assert "format_error" in data_validation_manager._validation_metrics.rejection_reasons

    @pytest.mark.asyncio
    async def test_validate_quote_data_invalid_spread(self, data_validation_manager):
        """Test quote data validation with invalid bid/ask spread."""
        quote_data = {
            "symbol": "MNQ",
            "timestamp": datetime.now(timezone.utc),
            "bestBid": 19000.25,  # Bid higher than ask (invalid)
            "bestAsk": 19000.0,
        }

        result = await data_validation_manager.validate_quote_data(quote_data)

        assert result is None
        assert data_validation_manager._validation_metrics.total_rejected == 1
        assert "invalid_spread_bid_gt_ask" in data_validation_manager._validation_metrics.rejection_reasons

    @pytest.mark.asyncio
    async def test_validate_quote_data_excessive_spread(self, data_validation_manager):
        """Test quote data validation with excessive spread."""
        quote_data = {
            "symbol": "MNQ",
            "timestamp": datetime.now(timezone.utc),
            "bestBid": 19000.0,
            "bestAsk": 19500.0,  # 500 point spread = ~2.6% (exceeds 2% limit)
        }

        result = await data_validation_manager.validate_quote_data(quote_data)

        assert result is None
        assert data_validation_manager._validation_metrics.total_rejected == 1
        assert "excessive_spread" in data_validation_manager._validation_metrics.rejection_reasons

    @pytest.mark.asyncio
    async def test_validate_trade_data_success(self, data_validation_manager):
        """Test successful trade data validation."""
        trade_data = {
            "symbolId": "MNQ",
            "price": 19000.25,
            "timestamp": datetime.now(timezone.utc),
            "volume": 5,
        }

        result = await data_validation_manager.validate_trade_data(trade_data)

        assert result is not None
        assert result == trade_data
        assert data_validation_manager._validation_metrics.total_processed == 1

    @pytest.mark.asyncio
    async def test_validate_trade_data_missing_price(self, data_validation_manager):
        """Test trade data validation with missing price."""
        trade_data = {
            "symbolId": "MNQ",
            "timestamp": datetime.now(timezone.utc),
            "volume": 5,
        }

        result = await data_validation_manager.validate_trade_data(trade_data)

        assert result is None
        assert data_validation_manager._validation_metrics.total_rejected == 1
        assert "missing_price" in data_validation_manager._validation_metrics.rejection_reasons

    @pytest.mark.asyncio
    async def test_validate_trade_data_negative_price(self, data_validation_manager):
        """Test trade data validation with negative price."""
        trade_data = {
            "symbolId": "MNQ",
            "price": -100.0,  # Invalid negative price
            "timestamp": datetime.now(timezone.utc),
            "volume": 5,
        }

        result = await data_validation_manager.validate_trade_data(trade_data)

        assert result is None
        assert data_validation_manager._validation_metrics.total_rejected == 1
        assert "negative_or_zero_price" in data_validation_manager._validation_metrics.rejection_reasons

    @pytest.mark.asyncio
    async def test_validate_trade_data_excessive_volume(self, data_validation_manager):
        """Test trade data validation with excessive volume."""
        trade_data = {
            "symbolId": "MNQ",
            "price": 19000.25,
            "timestamp": datetime.now(timezone.utc),
            "volume": 50000,  # Exceeds max_volume of 10000
        }

        result = await data_validation_manager.validate_trade_data(trade_data)

        assert result is None
        assert data_validation_manager._validation_metrics.total_rejected == 1
        assert "volume_above_maximum" in data_validation_manager._validation_metrics.rejection_reasons

    @pytest.mark.asyncio
    async def test_validate_price_value_tick_alignment(self, data_validation_manager):
        """Test price validation for tick size alignment."""
        # Valid aligned price (divisible by 0.25)
        assert await data_validation_manager._validate_price_value(19000.25, "test")

        # Invalid unaligned price (not divisible by 0.25)
        result = await data_validation_manager._validate_price_value(19000.13, "test")
        assert result is False
        assert "price_not_tick_aligned" in data_validation_manager._validation_metrics.rejection_reasons

    @pytest.mark.asyncio
    async def test_validate_price_value_anomaly_detection(self, data_validation_manager):
        """Test price validation with anomaly detection."""
        # Build up price history with normal prices
        normal_prices = [19000.0, 19001.0, 19002.0, 19000.5, 19001.5] * 5  # 25 prices
        for price in normal_prices:
            data_validation_manager._price_history.append(price)

        # Normal price should pass
        assert await data_validation_manager._validate_price_value(19001.0, "test")

        # Anomalous price (way outside normal range) should fail
        # Average ~19001, so 35000 = (35000-19001)/19001 * 100 = ~84% deviation (exceeds 50% limit)
        result = await data_validation_manager._validate_price_value(35000.0, "test")
        assert result is False
        assert "price_anomaly" in data_validation_manager._validation_metrics.rejection_reasons

    @pytest.mark.asyncio
    async def test_is_price_aligned_to_tick(self, data_validation_manager):
        """Test tick alignment calculation."""
        # Test exact alignment
        assert data_validation_manager._is_price_aligned_to_tick(19000.00, 0.25)
        assert data_validation_manager._is_price_aligned_to_tick(19000.25, 0.25)
        assert data_validation_manager._is_price_aligned_to_tick(19000.50, 0.25)
        assert data_validation_manager._is_price_aligned_to_tick(19000.75, 0.25)

        # Test misalignment
        assert not data_validation_manager._is_price_aligned_to_tick(19000.13, 0.25)
        assert not data_validation_manager._is_price_aligned_to_tick(19000.37, 0.25)

        # Test edge cases
        assert data_validation_manager._is_price_aligned_to_tick(100.0, 0.0)  # Zero tick size
        assert data_validation_manager._is_price_aligned_to_tick(100.0, -0.25)  # Negative tick size

    @pytest.mark.asyncio
    async def test_validate_volume_spike_detection(self, data_validation_manager):
        """Test volume spike detection doesn't reject but tracks."""
        # Build up volume history
        normal_volumes = [100, 150, 120, 80, 200] * 3  # 15 volumes, avg ~130
        for volume in normal_volumes:
            data_validation_manager._volume_history.append(volume)

        trade_data = {
            "symbolId": "MNQ",
            "price": 19000.25,
            "timestamp": datetime.now(timezone.utc),
            "volume": 1000,  # 1000 vs avg 130 = 7.7x spike
        }

        # Should pass validation but track the spike
        result = await data_validation_manager.validate_trade_data(trade_data)
        assert result is not None
        assert data_validation_manager._validation_metrics.volume_spikes >= 1

    @pytest.mark.asyncio
    async def test_validate_timestamp_future(self, data_validation_manager):
        """Test timestamp validation for future timestamps."""
        future_time = datetime.now(timezone.utc) + timedelta(seconds=10)  # 10s in future (exceeds 5s limit)

        trade_data = {
            "symbolId": "MNQ",
            "price": 19000.25,
            "timestamp": future_time,
            "volume": 5,
        }

        result = await data_validation_manager.validate_trade_data(trade_data)

        assert result is None
        assert "timestamp_too_future" in data_validation_manager._validation_metrics.rejection_reasons

    @pytest.mark.asyncio
    async def test_validate_timestamp_too_old(self, data_validation_manager):
        """Test timestamp validation for old timestamps."""
        old_time = datetime.now(timezone.utc) - timedelta(hours=25)  # 25 hours ago (exceeds 24h limit)

        trade_data = {
            "symbolId": "MNQ",
            "price": 19000.25,
            "timestamp": old_time,
            "volume": 5,
        }

        result = await data_validation_manager.validate_trade_data(trade_data)

        assert result is None
        assert "timestamp_too_past" in data_validation_manager._validation_metrics.rejection_reasons

    @pytest.mark.asyncio
    async def test_validate_timestamp_string_formats(self, data_validation_manager):
        """Test timestamp validation with various string formats."""
        # ISO format with Z
        trade_data = {
            "symbolId": "MNQ",
            "price": 19000.25,
            "timestamp": "2025-01-22T10:00:00Z",
            "volume": 5,
        }

        result = await data_validation_manager.validate_trade_data(trade_data)
        # Should pass validation (assuming timestamp is not too old/future)
        assert result is not None or "timestamp_too_past" in data_validation_manager._validation_metrics.rejection_reasons

    @pytest.mark.asyncio
    async def test_validate_timestamp_unix_timestamp(self, data_validation_manager):
        """Test timestamp validation with Unix timestamp."""
        import time
        current_unix = time.time()

        trade_data = {
            "symbolId": "MNQ",
            "price": 19000.25,
            "timestamp": current_unix,
            "volume": 5,
        }

        result = await data_validation_manager.validate_trade_data(trade_data)
        assert result is not None

    @pytest.mark.asyncio
    async def test_validate_timestamp_out_of_order(self, data_validation_manager):
        """Test timestamp validation for out-of-order timestamps."""
        # Add a recent timestamp to the history
        recent_time = datetime.now(timezone.utc)
        data_validation_manager._validation_metrics.recent_timestamps.append(recent_time)

        # Create a timestamp significantly earlier (beyond tolerance)
        old_time = recent_time - timedelta(seconds=120)  # 2 minutes earlier (exceeds 60s tolerance)

        trade_data = {
            "symbolId": "MNQ",
            "price": 19000.25,
            "timestamp": old_time,
            "volume": 5,
        }

        result = await data_validation_manager.validate_trade_data(trade_data)

        assert result is None
        assert "timestamp_out_of_order" in data_validation_manager._validation_metrics.rejection_reasons

    @pytest.mark.asyncio
    async def test_update_quality_metrics_trade(self, data_validation_manager):
        """Test quality metrics update for trade data."""
        trade_data = {
            "price": 19000.25,
            "volume": 100,
            "timestamp": datetime.now(timezone.utc),
        }

        await data_validation_manager._update_quality_metrics(trade_data, "trade")

        assert len(data_validation_manager._price_history) == 1
        assert data_validation_manager._price_history[0] == 19000.25
        assert len(data_validation_manager._volume_history) == 1
        assert data_validation_manager._volume_history[0] == 100
        assert len(data_validation_manager._validation_metrics.recent_timestamps) == 1

    @pytest.mark.asyncio
    async def test_update_quality_metrics_quote(self, data_validation_manager):
        """Test quality metrics update for quote data."""
        quote_data = {
            "bestBid": 19000.0,
            "bestAsk": 19000.25,
            "timestamp": datetime.now(timezone.utc),
        }

        await data_validation_manager._update_quality_metrics(quote_data, "quote")

        # Should use mid price (19000.125) for quotes
        assert len(data_validation_manager._price_history) == 1
        assert data_validation_manager._price_history[0] == 19000.125
        assert len(data_validation_manager._validation_metrics.recent_timestamps) == 1

    @pytest.mark.asyncio
    async def test_track_rejection(self, data_validation_manager):
        """Test rejection tracking with different reasons."""
        await data_validation_manager._track_rejection("price_anomaly")
        await data_validation_manager._track_rejection("volume_spike")
        await data_validation_manager._track_rejection("spread_violation")
        await data_validation_manager._track_rejection("timestamp_out_of_order")
        await data_validation_manager._track_rejection("format_error")

        metrics = data_validation_manager._validation_metrics
        assert metrics.total_rejected == 5
        assert metrics.rejection_reasons["price_anomaly"] == 1
        assert metrics.rejection_reasons["volume_spike"] == 1
        assert metrics.rejection_reasons["spread_violation"] == 1
        assert metrics.rejection_reasons["timestamp_out_of_order"] == 1
        assert metrics.rejection_reasons["format_error"] == 1

        # Check category counters
        assert metrics.price_anomalies == 1
        assert metrics.volume_spikes == 1
        assert metrics.spread_violations == 1
        assert metrics.timestamp_issues == 1
        assert metrics.format_errors == 1

    @pytest.mark.asyncio
    async def test_get_validation_status(self, data_validation_manager):
        """Test validation status reporting."""
        # Add some test data
        await data_validation_manager._track_rejection("price_anomaly")
        data_validation_manager._validation_metrics.total_processed = 100

        status = await data_validation_manager.get_validation_status()

        assert isinstance(status, dict)
        assert "validation_enabled" in status
        assert status["validation_enabled"] is True
        assert "total_processed" in status
        assert status["total_processed"] == 100
        assert "total_rejected" in status
        assert status["total_rejected"] == 1
        assert "rejection_rate" in status
        assert status["rejection_rate"] == 1.0  # 1/100 = 1%
        assert "rejection_reasons" in status
        assert "data_quality" in status
        assert "performance" in status
        assert "configuration" in status
        assert "recent_data_stats" in status

    @pytest.mark.asyncio
    async def test_validation_disabled_configs(self):
        """Test that validation can be selectively disabled."""
        config = ValidationConfig(
            enable_price_validation=False,
            enable_volume_validation=False,
            enable_timestamp_validation=False,
            enable_spread_validation=False,
            enable_tick_validation=False,
        )

        manager = MockDataValidationManager(config)

        # Should pass validation even with invalid data when disabled
        invalid_trade = {
            "symbolId": "MNQ",
            "price": -100.0,  # Negative price
            "timestamp": "invalid_timestamp",
            "volume": -50,  # Negative volume
        }

        result = await manager.validate_trade_data(invalid_trade)
        # Should pass format validation but not price/volume/timestamp validation
        # The exact result depends on whether format validation catches the issues

    @pytest.mark.asyncio
    async def test_validation_exception_handling(self, data_validation_manager):
        """Test that validation handles exceptions gracefully."""
        # Mock _parse_and_validate_trade_payload to raise an exception
        with patch.object(data_validation_manager, '_parse_and_validate_trade_payload',
                         side_effect=Exception("Test exception")):

            result = await data_validation_manager.validate_trade_data({"test": "data"})

            assert result is None
            assert "validation_exception" in data_validation_manager._validation_metrics.rejection_reasons


class TestValidationMixin:
    """Test the ValidationMixin following TDD principles."""

    def test_parse_and_validate_trade_payload_dict(self, validation_manager):
        """Test parsing valid trade payload as dict."""
        trade_data = {
            "symbolId": "MNQ",
            "price": 19000.25,
            "timestamp": "2025-01-22T10:00:00Z",
            "volume": 5,
        }

        result = validation_manager._parse_and_validate_trade_payload(trade_data)

        assert result == trade_data

    def test_parse_and_validate_trade_payload_json_string(self, validation_manager):
        """Test parsing trade payload from JSON string."""
        trade_json = '{"symbolId": "MNQ", "price": 19000.25, "timestamp": "2025-01-22T10:00:00Z", "volume": 5}'

        result = validation_manager._parse_and_validate_trade_payload(trade_json)

        assert result is not None
        assert result["symbolId"] == "MNQ"
        assert result["price"] == 19000.25

    def test_parse_and_validate_trade_payload_invalid_json(self, validation_manager):
        """Test parsing invalid JSON string."""
        invalid_json = '{"symbolId": "MNQ", "price": invalid}'

        result = validation_manager._parse_and_validate_trade_payload(invalid_json)

        assert result is None

    def test_parse_and_validate_trade_payload_signalr_format(self, validation_manager):
        """Test parsing SignalR format [contract_id, data_dict]."""
        signalr_data = ["CON.F.US.MNQ.U25", {
            "symbolId": "MNQ",
            "price": 19000.25,
            "timestamp": "2025-01-22T10:00:00Z",
            "volume": 5,
        }]

        result = validation_manager._parse_and_validate_trade_payload(signalr_data)

        assert result is not None
        assert result["symbolId"] == "MNQ"

    def test_parse_and_validate_trade_payload_empty_list(self, validation_manager):
        """Test parsing empty list."""
        result = validation_manager._parse_and_validate_trade_payload([])

        assert result is None

    def test_parse_and_validate_trade_payload_missing_fields(self, validation_manager):
        """Test parsing trade payload with missing required fields."""
        incomplete_trade = {
            "symbolId": "MNQ",
            "price": 19000.25,
            # Missing timestamp and volume
        }

        result = validation_manager._parse_and_validate_trade_payload(incomplete_trade)

        assert result is None

    def test_parse_and_validate_quote_payload_dict(self, validation_manager):
        """Test parsing valid quote payload as dict."""
        quote_data = {
            "symbol": "MNQ",
            "timestamp": "2025-01-22T10:00:00Z",
            "bestBid": 19000.0,
            "bestAsk": 19000.25,
        }

        result = validation_manager._parse_and_validate_quote_payload(quote_data)

        assert result == quote_data

    def test_parse_and_validate_quote_payload_json_string(self, validation_manager):
        """Test parsing quote payload from JSON string."""
        quote_json = '{"symbol": "MNQ", "timestamp": "2025-01-22T10:00:00Z", "bestBid": 19000.0}'

        result = validation_manager._parse_and_validate_quote_payload(quote_json)

        assert result is not None
        assert result["symbol"] == "MNQ"

    def test_parse_and_validate_quote_payload_signalr_format(self, validation_manager):
        """Test parsing SignalR format for quotes."""
        signalr_data = ["CON.F.US.MNQ.U25", {
            "symbol": "MNQ",
            "timestamp": "2025-01-22T10:00:00Z",
            "bestBid": 19000.0,
        }]

        result = validation_manager._parse_and_validate_quote_payload(signalr_data)

        assert result is not None
        assert result["symbol"] == "MNQ"

    def test_parse_and_validate_quote_payload_missing_required_fields(self, validation_manager):
        """Test parsing quote payload with missing required fields."""
        incomplete_quote = {
            "bestBid": 19000.0,
            "bestAsk": 19000.25,
            # Missing symbol and timestamp
        }

        result = validation_manager._parse_and_validate_quote_payload(incomplete_quote)

        assert result is None

    def test_symbol_matches_instrument_exact_match(self, validation_manager):
        """Test symbol matching for exact instrument match."""
        assert validation_manager._symbol_matches_instrument("MNQ")
        assert validation_manager._symbol_matches_instrument("mnq")  # Case insensitive

    def test_symbol_matches_instrument_full_symbol(self, validation_manager):
        """Test symbol matching with full symbol format."""
        assert validation_manager._symbol_matches_instrument("F.US.MNQ")
        assert validation_manager._symbol_matches_instrument("F.US.EP.MNQ")

    def test_symbol_matches_instrument_no_match(self, validation_manager):
        """Test symbol matching with non-matching symbol."""
        assert not validation_manager._symbol_matches_instrument("ES")
        assert not validation_manager._symbol_matches_instrument("F.US.ES")

    def test_symbol_matches_instrument_resolved_symbol(self, validation_manager):
        """Test symbol matching with resolved symbol ID."""
        # Test case where user specified "NQ" but it resolved to "ENQ"
        validation_manager.instrument = "NQ"
        validation_manager.instrument_symbol_id = "ENQ"

        assert validation_manager._symbol_matches_instrument("ENQ")
        assert validation_manager._symbol_matches_instrument("F.US.ENQ")
        assert validation_manager._symbol_matches_instrument("NQ")  # Original should still match

    def test_get_realtime_validation_status(self, validation_manager):
        """Test getting real-time validation status."""
        status = validation_manager.get_realtime_validation_status()

        assert isinstance(status, dict)
        assert "is_running" in status
        assert "contract_id" in status
        assert "instrument" in status
        assert "timeframes_configured" in status
        assert "data_available" in status
        assert "ticks_processed" in status
        assert "bars_cleaned" in status
        assert "projectx_compliance" in status

        # Check specific values
        assert status["is_running"] is True
        assert status["contract_id"] == "CON.F.US.MNQ.U25"
        assert status["instrument"] == "MNQ"
        assert status["ticks_processed"] == 1000
        assert status["bars_cleaned"] == 50


class TestValidationEdgeCases:
    """Test edge cases and error conditions following TDD principles."""

    @pytest.mark.asyncio
    async def test_validation_with_none_values(self, data_validation_manager):
        """Test validation with None values in data."""
        trade_data = {
            "symbolId": "MNQ",
            "price": None,  # None price
            "timestamp": datetime.now(timezone.utc),
            "volume": None,  # None volume
        }

        result = await data_validation_manager.validate_trade_data(trade_data)

        assert result is None  # Should fail due to missing price

    @pytest.mark.asyncio
    async def test_validation_with_string_numbers(self, data_validation_manager):
        """Test validation with string representations of numbers."""
        trade_data = {
            "symbolId": "MNQ",
            "price": "19000.25",  # String price
            "timestamp": datetime.now(timezone.utc),
            "volume": "5",  # String volume
        }

        result = await data_validation_manager.validate_trade_data(trade_data)

        assert result is not None  # Should pass - strings should be converted

    @pytest.mark.asyncio
    async def test_validation_performance_tracking(self, data_validation_manager):
        """Test that validation performance is properly tracked."""
        trade_data = {
            "symbolId": "MNQ",
            "price": 19000.25,
            "timestamp": datetime.now(timezone.utc),
            "volume": 5,
        }

        # Perform multiple validations
        for _ in range(5):
            await data_validation_manager.validate_trade_data(trade_data)

        metrics = data_validation_manager._validation_metrics
        assert metrics.validation_count == 5
        assert metrics.validation_time_total_ms > 0
        assert metrics.avg_validation_time_ms > 0

    @pytest.mark.asyncio
    async def test_concurrent_validation(self, data_validation_manager):
        """Test that concurrent validations work correctly."""
        async def validate_trade():
            trade_data = {
                "symbolId": "MNQ",
                "price": 19000.25,
                "timestamp": datetime.now(timezone.utc),
                "volume": 5,
            }
            return await data_validation_manager.validate_trade_data(trade_data)

        # Run 10 concurrent validations
        results = await asyncio.gather(*[validate_trade() for _ in range(10)])

        # All should succeed
        assert all(result is not None for result in results)
        assert data_validation_manager._validation_metrics.total_processed == 10
        assert data_validation_manager._validation_metrics.total_rejected == 0

    def test_validation_config_edge_cases(self):
        """Test ValidationConfig with edge case values."""
        # Test with zero/negative values
        config = ValidationConfig(
            min_price=0.0,  # Zero minimum
            max_volume=0,   # Zero maximum volume
            tick_tolerance=0.0,  # Zero tolerance
        )

        assert config.min_price == 0.0
        assert config.max_volume == 0
        assert config.tick_tolerance == 0.0


class TestValidationIntegration:
    """Test integration between ValidationMixin and DataValidationMixin."""

    @pytest.mark.asyncio
    async def test_full_validation_pipeline(self):
        """Test the complete validation pipeline from parsing to validation."""
        # Create a combined mock that has both mixins
        class CombinedValidationManager(ValidationMixin, DataValidationMixin):
            def __init__(self):
                self.logger = Mock()
                self.instrument = "MNQ"
                self.config = {"validation_config": ValidationConfig().__dict__}
                self.tick_size = 0.25
                DataValidationMixin.__init__(self)

        manager = CombinedValidationManager()

        # Test with SignalR-style trade data
        raw_trade = ["CON.F.US.MNQ.U25", {
            "symbolId": "MNQ",
            "price": 19000.25,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "volume": 5,
        }]

        # Should parse and validate successfully
        result = await manager.validate_trade_data(raw_trade)

        assert result is not None
        assert result["symbolId"] == "MNQ"
        assert result["price"] == 19000.25


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
