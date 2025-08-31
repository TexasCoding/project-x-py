"""Unit tests for data models in project_x_py.models."""

from __future__ import annotations

import pytest

from project_x_py.models import (
    Account,
    BracketOrderResponse,
    Instrument,
    MarketDataEvent,
    Order,
    OrderPlaceResponse,
    OrderUpdateEvent,
    Position,
    PositionUpdateEvent,
    ProjectXConfig,
    Trade,
)


class TestInstrumentAndAccount:
    def test_instrument_creation_defaults(self):
        inst = Instrument(
            id="CON.F.US.MNQ.H25",
            name="MNQH25",
            description="Micro Nasdaq March 2025",
            tickSize=0.25,
            tickValue=0.5,
            activeContract=True,
        )
        assert inst.id == "CON.F.US.MNQ.H25"
        assert inst.symbolId is None

    def test_account_creation(self):
        acct = Account(
            id=101,
            name="Sim-101",
            balance=10000.0,
            canTrade=True,
            isVisible=True,
            simulated=True,
        )
        assert acct.name == "Sim-101"
        assert acct.balance == pytest.approx(10000.0)


class TestOrderModel:
    def make_order(self, **overrides) -> Order:
        base = {
            "id": 1,
            "accountId": 10,
            "contractId": "CON.F.US.MNQ.H25",
            "creationTimestamp": "2024-01-01T00:00:00Z",
            "updateTimestamp": "2024-01-01T00:00:10Z",
            "status": 1,  # OPEN
            "type": 1,  # LIMIT
            "side": 0,  # BUY
            "size": 5,
        }
        base.update(overrides)
        return Order(**base)

    def test_order_state_properties(self):
        o = self.make_order(status=1)  # OPEN
        assert o.is_open and o.is_working and not o.is_terminal

        o = self.make_order(status=6)  # PENDING
        assert o.is_working and not o.is_open

        o = self.make_order(status=2)  # FILLED
        assert o.is_filled and o.is_terminal

        o = self.make_order(status=3)  # CANCELLED
        assert o.is_cancelled and o.is_terminal

        o = self.make_order(status=5)  # REJECTED
        assert o.is_rejected and o.is_terminal

    def test_order_side_type_status_strings(self):
        o = self.make_order(side=0, type=2, status=6)  # BUY, MARKET, PENDING
        assert o.side_str == "BUY"
        assert o.type_str == "MARKET"
        assert o.status_str == "PENDING"

        # Unknown values map to UNKNOWN
        o = self.make_order(side=1, type=99, status=99)
        assert o.side_str == "SELL"
        assert o.type_str == "UNKNOWN"
        assert o.status_str == "UNKNOWN"

    def test_order_fill_progress_and_remaining(self):
        o = self.make_order(size=10, fillVolume=None)
        assert o.filled_percent == 0.0
        assert o.remaining_size == 10

        o = self.make_order(size=10, fillVolume=3)
        assert o.filled_percent == pytest.approx(30.0)
        assert o.remaining_size == 7

        o = self.make_order(size=0, fillVolume=0)
        assert o.filled_percent == 0.0

    def test_order_symbol_extraction(self):
        o = self.make_order(contractId="CON.F.US.MNQ.H25")
        assert o.symbol == "MNQ"

        # Fallback: no dots
        o = self.make_order(contractId="MNQH25")
        assert o.symbol == "MNQH25"


