# Order Manager API

Comprehensive async order management with support for market, limit, stop, and bracket orders, plus advanced order lifecycle tracking.

## Overview

The OrderManager provides comprehensive order placement, modification, and tracking capabilities with full async support. It handles complex order types including bracket orders, OCO (One Cancels Other) orders, and position-based orders.


## Quick Start

```python
from project_x_py import TradingSuite

async def basic_order_management():
    suite = await TradingSuite.create(["MNQ"])
    mnq_context = suite["MNQ"]

    # Access the integrated order manager
    orders = mnq_context.orders

    # Place a simple market order
    response = await orders.place_market_order(
        contract_id=mnq_context.instrument_info.id,
        side=0,  # Buy
        size=1
    )

    print(f"Order placed: {response.orderId}")
    await suite.disconnect()
```

## Order Types

### Market Orders

```python
async def market_orders():
    suite = await TradingSuite.create(["MNQ"])
    mnq_orders = suite["MNQ"].orders
    mnq_instrument_id = suite["MNQ"].instrument_info.id

    # Simple market order
    buy_order = await mnq_orders.place_market_order(
        contract_id=mnq_instrument_id,
        side=0,  # Buy
        size=1
    )

    sell_order = await mnq_orders.place_market_order(
        contract_id=mnq_instrument_id,
        side=1,  # Sell
        size=2,
    )

    await suite.disconnect()
```

### Limit Orders

```python
async def limit_orders():
    suite = await TradingSuite.create(["MNQ"])
    mnq_orders = suite["MNQ"].orders
    mnq_instrument_id = suite["MNQ"].instrument_info.id

    # Buy limit order
    buy_limit = await mnq_orders.place_limit_order(
        contract_id=mnq_instrument_id,
        side=0,  # Buy
        size=1,
        limit_price=21000.0
    )

    # Sell limit order with time in force
    sell_limit = await mnq_orders.place_limit_order(
        contract_id=mnq_instrument_id,
        side=1,  # Sell
        size=1,
        limit_price=21100.0,
        time_in_force="GTC"  # Good Till Cancelled
    )

    await suite.disconnect()
```

### Stop Orders

```python
async def stop_orders():
    suite = await TradingSuite.create(["MNQ"])
    mnq_orders = suite["MNQ"].orders
    mnq_instrument_id = suite["MNQ"].instrument_info.id

    # Stop loss order
    stop_loss = await mnq_orders.place_stop_order(
        contract_id=mnq_instrument_id,
        side=1,  # Sell (to close long position)
        size=1,
        stop_price=20950.0
    )

    # Stop limit order
    stop_limit = await mnq_orders.place_stop_limit_order(
        contract_id=mnq_instrument_id,
        side=1,  # Sell
        size=1,
        stop_price=20950.0,
        limit_price=20940.0  # Limit price after stop triggered
    )

    await suite.disconnect()
```

## Advanced Order Types

### Bracket Orders


```python
async def bracket_orders():
    suite = await TradingSuite.create(["MNQ"])
    mnq_orders = suite["MNQ"].orders
    mnq_instrument_id = suite["MNQ"].instrument_info.id

    # Complete bracket order with stop and target
    bracket_result = await mnq_orders.place_bracket_order(
        contract_id=mnq_instrument_id,
        side=0,  # Buy
        size=1,
        entry_price=21050.0,    # Entry limit price
        stop_offset=25.0,       # $25 stop loss
        target_offset=50.0      # $50 profit target
    )

    print(f"Main Order: {bracket_result.main_order_id}")
    print(f"Stop Loss: {bracket_result.stop_order_id}")
    print(f"Take Profit: {bracket_result.target_order_id}")

    # Market bracket order (immediate entry)
    market_bracket = await mnq_orders.place_bracket_order(
        contract_id=mnq_instrument_id,
        side=0,  # Buy
        size=1,
        entry_price=None,       # Market entry
        stop_offset=30.0,
        target_offset=60.0
    )

    await suite.disconnect()
```

