"""
ProjectX Configuration Management

Author: @TexasCoding
Date: 2025-08-02

Overview:
    Handles configuration for the ProjectX client, including environment variables,
    config files, and default settings. Provides comprehensive configuration management
    with priority-based loading, validation, and customization for different deployment
    environments.

Key Features:
    - Priority-based configuration loading (Environment > Config file > Defaults)
    - Environment variable support with automatic type conversion
    - Configuration file management with JSON format
    - Configuration validation and error handling
    - Custom configuration creation for different endpoints
    - Authentication configuration management
    - Environment setup validation and status checking

Configuration Sources:
    - Environment variables with PROJECTX_ prefix
    - JSON configuration files with customizable paths
    - Default configuration with TopStepX endpoints
    - Custom configuration for different ProjectX deployments

Example Usage:
    ```python
    from project_x_py.config import (
        load_default_config,
        create_custom_config,
        ConfigManager,
        check_environment,
    )

    # Load default configuration
    config = load_default_config()

    # Create custom configuration
    custom_config = create_custom_config(
        user_hub_url="https://custom.projectx.com/hubs/user",
        market_hub_url="https://custom.projectx.com/hubs/market",
    )

    # Use configuration manager
    manager = ConfigManager("config.json")
    config = manager.load_config()

    # Check environment setup
    status = check_environment()
    if status["auth_configured"]:
        print("Authentication configured")
    else:
        print(f"Missing: {status['missing_required']}")
    ```

Configuration Priority:
    1. Environment variables (highest priority)
    2. Configuration file (JSON format)
    3. Default values (lowest priority)

Environment Variables:
    - PROJECTX_API_URL: Base API URL
    - PROJECTX_REALTIME_URL: WebSocket URL
    - PROJECTX_USER_HUB_URL: User hub URL
    - PROJECTX_MARKET_HUB_URL: Market hub URL
    - PROJECTX_TIMEZONE: Timezone for timestamps
    - PROJECTX_TIMEOUT_SECONDS: Request timeout
    - PROJECTX_RETRY_ATTEMPTS: Retry attempts
    - PROJECTX_RETRY_DELAY_SECONDS: Retry delay
    - PROJECTX_REQUESTS_PER_MINUTE: Rate limiting
    - PROJECTX_BURST_LIMIT: Burst limit

Authentication Variables:
    - PROJECT_X_API_KEY: API key for authentication
    - PROJECT_X_USERNAME: Username for authentication

Configuration Validation:
    - URL format validation for all endpoints
    - Numeric value validation for timeouts and limits
    - Timezone validation using pytz
    - Authentication credential validation
    - Comprehensive error reporting

See Also:
    - `models.ProjectXConfig`: Configuration data model
    - `utils.environment`: Environment variable utilities
"""

import logging
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

import orjson

from project_x_py.models import ProjectXConfig
from project_x_py.utils import get_env_var

logger = logging.getLogger(__name__)

__all__ = [
    "ConfigManager",
    "check_environment",
    "create_config_template",
    "create_custom_config",
    "get_default_config_path",
    "load_default_config",
    "load_topstepx_config",
]


