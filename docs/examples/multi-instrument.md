# Multi-Instrument Trading Examples

This guide provides comprehensive examples of multi-instrument trading patterns using the ProjectX Python SDK v3.5.0.

## Basic Multi-Instrument Setup

### Multiple Futures Contracts

```python
import asyncio
from project_x_py import TradingSuite

async def basic_multi_instrument():
    """Basic setup for multiple futures contracts."""

    # Create suite with multiple instruments
    suite = await TradingSuite.create(
        instruments=["MNQ", "ES", "MGC"],  # NASDAQ, S&P 500, Gold
        timeframes=["1min", "5min"],
        features=["orderbook", "risk_manager"]
    )

    print(f"Managing {len(suite)} instruments: {list(suite.keys())}")

    # Access individual instruments
    mnq_context = suite["MNQ"]
    es_context = suite["ES"]
    mgc_context = suite["MGC"]

    # Get current prices for all instruments
    for symbol, context in suite.items():
        current_price = await context.data.get_current_price()
        print(f"{symbol}: ${current_price:.2f}")

    await suite.disconnect()

asyncio.run(basic_multi_instrument())
```

### Cross-Market Analysis

```python
async def cross_market_analysis():
    """Analyze relationships between different market sectors."""

    suite = await TradingSuite.create(
        instruments=["ES", "MNQ", "MYM", "MGC", "MCL"],  # Stocks, Gold, Oil
        timeframes=["5min", "15min"]
    )

    # Collect 5min data for all instruments
    market_data = {}
    for symbol, context in suite.items():
        bars = await context.data.get_data("5min", count=100)
        if len(bars) > 0:
            market_data[symbol] = bars["close"].to_list()

    # Calculate correlation matrix
    print("Cross-Market Correlations:")
    symbols = list(market_data.keys())

    for i, symbol1 in enumerate(symbols):
        for j, symbol2 in enumerate(symbols):
            if i < j and symbol1 in market_data and symbol2 in market_data:
                # Simple correlation calculation
                returns1 = [market_data[symbol1][k]/market_data[symbol1][k-1] - 1
                           for k in range(1, len(market_data[symbol1]))]
                returns2 = [market_data[symbol2][k]/market_data[symbol2][k-1] - 1
                           for k in range(1, len(market_data[symbol2]))]

                if len(returns1) == len(returns2) and len(returns1) > 1:
                    import statistics
                    try:
                        corr = statistics.correlation(returns1, returns2)
                        print(f"  {symbol1} vs {symbol2}: {corr:.3f}")
                    except statistics.StatisticsError:
                        print(f"  {symbol1} vs {symbol2}: N/A")

    await suite.disconnect()

asyncio.run(cross_market_analysis())
```

## Pairs Trading Strategies

### ES/MNQ Spread Trading

```python
async def es_mnq_spread_trading():
    """Trade the spread between ES and MNQ futures."""

    suite = await TradingSuite.create(
        instruments=["ES", "MNQ"],
        timeframes=["1min", "5min"],
        features=["risk_manager"]
    )

    es_context = suite["ES"]
    mnq_context = suite["MNQ"]

    # Calculate the spread (normalized by contract values)
    es_price = await es_context.data.get_current_price()
    mnq_price = await mnq_context.data.get_current_price()

    # ES multiplier: $50, MNQ multiplier: $20
    spread = (es_price * 50) - (mnq_price * 20)
    print(f"ES/MNQ Spread: ${spread:.2f}")

    # Simple spread trading logic
    SPREAD_THRESHOLD = 500  # $500 threshold

    if spread > SPREAD_THRESHOLD:
        print("🔻 ES expensive relative to MNQ - Trade: Short ES, Long MNQ")

        # Place spread trade
        tasks = [
            es_context.orders.place_market_order(
                contract_id=es_context.instrument_info.id,
                side=1,  # Sell ES
                size=1
            ),
            mnq_context.orders.place_market_order(
                contract_id=mnq_context.instrument_info.id,
                side=0,  # Buy MNQ
                size=1
            )
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, result in enumerate(results):
            symbol = ["ES", "MNQ"][i]
            if isinstance(result, Exception):
                print(f"❌ {symbol} order failed: {result}")
            else:
                print(f"✅ {symbol} order placed: {result.order_id}")

    elif spread < -SPREAD_THRESHOLD:
        print("🔺 MNQ expensive relative to ES - Trade: Long ES, Short MNQ")

        # Place reverse spread trade
        tasks = [
            es_context.orders.place_market_order(
                contract_id=es_context.instrument_info.id,
                side=0,  # Buy ES
                size=1
            ),
            mnq_context.orders.place_market_order(
                contract_id=mnq_context.instrument_info.id,
                side=1,  # Sell MNQ
                size=1
            )
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, result in enumerate(results):
            symbol = ["ES", "MNQ"][i]
            if isinstance(result, Exception):
                print(f"❌ {symbol} order failed: {result}")
            else:
                print(f"✅ {symbol} order placed: {result.order_id}")

    else:
        print("➡️ Spread within normal range - No trade")

    await suite.disconnect()

asyncio.run(es_mnq_spread_trading())
```

