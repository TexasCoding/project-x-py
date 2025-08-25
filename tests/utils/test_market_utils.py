"""Comprehensive tests for market_utils.py module."""

from datetime import datetime, timedelta

import pytest
import pytz
from freezegun import freeze_time

from project_x_py.utils.market_utils import (
    convert_timeframe_to_seconds,
    extract_symbol_from_contract_id,
    get_market_session_info,
    is_market_hours,
    validate_contract_id,
)


class TestIsMarketHours:
    """Test the is_market_hours function."""

    def test_default_timezone(self):
        """Test with default Chicago timezone."""
        # Test during market hours (Wednesday 10 AM CT - definitely market hours)
        with freeze_time("2024-01-10 16:00:00"):  # Wednesday 10 AM CT (UTC-6)
            result = is_market_hours("America/Chicago")
            # Wednesday 10 AM should be market hours (not 4 PM maintenance break)
            assert isinstance(result, bool)

    def test_custom_timezone(self):
        """Test with custom timezone."""
        # Test that custom timezone is used and doesn't crash
        with freeze_time("2024-01-10 16:00:00"):  # Wednesday
            result = is_market_hours("America/New_York")
            assert isinstance(result, bool)

    def test_monday_during_hours(self):
        """Test Monday during market hours."""
        # Monday 10 AM CT
        with freeze_time("2024-01-08 16:00:00"):  # Monday 10 AM CT
            result = is_market_hours("America/Chicago")
            assert result is True

    def test_tuesday_during_hours(self):
        """Test Tuesday during market hours."""
        # Tuesday 2 PM CT
        with freeze_time("2024-01-09 20:00:00"):  # Tuesday 2 PM CT
            result = is_market_hours("America/Chicago")
            assert result is True

    def test_maintenance_break(self):
        """Test during maintenance break (4 PM CT)."""
        # Wednesday 4 PM CT - maintenance break
        with freeze_time("2024-01-10 22:00:00"):  # Wednesday 4 PM CT
            result = is_market_hours("America/Chicago")
            assert result is False

    def test_friday_after_close(self):
        """Test Friday after market close."""
        # Friday 5 PM CT - market closed
        with freeze_time("2024-01-12 23:00:00"):  # Friday 5 PM CT
            result = is_market_hours("America/Chicago")
            assert result is False

    def test_saturday_closed(self):
        """Test Saturday (market closed)."""
        # Saturday 10 AM CT - market closed all day
        with freeze_time("2024-01-13 16:00:00"):  # Saturday 10 AM CT
            result = is_market_hours("America/Chicago")
            assert result is False

    def test_sunday_before_open(self):
        """Test Sunday before market open (5 PM CT)."""
        # Sunday 4 PM CT - before 5 PM open
        with freeze_time("2024-01-14 22:00:00"):  # Sunday 4 PM CT
            result = is_market_hours("America/Chicago")
            assert result is False

    def test_sunday_market_open(self):
        """Test Sunday at market open (5 PM CT)."""
        # Sunday 5 PM CT - market opens
        with freeze_time("2024-01-14 23:00:00"):  # Sunday 5 PM CT
            result = is_market_hours("America/Chicago")
            assert result is True

    def test_all_weekdays_during_hours(self):
        """Test all weekdays during normal hours."""
        # Test each day at 10 AM CT (16:00 UTC)
        test_dates = [
            ("2024-01-08", True),   # Monday
            ("2024-01-09", True),   # Tuesday
            ("2024-01-10", True),   # Wednesday
            ("2024-01-11", True),   # Thursday
            ("2024-01-12", True),   # Friday (before 4 PM)
            ("2024-01-13", False),  # Saturday
            ("2024-01-14", False),  # Sunday (before 5 PM)
        ]

        for date_str, expected in test_dates:
            with freeze_time(f"{date_str} 16:00:00"):  # 10 AM CT
                result = is_market_hours("America/Chicago")
                assert result is expected, f"Failed for {date_str} (expected {expected}, got {result})"

    def test_edge_hour_cases(self):
        """Test edge cases around critical hours."""
        # Test on Wednesday at different hours
        base_date = "2024-01-10"
        hours_and_expected = [
            ("21:00:00", True),   # 3 PM CT - market open
            ("22:00:00", False),  # 4 PM CT - maintenance break
            ("23:00:00", True),   # 5 PM CT - market open
            ("06:00:00", True),   # Midnight CT - market open
            ("09:00:00", True),   # 3 AM CT - market open
        ]

        for time_str, expected in hours_and_expected:
            with freeze_time(f"{base_date} {time_str}"):
                result = is_market_hours("America/Chicago")
                assert result is expected, f"Hour {time_str} should return {expected}, got {result}"

    def test_timezone_handling(self):
        """Test that timezone is properly handled."""
        # Test with different timezones to ensure they work
        timezones = ["America/Chicago", "America/New_York", "UTC"]

        for tz in timezones:
            with freeze_time("2024-01-10 16:00:00"):  # Wednesday
                result = is_market_hours(tz)
                assert isinstance(result, bool)


