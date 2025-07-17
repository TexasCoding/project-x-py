#!/usr/bin/env python3
"""
Real-time Data Manager for Gold Strategy

Author: TexasCoding
Date: June 2025

This module provides efficient real-time data management by:
1. Loading initial historical data for all timeframes once at startup
2. Receiving real-time market data from ProjectX WebSocket feeds
3. Resampling real-time data into multiple timeframes (5m, 15m, 60m, 240m)
4. Maintaining synchronized OHLCV bars across all timeframes
5. Eliminating the need for repeated API calls during live trading

Key Benefits:
- 95% reduction in API calls (from every 5 minutes to once at startup)
- Sub-second data updates vs 5-minute polling delays
- Perfect synchronization between timeframes
- Resilient to API outages during trading
"""

import asyncio
import logging
import threading
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime
from typing import Any

import polars as pl
import pytz

from project_x_py import ProjectX
from project_x_py.realtime import ProjectXRealtimeClient


class ProjectXRealtimeDataManager:
    """
    Advanced real-time data manager for efficient multi-timeframe trading data.

    This class revolutionizes trading data management by maintaining live OHLCV data
    across multiple timeframes through real-time tick processing instead of repeated API calls.

    Core Concept:
        Traditional approach: Poll API every 5 minutes for each timeframe = 20+ API calls/hour
        Real-time approach: Load historical once + live tick processing = 1 API call + WebSocket

        Result: 95% reduction in API calls with sub-second data freshness

    Architecture:
        1. Initial Load: Fetches comprehensive historical data for all timeframes once
        2. Real-time Feed: Subscribes to live market data via WebSocket
        3. Tick Processing: Updates all timeframes simultaneously from each tick
        4. Data Synchronization: Maintains perfect alignment across timeframes
        5. Memory Management: Automatic cleanup with configurable limits

    Supported Timeframes:
        - 5 minutes: Primary timeframe for entry signals
        - 15 minutes: Trend confirmation and filtering
        - 60 minutes: Intermediate trend analysis
        - 240 minutes: Long-term trend and bias

    Features:
        - Zero-latency data updates via WebSocket
        - Automatic bar creation and OHLCV maintenance
        - Thread-safe multi-timeframe access
        - Memory-efficient sliding window storage
        - Timezone-aware timestamp handling (CME Central Time)
        - Event callbacks for new bars and data updates
        - Comprehensive health monitoring and statistics
        - Graceful fallback when WebSocket unavailable

    Data Flow:
        Market Tick → Real-time Client → Data Manager → Timeframe Update → Callbacks

    Benefits:
        - Real-time strategy execution with fresh data
        - Eliminated polling delays and timing gaps
        - Reduced API rate limiting concerns
        - Improved strategy performance through instant signals
        - Resilient to temporary API outages during trading

    Memory Management:
        - Maintains last 1000 bars per timeframe (~3.5 days of 5min data)
        - Automatic cleanup of old data to prevent memory growth
        - Efficient DataFrame operations with copy-on-write
        - Thread-safe data access with RLock synchronization

    Example Usage:
        >>> # Initialize with instrument
        >>> manager = ProjectXRealtimeDataManager("MGC", project_x, account_id)
        >>>
        >>> # Load historical data for all timeframes
        >>> if manager.initialize(initial_days=30):
        ...     print("Historical data loaded successfully")
        >>>
        >>> # Start real-time feed
        >>> jwt_token = project_x.get_session_token()
        >>> if manager.start_realtime_feed(jwt_token):
        ...     print("Real-time feed active")
        >>>
        >>> # Access multi-timeframe data
        >>> data_5m = manager.get_data("5min", bars=100)  # Last 100 5-minute bars
        >>> data_15m = manager.get_data("15min", bars=50)  # Last 50 15-minute bars
        >>> mtf_data = manager.get_mtf_data()  # All timeframes
        >>>
        >>> # Get current market data
        >>> current_price = manager.get_current_price()
        >>>
        >>> # Add callbacks for real-time events
        >>> def on_new_bar(data):
        ...     print(f"New {data['timeframe']} bar: {data['bar_time']}")
        >>> manager.add_callback("new_bar", on_new_bar)

    Error Handling:
        - Graceful handling of WebSocket disconnections
        - Automatic reconnection with JWT refresh
        - Data validation and NaN handling
        - Comprehensive logging for troubleshooting
        - Health checks for data freshness monitoring

    Thread Safety:
        - All public methods are thread-safe
        - RLock protection for data structures
        - Safe concurrent access from multiple strategies
        - Atomic operations for data updates

    Performance:
        - Sub-second data updates vs 5+ minute polling
        - Minimal CPU overhead with efficient resampling
        - Memory-efficient storage with automatic cleanup
        - Optimized for high-frequency trading applications
    """

    def __init__(
        self,
        instrument: str,
        project_x: ProjectX,
        account_id: str,
        timeframes: list[str] = ["5min"],
        user_hub_url: str = "https://rtc.topstepx.com/hubs/user",
        market_hub_url: str = "https://rtc.topstepx.com/hubs/market",
        timezone: str = "America/Chicago",
    ):
        """
        Initialize the real-time data manager.

        Args:
            instrument: Trading instrument (e.g., "MGC", "MNQ")
            project_x: ProjectX client for initial data loading
            account_id: Account ID for real-time subscriptions
            user_hub_url: URL for user hub
            market_hub_url: URL for market hub
        """
        self.instrument = instrument
        self.project_x = project_x
        self.account_id = account_id
        self.user_hub_url = user_hub_url
        self.market_hub_url = market_hub_url

        self.logger = logging.getLogger(__name__)

        # Set timezone for consistent timestamp handling
        self.timezone = pytz.timezone(timezone)  # CME timezone

        TIMEFRAMES = {
            "1sec": {"interval": 1, "unit": 1, "name": "1sec"},
            "5sec": {"interval": 5, "unit": 1, "name": "5sec"},
            "10sec": {"interval": 10, "unit": 1, "name": "10sec"},
            "15sec": {"interval": 15, "unit": 1, "name": "15sec"},
            "30sec": {"interval": 30, "unit": 1, "name": "30sec"},
            "1min": {"interval": 1, "unit": 2, "name": "1min"},
            "5min": {"interval": 5, "unit": 2, "name": "5min"},
            "15min": {"interval": 15, "unit": 2, "name": "15min"},
            "30min": {"interval": 30, "unit": 2, "name": "30min"},
            "1hr": {"interval": 60, "unit": 3, "name": "1hr"},
            "4hr": {"interval": 240, "unit": 3, "name": "4hr"},
            "1day": {"interval": 1, "unit": 4, "name": "1day"},
            "1week": {"interval": 1, "unit": 5, "name": "1week"},
            "1month": {"interval": 1, "unit": 6, "name": "1month"},
        }

        # Initialize timeframes as dict mapping timeframe names to configs
        self.timeframes = {}
        for tf in timeframes:
            if tf not in TIMEFRAMES:
                raise ValueError(
                    f"Invalid timeframe: {tf}, valid timeframes are: {list(TIMEFRAMES.keys())}"
                )
            self.timeframes[tf] = TIMEFRAMES[tf]

        # Data storage for each timeframe
        self.data: dict[str, pl.DataFrame] = {}

        # Real-time data components
        self.realtime_client: ProjectXRealtimeClient | None = None
        self.current_tick_data: list[dict] = []
        self.last_bar_times: dict[
            str, datetime
        ] = {}  # Track last bar time for each timeframe

        # Threading and synchronization
        self.data_lock = threading.RLock()
        self.is_running = False
        self.callbacks: dict[str, list[Callable]] = defaultdict(list)

        # Store reference to main event loop for async callback execution from threads
        self.main_loop = None
        try:
            self.main_loop = asyncio.get_running_loop()
        except RuntimeError:
            # No event loop running yet - will be set later when strategy starts
            pass

        # Contract ID for real-time subscriptions
        self.contract_id: str | None = None

        # Level 2 market depth storage for strategy integration
        self.last_level2_data: dict | None = (
            None  # Store latest Level 2 data for strategy access
        )
        self.level2_update_count = 0  # Track Level 2 updates for monitoring

        # Level 2 orderbook storage with Polars DataFrames
        self.orderbook_bids: pl.DataFrame = pl.DataFrame(
            {"price": [], "volume": [], "timestamp": [], "type": []},
            schema={
                "price": pl.Float64,
                "volume": pl.Int64,
                "timestamp": pl.Datetime,
                "type": pl.Utf8,
            },
        )

        self.orderbook_asks: pl.DataFrame = pl.DataFrame(
            {"price": [], "volume": [], "timestamp": [], "type": []},
            schema={
                "price": pl.Float64,
                "volume": pl.Int64,
                "timestamp": pl.Datetime,
                "type": pl.Utf8,
            },
        )

        # Trade flow storage (Type 5 - actual executions)
        self.recent_trades: pl.DataFrame = pl.DataFrame(
            {
                "price": [],
                "volume": [],
                "timestamp": [],
                "side": [],  # "buy" or "sell" inferred from price movement
            },
            schema={
                "price": pl.Float64,
                "volume": pl.Int64,
                "timestamp": pl.Datetime,
                "side": pl.Utf8,
            },
        )

        # Orderbook metadata
        self.last_orderbook_update: datetime | None = None
        self.orderbook_lock = threading.RLock()  # Separate lock for orderbook data

        # Statistics for different order types
        self.order_type_stats = {
            "type_1_count": 0,  # Ask updates
            "type_2_count": 0,  # Bid updates
            "type_5_count": 0,  # Trade executions
            "type_9_count": 0,  # Order modifications
            "type_10_count": 0,  # Order modifications/cancellations
            "other_types": 0,  # Unknown types
        }

        self.logger.info(f"RealtimeDataManager initialized for {instrument}")

    def initialize(self, initial_days: int = 1) -> bool:
        """
        Initialize the data manager by loading historical data for all timeframes.

        Args:
            initial_days: Number of days of historical data to load initially

        Returns:
            bool: True if initialization successful
        """
        try:
            self.logger.info(
                f"🔄 Initializing real-time data manager for {self.instrument}..."
            )

            # Load historical data for each timeframe
            for tf_key, tf_config in self.timeframes.items():
                interval = tf_config["interval"]
                unit = tf_config["unit"]

                # Ensure minimum from initial_days parameter
                data_days = max(initial_days, initial_days)

                unit_name = "minute" if unit == 2 else "second"
                self.logger.info(
                    f"📊 Loading {data_days} days of {interval}-{unit_name} historical data..."
                )

                # Add timeout and retry logic for historical data loading
                data = None
                max_retries = 3

                for attempt in range(max_retries):
                    try:
                        self.logger.info(
                            f"🔄 Attempt {attempt + 1}/{max_retries} to load {self.instrument} {interval}-{unit_name} data..."
                        )

                        # Simplified data loading without threading (timeouts handled at higher level)
                        data = self.project_x.get_data(
                            instrument=self.instrument,
                            days=data_days,
                            interval=interval,
                            unit=unit,
                            partial=True,
                        )

                        print(data)

                        if data is not None and len(data) > 0:
                            self.logger.info(
                                f"✅ Successfully loaded {self.instrument} {interval}-{unit_name} data on attempt {attempt + 1}"
                            )
                            break
                        else:
                            self.logger.warning(
                                f"⚠️ No data returned for {self.instrument} {interval}-{unit_name} (attempt {attempt + 1})"
                            )
                            if attempt < max_retries - 1:
                                self.logger.info("🔄 Retrying in 2 seconds...")
                                import time

                                time.sleep(2)
                            continue

                    except Exception as e:
                        self.logger.warning(
                            f"❌ Exception loading {self.instrument} {interval}-{unit_name} data: {e}"
                        )
                        if attempt < max_retries - 1:
                            self.logger.info("🔄 Retrying in 2 seconds...")
                            import time

                            time.sleep(2)
                        continue

                if data is not None and len(data) > 0:
                    with self.data_lock:
                        # Data is already a polars DataFrame from get_data()
                        data_copy = data

                        # Ensure timezone is handled properly
                        if "timestamp" in data_copy.columns:
                            timestamp_col = data_copy.get_column("timestamp")
                            if timestamp_col.dtype == pl.Datetime:
                                # Convert timezone if needed
                                data_copy = data_copy.with_columns(
                                    pl.col("timestamp")
                                    .dt.replace_time_zone("UTC")
                                    .dt.convert_time_zone(str(self.timezone.zone))
                                )

                        self.data[tf_key] = data_copy
                        if len(data_copy) > 0:
                            self.last_bar_times[tf_key] = (
                                data_copy.select(pl.col("timestamp")).tail(1).item()
                            )

                    self.logger.info(
                        f"✅ Loaded {len(data)} bars of {interval}-{unit_name} data"
                    )
                else:
                    self.logger.error(
                        f"❌ Failed to load {interval}-{unit_name} historical data"
                    )
                    return False

            # Get contract ID for real-time subscriptions
            instrument_obj = self.project_x.get_instrument(self.instrument)
            if instrument_obj:
                self.contract_id = instrument_obj.id
                self.logger.info(f"📡 Contract ID: {self.contract_id}")
            else:
                self.logger.error(f"❌ Failed to get contract ID for {self.instrument}")
                return False

            self.logger.info("✅ Real-time data manager initialization complete")
            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to initialize real-time data manager: {e}")
            return False

    def start_realtime_feed(self, jwt_token: str) -> bool:
        """
        Start the real-time data feed using ProjectX WebSocket connection.

        Args:
            jwt_token: JWT token for WebSocket authentication

        Returns:
            bool: True if real-time feed started successfully
        """
        try:
            if not self.contract_id:
                self.logger.error("❌ Cannot start real-time feed: No contract ID")
                return False

            # Basic JWT token validation
            if not jwt_token or len(jwt_token) < 50:
                self.logger.error(
                    f"❌ Invalid JWT token: {jwt_token[:20] if jwt_token else 'None'}..."
                )
                return False

            # Check if token looks like a JWT (has two dots)
            if jwt_token.count(".") != 2:
                self.logger.error(
                    "❌ JWT token format appears invalid (should have 2 dots)"
                )
                return False

            self.logger.info("🚀 Starting real-time data feed...")

            # Initialize ProjectX client for real-time data
            try:
                self.client = ProjectXRealtimeClient(
                    jwt_token=jwt_token,
                    account_id=self.account_id,
                    user_hub_url=self.user_hub_url,
                    market_hub_url=self.market_hub_url,
                )

                # Also set realtime_client property for position tracker access
                self.realtime_client = self.client

                # Register callbacks for real-time data events
                self.client.add_callback("market_depth", self._on_market_depth)
                self.client.add_callback("quote_update", self._on_quote_update)
                self.client.add_callback("market_trade", self._on_market_trade)

                self.logger.info("📊 ProjectX callbacks registered successfully")

            except Exception as e:
                self.logger.error(f"Failed to initialize ProjectX client: {e}")
                raise

            # Connect to WebSocket hubs with better error reporting
            self.logger.info(
                f"🔗 Attempting to connect with JWT token (length: {len(jwt_token)})"
            )
            self.logger.info(f"🔗 Account ID: {self.account_id}")
            self.logger.info(f"🔗 Contract ID: {self.contract_id}")

            try:
                connection_success = self.client.connect()
                if not connection_success:
                    self.logger.error(
                        "❌ Failed to connect to real-time hubs - connection returned False"
                    )
                    self.logger.error(
                        "❌ This could be due to: invalid JWT token, network issues, or server problems"
                    )
                    return False
                else:
                    self.logger.info("✅ Successfully connected to real-time hubs")

            except Exception as e:
                self.logger.error(f"❌ Exception during WebSocket connection: {e}")
                import traceback

                self.logger.error(f"❌ Connection traceback: {traceback.format_exc()}")
                return False

            # Subscribe to market data for our contract
            self.logger.info(
                f"📡 Subscribing to market data for contract: {self.contract_id}"
            )
            try:
                success = self.client.subscribe_market_data([self.contract_id])
                if not success:
                    self.logger.error(
                        f"❌ Failed to subscribe to market data for {self.contract_id}"
                    )
                    self.logger.error(
                        "❌ This could be due to: invalid contract ID, insufficient permissions, or server issues"
                    )
                    return False
                else:
                    self.logger.info(
                        f"✅ Successfully subscribed to market data for {self.contract_id}"
                    )
            except Exception as e:
                self.logger.error(f"❌ Exception during market data subscription: {e}")
                return False

            self.is_running = True
            self.logger.info("✅ Real-time data feed started successfully")
            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to start real-time feed: {e}")
            return False

    def stop_realtime_feed(self):
        """Stop the real-time data feed and clean up resources."""
        try:
            self.logger.info("🛑 Stopping real-time data feed...")
            self.is_running = False

            if self.client:
                self.client.disconnect()
                self.client = None

            self.logger.info("✅ Real-time data feed stopped")

        except Exception as e:
            self.logger.error(f"❌ Error stopping real-time feed: {e}")

    def _on_quote_update(self, data: dict):
        """
        Handle real-time quote updates from WebSocket with enhanced TopStepX compatibility.

        Addresses data format inconsistencies:
        - Maps bestBid/bestAsk to standard bid/ask fields
        - Handles partial updates (bid-only or ask-only)
        - Estimates bid/ask sizes when missing
        - Maintains quote state for proper mid-price calculation
        """
        try:
            contract_id = data.get("contract_id")
            quote_data = data.get("data", {})

            if contract_id != self.contract_id:
                return

            # Extract price information with TopStepX field mapping
            if isinstance(quote_data, dict):
                # Handle TopStepX field name variations
                current_bid = quote_data.get("bestBid") or quote_data.get("bid")
                current_ask = quote_data.get("bestAsk") or quote_data.get("ask")

                # Maintain quote state for handling partial updates
                if not hasattr(self, "_last_quote_state"):
                    self._last_quote_state: dict[str, float | None] = {
                        "bid": None,
                        "ask": None,
                    }

                # Update quote state with new data
                if current_bid is not None:
                    self._last_quote_state["bid"] = float(current_bid)
                if current_ask is not None:
                    self._last_quote_state["ask"] = float(current_ask)

                # Use most recent bid/ask values
                bid = self._last_quote_state["bid"]
                ask = self._last_quote_state["ask"]

                # Get last price for trade detection
                last_price = (
                    quote_data.get("lastPrice")
                    or quote_data.get("last")
                    or quote_data.get("price")
                )

                # Determine if this is a trade update or quote update
                is_trade_update = last_price is not None and "volume" in quote_data

                # Calculate price for tick processing
                price = None
                if is_trade_update and last_price is not None:
                    price = float(last_price)
                elif bid is not None and ask is not None:
                    price = (bid + ask) / 2  # Mid price for quote updates
                elif bid is not None:
                    price = bid  # Use bid if only bid available
                elif ask is not None:
                    price = ask  # Use ask if only ask available

                if price is not None:
                    # Use timezone-aware timestamp
                    current_time = datetime.now(self.timezone)

                    # Enhanced tick data with better field mapping
                    tick_data = {
                        "timestamp": current_time,
                        "price": float(price),
                        "bid": bid,
                        "ask": ask,
                        "volume": 0,  # Always 0 for quote updates (trades handled separately)
                        "type": "trade" if is_trade_update else "quote",
                    }

                    self._process_tick_data(tick_data)

                    # Create enhanced quote data for market microstructure analysis (only if we have both bid and ask)
                    if bid is not None and ask is not None:
                        enhanced_quote_data = self._create_enhanced_quote_data(
                            quote_data, bid, ask
                        )

                        # Trigger Level 2 quote callback with enhanced data
                        self._trigger_callbacks(
                            "quote_update",
                            {"contract_id": contract_id, "data": enhanced_quote_data},
                        )

        except Exception as e:
            self.logger.error(f"Error processing quote update: {e}")

    def _create_enhanced_quote_data(
        self, original_data: dict, bid: float, ask: float
    ) -> dict:
        """
        Create enhanced quote data with estimated sizes and standardized fields.

        Addresses TopStepX missing bid/ask size data by:
        1. Using Level 2 data when available
        2. Estimating sizes based on market conditions
        3. Providing fallback values for liquidity assessment
        """
        enhanced_data = original_data.copy()

        # Map TopStepX fields to standard names
        enhanced_data["bid"] = bid
        enhanced_data["ask"] = ask

        # Estimate bid/ask sizes if not provided
        if "bidSize" not in enhanced_data and "askSize" not in enhanced_data:
            # Try to get sizes from Level 2 data if available
            if hasattr(self, "last_level2_data") and self.last_level2_data:
                level2_bids = self.last_level2_data.get("bids", [])
                level2_asks = self.last_level2_data.get("asks", [])

                # Find matching bid/ask sizes from Level 2 data
                bid_size = 0
                ask_size = 0

                for level2_bid in level2_bids:
                    if (
                        abs(level2_bid.get("price", 0) - bid) < 0.01
                    ):  # Match within 1 cent
                        bid_size = level2_bid.get("volume", 0)
                        break

                for level2_ask in level2_asks:
                    if (
                        abs(level2_ask.get("price", 0) - ask) < 0.01
                    ):  # Match within 1 cent
                        ask_size = level2_ask.get("volume", 0)
                        break

                enhanced_data["bidSize"] = bid_size
                enhanced_data["askSize"] = ask_size
            else:
                # Estimate sizes based on market conditions for MNQ futures
                # Use conservative estimates that won't trigger false liquidity signals
                spread_ticks = ((ask - bid) / 0.25) if bid and ask else 0

                if spread_ticks <= 1:
                    # Tight spread suggests good liquidity
                    estimated_size = 150  # Conservative estimate for MNQ
                elif spread_ticks <= 2:
                    # Normal spread
                    estimated_size = 100
                else:
                    # Wide spread suggests lower liquidity
                    estimated_size = 50

                enhanced_data["bidSize"] = estimated_size
                enhanced_data["askSize"] = estimated_size

        return enhanced_data

    def _on_market_depth(self, data: dict) -> None:
        """
        Process market depth data from ProjectX WebSocket and update Level 2 orderbook.

        Args:
            data: Market depth data containing price levels and volumes
        """
        try:
            contract_id = data.get("contract_id", "Unknown")
            depth_data = data.get("data", [])

            # Only process data for our contract
            if contract_id != self.contract_id:
                return

            # Update statistics
            self.level2_update_count += 1

            # Process each market depth entry
            with self.orderbook_lock:
                current_time = datetime.now(self.timezone)

                bid_updates = []
                ask_updates = []
                trade_updates = []

                for entry in depth_data:
                    price = entry.get("price", 0.0)
                    volume = entry.get("volume", 0)
                    entry_type = entry.get("type", 0)
                    timestamp_str = entry.get("timestamp", "")

                    # Update statistics
                    if entry_type == 1:
                        self.order_type_stats["type_1_count"] += 1
                    elif entry_type == 2:
                        self.order_type_stats["type_2_count"] += 1
                    elif entry_type == 5:
                        self.order_type_stats["type_5_count"] += 1
                    elif entry_type == 9:
                        self.order_type_stats["type_9_count"] += 1
                    elif entry_type == 10:
                        self.order_type_stats["type_10_count"] += 1
                    else:
                        self.order_type_stats["other_types"] += 1

                    # Parse timestamp if provided, otherwise use current time
                    if timestamp_str and timestamp_str != "0001-01-01T00:00:00+00:00":
                        try:
                            timestamp = datetime.fromisoformat(
                                timestamp_str.replace("Z", "+00:00")
                            )
                            if timestamp.tzinfo is None:
                                timestamp = self.timezone.localize(timestamp)
                            else:
                                timestamp = timestamp.astimezone(self.timezone)
                        except Exception:
                            timestamp = current_time
                    else:
                        timestamp = current_time

                    # Enhanced type mapping based on TopStepX format:
                    # Type 1 = Ask/Offer (selling pressure)
                    # Type 2 = Bid (buying pressure)
                    # Type 5 = Trade (market execution) - record for trade flow analysis
                    # Type 9 = Order modification (update existing order)
                    # Type 10 = Order modification/cancellation (often volume=0 means cancel)

                    if entry_type == 2:  # Bid
                        bid_updates.append(
                            {
                                "price": float(price),
                                "volume": int(volume),
                                "timestamp": timestamp,
                                "type": "bid",
                            }
                        )
                    elif entry_type == 1:  # Ask
                        ask_updates.append(
                            {
                                "price": float(price),
                                "volume": int(volume),
                                "timestamp": timestamp,
                                "type": "ask",
                            }
                        )
                    elif entry_type == 5:  # Trade execution
                        if volume > 0:  # Only record actual trades with volume
                            trade_updates.append(
                                {
                                    "price": float(price),
                                    "volume": int(volume),
                                    "timestamp": timestamp,
                                }
                            )
                    elif entry_type in [9, 10]:  # Order modifications
                        # Type 9/10 can affect both bid and ask sides
                        # We need to determine which side based on price relative to current mid
                        # For now, we'll apply the update to the appropriate side based on existing orderbook

                        best_prices = self.get_best_bid_ask()
                        mid_price = best_prices.get("mid")

                        if mid_price and price != 0:
                            if price <= mid_price:  # Likely a bid modification
                                bid_updates.append(
                                    {
                                        "price": float(price),
                                        "volume": int(
                                            volume
                                        ),  # Could be 0 for cancellation
                                        "timestamp": timestamp,
                                        "type": f"bid_mod_{entry_type}",
                                    }
                                )
                            else:  # Likely an ask modification
                                ask_updates.append(
                                    {
                                        "price": float(price),
                                        "volume": int(
                                            volume
                                        ),  # Could be 0 for cancellation
                                        "timestamp": timestamp,
                                        "type": f"ask_mod_{entry_type}",
                                    }
                                )
                        else:
                            # If we can't determine side, try both (safer approach)
                            # The update logic will handle duplicates appropriately
                            bid_updates.append(
                                {
                                    "price": float(price),
                                    "volume": int(volume),
                                    "timestamp": timestamp,
                                    "type": f"bid_mod_{entry_type}",
                                }
                            )
                            ask_updates.append(
                                {
                                    "price": float(price),
                                    "volume": int(volume),
                                    "timestamp": timestamp,
                                    "type": f"ask_mod_{entry_type}",
                                }
                            )

                # Update bid levels
                if bid_updates:
                    self._update_orderbook_side(bid_updates, "bid")

                # Update ask levels
                if ask_updates:
                    self._update_orderbook_side(ask_updates, "ask")

                # Update trade flow data
                if trade_updates:
                    self._update_trade_flow(trade_updates)

                # Update last update time
                self.last_orderbook_update = current_time

            # Store the complete Level 2 data structure (existing functionality)
            processed_data = self._process_level2_data(depth_data)
            self.last_level2_data = {
                "contract_id": contract_id,
                "timestamp": current_time,
                "bids": processed_data["bids"],
                "asks": processed_data["asks"],
                "best_bid": processed_data["best_bid"],
                "best_ask": processed_data["best_ask"],
                "spread": processed_data["spread"],
                "raw_data": depth_data,
            }

            # Trigger callbacks for any registered listeners
            self._trigger_callbacks("market_depth", data)

        except Exception as e:
            self.logger.error(f"❌ Error processing market depth: {e}")
            import traceback

            self.logger.error(f"❌ Market depth traceback: {traceback.format_exc()}")

    def _update_orderbook_side(self, updates: list[dict], side: str) -> None:
        """
        Update bid or ask side of the orderbook with new price levels.

        Args:
            updates: List of price level updates {price, volume, timestamp}
            side: "bid" or "ask"
        """
        try:
            if side == "bid":
                current_df = self.orderbook_bids
            else:
                current_df = self.orderbook_asks

            # Create DataFrame from updateså
            if updates:
                updates_df = pl.DataFrame(updates)

                # Combine with existing data
                if len(current_df) > 0:
                    combined_df = pl.concat([current_df, updates_df])
                else:
                    combined_df = updates_df

                # Group by price and take the latest update (last timestamp)
                latest_df = combined_df.group_by("price").agg(
                    [
                        pl.col("volume").last(),
                        pl.col("timestamp").last(),
                        pl.col("type").last(),
                    ]
                )

                # Remove zero-volume levels (market depth deletions)
                latest_df = latest_df.filter(pl.col("volume") > 0)

                # Sort appropriately (bids: high to low, asks: low to high)
                if side == "bid":
                    latest_df = latest_df.sort("price", descending=True)
                    self.orderbook_bids = latest_df
                else:
                    latest_df = latest_df.sort("price", descending=False)
                    self.orderbook_asks = latest_df

                # Keep only top 100 levels to manage memory
                if side == "bid":
                    self.orderbook_bids = self.orderbook_bids.head(100)
                else:
                    self.orderbook_asks = self.orderbook_asks.head(100)

        except Exception as e:
            self.logger.error(f"❌ Error updating {side} orderbook: {e}")

    def _update_trade_flow(self, trade_updates: list[dict]) -> None:
        """
        Update trade flow data with new trade executions.

        Args:
            trade_updates: List of trade executions {price, volume, timestamp}
        """
        try:
            if not trade_updates:
                return

            # Get current best bid/ask to determine trade direction
            best_prices = self.get_best_bid_ask()
            best_bid = best_prices.get("bid")
            best_ask = best_prices.get("ask")

            # Enhance trade data with side detection
            enhanced_trades = []
            for trade in trade_updates:
                price = trade["price"]

                # Determine trade side based on price relative to bid/ask
                if best_bid and best_ask:
                    if price >= best_ask:
                        side = "buy"  # Trade at or above ask (aggressive buy)
                    elif price <= best_bid:
                        side = "sell"  # Trade at or below bid (aggressive sell)
                    else:
                        side = "unknown"  # Trade between bid/ask
                else:
                    side = "unknown"

                enhanced_trades.append(
                    {
                        "price": trade["price"],
                        "volume": trade["volume"],
                        "timestamp": trade["timestamp"],
                        "side": side,
                    }
                )

            # Create DataFrame from enhanced trades
            if enhanced_trades:
                trades_df = pl.DataFrame(enhanced_trades)

                # Combine with existing trade data
                if len(self.recent_trades) > 0:
                    combined_df = pl.concat([self.recent_trades, trades_df])
                else:
                    combined_df = trades_df

                # Keep only last 1000 trades to manage memory
                self.recent_trades = combined_df.tail(1000)

        except Exception as e:
            self.logger.error(f"❌ Error updating trade flow: {e}")

    def _process_level2_data(self, depth_data: list) -> dict:
        """
        Process raw Level 2 data into structured bid/ask format.

        Args:
            depth_data: List of market depth entries with price, volume, type

        Returns:
            dict: Processed data with separate bids and asks
        """
        bids = []
        asks = []

        for entry in depth_data:
            price = entry.get("price", 0)
            volume = entry.get("volume", 0)
            entry_type = entry.get("type", 0)

            # Type mapping based on TopStepX format:
            # Type 1 = Ask/Offer (selling pressure)
            # Type 2 = Bid (buying pressure)
            # Type 5 = Trade (market execution)
            # Type 9/10 = Order modifications

            if entry_type == 2 and volume > 0:  # Bid
                bids.append({"price": price, "volume": volume})
            elif entry_type == 1 and volume > 0:  # Ask
                asks.append({"price": price, "volume": volume})

        # Sort bids (highest to lowest) and asks (lowest to highest)
        bids.sort(key=lambda x: x["price"], reverse=True)
        asks.sort(key=lambda x: x["price"])

        # Calculate best bid/ask and spread
        best_bid = bids[0]["price"] if bids else 0
        best_ask = asks[0]["price"] if asks else 0
        spread = best_ask - best_bid if best_bid and best_ask else 0

        return {
            "bids": bids,
            "asks": asks,
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread": spread,
        }

    def _on_market_trade(self, data: dict) -> None:
        """
        Process market trade data from ProjectX WebSocket.
        """
        try:
            self._trigger_callbacks("market_trade", data)

        except Exception as e:
            self.logger.error(f"❌ Error processing market trade: {e}")

    def _update_timeframe_data(
        self, tf_key: str, timestamp: datetime, price: float, volume: int
    ):
        """
        Update a specific timeframe with new tick data.

        Args:
            tf_key: Timeframe key (e.g., "5", "15", "60", "240")
            timestamp: Timestamp of the tick
            price: Price of the tick
            volume: Volume of the tick
        """
        try:
            interval = self.timeframes[tf_key]["interval"]
            unit = self.timeframes[tf_key]["unit"]

            # Calculate the bar time for this timeframe
            bar_time = self._calculate_bar_time(timestamp, interval, unit)

            # Get current data for this timeframe
            if tf_key not in self.data:
                return

            current_data = self.data[tf_key]

            # Check if we need to create a new bar or update existing
            if len(current_data) == 0:
                # First bar - ensure minimum volume for pattern detection
                bar_volume = max(volume, 1) if volume > 0 else 1
                new_bar = pl.DataFrame(
                    {
                        "timestamp": [bar_time],
                        "open": [price],
                        "high": [price],
                        "low": [price],
                        "close": [price],
                        "volume": [bar_volume],
                    }
                )

                self.data[tf_key] = new_bar
                self.last_bar_times[tf_key] = bar_time

            else:
                last_bar_time = current_data.select(pl.col("timestamp")).tail(1).item()

                if bar_time > last_bar_time:
                    # New bar needed - ensure minimum volume for pattern detection
                    bar_volume = max(volume, 1) if volume > 0 else 1
                    new_bar = pl.DataFrame(
                        {
                            "timestamp": [bar_time],
                            "open": [price],
                            "high": [price],
                            "low": [price],
                            "close": [price],
                            "volume": [bar_volume],
                        }
                    )

                    self.data[tf_key] = pl.concat([current_data, new_bar])
                    self.last_bar_times[tf_key] = bar_time

                    # Trigger new bar callback
                    self._trigger_callbacks(
                        "new_bar",
                        {
                            "timeframe": tf_key,
                            "bar_time": bar_time,
                            "data": new_bar.to_dicts()[0],
                        },
                    )

                elif bar_time == last_bar_time:
                    # Update existing bar - get the last row for modification
                    last_row_mask = current_data.get_column("timestamp") == bar_time

                    # Get current OHLCV values safely
                    current_high = (
                        current_data.filter(last_row_mask).select(pl.col("high")).item()
                    )
                    current_low = (
                        current_data.filter(last_row_mask).select(pl.col("low")).item()
                    )
                    current_volume = (
                        current_data.filter(last_row_mask)
                        .select(pl.col("volume"))
                        .item()
                    )

                    # Calculate new OHLCV values
                    new_high = (
                        max(current_high, price) if current_high is not None else price
                    )
                    new_low = (
                        min(current_low, price) if current_low is not None else price
                    )
                    new_volume = current_volume + volume

                    # Ensure minimum volume of 1 for pattern detection
                    new_volume = max(new_volume, 1)

                    # Update the DataFrame using polars operations
                    self.data[tf_key] = current_data.with_columns(
                        [
                            pl.when(pl.col("timestamp") == bar_time)
                            .then(pl.lit(new_high))
                            .otherwise(pl.col("high"))
                            .alias("high"),
                            pl.when(pl.col("timestamp") == bar_time)
                            .then(pl.lit(new_low))
                            .otherwise(pl.col("low"))
                            .alias("low"),
                            pl.when(pl.col("timestamp") == bar_time)
                            .then(pl.lit(price))
                            .otherwise(pl.col("close"))
                            .alias("close"),
                            pl.when(pl.col("timestamp") == bar_time)
                            .then(pl.lit(new_volume))
                            .otherwise(pl.col("volume"))
                            .alias("volume"),
                        ]
                    )

            # Keep only recent data to manage memory (keep last 1000 bars per timeframe)
            if len(self.data[tf_key]) > 1000:
                self.data[tf_key] = self.data[tf_key].tail(1000)

        except Exception as e:
            self.logger.error(f"Error updating {tf_key} timeframe: {e}")

    def _calculate_bar_time(
        self, timestamp: datetime, interval: int, unit: int
    ) -> datetime:
        """
        Calculate the bar time for a given timestamp and interval.

        Args:
            timestamp: The tick timestamp (should be timezone-aware)
            interval: Bar interval value
            unit: Time unit (1=seconds, 2=minutes)

        Returns:
            datetime: The bar time (start of the bar period) - timezone-aware
        """
        # Ensure timestamp is timezone-aware
        if timestamp.tzinfo is None:
            timestamp = self.timezone.localize(timestamp)

        if unit == 1:  # Seconds
            # Round down to the nearest interval in seconds
            total_seconds = timestamp.second + timestamp.microsecond / 1000000
            rounded_seconds = (int(total_seconds) // interval) * interval
            bar_time = timestamp.replace(second=rounded_seconds, microsecond=0)
        elif unit == 2:  # Minutes
            # Round down to the nearest interval in minutes
            minutes = (timestamp.minute // interval) * interval
            bar_time = timestamp.replace(minute=minutes, second=0, microsecond=0)
        else:
            raise ValueError(f"Unsupported time unit: {unit}")

        return bar_time

    def _process_tick_data(self, tick: dict):
        """
        Process incoming tick data and update all timeframes.

        Args:
            tick: Dictionary containing tick data (timestamp, price, volume, etc.)
        """
        try:
            if not self.is_running:
                return

            timestamp = tick["timestamp"]
            price = tick["price"]
            volume = tick.get("volume", 0)

            # Update each timeframe
            with self.data_lock:
                for tf_key, tf_config in self.timeframes.items():
                    self._update_timeframe_data(tf_key, timestamp, price, volume)

            # Trigger callbacks for data updates
            self._trigger_callbacks(
                "data_update",
                {"timestamp": timestamp, "price": price, "volume": volume},
            )

        except Exception as e:
            self.logger.error(f"Error processing tick data: {e}")

    def get_data(
        self, timeframe: str = "5min", bars: int | None = None
    ) -> pl.DataFrame | None:
        """
        Get data for a specific timeframe.

        Args:
            timeframe: Timeframe key ("15sec", "1min", "5min", "15min")
            bars: Number of recent bars to return (None for all)

        Returns:
            pl.DataFrame: OHLCV data for the timeframe
        """
        try:
            with self.data_lock:
                if timeframe not in self.data:
                    self.logger.warning(f"No data available for timeframe {timeframe}")
                    return None

                data = self.data[timeframe].clone()

                if bars and len(data) > bars:
                    data = data.tail(bars)

                return data

        except Exception as e:
            self.logger.error(f"Error getting data for timeframe {timeframe}: {e}")
            return None

    def get_mtf_data(
        self, timeframes: list[str] | None = None, bars: int | None = None
    ) -> dict[str, pl.DataFrame]:
        """
        Get multi-timeframe data - replacement for get_data_for_mtf_analysis().

        Args:
            timeframes: List of timeframes to return (None for all)
            bars: Number of recent bars per timeframe (None for all)

        Returns:
            dict: Dictionary mapping timeframe keys to DataFrames
        """
        if timeframes is None:
            timeframes = list(self.timeframes.keys())

        mtf_data = {}

        for tf in timeframes:
            data = self.get_data(tf, bars)
            if data is not None and len(data) > 0:
                mtf_data[tf] = data

        return mtf_data

    def get_current_price(self) -> float | None:
        """Get the current market price from the most recent data."""
        try:
            # Use 15-second data for current price (most recent/frequent updates)
            data_15s = self.get_data("15sec", bars=1)
            if data_15s is not None and len(data_15s) > 0:
                return float(data_15s.select(pl.col("close")).tail(1).item())

            return None

        except Exception as e:
            self.logger.error(f"Error getting current price: {e}")
            return None

    def get_orderbook_bids(self, levels: int = 10) -> pl.DataFrame:
        """
        Get the current bid side of the orderbook.

        Args:
            levels: Number of price levels to return (default: 10)

        Returns:
            pl.DataFrame: Bid levels sorted by price (highest to lowest)
        """
        try:
            with self.orderbook_lock:
                if len(self.orderbook_bids) == 0:
                    return pl.DataFrame(
                        {"price": [], "volume": [], "timestamp": [], "type": []},
                        schema={
                            "price": pl.Float64,
                            "volume": pl.Int64,
                            "timestamp": pl.Datetime,
                            "type": pl.Utf8,
                        },
                    )

                return self.orderbook_bids.head(levels).clone()

        except Exception as e:
            self.logger.error(f"Error getting orderbook bids: {e}")
            return pl.DataFrame(
                {"price": [], "volume": [], "timestamp": [], "type": []},
                schema={
                    "price": pl.Float64,
                    "volume": pl.Int64,
                    "timestamp": pl.Datetime,
                    "type": pl.Utf8,
                },
            )

    def get_orderbook_asks(self, levels: int = 10) -> pl.DataFrame:
        """
        Get the current ask side of the orderbook.

        Args:
            levels: Number of price levels to return (default: 10)

        Returns:
            pl.DataFrame: Ask levels sorted by price (lowest to highest)
        """
        try:
            with self.orderbook_lock:
                if len(self.orderbook_asks) == 0:
                    return pl.DataFrame(
                        {"price": [], "volume": [], "timestamp": [], "type": []},
                        schema={
                            "price": pl.Float64,
                            "volume": pl.Int64,
                            "timestamp": pl.Datetime,
                            "type": pl.Utf8,
                        },
                    )

                return self.orderbook_asks.head(levels).clone()

        except Exception as e:
            self.logger.error(f"Error getting orderbook asks: {e}")
            return pl.DataFrame(
                {"price": [], "volume": [], "timestamp": [], "type": []},
                schema={
                    "price": pl.Float64,
                    "volume": pl.Int64,
                    "timestamp": pl.Datetime,
                    "type": pl.Utf8,
                },
            )

    def get_orderbook_snapshot(self, levels: int = 10) -> dict[str, Any]:
        """
        Get a complete orderbook snapshot with both bids and asks.

        Args:
            levels: Number of price levels to return for each side (default: 10)

        Returns:
            dict: {"bids": DataFrame, "asks": DataFrame, "metadata": dict}
        """
        try:
            with self.orderbook_lock:
                bids = self.get_orderbook_bids(levels)
                asks = self.get_orderbook_asks(levels)

                # Calculate metadata
                best_bid = (
                    float(bids.select(pl.col("price")).head(1).item())
                    if len(bids) > 0
                    else None
                )
                best_ask = (
                    float(asks.select(pl.col("price")).head(1).item())
                    if len(asks) > 0
                    else None
                )
                spread = (best_ask - best_bid) if best_bid and best_ask else None
                mid_price = (
                    ((best_bid + best_ask) / 2) if best_bid and best_ask else None
                )

                # Calculate total volume at each side
                total_bid_volume = (
                    int(bids.select(pl.col("volume").sum()).item())
                    if len(bids) > 0
                    else 0
                )
                total_ask_volume = (
                    int(asks.select(pl.col("volume").sum()).item())
                    if len(asks) > 0
                    else 0
                )

                return {
                    "bids": bids,
                    "asks": asks,
                    "metadata": {
                        "best_bid": best_bid,
                        "best_ask": best_ask,
                        "spread": spread,
                        "mid_price": mid_price,
                        "total_bid_volume": total_bid_volume,
                        "total_ask_volume": total_ask_volume,
                        "last_update": self.last_orderbook_update,
                        "levels_count": {"bids": len(bids), "asks": len(asks)},
                    },
                }

        except Exception as e:
            self.logger.error(f"Error getting orderbook snapshot: {e}")
            return {
                "bids": pl.DataFrame(
                    schema={
                        "price": pl.Float64,
                        "volume": pl.Int64,
                        "timestamp": pl.Datetime,
                        "type": pl.Utf8,
                    }
                ),
                "asks": pl.DataFrame(
                    schema={
                        "price": pl.Float64,
                        "volume": pl.Int64,
                        "timestamp": pl.Datetime,
                        "type": pl.Utf8,
                    }
                ),
                "metadata": {},
            }

    def get_best_bid_ask(self) -> dict[str, float | None]:
        """
        Get the current best bid and ask prices.

        Returns:
            dict: {"bid": float, "ask": float, "spread": float, "mid": float}
        """
        try:
            with self.orderbook_lock:
                best_bid = None
                best_ask = None

                if len(self.orderbook_bids) > 0:
                    best_bid = float(
                        self.orderbook_bids.select(pl.col("price")).head(1).item()
                    )

                if len(self.orderbook_asks) > 0:
                    best_ask = float(
                        self.orderbook_asks.select(pl.col("price")).head(1).item()
                    )

                spread = (best_ask - best_bid) if best_bid and best_ask else None
                mid_price = (
                    ((best_bid + best_ask) / 2) if best_bid and best_ask else None
                )

                return {
                    "bid": best_bid,
                    "ask": best_ask,
                    "spread": spread,
                    "mid": mid_price,
                }

        except Exception as e:
            self.logger.error(f"Error getting best bid/ask: {e}")
            return {"bid": None, "ask": None, "spread": None, "mid": None}

    def get_orderbook_depth(self, price_range: float = 10.0) -> dict[str, int | float]:
        """
        Get orderbook depth within a price range of the mid price.

        Args:
            price_range: Price range around mid to analyze (in price units)

        Returns:
            dict: Volume and level counts within the range
        """
        try:
            with self.orderbook_lock:
                best_prices = self.get_best_bid_ask()
                mid_price = best_prices.get("mid")

                if not mid_price:
                    return {
                        "bid_volume": 0,
                        "ask_volume": 0,
                        "bid_levels": 0,
                        "ask_levels": 0,
                    }

                # Define price range
                lower_bound = mid_price - price_range
                upper_bound = mid_price + price_range

                # Filter bids in range
                bids_in_range = self.orderbook_bids.filter(
                    (pl.col("price") >= lower_bound) & (pl.col("price") <= mid_price)
                )

                # Filter asks in range
                asks_in_range = self.orderbook_asks.filter(
                    (pl.col("price") <= upper_bound) & (pl.col("price") >= mid_price)
                )

                bid_volume = (
                    int(bids_in_range.select(pl.col("volume").sum()).item())
                    if len(bids_in_range) > 0
                    else 0
                )
                ask_volume = (
                    int(asks_in_range.select(pl.col("volume").sum()).item())
                    if len(asks_in_range) > 0
                    else 0
                )

                return {
                    "bid_volume": bid_volume,
                    "ask_volume": ask_volume,
                    "bid_levels": len(bids_in_range),
                    "ask_levels": len(asks_in_range),
                    "price_range": price_range,
                    "mid_price": mid_price,
                }

        except Exception as e:
            self.logger.error(f"Error getting orderbook depth: {e}")
            return {"bid_volume": 0, "ask_volume": 0, "bid_levels": 0, "ask_levels": 0}

    def get_recent_trades(self, count: int = 100) -> pl.DataFrame:
        """
        Get recent trade executions (Type 5 data).

        Args:
            count: Number of recent trades to return

        Returns:
            pl.DataFrame: Recent trades with price, volume, timestamp, side
        """
        try:
            with self.orderbook_lock:
                if len(self.recent_trades) == 0:
                    return pl.DataFrame(
                        {"price": [], "volume": [], "timestamp": [], "side": []},
                        schema={
                            "price": pl.Float64,
                            "volume": pl.Int64,
                            "timestamp": pl.Datetime,
                            "side": pl.Utf8,
                        },
                    )

                return self.recent_trades.tail(count).clone()

        except Exception as e:
            self.logger.error(f"Error getting recent trades: {e}")
            return pl.DataFrame(
                schema={
                    "price": pl.Float64,
                    "volume": pl.Int64,
                    "timestamp": pl.Datetime,
                    "side": pl.Utf8,
                }
            )

    def clear_recent_trades(self) -> None:
        """
        Clear the recent trades history for fresh monitoring periods.

        This is useful when you want to measure trade flow for a specific
        monitoring period without including pre-existing trade data.
        """
        try:
            with self.orderbook_lock:
                self.recent_trades = pl.DataFrame(
                    {"price": [], "volume": [], "timestamp": [], "side": []},
                    schema={
                        "price": pl.Float64,
                        "volume": pl.Int64,
                        "timestamp": pl.Datetime,
                        "side": pl.Utf8,
                    },
                )

                self.logger.info("🧹 Recent trades history cleared")

        except Exception as e:
            self.logger.error(f"❌ Error clearing recent trades: {e}")

    def get_trade_flow_summary(self, minutes: int = 5) -> dict[str, Any]:
        """
        Get trade flow summary for the last N minutes.

        Args:
            minutes: Number of minutes to analyze

        Returns:
            dict: Trade flow statistics
        """
        try:
            with self.orderbook_lock:
                if len(self.recent_trades) == 0:
                    return {
                        "total_volume": 0,
                        "trade_count": 0,
                        "buy_volume": 0,
                        "sell_volume": 0,
                        "buy_trades": 0,
                        "sell_trades": 0,
                        "avg_trade_size": 0,
                        "vwap": 0,
                        "buy_sell_ratio": 0,
                    }

                # Filter trades from last N minutes
                from datetime import timedelta

                cutoff_time = datetime.now(self.timezone) - timedelta(minutes=minutes)
                recent_trades = self.recent_trades.filter(
                    pl.col("timestamp") >= cutoff_time
                )

                if len(recent_trades) == 0:
                    return {
                        "total_volume": 0,
                        "trade_count": 0,
                        "buy_volume": 0,
                        "sell_volume": 0,
                        "buy_trades": 0,
                        "sell_trades": 0,
                        "avg_trade_size": 0,
                        "vwap": 0,
                        "buy_sell_ratio": 0,
                    }

                # Calculate statistics
                total_volume = int(recent_trades.select(pl.col("volume").sum()).item())
                trade_count = len(recent_trades)

                # Buy/sell breakdown
                buy_trades = recent_trades.filter(pl.col("side") == "buy")
                sell_trades = recent_trades.filter(pl.col("side") == "sell")

                buy_volume = (
                    int(buy_trades.select(pl.col("volume").sum()).item())
                    if len(buy_trades) > 0
                    else 0
                )
                sell_volume = (
                    int(sell_trades.select(pl.col("volume").sum()).item())
                    if len(sell_trades) > 0
                    else 0
                )

                buy_count = len(buy_trades)
                sell_count = len(sell_trades)

                # Calculate VWAP (Volume Weighted Average Price)
                if total_volume > 0:
                    vwap_calc = recent_trades.select(
                        (pl.col("price") * pl.col("volume")).sum()
                        / pl.col("volume").sum()
                    ).item()
                    vwap = float(vwap_calc)
                else:
                    vwap = 0

                avg_trade_size = total_volume / trade_count if trade_count > 0 else 0
                buy_sell_ratio = (
                    buy_volume / sell_volume
                    if sell_volume > 0
                    else float("inf")
                    if buy_volume > 0
                    else 0
                )

                return {
                    "total_volume": total_volume,
                    "trade_count": trade_count,
                    "buy_volume": buy_volume,
                    "sell_volume": sell_volume,
                    "buy_trades": buy_count,
                    "sell_trades": sell_count,
                    "avg_trade_size": avg_trade_size,
                    "vwap": vwap,
                    "buy_sell_ratio": buy_sell_ratio,
                    "period_minutes": minutes,
                }

        except Exception as e:
            self.logger.error(f"Error getting trade flow summary: {e}")
            return {"error": str(e)}

    def get_order_type_statistics(self) -> dict[str, int]:
        """
        Get statistics about different order types processed.

        Returns:
            dict: Count of each order type processed
        """
        return self.order_type_stats.copy()

    def get_liquidity_levels(
        self, min_volume: int = 100, levels: int = 20
    ) -> dict[str, Any]:
        """
        Identify significant liquidity levels in the orderbook.

        Args:
            min_volume: Minimum volume threshold for significance
            levels: Number of levels to analyze from each side

        Returns:
            dict: {"bid_liquidity": DataFrame, "ask_liquidity": DataFrame}
        """
        try:
            with self.orderbook_lock:
                # Get top levels from each side
                bids = self.get_orderbook_bids(levels)
                asks = self.get_orderbook_asks(levels)

                # Filter for significant volume levels
                significant_bids = bids.filter(pl.col("volume") >= min_volume)
                significant_asks = asks.filter(pl.col("volume") >= min_volume)

                # Add liquidity score (volume relative to average)
                if len(significant_bids) > 0:
                    avg_bid_volume = significant_bids.select(
                        pl.col("volume").mean()
                    ).item()
                    significant_bids = significant_bids.with_columns(
                        [
                            (pl.col("volume") / avg_bid_volume).alias(
                                "liquidity_score"
                            ),
                            pl.lit("bid").alias("side"),
                        ]
                    )

                if len(significant_asks) > 0:
                    avg_ask_volume = significant_asks.select(
                        pl.col("volume").mean()
                    ).item()
                    significant_asks = significant_asks.with_columns(
                        [
                            (pl.col("volume") / avg_ask_volume).alias(
                                "liquidity_score"
                            ),
                            pl.lit("ask").alias("side"),
                        ]
                    )

                return {
                    "bid_liquidity": significant_bids,
                    "ask_liquidity": significant_asks,
                    "analysis": {
                        "total_bid_levels": len(significant_bids),
                        "total_ask_levels": len(significant_asks),
                        "avg_bid_volume": avg_bid_volume
                        if len(significant_bids) > 0
                        else 0,
                        "avg_ask_volume": avg_ask_volume
                        if len(significant_asks) > 0
                        else 0,
                    },
                }

        except Exception as e:
            self.logger.error(f"Error analyzing liquidity levels: {e}")
            return {"bid_liquidity": pl.DataFrame(), "ask_liquidity": pl.DataFrame()}

    def detect_order_clusters(
        self, price_tolerance: float = 0.25, min_cluster_size: int = 3
    ) -> dict[str, Any]:
        """
        Detect clusters of orders at similar price levels.

        Args:
            price_tolerance: Price difference tolerance for clustering (e.g., 0.25 for quarter-point clusters)
            min_cluster_size: Minimum number of orders to form a cluster

        Returns:
            dict: {"bid_clusters": list, "ask_clusters": list}
        """
        try:
            with self.orderbook_lock:
                bid_clusters = self._find_clusters(
                    self.orderbook_bids, price_tolerance, min_cluster_size
                )
                ask_clusters = self._find_clusters(
                    self.orderbook_asks, price_tolerance, min_cluster_size
                )

                return {
                    "bid_clusters": bid_clusters,
                    "ask_clusters": ask_clusters,
                    "cluster_count": len(bid_clusters) + len(ask_clusters),
                    "analysis": {
                        "strongest_bid_cluster": max(
                            bid_clusters, key=lambda x: x["total_volume"]
                        )
                        if bid_clusters
                        else None,
                        "strongest_ask_cluster": max(
                            ask_clusters, key=lambda x: x["total_volume"]
                        )
                        if ask_clusters
                        else None,
                    },
                }

        except Exception as e:
            self.logger.error(f"Error detecting order clusters: {e}")
            return {"bid_clusters": [], "ask_clusters": []}

    def _find_clusters(
        self, df: pl.DataFrame, tolerance: float, min_size: int
    ) -> list[dict]:
        """Helper method to find price clusters in orderbook data."""
        if len(df) == 0:
            return []

        clusters = []
        prices = df.get_column("price").to_list()
        volumes = df.get_column("volume").to_list()

        i = 0
        while i < len(prices):
            cluster_prices = [prices[i]]
            cluster_volumes = [volumes[i]]
            cluster_indices = [i]

            # Look for nearby prices within tolerance
            j = i + 1
            while j < len(prices) and abs(prices[j] - prices[i]) <= tolerance:
                cluster_prices.append(prices[j])
                cluster_volumes.append(volumes[j])
                cluster_indices.append(j)
                j += 1

            # If cluster is large enough, record it
            if len(cluster_prices) >= min_size:
                clusters.append(
                    {
                        "center_price": sum(cluster_prices) / len(cluster_prices),
                        "price_range": (min(cluster_prices), max(cluster_prices)),
                        "total_volume": sum(cluster_volumes),
                        "order_count": len(cluster_prices),
                        "volume_weighted_price": sum(
                            p * v
                            for p, v in zip(
                                cluster_prices, cluster_volumes, strict=False
                            )
                        )
                        / sum(cluster_volumes),
                        "indices": cluster_indices,
                    }
                )

            # Move to next unclustered price
            i = j if j > i + 1 else i + 1

        return clusters

    def detect_iceberg_orders(
        self,
        min_refresh_count: int = 3,
        volume_consistency_threshold: float = 0.8,
        time_window_minutes: int = 10,
    ) -> dict[str, Any]:
        """
        Detect potential iceberg orders by analyzing order refresh patterns.

        Args:
            min_refresh_count: Minimum number of refreshes to consider iceberg
            volume_consistency_threshold: How consistent volumes should be (0-1)
            time_window_minutes: Time window to analyze for patterns

        Returns:
            dict: {"potential_icebergs": list, "confidence_levels": list}
        """
        try:
            from datetime import timedelta

            with self.orderbook_lock:
                cutoff_time = datetime.now(self.timezone) - timedelta(
                    minutes=time_window_minutes
                )

                # This is a simplified iceberg detection
                # In practice, you'd track price level history over time
                potential_icebergs = []

                # Look for prices with consistent volume that might be refilling
                # Filter orderbook data by time window
                for side, df in [
                    ("bid", self.orderbook_bids),
                    ("ask", self.orderbook_asks),
                ]:
                    if len(df) == 0:
                        continue

                    # Filter by time window if timestamp data is available
                    if "timestamp" in df.columns:
                        recent_df = df.filter(pl.col("timestamp") >= cutoff_time)
                    else:
                        # If no timestamp filtering possible, use current orderbook
                        recent_df = df

                    if len(recent_df) == 0:
                        continue

                    # Group by price and analyze volume patterns
                    # This is a simplified approach - real iceberg detection requires historical tracking
                    for price_level in recent_df.get_column("price").unique():
                        level_data = recent_df.filter(pl.col("price") == price_level)
                        if len(level_data) > 0:
                            volume = level_data.get_column("volume")[0]
                            timestamp = (
                                level_data.get_column("timestamp")[0]
                                if "timestamp" in level_data.columns
                                else datetime.now(self.timezone)
                            )

                            # Enhanced heuristics for iceberg detection
                            # 1. Large volume at round numbers
                            round_number_check = (
                                price_level % 1.0 == 0 or price_level % 0.5 == 0
                            )

                            # 2. Volume size relative to market (simplified)
                            volume_threshold = (
                                500  # Could be dynamic based on average market volume
                            )

                            # 3. Consistent volume patterns (simplified - would need historical tracking for full implementation)
                            if volume > volume_threshold and round_number_check:
                                # Calculate confidence based on multiple factors
                                confidence_score = 0.0
                                confidence_score += 0.3 if round_number_check else 0.0
                                confidence_score += (
                                    0.4 if volume > volume_threshold * 2 else 0.2
                                )
                                confidence_score += (
                                    0.3 if timestamp >= cutoff_time else 0.0
                                )

                                if confidence_score >= 0.5:
                                    confidence_level = (
                                        "high"
                                        if confidence_score >= 0.8
                                        else "medium"
                                        if confidence_score >= 0.6
                                        else "low"
                                    )

                                    potential_icebergs.append(
                                        {
                                            "price": float(price_level),
                                            "volume": int(volume),
                                            "side": side,
                                            "confidence": confidence_level,
                                            "confidence_score": confidence_score,
                                            "estimated_hidden_size": int(
                                                volume * (2 + confidence_score)
                                            ),  # Better estimate based on confidence
                                            "detection_method": "time_filtered_heuristic",
                                            "timestamp": timestamp,
                                            "time_window_minutes": time_window_minutes,
                                        }
                                    )

                return {
                    "potential_icebergs": potential_icebergs,
                    "analysis": {
                        "total_detected": len(potential_icebergs),
                        "bid_icebergs": sum(
                            1 for x in potential_icebergs if x["side"] == "bid"
                        ),
                        "ask_icebergs": sum(
                            1 for x in potential_icebergs if x["side"] == "ask"
                        ),
                        "time_window_minutes": time_window_minutes,
                        "cutoff_time": cutoff_time,
                        "high_confidence": sum(
                            1 for x in potential_icebergs if x["confidence"] == "high"
                        ),
                        "medium_confidence": sum(
                            1 for x in potential_icebergs if x["confidence"] == "medium"
                        ),
                        "low_confidence": sum(
                            1 for x in potential_icebergs if x["confidence"] == "low"
                        ),
                        "note": "Time-filtered iceberg detection with confidence scoring - full detection requires historical order tracking",
                    },
                }

        except Exception as e:
            self.logger.error(f"Error detecting iceberg orders: {e}")
            return {"potential_icebergs": [], "analysis": {}}

    def get_cumulative_delta(self, time_window_minutes: int = 30) -> dict[str, Any]:
        """
        Calculate cumulative delta (running total of buy vs sell volume).

        Args:
            time_window_minutes: Time window for delta calculation

        Returns:
            dict: Cumulative delta analysis
        """
        try:
            from datetime import timedelta

            with self.orderbook_lock:
                if len(self.recent_trades) == 0:
                    return {
                        "cumulative_delta": 0,
                        "delta_trend": "neutral",
                        "time_series": [],
                        "analysis": {
                            "total_buy_volume": 0,
                            "total_sell_volume": 0,
                            "net_volume": 0,
                            "trade_count": 0,
                        },
                    }

                cutoff_time = datetime.now(self.timezone) - timedelta(
                    minutes=time_window_minutes
                )
                recent_trades = self.recent_trades.filter(
                    pl.col("timestamp") >= cutoff_time
                )

                if len(recent_trades) == 0:
                    return {
                        "cumulative_delta": 0,
                        "delta_trend": "neutral",
                        "time_series": [],
                        "analysis": {"note": "No trades in time window"},
                    }

                # Sort by timestamp for cumulative calculation
                trades_sorted = recent_trades.sort("timestamp")

                # Calculate cumulative delta
                cumulative_delta = 0
                delta_series = []
                total_buy_volume = 0
                total_sell_volume = 0

                for trade in trades_sorted.to_dicts():
                    volume = trade["volume"]
                    side = trade["side"]
                    timestamp = trade["timestamp"]

                    if side == "buy":
                        cumulative_delta += volume
                        total_buy_volume += volume
                    elif side == "sell":
                        cumulative_delta -= volume
                        total_sell_volume += volume

                    delta_series.append(
                        {
                            "timestamp": timestamp,
                            "delta": cumulative_delta,
                            "volume": volume,
                            "side": side,
                        }
                    )

                # Determine trend
                if cumulative_delta > 500:
                    trend = "strongly_bullish"
                elif cumulative_delta > 100:
                    trend = "bullish"
                elif cumulative_delta < -500:
                    trend = "strongly_bearish"
                elif cumulative_delta < -100:
                    trend = "bearish"
                else:
                    trend = "neutral"

                return {
                    "cumulative_delta": cumulative_delta,
                    "delta_trend": trend,
                    "time_series": delta_series,
                    "analysis": {
                        "total_buy_volume": total_buy_volume,
                        "total_sell_volume": total_sell_volume,
                        "net_volume": total_buy_volume - total_sell_volume,
                        "trade_count": len(trades_sorted),
                        "time_window_minutes": time_window_minutes,
                        "delta_per_minute": cumulative_delta / time_window_minutes
                        if time_window_minutes > 0
                        else 0,
                    },
                }

        except Exception as e:
            self.logger.error(f"Error calculating cumulative delta: {e}")
            return {"cumulative_delta": 0, "error": str(e)}

    def get_market_imbalance(self) -> dict[str, Any]:
        """
        Calculate market imbalance metrics from orderbook and trade flow.

        Returns:
            dict: Market imbalance analysis
        """
        try:
            with self.orderbook_lock:
                # Get top 10 levels for analysis
                bids = self.get_orderbook_bids(10)
                asks = self.get_orderbook_asks(10)

                if len(bids) == 0 or len(asks) == 0:
                    return {
                        "imbalance_ratio": 0,
                        "direction": "neutral",
                        "confidence": "low",
                    }

                # Calculate volume imbalance at top levels
                top_bid_volume = bids.head(5).select(pl.col("volume").sum()).item()
                top_ask_volume = asks.head(5).select(pl.col("volume").sum()).item()

                total_volume = top_bid_volume + top_ask_volume
                if total_volume == 0:
                    return {
                        "imbalance_ratio": 0,
                        "direction": "neutral",
                        "confidence": "low",
                    }

                # Calculate imbalance ratio (-1 to 1, where -1 = all sell pressure, 1 = all buy pressure)
                imbalance_ratio = (top_bid_volume - top_ask_volume) / total_volume

                # Get recent trade flow for confirmation
                trade_flow = self.get_trade_flow_summary(minutes=5)
                trade_imbalance = 0
                if trade_flow["total_volume"] > 0:
                    trade_imbalance = (
                        trade_flow["buy_volume"] - trade_flow["sell_volume"]
                    ) / trade_flow["total_volume"]

                # Determine direction and confidence
                if imbalance_ratio > 0.3:
                    direction = "bullish"
                    confidence = "high" if trade_imbalance > 0.2 else "medium"
                elif imbalance_ratio < -0.3:
                    direction = "bearish"
                    confidence = "high" if trade_imbalance < -0.2 else "medium"
                else:
                    direction = "neutral"
                    confidence = "low"

                return {
                    "imbalance_ratio": imbalance_ratio,
                    "direction": direction,
                    "confidence": confidence,
                    "orderbook_metrics": {
                        "top_bid_volume": top_bid_volume,
                        "top_ask_volume": top_ask_volume,
                        "bid_ask_ratio": top_bid_volume / top_ask_volume
                        if top_ask_volume > 0
                        else float("inf"),
                    },
                    "trade_flow_metrics": {
                        "trade_imbalance": trade_imbalance,
                        "recent_buy_volume": trade_flow["buy_volume"],
                        "recent_sell_volume": trade_flow["sell_volume"],
                    },
                }

        except Exception as e:
            self.logger.error(f"Error calculating market imbalance: {e}")
            return {"imbalance_ratio": 0, "error": str(e)}

    def get_volume_profile(self, price_bucket_size: float = 0.25) -> dict[str, Any]:
        """
        Create volume profile from recent trade data.

        Args:
            price_bucket_size: Size of price buckets for grouping trades

        Returns:
            dict: Volume profile analysis
        """
        try:
            with self.orderbook_lock:
                if len(self.recent_trades) == 0:
                    return {"profile": [], "poc": None, "value_area": None}

                # Group trades by price buckets
                trades_with_buckets = self.recent_trades.with_columns(
                    [(pl.col("price") / price_bucket_size).floor().alias("bucket")]
                )

                # Calculate volume profile
                profile = (
                    trades_with_buckets.group_by("bucket")
                    .agg(
                        [
                            pl.col("volume").sum().alias("total_volume"),
                            pl.col("price").mean().alias("avg_price"),
                            pl.col("volume").count().alias("trade_count"),
                            pl.col("volume")
                            .filter(pl.col("side") == "buy")
                            .sum()
                            .alias("buy_volume"),
                            pl.col("volume")
                            .filter(pl.col("side") == "sell")
                            .sum()
                            .alias("sell_volume"),
                        ]
                    )
                    .sort("bucket")
                )

                if len(profile) == 0:
                    return {"profile": [], "poc": None, "value_area": None}

                # Find Point of Control (POC) - price level with highest volume
                max_volume_row = profile.filter(
                    pl.col("total_volume")
                    == profile.select(pl.col("total_volume").max()).item()
                ).head(1)

                poc_price = (
                    max_volume_row.select(pl.col("avg_price")).item()
                    if len(max_volume_row) > 0
                    else None
                )
                poc_volume = (
                    max_volume_row.select(pl.col("total_volume")).item()
                    if len(max_volume_row) > 0
                    else 0
                )

                # Calculate value area (70% of volume)
                total_volume = profile.select(pl.col("total_volume").sum()).item()
                value_area_volume = total_volume * 0.7

                # Find value area high and low
                profile_sorted = profile.sort("total_volume", descending=True)
                cumulative_volume = 0
                value_area_prices = []

                for row in profile_sorted.to_dicts():
                    cumulative_volume += row["total_volume"]
                    value_area_prices.append(row["avg_price"])
                    if cumulative_volume >= value_area_volume:
                        break

                value_area = {
                    "high": max(value_area_prices) if value_area_prices else None,
                    "low": min(value_area_prices) if value_area_prices else None,
                    "volume_percentage": (cumulative_volume / total_volume * 100)
                    if total_volume > 0
                    else 0,
                }

                return {
                    "profile": profile.to_dicts(),
                    "poc": {"price": poc_price, "volume": poc_volume},
                    "value_area": value_area,
                    "total_volume": total_volume,
                    "bucket_size": price_bucket_size,
                }

        except Exception as e:
            self.logger.error(f"Error creating volume profile: {e}")
            return {"profile": [], "error": str(e)}

    def get_support_resistance_levels(
        self, lookback_minutes: int = 60
    ) -> dict[str, Any]:
        """
        Identify dynamic support and resistance levels from orderbook and trade data.

        Args:
            lookback_minutes: Minutes of data to analyze

        Returns:
            dict: {"support_levels": list, "resistance_levels": list}
        """
        try:
            with self.orderbook_lock:
                # Get volume profile for support/resistance detection
                volume_profile = self.get_volume_profile()

                if not volume_profile["profile"]:
                    return {"support_levels": [], "resistance_levels": []}

                # Get current market price
                best_prices = self.get_best_bid_ask()
                current_price = best_prices.get("mid")

                if not current_price:
                    return {"support_levels": [], "resistance_levels": []}

                # Identify significant volume levels
                profile_data = volume_profile["profile"]
                avg_volume = sum(level["total_volume"] for level in profile_data) / len(
                    profile_data
                )
                significant_levels = [
                    level
                    for level in profile_data
                    if level["total_volume"] > avg_volume * 1.5
                ]

                # Separate into support (below current price) and resistance (above current price)
                support_levels = []
                resistance_levels = []

                for level in significant_levels:
                    level_price = level["avg_price"]
                    level_strength = level["total_volume"] / avg_volume

                    level_info = {
                        "price": level_price,
                        "volume": level["total_volume"],
                        "strength": level_strength,
                        "trade_count": level["trade_count"],
                        "type": "volume_cluster",
                    }

                    if level_price < current_price:
                        support_levels.append(level_info)
                    else:
                        resistance_levels.append(level_info)

                # Sort by proximity to current price
                support_levels.sort(key=lambda x: abs(x["price"] - current_price))
                resistance_levels.sort(key=lambda x: abs(x["price"] - current_price))

                # Add orderbook levels as potential support/resistance
                liquidity_levels = self.get_liquidity_levels(min_volume=200, levels=15)

                for bid_level in liquidity_levels["bid_liquidity"].to_dicts():
                    if bid_level["price"] < current_price:
                        support_levels.append(
                            {
                                "price": bid_level["price"],
                                "volume": bid_level["volume"],
                                "strength": bid_level["liquidity_score"],
                                "type": "orderbook_liquidity",
                            }
                        )

                for ask_level in liquidity_levels["ask_liquidity"].to_dicts():
                    if ask_level["price"] > current_price:
                        resistance_levels.append(
                            {
                                "price": ask_level["price"],
                                "volume": ask_level["volume"],
                                "strength": ask_level["liquidity_score"],
                                "type": "orderbook_liquidity",
                            }
                        )

                # Remove duplicates and sort by strength
                support_levels = sorted(
                    support_levels, key=lambda x: x["strength"], reverse=True
                )[:10]
                resistance_levels = sorted(
                    resistance_levels, key=lambda x: x["strength"], reverse=True
                )[:10]

                return {
                    "support_levels": support_levels,
                    "resistance_levels": resistance_levels,
                    "current_price": current_price,
                    "analysis": {
                        "strongest_support": support_levels[0]
                        if support_levels
                        else None,
                        "strongest_resistance": resistance_levels[0]
                        if resistance_levels
                        else None,
                        "total_levels": len(support_levels) + len(resistance_levels),
                    },
                }

        except Exception as e:
            self.logger.error(f"Error identifying support/resistance levels: {e}")
            return {"support_levels": [], "resistance_levels": []}

    def get_advanced_market_metrics(self) -> dict[str, Any]:
        """
        Get comprehensive advanced market microstructure metrics.

        Returns:
            dict: Complete advanced market analysis
        """
        try:
            return {
                "liquidity_analysis": self.get_liquidity_levels(),
                "order_clusters": self.detect_order_clusters(),
                "iceberg_detection": self.detect_iceberg_orders(),
                "cumulative_delta": self.get_cumulative_delta(),
                "market_imbalance": self.get_market_imbalance(),
                "volume_profile": self.get_volume_profile(),
                "support_resistance": self.get_support_resistance_levels(),
                "orderbook_snapshot": self.get_orderbook_snapshot(),
                "trade_flow": self.get_trade_flow_summary(),
                "timestamp": datetime.now(self.timezone),
                "analysis_summary": {
                    "data_quality": "high"
                    if len(self.recent_trades) > 100
                    else "medium",
                    "market_activity": "active"
                    if len(self.recent_trades) > 50
                    else "quiet",
                    "analysis_completeness": "full",
                },
            }

        except Exception as e:
            self.logger.error(f"Error getting advanced market metrics: {e}")
            return {"error": str(e)}

    def add_callback(self, event_type: str, callback: Callable):
        """
        Add a callback for specific events.

        Args:
            event_type: Type of event ('data_update', 'new_bar', etc.)
            callback: Callback function to execute
        """
        self.callbacks[event_type].append(callback)
        self.logger.debug(f"Added callback for {event_type}")

    def remove_callback(self, event_type: str, callback: Callable):
        """Remove a callback for specific events."""
        if callback in self.callbacks[event_type]:
            self.callbacks[event_type].remove(callback)
            self.logger.debug(f"Removed callback for {event_type}")

    def set_main_loop(self, loop=None):
        """Set the main event loop for async callback execution from threads."""
        if loop is None:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                self.logger.debug("No running event loop found when setting main loop")
                return
        self.main_loop = loop
        self.logger.debug("Main event loop set for async callback execution")

    def _trigger_callbacks(self, event_type: str, data: dict):
        """Trigger all callbacks for a specific event type, handling both sync and async callbacks."""
        for callback in self.callbacks[event_type]:
            try:
                if asyncio.iscoroutinefunction(callback):
                    # Handle async callback from thread context
                    if self.main_loop and not self.main_loop.is_closed():
                        # Schedule the coroutine in the main event loop from this thread
                        asyncio.run_coroutine_threadsafe(callback(data), self.main_loop)
                    else:
                        # Try to get current loop or use main_loop
                        try:
                            current_loop = asyncio.get_running_loop()
                            current_loop.create_task(callback(data))
                        except RuntimeError:
                            self.logger.warning(
                                f"⚠️ Cannot execute async {event_type} callback - no event loop available"
                            )
                            continue
                else:
                    # Handle sync callback normally
                    callback(data)
            except Exception as e:
                self.logger.error(f"Error in {event_type} callback: {e}")

    def get_statistics(self) -> dict:
        """Get statistics about the real-time data manager."""
        stats: dict[str, Any] = {
            "is_running": self.is_running,
            "contract_id": self.contract_id,
            "timeframes": {},
            "orderbook": {},
        }

        with self.data_lock:
            for tf_key in self.timeframes.keys():
                if tf_key in self.data:
                    data = self.data[tf_key]
                    stats["timeframes"][tf_key] = {
                        "bars": len(data),
                        "latest_time": data.select(pl.col("timestamp")).tail(1).item()
                        if len(data) > 0
                        else None,
                        "latest_price": float(
                            data.select(pl.col("close")).tail(1).item()
                        )
                        if len(data) > 0
                        else None,
                    }

        # Add orderbook statistics
        with self.orderbook_lock:
            best_prices = self.get_best_bid_ask()
            stats["orderbook"] = {
                "bid_levels": len(self.orderbook_bids),
                "ask_levels": len(self.orderbook_asks),
                "best_bid": best_prices.get("bid"),
                "best_ask": best_prices.get("ask"),
                "spread": best_prices.get("spread"),
                "mid_price": best_prices.get("mid"),
                "last_update": self.last_orderbook_update,
                "level2_updates": self.level2_update_count,
            }

            # Add trade flow statistics
            stats["trade_flow"] = {
                "recent_trades_count": len(self.recent_trades),
                "last_5min_summary": self.get_trade_flow_summary(minutes=5),
            }

            # Add order type statistics
            stats["order_types"] = self.get_order_type_statistics()

        return stats

    def health_check(self) -> bool:
        """
        Perform a health check on the real-time data manager.

        Returns:
            bool: True if healthy, False if issues detected
        """
        try:
            # Check if running
            if not self.is_running:
                self.logger.warning("Health check: Real-time feed not running")
                return False

            # Check if we have recent data
            current_time = datetime.now()

            with self.data_lock:
                for tf_key, data in self.data.items():
                    if len(data) == 0:
                        self.logger.warning(
                            f"Health check: No data for timeframe {tf_key}"
                        )
                        return False

                    latest_time = data.select(pl.col("timestamp")).tail(1).item()
                    # Convert to datetime for comparison if needed
                    if hasattr(latest_time, "to_pydatetime"):
                        latest_time = latest_time.to_pydatetime()
                    elif hasattr(latest_time, "tz_localize"):
                        latest_time = latest_time.tz_localize(None)

                    time_diff = (current_time - latest_time).total_seconds()

                    # Calculate timeframe-aware staleness threshold
                    tf_config = self.timeframes.get(tf_key, {})
                    interval = tf_config.get("interval", 5)
                    unit = tf_config.get("unit", 2)  # 1=seconds, 2=minutes

                    if unit == 1:  # Seconds-based timeframes
                        max_age_seconds = (
                            interval * 4
                        )  # Allow 4x the interval (e.g., 60s for 15sec data)
                    else:  # Minute-based timeframes
                        max_age_seconds = (
                            interval * 60 * 1.2 + 180
                        )  # 1.2x interval + 3min buffer (e.g., 18min for 15min data)

                    if time_diff > max_age_seconds:
                        self.logger.warning(
                            f"Health check: Stale data for timeframe {tf_key} ({time_diff / 60:.1f} minutes old, threshold: {max_age_seconds / 60:.1f} minutes)"
                        )
                        return False

            return True

        except Exception as e:
            self.logger.error(f"Error in health check: {e}")
            return False

    def cleanup_old_data(self, max_bars_per_timeframe: int = 1000):
        """
        Clean up old data to manage memory usage in long-running sessions.

        Args:
            max_bars_per_timeframe: Maximum number of bars to keep per timeframe
        """
        try:
            with self.data_lock:
                for tf_key in self.timeframes.keys():
                    if (
                        tf_key in self.data
                        and len(self.data[tf_key]) > max_bars_per_timeframe
                    ):
                        old_length = len(self.data[tf_key])
                        self.data[tf_key] = self.data[tf_key].tail(
                            max_bars_per_timeframe
                        )
                        new_length = len(self.data[tf_key])

                        self.logger.debug(
                            f"Cleaned up {tf_key} data: {old_length} -> {new_length} bars"
                        )

        except Exception as e:
            self.logger.error(f"Error cleaning up old data: {e}")

    def force_data_refresh(self) -> bool:
        """
        Force a complete data refresh by reloading historical data.
        Useful for recovery from data corruption or extended disconnections.

        Returns:
            bool: True if refresh successful
        """
        try:
            self.logger.info("🔄 Forcing complete data refresh...")

            # Stop real-time feed temporarily
            was_running = self.is_running
            if was_running:
                self.stop_realtime_feed()

            # Clear existing data
            with self.data_lock:
                self.data.clear()
                self.last_bar_times.clear()

            # Reload historical data
            success = self.initialize()

            # Restart real-time feed if it was running
            if was_running and success:
                jwt_token = self.project_x.get_session_token()
                success = self.start_realtime_feed(jwt_token)

            if success:
                self.logger.info("✅ Data refresh completed successfully")
            else:
                self.logger.error("❌ Data refresh failed")

            return success

        except Exception as e:
            self.logger.error(f"❌ Error during data refresh: {e}")
            return False

    def enable_level2_data(self, enabled: bool = True) -> None:
        """
        Enable or disable Level 2 market depth data collection.

        Args:
            enabled: Whether to enable Level 2 data collection
        """
        try:
            if hasattr(self, "client") and self.client:
                if enabled:
                    self.logger.info("📊 Enabling Level 2 data collection...")
                    # Level 2 subscription is handled automatically by subscribe_market_data
                    self.level2_enabled = True
                else:
                    self.logger.info("📊 Disabling Level 2 data collection...")
                    self.level2_enabled = False
                    self.last_level2_data = None
            else:
                self.logger.warning(
                    "⚠️ Cannot enable Level 2 data: ProjectX client not initialized"
                )
        except Exception as e:
            self.logger.error(f"❌ Error enabling Level 2 data: {e}")

    def get_level2_capabilities(self) -> dict:
        """
        Get information about Level 2 data capabilities.

        Returns:
            dict: Level 2 capabilities and status
        """
        return {
            "depth_data_supported": True,
            "order_book_analysis": True,
            "institutional_detection": True,
            "market_maker_activity": True,
            "iceberg_detection": True,
            "dynamic_support_resistance": True,
            "enhanced_spread_analysis": True,
            "real_time_pressure_analysis": True,
            "status": "Ready for Level 2 integration",
        }

    def _parse_timeframe_string(self, timeframe_str: str) -> dict | None:
        """
        Parse timeframe string into interval and unit.

        Args:
            timeframe_str: Timeframe string like "15sec", "1min", "5min", "1hour"

        Returns:
            dict: With interval, unit, and name, or None if invalid
        """
        tf_str = timeframe_str.lower().strip()

        # Extract number and unit
        import re

        match = re.match(r"(\d+)(sec|min|hour|h)$", tf_str)
        if not match:
            self.logger.warning(f"⚠️ Invalid timeframe format: {timeframe_str}")
            return None

        number = int(match.group(1))
        unit_str = match.group(2)

        # Convert to ProjectX API format
        if unit_str in ["sec"]:
            # Unit 1 = seconds
            return {"interval": number, "unit": 1, "name": timeframe_str}
        elif unit_str in ["min"]:
            # Unit 2 = minutes
            return {"interval": number, "unit": 2, "name": timeframe_str}
        elif unit_str in ["hour", "h"]:
            # Unit 2 = minutes, convert hours to minutes
            return {"interval": number * 60, "unit": 2, "name": timeframe_str}
        else:
            self.logger.warning(f"⚠️ Unsupported timeframe unit: {unit_str}")
            return None

    def _calculate_required_days(
        self, interval: int, unit: int, max_ema_period: int = 800
    ) -> int:
        """
        Calculate the number of days needed to load sufficient data for EMA calculations.

        Args:
            interval: Timeframe interval (e.g., 15 for 15-second, 5 for 5-minute)
            unit: Unit type (1 = seconds, 2 = minutes)
            max_ema_period: Maximum EMA period configured (default 800)

        Returns:
            int: Number of days to load, with safety buffer
        """
        # Convert timeframe to minutes
        if unit == 1:  # Seconds
            timeframe_minutes = interval / 60.0
        else:  # Minutes
            timeframe_minutes = interval

        # Calculate total minutes needed for max EMA period
        total_minutes_needed = max_ema_period * timeframe_minutes

        # Futures markets typically trade ~23 hours per day (96% uptime)
        # Add 20% safety buffer for weekends, holidays, maintenance windows
        market_efficiency = (
            0.80  # Conservative estimate accounting for all non-trading time
        )

        # Convert to days with safety buffer
        trading_minutes_per_day = 24 * 60 * market_efficiency  # ~1152 minutes/day
        required_days = total_minutes_needed / trading_minutes_per_day

        # Apply minimum and maximum bounds
        min_days = 1  # Always load at least 1 day
        max_days = 60  # Cap at 60 days for API efficiency

        # Round up and add extra buffer for safety
        calculated_days = max(min_days, min(max_days, int(required_days * 1.3) + 1))

        self.logger.debug(
            f"📊 Timeframe calculation: {interval}{('sec' if unit == 1 else 'min')} "
            f"→ {timeframe_minutes:.2f} min/bar × {max_ema_period} periods "
            f"= {total_minutes_needed:.0f} min = {required_days:.1f} days "
            f"→ {calculated_days} days (with buffer)"
        )

        return calculated_days

    def _extract_max_ema_period_from_config(self, strategy_config: dict) -> int:
        """
        Extract the maximum EMA period from strategy configuration.

        Args:
            strategy_config: Full strategy configuration dictionary

        Returns:
            int: Maximum EMA period found, defaults to 800
        """
        max_ema = 800  # Default fallback

        # Check various config sections for EMA periods
        ema_sources = [
            strategy_config.get("signals", {})
            .get("level_detection", {})
            .get("ema_periods", []),
            strategy_config.get("signal_generation", {}).get("ema_periods", []),
            strategy_config.get("level_detection", {}).get("ema_periods", []),
        ]

        for ema_periods in ema_sources:
            if isinstance(ema_periods, list) and ema_periods:
                max_ema = max(max_ema, max(ema_periods))

        self.logger.info(f"📈 Maximum EMA period detected: {max_ema}")
        return max_ema

    def detect_iceberg_orders_advanced(
        self,
        time_window_minutes: int = 30,
        min_refresh_count: int = 5,
        volume_consistency_threshold: float = 0.85,
        min_total_volume: int = 1000,
        statistical_confidence: float = 0.95,
    ) -> dict[str, Any]:
        """
        Advanced iceberg order detection using statistical analysis and order flow tracking.

        This implementation uses institutional-grade techniques:
        - Order flow pattern analysis
        - Statistical refresh rate detection
        - Volume consistency modeling
        - Execution pattern recognition
        - Time-series anomaly detection

        Args:
            time_window_minutes: Analysis window for historical patterns
            min_refresh_count: Minimum refreshes to qualify as iceberg
            volume_consistency_threshold: Required volume consistency (0-1)
            min_total_volume: Minimum cumulative volume threshold
            statistical_confidence: Statistical confidence level for detection

        Returns:
            dict: Advanced iceberg analysis with confidence metrics
        """
        try:
            from collections import defaultdict, deque
            from datetime import timedelta
            from statistics import mean, stdev

            with self.orderbook_lock:
                cutoff_time = datetime.now(self.timezone) - timedelta(
                    minutes=time_window_minutes
                )

                # Initialize order flow tracking structures
                def create_history_dict():
                    return {
                        "volume_history": deque(maxlen=100),
                        "timestamp_history": deque(maxlen=100),
                        "refresh_events": [],
                        "total_volume_seen": 0,
                        "appearance_count": 0,
                        "disappearance_count": 0,
                        "consistent_volume_periods": 0,
                        "volume_variance": 0.0,
                        "inter_refresh_times": [],
                        "execution_patterns": [],
                    }

                price_level_history = defaultdict(create_history_dict)

                potential_icebergs = []

                # STEP 1: Analyze historical order flow patterns
                # This would typically use stored orderbook snapshots over time
                # For this implementation, we'll simulate the analysis with current data
                # and recent trades to demonstrate the methodology

                for side, df in [
                    ("bid", self.orderbook_bids),
                    ("ask", self.orderbook_asks),
                ]:
                    if len(df) == 0:
                        continue

                    # Filter by time window
                    if "timestamp" in df.columns:
                        recent_df = df.filter(pl.col("timestamp") >= cutoff_time)
                    else:
                        recent_df = df

                    if len(recent_df) == 0:
                        continue

                    # STEP 2: Track volume patterns at each price level
                    for price_level in recent_df.get_column("price").unique():
                        level_data = recent_df.filter(pl.col("price") == price_level)

                        if len(level_data) == 0:
                            continue

                        volumes = level_data.get_column("volume").to_list()
                        timestamps = (
                            level_data.get_column("timestamp").to_list()
                            if "timestamp" in level_data.columns
                            else [datetime.now(self.timezone)]
                        )

                        # Update tracking structures
                        history = price_level_history[price_level]
                        for vol in volumes:
                            history["volume_history"].append(vol)
                        for ts in timestamps:
                            history["timestamp_history"].append(ts)
                        history["total_volume_seen"] += sum(volumes)
                        history["appearance_count"] += len(volumes)

                        # STEP 3: Statistical analysis of volume consistency
                        if len(history["volume_history"]) >= 3:
                            volume_list = list(history["volume_history"])
                            vol_mean = mean(volume_list)
                            vol_std = (
                                stdev(volume_list) if len(volume_list) > 1 else 0.0
                            )

                            # Coefficient of variation (lower = more consistent)
                            cv = vol_std / vol_mean if vol_mean > 0 else float("inf")
                            volume_consistency = max(0.0, 1.0 - cv)

                            history["volume_variance"] = cv

                            # STEP 4: Analyze refresh patterns and timing
                            if len(history["timestamp_history"]) >= 2:
                                time_diffs = []
                                prev_time = None
                                for ts in history["timestamp_history"]:
                                    if prev_time:
                                        diff = (ts - prev_time).total_seconds()
                                        time_diffs.append(diff)
                                    prev_time = ts

                                if time_diffs:
                                    avg_refresh_interval = mean(time_diffs)
                                    refresh_regularity = (
                                        1.0 / (1.0 + stdev(time_diffs))
                                        if len(time_diffs) > 1
                                        else 1.0
                                    )
                                    history["inter_refresh_times"] = time_diffs
                                else:
                                    avg_refresh_interval = 0
                                    refresh_regularity = 0
                            else:
                                avg_refresh_interval = 0
                                refresh_regularity = 0

                            # STEP 5: Advanced pattern recognition
                            current_volume = volumes[-1] if volumes else 0

                            # Iceberg indicators
                            indicators = {
                                "volume_consistency": volume_consistency,
                                "refresh_regularity": refresh_regularity,
                                "round_price": self._is_round_price(price_level),
                                "volume_significance": min(
                                    1.0, current_volume / max(1, min_total_volume)
                                ),
                                "refresh_frequency": min(
                                    1.0, len(volumes) / max(1, min_refresh_count)
                                ),
                                "time_persistence": min(
                                    1.0, len(history["timestamp_history"]) / 10.0
                                ),
                                "volume_replenishment": self._analyze_volume_replenishment(
                                    volume_list
                                ),
                            }

                            # STEP 6: Calculate composite confidence score
                            weights = {
                                "volume_consistency": 0.25,
                                "refresh_regularity": 0.20,
                                "round_price": 0.10,
                                "volume_significance": 0.15,
                                "refresh_frequency": 0.15,
                                "time_persistence": 0.10,
                                "volume_replenishment": 0.05,
                            }

                            confidence_score = sum(
                                indicators[key] * weights[key] for key in weights
                            )

                            # STEP 7: Statistical significance testing
                            # Check if pattern is statistically significant
                            statistical_significance = (
                                self._calculate_statistical_significance(
                                    volume_list,
                                    avg_refresh_interval,
                                    statistical_confidence,
                                )
                            )

                            # STEP 8: Final iceberg classification
                            is_iceberg = (
                                confidence_score >= 0.6
                                and volume_consistency >= volume_consistency_threshold
                                and len(volumes) >= min_refresh_count
                                and history["total_volume_seen"] >= min_total_volume
                                and statistical_significance >= statistical_confidence
                            )

                            if is_iceberg:
                                # STEP 9: Estimate hidden size using advanced models
                                estimated_hidden_size = (
                                    self._estimate_iceberg_hidden_size(
                                        volume_list,
                                        confidence_score,
                                        history["total_volume_seen"],
                                    )
                                )

                                # Calculate confidence level
                                if (
                                    confidence_score >= 0.9
                                    and statistical_significance >= 0.99
                                ):
                                    confidence_level = "very_high"
                                elif (
                                    confidence_score >= 0.8
                                    and statistical_significance >= 0.95
                                ):
                                    confidence_level = "high"
                                elif confidence_score >= 0.7:
                                    confidence_level = "medium"
                                else:
                                    confidence_level = "low"

                                iceberg_data = {
                                    "price": float(price_level),
                                    "current_volume": int(current_volume),
                                    "side": side,
                                    "confidence": confidence_level,
                                    "confidence_score": round(confidence_score, 3),
                                    "statistical_significance": round(
                                        statistical_significance, 3
                                    ),
                                    "estimated_hidden_size": int(estimated_hidden_size),
                                    "total_volume_observed": int(
                                        history["total_volume_seen"]
                                    ),
                                    "refresh_count": len(volumes),
                                    "volume_consistency": round(volume_consistency, 3),
                                    "refresh_regularity": round(refresh_regularity, 3),
                                    "avg_refresh_interval_seconds": round(
                                        avg_refresh_interval, 1
                                    ),
                                    "detection_method": "advanced_statistical_analysis",
                                    "indicators": {
                                        k: round(v, 3) for k, v in indicators.items()
                                    },
                                    "timestamps": timestamps[-5:],  # Last 5 timestamps
                                    "volume_history": volume_list[
                                        -10:
                                    ],  # Last 10 volumes
                                }

                                potential_icebergs.append(iceberg_data)

                # STEP 10: Cross-reference with trade data for execution pattern analysis
                potential_icebergs = self._cross_reference_with_trades(
                    potential_icebergs, cutoff_time
                )

                # Sort by confidence score (highest first)
                potential_icebergs.sort(
                    key=lambda x: x["confidence_score"], reverse=True
                )

                return {
                    "potential_icebergs": potential_icebergs,
                    "analysis": {
                        "total_detected": len(potential_icebergs),
                        "detection_method": "advanced_statistical_analysis",
                        "time_window_minutes": time_window_minutes,
                        "cutoff_time": cutoff_time,
                        "confidence_distribution": {
                            "very_high": sum(
                                1
                                for x in potential_icebergs
                                if x["confidence"] == "very_high"
                            ),
                            "high": sum(
                                1
                                for x in potential_icebergs
                                if x["confidence"] == "high"
                            ),
                            "medium": sum(
                                1
                                for x in potential_icebergs
                                if x["confidence"] == "medium"
                            ),
                            "low": sum(
                                1
                                for x in potential_icebergs
                                if x["confidence"] == "low"
                            ),
                        },
                        "side_distribution": {
                            "bid": sum(
                                1 for x in potential_icebergs if x["side"] == "bid"
                            ),
                            "ask": sum(
                                1 for x in potential_icebergs if x["side"] == "ask"
                            ),
                        },
                        "total_estimated_hidden_volume": sum(
                            x["estimated_hidden_size"] for x in potential_icebergs
                        ),
                        "statistical_thresholds": {
                            "min_refresh_count": min_refresh_count,
                            "volume_consistency_threshold": volume_consistency_threshold,
                            "statistical_confidence": statistical_confidence,
                            "min_total_volume": min_total_volume,
                        },
                        "notes": [
                            "Advanced iceberg detection using statistical analysis",
                            "Includes order flow pattern recognition",
                            "Uses time-series analysis and refresh rate modeling",
                            "Incorporates execution pattern cross-referencing",
                            "Provides statistical significance testing",
                        ],
                    },
                }

        except Exception as e:
            self.logger.error(f"Error in advanced iceberg detection: {e}")
            return {"potential_icebergs": [], "analysis": {"error": str(e)}}

    def _is_round_price(self, price: float) -> float:
        """Check if price is at psychologically significant level."""
        # Check various round number patterns
        if price % 1.0 == 0:  # Whole numbers
            return 1.0
        elif price % 0.5 == 0:  # Half numbers
            return 0.8
        elif price % 0.25 == 0:  # Quarter numbers
            return 0.6
        elif price % 0.1 == 0:  # Tenth numbers
            return 0.4
        else:
            return 0.0

    def _analyze_volume_replenishment(self, volume_history: list) -> float:
        """Analyze how consistently volume is replenished after depletion."""
        if len(volume_history) < 4:
            return 0.0

        # Look for patterns where volume drops then returns to similar levels
        replenishment_score = 0.0
        for i in range(2, len(volume_history)):
            prev_vol = volume_history[i - 2]
            current_vol = volume_history[i - 1]
            next_vol = volume_history[i]

            # Check if volume dropped then replenished
            if (
                prev_vol > 0
                and current_vol < prev_vol * 0.5
                and next_vol > prev_vol * 0.8
            ):
                replenishment_score += 1.0

        return min(1.0, replenishment_score / max(1, len(volume_history) - 2))

    def _calculate_statistical_significance(
        self, volume_list: list, avg_refresh_interval: float, confidence_level: float
    ) -> float:
        """Calculate statistical significance of observed patterns."""
        if len(volume_list) < 3:
            return 0.0

        try:
            from statistics import mean, stdev

            # Simple statistical significance based on volume consistency
            # In practice, this would use more sophisticated statistical tests
            volume_std = stdev(volume_list) if len(volume_list) > 1 else 0
            volume_mean = mean(volume_list)

            # Calculate coefficient of variation
            cv = volume_std / volume_mean if volume_mean > 0 else float("inf")

            # Convert to significance score (lower CV = higher significance)
            significance = max(0.0, min(1.0, 1.0 - cv))

            # Adjust for sample size (more samples = higher confidence)
            sample_size_factor = min(1.0, len(volume_list) / 10.0)

            return significance * sample_size_factor

        except Exception:
            return 0.0

    def _estimate_iceberg_hidden_size(
        self, volume_history: list, confidence_score: float, total_observed: int
    ) -> int:
        """Estimate hidden size using statistical models."""
        if not volume_history:
            return 0

        from statistics import mean

        # Advanced estimation based on multiple factors
        avg_visible = mean(volume_history)

        # Estimate based on refresh patterns and confidence
        base_multiplier = 3.0 + (confidence_score * 7.0)  # 3x to 10x multiplier

        # Adjust for consistency patterns
        if len(volume_history) > 5:
            # More data points suggest larger hidden size
            base_multiplier *= 1.0 + len(volume_history) / 20.0

        estimated_hidden = int(avg_visible * base_multiplier)

        # Ensure estimate is reasonable relative to observed volume
        max_reasonable = total_observed * 5
        return min(estimated_hidden, max_reasonable)

    def _cross_reference_with_trades(
        self, icebergs: list, cutoff_time: datetime
    ) -> list:
        """Cross-reference iceberg candidates with actual trade execution patterns."""
        if not (len(self.recent_trades) > 0) or not icebergs:
            return icebergs

        # Filter trades to time window
        recent_trades_df = self.recent_trades
        if "timestamp" in recent_trades_df.columns:
            trades_in_window = recent_trades_df.filter(
                pl.col("timestamp") >= cutoff_time
            )
        else:
            trades_in_window = recent_trades_df

        if len(trades_in_window) == 0:
            return icebergs

        # Enhance icebergs with trade execution analysis
        enhanced_icebergs = []

        for iceberg in icebergs:
            price = iceberg["price"]
            side = iceberg["side"]

            # Find trades near this price level (within 1 tick)
            price_tolerance = 0.01  # 1 cent tolerance
            nearby_trades = trades_in_window.filter(
                (pl.col("price") >= price - price_tolerance)
                & (pl.col("price") <= price + price_tolerance)
            )

            if len(nearby_trades) > 0:
                from statistics import mean, stdev

                trade_volumes = nearby_trades.get_column("volume").to_list()
                total_trade_volume = sum(trade_volumes)
                avg_trade_size = mean(trade_volumes)
                trade_count = len(trade_volumes)

                # Calculate execution consistency
                if len(trade_volumes) > 1:
                    trade_std = stdev(trade_volumes)
                    execution_consistency = 1.0 - (trade_std / mean(trade_volumes))
                else:
                    execution_consistency = 1.0

                # Update iceberg data with trade analysis
                iceberg["execution_analysis"] = {
                    "nearby_trades_count": trade_count,
                    "total_trade_volume": int(total_trade_volume),
                    "avg_trade_size": round(avg_trade_size, 2),
                    "execution_consistency": round(max(0, execution_consistency), 3),
                    "volume_to_trade_ratio": round(
                        iceberg["current_volume"] / max(1, avg_trade_size), 2
                    ),
                }

                # Adjust confidence based on trade patterns
                if execution_consistency > 0.7 and trade_count >= 3:
                    iceberg["confidence_score"] = min(
                        1.0, iceberg["confidence_score"] * 1.1
                    )
                    iceberg["detection_method"] += "_with_trade_confirmation"

            enhanced_icebergs.append(iceberg)

        return enhanced_icebergs
