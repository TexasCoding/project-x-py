Authentication
==============

This guide covers how to set up authentication for the ProjectX API.

API Credentials
---------------

To use project-x-py, you need:

1. **Username**: Your TopStepX account username
2. **API Key**: A valid API key from your TopStepX account

Getting Your Credentials
-------------------------

1. Log in to your TopStepX account
2. Navigate to the API section
3. Generate a new API key if you don't have one
4. Copy both your username and API key

.. warning::
   Keep your API credentials secure! Never commit them to version control or share them publicly.

Setting Up Credentials
-----------------------

Environment Variables (Recommended)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The most secure way to store credentials is using environment variables:

**Linux/macOS:**

.. code-block:: bash

   export PROJECT_X_API_KEY='your_api_key_here'
   export PROJECT_X_USERNAME='your_username_here'

**Windows Command Prompt:**

.. code-block:: cmd

   set PROJECT_X_API_KEY=your_api_key_here
   set PROJECT_X_USERNAME=your_username_here

**Windows PowerShell:**

.. code-block:: powershell

   $env:PROJECT_X_API_KEY='your_api_key_here'
   $env:PROJECT_X_USERNAME='your_username_here'

.env File
~~~~~~~~~

Create a ``.env`` file in your project directory:

.. code-block:: text

   PROJECT_X_API_KEY=your_api_key_here
   PROJECT_X_USERNAME=your_username_here

.. note::
   Make sure to add ``.env`` to your ``.gitignore`` file to avoid committing credentials.

Direct Instantiation
~~~~~~~~~~~~~~~~~~~~~

For testing or when environment variables aren't available:

.. code-block:: python

   from project_x_py import ProjectX

   client = ProjectX(
       username='your_username',
       api_key='your_api_key'
   )

Using the Client
----------------

Environment Variables
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from project_x_py import ProjectX

   # Automatically loads from environment variables
   client = ProjectX.from_env()

   # Verify authentication
   account = client.get_account_info()
   print(f"Authenticated as: {account.name}")

With Account Selection
~~~~~~~~~~~~~~~~~~~~~~

If you have multiple accounts:

.. code-block:: python

   # List all available accounts
   accounts = client.list_accounts()
   for account in accounts:
       print(f"Account: {account['name']} (ID: {account['id']})")

   # Create client for specific account
   client = ProjectX.from_env(account_name="My Trading Account")

Authentication Verification
---------------------------

Check if authentication is working:

.. code-block:: python

   from project_x_py import check_setup

   status = check_setup()
   print(status)

   # Manual verification
   try:
       client = ProjectX.from_env()
       account = client.get_account_info()
       print(f"✅ Authentication successful: {account.name}")
   except Exception as e:
       print(f"❌ Authentication failed: {e}")

Session Management
------------------

The client automatically handles:

- JWT token generation and refresh
- Session expiration handling
- Automatic re-authentication

You can check session status:

.. code-block:: python

   # Check session health
   health = client.get_health_status()
   print(f"Authenticated: {health['authenticated']}")
   print(f"Token expires: {health['token_expires_at']}")

Configuration Options
---------------------

Advanced authentication settings:

.. code-block:: python

   from project_x_py import ProjectXConfig

   # Custom configuration
   config = ProjectXConfig(
       base_url="https://api.topstepx.com",
       timeout_seconds=30,
       retry_attempts=3,
       # ... other options
   )

   client = ProjectX(
       username='your_username',
       api_key='your_api_key',
       config=config
   )

Troubleshooting
---------------

Common Authentication Issues
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Invalid Credentials**

.. code-block:: text

   ProjectXAuthenticationError: Invalid username or API key

- Verify your username and API key are correct
- Check for extra spaces or hidden characters
- Ensure the API key hasn't expired

**Network Issues**

.. code-block:: text

   ProjectXConnectionError: Connection failed

- Check your internet connection
- Verify the API endpoint is accessible
- Check if there are firewall restrictions

**Rate Limiting**

.. code-block:: text

   ProjectXRateLimitError: Rate limit exceeded

- Reduce the frequency of API calls
- Implement proper rate limiting in your code
- Contact TopStepX if you need higher limits

Debug Mode
~~~~~~~~~~

Enable debug logging to troubleshoot issues:

.. code-block:: python

   from project_x_py import setup_logging

   # Enable debug logging
   setup_logging(level='DEBUG')

   # Now all API calls will be logged
   client = ProjectX.from_env()

Best Practices
--------------

1. **Use Environment Variables**: Never hardcode credentials in your source code
2. **Rotate Keys Regularly**: Generate new API keys periodically
3. **Monitor Usage**: Keep track of your API usage and rate limits
4. **Error Handling**: Always implement proper error handling for authentication failures
5. **Secure Storage**: Use secure credential storage in production environments

Example: Production Setup
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   import os
   from project_x_py import ProjectX, ProjectXAuthenticationError

   def create_authenticated_client():
       """Create an authenticated client with proper error handling."""
       try:
           # Check if credentials are available
           if not os.getenv('PROJECT_X_API_KEY'):
               raise ValueError("PROJECT_X_API_KEY environment variable not set")
           if not os.getenv('PROJECT_X_USERNAME'):
               raise ValueError("PROJECT_X_USERNAME environment variable not set")
           
           # Create client
           client = ProjectX.from_env()
           
           # Verify authentication
           account = client.get_account_info()
           print(f"Authenticated successfully: {account.name}")
           
           return client
           
       except ProjectXAuthenticationError as e:
           print(f"Authentication failed: {e}")
           raise
       except Exception as e:
           print(f"Client creation failed: {e}")
           raise

   # Usage
   client = create_authenticated_client()

Next Steps
----------

Once authentication is working:

1. :doc:`Configure the client <configuration>`
2. :doc:`Try the quickstart guide <quickstart>`
3. :doc:`Explore the API reference <api/client>` 