"""V3
Async ProjectX Python SDK - Core Async Client Module

Author: @TexasCoding
Date: 2025-08-02

This module contains the async version of the ProjectX client class for the ProjectX Python SDK.
It provides a comprehensive asynchronous interface for interacting with the ProjectX Trading Platform
Gateway API, enabling developers to build high-performance trading applications.

The async client handles authentication, account management, market data retrieval, and basic
trading operations using async/await patterns for improved performance and concurrency.

Key Features:
- Async multi-account authentication and management
- Concurrent API operations with httpx
- Async historical market data retrieval with caching
- Non-blocking position tracking and trade history
- Async error handling and connection management
- HTTP/2 support for improved performance

For advanced trading operations, use the specialized managers:
- OrderManager: Complete order lifecycle management
- PositionManager: Portfolio analytics and risk management
- ProjectXRealtimeDataManager: Real-time multi-timeframe OHLCV data
- OrderBook: Level 2 market depth and microstructure analysis
"""

from project_x_py.client.base import ProjectXBase
from project_x_py.utils.async_rate_limiter import RateLimiter


class ProjectX(ProjectXBase):
    """
    Async core ProjectX client for the ProjectX Python SDK.

    This class provides the async foundation for building trading applications by offering
    comprehensive asynchronous access to the ProjectX Trading Platform Gateway API. It handles
    core functionality including:

    - Multi-account authentication and JWT token management
    - Async instrument search and contract selection with caching
    - High-performance historical market data retrieval
    - Non-blocking position and trade history access
    - Automatic retry logic and connection pooling
    - Rate limiting and error handling

    The async client is designed for high-performance applications requiring concurrent
    operations, real-time data processing, or integration with async frameworks like
    FastAPI, aiohttp, or Discord.py.

    For order management and real-time data, use the specialized async managers from the
    project_x_py.async_api module which integrate seamlessly with this client.

    Example:
        >>> # V3: Basic async SDK usage with environment variables (recommended)
        >>> import asyncio
        >>> from project_x_py import ProjectX
        >>>
        >>> async def main():
        >>> # V3: Create and authenticate client with context manager
        >>>     async with ProjectX.from_env() as client:
        >>>         await client.authenticate()
        >>>
        >>> # V3: Get account info with typed models
        >>>         account = client.account_info  # After authentication
        >>>         print(f"Account: {account.name}")
        >>>         print(f"ID: {account.id}")
        >>>         print(f"Balance: ${account.balance:,.2f}")
        >>>
        >>> # V3: Search for instruments with smart contract selection
        >>>         instruments = await client.search_instruments("MNQ")
        >>>         mnq = instruments[0] if instruments else None
        >>>         if mnq:
        >>>             print(f"Found: {mnq.name} ({mnq.symbol})")
        >>>             print(f"Contract ID: {mnq.id}")
        >>>
        >>> # V3: Get historical data concurrently (returns Polars DataFrames)
        >>>         tasks = [
        >>>             client.get_bars("MNQ", days=5, interval=5),  # 5-min bars
        >>>             client.get_bars("ES", days=1, interval=1),   # 1-min bars
        >>>         ]
        >>>         nasdaq_data, sp500_data = await asyncio.gather(*tasks)
        >>>
        >>>         print(f"Nasdaq bars: {len(nasdaq_data)} (Polars DataFrame)")
        >>>         print(f"S&P 500 bars: {len(sp500_data)} (Polars DataFrame)")
        >>>         print(f"Columns: {nasdaq_data.columns}")
        >>>
        >>> asyncio.run(main())

    For advanced async trading applications, use the `TradingSuite`:
        >>> # V3: Advanced trading with the TradingSuite
        >>> import asyncio
        >>> from project_x_py import TradingSuite
        >>>
        >>> async def trading_app():
        >>> # The TradingSuite simplifies setup and integrates all managers
        >>>     suite = await TradingSuite.create(
        ...         "MNQ",
        ...         timeframes=["1min", "5min"],
        ...         features=["orderbook", "risk_manager"]
        ...     )
        >>>
        >>> # Client is authenticated and real-time data is streaming.
        >>>
        >>> # Access integrated managers easily
        >>>     order = await suite.orders.place_market_order(
        ...         contract_id=suite.instrument_id,
        ...         side=0,  # Buy
        ...         size=1
        ...     )
        >>>
        >>>     position = await suite.positions.get_position("MNQ")
        >>>     bars = await suite.data.get_data("1min")
        >>>
        >>>     print(f"Placed order {order.id}, current position: {position.size}")
        >>>     print(f"Latest 1-min bar: {bars.tail(1)}")
        >>>
        >>> asyncio.run(trading_app())
    """


__all__ = ["ProjectX", "ProjectXBase", "RateLimiter"]
