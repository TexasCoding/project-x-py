"""
Comprehensive tests for order_templates module.

Tests all template classes, edge cases, and error conditions.
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import polars as pl
import pytest

from project_x_py.models import BracketOrderResponse, Instrument
from project_x_py.order_templates import (
    TEMPLATES,
    ATRStopTemplate,
    BreakoutTemplate,
    OrderTemplate,
    RiskRewardTemplate,
    ScalpingTemplate,
    get_template,
)


class TestOrderTemplate:
    """Test the abstract base class."""

    def test_cannot_instantiate_directly(self):
        """Test that OrderTemplate cannot be instantiated."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            OrderTemplate()  # type: ignore

    def test_requires_create_order_implementation(self):
        """Test that subclasses must implement create_order."""

        class IncompleteTemplate(OrderTemplate):
            pass

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteTemplate()  # type: ignore


class TestRiskRewardTemplate:
    """Test RiskRewardTemplate class."""

    def test_initialization_defaults(self):
        """Test default initialization."""
        template = RiskRewardTemplate()
        assert template.risk_reward_ratio == 2.0
        assert template.stop_distance is None
        assert template.use_limit_entry is True

    def test_initialization_custom(self):
        """Test custom initialization."""
        template = RiskRewardTemplate(
            risk_reward_ratio=3.0, stop_distance=10.0, use_limit_entry=False
        )
        assert template.risk_reward_ratio == 3.0
        assert template.stop_distance == 10.0
        assert template.use_limit_entry is False

    @pytest.mark.asyncio
    async def test_create_order_with_size(self):
        """Test creating order with explicit size."""
        template = RiskRewardTemplate(risk_reward_ratio=2.0, stop_distance=5.0)

        # Mock TradingSuite and its components
        suite = MagicMock()
        suite.data = AsyncMock()
        suite.data.get_current_price = AsyncMock(return_value=100.0)

        # Mock OrderChainBuilder
        mock_builder = MagicMock()
        mock_builder.limit_order = MagicMock(return_value=mock_builder)
        mock_builder.with_stop_loss = MagicMock(return_value=mock_builder)
        mock_builder.with_take_profit = MagicMock(return_value=mock_builder)
        mock_builder.execute = AsyncMock(
            return_value=BracketOrderResponse(
                success=True,
                entry_order_id=123,
                stop_order_id=124,
                target_order_id=125,
                entry_price=100.0,
                stop_loss_price=95.0,
                take_profit_price=110.0,
                entry_response=None,
                stop_response=None,
                target_response=None,
                error_message=None,
            )
        )

        with patch("project_x_py.order_templates.OrderChainBuilder", return_value=mock_builder):
            result = await template.create_order(suite, side=0, size=10)

        assert result.success is True
        assert result.entry_order_id == 123
        mock_builder.limit_order.assert_called_once_with(size=10, price=100.0, side=0)
        mock_builder.with_stop_loss.assert_called_once_with(offset=5.0)
        mock_builder.with_take_profit.assert_called_once_with(offset=10.0)  # 5.0 * 2.0

    @pytest.mark.asyncio
    async def test_create_order_with_risk_amount(self):
        """Test creating order with risk amount."""
        template = RiskRewardTemplate(risk_reward_ratio=2.0, stop_distance=5.0)

        # Mock TradingSuite and its components
        suite = MagicMock()
        suite.data = AsyncMock()
        suite.data.get_current_price = AsyncMock(return_value=100.0)

        # Mock instrument
        instrument = MagicMock(spec=Instrument)
        instrument.tickValue = 1.0
        suite.instrument = instrument

        # Mock OrderChainBuilder
        mock_builder = MagicMock()
        mock_builder.limit_order = MagicMock(return_value=mock_builder)
        mock_builder.with_stop_loss = MagicMock(return_value=mock_builder)
        mock_builder.with_take_profit = MagicMock(return_value=mock_builder)
        mock_builder.execute = AsyncMock(
            return_value=BracketOrderResponse(
                success=True,
                entry_order_id=124,
                stop_order_id=125,
                target_order_id=126,
                entry_price=100.0,
                stop_loss_price=95.0,
                take_profit_price=110.0,
                entry_response=None,
                stop_response=None,
                target_response=None,
                error_message=None,
            )
        )

        with patch("project_x_py.order_templates.OrderChainBuilder", return_value=mock_builder):
            result = await template.create_order(suite, side=0, risk_amount=50.0)

        assert result.success is True
        # Size should be calculated as risk_amount / (stop_distance * tick_value)
        # 50 / (5 * 1) = 10
        mock_builder.limit_order.assert_called_once_with(size=10, price=100.0, side=0)

    @pytest.mark.asyncio
    async def test_create_order_with_risk_percent(self):
        """Test creating order with risk percentage."""
        template = RiskRewardTemplate(risk_reward_ratio=2.0, stop_distance=5.0)

        # Mock TradingSuite and its components
        suite = MagicMock()
        suite.data = AsyncMock()
        suite.data.get_current_price = AsyncMock(return_value=100.0)

        # Mock instrument
        instrument = MagicMock(spec=Instrument)
        instrument.tickValue = 1.0
        suite.instrument = instrument

        # Mock account info
        account = MagicMock()
        account.balance = Decimal("10000.00")
        suite.client = MagicMock()
        suite.client.account_info = account

        # Mock OrderChainBuilder
        mock_builder = MagicMock()
        mock_builder.limit_order = MagicMock(return_value=mock_builder)
        mock_builder.with_stop_loss = MagicMock(return_value=mock_builder)
        mock_builder.with_take_profit = MagicMock(return_value=mock_builder)
        mock_builder.execute = AsyncMock(
            return_value=BracketOrderResponse(
                success=True,
                entry_order_id=125,
                stop_order_id=126,
                target_order_id=127,
                entry_price=100.0,
                stop_loss_price=95.0,
                take_profit_price=110.0,
                entry_response=None,
                stop_response=None,
                target_response=None,
                error_message=None,
            )
        )

        with patch("project_x_py.order_templates.OrderChainBuilder", return_value=mock_builder):
            result = await template.create_order(suite, side=0, risk_percent=0.01)  # 1% risk

        assert result.success is True
        # Size = (balance * risk_percent) / (stop_distance * tick_value)
        # (10000 * 0.01) / (5 * 1) = 100 / 5 = 20
        mock_builder.limit_order.assert_called_once_with(size=20, price=100.0, side=0)

    @pytest.mark.asyncio
    async def test_create_order_market_entry(self):
        """Test creating order with market entry."""
        template = RiskRewardTemplate(use_limit_entry=False)

        suite = MagicMock()
        suite.data = AsyncMock()
        suite.data.get_current_price = AsyncMock(return_value=100.0)

        mock_builder = MagicMock()
        mock_builder.market_order = MagicMock(return_value=mock_builder)
        mock_builder.with_stop_loss = MagicMock(return_value=mock_builder)
        mock_builder.with_take_profit = MagicMock(return_value=mock_builder)
        mock_builder.execute = AsyncMock(
            return_value=BracketOrderResponse(
                success=True,
                entry_order_id=126,
                stop_order_id=126,
                target_order_id=126,
                entry_price=100.0,
                stop_loss_price=99.0,
                take_profit_price=102.0,
                entry_response=None,
                stop_response=None,
                target_response=None,
                error_message=None,
            )
        )

        with patch("project_x_py.order_templates.OrderChainBuilder", return_value=mock_builder):
            result = await template.create_order(suite, side=1, size=5)

        assert result.success is True
        mock_builder.market_order.assert_called_once_with(size=5, side=1)

    @pytest.mark.asyncio
    async def test_create_order_with_entry_offset(self):
        """Test creating order with entry offset."""
        template = RiskRewardTemplate()

        suite = MagicMock()
        suite.data = AsyncMock()
        suite.data.get_current_price = AsyncMock(return_value=100.0)

        mock_builder = MagicMock()
        mock_builder.limit_order = MagicMock(return_value=mock_builder)
        mock_builder.with_stop_loss = MagicMock(return_value=mock_builder)
        mock_builder.with_take_profit = MagicMock(return_value=mock_builder)
        mock_builder.execute = AsyncMock(
            return_value=BracketOrderResponse(
                success=True,
                entry_order_id=127,
                stop_order_id=127,
                target_order_id=127,
                entry_price=100.0,
                stop_loss_price=99.0,
                take_profit_price=102.0,
                entry_response=None,
                stop_response=None,
                target_response=None,
                error_message=None,
            )
        )

        with patch("project_x_py.order_templates.OrderChainBuilder", return_value=mock_builder):
            # BUY with offset - should subtract from price
            await template.create_order(suite, side=0, size=10, entry_offset=2.0)
            mock_builder.limit_order.assert_called_with(size=10, price=98.0, side=0)

            # SELL with offset - should add to price
            await template.create_order(suite, side=1, size=10, entry_offset=2.0)
            mock_builder.limit_order.assert_called_with(size=10, price=102.0, side=1)

    @pytest.mark.asyncio
    async def test_create_order_no_current_price(self):
        """Test error when current price unavailable."""
        template = RiskRewardTemplate()

        suite = MagicMock()
        suite.data = AsyncMock()
        suite.data.get_current_price = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="Cannot get current price"):
            await template.create_order(suite, side=0, size=10)

    @pytest.mark.asyncio
    async def test_create_order_no_size_params(self):
        """Test error when no size parameters provided."""
        template = RiskRewardTemplate()

        suite = MagicMock()
        suite.data = AsyncMock()
        suite.data.get_current_price = AsyncMock(return_value=100.0)

        with pytest.raises(ValueError, match="Must provide size, risk_amount, or risk_percent"):
            await template.create_order(suite, side=0)

    @pytest.mark.asyncio
    async def test_create_order_no_account_info(self):
        """Test error when account info unavailable for risk_percent."""
        template = RiskRewardTemplate()

        suite = MagicMock()
        suite.data = AsyncMock()
        suite.data.get_current_price = AsyncMock(return_value=100.0)
        suite.client = MagicMock()
        suite.client.account_info = None

        with pytest.raises(ValueError, match="No account information available"):
            await template.create_order(suite, side=0, risk_percent=0.01)

    @pytest.mark.asyncio
    async def test_create_order_default_stop_distance(self):
        """Test using default stop distance when not specified."""
        template = RiskRewardTemplate(stop_distance=None)

        suite = MagicMock()
        suite.data = AsyncMock()
        suite.data.get_current_price = AsyncMock(return_value=100.0)

        mock_builder = MagicMock()
        mock_builder.limit_order = MagicMock(return_value=mock_builder)
        mock_builder.with_stop_loss = MagicMock(return_value=mock_builder)
        mock_builder.with_take_profit = MagicMock(return_value=mock_builder)
        mock_builder.execute = AsyncMock(
            return_value=BracketOrderResponse(
                success=True,
                entry_order_id=128,
                stop_order_id=128,
                target_order_id=128,
                entry_price=100.0,
                stop_loss_price=99.0,
                take_profit_price=102.0,
                entry_response=None,
                stop_response=None,
                target_response=None,
                error_message=None,
            )
        )

        with patch("project_x_py.order_templates.OrderChainBuilder", return_value=mock_builder):
            await template.create_order(suite, side=0, size=10)

        # Default stop distance should be 1% of price = 1.0
        mock_builder.with_stop_loss.assert_called_once_with(offset=1.0)
        mock_builder.with_take_profit.assert_called_once_with(offset=2.0)  # 1.0 * 2.0


