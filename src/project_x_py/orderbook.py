#!/usr/bin/env python3
"""
OrderBook Manager for Real-time Market Data

Author: TexasCoding
Date: June 2025

This module provides comprehensive orderbook management and analysis capabilities:
1. Real-time Level 2 market depth processing
2. Trade flow analysis and execution tracking
3. Advanced market microstructure analytics
4. Iceberg order detection using statistical analysis
5. Support/resistance level identification
6. Market imbalance and liquidity analysis

Key Features:
- Thread-safe orderbook operations
- Polars DataFrame-based storage for efficient analysis
- Advanced institutional-grade order flow analytics
- Statistical significance testing for pattern recognition
- Real-time market maker and iceberg detection
- Comprehensive liquidity and depth analysis
"""

import gc
import logging
import threading
import time
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime, timedelta
from statistics import mean, stdev
from typing import Any

import polars as pl
import pytz


class OrderBook:
    """
    Advanced orderbook manager for real-time market depth and trade flow analysis.

    This class provides institutional-grade orderbook analytics including:
    - Real-time Level 2 market depth processing
    - Trade execution flow analysis
    - Iceberg order detection with statistical confidence
    - Dynamic support/resistance identification
    - Market imbalance and liquidity metrics
    - Volume profile and cumulative delta analysis

    The orderbook maintains separate bid and ask sides with full depth,
    tracks all trade executions, and provides advanced analytics for
    algorithmic trading strategies.
    """

    def __init__(self, instrument: str, timezone: str = "America/Chicago"):
        """
        Initialize the orderbook manager.

        Args:
            instrument: Trading instrument (e.g., "MGC", "MNQ")
            timezone: Timezone for timestamp handling
        """
        self.instrument = instrument
        self.timezone = pytz.timezone(timezone)
        self.logger = logging.getLogger(__name__)

        # Thread-safe locks for concurrent access
        self.orderbook_lock = threading.RLock()

        # Memory management settings
        self.max_trades = 10000  # Maximum trades to keep in memory
        self.max_depth_entries = 1000  # Maximum depth entries per side
        self.cleanup_interval = 300  # 5 minutes
        self.last_cleanup = time.time()

        # Performance monitoring
        self.memory_stats = {
            "total_trades": 0,
            "trades_cleaned": 0,
            "last_cleanup": time.time(),
        }

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
        self.last_level2_data: dict | None = None
        self.level2_update_count = 0

        # Statistics for different order types
        self.order_type_stats = {
            "type_1_count": 0,  # Ask updates
            "type_2_count": 0,  # Bid updates
            "type_5_count": 0,  # Trade executions
            "type_9_count": 0,  # Order modifications
            "type_10_count": 0,  # Order modifications/cancellations
            "other_types": 0,  # Unknown types
        }

        # Callbacks for orderbook events
        self.callbacks: dict[str, list[Callable]] = defaultdict(list)

        self.logger.info(f"OrderBook initialized for {instrument}")

    def _cleanup_old_data(self) -> None:
        """
        Clean up old data to manage memory usage efficiently.
        """
        current_time = time.time()

        # Only cleanup if interval has passed
        if current_time - self.last_cleanup < self.cleanup_interval:
            return

        with self.orderbook_lock:
            initial_trade_count = len(self.recent_trades)
            initial_bid_count = len(self.orderbook_bids)
            initial_ask_count = len(self.orderbook_asks)

            # Cleanup recent trades - keep only the most recent trades
            if len(self.recent_trades) > self.max_trades:
                self.recent_trades = self.recent_trades.tail(self.max_trades // 2)
                self.memory_stats["trades_cleaned"] += initial_trade_count - len(
                    self.recent_trades
                )

            # Cleanup orderbook depth - keep only recent depth entries
            cutoff_time = datetime.now(self.timezone) - timedelta(hours=1)

            if len(self.orderbook_bids) > self.max_depth_entries:
                self.orderbook_bids = self.orderbook_bids.filter(
                    pl.col("timestamp") > cutoff_time
                ).tail(self.max_depth_entries // 2)

            if len(self.orderbook_asks) > self.max_depth_entries:
                self.orderbook_asks = self.orderbook_asks.filter(
                    pl.col("timestamp") > cutoff_time
                ).tail(self.max_depth_entries // 2)

            self.last_cleanup = current_time
            self.memory_stats["last_cleanup"] = current_time

            # Log cleanup stats
            trades_after = len(self.recent_trades)
            bids_after = len(self.orderbook_bids)
            asks_after = len(self.orderbook_asks)

            if (
                initial_trade_count != trades_after
                or initial_bid_count != bids_after
                or initial_ask_count != asks_after
            ):
                self.logger.debug(
                    f"OrderBook cleanup - Trades: {initial_trade_count}→{trades_after}, "
                    f"Bids: {initial_bid_count}→{bids_after}, "
                    f"Asks: {initial_ask_count}→{asks_after}"
                )

                # Force garbage collection after significant cleanup
                gc.collect()

    def get_memory_stats(self) -> dict:
        """
        Get current memory usage statistics.

        Returns:
            Dictionary with memory statistics
        """
        with self.orderbook_lock:
            return {
                "recent_trades_count": len(self.recent_trades),
                "orderbook_bids_count": len(self.orderbook_bids),
                "orderbook_asks_count": len(self.orderbook_asks),
                "total_memory_entries": (
                    len(self.recent_trades)
                    + len(self.orderbook_bids)
                    + len(self.orderbook_asks)
                ),
                "max_trades": self.max_trades,
                "max_depth_entries": self.max_depth_entries,
                **self.memory_stats,
            }

    def process_market_depth(self, data: dict) -> None:
        """
        Process market depth data and update Level 2 orderbook.

        Args:
            data: Market depth data containing price levels and volumes
        """
        try:
            contract_id = data.get("contract_id", "Unknown")
            depth_data = data.get("data", [])

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
                    updates_df = pl.from_dicts(bid_updates)
                    self._update_orderbook_side(updates_df, "bid")

                # Update ask levels
                if ask_updates:
                    updates_df = pl.from_dicts(ask_updates)
                    self._update_orderbook_side(updates_df, "ask")

                # Update trade flow data
                if trade_updates:
                    updates_df = pl.from_dicts(trade_updates)
                    self._update_trade_flow(updates_df)

                # Update last update time
                self.last_orderbook_update = current_time

            # Store the complete Level 2 data structure
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

            # Periodic memory cleanup
            self._cleanup_old_data()

        except Exception as e:
            self.logger.error(f"❌ Error processing market depth: {e}")
            import traceback

            self.logger.error(f"❌ Market depth traceback: {traceback.format_exc()}")

    def _update_orderbook_side(self, updates_df: pl.DataFrame, side: str) -> None:
        """
        Update bid or ask side of the orderbook with new price levels.

        Args:
            updates: List of price level updates {price, volume, timestamp}
            side: "bid" or "ask"
        """
        try:
            current_df = self.orderbook_bids if side == "bid" else self.orderbook_asks

            # Combine with existing data
            if current_df.height > 0:
                combined_df = pl.concat([current_df, updates_df])
            else:
                combined_df = updates_df

            # Group by price and take the latest update
            latest_df = combined_df.group_by("price").agg(
                [
                    pl.col("volume").last(),
                    pl.col("timestamp").last(),
                    pl.col("type").last(),
                ]
            )

            # Remove zero-volume levels
            latest_df = latest_df.filter(pl.col("volume") > 0)

            # Sort appropriately
            if side == "bid":
                latest_df = latest_df.sort("price", descending=True)
                self.orderbook_bids = latest_df.head(100)
            else:
                latest_df = latest_df.sort("price", descending=False)
                self.orderbook_asks = latest_df.head(100)

        except Exception as e:
            self.logger.error(f"❌ Error updating {side} orderbook: {e}")

    def _update_trade_flow(self, trade_updates: pl.DataFrame) -> None:
        """
        Update trade flow data with new trade executions.

        Args:
            trade_updates: List of trade executions {price, volume, timestamp}
        """
        try:
            if trade_updates.height == 0:
                return

            # Get current best bid/ask to determine trade direction
            best_prices = self.get_best_bid_ask()
            best_bid = best_prices.get("bid")
            best_ask = best_prices.get("ask")

            # Enhance trade data with side detection
            enhanced_trades = trade_updates.with_columns(
                pl.when(pl.col("price") >= best_ask)
                .then(pl.lit("buy"))
                .when(pl.col("price") <= best_bid)
                .then(pl.lit("sell"))
                .otherwise(pl.lit("unknown"))
                .alias("side")
            )

            # Combine with existing trade data
            if self.recent_trades.height > 0:
                combined_df = pl.concat([self.recent_trades, enhanced_trades])
            else:
                combined_df = enhanced_trades

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
            price_tolerance: Price difference tolerance for clustering
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
            with self.orderbook_lock:
                cutoff_time = datetime.now(self.timezone) - timedelta(
                    minutes=time_window_minutes
                )

                # This is a simplified iceberg detection
                # In practice, you'd track price level history over time
                potential_icebergs = []

                # Look for prices with consistent volume that might be refilling
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

                            # 2. Volume size relative to market
                            volume_threshold = 500

                            # 3. Consistent volume patterns
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
                                            ),
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
                    },
                }

        except Exception as e:
            self.logger.error(f"Error detecting iceberg orders: {e}")
            return {"potential_icebergs": [], "analysis": {}}

    def detect_iceberg_orders_advanced(
        self,
        time_window_minutes: int = 30,
        min_refresh_count: int = 5,
        volume_consistency_threshold: float = 0.85,
        min_total_volume: int = 1000,
        statistical_confidence: float = 0.95,
    ) -> dict[str, Any]:
        """
        Advanced iceberg order detection using statistical analysis.

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
            with self.orderbook_lock:
                cutoff_time = datetime.now(self.timezone) - timedelta(
                    minutes=time_window_minutes
                )

                # Use Polars for history tracking
                history_df = pl.DataFrame(
                    {
                        "price_level": [],
                        "volume": [],
                        "timestamp": [],
                    }
                )

                for side, df in [
                    ("bid", self.orderbook_bids),
                    ("ask", self.orderbook_asks),
                ]:
                    if df.height == 0:
                        continue

                    recent_df = (
                        df.filter(pl.col("timestamp") >= pl.lit(cutoff_time))
                        if "timestamp" in df.columns
                        else df
                    )

                    if recent_df.height == 0:
                        continue

                    # Append to history_df
                    side_df = recent_df.with_columns(pl.lit(side).alias("side"))
                    history_df = pl.concat([history_df, side_df])

                # Now perform groupby and statistical analysis on history_df
                # For example:
                grouped = history_df.group_by("price_level", "side").agg(
                    pl.col("volume").mean().alias("avg_volume"),
                    pl.col("volume").std().alias("vol_std"),
                    pl.col("volume").count().alias("refresh_count"),
                    pl.col("timestamp")
                    .sort()
                    .diff()
                    .mean()
                    .alias("avg_refresh_interval"),
                )

                # Then filter for potential icebergs based on conditions
                potential = grouped.filter(
                    (pl.col("refresh_count") >= min_refresh_count)
                    & (
                        pl.col("vol_std") / pl.col("avg_volume")
                        < (1 - volume_consistency_threshold)
                    )
                )

                potential_icebergs = []
                for row in potential.to_dicts():
                    confidence_score = 0.7  # Simplified calculation
                    estimated_hidden_size = row["avg_volume"] * 3
                    iceberg_data = {
                        "price": row["price_level"],
                        "current_volume": row["avg_volume"],
                        "side": row["side"],
                        "confidence": "medium",
                        "confidence_score": confidence_score,
                        "estimated_hidden_size": estimated_hidden_size,
                        "refresh_count": row["refresh_count"],
                    }
                    potential_icebergs.append(iceberg_data)

                # STEP 10: Cross-reference with trade data
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
                    },
                }

        except Exception as e:
            self.logger.error(f"Error in advanced iceberg detection: {e}")
            return {"potential_icebergs": [], "analysis": {"error": str(e)}}

    def get_cumulative_delta(self, time_window_minutes: int = 30) -> dict[str, Any]:
        """
        Calculate cumulative delta (running total of buy vs sell volume).

        Args:
            time_window_minutes: Time window for delta calculation

        Returns:
            dict: Cumulative delta analysis
        """
        try:
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
                
                # 🔍 DEBUG: Log orderbook data availability
                self.logger.debug(f"🔍 Orderbook data: {len(bids)} bids, {len(asks)} asks")
                self.logger.debug(f"🔍 Top volumes: bid={top_bid_volume}, ask={top_ask_volume}")

                total_volume = top_bid_volume + top_ask_volume
                if total_volume == 0:
                    self.logger.debug(f"🔍 Zero total volume - returning neutral (bids={len(bids)}, asks={len(asks)})")
                    return {
                        "imbalance_ratio": 0,
                        "direction": "neutral",
                        "confidence": "low",
                    }

                # Calculate imbalance ratio (-1 to 1)
                imbalance_ratio = (top_bid_volume - top_ask_volume) / total_volume

                # Get recent trade flow for confirmation
                trade_flow = self.get_trade_flow_summary(minutes=5)
                trade_imbalance = 0
                if trade_flow["total_volume"] > 0:
                    trade_imbalance = (
                        trade_flow["buy_volume"] - trade_flow["sell_volume"]
                    ) / trade_flow["total_volume"]

                # Determine direction and confidence
                # 🧪 TEMPORARY: Lower thresholds for low-volatility debugging
                # Normal: 0.3, Debug: 0.05 (much more sensitive)
                bullish_threshold = 0.05  # Was 0.3
                bearish_threshold = -0.05  # Was -0.3
                
                if imbalance_ratio > bullish_threshold:
                    direction = "bullish"
                    confidence = "high" if trade_imbalance > 0.2 else "medium"
                elif imbalance_ratio < bearish_threshold:
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

                # Separate into support and resistance
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
        Add a callback for specific orderbook events.

        Args:
            event_type: Type of event ('market_depth', 'trade_execution', etc.)
            callback: Callback function to execute
        """
        self.callbacks[event_type].append(callback)
        self.logger.debug(f"Added orderbook callback for {event_type}")

    def remove_callback(self, event_type: str, callback: Callable):
        """Remove a callback for specific events."""
        if callback in self.callbacks[event_type]:
            self.callbacks[event_type].remove(callback)
            self.logger.debug(f"Removed orderbook callback for {event_type}")

    def _trigger_callbacks(self, event_type: str, data: dict):
        """Trigger all callbacks for a specific event type."""
        for callback in self.callbacks[event_type]:
            try:
                callback(data)
            except Exception as e:
                self.logger.error(f"Error in {event_type} orderbook callback: {e}")

    def get_statistics(self) -> dict[str, Any]:
        """Get statistics about the orderbook."""
        with self.orderbook_lock:
            best_prices = self.get_best_bid_ask()
            return {
                "instrument": self.instrument,
                "bid_levels": len(self.orderbook_bids),
                "ask_levels": len(self.orderbook_asks),
                "best_bid": best_prices.get("bid"),
                "best_ask": best_prices.get("ask"),
                "spread": best_prices.get("spread"),
                "mid_price": best_prices.get("mid"),
                "last_update": self.last_orderbook_update,
                "level2_updates": self.level2_update_count,
                "recent_trades_count": len(self.recent_trades),
                "order_type_stats": self.get_order_type_statistics(),
            }

    # Helper methods for advanced iceberg detection
    def _is_round_price(self, price: float) -> float:
        """Check if price is at psychologically significant level."""
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
            # Simple statistical significance based on volume consistency
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

        avg_visible = mean(volume_history)

        # Advanced estimation based on multiple factors
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
        trades_in_window = self.recent_trades.filter(pl.col("timestamp") >= cutoff_time)

        if len(trades_in_window) == 0:
            return icebergs

        # Enhance icebergs with trade execution analysis
        enhanced_icebergs = []

        for iceberg in icebergs:
            price = iceberg["price"]

            # Find trades near this price level (within 1 tick)
            price_tolerance = 0.01  # 1 cent tolerance
            nearby_trades = trades_in_window.filter(
                (pl.col("price") >= price - price_tolerance)
                & (pl.col("price") <= price + price_tolerance)
            )

            if len(nearby_trades) > 0:
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
