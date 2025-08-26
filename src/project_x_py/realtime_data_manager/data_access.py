"""
Data access methods for retrieving OHLCV data.

Author: @TexasCoding
Date: 2025-08-02

Overview:
    Provides data access and retrieval methods for OHLCV (Open, High, Low, Close, Volume)
    data across multiple timeframes. Implements thread-safe data access with comprehensive
    filtering and retrieval capabilities for real-time trading applications.

Key Features:
    - Thread-safe data access with asyncio locks
    - Multi-timeframe OHLCV data retrieval
    - Current price access with real-time updates
    - Memory-efficient data filtering and limiting
    - Timezone-aware timestamp handling
    - Comprehensive data validation and error handling

Data Access Capabilities:
    - Individual timeframe data retrieval with optional bar limits
    - Multi-timeframe data access for comprehensive analysis
    - Current market price access from tick or bar data
    - Memory-efficient data copying and filtering
    - Thread-safe operations with proper locking
    - Comprehensive error handling and validation

Example Usage:
    ```python
    # V3.1: Data access via TradingSuite
    from project_x_py import TradingSuite
    from project_x_py.indicators import RSI, MACD

    # V3.1: Create suite with data manager
    suite = await TradingSuite.create(
        "MNQ",
        timeframes=["1min", "5min", "15min"],
        initial_days=5,
    )

    # V3.1: Get the most recent 100 bars of 5-minute data
    data_5m = await suite.data.get_data("5min", bars=100)

    if data_5m is not None:
        print(f"Got {len(data_5m)} bars of 5-minute data")

        # V3.1: Access actual OHLCV columns
        latest = data_5m.tail(1)
        print(f"Latest bar:")
        print(f"  Open: {latest['open'][0]}")
        print(f"  High: {latest['high'][0]}")
        print(f"  Low: {latest['low'][0]}")
        print(f"  Close: {latest['close'][0]}")
        print(f"  Volume: {latest['volume'][0]}")

        # V3.1: Calculate indicators with Polars
        if len(data_5m) >= 20:
            sma_20 = data_5m["close"].tail(20).mean()
            print(f"20-bar SMA: {sma_20:.2f}")

            # V3.1: Use pipe for indicator chaining
            with_indicators = data_5m.pipe(RSI, period=14).pipe(MACD)

    # V3.1: Get current market price
    current_price = await suite.data.get_current_price()
    if current_price is not None:
        print(f"Current {suite.instrument} price: ${current_price:.2f}")

    # V3.1: Get multi-timeframe data for analysis
    mtf_data = await suite.data.get_mtf_data()
    for tf, data in mtf_data.items():
        print(f"{tf}: {len(data)} bars available")
        if len(data) > 0:
            latest_close = data["close"].tail(1)[0]
            print(f"  Latest close: {latest_close:.2f}")
    ```

Data Structures:
    OHLCV DataFrame columns:
        - timestamp: Bar timestamp (timezone-aware datetime)
        - open: Opening price for the period
        - high: Highest price during the period
        - low: Lowest price during the period
        - close: Closing price for the period
        - volume: Volume traded during the period

Performance Characteristics:
    - Thread-safe operations with minimal locking overhead
    - Memory-efficient data copying and filtering
    - Optimized for real-time trading applications
    - Support for large datasets with sliding window management

See Also:
    - `realtime_data_manager.core.RealtimeDataManager`
    - `realtime_data_manager.callbacks.CallbackMixin`
    - `realtime_data_manager.data_processing.DataProcessingMixin`
    - `realtime_data_manager.memory_management.MemoryManagementMixin`
    - `realtime_data_manager.validation.ValidationMixin`
"""

import asyncio
import logging
from collections import deque
from datetime import datetime
from typing import TYPE_CHECKING, Any

import polars as pl

if TYPE_CHECKING:
    from pytz import BaseTzInfo


logger = logging.getLogger(__name__)