### Sector Rotation Strategy

```python
async def sector_rotation_strategy():
    """Rotate between different sectors based on relative strength."""

    suite = await TradingSuite.create(
        instruments=["ES", "MNQ", "MYM", "MGC"],  # Large Cap, Tech, Small Cap, Gold
        timeframes=["15min", "1hour"],
        features=["risk_manager"]
    )

    # Calculate relative strength for each instrument
    relative_strength = {}

    for symbol, context in suite.items():
        # Get recent data
        bars = await context.data.get_data("15min", count=20)
        if len(bars) >= 10:
            # Calculate momentum (20-period vs 10-period average)
            recent_avg = bars.tail(10)["close"].mean()
            longer_avg = bars["close"].mean()

            momentum = (recent_avg / longer_avg - 1) * 100
            relative_strength[symbol] = momentum
            print(f"{symbol} Momentum: {momentum:.2f}%")

    if relative_strength:
        # Find strongest and weakest instruments
        strongest = max(relative_strength.items(), key=lambda x: x[1])
        weakest = min(relative_strength.items(), key=lambda x: x[1])

        print(f"\\n🚀 Strongest: {strongest[0]} ({strongest[1]:.2f}%)")
        print(f"📉 Weakest: {weakest[0]} ({weakest[1]:.2f}%)")

        # If momentum spread is significant, execute rotation
        momentum_spread = strongest[1] - weakest[1]
        if momentum_spread > 2.0:  # 2% momentum difference
            print(f"\\n🔄 Executing sector rotation (spread: {momentum_spread:.2f}%)")

            # Long the strongest, short the weakest
            tasks = [
                suite[strongest[0]].orders.place_market_order(
                    contract_id=suite[strongest[0]].instrument_id,
                    side=0,  # Buy strongest
                    size=1
                ),
                suite[weakest[0]].orders.place_market_order(
                    contract_id=suite[weakest[0]].instrument_id,
                    side=1,  # Sell weakest
                    size=1
                )
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            actions = ["Long", "Short"]
            symbols = [strongest[0], weakest[0]]
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    print(f"❌ {actions[i]} {symbols[i]} failed: {result}")
                else:
                    print(f"✅ {actions[i]} {symbols[i]}: {result.order_id}")
        else:
            print(f"\\n➡️ Momentum spread too small ({momentum_spread:.2f}%) - No rotation")

    await suite.disconnect()

asyncio.run(sector_rotation_strategy())
```

## Portfolio Management

### Portfolio Exposure Management

