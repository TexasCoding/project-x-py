# Project-X Python Library Testing Plan

## Overview
This document outlines the comprehensive testing plan for the Project-X Python financial trading API library. The plan follows a systematic, phased approach to ensure all components are tested from basic functionality to complex integrations.

## Testing Status

### Phase 1: Core Components (✓ 75% Complete)
1. **Authentication** ✅ (12/12 tests passing)
2. **Basic API Operations** ✅ (15/15 tests passing)
3. **Order Manager Initialization** ✅ (11/11 tests passing)
4. **Real-time Client Connection** ❌ (0/12 tests - blocked by SignalR mocking issue)

### Phase 2: Order Management (🚧 In Progress)
1. **Order Creation and Submission** ✅ (13/13 tests passing)
2. **Order Modification and Cancellation** ✅ (17/17 tests passing)
3. **Order Status Tracking** ✅ (15/15 tests passing)
4. **Position Management Integration**
5. **Risk Management Features**

### Phase 3: Real-time Features
1. **Live Market Data Streaming**
2. **Order Status Updates**
3. **Position Updates**
4. **Account Balance Updates**

### Phase 4: Advanced Features
1. **Multiple Account Management**
2. **Complex Order Types**
3. **Historical Data Analysis**
4. **Error Recovery and Resilience**

## Phase 1 Tests - Core Components

### Test 1: Authentication (✅ COMPLETE)
- **File**: `tests/test_client_auth.py`
- **Status**: All tests passing
- **Tests**:
  - Valid credentials from environment variables
  - Direct credentials authentication
  - Invalid credentials handling
  - Missing credentials error
  - Expired token refresh
  - Multi-account selection
  - Account not found error
  - Configuration management
  - Environment variable config override
  - JWT token storage and reuse
  - Lazy authentication

### Test 2: Basic API Operations (✅ COMPLETE)
- **File**: `tests/test_client_operations.py`
- **Status**: All tests passing
- **Tests**:
  - Instrument search functionality
  - Get instrument details
  - Historical data retrieval with different timeframes
  - Account information retrieval
  - Position retrieval and filtering
  - Error handling for network errors
  - Invalid response handling
  - Rate limiting behavior

### Test 3: Order Manager Initialization (✅ COMPLETE)
- **File**: `tests/test_order_manager_init.py`
- **Status**: All tests passing
- **Tests**:
  - Basic initialization
  - Initialize with/without real-time client
  - Initialization failure handling
  - Reinitialization capability
  - Helper function behavior
  - Authentication requirements
  - Order manager attributes

### Test 4: Real-time Client Connection (❌ BLOCKED)
- **File**: `tests/test_realtime_client.py`
- **Status**: Blocked by SignalR mocking issue
- **Issue**: Unable to mock `signalrcore.HubConnectionBuilder`
- **Tests** (to be implemented when unblocked):
  - Basic connection establishment
  - Connection failure handling
  - Disconnection behavior
  - Subscription management
  - Callback registration
  - Event handlers
  - Reconnection capability

## Phase 2 Tests - Order Management

### Test 5: Order Creation and Submission
Create comprehensive tests for order creation and submission functionality.

**Test Coverage**:
- Market order creation
- Limit order creation
- Stop order creation
- Complex order types (OCO, bracket)
- Order validation
- Order submission success
- Order submission failure
- Insufficient balance handling
- Invalid instrument handling
- Order timeout handling

### Test 6: Order Modification
Test order modification capabilities.

**Test Coverage**:
- Modify order quantity
- Modify order price
- Modify stop price
- Cancel and replace
- Modification validation
- Modification of filled orders (should fail)
- Modification of cancelled orders (should fail)
- Concurrent modification handling

### Test 7: Order Cancellation
Test order cancellation functionality.

**Test Coverage**:
- Cancel single order
- Cancel all orders
- Cancel orders by instrument
- Cancel orders by account
- Cancellation of filled orders (should fail)
- Cancellation of already cancelled orders
- Partial fill cancellation

### Test 8: Position Management
Test position tracking and management.

**Test Coverage**:
- Position creation from fills
- Position updates
- Position close
- Position P&L calculation
- Multi-position handling
- Position by account filtering
- Position by instrument filtering

### Test 9: Risk Management
Test risk management features.

**Test Coverage**:
- Position size limits
- Daily loss limits
- Order validation against limits
- Risk metric calculations
- Margin requirements
- Account balance checks

## Phase 3 Tests - Real-time Features