class TestATRStopTemplate:
    """Test ATRStopTemplate class."""

    def test_initialization_defaults(self):
        """Test default initialization."""
        template = ATRStopTemplate()
        assert template.atr_multiplier == 2.0
        assert template.atr_period == 14
        assert template.target_multiplier == 3.0
        assert template.timeframe == "5min"

    def test_initialization_custom(self):
        """Test custom initialization."""
        template = ATRStopTemplate(
            atr_multiplier=1.5, atr_period=20, target_multiplier=2.5, timeframe="1min"
        )
        assert template.atr_multiplier == 1.5
        assert template.atr_period == 20
        assert template.target_multiplier == 2.5
        assert template.timeframe == "1min"

    @pytest.mark.asyncio
    async def test_create_order_success(self):
        """Test successful order creation with ATR stops."""
        template = ATRStopTemplate(atr_multiplier=2.0, atr_period=14)

        # Create mock data with ATR
        data = pl.DataFrame(
            {
                "high": [105.0] * 20,
                "low": [95.0] * 20,
                "close": [100.0] * 20,
                "atr_14": [2.5] * 20,
            }
        )

        suite = MagicMock()
        suite.data = AsyncMock()
        suite.data.get_data = AsyncMock(return_value=data)
        suite.data.get_current_price = AsyncMock(return_value=100.0)

        mock_builder = MagicMock()
        mock_builder.market_order = MagicMock(return_value=mock_builder)
        mock_builder.with_stop_loss = MagicMock(return_value=mock_builder)
        mock_builder.with_take_profit = MagicMock(return_value=mock_builder)
        mock_builder.execute = AsyncMock(
            return_value=BracketOrderResponse(
                success=True,
                entry_order_id=200,
                stop_order_id=200,
                target_order_id=200,
                entry_price=100.0,
                stop_loss_price=99.0,
                take_profit_price=102.0,
                entry_response=None,
                stop_response=None,
                target_response=None,
                error_message=None,
            )
        )

        with patch("project_x_py.order_templates.OrderChainBuilder", return_value=mock_builder):
            with patch("project_x_py.order_templates.ATR", return_value=data):
                result = await template.create_order(suite, side=0, size=10)

        assert result.success is True
        # Stop distance = ATR * multiplier = 2.5 * 2.0 = 5.0
        # Target distance = stop * target_multiplier = 5.0 * 3.0 = 15.0
        mock_builder.with_stop_loss.assert_called_once_with(offset=5.0)
        mock_builder.with_take_profit.assert_called_once_with(offset=15.0)

    @pytest.mark.asyncio
    async def test_create_order_insufficient_data(self):
        """Test error with insufficient data for ATR calculation."""
        template = ATRStopTemplate()

        suite = MagicMock()
        suite.data = AsyncMock()
        suite.data.get_data = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="Insufficient data for ATR calculation"):
            await template.create_order(suite, side=0, size=10)

    @pytest.mark.asyncio
    async def test_create_order_with_limit_entry(self):
        """Test order creation with limit entry."""
        template = ATRStopTemplate()

        data = pl.DataFrame(
            {
                "high": [105.0] * 20,
                "low": [95.0] * 20,
                "close": [100.0] * 20,
                "atr_14": [2.5] * 20,
            }
        )

        suite = MagicMock()
        suite.data = AsyncMock()
        suite.data.get_data = AsyncMock(return_value=data)
        suite.data.get_current_price = AsyncMock(return_value=100.0)

        mock_builder = MagicMock()
        mock_builder.limit_order = MagicMock(return_value=mock_builder)
        mock_builder.with_stop_loss = MagicMock(return_value=mock_builder)
        mock_builder.with_take_profit = MagicMock(return_value=mock_builder)
        mock_builder.execute = AsyncMock(
            return_value=BracketOrderResponse(
                success=True,
                entry_order_id=201,
                stop_order_id=201,
                target_order_id=201,
                entry_price=100.0,
                stop_loss_price=99.0,
                take_profit_price=102.0,
                entry_response=None,
                stop_response=None,
                target_response=None,
                error_message=None,
            )
        )

        with patch("project_x_py.order_templates.OrderChainBuilder", return_value=mock_builder):
            with patch("project_x_py.order_templates.ATR", return_value=data):
                # BUY with limit and offset
                await template.create_order(suite, side=0, size=10, use_limit_entry=True, entry_offset=1.0)
                mock_builder.limit_order.assert_called_with(size=10, price=99.0, side=0)

                # SELL with limit and offset
                await template.create_order(suite, side=1, size=10, use_limit_entry=True, entry_offset=1.0)
                mock_builder.limit_order.assert_called_with(size=10, price=101.0, side=1)

    @pytest.mark.asyncio
    async def test_create_order_no_size(self):
        """Test error when size not provided."""
        template = ATRStopTemplate()

        data = pl.DataFrame({"atr_14": [2.5] * 20})
        suite = MagicMock()
        suite.data = AsyncMock()
        suite.data.get_data = AsyncMock(return_value=data)
        suite.data.get_current_price = AsyncMock(return_value=100.0)

        with patch("project_x_py.order_templates.ATR", return_value=data):
            with pytest.raises(ValueError, match="Size is required"):
                await template.create_order(suite, side=0)


