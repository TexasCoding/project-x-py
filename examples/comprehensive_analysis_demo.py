#!/usr/bin/env python3
"""
Comprehensive Analysis Demo

This example showcases the enhanced ProjectX package capabilities including:
1. Comprehensive API endpoint coverage
2. Advanced technical indicators (MACD, Stochastic, Williams %R, ATR, ADX, CCI)
3. Statistical analysis functions
4. Pattern recognition (candlestick and chart patterns)
5. Portfolio performance analysis
6. Risk management calculations
7. Market microstructure analysis

Author: TexasCoding
Date: June 2025
"""

from datetime import datetime, timedelta

import polars as pl

from project_x_py import (
    ProjectX,
    # Market Microstructure
    analyze_bid_ask_spread,
    # Advanced Technical Indicators
    calculate_adx,
    calculate_atr,
    calculate_bollinger_bands,
    calculate_commodity_channel_index,
    # Statistical Analysis
    calculate_correlation_matrix,
    calculate_macd,
    calculate_max_drawdown,
    # Portfolio Analysis
    calculate_portfolio_metrics,
    calculate_position_sizing,
    calculate_sharpe_ratio,
    calculate_stochastic,
    calculate_volatility_metrics,
    calculate_volume_profile,
    calculate_williams_r,
    # Utility functions
    create_data_snapshot,
    # Pattern Recognition
    detect_candlestick_patterns,
    detect_chart_patterns,
)


def demonstrate_enhanced_api_coverage(client: ProjectX):
    """Demonstrate comprehensive API endpoint access."""
    print("=" * 80)
    print("📊 ENHANCED API COVERAGE DEMONSTRATION")
    print("=" * 80)

    try:
        # 1. Trade History Analysis
        print("\n1. 📈 Trade History Analysis")
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)

        trades = client.search_trades(
            start_date=start_date, end_date=end_date, limit=50
        )
        print(f"   Found {len(trades)} trades in the last 30 days")

        if trades:
            total_pnl = sum(trade.get("pnl", 0) for trade in trades)
            print(f"   Total P&L: ${total_pnl:.2f}")

        # 2. Position History
        print("\n2. 📊 Position History")
        position_history = client.search_position_history(
            start_date=start_date, include_closed=True, limit=20
        )
        print(f"   Found {len(position_history)} position records")

        # 3. Account Performance Metrics
        print("\n3. 💰 Account Performance")
        performance = client.get_account_performance(start_date=start_date)
        if "error" not in performance:
            print(f"   Total P&L: ${performance.get('totalPnl', 0):.2f}")
            print(f"   Win Rate: {performance.get('winRate', 0) * 100:.1f}%")
            print(f"   Profit Factor: {performance.get('profitFactor', 0):.2f}")

        # 4. Risk Metrics
        print("\n4. ⚠️ Risk Management")
        risk_metrics = client.get_risk_metrics()
        if "error" not in risk_metrics:
            print(f"   Current Risk: ${risk_metrics.get('currentRisk', 0):.2f}")
            print(f"   Risk Limit: ${risk_metrics.get('riskLimit', 0):.2f}")

        # 5. Account Settings
        print("\n5. ⚙️ Account Configuration")
        settings = client.get_account_settings()
        if "error" not in settings:
            print(f"   Max Position Size: {settings.get('maxPositionSize', 'N/A')}")
            print(f"   Risk Limit: ${settings.get('riskLimit', 0)}")

        # 6. Account Statements
        print("\n6. 📋 Account Statements")
        statements = client.get_account_statements(start_date=start_date)
        print(f"   Retrieved {len(statements)} statements")

        # 7. Tick Data (if available)
        print("\n7. 🔥 Tick-Level Data")
        try:
            tick_data = client.get_tick_data("MGC", limit=100)
            if tick_data is not None:
                print(f"   Retrieved {len(tick_data)} ticks")
                print(f"   Columns: {tick_data.columns}")
            else:
                print("   No tick data available")
        except Exception as e:
            print(f"   Tick data not available: {e}")

    except Exception as e:
        print(f"⚠️ API Coverage Demo Error: {e}")


