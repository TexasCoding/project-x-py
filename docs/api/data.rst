Data API
========

Real-time market data, orderbook analysis, and technical indicators.

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

.. autoclass:: OrderBook
   :members:
   :undoc-members:
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

Technical Analysis Utilities
----------------------------

Moving Averages
~~~~~~~~~~~~~~~

.. autofunction:: project_x_py.utils.calculate_sma
.. autofunction:: project_x_py.utils.calculate_ema

Momentum Indicators
~~~~~~~~~~~~~~~~~~

.. autofunction:: project_x_py.utils.calculate_rsi
.. autofunction:: project_x_py.utils.calculate_macd
.. autofunction:: project_x_py.utils.calculate_stochastic
.. autofunction:: project_x_py.utils.calculate_williams_r

Volatility Indicators
~~~~~~~~~~~~~~~~~~~~~

.. autofunction:: project_x_py.utils.calculate_bollinger_bands
.. autofunction:: project_x_py.utils.calculate_atr
.. autofunction:: project_x_py.utils.calculate_volatility_metrics

Trend Indicators
~~~~~~~~~~~~~~~~

.. autofunction:: project_x_py.utils.calculate_adx
.. autofunction:: project_x_py.utils.calculate_commodity_channel_index

Volume Analysis
~~~~~~~~~~~~~~~

.. autofunction:: project_x_py.utils.calculate_volume_profile
.. autofunction:: project_x_py.utils.analyze_bid_ask_spread

Pattern Recognition
~~~~~~~~~~~~~~~~~~~

.. autofunction:: project_x_py.utils.detect_candlestick_patterns
.. autofunction:: project_x_py.utils.detect_chart_patterns
.. autofunction:: project_x_py.utils.find_support_resistance_levels

Data Utilities
--------------

.. autofunction:: project_x_py.utils.create_data_snapshot
.. autofunction:: project_x_py.utils.convert_timeframe_to_seconds
.. autofunction:: project_x_py.utils.get_market_session_info
.. autofunction:: project_x_py.utils.is_market_hours 