```python
async def portfolio_exposure_management():
    """Manage portfolio exposure across multiple instruments."""

    suite = await TradingSuite.create(
        instruments=["MNQ", "ES", "MGC", "MCL"],  # Diversified portfolio
        timeframes=["5min"],
        features=["risk_manager"]
    )

    # Calculate current portfolio exposure
    total_exposure = 0
    positions_summary = {}

    print("Current Portfolio Positions:")
    print("-" * 50)

    for symbol, context in suite.items():
        position = await context.positions.get_position(symbol)
        if position and position.size != 0:
            # Get current market value
            current_price = await context.data.get_current_price()
            market_value = abs(position.size) * current_price

            # Calculate position value (varies by contract)
            if symbol in ["ES"]:
                multiplier = 50
            elif symbol in ["MNQ", "MYM"]:
                multiplier = 20
            elif symbol in ["MGC"]:
                multiplier = 100
            elif symbol in ["MCL"]:
                multiplier = 1000
            else:
                multiplier = 1

            position_value = market_value * multiplier
            total_exposure += position_value

            positions_summary[symbol] = {
                'size': position.size,
                'price': current_price,
                'value': position_value,
                'pnl': position.unrealized_pnl
            }

            direction = "LONG" if position.size > 0 else "SHORT"
            print(f"{symbol:4} | {direction:5} | {abs(position.size):3.0f} @ ${current_price:8.2f} | "
                  f"Value: ${position_value:10,.0f} | P&L: ${position.unrealized_pnl:8.2f}")
        else:
            print(f"{symbol:4} | ----  | No Position")

    print("-" * 50)
    print(f"Total Portfolio Exposure: ${total_exposure:,.0f}")

    # Portfolio risk metrics
    total_pnl = sum(pos['pnl'] for pos in positions_summary.values())
    print(f"Total Unrealized P&L: ${total_pnl:.2f}")

    if total_exposure > 0:
        portfolio_return = (total_pnl / total_exposure) * 100
        print(f"Portfolio Return: {portfolio_return:.2f}%")

    # Risk management: Check if exposure is too high
    MAX_EXPOSURE = 500000  # $500k max exposure
    if total_exposure > MAX_EXPOSURE:
        print(f"\\n⚠️ WARNING: Portfolio exposure (${total_exposure:,.0f}) exceeds limit (${MAX_EXPOSURE:,.0f})")

        # Calculate reduction needed
        reduction_needed = total_exposure - MAX_EXPOSURE
        print(f"   Need to reduce exposure by: ${reduction_needed:,.0f}")

        # Suggest position reductions (largest positions first)
        sorted_positions = sorted(
            positions_summary.items(),
            key=lambda x: x[1]['value'],
            reverse=True
        )

        print("\\n📉 Suggested Position Reductions:")
        for symbol, pos_data in sorted_positions[:2]:  # Top 2 largest positions
            reduction_pct = min(50, (reduction_needed / pos_data['value']) * 100)
            contracts_to_close = max(1, int(abs(pos_data['size']) * reduction_pct / 100))
            print(f"   {symbol}: Reduce by {contracts_to_close} contracts ({reduction_pct:.0f}%)")

    await suite.disconnect()

asyncio.run(portfolio_exposure_management())
```

### Dynamic Hedging

```python
async def dynamic_hedging_strategy():
    """Implement dynamic hedging across correlated instruments."""

    suite = await TradingSuite.create(
        instruments=["ES", "MNQ", "MYM"],  # Correlated equity indices
        timeframes=["5min"],
        features=["risk_manager"]
    )

    # Calculate current delta exposure
    print("Portfolio Delta Analysis:")
    print("-" * 40)

    total_delta = 0
    position_deltas = {}

    for symbol, context in suite.items():
        position = await context.positions.get_position(symbol)
        if position and position.size != 0:
            # Simplified delta calculation (1.0 for equity futures)
            delta = position.size * 1.0  # Each contract has delta of 1
            total_delta += delta
            position_deltas[symbol] = delta

            print(f"{symbol}: {position.size:3.0f} contracts | Delta: {delta:6.1f}")
        else:
            position_deltas[symbol] = 0.0
            print(f"{symbol}:  No position      | Delta:    0.0")

    print("-" * 40)
    print(f"Total Portfolio Delta: {total_delta:.1f}")

    # Hedging logic: Keep portfolio delta near zero
    DELTA_THRESHOLD = 2.0  # Allow +/- 2 delta

    if abs(total_delta) > DELTA_THRESHOLD:
        print(f"\\n⚖️ Portfolio needs hedging (Delta: {total_delta:.1f})")

        # Choose hedging instrument (ES is most liquid)
        hedge_symbol = "ES"
        hedge_context = suite[hedge_symbol]

        # Calculate hedge size needed
        hedge_size = -int(total_delta)  # Opposite direction

        if hedge_size != 0:
            print(f"📈 Hedge Trade: {abs(hedge_size)} {hedge_symbol} contracts ({'Long' if hedge_size > 0 else 'Short'})")

            try:
                hedge_order = await hedge_context.orders.place_market_order(
                    contract_id=hedge_context.instrument_id,
                    side=0 if hedge_size > 0 else 1,
                    size=abs(hedge_size)
                )
                print(f"✅ Hedge order placed: {hedge_order.order_id}")

                # Update expected delta
                new_total_delta = total_delta + hedge_size
                print(f"📊 Expected new portfolio delta: {new_total_delta:.1f}")

            except Exception as e:
                print(f"❌ Hedge order failed: {e}")
    else:
        print(f"\\n✅ Portfolio delta within tolerance ({total_delta:.1f})")

    await suite.disconnect()

asyncio.run(dynamic_hedging_strategy())
```