def demonstrate_advanced_technical_indicators(data: pl.DataFrame):
    """Demonstrate advanced technical indicator calculations."""
    print("\n" + "=" * 80)
    print("📈 ADVANCED TECHNICAL INDICATORS")
    print("=" * 80)

    if data.is_empty():
        print("❌ No data available for technical analysis")
        return data

    print(f"📊 Analyzing {len(data)} bars of OHLCV data")

    # 1. MACD - Trend following momentum indicator
    print("\n1. 📈 MACD (Moving Average Convergence Divergence)")
    data = calculate_macd(data, fast_period=12, slow_period=26, signal_period=9)
    latest_macd = data.select(["macd", "macd_signal", "macd_histogram"]).tail(1)
    print(f"   Latest MACD: {latest_macd.item(0, 'macd'):.4f}")
    print(f"   Signal Line: {latest_macd.item(0, 'macd_signal'):.4f}")
    print(f"   Histogram: {latest_macd.item(0, 'macd_histogram'):.4f}")

    # 2. Stochastic Oscillator - Momentum indicator
    print("\n2. 📊 Stochastic Oscillator")
    data = calculate_stochastic(data, k_period=14, d_period=3)
    latest_stoch = data.select(["stoch_k", "stoch_d"]).tail(1)
    print(f"   %K: {latest_stoch.item(0, 'stoch_k'):.2f}")
    print(f"   %D: {latest_stoch.item(0, 'stoch_d'):.2f}")

    # 3. Williams %R - Momentum indicator
    print("\n3. 📉 Williams %R")
    data = calculate_williams_r(data, period=14)
    latest_wr = data.select("williams_r").tail(1).item()
    print(f"   Williams %R: {latest_wr:.2f}")

    # 4. Average True Range (ATR) - Volatility indicator
    print("\n4. 📏 Average True Range (ATR)")
    data = calculate_atr(data, period=14)
    latest_atr = data.select("atr_14").tail(1).item()
    print(f"   ATR(14): {latest_atr:.4f}")

    # 5. Average Directional Index (ADX) - Trend strength
    print("\n5. 🎯 Average Directional Index (ADX)")
    data = calculate_adx(data, period=14)
    latest_adx = data.select(["adx", "di_plus", "di_minus"]).tail(1)
    print(f"   ADX: {latest_adx.item(0, 'adx'):.2f}")
    print(f"   +DI: {latest_adx.item(0, 'di_plus'):.2f}")
    print(f"   -DI: {latest_adx.item(0, 'di_minus'):.2f}")

    # 6. Commodity Channel Index (CCI) - Momentum indicator
    print("\n6. 📊 Commodity Channel Index (CCI)")
    data = calculate_commodity_channel_index(data, period=20)
    latest_cci = data.select("cci").tail(1).item()
    print(f"   CCI: {latest_cci:.2f}")

    # 7. Bollinger Bands - Volatility bands
    print("\n7. 📈 Bollinger Bands")
    data = calculate_bollinger_bands(data, period=20, std_dev=2.0)
    latest_bb = data.select(["bb_upper", "bb_middle", "bb_lower", "close"]).tail(1)
    close_price = latest_bb.item(0, "close")
    upper_band = latest_bb.item(0, "bb_upper")
    lower_band = latest_bb.item(0, "bb_lower")

    print(f"   Upper Band: {upper_band:.4f}")
    print(f"   Middle Band: {latest_bb.item(0, 'bb_middle'):.4f}")
    print(f"   Lower Band: {lower_band:.4f}")
    print(
        f"   Price Position: {((close_price - lower_band) / (upper_band - lower_band) * 100):.1f}%"
    )

    return data


