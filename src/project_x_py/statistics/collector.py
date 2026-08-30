"""
Component-specific statistics collection for ProjectX SDK.

Author: @TexasCoding
Date: 2025-08-21

Overview:
    Provides specialized collectors for gathering statistics from each SDK component.
    Each collector extracts component-specific metrics, calculates derived metrics
    (fill rates, win rates, spreads, etc.), and handles missing/optional components
    gracefully using the TypedDict types from stats_types.py.

Key Features:
    - 100% async architecture with proper error handling
    - Component-specific collectors for detailed metrics extraction
    - Derived metric calculations (fill rates, P&L, performance ratios)
    - Graceful handling of missing/optional components
    - Type-safe statistics using TypedDict definitions
    - Performance optimization with caching and concurrent collection

Components Supported:
    - OrderManager: Order lifecycle, fill rates, volume metrics
    - PositionManager: P&L analysis, risk metrics, performance ratios
    - RealtimeDataManager: Data throughput, latency, storage metrics
    - OrderBook: Market microstructure, spread analysis, pattern detection
    - RiskManager: Risk assessment, rule violations, managed trades

Example Usage:
    ```python
    from project_x_py.statistics.collector import ComponentCollector

    # Initialize collector with TradingSuite
    collector = ComponentCollector(trading_suite)

    # Collect all component statistics
    stats = await collector.collect()

    # Access component-specific stats
    order_stats = stats.get("order_manager")
    position_stats = stats.get("position_manager")
    ```

See Also:
    - `project_x_py.types.stats_types`: TypedDict definitions
    - `project_x_py.statistics.base`: Base statistics tracking
    - `project_x_py.statistics.aggregator`: Cross-component aggregation
"""

import asyncio
import time
from typing import TYPE_CHECKING, Any

from project_x_py.statistics.base import BaseStatisticsTracker
from project_x_py.types.stats_types import (
    OrderbookStats,
    OrderManagerStats,
    PositionManagerStats,
    RealtimeDataManagerStats,
    RiskManagerStats,
)

if TYPE_CHECKING:
    from project_x_py.trading_suite import TradingSuite