class TestBreakoutTemplate:
    """Test BreakoutTemplate class."""

    def test_initialization_defaults(self):
        """Test default initialization."""
        template = BreakoutTemplate()
        assert template.breakout_offset == 2.0
        assert template.stop_at_level is True
        assert template.target_range_multiplier == 1.5

    def test_initialization_custom(self):
        """Test custom initialization."""
        template = BreakoutTemplate(
            breakout_offset=3.0, stop_at_level=False, target_range_multiplier=2.0
        )
        assert template.breakout_offset == 3.0
        assert template.stop_at_level is False
        assert template.target_range_multiplier == 2.0

    @pytest.mark.asyncio
    async def test_create_order_with_level(self):
        """Test creating order with specified breakout level."""
        template = BreakoutTemplate()

        suite = MagicMock()

        mock_builder = MagicMock()
        mock_builder.stop_order = MagicMock(return_value=mock_builder)
        mock_builder.with_stop_loss = MagicMock(return_value=mock_builder)
        mock_builder.with_take_profit = MagicMock(return_value=mock_builder)
        mock_builder.execute = AsyncMock(
            return_value=BracketOrderResponse(
                success=True,
                entry_order_id=300,
                stop_order_id=300,
                target_order_id=300,
                entry_price=100.0,
                stop_loss_price=99.0,
                take_profit_price=102.0,
                entry_response=None,
                stop_response=None,
                target_response=None,
                error_message=None,
            )
        )

        with patch("project_x_py.order_templates.OrderChainBuilder", return_value=mock_builder):
            # BUY breakout
            result = await template.create_order(
                suite, side=0, size=10, breakout_level=100.0, range_size=5.0
            )

        assert result.success is True
        # Entry = breakout_level + offset = 100 + 2 = 102
        # Stop = breakout_level (stop_at_level=True) = 100
        # Target = entry + (range * multiplier) = 102 + (5 * 1.5) = 109.5
        mock_builder.stop_order.assert_called_once_with(size=10, price=102.0, side=0)
        mock_builder.with_stop_loss.assert_called_once_with(price=100.0)
        mock_builder.with_take_profit.assert_called_once_with(price=109.5)

    @pytest.mark.asyncio
    async def test_create_order_sell_breakout(self):
        """Test creating sell breakout order."""
        template = BreakoutTemplate()

        suite = MagicMock()

        mock_builder = MagicMock()
        mock_builder.stop_order = MagicMock(return_value=mock_builder)
        mock_builder.with_stop_loss = MagicMock(return_value=mock_builder)
        mock_builder.with_take_profit = MagicMock(return_value=mock_builder)
        mock_builder.execute = AsyncMock(
            return_value=BracketOrderResponse(
                success=True,
                entry_order_id=301,
                stop_order_id=301,
                target_order_id=301,
                entry_price=100.0,
                stop_loss_price=99.0,
                take_profit_price=102.0,
                entry_response=None,
                stop_response=None,
                target_response=None,
                error_message=None,
            )
        )

        with patch("project_x_py.order_templates.OrderChainBuilder", return_value=mock_builder):
            # SELL breakout
            await template.create_order(
                suite, side=1, size=10, breakout_level=100.0, range_size=5.0
            )

        # Entry = breakout_level - offset = 100 - 2 = 98
        # Stop = breakout_level (stop_at_level=True) = 100
        # Target = entry - (range * multiplier) = 98 - (5 * 1.5) = 90.5
        mock_builder.stop_order.assert_called_once_with(size=10, price=98.0, side=1)
        mock_builder.with_stop_loss.assert_called_once_with(price=100.0)
        mock_builder.with_take_profit.assert_called_once_with(price=90.5)

    @pytest.mark.asyncio
    async def test_create_order_stop_not_at_level(self):
        """Test creating order with stop not at breakout level."""
        template = BreakoutTemplate(stop_at_level=False)

        suite = MagicMock()

        mock_builder = MagicMock()
        mock_builder.stop_order = MagicMock(return_value=mock_builder)
        mock_builder.with_stop_loss = MagicMock(return_value=mock_builder)
        mock_builder.with_take_profit = MagicMock(return_value=mock_builder)
        mock_builder.execute = AsyncMock(
            return_value=BracketOrderResponse(
                success=True,
                entry_order_id=302,
                stop_order_id=302,
                target_order_id=302,
                entry_price=100.0,
                stop_loss_price=99.0,
                take_profit_price=102.0,
                entry_response=None,
                stop_response=None,
                target_response=None,
                error_message=None,
            )
        )

        with patch("project_x_py.order_templates.OrderChainBuilder", return_value=mock_builder):
            # BUY breakout with stop below level
            await template.create_order(
                suite, side=0, size=10, breakout_level=100.0, range_size=5.0
            )

        # Stop = breakout_level - range_size = 100 - 5 = 95
        mock_builder.with_stop_loss.assert_called_once_with(price=95.0)

    @pytest.mark.asyncio
    async def test_create_order_auto_detect_level(self):
        """Test auto-detecting breakout level."""
        template = BreakoutTemplate()

        suite = MagicMock()
        suite.data = AsyncMock()
        suite.data.get_price_range = AsyncMock(
            return_value={"high": 105.0, "low": 95.0, "range": 10.0}
        )

        mock_builder = MagicMock()
        mock_builder.stop_order = MagicMock(return_value=mock_builder)
        mock_builder.with_stop_loss = MagicMock(return_value=mock_builder)
        mock_builder.with_take_profit = MagicMock(return_value=mock_builder)
        mock_builder.execute = AsyncMock(
            return_value=BracketOrderResponse(
                success=True,
                entry_order_id=303,
                stop_order_id=303,
                target_order_id=303,
                entry_price=100.0,
                stop_loss_price=99.0,
                take_profit_price=102.0,
                entry_response=None,
                stop_response=None,
                target_response=None,
                error_message=None,
            )
        )

        with patch("project_x_py.order_templates.OrderChainBuilder", return_value=mock_builder):
            # BUY should use high as breakout level
            await template.create_order(suite, side=0, size=10)

        suite.data.get_price_range.assert_called_once_with(bars=20, timeframe="5min")
        # Entry = high + offset = 105 + 2 = 107
        mock_builder.stop_order.assert_called_once_with(size=10, price=107.0, side=0)

    @pytest.mark.asyncio
    async def test_create_order_no_range_stats(self):
        """Test error when range stats unavailable."""
        template = BreakoutTemplate()

        suite = MagicMock()
        suite.data = AsyncMock()
        suite.data.get_price_range = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="Cannot calculate price range"):
            await template.create_order(suite, side=0, size=10)

    @pytest.mark.asyncio
    async def test_create_order_no_size(self):
        """Test error when size not provided."""
        template = BreakoutTemplate()
        suite = MagicMock()

        with pytest.raises(ValueError, match="Size is required"):
            await template.create_order(suite, side=0, breakout_level=100.0, range_size=5.0)

    @pytest.mark.asyncio
    async def test_create_order_no_range_size(self):
        """Test error when range size not provided and not auto-detected."""
        template = BreakoutTemplate()
        suite = MagicMock()

        with pytest.raises(ValueError, match="Range size is required"):
            await template.create_order(suite, side=0, size=10, breakout_level=100.0)


