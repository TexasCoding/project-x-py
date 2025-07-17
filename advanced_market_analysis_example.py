#!/usr/bin/env python3
"""
Advanced Market Microstructure Analysis Example
============================================

This example demonstrates the comprehensive advanced market analysis capabilities
of the Project-X-Py orderbook system, including:

1. Liquidity Levels Analysis
2. Order Cluster Detection
3. Iceberg Order Detection
4. Cumulative Delta Analysis
5. Market Imbalance Detection
6. Volume Profile Analysis
7. Dynamic Support/Resistance Levels
8. Comprehensive Market Metrics

Author: TexasCoding
Date: January 2025
"""

import asyncio
import json
import logging
from datetime import datetime

from project_x_py import ProjectX
from project_x_py.realtime_data_manager import ProjectXRealtimeDataManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


def print_section(title: str):
    """Print a formatted section header."""
    print(f"\n{'='*60}")
    print(f" {title}")
    print('='*60)


def print_subsection(title: str):
    """Print a formatted subsection header."""
    print(f"\n{'-'*40}")
    print(f" {title}")
    print('-'*40)


async def demonstrate_advanced_market_analysis():
    """
    Comprehensive demonstration of advanced market microstructure analysis.
    """
    print_section("🔬 ADVANCED MARKET MICROSTRUCTURE ANALYSIS")
    print("This demo showcases professional-grade market analysis capabilities")
    print("including institutional order detection, hidden liquidity analysis,")
    print("and real-time market pressure measurement.")
    
    # Initialize ProjectX client
    print_subsection("📡 Initializing ProjectX Client")
    try:
        # Note: In a real implementation, you would provide your actual credentials
        project_x = ProjectX(username="jeffw102", api_key="Q1yl6AVP0aWGigl176fLN5O7gooUaJGTaSLUtKQMoZE=")
        print("✅ ProjectX client initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize ProjectX: {e}")
        print("💡 This is expected in demo mode - replace with your actual credentials")
        print("📝 To run this demo with real data, update the credentials in the script")
        return
    
    # Configuration
    INSTRUMENT = "MNQ"  # E-mini NASDAQ futures
    ACCOUNT_ID = "your_account_id_here"
    
    # Initialize Real-time Data Manager
    print_subsection("🚀 Setting Up Advanced Market Data Manager")
    data_manager = ProjectXRealtimeDataManager(
        instrument=INSTRUMENT,
        project_x=project_x,
        account_id=ACCOUNT_ID,
        timeframes=["15sec", "1min", "5min"]  # Multi-timeframe analysis
    )
    
    # Load historical data
    print("📊 Loading historical market data...")
    if not data_manager.initialize(initial_days=7):
        print("❌ Failed to initialize data manager")
        return

    jwt_token = project_x.get_session_token()
    if not data_manager.start_realtime_feed(jwt_token):
        print("❌ Failed to start real-time feed")
        return
    print("✅ Real-time feed started - collecting orderbook data...")
    
    print("✅ Historical data loaded successfully")
    
    # Start real-time feed (simulated - replace with actual JWT token)
    print("🔄 Starting real-time market feed...")
    # jwt_token = project_x.get_session_token()
    # success = data_manager.start_realtime_feed(jwt_token)
    print("✅ Real-time feed ready (demo mode)")
    
    # Wait for some market data to accumulate
    print("⏳ Allowing market data to accumulate...")
    await asyncio.sleep(240)
    
    print("\n📊 DEMO MODE EXPLANATION:")
    print("   • Historical OHLCV data: ✅ Available (20,000+ bars loaded)")
    print("   • Real-time orderbook: ❌ Requires live WebSocket connection")
    print("   • Trade flow data: ❌ Generated from real-time market depth")
    print("   • Advanced analysis: 🔄 Will demonstrate with simulated data structures")
    print("   • To see full functionality: Connect to live TopStepX market feed")
    
    # ============================================================================
    # 1. LIQUIDITY LEVELS ANALYSIS
    # ============================================================================
    print_section("💧 LIQUIDITY LEVELS ANALYSIS")
    print("Identifying significant price levels with substantial volume")
    
    # Note: This demo works with historical data only
    print("📝 Demo Note: Running in historical data mode - real-time orderbook data requires live connection")
    
    liquidity_analysis = data_manager.get_liquidity_levels(
        min_volume=150,  # Minimum volume threshold for significance
        levels=25        # Analyze top 25 levels from each side
    )
    
    analysis_info = liquidity_analysis.get('analysis', {})
    print(f"\n📈 Bid Liquidity Levels Found: {analysis_info.get('total_bid_levels', 0)}")
    print(f"📉 Ask Liquidity Levels Found: {analysis_info.get('total_ask_levels', 0)}")
    print(f"💰 Average Bid Volume: {analysis_info.get('avg_bid_volume', 0):,.0f} contracts")
    print(f"💰 Average Ask Volume: {analysis_info.get('avg_ask_volume', 0):,.0f} contracts")
    
    # Display top liquidity levels
    if len(liquidity_analysis['bid_liquidity']) > 0:
        print("\n🔝 Top Bid Liquidity Levels:")
        top_bids = liquidity_analysis['bid_liquidity'].head(5).to_dicts()
        for i, level in enumerate(top_bids, 1):
            print(f"  {i}. Price: ${level['price']:.2f} | Volume: {level['volume']:,} | Score: {level['liquidity_score']:.2f}")
    
    if len(liquidity_analysis['ask_liquidity']) > 0:
        print("\n🔝 Top Ask Liquidity Levels:")
        top_asks = liquidity_analysis['ask_liquidity'].head(5).to_dicts()
        for i, level in enumerate(top_asks, 1):
            print(f"  {i}. Price: ${level['price']:.2f} | Volume: {level['volume']:,} | Score: {level['liquidity_score']:.2f}")
    
    # ============================================================================
    # 2. ORDER CLUSTER DETECTION
    # ============================================================================
    print_section("🎯 ORDER CLUSTER DETECTION")
    print("Detecting groups of orders at similar price levels")
    
    cluster_analysis = data_manager.detect_order_clusters(
        price_tolerance=0.25,    # Quarter-point clustering tolerance
        min_cluster_size=3       # Minimum 3 orders to form a cluster
    )
    
    print(f"\n📊 Total Clusters Detected: {cluster_analysis.get('cluster_count', 0)}")
    print(f"📈 Bid Clusters: {len(cluster_analysis.get('bid_clusters', []))}")
    print(f"📉 Ask Clusters: {len(cluster_analysis.get('ask_clusters', []))}")
    
    # Display strongest clusters
    cluster_analysis_info = cluster_analysis.get('analysis', {})
    if cluster_analysis_info.get('strongest_bid_cluster'):
        strongest_bid = cluster_analysis_info['strongest_bid_cluster']
        print(f"\n💪 Strongest Bid Cluster:")
        print(f"  🎯 Center Price: ${strongest_bid['center_price']:.2f}")
        print(f"  📏 Price Range: ${strongest_bid['price_range'][0]:.2f} - ${strongest_bid['price_range'][1]:.2f}")
        print(f"  📦 Total Volume: {strongest_bid['total_volume']:,} contracts")
        print(f"  🔢 Order Count: {strongest_bid['order_count']} orders")
    
    if cluster_analysis_info.get('strongest_ask_cluster'):
        strongest_ask = cluster_analysis_info['strongest_ask_cluster']
        print(f"\n💪 Strongest Ask Cluster:")
        print(f"  🎯 Center Price: ${strongest_ask['center_price']:.2f}")
        print(f"  📏 Price Range: ${strongest_ask['price_range'][0]:.2f} - ${strongest_ask['price_range'][1]:.2f}")
        print(f"  📦 Total Volume: {strongest_ask['total_volume']:,} contracts")
        print(f"  🔢 Order Count: {strongest_ask['order_count']} orders")
    
    # ============================================================================
    # 3. ICEBERG ORDER DETECTION
    # ============================================================================
    print_section("🧊 ICEBERG ORDER DETECTION")
    print("Scanning for hidden institutional orders with large size")
    
    iceberg_analysis = data_manager.detect_iceberg_orders(
        min_refresh_count=3,              # Minimum refreshes to consider iceberg
        volume_consistency_threshold=0.8,  # Volume consistency requirement
        time_window_minutes=10            # Analysis time window
    )
    
    iceberg_info = iceberg_analysis.get('analysis', {})
    print(f"\n🎣 Potential Icebergs Detected: {iceberg_info.get('total_detected', 0)}")
    print(f"📈 Bid-side Icebergs: {iceberg_info.get('bid_icebergs', 0)}")
    print(f"📉 Ask-side Icebergs: {iceberg_info.get('ask_icebergs', 0)}")
    
    # Show confidence breakdown
    if iceberg_info.get('total_detected', 0) > 0:
        print(f"🔒 Confidence Breakdown:")
        print(f"   High: {iceberg_info.get('high_confidence', 0)}")
        print(f"   Medium: {iceberg_info.get('medium_confidence', 0)}")
        print(f"   Low: {iceberg_info.get('low_confidence', 0)}")
        print(f"⏰ Time Window: {iceberg_info.get('time_window_minutes', 10)} minutes")
    
    potential_icebergs = iceberg_analysis.get('potential_icebergs', [])
    if potential_icebergs:
        print("\n🧊 Detected Potential Iceberg Orders:")
        for i, iceberg in enumerate(potential_icebergs[:5], 1):
            confidence_score = iceberg.get('confidence_score', 0)
            print(f"  {i}. ${iceberg['price']:.2f} {iceberg['side'].upper()} | "
                  f"Visible: {iceberg['volume']:,} | "
                  f"Est. Hidden: {iceberg['estimated_hidden_size']:,} | "
                  f"Confidence: {iceberg['confidence']} ({confidence_score:.2f})")
    
    if 'note' in iceberg_info:
        print(f"\n💡 Note: {iceberg_info['note']}")
    
    # ============================================================================
    # 3b. ADVANCED ICEBERG ORDER DETECTION (Institutional-Grade)
    # ============================================================================
    print_section("🔬 ADVANCED ICEBERG DETECTION (Institutional)")
    print("Using statistical analysis, order flow tracking, and multi-factor scoring")
    
    try:
        advanced_iceberg_analysis = data_manager.detect_iceberg_orders_advanced(
            time_window_minutes=30,               # Longer analysis window
            min_refresh_count=5,                  # Higher threshold for institutional detection
            volume_consistency_threshold=0.85,    # Stricter consistency requirement  
            min_total_volume=1000,               # Minimum volume for institutional orders
            statistical_confidence=0.90          # High statistical confidence required
        )
        
        advanced_info = advanced_iceberg_analysis.get('analysis', {})
        advanced_icebergs = advanced_iceberg_analysis.get('potential_icebergs', [])
        
        print(f"\n🎯 Advanced Detection Results:")
        print(f"📊 Total Detected: {advanced_info.get('total_detected', 0)}")
        print(f"🔬 Detection Method: {advanced_info.get('detection_method', 'N/A')}")
        print(f"⏱️  Analysis Window: {advanced_info.get('time_window_minutes', 30)} minutes")
        
        # Show confidence distribution for advanced method
        confidence_dist = advanced_info.get('confidence_distribution', {})
        if any(confidence_dist.values()):
            print(f"\n📈 Confidence Distribution:")
            for level, count in confidence_dist.items():
                if count > 0:
                    print(f"   {level.replace('_', ' ').title()}: {count}")
        
        # Show side distribution
        side_dist = advanced_info.get('side_distribution', {})
        if any(side_dist.values()):
            print(f"\n⚖️  Side Distribution:")
            print(f"   Bid Icebergs: {side_dist.get('bid', 0)}")
            print(f"   Ask Icebergs: {side_dist.get('ask', 0)}")
        
        # Show estimated hidden volume
        total_hidden = advanced_info.get('total_estimated_hidden_volume', 0)
        if total_hidden > 0:
            print(f"\n💰 Total Estimated Hidden Volume: {total_hidden:,} contracts")
        
        # Display detailed advanced iceberg information
        if advanced_icebergs:
            print(f"\n🧊 ADVANCED ICEBERG ANALYSIS:")
            for i, iceberg in enumerate(advanced_icebergs[:3], 1):  # Show top 3
                print(f"\n  {i}. ICEBERG at ${iceberg['price']:.2f} ({iceberg['side'].upper()})")
                print(f"     🎯 Confidence: {iceberg['confidence']} ({iceberg['confidence_score']:.3f})")
                print(f"     👁️  Visible Volume: {iceberg['current_volume']:,}")
                print(f"     🫥 Estimated Hidden: {iceberg['estimated_hidden_size']:,}")
                print(f"     📊 Total Observed: {iceberg['total_volume_observed']:,}")
                print(f"     🔄 Refresh Count: {iceberg['refresh_count']}")
                print(f"     📈 Volume Consistency: {iceberg['volume_consistency']:.3f}")
                print(f"     ⏱️  Avg Refresh Interval: {iceberg['avg_refresh_interval_seconds']:.1f}s")
                print(f"     📉 Statistical Significance: {iceberg['statistical_significance']:.3f}")
                
                # Show detailed indicators
                indicators = iceberg.get('indicators', {})
                if indicators:
                    print(f"     🔍 Factor Analysis:")
                    for factor, score in indicators.items():
                        factor_name = factor.replace('_', ' ').title()
                        print(f"        {factor_name}: {score:.3f}")
                
                # Show execution analysis if available
                if 'execution_analysis' in iceberg:
                    exec_analysis = iceberg['execution_analysis']
                    print(f"     🎯 Execution Analysis:")
                    print(f"        Nearby Trades: {exec_analysis['nearby_trades_count']}")
                    print(f"        Trade Volume: {exec_analysis['total_trade_volume']:,}")
                    print(f"        Avg Trade Size: {exec_analysis['avg_trade_size']:.1f}")
                    print(f"        Execution Consistency: {exec_analysis['execution_consistency']:.3f}")
        
        # Show comparison between methods
        simple_count = iceberg_info.get('total_detected', 0)
        advanced_count = advanced_info.get('total_detected', 0)
        
        print(f"\n📊 METHOD COMPARISON:")
        print(f"   Simplified Detection: {simple_count} icebergs")
        print(f"   Advanced Detection: {advanced_count} icebergs")
        
        if simple_count != advanced_count:
            if advanced_count < simple_count:
                print(f"   🎯 Advanced method filtered out {simple_count - advanced_count} false positives")
                print(f"   ✅ Higher precision with institutional-grade validation")
            else:
                print(f"   🔍 Advanced method found {advanced_count - simple_count} additional icebergs")
                print(f"   📈 Better detection through sophisticated analysis")
        else:
            print(f"   ⚖️  Both methods agree on iceberg count")
        
        # Show advanced method notes
        notes = advanced_info.get('notes', [])
        if notes:
            print(f"\n🏛️  INSTITUTIONAL TECHNIQUES:")
            for note in notes:
                print(f"   • {note}")
        
    except AttributeError as e:
        print(f"\n⚠️  Advanced iceberg detection not available")
        print(f"🔧 This requires the institutional-grade implementation")
        print(f"💡 Currently showing simplified detection results above")
    except Exception as e:
        print(f"\n❌ Error in advanced iceberg detection: {e}")
        print(f"🔄 Falling back to simplified detection results above")
    
    # ============================================================================
    # 4. CUMULATIVE DELTA ANALYSIS
    # ============================================================================
    print_section("📊 CUMULATIVE DELTA ANALYSIS")
    print("Tracking net buying vs selling pressure over time")
    
    delta_analysis = data_manager.get_cumulative_delta(time_window_minutes=30)
    
    print(f"\n📈 Cumulative Delta: {delta_analysis['cumulative_delta']:,} contracts")
    print(f"📊 Delta Trend: {delta_analysis['delta_trend'].upper()}")
    
    analysis = delta_analysis.get('analysis', {})
    if 'note' in analysis:
        print(f"📝 Note: {analysis['note']}")
    else:
        print(f"💰 Total Buy Volume: {analysis.get('total_buy_volume', 0):,}")
        print(f"💰 Total Sell Volume: {analysis.get('total_sell_volume', 0):,}")
        print(f"🔢 Trade Count: {analysis.get('trade_count', 0):,}")
        print(f"⚡ Delta per Minute: {analysis.get('delta_per_minute', 0):.1f}")
    
    # Delta interpretation
    delta_value = delta_analysis['cumulative_delta']
    if delta_value > 500:
        print("🚀 INTERPRETATION: Strong bullish momentum - aggressive buying detected")
    elif delta_value > 100:
        print("📈 INTERPRETATION: Moderate bullish pressure")
    elif delta_value < -500:
        print("🐻 INTERPRETATION: Strong bearish momentum - aggressive selling detected")
    elif delta_value < -100:
        print("📉 INTERPRETATION: Moderate bearish pressure")
    else:
        print("⚖️ INTERPRETATION: Balanced market - no significant directional bias")
    
    # ============================================================================
    # 5. MARKET IMBALANCE ANALYSIS
    # ============================================================================
    print_section("⚖️ MARKET IMBALANCE ANALYSIS")
    print("Measuring orderbook and trade flow imbalances")
    
    imbalance_analysis = data_manager.get_market_imbalance()
    
    print(f"\n📊 Imbalance Ratio: {imbalance_analysis.get('imbalance_ratio', 0):.3f}")
    print(f"🎯 Direction: {imbalance_analysis.get('direction', 'neutral').upper()}")
    print(f"🔒 Confidence: {imbalance_analysis.get('confidence', 'low').upper()}")
    
    ob_metrics = imbalance_analysis.get('orderbook_metrics', {})
    if ob_metrics:
        print(f"\n📈 Orderbook Metrics:")
        print(f"  💰 Top Bid Volume: {ob_metrics.get('top_bid_volume', 0):,}")
        print(f"  💰 Top Ask Volume: {ob_metrics.get('top_ask_volume', 0):,}")
        print(f"  📊 Bid/Ask Ratio: {ob_metrics.get('bid_ask_ratio', 0):.2f}")
    
    tf_metrics = imbalance_analysis.get('trade_flow_metrics', {})
    if tf_metrics:
        print(f"\n🔄 Trade Flow Metrics:")
        print(f"  📈 Recent Buy Volume: {tf_metrics.get('recent_buy_volume', 0):,}")
        print(f"  📉 Recent Sell Volume: {tf_metrics.get('recent_sell_volume', 0):,}")
        print(f"  ⚖️ Trade Imbalance: {tf_metrics.get('trade_imbalance', 0):.3f}")
    else:
        print(f"\n📝 Note: Trade flow metrics require real-time market data")
    
    # ============================================================================
    # 6. VOLUME PROFILE ANALYSIS
    # ============================================================================
    print_section("📊 VOLUME PROFILE ANALYSIS")
    print("Creating price-volume distribution and identifying key levels")
    
    volume_profile = data_manager.get_volume_profile(price_bucket_size=0.25)
    
    poc = volume_profile.get('poc')
    if poc and poc.get('price'):
        print(f"\n🎯 Point of Control (POC):")
        print(f"  💰 Price: ${poc['price']:.2f}")
        print(f"  📦 Volume: {poc['volume']:,} contracts")
    else:
        print(f"\n📝 Note: No Point of Control available (requires trade data)")
    
    value_area = volume_profile.get('value_area')
    if value_area and value_area.get('high'):
        print(f"\n📊 Value Area (70% of volume):")
        print(f"  📈 High: ${value_area['high']:.2f}")
        print(f"  📉 Low: ${value_area['low']:.2f}")
        print(f"  📊 Coverage: {value_area['volume_percentage']:.1f}%")
    else:
        print(f"\n📝 Note: Value Area calculation requires trade data")
    
    print(f"\n📈 Profile Summary:")
    print(f"  📦 Total Volume: {volume_profile.get('total_volume', 0):,} contracts")
    print(f"  📏 Bucket Size: ${volume_profile.get('bucket_size', 0.25)}")
    print(f"  🔢 Price Levels: {len(volume_profile.get('profile', []))}")
    
    # ============================================================================
    # 7. SUPPORT & RESISTANCE LEVELS
    # ============================================================================
    print_section("🏗️ DYNAMIC SUPPORT & RESISTANCE")
    print("Identifying key price levels from orderbook and volume data")
    
    sr_analysis = data_manager.get_support_resistance_levels(lookback_minutes=60)
    
    current_price = sr_analysis.get('current_price')
    if current_price:
        print(f"\n🎯 Current Price: ${current_price:.2f}")
    else:
        print(f"\n📝 Note: Current price not available (requires orderbook data)")
    
    support_levels = sr_analysis.get('support_levels', [])
    resistance_levels = sr_analysis.get('resistance_levels', [])
    print(f"🏗️ Support Levels Found: {len(support_levels)}")
    print(f"🚧 Resistance Levels Found: {len(resistance_levels)}")
    
    sr_analysis_info = sr_analysis.get('analysis', {})
    strongest_support = sr_analysis_info.get('strongest_support')
    if strongest_support:
        print(f"\n💪 Strongest Support:")
        print(f"  💰 Price: ${strongest_support['price']:.2f}")
        print(f"  📦 Volume: {strongest_support['volume']:,}")
        print(f"  💪 Strength: {strongest_support['strength']:.2f}")
        print(f"  🏷️ Type: {strongest_support['type']}")
    
    strongest_resistance = sr_analysis_info.get('strongest_resistance')
    if strongest_resistance:
        print(f"\n🚧 Strongest Resistance:")
        print(f"  💰 Price: ${strongest_resistance['price']:.2f}")
        print(f"  📦 Volume: {strongest_resistance['volume']:,}")
        print(f"  💪 Strength: {strongest_resistance['strength']:.2f}")
        print(f"  🏷️ Type: {strongest_resistance['type']}")
    
    # ============================================================================
    # 8. COMPREHENSIVE MARKET METRICS
    # ============================================================================
    print_section("🎯 COMPREHENSIVE MARKET ANALYSIS")
    print("Complete real-time market microstructure overview")
    
    advanced_metrics = data_manager.get_advanced_market_metrics()
    
    print(f"\n📊 Analysis Summary:")
    summary = advanced_metrics['analysis_summary']
    print(f"  🔍 Data Quality: {summary['data_quality'].upper()}")
    print(f"  📈 Market Activity: {summary['market_activity'].upper()}")
    print(f"  ✅ Analysis Completeness: {summary['analysis_completeness'].upper()}")
    print(f"  🕐 Timestamp: {advanced_metrics['timestamp']}")
    
    # Trade Flow Summary
    trade_flow = advanced_metrics['trade_flow']
    print(f"\n🔄 Recent Trade Flow (5 min):")
    print(f"  📦 Total Volume: {trade_flow['total_volume']:,}")
    print(f"  🔢 Trade Count: {trade_flow['trade_count']:,}")
    print(f"  📈 Buy Volume: {trade_flow['buy_volume']:,}")
    print(f"  📉 Sell Volume: {trade_flow['sell_volume']:,}")
    print(f"  💰 VWAP: ${trade_flow['vwap']:.2f}")
    print(f"  ⚖️ Buy/Sell Ratio: {trade_flow['buy_sell_ratio']:.2f}")
    
    # Orderbook Snapshot
    ob_snapshot = advanced_metrics.get('orderbook_snapshot', {})
    metadata = ob_snapshot.get('metadata', {})
    
    print(f"\n📊 Orderbook Snapshot:")
    
    best_bid = metadata.get('best_bid')
    best_ask = metadata.get('best_ask')
    spread = metadata.get('spread')
    mid_price = metadata.get('mid_price')
    
    if best_bid is not None:
        print(f"  💰 Best Bid: ${best_bid:.2f}")
    else:
        print(f"  💰 Best Bid: N/A (no orderbook data)")
        
    if best_ask is not None:
        print(f"  💰 Best Ask: ${best_ask:.2f}")
    else:
        print(f"  💰 Best Ask: N/A (no orderbook data)")
        
    if spread is not None:
        print(f"  📏 Spread: ${spread:.2f}")
    else:
        print(f"  📏 Spread: N/A")
        
    if mid_price is not None:
        print(f"  🎯 Mid Price: ${mid_price:.2f}")
    else:
        print(f"  🎯 Mid Price: N/A")
    
    levels_count = metadata.get('levels_count', {})
    print(f"  📈 Bid Levels: {levels_count.get('bids', 0)}")
    print(f"  📉 Ask Levels: {levels_count.get('asks', 0)}")
    
    # ============================================================================
    # 9. PRACTICAL TRADING INSIGHTS
    # ============================================================================
    print_section("💡 PRACTICAL TRADING INSIGHTS")
    print("Actionable market intelligence for trading decisions")
    
    # Market condition assessment
    print("\n🎯 MARKET CONDITION ASSESSMENT:")
    
    # Liquidity assessment
    total_liquidity_levels = (liquidity_analysis['analysis']['total_bid_levels'] + 
                            liquidity_analysis['analysis']['total_ask_levels'])
    if total_liquidity_levels > 10:
        print("  💧 Liquidity: HIGH - Deep orderbook with multiple significant levels")
    elif total_liquidity_levels > 5:
        print("  💧 Liquidity: MEDIUM - Adequate liquidity available")
    else:
        print("  💧 Liquidity: LOW - Thin orderbook, exercise caution")
    
    # Volatility assessment from clusters
    cluster_count = cluster_analysis['cluster_count']
    if cluster_count > 5:
        print("  📊 Order Distribution: CLUSTERED - Strong price level convergence")
    elif cluster_count > 2:
        print("  📊 Order Distribution: MODERATE - Some price level clustering")
    else:
        print("  📊 Order Distribution: SCATTERED - Dispersed order placement")
    
    # Institutional activity
    iceberg_count = iceberg_analysis['analysis']['total_detected']
    if iceberg_count > 3:
        print("  🏛️ Institutional Activity: HIGH - Multiple large hidden orders")
    elif iceberg_count > 0:
        print("  🏛️ Institutional Activity: MODERATE - Some large order activity")
    else:
        print("  🏛️ Institutional Activity: LOW - Primarily retail flow")
    
    # Market momentum
    delta_trend = delta_analysis['delta_trend']
    if 'strongly' in delta_trend:
        print(f"  🚀 Momentum: STRONG {delta_trend.split('_')[1].upper()} - Clear directional bias")
    elif delta_trend != 'neutral':
        print(f"  📈 Momentum: MODERATE {delta_trend.upper()} - Some directional bias")
    else:
        print("  ⚖️ Momentum: BALANCED - No clear directional bias")
    
    print("\n📋 TRADING RECOMMENDATIONS:")
    
    # Entry recommendations based on support/resistance
    support_levels = sr_analysis.get('support_levels', [])
    resistance_levels = sr_analysis.get('resistance_levels', [])
    current_price = sr_analysis.get('current_price')
    
    if support_levels and resistance_levels and current_price:
        nearest_support = min(support_levels, 
                            key=lambda x: abs(x['price'] - current_price))
        nearest_resistance = min(resistance_levels, 
                               key=lambda x: abs(x['price'] - current_price))
        
        print(f"  🎯 Nearest Support: ${nearest_support['price']:.2f} (strength: {nearest_support['strength']:.2f})")
        print(f"  🎯 Nearest Resistance: ${nearest_resistance['price']:.2f} (strength: {nearest_resistance['strength']:.2f})")
        
        support_distance = current_price - nearest_support['price']
        resistance_distance = nearest_resistance['price'] - current_price
        
        if support_distance < resistance_distance:
            print("  💡 Price closer to support - Consider long bias on bounce")
        else:
            print("  💡 Price closer to resistance - Consider short bias on rejection")
    else:
        print("  📝 Support/Resistance analysis requires real-time orderbook data")
    
    # Volume-based insights
    poc = volume_profile.get('poc')
    if poc and poc.get('price') and current_price:
        poc_price = poc['price']
        if current_price > poc_price:
            print(f"  📊 Price above POC (${poc_price:.2f}) - Bullish positioning")
        else:
            print(f"  📊 Price below POC (${poc_price:.2f}) - Bearish positioning")
    else:
        print("  📝 Volume profile analysis requires trade flow data")
    
    print_section("✅ ADVANCED MARKET ANALYSIS COMPLETE")
    print("Your orderbook now has professional-grade market microstructure capabilities!")
    print("Use these insights for:")
    print("• Institutional order detection")
    print("• Hidden liquidity identification") 
    print("• Market momentum assessment")
    print("• Dynamic support/resistance levels")
    print("• Volume-based trade timing")
    print("• Risk management optimization")


