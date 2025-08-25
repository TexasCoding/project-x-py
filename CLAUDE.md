# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Memory Check Protocol:

Before responding to any request, I must:

1. Search memory for user preferences related to the current topic/request
2. Apply saved preferences without asking again
3. Only save NEW preferences, corrections, or special treatments - not tasks or general info
4. Check for topic-specific preferences (e.g., favorite subjects, style preferences, format preferences)

## CRITICAL: Testing and Running Examples

**ALWAYS use `./test.sh` to run tests and examples.** The environment variables are not set globally, but test.sh handles this automatically.

```bash
# CORRECT - Always use test.sh:
./test.sh examples/01_basic_client_connection.py
./test.sh examples/21_statistics_usage.py
./test.sh /tmp/test_script.py

# WRONG - Never use these directly:
uv run python examples/01_basic_client_connection.py
PROJECT_X_API_KEY="..." PROJECT_X_USERNAME="..." uv run python script.py
```

The test.sh script properly configures all required environment variables. DO NOT attempt to set PROJECT_X_API_KEY or PROJECT_X_USERNAME manually.

## Project Status: v3.3.0 - Complete Statistics Module Redesign

**IMPORTANT**: This project uses a fully asynchronous architecture. All APIs are async-only, optimized for high-performance futures trading.

## Development Phase Guidelines

**IMPORTANT**: This project has reached stable production status. When making changes:

1. **Maintain Backward Compatibility**: Keep existing APIs functional with deprecation warnings
2. **Deprecation Policy**: Mark deprecated features with warnings, remove after 2 minor versions
3. **Semantic Versioning**: Follow semver strictly (MAJOR.MINOR.PATCH)
4. **Migration Paths**: Provide clear migration guides for breaking changes
5. **Modern Patterns**: Use the latest Python patterns while maintaining compatibility
6. **Gradual Refactoring**: Improve code quality without breaking existing interfaces
7. **Async-First**: All new code must use async/await patterns

Example approach:
- ✅ DO: Keep old method signatures with deprecation warnings
- ✅ DO: Provide new improved APIs alongside old ones
- ✅ DO: Add compatibility shims when necessary
- ✅ DO: Document migration paths clearly
- ❌ DON'T: Break existing APIs without major version bump
- ❌ DON'T: Remove deprecated features without proper notice period

### Deprecation Process
1. Use the standardized `@deprecated` decorator from `project_x_py.utils.deprecation`
2. Provide clear reason, version info, and replacement path
3. Keep deprecated feature for at least 2 minor versions
4. Remove only in major version releases (4.0.0, 5.0.0, etc.)

Example:
```python
from project_x_py.utils.deprecation import deprecated, deprecated_class

# For functions/methods
@deprecated(
    reason="Method renamed for clarity",
    version="3.1.14",  # When deprecated
    removal_version="4.0.0",  # When it will be removed
    replacement="new_method()"  # What to use instead
)
def old_method(self):
    return self.new_method()

# For classes
@deprecated_class(
    reason="Integrated into TradingSuite",
    version="3.1.14",
    removal_version="4.0.0",
    replacement="TradingSuite"
)
class OldManager:
    pass
```

The standardized deprecation utilities provide:
- Consistent warning messages across the SDK
- Automatic docstring updates with deprecation info
- IDE support through the `deprecated` package
- Metadata tracking for deprecation management
- Support for functions, methods, classes, and parameters

## Test-Driven Development (TDD) Methodology

**CRITICAL**: This project follows strict Test-Driven Development principles. Tests define the specification, not the implementation.

### Core TDD Rules

1. **Write Tests FIRST**
   - Tests must be written BEFORE implementation code
   - Tests define the contract/specification of how code should behave
   - Follow Red-Green-Refactor cycle religiously

2. **Tests as Source of Truth**
   - Tests validate EXPECTED behavior, not current behavior
   - If existing code fails a test, FIX THE CODE, not the test
   - Tests document how the system SHOULD work
   - Never write tests that simply match faulty logic

3. **Red-Green-Refactor Cycle**
   ```
   1. RED: Write a failing test that defines expected behavior
   2. GREEN: Write minimal code to make the test pass
   3. REFACTOR: Improve code while keeping tests green
   4. REPEAT: Continue for next feature/requirement
   ```

4. **Testing Existing Code**
   - Treat tests as debugging tools
   - Write tests for what the code SHOULD do, not what it currently does
   - If tests reveal bugs, fix the implementation
   - Only modify tests if requirements have genuinely changed

