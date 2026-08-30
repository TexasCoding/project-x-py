"""
Tests for trading session configuration system.

This test file defines the EXPECTED behavior for trading sessions (ETH/RTH).
Following strict TDD methodology - these tests define the specification,
not the current behavior. Implementation must be changed to match these tests.

Author: TDD Implementation
Date: 2025-08-28
"""

from datetime import datetime, time, timedelta, timezone
from typing import Any, Dict

import pytest

# Note: These imports will fail initially - that's expected in RED phase
from project_x_py.sessions import (
    DEFAULT_SESSIONS,
    SessionConfig,
    SessionTimes,
    SessionType,
)


class TestSessionConfig:
    """Test session configuration creation and validation."""

    def test_default_session_config_creation(self):
        """Session config should default to ETH with correct timezone."""
        config = SessionConfig()
        assert config.session_type == SessionType.ETH
        assert config.market_timezone == "America/New_York"
        assert config.use_exchange_timezone is True

    def test_rth_session_config_creation(self):
        """RTH session config should be creatable with correct defaults."""
        config = SessionConfig(session_type=SessionType.RTH)
        assert config.session_type == SessionType.RTH
        assert config.market_timezone == "America/New_York"
        assert config.use_exchange_timezone is True

    def test_custom_timezone_config(self):
        """Should support custom timezone configuration."""
        config = SessionConfig(
            session_type=SessionType.RTH,
            market_timezone="Europe/London",
            use_exchange_timezone=False,
        )
        assert config.market_timezone == "Europe/London"
        assert config.use_exchange_timezone is False

    def test_session_config_validation(self):
        """Should validate session configuration parameters."""
        # Invalid timezone should raise ValueError
        with pytest.raises(ValueError, match="Invalid timezone"):
            SessionConfig(market_timezone="Invalid/Timezone")

        # Invalid session type should raise ValueError
        with pytest.raises(ValueError, match="Invalid session type"):
            SessionConfig(session_type="INVALID")


class TestSessionTimes:
    """Test session time definitions and validation."""

    def test_session_times_creation(self):
        """Should create session times with proper validation."""
        times = SessionTimes(
            rth_start=time(9, 30),
            rth_end=time(16, 0),
            eth_start=time(18, 0),
            eth_end=time(17, 0),
        )
        assert times.rth_start == time(9, 30)
        assert times.rth_end == time(16, 0)
        assert times.eth_start == time(18, 0)
        assert times.eth_end == time(17, 0)

    def test_session_times_validation(self):
        """Should validate session times for logical consistency."""
        # ETH start and end must both be provided or both be None
        with pytest.raises(
            ValueError, match="ETH start and end must both be provided or both be None"
        ):
            SessionTimes(
                rth_start=time(9, 30),
                rth_end=time(16, 0),
                eth_start=time(18, 0),
                eth_end=None,  # Only one ETH time provided
            )

    def test_session_overlap_validation(self):
        """Should validate that RTH is contained within ETH."""
        # RTH should be subset of ETH trading hours
        times = SessionTimes(
            rth_start=time(9, 30),
            rth_end=time(16, 0),
            eth_start=time(18, 0),  # Previous day
            eth_end=time(17, 0),  # Current day
        )
        # This should be valid - RTH (9:30-16:00) is within ETH (18:00 prev - 17:00 curr)
        assert times.is_rth_within_eth()


class TestDefaultSessions:
    """Test default session configurations for major products."""

    def test_default_sessions_exist(self):
        """DEFAULT_SESSIONS should contain all major futures products."""
        required_products = [
            "ES",
            "NQ",
            "YM",
            "RTY",
            "MNQ",
            "MES",
            "CL",
            "GC",
            "SI",
            "ZN",
        ]
        for product in required_products:
            assert product in DEFAULT_SESSIONS, f"Missing session config for {product}"

    def test_equity_index_futures_sessions(self):
        """ES/NQ should have correct RTH times: 9:30 AM - 4:00 PM ET."""
        for product in ["ES", "NQ", "YM", "RTY", "MNQ", "MES"]:
            times = DEFAULT_SESSIONS[product]
            assert times.rth_start == time(9, 30), f"{product} RTH start incorrect"
            assert times.rth_end == time(16, 0), f"{product} RTH end incorrect"
            assert times.eth_start == time(18, 0), f"{product} ETH start incorrect"
            assert times.eth_end == time(17, 0), f"{product} ETH end incorrect"

    def test_commodity_futures_sessions(self):
        """CL should have correct RTH times: 9:00 AM - 2:30 PM ET."""
        times = DEFAULT_SESSIONS["CL"]
        assert times.rth_start == time(9, 0)
        assert times.rth_end == time(14, 30)
        # ETH for commodities typically Sunday 6 PM ET to Friday 5 PM ET
        assert times.eth_start == time(18, 0)
        assert times.eth_end == time(17, 0)

    def test_precious_metals_sessions(self):
        """GC/SI should have correct RTH times: 8:20 AM - 1:30 PM ET."""
        for product in ["GC", "SI"]:
            times = DEFAULT_SESSIONS[product]
            assert times.rth_start == time(8, 20), f"{product} RTH start incorrect"
            assert times.rth_end == time(13, 30), f"{product} RTH end incorrect"

    def test_treasury_futures_sessions(self):
        """ZN should have correct RTH times: 8:20 AM - 3:00 PM ET."""
        times = DEFAULT_SESSIONS["ZN"]
        assert times.rth_start == time(8, 20)
        assert times.rth_end == time(15, 0)