class ConfigManager:
    """
    Configuration manager for ProjectX client.

    Handles loading configuration from:
    1. Environment variables
    2. Configuration files
    3. Default values

    Priority order: Environment variables > Config file > Defaults
    """

    def __init__(self, config_file: str | Path | None = None):
        """
        Initialize configuration manager.

        Args:
            config_file: Optional path to configuration file
        """
        self.config_file: Path | None = Path(config_file) if config_file else None
        self._config: ProjectXConfig | None = None

    def load_config(self) -> ProjectXConfig:
        """
        Load configuration with priority order.

        Returns:
            ProjectXConfig instance
        """
        if self._config is not None:
            return self._config

        # Start with default configuration
        config_dict = asdict(ProjectXConfig())

        # Override with config file if it exists
        if self.config_file and self.config_file.exists():
            try:
                file_config = self._load_config_file()
                config_dict.update(file_config)
                logger.info(f"Loaded configuration from {self.config_file}")
            except Exception as e:
                logger.warning(f"Failed to load config file {self.config_file}: {e}")

        # Override with environment variables
        env_config = self._load_env_config()
        config_dict.update(env_config)

        self._config = ProjectXConfig(**config_dict)
        return self._config

    def _load_config_file(self) -> dict[str, Any]:
        """Load configuration from JSON file."""
        if not self.config_file or not self.config_file.exists():
            return {}

        try:
            with open(self.config_file, encoding="utf-8") as f:
                content = f.read()
                data = orjson.loads(content)
                return dict(data) if isinstance(data, dict) else {}
        except (orjson.JSONDecodeError, OSError) as e:
            logger.error(f"Error loading config file: {e}")
            return {}

    def _load_env_config(self) -> dict[str, Any]:
        """Load configuration from environment variables."""
        env_config = {}

        # Map environment variable names to config keys
        env_mappings = {
            "PROJECTX_API_URL": "api_url",
            "PROJECTX_REALTIME_URL": "realtime_url",
            "PROJECTX_USER_HUB_URL": "user_hub_url",
            "PROJECTX_MARKET_HUB_URL": "market_hub_url",
            "PROJECTX_TIMEZONE": "timezone",
            "PROJECTX_TIMEOUT_SECONDS": ("timeout_seconds", int),
            "PROJECTX_RETRY_ATTEMPTS": ("retry_attempts", int),
            "PROJECTX_RETRY_DELAY_SECONDS": ("retry_delay_seconds", float),
            "PROJECTX_REQUESTS_PER_MINUTE": ("requests_per_minute", int),
            "PROJECTX_BURST_LIMIT": ("burst_limit", int),
        }

        for env_var, config_key in env_mappings.items():
            value = os.environ.get(env_var)
            if value is not None:
                if isinstance(config_key, tuple):
                    key, value_type = config_key
                    try:
                        env_config[key] = value_type(value)
                    except ValueError as e:
                        logger.warning(f"Invalid value for {env_var}: {value} ({e})")
                else:
                    env_config[config_key] = value

        return env_config

    def save_config(
        self,
        config: ProjectXConfig,
        file_path: str | Path | None = None,
    ) -> None:
        """
        Save configuration to file.

        Args:
            config: Configuration to save
            file_path: Optional path to save to (uses self.config_file if None)
        """
        target_file = Path(file_path) if file_path else self.config_file

        if target_file is None:
            raise ValueError("No config file path specified")

        try:
            # Create directory if it doesn't exist
            target_file.parent.mkdir(parents=True, exist_ok=True)

            # Convert config to dict and save as JSON
            config_dict = asdict(config)
            with open(target_file, "wb") as f:
                f.write(orjson.dumps(config_dict, option=orjson.OPT_INDENT_2))

            logger.info(f"Configuration saved to {target_file}")

        except Exception as e:
            logger.error(f"Failed to save config to {target_file}: {e}")
            raise

    def get_auth_config(self) -> dict[str, str]:
        """
        Get authentication configuration from environment variables.

        Returns:
            Dictionary with authentication settings

        Raises:
            ValueError: If required authentication variables are missing or invalid
        """
        api_key = get_env_var("PROJECT_X_API_KEY", required=True)
        username = get_env_var("PROJECT_X_USERNAME", required=True)

        if not api_key:
            raise ValueError("PROJECT_X_API_KEY environment variable is required")
        if not username:
            raise ValueError("PROJECT_X_USERNAME environment variable is required")

        if not isinstance(api_key, str) or len(api_key) < 10:
            raise ValueError(
                "Invalid PROJECT_X_API_KEY format - must be a string longer than 10 characters"
            )

        return {"api_key": api_key, "username": username}

    def validate_config(self, config: ProjectXConfig) -> bool:
        """
        Validate configuration settings.

        Args:
            config: Configuration to validate

        Returns:
            True if configuration is valid

        Raises:
            ValueError: If configuration is invalid
        """
        errors: list[str] = []

        # Validate URLs
        required_urls: list[str] = [
            "api_url",
            "realtime_url",
            "user_hub_url",
            "market_hub_url",
        ]
        for url_field in required_urls:
            url = getattr(config, url_field)
            if not url or not isinstance(url, str):
                errors.append(f"{url_field} must be a non-empty string")
            elif not url.startswith(("http://", "https://", "wss://")):
                errors.append(f"{url_field} must be a valid URL")
            elif url.startswith("http://"):
                from urllib.parse import urlparse

                host = (urlparse(url).hostname or "").lower()
                if host not in {"localhost", "127.0.0.1"}:
                    errors.append(
                        f"{url_field} must use HTTPS (http:// is only allowed "
                        "for localhost)"
                    )

        # Validate numeric settings
        if config.timeout_seconds <= 0:
            errors.append("timeout_seconds must be positive")
        if config.retry_attempts < 0:
            errors.append("retry_attempts must be non-negative")
        if config.retry_delay_seconds < 0:
            errors.append("retry_delay_seconds must be non-negative")
        if config.requests_per_minute <= 0:
            errors.append("requests_per_minute must be positive")
        if config.burst_limit <= 0:
            errors.append("burst_limit must be positive")

        # Validate timezone
        try:
            import pytz

            pytz.timezone(config.timezone)
        except Exception:
            errors.append(f"Invalid timezone: {config.timezone}")

        if errors:
            raise ValueError(f"Configuration validation failed: {'; '.join(errors)}")

        return True


