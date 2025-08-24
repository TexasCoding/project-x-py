#!/usr/bin/env python3
"""
Example: Order Lifecycle Tracking with EventBus v4.0.0

This example demonstrates modern order lifecycle management using the EventBus
system and OrderManager bracket orders, replacing the deprecated OrderTracker
and OrderChainBuilder from v3.x.

Key features shown:
- EventBus-based order event tracking with suite.on(EventType.ORDER_FILLED, callback)
- Async order state monitoring with timeouts
- OrderManager.place_bracket_order() for complex orders (replaces OrderChainBuilder)
- Manual order modification and cancellation
- Event-driven order lifecycle management
- Multiple order tracking patterns

Migration from v3.x:
- OrderTracker → Custom OrderTracker class using EventBus
- OrderChainBuilder → OrderManager.place_bracket_order()
- suite.track_order() → Custom event tracking with suite.on()
- suite.order_chain() → Direct OrderManager methods

Note: This example may show "Outside of trading hours" errors when markets are closed.
This is expected behavior and demonstrates proper error handling.

Author: SDK v4.0.0 Examples
"""

import asyncio
from decimal import Decimal
from typing import Any, Dict, List, Optional

from project_x_py import EventType, OrderSide, ProjectXOrderError, TradingSuite


class OrderTracker:
    """Modern order tracker using EventBus for lifecycle monitoring."""

    def __init__(self, suite: TradingSuite):
        self.suite = suite
        self.tracked_orders: Dict[int, Dict[str, Any]] = {}
        self.order_events: Dict[int, List[Any]] = {}
        self.event_handlers: List[tuple] = []

    async def __aenter__(self) -> "OrderTracker":
        """Enter context and register event handlers."""
        # Register for all order-related events
        await self.suite.on(EventType.ORDER_PLACED, self._handle_order_event)
        await self.suite.on(EventType.ORDER_FILLED, self._handle_order_event)
        await self.suite.on(EventType.ORDER_PARTIAL_FILL, self._handle_order_event)
        await self.suite.on(EventType.ORDER_CANCELLED, self._handle_order_event)
        await self.suite.on(EventType.ORDER_MODIFIED, self._handle_order_event)
        await self.suite.on(EventType.ORDER_REJECTED, self._handle_order_event)

        self.event_handlers = [
            (EventType.ORDER_PLACED, self._handle_order_event),
            (EventType.ORDER_FILLED, self._handle_order_event),
            (EventType.ORDER_PARTIAL_FILL, self._handle_order_event),
            (EventType.ORDER_CANCELLED, self._handle_order_event),
            (EventType.ORDER_MODIFIED, self._handle_order_event),
            (EventType.ORDER_REJECTED, self._handle_order_event),
        ]

        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context and unregister event handlers."""
        for event_type, handler in self.event_handlers:
            await self.suite.off(event_type, handler)

    async def _handle_order_event(self, event: Any) -> None:
        """Handle incoming order events."""
        order_data = event.data
        order_id = order_data.get("order_id") or order_data.get("id")

        if order_id and order_id in self.tracked_orders:
            # Update order status
            self.tracked_orders[order_id]["last_event"] = event
            self.tracked_orders[order_id]["status"] = order_data.get(
                "status", "UNKNOWN"
            )

            # Store event history
            if order_id not in self.order_events:
                self.order_events[order_id] = []
            self.order_events[order_id].append(event)

    def track(self, order: Any) -> None:
        """Start tracking an order."""
        order_id = order.orderId if hasattr(order, "orderId") else order.id
        self.tracked_orders[order_id] = {
            "order": order,
            "status": "PENDING",
            "last_event": None,
            "created_at": asyncio.get_event_loop().time(),
        }

    async def wait_for_fill(
        self, order_id: Optional[int] = None, timeout: float = 30
    ) -> Any:
        """Wait for an order to fill."""
        target_order_id = (
            order_id or list(self.tracked_orders.keys())[0]
            if self.tracked_orders
            else None
        )

        if not target_order_id:
            raise ProjectXOrderError("No order being tracked")

        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_time < timeout:
            if target_order_id in self.tracked_orders:
                last_event = self.tracked_orders[target_order_id]["last_event"]
                if last_event and last_event.event_type == EventType.ORDER_FILLED:
                    return last_event.data

            await asyncio.sleep(0.1)

        raise TimeoutError(f"Order {target_order_id} not filled within {timeout}s")

    async def wait_for_status(
        self, target_status: int, order_id: Optional[int] = None, timeout: float = 30
    ) -> Any:
        """Wait for an order to reach a specific status."""
        target_order_id = (
            order_id or list(self.tracked_orders.keys())[0]
            if self.tracked_orders
            else None
        )

        if not target_order_id:
            raise ProjectXOrderError("No order being tracked")

        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_time < timeout:
            if target_order_id in self.tracked_orders:
                status = self.tracked_orders[target_order_id].get("status")
                if status == target_status:
                    return self.tracked_orders[target_order_id]["last_event"]

            await asyncio.sleep(0.1)

        raise TimeoutError(
            f"Order {target_order_id} did not reach status {target_status} within {timeout}s"
        )

    async def modify_or_cancel(
        self, order_id: Optional[int] = None, new_price: Optional[Decimal] = None
    ) -> bool:
        """Modify order price or cancel if modification fails."""
        target_order_id = (
            order_id or list(self.tracked_orders.keys())[0]
            if self.tracked_orders
            else None
        )

        if not target_order_id:
            return False

        if new_price:
            try:
                # Attempt to modify the order
                success = await self.suite.orders.modify_order(
                    target_order_id, limit_price=new_price
                )
                return success
            except Exception:
                # If modification fails, try to cancel
                pass

        # Cancel the order
        try:
            return await self.suite.orders.cancel_order(target_order_id)
        except Exception:
            return False

    async def get_current_status(
        self, order_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Get current order status."""
        target_order_id = (
            order_id or list(self.tracked_orders.keys())[0]
            if self.tracked_orders
            else None
        )

        if target_order_id and target_order_id in self.tracked_orders:
            return self.tracked_orders[target_order_id]

        return None


