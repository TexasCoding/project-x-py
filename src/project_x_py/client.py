"""
ProjectX API Client

This module contains the main ProjectX client class for trading operations.
"""

import datetime
import json
import logging
import time
from datetime import timedelta
from typing import Optional

import polars as pl
import pytz
import requests

from .config import ConfigManager
from .exceptions import (
    ProjectXAuthenticationError,
    ProjectXConnectionError,
    ProjectXDataError,
    ProjectXError,
    ProjectXInstrumentError,
    ProjectXOrderError,
    ProjectXRateLimitError,
    ProjectXServerError,
)
from .models import (
    Account,
    BracketOrderResponse,
    Instrument,
    Order,
    OrderPlaceResponse,
    Position,
    ProjectXConfig,
    Trade,
)
from .utils import (
    extract_symbol_from_contract_id,
)


class ProjectX:
    """
    A comprehensive Python client for the ProjectX Gateway API.

    This class provides complete access to trading functionality including:
    - Market data retrieval
    - Account management
    - Order placement, modification, and cancellation
    - Position management
    - Trade history and analysis

    The client handles authentication, error management, and provides both
    low-level API access and high-level convenience methods.

    Attributes:
        config (ProjectXConfig): Configuration settings
        api_key (str): API key for authentication
        username (str): Username for authentication
        base_url (str): Base URL for the API endpoints
        session_token (str): JWT token for authenticated requests
        headers (dict): HTTP headers for API requests
        account_info (Account): Default account information

    Example:
        >>> # Using environment variables (recommended)
        >>> project_x = ProjectX.from_env()
        >>> # Using explicit credentials
        >>> project_x = ProjectX(username="your_username", api_key="your_api_key")
        >>> # Get market data
        >>> instruments = project_x.search_instruments("MGC")
        >>> data = project_x.get_data("MGC", days=5, interval=15)
        >>> positions = project_x.search_open_positions()
    """

    def __init__(
        self,
        username: str,
        api_key: str,
        config: ProjectXConfig | None = None,
    ):
        """
        Initialize the ProjectX client.

        Args:
            username: Username for TopStepX account
            api_key: API key for TopStepX authentication
            config: Optional configuration object (uses defaults if None)

        Raises:
            ValueError: If required credentials are missing
            ProjectXError: If configuration is invalid
        """
        if not username or not api_key:
            raise ValueError("Both username and api_key are required")

        # Load configuration
        if config is None:
            config_manager = ConfigManager()
            config = config_manager.load_config()

        self.config = config
        self.api_key = api_key
        self.username = username

        # Set up timezone and URLs from config
        self.timezone = pytz.timezone(config.timezone)
        self.base_url = config.api_url

        # Initialize client settings from config
        self.timeout_seconds = config.timeout_seconds
        self.retry_attempts = config.retry_attempts
        self.retry_delay_seconds = config.retry_delay_seconds
        self.requests_per_minute = config.requests_per_minute
        self.burst_limit = config.burst_limit

        # Authentication and session management
        self.session_token: str = ""
        self.headers = None
        self.token_expires_at = None
        self.last_request_time = 0
        self.min_request_interval = 60.0 / self.requests_per_minute

        # Lazy initialization - don't authenticate immediately
        self.account_info: Account | None = None
        self._authenticated = False

        self.logger = logging.getLogger(__name__)

    @classmethod
    def from_env(cls, config: ProjectXConfig | None = None) -> "ProjectX":
        """
        Create ProjectX client using environment variables.

        Environment Variables Required:
            PROJECT_X_API_KEY: API key for TopStepX authentication
            PROJECT_X_USERNAME: Username for TopStepX account

        Args:
            config: Optional configuration object

        Returns:
            ProjectX client instance

        Raises:
            ValueError: If required environment variables are not set

        Example:
            >>> import os
            >>> os.environ["PROJECT_X_API_KEY"] = "your_api_key_here"
            >>> os.environ["PROJECT_X_USERNAME"] = "your_username_here"
            >>> project_x = ProjectX.from_env()
        """
        config_manager = ConfigManager()
        auth_config = config_manager.get_auth_config()

        return cls(
            username=auth_config["username"],
            api_key=auth_config["api_key"],
            config=config,
        )

    @classmethod
    def from_config_file(cls, config_file: str) -> "ProjectX":
        """
        Create ProjectX client using a configuration file.

        Args:
            config_file: Path to configuration file

        Returns:
            ProjectX client instance
        """
        config_manager = ConfigManager(config_file)
        config = config_manager.load_config()
        auth_config = config_manager.get_auth_config()

        return cls(
            username=auth_config["username"],
            api_key=auth_config["api_key"],
            config=config,
        )

    def _ensure_authenticated(self):
        """
        Ensure the client is authenticated with a valid token.

        This method implements lazy authentication and automatic token refresh.
        """
        current_time = time.time()

        # Check if we need to authenticate or refresh token
        if (
            not self._authenticated
            or self.session_token is None
            or (self.token_expires_at and current_time >= self.token_expires_at)
        ):
            self._authenticate_with_retry()

        # Rate limiting: ensure minimum interval between requests
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_interval:
            time.sleep(self.min_request_interval - time_since_last)

        self.last_request_time = time.time()

    def _authenticate_with_retry(
        self, max_retries: int | None = None, base_delay: float | None = None
    ):
        """
        Authenticate with retry logic for handling temporary server issues.

        Args:
            max_retries: Maximum number of retry attempts (uses config if None)
            base_delay: Base delay between retries (uses config if None)
        """
        if max_retries is None:
            max_retries = self.retry_attempts
        if base_delay is None:
            base_delay = self.retry_delay_seconds

        for attempt in range(max_retries):
            try:
                self._authenticate()
                return
            except ProjectXError as e:
                if "503" in str(e) and attempt < max_retries - 1:
                    delay = base_delay * (2**attempt)
                    self.logger.error(
                        f"Authentication failed (attempt {attempt + 1}/{max_retries}), retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                else:
                    raise

    def _authenticate(self):
        """
        Authenticate with the ProjectX API and obtain a session token.

        Uses the API key to authenticate and sets up headers for subsequent requests.

        Raises:
            ProjectXAuthenticationError: If authentication fails
            ProjectXServerError: If server returns 5xx error
            ProjectXConnectionError: If connection fails
        """
        url = f"{self.base_url}/Auth/loginKey"
        headers = {"accept": "text/plain", "Content-Type": "application/json"}

        payload = {"userName": self.username, "apiKey": self.api_key}

        try:
            response = requests.post(
                url, headers=headers, json=payload, timeout=self.timeout_seconds
            )

            # Handle different HTTP status codes
            if response.status_code == 503:
                raise ProjectXServerError(
                    f"Server temporarily unavailable (503): {response.text}"
                )
            elif response.status_code == 429:
                raise ProjectXRateLimitError(
                    f"Rate limit exceeded (429): {response.text}"
                )
            elif response.status_code >= 500:
                raise ProjectXServerError(
                    f"Server error ({response.status_code}): {response.text}"
                )
            elif response.status_code >= 400:
                raise ProjectXAuthenticationError(
                    f"Authentication failed ({response.status_code}): {response.text}"
                )

            response.raise_for_status()

            data = response.json()
            if not data.get("success", False):
                error_msg = data.get("errorMessage", "Unknown authentication error")
                raise ProjectXAuthenticationError(f"Authentication failed: {error_msg}")

            self.session_token = data["token"]

            # Estimate token expiration (typically JWT tokens last 1 hour)
            # Set expiration to 45 minutes to allow for refresh buffer
            self.token_expires_at = time.time() + (45 * 60)

            # Set up headers for subsequent requests
            self.headers = {
                "Authorization": f"Bearer {self.session_token}",
                "accept": "text/plain",
                "Content-Type": "application/json",
            }

            self._authenticated = True
            self.logger.info("ProjectX authentication successful")

        except requests.RequestException as e:
            self.logger.error(f"Authentication request failed: {e}")
            raise ProjectXConnectionError(f"Authentication request failed: {e}")
        except (KeyError, json.JSONDecodeError) as e:
            self.logger.error(f"Invalid authentication response: {e}")
            raise ProjectXAuthenticationError(f"Invalid authentication response: {e}")

    def get_session_token(self):
        """
        Get the current session token.

        Returns:
            str: The JWT session token

        Note:
            This is a legacy method for backward compatibility.
        """
        self._ensure_authenticated()
        return self.session_token

    def get_account_info(self) -> Optional[Account]:
        """
        Retrieve account information for active accounts.

        Returns:
            Account: Account information including balance and trading permissions
            None: If no active accounts are found

        Raises:
            ProjectXError: If not authenticated or API request fails

        Example:
            >>> account = project_x.get_account_info()
            >>> print(f"Account balance: ${account.balance}")
        """
        self._ensure_authenticated()

        # Cache account info to avoid repeated API calls
        if self.account_info is not None:
            return self.account_info

        url = f"{self.base_url}/Account/search"
        payload = {"onlyActiveAccounts": True}

        try:
            response = requests.post(
                url, headers=self.headers, json=payload, timeout=self.timeout_seconds
            )
            self._handle_response_errors(response)

            data = response.json()
            if not data.get("success", False):
                error_msg = data.get("errorMessage", "Unknown error")
                self.logger.error(f"Account search failed: {error_msg}")
                raise ProjectXError(f"Account search failed: {error_msg}")

            accounts = data.get("accounts", [])
            if not accounts:
                return None

            self.account_info = Account(**accounts[0])
            return self.account_info

        except requests.RequestException as e:
            raise ProjectXConnectionError(f"Account search request failed: {e}")
        except (KeyError, json.JSONDecodeError, TypeError) as e:
            self.logger.error(f"Invalid account response: {e}")
            raise ProjectXDataError(f"Invalid account response: {e}")

    def _handle_response_errors(self, response: requests.Response):
        """
        Handle HTTP response errors consistently.

        Args:
            response: requests.Response object

        Raises:
            ProjectXServerError: For 5xx errors
            ProjectXRateLimitError: For 429 errors
            ProjectXError: For other 4xx errors
        """
        if response.status_code == 503:
            raise ProjectXServerError(f"Server temporarily unavailable (503)")
        elif response.status_code == 429:
            raise ProjectXRateLimitError(f"Rate limit exceeded (429)")
        elif response.status_code >= 500:
            raise ProjectXServerError(f"Server error ({response.status_code})")
        elif response.status_code >= 400:
            raise ProjectXError(f"Client error ({response.status_code})")

        response.raise_for_status()

    def get_instrument(self, symbol: str) -> Optional[Instrument]:
        """
        Search for the first instrument matching a symbol.

        Args:
            symbol: Symbol to search for (e.g., "MGC", "MNQ")

        Returns:
            Instrument: First matching instrument with contract details
            None: If no instruments are found

        Raises:
            ProjectXInstrumentError: If instrument search fails

        Example:
            >>> instrument = project_x.get_instrument("MGC")
            >>> print(f"Contract: {instrument.name} - {instrument.description}")
        """
        self._ensure_authenticated()

        url = f"{self.base_url}/Contract/search"
        payload = {"searchText": symbol, "live": False}

        try:
            response = requests.post(
                url, headers=self.headers, json=payload, timeout=self.timeout_seconds
            )
            self._handle_response_errors(response)

            data = response.json()
            if not data.get("success", False):
                error_msg = data.get("errorMessage", "Unknown error")
                self.logger.error(f"Contract search failed: {error_msg}")
                raise ProjectXInstrumentError(f"Contract search failed: {error_msg}")

            contracts = data.get("contracts", [])
            if not contracts:
                self.logger.error(f"No contracts found for symbol: {symbol}")
                return None

            return Instrument(**contracts[0])

        except requests.RequestException as e:
            raise ProjectXConnectionError(f"Contract search request failed: {e}")
        except (KeyError, json.JSONDecodeError, TypeError) as e:
            self.logger.error(f"Invalid contract response: {e}")
            raise ProjectXDataError(f"Invalid contract response: {e}")

    def search_instruments(self, symbol: str) -> list[Instrument]:
        """
        Search for all instruments matching a symbol.

        Args:
            symbol: Symbol to search for (e.g., "MGC", "MNQ")

        Returns:
            List[Instrument]: List of all matching instruments

        Raises:
            ProjectXInstrumentError: If instrument search fails

        Example:
            >>> instruments = project_x.search_instruments("NQ")
            >>> for inst in instruments:
            ...     print(f"{inst.name}: {inst.description}")
        """
        self._ensure_authenticated()

        url = f"{self.base_url}/Contract/search"
        payload = {"searchText": symbol, "live": False}

        try:
            response = requests.post(
                url, headers=self.headers, json=payload, timeout=self.timeout_seconds
            )
            self._handle_response_errors(response)

            data = response.json()
            if not data.get("success", False):
                error_msg = data.get("errorMessage", "Unknown error")
                self.logger.error(f"Contract search failed: {error_msg}")
                raise ProjectXInstrumentError(f"Contract search failed: {error_msg}")

            contracts = data.get("contracts", [])
            return [Instrument(**contract) for contract in contracts]

        except requests.RequestException as e:
            raise ProjectXConnectionError(f"Contract search request failed: {e}")
        except (KeyError, json.JSONDecodeError, TypeError) as e:
            self.logger.error(f"Invalid contract response: {e}")
            raise ProjectXDataError(f"Invalid contract response: {e}")

    def get_data(
        self,
        instrument: str,
        days: int = 8,
        interval: int = 5,
        unit: int = 2,
        limit: int | None = None,
        partial: bool = True,
    ) -> pl.DataFrame | None:
        """
        Retrieve historical bar data for an instrument.

        Args:
            instrument: Symbol of the instrument (e.g., "MGC", "MNQ")
            days: Number of days of historical data. Defaults to 8.
            interval: Interval in minutes between bars. Defaults to 5.
            unit: Unit of time for the interval. Defaults to 2 (minutes).
                  1=Second, 2=Minute, 3=Hour, 4=Day, 5=Week, 6=Month.
            limit: Number of bars to retrieve. Defaults to calculated value.
            partial: Include partial bars. Defaults to True.

        Returns:
            pl.DataFrame: DataFrame with OHLCV data indexed by timestamp
                Columns: open, high, low, close, volume
                Index: timestamp (timezone-aware, US Central)
            None: If no data is available

        Raises:
            ProjectXInstrumentError: If instrument not found
            ProjectXDataError: If data retrieval fails

        Example:
            >>> data = project_x.get_data("MGC", days=5, interval=15)
            >>> print(f"Retrieved {len(data)} bars")
            >>> print(data.tail())
        """
        self._ensure_authenticated()

        # Get instrument details
        instrument_obj = self.get_instrument(instrument)
        if not instrument_obj:
            raise ProjectXInstrumentError(f"Instrument '{instrument}' not found")

        url = f"{self.base_url}/History/retrieveBars"

        # Calculate date range
        start_date = datetime.datetime.now(self.timezone) - timedelta(days=days)
        end_date = datetime.datetime.now(self.timezone)

        # Calculate limit based on unit type
        if not limit:
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

        payload = {
            "contractId": instrument_obj.id,
            "live": False,
            "startTime": start_date.isoformat(),
            "endTime": end_date.isoformat(),
            "unit": unit,
            "unitNumber": interval,
            "limit": limit,
            "includePartialBar": partial,
        }

        try:
            response = requests.post(
                url, headers=self.headers, json=payload, timeout=self.timeout_seconds
            )
            self._handle_response_errors(response)

            data = response.json()
            if not data.get("success", False):
                error_msg = data.get("errorMessage", "Unknown error")
                self.logger.error(f"History retrieval failed: {error_msg}")
                raise ProjectXDataError(f"History retrieval failed: {error_msg}")

            bars = data.get("bars", [])
            if not bars:
                return None

            # Create DataFrame with polars
            df = pl.from_dicts(bars).sort("t")
            df = df.rename(
                {
                    "t": "timestamp",
                    "o": "open",
                    "h": "high",
                    "l": "low",
                    "c": "close",
                    "v": "volume",
                }
            )

            # Convert timestamp to datetime and handle timezone properly
            df = df.with_columns(
                pl.col("timestamp")
                .str.to_datetime()
                .dt.replace_time_zone("UTC")
                .dt.convert_time_zone(str(self.timezone.zone))
            )

            return df

        except requests.RequestException as e:
            raise ProjectXConnectionError(f"History retrieval request failed: {e}")
        except (KeyError, json.JSONDecodeError, ValueError) as e:
            self.logger.error(f"Invalid history response: {e}")
            raise ProjectXDataError(f"Invalid history response: {e}")

    # Order Management Methods - simplified interface
    def place_market_order(
        self, contract_id: str, side: int, size: int, account_id: int | None = None
    ) -> OrderPlaceResponse:
        """
        Place a market order (immediate execution at current market price).

        Args:
            contract_id: The contract ID to trade
            side: Order side: 0=Buy, 1=Sell
            size: Number of contracts to trade
            account_id: Account ID. Uses default account if None.

        Returns:
            OrderPlaceResponse: Response containing order ID and status

        Example:
            >>> # Buy 1 contract at market price
            >>> response = project_x.place_market_order("CON.F.US.MGC.M25", 0, 1)
        """
        return self.place_order(
            contract_id=contract_id,
            order_type=2,  # Market order
            side=side,
            size=size,
            account_id=account_id,
        )

    def place_limit_order(
        self,
        contract_id: str,
        side: int,
        size: int,
        limit_price: float,
        account_id: int | None = None,
    ) -> OrderPlaceResponse:
        """
        Place a limit order (execute only at specified price or better).

        Args:
            contract_id: The contract ID to trade
            side: Order side: 0=Buy, 1=Sell
            size: Number of contracts to trade
            limit_price: Maximum price for buy orders, minimum price for sell orders
            account_id: Account ID. Uses default account if None.

        Returns:
            OrderPlaceResponse: Response containing order ID and status

        Example:
            >>> # Sell 1 contract with minimum price of $2050
            >>> response = project_x.place_limit_order("CON.F.US.MGC.M25", 1, 1, 2050.0)
        """
        return self.place_order(
            contract_id=contract_id,
            order_type=1,  # Limit order
            side=side,
            size=size,
            limit_price=limit_price,
            account_id=account_id,
        )

    def place_order(
        self,
        contract_id: str,
        order_type: int,
        side: int,
        size: int,
        limit_price: float | None = None,
        stop_price: float | None = None,
        trail_price: float | None = None,
        custom_tag: str | None = None,
        linked_order_id: int | None = None,
        account_id: int | None = None,
    ) -> OrderPlaceResponse:
        """
        Place an order with comprehensive parameter support and automatic price alignment.

        All price parameters are automatically aligned to the instrument's tick size.

        Args:
            contract_id: The contract ID to trade
            order_type: Order type:
                1=Limit, 2=Market, 4=Stop, 5=TrailingStop, 6=JoinBid, 7=JoinAsk
            side: Order side: 0=Buy, 1=Sell
            size: Number of contracts to trade
            limit_price: Limit price for limit orders (auto-aligned to tick size)
            stop_price: Stop price for stop orders (auto-aligned to tick size)
            trail_price: Trail amount for trailing stop orders (auto-aligned to tick size)
            custom_tag: Custom identifier for the order
            linked_order_id: ID of a linked order (for OCO, etc.)
            account_id: Account ID. Uses default account if None.

        Returns:
            OrderPlaceResponse: Response containing order ID and status

        Raises:
            ProjectXOrderError: If order placement fails

        Example:
            >>> # Place a limit order - price will be auto-aligned to tick size
            >>> response = project_x.place_order(
            ...     "CON.F.US.MGC.M25", 1, 0, 1, limit_price=2050.15
            ... )
        """
        self._ensure_authenticated()

        # Use account_info if no account_id provided
        if account_id is None:
            if not self.account_info:
                self.get_account_info()
            if not self.account_info:
                raise ProjectXOrderError("No account information available")
            account_id = self.account_info.id

        # Align all prices to tick size to prevent "Invalid price" errors
        aligned_limit_price = self._align_price_to_tick_size(limit_price, contract_id)
        aligned_stop_price = self._align_price_to_tick_size(stop_price, contract_id)
        aligned_trail_price = self._align_price_to_tick_size(trail_price, contract_id)

        url = f"{self.base_url}/Order/place"
        payload = {
            "accountId": account_id,
            "contractId": contract_id,
            "type": order_type,
            "side": side,
            "size": size,
            "limitPrice": aligned_limit_price,
            "stopPrice": aligned_stop_price,
            "trailPrice": aligned_trail_price,
            "customTag": custom_tag,
            "linkedOrderId": linked_order_id,
        }

        try:
            response = requests.post(
                url, headers=self.headers, json=payload, timeout=self.timeout_seconds
            )
            self._handle_response_errors(response)

            data = response.json()
            if not data.get("success", False):
                error_msg = data.get("errorMessage", "Unknown error")
                self.logger.error(f"Order placement failed: {error_msg}")
                raise ProjectXOrderError(f"Order placement failed: {error_msg}")

            return OrderPlaceResponse(**data)

        except requests.RequestException as e:
            raise ProjectXConnectionError(f"Order placement request failed: {e}")
        except (KeyError, json.JSONDecodeError, TypeError) as e:
            self.logger.error(f"Invalid order placement response: {e}")
            raise ProjectXDataError(f"Invalid order placement response: {e}")

    def _align_price_to_tick_size(
        self, price: float | None, contract_id: str
    ) -> float | None:
        """
        Align a price to the instrument's tick size.

        Args:
            price: The price to align
            contract_id: Contract ID to get tick size from

        Returns:
            float: Price aligned to tick size
            None: If price is None
        """
        try:
            if price is None:
                return None

            instrument_obj = None

            # Try to get instrument by simple symbol first (e.g., "MNQ")
            if "." not in contract_id:
                instrument_obj = self.get_instrument(contract_id)
            else:
                # Extract symbol from contract ID (e.g., "CON.F.US.MGC.M25" -> "MGC")
                symbol = extract_symbol_from_contract_id(contract_id)
                if symbol:
                    instrument_obj = self.get_instrument(symbol)

            if not instrument_obj or not hasattr(instrument_obj, "tickSize"):
                self.logger.warning(
                    f"No tick size available for contract {contract_id}, using original price: {price}"
                )
                return price

            tick_size = instrument_obj.tickSize
            if tick_size is None or tick_size <= 0:
                self.logger.warning(
                    f"Invalid tick size {tick_size} for {contract_id}, using original price: {price}"
                )
                return price

            self.logger.debug(
                f"Aligning price {price} with tick size {tick_size} for {contract_id}"
            )

            # Use Decimal for precise arithmetic to avoid floating point errors
            from decimal import ROUND_HALF_UP, Decimal

            # Convert to Decimal for precise calculation
            price_decimal = Decimal(str(price))
            tick_decimal = Decimal(str(tick_size))

            # Round to nearest tick using precise decimal arithmetic
            ticks = (price_decimal / tick_decimal).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
            aligned_decimal = ticks * tick_decimal

            # Determine the number of decimal places needed for the tick size
            tick_str = str(tick_size)
            if "." in tick_str:
                decimal_places = len(tick_str.split(".")[1])
            else:
                decimal_places = 0

            # Create the quantization pattern
            if decimal_places == 0:
                quantize_pattern = Decimal("1")
            else:
                quantize_pattern = Decimal("0." + "0" * (decimal_places - 1) + "1")

            result = float(aligned_decimal.quantize(quantize_pattern))

            if result != price:
                self.logger.info(
                    f"Price alignment: {price} -> {result} (tick size: {tick_size})"
                )

            return result

        except Exception as e:
            self.logger.error(f"Error aligning price {price} to tick size: {e}")
            return price  # Return original price if alignment fails

    # Position Management Methods
    def search_open_positions(self, account_id: int | None = None) -> list[Position]:
        """
        Search for currently open positions.

        Args:
            account_id: Account ID to search. Uses default account if None.

        Returns:
            List[Position]: List of open positions with size and average price

        Raises:
            ProjectXError: If position search fails

        Example:
            >>> positions = project_x.search_open_positions()
            >>> for pos in positions:
            ...     print(f"{pos.contractId}: {pos.size} @ ${pos.averagePrice}")
        """
        self._ensure_authenticated()

        # Use account_info if no account_id provided
        if account_id is None:
            if not self.account_info:
                self.get_account_info()
            if not self.account_info:
                raise ProjectXError("No account information available")
            account_id = self.account_info.id

        url = f"{self.base_url}/Position/searchOpen"
        payload = {"accountId": account_id}

        try:
            response = requests.post(
                url, headers=self.headers, json=payload, timeout=self.timeout_seconds
            )
            self._handle_response_errors(response)

            data = response.json()
            if not data.get("success", False):
                error_msg = data.get("errorMessage", "Unknown error")
                self.logger.error(f"Position search failed: {error_msg}")
                raise ProjectXError(f"Position search failed: {error_msg}")

            positions = data.get("positions", [])
            return [Position(**position) for position in positions]

        except requests.RequestException as e:
            raise ProjectXConnectionError(f"Position search request failed: {e}")
        except (KeyError, json.JSONDecodeError, TypeError) as e:
            self.logger.error(f"Invalid position search response: {e}")
            raise ProjectXDataError(f"Invalid position search response: {e}")

    # Additional convenience methods can be added here as needed
    def get_health_status(self) -> dict:
        """
        Get client health status.

        Returns:
            Dict with health status information
        """
        return {
            "authenticated": self._authenticated,
            "has_session_token": bool(self.session_token),
            "token_expires_at": self.token_expires_at,
            "account_info_loaded": self.account_info is not None,
            "config": {
                "base_url": self.base_url,
                "timeout_seconds": self.timeout_seconds,
                "retry_attempts": self.retry_attempts,
                "requests_per_minute": self.requests_per_minute,
            },
        }
