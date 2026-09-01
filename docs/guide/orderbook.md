# OrderBook Guide

This guide covers comprehensive Level 2 market depth analysis using the ProjectX Python SDK. The OrderBook component provides real-time market microstructure analysis with advanced features including spoofing detection, iceberg identification, and volume profile analysis.

## Overview

The OrderBook provides complete Level 2 market depth analysis with real-time updates via WebSocket. It includes sophisticated market microstructure analysis tools designed for institutional-level trading and market making applications.

### Key Features

- **Level 2 Market Depth**: Real-time bid/ask levels with volume
- **Market Microstructure Analysis**: Spread analysis, depth imbalance, and liquidity metrics
- **Spoofing heuristics**: Experimental volume-change labels (`detect_spoofing`), not order-lifecycle detection
- **Iceberg Detection**: Identify hidden order algorithms
- **Volume Profile**: Price-volume distribution analysis
- **Trade Flow Analysis**: Real-time trade classification and flow
- **Memory Management**: Efficient sliding window data management

## Getting Started

### Basic Setup

```python
import asyncio
from project_x_py import TradingSuite

async def basic_orderbook_setup():
    # Enable OrderBook feature
    suite = await TradingSuite.create(
        "MNQ",
        features=["orderbook"],  # Enable Level 2 data
        initial_days=1
    )

    # OrderBook is automatically initialized and connected
    orderbook = suite.orderbook

    print("OrderBook connected and receiving Level 2 data")

    # Get current best bid/ask
    best_prices = await orderbook.get_best_bid_ask()
    print(f"Best Bid: ${best_prices['bid']:.2f}")
    print(f"Best Ask: ${best_prices['ask']:.2f}")
    print(f"Spread: ${best_prices['spread']:.2f}")
```

### OrderBook Data Structure

The OrderBook maintains real-time Level 2 data with the following structure:

```python
async def examine_orderbook_structure():
    suite = await TradingSuite.create("MNQ", features=["orderbook"])
    orderbook = suite.orderbook

    # Get bid levels (sorted by price descending)
    bids = await orderbook.get_orderbook_bids(levels=10)
    print("Bid Levels (highest first):")
    print(bids.head())

    # Get ask levels (sorted by price ascending)
    asks = await orderbook.get_orderbook_asks(levels=10)
    print("Ask Levels (lowest first):")
    print(asks.head())

    # Orderbook snapshot (real API)
    snapshot = await orderbook.get_orderbook_snapshot(levels=10)
    print(f"Snapshot - Bid levels: {len(snapshot['bids'])}, Ask levels: {len(snapshot['asks'])}")
```

## Market Depth Analysis

### Bid/Ask Spread Analysis

```python
async def spread_analysis():
    suite = await TradingSuite.create("MNQ", features=["orderbook"])
    orderbook = suite.orderbook

    # Real-time spread monitoring
    spread_history = []

    async def monitor_spread():
        """Monitor spread changes in real-time."""

        for _ in range(20):  # Monitor for 20 updates
            best_prices = await orderbook.get_best_bid_ask()

            if best_prices['bid'] and best_prices['ask']:
                spread = best_prices['spread']
                mid_price = (best_prices['bid'] + best_prices['ask']) / 2
                spread_bps = (spread / mid_price) * 10000  # Basis points

                spread_history.append({
                    'timestamp': datetime.now(),
                    'spread': spread,
                    'spread_bps': spread_bps,
                    'bid': best_prices['bid'],
                    'ask': best_prices['ask']
                })

                print(f"Spread: ${spread:.2f} ({spread_bps:.1f} bps) | Bid: ${best_prices['bid']:.2f} Ask: ${best_prices['ask']:.2f}")

                # Spread alerts
                if spread > 5.0:  # Wide spread for MNQ
                    print("  Wide spread detected!")
                elif spread < 0.5:  # Tight spread
                    print("=% Tight spread - high liquidity")

            await asyncio.sleep(5)  # Check every 5 seconds

    await monitor_spread()

    # Spread analysis
    if spread_history:
        avg_spread = sum(s['spread'] for s in spread_history) / len(spread_history)
        max_spread = max(s['spread'] for s in spread_history)
        min_spread = min(s['spread'] for s in spread_history)

        print(f"\nSpread Analysis:")
        print(f"Average: ${avg_spread:.2f}")
        print(f"Range: ${min_spread:.2f} - ${max_spread:.2f}")
        print(f"Volatility: ${max_spread - min_spread:.2f}")
```