5. **Test Writing Principles**
   - Each test should have a single, clear purpose
   - Test outcomes and behavior, not implementation details
   - Tests should be independent and isolated
   - Use descriptive test names that explain the expected behavior

### Example TDD Workflow

```python
# Step 1: Write the test FIRST (Red phase)
@pytest.mark.asyncio
async def test_order_manager_places_bracket_order():
    """Test that bracket orders create parent, stop, and target orders."""
    # Define expected behavior
    order_manager = OrderManager(mock_client)

    result = await order_manager.place_bracket_order(
        instrument="MNQ",
        quantity=1,
        stop_offset=10,
        target_offset=20
    )

    # Assert expected outcomes
    assert result.parent_order is not None
    assert result.stop_order is not None
    assert result.target_order is not None
    assert result.stop_order.price == result.parent_order.price - 10
    assert result.target_order.price == result.parent_order.price + 20

# Step 2: Run test - it SHOULD fail (Red confirmed)
# Step 3: Implement minimal code to pass (Green phase)
# Step 4: Refactor implementation while keeping test green
# Step 5: Write next test for edge cases
```

### Testing as Debugging

When testing existing code:
```python
# WRONG: Writing test to match buggy behavior
def test_buggy_calculation():
    # This matches what the code currently does (wrong!)
    assert calculate_risk(100, 10) == 1100  # Bug: should be 110

# CORRECT: Write test for expected behavior
def test_risk_calculation():
    # This defines what the code SHOULD do
    assert calculate_risk(100, 10) == 110  # 10% of 100 is 10, total 110
    # If this fails, FIX calculate_risk(), don't change the test
```

### Test Organization

- `tests/unit/` - Fast, isolated unit tests (mock all dependencies)
- `tests/integration/` - Test component interactions
- `tests/e2e/` - End-to-end tests with real services
- Always run tests with `./test.sh` for proper environment setup

### TDD Benefits for This Project

1. **API Stability**: Tests ensure backward compatibility
2. **Async Safety**: Tests catch async/await issues early
3. **Financial Accuracy**: Tests validate pricing and calculations
4. **Documentation**: Tests serve as living documentation
5. **Refactoring Confidence**: Tests enable safe refactoring

Remember: The test suite is the specification. Code must conform to tests, not vice versa.

## Specialized Agent Usage Guidelines

### IMPORTANT: Use Appropriate Subagents for Different Tasks

Claude Code includes specialized agents that should be used PROACTIVELY for specific development tasks. Each agent has specialized knowledge and tools optimized for their domain.

### Core Development Agents

#### **python-developer**
Use for project-x-py SDK development tasks:
- Writing async trading components (OrderManager, PositionManager, etc.)
- Implementing financial indicators with Polars DataFrames
- Optimizing real-time data processing and WebSocket connections
- Creating new TradingSuite features
- Performance profiling with memory_profiler and py-spy
- Integration testing with mock market data generators
- Benchmark suite management for performance tracking
- WebSocket load testing and stress testing

Example scenarios:
- "Implement a new technical indicator"
- "Add WebSocket reconnection logic"
- "Create async order placement methods"
- "Profile memory usage in real-time data manager"

Enhanced capabilities:
- Memory profiling: `mprof run ./test.sh examples/04_realtime_data.py`
- Async profiling: `py-spy record -o profile.svg -- ./test.sh examples/00_trading_suite_demo.py`
- Benchmark tests: `uv run pytest tests/benchmarks/ --benchmark-only`

#### **code-standards-enforcer**
Use PROACTIVELY for maintaining SDK standards:
- **ALWAYS check IDE diagnostics first** via `mcp__ide__getDiagnostics`
- Automated pre-commit hook setup and validation
- Performance regression detection with benchmarks
- Memory leak detection via tracemalloc
- Security vulnerability scanning with bandit
- Dependency audit with pip-audit
- Verifying 100% async architecture
- Type safety with TypedDict/Protocol

Example scenarios:
- After implementing new features
- Before creating pull requests
- When refactoring existing code
- **After any code changes** - check IDE diagnostics immediately

Enhanced tools:
- Security scanning: `uv run bandit -r src/`
- Dependency audit: `uv run pip-audit`
- Pre-commit validation: `pre-commit run --all-files`

