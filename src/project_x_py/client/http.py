"""
Async HTTP/2 client, rate-limiting, and robust error handling for ProjectX SDK.

Author: @TexasCoding
Date: 2025-08-02

Overview:
    Implements the async HTTP/2 client logic for ProjectX API access, including connection
    pooling, automatic retry on transient errors, and adaptive rate limiting. All API calls
    are decorated for rate control and network resilience, with detailed error mapping for
    4xx and 5xx responses. Integrates with authentication for seamless token refresh and
    propagates network/runtime errors as SDK-specific exceptions.

Key Features:
    - HTTP/2 async client with connection pooling (via httpx)
    - Decorators for automatic rate limiting and network retry logic
    - Error mapping: raises precise exceptions for 4xx/5xx responses
    - Automatic JWT token refresh on 401/expired session
    - API call logging, health status, and statistics
    - Centralized request/response handling for all mixins

Example Usage:
    ```python
    import asyncio
    from project_x_py import ProjectX


    async def main():
        # V3: Monitor client performance and health metrics
        async with ProjectX.from_env() as client:
            await client.authenticate()

            # Perform some operations
            await client.get_instrument("MNQ")
            await client.get_bars("MNQ", days=1)

            # Check performance statistics
            stats = await client.get_health_status()
            print(f"API Calls: {stats['api_calls']}")
            print(f"Cache Hits: {stats['cache_hits']}")
            print(f"Cache Hit Ratio: {stats['cache_hit_ratio']:.1%}")
            print(f"Active Connections: {stats['active_connections']}")


    asyncio.run(main())
    ```

See Also:
    - `project_x_py.client.base.ProjectXBase`
    - `project_x_py.client.auth.AuthenticationMixin`
    - `project_x_py.client.cache.CacheMixin`
"""

import asyncio
import time
from typing import TYPE_CHECKING, Any, TypeVar

import httpx

from project_x_py.exceptions import (
    OrderSubmissionUncertainError,
    ProjectXAuthenticationError,
    ProjectXConnectionError,
    ProjectXDataError,
    ProjectXError,
    ProjectXRateLimitError,
    ProjectXServerError,
)
from project_x_py.types.response_types import PerformanceStatsResponse
from project_x_py.utils import (
    ErrorMessages,
    LogContext,
    LogMessages,
    ProjectXLogger,
    format_error_message,
    handle_errors,
    handle_rate_limit,
    log_api_call,
)

if TYPE_CHECKING:
    from project_x_py.types import ProjectXClientProtocol

T = TypeVar("T")

logger = ProjectXLogger.get_logger(__name__)

MUTATING_ENDPOINTS = frozenset(
    {
        "/Order/place",
        "/Order/cancel",
        "/Order/modify",
        "/Position/closeContract",
        "/Position/partialCloseContract",
    }
)


def _is_mutating_request(method: str, endpoint: str) -> bool:
    """True when a retry would risk a duplicate live broker mutation."""
    return method.upper() in {"POST", "PUT", "PATCH", "DELETE"} and (
        endpoint in MUTATING_ENDPOINTS
    )


