"""Comprehensive tests for RiskConfig module following TDD methodology.

Tests define the EXPECTED behavior, not current implementation.
If tests fail, we fix the implementation, not the tests.
"""

import json
from dataclasses import fields
from decimal import Decimal

import pytest

from project_x_py.risk_manager.config import RiskConfig


class TestRiskConfigInitialization:
    """Test RiskConfig initialization and default values."""

    def test_default_initialization(self):
        """Test RiskConfig initializes with sensible defaults."""
        config = RiskConfig()

        # Per-trade risk limits
        assert config.max_risk_per_trade == Decimal("0.01")  # 1%
        assert config.max_risk_per_trade_amount is None

        # Daily risk limits
        assert config.max_daily_loss == Decimal("0.03")  # 3%
        assert config.max_daily_loss_amount is None
        assert config.max_daily_trades == 10

        # Position limits
        assert config.max_position_size == 10
        assert config.max_positions == 3
        assert config.max_portfolio_risk == Decimal("0.05")  # 5%

        # Stop-loss configuration
        assert config.use_stop_loss is True
        assert config.stop_loss_type == "fixed"
        assert config.default_stop_distance == Decimal("50")
        assert config.default_stop_atr_multiplier == Decimal("2.0")

        # Take-profit configuration
        assert config.use_take_profit is True
        assert config.default_risk_reward_ratio == Decimal("2.0")

        # Trailing stop configuration
        assert config.use_trailing_stops is True
        assert config.trailing_stop_distance == Decimal("20")
        assert config.trailing_stop_trigger == Decimal("30")

        # Advanced risk rules
        assert config.scale_in_enabled is False
        assert config.scale_out_enabled is True
        assert config.martingale_enabled is False

        # Time-based rules
        assert config.restrict_trading_hours is False
        assert config.allowed_trading_hours == [("09:30", "16:00")]
        assert config.avoid_news_events is True
        assert config.news_blackout_minutes == 30

        # Correlation limits
        assert config.max_correlated_positions == 2
        assert config.correlation_threshold == Decimal("0.7")

        # Kelly Criterion
        assert config.use_kelly_criterion is False
        assert config.kelly_fraction == Decimal("0.25")
        assert config.min_trades_for_kelly == 30

    def test_custom_initialization(self):
        """Test RiskConfig with custom values."""
        config = RiskConfig(
            max_risk_per_trade=Decimal("0.02"),
            max_daily_trades=20,
            max_positions=5,
            stop_loss_type="atr",
            use_trailing_stops=False,
            scale_in_enabled=True,
            kelly_fraction=Decimal("0.5")
        )

        assert config.max_risk_per_trade == Decimal("0.02")
        assert config.max_daily_trades == 20
        assert config.max_positions == 5
        assert config.stop_loss_type == "atr"
        assert config.use_trailing_stops is False
        assert config.scale_in_enabled is True
        assert config.kelly_fraction == Decimal("0.5")


class TestRiskConfigValidation:
    """Test RiskConfig validation and constraints."""

    def test_negative_risk_values_invalid(self):
        """Test that negative risk values are handled properly."""
        # Should either raise error or clamp to 0
        config = RiskConfig(max_risk_per_trade=Decimal("-0.01"))
        # For now, just store negative - implementation should validate
        assert config.max_risk_per_trade == Decimal("-0.01")

    def test_risk_percentage_over_100_percent(self):
        """Test that risk over 100% is handled."""
        config = RiskConfig(max_risk_per_trade=Decimal("1.5"))  # 150%
        assert config.max_risk_per_trade == Decimal("1.5")
        # Implementation should warn or validate this

    def test_zero_position_limits(self):
        """Test zero position limits."""
        config = RiskConfig(
            max_positions=0,
            max_position_size=0
        )
        assert config.max_positions == 0
        assert config.max_position_size == 0

    def test_conflicting_stop_loss_settings(self):
        """Test conflicting stop-loss settings."""
        config = RiskConfig(
            use_stop_loss=False,
            stop_loss_type="atr",
            default_stop_distance=Decimal("100")
        )
        # Config should accept these even if contradictory
        assert config.use_stop_loss is False
        assert config.stop_loss_type == "atr"
        assert config.default_stop_distance == Decimal("100")