### Market Depth and Liquidity

```python
async def depth_analysis():
    suite = await TradingSuite.create("MNQ", features=["orderbook"])
    orderbook = suite.orderbook

    # Analyze market depth at multiple levels
    levels_to_analyze = [1, 5, 10, 20]

    for level_count in levels_to_analyze:
        bids = await orderbook.get_orderbook_bids(levels=level_count)
        asks = await orderbook.get_orderbook_asks(levels=level_count)

        # Calculate cumulative volume
        bid_volume = bids['volume'].sum() if not bids.is_empty() else 0
        ask_volume = asks['volume'].sum() if not asks.is_empty() else 0
        total_volume = bid_volume + ask_volume

        # Volume imbalance
        if total_volume > 0:
            bid_ratio = bid_volume / total_volume
            imbalance = bid_ratio - 0.5  # -0.5 to +0.5 scale

            print(f"Depth at {level_count} levels:")
            print(f"  Bid Volume: {bid_volume:,}")
            print(f"  Ask Volume: {ask_volume:,}")
            print(f"  Imbalance: {imbalance:+.3f} ({'Bid Heavy' if imbalance > 0 else 'Ask Heavy' if imbalance < 0 else 'Balanced'})")

            # Large imbalance alerts
            if abs(imbalance) > 0.3:
                direction = "Bullish" if imbalance > 0 else "Bearish"
                print(f"  = Strong {direction} Imbalance!")

        print()

    # Price impact analysis
    await analyze_price_impact(orderbook)

async def analyze_price_impact(orderbook):
    """Analyze price impact for different order sizes."""

    test_sizes = [1, 5, 10, 25, 50]  # Contract sizes to test

    print("Price Impact Analysis:")

    snapshot = await orderbook.get_orderbook_snapshot(levels=20)
    print(f"Best bid: {snapshot.get('best_bid')}  Best ask: {snapshot.get('best_ask')}")
    print(f"Spread: {snapshot.get('spread')}  Imbalance: {snapshot.get('imbalance')}")
    print("Use snapshot bid/ask levels to estimate walk-the-book impact; "
          "there is no calculate_price_impact() API.")
```

### Order Flow and Trade Analysis

