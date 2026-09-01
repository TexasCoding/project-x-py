"""
Async-first statistics system for ProjectX SDK.

This module provides comprehensive statistics tracking, aggregation, and export
capabilities for all SDK components with 100% async architecture.

Author: SDK v4.0.0
Date: 2025-01-21

Key Components:
    - BaseStatisticsTracker: Core async statistics tracking
    - ComponentCollector: Component-specific statistics collection
    - StatisticsAggregator: Parallel statistics aggregation
    - HealthMonitor: Health scoring and monitoring
    - StatsExporter: Multiple export format support

Example:
    ```python
    from project_x_py import TradingSuite

    suite = await TradingSuite.create("MNQ")

    # Get comprehensive statistics
    stats = await suite.get_stats()
    print(f"Health Score: {stats['health_score']}")

    # Export to different formats
    prometheus_metrics = await suite.export_stats("prometheus")
    ```
"""

from project_x_py.statistics.aggregator import StatisticsAggregator
from project_x_py.statistics.base import BaseStatisticsTracker, StatisticsProvider
from project_x_py.statistics.bounded_statistics import (
    BoundedCounter,
    BoundedStatisticsMixin,
    BoundedStatisticsProvider,
    CircularBuffer,
    CleanupScheduler,
)
from project_x_py.statistics.collector import ComponentCollector
from project_x_py.statistics.export import StatsExporter
from project_x_py.statistics.health import HealthMonitor

__all__ = [
    "BaseStatisticsTracker",
    "StatisticsProvider",
    "ComponentCollector",
    "StatisticsAggregator",
    "HealthMonitor",
    "StatsExporter",
    # Bounded statistics components
    "BoundedCounter",
    "BoundedStatisticsMixin",
    "BoundedStatisticsProvider",
    "CircularBuffer",
    "CleanupScheduler",
]

__version__ = "4.2.0"
