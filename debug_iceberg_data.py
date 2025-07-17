#!/usr/bin/env python3
"""
Debug Script: Iceberg Detection Data Analysis
============================================

This script analyzes the current state of orderbook data to understand
why iceberg detection isn't finding any results.
"""

import time
from datetime import datetime, timedelta
from project_x_py import ProjectX
from src.project_x_py.realtime_data_manager import ProjectXRealtimeDataManager

def debug_iceberg_data():
    """Analyze current orderbook state for iceberg detection debugging."""
    
    print("🔍 ICEBERG DETECTION DEBUG ANALYSIS")
    print("=" * 60)
    
    # Initialize (same as your main script)
    project_x = ProjectX(
        username="jeffw102",
        api_key="Q1yl6AVP0aWGigl176fLN5O7gooUaJGTaSLUtKQMoZE="
    )
    
    # Initialize data manager
    data_manager = ProjectXRealtimeDataManager(
        instrument="MNQ",
        project_x=project_x,
        account_id="your_account_id_here",
        timeframes=["15sec", "1min", "5min"]
    )
    
    # Load historical data
    print("📊 Loading historical data...")
    if not data_manager.initialize():
        print("❌ Failed to initialize data manager")
        return
    
    # Start real-time feed (if possible)
    print("🚀 Starting real-time feed...")
    try:
        jwt_token = project_x.get_session_token()
        feed_started = data_manager.start_realtime_feed(jwt_token)
        print(f"✅ Real-time feed: {'Started' if feed_started else 'Failed'}")
    except Exception as e:
        print(f"⚠️ Real-time feed unavailable: {e}")
        feed_started = False
    
    # Wait a bit for data to accumulate
    if feed_started:
        print("⏳ Waiting 30 seconds for orderbook data...")
        time.sleep(30)
    
    print("\n" + "=" * 60)
    print("📊 CURRENT DATA STATUS")
    print("=" * 60)
    
    # 1. Check orderbook data
    print("\n1️⃣ ORDERBOOK STATUS:")
    bids = data_manager.get_orderbook_bids(levels=20)
    asks = data_manager.get_orderbook_asks(levels=20)
    
    print(f"   📈 Bid levels: {len(bids)}")
    print(f"   📉 Ask levels: {len(asks)}")
    
    if len(bids) > 0:
        print(f"   💰 Best bid: ${bids.select('price').head(1).item():.2f}")
        print(f"   📦 Bid volume: {bids.select('volume').head(1).item():,}")
        print(f"   🕐 Last bid update: {bids.select('timestamp').head(1).item()}")
    else:
        print("   ❌ No bid data available")
    
    if len(asks) > 0:
        print(f"   💰 Best ask: ${asks.select('price').head(1).item():.2f}")
        print(f"   📦 Ask volume: {asks.select('volume').head(1).item():,}")
        print(f"   🕐 Last ask update: {asks.select('timestamp').head(1).item()}")
    else:
        print("   ❌ No ask data available")
    
    # 2. Check trade flow data
    print("\n2️⃣ TRADE FLOW STATUS:")
    trades = data_manager.get_recent_trades(count=100)
    print(f"   🔄 Recent trades: {len(trades)}")
    
    if len(trades) > 0:
        latest_trade = trades.tail(1)
        print(f"   💰 Latest trade: ${latest_trade.select('price').item():.2f}")
        print(f"   📦 Trade volume: {latest_trade.select('volume').item():,}")
        print(f"   🕐 Last trade: {latest_trade.select('timestamp').item()}")
        
        # Trade flow summary
        trade_summary = data_manager.get_trade_flow_summary(minutes=10)
        print(f"   📊 10min volume: {trade_summary['total_volume']:,}")
        print(f"   📈 Buy volume: {trade_summary['buy_volume']:,}")
        print(f"   📉 Sell volume: {trade_summary['sell_volume']:,}")
    else:
        print("   ❌ No trade data available")
    
    # 3. Check data age and freshness
    print("\n3️⃣ DATA FRESHNESS:")
    current_time = datetime.now(data_manager.timezone)
    
    if hasattr(data_manager, 'last_orderbook_update') and data_manager.last_orderbook_update:
        age = (current_time - data_manager.last_orderbook_update).total_seconds()
        print(f"   🕐 Last orderbook update: {age:.1f} seconds ago")
        if age > 300:  # 5 minutes
            print("   ⚠️ Orderbook data is stale (>5 minutes old)")
    else:
        print("   ❌ No orderbook updates recorded")
    
    # 4. Analyze why no icebergs detected
    print("\n4️⃣ ICEBERG DETECTION ANALYSIS:")
    
    # Check data requirements
    has_sufficient_bids = len(bids) >= 5
    has_sufficient_asks = len(asks) >= 5
    has_trade_data = len(trades) > 0
    
    print(f"   📊 Sufficient bid levels (≥5): {'✅' if has_sufficient_bids else '❌'} ({len(bids)})")
    print(f"   📊 Sufficient ask levels (≥5): {'✅' if has_sufficient_asks else '❌'} ({len(asks)})")
    print(f"   🔄 Has trade data: {'✅' if has_trade_data else '❌'} ({len(trades)})")
    
    # Check for potential iceberg conditions
    if len(bids) > 0 and len(asks) > 0:
        print("\n   🔍 POTENTIAL ICEBERG CONDITIONS:")
        
        # Look for large volumes
        all_volumes = []
        if len(bids) > 0:
            bid_volumes = bids.select('volume').to_series().to_list()
            all_volumes.extend(bid_volumes)
        if len(asks) > 0:
            ask_volumes = asks.select('volume').to_series().to_list()
            all_volumes.extend(ask_volumes)
        
        if all_volumes:
            max_volume = max(all_volumes)
            avg_volume = sum(all_volumes) / len(all_volumes)
            print(f"   📦 Max volume: {max_volume:,}")
            print(f"   📊 Avg volume: {avg_volume:.1f}")
            print(f"   💪 Large orders (>500): {sum(1 for v in all_volumes if v > 500)}")
            print(f"   🏛️ Institutional size (>1000): {sum(1 for v in all_volumes if v > 1000)}")
        
        # Check for round number pricing
        all_prices = []
        if len(bids) > 0:
            bid_prices = bids.select('price').to_series().to_list()
            all_prices.extend(bid_prices)
        if len(asks) > 0:
            ask_prices = asks.select('price').to_series().to_list()
            all_prices.extend(ask_prices)
        
        if all_prices:
            round_prices = [p for p in all_prices if p % 1.0 == 0 or p % 0.5 == 0]
            print(f"   🎯 Round number prices: {len(round_prices)}/{len(all_prices)}")
    
    # 5. Recommendations
    print("\n5️⃣ RECOMMENDATIONS:")
    
    if not feed_started:
        print("   🔧 Start real-time feed for live orderbook data")
        print("   📡 Ensure WebSocket connection is working")
    
    if len(bids) == 0 or len(asks) == 0:
        print("   ⏳ Wait longer for orderbook data to accumulate")
        print("   🔄 Check if market is active (trading hours)")
    
    if len(trades) == 0:
        print("   📈 Wait for trade executions to generate flow data")
        print("   🎯 Iceberg detection works best during active trading")
    
    print("   ⏰ For best results, run during active market hours:")
    print("     • Futures: 6PM-5PM CT (next day)")
    print("     • Most active: 9:30AM-4PM ET")
    
    print("\n" + "=" * 60)
    print("💡 SUMMARY")
    print("=" * 60)
    
    if not feed_started or len(bids) == 0:
        print("🔍 Root Cause: Insufficient real-time orderbook data")
        print("✅ Solution: Ensure live WebSocket feed + wait 15-30 minutes")
    elif len(trades) == 0:
        print("🔍 Root Cause: No trade execution data for pattern validation")
        print("✅ Solution: Wait for market activity during trading hours")
    else:
        print("🔍 Root Cause: Insufficient time for iceberg patterns to develop")
        print("✅ Solution: Monitor for 30+ minutes during active trading")
    
    print("\n🎯 Expected Timeline:")
    print("   • 5-10 minutes: Basic orderbook population")
    print("   • 15-20 minutes: Simple iceberg detection possible")
    print("   • 30+ minutes: Advanced iceberg detection optimal")
    print("   • 1+ hours: High-confidence institutional detection")

if __name__ == "__main__":
    debug_iceberg_data() 