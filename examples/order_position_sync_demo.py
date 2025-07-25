#!/usr/bin/env python3
"""
Order-Position Synchronization Demo

This example demonstrates the new automatic synchronization between orders and positions:
1. When positions change size, related stop/target orders are automatically updated
2. When positions are closed, related orders are automatically cancelled
3. Track which orders belong to which positions

Author: TexasCoding
Date: June 2025
"""

import asyncio
import logging
from typing import Any

from project_x_py import ProjectX
from project_x_py.order_manager import OrderManager
from project_x_py.position_manager import PositionManager
from project_x_py.realtime import ProjectXRealtimeClient

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def order_position_sync_demo():
    """Demonstrate order-position synchronization features."""

    # Initialize the clients (replace with your actual credentials)
    client = ProjectX(
        username="your_username",
        api_key="your_api_key",
        account_name="your_account_name",
    )

    account_info = client.get_account_info()
    account_id = account_info.id if account_info else None
    jwt_token = client.get_session_token()

    realtime_client: ProjectXRealtimeClient | None = ProjectXRealtimeClient(
        jwt_token=jwt_token,
        account_id=str(account_id),
    )

    order_manager = OrderManager(client)
    position_manager = PositionManager(client)

    logger.info("🚀 Starting order-position synchronization demo")

    instrument = client.get_instrument("MGC")

    try:
        # Initialize all components with cross-references
        # Note: Check actual method signatures in your implementation
        order_manager.initialize(realtime_client=realtime_client)
        position_manager.initialize(
            realtime_client=realtime_client,
            order_manager=order_manager,  # Enable automatic synchronization
        )

        logger.info("✅ All components initialized")

        contract_id = instrument.id if instrument else None
        if not contract_id:
            raise ValueError("Instrument not found")

        # 1. Place a bracket order (entry + stop + target)
        logger.info(f"\n📈 Step 1: Placing bracket order for {contract_id}")
        bracket_response = order_manager.place_bracket_order(
            contract_id=contract_id,
            side=0,  # Buy
            size=2,  # 2 contracts
            entry_price=2045.0,
            stop_loss_price=2040.0,
            take_profit_price=2055.0,
        )

        if bracket_response.success:
            logger.info("✅ Bracket order placed successfully:")
            logger.info(f"   Entry Order: {bracket_response.entry_order_id}")
            logger.info(f"   Stop Order: {bracket_response.stop_order_id}")
            logger.info(f"   Target Order: {bracket_response.target_order_id}")

            # Show order tracking
            position_orders = order_manager.get_position_orders(contract_id)
            logger.info(f"📊 Orders tracked for {contract_id}: {position_orders}")
        else:
            logger.error(f"❌ Bracket order failed: {bracket_response.error_message}")
            return

        # Wait for potential position creation (if entry order fills)
        logger.info("\n⏳ Waiting for potential order fills...")
        await asyncio.sleep(10)

        # 2. Check current position
        current_position = position_manager.get_position(contract_id)
        if current_position:
            logger.info(f"📊 Current position: {current_position.size} contracts")

            # 3. Simulate adding to position (manual market order)
            logger.info("\n📈 Step 2: Adding to position (+1 contract)")
            add_response = order_manager.place_market_order(
                contract_id=contract_id,
                side=0,  # Buy (same direction)
                size=1,
            )

            if add_response.success:
                logger.info(f"✅ Added to position with order {add_response.orderId}")

                # Wait for position update
                await asyncio.sleep(5)

                # Check if orders were automatically updated
                updated_position = position_manager.get_position(contract_id)
                if updated_position:
                    logger.info(
                        f"📊 Updated position: {updated_position.size} contracts"
                    )
                    logger.info(
                        "🔄 Related stop/target orders should be automatically updated!"
                    )

            # 4. Simulate partial position close
            logger.info("\n📉 Step 3: Partially closing position (-1 contract)")
            close_response = order_manager.place_market_order(
                contract_id=contract_id,
                side=1,  # Sell (opposite direction)
                size=1,
            )

            if close_response.success:
                logger.info(
                    f"✅ Partially closed position with order {close_response.orderId}"
                )

                # Wait for position update
                await asyncio.sleep(5)

                # Check updated position and orders
                updated_position = position_manager.get_position(contract_id)
                if updated_position:
                    logger.info(
                        f"📊 Position after partial close: {updated_position.size} contracts"
                    )
                    logger.info(
                        "🔄 Related orders should be updated to match new position size!"
                    )

            # 5. Close entire position
            logger.info("\n🔚 Step 4: Closing entire position")
            final_close = position_manager.close_position_direct(contract_id)

            if final_close.get("success", False):
                logger.info("✅ Position closed completely")

                # Wait for position closure processing
                await asyncio.sleep(5)

                # Check that related orders were cancelled
                remaining_position = position_manager.get_position(contract_id)
                if not remaining_position:
                    logger.info(
                        "✅ Position closed - related orders should be automatically cancelled!"
                    )
                    position_orders = order_manager.get_position_orders(contract_id)
                    logger.info(f"📊 Remaining tracked orders: {position_orders}")

        else:
            logger.info(
                "📊 No position currently open (entry order may not have filled)"
            )

            # Manual synchronization example
            logger.info("\n🔄 Step 2: Manual synchronization example")
            sync_result = order_manager.sync_orders_with_position(contract_id)
            logger.info(f"📊 Sync result: {sync_result}")

        # 6. Show final statistics
        logger.info("\n📊 Final Statistics:")
        order_stats = order_manager.get_order_statistics()
        position_stats = position_manager.get_position_statistics()

        logger.info("Order Manager - Position Order Tracking:")
        logger.info(
            f"   Total tracked orders: {order_stats['position_order_relationships']['total_tracked_orders']}"
        )
        logger.info(
            f"   Positions with orders: {order_stats['position_order_relationships']['positions_with_orders']}"
        )

        logger.info("Position Manager - Order Sync Status:")
        logger.info(f"   Order sync enabled: {position_stats['order_sync_enabled']}")
        logger.info(f"   Realtime enabled: {position_stats['realtime_enabled']}")

        # 7. Cleanup any remaining orders
        logger.info(f"\n🧹 Cleaning up any remaining orders for {contract_id}")
        cleanup_result = order_manager.cancel_position_orders(contract_id)
        logger.info(f"📊 Cleanup result: {cleanup_result}")

    except Exception as e:
        logger.error(f"❌ Demo error: {e}")

    finally:
        # Cleanup
        logger.info("\n🧹 Cleaning up connections...")
        order_manager.cleanup()
        position_manager.cleanup()
        if realtime_client:
            realtime_client.disconnect()
        logger.info("✅ Demo completed!")


