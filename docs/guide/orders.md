# Order Management Guide

This guide covers comprehensive order management using ProjectX Python SDK v3.3.4+. All order operations are fully asynchronous and provide real-time tracking capabilities.

## Overview

The OrderManager provides complete lifecycle management for all order types including market, limit, stop, OCO (One Cancels Other), and bracket orders. All operations are async-first for optimal performance in trading applications.

### Key Features

- **Multiple Order Types**: Market, limit, stop, OCO, and bracket orders
- **Real-time Tracking**: Live order status updates via WebSocket
- **Error Recovery**: Automatic retry logic and comprehensive error handling
- **Price Precision**: Automatic tick size alignment using Decimal arithmetic
- **Concurrent Operations**: Place and manage multiple orders simultaneously
- **Risk Integration**: Built-in integration with RiskManager when enabled

## Getting Started

### Basic Setup

```python
import asyncio
from decimal import Decimal

from project_x_py import TradingSuite


async def main():
    # Initialize with order management capabilities
    suite = await TradingSuite.create("MNQ")

    mnq_context = suite["MNQ"]
    # Order manager is automatically available
    order_manager = mnq_context.orders

    # Get instrument information for proper pricing
    instrument = mnq_context.instrument_info
    print(f"Tick size: ${instrument.tickSize}")


asyncio.run(main())
```

### Safety First

** WARNING**: Order examples in this guide place real orders on the market. Always:

- Use micro contracts (MNQ, MES) for testing
- Set small position sizes
- Have exit strategies ready
- Test in paper trading environments when available

## Order Types

### Market Orders

Market orders execute immediately at the current market price with guaranteed fills but no price control.

```python
import asyncio

from project_x_py import TradingSuite


async def place_market_order():
    suite = await TradingSuite.create("MNQ")

    try:
        # Place buy market order
        response = await suite["MNQ"].orders.place_market_order(
            contract_id=suite["MNQ"].instrument_info.id,  # Or use suite.instrument_info.id
            side=0,  # 0 = Buy, 1 = Sell
            size=1,  # Number of contracts
        )

        print(f"Market order placed: {response.orderId}")
        print(f"Status: {response.success}")

        # Wait for fill confirmation
        await asyncio.sleep(2)
        order_status = await suite["MNQ"].orders.get_order_statistics_async()
        print(f"Final status: {order_status}")

    except Exception as e:
        print(f"Order failed: {e}")
    finally:
        await suite.disconnect()


asyncio.run(place_market_order())
```

### Native Gateway brackets

Prefer attaching stop and target on the entry when the Gateway accepts native brackets:

```python
await suite.orders.place_order(
    contract_id=suite.instrument_info.id,
    side=0,
    size=1,
    order_type=1,
    limit_price=21000.0,
    stop_loss_bracket={"ticks": 16, "type": 4},
    take_profit_bracket={"ticks": 32, "type": 1},
)
```

If a place/cancel HTTP call is cancelled or the transport drops after send, catch
`OrderSubmissionUncertainError` and reconcile with `get_order_by_id()` before retrying.

### Limit Orders

Limit orders execute only at specified price or better, providing price control but no fill guarantee.

```python
import asyncio
from decimal import Decimal

from project_x_py import TradingSuite


async def place_limit_order():
    suite = await TradingSuite.create("MNQ")

    # Get current market price for context
    current_price = await suite["MNQ"].data.get_current_price()

    # Place buy limit order below market
    limit_price = Decimal(str(current_price)) - Decimal("2.00")  # $2.00 below market

    response = await suite["MNQ"].orders.place_limit_order(
        contract_id=suite["MNQ"].instrument_info.id,
        side=0,  # Buy
        size=1,
        limit_price=float(limit_price),
    )

    print(f"Limit order placed at ${limit_price}")
    print(f"Order ID: {response.orderId}")

    # Monitor order status
    while True:
        status = await suite["MNQ"].orders.get_order_by_id(response.orderId)
        if status is None:
            continue

        if status.status in [2, 3, 4]:
            print(
                f"Status: {'FILLED' if status.status == 2 else 'CANCELLED' if status.status == 3 else 'EXPIRED' if status.status == 4 else 'PENDING'}"
            )
            break

        await asyncio.sleep(5)  # Check every 5 seconds


asyncio.run(place_limit_order())
```

### Stop Orders

Stop orders become market orders when the stop price is reached, useful for exits and breakout entries.