class TestPositionModel:
    def make_position(self, **overrides) -> Position:
        base = {
            "id": 42,
            "accountId": 10,
            "contractId": "CON.F.US.MGC.M25",
            "creationTimestamp": "2024-01-01T00:00:00Z",
            "type": 1,  # LONG
            "size": 2,
            "averagePrice": 2050.0,
        }
        base.update(overrides)
        return Position(**base)

    def test_basic_properties_and_indexing(self):
        p = self.make_position()
        assert p.is_long and not p.is_short
        assert p.direction == "LONG"
        assert p["averagePrice"] == pytest.approx(2050.0)
        assert p.symbol == "MGC"

    def test_short_position_helpers(self):
        p = self.make_position(type=2, size=3)
        assert p.is_short
        assert p.direction == "SHORT"
        assert p.signed_size == -3

    def test_direction_undefined(self):
        p = self.make_position(type=0)
        assert p.direction == "UNDEFINED"
        assert p.signed_size == 2  # stays positive

    def test_total_cost_and_unrealized_pnl(self):
        p = self.make_position(size=4, averagePrice=100.0)
        assert p.total_cost == pytest.approx(400.0)

        # Long: price up => positive PnL
        assert p.unrealized_pnl(101.0) == pytest.approx(4.0)
        # Custom tick value multiplier
        assert p.unrealized_pnl(101.0, tick_value=5.0) == pytest.approx(20.0)

        # Short: price down => positive PnL
        p_short = self.make_position(type=2, size=4, averagePrice=100.0)
        assert p_short.unrealized_pnl(99.0) == pytest.approx(4.0)

        # Undefined => zero
        p_undef = self.make_position(type=0)
        assert p_undef.unrealized_pnl(999.0) == 0.0

    def test_symbol_fallback(self):
        p = self.make_position(contractId="SYNTH-ABC")
        assert p.symbol == "SYNTH-ABC"


class TestTradeModel:
    def test_trade_slots_and_attributes(self):
        t = Trade(
            id=7,
            accountId=10,
            contractId="CON.F.US.MNQ.H25",
            creationTimestamp="2024-01-01T00:00:00Z",
            price=5000.0,
            profitAndLoss=None,
            fees=2.5,
            side=0,
            size=1,
            voided=False,
            orderId=123,
        )

        # Access attributes
        assert t.price == pytest.approx(5000.0)
        assert t.profitAndLoss is None  # half-turn trade allowed

        # __slots__ should prevent setting unknown attributes
        with pytest.raises(AttributeError):
            t.extra = "not-allowed"  # type: ignore[attr-defined]


class TestBracketAndResponses:
    def test_order_place_response(self):
        r = OrderPlaceResponse(
            orderId=555, success=True, errorCode=0, errorMessage=None
        )
        assert r.success is True
        assert r.orderId == 555

    def test_bracket_order_response(self):
        entry = OrderPlaceResponse(
            orderId=1, success=True, errorCode=0, errorMessage=None
        )
        # stop/target responses could be None if not created
        br = BracketOrderResponse(
            success=True,
            entry_order_id=1,
            stop_order_id=2,
            target_order_id=3,
            entry_price=100.0,
            stop_loss_price=95.0,
            take_profit_price=110.0,
            entry_response=entry,
            stop_response=None,
            target_response=None,
            error_message=None,
        )
        assert br.success is True
        assert br.entry_price == pytest.approx(100.0)
        assert br.entry_response and br.entry_response.orderId == 1


class TestConfigAndEvents:
    def test_projectxconfig_defaults_and_overrides(self):
        cfg = ProjectXConfig()
        assert cfg.api_url == "https://api.topstepx.com/api"
        assert cfg.user_hub_url.endswith("/hubs/user")
        assert cfg.market_hub_url.endswith("/hubs/market")
        assert cfg.timezone == "America/Chicago"
        assert cfg.timeout_seconds == 30
        assert cfg.retry_attempts == 3

        # Override a few and ensure they stick
        cfg = ProjectXConfig(api_url="https://custom/api", timezone="UTC")
        assert cfg.api_url == "https://custom/api"
        assert cfg.timezone == "UTC"

    def test_event_dataclasses(self):
        oue = OrderUpdateEvent(orderId=1, status=2, fillVolume=1, updateTimestamp="t")
        pue = PositionUpdateEvent(
            positionId=2,
            contractId="CON.F.US.MNQ.H25",
            size=1,
            averagePrice=10.0,
            updateTimestamp="t",
        )
        mde = MarketDataEvent(
            contractId="CON.F.US.MNQ.H25",
            lastPrice=1.0,
            bid=None,
            ask=1.25,
            volume=10,
            timestamp="t",
        )

        assert oue.status == 2
        assert pue.size == 1 and pue.contractId.endswith("MNQ.H25")
        assert mde.ask == pytest.approx(1.25)
