#!/usr/bin/env python3
"""
Level 2 Orderbook Usage Example

This example demonstrates how to use the real-time Level 2 orderbook functionality
with the ProjectX Real-time Data Manager.

Author: TexasCoding
Date: July 2025
"""

import time
from project_x_py import ProjectX, setup_logging
from project_x_py.realtime_data_manager import ProjectXRealtimeDataManager

# Setup logging
setup_logging()

def print_orderbook_summary(manager):
    """Print a summary of the current orderbook state."""
    # Get best bid/ask
    best_prices = manager.get_best_bid_ask()
    print(f"\n📊 Best Bid/Ask:")
    print(f"   Bid: ${best_prices['bid']:.2f}" if best_prices['bid'] else "   Bid: None")
    print(f"   Ask: ${best_prices['ask']:.2f}" if best_prices['ask'] else "   Ask: None") 
    print(f"   Spread: ${best_prices['spread']:.2f}" if best_prices['spread'] else "   Spread: None")
    print(f"   Mid: ${best_prices['mid']:.2f}" if best_prices['mid'] else "   Mid: None")

def print_orderbook_levels(manager):
    """Print the top orderbook levels."""
    print(f"\n📈 Top 5 Orderbook Levels:")
    
    # Get top 5 levels
    bids = manager.get_orderbook_bids(levels=5)
    asks = manager.get_orderbook_asks(levels=5)
    
    print("   ASKS (Sellers)")
    if len(asks) > 0:
        for row in asks.iter_rows():
            price, volume, timestamp, order_type = row
            print(f"   ${price:8.2f} | {volume:4d} contracts")
    else:
        print("   No ask data available")
    
    print("   " + "-" * 25)
    
    print("   BIDS (Buyers)")
    if len(bids) > 0:
        for row in bids.iter_rows():
            price, volume, timestamp, order_type = row
            print(f"   ${price:8.2f} | {volume:4d} contracts")
    else:
        print("   No bid data available")

def print_orderbook_depth_analysis(manager):
    """Print orderbook depth analysis."""
    depth = manager.get_orderbook_depth(price_range=20.0)  # 20 point range
    
    print(f"\n🔍 Orderbook Depth Analysis (±20 points):")
    print(f"   Bid Volume: {depth['bid_volume']:,} contracts ({depth['bid_levels']} levels)")
    print(f"   Ask Volume: {depth['ask_volume']:,} contracts ({depth['ask_levels']} levels)")
    print(f"   Mid Price: ${depth.get('mid_price', 0):.2f}")
    
    # Calculate imbalance
    total_volume = depth['bid_volume'] + depth['ask_volume']
    if total_volume > 0:
        bid_ratio = depth['bid_volume'] / total_volume * 100
        ask_ratio = depth['ask_volume'] / total_volume * 100
        print(f"   Volume Imbalance: {bid_ratio:.1f}% bids / {ask_ratio:.1f}% asks")