```python
from project_x_py import EventType

async def order_flow_analysis():
    suite = await TradingSuite.create("MNQ", features=["orderbook"])
    orderbook = suite.orderbook

    # Trade flow tracking
    trade_flow = {
        'buy_volume': 0,
        'sell_volume': 0,
        'trade_count': 0,
        'large_trades': []
    }

    async def on_trade(event):
        """Analyze each trade for flow patterns."""
        trade_data = event.data

        price = trade_data['price']
        size = trade_data['size']
        side = trade_data.get('side', 'unknown')  # 'buy' or 'sell'

        trade_flow['trade_count'] += 1

        # Classify trade direction if not provided
        if side == 'unknown':
            best_prices = await orderbook.get_best_bid_ask()
            if best_prices['bid'] and best_prices['ask']:
                mid_price = (best_prices['bid'] + best_prices['ask']) / 2
                side = 'buy' if price >= mid_price else 'sell'

        # Update flow metrics
        if side == 'buy':
            trade_flow['buy_volume'] += size
        elif side == 'sell':
            trade_flow['sell_volume'] += size

        # Track large trades
        if size >= 50:  # Large trade threshold
            trade_flow['large_trades'].append({
                'timestamp': trade_data.get('timestamp', datetime.now()),
                'price': price,
                'size': size,
                'side': side
            })

            print(f"=% Large {side} trade: {size} @ ${price:.2f}")

        # Periodic flow summary
        if trade_flow['trade_count'] % 20 == 0:
            await print_flow_summary(trade_flow)

    async def print_flow_summary(flow):
        """Print current order flow summary."""

        total_volume = flow['buy_volume'] + flow['sell_volume']

        if total_volume > 0:
            buy_ratio = flow['buy_volume'] / total_volume
            flow_imbalance = buy_ratio - 0.5

            print(f"\n= Order Flow Summary (last {flow['trade_count']} trades):")
            print(f"  Buy Volume: {flow['buy_volume']:,} ({buy_ratio:.1%})")
            print(f"  Sell Volume: {flow['sell_volume']:,} ({1-buy_ratio:.1%})")
            print(f"  Flow Bias: {flow_imbalance:+.3f} ({'Bullish' if flow_imbalance > 0 else 'Bearish' if flow_imbalance < 0 else 'Neutral'})")
            print(f"  Large Trades: {len(flow['large_trades'])}")

    # Register for trade events
    await suite.on(EventType.TRADE_TICK, on_trade)

    # Monitor for 2 minutes
    await asyncio.sleep(120)

    # Final flow analysis
    if trade_flow['large_trades']:
        print(f"\n=
 Large Trade Analysis:")

        # Analyze large trade timing
        large_trades = trade_flow['large_trades'][-10:]  # Last 10 large trades

        buy_large = sum(t['size'] for t in large_trades if t['side'] == 'buy')
        sell_large = sum(t['size'] for t in large_trades if t['side'] == 'sell')

        if buy_large > sell_large * 1.5:
            print("  = Large buyer dominance")
        elif sell_large > buy_large * 1.5:
            print("  = Large seller dominance")
        else:
            print("    Balanced large trade flow")
```

## Advanced Market Microstructure

### Market Imbalance Detection

```python
async def market_imbalance_analysis():
    suite = await TradingSuite.create("MNQ", features=["orderbook"])
    orderbook = suite.orderbook

    # Track imbalance over time
    imbalance_history = []

    async def monitor_imbalance():
        """Monitor order book imbalance patterns."""

        for _ in range(30):  # 30 measurements
            imbalance = await orderbook.get_market_imbalance()

            timestamp = datetime.now()
            imbalance_history.append({
                'timestamp': timestamp,
                'imbalance': imbalance,
                'level': classify_imbalance(imbalance)
            })

            print(f"Market Imbalance: {imbalance:+.3f} ({classify_imbalance(imbalance)})")

            # Extreme imbalance alerts
            if abs(imbalance) > 0.7:
                direction = "Bullish" if imbalance > 0 else "Bearish"
                print(f"= EXTREME {direction.upper()} IMBALANCE!")

            await asyncio.sleep(10)  # Every 10 seconds

    def classify_imbalance(imbalance):
        """Classify imbalance level."""
        if imbalance > 0.5:
            return "Strong Bid"
        elif imbalance > 0.2:
            return "Moderate Bid"
        elif imbalance > -0.2:
            return "Balanced"
        elif imbalance > -0.5:
            return "Moderate Ask"
        else:
            return "Strong Ask"

    await monitor_imbalance()

    # Imbalance trend analysis
    if len(imbalance_history) >= 10:
        recent_avg = sum(h['imbalance'] for h in imbalance_history[-10:]) / 10
        earlier_avg = sum(h['imbalance'] for h in imbalance_history[-20:-10]) / 10

        trend = recent_avg - earlier_avg

        print(f"\nImbalance Trend Analysis:")
        print(f"Recent Average: {recent_avg:+.3f}")
        print(f"Earlier Average: {earlier_avg:+.3f}")
        print(f"Trend: {trend:+.3f} ({'Increasing Bid Pressure' if trend > 0 else 'Increasing Ask Pressure' if trend < 0 else 'Stable'})")
```

### Liquidity Analysis

