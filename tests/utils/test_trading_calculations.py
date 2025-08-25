"""Comprehensive tests for trading_calculations.py module."""

import math
from typing import Any

import pytest

from project_x_py.utils.trading_calculations import (
    calculate_position_sizing,
    calculate_position_value,
    calculate_risk_reward_ratio,
    calculate_tick_value,
    round_to_tick_size,
)


def assert_float_equal(actual: float, expected: float, tolerance: float = 1e-8) -> None:
    """Helper function to compare floats with tolerance for precision issues."""
    assert abs(actual - expected) < tolerance, f"Expected {expected}, got {actual}"


class TestCalculateTickValue:
    """Test the calculate_tick_value function."""

    def test_basic_tick_value_calculation(self):
        """Test basic tick value calculation."""
        # MGC: 5 ticks movement (0.5 / 0.1 = 5 ticks) at $1 per tick
        result = calculate_tick_value(0.5, 0.1, 1.0)
        assert result == 5.0

    def test_different_instruments(self):
        """Test with different instrument specifications."""
        # NQ: 2 points movement at $20 per point (0.25 tick size)
        nq_value = calculate_tick_value(2.0, 0.25, 5.0)  # 8 ticks * $5 = $40
        assert nq_value == 40.0

        # ES: 10 ticks movement at $12.50 per tick
        es_value = calculate_tick_value(2.5, 0.25, 12.5)  # 10 ticks * $12.50 = $125
        assert es_value == 125.0

    def test_fractional_price_changes(self):
        """Test with fractional price changes."""
        result = calculate_tick_value(0.15, 0.05, 2.0)  # 3 ticks * $2 = $6
        assert_float_equal(result, 6.0)

    def test_negative_price_changes(self):
        """Test with negative price changes (should use absolute value)."""
        result = calculate_tick_value(-0.5, 0.1, 1.0)
        assert result == 5.0  # Same as positive 0.5

    def test_zero_price_change(self):
        """Test with zero price change."""
        result = calculate_tick_value(0.0, 0.1, 1.0)
        assert result == 0.0

    def test_invalid_tick_size(self):
        """Test with invalid tick size (zero or negative)."""
        with pytest.raises(ValueError, match="tick_size must be positive"):
            calculate_tick_value(1.0, 0.0, 1.0)

        with pytest.raises(ValueError, match="tick_size must be positive"):
            calculate_tick_value(1.0, -0.1, 1.0)

    def test_negative_tick_value(self):
        """Test with negative tick value."""
        with pytest.raises(ValueError, match="tick_value cannot be negative"):
            calculate_tick_value(1.0, 0.1, -1.0)

    def test_zero_tick_value(self):
        """Test with zero tick value."""
        result = calculate_tick_value(1.0, 0.1, 0.0)
        assert result == 0.0

    def test_invalid_price_change_type(self):
        """Test with invalid price change type."""
        with pytest.raises(TypeError, match="price_change must be numeric"):
            calculate_tick_value("invalid", 0.1, 1.0)

    def test_large_price_movements(self):
        """Test with large price movements."""
        result = calculate_tick_value(100.0, 0.01, 0.5)  # 10000 ticks * $0.5 = $5000
        assert result == 5000.0

    def test_small_tick_sizes(self):
        """Test with very small tick sizes."""
        result = calculate_tick_value(1.0, 0.001, 0.1)  # 1000 ticks * $0.1 = $100
        assert result == 100.0

    def test_floating_point_precision(self):
        """Test floating point precision in calculations."""
        # Test case that might have precision issues
        result = calculate_tick_value(0.3, 0.1, 1.0)
        assert_float_equal(result, 3.0)

    def test_edge_case_values(self):
        """Test edge case values."""
        # Very small price change
        result = calculate_tick_value(1e-6, 1e-6, 1.0)
        assert result == 1.0

        # Very large tick value
        result = calculate_tick_value(1.0, 1.0, 1000.0)
        assert result == 1000.0


