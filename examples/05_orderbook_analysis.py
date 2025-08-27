#!/usr/bin/env python3
"""
Async Level 2 Orderbook Analysis Example

Demonstrates comprehensive Level 2 orderbook analysis using async/await:
- Real-time bid/ask levels and depth
- Market microstructure analysis
- Trade flow analysis
- Order type statistics
- Iceberg detection
- Market imbalance monitoring
- Best bid/ask tracking

Uses MNQ for Level 2 orderbook data with OrderBook.

Updated for v3.0.0: Uses new TradingSuite for simplified initialization.

Usage:
    Run with: ./test.sh (sets environment variables)
    Or: uv run examples/05_orderbook_analysis.py

Note: This example includes several wait periods:
    - 5 seconds for initial data population
    - 45 seconds for real-time monitoring
    - 2 minutes before comprehensive method demonstration
    Total runtime is approximately 3 minutes.

Author: TexasCoding
Date: July 2025
"""

import asyncio
import sys
import time
from datetime import datetime

from project_x_py import (
    TradingSuite,
    setup_logging,
)
from project_x_py.orderbook import OrderBook


async def display_best_prices(orderbook: OrderBook) -> None:
    """Display current best bid/ask prices."""
    best_prices = await orderbook.get_best_bid_ask()
    best_bid = best_prices.get("bid")
    best_ask = best_prices.get("ask")
    spread = best_prices.get("spread")

    print("📊 Best Bid/Ask:", flush=True)
    if best_bid is not None and best_ask is not None:
        # Get top level bids/asks to get sizes
        bids_df = await orderbook.get_orderbook_bids(levels=1)
        asks_df = await orderbook.get_orderbook_asks(levels=1)

        bid_size = bids_df["volume"].item() if bids_df.height > 0 else 0
        ask_size = asks_df["volume"].item() if asks_df.height > 0 else 0

        mid_price = (best_bid + best_ask) / 2

        print(f"   Best Bid: ${best_bid:,.2f} x {bid_size}", flush=True)
        print(f"   Best Ask: ${best_ask:,.2f} x {ask_size}", flush=True)
        print(f"   Spread: ${spread:.2f}", flush=True)
        print(f"   Mid: ${mid_price:,.2f}", flush=True)
    else:
        print("   No bid/ask available", flush=True)


async def display_market_depth(orderbook: OrderBook) -> None:
    """Display market depth on both sides."""
    # Get bid and ask levels separately
    bids_df = await orderbook.get_orderbook_bids(levels=5)
    asks_df = await orderbook.get_orderbook_asks(levels=5)

    print("\n📈 Market Depth (Top 5 Levels):", flush=True)

    # Display bids
    print("\n   BIDS:", flush=True)
    total_bid_size = 0
    if not bids_df.is_empty():
        for i, row in enumerate(bids_df.to_dicts()):
            total_bid_size += row["volume"]
            print(
                f"   Level {i + 1}: ${row['price']:,.2f} x {row['volume']:>4} | "
                f"Total: {total_bid_size:>5}",
                flush=True,
            )
    else:
        print("   No bids available", flush=True)

    # Display asks
    print("\n   ASKS:", flush=True)
    total_ask_size = 0
    if not asks_df.is_empty():
        for i, row in enumerate(asks_df.to_dicts()):
            total_ask_size += row["volume"]
            print(
                f"   Level {i + 1}: ${row['price']:,.2f} x {row['volume']:>4} | "
                f"Total: {total_ask_size:>5}",
                flush=True,
            )
    else:
        print("   No asks available", flush=True)

    if total_bid_size > 0 and total_ask_size > 0:
        imbalance = (total_bid_size - total_ask_size) / (
            total_bid_size + total_ask_size
        )
        print(f"\n   Imbalance: {imbalance:.2%} ", end="", flush=True)
        if imbalance > 0.1:
            print("(Bid Heavy 🟢)", flush=True)
        elif imbalance < -0.1:
            print("(Ask Heavy 🔴)", flush=True)
        else:
            print("(Balanced ⚖️)", flush=True)