```python
async def liquidity_analysis():
    suite = await TradingSuite.create("MNQ", features=["orderbook"])
    orderbook = suite.orderbook

    # Analyze liquidity at different price levels
    liquidity_metrics = await orderbook.get_liquidity_metrics()

    print("= Liquidity Analysis:")
    print(f"  Total Bid Liquidity: {liquidity_metrics['total_bid_volume']:,}")
    print(f"  Total Ask Liquidity: {liquidity_metrics['total_ask_volume']:,}")
    print(f"  Weighted Mid Price: ${liquidity_metrics['weighted_mid']:.2f}")
    print(f"  Liquidity Ratio: {liquidity_metrics['liquidity_ratio']:.3f}")

    # Liquidity depth analysis
    price_levels = [1, 2, 5, 10, 25]  # Price points away from mid

    best_prices = await orderbook.get_best_bid_ask()
    if best_prices['bid'] and best_prices['ask']:
        mid_price = (best_prices['bid'] + best_prices['ask']) / 2

        print(f"\nLiquidity at Price Levels (from mid ${mid_price:.2f}):")

        for level in price_levels:
            # Analyze liquidity $X away from mid
            upper_price = mid_price + level
            lower_price = mid_price - level

            # Get volume within range
            bids = await orderbook.get_orderbook_bids()
            asks = await orderbook.get_orderbook_asks()

            # Filter for price range
            bids_in_range = bids.filter(pl.col('price') >= lower_price)
            asks_in_range = asks.filter(pl.col('price') <= upper_price)

            bid_liquidity = bids_in_range['volume'].sum() if not bids_in_range.is_empty() else 0
            ask_liquidity = asks_in_range['volume'].sum() if not asks_in_range.is_empty() else 0
            total_liquidity = bid_liquidity + ask_liquidity

            print(f"  ${level}: {total_liquidity:,} contracts ({bid_liquidity:,} bids, {ask_liquidity:,} asks)")

    # Liquidity concentration analysis
    await analyze_liquidity_concentration(orderbook)

async def analyze_liquidity_concentration(orderbook):
    """Analyze where liquidity is concentrated."""

    bids = await orderbook.get_orderbook_bids(levels=20)
    asks = await orderbook.get_orderbook_asks(levels=20)

    if not bids.is_empty() and not asks.is_empty():
        # Calculate cumulative volume
        bids_with_cumsum = bids.with_columns(
            pl.col('volume').cumsum().alias('cumulative_volume')
        )
        asks_with_cumsum = asks.with_columns(
            pl.col('volume').cumsum().alias('cumulative_volume')
        )

        total_bid_volume = bids['volume'].sum()
        total_ask_volume = asks['volume'].sum()

        # Find levels containing 50% and 80% of volume
        def find_concentration_level(df, total_volume, percentage):
            target_volume = total_volume * percentage
            level = df.filter(pl.col('cumulative_volume') >= target_volume)
            return len(df) - len(level) + 1 if not level.is_empty() else len(df)

        bid_50_level = find_concentration_level(bids_with_cumsum, total_bid_volume, 0.5)
        bid_80_level = find_concentration_level(bids_with_cumsum, total_bid_volume, 0.8)

        ask_50_level = find_concentration_level(asks_with_cumsum, total_ask_volume, 0.5)
        ask_80_level = find_concentration_level(asks_with_cumsum, total_ask_volume, 0.8)

        print(f"\n< Liquidity Concentration:")
        print(f"  Bid side - 50% in top {bid_50_level} levels, 80% in top {bid_80_level} levels")
        print(f"  Ask side - 50% in top {ask_50_level} levels, 80% in top {ask_80_level} levels")

        # Concentration analysis
        if bid_50_level <= 3 or ask_50_level <= 3:
            print("  = High liquidity concentration - market depth may be thin")
        elif bid_50_level >= 8 or ask_50_level >= 8:
            print("  <
 Well-distributed liquidity - good market depth")
```

## Spoofing Heuristics (experimental)

