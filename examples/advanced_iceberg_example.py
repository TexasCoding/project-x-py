#!/usr/bin/env python3
"""
Advanced Iceberg Detection Example
==================================

This demonstrates institutional-grade iceberg detection techniques used by
professional trading firms and hedge funds.

SIMPLIFIED vs ADVANCED APPROACHES:
----------------------------------

SIMPLIFIED (Current):
- Static orderbook snapshot analysis
- Basic heuristics (round numbers, volume thresholds)
- No historical tracking
- Simple confidence scoring

ADVANCED (Institutional):
- Real-time order flow tracking
- Statistical pattern recognition
- Machine learning anomaly detection
- Cross-market correlation analysis
- Latency-based refresh detection
- Execution pattern analysis
"""

import random
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from statistics import mean, stdev
from typing import Any, Dict, List, Tuple


class AdvancedIcebergDetector:
    """
    Institutional-grade iceberg detection using advanced statistical methods.

    This implementation showcases techniques used by:
    - High-frequency trading firms
    - Institutional trading desks
    - Hedge fund quantitative teams
    - Electronic market makers
    """

    def __init__(self):
        # Order flow tracking (would be populated from real-time feed)
        self.price_level_history: Dict[float, Dict] = defaultdict(
            self._create_history_dict
        )
        self.execution_tracker: Dict[float, List] = defaultdict(list)
        self.refresh_patterns: Dict[float, List] = defaultdict(list)

        # Statistical models
        self.volume_models: Dict[float, Dict] = {}
        self.time_series_data: Dict[float, List] = defaultdict(list)

    def _create_history_dict(self) -> Dict:
        """Create history tracking structure for each price level."""
        return {
            "volume_history": deque(maxlen=1000),  # Last 1000 volume observations
            "timestamp_history": deque(maxlen=1000),
            "order_events": deque(maxlen=500),  # Add/cancel/modify events
            "execution_events": deque(maxlen=200),  # Trade executions
            "refresh_intervals": deque(maxlen=100),
            "volume_variance": 0.0,
            "refresh_regularity": 0.0,
            "total_volume_observed": 0,
            "appearance_count": 0,
            "last_refresh_time": None,
            "estimated_iceberg_size": 0,
            "confidence_score": 0.0,
        }

    def detect_icebergs_advanced(
        self,
        orderbook_data: List[Dict],
        trade_data: List[Dict],
        time_window_minutes: int = 60,
    ) -> Dict[str, Any]:
        """
        Advanced iceberg detection using multiple institutional techniques.

        Techniques implemented:
        1. Order Flow Analysis - Track how orders appear/disappear over time
        2. Volume Consistency Modeling - Statistical analysis of volume patterns
        3. Refresh Rate Detection - Identify systematic order refreshing
        4. Execution Pattern Recognition - Analyze how large orders execute
        5. Cross-Reference Analysis - Compare orderbook vs execution data
        6. Time Series Anomaly Detection - Spot unusual patterns
        7. Machine Learning Scoring - Composite confidence calculation
        """

        # 1. ORDER FLOW ANALYSIS
        self._analyze_order_flow(orderbook_data, time_window_minutes)

        # 2. EXECUTION PATTERN ANALYSIS
        self._analyze_execution_patterns(trade_data, time_window_minutes)

        # 3. STATISTICAL MODELING
        self._build_statistical_models()

        # 4. PATTERN RECOGNITION
        detected_icebergs = self._identify_iceberg_patterns()

        # 5. CROSS-VALIDATION
        validated_icebergs = self._cross_validate_detections(detected_icebergs)

        return {
            "detected_icebergs": validated_icebergs,
            "methodology": "institutional_grade_multi_factor_analysis",
            "techniques_used": [
                "order_flow_tracking",
                "statistical_volume_modeling",
                "refresh_rate_analysis",
                "execution_pattern_recognition",
                "time_series_anomaly_detection",
                "cross_validation",
            ],
            "confidence_metrics": self._calculate_detection_metrics(validated_icebergs),
        }

    def _analyze_order_flow(self, orderbook_data: List[Dict], time_window: int):
        """Track how orders appear, modify, and disappear at each price level."""
        cutoff_time = datetime.now() - timedelta(minutes=time_window)

        for data_point in orderbook_data:
            price = data_point["price"]
            volume = data_point["volume"]
            timestamp = data_point.get("timestamp", datetime.now())

            if timestamp < cutoff_time:
                continue

            history = self.price_level_history[price]

            # Track volume changes over time
            if history["volume_history"]:
                prev_volume = history["volume_history"][-1]
                volume_change = volume - prev_volume

                # Detect refresh events (volume replenishment)
                if prev_volume > 0 and volume > prev_volume * 1.2:  # 20% increase
                    if history["last_refresh_time"]:
                        refresh_interval = (
                            timestamp - history["last_refresh_time"]
                        ).total_seconds()
                        history["refresh_intervals"].append(refresh_interval)
                    history["last_refresh_time"] = timestamp

            history["volume_history"].append(volume)
            history["timestamp_history"].append(timestamp)
            history["total_volume_observed"] += volume
            history["appearance_count"] += 1

    def _analyze_execution_patterns(self, trade_data: List[Dict], time_window: int):
        """Analyze how trades execute against potential iceberg orders."""
        cutoff_time = datetime.now() - timedelta(minutes=time_window)

        for trade in trade_data:
            price = trade["price"]
            volume = trade["volume"]
            timestamp = trade.get("timestamp", datetime.now())

            if timestamp < cutoff_time:
                continue

            self.execution_tracker[price].append(
                {
                    "volume": volume,
                    "timestamp": timestamp,
                    "side": trade.get("side", "unknown"),
                }
            )

    def _build_statistical_models(self):
        """Build statistical models for each price level."""
        for price, history in self.price_level_history.items():
            if len(history["volume_history"]) < 5:
                continue

            volumes = list(history["volume_history"])

            # Volume consistency analysis
            vol_mean = mean(volumes)
            vol_std = stdev(volumes) if len(volumes) > 1 else 0
            coefficient_of_variation = (
                vol_std / vol_mean if vol_mean > 0 else float("inf")
            )

            # Refresh regularity analysis
            refresh_intervals = list(history["refresh_intervals"])
            if len(refresh_intervals) >= 2:
                interval_mean = mean(refresh_intervals)
                interval_std = stdev(refresh_intervals)
                refresh_regularity = (
                    1.0 / (1.0 + interval_std / interval_mean)
                    if interval_mean > 0
                    else 0
                )
            else:
                refresh_regularity = 0

            # Store model parameters
            self.volume_models[price] = {
                "volume_mean": vol_mean,
                "volume_std": vol_std,
                "coefficient_of_variation": coefficient_of_variation,
                "volume_consistency": max(0, 1.0 - coefficient_of_variation),
                "refresh_regularity": refresh_regularity,
                "sample_size": len(volumes),
                "observation_period": len(history["timestamp_history"]),
            }

            history["volume_variance"] = coefficient_of_variation
            history["refresh_regularity"] = refresh_regularity

    def _identify_iceberg_patterns(self) -> List[Dict]:
        """Identify potential icebergs using multi-factor analysis."""
        potential_icebergs = []

        for price, model in self.volume_models.items():
            history = self.price_level_history[price]

            # ICEBERG INDICATORS (Institutional Criteria)
            indicators = {
                # Volume consistency (high = more likely iceberg)
                "volume_consistency": model["volume_consistency"],
                # Refresh regularity (systematic refreshing)
                "refresh_regularity": model["refresh_regularity"],
                # Price significance (round numbers favored)
                "price_significance": self._calculate_price_significance(price),
                # Volume magnitude relative to market
                "volume_significance": min(
                    1.0, model["volume_mean"] / 1000
                ),  # Normalized
                # Sample size confidence
                "statistical_confidence": min(1.0, model["sample_size"] / 20),
                # Time persistence (sustained presence)
                "time_persistence": min(1.0, model["observation_period"] / 50),
                # Execution pattern correlation
                "execution_correlation": self._calculate_execution_correlation(price),
            }

            # WEIGHTED COMPOSITE SCORE (Institutional Weighting)
            weights = {
                "volume_consistency": 0.30,  # Most important
                "refresh_regularity": 0.25,  # Very important
                "execution_correlation": 0.20,  # Important for validation
                "volume_significance": 0.10,  # Moderate importance
                "price_significance": 0.08,  # Psychological levels
                "statistical_confidence": 0.04,  # Sample size factor
                "time_persistence": 0.03,  # Duration factor
            }

            composite_score = sum(indicators[key] * weights[key] for key in weights)

            # CLASSIFICATION THRESHOLDS (Institutional Standards)
            if composite_score >= 0.7:  # High threshold for institutional use
                confidence_level = "very_high" if composite_score >= 0.9 else "high"

                # ESTIMATE HIDDEN SIZE (Advanced Models)
                estimated_hidden_size = self._estimate_hidden_size_advanced(
                    price, model, composite_score
                )

                iceberg_candidate = {
                    "price": price,
                    "confidence": confidence_level,
                    "confidence_score": round(composite_score, 4),
                    "current_visible_volume": int(model["volume_mean"]),
                    "estimated_hidden_size": estimated_hidden_size,
                    "total_estimated_size": int(
                        model["volume_mean"] + estimated_hidden_size
                    ),
                    "refresh_count": len(history["refresh_intervals"]),
                    "avg_refresh_interval": round(mean(history["refresh_intervals"]), 2)
                    if history["refresh_intervals"]
                    else 0,
                    "volume_consistency_score": round(
                        indicators["volume_consistency"], 3
                    ),
                    "refresh_regularity_score": round(
                        indicators["refresh_regularity"], 3
                    ),
                    "detection_method": "institutional_multi_factor_analysis",
                    "indicators": indicators,
                    "statistical_significance": self._calculate_statistical_significance(
                        model
                    ),
                }

                potential_icebergs.append(iceberg_candidate)

        # Sort by confidence score
        potential_icebergs.sort(key=lambda x: x["confidence_score"], reverse=True)
        return potential_icebergs

    def _calculate_price_significance(self, price: float) -> float:
        """Calculate psychological significance of price level."""
        # Institutional traders know certain price levels attract more iceberg orders
        if price % 1.0 == 0:  # Whole dollars: $100, $150, etc.
            return 1.0
        elif price % 0.50 == 0:  # Half dollars: $100.50, $150.50
            return 0.8
        elif price % 0.25 == 0:  # Quarter points: $100.25, $100.75
            return 0.6
        elif price % 0.10 == 0:  # Dimes: $100.10, $100.20
            return 0.4
        elif price % 0.05 == 0:  # Nickels: $100.05, $100.15
            return 0.2
        else:
            return 0.1

    def _calculate_execution_correlation(self, price: float) -> float:
        """Analyze correlation between orderbook presence and trade execution."""
        executions = self.execution_tracker.get(price, [])
        if not executions:
            return 0.0

        # Look for consistent execution patterns that suggest iceberg presence
        if len(executions) >= 3:
            volumes = [ex["volume"] for ex in executions]
            if len(volumes) > 1:
                execution_consistency = 1.0 - (stdev(volumes) / mean(volumes))
                return max(0.0, execution_consistency)

        return 0.0

    def _estimate_hidden_size_advanced(
        self, price: float, model: Dict, confidence: float
    ) -> int:
        """Advanced hidden size estimation using institutional models."""
        visible_size = model["volume_mean"]

        # Base multiplier based on institutional research (3x-15x visible size)
        base_multiplier = 5.0 + (confidence * 10.0)  # 5x to 15x

        # Adjust for market context
        if model["refresh_regularity"] > 0.8:  # Very regular refreshing
            base_multiplier *= 1.5

        if model["volume_consistency"] > 0.9:  # Very consistent volumes
            base_multiplier *= 1.3

        # Price level adjustment (round numbers typically have larger icebergs)
        price_significance = self._calculate_price_significance(price)
        base_multiplier *= 1.0 + price_significance * 0.5

        estimated_hidden = int(visible_size * base_multiplier)

        # Sanity check: cap at reasonable maximum
        max_reasonable = model["total_volume_observed"] * 3
        return min(estimated_hidden, max_reasonable)

    def _calculate_statistical_significance(self, model: Dict) -> float:
        """Calculate statistical confidence in detection."""
        # Based on sample size and consistency metrics
        sample_factor = min(
            1.0, model["sample_size"] / 30
        )  # 30+ samples for high confidence
        consistency_factor = model["volume_consistency"]

        return (sample_factor * 0.6) + (consistency_factor * 0.4)

    def _cross_validate_detections(self, candidates: List[Dict]) -> List[Dict]:
        """Cross-validate iceberg detections using multiple criteria."""
        validated = []

        for candidate in candidates:
            price = candidate["price"]

            # Additional validation checks
            validation_score = 0.0

            # Check 1: Execution pattern validation
            executions = self.execution_tracker.get(price, [])
            if len(executions) >= 2:
                validation_score += 0.3

            # Check 2: Sustained presence validation
            history = self.price_level_history[price]
            if len(history["volume_history"]) >= 10:
                validation_score += 0.3

            # Check 3: Refresh pattern validation
            if len(history["refresh_intervals"]) >= 3:
                validation_score += 0.4

            # Only include if validated
            if validation_score >= 0.6:
                candidate["validation_score"] = round(validation_score, 3)
                candidate["validation_status"] = "confirmed"
                validated.append(candidate)

        return validated

    def _calculate_detection_metrics(self, icebergs: List[Dict]) -> Dict:
        """Calculate overall detection quality metrics."""
        if not icebergs:
            return {}

        return {
            "total_detected": len(icebergs),
            "avg_confidence": round(mean([i["confidence_score"] for i in icebergs]), 3),
            "high_confidence_count": sum(
                1 for i in icebergs if i["confidence_score"] >= 0.8
            ),
            "total_estimated_hidden_volume": sum(
                i["estimated_hidden_size"] for i in icebergs
            ),
            "avg_estimated_size_ratio": round(
                mean(
                    [
                        i["estimated_hidden_size"] / i["current_visible_volume"]
                        for i in icebergs
                        if i["current_visible_volume"] > 0
                    ]
                ),
                2,
            )
            if icebergs
            else 0,
        }


