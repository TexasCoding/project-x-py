"""
ProjectX Custom Exceptions

Author: TexasCoding
Date: June 2025

This module defines custom exception classes for the ProjectX API client.

"""


class ProjectXError(Exception):
    """Base exception for ProjectX API errors."""

    def __init__(
        self,
        message: str,
        error_code: int | None = None,
        response_data: dict | None = None,
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


class ProjectXPositionError(ProjectXError):
    """Position management errors."""


class ProjectXInstrumentError(ProjectXError):
    """Instrument-related errors."""
