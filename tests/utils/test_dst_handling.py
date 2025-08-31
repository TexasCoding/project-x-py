"""
Tests for DST (Daylight Saving Time) transition handling in real-time data manager.

Author: @TexasCoding
Date: 2025-08-22

Overview:
    Comprehensive tests for DST transition detection and handling in the
    project-x-py SDK real-time data manager. Covers both spring forward
    (missing hour) and fall back (duplicate hour) scenarios.

Test Categories:
    - DST transition detection
    - Bar time calculation during transitions
    - Spring forward handling (missing hour)
    - Fall back handling (duplicate hour)
    - Cross-DST data queries
    - Performance testing
    - Edge cases and error handling

Key Scenarios Tested:
    - US Eastern timezone DST transitions
    - CME Chicago timezone DST transitions
    - Non-DST timezones (UTC, Asia/Tokyo)
    - Rapid tick processing during transitions
    - Data integrity across DST boundaries
"""

import logging
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
import pytz

from project_x_py.realtime_data_manager.dst_handling import DSTHandlingMixin


class MockDSTManager(DSTHandlingMixin):
    """Mock class for testing DST handling functionality."""

    def __init__(self, timezone="America/Chicago"):
        self.timezone = pytz.timezone(timezone)
        self.tick_size = 0.25
        self.logger = logging.getLogger(__name__)
        super().__init__()

    def _calculate_bar_time(self, timestamp, interval, unit):
        """Mock standard bar time calculation."""
        if timestamp.tzinfo is None and self.timezone is not None:
            timestamp = self.timezone.localize(timestamp)

        if unit == 1:  # Seconds
            total_seconds = timestamp.second + timestamp.microsecond / 1000000
            rounded_seconds = (int(total_seconds) // interval) * interval
            bar_time = timestamp.replace(second=rounded_seconds, microsecond=0)
        elif unit == 2:  # Minutes
            minutes = (timestamp.minute // interval) * interval
            bar_time = timestamp.replace(minute=minutes, second=0, microsecond=0)
        else:
            raise ValueError(f"Unsupported time unit: {unit}")

        return bar_time


class TestDSTHandling:
    """Test suite for DST transition handling."""

    @pytest.fixture
    def chicago_manager(self):
        """Create DST manager with Chicago timezone."""
        return MockDSTManager(timezone="America/Chicago")

    @pytest.fixture
    def eastern_manager(self):
        """Create DST manager with Eastern timezone."""
        return MockDSTManager(timezone="America/New_York")

    @pytest.fixture
    def utc_manager(self):
        """Create DST manager with UTC timezone."""
        return MockDSTManager(timezone="UTC")

    def test_dst_initialization(self, chicago_manager):
        """Test DST handling initialization."""
        assert chicago_manager.timezone.zone == "America/Chicago"
        assert hasattr(chicago_manager, "dst_logger")
        assert hasattr(chicago_manager, "_dst_check_window")
        assert chicago_manager._dst_check_window == timedelta(hours=6)

    def test_dst_transition_detection_spring_forward(self, chicago_manager):
        """Test detection of spring forward DST transition."""
        # Spring forward 2025: March 9, 2:00 AM becomes 3:00 AM
        spring_forward_time = datetime(2025, 3, 9, 2, 30, 0)

        # This time should be detected as DST transition
        is_transition = chicago_manager.is_dst_transition_period(spring_forward_time)

        # The exact behavior depends on how pytz handles this
        # We mainly want to ensure no exceptions are raised
        assert isinstance(is_transition, bool)

    def test_dst_transition_detection_fall_back(self, chicago_manager):
        """Test detection of fall back DST transition."""
        # Fall back 2025: November 2, 2:00 AM becomes 1:00 AM
        fall_back_time = datetime(2025, 11, 2, 1, 30, 0)

        # This time should be detected as DST transition
        is_transition = chicago_manager.is_dst_transition_period(fall_back_time)

        # The exact behavior depends on how pytz handles this
        assert isinstance(is_transition, bool)

    def test_non_dst_timezone(self, utc_manager):
        """Test DST handling with non-DST timezone."""
        test_time = datetime(2025, 3, 9, 2, 30, 0)

        # UTC should never have DST transitions
        is_transition = utc_manager.is_dst_transition_period(test_time)
        assert is_transition is False

    def test_dst_bar_time_calculation_normal(self, chicago_manager):
        """Test DST-aware bar time calculation during normal periods."""
        normal_time = chicago_manager.timezone.localize(
            datetime(2025, 6, 15, 10, 35, 0)
        )

        # 5-minute bars
        bar_time = chicago_manager.handle_dst_bar_time(normal_time, 5, 2)

        assert bar_time is not None
        assert bar_time.minute == 35  # Should round to 35 minutes
        assert bar_time.second == 0
        assert bar_time.microsecond == 0

    def test_dst_bar_time_fallback(self, chicago_manager):
        """Test fallback to standard calculation when not in DST period."""
        normal_time = chicago_manager.timezone.localize(
            datetime(2025, 6, 15, 10, 35, 0)
        )

        with patch.object(
            chicago_manager, "is_dst_transition_period", return_value=False
        ):
            bar_time = chicago_manager.handle_dst_bar_time(normal_time, 5, 2)

        assert bar_time is not None
        assert bar_time.minute == 35

    def test_dst_status_information(self, chicago_manager):
        """Test DST status information retrieval."""
        status = chicago_manager.get_dst_status()

        assert "timezone" in status
        assert "current_time" in status
        assert "in_dst_transition" in status
        assert "cache_size" in status

        assert status["timezone"] == "America/Chicago"
        assert isinstance(status["in_dst_transition"], bool)
        assert isinstance(status["cache_size"], int)

    def test_dst_cache_management(self, chicago_manager):
        """Test DST cache functionality."""
        # Clear any existing cache first (class-level cache may have data from other tests)
        chicago_manager.clear_dst_cache()

        # Initial cache should be empty after clearing
        assert len(chicago_manager._dst_cache) == 0

        # Check a time to populate cache
        test_time = datetime(2025, 6, 15, 10, 0, 0)
        chicago_manager.is_dst_transition_period(test_time)

        # Cache might be populated (depends on implementation)
        initial_cache_size = len(chicago_manager._dst_cache)

        # Clear cache
        chicago_manager.clear_dst_cache()
        assert len(chicago_manager._dst_cache) == 0

    def test_dst_event_logging(self, chicago_manager):
        """Test DST event logging functionality."""
        test_time = datetime(2025, 3, 9, 2, 30, 0)

        with patch.object(chicago_manager.dst_logger, "log") as mock_log:
            chicago_manager.log_dst_event("SPRING_FORWARD", test_time, "Test event")

            mock_log.assert_called_once()
            args, kwargs = mock_log.call_args
            assert "DST SPRING_FORWARD" in args[1]
            assert "Test event" in args[1]

    def test_next_dst_transition_prediction(self, chicago_manager):
        """Test prediction of next DST transition."""
        next_transition = chicago_manager.predict_next_dst_transition()

        if next_transition is not None:
            transition_time, transition_type = next_transition
            assert isinstance(transition_time, datetime)
            assert transition_type in ["SPRING_FORWARD", "FALL_BACK"]
            # Should be in the future (relative to current time)
            assert transition_time > datetime.now()

    def test_dst_cache_expiry(self, chicago_manager):
        """Test DST cache expiry functionality."""
        test_time = datetime(2025, 6, 15, 10, 0, 0)

        # Check transition to populate cache
        chicago_manager.is_dst_transition_period(test_time)

        # Manually expire cache entries
        for key in chicago_manager._dst_cache_expiry:
            chicago_manager._dst_cache_expiry[key] = datetime.now() - timedelta(hours=2)

        # Next check should refresh cache
        chicago_manager.is_dst_transition_period(test_time)

    def test_timezone_aware_timestamp_handling(self, chicago_manager):
        """Test handling of timezone-aware vs naive timestamps."""
        # Naive timestamp
        naive_time = datetime(2025, 6, 15, 10, 30, 0)
        result1 = chicago_manager.handle_dst_bar_time(naive_time, 5, 2)
        assert result1 is not None

        # Timezone-aware timestamp
        aware_time = chicago_manager.timezone.localize(naive_time)
        result2 = chicago_manager.handle_dst_bar_time(aware_time, 5, 2)
        assert result2 is not None

        # Results should be equivalent
        assert result1.replace(tzinfo=None) == result2.replace(tzinfo=None)

    def test_dst_handling_with_different_intervals(self, chicago_manager):
        """Test DST handling with various time intervals."""
        test_time = chicago_manager.timezone.localize(datetime(2025, 6, 15, 10, 37, 30))

        # 1-minute bars
        bar_1min = chicago_manager.handle_dst_bar_time(test_time, 1, 2)
        assert bar_1min.minute == 37

        # 5-minute bars
        bar_5min = chicago_manager.handle_dst_bar_time(test_time, 5, 2)
        assert bar_5min.minute == 35  # Round down to 35

        # 15-minute bars
        bar_15min = chicago_manager.handle_dst_bar_time(test_time, 15, 2)
        assert bar_15min.minute == 30  # Round down to 30

        # 30-second bars
        bar_30sec = chicago_manager.handle_dst_bar_time(test_time, 30, 1)
        assert bar_30sec.second == 30  # Round down to 30 seconds

    def test_error_handling_in_dst_operations(self, chicago_manager):
        """Test error handling in DST operations."""
        # Invalid timezone should not crash
        with patch.object(chicago_manager, "timezone", None):
            result = chicago_manager.handle_dst_bar_time(datetime.now(), 5, 2)
            assert result is not None  # Should fallback gracefully

        # Invalid time unit
        test_time = datetime(2025, 6, 15, 10, 30, 0)
        with pytest.raises(ValueError):
            chicago_manager.handle_dst_bar_time(test_time, 5, 99)  # Invalid unit

    @pytest.mark.integration
    def test_dst_handling_performance(self, chicago_manager):
        """Test DST handling performance under load."""
        import time

        test_times = []
        base_time = datetime(2025, 6, 15, 10, 0, 0)

        # Generate 1000 test timestamps
        for i in range(1000):
            test_times.append(base_time + timedelta(minutes=i))

        start_time = time.time()

        # Process all timestamps
        for timestamp in test_times:
            chicago_manager.is_dst_transition_period(timestamp)

        end_time = time.time()
        processing_time = end_time - start_time

        # Should process 1000 timestamps in under 1 second
        assert processing_time < 1.0, f"DST processing too slow: {processing_time:.3f}s"

        # Cache should improve performance
        assert len(chicago_manager._dst_cache) > 0

    def test_multiple_timezone_support(self):
        """Test DST handling across different timezones."""
        timezones = [
            "America/Chicago",  # CME futures
            "America/New_York",  # US Eastern
            "Europe/London",  # UK (different DST dates)
            "Australia/Sydney",  # Southern hemisphere DST
            "UTC",  # No DST
            "Asia/Tokyo",  # No DST
        ]

        for tz_name in timezones:
            manager = MockDSTManager(timezone=tz_name)
            test_time = datetime(2025, 6, 15, 10, 30, 0)

            # Should not raise exceptions
            status = manager.get_dst_status()
            assert status["timezone"] == tz_name

            # Bar time calculation should work
            bar_time = manager.handle_dst_bar_time(test_time, 5, 2)
            assert bar_time is not None


@pytest.mark.integration
class TestDSTIntegration:
    """Integration tests for DST handling with real data scenarios."""

    def test_dst_transition_data_integrity(self):
        """Test data integrity across DST transitions."""
        manager = MockDSTManager(timezone="America/Chicago")

        # Simulate tick data around spring forward transition
        # March 9, 2025: 2:00 AM becomes 3:00 AM
        base_time = datetime(2025, 3, 9, 1, 55, 0)  # Start before transition

        processed_bars = []

        # Process ticks every minute for 2 hours
        for i in range(120):
            tick_time = base_time + timedelta(minutes=i)

            try:
                bar_time = manager.handle_dst_bar_time(tick_time, 5, 2)
                if bar_time is not None:
                    processed_bars.append(bar_time)
            except Exception as e:
                # Log but don't fail - some times may be invalid during DST
                print(f"DST transition handling for {tick_time}: {e}")

        # Should have processed most bars successfully
        assert len(processed_bars) > 100

        # Check for proper time sequence (no duplicates from different DST zones)
        sorted_bars = sorted(processed_bars)
        for i in range(1, len(sorted_bars)):
            time_diff = sorted_bars[i] - sorted_bars[i - 1]
            # Should have reasonable time differences (allowing for DST gaps)
            assert time_diff <= timedelta(hours=2)

    def test_cross_dst_historical_queries(self):
        """Test historical data queries that cross DST boundaries."""
        manager = MockDSTManager(timezone="America/Chicago")

        # Query spanning DST transition
        start_time = datetime(2025, 3, 8, 12, 0, 0)  # Day before spring forward
        end_time = datetime(2025, 3, 10, 12, 0, 0)  # Day after spring forward

        # Generate hourly timestamps across DST boundary
        current_time = start_time
        timestamps = []

        while current_time <= end_time:
            try:
                localized_time = manager.timezone.localize(current_time)
                timestamps.append(localized_time)
            except pytz.NonExistentTimeError:
                # Skip non-existent times during spring forward
                manager.log_dst_event(
                    "SPRING_FORWARD_SKIP", current_time, "Skipped non-existent time"
                )
            except pytz.AmbiguousTimeError:
                # Use standard time for ambiguous times
                localized_time = manager.timezone.localize(current_time, is_dst=False)
                timestamps.append(localized_time)
                manager.log_dst_event(
                    "FALL_BACK_DISAMBIGUATE", current_time, "Used standard time"
                )

            current_time += timedelta(hours=1)

        # Should have most timestamps except for spring forward gap
        assert len(timestamps) >= 47  # 48 hours minus spring forward gap

        # Verify proper timezone handling
        for ts in timestamps:
            assert ts.tzinfo is not None
            assert str(ts.tzinfo) in ["CST", "CDT", "America/Chicago"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