class TestScalpingTemplate:
    """Test ScalpingTemplate class."""

    def test_initialization_defaults(self):
        """Test default initialization."""
        template = ScalpingTemplate()
        assert template.stop_ticks == 4
        assert template.target_ticks == 8
        assert template.use_market_entry is True
        assert template.max_spread_ticks == 2

    def test_initialization_custom(self):
        """Test custom initialization."""
        template = ScalpingTemplate(
            stop_ticks=3, target_ticks=9, use_market_entry=False, max_spread_ticks=1
        )
        assert template.stop_ticks == 3
        assert template.target_ticks == 9
        assert template.use_market_entry is False
        assert template.max_spread_ticks == 1

    @pytest.mark.asyncio
    async def test_create_order_market_entry(self):
        """Test creating scalping order with market entry."""
        template = ScalpingTemplate()

        instrument = MagicMock(spec=Instrument)
        instrument.tickSize = 0.25

        suite = MagicMock()
        suite.instrument = instrument

        mock_builder = MagicMock()
        mock_builder.market_order = MagicMock(return_value=mock_builder)
        mock_builder.with_stop_loss = MagicMock(return_value=mock_builder)
        mock_builder.with_take_profit = MagicMock(return_value=mock_builder)
        mock_builder.execute = AsyncMock(
            return_value=BracketOrderResponse(
                success=True,
                entry_order_id=400,
                stop_order_id=400,
                target_order_id=400,
                entry_price=100.0,
                stop_loss_price=99.0,
                take_profit_price=102.0,
                entry_response=None,
                stop_response=None,
                target_response=None,
                error_message=None,
            )
        )

        with patch("project_x_py.order_templates.OrderChainBuilder", return_value=mock_builder):
            result = await template.create_order(suite, side=0, size=10, check_spread=False)

        assert result.success is True
        mock_builder.market_order.assert_called_once_with(size=10, side=0)
        # Stop = 4 ticks * 0.25 = 1.0
        # Target = 8 ticks * 0.25 = 2.0
        mock_builder.with_stop_loss.assert_called_once_with(offset=1.0)
        mock_builder.with_take_profit.assert_called_once_with(offset=2.0)

    @pytest.mark.asyncio
    async def test_create_order_limit_entry(self):
        """Test creating scalping order with limit entry."""
        template = ScalpingTemplate(use_market_entry=False)

        instrument = MagicMock(spec=Instrument)
        instrument.tickSize = 0.25

        suite = MagicMock()
        suite.instrument = instrument
        suite.data = AsyncMock()
        suite.data.get_current_price = AsyncMock(return_value=100.0)

        mock_builder = MagicMock()
        mock_builder.limit_order = MagicMock(return_value=mock_builder)
        mock_builder.with_stop_loss = MagicMock(return_value=mock_builder)
        mock_builder.with_take_profit = MagicMock(return_value=mock_builder)
        mock_builder.execute = AsyncMock(
            return_value=BracketOrderResponse(
                success=True,
                entry_order_id=401,
                stop_order_id=401,
                target_order_id=401,
                entry_price=100.0,
                stop_loss_price=99.0,
                take_profit_price=102.0,
                entry_response=None,
                stop_response=None,
                target_response=None,
                error_message=None,
            )
        )

        with patch("project_x_py.order_templates.OrderChainBuilder", return_value=mock_builder):
            await template.create_order(suite, side=0, size=10, check_spread=False)

        mock_builder.limit_order.assert_called_once_with(size=10, price=100.0, side=0)

    @pytest.mark.asyncio
    async def test_create_order_check_spread_pass(self):
        """Test spread check passes."""
        template = ScalpingTemplate(max_spread_ticks=3)

        instrument = MagicMock(spec=Instrument)
        instrument.tickSize = 0.25

        orderbook = AsyncMock()
        orderbook.get_bid_ask_spread = AsyncMock(return_value=0.5)  # 2 ticks

        suite = MagicMock()
        suite.instrument = instrument
        suite.orderbook = orderbook

        mock_builder = MagicMock()
        mock_builder.market_order = MagicMock(return_value=mock_builder)
        mock_builder.with_stop_loss = MagicMock(return_value=mock_builder)
        mock_builder.with_take_profit = MagicMock(return_value=mock_builder)
        mock_builder.execute = AsyncMock(
            return_value=BracketOrderResponse(
                success=True,
                entry_order_id=402,
                stop_order_id=402,
                target_order_id=402,
                entry_price=100.0,
                stop_loss_price=99.0,
                take_profit_price=102.0,
                entry_response=None,
                stop_response=None,
                target_response=None,
                error_message=None,
            )
        )

        with patch("project_x_py.order_templates.OrderChainBuilder", return_value=mock_builder):
            result = await template.create_order(suite, side=0, size=10, check_spread=True)

        assert result.success is True
        orderbook.get_bid_ask_spread.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_order_check_spread_fail(self):
        """Test spread check fails."""
        template = ScalpingTemplate(max_spread_ticks=2)

        instrument = MagicMock(spec=Instrument)
        instrument.tickSize = 0.25

        orderbook = AsyncMock()
        orderbook.get_bid_ask_spread = AsyncMock(return_value=1.0)  # 4 ticks

        suite = MagicMock()
        suite.instrument = instrument
        suite.orderbook = orderbook

        with pytest.raises(ValueError, match="Spread too wide: 4.0 ticks"):
            await template.create_order(suite, side=0, size=10, check_spread=True)

    @pytest.mark.asyncio
    async def test_create_order_no_instrument(self):
        """Test error when instrument unavailable."""
        template = ScalpingTemplate()

        suite = MagicMock()
        suite.instrument = None

        with pytest.raises(ValueError, match="Cannot get instrument details"):
            await template.create_order(suite, side=0, size=10)

    @pytest.mark.asyncio
    async def test_create_order_no_size(self):
        """Test error when size not provided."""
        template = ScalpingTemplate()

        instrument = MagicMock(spec=Instrument)
        instrument.tickSize = 0.25

        suite = MagicMock()
        suite.instrument = instrument
        suite.orderbook = None  # No orderbook, so spread check won't run

        with pytest.raises(ValueError, match="Size is required"):
            await template.create_order(suite, side=0)

    @pytest.mark.asyncio
    async def test_create_order_no_current_price_for_limit(self):
        """Test error when current price unavailable for limit entry."""
        template = ScalpingTemplate(use_market_entry=False)

        instrument = MagicMock(spec=Instrument)
        instrument.tickSize = 0.25

        suite = MagicMock()
        suite.instrument = instrument
        suite.orderbook = None  # No orderbook, so spread check won't run
        suite.data = AsyncMock()
        suite.data.get_current_price = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="Cannot get current price"):
            await template.create_order(suite, side=0, size=10, check_spread=False)