async def display_trade_flow(orderbook: OrderBook) -> None:
    """Display recent trade flow analysis."""
    trades = await orderbook.get_recent_trades(count=10)

    if not trades:
        print("\n📉 No recent trades available", flush=True)
        return

    print(f"\n📉 Recent Trade Flow ({len(trades)} trades):", flush=True)

    buy_volume = sum(t["volume"] for t in trades if t.get("side") == "buy")
    sell_volume = sum(t["volume"] for t in trades if t.get("side") == "sell")
    total_volume = buy_volume + sell_volume

    if total_volume > 0:
        print(
            f"   Buy Volume: {buy_volume:,} ({buy_volume / total_volume:.1%})",
            flush=True,
        )
        print(
            f"   Sell Volume: {sell_volume:,} ({sell_volume / total_volume:.1%})",
            flush=True,
        )

    # Show last 5 trades
    print("\n   Last 5 Trades:", flush=True)
    for trade in trades[:5]:
        side_emoji = "🟢" if trade.get("side") == "buy" else "🔴"
        timestamp = trade.get("timestamp", "")
        if isinstance(timestamp, datetime):
            timestamp = timestamp.strftime("%H:%M:%S")
        print(
            f"   {side_emoji} ${trade['price']:,.2f} x {trade['volume']} @ {timestamp}",
            flush=True,
        )


async def display_market_microstructure(orderbook: OrderBook) -> None:
    """Display market microstructure analysis."""
    # Use get_advanced_market_metrics instead
    try:
        microstructure = await orderbook.get_advanced_market_metrics()
    except AttributeError:
        # Fallback to basic stats if method doesn't exist
        microstructure = await orderbook.get_statistics()

    print("\n🔬 Market Microstructure:", flush=True)
    print(f"   Bid Depth: {microstructure.get('bid_depth', 0)} levels", flush=True)
    print(f"   Ask Depth: {microstructure.get('ask_depth', 0)} levels", flush=True)
    print(f"   Total Bid Size: {microstructure.get('total_bid_size', 0):,}", flush=True)
    print(f"   Total Ask Size: {microstructure.get('total_ask_size', 0):,}", flush=True)

    if microstructure.get("avg_bid_size", 0) > 0:
        print(
            f"   Avg Bid Size: {microstructure.get('avg_bid_size', 0):.1f}", flush=True
        )
    if microstructure.get("avg_ask_size", 0) > 0:
        print(
            f"   Avg Ask Size: {microstructure.get('avg_ask_size', 0):.1f}", flush=True
        )

    # Price levels
    if microstructure.get("price_levels"):
        print(f"   Unique Price Levels: {microstructure['price_levels']}", flush=True)

    # Order clustering
    if microstructure.get("order_clustering"):
        print(
            f"   Order Clustering: {microstructure['order_clustering']:.2f}",
            flush=True,
        )


async def display_iceberg_detection(orderbook: OrderBook) -> None:
    """Display potential iceberg orders."""
    # Use detect_iceberg_orders instead of detect_icebergs
    icebergs = await orderbook.detect_iceberg_orders(
        min_refreshes=5,
        volume_threshold=50,
        time_window_minutes=10,
    )

    print("\n🧊 Iceberg Detection:", flush=True)
    if icebergs and "iceberg_levels" in icebergs:
        iceberg_list = icebergs["iceberg_levels"]
        if iceberg_list:
            for iceberg in iceberg_list[:3]:  # Show top 3
                side = "BID" if iceberg["side"] == "bid" else "ASK"
                print(
                    f"   Potential {side} iceberg at ${iceberg['price']:,.2f}",
                    flush=True,
                )
                print(
                    f"     - Avg Volume: {iceberg.get('avg_volume', 'N/A'):.1f}",
                    flush=True,
                )
                print(
                    f"     - Refresh Count: {iceberg.get('refresh_count', 'N/A')}",
                    flush=True,
                )
                print(
                    f"     - Replenishments: {iceberg.get('replenishment_count', 'N/A')}",
                    flush=True,
                )
                print(
                    f"     - Confidence: {iceberg.get('confidence', 0):.1%}", flush=True
                )
        else:
            print("   No iceberg orders detected", flush=True)
    else:
        print("   No iceberg orders detected", flush=True)


