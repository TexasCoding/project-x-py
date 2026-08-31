"""
Async instrument search, selection, and historical bar data for ProjectX clients.

Author: @TexasCoding
Date: 2025-08-02

Overview:
    Provides async methods for instrument discovery, smart contract selection, and retrieval
    of historical OHLCV bar data, with Polars DataFrame output for high-performance analysis.
    Integrates in-memory caching for both instrument and bar queries, minimizing redundant
    API calls and ensuring data consistency. Designed to support trading and analytics flows
    requiring timely and accurate market data.

Key Features:
    - Symbol/name instrument search with live/active filtering
    - Sophisticated contract selection logic (front month, micro, etc.)
    - Historical bar data retrieval (OHLCV) with timezone handling
    - Transparent, per-query caching for both instrument and bars
    - Data returned as Polars DataFrame (timestamp, open, high, low, close, volume)
    - Utilities for cache management and periodic cleanup

Example Usage:
    ```python
    import asyncio
    from project_x_py import ProjectX


    async def main():
        # V3: Async market data retrieval with Polars DataFrames
        async with ProjectX.from_env() as client:
            await client.authenticate()

            # Get instrument details with smart contract selection
            instrument = await client.get_instrument("ES")
            print(f"Trading: {instrument.name} ({instrument.id})")
            print(f"Tick size: {instrument.tick_size}")

            # Fetch historical bars (returns Polars DataFrame)
            bars = await client.get_bars("ES", days=3, interval=15)
            print(f"Retrieved {len(bars)} 15-minute bars")
            print(bars.head())

            # V3: Can also search by contract ID directly
            mnq_sept = await client.get_instrument("CON.F.US.MNQ.U25")
            print(f"Contract: {mnq_sept.symbol}")


    asyncio.run(main())
    ```

See Also:
    - `project_x_py.client.cache.CacheMixin`
    - `project_x_py.client.base.ProjectXBase`
    - `project_x_py.client.trading.TradingMixin`
"""

import datetime
import re
from datetime import UTC
from typing import Any

import polars as pl
import pytz

from project_x_py.exceptions import ProjectXInstrumentError
from project_x_py.models import Instrument
from project_x_py.utils import (
    ErrorMessages,
    LogContext,
    LogMessages,
    ProjectXLogger,
    format_error_message,
    handle_errors,
    validate_response,
)

logger = ProjectXLogger.get_logger(__name__)