def demonstrate_statistical_analysis(data: pl.DataFrame):
    """Demonstrate statistical analysis capabilities."""
    print("\n" + "=" * 80)
    print("📊 STATISTICAL ANALYSIS")
    print("=" * 80)

    if data.is_empty():
        print("❌ No data available for statistical analysis")
        return

    # 1. Correlation Analysis
    print("\n1. 🔗 Correlation Matrix")
    price_columns = ["open", "high", "low", "close"]
    corr_matrix = calculate_correlation_matrix(data, columns=price_columns)
    print("   OHLC Correlation Matrix:")
    print(corr_matrix)

    # 2. Volatility Metrics
    print("\n2. 📈 Volatility Analysis")
    vol_metrics = calculate_volatility_metrics(data, price_column="close", window=20)
    if "error" not in vol_metrics:
        print(f"   Daily Volatility: {vol_metrics['volatility']:.4f}")
        print(f"   Annualized Volatility: {vol_metrics['annualized_volatility']:.2%}")
        print(
            f"   Average Rolling Vol: {vol_metrics.get('avg_rolling_volatility', 0):.4f}"
        )

    # 3. Sharpe Ratio
    print("\n3. 📊 Risk-Adjusted Returns")
    data_with_returns = data.with_columns(pl.col("close").pct_change().alias("returns"))
    sharpe = calculate_sharpe_ratio(data_with_returns, risk_free_rate=0.02)
    print(f"   Sharpe Ratio: {sharpe:.2f}")

    # 4. Maximum Drawdown
    print("\n4. 📉 Drawdown Analysis")
    dd_metrics = calculate_max_drawdown(data, price_column="close")
    if "error" not in dd_metrics:
        print(f"   Max Drawdown: {dd_metrics['max_drawdown']:.2%}")
        print(f"   Drawdown Duration: {dd_metrics['max_drawdown_duration']} periods")


def demonstrate_pattern_recognition(data: pl.DataFrame):
    """Demonstrate pattern recognition capabilities."""
    print("\n" + "=" * 80)
    print("🔍 PATTERN RECOGNITION")
    print("=" * 80)

    if data.is_empty():
        print("❌ No data available for pattern recognition")
        return

    # 1. Candlestick Patterns
    print("\n1. 🕯️ Candlestick Pattern Detection")
    patterns_data = detect_candlestick_patterns(data)

    # Count pattern occurrences
    doji_count = patterns_data.filter(pl.col("doji") == True).height
    hammer_count = patterns_data.filter(pl.col("hammer") == True).height
    shooting_star_count = patterns_data.filter(pl.col("shooting_star") == True).height
    long_body_count = patterns_data.filter(pl.col("long_body") == True).height

    print(f"   Doji patterns: {doji_count}")
    print(f"   Hammer patterns: {hammer_count}")
    print(f"   Shooting star patterns: {shooting_star_count}")
    print(f"   Long body candles: {long_body_count}")

    # 2. Chart Patterns
    print("\n2. 📈 Chart Pattern Detection")
    chart_patterns = detect_chart_patterns(data, price_column="close", window=20)
    if "error" not in chart_patterns:
        print(f"   Double tops: {len(chart_patterns['double_tops'])}")
        print(f"   Double bottoms: {len(chart_patterns['double_bottoms'])}")

        # Show details of any double tops found
        if chart_patterns["double_tops"]:
            for i, pattern in enumerate(
                chart_patterns["double_tops"][:3]
            ):  # Show first 3
                print(
                    f"     Double Top {i + 1}: ${pattern['price']:.2f} (Strength: {pattern['strength']:.2f})"
                )


