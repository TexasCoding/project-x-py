#!/usr/bin/env python3
"""
Iceberg Detection: Simplified vs Advanced Comparison
=====================================================

This demonstrates the key differences between simplified and advanced
iceberg detection approaches using the project-x-py library.
"""

import polars as pl
from datetime import datetime, timedelta
import random
from src.project_x_py.realtime_data_manager import ProjectXRealtimeDataManager

# Mock ProjectX class for demo purposes
class MockProjectX:
    def __init__(self):
        pass

def create_sample_iceberg_data():
    """Create sample data with realistic iceberg patterns."""
    
    # Simulate 2 hours of orderbook data with icebergs
    base_time = datetime.now()
    orderbook_data = []
    trade_data = []
    
    # ICEBERG 1: Large institutional order at $150.00 (round number)
    print("🧊 Simulating iceberg at $150.00...")
    for i in range(120):  # 2 hours of data
        # Iceberg characteristics:
        # - Consistent volume around 1000 shares
        # - Regular refreshes every 10 periods
        # - Slight volume variation to appear natural
        
        base_volume = 1000
        if i % 10 == 0:  # Refresh event
            volume = base_volume  # Exact refresh
        else:
            volume = base_volume + random.randint(-100, 100)  # Natural variation
            
        orderbook_data.append({
            'price': 150.00,
            'volume': volume,
            'timestamp': base_time + timedelta(minutes=i),
            'side': 'bid'
        })
        
        # Simulate trades "eating" the iceberg
        if i % 7 == 0:  # Periodic execution
            trade_data.append({
                'price': 150.00,
                'volume': random.randint(50, 200),
                'timestamp': base_time + timedelta(minutes=i, seconds=30),
                'side': 'sell'
            })
    
    # ICEBERG 2: Medium-sized order at $149.75 (quarter level)
    print("🧊 Simulating iceberg at $149.75...")
    for i in range(80):
        base_volume = 500
        if i % 8 == 0:  # Less frequent refreshes
            volume = base_volume
        else:
            volume = base_volume + random.randint(-75, 75)
            
        orderbook_data.append({
            'price': 149.75,
            'volume': volume,
            'timestamp': base_time + timedelta(minutes=i),
            'side': 'bid'
        })
        
        if i % 9 == 0:
            trade_data.append({
                'price': 149.75,
                'volume': random.randint(30, 120),
                'timestamp': base_time + timedelta(minutes=i, seconds=45),
                'side': 'sell'
            })
    
    # NORMAL ORDERS: Random price levels (should not be detected as icebergs)
    print("📊 Adding normal market orders...")
    for i in range(50):
        for price in [149.50, 149.25, 150.25, 150.50]:
            orderbook_data.append({
                'price': price,
                'volume': random.randint(100, 800),  # More random volumes
                'timestamp': base_time + timedelta(minutes=random.randint(0, 120)),
                'side': random.choice(['bid', 'ask'])
            })
    
    return orderbook_data, trade_data