## Real-time Multi-Instrument Monitoring

### Live Portfolio Dashboard

```python
from project_x_py import EventType
import asyncio
from datetime import datetime

async def live_portfolio_dashboard():
    """Real-time monitoring dashboard for multi-instrument portfolio."""

    suite = await TradingSuite.create(
        instruments=["MNQ", "ES", "MGC", "MCL"],
        timeframes=["1min", "5min"],
        features=["orderbook", "risk_manager"]
    )

    # Portfolio state tracking
    portfolio_state = {
        "last_update": datetime.now(),
        "prices": {},
        "positions": {},
        "pnl": 0.0,
        "exposure": 0.0
    }

    async def update_portfolio_metrics():
        """Update portfolio metrics."""
        total_pnl = 0
        total_exposure = 0

        for symbol, context in suite.items():
            try:
                # Get current price
                current_price = await context.data.get_current_price()
                portfolio_state["prices"][symbol] = current_price

                # Get position
                position = await context.positions.get_position(symbol)
                if position and position.size != 0:
                    portfolio_state["positions"][symbol] = {
                        "size": position.size,
                        "avg_price": position.avg_price,
                        "pnl": position.unrealized_pnl
                    }
                    total_pnl += position.unrealized_pnl
                    total_exposure += abs(position.size * current_price)
                else:
                    portfolio_state["positions"][symbol] = None

            except Exception as e:
                print(f"❌ Error updating {symbol}: {e}")

        portfolio_state["pnl"] = total_pnl
        portfolio_state["exposure"] = total_exposure
        portfolio_state["last_update"] = datetime.now()

    def print_dashboard():
        """Print the portfolio dashboard."""
        print("\\n" + "=" * 80)
        print(f"📊 LIVE PORTFOLIO DASHBOARD - {portfolio_state['last_update'].strftime('%H:%M:%S')}")
        print("=" * 80)

        # Current prices
        print("\\n💹 Current Prices:")
        for symbol, price in portfolio_state["prices"].items():
            print(f"  {symbol:4}: ${price:8.2f}")

        # Positions
        print("\\n📈 Positions:")
        print("  Symbol | Size  |  Avg Price  | Current P&L")
        print("  " + "-" * 42)

        for symbol in suite.keys():
            position = portfolio_state["positions"].get(symbol)
            if position:
                pnl_color = "🟢" if position["pnl"] >= 0 else "🔴"
                print(f"  {symbol:6} | {position['size']:4.0f}  | ${position['avg_price']:8.2f}  | "
                      f"{pnl_color} ${position['pnl']:8.2f}")
            else:
                print(f"  {symbol:6} | ---- | --------  | ---- ----")

        # Portfolio summary
        print("\\n💰 Portfolio Summary:")
        pnl_color = "🟢" if portfolio_state["pnl"] >= 0 else "🔴"
        print(f"  Total P&L: {pnl_color} ${portfolio_state['pnl']:10.2f}")
        print(f"  Exposure:  📊 ${portfolio_state['exposure']:10,.0f}")

        if portfolio_state["exposure"] > 0:
            return_pct = (portfolio_state["pnl"] / portfolio_state["exposure"]) * 100
            return_color = "🟢" if return_pct >= 0 else "🔴"
            print(f"  Return:    {return_color} {return_pct:8.2f}%")

    # Event handlers for real-time updates
    for symbol, context in suite.items():
        # Price update handler
        async def make_price_handler(sym):
            async def on_new_bar(event):
                if event.timeframe == "1min":
                    await update_portfolio_metrics()
                    print_dashboard()
            return on_new_bar

        # Position change handler
        async def make_position_handler(sym):
            async def on_position_changed(event):
                await update_portfolio_metrics()
                print_dashboard()
            return on_position_changed

        price_handler = await make_price_handler(symbol)
        position_handler = await make_position_handler(symbol)

        await context.on(EventType.NEW_BAR, price_handler)
        await context.on(EventType.POSITION_CHANGED, position_handler)

    # Initial dashboard update
    await update_portfolio_metrics()
    print_dashboard()

    print("\\n🔄 Monitoring portfolio in real-time... (Press Ctrl+C to stop)")

    try:
        # Update dashboard every 30 seconds as backup
        while True:
            await asyncio.sleep(30)
            await update_portfolio_metrics()
            print_dashboard()

    except KeyboardInterrupt:
        print("\\n🛑 Dashboard stopped by user")

    finally:
        await suite.disconnect()
        print("✅ Disconnected successfully")

# Run the dashboard
asyncio.run(live_portfolio_dashboard())
```