class TestSessionConfigOverrides:
    """Test custom session overrides and product-specific configurations."""

    def test_custom_session_override(self):
        """Custom session times should override defaults."""
        custom_times = SessionTimes(
            rth_start=time(8, 0),
            rth_end=time(15, 0),
            eth_start=time(17, 0),
            eth_end=time(16, 0),
        )
        config = SessionConfig(
            session_type=SessionType.RTH, product_sessions={"MNQ": custom_times}
        )
        assert config.product_sessions["MNQ"].rth_start == time(8, 0)
        assert config.product_sessions["MNQ"].rth_end == time(15, 0)

    def test_multiple_product_overrides(self):
        """Should support overrides for multiple products."""
        custom_es = SessionTimes(
            rth_start=time(9, 0),
            rth_end=time(15, 30),
            eth_start=time(17, 30),
            eth_end=time(16, 30),
        )
        custom_cl = SessionTimes(
            rth_start=time(8, 30),
            rth_end=time(14, 0),
            eth_start=time(17, 0),
            eth_end=time(16, 0),
        )

        config = SessionConfig(product_sessions={"ES": custom_es, "CL": custom_cl})

        assert config.product_sessions["ES"].rth_start == time(9, 0)
        assert config.product_sessions["CL"].rth_start == time(8, 30)

    def test_fallback_to_defaults(self):
        """Should fall back to defaults for products not in overrides."""
        config = SessionConfig(
            product_sessions={
                "MNQ": SessionTimes(
                    rth_start=time(10, 0),
                    rth_end=time(15, 0),
                    eth_start=time(18, 0),
                    eth_end=time(17, 0),
                )
            }
        )

        # MNQ should use custom times
        mnq_times = config.get_session_times("MNQ")
        assert mnq_times.rth_start == time(10, 0)

        # ES should use defaults
        es_times = config.get_session_times("ES")
        assert es_times.rth_start == time(9, 30)  # Default for ES


class TestSessionTypeEnum:
    """Test SessionType enumeration."""

    def test_session_type_values(self):
        """SessionType enum should have correct values."""
        assert SessionType.ETH == "ETH"
        assert SessionType.RTH == "RTH"
        assert SessionType.CUSTOM == "CUSTOM"

    def test_session_type_string_conversion(self):
        """Should support string conversion and comparison."""
        assert str(SessionType.ETH) == "ETH"
        assert SessionType.RTH.value == "RTH"

    def test_session_type_from_string(self):
        """Should create SessionType from string values."""
        assert SessionType("ETH") == SessionType.ETH
        assert SessionType("RTH") == SessionType.RTH

        with pytest.raises(ValueError):
            SessionType("INVALID")


