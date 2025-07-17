#!/usr/bin/env python3
"""
Basic Usage Example for ProjectX Python Client

This script demonstrates the basic functionality of the ProjectX client
including authentication, market data retrieval, and position monitoring.

Requirements:
- Set PROJECT_X_API_KEY environment variable
- Set PROJECT_X_USERNAME environment variable
"""

import os

from project_x_py import ProjectX, setup_logging


def main():
    """Main example function."""
    # Set up logging
    logger = setup_logging(level="INFO")
    logger.info("Starting ProjectX basic usage example")

    # Check environment variables
    api_key = os.getenv('PROJECT_X_API_KEY')
    username = os.getenv('PROJECT_X_USERNAME')

    if not api_key or not username:
        print("❌ Error: Please set PROJECT_X_API_KEY and PROJECT_X_USERNAME environment variables")
        print("Example:")
        print("  export PROJECT_X_API_KEY='your_api_key'")
        print("  export PROJECT_X_USERNAME='your_username'")
        return

    try:
        # Create client using environment variables
        print("🔑 Creating ProjectX client...")
        client = ProjectX.from_env()

        # Get account information
        print("📊 Getting account information...")
        account = client.get_account_info()
        if account:
            print(f"✅ Account: {account.name}")
            print(f"💰 Balance: ${account.balance:,.2f}")
            print(f"🔄 Trading Enabled: {account.canTrade}")
            print(f"📈 Simulated: {account.simulated}")
        else:
            print("❌ No account information available")
            return

        # Search for instruments
        print("\n🔍 Searching for MGC instruments...")
        instruments = client.search_instruments("MGC")
        print(f"✅ Found {len(instruments)} MGC instruments")

        if instruments:
            for i, inst in enumerate(instruments[:3]):  # Show first 3
                print(f"  {i+1}. {inst.name}: {inst.description}")
                print(f"     Tick Size: ${inst.tickSize}, Tick Value: ${inst.tickValue}")

        # Get historical data
        print("\n📈 Getting historical data for MGC...")
        data = client.get_data("MGC", days=5, interval=15)
        if data is not None:
            print(f"✅ Retrieved {len(data)} bars of 15-minute data")

            # Show recent data
            recent_data = data.tail(5)
            print("\nRecent 15-minute bars:")
            for row in recent_data.iter_rows(named=True):
                timestamp = row['timestamp']
                close = row['close']
                volume = row['volume']
                print(f"  {timestamp}: Close=${close:.2f}, Volume={volume}")
        else:
            print("❌ No historical data available")

        # Check current positions
        print("\n💼 Checking open positions...")
        positions = client.search_open_positions()
        if positions:
            print(f"✅ Found {len(positions)} open positions:")
            for pos in positions:
                direction = "LONG" if pos.type == 1 else "SHORT"
                print(f"  {direction} {pos.size} {pos.contractId} @ ${pos.averagePrice:.2f}")
        else:
            print("📝 No open positions")

        # Demo order placement (commented out for safety)
        print("\n📝 Order placement example (commented out for safety):")
        print("  # Place a limit order")
        print("  # response = client.place_limit_order(")
        print("  #     contract_id='CON.F.US.MGC.M25',")
        print("  #     side=1,  # Sell")
        print("  #     size=1,")
        print("  #     limit_price=2100.0")
        print("  # )")
        print("  # if response.success:")
        print("  #     print(f'Order placed: {response.orderId}')")

        print("\n✅ Basic usage example completed successfully!")

    except Exception as e:
        print(f"❌ Error: {e}")
        logger.error(f"Example failed: {e}")


if __name__ == "__main__":
    main()
