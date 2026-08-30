# Contributing to ProjectX Python SDK

Thank you for considering contributing to the ProjectX Python SDK! This document provides guidelines and instructions to help you contribute effectively.

## Table of Contents
- [Development Setup](#development-setup)
- [Code Style and Conventions](#code-style-and-conventions)
- [Pull Request Process](#pull-request-process)
- [Testing Guidelines](#testing-guidelines)
- [Documentation Requirements](#documentation-requirements)
- [Architecture Guidelines](#architecture-guidelines)

## Development Setup

### Prerequisites
- Python 3.12 or higher
- UV package manager (recommended)

### Local Development Environment

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/project-x-py.git
   cd project-x-py
   ```

2. **Set up the development environment with UV (recommended)**
   ```bash
   # Install UV if you haven't already
   curl -sSf https://install.determinate.systems/uv | python3 -

   # Install development dependencies
   uv sync
   ```

3. **Alternative setup with pip**
   ```bash
   pip install -e ".[dev]"
   ```

4. **Verify installation**
   ```bash
   uv run pytest -xvs tests/
   ```

## Code Style and Conventions

This project follows strict code style guidelines to maintain consistency and quality:

### Python Version
- Use Python 3.12+ features and syntax
- Use modern typing features (e.g., `int | None` instead of `Optional[int]`)

### Formatting and Linting
- We use Ruff for both formatting and linting
- Always run these commands before submitting code:
  ```bash
  # Format code
  uv run ruff format .

  # Lint code (with safe auto-fix)
  uv run ruff check --fix .
  ```

### Type Hints
- All code MUST include comprehensive type hints
- Use Python 3.10+ union syntax: `int | None` instead of `Optional[int]`
- Use `isinstance(x, (A | B))` instead of `isinstance(x, (A, B))`
- Use `dict[str, Any]` instead of `Dict[str, Any]`
- Run mypy to ensure type safety: `uv run mypy src/`

### Async/Await
- This project uses an async-first architecture
- All I/O operations must be async
- Use `async/await` consistently
- Use appropriate locking mechanisms for thread safety

### Data Processing
- Use Polars exclusively for DataFrame operations
- Never include Pandas fallbacks or compatibility code
- Use vectorized operations where possible
- Validate DataFrame schemas before operations

### Error Handling (v2.0.5+)

Use the centralized error handling system:

1. **Use Error Handling Decorators**
   ```python
   from project_x_py.utils import handle_errors, retry_on_network_error

   @handle_errors("operation name")
   @retry_on_network_error(max_attempts=3)
   async def my_method(self, ...):
       # Method implementation
   ```

2. **Use Structured Logging**
   ```python
   from project_x_py.utils import ProjectXLogger, LogMessages, LogContext

   logger = ProjectXLogger.get_logger(__name__)

   with LogContext(logger, operation="fetch_data", symbol="MGC"):
       logger.info(LogMessages.DATA_FETCH)
   ```

3. **Use Standardized Error Messages**
   ```python
   from project_x_py.utils import ErrorMessages, format_error_message

   raise ProjectXError(
       format_error_message(ErrorMessages.ORDER_NOT_FOUND, order_id=order_id)
   )
   ```

4. **Validate Input Parameters**
   - Use `@validate_response` decorator for API responses
   - Validate parameters at method entry
   - Return typed errors with context

## Pull Request Process

1. **Create a feature branch** from `main`
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Implement your changes** following the code style guidelines

3. **Add/update tests** to cover your changes

4. **Ensure all tests pass**
   ```bash
   uv run pytest -xvs tests/
   ```

5. **Format and lint your code**
   ```bash
   uv run ruff format .
   uv run ruff check --fix .
   uv run mypy src/
   ```

6. **Update documentation** to reflect your changes

7. **Submit a pull request** with:
   - Clear description of the changes
   - Reference to any related issues
   - Explanation of how to test the changes

8. **Address review feedback** until your PR is approved

## Testing Guidelines

All code contributions should include appropriate tests:

### Test Coverage
- Maintain or improve test coverage with each PR
- Write both unit and integration tests

### Test Structure
- Follow the existing test pattern in the `tests/` directory
- Use descriptive test names (`test_should_validate_market_data`)
- Include tests for both success and failure scenarios

### Test Organization
- Unit tests: Focus on testing individual functions/methods
- Integration tests: Test the interaction between components
- Comprehensive tests: Test full workflows and realistic scenarios

### Test Execution
```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_async_client.py

# Run tests with coverage report
uv run pytest --cov=src/project_x_py
```

## Documentation Requirements

Good documentation is essential for this project:

### Code Documentation
- All public classes, methods, and functions MUST have docstrings
- Follow the established docstring format (Google style)
- Include Args and Returns sections in docstrings
- Document expected parameter types and return values
- Include examples for complex methods

### README and Example Updates
- Update the README.md when adding new features
- Add examples to the `examples/` directory for significant features
- Keep the documentation synchronized with the code

### API Reference Documentation
- Add/update Sphinx documentation for public APIs
- Build and verify documentation changes:
  ```bash
  cd docs
  uv run sphinx-build -b html . _build/html
  ```

## Architecture Guidelines

### Backward Compatibility Policy (v3.1.1+)

**IMPORTANT**: This project maintains strict backward compatibility:

1. **API Stability**: Public APIs must remain stable between minor versions
2. **Deprecation Process**:
   - Add deprecation warnings using `warnings.warn()` and `@deprecated` decorator
   - Document the replacement in the deprecation message
   - Keep deprecated features for at least 2 minor versions
   - Only remove in major version releases (4.0.0, 5.0.0, etc.)

3. **Adding Deprecation Warnings**:
   ```python
   import warnings
   from typing import deprecated

   @deprecated("Use new_method() instead. Will be removed in v4.0.0")
   def old_method(self):
       warnings.warn(
           "old_method() is deprecated, use new_method() instead. "
           "Will be removed in v4.0.0",
           DeprecationWarning,
           stacklevel=2
       )
       return self.new_method()
   ```

4. **Introducing New Features**:
   - Add new methods/classes alongside existing ones
   - Provide migration guides in docstrings
   - Update examples to use new patterns
   - Keep old patterns working with deprecation warnings

5. **Version Numbering** (Semantic Versioning):
   - PATCH (x.x.N): Bug fixes only, no API changes
   - MINOR (x.N.x): New features, deprecations allowed, no breaking changes
   - MAJOR (N.x.x): Breaking changes allowed, remove deprecated features

### Project Structure

The SDK uses a modular architecture where large components are split into multi-file packages:

- **Client Module** (`client/`): Core async client functionality
  - `auth.py`: Authentication and token management
  - `http.py`: HTTP client and request handling
  - `cache.py`: Caching for instruments and market data
  - `market_data.py`: Market data operations
  - `trading.py`: Trading operations
  - `base.py`: Base class combining mixins

- **Trading Modules**:
  - `order_manager/`: Order lifecycle management (10 modules)
  - `position_manager/`: Portfolio and risk management (12 modules)

- **Real-time Modules**:
  - `realtime/`: WebSocket client functionality (8 modules)
  - `realtime_data_manager/`: Real-time OHLCV data (9 modules)

- **Utilities** (`utils/`): Shared utilities (10 modules)
  - Trading calculations, portfolio analytics, pattern detection
  - Market microstructure, formatting, environment handling

- **Indicators** (`indicators/`): 64 named indicators (Polars; not a full TA-Lib port)
  - Organized by category (momentum, overlap, volatility, etc.)

### Adding New Features
- Place new functionality in the appropriate existing module
- For large features, consider creating a new sub-module
- Maintain backward compatibility for all public APIs
- Follow the established mixin pattern for client extensions

### Performance Considerations
- Implement time window filtering for analysis methods
- Filter data BEFORE processing to reduce memory usage
- Implement appropriate data cleanup for old entries
- Use appropriate data types (int vs float vs str)
- Consider memory management in all components

### API Design
- Follow the established API patterns
- Use async context managers for resource management
- Implement proper error handling and validation
- Provide clear feedback on API errors

### ProjectX Platform Integration
- Follow the ProjectX API documentation
- Use configuration objects for URL management
- Never hardcode platform URLs
- Handle all required/optional fields in API responses
- Support both TopStepX endpoints and custom endpoints

## Reporting Issues

If you encounter any bugs or have feature requests:

1. Check if the issue already exists in the GitHub issue tracker
2. If not, create a new issue with:
   - Detailed description of the issue
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment information (Python version, OS, etc.)

## License

By contributing to this project, you agree that your contributions will be licensed under the project's MIT license.

## Questions?

If you have any questions or need help, please open an issue or contact the project maintainers.

Thank you for contributing to the ProjectX Python SDK!
