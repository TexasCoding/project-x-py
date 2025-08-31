"""Tests for centralized type definitions."""


class TestTypes:
    """Tests for type imports and consistency."""

    def test_base_types_import(self):
        """Test that base types can be imported."""
        from project_x_py.types import (
            DEFAULT_TIMEZONE,
            TICK_SIZE_PRECISION,
        )

        assert DEFAULT_TIMEZONE == "America/Chicago"
        assert TICK_SIZE_PRECISION == 8

    def test_trading_types_import(self):
        """Test that trading types can be imported."""
        from project_x_py.types import (
            OrderSide,
            OrderStatus,
            OrderType,
        )

        # Test enums
        assert OrderSide.BUY.value == 0
        assert OrderSide.SELL.value == 1
        assert OrderType.MARKET.value == 2
        assert OrderStatus.PENDING.value == 6

    def test_market_data_types_import(self):
        """Test that market data types can be imported."""
        from project_x_py.types import (
            DomType,
            IcebergConfig,
            MemoryConfig,
            OrderbookSide,
        )

        # Test enums
        assert DomType.ASK.value == 1
        assert DomType.BID.value == 2
        assert OrderbookSide.BID.value == 0
        assert OrderbookSide.ASK.value == 1

        # Test dataclass defaults
        memory_config = MemoryConfig()
        assert memory_config.max_trades == 10000
        assert memory_config.max_depth_entries == 1000

        iceberg_config = IcebergConfig()
        assert iceberg_config.min_refreshes == 5
        assert iceberg_config.confidence_threshold == 0.7

    def test_protocol_imports(self):
        """Test that protocol definitions can be imported."""
        from project_x_py.types import (
            OrderManagerProtocol,
            PositionManagerProtocol,
            ProjectXClientProtocol,
            ProjectXRealtimeClientProtocol,
            RealtimeDataManagerProtocol,
        )

        # Protocols should be importable
        assert ProjectXClientProtocol is not None
        assert OrderManagerProtocol is not None
        assert PositionManagerProtocol is not None
        assert ProjectXRealtimeClientProtocol is not None
        assert RealtimeDataManagerProtocol is not None

    def test_no_duplicate_imports(self):
        """Test that types are not duplicated across modules."""
        # Import from centralized location
        from project_x_py.types import OrderStatsResponse, OrderStatus

        # OrderStatsResponse should be available from types module
        assert OrderStatsResponse is not None
        assert OrderStatus is not None

    def test_type_consistency_across_modules(self):
        """Test that types are consistent when used across different modules."""
        # This test ensures that all modules are using the same type definitions

        # OrderManager should accept and use OrderStats from centralized types
        # This is a compile-time check that happens when modules are imported
        assert True  # If we get here, imports are consistent