```python
import asyncio
from decimal import Decimal

from project_x_py import TradingSuite


async def place_stop_order():
    suite = await TradingSuite.create("MNQ")

    current_price = await suite["MNQ"].data.get_current_price()

    # Stop loss order (sell stop below current price)
    stop_price = Decimal(str(current_price)) - Decimal("2.00")  # $2.00 below market

    response = await suite["MNQ"].orders.place_stop_order(
        contract_id=suite["MNQ"].instrument_info.id,
        side=1,  # Sell (for stop loss)
        size=1,
        stop_price=float(stop_price),
    )

    print(f"Stop order placed at ${stop_price}")

    # Or stop entry order (buy stop above current price for breakouts)
    breakout_price = Decimal(str(current_price)) + Decimal("2.00")

    breakout_response = await suite["MNQ"].orders.place_stop_order(
        contract_id=suite["MNQ"].instrument_info.id,
        side=0,  # Buy
        size=1,
        stop_price=float(breakout_price),
    )

    print(f"Breakout order placed at ${breakout_price}")


asyncio.run(place_stop_order())
```

### Bracket Orders

Bracket orders are the most sophisticated order type, combining entry, stop loss, and take profit in one operation.

```python
import asyncio
from decimal import Decimal

from project_x_py import TradingSuite
from project_x_py.models import BracketOrderResponse


async def place_bracket_order():
    suite = await TradingSuite.create("MNQ")

    current_price = await suite["MNQ"].data.get_current_price()

    # Complete bracket order setup
    response = await suite["MNQ"].orders.place_bracket_order(
        contract_id=suite["MNQ"].instrument_info.id,
        side=0,  # Buy entry
        size=1,
        # Entry order (optional - if None, uses market order)
        entry_type="market",
        entry_price=None,
        # Risk management
        stop_loss_price=float(
            Decimal(str(current_price)) - Decimal("4")
        ),  # Stop loss $4 from entry
        take_profit_price=float(
            Decimal(str(current_price)) + Decimal("8")
        ),  # Take profit $8 from entry
        # Order timing
    )


    print("Bracket order placed:")
    print(f"  Entry: {response.entry_order_id}")
    print(f"  Stop Loss: {response.stop_order_id}")
    print(f"  Take Profit: {response.target_order_id}")

    # Monitor bracket order progress
    await monitor_bracket_order(suite, response)


async def monitor_bracket_order(
    suite: TradingSuite, bracket_response: BracketOrderResponse
):
    """Monitor all three orders in a bracket."""

    while True:
        if bracket_response.entry_order_id is None:
            continue
        # Check main order status
        main_status = await suite["MNQ"].orders.get_order_by_id(
            bracket_response.entry_order_id
        )

        print(f"Entry order: {main_status}")

        if main_status == "FILLED":
            print("Entry filled! Monitoring exit orders...")

            # Now monitor the exit orders
            while True:
                if bracket_response.stop_order_id is None:
                    continue
                stop_status = await suite["MNQ"].orders.get_order_by_id(
                    bracket_response.stop_order_id
                )
                if bracket_response.target_order_id is None:
                    continue
                target_status = await suite["MNQ"].orders.get_order_by_id(
                    bracket_response.target_order_id
                )

                if stop_status is None:
                    continue
                if target_status is None:
                    continue
                if stop_status.status == 2:
                    print("Stop loss triggered!")
                    break
                elif target_status.status == 2:
                    print("Take profit hit!")
                    break

                await asyncio.sleep(2)
            break

        elif main_status in ["CANCELLED", "REJECTED"]:
            print(f"Entry order {main_status}")
            break

        await asyncio.sleep(5)


asyncio.run(place_bracket_order())
```

## Order Lifecycle and Tracking

### Real-time Order Status

Track order status changes in real-time using events or polling:

```python
import asyncio
from decimal import Decimal

from project_x_py import EventType, TradingSuite
from project_x_py.event_bus import Event


def on_order_update(event: Event):
    order_data = event.data
    print(f"Order {order_data['order_id']} status: {order_data['status']}")

    if order_data["status"] == "FILLED":
        print(f"  Filled at ${order_data['fill_price']}")
        print(f"  Quantity: {order_data['filled_quantity']}")


async def setup_order_tracking():
    suite = await TradingSuite.create("MNQ")

    # Event-driven tracking (recommended)
    async def on_order_update(event: Event):
        order_data = event.data

        print(order_data)
        print(f"Order {order_data['order_id']} status: {order_data['new_status']}")

        if order_data["status"] == "FILLED":
            print(f"  Filled at ${order_data['filledPrice']}")
            print(f"  Quantity: {order_data['filled_quantity']}")
        if order_data["status"] == "MODIFIED":
            print(f"  Modified at ${order_data['limitPrice']}")
            print(f"  Quantity: {order_data['size']}")

    current_price = await suite["MNQ"].data.get_current_price()
    if current_price:
        limit_price = Decimal(str(current_price)) - Decimal("2.0")
    else:
        return

    # Place an order to demonstrate tracking
    response = await suite["MNQ"].orders.place_limit_order(
        contract_id=suite["MNQ"].instrument_info.id,
        side=0,
        size=1,
        limit_price=float(limit_price),
    )
    print(f"Tracking order: {response.orderId}")

    await suite.on(EventType.ORDER_FILLED, on_order_update)
    await suite.on(EventType.ORDER_MODIFIED, on_order_update)

    # Keep connection alive for events
    await asyncio.sleep(30)


asyncio.run(setup_order_tracking())
```

## Order Modification and Cancellation

### Modifying Orders

```python
import asyncio
from decimal import Decimal

from project_x_py import TradingSuite


async def modify_orders():
    suite = await TradingSuite.create("MNQ")

    # Place initial limit order
    current_price = await suite["MNQ"].data.get_current_price()
    initial_price = Decimal(str(current_price)) - Decimal("50")

    response = await suite["MNQ"].orders.place_limit_order(
        contract_id=suite["MNQ"].instrument_info.id,
        side=0,
        size=1,
        limit_price=float(initial_price),
    )

    order_id = response.orderId
    print(f"Initial order at ${initial_price}")

    # Wait a moment
    await asyncio.sleep(5)

    # Modify the order price (move closer to market)
    new_price = Decimal(str(current_price)) - Decimal("25")

    modify_response = await suite["MNQ"].orders.modify_order(
        order_id=order_id,
        limit_price=float(new_price),
        size=2,  # Also increase size
    )

    print(f"Order modified to ${new_price}, size: 2")

    # Modify only specific fields
    await suite["MNQ"].orders.modify_order(
        order_id=order_id,
        size=3,  # Only change size
    )


asyncio.run(modify_orders())
```

### Cancelling Orders

```python
import asyncio
from decimal import Decimal

from project_x_py import TradingSuite


async def cancel_orders():
    suite = await TradingSuite.create("MNQ")

    # Place multiple orders
    orders: list[int] = []
    current_price = await suite["MNQ"].data.get_current_price()

    for i in range(3):
        price = Decimal(str(current_price)) - Decimal(str(10 * (i + 1)))
        response = await suite["MNQ"].orders.place_limit_order(
            contract_id=suite["MNQ"].instrument_info.id,
            side=0,
            size=1,
            limit_price=float(price),
        )
        orders.append(response.orderId)

    print(f"Placed {len(orders)} orders")

    # Cancel individual order
    await suite["MNQ"].orders.cancel_order(order_id=orders[0])
    print("Cancelled first order")

    # Cancel multiple orders
    for order in orders[1:]:
        await suite["MNQ"].orders.cancel_order(order_id=order)
    print("Cancelled remaining orders")

    # Cancel all open orders (nuclear option)
    await suite["MNQ"].orders.cancel_all_orders(contract_id=suite["MNQ"].instrument_info.id)
    print("All orders cancelled")


asyncio.run(cancel_orders())
```

## Error Handling and Recovery

### Comprehensive Error Handling

```python
import asyncio
from decimal import Decimal

from project_x_py import TradingSuite
from project_x_py.exceptions import (
    ProjectXOrderError,
    ProjectXPositionError,
    ProjectXRateLimitError,
)


async def robust_order_placement():
    suite = await TradingSuite.create("MNQ")

    try:
        response = await suite["MNQ"].orders.place_bracket_order(
            contract_id=suite["MNQ"].instrument_info.id,
            side=0,
            size=1,
            entry_price=None,
            entry_type="market",
            stop_loss_price=float(Decimal("50")),
            take_profit_price=float(Decimal("100")),
        )

        print(f"Order 1 placed successfully: {response.entry_order_id}")

        # This will raise an error because if the entry_price is None, the entry_type must be "market"
        response = await suite["MNQ"].orders.place_bracket_order(
            contract_id=suite["MNQ"].instrument_info.id,
            side=1,
            size=1,
            entry_price=None,
            stop_loss_price=float(Decimal("50")),
            take_profit_price=float(Decimal("100")),
        )

    except ProjectXPositionError as e:
        print(f"Insufficient margin: {e}")
        # Reduce position size or add funds

    except ProjectXOrderError as e:
        print(f"Order error: {e}")
        if "invalid price" in str(e).lower():
            # Price alignment issue - check tick size
            instrument = suite["MNQ"].instrument_info
            print(f"Tick size: {instrument.tickSize}")

    except ProjectXRateLimitError as e:
        print(f"Rate limited: {e}")
        # Wait and retry
        await asyncio.sleep(1)
        # Retry logic here...

    except Exception as e:
        print(f"Unexpected error: {e}")

asyncio.run(robust_order_placement())
```

