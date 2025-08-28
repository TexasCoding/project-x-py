# Order Manager Test Fixes Required

## Executive Summary
Current Status: **266 passing / 30 failing** tests in order_manager module (89.9% pass rate)

Initial Status: 221 passing / 75 failing (74.7% pass rate)
Progress Made: 45 test failures fixed (60% improvement)

## Completed Fixes ✅

### 1. Authentication Issues
- Created `conftest_mock.py` with properly mocked OrderManager fixture
- Fixed context manager issues with patches
- Added all required async mocks for client methods

### 2. Code Quality Issues
- Removed trailing whitespace in `core.py` and `tracking.py`
- Fixed import paths and references

### 3. Test Assertion Fixes
- Fixed OCO order ID types (string "oco_1" → numeric "1001")
- Updated position order assertions to use positional arguments instead of keyword arguments
- Fixed cleanup task method name (`_cleanup_old_orders` → `_cleanup_completed_orders`)
- Updated rejection tracking initialization

## Remaining Test Failures (30 tests)

### Category 1: Position Order Implementation Gaps (20 failures)

#### 1.1 Missing/Incorrect Method Signatures
**Location:** `src/project_x_py/order_manager/position_orders.py`

- **`test_close_position_flat_position`**
  - Issue: Method doesn't validate if position size is 0
  - Expected: Should raise ProjectXOrderError for flat positions
  - Actual: Attempts to place order with size=0

- **`test_close_position_with_invalid_method`**
  - Issue: No validation for invalid close methods
  - Expected: Should raise ProjectXOrderError for invalid method
  - Actual: Falls through without error

- **`test_add_stop_loss_no_position`**
  - Issue: Returns None instead of raising exception
  - Expected: ProjectXOrderError when no position exists
  - Actual: Returns None silently

- **`test_add_stop_loss_invalid_price_long`**
  - Issue: No price validation for stop orders
  - Expected: Validate stop price is below entry for long positions
  - Actual: No validation performed

- **`test_add_take_profit_invalid_price_long`**
  - Issue: No price validation for take profit orders
  - Expected: Validate target price is above entry for long positions
  - Actual: No validation performed

#### 1.2 Position Order Tracking Methods
**Issue:** Methods don't exist or have different signatures

- **`track_order_for_position`**
  - Test expects: `track_order_for_position(contract_id, order_id, order_type, meta={})`
  - Actual: Method may not exist or has different signature

- **`get_position_orders`**
  - Test expects: Returns dict of orders, supports filtering by type/status
  - Actual: Returns different structure or doesn't exist

- **`cancel_position_orders`**
  - Test expects: Returns list of cancelled order IDs
  - Actual: Returns dict with different structure

- **`update_position_order_sizes`**
  - Test expects: Returns list of updated order IDs
  - Actual: Returns dict with different structure

- **`sync_orders_with_position`**
  - Test expects: `sync_orders_with_position(contract_id, target_size, cancel_orphaned=True)`
  - Actual: Missing required positional argument or different signature

#### 1.3 Event Handler Methods
**Issue:** Event handlers have incorrect signatures

- **`on_position_changed`**
  - Test expects: `on_position_changed(event)` where event is a dict
  - Actual: Missing required positional arguments `old_size` and `new_size`

- **`on_position_closed`**
  - Test expects: `on_position_closed(event)` where event is dict with `contract_id`
  - Actual: TypeError - unhashable type: 'dict'

### Category 2: Core Module Issues (8 failures)

#### 2.1 Order Modification
**Location:** `src/project_x_py/order_manager/core.py`

- **`test_modify_order_no_changes`**
  - Issue: Method doesn't handle case where no modifications are provided
  - Expected: Should handle gracefully or raise appropriate error
  - Actual: Unknown behavior

#### 2.2 Price Alignment
- **`test_place_order_aligns_all_price_types`**
  - Issue: Price alignment not working for all order types
  - Expected: All price types should be aligned to tick size
  - Actual: Some price types not aligned

#### 2.3 Concurrency
- **`test_order_lock_prevents_race_conditions`**
  - Issue: Order lock mechanism not preventing race conditions
  - Expected: Concurrent operations should be serialized
  - Actual: Race conditions still possible

#### 2.4 Statistics
- **`test_statistics_update_on_order_lifecycle`**
  - Issue: Statistics not updating properly through order lifecycle
  - Expected: Stats should update at each state change
  - Actual: Missing updates or incorrect counts