## Advanced Multi-Instrument Patterns

### Cross-Instrument Arbitrage

```python
async def cross_instrument_arbitrage():
    """Detect and execute arbitrage opportunities between related instruments."""

    suite = await TradingSuite.create(
        instruments=["ES", "SPY"],  # E-mini S&P 500 futures vs ETF
        timeframes=["1min"],
        features=["orderbook"]
    )

    es_context = suite["ES"]
    spy_context = suite["SPY"] if "SPY" in suite else None

    if not spy_context:
        print("❌ SPY not available for arbitrage")
        await suite.disconnect()
        return

    # Monitor for arbitrage opportunities
    print("🔍 Monitoring ES/SPY arbitrage opportunities...")

    async def check_arbitrage():
        try:
            # Get current prices
            es_price = await es_context.data.get_current_price()
            spy_price = await spy_context.data.get_current_price()

            # Calculate theoretical fair value
            # ES contract size is $50 per point, SPY is $1 per share
            es_value = es_price * 50
            spy_value = spy_price * 1

            # Calculate basis (futures premium/discount to spot)
            basis = es_value - (spy_value * 50)  # Normalize to contract size

            print(f"ES: ${es_price:.2f} | SPY: ${spy_price:.2f} | Basis: ${basis:.2f}")

            # Arbitrage thresholds
            ARBITRAGE_THRESHOLD = 25.0  # $25 basis threshold

            if basis > ARBITRAGE_THRESHOLD:
                print(f"🔺 ES overvalued by ${basis:.2f} - Sell ES, Buy SPY")

                # Execute arbitrage
                tasks = [
                    es_context.orders.place_market_order(
                        contract_id=es_context.instrument_id,
                        side=1,  # Sell ES
                        size=1
                    ),
                    spy_context.orders.place_market_order(
                        contract_id=spy_context.instrument_id,
                        side=0,  # Buy SPY equivalent
                        size=50  # 50 shares to match 1 ES contract
                    )
                ]

                results = await asyncio.gather(*tasks, return_exceptions=True)
                for i, result in enumerate(results):
                    symbol = ["ES", "SPY"][i]
                    if isinstance(result, Exception):
                        print(f"❌ {symbol} arbitrage leg failed: {result}")
                    else:
                        print(f"✅ {symbol} arbitrage executed: {result.order_id}")

            elif basis < -ARBITRAGE_THRESHOLD:
                print(f"🔻 ES undervalued by ${abs(basis):.2f} - Buy ES, Sell SPY")

                # Execute reverse arbitrage
                tasks = [
                    es_context.orders.place_market_order(
                        contract_id=es_context.instrument_id,
                        side=0,  # Buy ES
                        size=1
                    ),
                    spy_context.orders.place_market_order(
                        contract_id=spy_context.instrument_id,
                        side=1,  # Sell SPY equivalent
                        size=50  # 50 shares to match 1 ES contract
                    )
                ]

                results = await asyncio.gather(*tasks, return_exceptions=True)
                for i, result in enumerate(results):
                    symbol = ["ES", "SPY"][i]
                    if isinstance(result, Exception):
                        print(f"❌ {symbol} arbitrage leg failed: {result}")
                    else:
                        print(f"✅ {symbol} arbitrage executed: {result.order_id}")

            else:
                print(f"➡️ No arbitrage opportunity (basis: ${basis:.2f})")

        except Exception as e:
            print(f"❌ Arbitrage check failed: {e}")

    # Check for arbitrage every 10 seconds
    try:
        for _ in range(18):  # Run for 3 minutes
            await check_arbitrage()
            await asyncio.sleep(10)
    except KeyboardInterrupt:
        print("\\n🛑 Arbitrage monitoring stopped")

    await suite.disconnect()

asyncio.run(cross_instrument_arbitrage())
```

