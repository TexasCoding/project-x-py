#!/usr/bin/env python3
"""
Example: Lorenz Formula Indicator - Chaos Theory Market Analysis

This example demonstrates how to use the Lorenz Formula indicator which applies
chaos theory to market analysis. The Lorenz system creates a dynamic attractor
that responds to market volatility, trend strength, and volume patterns.

The indicator generates three output values (x, y, z) that can reveal:
- Market instability and potential breakouts
- Regime changes in market behavior
- Hidden patterns not captured by traditional indicators

Author: @TexasCoding
Date: 2025-01-31
"""

import asyncio
from datetime import timedelta

import polars as pl

from project_x_py import ProjectX
from project_x_py.indicators import LORENZ, calculate_lorenz


async def main():
    """Demonstrate Lorenz Formula indicator usage."""

    # Initialize client
    async with ProjectX.from_env() as client:
        print("=== Lorenz Formula Indicator Example ===\n")

        # Authenticate
        await client.authenticate()
        print("✓ Authenticated with TopStepX\n")

        # Get historical data for analysis
        instrument = "MNQ"
        print(f"Fetching historical data for {instrument}...")

        # Get bars for analysis
        df = await client.get_bars(instrument, days=5)

        if df is None or df.is_empty():
            print("No data available")
            return

        print(f"✓ Retrieved {len(df)} bars\n")

        # Example 1: Basic Lorenz calculation with defaults
        print("Example 1: Basic Lorenz Calculation")
        print("-" * 40)

        # Calculate Lorenz with default parameters
        result = LORENZ(df)

        # Display sample results
        print("Latest Lorenz values:")
        latest = result.tail(5).select(
            ["timestamp", "close", "lorenz_x", "lorenz_y", "lorenz_z"]
        )
        print(latest)
        print()

        # Example 2: Custom parameters for different sensitivity
        print("Example 2: Custom Parameters (Smaller dt for stability)")
        print("-" * 40)

        # Use smaller dt for more gradual updates
        result_stable = calculate_lorenz(
            df,
            window=20,  # Longer window for smoother parameters
            dt=0.01,  # Smaller time step for stability
            volatility_scale=0.015,  # Adjust based on market
        )

        # Compare volatility of outputs
        z_default = result["lorenz_z"].drop_nulls()
        z_stable = result_stable["lorenz_z"].drop_nulls()

        print(f"Default parameters - Z std dev: {z_default.std():.4f}")
        print(f"Stable parameters  - Z std dev: {z_stable.std():.4f}")
        print()

        # Example 3: Using Lorenz for signal generation
        print("Example 3: Signal Generation with Lorenz")
        print("-" * 40)

        # Calculate Lorenz and generate signals
        signal_df = LORENZ(df, window=14, dt=0.1)

        # Add signal logic based on z-value
        signal_df = signal_df.with_columns(
            [
                # Z-value momentum (positive = bullish, negative = bearish)
                pl.when(pl.col("lorenz_z") > 0)
                .then(pl.lit(1))
                .when(pl.col("lorenz_z") < 0)
                .then(pl.lit(-1))
                .otherwise(pl.lit(0))
                .alias("z_signal"),
                # Z-value crossing its moving average
                pl.col("lorenz_z").rolling_mean(window_size=10).alias("z_ma"),
            ]
        )

        # Add crossover signals
        signal_df = signal_df.with_columns(
            [
                pl.when(
                    (pl.col("lorenz_z") > pl.col("z_ma"))
                    & (pl.col("lorenz_z").shift(1) <= pl.col("z_ma").shift(1))
                )
                .then(pl.lit("BUY"))
                .when(
                    (pl.col("lorenz_z") < pl.col("z_ma"))
                    & (pl.col("lorenz_z").shift(1) >= pl.col("z_ma").shift(1))
                )
                .then(pl.lit("SELL"))
                .otherwise(pl.lit(""))
                .alias("crossover_signal")
            ]
        )

        # Show signals
        signals = signal_df.filter(pl.col("crossover_signal") != "").tail(10)
        if len(signals) > 0:
            print("Recent crossover signals:")
            print(
                signals.select(
                    ["timestamp", "close", "lorenz_z", "z_ma", "crossover_signal"]
                )
            )
        else:
            print("No crossover signals in recent data")
        print()

        # Example 4: Regime detection using Lorenz
        print("Example 4: Market Regime Detection")
        print("-" * 40)

        # Calculate with parameters suited for regime detection
        regime_df = calculate_lorenz(df, window=30, dt=0.05)

        # Analyze the attractor's behavior
        regime_df = regime_df.with_columns(
            [
                # Distance from origin (magnitude of chaos)
                (
                    pl.col("lorenz_x") ** 2
                    + pl.col("lorenz_y") ** 2
                    + pl.col("lorenz_z") ** 2
                )
                .sqrt()
                .alias("chaos_magnitude"),
                # Rate of change in z (instability measure)
                pl.col("lorenz_z").diff().abs().alias("z_volatility"),
            ]
        )

        # Classify regimes based on chaos magnitude
        regime_df = regime_df.with_columns(
            [
                pl.when(pl.col("chaos_magnitude") < 10)
                .then(pl.lit("STABLE"))
                .when(pl.col("chaos_magnitude") < 50)
                .then(pl.lit("TRANSITIONAL"))
                .otherwise(pl.lit("CHAOTIC"))
                .alias("market_regime")
            ]
        )

        # Show regime analysis
        print("Market regime distribution:")
        regime_counts = regime_df.group_by("market_regime").len().sort("market_regime")
        print(regime_counts)
        print()

        print("Latest market regime:")
        latest_regime = regime_df.tail(1).select(
            ["timestamp", "close", "chaos_magnitude", "market_regime"]
        )
        print(latest_regime)
        print()

        # Example 5: Combining with other indicators
        print("Example 5: Combining Lorenz with RSI")
        print("-" * 40)

        from project_x_py.indicators import RSI

        # Calculate both indicators
        combined_df = LORENZ(df, window=14, dt=0.1)
        combined_df = RSI(combined_df, period=14)

        # Create combined signal
        combined_df = combined_df.with_columns(
            [
                # Strong buy: Lorenz turning positive + oversold RSI
                pl.when(
                    (pl.col("lorenz_z") > 0)
                    & (pl.col("lorenz_z").shift(1) <= 0)
                    & (pl.col("rsi_14") < 35)
                )
                .then(pl.lit("STRONG_BUY"))
                # Strong sell: Lorenz turning negative + overbought RSI
                .when(
                    (pl.col("lorenz_z") < 0)
                    & (pl.col("lorenz_z").shift(1) >= 0)
                    & (pl.col("rsi_14") > 65)
                )
                .then(pl.lit("STRONG_SELL"))
                .otherwise(pl.lit(""))
                .alias("combined_signal")
            ]
        )

        # Show combined signals
        combined_signals = combined_df.filter(pl.col("combined_signal") != "").tail(5)
        if len(combined_signals) > 0:
            print("Combined Lorenz + RSI signals:")
            print(
                combined_signals.select(
                    ["timestamp", "close", "lorenz_z", "rsi_14", "combined_signal"]
                )
            )
        else:
            print("No combined signals in recent data")
        print()

        # Summary statistics
        print("=== Lorenz Indicator Statistics ===")
        print("-" * 40)

        final_df = LORENZ(df, window=14, dt=0.1)

        # Calculate statistics for each component
        for component in ["lorenz_x", "lorenz_y", "lorenz_z"]:
            values = final_df[component].drop_nulls()
            if len(values) > 0:
                min_val = values.min()
                max_val = values.max()
                if min_val is not None and max_val is not None:
                    print(f"\n{component.upper()}:")
                    print(f"  Mean:     {values.mean():8.4f}")
                    print(f"  Std Dev:  {values.std():8.4f}")
                    print(f"  Min:      {min_val:8.4f}")
                    print(f"  Max:      {max_val:8.4f}")
                    print(f"  Range:    {max_val - min_val:8.4f}")  # type: ignore
                else:
                    print(f"\n{component.upper()}: Invalid data")
            else:
                print(f"\n{component.upper()}: No data available")

        # Tips for using Lorenz
        print("\n=== Tips for Using Lorenz Indicator ===")
        print("-" * 40)
        print("1. Adjust 'dt' parameter:")
        print("   - Smaller dt (0.01-0.1): More stable, gradual changes")
        print("   - Larger dt (0.5-1.0): More sensitive, faster response")
        print()
        print("2. Window size affects parameter calculation:")
        print("   - Shorter window (10-14): More responsive to recent changes")
        print("   - Longer window (20-30): Smoother, more stable parameters")
        print()
        print("3. Primary signal is 'lorenz_z':")
        print("   - Positive Z: Bullish tendency")
        print("   - Negative Z: Bearish tendency")
        print("   - Large |Z|: Strong trend or volatility")
        print()
        print("4. Monitor chaos magnitude (x²+y²+z²):")
        print("   - Low values: Stable market")
        print("   - High values: Chaotic/volatile market")
        print()
        print("5. Combine with other indicators for confirmation")
        print("   - Use with momentum indicators (RSI, MACD)")
        print("   - Confirm with volume indicators")
        print("   - Validate with price action")


if __name__ == "__main__":
    asyncio.run(main())
