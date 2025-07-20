"""
ProjectX API Client

Author: TexasCoding
Date: June 2025

This module contains the main ProjectX client class for trading operations.
It provides a comprehensive interface for interacting with the ProjectX API,
including authentication, account management, market data retrieval, and order
management.

The client handles authentication, error management, and provides both
low-level API access and high-level convenience methods.

"""

import datetime
import gc
import json
import logging
import os  # Added for os.getenv
import time
from datetime import timedelta

import polars as pl
import pytz
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import ConfigManager
from .exceptions import (
    ProjectXAuthenticationError,
    ProjectXConnectionError,
    ProjectXDataError,
    ProjectXError,
    ProjectXInstrumentError,
    ProjectXRateLimitError,
    ProjectXServerError,
)
from .models import (
    Account,
    Instrument,
    Position,
    ProjectXConfig,
)


class ProjectX:
    """
    A comprehensive Python client for the ProjectX Gateway API.

    This class provides access to core trading functionality including:
    - Market data retrieval
    - Account management with multi-account support
    - Instrument search and contract details
    - Position management
    - Authentication and session management

    For order management operations, use the OrderManager class.
    For real-time market data, use ProjectXRealtimeDataManager and OrderBook.

    The client handles authentication, error management, and provides both
    low-level API access and high-level convenience methods.

    Attributes:
        config (ProjectXConfig): Configuration settings
        api_key (str): API key for authentication
        username (str): Username for authentication
        account_name (str | None): Optional account name for multi-account selection
        base_url (str): Base URL for the API endpoints
        session_token (str): JWT token for authenticated requests
        headers (dict): HTTP headers for API requests
        account_info (Account): Selected account information

    Example:
        >>> # Using environment variables (recommended)
        >>> project_x = ProjectX.from_env()
        >>> # Using explicit credentials
        >>> project_x = ProjectX(username="your_username", api_key="your_api_key")
        >>> # Selecting specific account by name
        >>> project_x = ProjectX.from_env(account_name="Main Trading Account")
        >>> # List available accounts
        >>> accounts = project_x.list_accounts()
        >>> for account in accounts:
        ...     print(f"Account: {account['name']} (ID: {account['id']})")
        >>> # Get market data
        >>> instruments = project_x.search_instruments("MGC")
        >>> data = project_x.get_data("MGC", days=5, interval=15)
        >>> positions = project_x.search_open_positions()
        >>> # For order management, use OrderManager
        >>> from project_x_py import create_order_manager
        >>> order_manager = create_order_manager(project_x)
        >>> response = order_manager.place_market_order("MGC", 0, 1)
    """

    def __init__(
        self,
        username: str,
        api_key: str,
        config: ProjectXConfig | None = None,
        account_name: str | None = None,
    ):
        """
        Initialize the ProjectX client.

        Args:
            username: Username for TopStepX account
            api_key: API key for TopStepX authentication
            config: Optional configuration object (uses defaults if None)
            account_name: Optional account name to select specific account (uses first if None)

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
        self.account_name = account_name  # Store account name for selection

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

        # Connection pooling and session management
        self.session = self._create_session()

        # Caching for performance
        self.instrument_cache: dict[str, Instrument] = {}
        self.cache_ttl = 300  # 5 minutes cache TTL
        self.last_cache_cleanup = time.time()

        # Lazy initialization - don't authenticate immediately
        self.account_info: Account | None = None
        self._authenticated = False

        # Performance monitoring
        self.api_call_count = 0
        self.cache_hit_count = 0

        self.logger = logging.getLogger(__name__)

    @classmethod
    def from_env(
        cls, config: ProjectXConfig | None = None, account_name: str | None = None
    ) -> "ProjectX":
        """
        Create ProjectX client using environment variables.

        Environment Variables Required:
            PROJECT_X_API_KEY: API key for TopStepX authentication
            PROJECT_X_USERNAME: Username for TopStepX account

        Optional Environment Variables:
            PROJECT_X_ACCOUNT_NAME: Account name to select specific account

        Args:
            config: Optional configuration object
            account_name: Optional account name (overrides environment variable)

        Returns:
            ProjectX client instance

        Raises:
            ValueError: If required environment variables are not set

        Example:
            >>> import os
            >>> os.environ["PROJECT_X_API_KEY"] = "your_api_key_here"
            >>> os.environ["PROJECT_X_USERNAME"] = "your_username_here"
            >>> os.environ["PROJECT_X_ACCOUNT_NAME"] = (
            ...     "Main Trading Account"  # Optional
            ... )
            >>> project_x = ProjectX.from_env()
        """
        config_manager = ConfigManager()
        auth_config = config_manager.get_auth_config()

        # Use provided account_name or try to get from environment
        if account_name is None:
            account_name = os.getenv("PROJECT_X_ACCOUNT_NAME")

        return cls(
            username=auth_config["username"],
            api_key=auth_config["api_key"],
            config=config,
            account_name=account_name,
        )

    @classmethod
    def from_config_file(
        cls, config_file: str, account_name: str | None = None
    ) -> "ProjectX":
        """
        Create ProjectX client using a configuration file.

        Args:
            config_file: Path to configuration file
            account_name: Optional account name to select specific account

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
            account_name=account_name,
        )

    def _create_session(self) -> requests.Session:
        """
        Create an optimized requests session with connection pooling and retries.

        Returns:
            Configured requests session
        """
        session = requests.Session()

        # Configure retry strategy
        retry_strategy = Retry(
            total=self.retry_attempts,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST", "GET"],
        )

        # Configure HTTP adapter with connection pooling
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,  # Number of connection pools
            pool_maxsize=20,  # Maximum connections per pool
            pool_block=True,  # Block when pool is full
        )

        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    def _cleanup_cache(self) -> None:
        """
        Clean up expired cache entries periodically.
        """
        current_time = time.time()
        if current_time - self.last_cache_cleanup > self.cache_ttl:
            # Clear instrument cache (instruments don't change often)
            # Could implement more sophisticated TTL per entry if needed
            self.last_cache_cleanup = current_time

            # Log cache statistics
            if self.api_call_count > 0:
                cache_hit_rate = (self.cache_hit_count / self.api_call_count) * 100
                self.logger.debug(
                    f"Cache stats: {self.cache_hit_count}/{self.api_call_count} "
                    f"hits ({cache_hit_rate:.1f}%)"
                )

    def _ensure_authenticated(self):
        """
        Ensure the client is authenticated with a valid token.

        This method implements lazy authentication and automatic token refresh.
        """
        current_time = time.time()

        # Check if we need to authenticate or refresh token
        # Preemptive refresh at 80% of token lifetime for better performance
        refresh_threshold = (
            self.token_expires_at - (45 * 60 * 0.2) if self.token_expires_at else 0
        )

        if (
            not self._authenticated
            or self.session_token is None
            or (self.token_expires_at and current_time >= refresh_threshold)
        ):
            self._authenticate_with_retry()

        # Periodic cache cleanup
        self._cleanup_cache()

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
            self.logger.debug(
                f"Authentication attempt {attempt + 1}/{max_retries} with payload: {self.username}, {self.api_key[:4]}****"
            )
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
            self.api_call_count += 1
            response = self.session.post(url, headers=headers, json=payload)

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
            raise ProjectXConnectionError(f"Authentication request failed: {e}") from e
        except (KeyError, json.JSONDecodeError) as e:
            self.logger.error(f"Invalid authentication response: {e}")
            raise ProjectXAuthenticationError(
                f"Invalid authentication response: {e}"
            ) from e

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

    def get_account_info(self) -> Account | None:
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
            self.api_call_count += 1
            response = self.session.post(url, headers=self.headers, json=payload)
            self._handle_response_errors(response)

            data = response.json()
            if not data.get("success", False):
                error_msg = data.get("errorMessage", "Unknown error")
                self.logger.error(f"Account search failed: {error_msg}")
                raise ProjectXError(f"Account search failed: {error_msg}")

            accounts = data.get("accounts", [])
            if not accounts:
                return None

            # If account_name is provided, find the specific account by name
            if self.account_name:
                for account in accounts:
                    if account.get("name") == self.account_name:
                        self.account_info = Account(**account)
                        return self.account_info
                self.logger.warning(
                    f"Account with name '{self.account_name}' not found."
                )
                return None

            # Otherwise, take the first active account
            self.account_info = Account(**accounts[0])
            return self.account_info

        except requests.RequestException as e:
            raise ProjectXConnectionError(f"Account search request failed: {e}") from e
        except (KeyError, json.JSONDecodeError, TypeError) as e:
            self.logger.error(f"Invalid account response: {e}")
            raise ProjectXDataError(f"Invalid account response: {e}") from e

    def list_accounts(self) -> list[dict]:
        """
        List all available accounts for the authenticated user.

        Returns:
            List[dict]: List of all available accounts with their details

        Raises:
            ProjectXError: If not authenticated or API request fails

        Example:
            >>> accounts = project_x.list_accounts()
            >>> for account in accounts:
            ...     print(f"Account: {account['name']} (ID: {account['id']})")
            ...     print(f"  Balance: ${account.get('balance', 0):.2f}")
            ...     print(f"  Can Trade: {account.get('canTrade', False)}")
        """
        self._ensure_authenticated()

        url = f"{self.base_url}/Account/search"
        payload = {"onlyActiveAccounts": True}

        try:
            self.api_call_count += 1
            response = self.session.post(url, headers=self.headers, json=payload)
            self._handle_response_errors(response)

            data = response.json()
            if not data.get("success", False):
                error_msg = data.get("errorMessage", "Unknown error")
                self.logger.error(f"Account search failed: {error_msg}")
                raise ProjectXError(f"Account search failed: {error_msg}")

            accounts = data.get("accounts", [])
            return accounts

        except requests.RequestException as e:
            raise ProjectXConnectionError(f"Account search request failed: {e}") from e
        except (KeyError, json.JSONDecodeError, TypeError) as e:
            self.logger.error(f"Invalid account response: {e}")
            raise ProjectXDataError(f"Invalid account response: {e}") from e

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
            raise ProjectXServerError("Server temporarily unavailable (503)")
        elif response.status_code == 429:
            raise ProjectXRateLimitError("Rate limit exceeded (429)")
        elif response.status_code >= 500:
            raise ProjectXServerError(f"Server error ({response.status_code})")
        elif response.status_code >= 400:
            raise ProjectXError(f"Client error ({response.status_code})")

        response.raise_for_status()

    def get_instrument(self, symbol: str) -> Instrument | None:
        """
        Search for the first instrument matching a symbol with caching.

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
        # Check cache first
        if symbol in self.instrument_cache:
            self.cache_hit_count += 1
            return self.instrument_cache[symbol]

        self._ensure_authenticated()

        url = f"{self.base_url}/Contract/search"
        payload = {"searchText": symbol, "live": False}

        try:
            self.api_call_count += 1
            response = self.session.post(url, headers=self.headers, json=payload)
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

            instrument = Instrument(**contracts[0])
            # Cache the result
            self.instrument_cache[symbol] = instrument
            return instrument

        except requests.RequestException as e:
            raise ProjectXConnectionError(f"Contract search request failed: {e}") from e
        except (KeyError, json.JSONDecodeError, TypeError) as e:
            self.logger.error(f"Invalid contract response: {e}")
            raise ProjectXDataError(f"Invalid contract response: {e}") from e

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
            self.api_call_count += 1
            response = self.session.post(url, headers=self.headers, json=payload)
            self._handle_response_errors(response)

            data = response.json()
            if not data.get("success", False):
                error_msg = data.get("errorMessage", "Unknown error")
                self.logger.error(f"Contract search failed: {error_msg}")
                raise ProjectXInstrumentError(f"Contract search failed: {error_msg}")

            contracts = data.get("contracts", [])
            return [Instrument(**contract) for contract in contracts]

        except requests.RequestException as e:
            raise ProjectXConnectionError(f"Contract search request failed: {e}") from e
        except (KeyError, json.JSONDecodeError, TypeError) as e:
            self.logger.error(f"Invalid contract response: {e}")
            raise ProjectXDataError(f"Invalid contract response: {e}") from e

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
            self.api_call_count += 1
            response = self.session.post(url, headers=self.headers, json=payload)
            self._handle_response_errors(response)

            data = response.json()
            if not data.get("success", False):
                error_msg = data.get("errorMessage", "Unknown error")
                self.logger.error(f"History retrieval failed: {error_msg}")
                raise ProjectXDataError(f"History retrieval failed: {error_msg}")

            bars = data.get("bars", [])
            if not bars:
                return None

            # Optimize DataFrame creation and operations
            # Create DataFrame with proper schema and efficient column operations
            df = (
                pl.from_dicts(bars)
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
                .with_columns(
                    # Optimized datetime conversion with cached timezone
                    pl.col("timestamp")
                    .str.to_datetime()
                    .dt.replace_time_zone("UTC")
                    .dt.convert_time_zone(str(self.timezone.zone))
                )
            )

            # Trigger garbage collection for large datasets
            if len(df) > 10000:
                gc.collect()

            return df

        except requests.RequestException as e:
            raise ProjectXConnectionError(
                f"History retrieval request failed: {e}"
            ) from e
        except (KeyError, json.JSONDecodeError, ValueError) as e:
            self.logger.error(f"Invalid history response: {e}")
            raise ProjectXDataError(f"Invalid history response: {e}") from e

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
            self.api_call_count += 1
            response = self.session.post(url, headers=self.headers, json=payload)
            self._handle_response_errors(response)

            data = response.json()
            if not data.get("success", False):
                error_msg = data.get("errorMessage", "Unknown error")
                self.logger.error(f"Position search failed: {error_msg}")
                raise ProjectXError(f"Position search failed: {error_msg}")

            positions = data.get("positions", [])
            return [Position(**position) for position in positions]

        except requests.RequestException as e:
            raise ProjectXConnectionError(f"Position search request failed: {e}") from e
        except (KeyError, json.JSONDecodeError, TypeError) as e:
            self.logger.error(f"Invalid position search response: {e}")
            raise ProjectXDataError(f"Invalid position search response: {e}") from e

    # ================================================================================
    # ENHANCED API COVERAGE - COMPREHENSIVE ENDPOINT ACCESS
    # ================================================================================

    def search_trades(
        self,
        start_date: datetime.datetime | None = None,
        end_date: datetime.datetime | None = None,
        contract_id: str | None = None,
        account_id: int | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """
        Search trade execution history.

        Args:
            start_date: Start date for trade search (default: 30 days ago)
            end_date: End date for trade search (default: now)
            contract_id: Optional contract ID filter
            account_id: Account ID to search. Uses default account if None.
            limit: Maximum number of trades to return

        Returns:
            List[dict]: List of executed trades with details

        Example:
            >>> from datetime import datetime, timedelta
            >>> start = datetime.now() - timedelta(days=7)
            >>> trades = project_x.search_trades(start_date=start)
            >>> for trade in trades:
            ...     print(
            ...         f"Trade: {trade['contractId']} - {trade['size']} @ ${trade['price']}"
            ...     )
        """
        self._ensure_authenticated()

        if account_id is None:
            if not self.account_info:
                self.get_account_info()
            if not self.account_info:
                raise ProjectXError("No account information available")
            account_id = self.account_info.id

        # Default date range if not provided
        if start_date is None:
            start_date = datetime.datetime.now(self.timezone) - timedelta(days=30)
        if end_date is None:
            end_date = datetime.datetime.now(self.timezone)

        url = f"{self.base_url}/Trade/search"
        payload = {
            "accountId": account_id,
            "startTime": start_date.isoformat(),
            "endTime": end_date.isoformat(),
            "limit": limit,
        }

        if contract_id:
            payload["contractId"] = contract_id

        try:
            self.api_call_count += 1
            response = self.session.post(url, headers=self.headers, json=payload)
            self._handle_response_errors(response)

            data = response.json()
            if not data.get("success", False):
                error_msg = data.get("errorMessage", "Unknown error")
                self.logger.error(f"Trade search failed: {error_msg}")
                raise ProjectXDataError(f"Trade search failed: {error_msg}")

            return data.get("trades", [])

        except requests.RequestException as e:
            raise ProjectXConnectionError(f"Trade search request failed: {e}") from e
        except (KeyError, json.JSONDecodeError, TypeError) as e:
            self.logger.error(f"Invalid trade search response: {e}")
            raise ProjectXDataError(f"Invalid trade search response: {e}") from e

    def search_position_history(
        self,
        start_date: datetime.datetime | None = None,
        end_date: datetime.datetime | None = None,
        contract_id: str | None = None,
        account_id: int | None = None,
        include_closed: bool = True,
        limit: int = 100,
    ) -> list[dict]:
        """
        Search position history including closed positions.

        Args:
            start_date: Start date for position search (default: 30 days ago)
            end_date: End date for position search (default: now)
            contract_id: Optional contract ID filter
            account_id: Account ID to search. Uses default account if None.
            include_closed: Whether to include closed positions
            limit: Maximum number of positions to return

        Returns:
            List[dict]: List of position history with details

        Example:
            >>> positions = project_x.search_position_history(include_closed=True)
            >>> for pos in positions:
            ...     if pos.get("status") == "closed":
            ...         print(
            ...             f"Closed: {pos['contractId']} - P&L: ${pos.get('realizedPnl', 0)}"
            ...         )
        """
        self._ensure_authenticated()

        if account_id is None:
            if not self.account_info:
                self.get_account_info()
            if not self.account_info:
                raise ProjectXError("No account information available")
            account_id = self.account_info.id

        # Default date range if not provided
        if start_date is None:
            start_date = datetime.datetime.now(self.timezone) - timedelta(days=30)
        if end_date is None:
            end_date = datetime.datetime.now(self.timezone)

        url = f"{self.base_url}/Position/search"
        payload = {
            "accountId": account_id,
            "startTime": start_date.isoformat(),
            "endTime": end_date.isoformat(),
            "includeClosed": include_closed,
            "limit": limit,
        }

        if contract_id:
            payload["contractId"] = contract_id

        try:
            self.api_call_count += 1
            response = self.session.post(url, headers=self.headers, json=payload)
            self._handle_response_errors(response)

            data = response.json()
            if not data.get("success", False):
                error_msg = data.get("errorMessage", "Unknown error")
                self.logger.error(f"Position history search failed: {error_msg}")
                raise ProjectXDataError(f"Position history search failed: {error_msg}")

            return data.get("positions", [])

        except requests.RequestException as e:
            raise ProjectXConnectionError(
                f"Position history request failed: {e}"
            ) from e
        except (KeyError, json.JSONDecodeError, TypeError) as e:
            self.logger.error(f"Invalid position history response: {e}")
            raise ProjectXDataError(f"Invalid position history response: {e}") from e

    def get_account_performance(
        self,
        start_date: datetime.datetime | None = None,
        end_date: datetime.datetime | None = None,
        account_id: int | None = None,
    ) -> dict:
        """
        Get account performance metrics.

        Args:
            start_date: Start date for performance calculation (default: 30 days ago)
            end_date: End date for performance calculation (default: now)
            account_id: Account ID. Uses default account if None.

        Returns:
            dict: Performance metrics including P&L, win rate, etc.

        Example:
            >>> perf = project_x.get_account_performance()
            >>> print(f"Total P&L: ${perf.get('totalPnl', 0):.2f}")
            >>> print(f"Win Rate: {perf.get('winRate', 0) * 100:.1f}%")
        """
        self._ensure_authenticated()

        if account_id is None:
            if not self.account_info:
                self.get_account_info()
            if not self.account_info:
                raise ProjectXError("No account information available")
            account_id = self.account_info.id

        # Default date range if not provided
        if start_date is None:
            start_date = datetime.datetime.now(self.timezone) - timedelta(days=30)
        if end_date is None:
            end_date = datetime.datetime.now(self.timezone)

        url = f"{self.base_url}/Account/performance"
        payload = {
            "accountId": account_id,
            "startTime": start_date.isoformat(),
            "endTime": end_date.isoformat(),
        }

        try:
            self.api_call_count += 1
            response = self.session.post(url, headers=self.headers, json=payload)
            self._handle_response_errors(response)

            data = response.json()
            if not data.get("success", False):
                error_msg = data.get("errorMessage", "Unknown error")
                self.logger.error(f"Performance retrieval failed: {error_msg}")
                # Return empty performance data instead of failing
                return {
                    "totalPnl": 0.0,
                    "winRate": 0.0,
                    "totalTrades": 0,
                    "avgWin": 0.0,
                    "avgLoss": 0.0,
                    "profitFactor": 0.0,
                    "maxDrawdown": 0.0,
                }

            return data.get("performance", {})

        except requests.RequestException as e:
            self.logger.warning(f"Performance request failed: {e}")
            return {"error": str(e)}
        except (KeyError, json.JSONDecodeError, TypeError) as e:
            self.logger.warning(f"Invalid performance response: {e}")
            return {"error": str(e)}

    def get_account_settings(self, account_id: int | None = None) -> dict:
        """
        Get account settings and configuration.

        Args:
            account_id: Account ID. Uses default account if None.

        Returns:
            dict: Account settings and configuration

        Example:
            >>> settings = project_x.get_account_settings()
            >>> print(f"Risk Limit: ${settings.get('riskLimit', 0)}")
            >>> print(f"Max Position Size: {settings.get('maxPositionSize', 0)}")
        """
        self._ensure_authenticated()

        if account_id is None:
            if not self.account_info:
                self.get_account_info()
            if not self.account_info:
                raise ProjectXError("No account information available")
            account_id = self.account_info.id

        url = f"{self.base_url}/Account/settings"
        payload = {"accountId": account_id}

        try:
            self.api_call_count += 1
            response = self.session.post(url, headers=self.headers, json=payload)
            self._handle_response_errors(response)

            data = response.json()
            if not data.get("success", False):
                error_msg = data.get("errorMessage", "Unknown error")
                self.logger.warning(f"Settings retrieval failed: {error_msg}")
                return {"error": error_msg}

            return data.get("settings", {})

        except requests.RequestException as e:
            self.logger.warning(f"Settings request failed: {e}")
            return {"error": str(e)}
        except (KeyError, json.JSONDecodeError, TypeError) as e:
            self.logger.warning(f"Invalid settings response: {e}")
            return {"error": str(e)}

    def get_risk_metrics(self, account_id: int | None = None) -> dict:
        """
        Get risk management metrics and limits.

        Args:
            account_id: Account ID. Uses default account if None.

        Returns:
            dict: Risk metrics including limits and current exposure

        Example:
            >>> risk = project_x.get_risk_metrics()
            >>> print(f"Current Risk: ${risk.get('currentRisk', 0):.2f}")
            >>> print(f"Risk Limit: ${risk.get('riskLimit', 0):.2f}")
        """
        self._ensure_authenticated()

        if account_id is None:
            if not self.account_info:
                self.get_account_info()
            if not self.account_info:
                raise ProjectXError("No account information available")
            account_id = self.account_info.id

        url = f"{self.base_url}/Risk/metrics"
        payload = {"accountId": account_id}

        try:
            self.api_call_count += 1
            response = self.session.post(url, headers=self.headers, json=payload)
            self._handle_response_errors(response)

            data = response.json()
            if not data.get("success", False):
                error_msg = data.get("errorMessage", "Unknown error")
                self.logger.warning(f"Risk metrics retrieval failed: {error_msg}")
                return {"error": error_msg}

            return data.get("risk", {})

        except requests.RequestException as e:
            self.logger.warning(f"Risk metrics request failed: {e}")
            return {"error": str(e)}
        except (KeyError, json.JSONDecodeError, TypeError) as e:
            self.logger.warning(f"Invalid risk metrics response: {e}")
            return {"error": str(e)}

    def get_account_statements(
        self,
        start_date: datetime.datetime | None = None,
        end_date: datetime.datetime | None = None,
        account_id: int | None = None,
        statement_type: str = "daily",
    ) -> list[dict]:
        """
        Get account statements for a date range.

        Args:
            start_date: Start date for statements (default: 30 days ago)
            end_date: End date for statements (default: now)
            account_id: Account ID. Uses default account if None.
            statement_type: Type of statement ("daily", "monthly", "trade")

        Returns:
            List[dict]: List of account statements

        Example:
            >>> statements = project_x.get_account_statements()
            >>> for stmt in statements:
            ...     print(f"Date: {stmt['date']} - Balance: ${stmt.get('balance', 0)}")
        """
        self._ensure_authenticated()

        if account_id is None:
            if not self.account_info:
                self.get_account_info()
            if not self.account_info:
                raise ProjectXError("No account information available")
            account_id = self.account_info.id

        # Default date range if not provided
        if start_date is None:
            start_date = datetime.datetime.now(self.timezone) - timedelta(days=30)
        if end_date is None:
            end_date = datetime.datetime.now(self.timezone)

        url = f"{self.base_url}/Account/statements"
        payload = {
            "accountId": account_id,
            "startTime": start_date.isoformat(),
            "endTime": end_date.isoformat(),
            "type": statement_type,
        }

        try:
            self.api_call_count += 1
            response = self.session.post(url, headers=self.headers, json=payload)
            self._handle_response_errors(response)

            data = response.json()
            if not data.get("success", False):
                error_msg = data.get("errorMessage", "Unknown error")
                self.logger.warning(f"Statements retrieval failed: {error_msg}")
                return []

            return data.get("statements", [])

        except requests.RequestException as e:
            self.logger.warning(f"Statements request failed: {e}")
            return []
        except (KeyError, json.JSONDecodeError, TypeError) as e:
            self.logger.warning(f"Invalid statements response: {e}")
            return []

    def get_tick_data(
        self,
        instrument: str,
        start_time: datetime.datetime | None = None,
        end_time: datetime.datetime | None = None,
        limit: int = 1000,
    ) -> pl.DataFrame | None:
        """
        Retrieve tick-level market data for an instrument.

        Args:
            instrument: Symbol of the instrument (e.g., "MGC", "MNQ")
            start_time: Start time for tick data (default: 1 hour ago)
            end_time: End time for tick data (default: now)
            limit: Maximum number of ticks to retrieve

        Returns:
            pl.DataFrame: DataFrame with tick data (timestamp, price, volume, side)
            None: If no data is available

        Example:
            >>> ticks = project_x.get_tick_data("MGC", limit=500)
            >>> print(f"Retrieved {len(ticks)} ticks")
        """
        self._ensure_authenticated()

        # Get instrument details
        instrument_obj = self.get_instrument(instrument)
        if not instrument_obj:
            raise ProjectXInstrumentError(f"Instrument '{instrument}' not found")

        # Default time range if not provided
        if start_time is None:
            start_time = datetime.datetime.now(self.timezone) - timedelta(hours=1)
        if end_time is None:
            end_time = datetime.datetime.now(self.timezone)

        url = f"{self.base_url}/History/retrieveTicks"
        payload = {
            "contractId": instrument_obj.id,
            "startTime": start_time.isoformat(),
            "endTime": end_time.isoformat(),
            "limit": limit,
        }

        try:
            self.api_call_count += 1
            response = self.session.post(url, headers=self.headers, json=payload)
            self._handle_response_errors(response)

            data = response.json()
            if not data.get("success", False):
                error_msg = data.get("errorMessage", "Unknown error")
                self.logger.warning(f"Tick data retrieval failed: {error_msg}")
                return None

            ticks = data.get("ticks", [])
            if not ticks:
                return None

            # Create DataFrame with polars
            df = pl.from_dicts(ticks).sort("timestamp")

            # Convert timestamp to datetime and handle timezone properly
            df = df.with_columns(
                pl.col("timestamp")
                .str.to_datetime()
                .dt.replace_time_zone("UTC")
                .dt.convert_time_zone(str(self.timezone.zone))
            )

            return df

        except requests.RequestException as e:
            self.logger.warning(f"Tick data request failed: {e}")
            return None
        except (KeyError, json.JSONDecodeError, ValueError) as e:
            self.logger.warning(f"Invalid tick data response: {e}")
            return None

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