## Best Practices

### Resource Management

```python
async def resource_management_example():
    """Demonstrate proper resource management for multi-instrument trading."""

    # Use context manager for automatic cleanup
    async with TradingSuite.create([
        "MNQ", "ES", "MGC", "MCL", "MYM"
    ], features=["orderbook", "risk_manager"]) as suite:

        # Monitor resource usage
        stats = await suite.get_stats()
        print(f"Initial memory usage: {stats.get('memory_usage_mb', 0):.1f} MB")

        # Your trading logic here
        for symbol, context in suite.items():
            # Check component statistics
            order_stats = await context.orders.get_stats()
            print(f"{symbol} - Orders placed: {order_stats.get('orders_placed', 0)}, Errors: {order_stats.get('error_count', 0)}")

        # Periodic resource monitoring
        stats = await suite.get_stats()
        if stats.get('memory_usage_mb', 0) > 100:  # 100MB threshold
            print("⚠️ High memory usage detected")

        # Suite automatically disconnects and cleans up on exit

    print("✅ All resources cleaned up automatically")

asyncio.run(resource_management_example())
```

### Error Handling

```python
async def error_handling_example():
    """Demonstrate robust error handling for multi-instrument operations."""

    try:
        suite = await TradingSuite.create([
            "MNQ", "ES", "INVALID_SYMBOL"  # Intentional invalid symbol
        ])

        # Handle partial initialization
        print(f"Successfully initialized {len(suite)} instruments")
        print(f"Available instruments: {list(suite.keys())}")

        # Robust order placement
        order_tasks = []
        for symbol, context in suite.items():
            try:
                task = context.orders.place_market_order(
                    contract_id=context.instrument_id,
                    side=0, size=1
                )
                order_tasks.append((symbol, task))
            except Exception as e:
                print(f"❌ Failed to create order task for {symbol}: {e}")

        # Execute orders with error handling
        if order_tasks:
            tasks = [task for _, task in order_tasks]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for i, result in enumerate(results):
                symbol = order_tasks[i][0]
                if isinstance(result, Exception):
                    print(f"❌ {symbol} order failed: {result}")
                else:
                    print(f"✅ {symbol} order succeeded: {result.order_id}")

    except Exception as e:
        print(f"❌ Suite creation failed: {e}")

    finally:
        if 'suite' in locals():
            await suite.disconnect()

asyncio.run(error_handling_example())
```

## Migration from Single to Multi-Instrument

### Before (v3.4.x)

```python
# Old single-instrument pattern
suite = await TradingSuite.create("MNQ")
bars = await suite.data.get_data("5min")
order = await suite.orders.place_market_order(...)
```

### After (v3.5.0)

```python
# New multi-instrument pattern (recommended)
suite = await TradingSuite.create(["MNQ"])  # List notation
mnq = suite["MNQ"]  # Explicit instrument access
bars = await mnq.data.get_data("5min")
order = await mnq.orders.place_market_order(...)

# Or full multi-instrument
suite = await TradingSuite.create(["MNQ", "ES"])
for symbol, context in suite.items():
    bars = await context.data.get_data("5min")
    # Process each instrument
```

### Backward Compatibility

```python
# This still works but shows deprecation warnings
suite = await TradingSuite.create("MNQ")  # Single string (legacy)
bars = await suite.data.get_data("5min")   # Direct access (deprecated)

# Recommended migration path:
suite = await TradingSuite.create(["MNQ"])  # Convert to list
mnq = suite["MNQ"]                          # Explicit access
bars = await mnq.data.get_data("5min")     # Through context
```

These examples demonstrate the power and flexibility of the multi-instrument architecture in ProjectX Python SDK v3.5.0. Start with basic multi-instrument setups and gradually implement more sophisticated strategies as your trading requirements evolve.