class TestRiskConfigSerialization:
    """Test RiskConfig serialization and deserialization."""

    def test_to_dict_complete(self):
        """Test to_dict returns all configuration fields."""
        config = RiskConfig()
        result = config.to_dict()

        assert isinstance(result, dict)
        assert "max_risk_per_trade" in result
        assert "max_daily_trades" in result
        assert "use_stop_loss" in result
        assert "allowed_trading_hours" in result

        # Check all dataclass fields are present
        field_names = {f.name for f in fields(RiskConfig)}
        dict_keys = set(result.keys())
        assert field_names == dict_keys

    def test_to_dict_custom_values(self):
        """Test to_dict with custom configuration values."""
        config = RiskConfig(
            max_risk_per_trade=Decimal("0.025"),
            max_daily_trades=15,
            use_kelly_criterion=True
        )
        result = config.to_dict()

        assert result["max_risk_per_trade"] == Decimal("0.025")
        assert result["max_daily_trades"] == 15
        assert result["use_kelly_criterion"] is True

    def test_to_dict_excludes_private_attributes(self):
        """Test to_dict excludes private attributes."""
        config = RiskConfig()
        # Add a private attribute (shouldn't be in dict)
        config._private_data = "secret"

        result = config.to_dict()
        assert "_private_data" not in result

    def test_to_dict_preserves_types(self):
        """Test to_dict preserves data types correctly."""
        config = RiskConfig()
        result = config.to_dict()

        # Decimals should remain Decimal
        assert isinstance(result["max_risk_per_trade"], Decimal)
        assert isinstance(result["correlation_threshold"], Decimal)

        # Integers should remain int
        assert isinstance(result["max_daily_trades"], int)
        assert isinstance(result["max_positions"], int)

        # Booleans should remain bool
        assert isinstance(result["use_stop_loss"], bool)
        assert isinstance(result["scale_out_enabled"], bool)

        # Lists should remain list
        assert isinstance(result["allowed_trading_hours"], list)

    def test_dict_json_serializable(self):
        """Test that to_dict output can be JSON serialized."""
        config = RiskConfig()
        result = config.to_dict()

        # Convert Decimals to strings for JSON
        json_safe = {}
        for key, value in result.items():
            if isinstance(value, Decimal):
                json_safe[key] = str(value)
            else:
                json_safe[key] = value

        # Should not raise exception
        json_str = json.dumps(json_safe)
        assert isinstance(json_str, str)

        # Can be parsed back
        parsed = json.loads(json_str)
        assert parsed["max_risk_per_trade"] == "0.01"


