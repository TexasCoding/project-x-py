#!/usr/bin/env python3
"""
Developer Utilities Demo for ProjectX SDK

This example demonstrates the enhanced utility functions that make
the ProjectX package more developer-friendly for strategy development.

Author: TexasCoding
Date: June 2025
"""

import os
from datetime import datetime

# Import main classes
# Import utility functions
from project_x_py import (
    ProjectX,
    calculate_bollinger_bands,
    calculate_ema,
    calculate_position_value,
    calculate_risk_reward_ratio,
    calculate_rsi,
    # Technical analysis
    calculate_sma,
    calculate_tick_value,
    convert_timeframe_to_seconds,
    # Data utilities
    create_data_snapshot,
    create_trading_suite,
    extract_symbol_from_contract_id,
    find_support_resistance_levels,
    format_price,
    format_volume,
    get_market_session_info,
    # Market utilities
    is_market_hours,
    round_to_tick_size,
    # Contract and price utilities
    validate_contract_id,
)


def demonstrate_contract_utilities():
    """Demonstrate contract ID and price utilities."""
    print("🔧 Contract & Price Utilities")
    print("=" * 50)

    # Contract validation
    contracts = ["CON.F.US.MGC.M25", "MGC", "invalid.contract", "NQ"]
    for contract in contracts:
        valid = validate_contract_id(contract)
        symbol = extract_symbol_from_contract_id(contract)
        print(f"Contract: {contract:20} Valid: {valid:5} Symbol: {symbol}")

    print()

    # Price calculations
    print("Price Calculations:")
    print(f"MGC 5-tick move value: ${calculate_tick_value(0.5, 0.1, 1.0):.2f}")
    print(
        f"5 MGC contracts at $2050: ${calculate_position_value(5, 2050.0, 1.0, 0.1):,.2f}"
    )
    print(
        f"Price $2050.37 rounded to 0.1 tick: ${round_to_tick_size(2050.37, 0.1):.1f}"
    )

    # Risk/reward calculation
    rr_ratio = calculate_risk_reward_ratio(2050, 2045, 2065)
    print(f"Risk/Reward ratio (2050 entry, 2045 stop, 2065 target): {rr_ratio:.1f}:1")
    print()


def demonstrate_market_utilities():
    """Demonstrate market timing and session utilities."""
    print("⏰ Market Timing Utilities")
    print("=" * 50)

    # Market hours check
    market_open = is_market_hours()
    print(f"Market currently open: {market_open}")

    # Detailed session info
    session_info = get_market_session_info()
    print(
        f"Current time: {session_info['current_time'].strftime('%Y-%m-%d %H:%M:%S %Z')}"
    )
    print(f"Day of week: {session_info['weekday']}")
    print(f"Market open: {session_info['is_open']}")

    if not session_info["is_open"] and "next_session_start" in session_info:
        next_open = session_info["next_session_start"]
        if next_open:
            print(f"Next session opens: {next_open.strftime('%Y-%m-%d %H:%M:%S %Z')}")

    # Timeframe conversions
    timeframes = ["5sec", "1min", "5min", "15min", "1hr", "4hr", "1day"]
    print("\nTimeframe conversions:")
    for tf in timeframes:
        seconds = convert_timeframe_to_seconds(tf)
        print(f"{tf:>6}: {seconds:>6} seconds")
    print()


