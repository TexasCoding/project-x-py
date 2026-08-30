# ProjectX Python SDK Documentation

This directory contains the MkDocs-based documentation for the ProjectX Python SDK.

## Setup

### Install Dependencies

```bash
# Using UV (recommended)
uv add --dev mkdocs mkdocs-material mkdocstrings[python] mkdocs-jupyter pymdown-extensions

# Or using pip
pip install mkdocs mkdocs-material mkdocstrings[python] mkdocs-jupyter pymdown-extensions
```

## Local Development

### Serve Documentation Locally

```bash
# Using the helper script
./scripts/serve-docs.sh

# Or directly with MkDocs
mkdocs serve

# View at http://localhost:8000
```

### Build Documentation

```bash
# Build static site
mkdocs build

# Output will be in site/ directory
```

## Deployment

### GitHub Pages

The documentation is automatically deployed to GitHub Pages when changes are pushed to the main branch.

URL: https://texascoding.github.io/project-x-py/

### Manual Deployment

```bash
# Deploy specific version
./scripts/deploy-docs.sh 3.3.4 latest

# Deploy without alias
./scripts/deploy-docs.sh 3.3.4
```

## Documentation Structure

```
docs/
├── index.md                    # Home page
├── getting-started/            # Installation, setup, quickstart
│   ├── installation.md
│   ├── quickstart.md
│   ├── authentication.md
│   └── configuration.md
├── guide/                      # User guides
│   ├── trading-suite.md       # Main trading suite guide
│   ├── orders.md              # Order management
│   ├── positions.md           # Position tracking
│   ├── realtime.md            # Real-time data
│   ├── indicators.md          # Technical indicators
│   ├── risk.md               # Risk management
│   └── orderbook.md          # Level 2 data
├── api/                       # API reference
│   ├── client.md             # Core client
│   ├── trading-suite.md      # TradingSuite API
│   ├── order-manager.md      # OrderManager API
│   ├── position-manager.md   # PositionManager API
│   ├── data-manager.md       # DataManager API
│   ├── indicators.md         # Indicators API
│   ├── statistics.md         # Statistics API
│   └── models.md             # Data models
├── examples/                  # Code examples
│   ├── basic.md              # Basic usage
│   ├── advanced.md           # Advanced strategies
│   ├── realtime.md           # Real-time processing
│   ├── backtesting.md        # Backtesting
│   └── notebooks/            # Jupyter notebooks
├── development/               # Development docs
│   ├── contributing.md       # Contribution guide
│   ├── testing.md           # Testing guide
│   ├── agents.md            # Grok agents, skills, hooks
│   └── architecture.md      # System architecture
├── migration/                # Migration guides
│   ├── v3-to-v4.md         # v3 to v4 migration
│   └── breaking-changes.md  # Breaking changes
└── changelog.md             # Version changelog
```

## Writing Documentation

### Markdown Features

MkDocs Material supports enhanced markdown features:

- **Admonitions**: `!!! note`, `!!! warning`, `!!! danger`, `!!! tip`
- **Code blocks**: With syntax highlighting and line numbers
- **Tabs**: For alternative code examples
- **Tables**: Standard markdown tables
- **Task lists**: `- [ ]` and `- [x]`
- **Emojis**: `:smile:`, `:warning:`
- **Icons**: Material Design icons

### Code Examples

Always use async/await patterns:

```python
async def example():
    # Use a list for instruments, even for a single one
    suite = await TradingSuite.create(["MNQ"])

    # Access the context for the instrument
    mnq_context = suite["MNQ"]

    # Your code here, using the context
    # For example: await mnq_context.data.get_current_price()

    await suite.disconnect()
```

### API Documentation

We use mkdocstrings for auto-generated API docs, but currently most references are removed due to compatibility issues. Future work includes:

1. Fixing module imports for mkdocstrings
2. Adding proper docstrings to all public APIs
3. Enabling auto-generated API documentation

## Style Guide

### Headers

- Use `#` for page title
- Use `##` for main sections
- Use `###` for subsections
- Avoid going deeper than `####`

### Code

- Use `python` for code blocks
- Include imports in examples
- Show error handling
- Add comments for clarity

### Safety Warnings

Always include safety warnings for trading examples:

```markdown
!!! warning "Live Trading Risk"
    This example places real orders on the market. Always test with paper trading first.
```

## Contributing

1. Make changes in the `docs/` directory
2. Test locally with `mkdocs serve`
3. Ensure build passes with `mkdocs build --strict`
4. Submit PR with documentation changes

## Migration from Sphinx

This documentation was migrated from Sphinx (ReadTheDocs) to MkDocs. Key changes:

- `.rst` files converted to `.md`
- Sphinx directives replaced with MkDocs equivalents
- Auto-generated API docs temporarily disabled
- GitHub Pages deployment instead of ReadTheDocs

## Known Issues

1. **mkdocstrings**: Some API references are commented out due to import issues
2. **Encoding**: Some files had UTF-8 encoding issues (fixed with iconv)
3. **Missing diagrams**: Architecture diagrams need to be recreated

## Future Improvements

- [ ] Fix mkdocstrings integration for auto-generated API docs
- [ ] Add architecture diagrams using Mermaid
- [ ] Create interactive examples with embedded code runners
- [ ] Add search functionality enhancements
- [ ] Implement versioned documentation with Mike
- [ ] Add API playground for testing

## Resources

- [MkDocs Documentation](https://www.mkdocs.org/)
- [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/)
- [mkdocstrings](https://mkdocstrings.github.io/)
- [Mike (versioning)](https://github.com/jimporter/mike)