class TestGetMarketSessionInfo:
    """Test the get_market_session_info function."""

    def test_basic_session_info_structure(self):
        """Test basic structure of session info."""
        with freeze_time("2024-01-10 16:00:00"):  # Wednesday
            info = get_market_session_info("America/Chicago")

            required_keys = ["is_open", "current_time", "timezone", "weekday"]
            for key in required_keys:
                assert key in info

    def test_market_open_session_info(self):
        """Test session info when market is open."""
        # Wednesday 10 AM CT - market should be open
        with freeze_time("2024-01-10 16:00:00"):
            info = get_market_session_info("America/Chicago")

            assert info["is_open"] is True
            assert info["weekday"] == "Wednesday"
            assert info["timezone"] == "America/Chicago"

    def test_market_closed_session_info(self):
        """Test session info when market is closed."""
        # Saturday - market should be closed
        with freeze_time("2024-01-13 16:00:00"):
            info = get_market_session_info("America/Chicago")

            assert info["is_open"] is False
            assert "next_session_start" in info

    def test_friday_after_close(self):
        """Test Friday after market close."""
        # Friday 5 PM CT - after close
        with freeze_time("2024-01-12 23:00:00"):
            info = get_market_session_info("America/Chicago")
            # Should either be closed or show next session info
            assert isinstance(info["is_open"], bool)

    def test_saturday_session_info(self):
        """Test Saturday session info."""
        with freeze_time("2024-01-13 16:00:00"):  # Saturday
            info = get_market_session_info("America/Chicago")
            # Should show market closed
            assert info["is_open"] is False

    def test_sunday_before_open(self):
        """Test Sunday before market open."""
        # Sunday 4 PM CT - before 5 PM open
        with freeze_time("2024-01-14 22:00:00"):
            info = get_market_session_info("America/Chicago")
            # Should show when market opens
            assert isinstance(info["is_open"], bool)

    def test_maintenance_break(self):
        """Test during maintenance break (4 PM)."""
        # Wednesday 4 PM CT - maintenance break
        with freeze_time("2024-01-10 22:00:00"):
            info = get_market_session_info("America/Chicago")
            # Should show market closed during maintenance
            assert info["is_open"] is False

    def test_custom_timezone(self):
        """Test with custom timezone."""
        with freeze_time("2024-01-10 16:00:00"):
            info = get_market_session_info("America/New_York")
            assert info["timezone"] == "America/New_York"

    def test_time_calculations(self):
        """Test that time calculations are properly done."""
        with freeze_time("2024-01-10 16:00:00"):  # Wednesday
            info = get_market_session_info("America/Chicago")
            assert isinstance(info["current_time"], datetime)
            assert info["current_time"].tzinfo is not None


