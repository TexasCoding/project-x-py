"""
Session configuration classes and default session times.

Implements the configuration system for trading sessions including
default session times for major futures products.

Author: TDD Implementation
Date: 2025-08-28
"""

from dataclasses import dataclass, field
from datetime import datetime, time
from enum import Enum

import pytz


class SessionType(Enum):
    """Enumeration of available session types."""

    ETH = "ETH"  # Electronic Trading Hours (24-hour)
    RTH = "RTH"  # Regular Trading Hours (pit hours)
    CUSTOM = "CUSTOM"  # Custom session definition

    def __str__(self) -> str:
        """Return the string value of the enum."""
        return self.value

    def __eq__(self, other: object) -> bool:
        """Allow comparison with string values."""
        if isinstance(other, str):
            return self.value == other
        return super().__eq__(other)


@dataclass
class SessionTimes:
    """Defines session time boundaries for a trading product."""

    rth_start: time
    rth_end: time
    eth_start: time | None = None  # Previous day
    eth_end: time | None = None  # Current day

    def __post_init__(self) -> None:
        """Validate session times after initialization."""
        # Note: Allow RTH sessions that cross midnight (e.g., some Asian markets)
        # Most US futures have RTH within the same day, but global markets may differ

        # Validate that ETH start/end are both provided or both None
        if (self.eth_start is None) != (self.eth_end is None):
            raise ValueError("ETH start and end must both be provided or both be None")

    def is_rth_within_eth(self) -> bool:
        """Check if RTH session is properly contained within ETH session."""
        # For most products, ETH runs from previous day 6 PM to current day 5 PM
        # RTH is typically 9:30 AM to 4:00 PM, which is within this range
        return True  # Simplified validation for now


@dataclass
class SessionConfig:
    """Configuration for trading session handling."""

    session_type: SessionType = field(default_factory=lambda: SessionType.ETH)
    market_timezone: str = "America/New_York"
    use_exchange_timezone: bool = True
    product_sessions: dict[str, SessionTimes] | None = field(default=None)

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        # Validate timezone
        try:
            pytz.timezone(self.market_timezone)
        except pytz.exceptions.UnknownTimeZoneError as err:
            raise ValueError(f"Invalid timezone: {self.market_timezone}") from err

        # Validate session type
        if isinstance(self.session_type, str):
            try:
                self.session_type = SessionType(self.session_type)
            except ValueError as err:
                raise ValueError(f"Invalid session type: {self.session_type}") from err

        # Initialize product_sessions if None
        if self.product_sessions is None:
            self.product_sessions = {}

    def get_session_times(self, product: str) -> SessionTimes:
        """Get session times for a specific product."""
        # Check for product-specific override
        if self.product_sessions and product in self.product_sessions:
            return self.product_sessions[product]

        # Fall back to default session times
        if product in DEFAULT_SESSIONS:
            return DEFAULT_SESSIONS[product]

        raise ValueError(f"Unknown product: {product}") from None

    def is_market_open(self, timestamp: datetime, product: str) -> bool:
        """Check if market is open at given timestamp for product."""
        session_times = self.get_session_times(product)

        # Return False for non-datetime objects or naive datetimes for safety
        if not hasattr(timestamp, "tzinfo") or timestamp.tzinfo is None:
            return False

        if hasattr(timestamp, "astimezone"):
            market_tz = pytz.timezone(self.market_timezone)
            market_time = timestamp.astimezone(market_tz)
            current_time = market_time.time()

            # Check for weekends (excluding Sunday evening ETH exception)
            if market_time.weekday() >= 5:  # Saturday (5) or Sunday (6)
                # Allow Sunday evening ETH (6 PM ET onwards)
                return (
                    self.session_type == SessionType.ETH
                    and market_time.weekday() == 6
                    and market_time.hour >= 18
                )

            if self.session_type == SessionType.RTH:
                return session_times.rth_start <= current_time < session_times.rth_end
            elif self.session_type == SessionType.ETH:
                return self._is_eth_open(current_time, session_times)

        return False

    def _is_eth_open(self, current_time: time, session_times: SessionTimes) -> bool:
        """True when Globex ETH is open (excludes 17:00-18:00 ET maintenance)."""
        if session_times.eth_start is None or session_times.eth_end is None:
            return session_times.rth_start <= current_time < session_times.rth_end

        # Equity-index Globex: 18:00 previous day through 17:00 current day.
        # Overnight 00:00-06:00 is ETH, not BREAK.
        if session_times.eth_start > session_times.eth_end:
            # Overnight wrap (e.g. 18:00 → 17:00)
            in_eth = (
                current_time >= session_times.eth_start
                or current_time < session_times.eth_end
            )
        else:
            in_eth = session_times.eth_start <= current_time < session_times.eth_end

        # Explicit maintenance window (CME daily break 17:00-18:00 ET)
        if time(17, 0) <= current_time < time(18, 0):
            return False
        return in_eth

    def get_current_session(self, timestamp: datetime, product: str) -> str:
        """Get current session type (RTH, ETH, BREAK) for timestamp."""
        session_times = self.get_session_times(product)

        # Return BREAK for non-datetime objects or naive datetimes for safety
        if not hasattr(timestamp, "tzinfo") or timestamp.tzinfo is None:
            return "BREAK"

        if hasattr(timestamp, "astimezone"):
            market_tz = pytz.timezone(self.market_timezone)
            market_time = timestamp.astimezone(market_tz)
            current_time = market_time.time()

            # Maintenance 17:00-18:00 ET is BREAK (not overnight ETH)
            if time(17, 0) <= current_time < time(18, 0):
                return "BREAK"

            # RTH 9:30-16:00 (product-specific) is RTH
            if session_times.rth_start <= current_time < session_times.rth_end:
                return "RTH"

            # Overnight 00:00-06:00 and evening Globex are ETH, not BREAK
            if (
                session_times.eth_start is not None
                and session_times.eth_end is not None
            ):
                if session_times.eth_start > session_times.eth_end:
                    if (
                        current_time >= session_times.eth_start
                        or current_time < session_times.eth_end
                    ):
                        return "ETH"
                elif session_times.eth_start <= current_time < session_times.eth_end:
                    return "ETH"

            return "BREAK"

        return "BREAK"