#### 2.5 Error Recovery
- **`test_recovery_manager_handles_partial_failures`**
  - Issue: Recovery manager not handling partial failures correctly
  - Expected: Should recover from partial failures
  - Actual: Complete failure or incorrect recovery

#### 2.6 Memory Management
- **`test_cleanup_task_starts_on_initialize`**
  - Issue: Cleanup task initialization issue
  - Expected: Should start cleanup task on initialization
  - Actual: Task not starting or incorrect initialization

#### 2.7 Account Handling
- **`test_place_order_with_invalid_account_id`**
  - Issue: Invalid account IDs not validated
  - Expected: Should validate account ID
  - Actual: No validation

- **`test_search_orders_uses_correct_account`**
  - Issue: Account ID not being used correctly in search
  - Expected: Should filter by account ID
  - Actual: Not filtering or using wrong account

### Category 3: Real-time Tracking (2 failures)

#### 3.1 Callback Setup
**Location:** `src/project_x_py/order_manager/tracking.py`

- **`test_setup_realtime_callbacks`**
  - Issue: Real-time callbacks not being set up correctly
  - Expected: Should register callbacks with realtime client
  - Actual: Callbacks not registered or incorrect registration

#### 3.2 Network Failures
- **`test_order_tracking_with_network_failures`**
  - Issue: Network failures not handled gracefully
  - Expected: Should handle network failures and recover
  - Actual: Crashes or doesn't recover

## Recommended Fix Priority

### High Priority (Core Functionality)
1. Fix position validation in `close_position` (check size != 0)
2. Add method validation in `close_position`
3. Fix return values vs exceptions for no-position cases
4. Add price validation for stop loss and take profit orders

### Medium Priority (Tracking & Sync)
1. Implement/fix `track_order_for_position` method
2. Fix `get_position_orders` return structure
3. Fix `cancel_position_orders` return structure
4. Implement proper `sync_orders_with_position` signature

### Low Priority (Event Handlers & Edge Cases)
1. Fix event handler signatures
2. Implement network failure recovery
3. Add account ID validation

## Implementation Guide

### Fix 1: Position Validation
```python
# In position_orders.py - close_position method
if not position or position.size == 0:
    raise ProjectXOrderError(f"No open position found for {contract_id}")

if method not in ["market", "limit"]:
    raise ProjectXOrderError(f"Invalid close method: {method}")
```

### Fix 2: Price Validation
```python
# In position_orders.py - add_stop_loss method
if position.type == PositionType.LONG and stop_price >= position.averagePrice:
    raise ProjectXOrderError("Stop price must be below entry for long position")
elif position.type == PositionType.SHORT and stop_price <= position.averagePrice:
    raise ProjectXOrderError("Stop price must be above entry for short position")
```

### Fix 3: Method Return Types
```python
# Ensure consistent return types
def cancel_position_orders(self, contract_id, order_types=None):
    # Should return list of cancelled order IDs, not dict
    return cancelled_order_ids  # ["1001", "1002", ...]
```

### Fix 4: Event Handler Signatures
```python
# Fix event handler to accept dict
async def on_position_changed(self, event: dict):
    contract_id = event.get("contract_id")
    old_size = event.get("old_size")
    new_size = event.get("new_size")
    # Process event...
```

## Testing Commands

```bash
# Run all order manager tests
uv run pytest tests/order_manager/ -v

# Run only failing tests
uv run pytest tests/order_manager/test_position_orders_advanced.py -v
uv run pytest tests/order_manager/test_core_advanced.py -v
uv run pytest tests/order_manager/test_tracking_advanced.py -v

# Run with coverage
uv run pytest tests/order_manager/ --cov=src/project_x_py/order_manager --cov-report=html
```

## Success Criteria
- [ ] All 296 tests passing (100% pass rate)
- [ ] No IDE diagnostic warnings in order_manager module
- [ ] Consistent return types across all methods
- [ ] Proper exception handling for edge cases
- [ ] Complete test coverage for critical paths

## Notes
- Many failures are due to unimplemented or partially implemented features
- Test expectations follow TDD principles - implementation should match tests
- Some design decisions (returning None vs raising exceptions) may need team discussion
- Consider adding integration tests for real-time features once unit tests pass
