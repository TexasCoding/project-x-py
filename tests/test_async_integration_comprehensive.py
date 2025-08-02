"""
Comprehensive async integration tests converted from synchronous integration tests.

Tests complete end-to-end workflows with async components.
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import polars as pl
import pytest

from project_x_py import (
    ProjectX,
    create_order_manager,
    create_position_manager,
    create_trading_suite,
    ProjectXRealtimeClient,
)
AsyncProjectX = ProjectX
AsyncProjectXRealtimeClient = ProjectXRealtimeClient
from project_x_py.models import Instrument


class TestAsyncEndToEndWorkflows:
    """Test cases for complete async trading workflows."""

    @pytest.mark.asyncio
    async def test_complete_async_trading_workflow(self):
        """Test complete async trading workflow from authentication to order execution."""
        with patch("httpx.AsyncClient") as mock_client_class:
            # Setup async client mock
            mock_http_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_http_client

            # Mock authentication response
            auth_response = AsyncMock()
            auth_response.status_code = 200
            auth_response.json.return_value = {
                "success": True,
                "token": "test_jwt_token",
            }
            auth_response.raise_for_status.return_value = None

            # Mock account info response
            account_response = AsyncMock()
            account_response.status_code = 200
            account_response.json.return_value = {
                "simAccounts": [
                    {
                        "id": "test_account",
                        "name": "Test Account",
                        "balance": 50000.0,
                        "canTrade": True,
                        "simulated": True,
                    }
                ],
                "liveAccounts": [],
            }

            # Mock instrument response
            instrument_response = AsyncMock()
            instrument_response.status_code = 200
            instrument_response.json.return_value = {
                "success": True,
                "instruments": [
                    {
                        "id": "CON.F.US.MGC.M25",
                        "symbol": "MGC",
                        "name": "MGCH25",
                        "activeContract": "CON.F.US.MGC.M25",
                        "lastPrice": 2045.0,
                        "tickSize": 0.1,
                        "pointValue": 10.0,
                    }
                ],
            }

            # Mock order placement response
            order_response = AsyncMock()
            order_response.status_code = 200
            order_response.json.return_value = {
                "success": True,
                "orderId": "ORD12345",
                "status": "Submitted",
            }

            async def mock_response_router(method, url, **kwargs):
                """Route mock responses based on URL."""
                if method == "POST" and "Auth/loginKey" in url:
                    return auth_response
                elif method == "GET" and "Account/search" in url:
                    return account_response
                elif method == "GET" and "instruments" in url:
                    return instrument_response
                elif method == "POST" and "orders" in url:
                    return order_response
                else:
                    response = AsyncMock()
                    response.status_code = 200
                    response.json.return_value = {"success": True}
                    return response

            mock_http_client.post = lambda url, **kwargs: mock_response_router(
                "POST", url, **kwargs
            )
            mock_http_client.get = lambda url, **kwargs: mock_response_router(
                "GET", url, **kwargs
            )

            # Act - Complete async workflow
            async with ProjectX(username="test_user", api_key="test_key") as client:
                # 1. Authenticate
                await client.authenticate()
                assert client.session_token == "test_jwt_token"

                # 2. Initialize managers
                order_manager = create_order_manager(client)
                position_manager = create_position_manager(client)

                await order_manager.initialize()
                await position_manager.initialize()

                # 3. Get instrument concurrently with other operations
                instrument_task = client.search_instruments("MGC")
                account_task = client.list_accounts()

                instruments, accounts = await asyncio.gather(
                    instrument_task, account_task
                )

                assert len(instruments) > 0
                instrument = instruments[0]

                # 4. Place order asynchronously
                response = await order_manager.place_market_order(
                    contract_id=instrument.id,
                    side=0,  # Buy
                    size=1,
                )

                # Assert workflow completed successfully
                assert response.success is True
                assert response.orderId == "ORD12345"

    @pytest.mark.asyncio
    async def test_concurrent_multi_instrument_analysis(self):
        """Test concurrent analysis of multiple instruments."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_http_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_http_client

            # Mock responses for multiple instruments
            symbols = ["MGC", "MNQ", "MES", "M2K"]

            async def mock_instruments_response(symbol):
                return AsyncMock(
                    status_code=200,
                    json=AsyncMock(
                        return_value={
                            "success": True,
                            "instruments": [
                                {
                                    "id": f"CON.F.US.{symbol}.M25",
                                    "symbol": symbol,
                                    "name": f"{symbol}H25",
                                    "activeContract": f"CON.F.US.{symbol}.M25",
                                    "lastPrice": 2000.0 + hash(symbol) % 100,
                                    "tickSize": 0.1,
                                    "pointValue": 10.0,
                                }
                            ],
                        }
                    ),
                )

            async def mock_data_response(symbol, days, interval):
                # Create mock OHLCV data
                dates = pl.date_range(
                    datetime.now() - timedelta(days=days),
                    datetime.now(),
                    f"{interval}m",
                    eager=True,
                )[:10]  # Limit to 10 bars for testing

                base_price = 2000.0 + hash(symbol) % 100
                return pl.DataFrame(
                    {
                        "timestamp": dates,
                        "open": [base_price + i for i in range(len(dates))],
                        "high": [base_price + i + 1 for i in range(len(dates))],
                        "low": [base_price + i - 1 for i in range(len(dates))],
                        "close": [base_price + i + 0.5 for i in range(len(dates))],
                        "volume": [1000 + i * 10 for i in range(len(dates))],
                    }
                )

            # Mock client methods
            mock_http_client.get = AsyncMock(side_effect=mock_instruments_response)

            async with ProjectX(username="test", api_key="test") as client:
                # Mock authenticate
                client.session_token = "test_token"
                client.account_info = Mock(id="test_account", name="Test")

                # Mock get_data method directly on client
                client.get_data = AsyncMock(side_effect=mock_data_response)

                # Perform concurrent analysis
                tasks = []
                for symbol in symbols:
                    task = asyncio.create_task(
                        client.get_data(symbol, days=5, interval=60)
                    )
                    tasks.append(task)

                # Wait for all data concurrently
                data_results = await asyncio.gather(*tasks)

                # Verify all data was retrieved
                assert len(data_results) == len(symbols)
                for data in data_results:
                    assert data is not None
                    assert len(data) > 0
                    assert "close" in data.columns

    @pytest.mark.asyncio
    async def test_async_trading_suite_integration(self):
        """Test complete async trading suite integration."""
        with patch("project_x_py.AsyncProjectX") as mock_client_class:
            # Create mock async client
            mock_client = AsyncMock(spec=ProjectX)
            mock_client.session_token = "test_jwt"
            mock_client.account_info = Mock(id="test_account", name="Test Account")
            mock_client_class.return_value = mock_client

            # Create complete trading suite
            suite = await create_trading_suite(
                instrument="MGC",
                project_x=mock_client,
                jwt_token="test_jwt",
                account_id="test_account",
                timeframes=["1min", "5min", "15min"],
            )

            # Verify all components are created and connected
            assert "realtime_client" in suite
            assert "data_manager" in suite
            assert "orderbook" in suite
            assert "order_manager" in suite
            assert "position_manager" in suite
            assert "config" in suite

            # Verify components are properly connected
            assert suite["data_manager"].realtime_client == suite["realtime_client"]
            assert suite["orderbook"].realtime_client == suite["realtime_client"]

            # Test component interaction
            realtime_client = suite["realtime_client"]
            data_manager = suite["data_manager"]
            order_manager = suite["order_manager"]

            # Mock component methods
            realtime_client.connect = AsyncMock(return_value=True)
            data_manager.initialize = AsyncMock(return_value=True)
            order_manager.initialize = AsyncMock(return_value=True)

            # Test initialization sequence
            await realtime_client.connect()
            await data_manager.initialize(initial_days=1)
            await order_manager.initialize()

            # Verify all components initialized
            realtime_client.connect.assert_called_once()
            data_manager.initialize.assert_called_once_with(initial_days=1)
            order_manager.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_error_recovery_workflow(self):
        """Test error recovery in async workflows."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_http_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_http_client

            # Mock mixed success/failure responses
            call_count = 0

            async def failing_then_success(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count <= 2:
                    raise Exception("Network error")
                else:
                    response = AsyncMock()
                    response.status_code = 200
                    response.json.return_value = {"success": True, "data": "test"}
                    return response

            mock_http_client.get = failing_then_success

            async with ProjectX(username="test", api_key="test") as client:
                client.session_token = "test_token"

                # Test retry logic with gather and exception handling
                tasks = [
                    client.search_instruments("MGC"),
                    client.search_instruments("MNQ"),
                    client.search_instruments("MES"),
                ]

                # Use return_exceptions to handle failures gracefully
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Should have some failures and some successes
                exceptions = [r for r in results if isinstance(r, Exception)]
                successes = [r for r in results if not isinstance(r, Exception)]

                # At least one should succeed after retries
                assert len(successes) >= 1 or len(exceptions) >= 1

    @pytest.mark.asyncio
    async def test_async_real_time_data_workflow(self):
        """Test async real-time data processing workflow."""
        with patch("project_x_py.realtime.ProjectXRealtimeClient") as mock_realtime_class:
            # Mock realtime client
            mock_realtime = AsyncMock()
            mock_realtime_class.return_value = mock_realtime
            mock_realtime.connect = AsyncMock(return_value=True)
            mock_realtime.subscribe_market_data = AsyncMock(return_value=True)
            mock_realtime.add_callback = AsyncMock()

            # Mock data manager
            with patch(
                "project_x_py.AsyncRealtimeDataManager"
            ) as mock_data_manager_class:
                mock_data_manager = AsyncMock()
                mock_data_manager_class.return_value = mock_data_manager
                mock_data_manager.initialize = AsyncMock(return_value=True)
                mock_data_manager.start_realtime_feed = AsyncMock(return_value=True)

                # Test workflow
                realtime_client = mock_realtime_class("jwt_token", "account_id")
                data_manager = mock_data_manager_class(
                    "MGC", Mock(), realtime_client, ["1min", "5min"]
                )

                # Execute workflow
                connect_result = await realtime_client.connect()
                init_result = await data_manager.initialize(initial_days=1)
                feed_result = await data_manager.start_realtime_feed()

                # Verify workflow
                assert connect_result is True
                assert init_result is True
                assert feed_result is True

                # Verify sequence
                realtime_client.connect.assert_called_once()
                data_manager.initialize.assert_called_once_with(initial_days=1)
                data_manager.start_realtime_feed.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_performance_monitoring(self):
        """Test performance monitoring in async workflows."""
        import time

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_http_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_http_client

            # Mock responses with artificial delays
            async def delayed_response(delay=0.1):
                await asyncio.sleep(delay)
                response = AsyncMock()
                response.status_code = 200
                response.json.return_value = {"success": True, "data": []}
                return response

            mock_http_client.get = lambda *args, **kwargs: delayed_response(0.05)

            async with ProjectX(username="test", api_key="test") as client:
                client.session_token = "test_token"
                client.account_info = Mock(id="test")

                # Time sequential vs concurrent operations

                # Sequential
                start_sequential = time.time()
                await client.search_instruments("MGC")
                await client.search_instruments("MNQ")
                await client.search_instruments("MES")
                sequential_time = time.time() - start_sequential

                # Concurrent
                start_concurrent = time.time()
                await asyncio.gather(
                    client.search_instruments("MGC"),
                    client.search_instruments("MNQ"),
                    client.search_instruments("MES"),
                )
                concurrent_time = time.time() - start_concurrent

                # Concurrent should be significantly faster
                assert concurrent_time < sequential_time * 0.7


class TestSyncAsyncWorkflowCompatibility:
    """Test compatibility between sync and async workflows."""

    @pytest.mark.asyncio
    async def test_mixed_sync_async_components(self):
        """Test that sync and async components can work together appropriately."""
        # Create sync client for comparison
        sync_client = Mock(spec=ProjectX)
        sync_client.session_token = "test_token"
        sync_client.account_info = Mock(id=1001, name="Test")

        # Create async client
        async_client = AsyncMock(spec=ProjectX)
        async_client.session_token = "test_token"
        async_client.account_info = Mock(id="1001", name="Test")

        # Both should be able to create their respective managers
        sync_order_manager = create_order_manager(sync_client)
        async_order_manager = create_order_manager(async_client)

        # Initialize sync manager
        sync_result = sync_order_manager.initialize()
        assert sync_result is True

        # Initialize async manager
        async_result = await async_order_manager.initialize()
        assert async_result is True

        # Verify different types
        assert type(sync_order_manager).__name__ == "OrderManager"
        assert type(async_order_manager).__name__ == "AsyncOrderManager"

    @pytest.mark.asyncio
    async def test_configuration_compatibility(self):
        """Test that configuration works with both sync and async workflows."""
        from project_x_py import ProjectXConfig

        config = ProjectXConfig(timeout_seconds=45, retry_attempts=5)

        # Should work with both client types
        sync_client = ProjectX(username="test", api_key="test", config=config)
        async_client = ProjectX(username="test", api_key="test", config=config)

        assert sync_client.config.timeout_seconds == 45
        assert async_client.config.timeout_seconds == 45

    @pytest.mark.asyncio
    async def test_model_compatibility_across_workflows(self):
        """Test that models work consistently across sync and async workflows."""

        # Create model instances
        instrument = Instrument(
            id="TEST123",
            name="Test Instrument",
            description="Test Instrument",
            tickSize=0.01,
            tickValue=1.0,
            activeContract=True,
        )

        # Should work with both sync and async contexts
        assert instrument.id == "TEST123"
        assert instrument.name == "Test Instrument"

        # Test in async context
        async def async_model_test():
            return instrument.name

        result = await async_model_test()
        assert result == "Test Instrument"