def demonstrate_portfolio_analysis():
    """Demonstrate portfolio analysis capabilities."""
    print("\n" + "=" * 80)
    print("💼 PORTFOLIO ANALYSIS")
    print("=" * 80)

    # Sample trade data
    sample_trades = [
        {"pnl": 500, "size": 1, "timestamp": "2024-06-01"},
        {"pnl": -200, "size": 1, "timestamp": "2024-06-02"},
        {"pnl": 750, "size": 2, "timestamp": "2024-06-03"},
        {"pnl": -150, "size": 1, "timestamp": "2024-06-04"},
        {"pnl": 300, "size": 1, "timestamp": "2024-06-05"},
        {"pnl": -400, "size": 1, "timestamp": "2024-06-06"},
        {"pnl": 600, "size": 2, "timestamp": "2024-06-07"},
        {"pnl": 250, "size": 1, "timestamp": "2024-06-08"},
    ]

    print("\n1. 📊 Portfolio Performance Metrics")
    portfolio_metrics = calculate_portfolio_metrics(
        sample_trades, initial_balance=50000
    )

    if "error" not in portfolio_metrics:
        print(f"   Total Trades: {portfolio_metrics['total_trades']}")
        print(f"   Total P&L: ${portfolio_metrics['total_pnl']:.2f}")
        print(f"   Total Return: {portfolio_metrics['total_return']:.2%}")
        print(f"   Win Rate: {portfolio_metrics['win_rate']:.1%}")
        print(f"   Profit Factor: {portfolio_metrics['profit_factor']:.2f}")
        print(f"   Average Win: ${portfolio_metrics['avg_win']:.2f}")
        print(f"   Average Loss: ${portfolio_metrics['avg_loss']:.2f}")
        print(f"   Max Drawdown: {portfolio_metrics['max_drawdown']:.2%}")
        print(f"   Expectancy: ${portfolio_metrics['expectancy']:.2f}")

    # 2. Position Sizing
    print("\n2. 🎯 Position Sizing Calculator")
    account_balance = 50000
    risk_per_trade = 0.02  # 2%
    entry_price = 2050.0
    stop_loss_price = 2040.0
    tick_value = 1.0

    sizing = calculate_position_sizing(
        account_balance, risk_per_trade, entry_price, stop_loss_price, tick_value
    )

    if "error" not in sizing:
        print(f"   Account Balance: ${account_balance:,.2f}")
        print(f"   Risk per Trade: {risk_per_trade:.1%}")
        print(f"   Entry Price: ${entry_price:.2f}")
        print(f"   Stop Loss: ${stop_loss_price:.2f}")
        print(f"   Position Size: {sizing['position_size']} contracts")
        print(
            f"   Actual Risk: ${sizing['actual_dollar_risk']:.2f} ({sizing['actual_risk_percent']:.2%})"
        )


def demonstrate_market_microstructure_analysis(data: pl.DataFrame):
    """Demonstrate market microstructure analysis."""
    print("\n" + "=" * 80)
    print("🔬 MARKET MICROSTRUCTURE ANALYSIS")
    print("=" * 80)

    if data.is_empty():
        print("❌ No data available for microstructure analysis")
        return

    # 1. Volume Profile Analysis
    print("\n1. 📊 Volume Profile Analysis")
    volume_profile = calculate_volume_profile(
        data, price_column="close", volume_column="volume"
    )

    if "error" not in volume_profile:
        print(f"   Point of Control (POC): ${volume_profile['poc_price']:.2f}")
        print(f"   POC Volume: {volume_profile['poc_volume']:,}")
        print(f"   Value Area High: ${volume_profile['value_area_high']:.2f}")
        print(f"   Value Area Low: ${volume_profile['value_area_low']:.2f}")
        print(f"   Total Volume: {volume_profile['total_volume']:,}")
        print(f"   Price Levels: {volume_profile['num_price_levels']}")

    # 2. Simulated Bid-Ask Spread Analysis (since we have OHLC data)
    print("\n2. 📈 Bid-Ask Spread Analysis (Simulated)")
    # Create simulated bid/ask data from OHLC
    spread_data = data.with_columns(
        [
            (pl.col("close") - 0.05).alias("bid"),  # Simulated bid
            (pl.col("close") + 0.05).alias("ask"),  # Simulated ask
        ]
    )

    spread_analysis = analyze_bid_ask_spread(spread_data, "bid", "ask")
    if "error" not in spread_analysis:
        print(f"   Average Spread: ${spread_analysis['avg_spread']:.4f}")
        print(f"   Median Spread: ${spread_analysis['median_spread']:.4f}")
        print(f"   Spread Volatility: ${spread_analysis['spread_volatility']:.4f}")
        print(f"   Relative Spread: {spread_analysis['avg_relative_spread']:.4%}")