def demonstrate_data_utilities(client: ProjectX):
    """Demonstrate data analysis and utility functions."""
    print("📊 Data Analysis Utilities")
    print("=" * 50)

    # Get some sample data
    try:
        print("Fetching MGC data...")
        data = client.get_data("MGC", days=30, interval=5)

        if data is not None and not data.is_empty():
            # Create data snapshot
            snapshot = create_data_snapshot(data, "MGC 5-minute OHLCV data")
            print(f"Data snapshot: {snapshot['description']}")
            print(f"  Rows: {format_volume(snapshot['row_count'])}")
            print(f"  Columns: {snapshot['columns']}")
            print(f"  Timespan: {snapshot.get('timespan', 'Unknown')}")

            if "statistics" in snapshot:
                print("  Basic statistics:")
                for col, stats in snapshot["statistics"].items():
                    if col == "close":
                        print(
                            f"    {col}: {format_price(stats['min'])} - {format_price(stats['max'])} (avg: {format_price(stats['mean'])})"
                        )
                    elif col == "volume":
                        print(
                            f"    {col}: {format_volume(int(stats['min']))} - {format_volume(int(stats['max']))} (avg: {format_volume(int(stats['mean']))})"
                        )

            print()

            # Demonstrate technical analysis functions
            print("Technical Analysis Functions:")

            # Add moving averages
            data_with_sma = calculate_sma(data, period=20)
            data_with_ema = calculate_ema(data_with_sma, period=20)

            print(f"  Added SMA(20) and EMA(20) columns")
            print(f"  Columns now: {data_with_ema.columns}")

            # Add RSI
            data_with_rsi = calculate_rsi(data_with_ema, period=14)
            print(f"  Added RSI(14) column")

            # Add Bollinger Bands
            data_with_bb = calculate_bollinger_bands(
                data_with_rsi, period=20, std_dev=2.0
            )
            print(f"  Added Bollinger Bands (20, 2.0)")
            print(f"  Final columns: {len(data_with_bb.columns)} columns")

            # Find support/resistance levels
            levels = find_support_resistance_levels(
                data, min_touches=3, tolerance_pct=0.1
            )
            print(f"  Found {len(levels)} potential support/resistance levels")

            if levels:
                print("  Top 3 levels by strength:")
                for i, level in enumerate(levels[:3]):
                    print(
                        f"    {i + 1}. ${level['price']:.2f} - {level['touches']} touches, strength: {level['strength']:.2f}"
                    )

            # Show latest values with technical indicators
            if len(data_with_bb) > 0:
                latest = data_with_bb.tail(1)
                print(f"\nLatest bar analysis:")
                latest_data = latest.to_dicts()[0]
                print(f"  Price: {format_price(latest_data['close'])}")
                print(f"  SMA(20): {format_price(latest_data.get('sma_20', 0))}")
                print(f"  EMA(20): {format_price(latest_data.get('ema_20', 0))}")
                print(f"  RSI(14): {latest_data.get('rsi_14', 0):.1f}")
                print(f"  BB Upper: {format_price(latest_data.get('bb_upper', 0))}")
                print(f"  BB Lower: {format_price(latest_data.get('bb_lower', 0))}")

        else:
            print("❌ No data available for analysis")

    except Exception as e:
        print(f"❌ Error in data analysis: {e}")

    print()


def demonstrate_strategy_workflow():
    """Show a typical workflow for strategy developers."""
    print("🎯 Strategy Development Workflow")
    print("=" * 50)

    print("1. Environment Setup")
    print("   Set PROJECT_X_API_KEY and PROJECT_X_USERNAME environment variables")

    print("\n2. Basic Client Setup")
    print("   client = ProjectX.from_env()")
    print("   account = client.get_account_info()")

    print("\n3. Data Analysis")
    print("   data = client.get_data('MGC', days=30)")
    print("   data_with_indicators = calculate_sma(calculate_ema(data))")
    print("   levels = find_support_resistance_levels(data)")

    print("\n4. Order Management")
    print("   from project_x_py import create_order_manager")
    print("   order_manager = create_order_manager(client)")
    print("   response = order_manager.place_bracket_order(...)")

    print("\n5. Position Monitoring")
    print("   from project_x_py import create_position_manager")
    print("   position_manager = create_position_manager(client)")
    print("   positions = position_manager.get_all_positions()")

    print("\n6. Real-time Integration")
    print(
        "   trading_suite = create_trading_suite('MGC', client, jwt_token, account_id)"
    )
    print("   real_time_data = trading_suite['data_manager'].get_data('5min')")

    print()


def main():
    """Demonstrate ProjectX SDK utilities for strategy developers."""
    print("🚀 ProjectX SDK - Developer Utilities Demo")
    print("=" * 60)
    print()

    # Demonstrate utilities that don't need API connection
    demonstrate_contract_utilities()
    demonstrate_market_utilities()
    demonstrate_strategy_workflow()

    # Try to connect and demonstrate data utilities
    try:
        if not os.getenv("PROJECT_X_API_KEY") or not os.getenv("PROJECT_X_USERNAME"):
            print(
                "⚠️  API credentials not found. Set environment variables to test data utilities:"
            )
            print("   export PROJECT_X_API_KEY='your_api_key'")
            print("   export PROJECT_X_USERNAME='your_username'")
            print()
            return

        print("🔑 Creating ProjectX client...")
        client = ProjectX.from_env()

        # Test authentication
        account = client.get_account_info()
        if account:
            print(f"✅ Connected to account: {account.name}")
            print(f"   Balance: ${account.balance:,.2f}")
            print()

            # Demonstrate data utilities
            demonstrate_data_utilities(client)
        else:
            print("❌ Could not retrieve account information")

    except Exception as e:
        print(f"❌ Error connecting to ProjectX: {e}")
        print("   Make sure your API credentials are correct")

    print(
        "✅ Demo completed! These utilities make ProjectX SDK more developer-friendly."
    )
    print("\nNext steps:")
    print("  1. Use these utilities in your own strategy development")
    print("  2. Combine with real-time data for live trading")
    print("  3. Build comprehensive risk management systems")
    print("  4. Create automated trading strategies")


if __name__ == "__main__":
    main()