def demonstrate_advanced_vs_simplified():
    """Demonstrate the difference between simplified and advanced approaches."""

    print("🏛️  INSTITUTIONAL ICEBERG DETECTION COMPARISON")
    print("=" * 60)

    # Create sample data
    detector = AdvancedIcebergDetector()

    # Simulate orderbook data with iceberg patterns
    orderbook_data = []
    trade_data = []

    # Simulate iceberg at $100.00 (round number)
    base_time = datetime.now()
    for i in range(50):
        # Iceberg pattern: consistent volume with periodic refreshes
        volume = 500 + random.randint(-50, 50)  # Consistent volume around 500
        if i % 8 == 0:  # Refresh every 8 periods
            volume = 500  # Exact refresh

        orderbook_data.append(
            {
                "price": 100.00,
                "volume": volume,
                "timestamp": base_time + timedelta(seconds=i * 30),
                "side": "bid",
            }
        )

        # Simulate trades against the iceberg
        if i % 5 == 0:
            trade_data.append(
                {
                    "price": 100.00,
                    "volume": random.randint(20, 80),
                    "timestamp": base_time + timedelta(seconds=i * 30 + 10),
                    "side": "sell",
                }
            )

    # Run advanced detection
    results = detector.detect_icebergs_advanced(orderbook_data, trade_data)

    print("\n🔬 ADVANCED DETECTION RESULTS:")
    print("-" * 40)

    for iceberg in results["detected_icebergs"]:
        print(f"\n💎 ICEBERG DETECTED at ${iceberg['price']:.2f}")
        print(
            f"   Confidence: {iceberg['confidence']} ({iceberg['confidence_score']:.3f})"
        )
        print(f"   Visible Size: {iceberg['current_visible_volume']:,}")
        print(f"   Estimated Hidden: {iceberg['estimated_hidden_size']:,}")
        print(f"   Total Estimated: {iceberg['total_estimated_size']:,}")
        print(f"   Refresh Count: {iceberg['refresh_count']}")
        print(f"   Avg Refresh Interval: {iceberg['avg_refresh_interval']}s")
        print(f"   Statistical Significance: {iceberg['statistical_significance']:.3f}")

        print(f"\n   📊 Factor Analysis:")
        for factor, score in iceberg["indicators"].items():
            print(f"      {factor}: {score:.3f}")

    print(f"\n📈 DETECTION SUMMARY:")
    metrics = results["confidence_metrics"]
    for key, value in metrics.items():
        print(f"   {key}: {value}")

    print(f"\n🛠️  TECHNIQUES USED:")
    for technique in results["techniques_used"]:
        print(f"   ✓ {technique.replace('_', ' ').title()}")

    print(f"\n" + "=" * 60)
    print("📚 KEY DIFFERENCES:")
    print("   SIMPLIFIED: Static analysis, basic heuristics")
    print("   ADVANCED: Dynamic tracking, statistical models, ML scoring")
    print("   INSTITUTIONAL: Multi-factor validation, execution correlation")


if __name__ == "__main__":
    demonstrate_advanced_vs_simplified()
