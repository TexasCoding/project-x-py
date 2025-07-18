Configuration
=============

Learn how to configure project-x-py for your specific needs.

Overview
--------

project-x-py can be configured in several ways:

1. **Environment variables** (recommended for credentials)
2. **Configuration objects** (for application settings)
3. **Constructor parameters** (for one-off settings)

Default Configuration
---------------------

The package comes with sensible defaults:

.. code-block:: python

   from project_x_py import load_default_config

   config = load_default_config()
   print(config)

Configuration Options
---------------------

Core Settings
~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 15 15 45

   * - Setting
     - Type
     - Default
     - Description
   * - ``base_url``
     - str
     - ``"https://api.topstepx.com"``
     - API base URL
   * - ``timeout_seconds``
     - int
     - ``30``
     - Request timeout in seconds
   * - ``retry_attempts``
     - int
     - ``3``
     - Number of retry attempts for failed requests
   * - ``requests_per_minute``
     - int
     - ``120``
     - Rate limit for API requests

WebSocket Settings
~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 15 15 45

   * - Setting
     - Type
     - Default
     - Description
   * - ``user_hub_url``
     - str
     - ``"https://rtc.topstepx.com/hubs/user"``
     - User data WebSocket URL
   * - ``market_hub_url``
     - str
     - ``"https://rtc.topstepx.com/hubs/market"``
     - Market data WebSocket URL
   * - ``ping_interval``
     - int
     - ``30``
     - WebSocket ping interval (seconds)

Timezone Settings
~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 15 15 45

   * - Setting
     - Type
     - Default
     - Description
   * - ``timezone``
     - str
     - ``"America/Chicago"``
     - Default timezone for timestamps

Configuration Methods
---------------------

Environment Variables
~~~~~~~~~~~~~~~~~~~~~

Set configuration via environment variables:

.. code-block:: bash

   # Required credentials
   export PROJECT_X_API_KEY='your_api_key'
   export PROJECT_X_USERNAME='your_username'
   
   # Optional configuration
   export PROJECT_X_BASE_URL='https://api.topstepx.com'
   export PROJECT_X_TIMEOUT='60'
   export PROJECT_X_TIMEZONE='America/New_York'

Configuration Object
~~~~~~~~~~~~~~~~~~~~

Create a custom configuration:

.. code-block:: python

   from project_x_py import ProjectXConfig, ProjectX

   # Custom configuration
   config = ProjectXConfig(
       base_url="https://api.topstepx.com",
       timeout_seconds=60,
       retry_attempts=5,
       requests_per_minute=200,
       timezone="America/New_York"
   )

   # Use with client
   client = ProjectX(
       username='your_username',
       api_key='your_api_key',
       config=config
   )

Configuration File
~~~~~~~~~~~~~~~~~~

Create a configuration file:

.. code-block:: python

   from project_x_py import create_config_template

   # Create a template configuration file
   create_config_template('config.json')

Then load it:

.. code-block:: python

   from project_x_py import ConfigManager

   # Load configuration from file
   config_manager = ConfigManager('config.json')
   config = config_manager.load_config()

   client = ProjectX.from_env(config=config)

Advanced Configuration
----------------------

Custom Endpoints
~~~~~~~~~~~~~~~~

For testing or custom deployments:

.. code-block:: python

   config = ProjectXConfig(
       base_url="https://sandbox-api.topstepx.com",
       user_hub_url="https://sandbox-rtc.topstepx.com/hubs/user",
       market_hub_url="https://sandbox-rtc.topstepx.com/hubs/market"
   )

Rate Limiting
~~~~~~~~~~~~~

Adjust rate limiting for your usage pattern:

.. code-block:: python

   config = ProjectXConfig(
       requests_per_minute=60,  # Lower rate for batch processing
       timeout_seconds=120      # Longer timeout for slow connections
   )

Multiple Accounts
~~~~~~~~~~~~~~~~~

Configure for specific accounts:

.. code-block:: python

   # Production account
   prod_client = ProjectX.from_env(account_name="Production Trading")

   # Testing account  
   test_client = ProjectX.from_env(account_name="Demo Account")