async def demonstrate_basic_order_tracking() -> None:
    """Show basic order tracking with EventBus."""

    async with await TradingSuite.create("MNQ") as suite:
        print("=== Basic Order Tracking with EventBus ===\n")

        # Get current price
        price = await suite.data.get_latest_price()
        if price is None:
            print("No price data available")
            return

        print(f"Current price: ${price:,.2f}")
        print(f"Using contract: {suite.instrument_id}\n")

        # Create order tracker
        async with OrderTracker(suite) as tracker:
            try:
                # Place a limit order below market
                assert suite.instrument_id is not None
                order = await suite.orders.place_limit_order(
                    contract_id=suite.instrument_id,
                    side=0,  # BUY
                    size=1,
                    limit_price=price - 50,  # 50 points below market
                )

                if not order.success:
                    print(f"Order failed: {order.errorMessage}")
                    print(
                        "Note: This is likely due to market being closed or invalid parameters"
                    )
                    return

                # Track the order
                tracker.track(order)
                print(f"Placed BUY limit order at ${price - 50:,.2f}")
                print(f"Order ID: {order.orderId}")

                # Wait for fill or timeout
                try:
                    print("Waiting for fill (10s timeout)...")
                    filled_order = await tracker.wait_for_fill(timeout=10)
                    print(
                        f"✅ Order filled at ${filled_order.get('filledPrice', 'N/A'):,.2f}!"
                    )

                except TimeoutError:
                    print("⏱️ Order not filled in 10 seconds")

                    # Try to improve the price
                    print("Modifying order price...")
                    success = await tracker.modify_or_cancel(
                        new_price=Decimal(str(price - 25))
                    )

                    if success:
                        print(f"✅ Order modified to ${price - 25:,.2f}")
                    else:
                        print("❌ Order cancelled")

                except ProjectXOrderError as e:
                    print(f"❌ Order error: {e}")

            except ProjectXOrderError as e:
                print(f"❌ Order placement failed: {e}")
                print(
                    "This is expected when markets are closed. The example shows proper error handling."
                )