`detect_spoofing()` is a **heuristic / experimental** volume-change detector.
There is no `enable_spoofing_detection()` API and no `EventType.SPOOFING_DETECTED`.
Pattern labels currently emitted: `quote_stuffing`, `layering`,
`momentum_ignition`, `flashing`, `pinging`, `order_manipulation`.

```python
async def spoofing_detection():
    suite = await TradingSuite.create("MNQ", features=["orderbook"])
    orderbook = suite.orderbook

    # Poll the heuristic detector (no dedicated spoofing event type)
    alerts = await orderbook.detect_spoofing()
    for alert in alerts:
        print(f"Heuristic: {alert}")

# Pattern labels currently used by the heuristic:
# quote_stuffing, layering, momentum_ignition, flashing, pinging, order_manipulation
```

## Iceberg Detection

```python
async def iceberg_detection():
    suite = await TradingSuite.create("MNQ", features=["orderbook"])
    orderbook = suite.orderbook

    # Enable iceberg detection
    detected_icebergs = await orderbook.detect_iceberg_orders(
        min_total_size=100,       # Minimum total iceberg size
        min_visible_ratio=0.2,    # Maximum visible portion
        time_window=300           # 5 minute window
    )

    print(f"> Iceberg Orders Detected: {len(detected_icebergs)}")

    for iceberg in detected_icebergs:
        side = iceberg['side']
        price = iceberg['price']
        estimated_size = iceberg['estimated_total_size']
        visible_size = iceberg['visible_size']
        confidence = iceberg['confidence']

        print(f"\n< Iceberg Order:")
        print(f"  Side: {side}")
        print(f"  Price: ${price:.2f}")
        print(f"  Estimated Total: {estimated_size:,}")
        print(f"  Visible: {visible_size:,}")
        print(f"  Confidence: {confidence:.2f}")

        # High confidence icebergs
        if confidence >= 0.8:
            print(f"  = High confidence iceberg - large hidden size!")

    # Real-time iceberg monitoring
    iceberg_tracker = {
        'detected_count': 0,
        'total_hidden_size': 0
    }

    async def on_iceberg_detected(event):
        """Handle real-time iceberg detection."""
        iceberg_data = event.data

        iceberg_tracker['detected_count'] += 1
        iceberg_tracker['total_hidden_size'] += iceberg_data.get('estimated_hidden_size', 0)

        print(f"> New iceberg detected at ${iceberg_data['price']:.2f}")
        print(f"  Estimated hidden: {iceberg_data.get('estimated_hidden_size', 0):,}")

    await suite.on(EventType.ICEBERG_DETECTED, on_iceberg_detected)

    # Monitor for new icebergs
    print("\n=
 Monitoring for iceberg orders...")
    await asyncio.sleep(180)  # 3 minutes

    print(f"\n= Iceberg Monitoring Summary:")
    print(f"  New icebergs detected: {iceberg_tracker['detected_count']}")
    print(f"  Total hidden size estimate: {iceberg_tracker['total_hidden_size']:,}")
```

## Volume Profile Analysis

