"""
Position Manager Module for ProjectX Trading Platform.

Author: @TexasCoding
Date: 2025-08-02

Overview:
    Provides comprehensive position management functionality for ProjectX trading operations,
    including real-time tracking, P&L calculations, risk management, and direct position
    operations. Integrates with both API and real-time clients for seamless position
    lifecycle management.

Key Features:
    - Real-time position tracking and monitoring via WebSocket
    - P&L calculations and portfolio analytics with market prices
    - Risk metrics and position sizing with configurable thresholds
    - Position monitoring and alerts with customizable triggers
    - Direct position operations (close, partial close, bulk operations)
    - Statistics, history, and comprehensive report generation
    - Thread-safe operations with async/await patterns
    - Event-driven callbacks for custom position monitoring

Position Management Capabilities:
    - Real-time position updates and closure detection
    - Portfolio-level P&L analysis with current market prices
    - Risk assessment and position sizing calculations
    - Automated position monitoring with configurable alerts
    - Direct position operations through ProjectX API
    - Comprehensive reporting and historical analysis

Note:
    While this module provides direct access to the `PositionManager`, for most
    trading applications, it is recommended to use the `TradingSuite`. The suite
    automatically creates, configures, and manages the position manager, providing
    simplified access to its functionality via `suite.positions`.
    The example below shows the lower-level manual setup.

Example Usage:
    ```python
    # V3.1: Comprehensive position management with TradingSuite
    import asyncio
    from project_x_py import TradingSuite


    async def main():
        # V3.1: Create suite with integrated position manager
        suite = await TradingSuite.create("MNQ", timeframes=["1min"])

        # V3.1: Get current positions with detailed info
        positions = await suite.positions.get_all_positions()
        for pos in positions:
            print(f"Contract: {pos.contractId}")
            print(f"  Size: {pos.size}")
            print(f"  Avg Price: ${pos.averagePrice:.2f}")
            print(f"  Direction: {pos.direction}")

        # V3.1: Calculate portfolio P&L with current market prices
        current_price = await suite.data.get_current_price()
        market_prices = {"MNQ": current_price, "ES": 4500.0}
        pnl = await suite.positions.calculate_portfolio_pnl(market_prices)
        print(f"Total P&L: ${pnl['total_pnl']:.2f}")
        print(f"Unrealized: ${pnl['unrealized_pnl']:.2f}")
        print(f"Realized: ${pnl['realized_pnl']:.2f}")

        # V3.1: Risk analysis with comprehensive metrics
        risk = await suite.positions.get_risk_metrics()
        print(f"Portfolio Risk: {risk['portfolio_risk']:.2%}")
        print(f"Max Drawdown: ${risk['max_drawdown']:.2f}")
        print(f"VaR (95%): ${risk['var_95']:.2f}")

        # V3.1: Position sizing with risk management
        sizing = await suite.positions.calculate_position_size(
            suite.instrument_id,
            risk_amount=500.0,
            entry_price=current_price,
            stop_price=current_price - 10.0,
        )
        print(f"Suggested size: {sizing['suggested_size']} contracts")
        print(f"Position risk: ${sizing['position_risk']:.2f}")

        # V3.1: Set up position monitoring with alerts
        await suite.positions.add_position_alert(
            suite.instrument_id, max_loss=-500.0, min_profit=1000.0
        )
        await suite.positions.start_monitoring(interval_seconds=5)

        await suite.disconnect()


    asyncio.run(main())
    ```

See Also:
    - `position_manager.core.PositionManager`
    - `position_manager.analytics.PositionAnalyticsMixin`
    - `position_manager.risk.RiskManagementMixin`
    - `position_manager.monitoring.PositionMonitoringMixin`
    - `position_manager.operations.PositionOperationsMixin`
    - `position_manager.reporting.PositionReportingMixin`
    - `position_manager.tracking.PositionTrackingMixin`
"""

from project_x_py.position_manager.core import PositionManager

__all__ = ["PositionManager"]