### OCO (One Cancels Other) Orders

```python
async def oco_orders():
    suite = await TradingSuite.create(["MNQ"])
    mnq_orders = suite["MNQ"].orders
    mnq_instrument_id = suite["MNQ"].instrument_info.id

    # OCO order: Either stop loss OR take profit
    oco_result = await mnq_orders.place_oco_order(
        contract_id=mnq_instrument_id,
        size=1,
        first_order={
            "type": "limit",
            "side": 1,  # Sell
            "price": 21100.0  # Take profit
        },
        second_order={
            "type": "stop",
            "side": 1,  # Sell
            "stop_price": 20950.0  # Stop loss
        }
    )

    await suite.disconnect()
```

### Position-Based Orders


```python
async def position_based_orders():
    suite = await TradingSuite.create(["MNQ"])
    mnq_orders = suite["MNQ"].orders

    # Close entire position
    close_result = await mnq_orders.close_position(
        instrument="MNQ",
        method="market"  # or "limit"
    )

    # Reduce position by 50%
    reduce_result = await mnq_orders.reduce_position(
        instrument="MNQ",
        percentage=0.5,  # Reduce by 50%
        method="limit",
        limit_price=21075.0
    )

    # Scale out of position in stages
    scale_result = await mnq_orders.scale_out_position(
        instrument="MNQ",
        levels=[
            {"percentage": 0.33, "price": 21060.0},  # Take 1/3 at 21060
            {"percentage": 0.33, "price": 21080.0},  # Take 1/3 at 21080
            {"percentage": 0.34, "price": 21100.0}   # Take remaining at 21100
        ]
    )

    await suite.disconnect()
```

## Order Modification & Management

### Modify Orders

```python
async def modify_orders():
    suite = await TradingSuite.create(["MNQ"])
    mnq_orders = suite["MNQ"].orders
    mnq_instrument_id = suite["MNQ"].instrument_info.id

    # Place initial order
    order = await mnq_orders.place_limit_order(
        contract_id=mnq_instrument_id,
        side=0,
        size=1,
        limit_price=21000.0
    )

    # Modify price
    modified = await mnq_orders.modify_order(
        order_id=order.order_id,
        limit_price=21010.0  # New price
    )

    # Modify quantity
    modified_qty = await mnq_orders.modify_order(
        order_id=order.order_id,
        size=2  # Increase size
    )

    await suite.disconnect()
```

### Cancel Orders

```python
async def cancel_orders():
    suite = await TradingSuite.create(["MNQ"])
    mnq_orders = suite["MNQ"].orders
    mnq_instrument_id = suite["MNQ"].instrument_info.id

    # Place some orders
    order1 = await mnq_orders.place_limit_order(
        contract_id=mnq_instrument_id,
        side=0, size=1, limit_price=21000.0
    )
    order2 = await mnq_orders.place_limit_order(
        contract_id=mnq_instrument_id,
        side=0, size=1, limit_price=21010.0
    )

    # Cancel single order
    await mnq_orders.cancel_order(order1.order_id)

    # Cancel multiple orders
    await mnq_orders.cancel_orders([order1.order_id, order2.order_id])

    # Cancel all orders for instrument
    await mnq_orders.cancel_all_orders(instrument="MNQ")

    # Cancel all orders (all instruments)
    await suite.orders.cancel_all_orders()

    await suite.disconnect()
```

## Order Tracking & Status

### Order Status Monitoring

```python
async def order_status():
    suite = await TradingSuite.create(["MNQ"])
    mnq_orders = suite["MNQ"].orders
    mnq_instrument_id = suite["MNQ"].instrument_info.id

    # Place order
    order = await mnq_orders.place_limit_order(
        contract_id=mnq_instrument_id,
        side=0, size=1, limit_price=21000.0
    )

    # Get order status
    status = await mnq_orders.get_order_status(order.order_id)
    print(f"Order Status: {status.status}")
    print(f"Filled Quantity: {status.filled_quantity}")
    print(f"Remaining: {status.remaining_quantity}")

    # Get detailed order info
    order_info = await mnq_orders.get_order(order.order_id)

    # Wait for fill
    filled_order = await mnq_orders.wait_for_fill(
        order.order_id,
        timeout=60.0
    )

    await suite.disconnect()
```

