#!/usr/bin/env python3
"""
Test script to verify that timestamp filtering works correctly with polars and timezone-aware datetimes.
This helps debug the monitoring period issue in the orderbook example.
"""

import polars as pl
import pytz
from datetime import datetime, timedelta

# Set up Chicago timezone (same as the trading system)
chicago_tz = pytz.timezone("America/Chicago")

print("🧪 Testing Timestamp Filtering Logic")
print("="*50)

# Create some test trade data with timestamps
current_time = datetime.now(chicago_tz)
monitoring_start = current_time - timedelta(seconds=30)

print(f"Current time: {current_time.strftime('%H:%M:%S.%f')}")
print(f"Monitoring start: {monitoring_start.strftime('%H:%M:%S.%f')}")

# Create test trades - some before monitoring, some after
test_trades = []

# Add trades from 2 minutes ago (before monitoring)
for i in range(5):
    trade_time = current_time - timedelta(minutes=2) + timedelta(seconds=i*10)
    test_trades.append({
        "price": 23050.0 + i,
        "volume": 100 + i*10,
        "timestamp": trade_time,
        "side": "buy" if i % 2 == 0 else "sell"
    })

# Add trades from during monitoring period
for i in range(3):
    trade_time = monitoring_start + timedelta(seconds=i*10)
    test_trades.append({
        "price": 23055.0 + i,
        "volume": 200 + i*10,
        "timestamp": trade_time,
        "side": "buy" if i % 2 == 0 else "sell"
    })

# Create DataFrame
trades_df = pl.DataFrame(test_trades)

print(f"\n📊 Test Data Created:")
print(f"   Total trades: {len(trades_df)}")
print(f"   Oldest trade: {trades_df.select(pl.col('timestamp').min()).item().strftime('%H:%M:%S.%f')}")
print(f"   Newest trade: {trades_df.select(pl.col('timestamp').max()).item().strftime('%H:%M:%S.%f')}")

# Test the filtering
monitoring_trades = trades_df.filter(pl.col("timestamp") >= monitoring_start)

print(f"\n🔍 Filtering Test:")
print(f"   Trades after monitoring start: {len(monitoring_trades)}")
print(f"   Expected: 3 trades (the ones added during monitoring)")

if len(monitoring_trades) == 3:
    print("✅ Timestamp filtering works correctly!")
    
    # Show the filtered trades
    print(f"\n📋 Filtered Trades:")
    for row in monitoring_trades.iter_rows():
        price, volume, timestamp, side = row
        print(f"   {timestamp.strftime('%H:%M:%S.%f')}: {side} {volume} @ {price}")
        
else:
    print("❌ Timestamp filtering is not working as expected!")
    print(f"\n📋 All Trades:")
    for row in trades_df.iter_rows():
        price, volume, timestamp, side = row
        is_after = "✓" if timestamp >= monitoring_start else "✗"
        print(f"   {is_after} {timestamp.strftime('%H:%M:%S.%f')}: {side} {volume} @ {price}")

print(f"\n💡 This test helps verify that the polars timestamp filtering logic")
print(f"   used in the orderbook example should work correctly.")
print(f"   If this test passes but the orderbook example still shows")
print(f"   identical values, then all trades in memory are probably")
print(f"   from after the monitoring start time.") 