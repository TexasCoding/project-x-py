"""
ProjectX API Client for TopStepX Futures Trading

A comprehensive Python client for the ProjectX Gateway API, providing access to:
- Market data retrieval
- Account management
- Order placement, modification, and cancellation
- Position management
- Trade history and analysis
- Real-time data streams

Author: TexasCoding
Date: June 2025
"""

from typing import Optional

__version__ = "0.2.0"
__author__ = "TexasCoding"

# Core client classes
from .client import ProjectX
from .realtime import ProjectXRealtimeClient
from .realtime_data_manager import ProjectXRealtimeDataManager

# Data models
from .models import (
    # Configuration
    ProjectXConfig,
    # Trading entities
    Instrument,
    Account,
    Order,
    OrderPlaceResponse,
    Position,
    Trade,
    BracketOrderResponse,
)

# Exceptions
from .exceptions import (
    ProjectXError,
    ProjectXAuthenticationError,
    ProjectXServerError,
    ProjectXRateLimitError,
    ProjectXConnectionError,
    ProjectXDataError,
    ProjectXOrderError,
    ProjectXPositionError,
    ProjectXInstrumentError,
)

# Configuration management
from .config import (
    ConfigManager,
    load_default_config,
    create_config_template,
    check_environment,
)

# Utility functions
from .utils import (
    setup_logging,
    get_env_var,
    format_price,
    format_volume,
    is_market_hours,
    RateLimiter,
)

# Convenience imports for backward compatibility
from .utils import get_polars_rows as _get_polars_rows
from .utils import get_polars_last_value as _get_polars_last_value


# Public API - these are the main classes users should import
__all__ = [
    # Main client classes
    "ProjectX",
    "ProjectXRealtimeClient",
    "ProjectXRealtimeDataManager",
    # Configuration
    "ProjectXConfig",
    "ConfigManager",
    "load_default_config",
    "create_config_template",
    "check_environment",
    # Data models
    "Instrument",
    "Account",
    "Order",
    "OrderPlaceResponse",
    "Position",
    "Trade",
    "BracketOrderResponse",
    # Exceptions
    "ProjectXError",
    "ProjectXAuthenticationError",
    "ProjectXServerError",
    "ProjectXRateLimitError",
    "ProjectXConnectionError",
    "ProjectXDataError",
    "ProjectXOrderError",
    "ProjectXPositionError",
    "ProjectXInstrumentError",
    # Utilities
    "setup_logging",
    "get_env_var",
    "format_price",
    "format_volume",
    "is_market_hours",
    "RateLimiter",
]


def get_version() -> str:
    """Get the current version of the ProjectX package."""
    return __version__


def quick_start() -> dict:
    """
    Get quick start information for the ProjectX package.

    Returns:
        Dict with setup instructions and examples
    """
    return {
        "version": __version__,
        "setup_instructions": [
            "1. Set environment variables:",
            "   export PROJECT_X_API_KEY='your_api_key'",
            "   export PROJECT_X_USERNAME='your_username'",
            "",
            "2. Basic usage:",
            "   from project_x_py import ProjectX",
            "   client = ProjectX.from_env()",
            "   instruments = client.search_instruments('MGC')",
            "   data = client.get_data('MGC', days=5)",
        ],
        "examples": {
            "basic_client": "client = ProjectX.from_env()",
            "get_instruments": "instruments = client.search_instruments('MGC')",
            "get_data": "data = client.get_data('MGC', days=5, interval=15)",
            "place_order": "response = client.place_market_order('CONTRACT_ID', 0, 1)",
            "get_positions": "positions = client.search_open_positions()",
        },
        "documentation": "https://github.com/your-repo/project-x-py",
        "support": "Create an issue at https://github.com/your-repo/project-x-py/issues",
    }


def check_setup() -> dict:
    """
    Check if the ProjectX package is properly set up.

    Returns:
        Dict with setup status and recommendations
    """
    try:
        from .config import check_environment

        env_status = check_environment()

        status = {
            "environment_configured": env_status["auth_configured"],
            "config_file_exists": env_status["config_file_exists"],
            "issues": [],
            "recommendations": [],
        }

        if not env_status["auth_configured"]:
            status["issues"].append("Missing required environment variables")
            status["recommendations"].extend(
                [
                    "Set PROJECT_X_API_KEY environment variable",
                    "Set PROJECT_X_USERNAME environment variable",
                ]
            )

        if env_status["missing_required"]:
            status["missing_variables"] = env_status["missing_required"]

        if env_status["environment_overrides"]:
            status["environment_overrides"] = env_status["environment_overrides"]

        if not status["issues"]:
            status["status"] = "Ready to use"
        else:
            status["status"] = "Setup required"

        return status

    except Exception as e:
        return {
            "status": "Error checking setup",
            "error": str(e),
            "recommendations": [
                "Ensure all dependencies are installed",
                "Check package installation",
            ],
        }


# Package-level convenience functions
def create_client(
    username: Optional[str] = None,
    api_key: Optional[str] = None,
    config: Optional[ProjectXConfig] = None,
) -> ProjectX:
    """
    Create a ProjectX client with flexible initialization.

    Args:
        username: Username (uses env var if None)
        api_key: API key (uses env var if None)
        config: Configuration object (uses defaults if None)

    Returns:
        ProjectX client instance

    Example:
        >>> # Using environment variables
        >>> client = create_client()
        >>> # Using explicit credentials
        >>> client = create_client("username", "api_key")
    """
    if username is None or api_key is None:
        return ProjectX.from_env(config=config)
    else:
        return ProjectX(username=username, api_key=api_key, config=config)


def create_realtime_client(
    jwt_token: str, account_id: str, config: Optional[ProjectXConfig] = None
) -> ProjectXRealtimeClient:
    """
    Create a ProjectX real-time client.

    Args:
        jwt_token: JWT authentication token
        account_id: Account ID for subscriptions
        config: Configuration object (uses defaults if None)

    Returns:
        ProjectXRealtimeClient instance
    """
    if config is None:
        config = load_default_config()

    return ProjectXRealtimeClient(
        jwt_token=jwt_token,
        account_id=account_id,
        user_hub_url=config.user_hub_url,
        market_hub_url=config.market_hub_url,
    )


def create_data_manager(
    instrument: str,
    project_x: ProjectX,
    account_id: str,
    config: Optional[ProjectXConfig] = None,
) -> ProjectXRealtimeDataManager:
    """
    Create a ProjectX real-time data manager.

    Args:
        instrument: Trading instrument symbol
        project_x: ProjectX client instance
        account_id: Account ID for real-time subscriptions
        config: Configuration object (uses defaults if None)

    Returns:
        ProjectXRealtimeDataManager instance
    """
    if config is None:
        config = load_default_config()

    return ProjectXRealtimeDataManager(
        instrument=instrument,
        project_x=project_x,
        account_id=account_id,
        user_hub_url=config.user_hub_url,
        market_hub_url=config.market_hub_url,
        timezone=config.timezone,
    )
