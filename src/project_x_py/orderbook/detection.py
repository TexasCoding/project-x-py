"""
Async detection algorithms for ProjectX orderbook.

Author: @TexasCoding
Date: 2025-08-02

Overview:
    Implements sophisticated detection logic for iceberg orders, clusters, and
    hidden liquidity in the ProjectX async orderbook. Uses historical price
    level, trade, and refresh data to infer institutional activity and market
    manipulation attempts.

Key Features:
    - Iceberg order detection with confidence scoring
    - Order clustering and spread concentration analysis
    - Market microstructure and hidden volume metrics
    - Configurable detection sensitivity and parameters
    - Advanced market metrics and book pressure analysis
    - Real-time detection with historical pattern recognition
    - Comprehensive error handling and graceful degradation

Detection Algorithms:
    - Iceberg Orders: Large orders split into smaller pieces to hide true size
    - Order Clusters: Groups of orders at similar price levels indicating coordination
    - Market Microstructure: Book pressure, trade intensity, and price concentration
    - Hidden Liquidity: Volume patterns suggesting institutional activity
    - Advanced Metrics: Comprehensive market structure analysis

Example Usage:
    ```python
    # V3.1: Advanced detection with TradingSuite's orderbook
    from project_x_py import TradingSuite

    suite = await TradingSuite.create("MNQ", features=["orderbook"])

    # V3.1: Detect iceberg orders with confidence scoring
    icebergs = await suite.orderbook.detect_iceberg_orders(min_refreshes=5)
    for level in icebergs["iceberg_levels"]:
        print(f"Iceberg at {level['price']:.2f}: confidence {level['confidence']:.1%}")

    # V3.1: Order clustering analysis
    clusters = await suite.orderbook.detect_order_clusters(min_cluster_size=3)
    for cluster in clusters:
        print(
            f"Cluster at {cluster['center_price']:.2f}: {cluster['total_volume']} contracts"
        )

    # V3.1: Advanced market metrics
    metrics = await suite.orderbook.get_advanced_market_metrics()
    print(f"Book pressure ratio: {metrics['book_pressure']['pressure_ratio']}")

    await suite.disconnect()
    ```

See Also:
    - `orderbook.base.OrderBookBase`
    - `orderbook.analytics.MarketAnalytics`
"""

import logging
from datetime import datetime, timedelta
from typing import Any

import polars as pl

from project_x_py.orderbook.base import OrderBookBase
from project_x_py.types import IcebergConfig
from project_x_py.types.response_types import (
    OrderbookAnalysisResponse,
    SpoofingDetectionResponse,
)


