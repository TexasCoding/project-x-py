#!/usr/bin/env python3
"""
ProjectX SDK Statistics Usage Example
=====================================

This example demonstrates the comprehensive statistics and monitoring capabilities
introduced in v3.3.0 of the ProjectX SDK.

Key Features Demonstrated:
- Component-level statistics collection
- Multi-format export (JSON, Prometheus, CSV, Datadog)
- Health monitoring and scoring
- Performance metrics tracking
- Error and anomaly detection
- Memory usage monitoring
- Adaptive strategy based on statistics

Version: 3.3.0 - Complete Statistics Module Redesign
Author: TexasCoding
"""

import asyncio
import json
from decimal import Decimal

from project_x_py import Features, TradingSuite, utils
from project_x_py.models import Order, OrderPlaceResponse


async def main():
    """Main example demonstrating v3.3.0 statistics capabilities."""
    suite = None

    try:
        print("=" * 60)
        print("ProjectX SDK Statistics Usage Example")
        print("=" * 60)

        # =========================================================================
        # 1. INITIALIZE TRADING SUITE WITH STATISTICS FEATURES
        # =========================================================================
        suite = await TradingSuite.create(
            ["MNQ"],
            features=[Features.ORDERBOOK, Features.RISK_MANAGER],
            timeframes=["1min", "5min"],
            initial_days=1,
        )

        mnq_suite = suite["MNQ"]

        if suite is None:
            print("❌ Failed to initialize trading suite")
            return

        if not mnq_suite.instrument_info:
            print("❌ Failed to initialize trading suite")
            return

        if not suite.client:
            print("❌ Failed to initialize trading suite")
            return

        if not mnq_suite.data:
            print("❌ Failed to initialize trading suite")
            return

        if not mnq_suite.orders:
            print("❌ Failed to initialize trading suite")
            return

        if not mnq_suite.positions:
            print("❌ Failed to initialize trading suite")
            return

        if not mnq_suite.risk_manager:
            print("❌ Failed to initialize trading suite")
            return

        if not suite.client.account_info:
            print("❌ Failed to initialize trading suite")
            return

        print(f"\n✅ Trading suite initialized for {mnq_suite.instrument_info.id}")
        print(f"   Account: {suite.client.account_info.name}")

        # =========================================================================
        # GENERATE SOME TRADING ACTIVITY FOR STATISTICS
        # =========================================================================
        print("\n" + "=" * 60)
        print("1. GENERATING TRADING ACTIVITY FOR STATISTICS")
        print("=" * 60)

        print("\n📈 Placing test orders to generate statistics...")

        # Get current price for placing limit orders
        current_price = await mnq_suite.data.get_current_price()
        if not current_price:
            bars = await mnq_suite.data.get_data("1min")
            if bars is not None and not bars.is_empty():
                current_price = Decimal(str(bars[-1]["close"]))
            else:
                current_price = Decimal("20000")

        print(f"   Current {mnq_suite.instrument_info.id} price: ${current_price:,.2f}")

        # Place some test orders (far from market to avoid fills)
        test_orders: list[OrderPlaceResponse] = []

        # Buy orders below market
        for i in range(3):
            price = float(current_price) - (50 + i * 50)
            price = utils.round_to_tick_size(
                float(price), mnq_suite.instrument_info.tickSize
            )

            print(f"\n   Placing buy limit order at ${price:,.2f}...")
            order = await mnq_suite.orders.place_limit_order(
                contract_id=mnq_suite.instrument_info.id,
                side=0,  # Buy
                size=1,
                limit_price=float(price),
            )
            test_orders.append(order)
            print(f"   ✅ Order placed: {order.orderId}")

        # Sell orders above market
        for i in range(2):
            price = float(current_price) + (50 + i * 50)
            price = utils.round_to_tick_size(
                float(price), mnq_suite.instrument_info.tickSize
            )

            print(f"\n   Placing sell limit order at ${price:,.2f}...")
            order = await mnq_suite.orders.place_limit_order(
                contract_id=mnq_suite.instrument_info.id,
                side=1,  # Sell
                size=1,
                limit_price=float(price),
            )
            test_orders.append(order)
            print(f"   ✅ Order placed: {order.orderId}")

        # =========================================================================
        # 2. COMPONENT-LEVEL STATISTICS
        # =========================================================================
        print("\n" + "=" * 60)
        print("2. COMPONENT-LEVEL STATISTICS")
        print("=" * 60)

        # Get order manager statistics (v3.3.0 - async API)
        order_stats = await mnq_suite.orders.get_stats()
        print("\n📊 Order Manager Statistics:")
        print(f"  Orders placed: {order_stats.get('orders_placed', 0)}")
        print(f"  Orders filled: {order_stats.get('orders_filled', 0)}")
        print(f"  Orders cancelled: {order_stats.get('orders_cancelled', 0)}")
        print(f"  Error count: {order_stats.get('error_count', 0)}")
        print(f"  Memory usage: {order_stats.get('memory_usage_mb', 0):.2f}MB")

        # Get position manager statistics (v3.3.0 - async API)
        position_stats = await mnq_suite.positions.get_stats()
        print("\n📊 Position Manager Statistics:")
        print(f"  Positions opened: {position_stats.get('positions_opened', 0)}")
        print(f"  Positions closed: {position_stats.get('positions_closed', 0)}")
        print(f"  Error count: {position_stats.get('error_count', 0)}")
        print(f"  Memory usage: {position_stats.get('memory_usage_mb', 0):.2f}MB")

        # Get data manager statistics (v3.3.0 - async API)
        data_stats = await mnq_suite.data.get_stats()
        print("\n📊 Data Manager Statistics:")
        print(f"  Bars processed: {data_stats.get('bars_processed', 0)}")
        print(f"  Ticks processed: {data_stats.get('ticks_processed', 0)}")
        print(f"  Error count: {data_stats.get('error_count', 0)}")
        print(f"  Memory usage: {data_stats.get('memory_usage_mb', 0):.2f}MB")

        # =========================================================================
        # 3. AGGREGATED STATISTICS WITH v3.3.0 ARCHITECTURE
        # =========================================================================
        print("\n" + "=" * 60)
        print("3. AGGREGATED STATISTICS (v3.3.0 Feature)")
        print("=" * 60)

        # Get comprehensive suite statistics
        comprehensive_stats = await suite._stats_aggregator.get_comprehensive_stats()

        print("\n⚡ System Performance Metrics:")
        print(f"  Total Operations: {comprehensive_stats.get('total_operations', 0):,}")
        print(f"  Total Errors: {comprehensive_stats.get('total_errors', 0)}")
        print(f"  Component Count: {comprehensive_stats.get('components', 0)}")
        print(f"  Memory Usage: {comprehensive_stats.get('memory_usage_mb', 0):.2f}MB")

        # Calculate health score using HealthMonitor
        # Note: For compatibility, we'll use the stats as-is for health calculation
        # The HealthMonitor can handle TradingSuiteStats structure
        from project_x_py.statistics.health import HealthMonitor

        monitor = HealthMonitor()
        # Cast to dict for type compatibility
        stats_dict = dict(comprehensive_stats)
        health_score = await monitor.calculate_health(stats_dict)  # type: ignore
        print(f"\n  Overall Health Score: {health_score:.1f}/100")

        # Get detailed health breakdown
        breakdown = await monitor.get_health_breakdown(stats_dict)  # type: ignore
        print("\n  Health Breakdown:")
        for category, score in breakdown.items():
            if category not in ["overall_score", "weighted_total"]:
                print(f"    {category}: {score:.1f}/100")

        # =========================================================================
        # 4. MULTI-FORMAT EXPORT (v3.3.0 Feature)
        # =========================================================================
        print("\n" + "=" * 60)
        print("4. MULTI-FORMAT EXPORT")
        print("=" * 60)

        from project_x_py.statistics.export import StatsExporter

        exporter = StatsExporter()

        # Export to JSON (comprehensive_stats is already a dict)
        json_stats = json.dumps(comprehensive_stats, indent=2)
        print("\n📄 JSON Export (sample):")
        json_str = json.dumps(json_stats, indent=2)
        for line in json_str.split("\n")[:5]:
            print(f"  {line}")
        print("  ...")

        # Note: The export() method is not available in the current API
        # We'll skip this section and use the newer to_prometheus() method below

        # Export to different formats
        print("\n📑 Exporting statistics to multiple formats...")

        # Export to CSV
        csv_stats = await exporter.to_csv(
            comprehensive_stats, include_timestamp=True
        )
        print("\n📊 CSV Export (first 3 lines):")
        for line in csv_stats.split("\n")[:3]:
            if line:
                print(f"  {line}")

        # Export to Prometheus format
        prometheus_stats = await exporter.to_prometheus(comprehensive_stats)
        print("\n📊 Prometheus Export (first 5 metrics):")
        for line in prometheus_stats.split("\n")[:10]:
            if line and not line.startswith("#"):
                print(f"  {line}")
        # Export to Datadog format
        datadog_stats = await exporter.to_datadog(
            comprehensive_stats, prefix="projectx"
        )
        print("\n📊 Datadog Export (first 3 metrics):")
        for metric in datadog_stats.get("series", [])[:3]:
            print(
                f"  {metric['metric']}: {metric['points'][0][1] if metric['points'] else 'N/A'}"
            )

        # Save JSON to file
        with open("trading_stats.json", "w") as f:
            f.write(json_stats)
        print("\n✅ Statistics exported to trading_stats.json")

        # =========================================================================
        # 5. MONITORING & ALERTING
        # =========================================================================
        print("\n" + "=" * 60)
        print("5. MONITORING & ALERTING")
        print("=" * 60)

        # Check for errors in the aggregated statistics
        errors = comprehensive_stats.get("errors", {})
        if errors.get("total_errors", 0) > 0:
            print("\n⚠️ Errors detected:")
            print(f"  Total errors: {errors.get('total_errors', 0)}")
            error_rate = errors.get("error_rate", 0.0)
            print(f"  Error rate: {error_rate:.2%}")
            recent_errors = errors.get("recent_errors", [])
            if recent_errors:
                print("  Recent errors:")
                for error in recent_errors[:3]:
                    print(
                        f"    - {error.get('timestamp', 'N/A')}: {error.get('message', 'N/A')}"
                    )

        # Check system health (already calculated above)
        if health_score < 80:
            print("\n⚠️ System health below optimal threshold")
            print("  Recommended actions:")
            print("  - Check connection stability")
            print("  - Review error logs")
            print("  - Monitor memory usage")

        # =========================================================================
        # 6. ADAPTIVE STRATEGY EXAMPLE
        # =========================================================================
        print("\n" + "=" * 60)
        print("6. ADAPTIVE STRATEGY BASED ON STATISTICS")
        print("=" * 60)

        # Adjust trading based on system health (using health_score from above)
        if health_score >= 90:
            print("\n✅ System health excellent - normal trading mode")
            print("  - Full position sizes allowed")
            print("  - Tight stops enabled")
            print("  - All strategies active")
        elif health_score >= 70:
            print("\n⚠️ System health degraded - cautious mode")
            print("  - Reduced position sizes (75%)")
            print("  - Wider stops")
            print("  - Conservative strategies only")
        else:
            print("\n🛑 System health critical - safe mode")
            print("  - Minimal position sizes (25%)")
            print("  - Emergency stops only")
            print("  - Close existing positions")

        # Check performance for latency issues
        if comprehensive_stats and comprehensive_stats.get("avg_latency_ms", 0) > 500:
            print("\n⚠️ High latency detected - optimizing order placement")
            print("  - Switching to limit orders only")
            print("  - Increasing price buffers")
            print("  - Reducing order frequency")

    except Exception as e:
        print(f"\n❌ Error during example execution: {e}")
        import traceback

        traceback.print_exc()

    finally:
        # =========================================================================
        # CLEANUP - ENSURE NO OPEN ORDERS OR POSITIONS
        # =========================================================================
        print("\n" + "=" * 60)
        print("CLEANUP - ENSURING NO OPEN ORDERS OR POSITIONS")
        print("=" * 60)

        if mnq_suite:
            try:
                # Cancel test orders
                if "test_orders" in locals() and test_orders:
                    print(f"\n🧹 Cancelling {len(test_orders)} test orders...")
                    for order in test_orders:
                        try:
                            await mnq_suite.orders.cancel_order(order.orderId)
                            print(f"   ✅ Cancelled order {order.orderId}")
                        except Exception as e:
                            print(f"   ⚠️ Could not cancel order {order.orderId}: {e}")

                # Check for any remaining open orders
                print("\n🔍 Checking for any remaining open orders...")
                open_orders = await mnq_suite.orders.search_open_orders()
                if open_orders:
                    print(f"   ⚠️ Found {len(open_orders)} open orders, cancelling...")
                    for order in open_orders:
                        try:
                            await mnq_suite.orders.cancel_order(order.id)
                            print(f"   ✅ Cancelled order {order.id}")
                        except Exception as e:
                            print(f"   ⚠️ Could not cancel order {order.id}: {e}")
                else:
                    print("   ✅ No open orders found")

                # Check for open positions
                print("\n🔍 Checking for open positions...")
                positions = await mnq_suite.positions.get_all_positions()
                if positions:
                    print(f"   ⚠️ Found {len(positions)} open positions")
                    for pos in positions:
                        print(f"      - {pos.contractId}: {pos.size} contracts")
                else:
                    print("   ✅ No open positions found")

                print("\n✅ Cleanup successful!")

            except Exception as e:
                print(f"\n⚠️ Error during cleanup: {e}")

            if suite:
                # Disconnect
                print("\n" + "=" * 60)
                print("Disconnecting...")
                await suite.disconnect()
                print("✅ Example complete!")

        print("\nKey Takeaways:")
        print("• SDK provides comprehensive statistics without UI components")
        print("• All statistics are easily accessible via async methods")
        print("• Export formats support external monitoring systems")
        print("• Statistics can drive adaptive strategy behavior")
        print("• Memory and performance metrics help prevent issues")
        print("• Always clean up open orders and positions on exit")


if __name__ == "__main__":
    asyncio.run(main())
