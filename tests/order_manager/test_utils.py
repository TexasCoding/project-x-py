"""Unit tests for order_manager.utils."""

from unittest.mock import MagicMock

import pytest

from project_x_py.order_manager import utils


class TestAlignPriceToTick:
    """Tests for align_price_to_tick utility."""

    def test_aligns_up(self):
        """Price rounds to nearest tick size (upwards)."""
        assert utils.align_price_to_tick(100.07, 0.1) == 100.1

    def test_aligns_down(self):
        """Price rounds to nearest tick size (downwards)."""
        assert utils.align_price_to_tick(99.92, 0.25) == 100.0

    def test_zero_tick_size(self):
        """Returns price unchanged if tick size is zero."""
        assert utils.align_price_to_tick(50.0, 0.0) == 50.0

    def test_negative_tick_size(self):
        """Returns price unchanged if tick size is negative."""
        assert utils.align_price_to_tick(50.0, -1.0) == 50.0


@pytest.mark.asyncio
async def test_align_price_to_tick_size_returns_input(monkeypatch):
    """Patch get_instrument to always return tickSize=0.5; should align price to 100.0."""

    class DummyClient:
        async def get_instrument(self, contract_id):
            class Instrument:
                tickSize = 0.5

            return Instrument()

    price = await utils.align_price_to_tick_size(100.2, "MGC", DummyClient())
    assert price == 100.0


@pytest.mark.asyncio
async def test_align_price_to_tick_size_price_none():
    """Returns None if price is None."""
    result = await utils.align_price_to_tick_size(None, "MGC", MagicMock())
    assert result is None


@pytest.mark.asyncio
async def test_align_price_to_tick_size_handles_missing_instrument(monkeypatch):
    """Returns original price if instrument lookup fails."""

    class DummyClient:
        async def get_instrument(self, contract_id):
            return None

    price = await utils.align_price_to_tick_size(101.5, "FOO", DummyClient())
    assert price == 101.5


@pytest.mark.asyncio
async def test_resolve_contract_id(monkeypatch):
    """resolve_contract_id fetches instrument and returns expected dict."""

    class DummyInstrument:
        id = "X"
        name = "X"
        tickSize = 0.1
        tickValue = 1.0
        activeContract = True

    class DummyClient:
        async def get_instrument(self, contract_id):
            return DummyInstrument()

    result = await utils.resolve_contract_id("X", DummyClient())
    assert result == {
        "id": "X",
        "name": "X",
        "tickSize": 0.1,
        "tickValue": 1.0,
        "activeContract": True,
    }


@pytest.mark.asyncio
async def test_resolve_contract_id_handles_missing(monkeypatch):
    """Returns None if instrument not found."""

    class DummyClient:
        async def get_instrument(self, contract_id):
            return None

    assert await utils.resolve_contract_id("X", DummyClient()) is None


class TestAlignPriceToTickEdgeCases:
    """Test edge cases for align_price_to_tick function."""

    def test_exact_tick_alignment(self):
        """Price already aligned to tick should remain unchanged."""
        assert utils.align_price_to_tick(100.0, 0.25) == 100.0
        assert utils.align_price_to_tick(99.75, 0.25) == 99.75

    def test_very_small_tick_sizes(self):
        """Handle very small tick sizes correctly."""
        assert utils.align_price_to_tick(100.123456, 0.000001) == pytest.approx(100.123456)
        assert utils.align_price_to_tick(100.1234567, 0.0000001) == pytest.approx(100.1234567)

    def test_large_tick_sizes(self):
        """Handle large tick sizes correctly."""
        assert utils.align_price_to_tick(1234.56, 10.0) == 1230.0
        assert utils.align_price_to_tick(1235.0, 10.0) == 1240.0  # Rounds to nearest tick
        assert utils.align_price_to_tick(1239.99, 10.0) == 1240.0

    def test_negative_prices(self):
        """Handle negative prices correctly."""
        assert utils.align_price_to_tick(-100.07, 0.1) == -100.1
        assert utils.align_price_to_tick(-99.92, 0.25) == -100.0

    def test_zero_price(self):
        """Handle zero price correctly."""
        assert utils.align_price_to_tick(0.0, 0.25) == 0.0
        assert utils.align_price_to_tick(0.1, 0.25) == 0.0
        assert utils.align_price_to_tick(0.13, 0.25) == 0.25

    def test_floating_point_precision(self):
        """Handle floating point precision issues."""
        # Test cases that might cause floating point precision issues
        result = utils.align_price_to_tick(100.1 + 0.2, 0.25)  # 100.30000000000001
        assert result == 100.25

    def test_various_tick_sizes(self):
        """Test alignment with various common tick sizes."""
        # Common futures tick sizes
        assert utils.align_price_to_tick(4567.73, 0.25) == 4567.75  # ES
        assert utils.align_price_to_tick(17005.3, 1.0) == 17005.0   # NQ
        assert utils.align_price_to_tick(2134.567, 0.005) == 2134.565  # Bonds


