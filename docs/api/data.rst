Data API
========

Real-time market data, Level 2 orderbook analysis, and institutional-grade market microstructure tools.

Real-time Data Management
-------------------------

.. currentmodule:: project_x_py

.. autoclass:: ProjectXRealtimeDataManager
   :members:
   :undoc-members:
   :show-inheritance:

Real-time Client
----------------

.. autoclass:: ProjectXRealtimeClient
   :members:
   :undoc-members:
   :show-inheritance:

Orderbook Analysis
------------------

.. note::
   **Level 2 OrderBook API**: For comprehensive Level 2 orderbook analysis including 
   iceberg detection, market imbalance analysis, and institutional-grade market 
   microstructure tools, see the dedicated :doc:`orderbook` module.

.. autoclass:: OrderBook
   :members: get_orderbook_snapshot, get_best_bid_ask, get_advanced_market_metrics
   :show-inheritance:

Data Factory Functions
----------------------

.. autofunction:: create_realtime_client
.. autofunction:: create_data_manager
.. autofunction:: create_orderbook

Instrument Models
-----------------

.. autoclass:: project_x_py.models.Instrument
   :members:
   :undoc-members:
   :show-inheritance:

.. note::
   **Technical Indicators**: For comprehensive technical analysis with 25+ indicators, 
   see the :doc:`indicators` module which provides TA-Lib compatible indicators 
   optimized for Polars DataFrames.

Data Utilities
--------------

.. autofunction:: project_x_py.utils.create_data_snapshot
.. autofunction:: project_x_py.utils.convert_timeframe_to_seconds
.. autofunction:: project_x_py.utils.get_market_session_info
.. autofunction:: project_x_py.utils.is_market_hours 