"""
ProjectX Custom Exceptions

Author: @TexasCoding
Date: 2025-08-02

Overview:
    Defines custom exception classes for the ProjectX API client. Provides
    comprehensive error handling with categorized exceptions for different
    types of errors, including authentication, network, data validation,
    and trading-specific errors.

Key Features:
    - Hierarchical exception structure with base ProjectXError
    - Categorized exceptions for different error types
    - Error code support for programmatic error handling
    - Response data preservation for debugging
    - Comprehensive error context and metadata
    - Type-safe exception handling across the SDK

Exception Categories:
    - Authentication: Login, token, and permission errors
    - Connection: Network, timeout, and SSL errors
    - Server: Server-side errors and API issues
    - Client: Client-side errors and invalid requests
    - Data: Validation, parsing, and format errors
    - Trading: Order, position, and instrument errors

Example Usage:
    ```python
    from project_x_py.exceptions import (
        ProjectXError,
        ProjectXAuthenticationError,
        ProjectXRateLimitError,
        ProjectXOrderError,
    )

    try:
        await client.authenticate()
    except ProjectXAuthenticationError as e:
        print(f"Authentication failed: {e}")
        print(f"Error code: {e.error_code}")

    try:
        await order_manager.place_order(...)
    except ProjectXRateLimitError as e:
        print(f"Rate limit exceeded: {e}")
        # Handle rate limiting with retry logic

    try:
        await client.get_instrument("INVALID")
    except ProjectXInstrumentError as e:
        print(f"Instrument error: {e}")

    # Generic error handling
    try:
        # API operation
        pass
    except ProjectXError as e:
        print(f"ProjectX error: {e}")
        if e.response_data:
            print(f"Response data: {e.response_data}")
    ```

Exception Hierarchy:
    - ProjectXError: Base exception for all ProjectX errors
    - ProjectXAuthenticationError: Authentication and authorization errors
    - ProjectXRateLimitError: Rate limiting and throttling errors
    - ProjectXServerError: Server-side errors (5xx status codes)
    - ProjectXClientError: Client-side errors (4xx status codes)
    - ProjectXConnectionError: Network and connection errors
    - ProjectXDataError: Data validation and processing errors
    - ProjectXOrderError: Order placement and management errors
    - ProjectXPositionError: Position management errors
    - ProjectXInstrumentError: Instrument-related errors

Error Handling Features:
    - Error code support for programmatic handling
    - Response data preservation for debugging
    - Comprehensive error context and metadata
    - Type-safe exception handling
    - Hierarchical error categorization
    - Consistent error message formatting

See Also:
    - `utils.error_handler`: Error handling decorators and utilities
    - `utils.error_messages`: Standardized error messages
"""

from typing import Any

__all__ = [
    "InvalidOrderParameters",
    "OrderSubmissionUncertainError",
    "ProjectXAuthenticationError",
    "ProjectXClientError",
    "ProjectXConnectionError",
    "ProjectXDataError",
    "ProjectXError",
    "ProjectXInstrumentError",
    "ProjectXOrderError",
    "ProjectXPositionError",
    "ProjectXRateLimitError",
    "ProjectXServerError",
    "RiskLimitExceeded",
]


class ProjectXError(Exception):
    """Base exception for ProjectX API errors."""

    def __init__(
        self,
        message: str,
        error_code: int | None = None,
        response_data: dict[str, Any] | None = None,
    ):
        """
        Initialize ProjectX error.

        Args:
            message: Error message
            error_code: Optional error code
            response_data: Optional response data from API
        """
        super().__init__(message)
        self.error_code = error_code
        self.response_data = response_data or {}


class ProjectXAuthenticationError(ProjectXError):
    """Authentication-related errors."""


class ProjectXRateLimitError(ProjectXError):
    """Rate limiting errors."""


class ProjectXServerError(ProjectXError):
    """Server-side errors (5xx)."""


class ProjectXClientError(ProjectXError):
    """Client-side errors (4xx)."""


class ProjectXConnectionError(ProjectXError):
    """Connection and network errors."""


class ProjectXDataError(ProjectXError):
    """Data validation and processing errors."""


class ProjectXOrderError(ProjectXError):
    """Order placement and management errors."""


class OrderSubmissionUncertainError(ProjectXOrderError):
    """The order request may have reached the broker; do not assume it failed.

    Raised when cancellation or a transport error occurs after the HTTP request
    may already have been sent. Callers must reconcile against open orders,
    positions, and trades instead of flattening as if the order never existed.
    """

    def __init__(
        self,
        message: str,
        error_code: int | None = None,
        response_data: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ):
        super().__init__(message, error_code=error_code, response_data=response_data)
        self.payload = payload or {}


class ProjectXPositionError(ProjectXError):
    """Position management errors."""


class ProjectXInstrumentError(ProjectXError):
    """Instrument-related errors."""


class RiskLimitExceeded(ProjectXError):
    """Risk limit exceeded errors."""


class InvalidOrderParameters(ProjectXError):
    """Invalid order parameters errors."""