class TestSessionConfigMethods:
    """Test SessionConfig utility methods."""

    def test_get_session_times_default(self):
        """get_session_times should return default times for standard products."""
        config = SessionConfig()
        es_times = config.get_session_times("ES")

        # Should return default ES times
        assert es_times.rth_start == time(9, 30)
        assert es_times.rth_end == time(16, 0)

    def test_get_session_times_custom(self):
        """get_session_times should return custom times when overridden."""
        custom_times = SessionTimes(
            rth_start=time(10, 0),
            rth_end=time(15, 0),
            eth_start=time(18, 0),
            eth_end=time(17, 0),
        )
        config = SessionConfig(product_sessions={"ES": custom_times})

        es_times = config.get_session_times("ES")
        assert es_times.rth_start == time(10, 0)

    def test_get_session_times_unknown_product(self):
        """get_session_times should handle unknown products gracefully."""
        config = SessionConfig()

        # Should return generic session times or raise appropriate error
        with pytest.raises(ValueError, match="Unknown product"):
            config.get_session_times("UNKNOWN_PRODUCT")

    def test_is_market_open_method(self):
        """Should provide method to check if market is open."""
        config = SessionConfig(session_type=SessionType.RTH)

        # RTH hours (10 AM ET = 3 PM UTC on trading day)
        trading_time = datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc)
        assert config.is_market_open(trading_time, "ES") is True

        # Outside RTH hours (7 PM ET = 12 AM UTC next day)
        after_hours = datetime(2024, 1, 16, 0, 0, tzinfo=timezone.utc)
        assert config.is_market_open(after_hours, "ES") is False

    def test_get_current_session_method(self):
        """Should provide method to get current session type."""
        config = SessionConfig(session_type=SessionType.ETH)

        # During RTH hours
        rth_time = datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc)  # 10 AM ET
        current_session = config.get_current_session(rth_time, "ES")
        assert current_session == "RTH"

        # During overnight hours
        overnight_time = datetime(2024, 1, 16, 2, 0, tzinfo=timezone.utc)  # 9 PM ET
        current_session = config.get_current_session(overnight_time, "ES")
        assert current_session == "ETH"

        # During maintenance break
        maintenance_time = datetime(
            2024, 1, 15, 22, 30, tzinfo=timezone.utc
        )  # 5:30 PM ET
        current_session = config.get_current_session(maintenance_time, "ES")
        assert current_session == "BREAK"


class TestSessionConfigErrorHandling:
    """Test error handling paths and uncovered lines in config.py."""

    def test_is_market_open_with_eth_session_type(self):
        """ETH config uses Globex hours, not pit/RTH hours."""
        config = SessionConfig(session_type=SessionType.ETH)

        rth_time = datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc)  # 10 AM ET
        assert config.is_market_open(rth_time, "ES") is True

        after_hours = datetime(2024, 1, 16, 0, 0, tzinfo=timezone.utc)  # 7 PM ET
        assert config.is_market_open(after_hours, "ES") is True

        # Tuesday 20:00 ET
        tuesday_eth = datetime(2024, 1, 17, 1, 0, tzinfo=timezone.utc)
        assert config.is_market_open(tuesday_eth, "ES") is True

        # Maintenance 17:30 ET
        maintenance = datetime(2024, 1, 15, 22, 30, tzinfo=timezone.utc)
        assert config.is_market_open(maintenance, "ES") is False

    def test_is_market_open_with_naive_datetime(self):
        """Test is_market_open with datetime without timezone (line 119)."""
        config = SessionConfig(session_type=SessionType.RTH)

        # Naive datetime should return False due to missing astimezone method
        naive_time = datetime(2024, 1, 15, 10, 0)  # No timezone info
        result = config.is_market_open(naive_time, "ES")
        assert result is False

    def test_is_market_open_with_invalid_timestamp(self):
        """Test is_market_open with non-datetime object (line 119)."""
        config = SessionConfig(session_type=SessionType.RTH)

        # String timestamp should return False
        result = config.is_market_open("2024-01-15 10:00:00", "ES")
        assert result is False

        # None timestamp should return False
        result = config.is_market_open(None, "ES")
        assert result is False

    def test_get_current_session_break_period(self):
        """Maintenance 17:00-18:00 ET is BREAK; overnight is ETH."""
        config = SessionConfig(session_type=SessionType.ETH)

        maintenance_time = datetime(2024, 1, 15, 22, 30, tzinfo=timezone.utc)
        current_session = config.get_current_session(maintenance_time, "ES")
        assert current_session == "BREAK"

        overnight = datetime(2024, 1, 15, 7, 0, tzinfo=timezone.utc)  # 2 AM ET
        current_session = config.get_current_session(overnight, "ES")
        assert current_session == "ETH"

    def test_session_config_with_unknown_session_type(self):
        """Test handling of unknown session type in SessionConfig."""
        # This should test the validation logic for session types
        with pytest.raises(ValueError, match="Invalid session type"):
            SessionConfig(session_type="UNKNOWN_SESSION")

    def test_session_config_timezone_edge_cases(self):
        """Test timezone handling edge cases."""
        # Test with UTC timezone
        config = SessionConfig(market_timezone="UTC")
        assert config.market_timezone == "UTC"

        # Test timezone validation with edge case
        with pytest.raises(ValueError, match="Invalid timezone"):
            SessionConfig(market_timezone="Invalid/Timezone/Format")


