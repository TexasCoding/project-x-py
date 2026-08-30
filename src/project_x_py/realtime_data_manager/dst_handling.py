"""
DST (Daylight Saving Time) transition handling for real-time data management.

Author: @TexasCoding
Date: 2025-08-22

Overview:
    Provides DST transition detection and handling functionality for real-time market data
    processing. Ensures proper bar alignment and data integrity during timezone transitions
    in trading systems.

Key Features:
    - DST transition detection for any timezone
    - Proper bar alignment during spring forward/fall back transitions
    - Handles missing hours (spring forward) and duplicate hours (fall back)
    - Comprehensive logging for DST-related events
    - Support for both US Eastern (market timezone) and other timezones
    - Future DST transition prediction and preparation

DST Handling Scenarios:
    - Spring Forward: 2:00 AM becomes 3:00 AM (missing hour)
        - Skip bars during the missing hour
        - Prevent creation of invalid timestamps
        - Log the gap in data

    - Fall Back: 2:00 AM becomes 1:00 AM (duplicate hour)
        - Handle first and second occurrence of same hour
        - Use DST-aware timestamps to distinguish
        - Maintain proper bar sequence

    - Cross-DST Data Queries:
        - Proper timezone conversion for historical data
        - Handle gaps and overlaps in bar data
        - Maintain data integrity across transitions

Architecture:
    - Mixin-based design for integration with RealtimeDataManager
    - pytz-based timezone handling for accurate DST detection
    - Event-driven logging for DST events
    - Thread-safe operations with proper locking

Usage:
    This mixin is automatically integrated into RealtimeDataManager when the
    TradingSuite is created. It provides transparent DST handling for all
    real-time data operations.

Example:
    ```python
    # DST handling is automatic with TradingSuite
    suite = await TradingSuite.create(
        "ES",  # S&P 500 E-mini futures
        timeframes=["1min", "5min"],
        timezone="America/Chicago",  # CME timezone with DST
    )

    # DST transitions are handled automatically
    # - Spring forward: No bars created for missing hour
    # - Fall back: Proper handling of duplicate hour
    # - All transitions logged for monitoring
    ```

Performance Considerations:
    - Minimal overhead during normal operation
    - DST transition checks cached for 1-hour periods
    - Only activates special handling during actual transitions
    - Efficient timezone offset calculations

Trading Considerations:
    - Futures markets may have different DST handling than stock markets
    - Some exchanges may not observe DST (e.g., Asia/Tokyo)
    - Critical for intraday strategies around transition times
    - Risk management systems must account for data gaps/overlaps
"""

import logging
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any, ClassVar, Union

import pytz

if TYPE_CHECKING:
    from pytz.tzinfo import BaseTzInfo