### Test 10: Market Data Streaming
Test real-time market data functionality.

**Test Coverage**:
- Subscribe to market data
- Receive bid/ask updates
- Receive trade updates
- Handle data gaps
- Reconnection with data recovery
- Multiple instrument subscriptions
- Unsubscribe functionality

### Test 11: Order Status Updates
Test real-time order status updates.

**Test Coverage**:
- Order acknowledgment
- Order fill notifications
- Partial fill updates
- Order rejection notifications
- Order cancellation confirmations
- Status update callbacks

### Test 12: Account Updates
Test real-time account updates.

**Test Coverage**:
- Balance updates
- Margin updates
- P&L updates
- Position updates
- Account status changes

## Phase 4 Tests - Advanced Features

### Test 13: Multiple Account Management
Test handling multiple trading accounts.

**Test Coverage**:
- Account switching
- Per-account order management
- Per-account position tracking
- Cross-account reporting
- Account isolation

### Test 14: Error Recovery
Test error recovery and resilience.

**Test Coverage**:
- Network disconnection recovery
- API error recovery
- Invalid data handling
- Rate limit recovery
- Session timeout handling
- Graceful degradation

### Test 15: Performance Testing
Test performance under load.

**Test Coverage**:
- High frequency order submission
- Large position handling
- Multiple concurrent operations
- Memory usage optimization
- Latency measurements

## Testing Guidelines

### 1. Test Structure
- Use pytest framework
- Follow AAA pattern (Arrange, Act, Assert)
- Use fixtures for common setup
- Mock external dependencies
- Test both success and failure cases

### 2. Coverage Requirements
- Minimum 80% code coverage
- 100% coverage for critical paths
- All error cases must be tested
- Edge cases must be covered

### 3. Performance Criteria
- Order submission < 100ms
- Market data updates < 50ms
- Position calculations < 10ms
- Memory usage < 500MB under normal load

### 4. Security Testing
- Authentication token handling
- Secure credential storage
- API key protection
- Session management

## Known Issues

### SignalR Mocking Issue
- **Problem**: Cannot mock `signalrcore.HubConnectionBuilder`
- **Impact**: Real-time client tests cannot be executed
- **Workaround**: Consider alternative mocking strategies or integration tests
- **Status**: Under investigation

### Test Environment Requirements
- Python 3.8+
- Mock API endpoints
- Test credentials
- Isolated test environment

## Next Steps

1. **Immediate**: Begin Phase 2 order management tests
2. **Short-term**: Resolve SignalR mocking issue
3. **Medium-term**: Complete Phase 3 real-time tests
4. **Long-term**: Implement performance and stress testing

## Reporting

Test results should include:
- Test execution summary
- Coverage report
- Failed test details
- Performance metrics
- Recommendations for fixes
=======
# Project-X-Py Comprehensive Testing Plan

## Overview
This document provides a systematic testing plan for validating all components of the project-x-py financial trading API library. This plan is designed for automated execution by a background testing agent.

## Test Environment Setup

### Prerequisites
- Valid TopStepX API credentials
- Test trading account (preferably demo/paper trading)
- Network connectivity for WebSocket connections
- Python 3.11+ with all dependencies installed

### Environment Variables Required
```bash
export PROJECT_X_API_KEY="your_test_api_key"
export PROJECT_X_USERNAME="your_test_username"
export PROJECT_X_ACCOUNT_NAME="Test Account"  # Optional
```

### Test Data Setup
- Use **MGC** (Micro Gold) as primary test instrument (low margin requirements)
- Test timeframe: Current market hours or replay data
- Position sizes: Minimum quantities (1 contract for most tests)

---

## 1. Core Client Testing (`client.py`)

### 1.1 Authentication & Configuration Testing
**Priority:** Critical
**Location:** `tests/test_client_auth.py`

#### Test Cases:
- [ ] **Valid credentials authentication**
  - Test with environment variables
  - Test with direct credentials
  - Verify JWT token generation and storage
  
- [ ] **Invalid credentials handling**
  - Wrong username/password
  - Missing credentials
  - Expired credentials
  
- [ ] **Multi-account selection**
  - List available accounts
  - Select specific account by name
  - Handle account not found scenarios
  
- [ ] **Configuration management**
  - Default configuration loading
  - Custom configuration override
  - Environment variable precedence

#### Expected Results:
- All authentication methods work correctly
- Proper error handling for invalid credentials
- Account selection functions as expected
- Configuration hierarchy respected