#### **code-refactor**
Use PROACTIVELY for architecture improvements:
- AST-based code analysis for safe refactoring
- Dependency graph visualization with pydeps
- API migration script generation
- Performance impact analysis
- Migrating to TradingSuite patterns
- Optimizing Polars operations
- Consolidating WebSocket handling
- Modernizing async patterns

Example scenarios:
- "Refactor OrderManager to use EventBus"
- "Optimize DataFrame operations in indicators"
- "Migrate legacy sync code to async"
- "Visualize component dependencies"

#### **code-documenter**
Use PROACTIVELY for documentation tasks:
- Interactive API documentation with mkdocs-material
- Automated changelog generation from commits
- Example notebook generation with papermill
- API reference auto-generation with mkdocstrings
- Writing migration guides
- Maintaining README and examples/
- Writing deprecation notices
- Updating docstrings

Example scenarios:
- After adding new features
- When changing APIs
- Creating example scripts
- Generating interactive documentation

Enhanced documentation:
- Build docs: `mkdocs build`
- Serve locally: `mkdocs serve`
- Generate notebooks: `papermill template.ipynb output.ipynb`

#### **code-debugger**
Use PROACTIVELY for troubleshooting:
- Production log analysis with structured logging
- Distributed tracing with OpenTelemetry
- Async debugging with aiomonitor
- Memory leak detection with objgraph and tracemalloc
- WebSocket packet analysis and replay
- Order lifecycle failures
- Real-time data gaps
- Event deadlocks

Example scenarios:
- "Debug why orders aren't filling"
- "Fix WebSocket reconnection issues"
- "Trace event propagation problems"
- "Analyze production memory leaks"

Enhanced debugging:
- Async monitor: `aiomonitor` on port 50101
- Memory analysis: `objgraph.show_growth()`
- Distributed tracing with OpenTelemetry

#### **code-reviewer**
Use PROACTIVELY for code review:
- Security-focused review with semgrep
- Complexity analysis with radon
- Test coverage delta reporting
- Breaking change detection
- Performance benchmark comparison
- Reviewing async patterns
- Validating financial data integrity
- Ensuring API stability

Example scenarios:
- Before merging pull requests
- After completing features
- Before version releases
- Security audit reviews

Enhanced review tools:
- Complexity analysis: `radon cc src/ -s`
- Security patterns: `semgrep --config=auto src/`
- Coverage delta: `diff-cover coverage.xml`

### Specialized Performance & Testing Agents

#### **performance-optimizer**
Use PROACTIVELY for performance tuning:
- Memory profiling and optimization
- Async performance tuning
- Cache optimization strategies
- WebSocket message batching
- DataFrame operation optimization
- Benchmark management and comparison
- Resource utilization analysis

Example scenarios:
- "Optimize tick processing latency"
- "Reduce memory usage in orderbook"
- "Improve DataFrame aggregation performance"
- "Profile async event loop bottlenecks"

#### **integration-tester**
Use for end-to-end testing with market simulation:
- Mock market data generation
- Order lifecycle simulation
- WebSocket stress testing
- Multi-timeframe backtesting
- Paper trading validation
- Market replay testing
- Cross-component integration testing

Example scenarios:
- "Test order execution under volatile conditions"
- "Validate indicator calculations with real data"
- "Stress test WebSocket with 1000+ ticks/second"
- "Simulate market gaps and disconnections"

#### **security-auditor**
Use PROACTIVELY for security and compliance:
- API key security validation
- WebSocket authentication audit
- Data encryption verification
- PII handling compliance
- Dependency vulnerability scanning
- Secret scanning in codebase
- Input validation checks
- Rate limiting verification

Example scenarios:
- Before releases
- After adding authentication features
- When handling sensitive data
- Regular security audits

#### **release-manager**
Use for release preparation and deployment:
- Semantic versioning validation
- Breaking change detection
- Migration script generation
- Release notes compilation
- PyPI deployment automation
- Git tag management
- Pre-release testing coordination
- Rollback procedure planning

Example scenarios:
- Preparing version releases
- Creating migration guides
- Automating deployment pipeline
- Managing release branches

#### **data-analyst**
Use for market data analysis and validation:
- Indicator accuracy testing against TA-Lib
- Market microstructure analysis
- Order flow pattern detection
- Statistical validation of calculations
- Backtest result analysis
- Performance attribution
- Volume profile analysis
- Data quality verification

