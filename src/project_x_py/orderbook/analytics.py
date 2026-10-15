"""
Async market analytics for ProjectX orderbook.

Author: @TexasCoding
Date: 2025-08-02

Overview:
    Implements advanced quantitative analytics for the async orderbook, extracting
    actionable insights on market structure, order flow, liquidity, and trade intensity.
    Enables strategy development and microstructure research on deep market data.

Key Features:
    - Market imbalance detection and ratio analysis
    - Orderbook depth and liquidity distribution metrics
    - Cumulative delta and trade flow statistics
    - VWAP, spread, and volume breakdowns
    - Statistical summaries for trading strategy development
    - Real-time analytics with thread-safe operations
    - Comprehensive error handling and graceful degradation
    - Configurable analysis parameters and time windows

Analytics Categories:
    - Market Imbalance: Buy/sell pressure analysis and ratio calculations
    - Orderbook Depth: Liquidity analysis within price ranges
    - Trade Flow: Cumulative delta and trade classification statistics
    - Liquidity Analysis: Significant liquidity level identification
    - Spread Analysis: Bid-ask spread characteristics and patterns
    - Statistical Summaries: Comprehensive orderbook health metrics

Example Usage:
    ```python
    # V3.1: Using analytics with TradingSuite's orderbook
    from project_x_py import TradingSuite

    suite = await TradingSuite.create("MNQ", features=["orderbook"])

    # V3.1: Market imbalance analysis
    imbalance = await suite.orderbook.get_market_imbalance(levels=10)
    print(f"Imbalance: {imbalance['imbalance_ratio']:.2%}")
    print(f"Analysis: {imbalance['analysis']}")

    # V3.1: Depth analysis
    depth = await suite.orderbook.get_orderbook_depth(price_range=5.0)
    print(f"Bid depth: {depth['bid_depth']['total_volume']} contracts")
    print(f"Ask depth: {depth['ask_depth']['total_volume']} contracts")

    # V3.1: Trade flow analysis
    delta = await suite.orderbook.get_cumulative_delta(time_window_minutes=60)
    print(f"Cumulative delta: {delta['cumulative_delta']}")

    await suite.disconnect()
    ```

See Also:
    - `orderbook.base.OrderBookBase`
    - `orderbook.detection.OrderDetection`
    - `orderbook.profile.VolumeProfile`
"""

from datetime import datetime, timedelta
from typing import Any

import polars as pl

from project_x_py.types.response_types import (
    LiquidityAnalysisResponse,
    MarketImpactResponse,
)
from project_x_py.utils import (
    ProjectXLogger,
    handle_errors,
)

from .base import OrderBookBase