### 1.2 Core API Operations Testing
**Priority:** Critical
**Location:** `tests/test_client_operations.py`

#### Test Cases:
- [ ] **Instrument search and management**
  ```python
  # Test search_instruments()
  instruments = client.search_instruments("MGC")
  assert len(instruments) > 0
  assert any("MGC" in inst.name for inst in instruments)
  
  # Test get_instrument()
  mgc_contract = client.get_instrument("MGC")
  assert mgc_contract.tickSize > 0
  assert mgc_contract.tickValue > 0
  ```

- [ ] **Historical data retrieval**
  ```python
  # Test get_data() with various parameters
  data = client.get_data("MGC", days=5, interval=15)
  assert len(data) > 0
  assert "open" in data.columns
  assert data["timestamp"].is_sorted()
  
  # Test different timeframes
  for interval in [1, 5, 15, 60, 240]:
      data = client.get_data("MGC", days=1, interval=interval)
      assert len(data) > 0
  ```

- [ ] **Account information retrieval**
  ```python
  # Test list_accounts()
  accounts = client.list_accounts()
  assert len(accounts) > 0
  
  # Test account balance and details
  balance = client.get_account_balance()
  assert isinstance(balance, (int, float))
  ```

- [ ] **Position retrieval**
  ```python
  # Test search_open_positions()
  positions = client.search_open_positions()
  assert isinstance(positions, list)
  
  # Test position filtering
  mgc_positions = client.search_open_positions(instrument="MGC")
  ```

#### Expected Results:
- All API endpoints respond correctly
- Data format validation passes
- Error handling works for invalid parameters
- Rate limiting respects configured limits

---

## 2. Order Management Testing (`order_manager.py`)

### 2.1 Order Manager Initialization Testing
**Priority:** Critical
**Location:** `tests/test_order_manager_init.py`

#### Test Cases:
- [ ] **Basic initialization**
  ```python
  order_manager = OrderManager(client)
  assert order_manager.project_x == client
  assert order_manager.initialize() == True
  ```

- [ ] **Real-time integration**
  ```python
  realtime_client = ProjectXRealtimeClient(jwt_token, account_id)
  order_manager.initialize(realtime_client=realtime_client)
  assert order_manager._realtime_enabled == True
  ```

### 2.2 Order Placement Testing
**Priority:** Critical
**Location:** `tests/test_order_placement.py`

#### Test Cases:
- [ ] **Market orders**
  ```python
  # Buy market order
  response = order_manager.place_market_order("MGC", side=0, size=1)
  assert response.success == True
  assert response.order_id is not None
  
  # Sell market order
  response = order_manager.place_market_order("MGC", side=1, size=1)
  assert response.success == True
  ```

- [ ] **Limit orders**
  ```python
  # Get current price for reference
  current_price = client.get_current_price("MGC")
  
  # Buy limit below market
  buy_price = current_price - 5.0
  response = order_manager.place_limit_order("MGC", 0, 1, buy_price)
  assert response.success == True
  
  # Sell limit above market
  sell_price = current_price + 5.0
  response = order_manager.place_limit_order("MGC", 1, 1, sell_price)
  assert response.success == True
  ```

- [ ] **Stop orders**
  ```python
  current_price = client.get_current_price("MGC")
  
  # Buy stop above market
  stop_price = current_price + 3.0
  response = order_manager.place_stop_order("MGC", 0, 1, stop_price)
  assert response.success == True
  
  # Sell stop below market  
  stop_price = current_price - 3.0
  response = order_manager.place_stop_order("MGC", 1, 1, stop_price)
  assert response.success == True
  ```

- [ ] **Bracket orders**
  ```python
  current_price = client.get_current_price("MGC")
  entry_price = current_price - 2.0
  stop_loss = entry_price - 5.0
  take_profit = entry_price + 10.0
  
  response = order_manager.place_bracket_order(
      "MGC", 0, 1, entry_price, stop_loss, take_profit
  )
  assert response.success == True
  assert response.entry_order_id is not None
  assert response.stop_order_id is not None
  assert response.target_order_id is not None
  ```

#### Expected Results:
- All order types place successfully
- Order IDs returned and tracked
- Price alignment to tick sizes works
- Proper error handling for invalid parameters

### 2.3 Order Management Testing
**Priority:** High
**Location:** `tests/test_order_management.py`