def main():
    """Main demonstration function."""
    print("🚀 ProjectX Comprehensive Analysis Demo")
    print("=" * 80)
    print("Demonstrating enhanced API coverage and advanced data analysis tools")

    try:
        # Initialize ProjectX client
        print("\n📡 Initializing ProjectX client...")
        client = ProjectX.from_env()

        # Demonstrate enhanced API coverage
        demonstrate_enhanced_api_coverage(client)

        # Get sample data for analysis
        print("\n📊 Fetching sample data for analysis...")
        try:
            data = client.get_data("MGC", days=30, interval=15)  # 15-minute bars
            if data is None or data.is_empty():
                print("⚠️ No market data available. Using simulated data for demo.")
                # Create sample data for demonstration
                try:
                    import numpy as np  # type: ignore

                    dates = pl.date_range(
                        datetime.now() - timedelta(days=30),
                        datetime.now(),
                        interval="15m",
                        eager=True,
                    )[:1000]  # Limit to reasonable size

                    # Generate realistic OHLCV data
                    base_price = 2050.0
                    price_changes = np.random.normal(0, 2, len(dates))
                    closes = base_price + np.cumsum(price_changes)

                    data = pl.DataFrame(
                        {
                            "timestamp": dates,
                            "open": closes + np.random.normal(0, 0.5, len(dates)),
                            "high": closes + np.abs(np.random.normal(2, 1, len(dates))),
                            "low": closes - np.abs(np.random.normal(2, 1, len(dates))),
                            "close": closes,
                            "volume": np.random.randint(100, 2000, len(dates)),
                        }
                    )
                except ImportError:
                    # Fallback without numpy
                    import random

                    dates = pl.date_range(
                        datetime.now() - timedelta(days=30),
                        datetime.now(),
                        interval="15m",
                        eager=True,
                    )[:100]  # Smaller dataset without numpy

                    base_price = 2050.0
                    closes = []
                    current_price = base_price

                    for _ in range(len(dates)):
                        current_price += random.uniform(-2, 2)
                        closes.append(current_price)

                    data = pl.DataFrame(
                        {
                            "timestamp": dates,
                            "open": [c + random.uniform(-0.5, 0.5) for c in closes],
                            "high": [c + abs(random.uniform(1, 3)) for c in closes],
                            "low": [c - abs(random.uniform(1, 3)) for c in closes],
                            "close": closes,
                            "volume": [random.randint(100, 2000) for _ in closes],
                        }
                    )

        except Exception as e:
            print(f"⚠️ Error fetching data: {e}. Using simulated data.")
            # Create minimal sample data
            data = pl.DataFrame(
                {
                    "timestamp": [datetime.now()],
                    "open": [2050.0],
                    "high": [2055.0],
                    "low": [2045.0],
                    "close": [2052.0],
                    "volume": [1000],
                }
            )

        # Create data snapshot
        snapshot = create_data_snapshot(data, "MGC 15-minute OHLCV data")
        print(
            f"\n📋 Data Snapshot: {snapshot['row_count']} rows, {len(snapshot['columns'])} columns"
        )

        # Run all demonstrations
        data = demonstrate_advanced_technical_indicators(data)
        demonstrate_statistical_analysis(data)
        demonstrate_pattern_recognition(data)
        demonstrate_portfolio_analysis()
        demonstrate_market_microstructure_analysis(data)

        print("\n" + "=" * 80)
        print("✅ COMPREHENSIVE ANALYSIS DEMO COMPLETED")
        print("=" * 80)
        print("\n🎯 Key Takeaways:")
        print("• Enhanced API coverage provides access to all ProjectX endpoints")
        print("• Advanced technical indicators for comprehensive market analysis")
        print("• Statistical tools for risk assessment and performance evaluation")
        print("• Pattern recognition for automated signal detection")
        print("• Portfolio analytics for strategy development and optimization")
        print("• Market microstructure analysis for institutional-grade insights")
        print("\n💡 This demonstrates ProjectX as a professional-grade trading SDK!")

    except Exception as e:
        print(f"❌ Demo failed: {e}")
        print("\n💡 Make sure your ProjectX API credentials are configured:")
        print("   export PROJECT_X_API_KEY='your_api_key'")
        print("   export PROJECT_X_USERNAME='your_username'")


if __name__ == "__main__":
    main()