async def demonstrate_bracket_orders() -> None:
    """Show modern bracket order functionality."""

    async with await TradingSuite.create("MNQ") as suite:
        print("\n=== Modern Bracket Orders ===\n")

        # Get current price
        price = await suite.data.get_latest_price()
        if price is None:
            print("No price data available")
            return

        print(f"Current price: ${price:,.2f}")

        try:
            # 1. Market bracket order
            print("\n1. Market Order with Bracket:")
            assert suite.instrument_id is not None

            # For market bracket order, use current price as entry_price
            result = await suite.orders.place_bracket_order(
                contract_id=suite.instrument_id,
                side=0,  # BUY
                size=1,
                entry_price=price,  # Market entry
                stop_loss_price=price - 20,  # 20 points stop
                take_profit_price=price + 40,  # 40 points target
                entry_type="market",  # Market entry order
            )

            if result.success:
                print("✅ Bracket order placed successfully:")
                print(f"   Entry: Market order (ID: {result.entry_order_id})")
                print("   Stop and target orders will be placed after fill")
            else:
                print(f"❌ Bracket order failed: {result.error_message}")
                print("Note: This is expected when markets are closed")

            await asyncio.sleep(2)  # Allow processing time

            print("\n" + "-" * 50)

            # 2. Limit bracket order with specific prices
            print("\n2. Limit Order with Specific Stop/Target Prices:")

            entry_price = price - 10
            stop_price = price - 30
            target_price = price + 20

            result = await suite.orders.place_bracket_order(
                contract_id=suite.instrument_id,
                side=0,  # BUY
                size=1,
                entry_price=entry_price,  # Limit entry
                stop_loss_price=stop_price,
                take_profit_price=target_price,
                entry_type="limit",  # Limit entry order
            )

            print(f"Entry: Limit BUY at ${entry_price:,.2f}")
            print(f"Stop: ${stop_price:,.2f}")
            print(f"Target: ${target_price:,.2f}")
            print(f"Result: {'✅ Success' if result.success else '❌ Failed'}")

            if not result.success:
                print(f"Error: {result.error_message}")
                print("Note: This is expected when markets are closed")

        except ProjectXOrderError as e:
            print(f"❌ Bracket order placement failed: {e}")
            print(
                "This demonstrates the EventBus pattern even when orders fail due to market hours."
            )


async def demonstrate_event_monitoring() -> None:
    """Show comprehensive event monitoring."""

    async with await TradingSuite.create("MNQ") as suite:
        print("\n=== Event-Driven Order Monitoring ===\n")

        # Track all order events
        events_received: List[Any] = []
        order_states: Dict[int, str] = {}

        async def on_order_placed(event: Any) -> None:
            events_received.append(event)
            order_id = event.data.get("order_id", event.data.get("id"))
            order_states[order_id] = "PLACED"
            print(f"📨 ORDER_PLACED - Order {order_id}")

        async def on_order_filled(event: Any) -> None:
            events_received.append(event)
            order_id = event.data.get("order_id", event.data.get("id"))
            order_states[order_id] = "FILLED"
            fill_price = event.data.get("filledPrice", "N/A")
            print(f"✅ ORDER_FILLED - Order {order_id} at ${fill_price}")

        async def on_order_cancelled(event: Any) -> None:
            events_received.append(event)
            order_id = event.data.get("order_id", event.data.get("id"))
            order_states[order_id] = "CANCELLED"
            print(f"❌ ORDER_CANCELLED - Order {order_id}")

        async def on_order_modified(event: Any) -> None:
            events_received.append(event)
            order_id = event.data.get("order_id", event.data.get("id"))
            print(f"📝 ORDER_MODIFIED - Order {order_id}")

        # Register event handlers
        await suite.on(EventType.ORDER_PLACED, on_order_placed)
        await suite.on(EventType.ORDER_FILLED, on_order_filled)
        await suite.on(EventType.ORDER_CANCELLED, on_order_cancelled)
        await suite.on(EventType.ORDER_MODIFIED, on_order_modified)

        try:
            # Get current price
            price = await suite.data.get_latest_price()
            if price is None:
                return

            print(f"Current price: ${price:,.2f}")

            # Place order far from market
            assert suite.instrument_id is not None
            try:
                order = await suite.orders.place_limit_order(
                    contract_id=suite.instrument_id,
                    side=1,  # SELL
                    size=1,
                    limit_price=price + 100,  # Far from market
                )
            except ProjectXOrderError as e:
                print(f"❌ Order placement failed: {e}")
                print(
                    "This is expected when markets are closed. Event monitoring still demonstrated."
                )
                return

            if order.success:
                print(f"Placed SELL limit order at ${price + 100:,.2f}")

                # Wait for placed event
                await asyncio.sleep(1)

                # Modify the order
                print("Modifying order price...")
                await suite.orders.modify_order(order.orderId, limit_price=price + 50)

                await asyncio.sleep(1)

                # Cancel the order
                print("Cancelling order...")
                await suite.orders.cancel_order(order.orderId)

                await asyncio.sleep(1)

                print("\nEvent Summary:")
                print(f"Total events received: {len(events_received)}")
                for order_id, state in order_states.items():
                    print(f"Order {order_id}: {state}")

        finally:
            # Unregister event handlers
            await suite.off(EventType.ORDER_PLACED, on_order_placed)
            await suite.off(EventType.ORDER_FILLED, on_order_filled)
            await suite.off(EventType.ORDER_CANCELLED, on_order_cancelled)
            await suite.off(EventType.ORDER_MODIFIED, on_order_modified)