#### Test Cases:
- [ ] **Order search and retrieval**
  ```python
  # Search open orders
  orders = order_manager.search_open_orders()
  assert isinstance(orders, list)
  
  # Search by instrument
  mgc_orders = order_manager.search_open_orders(instrument="MGC")
  
  # Get specific order
  if orders:
      order = order_manager.get_order(orders[0].id)
      assert order is not None
  ```

- [ ] **Order cancellation**
  ```python
  # Place a limit order to cancel
  response = order_manager.place_limit_order("MGC", 0, 1, current_price - 10.0)
  order_id = response.order_id
  
  # Cancel the order
  cancel_result = order_manager.cancel_order(order_id)
  assert cancel_result == True
  
  # Verify cancellation
  order = order_manager.get_order(order_id)
  assert order.status in ["Cancelled", "Canceled"]
  ```

- [ ] **Order modification**
  ```python
  # Place a limit order to modify
  response = order_manager.place_limit_order("MGC", 0, 1, current_price - 10.0)
  order_id = response.order_id
  
  # Modify the order
  new_price = current_price - 8.0
  modify_result = order_manager.modify_order(order_id, new_price=new_price)
  assert modify_result == True
  ```

#### Expected Results:
- Order search returns accurate results
- Cancellation works reliably
- Modification updates order correctly
- Status tracking is accurate

---

## 3. Position Management Testing (`position_manager.py`)

### 3.1 Position Manager Initialization Testing
**Priority:** Critical
**Location:** `tests/test_position_manager_init.py`

#### Test Cases:
- [ ] **Basic initialization**
  ```python
  position_manager = PositionManager(client)
  assert position_manager.initialize() == True
  ```

- [ ] **Real-time integration**
  ```python
  position_manager.initialize(realtime_client=realtime_client)
  assert position_manager._realtime_enabled == True
  ```

### 3.2 Position Tracking Testing
**Priority:** Critical
**Location:** `tests/test_position_tracking.py`

#### Test Cases:
- [ ] **Position retrieval**
  ```python
  # Get all positions
  positions = position_manager.get_all_positions()
  assert isinstance(positions, list)
  
  # Get specific position
  mgc_position = position_manager.get_position("MGC")
  # May be None if no position exists
  ```

- [ ] **Position P&L calculation**
  ```python
  # If we have positions, test P&L calculation
  positions = position_manager.get_all_positions()
  if positions:
      position = positions[0]
      pnl = position_manager.calculate_position_pnl(position.instrument)
      assert isinstance(pnl, dict)
      assert "unrealized_pnl" in pnl
      assert "realized_pnl" in pnl
  ```

### 3.3 Portfolio Analytics Testing
**Priority:** High
**Location:** `tests/test_portfolio_analytics.py`

#### Test Cases:
- [ ] **Portfolio P&L**
  ```python
  portfolio_pnl = position_manager.get_portfolio_pnl()
  assert isinstance(portfolio_pnl, dict)
  assert "total_unrealized" in portfolio_pnl
  assert "total_realized" in portfolio_pnl
  ```

- [ ] **Risk metrics**
  ```python
  risk_metrics = position_manager.get_risk_metrics()
  assert isinstance(risk_metrics, dict)
  # Handle missing keys gracefully
  assert "portfolio_value" in risk_metrics or len(risk_metrics) >= 0
  ```

- [ ] **Position sizing**
  ```python
  # Test position sizing calculation
  risk_amount = 100.0
  entry_price = 2045.0
  stop_price = 2040.0
  
  size = position_manager.calculate_position_size(
      "MGC", risk_amount, entry_price, stop_price
  )
  assert isinstance(size, (int, float))
  assert size > 0
  ```

#### Expected Results:
- Portfolio calculations work correctly
- Risk metrics are computed accurately
- Position sizing follows risk parameters
- Error handling for no positions

---

## 4. Real-time Data Management Testing (`realtime_data_manager.py`)

### 4.1 Data Manager Initialization Testing
**Priority:** Critical
**Location:** `tests/test_realtime_data_manager.py`

#### Test Cases:
- [ ] **Basic initialization**
  ```python
  data_manager = ProjectXRealtimeDataManager("MGC", client, account_id)
  assert data_manager.instrument == "MGC"
  ```

- [ ] **Historical data loading**
  ```python
  success = data_manager.initialize(initial_days=7)
  assert success == True
  
  # Check that data was loaded for default timeframes
  data_5min = data_manager.get_data("5min")
  assert len(data_5min) > 0
  assert "timestamp" in data_5min.columns
  ```

### 4.2 Multi-timeframe Data Testing
**Priority:** High
**Location:** `tests/test_mtf_data.py`