```python
async def volume_profile_analysis():
    suite = await TradingSuite.create("MNQ", features=["orderbook"])
    orderbook = suite.orderbook

    # Get volume profile for current session
    volume_profile = await orderbook.get_volume_profile(
        time_window=3600,  # 1 hour window
        price_buckets=50   # 50 price levels
    )

    print("= Volume Profile Analysis:")

    # Find high volume nodes (HVN) and low volume nodes (LVN)
    max_volume = volume_profile['volume'].max()
    hvn_threshold = max_volume * 0.7  # 70% of max volume
    lvn_threshold = max_volume * 0.2  # 20% of max volume

    hvn_levels = volume_profile.filter(pl.col('volume') >= hvn_threshold)
    lvn_levels = volume_profile.filter(pl.col('volume') <= lvn_threshold)

    print(f"\n< High Volume Nodes (HVN):")
    for row in hvn_levels.iter_rows(named=True):
        print(f"  ${row['price_level']:.2f}: {row['volume']:,} contracts")

    print(f"\n=s  Low Volume Nodes (LVN) - Potential breakout levels:")
    for row in lvn_levels.head(5).iter_rows(named=True):
        print(f"  ${row['price_level']:.2f}: {row['volume']:,} contracts")

    # Point of Control (POC) - highest volume price
    poc_row = volume_profile.sort('volume', descending=True).head(1)
    if not poc_row.is_empty():
        poc_price = poc_row['price_level'][0]
        poc_volume = poc_row['volume'][0]
        print(f"\n=Q Point of Control (POC): ${poc_price:.2f} ({poc_volume:,} contracts)")

    # Value Area calculation (70% of volume)
    total_volume = volume_profile['volume'].sum()
    target_volume = total_volume * 0.7

    # Find value area range
    sorted_profile = volume_profile.sort('volume', descending=True)
    cumulative_volume = 0
    value_area_prices = []

    for row in sorted_profile.iter_rows(named=True):
        cumulative_volume += row['volume']
        value_area_prices.append(row['price_level'])

        if cumulative_volume >= target_volume:
            break

    if value_area_prices:
        value_area_high = max(value_area_prices)
        value_area_low = min(value_area_prices)

        print(f"\n= Value Area (70% of volume):")
        print(f"  High: ${value_area_high:.2f}")
        print(f"  Low: ${value_area_low:.2f}")
        print(f"  Range: ${value_area_high - value_area_low:.2f}")

        # Current price relative to value area
        current_price = (await orderbook.get_best_bid_ask())
        if current_price['bid'] and current_price['ask']:
            mid_price = (current_price['bid'] + current_price['ask']) / 2

            if mid_price > value_area_high:
                print(f"  = Price above value area - potential resistance")
            elif mid_price < value_area_low:
                print(f"  = Price below value area - potential support")
            else:
                print(f"   Price within value area")

    # Volume distribution analysis
    await analyze_volume_distribution(volume_profile)

async def analyze_volume_distribution(volume_profile):
    """Analyze the distribution characteristics of volume."""

    # Calculate statistics
    volumes = volume_profile['volume'].to_list()
    prices = volume_profile['price_level'].to_list()

    if volumes and prices:
        # Weighted average price by volume
        total_volume = sum(volumes)
        vwap = sum(p * v for p, v in zip(prices, volumes)) / total_volume

        # Volume distribution metrics
        max_volume = max(volumes)
        min_volume = min(volumes)
        avg_volume = sum(volumes) / len(volumes)

        # Concentration ratio (top 20% of levels contain what % of volume?)
        sorted_volumes = sorted(volumes, reverse=True)
        top_20_count = max(1, len(sorted_volumes) // 5)
        top_20_volume = sum(sorted_volumes[:top_20_count])
        concentration_ratio = top_20_volume / total_volume

        print(f"\n= Volume Distribution Analysis:")
        print(f"  VWAP: ${vwap:.2f}")
        print(f"  Volume Range: {min_volume:,} - {max_volume:,}")
        print(f"  Average Volume: {avg_volume:,.0f}")
        print(f"  Concentration Ratio: {concentration_ratio:.1%}")

        if concentration_ratio > 0.6:
            print("  = High concentration - volume clustered at few levels")
        elif concentration_ratio < 0.4:
            print("  <
 Well distributed volume across price levels")
        else:
            print("    Moderate volume concentration")
```

## Memory Management and Performance

### OrderBook Memory Management