def load_default_config() -> ProjectXConfig:
    """
    Load default configuration with environment variable overrides.

    Returns:
        ProjectXConfig instance
    """
    manager = ConfigManager()
    return manager.load_config()


def load_topstepx_config() -> ProjectXConfig:
    """
    Load configuration for TopStepX endpoints (uses default config).

    Returns:
        ProjectXConfig: Configuration with TopStepX URLs
    """
    return load_default_config()


def create_custom_config(
    user_hub_url: str, market_hub_url: str, **kwargs: Any
) -> ProjectXConfig:
    """
    Create custom configuration with specified URLs.

    Args:
        user_hub_url: Custom user hub URL
        market_hub_url: Custom market hub URL
        **kwargs: Additional configuration parameters

    Returns:
        ProjectXConfig: Custom configuration instance
    """
    config = load_default_config()
    config.user_hub_url = user_hub_url
    config.market_hub_url = market_hub_url

    # Apply any additional kwargs
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)

    return config


def create_config_template(file_path: str | Path) -> None:
    """
    Create a configuration file template.

    Args:
        file_path: Path where to create the template
    """
    template_config = ProjectXConfig()
    config_dict: dict[str, Any] = asdict(template_config)

    # Add comments to the template
    template = {
        "_comment": "ProjectX Configuration Template",
        "_description": {
            "api_url": "Base URL for the ProjectX API",
            "realtime_url": "WebSocket URL for real-time data",
            "user_hub_url": "SignalR hub URL for user events",
            "market_hub_url": "SignalR hub URL for market data",
            "timezone": "Timezone for timestamp handling",
            "timeout_seconds": "Request timeout in seconds",
            "retry_attempts": "Number of retry attempts for failed requests",
            "retry_delay_seconds": "Delay between retry attempts",
            "requests_per_minute": "Rate limiting - requests per minute",
            "burst_limit": "Rate limiting - burst limit",
        },
        **config_dict,
    }

    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(file_path, "wb") as f:
        f.write(orjson.dumps(template, option=orjson.OPT_INDENT_2))

    logger.info(f"Configuration template created at {file_path}")


def get_default_config_path() -> Path:
    """
    Get the default configuration file path.

    Returns:
        Path to default config file
    """
    # Try user config directory first, then current directory
    possible_paths = [
        Path.home() / ".config" / "projectx" / "config.json",
        Path.cwd() / "projectx_config.json",
        Path.cwd() / ".projectx_config.json",
    ]

    # Return first existing file, or first path as default
    for path in possible_paths:
        if path.exists():
            return path

    return possible_paths[0]


# Environment variable validation helpers
def check_environment() -> dict[str, Any]:
    """
    Check environment setup for ProjectX.

    Returns:
        Dictionary with environment status
    """
    status: dict[str, Any] = {
        "auth_configured": False,
        "config_file_exists": False,
        "environment_overrides": [],
        "missing_required": [],
    }

    # Check required auth variables
    try:
        api_key = get_env_var("PROJECT_X_API_KEY")
        username = get_env_var("PROJECT_X_USERNAME")

        if api_key and username:
            status["auth_configured"] = True
        else:
            if not api_key:
                status["missing_required"].append("PROJECT_X_API_KEY")
            if not username:
                status["missing_required"].append("PROJECT_X_USERNAME")
    except Exception:
        status["missing_required"].extend(["PROJECT_X_API_KEY", "PROJECT_X_USERNAME"])

    # Check for config file
    default_path: Path = get_default_config_path()
    if default_path.exists():
        status["config_file_exists"] = True
        status["config_file_path"] = str(default_path)

    # Check for environment overrides
    env_vars: list[str] = [
        "PROJECTX_API_URL",
        "PROJECTX_REALTIME_URL",
        "PROJECTX_USER_HUB_URL",
        "PROJECTX_MARKET_HUB_URL",
        "PROJECTX_TIMEZONE",
        "PROJECTX_TIMEOUT_SECONDS",
        "PROJECTX_RETRY_ATTEMPTS",
        "PROJECTX_RETRY_DELAY_SECONDS",
        "PROJECTX_REQUESTS_PER_MINUTE",
        "PROJECTX_BURST_LIMIT",
    ]

    for var in env_vars:
        if os.environ.get(var):
            status["environment_overrides"].append(var)

    return status