## Performance Optimization

### Concurrent Order Operations

```python
async def concurrent_operations():
    suite = await TradingSuite.create("MNQ")

    current_price = await suite.data.get_current_price()

    # Place multiple orders concurrently
    tasks = []

    for i in range(5):
        price = Decimal(str(current_price)) - Decimal(str(10 * (i + 1)))

        task = suite.orders.place_limit_order(
            "MNQ", 0, 1, price, time_in_force="DAY"
        )
        tasks.append(task)

    # Execute all orders concurrently
    responses = await asyncio.gather(*tasks, return_exceptions=True)

    successful_orders = []
    for i, response in enumerate(responses):
        if isinstance(response, Exception):
            print(f"Order {i} failed: {response}")
        else:
            successful_orders.append(response.order_id)
            print(f"Order {i} placed: {response.order_id}")

    print(f"Successfully placed {len(successful_orders)} orders")

    # Monitor all orders concurrently
    status_tasks = [
        suite.orders.get_order_status(order_id)
        for order_id in successful_orders
    ]

    statuses = await asyncio.gather(*status_tasks)
    for order_id, status in zip(successful_orders, statuses):
        print(f"Order {order_id}: {status}")
```

### Batch Operations

```python
async def batch_operations():
    suite = await TradingSuite.create("MNQ")

    # Batch cancel multiple orders
    order_ids = ["order1", "order2", "order3"]  # Your order IDs

    results = await suite.orders.batch_cancel_orders(order_ids)

    for order_id, result in results.items():
        if result["success"]:
            print(f"Cancelled {order_id}")
        else:
            print(f"Failed to cancel {order_id}: {result['error']}")

    # Batch status check
    statuses = await suite.orders.batch_get_status(order_ids)

    for order_id, status in statuses.items():
        print(f"Order {order_id}: {status}")
```

## Best Practices

### 1. Order Size and Risk Management

```python
# Always calculate position sizes based on risk
async def calculate_position_size(suite, entry_price, stop_price, risk_percent=0.01):
    """Calculate position size based on risk tolerance."""

    account_info = suite.client.account_info
    risk_amount = account_info.balance * Decimal(str(risk_percent))

    price_risk = abs(entry_price - stop_price)

    # Account for contract multiplier
    instrument = await suite.client.get_instrument("MNQ")
    multiplier = instrument.contractSize or Decimal("20")  # MNQ multiplier

    position_size = int(risk_amount / (price_risk * multiplier))

    return max(1, position_size)  # Minimum 1 contract
```

### 2. Price Precision

```python
# Always use Decimal for price calculations
from decimal import Decimal, ROUND_HALF_UP

async def align_to_tick_size(price: Decimal, tick_size: Decimal) -> Decimal:
    """Align price to instrument tick size."""

    return (price / tick_size).quantize(
        Decimal('1'), rounding=ROUND_HALF_UP
    ) * tick_size

# Usage
current_price = await suite.data.get_current_price()
instrument = await suite.client.get_instrument("MNQ")

entry_price = Decimal(str(current_price)) - Decimal("25")
aligned_price = await align_to_tick_size(
    entry_price,
    Decimal(str(instrument.tickSize))
)
```

### 3. Order Validation

