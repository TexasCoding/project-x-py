# ProjectX Python SDK Examples (v4.1.0)

This directory contains working examples for the ProjectX Python SDK v4.1.0. All examples use **MNQ (Micro E-mini NASDAQ)** contracts to minimize risk during testing.

**Note:** v4.0 is the TopstepX Gateway revival. Use `TradingSuite.create()`, `await suite.get_stats()` / `export_stats()`, and see `docs/migration/v3-to-v4.md` for breaking changes.

## ⚠️ Important Safety Notice

**These examples place REAL ORDERS on the market!**
- Only use with simulated/demo accounts
- MNQ micro contracts are used to reduce risk
- Always monitor positions closely
- Examples include safety confirmations before placing orders

## Quick Start

Use the provided `test.sh` script which sets the required environment variables:

```bash
# Make executable
chmod +x test.sh

# Run any example
./test.sh examples/01_basic_client_connection.py
```

Or set environment variables manually:

```bash
export PROJECT_X_API_KEY="your_api_key"
export PROJECT_X_USERNAME="your_username"
export PROJECT_X_ACCOUNT_NAME="your_account_name"

uv run examples/01_basic_client_connection.py
```

## Examples Overview

### Core Examples

#### 00. Trading Suite Demo (`00_trading_suite_demo.py`)
**Quick start with TradingSuite**
- Simplified one-line initialization
- All components integrated and ready
- Automatic authentication and connection

#### 01. Basic Client Connection (`01_basic_client_connection.py`)
**Foundation for all other examples**
- Async client authentication using environment variables
- Account information and verification
- Concurrent API operations demonstration
- Proper resource cleanup with context managers

#### 02. Order Management (`02_order_management.py`)
**⚠️ Places REAL ORDERS - Use with caution!**
- Market, limit, and stop orders
- Bracket orders (entry + stop loss + take profit)
- Order modification and cancellation
- Real-time order status tracking
- Order cleanup and safety measures

#### 03. Position Management (`03_position_management.py`)
**Position tracking and risk management**
- Real-time position monitoring
- Portfolio P&L calculations
- Risk metrics and analysis
- Position sizing calculations
- Position alerts and callbacks

#### 04. Real-time Data Streaming (`04_realtime_data.py`)
**Multi-timeframe market data streaming**
- WebSocket connection management
- Multiple timeframe data (15sec, 1min, 5min, 15min, 1hr)
- Real-time callbacks and events
- Memory management and optimization
- Historical data initialization

#### 05. Orderbook Analysis (`05_orderbook_analysis.py`)
**Level 2 market microstructure analysis**
- Real-time bid/ask levels and depth
- Market imbalance detection
- Trade flow analysis
- Order type statistics
- Memory management for high-frequency data

#### 06. Advanced Orderbook (`06_advanced_orderbook.py`)
**Advanced market microstructure features**
- Iceberg order detection
- Spoofing detection
- Volume profile analysis
- Market microstructure metrics

#### 07. Technical Indicators (`07_technical_indicators.py`)
**Comprehensive technical analysis**
- 64 named indicators including pattern recognition (not a full TA-Lib port)
- Fair Value Gap (FVG) detection
- Order Block identification
- Multi-timeframe indicator analysis
- Real-time indicator updates

#### 08. Order and Position Tracking (`08_order_and_position_tracking.py`)
**Real-time order and position monitoring**
- Concurrent order and position tracking
- Event-based status updates
- Portfolio-level monitoring

#### 09. Instrument Search (`09_get_check_available_instruments.py`)
**Interactive instrument discovery**
- Search available instruments
- Get instrument specifications
- Check trading permissions

### Advanced Features

#### 10. Unified Event System (`10_unified_event_system.py`)
**EventBus demonstration**
- Type-safe event handling
- Priority-based handlers
- Cross-component communication

#### 11. Simplified Data Access (`11_simplified_data_access.py`)
**v3.0.0 simplified APIs**
- Easy data retrieval patterns
- Automatic timeframe management
- Efficient data caching

#### 12. Multi-Timeframe Strategy (`12_simplified_multi_timeframe.py`)
**Simplified multi-timeframe trading**
- Clean multi-timeframe analysis
- Simplified signal generation
- TradingSuite integration

#### 13. Simplified Strategy (`13_simplified_strategy.py`)
**Complete trading strategy with TradingSuite**
- Entry and exit logic
- Risk management
- Performance tracking

#### 14. Enhanced Models (`14_enhanced_models.py`)
**Strategy-friendly data models**
- Position properties for easy access
- Order state helpers
- Performance metrics

#### 15. Order Lifecycle Tracking (`15_order_lifecycle_tracking.py`)
**Comprehensive order management**
- OrderTracker context manager
- Async waiting for fills
- Order chain builder
- Order templates

#### 16. Risk Management (`16_risk_management.py`)
**⚠️ Places REAL ORDERS**
- Position sizing algorithms
- Risk limit enforcement
- Portfolio risk monitoring

#### 17. Join Orders (`17_join_orders.py`)
**Advanced order types**
- JoinBid for better fills
- JoinAsk for better exits
- Improved execution quality

#### 18. Managed Trades (`18_managed_trades.py`)
**Automatic risk management**
- ManagedTrade context manager
- Automatic stop/target placement
- Position scaling