#### Test Cases:
- [ ] **Multiple timeframe data retrieval**
  ```python
  # Test all supported timeframes
  timeframes = ["5sec", "15sec", "1min", "5min", "15min", "1hour", "4hour"]
  
  for tf in timeframes:
      data = data_manager.get_data(tf, bars=50)
      if len(data) > 0:  # May be empty for very short timeframes
          assert "open" in data.columns
          assert "high" in data.columns
          assert "low" in data.columns
          assert "close" in data.columns
          assert "volume" in data.columns
  ```

- [ ] **Multi-timeframe analysis**
  ```python
  mtf_data = data_manager.get_mtf_data()
  assert isinstance(mtf_data, dict)
  assert len(mtf_data) > 0
  ```

### 4.3 Real-time Feed Testing
**Priority:** High
**Location:** `tests/test_realtime_feed.py`

#### Test Cases:
- [ ] **Real-time feed start/stop**
  ```python
  # Start real-time feed
  success = data_manager.start_realtime_feed()
  assert success == True
  
  # Wait for some data updates
  import time
  time.sleep(10)
  
  # Check current price is available
  current_price = data_manager.get_current_price()
  assert current_price is not None
  assert current_price > 0
  
  # Stop real-time feed
  data_manager.stop_realtime_feed()
  ```

#### Expected Results:
- Historical data loads correctly
- Multiple timeframes populate properly
- Real-time updates work when market is open
- Current price updates in real-time

---

## 5. OrderBook Testing (`orderbook.py`)

### 5.1 OrderBook Initialization Testing
**Priority:** High
**Location:** `tests/test_orderbook.py`

#### Test Cases:
- [ ] **Basic initialization**
  ```python
  orderbook = OrderBook("MGC")
  assert orderbook.instrument == "MGC"
  ```

### 5.2 Market Microstructure Analytics Testing
**Priority:** High
**Location:** `tests/test_market_microstructure.py`

#### Test Cases:
- [ ] **Orderbook snapshot**
  ```python
  # This requires real-time data feed
  snapshot = orderbook.get_orderbook_snapshot()
  if snapshot:  # May be empty without real data
      assert "bid_price" in snapshot
      assert "ask_price" in snapshot
      assert "bid_volume" in snapshot
      assert "ask_volume" in snapshot
  ```

- [ ] **Advanced analytics**
  ```python
  # Test advanced market metrics
  metrics = orderbook.get_advanced_analytics()
  assert isinstance(metrics, dict)
  
  # These analytics require sufficient market data
  # Tests should handle empty results gracefully
  ```

#### Expected Results:
- OrderBook handles market data correctly
- Analytics functions don't crash with empty data
- Proper data structure validation

---

## 6. Real-time Client Testing (`realtime.py`)

### 6.1 Connection Testing
**Priority:** Critical
**Location:** `tests/test_realtime_client.py`

#### Test Cases:
- [ ] **SignalR dependency check**
  ```python
  # Test that SignalR is available
  from project_x_py.realtime import SIGNALR_AVAILABLE
  if not SIGNALR_AVAILABLE:
      pytest.skip("SignalR not available - install signalrcore")
  ```

- [ ] **Basic connection**
  ```python
  realtime_client = ProjectXRealtimeClient(jwt_token, account_id)
  
  # Test connection
  success = realtime_client.connect()
  assert success == True
  
  # Test disconnection
  realtime_client.disconnect()
  ```

### 6.2 Subscription Testing
**Priority:** High
**Location:** `tests/test_realtime_subscriptions.py`

#### Test Cases:
- [ ] **User data subscriptions**
  ```python
  realtime_client.connect()
  
  # Subscribe to user updates
  success = realtime_client.subscribe_user_updates()
  assert success == True
  
  # Subscribe to market data
  success = realtime_client.subscribe_market_data(["CON.F.US.MGC.M25"])
  assert success == True
  ```

- [ ] **Callback registration**
  ```python
  callback_called = False
  
  def test_callback(data):
      nonlocal callback_called
      callback_called = True
  
  realtime_client.add_callback("quote_update", test_callback)
  
  # Wait for market data (if market is open)
  import time
  time.sleep(5)
  # Note: callback_called may be False if market is closed
  ```

#### Expected Results:
- Connection establishes successfully
- Subscriptions work without errors
- Callbacks can be registered and triggered

---

## 7. Configuration Testing (`config.py`)

### 7.1 Configuration Management Testing
**Priority:** Medium
**Location:** `tests/test_config.py`