def print_trade_flow_analysis(manager, monitoring_start_time=None):
    """Print trade flow analysis with both monitoring period and 5-minute data"""
    print("\n💹 Trade Flow Analysis:")
    
    # Get 5-minute summary for market context
    trade_summary_5min = manager.get_trade_flow_summary(minutes=5)
    print(f"   📊 Last 5 minutes (Market Context):")
    print(f"      Total Volume: {trade_summary_5min['total_volume']:,} contracts")
    print(f"      Total Trades: {trade_summary_5min['trade_count']}")
    print(f"      Buy Volume: {trade_summary_5min['buy_volume']:,} contracts ({trade_summary_5min['buy_trades']} trades)")
    print(f"      Sell Volume: {trade_summary_5min['sell_volume']:,} contracts ({trade_summary_5min['sell_trades']} trades)")
    print(f"      Avg Trade Size: {trade_summary_5min['avg_trade_size']:.1f} contracts")
    print(f"      VWAP: ${trade_summary_5min['vwap']:.2f}")
    print(f"      Buy/Sell Ratio: {trade_summary_5min['buy_sell_ratio']:.2f}")
    
    # If we have a monitoring start time, also show data just for the monitoring period
    if monitoring_start_time:
        # Get trades only from monitoring period
        import polars as pl
        from datetime import datetime
        
        with manager.orderbook_lock:
            if len(manager.recent_trades) > 0:
                # Debug: Show timestamp info
                all_trades = manager.recent_trades
                if len(all_trades) > 0:
                    oldest_trade = all_trades.select(pl.col("timestamp").min()).item()
                    newest_trade = all_trades.select(pl.col("timestamp").max()).item()
                    print(f"\n   🔍 Debug Info:")
                    print(f"      Monitoring started: {monitoring_start_time.strftime('%H:%M:%S.%f')}")
                    print(f"      Oldest trade in memory: {oldest_trade.strftime('%H:%M:%S.%f') if oldest_trade else 'None'}")
                    print(f"      Newest trade in memory: {newest_trade.strftime('%H:%M:%S.%f') if newest_trade else 'None'}")
                    print(f"      Total trades in memory: {len(all_trades)}")
                
                monitoring_trades = manager.recent_trades.filter(
                    pl.col("timestamp") >= monitoring_start_time
                )
                
                print(f"      Trades after monitoring start: {len(monitoring_trades)}")
                
                if len(monitoring_trades) > 0:
                    # Calculate monitoring period statistics
                    monitoring_duration = (datetime.now(manager.timezone) - monitoring_start_time).total_seconds()
                    total_volume = int(monitoring_trades.select(pl.col("volume").sum()).item())
                    trade_count = len(monitoring_trades)
                    
                    buy_trades = monitoring_trades.filter(pl.col("side") == "buy")
                    sell_trades = monitoring_trades.filter(pl.col("side") == "sell")
                    
                    buy_volume = int(buy_trades.select(pl.col("volume").sum()).item()) if len(buy_trades) > 0 else 0
                    sell_volume = int(sell_trades.select(pl.col("volume").sum()).item()) if len(sell_trades) > 0 else 0
                    
                    buy_count = len(buy_trades)
                    sell_count = len(sell_trades)
                    
                    avg_trade_size = total_volume / trade_count if trade_count > 0 else 0
                    buy_sell_ratio = buy_volume / sell_volume if sell_volume > 0 else float('inf') if buy_volume > 0 else 0
                    
                    print(f"\n   ⏱️ Monitoring Period Only ({monitoring_duration:.1f} seconds):")
                    print(f"      Total Volume: {total_volume:,} contracts")
                    print(f"      Total Trades: {trade_count}")
                    print(f"      Buy Volume: {buy_volume:,} contracts ({buy_count} trades)")
                    print(f"      Sell Volume: {sell_volume:,} contracts ({sell_count} trades)")
                    print(f"      Avg Trade Size: {avg_trade_size:.1f} contracts")
                    print(f"      Buy/Sell Ratio: {buy_sell_ratio:.2f}")
                    
                    # Calculate per-second rates
                    if monitoring_duration > 0:
                        volume_per_second = total_volume / monitoring_duration
                        trades_per_second = trade_count / monitoring_duration
                        print(f"      📈 Rate: {volume_per_second:.1f} contracts/sec, {trades_per_second:.2f} trades/sec")
                        
                        # Warn if rates seem too high
                        if volume_per_second > 500:  # More than 500 contracts/second is very high
                            print(f"      ⚠️ Warning: Volume rate seems very high - check if all trades are really from monitoring period")
                else:
                    print(f"\n   ⏱️ Monitoring Period: No trades during monitoring window")
            else:
                print(f"\n   ⏱️ Monitoring Period: No trade data available")

def print_order_statistics(manager):
    """Print order type statistics."""
    order_stats = manager.get_order_type_statistics()
    
    print(f"\n📊 Order Type Statistics:")
    print(f"   Type 1 (Asks): {order_stats['type_1_count']:,}")
    print(f"   Type 2 (Bids): {order_stats['type_2_count']:,}")
    print(f"   Type 5 (Trades): {order_stats['type_5_count']:,}")
    print(f"   Type 9 (Modifications): {order_stats['type_9_count']:,}")
    print(f"   Type 10 (Modifications): {order_stats['type_10_count']:,}")
    print(f"   Other Types: {order_stats['other_types']:,}")

