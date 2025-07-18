#!/usr/bin/env python3
"""
Order and Position Management Demo with Real Orders

This script demonstrates comprehensive order and position management using the
ProjectX OrderManager and PositionManager by placing REAL ORDERS on the market.

⚠️  WARNING: THIS SCRIPT PLACES REAL ORDERS! ⚠️
- Only run in a simulated/demo account
- Use small position sizes for testing
- Monitor positions closely
- Cancel orders promptly if needed

Features Demonstrated:
1. Account and position status monitoring
2. Order placement (market, limit, stop, bracket orders)
3. Real-time order status tracking
4. Position monitoring and risk management
5. Portfolio P&L calculation
6. Order and position cleanup

Requirements:
- Set PROJECT_X_API_KEY environment variable
- Set PROJECT_X_USERNAME environment variable
- Use simulated account for testing

Author: TexasCoding
Date: June 2025
"""

import os
import time
from datetime import datetime
from typing import Any, Dict

from project_x_py import (
    ProjectX,
    create_order_manager,
    create_position_manager,
    create_realtime_client,
    setup_logging,
)


class OrderPositionDemoManager:
    """
    Demo manager for testing order and position management functionality.

    This class encapsulates the demo logic and provides safety features
    for testing with real orders.
    """

    def __init__(self, test_symbol: str = "MGC", test_size: int = 1):
        """
        Initialize the demo manager.

        Args:
            test_symbol: Symbol to use for testing (default: MGC - Micro Gold)
            test_size: Position size for testing (default: 1 contract)
        """
        self.test_symbol = test_symbol
        self.test_size = test_size
        self.logger = setup_logging(level="INFO")

        # Initialize components
        self.client: ProjectX | None = None
        self.order_manager = None
        self.position_manager = None
        self.realtime_client = None

        # Contract information
        self.contract_id: str | None = None  # Full contract ID for orders
        self.instrument = None

        # Track demo orders and positions for cleanup
        self.demo_orders: list[int] = []
        self.demo_positions: list[str] = []

        # Safety settings
        self.max_risk_per_trade = 50.0  # Maximum $ risk per trade
        self.max_total_risk = 200.0  # Maximum total $ risk

    def validate_environment(self) -> bool:
        """Validate environment setup and safety requirements."""
        try:
            # Initialize client
            self.client = ProjectX(
                username="username",
                api_key="api_key",
                account_name="account_name",
            )
            account = self.client.get_account_info()

            if not account:
                self.logger.error("❌ Could not retrieve account information")
                return False

            # Verify simulated account (safety check)
            if not account.simulated:
                print("⚠️  WARNING: This appears to be a LIVE account!")
                print("This demo places REAL ORDERS with REAL MONEY!")
                response = input(
                    "Are you sure you want to continue? (type 'YES' to proceed): "
                )
                if response != "YES":
                    self.logger.info("Demo cancelled for safety")
                    return False

            # Display account info
            print(f"\n📊 Account Information:")
            print(f"   Name: {account.name}")
            print(f"   Balance: ${account.balance:,.2f}")
            print(f"   Simulated: {account.simulated}")
            print(f"   Trading Enabled: {account.canTrade}")

            if not account.canTrade:
                self.logger.error("❌ Trading is not enabled on this account")
                return False

            return True

        except Exception as e:
            self.logger.error(f"❌ Environment validation failed: {e}")
            return False

    def initialize_managers(self) -> bool:
        """Initialize order and position managers."""
        try:
            if not self.client:
                return False

            # Get account info for realtime client
            account = self.client.get_account_info()
            if not account:
                return False

            # Get the proper contract ID for the instrument
            print(f"\n🔍 Looking up contract information for {self.test_symbol}...")
            self.instrument = self.client.get_instrument(self.test_symbol)
            if not self.instrument:
                self.logger.error(f"❌ Could not find instrument: {self.test_symbol}")
                return False

            self.contract_id = self.instrument.id
            print(f"✅ Found contract: {self.instrument.name}")
            print(f"   Contract ID: {self.contract_id}")
            print(f"   Description: {self.instrument.description}")
            print(f"   Tick Size: ${self.instrument.tickSize}")

            # Create realtime client (optional but recommended)
            try:
                self.realtime_client = create_realtime_client(
                    jwt_token=self.client.session_token, account_id=str(account.id)
                )
                self.logger.info("✅ Real-time client created")
            except Exception as e:
                self.logger.warning(
                    f"⚠️ Real-time client failed (continuing without): {e}"
                )
                self.realtime_client = None

            # Create order manager
            self.order_manager = create_order_manager(
                project_x=self.client, realtime_client=self.realtime_client
            )

            # Create position manager
            self.position_manager = create_position_manager(
                project_x=self.client, realtime_client=self.realtime_client
            )

            self.logger.info("✅ Order and Position managers initialized")
            return True

        except Exception as e:
            self.logger.error(f"❌ Manager initialization failed: {e}")
            return False

    def show_current_status(self):
        """Display current account, positions, and orders status."""
        print(f"\n{'=' * 60}")
        print("📈 CURRENT STATUS")
        print(f"{'=' * 60}")

        try:
            if not self.position_manager or not self.order_manager:
                print("❌ Managers not initialized")
                return

            # Show positions
            positions = self.position_manager.get_all_positions()
            print(f"\n📊 Current Positions ({len(positions)}):")
            if positions:
                for pos in positions:
                    direction = "LONG" if pos.type == 1 else "SHORT"
                    print(
                        f"   {pos.contractId}: {direction} {pos.size} @ ${pos.averagePrice:.2f}"
                    )
            else:
                print("   No open positions")

            # Show open orders
            orders = self.order_manager.search_open_orders()
            print(f"\n📋 Open Orders ({len(orders)}):")
            if orders:
                for order in orders:
                    side = "BUY" if order.side == 0 else "SELL"
                    print(
                        f"   Order #{order.id}: {side} {order.size} {order.contractId} @ ${order.limitPrice or order.stopPrice or 'Market'}"
                    )
            else:
                print("   No open orders")

            # Show portfolio metrics
            try:
                portfolio_data = self.position_manager.get_portfolio_pnl()
                print(f"\n💰 Portfolio Metrics:")
                print(f"   Total Positions: {portfolio_data['position_count']}")
            except Exception as e:
                self.logger.error(f"❌ Portfolio P&L calculation failed: {e}")
                print(f"\n💰 Portfolio Metrics: Error - {e}")

            try:
                risk_metrics = self.position_manager.get_risk_metrics()
                print(f"   Total Exposure: ${risk_metrics['total_exposure']:.2f}")
                print(
                    f"   Largest Position Risk: {risk_metrics['largest_position_risk']:.2%}"
                )
                print(
                    f"   Diversification Score: {risk_metrics['diversification_score']:.2f}"
                )

                # Safely check for risk warnings
                risk_warnings = risk_metrics.get("risk_warnings", [])
                if risk_warnings:
                    print(f"\n⚠️ Risk Warnings:")
                    for warning in risk_warnings:
                        print(f"   • {warning}")
                else:
                    print(f"\n✅ No risk warnings detected")

            except Exception as e:
                self.logger.error(f"❌ Risk metrics calculation failed: {e}")
                print(f"   Risk Metrics: Error - {e}")

        except Exception as e:
            self.logger.error(f"❌ Status display failed: {e}")

    def test_basic_orders(self) -> bool:
        """Test basic order placement and management."""
        print(f"\n{'=' * 60}")
        print("🎯 TESTING BASIC ORDERS")
        print(f"{'=' * 60}")

        try:
            if not self.client or not self.order_manager or not self.contract_id:
                self.logger.error(
                    "❌ Client, order manager, or contract ID not initialized"
                )
                return False

            # Get current market data for price reference
            market_data = self.client.get_data(self.test_symbol, days=1, interval=1)

            if market_data is None:
                self.logger.error(f"❌ No market data available for {self.test_symbol}")
                return False

            if market_data.is_empty():
                self.logger.error(f"❌ No market data available for {self.test_symbol}")
                return False

            current_price = float(market_data.select("close").tail(1).item())
            print(f"\n📈 Current {self.test_symbol} price: ${current_price:.2f}")

            # Test 1: Place a limit order below market (less likely to fill immediately)
            limit_price = current_price - 10.0  # $10 below market
            print(f"\n🎯 Test 1: Placing limit BUY order")
            print(f"   Contract ID: {self.contract_id}")
            print(f"   Price: ${limit_price:.2f}")
            print(f"   Size: {self.test_size} contracts")

            try:
                limit_response = self.order_manager.place_limit_order(
                    contract_id=self.contract_id,
                    side=0,  # Buy
                    size=self.test_size,
                    limit_price=limit_price,
                )

                if limit_response.success:
                    print(
                        f"✅ Limit order placed successfully! Order ID: {limit_response.orderId}"
                    )
                    self.demo_orders.append(limit_response.orderId)

                    # Wait a moment and check order status
                    time.sleep(2)
                    order_info = self.order_manager.get_order_by_id(
                        limit_response.orderId
                    )
                    if order_info:
                        print(f"   Order Status: {order_info.status}")
                else:
                    print(f"❌ Limit order failed: {limit_response}")
                    return False

            except Exception as e:
                self.logger.error(f"❌ Limit order placement exception: {e}")
                return False

            # Test 2: Place a stop order above market
            stop_price = current_price + 20.0  # $20 above market
            print(f"\n🎯 Test 2: Placing stop BUY order")
            print(f"   Contract ID: {self.contract_id}")
            print(f"   Stop Price: ${stop_price:.2f}")

            try:
                stop_response = self.order_manager.place_stop_order(
                    contract_id=self.contract_id,
                    side=0,  # Buy
                    size=self.test_size,
                    stop_price=stop_price,
                )

                if stop_response.success:
                    print(
                        f"✅ Stop order placed successfully! Order ID: {stop_response.orderId}"
                    )
                    self.demo_orders.append(stop_response.orderId)
                else:
                    print(f"❌ Stop order failed: {stop_response}")

            except Exception as e:
                self.logger.error(f"❌ Stop order placement exception: {e}")

            # Test 3: Show order management
            print(f"\n📋 Current open orders:")
            open_orders = self.order_manager.search_open_orders(
                contract_id=self.contract_id
            )
            for order in open_orders:
                side = "BUY" if order.side == 0 else "SELL"
                price = order.limitPrice or order.stopPrice or "Market"
                print(f"   Order #{order.id}: {side} {order.size} @ ${price}")

            return True

        except Exception as e:
            self.logger.error(f"❌ Basic order test failed: {e}")
            return False

    def test_bracket_order(self) -> bool:
        """Test bracket order functionality."""
        print(f"\n{'=' * 60}")
        print("🎯 TESTING BRACKET ORDERS")
        print(f"{'=' * 60}")

        try:
            if not self.client or not self.order_manager or not self.contract_id:
                self.logger.error(
                    "❌ Client, order manager, or contract ID not initialized"
                )
                return False

            # Get current market data
            market_data = self.client.get_data(self.test_symbol, days=1, interval=1)
            if market_data is None:
                self.logger.error(f"❌ No market data available for {self.test_symbol}")
                return False

            if market_data.is_empty():
                return False

            current_price = float(market_data.select("close").tail(1).item())

            # Define bracket parameters (small risk)
            entry_price = current_price - 5.0  # Entry below market
            stop_price = entry_price - 5.0  # $5 risk
            target_price = entry_price + 10.0  # $10 profit target (2:1 R/R)

            print(f"\n🎯 Placing bracket order:")
            print(f"   Contract ID: {self.contract_id}")
            print(f"   Entry: ${entry_price:.2f}")
            print(f"   Stop: ${stop_price:.2f}")
            print(f"   Target: ${target_price:.2f}")
            print(f"   Risk: ${abs(entry_price - stop_price):.2f} per contract")

            bracket_response = self.order_manager.place_bracket_order(
                contract_id=self.contract_id,
                side=0,  # Buy
                size=self.test_size,
                entry_price=entry_price,
                stop_loss_price=stop_price,
                take_profit_price=target_price,
                entry_type="market",
            )

            if bracket_response.success:
                print(f"✅ Bracket order placed successfully!")
                print(f"   Entry Order ID: {bracket_response.entry_order_id}")
                print(f"   Stop Order ID: {bracket_response.stop_order_id}")
                print(f"   Target Order ID: {bracket_response.target_order_id}")

                # Track all bracket orders for cleanup
                if bracket_response.entry_order_id:
                    self.demo_orders.append(bracket_response.entry_order_id)
                if bracket_response.stop_order_id:
                    self.demo_orders.append(bracket_response.stop_order_id)
                if bracket_response.target_order_id:
                    self.demo_orders.append(bracket_response.target_order_id)

                return True
            else:
                print(f"❌ Bracket order failed: {bracket_response.error_message}")
                return False

        except Exception as e:
            self.logger.error(f"❌ Bracket order test failed: {e}")
            return False

    def test_position_management(self):
        """Test position management features."""
        print(f"\n{'=' * 60}")
        print("📊 TESTING POSITION MANAGEMENT")
        print(f"{'=' * 60}")

        try:
            if not self.position_manager or not self.client or not self.contract_id:
                self.logger.error(
                    "❌ Position manager, client, or contract ID not initialized"
                )
                return

            # Show current positions
            positions = self.position_manager.get_all_positions()
            print(f"\n📊 Current Positions: {len(positions)}")

            # If we have positions, demonstrate position management
            if positions:
                for pos in positions:
                    direction = "LONG" if pos.type == 1 else "SHORT"
                    print(
                        f"   {pos.contractId}: {direction} {pos.size} @ ${pos.averagePrice:.2f}"
                    )

                    # Track position for monitoring
                    if pos.contractId not in self.demo_positions:
                        self.demo_positions.append(pos.contractId)

            # Test position monitoring setup
            print(f"\n⚠️ Setting up position alerts...")
            self.position_manager.add_position_alert(
                contract_id=self.contract_id,
                max_loss=-self.max_risk_per_trade,  # Alert if loss exceeds max risk
                max_gain=self.max_risk_per_trade * 2,  # Alert if profit exceeds 2x risk
            )
            print(f"   Alert added for {self.contract_id}")

            # Test position sizing calculation
            market_data = self.client.get_data(self.test_symbol, days=1, interval=1)
            if market_data is None:
                self.logger.error(f"❌ No market data available for {self.test_symbol}")
                return False

            if market_data.is_empty():
                self.logger.error(f"❌ No market data available for {self.test_symbol}")
                return False

            if not market_data.is_empty():
                current_price = float(market_data.select("close").tail(1).item())

                # Use the base symbol for position sizing, not the full contract ID
                sizing = self.position_manager.calculate_position_size(
                    contract_id=self.test_symbol,  # Use base symbol (MGC) not full contract ID
                    risk_amount=self.max_risk_per_trade,
                    entry_price=current_price,
                    stop_price=current_price - 5.0,
                )

                print(f"\n📐 Position Sizing Analysis:")
                print(f"   Risk Amount: ${self.max_risk_per_trade:.2f}")

                # Check if sizing calculation was successful
                if "error" in sizing:
                    print(f"   ❌ Position sizing error: {sizing['error']}")
                else:
                    print(f"   Suggested Size: {sizing['suggested_size']} contracts")
                    print(f"   Risk per Contract: ${sizing['risk_per_contract']:.2f}")
                    print(f"   Risk Percentage: {sizing['risk_percentage']:.2f}%")

            # Show portfolio metrics
            try:
                portfolio_data = self.position_manager.get_portfolio_pnl()
                print(f"\n💰 Portfolio Metrics:")
                print(f"   Total Positions: {portfolio_data['position_count']}")
            except Exception as e:
                self.logger.error(f"❌ Portfolio P&L calculation failed: {e}")
                print(f"\n💰 Portfolio Metrics: Error - {e}")

            try:
                risk_metrics = self.position_manager.get_risk_metrics()
                print(f"   Total Exposure: ${risk_metrics['total_exposure']:.2f}")
                print(
                    f"   Largest Position Risk: {risk_metrics['largest_position_risk']:.2%}"
                )
                print(
                    f"   Diversification Score: {risk_metrics['diversification_score']:.2f}"
                )

                # Safely check for risk warnings
                risk_warnings = risk_metrics.get("risk_warnings", [])
                if risk_warnings:
                    print(f"\n⚠️ Risk Warnings:")
                    for warning in risk_warnings:
                        print(f"   • {warning}")
                else:
                    print(f"\n✅ No risk warnings detected")

            except Exception as e:
                self.logger.error(f"❌ Risk metrics calculation failed: {e}")
                print(f"   Risk Metrics: Error - {e}")

        except Exception as e:
            self.logger.error(f"❌ Position management test failed: {e}")
            print(f"\n❌ Position management test encountered an error: {e}")
            # Continue with the demo instead of stopping

    def monitor_orders_and_positions(self, duration_seconds: int = 30):
        """Monitor orders and positions for a specified duration."""
        print(f"\n{'=' * 60}")
        print(f"👀 MONITORING ORDERS & POSITIONS ({duration_seconds}s)")
        print(f"{'=' * 60}")

        if not self.order_manager or not self.position_manager or not self.contract_id:
            self.logger.error("❌ Managers or contract ID not initialized")
            return

        start_time = time.time()

        try:
            while time.time() - start_time < duration_seconds:
                # Check order status
                open_orders = self.order_manager.search_open_orders(
                    contract_id=self.contract_id
                )
                filled_orders = []

                for order_id in self.demo_orders[
                    :
                ]:  # Copy list to avoid modification during iteration
                    if self.order_manager.is_order_filled(order_id):
                        filled_orders.append(order_id)
                        self.demo_orders.remove(order_id)

                if filled_orders:
                    print(f"\n✅ Orders filled: {filled_orders}")

                    # Refresh positions after fills
                    positions = self.position_manager.get_all_positions()
                    print(f"📊 Updated positions: {len(positions)}")
                    for pos in positions:
                        direction = "LONG" if pos.type == 1 else "SHORT"
                        print(
                            f"   {pos.contractId}: {direction} {pos.size} @ ${pos.averagePrice:.2f}"
                        )

                # Show monitoring status
                remaining_time = duration_seconds - (time.time() - start_time)
                print(
                    f"\r⏱️ Monitoring... {remaining_time:.0f}s remaining",
                    end="",
                    flush=True,
                )
                time.sleep(2)

        except KeyboardInterrupt:
            print(f"\n⏹️ Monitoring stopped by user")
        except Exception as e:
            self.logger.error(f"❌ Monitoring failed: {e}")

        print(f"\n✅ Monitoring complete")

    def show_final_statistics(self):
        """Display final statistics and summary."""
        print(f"\n{'=' * 60}")
        print("📊 FINAL STATISTICS")
        print(f"{'=' * 60}")

        try:
            if not self.order_manager or not self.position_manager:
                print("❌ Managers not initialized")
                return

            # Order statistics
            order_stats = self.order_manager.get_order_statistics()
            print(f"\n📋 Order Statistics:")
            print(f"   Orders Placed: {order_stats['statistics']['orders_placed']}")
            print(
                f"   Orders Cancelled: {order_stats['statistics']['orders_cancelled']}"
            )
            print(f"   Orders Modified: {order_stats['statistics']['orders_modified']}")
            print(
                f"   Bracket Orders: {order_stats['statistics']['bracket_orders_placed']}"
            )

            # Position statistics
            position_stats = self.position_manager.get_position_statistics()
            print(f"\n📊 Position Statistics:")
            print(
                f"   Positions Tracked: {position_stats['statistics']['positions_tracked']}"
            )
            print(
                f"   Positions Closed: {position_stats['statistics']['positions_closed']}"
            )
            print(f"   Monitoring Active: {position_stats['monitoring_active']}")

            # Final status
            print(f"\n📈 Final Status:")
            positions = self.position_manager.get_all_positions()
            orders = self.order_manager.search_open_orders()
            print(f"   Open Positions: {len(positions)}")
            print(f"   Open Orders: {len(orders)}")

        except Exception as e:
            self.logger.error(f"❌ Statistics display failed: {e}")

    def cleanup_demo_orders(self):
        """Cancel any remaining demo orders for cleanup."""
        print(f"\n{'=' * 60}")
        print("🧹 CLEANUP - CANCELLING DEMO ORDERS")
        print(f"{'=' * 60}")

        if not self.demo_orders:
            print("✅ No demo orders to cancel")
            return

        if not self.order_manager:
            print("❌ Order manager not initialized")
            return

        print(f"\n🧹 Cancelling {len(self.demo_orders)} demo orders...")

        cancelled_count = 0
        failed_count = 0

        for order_id in self.demo_orders:
            try:
                if self.order_manager.cancel_order(order_id):
                    print(f"✅ Cancelled order #{order_id}")
                    cancelled_count += 1
                else:
                    print(f"❌ Failed to cancel order #{order_id}")
                    failed_count += 1
            except Exception as e:
                print(f"❌ Error cancelling order #{order_id}: {e}")
                failed_count += 1

        print(f"\n📊 Cleanup Summary:")
        print(f"   Cancelled: {cancelled_count}")
        print(f"   Failed: {failed_count}")

        # Clear the demo orders list
        self.demo_orders.clear()

    def run_demo(self):
        """Run the complete order and position management demo."""
        print(f"\n{'=' * 80}")
        print("🚀 ORDER & POSITION MANAGEMENT DEMO")
        print(f"{'=' * 80}")
        print("⚠️  This demo places REAL ORDERS on the market!")
        print("   Please ensure you're using a simulated/demo account")
        print("   and monitor your positions closely.")
        print(f"{'=' * 80}")

        try:
            # Step 1: Validate environment and setup
            if not self.validate_environment():
                return False

            # Step 2: Initialize managers
            if not self.initialize_managers():
                return False

            # Step 3: Show initial status
            self.show_current_status()

            # Step 4: Test basic orders
            if not self.test_basic_orders():
                print("❌ Basic order tests failed, stopping demo")
                self.cleanup_demo_orders()
                return False

            # Step 5: Test bracket orders
            self.test_bracket_order()

            # Step 6: Test position management
            self.test_position_management()

            # Step 7: Monitor for a short time
            self.monitor_orders_and_positions(30)

            # Step 8: Show final statistics
            self.show_final_statistics()

            # Step 9: Cleanup demo orders
            self.cleanup_demo_orders()

            print(f"\n✅ Demo completed successfully!")
            print(f"📊 Review your positions and orders in your trading platform")
            print(f"⚠️  Remember to close any open positions if desired")

            return True

        except KeyboardInterrupt:
            print(f"\n⏹️ Demo interrupted by user")
            self.cleanup_demo_orders()
            return False
        except Exception as e:
            self.logger.error(f"❌ Demo failed: {e}")
            self.cleanup_demo_orders()
            return False
        finally:
            # Cleanup managers
            if self.order_manager:
                self.order_manager.cleanup()
            if self.position_manager:
                self.position_manager.cleanup()


def main():
    """Main demo function."""
    # Configuration
    TEST_SYMBOL = "MGC"  # Micro Gold futures (smaller size for testing)
    TEST_SIZE = 1  # 1 contract for testing

    # Safety warning
    print("⚠️  WARNING: This script places REAL ORDERS!")
    print("   Only run this on a simulated/demo account")
    print("   Use small position sizes for testing")
    response = input("\nContinue with demo? (y/N): ")

    if response.lower() != "y":
        print("Demo cancelled for safety")
        return

    # Create and run demo
    demo = OrderPositionDemoManager(test_symbol=TEST_SYMBOL, test_size=TEST_SIZE)

    success = demo.run_demo()

    if success:
        print(f"\n🎉 Demo completed successfully!")
    else:
        print(f"\n❌ Demo encountered errors - check logs for details")


if __name__ == "__main__":
    main()