async def monitor_orderbook_realtime(orderbook: OrderBook, duration: int = 45) -> None:
    """Monitor orderbook in real-time for specified duration."""
    print(f"\n🔄 Real-time Monitoring ({duration} seconds)...", flush=True)
    print("=" * 60, flush=True)

    start_time = time.time()
    update_interval = 5  # seconds

    while time.time() - start_time < duration:
        elapsed = int(time.time() - start_time)
        print(f"\n⏰ Update at {elapsed}s:", flush=True)

        # Show best prices
        await display_best_prices(orderbook)

        # Show depth summary
        bids_df = await orderbook.get_orderbook_bids(levels=3)
        asks_df = await orderbook.get_orderbook_asks(levels=3)
        if not bids_df.is_empty() and not asks_df.is_empty():
            bid_size = bids_df["volume"].sum()
            ask_size = asks_df["volume"].sum()
            print(f"\n   Top 3 Levels: {bid_size} bids | {ask_size} asks", flush=True)

        # Show recent trade
        trades = await orderbook.get_recent_trades(count=1)
        if trades:
            trade = trades[0]
            side_emoji = "🟢" if trade.get("side") == "buy" else "🔴"
            print(
                f"   Last Trade: {side_emoji} ${trade['price']:,.2f} x {trade['volume']}",
                flush=True,
            )

        await asyncio.sleep(update_interval)

    print("\n✅ Real-time monitoring completed", flush=True)


