# GEMINI.md

This file provides guidance to Google's Gemini models when working with code in this repository.

## Project Status: v4.0.1 - TopstepX Gateway revival and live-order hardening

**IMPORTANT**: This project uses a fully asynchronous architecture. All APIs are async-only, optimized for high-performance futures trading.

---

## CRITICAL: Test-Driven Development (TDD) Methodology

**This project follows strict Test-Driven Development principles. Tests define the specification, not the implementation. All rules are MANDATORY.**

### 1. The RED-GREEN-REFACTOR Cycle (NON-NEGOTIABLE)

**ALWAYS follow this exact sequence for ALL development work:**

1.  **RED**: Write a failing test that defines the desired behavior or reproduces a bug.
2.  **GREEN**: Write the absolute minimal amount of implementation code required to make the test pass.
3.  **REFACTOR**: Improve the code's structure, readability, and performance while ensuring all tests remain green.
4.  **REPEAT**: Continue the cycle for the next piece of functionality.

**FORBIDDEN**: Writing implementation code before a failing test exists.

### 2. Test-First Development

-   **MANDATORY**: Tests MUST be written **BEFORE** any implementation code.
-   **MANDATORY**: Run the new test to confirm it fails as expected (the **RED** phase) before writing implementation code.
-   **PRINCIPLE**: Tests are the executable specification of the system. If the code does not meet the test's specification, the code is wrong.
-   **FORBIDDEN**: Writing tests after the implementation is complete.

### 3. TDD-Based Debugging

**When fixing a bug, the TDD cycle is the ONLY acceptable method:**

1.  Write a new test that specifically reproduces the bug.
2.  Run the test and confirm it **FAILS** in the same way as the bug report. This is your **RED** state.
3.  Write the minimal code necessary to fix the bug and make the test pass. This is your **GREEN** state.
4.  Run all tests to ensure the fix has not caused regressions.
5.  Refactor the code if necessary.

**FORBIDDEN**: Modifying code to fix a bug without first writing a failing test that captures the bug.

---

## CRITICAL: Development Workflow & Quality

### 1. Mandatory Development Workflow

A disciplined workflow is required to ensure quality and consistency.

```bash
# Step 1: RED - Write a failing test for a new feature
# The test must define the expected behavior.
uv run pytest tests/test_new_feature.py::test_specific_behavior
# --> MUST FAIL to confirm the RED phase.

# Step 2: GREEN - Write minimal implementation
# Write only enough code to make the test pass.
uv run pytest tests/test_new_feature.py::test_specific_behavior
# --> MUST PASS to confirm the GREEN phase.

# Step 3: REFACTOR - Improve the code
# Clean up the implementation while keeping all tests green.
uv run pytest
# --> ALL tests must continue to pass.
```

### 2. Mandatory Quality Gates

**Before any commit, ALL of the following checks MUST pass without errors:**

```bash
# 1. Format code
uv run ruff format .

# 2. Lint code (with auto-fix)
uv run ruff check . --fix

# 3. Check static types
uv run mypy src/

# 4. Run the full test suite
./test.sh
```

### 3. Test Execution

**ALWAYS use the `./test.sh` script to run examples.** This script correctly sets up the required environment variables.

```bash
# ✅ CORRECT: Use the test wrapper script
./test.sh examples/01_basic_client_connection.py

# ❌ WRONG: Do not run python directly
uv run python examples/01_basic_client_connection.py
```

---

## CRITICAL: Code Quality Standards

### 1. Modern Python and Type Hints (Python 3.10+)

-   **ALWAYS** use modern union syntax (`X | Y` instead of `Union[X, Y]`).
-   **ALWAYS** use modern `isinstance` syntax (`isinstance(x, int | float)`).
-   **MANDATORY**: Provide type hints for all function parameters, return values, and class attributes.
-   **FORBIDDEN**: Use of legacy typing syntax (`Optional`, `Union`, `Dict`, etc.).

### 2. Async-First Patterns

-   **MANDATORY**: All new code must use `async/await` patterns.
-   **MANDATORY**: All async tests must be decorated with `@pytest.mark.asyncio`.
-   **FORBIDDEN**: Using `asyncio.run()` or `.result()` inside test methods.

### 3. Error Handling

-   **ALWAYS** wrap external API calls in specific `try...except` blocks.
-   **Raise** custom, specific exceptions from caught exceptions to provide context.
-   **FORBIDDEN**: Bare `except:` clauses or swallowing exceptions without logging and re-raising.

### 4. Data Operations

-   **MANDATORY**: Use **Polars** for all DataFrame operations.
-   **FORBIDDEN**: Any use of the `pandas` library is strictly prohibited.

---

## Development Phase Guidelines

**IMPORTANT**: This project has reached stable production status. When making changes:

1.  **Maintain Backward Compatibility**: Keep existing APIs functional with deprecation warnings.
2.  **Deprecation Policy**: Mark deprecated features with warnings; remove after 2 minor versions.
3.  **Semantic Versioning**: Follow semver strictly (MAJOR.MINOR.PATCH).
4.  **Migration Paths**: Provide clear migration guides for breaking changes.
5.  **Gradual Refactoring**: Improve code quality without breaking existing interfaces.

### Deprecation Process
1.  Use the standardized `@deprecated` decorator from `project_x_py.utils.deprecation`.
2.  Provide a clear reason, version info, and replacement path.
3.  Keep the deprecated feature for at least 2 minor versions.
4.  Remove only in major version releases (4.0.0, 5.0.0, etc.).

Example:
```python
from project_x_py.utils.deprecation import deprecated

@deprecated(
    reason="Method renamed for clarity",
    version="3.1.14",
    removal_version="4.0.0",
    replacement="new_method()"
)
def old_method(self):
    return self.new_method()
```

## Development Documentation with Obsidian

**ALWAYS use Obsidian for**:
-   Multi-session development plans
-   Testing procedures and results
-   Architecture decisions and design documents
-   Bug investigation notes

**DO NOT create project files for temporary notes or logs.** Keep the repository clean.

### Obsidian Structure
```
Development/
  ProjectX SDK/
    Feature Planning/
      [Feature Name].md
    Testing Plans/
      [Version] Release Testing.md
    Architecture Decisions/
      [Decision Topic].md
    Bug Investigations/
      [Issue Number] - [Description].md
```

## Development Commands

### Package Management (UV)
```bash
uv add [package]              # Add a dependency
uv add --dev [package]        # Add a development dependency
uv sync                       # Install/sync dependencies
uv run [command]              # Run command in virtual environment
```

### Testing
```bash
./test.sh                     # Run all tests via the wrapper
uv run pytest tests/test_client.py  # Run specific test file
uv run pytest -m "not slow"   # Run tests excluding slow ones
uv run pytest --cov=project_x_py --cov-report=html  # Generate coverage report
uv run pytest -k "async"      # Run only async tests
```

### Code Quality
```bash
uv run ruff check . --fix     # Auto-fix linting issues
uv run ruff format .          # Format code
uv run mypy src/              # Type checking
```

## Project Architecture

### Core Components (v3.0.2 - Multi-file Packages)

**ProjectX Client (`src/project_x_py/client/`)**
- Main async API client for TopStepX ProjectX Gateway
- Modular architecture with specialized modules:
  - `auth.py`: Authentication and JWT token management
  - `http.py`: Async HTTP client with retry logic
  - `cache.py`: Intelligent caching for instruments
  - `market_data.py`: Market data operations
  - `trading.py`: Trading operations
  - `rate_limiter.py`: Async rate limiting
  - `base.py`: Base class combining all mixins

**Specialized Managers (All Async)**
- `OrderManager` (`order_manager/`): Comprehensive async order operations
- `PositionManager` (`position_manager/`): Async position tracking and risk management
- `RiskManager` (`risk_manager/`): Integrated risk management
- `ProjectXRealtimeDataManager` (`realtime_data_manager/`): Async WebSocket data
- `OrderBook` (`orderbook/`): Async Level 2 market depth

**Technical Indicators (`src/project_x_py/indicators/`)**
- TA-Lib compatible indicator library built on Polars
- 58+ indicators including pattern recognition.
- All indicators work with Polars DataFrames for performance.

### Trading Suite Usage (v3.0.0+)
```python
# Complete trading suite with all managers
from project_x_py import TradingSuite

async def main():
    suite = await TradingSuite.create(
        "MNQ",
        timeframes=["1min", "5min"],
        features=["orderbook", "risk_manager"],
        initial_days=5
    )

    # All managers are integrated and ready
    order = await suite.orders.place_market_order(
        contract_id=suite.instrument_info.id,
        side=0,  # Buy
        size=1
    )
    position = await suite.positions.get_position("MNQ")
    bars = await suite.data.get_data("1min")
```

## Recent Changes

### v3.3.0 - Latest Release (2025-01-21)
- **Breaking**: Complete statistics system redesign with 100% async-first architecture
- **Added**: New statistics module with BaseStatisticsTracker, ComponentCollector, StatisticsAggregator
- **Added**: Multi-format export (JSON, Prometheus, CSV, Datadog) with data sanitization
- **Added**: Enhanced health monitoring with 0-100 scoring and configurable thresholds
- **Added**: TTL caching, parallel collection, and circular buffers for performance optimization
- **Added**: 45+ new tests covering all aspects of the async statistics system
- **Fixed**: Eliminated all statistics-related deadlocks with single RW lock per component
- **Changed**: All statistics methods now require `await` for consistency and performance
- **Removed**: Legacy statistics mixins (EnhancedStatsTrackingMixin, StatsTrackingMixin)