#### 19. Risk Manager Live Demo (`19_risk_manager_live_demo.py`)
**⚠️ Complete risk management system**
- All risk features demonstrated
- Live position monitoring
- Real-time risk adjustments

### Real-time Data Manager Examples

Located in `realtime_data_manager/`:

#### Events with Wait For (`00_events_with_wait_for.py`)
- Async waiting for specific events
- Timeout handling

#### Events with On (`01_events_with_on.py`)
- Event-driven data processing
- CSV export functionality
- Plotly charting integration

## Running Examples Safely

### Recommended Learning Path

1. **Start with Basic Examples** (No order placement):
   ```bash
   ./test.sh examples/00_trading_suite_demo.py
   ./test.sh examples/01_basic_client_connection.py
   ./test.sh examples/04_realtime_data.py
   ./test.sh examples/05_orderbook_analysis.py
   ./test.sh examples/07_technical_indicators.py
   ```

2. **Data and Analysis** (No order placement):
   ```bash
   ./test.sh examples/03_position_management.py
   ./test.sh examples/06_advanced_orderbook.py
   ./test.sh examples/11_simplified_data_access.py
   ```

3. **Order Management** (⚠️ Places real orders):
   ```bash
   ./test.sh examples/02_order_management.py
   ./test.sh examples/15_order_lifecycle_tracking.py
   ./test.sh examples/17_join_orders.py
   ```

4. **Complete Strategies** (⚠️ Places real orders):
   ```bash
   ./test.sh examples/12_simplified_multi_timeframe.py
   ./test.sh examples/13_simplified_strategy.py
   ./test.sh examples/16_risk_management.py
   ./test.sh examples/18_managed_trades.py
   ```

### Safety Features

All examples include:
- User confirmation prompts before placing orders
- Order cleanup and cancellation
- Risk management and position sizing
- Error handling and graceful degradation
- Comprehensive logging and status reporting

### Account Requirements

- **API Access**: Valid ProjectX API credentials
- **Trading Permissions**: Account must have trading enabled
- **Simulated Account**: Strongly recommended for testing
- **Balance**: Sufficient margin for MNQ micro contracts

## Key Concepts Demonstrated

### Architecture Patterns
- **Factory Functions**: Using `create_*` functions for component initialization
- **Dependency Injection**: Components receive their dependencies
- **Real-time Integration**: Single WebSocket connection shared across managers
- **Error Handling**: Comprehensive exception handling and recovery

### Data Management
- **Polars DataFrames**: High-performance data structures throughout
- **Memory Optimization**: Sliding windows and automatic cleanup
- **Multi-timeframe Sync**: Synchronized data across timeframes
- **Caching Strategies**: Efficient data caching and retrieval

### Trading Features
- **Order Types**: Market, limit, stop, bracket orders
- **Position Tracking**: Real-time position monitoring and P&L
- **Risk Management**: Position sizing and risk metrics
- **Technical Analysis**: Professional indicator library

### Real-time Features
- **WebSocket Connections**: Efficient real-time data streaming
- **Event Callbacks**: Custom event handling and notifications
- **System Health**: Connection monitoring and automatic recovery
- **Performance Monitoring**: Memory usage and system statistics

## Troubleshooting

### Common Issues

1. **Authentication Errors**
   - Verify API key and username are correct
   - Check account name matches your account
   - Ensure account has API access enabled

2. **Trading Errors**
   - Verify account has trading permissions
   - Check sufficient margin/balance
   - Ensure market hours for futures trading

3. **Data Issues**
   - Check internet connection for real-time feeds
   - Verify instrument symbols (MNQ should work)
   - Check if market is open for live data

4. **WebSocket Errors**
   - JWT token may have expired (automatically refreshed)
   - Network issues or firewall blocking connections
   - Check firewall settings for WebSocket connections

### Debug Mode

Enable debug logging by modifying examples:

```python
logger = setup_logging(level="DEBUG")  # Change from INFO to DEBUG
```

### Getting Help

- Review the main SDK documentation
- Check `AGENTS.md` for development guidance
- Look at error messages and stack traces
- Test with the basic client connection example first

## Performance Notes

### Expected Performance
- **50-70% reduction in API calls** through intelligent caching
- **Sub-second response times** for cached operations
- **95% reduction in polling** with real-time WebSocket feeds
- **Efficient memory usage** through sliding windows

### Memory Limits (Configurable)
- `max_trades = 10000` (OrderBook trade history)
- `max_depth_entries = 1000` (OrderBook depth per side)
- `max_bars_per_timeframe = 1000` (Real-time data per timeframe)
- `tick_buffer_size = 1000` (Tick data buffer)

## Next Steps

After running these examples:

1. **Study the Source Code**: Examine how each feature is implemented
2. **Build Custom Strategies**: Use examples as templates for your strategies
3. **Integrate with Your Systems**: Adapt patterns to your trading infrastructure
4. **Test Thoroughly**: Always test with simulated accounts first
5. **Monitor Performance**: Use built-in performance monitoring tools

## Contributing

When creating new examples:
- Follow the established naming convention
- Include comprehensive error handling
- Add safety confirmations for order placement
- Use MNQ for consistency
- Document key learning objectives
- Include cleanup procedures