class TestCalculatePositionValue:
    """Test the calculate_position_value function."""

    def test_basic_position_value(self):
        """Test basic position value calculation."""
        # 5 contracts of MGC at $2050, $1 per tick, 0.1 tick size
        # Value per point = 1/0.1 * 1 = 10, Total = 5 * 2050 * 10 = $102,500
        result = calculate_position_value(5, 2050.0, 1.0, 0.1)
        assert result == 102500.0

    def test_different_contract_specifications(self):
        """Test with different contract specifications."""
        # NQ: 2 contracts at 15000, $5 per tick, 0.25 tick size
        # Value per point = 1/0.25 * 5 = 20, Total = 2 * 15000 * 20 = $600,000
        nq_value = calculate_position_value(2, 15000.0, 5.0, 0.25)
        assert nq_value == 600000.0

    def test_single_contract(self):
        """Test with single contract."""
        result = calculate_position_value(1, 100.0, 1.0, 0.1)
        expected = 1 * 100.0 * (1.0 / 0.1)  # 1000
        assert result == expected

    def test_negative_position_size(self):
        """Test with negative position size (short position)."""
        result = calculate_position_value(-3, 100.0, 1.0, 0.1)
        # Should return absolute value
        assert result == 3000.0

    def test_zero_position_size(self):
        """Test with zero position size."""
        result = calculate_position_value(0, 100.0, 1.0, 0.1)
        assert result == 0.0

    def test_invalid_tick_size(self):
        """Test with invalid tick size."""
        with pytest.raises(ValueError, match="tick_size must be positive"):
            calculate_position_value(1, 100.0, 1.0, 0.0)

    def test_invalid_tick_value(self):
        """Test with invalid tick value."""
        with pytest.raises(ValueError, match="tick_value cannot be negative"):
            calculate_position_value(1, 100.0, -1.0, 0.1)

    def test_invalid_price(self):
        """Test with invalid price."""
        with pytest.raises(ValueError, match="price cannot be negative"):
            calculate_position_value(1, -100.0, 1.0, 0.1)

    def test_invalid_size_type(self):
        """Test with invalid size type."""
        with pytest.raises(TypeError, match="size must be an integer"):
            calculate_position_value(1.5, 100.0, 1.0, 0.1)

    def test_zero_price(self):
        """Test with zero price."""
        result = calculate_position_value(5, 0.0, 1.0, 0.1)
        assert result == 0.0

    def test_fractional_tick_sizes(self):
        """Test with fractional tick sizes."""
        result = calculate_position_value(2, 50.0, 0.5, 0.05)
        # Value per point = 1/0.05 * 0.5 = 10, Total = 2 * 50 * 10 = 1000
        assert result == 1000.0

    def test_large_positions(self):
        """Test with large positions."""
        result = calculate_position_value(1000, 10.0, 0.1, 0.01)
        # Value per point = 1/0.01 * 0.1 = 10, Total = 1000 * 10 * 10 = 100,000
        assert result == 100000.0

    def test_mathematical_precision(self):
        """Test mathematical precision in calculations."""
        # Test with values that might cause precision issues
        result = calculate_position_value(3, 33.33, 0.3, 0.1)
        expected = 3 * 33.33 * (0.3 / 0.1)
        assert_float_equal(result, expected)