class MarketDataMixin:
    """Mixin class providing market data functionality."""

    # These attributes are provided by the base class
    logger: Any
    config: Any  # ProjectXConfig

    async def _ensure_authenticated(self) -> None:
        """Provided by AuthenticationMixin."""

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        retry_count: int = 0,
    ) -> Any:
        """Provided by HttpMixin."""
        _ = (method, endpoint, data, params, headers, retry_count)

    def get_cached_instrument(self, symbol: str) -> Instrument | None:
        """Provided by CacheMixin."""
        _ = symbol
        return None

    def cache_instrument(self, symbol: str, instrument: Any) -> None:
        """Provided by CacheMixin."""
        _ = (symbol, instrument)

    def get_cached_market_data(self, cache_key: str) -> pl.DataFrame | None:
        """Provided by CacheMixin."""
        _ = cache_key
        return None

    def cache_market_data(self, cache_key: str, data: Any) -> None:
        """Provided by CacheMixin."""
        _ = (cache_key, data)

    @handle_errors("get instrument")
    @validate_response(required_fields=["success", "contracts"])
    async def get_instrument(self, symbol: str, live: bool = False) -> Instrument:
        """
        Get detailed instrument information with caching.

        Args:
            symbol: Trading symbol (e.g., 'MNQ', 'ES', 'NQ') or full contract ID
                   (e.g., 'CON.F.US.MNQ.U25')
            live: If True, prefer Gateway live/active **listed** contracts.
                Practice/sim contracts (TopstepX Practice MNQ/MES, etc.) are
                often excluded from ``live=True``. When no live match is found,
                the search is retried with ``live=False`` and a warning is
                logged. Default False.

        Returns:
            Instrument object with complete contract details

        Example:
            >>> # V3: Get instrument with automatic contract selection
            >>> instrument = await client.get_instrument("NQ")
            >>> print(f"Trading {instrument.symbol} - {instrument.name}")
            >>> print(f"Contract ID: {instrument.id}")
            >>> print(f"Tick size: {instrument.tick_size}")
            >>> print(f"Tick value: ${instrument.tick_value}")
            >>> # V3: Get specific contract by full ID
            >>> mnq_contract = await client.get_instrument("CON.F.US.MNQ.U25")
            >>> print(f"Specific contract: {mnq_contract.symbol}")
        """
        with LogContext(
            logger,
            operation="get_instrument",
            symbol=symbol,
            live=live,
        ):
            await self._ensure_authenticated()

            # Check cache first
            cached_instrument = self.get_cached_instrument(symbol)
            if cached_instrument:
                logger.debug(LogMessages.CACHE_HIT, extra={"symbol": symbol})
                return cached_instrument

            logger.debug(LogMessages.CACHE_MISS, extra={"symbol": symbol})

            # Official lookup when the caller already has a full contract id
            if symbol.startswith("CON."):
                by_id = await self._make_request(
                    "POST", "/Contract/searchById", data={"contractId": symbol}
                )
                if (
                    isinstance(by_id, dict)
                    and by_id.get("success")
                    and isinstance(by_id.get("contract"), dict)
                ):
                    instrument = Instrument.from_api(by_id["contract"])
                    self.cache_instrument(symbol, instrument)
                    return instrument

            # Check if this is a full contract ID (e.g., CON.F.US.MNQ.U25)
            # If so, extract the base symbol for searching
            search_symbol = symbol
            is_contract_id = False
            if symbol.startswith("CON."):
                # Regex to capture the symbol part of a contract ID, e.g., "MNQ.U25" from "CON.F.US.MNQ.U25"
                # This is more robust than splitting by '.' and relying on indices.
                contract_pattern = re.compile(
                    r"^CON\.[A-Z]\.[A-Z]{2}\.(?P<symbol_details>.+)$"
                )
                match = contract_pattern.match(symbol)
                if match:
                    is_contract_id = True
                    symbol_details = match.group("symbol_details")
                    # The symbol can be in parts (e.g., "MNQ.U25") or joined (e.g., "MNQU25")
                    # We only want the base symbol, e.g., "MNQ"
                    base_symbol_part = symbol_details.split(".")[0]

                    # Remove any futures month/year suffix from the base symbol part
                    futures_pattern = re.compile(
                        r"^(?P<base>.+?)(?P<expiry>[FGHJKMNQUVXZ]\d{1,2})$"
                    )
                    futures_match = futures_pattern.match(base_symbol_part)
                    if futures_match:
                        search_symbol = futures_match.group("base")
                    else:
                        search_symbol = base_symbol_part

            # Search for instrument. live=True is Gateway "listed/active" and
            # can exclude Practice/sim contracts (#131).
            payload = {"searchText": search_symbol, "live": live}
            response = await self._make_request(
                "POST", "/Contract/search", data=payload
            )
            contracts_data = (
                response.get("contracts", []) if isinstance(response, dict) else []
            )
            if (
                live
                and isinstance(response, dict)
                and response.get("success") is True
                and not contracts_data
            ):
                logger.warning(
                    "No live/active listed contracts for %s; retrying with "
                    "live=False (Practice/sim contracts are excluded from live=True)",
                    symbol,
                    extra={"symbol": symbol, "live": True},
                )
                payload = {"searchText": search_symbol, "live": False}
                response = await self._make_request(
                    "POST", "/Contract/search", data=payload
                )
                contracts_data = (
                    response.get("contracts", []) if isinstance(response, dict) else []
                )

            if not response or not response.get("success", False):
                raise ProjectXInstrumentError(
                    format_error_message(
                        ErrorMessages.INSTRUMENT_NOT_FOUND, symbol=symbol
                    )
                )

            if not contracts_data:
                raise ProjectXInstrumentError(
                    format_error_message(
                        ErrorMessages.INSTRUMENT_NOT_FOUND, symbol=symbol
                    )
                )

            # Select best match
            if is_contract_id:
                # If searching by contract ID, try to find exact match
                best_match = None
                for contract in contracts_data:
                    if contract.get("id") == symbol:
                        best_match = contract
                        break

                # If no exact match by ID, use the selection logic with search_symbol
                if best_match is None:
                    best_match = self._select_best_contract(
                        contracts_data, search_symbol
                    )
            else:
                best_match = self._select_best_contract(contracts_data, symbol)

            instrument = Instrument.from_api(best_match)

            # Cache the result
            self.cache_instrument(symbol, instrument)
            logger.debug(LogMessages.CACHE_UPDATE, extra={"symbol": symbol})

            return instrument

    def _select_best_contract(
        self,
        instruments: list[dict[str, Any]],
        search_symbol: str,
    ) -> dict[str, Any]:
        """
        Select the best matching contract from search results.

        This method implements smart contract selection logic for futures and other
        instruments, ensuring the most appropriate contract is selected based on
        the search criteria. The selection algorithm follows these priorities:

        1. Exact symbol match (case-insensitive)
        2. For futures contracts:
           - Identifies the base symbol (e.g., "ES" from "ESM23")
           - Groups contracts by base symbol
           - Selects the front month contract (chronologically closest expiration)
        3. For micro contracts, ensures proper matching (e.g., "MNQ" for micro Nasdaq)
        4. Falls back to the first result if no better match is found

        The futures month codes follow CME convention: F(Jan), G(Feb), H(Mar), J(Apr),
        K(May), M(Jun), N(Jul), Q(Aug), U(Sep), V(Oct), X(Nov), Z(Dec)

        Args:
            instruments: List of instrument dictionaries from search results
            search_symbol: Original search symbol provided by the user

        Returns:
            dict[str, Any]: Best matching instrument dictionary with complete contract details

        Raises:
            ProjectXInstrumentError: If no instruments are found for the given symbol
        """
        if not instruments:
            raise ProjectXInstrumentError(f"No instruments found for: {search_symbol}")

        search_upper = search_symbol.upper()

        # First try exact match
        for inst in instruments:
            if inst.get("name", "").upper() == search_upper:
                return inst

        # For futures, try to find the front month
        # Extract base symbol and find all contracts
        futures_pattern = re.compile(r"^(.+?)([FGHJKMNQUVXZ]\d{1,2})$")
        base_symbols: dict[str, list[dict[str, Any]]] = {}

        for inst in instruments:
            name = inst.get("name", "").upper()
            match = futures_pattern.match(name)
            if match:
                base = match.group(1)
                if base not in base_symbols:
                    base_symbols[base] = []
                base_symbols[base].append(inst)

        # Find contracts matching our search
        matching_base = None
        for base in base_symbols:
            if base == search_upper or search_upper.startswith(base):
                matching_base = base
                break

        if matching_base and base_symbols[matching_base]:
            # Sort by name to get front month (alphabetical = chronological for futures)
            sorted_contracts = sorted(
                base_symbols[matching_base], key=lambda x: x.get("name", "")
            )
            return sorted_contracts[0]

        # Default to first result
        return instruments[0]

    @handle_errors("list available contracts")
    async def list_available_contracts(self, live: bool = False) -> list[Instrument]:
        """List contracts available to the authenticated account.

        Args:
            live: If True, list live-subscription contracts.

        Returns:
            List of Instrument objects from POST /Contract/available.
        """
        await self._ensure_authenticated()
        response = await self._make_request(
            "POST", "/Contract/available", data={"live": live}
        )
        if not isinstance(response, dict) or not response.get("success", False):
            error_msg = (
                response.get("errorMessage", "Contract available search failed")
                if isinstance(response, dict)
                else "Contract available search failed"
            )
            raise ProjectXInstrumentError(error_msg)
        contracts = response.get("contracts", []) or []
        return [Instrument.from_api(contract) for contract in contracts]

    @handle_errors("search instruments")
    @validate_response(required_fields=["success", "contracts"])
    async def search_instruments(
        self, query: str, live: bool = False
    ) -> list[Instrument]:
        """
        Search for instruments by symbol or name.

        Args:
            query: Search query (symbol or partial name)
            live: If True, search only Gateway live/active listed instruments.
                Practice/sim contracts may be omitted. Unlike
                ``get_instrument(live=True)``, this method does not fall back
                to ``live=False``.

        Returns:
            List of Instrument objects matching the query

        Example:
            >>> # V3: Search for instruments by symbol or name
            >>> instruments = await client.search_instruments("MNQ")
            >>> for inst in instruments:
            >>>     print(f"{inst.symbol}: {inst.name}")
            >>>     print(f"  Contract ID: {inst.id}")
            >>>     print(f"  Description: {inst.description}")
            >>>     print(f"  Exchange: {inst.exchange}")
        """
        with LogContext(
            logger,
            operation="search_instruments",
            query=query,
            live=live,
        ):
            await self._ensure_authenticated()

            logger.debug(LogMessages.DATA_FETCH, extra={"query": query})

            payload = {"searchText": query, "live": live}
            response = await self._make_request(
                "POST", "/Contract/search", data=payload
            )

            if (
                not response
                or not isinstance(response, dict)
                or not response.get("success", False)
            ):
                return []

            contracts_data = (
                response.get("contracts", []) if isinstance(response, dict) else []
            )
            instruments = [Instrument.from_api(contract) for contract in contracts_data]

            logger.debug(
                LogMessages.DATA_RECEIVED,
                extra={"count": len(instruments), "query": query},
            )

            return instruments

    HISTORY_BAR_LIMIT = 20_000

    def _dataframe_from_bars_response(self, response: Any) -> pl.DataFrame:
        if not response or not isinstance(response, dict):
            return pl.DataFrame()
        if not response.get("success", False):
            error_msg = response.get("errorMessage", "Unknown error")
            self.logger.error(
                LogMessages.DATA_ERROR,
                extra={"operation": "get_history", "error": error_msg},
            )
            return pl.DataFrame()
        bars_data = response.get("bars", [])
        if not bars_data:
            return pl.DataFrame()
        data = (
            pl.DataFrame(bars_data)
            .sort("t")
            .rename(
                {
                    "t": "timestamp",
                    "o": "open",
                    "h": "high",
                    "l": "low",
                    "c": "close",
                    "v": "volume",
                }
            )
        )
        canonical = ["timestamp", "open", "high", "low", "close", "volume"]
        extra = [column for column in data.columns if column not in canonical]
        data = data.select(canonical + extra)
        try:
            data = data.with_columns(
                pl.col("timestamp")
                .str.to_datetime()
                .dt.replace_time_zone("UTC")
                .dt.convert_time_zone(self.config.timezone)
            )
        except Exception:
            try:
                data = data.with_columns(
                    pl.col("timestamp")
                    .str.to_datetime(time_zone="UTC")
                    .dt.convert_time_zone(self.config.timezone)
                )
            except Exception:
                data = data.with_columns(
                    pl.when(pl.col("timestamp").str.contains("[+-]\\d{2}:\\d{2}$|Z$"))
                    .then(pl.col("timestamp").str.to_datetime())
                    .otherwise(
                        pl.col("timestamp")
                        .str.to_datetime()
                        .dt.replace_time_zone("UTC")
                    )
                    .dt.convert_time_zone(self.config.timezone)
                    .alias("timestamp")
                )
        if data.is_empty():
            return data
        return data.sort("timestamp")

    async def _retrieve_bars_paged(
        self,
        contract_id: str,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
        interval: int,
        unit: int,
        live: bool,
        partial: bool,
        page_limit: int,
    ) -> tuple[pl.DataFrame, bool]:
        frames: list[pl.DataFrame] = []
        page_end = end_date
        first_ok = False
        cap = max(1, min(int(page_limit), self.HISTORY_BAR_LIMIT))
        for page_index in range(20):
            payload = {
                "contractId": contract_id,
                "live": live,
                "startTime": start_date.astimezone(pytz.UTC).isoformat(),
                "endTime": page_end.astimezone(pytz.UTC).isoformat(),
                "unit": unit,
                "unitNumber": interval,
                "limit": cap,
                "includePartialBar": partial,
            }
            response = await self._make_request(
                "POST", "/History/retrieveBars", data=payload
            )
            if page_index == 0:
                if (
                    not response
                    or not isinstance(response, dict)
                    or not response.get("success", False)
                ):
                    if response and isinstance(response, dict):
                        self._dataframe_from_bars_response(response)
                    return pl.DataFrame(), False
                first_ok = True
            frame = self._dataframe_from_bars_response(response)
            if frame.is_empty():
                break
            frames.append(frame)
            earliest = frame["timestamp"].min()
            if len(frame) < self.HISTORY_BAR_LIMIT:
                break
            if not isinstance(earliest, datetime.datetime) or earliest <= start_date:
                break
            page_end = earliest
        if not frames:
            return pl.DataFrame(), first_ok
        data = pl.concat(frames).unique(subset=["timestamp"], keep="last")
        return data.sort("timestamp"), True

    @staticmethod
    def _should_stitch_contracts(symbol: str, unit: int, interval: int) -> bool:
        if symbol.startswith("CON."):
            return False
        if unit >= 3:
            return True
        return unit == 2 and interval >= 60

    async def _stitch_prior_contract_bars(
        self,
        active_contract_id: str,
        existing: pl.DataFrame,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
        interval: int,
        unit: int,
        live: bool,
        partial: bool,
        page_limit: int,
    ) -> pl.DataFrame:
        from project_x_py.client.contract_calendar import iter_prior_contract_ids

        if existing.is_empty():
            current_earliest: datetime.datetime = end_date
        else:
            earliest_existing = existing["timestamp"].min()
            if isinstance(earliest_existing, datetime.datetime):
                current_earliest = earliest_existing
            else:
                current_earliest = end_date
        collected: list[pl.DataFrame] = []
        misses = 0
        attempts = 0
        for prior_id in iter_prior_contract_ids(active_contract_id, max_count=16):
            attempts += 1
            if attempts > 16:
                break
            if current_earliest <= start_date:
                break
            try:
                by_id = await self._make_request(
                    "POST", "/Contract/searchById", data={"contractId": prior_id}
                )
            except Exception:
                misses += 1
                if misses >= 4:
                    break
                continue
            contract = (
                by_id.get("contract")
                if isinstance(by_id, dict) and by_id.get("success")
                else None
            )
            if not isinstance(contract, dict):
                misses += 1
                if misses >= 4:
                    break
                continue
            misses = 0
            chunk, chunk_ok = await self._retrieve_bars_paged(
                prior_id,
                start_date,
                current_earliest,
                interval,
                unit,
                live,
                partial,
                page_limit,
            )
            if not chunk_ok or chunk.is_empty():
                continue
            collected.append(chunk)
            earliest = chunk["timestamp"].min()
            if isinstance(earliest, datetime.datetime) and earliest < current_earliest:
                current_earliest = earliest
        collected.reverse()
        frames = [frame for frame in collected if not frame.is_empty()]
        if not existing.is_empty():
            frames.append(existing)
        if not frames:
            return existing
        return (
            pl.concat(frames)
            .unique(subset=["timestamp"], keep="last")
            .sort("timestamp")
        )

    @handle_errors("get bars")
    async def get_bars(
        self,
        symbol: str,
        days: int = 8,
        interval: int = 5,
        unit: int = 2,
        limit: int | None = None,
        partial: bool = True,
        start_time: datetime.datetime | None = None,
        end_time: datetime.datetime | None = None,
        live: bool = False,
    ) -> pl.DataFrame:
        """
        Retrieve historical OHLCV bar data for an instrument.

        This method fetches historical market data with intelligent caching and
        timezone handling. The data is returned as a Polars DataFrame optimized
        for financial analysis and technical indicator calculations.

        Args:
            symbol: Symbol of the instrument (e.g., "MNQ", "ES", "NQ")
            days: Number of days of historical data (default: 8, ignored if start_time/end_time provided)
            interval: Interval between bars in the specified unit (default: 5)
            unit: Time unit for the interval (default: 2 for minutes)
                  1=Second, 2=Minute, 3=Hour, 4=Day, 5=Week, 6=Month, 7=Tick
            limit: Maximum number of bars to retrieve (auto-calculated if None,
                   capped at 20,000 per Gateway)
            partial: Include incomplete/partial bars (default: True)
            start_time: Optional start datetime (overrides days if provided)
            end_time: Optional end datetime (defaults to now if not provided)
            live: If True, retrieve bars from the live data subscription

        Returns:
            pl.DataFrame: DataFrame with OHLCV data and timezone-aware timestamps
                Columns: timestamp, open, high, low, close, volume
                Timezone: Converted to your configured timezone (default: US/Central)

        Raises:
            ProjectXInstrumentError: If instrument not found or invalid
            ProjectXDataError: If data retrieval fails or invalid response

        Example:
            >>> # V3: Get historical OHLCV data as Polars DataFrame
            >>> # Get 5 days of 15-minute Nasdaq futures data
            >>> data = await client.get_bars("MNQ", days=5, interval=15)
            >>> print(f"Retrieved {len(data)} bars")
            >>> print(f"Columns: {data.columns}")
            >>> print(
            ...     f"Date range: {data['timestamp'].min()} to {data['timestamp'].max()}"
            ... )
            >>> # V3: Process with Polars operations
            >>> daily_highs = data.group_by_dynamic("timestamp", every="1d").agg(
            ...     pl.col("high").max()
            ... )
            >>> print(f"Daily highs: {daily_highs}")
            >>> # V3: Different time units available
            >>> # unit=1 (seconds), 2 (minutes), 3 (hours), 4 (days)
            >>> hourly_data = await client.get_bars("ES", days=1, interval=1, unit=3)
            >>> # V3: Use specific time range
            >>> from datetime import datetime
            >>> start = datetime(2025, 1, 1, 9, 30)
            >>> end = datetime(2025, 1, 1, 16, 0)
            >>> data = await client.get_bars("ES", start_time=start, end_time=end)
        """
        with LogContext(
            logger,
            operation="get_bars",
            symbol=symbol,
            days=days,
            interval=interval,
            unit=unit,
            partial=partial,
        ):
            await self._ensure_authenticated()

            # Calculate date range
            from datetime import timedelta

            # Use the configured timezone (America/Chicago by default)
            market_tz = pytz.timezone(self.config.timezone)

            if start_time is not None or end_time is not None:
                # Use provided time range
                if start_time is not None:
                    # Ensure timezone awareness
                    if start_time.tzinfo is None:
                        start_date = market_tz.localize(start_time)
                    else:
                        start_date = start_time.astimezone(market_tz)
                else:
                    # Default to days parameter ago if only end_time provided
                    start_date = datetime.datetime.now(market_tz) - timedelta(days=days)

                if end_time is not None:
                    # Ensure timezone awareness
                    if end_time.tzinfo is None:
                        end_date = market_tz.localize(end_time)
                    else:
                        end_date = end_time.astimezone(market_tz)
                else:
                    # Default to now if only start_time provided
                    end_date = datetime.datetime.now(market_tz)

                # Calculate days for cache key (approximate)
                days_calc = int((end_date - start_date).total_seconds() / 86400)
                cache_key = f"{symbol}_{start_date.isoformat()}_{end_date.isoformat()}_{interval}_{unit}_{partial}_{live}"
            else:
                # Use days parameter
                start_date = datetime.datetime.now(market_tz) - timedelta(days=days)
                end_date = datetime.datetime.now(market_tz)
                days_calc = days
                cache_key = f"{symbol}_{days}_{interval}_{unit}_{partial}_{live}"

            # Check market data cache
            cached_data = self.get_cached_market_data(cache_key)
            if cached_data is not None:
                logger.debug(LogMessages.CACHE_HIT, extra={"cache_key": cache_key})
                return cached_data

            logger.debug(
                LogMessages.DATA_FETCH,
                extra={"symbol": symbol, "days": days_calc, "interval": interval},
            )

            # Lookup instrument
            instrument = await self.get_instrument(symbol)

        # Calculate limit based on unit type
        if limit is None:
            if unit == 1:  # Seconds
                total_seconds = int((end_date - start_date).total_seconds())
                limit = int(total_seconds / interval)
            elif unit == 2:  # Minutes
                total_minutes = int((end_date - start_date).total_seconds() / 60)
                limit = int(total_minutes / interval)
            elif unit == 3:  # Hours
                total_hours = int((end_date - start_date).total_seconds() / 3600)
                limit = int(total_hours / interval)
            else:  # Days or other units
                total_minutes = int((end_date - start_date).total_seconds() / 60)
                limit = int(total_minutes / interval)

        limit = max(1, min(int(limit), self.HISTORY_BAR_LIMIT))

        data, gateway_ok = await self._retrieve_bars_paged(
            instrument.id,
            start_date,
            end_date,
            interval,
            unit,
            live,
            partial,
            limit,
        )
        if not gateway_ok:
            return pl.DataFrame()
        earliest_ts = None if data.is_empty() else data["timestamp"].min()
        if self._should_stitch_contracts(symbol, unit, interval) and (
            data.is_empty()
            or (isinstance(earliest_ts, datetime.datetime) and earliest_ts > start_date)
        ):
            data = await self._stitch_prior_contract_bars(
                instrument.id,
                data,
                start_date,
                end_date,
                interval,
                unit,
                live,
                partial,
                limit,
            )
        if data.is_empty():
            return data
        self.cache_market_data(cache_key, data)
        return data

    # Session-aware methods
    async def get_session_bars(
        self,
        symbol: str,
        timeframe: str = "1min",
        session_type: Any | None = None,
        session_config: Any | None = None,
        days: int = 1,
        **kwargs: Any,
    ) -> pl.DataFrame:
        """
        Get historical bars filtered by trading session.

        Args:
            symbol: Instrument symbol
            timeframe: Data timeframe (e.g., "1min", "5min")
            session_type: Type of session to filter (RTH/ETH)
            session_config: Optional custom session configuration
            days: Number of days of data to fetch
            **kwargs: Additional arguments for get_bars

        Returns:
            Polars DataFrame with session-filtered bars

        Example:
            ```python
            from project_x_py.sessions import SessionType

            # Get RTH-only bars
            rth_bars = await client.get_session_bars(
                "MNQ", session_type=SessionType.RTH, days=5
            )
            ```
        """
        # Parse timeframe to get interval
        interval = 1
        if timeframe == "1min":
            interval = 1
        elif timeframe == "5min":
            interval = 5
        elif timeframe == "15min":
            interval = 15
        elif timeframe == "30min":
            interval = 30
        elif timeframe == "60min" or timeframe == "1hour":
            interval = 60

        # Get all bars first
        bars = await self.get_bars(symbol, days=days, interval=interval, **kwargs)

        # Apply session filtering if requested
        if session_type is not None or session_config is not None:
            from project_x_py.sessions import (
                SessionConfig,
                SessionFilterMixin,
            )

            # Use provided config or create one
            if session_config is None and session_type is not None:
                session_config = SessionConfig(session_type=session_type)

            if session_config is not None:
                filter_mixin = SessionFilterMixin(config=session_config)
                bars = await filter_mixin.filter_by_session(
                    bars, session_config.session_type, symbol
                )

        return bars

    async def get_session_market_hours(self, symbol: str) -> dict[str, Any]:
        """
        Get market hours for a specific instrument's sessions.

        Args:
            symbol: Instrument symbol

        Returns:
            Dictionary with RTH and ETH market hours

        Example:
            ```python
            hours = await client.get_session_market_hours("ES")
            print(f"RTH: {hours['RTH']['open']} - {hours['RTH']['close']}")
            ```
        """
        from project_x_py.sessions import DEFAULT_SESSIONS

        # Get session times from default or custom config
        session_times = DEFAULT_SESSIONS.get(symbol)

        if session_times:
            return {
                "RTH": {
                    "open": session_times.rth_start.strftime("%H:%M"),
                    "close": session_times.rth_end.strftime("%H:%M"),
                    "timezone": "America/New_York",
                },
                "ETH": {
                    "open": session_times.eth_start.strftime("%H:%M")
                    if session_times.eth_start
                    else "18:00",
                    "close": session_times.eth_end.strftime("%H:%M")
                    if session_times.eth_end
                    else "17:00",
                    "timezone": "America/New_York",
                },
            }

        # Default hours for unknown instruments
        return {
            "RTH": {"open": "09:30", "close": "16:00", "timezone": "America/New_York"},
            "ETH": {"open": "18:00", "close": "17:00", "timezone": "America/New_York"},
        }

    async def get_session_volume_profile(
        self,
        symbol: str,
        session_type: Any | None = None,
        days: int = 1,
        price_levels: int = 50,
    ) -> dict[str, Any]:
        """
        Calculate volume profile for a specific session.

        Args:
            symbol: Instrument symbol
            session_type: Type of session (RTH/ETH)
            days: Number of days for profile calculation
            price_levels: Number of price levels for profile

        Returns:
            Dictionary with price levels and volume distribution

        Example:
            ```python
            profile = await client.get_session_volume_profile(
                "MNQ", session_type=SessionType.RTH
            )
            ```
        """
        # Get session-filtered bars
        bars = await self.get_session_bars(
            symbol, timeframe="1min", session_type=session_type, days=days
        )

        if bars.is_empty():
            return {"price_level": [], "volume": [], "session_type": str(session_type)}

        # Calculate price levels
        low_min = bars["low"].min()
        high_max = bars["high"].max()
        price_min = (
            float(low_min)
            if low_min is not None and isinstance(low_min, int | float)
            else 0.0
        )
        price_max = (
            float(high_max)
            if high_max is not None and isinstance(high_max, int | float)
            else 0.0
        )
        price_step = (price_max - price_min) / price_levels

        # Create price bins
        price_bins = [price_min + i * price_step for i in range(price_levels + 1)]

        # Calculate volume at each price level
        volume_profile = []
        for i in range(len(price_bins) - 1):
            level_min = price_bins[i]
            level_max = price_bins[i + 1]

            # Find bars that traded in this price range
            level_volume = bars.filter(
                (pl.col("low") <= level_max) & (pl.col("high") >= level_min)
            )["volume"].sum()

            volume_profile.append(
                {
                    "price": (level_min + level_max) / 2,
                    "volume": int(level_volume) if level_volume else 0,
                }
            )

        return {
            "price_level": [p["price"] for p in volume_profile],
            "volume": [p["volume"] for p in volume_profile],
            "session_type": str(session_type) if session_type else "ALL",
        }

    async def get_session_statistics(
        self,
        symbol: str,
        session_type: Any | None = None,
        days: int = 1,
    ) -> dict[str, Any]:
        """
        Calculate statistics for a specific trading session.

        Args:
            symbol: Instrument symbol
            session_type: Type of session (RTH/ETH)
            days: Number of days for statistics

        Returns:
            Dictionary with session statistics

        Example:
            ```python
            stats = await client.get_session_statistics(
                "MNQ", session_type=SessionType.RTH
            )
            print(f"Session High: {stats['session_high']}")
            print(f"Session VWAP: {stats['session_vwap']}")
            ```
        """
        # Get session-filtered bars
        bars = await self.get_session_bars(
            symbol, timeframe="1min", session_type=session_type, days=days
        )

        if bars.is_empty():
            return {
                "session_high": None,
                "session_low": None,
                "session_volume": 0,
                "session_vwap": None,
                "session_range": None,
            }

        # Calculate statistics
        high_val = bars["high"].max()
        low_val = bars["low"].min()
        session_high = (
            float(high_val)
            if high_val is not None and isinstance(high_val, int | float)
            else 0.0
        )
        session_low = (
            float(low_val)
            if low_val is not None and isinstance(low_val, int | float)
            else 0.0
        )
        session_volume = int(bars["volume"].sum())

        # Calculate VWAP
        bars_with_pv = bars.with_columns(
            [(pl.col("close") * pl.col("volume")).alias("price_volume")]
        )
        total_pv = bars_with_pv["price_volume"].sum()
        total_volume = bars_with_pv["volume"].sum()
        session_vwap = float(total_pv / total_volume) if total_volume > 0 else None

        return {
            "session_high": session_high,
            "session_low": session_low,
            "session_volume": session_volume,
            "session_vwap": session_vwap,
            "session_range": session_high - session_low,
        }

    async def is_session_open(
        self,
        symbol: str,
        session_type: Any | None = None,
    ) -> bool:
        """
        Check if market is currently open for a specific session.

        Args:
            symbol: Instrument symbol
            session_type: Type of session to check (RTH/ETH)

        Returns:
            True if session is currently open

        Example:
            ```python
            if await client.is_session_open("ES", SessionType.RTH):
                print("Regular trading hours are open")
            ```
        """
        from datetime import datetime

        from project_x_py.sessions import SessionConfig, SessionFilterMixin, SessionType

        # Create session filter
        config = SessionConfig(
            session_type=session_type if session_type else SessionType.ETH
        )
        filter_mixin = SessionFilterMixin(config=config)

        # Check current time
        now = datetime.now(UTC)
        return filter_mixin.is_in_session(now, config.session_type, symbol)

    async def get_next_session_open(
        self,
        symbol: str,
        session_type: Any | None = None,
    ) -> datetime.datetime | None:
        """
        Get the next session open time.

        Args:
            symbol: Instrument symbol
            session_type: Type of session (RTH/ETH)

        Returns:
            Datetime of next session open

        Example:
            ```python
            next_open = await client.get_next_session_open("ES", SessionType.RTH)
            print(f"RTH opens at: {next_open}")
            ```
        """
        from datetime import datetime, timedelta

        import pytz

        from project_x_py.sessions import DEFAULT_SESSIONS, SessionType

        # Get session times
        session_times = DEFAULT_SESSIONS.get(symbol)
        if not session_times:
            return None

        # Get current time in market timezone
        market_tz = pytz.timezone("America/New_York")
        now = datetime.now(market_tz)

        # Determine which session time to use
        if session_type == SessionType.RTH:
            session_start = session_times.rth_start
        else:
            session_start = session_times.eth_start or session_times.rth_start

        # Calculate next open
        next_open = now.replace(
            hour=session_start.hour,
            minute=session_start.minute,
            second=0,
            microsecond=0,
        )

        # If we're past today's open, move to next trading day
        if now >= next_open:
            next_open += timedelta(days=1)
            # Skip weekends
            while next_open.weekday() >= 5:  # Saturday = 5, Sunday = 6
                next_open += timedelta(days=1)

        return next_open.astimezone(pytz.UTC)

    async def get_session_trades(
        self,
        symbol: str,
        session_type: Any | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Get recent trades filtered by session.

        Args:
            symbol: Instrument symbol
            session_type: Type of session (RTH/ETH)
            limit: Maximum number of trades to return

        Returns:
            List of trade dictionaries

        Note: This is a placeholder for future implementation when
        trade data API is available.
        """
        # Placeholder - would need actual trade data endpoint
        _ = (symbol, session_type, limit)  # Mark as used
        return []

    async def get_session_order_flow(
        self,
        symbol: str,
        session_type: Any | None = None,
        days: int = 1,
    ) -> dict[str, Any]:
        """
        Analyze order flow for a specific session.

        Args:
            symbol: Instrument symbol
            session_type: Type of session (RTH/ETH)
            days: Number of days for analysis

        Returns:
            Dictionary with order flow metrics

        Note: This is a simplified implementation using bar data.
        Full implementation would require tick/trade data.
        """
        # Get session bars
        bars = await self.get_session_bars(
            symbol, timeframe="1min", session_type=session_type, days=days
        )

        if bars.is_empty():
            return {
                "buy_volume": 0,
                "sell_volume": 0,
                "net_delta": 0,
                "total_volume": 0,
            }

        # Simple approximation: up bars = buying, down bars = selling
        bars_with_direction = bars.with_columns(
            [
                pl.when(pl.col("close") >= pl.col("open"))
                .then(pl.col("volume"))
                .otherwise(0)
                .alias("buy_volume"),
                pl.when(pl.col("close") < pl.col("open"))
                .then(pl.col("volume"))
                .otherwise(0)
                .alias("sell_volume"),
            ]
        )

        buy_volume = int(bars_with_direction["buy_volume"].sum())
        sell_volume = int(bars_with_direction["sell_volume"].sum())

        return {
            "buy_volume": buy_volume,
            "sell_volume": sell_volume,
            "net_delta": buy_volume - sell_volume,
            "total_volume": buy_volume + sell_volume,
        }