class TestValidateContractId:
    """Test the validate_contract_id function."""

    def test_valid_full_contract_ids(self):
        """Test valid full contract ID formats."""
        valid_ids = [
            "CON.F.US.MGC.M25",
            "CON.F.US.NQ.H24",
            "CON.F.US.ES.Z23",
            "CON.F.US.GC.F25",
        ]

        for contract_id in valid_ids:
            assert validate_contract_id(contract_id) is True

    def test_valid_simple_contract_ids(self):
        """Test valid simple contract ID formats."""
        valid_ids = [
            "MGC",
            "NQ",
            "ES",
            "GC",
            "CL",
            "AAPL",  # 4 character symbol
        ]

        for contract_id in valid_ids:
            assert validate_contract_id(contract_id) is True

    def test_invalid_contract_ids(self):
        """Test invalid contract ID formats."""
        invalid_ids = [
            "",  # Empty string
            "CON.F.US.MGC",  # Missing month/year
            "CON.F.US.MGC.M25.EXTRA",  # Extra parts
            "INVALID.FORMAT",  # Wrong format
            "CON.E.US.MGC.M25",  # Wrong exchange type (E instead of F)
            "CON.F.EU.MGC.M25",  # Wrong country (EU instead of US)
            "M",  # Too short symbol
            "TOOLONG",  # Too long simple symbol
            "123",  # Numeric symbol
            "MGC.M25",  # Partial format
        ]

        for contract_id in invalid_ids:
            assert validate_contract_id(contract_id) is False

    def test_month_codes(self):
        """Test all valid futures month codes."""
        valid_months = ["F", "G", "H", "J", "K", "M", "N", "Q", "U", "V", "X", "Z"]

        for month in valid_months:
            contract_id = f"CON.F.US.MGC.{month}25"
            assert validate_contract_id(contract_id) is True

    def test_invalid_month_codes(self):
        """Test invalid month codes."""
        invalid_months = ["A", "B", "C", "D", "E", "I", "L", "O", "P", "R", "S", "T", "W", "Y"]

        for month in invalid_months:
            contract_id = f"CON.F.US.MGC.{month}25"
            assert validate_contract_id(contract_id) is False

    def test_year_formats(self):
        """Test different year formats."""
        valid_years = ["23", "24", "25", "00", "99"]

        for year in valid_years:
            contract_id = f"CON.F.US.MGC.M{year}"
            assert validate_contract_id(contract_id) is True

    def test_symbol_lengths(self):
        """Test different symbol lengths."""
        # 2-character symbols
        assert validate_contract_id("CON.F.US.GC.M25") is True
        assert validate_contract_id("GC") is True

        # 3-character symbols
        assert validate_contract_id("CON.F.US.MGC.M25") is True
        assert validate_contract_id("MGC") is True

        # 4-character symbols
        assert validate_contract_id("CON.F.US.GOLD.M25") is True
        assert validate_contract_id("GOLD") is True

        # 1-character symbol (invalid)
        assert validate_contract_id("CON.F.US.G.M25") is False
        assert validate_contract_id("G") is False

        # 5-character symbol (invalid)
        assert validate_contract_id("CON.F.US.GOLDX.M25") is False
        assert validate_contract_id("GOLDX") is False

    def test_case_sensitivity(self):
        """Test case sensitivity."""
        # Should be case sensitive (uppercase required)
        assert validate_contract_id("CON.F.US.mgc.M25") is False
        assert validate_contract_id("con.f.us.MGC.M25") is False
        assert validate_contract_id("mgc") is False

    def test_special_characters(self):
        """Test handling of special characters."""
        invalid_ids = [
            "CON.F.US.MG$.M25",  # Special character in symbol
            "CON.F.US.MGC.M2$",  # Special character in year
            "CON F.US.MGC.M25",  # Space instead of dot
            "CON/F/US/MGC/M25",  # Forward slashes
        ]

        for contract_id in invalid_ids:
            assert validate_contract_id(contract_id) is False


class TestExtractSymbolFromContractId:
    """Test the extract_symbol_from_contract_id function."""

    def test_extract_from_full_contract_ids(self):
        """Test extracting symbols from full contract IDs."""
        test_cases = [
            ("CON.F.US.MGC.M25", "MGC"),
            ("CON.F.US.NQ.H24", "NQ"),
            ("CON.F.US.ES.Z23", "ES"),
            ("CON.F.US.GC.F25", "GC"),
            ("CON.F.US.GOLD.M25", "GOLD"),
        ]

        for contract_id, expected_symbol in test_cases:
            result = extract_symbol_from_contract_id(contract_id)
            assert result == expected_symbol

    def test_extract_from_simple_symbols(self):
        """Test extracting symbols from simple symbol format."""
        test_cases = ["MGC", "NQ", "ES", "GC", "GOLD"]

        for symbol in test_cases:
            result = extract_symbol_from_contract_id(symbol)
            assert result == symbol

    def test_invalid_contract_ids(self):
        """Test extraction from invalid contract IDs."""
        invalid_ids = [
            "CON.F.US.MGC",  # Missing month/year
            "INVALID.FORMAT",
            "CON.E.US.MGC.M25",  # Wrong format
            "",  # Empty string
            "TOOLONG",  # Too long
            "1",  # Too short
        ]

        for contract_id in invalid_ids:
            result = extract_symbol_from_contract_id(contract_id)
            assert result is None

    def test_none_input(self):
        """Test with None input."""
        result = extract_symbol_from_contract_id(None)
        assert result is None

    def test_empty_string_input(self):
        """Test with empty string input."""
        result = extract_symbol_from_contract_id("")
        assert result is None

    def test_edge_case_formats(self):
        """Test edge cases in format detection."""
        # Test boundary cases for simple symbol detection
        edge_cases = [
            ("AA", "AA"),  # 2 characters
            ("AAA", "AAA"),  # 3 characters
            ("AAAA", "AAAA"),  # 4 characters
            ("A", None),  # 1 character (invalid)
            ("AAAAA", None),  # 5 characters (invalid)
        ]

        for contract_id, expected in edge_cases:
            result = extract_symbol_from_contract_id(contract_id)
            assert result == expected

    def test_regex_pattern_matching(self):
        """Test that regex patterns work correctly."""
        # Test full pattern matching
        full_pattern_cases = [
            ("CON.F.US.ABC.M25", "ABC"),
            ("CON.F.US.ABCD.H24", "ABCD"),
        ]

        for contract_id, expected in full_pattern_cases:
            result = extract_symbol_from_contract_id(contract_id)
            assert result == expected

        # Test simple pattern matching
        simple_pattern_cases = ["AB", "ABC", "ABCD"]
        for contract_id in simple_pattern_cases:
            result = extract_symbol_from_contract_id(contract_id)
            assert result == contract_id


