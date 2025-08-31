"""
Tests for Lorenz Formula Indicator

Author: @TexasCoding
Date: 2025-01-31

Test suite for the Lorenz Formula indicator which uses chaos theory to analyze
market dynamics through OHLCV data transformation into a chaotic dynamical system.
"""

import numpy as np
import polars as pl
import pytest

from project_x_py.indicators.lorenz import LORENZ, LORENZIndicator, calculate_lorenz


class TestLorenzIndicator:
    """Test suite for Lorenz Formula indicator."""

    @pytest.fixture
    def sample_data(self) -> pl.DataFrame:
        """Create sample OHLCV data for testing."""
        np.random.seed(42)
        n = 100

        # Generate realistic OHLCV data
        prices = 100 + np.cumsum(np.random.randn(n) * 0.5)

        return pl.DataFrame({
            "open": prices + np.random.randn(n) * 0.1,
            "high": prices + abs(np.random.randn(n) * 0.3),
            "low": prices - abs(np.random.randn(n) * 0.3),
            "close": prices,
            "volume": np.random.uniform(1000, 10000, n)
        })

    def test_lorenz_initialization(self):
        """Test LORENZ indicator initialization."""
        indicator = LORENZIndicator()
        assert indicator.name == "LORENZ"
        assert "Lorenz Formula" in indicator.description
        assert "chaos theory" in indicator.description.lower()

    def test_lorenz_basic_calculation(self, sample_data):
        """Test basic Lorenz calculation with default parameters."""
        indicator = LORENZIndicator()
        result = indicator.calculate(sample_data)

        # Check that all required columns are present
        assert "lorenz_x" in result.columns
        assert "lorenz_y" in result.columns
        assert "lorenz_z" in result.columns

        # Check data types
        assert result["lorenz_x"].dtype == pl.Float64
        assert result["lorenz_y"].dtype == pl.Float64
        assert result["lorenz_z"].dtype == pl.Float64

        # Check that we have values (not all null)
        assert not result["lorenz_x"].is_null().all()
        assert not result["lorenz_y"].is_null().all()
        assert not result["lorenz_z"].is_null().all()

    def test_lorenz_custom_parameters(self, sample_data):
        """Test Lorenz calculation with custom parameters."""
        indicator = LORENZIndicator()
        result = indicator.calculate(
            sample_data,
            window=20,
            dt=0.01,
            volatility_scale=0.03,
            initial_x=1.0,
            initial_y=1.0,
            initial_z=1.0
        )

        # Verify columns exist
        assert "lorenz_x" in result.columns
        assert "lorenz_y" in result.columns
        assert "lorenz_z" in result.columns

        # Check initial values
        first_x = result["lorenz_x"][0]
        first_y = result["lorenz_y"][0]
        first_z = result["lorenz_z"][0]

        assert first_x == 1.0
        assert first_y == 1.0
        assert first_z == 1.0

    def test_lorenz_small_dt_stability(self, sample_data):
        """Test that smaller dt values produce more stable updates."""
        indicator = LORENZIndicator()

        # Calculate with large dt
        result_large_dt = indicator.calculate(sample_data, dt=1.0)

        # Calculate with small dt
        result_small_dt = indicator.calculate(sample_data, dt=0.01)

        # Small dt should produce smaller changes between consecutive values
        diff_large = abs(result_large_dt["lorenz_z"].diff()).drop_nulls().mean()
        diff_small = abs(result_small_dt["lorenz_z"].diff()).drop_nulls().mean()

        assert diff_small < diff_large

    def test_lorenz_window_size_validation(self, sample_data):
        """Test validation of window size parameter."""
        indicator = LORENZIndicator()

        # Test with valid window
        result = indicator.calculate(sample_data, window=10)
        assert "lorenz_z" in result.columns

        # Test with window larger than data
        with pytest.raises(Exception):  # Should raise IndicatorError
            indicator.calculate(sample_data[:5], window=10)

    def test_lorenz_handles_nan_gracefully(self, sample_data):
        """Test that Lorenz handles NaN values in early rows gracefully."""
        indicator = LORENZIndicator()
        result = indicator.calculate(sample_data, window=14)

        # Early rows should use default parameters when volatility is NaN
        # But should still produce numeric outputs
        for i in range(14):  # First window period
            assert not np.isnan(result["lorenz_x"][i])
            assert not np.isnan(result["lorenz_y"][i])
            assert not np.isnan(result["lorenz_z"][i])

    def test_lorenz_function_interface(self, sample_data):
        """Test the function-based interface."""
        result = calculate_lorenz(sample_data, window=14, dt=0.1)

        assert "lorenz_x" in result.columns
        assert "lorenz_y" in result.columns
        assert "lorenz_z" in result.columns

    def test_lorenz_talib_style_interface(self, sample_data):
        """Test TA-Lib style LORENZ function."""
        result = LORENZ(sample_data, window=14, dt=0.1)

        assert "lorenz_x" in result.columns
        assert "lorenz_y" in result.columns
        assert "lorenz_z" in result.columns

    def test_lorenz_chaos_property(self, sample_data):
        """Test that Lorenz system can produce different outputs with different initial conditions."""
        indicator = LORENZIndicator()

        # Run with different initial conditions
        result1 = indicator.calculate(sample_data, initial_x=0.0, initial_y=1.0, initial_z=0.0)
        result2 = indicator.calculate(sample_data, initial_x=5.0, initial_y=5.0, initial_z=5.0)

        # The systems should produce different trajectories
        z1_values = result1["lorenz_z"].to_list()
        z2_values = result2["lorenz_z"].to_list()

        # Check that outputs are not identical (different initial conditions lead to different paths)
        assert z1_values != z2_values

    def test_lorenz_parameter_scaling(self, sample_data):
        """Test that parameters are properly scaled from market data."""
        indicator = LORENZIndicator()
        result = indicator.calculate(sample_data, window=14)

        # Parameters should be dynamic and change over time
        # Check that z values vary (not constant)
        z_values = result["lorenz_z"].drop_nulls()
        z_std = z_values.std()

        assert z_std > 0  # Should have variation

    def test_lorenz_volume_impact(self):
        """Test that volume ratio is calculated and affects the system."""
        # Create simple test data
        n = 30
        data = pl.DataFrame({
            "open": [100.0] * n,
            "high": [101.0] * n,
            "low": [99.0] * n,
            "close": [100.0 + i * 0.1 for i in range(n)],  # Slight trend
            "volume": [5000.0 if i < 15 else 10000.0 for i in range(n)]  # Volume step change
        })

        indicator = LORENZIndicator()
        result = indicator.calculate(data, window=10, dt=0.01)

        # Check that Lorenz values are calculated
        assert "lorenz_x" in result.columns
        assert "lorenz_y" in result.columns
        assert "lorenz_z" in result.columns

        # Verify we have numeric outputs (not all NaN or same value)
        z_values = result["lorenz_z"].drop_nulls().to_list()
        assert len(z_values) > 0
        # Check that there's some variation in the output
        assert len(set(z_values)) > 1

    def test_lorenz_with_missing_columns(self):
        """Test error handling when required columns are missing."""
        incomplete_data = pl.DataFrame({
            "close": [100, 101, 102],
            "volume": [1000, 1100, 1200]
        })

        indicator = LORENZIndicator()
        with pytest.raises(Exception):  # Should raise IndicatorError
            indicator.calculate(incomplete_data)

    def test_lorenz_empty_data(self):
        """Test error handling with empty DataFrame."""
        empty_data = pl.DataFrame({
            "open": [],
            "high": [],
            "low": [],
            "close": [],
            "volume": []
        })

        indicator = LORENZIndicator()
        with pytest.raises(Exception):  # Should raise IndicatorError
            indicator.calculate(empty_data)

    def test_lorenz_single_row(self):
        """Test behavior with single row of data."""
        single_row = pl.DataFrame({
            "open": [100.0],
            "high": [101.0],
            "low": [99.0],
            "close": [100.5],
            "volume": [1000.0]
        })

        indicator = LORENZIndicator()
        result = indicator.calculate(single_row, window=1)

        # Should return initial values only
        assert len(result) == 1
        assert result["lorenz_x"][0] == 0.0  # Default initial
        assert result["lorenz_y"][0] == 1.0  # Default initial
        assert result["lorenz_z"][0] == 0.0  # Default initial

    def test_lorenz_convergence_with_stable_prices(self):
        """Test that Lorenz converges with stable prices."""
        # Create stable price data
        n = 100
        stable_data = pl.DataFrame({
            "open": [100.0] * n,
            "high": [100.1] * n,
            "low": [99.9] * n,
            "close": [100.0] * n,
            "volume": [5000.0] * n
        })

        indicator = LORENZIndicator()
        result = indicator.calculate(stable_data, window=14, dt=0.01)

        # With stable data, the system should stabilize
        # Check last 10 values have low variance
        last_10_z = result["lorenz_z"][-10:]
        z_variance = last_10_z.var()

        # Variance should be relatively small for stable market
        assert z_variance is not None
        assert z_variance < 10.0  # Threshold for "stable"