Example scenarios:
- "Validate MACD implementation"
- "Analyze order flow imbalances"
- "Compare indicator outputs with TA-Lib"
- "Statistical validation of backtest results"

### Agent Collaboration Patterns

#### Pattern 1: Feature Development
```
1. data-analyst: Analyze requirements and validate approach
2. python-developer: Implement the feature
3. integration-tester: Create comprehensive tests
4. code-standards-enforcer: Ensure compliance
5. performance-optimizer: Optimize if needed
6. code-documenter: Create documentation
7. code-reviewer: Final review
8. release-manager: Prepare for release
```

#### Pattern 2: Bug Investigation
```
1. code-debugger: Investigate and identify root cause
2. integration-tester: Reproduce with test case
3. python-developer: Implement fix
4. code-standards-enforcer: Verify fix quality
5. code-reviewer: Review the fix
```

#### Pattern 3: Performance Issue
```
1. performance-optimizer: Profile and identify bottlenecks
2. code-refactor: Plan optimization strategy
3. python-developer: Implement optimizations
4. integration-tester: Verify performance improvements
5. code-reviewer: Review changes
```

#### Pattern 4: Security Audit
```
1. security-auditor: Comprehensive security scan
2. code-debugger: Investigate vulnerabilities
3. python-developer: Implement fixes
4. code-standards-enforcer: Verify secure coding
5. integration-tester: Test security measures
```

#### Pattern 5: Release Preparation
```
1. code-standards-enforcer: Pre-release compliance check
2. security-auditor: Security validation
3. integration-tester: Full regression testing
4. performance-optimizer: Performance regression check
5. code-documenter: Update documentation
6. release-manager: Coordinate release
```

### Agent Selection Best Practices

1. **Use agents concurrently** when multiple tasks can be parallelized
2. **Be specific** in task descriptions for agents
3. **Choose the right agent** based on the task type, not just keywords
4. **Use PROACTIVELY** - don't wait for user to request specific agents
5. **Combine agents** for complex tasks using collaboration patterns
6. **Leverage specialized agents** for their unique capabilities
7. **Follow patterns** for common workflows to ensure comprehensive coverage

### Example Multi-Agent Workflows

#### Implementing a New Trading Feature
```python
# Concurrent agent execution for new feature
1. Launch simultaneously:
   - data-analyst: Validate market data requirements
   - performance-optimizer: Baseline current performance
   - security-auditor: Review security implications

2. python-developer: Implement based on analysis results

3. Launch simultaneously:
   - integration-tester: Create test suite
   - code-standards-enforcer: Check compliance
   - code-documenter: Write documentation

4. code-reviewer: Final review before merge
```

#### Debugging Production Issue
```python
# Sequential debugging workflow
1. code-debugger: Analyze logs and identify issue
2. performance-optimizer: Check for performance degradation
3. python-developer: Implement fix
4. integration-tester: Verify fix with reproduction test
5. code-reviewer: Review and approve fix
```

### Agent Command Requirements

**Note**: Tool permissions are configured at the system level. This section documents common commands agents need.

#### Commands Agents Typically Use

**All Agents**:
- `./test.sh [script]` - Run tests and examples with proper environment
- File operations (Read, Write, Edit, MultiEdit)
- `git status`, `git diff`, `git add` - Version control

**python-developer**:
- `uv run pytest` - Run test suite
- `uv add [package]` - Add dependencies
- `./test.sh examples/*.py` - Test example scripts

**code-standards-enforcer**:
- `mcp__ide__getDiagnostics` - **CHECK FIRST** - IDE diagnostics
- `uv run ruff check .` - Lint code
- `uv run ruff format .` - Format code
- `uv run mypy src/` - Type checking
- `uv run pytest --cov` - Coverage reports

**code-debugger**:
- `./test.sh` with debug scripts
- `grep` and search operations
- Log analysis commands

**code-reviewer**:
- `git diff` - Review changes
- `uv run pytest` - Verify tests pass
- Static analysis tools

#### Example Agent Command Workflow

```bash
# Agent workflow for implementing a feature
1. python-developer:
   - Edit src/project_x_py/new_feature.py
   - ./test.sh tests/test_new_feature.py

2. code-standards-enforcer:
   - mcp__ide__getDiagnostics  # ALWAYS CHECK FIRST
   - uv run ruff check src/
   - uv run mypy src/
   - Fix any issues found

3. code-reviewer:
   - mcp__ide__getDiagnostics  # Verify no issues remain
   - git diff
   - uv run pytest
   - Review implementation
```

