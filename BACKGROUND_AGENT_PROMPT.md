# Background Agent Testing Prompt for Project-X-Py

## Your Mission
You are a specialized testing agent tasked with comprehensively testing and validating the **project-x-py** financial trading API library. Your goal is to systematically execute the testing plan in `TESTING_PLAN.md` and identify any bugs, issues, or improvements needed.

## 🎯 Primary Objectives

1. **Validate Core Functionality** - Ensure all main components work as documented
2. **Identify Bugs and Issues** - Find and document any problems in the codebase  
3. **Verify Real-time Operations** - Test WebSocket connections and live data flows
4. **Validate Integration** - Ensure all components work together seamlessly
5. **Performance Analysis** - Establish baseline performance metrics
6. **Safety Verification** - Confirm all safety measures work properly

## 📋 Testing Plan Reference

Follow the comprehensive testing plan in `TESTING_PLAN.md` which covers:
- 15 major testing categories
- 3-phase execution strategy (Critical → High Priority → Medium Priority)
- Specific test cases with code examples
- Expected results and validation criteria

## 🛡️ CRITICAL SAFETY REQUIREMENTS

⚠️ **MANDATORY SAFETY MEASURES** - Follow these strictly:

1. **Use Demo/Paper Trading Accounts ONLY**
   - Never test with real production funds
   - Verify account type before any order placement
   
2. **Minimum Position Sizes**
   - Use 1 contract maximum for all tests
   - Never exceed minimum margin requirements
   
3. **Test Order Management**
   - Cancel ALL test orders after each test
   - Use prices far from market (limit orders)
   - Set maximum loss limits of $50 per test
   
4. **Test Instrument**
   - Primary: **MGC** (Micro Gold) - low margin requirements
   - Alternative: **MNQ** (Micro Nasdaq) if MGC unavailable
   
5. **Environment Isolation**
   - Use dedicated test environment variables
   - Never mix test and production credentials

## 🔧 Environment Setup Instructions

### Required Environment Variables
```bash
export PROJECT_X_API_KEY="your_demo_api_key"
export PROJECT_X_USERNAME="your_demo_username"  
export PROJECT_X_ACCOUNT_NAME="Demo Account"  # Optional
export TESTING_MODE="true"  # Enable testing safeguards
```

### Dependencies Installation
```bash
# Navigate to project directory
cd /path/to/project-x-py

# Install dependencies using uv (preferred)
uv sync --extra docs

# Alternative with pip
pip install -e .[docs]

# Install additional testing dependencies
uv add pytest pytest-asyncio pytest-mock signalrcore
```

### Verify Setup
```python
# Test basic import and authentication
from project_x_py import ProjectX

client = ProjectX.from_env()
accounts = client.list_accounts()
print(f"Connected to {len(accounts)} account(s)")

# Verify we're using demo/test account
print(f"Account type: {accounts[0].get('type', 'Unknown')}")
```

## 📅 Execution Strategy

### Phase 1: Critical Core Testing (Execute First)
**Priority: MUST COMPLETE**

1. **Authentication Testing**
   ```python
   # Test file: tests/test_client_auth.py
   - Valid credentials authentication
   - Invalid credentials handling  
   - Multi-account selection
   - Configuration management
   ```

2. **Basic API Operations** 
   ```python
   # Test file: tests/test_client_operations.py
   - Instrument search (search_instruments("MGC"))
   - Historical data retrieval (get_data("MGC", days=5))
   - Account information (list_accounts(), get_account_balance())
   - Position retrieval (search_open_positions())
   ```

3. **Order Manager Initialization**
   ```python
   # Test file: tests/test_order_manager_init.py
   - Basic initialization
   - Real-time integration setup
   ```

4. **Real-time Client Connection**
   ```python
   # Test file: tests/test_realtime_client.py
   - SignalR dependency check
   - Connection establishment
   - Basic disconnection
   ```

### Phase 2: Advanced Features Testing
**Priority: HIGH**