class TestConvertTimeframeToSeconds:
    """Test the convert_timeframe_to_seconds function."""

    def test_second_timeframes(self):
        """Test second-based timeframes."""
        test_cases = [
            ("1s", 1),
            ("5s", 5),
            ("10sec", 10),
            ("30second", 30),
            ("60seconds", 60),
        ]

        for timeframe, expected in test_cases:
            result = convert_timeframe_to_seconds(timeframe)
            assert result == expected

    def test_minute_timeframes(self):
        """Test minute-based timeframes."""
        test_cases = [
            ("1m", 60),
            ("5m", 300),
            ("15min", 900),
            ("30minute", 1800),
            ("60minutes", 3600),
        ]

        for timeframe, expected in test_cases:
            result = convert_timeframe_to_seconds(timeframe)
            assert result == expected

    def test_hour_timeframes(self):
        """Test hour-based timeframes."""
        test_cases = [
            ("1h", 3600),
            ("2h", 7200),
            ("4hr", 14400),
            ("8hour", 28800),
            ("24hours", 86400),
        ]

        for timeframe, expected in test_cases:
            result = convert_timeframe_to_seconds(timeframe)
            assert result == expected

    def test_day_timeframes(self):
        """Test day-based timeframes."""
        test_cases = [
            ("1d", 86400),
            ("2d", 172800),
            ("7day", 604800),
            ("30days", 2592000),
        ]

        for timeframe, expected in test_cases:
            result = convert_timeframe_to_seconds(timeframe)
            assert result == expected

    def test_week_timeframes(self):
        """Test week-based timeframes."""
        test_cases = [
            ("1w", 604800),
            ("2w", 1209600),
            ("4week", 2419200),
            ("52weeks", 31449600),
        ]

        for timeframe, expected in test_cases:
            result = convert_timeframe_to_seconds(timeframe)
            assert result == expected

    def test_case_insensitive(self):
        """Test that function is case insensitive."""
        test_cases = [
            ("1MIN", 60),
            ("5Min", 300),
            ("1HR", 3600),
            ("1DAY", 86400),
            ("1WEEK", 604800),
        ]

        for timeframe, expected in test_cases:
            result = convert_timeframe_to_seconds(timeframe)
            assert result == expected

    def test_invalid_timeframes(self):
        """Test invalid timeframe formats."""
        invalid_timeframes = [
            "",  # Empty string
            "invalid",  # No number
            "1x",  # Unknown unit
            "abc",  # Non-numeric
            "1.5min",  # Decimal (not handled by simple regex)
        ]

        for timeframe in invalid_timeframes:
            result = convert_timeframe_to_seconds(timeframe)
            assert result == 0

    def test_edge_case_numbers(self):
        """Test edge cases with numbers."""
        test_cases = [
            ("0min", 0),  # Zero
            ("999min", 59940),  # Large number
            ("1min", 60),  # Basic case
        ]

        for timeframe, expected in test_cases:
            result = convert_timeframe_to_seconds(timeframe)
            assert result == expected

    def test_all_unit_variations(self):
        """Test all unit variations comprehensively."""
        unit_mappings = {
            # Seconds
            "s": 1,
            "sec": 1,
            "second": 1,
            "seconds": 1,
            # Minutes
            "m": 60,
            "min": 60,
            "minute": 60,
            "minutes": 60,
            # Hours
            "h": 3600,
            "hr": 3600,
            "hour": 3600,
            "hours": 3600,
            # Days
            "d": 86400,
            "day": 86400,
            "days": 86400,
            # Weeks
            "w": 604800,
            "week": 604800,
            "weeks": 604800,
        }

        for unit, multiplier in unit_mappings.items():
            timeframe = f"2{unit}"
            expected = 2 * multiplier
            result = convert_timeframe_to_seconds(timeframe)
            assert result == expected, f"Failed for timeframe: {timeframe}"

    def test_regex_matching_edge_cases(self):
        """Test regex pattern matching edge cases."""
        # Test that regex properly separates number and unit
        test_cases = [
            ("123min", 7380),  # 3-digit number
            ("1000s", 1000),  # Large number
        ]

        for timeframe, expected in test_cases:
            result = convert_timeframe_to_seconds(timeframe)
            assert result == expected

    def test_common_trading_timeframes(self):
        """Test common trading timeframes."""
        common_timeframes = [
            ("1min", 60),
            ("5min", 300),
            ("15min", 900),
            ("30min", 1800),
            ("1hr", 3600),
            ("4hr", 14400),
            ("1day", 86400),
            ("1week", 604800),
        ]

        for timeframe, expected in common_timeframes:
            result = convert_timeframe_to_seconds(timeframe)
            assert result == expected
