#!/usr/bin/env python3
"""
Demo script to show the difference between 5-minute trade analysis vs actual monitoring period.

This illustrates why the trade volumes seemed so high in the original example.
"""

from datetime import datetime, timedelta
import random

# Simulate what happens in the real orderbook example
print("🔍 Trade Flow Time Window Analysis Demo")
print("="*50)

# Simulate current time and monitoring start
current_time = datetime.now()
monitoring_start = current_time - timedelta(seconds=30)  # 30 seconds ago
five_min_ago = current_time - timedelta(minutes=5)      # 5 minutes ago

print(f"📅 Current Time: {current_time.strftime('%H:%M:%S')}")
print(f"⏰ Monitoring Started: {monitoring_start.strftime('%H:%M:%S')} (30 seconds ago)")
print(f"📊 5-Minute Window: {five_min_ago.strftime('%H:%M:%S')} (5 minutes ago)")

# Simulate trade data over the last 5 minutes
print(f"\n💹 Simulated Trade Data:")

# Generate realistic trading volumes
# MNQ is very liquid, but let's use realistic numbers
total_5min_volume = 45000  # Contracts in 5 minutes (realistic for active hours)
total_5min_trades = 200

# Only a small portion would be from the monitoring period
monitoring_volume = 1200  # Contracts in 30 seconds (much more reasonable)
monitoring_trades = 12

print(f"   📊 Last 5 Minutes (What you saw in original):")
print(f"      Total Volume: {total_5min_volume:,} contracts")
print(f"      Total Trades: {total_5min_trades}")
print(f"      Avg Trade Size: {total_5min_volume/total_5min_trades:.1f} contracts")
print(f"      Rate: {total_5min_volume/300:.1f} contracts/sec, {total_5min_trades/300:.2f} trades/sec")

print(f"\n   ⏱️ Monitoring Period Only (30 seconds):")
print(f"      Total Volume: {monitoring_volume:,} contracts") 
print(f"      Total Trades: {monitoring_trades}")
print(f"      Avg Trade Size: {monitoring_volume/monitoring_trades:.1f} contracts")
print(f"      Rate: {monitoring_volume/30:.1f} contracts/sec, {monitoring_trades/30:.2f} trades/sec")

print(f"\n🔍 Analysis:")
print(f"   • Original showed {total_5min_volume:,} contracts (5 minutes)")
print(f"   • But you only monitored for 30 seconds")
print(f"   • Actual monitoring period: {monitoring_volume:,} contracts")
print(f"   • Difference: {(total_5min_volume/monitoring_volume):.1f}x higher!")

print(f"\n✅ Solution Applied:")
print(f"   • Now shows BOTH time windows for context")
print(f"   • 5-minute data for market context")
print(f"   • Monitoring period data for what you actually observed")
print(f"   • Clear labeling to avoid confusion")

print(f"\n💡 For Reference:")
print(f"   • MNQ can trade 50,000+ contracts/5min during active hours")
print(f"   • Your monitoring period would be ~1/10th of that")
print(f"   • Original analysis was correct, just wrong time window!") 