#### IDE Diagnostics Priority

**CRITICAL**: The `code-standards-enforcer` agent must ALWAYS:
1. **First** check `mcp__ide__getDiagnostics` for the modified files
2. **Fix** any IDE diagnostic errors/warnings before proceeding
3. **Then** run traditional linting tools (ruff, mypy)
4. **Verify** with IDE diagnostics again after fixes

This catches issues that mypy might miss, such as:
- Incorrect method names (e.g., `get_statistics` vs `get_position_stats`)
- Missing attributes on classes
- Type mismatches that IDE's type checker detects
- Real-time semantic errors

### MCP Server Permissions for Agents

**Note**: MCP server access is system-configured. Agents should have access to relevant MCP servers for their tasks.

#### Essential MCP Servers for Agents

**All Agents Should Access**:
- `mcp__aakarsh-sasi-memory-bank-mcp` - Track progress and context
- `mcp__mcp-obsidian` - Document plans and decisions
- `mcp__smithery-ai-filesystem` - File operations

**python-developer**:
- `mcp__project-x-py_Docs` - Search project documentation
- `mcp__upstash-context-7-mcp` - Get library documentation
- `mcp__waldzellai-clear-thought` - Complex problem solving
- `mcp__itseasy-21-mcp-knowledge-graph` - Map component relationships

**code-standards-enforcer**:
- `mcp__project-x-py_Docs` - Verify against documentation
- `mcp__aakarsh-sasi-memory-bank-mcp` - Check architectural decisions

**code-refactor**:
- `mcp__waldzellai-clear-thought` - Plan refactoring strategy
- `mcp__itseasy-21-mcp-knowledge-graph` - Understand dependencies
- `mcp__aakarsh-sasi-memory-bank-mcp` - Log refactoring decisions

**code-documenter**:
- `mcp__mcp-obsidian` - Create documentation
- `mcp__project-x-py_Docs` - Reference existing docs
- `mcp__tavily-mcp` - Research external APIs

**code-debugger**:
- `mcp__waldzellai-clear-thought` - Analyze issues systematically
- `mcp__itseasy-21-mcp-knowledge-graph` - Trace data flow
- `mcp__ide` - Get diagnostics and errors

**code-reviewer**:
- `mcp__github` - Review PRs and issues
- `mcp__project-x-py_Docs` - Verify against standards
- `mcp__aakarsh-sasi-memory-bank-mcp` - Check design decisions

#### Example MCP Usage in Agent Workflows

```python
# python-developer agent workflow
1. Search existing patterns:
   await mcp__project_x_py_Docs__search_project_x_py_code(
       query="async def place_order"
   )

2. Track implementation:
   await mcp__aakarsh_sasi_memory_bank_mcp__track_progress(
       action="Implemented async order placement",
       description="Added bracket order support"
   )

3. Document in Obsidian:
   await mcp__mcp_obsidian__obsidian_append_content(
       filepath="Development/ProjectX SDK/Features/Order System.md",
       content="## Bracket Order Implementation\n..."
   )

# code-debugger agent workflow
1. Analyze problem:
   await mcp__waldzellai_clear_thought__clear_thought(
       operation="debugging_approach",
       prompt="WebSocket disconnecting under load"
   )

2. Check component relationships:
   await mcp__itseasy_21_mcp_knowledge_graph__search_nodes(
       query="WebSocket RealtimeClient"
   )

3. Get IDE diagnostics:
   await mcp__ide__getDiagnostics()
```

#### MCP Server Best Practices for Agents

1. **Memory Bank**: Update after completing tasks
2. **Obsidian**: Document multi-session plans and decisions
3. **Clear Thought**: Use for complex analysis and planning
4. **Knowledge Graph**: Maintain component relationships
5. **Project Docs**: Reference before implementing
6. **GitHub**: Check issues and PRs for context

## Development Documentation with Obsidian

### Important: Use Obsidian for Development Plans and Progress Tracking

**ALWAYS use Obsidian MCP integration for**:
- Multi-session development plans
- Testing procedures and results
- Architecture decisions and design documents
- Feature planning and roadmaps
- Bug investigation notes
- Performance optimization tracking
- Release planning and checklists

**DO NOT create project files for**:
- Personal development notes (use Obsidian instead)
- Temporary planning documents
- Testing logs and results
- Work-in-progress documentation
- Meeting notes or discussions