async def demonstrate_multiple_order_tracking() -> None:
    """Show tracking multiple orders simultaneously."""

    async with await TradingSuite.create("MNQ") as suite:
        print("\n=== Multiple Order Tracking ===\n")

        # Get current price
        price = await suite.data.get_latest_price()
        if price is None:
            return

        print(f"Current price: ${price:,.2f}")

        # Create multiple orders with event tracking
        order_trackers: Dict[int, Dict[str, Any]] = {}

        async def track_order_event(event: Any) -> None:
            """Track events for all our orders."""
            order_data = event.data
            order_id = order_data.get("order_id", order_data.get("id"))

            if order_id in order_trackers:
                order_trackers[order_id]["events"].append(event)
                order_trackers[order_id]["last_status"] = event.event_type.name
                print(f"📨 {event.event_type.name} - Order {order_id}")

        # Register event handler
        await suite.on(EventType.ORDER_PLACED, track_order_event)
        await suite.on(EventType.ORDER_FILLED, track_order_event)
        await suite.on(EventType.ORDER_CANCELLED, track_order_event)

        try:
            # Place multiple staggered orders
            orders_placed = []

            for i in range(3):
                assert suite.instrument_id is not None
                try:
                    order = await suite.orders.place_limit_order(
                        contract_id=suite.instrument_id,
                        side=0,  # BUY
                        size=1,
                        limit_price=price - (10 * (i + 1)),  # Staggered prices
                    )
                except ProjectXOrderError:
                    print(f"Order {i + 1}: Failed (market closed)")
                    continue

                if order.success:
                    orders_placed.append(order)
                    order_trackers[order.orderId] = {
                        "order": order,
                        "events": [],
                        "last_status": "PENDING",
                        "price": price - (10 * (i + 1)),
                    }
                    print(
                        f"Order {i + 1}: BUY at ${price - (10 * (i + 1)):,.2f} (ID: {order.orderId})"
                    )

            print(f"\nTracking {len(orders_placed)} orders...")
            await asyncio.sleep(2)  # Allow events to process

            # Check if any filled (unlikely with prices far from market)
            filled_orders = [
                order_id
                for order_id, data in order_trackers.items()
                if data["last_status"] == "ORDER_FILLED"
            ]

            if filled_orders:
                print(f"✅ {len(filled_orders)} orders filled!")
            else:
                print("⏱️ No orders filled (as expected with off-market prices)")

            # Cancel remaining orders
            print("Cancelling remaining orders...")
            for order in orders_placed:
                if order.orderId in order_trackers:
                    await suite.orders.cancel_order(order.orderId)

            await asyncio.sleep(1)  # Allow cancel events

            # Summary
            print("\nTracking Summary:")
            for order_id, data in order_trackers.items():
                print(
                    f"Order {order_id}: {len(data['events'])} events, status: {data['last_status']}"
                )

        finally:
            # Cleanup event handlers
            await suite.off(EventType.ORDER_PLACED, track_order_event)
            await suite.off(EventType.ORDER_FILLED, track_order_event)
            await suite.off(EventType.ORDER_CANCELLED, track_order_event)