async def demonstrate_comprehensive_methods(orderbook: OrderBook) -> None:
    """Demonstrate all comprehensive orderbook methods after 2 minutes."""
    print("\n⏰ Waiting 2 minutes for data accumulation...", flush=True)
    print(
        "   (This ensures we have enough data for comprehensive analysis)", flush=True
    )

    # Show countdown
    for i in range(4):
        remaining = 120 - (i * 30)
        print(f"   {remaining} seconds remaining...", flush=True)
        await asyncio.sleep(30)

    print("\n🎯 Demonstrating Comprehensive Methods:", flush=True)
    print("=" * 60, flush=True)

    # 1. Volume Profile Analysis
    print("\n📊 Volume Profile Analysis:", flush=True)
    try:
        volume_profile = await orderbook.get_volume_profile(price_bins=10)
        if volume_profile and "profile" in volume_profile:
            print("   Price Range | Volume | Percentage", flush=True)
            print("   " + "-" * 40, flush=True)
            profile_data = volume_profile["profile"]
            for level in profile_data[:5]:  # Show top 5
                price_range = f"${level['price_min']:.2f}-${level['price_max']:.2f}"
                volume = level["volume"]
                percentage = level.get("percentage", 0)
                print(
                    f"   {price_range:<15} | {volume:>6,} | {percentage:>5.1f}%",
                    flush=True,
                )
        else:
            print("   No volume profile data available", flush=True)
    except Exception as e:
        print(f"   Error: {e}", flush=True)

    # 2. Order Type Statistics
    print("\n📈 Order Type Statistics:", flush=True)
    try:
        order_stats = await orderbook.get_order_type_statistics()
        if order_stats:
            # The stats are tracked by DomType numbers
            total_events = sum(
                v for k, v in order_stats.items() if k.startswith("type_")
            )
            if total_events > 0:
                print(f"   Total Events: {total_events:,}", flush=True)
                # Show top event types
                top_types = sorted(
                    [(k, v) for k, v in order_stats.items() if k.startswith("type_")],
                    key=lambda x: x[1],
                    reverse=True,
                )[:5]
                for type_key, count in top_types:
                    if count > 0:
                        type_num = type_key.replace("type_", "").replace("_count", "")
                        print(f"   Type {type_num}: {count:,} events", flush=True)
            else:
                print("   No order statistics available", flush=True)
        else:
            print("   No order statistics available", flush=True)
    except Exception as e:
        print(f"   Error: {e}", flush=True)

    # 3. Market Impact Analysis
    print("\n💥 Market Impact Analysis:", flush=True)
    try:
        # Use get_orderbook_depth for market impact analysis
        impact = await orderbook.get_orderbook_depth(price_range=50.0)
        if impact:
            print("   Market Impact Analysis (50 tick range):", flush=True)
            print(
                f"   Estimated Fill Price: ${impact.get('estimated_fill_price', 0):,.2f}",
                flush=True,
            )
            print(
                f"   Price Impact: {impact.get('price_impact_pct', 0):.2%}", flush=True
            )
            print(f"   Spread Cost: ${impact.get('spread_cost', 0):,.2f}", flush=True)
            if impact.get("levels_consumed"):
                print(f"   Levels Consumed: {impact['levels_consumed']}", flush=True)
        else:
            print("   Insufficient depth for impact analysis", flush=True)
    except Exception as e:
        print(f"   Error: {e}", flush=True)

    # 4. Liquidity Analysis
    print("\n💧 Liquidity Analysis:", flush=True)
    try:
        # Use get_liquidity_levels instead
        liquidity = await orderbook.get_liquidity_levels()
        if liquidity and "bid_levels" in liquidity:
            bid_levels = liquidity.get("bid_levels", [])
            ask_levels = liquidity.get("ask_levels", [])
            bid_liquidity = sum(level.get("volume", 0) for level in bid_levels)
            ask_liquidity = sum(level.get("volume", 0) for level in ask_levels)
            print(
                f"   Bid Liquidity: {bid_liquidity:,} contracts",
                flush=True,
            )
            print(
                f"   Ask Liquidity: {ask_liquidity:,} contracts",
                flush=True,
            )
            print(f"   Significant Bid Levels: {len(bid_levels)}", flush=True)
            print(f"   Significant Ask Levels: {len(ask_levels)}", flush=True)
        else:
            print("   No liquidity data available", flush=True)
    except Exception as e:
        print(f"   Error: {e}", flush=True)

    # 5. Spoofing Detection
    print("\n🎭 Spoofing Detection:", flush=True)
    try:
        # Use detect_order_clusters as spoofing detection proxy
        spoofing = await orderbook.detect_order_clusters()
        if spoofing:  # This is actually order clusters
            for cluster in spoofing[:3]:  # Show top 3
                print(
                    f"   Order cluster at ${cluster.get('center_price', 0):,.2f}:",
                    flush=True,
                )
                print(f"     - Side: {cluster.get('side', 'N/A').upper()}", flush=True)
                print(
                    f"     - Size: {cluster.get('cluster_size', 0)} orders", flush=True
                )
                print(
                    f"     - Total Volume: {cluster.get('total_volume', 0):,}",
                    flush=True,
                )
        else:
            print("   No spoofing patterns detected", flush=True)
    except Exception as e:
        print(f"   Error: {e}", flush=True)

    # 6. Get full snapshot
    print("\n📸 Full Orderbook Snapshot:", flush=True)
    try:
        snapshot = await orderbook.get_orderbook_snapshot()
        if snapshot:
            print(f"   Timestamp: {snapshot.get('timestamp', 'N/A')}", flush=True)
            print(f"   Bid Levels: {len(snapshot.get('bids', []))}", flush=True)
            print(f"   Ask Levels: {len(snapshot.get('asks', []))}", flush=True)
            print(f"   Total Trades: {len(orderbook.recent_trades)}", flush=True)
        else:
            print("   No snapshot available", flush=True)
    except Exception as e:
        print(f"   Error: {e}", flush=True)


