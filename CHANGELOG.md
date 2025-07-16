# Changelog

All notable changes to the ProjectX Python client will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2025-01-28

### Added
- **Modular Architecture**: Split large monolithic file into logical modules
  - `client.py` - Main ProjectX client class
  - `models.py` - Data models and configuration
  - `exceptions.py` - Custom exception hierarchy
  - `utils.py` - Utility functions and helpers
  - `config.py` - Configuration management
- **Enhanced Error Handling**: Comprehensive exception hierarchy with specific error types
  - `ProjectXAuthenticationError` for auth failures
  - `ProjectXServerError` for 5xx errors
  - `ProjectXRateLimitError` for rate limiting
  - `ProjectXConnectionError` for network issues
  - `ProjectXDataError` for data validation errors
- **Configuration Management**: 
  - Environment variable support with `PROJECTX_*` prefix
  - JSON configuration file support
  - Default configuration with overrides
  - Configuration validation and templates
- **Professional Package Structure**:
  - Proper `pyproject.toml` with optional dependencies
  - Comprehensive README with examples
  - MIT license
  - Test framework setup with pytest
  - Development tools configuration (ruff, mypy, black)
- **Enhanced API Design**:
  - Factory methods: `ProjectX.from_env()`, `ProjectX.from_config_file()`
  - Improved type hints throughout
  - Better documentation and examples
  - Consistent error handling patterns
- **Utility Functions**:
  - `setup_logging()` for consistent logging
  - `get_env_var()` for environment variable handling
  - `format_price()` and `format_volume()` for display
  - `is_market_hours()` for market timing
  - `RateLimiter` class for API rate limiting

### Changed
- **Breaking**: Restructured package imports - use `from project_x_py import ProjectX` instead of importing from `__init__.py`
- **Breaking**: Configuration now uses `ProjectXConfig` dataclass instead of hardcoded values
- **Improved**: Better error messages with specific exception types
- **Enhanced**: Client initialization with lazy authentication
- **Updated**: Package metadata and PyPI classifiers

### Improved
- **Documentation**: Comprehensive README with installation, usage, and examples
- **Code Quality**: Improved type hints, docstrings, and code organization
- **Testing**: Basic test framework with pytest fixtures and mocks
- **Development**: Better development workflow with linting and formatting tools

### Dependencies
- **Core**: `polars>=1.31.0`, `pytz>=2025.2`, `requests>=2.32.4`
- **Optional Realtime**: `signalrcore>=0.9.5`, `websocket-client>=1.0.0`
- **Development**: `pytest`, `ruff`, `mypy`, `black`, `isort`

## [0.1.0] - 2025-01-01

### Added
- Initial release with basic trading functionality
- ProjectX Gateway API client
- Real-time data management via WebSocket
- Order placement, modification, and cancellation
- Position and trade management
- Historical market data retrieval
- Multi-timeframe data synchronization

### Features
- Authentication with TopStepX API
- Account management
- Instrument search and contract details
- OHLCV historical data with polars DataFrames
- Real-time market data streams
- Level 2 market depth data
- Comprehensive logging

---

## Release Notes

### Upgrading to v0.2.0

If you're upgrading from v0.1.0, please note the following breaking changes:

1. **Import Changes**:
   ```python
   # Old (v0.1.0)
   from project_x_py import ProjectX
   
   # New (v0.2.0) - same import, but underlying structure changed
   from project_x_py import ProjectX  # Still works
   ```

2. **Environment Variables**:
   ```bash
   # Required (same as before)
   export PROJECT_X_API_KEY="your_api_key"
   export PROJECT_X_USERNAME="your_username"
   
   # New optional configuration variables
   export PROJECTX_API_URL="https://api.topstepx.com/api"
   export PROJECTX_TIMEOUT_SECONDS="30"
   export PROJECTX_RETRY_ATTEMPTS="3"
   ```

3. **Client Initialization**:
   ```python
   # Recommended new approach
   client = ProjectX.from_env()  # Uses environment variables
   
   # Or with explicit credentials (same as before)
   client = ProjectX(username="user", api_key="key")
   
   # Or with custom configuration
   config = ProjectXConfig(timeout_seconds=60)
   client = ProjectX.from_env(config=config)
   ```

4. **Error Handling**:
   ```python
   # New specific exception types
   try:
       client = ProjectX.from_env()
       account = client.get_account_info()
   except ProjectXAuthenticationError:
       print("Authentication failed")
   except ProjectXServerError:
       print("Server error")
   except ProjectXError:
       print("General ProjectX error")
   ```

### Migration Guide

1. **Update imports**: No changes needed - existing imports still work
2. **Update error handling**: Consider using specific exception types
3. **Use new factory methods**: `ProjectX.from_env()` is now recommended
4. **Optional**: Set up configuration file for advanced settings
5. **Optional**: Use new utility functions for logging and formatting

### New Installation Options

```bash
# Basic installation (same as before)
pip install project-x-py

# With real-time features
pip install project-x-py[realtime]

# With development tools
pip install project-x-py[dev]

# Everything
pip install project-x-py[all]
``` 