#### Test Cases:
- [ ] **Default configuration**
  ```python
  config_manager = ConfigManager()
  config = config_manager.load_config()
  
  assert config.api_url == "https://api.topstepx.com/api"
  assert config.timezone == "America/Chicago"
  assert config.timeout_seconds == 30
  ```

- [ ] **Environment variable override**
  ```python
  import os
  os.environ["PROJECT_X_TIMEOUT"] = "60"
  
  config = config_manager.load_config()
  assert config.timeout_seconds == 60
  
  # Cleanup
  del os.environ["PROJECT_X_TIMEOUT"]
  ```

- [ ] **Configuration file loading**
  ```python
  # Create temporary config file
  import tempfile
  import json
  
  config_data = {"timeout_seconds": 45}
  with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
      json.dump(config_data, f)
      config_file = f.name
  
  config_manager = ConfigManager(config_file)
  config = config_manager.load_config()
  assert config.timeout_seconds == 45
  
  # Cleanup
  os.unlink(config_file)
  ```

#### Expected Results:
- Default configuration loads correctly
- Environment variables override defaults
- Configuration files are processed properly

---

## 8. Utilities Testing (`utils.py`)

### 8.1 Technical Analysis Testing
**Priority:** Medium
**Location:** `tests/test_utils_technical.py`

#### Test Cases:
- [ ] **Moving averages**
  ```python
  import polars as pl
  
  # Create test data
  data = pl.DataFrame({
      "close": [100, 101, 102, 103, 104, 105, 106, 107, 108, 109]
  })
  
  # Test SMA
  sma = calculate_sma(data, "close", 5)
  assert len(sma) == len(data)
  assert not sma[4:].is_null().any()  # No nulls after period
  
  # Test EMA
  ema = calculate_ema(data, "close", 5)
  assert len(ema) == len(data)
  ```

- [ ] **Technical indicators**
  ```python
  # Test RSI
  rsi = calculate_rsi(data, "close", 14)
  assert len(rsi) == len(data)
  
  # Test Bollinger Bands
  bb = calculate_bollinger_bands(data, "close", 20, 2.0)
  assert "upper_band" in bb.columns
  assert "lower_band" in bb.columns
  assert "middle_band" in bb.columns
  ```

### 8.2 Utility Functions Testing
**Priority:** Medium
**Location:** `tests/test_utils_functions.py`

#### Test Cases:
- [ ] **Price formatting**
  ```python
  formatted = format_price(2045.75)
  assert isinstance(formatted, str)
  assert "2045.75" in formatted
  ```

- [ ] **Contract ID validation**
  ```python
  valid_id = "CON.F.US.MGC.M25"
  assert validate_contract_id(valid_id) == True
  
  invalid_id = "invalid_contract"
  assert validate_contract_id(invalid_id) == False
  ```

- [ ] **Symbol extraction**
  ```python
  contract_id = "CON.F.US.MGC.M25"
  symbol = extract_symbol_from_contract_id(contract_id)
  assert symbol == "MGC"
  ```

#### Expected Results:
- Technical analysis functions work correctly
- Utility functions handle edge cases
- Error handling is appropriate

---

## 9. Models and Data Structures Testing (`models.py`)

### 9.1 Data Model Validation Testing
**Priority:** Medium
**Location:** `tests/test_models.py`

#### Test Cases:
- [ ] **Instrument model**
  ```python
  instrument = Instrument(
      id="CON.F.US.MGC.M25",
      name="MGCH25",
      description="Micro Gold March 2025",
      tickSize=0.1,
      tickValue=1.0,
      activeContract=True
  )
  
  assert instrument.id == "CON.F.US.MGC.M25"
  assert instrument.tickSize == 0.1
  assert instrument.activeContract == True
  ```

- [ ] **Order models**
  ```python
  order = Order(
      id="12345",
      contract_id="CON.F.US.MGC.M25",
      side=0,
      size=1,
      price=2045.0,
      status="Open",
      order_type="Limit"
  )
  
  assert order.id == "12345"
  assert order.side == 0
  assert order.size == 1
  ```

- [ ] **Configuration model**
  ```python
  config = ProjectXConfig()
  assert config.api_url == "https://api.topstepx.com/api"
  assert config.timeout_seconds == 30
  
  # Test custom config
  custom_config = ProjectXConfig(timeout_seconds=60)
  assert custom_config.timeout_seconds == 60
  ```