### Order History

```python
async def order_history():
    suite = await TradingSuite.create(["MNQ"])
    mnq_orders = suite["MNQ"].orders

    # Get all orders
    all_orders = await mnq_orders.get_orders()

    # Get orders by status
    pending_orders = await mnq_orders.get_orders(status="pending")
    filled_orders = await mnq_orders.get_orders(status="filled")

    # Get orders by instrument
    mnq_orders_filtered = await mnq_orders.get_orders(instrument="MNQ")

    # Get recent orders
    recent_orders = await mnq_orders.get_recent_orders(limit=10)

    await suite.disconnect()
```

## Order Lifecycle Tracking


```python
async def order_lifecycle():
    suite = await TradingSuite.create(["MNQ"])
    mnq_context = suite["MNQ"]

    # Track order lifecycle with events
    async def on_order_update(event):
        print(f"Order {event.order_id} status: {event.status}")

    async def on_order_filled(event):
        print(f"Order {event.order_id} filled at {event.fill_price}")

    # Register event handlers
    await mnq_context.orders.on_order_update(on_order_update)
    await mnq_context.orders.on_order_filled(on_order_filled)

    # Place order with tracking
    order = await mnq_context.orders.place_limit_order(
        contract_id=mnq_context.instrument_info.id,
        side=0, size=1, limit_price=21000.0
    )

    # Wait for events
    await asyncio.sleep(60)
    await suite.disconnect()
```

## Order Templates & Strategies

### Order Templates


```python
from project_x_py.order_templates import get_template

async def order_templates():
    suite = await TradingSuite.create(["MNQ"])
    mnq_context = suite["MNQ"]

    # Use predefined templates
    scalping_template = get_template("scalping")
    breakout_template = get_template("breakout")
    risk_reward_template = get_template("risk_reward")

    # Apply scalping template
    scalp_order = await scalping_template.create_order(
        context=mnq_context,
        side=0,  # Buy
        current_price=21050.0,
        atr_value=15.0
    )

    # Apply breakout template
    breakout_order = await breakout_template.create_order(
        context=mnq_context,
        side=0,  # Buy
        breakout_price=21075.0,
        support_level=21000.0,
        resistance_level=21150.0
    )

    await suite.disconnect()
```

### Custom Templates

```python
from project_x_py.order_templates import OrderTemplate

class CustomTemplate(OrderTemplate):
    """Custom order template for specific strategy."""

    async def create_order(self, context, side, **kwargs):
        # Custom logic here
        entry_price = kwargs.get('entry_price')
        risk_amount = kwargs.get('risk_amount', 100.0)

        # Calculate position size based on risk
        stop_distance = kwargs.get('stop_distance', 25.0)
        position_size = risk_amount / stop_distance

        # Place bracket order
        return await context.orders.place_bracket_order(
            contract_id=context.instrument_info.id,
            side=side,
            size=int(position_size),
            entry_price=entry_price,
            stop_offset=stop_distance,
            target_offset=stop_distance * 2  # 1:2 RR
        )

async def custom_template():
    suite = await TradingSuite.create(["MNQ"])
    mnq_context = suite["MNQ"]
    template = CustomTemplate()

    order = await template.create_order(
        context=mnq_context,
        side=0,
        entry_price=21050.0,
        risk_amount=200.0,
        stop_distance=30.0
    )

    await suite.disconnect()
```

## Error Recovery