class TestRoundToTickSize:
    """Test the round_to_tick_size function."""

    def test_basic_rounding(self):
        """Test basic rounding to tick size."""
        assert_float_equal(round_to_tick_size(100.37, 0.1), 100.4)
        assert_float_equal(round_to_tick_size(100.33, 0.1), 100.3)

    def test_exact_tick_values(self):
        """Test with prices already on tick boundaries."""
        assert_float_equal(round_to_tick_size(100.5, 0.1), 100.5)
        assert_float_equal(round_to_tick_size(100.0, 0.25), 100.0)

    def test_different_tick_sizes(self):
        """Test with different tick sizes."""
        # 0.25 tick size (common for index futures)
        assert_float_equal(round_to_tick_size(2050.13, 0.25), 2050.25)
        assert_float_equal(round_to_tick_size(2050.10, 0.25), 2050.0)

        # 0.05 tick size
        assert_float_equal(round_to_tick_size(100.07, 0.05), 100.05)
        assert_float_equal(round_to_tick_size(100.03, 0.05), 100.05)

    def test_halfway_cases(self):
        """Test halfway rounding cases."""
        # Due to floating point precision, 100.35/0.1 = 1003.4999999999999 -> rounds to 1003 -> 100.3
        assert_float_equal(round_to_tick_size(100.35, 0.1), 100.3)
        # 100.25/0.1 = 1002.5 -> rounds to 1002 (round half to even) -> 100.2
        assert_float_equal(round_to_tick_size(100.25, 0.1), 100.2)

    def test_negative_prices(self):
        """Test with invalid negative prices."""
        with pytest.raises(ValueError, match="price cannot be negative"):
            round_to_tick_size(-100.0, 0.1)

    def test_zero_price(self):
        """Test with zero price."""
        assert_float_equal(round_to_tick_size(0.0, 0.1), 0.0)

    def test_invalid_tick_size(self):
        """Test with invalid tick sizes."""
        with pytest.raises(ValueError, match="tick_size must be positive"):
            round_to_tick_size(100.0, 0.0)

        with pytest.raises(ValueError, match="tick_size must be positive"):
            round_to_tick_size(100.0, -0.1)

    def test_very_small_tick_sizes(self):
        """Test with very small tick sizes."""
        result = round_to_tick_size(100.12345, 0.001)
        assert_float_equal(result, 100.123)

    def test_large_tick_sizes(self):
        """Test with large tick sizes."""
        result = round_to_tick_size(157.0, 5.0)
        assert_float_equal(result, 155.0)  # Rounded to nearest 5

    def test_floating_point_edge_cases(self):
        """Test floating point edge cases."""
        # Cases that might have precision issues
        result = round_to_tick_size(2050.37, 0.1)
        assert_float_equal(result, 2050.4)

        result = round_to_tick_size(99.99, 0.01)
        assert_float_equal(result, 99.99)

    def test_fractional_tick_sizes(self):
        """Test with fractional tick sizes."""
        result = round_to_tick_size(100.333, 1/3)
        # Should round to nearest 1/3: 100 1/3 = 100.3333...
        expected = round(100.333 / (1/3)) * (1/3)
        assert_float_equal(result, expected)

    def test_scientific_notation_inputs(self):
        """Test with scientific notation inputs."""
        result = round_to_tick_size(1e2 + 0.37, 0.1)  # 100.37
        assert_float_equal(result, 100.4)

    def test_precision_boundary_cases(self):
        """Test cases at precision boundaries."""
        # Test cases that might trigger floating point precision issues
        test_cases = [
            (100.15, 0.1, 100.2),  # 100.15/0.1 = 1001.5 -> rounds to 1002 -> 100.2
            (100.05, 0.1, 100.0),  # 100.05/0.1 = 1000.4999999999999 -> rounds to 1000 -> 100.0
            (99.95, 0.1, 100.0),   # 99.95/0.1 = 999.5 -> rounds to 1000 -> 100.0
            (2050.375, 0.25, 2050.5),  # Should work as expected
            (2050.125, 0.25, 2050.0),  # Should work as expected
        ]

        for price, tick_size, expected in test_cases:
            result = round_to_tick_size(price, tick_size)
            assert_float_equal(result, expected)