async def main() -> bool:
    """Main async orderbook analysis demonstration."""
    logger = setup_logging(level="INFO")
    print("🚀 Async Level 2 Orderbook Analysis Example (v3.0.0)", flush=True)
    print("=" * 60, flush=True)

    # Important note about runtime
    print("\n⚠️  IMPORTANT: This example runs for approximately 3 minutes:", flush=True)
    print("   - 5 seconds: Initial data population", flush=True)
    print("   - 45 seconds: Real-time monitoring", flush=True)
    print("   - 2 minutes: Wait before comprehensive analysis", flush=True)
    print("   - 30 seconds: Comprehensive method demonstrations", flush=True)
    print("\nPress Ctrl+C at any time to stop early.", flush=True)

    try:
        # Initialize TradingSuite v3 with orderbook feature
        print("\n🔑 Initializing TradingSuite v3 with orderbook...", flush=True)

        suite = await TradingSuite.create(
            "MNQ",
            features=["orderbook"],
            timeframes=["1min", "5min"],
        )

        print("✅ TradingSuite created successfully!", flush=True)

        account = suite.client.account_info
        if account:
            print(f"   Account: {account.name}", flush=True)
            print(f"   Balance: ${account.balance:,.2f}", flush=True)
            print(f"   Simulated: {account.simulated}", flush=True)

        # Get orderbook from suite
        orderbook = suite.orderbook
        if not orderbook:
            print("❌ Orderbook not available in suite", flush=True)
            await suite.disconnect()
            return False

        print("\n✅ Orderbook initialized and connected!", flush=True)
        print("   - Real-time depth updates: Active", flush=True)
        print("   - Quote updates: Active", flush=True)
        print("   - Trade feed: Active", flush=True)

        # Wait for initial data
        print("\n⏳ Waiting 5 seconds for initial data population...", flush=True)
        await asyncio.sleep(5)

        # Show initial state
        print("\n" + "=" * 60, flush=True)
        print("📊 INITIAL ORDERBOOK STATE", flush=True)
        print("=" * 60, flush=True)

        await display_best_prices(orderbook)
        await display_market_depth(orderbook)
        await display_trade_flow(orderbook)
        await display_market_microstructure(orderbook)
        await display_iceberg_detection(orderbook)

        # Real-time monitoring
        print("\n" + "=" * 60, flush=True)
        print("📡 REAL-TIME MONITORING", flush=True)
        print("=" * 60, flush=True)

        await monitor_orderbook_realtime(orderbook, duration=45)

        # Comprehensive analysis (after 2 minutes)
        print("\n" + "=" * 60, flush=True)
        print("🔬 COMPREHENSIVE ANALYSIS", flush=True)
        print("=" * 60, flush=True)

        await demonstrate_comprehensive_methods(orderbook)

        # Final statistics
        print("\n" + "=" * 60, flush=True)
        print("📈 FINAL STATISTICS", flush=True)
        print("=" * 60, flush=True)

        # Memory stats
        memory_stats = await orderbook.get_memory_stats()
        print("\n💾 Memory Usage:", flush=True)
        print(f"   Bid Depth: {memory_stats.get('avg_bid_depth', 0):,}", flush=True)
        print(f"   Ask Depth: {memory_stats.get('avg_ask_depth', 0):,}", flush=True)
        print(
            f"   Trades Processed: {memory_stats.get('trades_processed', 0):,}",
            flush=True,
        )
        print(
            f"   Total Volume: {memory_stats.get('total_volume', 0):,}",
            flush=True,
        )

        print("\n✅ Orderbook analysis completed successfully!", flush=True)
        print("\n📝 Key Takeaways:", flush=True)
        print("   - Real-time Level 2 depth with async/await", flush=True)
        print("   - Market microstructure insights", flush=True)
        print("   - Iceberg and spoofing detection", flush=True)
        print("   - Trade flow and liquidity analysis", flush=True)
        print("   - Memory-efficient sliding window design", flush=True)

        await suite.disconnect()
        return True

    except KeyboardInterrupt:
        print("\n⏹️ Orderbook analysis interrupted by user", flush=True)
        return False
    except Exception as e:
        logger.error(f"Orderbook analysis failed: {e}")
        print(f"\n❌ Error: {e}", flush=True)
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
