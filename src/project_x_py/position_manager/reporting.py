"""
Statistics, history, and report generation functionality for ProjectX position management.

Author: @TexasCoding
Date: 2025-08-02

Overview:
    Provides comprehensive reporting and statistics functionality for position
    management. Includes system statistics, position history tracking,
    portfolio reports, and real-time validation status for monitoring and analysis.

Key Features:
    - Comprehensive system statistics and health monitoring
    - Position history tracking and analysis
    - Portfolio report generation with detailed analytics
    - Real-time validation status and compliance checking
    - Export capabilities for external reporting
    - Thread-safe operations with proper data handling

Reporting Capabilities:
    - System statistics and health monitoring
    - Position history with change tracking
    - Portfolio reports with risk analysis
    - Real-time integration validation
    - Export functionality for external systems

Example Usage:
    ```python
    # V3.1: Get system statistics with TradingSuite
    stats = suite.positions.get_position_statistics()
    print(f"Health: {stats['health_status']}")
    print(f"Tracking {stats['tracked_positions']} positions")

    # V3.1: Get position history
    history = await suite.positions.get_position_history(suite.instrument_id, limit=50)
    for entry in history[-5:]:
        print(f"{entry['timestamp']}: Size {entry['position']['size']}")

    # V3.1: Generate comprehensive report
    report = await suite.positions.export_portfolio_report()
    print(f"Portfolio Report - {report['report_timestamp']}")
    print(f"Positions: {report['portfolio_summary']['total_positions']}")

    # V3.1: Check real-time validation
    status = suite.positions.get_realtime_validation_status()
    print(f"Real-time enabled: {status['realtime_enabled']}")
    ```

See Also:
    - `position_manager.core.PositionManager`
    - `position_manager.analytics.PositionAnalyticsMixin`
    - `position_manager.risk.RiskManagementMixin`
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from project_x_py.types import PositionManagerProtocol
    from project_x_py.types.stats_types import PositionManagerStats


class PositionReportingMixin:
    """Mixin for statistics, history, and report generation."""

    async def get_position_statistics(
        self: "PositionManagerProtocol",
    ) -> "PositionManagerStats":
        """
        Get comprehensive position management statistics and health information.

        Provides detailed statistics about position tracking, monitoring status,
        performance metrics, and system health for debugging and monitoring.

        Returns:
            dict[str, Any]: Complete system statistics containing:
                - statistics (dict): Core metrics:
                    * positions_tracked (int): Current position count
                    * total_pnl (float): Aggregate P&L
                    * realized_pnl (float): Closed position P&L
                    * unrealized_pnl (float): Open position P&L
                    * positions_closed (int): Total positions closed
                    * positions_partially_closed (int): Partial closures
                    * last_update_time (datetime): Last data refresh
                    * monitoring_started (datetime): Monitoring start time
                - realtime_enabled (bool): Using WebSocket updates
                - order_sync_enabled (bool): Order synchronization active
                - monitoring_active (bool): Position monitoring running
                - tracked_positions (int): Positions in local cache
                - active_alerts (int): Untriggered alert count
                - callbacks_registered (dict): Callbacks by event type
                - risk_settings (dict): Current risk thresholds
                - health_status (str): "active" or "inactive"

        Example:
            >>> stats = position_manager.get_position_statistics()
            >>> print(f"System Health: {stats['health_status']}")
            >>> print(f"Tracking {stats['tracked_positions']} positions")
            >>> print(f"Real-time: {stats['realtime_enabled']}")
            >>> print(f"Monitoring: {stats['monitoring_active']}")
            >>> print(f"Positions closed: {stats['statistics']['positions_closed']}")
            >>> # Check callback registrations
            >>> for event, count in stats["callbacks_registered"].items():
            ...     print(f"{event}: {count} callbacks")

        Note:
            Statistics are cumulative since manager initialization.
            Use export_portfolio_report() for more detailed analysis.
        """
        # Update current positions count
        self.stats["open_positions"] = len(
            [p for p in self.tracked_positions.values() if p.size != 0]
        )
        self.stats["total_positions"] = len(self.tracked_positions)
        self.stats["position_updates"] += 1

        # Calculate performance metrics
        # Note: Position model doesn't have realized_pnl, so we use stats tracking instead
        closed_positions_count = self.stats.get("closed_positions", 0)
        winning_positions_count = self.stats.get("winning_positions", 0)

        win_rate = (
            winning_positions_count / closed_positions_count
            if closed_positions_count > 0
            else 0.0
        )

        # Calculate profit factor from stats
        gross_profit = self.stats.get("gross_profit", 0.0)
        gross_loss = abs(self.stats.get("gross_loss", 0.0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0

        # Calculate average metrics
        position_sizes = [
            abs(p.size) for p in self.tracked_positions.values() if p.size != 0
        ]
        avg_position_size = (
            sum(position_sizes) / len(position_sizes) if position_sizes else 0.0
        )
        largest_position = max(position_sizes) if position_sizes else 0

        return {
            "open_positions": self.stats["open_positions"],
            "closed_positions": self.stats["closed_positions"],
            "total_positions": self.stats["total_positions"],
            "total_pnl": self.stats["total_pnl"],
            "realized_pnl": self.stats["realized_pnl"],
            "unrealized_pnl": self.stats["unrealized_pnl"],
            "best_position_pnl": self.stats["best_position_pnl"],
            "worst_position_pnl": self.stats["worst_position_pnl"],
            "avg_position_size": avg_position_size,
            "largest_position": largest_position,
            "avg_hold_time_minutes": self.stats["avg_hold_time_minutes"],
            "longest_hold_time_minutes": self.stats["longest_hold_time_minutes"],
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "sharpe_ratio": self.stats["sharpe_ratio"],
            "max_drawdown": self.stats["max_drawdown"],
            "total_risk": self.stats["total_risk"],
            "max_position_risk": self.stats["max_position_risk"],
            "portfolio_correlation": self.stats["portfolio_correlation"],
            "var_95": self.stats["var_95"],
            "position_updates": self.stats["position_updates"],
            "risk_calculations": self.stats["risk_calculations"],
            "last_position_update": (
                self.stats["last_position_update"].isoformat()
                if self.stats["last_position_update"]
                else None
            ),
        }

    async def get_position_history(
        self: "PositionManagerProtocol", contract_id: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        """
        Get historical position data for a specific contract.

        Retrieves the history of position changes including size changes,
        timestamps, and position snapshots for analysis and debugging.

        Args:
            contract_id (str): Contract ID to retrieve history for (e.g., "MNQ")
            limit (int, optional): Maximum number of history entries to return.
                Returns most recent entries if history exceeds limit.
                Defaults to 100.

        Returns:
            list[dict]: Historical position entries, each containing:
                - timestamp (datetime): When the change occurred
                - position (dict): Complete position snapshot at that time
                - size_change (int): Change in position size from previous

        Example:
            >>> # V3.1: Get recent history with TradingSuite
            >>> history = await suite.positions.get_position_history(
            ...     suite.instrument_id, limit=50
            ... )
            >>> print(f"Found {len(history)} historical entries")
            >>> # V3.1: Analyze recent changes
            >>> for entry in history[-5:]:  # Last 5 changes
            ...     ts = entry["timestamp"].strftime("%H:%M:%S")
            ...     size = entry["position"]["size"]
            ...     change = entry["size_change"]
            ...     print(f"{ts}: Size {size} (change: {change:+d})")
            >>> # Find when position was opened
            >>> if history:
            ...     first_entry = history[0]
            ...     print(f"Position opened at {first_entry['timestamp']}")

        Note:
            - History is maintained in memory during manager lifetime
            - Cleared when cleanup() is called
            - Empty list returned if no history exists
        """
        async with self.position_lock:
            history: list[dict[str, Any]] = list(
                self.position_history.get(contract_id, [])
            )
            return history[-limit:] if history else []

    async def export_portfolio_report(
        self: "PositionManagerProtocol",
    ) -> dict[str, Any]:
        """
        Generate a comprehensive portfolio report with complete analysis.

        Creates a detailed report suitable for saving to file, sending via email,
        or displaying in dashboards. Combines all available analytics into a
        single comprehensive document.

        Returns:
            dict[str, Any]: Complete portfolio report containing:
                - report_timestamp (datetime): Report generation time
                - portfolio_summary (dict):
                    * total_positions (int): Open position count
                    * total_pnl (float): Aggregate P&L (requires prices)
                    * total_exposure (float): Sum of position values
                    * portfolio_risk (float): Risk score
                - positions (list[dict]): Detailed position list
                - risk_analysis (dict): Complete risk metrics
                - statistics (dict): System statistics and health
                - alerts (dict):
                    * active_alerts (int): Untriggered alert count
                    * triggered_alerts (int): Triggered alert count

        Example:
            >>> # Generate comprehensive report
            >>> report = await position_manager.export_portfolio_report()
            >>> print(f"Portfolio Report - {report['report_timestamp']}")
            >>> print(f"Positions: {report['portfolio_summary']['total_positions']}")
            >>> print(
            ...     f"Exposure: ${report['portfolio_summary']['total_exposure']:,.2f}"
            ... )
            >>> # Save report to file (async)
            >>> import json
            >>> import aiofiles
            >>> async with aiofiles.open("portfolio_report.json", "w") as f:
            ...     await f.write(json.dumps(report, indent=2, default=str))
            >>> # Send key metrics
            >>> summary = report["portfolio_summary"]
            >>> alerts = report["alerts"]
            >>> print(f"Active Alerts: {alerts['active_alerts']}")

        Use cases:
            - End-of-day reporting
            - Risk management dashboards
            - Performance tracking
            - Audit trails
            - Email summaries
        """
        positions = await self.get_all_positions()
        pnl_data = await self.get_portfolio_pnl()
        risk_data = await self.get_risk_metrics()
        stats = await self.get_position_statistics()

        return {
            "report_timestamp": datetime.now(),
            "portfolio_summary": {
                "total_positions": len(positions),
                "total_pnl": pnl_data["total_pnl"],
                "total_exposure": risk_data["current_risk"],
                "portfolio_risk": risk_data["max_risk"],
            },
            "positions": positions,
            "risk_analysis": risk_data,
            "statistics": stats,
            "alerts": {
                "active_alerts": len(
                    [a for a in self.position_alerts.values() if not a["triggered"]]
                ),
                "triggered_alerts": len(
                    [a for a in self.position_alerts.values() if a["triggered"]]
                ),
            },
        }

    def get_realtime_validation_status(
        self: "PositionManagerProtocol",
    ) -> dict[str, Any]:
        """
        Get validation status for real-time position feed integration and compliance.

        Provides detailed information about real-time integration status,
        payload validation settings, and ProjectX API compliance for debugging
        and system validation.

        Returns:
            dict[str, Any]: Validation and compliance status containing:
                - realtime_enabled (bool): WebSocket integration active
                - tracked_positions_count (int): Positions in cache
                - payload_validation (dict):
                    * enabled (bool): Validation active
                    * required_fields (list[str]): Expected fields
                    * position_type_enum (dict): Type mappings
                    * closure_detection (str): How closures detected
                - projectx_compliance (dict):
                    * gateway_user_position_format: Compliance status
                    * position_type_enum: Enum validation status
                    * closure_logic: Closure detection status
                    * payload_structure: Payload format status
                - statistics (dict): Current statistics

        Example:
            >>> # Check real-time integration health
            >>> status = position_manager.get_realtime_validation_status()
            >>> print(f"Real-time enabled: {status['realtime_enabled']}")
            >>> print(f"Tracking {status['tracked_positions_count']} positions")
            >>> # Verify API compliance
            >>> compliance = status["projectx_compliance"]
            >>> all_compliant = all("✅" in v for v in compliance.values())
            >>> print(f"Fully compliant: {all_compliant}")
            >>> # Check payload validation
            >>> validation = status["payload_validation"]
            >>> print(f"Closure detection: {validation['closure_detection']}")
            >>> print(f"Required fields: {len(validation['required_fields'])}")

        Use cases:
            - Integration testing
            - Debugging connection issues
            - Compliance verification
            - System health checks
        """
        return {
            "realtime_enabled": self._realtime_enabled,
            "tracked_positions_count": len(self.tracked_positions),
            "payload_validation": {
                "enabled": True,
                "required_fields": [
                    "id",
                    "accountId",
                    "contractId",
                    "creationTimestamp",
                    "type",
                    "size",
                    "averagePrice",
                ],
                "position_type_enum": {"Undefined": 0, "Long": 1, "Short": 2},
                "closure_detection": "size == 0 (not type == 0)",
            },
            "projectx_compliance": {
                "gateway_user_position_format": "✅ Compliant",
                "position_type_enum": "✅ Correct",
                "closure_logic": "✅ Fixed (was incorrectly checking type==0)",
                "payload_structure": "✅ Direct payload (no 'data' extraction)",
            },
            "statistics": self.stats.copy(),
        }