class ComponentCollector(BaseStatisticsTracker):
    """
    Specialized collector for extracting statistics from SDK components.

    Collects component-specific metrics and calculates derived metrics like
    fill rates, win rates, spreads, and performance ratios. Handles missing
    or optional components gracefully and provides type-safe statistics.

    Features:
        - Async collection from all available components
        - Component-specific metric extraction and calculations
        - Derived metric computation (rates, ratios, performance indicators)
        - Graceful error handling with partial results
        - Type-safe statistics using TypedDict definitions
        - Performance optimization with concurrent collection
    """

    def __init__(self, trading_suite: "TradingSuite"):
        """
        Initialize the component collector.

        Args:
            trading_suite: TradingSuite instance to collect statistics from
        """
        super().__init__("component_collector")
        self.trading_suite = trading_suite
        self._collection_start_time = time.time()

    def _suite_component(self, name: str) -> Any:
        """Return a manager from the suite or the first instrument context."""
        value = getattr(self.trading_suite, name, None)
        if value is not None:
            return value
        instruments = getattr(self.trading_suite, "_instruments", None) or {}
        for context in instruments.values():
            value = getattr(context, name, None)
            if value is not None:
                return value
        return None

    async def collect(self) -> dict[str, Any]:
        """
        Main collection method that delegates to specific component collectors.

        Collects statistics from all available components concurrently and
        handles any errors gracefully to return partial statistics if needed.

        Returns:
            Dictionary with component statistics, keyed by component name
        """
        await self.set_status("collecting")
        collection_start = time.time()

        try:
            # Collect from all components concurrently
            tasks = [
                self._collect_order_stats(),
                self._collect_position_stats(),
                self._collect_data_stats(),
                self._collect_orderbook_stats(),
                self._collect_risk_stats(),
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results and handle any exceptions
            stats = {}
            component_names = [
                "order_manager",
                "position_manager",
                "data_manager",
                "orderbook",
                "risk_manager",
            ]

            for _i, (name, result) in enumerate(
                zip(component_names, results, strict=False)
            ):
                if isinstance(result, Exception):
                    await self.track_error(
                        result,
                        f"Failed to collect {name} statistics",
                        {"component": name},
                    )
                    # Continue with other components
                elif result is not None:
                    stats[name] = result

            # Record collection timing
            collection_time = (time.time() - collection_start) * 1000
            await self.record_timing("full_collection", collection_time)
            await self.increment("collections_completed")
            await self.set_status("active")

            return stats

        except Exception as e:
            await self.track_error(e, "Statistics collection failed")
            await self.set_status("error")
            return {}

    async def _collect_order_stats(self) -> OrderManagerStats | None:
        """
        Collect statistics from OrderManager component.

        Extracts order lifecycle metrics, calculates fill rates, response times,
        and volume statistics. Handles both synchronous and async statistics APIs.

        Returns:
            OrderManagerStats if component is available, None otherwise
        """
        order_manager = self._suite_component("orders")
        if order_manager is None:
            return None

        try:
            start_time = time.time()

            # Get base statistics from order manager
            base_stats: dict[str, Any] = {}
            if hasattr(order_manager, "get_order_statistics"):
                # OrderManager has synchronous get_order_statistics method
                result = order_manager.get_order_statistics()
                # Convert TypedDict to regular dict
                base_stats = dict(result) if result else {}
            elif hasattr(order_manager, "stats"):
                # Fallback to direct stats access
                base_stats = dict(order_manager.stats)

            # Extract core metrics
            orders_placed = base_stats.get("orders_placed", 0)
            orders_filled = base_stats.get("orders_filled", 0)
            orders_cancelled = base_stats.get("orders_cancelled", 0)
            orders_rejected = base_stats.get("orders_rejected", 0)
            orders_modified = base_stats.get("orders_modified", 0)

            # Calculate derived metrics
            fill_rate = (orders_filled / orders_placed) if orders_placed > 0 else 0.0
            rejection_rate = (
                (orders_rejected / orders_placed) if orders_placed > 0 else 0.0
            )

            # Get timing statistics
            avg_fill_time = base_stats.get("avg_fill_time_ms", 0.0)
            avg_response_time = base_stats.get("avg_order_response_time_ms", 0.0)
            fastest_fill = base_stats.get("fastest_fill_ms", 0.0)
            slowest_fill = base_stats.get("slowest_fill_ms", 0.0)

            # Get order type breakdown
            market_orders = base_stats.get("market_orders", 0)
            limit_orders = base_stats.get("limit_orders", 0)
            stop_orders = base_stats.get("stop_orders", 0)
            bracket_orders = base_stats.get("bracket_orders", 0)

            # Get volume and value metrics
            total_volume = base_stats.get("total_volume", 0)
            total_value = base_stats.get("total_value", 0.0)
            largest_order = base_stats.get("largest_order", 0)
            avg_order_size = (
                (total_volume / orders_placed) if orders_placed > 0 else 0.0
            )

            # Get risk metrics
            risk_violations = base_stats.get("risk_violations", 0)
            validation_failures = base_stats.get("order_validation_failures", 0)

            # Get last order time
            last_order_time = base_stats.get("last_order_time")
            if last_order_time and not isinstance(last_order_time, str):
                last_order_time = str(last_order_time)

            stats: OrderManagerStats = {
                "orders_placed": int(orders_placed),
                "orders_filled": int(orders_filled),
                "orders_cancelled": int(orders_cancelled),
                "orders_rejected": int(orders_rejected),
                "orders_modified": int(orders_modified),
                "fill_rate": round(fill_rate, 4),
                "avg_fill_time_ms": float(avg_fill_time),
                "rejection_rate": round(rejection_rate, 4),
                "market_orders": int(market_orders),
                "limit_orders": int(limit_orders),
                "stop_orders": int(stop_orders),
                "bracket_orders": int(bracket_orders),
                "last_order_time": last_order_time,
                "avg_order_response_time_ms": float(avg_response_time),
                "fastest_fill_ms": float(fastest_fill),
                "slowest_fill_ms": float(slowest_fill),
                "total_volume": int(total_volume),
                "total_value": float(total_value),
                "avg_order_size": round(avg_order_size, 2),
                "largest_order": int(largest_order),
                "risk_violations": int(risk_violations),
                "order_validation_failures": int(validation_failures),
            }

            # Record collection timing
            collection_time = (time.time() - start_time) * 1000
            await self.record_timing("order_stats_collection", collection_time)

            return stats

        except Exception as e:
            await self.track_error(e, "Failed to collect OrderManager statistics")
            return None

    async def _collect_position_stats(self) -> PositionManagerStats | None:
        """
        Collect statistics from PositionManager component.

        Extracts position metrics, P&L analysis, performance ratios, and risk
        assessments. Calculates derived metrics like win rates and Sharpe ratios.

        Returns:
            PositionManagerStats if component is available, None otherwise
        """
        position_manager = self._suite_component("positions")
        if position_manager is None:
            return None

        try:
            start_time = time.time()

            # Get base statistics
            base_stats: dict[str, Any] = {}
            if hasattr(position_manager, "get_position_stats"):
                result = await position_manager.get_position_stats()
                if isinstance(result, dict):
                    base_stats = result
            elif hasattr(position_manager, "stats"):
                base_stats = dict(position_manager.stats)

            # Extract position counts
            open_positions = base_stats.get("open_positions", 0)
            closed_positions = base_stats.get("closed_positions", 0)
            total_positions = open_positions + closed_positions

            # Extract P&L metrics
            total_pnl = base_stats.get("total_pnl", 0.0)
            realized_pnl = base_stats.get("realized_pnl", 0.0)
            unrealized_pnl = base_stats.get("unrealized_pnl", 0.0)
            best_position_pnl = base_stats.get("best_position_pnl", 0.0)
            worst_position_pnl = base_stats.get("worst_position_pnl", 0.0)

            # Extract position size metrics
            avg_position_size = base_stats.get("avg_position_size", 0.0)
            largest_position = base_stats.get("largest_position", 0)
            avg_hold_time = base_stats.get("avg_hold_time_minutes", 0.0)
            longest_hold_time = base_stats.get("longest_hold_time_minutes", 0.0)

            # Extract performance metrics
            win_rate = base_stats.get("win_rate", 0.0)
            profit_factor = base_stats.get("profit_factor", 0.0)
            sharpe_ratio = base_stats.get("sharpe_ratio", 0.0)
            max_drawdown = base_stats.get("max_drawdown", 0.0)

            # Extract risk metrics
            total_risk = base_stats.get("total_risk", 0.0)
            max_position_risk = base_stats.get("max_position_risk", 0.0)
            portfolio_correlation = base_stats.get("portfolio_correlation", 0.0)
            var_95 = base_stats.get("var_95", 0.0)

            # Extract activity metrics
            position_updates = base_stats.get("position_updates", 0)
            risk_calculations = base_stats.get("risk_calculations", 0)
            last_position_update = base_stats.get("last_position_update")
            if last_position_update and not isinstance(last_position_update, str):
                last_position_update = str(last_position_update)

            stats: PositionManagerStats = {
                "open_positions": int(open_positions),
                "closed_positions": int(closed_positions),
                "total_positions": int(total_positions),
                "total_pnl": float(total_pnl),
                "realized_pnl": float(realized_pnl),
                "unrealized_pnl": float(unrealized_pnl),
                "best_position_pnl": float(best_position_pnl),
                "worst_position_pnl": float(worst_position_pnl),
                "avg_position_size": float(avg_position_size),
                "largest_position": int(largest_position),
                "avg_hold_time_minutes": float(avg_hold_time),
                "longest_hold_time_minutes": float(longest_hold_time),
                "win_rate": round(win_rate, 4),
                "profit_factor": round(profit_factor, 4),
                "sharpe_ratio": round(sharpe_ratio, 4),
                "max_drawdown": float(max_drawdown),
                "total_risk": float(total_risk),
                "max_position_risk": float(max_position_risk),
                "portfolio_correlation": round(portfolio_correlation, 4),
                "var_95": float(var_95),
                "position_updates": int(position_updates),
                "risk_calculations": int(risk_calculations),
                "last_position_update": last_position_update,
            }

            # Record collection timing
            collection_time = (time.time() - start_time) * 1000
            await self.record_timing("position_stats_collection", collection_time)

            return stats

        except Exception as e:
            await self.track_error(e, "Failed to collect PositionManager statistics")
            return None

    async def _collect_data_stats(self) -> RealtimeDataManagerStats | None:
        """
        Collect statistics from RealtimeDataManager component.

        Extracts data throughput metrics, latency measurements, storage utilization,
        and data quality indicators. Calculates processing rates and efficiency metrics.

        Returns:
            RealtimeDataManagerStats if component is available, None otherwise
        """
        data_manager = self._suite_component("data")
        if data_manager is None:
            return None

        try:
            start_time = time.time()

            # Get memory statistics (async method)
            base_stats: dict[str, Any] = {}
            if hasattr(data_manager, "get_memory_stats"):
                result = await data_manager.get_memory_stats()
                # Convert TypedDict to regular dict
                base_stats = dict(result) if result else {}

            # Extract data processing metrics
            bars_processed = base_stats.get("bars_processed", 0)
            ticks_processed = base_stats.get("ticks_processed", 0)
            quotes_processed = base_stats.get("quotes_processed", 0)
            trades_processed = base_stats.get("trades_processed", 0)

            # Extract timeframe statistics
            timeframe_stats = base_stats.get("timeframe_stats", {})

            # Extract performance metrics
            avg_processing_time = base_stats.get("avg_processing_time_ms", 0.0)
            data_latency = base_stats.get("data_latency_ms", 0.0)
            buffer_utilization = base_stats.get("buffer_utilization", 0.0)

            # Extract storage metrics
            total_bars_stored = base_stats.get("total_bars_stored", 0)
            memory_usage = base_stats.get("memory_usage_mb", 0.0)
            compression_ratio = base_stats.get("compression_ratio", 1.0)

            # Extract update metrics
            updates_per_minute = base_stats.get("updates_per_minute", 0.0)
            last_update = base_stats.get("last_update")
            if last_update and not isinstance(last_update, str):
                last_update = str(last_update)
            data_freshness = base_stats.get("data_freshness_seconds", 0.0)

            # Extract error metrics
            validation_errors = base_stats.get("data_validation_errors", 0)
            connection_interruptions = base_stats.get("connection_interruptions", 0)
            recovery_attempts = base_stats.get("recovery_attempts", 0)

            # Get overflow statistics if available
            overflow_stats = base_stats.get("overflow_stats", {})

            # Get lock optimization statistics if available
            lock_optimization_stats = base_stats.get("lock_optimization_stats", {})

            stats: RealtimeDataManagerStats = {
                "bars_processed": int(bars_processed),
                "ticks_processed": int(ticks_processed),
                "quotes_processed": int(quotes_processed),
                "trades_processed": int(trades_processed),
                "timeframe_stats": dict(timeframe_stats),
                "avg_processing_time_ms": float(avg_processing_time),
                "data_latency_ms": float(data_latency),
                "buffer_utilization": round(buffer_utilization, 4),
                "total_bars_stored": int(total_bars_stored),
                "memory_usage_mb": round(memory_usage, 2),
                "compression_ratio": round(compression_ratio, 4),
                "updates_per_minute": round(updates_per_minute, 2),
                "last_update": last_update,
                "data_freshness_seconds": float(data_freshness),
                "data_validation_errors": int(validation_errors),
                "connection_interruptions": int(connection_interruptions),
                "recovery_attempts": int(recovery_attempts),
                "overflow_stats": overflow_stats,
                "buffer_overflow_stats": overflow_stats,  # Add missing field
                "lock_optimization_stats": lock_optimization_stats,
            }

            # Record collection timing
            collection_time = (time.time() - start_time) * 1000
            await self.record_timing("data_stats_collection", collection_time)

            return stats

        except Exception as e:
            await self.track_error(
                e, "Failed to collect RealtimeDataManager statistics"
            )
            return None

    async def _collect_orderbook_stats(self) -> OrderbookStats | None:
        """
        Collect statistics from OrderBook component.

        Extracts market depth metrics, trade statistics, spread analysis, and
        pattern detection results. Calculates market microstructure indicators.

        Returns:
            OrderbookStats if component is available, None otherwise
        """
        orderbook = self._suite_component("orderbook")
        if orderbook is None:
            return None

        try:
            start_time = time.time()

            # Get memory statistics (async method)
            base_stats: dict[str, Any] = {}
            if hasattr(orderbook, "get_memory_stats"):
                result = await orderbook.get_memory_stats()
                # Result is already a dict from the orderbook implementation
                base_stats = result if result else {}

            # Extract depth statistics
            avg_bid_depth = base_stats.get("avg_bid_depth", 0)
            avg_ask_depth = base_stats.get("avg_ask_depth", 0)
            max_bid_depth = base_stats.get("max_bid_depth", 0)
            max_ask_depth = base_stats.get("max_ask_depth", 0)

            # Extract trade statistics
            trades_processed = base_stats.get("trades_processed", 0)
            avg_trade_size = base_stats.get("avg_trade_size", 0.0)
            largest_trade = base_stats.get("largest_trade", 0)
            total_volume = base_stats.get("total_volume", 0)

            # Extract market microstructure metrics
            avg_spread = base_stats.get("avg_spread", 0.0)
            spread_volatility = base_stats.get("spread_volatility", 0.0)
            price_levels = base_stats.get("price_levels", 0)
            order_clustering = base_stats.get("order_clustering", 0.0)

            # Extract pattern detection metrics
            icebergs_detected = base_stats.get("icebergs_detected", 0)
            spoofing_alerts = base_stats.get("spoofing_alerts", 0)
            unusual_patterns = base_stats.get("unusual_patterns", 0)

            # Extract performance metrics
            update_frequency = base_stats.get("update_frequency_per_second", 0.0)
            processing_latency = base_stats.get("processing_latency_ms", 0.0)
            memory_usage = base_stats.get("memory_usage_mb", 0.0)

            # Extract data quality metrics
            data_gaps = base_stats.get("data_gaps", 0)
            invalid_updates = base_stats.get("invalid_updates", 0)
            duplicate_updates = base_stats.get("duplicate_updates", 0)

            stats: OrderbookStats = {
                "avg_bid_depth": int(avg_bid_depth),
                "avg_ask_depth": int(avg_ask_depth),
                "max_bid_depth": int(max_bid_depth),
                "max_ask_depth": int(max_ask_depth),
                "trades_processed": int(trades_processed),
                "avg_trade_size": round(avg_trade_size, 2),
                "largest_trade": int(largest_trade),
                "total_volume": int(total_volume),
                "avg_spread": round(avg_spread, 4),
                "spread_volatility": round(spread_volatility, 4),
                "price_levels": int(price_levels),
                "order_clustering": round(order_clustering, 4),
                "icebergs_detected": int(icebergs_detected),
                "spoofing_alerts": int(spoofing_alerts),
                "unusual_patterns": int(unusual_patterns),
                "update_frequency_per_second": round(update_frequency, 2),
                "processing_latency_ms": float(processing_latency),
                "memory_usage_mb": round(memory_usage, 2),
                "data_gaps": int(data_gaps),
                "invalid_updates": int(invalid_updates),
                "duplicate_updates": int(duplicate_updates),
            }

            # Record collection timing
            collection_time = (time.time() - start_time) * 1000
            await self.record_timing("orderbook_stats_collection", collection_time)

            return stats

        except Exception as e:
            await self.track_error(e, "Failed to collect OrderBook statistics")
            return None

    async def _collect_risk_stats(self) -> RiskManagerStats | None:
        """
        Collect statistics from RiskManager component.

        Extracts risk rule evaluations, position risk metrics, managed trade
        statistics, and risk-adjusted performance indicators.

        Returns:
            RiskManagerStats if component is available, None otherwise
        """
        risk_manager = self._suite_component("risk_manager")
        if risk_manager is None:
            return None

        try:
            start_time = time.time()

            # Get base statistics
            base_stats: dict[str, Any] = {}
            if hasattr(risk_manager, "get_memory_stats"):
                result = risk_manager.get_memory_stats()
                if isinstance(result, dict):
                    base_stats = result

            # If no stats available, use defaults
            if not base_stats:
                # Provide default values for risk manager stats
                base_stats = {}

            # Extract rule statistics
            rules_evaluated = base_stats.get("rules_evaluated", 0)
            rule_violations = base_stats.get("rule_violations", 0)
            rule_warnings = base_stats.get("rule_warnings", 0)
            rules_passed = rules_evaluated - rule_violations - rule_warnings

            # Extract position risk metrics
            total_risk_exposure = base_stats.get("total_risk_exposure", 0.0)
            max_position_risk = base_stats.get("max_position_risk", 0.0)
            portfolio_risk = base_stats.get("portfolio_risk", 0.0)
            var_95 = base_stats.get("var_95", 0.0)

            # Extract risk limits
            max_loss_limit = base_stats.get("max_loss_limit", 0.0)
            daily_loss_limit = base_stats.get("daily_loss_limit", 0.0)
            position_size_limit = base_stats.get("position_size_limit", 0)
            leverage_limit = base_stats.get("leverage_limit", 0.0)

            # Extract risk events
            stop_losses_triggered = base_stats.get("stop_losses_triggered", 0)
            margin_calls = base_stats.get("margin_calls", 0)
            risk_alerts = base_stats.get("risk_alerts", 0)
            emergency_stops = base_stats.get("emergency_stops", 0)

            # Extract performance metrics
            risk_calculations_per_second = base_stats.get(
                "risk_calculations_per_second", 0.0
            )
            avg_calculation_time = base_stats.get("avg_calculation_time_ms", 0.0)
            memory_usage = base_stats.get("memory_usage_mb", 0.0)

            # Extract managed trade metrics
            managed_trades_active = base_stats.get("managed_trades_active", 0)
            managed_trades_completed = base_stats.get("managed_trades_completed", 0)
            managed_trades_stopped = base_stats.get("managed_trades_stopped", 0)
            avg_trade_duration = base_stats.get("avg_trade_duration_minutes", 0.0)

            # Extract risk-adjusted performance
            sharpe_ratio = base_stats.get("sharpe_ratio", 0.0)
            sortino_ratio = base_stats.get("sortino_ratio", 0.0)
            max_drawdown = base_stats.get("max_drawdown", 0.0)
            risk_adjusted_return = base_stats.get("risk_adjusted_return", 0.0)

            stats: RiskManagerStats = {
                "rules_evaluated": int(rules_evaluated),
                "rule_violations": int(rule_violations),
                "rule_warnings": int(rule_warnings),
                "rules_passed": int(rules_passed),
                "total_risk_exposure": float(total_risk_exposure),
                "max_position_risk": float(max_position_risk),
                "portfolio_risk": float(portfolio_risk),
                "var_95": float(var_95),
                "max_loss_limit": float(max_loss_limit),
                "daily_loss_limit": float(daily_loss_limit),
                "position_size_limit": int(position_size_limit),
                "leverage_limit": float(leverage_limit),
                "stop_losses_triggered": int(stop_losses_triggered),
                "margin_calls": int(margin_calls),
                "risk_alerts": int(risk_alerts),
                "emergency_stops": int(emergency_stops),
                "risk_calculations_per_second": round(risk_calculations_per_second, 2),
                "avg_calculation_time_ms": float(avg_calculation_time),
                "memory_usage_mb": round(memory_usage, 2),
                "managed_trades_active": int(managed_trades_active),
                "managed_trades_completed": int(managed_trades_completed),
                "managed_trades_stopped": int(managed_trades_stopped),
                "avg_trade_duration_minutes": float(avg_trade_duration),
                "sharpe_ratio": round(sharpe_ratio, 4),
                "sortino_ratio": round(sortino_ratio, 4),
                "max_drawdown": float(max_drawdown),
                "risk_adjusted_return": round(risk_adjusted_return, 4),
            }

            # Record collection timing
            collection_time = (time.time() - start_time) * 1000
            await self.record_timing("risk_stats_collection", collection_time)

            return stats

        except Exception as e:
            await self.track_error(e, "Failed to collect RiskManager statistics")
            return None


__all__ = [
    "ComponentCollector",
]
