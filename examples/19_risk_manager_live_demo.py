#!/usr/bin/env python3
"""
Live Risk Manager Demo - Complete Feature Demonstration

This example demonstrates ALL risk manager features with real positions:
- Position sizing based on risk parameters
- Risk validation and trade blocking
- Stop-loss and take-profit management
- Portfolio risk monitoring
- Managed trades with automatic cleanup
- Risk analytics and metrics

WARNING: This script will open REAL positions. Use with care!
"""

import asyncio
import logging
from decimal import Decimal
from typing import Any, cast

from project_x_py import EventType, TradingSuite
from project_x_py.models import BracketOrderResponse, Order, Position
from project_x_py.risk_manager import ManagedTrade, RiskConfig
from project_x_py.types import OrderSide

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class RiskManagerDemo:
    """Comprehensive demonstration of risk management features."""

    def __init__(self) -> None:
        """Initialize demo."""
        self.suite: TradingSuite | None = None
        self.positions_opened: list[Any] = []
        self.orders_placed: list[Any] = []
        self.demo_trades_enabled = True  # Set to False to skip actual trades

    async def setup(self) -> None:
        """Set up trading suite with risk management."""
        print("\n" + "=" * 60)
        print("RISK MANAGER LIVE DEMO")
        print("=" * 60)
        print("\n🔧 Setting up trading suite with risk management...")

        # Create suite with risk manager enabled
        self.suite = await TradingSuite.create(
            "MNQ",
            timeframes=["1min", "5min", "15min"],
            features=["risk_manager", "orderbook"],
            initial_days=5,
        )

        if not self.suite:
            raise RuntimeError("Failed to create trading suite")

        # Configure risk parameters
        if self.suite.risk_manager:
            self.suite.risk_manager.config = RiskConfig(
                max_position_size=5,  # Max 5 contracts per position
                max_positions=3,  # Max 3 concurrent positions
                max_risk_per_trade=Decimal(0.02),  # 2% per trade
                max_daily_loss=Decimal(0.05),  # 5% daily loss limit
                max_correlated_positions=3,  # Max 3 correlated positions
                use_kelly_criterion=True,  # Use Kelly for sizing
                use_trailing_stops=True,  # Auto-adjust stops
                trailing_stop_trigger=Decimal(50.0),  # Activate after $50 profit
                trailing_stop_distance=Decimal(25.0),  # Trail by $25
            )
            print("✅ Risk management configured")

        if self.suite.client.account_info:
            print(
                f"✅ Suite created for account: {self.suite.client.account_info.name}"
            )
        else:
            print("✅ Suite created")

        instrument = await self.suite.client.get_instrument("MNQ")
        print(f"✅ Instrument: {instrument.name}")

        # Register event handlers
        await self._register_event_handlers()

    async def _register_event_handlers(self) -> None:
        """Register handlers for risk events."""
        if not self.suite:
            return

        async def on_position_opened(event: Any) -> None:
            """Handle position opened."""
            pos = event.data.get("position") if hasattr(event, "data") else event
            if pos:
                logger.info(f"📊 Position Opened: {pos}")

        async def on_position_closed(event: Any) -> None:
            """Handle position closed."""
            pos = event.data.get("position") if hasattr(event, "data") else event
            if pos:
                logger.info(f"📊 Position Closed: {pos}")

        await self.suite.on(EventType.POSITION_OPENED, on_position_opened)
        await self.suite.on(EventType.POSITION_CLOSED, on_position_closed)

    async def demo_position_sizing(self) -> None:
        """Demonstrate position sizing calculations."""
        print("\n" + "-" * 60)
        print("1. POSITION SIZING DEMONSTRATION")
        print("-" * 60)

        if not self.suite:
            print("❌ Trading suite not initialized")
            return

        # Get current price
        current_price = await self.suite.data.get_current_price()
        if not current_price:
            print("❌ Could not get current price")
            return

        print(f"\n📈 Current MNQ Price: ${current_price:,.2f}")

        # Calculate different position sizes
        scenarios = [
            {"stop_loss": current_price - 50, "risk_percent": 0.01},  # 1% risk
            {"stop_loss": current_price - 100, "risk_percent": 0.02},  # 2% risk
            {
                "stop_loss": current_price - 25,
                "risk_amount": 100,
            },  # $100 fixed risk (4 contracts)
        ]

        for i, scenario in enumerate(scenarios, 1):
            if not self.suite.risk_manager:
                print("❌ Risk manager not enabled")
                return

            result = await self.suite.risk_manager.calculate_position_size(
                entry_price=current_price,
                stop_loss=scenario["stop_loss"],
                risk_percent=scenario.get("risk_percent"),
                risk_amount=scenario.get("risk_amount"),
                instrument=await self.suite.client.get_instrument("MNQ"),
            )

            print(f"\n📊 Scenario {i}:")
            print(f"   Stop Distance: ${current_price - scenario['stop_loss']:.2f}")
            if "risk_percent" in scenario:
                print(f"   Risk: {scenario['risk_percent'] * 100:.1f}% of account")
            else:
                print(f"   Risk: ${scenario['risk_amount']:.2f} fixed")
            print(f"   Calculated Size: {result.get('position_size', 0)} contracts")
            print(f"   Total Risk: ${result.get('risk_amount', 0):.2f}")
            print(f"   Risk/Reward @ 2:1: ${result.get('risk_amount', 0) * 2:.2f}")
            if (
                result.get("position_size", 0)
                == self.suite.risk_manager.config.max_position_size
            ):
                ideal_size = (
                    scenario.get("risk_amount", 0)
                    / (current_price - scenario["stop_loss"])
                    if "risk_amount" in scenario
                    else None
                )
                if (
                    ideal_size
                    and ideal_size > self.suite.risk_manager.config.max_position_size
                ):
                    print(
                        f"   (Limited by max size {self.suite.risk_manager.config.max_position_size}, ideal would be {int(ideal_size)})"
                    )

    async def demo_risk_validation(self) -> None:
        """Demonstrate trade validation against risk rules."""
        print("\n" + "-" * 60)
        print("2. RISK VALIDATION DEMONSTRATION")
        print("-" * 60)

        if not self.suite:
            print("❌ Trading suite not initialized")
            return

        current_price = await self.suite.data.get_current_price()
        if not current_price:
            return

        # Test various trade scenarios
        test_trades = [
            {"size": 1, "side": OrderSide.BUY, "desc": "Small long (should pass)"},
            {"size": 10, "side": OrderSide.BUY, "desc": "Large long (should fail)"},
            {"size": 3, "side": OrderSide.SELL, "desc": "Medium short"},
        ]

        for trade in test_trades:
            print(f"\n🔍 Testing: {trade['desc']}")
            print(f"   Size: {trade['size']} contracts")

            if not self.suite.risk_manager:
                print("❌ Risk manager not enabled")
                return

            # Create real Order object for validation
            instrument = await self.suite.client.get_instrument("MNQ")

            # Create a proper Order instance
            from datetime import datetime

            side_value = cast(
                int,
                trade["side"].value
                if hasattr(trade["side"], "value")
                else trade["side"],
            )
            size_value = cast(int, trade["size"])

            mock_order = Order(
                id=0,
                accountId=0,
                contractId=instrument.id,
                creationTimestamp=datetime.now().isoformat(),
                updateTimestamp=None,
                status=1,  # Open
                type=2,  # Market
                side=side_value,
                size=size_value,
                limitPrice=current_price if trade["side"] == OrderSide.BUY else None,
            )

            validation = await self.suite.risk_manager.validate_trade(order=mock_order)

            if validation.get("is_valid"):
                # Calculate a simple risk score based on portfolio risk (0-10 scale)
                portfolio_risk = validation.get("portfolio_risk", 0)
                risk_score = min(10.0, portfolio_risk * 100)  # Convert to 0-10 scale
                print(f"   ✅ APPROVED - Risk Score: {risk_score:.2f}/10")
            else:
                reasons = validation.get("reasons", [])
                if reasons:
                    print("   ❌ REJECTED - Reasons:")
                    for reason in reasons:
                        print(f"      - {reason}")
                else:
                    print("   ❌ REJECTED")
                for warning in validation.get("warnings", []):
                    print(f"   ⚠️ Warning: {warning}")

    async def demo_managed_trade(self) -> None:
        """Demonstrate managed trade with automatic risk management."""
        print("\n" + "-" * 60)
        print("3. MANAGED TRADE DEMONSTRATION")
        print("-" * 60)

        if not self.demo_trades_enabled:
            print("⚠️ Demo trades disabled - skipping actual position opening")
            return

        if not self.suite:
            print("❌ Trading suite not initialized")
            return

        # Check if we already have positions (from the real position demo)
        existing_positions = await self.suite.positions.get_all_positions()
        if existing_positions:
            print(
                f"⚠️ Skipping managed trade demo - already have {len(existing_positions)} positions"
            )
            return

        current_price = await self.suite.data.get_current_price()
        if not current_price:
            return

        print("\n🎯 Executing managed trade with automatic risk controls...")
        print("   Entry: Market Order")
        print(f"   Stop Loss: ${current_price - 50:.2f}")
        print(f"   Take Profit: ${current_price + 100:.2f}")
        print("   Max Risk: 1% of account")

        if not self.suite.risk_manager:
            print("❌ Risk manager not enabled")
            return

        instrument = await self.suite.client.get_instrument("MNQ")

        # Execute managed trade
        async with ManagedTrade(
            risk_manager=self.suite.risk_manager,
            order_manager=self.suite.orders,
            position_manager=self.suite.positions,
            instrument_id=instrument.id,
            data_manager=self.suite.data,
            max_risk_percent=0.01,  # 1% max risk
        ) as trade:
            # Enter long position with automatic sizing
            try:
                position = await trade.enter_long(
                    stop_loss=current_price - 50,
                    take_profit=current_price + 100,
                )

                if position:
                    print("\n✅ Position opened:")
                    print(f"   Size: {position.get('size', 'N/A')} contracts")
                    if trade._entry_order:
                        print(f"   Entry Order: {trade._entry_order.id}")
                    if trade._stop_order:
                        print(f"   Stop Order: {trade._stop_order.id}")
                    if trade._target_order:
                        print(f"   Target Order: {trade._target_order.id}")

                    self.positions_opened.append(position)

                    # Monitor for a few seconds
                    print("\n⏱️ Monitoring position for 5 seconds...")
                    await asyncio.sleep(5)

                    # Check if trailing stop activated
                    if self.suite.risk_manager.config.use_trailing_stops:
                        print("📈 Trailing stop monitoring active")
                else:
                    print("❌ Failed to open position")
            except Exception as e:
                print(f"❌ Error in managed trade: {e}")

    async def demo_real_position(self) -> None:
        """Open a real position to test risk features."""
        print("\n" + "-" * 60)
        print("4. REAL POSITION DEMONSTRATION")
        print("-" * 60)

        if not self.demo_trades_enabled:
            print("⚠️ Demo trades disabled - skipping")
            return

        if not self.suite:
            print("❌ Trading suite not initialized")
            return

        current_price = await self.suite.data.get_current_price()
        if not current_price:
            return

        print("\n🔄 Opening a real position for testing...")

        # Place a small market order
        instrument = await self.suite.client.get_instrument("MNQ")

        try:
            order = await self.suite.orders.place_market_order(
                contract_id=instrument.id,
                side=OrderSide.BUY,
                size=1,
            )

            if order:
                self.orders_placed.append(order)
                print(f"   ✅ Market order placed: {order.orderId}")

                # Wait for fill
                await asyncio.sleep(3)

                # Get the position
                positions = await self.suite.positions.get_all_positions()
                if positions:
                    position = positions[0]
                    print(f"   ✅ Position opened: {position.contractId}")
                    print(f"   Size: {position.size} contracts")

                    # Now attach risk orders
                    await self.demo_risk_orders_for_position(position)
                else:
                    print("   ⚠️ No position found after order")
        except Exception as e:
            print(f"   ❌ Error placing order: {e}")

    async def demo_risk_orders_for_position(self, position: Position) -> None:
        """Attach and manage risk orders for a position."""
        print("\n📎 Attaching risk orders to position...")

        if not self.suite:
            return

        current_price = await self.suite.data.get_current_price()
        if not current_price or not self.suite.risk_manager:
            return

        # Attach stop and target orders
        try:
            orders = await self.suite.risk_manager.attach_risk_orders(
                position=position,
                stop_loss=current_price - 30,  # $30 stop
                take_profit=current_price + 60,  # $60 target
            )

            if orders:
                print("✅ Risk orders attached:")
                # orders is the dict returned from attach_risk_orders
                if "bracket_order" in orders:
                    bracket: BracketOrderResponse = orders["bracket_order"]
                    if bracket.stop_order_id:
                        print(f"   - Stop Order ID: {bracket.stop_order_id}")
                    if bracket.target_order_id:
                        print(f"   - Target Order ID: {bracket.target_order_id}")
                    # Store the bracket response
                    self.orders_placed.append(bracket)

            # Wait and then adjust stops
            await asyncio.sleep(3)

            print("\n🔄 Adjusting stops to breakeven...")
            entry_price = position.averagePrice
            # For long position, stop should be below entry (breakeven - $5 for safety)
            new_stop_price = entry_price - 5 if position.is_long else entry_price + 5

            # Add retry logic for stop adjustment
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    adjusted = await self.suite.risk_manager.adjust_stops(
                        position=position,
                        new_stop=new_stop_price,
                    )

                    if adjusted:
                        print(
                            f"   ✅ Stops adjusted successfully to ${new_stop_price:.2f}"
                        )
                        break
                    else:
                        if attempt < max_retries - 1:
                            print(
                                f"   ⚠️ Stop adjustment failed, retrying... (attempt {attempt + 1}/{max_retries})"
                            )
                            await asyncio.sleep(1)  # Wait before retry
                        else:
                            print(
                                f"   ❌ Failed to adjust stops after {max_retries} attempts"
                            )
                            print(f"    Attempted to set stop to ${new_stop_price:.2f}")
                except Exception as stop_error:
                    if attempt < max_retries - 1:
                        print(f"   ⚠️ Stop adjustment error: {stop_error}, retrying...")
                        await asyncio.sleep(1)
                    else:
                        print(f"   ❌ Stop adjustment failed with error: {stop_error}")
                        print(
                            f"    Check that stop price ${new_stop_price:.2f} is valid for {position.direction} position"
                        )

        except Exception as e:
            print(f"❌ Error managing risk orders: {e}")

    async def demo_portfolio_risk(self) -> None:
        """Demonstrate portfolio-wide risk analysis."""
        print("\n" + "-" * 60)
        print("5. PORTFOLIO RISK ANALYSIS")
        print("-" * 60)

        if not self.suite:
            print("❌ Trading suite not initialized")
            return

        # Get all positions
        positions = await self.suite.positions.get_all_positions()

        print(f"\n📊 Current Positions: {len(positions)}")
        for pos in positions:
            size = pos.size
            print(f"   - {pos.contractId}: {size} contracts")

        if not self.suite.risk_manager:
            print("❌ Risk manager not enabled")
            return

        # Calculate portfolio risk metrics
        metrics = await self.suite.risk_manager.get_risk_metrics()

        print("\n📊 Portfolio Risk Metrics:")
        print(f"   Total Positions: {metrics.get('position_count', 0)}")
        print(f"   Current Risk: ${metrics.get('current_risk', 0):,.2f}")
        print(f"   Daily P&L: ${metrics.get('daily_loss', 0):.2f}")
        print(f"   Max Drawdown: ${metrics.get('max_drawdown', 0):.2f}")
        print(f"   Account Balance: ${metrics.get('account_balance', 0):,.2f}")

        # Calculate and display additional metrics
        total_exposure = sum(
            pos["risk_amount"] for pos in metrics.get("position_risks", [])
        )
        risk_percentage = metrics.get("current_risk", 0) / max(
            metrics.get("account_balance", 1), 1
        )
        print(f"   Total Exposure: ${total_exposure:,.2f}")
        print(f"   Risk Percentage: {risk_percentage:.2%}")

        # Sharpe ratio is a standard field
        if metrics.get("sharpe_ratio"):
            print(f"   Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")

        # Check risk limits
        print("\n🚦 Risk Limit Status:")
        print(
            f"   Position Limit: {metrics.get('position_count', 0)}/{self.suite.risk_manager.config.max_positions}"
        )
        daily_loss = cast(float, metrics.get("daily_loss", 0))
        account_balance = cast(float, metrics.get("account_balance", 1))
        daily_loss_limit = self.suite.risk_manager.config.max_daily_loss
        if self.suite.risk_manager.config.max_daily_loss_amount:
            daily_loss_limit_amount = (
                self.suite.risk_manager.config.max_daily_loss_amount
            )
        else:
            daily_loss_limit_amount = Decimal(account_balance) * daily_loss_limit
        print(
            f"   Daily Loss Limit: ${abs(daily_loss):.2f}/${daily_loss_limit_amount:.2f}"
        )

        # Check for warnings (may not be in RiskAnalysisResponse)
        warnings = cast(Any, metrics).get("warnings", [])
        if warnings:
            print("\n⚠️ Risk Warnings:")
            for warning in warnings:
                print(f"   - {warning}")

    async def demo_trade_recording(self) -> None:
        """Demonstrate trade result recording for Kelly criterion."""
        print("\n" + "-" * 60)
        print("6. TRADE HISTORY & KELLY CRITERION")
        print("-" * 60)

        if not self.suite or not self.suite.risk_manager:
            print("❌ Risk manager not enabled")
            return

        # Record some sample trades for demonstration
        sample_trades = [
            {"pnl": 150, "entry": 20000, "exit": 20150},  # Win
            {"pnl": -75, "entry": 20100, "exit": 20025},  # Loss
            {"pnl": 200, "entry": 20050, "exit": 20250},  # Win
            {"pnl": -50, "entry": 20200, "exit": 20150},  # Loss
            {"pnl": 100, "entry": 20150, "exit": 20250},  # Win
        ]

        print("\n📝 Recording sample trade history...")
        for i, trade in enumerate(sample_trades, 1):
            await self.suite.risk_manager.record_trade_result(
                position_id=f"demo_trade_{i}",
                pnl=trade["pnl"],
                duration_seconds=300,  # 5 minutes demo
            )
            result = "WIN" if trade["pnl"] > 0 else "LOSS"
            print(f"   Trade {i}: {result} ${abs(trade['pnl']):.2f}")

        # Display Kelly statistics
        print("\n📊 Kelly Criterion Statistics:")
        print(f"   Win Rate: {self.suite.risk_manager._win_rate:.1%}")
        print(f"   Avg Win: ${self.suite.risk_manager._avg_win:.2f}")
        print(f"   Avg Loss: ${abs(float(self.suite.risk_manager._avg_loss)):.2f}")

        if (
            self.suite.risk_manager._win_rate > 0
            and self.suite.risk_manager._avg_win > 0
            and self.suite.risk_manager._avg_loss != 0
        ):
            # Calculate Kelly percentage
            win_loss_ratio = float(
                self.suite.risk_manager._avg_win
                / abs(self.suite.risk_manager._avg_loss)
            )
            kelly_pct = (
                self.suite.risk_manager._win_rate * win_loss_ratio
                - (1 - self.suite.risk_manager._win_rate)
            ) / win_loss_ratio
            print(f"   Kelly %: {kelly_pct:.1%}")
            print(
                f"   Recommended Position Size: {max(0, min(kelly_pct, 0.25)):.1%} of capital"
            )

    async def cleanup(self) -> None:
        """Clean up all positions and orders."""
        print("\n" + "-" * 60)
        print("CLEANUP")
        print("-" * 60)

        if not self.suite:
            print("❌ Trading suite not initialized")
            return

        try:
            # Cancel all open orders
            if self.orders_placed:
                print("\n🚫 Cancelling open orders...")
                cancelled_count = 0
                for order_response in self.orders_placed:
                    try:
                        # Check if it's an OrderPlaceResponse
                        if hasattr(order_response, "orderId"):
                            # Get current order status
                            orders = await self.suite.orders.search_open_orders()
                            order = next(
                                (o for o in orders if o.id == order_response.orderId),
                                None,
                            )
                            if order and order.is_working:
                                await self.suite.orders.cancel_order(order.id)
                                print(f"   ✅ Cancelled order {order.id}")
                                cancelled_count += 1
                    except Exception as e:
                        logger.debug(f"Could not cancel order: {e}")
                if cancelled_count > 0:
                    print(f"   Cancelled {cancelled_count} orders")

            # Close all positions
            positions = await self.suite.positions.get_all_positions()
            if positions:
                print(f"\n📉 Closing {len(positions)} positions...")
                for position in positions:
                    try:
                        # Get position size
                        size = position.size
                        if size == 0:
                            continue

                        # Place market order to flatten
                        close_side = OrderSide.SELL if size > 0 else OrderSide.BUY
                        close_order = await self.suite.orders.place_market_order(
                            contract_id=position.contractId,
                            side=close_side,
                            size=abs(size),
                        )
                        if close_order:
                            print(f"   ✅ Closed position: {position.contractId}")
                            await asyncio.sleep(1)
                    except Exception as e:
                        logger.error(f"Error closing position: {e}")

            # Final risk report
            if self.suite.risk_manager:
                final_metrics = await self.suite.risk_manager.get_risk_metrics()
                print("\n📊 Final Risk Report:")
                print(f"   Daily P&L: ${final_metrics.get('daily_pnl', 0):.2f}")
                print(f"   Max Drawdown: ${final_metrics.get('max_drawdown', 0):.2f}")
                print(f"   Total Trades: {self.suite.risk_manager._daily_trades}")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

        finally:
            if self.suite:
                await self.suite.disconnect()
                print("\n✅ Disconnected from trading suite")


async def main() -> None:
    """Run the complete risk manager demonstration."""
    demo = RiskManagerDemo()

    # Set this to False to skip actual trading
    demo.demo_trades_enabled = True  # Enable for full testing

    try:
        # Setup
        await demo.setup()

        # Run all demonstrations
        await demo.demo_position_sizing()
        await asyncio.sleep(2)

        await demo.demo_risk_validation()
        await asyncio.sleep(2)

        # Open a real position to test features
        await demo.demo_real_position()
        await asyncio.sleep(2)

        # Try managed trade
        await demo.demo_managed_trade()
        await asyncio.sleep(2)

        # Portfolio analysis
        await demo.demo_portfolio_risk()
        await asyncio.sleep(2)

        # Record trades for Kelly
        await demo.demo_trade_recording()

        print("\n" + "=" * 60)
        print("DEMO COMPLETE")
        print("=" * 60)
        print("\n⚠️ Remember to check your account for any open positions!")

    except KeyboardInterrupt:
        print("\n⚠️ Demo interrupted by user")
    except Exception as e:
        logger.error(f"Demo error: {e}", exc_info=True)
    finally:
        # Always cleanup
        await demo.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