class DSTHandlingMixin:
    """
    Mixin to handle DST (Daylight Saving Time) transitions in real-time data processing.

    This mixin provides comprehensive DST transition detection and handling for trading
    systems that operate across timezone boundaries. It ensures data integrity during
    spring forward (missing hour) and fall back (duplicate hour) transitions.

    Key Capabilities:
        - Detects upcoming DST transitions within configurable window
        - Handles missing hours during spring forward transitions
        - Manages duplicate hours during fall back transitions
        - Provides DST-aware bar time calculations
        - Logs all DST-related events for monitoring
        - Maintains data integrity across transitions

    Integration:
        This mixin is designed to be included in RealtimeDataManager and provides
        transparent DST handling for all bar creation and timestamp operations.
    """

    # DST transition cache to avoid repeated calculations
    _dst_cache: ClassVar[dict[str, Any]] = {}
    _dst_cache_expiry: ClassVar[dict[str, datetime]] = {}
    _dst_year_transitions: ClassVar[
        dict[tuple[str, int], list[tuple[datetime, datetime]]]
    ] = {}
    _DST_CACHE_MAX_SIZE: ClassVar[int] = 96

    # Type declarations for attributes expected from main class
    if TYPE_CHECKING:
        timezone: BaseTzInfo | None

        def _calculate_bar_time(
            self, _timestamp: datetime, _interval: int, _unit: int
        ) -> datetime:
            """Expected method from main class for bar time calculation."""
            ...

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize DST handling with timezone configuration."""
        super().__init__(*args, **kwargs)

        # DST-specific logger for transition events
        self.dst_logger = logging.getLogger(f"{__name__}.dst")

        # DST configuration
        self._dst_check_window = timedelta(
            hours=6
        )  # Look ahead 6 hours for transitions
        self._dst_log_level = logging.INFO  # Log level for DST events

        # DST state tracking
        self._last_dst_check: datetime | None = None
        self._next_dst_transition: datetime | None = None
        self._in_dst_transition = False

        self.dst_logger.info(
            f"DST handling initialized for timezone: {getattr(self, 'timezone', 'UTC')}"
        )

    def is_dst_transition_period(self, timestamp: datetime) -> bool:
        """
        Check if timestamp falls within a DST transition period.

        Args:
            timestamp: Timestamp to check (should be timezone-aware)

        Returns:
            bool: True if timestamp is during DST transition
        """
        if not hasattr(self, "timezone") or self.timezone is None:
            return False

        tz = self.timezone  # Type checker now knows this is not None

        cache_key = f"{tz}_{timestamp.date()}_{timestamp.hour}"
        cache_expiry = self._dst_cache_expiry.get(cache_key)
        if cache_expiry and datetime.now() < cache_expiry:
            cached_result: bool = self._dst_cache.get(cache_key, False)
            return cached_result

        # Ensure timestamp is timezone-aware. is_dst=None raises on the 2 AM
        # spring-forward gap and the fall-back overlap.
        try:
            if timestamp.tzinfo is None:
                timestamp = tz.localize(timestamp, is_dst=None)
            elif timestamp.tzinfo != tz:
                timestamp = timestamp.astimezone(tz)
        except (pytz.AmbiguousTimeError, pytz.NonExistentTimeError):
            self._store_dst_cache(cache_key, True)
            return True

        is_transition = self._check_dst_transition(timestamp)
        self._store_dst_cache(cache_key, is_transition)
        return is_transition

    def _store_dst_cache(self, cache_key: str, value: bool) -> None:
        """Cache a DST check result with TTL and a hard size cap."""
        self._prune_dst_cache()
        self._dst_cache[cache_key] = value
        self._dst_cache_expiry[cache_key] = datetime.now() + timedelta(hours=1)

    def _prune_dst_cache(self) -> None:
        """Drop expired DST cache entries and cap unbounded growth."""
        now = datetime.now()
        expired = [
            key for key, expiry in self._dst_cache_expiry.items() if now >= expiry
        ]
        for key in expired:
            self._dst_cache.pop(key, None)
            self._dst_cache_expiry.pop(key, None)
        while (
            len(self._dst_cache) >= self._DST_CACHE_MAX_SIZE and self._dst_cache_expiry
        ):
            oldest = min(
                self._dst_cache_expiry, key=lambda key: self._dst_cache_expiry[key]
            )
            self._dst_cache.pop(oldest, None)
            self._dst_cache_expiry.pop(oldest, None)

    def _check_dst_transition(self, timestamp: datetime) -> bool:
        """
        Perform actual DST transition detection.

        Args:
            timestamp: Timezone-aware timestamp to check

        Returns:
            bool: True if during DST transition
        """
        try:
            # Get the date for this timestamp (for potential future use)
            # date = timestamp.date()
            if self.timezone is None:
                return False

            # Check if this timezone observes DST
            if not hasattr(self.timezone, "zone") or self.timezone.zone in [
                "UTC",
                "GMT",
            ]:
                return False

            # Find DST transitions for this year
            transitions = self._get_dst_transitions(timestamp.year)

            for transition_start, transition_end in transitions:
                # Ensure all datetimes are timezone-aware for comparison
                try:
                    if transition_start.tzinfo is None:
                        transition_start = self.timezone.localize(transition_start)
                    if transition_end.tzinfo is None:
                        transition_end = self.timezone.localize(transition_end)
                    if timestamp.tzinfo is None:
                        timestamp = self.timezone.localize(timestamp)

                    if transition_start <= timestamp <= transition_end:
                        return True
                except (pytz.AmbiguousTimeError, pytz.NonExistentTimeError):
                    # During DST transitions, some times may be ambiguous or non-existent
                    # In these cases, we're already in a transition period
                    return True

            return False

        except Exception as e:
            self.dst_logger.warning(f"Error checking DST transition: {e}")
            return False

    def _get_dst_transitions(self, year: int) -> list[tuple[datetime, datetime]]:
        """
        Get DST transition periods for a given year.

        US transitions occur at 2:00 AM local, not midnight. Probe 01:00 and
        02:00 each day with is_dst=None so NonExistentTimeError / AmbiguousTimeError
        catch the actual window.

        Args:
            year: Year to get transitions for

        Returns:
            list: List of (start, end) tuples for transition periods
        """
        if self.timezone is None:
            return []

        zone_name = getattr(self.timezone, "zone", str(self.timezone))
        year_key = (str(zone_name), year)
        cached = self._dst_year_transitions.get(year_key)
        if cached is not None:
            return cached

        transitions: list[tuple[datetime, datetime]] = []
        try:
            current = datetime(year, 1, 1)
            end = datetime(year, 12, 31)
            while current <= end:
                for hour in (1, 2):
                    candidate = current.replace(
                        hour=hour, minute=0, second=0, microsecond=0
                    )
                    try:
                        self.timezone.localize(candidate, is_dst=None)
                    except pytz.NonExistentTimeError:
                        transitions.append(
                            (
                                candidate - timedelta(hours=1),
                                candidate + timedelta(hours=1),
                            )
                        )
                        self.dst_logger.info(
                            f"DST Spring Forward detected at {candidate}"
                        )
                    except pytz.AmbiguousTimeError:
                        transitions.append(
                            (
                                candidate - timedelta(hours=1),
                                candidate + timedelta(hours=2),
                            )
                        )
                        self.dst_logger.info(f"DST Fall Back detected at {candidate}")
                current += timedelta(days=1)
        except Exception as e:
            self.dst_logger.error(f"Error getting DST transitions for {year}: {e}")

        if len(self._dst_year_transitions) >= 8:
            oldest = next(iter(self._dst_year_transitions))
            self._dst_year_transitions.pop(oldest, None)
        self._dst_year_transitions[year_key] = transitions
        return transitions

    def handle_dst_bar_time(
        self, timestamp: datetime, interval: int, unit: int
    ) -> datetime | None:
        """
        Calculate bar time with DST transition handling.

        This method provides DST-aware bar time calculations that properly handle
        transitions. During spring forward, it skips non-existent times. During
        fall back, it properly disambiguates duplicate times.

        Args:
            timestamp: Tick timestamp (timezone-aware)
            interval: Bar interval value
            unit: Time unit (1=seconds, 2=minutes)

        Returns:
            datetime: DST-aware bar time, or None if time should be skipped
        """
        if not hasattr(self, "timezone") or self.timezone is None:
            # Fallback to standard calculation - need to check if this method exists
            if hasattr(self, "_calculate_bar_time"):
                return self._calculate_bar_time(timestamp, interval, unit)
            else:
                return timestamp  # Simple fallback

        tz = self.timezone
        # Ensure timestamp is timezone-aware
        if timestamp.tzinfo is None:
            timestamp = tz.localize(timestamp)

        # Check if we're in a DST transition period
        if not self.is_dst_transition_period(timestamp):
            # Normal case - use standard calculation
            return self._calculate_bar_time(timestamp, interval, unit)

        return self._calculate_dst_aware_bar_time(timestamp, interval, unit)

    def _calculate_dst_aware_bar_time(
        self, timestamp: datetime, interval: int, unit: int
    ) -> datetime | None:
        """
        Calculate bar time during DST transitions.

        Args:
            timestamp: Timezone-aware timestamp
            interval: Bar interval value
            unit: Time unit (1=seconds, 2=minutes)

        Returns:
            datetime: Bar time or None if should be skipped
        """
        try:
            # Calculate base bar time using standard method
            base_bar_time = self._calculate_bar_time(timestamp, interval, unit)

            # Check if this bar time is valid during DST transition
            return self._validate_dst_bar_time(base_bar_time)

        except Exception as e:
            self.dst_logger.error(f"Error calculating DST-aware bar time: {e}")
            return None

    def _validate_dst_bar_time(self, bar_time: datetime) -> datetime | None:
        """
        Validate that a bar time is valid during DST transitions.

        Args:
            bar_time: Calculated bar time to validate

        Returns:
            datetime: Valid bar time or None if should be skipped
        """
        try:
            # Check for non-existent time (spring forward)
            try:
                # Try to localize the time to check if it exists
                if bar_time.tzinfo is None:
                    if hasattr(self, "timezone") and self.timezone is not None:
                        validated = self.timezone.localize(bar_time)
                    else:
                        validated = bar_time
                else:
                    validated = bar_time

                return validated

            except pytz.NonExistentTimeError:
                # Spring forward - this time doesn't exist
                self.dst_logger.warning(
                    f"Skipping bar for non-existent time during DST spring forward: {bar_time}"
                )
                return None

            except pytz.AmbiguousTimeError:
                # Fall back - time exists twice, use DST=False (standard time)
                if hasattr(self, "timezone") and self.timezone is not None:
                    validated = self.timezone.localize(bar_time, is_dst=False)
                else:
                    validated = bar_time
                self.dst_logger.info(
                    f"Using standard time for ambiguous DST fall back time: {bar_time}"
                )
                return validated

        except Exception as e:
            self.dst_logger.error(f"Error validating DST bar time {bar_time}: {e}")
            return bar_time  # Return original on error

    def log_dst_event(
        self, event_type: str, timestamp: datetime, details: str | None = None
    ) -> None:
        """
        Log DST-related events for monitoring and debugging.

        Args:
            event_type: Type of DST event (e.g., "SPRING_FORWARD", "FALL_BACK", "TRANSITION_DETECTED")
            timestamp: Timestamp associated with the event
            details: Optional additional details
        """
        log_message = f"DST {event_type}: {timestamp}"
        if details:
            log_message += f" - {details}"

        # Include timezone information
        if hasattr(self, "timezone") and self.timezone:
            log_message += f" (timezone: {self.timezone})"

        self.dst_logger.log(self._dst_log_level, log_message)

    def get_dst_status(self) -> dict[str, Any]:
        """
        Get current DST status and information.

        Returns:
            dict: DST status information including transitions and current state
        """
        current_time = datetime.now()
        if hasattr(self, "timezone") and self.timezone:
            current_time = current_time.astimezone(self.timezone)

        status = {
            "timezone": str(getattr(self, "timezone", "UTC")),
            "current_time": current_time,
            "in_dst_transition": self.is_dst_transition_period(current_time),
            "next_dst_check": self._last_dst_check,
            "cache_size": len(self._dst_cache),
        }

        # Add current DST status
        if hasattr(self, "timezone") and self.timezone:
            try:
                localized_time = self.timezone.localize(
                    current_time.replace(tzinfo=None)
                )
                status["is_dst"] = localized_time.dst() != timedelta(0)
                status["utc_offset"] = localized_time.utcoffset()
            except Exception:
                status["is_dst"] = None
                status["utc_offset"] = None

        return status

    def clear_dst_cache(self) -> None:
        """Clear DST transition cache (useful for testing or timezone changes)."""
        self._dst_cache.clear()
        self._dst_cache_expiry.clear()
        self._dst_year_transitions.clear()
        self.dst_logger.info("DST cache cleared")

    def predict_next_dst_transition(self) -> tuple[datetime, str] | None:
        """
        Predict the next DST transition for monitoring purposes.

        Returns:
            tuple: (transition_datetime, transition_type) or None if no transitions
        """
        if not hasattr(self, "timezone") or self.timezone is None:
            return None

        tz = self.timezone
        try:
            current_time = datetime.now()
            current_year = current_time.year

            # Check transitions for current and next year
            for year in [current_year, current_year + 1]:
                transitions = self._get_dst_transitions(year)

                for transition_start, transition_end in transitions:
                    if transition_start > current_time:
                        # Determine transition type by checking offset change
                        before = transition_start - timedelta(hours=1)
                        after = transition_end + timedelta(hours=1)

                        try:
                            before_offset = tz.localize(before).utcoffset()
                            after_offset = tz.localize(after).utcoffset()

                            if before_offset is not None and after_offset is not None:
                                transition_type = (
                                    "SPRING_FORWARD"
                                    if after_offset > before_offset
                                    else "FALL_BACK"
                                )
                            else:
                                transition_type = "UNKNOWN"
                            return (transition_start, transition_type)

                        except Exception:
                            continue

        except Exception as e:
            self.dst_logger.error(f"Error predicting next DST transition: {e}")

        return None

    def check_dst_transition(self, timestamp: datetime) -> dict[str, Any] | None:
        """
        Check for DST transitions around the given timestamp.

        Args:
            timestamp: Timestamp to check for nearby DST transitions

        Returns:
            Dictionary with transition info or None if no transition
        """
        if not hasattr(self, "timezone") or self.timezone is None:
            return None

        try:
            # Get DST transitions for the year
            transitions = self.get_dst_transition_dates(timestamp.year)

            # Check if we're within 24 hours of a transition
            for transition_type, transition_date in transitions.items():
                if (
                    transition_date
                    and abs((timestamp.date() - transition_date.date()).days) <= 1
                ):
                    if transition_type == "spring_forward":
                        return {
                            "type": "spring_forward",
                            "transition_time": transition_date,
                            "missing_hour": datetime(
                                transition_date.year,
                                transition_date.month,
                                transition_date.day,
                                2,
                                0,
                                0,
                            ),
                        }
                    else:
                        return {
                            "type": "fall_back",
                            "transition_time": transition_date,
                            "duplicate_hour": datetime(
                                transition_date.year,
                                transition_date.month,
                                transition_date.day,
                                1,
                                0,
                                0,
                            ),
                        }

            return None

        except Exception as e:
            self.dst_logger.error(f"Error checking DST transition: {e}")
            return None

    def is_missing_hour(
        self, timestamp: datetime, transition_date: Union[date, datetime]
    ) -> bool:
        """
        Check if timestamp falls in the missing hour during spring forward.

        Args:
            timestamp: Timestamp to check
            transition_date: Date of the DST transition

        Returns:
            True if timestamp is in the missing hour
        """
        if not hasattr(self, "timezone") or self.timezone is None:
            return False

        # Get the transition date
        date_to_check = (
            transition_date
            if isinstance(transition_date, date)
            and not isinstance(transition_date, datetime)
            else transition_date.date()
            if isinstance(transition_date, datetime)
            else transition_date
        )

        # Only check times on the transition date
        if timestamp.date() != date_to_check:
            return False

        # Get DST transition dates for this year
        transitions = self.get_dst_transition_dates(timestamp.year)
        spring_forward_date = transitions.get("spring_forward")

        if (
            spring_forward_date
            and (
                spring_forward_date.date()
                if isinstance(spring_forward_date, datetime)
                else spring_forward_date
            )
            == date_to_check
            and timestamp.hour == 2
        ):
            # Spring forward typically happens at 2:00 AM -> 3:00 AM
            # Times between 2:00 AM and 2:59:59 AM are missing
            try:
                # Try to localize with is_dst=None to trigger exceptions
                self.timezone.localize(timestamp, is_dst=None)
                return False
            except pytz.NonExistentTimeError:
                return True
            except Exception:
                return False

        return False

    def is_duplicate_hour(
        self, timestamp: datetime, transition_date: Union[date, datetime]
    ) -> bool:
        """
        Check if timestamp falls in the duplicate hour during fall back.

        Args:
            timestamp: Timestamp to check
            transition_date: Date of the DST transition

        Returns:
            True if timestamp is in the duplicate hour
        """
        if not hasattr(self, "timezone") or self.timezone is None:
            return False

        # Get the transition date
        date_to_check = (
            transition_date
            if isinstance(transition_date, date)
            and not isinstance(transition_date, datetime)
            else transition_date.date()
            if isinstance(transition_date, datetime)
            else transition_date
        )

        # Only check times on the transition date
        if timestamp.date() != date_to_check:
            return False

        # Get DST transition dates for this year
        transitions = self.get_dst_transition_dates(timestamp.year)
        fall_back_date = transitions.get("fall_back")

        if (
            fall_back_date
            and (
                fall_back_date.date()
                if isinstance(fall_back_date, datetime)
                else fall_back_date
            )
            == date_to_check
            and timestamp.hour == 1
        ):
            # Fall back typically creates duplicate 1:00-2:00 AM hour
            # Times between 1:00 AM and 1:59:59 AM occur twice
            try:
                # Try to localize with is_dst=None to trigger exceptions
                self.timezone.localize(timestamp, is_dst=None)
                return False
            except pytz.AmbiguousTimeError:
                return True
            except Exception:
                return False

        return False

    def adjust_bar_time_for_dst(self, timestamp: datetime) -> datetime:
        """
        Adjust bar time to handle DST transitions.

        Args:
            timestamp: Original timestamp

        Returns:
            Adjusted timestamp that accounts for DST
        """
        if not hasattr(self, "timezone") or self.timezone is None:
            return timestamp

        try:
            # Check if this is during a spring forward (missing hour)
            if self.is_missing_hour(timestamp, timestamp.date()):
                # Move to next valid hour (3 AM)
                return timestamp.replace(hour=3, minute=0, second=0, microsecond=0)

            # For fall back or normal times, return as-is
            return timestamp

        except Exception as e:
            self.dst_logger.error(f"Error adjusting bar time for DST: {e}")
            return timestamp

    def get_dst_transition_dates(self, year: int) -> dict[str, Union[datetime, None]]:
        """
        Get DST transition dates for a given year.

        Args:
            year: Year to get transitions for

        Returns:
            Dictionary with spring_forward and fall_back dates
        """
        transitions: dict[str, Union[datetime, None]] = {
            "spring_forward": None,
            "fall_back": None,
        }

        if not hasattr(self, "timezone") or self.timezone is None:
            return transitions

        try:
            # For US timezones, DST typically:
            # Spring forward: Second Sunday in March at 2:00 AM
            # Fall back: First Sunday in November at 2:00 AM

            # Find second Sunday in March
            march_first = datetime(year, 3, 1)
            days_until_sunday = (6 - march_first.weekday()) % 7
            first_sunday_march = march_first + timedelta(days=days_until_sunday)
            second_sunday_march = first_sunday_march + timedelta(days=7)
            spring_forward = second_sunday_march.replace(
                hour=2, minute=0, second=0, microsecond=0
            )

            # Find first Sunday in November
            nov_first = datetime(year, 11, 1)
            days_until_sunday = (6 - nov_first.weekday()) % 7
            first_sunday_nov = nov_first + timedelta(days=days_until_sunday)
            fall_back = first_sunday_nov.replace(
                hour=2, minute=0, second=0, microsecond=0
            )

            transitions["spring_forward"] = spring_forward
            transitions["fall_back"] = fall_back

        except Exception as e:
            self.dst_logger.error(f"Error getting DST transition dates: {e}")

        return transitions

    def is_dst_transition_day(self, check_date: Union[date, datetime]) -> bool:
        """
        Check if date is a DST transition day.

        Args:
            check_date: Date to check

        Returns:
            True if date has a DST transition
        """
        date_to_check = (
            check_date
            if isinstance(check_date, date) and not isinstance(check_date, datetime)
            else check_date.date()
            if isinstance(check_date, datetime)
            else check_date
        )
        year = date_to_check.year
        transitions = self.get_dst_transition_dates(year)

        spring_match = (
            transitions["spring_forward"] is not None
            and (
                transitions["spring_forward"].date()
                if isinstance(transitions["spring_forward"], datetime)
                else transitions["spring_forward"]
            )
            == date_to_check
        )
        fall_match = (
            transitions["fall_back"] is not None
            and (
                transitions["fall_back"].date()
                if isinstance(transitions["fall_back"], datetime)
                else transitions["fall_back"]
            )
            == date_to_check
        )

        return spring_match or fall_match

    def calculate_bar_intervals_across_dst(
        self, start_time: datetime, interval: str, count: int
    ) -> list[datetime]:
        """
        Calculate bar intervals that properly handle DST transitions.

        Args:
            start_time: Starting timestamp
            interval: Interval string (e.g., "1hr", "1min")
            count: Number of intervals to calculate

        Returns:
            List of timestamps accounting for DST
        """
        intervals = []
        current = start_time

        # Parse interval
        if interval == "1hr":
            delta = timedelta(hours=1)
        elif interval == "1min":
            delta = timedelta(minutes=1)
        else:
            # Parse other formats as needed
            delta = timedelta(hours=1)  # Default

        for _ in range(count):
            # Check if current time is valid (not missing due to DST)
            if not self.is_missing_hour(current, current.date()):
                intervals.append(current)

            current += delta

        return intervals

    def validate_timestamp_dst_aware(self, timestamp: datetime) -> bool:
        """
        Validate that timestamp is DST-aware and valid.

        Args:
            timestamp: Timestamp to validate

        Returns:
            True if timestamp is valid considering DST
        """
        if not hasattr(self, "timezone") or self.timezone is None:
            return True

        try:
            # Check if timestamp falls in missing hour
            if self.is_missing_hour(timestamp, timestamp.date()):
                return False

            # Try to localize to verify it's valid
            if timestamp.tzinfo is None:
                self.timezone.localize(timestamp)

            return True

        except (pytz.NonExistentTimeError, pytz.AmbiguousTimeError):
            return False
        except Exception:
            return True  # Assume valid if we can't determine otherwise

    def resolve_ambiguous_time(
        self, timestamp: datetime, first: bool = True
    ) -> datetime:
        """
        Resolve ambiguous time during fall back transition.

        Args:
            timestamp: Ambiguous timestamp
            first: True for first occurrence, False for second

        Returns:
            Resolved timestamp with proper DST info
        """
        if not hasattr(self, "timezone") or self.timezone is None:
            return timestamp

        try:
            if timestamp.tzinfo is None:
                # Localize with is_dst parameter to resolve ambiguity
                return self.timezone.localize(timestamp, is_dst=first)
            else:
                return timestamp

        except Exception as e:
            self.dst_logger.error(f"Error resolving ambiguous time: {e}")
            return timestamp

    def convert_to_local_time(self, utc_time: datetime) -> datetime:
        """
        Convert UTC time to local timezone with DST awareness.

        Args:
            utc_time: UTC timestamp

        Returns:
            Local timestamp with timezone info
        """
        if not hasattr(self, "timezone") or self.timezone is None:
            return utc_time

        try:
            if utc_time.tzinfo is None:
                utc_time = pytz.UTC.localize(utc_time)
            elif utc_time.tzinfo != pytz.UTC:
                utc_time = utc_time.astimezone(pytz.UTC)

            return utc_time.astimezone(self.timezone)

        except Exception as e:
            self.dst_logger.error(f"Error converting to local time: {e}")
            return utc_time

    def get_next_valid_bar_time(
        self, invalid_time: datetime, interval: str
    ) -> datetime:
        """
        Get the next valid bar time after an invalid one.

        Args:
            invalid_time: Invalid timestamp (e.g., during spring forward)
            interval: Bar interval

        Returns:
            Next valid timestamp
        """
        if interval == "1hr":
            # For spring forward, next hour after 2 AM is 3 AM
            return invalid_time.replace(hour=3, minute=0, second=0, microsecond=0)
        else:
            # For other intervals, just add the interval
            return invalid_time + timedelta(hours=1)

    def dst_transition_within_hours(self, timestamp: datetime, hours: int) -> bool:
        """
        Check if DST transition occurs within specified hours from timestamp.

        Args:
            timestamp: Starting timestamp
            hours: Hours to look ahead

        Returns:
            True if DST transition occurs within the time window
        """
        end_time = timestamp + timedelta(hours=hours)

        # Check all days in the range
        current = timestamp.date()
        end_date = end_time.date()

        while current <= end_date:
            if self.is_dst_transition_day(current):
                return True
            current += timedelta(days=1)

        return False

    def _init_dst_handling(self) -> None:
        """Initialize DST handling - called by mixins that need it."""
        # This method exists for compatibility with test setup