class TestGetTemplate:
    """Test get_template function."""

    def test_get_template_conservative_rr(self):
        """Test getting conservative risk/reward template."""
        template = get_template("conservative_rr")
        assert isinstance(template, RiskRewardTemplate)
        assert template.risk_reward_ratio == 1.5
        assert template.use_limit_entry is True

    def test_get_template_conservative_atr(self):
        """Test getting conservative ATR template."""
        template = get_template("conservative_atr")
        assert isinstance(template, ATRStopTemplate)
        assert template.atr_multiplier == 1.5
        assert template.target_multiplier == 2.0

    def test_get_template_standard_rr(self):
        """Test getting standard risk/reward template."""
        template = get_template("standard_rr")
        assert isinstance(template, RiskRewardTemplate)
        assert template.risk_reward_ratio == 2.0

    def test_get_template_standard_atr(self):
        """Test getting standard ATR template."""
        template = get_template("standard_atr")
        assert isinstance(template, ATRStopTemplate)
        assert template.atr_multiplier == 2.0
        assert template.target_multiplier == 3.0

    def test_get_template_standard_breakout(self):
        """Test getting standard breakout template."""
        template = get_template("standard_breakout")
        assert isinstance(template, BreakoutTemplate)

    def test_get_template_aggressive_rr(self):
        """Test getting aggressive risk/reward template."""
        template = get_template("aggressive_rr")
        assert isinstance(template, RiskRewardTemplate)
        assert template.risk_reward_ratio == 3.0
        assert template.use_limit_entry is False

    def test_get_template_aggressive_atr(self):
        """Test getting aggressive ATR template."""
        template = get_template("aggressive_atr")
        assert isinstance(template, ATRStopTemplate)
        assert template.atr_multiplier == 2.5
        assert template.target_multiplier == 4.0

    def test_get_template_aggressive_scalp(self):
        """Test getting aggressive scalping template."""
        template = get_template("aggressive_scalp")
        assert isinstance(template, ScalpingTemplate)
        assert template.stop_ticks == 3
        assert template.target_ticks == 9

    def test_get_template_tight_scalp(self):
        """Test getting tight scalping template."""
        template = get_template("tight_scalp")
        assert isinstance(template, ScalpingTemplate)
        assert template.stop_ticks == 2
        assert template.target_ticks == 4

    def test_get_template_normal_scalp(self):
        """Test getting normal scalping template."""
        template = get_template("normal_scalp")
        assert isinstance(template, ScalpingTemplate)
        assert template.stop_ticks == 4
        assert template.target_ticks == 8

    def test_get_template_wide_scalp(self):
        """Test getting wide scalping template."""
        template = get_template("wide_scalp")
        assert isinstance(template, ScalpingTemplate)
        assert template.stop_ticks == 6
        assert template.target_ticks == 12

    def test_get_template_invalid_name(self):
        """Test error with invalid template name."""
        with pytest.raises(ValueError, match="Unknown template: invalid"):
            get_template("invalid")

    def test_get_template_error_message(self):
        """Test error message lists available templates."""
        with pytest.raises(ValueError) as exc_info:
            get_template("bad_template")

        error_msg = str(exc_info.value)
        assert "Unknown template: bad_template" in error_msg
        assert "conservative_rr" in error_msg
        assert "standard_atr" in error_msg
        assert "aggressive_scalp" in error_msg