```python
async def orderbook_memory_management():
    suite = await TradingSuite.create("MNQ", features=["orderbook"])
    orderbook = suite.orderbook

    # Check memory usage
    memory_stats = await orderbook.get_memory_stats()

    print("= OrderBook Memory Usage:")
    print(f"  Trade History: {memory_stats['trade_count']:,} trades ({memory_stats['trade_memory_mb']:.1f} MB)")
    print(f"  Depth Entries: {memory_stats['depth_entries']:,} levels ({memory_stats['depth_memory_mb']:.1f} MB)")
    print(f"  Total Memory: {memory_stats['total_memory_mb']:.1f} MB")

    # Memory limits
    limits = await orderbook.get_memory_limits()
    print(f"\nMemory Limits:")
    print(f"  Max trades: {limits['max_trades']:,}")
    print(f"  Max depth entries: {limits['max_depth_entries']:,}")
    print(f"  Max memory: {limits['max_memory_mb']:.0f} MB")

    # Usage ratios
    trade_usage = memory_stats['trade_count'] / limits['max_trades']
    depth_usage = memory_stats['depth_entries'] / limits['max_depth_entries']
    memory_usage = memory_stats['total_memory_mb'] / limits['max_memory_mb']

    print(f"\nUsage Ratios:")
    print(f"  Trade buffer: {trade_usage:.1%}")
    print(f"  Depth buffer: {depth_usage:.1%}")
    print(f"  Memory usage: {memory_usage:.1%}")

    # Cleanup recommendations
    if memory_usage > 0.8:
        print("  High memory usage - consider cleanup")

        # Manual cleanup (usually automatic)
        cleaned_count = await orderbook.cleanup_old_data(keep_minutes=30)
        print(f"> Cleaned up {cleaned_count:,} old entries")

# Performance monitoring
async def orderbook_performance_monitoring():
    suite = await TradingSuite.create("MNQ", features=["orderbook"])
    orderbook = suite.orderbook

    # Performance metrics
    perf_stats = await orderbook.get_performance_stats()

    print(" OrderBook Performance:")
    print(f"  Update Rate: {perf_stats['updates_per_second']:.1f}/sec")
    print(f"  Processing Latency: {perf_stats['avg_processing_latency_ms']:.2f}ms")
    print(f"  Query Response Time: {perf_stats['avg_query_time_ms']:.2f}ms")
    print(f"  Memory Growth Rate: {perf_stats['memory_growth_mb_per_hour']:.2f} MB/hr")

    # Performance optimization
    if perf_stats['avg_processing_latency_ms'] > 10:
        print("  High processing latency detected")

        # Enable performance optimizations
        await orderbook.enable_optimizations(
            batch_updates=True,      # Batch multiple updates
            reduce_precision=False,  # Keep full precision
            compress_history=True    # Compress old data
        )

        print(" Performance optimizations enabled")
```

## Best Practices

### 1. Efficient OrderBook Queries

```python
# Good: Get specific levels you need
bids = await orderbook.get_orderbook_bids(levels=10)
asks = await orderbook.get_orderbook_asks(levels=10)

# Avoid: Requesting more levels than you need
snapshot = await orderbook.get_orderbook_snapshot(levels=5)
```

### 2. Event-Driven Processing

```python
async def efficient_orderbook_monitoring():
    suite = await TradingSuite.create("MNQ", features=["orderbook"])

    # Good: Event-driven updates
    async def on_depth_update(event):
        # Process only the change
        update_data = event.data
        print(f"Depth updated at level {update_data['level']}")

    await suite.on(EventType.MARKET_DEPTH_UPDATE, on_depth_update)

    # Avoid: Continuous polling
    # while True:
    #     depth = await orderbook.get_orderbook_bids(levels=5)  # Expensive
    #     await asyncio.sleep(1)
```

### 3. Memory-Conscious Operations

```python
async def memory_conscious_analysis():
    suite = await TradingSuite.create("MNQ", features=["orderbook"])
    orderbook = suite.orderbook

    # Set reasonable memory limits
    await orderbook.configure_memory_limits(
        max_trades=5000,        # Keep last 5K trades
        max_depth_entries=1000, # 1K depth entries per side
        cleanup_interval=300    # Cleanup every 5 minutes
    )

    # Use time-based queries instead of keeping all data
    recent_trades = await orderbook.get_recent_trades(minutes=30)
    recent_volume_profile = await orderbook.get_volume_profile(time_window=1800)
```

### 4. Robust Error Handling