@pytest.mark.asyncio
class TestAlignPriceToTickSizeAsync:
    """Test async align_price_to_tick_size function edge cases."""

    async def test_client_exception_handling(self):
        """Handle client exceptions gracefully."""
        class FailingClient:
            async def get_instrument(self, contract_id):
                raise Exception("Network error")

        # Should return original price on exception
        price = await utils.align_price_to_tick_size(100.2, "MNQ", FailingClient())
        assert price == 100.2

    async def test_instrument_without_tick_size(self):
        """Handle instrument without tickSize attribute."""
        class InstrumentWithoutTickSize:
            pass

        class ClientWithBadInstrument:
            async def get_instrument(self, contract_id):
                return InstrumentWithoutTickSize()

        price = await utils.align_price_to_tick_size(100.2, "BAD", ClientWithBadInstrument())
        assert price == 100.2

    async def test_instrument_with_zero_tick_size(self):
        """Handle instrument with zero tick size."""
        class ZeroTickInstrument:
            tickSize = 0.0

        class ClientWithZeroTick:
            async def get_instrument(self, contract_id):
                return ZeroTickInstrument()

        price = await utils.align_price_to_tick_size(100.2, "ZERO", ClientWithZeroTick())
        assert price == 100.2

    async def test_various_contract_scenarios(self):
        """Test various contract scenarios."""
        class VariableTickInstrument:
            def __init__(self, tick_size):
                self.tickSize = tick_size

        class VariableTickClient:
            def __init__(self, tick_size):
                self.tick_size = tick_size

            async def get_instrument(self, contract_id):
                return VariableTickInstrument(self.tick_size)

        # Test ES-like contract (0.25 tick)
        es_client = VariableTickClient(0.25)
        price = await utils.align_price_to_tick_size(4567.73, "ES", es_client)
        assert price == 4567.75

        # Test NQ-like contract (1.0 tick)
        nq_client = VariableTickClient(1.0)
        price = await utils.align_price_to_tick_size(17005.3, "NQ", nq_client)
        assert price == 17005.0

        # Test fine-grained contract (0.01 tick)
        fine_client = VariableTickClient(0.01)
        price = await utils.align_price_to_tick_size(123.456, "FINE", fine_client)
        assert price == 123.46


@pytest.mark.asyncio
class TestResolveContractIdExtended:
    """Extended tests for resolve_contract_id function."""

    async def test_resolve_contract_id_with_all_attributes(self):
        """Test resolve_contract_id with full instrument attributes."""
        class FullInstrument:
            id = "MNQ"
            name = "Micro E-mini NASDAQ-100"
            tickSize = 0.25
            tickValue = 0.5
            activeContract = True

        class FullClient:
            async def get_instrument(self, contract_id):
                return FullInstrument()

        result = await utils.resolve_contract_id("MNQ", FullClient())
        assert result == {
            "id": "MNQ",
            "name": "Micro E-mini NASDAQ-100",
            "tickSize": 0.25,
            "tickValue": 0.5,
            "activeContract": True,
        }

    async def test_resolve_contract_id_client_exception(self):
        """Test resolve_contract_id with client exception."""
        class FailingClient:
            async def get_instrument(self, contract_id):
                raise Exception("API error")

        result = await utils.resolve_contract_id("FAIL", FailingClient())
        assert result is None