### Obsidian Structure for ProjectX Development

When using Obsidian for this project, use the following structure:
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
    Performance/
      [Optimization Area].md
```

### Example Obsidian Usage

```python
# When creating multi-session plans:
await mcp__mcp_obsidian__obsidian_append_content(
    filepath="Development/ProjectX SDK/Feature Planning/WebSocket Improvements.md",
    content="# WebSocket Connection Improvements Plan\n..."
)

# When documenting test results:
await mcp__mcp_obsidian__obsidian_append_content(
    filepath="Development/ProjectX SDK/Testing Plans/v3.3.0 Release Testing.md",
    content="## Test Results\n..."
)
```

This keeps the project repository clean and focused on production code while maintaining comprehensive development documentation in Obsidian.

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
uv run pytest                # Run all tests
uv run pytest tests/test_client.py  # Run specific test file
uv run pytest -m "not slow"  # Run tests excluding slow ones
uv run pytest --cov=project_x_py --cov-report=html  # Generate coverage report
uv run pytest -k "async"     # Run only async tests
```

### Async Testing Patterns
```python
# Test async methods with pytest-asyncio
import pytest

@pytest.mark.asyncio
async def test_async_method():
    async with ProjectX.from_env() as client:
        await client.authenticate()
        result = await client.get_bars("MNQ", days=1)
        assert result is not None
```

### Code Quality
```bash
uv run ruff check .          # Lint code
uv run ruff check . --fix    # Auto-fix linting issues
uv run ruff format .         # Format code
uv run mypy src/             # Type checking
```

### Building and Distribution
```bash
uv build                     # Build wheel and source distribution
uv run python -m build       # Alternative build command
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
  - `core.py`: Main order operations
  - `bracket_orders.py`: OCO and bracket order logic
  - `position_orders.py`: Position-based order management
  - `tracking.py`: Order state tracking
  - `templates.py`: Order templates for common strategies
- `PositionManager` (`position_manager/`): Async position tracking and risk management
  - `core.py`: Position management core
  - `risk.py`: Risk calculations and limits
  - `analytics.py`: Performance analytics
  - `monitoring.py`: Real-time position monitoring
  - `tracking.py`: Position lifecycle tracking
- `RiskManager` (`risk_manager/`): Integrated risk management
  - `core.py`: Risk limits and validation
  - `monitoring.py`: Real-time risk monitoring
  - `analytics.py`: Risk metrics and reporting
- `ProjectXRealtimeDataManager` (`realtime_data_manager/`): Async WebSocket data
  - `core.py`: Main data manager
  - `callbacks.py`: Event callback handling
  - `data_processing.py`: OHLCV bar construction
  - `memory_management.py`: Efficient data storage
- `OrderBook` (`orderbook/`): Async Level 2 market depth
  - `base.py`: Core orderbook functionality
  - `analytics.py`: Market microstructure analysis
  - `detection.py`: Iceberg and spoofing detection
  - `profile.py`: Volume profile analysis

**Technical Indicators (`src/project_x_py/indicators/`)**
- TA-Lib compatible indicator library built on Polars
- 58+ indicators including pattern recognition:
  - **Momentum**: RSI, MACD, Stochastic, etc.
  - **Overlap**: SMA, EMA, Bollinger Bands, etc.
  - **Volatility**: ATR, Keltner Channels, etc.
  - **Volume**: OBV, VWAP, Money Flow, etc.
  - **Pattern Recognition** (NEW):
    - Fair Value Gap (FVG): Price imbalance detection
    - Order Block: Institutional order zone identification
    - Waddah Attar Explosion: Volatility-based trend strength
- All indicators work with Polars DataFrames for performance

**Configuration System**
- Environment variable based configuration
- JSON config file support (`~/.config/projectx/config.json`)
- ProjectXConfig dataclass for type safety
- ConfigManager for centralized configuration handling

**Event System**
- Unified EventBus for cross-component communication
- Type-safe event definitions
- Async event handlers with priority support
- Built-in event types for all trading events

### Available TradingSuite Features

The `Features` enum defines optional components that can be enabled:

- `ORDERBOOK = "orderbook"` - Level 2 market depth and analysis
- `RISK_MANAGER = "risk_manager"` - Position sizing and risk management
- `TRADE_JOURNAL = "trade_journal"` - Trade logging (future)
- `PERFORMANCE_ANALYTICS = "performance_analytics"` - Advanced metrics (future)
- `AUTO_RECONNECT = "auto_reconnect"` - Automatic reconnection (future)

**Note**: OrderManager and PositionManager are always included by default.

### Architecture Patterns

**Async Factory Functions**: Use async `create_*` functions for component initialization:
```python
# TradingSuite - Recommended approach (v3.0.0+)
async def setup_trading():
    # Simple one-line setup with TradingSuite
    suite = await TradingSuite.create(
        "MNQ",
        timeframes=["1min", "5min"],
        features=["orderbook"]
    )

    # Everything is ready - client authenticated, realtime connected
    return suite
