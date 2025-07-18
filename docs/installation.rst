Installation
============

This guide covers how to install project-x-py and its dependencies.

Requirements
------------

* Python 3.12 or higher
* TopStepX account with API access
* API credentials (username and API key)
* `uv <https://docs.astral.sh/uv/>`_ package manager (recommended)

Basic Installation
------------------

Install the latest stable version from PyPI using uv::

   uv add project-x-py

Or with pip if you prefer::

   pip install project-x-py

This will install the core package with all required dependencies:

* ``polars`` - Fast DataFrames for market data
* ``requests`` - HTTP client for API calls  
* ``pytz`` - Timezone handling

Optional Dependencies
---------------------

Real-time Features
~~~~~~~~~~~~~~~~~~

For real-time market data and WebSocket support::

   uv add "project-x-py[realtime]"

Or with pip::

   pip install project-x-py[realtime]

This includes:

* ``signalrcore`` - SignalR client for real-time connections
* ``websocket-client`` - WebSocket support

Development Tools
~~~~~~~~~~~~~~~~~

For development and testing::

   uv add "project-x-py[dev]"

Or with pip::

   pip install project-x-py[dev]

This includes:

* ``ruff`` - Fast Python linter
* ``pytest`` - Testing framework
* ``mypy`` - Type checking
* ``black`` - Code formatting
* ``pre-commit`` - Git hooks

Documentation
~~~~~~~~~~~~~

For building documentation::

   uv add "project-x-py[docs]"

Or with pip::

   pip install project-x-py[docs]

This includes:

* ``sphinx`` - Documentation generator
* ``sphinx-rtd-theme`` - ReadTheDocs theme
* ``myst-parser`` - Markdown support

All Features
~~~~~~~~~~~~

To install everything::

   uv add "project-x-py[all]"

Or with pip::

   pip install project-x-py[all]

Development Installation
------------------------

For development, clone the repository and install with uv::

   git clone https://github.com/TexasCoding/project-x-py.git
   cd project-x-py
   uv sync --extra dev --extra docs

Or with pip in editable mode::

   pip install -e .[dev,test,docs]

Verify Installation
-------------------

Test your installation::

   python -c "import project_x_py; print(project_x_py.get_version())"

Check environment setup::

   python -c "from project_x_py import check_setup; print(check_setup())"

Next Steps
----------

After installation:

1. :doc:`Set up authentication <authentication>`
2. :doc:`Configure the client <configuration>` 
3. :doc:`Try the quickstart guide <quickstart>`

Troubleshooting
---------------

Common Issues
~~~~~~~~~~~~~

**Import Error: No module named 'project_x_py'**

Make sure you've installed the package::

   uv add project-x-py

**Version Conflicts**

If you have dependency conflicts, uv handles this automatically. For pip users, try creating a fresh virtual environment::

   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install project-x-py

**Real-time Connection Issues**

Make sure you have the real-time dependencies::

   uv add "project-x-py[realtime]"

Getting Help
~~~~~~~~~~~~

* Check the :doc:`API documentation <api/client>`
* Browse :doc:`examples <examples/basic_usage>`
* Open an issue on `GitHub <https://github.com/TexasCoding/project-x-py/issues>`_ 