def callback_demo():
    """Demonstrate callback-based order-position synchronization."""

    logger.info("\n🔔 Callback Demo - Setting up position change handlers")

    def on_position_closed(data: Any):
        """Handle position closure events."""
        logger.info(f"🔔 Position closed callback triggered: {data}")

    def on_position_alert(data: Any):
        """Handle position alert events."""
        logger.info(f"🚨 Position alert callback triggered: {data}")

    def on_order_filled(data: Any):
        """Handle order fill events."""
        logger.info(f"✅ Order filled callback triggered: {data}")

    # These callbacks would be registered in a real application:
    # position_manager.add_callback("position_closed", on_position_closed)
    # position_manager.add_callback("position_alert", on_position_alert)
    # order_manager.add_callback("order_filled", on_order_filled)

    logger.info("📝 Callback setup complete (example only)")


def manual_sync_demo():
    """Demonstrate manual order-position synchronization methods."""

    logger.info("\n🔧 Manual Synchronization Demo")

    # These are the key synchronization methods available:

    # 1. Track individual orders for positions
    # order_manager.track_order_for_position(order_id=12345, contract_id="MGC", order_category="stop")

    # 2. Get all orders related to a position
    # position_orders = order_manager.get_position_orders("MGC")

    # 3. Cancel all orders for a position
    # result = order_manager.cancel_position_orders("MGC", categories=["stop", "target"])

    # 4. Update order sizes to match position
    # result = order_manager.update_position_order_sizes("MGC", new_position_size=3)

    # 5. Full synchronization
    # result = order_manager.sync_orders_with_position("MGC")

    # 6. Position-triggered callbacks
    # order_manager.on_position_changed("MGC", old_size=2, new_size=3)
    # order_manager.on_position_closed("MGC")

    logger.info("📝 Manual synchronization methods available:")
    logger.info("   - track_order_for_position()")
    logger.info("   - get_position_orders()")
    logger.info("   - cancel_position_orders()")
    logger.info("   - update_position_order_sizes()")
    logger.info("   - sync_orders_with_position()")
    logger.info("   - on_position_changed() / on_position_closed()")


if __name__ == "__main__":
    logger.info("🔄 Order-Position Synchronization Demo")
    logger.info("=" * 50)

    # Show manual methods
    manual_sync_demo()

    # Show callback setup
    callback_demo()

    # Run the main demo
    logger.info("\n🚀 Starting live demo...")
    try:
        asyncio.run(order_position_sync_demo())
    except KeyboardInterrupt:
        logger.info("\n⏹️  Demo interrupted by user")
    except Exception as e:
        logger.error(f"❌ Demo failed: {e}")