```

**Dependency Injection**: Managers receive their dependencies (ProjectX client, realtime client) rather than creating them.

**Real-time Integration**: Single `ProjectXRealtimeClient` instance shared across managers for WebSocket connection efficiency.

**Context Managers**: Always use async context managers for proper resource cleanup:
```python
async with ProjectX.from_env() as client:
    # Client automatically handles auth, cleanup
    pass
```

### Data Flow

1. **Authentication**: ProjectX client authenticates and provides JWT tokens
2. **Real-time Setup**: Create ProjectXRealtimeClient with JWT for WebSocket connections
3. **Manager Initialization**: Pass clients to specialized managers via dependency injection
4. **Data Processing**: Polars DataFrames used throughout for performance
5. **Event Handling**: Real-time updates flow through WebSocket to respective managers

## Important Technical Details

### Indicator Functions
- All indicators follow TA-Lib naming conventions (uppercase function names allowed in `indicators/__init__.py`)
- Use Polars pipe() method for chaining: `data.pipe(SMA, period=20).pipe(RSI, period=14)`
- Indicators support both class instantiation and direct function calls

### Price Precision
- All price handling uses Decimal for precision
- Automatic tick size alignment in OrderManager
- Price formatting utilities in utils.py

### Error Handling
- Custom exception hierarchy in exceptions.py
- All API errors wrapped in ProjectX-specific exceptions
- Comprehensive error context and retry logic

### Testing Strategy
- Pytest with async support and mocking
- Test markers: unit, integration, slow, realtime
- High test coverage required (configured in pyproject.toml)
- Mock external API calls in unit tests

## Environment Setup

Required environment variables:
- `PROJECT_X_API_KEY`: TopStepX API key
- `PROJECT_X_USERNAME`: TopStepX username

Optional configuration:
- `PROJECTX_API_URL`: Custom API endpoint
- `PROJECTX_TIMEOUT_SECONDS`: Request timeout
- `PROJECTX_RETRY_ATTEMPTS`: Retry attempts

## MCP Server Integration

Several MCP (Model Context Protocol) servers are available to enhance development workflow:

### Essential Development MCPs

#### Memory Bank (`mcp__aakarsh-sasi-memory-bank-mcp`)
Tracks development progress and maintains context across sessions:
```python
# Track feature implementation progress
await mcp__aakarsh_sasi_memory_bank_mcp__track_progress(
    action="Implemented bracket order system",
    description="Added OCO and bracket order support with automatic stop/target placement"
)

# Log architectural decisions
await mcp__aakarsh_sasi_memory_bank_mcp__log_decision(
    title="Event System Architecture",
    context="Need unified event handling across components",
    decision="Implement EventBus with async handlers and priority support",
    alternatives=["Direct callbacks", "Observer pattern", "Pub/sub with Redis"],
    consequences=["Better decoupling", "Easier testing", "Slight performance overhead"]
)

# Switch development modes
await mcp__aakarsh_sasi_memory_bank_mcp__switch_mode("debug")  # architect, code, debug, test
```

#### Knowledge Graph (`mcp__itseasy-21-mcp-knowledge-graph`)
Maps component relationships and data flow:
```python
# Map trading system relationships
await mcp__itseasy_21_mcp_knowledge_graph__create_entities(
    entities=[
        {"name": "TradingSuite", "entityType": "Core",
         "observations": ["Central orchestrator", "Manages all components"]},
        {"name": "OrderManager", "entityType": "Manager",
         "observations": ["Handles order lifecycle", "Supports bracket orders"]}
    ]
)

