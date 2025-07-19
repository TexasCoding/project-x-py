"""
ProjectX Configuration Management

Author: TexasCoding
Date: June 2025

This module handles configuration for the ProjectX client, including
environment variables, config files, and default settings.

"""

import json
import logging
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .models import ProjectXConfig
from .utils import get_env_var

logger = logging.getLogger(__name__)


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
        self.config_file = Path(config_file) if config_file else None
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
            with open(self.config_file) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
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

    def save_config(self, config: ProjectXConfig, file_path: str | Path | None = None):
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
            with open(target_file, "w") as f:
                json.dump(config_dict, f, indent=2)

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
        errors = []

        # Validate URLs
        required_urls = ["api_url", "realtime_url", "user_hub_url", "market_hub_url"]
        for url_field in required_urls:
            url = getattr(config, url_field)
            if not url or not isinstance(url, str):
                errors.append(f"{url_field} must be a non-empty string")
            elif not url.startswith(("http://", "https://", "wss://")):
                errors.append(f"{url_field} must be a valid URL")

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


def create_config_template(file_path: str | Path) -> None:
    """
    Create a configuration file template.

    Args:
        file_path: Path where to create the template
    """
    template_config = ProjectXConfig()
    config_dict = asdict(template_config)

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

    with open(file_path, "w") as f:
        json.dump(template, f, indent=2)

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
    status = {
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
    default_path = get_default_config_path()
    if default_path.exists():
        status["config_file_exists"] = True
        status["config_file_path"] = str(default_path)

    # Check for environment overrides
    env_vars = [
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