class DataAccessMixin:
    """Mixin for data access and retrieval methods."""

    # Type stubs - these attributes are expected to be provided by the class using this mixin
    if TYPE_CHECKING:
        from project_x_py.utils.lock_optimization import AsyncRWLock

        data_lock: "asyncio.Lock | AsyncRWLock"
        data_rw_lock: "AsyncRWLock"
        data: dict[str, pl.DataFrame]
        current_tick_data: list[dict[str, Any]] | deque[dict[str, Any]]
        tick_size: float
        timezone: "BaseTzInfo"

    async def get_data(
        self,
        timeframe: str = "5min",
        bars: int | None = None,
    ) -> pl.DataFrame | None:
        """
        Get OHLCV data for a specific timeframe.

        This method returns a Polars DataFrame containing OHLCV (Open, High, Low, Close, Volume)
        data for the specified timeframe. The data is retrieved from the in-memory cache,
        which is continuously updated in real-time. You can optionally limit the number of
        bars returned.

        Args:
            timeframe: Timeframe to retrieve (default: "5min").
                Must be one of the timeframes configured during initialization.
                Common values are "1min", "5min", "15min", "1hr".

            bars: Number of most recent bars to return (None for all available bars).
                When specified, returns only the N most recent bars, which is more
                memory efficient for large datasets.

        Returns:
            pl.DataFrame: A Polars DataFrame with OHLCV data containing the following columns:
                - timestamp: Bar timestamp (timezone-aware datetime)
                - open: Opening price for the period
                - high: Highest price during the period
                - low: Lowest price during the period
                - close: Closing price for the period
                - volume: Volume traded during the period

                Returns None if the timeframe is not available or no data is loaded.

        Example:
            ```python
            # Get the most recent 100 bars of 5-minute data
            data_5m = await manager.get_data("5min", bars=100)

            if data_5m is not None:
                print(f"Got {len(data_5m)} bars of 5-minute data")

                # Get the most recent close price
                latest_close = data_5m["close"].last()
                print(f"Latest close price: {latest_close}")

                # Calculate a simple moving average
                if len(data_5m) >= 20:
                    sma_20 = data_5m["close"].tail(20).mean()
                    print(f"20-bar SMA: {sma_20}")

                # Check for gaps in data
                if data_5m.height > 1:
                    timestamps = data_5m["timestamp"]
                    # This requires handling timezone-aware datetimes properly

                # Use the data with external libraries
                # Convert to pandas if needed (though Polars is preferred)
                # pandas_df = data_5m.to_pandas()
            else:
                print(f"No data available for timeframe: 5min")
            ```

        Note:
            - This method is thread-safe and can be called concurrently from multiple tasks
            - The returned DataFrame is a copy of the internal data and can be modified safely
            - For memory efficiency, specify the 'bars' parameter to limit the result size
        """
        # Check for optimized read lock (AsyncRWLock) and use it for better parallelism
        if hasattr(self, "data_rw_lock"):
            try:
                from project_x_py.utils.lock_optimization import AsyncRWLock

                if isinstance(self.data_rw_lock, AsyncRWLock):
                    async with self.data_rw_lock.read_lock():
                        if timeframe not in self.data:
                            return None

                        df = self.data[timeframe]
                        if bars is not None and len(df) > bars:
                            return df.tail(bars)
                        return df
            except (ImportError, TypeError):
                # Fall back to regular lock if AsyncRWLock not available or type check fails
                pass

        # Fallback to regular data_lock for backward compatibility
        async with self.data_lock:  # type: ignore
            if timeframe not in self.data:
                return None

            df = self.data[timeframe]
            if bars is not None and len(df) > bars:
                return df.tail(bars)
            return df

    async def get_current_price(self) -> float | None:
        """
        Get the current market price from the most recent data.

        This method provides the most recent market price available from tick data or bar data.
        It's designed for quick access to the current price without having to process the full
        OHLCV dataset, making it ideal for real-time trading decisions and order placement.

        The method follows this logic:
        1. First tries to get price from the most recent tick data (most up-to-date)
        2. If no tick data is available, falls back to the most recent bar close price
        3. Checks common timeframes in order of priority: 1min, 5min, 15min

        Returns:
            float: The current price if available
            None: If no price data is available from any source

        Example:
            ```python
            # Get the most recent price
            current_price = await manager.get_current_price()

            if current_price is not None:
                print(f"Current price: ${current_price:.2f}")

                # Use in trading logic
                if current_price > threshold:
                    # Place a sell order
                    await order_manager.place_market_order(
                        contract_id="MNQ",
                        side=1,  # Sell
                        size=1,
                    )
                    print(f"Placed sell order at ${current_price:.2f}")
            else:
                print("No current price data available")
            ```

        Note:
            - This method is optimized for performance and minimal latency
            - The returned price is the most recent available, which could be
              several seconds old if market activity is low
            - The method is thread-safe and can be called concurrently
        """
        # Try to get from tick data first
        if self.current_tick_data:
            try:
                # Import here to avoid circular import
                from project_x_py.order_manager.utils import align_price_to_tick

                raw_price = float(self.current_tick_data[-1]["price"])
                # Align the price to tick size
                return align_price_to_tick(raw_price, self.tick_size)
            except (ValueError, TypeError, KeyError) as e:
                # Handle corrupted tick data gracefully - log and fall back to bar data
                logger.warning(
                    f"Invalid tick data encountered: {e}. Falling back to bar data."
                )
                # Continue to fallback logic below

        # Fallback to most recent bar close (already aligned)
        # Use optimized read lock if available
        if hasattr(self, "data_rw_lock"):
            try:
                from project_x_py.utils.lock_optimization import AsyncRWLock

                if isinstance(self.data_rw_lock, AsyncRWLock):
                    async with self.data_rw_lock.read_lock():
                        for tf_key in [
                            "1min",
                            "5min",
                            "15min",
                        ]:  # Check common timeframes
                            if tf_key in self.data and not self.data[tf_key].is_empty():
                                return float(self.data[tf_key]["close"][-1])
                    return None
            except (ImportError, TypeError):
                # Fall back to regular lock if AsyncRWLock not available or type check fails
                pass

        # Fallback to regular lock
        async with self.data_lock:  # type: ignore
            for tf_key in ["1min", "5min", "15min"]:  # Check common timeframes
                if tf_key in self.data and not self.data[tf_key].is_empty():
                    return float(self.data[tf_key]["close"][-1])

        return None

    async def get_mtf_data(self) -> dict[str, pl.DataFrame]:
        """
        Get multi-timeframe OHLCV data for all configured timeframes.

        Returns:
            Dict mapping timeframe names to DataFrames

        Example:
            >>> mtf_data = await manager.get_mtf_data()
            >>> for tf, data in mtf_data.items():
            ...     print(f"{tf}: {len(data)} bars")
        """
        # Use optimized read lock if available
        if hasattr(self, "data_rw_lock"):
            try:
                from project_x_py.utils.lock_optimization import AsyncRWLock

                if isinstance(self.data_rw_lock, AsyncRWLock):
                    async with self.data_rw_lock.read_lock():
                        return {tf: df.clone() for tf, df in self.data.items()}
            except (ImportError, TypeError):
                # Fall back to regular lock if AsyncRWLock not available or type check fails
                pass

        # Fallback to regular lock
        async with self.data_lock:  # type: ignore
            return {tf: df.clone() for tf, df in self.data.items()}

    async def get_latest_bars(
        self,
        count: int = 1,
        timeframe: str = "5min",
    ) -> pl.DataFrame | None:
        """
        Get the most recent N bars for a timeframe.

        Convenience method for getting the latest bars without specifying the full data.

        Args:
            count: Number of most recent bars to return (default: 1)
            timeframe: Timeframe to retrieve (default: "5min")

        Returns:
            pl.DataFrame: Most recent bars or None if no data

        Example:
            >>> # Get the last 5 bars
            >>> bars = await manager.get_latest_bars(5)
            >>> if bars is not None:
            ...     latest_close = bars["close"][-1]
        """
        return await self.get_data(timeframe, bars=count)

    async def get_latest_price(self) -> float | None:
        """
        Get the most recent price from tick or bar data.

        Simplified alias for get_current_price() with clearer naming.

        Returns:
            float: Latest price or None if no data

        Example:
            >>> price = await manager.get_latest_price()
            >>> if price is not None:
            ...     print(f"Current price: ${price:.2f}")
        """
        return await self.get_current_price()

    async def get_ohlc(
        self,
        timeframe: str = "5min",
    ) -> dict[str, float] | None:
        """
        Get the most recent OHLC values as a dictionary.

        Returns the latest bar's OHLC values in an easy-to-use format.

        Args:
            timeframe: Timeframe to retrieve (default: "5min")

        Returns:
            dict: OHLC values {"open": ..., "high": ..., "low": ..., "close": ...}
                  or None if no data

        Example:
            >>> ohlc = await manager.get_ohlc()
            >>> if ohlc:
            ...     print(
            ...         f"O:{ohlc['open']} H:{ohlc['high']} L:{ohlc['low']} C:{ohlc['close']}"
            ...     )
        """
        data = await self.get_data(timeframe, bars=1)
        if data is None or data.is_empty():
            return None

        row = data.row(0, named=True)
        return {
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": float(row["volume"]),
        }

    async def get_price_range(
        self,
        bars: int = 20,
        timeframe: str = "5min",
    ) -> dict[str, float] | None:
        """
        Get price range statistics for recent bars.

        Returns high, low, and range for the specified number of bars.

        Args:
            bars: Number of bars to analyze (default: 20)
            timeframe: Timeframe to retrieve (default: "5min")

        Returns:
            dict: {"high": ..., "low": ..., "range": ..., "avg_range": ...}
                  or None if insufficient data

        Example:
            >>> range_stats = await manager.get_price_range(bars=50)
            >>> if range_stats:
            ...     print(f"50-bar range: ${range_stats['range']:.2f}")
        """
        data = await self.get_data(timeframe, bars=bars)
        if data is None or len(data) < bars:
            return None

        high_val = data["high"].max()
        low_val = data["low"].min()
        avg_range_val = (data["high"] - data["low"]).mean()

        # Ensure we have valid numeric values
        if high_val is None or low_val is None or avg_range_val is None:
            return None

        # Type narrowing - after None check, these are numeric
        if (
            not isinstance(high_val, int | float)
            or not isinstance(low_val, int | float)
            or not isinstance(avg_range_val, int | float)
        ):
            return None

        high = float(high_val)
        low = float(low_val)
        avg_range = float(avg_range_val)

        return {
            "high": high,
            "low": low,
            "range": high - low,
            "avg_range": avg_range,
        }

    async def get_volume_stats(
        self,
        bars: int = 20,
        timeframe: str = "5min",
    ) -> dict[str, float] | None:
        """
        Get volume statistics for recent bars.

        Returns volume statistics including total, average, and current.

        Args:
            bars: Number of bars to analyze (default: 20)
            timeframe: Timeframe to retrieve (default: "5min")

        Returns:
            dict: {"total": ..., "average": ..., "current": ..., "relative": ...}
                  or None if insufficient data

        Example:
            >>> vol_stats = await manager.get_volume_stats()
            >>> if vol_stats:
            ...     print(f"Volume relative to average: {vol_stats['relative']:.1%}")
        """
        data = await self.get_data(timeframe, bars=bars)
        if data is None or data.is_empty():
            return None

        volumes = data["volume"]
        total_vol = volumes.sum()
        avg_vol = volumes.mean()
        current_vol = volumes[-1]

        # Ensure we have valid numeric values
        if total_vol is None or avg_vol is None or current_vol is None:
            return None

        # Type narrowing - after None check, these are numeric
        if (
            not isinstance(total_vol, int | float)
            or not isinstance(avg_vol, int | float)
            or not isinstance(current_vol, int | float)
        ):
            return None

        total_volume = float(total_vol)
        avg_volume = float(avg_vol)
        current_volume = float(current_vol)

        return {
            "total": total_volume,
            "average": avg_volume,
            "current": current_volume,
            "relative": current_volume / avg_volume if avg_volume > 0 else 0.0,
        }

    async def is_data_ready(
        self,
        min_bars: int = 20,
        timeframe: str | None = None,
    ) -> bool:
        """
        Check if sufficient data is available for trading.

        Verifies that enough bars are loaded for the specified timeframe(s).

        Args:
            min_bars: Minimum number of bars required (default: 20)
            timeframe: Specific timeframe to check, or None to check all

        Returns:
            bool: True if sufficient data is available

        Example:
            >>> if await manager.is_data_ready(min_bars=50):
            ...     # Safe to start trading logic
            ...     strategy.start()
        """
        # Handle both Lock and AsyncRWLock types
        try:
            from project_x_py.utils.lock_optimization import AsyncRWLock

            if isinstance(self.data_lock, AsyncRWLock):
                async with self.data_lock.read_lock():
                    return await self._check_data_readiness(timeframe, min_bars)
            else:
                async with self.data_lock:
                    return await self._check_data_readiness(timeframe, min_bars)
        except (ImportError, TypeError):
            # Fall back to regular lock if AsyncRWLock not available or type check fails
            async with self.data_lock:  # type: ignore[union-attr]
                return await self._check_data_readiness(timeframe, min_bars)

    async def _check_data_readiness(self, timeframe: str | None, min_bars: int) -> bool:
        """Check if data is ready for trading."""
        if timeframe:
            # Check specific timeframe
            if timeframe not in self.data:
                return False
            return len(self.data[timeframe]) >= min_bars
        else:
            # Check all timeframes
            if not self.data:
                return False
            return all(len(df) >= min_bars for df in self.data.values())

    async def get_bars_since(
        self,
        timestamp: datetime,
        timeframe: str = "5min",
    ) -> pl.DataFrame | None:
        """
        Get all bars since a specific timestamp.

        Useful for getting data since a trade entry or specific event.

        Args:
            timestamp: Starting timestamp (inclusive)
            timeframe: Timeframe to retrieve (default: "5min")

        Returns:
            pl.DataFrame: Bars since timestamp or None if no data

        Example:
            >>> entry_time = datetime.now() - timedelta(hours=1)
            >>> bars = await manager.get_bars_since(entry_time)
            >>> if bars is not None:
            ...     print(f"Bars since entry: {len(bars)}")
        """
        data = await self.get_data(timeframe)
        if data is None or data.is_empty():
            return None

        # Convert timestamp to timezone-aware if needed
        from datetime import datetime
        from zoneinfo import ZoneInfo

        if isinstance(timestamp, datetime) and timestamp.tzinfo is None:
            # Assume it's in the data's timezone
            # self.timezone is a pytz timezone object, we need its zone string
            tz_str = str(self.timezone)
            timestamp = timestamp.replace(tzinfo=ZoneInfo(tz_str))

        # Filter bars
        mask = data["timestamp"] >= timestamp
        return data.filter(mask)

    async def get_data_or_none(
        self,
        timeframe: str = "5min",
        min_bars: int = 20,
    ) -> pl.DataFrame | None:
        """
        Get data only if minimum bars are available.

        Simplifies the common pattern of checking for None and minimum length.

        Args:
            timeframe: Timeframe to retrieve (default: "5min")
            min_bars: Minimum bars required (default: 20)

        Returns:
            pl.DataFrame: Data if min_bars available, None otherwise

        Example:
            >>> # Instead of:
            >>> # data = await manager.get_data("5min")
            >>> # if data is None or len(data) < 50:
            >>> #     return
            >>> # Simply use:
            >>> data = await manager.get_data_or_none("5min", min_bars=50)
            >>> if data is None:
            ...     return
        """
        data = await self.get_data(timeframe)
        if data is None or len(data) < min_bars:
            return None
        return data