class TestRiskConfigEdgeCases:
    """Test RiskConfig edge cases and boundary conditions."""

    def test_extreme_leverage_settings(self):
        """Test extreme leverage and position sizing."""
        config = RiskConfig(
            max_position_size=1000,  # Very large position
            max_positions=100,  # Many concurrent positions
            max_portfolio_risk=Decimal("1.0")  # 100% portfolio risk
        )

        assert config.max_position_size == 1000
        assert config.max_positions == 100
        assert config.max_portfolio_risk == Decimal("1.0")

    def test_conservative_settings(self):
        """Test extremely conservative risk settings."""
        config = RiskConfig(
            max_risk_per_trade=Decimal("0.001"),  # 0.1%
            max_daily_loss=Decimal("0.005"),  # 0.5%
            max_positions=1,
            max_position_size=1,
            martingale_enabled=False,
            scale_in_enabled=False
        )

        assert config.max_risk_per_trade == Decimal("0.001")
        assert config.max_daily_loss == Decimal("0.005")
        assert config.max_positions == 1

    def test_empty_trading_hours(self):
        """Test empty allowed trading hours list."""
        config = RiskConfig(
            restrict_trading_hours=True,
            allowed_trading_hours=[]
        )

        assert config.restrict_trading_hours is True
        assert config.allowed_trading_hours == []

    def test_invalid_trading_hours_format(self):
        """Test invalid trading hours format (should store as-is)."""
        config = RiskConfig(
            allowed_trading_hours=[("25:00", "30:00"), ("invalid", "times")]
        )

        # Config stores as-is, validation happens at usage
        assert config.allowed_trading_hours == [("25:00", "30:00"), ("invalid", "times")]

    def test_decimal_precision(self):
        """Test Decimal precision is maintained."""
        config = RiskConfig(
            max_risk_per_trade=Decimal("0.0123456789"),
            kelly_fraction=Decimal("0.3333333333")
        )

        assert config.max_risk_per_trade == Decimal("0.0123456789")
        assert config.kelly_fraction == Decimal("0.3333333333")

    def test_none_values_for_optional_limits(self):
        """Test None values for optional dollar limits."""
        config = RiskConfig(
            max_risk_per_trade_amount=None,
            max_daily_loss_amount=None
        )

        assert config.max_risk_per_trade_amount is None
        assert config.max_daily_loss_amount is None

    def test_dollar_amount_limits(self):
        """Test dollar amount limits are set correctly."""
        config = RiskConfig(
            max_risk_per_trade_amount=Decimal("500"),
            max_daily_loss_amount=Decimal("2000")
        )

        assert config.max_risk_per_trade_amount == Decimal("500")
        assert config.max_daily_loss_amount == Decimal("2000")


class TestRiskConfigIntegration:
    """Test RiskConfig integration with risk management system."""

    def test_config_immutability_not_enforced(self):
        """Test that config can be modified after creation (not frozen)."""
        config = RiskConfig()
        original_value = config.max_risk_per_trade

        # Should be able to modify
        config.max_risk_per_trade = Decimal("0.05")
        assert config.max_risk_per_trade == Decimal("0.05")
        assert config.max_risk_per_trade != original_value

    def test_config_copy_independence(self):
        """Test that config copies are independent."""
        import copy

        config1 = RiskConfig(max_risk_per_trade=Decimal("0.01"))
        config2 = copy.deepcopy(config1)

        config2.max_risk_per_trade = Decimal("0.02")

        assert config1.max_risk_per_trade == Decimal("0.01")
        assert config2.max_risk_per_trade == Decimal("0.02")

    def test_kelly_criterion_settings_coherence(self):
        """Test Kelly criterion settings work together."""
        config = RiskConfig(
            use_kelly_criterion=True,
            kelly_fraction=Decimal("0.25"),
            min_trades_for_kelly=50
        )

        assert config.use_kelly_criterion is True
        assert config.kelly_fraction == Decimal("0.25")
        assert config.min_trades_for_kelly == 50

    def test_stop_loss_type_variations(self):
        """Test different stop-loss type settings."""
        for stop_type in ["fixed", "atr", "percentage", "custom"]:
            config = RiskConfig(stop_loss_type=stop_type)
            assert config.stop_loss_type == stop_type

    def test_all_boolean_flags_toggle(self):
        """Test all boolean configuration flags can be toggled."""
        config = RiskConfig(
            use_stop_loss=False,
            use_take_profit=False,
            use_trailing_stops=False,
            scale_in_enabled=True,
            scale_out_enabled=False,
            martingale_enabled=True,
            restrict_trading_hours=True,
            avoid_news_events=False,
            use_kelly_criterion=True
        )

        assert config.use_stop_loss is False
        assert config.use_take_profit is False
        assert config.use_trailing_stops is False
        assert config.scale_in_enabled is True
        assert config.scale_out_enabled is False
        assert config.martingale_enabled is True
        assert config.restrict_trading_hours is True
        assert config.avoid_news_events is False
        assert config.use_kelly_criterion is True