class MarketAnalytics:
    """
    Provides market analytics for the orderbook.

    This class implements advanced analytics methods for the OrderBook, focusing on
    extracting actionable market insights from the raw orderbook data. It is designed as
    a component that is injected into the main OrderBook to provide specialized
    analytical capabilities while maintaining a clean separation of concerns.

    The analytics methods focus on several key areas:
    1. Market imbalance analysis - Detecting buy/sell pressure
    2. Liquidity distribution analysis - Understanding depth across price levels
    3. Trade flow analysis - Classifying aggressive vs. passive executions
    4. Cumulative delta tracking - Measuring net buying/selling pressure over time
    5. Significant liquidity levels - Identifying potential support/resistance
    6. Spread analysis - Bid-ask spread characteristics and patterns
    7. Statistical summaries - Comprehensive orderbook health metrics

    Each method follows a consistent pattern:
    - Thread-safe execution through the orderbook lock
    - Comprehensive error handling and logging
    - Return of structured analysis results with multiple metrics
    - Optional time filtering when appropriate
    - Configurable parameters for analysis sensitivity

    These analytics are designed to be used by trading strategies, market analysis tools,
    and visualization components that need deeper insights beyond raw orderbook data.

    Performance Characteristics:
        - All methods are optimized for real-time analysis
        - Thread-safe operations with minimal lock contention
        - Graceful degradation when data is insufficient
        - Memory-efficient calculations using Polars DataFrames
    """

    def __init__(self, orderbook: OrderBookBase):
        self.orderbook = orderbook
        self.logger = ProjectXLogger.get_logger(__name__)

    @handle_errors(
        "get market imbalance",
        reraise=False,
        default_return={
            "imbalance_ratio": 0.0,
            "bid_volume": 0,
            "ask_volume": 0,
            "analysis": "Error occurred",
        },
    )
    async def get_market_imbalance(self, levels: int = 10) -> LiquidityAnalysisResponse:
        """
        Calculate order flow imbalance between bid and ask sides.

        This method quantifies the imbalance between buying and selling pressure in the
        orderbook by comparing the total volume on the bid side versus the ask side.
        A positive imbalance ratio indicates stronger buying pressure, while a negative
        ratio indicates stronger selling pressure.

        The analysis includes:
        - Imbalance ratio: (bid_volume - ask_volume) / total_volume
        - Raw bid and ask volumes
        - Number of populated price levels on each side
        - Text analysis of market conditions based on the imbalance ratio
        - Timestamp of the analysis

        The method is thread-safe and acquires the orderbook lock during execution.

        Args:
            levels: Number of price levels to analyze on each side of the book (default: 10).
                Higher values analyze deeper into the orderbook but may include less
                relevant levels.

        Returns:
            Dict containing:
                imbalance_ratio: Float between -1.0 and 1.0 where:
                    - Positive values indicate buying pressure
                    - Negative values indicate selling pressure
                    - Values near 0 indicate a balanced orderbook
                bid_volume: Total volume on the bid side
                ask_volume: Total volume on the ask side
                bid_levels: Number of populated bid price levels analyzed
                ask_levels: Number of populated ask price levels analyzed
                analysis: Text description of market conditions
                timestamp: Time of analysis

        Example:
            >>> imbalance = await orderbook.get_market_imbalance(levels=5)
            >>> print(f"Imbalance ratio: {imbalance['imbalance_ratio']:.2f}")
            >>> print(f"Analysis: {imbalance['analysis']}")
            >>> print(
            ...     f"Bid volume: {imbalance['bid_volume']}, "
            ...     f"Ask volume: {imbalance['ask_volume']}"
            ... )
        """
        async with self.orderbook.orderbook_lock:
            # Get orderbook levels
            bids = self.orderbook._get_orderbook_bids_unlocked(levels)
            asks = self.orderbook._get_orderbook_asks_unlocked(levels)

            if bids.is_empty() or asks.is_empty():
                current_time = datetime.now(self.orderbook.timezone)
                return {
                    "bid_liquidity": 0.0,
                    "ask_liquidity": 0.0,
                    "total_liquidity": 0.0,
                    "avg_spread": 0.0,
                    "spread_volatility": 0.0,
                    "liquidity_score": 0.0,
                    "market_depth_score": 0.0,
                    "resilience_score": 0.0,
                    "tightness_score": 0.0,
                    "immediacy_score": 0.0,
                    "depth_imbalance": 0.0,
                    "effective_spread": 0.0,
                    "realized_spread": 0.0,
                    "price_impact": 0.0,
                    "timestamp": current_time.isoformat(),
                }

            # Calculate volumes
            bid_volume = int(bids["volume"].sum())
            ask_volume = int(asks["volume"].sum())
            total_volume = bid_volume + ask_volume

            if total_volume == 0:
                current_time = datetime.now(self.orderbook.timezone)
                return {
                    "bid_liquidity": 0.0,
                    "ask_liquidity": 0.0,
                    "total_liquidity": 0.0,
                    "avg_spread": 0.0,
                    "spread_volatility": 0.0,
                    "liquidity_score": 0.0,
                    "market_depth_score": 0.0,
                    "resilience_score": 0.0,
                    "tightness_score": 0.0,
                    "immediacy_score": 0.0,
                    "depth_imbalance": 0.0,
                    "effective_spread": 0.0,
                    "realized_spread": 0.0,
                    "price_impact": 0.0,
                    "timestamp": current_time.isoformat(),
                }

            # Calculate best prices for spread analysis
            best_bid = float(bids.sort("price", descending=True)["price"][0])
            best_ask = float(asks.sort("price")["price"][0])
            spread = best_ask - best_bid

            # Calculate depth imbalance
            depth_imbalance = (bid_volume - ask_volume) / total_volume

            # Calculate liquidity metrics
            bid_liquidity = float(bid_volume)
            ask_liquidity = float(ask_volume)
            total_liquidity = float(total_volume)

            # Calculate scores (0-10 scale)
            market_depth_score = min(10.0, total_volume / 1000)  # Arbitrary scaling
            tightness_score = max(
                0.0, 10.0 - (spread * 100)
            )  # Smaller spreads = higher score

            # Simple liquidity score based on volume and depth
            liquidity_score = (market_depth_score + tightness_score) / 2

            # Resilience and immediacy scores (simplified)
            resilience_score = min(
                10.0, (bids.height + asks.height) / 10
            )  # Based on depth levels
            immediacy_score = tightness_score  # Approximation

            # Spread analysis (simplified - would need historical data for true volatility)
            avg_spread = spread
            spread_volatility = 0.0  # Would need historical spreads
            effective_spread = spread  # Approximation
            realized_spread = spread * 0.5  # Approximation
            price_impact = abs(depth_imbalance) * spread  # Simplified calculation

            current_time = datetime.now(self.orderbook.timezone)

            return {
                "bid_liquidity": bid_liquidity,
                "ask_liquidity": ask_liquidity,
                "total_liquidity": total_liquidity,
                "avg_spread": avg_spread,
                "spread_volatility": spread_volatility,
                "liquidity_score": liquidity_score,
                "market_depth_score": market_depth_score,
                "resilience_score": resilience_score,
                "tightness_score": tightness_score,
                "immediacy_score": immediacy_score,
                "depth_imbalance": depth_imbalance,
                "effective_spread": effective_spread,
                "realized_spread": realized_spread,
                "price_impact": price_impact,
                "timestamp": current_time.isoformat(),
            }

    @handle_errors(
        "get orderbook depth",
        reraise=False,
        default_return={"error": "Analysis failed"},
    )
    async def get_orderbook_depth(self, price_range: float) -> MarketImpactResponse:
        """
        Analyze orderbook depth within a price range.

        Args:
            price_range: Price range from best bid/ask to analyze

        Returns:
            Dict containing depth analysis
        """
        async with self.orderbook.orderbook_lock:
            best_prices = self.orderbook._get_best_bid_ask_unlocked()
            best_bid = best_prices.get("bid")
            best_ask = best_prices.get("ask")

            if best_bid is None or best_ask is None:
                current_time = datetime.now(self.orderbook.timezone)
                return {
                    "estimated_fill_price": 0.0,
                    "price_impact_pct": 0.0,
                    "spread_cost": 0.0,
                    "market_impact_cost": 0.0,
                    "total_transaction_cost": 0.0,
                    "levels_consumed": 0,
                    "remaining_liquidity": 0.0,
                    "confidence_level": 0.0,
                    "slippage_estimate": 0.0,
                    "timing_risk": 0.0,
                    "liquidity_premium": 0.0,
                    "implementation_shortfall": 0.0,
                    "timestamp": current_time.isoformat(),
                }

            # Filter bids within range
            bid_depth = self.orderbook.orderbook_bids.filter(
                (pl.col("price") >= best_bid - price_range) & (pl.col("volume") > 0)
            )

            # Filter asks within range
            ask_depth = self.orderbook.orderbook_asks.filter(
                (pl.col("price") <= best_ask + price_range) & (pl.col("volume") > 0)
            )

            # Calculate market impact metrics
            spread = best_ask - best_bid
            mid_price = (best_bid + best_ask) / 2

            # Estimate fill price (simplified - assumes we're buying at best ask)
            estimated_fill_price = best_ask

            # Calculate various costs and impacts
            spread_cost = spread / 2  # Half spread as crossing cost
            price_impact_pct = (spread_cost / mid_price) * 100 if mid_price > 0 else 0.0

            # Market impact cost (simplified)
            bid_volume = (
                int(bid_depth["volume"].sum()) if not bid_depth.is_empty() else 0
            )
            ask_volume = (
                int(ask_depth["volume"].sum()) if not ask_depth.is_empty() else 0
            )
            total_volume = bid_volume + ask_volume

            market_impact_cost = spread_cost * 0.5  # Simplified calculation
            total_transaction_cost = spread_cost + market_impact_cost

            # Levels and liquidity analysis
            levels_consumed = min(bid_depth.height, ask_depth.height)
            remaining_liquidity = float(total_volume)

            # Risk metrics (simplified)
            confidence_level = min(
                100.0, total_volume / 100
            )  # Based on available volume
            slippage_estimate = price_impact_pct * 1.5  # Conservative estimate
            timing_risk = price_impact_pct * 0.3  # Risk from timing
            liquidity_premium = spread_cost * 0.2  # Premium for immediacy
            implementation_shortfall = slippage_estimate + timing_risk

            current_time = datetime.now(self.orderbook.timezone)

            return {
                "estimated_fill_price": estimated_fill_price,
                "price_impact_pct": price_impact_pct,
                "spread_cost": spread_cost,
                "market_impact_cost": market_impact_cost,
                "total_transaction_cost": total_transaction_cost,
                "levels_consumed": levels_consumed,
                "remaining_liquidity": remaining_liquidity,
                "confidence_level": confidence_level,
                "slippage_estimate": slippage_estimate,
                "timing_risk": timing_risk,
                "liquidity_premium": liquidity_premium,
                "implementation_shortfall": implementation_shortfall,
                "timestamp": current_time.isoformat(),
            }

    @handle_errors(
        "get cumulative delta",
        reraise=False,
        default_return={
            "cumulative_delta": 0,
            "buy_volume": 0,
            "sell_volume": 0,
            "error": "Analysis failed",
        },
    )
    async def get_cumulative_delta(
        self, time_window_minutes: int = 60
    ) -> dict[str, Any]:
        """
        Get cumulative delta (buy volume - sell volume) over time window.

        Args:
            time_window_minutes: Time window to analyze

        Returns:
            Dict containing cumulative delta analysis
        """
        async with self.orderbook.orderbook_lock:
            if self.orderbook.recent_trades.is_empty():
                return {
                    "cumulative_delta": 0,
                    "buy_volume": 0,
                    "sell_volume": 0,
                    "neutral_volume": 0,
                    "period_minutes": time_window_minutes,
                }

            # Filter trades within time window
            cutoff_time = datetime.now(self.orderbook.timezone) - timedelta(
                minutes=time_window_minutes
            )

            recent_trades = self.orderbook.recent_trades.filter(
                pl.col("timestamp") >= cutoff_time
            )

            if recent_trades.is_empty():
                return {
                    "cumulative_delta": 0,
                    "buy_volume": 0,
                    "sell_volume": 0,
                    "neutral_volume": 0,
                    "period_minutes": time_window_minutes,
                }

            # Calculate volumes by side
            buy_trades = recent_trades.filter(pl.col("side") == "buy")
            sell_trades = recent_trades.filter(pl.col("side") == "sell")
            neutral_trades = recent_trades.filter(pl.col("side") == "neutral")

            buy_volume = (
                int(buy_trades["volume"].sum()) if not buy_trades.is_empty() else 0
            )
            sell_volume = (
                int(sell_trades["volume"].sum()) if not sell_trades.is_empty() else 0
            )
            neutral_volume = (
                int(neutral_trades["volume"].sum())
                if not neutral_trades.is_empty()
                else 0
            )

            cumulative_delta = buy_volume - sell_volume

            return {
                "cumulative_delta": cumulative_delta,
                "buy_volume": buy_volume,
                "sell_volume": sell_volume,
                "neutral_volume": neutral_volume,
                "total_volume": buy_volume + sell_volume + neutral_volume,
                "period_minutes": time_window_minutes,
                "trade_count": recent_trades.height,
                "delta_per_trade": cumulative_delta / recent_trades.height
                if recent_trades.height > 0
                else 0,
            }

    @handle_errors(
        "get trade flow summary",
        reraise=False,
        default_return={"error": "Analysis failed"},
    )
    async def get_trade_flow_summary(self) -> dict[str, Any]:
        """Get comprehensive trade flow statistics."""
        async with self.orderbook.orderbook_lock:
            # Calculate VWAP
            vwap = None
            if self.orderbook.vwap_denominator > 0:
                vwap = self.orderbook.vwap_numerator / self.orderbook.vwap_denominator

            # Get recent trade statistics
            recent_trades_stats = {}
            if not self.orderbook.recent_trades.is_empty():
                recent_trades_stats = {
                    "total_trades": self.orderbook.recent_trades.height,
                    "avg_trade_size": float(
                        str(self.orderbook.recent_trades["volume"].mean())
                    ),
                    "max_trade_size": int(
                        str(self.orderbook.recent_trades["volume"].max())
                    ),
                    "min_trade_size": int(
                        str(self.orderbook.recent_trades["volume"].min())
                    ),
                }

            return {
                "aggressive_buy_volume": self.orderbook.trade_flow_stats[
                    "aggressive_buy_volume"
                ],
                "aggressive_sell_volume": self.orderbook.trade_flow_stats[
                    "aggressive_sell_volume"
                ],
                "passive_buy_volume": self.orderbook.trade_flow_stats[
                    "passive_buy_volume"
                ],
                "passive_sell_volume": self.orderbook.trade_flow_stats[
                    "passive_sell_volume"
                ],
                "market_maker_trades": self.orderbook.trade_flow_stats[
                    "market_maker_trades"
                ],
                "cumulative_delta": self.orderbook.cumulative_delta,
                "vwap": vwap,
                "session_start": self.orderbook.session_start_time,
                **recent_trades_stats,
            }

    @handle_errors(
        "get liquidity levels",
        reraise=False,
        default_return={"error": "Analysis failed"},
    )
    async def get_liquidity_levels(
        self, min_volume: int = 100, levels: int = 20
    ) -> dict[str, Any]:
        """
        Identify significant liquidity levels in the orderbook.

        Args:
            min_volume: Minimum volume to consider significant
            levels: Number of levels to check on each side

        Returns:
            Dict containing liquidity analysis
        """
        async with self.orderbook.orderbook_lock:
            # Get orderbook levels
            bids = self.orderbook._get_orderbook_bids_unlocked(levels)
            asks = self.orderbook._get_orderbook_asks_unlocked(levels)

            # Find significant bid levels
            significant_bids = []
            if not bids.is_empty():
                sig_bids = bids.filter(pl.col("volume") >= min_volume)
                if not sig_bids.is_empty():
                    significant_bids = sig_bids.to_dicts()

            # Find significant ask levels
            significant_asks = []
            if not asks.is_empty():
                sig_asks = asks.filter(pl.col("volume") >= min_volume)
                if not sig_asks.is_empty():
                    significant_asks = sig_asks.to_dicts()

            # Calculate liquidity concentration
            total_bid_liquidity = sum(b["volume"] for b in significant_bids)
            total_ask_liquidity = sum(a["volume"] for a in significant_asks)

            return {
                "significant_bid_levels": significant_bids,
                "significant_ask_levels": significant_asks,
                "total_bid_liquidity": total_bid_liquidity,
                "total_ask_liquidity": total_ask_liquidity,
                "liquidity_imbalance": (
                    (total_bid_liquidity - total_ask_liquidity)
                    / (total_bid_liquidity + total_ask_liquidity)
                    if (total_bid_liquidity + total_ask_liquidity) > 0
                    else 0
                ),
                "min_volume_threshold": min_volume,
            }

    @handle_errors(
        "get statistics", reraise=False, default_return={"error": "Analysis failed"}
    )
    async def get_statistics(self) -> dict[str, Any]:
        """Get comprehensive orderbook statistics."""
        async with self.orderbook.orderbook_lock:
            # Get best prices
            best_prices = self.orderbook._get_best_bid_ask_unlocked()

            # Calculate volume statistics
            total_bid_size = (
                self.orderbook.orderbook_bids["volume"].sum()
                if not self.orderbook.orderbook_bids.is_empty()
                else 0
            )
            total_ask_size = (
                self.orderbook.orderbook_asks["volume"].sum()
                if not self.orderbook.orderbook_asks.is_empty()
                else 0
            )

            # Calculate trade statistics
            buy_trades = 0
            sell_trades = 0
            total_trade_volume = 0
            if not self.orderbook.recent_trades.is_empty():
                # Optimized: Single pass through data with aggregation
                trade_stats = self.orderbook.recent_trades.group_by("side").agg(
                    [
                        pl.len().alias("count"),
                        pl.col("volume").sum().alias("total_volume"),
                    ]
                )

                # Extract buy/sell counts
                for row in trade_stats.iter_rows(named=True):
                    if row["side"] == "buy":
                        buy_trades = row["count"]
                    elif row["side"] == "sell":
                        sell_trades = row["count"]

                total_trade_volume = int(self.orderbook.recent_trades["volume"].sum())

            avg_trade_size = int(
                total_trade_volume / self.orderbook.recent_trades.height
                if self.orderbook.recent_trades.height > 0
                else 0
            )

            # Calculate VWAP
            vwap = (
                self.orderbook.vwap_numerator / self.orderbook.vwap_denominator
                if self.orderbook.vwap_denominator > 0
                else 0
            )

            # Get session high/low from trades
            session_high = 0
            session_low = 0
            if not self.orderbook.recent_trades.is_empty():
                max_price = self.orderbook.recent_trades["price"].max()
                min_price = self.orderbook.recent_trades["price"].min()
                # Handle Polars return types
                if isinstance(max_price, int | float):
                    session_high = int(max_price)
                if isinstance(min_price, int | float):
                    session_low = int(min_price)

            # Calculate basic stats
            stats = {
                "instrument": self.orderbook.instrument,
                "level2_update_count": self.orderbook.level2_update_count,
                "last_update": self.orderbook.last_orderbook_update,
                "best_bid": best_prices.get("bid"),
                "best_ask": best_prices.get("ask"),
                "spread": best_prices.get("spread"),
                "mid_price": best_prices.get("mid")
                if best_prices.get("mid")
                else (
                    (best_prices.get("bid", 0) + best_prices.get("ask", 0)) / 2
                    if best_prices.get("bid") and best_prices.get("ask")
                    else 0
                ),
                "bid_depth": self.orderbook.orderbook_bids.height,
                "ask_depth": self.orderbook.orderbook_asks.height,
                "total_bid_size": int(total_bid_size),
                "total_ask_size": int(total_ask_size),
                "total_trades": self.orderbook.recent_trades.height,
                "buy_trades": buy_trades,
                "sell_trades": sell_trades,
                "avg_trade_size": avg_trade_size,
                "vwap": vwap,
                "session_high": session_high,
                "session_low": session_low,
                "order_type_breakdown": dict(self.orderbook.order_type_stats),
            }

            # Add spread statistics if available
            if self.orderbook.spread_history:
                spreads = [s["spread"] for s in self.orderbook.spread_history[-100:]]
                stats["spread_stats"] = {
                    "current": best_prices.get("spread"),
                    "average": sum(spreads) / len(spreads),
                    "min": min(spreads),
                    "max": max(spreads),
                    "samples": len(spreads),
                }

            return stats

    @staticmethod
    def analyze_dataframe_spread(
        data: pl.DataFrame,
        bid_column: str = "bid",
        ask_column: str = "ask",
        mid_column: str | None = None,
    ) -> dict[str, Any]:
        """
        Analyze bid-ask spread characteristics from a DataFrame.

        This is a static method that can analyze spread data from any DataFrame,
        useful for historical analysis or backtesting scenarios where you have
        bid/ask data but not a live orderbook.

        Args:
            data: DataFrame with bid/ask price columns
            bid_column: Name of the bid price column (default: "bid")
            ask_column: Name of the ask price column (default: "ask")
            mid_column: Name of the mid price column (optional, will calculate if not provided)

        Returns:
            Dict containing spread analysis:
                - avg_spread: Average absolute spread
                - median_spread: Median absolute spread
                - min_spread: Minimum spread observed
                - max_spread: Maximum spread observed
                - avg_relative_spread: Average spread as percentage of mid price
                - spread_volatility: Standard deviation of spread

        Example:
            >>> # Analyze historical bid/ask data
            >>> spread_stats = MarketAnalytics.analyze_dataframe_spread(historical_data)
            >>> print(f"Average spread: ${spread_stats['avg_spread']:.4f}")
            >>> print(f"Relative spread: {spread_stats['avg_relative_spread']:.4%}")
        """
        required_cols = [bid_column, ask_column]
        for col in required_cols:
            if col not in data.columns:
                raise ValueError(f"Column '{col}' not found in data")

        if data.is_empty():
            return {"error": "No data provided"}

        try:
            # Calculate mid price if not provided
            if mid_column is None:
                data = data.with_columns(
                    ((pl.col(bid_column) + pl.col(ask_column)) / 2).alias("mid_price")
                )
                mid_column = "mid_price"

            # Calculate spread metrics
            analysis_data = (
                data.with_columns(
                    [
                        (pl.col(ask_column) - pl.col(bid_column)).alias("spread"),
                        (
                            (pl.col(ask_column) - pl.col(bid_column))
                            / pl.col(mid_column)
                        ).alias("relative_spread"),
                    ]
                )
                .select(["spread", "relative_spread"])
                .drop_nulls()
            )

            if analysis_data.is_empty():
                return {"error": "No valid spread data"}

            return {
                "avg_spread": analysis_data.select(pl.col("spread").mean()).item()
                or 0.0,
                "median_spread": analysis_data.select(pl.col("spread").median()).item()
                or 0.0,
                "min_spread": analysis_data.select(pl.col("spread").min()).item()
                or 0.0,
                "max_spread": analysis_data.select(pl.col("spread").max()).item()
                or 0.0,
                "avg_relative_spread": analysis_data.select(
                    pl.col("relative_spread").mean()
                ).item()
                or 0.0,
                "spread_volatility": analysis_data.select(pl.col("spread").std()).item()
                or 0.0,
            }

        except Exception as e:
            return {"error": str(e)}