class HttpMixin:
    """Mixin class providing HTTP client functionality."""

    # These attributes are provided by the base class or other mixins
    config: Any  # ProjectXConfig
    base_url: str
    headers: dict[str, str]
    session_token: str
    rate_limiter: Any  # RateLimiter
    cache_hit_count: int
    api_call_count: int

    def __init__(self) -> None:
        """Initialize HTTP client attributes."""
        super().__init__()
        self._client: httpx.AsyncClient | None = None
        self.api_call_count = 0

    async def _create_client(self: "ProjectXClientProtocol") -> httpx.AsyncClient:
        """
        Create an optimized httpx async client with connection pooling and retries.

        This method configures the HTTP client with:
        - HTTP/2 support for improved performance
        - Connection pooling to reduce overhead
        - Automatic retries on transient failures
        - Custom timeout settings
        - Proper SSL verification

        Returns:
            httpx.AsyncClient: Configured async HTTP client
        """
        # Configure timeout
        timeout = httpx.Timeout(
            connect=5.0,  # Reduced from 10.0 for faster connection establishment
            read=self.config.timeout_seconds,
            write=self.config.timeout_seconds,
            pool=5.0,  # Reduced pool timeout for faster failover
        )

        # Configure optimized limits for high-frequency trading
        limits = httpx.Limits(
            max_keepalive_connections=50,  # Increased from 20 for more persistent connections
            max_connections=200,  # Increased from 100 for higher concurrency
            keepalive_expiry=60.0,  # Increased from 30 to maintain connections longer
        )

        # Create async client with HTTP/2 support
        client = httpx.AsyncClient(
            timeout=timeout,
            limits=limits,
            http2=True,
            verify=True,
            follow_redirects=False,
            headers={
                "User-Agent": "ProjectX-Python-SDK/4.0.1",
                "Accept": "application/json",
            },
        )

        return client

    async def _ensure_client(self: "ProjectXClientProtocol") -> httpx.AsyncClient:
        """
        Ensure HTTP client is initialized and ready for API requests.

        This method lazily initializes the HTTP client when needed, creating a new
        client instance if one doesn't exist. It's used internally before making
        any API requests to ensure a valid client connection is available.

        Returns:
            httpx.AsyncClient: The initialized HTTP client instance

        Note:
            This method is called automatically by _make_request and doesn't need
            to be called directly in normal usage.
        """
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    @handle_rate_limit()
    async def _make_request(
        self: "ProjectXClientProtocol",
        method: str,
        endpoint: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        retry_count: int = 0,
    ) -> dict[str, Any] | list[Any]:
        """
        Make an async HTTP request with error handling and retry logic.

        Mutating broker endpoints are never retried. A timeout, disconnect,
        5xx, or cancellation after the request may have been sent raises
        ``OrderSubmissionUncertainError`` so callers reconcile instead of
        duplicating a live order.
        """
        mutating = _is_mutating_request(method, endpoint)
        max_attempts = 1 if mutating else 3
        last_exception: Exception | None = None

        for attempt in range(max_attempts):
            try:
                return await self._execute_http_request(
                    method,
                    endpoint,
                    data=data,
                    params=params,
                    headers=headers,
                    retry_count=retry_count,
                )
            except asyncio.CancelledError:
                if mutating:
                    raise OrderSubmissionUncertainError(
                        "Order request was cancelled after it may have been "
                        "submitted. Reconcile against positions and orders "
                        "before retrying.",
                        payload=data or {},
                    ) from None
                raise
            except (ProjectXConnectionError, ProjectXServerError) as e:
                if mutating:
                    raise OrderSubmissionUncertainError(
                        "Order request failed after a transport error; the "
                        "broker may have accepted the order. Reconcile "
                        "before retrying.",
                        payload=data or {},
                    ) from e
                last_exception = e
                if attempt < max_attempts - 1:
                    delay = min(1.0 * (2.0**attempt), 60.0)
                    logger.warning(
                        f"Retry {attempt + 1}/{max_attempts} for _make_request "
                        f"after {type(e).__name__}, waiting {delay:.1f}s",
                        extra={
                            "attempt": attempt + 1,
                            "max_attempts": max_attempts,
                            "delay": delay,
                            "error_type": type(e).__name__,
                            "endpoint": endpoint,
                        },
                    )
                    await asyncio.sleep(delay)
                    continue
                raise

        if last_exception is not None:
            raise last_exception
        raise ProjectXError("Unexpected state in HTTP request retry")

    async def _execute_http_request(
        self: "ProjectXClientProtocol",
        method: str,
        endpoint: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        retry_count: int = 0,
    ) -> dict[str, Any] | list[Any]:
        """Send a single HTTP request. Callers handle retry policy."""
        with LogContext(
            logger,
            operation="api_request",
            method=method,
            endpoint=endpoint,
            has_data=data is not None,
            has_params=params is not None,
        ):
            logger.debug(
                LogMessages.API_REQUEST, extra={"method": method, "endpoint": endpoint}
            )

            client = await self._ensure_client()

            url = f"{self.base_url}{endpoint}"
            request_headers = {**self.headers, **(headers or {})}

            # Add authorization if we have a token
            if self.session_token and endpoint != "/Auth/loginKey":
                request_headers["Authorization"] = f"Bearer {self.session_token}"

            # Apply rate limiting
            await self.rate_limiter.acquire()

            self.api_call_count += 1
            start_time = time.time()

            try:
                # Shield the in-flight request so asyncio cancellation cannot
                # double-release httpx/httpcore connection-pool semaphores (#85).
                response = await asyncio.shield(
                    client.request(
                        method=method,
                        url=url,
                        json=data,
                        params=params,
                        headers=request_headers,
                    )
                )
            except asyncio.CancelledError:
                raise
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                raise ProjectXConnectionError(str(e)) from e

            # Log API call
            log_api_call(
                logger,
                method=method,
                endpoint=endpoint,
                status_code=response.status_code,
                duration=time.time() - start_time,
            )

            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", "60"))
                message = format_error_message(
                    ErrorMessages.API_RATE_LIMITED, retry_after=retry_after
                )
                raise ProjectXRateLimitError(message)

            # Handle successful responses
            if response.status_code in (200, 201, 204):
                if response.status_code == 204:
                    return {}
                try:
                    result: dict[str, Any] | list[Any] = response.json()
                    return result
                except Exception as e:
                    # JSON parsing failed
                    raise ProjectXDataError(
                        format_error_message(
                            ErrorMessages.DATA_PARSE_ERROR,
                            data_type="JSON",
                            reason=str(e),
                        )
                    ) from e

            # Handle authentication errors
            if response.status_code == 401:
                if endpoint != "/Auth/loginKey" and retry_count == 0:
                    # Try to refresh authentication
                    await self._refresh_authentication()
                    retry_result: dict[str, Any] | list[Any] = await self._make_request(
                        method=method,
                        endpoint=endpoint,
                        data=data,
                        params=params,
                        headers=headers,
                        retry_count=retry_count + 1,
                    )
                    return retry_result
                raise ProjectXAuthenticationError(ErrorMessages.AUTH_FAILED)

            # Handle client errors
            if 400 <= response.status_code < 500:
                error_msg = f"Client error: {response.status_code}"
                try:
                    error_data = response.json()
                    if "message" in error_data:
                        error_msg = error_data["message"]
                    elif "error" in error_data:
                        error_msg = error_data["error"]
                except Exception:
                    error_msg = response.text

                if response.status_code == 404:
                    raise ProjectXDataError(
                        format_error_message(
                            ErrorMessages.API_RESOURCE_NOT_FOUND, resource=endpoint
                        )
                    )
                else:
                    raise ProjectXError(error_msg)

            # Handle server errors
            if 500 <= response.status_code < 600:
                raise ProjectXServerError(
                    format_error_message(
                        ErrorMessages.API_SERVER_ERROR,
                        status_code=response.status_code,
                        message=response.text[:200],  # Limit message length
                    )
                )

            # Should never reach here, but required for type checking
            raise ProjectXError(f"Unexpected response status: {response.status_code}")

    @handle_errors("get health status")
    async def get_health_status(
        self: "ProjectXClientProtocol",
    ) -> PerformanceStatsResponse:
        """
        Get client statistics and performance metrics.

        Returns:
            A dictionary containing client-side statistics including API calls
            and cache performance.

        Example:
            >>> # V3: Get comprehensive performance metrics
            >>> status = await client.get_health_status()
            >>> print(f"API Calls: {status['api_calls']}")
            >>> print(f"Cache Hits: {status['cache_hits']}")
            >>> print(f"Cache Hit Ratio: {status['cache_hit_ratio']:.2%}")
            >>> print(f"Total Requests: {status['total_requests']}")
            >>> print(f"Active Connections: {status['active_connections']}")
        """
        # Calculate client statistics
        total_requests = self.cache_hit_count + self.api_call_count
        cache_hit_ratio = (
            self.cache_hit_count / total_requests if total_requests > 0 else 0
        )
        cache_misses = self.api_call_count  # API calls are essentially cache misses

        return {
            "api_calls": self.api_call_count,
            "cache_hits": self.cache_hit_count,
            "cache_misses": cache_misses,
            "cache_hit_ratio": cache_hit_ratio,
            "total_requests": total_requests,
            "active_connections": 1
            if self._client and not self._client.is_closed
            else 0,
        }