class TestSessionConfigConcurrentAccess:
    """Test concurrent access patterns."""

    @pytest.mark.asyncio
    async def test_concurrent_session_checks(self):
        """Test concurrent access to session checking methods."""
        import asyncio

        config = SessionConfig(session_type=SessionType.RTH)
        timestamp = datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc)

        async def check_session():
            return config.is_market_open(timestamp, "ES")

        # Run multiple concurrent checks
        tasks = [check_session() for _ in range(100)]
        results = await asyncio.gather(*tasks)

        # All results should be consistent
        assert all(result is True for result in results)

    def test_session_config_immutability(self):
        """Test that session config behaves immutably in concurrent scenarios."""
        config = SessionConfig(session_type=SessionType.RTH)

        # Multiple threads shouldn't be able to modify the configuration
        original_type = config.session_type
        original_timezone = config.market_timezone

        # Verify configuration remains unchanged
        assert config.session_type == original_type
        assert config.market_timezone == original_timezone


class TestSessionConfigPerformanceEdgeCases:
    """Test performance-related edge cases."""

    def test_repeated_get_session_times_performance(self):
        """Test that repeated calls to get_session_times are efficient."""
        import time

        config = SessionConfig()

        start_time = time.time()

        # Call get_session_times many times
        for _ in range(1000):
            config.get_session_times("ES")

        end_time = time.time()
        duration = end_time - start_time

        # Should complete quickly (under 0.1 seconds)
        assert duration < 0.1

    def test_session_boundary_microsecond_precision(self):
        """Test handling of microsecond-precise timestamps at session boundaries."""
        config = SessionConfig(session_type=SessionType.RTH)

        # Exactly at market open with microseconds
        market_open = datetime(2024, 1, 15, 14, 30, 0, 123456, tzinfo=timezone.utc)
        assert config.is_market_open(market_open, "ES") is True

        # Just before market open with microseconds
        before_open = datetime(2024, 1, 15, 14, 29, 59, 999999, tzinfo=timezone.utc)
        assert config.is_market_open(before_open, "ES") is False


class TestEthHoursAndOvernight:
    """ETH is Globex, not pit hours. Overnight is ETH, not BREAK."""

    def test_eth_hours_open_for_eth_config(self):
        config = SessionConfig(session_type=SessionType.ETH)
        tuesday_20et = datetime(2024, 1, 17, 1, 0, tzinfo=timezone.utc)
        assert config.is_market_open(tuesday_20et, "ES") is True

    def test_midnight_to_six_is_eth_not_break(self):
        config = SessionConfig(session_type=SessionType.ETH)
        midnight_et = datetime(2024, 1, 15, 5, 0, tzinfo=timezone.utc)  # 00:00 ET
        three_et = datetime(2024, 1, 15, 8, 0, tzinfo=timezone.utc)  # 03:00 ET
        five_et = datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)  # 05:00 ET
        assert config.get_current_session(midnight_et, "ES") == "ETH"
        assert config.get_current_session(three_et, "ES") == "ETH"
        assert config.get_current_session(five_et, "ES") == "ETH"
        assert config.is_market_open(midnight_et, "ES") is True

    def test_maintenance_is_break(self):
        config = SessionConfig(session_type=SessionType.ETH)
        maint = datetime(2024, 1, 15, 22, 15, tzinfo=timezone.utc)  # 17:15 ET
        assert config.get_current_session(maint, "ES") == "BREAK"
        assert config.is_market_open(maint, "ES") is False

    def test_rth_still_labeled_rth(self):
        config = SessionConfig(session_type=SessionType.ETH)
        rth = datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc)  # 10:00 ET
        assert config.get_current_session(rth, "ES") == "RTH"

    def test_dst_spring_forward_eth_still_open(self):
        """Monday after spring-forward: 07:00 UTC is 03:00 EDT, still ETH."""
        config = SessionConfig(session_type=SessionType.ETH)
        # 2024-03-10 is Sunday (DST start). Monday 03:00 EDT = 07:00 UTC.
        after_spring = datetime(2024, 3, 11, 7, 0, tzinfo=timezone.utc)
        assert config.is_market_open(after_spring, "ES") is True
        assert config.get_current_session(after_spring, "ES") == "ETH"
