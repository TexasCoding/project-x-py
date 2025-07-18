project-x-py Documentation
==========================

.. image:: https://img.shields.io/pypi/v/project-x-py.svg
   :target: https://pypi.org/project/project-x-py/
   :alt: PyPI version

.. image:: https://img.shields.io/pypi/pyversions/project-x-py.svg
   :target: https://pypi.org/project/project-x-py/
   :alt: Python versions

.. image:: https://img.shields.io/github/license/TexasCoding/project-x-py.svg
   :target: https://github.com/TexasCoding/project-x-py/blob/main/LICENSE
   :alt: License

.. image:: https://readthedocs.org/projects/project-x-py/badge/?version=latest
   :target: https://project-x-py.readthedocs.io/en/latest/?badge=latest
   :alt: Documentation Status

**project-x-py** is a professional Python client for the TopStepX ProjectX Gateway API, providing comprehensive access to futures trading, real-time market data, and advanced market analysis tools.

Quick Start
-----------

Install the package::

   uv add project-x-py

Or with pip::

   pip install project-x-py

Set up your credentials::

   export PROJECT_X_API_KEY='your_api_key'
   export PROJECT_X_USERNAME='your_username'

Start trading::

   from project_x_py import ProjectX
   
   # Create client
   client = ProjectX.from_env()
   
   # Get market data
   data = client.get_data('MGC', days=5, interval=15)
   
   # Place an order
   from project_x_py import create_order_manager
   order_manager = create_order_manager(client)
   response = order_manager.place_limit_order('MGC', 0, 1, 2050.0)

Key Features
------------

🚀 **Core Trading Features**
   * Complete order management (market, limit, stop, bracket orders)
   * Real-time position tracking and portfolio management
   * Advanced risk management and position sizing
   * Multi-account support

📊 **Market Data & Analysis**
   * Historical OHLCV data with multiple timeframes
   * Real-time market data feeds via WebSocket
   * Advanced orderbook analysis and market depth
   * 50+ technical indicators and chart patterns

🔧 **Developer Tools**
   * Comprehensive Python typing support
   * Extensive examples and tutorials
   * Built-in logging and debugging tools
   * Flexible configuration management

⚡ **Real-time Capabilities**
   * Live market data streaming
   * Real-time order and position updates
   * Event-driven architecture
   * WebSocket-based connections

Table of Contents
-----------------

.. toctree::
   :maxdepth: 2
   :caption: Getting Started

   installation
   quickstart
   authentication
   configuration

.. toctree::
   :maxdepth: 2
   :caption: User Guide

   user_guide/client
   user_guide/market_data
   user_guide/trading
   user_guide/real_time
   user_guide/analysis

.. toctree::
   :maxdepth: 2
   :caption: Examples

   examples/basic_usage
   examples/trading_strategies
   examples/real_time_data
   examples/portfolio_management

.. toctree::
   :maxdepth: 2
   :caption: API Reference

   api/client
   api/trading
   api/data
   api/models
   api/utilities

.. toctree::
   :maxdepth: 2
   :caption: Advanced Topics

   advanced/architecture
   advanced/performance
   advanced/debugging
   advanced/contributing

.. toctree::
   :maxdepth: 1
   :caption: Additional Information

   changelog
   license
   support

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search` 