```python
async def error_recovery():
    suite = await TradingSuite.create(["MNQ"])
    mnq_orders = suite["MNQ"].orders
    mnq_instrument_id = suite["MNQ"].instrument_info.id

    try:
        # Attempt order placement
        order = await mnq_orders.place_limit_order(
            contract_id=mnq_instrument_id,
            side=0, size=1, limit_price=21000.0
        )
    except InsufficientMarginError:
        print("Insufficient margin - reducing position size")
        # Retry with smaller size
        order = await mnq_orders.place_limit_order(
            contract_id=mnq_instrument_id,
            side=0, size=0.5, limit_price=21000.0
        )
    except OrderRejectedError as e:
        print(f"Order rejected: {e}")
        # Handle rejection (adjust price, etc.)

    await suite.disconnect()
```

## Order Statistics

```python
async def order_statistics():
    suite = await TradingSuite.create(["MNQ"])
    mnq_orders = suite["MNQ"].orders

    # Get order manager statistics
    stats = await mnq_orders.get_stats()

    print(f"Total Orders: {stats['total_orders']}")
    print(f"Fill Rate: {stats['fill_rate']:.1%}")
    print(f"Average Fill Time: {stats['avg_fill_time_ms']:.0f}ms")
    print(f"Rejected Orders: {stats['rejected_orders']}")
    print(f"Error Rate: {stats['error_rate']:.1%}")

    # Performance metrics
    performance = stats.get('performance_metrics', {})
    print(f"Orders per Second: {performance.get('orders_per_second', 0):.1f}")
    print(f"Average Response Time: {performance.get('avg_response_time_ms', 0):.0f}ms")

    await suite.disconnect()
```

## Configuration

### OrderManagerConfig


```python
from project_x_py.types import OrderManagerConfig

async def configure_order_manager():
    # Custom order manager configuration
    order_config = OrderManagerConfig(
        max_concurrent_orders=10,      # Max simultaneous orders
        default_timeout=30.0,          # Default timeout in seconds
        retry_attempts=3,              # Retry attempts on failure
        enable_order_tracking=True,    # Enable lifecycle tracking
        track_performance=True,        # Track performance metrics
        auto_cancel_on_disconnect=True # Cancel orders on disconnect
    )

    suite = await TradingSuite.create(
        ["MNQ"],
        order_manager_config=order_config
    )

    await suite.disconnect()
```

## Best Practices

### Order Placement

```python
# Good: Use proper error handling
try:
    suite = await TradingSuite.create(["MNQ"])
    mnq_context = suite["MNQ"]
    order = await mnq_context.orders.place_limit_order(
        contract_id=mnq_context.instrument_info.id,
        side=0, size=1, limit_price=21000.0
    )
except ProjectXOrderError as e:
    print(f"Order failed: {e}")

# Good: Validate parameters
if suite["MNQ"].instrument_info.min_tick_size:
    # Round price to tick size
    rounded_price = round_to_tick_size(price, suite["MNQ"].instrument_info.min_tick_size)

# Good: Use bracket orders for risk management
bracket_order = await suite["MNQ"].orders.place_bracket_order(
    contract_id=suite["MNQ"].instrument_info.id,
    side=0, size=1,
    entry_price=21050.0,
    stop_offset=25.0,    # Risk management
    target_offset=50.0   # Profit target
)
```

### Resource Management

```python
# Good: Cancel orders on shutdown
async def cleanup_orders(suite):
    try:
        # Cancel pending orders
        await suite["MNQ"].orders.cancel_all_orders()
    except Exception as e:
        print(f"Cleanup failed: {e}")
    finally:
        await suite.disconnect()

# Good: Monitor order limits
stats = await suite["MNQ"].orders.get_stats()
if stats['pending_orders'] > 50:
    print("Warning: High number of pending orders")
```

## See Also

- [Trading Suite API](trading-suite.md) - Main trading interface
- [Position Manager API](position-manager.md) - Position management
- [Order Management Guide](../guide/orders.md) - Detailed usage guide
- [Risk Management Guide](../guide/risk.md) - Risk management concepts