```python
async def robust_orderbook_operations():
    suite = await TradingSuite.create("MNQ", features=["orderbook"])
    orderbook = suite.orderbook

    try:
        # OrderBook operations with error handling
        best_prices = await orderbook.get_best_bid_ask()

        if not best_prices['bid'] or not best_prices['ask']:
            print("  No bid/ask available - market may be closed")
            return

        # Proceed with analysis
        imbalance = await orderbook.get_market_imbalance()

    except ConnectionError:
        print("= Connection lost - attempting reconnection")
        await suite.reconnect()

    except Exception as e:
        print(f"L OrderBook error: {e}")

        # Fallback to basic price data
        current_price = await suite.data.get_current_price()
        print(f"Fallback to basic price: ${current_price:.2f}")
```

## Integration with Trading Strategies

### OrderBook-Based Entry Signals

```python
async def orderbook_entry_signals():
    suite = await TradingSuite.create("MNQ", features=["orderbook"])
    orderbook = suite.orderbook

    signal_tracker = {
        'imbalance_signals': 0,
        'liquidity_signals': 0,
        'spoofing_signals': 0
    }

    async def check_entry_conditions():
        """Check OrderBook conditions for trade entries."""

        # Get market data
        imbalance = await orderbook.get_market_imbalance()
        best_prices = await orderbook.get_best_bid_ask()
        liquidity = await orderbook.get_liquidity_metrics()

        signals = []

        # Imbalance-based signals
        if imbalance > 0.6:  # Strong bid imbalance
            signals.append(("BUY", "Strong bid imbalance", imbalance))
            signal_tracker['imbalance_signals'] += 1
        elif imbalance < -0.6:  # Strong ask imbalance
            signals.append(("SELL", "Strong ask imbalance", imbalance))
            signal_tracker['imbalance_signals'] += 1

        # Liquidity-based signals
        if best_prices['spread'] > 5.0:  # Wide spread
            signals.append(("AVOID", "Wide spread - low liquidity", best_prices['spread']))
        elif best_prices['spread'] < 1.0:  # Tight spread
            signals.append(("FAVORABLE", "Tight spread - good liquidity", best_prices['spread']))
            signal_tracker['liquidity_signals'] += 1

        # Recent spoofing heuristic (experimental)
        spoofing_alerts = await orderbook.detect_spoofing()
        recent_patterns = len(spoofing_alerts) if spoofing_alerts else 0

        if recent_patterns > 3:  # Multiple recent spoofing patterns
            signals.append(("CAUTION", "Recent spoofing detected", recent_patterns))
            signal_tracker['spoofing_signals'] += 1

        # Print signals
        if signals:
            print(f"\n= OrderBook Entry Signals @ {datetime.now().strftime('%H:%M:%S')}:")
            for signal_type, description, value in signals:
                print(f"  {signal_type}: {description} ({value:.2f})")

        return signals

    # Monitor for entry signals
    for _ in range(20):  # Check 20 times
        await check_entry_conditions()
        await asyncio.sleep(15)  # Every 15 seconds

    print(f"\n= Signal Summary:")
    print(f"  Imbalance signals: {signal_tracker['imbalance_signals']}")
    print(f"  Liquidity signals: {signal_tracker['liquidity_signals']}")
    print(f"  Spoofing warnings: {signal_tracker['spoofing_signals']}")
```

## Summary

The ProjectX OrderBook provides comprehensive Level 2 market depth analysis:

- **Real-time Level 2 data** with WebSocket streaming
- **Market microstructure analysis** including spread, depth, and liquidity metrics
- **Advanced pattern detection** with spoofing and iceberg identification
- **Volume profile analysis** for identifying key price levels
- **Memory management** with sliding windows and automatic cleanup
- **Performance optimization** with event-driven updates and caching
- **Integration-ready** for sophisticated trading strategies

The OrderBook is designed for institutional-level market analysis with comprehensive error handling, real-time monitoring, and production-ready performance optimizations.

---

**Previous**: [Technical Indicators Guide](indicators.md) | **Back to**: [User Guide Index](../index.md)