def run_comparison_demo():
    """Run comparison between simplified and advanced detection."""
    
    print("🏛️  ICEBERG DETECTION COMPARISON DEMO")
    print("=" * 60)
    
    # Create sample data
    orderbook_data, trade_data = create_sample_iceberg_data()
    
    # Initialize the data manager
    mock_project_x = MockProjectX()
    manager = ProjectXRealtimeDataManager(
        instrument="MGC",
        project_x=mock_project_x,
        account_id="demo"
    )
    
    # Populate with sample data
    print("\n📊 Populating orderbook with sample data...")
    
    # Convert to Polars DataFrames and populate
    for data in orderbook_data:
        if data['side'] == 'bid':
            bid_df = pl.DataFrame([data])
            manager.orderbook_bids = manager.orderbook_bids.vstack(bid_df) if len(manager.orderbook_bids) > 0 else bid_df
        else:
            ask_df = pl.DataFrame([data])
            manager.orderbook_asks = manager.orderbook_asks.vstack(ask_df) if len(manager.orderbook_asks) > 0 else ask_df
    
    # Add trade data
    if trade_data:
        trades_df = pl.DataFrame(trade_data)
        manager.recent_trades = trades_df
    
    print(f"✅ Loaded {len(orderbook_data)} orderbook entries and {len(trade_data)} trades")
    
    # RUN SIMPLIFIED DETECTION
    print("\n" + "="*60)
    print("🔍 SIMPLIFIED ICEBERG DETECTION")
    print("="*60)
    
    simplified_results = manager.detect_iceberg_orders(
        min_refresh_count=3,
        volume_consistency_threshold=0.8,
        time_window_minutes=60
    )
    
    print(f"\n📊 SIMPLIFIED RESULTS:")
    print(f"   Total Detected: {simplified_results['analysis']['total_detected']}")
    print(f"   Bid Icebergs: {simplified_results['analysis']['bid_icebergs']}")
    print(f"   Ask Icebergs: {simplified_results['analysis']['ask_icebergs']}")
    print(f"   Detection Method: {simplified_results['analysis'].get('note', 'Basic heuristic analysis')}")
    
    if simplified_results['potential_icebergs']:
        print(f"\n🧊 DETECTED ICEBERGS (Simplified):")
        for iceberg in simplified_results['potential_icebergs']:
            print(f"   💎 ${iceberg['price']:.2f} - {iceberg['volume']:,} shares")
            print(f"      Confidence: {iceberg['confidence']}")
            print(f"      Hidden Size Est: {iceberg['estimated_hidden_size']:,}")
            print(f"      Method: {iceberg['detection_method']}")
    else:
        print("   ❌ No icebergs detected with simplified method")
    
    # RUN ADVANCED DETECTION (if available)
    print("\n" + "="*60)
    print("🔬 ADVANCED ICEBERG DETECTION")
    print("="*60)
    
    try:
        advanced_results = manager.detect_iceberg_orders_advanced(
            time_window_minutes=60,
            min_refresh_count=5,
            volume_consistency_threshold=0.85,
            statistical_confidence=0.90
        )
        
        print(f"\n📊 ADVANCED RESULTS:")
        analysis = advanced_results['analysis']
        print(f"   Total Detected: {analysis['total_detected']}")
        print(f"   Detection Method: {analysis['detection_method']}")
        print(f"   Statistical Confidence: {analysis['statistical_thresholds']['statistical_confidence']}")
        
        if 'confidence_distribution' in analysis:
            print(f"   Confidence Distribution:")
            for level, count in analysis['confidence_distribution'].items():
                if count > 0:
                    print(f"      {level}: {count}")
        
        if advanced_results['potential_icebergs']:
            print(f"\n🧊 DETECTED ICEBERGS (Advanced):")
            for iceberg in advanced_results['potential_icebergs']:
                print(f"   💎 ${iceberg['price']:.2f}")
                print(f"      Confidence: {iceberg['confidence']} ({iceberg['confidence_score']:.3f})")
                print(f"      Visible: {iceberg['current_volume']:,} shares")
                print(f"      Hidden Est: {iceberg['estimated_hidden_size']:,}")
                print(f"      Total Est: {iceberg['total_volume_observed']:,}")
                print(f"      Refresh Count: {iceberg['refresh_count']}")
                print(f"      Volume Consistency: {iceberg['volume_consistency']:.3f}")
                print(f"      Statistical Significance: {iceberg['statistical_significance']:.3f}")
        else:
            print("   ❌ No icebergs detected with advanced method")
            
    except AttributeError:
        print("   ⚠️  Advanced detection method not available")
        print("   🔧 The advanced method requires additional implementation")
    
    # COMPARISON SUMMARY
    print("\n" + "="*60)
    print("📚 METHOD COMPARISON")
    print("="*60)
    
    print("\n🔍 SIMPLIFIED APPROACH:")
    print("   ✅ Fast and lightweight")
    print("   ✅ Easy to understand and implement")
    print("   ✅ Good for basic pattern detection")
    print("   ❌ Higher false positive rate")
    print("   ❌ Limited statistical validation")
    print("   ❌ No historical pattern tracking")
    print("   ❌ Simple heuristics only")
    
    print("\n🔬 ADVANCED APPROACH:")
    print("   ✅ Institutional-grade accuracy")
    print("   ✅ Statistical significance testing")
    print("   ✅ Multi-factor analysis")
    print("   ✅ Historical pattern tracking")
    print("   ✅ Execution pattern correlation")
    print("   ✅ Lower false positive rate")
    print("   ❌ More complex implementation")
    print("   ❌ Higher computational requirements")
    print("   ❌ Requires more historical data")
    
    print("\n🏛️ INSTITUTIONAL USAGE:")
    print("   • Hedge funds: Use advanced methods for alpha generation")
    print("   • HFT firms: Need microsecond-level pattern detection")
    print("   • Investment banks: Regulatory compliance requires sophisticated analysis")
    print("   • Asset managers: Risk management needs accurate size estimation")
    
    print("\n💡 RECOMMENDATION:")
    print("   • Simplified: Good for retail traders, basic analysis")
    print("   • Advanced: Essential for institutional trading, compliance")
    print("   • Hybrid: Use simplified for real-time alerts, advanced for validation")

if __name__ == "__main__":
    run_comparison_demo() 