Environment-Specific Configs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   import os
   from project_x_py import ProjectXConfig

   # Load different configs based on environment
   if os.getenv('ENVIRONMENT') == 'production':
       config = ProjectXConfig(
           base_url="https://api.topstepx.com",
           timeout_seconds=30,
           retry_attempts=3
       )
   else:
       config = ProjectXConfig(
           base_url="https://sandbox-api.topstepx.com", 
           timeout_seconds=60,
           retry_attempts=5
       )

Logging Configuration
---------------------

Configure logging for debugging and monitoring:

.. code-block:: python

   from project_x_py import setup_logging

   # Basic logging
   setup_logging(level='INFO')

   # Detailed logging for debugging
   setup_logging(level='DEBUG', format='detailed')

   # Custom logging configuration
   setup_logging(
       level='WARNING',
       format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
       filename='trading.log'
   )

Configuration Validation
-------------------------

Validate your configuration:

.. code-block:: python

   from project_x_py import check_setup

   # Check overall setup
   status = check_setup()
   if status['status'] != 'Ready to use':
       print("Configuration issues found:")
       for issue in status['issues']:
           print(f"  - {issue}")

   # Test client connection
   try:
       client = ProjectX.from_env()
       account = client.get_account_info()
       print(f"✅ Configuration valid: {account.name}")
   except Exception as e:
       print(f"❌ Configuration error: {e}")

Best Practices
--------------

Security
~~~~~~~~

1. **Never hardcode credentials** in source code
2. **Use environment variables** for sensitive data
3. **Rotate API keys** regularly
4. **Use different keys** for different environments

Performance
~~~~~~~~~~~

1. **Adjust timeouts** based on your network
2. **Set appropriate rate limits** for your usage
3. **Use connection pooling** for high-frequency trading
4. **Enable compression** for large data transfers

Monitoring
~~~~~~~~~~

1. **Enable logging** appropriate for your environment
2. **Monitor API usage** to avoid rate limits  
3. **Set up alerts** for connection failures
4. **Track performance metrics**

Example Configurations
----------------------

High-Frequency Trading
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   config = ProjectXConfig(
       timeout_seconds=10,      # Fast timeouts
       retry_attempts=1,        # Minimal retries
       requests_per_minute=500, # High rate limit
       ping_interval=15         # Frequent pings
   )

Batch Processing
~~~~~~~~~~~~~~~~

.. code-block:: python

   config = ProjectXConfig(
       timeout_seconds=300,     # Long timeouts
       retry_attempts=10,       # More retries
       requests_per_minute=30   # Lower rate limit
   )

Development/Testing
~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   config = ProjectXConfig(
       base_url="https://sandbox-api.topstepx.com",
       timeout_seconds=60,
       retry_attempts=5,
       timezone="UTC"           # Consistent timezone for testing
   )

Troubleshooting
---------------

Common Configuration Issues
~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Invalid timezone:**

.. code-block:: text

   ValueError: Invalid timezone: 'Invalid/Timezone'

Use a valid timezone from the `pytz` library:

.. code-block:: python

   import pytz
   print(pytz.all_timezones)  # List all valid timezones

**Connection timeouts:**

.. code-block:: text

   ProjectXConnectionError: Request timeout

Increase the timeout or check your network:

.. code-block:: python

   config = ProjectXConfig(timeout_seconds=120)

**Rate limit errors:**

.. code-block:: text

   ProjectXRateLimitError: Rate limit exceeded

Reduce your request rate:

.. code-block:: python

   config = ProjectXConfig(requests_per_minute=60)

Getting Help
~~~~~~~~~~~~

If you're having configuration issues:

1. Check the :doc:`troubleshooting guide <installation>`
2. Validate your setup with ``check_setup()``
3. Enable debug logging to see detailed errors
4. Review the :doc:`authentication guide <authentication>`

Next Steps
----------

Once your configuration is working:

1. :doc:`Try the quickstart guide <quickstart>`
2. :doc:`Explore trading features <user_guide/trading>`
3. :doc:`Set up real-time data <user_guide/real_time>` 