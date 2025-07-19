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

**project-x-py** is a professional Python client for the TopStepX ProjectX Gateway API, providing comprehensive access to futures trading, real-time market data, Level 2 orderbook analysis, and a complete technical analysis suite with 25+ TA-Lib compatible indicators.

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
   from project_x_py.indicators import RSI, SMA, MACD
   
   # Create client
   client = ProjectX.from_env()
   
   # Get market data with technical analysis
   data = client.get_data('MGC', days=30, interval=60)
   data = RSI(data, period=14)         # Add RSI
   data = SMA(data, period=20)         # Add moving average
   data = MACD(data)                   # Add MACD
   
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
   * **Level 2 orderbook analysis** with institutional-grade features
   * **25+ Technical Indicators** with TA-Lib compatibility (RSI, MACD, Bollinger Bands, etc.)
   * **Advanced market microstructure** analysis (iceberg detection, order flow, volume profile)

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
   api/orderbook
   api/indicators
   api/models
   api/utilities

Indices and Search
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

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