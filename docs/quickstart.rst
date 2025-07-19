Quick Start Guide
=================

Get up and running with project-x-py in minutes.

Prerequisites
-------------

Before you begin, make sure you have:

1. Python 3.12 or higher installed
2. project-x-py package installed (see :doc:`installation`)
3. TopStepX account with API access
4. Your API credentials (username and API key)

Step 1: Set Up Credentials
---------------------------

Set your API credentials as environment variables::

   export PROJECT_X_API_KEY='your_api_key_here'
   export PROJECT_X_USERNAME='your_username_here'

On Windows::

   set PROJECT_X_API_KEY=your_api_key_here
   set PROJECT_X_USERNAME=your_username_here

Or create a ``.env`` file in your project directory::

   PROJECT_X_API_KEY=your_api_key_here
   PROJECT_X_USERNAME=your_username_here

Step 2: Create Your First Client
---------------------------------

.. code-block:: python

   from project_x_py import ProjectX

   # Create client using environment variables
   client = ProjectX.from_env()

   # Get account information
   account = client.get_account_info()
   print(f"Account: {account.name}")
   print(f"Balance: ${account.balance:,.2f}")

Step 3: Get Market Data
-----------------------

.. code-block:: python

   # Get historical data for Micro Gold futures
   data = client.get_data('MGC', days=5, interval=15)
   print(f"Retrieved {len(data)} bars of data")
   print(data.head())

   # Search for instruments
   instruments = client.search_instruments('MGC')
   for instrument in instruments:
       print(f"{instrument.name}: {instrument.description}")

Step 4: Place Your First Order
-------------------------------

.. warning::
   The following examples place real orders! Make sure you're using a demo account for testing.

.. code-block:: python

   from project_x_py import create_order_manager

   # Create order manager
   order_manager = create_order_manager(client)

   # Place a limit order
   response = order_manager.place_limit_order(
       contract_id='MGC',  # Micro Gold
       side=0,             # 0=Buy, 1=Sell
       size=1,             # 1 contract
       limit_price=2050.0  # Limit price
   )

   if response.success:
       print(f"Order placed! Order ID: {response.orderId}")
   else:
       print(f"Order failed: {response}")

Step 5: Monitor Positions
-------------------------

.. code-block:: python

   from project_x_py import create_position_manager

   # Create position manager
   position_manager = create_position_manager(client)

   # Get all open positions
   positions = position_manager.get_all_positions()
   for position in positions:
       direction = "LONG" if position.type == 1 else "SHORT"
       print(f"{position.contractId}: {direction} {position.size} @ ${position.averagePrice:.2f}")

   # Get portfolio metrics
   portfolio = position_manager.get_portfolio_pnl()
   print(f"Total positions: {portfolio['position_count']}")

Step 6: Real-time Data (Optional)
----------------------------------

.. code-block:: python

   from project_x_py import create_trading_suite

   # Create complete trading suite with real-time capabilities
   suite = create_trading_suite(
       instrument='MGC',
       project_x=client,
       jwt_token=client.session_token,
       account_id=str(account.id)
   )

   # Connect to real-time feeds
   suite['realtime_client'].connect()

   # Start real-time data collection
   suite['data_manager'].initialize(initial_days=1)
   suite['data_manager'].start_realtime_feed()

   # Get real-time OHLCV data
   live_data = suite['data_manager'].get_data('5min')
   print(f"Live data: {len(live_data)} bars")

Common Patterns
---------------

Basic Trading Workflow
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from project_x_py import ProjectX, create_order_manager, create_position_manager

   # 1. Initialize client
   client = ProjectX.from_env()

   # 2. Set up trading managers
   order_manager = create_order_manager(client)
   position_manager = create_position_manager(client)

   # 3. Check account status
   account = client.get_account_info()
   print(f"Account balance: ${account.balance:,.2f}")

   # 4. Get market data
   data = client.get_data('MGC', days=1, interval=5)
   current_price = float(data.select('close').tail(1).item())

   # 5. Place bracket order (entry + stop + target)
   bracket = order_manager.place_bracket_order(
       contract_id='MGC',
       side=0,                    # Buy
       size=1,
       entry_price=current_price - 5.0,   # Entry below market
       stop_loss_price=current_price - 10.0,  # $5 risk
       take_profit_price=current_price + 5.0  # $10 profit target
   )

   if bracket.success:
       print("Bracket order placed successfully!")

Market Analysis with Technical Indicators
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from project_x_py.indicators import RSI, SMA, BBANDS, MACD

   # Get data
   data = client.get_data('MGC', days=30, interval=60)

   # Calculate technical indicators using TA-Lib style functions
   data = RSI(data, period=14)
   data = SMA(data, period=20)
   data = SMA(data, period=50)
   data = BBANDS(data, period=20, std_dev=2.0)
   data = MACD(data, fast_period=12, slow_period=26, signal_period=9)

   # Check latest values
   latest = data.tail(1)
   print(f"Current RSI: {latest['rsi_14'].item():.2f}")
   print(f"Price: ${latest['close'].item():.2f}")
   print(f"SMA(20): ${latest['sma_20'].item():.2f}")
   print(f"SMA(50): ${latest['sma_50'].item():.2f}")
   print(f"MACD: {latest['macd'].item():.4f}")

   # Simple signal logic
   rsi_val = latest['rsi_14'].item()
   price = latest['close'].item()
   sma_20 = latest['sma_20'].item()
   sma_50 = latest['sma_50'].item()
   
   if rsi_val < 30 and price > sma_20 > sma_50:
       print("🟢 Potential BUY signal: Oversold RSI + Uptrend")
   elif rsi_val > 70 and price < sma_20 < sma_50:
       print("🔴 Potential SELL signal: Overbought RSI + Downtrend")

Error Handling
~~~~~~~~~~~~~~

.. code-block:: python

   from project_x_py import ProjectXError, ProjectXOrderError

   try:
       # Attempt to place order
       response = order_manager.place_limit_order('MGC', 0, 1, 2050.0)
       
   except ProjectXOrderError as e:
       print(f"Order error: {e}")
       
   except ProjectXError as e:
       print(f"API error: {e}")
       
   except Exception as e:
       print(f"Unexpected error: {e}")

Next Steps
----------

Now that you have the basics working:

1. **Technical Analysis**: Explore the :doc:`comprehensive indicators library <api/indicators>` (25+ TA-Lib compatible indicators)
2. **Learn the API**: Explore the :doc:`API reference <api/client>`
3. **Study Examples**: Check out :doc:`detailed examples <examples/basic_usage>`
4. **Configure Advanced Features**: See :doc:`configuration options <configuration>`
5. **Real-time Trading**: Learn about :doc:`real-time capabilities <user_guide/real_time>`
6. **Risk Management**: Read about :doc:`position management <user_guide/trading>`

Tips for Success
----------------

1. **Start with Demo**: Always test with a simulated account first
2. **Small Sizes**: Use minimal position sizes while learning
3. **Error Handling**: Always wrap API calls in try/catch blocks
4. **Rate Limits**: Be mindful of API rate limits
5. **Logging**: Enable debug logging during development::

      from project_x_py import setup_logging
      setup_logging(level='DEBUG')

Getting Help
------------

If you run into issues:

* Check the :doc:`troubleshooting section <installation>`
* Browse the :doc:`examples directory <examples/basic_usage>`
* Review the :doc:`API documentation <api/client>`
* Open an issue on `GitHub <https://github.com/TexasCoding/project-x-py/issues>`_ 