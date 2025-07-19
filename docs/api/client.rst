Client API
==========

The main ProjectX client provides access to market data, account information, and core trading functionality.

ProjectX Client
---------------

.. currentmodule:: project_x_py

.. automodule:: project_x_py.client
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

.. autoclass:: ProjectX
   :members:
   :undoc-members:
   :show-inheritance:

Configuration Management
------------------------

.. autoclass:: project_x_py.config.ConfigManager
   :members:
   :undoc-members:
   :show-inheritance:

Configuration Models
--------------------

.. autoclass:: project_x_py.models.ProjectXConfig
   :members:
   :undoc-members:
   :show-inheritance:

Factory Functions
-----------------

Client Creation
~~~~~~~~~~~~~~~

.. autofunction:: create_client

Configuration Helpers
~~~~~~~~~~~~~~~~~~~~~

.. autofunction:: project_x_py.config.load_default_config
.. autofunction:: project_x_py.config.create_config_template
.. autofunction:: project_x_py.config.check_environment

Utility Functions
~~~~~~~~~~~~~~~~~

.. autofunction:: get_version
.. autofunction:: quick_start
.. autofunction:: check_setup 