```python
async def validate_order_before_placement(suite, contract_id, side, size, price=None):
    """Validate order parameters before placement."""

    # Check account margin
    account_info = suite.client.account_info

    # Get instrument info
    instrument = await suite.client.get_instrument(contract_id)

    # Validate size
    if size <= 0:
        raise ValueError("Order size must be positive")

    # Validate price alignment
    if price:
        tick_size = Decimal(str(instrument.tickSize))
        if price % tick_size != 0:
            raise ValueError(f"Price {price} not aligned to tick size {tick_size}")

    # Check position limits (if risk manager enabled)
    if hasattr(suite, 'risk_manager') and suite.risk_manager:
        current_position = await suite.positions.get_position(contract_id)
        new_size = (current_position.size if current_position else 0)

        if side == 0:  # Buy
            new_size += size
        else:  # Sell
            new_size -= size

        # Check if new position exceeds limits
        max_position = 10  # Your risk limit
        if abs(new_size) > max_position:
            raise ValueError(f"New position {new_size} exceeds limit {max_position}")

    return True
```

### 4. Event-Driven Order Management

```python
class OrderEventHandler:
    def __init__(self, suite):
        self.suite = suite
        self.active_orders = {}

    async def setup_event_handlers(self):
        """Setup comprehensive order event handling."""

        await self.suite.on(EventType.ORDER_PLACED, self.on_order_placed)
        await self.suite.on(EventType.ORDER_FILLED, self.on_order_filled)
        await self.suite.on(EventType.ORDER_CANCELLED, self.on_order_cancelled)
        await self.suite.on(EventType.ORDER_REJECTED, self.on_order_rejected)

    async def on_order_placed(self, event):
        """Handle order placement confirmation."""
        order_data = event.data
        self.active_orders[order_data['order_id']] = order_data
        print(f" Order placed: {order_data['order_id']}")

    async def on_order_filled(self, event):
        """Handle order fills."""
        order_data = event.data
        order_id = order_data['order_id']

        print(f"< Order filled: {order_id}")
        print(f"   Price: ${order_data['fill_price']}")
        print(f"   Quantity: {order_data['filled_quantity']}")

        # Remove from active orders
        if order_id in self.active_orders:
            del self.active_orders[order_id]

        # Handle bracket order logic
        if 'bracket_group_id' in order_data:
            await self.handle_bracket_fill(order_data)

    async def handle_bracket_fill(self, order_data):
        """Handle bracket order fills specially."""
        group_id = order_data['bracket_group_id']

        if order_data['order_type'] == 'entry':
            print(f"Bracket entry filled - monitoring exits for group {group_id}")
        elif order_data['order_type'] in ['stop', 'target']:
            print(f"Bracket exit filled - group {group_id} complete")
            # Cancel remaining exit order if needed

# Usage
async def run_with_event_handling():
    suite = await TradingSuite.create("MNQ")

    handler = OrderEventHandler(suite)
    await handler.setup_event_handlers()

    # Your trading logic here...
    response = await suite.orders.place_bracket_order(
        "MNQ", 0, 1,
        stop_offset=Decimal("50"),
        target_offset=Decimal("100")
    )

    # Events will be handled automatically
    await asyncio.sleep(60)  # Keep running for events
```

## Integration with Risk Management

When the RiskManager feature is enabled, order placement is automatically validated:

```python
async def risk_managed_trading():
    # Enable risk management
    suite = await TradingSuite.create("MNQ", features=["risk_manager"])

    # Risk manager validates all orders automatically
    try:
        response = await suite.orders.place_bracket_order(
            contract_id="MNQ",
            side=0, size=5,  # Large size
            stop_offset=Decimal("25"),
            target_offset=Decimal("75")
        )

    except ProjectXRiskViolationError as e:
        print(f"Risk check failed: {e}")
        # Order was rejected due to risk limits

    # Set custom risk parameters
    await suite.risk_manager.set_position_limit("MNQ", max_contracts=3)
    await suite.risk_manager.set_daily_loss_limit(Decimal("1000"))

    # Now retry with smaller size
    response = await suite.orders.place_bracket_order(
        contract_id="MNQ",
        side=0, size=2,  # Safer size
        stop_offset=Decimal("50"),
        target_offset=Decimal("100")
    )
```

## Summary

The ProjectX OrderManager provides comprehensive order management capabilities:

- **Multiple order types** with full async support
- **Real-time tracking** via WebSocket events
- **Error recovery** with automatic retry logic
- **Price precision** handling with tick alignment
- **Risk integration** when RiskManager is enabled
- **Concurrent operations** for high-performance trading
- **Event-driven architecture** for responsive applications

All order operations are designed for production trading environments with proper error handling, logging, and performance optimization. Always test thoroughly with small positions before deploying live trading strategies.

---

**Next**: [Position Management Guide](positions.md) | **Previous**: [Trading Suite Guide](trading-suite.md)