class TestTemplatesDict:
    """Test TEMPLATES dictionary."""

    def test_templates_dict_complete(self):
        """Test that TEMPLATES dict contains all expected templates."""
        expected_templates = [
            "conservative_rr",
            "conservative_atr",
            "standard_rr",
            "standard_atr",
            "standard_breakout",
            "aggressive_rr",
            "aggressive_atr",
            "aggressive_scalp",
            "tight_scalp",
            "normal_scalp",
            "wide_scalp",
        ]

        for name in expected_templates:
            assert name in TEMPLATES
            assert isinstance(TEMPLATES[name], OrderTemplate)

    def test_templates_dict_types(self):
        """Test that all templates are correct types."""
        type_mapping = {
            "conservative_rr": RiskRewardTemplate,
            "conservative_atr": ATRStopTemplate,
            "standard_rr": RiskRewardTemplate,
            "standard_atr": ATRStopTemplate,
            "standard_breakout": BreakoutTemplate,
            "aggressive_rr": RiskRewardTemplate,
            "aggressive_atr": ATRStopTemplate,
            "aggressive_scalp": ScalpingTemplate,
            "tight_scalp": ScalpingTemplate,
            "normal_scalp": ScalpingTemplate,
            "wide_scalp": ScalpingTemplate,
        }

        for name, expected_type in type_mapping.items():
            assert isinstance(TEMPLATES[name], expected_type)


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_zero_price_handling(self):
        """Test handling of very small prices."""
        template = RiskRewardTemplate()

        suite = MagicMock()
        suite.data = AsyncMock()
        suite.data.get_current_price = AsyncMock(return_value=0.01)  # Very small price

        # Even with zero price, should use it (might be valid for some instruments)
        mock_builder = MagicMock()
        mock_builder.limit_order = MagicMock(return_value=mock_builder)
        mock_builder.with_stop_loss = MagicMock(return_value=mock_builder)
        mock_builder.with_take_profit = MagicMock(return_value=mock_builder)
        mock_builder.execute = AsyncMock(
            return_value=BracketOrderResponse(
                success=True,
                entry_order_id=500,
                stop_order_id=500,
                target_order_id=500,
                entry_price=100.0,
                stop_loss_price=99.0,
                take_profit_price=102.0,
                entry_response=None,
                stop_response=None,
                target_response=None,
                error_message=None,
            )
        )

        with patch("project_x_py.order_templates.OrderChainBuilder", return_value=mock_builder):
            await template.create_order(suite, side=0, size=10)

        # Default stop distance with very small price should be 1% = 0.0001
        mock_builder.with_stop_loss.assert_called_once_with(offset=0.0001)

    @pytest.mark.asyncio
    async def test_negative_values(self):
        """Test handling of negative values."""
        # Negative risk/reward ratio should work
        template = RiskRewardTemplate(risk_reward_ratio=-1.0, stop_distance=5.0)
        assert template.risk_reward_ratio == -1.0

        # Negative ATR multiplier should work
        atr_template = ATRStopTemplate(atr_multiplier=-1.0)
        assert atr_template.atr_multiplier == -1.0

    @pytest.mark.asyncio
    async def test_very_large_values(self):
        """Test handling of very large values."""
        template = RiskRewardTemplate(risk_reward_ratio=1000.0, stop_distance=10000.0)
        assert template.risk_reward_ratio == 1000.0
        assert template.stop_distance == 10000.0

    @pytest.mark.asyncio
    async def test_execution_failure(self):
        """Test handling of order execution failure."""
        template = RiskRewardTemplate()

        suite = MagicMock()
        suite.data = AsyncMock()
        suite.data.get_current_price = AsyncMock(return_value=100.0)

        mock_builder = MagicMock()
        mock_builder.limit_order = MagicMock(return_value=mock_builder)
        mock_builder.with_stop_loss = MagicMock(return_value=mock_builder)
        mock_builder.with_take_profit = MagicMock(return_value=mock_builder)
        mock_builder.execute = AsyncMock(
            return_value=BracketOrderResponse(
                success=False,
                entry_order_id=None,
                stop_order_id=None,
                target_order_id=None,
                entry_price=100.0,
                stop_loss_price=99.0,
                take_profit_price=102.0,
                entry_response=None,
                stop_response=None,
                target_response=None,
                error_message="Order rejected"
            )
        )

        with patch("project_x_py.order_templates.OrderChainBuilder", return_value=mock_builder):
            result = await template.create_order(suite, side=0, size=10)

        assert result.success is False
        assert result.error_message == "Order rejected"

    @pytest.mark.asyncio
    async def test_missing_tick_value(self):
        """Test handling when instrument has no tick value."""
        template = RiskRewardTemplate()

        suite = MagicMock()
        suite.data = AsyncMock()
        suite.data.get_current_price = AsyncMock(return_value=100.0)

        # Instrument with None tickValue - this should cause an error
        # The code doesn't handle None tickValue properly
        instrument = MagicMock(spec=Instrument)
        instrument.tickValue = None
        suite.instrument = instrument

        # This should raise a TypeError when trying to multiply with None
        with pytest.raises(TypeError, match="unsupported operand type"):
            await template.create_order(suite, side=0, risk_amount=100.0)