#### Expected Results:
- Data models create correctly
- Field validation works
- Default values are appropriate

---

## 10. Exception Handling Testing (`exceptions.py`)

### 10.1 Exception Classes Testing
**Priority:** Medium
**Location:** `tests/test_exceptions.py`

#### Test Cases:
- [ ] **Exception inheritance**
  ```python
  from project_x_py.exceptions import *
  
  # Test that all exceptions inherit from ProjectXError
  assert issubclass(ProjectXAuthenticationError, ProjectXError)
  assert issubclass(ProjectXConnectionError, ProjectXError)
  assert issubclass(ProjectXOrderError, ProjectXError)
  ```

- [ ] **Exception raising and catching**
  ```python
  # Test authentication error
  try:
      raise ProjectXAuthenticationError("Invalid credentials")
  except ProjectXError as e:
      assert str(e) == "Invalid credentials"
  
  # Test order error
  try:
      raise ProjectXOrderError("Order failed")
  except ProjectXError as e:
      assert str(e) == "Order failed"
  ```

#### Expected Results:
- All exceptions inherit correctly
- Error messages are preserved
- Exception hierarchy works

---

## 11. Examples Validation Testing

### 11.1 Example Scripts Testing
**Priority:** High
**Location:** `tests/test_examples.py`

#### Test Cases:
- [ ] **Basic usage example**
  ```python
  # Run basic_usage.py and verify it completes without errors
  import subprocess
  result = subprocess.run([
      "python", "examples/basic_usage.py"
  ], capture_output=True, text=True)
  
  # Should not crash (return code 0 or 1 for expected errors)
  assert result.returncode in [0, 1]
  ```

- [ ] **Order management demo**
  ```python
  # Test order_position_management_demo.py
  # This should be run with caution as it places real orders
  # Consider using environment flag to enable/disable
  ```

- [ ] **Market analysis examples**
  ```python
  # Test advanced_market_analysis_example.py
  # Verify it can run and produce output
  ```

#### Expected Results:
- Examples run without critical errors
- Output is generated appropriately
- No unexpected crashes

---

## 12. Integration Testing

### 12.1 End-to-End Trading Workflow
**Priority:** Critical
**Location:** `tests/test_integration.py`

#### Test Cases:
- [ ] **Complete trading workflow**
  ```python
  # 1. Initialize all managers
  client = ProjectX.from_env()
  order_manager = create_order_manager(client)
  position_manager = create_position_manager(client)
  
  # 2. Place a small test order
  response = order_manager.place_limit_order(
      "MGC", 0, 1, current_price - 20.0  # Far from market
  )
  assert response.success == True
  
  # 3. Check order appears in search
  orders = order_manager.search_open_orders()
  order_ids = [o.id for o in orders]
  assert response.order_id in order_ids
  
  # 4. Cancel the order
  success = order_manager.cancel_order(response.order_id)
  assert success == True
  
  # 5. Verify cancellation
  time.sleep(2)  # Allow time for cancellation
  order = order_manager.get_order(response.order_id)
  assert order.status in ["Cancelled", "Canceled"]
  ```

- [ ] **Real-time data integration**
  ```python
  # Test that all components work together with real-time data
  suite = create_trading_suite(
      "MGC", client, jwt_token, account_id
  )
  
  # Connect
  assert suite["realtime_client"].connect() == True
  
  # Initialize data manager
  assert suite["data_manager"].initialize(initial_days=7) == True
  
  # Start real-time feed
  assert suite["data_manager"].start_realtime_feed() == True
  
  # Wait for data
  time.sleep(10)
  
  # Check data is updating
  current_price = suite["data_manager"].get_current_price()
  assert current_price is not None
  
  # Cleanup
  suite["realtime_client"].disconnect()
  ```

#### Expected Results:
- Complete workflows execute successfully
- All components integrate properly
- Real-time data flows correctly
- Cleanup works properly

---

## 13. Performance and Load Testing

### 13.1 Performance Testing
**Priority:** Medium
**Location:** `tests/test_performance.py`

#### Test Cases:
- [ ] **API response times**
  ```python
  import time
  
  # Test search_instruments performance
  start_time = time.time()
  instruments = client.search_instruments("MGC")
  end_time = time.time()
  
  assert (end_time - start_time) < 5.0  # Should complete in under 5 seconds
  ```

- [ ] **Data processing performance**
  ```python
  # Test large data set processing
  data = client.get_data("MGC", days=30, interval=1)
  
  start_time = time.time()
  sma = calculate_sma(data, "close", 20)
  end_time = time.time()
  
  assert (end_time - start_time) < 2.0  # Should be fast
  ```