class TestCalculateRiskRewardRatio:
    """Test the calculate_risk_reward_ratio function."""

    def test_basic_risk_reward_calculation(self):
        """Test basic risk/reward ratio calculation."""
        # Entry: 100, Stop: 95, Target: 110
        # Risk: 5, Reward: 10, Ratio: 2.0
        result = calculate_risk_reward_ratio(100.0, 95.0, 110.0)
        assert_float_equal(result, 2.0)

    def test_equal_risk_reward(self):
        """Test equal risk and reward (1:1 ratio)."""
        result = calculate_risk_reward_ratio(100.0, 95.0, 105.0)
        assert_float_equal(result, 1.0)

    def test_higher_risk_than_reward(self):
        """Test case where risk is higher than reward."""
        result = calculate_risk_reward_ratio(100.0, 90.0, 105.0)
        assert_float_equal(result, 0.5)  # Risk: 10, Reward: 5

    def test_short_position_setup(self):
        """Test risk/reward for short position."""
        # Short at 100, stop at 105, target at 90
        result = calculate_risk_reward_ratio(100.0, 105.0, 90.0)
        assert_float_equal(result, 2.0)  # Risk: 5, Reward: 10

    def test_zero_risk(self):
        """Test with zero risk (entry equals stop)."""
        with pytest.raises(ValueError, match="Entry price and stop price cannot be equal"):
            calculate_risk_reward_ratio(100.0, 100.0, 110.0)

    def test_invalid_long_position_target(self):
        """Test invalid target for long position."""
        with pytest.raises(ValueError, match="For long positions, target must be above entry"):
            calculate_risk_reward_ratio(100.0, 95.0, 95.0)  # target below entry for long

    def test_invalid_short_position_target(self):
        """Test invalid target for short position."""
        with pytest.raises(ValueError, match="For short positions, target must be below entry"):
            calculate_risk_reward_ratio(100.0, 105.0, 105.0)  # target above entry for short

    def test_zero_reward_long_position(self):
        """Test zero reward scenario for long position."""
        # Long position: entry=100, stop=95, target=100 (zero reward)
        # This should raise ValueError because target must be above entry for long
        with pytest.raises(ValueError, match="For long positions, target must be above entry"):
            calculate_risk_reward_ratio(100.0, 95.0, 100.0)

    def test_zero_reward_short_position(self):
        """Test zero reward scenario for short position."""
        # Short position: entry=100, stop=105, target=100 (zero reward)
        # This should raise ValueError because target must be below entry for short
        with pytest.raises(ValueError, match="For short positions, target must be below entry"):
            calculate_risk_reward_ratio(100.0, 105.0, 100.0)

    def test_negative_prices(self):
        """Test with negative prices."""
        # Should work as long as the logic is consistent
        result = calculate_risk_reward_ratio(-10.0, -15.0, -5.0)
        assert_float_equal(result, 1.0)  # Risk: 5, Reward: 5

    def test_very_small_differences(self):
        """Test with very small price differences."""
        result = calculate_risk_reward_ratio(100.0, 99.99, 100.02)
        assert_float_equal(result, 2.0)  # Risk: 0.01, Reward: 0.02

    def test_large_price_differences(self):
        """Test with large price differences."""
        result = calculate_risk_reward_ratio(1000.0, 500.0, 2000.0)
        assert_float_equal(result, 2.0)  # Risk: 500, Reward: 1000

    def test_floating_point_precision(self):
        """Test floating point precision in risk/reward calculations."""
        # Use values that might cause precision issues
        result = calculate_risk_reward_ratio(100.33, 100.03, 100.93)
        expected = (100.93 - 100.33) / (100.33 - 100.03)  # 0.6 / 0.3 = 2.0
        assert_float_equal(result, expected)

    def test_edge_case_values(self):
        """Test edge case values."""
        # Very high ratio
        result = calculate_risk_reward_ratio(100.0, 99.0, 200.0)
        assert_float_equal(result, 100.0)  # Risk: 1, Reward: 100

        # Very low ratio
        result = calculate_risk_reward_ratio(100.0, 1.0, 101.0)
        expected = 1.0 / 99.0  # Risk: 99, Reward: 1
        assert_float_equal(result, expected)


