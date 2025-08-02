"""
ProjectX Custom Exceptions

Author: TexasCoding
Date: June 2025

This module defines custom exception classes for the ProjectX API client.
"""


class ProjectXError(Exception):
    """Base exception for all Project X errors."""
    pass


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