async def demonstrate_advanced_bracket_patterns() -> None:
    """Show advanced bracket order patterns."""

    async with await TradingSuite.create("MNQ") as suite:
        print("\n=== Advanced Bracket Patterns ===\n")

        # Get current price
        price = await suite.data.get_latest_price()
        if price is None:
            return

        print(f"Current price: ${price:,.2f}")

        # 1. Risk-based bracket (risking $100)
        print("\n1. Risk-Based Bracket Order:")

        # Calculate position size for $100 risk with 20-point stop
        tick_value = 5.0  # MNQ tick value
        risk_points = 20
        risk_amount = 100.0
        position_size = int(risk_amount / (risk_points * tick_value))

        assert suite.instrument_id is not None
        result = await suite.orders.place_bracket_order(
            contract_id=suite.instrument_id,
            side=0,  # BUY
            size=position_size,
            entry_price=price - 5,  # 5 points below market
            stop_loss_price=price - 5 - risk_points,  # 20 points stop
            take_profit_price=price
            - 5
            + (risk_points * 2),  # 40 points target (2:1 R/R)
            entry_type="limit",  # Limit entry order
        )

        print(f"Risk Amount: ${risk_amount}")
        print(f"Position Size: {position_size} contracts")
        print(f"Entry: ${price - 5:,.2f}")
        print(f"Stop: ${price - 5 - risk_points:,.2f}")
        print(f"Target: ${price - 5 + (risk_points * 2):,.2f}")
        print("Risk/Reward: 1:2")
        print(f"Result: {'✅ Success' if result.success else '❌ Failed'}")

        if not result.success:
            print(f"Error: {result.error_message}")

        await asyncio.sleep(1)

        print("\n" + "-" * 50)

        # 2. Trailing stop simulation (manual approach)
        print("\n2. Manual Trailing Stop Pattern:")

        # Place initial position
        try:
            entry_order = await suite.orders.place_market_order(
                contract_id=suite.instrument_id,
                side=0,  # BUY
                size=1,
            )
        except ProjectXOrderError as e:
            print(f"❌ Entry order failed: {e}")
            print(
                "This is expected when markets are closed. Example shows trailing stop concept."
            )
            return

        if entry_order.success:
            print(f"✅ Market order placed (ID: {entry_order.orderId})")

            # Simulate trailing stop logic
            initial_stop = price - 20
            trail_amount = 10

            print(f"Initial stop: ${initial_stop:,.2f}")
            print(f"Trail amount: {trail_amount} points")
            print("(In real trading, this would monitor price and adjust stop)")

            # Place initial stop
            try:
                stop_order = await suite.orders.place_stop_order(
                    contract_id=suite.instrument_id,
                    side=1,  # SELL
                    size=1,
                    stop_price=initial_stop,
                )

                if stop_order.success:
                    print(f"✅ Initial stop placed at ${initial_stop:,.2f}")
                else:
                    print(f"❌ Stop order failed: {stop_order.errorMessage}")
            except ProjectXOrderError as e:
                print(f"❌ Stop order failed: {e}")
                print("This is expected when markets are closed")

            # In a real implementation, you would:
            # 1. Monitor price updates via WebSocket
            # 2. Calculate new stop level when price moves favorably
            # 3. Modify stop order when trail threshold is hit
            # 4. Handle fill events and cleanup

            print("(Trailing logic would run here in production)")