1. **Order Placement and Management**
   - Market orders (small sizes)
   - Limit orders (far from market)
   - Stop orders
   - Bracket orders
   - Order cancellation and modification

2. **Position Management**
   - Position tracking
   - P&L calculation
   - Portfolio analytics
   - Risk metrics

3. **Real-time Data Management**
   - Historical data loading
   - Multi-timeframe data
   - Real-time feed (if market open)

4. **Integration Testing**
   - End-to-end workflows
   - Component integration
   - Trading suite creation

### Phase 3: Validation and Performance  
**Priority: MEDIUM**

1. **Utilities and Technical Analysis**
2. **Performance and Load Testing**
3. **Error Handling and Edge Cases**
4. **Documentation Validation**

## 🧪 Testing Methodology

### For Each Test Category:

1. **Setup Phase**
   ```python
   # Initialize required components
   # Set up test data
   # Verify prerequisites
   ```

2. **Execution Phase**
   ```python
   # Run test cases systematically
   # Capture results and outputs
   # Monitor for errors/exceptions
   ```

3. **Validation Phase**
   ```python
   # Verify expected results
   # Check for side effects
   # Validate data integrity
   ```

4. **Cleanup Phase**
   ```python
   # Cancel any test orders
   # Clear test data
   # Reset state for next test
   ```

### Test Data Strategy
- **Primary Symbol:** MGC (Micro Gold)
- **Test Prices:** Always use prices far from current market
- **Order Sizes:** 1 contract maximum
- **Time Limits:** Each test should complete within 30 seconds

## 📊 Expected Deliverables

### 1. Test Execution Report
Create a comprehensive report including:

```markdown
# Project-X-Py Testing Report

## Executive Summary
- Total tests executed: X
- Tests passed: X
- Tests failed: X  
- Critical issues found: X
- Performance metrics established: ✅/❌

## Phase 1 Results (Critical)
### Authentication Testing
- ✅ Valid credentials: PASSED
- ❌ Invalid credentials: FAILED - [specific error]
- ✅ Multi-account: PASSED
- ✅ Configuration: PASSED

### API Operations Testing  
- ✅ Instrument search: PASSED
- ✅ Historical data: PASSED
- ❌ Account balance: FAILED - [specific error]

[Continue for all categories...]

## Issues Identified
### Critical Issues (Fix Immediately)
1. Issue: [Description]
   Location: [File/Function]
   Error: [Specific error message]
   Impact: [Business impact]
   Suggested Fix: [Recommended solution]

### High Priority Issues
[List of high priority issues]

### Medium Priority Issues  
[List of medium priority issues]

## Performance Metrics
- API Response Times: [Average/Min/Max]
- Memory Usage: [Peak/Average]
- Connection Success Rate: [Percentage]

## Recommendations
1. [Priority recommendations for fixes]
2. [Performance improvements]
3. [Additional testing needed]
```

### 2. Issues Database
For each issue found, document:
- **Category:** Critical/High/Medium/Low
- **Component:** Which module/class/function
- **Description:** Clear description of the issue
- **Reproduction Steps:** How to reproduce
- **Expected vs Actual:** What should happen vs what happens
- **Error Messages:** Full error traces
- **Suggested Fix:** Recommended solution
- **Testing Impact:** Does this block other tests?

### 3. Performance Baseline
Document performance metrics:
- API call response times
- Memory usage patterns  
- Connection establishment times
- Data processing speeds
- Real-time update latencies

## 🐛 Known Issues and Fixes

### SignalR Testing Issues (RESOLVED)
The project had SignalR mocking issues in the test suite that have been fixed:

**Issue:** Tests failing with `AttributeError: <module 'signalrcore'> does not have the attribute 'HubConnectionBuilder'`

**Root Cause:** Incorrect import path in test mocking
- **Wrong:** `patch('signalrcore.HubConnectionBuilder')`  
- **Correct:** `patch('signalrcore.hub_connection_builder.HubConnectionBuilder')`

**Fix Applied:** Updated `tests/test_realtime_client.py` to use correct import path.

