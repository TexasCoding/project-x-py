# Documentation for project-x-py

This directory contains the Sphinx documentation for the project-x-py package.

## Building the Documentation

### Prerequisites

Install the documentation dependencies:

```bash
# With uv (recommended)
uv sync --extra docs

# Or with pip
pip install -e .[docs]
```

### Building HTML Documentation

**Linux/macOS:**
```bash
make html
```

**Windows:**
```bash
make.bat html
```

The built documentation will be in `_build/html/`. Open `_build/html/index.html` in your browser.

### Live Reload Development

For development with automatic rebuilding:

```bash
# With uv
uv add --dev sphinx-autobuild
make livehtml

# Or with pip
pip install sphinx-autobuild
make livehtml
```

This will start a local server with live reload at http://localhost:8000

### Other Build Targets

- `make clean` - Clean build directory
- `make linkcheck` - Check for broken links
- `make coverage` - Check documentation coverage
- `make latex` - Build LaTeX documentation
- `make epub` - Build EPUB documentation

## Documentation Structure

```
docs/
├── conf.py                 # Sphinx configuration
├── index.rst              # Main documentation page
├── installation.rst       # Installation guide
├── quickstart.rst         # Quick start tutorial
├── authentication.rst     # Authentication setup
├── configuration.rst      # Configuration guide
├── api/                   # API reference
│   ├── client.rst         # Client API documentation
│   ├── trading.rst        # Trading API documentation
│   ├── data.rst           # Data API documentation
│   ├── models.rst         # Models and exceptions
│   └── utilities.rst      # Utility functions
├── user_guide/           # User guides
├── examples/             # Examples and tutorials
├── advanced/             # Advanced topics
├── _static/              # Static files (CSS, images)
├── _templates/           # Custom Sphinx templates
└── _build/               # Built documentation (ignored by git)
```

## Writing Documentation

### RestructuredText (RST)

Most documentation files use RST format. Key syntax:

```rst
Title
=====

Subtitle
--------

**Bold text**
*Italic text*

Code blocks::

    code here

.. code-block:: python

   print("Python code")

.. warning::
   This is a warning box

.. note::
   This is a note box
```

### API Documentation

API documentation is automatically generated using Sphinx autodoc. The source code docstrings are parsed to create the API reference.

### Adding New Pages

1. Create a new `.rst` file in the appropriate directory
2. Add the file to the appropriate `toctree` directive in `index.rst` or parent file
3. Rebuild the documentation

## Deployment

The documentation is automatically built and deployed to ReadTheDocs when changes are pushed to the main branch.

- **Live documentation**: https://project-x-py.readthedocs.io
- **ReadTheDocs project**: https://readthedocs.org/projects/project-x-py/

## Contributing

When contributing to documentation:

1. Follow the existing structure and style
2. Use clear, concise language
3. Include code examples where appropriate
4. Test that documentation builds without errors
5. Check for broken links with `make linkcheck`

### Style Guide

- Use present tense ("returns" not "will return")
- Use active voice when possible
- Include type hints in code examples
- Add docstring examples for all public functions
- Keep line length under 80 characters in RST files

## Troubleshooting

### Common Issues

**Build errors:**
- Check that all dependencies are installed: `uv sync --extra docs` (or `pip install -e .[docs]`)
- Verify Python path is correct in `conf.py`
- Check for syntax errors in RST files

**Missing modules:**
- Ensure the package is installed in development mode: `uv sync` (or `pip install -e .`)
- Check that `sys.path` is configured correctly in `conf.py`

**Broken links:**
- Run `make linkcheck` to identify broken external links
- Update or remove outdated links

### Getting Help

- Sphinx documentation: https://www.sphinx-doc.org/
- ReadTheDocs guides: https://docs.readthedocs.io/
- Project issues: https://github.com/TexasCoding/project-x-py/issues 