class TestCalculatePositionSizing:
    """Test the calculate_position_sizing function."""

    def test_basic_position_sizing(self):
        """Test basic position sizing calculation."""
        # $50,000 account, 2% risk, entry 2050, stop 2040, tick value $1
        result = calculate_position_sizing(50000, 0.02, 2050, 2040, 1.0)

        assert isinstance(result, dict)
        assert "position_size" in result
        assert "max_dollar_risk" in result
        assert "actual_risk_percent" in result

        # Risk amount should be 2% of $50,000 = $1,000
        assert_float_equal(result["max_dollar_risk"], 1000.0)

        # Position size = Risk Amount / (Price Difference * Tick Value)
        # = 1000 / (10 * 1) = 100 contracts
        assert result["position_size"] == 100

    def test_different_risk_percentages(self):
        """Test with different risk percentages."""
        # 1% risk
        result1 = calculate_position_sizing(100000, 0.01, 2000, 1990, 1.0)
        assert_float_equal(result1["max_dollar_risk"], 1000.0)
        assert result1["position_size"] == 100

        # 5% risk
        result5 = calculate_position_sizing(100000, 0.05, 2000, 1990, 1.0)
        assert_float_equal(result5["max_dollar_risk"], 5000.0)
        assert result5["position_size"] == 500

    def test_different_tick_values(self):
        """Test with different tick values."""
        # Higher tick value should result in smaller position size
        result = calculate_position_sizing(50000, 0.02, 100, 95, 5.0)

        risk_per_contract = (100 - 95) * 5.0  # $25
        expected_size = int(1000 / risk_per_contract)  # 40 contracts
        assert result["position_size"] == expected_size

    def test_short_position(self):
        """Test position sizing for short positions."""
        # Short position: entry 100, stop 105
        result = calculate_position_sizing(50000, 0.02, 100, 105, 1.0)

        # Risk should be calculated as absolute difference
        assert_float_equal(result["max_dollar_risk"], 1000.0)
        assert result["position_size"] == 200  # 1000 / 5 = 200

    def test_zero_risk_amount(self):
        """Test with zero risk amount."""
        with pytest.raises(ValueError, match="risk_per_trade must be between 0 and 1"):
            calculate_position_sizing(50000, 0.0, 100, 95, 1.0)

    def test_invalid_account_balance(self):
        """Test with invalid account balance."""
        with pytest.raises(ValueError, match="account_balance must be positive"):
            calculate_position_sizing(-50000, 0.02, 100, 95, 1.0)

    def test_invalid_risk_percentage(self):
        """Test with invalid risk percentage."""
        with pytest.raises(ValueError, match="risk_per_trade must be between 0 and 1"):
            calculate_position_sizing(50000, 1.5, 100, 95, 1.0)

        with pytest.raises(ValueError, match="risk_per_trade must be between 0 and 1"):
            calculate_position_sizing(50000, -0.01, 100, 95, 1.0)

    def test_zero_price_difference(self):
        """Test with zero price difference (entry equals stop)."""
        result = calculate_position_sizing(50000, 0.02, 100, 100, 1.0)

        # Should return error when no price risk
        assert "error" in result
        assert "No price risk" in result["error"]

    def test_invalid_tick_value(self):
        """Test with invalid tick value."""
        with pytest.raises(ValueError, match="tick_value must be positive"):
            calculate_position_sizing(50000, 0.02, 100, 95, 0.0)

    def test_large_account_balance(self):
        """Test with large account balance."""
        result = calculate_position_sizing(1000000, 0.01, 2000, 1990, 1.0)

        assert_float_equal(result["max_dollar_risk"], 10000.0)
        assert result["position_size"] == 1000

    def test_small_price_differences(self):
        """Test with small price differences."""
        result = calculate_position_sizing(50000, 0.02, 100.0, 99.9, 0.1)

        # Risk per contract = 0.1 * 0.1 = 0.01
        expected_size = int(1000 / 0.01)  # 100,000 contracts
        assert result["position_size"] == expected_size

    def test_fractional_calculations(self):
        """Test with fractional calculations."""
        result = calculate_position_sizing(33333, 0.03, 150.5, 145.25, 2.5)

        # Should handle fractional values correctly
        assert isinstance(result["position_size"], int)
        assert isinstance(result["max_dollar_risk"], float)
        assert isinstance(result["actual_risk_percent"], float)

    def test_actual_risk_percentage_calculation(self):
        """Test actual risk percentage calculation."""
        result = calculate_position_sizing(50000, 0.02, 100, 95, 1.0)

        # Actual risk should match target when position size is exact
        # Position size 200 * risk per contract 5 = 1000
        actual_risk = result["position_size"] * 5  # risk per contract
        actual_risk_percent = actual_risk / 50000

        assert_float_equal(result["actual_risk_percent"], actual_risk_percent)

    def test_position_sizing_edge_cases(self):
        """Test edge cases in position sizing."""
        # Very small account
        result = calculate_position_sizing(1000, 0.02, 100, 95, 1.0)
        assert result["max_dollar_risk"] == 20.0
        assert result["position_size"] == 4

        # Very large risk per contract
        result = calculate_position_sizing(50000, 0.02, 1000, 900, 1.0)
        assert result["position_size"] == 10  # 1000 / 100 = 10