def demonstrate_basic_usage():
    """
    Show basic usage patterns for the advanced features.
    """
    print_section("📚 BASIC USAGE EXAMPLES")
    
    print("""
# Basic usage examples for advanced market analysis:

from project_x_py.realtime_data_manager import ProjectXRealtimeDataManager

# Initialize manager (same as before)
manager = ProjectXRealtimeDataManager("MNQ", project_x, account_id)
manager.initialize()

# 1. Get liquidity levels
liquidity = manager.get_liquidity_levels(min_volume=100, levels=20)
print(f"Found {len(liquidity['bid_liquidity'])} significant bid levels")

# 2. Detect order clusters  
clusters = manager.detect_order_clusters(price_tolerance=0.25, min_cluster_size=3)
print(f"Detected {clusters['cluster_count']} order clusters")

# 3. Check for iceberg orders
icebergs = manager.detect_iceberg_orders(time_window_minutes=10)
print(f"Found {len(icebergs['potential_icebergs'])} potential icebergs")

# 4. Calculate cumulative delta
delta = manager.get_cumulative_delta(time_window_minutes=30)
print(f"Cumulative delta: {delta['cumulative_delta']} ({delta['delta_trend']})")

# 5. Market imbalance
imbalance = manager.get_market_imbalance()
print(f"Market direction: {imbalance['direction']} (confidence: {imbalance['confidence']})")

# 6. Volume profile
profile = manager.get_volume_profile(price_bucket_size=0.25)
print(f"POC at ${profile['poc']['price']:.2f} with {profile['poc']['volume']} volume")

# 7. Support/resistance levels
sr_levels = manager.get_support_resistance_levels(lookback_minutes=60)
print(f"Found {len(sr_levels['support_levels'])} support and {len(sr_levels['resistance_levels'])} resistance levels")

# 8. Complete analysis (all features at once)
complete_analysis = manager.get_advanced_market_metrics()
# Returns comprehensive dictionary with all analysis results
""")


if __name__ == "__main__":
    print("🔬 Advanced Market Microstructure Analysis Demo")
    print("=" * 60)
    
    # Run the comprehensive demonstration
    asyncio.run(demonstrate_advanced_market_analysis())
    
    # Show basic usage examples
    demonstrate_basic_usage()
    
    print("\n🎉 Demo complete! Your orderbook is now equipped with professional-grade")
    print("   market microstructure analysis capabilities.") 