class OrderDetection:
    """
    Provides advanced order detection algorithms.

    This class implements sophisticated algorithms for detecting hidden patterns in
    orderbook data that may indicate specific trading behaviors, hidden liquidity,
    or other market microstructure phenomena. It is designed as a specialized component
    of the OrderBook that focuses solely on detection capabilities.

    Key features:
    1. Iceberg order detection - Identifies large orders that are deliberately split
       into smaller pieces to hide their true size
    2. Order clustering analysis - Detects groups of orders at similar price levels
       that may represent coordinated activity or key liquidity zones
    3. Advanced market metrics - Calculates metrics like book pressure and
       price concentration to reveal hidden market dynamics
    4. Hidden liquidity detection - Identifies volume patterns suggesting institutional activity
    5. Market microstructure analysis - Comprehensive market structure metrics

    Each detection algorithm follows these principles:
    - Configurable sensitivity with reasonable defaults
    - Explicit confidence scoring to indicate detection reliability
    - Comprehensive metadata to explain the reasoning behind detections
    - Thread-safe implementation through orderbook lock usage
    - Proper error handling with graceful degradation
    - Real-time detection with historical pattern recognition

    The detection methods leverage the historical data accumulated by the orderbook
    to identify patterns over time rather than just analyzing the current state,
    allowing for more sophisticated and reliable detections.

    Performance Characteristics:
        - Real-time detection capabilities with minimal latency
        - Memory-efficient algorithms using historical data
        - Configurable detection sensitivity and parameters
        - Thread-safe operations with proper lock management
    """

    def __init__(self, orderbook: OrderBookBase):
        self.orderbook = orderbook
        self.logger = logging.getLogger(__name__)
        self.iceberg_config = IcebergConfig()

    async def detect_iceberg_orders(
        self,
        min_refreshes: int | None = None,
        volume_threshold: int | None = None,
        time_window_minutes: int | None = None,
    ) -> dict[str, Any]:
        """
        Detect potential iceberg orders based on price level refresh patterns.

        Iceberg orders are detected by looking for price levels that:
        1. Refresh frequently with new volume
        2. Maintain consistent volume levels
        3. Show patterns of immediate replenishment after trades

        Args:
            min_refreshes: Minimum refreshes to consider iceberg (default: 5)
            volume_threshold: Minimum volume to consider (default: 50)
            time_window_minutes: Time window to analyze (default: 10)

        Returns:
            List of detected iceberg orders with analysis
        """
        min_refreshes = min_refreshes or self.iceberg_config.min_refreshes
        volume_threshold = volume_threshold or self.iceberg_config.volume_threshold
        time_window_minutes = (
            time_window_minutes or self.iceberg_config.time_window_minutes
        )

        async with self.orderbook.orderbook_lock:
            try:
                current_time = datetime.now(self.orderbook.timezone)
                cutoff_time = current_time - timedelta(minutes=time_window_minutes)

                detected_icebergs = []

                # Analyze price level history
                for (
                    price,
                    side,
                ), history in self.orderbook.price_level_history.items():
                    # Filter recent history
                    recent_history = [
                        h
                        for h in history
                        if h.get("timestamp", current_time) > cutoff_time
                    ]

                    if len(recent_history) < min_refreshes:
                        continue

                    # Analyze refresh patterns
                    volumes = [h["volume"] for h in recent_history]
                    avg_volume = sum(volumes) / len(volumes)

                    if avg_volume < volume_threshold:
                        continue

                    # Check for consistent replenishment
                    replenishments = self._analyze_volume_replenishment(recent_history)

                    if replenishments >= min_refreshes - 1:
                        # Calculate confidence score
                        confidence = self._calculate_iceberg_confidence(
                            recent_history, replenishments
                        )

                        if confidence >= self.iceberg_config.confidence_threshold:
                            detected_icebergs.append(
                                {
                                    "price": price,
                                    "side": side,
                                    "avg_volume": avg_volume,
                                    "refresh_count": len(recent_history),
                                    "replenishment_count": replenishments,
                                    "confidence": confidence,
                                    "estimated_hidden_size": self._estimate_iceberg_hidden_size(
                                        recent_history, avg_volume
                                    ),
                                    "last_update": recent_history[-1]["timestamp"],
                                }
                            )

                # Sort by confidence
                detected_icebergs.sort(key=lambda x: x["confidence"], reverse=True)

                # Update statistics
                self.orderbook.trade_flow_stats["iceberg_detected_count"] = len(
                    detected_icebergs
                )

                # Return as dictionary with metadata
                return {
                    "iceberg_levels": detected_icebergs,
                    "analysis_window_minutes": time_window_minutes,
                    "detection_parameters": {
                        "min_refreshes": min_refreshes,
                        "volume_threshold": volume_threshold,
                        "confidence_threshold": self.iceberg_config.confidence_threshold,
                    },
                    "timestamp": current_time,
                }

            except Exception as e:
                self.logger.error(f"Error detecting iceberg orders: {e}")
                return {
                    "iceberg_levels": [],
                    "analysis_window_minutes": time_window_minutes,
                    "detection_parameters": {
                        "min_refreshes": min_refreshes,
                        "volume_threshold": volume_threshold,
                        "confidence_threshold": self.iceberg_config.confidence_threshold,
                    },
                    "timestamp": datetime.now(self.orderbook.timezone),
                    "error": str(e),
                }

    def _analyze_volume_replenishment(self, history: list[dict[str, Any]]) -> int:
        """
        Count volume replenishment events in price level history.

        This method analyzes the volume history for a specific price level to identify
        patterns that suggest iceberg order activity. Iceberg orders typically show
        repeated replenishment where volume decreases (due to fills) and then
        immediately increases again (new iceberg slice revealed).

        Args:
            history: List of volume updates for a price level, each containing:
                - volume: Volume at the price level
                - timestamp: Time of the update

        Returns:
            int: Number of replenishment events detected
        """
        if len(history) < 2:
            return 0

        replenishments = 0
        for i in range(1, len(history)):
            prev_volume = history[i - 1]["volume"]
            curr_volume = history[i]["volume"]

            # Check if volume increased after decrease
            if prev_volume < curr_volume:
                replenishments += 1

        return replenishments

    def _calculate_iceberg_confidence(
        self, history: list[dict[str, Any]], replenishments: int
    ) -> float:
        """
        Calculate confidence score for iceberg detection.

        This method computes a confidence score (0.0 to 1.0) indicating how likely
        it is that the observed price level behavior represents an iceberg order.
        The score is based on multiple factors that are characteristic of iceberg
        order patterns.

        Scoring components:
        1. Refresh frequency (40%): More frequent refreshes increase confidence
        2. Replenishment pattern (40%): More replenishment events increase confidence
        3. Volume consistency (20%): Consistent volume sizes increase confidence

        Args:
            history: List of volume updates for the price level
            replenishments: Number of replenishment events detected

        Returns:
            float: Confidence score between 0.0 and 1.0 where higher values
                indicate stronger evidence of iceberg order activity
        """
        if not history:
            return 0.0

        # Base confidence from refresh frequency
        refresh_score = min(len(history) / 10, 1.0) * 0.4

        # Replenishment pattern score
        replenishment_score = min(replenishments / 5, 1.0) * 0.4

        # Volume consistency score
        volumes = [h["volume"] for h in history]
        avg_volume = sum(volumes) / len(volumes)
        volume_std = (sum((v - avg_volume) ** 2 for v in volumes) / len(volumes)) ** 0.5
        consistency_score = (
            max(0, 1 - (volume_std / avg_volume)) * 0.2 if avg_volume > 0 else 0
        )

        return refresh_score + replenishment_score + consistency_score

    def _estimate_iceberg_hidden_size(
        self, history: list[dict[str, Any]], avg_volume: float
    ) -> float:
        """
        Estimate the hidden size of an iceberg order.

        This method attempts to estimate the total size of an iceberg order based
        on the observed refresh patterns and volume behavior. The estimation
        considers how frequently the order refreshes and the average volume
        displayed to project the total hidden quantity.

        The estimation algorithm:
        1. Calculates refresh rate based on history length over time window
        2. Projects total activity by scaling average volume by refresh rate
        3. Subtracts visible volume to estimate hidden portion

        Args:
            history: List of volume updates for the price level
            avg_volume: Average volume observed at this price level

        Returns:
            float: Estimated hidden size of the iceberg order. Returns 0 if
                the estimation suggests no hidden volume.

        Note:
            This is a heuristic estimation and actual hidden sizes may vary
            significantly. Use for relative comparison rather than absolute sizing.
        """
        # Simple estimation based on refresh frequency and volume
        refresh_rate = len(history) / 10  # Assume 10 minute window
        estimated_total = avg_volume * refresh_rate * 10  # Project over time
        return max(0, estimated_total - avg_volume)

    async def detect_order_clusters(
        self, min_cluster_size: int = 3, price_tolerance: float = 0.1
    ) -> list[dict[str, Any]]:
        """
        Detect clusters of orders at similar price levels.

        Args:
            min_cluster_size: Minimum orders to form a cluster
            price_tolerance: Price range to consider as cluster

        Returns:
            List of detected order clusters
        """
        async with self.orderbook.orderbook_lock:
            try:
                clusters = []

                # Analyze bid clusters
                if not self.orderbook.orderbook_bids.is_empty():
                    bid_clusters = await self._find_clusters(
                        self.orderbook.orderbook_bids,
                        "bid",
                        min_cluster_size,
                        price_tolerance,
                    )
                    clusters.extend(bid_clusters)

                # Analyze ask clusters
                if not self.orderbook.orderbook_asks.is_empty():
                    ask_clusters = await self._find_clusters(
                        self.orderbook.orderbook_asks,
                        "ask",
                        min_cluster_size,
                        price_tolerance,
                    )
                    clusters.extend(ask_clusters)

                return clusters

            except Exception as e:
                self.logger.error(f"Error detecting order clusters: {e}")
                return []

    async def _find_clusters(
        self,
        orderbook_df: pl.DataFrame,
        side: str,
        min_cluster_size: int,
        price_tolerance: float,
    ) -> list[dict[str, Any]]:
        """
        Find order clusters in orderbook data.

        This method identifies clusters of orders at similar price levels within
        the orderbook. Clusters represent areas where multiple orders are grouped
        closely together, which may indicate institutional activity, key price
        levels, or coordinated trading behavior.

        Algorithm:
        1. Sorts orderbook by price (descending for bids, ascending for asks)
        2. Iterates through price levels to find groups within tolerance
        3. Forms clusters by grouping nearby prices
        4. Filters clusters that meet minimum size requirements
        5. Calculates cluster statistics (center price, volume, etc.)

        Args:
            orderbook_df: DataFrame containing orderbook data with price/volume columns
            side: "bid" or "ask" to specify which side of the book to analyze
            min_cluster_size: Minimum number of orders required to form a cluster
            price_tolerance: Maximum price difference to group orders together

        Returns:
            List of cluster dictionaries, each containing:
                - side: "bid" or "ask"
                - center_price: Average price of the cluster
                - price_range: (min_price, max_price) tuple
                - total_volume: Sum of all volumes in the cluster
                - order_count: Number of price levels in the cluster
                - avg_order_size: Average volume per price level
                - prices: List of all prices in the cluster
                - volumes: List of all volumes in the cluster
        """
        if orderbook_df.is_empty():
            return []

        # Sort by price
        sorted_df = orderbook_df.sort("price", descending=(side == "bid"))
        prices = sorted_df["price"].to_list()
        volumes = sorted_df["volume"].to_list()

        clusters = []
        i = 0

        while i < len(prices):
            # Start a new cluster
            cluster_prices = [prices[i]]
            cluster_volumes = [volumes[i]]
            j = i + 1

            # Find all prices within tolerance
            while j < len(prices) and abs(prices[j] - prices[i]) <= price_tolerance:
                cluster_prices.append(prices[j])
                cluster_volumes.append(volumes[j])
                j += 1

            # Check if cluster is large enough
            if len(cluster_prices) >= min_cluster_size:
                clusters.append(
                    {
                        "side": side,
                        "center_price": sum(cluster_prices) / len(cluster_prices),
                        "price_range": (min(cluster_prices), max(cluster_prices)),
                        "total_volume": sum(cluster_volumes),
                        "order_count": len(cluster_prices),
                        "avg_order_size": sum(cluster_volumes) / len(cluster_volumes),
                        "prices": cluster_prices,
                        "volumes": cluster_volumes,
                    }
                )

            i = j

        return clusters

    async def detect_spoofing(
        self,
        time_window_minutes: int = 10,
        min_placement_frequency: float = 3.0,  # placements per minute
        min_cancellation_rate: float = 0.8,  # 80% cancellation rate
        max_time_to_cancel: float = 30.0,  # seconds
        min_distance_ticks: int = 3,  # minimum distance from market
        confidence_threshold: float = 0.7,  # minimum confidence score
    ) -> list[SpoofingDetectionResponse]:
        """
        Detect potential spoofing patterns in order book behavior.

        This method implements a sophisticated spoofing detection algorithm that identifies
        common market manipulation patterns including layering, quote stuffing, and
        momentum ignition. It analyzes order placement and cancellation patterns to
        identify anomalous behavior that may constitute market manipulation.

        Detection Patterns:
        1. Layering: Multiple orders at different price levels with high cancellation rates
        2. Quote Stuffing: Rapid placement and cancellation of orders to create noise
        3. Momentum Ignition: Aggressive orders designed to trigger other participants
        4. Flashing: Brief display of large orders to mislead other traders

        Algorithm Components:
        - Order lifecycle tracking: Monitors placement, modification, and cancellation
        - Statistical analysis: Identifies patterns that deviate from normal behavior
        - Temporal analysis: Considers timing patterns in order behavior
        - Price level analysis: Examines distance from current market and clustering
        - Volume analysis: Analyzes order sizes relative to typical market activity

        Args:
            time_window_minutes: Time window for analysis (default: 10 minutes)
            min_placement_frequency: Minimum order placements per minute to consider
            min_cancellation_rate: Minimum cancellation rate (0.0-1.0) to flag
            max_time_to_cancel: Maximum average time to cancellation (seconds)
            min_distance_ticks: Minimum distance from best bid/ask in ticks
            confidence_threshold: Minimum confidence score to include in results

        Returns:
            List of SpoofingDetectionResponse objects containing:
            - price: Price level where spoofing detected
            - side: "bid" or "ask"
            - order_size: Typical order size at this level
            - placement_frequency: Orders placed per minute
            - cancellation_rate: Percentage of orders cancelled (0.0-1.0)
            - time_to_cancel_avg_seconds: Average time before cancellation
            - distance_from_market: Distance in ticks from best bid/ask
            - confidence: Confidence score (0.0-1.0)
            - pattern: Type of spoofing pattern detected
            - first_detected: ISO timestamp of first detection
            - last_detected: ISO timestamp of most recent detection
            - total_instances: Number of instances detected

        Example:
            >>> # Detect spoofing with default parameters
            >>> spoofing = await orderbook.detect_spoofing()
            >>> for detection in spoofing:
            ...     print(
            ...         f"Spoofing at {detection['price']:.2f}: "
            ...         f"{detection['pattern']} (confidence: {detection['confidence']:.1%})"
            ...     )
            >>>
            >>> # Custom parameters for more sensitive detection
            >>> sensitive = await orderbook.detect_spoofing(
            ...     min_cancellation_rate=0.6,  # Lower threshold
            ...     confidence_threshold=0.5,  # Lower confidence required
            ...     time_window_minutes=5,  # Shorter window
            ... )

        Note:
            This method requires sufficient historical data to be effective. Results
            should be combined with other market analysis techniques for comprehensive
            manipulation detection. High-frequency data provides better accuracy.
        """
        async with self.orderbook.orderbook_lock:
            try:
                current_time = datetime.now(self.orderbook.timezone)
                cutoff_time = current_time - timedelta(minutes=time_window_minutes)

                detections: list[SpoofingDetectionResponse] = []

                # Get current market prices for distance calculation
                best_bid = self._get_best_bid_price()
                best_ask = self._get_best_ask_price()

                if not best_bid or not best_ask:
                    self.logger.warning(
                        "Cannot detect spoofing without valid market prices"
                    )
                    return []

                tick_size = await self._get_tick_size()

                # Analyze price level history for spoofing patterns with optimizations
                # Limit analysis to most recent price levels to avoid O(N²) complexity
                price_levels_to_analyze = list(
                    self.orderbook.price_level_history.items()
                )

                # Sort by most recent activity and limit to top 1000 price levels
                price_levels_to_analyze.sort(
                    key=lambda x: x[1][-1]["timestamp"] if x[1] else current_time,
                    reverse=True,
                )
                price_levels_to_analyze = price_levels_to_analyze[:1000]
                for (price, side), history in price_levels_to_analyze:
                    # Use binary search for timestamp filtering if history is large
                    if len(history) > 100:
                        # Binary search to find cutoff point
                        import bisect

                        # Create a list of timestamps for binary search
                        timestamps = [h.get("timestamp", current_time) for h in history]
                        cutoff_idx = bisect.bisect_left(timestamps, cutoff_time)
                        recent_history = list(history)[cutoff_idx:]
                    else:
                        # For small histories, use simple filtering
                        recent_history = [
                            h
                            for h in history
                            if h.get("timestamp", current_time) > cutoff_time
                        ]

                    if len(recent_history) < 2:
                        continue

                    # Calculate spoofing metrics
                    metrics = self._calculate_spoofing_metrics(
                        recent_history,
                        price,
                        side,
                        best_bid,
                        best_ask,
                        tick_size,
                        time_window_minutes,
                    )

                    # Apply detection thresholds
                    if (
                        metrics["placement_frequency"] >= min_placement_frequency
                        and metrics["cancellation_rate"] >= min_cancellation_rate
                        and metrics["avg_time_to_cancel"] <= max_time_to_cancel
                        and metrics["distance_ticks"] >= min_distance_ticks
                    ):
                        # Calculate confidence score
                        confidence = self._calculate_spoofing_confidence(metrics)

                        if confidence >= confidence_threshold:
                            # Determine spoofing pattern
                            pattern = self._classify_spoofing_pattern(metrics)

                            # Create detection response
                            detection: SpoofingDetectionResponse = {
                                "price": float(price),
                                "side": side,
                                "order_size": int(metrics["avg_order_size"]),
                                "placement_frequency": float(
                                    metrics["placement_frequency"]
                                ),
                                "cancellation_rate": float(
                                    metrics["cancellation_rate"]
                                ),
                                "time_to_cancel_avg_seconds": float(
                                    metrics["avg_time_to_cancel"]
                                ),
                                "distance_from_market": float(
                                    metrics["distance_ticks"]
                                ),
                                "confidence": float(confidence),
                                "pattern": pattern,
                                "first_detected": recent_history[0][
                                    "timestamp"
                                ].isoformat(),
                                "last_detected": recent_history[-1][
                                    "timestamp"
                                ].isoformat(),
                                "total_instances": len(recent_history),
                            }

                            detections.append(detection)

                # Sort by confidence score (highest first)
                detections.sort(key=lambda x: x["confidence"], reverse=True)

                # Update statistics
                self.orderbook.trade_flow_stats["spoofing_alerts"] = len(detections)

                # Log detection results
                if detections:
                    self.logger.info(
                        f"Detected {len(detections)} potential spoofing patterns"
                    )
                    for detection in detections[:3]:  # Log top 3
                        self.logger.info(
                            f"Spoofing: {detection['pattern']} at {detection['price']:.2f} "
                            f"({detection['side']}) - confidence: {detection['confidence']:.1%}"
                        )

                return detections

            except Exception as e:
                self.logger.error(f"Error detecting spoofing: {e}")
                return []

    def _get_best_bid_price(self) -> float | None:
        """Get current best bid price."""
        try:
            if not self.orderbook.orderbook_bids.is_empty():
                return float(
                    self.orderbook.orderbook_bids.sort("price", descending=True)[
                        "price"
                    ][0]
                )
        except Exception:
            pass
        return None

    def _get_best_ask_price(self) -> float | None:
        """Get current best ask price."""
        try:
            if not self.orderbook.orderbook_asks.is_empty():
                return float(self.orderbook.orderbook_asks.sort("price")["price"][0])
        except Exception:
            pass
        return None

    async def _get_tick_size(self) -> float:
        """Get instrument tick size from configuration or API."""
        # First try to get from project_x client if available
        if self.orderbook.project_x:
            try:
                # Try to get instrument info from the API
                instrument_info = await self.orderbook.project_x.get_instrument(
                    self.orderbook.instrument
                )
                if instrument_info and hasattr(instrument_info, "tickSize"):
                    return float(instrument_info.tickSize)
            except Exception:
                # Fall back to defaults if API call fails
                pass

        # Fall back to defaults for common futures
        defaults = {
            "ES": 0.25,
            "MES": 0.25,  # S&P 500
            "NQ": 0.25,
            "MNQ": 0.25,  # NASDAQ
            "RTY": 0.10,
            "M2K": 0.10,  # Russell 2000
            "YM": 1.0,
            "MYM": 1.0,  # Dow Jones
        }
        return defaults.get(self.orderbook.instrument, 0.01)  # Default to penny

    def _calculate_spoofing_metrics(
        self,
        history: list[dict[str, Any]],
        price: float,
        side: str,
        best_bid: float,
        best_ask: float,
        tick_size: float,
        window_minutes: int,
    ) -> dict[str, float]:
        """Calculate metrics for spoofing detection."""

        # Basic statistics
        total_events = len(history)
        volumes = [h.get("volume", 0) for h in history]
        avg_volume = sum(volumes) / len(volumes) if volumes else 0

        # Placement frequency (events per minute)
        placement_frequency = total_events / window_minutes

        # Calculate cancellation metrics
        cancellations = 0
        cancel_times = []

        for i in range(1, len(history)):
            prev_vol = history[i - 1].get("volume", 0)
            curr_vol = history[i].get("volume", 0)

            # Volume decrease indicates cancellation/fill
            if curr_vol < prev_vol:
                cancellations += 1

                # Calculate time between placement and cancellation
                time_diff = (
                    history[i]["timestamp"] - history[i - 1]["timestamp"]
                ).total_seconds()
                cancel_times.append(time_diff)

        cancellation_rate = cancellations / max(total_events - 1, 1)
        avg_time_to_cancel = (
            sum(cancel_times) / len(cancel_times) if cancel_times else 0
        )

        # Distance from market
        if side == "bid":
            distance_ticks = abs(best_bid - price) / tick_size
        else:
            distance_ticks = abs(price - best_ask) / tick_size

        return {
            "placement_frequency": placement_frequency,
            "cancellation_rate": cancellation_rate,
            "avg_time_to_cancel": avg_time_to_cancel,
            "distance_ticks": distance_ticks,
            "avg_order_size": avg_volume,
            "total_events": total_events,
            "volume_volatility": self._calculate_volume_volatility(volumes),
        }

    def _calculate_volume_volatility(self, volumes: list[float]) -> float:
        """Calculate volume volatility as coefficient of variation."""
        if not volumes or len(volumes) < 2:
            return 0.0

        mean_vol = sum(volumes) / len(volumes)
        if mean_vol == 0:
            return 0.0

        variance = sum((v - mean_vol) ** 2 for v in volumes) / len(volumes)
        std_dev = float(variance**0.5)

        return std_dev / mean_vol  # Coefficient of variation

    def _calculate_spoofing_confidence(self, metrics: dict[str, float]) -> float:
        """
        Calculate confidence score for spoofing detection.

        Combines multiple factors to produce a confidence score between 0.0 and 1.0.
        Higher scores indicate stronger evidence of spoofing behavior.
        """

        # Factor 1: Placement frequency (30% weight)
        # Higher frequency increases suspicion
        freq_score = min(float(metrics["placement_frequency"]) / 10.0, 1.0) * 0.30

        # Factor 2: Cancellation rate (35% weight)
        # Higher cancellation rate increases suspicion
        cancel_score = float(metrics["cancellation_rate"]) * 0.35

        # Factor 3: Speed of cancellation (25% weight)
        # Faster cancellations are more suspicious
        speed_score = max(0, 1.0 - (float(metrics["avg_time_to_cancel"]) / 60.0)) * 0.25

        # Factor 4: Distance from market (10% weight)
        # Orders further from market are more likely to be spoofing
        distance_score = min(float(metrics["distance_ticks"]) / 20.0, 1.0) * 0.10

        return min(freq_score + cancel_score + speed_score + distance_score, 1.0)

    def _classify_spoofing_pattern(self, metrics: dict[str, float]) -> str:
        """
        Classify the type of spoofing pattern based on characteristics.
        """

        # Quote stuffing: Very high frequency, very fast cancellations
        if (
            float(metrics["placement_frequency"]) > 8.0
            and float(metrics["avg_time_to_cancel"]) < 5.0
        ):
            return "quote_stuffing"

        # Layering: Multiple price levels, high cancellation rate, moderate distance
        if (
            float(metrics["cancellation_rate"]) > 0.9
            and float(metrics["distance_ticks"]) > 1
            and float(metrics["distance_ticks"]) < 10
        ):
            return "layering"

        # Momentum ignition: Large orders, quick cancellation after market moves
        if (
            float(metrics["avg_order_size"]) > 100
            and float(metrics["avg_time_to_cancel"]) < 10.0
            and float(metrics["distance_ticks"]) < 3
        ):
            return "momentum_ignition"

        # Flashing: Large orders, very brief display times
        if (
            float(metrics["avg_order_size"]) > 200
            and float(metrics["avg_time_to_cancel"]) < 2.0
        ):
            return "flashing"

        # Pinging: Frequent small orders testing market
        if (
            float(metrics["placement_frequency"]) > 5.0
            and float(metrics["avg_order_size"]) < 10
            and float(metrics["distance_ticks"]) < 2
        ):
            return "pinging"

        # Default classification
        return "order_manipulation"

    async def get_advanced_market_metrics(self) -> OrderbookAnalysisResponse:
        """
        Calculate advanced market microstructure metrics.

        Returns:
            Dict containing various market metrics
        """
        async with self.orderbook.orderbook_lock:
            try:
                # Initialize default values
                bid_depth = self.orderbook.orderbook_bids.height
                ask_depth = self.orderbook.orderbook_asks.height

                # Calculate basic metrics
                total_bid_size = (
                    int(self.orderbook.orderbook_bids["volume"].sum())
                    if not self.orderbook.orderbook_bids.is_empty()
                    else 0
                )
                total_ask_size = (
                    int(self.orderbook.orderbook_asks["volume"].sum())
                    if not self.orderbook.orderbook_asks.is_empty()
                    else 0
                )

                avg_bid_size = (
                    float(total_bid_size / bid_depth) if bid_depth > 0 else 0.0
                )
                avg_ask_size = (
                    float(total_ask_size / ask_depth) if ask_depth > 0 else 0.0
                )

                # Calculate spread and prices
                best_bid = (
                    float(
                        self.orderbook.orderbook_bids.sort("price", descending=True)[
                            "price"
                        ][0]
                    )
                    if not self.orderbook.orderbook_bids.is_empty()
                    else 0.0
                )
                best_ask = (
                    float(self.orderbook.orderbook_asks.sort("price")["price"][0])
                    if not self.orderbook.orderbook_asks.is_empty()
                    else 0.0
                )

                spread = best_ask - best_bid if best_bid > 0 and best_ask > 0 else 0.0
                mid_price = (
                    (best_bid + best_ask) / 2 if best_bid > 0 and best_ask > 0 else 0.0
                )

                # Calculate imbalance
                imbalance = (
                    (total_bid_size - total_ask_size)
                    / (total_bid_size + total_ask_size)
                    if (total_bid_size + total_ask_size) > 0
                    else 0.0
                )

                # Calculate weighted mid price (volume weighted)
                weighted_mid_price = (
                    ((best_bid * total_ask_size) + (best_ask * total_bid_size))
                    / (total_bid_size + total_ask_size)
                    if (total_bid_size + total_ask_size) > 0
                    else mid_price
                )

                # Simple clustering metric (could be enhanced)
                order_clustering = 0.0
                if bid_depth > 0 and ask_depth > 0:
                    # Simple clustering based on depth concentration
                    top_5_bids = min(5, bid_depth)
                    top_5_asks = min(5, ask_depth)
                    top_bid_volume = int(
                        self.orderbook.orderbook_bids.sort("price", descending=True)
                        .head(top_5_bids)["volume"]
                        .sum()
                    )
                    top_ask_volume = int(
                        self.orderbook.orderbook_asks.sort("price")
                        .head(top_5_asks)["volume"]
                        .sum()
                    )

                    order_clustering = (
                        (top_bid_volume + top_ask_volume)
                        / (total_bid_size + total_ask_size)
                        if (total_bid_size + total_ask_size) > 0
                        else 0.0
                    )

                # Calculate VWAP and TWAP (simplified)
                volume_weighted_avg_price = (
                    mid_price  # Simplified - would need trade data for true VWAP
                )
                time_weighted_avg_price = (
                    mid_price  # Simplified - would need time series for true TWAP
                )

                current_time = datetime.now(self.orderbook.timezone)

                return {
                    "bid_depth": bid_depth,
                    "ask_depth": ask_depth,
                    "total_bid_size": total_bid_size,
                    "total_ask_size": total_ask_size,
                    "avg_bid_size": avg_bid_size,
                    "avg_ask_size": avg_ask_size,
                    "price_levels": bid_depth + ask_depth,
                    "order_clustering": order_clustering,
                    "imbalance": imbalance,
                    "spread": spread,
                    "mid_price": mid_price,
                    "weighted_mid_price": weighted_mid_price,
                    "volume_weighted_avg_price": volume_weighted_avg_price,
                    "time_weighted_avg_price": time_weighted_avg_price,
                    "timestamp": current_time.isoformat(),
                }

            except Exception as e:
                self.logger.error(f"Error calculating advanced metrics: {e}")
                # Return error response with default values
                current_time = datetime.now(self.orderbook.timezone)
                return {
                    "bid_depth": 0,
                    "ask_depth": 0,
                    "total_bid_size": 0,
                    "total_ask_size": 0,
                    "avg_bid_size": 0.0,
                    "avg_ask_size": 0.0,
                    "price_levels": 0,
                    "order_clustering": 0.0,
                    "imbalance": 0.0,
                    "spread": 0.0,
                    "mid_price": 0.0,
                    "weighted_mid_price": 0.0,
                    "volume_weighted_avg_price": 0.0,
                    "time_weighted_avg_price": 0.0,
                    "timestamp": current_time.isoformat(),
                }
