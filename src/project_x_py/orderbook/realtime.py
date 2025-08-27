"""
Async real-time data handling for ProjectX orderbook.

Author: @TexasCoding
Date: 2025-08-02

Overview:
    Manages WebSocket callbacks, real-time Level 2 data processing, and live orderbook
    updates for ProjectX via the Gateway. Handles event registration, contract
    subscription, and async orderbook data updates for trading and analytics.

Key Features:
    - WebSocket-based real-time data ingest and event processing
    - Market depth and quote update callbacks for orderbook
    - Async event/callback registration and contract management
    - Orderbook reset, trade, and depth update logic

Example Usage:
    ```python
    # V3.1: Real-time handler integrated in TradingSuite
    from project_x_py import TradingSuite, EventType

    # V3.1: Create suite with orderbook feature
    suite = await TradingSuite.create("MNQ", features=["orderbook"])


    # V3.1: Real-time connection is automatically established
    # Register handlers via suite's EventBus
    @suite.events.on(EventType.MARKET_DEPTH_UPDATE)
    async def on_depth(event):
        data = event.data
        print(f"Depth: Best bid {data['bids'][0]['price']} @ {data['bids'][0]['size']}")


    # Real-time updates flow automatically through the suite's EventBus

    await suite.disconnect()
    ```

See Also:
    - `orderbook.base.OrderBookBase`
    - `orderbook.analytics.MarketAnalytics`
    - `orderbook.detection.OrderDetection`
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any

import polars as pl

if TYPE_CHECKING:
    from project_x_py.realtime import ProjectXRealtimeClient

import logging

from project_x_py.orderbook.base import OrderBookBase
from project_x_py.types import DomType


class RealtimeHandler:
    """
    Handles real-time data updates for the async orderbook.

    This class manages the integration between the orderbook and ProjectX's real-time
    data feed, processing WebSocket-based market depth and quote updates. It serves as
    the bridge between the raw real-time data from the Gateway and the structured
    orderbook data storage, ensuring that live market updates are properly processed
    and integrated.

    Key responsibilities:
    1. WebSocket callback registration and management for market data events
    2. Processing and filtering of Level 2 market depth updates
    3. Quote update handling for top-of-book price tracking
    4. Contract ID validation and symbol matching
    5. Trade execution detection and orderbook level maintenance
    6. Event triggering for registered orderbook callbacks

    The handler implements sophisticated logic for:
    - Distinguishing between different DomType events (trades, depth updates, resets)
    - Maintaining accurate bid/ask level data through add/remove/update operations
    - Detecting and classifying trade events based on price movement
    - Managing orderbook resets and maintaining data consistency

    Thread safety:
        All data modifications are performed within the orderbook's async lock,
        ensuring thread-safe operation in concurrent environments.

    Connection management:
        The handler tracks connection state and subscription status, allowing for
        proper cleanup and reconnection scenarios.
    """

    def __init__(self, orderbook: OrderBookBase):
        self.orderbook = orderbook
        self.logger = logging.getLogger(__name__)
        self.realtime_client: ProjectXRealtimeClient | None = None

        # Track connection state
        self.is_connected = False
        self.subscribed_contracts: set[str] = set()

    async def initialize(
        self,
        realtime_client: "ProjectXRealtimeClient",
        subscribe_to_depth: bool = True,
        subscribe_to_quotes: bool = True,
    ) -> bool:
        """
        Initialize real-time data feed connection.

        Args:
            realtime_client: real-time client instance
            subscribe_to_depth: Subscribe to market depth updates (kept for compatibility)
            subscribe_to_quotes: Subscribe to quote updates (kept for compatibility)

        Returns:
            bool: True if initialization successful
        """
        # Note: subscribe_to_depth and subscribe_to_quotes are kept for API compatibility
        # The actual subscription happens at the TradingSuite level
        _ = subscribe_to_depth  # Acknowledge parameter
        _ = subscribe_to_quotes  # Acknowledge parameter
        try:
            self.realtime_client = realtime_client

            # Setup callbacks
            await self._setup_realtime_callbacks()

            # Note: Don't subscribe here - the example already subscribes with the proper contract ID
            # The example gets the contract ID and subscribes after initialization

            self.is_connected = True

            self.logger.info(
                f"OrderBook initialized successfully for {self.orderbook.instrument}"
            )
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize OrderBook: {e}")
            return False

    async def _setup_realtime_callbacks(self) -> None:
        """
        Setup callbacks for real-time data processing.

        This method registers the necessary callback functions with the real-time client
        to handle incoming market data events. It establishes the event handlers for:
        - Market depth updates (Level 2 orderbook data)
        - Quote updates (best bid/ask price changes)

        The callbacks are registered asynchronously and will be triggered whenever
        the corresponding market data events are received from the WebSocket feed.

        Note:
            This method should only be called after the realtime_client has been set
            and is ready to accept callback registrations.
        """
        if not self.realtime_client:
            return

        # Market depth callback for Level 2 data
        await self.realtime_client.add_callback(
            "market_depth", self._on_market_depth_update
        )

        # Quote callback for best bid/ask tracking
        await self.realtime_client.add_callback("quote_update", self._on_quote_update)

    async def _on_market_depth_update(self, data: dict[str, Any]) -> None:
        """
        Callback for market depth updates (Level 2 data).

        This method is triggered whenever a market depth update is received from the
        WebSocket feed. It processes Level 2 orderbook data including bid/ask price
        level changes, volume updates, and trade executions.

        The method performs the following operations:
        1. Validates that the update is for the correct contract/instrument
        2. Processes the market depth data through the orderbook
        3. Triggers any registered callbacks with processed update information

        Args:
            data: Market depth update data containing:
                - contract_id: The contract identifier for the update
                - data: List of depth entries with price, volume, and type information

        Note:
            This callback expects data in the ProjectX Gateway format where each
            depth entry contains DomType information for proper processing.
        """
        try:
            self.logger.debug(f"Market depth callback received: {list(data.keys())}")
            # The data comes structured as {"contract_id": ..., "data": ...}
            contract_id = data.get("contract_id", "")
            if isinstance(data.get("data"), list) and len(data.get("data", [])) > 0:
                self.logger.debug(f"First data entry: {data['data'][0]}")
            if not self._is_relevant_contract(contract_id):
                return

            # Process the market depth data
            await self._process_market_depth(data)

            # Trigger any registered callbacks
            await self.orderbook._trigger_callbacks(
                "market_depth_processed",
                {
                    "contract_id": contract_id,
                    "update_count": self.orderbook.level2_update_count,
                    "timestamp": datetime.now(self.orderbook.timezone),
                },
            )

        except Exception as e:
            self.logger.error(f"Error processing market depth update: {e}")

    async def _on_quote_update(self, data: dict[str, Any]) -> None:
        """
        Callback for quote updates.

        This method handles quote update events that provide top-of-book information
        including best bid/ask prices and sizes. Quote updates are typically more
        frequent than full depth updates and provide real-time insight into the
        best available prices.

        Args:
            data: Quote update data containing:
                - contract_id: The contract identifier for the quote
                - data: Quote information with bid, ask, bidSize, askSize fields

        Note:
            Quote updates are processed separately from market depth updates and
            primarily serve to maintain accurate top-of-book information and
            trigger quote-specific callbacks for client applications.
        """
        try:
            # The data comes structured as {"contract_id": ..., "data": ...}
            contract_id = data.get("contract_id", "")
            if not self._is_relevant_contract(contract_id):
                return

            # Extract quote data
            quote_data = data.get("data", {})

            # Trigger quote update callbacks
            # Gateway uses 'bestBid'/'bestAsk' not 'bid'/'ask'
            await self.orderbook._trigger_callbacks(
                "quote_update",
                {
                    "contract_id": contract_id,
                    "bid": quote_data.get("bestBid"),
                    "ask": quote_data.get("bestAsk"),
                    "bid_size": quote_data.get("bidSize"),
                    "ask_size": quote_data.get("askSize"),
                    "timestamp": datetime.now(self.orderbook.timezone),
                },
            )

        except Exception as e:
            self.logger.error(f"Error processing quote update: {e}")

    def _is_relevant_contract(self, contract_id: str) -> bool:
        """
        Check if the contract ID is relevant to this orderbook.

        This method determines whether incoming market data is for the instrument
        that this orderbook is tracking. It handles various contract ID formats
        and performs fuzzy matching to accommodate different naming conventions
        between the orderbook instrument identifier and the full contract IDs
        received from the Gateway.

        The matching logic handles:
        - Exact instrument matches
        - Contract ID prefixes (e.g., "CON.F.US." prefixes)
        - Symbol extraction from full contract identifiers
        - Partial matching for related contracts

        Args:
            contract_id: The contract identifier from the incoming market data

        Returns:
            bool: True if the contract is relevant to this orderbook, False otherwise

        Example:
            >>> handler._is_relevant_contract("CON.F.US.ES.H25")  # ES orderbook
            True
            >>> handler._is_relevant_contract("CON.F.US.NQ.H25")  # ES orderbook
            False
        """
        if contract_id == self.orderbook.instrument:
            return True

        # Handle case where instrument might be a symbol and contract_id is full ID
        clean_contract = contract_id.replace("CON.F.US.", "").split(".")[0]
        clean_instrument = self.orderbook.instrument.replace("CON.F.US.", "").split(
            "."
        )[0]

        is_match = clean_contract == clean_instrument
        if not is_match:
            self.logger.debug(
                f"Contract mismatch: received '{contract_id}' (clean: '{clean_contract}'), "
                f"expected '{self.orderbook.instrument}' (clean: '{clean_instrument}')"
            )
        return is_match

    async def _process_market_depth(self, data: dict[str, Any]) -> None:
        """
        Process market depth update from ProjectX Gateway.

        This method handles the core processing of Level 2 market depth data,
        converting raw Gateway updates into structured orderbook changes. It
        processes each depth entry according to its DomType and updates the
        appropriate orderbook data structures.

        The processing includes:
        1. Extracting and validating market depth entries
        2. Recording pre-update best bid/ask for comparison
        3. Processing each depth entry based on its type (trade, depth update, reset)
        4. Maintaining orderbook consistency and triggering appropriate callbacks

        Args:
            data: Market depth data structure containing:
                - data: List of market depth entries from the Gateway
                Each entry contains price, volume, timestamp, and type information

        Thread Safety:
            This method acquires the orderbook lock and processes all updates
            atomically to ensure data consistency.
        """
        market_data = data.get("data", [])
        if not market_data:
            return

        self.logger.debug(f"Processing market depth data: {len(market_data)} entries")
        if len(market_data) > 0:
            self.logger.debug(f"Sample entry: {market_data[0]}")

        # Update statistics
        self.orderbook.level2_update_count += 1

        # Process each market depth entry
        async with self.orderbook.orderbook_lock:
            current_time = datetime.now(self.orderbook.timezone)

            # Get best prices before processing updates - use unlocked version since we're already in the lock
            pre_update_best = self.orderbook._get_best_bid_ask_unlocked()
            pre_update_bid = pre_update_best.get("bid")
            pre_update_ask = pre_update_best.get("ask")

            for entry in market_data:
                await self._process_single_depth_entry(
                    entry, current_time, pre_update_bid, pre_update_ask
                )

            self.orderbook.last_orderbook_update = current_time
            self.orderbook.last_level2_data = data

            # Update memory stats
            self.orderbook.memory_manager.memory_stats["total_trades"] = (
                self.orderbook.recent_trades.height
            )

    async def _process_single_depth_entry(
        self,
        entry: dict[str, Any],
        current_time: datetime,
        pre_update_bid: float | None,
        pre_update_ask: float | None,
    ) -> None:
        """
        Process a single depth entry from market data.

        This method handles individual market depth entries, routing them to the
        appropriate processing logic based on their DomType. It ensures that each
        type of market event (trades, bid/ask updates, resets) is handled correctly
        and that the orderbook state remains consistent.

        Processing logic by DomType:
        - TRADE: Records trade execution and updates trade history
        - BID/ASK: Updates corresponding side of the orderbook
        - BEST_BID/BEST_ASK: Updates best price levels
        - NEW_BEST_BID/NEW_BEST_ASK: Handles new best price events
        - RESET: Clears and resets the entire orderbook

        Args:
            entry: Single market depth entry containing:
                - type: DomType integer indicating the event type
                - price: Price level for the event
                - volume: Volume associated with the event
            current_time: Timestamp for the update
            pre_update_bid: Best bid price before this update batch
            pre_update_ask: Best ask price before this update batch

        Note:
            This method should only be called from within _process_market_depth
            while the orderbook lock is already held.
        """
        try:
            trade_type = entry.get("type", 0)
            price = float(entry.get("price", 0))
            volume = int(entry.get("volume", 0))

            # Map type and update statistics
            type_name = self.orderbook._map_trade_type(trade_type)
            self.orderbook.order_type_stats[f"type_{trade_type}_count"] += 1

            # Handle different trade types
            if trade_type == DomType.TRADE:
                # Process actual trade execution
                await self._process_trade(
                    price,
                    volume,
                    current_time,
                    pre_update_bid,
                    pre_update_ask,
                    type_name,
                )
            elif trade_type == DomType.BID:
                # Update bid side
                await self._update_orderbook_level(
                    price, volume, current_time, is_bid=True
                )
            elif trade_type == DomType.ASK:
                # Update ask side
                await self._update_orderbook_level(
                    price, volume, current_time, is_bid=False
                )
            elif trade_type in (DomType.BEST_BID, DomType.NEW_BEST_BID):
                # New best bid
                await self._update_orderbook_level(
                    price, volume, current_time, is_bid=True
                )
            elif trade_type in (DomType.BEST_ASK, DomType.NEW_BEST_ASK):
                # New best ask
                await self._update_orderbook_level(
                    price, volume, current_time, is_bid=False
                )
            elif trade_type == DomType.RESET:
                # Reset orderbook
                await self._reset_orderbook()

        except Exception as e:
            self.logger.error(f"Error processing depth entry: {e}")

    async def _process_trade(
        self,
        price: float,
        volume: int,
        timestamp: datetime,
        pre_bid: float | None,
        pre_ask: float | None,
        order_type: str,
    ) -> None:
        """
        Process a trade execution event.

        This method handles actual trade executions (DomType.TRADE), recording the
        trade in the orderbook's trade history and updating related statistics.
        It performs trade side classification based on the trade price relative
        to the best bid/ask prices at the time of execution.

        Trade Classification Logic:
        - Buy trade: Price >= best ask (aggressive buyer)
        - Sell trade: Price <= best bid (aggressive seller)
        - Neutral trade: Price between bid and ask (cannot determine aggressor)

        The method also updates:
        - Recent trades DataFrame with full trade details
        - VWAP calculations (numerator and denominator)
        - Cumulative delta tracking
        - Trade flow statistics by side and aggression level

        Args:
            price: Execution price of the trade
            volume: Number of contracts/shares traded
            timestamp: Time of trade execution
            pre_bid: Best bid price before the trade
            pre_ask: Best ask price before the trade
            order_type: String representation of the order type

        Note:
            This method assumes the orderbook lock is already held by the caller.
        """
        # Determine trade side based on price relative to spread
        side = "unknown"
        if pre_bid is not None and pre_ask is not None:
            _mid_price = (pre_bid + pre_ask) / 2
            if price >= pre_ask:
                side = "buy"
                self.orderbook.trade_flow_stats["aggressive_buy_volume"] += volume
            elif price <= pre_bid:
                side = "sell"
                self.orderbook.trade_flow_stats["aggressive_sell_volume"] += volume
            else:
                # Trade inside spread - likely market maker
                side = "neutral"
                self.orderbook.trade_flow_stats["market_maker_trades"] += 1

        # Calculate spread at trade time
        spread_at_trade = None
        mid_price_at_trade = None
        if pre_bid is not None and pre_ask is not None:
            spread_at_trade = pre_ask - pre_bid
            mid_price_at_trade = (pre_bid + pre_ask) / 2

        # Update cumulative delta
        if side == "buy":
            self.orderbook.cumulative_delta += volume
        elif side == "sell":
            self.orderbook.cumulative_delta -= volume

        # Store delta history
        self.orderbook.delta_history.append(
            {
                "timestamp": timestamp,
                "delta": self.orderbook.cumulative_delta,
                "volume": volume,
                "side": side,
            }
        )

        # Update VWAP
        self.orderbook.vwap_numerator += price * volume
        self.orderbook.vwap_denominator += volume

        # Update memory stats for total volume
        self.orderbook.memory_manager.memory_stats["total_volume"] = (
            self.orderbook.memory_manager.memory_stats.get("total_volume", 0) + volume
        )
        if volume > self.orderbook.memory_manager.memory_stats.get("largest_trade", 0):
            self.orderbook.memory_manager.memory_stats["largest_trade"] = volume

        # Create trade record
        new_trade = pl.DataFrame(
            {
                "price": [price],
                "volume": [volume],
                "timestamp": [timestamp],
                "side": [side],
                "spread_at_trade": [spread_at_trade],
                "mid_price_at_trade": [mid_price_at_trade],
                "best_bid_at_trade": [pre_bid],
                "best_ask_at_trade": [pre_ask],
                "order_type": [order_type],
            }
        )

        # Append to recent trades
        self.orderbook.recent_trades = pl.concat(
            [self.orderbook.recent_trades, new_trade],
            how="vertical",
        )

        # Trigger trade callback
        await self.orderbook._trigger_callbacks(
            "trade_processed",
            {
                "trade_data": {
                    "price": price,
                    "volume": volume,
                    "timestamp": timestamp,
                    "side": side,
                    "order_type": order_type,
                },
                "cumulative_delta": self.orderbook.cumulative_delta,
            },
        )

    async def _update_orderbook_level(
        self, price: float, volume: int, timestamp: datetime, is_bid: bool
    ) -> None:
        """
        Update a single orderbook level.

        This method handles updates to individual price levels in the orderbook,
        including adding new levels, updating existing levels, and removing levels
        when volume reaches zero. It maintains proper orderbook structure and
        updates historical tracking for analytics purposes.

        Operations performed:
        1. Records the update in price level history for pattern detection
        2. Checks if the price level already exists in the orderbook
        3. If volume is 0: Removes the price level completely
        4. If volume > 0 and level exists: Updates volume and timestamp
        5. If volume > 0 and level doesn't exist: Adds new price level
        6. Updates the appropriate DataFrame (bids or asks) with new data

        Args:
            price: Price level to update
            volume: New volume for the price level (0 means remove)
            timestamp: Time of the update
            is_bid: True for bid side updates, False for ask side updates

        Note:
            This method assumes the orderbook lock is already held and modifies
            the orderbook DataFrames in-place.
        """
        side = "bid" if is_bid else "ask"

        # Update price level history for analytics with memory bounds
        history_key = (price, side)

        # Check if we need to enforce memory bounds and key doesn't exist
        if (
            len(self.orderbook.price_level_history)
            >= self.orderbook.max_price_levels_tracked
            and history_key not in self.orderbook.price_level_history
        ):
            # Remove the oldest entry (first in dict)
            oldest_key = next(iter(self.orderbook.price_level_history))
            del self.orderbook.price_level_history[oldest_key]

        self.orderbook.price_level_history[history_key].append(
            {
                "volume": volume,
                "timestamp": timestamp,
                "change_type": "update",
            }
        )

        # Get the current DataFrame reference
        if is_bid:
            orderbook_df = self.orderbook.orderbook_bids
        else:
            orderbook_df = self.orderbook.orderbook_asks

        # Check if price level exists
        existing = orderbook_df.filter(pl.col("price") == price)

        if existing.height > 0:
            if volume == 0:
                # Remove the level
                orderbook_df = orderbook_df.filter(pl.col("price") != price)
            else:
                # Update the level
                orderbook_df = orderbook_df.with_columns(
                    pl.when(pl.col("price") == price)
                    .then(pl.lit(volume))
                    .otherwise(pl.col("volume"))
                    .alias("volume"),
                    pl.when(pl.col("price") == price)
                    .then(pl.lit(timestamp))
                    .otherwise(pl.col("timestamp"))
                    .alias("timestamp"),
                )
        else:
            if volume > 0:
                # Add new level
                new_level = pl.DataFrame(
                    {
                        "price": [price],
                        "volume": [volume],
                        "timestamp": [timestamp],
                    }
                )
                orderbook_df = pl.concat([orderbook_df, new_level], how="vertical")

        # Always update the appropriate DataFrame reference
        if is_bid:
            self.orderbook.orderbook_bids = orderbook_df
        else:
            self.orderbook.orderbook_asks = orderbook_df

    async def _reset_orderbook(self) -> None:
        """
        Reset the orderbook state.

        This method completely clears the orderbook and reinitializes it to an empty
        state. It's typically called when a DomType.RESET event is received, which
        indicates that the market data feed is being reset and all previous orderbook
        data should be discarded.

        The reset operation:
        1. Clears all bid price levels
        2. Clears all ask price levels
        3. Reinitializes DataFrames with proper schema
        4. Triggers reset callbacks for dependent components

        Note:
            This method assumes the orderbook lock is already held and should only
            be called in response to explicit reset events from the data feed.
        """
        self.orderbook.orderbook_bids = pl.DataFrame(
            {"price": [], "volume": [], "timestamp": []},
            schema={
                "price": pl.Float64,
                "volume": pl.Int64,
                "timestamp": pl.Datetime(time_zone=self.orderbook.timezone.zone),
            },
        )
        self.orderbook.orderbook_asks = pl.DataFrame(
            {"price": [], "volume": [], "timestamp": []},
            schema={
                "price": pl.Float64,
                "volume": pl.Int64,
                "timestamp": pl.Datetime(time_zone=self.orderbook.timezone.zone),
            },
        )
        self.logger.info("Orderbook reset due to RESET event")

    async def disconnect(self) -> None:
        """
        Disconnect from real-time data feed.

        This method properly disconnects the orderbook from the real-time data feed,
        cleaning up subscriptions and resetting connection state. It should be called
        when the orderbook is no longer needed or when shutting down the application.

        Disconnect operations:
        1. Unsubscribes from market data for all subscribed contracts
        2. Clears the set of subscribed contracts
        3. Resets connection state flags
        4. Handles any errors during the disconnection process gracefully

        Note:
            This method is safe to call multiple times and will not raise errors
            if already disconnected.
        """
        if self.realtime_client and self.subscribed_contracts:
            try:
                # Unsubscribe from market data
                await self.realtime_client.unsubscribe_market_data(
                    list(self.subscribed_contracts)
                )

                # Remove callbacks
                await self.realtime_client.remove_callback(
                    "market_depth", self._on_market_depth_update
                )
                await self.realtime_client.remove_callback(
                    "quote_update", self._on_quote_update
                )

                self.subscribed_contracts.clear()
                self.is_connected = False

            except Exception as e:
                self.logger.error(f"Error during disconnect: {e}")