await mcp__itseasy_21_mcp_knowledge_graph__create_relations(
    relations=[
        {"from": "TradingSuite", "to": "OrderManager", "relationType": "manages"},
        {"from": "OrderManager", "to": "ProjectXClient", "relationType": "uses"}
    ]
)
```

#### Clear Thought Reasoning (`mcp__waldzellai-clear-thought`)
For complex problem-solving and architecture decisions:
```python
# Analyze performance bottlenecks
await mcp__waldzellai_clear_thought__clear_thought(
    operation="debugging_approach",
    prompt="WebSocket connection dropping under high message volume",
    context="Real-time data manager processing 1000+ ticks/second"
)

# Plan refactoring strategy
await mcp__waldzellai_clear_thought__clear_thought(
    operation="systems_thinking",
    prompt="Refactor monolithic client into modular mixins",
    context="Need better separation of concerns without breaking existing API"
)
```

### Documentation & Research MCPs

#### Project Documentation (`mcp__project-x-py_Docs`)
Quick access to project-specific documentation:
```python
# Search project documentation
await mcp__project_x_py_Docs__search_project_x_py_documentation(
    query="bracket order implementation"
)

# Search codebase
await mcp__project_x_py_Docs__search_project_x_py_code(
    query="async def place_bracket_order"
)
```

#### External Research (`mcp__tavily-mcp`)
Research trading APIs and async patterns:
```python
# Search for solutions
await mcp__tavily_mcp__tavily_search(
    query="python asyncio websocket reconnection pattern futures trading",
    max_results=5,
    search_depth="advanced"
)

# Extract documentation
await mcp__tavily_mcp__tavily_extract(
    urls=["https://docs.python.org/3/library/asyncio-task.html"],
    format="markdown"
)
```

### Best Practices for MCP Usage

1. **Memory Bank**: Update after completing significant features or making architectural decisions
2. **Knowledge Graph**: Maintain when adding new components or changing relationships
3. **Clear Thought**: Use for complex debugging, performance analysis, or architecture planning
4. **Documentation MCPs**: Reference before implementing new features to understand existing patterns

### When to Use Each MCP

- **Starting a new feature**: Check Memory Bank for context, use Clear Thought for planning
- **Debugging complex issues**: Clear Thought for analysis, Knowledge Graph for understanding relationships
- **Making architectural decisions**: Log with Memory Bank, analyze with Clear Thought
- **Understanding existing code**: Project Docs for internal code, Tavily for external research
- **Tracking progress**: Memory Bank for TODO tracking and progress updates

## Performance Optimizations

### Connection Pooling & Caching (client.py)
- HTTP connection pooling with retry strategies for 50-70% fewer connection overhead
- Instrument caching reduces repeated API calls by 80%
- Preemptive JWT token refresh at 80% lifetime prevents authentication delays
- Session-based requests with automatic retry on failures

### Memory Management
- **OrderBook**: Sliding windows with configurable limits (max 10K trades, 1K depth entries)
- **RealtimeDataManager**: Automatic cleanup maintains 1K bars per timeframe
- **Indicators**: LRU cache for repeated calculations (100 entry limit)
- Periodic garbage collection after large data operations

### Optimized DataFrame Operations
- **Chained operations** reduce intermediate DataFrame creation by 30-40%
- **Lazy evaluation** with Polars for better memory efficiency
- **Efficient datetime parsing** with cached timezone objects
- **Vectorized operations** in orderbook analysis

### Performance Monitoring
Use async built-in methods to monitor performance:
```python
# Client performance stats (async)
async with ProjectX.from_env() as client:
    await client.authenticate()

    # Check performance metrics
    stats = await client.get_performance_stats()
    print(f"API calls: {stats['api_calls']}")
    print(f"Cache hits: {stats['cache_hits']}")

    # Health check
    health = await client.get_health_status()

    # Memory usage monitoring
    orderbook_stats = await orderbook.get_memory_stats()
    data_manager_stats = await data_manager.get_memory_stats()
```

### Expected Performance Improvements
- **50-70% reduction in API calls** through intelligent caching
- **30-40% faster indicator calculations** via chained operations
- **60% less memory usage** through sliding windows and cleanup
- **Sub-second response times** for cached operations
- **95% reduction in polling** with real-time WebSocket feeds

### Memory Limits (Configurable)
- `max_trades = 10000` (OrderBook trade history)
- `max_depth_entries = 1000` (OrderBook depth per side)
- `max_bars_per_timeframe = 1000` (Real-time data per timeframe)
- `tick_buffer_size = 1000` (Tick data buffer)
- `cache_max_size = 100` (Indicator cache entries)

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
