"""Wave A remaining-audit tests: OCO protection, daily-loss events, stop math, ManagedTrade.

These tests define the expected live-money behavior. If they fail, fix the
implementation, not the tests.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from project_x_py.event_bus import EventBus, EventType
from project_x_py.models import Account, Instrument, Order, Position
from project_x_py.risk_manager import RiskConfig, RiskManager
from project_x_py.risk_manager.managed_trade import ManagedTrade
from project_x_py.types import OrderSide, OrderStatus


def _mnq_instrument() -> Instrument:
    return Instrument(
        id="MNQ",
        name="Micro E-mini Nasdaq",
        description="Micro E-mini Nasdaq futures",
        tickSize=0.25,
        tickValue=5.0,
        activeContract=True,
    )


def _account(balance: float = 100_000.0) -> Account:
    return Account(
        id=12345,
        name="Test Account",
        balance=balance,
        canTrade=True,
        isVisible=True,
        simulated=True,
    )


def _install_oco_tracking(order_manager: MagicMock) -> MagicMock:
    """Give a MagicMock OrderManager real OCO pair tracking."""
    order_manager.oco_pairs = {}
    order_manager.cancel_order = AsyncMock(return_value=True)

    async def track_oco_pair(order1_id: str, order2_id: str) -> None:
        order_manager.oco_pairs[str(order1_id)] = str(order2_id)
        order_manager.oco_pairs[str(order2_id)] = str(order1_id)

    async def handle_oco_fill(order_id: str) -> None:
        order_id = str(order_id)
        other = order_manager.oco_pairs.get(order_id)
        if other is None:
            return
        await order_manager.cancel_order(int(other))
        order_manager.oco_pairs.pop(order_id, None)
        order_manager.oco_pairs.pop(other, None)

    order_manager.track_oco_pair = track_oco_pair
    order_manager._handle_oco_fill = handle_oco_fill
    return order_manager


def _order_response(order_id: int) -> MagicMock:
    response = MagicMock()
    response.success = True
    response.orderId = order_id
    return response


@pytest.fixture
def mock_client() -> MagicMock:
    client = MagicMock()
    client.account_info = _account()
    client.list_accounts = AsyncMock(return_value=[client.account_info])
    client.get_instrument = AsyncMock(return_value=_mnq_instrument())
    return client


@pytest.fixture
def mock_order_manager() -> MagicMock:
    om = MagicMock()
    om.search_open_orders = AsyncMock(return_value=[])
    om.place_stop_order = AsyncMock(return_value=_order_response(100))
    om.place_limit_order = AsyncMock(return_value=_order_response(101))
    om.place_market_order = AsyncMock(return_value=_order_response(200))
    om.modify_order = AsyncMock(return_value=True)
    om.cancel_order = AsyncMock(return_value=True)
    return _install_oco_tracking(om)


@pytest.fixture
def mock_position() -> MagicMock:
    position = MagicMock(spec=Position)
    position.id = 1
    position.contractId = "MNQ"
    position.averagePrice = 18000.0
    position.size = 2
    position.netQuantity = 2
    position.is_long = True
    return position


@pytest.fixture
def mock_position_manager() -> MagicMock:
    pm = MagicMock()
    pm.get_all_positions = AsyncMock(return_value=[])
    pm.get_position = AsyncMock(return_value=None)
    pm.close_position_direct = AsyncMock(return_value={"success": True})
    pm.close_position = AsyncMock(return_value={"success": True})
    return pm


@pytest.fixture
async def risk_manager(
    mock_client: MagicMock,
    mock_order_manager: MagicMock,
    mock_position_manager: MagicMock,
) -> RiskManager:
    event_bus = EventBus()
    rm = RiskManager(
        project_x=mock_client,
        order_manager=mock_order_manager,
        event_bus=event_bus,
        position_manager=mock_position_manager,
        config=RiskConfig(),
    )
    if hasattr(rm, "_init_task"):
        try:
            await asyncio.wait_for(rm._init_task, timeout=1.0)
        except TimeoutError:
            pass
    return rm


def _mock_order(
    *,
    size: int = 1,
    contract_id: str = "MNQ",
    side: int = 0,
    order_type: int = 2,
) -> Order:
    return Order(
        id=0,
        accountId=12345,
        contractId=contract_id,
        creationTimestamp=datetime.now().isoformat(),
        updateTimestamp=None,
        status=6,
        type=order_type,
        side=side,
        size=size,
    )


class TestProtectiveOrdersAreOco:
    """A1: stop and target must cancel each other on fill."""

    @pytest.mark.asyncio
    async def test_target_fill_cancels_working_stop(
        self,
        risk_manager: RiskManager,
        mock_position: MagicMock,
        mock_order_manager: MagicMock,
    ) -> None:
        result = await risk_manager.attach_risk_orders(
            position=mock_position,
            stop_loss=17987.5,
            take_profit=18025.0,
        )
        stop_id = result["bracket_order"].stop_order_id
        target_id = result["bracket_order"].target_order_id
        assert stop_id == 100
        assert target_id == 101
        mock_order_manager.place_limit_order.assert_called()
        assert (
            mock_order_manager.place_limit_order.call_args.kwargs.get("linked_order_id")
            == stop_id
        )

        await mock_order_manager._handle_oco_fill(str(target_id))

        mock_order_manager.cancel_order.assert_called_with(stop_id)

    @pytest.mark.asyncio
    async def test_stop_fill_cancels_working_target(
        self,
        risk_manager: RiskManager,
        mock_position: MagicMock,
        mock_order_manager: MagicMock,
    ) -> None:
        result = await risk_manager.attach_risk_orders(
            position=mock_position,
            stop_loss=17987.5,
            take_profit=18025.0,
        )
        stop_id = result["bracket_order"].stop_order_id
        target_id = result["bracket_order"].target_order_id

        await mock_order_manager._handle_oco_fill(str(stop_id))

        mock_order_manager.cancel_order.assert_called_with(target_id)


class TestDailyLossFromPositionCloseEvents:
    """A3: daily loss/trade counters must move from real close events."""

    @pytest.mark.asyncio
    async def test_closed_losing_position_blocks_next_validate_trade(
        self,
        mock_client: MagicMock,
        mock_order_manager: MagicMock,
        mock_position_manager: MagicMock,
    ) -> None:
        event_bus = EventBus()
        config = RiskConfig(max_daily_loss_amount=Decimal("1000"))
        rm = RiskManager(
            project_x=mock_client,
            order_manager=mock_order_manager,
            event_bus=event_bus,
            position_manager=mock_position_manager,
            config=config,
        )
        if hasattr(rm, "_init_task"):
            try:
                await asyncio.wait_for(rm._init_task, timeout=1.0)
            except TimeoutError:
                pass

        position = MagicMock(spec=Position)
        position.id = 42
        position.contractId = "MNQ"
        position.size = 0
        position.averagePrice = 18000.0

        await event_bus.emit(
            EventType.POSITION_CLOSED,
            {
                "contract_id": "MNQ",
                "position": position,
                "pnl": -1500.0,
            },
        )

        result = await rm.validate_trade(_mock_order())

        assert result["is_valid"] is False
        assert any("Daily loss" in reason for reason in result["reasons"])

    @pytest.mark.asyncio
    async def test_gateway_position_closed_payload_blocks_next_validate_trade(
        self,
        mock_client: MagicMock,
        mock_order_manager: MagicMock,
        mock_position_manager: MagicMock,
    ) -> None:
        """Live GatewayUserPosition close is {contractId, id, size:0} plus computed pnl."""
        event_bus = EventBus()
        config = RiskConfig(max_daily_loss_amount=Decimal("1000"))
        rm = RiskManager(
            project_x=mock_client,
            order_manager=mock_order_manager,
            event_bus=event_bus,
            position_manager=mock_position_manager,
            config=config,
        )
        if hasattr(rm, "_init_task"):
            try:
                await asyncio.wait_for(rm._init_task, timeout=1.0)
            except TimeoutError:
                pass

        await event_bus.emit(
            EventType.POSITION_CLOSED,
            {
                "id": 42,
                "contractId": "CON.F.US.MNQ.U25",
                "size": 0,
                "averagePrice": 17900.0,
                "type": 1,
                "pnl": -1500.0,
            },
        )

        result = await rm.validate_trade(_mock_order())

        assert result["is_valid"] is False
        assert any("Daily loss" in reason for reason in result["reasons"])

    @pytest.mark.asyncio
    async def test_record_trade_result_does_not_double_count_event(
        self,
        mock_client: MagicMock,
        mock_order_manager: MagicMock,
        mock_position_manager: MagicMock,
    ) -> None:
        event_bus = EventBus()
        rm = RiskManager(
            project_x=mock_client,
            order_manager=mock_order_manager,
            event_bus=event_bus,
            position_manager=mock_position_manager,
            config=RiskConfig(),
        )
        if hasattr(rm, "_init_task"):
            try:
                await asyncio.wait_for(rm._init_task, timeout=1.0)
            except TimeoutError:
                pass

        position = MagicMock(spec=Position)
        position.id = 7
        position.contractId = "MNQ"

        await rm.record_trade_result("7", pnl=-200.0, duration_seconds=30)
        await event_bus.emit(
            EventType.POSITION_CLOSED,
            {"position": position, "pnl": -200.0},
        )

        assert rm._daily_loss == Decimal("200")
        assert rm._daily_trades == 1


class TestUnifiedStopDistance:
    """A4: attach_risk_orders and calculate_stop_loss share ticks/percent math."""

    @pytest.mark.asyncio
    async def test_calculate_stop_loss_fixed_ticks_mnq(
        self, risk_manager: RiskManager
    ) -> None:
        risk_manager.config.stop_loss_type = "fixed"
        risk_manager.config.default_stop_distance = Decimal("50")
        instrument = _mnq_instrument()

        stop = await risk_manager.calculate_stop_loss(
            entry_price=18000.0,
            side=OrderSide.BUY,
            instrument=instrument,
        )

        # 50 ticks * 0.25 = 12.5 points → 17987.5
        assert stop == 17987.5

    @pytest.mark.asyncio
    async def test_calculate_stop_loss_percentage_mnq(
        self, risk_manager: RiskManager
    ) -> None:
        risk_manager.config.stop_loss_type = "percentage"
        risk_manager.config.default_stop_distance = Decimal("50")
        instrument = _mnq_instrument()

        stop = await risk_manager.calculate_stop_loss(
            entry_price=18000.0,
            side=OrderSide.BUY,
            instrument=instrument,
        )

        # 50% of 18000 = 9000 → 9000, aligned to 0.25
        assert stop == 9000.0

    @pytest.mark.asyncio
    async def test_attach_risk_orders_fixed_ticks_mnq(
        self,
        risk_manager: RiskManager,
        mock_position: MagicMock,
        mock_order_manager: MagicMock,
    ) -> None:
        risk_manager.config.use_stop_loss = True
        risk_manager.config.use_take_profit = False
        risk_manager.config.stop_loss_type = "fixed"
        risk_manager.config.default_stop_distance = Decimal("50")

        result = await risk_manager.attach_risk_orders(position=mock_position)

        assert result["stop_loss"] == 17987.5
        call_kwargs = mock_order_manager.place_stop_order.call_args.kwargs
        assert call_kwargs["stop_price"] == 17987.5

    @pytest.mark.asyncio
    async def test_attach_risk_orders_percentage_mnq(
        self,
        risk_manager: RiskManager,
        mock_position: MagicMock,
        mock_order_manager: MagicMock,
    ) -> None:
        risk_manager.config.use_stop_loss = True
        risk_manager.config.use_take_profit = False
        risk_manager.config.stop_loss_type = "percentage"
        risk_manager.config.default_stop_distance = Decimal("1")  # 1%

        result = await risk_manager.attach_risk_orders(position=mock_position)

        # 18000 * 1% = 180 → stop 17820
        assert result["stop_loss"] == 17820.0


class TestManagedTradeDoesNotLeaveNakedPosition:
    """A5: flatten on attach failure; validate scale-in; resize scale-out."""

    @pytest.fixture
    def managed_trade(
        self,
        risk_manager: RiskManager,
        mock_order_manager: MagicMock,
        mock_position_manager: MagicMock,
    ) -> ManagedTrade:
        return ManagedTrade(
            risk_manager=risk_manager,
            order_manager=mock_order_manager,
            position_manager=mock_position_manager,
            instrument_id="MNQ",
        )

    @pytest.mark.asyncio
    async def test_attach_failure_after_fill_flattens_or_has_stop(
        self,
        mock_order_manager: MagicMock,
        mock_position_manager: MagicMock,
    ) -> None:
        risk = MagicMock()
        risk.config = RiskConfig()
        risk.validate_trade = AsyncMock(
            return_value={"is_valid": True, "reasons": [], "warnings": []}
        )
        risk.attach_risk_orders = AsyncMock(side_effect=RuntimeError("attach failed"))

        position = MagicMock(spec=Position)
        position.contractId = "MNQ"
        position.size = 2
        position.is_long = True
        position.averagePrice = 18000.0
        mock_position_manager.get_all_positions = AsyncMock(return_value=[position])
        mock_position_manager.close_position_direct = AsyncMock(
            return_value={"success": True}
        )
        mock_position_manager.close_position = AsyncMock(return_value={"success": True})

        entry = MagicMock(spec=Order)
        entry.id = 1
        entry.is_working = False
        entry.is_filled = True
        entry.status = OrderStatus.FILLED.value
        mock_order_manager.search_open_orders = AsyncMock(return_value=[entry])
        mock_order_manager.place_market_order = AsyncMock(
            return_value=_order_response(1)
        )

        trade = ManagedTrade(
            risk_manager=risk,
            order_manager=mock_order_manager,
            position_manager=mock_position_manager,
            instrument_id="MNQ",
        )

        with pytest.raises(RuntimeError, match="attach failed"):
            async with trade:
                await trade.enter_long(
                    size=2,
                    entry_price=18000.0,
                    stop_loss=17987.5,
                )

        flattened = (
            mock_position_manager.close_position_direct.called
            or mock_position_manager.close_position.called
            or mock_order_manager.place_market_order.call_count >= 2
        )
        has_stop = trade._stop_order is not None
        assert flattened or has_stop

    @pytest.mark.asyncio
    async def test_scale_out_resizes_protective_to_remainder(
        self, managed_trade: ManagedTrade, mock_order_manager: MagicMock
    ) -> None:
        managed_trade.risk.config.scale_out_enabled = True

        position = MagicMock(spec=Position)
        position.contractId = "MNQ"
        position.size = 4
        position.is_long = True
        managed_trade._positions = [position]

        stop = MagicMock(spec=Order)
        stop.id = 10
        stop.size = 4
        stop.is_working = True
        target = MagicMock(spec=Order)
        target.id = 11
        target.size = 4
        target.is_working = True
        managed_trade._stop_order = stop
        managed_trade._target_order = target

        mock_order_manager.search_open_orders = AsyncMock(return_value=[])

        result = await managed_trade.scale_out(exit_size=1)

        remainder = 3
        assert result["remaining_size"] == remainder
        assert mock_order_manager.modify_order.call_count >= 1
        size_calls = [
            call
            for call in mock_order_manager.modify_order.call_args_list
            if call.kwargs.get("size") == remainder
            or (len(call.args) > 1 and call.args[1] == remainder)
        ]
        assert size_calls, "protective orders must be resized to remaining size"
        assert stop.size == remainder
        assert target.size == remainder

    @pytest.mark.asyncio
    async def test_scale_in_calls_validate_trade_and_refuses_invalid(
        self, mock_order_manager: MagicMock, mock_position_manager: MagicMock
    ) -> None:
        risk = MagicMock()
        risk.config = RiskConfig(scale_in_enabled=True)
        risk.validate_trade = AsyncMock(
            return_value={
                "is_valid": False,
                "reasons": ["Daily trade limit reached (10)"],
                "warnings": [],
            }
        )

        position = MagicMock(spec=Position)
        position.contractId = "MNQ"
        position.size = 2
        position.is_long = True

        trade = ManagedTrade(
            risk_manager=risk,
            order_manager=mock_order_manager,
            position_manager=mock_position_manager,
            instrument_id="MNQ",
        )
        trade._positions = [position]

        mock_order_manager.place_market_order.reset_mock()

        with pytest.raises(ValueError, match="validation failed"):
            await trade.scale_in(additional_size=1)

        risk.validate_trade.assert_awaited()
        mock_order_manager.place_market_order.assert_not_called()