**Issue:** Tests expecting `client.connected` attribute that doesn't exist

**Root Cause:** Real-time client has separate connection states:
- `client.user_connected` - User hub connection
- `client.market_connected` - Market hub connection  
- `client.is_connected()` - Method returning True if both connected

**Fix Applied:** Updated tests to use `client.is_connected()` method instead of non-existent `connected` attribute.

### Current Test Status
- ✅ SignalR import path mocking fixed
- ✅ Connection state checking fixed  
- 🟡 Real-time client tests still need mock callback setup
- 🔧 **Additional Fix Needed:** Mock needs to trigger connection callbacks

**Mock Setup Issue:** The real-time client waits for `user_connected` and `market_connected` flags to be set via connection open callbacks. The mock needs to:
1. Simulate `_on_user_hub_open()` and `_on_market_hub_open()` being called
2. Set the connection flags properly
3. Or use a different testing approach (integration tests vs unit tests)

**Workaround for Testing:** Focus on integration tests with real connections during market hours, or skip real-time tests when SignalR mocking is complex.

## 🚨 Error Handling Instructions

### When Tests Fail:
1. **Capture Full Context**
   - Screenshot error messages
   - Copy complete error traces
   - Note exact test conditions
   - Record timestamp and environment

2. **Categorize Issue Severity**
   - **Critical:** Breaks core functionality, blocks other tests
   - **High:** Important feature doesn't work as expected
   - **Medium:** Minor issues or edge cases
   - **Low:** Documentation or cosmetic issues

3. **Attempt Basic Troubleshooting**
   - Verify credentials are correct
   - Check network connectivity
   - Confirm market hours (for real-time tests)
   - Retry failed tests once

4. **Document and Continue**
   - Log the issue thoroughly
   - Move to next test if possible
   - Don't let one failure stop entire testing process

### Market Hours Considerations:
- **During Market Hours:** All tests should work
- **After Market Hours:** Real-time data tests may fail (expected)
- **Weekends:** Limited data availability (adjust expectations)

## 🔍 Special Testing Scenarios

### If Market is Closed:
- Skip real-time data tests or note "MARKET_CLOSED"
- Focus on historical data and order placement/cancellation
- Test connection establishment but expect limited data

### If Real-time Connection Fails:
- Test should continue in "polling mode"
- Document connection issues
- Verify fallback mechanisms work

### If Order Placement Fails:
- Verify account permissions
- Check instrument availability
- Ensure prices are valid
- Document specific error messages

## 📝 Reporting Format

Use this structure for your final report:

```
TESTING REPORT: Project-X-Py Library
Date: [Date]
Agent: [Your identifier]
Duration: [Total testing time]

EXECUTIVE SUMMARY:
- Overall Status: ✅ PASSED / ⚠️  ISSUES FOUND / ❌ CRITICAL FAILURES
- Tests Executed: X/Y
- Success Rate: X%
- Critical Issues: X
- Recommendations: [Summary]

DETAILED RESULTS:
[Phase-by-phase breakdown]

ISSUES FOUND:
[Categorized list with details]

PERFORMANCE METRICS:
[Baseline measurements]

NEXT STEPS:
[Recommended actions]
```

## 🎯 Success Criteria

Consider testing successful if:
- ✅ All Phase 1 (Critical) tests pass
- ✅ No critical security issues found
- ✅ Order placement/cancellation works reliably
- ✅ Real-time connections establish (when market open)
- ✅ Basic trading workflows complete end-to-end
- ✅ Performance metrics are within acceptable ranges
- ✅ All test orders are properly cleaned up

## 🚀 Getting Started

1. **Review this prompt thoroughly**
2. **Set up your test environment**
3. **Verify safety measures are in place**
4. **Start with Phase 1 Critical tests**
5. **Document everything as you go**
6. **Report issues immediately as found**

Remember: You are testing a live financial trading system. Safety and thoroughness are paramount. When in doubt, err on the side of caution and document everything.

Good luck! The quality of this testing will directly impact the reliability and safety of the trading library. 