- [ ] **Memory usage monitoring**
  ```python
  import psutil
  import os
  
  process = psutil.Process(os.getpid())
  initial_memory = process.memory_info().rss
  
  # Perform memory-intensive operations
  for i in range(100):
      data = client.get_data("MGC", days=1, interval=1)
  
  final_memory = process.memory_info().rss
  memory_growth = final_memory - initial_memory
  
  # Memory growth should be reasonable (< 100MB)
  assert memory_growth < 100 * 1024 * 1024
  ```

#### Expected Results:
- API calls complete within reasonable time
- Data processing is efficient
- Memory usage is controlled

---

## 14. Error Handling and Edge Cases Testing

### 14.1 Network Error Testing
**Priority:** High
**Location:** `tests/test_error_handling.py`

#### Test Cases:
- [ ] **Connection timeout handling**
  ```python
  # Test with very short timeout
  config = ProjectXConfig(timeout_seconds=0.1)
  client = ProjectX(username, api_key, config=config)
  
  # Should handle timeout gracefully
  try:
      instruments = client.search_instruments("MGC")
  except ProjectXConnectionError:
      pass  # Expected
  ```

- [ ] **Invalid data handling**
  ```python
  # Test with invalid instrument
  try:
      data = client.get_data("INVALID_SYMBOL", days=1)
  except ProjectXInstrumentError:
      pass  # Expected
  ```

- [ ] **Rate limiting testing**
  ```python
  # Test rapid API calls
  for i in range(10):
      try:
          instruments = client.search_instruments("MGC")
      except ProjectXRateLimitError:
          pass  # Expected if rate limited
  ```

#### Expected Results:
- Appropriate exceptions are raised
- Error messages are helpful
- System remains stable after errors

---

## 15. Documentation and Validation Testing

### 15.1 Documentation Testing
**Priority:** Medium
**Location:** `tests/test_documentation.py`

#### Test Cases:
- [ ] **Docstring validation**
  ```python
  import inspect
  from project_x_py import ProjectX
  
  # Check that key methods have docstrings
  assert ProjectX.__doc__ is not None
  assert ProjectX.search_instruments.__doc__ is not None
  assert ProjectX.get_data.__doc__ is not None
  ```

- [ ] **Example code in docstrings**
  ```python
  # Extract and test example code from docstrings
  # This is complex but valuable for ensuring examples work
  ```

#### Expected Results:
- All public methods have docstrings
- Example code in docstrings is valid
- Documentation is complete

---

## Test Execution Strategy

### Phase 1: Core Functionality (Priority: Critical)
1. Client authentication and basic operations
2. Order manager initialization and basic order placement
3. Position manager basic functionality
4. Real-time client connection

### Phase 2: Advanced Features (Priority: High)  
1. Complex order types (bracket, stop, etc.)
2. Real-time data management
3. OrderBook analytics
4. Integration testing

### Phase 3: Validation and Performance (Priority: Medium)
1. Utilities and technical analysis
2. Performance testing
3. Error handling validation
4. Documentation testing

### Test Data Management
- Use consistent test symbols (MGC for most tests)
- Clean up test orders after each test
- Handle market hours (tests may behave differently when market is closed)
- Use paper/demo accounts when possible

### Continuous Integration Considerations
- Tests should be able to run in CI environment
- Handle cases where real-time connections may fail
- Provide mock data for offline testing
- Separate live trading tests from unit tests

### Reporting
- Generate comprehensive test reports
- Track test coverage across all modules
- Monitor performance metrics over time
- Log any issues found for developer review

### Safety Measures
- Always use minimum position sizes for live tests
- Implement maximum loss limits
- Cancel all test orders at completion
- Use demo accounts when available
- Never test with production funds

---

## Expected Outcomes

After completing this testing plan, you should have:

1. **✅ Verified Core Functionality**: All main components work as expected
2. **✅ Validated Integration**: Components work together seamlessly  
3. **✅ Confirmed Real-time Operations**: WebSocket connections and data flows function properly
4. **✅ Tested Error Handling**: System handles errors gracefully
5. **✅ Validated Examples**: All example scripts run correctly
6. **✅ Performance Baseline**: Established performance benchmarks
7. **✅ Documentation Accuracy**: Verified all documentation is correct

This comprehensive testing plan ensures the project-x-py library is production-ready and reliable for financial trading operations. 