def print_final_snapshot(manager, monitoring_start_time):
    """Print final orderbook snapshot and monitoring summary."""
    print("\n" + "="*50)
    print("📸 FINAL ORDERBOOK SNAPSHOT")
    print("="*50)
    
    snapshot = manager.get_orderbook_snapshot(levels=10)
    metadata = snapshot['metadata']
    
    print(f"Best Bid: ${metadata.get('best_bid', 0):.2f}")
    print(f"Best Ask: ${metadata.get('best_ask', 0):.2f}")
    print(f"Spread: ${metadata.get('spread', 0):.2f}")
    print(f"Mid Price: ${metadata.get('mid_price', 0):.2f}")
    print(f"Total Bid Volume: {metadata.get('total_bid_volume', 0):,} contracts")
    print(f"Total Ask Volume: {metadata.get('total_ask_volume', 0):,} contracts")
    print(f"Bid Levels: {metadata.get('levels_count', {}).get('bids', 0)}")
    print(f"Ask Levels: {metadata.get('levels_count', {}).get('asks', 0)}")
    print(f"Last Update: {metadata.get('last_update', 'Never')}")
    
    # Show sample of the DataFrames
    print(f"\n📊 Sample Bid Data (Polars DataFrame):")
    print(snapshot['bids'].head(5))
    
    print(f"\n📊 Sample Ask Data (Polars DataFrame):")
    print(snapshot['asks'].head(5))
    
    # Show recent trades
    recent_trades = manager.get_recent_trades(count=10)
    print(f"\n💹 Recent Trades (Polars DataFrame):")
    print(recent_trades)

def main():
    print("🚀 Starting Level 2 Orderbook Example")
    
    try:
        print("🔐 Authenticating with ProjectX...")
        project_x = ProjectX(username="jeffw102", api_key="Q1yl6AVP0aWGigl176fLN5O7gooUaJGTaSLUtKQMoZE=")
        account = project_x.get_account_info()
        if not account:
            raise ValueError("No account found")
        account_id = str(account.id)
        print(f"✅ Account ID: {account_id}")
        
        print("📊 Initializing real-time data manager for MNQ...")
        manager = ProjectXRealtimeDataManager("MNQ", project_x, account_id)
        
        if not manager.initialize():
            print("❌ Failed to initialize data manager")
            return
        print("✅ Historical data loaded")
        
        jwt_token = project_x.get_session_token()
        if not manager.start_realtime_feed(jwt_token):
            print("❌ Failed to start real-time feed") 
            return
        print("✅ Real-time feed started - collecting orderbook data...")
        
        # Track monitoring start time
        from datetime import datetime
        monitoring_start_time = datetime.now(manager.timezone)
        print(f"🕐 Monitoring started at: {monitoring_start_time.strftime('%H:%M:%S')}")
        
        # Optional: Clear trade history for clean monitoring period measurement
        # Uncomment the next line if you want to measure only trades during monitoring
        # manager.clear_recent_trades()
        # print("🧹 Cleared trade history for clean monitoring period")
        
        print("\n" + "="*50)
        print("📊 LEVEL 2 ORDERBOOK MONITOR")
        print("="*50)
        print("Monitoring MNQ orderbook for 30 seconds...")
        print("Press Ctrl+C to stop")
        
        import time
        for i in range(30):
            time.sleep(1)
            print(f"\n⏰ Update {i+1}/30")
            
            # Show current best bid/ask
            best_prices = manager.get_best_bid_ask()
            print(f"\n📊 Best Bid/Ask:")
            print(f"   Bid: ${best_prices['bid']:.2f}" if best_prices['bid'] else "   Bid: None")
            print(f"   Ask: ${best_prices['ask']:.2f}" if best_prices['ask'] else "   Ask: None") 
            print(f"   Spread: ${best_prices['spread']:.2f}" if best_prices['spread'] else "   Spread: None")
            print(f"   Mid: ${best_prices['mid']:.2f}" if best_prices['mid'] else "   Mid: None")
            
            # Show detailed analysis every 5 seconds
            if (i + 1) % 5 == 0:
                print_orderbook_levels(manager)
                print_orderbook_depth_analysis(manager)
                print_trade_flow_analysis(manager, monitoring_start_time)
                print_order_statistics(manager)
        
        print("\n✅ Monitoring complete!")
        print_final_snapshot(manager, monitoring_start_time)
        
    except KeyboardInterrupt:
        print("\n🛑 Stopped by user")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'manager' in locals():
            manager.stop_realtime_feed()
            print("✅ Real-time feed stopped")

if __name__ == "__main__":
    main() 