async def cleanup_demo_orders_and_positions() -> None:
    """Clean up any open orders and positions created during the demo."""
    print("\n" + "=" * 50)
    print("=== Demo Cleanup ===")
    print("=" * 50 + "\n")

    async with await TradingSuite.create("MNQ") as suite:
        print("Cleaning up demo orders and positions...\n")

        # 1. Cancel all open orders
        print("1. Checking for open orders...")
        try:
            open_orders = await suite.orders.search_open_orders()

            if open_orders:
                print(f"   Found {len(open_orders)} open orders to cancel:")
                for order in open_orders:
                    try:
                        success = await suite.orders.cancel_order(order.id)
                        if success:
                            # Get order type and side names safely
                            order_type = (
                                "LIMIT"
                                if order.type == 1
                                else "MARKET"
                                if order.type == 2
                                else "STOP"
                                if order.type == 4
                                else str(order.type)
                            )
                            side = (
                                "BUY"
                                if order.side == 0
                                else "SELL"
                                if order.side == 1
                                else str(order.side)
                            )
                            print(
                                f"   ✅ Cancelled order {order.id} ({order_type} {side})"
                            )
                        else:
                            print(f"   ⚠️ Failed to cancel order {order.id}")
                    except Exception as e:
                        print(f"   ⚠️ Error cancelling order {order.id}: {e}")
            else:
                print("   No open orders found")
        except Exception as e:
            print(f"   ⚠️ Error retrieving open orders: {e}")

        print()

        # 2. Close all open positions
        print("2. Checking for open positions...")
        try:
            positions = await suite.positions.get_all_positions()

            if positions:
                print(f"   Found {len(positions)} positions to check:")
                for position in positions:
                    if position.size != 0:
                        try:
                            # Place a market order to close the position
                            # Position type: 1=LONG, 2=SHORT
                            order_side = int(
                                OrderSide.SELL if position.type == 1 else OrderSide.BUY
                            )  # SELL if long, BUY if short
                            size = position.size  # size is always positive

                            result = await suite.orders.place_market_order(
                                contract_id=position.contractId,
                                side=order_side,
                                size=size,
                            )

                            if result.success:
                                position_type = (
                                    "LONG"
                                    if position.type == 1
                                    else "SHORT"
                                    if position.type == 2
                                    else "UNKNOWN"
                                )
                                print(
                                    f"   ✅ Closed {position_type} position in {position.contractId} (Size: {position.size})"
                                )
                            else:
                                print(
                                    f"   ⚠️ Failed to close position in {position.contractId}: {result.errorMessage}"
                                )
                        except Exception as e:
                            print(
                                f"   ⚠️ Error closing position in {position.contractId}: {e}"
                            )
            else:
                print("   No open positions found")
        except Exception as e:
            print(f"   ⚠️ Error retrieving positions: {e}")

        print("\n✅ Demo cleanup complete!")


async def main() -> None:
    """Run all demonstrations."""
    try:
        # Basic order tracking with EventBus
        await demonstrate_basic_order_tracking()

        # Modern bracket orders
        await demonstrate_bracket_orders()

        # Event monitoring
        await demonstrate_event_monitoring()

        # Multiple order tracking
        await demonstrate_multiple_order_tracking()

        # Advanced bracket patterns
        await demonstrate_advanced_bracket_patterns()

    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        # Always run cleanup, even if demo fails
        try:
            await cleanup_demo_orders_and_positions()
        except Exception as cleanup_error:
            print(f"\n⚠️ Cleanup error: {cleanup_error}")


if __name__ == "__main__":
    print("ProjectX SDK v4.0.0 - Order Lifecycle Tracking with EventBus")
    print("=" * 60)
    print("This example demonstrates migration from v3.x deprecated features:")
    print("• OrderTracker → Custom EventBus-based tracking")
    print("• OrderChainBuilder → OrderManager.place_bracket_order()")
    print("• suite.track_order() → suite.on(EventType.ORDER_FILLED, callback)")
    print("• suite.order_chain() → Direct OrderManager methods")
    print("=" * 60)
    asyncio.run(main())