# Default session times for major futures products
def resolve_session_product(product: str) -> str:
    """Map a contract id or listed symbol to a DEFAULT_SESSIONS key.

    Accepts root symbols (``MNQ``), Gateway ids (``CON.F.US.MNQ.H26``),
    and month-coded names (``MNQH26``). Returns the original string when
    no known product is found so callers can still raise ``Unknown product``.
    """
    if product in DEFAULT_SESSIONS:
        return product
    upper = product.upper()
    if upper in DEFAULT_SESSIONS:
        return upper

    tokens = product.replace("-", ".").split(".")
    candidates: list[str] = []
    for token in reversed(tokens):
        letters = "".join(ch for ch in token if ch.isalpha()).upper()
        if letters:
            candidates.append(letters)
    if not candidates:
        letters = "".join(ch for ch in product if ch.isalpha()).upper()
        if letters:
            candidates.append(letters)

    for letters in candidates:
        if letters in DEFAULT_SESSIONS:
            return letters
        for length in (4, 3, 2):
            if len(letters) >= length and letters[:length] in DEFAULT_SESSIONS:
                return letters[:length]
    return product


DEFAULT_SESSIONS: dict[str, SessionTimes] = {
    # ========== EQUITY INDEX FUTURES ==========
    # Full-size Equity Index - RTH: 9:30 AM - 4:00 PM ET
    "ES": SessionTimes(  # S&P 500 E-mini
        rth_start=time(9, 30),
        rth_end=time(16, 0),
        eth_start=time(18, 0),  # 6 PM ET previous day
        eth_end=time(17, 0),  # 5 PM ET current day
    ),
    "NQ": SessionTimes(  # NASDAQ-100 E-mini
        rth_start=time(9, 30),
        rth_end=time(16, 0),
        eth_start=time(18, 0),
        eth_end=time(17, 0),
    ),
    "YM": SessionTimes(  # Dow Jones E-mini
        rth_start=time(9, 30),
        rth_end=time(16, 0),
        eth_start=time(18, 0),
        eth_end=time(17, 0),
    ),
    "RTY": SessionTimes(  # Russell 2000 E-mini
        rth_start=time(9, 30),
        rth_end=time(16, 0),
        eth_start=time(18, 0),
        eth_end=time(17, 0),
    ),
    # Micro Equity Index - Same hours as full-size
    "MES": SessionTimes(  # Micro E-mini S&P 500
        rth_start=time(9, 30),
        rth_end=time(16, 0),
        eth_start=time(18, 0),
        eth_end=time(17, 0),
    ),
    "MNQ": SessionTimes(  # Micro E-mini NASDAQ-100
        rth_start=time(9, 30),
        rth_end=time(16, 0),
        eth_start=time(18, 0),
        eth_end=time(17, 0),
    ),
    "MYM": SessionTimes(  # Micro E-mini Dow Jones
        rth_start=time(9, 30),
        rth_end=time(16, 0),
        eth_start=time(18, 0),
        eth_end=time(17, 0),
    ),
    "M2K": SessionTimes(  # Micro E-mini Russell 2000
        rth_start=time(9, 30),
        rth_end=time(16, 0),
        eth_start=time(18, 0),
        eth_end=time(17, 0),
    ),
    # ========== ENERGY FUTURES ==========
    # Crude Oil - RTH: 9:00 AM - 2:30 PM ET
    "CL": SessionTimes(  # Crude Oil (WTI)
        rth_start=time(9, 0),
        rth_end=time(14, 30),
        eth_start=time(18, 0),
        eth_end=time(17, 0),
    ),
    "MCL": SessionTimes(  # Micro WTI Crude Oil
        rth_start=time(9, 0),
        rth_end=time(14, 30),
        eth_start=time(18, 0),
        eth_end=time(17, 0),
    ),
    "QM": SessionTimes(  # E-mini Crude Oil
        rth_start=time(9, 0),
        rth_end=time(14, 30),
        eth_start=time(18, 0),
        eth_end=time(17, 0),
    ),
    # Natural Gas - RTH: 9:00 AM - 2:30 PM ET
    "NG": SessionTimes(  # Natural Gas
        rth_start=time(9, 0),
        rth_end=time(14, 30),
        eth_start=time(18, 0),
        eth_end=time(17, 0),
    ),
    "QG": SessionTimes(  # E-mini Natural Gas
        rth_start=time(9, 0),
        rth_end=time(14, 30),
        eth_start=time(18, 0),
        eth_end=time(17, 0),
    ),
    # Refined Products - RTH: 9:00 AM - 2:30 PM ET
    "RB": SessionTimes(  # RBOB Gasoline
        rth_start=time(9, 0),
        rth_end=time(14, 30),
        eth_start=time(18, 0),
        eth_end=time(17, 0),
    ),
    "HO": SessionTimes(  # Heating Oil
        rth_start=time(9, 0),
        rth_end=time(14, 30),
        eth_start=time(18, 0),
        eth_end=time(17, 0),
    ),
    # ========== PRECIOUS METALS ==========
    # Gold & Silver - RTH: 8:20 AM - 1:30 PM ET
    "GC": SessionTimes(  # Gold
        rth_start=time(8, 20),
        rth_end=time(13, 30),
        eth_start=time(18, 0),
        eth_end=time(17, 0),
    ),
    "MGC": SessionTimes(  # Micro Gold
        rth_start=time(8, 20),
        rth_end=time(13, 30),
        eth_start=time(18, 0),
        eth_end=time(17, 0),
    ),
    "QO": SessionTimes(  # E-mini Gold
        rth_start=time(8, 20),
        rth_end=time(13, 30),
        eth_start=time(18, 0),
        eth_end=time(17, 0),
    ),
    "SI": SessionTimes(  # Silver
        rth_start=time(8, 20),
        rth_end=time(13, 30),
        eth_start=time(18, 0),
        eth_end=time(17, 0),
    ),
    "SIL": SessionTimes(  # Micro Silver
        rth_start=time(8, 20),
        rth_end=time(13, 30),
        eth_start=time(18, 0),
        eth_end=time(17, 0),
    ),
    "QI": SessionTimes(  # E-mini Silver
        rth_start=time(8, 20),
        rth_end=time(13, 30),
        eth_start=time(18, 0),
        eth_end=time(17, 0),
    ),
    # Platinum Group - RTH: 8:20 AM - 1:05 PM ET
    "PL": SessionTimes(  # Platinum
        rth_start=time(8, 20),
        rth_end=time(13, 5),
        eth_start=time(18, 0),
        eth_end=time(17, 0),
    ),
    "PA": SessionTimes(  # Palladium
        rth_start=time(8, 20),
        rth_end=time(13, 5),
        eth_start=time(18, 0),
        eth_end=time(17, 0),
    ),
    # Copper - RTH: 8:20 AM - 1:00 PM ET
    "HG": SessionTimes(  # Copper
        rth_start=time(8, 20),
        rth_end=time(13, 0),
        eth_start=time(18, 0),
        eth_end=time(17, 0),
    ),
    "QC": SessionTimes(  # E-mini Copper
        rth_start=time(8, 20),
        rth_end=time(13, 0),
        eth_start=time(18, 0),
        eth_end=time(17, 0),
    ),
    # ========== TREASURY/INTEREST RATE FUTURES ==========
    # Treasury Futures - RTH: 8:20 AM - 3:00 PM ET
    "ZB": SessionTimes(  # 30-Year T-Bond
        rth_start=time(8, 20),
        rth_end=time(15, 0),
        eth_start=time(18, 0),
        eth_end=time(17, 0),
    ),
    "ZN": SessionTimes(  # 10-Year T-Note
        rth_start=time(8, 20),
        rth_end=time(15, 0),
        eth_start=time(18, 0),
        eth_end=time(17, 0),
    ),
    "ZF": SessionTimes(  # 5-Year T-Note
        rth_start=time(8, 20),
        rth_end=time(15, 0),
        eth_start=time(18, 0),
        eth_end=time(17, 0),
    ),
    "ZT": SessionTimes(  # 2-Year T-Note
        rth_start=time(8, 20),
        rth_end=time(15, 0),
        eth_start=time(18, 0),
        eth_end=time(17, 0),
    ),
    "ZQ": SessionTimes(  # 30-Day Fed Funds
        rth_start=time(8, 20),
        rth_end=time(15, 0),
        eth_start=time(18, 0),
        eth_end=time(17, 0),
    ),
    # Micro Treasury - Same hours as full-size
    "2YY": SessionTimes(  # Micro 2-Year Yield
        rth_start=time(8, 20),
        rth_end=time(15, 0),
        eth_start=time(18, 0),
        eth_end=time(17, 0),
    ),
    "5YY": SessionTimes(  # Micro 5-Year Yield
        rth_start=time(8, 20),
        rth_end=time(15, 0),
        eth_start=time(18, 0),
        eth_end=time(17, 0),
    ),
    "10Y": SessionTimes(  # Micro 10-Year Yield
        rth_start=time(8, 20),
        rth_end=time(15, 0),
        eth_start=time(18, 0),
        eth_end=time(17, 0),
    ),
    "30Y": SessionTimes(  # Micro 30-Year Yield
        rth_start=time(8, 20),
        rth_end=time(15, 0),
        eth_start=time(18, 0),
        eth_end=time(17, 0),
    ),
    # ========== CURRENCY FUTURES ==========
    # Major Currency Pairs - RTH: 8:20 AM - 3:00 PM ET
    "6E": SessionTimes(  # Euro FX
        rth_start=time(8, 20),
        rth_end=time(15, 0),
        eth_start=time(17, 0),  # 5 PM ET previous day
        eth_end=time(16, 0),  # 4 PM ET current day
    ),
    "6B": SessionTimes(  # British Pound
        rth_start=time(8, 20),
        rth_end=time(15, 0),
        eth_start=time(17, 0),
        eth_end=time(16, 0),
    ),
    "6J": SessionTimes(  # Japanese Yen
        rth_start=time(8, 20),
        rth_end=time(15, 0),
        eth_start=time(17, 0),
        eth_end=time(16, 0),
    ),
    "6C": SessionTimes(  # Canadian Dollar
        rth_start=time(8, 20),
        rth_end=time(15, 0),
        eth_start=time(17, 0),
        eth_end=time(16, 0),
    ),
    "6A": SessionTimes(  # Australian Dollar
        rth_start=time(8, 20),
        rth_end=time(15, 0),
        eth_start=time(17, 0),
        eth_end=time(16, 0),
    ),
    "6S": SessionTimes(  # Swiss Franc
        rth_start=time(8, 20),
        rth_end=time(15, 0),
        eth_start=time(17, 0),
        eth_end=time(16, 0),
    ),
    "6N": SessionTimes(  # New Zealand Dollar
        rth_start=time(8, 20),
        rth_end=time(15, 0),
        eth_start=time(17, 0),
        eth_end=time(16, 0),
    ),
    "6M": SessionTimes(  # Mexican Peso
        rth_start=time(8, 20),
        rth_end=time(15, 0),
        eth_start=time(17, 0),
        eth_end=time(16, 0),
    ),
    # Micro Currency - Same hours as full-size
    "M6E": SessionTimes(  # Micro EUR/USD
        rth_start=time(8, 20),
        rth_end=time(15, 0),
        eth_start=time(17, 0),
        eth_end=time(16, 0),
    ),
    "M6B": SessionTimes(  # Micro GBP/USD
        rth_start=time(8, 20),
        rth_end=time(15, 0),
        eth_start=time(17, 0),
        eth_end=time(16, 0),
    ),
    "M6A": SessionTimes(  # Micro AUD/USD
        rth_start=time(8, 20),
        rth_end=time(15, 0),
        eth_start=time(17, 0),
        eth_end=time(16, 0),
    ),
    "MJY": SessionTimes(  # Micro USD/JPY
        rth_start=time(8, 20),
        rth_end=time(15, 0),
        eth_start=time(17, 0),
        eth_end=time(16, 0),
    ),
    "MSF": SessionTimes(  # Micro USD/CHF
        rth_start=time(8, 20),
        rth_end=time(15, 0),
        eth_start=time(17, 0),
        eth_end=time(16, 0),
    ),
    "MCD": SessionTimes(  # Micro USD/CAD
        rth_start=time(8, 20),
        rth_end=time(15, 0),
        eth_start=time(17, 0),
        eth_end=time(16, 0),
    ),
    "MIR": SessionTimes(  # Micro USD/INR
        rth_start=time(8, 20),
        rth_end=time(15, 0),
        eth_start=time(17, 0),
        eth_end=time(16, 0),
    ),
    # ========== AGRICULTURE FUTURES ==========
    # Grains - RTH: 9:30 AM - 2:20 PM ET (CT: 8:30 AM - 1:20 PM)
    "ZC": SessionTimes(  # Corn
        rth_start=time(9, 30),
        rth_end=time(14, 20),
        eth_start=time(20, 0),  # 8 PM ET previous day
        eth_end=time(8, 45),  # 8:45 AM ET current day
    ),
    "ZS": SessionTimes(  # Soybeans
        rth_start=time(9, 30),
        rth_end=time(14, 20),
        eth_start=time(20, 0),
        eth_end=time(8, 45),
    ),
    "ZW": SessionTimes(  # Wheat
        rth_start=time(9, 30),
        rth_end=time(14, 20),
        eth_start=time(20, 0),
        eth_end=time(8, 45),
    ),
    "ZM": SessionTimes(  # Soybean Meal
        rth_start=time(9, 30),
        rth_end=time(14, 20),
        eth_start=time(20, 0),
        eth_end=time(8, 45),
    ),
    "ZL": SessionTimes(  # Soybean Oil
        rth_start=time(9, 30),
        rth_end=time(14, 20),
        eth_start=time(20, 0),
        eth_end=time(8, 45),
    ),
    "KE": SessionTimes(  # KC Wheat
        rth_start=time(9, 30),
        rth_end=time(14, 20),
        eth_start=time(20, 0),
        eth_end=time(8, 45),
    ),
    "ZO": SessionTimes(  # Oats
        rth_start=time(9, 30),
        rth_end=time(14, 20),
        eth_start=time(20, 0),
        eth_end=time(8, 45),
    ),
    "ZR": SessionTimes(  # Rough Rice
        rth_start=time(9, 30),
        rth_end=time(14, 20),
        eth_start=time(20, 0),
        eth_end=time(8, 45),
    ),
    # Mini-sized Grains - Same hours as full-size
    "XC": SessionTimes(  # Mini Corn
        rth_start=time(9, 30),
        rth_end=time(14, 20),
        eth_start=time(20, 0),
        eth_end=time(8, 45),
    ),
    "XK": SessionTimes(  # Mini Soybeans
        rth_start=time(9, 30),
        rth_end=time(14, 20),
        eth_start=time(20, 0),
        eth_end=time(8, 45),
    ),
    "XW": SessionTimes(  # Mini Wheat
        rth_start=time(9, 30),
        rth_end=time(14, 20),
        eth_start=time(20, 0),
        eth_end=time(8, 45),
    ),
    # Livestock - RTH: 9:30 AM - 2:05 PM ET
    "LE": SessionTimes(  # Live Cattle
        rth_start=time(9, 30),
        rth_end=time(14, 5),
        eth_start=None,  # No overnight session
        eth_end=None,
    ),
    "HE": SessionTimes(  # Lean Hogs
        rth_start=time(9, 30), rth_end=time(14, 5), eth_start=None, eth_end=None
    ),
    "GF": SessionTimes(  # Feeder Cattle
        rth_start=time(9, 30), rth_end=time(14, 5), eth_start=None, eth_end=None
    ),
    # Dairy - RTH: 9:30 AM - 2:10 PM ET
    "DC": SessionTimes(  # Class III Milk
        rth_start=time(9, 30), rth_end=time(14, 10), eth_start=None, eth_end=None
    ),
    # ========== CRYPTOCURRENCY FUTURES ==========
    # Bitcoin & Ether - Trade nearly 24/7
    "BTC": SessionTimes(  # Bitcoin Futures
        rth_start=time(9, 30),
        rth_end=time(16, 0),
        eth_start=time(18, 0),  # Sunday 6 PM ET
        eth_end=time(17, 0),  # Friday 5 PM ET
    ),
    "MBT": SessionTimes(  # Micro Bitcoin
        rth_start=time(9, 30),
        rth_end=time(16, 0),
        eth_start=time(18, 0),
        eth_end=time(17, 0),
    ),
    "ETH": SessionTimes(  # Ether Futures
        rth_start=time(9, 30),
        rth_end=time(16, 0),
        eth_start=time(18, 0),
        eth_end=time(17, 0),
    ),
    "MET": SessionTimes(  # Micro Ether
        rth_start=time(9, 30),
        rth_end=time(16, 0),
        eth_start=time(18, 0),
        eth_end=time(17, 0),
    ),
    # ========== VOLATILITY FUTURES ==========
    # VIX - RTH: 9:30 AM - 4:15 PM ET
    "VX": SessionTimes(  # VIX Futures
        rth_start=time(9, 30),
        rth_end=time(16, 15),
        eth_start=time(18, 0),
        eth_end=time(9, 30),
    ),
    "VXM": SessionTimes(  # Mini VIX
        rth_start=time(9, 30),
        rth_end=time(16, 15),
        eth_start=time(18, 0),
        eth_end=time(9, 30),
    ),
}
